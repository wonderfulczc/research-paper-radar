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

ELSEVIER_CACHE_PATH = RADAR_ARTIFACT_DIR / "cache" / "elsevier_cache.json"
ELSEVIER_USER_AGENT = "Codex research-paper-radar elsevier-enrichment"
DEFAULT_ENRICH_LIMIT = 80
REQUEST_TIMEOUT_SECONDS = int(os.environ.get("ELSEVIER_TIMEOUT_SECONDS", "30"))
REQUEST_RETRIES = int(os.environ.get("ELSEVIER_RETRIES", "2"))

SCOPUS_ABSTRACT_DOI = "https://api.elsevier.com/content/abstract/doi/"
SCIENCEDIRECT_ARTICLE_DOI = "https://api.elsevier.com/content/article/doi/"

_cache = None
_cache_dirty = False
_last_call_at = 0.0


def _env_or_user_var(names) -> str:
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


def elsevier_api_key() -> str:
    return _env_or_user_var([
        "ELSEVIER_API_KEY",
        "ELSEVIER_APIKEY",
        "ELS_API_KEY",
        "ELS_APIKEY",
        "X_ELS_APIKEY",
        "X_ELS_API_KEY",
    ])


def elsevier_insttoken() -> str:
    return _env_or_user_var([
        "ELSEVIER_INSTTOKEN",
        "ELSEVIER_INST_TOKEN",
        "ELS_INSTTOKEN",
        "ELS_INST_TOKEN",
        "X_ELS_INSTTOKEN",
        "X_ELS_INST_TOKEN",
    ])


def elsevier_available() -> bool:
    return bool(elsevier_api_key())


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
    if not ELSEVIER_CACHE_PATH.exists():
        _cache = {}
        return _cache
    try:
        _cache = json.loads(ELSEVIER_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        _cache = {}
    return _cache


def save_cache() -> None:
    global _cache_dirty
    if not _cache_dirty or _cache is None:
        return
    ELSEVIER_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    ELSEVIER_CACHE_PATH.write_text(
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


def headers() -> dict:
    values = {
        "User-Agent": ELSEVIER_USER_AGENT,
        "Accept": "application/json",
        "X-ELS-APIKey": elsevier_api_key(),
    }
    token = elsevier_insttoken()
    if token:
        values["X-ELS-Insttoken"] = token
    return values


def request_json(url: str, params: dict) -> dict:
    if not elsevier_api_key():
        return {}
    full_url = url + "?" + urllib.parse.urlencode(params)
    last_error = ""
    for attempt in range(REQUEST_RETRIES + 1):
        throttle()
        req = urllib.request.Request(full_url, headers=headers())
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return {"not_found": True}
            if exc.code in {401, 403}:
                return {"error": f"HTTP {exc.code}"}
            last_error = f"HTTP {exc.code}"
            if exc.code in {429, 500, 502, 503, 504} and attempt < REQUEST_RETRIES:
                retry_after = exc.headers.get("Retry-After")
                time.sleep(float(retry_after or (2.0 + attempt * 3.0)))
                continue
            return {"error": last_error}
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < REQUEST_RETRIES:
                time.sleep(1.5 * (attempt + 1))
                continue
            return {"error": last_error}
    return {"error": last_error or "unknown"}


def find_values(node, key: str) -> list:
    values = []
    if isinstance(node, dict):
        for node_key, node_value in node.items():
            if node_key == key:
                values.append(node_value)
            values.extend(find_values(node_value, key))
    elif isinstance(node, list):
        for item in node:
            values.extend(find_values(item, key))
    return values


def first_text(data, keys) -> str:
    for key in keys:
        for value in find_values(data, key):
            text = clean_text(value)
            if text:
                return text
    return ""


def extract_metadata(data: dict, endpoint: str) -> dict:
    if not data or data.get("not_found") or data.get("error"):
        return data or {}
    return {
        "title": first_text(data, ["dc:title", "title"]),
        "abstract": first_text(data, ["dc:description", "prism:teaser", "description"]),
        "venue": first_text(data, ["prism:publicationName", "publicationName"]),
        "date": first_text(data, ["prism:coverDate", "coverDate", "prism:coverDisplayDate"]),
        "doi": normalize_doi(first_text(data, ["prism:doi", "dc:identifier"])),
        "url": first_text(data, ["prism:url"]),
        "citation_count": first_text(data, ["citedby-count"]),
        "endpoint": endpoint,
        "raw": data,
    }


def elsevier_record_by_doi(doi: str) -> dict:
    global _cache_dirty
    doi_value = normalize_doi(doi)
    if not elsevier_api_key() or not doi_value:
        return {}

    cache_key = f"DOI:{doi_value}"
    cache = load_cache()
    if cache_key in cache:
        return cache[cache_key]

    attempts = [
        (
            "Elsevier Scopus Abstract Retrieval",
            SCOPUS_ABSTRACT_DOI + urllib.parse.quote(doi_value, safe=""),
            {"view": "META_ABS"},
        ),
        (
            "Elsevier ScienceDirect Article Retrieval",
            SCIENCEDIRECT_ARTICLE_DOI + urllib.parse.quote(doi_value, safe=""),
            {"view": "META_ABS"},
        ),
        (
            "Elsevier ScienceDirect Article Metadata",
            SCIENCEDIRECT_ARTICLE_DOI + urllib.parse.quote(doi_value, safe=""),
            {"view": "COMPLETE"},
        ),
    ]

    best = {}
    errors = []
    for endpoint, url, params in attempts:
        data = request_json(url, params)
        if data.get("error"):
            errors.append(f"{endpoint} {data['error']}")
            continue
        if data.get("not_found"):
            continue
        record = extract_metadata(data, endpoint)
        if not best and record:
            best = record
        abstract = clean_text(record.get("abstract") if record else "")
        if len(abstract.split()) >= 20:
            cache[cache_key] = record
            _cache_dirty = True
            return record

    if not best and errors:
        best = {"error": "; ".join(errors[:3])}
    cache[cache_key] = best or {"not_found": True}
    _cache_dirty = True
    return cache[cache_key]


def likely_elsevier(candidate) -> bool:
    doi = normalize_doi(getattr(candidate, "doi", ""))
    venue = (getattr(candidate, "venue", "") or "").lower()
    if doi.startswith("10.1016/"):
        return True
    return any(
        hint in venue
        for hint in [
            "nano energy",
            "device",
            "joule",
            "matter",
            "cell reports physical science",
            "sensors and actuators",
            "measurement",
        ]
    )


def elsevier_enrich_candidates(candidates, limit: int | None = None) -> dict:
    if limit is None:
        limit = int(os.environ.get("ELSEVIER_ENRICH_LIMIT", DEFAULT_ENRICH_LIMIT))
    result = {
        "available": elsevier_available(),
        "checked": 0,
        "filled_abstracts": 0,
        "limit": limit,
    }
    if not result["available"]:
        return result

    pending = []
    for candidate in candidates:
        doi = normalize_doi(getattr(candidate, "doi", ""))
        if not doi or not likely_elsevier(candidate):
            continue
        abstract = clean_text(getattr(candidate, "abstract", ""))
        source = getattr(candidate, "abstract_source", "")
        if not abstract or source in {"not retrieved", "seed/manual-evidence", "page-text/manual-evidence"}:
            pending.append(candidate)

    pending.sort(key=lambda c: ((getattr(c, "abstract_source", "") != "not retrieved"), getattr(c, "title", "")))
    if limit >= 0:
        pending = pending[:limit]

    for candidate in pending:
        data = elsevier_record_by_doi(getattr(candidate, "doi", ""))
        result["checked"] += 1
        if not data or data.get("not_found") or data.get("error"):
            continue

        abstract = clean_text(data.get("abstract") or "")
        if abstract and len(abstract.split()) >= 20:
            candidate.abstract = abstract
            candidate.abstract_source = data.get("endpoint") or "Elsevier API"
            result["filled_abstracts"] += 1

        if data.get("title") and not getattr(candidate, "title", ""):
            candidate.title = data["title"]
        if data.get("venue") and not getattr(candidate, "venue", ""):
            candidate.venue = data["venue"]
        if data.get("date") and not getattr(candidate, "date", ""):
            candidate.date = data["date"]
        if data.get("citation_count") and hasattr(candidate, "citation_count"):
            try:
                candidate.citation_count = int(data["citation_count"])
            except ValueError:
                pass

    save_cache()
    return result
