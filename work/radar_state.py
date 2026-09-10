import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_RADAR_ARTIFACT_DIR = (
    r"D:\PhD\10_vibe项目\research_paper_radar"
    if os.name == "nt"
    else "artifacts/research_paper_radar"
)
RADAR_ARTIFACT_DIR = Path(os.environ.get("RADAR_ARTIFACT_DIR", DEFAULT_RADAR_ARTIFACT_DIR))
RADAR_STATE_DIR = Path(os.environ.get("RADAR_STATE_DIR", str(RADAR_ARTIFACT_DIR / "state")))
SEEN_INDEX_PATH = RADAR_STATE_DIR / "seen_papers.json"
SEEN_INDEX_SEED_PATH = Path(os.environ.get("RADAR_SEEN_SEED_PATH", "data/seen_papers.seed.json"))


def normalize_doi(value: str) -> str:
    value = (value or "").strip().lower()
    value = value.replace("https://doi.org/", "").replace("http://doi.org/", "")
    value = value.replace("doi:", "").strip()
    return value.rstrip(".")


def normalize_title(value: str) -> str:
    value = (value or "").lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def title_hash(value: str) -> str:
    normalized = normalize_title(value)
    if not normalized:
        return ""
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:20]


def candidate_identity(candidate) -> dict:
    doi = normalize_doi(getattr(candidate, "doi", ""))
    hashed_title = title_hash(getattr(candidate, "title", ""))
    key = f"doi:{doi}" if doi else f"title:{hashed_title}"
    return {
        "key": key,
        "doi": doi,
        "title_hash": hashed_title,
    }


def load_seen_index(path: Path = SEEN_INDEX_PATH) -> dict:
    source_path = path
    if not source_path.exists() and SEEN_INDEX_SEED_PATH.exists():
        source_path = SEEN_INDEX_SEED_PATH
    if not source_path.exists():
        return {"version": 1, "updated_at": "", "papers": {}}
    try:
        data = json.loads(source_path.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "updated_at": "", "papers": {}}
    if not isinstance(data, dict):
        return {"version": 1, "updated_at": "", "papers": {}}
    data.setdefault("version", 1)
    data.setdefault("updated_at", "")
    data.setdefault("papers", {})
    return data


def save_seen_index(index: dict, path: Path = SEEN_INDEX_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    index["updated_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def is_seen(candidate, index: dict) -> bool:
    identity = candidate_identity(candidate)
    key = identity["key"]
    if key and key in index.get("papers", {}):
        return True
    doi = identity["doi"]
    hashed_title = identity["title_hash"]
    for entry in index.get("papers", {}).values():
        if doi and entry.get("doi") == doi:
            return True
        if hashed_title and entry.get("title_hash") == hashed_title:
            return True
    return False


def split_unseen(candidates, index: dict) -> tuple[list, list]:
    unseen = []
    seen = []
    for candidate in candidates:
        if is_seen(candidate, index):
            seen.append(candidate)
        else:
            unseen.append(candidate)
    return unseen, seen


def update_seen_index(candidates, report_id: str, path: Path = SEEN_INDEX_PATH) -> dict:
    index = load_seen_index(path)
    papers = index.setdefault("papers", {})
    touched = 0
    for candidate in candidates:
        identity = candidate_identity(candidate)
        key = identity["key"]
        if not key or key == "title:":
            continue
        entry = papers.get(key)
        if entry is None:
            entry = {
                "doi": identity["doi"],
                "title_hash": identity["title_hash"],
                "feedback": "",
            }
            papers[key] = entry
        else:
            entry["doi"] = entry.get("doi") or identity["doi"]
            entry["title_hash"] = entry.get("title_hash") or identity["title_hash"]
            entry.setdefault("feedback", "")
        touched += 1
    save_seen_index(index, path)
    return {
        "path": str(path),
        "total": len(papers),
        "touched": touched,
    }


FEEDBACK_ACTIONS = {
    "extremely_related",
    "related",
    "reference_only",
    "irrelevant",
    "downloaded",
    "read",
    "wrong",
    "follow",
    "less",
}


def feedback_action(entry: dict) -> str:
    feedback = entry.get("feedback", "")
    if isinstance(feedback, dict):
        return str(feedback.get("action", "")).strip()
    return str(feedback or "").strip()


def merge_feedback_events(events: list[dict], path: Path = SEEN_INDEX_PATH) -> dict:
    index = load_seen_index(path)
    papers = index.setdefault("papers", {})
    accepted = 0
    ignored = 0
    for event in events:
        doi = normalize_doi(str(event.get("doi", "")))
        hashed_title = str(event.get("title_hash", "")).strip().lower()
        action = str(event.get("action", "")).strip()
        if action not in FEEDBACK_ACTIONS or (not doi and not hashed_title):
            ignored += 1
            continue
        key = f"doi:{doi}" if doi else f"title:{hashed_title}"
        entry = papers.setdefault(
            key,
            {"doi": doi, "title_hash": hashed_title, "feedback": ""},
        )
        entry["doi"] = entry.get("doi") or doi
        entry["title_hash"] = entry.get("title_hash") or hashed_title
        entry["feedback"] = {
            "action": action,
            "updated_at": str(event.get("timestamp") or event.get("updated_at") or ""),
        }
        accepted += 1
    if accepted:
        save_seen_index(index, path)
    return {
        "path": str(path),
        "accepted": accepted,
        "ignored": ignored,
        "total": len(papers),
    }
