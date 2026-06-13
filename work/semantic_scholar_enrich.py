import html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from radar_state import RADAR_ARTIFACT_DIR

S2_BASE = "https://api.semanticscholar.org/graph/v1/paper/"
S2_FIELDS = ",".join(
    [
        "paperId",
        "externalIds",
        "title",
        "abstract",
        "venue",
        "year",
        "publicationDate",
        "url",
        "citationCount",
        "influentialCitationCount",
        "isOpenAccess",
        "openAccessPdf",
    ]
)
S2_CACHE_PATH = RADAR_ARTIFACT_DIR / "cache" / "semantic_scholar_cache.json"
S2_USER_AGENT = "Codex research-paper-radar semantic-scholar-enrichment"
DEFAULT_ENRICH_LIMIT = 120
REQUIRE_API_KEY = os.environ.get("SEMANTIC_SCHOLAR_REQUIRE_KEY", "").strip().lower() in {"1", "true", "yes"}

_cache = None
_cache_dirty = False
_last_call_at = 0.0


def semantic_scholar_api_key() -> str:
    key = (
        os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
        or os.environ.get("S2_API_KEY")
        or ""
    ).strip()
    if key or os.name != "nt":
        return key

    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as env_key:
            value, _ = winreg.QueryValueEx(env_key, "SEMANTIC_SCHOLAR_API_KEY")
        return str(value or "").strip()
    except Exception:
        return ""


def semantic_scholar_available() -> bool:
    return bool(semantic_scholar_api_key()) or not REQUIRE_API_KEY


def normalize_doi(doi: str) -> str:
    doi = (doi or "").strip()
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi, flags=re.I)
    return doi.lower()


def clean_text(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def load_cache() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    if not S2_CACHE_PATH.exists():
        _cache = {}
        return _cache
    try:
        _cache = json.loads(S2_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        _cache = {}
    return _cache


def save_cache() -> None:
    global _cache_dirty
    if not _cache_dirty or _cache is None:
        return
    S2_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    S2_CACHE_PATH.write_text(
        json.dumps(_cache, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _cache_dirty = False


def throttle() -> None:
    global _last_call_at
    elapsed = time.monotonic() - _last_call_at
    if elapsed < 1.15:
        time.sleep(1.15 - elapsed)
    _last_call_at = time.monotonic()


def semantic_scholar_paper_by_doi(doi: str) -> dict:
    global _cache_dirty
    key = semantic_scholar_api_key()
    doi_value = normalize_doi(doi)
    if REQUIRE_API_KEY and not key:
        return {}
    if not doi_value:
        return {}

    cache_key = f"DOI:{doi_value}"
    cache = load_cache()
    cached = cache.get(cache_key)
    if cached and not cached.get("error"):
        return cached
    if cached and cached.get("error"):
        cache.pop(cache_key, None)
        _cache_dirty = True

    identifier = urllib.parse.quote(cache_key, safe=":")
    url = f"{S2_BASE}{identifier}?fields={urllib.parse.quote(S2_FIELDS, safe=',')}"
    headers = {
        "User-Agent": S2_USER_AGENT,
    }
    if key:
        headers["x-api-key"] = key

    data = {}
    for attempt in range(3):
        throttle()
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=40) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                data = {"not_found": True}
                break
            if exc.code in {429, 500, 502, 503, 504} and attempt < 2:
                time.sleep(2.0 + attempt * 3.0)
                continue
            data = {"error": f"HTTP {exc.code}"}
            break
        except Exception as exc:
            data = {"error": type(exc).__name__}
            break

    if data and not data.get("error"):
        cache[cache_key] = data
        _cache_dirty = True
    return data


def candidate_priority(candidate) -> tuple:
    tracks = set(getattr(candidate, "tracks", set()) or set())
    title = (getattr(candidate, "title", "") or "").lower()
    venue = (getattr(candidate, "venue", "") or "").lower()
    source = (getattr(candidate, "abstract_source", "") or "").lower()
    topish = "top" in tracks or any(
        hint in venue
        for hint in [
            "nature",
            "science",
            "nano energy",
            "ieee transactions",
            "device",
            "advanced materials",
            "acs nano",
        ]
    )
    coreish = "core" in tracks or any(
        hint in title
        for hint in [
            "triboelectric-discharge",
            "triboelectric discharge",
            "breakdown discharge",
            "wireless sensing",
            "gas breakdown",
        ]
    )
    transferish = "transfer" in tracks
    manual_evidence = source in {"page-text/manual-evidence", "seed/manual-evidence"}
    track_rank = 0 if topish else 1 if coreish else 2 if transferish else 3
    return (track_rank, 0 if manual_evidence else 1, title)


def semantic_scholar_enrich_candidates(candidates, limit: int | None = None) -> dict:
    if limit is None:
        limit = int(os.environ.get("SEMANTIC_SCHOLAR_ENRICH_LIMIT", DEFAULT_ENRICH_LIMIT))
    result = {
        "available": semantic_scholar_available(),
        "authenticated": bool(semantic_scholar_api_key()),
        "checked": 0,
        "filled_abstracts": 0,
        "limit": limit,
    }
    if not result["available"]:
        return result

    pending = []
    for candidate in candidates:
        doi = normalize_doi(getattr(candidate, "doi", ""))
        if not doi:
            continue
        abstract = clean_text(getattr(candidate, "abstract", ""))
        source = getattr(candidate, "abstract_source", "")
        if not abstract or source in {"page-text/manual-evidence", "seed/manual-evidence"}:
            pending.append(candidate)

    pending.sort(key=candidate_priority)
    if limit >= 0:
        pending = pending[:limit]

    for candidate in pending:
        data = semantic_scholar_paper_by_doi(getattr(candidate, "doi", ""))
        result["checked"] += 1
        if not data or data.get("not_found") or data.get("error"):
            continue

        abstract = clean_text(data.get("abstract") or "")
        if abstract and len(abstract.split()) >= 20:
            candidate.abstract = abstract
            candidate.abstract_source = "Semantic Scholar"
            result["filled_abstracts"] += 1

        if hasattr(candidate, "s2_paper_id"):
            candidate.s2_paper_id = data.get("paperId") or ""
        if hasattr(candidate, "citation_count"):
            candidate.citation_count = data.get("citationCount") or 0
        if hasattr(candidate, "influential_citation_count"):
            candidate.influential_citation_count = data.get("influentialCitationCount") or 0

    save_cache()
    return result
