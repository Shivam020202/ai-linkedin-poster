"""Painted styles: backgrounds and panels for the gradient, glass, tiles and skeuo themes.

Every painted background is checked against the theme's text colours using its real pixels
(sampled inside the content margins). If anything is under WCAG AA, the background is dimmed
or the text colour adjusted until it passes. Translucent panels do the same for their own region.
"""
from __future__ import annotations

import math
import random
from dataclasses import replace

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter

from .contrast import AA_BODY, AA_LARGE, Color, contrast_ratio, ensure_contrast, is_dark, mix
from .themes import Theme, shift

WHITE: Color = (255, 255, 255)
BLACK: Color = (0, 0, 0)


def _samples(img: Image.Image, box=None, n=(36, 45)) -> list[Color]:
    region = img.crop(box) if box else img
    raw = region.convert("RGB").resize(n, Image.BILINEAR).tobytes()
    return [tuple(raw[i:i + 3]) for i in range(0, len(raw), 3)]


def min_contrast(color: Color, samples: list[Color]) -> float:
    return min(contrast_ratio(color, s) for s in samples)


def _worst(color: Color, samples: list[Color]) -> Color:
    return min(samples, key=lambda s: contrast_ratio(color, s))


def _ensure_all(color: Color, samples: list[Color], ratio: float) -> Color:
    """Adjust color until it passes against every sample (the worst pixel can change as the colour moves)."""
    for _ in range(8):
        worst = _worst(color, samples)
        if contrast_ratio(color, worst) >= ratio:
            break
        color = ensure_contrast(color, worst, ratio + 0.05)
    return color


def _vgradient(size, top: Color, bottom: Color) -> Image.Image:
    mask = Image.linear_gradient("L").resize(size)
    return Image.composite(Image.new("RGB", size, bottom), Image.new("RGB", size, top), mask)


def _round_mask(size, r: int, value: int = 255) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=max(0, r), fill=value)
    return mask


class Styler:
    def __init__(self, theme: Theme, W: int, H: int, k: float, margin: int):
        self.t, self.W, self.H, self.k, self.M = theme, W, H, k, margin
        self.rng = random.Random(7)  # same texture on every slide

    def px(self, v: float) -> int:
        return round(v * self.k)

    # ---- background --------------------------------------------------------
    def prepare(self) -> tuple[Image.Image, Theme]:
        """Paint the background once and return it with contrast-checked theme colours."""
        t = self.t
        painter = {"gradient": self._bg_gradient, "glass": self._bg_glass, "tiles": self._bg_tiles,
                   "skeuo": self._bg_skeuo, "aurora": self._bg_aurora, "editorial": self._bg_editorial,
                   "brutal": self._bg_brutal, "noir": self._bg_noir, "blueprint": self._bg_blueprint,
                   "clay": self._bg_clay}.get(t.style)
        if painter is None:
            return Image.new("RGB", (self.W, self.H), t.bg), t
        img = painter()
        content = (self.M, self.M, self.W - self.M, self.H - self.M)
        light_text = not is_dark(t.fg)
        for _ in range(14):  # darken/lighten the background until titles pass AA against every pixel
            samples = _samples(img, content)
            if min_contrast(t.fg, samples) >= AA_BODY + 0.3:
                break
            # scale brightness (keeps colours rich) rather than mixing in grey
            img = ImageEnhance.Brightness(img).enhance(0.9) if light_text \
                else Image.blend(img, Image.new("RGB", img.size, WHITE), 0.15)
        samples = _samples(img, content)
        avg = img.crop(content).resize((1, 1), Image.BOX).getpixel((0, 0))
        fixed = replace(
            t, bg=avg,
            body=_ensure_all(t.body, samples, AA_BODY),
            muted=_ensure_all(t.muted, samples, AA_BODY),
            accent=_ensure_all(t.accent, samples, AA_LARGE),
        )
        fixed = replace(fixed, on_accent=ensure_contrast(fixed.on_accent, fixed.accent, AA_BODY))
        self.t = fixed
        return img, fixed

    def _bg_gradient(self) -> Image.Image:
        c = self.t.palette
        mesh = Image.new("RGB", (2, 2))
        mesh.putdata([c[0], c[1], c[3], c[2]])
        img = mesh.resize((self.W, self.H), Image.BICUBIC)
        # soft light bloom in the top-right corner
        glow = Image.new("L", (self.W // 4, self.H // 4), 0)
        ImageDraw.Draw(glow).ellipse((self.W // 8, -self.H // 16, self.W // 3, self.H // 10), fill=90)
        glow = glow.filter(ImageFilter.GaussianBlur(28)).resize((self.W, self.H), Image.BICUBIC)
        img.paste(shift(c[1], 0, 0.5, 1.6), (0, 0), glow)
        return self._grain(img, 0.035)

    def _bg_glass(self) -> Image.Image:
        t = self.t
        sw, sh = self.W // 6, self.H // 6
        small = Image.new("RGB", (sw, sh), t.bg)
        d = ImageDraw.Draw(small)
        blobs = [(0.85, 0.12, 0.42), (0.1, 0.38, 0.36), (0.75, 0.72, 0.4), (0.25, 0.95, 0.3)]
        for (cx, cy, r), color in zip(blobs, t.palette):
            rr = r * sw
            d.ellipse((cx * sw - rr, cy * sh - rr, cx * sw + rr, cy * sh + rr), fill=color)
        small = small.filter(ImageFilter.GaussianBlur(sw / 9))
        img = small.resize((self.W, self.H), Image.BICUBIC)
        img = Image.blend(img, Image.new("RGB", img.size, t.bg), 0.2)
        return self._grain(img, 0.03)

    def _bg_tiles(self) -> Image.Image:
        t = self.t
        img = Image.new("RGB", (self.W, self.H), t.bg)
        d = ImageDraw.Draw(img)
        for y0, size in ((0, self.px(58)), (self.H - self.px(42), self.px(42))):
            x, i = 0, 0
            while x < self.W:
                self._tile(d, x, y0, size, i)
                x += size
                i += 1
        return img

    def _tile(self, d, x, y, s, i):
        """Bauhaus-style tile motifs in brand colours."""
        pal = self.t.palette
        bg = pal[(i * 3) % len(pal)]
        fg = pal[(i * 3 + 2) % len(pal)] if pal[(i * 3 + 2) % len(pal)] != bg else self.t.bg
        d.rectangle((x, y, x + s, y + s), fill=bg)
        motif = (i * 7) % 5
        if motif == 0:
            d.pieslice((x - s, y - s, x + s, y + s), 0, 90, fill=fg)            # quarter circle
        elif motif == 1:
            d.ellipse((x + s * 0.2, y + s * 0.2, x + s * 0.8, y + s * 0.8), fill=fg)
        elif motif == 2:
            d.polygon([(x, y + s), (x + s, y + s), (x + s, y)], fill=fg)       # triangle
        elif motif == 3:
            d.rectangle((x, y + s / 2, x + s, y + s), fill=fg)                # half block
        d.line([(x, y), (x, y + s)], fill=self.t.fg, width=2)

    def _bg_skeuo(self) -> Image.Image:
        t = self.t
        img = _vgradient((self.W, self.H), mix(t.bg, WHITE, 0.25), mix(t.bg, BLACK, 0.04))
        img = self._grain(img, 0.07)
        vignette = Image.radial_gradient("L").resize((self.W, self.H), Image.BICUBIC)
        vignette = vignette.point(lambda v: max(0, v - 120) * 0.45)
        img.paste((70, 52, 36), (0, 0), vignette)
        return img

    def _bg_aurora(self) -> Image.Image:
        """Dark sky with soft ribbons of light and a few stars."""
        t = self.t
        sw, sh = self.W // 8, self.H // 8
        small = Image.new("RGB", (sw, sh), t.bg)
        d = ImageDraw.Draw(small)
        for k, color in enumerate(t.palette):
            pts = []
            for i in range(0, 41):
                x = sw * i / 40
                y = sh * (0.18 + 0.2 * k) + math.sin(i / 40 * math.pi * 2 + k * 1.7) * sh * 0.08
                pts.append((x, y))
            d.line(pts, fill=color, width=int(sh * 0.07), joint="curve")
        small = small.filter(ImageFilter.GaussianBlur(sh * 0.05))
        img = small.resize((self.W, self.H), Image.BICUBIC)
        d = ImageDraw.Draw(img)
        for _ in range(70):
            x, y, r = self.rng.random() * self.W, self.rng.random() * self.H * 0.6, self.rng.choice((1, 1, 2)) * self.k
            d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255))
        return self._grain(img, 0.025)

    def _bg_editorial(self) -> Image.Image:
        """Newsprint: warm paper, a masthead double rule and faint column lines."""
        t = self.t
        img = self._grain(Image.new("RGB", (self.W, self.H), t.bg), 0.03)
        d = ImageDraw.Draw(img)
        y = self.M - self.px(26)
        d.line([(self.M, y), (self.W - self.M, y)], fill=t.fg, width=self.px(4))
        d.line([(self.M, y + self.px(9)), (self.W - self.M, y + self.px(9))], fill=t.fg, width=max(1, self.px(1.5)))
        for i in range(1, 4):
            x = self.M + (self.W - 2 * self.M) * i / 4
            d.line([(x, self.M + self.px(80)), (x, self.H - self.M - self.px(90))], fill=mix(t.bg, t.fg, 0.07),
                   width=max(1, self.px(1)))
        yb = self.H - self.M - self.px(76)
        d.line([(self.M, yb), (self.W - self.M, yb)], fill=t.fg, width=max(1, self.px(1.5)))
        return img

    def _bg_brutal(self) -> Image.Image:
        """Neo-brutalism: flat bright colour, thick frame, chunky black-outlined shapes in the margins
        (kept outside the text area so they never sit under words)."""
        t = self.t
        img = Image.new("RGB", (self.W, self.H), t.bg)
        d = ImageDraw.Draw(img)
        ol = max(4, self.px(5))
        R = self.M * 0.95
        cx, cy = self.W - self.M * 0.15, self.M * 0.15
        pts = [(cx + (R if i % 2 == 0 else R * 0.6) * math.cos(math.radians(i * 15)),
                cy + (R if i % 2 == 0 else R * 0.6) * math.sin(math.radians(i * 15))) for i in range(24)]
        d.polygon(pts, fill=t.palette[0], outline=BLACK, width=ol)
        r = int(self.M * 1.0)
        d.pieslice((-r, self.H - r, r, self.H + r), 270, 360, fill=t.palette[1], outline=BLACK, width=ol)
        ph = int(self.M * 0.55)
        d.rounded_rectangle((self.W - self.px(300), self.H - ph, self.W + self.px(40), self.H + self.px(40)),
                            radius=ph, fill=t.palette[2], outline=BLACK, width=ol)
        d.rectangle((0, 0, self.W - 1, self.H - 1), outline=BLACK, width=self.px(12))
        return img

    def _bg_noir(self) -> Image.Image:
        """Near-black with a faint dot grid, accent crop marks and a soft glow."""
        t = self.t
        img = Image.new("RGB", (self.W, self.H), t.bg)
        d = ImageDraw.Draw(img)
        step = self.px(36)
        dot = mix(t.bg, WHITE, 0.09)
        for x in range(step // 2, self.W, step):
            for y in range(step // 2, self.H, step):
                d.ellipse((x - self.k, y - self.k, x + self.k, y + self.k), fill=dot)
        L, w, o = self.px(46), max(2, self.px(3)), self.px(30)
        for (x, y, sx, sy) in ((o, o, 1, 1), (self.W - o, o, -1, 1), (o, self.H - o, 1, -1),
                               (self.W - o, self.H - o, -1, -1)):
            d.line([(x, y), (x + sx * L, y)], fill=t.accent, width=w)
            d.line([(x, y), (x, y + sy * L)], fill=t.accent, width=w)
        glow = Image.new("L", (self.W // 4, self.H // 4), 0)
        ImageDraw.Draw(glow).ellipse((self.W // 6, self.H // 7, self.W // 3, int(self.H / 3.2)), fill=60)
        glow = glow.filter(ImageFilter.GaussianBlur(self.W // 30)).resize((self.W, self.H), Image.BICUBIC)
        img.paste(t.accent, (0, 0), glow)
        return self._grain(img, 0.02)

    def _bg_blueprint(self) -> Image.Image:
        """Technical drawing: fine and major grid lines and a frame."""
        t = self.t
        img = Image.new("RGB", (self.W, self.H), t.bg)
        d = ImageDraw.Draw(img)
        fine, major = self.px(27), self.px(135)
        for x in range(0, self.W, fine):
            d.line([(x, 0), (x, self.H)], fill=mix(t.bg, WHITE, 0.07 if x % major else 0.16), width=max(1, self.px(1)))
        for y in range(0, self.H, fine):
            d.line([(0, y), (self.W, y)], fill=mix(t.bg, WHITE, 0.07 if y % major else 0.16), width=max(1, self.px(1)))
        o = self.px(24)
        d.rectangle((o, o, self.W - o, self.H - o), outline=mix(t.bg, WHITE, 0.5), width=max(2, self.px(2)))
        return img

    def _bg_clay(self) -> Image.Image:
        """Soft pastel claymorphism: puffy shaded blobs on a light backdrop."""
        t = self.t
        img = Image.new("RGB", (self.W, self.H), t.bg)
        for (cx, cy, r), color in zip(((0.94, 0.06, 0.22), (0.0, 0.60, 0.15), (0.90, 0.97, 0.19)), t.palette):
            R = int(r * self.W)
            blob = Image.new("RGBA", (2 * R, 2 * R), (0, 0, 0, 0))
            ImageDraw.Draw(blob).ellipse((0, 0, 2 * R - 1, 2 * R - 1), fill=(*color, 255))
            shade = Image.radial_gradient("L").resize((2 * R, 2 * R)).point(lambda v: int(min(255, v * v / 255 * 0.55)))
            dark = Image.new("RGBA", blob.size, (*mix(color, BLACK, 0.4), 255))
            dark.putalpha(ImageChops.multiply(shade, blob.getchannel("A")))
            blob.alpha_composite(dark)
            hl = Image.new("L", blob.size, 0)  # soft specular highlight, top-left: the 'puffy clay' look
            ImageDraw.Draw(hl).ellipse((int(0.35 * R), int(0.25 * R), int(1.05 * R), int(0.8 * R)), fill=150)
            hl = ImageChops.multiply(hl.filter(ImageFilter.GaussianBlur(R // 5)), blob.getchannel("A"))
            white = Image.new("RGBA", blob.size, (255, 255, 255, 255))
            white.putalpha(hl)
            blob.alpha_composite(white)
            sh = Image.new("L", (int(2.4 * R), int(2.4 * R)), 0)
            ImageDraw.Draw(sh).ellipse((int(0.2 * R), int(0.3 * R), int(2.2 * R), int(2.3 * R)), fill=70)
            sh = sh.filter(ImageFilter.GaussianBlur(R // 6))
            x, y = int(cx * self.W - R), int(cy * self.H - R)
            img.paste(mix(t.bg, BLACK, 0.25), (x - int(0.2 * R), y), sh)
            img.paste(blob, (x, y), blob)
        return img

    def _grain(self, img: Image.Image, amount: float) -> Image.Image:
        noise = Image.effect_noise((self.W, self.H), 40).convert("RGB")
        return Image.blend(img, noise, amount)

    # ---- panels --------------------------------------------------------------
    def panel(self, img: Image.Image, box, radius: float, outline: Color | None = None, width: int = 2,
              fill: Color | None = None) -> None:
        x0, y0, x1, y1 = (round(v) for v in box)
        if x1 - x0 < 4 or y1 - y0 < 4:
            return
        t = self.t
        r = round(radius * t.radius)
        d = ImageDraw.Draw(img)
        if t.style == "tiles":
            off = self.px(10)
            d.rectangle((x0 + off, y0 + off, x1 + off, y1 + off), fill=t.fg)
            d.rectangle((x0, y0, x1, y1), fill=fill or t.surface, outline=outline or t.fg, width=max(3, width))
        elif t.style == "skeuo":
            self._shadow(img, (x0, y0, x1, y1), r, (0, self.px(10)), self.px(14), (60, 40, 20), 110)
            base = fill or t.surface
            grad = _vgradient((x1 - x0, y1 - y0), mix(base, WHITE, 0.5), mix(base, t.line, 0.25))
            img.paste(grad, (x0, y0), _round_mask(grad.size, r))
            d.rounded_rectangle((x0, y0, x1, y1), radius=r, outline=outline or mix(t.line, BLACK, 0.12),
                                width=max(2, width))
            d.line([(x0 + r, y0 + 2), (x1 - r, y0 + 2)], fill=WHITE, width=2)  # top bevel highlight
            self._stitch(d, x0, y0, x1, y1, r, mix(base, t.line, 0.9))
        elif t.style in ("glass", "gradient"):
            self._shadow(img, (x0, y0, x1, y1), r, (0, self.px(14)), self.px(22), BLACK, 90)
            self._frost(img, (x0, y0, x1, y1), r, blur=self.px(26 if t.style == "glass" else 14))
            border = outline or WHITE
            ring = Image.new("L", (x1 - x0, y1 - y0), 0)
            ImageDraw.Draw(ring).rounded_rectangle((0, 0, x1 - x0 - 1, y1 - y0 - 1), radius=r,
                                                   outline=255, width=max(2, width))
            if not outline:  # specular rim: bright along the top, fading down like real glass
                fade = Image.linear_gradient("L").rotate(180).resize(ring.size).point(lambda v: 50 + v * 0.7)
                ring = ImageChops.multiply(ring, fade)
            img.paste(border, (x0, y0), ring)
        else:
            d.rounded_rectangle((x0, y0, x1, y1), radius=r, fill=fill or t.surface,
                                outline=outline or t.line, width=width)

    def _frost(self, img, box, r, blur):
        """Blur what's behind the panel, tint it until the panel text passes AA, add a sheen."""
        x0, y0, x1, y1 = box
        t = self.t
        region = img.crop(box).filter(ImageFilter.GaussianBlur(blur))
        frosted = Image.blend(region, Image.new("RGB", region.size, WHITE), 0.10)
        light_text = not is_dark(t.on_surface)
        pane, amount = frosted, 0.0
        while amount < 0.95:
            pane = ImageEnhance.Brightness(frosted).enhance(1 - amount) if light_text \
                else Image.blend(frosted, Image.new("RGB", region.size, WHITE), amount)
            if min_contrast(t.on_surface, _samples(pane, n=(16, 16))) >= AA_BODY + 0.3:
                break
            amount += 0.07
        mask = _round_mask(region.size, r)
        img.paste(pane, (x0, y0), mask)
        sheen = Image.linear_gradient("L").rotate(180).resize(region.size).point(lambda v: v * 0.16)
        img.paste(WHITE, (x0, y0), ImageChops.multiply(sheen, mask))

    def _shadow(self, img, box, r, offset, blur, color, alpha):
        x0, y0, x1, y1 = box
        pad = blur * 3
        w, h = x1 - x0 + 2 * pad, y1 - y0 + 2 * pad
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle((pad, pad, w - pad, h - pad), radius=r, fill=alpha)
        mask = mask.filter(ImageFilter.GaussianBlur(blur))
        bx, by = x0 - pad + offset[0], y0 - pad + offset[1]
        img.paste(color, (bx, by, bx + w, by + h), mask)

    def _stitch(self, d, x0, y0, x1, y1, r, color):
        """Dashed 'stitching' inset from the edge — classic skeuomorphic leather/fabric detail."""
        inset, dash = self.px(12), self.px(9)
        lo, hi = r + inset, r + inset
        for x in range(x0 + lo, x1 - hi, dash * 2):
            d.line([(x, y0 + inset), (min(x + dash, x1 - hi), y0 + inset)], fill=color, width=2)
            d.line([(x, y1 - inset), (min(x + dash, x1 - hi), y1 - inset)], fill=color, width=2)
        for y in range(y0 + lo, y1 - hi, dash * 2):
            d.line([(x0 + inset, y), (x0 + inset, min(y + dash, y1 - hi))], fill=color, width=2)
            d.line([(x1 - inset, y), (x1 - inset, min(y + dash, y1 - hi))], fill=color, width=2)
