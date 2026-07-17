"""
ingest_news_initial.py

Initial load of AI news into Snowflake.
"""

from news_fetcher import NewsFetcher
from snowflake_loader import SnowflakeLoader
from utils import (
    validate_required_columns,
    remove_dataframe_duplicates,
    normalize_value,
    clean_text
)
import pandas as pd

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
    "raw_json"
]


def main():

    print("=" * 60)
    print("AI NEWS MONITOR - INITIAL INGESTION")
    print("=" * 60)

    loader = SnowflakeLoader()

    try:

        print("\nStep 1 : Fetch articles")

        fetcher = NewsFetcher()

        df = fetcher.fetch_all()

        print(f"Fetched {len(df)} articles")

        print("\nStep 2 : Validate data")

        validate_required_columns(
            df,
            REQUIRED_COLUMNS
        )

        df = remove_dataframe_duplicates(df)

        print(f"Valid articles : {len(df)}")

        print("\nStep 3 : Connect Snowflake")

        loader.connect()

        print("\nStep 4 : Upload Stage")
        
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


        for col in TEXT_COLUMNS:
            if col in df.columns:
                df[col] = df[col].apply(clean_text)

        for col in df.columns:
            df[col] = df[col].apply(normalize_value)

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

        df.columns = [col.upper() for col in df.columns]

        print(df.columns.tolist())

        rows_uploaded = loader.upload_stage(
            df,
            table_name="NEWS_ARTICLES_STAGE"
        )

        print("\nStep 5 : Merge Stage -> Raw")

        loader.execute_sql_file(
            "sql/merge_news.sql"
        )

        print("\nStep 6 : Write Pipeline Log")

        loader.write_log(
            run_id=df.iloc[0]["BATCH_ID"],
            pipeline_name="INITIAL_LOAD",
            status="SUCCESS",
            rows_inserted=rows_uploaded,
            comments=f"Loaded {rows_uploaded} rows."
        )

        print("\nInitial ingestion completed successfully.")

    except Exception as ex:

        print(ex)

        try:

            loader.write_log(
                run_id="UNKNOWN",
                pipeline_name="INITIAL_LOAD",
                status="FAILED",
                rows_inserted=0,
                comments=str(ex)
            )

        except Exception:

            pass

    finally:

        loader.close()


if __name__ == "__main__":

    main()