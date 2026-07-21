from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from news_fetcher import NewsFetcher
from snowflake_loader import SnowflakeLoader
from utils import (
    validate_required_columns,
    remove_dataframe_duplicates,
    normalize_value,
    clean_text,
)

import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent
DBT_PROJECT_DIR = PROJECT_ROOT / "ai_news_dbt"
ENRICHMENT_SCRIPT = PROJECT_ROOT / "enrich_news_groq.py"


PIPELINE_NAME = "DAILY_INCREMENTAL"
OVERLAP_DAYS = 2

REQUIRED_COLUMNS = [
    "article_key",
    "provider",
    "query_name",
    "query_text",
    "source_name",
    "title",
    "article_url",
    "published_at",
    "batch_id",
    "ingested_at",
    "raw_json",
]

TEXT_COLUMNS = [
    "provider",
    "query_name",
    "query_text",
    "source_name",
    "source_id",
    "author",
    "title",
    "description",
    "article_url",
    "image_url",
    "language",
    "country",
    "category",
]

def run_python_script(
    script_path: Path,
    description: str,
) -> None:
    """
    Run another Python script using the same virtual environment.
    """

    command = [
        sys.executable,
        str(script_path),
    ]

    print(
        f"[INFO] Running {description}: "
        f"{' '.join(command)}"
    )

    result = subprocess.run(
        command,
        cwd=script_path.parent,
        check=False,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"{description} failed with exit code "
            f"{result.returncode}."
        )

def prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply the same cleaning steps used by the initial ingestion.
    """

    validate_required_columns(
        df,
        REQUIRED_COLUMNS,
    )

    df = remove_dataframe_duplicates(df)

    for column in TEXT_COLUMNS:
        if column in df.columns:
            df[column] = df[column].apply(clean_text)

    for column in df.columns:
        df[column] = df[column].apply(normalize_value)

    df["published_at"] = pd.to_datetime(
        df["published_at"],
        errors="coerce",
        utc=True,
        format="mixed",
    ).dt.tz_localize(None)

    df["ingested_at"] = pd.to_datetime(
        df["ingested_at"],
        errors="coerce",
        utc=True,
        format="mixed",
    ).dt.tz_localize(None)

    df.columns = [
        column.upper()
        for column in df.columns
    ]

    return df


def main():
    print("=" * 60)
    print("AI NEWS MONITOR - INCREMENTAL INGESTION")
    print("=" * 60)

    loader = SnowflakeLoader()
    run_id = None
    run_started = False

    try:
        print("\nStep 1: Connect to Snowflake")

        loader.connect()

        print("\nStep 2: Read last successful checkpoint")

        last_fetch_to = loader.get_last_successful_fetch_to()

        if last_fetch_to is None:
            raise RuntimeError(
                "No successful FETCH_TO checkpoint was found."
            )

        fetch_from = last_fetch_to - timedelta(
            days=OVERLAP_DAYS
        )

        fetch_to = datetime.now(
            timezone.utc
        ).date()

        print(
            f"Last successful FETCH_TO: {last_fetch_to}"
        )
        print(
            f"Calculated FETCH_FROM: {fetch_from}"
        )
        print(
            f"Calculated FETCH_TO: {fetch_to}"
        )

        print("\nStep 3: Create dynamic fetcher")

        fetcher = NewsFetcher(
            from_date=fetch_from,
            to_date=fetch_to,
            batch_prefix="DAILY",
        )

        run_id = fetcher.batch_id

        loader.start_pipeline_run(
            run_id=run_id,
            pipeline_name=PIPELINE_NAME,
            fetch_from=fetch_from,
            fetch_to=fetch_to,
        )

        run_started = True

        print("\nStep 4: Fetch articles")

        df = fetcher.fetch_all()

        rows_fetched = len(df)

        print(
            f"Articles retained after filtering: "
            f"{rows_fetched}"
        )

        if df.empty:
            loader.complete_pipeline_run(
                run_id=run_id,
                rows_fetched=0,
                rows_staged=0,
                rows_inserted=0,
                comments=(
                    "No eligible articles were returned "
                    "for the calculated date range."
                ),
            )

            print(
                "\nIncremental ingestion completed. "
                "No new articles were found."
            )

            return

        print("\nStep 5: Validate and prepare data")

        df = prepare_dataframe(df)

        print(
            f"Valid rows ready for landing: {len(df)}"
        )

        print("\nStep 6: Upload landing batch")

        rows_landed = loader.upload_landing(
            df,
            table_name="NEWS_ARTICLES_LANDING",
        )

        print("\nStep 7: Merge landing batch into RAW")

        raw_rows_before = loader.get_table_row_count(
            table_name="NEWS_ARTICLES_RAW",
        )

        loader.execute_sql_file(
            "sql/merge_news.sql"
        )

        raw_rows_after = loader.get_table_row_count(
            table_name="NEWS_ARTICLES_RAW",
        )

        rows_inserted = raw_rows_after - raw_rows_before

        print(
            f"New RAW rows inserted: {rows_inserted}"
        )

        if rows_inserted > 0:
            print("\nStep 8: Build dbt STG and INT")

            run_dbt_command(
                "stg_news_articles int_news_ready_for_llm"
            )
        else:
            print(
                "\nStep 8: No new RAW rows. "
                "dbt STG and INT rebuild not required."
            )

        print("\nStep 9: Check pending Groq enrichment")

        run_python_script(
            script_path=ENRICHMENT_SCRIPT,
            description="Groq enrichment",
        )

        print("\nStep 10: Build dbt MART")

        run_dbt_command(
            "mart_news_dashboard"
        )

        if rows_inserted > 0:
            success_comment = (
                "Incremental ingestion completed with "
                f"{OVERLAP_DAYS}-day overlap. "
                f"{rows_inserted} new RAW rows inserted. "
                "Pending Groq enrichment checked and MART rebuilt. "
            )
        else:
            success_comment = (
                "Incremental ingestion completed with "
                f"{OVERLAP_DAYS}-day overlap. "
                "No new RAW rows inserted; downstream steps skipped."
            )

        loader.complete_pipeline_run(
            run_id=run_id,
            rows_fetched=rows_fetched,
            rows_staged=rows_landed,
            rows_inserted=rows_inserted,
            comments=success_comment,
        )
        print(
            "\nIncremental ingestion completed successfully."
        )

    except Exception as error:
        print(f"\n[ERROR] {error}")

        if run_started and run_id is not None:
            try:
                loader.fail_pipeline_run(
                    run_id=run_id,
                    comments=str(error),
                )
            except Exception as log_error:
                print(
                    f"[ERROR] Failed to update pipeline log: "
                    f"{log_error}"
                )

        raise

    finally:
        loader.close()


def run_dbt_command(select: str) -> None:
    """
    Run a dbt build command for the selected models.
    """

    command = [
        "dbt",
        "build",
        "--select",
        select,
    ]

    print(
        f"[INFO] Running dbt: "
        f"{' '.join(command)}"
    )

    result = subprocess.run(
        command,
        cwd=DBT_PROJECT_DIR,
        check=False,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"dbt failed for selector: {select}"
        )

if __name__ == "__main__":
    main()