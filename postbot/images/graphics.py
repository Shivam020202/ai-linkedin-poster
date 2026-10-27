"""Infographics & illustrations. Each graphic returns an RGBA object (with its own shadow) that the
renderer places on the slide. Specs come from the model, so the picture is about the post's topic.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from PIL import Image, ImageDraw

from .contrast import contrast_ratio, ensure_contrast, hex_to_rgb, mix
from .effects import (diag_gradient, drop_shadow, fit_into, gloss, layer, rgba, rotate, rounded_mask, sticker,
                      tilt)
from .fonts import load_font
from .icons import ICONS, icon
from .mockups import BAD, GOOD, INK, SCREENS, UI, WEB, browser, phone
from .themes import Theme

WHITE = (255, 255, 255)
CARD_INK = (24, 26, 36)
CARD_MUTED = (100, 104, 118)


@dataclass
class GCtx:
    theme: Theme
    ui: UI
    heading: str
    body: str
    rng: random.Random
    ss: float  # pixels per design unit (1 at 1080 wide)

    @property
    def a(self):
        return self.ui.accent

    @property
    def b(self):
        return self.ui.accent2


def _font(ctx, size, weight=600, family=None):
    return load_font(family or ctx.body, weight, max(8, int(size * ctx.ss)))


def _label_w(ctx, text, size, weight=600):
    return _font(ctx, size, weight).getlength(text)


def _pill(ctx, text, size=26, fill=WHITE, color=CARD_INK, icon_name=None, icon_color=None):
    f = _font(ctx, size, 700)
    pad = int(size * 0.75 * ctx.ss)
    ic = int(size * 1.05 * ctx.ss) if icon_name else 0
    w = int(f.getlength(text) + 2 * pad + (ic + pad * 0.6 if ic else 0))
    h = int(size * 2.1 * ctx.ss)
    obj = layer(w, h)
    d = ImageDraw.Draw(obj)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=h // 2, fill=rgba(fill))
    x = pad
    if ic:
        obj.alpha_composite(icon(icon_name, ic, icon_color or color), (x, (h - ic) // 2))
        x += int(ic + pad * 0.6)
    d.text((x, h / 2), text, font=f, fill=rgba(ensure_contrast(color, fill, 4.5)), anchor="lm")
    return obj


def _shadow(obj, ctx, blur=26, dy=22, opacity=0.32):
    return drop_shadow(obj, int(blur * ctx.ss), (0, int(dy * ctx.ss)), (10, 10, 25), opacity)


def _icon_name(name, fallback="sparkle"):
    return name if name in ICONS else fallback


def _tile(ctx, size, icon_name, a, b, radius=0.28):
    """Glossy gradient app-icon style tile."""
    s = int(size)
    g = diag_gradient((s, s), a, b)
    g.putalpha(rounded_mask((s, s), int(s * radius)))
    on = ensure_contrast(WHITE, mix(a, b, 0.5), 3.0)
    ic = icon(_icon_name(icon_name), int(s * 0.5), on)
    g.alpha_composite(ic, ((s - ic.width) // 2, (s - ic.height) // 2))
    return gloss(g, 0.3)


# ---- device graphics -----------------------------------------------------------
def g_phone(spec, w, h, ctx):
    ph = phone(spec.get("screen", "list"), ctx.ui, int(h * 0.92), spec.get("title", ""), spec.get("items"))
    if spec.get("tilt", True):
        ph = tilt(ph, 0.10, ctx.rng.choice(["left", "right"]))
    return fit_into(_shadow(ph, ctx, 40, 34, 0.38), w, h)


def g_browser(spec, w, h, ctx):
    br = browser(spec.get("layout", "hero"), ctx.ui, int(w * 0.9), spec.get("title", ""), spec.get("items"))
    if spec.get("tilt", True):
        br = tilt(br, 0.07, ctx.rng.choice(["left", "right"]))
    return fit_into(_shadow(br, ctx, 40, 30, 0.35), w, h)


def g_compare(spec, w, h, ctx):
    """Two devices side by side: the weak version and the better one."""
    labels = (spec.get("left_label") or "Before", spec.get("right_label") or "After")
    screens = (spec.get("left_screen") or "cluttered", spec.get("right_screen") or "cards")
    winner = spec.get("winner", "right")
    obj = layer(w, h)
    ph_h = int(h * 0.80)
    for i in range(2):
        scr = screens[i]
        if scr in WEB:
            dev = browser(scr, ctx.ui, int(w * 0.46), spec.get("title", ""), spec.get("items"))
        else:
            dev = phone(scr if scr in SCREENS else "list", ctx.ui, ph_h, spec.get("title", ""), spec.get("items"))
        dev = rotate(dev, 4 if i == 0 else -4)
        dev = _shadow(dev, ctx, 30, 26, 0.35)
        dev = fit_into(dev, w * 0.52, h * 0.86)
        x = int(w * (0.25 + 0.5 * i) - dev.width / 2)
        obj.alpha_composite(dev, (x, 0))
        ok = (i == 1) == (winner == "right") if winner in ("left", "right") else None
        col = GOOD if ok else BAD if ok is False else CARD_INK
        pill = _pill(ctx, labels[i][:16], 26, WHITE, col, "check" if ok else "cross" if ok is False else None, col)
        pill = _shadow(pill, ctx, 12, 8, 0.25)
        obj.alpha_composite(pill, (int(w * (0.25 + 0.5 * i) - pill.width / 2), h - pill.height))
    return obj


# ---- diagrams -------------------------------------------------------------------
def g_steps(spec, w, h, ctx):
    items = (spec.get("items") or [])[:5] or [{"icon": "bulb", "label": "Idea"}, {"icon": "brush", "label": "Design"},
                                              {"icon": "check", "label": "Ship"}]
    items = [i if isinstance(i, dict) else {"label": str(i), "icon": "sparkle"} for i in items]
    n = len(items)
    obj = layer(w, h)
    d = ImageDraw.Draw(obj)
    tile = min(w / (n * 1.35), h * 0.46)
    cy = h * 0.42
    xs = [w * (i + 0.5) / n for i in range(n)]
    ys = [cy + (tile * 0.28 if i % 2 else -tile * 0.28) for i in range(n)]
    lc = ctx.theme.fg
    for i in range(n - 1):  # dashed curved connectors
        x0, y0, x1, y1 = xs[i] + tile * 0.55, ys[i], xs[i + 1] - tile * 0.55, ys[i + 1]
        steps = 22
        for k in range(0, steps, 2):
            t0, t1 = k / steps, (k + 1) / steps
            p0 = (x0 + (x1 - x0) * t0, y0 + (y1 - y0) * t0 - math.sin(math.pi * t0) * tile * 0.25)
            p1 = (x0 + (x1 - x0) * t1, y0 + (y1 - y0) * t1 - math.sin(math.pi * t1) * tile * 0.25)
            d.line([p0, p1], fill=rgba(mix(lc, ctx.theme.bg, 0.35)), width=max(3, int(4 * ctx.ss)))
    cols = [(ctx.a, ctx.b), (ctx.b, ctx.a)]
    for i, it in enumerate(items):
        a, b = cols[i % 2]
        t = _shadow(_tile(ctx, tile, it.get("icon", "sparkle"), a, b), ctx, 18, 14, 0.3)
        obj.alpha_composite(t, (int(xs[i] - t.width / 2), int(ys[i] - t.height / 2)))
        num = _pill(ctx, str(i + 1), 18, WHITE, CARD_INK)
        obj.alpha_composite(num, (int(xs[i] + tile * 0.30), int(ys[i] - tile * 0.62)))
        lab = str(it.get("label", ""))[:18]
        f = _font(ctx, 30 if n <= 3 else 26, 700)
        d.text((xs[i], ys[i] + tile * 0.75), lab, font=f, fill=rgba(ctx.theme.fg), anchor="ma")
    return obj


def g_icons(spec, w, h, ctx):
    items = (spec.get("items") or [])[:6] or [{"icon": "type", "label": "Type"}, {"icon": "palette", "label": "Colour"},
                                              {"icon": "grid", "label": "Layout"}, {"icon": "play", "label": "Motion"}]
    items = [i if isinstance(i, dict) else {"label": str(i), "icon": "sparkle"} for i in items]
    n = len(items)
    cols = 2 if n <= 4 else 3
    rows = math.ceil(n / cols)
    obj = layer(w, h)
    cw, ch = w / cols, h / rows
    card = min(cw * 0.86, ch * 0.88)
    for i, it in enumerate(items):
        cx, cy = cw * (i % cols + 0.5), ch * (i // cols + 0.5)
        c = layer(card, card)
        d = ImageDraw.Draw(c)
        d.rounded_rectangle((0, 0, card - 1, card - 1), radius=int(card * 0.14), fill=rgba(WHITE))
        a, b = (ctx.a, ctx.b) if i % 2 == 0 else (ctx.b, ctx.a)
        t = _tile(ctx, card * 0.42, it.get("icon", "sparkle"), a, b)
        c.alpha_composite(t, (int(card * 0.12), int(card * 0.12)))
        f = _font(ctx, 30, 750, ctx.heading)
        lab = str(it.get("label", ""))[:16]
        while f.getlength(lab) > card * 0.8 and f.size > 14:
            f = load_font(ctx.heading, 750, f.size - 2)
        d.text((card * 0.12, card * 0.80), lab, font=f, fill=rgba(CARD_INK), anchor="ls")
        c = _shadow(c, ctx, 20, 16, 0.25)
        c = rotate(c, ctx.rng.uniform(-3, 3))
        obj.alpha_composite(c, (int(cx - c.width / 2), int(cy - c.height / 2)))
    return obj


def g_timeline(spec, w, h, ctx):
    items = (spec.get("items") or [])[:5] or [{"year": "2007", "label": "Skeuomorphic"},
                                              {"year": "2013", "label": "Flat"}, {"year": "Now", "label": "Depth"}]
    items = [i if isinstance(i, dict) else {"year": "", "label": str(i)} for i in items]
    n = len(items)
    obj = layer(w, h)
    d = ImageDraw.Draw(obj)
    y = h * 0.5
    d.line([(w * 0.04, y), (w * 0.96, y)], fill=rgba(mix(ctx.theme.fg, ctx.theme.bg, 0.3)), width=max(4, int(6 * ctx.ss)))
    cw = w / n
    for i, it in enumerate(items):
        x = cw * (i + 0.5)
        last = i == n - 1
        r = 18 * ctx.ss if not last else 26 * ctx.ss
        d.ellipse((x - r, y - r, x + r, y + r), fill=rgba(ctx.a if last else WHITE),
                  outline=rgba(ctx.theme.fg), width=max(3, int(4 * ctx.ss)))
        card_w, card_h = cw * 0.88, h * 0.34
        c = layer(card_w, card_h)
        cd = ImageDraw.Draw(c)
        fillc = WHITE
        cd.rounded_rectangle((0, 0, card_w - 1, card_h - 1), radius=int(card_h * 0.16), fill=rgba(fillc))
        yr = str(it.get("year", ""))[:6]
        fy = load_font(ctx.heading, 850, int(card_h * 0.36))
        while fy.getlength(yr) > card_w * 0.8 and fy.size > 14:
            fy = load_font(ctx.heading, 850, fy.size - 3)
        cd.text((card_w * 0.1, card_h * 0.1), yr, font=fy,
                fill=rgba(ensure_contrast(ctx.a if last else CARD_INK, WHITE, 3)), anchor="la")
        lab = str(it.get("label", ""))[:20]
        fl = load_font(ctx.body, 650, int(card_h * 0.16))
        while fl.getlength(lab) > card_w * 0.84 and fl.size > 12:
            fl = load_font(ctx.body, 650, fl.size - 2)
        cd.text((card_w * 0.1, card_h * 0.84), lab, font=fl, fill=rgba(CARD_MUTED), anchor="ls")
        c = _shadow(c, ctx, 16, 12, 0.25)
        top = i % 2 == 0
        obj.alpha_composite(c, (int(x - c.width / 2), int((y - card_h - h * 0.08 if top else y + h * 0.08) - (c.height - card_h) / 2)))
    return obj


def g_spectrum(spec, w, h, ctx):
    left, right = str(spec.get("left", "Minimal"))[:16], str(spec.get("right", "Maximal"))[:16]
    pos = max(0.05, min(0.95, float(spec.get("marker", 65) or 65) / 100))
    label = str(spec.get("marker_label", "Sweet spot"))[:18]
    obj = layer(w, h)
    track_h = int(h * 0.12)
    tw = int(w * 0.9)
    tx, ty = int(w * 0.05), int(h * 0.48)
    track = diag_gradient((tw, track_h), mix(ctx.a, WHITE, 0.15), ctx.b)
    track.putalpha(rounded_mask(track.size, track_h // 2))
    obj.alpha_composite(_shadow(track, ctx, 14, 10, 0.25), (tx - int(42 * ctx.ss), ty - int(42 * ctx.ss) + int(4 * ctx.ss)))
    d = ImageDraw.Draw(obj)
    for k in range(1, 10):  # tick marks
        x = tx + tw * k / 10
        d.line([(x, ty + track_h + 14 * ctx.ss), (x, ty + track_h + 30 * ctx.ss)],
               fill=rgba(mix(ctx.theme.fg, ctx.theme.bg, 0.4)), width=max(2, int(3 * ctx.ss)))
    kr = int(track_h * 1.05)
    knob = layer(2 * kr, 2 * kr)
    ImageDraw.Draw(knob).ellipse((0, 0, 2 * kr - 1, 2 * kr - 1), fill=rgba(WHITE))
    ImageDraw.Draw(knob).ellipse((kr * 0.45, kr * 0.45, kr * 1.55, kr * 1.55), fill=rgba(ctx.a))
    knob = _shadow(gloss(knob, 0.3), ctx, 16, 10, 0.35)
    kx = tx + tw * pos
    obj.alpha_composite(knob, (int(kx - knob.width / 2), int(ty + track_h / 2 - knob.height / 2 + 6 * ctx.ss)))
    bubble = _shadow(_pill(ctx, label, 28, CARD_INK, WHITE), ctx, 12, 8, 0.3)
    obj.alpha_composite(bubble, (int(min(max(kx - bubble.width / 2, 0), w - bubble.width)), int(ty - kr - bubble.height)))
    f = _font(ctx, 34, 750, ctx.heading)
    d.text((tx, ty + track_h + 50 * ctx.ss), left, font=f, fill=rgba(ctx.theme.fg), anchor="la")
    d.text((tx + tw, ty + track_h + 50 * ctx.ss), right, font=f, fill=rgba(ctx.theme.fg), anchor="ra")
    return obj


def g_stat(spec, w, h, ctx):
    value = str(spec.get("value", "8pt"))[:8]
    label = str(spec.get("label", ""))[:30]
    ic = _icon_name(spec.get("icon", "ruler"), "ruler")
    s = int(min(w * 0.62, h * 0.86))
    disc = layer(s, s)
    g = diag_gradient((s, s), ctx.a, ctx.b)
    g.putalpha(rounded_mask((s, s), s // 2))
    disc.alpha_composite(g)
    d = ImageDraw.Draw(disc)
    ring = int(s * 0.11)  # gradient ring, value on a white face: legible whatever the colours
    d.ellipse((ring, ring, s - ring, s - ring), fill=rgba(WHITE))
    d.ellipse((ring * 1.5, ring * 1.5, s - ring * 1.5, s - ring * 1.5), outline=rgba(mix(ctx.a, WHITE, 0.75)),
              width=max(2, int(s * 0.01)))
    val_col = ensure_contrast(ctx.a, WHITE, 3.0)
    f = load_font(ctx.heading, 850, int(s * 0.24))
    while f.getlength(value) > s * 0.62 and f.size > 20:
        f = load_font(ctx.heading, 850, f.size - 4)
    d.text((s / 2, s * 0.48), value, font=f, fill=rgba(val_col), anchor="mm")
    if label:
        fl = load_font(ctx.body, 650, int(s * 0.055))
        while fl.getlength(label) > s * 0.58 and fl.size > 12:
            fl = load_font(ctx.body, 650, fl.size - 2)
        d.text((s / 2, s * 0.66), label, font=fl, fill=rgba(CARD_MUTED), anchor="mm")
    disc = gloss(disc, 0.22)
    out = layer(w, h)
    disc = _shadow(disc, ctx, 34, 28, 0.35)
    out.alpha_composite(disc, (int((w - disc.width) / 2), int((h - disc.height) / 2)))
    badge = _shadow(sticker(_tile(ctx, s * 0.30, ic, WHITE, mix(WHITE, ctx.a, 0.12)), int(5 * ctx.ss)), ctx, 14, 10, 0.3)
    badge = rotate(badge, -10)
    out.alpha_composite(badge, (int(w / 2 + s * 0.22), int(h / 2 - s * 0.62)))
    return out


def g_layers(spec, w, h, ctx):
    """Exploded isometric stack: e.g. tokens -> components -> patterns -> pages."""
    items = [str(i)[:18] for i in (spec.get("items") or [])][:5] or ["Tokens", "Components", "Patterns", "Pages"]
    n = len(items)
    obj = layer(w, h)
    pw, ph = w * 0.56, h * 0.20
    gap = (h - ph * 1.6) / max(1, n - 1) if n > 1 else 0
    gap = min(gap, h * 0.2)
    x0 = w * 0.04
    total = ph + gap * (n - 1)
    ystart = (h - total) / 2 + total - ph
    for i, lab in enumerate(items):  # bottom first
        y = ystart - i * gap
        t = i / max(1, n - 1)
        col_a, col_b = mix(ctx.a, ctx.b, t), mix(ctx.b, ctx.a, t * 0.5)
        plate = layer(pw, ph + 16 * ctx.ss)
        top = [(pw * 0.5, 0), (pw, ph * 0.5), (pw * 0.5, ph), (0, ph * 0.5)]
        side_l = [(0, ph * 0.5), (pw * 0.5, ph), (pw * 0.5, ph + 14 * ctx.ss), (0, ph * 0.5 + 14 * ctx.ss)]
        side_r = [(pw * 0.5, ph), (pw, ph * 0.5), (pw, ph * 0.5 + 14 * ctx.ss), (pw * 0.5, ph + 14 * ctx.ss)]
        pd = ImageDraw.Draw(plate)
        pd.polygon(side_l, fill=rgba(mix(col_a, (0, 0, 0), 0.3)))
        pd.polygon(side_r, fill=rgba(mix(col_b, (0, 0, 0), 0.4)))
        g = diag_gradient(plate.size, mix(col_a, WHITE, 0.15), col_b)
        m = Image.new("L", plate.size, 0)
        ImageDraw.Draw(m).polygon(top, fill=235)
        g.putalpha(m)
        plate.alpha_composite(g)
        # a soft inner rim so plates read as glass-like layers
        inner = [(pw * 0.5, ph * 0.12), (pw * 0.88, ph * 0.5), (pw * 0.5, ph * 0.88), (pw * 0.12, ph * 0.5)]
        pd.polygon(inner, outline=rgba(WHITE, 120), width=max(2, int(2 * ctx.ss)))
        plate = _shadow(plate, ctx, 18, 16, 0.3)
        px = int(x0 - (plate.width - pw) / 2)
        obj.alpha_composite(plate, (px, int(y - (plate.height - ph) / 2)))
        # leader line + label
        d = ImageDraw.Draw(obj)
        lx0, ly = x0 + pw * 0.98, y + ph * 0.5
        d.line([(lx0, ly), (w * 0.66, ly)], fill=rgba(mix(ctx.theme.fg, ctx.theme.bg, 0.35)), width=max(2, int(3 * ctx.ss)))
        d.ellipse((lx0 - 6 * ctx.ss, ly - 6 * ctx.ss, lx0 + 6 * ctx.ss, ly + 6 * ctx.ss), fill=rgba(ctx.theme.fg))
        pill = _pill(ctx, lab, 26, WHITE, CARD_INK)
        obj.alpha_composite(_shadow(pill, ctx, 10, 6, 0.2), (int(w * 0.66) - int(30 * ctx.ss), int(ly - pill.height / 2 - 30 * ctx.ss)))
    return obj


COMPONENTS = ["button", "toggle", "slider", "checkbox", "chip", "avatars", "input", "rating", "tabs", "progress"]


def _component(kind, ctx, scale):
    u = ctx.ss * scale
    if kind == "button":
        o = layer(260 * u, 84 * u); d = ImageDraw.Draw(o)
        g = diag_gradient(o.size, ctx.a, mix(ctx.a, ctx.b, 0.5)); g.putalpha(rounded_mask(o.size, int(42 * u))); o.alpha_composite(g)
        d.text((130 * u, 42 * u), "Get started", font=load_font(ctx.body, 700, int(28 * u)),
               fill=rgba(ensure_contrast(WHITE, ctx.a, 3)), anchor="mm")
        return gloss(o, 0.25)
    if kind == "toggle":
        o = layer(150 * u, 84 * u); d = ImageDraw.Draw(o)
        d.rounded_rectangle((0, 0, o.width - 1, o.height - 1), radius=int(42 * u), fill=rgba(ctx.b))
        d.ellipse((74 * u, 8 * u, 142 * u, 76 * u), fill=rgba(WHITE))
        return gloss(o, 0.2)
    if kind == "slider":
        o = layer(300 * u, 70 * u); d = ImageDraw.Draw(o)
        d.rounded_rectangle((10 * u, 28 * u, 290 * u, 42 * u), radius=int(7 * u), fill=rgba((225, 227, 233)))
        d.rounded_rectangle((10 * u, 28 * u, 190 * u, 42 * u), radius=int(7 * u), fill=rgba(ctx.a))
        d.ellipse((160 * u, 5 * u, 220 * u, 65 * u), fill=rgba(WHITE), outline=rgba(ctx.a), width=int(5 * u))
        return o
    if kind == "checkbox":
        o = layer(96 * u, 96 * u); d = ImageDraw.Draw(o)
        d.rounded_rectangle((0, 0, o.width - 1, o.height - 1), radius=int(24 * u), fill=rgba(ctx.a))
        o.alpha_composite(icon("check", int(60 * u), ensure_contrast(WHITE, ctx.a, 3)), (int(18 * u), int(18 * u)))
        return gloss(o, 0.25)
    if kind == "chip":
        return _pill(ctx, "Design", 26 * scale, mix(ctx.b, WHITE, 0.82), ctx.b, "sparkle", ctx.b)
    if kind == "avatars":
        o = layer(230 * u, 84 * u); d = ImageDraw.Draw(o)
        for k, c in enumerate([ctx.a, ctx.b, (16, 185, 129), (99, 102, 241)]):
            x = k * 48 * u
            d.ellipse((x, 0, x + 84 * u, 84 * u), fill=rgba(WHITE))
            d.ellipse((x + 6 * u, 6 * u, x + 78 * u, 78 * u), fill=rgba(c))
            d.text((x + 42 * u, 42 * u), "AMKR"[k], font=load_font(ctx.heading, 800, int(30 * u)),
                   fill=rgba(ensure_contrast(WHITE, c, 3)), anchor="mm")
        return o
    if kind == "input":
        o = layer(340 * u, 84 * u); d = ImageDraw.Draw(o)
        d.rounded_rectangle((0, 0, o.width - 1, o.height - 1), radius=int(18 * u), fill=rgba(WHITE),
                            outline=rgba(ctx.a), width=int(4 * u))
        o.alpha_composite(icon("search", int(34 * u), CARD_MUTED), (int(22 * u), int(25 * u)))
        d.text((74 * u, 42 * u), "Search designs", font=load_font(ctx.body, 500, int(26 * u)), fill=rgba(CARD_MUTED), anchor="lm")
        return o
    if kind == "rating":
        o = layer(260 * u, 60 * u)
        for k in range(5):
            o.alpha_composite(icon("star", int(48 * u), (245, 170, 30) if k < 4 else (220, 222, 228)), (int(k * 52 * u), int(6 * u)))
        return o
    if kind == "tabs":
        o = layer(330 * u, 80 * u); d = ImageDraw.Draw(o)
        d.rounded_rectangle((0, 0, o.width - 1, o.height - 1), radius=int(40 * u), fill=rgba((236, 237, 242)))
        d.rounded_rectangle((8 * u, 8 * u, 165 * u, 72 * u), radius=int(32 * u), fill=rgba(WHITE))
        f = load_font(ctx.body, 700, int(24 * u))
        d.text((86 * u, 40 * u), "Design", font=f, fill=rgba(CARD_INK), anchor="mm")
        d.text((248 * u, 40 * u), "Code", font=f, fill=rgba(CARD_MUTED), anchor="mm")
        return o
    o = layer(300 * u, 40 * u); d = ImageDraw.Draw(o)  # progress
    d.rounded_rectangle((0, 8 * u, 300 * u, 32 * u), radius=int(12 * u), fill=rgba((225, 227, 233)))
    g = diag_gradient((int(210 * u), int(24 * u)), ctx.a, ctx.b); g.putalpha(rounded_mask(g.size, int(12 * u)))
    o.alpha_composite(g, (0, int(8 * u)))
    return o


def g_components(spec, w, h, ctx):
    """A floating collage of UI components (sticker cut-outs)."""
    kinds = [k for k in (spec.get("items") or []) if k in COMPONENTS][:6] or \
        ctx.rng.sample(COMPONENTS, 6)
    obj = layer(w, h)
    slots = [(0.28, 0.16), (0.74, 0.12), (0.22, 0.47), (0.70, 0.43), (0.32, 0.80), (0.75, 0.78)]
    ctx.rng.shuffle(slots)
    scale = min(w / 760, h / 700) * 1.25
    for kind, (sx, sy) in zip(kinds, slots):
        comp = _component(kind, ctx, scale)
        comp = sticker(comp, int(7 * ctx.ss * scale))
        comp = rotate(comp, ctx.rng.uniform(-9, 9))
        comp = _shadow(comp, ctx, 20, 16, 0.3)
        comp = fit_into(comp, w * 0.5, h * 0.36)
        obj.alpha_composite(comp, (int(w * sx - comp.width / 2), int(h * sy - comp.height / 2)))
    return obj


def g_palette(spec, w, h, ctx):
    """Paint-chip fan of named colours."""
    cols = []
    for c in (spec.get("colors") or [])[:6]:
        try:
            cols.append((hex_to_rgb(str(c.get("hex", ""))), str(c.get("name", ""))[:12]))
        except (ValueError, AttributeError):
            continue
    if len(cols) < 3:
        cols = [(ctx.a, "Primary"), (ctx.b, "Secondary"), (mix(ctx.a, WHITE, 0.6), "Tint"),
                ((24, 26, 36), "Ink"), ((245, 245, 248), "Paper")]
    cols = cols[::-1]  # first colour ends up on top of the fan
    n = len(cols)
    obj = layer(w, h)
    cw, chh = int(w * 0.30), int(h * 0.78)
    pivot = (w / 2, h * 0.96)
    for i, (c, name) in enumerate(cols):
        chip = layer(cw, chh)
        d = ImageDraw.Draw(chip)
        d.rounded_rectangle((0, 0, cw - 1, chh - 1), radius=int(cw * 0.08), fill=rgba(WHITE))
        d.rounded_rectangle((int(cw * 0.06), int(cw * 0.06), cw - int(cw * 0.06), int(chh * 0.70)),
                            radius=int(cw * 0.05), fill=rgba(c))
        f = load_font(ctx.heading, 800, int(cw * 0.11))
        d.text((cw * 0.08, chh * 0.80), name, font=f, fill=rgba(CARD_INK), anchor="lm")
        d.text((cw * 0.08, chh * 0.90), "#%02X%02X%02X" % c, font=load_font(ctx.body, 500, int(cw * 0.08)),
               fill=rgba(CARD_MUTED), anchor="lm")
        ang = (i - (n - 1) / 2) * (52 / max(1, n - 1))
        chip = _shadow(chip, ctx, 16, 10, 0.25)
        r = rotate(chip, -ang)
        # place so the chip's bottom-centre stays near the fan pivot
        rad = math.radians(ang)
        dist = chh * 0.48
        cx = pivot[0] + math.sin(rad) * dist
        cy = pivot[1] - math.cos(rad) * dist
        obj.alpha_composite(r, (int(cx - r.width / 2), int(cy - r.height / 2)))
    return obj


def g_type(spec, w, h, ctx):
    """Type specimen card with metric lines."""
    sample = str(spec.get("sample", "Aa"))[:10]
    style = spec.get("style", "sans")
    family = {"serif": "dm-serif-display", "display": ctx.heading, "mono": "space-grotesk"}.get(style, ctx.heading)
    weight = 400 if style == "serif" else 800
    label = str(spec.get("label", {"serif": "Serif", "mono": "Grotesk", "display": "Display"}.get(style, "Sans")))[:22]
    cw, chh = int(w * 0.92), int(h * 0.86)
    card = layer(cw, chh)
    d = ImageDraw.Draw(card)
    d.rounded_rectangle((0, 0, cw - 1, chh - 1), radius=int(cw * 0.05), fill=rgba(WHITE))
    f = load_font(family, weight, int(chh * 0.5))
    while f.getlength(sample) > cw * 0.84 and f.size > 30:
        f = load_font(family, weight, f.size - 6)
    base = chh * 0.66
    asc, desc = f.getmetrics()
    xh = f.getbbox("x")[3] - f.getbbox("x")[1]
    for yy, name in ((base, "baseline"), (base - xh, "x-height"), (base - asc * 0.72, "cap height")):
        d.line([(cw * 0.05, yy), (cw * 0.95, yy)], fill=rgba(mix(ctx.a, WHITE, 0.4)), width=max(2, int(2 * ctx.ss)))
        d.text((cw * 0.95, yy - 6 * ctx.ss), name, font=load_font(ctx.body, 600, int(18 * ctx.ss)),
               fill=rgba(ensure_contrast(ctx.a, WHITE, 3)), anchor="rs")
    d.text((cw * 0.08, base), sample, font=f, fill=rgba(CARD_INK), anchor="ls")
    d.text((cw * 0.08, chh * 0.88), label, font=load_font(ctx.heading, 800, int(chh * 0.06)), fill=rgba(CARD_INK), anchor="ls")
    card = _shadow(card, ctx, 30, 24, 0.3)
    return fit_into(rotate(card, ctx.rng.uniform(-3, 3)), w, h)


def g_checklist(spec, w, h, ctx):
    items = [str(i)[:44] for i in (spec.get("items") or [])][:5] or ["Clear hierarchy", "One primary action",
                                                                     "Readable contrast"]
    cw = int(w * 0.94)
    row = int(min(h * 0.86 / len(items), 150 * ctx.ss))
    chh = row * len(items) + int(40 * ctx.ss)
    card = layer(cw, chh)
    d = ImageDraw.Draw(card)
    d.rounded_rectangle((0, 0, cw - 1, chh - 1), radius=int(36 * ctx.ss), fill=rgba(WHITE))
    for i, it in enumerate(items):
        y = int(20 * ctx.ss) + i * row
        box = int(row * 0.46)
        bx, by = int(32 * ctx.ss), y + (row - box) // 2
        g = diag_gradient((box, box), ctx.a, ctx.b); g.putalpha(rounded_mask((box, box), box // 4))
        card.alpha_composite(g, (bx, by))
        card.alpha_composite(icon("check", int(box * 0.7), ensure_contrast(WHITE, ctx.a, 3)),
                             (bx + int(box * 0.15), by + int(box * 0.15)))
        f = load_font(ctx.body, 650, int(row * 0.26))
        while f.getlength(it) > cw - bx - box - 70 * ctx.ss and f.size > 14:
            f = load_font(ctx.body, 650, f.size - 2)
        d.text((bx + box + 26 * ctx.ss, y + row / 2), it, font=f, fill=rgba(CARD_INK), anchor="lm")
        if i < len(items) - 1:
            d.line([(bx, y + row), (cw - 32 * ctx.ss, y + row)], fill=rgba((235, 236, 240)), width=max(1, int(2 * ctx.ss)))
    return fit_into(_shadow(card, ctx, 28, 20, 0.28), w, h)


def g_hero_icon(spec, w, h, ctx):
    """Big glossy 3D-ish icon badge with orbiting satellite icons — a strong 'cover' visual."""
    main = _icon_name(spec.get("icon", "sparkle"))
    sats = [_icon_name(s) for s in (spec.get("items") or []) if s in ICONS][:4] or \
        ctx.rng.sample([n for n in ("heart", "star", "bolt", "cursor", "chat", "layers", "eye") if n != main], 4)
    obj = layer(w, h)
    s = int(min(w, h) * 0.56)
    big = _tile(ctx, s, main, ctx.a, ctx.b, 0.3)
    big = _shadow(rotate(big, -8), ctx, 40, 36, 0.4)
    obj.alpha_composite(big, (int((w - big.width) / 2), int((h - big.height) / 2)))
    spots = [(0.16, 0.22), (0.84, 0.18), (0.12, 0.78), (0.86, 0.76)]
    for k, (name, (sx, sy)) in enumerate(zip(sats, spots)):
        t = _tile(ctx, s * 0.30, name, WHITE, mix(WHITE, ctx.b, 0.15), 0.3)
        recol = layer(t.width, t.height)
        recol.alpha_composite(t)
        ic = icon(name, int(s * 0.15), ctx.a if k % 2 else ctx.b)
        recol.alpha_composite(ic, ((t.width - ic.width) // 2, (t.height - ic.height) // 2))
        t = _shadow(sticker(rotate(recol, ctx.rng.uniform(-14, 14)), int(4 * ctx.ss)), ctx, 18, 14, 0.3)
        obj.alpha_composite(t, (int(w * sx - t.width / 2), int(h * sy - t.height / 2)))
    return obj


GRAPHICS = {
    "phone": g_phone, "browser": g_browser, "compare": g_compare, "steps": g_steps, "icons": g_icons,
    "timeline": g_timeline, "spectrum": g_spectrum, "stat": g_stat, "layers": g_layers,
    "components": g_components, "palette": g_palette, "type": g_type, "checklist": g_checklist,
    "hero_icon": g_hero_icon,
}


def draw_graphic(spec: dict, w: int, h: int, ctx: GCtx) -> Image.Image:
    fn = GRAPHICS.get((spec or {}).get("type"), g_hero_icon)
    try:
        return fn(spec or {}, int(w), int(h), ctx)
    except Exception:  # noqa: BLE001 — a bad spec must never kill the post; fall back to a safe visual
        import logging
        logging.getLogger("graphics").warning("graphic %s failed — using hero_icon", spec, exc_info=True)
        return g_hero_icon({"icon": "sparkle"}, int(w), int(h), ctx)


__all__ = ["GRAPHICS", "GCtx", "draw_graphic", "COMPONENTS", "contrast_ratio"]
