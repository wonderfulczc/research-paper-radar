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

SN_BASE = "https://api.springernature.com/"
SN_ENDPOINTS = ["meta/v2/json", "metadata/json"]
SN_CACHE_PATH = RADAR_ARTIFACT_DIR / "cache" / "springer_nature_cache.json"
SN_USER_AGENT = "Codex research-paper-radar springer-nature-enrichment"
DEFAULT_ENRICH_LIMIT = 80
REQUEST_TIMEOUT_SECONDS = int(os.environ.get("SPRINGER_NATURE_TIMEOUT_SECONDS", "30"))
REQUEST_RETRIES = int(os.environ.get("SPRINGER_NATURE_RETRIES", "2"))

_cache = None
_cache_dirty = False
_last_call_at = 0.0


def springer_nature_api_key() -> str:
    names = [
        "SPRINGER_NATURE_API_KEY",
        "SPRINGERNATURE_API_KEY",
        "SPRINGER_API_KEY",
    ]
    for name in names:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value

    if os.name != "nt":
        return ""

    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as env_key:
            for name in names:
                try:
                    value, _ = winreg.QueryValueEx(env_key, name)
                except FileNotFoundError:
                    continue
                value = str(value or "").strip()
                if value:
                    return value
    except Exception:
        return ""
    return ""


def springer_nature_available() -> bool:
    return bool(springer_nature_api_key())


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
    if not SN_CACHE_PATH.exists():
        _cache = {}
        return _cache
    try:
        _cache = json.loads(SN_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        _cache = {}
    return _cache


def save_cache() -> None:
    global _cache_dirty
    if not _cache_dirty or _cache is None:
        return
    SN_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SN_CACHE_PATH.write_text(
        json.dumps(_cache, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _cache_dirty = False


def throttle() -> None:
    global _last_call_at
    elapsed = time.monotonic() - _last_call_at
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)
    _last_call_at = time.monotonic()


def request_json(endpoint: str, q: str) -> dict:
    key = springer_nature_api_key()
    params = {
        "q": q,
        "p": "5",
        "s": "1",
        "api_key": key,
    }
    url = SN_BASE + endpoint + "?" + urllib.parse.urlencode(params)
    headers = {"User-Agent": SN_USER_AGENT}
    last_error = ""

    for attempt in range(REQUEST_RETRIES + 1):
        throttle()
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                return {"records": [], "error": f"HTTP {exc.code}"}
            if exc.code == 404:
                return {"records": [], "not_found": True}
            last_error = f"HTTP {exc.code}"
            if exc.code in {429, 500, 502, 503, 504} and attempt < REQUEST_RETRIES:
                retry_after = exc.headers.get("Retry-After")
                time.sleep(float(retry_after or (2.0 + attempt * 3.0)))
                continue
            return {"records": [], "error": last_error}
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < REQUEST_RETRIES:
                time.sleep(1.5 * (attempt + 1))
                continue
            return {"records": [], "error": last_error}

    return {"records": [], "error": last_error or "unknown"}


def record_doi(record: dict) -> str:
    for key in ["doi", "DOI", "prism:doi"]:
        value = normalize_doi(record.get(key, ""))
        if value:
            return value

    identifiers = record.get("identifier") or record.get("identifiers") or []
    if isinstance(identifiers, str):
        identifiers = [identifiers]
    for item in identifiers:
        value = clean_text(item)
        match = re.search(r"10\.\d{4,9}/\S+", value, flags=re.I)
        if match:
            return normalize_doi(match.group(0).rstrip(".,;"))
    return ""


def find_matching_record(records: list, doi: str) -> dict:
    doi_value = normalize_doi(doi)
    if not doi_value:
        return records[0] if records else {}
    for record in records:
        if record_doi(record) == doi_value:
            return record
    return records[0] if records else {}


def abstract_from_record(record: dict) -> str:
    for key in [
        "abstract",
        "description",
        "dc:description",
        "summary",
        "teaser",
        "prism:teaser",
    ]:
        value = clean_text(record.get(key))
        if len(value.split()) >= 20:
            return value
    return ""


def metadata_from_record(record: dict) -> dict:
    if not record:
        return {}
    return {
        "title": clean_text(record.get("title") or record.get("dc:title")),
        "abstract": abstract_from_record(record),
        "venue": clean_text(
            record.get("publicationName")
            or record.get("journal")
            or record.get("prism:publicationName")
        ),
        "date": clean_text(
            record.get("publicationDate")
            or record.get("coverDate")
            or record.get("onlineDate")
            or record.get("date")
        ),
        "doi": record_doi(record),
        "url": clean_text(record.get("url") or record.get("webUrl") or record.get("landingPage")),
        "raw": record,
    }


def springer_nature_record_by_doi(doi: str) -> dict:
    global _cache_dirty
    key = springer_nature_api_key()
    doi_value = normalize_doi(doi)
    if not key or not doi_value:
        return {}

    cache_key = f"DOI:{doi_value}"
    cache = load_cache()
    if cache_key in cache:
        return cache[cache_key]

    query_variants = [
        f'doi:"{doi_value}"',
        f"doi:{doi_value}",
    ]
    best = {}
    errors = []
    for endpoint in SN_ENDPOINTS:
        for query in query_variants:
            data = request_json(endpoint, query)
            if data.get("error"):
                errors.append(f"{endpoint} {data['error']}")
            records = data.get("records") or []
            if records:
                record = find_matching_record(records, doi_value)
                best = metadata_from_record(record)
                best["endpoint"] = endpoint
                if best.get("abstract"):
                    cache[cache_key] = best
                    _cache_dirty = True
                    return best
                if not cache.get(cache_key):
                    cache[cache_key] = best
                    _cache_dirty = True

    if not best and errors:
        best = {"error": "; ".join(errors[:3])}
    cache[cache_key] = best or {"not_found": True}
    _cache_dirty = True
    return cache[cache_key]


def likely_springer_nature(candidate) -> bool:
    doi = normalize_doi(getattr(candidate, "doi", ""))
    venue = (getattr(candidate, "venue", "") or "").lower()
    title = (getattr(candidate, "title", "") or "").lower()
    if doi.startswith("10.1038/") or doi.startswith("10.1186/") or doi.startswith("10.1007/"):
        return True
    return any(
        hint in venue or hint in title
        for hint in [
            "nature",
            "communications ",
            "scientific reports",
            "springer",
            "npj",
            "microsystems & nanoengineering",
        ]
    )


def springer_nature_enrich_candidates(candidates, limit: int | None = None) -> dict:
    if limit is None:
        limit = int(os.environ.get("SPRINGER_NATURE_ENRICH_LIMIT", DEFAULT_ENRICH_LIMIT))
    result = {
        "available": springer_nature_available(),
        "checked": 0,
        "filled_abstracts": 0,
        "limit": limit,
    }
    if not result["available"]:
        return result

    pending = []
    for candidate in candidates:
        doi = normalize_doi(getattr(candidate, "doi", ""))
        if not doi or not likely_springer_nature(candidate):
            continue
        abstract = clean_text(getattr(candidate, "abstract", ""))
        source = getattr(candidate, "abstract_source", "")
        if not abstract or source in {"page-text/manual-evidence", "not retrieved"}:
            pending.append(candidate)

    pending.sort(key=lambda c: ((getattr(c, "abstract_source", "") != "page-text/manual-evidence"), getattr(c, "title", "")))
    if limit >= 0:
        pending = pending[:limit]

    for candidate in pending:
        data = springer_nature_record_by_doi(getattr(candidate, "doi", ""))
        result["checked"] += 1
        if not data or data.get("not_found") or data.get("error"):
            continue

        abstract = clean_text(data.get("abstract") or "")
        if abstract and len(abstract.split()) >= 20:
            candidate.abstract = abstract
            candidate.abstract_source = "Springer Nature Meta API"
            result["filled_abstracts"] += 1

        if data.get("title") and not getattr(candidate, "title", ""):
            candidate.title = data["title"]
        if data.get("venue") and not getattr(candidate, "venue", ""):
            candidate.venue = data["venue"]
        if data.get("date") and not getattr(candidate, "date", ""):
            candidate.date = data["date"]

    save_cache()
    return result
