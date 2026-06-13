from crossref_enrich import crossref_available, crossref_work_by_doi


TEST_DOIS = [
    "10.1126/sciadv.adt0318",
    "10.1038/s44460-026-00033-3",
]


def main() -> int:
    if not crossref_available():
        print("Crossref: disabled")
        return 2

    print("Crossref: available")
    for doi in TEST_DOIS:
        print(f"\nDOI: {doi}")
        data = crossref_work_by_doi(doi)
        if not data:
            print("Result: empty response")
            continue
        if data.get("not_found"):
            print("Result: not found in Crossref")
            continue
        if data.get("error"):
            print(f"Result: {data['error']}")
            continue

        abstract = data.get("abstract") or ""
        print(f"Title: {data.get('title') or '(no title)'}")
        print(f"Venue: {data.get('venue') or '(no venue)'}")
        print(f"Date: {data.get('date') or '(no date)'}")
        print(f"Citations: {data.get('citation_count') or 0}")
        print(f"Abstract length: {len(abstract)}")
        print(f"Abstract preview: {abstract[:600] if abstract else '(no abstract returned)'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
