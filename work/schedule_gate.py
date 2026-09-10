import argparse
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from radar_state import RADAR_STATE_DIR


SCHEDULE_STATE_PATH = RADAR_STATE_DIR / "schedule.json"


def parse_positive_int(value: str, default: int) -> int:
    try:
        parsed = int((value or "").strip())
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def load_state(path: Path = SCHEDULE_STATE_PATH) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat((value or "")[:10])
    except ValueError:
        return None


def decision(today: date | None = None) -> dict:
    today = today or date.today()
    trigger = os.environ.get("GITHUB_EVENT_NAME", "manual").strip().lower()
    enabled = os.environ.get("RADAR_SCHEDULE_ENABLED", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }
    interval_days = parse_positive_int(os.environ.get("RADAR_INTERVAL_DAYS", "60"), 60)

    if trigger != "schedule":
        return {
            "should_run": True,
            "reason": f"{trigger or 'manual'} trigger bypasses the schedule gate",
            "interval_days": interval_days,
            "next_run": today.isoformat(),
        }
    if not enabled:
        return {
            "should_run": False,
            "reason": "scheduled radar is disabled by RADAR_SCHEDULE_ENABLED",
            "interval_days": interval_days,
            "next_run": "disabled",
        }

    state = load_state()
    last_run = parse_date(state.get("last_successful_scheduled_run", ""))
    if last_run is None:
        last_run = parse_date(os.environ.get("RADAR_SCHEDULE_INITIAL_LAST_RUN", ""))
    if last_run is None:
        return {
            "should_run": True,
            "reason": "no previous successful scheduled run is recorded",
            "interval_days": interval_days,
            "next_run": today.isoformat(),
        }

    next_run = last_run + timedelta(days=interval_days)
    return {
        "should_run": today >= next_run,
        "reason": (
            f"interval elapsed since {last_run.isoformat()}"
            if today >= next_run
            else f"next run is due on {next_run.isoformat()}"
        ),
        "interval_days": interval_days,
        "next_run": next_run.isoformat(),
    }


def write_github_output(result: dict) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT", "").strip()
    if not output_path:
        return
    with Path(output_path).open("a", encoding="utf-8") as handle:
        for key in ("should_run", "reason", "interval_days", "next_run"):
            value = result[key]
            if isinstance(value, bool):
                value = str(value).lower()
            handle.write(f"{key}={value}\n")


def mark_success(today: date | None = None) -> None:
    trigger = os.environ.get("GITHUB_EVENT_NAME", "manual").strip().lower()
    if trigger != "schedule":
        print("Manual run completed; scheduled cadence was not advanced.")
        return
    today = today or date.today()
    state = load_state()
    state.update(
        {
            "version": 1,
            "last_successful_scheduled_run": today.isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    SCHEDULE_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCHEDULE_STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Marked successful scheduled radar run: {today.isoformat()}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("check", "mark"))
    args = parser.parse_args()
    if args.command == "mark":
        mark_success()
        return
    result = decision()
    write_github_output(result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
