"""Motion video renderer.

The post's slides become scenes. Each scene is a list of layers (pre-rendered sprites) with an animation
rule, and `seek(t)` composes the frame for any time t from scratch — no state carried between frames.
That makes rendering deterministic: frame 600 can be rendered without frames 0–599, and the same t
always gives the same image.
"""
from __future__ import annotations

import hashlib
import logging
import math
import random
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw

from ..images.contrast import ensure_contrast, mix
from ..images.effects import fit_into
from ..images.fonts import load_font
from ..images.graphics import GCtx, draw_graphic
from ..images.mockups import UI
from ..images.render import graphic_accents
from ..images.styles import Styler
from ..images.textfit import fit_text
from ..images.themes import get_theme
from .audio import synth
from .encode import Encoder, probe_duration
from .motion import clamp01, ease_in_cubic, ease_in_out, ease_out_cubic, fade, spring

log = logging.getLogger("video")

FORMATS = {"4:5": (1080, 1350), "9:16": (1080, 1920), "1:1": (1080, 1080), "16:9": (1920, 1080)}
EXIT = 0.38          # seconds of exit animation at the end of each scene
SCENE_LEN = {"cover": 3.9, "point": 3.5, "checklist": 3.9, "cta": 3.6, "quote": 4.5}

# How each graphic type enters (the 'motion vocabulary').
REVEALS = {
    "steps": "bands_x", "timeline": "bands_x", "compare": "bands_x", "icons": "cells",
    "checklist": "wipe_down", "layers": "wipe_up", "spectrum": "wipe_right", "type": "wipe_right",
    "phone": "device", "browser": "device",
    "palette": "pop", "components": "pop", "stat": "pop", "hero_icon": "pop",
}


def parse_format(fmt: str) -> tuple[int, int]:
    if fmt in FORMATS:
        return FORMATS[fmt]
    w, _, h = fmt.lower().partition("x")
    return int(w) // 2 * 2, int(h) // 2 * 2


@dataclass
class Layer:
    sprite: Image.Image          # RGBA
    x: int
    y: int
    start: float                 # seconds after scene start
    mode: str = "fade_up"        # rise | fade_up | pop | device | bands_x | cells | wipe_*
    clip: tuple | None = None    # visible box for 'rise' (text revealed from behind its line)
    parts: int = 1               # bands/cells count
    grid: tuple = (1, 1)         # cells (cols, rows)
    float_amp: float = 0.0       # gentle idle motion (px)


@dataclass
class Scene:
    kind: str
    start: float
    end: float
    layers: list[Layer] = field(default_factory=list)
    graphic_at: float | None = None  # when the main graphic lands (for the sound 'pop')


class VideoRenderer:
    def __init__(self, cfg: dict, theme_name: str, fmt: str = "4:5", seed: str | int = 0, fps: int | None = None):
        self.cfg = cfg
        vcfg = cfg.get("video", {})
        self.fps = int(fps or vcfg.get("fps", 30))
        self.W, self.H = parse_format(fmt)
        self.fmt = fmt
        self.k = min(self.W, self.H) / 1080          # 1.0 at 1080 on the short side
        self.M = round(72 * self.k)
        self.wide = self.W / self.H > 1.2
        self.seed = str(seed)
        # Background is painted at 2x for smooth gradients, then downsampled once.
        styler = Styler(get_theme(theme_name, cfg["brand"]), self.W * 2, self.H * 2, self.k * 2, self.M * 2)
        bg2, self.theme = styler.prepare()
        self.background = bg2.resize((self.W, self.H), Image.LANCZOS)
        self.heading = self.theme.heading_font or cfg["fonts"]["heading"]
        self.body = cfg["fonts"]["body"]
        a, b = graphic_accents(cfg["brand"], self._rng("colours"))
        self.ui = UI(a, b, self.body, self.heading)
        self.scenes: list[Scene] = []
        self.duration = 0.0
        self.base = None
        self.truncations = 0

    def px(self, v: float) -> int:
        return round(v * self.k)

    def _rng(self, salt: str) -> random.Random:
        h = hashlib.sha256(f"{self.seed}:{salt}".encode()).hexdigest()
        return random.Random(int(h[:12], 16))

    # ---- build the timeline ------------------------------------------------
    def build(self, data: dict, kicker: str = "") -> None:
        from ..content.schema import normalize_slide
        slides = [normalize_slide(s, i) if s.get("kind") not in ("cta", "quote", "checklist", "cover", "point")
                  or (s.get("kind") in ("cover", "point") and "graphic" not in s) else s
                  for i, s in enumerate(data["slides"])]
        t = 0.0
        point_no = 0
        for i, slide in enumerate(slides):
            kind = slide.get("kind", "point")
            if kind == "point":
                point_no += 1
            length = SCENE_LEN.get(kind, 3.5)
            scene = Scene(kind, t, t + length)
            self._layout_scene(scene, slide, point_no, i)
            self.scenes.append(scene)
            t += length
        self.duration = t
        self.base = self._chrome(kicker)

    def _chrome(self, kicker: str) -> Image.Image:
        """Static frame furniture drawn once: background, kicker pill, name/handle."""
        t = self.theme
        img = self.background.copy()
        d = ImageDraw.Draw(img)
        if kicker:
            font = load_font(self.body, 700, self.px(22))
            text = kicker.upper()
            w = font.getlength(text)
            fill = mix(t.bg, t.accent, 0.16)
            y = self.M
            d.rounded_rectangle((self.M, y, self.M + w + self.px(40), y + self.px(46)),
                                radius=round(self.px(23) * t.radius), fill=fill, outline=t.accent, width=2)
            d.text((self.M + self.px(20), y + self.px(23)), text, font=font, fill=ensure_contrast(t.fg, fill), anchor="lm")
        p = self.cfg["profile"]
        cy = self.H - self.M - self.px(30)
        r = self.px(28)
        shape = d.rectangle if t.radius == 0 else d.ellipse
        shape((self.M, cy - r, self.M + 2 * r, cy + r), fill=t.accent)
        initials = "".join(w[0] for w in p["name"].split()[:2]).upper() or "•"
        d.text((self.M + r, cy), initials, font=load_font(self.heading, 700, self.px(23)), fill=t.on_accent, anchor="mm")
        tx = self.M + 2 * r + self.px(16)
        d.text((tx, cy - self.px(3)), p["name"], font=load_font(self.body, 700, self.px(24)), fill=t.fg, anchor="ls")
        d.text((tx, cy + self.px(25)), p["handle"], font=load_font(self.body, 400, self.px(20)), fill=t.muted, anchor="ls")
        return img

    def _area(self):
        top = self.M + self.px(84)
        bottom = self.H - self.M - self.px(110)
        return self.M, top, self.W - 2 * self.M, bottom - top

    def _words(self, scene: Scene, text: str, x: int, y: int, w: int, h: int, max_size: int, min_size: int,
               start: float, family=None, weight=None, color=None, lh=1.08) -> int:
        """Headline as one sprite per word, rising from behind its line. Returns the y below the block."""
        t = self.theme
        family = family or self.heading
        weight = weight or t.title_weight
        fit = fit_text(text, family, weight, int(w), int(max(h, 1)), self.px(max_size), self.px(min_size), lh)
        if fit.truncated:
            self.truncations += 1
        font, color = fit.font, color or t.fg
        n = 0
        for li, line in enumerate(fit.lines):
            ly = y + li * fit.line_px
            base = round(fit.line_px * 0.5 + fit.size * 0.36)
            cx = x
            for word in line.split(" "):
                if not word:
                    continue
                ww = int(font.getlength(word)) + 4
                spr = Image.new("RGBA", (ww, int(fit.line_px * 1.25)), (0, 0, 0, 0))
                sd = ImageDraw.Draw(spr)
                if t.emboss:
                    sd.text((0, base + max(1, fit.size // 30)), word, font=font, fill=t.emboss, anchor="ls")
                sd.text((0, base), word, font=font, fill=color, anchor="ls")
                clip = (x - self.px(10), ly - self.px(4), x + w + self.px(10), ly + int(fit.line_px * 1.22))
                scene.layers.append(Layer(spr, int(cx), int(ly), start + n * 0.055, "rise", clip=clip))
                cx += font.getlength(word + " ")
                n += 1
        return y + fit.height

    def _text_sprite(self, scene, text, x, y, w, h, size, weight, color, start, family=None) -> int:
        if not text:
            return y
        fit = fit_text(text, family or self.body, weight, int(w), int(max(h, 1)), self.px(size), self.px(20), 1.35)
        spr = Image.new("RGBA", (int(w) + 8, fit.height + self.px(8)), (0, 0, 0, 0))
        d = ImageDraw.Draw(spr)
        from ..images.textfit import draw_fit
        draw_fit(d, fit, 0, 0, color)
        scene.layers.append(Layer(spr, int(x), int(y), start, "fade_up"))
        return y + fit.height

    def _graphic(self, scene: Scene, spec: dict, box, start: float, idx: int) -> None:
        x, y, w, h = (int(v) for v in box)
        if w < 60 or h < 60:
            return
        if h > w * 1.15:  # tall formats: keep a sensible picture shape and centre it in the free space
            y += int((h - w * 1.15) / 2)
            h = int(w * 1.15)
        ctx = GCtx(self.theme, self.ui, self.heading, self.body, self._rng(f"g{idx}"), self.k * 2)
        obj = draw_graphic(spec, w * 2, h * 2, ctx)
        obj = fit_into(obj, w * 2.2, h * 2.2)
        obj = obj.resize((max(1, obj.width // 2), max(1, obj.height // 2)), Image.LANCZOS)
        gx, gy = x + (w - obj.width) // 2, y + (h - obj.height) // 2
        gtype = spec.get("type", "hero_icon")
        mode = REVEALS.get(gtype, "pop")
        n = len(spec.get("items") or []) or (2 if gtype == "compare" else 3)
        grid = (1, 1)
        if gtype == "icons":
            cols = 2 if n <= 4 else 3
            grid = (cols, math.ceil(n / cols))
        if gtype == "compare":
            n = 2
        scene.layers.append(Layer(obj, gx, gy, start, mode, parts=max(1, n), grid=grid,
                                  float_amp=self.px(7) if mode in ("device", "pop") else 0))
        scene.graphic_at = scene.start + start + 0.12

    def _layout_scene(self, scene: Scene, slide: dict, point_no: int, idx: int) -> None:
        t = self.theme
        x, y, w, h = self._area()
        kind = scene.kind
        g = slide.get("graphic")
        title = slide.get("title", "")
        caption = slide.get("caption", "")
        if kind == "cta":
            gh = int(h * 0.42)
            self._graphic(scene, g or {"type": "hero_icon", "icon": "bookmark", "items": ["heart", "chat", "refresh", "star"]},
                          (x, y, w, gh), 0.15, idx)
            yb = self._words(scene, title, x, y + gh + self.px(30), w, int(h * 0.30), 86, 44, 0.55)
            yb = self._text_sprite(scene, caption, x, yb + self.px(24), w, self.px(120), 34, 500, t.body, 1.0)
            self._pill(scene, f"Follow {self.cfg['profile']['name']}", x, yb + self.px(40), 1.25)
            return
        if kind == "quote":
            qf = load_font(self.cfg["fonts"].get("serif", "dm-serif-display"), 400, self.px(260))
            spr = Image.new("RGBA", (self.px(200), self.px(220)), (0, 0, 0, 0))
            ImageDraw.Draw(spr).text((0, self.px(200)), "“", font=qf, fill=t.accent, anchor="ls")
            scene.layers.append(Layer(spr, x - self.px(8), y, 0.1, "pop"))
            yb = self._words(scene, title, x, y + self.px(220), w, int(h * 0.55), 80, 40, 0.4,
                             family=self.cfg["fonts"].get("serif", "dm-serif-display"), weight=400, lh=1.18)
            self._text_sprite(scene, caption, x, yb + self.px(30), w, self.px(120), 30, 500, t.muted, 1.4)
            return

        if self.wide:  # 16:9 — text column left, graphic right (layout, not a crop)
            tw = int(w * 0.42)
            ty = y + self.px(20)
            if kind == "point":
                ty = self._num(scene, point_no, x, ty)
            yb = self._words(scene, title, x, ty, tw, int(h * 0.55), 84, 40, 0.06)
            self._text_sprite(scene, caption, x, yb + self.px(24), tw, self.px(160), 32, 500, t.body,
                              0.3 + 0.05 * len(title.split()))
            self._graphic(scene, g or {"type": "hero_icon"}, (x + tw + self.px(40), y - self.px(20),
                                                              w - tw - self.px(40), h + self.px(40)),
                          0.35, idx)
            return

        ty = y + self.px(6)
        if kind == "point":
            ty = self._num(scene, point_no, x, ty)
        title_max = 92 if kind == "cover" else 70
        yb = self._words(scene, title, x, ty, w, int(h * 0.30), title_max, 42, 0.06)
        cap_start = 0.25 + 0.055 * len(title.split())
        yb = self._text_sprite(scene, caption, x, yb + self.px(20), w, self.px(110), 32, 500, t.body, cap_start)
        gy = yb + self.px(40)
        self._graphic(scene, g or {"type": "hero_icon"}, (x - self.px(20), gy, w + self.px(40), y + h - gy),
                      min(0.75, cap_start + 0.12), idx)

    def _num(self, scene, point_no, x, y) -> int:
        t = self.theme
        f = load_font(self.heading, 900, self.px(60))
        spr = Image.new("RGBA", (self.px(140), self.px(76)), (0, 0, 0, 0))
        ImageDraw.Draw(spr).text((0, self.px(62)), f"{point_no:02d}", font=f, fill=t.accent, anchor="ls")
        scene.layers.append(Layer(spr, x, y, 0.0, "fade_up"))
        return y + self.px(80)

    def _pill(self, scene, text, x, y, start):
        t = self.theme
        f = load_font(self.body, 700, self.px(30))
        w, h = int(f.getlength(text)) + self.px(70), self.px(84)
        spr = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(spr)
        d.rounded_rectangle((0, 0, w - 1, h - 1), radius=round(h / 2 * max(t.radius, 0.2)), fill=t.accent)
        d.text((w / 2, h / 2), text, font=f, fill=t.on_accent, anchor="mm")
        scene.layers.append(Layer(spr, x, y, start, "pop"))

    # ---- seek(t) ---------------------------------------------------------------
    def seek(self, t: float) -> Image.Image:
        """The frame at time t, computed only from t (no previous frame needed)."""
        frame = self.base.copy()
        for scene in self.scenes:
            if scene.start - 0.01 <= t < scene.end + 0.01:
                lt = t - scene.start
                length = scene.end - scene.start
                exit_q = ease_in_cubic((lt - (length - EXIT)) / EXIT) if scene is not self.scenes[-1] else 0.0
                for layer in scene.layers:
                    self._draw_layer(frame, layer, lt, length, exit_q)
        self._progress(frame, t)
        return frame

    def _progress(self, frame, t):
        d = ImageDraw.Draw(frame)
        h = max(3, self.px(6))
        d.rectangle((0, self.H - h, int(self.W * clamp01(t / max(self.duration, 0.01))), self.H), fill=self.theme.accent)

    @staticmethod
    def _alpha(sprite: Image.Image, opacity: float) -> Image.Image:
        a = sprite.getchannel("A")
        return a if opacity >= 0.999 else a.point(lambda v: int(v * opacity))

    def _paste(self, frame, sprite, x, y, opacity, clip=None):
        if opacity <= 0.003:
            return
        if clip:  # only the part inside the clip box is visible
            cx0, cy0, cx1, cy1 = clip
            sx0, sy0 = max(0, cx0 - x), max(0, cy0 - y)
            sx1, sy1 = min(sprite.width, cx1 - x), min(sprite.height, cy1 - y)
            if sx1 <= sx0 or sy1 <= sy0:
                return
            sprite = sprite.crop((sx0, sy0, sx1, sy1))
            x, y = x + sx0, y + sy0
        frame.paste(sprite.convert("RGB") if False else sprite, (int(x), int(y)), self._alpha(sprite, opacity))

    def _draw_layer(self, frame, L: Layer, lt: float, length: float, exit_q: float):
        lt0 = lt - L.start
        if lt0 < 0:
            return
        out_op = 1 - exit_q
        out_dy = -self.px(46) * exit_q
        idle = L.float_amp * math.sin(2 * math.pi * (lt / 3.2)) * clamp01(lt0 / 0.8)
        m = L.mode
        if m == "rise":
            p = spring(lt0, 260, 26)
            dy = (1 - p) * L.sprite.height * 0.95
            self._paste(frame, L.sprite, L.x, L.y + dy + out_dy, fade(lt0, 0, 0.12) * out_op,
                        clip=(L.clip[0], L.clip[1] + out_dy, L.clip[2], L.clip[3] + out_dy))
        elif m == "fade_up":
            p = spring(lt0, 170, 24)
            self._paste(frame, L.sprite, L.x, L.y + (1 - p) * self.px(28) + out_dy, fade(lt0, 0, 0.3) * out_op)
        elif m in ("pop", "device"):
            if m == "pop":
                p = spring(lt0, 190, 15)          # a touch of overshoot
                scale = 0.82 + 0.18 * p
                dy = (1 - p) * self.px(40)
            else:
                p = spring(lt0, 120, 20)
                scale = (0.95 + 0.05 * p) * (1 + 0.025 * ease_in_out(lt / length))  # slow push-in
                dy = (1 - p) * self.px(180)
            spr = L.sprite
            if abs(scale - 1) > 0.004:
                spr = spr.resize((max(1, int(spr.width * scale)), max(1, int(spr.height * scale))), Image.BILINEAR)
            x = L.x + (L.sprite.width - spr.width) / 2
            y = L.y + (L.sprite.height - spr.height) / 2 + dy + idle + out_dy
            self._paste(frame, spr, x, y, fade(lt0, 0, 0.22) * out_op)
        elif m in ("bands_x", "cells"):
            cols, rows = (L.parts, 1) if m == "bands_x" else L.grid
            bw, bh = L.sprite.width / cols, L.sprite.height / rows
            for r in range(rows):
                for c in range(cols):
                    i = r * cols + c
                    st = i * 0.17
                    p = spring(lt0 - st, 200, 22)
                    if p <= 0:
                        continue
                    box = (int(c * bw), int(r * bh), int((c + 1) * bw), int((r + 1) * bh))
                    part = L.sprite.crop(box)
                    self._paste(frame, part, L.x + box[0], L.y + box[1] + (1 - p) * self.px(46) + out_dy,
                                fade(lt0 - st, 0, 0.2) * out_op)
        elif m.startswith("wipe"):
            q = ease_out_cubic(lt0 / 0.9)
            w, h = L.sprite.size
            if m == "wipe_right":
                box = (0, 0, max(1, int(w * q)), h)
            elif m == "wipe_down":
                box = (0, 0, w, max(1, int(h * q)))
            else:  # wipe_up
                box = (0, h - max(1, int(h * q)), w, h)
            part = L.sprite.crop(box)
            self._paste(frame, part, L.x + box[0], L.y + box[1] + out_dy, fade(lt0, 0, 0.2) * out_op)

    # ---- output ------------------------------------------------------------------
    def frame_count(self) -> int:
        return int(round(self.duration * self.fps))

    def render(self, out: Path, audio: Path | None = None) -> Path:
        enc = Encoder(out, self.W, self.H, self.fps, audio)
        try:
            for f in range(self.frame_count()):
                enc.write(self.seek(f / self.fps))
        finally:
            enc.close()
        return out

    def review_times(self) -> list[float]:
        """Frames worth inspecting: each scene settled, plus just after every transition."""
        times = []
        for s in self.scenes:
            times.append(s.start + 0.45)                       # mid-entrance
            times.append(min(s.end - EXIT - 0.05, s.start + 2.4))  # settled
        return times

    def contact_sheet(self, path: Path, cols: int = 4) -> Path:
        times = self.review_times()
        thumbs = [self.seek(t).resize((self.W // 4, self.H // 4), Image.LANCZOS) for t in times]
        tw, th = thumbs[0].size
        rows = math.ceil(len(thumbs) / cols)
        sheet = Image.new("RGB", (cols * (tw + 8) + 8, rows * (th + 8) + 8), (230, 230, 232))
        for i, im in enumerate(thumbs):
            sheet.paste(im, (8 + (i % cols) * (tw + 8), 8 + (i // cols) * (th + 8)))
        sheet.save(path)
        return path

    def soundtrack(self, path: Path) -> Path:
        music = self.cfg.get("video", {}).get("music", "")
        if music and Path(music).exists():
            return Path(music)
        pops = [s.graphic_at for s in self.scenes if s.graphic_at is not None]
        return synth(self.duration, [s.start for s in self.scenes], pops, self.seed, path)

    def qa(self, video: Path) -> dict:
        """Automatic checks on the encoded file (duration, blank frames, text overflow)."""
        issues = []
        dur = probe_duration(video)
        if abs(dur - self.duration) > 0.6:
            issues.append(f"duration {dur:.1f}s, expected {self.duration:.1f}s")
        for t in self.review_times():
            fr = self.seek(t).convert("L").resize((60, 75))
            lo, hi = fr.getextrema()
            if hi - lo < 12:
                issues.append(f"frame at {t:.1f}s looks blank")
        if self.truncations:
            issues.append(f"{self.truncations} text block(s) had to be shortened")
        return {"duration": round(dur, 2), "frames": self.frame_count(), "issues": issues}
