import json
import wave
from datetime import date

import pytest

from postbot.content.sample import sample_post
from postbot.video.motion import multi_spring, spring
from postbot.video.render import VideoRenderer, parse_format


def small(cfg):
    cfg["video"] = {"fps": 8, "formats": ["270x338"], "audio": True, "music": ""}
    return cfg


def short_post():
    post = sample_post()
    post["slides"] = [post["slides"][0], post["slides"][4], post["slides"][-1]]  # cover, steps point, cta
    return post


def test_spring_is_closed_form():
    assert spring(0) == 0 and spring(-1) == 0
    assert spring(2.0) == pytest.approx(1, abs=1e-3)
    assert 0 < spring(0.1) < spring(0.2) < 1
    assert max(spring(t / 100, 190, 12) for t in range(200)) > 1  # low damping overshoots
    assert multi_spring(5, 10, [(0, 5), (1, -2)]) == pytest.approx(13, abs=1e-3)


def test_parse_format():
    assert parse_format("9:16") == (1080, 1920)
    assert parse_format("271x339") == (270, 338)  # even sizes for H.264


def test_seek_is_deterministic_and_order_independent(cfg):
    v = VideoRenderer(small(cfg), "grid", "270x338", seed="t")
    v.build(short_post(), "Kicker")
    late = v.seek(5.0).tobytes()          # jump straight to a late frame…
    for t in (0, 1.2, 3.3):
        v.seek(t)                          # …render others in any order…
    assert v.seek(5.0).tobytes() == late  # …and the same t still gives the same frame


def test_frames_change_over_time(cfg):
    v = VideoRenderer(small(cfg), "noir", "270x338", seed="t")
    v.build(short_post())
    assert v.seek(0.0).tobytes() != v.seek(1.5).tobytes()
    assert len(v.scenes) == 3 and v.duration > 9


def test_render_encodes_mp4_with_audio(cfg, tmp_path):
    v = VideoRenderer(small(cfg), "glass", "270x338", seed="t", fps=8)
    v.build(short_post())
    wav = v.soundtrack(tmp_path / "s.wav")
    with wave.open(str(wav)) as w:
        assert abs(w.getnframes() / w.getframerate() - v.duration) < 0.05
    out = v.render(tmp_path / "v.mp4", wav)
    report = v.qa(out)
    assert out.stat().st_size > 10_000
    assert report["issues"] == [], report
    assert v.contact_sheet(tmp_path / "sheet.png").exists()


def test_every_graphic_type_animates(cfg):
    from postbot.content.schema import GRAPHICS
    v = VideoRenderer(small(cfg), "grid", "270x338", seed="g")
    slides = [{"kind": "point", "title": f"Point {g}", "graphic": {"type": g}} for g in GRAPHICS]
    v.build({"format": "carousel", "slides": slides})
    for s in v.scenes:
        assert s.graphic_at is not None
        v.seek(s.start + 0.6)   # mid-entrance
        v.seek(s.start + 2.5)   # settled


def test_daily_video_slot_sends_and_records(cfg, isolated, fake_tg, monkeypatch):
    import postbot.video_pipeline as vp
    monkeypatch.setattr(vp, "OUTPUT_DIR", isolated.history_path.parent.parent / "output")
    monkeypatch.setattr(vp, "ROOT", isolated.history_path.parent.parent)
    monkeypatch.setenv("TELEGRAM_API_BASE", fake_tg.url)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1:x")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    made, failed = vp.run_video_slot(small(cfg), isolated, None, day=date(2026, 10, 26), offline=True)
    assert (made, failed) == (1, 0)
    assert fake_tg.methods() == ["sendMessage", "sendVideo", "sendMessage"]
    assert "video" in fake_tg.calls[1][2]
    entry = isolated.history()[-1]
    assert entry["format"] == "video" and "-v" in entry["id"]
    assert isolated.slot_done("2026-10-26", vp.VIDEO_SLOT)
    meta = json.loads((isolated.history_path.parent.parent / entry["dir"] / "meta.json").read_text())
    assert meta["videos"][0]["qa"]["issues"] == []
    # already done today -> nothing
    assert vp.run_video_slot(small(cfg), isolated, None, day=date(2026, 10, 26), offline=True) == (0, 0)


def test_video_due(cfg, isolated):
    from datetime import datetime
    from postbot.video_pipeline import video_due
    assert video_due(cfg, isolated, datetime(2026, 10, 26, 13, 5), ["13:00"])
    assert not video_due(cfg, isolated, datetime(2026, 10, 26, 12, 55), ["13:00"])
    cfg["video"] = {"enabled": False}
    assert not video_due(cfg, isolated, datetime(2026, 10, 26, 13, 5), ["13:00"])
