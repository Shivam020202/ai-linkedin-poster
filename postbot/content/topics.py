"""Topic bank (topics.yaml) and rotation: no topic repeats within `no_repeat_days`."""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import yaml

from ..config import TOPICS_PATH

CASE_STUDY_FOCUS = [
    "the problem and who it was for",
    "one key design decision and the trade-off behind it",
    "how the information architecture or flow was shaped",
    "the visual system — type, colour, spacing choices",
    "what I would do differently now",
]


@dataclass
class Topic:
    text: str
    category: str
    label: str
    dev: bool = False
    guide: str = ""


def load_topics(path: Path = TOPICS_PATH) -> list[Topic]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out = []
    for key, cat in (data.get("categories") or {}).items():
        for text in cat.get("topics") or []:
            out.append(Topic(str(text).strip(), key, cat.get("label", key), bool(cat.get("dev")),
                             " ".join(str(cat.get("guide", "")).split())))
    return out


def add_topic(text: str, path: Path = TOPICS_PATH) -> bool:
    text = text.strip()
    if not text:
        return False
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    cats = data.setdefault("categories", {})
    if any(text.lower() == str(t).lower() for c in cats.values() for t in (c.get("topics") or [])):
        return False
    custom = cats.setdefault("custom", {"label": "My topics", "topics": []})
    custom["topics"] = (custom.get("topics") or []) + [text]
    _save(data, path)
    return True


def remove_topic(text: str, path: Path = TOPICS_PATH) -> bool:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    removed = False
    for cat in (data.get("categories") or {}).values():
        before = cat.get("topics") or []
        after = [t for t in before if str(t).lower() != text.strip().lower()]
        removed |= len(after) != len(before)
        cat["topics"] = after
    if removed:
        _save(data, path)
    return removed


def _save(data: dict, path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    header = "\n".join(l for l in lines if l.startswith("#"))
    path.write_text(header + "\n\n" + yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _recent(history: list[dict], today: date, days: int) -> list[dict]:
    cutoff = (today - timedelta(days=days)).isoformat()
    return [h for h in history if h.get("date", "") > cutoff]


def pick_topic(topics: list[Topic], history: list[dict], today: date, rng: random.Random,
               no_repeat_days: int = 30, dev_ratio: float = 0.15, exclude: set[str] = frozenset()) -> Topic:
    """Choose a topic not used in the last `no_repeat_days`, balancing categories."""
    if not topics:
        raise ValueError("topics.yaml has no topics")
    recent_topics = {h["topic"].lower() for h in _recent(history, today, no_repeat_days) if h.get("topic")}
    excluded = {e.lower() for e in exclude} | recent_topics

    design = [t for t in topics if not t.dev]
    dev = [t for t in topics if t.dev]
    pool = dev if (dev and (not design or rng.random() < dev_ratio)) else design

    fresh = [t for t in pool if t.text.lower() not in excluded] or \
            [t for t in topics if t.text.lower() not in excluded]
    if not fresh:
        # everything used recently: take the least recently used topics
        last_used = {}
        for h in history:
            last_used[h.get("topic", "").lower()] = h.get("date", "")
        oldest = min(last_used.get(t.text.lower(), "") for t in topics)
        fresh = [t for t in topics if last_used.get(t.text.lower(), "") == oldest
                 and t.text.lower() not in {e.lower() for e in exclude}] or topics

    # Down-weight categories used in the last few posts, so the feed mixes subjects.
    recent_cats = [h.get("category") for h in history[-4:]]
    weights = [1.0 / (1 + 3 * recent_cats.count(t.category)) for t in fresh]
    # custom topics the user added get a boost: they asked for them
    weights = [w * (2.5 if t.category == "custom" else 1) for w, t in zip(weights, fresh)]
    return rng.choices(fresh, weights=weights, k=1)[0]


def pick_case_study(portfolio: list[dict], history: list[dict]) -> tuple[dict, str] | None:
    """Least-recently featured portfolio project + a focus not used for it before (if possible)."""
    if not portfolio:
        return None
    featured = [h for h in history if h.get("category") == "portfolio"]

    def last_seen(p):
        dates = [h["date"] for h in featured if h.get("project") == p["name"]]
        return max(dates) if dates else ""

    project = min(portfolio, key=last_seen)
    used = [h.get("angle", "") for h in featured if h.get("project") == project["name"]]
    focus = next((f for f in CASE_STUDY_FOCUS if f"case_study:{f}" not in used),
                 CASE_STUDY_FOCUS[len(used) % len(CASE_STUDY_FOCUS)])
    return project, focus


def upcoming(topics: list[Topic], history: list[dict], today: date, n: int = 10,
             no_repeat_days: int = 30, dev_ratio: float = 0.15, seed: int = 0) -> list[Topic]:
    """Preview the next n picks (simulated; real picks are random within the same rules)."""
    rng = random.Random(seed or today.toordinal())
    sim = list(history)
    out = []
    for i in range(n):
        day = today + timedelta(days=i // 2)
        t = pick_topic(topics, sim, day, rng, no_repeat_days, dev_ratio)
        out.append(t)
        sim.append({"topic": t.text, "category": t.category, "date": day.isoformat()})
    return out
