import re

from radar_state import candidate_identity, feedback_action


POSITIVE_ACTIONS = {"extremely_related", "related"}
NEGATIVE_ACTIONS = {"irrelevant", "wrong", "less"}
STOPWORDS = {
    "about",
    "based",
    "effect",
    "enhanced",
    "for",
    "from",
    "high",
    "method",
    "novel",
    "self",
    "system",
    "the",
    "this",
    "using",
    "with",
}


def title_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", (value or "").lower())
        if len(token) >= 4 and token not in STOPWORDS
    }


def feedback_examples(candidates, seen_index: dict) -> list[tuple[object, str]]:
    papers = seen_index.get("papers", {})
    examples = []
    for candidate in candidates:
        identity = candidate_identity(candidate)
        entry = papers.get(identity["key"])
        if not entry:
            continue
        action = feedback_action(entry)
        if action in POSITIVE_ACTIONS | NEGATIVE_ACTIONS:
            examples.append((candidate, action))
    return examples


def similarity(left, right) -> float:
    score = 0.0
    if left.mechanism_pair and left.mechanism_pair == right.mechanism_pair:
        score += 0.35
    if left.venue and left.venue.lower() == right.venue.lower():
        score += 0.25
    left_tokens = title_tokens(left.title)
    right_tokens = title_tokens(right.title)
    union = left_tokens | right_tokens
    if union:
        score += 0.4 * len(left_tokens & right_tokens) / len(union)
    return score


def apply_feedback_learning(candidates, seen_index: dict) -> dict:
    examples = feedback_examples(candidates, seen_index)
    adjusted = 0
    for candidate in candidates:
        if candidate.level == "exclude":
            continue
        identity = candidate_identity(candidate)
        if feedback_action(seen_index.get("papers", {}).get(identity["key"], {})):
            continue
        positive = 0.0
        negative = 0.0
        for example, action in examples:
            match = similarity(candidate, example)
            if action in POSITIVE_ACTIONS:
                positive = max(positive, match)
            elif action in NEGATIVE_ACTIONS:
                negative = max(negative, match)
        delta = 0
        note = ""
        if negative >= 0.85 and negative > positive:
            candidate.level = "exclude"
            delta = -3
            note = "反馈学习：与已标记无关/误判论文近乎同类，本轮排除。"
        elif negative >= 0.65 and negative > positive:
            delta = -2
            note = "反馈学习：与已标记无关/误判论文高度相似，相关性降权。"
        elif negative >= 0.45 and negative > positive:
            delta = -1
            note = "反馈学习：与负反馈样例存在相似机制或题名线索，轻度降权。"
        elif positive >= 0.65 and positive > negative:
            delta = 1
            note = "反馈学习：与极其相关/相关样例高度相似，相关性加权。"
        if not delta:
            continue
        candidate.relevance = max(0, min(10, candidate.relevance + delta))
        if candidate.relevance < 6:
            candidate.level = "exclude"
        elif candidate.level == "可参考" and candidate.relevance >= 7:
            candidate.level = "建议读"
        candidate.reason = f"{candidate.reason} {note}".strip()
        adjusted += 1
    return {"examples": len(examples), "adjusted": adjusted}
