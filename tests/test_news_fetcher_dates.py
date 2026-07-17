from datetime import date

from news_fetcher import NewsFetcher


def main():
    fetcher = NewsFetcher(
        from_date=date(2026, 7, 10),
        to_date=date(2026, 7, 16),
        batch_prefix="DAILY",
    )

    print(f"Batch ID: {fetcher.batch_id}")
    print(f"From date: {fetcher.from_date}")
    print(f"To date: {fetcher.to_date}")


if __name__ == "__main__":
    main()