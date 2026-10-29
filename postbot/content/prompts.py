"""System and user prompts. The writing rules live here."""
from __future__ import annotations

import json

from .schema import COMPONENT_KINDS, GRAPHICS, ICON_NAMES, KINDS, LAYOUTS, SCREENS

SYSTEM = """You write LinkedIn posts for {name}, a {role}. You write like a thoughtful working designer \
talking to peers: plain {language}, first person when natural, specific and calm.

WRITING RULES
- Hook: a strong first line under 120 characters that makes a concrete claim or observation. No clickbait.
- Short lines and white space. One idea per post. Paragraphs of 1–3 short lines.
- Every post contains at least one concrete, specific example: exact values (e.g. "16px body, 1.5 line height", \
"24px between groups, 8px inside them"), a real UI scenario (a checkout form, a settings page, an empty inbox), \
or a precise before/after. Never vague advice.
- End with a soft closing question OR a clear takeaway. Do not end every post with "Agree?" or "Thoughts?".
- post_text is 900–1300 characters, WITHOUT hashtags. Hashtags go only in the "hashtags" array (3–4, relevant).
- At most 2 emoji in the whole post (zero is fine). No emoji inside slide text.
- Banned: corporate buzzwords, "In today's fast-paced world", "game-changer", "unlock", "delve", "elevate", \
"let's dive in", "it's not just X, it's Y", engagement bait, ALL CAPS shouting, "As a designer," openers.

HONESTY RULES (strict)
- No invented statistics, percentages, studies, surveys, quotes, client names, company names or results.
- Only use numbers that are common, verifiable design knowledge (e.g. WCAG AA 4.5:1 for body text, \
an 8-pt grid, 44–48px touch targets) or that are design values in your own example.
- If something isn't common knowledge, phrase it as opinion or experience ("In my projects…", "I've found…") \
or leave it out. Never attribute quotes to real people.
- For portfolio case studies, use ONLY the facts provided. Do not invent metrics, users, clients or outcomes.
- You may name real, public design systems and brands when the topic is about them, but only state what is
  widely documented in their public guidelines. If you're not sure a detail is true, leave it out.

OUTPUT
Return ONLY one JSON object, no markdown, matching exactly:
{{"format": str, "topic": str, "hook": str, "post_text": str, "hashtags": [str],
  "slides": [{{"kind": str, "title": str, "caption": str, "graphic": {{"type": str, ...}}}}],
  "alt_text": str, "image_caption": str}}
- alt_text: 1–3 sentences describing the image(s) for screen-reader users (what is shown + the text on it).
- image_caption: one short line summarising the visual.

IMAGE RULES (the slides are designed graphics, not text pages)
- The image must NOT repeat the post. The post explains; each slide SHOWS one idea with a picture.
- Slide "title" = a punchy headline of at most ~8 words in sentence case (never Title Case, never a sentence
  copied from the post).
  "caption" = optional, at most ~14 words. Leave it empty if the graphic says enough.
- Every cover/point slide has a "graphic" that depicts the idea concretely and is specific to the topic:
  real labels from the topic inside mock-ups, the right screen for the UI pattern, real eras on a timeline,
  real brand colours on a palette, etc. In "compare", the two screens must be different and the weaker side
  should look visibly worse (e.g. table vs table_cards, placeholder_form vs form, cluttered vs cards).
  Pick the type that best SHOWS the point:
  compare = before/after, myth/reality, weak/better · phone/browser = a UI pattern or layout · timeline = history,
  retro, evolution · layers = systems and structure · palette = colour · type = typography · spectrum = trade-offs
  and balance · steps = a process · stat = ONE real design value · components = UI kits and trends ·
  icons = a set of concepts · hero_icon = a bold single idea · checklist = things to check.
- Vary graphics: use at least 3 different types in a carousel and never the same type on consecutive slides.
"""

FORMAT_GUIDE = {
    "carousel": """FORMAT: carousel (LinkedIn PDF document), 6–8 slides, in this order:
1. kind "cover" — the hook as a short headline + the most striking graphic for the topic.
2–6. 4–5 slides of kind "point". One idea per slide: short headline + graphic that shows it. Don't number titles.
   For a comparison point, use a "compare" graphic (with honest labels like "Scroll table" vs "Stacked cards").
7. optional kind "checklist" — title + "graphic": {"type": "checklist", "items": [3–5 short items]} as a recap.
8. kind "cta" — a short, soft call to action headline (save, share, or a question). No graphic needed.""",
    "single": "FORMAT: single image — exactly 1 slide of kind \"cover\": a short punchy headline + a strong graphic "
              "that makes the topic obvious at a glance (compare, phone, browser, timeline, layers… whatever fits).",
    "quote": "FORMAT: quote/insight card — exactly 1 slide of kind \"quote\": title = the insight in your own "
             "words (it's YOUR line, not a famous person's), caption = a short context line, plus a \"graphic\" "
             "(usually hero_icon or icons) that hints at the subject.",
    "checklist": "FORMAT: checklist card — exactly 1 slide of kind \"checklist\": title + "
                 "\"graphic\": {\"type\": \"checklist\", \"items\": [4–5 short, actionable checks]}.",
}

ANGLE_GUIDE = {
    "tips": "ANGLE: practical tips — teach one skill with concrete examples.",
    "video": "ANGLE: short MOTION VIDEO script (~20 seconds), not a static carousel. Exactly 6 slides: cover, "
             "4 points, cta (no checklist). Each slide is on screen for ~3.5 seconds, so headlines must be at most "
             "6 words and captions empty or at most 8 words. Choose graphics that animate well and differ on every "
             "slide: steps, compare, timeline, icons, layers, phone, browser, components. post_text is the LinkedIn "
             "caption that goes with the video.",
    "breakdown": "ANGLE: breakdown — take the subject apart step by step: what it is, why it works (or why "
                 "people get it wrong), and exactly how to apply it, with a concrete example per slide.",
    "case_study": "ANGLE: mini case study / teardown — walk through a real-feeling UI scenario step by step, "
                  "explaining decisions and trade-offs. If it isn't one of my projects, present it as a "
                  "teardown of a common pattern (no brand names, no made-up results).",
    "do_dont": "ANGLE: do this, not that — show it with a \"compare\" graphic (winner = the better one).",
    "before_after": "ANGLE: before → after — show it with a \"compare\" graphic using two different screens.",
    "bold_statement": "ANGLE: bold statement — one punchy, defensible opinion as the headline, with a graphic "
                      "that makes the point visible.",
    "myth_vs_reality": "ANGLE: myth vs reality — the myth must be a belief people genuinely hold. Show it with a "
                       "\"compare\" graphic labelled Myth / Reality, or a spectrum.",
    "insight": "ANGLE: insight — a sharp observation from practice, explained with an example.",
    "reflective": "ANGLE: lighter, reflective weekend post — a lesson, a habit, or something that changed how "
                  "you work. Warmer tone, still one concrete example.",
    "checklist": "ANGLE: checklist — something people can save and use on their next project.",
    "quick_tip": "ANGLE: quick tip — one small technique explained in a few steps.",
}

VOICES = [
    "Open with a short scenario from a recent (unnamed) project.",
    "Direct teaching voice: state the rule, then show it.",
    "Contrarian but fair: challenge a popular habit, then give the nuance.",
    "Share a mistake you used to make and what you do now.",
    "Lead with a question a junior designer asked you, then answer it.",
    "Observational: something you noticed in an everyday app (describe it generically unless the topic names a brand).",
    "Playful and curious: 'what if we tried…', then show what happens.",
]


def system_prompt(cfg: dict) -> str:
    return SYSTEM.format(name=cfg["profile"]["name"], role=cfg["profile"]["role"],
                         language=cfg["content"].get("language", "English"))


def user_prompt(*, fmt: str, angle: str, topic: str, category_label: str, voice: str,
                recent_hooks: list[str], project: dict | None = None, focus: str = "",
                extra: str = "", guide: str = "") -> str:
    kinds = {k: v for k, v in KINDS.items()}
    parts = [
        f"TOPIC: {topic}",
        f"CATEGORY: {category_label}",
        f"HOW TO APPROACH THIS CATEGORY: {guide}" if guide else "",
        FORMAT_GUIDE[fmt],
        ANGLE_GUIDE.get(angle, ""),
        f"VOICE FOR THIS POST: {voice}",
        "SLIDE KINDS and max characters per field (hard limits — text must fit the image):\n"
        + json.dumps(kinds),
        "GRAPHIC TYPES (slide \"graphic\" object):\n" + "\n".join(f"- {k}: {v}" for k, v in GRAPHICS.items()),
        f"SCREENS: {', '.join(SCREENS)}\nLAYOUTS: {', '.join(LAYOUTS)}\nCOMPONENTS: {', '.join(COMPONENT_KINDS)}\n"
        f"ICONS: {', '.join(ICON_NAMES)}",
    ]
    if project:
        parts.append(
            "THIS IS A CASE STUDY OF MY OWN PROJECT. Use only these facts:\n"
            f"Project: {project['name']}\nDescription: {project.get('description', '')}\n"
            f"Focus on: {focus}. Where details are missing, talk about process and reasoning in general "
            "terms — do not invent metrics, users or outcomes."
        )
    if recent_hooks:
        parts.append("Recent hooks — do NOT reuse their structure or wording:\n- " + "\n- ".join(recent_hooks[-8:]))
    if extra:
        parts.append(extra)
    parts.append(f'Set "format" to "{fmt}" and "topic" to the topic above.')
    return "\n\n".join(p for p in parts if p)


def revise_prompt(previous: dict, instruction: str) -> str:
    return (
        f"Here is a post you wrote (JSON):\n{json.dumps(previous, ensure_ascii=False)}\n\n"
        f"REVISION REQUEST: {instruction}\n"
        "Return the full revised JSON object with the same keys and the same slides structure."
    )


def fix_prompt(original_user: str, errors: list[str]) -> str:
    return (original_user + "\n\nYOUR PREVIOUS ANSWER HAD PROBLEMS — fix all of them and return the full JSON again:\n- "
            + "\n- ".join(errors))
