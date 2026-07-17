from snowflake_loader import SnowflakeLoader


def main():
    loader = SnowflakeLoader()

    try:
        loader.connect()

        checkpoint = loader.get_last_successful_fetch_to()

        print(f"Last successful FETCH_TO: {checkpoint}")

    finally:
        loader.close()


if __name__ == "__main__":
    main()