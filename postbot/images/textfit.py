"""Wrap + shrink text to fit a box. Never overflows: if even the minimum size can't fit, it truncates with '…'."""
from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

from .fonts import load_font


@dataclass
class Fit:
    lines: list[str]
    font: ImageFont.FreeTypeFont
    size: int
    line_px: int
    width: int
    truncated: bool = False

    @property
    def height(self) -> int:
        return self.line_px * len(self.lines)


_SUBSTITUTES = {"\u2192": "->", "\u2190": "<-", "\u2014": "-", "\u2013": "-", "\u2018": "'", "\u2019": "'",
                "\u201c": '"', "\u201d": '"', "\u2026": "...", "\u2022": "-", "\u00d7": "x"}
_missing_cache: dict[tuple[int, str], bool] = {}


def _missing(font, ch: str) -> bool:
    """True if the font has no glyph for ch (renders the same as a known-missing codepoint)."""
    key = (id(font), ch)
    if key not in _missing_cache:
        try:
            _missing_cache[key] = _raster(font, ch) == _raster(font, "\U0010fffd")
        except (OSError, ValueError):
            _missing_cache[key] = False
    return _missing_cache[key]


def _raster(font, ch: str) -> bytes:
    size = int(font.size * 2)
    img = Image.new("L", (size, size))
    ImageDraw.Draw(img).text((size // 4, size // 4), ch, font=font, fill=255)
    return img.tobytes()


def clean_for_font(text: str, font) -> str:
    out = []
    for ch in text:
        if ord(ch) < 128 or not _missing(font, ch):
            out.append(ch)
        else:
            out.append(_SUBSTITUTES.get(ch, ""))
    return "".join(out)


def _break_word(word: str, font, max_w: float) -> list[str]:
    parts, cur = [], ""
    for ch in word:
        if cur and font.getlength(cur + ch) > max_w:
            parts.append(cur)
            cur = ch
        else:
            cur += ch
    return parts + ([cur] if cur else [])


def wrap(text: str, font, max_w: float) -> list[str]:
    lines: list[str] = []
    for para in text.split("\n"):
        words = para.split()
        if not words:
            lines.append("")
            continue
        cur = ""
        for word in words:
            pieces = [word] if font.getlength(word) <= max_w else _break_word(word, font, max_w)
            for piece in pieces:
                trial = f"{cur} {piece}" if cur else piece
                if font.getlength(trial) <= max_w:
                    cur = trial
                else:
                    if cur:
                        lines.append(cur)
                    cur = piece
        lines.append(cur)
    return lines


def _ellipsize(line: str, font, max_w: float) -> str:
    line = line.rstrip(" ,;:—-.")
    while line and font.getlength(line + "…") > max_w:
        line = line[:-1].rstrip()
    return line + "…"


def fit_text(text: str, family: str, weight: int, max_w: int, max_h: int,
             max_size: int, min_size: int, line_height: float = 1.25) -> Fit:
    text = (text or "").strip()
    size = max_size
    while True:
        font = load_font(family, weight, size)
        line_px = round(size * line_height)
        lines = wrap(clean_for_font(text, font), font, max_w) if text else []
        if line_px * len(lines) <= max_h or size <= min_size:
            break
        size = max(min_size, size - 2)
    truncated = False
    max_lines = max(1, max_h // line_px)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = _ellipsize(lines[-1], font, max_w)
        truncated = True
    width = int(max((font.getlength(l) for l in lines), default=0))
    return Fit(lines, font, size, line_px, width, truncated)


def draw_fit(draw: ImageDraw.ImageDraw, fit: Fit, x: int, y: int, fill, align: str = "left",
             box_w: int | None = None, shadow=None) -> int:
    """Draw a Fit at (x, y). Returns the y just below the block. `shadow` = letterpress highlight colour."""
    for line in fit.lines:
        lx = x
        if align == "center" and box_w:
            lx = x + (box_w - fit.font.getlength(line)) / 2
        # 'ls' anchor = left/baseline; place baseline ~80% down the line box so ascenders stay inside
        base = y + round(fit.line_px * 0.5 + fit.size * 0.36)
        if shadow:
            draw.text((lx, base + max(1, fit.size // 30)), line, font=fit.font, fill=shadow, anchor="ls")
        draw.text((lx, base), line, font=fit.font, fill=fill, anchor="ls")
        y += fit.line_px
    return y
