"""Small illustrative diagrams drawn with Pillow (no AI images).

Each function draws inside box=(x, y, w, h). Any numbers shown are either design values in the drawing
itself (8/16/24…) or computed on the spot (contrast ratios) — nothing invented.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PIL import ImageDraw

from .contrast import contrast_ratio, ensure_contrast, hex_to_rgb, mix
from .fonts import load_font
from .themes import Theme, marker_colors

Box = tuple[int, int, int, int]
RADIUS_K = 1.0  # set per theme by the renderer (0 = sharp corners for the tiles theme)


@dataclass
class Ctx:
    theme: Theme
    heading: str
    body: str
    brand: dict
    styler: Any = None   # styles.Styler — paints themed panels (glass, bevels, hard shadows)
    img: Any = None      # the slide being drawn (styled panels need pixel access)


# ---- primitives --------------------------------------------------------
def rrect(d: ImageDraw.ImageDraw, x0, y0, x1, y1, r, fill=None, outline=None, width=1):
    d.rounded_rectangle((round(x0), round(y0), round(x1), round(y1)), radius=round(r * RADIUS_K),
                        fill=fill, outline=outline, width=width)


def text(d, xy, s, ctx: Ctx, size, fill, weight=500, anchor="la", family=None):
    d.text((round(xy[0]), round(xy[1])), s, font=load_font(family or ctx.body, weight, size), fill=fill,
           anchor=anchor)


def check(d, cx, cy, r, color, width=None):
    w = width or max(3, round(r / 3))
    d.line([(cx - r * 0.6, cy), (cx - r * 0.15, cy + r * 0.5), (cx + r * 0.65, cy - r * 0.5)],
           fill=color, width=w, joint="curve")


def cross(d, cx, cy, r, color, width=None):
    w = width or max(3, round(r / 3))
    k = r * 0.5
    d.line([(cx - k, cy - k), (cx + k, cy + k)], fill=color, width=w)
    d.line([(cx - k, cy + k), (cx + k, cy - k)], fill=color, width=w)


def badge(d, cx, cy, r, ok: bool, ctx: Ctx):
    good, bad = marker_colors(ctx.theme)
    color = good if ok else bad
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)
    icon = (255, 255, 255) if contrast_ratio((255, 255, 255), color) >= 3 else (17, 24, 39)
    (check if ok else cross)(d, cx, cy, r * 0.75, icon)


def dashed_rect(d, x0, y0, x1, y1, color, dash=8, width=3):
    for x in range(round(x0), round(x1), dash * 2):
        d.line([(x, y0), (min(x + dash, x1), y0)], fill=color, width=width)
        d.line([(x, y1), (min(x + dash, x1), y1)], fill=color, width=width)
    for y in range(round(y0), round(y1), dash * 2):
        d.line([(x0, y), (x0, min(y + dash, y1))], fill=color, width=width)
        d.line([(x1, y), (x1, min(y + dash, y1))], fill=color, width=width)


def panel(d, box: Box, ctx: Ctx, outline=None):
    x, y, w, h = box
    t = ctx.theme
    if ctx.styler is not None and ctx.img is not None:
        ctx.styler.panel(ctx.img, (x, y, x + w, y + h), 28, outline=outline)
    else:
        rrect(d, x, y, x + w, y + h, 28, fill=t.surface, outline=outline or t.line, width=2)


def bar(d, x, y, w, h, color):
    rrect(d, x, y, x + w, y + h, h / 2, fill=color)


def _ink(ctx: Ctx):
    """Colours for mock UI drawn on the surface panel."""
    t = ctx.theme
    ink = t.on_surface
    soft = mix(t.surface, ink, 0.18)
    softer = mix(t.surface, ink, 0.09)
    accent = ensure_contrast(t.accent, t.surface, 3.0)
    return ink, soft, softer, accent


def button(d, x, y, w, h, label, ctx: Ctx, fill, fg, size=None, outline=None):
    rrect(d, x, y, x + w, y + h, min(16, h / 3), fill=fill, outline=outline, width=3)
    text(d, (x + w / 2, y + h / 2), label, ctx, size or round(h * 0.36), fg, 600, anchor="mm")


# ---- visuals -----------------------------------------------------------
def v_grid8(d, box: Box, ctx: Ctx):
    x, y, w, h = box
    panel(d, box, ctx)
    ink, soft, softer, accent = _ink(ctx)
    s = 24  # one grid cell = 8pt, drawn at 3x
    gx0, gy0 = x + s, y + s
    gx1, gy1 = x + w - s, y + h - s
    for gx in range(gx0, gx1 + 1, s):
        d.line([(gx, gy0), (gx, gy1)], fill=mix(ctx.theme.surface, accent, 0.13), width=1)
    for gy in range(gy0, gy1 + 1, s):
        d.line([(gx0, gy), (gx1, gy)], fill=mix(ctx.theme.surface, accent, 0.13), width=1)
    cols = (gx1 - gx0) // s
    rows = (gy1 - gy0) // s
    cx0, cy0 = gx0 + 2 * s, gy0 + 2 * s
    cx1 = gx0 + (cols - 2) * s
    cy1 = gy0 + (rows - 2) * s
    rrect(d, cx0, cy0, cx1, cy1, 12, fill=ctx.theme.surface, outline=ink, width=3)
    # contents snapped to grid
    rrect(d, cx0 + s, cy0 + s, cx1 - s, cy0 + s * max(3, (rows - 4) // 2), 8, fill=mix(ctx.theme.surface, accent, 0.25))
    ty = cy0 + s * max(3, (rows - 4) // 2) + s
    if ty + 2 * s < cy1 - 2 * s:
        bar(d, cx0 + s, ty, (cx1 - cx0) * 0.55, s * 0.8, soft)
        bar(d, cx0 + s, ty + s * 1.5, (cx1 - cx0) * 0.75, s * 0.6, softer)
    by = cy1 - s * 3
    if by > ty + 2 * s:
        button(d, cx0 + s, by, s * 7, s * 2, "Button", ctx, accent, ensure_contrast((255, 255, 255), accent), size=22)
    # dimension markers: 16 (two 8pt cells) from the grid edge to the card
    my = (cy0 + cy1) / 2
    d.line([(gx0 + 3, my), (cx0 - 3, my)], fill=accent, width=3)
    for ex in (gx0 + 3, cx0 - 3):
        d.line([(ex, my - 9), (ex, my + 9)], fill=accent, width=3)
    rrect(d, gx0 + 2, my - 46, cx0 - 2, my - 16, 6, fill=accent)
    text(d, ((gx0 + cx0) / 2, my - 31), "16", ctx, 20, ensure_contrast((255, 255, 255), accent), 700, anchor="mm")


def v_spacing(d, box: Box, ctx: Ctx):
    x, y, w, h = box
    panel(d, box, ctx)
    ink, soft, softer, accent = _ink(ctx)
    gap_fill = mix(ctx.theme.surface, accent, 0.22)
    unit = max(3, min(6, (h - 80) // 70))     # px per spacing step drawn (scaled)
    fx0, fx1 = x + 60, x + w * 0.62
    cy = y + 40
    seq = ["label", 8, "input", 16, "label", 8, "input", 32, "label", 8, "input"]
    total = sum(unit * v if isinstance(v, int) else (unit * 4 if v == "label" else unit * 10) for v in seq)
    scale = min(1.0, (h - 80) / total)
    for item in seq:
        if item == "label":
            hh = unit * 4 * scale
            bar(d, fx0, cy, (fx1 - fx0) * 0.35, hh, soft)
            cy += hh
        elif item == "input":
            hh = unit * 10 * scale
            rrect(d, fx0, cy, fx1, cy + hh, 10, fill=ctx.theme.surface, outline=soft, width=3)
            cy += hh
        else:
            hh = unit * item * scale
            d.rectangle((fx0, cy, fx1, cy + hh), fill=gap_fill)
            text(d, (fx1 + 24, cy + hh / 2), f"{item}px", ctx, 24, accent, 700, anchor="lm")
            cy += hh


def v_type_scale(d, box: Box, ctx: Ctx):
    x, y, w, h = box
    panel(d, box, ctx)
    ink, soft, softer, accent = _ink(ctx)
    scale = [("Display", 40), ("Title", 32), ("Heading", 24), ("Body", 16), ("Caption", 12)]
    total = sum(size * 1.35 for _, size in scale)
    k = min(2.6, (h - 70) / total)
    cy = y + (h - total * k) / 2
    for name, size in scale:
        px = round(size * k)
        text(d, (x + 50, cy + px * 1.05), name, ctx, px, ink, 700 if size >= 24 else 400, anchor="ls",
             family=ctx.heading)
        text(d, (x + w - 50, cy + px * 1.05), f"{size}px", ctx, 22, accent, 600, anchor="rs")
        cy += px * 1.35


def v_contrast(d, box: Box, ctx: Ctx):
    x, y, w, h = box
    primary = hex_to_rgb(ctx.brand["primary"])
    pairs = [((156, 163, 175), (255, 255, 255)), ((75, 85, 99), (255, 255, 255)),
             ((255, 255, 255), primary)]
    gap = 24
    sw = (w - gap * 2) / 3
    for i, (fg, bg) in enumerate(pairs):
        sx = x + i * (sw + gap)
        rrect(d, sx, y, sx + sw, y + h, 24, fill=bg, outline=ctx.theme.line, width=2)
        text(d, (sx + sw / 2, y + h * 0.38), "Aa", ctx, round(min(sw, h) * 0.32), fg, 700, anchor="mm",
             family=ctx.heading)
        ratio = contrast_ratio(fg, bg)
        ok = ratio >= 4.5
        label_color = ensure_contrast((17, 24, 39), bg) if not _dark(bg) else (255, 255, 255)
        text(d, (sx + sw / 2, y + h * 0.68), f"{ratio:.1f}:1", ctx, round(sw * 0.13), label_color, 700, anchor="mm")
        badge(d, sx + sw / 2, y + h * 0.85, round(sw * 0.07), ok, ctx)


def _dark(c):
    return contrast_ratio(c, (255, 255, 255)) > contrast_ratio(c, (0, 0, 0))


def v_buttons(d, box: Box, ctx: Ctx):
    x, y, w, h = box
    panel(d, box, ctx)
    ink, soft, softer, accent = _ink(ctx)
    half = w / 2
    # weak: three equal, low-contrast, cramped
    bx = x + 40
    bw = half - 80
    for i in range(3):
        by = y + h * 0.18 + i * (h * 0.2)
        rrect(d, bx, by, bx + bw, by + h * 0.13, 8, fill=softer)
        text(d, (bx + bw / 2, by + h * 0.065), ["Save", "Continue", "Cancel"][i], ctx, 22,
             mix(ctx.theme.surface, ink, 0.45), 500, anchor="mm")
    badge(d, x + half / 2, y + h * 0.86, 22, False, ctx)
    d.line([(x + half, y + 30), (x + half, y + h - 30)], fill=ctx.theme.line, width=2)
    # strong: clear primary / secondary / tertiary
    bx = x + half + 40
    on_accent = ensure_contrast((255, 255, 255), accent)
    button(d, bx, y + h * 0.16, bw, h * 0.17, "Continue", ctx, accent, on_accent, size=26)
    button(d, bx, y + h * 0.39, bw, h * 0.17, "Save draft", ctx, ctx.theme.surface, accent, size=26, outline=accent)
    text(d, (bx + bw / 2, y + h * 0.68), "Cancel", ctx, 24, ink, 600, anchor="mm")
    badge(d, x + half * 1.5, y + h * 0.86, 22, True, ctx)


def v_form_field(d, box: Box, ctx: Ctx):
    x, y, w, h = box
    panel(d, box, ctx)
    ink, soft, softer, accent = _ink(ctx)
    good, bad = marker_colors(ctx.theme)
    fx0, fx1 = x + 50, x + w - 50
    fh = min(76, h * 0.2)
    gap = (h - 2 * fh - 4 * 30) / 4
    cy = y + gap
    text(d, (fx0, cy), "Email", ctx, 26, ink, 600)
    cy += 38
    rrect(d, fx0, cy, fx1, cy + fh, 12, fill=ctx.theme.surface, outline=accent, width=4)
    text(d, (fx0 + 24, cy + fh / 2), "maya@studio.design", ctx, 26, ink, 400, anchor="lm")
    cy += fh + 10
    text(d, (fx0, cy), "We'll only use this for receipts", ctx, 21, mix(ctx.theme.surface, ink, 0.7), 400)
    cy += gap + 26
    text(d, (fx0, cy), "Phone", ctx, 26, ink, 600)
    cy += 38
    rrect(d, fx0, cy, fx1, cy + fh, 12, fill=ctx.theme.surface, outline=bad, width=4)
    text(d, (fx0 + 24, cy + fh / 2), "98765", ctx, 26, ink, 400, anchor="lm")
    cy += fh + 10
    text(d, (fx0, cy), "Enter all 10 digits, like 98765 43210", ctx, 21, bad, 600)


def v_card(d, box: Box, ctx: Ctx):
    x, y, w, h = box
    ink, soft, softer, accent = _ink(ctx)
    cw = min(w * 0.62, h * 0.95)
    cx0 = x + (w - cw) / 2
    if ctx.styler is None or ctx.theme.style == "flat":
        rrect(d, cx0 + 8, y + 12, cx0 + cw + 8, y + h + 4, 28, fill=mix(ctx.theme.bg, (0, 0, 0), 0.08))
    panel(d, (cx0, y, cw, h - 8), ctx)
    ih = (h - 8) * 0.45
    rrect(d, cx0 + 24, y + 24, cx0 + cw - 24, y + ih, 18, fill=mix(ctx.theme.surface, accent, 0.25))
    mx, my = cx0 + cw / 2, y + 24 + (ih - 24) / 2
    d.polygon([(mx - 70, my + 40), (mx - 15, my - 25), (mx + 25, my + 15), (mx + 45, my - 5), (mx + 85, my + 40)],
              fill=mix(ctx.theme.surface, accent, 0.55))
    d.ellipse((mx + 35, my - 55, mx + 65, my - 25), fill=mix(ctx.theme.surface, accent, 0.55))
    ty = y + ih + 30
    text(d, (cx0 + 32, ty), "Project title", ctx, 30, ink, 700, family=ctx.heading)
    bar(d, cx0 + 32, ty + 52, cw * 0.7, 14, softer)
    bar(d, cx0 + 32, ty + 78, cw * 0.5, 14, softer)
    bh = 56
    by = y + h - 8 - 24 - bh
    if by > ty + 100:
        button(d, cx0 + 32, by, 170, bh, "View", ctx, accent, ensure_contrast((255, 255, 255), accent), size=24)


def v_hierarchy(d, box: Box, ctx: Ctx):
    x, y, w, h = box
    panel(d, box, ctx)
    ink, soft, softer, accent = _ink(ctx)
    lx = x + 110
    rows = [("1", 52, 800, "Page heading"), ("2", 32, 600, "Section subheading"), ("3", 22, 400, None)]
    content_h = 52 * 1.9 + 32 * 1.9 + 120
    cy = y + (h - content_h) / 2
    for num, size, weight, label in rows:
        d.ellipse((x + 40, cy, x + 80, cy + 40), fill=accent)
        text(d, (x + 60, cy + 20), num, ctx, 22, ensure_contrast((255, 255, 255), accent), 700, anchor="mm")
        if label:
            text(d, (lx, cy + 20), label, ctx, size, ink, weight, anchor="lm", family=ctx.heading)
            cy += size * 1.9
        else:
            for i, frac in enumerate((0.92, 0.85, 0.6)):
                bar(d, lx, cy + 12 + i * 34, (w - 150) * frac, 14, soft)
            cy += 120


def v_touch_target(d, box: Box, ctx: Ctx):
    x, y, w, h = box
    panel(d, box, ctx)
    ink, soft, softer, accent = _ink(ctx)
    good, bad = marker_colors(ctx.theme)
    k = min(4.0, (h - 120) / 48 * 0.75)  # draw at k× so 48px is visible
    for i, (size, ok) in enumerate(((24, False), (48, True))):
        cx = x + w * (0.27 + 0.46 * i)
        cy = y + h * 0.45
        r = 12 * k
        cross(d, cx, cy, r * 1.4, ink, width=max(4, round(k * 1.6)))
        half = size * k / 2
        dashed_rect(d, cx - half, cy - half, cx + half, cy + half, good if ok else bad, dash=10, width=3)
        text(d, (cx, cy + max(half, r) + 34), f"{size}×{size}px", ctx, 26, ink, 700, anchor="mt")
        badge(d, cx, y + h - 50, 20, ok, ctx)


def v_swatches(d, box: Box, ctx: Ctx):
    x, y, w, h = box
    keys = ["primary", "secondary", "dark", "light"]
    gap = 20
    sw = (w - gap * 3) / 4
    for i, k in enumerate(keys):
        sx = x + i * (sw + gap)
        c = hex_to_rgb(ctx.brand[k])
        rrect(d, sx, y, sx + sw, y + h * 0.72, 22, fill=c, outline=ctx.theme.line, width=2)
        text(d, (sx + 6, y + h * 0.78), k.capitalize(), ctx, 24, ctx.theme.fg, 700)
        text(d, (sx + 6, y + h * 0.78 + 34), ctx.brand[k].upper(), ctx, 22, ctx.theme.muted, 500)


def v_alignment(d, box: Box, ctx: Ctx):
    x, y, w, h = box
    ink, soft, softer, accent = _ink(ctx)
    good, bad = marker_colors(ctx.theme)
    half = (w - 30) / 2
    for i in range(2):
        px = x + i * (half + 30)
        panel(d, (px, y, half, h), ctx)
        offsets = [40, 70, 30, 95, 55] if i == 0 else [44] * 5
        widths = [0.6, 0.8, 0.5, 0.7, 0.4]
        cy = y + 50
        step = (h - 140) / 5
        for j, (off, wf) in enumerate(zip(offsets, widths)):
            bar(d, px + off, cy, (half - 140) * wf, 22 if j == 0 else 14, ink if j == 0 else soft)
            cy += step
        if i == 1:
            for yy in range(round(y + 30), round(y + h - 90), 18):
                d.line([(px + 40, yy), (px + 40, yy + 9)], fill=accent, width=3)
        badge(d, px + half / 2, y + h - 48, 20, i == 1, ctx)


def v_empty_state(d, box: Box, ctx: Ctx):
    x, y, w, h = box
    panel(d, box, ctx)
    ink, soft, softer, accent = _ink(ctx)
    cx = x + w / 2
    r = min(w, h) * 0.17
    cy = y + h * 0.1 + r
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=mix(ctx.theme.surface, accent, 0.18))
    tray_w = r * 1.1
    d.rounded_rectangle((cx - tray_w / 2, cy - r * 0.25, cx + tray_w / 2, cy + r * 0.45), radius=10,
                        outline=accent, width=6)
    d.line([(cx - tray_w / 2, cy + r * 0.05), (cx - tray_w * 0.18, cy + r * 0.05), (cx - tray_w * 0.1, cy + r * 0.2),
            (cx + tray_w * 0.1, cy + r * 0.2), (cx + tray_w * 0.18, cy + r * 0.05), (cx + tray_w / 2, cy + r * 0.05)],
           fill=accent, width=6)
    ty = cy + r + 34
    text(d, (cx, ty), "No projects yet", ctx, 32, ink, 700, anchor="mt", family=ctx.heading)
    text(d, (cx, ty + 48), "Create one to see it here", ctx, 24, mix(ctx.theme.surface, ink, 0.7), 400, anchor="mt")
    bh = 60
    if ty + 100 + bh < y + h - 20:
        button(d, cx - 130, ty + 100, 260, bh, "Create project", ctx, accent,
               ensure_contrast((255, 255, 255), accent), size=24)


def v_checklist(d, box: Box, ctx: Ctx):
    x, y, w, h = box
    panel(d, box, ctx)
    ink, soft, softer, accent = _ink(ctx)
    n = 4
    step = (h - 60) / n
    for i in range(n):
        cy = y + 30 + i * step + step / 2
        s = min(44, step * 0.6)
        done = i < 3
        rrect(d, x + 50, cy - s / 2, x + 50 + s, cy + s / 2, 8, fill=accent if done else None,
              outline=accent, width=4)
        if done:
            check(d, x + 50 + s / 2, cy, s * 0.42, ensure_contrast((255, 255, 255), accent))
        bar(d, x + 50 + s + 28, cy - 8, (w - 200) * (0.8 - 0.12 * (i % 3)), 16, soft if done else softer)


VISUAL_FUNCS = {
    "grid8": v_grid8, "spacing": v_spacing, "type_scale": v_type_scale, "contrast": v_contrast,
    "buttons": v_buttons, "form_field": v_form_field, "card": v_card, "hierarchy": v_hierarchy,
    "touch_target": v_touch_target, "swatches": v_swatches, "alignment": v_alignment,
    "empty_state": v_empty_state, "checklist": v_checklist,
}


def draw_visual(name: str, d: ImageDraw.ImageDraw, box: Box, ctx: Ctx) -> bool:
    fn = VISUAL_FUNCS.get(name)
    if not fn or box[2] < 200 or box[3] < 160:
        return False
    fn(d, box, ctx)
    return True
