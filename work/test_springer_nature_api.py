from springer_nature_enrich import (
    springer_nature_available,
    springer_nature_record_by_doi,
)


TEST_DOIS = [
    "10.1038/s44460-026-00033-3",
    "10.1038/s41378-025-00987-3",
]


def main() -> int:
    if not springer_nature_available():
        print("Springer Nature Meta API key: NOT FOUND")
        print(
            "Set one of SPRINGER_NATURE_API_KEY, SPRINGERNATURE_API_KEY, "
            "or SPRINGER_API_KEY before running this test."
        )
        return 2

    print("Springer Nature Meta API key: FOUND")
    for doi in TEST_DOIS:
        print(f"\nDOI: {doi}")
        data = springer_nature_record_by_doi(doi)
        if not data:
            print("Result: empty response")
            continue
        if data.get("not_found"):
            print("Result: not found in Springer Nature API")
            continue
        if data.get("error"):
            print(f"Result: {data['error']}")
            continue

        abstract = data.get("abstract") or ""
        print(f"Endpoint: {data.get('endpoint') or '(unknown)'}")
        print(f"Title: {data.get('title') or '(no title)'}")
        print(f"Venue: {data.get('venue') or '(no venue)'}")
        print(f"Date: {data.get('date') or '(no date)'}")
        print(f"Abstract length: {len(abstract)}")
        print(f"Abstract preview: {abstract[:600] if abstract else '(no abstract returned)'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
