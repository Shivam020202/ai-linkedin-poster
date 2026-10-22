"""System and user prompts. The writing rules live here."""
from __future__ import annotations

import json

from .schema import KINDS, VISUALS

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
  "slides": [{{"kind": str, "title": str, "visual": str, ...kind-specific fields}}],
  "alt_text": str, "image_caption": str}}
- alt_text: 1–3 sentences describing the image(s) for screen-reader users (what is shown + the text on it).
- image_caption: one short line summarising the visual.
"""

FORMAT_GUIDE = {
    "carousel": """FORMAT: carousel (LinkedIn PDF document), 7–9 slides, in this order:
1. kind "hook" — big promise/claim (title) + optional one-line subtitle (body).
2. kind "problem" — the problem or common mistake.
3–7. 4–5 slides of kind "tip" (or "do_dont" / "before_after" where a comparison is clearer). Each slide = one \
point with a concrete example; pick a "visual" that illustrates it when one fits. Use each visual at most \
once per carousel. Don't number slide titles ("1.", "Tip 2:") — the design adds labels.
8. kind "recap" — "items": 3–5 short bullet points.
9. kind "cta" — soft call to action (save, share, follow, or a question).""",
    "single": "FORMAT: single image card — exactly 1 slide.",
    "quote": "FORMAT: quote/insight card — exactly 1 slide of kind \"quote\": title = the insight in your own "
             "words (it's YOUR line, not a famous person's), body = a short context line.",
    "checklist": "FORMAT: checklist card — exactly 1 slide of kind \"checklist\": title + 4–6 \"items\" that are "
                 "short, actionable checks.",
}

ANGLE_GUIDE = {
    "tips": "ANGLE: practical tips — teach one skill with concrete examples.",
    "breakdown": "ANGLE: breakdown — take the subject apart step by step: what it is, why it works (or why "
                 "people get it wrong), and exactly how to apply it, with a concrete example per slide.",
    "case_study": "ANGLE: mini case study / teardown — walk through a real-feeling UI scenario step by step, "
                  "explaining decisions and trade-offs. If it isn't one of my projects, present it as a "
                  "teardown of a common pattern (no brand names, no made-up results).",
    "do_dont": "ANGLE: do this, not that — slide kind \"do_dont\" with \"do\" and \"dont\" fields.",
    "before_after": "ANGLE: before → after — slide kind \"before_after\" with \"before\" and \"after\" fields.",
    "bold_statement": "ANGLE: bold statement — slide kind \"statement\": one punchy, defensible opinion as title, "
                      "a one-line support in body. Pick a visual that illustrates it.",
    "myth_vs_reality": "ANGLE: myth vs reality — slide kind \"myth_reality\" with \"myth\" and \"reality\" fields. "
                       "The myth must be a belief people genuinely hold.",
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
        "VISUALS (set \"visual\" on each slide; use \"none\" if nothing fits):\n"
        + "\n".join(f"- {k}: {v}" for k, v in VISUALS.items()),
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
