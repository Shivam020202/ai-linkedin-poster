"""Plan a post (format, angle, topic, voice) and get validated JSON content from the AI provider."""
from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from datetime import date

from . import prompts
from .schema import ValidationError, normalize, parse_json, validate
from .topics import Topic, load_topics, pick_case_study, pick_topic

log = logging.getLogger("generator")

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
FALLBACK_TAGS = {
    "brand_systems": ["#DesignSystems", "#UIDesign", "#ProductDesign", "#Branding"],
    "modern_trends": ["#DesignTrends", "#UIDesign", "#ProductDesign", "#UXDesign"],
    "retro_revival": ["#RetroDesign", "#UIDesign", "#DesignInspiration", "#ProductDesign"],
    "misconceptions": ["#UXDesign", "#DesignThinking", "#UIDesign", "#ProductDesign"],
}
DEFAULT_TAGS = ["#UXDesign", "#UIDesign", "#ProductDesign", "#DesignTips"]


@dataclass
class Plan:
    fmt: str
    angle: str
    topic: Topic
    voice: str
    project: dict | None = None
    focus: str = ""
    extra: str = ""
    meta: dict = field(default_factory=dict)


def slot_format(cfg: dict, day: date, slot: int) -> tuple[str, str]:
    plan = cfg["schedule"]["format_plan"].get(WEEKDAYS[day.weekday()]) or ["carousel:tips"]
    fmt, _, angle = plan[slot % len(plan)].partition(":")
    return fmt, angle or "tips"


def plan_post(cfg: dict, history: list[dict], day: date, slot: int, rng: random.Random,
              fmt_angle: str | None = None, topic_text: str | None = None,
              exclude_topics: set[str] = frozenset()) -> Plan:
    if fmt_angle:
        fmt, _, angle = fmt_angle.partition(":")
        angle = angle or "tips"
    else:
        fmt, angle = slot_format(cfg, day, slot)
    content = cfg["content"]
    topics = load_topics()
    project, focus = None, ""

    if topic_text:
        topic = Topic(topic_text, "custom", "Requested topic")
    elif angle == "case_study" and content.get("portfolio") and rng.random() < 0.7:
        project, focus = pick_case_study(content["portfolio"], history)
        topic = Topic(f"Case study: {project['name']}", "portfolio", "Portfolio case study")
    elif angle == "case_study":
        teardowns = [t for t in topics if t.category == "case_studies"] or topics
        topic = pick_topic(teardowns, history, day, rng, content["no_repeat_days"], 0, exclude_topics)
    else:
        topic = pick_topic(topics, history, day, rng, content["no_repeat_days"],
                           content["dev_topic_ratio"], exclude_topics)

    recent_voices = [h.get("voice") for h in history[-3:]]
    voice = rng.choice([v for v in prompts.VOICES if v not in recent_voices] or prompts.VOICES)
    return Plan(fmt, angle, topic, voice, project, focus)


def _ask(chain, system: str, user: str, fmt: str, length: tuple[int, int] | None = None) -> dict:
    prompt = user
    for attempt in (1, 2):
        raw = chain.generate(system, prompt)
        try:
            data = parse_json(raw)
            hard, soft = validate(data, fmt, length)
        except ValidationError as exc:
            data, hard, soft = None, exc.errors, []
        if not hard and not soft:
            return data
        log.info("attempt %d issues: %s", attempt, "; ".join(hard + soft)[:500])
        if attempt == 1:
            prompt = prompts.fix_prompt(user, hard + soft)
        elif hard:
            raise ValidationError(hard, hard=True)
    return data  # only soft issues left: normalize() makes it usable


def generate_content(chain, cfg: dict, plan: Plan, history: list[dict]) -> dict:
    recent_hooks = [h.get("hook", "") for h in history[-10:] if h.get("hook")]
    user = prompts.user_prompt(
        fmt=plan.fmt, angle=plan.angle, topic=plan.topic.text, category_label=plan.topic.label,
        voice=plan.voice, recent_hooks=recent_hooks, project=plan.project, focus=plan.focus, extra=plan.extra,
        guide=plan.topic.guide,
    )
    data = _ask(chain, prompts.system_prompt(cfg), user, plan.fmt)
    tags = FALLBACK_TAGS.get(plan.topic.category, DEFAULT_TAGS)
    data = normalize(data, plan.fmt, tags, plan.topic.category)
    data["topic"] = plan.topic.text
    return data


def revise_content(chain, cfg: dict, previous: dict, instruction: str,
                   length: tuple[int, int] | None = None) -> dict:
    fmt = previous["format"]
    keep = {k: previous[k] for k in ("format", "topic", "hook", "post_text", "hashtags", "slides",
                                      "alt_text", "image_caption") if k in previous}
    data = _ask(chain, prompts.system_prompt(cfg), prompts.revise_prompt(keep, instruction), fmt, length)
    data = normalize(data, fmt, previous.get("hashtags") or DEFAULT_TAGS, previous.get("category", ""))
    data["topic"] = previous.get("topic", data.get("topic", ""))
    return data
