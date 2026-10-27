"""Themes built from the brand colours. Flat themes are checked here; painted themes (gradient,
glass, tiles, skeuo) are re-checked against the actual background pixels in styles.py."""
from __future__ import annotations

import colorsys
import logging
from dataclasses import dataclass, replace

from .contrast import AA_BODY, AA_LARGE, Color, contrast_ratio, ensure_contrast, hex_to_rgb, is_dark, mix

log = logging.getLogger("themes")

THEME_NAMES = ["grid", "accent", "gradient", "glass", "tiles", "skeuo",
               "aurora", "editorial", "brutal", "noir", "blueprint", "clay"]
WHITE: Color = (255, 255, 255)
BLACK: Color = (0, 0, 0)
GOOD: Color = (22, 163, 74)   # green for "do"/pass markers
BAD: Color = (220, 38, 38)    # red for "don't"/fail markers


@dataclass(frozen=True)
class Theme:
    name: str
    bg: Color          # solid background, or the average colour of a painted one
    fg: Color          # titles
    body: Color        # body text
    muted: Color       # labels, footer
    accent: Color      # highlights, shapes, accent text (large)
    on_accent: Color   # text placed on an accent fill
    surface: Color     # cards/panels (representative colour for translucent ones)
    on_surface: Color
    line: Color        # hairlines, grid
    decor: str         # flat themes: circle | grid | none
    title_weight: int = 800
    body_weight: int = 400
    style: str = "flat"          # flat | gradient | glass | tiles | skeuo
    radius: float = 1.0          # corner-radius multiplier (tiles = 0, sharp)
    emboss: Color | None = None  # letterpress highlight under titles (skeuo)
    palette: tuple = ()          # extra colours for painted backgrounds
    heading_font: str | None = None  # overrides the configured heading font (e.g. serif for editorial)


def shift(c: Color, hue: float = 0.0, sat: float = 1.0, val: float = 1.0) -> Color:
    """Rotate hue (degrees) and scale saturation/value."""
    h, s, v = colorsys.rgb_to_hsv(*(x / 255 for x in c))
    r, g, b = colorsys.hsv_to_rgb((h + hue / 360) % 1, min(1, s * sat), min(1, v * val))
    return (round(r * 255), round(g * 255), round(b * 255))


def hsv(h: float, s: float, v: float) -> Color:
    """Colour from hue in degrees; hues in the yellow–olive band (muddy when darkened) are moved to green-teal."""
    h %= 360
    if 40 <= h <= 100:
        h += 80
    r, g, b = colorsys.hsv_to_rgb(h / 360, s, v)
    return (round(r * 255), round(g * 255), round(b * 255))


def hue(c: Color) -> float:
    return colorsys.rgb_to_hsv(*(x / 255 for x in c))[0] * 360


def _vivid(p: Color, s: Color) -> Color:
    """The more colourful of the two brand colours (an ink-black primary makes a dull gradient)."""
    sat = lambda c: colorsys.rgb_to_hsv(*(x / 255 for x in c))[1] * max(c) / 255
    return s if sat(s) >= sat(p) else p


def build_theme(name: str, brand: dict) -> Theme:
    p, s = hex_to_rgb(brand["primary"]), hex_to_rgb(brand["secondary"])
    d, l = hex_to_rgb(brand["dark"]), hex_to_rgb(brand["light"])
    v = _vivid(p, s)
    if name == "accent":
        t = Theme(name, p, WHITE, mix(WHITE, p, 0.08), mix(WHITE, p, 0.25), s, d, mix(p, WHITE, 0.14),
                  WHITE, mix(p, WHITE, 0.22), "circle")
    elif name == "gradient":
        # deep mesh gradient: the brand hue plus two neighbours, dark enough for white text
        h = hue(v)
        corners = (hsv(h - 30, 0.85, 0.6), hsv(h, 0.9, 0.74), hsv(h - 80, 0.75, 0.48), hsv(h - 140, 0.7, 0.22))
        bg = mix(mix(corners[0], corners[1], 0.5), mix(corners[2], corners[3], 0.5), 0.5)
        t = Theme(name, bg, WHITE, mix(WHITE, bg, 0.06), mix(WHITE, bg, 0.22), shift(v, 10, 0.55, 1.6), d,
                  mix(bg, WHITE, 0.12), WHITE, mix(bg, WHITE, 0.25), "none",
                  style="gradient", radius=1.3, palette=corners)
    elif name == "glass":
        h = hue(v)
        base = hsv(h - 130, 0.65, 0.14)
        blobs = (hsv(h, 0.85, 0.85), hsv(h - 45, 0.8, 0.75), hsv(h + 150, 0.75, 0.72), hsv(h - 100, 0.8, 0.7))
        t = Theme(name, base, WHITE, mix(WHITE, base, 0.06), mix(WHITE, base, 0.25), shift(v, 0, 0.6, 1.5), d,
                  mix(base, WHITE, 0.14), WHITE, mix(base, WHITE, 0.3), "none",
                  title_weight=700, style="glass", radius=1.5, palette=blobs)
    elif name == "tiles":
        paper = (245, 243, 238)
        ink = mix(d, BLACK, 0.3)
        t = Theme(name, paper, ink, mix(ink, paper, 0.08), mix(ink, paper, 0.3), v, WHITE, WHITE, ink, ink,
                  "none", title_weight=900, body_weight=500, style="tiles", radius=0.0,
                  palette=(v, shift(v, 40, 1.0, 1.0), p, shift(v, -150, 0.8, 0.9), ink))
    elif name == "skeuo":
        paper = (232, 224, 210)
        ink = (58, 44, 32)
        t = Theme(name, paper, ink, mix(ink, paper, 0.1), mix(ink, paper, 0.3), shift(v, 0, 1.0, 0.8), WHITE,
                  (246, 242, 234), ink, (196, 184, 164), "none", title_weight=800, style="skeuo",
                  radius=1.1, emboss=(250, 246, 238))
    elif name == "aurora":
        h = hue(v)
        base = hsv(h - 160, 0.7, 0.10)
        t = Theme(name, base, WHITE, mix(WHITE, base, 0.08), mix(WHITE, base, 0.3), hsv(h + 120, 0.55, 1.0), d,
                  mix(base, WHITE, 0.1), WHITE, mix(base, WHITE, 0.2), "none", title_weight=750, style="aurora",
                  radius=1.2, palette=(hsv(h + 120, 0.8, 0.9), hsv(h + 170, 0.7, 0.85), hsv(h - 40, 0.75, 0.9)))
    elif name == "editorial":
        paper, ink = (247, 243, 234), (28, 24, 20)
        t = Theme(name, paper, ink, mix(ink, paper, 0.12), mix(ink, paper, 0.35), shift(v, 0, 1.0, 0.85), WHITE,
                  WHITE, ink, (205, 196, 180), "none", title_weight=400, body_weight=400, style="editorial",
                  radius=0.3, heading_font="dm-serif-display")
    elif name == "brutal":
        h = hue(v)
        bg = hsv(h + 45, 0.32, 1.0)
        t = Theme(name, bg, BLACK, (20, 20, 20), (40, 40, 40), BLACK, bg, WHITE, BLACK, BLACK, "none",
                  title_weight=900, body_weight=600, style="brutal", radius=0.5,
                  palette=(v, hsv(h + 160, 0.7, 0.9), hsv(h - 50, 0.8, 1.0)))
    elif name == "noir":
        bg = (11, 11, 13)
        t = Theme(name, bg, (246, 246, 246), (200, 200, 205), (150, 150, 158), v, bg, (28, 28, 32), WHITE,
                  (40, 40, 46), "none", title_weight=800, style="noir", radius=0.8)
    elif name == "blueprint":
        bg = (18, 62, 140)
        t = Theme(name, bg, WHITE, (225, 236, 255), (180, 205, 245), (255, 214, 102), (18, 40, 90),
                  mix(bg, WHITE, 0.1), WHITE, (90, 140, 220), "none", title_weight=750, style="blueprint",
                  radius=0.4, heading_font="space-grotesk")
    elif name == "clay":
        h = hue(v)
        bg = hsv(h + 200, 0.10, 0.97)
        ink = (40, 36, 60)
        t = Theme(name, bg, ink, mix(ink, bg, 0.1), mix(ink, bg, 0.32), shift(v, 0, 0.9, 0.85), WHITE, WHITE, ink,
                  mix(bg, ink, 0.1), "none", title_weight=800, style="clay", radius=1.6,
                  palette=(hsv(h, 0.35, 1.0), hsv(h + 120, 0.3, 1.0), hsv(h + 220, 0.3, 1.0)))
    else:  # grid
        t = Theme("grid", l, d, mix(d, l, 0.15), mix(d, l, 0.4), p, WHITE, WHITE, d,
                  mix(l, p, 0.12), "grid")
    return enforce_contrast(t)


def enforce_contrast(t: Theme) -> Theme:
    """Auto-adjust text colours so body text meets AA 4.5:1 and accents meet 3:1."""
    fixed = replace(
        t,
        fg=ensure_contrast(t.fg, t.bg, AA_BODY),
        body=ensure_contrast(t.body, t.bg, AA_BODY),
        muted=ensure_contrast(t.muted, t.bg, AA_BODY),
        accent=ensure_contrast(t.accent, t.bg, AA_LARGE),
        on_surface=ensure_contrast(t.on_surface, t.surface, AA_BODY),
    )
    fixed = replace(fixed, on_accent=ensure_contrast(fixed.on_accent, fixed.accent, AA_BODY))
    if fixed != t:
        log.debug("theme %s: adjusted colours for contrast", t.name)
    return fixed


def theme_passes(t: Theme) -> bool:
    return (contrast_ratio(t.fg, t.bg) >= AA_BODY and contrast_ratio(t.body, t.bg) >= AA_BODY
            and contrast_ratio(t.muted, t.bg) >= AA_BODY and contrast_ratio(t.on_surface, t.surface) >= AA_BODY
            and contrast_ratio(t.on_accent, t.accent) >= AA_BODY and contrast_ratio(t.accent, t.bg) >= AA_LARGE)


def get_theme(name: str, brand: dict) -> Theme:
    theme = build_theme(name if name in THEME_NAMES else "grid", brand)
    if not theme_passes(theme):
        log.warning("theme %s fails contrast with these brand colours — using grid", name)
        theme = build_theme("grid", brand)
    return theme


def marker_colors(t: Theme) -> tuple[Color, Color]:
    """Green/red markers that stay readable on the theme's surface colour."""
    return ensure_contrast(GOOD, t.surface, AA_LARGE), ensure_contrast(BAD, t.surface, AA_LARGE)


__all__ = ["Theme", "THEME_NAMES", "get_theme", "build_theme", "theme_passes", "marker_colors", "is_dark", "shift"]
