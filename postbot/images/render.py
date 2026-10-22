"""Render post JSON into on-brand slides (PNG) and a multi-page PDF for carousels."""
from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageDraw

from . import visuals
from .contrast import ensure_contrast, mix
from .fonts import load_font
from .styles import Styler
from .textfit import Fit, draw_fit, fit_text
from .themes import Theme, get_theme, marker_colors
from .visuals import Ctx, badge, draw_visual, rrect

log = logging.getLogger("render")

KICKERS = {
    "problem": "The problem", "recap": "Recap", "checklist": "Checklist", "do_dont": "Do / Don't",
    "before_after": "Before / After", "myth_reality": "Myth vs reality",
}
PAIRS = {
    "do_dont": (("dont", "Don't", False), ("do", "Do", True)),
    "before_after": (("before", "Before", False), ("after", "After", True)),
    "myth_reality": (("myth", "Myth", False), ("reality", "Reality", True)),
}


class Renderer:
    def __init__(self, cfg: dict, theme_name: str):
        self.cfg = cfg
        self.W = int(cfg["image"]["width"])
        self.H = int(cfg["image"]["height"])
        self.k = self.W / 1080  # scale factor for non-default sizes
        self.M = round(86 * self.k)
        self.styler = Styler(get_theme(theme_name, cfg["brand"]), self.W, self.H, self.k, self.M)
        self.background, self.theme = self.styler.prepare()  # theme colours re-checked on real pixels
        self.heading = cfg["fonts"]["heading"]
        self.body = cfg["fonts"]["body"]
        self.serif = cfg["fonts"].get("serif", "dm-serif-display")
        self.ctx = Ctx(self.theme, self.heading, self.body, cfg["brand"], self.styler)
        self.truncations = 0

    def px(self, v: float) -> int:
        return round(v * self.k)

    # ---- public --------------------------------------------------------
    def render_post(self, data: dict, out_dir: Path, kicker: str = "") -> dict:
        out_dir.mkdir(parents=True, exist_ok=True)
        slides = data["slides"]
        images, paths = [], []
        tip_no = 0
        for i, slide in enumerate(slides):
            if slide["kind"] == "tip":
                tip_no += 1
            img = self.render_slide(slide, i, len(slides), data["format"], kicker, tip_no)
            path = out_dir / f"slide-{i + 1:02d}.png"
            img.save(path, compress_level=6)
            images.append(img)
            paths.append(path)
        pdf = None
        if data["format"] == "carousel":
            pdf = out_dir / "carousel.pdf"
            images[0].save(pdf, "PDF", save_all=True, append_images=images[1:], resolution=72)
        return {"images": paths, "pdf": pdf, "theme": self.theme.name}

    def render_slide(self, slide: dict, idx: int, total: int, fmt: str, kicker: str = "", tip_no: int = 0):
        t = self.theme
        img = self.background.copy()
        d = ImageDraw.Draw(img)
        self.img = self.ctx.img = img
        visuals.RADIUS_K = t.radius
        if t.style == "flat":
            self._decor(d)
        carousel = fmt == "carousel"
        kind = slide["kind"]

        top = self.M + self.px(96)
        bottom = self.H - self.M - self.px(104)
        area = (self.M, top, self.W - 2 * self.M, bottom - top)

        label = {"hook": kicker, "statement": kicker, "tip": f"Tip {tip_no}" if tip_no else "",
                 "text": "", "quote": "", "cta": ""}.get(kind, KICKERS.get(kind, ""))
        self._header(d, label if kind != "hook" else kicker, idx, total, carousel)

        if kind in PAIRS:
            self._pair(d, slide, area)
        elif kind in ("recap", "checklist"):
            self._list(d, slide, area)
        elif kind == "quote":
            self._quote(d, slide, area)
        elif kind == "cta":
            self._cta(d, slide, area)
        else:
            self._standard(d, slide, area, big=kind in ("hook", "statement"))
        self._footer(d, idx, total, carousel)
        return img

    # ---- chrome --------------------------------------------------------
    def _decor(self, d: ImageDraw.ImageDraw):
        t, W, H = self.theme, self.W, self.H
        if t.decor == "bar":
            d.rectangle((0, 0, W, self.px(14)), fill=t.accent)
        elif t.decor == "dots":
            c = mix(t.bg, t.accent, 0.28)
            for gx in range(10):
                for gy in range(3):
                    x, y = W - self.px(40) - gx * self.px(26), self.px(22) + gy * self.px(22)
                    if gx + 2 * gy < 10:
                        d.ellipse((x - 3, y - 3, x + 3, y + 3), fill=c)
        elif t.decor == "circle":
            c = mix(t.bg, (255, 255, 255), 0.07)
            r = self.px(420)
            d.ellipse((W - r * 0.9, H - r * 1.25, W + r * 1.1, H + r * 0.75), fill=c)
        elif t.decor == "block":
            d.rectangle((W - self.px(190), 0, W, self.px(16)), fill=t.fg)
            d.rectangle((0, H - self.px(16), self.px(260), H), fill=t.fg)
            d.rectangle((W - self.px(16), 0, W, self.px(190)), fill=t.fg)
        elif t.decor == "grid":
            step = self.px(40)
            for x in range(0, W, step):
                d.line([(x, 0), (x, H)], fill=t.line, width=1)
            for y in range(0, H, step):
                d.line([(0, y), (W, y)], fill=t.line, width=1)

    def _header(self, d, label: str, idx: int, total: int, carousel: bool):
        t = self.theme
        y = self.M
        if label:
            font = load_font(self.body, 700, self.px(24))
            text = label.upper()
            w = font.getlength(text)
            rrect(d, self.M, y, self.M + w + self.px(36), y + self.px(48), self.px(24),
                  fill=mix(t.bg, t.accent, 0.14), outline=t.accent, width=2)
            d.text((self.M + self.px(18), y + self.px(24)), text, font=font,
                   fill=ensure_contrast(t.fg, mix(t.bg, t.accent, 0.14)), anchor="lm")
        if carousel:
            font = load_font(self.body, 600, self.px(26))
            d.text((self.W - self.M, y + self.px(24)), f"{idx + 1}/{total}", font=font, fill=t.muted, anchor="rm")

    def _footer(self, d, idx: int, total: int, carousel: bool):
        t, p = self.theme, self.cfg["profile"]
        cy = self.H - self.M - self.px(28)
        r = self.px(30)
        x = self.M
        (d.rectangle if t.radius == 0 else d.ellipse)((x, cy - r, x + 2 * r, cy + r), fill=t.accent)
        initials = "".join(w[0] for w in p["name"].split()[:2]).upper() or "•"
        d.text((x + r, cy), initials, font=load_font(self.heading, 700, self.px(24)), fill=t.on_accent, anchor="mm")
        tx = x + 2 * r + self.px(18)
        d.text((tx, cy - self.px(4)), p["name"], font=load_font(self.body, 700, self.px(25)), fill=t.fg, anchor="ls")
        d.text((tx, cy + self.px(26)), p["handle"], font=load_font(self.body, 400, self.px(21)), fill=t.muted,
               anchor="ls")
        if not carousel:
            return
        last = idx == total - 1
        right = self.W - self.M
        if not last:
            ar = self.px(30)
            acx = right - ar
            (d.rectangle if t.radius == 0 else d.ellipse)((acx - ar, cy - ar, acx + ar, cy + ar), fill=t.accent)
            w = self.px(5)
            d.line([(acx - self.px(12), cy), (acx + self.px(11), cy)], fill=t.on_accent, width=w)
            d.line([(acx + self.px(1), cy - self.px(10)), (acx + self.px(12), cy), (acx + self.px(1), cy + self.px(10))],
                   fill=t.on_accent, width=w, joint="curve")
            right = acx - ar - self.px(24)
        dot, gap = self.px(10), self.px(22)
        for i in range(total):
            dx = right - (total - 1 - i) * gap - dot
            color = t.accent if i == idx else mix(t.bg, t.muted, 0.35)
            rad = dot / 2 if i == idx else dot / 2.6
            d.ellipse((dx + dot / 2 - rad, cy - rad, dx + dot / 2 + rad, cy + rad), fill=color)

    # ---- content layouts ----------------------------------------------
    def _fit(self, text, family, weight, w, h, max_size, min_size, lh=1.2) -> Fit:
        fit = fit_text(text, family, weight, w, h, self.px(max_size), self.px(min_size), lh)
        if fit.truncated:
            self.truncations += 1
            log.warning("text truncated to fit: %r", text[:60])
        return fit

    def _visual_box(self, slide, area, frac=0.46):
        x, y, w, h = area
        if slide.get("visual", "none") in ("", "none", None):
            return None, area
        vh = min(self.px(540), round(h * frac))
        return (x, y + h - vh, w, vh), (x, y, w, h - vh - self.px(44))

    def _place_visual(self, d, slide, x, w, top, bottom):
        """Give the illustration all the space left below the text (capped), centred in it."""
        avail = bottom - top
        vh = min(avail, self.px(620))
        draw_visual(slide["visual"], d, (x, top + (avail - vh) // 2, w, vh), self.ctx)

    def _standard(self, d, slide, area, big: bool):
        t = self.theme
        x, y, w, h = area
        has_visual = slide.get("visual", "none") not in ("", "none", None)
        gap, vgap = self.px(28), self.px(56)
        text_h = h - (self.px(400) + vgap if has_visual else 0)
        title_max = (112 if big else 74) if not has_visual else (88 if big else 68)
        title = self._fit(slide.get("title", ""), self.heading, t.title_weight, w, round(text_h * 0.62),
                          title_max, 40 if big else 36, 1.12)
        body_h = text_h - title.height - gap - (self.px(20) if big else 0)
        body = self._fit(slide.get("body", ""), self.body, t.body_weight, w, body_h, 42 if not has_visual else 38,
                         24, 1.4) if slide.get("body") and body_h > self.px(40) else None
        block_h = title.height + (gap + body.height if body else 0)
        cy = y + (h - block_h) // 2 if (big and not has_visual) else y + self.px(10)
        cy = draw_fit(d, title, x, cy, t.fg, shadow=t.emboss)
        if big:
            d.rectangle((x, cy + self.px(10), x + self.px(110), cy + self.px(20)), fill=t.accent)
            cy += self.px(20)
        if body:
            cy = draw_fit(d, body, x, cy + gap, t.body)
        if has_visual:
            self._place_visual(d, slide, x, w, cy + vgap, y + h)

    def _pair(self, d, slide, area):
        t = self.theme
        vbox, (x, y, w, h) = self._visual_box(slide, area, 0.36)
        title = self._fit(slide.get("title", ""), self.heading, t.title_weight, w, round(h * 0.26), 66, 36, 1.12)
        cy = draw_fit(d, title, x, y + self.px(6), t.fg, shadow=t.emboss) + self.px(32)
        good, bad = marker_colors(t)
        gap = self.px(24)
        ph = (y + h - cy - gap) // 2
        for i, (field, label, ok) in enumerate(PAIRS[slide["kind"]]):
            py = cy + i * (ph + gap)
            self.styler.panel(self.img, (x, py, x + w, py + ph), self.px(26), outline=good if ok else bad,
                              width=self.px(4))
            br = self.px(22)
            badge(d, x + self.px(32) + br, py + self.px(32) + br, br, ok, self.ctx)
            d.text((x + self.px(32) + 2 * br + self.px(18), py + self.px(32) + br), label.upper(),
                   font=load_font(self.body, 800, self.px(26)),
                   fill=t.on_surface if t.style in ("glass", "gradient") else (good if ok else bad), anchor="lm")
            ty = py + self.px(32) + 2 * br + self.px(18)
            room = py + ph - ty - self.px(30)
            fit = self._fit(slide.get(field, ""), self.body, 500, w - self.px(64), room, 50, 22, 1.3)
            draw_fit(d, fit, x + self.px(32), ty + max(0, (room - fit.height) // 2), t.on_surface)
        if vbox:
            draw_visual(slide["visual"], d, vbox, self.ctx)

    def _list(self, d, slide, area):
        t = self.theme
        x, y, w, h = area
        title = self._fit(slide.get("title", ""), self.heading, t.title_weight, w, round(h * 0.24), 72, 40, 1.12)
        cy = draw_fit(d, title, x, y + self.px(6), t.fg, shadow=t.emboss) + self.px(44)
        items = slide.get("items") or []
        if not items:
            return
        row_gap = self.px(22)
        row_h = min(self.px(190), (y + h - cy - row_gap * (len(items) - 1)) // len(items))
        box = self.px(48)
        tw = w - box - self.px(30)
        # one shared size so the list looks even
        size = min(self._fit(it, self.body, 500, tw - self.px(48), row_h - self.px(28), 40, 22, 1.28).size
                   for it in items)
        for it in items:
            self.styler.panel(self.img, (x, cy, x + w, cy + row_h), self.px(22), outline=t.surface, width=1)
            bx, by = x + self.px(24), cy + (row_h - box) // 2
            rrect(d, bx, by, bx + box, by + box, self.px(12), fill=t.accent)
            d.line([(bx + box * 0.25, by + box * 0.52), (bx + box * 0.43, by + box * 0.7), (bx + box * 0.76, by + box * 0.32)],
                   fill=t.on_accent, width=self.px(6), joint="curve")
            fit = fit_text(it, self.body, 500, tw - self.px(48), row_h - self.px(28), size, self.px(22), 1.28)
            draw_fit(d, fit, bx + box + self.px(26), cy + (row_h - fit.height) // 2, t.on_surface)
            cy += row_h + row_gap

    def _quote(self, d, slide, area):
        t = self.theme
        x, y, w, h = area
        qfont = load_font(self.serif, 400, self.px(260))
        d.text((x - self.px(8), y + self.px(170)), "“", font=qfont, fill=t.accent, anchor="ls")
        qy = y + self.px(190)
        quote = self._fit(slide.get("title", ""), self.serif, 400, w, round((h - self.px(190)) * 0.72), 76, 38, 1.22)
        cy = draw_fit(d, quote, x, qy, t.fg, shadow=t.emboss) + self.px(36)
        d.rectangle((x, cy, x + self.px(80), cy + self.px(6)), fill=t.accent)
        if slide.get("body"):
            sub = self._fit(slide["body"], self.body, 500, w, y + h - cy - self.px(30), 30, 22, 1.35)
            draw_fit(d, sub, x, cy + self.px(30), t.muted)

    def _cta(self, d, slide, area):
        t = self.theme
        x, y, w, h = area
        title = self._fit(slide.get("title", ""), self.heading, t.title_weight, w, round(h * 0.4), 96, 44, 1.12)
        body = self._fit(slide.get("body", ""), self.body, t.body_weight, w, round(h * 0.22), 42, 26, 1.4) \
            if slide.get("body") else None
        chip_h = self.px(84)
        total = title.height + (self.px(30) + body.height if body else 0) + self.px(70) + chip_h
        cy = y + (h - total) // 2
        cy = draw_fit(d, title, x, cy, t.fg, shadow=t.emboss)
        if body:
            cy = draw_fit(d, body, x, cy + self.px(30), t.body)
        cy += self.px(70)
        cx = x
        font = load_font(self.body, 700, self.px(28))
        for label in ("Save", "Share", "Follow"):
            cw = font.getlength(label) + self.px(64)
            rrect(d, cx, cy, cx + cw, cy + chip_h, chip_h // 2,
                  fill=t.accent if label == "Follow" else None, outline=t.accent, width=self.px(4))
            d.text((cx + cw / 2, cy + chip_h / 2), label, font=font,
                   fill=t.on_accent if label == "Follow" else ensure_contrast(t.accent, t.bg), anchor="mm")
            cx += cw + self.px(20)
