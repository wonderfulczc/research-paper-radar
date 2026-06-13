import csv
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from semantic_scholar_enrich import semantic_scholar_enrich_candidates
from crossref_enrich import crossref_enrich_candidates
from springer_nature_enrich import springer_nature_enrich_candidates
from elsevier_enrich import elsevier_enrich_candidates
from mechanism_terms import MECHANISM_TERMS
from radar_state import RADAR_ARTIFACT_DIR, SEEN_INDEX_PATH, is_seen, load_seen_index, update_seen_index
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
START = TODAY - timedelta(days=61)
REPORT_ID = f"RADAR-{TODAY.isoformat()}"
BASE = "https://api.openalex.org/works"
OPENALEX_TIMEOUT_SECONDS = int(os.environ.get("OPENALEX_TIMEOUT_SECONDS", "20"))
OPENALEX_RETRIES = int(os.environ.get("OPENALEX_RETRIES", "2"))
OPENALEX_PER_PAGE = int(os.environ.get("OPENALEX_PER_PAGE", "10"))
CAS_PARTITION_TABLE = Path(os.environ.get("CAS_PARTITION_TABLE", "work/journal_quartiles.csv"))
CAS_PARTITION_MODE = os.environ.get("CAS_PARTITION_MODE", "off").strip().lower()
if CAS_PARTITION_MODE not in {"strict", "warn", "off"}:
    CAS_PARTITION_MODE = "strict"
CAS_ALLOWED_ZONES = {"1", "2"}
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

QUERIES = [
    ("core", "breakdown discharge wireless sensing"),
    ("core", "triboelectric discharge wireless sensing"),
    ("core", "microgap discharge electromagnetic emission"),
    ("core", "spark discharge electromagnetic signal sensor"),
    ("core", "corona discharge electromagnetic sensing"),
    ("core", "discharge current waveform electromagnetic pulse sensor"),
    ("core", "partial discharge electromagnetic sensor"),
    ("transfer", "flexible passive wireless sensor LC resonator"),
    ("transfer", "chipless RFID flexible sensor"),
    ("transfer", "battery-free wireless flexible sensor"),
    ("transfer", "passive wireless SAW sensor"),
    ("transfer", "NFC flexible sensor"),
    ("transfer", "backscatter wearable sensor"),
    ("transfer", "chip-less self-powered electronic patch"),
    ("transfer", "self-powered electronic patch wireless sensing"),
    ("transfer", "self-powered electrotactile textile haptic glove"),
    ("transfer", "electrotactile textile haptic human-machine interface"),
    ("transfer", "triboelectric wireless sensor"),
    ("transfer", "self-powered wireless sensor energy harvesting"),
    ("top", "Nature battery-free wireless sensor"),
    ("top", "Nature Sensors self-powered sensor"),
    ("top", "Nature Sensors electronic patch"),
    ("top", "Nature Portfolio wireless passive sensor"),
    ("top", "Advanced Materials flexible wireless sensor"),
    ("top", "Advanced Functional Materials wireless sensor"),
    ("top", "ACS Nano wireless sensor battery-free"),
    ("top", "Nano Energy self-powered wireless sensor"),
    ("top", "IEEE Transactions partial discharge UHF sensor"),
    ("top", "IEEE Transactions wireless passive sensor"),
    ("top", "IEEE Transactions antennas microwave sensor"),
]

POSITIVE = {
    "discharge": 3,
    "breakdown": 3,
    "spark": 3,
    "corona": 3,
    "partial discharge": 3,
    "electromagnetic": 2,
    "wireless": 2,
    "self-powered": 2,
    "battery-free": 2,
    "passive": 2,
    "lc": 2,
    "resonator": 2,
    "rfid": 2,
    "chipless": 2,
    "saw": 2,
    "backscatter": 2,
    "flexible": 1,
    "wearable": 1,
    "triboelectric": 1,
    "sensor": 1,
    "sensing": 1,
}

NEGATIVE = {
    "deep learning": 3,
    "machine learning": 2,
    "prediction": 2,
    "review": 2,
    "surface modification": 2,
    "plasma physiotherapy": 3,
    "spark plug": 3,
    "combustion": 2,
    "landfill gas": 2,
    "material synthesis": 2,
    "photocatal": 2,
    "electrochemical": 2,
    "charging–discharging": 2,
    "charging-discharging": 2,
}

TOP_VENUE_HINTS = [
    *S_TIER_VENUES,
    *A_TIER_VENUES,
    *IEEE_CORE_VENUES,
]

STRONG_SPECIALIST_HINTS = [
    *B_TIER_DIRECT_ONLY_VENUES,
]

MDPI_VENUES = [
    "Sensors",
    "Micromachines",
    "Energies",
    "Electronics",
    "Materials",
    "Nanomaterials",
    "Polymers",
    "Applied Sciences",
    "Bioengineering",
]

@dataclass
class Candidate:
    title: str
    date: str
    doi: str
    venue: str
    work_type: str
    landing: str
    abstract: str
    abstract_source: str = "not retrieved"
    queries: set = field(default_factory=set)
    tracks: set = field(default_factory=set)
    openalex_id: str = ""
    s2_paper_id: str = ""
    citation_count: int = 0
    influential_citation_count: int = 0
    relevance: int = 0
    novelty: int = 0
    level: str = "暂不读"
    paper_type: str = "近似但排除"
    reason: str = ""
    novelty_reason: str = ""
    borrow: str = ""
    risk: str = ""
    venue_class: str = ""
    venue_priority: str = "ordinary"
    fit_class: str = ""
    mechanism_pair: str = ""
    mechanism_evidence: str = ""
    cas_zone: str = ""
    quality_source: str = ""
    quality_gate: str = "unchecked"


def openalex_query(query: str, per_page: int | None = None) -> dict:
    if per_page is None:
        per_page = OPENALEX_PER_PAGE
    params = {
        "search": query,
        "filter": f"from_publication_date:{START.isoformat()},to_publication_date:{TODAY.isoformat()}",
        "per_page": str(per_page),
        "sort": "relevance_score:desc",
    }
    url = BASE + "?" + urllib.parse.urlencode(params)
    headers = {"User-Agent": "Codex research-paper-radar test"}
    last_error = ""
    for attempt in range(OPENALEX_RETRIES + 1):
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=OPENALEX_TIMEOUT_SECONDS) as resp:
                raw = resp.read().decode("utf-8")
            return json.loads(raw)
        except (TimeoutError, urllib.error.URLError, OSError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < OPENALEX_RETRIES:
                wait_seconds = 1.5 * (attempt + 1)
                print(
                    f"WARNING: OpenAlex query timeout/error, retry {attempt + 1}/{OPENALEX_RETRIES}: {query}",
                    file=sys.stderr,
                )
                time.sleep(wait_seconds)
                continue
            print(
                f"WARNING: OpenAlex query skipped after retries: {query} ({last_error})",
                file=sys.stderr,
            )
            return {"meta": {"count": 0}, "results": [], "error": last_error}


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
    if title:
        return title
    return (work.get("doi") or "").lower()


def keyword_score(text):
    low = text.lower()
    pos = sum(weight for term, weight in POSITIVE.items() if term in low)
    neg = sum(weight for term, weight in NEGATIVE.items() if term in low)
    return pos, neg


def venue_contains(venue: str, hints) -> bool:
    low = venue.lower()
    for hint in hints:
        h = hint.lower()
        if h in {"nature", "science", "device"}:
            if low == h:
                return True
        elif h in low:
            return True
    return False


def is_mdpi(candidate: Candidate) -> bool:
    doi = (candidate.doi or "").lower()
    if "10.3390/" in doi:
        return True
    return any(candidate.venue.lower() == venue.lower() for venue in MDPI_VENUES)


def venue_class(candidate: Candidate) -> str:
    if is_mdpi(candidate):
        return "MDPI low-priority"
    priority = venue_priority(candidate.venue)
    if priority in {"S", "A", "IEEE"}:
        return "top venue"
    if priority == "B":
        return "strong specialist"
    return "ordinary/unknown"


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
    row = load_journal_quality_table().get(normalize_venue_name(candidate.venue))
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


def mechanism_profile(text: str) -> dict:
    low = text.lower()
    return {
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


def merge_manual_profile(candidate: Candidate, profile: dict) -> dict:
    doi_key = (candidate.doi or "").lower().replace("https://doi.org/", "")
    manual = MANUAL_EVIDENCE.get(doi_key)
    if manual:
        for key, value in manual["profile"].items():
            profile[key] = profile[key] or value
    return profile


def classify(candidate: Candidate):
    text = " ".join([candidate.title, candidate.abstract, candidate.venue])
    title_low = candidate.title.lower()
    low = text.lower()
    profile = merge_manual_profile(candidate, mechanism_profile(text))
    candidate.mechanism_pair = mechanism_pair_label(profile)
    candidate.mechanism_evidence = mechanism_evidence_text(profile)
    pos, neg = keyword_score(text)
    candidate.venue_priority = venue_priority(candidate.venue)
    candidate.venue_class = venue_class(candidate)

    review = "review" in low
    mdpi = candidate.venue_class == "MDPI low-priority"
    top_or_strong = candidate.venue_class in {"top venue", "strong specialist"}
    teng = "triboelectric" in low or "teng" in low
    weak_ml = has_any(low, ["deep learning", "machine learning", "prediction", "classification"])
    partial_any = "partial discharge" in low
    power_equipment_pd = "partial discharge" in low and has_any(
        low,
        ["high-voltage", "high voltage", "cable", "transformer", "insulation", "switchgear", "power equipment"],
    )
    core_discharge = bool(re.search(
        r"\b(breakdown|spark|corona|microgap|microplasma)\b|"
        r"triboelectric[- ]discharge|discharge[- ]triggered|electromagnetic pulse",
        low,
    ))
    user_core_discharge = bool(re.search(
        r"\b(spark|corona|microgap|microplasma)\b|"
        r"triboelectric[- ]discharge|discharge[- ]triggered|breakdown[- ]discharge|"
        r"(breakdown.*wireless|wireless.*breakdown)",
        low,
    ))
    em_readout = has_any(
        low,
        ["electromagnetic", "rf ", "radio", "uhf", "ghz", "microwave", "antenna", "waveform", "spectrum", "frequency", "pulse", "emission"],
    )
    wireless_readout = has_any(
        low,
        ["wireless", "rfid", "nfc", "backscatter", "chipless", "saw", "lc", "resonator", "dual-band", "microwave", "antenna", "reader"],
    )
    sensing_path = has_any(low, ["sensor", "sensing", "detection", "localization", "monitoring", "readout"])
    passive_wireless = has_any(
        low,
        ["battery-free", "batteryless", "passive", "chipless", "rfid", "nfc", "backscatter", "saw", "lc", "resonator", "dual-band", "microwave"],
    ) and wireless_readout and sensing_path and has_any(
        title_low,
        ["sensor", "sensing", "wireless", "batteryless", "battery-free", "passive", "rfid", "nfc", "backscatter", "chipless", "saw", "antenna", "resonator"],
    )
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
    preferred_pair = candidate.mechanism_pair in {"A+B", "B+C", "A+B+C"}
    ac_only = candidate.mechanism_pair == "A+C"
    ac_exception = is_ac_exception_venue(candidate.venue)

    relevance = 0
    direct_transfer_cue = has_any(
        low,
        ["high voltage", "high-voltage", "electric field", "electrostatic", "field emission", "air gap", "microgap", "spark", "corona", "breakdown", "discharge", "plasma"],
    )

    if core_discharge and wireless_readout and em_readout and sensing_path and user_core_discharge:
        relevance = 9
        candidate.fit_class = "core-chain"
    elif core_discharge and em_readout and sensing_path and user_core_discharge:
        relevance = 7
        candidate.fit_class = "mechanism-support"
    elif passive_wireless and direct_transfer_cue and top_or_strong:
        relevance = 4
        candidate.fit_class = "direct-transfer-near-miss"
    elif core_chain:
        relevance = 8
        candidate.fit_class = "abstract-chain-match"
    elif preferred_pair and top_or_strong:
        relevance = 7 if candidate.mechanism_pair in {"B+C", "A+B+C"} else 6
        candidate.fit_class = "mechanism-support" if candidate.mechanism_pair in {"B+C", "A+B+C"} else "top-transfer-reference"
    elif partial_chain_reference and top_or_strong:
        relevance = 6
        candidate.fit_class = "top-transfer-reference"
    elif ac_only and ac_exception:
        relevance = 5
        candidate.fit_class = "top-ac-transfer-reference"
    elif passive_wireless:
        relevance = 2
        candidate.fit_class = "generic-transfer-rejected"
    elif power_equipment_pd and em_readout:
        relevance = 5
        candidate.fit_class = "partial-discharge-reference"
    else:
        relevance = max(0, min(4, 2 + min(pos, 2) - neg))
        candidate.fit_class = "weak-or-keyword-adjacent"

    if ac_only and not ac_exception:
        relevance = min(relevance, 2)
        candidate.fit_class = "ac-only-rejected"
    if teng and not (user_core_discharge and em_readout and wireless_readout) and candidate.mechanism_pair not in {"A+B+C", "B+C"}:
        relevance = min(relevance, 2)
        candidate.fit_class = "teng-reference-only"
    if partial_any and not user_core_discharge:
        relevance = min(relevance, 5)
        candidate.fit_class = "partial-discharge-reference"
    if mdpi and relevance < 9:
        relevance = min(relevance, 4)
    if weak_ml:
        relevance = min(relevance, 3)
    if review:
        relevance = min(relevance, 4)
    if neg >= 3 and candidate.fit_class not in {"core-chain", "mechanism-support"}:
        relevance = min(relevance, 4)

    novelty = 3
    if candidate.fit_class == "core-chain":
        novelty = 8
    elif candidate.fit_class == "mechanism-support":
        novelty = 6
    elif candidate.fit_class in {"direct-transfer-near-miss", "partial-discharge-reference", "teng-reference-only", "top-transfer-reference"}:
        novelty = 5
    elif candidate.fit_class == "top-ac-transfer-reference":
        novelty = 6
    if candidate.fit_class == "top-transfer-reference":
        novelty = 7
    if candidate.fit_class == "abstract-chain-match":
        novelty = 7
    elif candidate.fit_class == "generic-transfer-rejected":
        novelty = 3
    if has_any(low, ["exceptional-point", "chipless", "battery-free", "batteryless", "non-reciprocal", "ghz", "dual-band", "self-calibration"]):
        novelty += 1
    if candidate.venue_class == "top venue":
        novelty += 1
    if mdpi:
        novelty = min(novelty, 5)
    if weak_ml:
        novelty = min(novelty, 4)
    if review:
        novelty = min(novelty, 5)
    novelty = min(9, novelty)

    candidate.relevance = relevance
    candidate.novelty = novelty

    if candidate.fit_class == "core-chain":
        candidate.paper_type = "击穿放电无线传感" if "sensor" in low or "sensing" in low else "击穿放电机理支撑"
        candidate.reason = "明确含击穿/放电机制，并出现无线、射频或电磁信号读出线索。"
        candidate.borrow = "可核验其放电触发信号、波形/频谱特征或无线接收设计。"
    elif candidate.fit_class == "mechanism-support":
        candidate.paper_type = "击穿放电机理支撑"
        candidate.reason = "含击穿/放电或 EM 信号机制，但无线传感链条需要进一步核验。"
        candidate.borrow = "可借鉴放电阈值、波形或实验方法；若无 EM 读出则排除。"
    elif candidate.fit_class == "direct-transfer-near-miss":
        candidate.paper_type = "柔性无线传感借鉴"
        candidate.reason = "有少量可迁移线索，但仍未直接连接到击穿放电无线传感链条。"
        candidate.borrow = "仅作为近似候选复核，不进入主表推荐。"
    elif candidate.fit_class == "generic-transfer-rejected":
        candidate.paper_type = "近似但排除"
        candidate.reason = "泛无线/泛被动/泛传感方向，经用户反馈判定为无关或无参考性。"
        candidate.borrow = "不作为后续主表推荐模式。"
    elif candidate.fit_class == "partial-discharge-reference":
        candidate.paper_type = "击穿放电机理支撑"
        candidate.reason = "局部放电监测方向，仅在 EM/UHF/定位方法可迁移时有参考价值。"
        candidate.borrow = "最多参考接收、定位或信号处理方法，不作为核心无线传感论文。"
    elif candidate.fit_class == "teng-reference-only":
        candidate.paper_type = "自供能/无电池无线传感借鉴"
        candidate.reason = "TENG/自供能相关但未证明与击穿放电无线读出强相关。"
        candidate.borrow = "仅可参考能量管理、结构设计或系统供能思路。"
    elif candidate.fit_class == "abstract-chain-match":
        candidate.paper_type = "自供能/无电池无线传感借鉴"
        candidate.reason = "可见题名/摘要/页面证据形成机制链条：自供能/摩擦或 triboelectric 激发，产生电磁波或击穿放电，并服务无线通信/传感系统。"
        candidate.borrow = "可借鉴信号产生机制、无线读出距离、系统集成和可穿戴传感实现。"
    elif candidate.fit_class == "top-transfer-reference":
        candidate.paper_type = "自供能/无电池无线传感借鉴"
        candidate.reason = "摘要具备自供能、摩擦/triboelectric 与放电/电磁生成要素，但无线读出链条不完整；作为强转移参考保留。"
        candidate.borrow = "可参考系统结构、能量/信号耦合方式、可穿戴封装或交互场景。"
    elif candidate.fit_class == "top-ac-transfer-reference":
        candidate.paper_type = "自供能/无电池无线传感借鉴"
        candidate.reason = "仅满足 A+C，按规则降权；因 venue 在 Nature/Science/Nature Electronics/Nature Sensors/IEEE Transactions 例外清单内，作为强转移参考保留。"
        candidate.borrow = "仅参考系统功能、无线/可穿戴设计或验证场景；不能作为击穿放电核心证据。"
    elif candidate.fit_class == "ac-only-rejected":
        candidate.paper_type = "近似但排除"
        candidate.reason = "仅满足 A+C，缺少击穿放电/电磁波生成证据，且不在严格顶刊例外清单内。"
        candidate.borrow = "不进入主表推荐，除非源页面补出 B 侧机制证据。"
    else:
        candidate.paper_type = "近似但排除"
        candidate.reason = "关键词相近，但未看到明确的放电无线传感或可迁移被动无线机制。"
        candidate.borrow = "暂不作为主线参考。"

    if mdpi:
        candidate.risk = "MDPI/低优先 venue；除非极其直接，否则减少推荐。"
    elif teng and candidate.fit_class == "teng-reference-only":
        candidate.risk = "TENG-based only; user feedback marked this family as irrelevant/no-reference unless discharge-wireless readout is explicit."
    elif candidate.fit_class == "partial-discharge-reference":
        candidate.risk = "局部放电监测/诊断方向；通常仅可参考，避免误作核心推荐。"
    elif candidate.fit_class == "top-transfer-reference":
        candidate.risk = "强转移参考，不等同于击穿放电无线传感核心论文。"
    elif candidate.fit_class == "top-ac-transfer-reference":
        candidate.risk = "A+C 顶刊例外，仍缺少 B 侧击穿放电/电磁波生成证据。"
    elif candidate.fit_class == "ac-only-rejected":
        candidate.risk = "A+C 非例外组合；按用户反馈不进入推荐。"
    elif candidate.fit_class == "abstract-chain-match":
        candidate.risk = "需源页面复核摘要链条和实际实验结构。"
    elif weak_ml:
        candidate.risk = "pure ML/prediction/classification emphasis; weak device or wireless-readout transfer value."
    elif "review" in low:
        candidate.risk = "综述类；除非作为机制地图，否则不进入主表。"
    elif neg:
        candidate.risk = "存在弱相关或负向关键词，需人工复核。"
    elif not candidate.abstract:
        candidate.risk = "OpenAlex 未给出摘要，证据级别偏低。"
    else:
        candidate.risk = "需核验出版商页面和图文摘要。"

    if candidate.venue_class == "top venue":
        candidate.novelty_reason = "顶刊/大子刊候选；仍需按机制相关性复核，不能仅凭 venue 推荐。"
    elif candidate.venue_class == "strong specialist":
        candidate.novelty_reason = "强专业期刊候选；按机制迁移价值初判。"
    else:
        candidate.novelty_reason = "按标题/摘要关键词初判；正式结论需结合源页面。"

    if weak_ml or review or mdpi or (neg >= 3 and candidate.fit_class not in {"core-chain", "mechanism-support"}):
        candidate.level = "暂不读"
    elif candidate.fit_class == "core-chain" and candidate.relevance >= 9 and candidate.novelty >= 8:
        candidate.level = "必读"
    elif candidate.relevance >= 7:
        candidate.level = "建议读"
    elif candidate.fit_class == "mechanism-support" and candidate.relevance >= 5:
        candidate.level = "可参考"
    elif candidate.fit_class == "top-transfer-reference" and candidate.relevance >= 7:
        candidate.level = "建议读"
    elif candidate.fit_class == "top-transfer-reference":
        candidate.level = "可参考"
    elif candidate.fit_class == "top-ac-transfer-reference":
        candidate.level = "可参考"
    elif candidate.fit_class == "abstract-chain-match":
        candidate.level = "建议读"
    else:
        candidate.level = "暂不读"
    if candidate.level != "暂不读":
        candidate.reason = f"{candidate.reason} 机制组合：{candidate.mechanism_pair}。"


def feedback_buttons(paper_id):
    actions = [
        ("extremely_related", "极其相关", "relevance"),
        ("related", "相关", "relevance"),
        ("reference_only", "可参考", "relevance"),
        ("irrelevant", "无关", "relevance"),
        ("downloaded", "已下载", "workflow"),
        ("read", "已精读", "workflow"),
        ("wrong", "误判", "workflow"),
        ("follow", "重点跟进", "workflow"),
        ("less", "下次少推此类", "workflow"),
    ]
    buttons = "".join(
        f'<button type="button" data-group="{group}" data-action="{action}">{html.escape(label)}</button>'
        for action, label, group in actions
    )
    return (
        f'<td class="feedback" data-paper-id="{html.escape(paper_id)}">'
        '<span class="small">非持久：</span>'
        f"{buttons}<span class=\"feedback-status\">尚未反馈</span></td>"
    )


def is_reference_worthy(candidate: Candidate) -> bool:
    return candidate.level in {"必读", "建议读", "可参考"}


def topic_relevance_text(candidate: Candidate) -> str:
    mapping = {
        "core-chain": "极其相关候选：贴近击穿/放电触发无线信号链条。",
        "mechanism-support": "相关候选：提供击穿/放电或电磁信号机制支撑，但需复核无线读出链条。",
        "direct-transfer-near-miss": "近似但不推荐：存在少量迁移线索，但没有直接进入课题链条。",
        "generic-transfer-rejected": "无关：泛无线/泛被动/泛传感方向已由用户反馈判定为无参考性。",
        "partial-discharge-reference": "无关或弱参考：局部放电监测/诊断方向，通常不服务当前课题主线。",
        "teng-reference-only": "无关或弱参考：TENG/自供能方向，未证明与击穿放电无线读出强相关。",
        "abstract-chain-match": "相关：摘要形成自供能/摩擦或 triboelectric 到电磁波/放电，再到无线通信/传感的链条。",
        "top-transfer-reference": "可参考：摘要具备自供能、摩擦/triboelectric 与放电/电磁生成要素，但无线读出链条不完整。",
        "top-ac-transfer-reference": "可参考：仅 A+C，但 venue 属于严格顶刊/IEEE Trans 例外清单，已降级。",
        "ac-only-rejected": "无关或弱相关：仅 A+C，缺少 B 侧击穿放电/电磁波生成证据。",
        "weak-or-keyword-adjacent": "无关或弱相关：主要是关键词相近，缺少清晰课题迁移路径。",
    }
    return mapping.get(candidate.fit_class, "待复核：需要源页面确认与课题的真实关系。")


def render_html(candidates, exclusions, query_counts, output_path):
    top_count = sum(1 for c in candidates if c.venue_priority in {"S", "A", "IEEE"})
    top_shortfall = max(0, 3 - top_count)
    seen_filtered_count = getattr(render_html, "seen_filtered_count", 0)

    def render_candidate_row(c: Candidate, idx: int, paper_id: str, extra_judgment: str = "") -> str:
        doi_text = c.doi.replace("https://doi.org/", "") if c.doi else ""
        doi_html = f'<a href="{html.escape(c.doi)}">{html.escape(doi_text)}</a>' if c.doi else "无 DOI"
        evidence = c.abstract_source if c.abstract else "metadata only"
        title = f'<a href="{html.escape(c.landing)}">{html.escape(c.title)}</a>' if c.landing else html.escape(c.title)
        abstract_text = c.abstract or "未获取到摘要"
        risk_text = f" 排除/风险：{c.risk}" if c.risk else ""
        summary = (
            f"筛选原因：{c.reason} "
            f"与课题相关性：{topic_relevance_text(c)} "
            f"机制链：{c.mechanism_pair}（{c.mechanism_evidence}）；期刊优先级：{venue_priority_label(c.venue_priority)}。"
            f"{extra_judgment}{risk_text} "
            f"当前等级：{c.level}；venue：{c.venue_class}；证据边界：OpenAlex/Semantic Scholar/Springer Nature/Elsevier 初筛，待 DOI/出版商源页面复核。"
        )
        return (
            "<tr>"
            f"<td>{idx}</td>"
            f"<td class=\"level\">{html.escape(c.level)}</td>"
            f"<td>{html.escape(c.paper_type)}</td>"
            f"<td class=\"title-cell\">{title}</td>"
            f"<td class=\"abstract-cell\">{html.escape(abstract_text)}</td>"
            f"<td class=\"venue-cell\">{html.escape(c.venue)}</td>"
            f"<td>{html.escape(c.date[:4])}</td>"
            f"<td class=\"doi-cell\">{doi_html}</td>"
            f"<td>{evidence}</td>"
            f"<td>{c.relevance}</td>"
            f"<td>{c.novelty}</td>"
            f"<td class=\"judgment-cell\">{html.escape(summary)}</td>"
            f"<td class=\"judgment-cell\">{html.escape(c.novelty_reason)}</td>"
            f"<td class=\"judgment-cell\">{html.escape(c.borrow)}</td>"
            f"{feedback_buttons(paper_id)}"
            "</tr>"
        )

    def render_exclusion_row(c: Candidate, idx: int, paper_id: str) -> str:
        doi_text = c.doi.replace("https://doi.org/", "") if c.doi else ""
        doi_html = f'<a href="{html.escape(c.doi)}">{html.escape(doi_text)}</a>' if c.doi else "无 DOI"
        title = f'<a href="{html.escape(c.landing)}">{html.escape(c.title)}</a>' if c.landing else html.escape(c.title)
        abstract_text = c.abstract or "未获取到摘要"
        judgment = (
            f"非推荐；已按用户反馈归入无关/无参考候选。"
            f"筛选原因：{c.reason} "
            f"与课题相关性：{topic_relevance_text(c)} "
            f"排除依据：{c.risk} "
            f"venue：{c.venue_class}。"
        )
        return (
            "<tr class=\"excluded-row\">"
            f"<td>{idx}</td>"
            "<td class=\"excluded-status\">已剔除<br><span class=\"small\">非推荐</span></td>"
            f"<td>{html.escape(c.paper_type)}</td>"
            f"<td class=\"title-cell\">{title}</td>"
            f"<td class=\"abstract-cell\">{html.escape(abstract_text)}</td>"
            f"<td class=\"venue-cell\">{html.escape(c.venue)}</td>"
            f"<td>{html.escape(c.date[:4])}</td>"
            f"<td class=\"doi-cell\">{doi_html}</td>"
            f"<td>{c.relevance}</td>"
            f"<td class=\"judgment-cell\">{html.escape(judgment)}</td>"
            f"{feedback_buttons(paper_id)}"
            "</tr>"
        )

    rows = []
    for idx, c in enumerate(candidates, 1):
        paper_id = f"P{idx:03d}"
        rows.append(render_candidate_row(c, idx, paper_id))
    if not rows:
        rows.append(
            '<tr><td colspan="15">本轮按用户反馈后的严格门槛筛选后，未发现可进入主表的合格论文。'
            '顶刊/强刊若仅为泛无线、泛被动、TENG、自供能或局部放电监测，已转入近似排除，不再凑数推荐。</td></tr>'
        )

    shown_exclusions = []

    query_items = "".join(
        f"<li>{html.escape(q)}：{count}</li>" for q, count in query_counts
    )
    venue_rule = "期刊名单只用于优先级排序和保底提示，不覆盖 A/B/C 机制链硬筛选；中科院分区门槛默认关闭。"

    doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>最近两个月击穿放电无线传感文献雷达</title>
  <style>
    body {{ margin:0; font-family: Arial, "Microsoft YaHei", sans-serif; color:#18212f; background:#fff; }}
    main {{ max-width: 1880px; margin: 0 auto; padding: 24px; }}
    h1 {{ font-size: 24px; margin: 0 0 8px; }}
    h2 {{ font-size: 18px; margin: 26px 0 10px; }}
    p, li {{ color:#536071; line-height:1.55; }}
    .notice, .summary div {{ border:1px solid #d9e0ea; border-radius:6px; padding:10px 12px; background:#f8fafc; }}
    .summary {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap:10px; margin:16px 0 22px; }}
    .table-scroll-top {{ position:sticky; top:0; z-index:8; width:100%; height:16px; overflow-x:auto; overflow-y:hidden; border:1px solid #d9e0ea; border-bottom:0; background:#f8fafc; }}
    .table-scroll-top > div {{ height:1px; }}
    .table-wrap {{ width:100%; overflow-x:auto; border:1px solid #d9e0ea; }}
    table {{ width:100%; min-width:3130px; border-collapse:collapse; table-layout:fixed; font-size:13px; }}
    th, td {{ border:1px solid #d9e0ea; padding:8px; vertical-align:top; word-break:normal; overflow-wrap:anywhere; }}
    th {{ background:#eef3f8; text-align:left; }}
    thead th {{ position:sticky; top:16px; z-index:7; box-shadow:0 1px 0 #d9e0ea, 0 2px 6px rgba(15,23,42,.08); }}
    .title-cell {{ line-height:1.35; }}
    .abstract-cell {{ color:#334155; line-height:1.48; overflow-wrap:normal; }}
    .venue-cell {{ line-height:1.35; }}
    .doi-cell {{ font-size:12px; line-height:1.35; }}
    .judgment-cell {{ line-height:1.45; }}
    .level {{ font-weight:700; }}
    .excluded-row td {{ background:#fbfcfe; }}
    .excluded-status {{ color:#7f1d1d; font-weight:700; }}
    .small {{ font-size:12px; color:#697386; }}
    .feedback button {{ display:inline-block; margin:0 4px 5px 0; border:1px solid #9bb8e8; border-radius:4px; padding:3px 6px; color:#1f5fbf; background:#f7fbff; cursor:pointer; font:inherit; line-height:1.2; }}
    .feedback button[data-action="extremely_related"] {{ --active-bg:#dff8ea; --active-border:#239354; --active-ink:#0f6537; }}
    .feedback button[data-action="related"] {{ --active-bg:#e7f1ff; --active-border:#5f9be3; --active-ink:#1f5fbf; }}
    .feedback button[data-action="reference_only"] {{ --active-bg:#fff3cf; --active-border:#d49b24; --active-ink:#8a5a00; }}
    .feedback button[data-action="downloaded"] {{ --active-bg:#e7f1ff; --active-border:#6fa4e8; --active-ink:#1f5fbf; }}
    .feedback button[data-action="read"], .feedback button[data-action="follow"] {{ --active-bg:#ecfdf3; --active-border:#41a96b; --active-ink:#136c3b; }}
    .feedback button[data-action="irrelevant"], .feedback button[data-action="wrong"], .feedback button[data-action="less"] {{ --active-bg:#fff1f0; --active-border:#e46b61; --active-ink:#a92d25; }}
    .feedback.has-selection button {{ color:#ffffff; background:#111827; border-color:#111827; }}
    .feedback button.active,
    .feedback.has-selection button.active {{ color:var(--active-ink); background:var(--active-bg); border-color:var(--active-border); font-weight:700; box-shadow:0 0 0 2px var(--active-border) inset; }}
    .feedback-status {{ display:block; min-height:18px; margin-top:2px; color:#415064; }}
  </style>
</head>
<body>
<main>
  <h1>最近两个月击穿放电无线传感文献雷达</h1>
  <p>报告 ID：{REPORT_ID}｜生成日期：{TODAY.isoformat()}｜窗口：{START.isoformat()} 至 {TODAY.isoformat()}</p>
  <section class="notice">
    <b>证据边界：</b>本轮为公开 OpenAlex 元数据/摘要初筛，并在配置 API key 时使用 Semantic Scholar、Springer Nature Meta API 与 Elsevier API 补全 DOI 摘要/引用元数据；未下载全文，未绕过访问限制。机制筛选按 A=自供能/摩擦/triboelectric 激发、B=击穿放电/电磁波生成、C=无线通信/传感/可穿戴系统功能执行，优先 A+B/B+C，A+C 降权且仅在 S 级顶刊和 IEEE Transactions 例外。{venue_rule} 纳入结论应在 DOI 源页面复核后再用于正式阅读清单。
  </section>
  <section class="summary">
    <div><b>检索源</b><br>OpenAlex public API + Semantic Scholar API key enrichment + Springer Nature Meta API + Elsevier API；DOI 链接作为下载/源页指针</div>
    <div><b>候选规模</b><br>{sum(count for _, count in query_counts)} 个查询返回计数之和；去重后 {len(candidates) + len(exclusions)} 个候选进入初筛</div>
    <div><b>纳入数量</b><br>推荐主表 {len(candidates)} 篇；已见去重隐藏 {seen_filtered_count} 篇；非推荐样例不展示</div>
    <div><b>优先期刊保底</b><br>本轮主表含 {top_count} 篇 S/A/IEEE 优先 venue 合格候选；目标 3 篇，缺口 {top_shortfall} 篇。期刊名单只加权，不替代机制链判断。</div>
    <div><b>反馈状态</b><br>未配置反馈端点；按钮原地更新，不跳转，可反复修改</div>
  </section>
  <h2>推荐文献（仅含有参考性论文）</h2>
  <div class="table-scroll-top" aria-label="表格横向滚动条"><div></div></div>
  <div class="table-wrap">
  <table>
    <colgroup>
      <col style="width:52px">
      <col style="width:90px">
      <col style="width:140px">
      <col style="width:320px">
      <col style="width:720px">
      <col style="width:180px">
      <col style="width:70px">
      <col style="width:170px">
      <col style="width:110px">
      <col style="width:80px">
      <col style="width:80px">
      <col style="width:420px">
      <col style="width:220px">
      <col style="width:240px">
      <col style="width:240px">
    </colgroup>
    <thead><tr>
      <th>序号</th><th>推荐等级</th><th>文献类型</th><th>标题</th><th>摘要</th><th>期刊/会议</th><th>年份</th><th>DOI</th><th>证据级别</th><th>相关性评分</th><th>创新性评分</th><th>综合判断</th><th>创新点判断</th><th>可借鉴点</th><th>用户反馈</th>
    </tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
  </div>
  <section class="notice">
    <b>非推荐项：</b>按用户要求不再展示非推荐样例；若主表为空，表示本轮严格筛选未确认可推荐论文。
  </section>
  <h2>查询计数</h2>
  <ul>{query_items}</ul>
</main>
<script>
  (function () {{
    document.querySelectorAll(".table-wrap").forEach((wrap) => {{
      const top = wrap.previousElementSibling;
      if (!top || !top.classList.contains("table-scroll-top")) return;
      const spacer = top.firstElementChild;
      let syncing = false;
      const resize = () => {{ spacer.style.width = wrap.scrollWidth + "px"; }};
      const sync = (from, to) => {{
        if (syncing) return;
        syncing = true;
        to.scrollLeft = from.scrollLeft;
        syncing = false;
      }};
      resize();
      if (window.ResizeObserver) {{
        const observer = new ResizeObserver(resize);
        observer.observe(wrap);
        const table = wrap.querySelector("table");
        if (table) observer.observe(table);
      }} else {{
        window.addEventListener("resize", resize);
      }}
      top.addEventListener("scroll", () => sync(top, wrap));
      wrap.addEventListener("scroll", () => sync(wrap, top));
    }});
    const actionLabels = {{extremely_related:"极其相关", related:"相关", reference_only:"可参考", irrelevant:"无关", downloaded:"已下载", read:"已精读", wrong:"误判", follow:"重点跟进", less:"下次少推此类"}};
    const feedbackEndpoint = "";
    document.querySelectorAll(".feedback button").forEach((button) => {{
      button.addEventListener("click", () => {{
        const cell = button.closest(".feedback");
        const group = button.dataset.group || "workflow";
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
    out_dir = RADAR_ARTIFACT_DIR / "reports"
    work_dir = RADAR_ARTIFACT_DIR / "runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    candidates = {}
    query_counts = []
    query_limit = int(os.environ.get("RADAR_QUERY_LIMIT", "0"))
    active_queries = QUERIES[:query_limit] if query_limit > 0 else QUERIES
    for idx, (track, query) in enumerate(active_queries, 1):
        print(f"OpenAlex query {idx}/{len(active_queries)} [{track}]: {query}", flush=True)
        data = openalex_query(query)
        query_counts.append((query, int(data.get("meta", {}).get("count", 0))))
        for work in data.get("results", []):
            key = normalized_key(work)
            if not key:
                continue
            item = candidates.get(key)
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
                    work_type=work.get("type") or "",
                    landing=landing,
                    abstract=abstract,
                    abstract_source=abstract_source,
                    openalex_id=work.get("id") or "",
                )
                candidates[key] = item
            item.queries.add(query)
            item.tracks.add(track)
        time.sleep(0.15)

    s2_stats = semantic_scholar_enrich_candidates(candidates.values())
    cr_stats = crossref_enrich_candidates(candidates.values())
    sn_stats = springer_nature_enrich_candidates(candidates.values())
    els_stats = elsevier_enrich_candidates(candidates.values())

    for candidate in candidates.values():
        classify(candidate)
        apply_quality_gate(candidate)

    seen_index = load_seen_index()
    show_seen = os.environ.get("RADAR_SHOW_SEEN", "").strip().lower() in {"1", "true", "yes"}
    all_items = sorted(
        candidates.values(),
        key=lambda c: (
            c.level == "必读",
            c.level == "建议读",
            c.level == "可参考",
            c.mechanism_pair in {"A+B+C", "B+C", "A+B"},
            venue_priority_rank(c.venue_priority),
            c.relevance,
            c.novelty,
            c.date,
        ),
        reverse=True,
    )

    def eligible(candidate: Candidate) -> bool:
        if candidate.level not in {"必读", "建议读", "可参考"}:
            return False
        if candidate.fit_class not in {"core-chain", "mechanism-support"}:
            if candidate.fit_class not in {"abstract-chain-match", "top-transfer-reference", "top-ac-transfer-reference"}:
                return False
        if candidate.paper_type == "近似但排除":
            return False
        if "review" in candidate.title.lower():
            return False
        if candidate.venue_class == "MDPI low-priority":
            return False
        if not show_seen and is_seen(candidate, seen_index):
            return False
        return True

    included = []
    seen_ids = set()

    def append_candidate(candidate: Candidate):
        key = normalized_key({"display_name": candidate.title, "doi": candidate.doi})
        if key in seen_ids:
            return
        included.append(candidate)
        seen_ids.add(key)

    top_lane = [
        c for c in all_items
        if eligible(c) and c.venue_priority in {"S", "A", "IEEE"}
    ]
    for candidate in top_lane[:3]:
        append_candidate(candidate)

    for candidate in all_items:
        if len(included) >= 12:
            break
        if eligible(candidate):
            append_candidate(candidate)

    included_keys = {id(c) for c in included}
    excluded = [c for c in all_items if id(c) not in included_keys]
    pre_quality_recommended = [
        c for c in all_items
        if c.level in {"必读", "建议读", "可参考"}
        and c.fit_class in {"core-chain", "mechanism-support", "abstract-chain-match", "top-transfer-reference", "top-ac-transfer-reference"}
        and c.paper_type != "近似但排除"
    ]
    seen_filtered = [c for c in pre_quality_recommended if is_seen(c, seen_index)]
    quality_excluded = [c for c in pre_quality_recommended if not quality_allows(c)]
    seen_update = update_seen_index(pre_quality_recommended, REPORT_ID)

    json_path = work_dir / f"openalex_candidates_{TODAY.isoformat()}.json"
    json_path.write_text(
        json.dumps(
            {
                "report_id": REPORT_ID,
                "window": [START.isoformat(), TODAY.isoformat()],
                "query_counts": query_counts,
                "pre_quality_recommended_count": len(pre_quality_recommended),
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
                "crossref_enrichment": cr_stats,
                "springer_nature_enrichment": sn_stats,
                "elsevier_enrichment": els_stats,
                "included": [c.__dict__ | {"queries": sorted(c.queries), "tracks": sorted(c.tracks)} for c in included],
                "excluded": [c.__dict__ | {"queries": sorted(c.queries), "tracks": sorted(c.tracks)} for c in excluded[:30]],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    html_path = out_dir / f"research_paper_radar_openalex_{TODAY.isoformat()}.html"
    render_html.seen_filtered_count = len(seen_filtered)
    render_html(included, excluded, query_counts, html_path)
    print(f"Wrote {html_path}")
    print(f"Wrote {json_path}")
    print(f"Included {len(included)} of {len(candidates)} deduplicated candidates")
    print(f"Pre-quality recommended: {len(pre_quality_recommended)}")
    print(f"Quality excluded: {len(quality_excluded)}")
    print(f"Seen filtered: {len(seen_filtered)}")
    print(f"Seen index: {seen_update['path']} total={seen_update['total']} touched={seen_update['touched']}")
    print(f"CAS partition mode: {CAS_PARTITION_MODE} table={CAS_PARTITION_TABLE}")
    print(
        "Semantic Scholar enrichment: "
        f"available={s2_stats['available']} authenticated={s2_stats['authenticated']} "
        f"checked={s2_stats['checked']} "
        f"filled_abstracts={s2_stats['filled_abstracts']}"
    )
    print(
        "Crossref enrichment: "
        f"available={cr_stats['available']} checked={cr_stats['checked']} "
        f"filled_abstracts={cr_stats['filled_abstracts']}"
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


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
