import os
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path


KEEPALIVE_PATH = Path(".github/radar-keepalive")


def run(*args: str, check: bool = True) -> str:
    completed = subprocess.run(
        args,
        check=check,
        text=True,
        capture_output=True,
    )
    return completed.stdout.strip()


def main() -> None:
    if os.environ.get("GITHUB_EVENT_NAME", "").strip().lower() != "schedule":
        print("Keepalive skipped outside a scheduled run.")
        return
    try:
        threshold_days = max(1, int(os.environ.get("RADAR_KEEPALIVE_DAYS", "45")))
    except ValueError:
        threshold_days = 45
    latest_timestamp = int(run("git", "log", "-1", "--format=%ct") or "0")
    age_days = int((datetime.now(timezone.utc).timestamp() - latest_timestamp) // 86400)
    if age_days < threshold_days:
        print(f"Keepalive not due: latest repository commit is {age_days} days old.")
        return

    KEEPALIVE_PATH.parent.mkdir(parents=True, exist_ok=True)
    KEEPALIVE_PATH.write_text(
        f"Last radar keepalive: {date.today().isoformat()}\n",
        encoding="utf-8",
    )
    run("git", "config", "user.name", "github-actions[bot]")
    run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    run("git", "add", str(KEEPALIVE_PATH))
    message = (
        "chore: keep literature radar schedule active\n\n"
        "CI reason: record lightweight repository activity before GitHub's "
        "60-day scheduled-workflow inactivity limit."
    )
    run("git", "commit", "-m", message)
    run("git", "push")
    print("Published scheduled-workflow keepalive commit.")


if __name__ == "__main__":
    main()
