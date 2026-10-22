"""Post JSON schema: limits the model is told about, validation, and normalisation."""
from __future__ import annotations

import json
import re

FORMATS = {
    "carousel": (7, 9),
    "single": (1, 1),
    "quote": (1, 1),
    "checklist": (1, 1),
}

# kind -> {field: max chars}; the model sees these limits in the prompt.
KINDS: dict[str, dict[str, int]] = {
    "hook": {"title": 80, "body": 120},
    "problem": {"title": 60, "body": 220},
    "tip": {"title": 60, "body": 220},
    "text": {"title": 60, "body": 220},
    "recap": {"title": 60, "items": 60},
    "cta": {"title": 60, "body": 140},
    "statement": {"title": 110, "body": 160},
    "do_dont": {"title": 60, "do": 110, "dont": 110},
    "before_after": {"title": 60, "before": 110, "after": 110},
    "myth_reality": {"title": 60, "myth": 120, "reality": 160},
    "quote": {"title": 170, "body": 80},
    "checklist": {"title": 60, "items": 70},
}
REQUIRED = {
    "do_dont": ("do", "dont"), "before_after": ("before", "after"),
    "myth_reality": ("myth", "reality"), "checklist": ("items",), "recap": ("items",),
}

# Illustrations the image engine can draw (see images/visuals.py).
VISUALS = {
    "none": "no illustration",
    "grid8": "8-pt spacing grid with a card snapped to it",
    "spacing": "spacing guides between stacked elements (8/16/24/32)",
    "type_scale": "type specimen showing a size scale",
    "contrast": "colour contrast pass/fail swatches with real ratios",
    "buttons": "weak vs strong button (hierarchy, padding, contrast)",
    "form_field": "input with label above, helper text and error state",
    "card": "simple UI card mock-up (image, title, text, button)",
    "hierarchy": "wireframe showing heading > subheading > body",
    "touch_target": "small icon vs 48px touch target",
    "swatches": "brand colour palette swatches",
    "alignment": "messy vs aligned left edge",
    "empty_state": "empty-state mock-up with illustration placeholder and CTA",
    "checklist": "checkbox list illustration",
}

BANNED = [
    "in today's fast-paced world", "game-changer", "game changer", "unlock the power", "delve",
    "elevate your", "in the ever-evolving", "let's dive in", "buckle up", "synergy", "leverage",
    "revolutionize", "it's not just", "unleash",
]
FABRICATION = [
    r"\bstudies (show|have shown|found)\b", r"\bresearch (shows|has shown|found|suggests)\b",
    r"\baccording to (a|an|the) (study|survey|report)\b", r"\b\d{1,3}(\.\d+)?\s?% of (users|people|designers|visitors|customers)\b",
    r"\ba (recent )?(study|survey) (by|from|of)\b",
]
EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF]")


class ValidationError(Exception):
    def __init__(self, errors: list[str], hard: bool):
        super().__init__("; ".join(errors))
        self.errors = errors
        self.hard = hard


def parse_json(raw: str) -> dict:
    """Parse model output, tolerating ```json fences or prose around the object."""
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    if not text.startswith("{"):
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1:
            raise ValidationError(["Response was not a JSON object."], hard=True)
        text = text[start:end + 1]
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValidationError([f"Invalid JSON: {exc}"], hard=True) from None
    if not isinstance(data, dict):
        raise ValidationError(["Top level must be a JSON object."], hard=True)
    return data


def _s(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def validate(data: dict, fmt: str, length: tuple[int, int] | None = None) -> tuple[list[str], list[str]]:
    """Return (hard_errors, soft_errors). Hard errors make the post unusable."""
    hard, soft = [], []
    for key in ("hook", "post_text", "alt_text"):
        if not _s(data.get(key)):
            hard.append(f"Missing or empty '{key}'.")
    slides = data.get("slides")
    if not isinstance(slides, list) or not slides:
        hard.append("'slides' must be a non-empty list.")
        return hard, soft
    lo, hi = FORMATS[fmt]
    if not lo <= len(slides) <= hi:
        hard.append(f"Format '{fmt}' needs {lo}–{hi} slides, got {len(slides)}.")
    for i, slide in enumerate(slides, 1):
        if not isinstance(slide, dict):
            hard.append(f"Slide {i} is not an object.")
            continue
        kind = slide.get("kind")
        if kind not in KINDS:
            hard.append(f"Slide {i}: unknown kind '{kind}'. Use one of {sorted(KINDS)}.")
            continue
        if not _s(slide.get("title")):
            hard.append(f"Slide {i}: missing title.")
        for field in REQUIRED.get(kind, ()):
            if not slide.get(field):
                hard.append(f"Slide {i} ({kind}): missing '{field}'.")
        for field, limit in KINDS[kind].items():
            values = slide.get(field) if field == "items" else [slide.get(field)]
            for v in values or []:
                if isinstance(v, str) and len(v) > limit:
                    soft.append(f"Slide {i} '{field}' is {len(v)} chars; max {limit}.")
        if slide.get("visual") and slide["visual"] not in VISUALS:
            soft.append(f"Slide {i}: unknown visual '{slide['visual']}'.")

    post = _s(data.get("post_text"))
    lo_len, hi_len = length or (900, 1300)
    n = len(post)
    # small tolerance either side before asking the model to fix it
    if post and not lo_len - 100 <= n <= hi_len + 150:
        soft.append(f"post_text is {n} characters; it must be {lo_len}–{hi_len}.")
    if post and len(post.split("\n", 1)[0]) > 140:
        soft.append("The first line (hook) must be under ~120 characters.")
    emojis = EMOJI.findall(post)
    if len(emojis) > 2:
        soft.append(f"Use at most 2 emoji (found {len(emojis)}).")
    lower = post.lower()
    for phrase in BANNED:
        if phrase in lower:
            soft.append(f"Remove the cliché '{phrase}'.")
    for pattern in FABRICATION:
        match = re.search(pattern, post, re.I)
        if match:
            soft.append(f"'{match.group(0)}' looks like an unverifiable statistic/study — "
                        "remove it or rephrase as your own experience.")
    tags = data.get("hashtags")
    if not isinstance(tags, list) or not 3 <= len(tags) <= 4:
        soft.append("Provide 3–4 hashtags.")
    return hard, soft


def _trim(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit - 1].rsplit(" ", 1)[0].rstrip(",;:—-")
    return cut + "…"


def normalize(data: dict, fmt: str, fallback_tags: list[str]) -> dict:
    """Clamp lengths, tidy hashtags and emoji so a 'soft-invalid' post is still usable."""
    post = _s(data.get("post_text"))
    # pull hashtag lines off the end of the body into the hashtag list
    lines = post.rstrip().split("\n")
    tags = [t for t in (data.get("hashtags") or []) if isinstance(t, str)]
    while lines and re.fullmatch(r"(\s*#\w+\s*)+", lines[-1]):
        tags = re.findall(r"#\w+", lines.pop()) + tags
    post = "\n".join(lines).strip()
    # max 2 emoji: drop the extras
    count = 0

    def keep(m):
        nonlocal count
        count += 1
        return m.group(0) if count <= 2 else ""
    post = re.sub(r" {2,}", " ", EMOJI.sub(keep, post))

    clean_tags = []
    for t in tags + fallback_tags:
        t = "#" + re.sub(r"[^\w]", "", t.lstrip("#"))
        if len(t) > 1 and t.lower() not in {c.lower() for c in clean_tags}:
            clean_tags.append(t)
    data["post_text"] = post
    data["hashtags"] = clean_tags[:4] if len(clean_tags) >= 3 else clean_tags

    slides = []
    seen_visuals: set[str] = set()
    for slide in data.get("slides", []):
        kind = slide.get("kind", "text")
        limits = KINDS.get(kind, KINDS["text"])
        visual = slide.get("visual") if slide.get("visual") in VISUALS else "none"
        if visual in seen_visuals:
            visual = "none"  # the same diagram twice in a carousel looks lazy
        seen_visuals.add(visual) if visual != "none" else None
        clean = {"kind": kind, "visual": visual}
        for field, limit in limits.items():
            if field == "items":
                items = [i for i in (slide.get("items") or []) if isinstance(i, str) and i.strip()]
                clean["items"] = [_trim(strip_emoji(i), limit) for i in items[:6]]
            else:
                clean[field] = _trim(strip_emoji(_s(slide.get(field))), limit)
        slides.append(clean)
    lo, hi = FORMATS[fmt]
    data["slides"] = slides[:hi]
    data["format"] = fmt
    data["hook"] = _s(data.get("hook")) or post.split("\n", 1)[0]
    data["alt_text"] = _s(data.get("alt_text"))[:1000]
    data["image_caption"] = _s(data.get("image_caption"))
    return data


def strip_emoji(text: str) -> str:
    """Images use text fonts without emoji glyphs, so emoji would render as boxes."""
    return re.sub(r" {2,}", " ", EMOJI.sub("", text.replace("️", ""))).strip()


def full_post_text(data: dict) -> str:
    return data["post_text"].strip() + "\n\n" + " ".join(data.get("hashtags", []))
