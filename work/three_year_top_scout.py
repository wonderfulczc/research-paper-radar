import csv
import html
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from semantic_scholar_enrich import semantic_scholar_enrich_candidates
from springer_nature_enrich import springer_nature_enrich_candidates
from elsevier_enrich import elsevier_enrich_candidates
from mechanism_terms import MECHANISM_TERMS
from radar_state import RADAR_ARTIFACT_DIR, SEEN_INDEX_PATH, load_seen_index, split_unseen, update_seen_index
from priority_venues import (
    A_TIER_VENUES,
    B_TIER_DIRECT_ONLY_VENUES,
    IEEE_CORE_VENUES,
    S_TIER_VENUES,
    is_ac_exception_venue as priority_ac_exception_venue,
    venue_priority,
    venue_priority_label,
    venue_priority_rank,
)


TODAY = date.today()
START = date(TODAY.year - 3, TODAY.month, TODAY.day)
BASE = "https://api.openalex.org/works"
REPORT_ID = f"RADAR-3YR-SCOUT-{TODAY.isoformat()}"
OPENALEX_TIMEOUT_SECONDS = int(os.environ.get("OPENALEX_TIMEOUT_SECONDS", "25"))
OPENALEX_RETRIES = int(os.environ.get("OPENALEX_RETRIES", "2"))
OPENALEX_PER_PAGE = int(os.environ.get("OPENALEX_PER_PAGE", "50"))
OPENALEX_DISABLED = os.environ.get("OPENALEX_DISABLED", "").strip().lower() in {"1", "true", "yes"}
OPENALEX_CACHE_ONLY = os.environ.get("OPENALEX_CACHE_ONLY", "").strip().lower() in {"1", "true", "yes"}
OPENALEX_CACHE_TTL_DAYS = int(os.environ.get("OPENALEX_CACHE_TTL_DAYS", "14"))
OPENALEX_MAX_TIMEOUTS = int(os.environ.get("OPENALEX_MAX_TIMEOUTS", "6"))
OPENALEX_CACHE_PATH = RADAR_ARTIFACT_DIR / "cache" / "openalex_query_cache.json"
CAS_PARTITION_TABLE = Path(os.environ.get("CAS_PARTITION_TABLE", "work/journal_quartiles.csv"))
CAS_PARTITION_MODE = os.environ.get("CAS_PARTITION_MODE", "off").strip().lower()
if CAS_PARTITION_MODE not in {"strict", "warn", "off"}:
    CAS_PARTITION_MODE = "strict"
CAS_ALLOWED_ZONES = {"1", "2"}

_openalex_cache = None
_openalex_cache_dirty = False
_journal_quality_table = None

MANUAL_EVIDENCE = {
    "10.1038/s44460-026-00033-3": {
        "abstract_hint": "源页面摘要要点：自供能电子贴片通过摩擦诱导电磁波工作，面向可穿戴传感和无线通信。",
        "profile": {
            "self_powered": True,
            "tribo_or_friction": True,
            "discharge_or_em_generation": True,
            "wireless_or_communication": True,
            "sensing_or_system": True,
        },
    },
    "10.1126/sciadv.adt0318": {
        "abstract_hint": "用户核实摘要要点：摘要包含 gas breakdown discharge、self-powered 与 triboelectric effect，面向可穿戴触觉/人机接口系统。",
        "profile": {
            "self_powered": True,
            "tribo_or_friction": True,
            "discharge_or_em_generation": True,
            "wireless_or_communication": False,
            "sensing_or_system": True,
        },
    },
    "10.1038/s41378-025-00987-3": {
        "abstract_hint": "Springer Nature Meta 摘要要点：battery-free wireless sensor 通过 Maxwell's displacement current 和接触分离 TENG 产生高频电磁波，实现加密信号传输。",
        "profile": {
            "self_powered": True,
            "tribo_or_friction": True,
            "discharge_or_em_generation": True,
            "wireless_or_communication": True,
            "sensing_or_system": True,
        },
    },
}

SEED_PAPERS = [
    {
        "title": "Self-Powered Wireless Sensing System Based on Triboelectric-Discharge Effect",
        "date": "2024-04-29",
        "doi": "https://doi.org/10.1109/ted.2024.3392182",
        "venue": "IEEE Transactions on Electron Devices",
        "track": "seed",
        "query": "seed: known anchor",
    },
    {
        "title": "Chip-less, self-powered electronic patch for wireless sensing and communication",
        "date": "2026-02-27",
        "doi": "https://doi.org/10.1038/s44460-026-00033-3",
        "venue": "Nature Sensors",
        "track": "seed",
        "query": "seed: user-confirmed Nature Sensors DOI",
    },
    {
        "title": "Self-powered electrotactile textile haptic glove for enhanced human-machine interface",
        "date": "2025-03-21",
        "doi": "https://doi.org/10.1126/sciadv.adt0318",
        "venue": "Science Advances",
        "track": "seed",
        "query": "seed: user-confirmed Science Advances DOI",
    },
    {
        "title": "A battery-free wireless sensor for encrypted signal transmission via Maxwell’s displacement current",
        "date": "2025-06-30",
        "doi": "https://doi.org/10.1038/s41378-025-00987-3",
        "venue": "Microsystems & Nanoengineering",
        "track": "seed",
        "query": "seed: Springer Nature strong venue",
    },
    {
        "title": "Self-powered wireless rapid oil quality sensing system based on triboelectric-discharge effect",
        "date": "2025-09-04",
        "doi": "https://doi.org/10.1016/j.nanoen.2025.111439",
        "venue": "Nano Energy",
        "track": "seed",
        "query": "seed: Nano Energy known candidate",
    },
    {
        "title": "Breakdown discharge effect enabled self-powered multi-mechanism wireless sensing scheme",
        "date": "2025-01-13",
        "doi": "https://doi.org/10.1016/j.nanoen.2025.110671",
        "venue": "Nano Energy",
        "track": "seed",
        "query": "seed: Nano Energy known candidate",
    },
    {
        "title": "A Compact‐Sized Fully Self‐Powered Wireless Flowmeter Based on Triboelectric Discharge",
        "date": "2024-04-18",
        "doi": "https://doi.org/10.1002/smtd.202301670",
        "venue": "Small Methods",
        "track": "seed",
        "query": "seed: known strong candidate",
    },
    {
        "title": "Triboelectric discharge based self-powered wireless sensing system for smart home application",
        "date": "2025-10-29",
        "doi": "https://doi.org/10.20517/ss.2025.72",
        "venue": "Soft Science",
        "track": "seed",
        "query": "seed: known direct candidate",
    },
    {
        "title": "A self-powered, process-oriented wireless sensor with high discharge signal density",
        "date": "2024-07-02",
        "doi": "https://doi.org/10.1016/j.device.2024.100437",
        "venue": "Device",
        "track": "seed",
        "query": "seed: Device known candidate",
        "abstract_hint": "已知摘要要点：基于 triboelectric effect 产生连续 discharge breakdown signal flow，并通过感应线圈实现高密度无线传输，服务长距离自供能无线传感。",
    },
]

QUERIES = [
    ("core", '"Self-Powered Wireless Sensing System Based on Triboelectric-Discharge Effect"'),
    ("core", '"triboelectric-discharge" wireless sensing'),
    ("core", '"triboelectric discharge" wireless sensor'),
    ("core", "breakdown discharge wireless sensing"),
    ("core", "spark discharge electromagnetic signal sensor"),
    ("core", "microgap discharge wireless sensor"),
    ("core", "corona discharge electromagnetic sensing"),
    ("core", "discharge electromagnetic pulse wireless sensor"),
    ("core", "RLC frequency modulation wireless sensor discharge"),
    ("transfer", "chip-less self-powered electronic patch"),
    ("transfer", "self-powered electronic patch wireless sensing"),
    ("transfer", "self-powered electrotactile textile haptic glove"),
    ("transfer", "electrotactile textile haptic human-machine interface"),
    ("transfer", "self-powered textile haptic wearable sensor"),
    ("mechanism", "microgap gas breakdown electromagnetic emission sensor"),
    ("mechanism", "spark discharge electromagnetic emission sensing"),
    ("mechanism", "corona discharge RF emission sensor"),
    ("mechanism", "partial discharge UHF wireless sensor"),
    ("top", "Nature battery-free wireless sensor"),
    ("top", "Nature Sensors self-powered sensor"),
    ("top", "Nature Sensors electronic patch"),
    ("top", "Nature Portfolio passive wireless sensor"),
    ("top", "Nature Electronics wireless sensor"),
    ("top", "Nature Communications wireless sensor"),
    ("top", "Science Advances wireless sensor battery-free"),
    ("top", "Science wireless passive sensor"),
    ("top", "IEEE Transactions partial discharge UHF sensor"),
    ("top", "IEEE Transactions electron devices discharge sensor"),
    ("top", "IEEE Transactions wireless passive sensor"),
    ("top", "IEEE Sensors Journal partial discharge UHF sensor"),
]

TOP_VENUE_HINTS = [
    *S_TIER_VENUES,
    *A_TIER_VENUES,
    *IEEE_CORE_VENUES,
]


@dataclass
class Candidate:
    title: str
    date: str
    doi: str
    venue: str
    landing: str
    abstract: str
    abstract_source: str = "not retrieved"
    queries: set = field(default_factory=set)
    tracks: set = field(default_factory=set)
    s2_paper_id: str = ""
    citation_count: int = 0
    influential_citation_count: int = 0
    relevance: int = 0
    novelty: int = 0
    level: str = "exclude"
    reason: str = ""
    venue_class: str = "ordinary/unknown"
    venue_priority: str = "ordinary"
    mechanism_pair: str = ""
    mechanism_evidence: str = ""
    cas_zone: str = ""
    quality_source: str = ""
    quality_gate: str = "unchecked"


def request_json(url: str, label: str = "OpenAlex") -> dict:
    headers = {"User-Agent": "Codex research-paper-radar 3yr scout"}
    last_error = ""
    for attempt in range(OPENALEX_RETRIES + 1):
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=OPENALEX_TIMEOUT_SECONDS) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (TimeoutError, urllib.error.URLError, OSError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < OPENALEX_RETRIES:
                print(
                    f"WARNING: OpenAlex query timeout/error, retry {attempt + 1}/{OPENALEX_RETRIES}: {label}",
                    file=sys.stderr,
                )
                time.sleep(1.5 * (attempt + 1))
                continue
            print(
                f"WARNING: OpenAlex query skipped after retries: {label} ({last_error})",
                file=sys.stderr,
            )
            return {"meta": {"count": 0}, "results": [], "error": last_error}


def openalex_cache_key(query: str, per_page: int) -> str:
    raw = f"{START.isoformat()}|{TODAY.isoformat()}|{per_page}|{query}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_openalex_cache() -> dict:
    global _openalex_cache
    if _openalex_cache is not None:
        return _openalex_cache
    if not OPENALEX_CACHE_PATH.exists():
        _openalex_cache = {}
        return _openalex_cache
    try:
        _openalex_cache = json.loads(OPENALEX_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        _openalex_cache = {}
    return _openalex_cache


def save_openalex_cache() -> None:
    global _openalex_cache_dirty
    if not _openalex_cache_dirty or _openalex_cache is None:
        return
    OPENALEX_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    OPENALEX_CACHE_PATH.write_text(
        json.dumps(_openalex_cache, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _openalex_cache_dirty = False


def get_cached_openalex(query: str, per_page: int) -> dict:
    cache = load_openalex_cache()
    entry = cache.get(openalex_cache_key(query, per_page))
    if not entry:
        return {}
    max_age = OPENALEX_CACHE_TTL_DAYS * 24 * 3600
    age = time.time() - float(entry.get("saved_at", 0))
    if max_age >= 0 and age > max_age:
        return {}
    data = dict(entry.get("data") or {})
    data["_cache_hit"] = True
    return data


def put_cached_openalex(query: str, per_page: int, data: dict) -> None:
    global _openalex_cache_dirty
    if not data or data.get("error"):
        return
    cache = load_openalex_cache()
    cache[openalex_cache_key(query, per_page)] = {
        "query": query,
        "per_page": per_page,
        "window": [START.isoformat(), TODAY.isoformat()],
        "saved_at": time.time(),
        "data": data,
    }
    _openalex_cache_dirty = True


def openalex_query(query: str, per_page: int | None = None) -> dict:
    if per_page is None:
        per_page = OPENALEX_PER_PAGE
    cached = get_cached_openalex(query, per_page)
    if OPENALEX_CACHE_ONLY:
        if cached:
            print(f"OpenAlex cache hit: {query}", flush=True)
            return cached
        print(f"WARNING: OpenAlex cache miss while OPENALEX_CACHE_ONLY=1: {query}", file=sys.stderr)
        return {"meta": {"count": 0}, "results": [], "error": "cache miss"}
    params = {
        "search": query,
        "filter": f"from_publication_date:{START.isoformat()},to_publication_date:{TODAY.isoformat()}",
        "per_page": str(per_page),
        "sort": "relevance_score:desc",
    }
    data = request_json(BASE + "?" + urllib.parse.urlencode(params), label=query)
    if data.get("error") and cached:
        print(f"OpenAlex cache fallback after timeout/error: {query}", flush=True)
        return cached
    put_cached_openalex(query, per_page, data)
    return data


def reconstruct_abstract(index):
    if not index:
        return ""
    positions = []
    for word, idxs in index.items():
        for idx in idxs:
            positions.append((idx, word))
    positions.sort()
    return " ".join(word for _, word in positions)


def clean_html_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def fetch_visible_abstract(url: str) -> str:
    if not url:
        return ""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        raw = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
    except Exception:
        return ""

    for pattern in [
        r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']+)["\']',
        r'<meta\s+name=["\']dc.description["\']\s+content=["\']([^"\']+)["\']',
        r'<meta\s+property=["\']og:description["\']\s+content=["\']([^"\']+)["\']',
    ]:
        match = re.search(pattern, raw, re.I)
        if match:
            text = clean_html_text(match.group(1))
            if len(text.split()) >= 30:
                return text

    abstract_match = re.search(
        r"<h2[^>]*>\s*Abstract\s*</h2>(.*?)(?:<h2|<section|<div class=\"c-article-access-container)",
        raw,
        re.I | re.S,
    )
    if abstract_match:
        text = clean_html_text(abstract_match.group(1))
        if len(text.split()) >= 30:
            return text
    return ""


def source_name(work):
    loc = work.get("primary_location") or {}
    source = loc.get("source") or {}
    return source.get("display_name") or loc.get("raw_source_name") or ""


def first_landing(work):
    loc = work.get("primary_location") or {}
    return loc.get("landing_page_url") or work.get("doi") or work.get("id") or ""


def normalized_key(work):
    title = re.sub(r"\W+", " ", work.get("display_name") or work.get("title") or "").strip().lower()
    doi = (work.get("doi") or "").lower()
    return doi or title


def normalized_candidate_key(candidate: Candidate) -> str:
    return normalized_key({"display_name": candidate.title, "doi": candidate.doi})


def add_seed_papers(items: dict) -> int:
    added = 0
    for seed in SEED_PAPERS:
        key = normalized_key({"display_name": seed["title"], "doi": seed["doi"]})
        if not key:
            continue
        doi_value = seed["doi"].lower().replace("https://doi.org/", "")
        abstract = ""
        abstract_source = "not retrieved"
        if doi_value in MANUAL_EVIDENCE:
            abstract = MANUAL_EVIDENCE[doi_value]["abstract_hint"]
            abstract_source = "page-text/manual-evidence"
        elif seed.get("abstract_hint"):
            abstract = seed["abstract_hint"]
            abstract_source = "seed/manual-evidence"
        if key in items:
            item = items[key]
            item.queries.add(seed["query"])
            item.tracks.add(seed["track"])
            if not item.title:
                item.title = seed["title"]
            if not item.date:
                item.date = seed["date"]
            if not item.venue:
                item.venue = seed["venue"]
            if not item.abstract and abstract:
                item.abstract = abstract
                item.abstract_source = abstract_source
            continue
        item = Candidate(
            title=seed["title"],
            date=seed["date"],
            doi=seed["doi"],
            venue=seed["venue"],
            landing=seed["doi"],
            abstract=abstract,
            abstract_source=abstract_source,
        )
        item.queries.add(seed["query"])
        item.tracks.add(seed["track"])
        items[key] = item
        added += 1
    return added


def has_any(text: str, terms) -> bool:
    return any(term in text for term in terms)


def normalize_venue_name(value: str) -> str:
    value = html.unescape(value or "").lower()
    value = value.replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_cas_zone(value: str) -> str:
    value = str(value or "").strip().lower()
    value = value.replace("中科院", "").replace("大类", "").replace("小类", "").strip()
    if value in {"1", "一区", "1区", "zone 1", "zone1"}:
        return "1"
    if value in {"2", "二区", "2区", "zone 2", "zone2"}:
        return "2"
    return ""


def load_journal_quality_table() -> dict:
    global _journal_quality_table
    if _journal_quality_table is not None:
        return _journal_quality_table
    table = {}
    if not CAS_PARTITION_TABLE.exists():
        _journal_quality_table = table
        return table
    with CAS_PARTITION_TABLE.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            names = [
                row.get("title") or row.get("venue") or row.get("journal") or "",
                row.get("aliases") or row.get("alias") or "",
            ]
            for name_group in names:
                for name in re.split(r"[;|]", name_group):
                    normalized = normalize_venue_name(name)
                    if normalized:
                        table[normalized] = row
    _journal_quality_table = table
    return table


def format_quality_source(row: dict) -> str:
    parts = []
    for key in ["source", "year", "category"]:
        value = (row.get(key) or "").strip()
        if value:
            parts.append(value)
    return " / ".join(parts)


def apply_quality_gate(candidate: Candidate) -> None:
    candidate.quality_gate = "off" if CAS_PARTITION_MODE == "off" else "unknown"
    candidate.cas_zone = ""
    candidate.quality_source = ""
    if CAS_PARTITION_MODE == "off":
        return
    table = load_journal_quality_table()
    row = table.get(normalize_venue_name(candidate.venue))
    if not row:
        return
    zone = normalize_cas_zone(
        row.get("cas_zone")
        or row.get("cas_partition")
        or row.get("cas")
        or row.get("zone")
    )
    candidate.cas_zone = zone or (
        row.get("cas_zone")
        or row.get("cas_partition")
        or row.get("cas")
        or row.get("zone")
        or ""
    ).strip()
    candidate.quality_source = format_quality_source(row)
    candidate.quality_gate = "pass" if zone in CAS_ALLOWED_ZONES else "fail"


def quality_allows(candidate: Candidate) -> bool:
    if CAS_PARTITION_MODE == "off":
        return True
    if candidate.quality_gate == "pass":
        return True
    return CAS_PARTITION_MODE == "warn"


def quality_text(candidate: Candidate) -> str:
    if CAS_PARTITION_MODE == "off":
        return "未启用"
    if candidate.quality_gate == "pass":
        text = f"中科院{candidate.cas_zone}区"
        if candidate.quality_source:
            text += f"（{candidate.quality_source}）"
        return text
    if candidate.quality_gate == "fail":
        return f"未通过：{candidate.cas_zone or '非1/2区'}"
    return "中科院分区未匹配"


def mechanism_categories(profile: dict) -> list[str]:
    categories = []
    if profile["self_powered"] or profile["tribo_or_friction"]:
        categories.append("A")
    if profile["discharge_or_em_generation"]:
        categories.append("B")
    if profile["wireless_or_communication"] or profile["sensing_or_system"]:
        categories.append("C")
    return categories


def mechanism_pair_label(profile: dict) -> str:
    categories = mechanism_categories(profile)
    if not categories:
        return "none"
    return "+".join(categories)


def mechanism_evidence_text(profile: dict) -> str:
    parts = []
    if profile["self_powered"] or profile["tribo_or_friction"]:
        parts.append("A=自供能/摩擦/triboelectric激发")
    if profile["discharge_or_em_generation"]:
        parts.append("B=击穿放电/电磁波生成")
    if profile["wireless_or_communication"] or profile["sensing_or_system"]:
        parts.append("C=无线通信/传感/可穿戴系统功能")
    return "；".join(parts) if parts else "未形成机制链"


def is_ac_exception_venue(venue: str) -> bool:
    return priority_ac_exception_venue(venue)


def mechanism_profile(candidate: Candidate) -> dict:
    text = " ".join([candidate.title, candidate.abstract, candidate.venue])
    low = text.lower()
    profile = {
        "self_powered": has_any(
            low,
            MECHANISM_TERMS["self_powered"],
        ),
        "tribo_or_friction": has_any(
            low,
            MECHANISM_TERMS["tribo_or_friction"],
        ),
        "discharge_or_em_generation": has_any(
            low,
            MECHANISM_TERMS["discharge_or_em_generation"],
        ),
        "wireless_or_communication": has_any(
            low,
            MECHANISM_TERMS["wireless_or_communication"],
        ),
        "sensing_or_system": has_any(
            low,
            MECHANISM_TERMS["sensing_or_system"],
        ),
    }
    doi_key = (candidate.doi or "").lower().replace("https://doi.org/", "")
    manual = MANUAL_EVIDENCE.get(doi_key)
    if manual:
        for key, value in manual["profile"].items():
            profile[key] = profile[key] or value
    return profile


def venue_class(venue: str) -> str:
    return venue_priority_label(venue_priority(venue))


def is_mdpi(candidate: Candidate) -> bool:
    doi = (candidate.doi or "").lower()
    venue = (candidate.venue or "").lower()
    return "10.3390/" in doi or venue in {
        "sensors",
        "micromachines",
        "energies",
        "electronics",
        "materials",
        "nanomaterials",
        "applied sciences",
        "photonics",
        "journal of composites science",
    }


def classify(candidate: Candidate):
    text = " ".join([candidate.title, candidate.abstract, candidate.venue])
    low = text.lower()
    candidate.venue_priority = venue_priority(candidate.venue)
    candidate.venue_class = venue_class(candidate.venue)
    profile = mechanism_profile(candidate)
    candidate.mechanism_pair = mechanism_pair_label(profile)
    candidate.mechanism_evidence = mechanism_evidence_text(profile)

    exact_anchor = "self-powered wireless sensing system based on triboelectric-discharge effect" in low
    tribo_discharge = "triboelectric-discharge" in low or "triboelectric discharge" in low
    breakdown_discharge_effect = "breakdown discharge effect" in low
    discharge = has_any(low, ["breakdown", "spark", "corona", "microgap", "microplasma", "partial discharge", "discharge"])
    em_wireless = has_any(
        low,
        ["wireless", "electromagnetic", "emission", "rf", "uhf", "antenna", "radio", "rlc", "frequency modulation", "pulse"],
    )
    sensing = has_any(low, ["sensor", "sensing", "detection", "monitoring", "readout"])
    generic_teng = has_any(low, ["teng", "triboelectric", "nanogenerator"]) and not (exact_anchor or tribo_discharge)
    generic_wireless = has_any(low, ["battery-free", "passive", "backscatter", "rfid", "saw", "wearable"]) and not discharge
    core_chain = (
        profile["self_powered"]
        and profile["tribo_or_friction"]
        and profile["discharge_or_em_generation"]
        and profile["wireless_or_communication"]
        and profile["sensing_or_system"]
    )
    partial_chain_reference = (
        profile["self_powered"]
        and profile["tribo_or_friction"]
        and profile["discharge_or_em_generation"]
        and profile["sensing_or_system"]
    )
    ml_or_prediction = has_any(low, ["machine learning", "deep learning", "prediction", "classification"])
    pure_pd_power = "partial discharge" in low and has_any(
        low, ["transformer", "cable", "switchgear", "insulation", "power equipment"]
    ) and not ("wireless" in low and ("uhf" in low or "antenna" in low))
    review = has_any(low, ["review", "advances in", "recent advances", "bibliometric"])
    mdpi = is_mdpi(candidate)
    preferred_pair = candidate.mechanism_pair in {"A+B", "B+C", "A+B+C"}
    ac_only = candidate.mechanism_pair == "A+C"
    ac_exception = is_ac_exception_venue(candidate.venue)
    priority_venue = candidate.venue_priority in {"S", "A", "IEEE"}
    blocked = mdpi or review or pure_pd_power or ml_or_prediction

    if exact_anchor:
        candidate.level = "必读"
        candidate.relevance = 10
        candidate.novelty = 8
        candidate.reason = "已知锚点论文，完整匹配 TENG 高压触发放电、电磁无线信号、RLC/频率调制传感链条。"
    elif core_chain and not blocked:
        candidate.level = "建议读"
        candidate.relevance = 8
        candidate.novelty = 7
        candidate.reason = "可见题名/摘要/页面证据形成机制链条：自供能/摩擦或 triboelectric 激发，产生电磁波或击穿放电，并服务无线通信/传感系统。"
    elif (tribo_discharge or breakdown_discharge_effect) and em_wireless and sensing and not blocked:
        candidate.level = "建议读"
        candidate.relevance = 8
        candidate.novelty = 7
        candidate.reason = "题名/摘要直接指向 triboelectric/breakdown discharge + wireless sensing 链条。"
    elif preferred_pair and priority_venue and not blocked:
        candidate.level = "建议读" if candidate.mechanism_pair in {"B+C", "A+B+C"} else "可参考"
        candidate.relevance = 7 if candidate.level == "建议读" else 6
        candidate.novelty = 7
        candidate.reason = "满足机制三要素中的优先组合 A+B 或 B+C，且 venue 属于优先期刊名单；作为课题相关候选保留。"
    elif partial_chain_reference and priority_venue and not blocked:
        candidate.level = "可参考"
        candidate.relevance = 6
        candidate.novelty = 7
        candidate.reason = "摘要具备自供能、摩擦/triboelectric 与放电/电磁生成要素，但无线读出链条不完整；作为强转移参考保留。"
    elif ac_only and ac_exception and not blocked:
        candidate.level = "可参考"
        candidate.relevance = 6
        candidate.novelty = 7
        candidate.reason = "仅满足 A+C，按规则降权；因 venue 在 Nature/Science/Nature Electronics/Nature Sensors/IEEE Transactions 例外清单内，作为强转移参考保留。"
    else:
        candidate.level = "exclude"
        candidate.relevance = 0
        candidate.novelty = 0
        if ac_only and not ac_exception:
            candidate.reason = "仅满足 A+C，缺少击穿放电/电磁波生成证据，且不在严格顶刊例外清单内。"
        elif generic_teng:
            candidate.reason = "泛 TENG/自供能方向，未显式连接 triboelectric-discharge 无线读出。"
        elif generic_wireless:
            candidate.reason = "泛无源/柔性/无线传感，未显式连接击穿放电链条。"
        elif mdpi:
            candidate.reason = "MDPI 或低优先 venue，且未达到极其直接门槛。"
        elif review:
            candidate.reason = "综述/泛领域文章，不进入推荐。"
        elif pure_pd_power:
            candidate.reason = "电力设备局部放电监测/诊断，转移价值不足。"
        elif ml_or_prediction:
            candidate.reason = "偏预测/分类算法，非装置或无线读出机制。"
        else:
            candidate.reason = "未通过严格课题门槛。"
    if candidate.level != "exclude":
        candidate.reason = f"{candidate.reason} 机制组合：{candidate.mechanism_pair}。"


def feedback_buttons(paper_id: str) -> str:
    actions = [
        ("extremely_related", "极其相关"),
        ("related", "相关"),
        ("reference_only", "可参考"),
        ("irrelevant", "无关"),
    ]
    buttons = "".join(
        f'<button type="button" data-action="{action}">{html.escape(label)}</button>'
        for action, label in actions
    )
    return (
        f'<td class="feedback" data-paper-id="{html.escape(paper_id)}">'
        f"{buttons}<span class=\"feedback-status\">尚未反馈</span></td>"
    )


def render_html(recommended, query_counts, output_path):
    rows = []
    for idx, c in enumerate(recommended, 1):
        paper_id = f"P{idx:03d}"
        doi_text = c.doi.replace("https://doi.org/", "") if c.doi else ""
        doi_html = f'<a href="{html.escape(c.doi)}">{html.escape(doi_text)}</a>' if c.doi else "无 DOI"
        title = f'<a href="{html.escape(c.landing)}">{html.escape(c.title)}</a>' if c.landing else html.escape(c.title)
        rows.append(
            "<tr>"
            f"<td>{idx}</td>"
            f"<td>{html.escape(c.level)}</td>"
            f"<td>{title}</td>"
            f"<td>{html.escape(c.abstract or '未获取到摘要')}</td>"
            f"<td>{html.escape(c.venue)}</td>"
            f"<td>{html.escape(c.date[:4])}</td>"
            f"<td>{html.escape(c.mechanism_pair)}</td>"
            f"<td>{html.escape(venue_priority_label(c.venue_priority))}</td>"
            f"<td>{doi_html}</td>"
            f"<td>{c.relevance}</td>"
            f"<td>{c.novelty}</td>"
            f"<td>{html.escape(c.reason)}</td>"
            f"{feedback_buttons(paper_id)}"
            "</tr>"
        )
    if not rows:
        rows.append('<tr><td colspan="13">本轮近 3 年严格核查未确认新的可推荐论文。</td></tr>')
    priority_count = sum(1 for c in recommended if c.venue_priority in {"S", "A", "IEEE"})
    query_items = "".join(f"<li>{html.escape(q)}：{n}</li>" for q, n in query_counts)
    seen_filtered_count = getattr(render_html, "seen_filtered_count", 0)
    seen_index_path = getattr(render_html, "seen_index_path", SEEN_INDEX_PATH)
    venue_rule = "期刊名单只用于优先级排序和保底提示，不覆盖 A/B/C 机制链硬筛选；中科院分区门槛默认关闭。"
    doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>近 3 年击穿放电无线传感顶刊/IEEE 定向核查</title>
  <style>
    body {{ font-family: Arial, "Microsoft YaHei", sans-serif; margin: 24px; color: #18212f; }}
    table {{ width: 100%; border-collapse: collapse; table-layout: fixed; font-size: 13px; }}
    th, td {{ border: 1px solid #d9e0ea; padding: 8px; vertical-align: top; word-break: break-word; }}
    th {{ background: #eef3f8; }}
    .notice {{ border: 1px solid #d9e0ea; background: #f8fafc; padding: 10px 12px; border-radius: 6px; }}
    .feedback button {{ display:inline-block; margin:0 4px 5px 0; border:1px solid #9bb8e8; border-radius:4px; padding:3px 6px; color:#1f5fbf; background:#f7fbff; cursor:pointer; font:inherit; line-height:1.2; }}
    .feedback button[data-action="extremely_related"] {{ --active-bg:#dff8ea; --active-border:#239354; --active-ink:#0f6537; }}
    .feedback button[data-action="related"] {{ --active-bg:#e7f1ff; --active-border:#5f9be3; --active-ink:#1f5fbf; }}
    .feedback button[data-action="reference_only"] {{ --active-bg:#fff3cf; --active-border:#d49b24; --active-ink:#8a5a00; }}
    .feedback button[data-action="irrelevant"] {{ --active-bg:#fff1f0; --active-border:#e46b61; --active-ink:#a92d25; }}
    .feedback.has-selection button {{ color:#ffffff; background:#111827; border-color:#111827; }}
    .feedback button.active,
    .feedback.has-selection button.active {{ color:var(--active-ink); background:var(--active-bg); border-color:var(--active-border); font-weight:700; box-shadow:0 0 0 2px var(--active-border) inset; }}
    .feedback-status {{ display:block; min-height:18px; margin-top:2px; color:#415064; }}
  </style>
</head>
<body>
  <h1>近 3 年击穿放电无线传感顶刊/IEEE 定向核查</h1>
  <p>报告 ID：{REPORT_ID}｜窗口：{START.isoformat()} 至 {TODAY.isoformat()}</p>
  <div class="notice">只展示通过严格门槛的推荐论文；非推荐样例不再列出。机制筛选按 A=自供能/摩擦/triboelectric 激发、B=击穿放电/电磁波生成、C=无线通信/传感/可穿戴系统功能执行，优先 A+B/B+C，A+C 降权且仅在 S 级顶刊和 IEEE Transactions 例外。{venue_rule} 检索源为 OpenAlex public API，并在配置 API key 时用 Semantic Scholar、Springer Nature Meta API 与 Elsevier API 补全 DOI 摘要/引用元数据；结论为元数据/摘要层面初筛。</div>
  <p>推荐数量：{len(recommended)}；其中 S/A/IEEE 优先 venue：{priority_count}；已见去重隐藏：{seen_filtered_count}。去重索引：{html.escape(str(seen_index_path))}</p>
  <table>
    <thead><tr><th style="width:42px">序号</th><th style="width:70px">等级</th><th style="width:250px">标题</th><th>摘要</th><th style="width:130px">期刊/会议</th><th style="width:55px">年份</th><th style="width:72px">机制链</th><th style="width:120px">期刊优先级</th><th style="width:110px">DOI</th><th style="width:70px">相关性</th><th style="width:70px">创新性</th><th style="width:260px">综合判断</th><th style="width:150px">用户反馈</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
  <h2>查询计数</h2>
  <ul>{query_items}</ul>
<script>
  (function () {{
    const actionLabels = {{extremely_related:"极其相关", related:"相关", reference_only:"可参考", irrelevant:"无关"}};
    const feedbackEndpoint = "";
    document.querySelectorAll(".feedback button").forEach((button) => {{
      button.addEventListener("click", () => {{
        const cell = button.closest(".feedback");
        cell.classList.add("has-selection");
        cell.querySelectorAll("button").forEach((item) => {{
          const selected = item === button;
          item.classList.toggle("active", selected);
          item.setAttribute("aria-pressed", selected ? "true" : "false");
        }});
        const label = actionLabels[button.dataset.action] || button.textContent.trim();
        const time = new Date().toLocaleTimeString("zh-CN", {{hour12:false}});
        cell.querySelector(".feedback-status").textContent = "当前反馈：" + label + "，更新时间 " + time;
        if (feedbackEndpoint) {{
          const params = new URLSearchParams({{report_id:"{REPORT_ID}", paper_id:cell.dataset.paperId || "", action:button.dataset.action || ""}});
          fetch(feedbackEndpoint + "?" + params.toString(), {{method:"GET", keepalive:true}}).catch(() => {{}});
        }}
      }});
    }});
  }})();
</script>
</body>
</html>
"""
    output_path.write_text(doc, encoding="utf-8")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    work_dir = RADAR_ARTIFACT_DIR / "runs"
    out_dir = RADAR_ARTIFACT_DIR / "reports"
    work_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    items = {}
    query_counts = []
    query_limit = int(os.environ.get("RADAR_QUERY_LIMIT", "0"))
    active_queries = QUERIES[:query_limit] if query_limit > 0 else QUERIES
    if OPENALEX_DISABLED:
        print("OpenAlex disabled by OPENALEX_DISABLED=1; using DOI seed fallback only.", flush=True)
        query_counts.append(("OpenAlex disabled", 0))
    else:
        openalex_timeouts = 0
        for idx, (track, query) in enumerate(active_queries, 1):
            print(f"OpenAlex query {idx}/{len(active_queries)} [{track}]: {query}", flush=True)
            data = openalex_query(query)
            if data.get("error") and not data.get("_cache_hit"):
                openalex_timeouts += 1
                if OPENALEX_MAX_TIMEOUTS >= 0 and openalex_timeouts >= OPENALEX_MAX_TIMEOUTS:
                    label = "cache miss" if OPENALEX_CACHE_ONLY else "timeout"
                    print(
                        f"OpenAlex {label} budget reached ({openalex_timeouts}); stopping OpenAlex queries and using DOI/API fallback.",
                        flush=True,
                    )
                    query_counts.append((f"OpenAlex {label} budget reached", openalex_timeouts))
                    break
            query_counts.append((query, int(data.get("meta", {}).get("count", 0))))
            for work in data.get("results", []):
                key = normalized_key(work)
                if not key:
                    continue
                item = items.get(key)
                if item is None:
                    landing = first_landing(work)
                    doi_value = (work.get("doi") or "").lower().replace("https://doi.org/", "")
                    abstract = reconstruct_abstract(work.get("abstract_inverted_index"))
                    abstract_source = "OpenAlex" if abstract else "not retrieved"
                    if not abstract and doi_value in MANUAL_EVIDENCE:
                        abstract = MANUAL_EVIDENCE[doi_value]["abstract_hint"]
                        abstract_source = "page-text/manual-evidence"
                    item = Candidate(
                        title=work.get("display_name") or work.get("title") or "",
                        date=work.get("publication_date") or "",
                        doi=work.get("doi") or "",
                        venue=source_name(work),
                        landing=landing,
                        abstract=abstract,
                        abstract_source=abstract_source,
                    )
                    items[key] = item
                item.queries.add(query)
                item.tracks.add(track)
            time.sleep(0.15)

    seed_added = add_seed_papers(items)
    if seed_added:
        query_counts.append(("seed DOI fallback", seed_added))

    s2_stats = semantic_scholar_enrich_candidates(items.values())
    sn_stats = springer_nature_enrich_candidates(items.values())
    els_stats = elsevier_enrich_candidates(items.values())

    for item in items.values():
        classify(item)
        apply_quality_gate(item)

    seen_index = load_seen_index()
    show_seen = os.environ.get("RADAR_SHOW_SEEN", "").strip().lower() in {"1", "true", "yes"}
    pre_quality_recommended = [
        c for c in items.values()
        if c.level in {"必读", "建议读", "可参考"}
    ]
    quality_excluded = [c for c in pre_quality_recommended if not quality_allows(c)]
    quality_allowed = [c for c in pre_quality_recommended if quality_allows(c)]
    if show_seen:
        recommended = quality_allowed
        seen_filtered = []
    else:
        recommended, seen_filtered = split_unseen(quality_allowed, seen_index)
    recommended.sort(
        key=lambda c: (
            c.level == "必读",
            c.level == "建议读",
            c.mechanism_pair in {"A+B+C", "B+C", "A+B"},
            venue_priority_rank(c.venue_priority),
            c.relevance,
            c.novelty,
            c.date,
        ),
        reverse=True,
    )
    seen_update = update_seen_index(quality_allowed, REPORT_ID)

    payload = {
        "report_id": REPORT_ID,
        "window": [START.isoformat(), TODAY.isoformat()],
        "query_counts": query_counts,
        "candidate_count": len(items),
        "seed_candidate_count": seed_added,
        "pre_quality_recommended_count": len(pre_quality_recommended),
        "recommended_count": len(recommended),
        "quality_excluded_count": len(quality_excluded),
        "seen_filtered_count": len(seen_filtered),
        "seen_index": seen_update,
        "quality_gate": {
            "mode": CAS_PARTITION_MODE,
            "table": str(CAS_PARTITION_TABLE),
            "allowed_cas_zones": sorted(CAS_ALLOWED_ZONES),
        },
        "venue_priority_rule": {
            "S": S_TIER_VENUES,
            "A": A_TIER_VENUES,
            "IEEE": IEEE_CORE_VENUES,
            "B_direct_only": B_TIER_DIRECT_ONLY_VENUES,
            "note": "venue priority changes ranking and top-lane coverage only; A/B/C mechanism evidence remains the hard gate",
        },
        "mechanism_rule": {
            "A": "self-powered/friction/triboelectric/electrostatic excitation",
            "B": "breakdown discharge/electromagnetic wave generation",
            "C": "wireless communication/sensing/wearable system function",
            "preferred": ["A+B", "B+C", "A+B+C"],
            "A+C_exception_venues": ["S-tier venues", "IEEE Transactions*"],
        },
        "semantic_scholar_enrichment": s2_stats,
        "springer_nature_enrichment": sn_stats,
        "elsevier_enrichment": els_stats,
        "recommended": [
            c.__dict__ | {"queries": sorted(c.queries), "tracks": sorted(c.tracks)}
            for c in recommended
        ],
        "top_venue_recommended_count": sum(1 for c in recommended if c.venue_priority in {"S", "A", "IEEE"}),
    }
    json_path = work_dir / f"three_year_top_scout_{TODAY.isoformat()}.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path = out_dir / f"research_paper_radar_3yr_top_scout_{TODAY.isoformat()}.html"
    render_html.seen_filtered_count = len(seen_filtered)
    render_html.seen_index_path = SEEN_INDEX_PATH
    render_html(recommended, query_counts, html_path)
    save_openalex_cache()
    print(f"Candidates: {len(items)}")
    print(f"Seed DOI fallback candidates added: {seed_added}")
    print(f"Pre-quality recommended: {len(pre_quality_recommended)}")
    print(f"Quality excluded: {len(quality_excluded)}")
    print(f"Seen filtered: {len(seen_filtered)}")
    print(f"Seen index: {seen_update['path']} total={seen_update['total']} touched={seen_update['touched']}")
    print(f"CAS partition mode: {CAS_PARTITION_MODE} table={CAS_PARTITION_TABLE}")
    print(f"Recommended: {len(recommended)}")
    print(f"Top/strong recommended: {payload['top_venue_recommended_count']}")
    print(
        "Semantic Scholar enrichment: "
        f"available={s2_stats['available']} checked={s2_stats['checked']} "
        f"filled_abstracts={s2_stats['filled_abstracts']}"
    )
    print(
        "Springer Nature enrichment: "
        f"available={sn_stats['available']} checked={sn_stats['checked']} "
        f"filled_abstracts={sn_stats['filled_abstracts']}"
    )
    print(
        "Elsevier enrichment: "
        f"available={els_stats['available']} checked={els_stats['checked']} "
        f"filled_abstracts={els_stats['filled_abstracts']}"
    )
    print(f"Wrote {json_path}")
    print(f"Wrote {html_path}")
    for c in recommended:
        print(f"- {c.level}: {c.title} | {c.venue} | {c.date} | {c.doi}")


if __name__ == "__main__":
    main()
