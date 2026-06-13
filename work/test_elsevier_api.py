from elsevier_enrich import elsevier_available, elsevier_record_by_doi


TEST_DOIS = [
    "10.1016/j.nanoen.2025.111439",
    "10.1016/j.nanoen.2025.110671",
    "10.1016/j.device.2024.100437",
]


def main() -> int:
    if not elsevier_available():
        print("Elsevier API key: NOT FOUND")
        print("Set ELSEVIER_API_KEY before running this test.")
        return 2

    print("Elsevier API key: FOUND")
    for doi in TEST_DOIS:
        print(f"\nDOI: {doi}")
        data = elsevier_record_by_doi(doi)
        if not data:
            print("Result: empty response")
            continue
        if data.get("not_found"):
            print("Result: not found in Elsevier API")
            continue
        if data.get("error"):
            print(f"Result: {data['error']}")
            continue

        abstract = data.get("abstract") or ""
        print(f"Endpoint: {data.get('endpoint') or '(unknown)'}")
        print(f"Title: {data.get('title') or '(no title)'}")
        print(f"Venue: {data.get('venue') or '(no venue)'}")
        print(f"Date: {data.get('date') or '(no date)'}")
        print(f"Citations: {data.get('citation_count') or 0}")
        print(f"Abstract length: {len(abstract)}")
        print(f"Abstract preview: {abstract[:600] if abstract else '(no abstract returned)'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
