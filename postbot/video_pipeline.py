"""Daily motion video: plan → script (AI) → validate → render each format → QA → save → send."""
from __future__ import annotations

import json
import logging
import random
from datetime import date, datetime
from pathlib import Path

from .config import OUTPUT_DIR, ROOT
from .content.generator import generate_content, plan_post
from .content.sample import sample_post
from .content.schema import full_post_text
from .pipeline import choose_theme, load_post, now_local, plan_from_meta, telegram
from .storage import Store
from .telegram.delivery import send_error, send_video_post
from .video.render import VideoRenderer

log = logging.getLogger("video")
VIDEO_SLOT = 99  # id used in state.done_slots for "today's video"


def video_settings(cfg: dict) -> dict:
    v = {"enabled": True, "time": None, "formats": ["4:5"], "fps": 30, "audio": True, "music": ""}
    v.update(cfg.get("video") or {})
    return v


def _video_dir(day: str) -> Path:
    base = OUTPUT_DIR / day
    n = 1
    while (base / f"video-{n}").exists():
        n += 1
    return base / f"video-{n}"


def build_video(cfg: dict, store: Store, chain, *, day: date, topic_text: str | None = None,
                theme: str | None = None, offline: bool = False, record: bool = True, formats: list[str] | None = None,
                data: dict | None = None, plan=None, variant_of: str | None = None) -> dict:
    vcfg = video_settings(cfg)
    history = store.history()
    plan = plan or plan_post(cfg, history, day, 0, random.Random(), "carousel:video", topic_text)
    if data is None:
        if offline:
            data = sample_post("carousel")
        else:
            log.info("writing video script — %s", plan.topic.text)
            data = generate_content(chain, cfg, plan, history)
    theme_name = choose_theme(cfg, store, history, theme)
    out_dir = _video_dir(day.isoformat())
    out_dir.mkdir(parents=True, exist_ok=True)
    seed = f"{day.isoformat()}:{out_dir.name}:{plan.topic.text}"
    kicker = plan.topic.label if plan.topic.category != "custom" else ""

    videos = []
    for i, fmt in enumerate(formats or vcfg["formats"]):
        vr = VideoRenderer(cfg, theme_name, fmt, seed, fps=vcfg["fps"])
        vr.build(data, kicker)
        audio = vr.soundtrack(out_dir / "soundtrack.wav") if vcfg["audio"] else None
        path = out_dir / f"video-{fmt.replace(':', 'x')}.mp4"
        log.info("rendering %s (%d frames)", path.name, vr.frame_count())
        vr.render(path, audio)
        qa = vr.qa(path)
        if i == 0:
            vr.contact_sheet(out_dir / "contact-sheet.png")
            settled = vr.scenes[0].start + min(2.4, vr.scenes[0].end - vr.scenes[0].start - 0.5)
            vr.seek(settled).save(out_dir / "poster.png")
        for issue in qa["issues"]:
            log.warning("QA %s: %s", fmt, issue)
        videos.append({"path": path, "format": fmt, "width": vr.W, "height": vr.H,
                       "duration": round(vr.duration, 1), "qa": qa})

    post_id = f"{day.strftime('%y%m%d')}-v{out_dir.name.split('-')[1]}"
    (out_dir / "post.txt").write_text(full_post_text(data) + "\n", encoding="utf-8")
    meta = {
        "id": post_id, "date": day.isoformat(), "slot": VIDEO_SLOT, "theme": theme_name,
        "plan": {"format": "video", "angle": "video", "topic": plan.topic.text, "category": plan.topic.category,
                 "label": plan.topic.label, "guide": plan.topic.guide, "voice": plan.voice,
                 "project": None, "focus": ""},
        "content": data,
        "videos": [{k: (str(v.name) if k == "path" else v) for k, v in vid.items()} for vid in videos],
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    entry = {
        "id": post_id, "date": day.isoformat(), "slot": VIDEO_SLOT,
        "created_at": datetime.now().isoformat(timespec="seconds"), "topic": plan.topic.text,
        "category": plan.topic.category, "format": "video", "angle": "video", "voice": plan.voice,
        "theme": theme_name, "hook": data.get("hook", ""), "project": None,
        "dir": str(out_dir.relative_to(ROOT)), "delivered": False,
    }
    if variant_of:
        entry["variant_of"] = variant_of
    if record:
        store.add_post(entry)
    return {"id": post_id, "entry": entry, "data": data, "plan": plan, "theme": theme_name,
            "videos": videos, "dir": out_dir, "poster": out_dir / "poster.png"}


def print_video(post: dict) -> None:
    print("\n" + "═" * 70)
    print(f"VIDEO · theme {post['theme']} · {post['data']['topic']}")
    for v in post["videos"]:
        issues = "; ".join(v["qa"]["issues"]) or "no issues"
        print(f"  {v['format']:>5}  {v['width']}x{v['height']}  {v['duration']}s  {v['path']}  [QA: {issues}]")
    print(f"  contact sheet: {post['dir'] / 'contact-sheet.png'}")
    print("─" * 70)
    print(full_post_text(post["data"]))


def video_due(cfg: dict, store: Store, now: datetime, times: list[str]) -> bool:
    vcfg = video_settings(cfg)
    if not vcfg["enabled"]:
        return False
    at = vcfg["time"] or (times[0] if times else "09:00")
    return now.strftime("%H:%M") >= at and not store.slot_done(now.date().isoformat(), VIDEO_SLOT)


def run_video_slot(cfg: dict, store: Store, chain, *, day: date | None = None, dry_run: bool = False,
                   interactive: bool = False, offline: bool = False, force: bool = False) -> tuple[int, int]:
    """Make and send today's video. Returns (made, failed)."""
    day = day or now_local(cfg).date()
    api, chat_id = (None, None) if dry_run else telegram()
    if not force:
        if store.state()["paused"]:
            return 0, 0
        if store.slot_done(day.isoformat(), VIDEO_SLOT):
            return 0, 0
    try:
        post = build_video(cfg, store, chain, day=day, offline=offline, record=not dry_run)
        if dry_run:
            print_video(post)
        else:
            send_video_post(api, chat_id, cfg, post, interactive)
            store.update_post(post["id"], delivered=True)
        made, failed = 1, 0
    except Exception as exc:  # noqa: BLE001 — tell the user instead of failing silently
        log.debug("details", exc_info=True)
        send_error(api, chat_id, f"Couldn't create today's video: {exc}")
        made, failed = 0, 1
    if not dry_run and not force:
        store.mark_slot_done(day.isoformat(), VIDEO_SLOT)
    return made, failed


def regenerate_video(cfg: dict, store: Store, chain, post_id: str, mode: str) -> dict:
    """Buttons: vnew = a new video on a different topic, vtheme = same script in the next theme."""
    loaded = load_post(post_id, store)
    if not loaded:
        raise LookupError("I can't find that video any more (output folder deleted?).")
    entry, meta = loaded
    day = date.fromisoformat(entry["date"])
    if mode == "vtheme":
        themes = cfg["image"]["themes"]
        i = themes.index(entry["theme"]) if entry["theme"] in themes else -1
        return build_video(cfg, store, chain, day=day, theme=themes[(i + 1) % len(themes)],
                           data=meta["content"], plan=plan_from_meta(meta), variant_of=post_id)
    # vnew: fresh script on a different topic (same rotation rules as posts)
    from .content.generator import Plan
    from .content.prompts import VOICES
    from .content.topics import load_topics, pick_topic
    c = cfg["content"]
    topic = pick_topic(load_topics(), store.history(), day, random.Random(), c["no_repeat_days"],
                       c["dev_topic_ratio"], {entry["topic"]})
    return build_video(cfg, store, chain, day=day, plan=Plan("carousel", "video", topic, random.choice(VOICES)))
