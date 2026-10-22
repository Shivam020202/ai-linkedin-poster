"""Local mode: a tiny built-in scheduler + Telegram long polling, in one process."""
from __future__ import annotations

import logging
import queue
import threading
from datetime import datetime, timedelta
from typing import Callable

from ..config import secret
from ..pipeline import now_local, run_slot, schedule_times
from ..providers import ProviderChain
from ..storage import Store
from ..telegram.api import TelegramAPI
from ..telegram.delivery import send_error
from ..telegram.listener import COMMANDS, Listener, next_run_text

log = logging.getLogger("scheduler")
GRACE = timedelta(hours=2)  # a slot missed by more than this (PC asleep) is skipped, not posted late


def due_slots(now: datetime, times: list[str], done: set[int], queued: set[int],
              grace: timedelta = GRACE) -> list[int]:
    """Slots whose time has arrived today, within the grace window, not done or queued yet."""
    out = []
    for i, t in enumerate(times):
        h, m = map(int, t.split(":"))
        at = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if at <= now < at + grace and i not in done and i not in queued:
            out.append(i)
    return out


class Worker:
    """Runs generation jobs one at a time so Telegram polling stays responsive."""

    def __init__(self, api: TelegramAPI, chat_id: str):
        self.q: queue.Queue[tuple[str, Callable[[], None]]] = queue.Queue()
        self.api, self.chat_id = api, chat_id
        threading.Thread(target=self._loop, daemon=True).start()

    def submit(self, label: str, job: Callable[[], None]) -> None:
        self.q.put((label, job))

    def _loop(self):
        while True:
            label, job = self.q.get()
            try:
                job()
            except Exception as exc:  # noqa: BLE001
                log.debug("job failed", exc_info=True)
                send_error(self.api, self.chat_id, f"{label} failed: {exc}")


def run_forever(cfg: dict) -> None:
    store = Store()
    chat_id = secret("TELEGRAM_CHAT_ID")
    token = secret("TELEGRAM_BOT_TOKEN")
    poll_api, work_api = TelegramAPI(token), TelegramAPI(token)  # one session per thread
    chain = ProviderChain(cfg["ai"])
    worker = Worker(work_api, chat_id)
    listener = Listener(cfg, store, poll_api, chat_id, chain, worker.submit)
    stop = threading.Event()

    poll_api.call("deleteWebhook")
    poll_api.set_commands(COMMANDS)
    times = schedule_times(cfg, store)
    poll_api.send_message(chat_id, f"🟢 Bot is running. Next scheduled post {next_run_text(cfg, times)}. /help")
    log.info("running — times %s %s. Ctrl+C to stop.", times, cfg["schedule"]["timezone"])

    queued: dict[str, set[int]] = {}

    def tick():
        while not stop.is_set():
            try:
                now = now_local(cfg)
                day = now.date().isoformat()
                done = set(store.state()["done_slots"].get(day, []))
                q = queued.setdefault(day, set())
                for slot in due_slots(now, schedule_times(cfg, store), done, q):
                    q.add(slot)
                    log.info("slot %d due — queueing", slot)
                    worker.submit(f"Scheduled post (slot {slot + 1})",
                                  lambda s=slot: run_slot(cfg, store, chain, s, interactive=True))
            except Exception:  # noqa: BLE001
                log.exception("scheduler tick failed")
            stop.wait(20)

    threading.Thread(target=tick, daemon=True).start()
    try:
        listener.poll_forever(stop)
    finally:
        stop.set()
