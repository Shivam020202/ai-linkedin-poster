"""Post JSON schema: limits the model is told about, validation, and normalisation."""
from __future__ import annotations

import json
import re

FORMATS = {
    "carousel": (6, 9),
    "single": (1, 1),
    "quote": (1, 1),
    "checklist": (1, 1),
}

# kind -> {field: max chars}. Slide text is a short headline, NOT the post text — the graphic does the talking.
KINDS: dict[str, dict[str, int]] = {
    "cover": {"title": 70, "caption": 110},
    "point": {"title": 60, "caption": 110},
    "quote": {"title": 170, "caption": 80},
    "checklist": {"title": 60, "caption": 110},
    "cta": {"title": 60, "caption": 110},
}
LEGACY_KINDS = {"hook": "cover", "statement": "cover", "problem": "point", "tip": "point", "text": "point",
                "do_dont": "point", "before_after": "point", "myth_reality": "point", "recap": "checklist"}

SCREENS = ["list", "cards", "form", "placeholder_form", "table", "table_cards", "dashboard", "chat", "empty_state",
           "settings", "search", "onboarding", "pricing", "nav_bottom", "cluttered", "product"]
LAYOUTS = ["hero", "bento", "editorial", "asymmetric", "dashboard", "grid"]
COMPONENT_KINDS = ["button", "toggle", "slider", "checkbox", "chip", "avatars", "input", "rating", "tabs", "progress"]
ICON_NAMES = ["search", "menu", "user", "heart", "star", "bell", "gear", "home", "chart", "lock", "eye", "cursor",
              "layers", "grid", "palette", "type", "phone", "monitor", "sparkle", "bolt", "clock", "check", "cross",
              "arrow", "toggle", "chat", "cart", "filter", "bulb", "target", "compass", "puzzle", "ruler", "wand",
              "refresh", "moon", "sun", "image", "play", "globe", "shield", "bookmark", "cube", "brush",
              "accessibility"]

# What the model is told about each graphic (also used to validate).
GRAPHICS = {
    "phone": "phone mock-up of a real app screen. {screen: one of SCREENS, title: <=22 chars, items: up to 6 labels <=20}",
    "browser": "browser window with a web layout. {layout: one of LAYOUTS, title: <=28, items: up to 5 labels <=18}",
    "compare": "two devices side by side, weak vs better. {left_label: <=16, right_label: <=16, left_screen: SCREEN or "
               "LAYOUT, right_screen: SCREEN or LAYOUT, winner: left|right|none, title: <=22, items: labels}",
    "steps": "a process flow. {items: 3-5 of {icon: ICON, label: <=18}}",
    "icons": "tiles of concepts. {items: 3-6 of {icon: ICON, label: <=16}}",
    "timeline": "eras over time. {items: 3-5 of {year: <=6, label: <=20}} — use a year ONLY if it is widely known "
                "and certain (e.g. iOS 7 flat redesign = 2013); otherwise use 'Before', 'Then', 'Early', 'Now'",
    "spectrum": "a trade-off slider. {left: <=16, right: <=16, marker: 0-100, marker_label: <=18}",
    "stat": "one big design value. {value: <=8 e.g. '4.5:1', '44px', '8pt', label: <=30, icon: ICON} — only real, "
            "verifiable design values, never invented statistics",
    "layers": "exploded isometric stack. {items: 3-5 labels <=18, bottom layer first}",
    "components": "floating collage of UI components. {items: 3-6 of COMPONENTS}",
    "palette": "fan of colour chips. {colors: 3-6 of {hex: '#RRGGBB', name: <=12}}",
    "type": "type specimen with metric lines. {sample: <=10 chars, style: serif|sans|display|mono, label: <=22}",
    "checklist": "card with checked items. {items: 3-5 short items <=44}",
    "hero_icon": "big glossy 3D icon with floating satellite icons. {icon: ICON, items: up to 4 ICONs}",
}
# Sensible pictures per category when the model's graphic is missing or broken.
CATEGORY_GRAPHICS = {
    "problem_solving": [{"type": "compare", "left_screen": "cluttered", "right_screen": "cards", "winner": "right"},
                        {"type": "phone", "screen": "settings"}, {"type": "steps"}],
    "misconceptions": [{"type": "compare", "left_label": "Myth", "right_label": "Reality", "winner": "right"},
                       {"type": "spectrum"}, {"type": "hero_icon", "icon": "bulb"}],
    "breaking_norms": [{"type": "browser", "layout": "asymmetric"}, {"type": "browser", "layout": "editorial"},
                       {"type": "hero_icon", "icon": "bolt"}],
    "experiments": [{"type": "steps"}, {"type": "hero_icon", "icon": "wand"}, {"type": "phone", "screen": "onboarding"}],
    "modern_trends": [{"type": "browser", "layout": "bento"}, {"type": "components"}, {"type": "hero_icon", "icon": "sparkle"}],
    "brand_systems": [{"type": "layers"}, {"type": "palette"}, {"type": "components"}],
    "retro_revival": [{"type": "timeline"}, {"type": "components"}, {"type": "type", "style": "serif"}],
}
DEFAULT_GRAPHICS = [{"type": "hero_icon", "icon": "sparkle"}, {"type": "icons"}, {"type": "components"}]

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
    types = []
    for i, slide in enumerate(slides, 1):
        if not isinstance(slide, dict):
            hard.append(f"Slide {i} is not an object.")
            continue
        kind = LEGACY_KINDS.get(slide.get("kind"), slide.get("kind"))
        if kind not in KINDS:
            soft.append(f"Slide {i}: unknown kind '{kind}'. Use one of {sorted(KINDS)}.")
            kind = "point"
        if not _s(slide.get("title")):
            hard.append(f"Slide {i}: missing title.")
        for field, limit in KINDS[kind].items():
            v = slide.get(field)
            if isinstance(v, str) and len(v) > limit:
                soft.append(f"Slide {i} '{field}' is {len(v)} chars; max {limit}. Slide text is a short headline.")
        g = slide.get("graphic")
        if kind in ("cover", "point"):
            if not isinstance(g, dict) or g.get("type") not in GRAPHICS:
                soft.append(f"Slide {i}: needs a 'graphic' whose type is one of {sorted(GRAPHICS)}.")
            else:
                types.append(g["type"])
    if fmt == "carousel" and len(types) >= 4 and len(set(types)) < 3:
        soft.append("Use at least 3 different graphic types across the carousel so slides don't look alike.")

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


def normalize(data: dict, fmt: str, fallback_tags: list[str], category: str = "") -> dict:
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
    for i, slide in enumerate(data.get("slides", [])):
        if not isinstance(slide, dict):
            continue
        slides.append(normalize_slide(slide, i, category))
    lo, hi = FORMATS[fmt]
    data["slides"] = slides[:hi]
    data["format"] = fmt
    data["hook"] = _s(data.get("hook")) or post.split("\n", 1)[0]
    data["alt_text"] = _s(data.get("alt_text"))[:1000]
    data["image_caption"] = _s(data.get("image_caption"))
    return data


def _str(v, limit) -> str:
    return _trim(strip_emoji(v if isinstance(v, str) else str(v if v is not None else "")), limit)


def _icon(v, default="sparkle") -> str:
    v = str(v or "").strip().lower()
    return v if v in ICON_NAMES else default


def fallback_graphic(category: str, i: int) -> dict:
    options = CATEGORY_GRAPHICS.get(category, DEFAULT_GRAPHICS)
    return dict(options[i % len(options)])


def normalize_graphic(g, category: str = "", i: int = 0) -> dict:
    """Clamp a model-provided graphic spec to what the renderer supports; fall back if unusable."""
    if not isinstance(g, dict) or g.get("type") not in GRAPHICS:
        return fallback_graphic(category, i)
    t = g["type"]
    out: dict = {"type": t}
    items = g.get("items") if isinstance(g.get("items"), list) else []
    if t == "phone":
        out.update(screen=g.get("screen") if g.get("screen") in SCREENS else "list", title=_str(g.get("title"), 22),
                   items=[_str(x, 20) for x in items[:6]])
    elif t == "browser":
        out.update(layout=g.get("layout") if g.get("layout") in LAYOUTS else "hero", title=_str(g.get("title"), 28),
                   items=[_str(x, 18) for x in items[:5]])
    elif t == "compare":
        ok = SCREENS + LAYOUTS
        out.update(left_label=_str(g.get("left_label") or "Before", 16), right_label=_str(g.get("right_label") or "After", 16),
                   left_screen=g.get("left_screen") if g.get("left_screen") in ok else "cluttered",
                   right_screen=g.get("right_screen") if g.get("right_screen") in ok else "cards",
                   winner=g.get("winner") if g.get("winner") in ("left", "right", "none") else "right",
                   title=_str(g.get("title"), 22), items=[_str(x, 20) for x in items[:6]])
        if out["left_screen"] == out["right_screen"]:  # identical pictures compare nothing: make the loser look weak
            weak = {"table_cards": "table", "form": "placeholder_form"}.get(out["right_screen"], "cluttered")
            loser = "left_screen" if out["winner"] != "left" else "right_screen"
            out[loser] = weak if weak != out[loser] else "table"
    elif t in ("steps", "icons"):
        n = 5 if t == "steps" else 6
        out["items"] = [{"icon": _icon(x.get("icon")), "label": _str(x.get("label"), 18 if t == "steps" else 16)}
                        if isinstance(x, dict) else {"icon": "sparkle", "label": _str(x, 16)} for x in items[:n]]
        if len(out["items"]) < 2:
            return fallback_graphic(category, i)
    elif t == "timeline":
        out["items"] = [{"year": _str(x.get("year"), 6), "label": _str(x.get("label"), 20)}
                        for x in items[:5] if isinstance(x, dict)]
        if len(out["items"]) < 2:
            return fallback_graphic(category, i)
    elif t == "spectrum":
        try:
            marker = max(0, min(100, float(g.get("marker", 60))))
        except (TypeError, ValueError):
            marker = 60
        out.update(left=_str(g.get("left") or "Less", 16), right=_str(g.get("right") or "More", 16), marker=marker,
                   marker_label=_str(g.get("marker_label") or "Sweet spot", 18))
    elif t == "stat":
        out.update(value=_str(g.get("value") or "8pt", 8), label=_str(g.get("label"), 30), icon=_icon(g.get("icon"), "ruler"))
    elif t == "layers":
        out["items"] = [_str(x, 18) for x in items[:5]] or ["Tokens", "Components", "Patterns", "Pages"]
    elif t == "components":
        out["items"] = [x for x in items if x in COMPONENT_KINDS][:6]
    elif t == "palette":
        cols = []
        for c in (g.get("colors") or [])[:6]:
            if isinstance(c, dict) and re.fullmatch(r"#[0-9a-fA-F]{6}", str(c.get("hex", "")).strip()):
                cols.append({"hex": c["hex"].strip(), "name": _str(c.get("name"), 12)})
        out["colors"] = cols
    elif t == "type":
        out.update(sample=_str(g.get("sample") or "Aa", 10),
                   style=g.get("style") if g.get("style") in ("serif", "sans", "display", "mono") else "sans",
                   label=_str(g.get("label"), 22))
    elif t == "checklist":
        out["items"] = [_str(x, 44) for x in items[:5] if str(x).strip()]
    elif t == "hero_icon":
        out.update(icon=_icon(g.get("icon")), items=[_icon(x) for x in items[:4] if str(x).lower() in ICON_NAMES])
    return out


def normalize_slide(slide: dict, i: int, category: str = "") -> dict:
    """Clean one slide. Old-style slides (hook/tip/do_dont…) are converted to the graphic-first format."""
    kind = slide.get("kind", "point")
    graphic = slide.get("graphic")
    caption = slide.get("caption")
    if kind in LEGACY_KINDS:
        if kind in ("do_dont", "before_after", "myth_reality"):
            left, right = {"do_dont": ("dont", "do"), "before_after": ("before", "after"),
                           "myth_reality": ("myth", "reality")}[kind]
            caption = caption or slide.get(right)
            graphic = graphic or {"type": "compare", "left_label": left.capitalize().replace("Dont", "Don't"),
                                  "right_label": right.capitalize(), "winner": "right"}
        elif kind == "recap":
            graphic = graphic or {"type": "checklist", "items": slide.get("items") or []}
        caption = caption or slide.get("body")
        kind = LEGACY_KINDS[kind]
    if kind not in KINDS:
        kind = "point"
    limits = KINDS[kind]
    clean = {"kind": kind, "title": _str(slide.get("title"), limits["title"]),
             "caption": _str(caption or slide.get("body"), limits["caption"])}
    if kind == "checklist":
        items = slide.get("items") or (graphic or {}).get("items") or []
        clean["graphic"] = {"type": "checklist", "items": [_str(x, 44) for x in items[:5] if str(x).strip()]}
    elif kind in ("cover", "point") or graphic:
        clean["graphic"] = normalize_graphic(graphic, category, i)
    return clean


def strip_emoji(text: str) -> str:
    """Images use text fonts without emoji glyphs, so emoji would render as boxes."""
    return re.sub(r" {2,}", " ", EMOJI.sub("", text.replace("️", ""))).strip()


def full_post_text(data: dict) -> str:
    return data["post_text"].strip() + "\n\n" + " ".join(data.get("hashtags", []))
