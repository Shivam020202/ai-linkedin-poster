"""WCAG 2.x contrast maths and automatic colour adjustment."""
from __future__ import annotations

Color = tuple[int, int, int]

AA_BODY = 4.5
AA_LARGE = 3.0


def hex_to_rgb(value: str) -> Color:
    value = value.lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def rgb_to_hex(rgb: Color) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def _channel(c: int) -> float:
    s = c / 255
    return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4


def luminance(rgb: Color) -> float:
    r, g, b = (_channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: Color, b: Color) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def mix(a: Color, b: Color, t: float) -> Color:
    """t=0 -> a, t=1 -> b."""
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))  # type: ignore[return-value]


def is_dark(rgb: Color) -> bool:
    return contrast_ratio(rgb, (255, 255, 255)) > contrast_ratio(rgb, (0, 0, 0))


def ensure_contrast(fg: Color, bg: Color, minimum: float = AA_BODY) -> Color:
    """Return fg, nudged toward black or white until it reaches `minimum` against bg."""
    if contrast_ratio(fg, bg) >= minimum:
        return fg
    target = (255, 255, 255) if is_dark(bg) else (0, 0, 0)
    for step in range(1, 21):
        candidate = mix(fg, target, step / 20)
        if contrast_ratio(candidate, bg) >= minimum:
            return candidate
    # the preferred direction can't make it (mid-tone bg): try the other extreme
    other = (0, 0, 0) if target == (255, 255, 255) else (255, 255, 255)
    return target if contrast_ratio(target, bg) >= contrast_ratio(other, bg) else other
