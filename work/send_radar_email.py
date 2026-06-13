import html
import json
import mimetypes
import os
import re
import smtplib
import ssl
import sys
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path

from radar_state import RADAR_ARTIFACT_DIR


TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off", "skip"}


def env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def env_bool(name: str, default: bool = False) -> bool:
    value = env(name).lower()
    if not value:
        return default
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    return default


def split_addresses(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[;,]", value or "") if item.strip()]


def latest_file(folder: Path, pattern: str) -> Path | None:
    if not folder.exists():
        return None
    files = [path for path in folder.glob(pattern) if path.is_file()]
    if not files:
        return None
    return max(files, key=lambda path: path.stat().st_mtime)


def load_json(path: Path | None) -> dict:
    if not path or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def enabled_state() -> tuple[bool, bool]:
    value = env("RADAR_EMAIL_ENABLED", "auto").lower()
    if value in FALSE_VALUES:
        return False, False
    if value in TRUE_VALUES:
        return True, True

    return not config_errors(required=False), False


def config_errors(required: bool) -> list[str]:
    errors = []
    if not env("RADAR_EMAIL_TO"):
        errors.append("RADAR_EMAIL_TO (recipient address)")
    if not env("SMTP_HOST"):
        errors.append("SMTP_HOST (sender SMTP server)")
    if not (env("RADAR_EMAIL_FROM") or env("SMTP_USERNAME")):
        errors.append("RADAR_EMAIL_FROM or SMTP_USERNAME (sender address/login)")
    if env("SMTP_USERNAME") and not env("SMTP_PASSWORD"):
        errors.append("SMTP_PASSWORD (sender SMTP password/token)")
    return errors


def config_help() -> str:
    return (
        "RADAR_EMAIL_TO is only the recipient address. GitHub Actions still needs a sender "
        "delivery channel to send mail: set SMTP_HOST plus RADAR_EMAIL_FROM or SMTP_USERNAME, "
        "and set SMTP_PASSWORD when SMTP_USERNAME is used. If you only want the GitHub artifact, "
        "set RADAR_EMAIL_ENABLED=0 or run manual workflow with send_email=0."
    )


def recommendation_lines(payload: dict, limit: int = 10) -> list[str]:
    papers = payload.get("recommended") or payload.get("included") or []
    lines = []
    for paper in papers[:limit]:
        title = paper.get("title") or "(untitled)"
        venue = paper.get("venue") or "unknown venue"
        year = (paper.get("date") or paper.get("year") or "")[:4]
        doi = paper.get("doi") or ""
        level = paper.get("level") or paper.get("recommendation") or ""
        suffix = " | ".join(item for item in [venue, year, doi] if item)
        prefix = f"{level}: " if level else ""
        lines.append(f"- {prefix}{title}" + (f" ({suffix})" if suffix else ""))
    if len(papers) > limit:
        lines.append(f"- ... and {len(papers) - limit} more in the attached HTML report.")
    if not lines:
        lines.append("- No recommended papers in this run.")
    return lines


def build_subject(payload: dict) -> str:
    prefix = env("RADAR_EMAIL_SUBJECT_PREFIX", "Research Paper Radar")
    report_id = payload.get("report_id") or "latest"
    recommended = payload.get("recommended_count")
    if recommended is None:
        recommended = len(payload.get("recommended") or payload.get("included") or [])
    return f"{prefix}: {report_id} ({recommended} recommended)"


def build_text_body(payload: dict, report_path: Path, json_path: Path | None) -> str:
    report_id = payload.get("report_id") or report_path.stem
    window = payload.get("window") or []
    recommended = payload.get("recommended_count")
    if recommended is None:
        recommended = len(payload.get("recommended") or payload.get("included") or [])
    top_count = payload.get("top_venue_recommended_count", "")

    parts = [
        "Research Paper Radar report is attached.",
        "",
        f"Report ID: {report_id}",
        f"Window: {' to '.join(window) if isinstance(window, list) else window}",
        f"Recommended: {recommended}",
    ]
    if top_count != "":
        parts.append(f"Top/strong venue recommended: {top_count}")
    parts.extend(
        [
            f"HTML report: {report_path.name}",
            f"JSON result: {json_path.name if json_path else '(not attached)'}",
            "",
            "Recommended papers:",
            *recommendation_lines(payload),
            "",
            "Evidence boundary: metadata and abstracts only; no paid full text was downloaded.",
        ]
    )
    return "\n".join(parts)


def build_html_body(payload: dict, report_path: Path, json_path: Path | None) -> str:
    lines = recommendation_lines(payload)
    report_id = html.escape(str(payload.get("report_id") or report_path.stem))
    window = payload.get("window") or []
    window_text = " to ".join(window) if isinstance(window, list) else str(window)
    recommended = payload.get("recommended_count")
    if recommended is None:
        recommended = len(payload.get("recommended") or payload.get("included") or [])
    items = "".join(f"<li>{html.escape(line[2:] if line.startswith('- ') else line)}</li>" for line in lines)
    json_text = html.escape(json_path.name if json_path else "(not attached)")
    return f"""<!doctype html>
<html>
<body>
  <p>Research Paper Radar report is attached.</p>
  <ul>
    <li><b>Report ID:</b> {report_id}</li>
    <li><b>Window:</b> {html.escape(window_text)}</li>
    <li><b>Recommended:</b> {html.escape(str(recommended))}</li>
    <li><b>HTML report:</b> {html.escape(report_path.name)}</li>
    <li><b>JSON result:</b> {json_text}</li>
  </ul>
  <p><b>Recommended papers</b></p>
  <ul>{items}</ul>
  <p>Evidence boundary: metadata and abstracts only; no paid full text was downloaded.</p>
</body>
</html>"""


def attach_file(message: EmailMessage, path: Path) -> None:
    guessed_type, _ = mimetypes.guess_type(str(path))
    if guessed_type:
        maintype, subtype = guessed_type.split("/", 1)
    elif path.suffix.lower() == ".html":
        maintype, subtype = "text", "html"
    elif path.suffix.lower() == ".json":
        maintype, subtype = "application", "json"
    else:
        maintype, subtype = "application", "octet-stream"

    if maintype == "text":
        content = path.read_text(encoding="utf-8", errors="replace")
        message.add_attachment(content, subtype=subtype, filename=path.name)
    else:
        message.add_attachment(path.read_bytes(), maintype=maintype, subtype=subtype, filename=path.name)


def build_message(report_path: Path, json_path: Path | None, payload: dict) -> EmailMessage:
    to_addresses = split_addresses(env("RADAR_EMAIL_TO"))
    cc_addresses = split_addresses(env("RADAR_EMAIL_CC"))
    from_address = env("RADAR_EMAIL_FROM") or env("SMTP_USERNAME")

    message = EmailMessage()
    message["Subject"] = build_subject(payload)
    message["From"] = from_address
    message["To"] = ", ".join(to_addresses)
    if cc_addresses:
        message["Cc"] = ", ".join(cc_addresses)
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid(domain=(from_address.split("@")[-1] if "@" in from_address else None))

    message.set_content(build_text_body(payload, report_path, json_path))
    message.add_alternative(build_html_body(payload, report_path, json_path), subtype="html")
    attach_file(message, report_path)
    if json_path and env_bool("RADAR_EMAIL_ATTACH_JSON", True):
        attach_file(message, json_path)
    return message


def send_message(message: EmailMessage) -> None:
    host = env("SMTP_HOST")
    use_ssl = env_bool("SMTP_USE_SSL", False)
    port = int(env("SMTP_PORT", "465" if use_ssl else "587"))
    timeout = int(env("SMTP_TIMEOUT_SECONDS", "30"))
    username = env("SMTP_USERNAME")
    password = env("SMTP_PASSWORD")
    use_tls = env_bool("SMTP_USE_TLS", not use_ssl)
    context = ssl.create_default_context()

    if use_ssl:
        server = smtplib.SMTP_SSL(host, port, timeout=timeout, context=context)
    else:
        server = smtplib.SMTP(host, port, timeout=timeout)

    with server:
        server.ehlo()
        if use_tls and not use_ssl:
            server.starttls(context=context)
            server.ehlo()
        if username:
            server.login(username, password)
        recipients = split_addresses(env("RADAR_EMAIL_TO")) + split_addresses(env("RADAR_EMAIL_CC")) + split_addresses(env("RADAR_EMAIL_BCC"))
        server.send_message(message, to_addrs=recipients)


def main() -> int:
    enabled, required = enabled_state()
    if not enabled:
        print("Email disabled or not configured; skipping.")
        return 0

    errors = config_errors(required=required)
    if errors:
        message = "Missing email configuration: " + ", ".join(errors) + ". " + config_help()
        if required:
            print(f"ERROR: {message}", file=sys.stderr)
            return 2
        print(f"Email not configured; skipping. {message}")
        return 0

    report_path = latest_file(RADAR_ARTIFACT_DIR / "reports", "*.html")
    if not report_path:
        print(f"ERROR: no HTML report found under {RADAR_ARTIFACT_DIR / 'reports'}", file=sys.stderr)
        return 3

    json_path = latest_file(RADAR_ARTIFACT_DIR / "runs", "*.json")
    payload = load_json(json_path)
    message = build_message(report_path, json_path, payload)
    send_message(message)
    print(f"Email sent to {env('RADAR_EMAIL_TO')} with report {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
