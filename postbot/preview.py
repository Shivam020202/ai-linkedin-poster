"""`preview`: render the sample posts in every theme so you can pick favourites."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from .config import ROOT
from .content.sample import SINGLES, sample_post
from .images.render import Renderer
from .images.themes import THEME_NAMES


def contact_sheet(paths: list[Path], dest: Path, cols: int = 5, thumb_w: int = 324) -> None:
    thumbs = [Image.open(p) for p in paths]
    th = round(thumb_w * thumbs[0].height / thumbs[0].width)
    rows = (len(thumbs) + cols - 1) // cols
    pad = 16
    sheet = Image.new("RGB", (cols * (thumb_w + pad) + pad, rows * (th + pad) + pad), (230, 230, 232))
    for i, im in enumerate(thumbs):
        sheet.paste(im.resize((thumb_w, th), Image.LANCZOS),
                    (pad + (i % cols) * (thumb_w + pad), pad + (i // cols) * (th + pad)))
    sheet.save(dest)


def run_preview(cfg: dict, themes: list[str] | None = None, out: Path = ROOT / "preview") -> list[Path]:
    sheets = []
    for theme in themes or THEME_NAMES:
        renderer = Renderer(cfg, theme, seed=theme)
        tdir = out / theme
        paths = renderer.render_post(sample_post("carousel"), tdir / "carousel", kicker="Problem solving")["images"]
        for kind in SINGLES:
            renderer = Renderer(cfg, theme, seed=f"{theme}-{kind}")  # fresh seed per post, like real runs
            paths += renderer.render_post(sample_post(kind), tdir / kind, kicker="Problem solving")["images"]
        sheet = out / f"overview-{theme}.png"
        contact_sheet(paths, sheet)
        sheets.append(sheet)
    return sheets
