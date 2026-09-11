import json
import os
import re
import urllib.error
import urllib.request


def _enabled() -> bool:
    return os.environ.get("RADAR_TRANSLATE_ABSTRACTS", "0").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _needs_translation(value: str) -> bool:
    value = (value or "").strip()
    if not value:
        return False
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", value))
    return chinese_chars < max(8, len(value) // 5)


def translate_abstracts(candidates) -> dict:
    """Translate only final report abstracts through DeepL, preserving originals."""
    candidates = list(candidates)
    api_key = os.environ.get("DEEPL_API_KEY", "").strip()
    stats = {
        "enabled": _enabled(),
        "available": bool(api_key),
        "requested": 0,
        "translated": 0,
        "error": "",
    }
    if not stats["enabled"] or not api_key:
        return stats

    for candidate in candidates:
        if (candidate.abstract or "").strip() and not _needs_translation(candidate.abstract):
            candidate.abstract_zh = candidate.abstract
    translatable = [candidate for candidate in candidates if _needs_translation(candidate.abstract)]
    if not translatable:
        return stats

    endpoint = os.environ.get("DEEPL_API_URL", "").strip()
    if not endpoint:
        endpoint = (
            "https://api-free.deepl.com/v2/translate"
            if api_key.endswith(":fx")
            else "https://api.deepl.com/v2/translate"
        )
    body = json.dumps(
        {
            "text": [candidate.abstract for candidate in translatable],
            "source_lang": "EN",
            "target_lang": "ZH-HANS",
            "preserve_formatting": True,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={
            "Authorization": f"DeepL-Auth-Key {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "research-paper-radar abstract translator",
        },
        method="POST",
    )
    stats["requested"] = len(translatable)
    try:
        timeout = int(os.environ.get("DEEPL_TIMEOUT_SECONDS", "30"))
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        translations = payload.get("translations", [])
        for candidate, translation in zip(translatable, translations):
            translated = str(translation.get("text", "")).strip()
            if translated:
                candidate.abstract_zh = translated
                stats["translated"] += 1
    except (TimeoutError, urllib.error.URLError, OSError, ValueError, json.JSONDecodeError) as exc:
        stats["error"] = f"{type(exc).__name__}: {exc}"
    return stats
