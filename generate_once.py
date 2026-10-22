#!/usr/bin/env python3
"""Generate and send the posts that are due today, then exit.

For Windows Task Scheduler, cron or GitHub Actions. Same as `python bot.py once`.
  python generate_once.py              posts whose time has passed today and haven't been sent
  python generate_once.py --all        all of today's posts right now
  python generate_once.py --dry-run    generate into output/ without sending
"""
import sys

from bot import main

if __name__ == "__main__":
    sys.exit(main(["once", *sys.argv[1:]]))
