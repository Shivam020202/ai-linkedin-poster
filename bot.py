#!/usr/bin/env python3
"""Daily Content Bot — command line entry point.

  python bot.py setup                       first-run wizard (same as `python setup.py`)
  python bot.py test                        send a "hello" to your Telegram
  python bot.py preview                     render sample posts in every theme → preview/
  python bot.py now [--dry-run]             make one post right now (and send it)
  python bot.py once [--dry-run] [--all]    make the posts that are due today, then exit (cron / Actions)
  python bot.py run                         keep running: schedule + Telegram commands & buttons
  python bot.py topics                      show upcoming topics
  python bot.py cron                        print GitHub Actions cron lines for your times
"""
from __future__ import annotations

import argparse
import logging
import sys

from postbot.config import load_config, secret
from postbot.logutil import setup_logging

log = logging.getLogger("bot")


def _chain(cfg, args):
    if getattr(args, "offline", False):
        return None
    from postbot.providers import ProviderChain
    return ProviderChain(cfg["ai"])


def _ensure_fonts(cfg):
    from postbot.images.fonts import download_fonts
    download_fonts([cfg["fonts"]["heading"], cfg["fonts"]["body"], cfg["fonts"].get("serif", "dm-serif-display")])


def cmd_test(cfg, args) -> int:
    from postbot.telegram.api import TelegramAPI
    api = TelegramAPI(secret("TELEGRAM_BOT_TOKEN"))
    me = api.get_me()
    api.send_message(secret("TELEGRAM_CHAT_ID"), f"👋 hello from @{me['username']} — the connection works.")
    print(f"✓ Sent a test message via @{me['username']}")
    return 0


def cmd_preview(cfg, args) -> int:
    from postbot.preview import run_preview
    _ensure_fonts(cfg)
    sheets = run_preview(cfg, args.themes or None)
    print("✓ Previews rendered. Overview sheets:")
    for s in sheets:
        print("   ", s)
    print("Pick favourites and list them under image.themes in config.yaml.")
    return 0


def cmd_now(cfg, args) -> int:
    from postbot.pipeline import build_post, now_local, print_post, telegram
    from postbot.storage import Store
    from postbot.telegram.delivery import send_post
    _ensure_fonts(cfg)
    store = Store()
    post = build_post(cfg, store, _chain(cfg, args), day=now_local(cfg).date(), slot=args.slot,
                      fmt_angle=args.format, topic_text=args.topic, theme=args.theme,
                      offline=args.offline, record=not args.dry_run)
    print_post(post)
    if args.dry_run:
        print("\n(dry run — nothing sent)")
        return 0
    api, chat_id = telegram()
    send_post(api, chat_id, cfg, post)
    store.update_post(post["id"], delivered=True)
    print("✓ Sent to Telegram")
    return 0


def cmd_once(cfg, args) -> int:
    from postbot.pipeline import now_local, run_slot, schedule_times
    from postbot.storage import Store
    _ensure_fonts(cfg)
    store = Store()
    now = now_local(cfg)
    times = schedule_times(cfg, store)
    if args.slot is not None:
        slots = [args.slot]
    elif args.all:
        slots = list(range(len(times)))
    else:
        # every slot whose time has passed today and hasn't run yet (catches up a missed run)
        slots = [i for i, t in enumerate(times) if now.strftime("%H:%M") >= t
                 and not store.slot_done(now.date().isoformat(), i)]
    if not slots:
        print(f"Nothing due right now ({now:%H:%M} {cfg['schedule']['timezone']}; times {', '.join(times)}). "
              "Use --all to generate today's posts anyway.")
        return 0
    chain = _chain(cfg, args)
    made = failed = 0
    for slot in slots:
        m, f = run_slot(cfg, store, chain, slot, day=now.date(), dry_run=args.dry_run,
                        offline=args.offline, force=args.all or args.slot is not None,
                        interactive=args.buttons)
        made, failed = made + m, failed + f
    print(f"✓ {made} post(s) created" + (" (dry run)" if args.dry_run else " and sent")
          + (f", {failed} failed (see bot.log)" if failed else ""))
    return 1 if failed else 0


def cmd_run(cfg, args) -> int:
    from postbot.scheduler.local import run_forever
    _ensure_fonts(cfg)
    run_forever(cfg)
    return 0


def cmd_topics(cfg, args) -> int:
    from postbot.content.topics import load_topics, upcoming
    from postbot.pipeline import now_local
    from postbot.storage import Store
    c = cfg["content"]
    topics = load_topics()
    print(f"{len(topics)} topics in topics.yaml. Likely next picks:")
    for t in upcoming(topics, Store().history(), now_local(cfg).date(), args.n, c["no_repeat_days"],
                      c["dev_topic_ratio"]):
        print(f"  · [{t.label}] {t.text}")
    return 0


def cmd_cron(cfg, args) -> int:
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    tz = ZoneInfo(cfg["schedule"]["timezone"])
    print("Paste these under `schedule:` in .github/workflows/daily.yml (cron is UTC):")
    for t in cfg["schedule"]["times"]:
        h, m = map(int, t.split(":"))
        local = datetime.now(tz).replace(hour=h, minute=m, second=0, microsecond=0)
        utc = local.astimezone(ZoneInfo("UTC"))
        print(f'    - cron: "{utc.minute} {utc.hour} * * *"   # {t} {cfg["schedule"]["timezone"]}')
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bot.py", description="Daily LinkedIn content → Telegram")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("setup", help="first-run wizard")
    sub.add_parser("test", help="send a test message to Telegram")
    p = sub.add_parser("preview", help="render sample posts in every theme")
    p.add_argument("themes", nargs="*", help="only these themes")

    def gen_flags(p):
        p.add_argument("--dry-run", action="store_true", help="generate into output/ and print; don't send")
        p.add_argument("--offline", action="store_true", help="use built-in sample text instead of the AI")

    p = sub.add_parser("now", help="generate one post right now")
    gen_flags(p)
    p.add_argument("--topic", help="write about this topic")
    p.add_argument("--format", help="format:angle, e.g. carousel:tips, single:do_dont, quote:insight")
    p.add_argument("--theme", help="light | dark | accent | minimal | bold | grid")
    p.add_argument("--slot", type=int, default=0, help=argparse.SUPPRESS)

    p = sub.add_parser("once", help="make today's due posts, then exit (for cron / Task Scheduler / Actions)")
    gen_flags(p)
    p.add_argument("--all", action="store_true", help="make all of today's posts now")
    p.add_argument("--slot", type=int, help="run one specific slot (0 = first time of day)")
    p.add_argument("--buttons", action="store_true", help="add Regenerate/… buttons (needs `run` listening)")

    sub.add_parser("run", help="keep running: scheduler + Telegram commands")
    sub.add_parser("cron", help="print GitHub Actions cron lines (UTC) for your posting times")
    p = sub.add_parser("topics", help="show upcoming topics")
    p.add_argument("-n", type=int, default=10)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "setup":
        import setup
        setup.main()
        return 0
    setup_logging(args.verbose)
    cfg = load_config()
    handlers = {"test": cmd_test, "preview": cmd_preview, "now": cmd_now, "once": cmd_once,
                "run": cmd_run, "topics": cmd_topics, "cron": cmd_cron}
    try:
        return handlers[args.command](cfg, args)
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0
    except Exception as exc:  # noqa: BLE001 — top-level: report cleanly
        log.error("%s failed: %s", args.command, exc)
        log.debug("details", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
