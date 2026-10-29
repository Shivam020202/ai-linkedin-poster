"""Telegram commands and inline buttons (local `run` mode). Only your chat ID is served."""
from __future__ import annotations

import html
import logging
import re
import time
from datetime import timedelta
from typing import Callable

from ..content.topics import add_topic, load_topics, remove_topic, upcoming
from ..images.themes import THEME_NAMES
from ..pipeline import build_post, now_local, regenerate, schedule_times
from ..storage import Store
from .api import TelegramAPI, TelegramError
from .delivery import send_post

log = logging.getLogger("listener")

COMMANDS = [
    ("now", "generate a post immediately"),
    ("post", "<topic> — generate on a specific topic"),
    ("video", "[topic] — make a motion video now"),
    ("topics", "show upcoming topics"),
    ("add", "<topic> — add a topic"),
    ("remove", "<topic> — remove a topic"),
    ("skip", "skip the next scheduled post"),
    ("theme", "<name|auto> — fix a theme or rotate"),
    ("times", "09:00,18:30 — change the schedule"),
    ("history", "last 10 posts"),
    ("pause", "pause scheduled posts"),
    ("resume", "resume scheduled posts"),
    ("status", "schedule and settings"),
    ("help", "show commands"),
]
TIME = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def is_allowed(update: dict, chat_id: str) -> bool:
    """Only the owner's private chat may command the bot."""
    if "callback_query" in update:
        cq = update["callback_query"]
        chat = (cq.get("message") or {}).get("chat", {}).get("id")
        sender = cq.get("from", {}).get("id")
        return str(chat) == str(chat_id) and str(sender) == str(chat_id)
    msg = update.get("message") or {}
    return str(msg.get("chat", {}).get("id")) == str(chat_id)


def parse_times(text: str) -> list[str] | None:
    out = []
    for part in re.split(r"[,\s]+", text.strip()):
        if not part:
            continue
        m = TIME.match(part)
        if not m:
            return None
        out.append(f"{int(m.group(1)):02d}:{m.group(2)}")
    return sorted(set(out)) or None


class Listener:
    def __init__(self, cfg: dict, store: Store, api: TelegramAPI, chat_id: str, chain,
                 enqueue: Callable[[str, Callable[[], None]], None]):
        self.cfg, self.store, self.api, self.chat_id, self.chain = cfg, store, api, chat_id, chain
        self.enqueue = enqueue

    def reply(self, text: str, html_mode: bool = False) -> None:
        self.api.send_message(self.chat_id, text, parse_mode="HTML" if html_mode else None)

    # ---- polling loop ---------------------------------------------------
    def poll_forever(self, stop) -> None:
        offset = self.store.state().get("telegram_offset", 0)
        started = time.time()
        while not stop.is_set():
            try:
                updates = self.api.get_updates(offset, timeout=25)
            except TelegramError as exc:
                log.warning("polling error: %s — retrying in 10s", exc)
                stop.wait(10)
                continue
            for upd in updates:
                offset = upd["update_id"] + 1
                self.store.set_state(telegram_offset=offset)
                sent = (upd.get("message") or {}).get("date", time.time())
                if sent < started - 600:
                    continue  # ignore commands sent long before the bot started
                try:
                    self.handle(upd)
                except Exception as exc:  # noqa: BLE001
                    log.exception("update failed")
                    self.reply(f"⚠️ {exc}")

    def handle(self, upd: dict) -> None:
        if not is_allowed(upd, self.chat_id):
            who = (upd.get("message") or upd.get("callback_query") or {}).get("from", {}).get("id")
            log.warning("ignored update from unknown user %s", who)
            return
        if "callback_query" in upd:
            self.on_button(upd["callback_query"])
            return
        text = (upd.get("message") or {}).get("text", "").strip()
        if not text.startswith("/"):
            self.reply("Send /help to see what I can do.")
            return
        cmd, _, arg = text.partition(" ")
        cmd = cmd[1:].split("@")[0].lower()
        handler = getattr(self, f"cmd_{cmd}", None)
        if handler is None:
            self.reply("Unknown command. /help lists them.")
            return
        handler(arg.strip())

    # ---- commands -------------------------------------------------------
    def cmd_start(self, arg):
        self.cmd_help(arg)

    def cmd_help(self, arg):
        lines = ["<b>Commands</b>"] + [f"/{c} {html.escape(d)}" for c, d in COMMANDS]
        lines.append("\nButtons under each post: Regenerate · Make it shorter · Different topic · Theme.")
        self.reply("\n".join(lines), html_mode=True)

    def _make(self, label: str, **kwargs) -> None:
        def job():
            day = now_local(self.cfg).date()
            today = [h for h in self.store.history() if h.get("date") == day.isoformat()]
            post = build_post(self.cfg, self.store, self.chain, day=day, slot=len(today), **kwargs)
            send_post(self.api, self.chat_id, self.cfg, post, interactive=True)
            self.store.update_post(post["id"], delivered=True)
        self.reply(f"⏳ {label}…")
        self.enqueue(label, job)

    def cmd_now(self, arg):
        self._make("Writing a post")

    def cmd_post(self, arg):
        if not arg:
            self.reply("Usage: /post <topic>, e.g. /post empty states in dashboards")
            return
        self._make(f"Writing about “{arg[:80]}”", topic_text=arg[:200])

    def cmd_video(self, arg):
        from ..video_pipeline import build_video

        def job():
            day = now_local(self.cfg).date()
            post = build_video(self.cfg, self.store, self.chain, day=day, topic_text=arg[:200] or None)
            from .delivery import send_video_post
            send_video_post(self.api, self.chat_id, self.cfg, post, interactive=True)
            self.store.update_post(post["id"], delivered=True)
        self.reply("🎬 Making a video — this takes a minute or two…")
        self.enqueue("Video", job)

    def cmd_topics(self, arg):
        c = self.cfg["content"]
        nxt = upcoming(load_topics(), self.store.history(), now_local(self.cfg).date(), 10,
                       c["no_repeat_days"], c["dev_topic_ratio"])
        self.reply("Likely next topics:\n" + "\n".join(f"· {t.text}" for t in nxt)
                   + "\n\nAdd your own with /add <topic>.")

    def cmd_add(self, arg):
        if not arg:
            self.reply("Usage: /add <topic>")
        elif add_topic(arg[:200]):
            self.reply(f"✓ Added: {arg[:200]}")
        else:
            self.reply("That topic is already in the list.")

    def cmd_remove(self, arg):
        self.reply("✓ Removed." if arg and remove_topic(arg) else "No topic with exactly that text.")

    def cmd_skip(self, arg):
        st = self.store.set_state(skip_next=self.store.state()["skip_next"] + 1)
        self.reply(f"⏭ Will skip the next {st['skip_next']} scheduled slot(s).")

    def cmd_theme(self, arg):
        name = arg.lower().strip()
        if name in ("auto", "rotate", ""):
            self.store.set_state(theme=None)
            self.reply("🎨 Themes will rotate: " + ", ".join(self.cfg["image"]["themes"]))
        elif name in THEME_NAMES:
            self.store.set_state(theme=name)
            self.reply(f"🎨 Using the {name} theme for new posts. /theme auto to rotate again.")
        else:
            self.reply("Themes: " + ", ".join(THEME_NAMES) + ", or auto")

    def cmd_times(self, arg):
        times = parse_times(arg)
        if not times:
            self.reply("Usage: /times 09:00,18:30 (24-hour, your timezone)")
            return
        self.store.set_state(times=times)
        self.reply(f"🕘 New schedule: {', '.join(times)} ({self.cfg['schedule']['timezone']}).\n"
                   "Note: this changes local mode only. For GitHub Actions, edit the cron lines "
                   "in .github/workflows/daily.yml.")

    def cmd_history(self, arg):
        posts = [p for p in self.store.history() if not p.get("variant_of")][-10:]
        if not posts:
            self.reply("No posts yet. Try /now.")
            return
        self.reply("Last posts:\n" + "\n".join(
            f"· {p['date']} · {p['format']} · {p['topic']}" for p in reversed(posts)))

    def cmd_pause(self, arg):
        self.store.set_state(paused=True)
        self.reply("⏸ Paused. Scheduled posts won't be generated until /resume. /now still works.")

    def cmd_resume(self, arg):
        self.store.set_state(paused=False)
        self.reply("▶️ Resumed.")

    def cmd_status(self, arg):
        st = self.store.state()
        now = now_local(self.cfg)
        times = schedule_times(self.cfg, self.store)
        upcoming_t = [t for t in times if t > now.strftime("%H:%M")]
        nxt = f"today {upcoming_t[0]}" if upcoming_t else f"tomorrow {times[0]}"
        self.reply(
            f"Status: {'⏸ paused' if st['paused'] else '▶️ running'}\n"
            f"Times: {', '.join(times)} ({self.cfg['schedule']['timezone']}) · next: {nxt}\n"
            f"Posts/day: {self.cfg['schedule']['posts_per_day']} · skip queued: {st['skip_next']}\n"
            f"Theme: {st['theme'] or 'rotating'} · AI: {self.cfg['ai']['provider']}")

    # ---- buttons --------------------------------------------------------
    def _video_button(self, cq: dict, action: str, post_id: str) -> None:
        from ..video_pipeline import regenerate_video
        from .delivery import send_video_post
        label = "Making a new video" if action == "vnew" else "Re-rendering the video in another theme"
        self.api.answer_callback(cq["id"], label + "…")

        def job():
            post = regenerate_video(self.cfg, self.store, self.chain, post_id, action)
            send_video_post(self.api, self.chat_id, self.cfg, post, interactive=True)
            self.store.update_post(post["id"], delivered=True)
        self.reply(f"⏳ {label}…")
        self.enqueue(label, job)

    def on_button(self, cq: dict) -> None:
        data = cq.get("data", "")
        parts = data.split(":")
        action, post_id = parts[0], parts[-1]
        if action in ("vnew", "vtheme"):
            self._video_button(cq, action, post_id)
            return
        theme = parts[1] if action == "theme" and len(parts) == 3 else None
        labels = {"regen": "Regenerating", "short": "Shortening", "topic": "Picking a different topic",
                  "theme": "Re-rendering in another theme" if theme == "next" else f"Re-rendering in {theme} theme"}
        if action not in labels:
            self.api.answer_callback(cq["id"], "Unknown button")
            return
        self.api.answer_callback(cq["id"], labels[action] + "…")

        def job():
            post = regenerate(self.cfg, self.store, self.chain, post_id, action, theme)
            send_post(self.api, self.chat_id, self.cfg, post, interactive=True, only_text=action == "short")
            self.store.update_post(post["id"], delivered=True)
        self.reply(f"⏳ {labels[action]}…")
        self.enqueue(labels[action], job)


def next_run_text(cfg: dict, times: list[str]) -> str:
    now = now_local(cfg)
    later = [t for t in times if t > now.strftime("%H:%M")]
    if later:
        return f"today at {later[0]}"
    return f"{(now + timedelta(days=1)):%a} at {times[0]}"
