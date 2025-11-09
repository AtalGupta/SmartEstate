import argparse

from smartestate.etl import ingest_excel


def main():
    parser = argparse.ArgumentParser(description="Ingest property Excel into Postgres and Elasticsearch")
    parser.add_argument("--file", required=True, help="Path to Excel file")
    args = parser.parse_args()
    res = ingest_excel(args.file)
    print(res)


if __name__ == "__main__":
    main()

