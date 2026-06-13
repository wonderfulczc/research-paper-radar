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
SMTP_PROVIDER_DEFAULTS = {
    "qq": {"host": "smtp.qq.com", "port": "465", "use_ssl": True, "use_tls": False},
    "163": {"host": "smtp.163.com", "port": "465", "use_ssl": True, "use_tls": False},
    "gmail": {"host": "smtp.gmail.com", "port": "587", "use_ssl": False, "use_tls": True},
    "outlook": {"host": "smtp.office365.com", "port": "587", "use_ssl": False, "use_tls": True},
}


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


def env_bool_optional(name: str) -> bool | None:
    value = env(name).lower()
    if not value:
        return None
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    return None


def sender_address() -> str:
    return env("SMTP_USERNAME") or env("RADAR_EMAIL_FROM")


def sender_provider() -> str:
    explicit = env("SMTP_PROVIDER").lower()
    aliases = {
        "qqmail": "qq",
        "qq.com": "qq",
        "foxmail": "qq",
        "foxmail.com": "qq",
        "163.com": "163",
        "126.com": "163",
        "yeah.net": "163",
        "google": "gmail",
        "gmail.com": "gmail",
        "office365": "outlook",
        "hotmail": "outlook",
        "hotmail.com": "outlook",
        "live.com": "outlook",
        "outlook.com": "outlook",
    }
    if explicit:
        return aliases.get(explicit, explicit)

    address = sender_address().lower()
    if "@" not in address:
        return ""
    domain = address.rsplit("@", 1)[-1]
    return aliases.get(domain, "")


def address_domain(value: str) -> str:
    if "@" not in value:
        return ""
    return value.rsplit("@", 1)[-1].lower()


def smtp_defaults() -> dict:
    return SMTP_PROVIDER_DEFAULTS.get(sender_provider(), {})


def effective_smtp_host() -> str:
    return env("SMTP_HOST") or str(smtp_defaults().get("host", ""))


def effective_smtp_use_ssl() -> bool:
    explicit = env_bool_optional("SMTP_USE_SSL")
    if explicit is not None:
        return explicit
    default = smtp_defaults().get("use_ssl")
    if default is not None:
        return bool(default)
    return False


def effective_smtp_use_tls(use_ssl: bool) -> bool:
    explicit = env_bool_optional("SMTP_USE_TLS")
    if explicit is not None:
        return explicit
    default = smtp_defaults().get("use_tls")
    if default is not None:
        return bool(default)
    return not use_ssl


def effective_smtp_port(use_ssl: bool) -> int:
    value = env("SMTP_PORT") or str(smtp_defaults().get("port", ""))
    return int(value or ("465" if use_ssl else "587"))


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
    if not effective_smtp_host():
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
        "set RADAR_EMAIL_ENABLED=0 or run manual workflow with send_email=0. For QQ Mail sender "
        "to a 163 recipient, use SMTP_PROVIDER=qq or SMTP_HOST=smtp.qq.com, SMTP_PORT=465, "
        "SMTP_USE_SSL=1, SMTP_USE_TLS=0, SMTP_USERNAME=<your QQ email>, and a QQ SMTP authorization "
        "code as SMTP_PASSWORD."
    )


def describe_email_config() -> str:
    use_ssl = effective_smtp_use_ssl()
    use_tls = effective_smtp_use_tls(use_ssl)
    sender = sender_address()
    parts = [
        f"recipient_configured={bool(env('RADAR_EMAIL_TO'))}",
        f"from_configured={bool(env('RADAR_EMAIL_FROM'))}",
        f"username_configured={bool(env('SMTP_USERNAME'))}",
        f"password_configured={bool(env('SMTP_PASSWORD'))}",
        f"sender_domain={address_domain(sender) or '(unknown)'}",
        f"provider={sender_provider() or '(none)'}",
        f"host={effective_smtp_host() or '(missing)'}",
        f"port={effective_smtp_port(use_ssl)}",
        f"use_ssl={use_ssl}",
        f"use_tls={use_tls}",
    ]
    return "Email config: " + ", ".join(parts)


def smtp_error_text(exc: BaseException) -> str:
    if isinstance(exc, smtplib.SMTPResponseException):
        detail = exc.smtp_error
        if isinstance(detail, bytes):
            detail = detail.decode("utf-8", errors="replace")
        return f"{exc.smtp_code} {detail}".strip()
    return str(exc)


def send_failure_hint(exc: BaseException) -> str:
    provider = sender_provider()
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        if provider == "qq":
            return (
                "QQ/Foxmail authentication failed. Use the SMTP authorization code, "
                "not the web login password; set SMTP_USERNAME to the full sender address "
                "(for example name@foxmail.com), and keep RADAR_EMAIL_FROM the same as "
                "SMTP_USERNAME unless you know the sender alias is allowed."
            )
        return "SMTP authentication failed. Check SMTP_USERNAME and SMTP_PASSWORD/token."
    if isinstance(exc, smtplib.SMTPConnectError):
        return "SMTP connection failed. Check SMTP_HOST, SMTP_PORT, SMTP_USE_SSL and SMTP_USE_TLS."
    if isinstance(exc, ssl.SSLError):
        return "SMTP SSL/TLS failed. For QQ/Foxmail use port 465 with SMTP_USE_SSL=1 and SMTP_USE_TLS=0."
    if isinstance(exc, TimeoutError):
        return "SMTP connection timed out. Check host/port or try again later."
    if isinstance(exc, smtplib.SMTPSenderRefused):
        return "SMTP sender was refused. Make RADAR_EMAIL_FROM match SMTP_USERNAME for QQ/Foxmail."
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return "SMTP recipient was refused. Check RADAR_EMAIL_TO."
    return "SMTP send failed. Check the email configuration and provider restrictions."


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
    host = effective_smtp_host()
    use_ssl = effective_smtp_use_ssl()
    port = effective_smtp_port(use_ssl)
    timeout = int(env("SMTP_TIMEOUT_SECONDS", "30"))
    username = env("SMTP_USERNAME")
    password = env("SMTP_PASSWORD")
    use_tls = effective_smtp_use_tls(use_ssl)
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
        print(describe_email_config())
        return 0

    print(describe_email_config())
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
    try:
        send_message(message)
    except (smtplib.SMTPException, OSError, TimeoutError, ssl.SSLError) as exc:
        print(f"ERROR: {send_failure_hint(exc)} Detail: {smtp_error_text(exc)}", file=sys.stderr)
        return 4
    print(f"Email sent to {env('RADAR_EMAIL_TO')} with report {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
