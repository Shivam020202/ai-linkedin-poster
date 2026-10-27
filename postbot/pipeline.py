"""Glue: plan → generate → render → save → (optionally) deliver. Used by every entry point."""
from __future__ import annotations

import json
import logging
import random
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import OUTPUT_DIR, ROOT, secret
from .content.generator import Plan, generate_content, plan_post, revise_content
from .content.sample import sample_post
from .content.schema import full_post_text
from .content.topics import Topic
from .images.render import Renderer
from .storage import Store
from .telegram.api import TelegramAPI
from .telegram.delivery import send_error, send_post

log = logging.getLogger("pipeline")


def now_local(cfg: dict) -> datetime:
    return datetime.now(ZoneInfo(cfg["schedule"]["timezone"]))


def schedule_times(cfg: dict, store: Store) -> list[str]:
    return store.state().get("times") or cfg["schedule"]["times"]


def slot_counts(posts_per_day: int, n_slots: int) -> list[int]:
    """Spread posts over the day's time slots, e.g. 3 posts over 2 slots -> [2, 1]."""
    n_slots = max(1, n_slots)
    return [posts_per_day // n_slots + (1 if i < posts_per_day % n_slots else 0) for i in range(n_slots)]


def choose_theme(cfg: dict, store: Store, history: list[dict], override: str | None = None) -> str:
    if override:
        return override
    fixed = store.state().get("theme")
    if fixed:
        return fixed
    themes = cfg["image"]["themes"]
    last_used = {h.get("theme"): i for i, h in enumerate(history)}
    return min(themes, key=lambda t: last_used.get(t, -1))  # least recently used


def _post_dir(day: str) -> Path:
    base = OUTPUT_DIR / day
    n = 1
    while (base / f"post-{n}").exists():
        n += 1
    return base / f"post-{n}"


def build_post(cfg: dict, store: Store, chain, *, day: date, slot: int = 0, fmt_angle: str | None = None,
               topic_text: str | None = None, theme: str | None = None, offline: bool = False,
               record: bool = True, exclude_topics: set[str] = frozenset(),
               data: dict | None = None, plan: Plan | None = None, variant_of: str | None = None) -> dict:
    """Create one post on disk. `data` skips the AI call (used for re-theming)."""
    history = store.history()
    rng = random.Random()
    plan = plan or plan_post(cfg, history, day, slot, rng, fmt_angle, topic_text, exclude_topics)
    if data is None:
        if offline:
            data = sample_post("carousel" if plan.fmt == "carousel" else
                               {"single": "timeline", "quote": "quote", "checklist": "checklist"}[plan.fmt])
        else:
            log.info("generating %s:%s — %s", plan.fmt, plan.angle, plan.topic.text)
            data = generate_content(chain, cfg, plan, history)
    theme_name = choose_theme(cfg, store, history, theme)
    out_dir = _post_dir(day.isoformat())
    renderer = Renderer(cfg, theme_name, seed=f"{day.isoformat()}:{out_dir.name}:{plan.topic.text}")
    rendered = renderer.render_post(data, out_dir, kicker=plan.topic.label if plan.topic.category != "custom" else "")
    post_id = f"{day.strftime('%y%m%d')}-{out_dir.name.split('-')[1]}"

    (out_dir / "post.txt").write_text(full_post_text(data) + "\n", encoding="utf-8")
    meta = {
        "id": post_id, "date": day.isoformat(), "slot": slot, "theme": rendered["theme"],
        "plan": {"format": plan.fmt, "angle": plan.angle, "topic": plan.topic.text,
                 "category": plan.topic.category, "label": plan.topic.label, "guide": plan.topic.guide,
                 "voice": plan.voice,
                 "project": plan.project, "focus": plan.focus},
        "content": data,
        "files": [p.name for p in rendered["images"]] + (["carousel.pdf"] if rendered["pdf"] else []),
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    entry = {
        "id": post_id, "date": day.isoformat(), "slot": slot, "created_at": datetime.now().isoformat(timespec="seconds"),
        "topic": plan.topic.text, "category": plan.topic.category, "format": plan.fmt,
        "angle": f"case_study:{plan.focus}" if plan.project else plan.angle, "voice": plan.voice,
        "theme": rendered["theme"], "hook": data.get("hook", ""),
        "project": plan.project["name"] if plan.project else None,
        "dir": str(out_dir.relative_to(ROOT)), "delivered": False,
    }
    if variant_of:
        entry["variant_of"] = variant_of
    if record:
        store.add_post(entry)
    return {"id": post_id, "entry": entry, "data": data, "plan": plan, "theme": rendered["theme"],
            "images": rendered["images"], "pdf": rendered["pdf"], "dir": out_dir}


def load_post(post_id: str, store: Store) -> tuple[dict, dict] | None:
    entry = store.find_post(post_id)
    if not entry:
        return None
    meta_path = ROOT / entry["dir"] / "meta.json"
    if not meta_path.exists():
        return None
    return entry, json.loads(meta_path.read_text(encoding="utf-8"))


def plan_from_meta(meta: dict) -> Plan:
    p = meta["plan"]
    return Plan(p["format"], p["angle"], Topic(p["topic"], p["category"], p["label"], guide=p.get("guide", "")),
                p["voice"],
                p.get("project"), p.get("focus", ""))


def telegram() -> tuple[TelegramAPI, str]:
    return TelegramAPI(secret("TELEGRAM_BOT_TOKEN")), secret("TELEGRAM_CHAT_ID")


def print_post(post: dict) -> None:
    print("\n" + "═" * 70)
    print(f"{post['data']['format'].upper()} · theme {post['theme']} · {post['data']['topic']}")
    print(f"files: {post['dir']}")
    print("─" * 70)
    print(full_post_text(post["data"]))
    print("─" * 70)
    print("ALT TEXT:", post["data"].get("alt_text", ""))


def run_slot(cfg: dict, store: Store, chain, slot: int, *, day: date | None = None, dry_run: bool = False,
             interactive: bool = False, offline: bool = False, force: bool = False) -> tuple[int, int]:
    """Generate (and send) the posts that belong to one time slot. Returns (made, failed)."""
    day = day or now_local(cfg).date()
    state = store.state()
    api, chat_id = (None, None) if dry_run else telegram()
    if not force:
        if state["paused"]:
            log.info("paused — skipping slot %d", slot)
            return 0, 0
        if store.slot_done(day.isoformat(), slot):
            log.info("slot %d for %s already done", slot, day)
            return 0, 0
        if state["skip_next"] > 0:
            store.set_state(skip_next=state["skip_next"] - 1)
            store.mark_slot_done(day.isoformat(), slot)
            log.info("skipping slot %d (requested via /skip)", slot)
            if api:
                api.send_message(chat_id, "⏭ Skipped this slot as requested.")
            return 0, 0

    times = schedule_times(cfg, store)
    counts = slot_counts(int(cfg["schedule"]["posts_per_day"]), len(times))
    count = counts[slot % len(counts)]
    total = sum(counts)
    start = sum(counts[:slot % len(counts)])
    made = failed = 0
    used_topics: set[str] = set()
    for k in range(count):
        try:
            post = build_post(cfg, store, chain, day=day, slot=start + k, offline=offline,
                              record=not dry_run, exclude_topics=used_topics)
            used_topics.add(post["data"]["topic"])
            if dry_run:
                print_post(post)
            else:
                send_post(api, chat_id, cfg, post, start + k + 1, total, interactive)
                store.update_post(post["id"], delivered=True)
            made += 1
        except Exception as exc:  # noqa: BLE001 — tell the user instead of failing silently
            failed += 1
            log.debug("details", exc_info=True)
            send_error(api, chat_id, f"Couldn't create post {start + k + 1}/{total}: {exc}")
    if not dry_run and not force:
        store.mark_slot_done(day.isoformat(), slot)
    return made, failed


def regenerate(cfg: dict, store: Store, chain, post_id: str, mode: str, theme: str | None = None) -> dict:
    """Button actions: regen | short | topic | theme."""
    loaded = load_post(post_id, store)
    if not loaded:
        raise LookupError("I can't find that post any more (output folder deleted?).")
    entry, meta = loaded
    day = date.fromisoformat(entry["date"])
    plan = plan_from_meta(meta)
    if mode == "theme":
        if theme in (None, "next"):  # cycle to the next theme in config.yaml
            themes = cfg["image"]["themes"]
            i = themes.index(entry["theme"]) if entry["theme"] in themes else -1
            theme = themes[(i + 1) % len(themes)]
        return build_post(cfg, store, chain, day=day, slot=entry["slot"], theme=theme,
                          data=meta["content"], plan=plan, variant_of=post_id)
    if mode == "short":
        data = revise_content(chain, cfg, meta["content"],
                              "Make post_text noticeably shorter: 500–800 characters. Keep the hook idea, "
                              "the concrete example and the closing line. Keep slides as they are.",
                              length=(500, 800))
        return build_post(cfg, store, chain, day=day, slot=entry["slot"], theme=entry["theme"],
                          data=data, plan=plan, variant_of=post_id)
    if mode == "topic":
        return build_post(cfg, store, chain, day=day, slot=entry["slot"], fmt_angle=f"{plan.fmt}:{plan.angle}",
                          exclude_topics={entry["topic"]})
    # regen: same topic & format, fresh writing
    plan.extra = "Write a completely new take — different hook, structure and example than before:\n" \
                 + meta["content"].get("hook", "")
    return build_post(cfg, store, chain, day=day, slot=entry["slot"], plan=plan, theme=entry["theme"],
                      variant_of=post_id)
