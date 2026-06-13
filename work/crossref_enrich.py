import html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from radar_state import RADAR_ARTIFACT_DIR

CROSSREF_BASE = "https://api.crossref.org/works/"
CROSSREF_CACHE_PATH = RADAR_ARTIFACT_DIR / "cache" / "crossref_cache.json"
CROSSREF_USER_AGENT = "Codex research-paper-radar crossref-enrichment"
DEFAULT_ENRICH_LIMIT = 120
REQUEST_TIMEOUT_SECONDS = int(os.environ.get("CROSSREF_TIMEOUT_SECONDS", "35"))
REQUEST_RETRIES = int(os.environ.get("CROSSREF_RETRIES", "2"))
DISABLED = os.environ.get("CROSSREF_DISABLED", "").strip().lower() in {"1", "true", "yes"}

_cache = None
_cache_dirty = False
_last_call_at = 0.0


def crossref_available() -> bool:
    return not DISABLED


def normalize_doi(doi: str) -> str:
    doi = (doi or "").strip()
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi, flags=re.I)
    return doi.lower()


def clean_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return clean_text(" ".join(clean_text(item) for item in value))
    if isinstance(value, dict):
        return clean_text(" ".join(clean_text(item) for item in value.values()))
    value = html.unescape(str(value))
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def load_cache() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    if not CROSSREF_CACHE_PATH.exists():
        _cache = {}
        return _cache
    try:
        _cache = json.loads(CROSSREF_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        _cache = {}
    return _cache


def save_cache() -> None:
    global _cache_dirty
    if not _cache_dirty or _cache is None:
        return
    CROSSREF_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CROSSREF_CACHE_PATH.write_text(
        json.dumps(_cache, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _cache_dirty = False


def throttle() -> None:
    global _last_call_at
    elapsed = time.monotonic() - _last_call_at
    if elapsed < 0.8:
        time.sleep(0.8 - elapsed)
    _last_call_at = time.monotonic()


def request_headers() -> dict:
    user_agent = CROSSREF_USER_AGENT
    mailto = (os.environ.get("CROSSREF_MAILTO") or "").strip()
    if mailto:
        user_agent = f"{user_agent} (mailto:{mailto})"
    return {"User-Agent": user_agent}


def first_item(value) -> str:
    if isinstance(value, list) and value:
        return clean_text(value[0])
    return clean_text(value)


def date_from_parts(value) -> str:
    parts = value.get("date-parts") if isinstance(value, dict) else None
    if not parts or not isinstance(parts, list) or not parts[0]:
        return ""
    nums = [str(item).zfill(2) for item in parts[0]]
    if len(nums) >= 3:
        return f"{nums[0]}-{nums[1]}-{nums[2]}"
    if len(nums) == 2:
        return f"{nums[0]}-{nums[1]}"
    return nums[0]


def metadata_from_message(message: dict) -> dict:
    if not message:
        return {}
    published = (
        date_from_parts(message.get("published-online") or {})
        or date_from_parts(message.get("published-print") or {})
        or date_from_parts(message.get("published") or {})
        or date_from_parts(message.get("issued") or {})
    )
    return {
        "title": first_item(message.get("title")),
        "abstract": clean_text(message.get("abstract")),
        "venue": first_item(message.get("container-title")),
        "date": published,
        "doi": normalize_doi(message.get("DOI") or message.get("doi") or ""),
        "url": clean_text(message.get("URL") or message.get("resource", {}).get("primary", {}).get("URL")),
        "citation_count": message.get("is-referenced-by-count") or 0,
    }


def crossref_work_by_doi(doi: str) -> dict:
    global _cache_dirty
    doi_value = normalize_doi(doi)
    if DISABLED or not doi_value:
        return {}

    cache_key = f"DOI:{doi_value}"
    cache = load_cache()
    cached = cache.get(cache_key)
    if cached and not cached.get("error"):
        return cached
    if cached and cached.get("error"):
        cache.pop(cache_key, None)
        _cache_dirty = True

    url = CROSSREF_BASE + urllib.parse.quote(doi_value, safe="")
    data = {}
    for attempt in range(REQUEST_RETRIES + 1):
        throttle()
        req = urllib.request.Request(url, headers=request_headers())
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            data = metadata_from_message(payload.get("message") or {})
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                data = {"not_found": True}
                break
            if exc.code in {429, 500, 502, 503, 504} and attempt < REQUEST_RETRIES:
                retry_after = exc.headers.get("Retry-After")
                time.sleep(float(retry_after or (2.0 + attempt * 3.0)))
                continue
            data = {"error": f"HTTP {exc.code}"}
            break
        except Exception as exc:
            if attempt < REQUEST_RETRIES:
                time.sleep(1.5 * (attempt + 1))
                continue
            data = {"error": type(exc).__name__}
            break

    if data and not data.get("error"):
        cache[cache_key] = data
        _cache_dirty = True
    return data


def crossref_enrich_candidates(candidates, limit: int | None = None) -> dict:
    if limit is None:
        limit = int(os.environ.get("CROSSREF_ENRICH_LIMIT", DEFAULT_ENRICH_LIMIT))
    result = {
        "available": crossref_available(),
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
        if not abstract or source in {"not retrieved", "seed/manual-evidence", "page-text/manual-evidence"}:
            pending.append(candidate)

    pending.sort(key=lambda c: ((getattr(c, "abstract_source", "") not in {"page-text/manual-evidence", "seed/manual-evidence"}), getattr(c, "title", "")))
    if limit >= 0:
        pending = pending[:limit]

    for candidate in pending:
        data = crossref_work_by_doi(getattr(candidate, "doi", ""))
        result["checked"] += 1
        if not data or data.get("not_found") or data.get("error"):
            continue

        abstract = clean_text(data.get("abstract") or "")
        if abstract and len(abstract.split()) >= 20:
            candidate.abstract = abstract
            candidate.abstract_source = "Crossref"
            result["filled_abstracts"] += 1

        if data.get("title") and not getattr(candidate, "title", ""):
            candidate.title = data["title"]
        if data.get("venue") and not getattr(candidate, "venue", ""):
            candidate.venue = data["venue"]
        if data.get("date") and not getattr(candidate, "date", ""):
            candidate.date = data["date"]
        if data.get("citation_count") and hasattr(candidate, "citation_count") and not getattr(candidate, "citation_count", 0):
            try:
                candidate.citation_count = int(data["citation_count"])
            except (TypeError, ValueError):
                pass

    save_cache()
    return result
