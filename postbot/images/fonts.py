"""Free Google Fonts (OFL) downloaded on first run, with system-font fallbacks."""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import requests
from PIL import ImageFont

from ..config import FONTS_DIR

log = logging.getLogger("fonts")

_GF = "https://raw.githubusercontent.com/google/fonts/main/ofl/"

# family -> {"variable": url} or {"static": {weight: url}}
FAMILIES: dict[str, dict] = {
    "inter": {"variable": _GF + "inter/Inter%5Bopsz,wght%5D.ttf"},
    "space-grotesk": {"variable": _GF + "spacegrotesk/SpaceGrotesk%5Bwght%5D.ttf"},
    "dm-sans": {"variable": _GF + "dmsans/DMSans%5Bopsz,wght%5D.ttf"},
    "poppins": {"static": {
        400: _GF + "poppins/Poppins-Regular.ttf",
        500: _GF + "poppins/Poppins-Medium.ttf",
        600: _GF + "poppins/Poppins-SemiBold.ttf",
        700: _GF + "poppins/Poppins-Bold.ttf",
        800: _GF + "poppins/Poppins-ExtraBold.ttf",
    }},
    "dm-serif-display": {"static": {400: _GF + "dmserifdisplay/DMSerifDisplay-Regular.ttf"}},
}

SYSTEM_FALLBACKS = {
    "regular": [
        "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/google-noto/NotoSans-Regular.ttf",
        "C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf",
    ],
    "bold": [
        "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/google-noto/NotoSans-Bold.ttf",
        "C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/Library/Fonts/Arial Bold.ttf",
    ],
}


def _local_name(url: str) -> str:
    return url.rsplit("/", 1)[-1].replace("%5B", "[").replace("%5D", "]")


def download_fonts(families: list[str] | None = None) -> list[str]:
    """Download the given families (default: all). Returns the files that are present."""
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    present = []
    for fam in families or list(FAMILIES):
        spec = FAMILIES.get(fam)
        if not spec:
            continue
        urls = [spec["variable"]] if "variable" in spec else list(spec["static"].values())
        for url in urls:
            dest = FONTS_DIR / _local_name(url)
            if not dest.exists():
                try:
                    resp = requests.get(url, timeout=60)
                    resp.raise_for_status()
                    dest.write_bytes(resp.content)
                    log.info("downloaded font %s", dest.name)
                except requests.RequestException as exc:
                    log.warning("could not download %s (%s) — will use a system font", dest.name, exc)
                    continue
            present.append(dest.name)
    return present


def _system_font(weight: int) -> str:
    for path in SYSTEM_FALLBACKS["bold" if weight >= 600 else "regular"] + SYSTEM_FALLBACKS["regular"]:
        if Path(path).exists():
            return path
    return ""


@lru_cache(maxsize=256)
def load_font(family: str, weight: int, size: int) -> ImageFont.FreeTypeFont:
    size = max(8, int(size))
    spec = FAMILIES.get(family, FAMILIES["inter"])
    if "variable" in spec:
        path = FONTS_DIR / _local_name(spec["variable"])
        if path.exists():
            font = ImageFont.truetype(str(path), size)
            try:
                axes = []
                for axis in font.get_variation_axes():
                    name = axis["name"].decode() if isinstance(axis["name"], bytes) else str(axis["name"])
                    if name.lower().startswith("weight"):
                        value = weight
                    elif name.lower().startswith("optical"):
                        value = size / 2  # px -> roughly pt; clamps below
                    else:
                        value = axis["default"]
                    axes.append(min(max(value, axis["minimum"]), axis["maximum"]))
                font.set_variation_by_axes(axes)
            except (OSError, KeyError):
                pass  # FreeType without variation support: default weight
            return font
    else:
        static = spec["static"]
        best = min(static, key=lambda w: abs(w - weight))
        path = FONTS_DIR / _local_name(static[best])
        if path.exists():
            return ImageFont.truetype(str(path), size)
    fallback = _system_font(weight)
    if fallback:
        return ImageFont.truetype(fallback, size)
    return ImageFont.load_default(size)
