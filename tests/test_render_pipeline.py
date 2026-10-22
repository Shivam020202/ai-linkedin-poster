import json
from datetime import date, datetime

from PIL import Image

from postbot.content.sample import SINGLES, sample_post
from postbot.images.render import Renderer
from postbot.images.themes import THEME_NAMES
from postbot.pipeline import build_post, run_slot, slot_counts
from postbot.scheduler.local import due_slots


def test_carousel_renders_pngs_and_pdf(cfg, tmp_path):
    r = Renderer(cfg, "glass")
    out = r.render_post(sample_post(), tmp_path)
    assert len(out["images"]) == 9 and out["pdf"].exists()
    assert Image.open(out["images"][0]).size == (1080, 1350)
    pdf = out["pdf"].read_bytes()
    assert pdf.count(b"/Type /Page") - pdf.count(b"/Type /Pages") == 9
    assert r.truncations == 0


def test_all_themes_and_single_formats_render(cfg, tmp_path):
    for theme in THEME_NAMES:
        r = Renderer(cfg, theme)
        for kind in SINGLES:
            out = r.render_post(sample_post(kind), tmp_path / theme / kind)
            assert len(out["images"]) == 1 and out["pdf"] is None
        assert r.truncations == 0


def test_custom_size(cfg, tmp_path):
    cfg["image"].update(width=1080, height=1080)
    out = Renderer(cfg, "tiles").render_post(sample_post("checklist"), tmp_path)
    assert Image.open(out["images"][0]).size == (1080, 1080)


def test_build_post_writes_files_and_history(cfg, isolated):
    post = build_post(cfg, isolated, None, day=date(2026, 10, 26), offline=True)
    assert (post["dir"] / "post.txt").read_text().startswith("I stopped guessing")
    meta = json.loads((post["dir"] / "meta.json").read_text())
    assert meta["content"]["format"] == "carousel" and "carousel.pdf" in meta["files"]
    assert isolated.history()[-1]["id"] == post["id"]


def test_run_slot_sends_everything(cfg, isolated, fake_tg, monkeypatch):
    monkeypatch.setenv("TELEGRAM_API_BASE", fake_tg.url)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1:x")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    made, failed = run_slot(cfg, isolated, None, 0, day=date(2026, 10, 26), offline=True)
    assert (made, failed) == (1, 0)
    assert fake_tg.methods() == ["sendMessage", "sendMediaGroup", "sendDocument", "sendMessage"]
    assert isolated.slot_done("2026-10-26", 0)
    # second run of the same slot does nothing
    assert run_slot(cfg, isolated, None, 0, day=date(2026, 10, 26), offline=True) == (0, 0)


def test_failure_sends_error_message(cfg, isolated, fake_tg, monkeypatch):
    monkeypatch.setenv("TELEGRAM_API_BASE", fake_tg.url)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1:x")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")

    class Broken:
        def generate(self, *a):
            raise RuntimeError("quota exhausted")
    made, failed = run_slot(cfg, isolated, Broken(), 1, day=date(2026, 10, 26))
    assert (made, failed) == (0, 1)
    assert fake_tg.methods() == ["sendMessage"]
    assert "quota exhausted" in fake_tg.calls[0][1]["text"]


def test_pause_and_skip(cfg, isolated, fake_tg, monkeypatch):
    monkeypatch.setenv("TELEGRAM_API_BASE", fake_tg.url)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1:x")
    isolated.set_state(paused=True)
    assert run_slot(cfg, isolated, None, 0, day=date(2026, 10, 26), offline=True) == (0, 0)
    isolated.set_state(paused=False, skip_next=1)
    assert run_slot(cfg, isolated, None, 0, day=date(2026, 10, 26), offline=True) == (0, 0)
    assert isolated.state()["skip_next"] == 0


def test_slot_counts():
    assert slot_counts(2, 2) == [1, 1]
    assert slot_counts(3, 2) == [2, 1]
    assert slot_counts(2, 1) == [2]


def test_due_slots():
    now = datetime(2026, 10, 22, 9, 5)
    assert due_slots(now, ["09:00", "18:30"], set(), set()) == [0]
    assert due_slots(now, ["09:00", "18:30"], {0}, set()) == []
    assert due_slots(datetime(2026, 10, 22, 12, 0), ["09:00"], set(), set()) == []  # > 2h late: skipped
