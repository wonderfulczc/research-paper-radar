import json
import os
import urllib.request
from pathlib import Path

from radar_state import merge_feedback_events


def read_source(source: str) -> str:
    if source.startswith(("https://", "http://")):
        headers = {"User-Agent": "research-paper-radar feedback sync"}
        token = os.environ.get("RADAR_FEEDBACK_READ_TOKEN", "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(source, headers=headers)
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8")
    return Path(source).read_text(encoding="utf-8")


def parse_events(raw: str) -> list[dict]:
    raw = raw.strip()
    if not raw:
        return []
    if raw.startswith("[") or raw.startswith("{"):
        data = json.loads(raw)
        if isinstance(data, dict):
            data = data.get("events", [])
        if not isinstance(data, list):
            raise ValueError("feedback JSON must be a list or an object with an events list")
        return [event for event in data if isinstance(event, dict)]
    events = []
    for line in raw.splitlines():
        line = line.strip()
        if line:
            event = json.loads(line)
            if isinstance(event, dict):
                events.append(event)
    return events


def main() -> None:
    source = os.environ.get("RADAR_FEEDBACK_SOURCE_URL", "").strip()
    if not source:
        print("Feedback sync skipped: RADAR_FEEDBACK_SOURCE_URL is not configured.")
        return
    events = parse_events(read_source(source))
    result = merge_feedback_events(events)
    print(
        "Feedback sync: "
        f"events={len(events)} accepted={result['accepted']} ignored={result['ignored']} "
        f"state={result['path']}"
    )


if __name__ == "__main__":
    main()
