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
    assert len(out["images"]) == 7 and out["pdf"].exists()
    assert Image.open(out["images"][0]).size == (1080, 1350)
    pdf = out["pdf"].read_bytes()
    assert pdf.count(b"/Type /Page") - pdf.count(b"/Type /Pages") == 7
    assert r.truncations == 0


def test_all_themes_and_single_formats_render(cfg, tmp_path):
    for theme in THEME_NAMES:
        r = Renderer(cfg, theme, seed=theme)
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
    assert (post["dir"] / "post.txt").read_text().startswith("Horizontal scrolling tables")
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


def test_every_graphic_renders_in_every_layout(cfg, tmp_path):
    """Each graphic type x cover/point layout variant renders without errors or truncation."""
    from postbot.content.schema import GRAPHICS, fallback_graphic
    r = Renderer(cfg, "grid", seed=1)
    for gtype in GRAPHICS:
        for variant in ("stack", "split", "top"):
            r.cover_variant = variant
            r.point_offset = 0
            slide = {"kind": "cover", "title": "A short headline", "caption": "A caption", "graphic": {"type": gtype}}
            img = r.render_slide(slide, 0, 1, "single", "Kicker")
            assert img.size == (1080, 1350)
        for n in (1, 3):
            r.render_slide({"kind": "point", "title": "Point", "graphic": {"type": gtype}}, n, 6, "carousel", "", n)
    assert r.truncations == 0


def test_old_history_content_still_renders(cfg, tmp_path):
    """Posts generated before the graphic-first redesign can still be re-themed."""
    old = {"format": "single", "slides": [{"kind": "myth_reality", "title": "Accessible colour",
                                           "myth": "It looks dull", "reality": "Keep the brand colour", "visual": "contrast"}]}
    out = Renderer(cfg, "glass").render_post(old, tmp_path)
    assert len(out["images"]) == 1


def test_variety_between_posts(cfg):
    """Different posts get different layouts or illustration colours."""
    combos = set()
    for seed in range(12):
        r = Renderer(cfg, "grid", seed=seed)
        r._rng("layout")
        combos.add((r.ui.accent2, r._rng("layout").choice(["stack", "split", "top"])))
    assert len(combos) >= 5
