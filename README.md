# Daily Content Bot

Every day, at the times you choose, this bot writes LinkedIn-ready posts about design: problem solving, misconceptions, breaking the norms, trying new things, modern trends, popular brand design systems, and retro styles worth bringing back. Each post comes with an on-brand image or carousel, and the bot sends it all to you on **Telegram**. You copy the text, save the images or PDF, and post on LinkedIn yourself.

- **Free to run.** Gemini's free tier writes the text; Pillow draws the images on your machine.
- **It never touches LinkedIn.** No logging in, posting, scraping or browser automation. Telegram is only used to deliver posts to you.
- **It doesn't invent facts.** The model is told not to make up statistics, studies, quotes, clients or results, and the bot rejects drafts that look like they do.

What arrives in Telegram for each post:

1. A header: `Post 1/2 · Carousel · Topic: …` plus alt text you can paste into LinkedIn.
2. The images as an album, plus the **PDF** for carousels (LinkedIn "document" posts) or the full-quality PNG for single images.
3. The full post text in a tap-to-copy block, with buttons: **Open LinkedIn composer**, plus **Regenerate · Make it shorter · Different topic · Another theme** when the bot is running locally.

---

## Quick start (3 commands)

```bash
./run.sh setup        # Windows: run.bat setup   — the wizard asks for everything
./run.sh preview      # renders every theme into preview/ so you can pick favourites
./run.sh              # runs the schedule and listens for Telegram commands
```

`run.sh` / `run.bat` create a virtual environment and install the three dependencies (`requests`, `Pillow`, `PyYAML`) on first use. You need Python 3.11+.

If you'd rather manage things yourself: `pip install -r requirements.txt`, then `python setup.py`, then `python bot.py run`.

## Setup details

The wizard (`python setup.py`) saves secrets to `.env`, which is git-ignored, and settings to `config.yaml`, which holds no secrets. You can re-run it any time; pressing Enter keeps the current value.

**1. Telegram bot token**
1. In Telegram, open **@BotFather** and send `/newbot`.
2. Choose a name and a username ending in `bot`.
3. Paste the token (`123456789:AA…`) into the wizard.

**2. Your chat ID** is detected automatically. When the wizard asks, open your new bot and send `/start`. The wizard picks up your chat ID and sends you a test message. The bot only ever responds to this chat ID.

**3. Gemini API key (free)**
1. Go to <https://aistudio.google.com/apikey> and sign in with a Google account.
2. Click **Create API key**. No billing is needed for the free tier.
3. Paste the key. The wizard checks it and picks a current Flash model.

An optional **Groq** key (<https://console.groq.com/keys>, free) is used as a fallback if Gemini is rate-limited. If you run **Ollama** locally, it's tried last.

**4. Your details:** name, footer handle, role, brand colours (five palettes or your own hex values), fonts, posting times, timezone, posts per day and the dev-topic share.

**5. Portfolio projects (optional):** a name and 2–3 sentences for each project. With projects listed, `carousel:case_study` slots become case studies, written **only** from what you typed here. Leave the list empty to never write about your own projects.

Check the connection any time with `python bot.py test`.

## Commands

### Terminal

| Command | What it does |
|---|---|
| `python bot.py preview [theme…]` | Sample carousel + every single-card type in each theme → `preview/` (with `overview-<theme>.png` contact sheets) |
| `python bot.py now` | Make one post now and send it. Options: `--topic "…"`, `--format carousel:tips`, `--theme glass` |
| `python bot.py now --dry-run` | Generate into `output/` and print the text, **without sending** |
| `python bot.py now --dry-run --offline` | Same, using built-in sample text (no AI key needed) |
| `python bot.py run` | Local mode: scheduler + Telegram commands and buttons (Ctrl+C to stop) |
| `python generate_once.py` | Make the posts whose time has passed today, then exit (for Task Scheduler, cron or Actions). Add `--all` for all of today's posts, `--dry-run` to skip sending |
| `python bot.py topics` | Show likely upcoming topics |
| `python bot.py cron` | Print GitHub Actions cron lines (UTC) for your posting times |

### Telegram (while `run` is running)

`/now` · `/post <topic>` · `/topics` · `/add <topic>` · `/remove <topic>` · `/skip` · `/theme <name|auto>` · `/times 09:00,18:30` · `/history` · `/pause` · `/resume` · `/status` · `/help`

## How content is chosen

- **Topics:** `topics.yaml` has 66 seeded topics in 7 categories: problem solving, design misconceptions, breaking the norms, trying something new, modern design trends, brand design systems and retro revival. Each category has a `guide` that tells the writer how to approach it; for example, brand-system posts may only state what the system's public docs say. A topic isn't reused within 30 days (`content.no_repeat_days`), and recently used categories are down-weighted so the feed stays mixed.
- **Weekly format mix** (`schedule.format_plan` in `config.yaml`, one entry per daily slot):

  | Day | Morning | Evening |
  |---|---|---|
  | Mon | carousel · tips | single · do/don't |
  | Tue | single · bold statement | checklist |
  | Wed | checklist · quick tip | carousel · breakdown |
  | Thu | single · myth vs reality | quote · insight |
  | Fri | carousel · breakdown | single · before/after |
  | Sat–Sun | quote · reflective | checklist / statement |

  Formats: `carousel`, `single`, `quote`, `checklist`. Angles: `tips`, `breakdown`, `case_study`, `do_dont`, `before_after`, `bold_statement`, `myth_vs_reality`, `insight`, `reflective`, `checklist`, `quick_tip`.
- **Voice:** each post gets a different voice (a story, a mistake, a contrarian take…), and the model sees recent hooks so it doesn't repeat itself.
- **Validation:** the model must return JSON (`format, topic, hook, post_text, hashtags, slides, alt_text, image_caption`). If the JSON is malformed, the bot retries once with the errors listed. Clichés, more than 2 emoji, unverifiable "studies show…" claims, length outside 900–1300 characters and over-long slide text all trigger the same retry. Whatever is still off after the retry is fixed automatically (trimmed and tidied).

## Images

- 1080×1350 (4:5) by default. Change it with `image.width` / `image.height`.
- Six themes, rotating least recently used first:
  - `grid`: light background with a faint 8-pt grid
  - `accent`: solid brand colour
  - `gradient`: deep mesh gradient with grain and frosted cards
  - `glass`: liquid glass, with vivid blurred colour behind frosted panels and specular rims
  - `tiles`: sharp Bauhaus tile strips, square corners and hard shadows
  - `skeuo`: skeuomorphic textured paper with raised, stitched cards and embossed titles

  Keep your favourites in `image.themes`, or fix one with `/theme glass`. Every painted background is checked against WCAG AA on its **actual pixels**, and dimmed or adjusted until all text passes.
- Text **auto-fits**: it wraps, then shrinks, and only as a last resort gets cut short with "…". It never overflows. The model is told the per-field character limits.
- **Contrast check:** every theme is checked against WCAG AA (4.5:1 for body text, 3:1 for large text and accents). Colours that fail are adjusted automatically; if a theme still fails with your brand colours, the bot uses `grid` instead.
- **Illustrations** are drawn, not generated: 8-pt grid, spacing guides, type scale, contrast swatches (ratios calculated on the spot), weak vs strong buttons, form field with error state, card, hierarchy, touch targets, alignment, empty state, checklist, brand swatches.
- Fonts: Inter, Poppins, Space Grotesk, DM Sans, plus DM Serif Display for quotes. All are free Google Fonts (OFL), downloaded into `assets/fonts/` on first run. If a download fails, a system font is used.

Everything for a post is saved in `output/YYYY-MM-DD/post-N/`: `slide-01.png…`, `carousel.pdf`, `post.txt` and `meta.json`.

## Running it

### A. Local mode (on your computer)

```bash
./run.sh            # or: python bot.py run
```

Posts go out at your times, and all Telegram commands and buttons work. If the computer was asleep through a slot for more than 2 hours, that slot is skipped instead of posting late.

**No always-on process?** Schedule `generate_once.py` to run at each posting time instead:

- **Windows Task Scheduler:** Create Basic Task → Daily → 09:00 → *Start a program*:
  Program `C:\path\to\ai_poster_bot\.venv\Scripts\python.exe`, Arguments `generate_once.py`, Start in `C:\path\to\ai_poster_bot`. Add a second trigger at 18:30.
- **cron (Linux/macOS):** `crontab -e`, then
  ```
  0 9 * * *  cd /path/to/ai_poster_bot && .venv/bin/python generate_once.py
  30 18 * * * cd /path/to/ai_poster_bot && .venv/bin/python generate_once.py
  ```
  (cron uses the machine's timezone.)

### B. GitHub Actions (free; runs even when your PC is off)

1. Run `python setup.py` locally first, so `config.yaml` has your settings.
2. Create a **private** GitHub repository and push this folder. `.env` is git-ignored, so your secrets stay local. Check with `git status` before your first push.
3. In the repo, open **Settings → Secrets and variables → Actions → New repository secret** and add:
   `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GEMINI_API_KEY` (optionally `GROQ_API_KEY`).
4. Open **Actions → Daily posts → Run workflow** to try it right away.

How it behaves:
- The schedule in `.github/workflows/daily.yml` is in **UTC**: `30 3 * * *` = 09:00 IST and `0 13 * * *` = 18:30 IST. If you change your times, run `python bot.py cron` and paste the new lines into the workflow.
- **GitHub's cron isn't exact.** Runs often start 5–15 minutes late, and sometimes 30+ minutes late when GitHub is busy. If a run is missed entirely, the next run catches up on the missed post.
- After each run, the workflow commits `data/history.json` and `data/state.json`, so topics don't repeat across runs.
- **Buttons and commands (`/now`, Regenerate…) only work in local mode.** Actions runs, posts and exits, so its messages only have the "Open LinkedIn composer" button.
- Cost: each run takes about 1–2 minutes. Two runs a day is roughly 60–120 of the 2,000 free minutes a private repo gets each month.
- Don't run local mode and Actions at the same time, or you'll get duplicate posts.

## Customising

| What | Where |
|---|---|
| Topics | `topics.yaml` (any category, any text), or `/add` and `/remove` in Telegram |
| Brand colours, name, handle | `config.yaml → brand`, `profile` (or re-run `python setup.py`) |
| Fonts | `config.yaml → fonts.heading / fonts.body` (`inter`, `poppins`, `space-grotesk`, `dm-sans`) |
| Template look | `postbot/images/themes.py` (colours) and `postbot/images/styles.py` (gradient, glass, tiles, skeuo painting) |
| Themes in rotation | `config.yaml → image.themes` |
| Weekly format mix | `config.yaml → schedule.format_plan` |
| Times, posts per day | `config.yaml → schedule` (or `/times` in local mode) |
| Writing rules / voice | `postbot/content/prompts.py` |
| AI provider | `config.yaml → ai.provider` (`gemini`, `groq`, `ollama`) and `ai.fallbacks` |
| Tap-to-copy text vs. plain | `config.yaml → telegram.text_style` (`code` or `plain`) |

## Troubleshooting

| Problem | Fix |
|---|---|
| `TELEGRAM_BOT_TOKEN is missing` | Run `python setup.py` (or add the GitHub secrets for Actions). |
| `getMe: 401 Unauthorized` | The token is wrong or was revoked. Get a new one from @BotFather (`/token`) and re-run setup. |
| Chat ID not detected | Make sure you sent `/start` to *your* bot, then re-run setup, or enter the ID manually. |
| `gemini rate limit` | The free tier is per minute and per day. The bot backs off and retries, then tries Groq or Ollama if configured. Each post uses 1–2 requests. |
| `model … not found` | The bot switches to the newest available Flash model automatically. Update `ai.gemini_model` to silence the warning. |
| Text looks cut off ("…") | The model went past the limits even after the retry. Use **Regenerate**, or loosen the limits in `content/schema.py`. |
| Commands don't respond | Commands need `python bot.py run`. Only your chat ID is answered. Check `bot.log`. |
| `Conflict: terminated by other getUpdates request` | Two copies of `run` are polling at once. Stop one. |
| Actions run didn't arrive | Check the Actions tab. Scheduled runs can be late. Repos with no activity for 60 days get their schedules paused (the history commits count as activity). |
| Squares instead of symbols on images | That font lacks the glyph. The bot swaps in an ASCII equivalent; emoji are removed from images on purpose. |

Logs go to `bot.log` and the console. Secrets (tokens, keys) are redacted from all log output.

## Project layout

```
setup.py                 first-run wizard
bot.py                   CLI (preview / now / once / run / topics / cron)
generate_once.py         one-shot run for schedulers and Actions
config.yaml              settings (no secrets)  ·  .env  secrets (git-ignored)
topics.yaml              topic bank
data/                    history.json + state.json
postbot/
  providers/             gemini, groq, ollama + fallback chain with backoff
  content/               prompts, schema validation, topic rotation, generator, samples
  images/                fonts, themes, contrast, text auto-fit, illustrations, renderer
  telegram/              API client (retries, flood limits), delivery, command listener
  scheduler/             local scheduler loop
  pipeline.py            plan → generate → render → save → send
tests/                   pytest suite with a fake Telegram server (no network needed)
```

Run the tests with `pip install -r requirements-dev.txt && python -m pytest -q`.
