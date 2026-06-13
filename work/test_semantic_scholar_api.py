import sys

from semantic_scholar_enrich import (
    semantic_scholar_api_key,
    semantic_scholar_available,
    semantic_scholar_paper_by_doi,
)


TEST_DOIS = [
    "10.1126/sciadv.adt0318",
    "10.1038/s44460-026-00033-3",
]


def main() -> int:
    if not semantic_scholar_available():
        print("Semantic Scholar: unavailable")
        print("Set SEMANTIC_SCHOLAR_API_KEY or unset SEMANTIC_SCHOLAR_REQUIRE_KEY.")
        return 2

    key_status = "FOUND" if semantic_scholar_api_key() else "NOT FOUND; using public fallback"
    print(f"Semantic Scholar API key: {key_status}")
    for doi in TEST_DOIS:
        print(f"\nDOI: {doi}")
        data = semantic_scholar_paper_by_doi(doi)
        if not data:
            print("Result: empty response")
            continue
        if data.get("not_found"):
            print("Result: not found in Semantic Scholar")
            continue
        if data.get("error"):
            print(f"Result: {data['error']}")
            continue

        abstract = data.get("abstract") or ""
        print(f"Title: {data.get('title') or '(no title)'}")
        print(f"Venue: {data.get('venue') or '(no venue)'}")
        print(f"Year: {data.get('year') or '(no year)'}")
        print(f"Citations: {data.get('citationCount') or 0}")
        print(f"Influential citations: {data.get('influentialCitationCount') or 0}")
        print(f"Abstract length: {len(abstract)}")
        print(f"Abstract preview: {abstract[:600] if abstract else '(no abstract returned)'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
