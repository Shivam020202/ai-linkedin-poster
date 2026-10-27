"""Render post JSON into designed slides (PNG) and a multi-page PDF for carousels.

Slides are graphic-first: a short headline plus an illustration/infographic that shows the idea.
Everything is drawn at 2x and downsampled for smooth edges. Layout variants are picked per post
(seeded), so consecutive posts don't look the same.
"""
from __future__ import annotations

import hashlib
import logging
import random
from pathlib import Path

from PIL import Image, ImageDraw

from .contrast import contrast_ratio, ensure_contrast, hex_to_rgb, mix
from .effects import fit_into
from .fonts import load_font
from .graphics import GCtx, draw_graphic
from .mockups import UI
from .styles import Styler
from .textfit import Fit, draw_fit, fit_text
from .themes import Theme, get_theme, hsv, hue

log = logging.getLogger("render")
SS = 2  # supersampling factor

SPLIT_OK = {"phone", "type", "stat", "hero_icon", "components"}  # graphics that suit a half-width column


def _sat(c) -> float:
    mx, mn = max(c), min(c)
    return 0 if mx == 0 else (mx - mn) / mx * (mx / 255)


COMPANION_SHIFTS = [-60, 150, -115, 40, 190]  # hue offsets for the second illustration colour


def graphic_accents(brand: dict, rng: random.Random | None = None) -> tuple:
    """Two lively colours for illustrations: the brand's most vivid colour plus a companion.
    The companion changes from post to post (seeded), so feeds don't look identical."""
    p, s = hex_to_rgb(brand["primary"]), hex_to_rgb(brand["secondary"])
    vivid = sorted([p, s], key=_sat, reverse=True)
    a = vivid[0]
    brand_pair = _sat(vivid[1]) > 0.35 and contrast_ratio(vivid[0], vivid[1]) > 1.25
    if rng is None:
        return a, vivid[1] if brand_pair else hsv(hue(a) - 60, 0.75, 0.85)
    pick = rng.randrange(len(COMPANION_SHIFTS) + (2 if brand_pair else 0))
    if pick >= len(COMPANION_SHIFTS):
        return a, vivid[1]
    return a, hsv(hue(a) + COMPANION_SHIFTS[pick], 0.72, 0.86)


class Renderer:
    def __init__(self, cfg: dict, theme_name: str, seed: str | int | None = None):
        self.cfg = cfg
        self.W = int(cfg["image"]["width"])
        self.H = int(cfg["image"]["height"])
        self.IW, self.IH = self.W * SS, self.H * SS
        self.k = self.IW / 1080
        self.M = round(80 * self.k)
        self.styler = Styler(get_theme(theme_name, cfg["brand"]), self.IW, self.IH, self.k, self.M)
        self.background, self.theme = self.styler.prepare()  # theme colours re-checked on real pixels
        self.heading = cfg["fonts"]["heading"]
        self.body = cfg["fonts"]["body"]
        self.serif = cfg["fonts"].get("serif", "dm-serif-display")
        self.seed = seed if seed is not None else random.randrange(1 << 30)
        a, b = graphic_accents(cfg["brand"], self._rng("colours"))
        self.ui = UI(a, b, self.body, self.heading)
        self.truncations = 0
        self.cover_variant, self.point_offset = "stack", 0

    def px(self, v: float) -> int:
        return round(v * self.k)

    def _rng(self, salt: str) -> random.Random:
        h = hashlib.sha256(f"{self.seed}:{salt}".encode()).hexdigest()
        return random.Random(int(h[:12], 16))

    # ---- public --------------------------------------------------------
    def render_post(self, data: dict, out_dir: Path, kicker: str = "") -> dict:
        out_dir.mkdir(parents=True, exist_ok=True)
        slides = data["slides"]
        rng = self._rng("layout")
        self.cover_variant = rng.choice(["stack", "split", "top"])
        self.point_offset = rng.randrange(2)
        images, paths = [], []
        point_no = 0
        for i, slide in enumerate(slides):
            if slide.get("kind") not in ("cover", "quote", "checklist", "cta"):
                point_no += 1
            img = self.render_slide(slide, i, len(slides), data["format"], kicker, point_no)
            path = out_dir / f"slide-{i + 1:02d}.png"
            img.save(path, compress_level=6)
            images.append(img)
            paths.append(path)
        pdf = None
        if data["format"] == "carousel":
            pdf = out_dir / "carousel.pdf"
            images[0].save(pdf, "PDF", save_all=True, append_images=images[1:], resolution=72)
        return {"images": paths, "pdf": pdf, "theme": self.theme.name}

    def render_slide(self, slide: dict, idx: int, total: int, fmt: str, kicker: str = "", point_no: int = 1):
        from ..content.schema import KINDS, normalize_slide
        if slide.get("kind") not in KINDS or (slide.get("kind") in ("cover", "point") and "graphic" not in slide):
            slide = normalize_slide(slide, idx)  # old-style content from history
        t = self.theme
        img = self.background.copy()
        d = ImageDraw.Draw(img)
        self.img = img
        if t.style == "flat":
            self._decor(d)
        carousel = fmt == "carousel"
        kind = slide.get("kind", "point")
        top = self.M + self.px(84)
        bottom = self.IH - self.M - self.px(100)
        area = (self.M, top, self.IW - 2 * self.M, bottom - top)
        self._gctx = GCtx(t, self.ui, self.heading, self.body, self._rng(f"g{idx}"), self.k)

        label = kicker if kind in ("cover", "quote") else ("Checklist" if kind == "checklist" else "")
        self._header(d, label, idx, total, carousel)
        if kind == "cover":
            self._cover(d, slide, area)
        elif kind == "quote":
            self._quote(d, slide, area)
        elif kind == "checklist":
            self._checklist(d, slide, area)
        elif kind == "cta":
            self._cta(d, slide, area)
        else:
            self._point(d, slide, area, max(1, point_no))
        self._footer(d, idx, total, carousel)
        return img.resize((self.W, self.H), Image.LANCZOS)

    # ---- chrome --------------------------------------------------------
    def _decor(self, d: ImageDraw.ImageDraw):
        t, W, H = self.theme, self.IW, self.IH
        if t.decor == "circle":
            c = mix(t.bg, (255, 255, 255), 0.07)
            r = self.px(420)
            d.ellipse((W - r * 0.9, H - r * 1.25, W + r * 1.1, H + r * 0.75), fill=c)
        elif t.decor == "grid":
            step = self.px(40)
            for x in range(0, W, step):
                d.line([(x, 0), (x, H)], fill=t.line, width=SS)
            for y in range(0, H, step):
                d.line([(0, y), (W, y)], fill=t.line, width=SS)

    def _rr(self, d, box, r, **kw):
        d.rounded_rectangle(box, radius=round(r * self.theme.radius), **kw)

    def _header(self, d, label: str, idx: int, total: int, carousel: bool):
        t = self.theme
        y = self.M
        if label:
            font = load_font(self.body, 700, self.px(22))
            text = label.upper()
            w = font.getlength(text)
            fill = mix(t.bg, t.accent, 0.16)
            self._rr(d, (self.M, y, self.M + w + self.px(40), y + self.px(46)), self.px(23), fill=fill,
                     outline=t.accent, width=SS * 2)
            d.text((self.M + self.px(20), y + self.px(23)), text, font=font, fill=ensure_contrast(t.fg, fill), anchor="lm")
        if carousel:
            font = load_font(self.body, 700, self.px(24))
            d.text((self.IW - self.M, y + self.px(23)), f"{idx + 1:02d} / {total:02d}", font=font, fill=t.muted, anchor="rm")

    def _footer(self, d, idx: int, total: int, carousel: bool):
        t, p = self.theme, self.cfg["profile"]
        cy = self.IH - self.M - self.px(26)
        r = self.px(28)
        x = self.M
        shape = d.rectangle if t.radius == 0 else d.ellipse
        shape((x, cy - r, x + 2 * r, cy + r), fill=t.accent)
        initials = "".join(w[0] for w in p["name"].split()[:2]).upper() or "•"
        d.text((x + r, cy), initials, font=load_font(self.heading, 700, self.px(23)), fill=t.on_accent, anchor="mm")
        tx = x + 2 * r + self.px(16)
        d.text((tx, cy - self.px(3)), p["name"], font=load_font(self.body, 700, self.px(24)), fill=t.fg, anchor="ls")
        d.text((tx, cy + self.px(25)), p["handle"], font=load_font(self.body, 400, self.px(20)), fill=t.muted, anchor="ls")
        if not carousel:
            return
        right = self.IW - self.M
        if idx < total - 1:
            ar = self.px(28)
            acx = right - ar
            shape((acx - ar, cy - ar, acx + ar, cy + ar), fill=t.accent)
            w = self.px(5)
            d.line([(acx - self.px(11), cy), (acx + self.px(10), cy)], fill=t.on_accent, width=w)
            d.line([(acx + self.px(1), cy - self.px(9)), (acx + self.px(11), cy), (acx + self.px(1), cy + self.px(9))],
                   fill=t.on_accent, width=w, joint="curve")
            right = acx - ar - self.px(22)
        dot, gap = self.px(10), self.px(20)
        for i in range(total):
            dx = right - (total - 1 - i) * gap - dot
            color = t.accent if i == idx else mix(t.bg, t.muted, 0.4)
            rad = dot / 2 if i == idx else dot / 2.8
            d.ellipse((dx + dot / 2 - rad, cy - rad, dx + dot / 2 + rad, cy + rad), fill=color)

    # ---- helpers --------------------------------------------------------
    def _fit(self, text, family, weight, w, h, max_size, min_size, lh=1.1) -> Fit:
        fit = fit_text(text, family, weight, int(w), int(max(h, 1)), self.px(max_size), self.px(min_size), lh)
        if fit.truncated:
            self.truncations += 1
            log.warning("text truncated to fit: %r", text[:60])
        return fit

    def _text_block(self, d, slide, x, y, w, h, title_max, title_min=40, caption_max=34, align_bottom=False,
                    center_v=False):
        """Headline (+ caption) inside a box; returns the y below the block."""
        t = self.theme
        caption = slide.get("caption") or ""
        title = self._fit(slide.get("title", ""), self.heading, t.title_weight, w, h * (0.74 if caption else 1),
                          title_max, title_min, 1.08)
        gap = self.px(22)
        cap = self._fit(caption, self.body, min(900, t.body_weight + 100), w, h - title.height - gap, caption_max, 22,
                        1.35) if caption and h - title.height - gap > self.px(30) else None
        block = title.height + (gap + cap.height if cap else 0)
        if align_bottom:
            y = y + h - block
        elif center_v:
            y = y + (h - block) // 2
        y = draw_fit(d, title, x, y, t.fg, shadow=t.emboss)
        if cap:
            y = draw_fit(d, cap, x, y + gap, t.body)
        return y

    def _place(self, spec, box, anchor="center"):
        """Draw a graphic into box=(x, y, w, h); the box may extend past the canvas (bleed)."""
        x, y, w, h = (int(v) for v in box)
        if w < 50 or h < 50:
            return
        obj = draw_graphic(spec, w, h, self._gctx)
        obj = fit_into(obj, w * 1.1, h * 1.1)  # soft shadows may spill a little past the box
        ox = x + (w - obj.width) // 2
        oy = y + (h - obj.height) // 2 if anchor == "center" else (y + h - obj.height if anchor == "bottom" else y)
        self.img.paste(obj, (ox, oy), obj)

    # ---- layouts ---------------------------------------------------------
    def _cover(self, d, slide, area):
        x, y, w, h = area
        g = slide.get("graphic") or {"type": "hero_icon"}
        variant = self.cover_variant
        if variant == "split" and g.get("type") not in SPLIT_OK:
            variant = "stack"  # wide diagrams need the full width
        if variant == "split":
            tw = int(w * 0.54)
            self._text_block(d, slide, x, y, tw, h, 92, 46, 32, center_v=True)
            bleed = self.px(120)
            self._place(g, (x + tw + self.px(10), y - self.px(30), w - tw + bleed, h + self.px(60)))
        elif variant == "top":
            gh = int(h * 0.60)
            self._place(g, (x - self.px(20), y, w + self.px(40), gh))
            self._text_block(d, slide, x, y + gh + self.px(30), w, h - gh - self.px(30), 86, 44, 32, align_bottom=True)
        else:  # stack: headline first, picture fills the rest
            th = int(h * 0.36)
            yb = self._text_block(d, slide, x, y + self.px(6), w, th, 96, 48, 34)
            d.rectangle((x, yb + self.px(18), x + self.px(96), yb + self.px(28)), fill=self.theme.accent)
            gy = yb + self.px(50)
            self._place(g, (x - self.px(20), gy, w + self.px(40), y + h - gy))

    def _point(self, d, slide, area, point_no):
        t = self.theme
        x, y, w, h = area
        g = slide.get("graphic") or {"type": "hero_icon"}
        num = f"{point_no:02d}"
        nf = load_font(self.heading, 900, self.px(64))
        variant = (point_no + self.point_offset) % 2
        if g.get("type") in ("phone", "type", "stat"):
            variant = 2 if point_no % 2 else variant  # tall objects look best beside the headline
        if variant == 0:  # number + headline on top, picture below
            d.text((x, y + self.px(56)), num, font=nf, fill=t.accent, anchor="ls")
            yb = self._text_block(d, slide, x, y + self.px(80), w, int(h * 0.30), 68, 40, 32)
            gy = yb + self.px(36)
            self._place(g, (x - self.px(20), gy, w + self.px(40), y + h - gy))
        elif variant == 1:  # picture first, headline anchored at the bottom
            gh = int(h * 0.62)
            self._place(g, (x - self.px(20), y, w + self.px(40), gh))
            ty = y + gh + self.px(24)
            d.text((x, ty + self.px(48)), num, font=load_font(self.heading, 900, self.px(46)), fill=t.accent, anchor="ls")
            self._text_block(d, slide, x, ty + self.px(64), w, y + h - ty - self.px(64), 60, 36, 30)
        else:  # split: headline column + device bleeding off the right edge
            tw = int(w * 0.46)
            d.text((x, y + self.px(56)), num, font=nf, fill=t.accent, anchor="ls")
            self._text_block(d, slide, x, y + self.px(80), tw, h - self.px(80), 64, 36, 30, center_v=True)
            self._place(g, (x + tw, y - self.px(20), w - tw + self.px(140), h + self.px(40)))

    def _quote(self, d, slide, area):
        t = self.theme
        x, y, w, h = area
        g = slide.get("graphic")
        if g:  # small illustration in the top-right corner, clear of the quote text
            gs = self.px(250)
            self._place(g, (x + w - gs + self.px(20), y - self.px(30), gs, gs))
        qfont = load_font(self.serif, 400, self.px(300))
        d.text((x - self.px(10), y + self.px(220)), "“", font=qfont, fill=t.accent, anchor="ls")
        qy = y + self.px(250)
        quote = self._fit(slide.get("title", ""), self.serif, 400, w, (h - self.px(250)) * 0.78, 84, 40, 1.18)
        cy = draw_fit(d, quote, x, qy, t.fg, shadow=t.emboss) + self.px(34)
        d.rectangle((x, cy, x + self.px(90), cy + self.px(8)), fill=t.accent)
        if slide.get("caption"):
            sub = self._fit(slide["caption"], self.body, 500, w, y + h - cy - self.px(30), 30, 22, 1.35)
            draw_fit(d, sub, x, cy + self.px(34), t.muted)

    def _checklist(self, d, slide, area):
        x, y, w, h = area
        yb = self._text_block(d, slide, x, y + self.px(6), w, int(h * 0.28), 80, 44, 30)
        gy = yb + self.px(40)
        g = slide.get("graphic") or {"type": "checklist", "items": slide.get("items") or []}
        self._place(g, (x - self.px(10), gy, w + self.px(20), y + h - gy), anchor="top")

    def _cta(self, d, slide, area):
        t = self.theme
        x, y, w, h = area
        gh = int(h * 0.46)
        self._place(slide.get("graphic") or {"type": "hero_icon", "icon": "bookmark",
                                             "items": ["heart", "chat", "refresh", "star"]}, (x, y, w, gh))
        yb = self._text_block(d, slide, x, y + gh + self.px(20), w, h - gh - self.px(150), 84, 44, 32)
        chip_h = self.px(80)
        cy = min(max(yb + self.px(40), y + h - chip_h), y + h - chip_h)
        cx = x
        font = load_font(self.body, 700, self.px(28))
        for label in ("Save", "Share", "Follow"):
            cw = font.getlength(label) + self.px(64)
            fill = t.accent if label == "Follow" else None
            self._rr(d, (cx, cy, cx + cw, cy + chip_h), chip_h // 2, fill=fill, outline=t.accent, width=self.px(4))
            d.text((cx + cw / 2, cy + chip_h / 2), label, font=font,
                   fill=t.on_accent if fill else ensure_contrast(t.accent, t.bg), anchor="mm")
            cx += cw + self.px(18)


__all__ = ["Renderer", "Theme", "graphic_accents"]
