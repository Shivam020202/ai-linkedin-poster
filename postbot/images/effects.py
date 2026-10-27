"""Layer effects that make flat drawings feel like real objects: shadows, sticker cutouts, tilt, gloss."""
from __future__ import annotations

from PIL import Image, ImageChops, ImageDraw, ImageFilter

Color = tuple[int, int, int]


def layer(w: int, h: int) -> Image.Image:
    return Image.new("RGBA", (max(1, int(w)), max(1, int(h))), (0, 0, 0, 0))


def rgba(c: Color, a: int = 255) -> tuple[int, int, int, int]:
    return (c[0], c[1], c[2], a)


def drop_shadow(obj: Image.Image, blur: int, offset=(0, 0), color: Color = (0, 0, 0), opacity: float = 0.35,
                pad: int | None = None) -> Image.Image:
    """Return a bigger RGBA image: soft shadow under the object. The object sits at (pad, pad)."""
    pad = int(blur * 1.8 + max(abs(offset[0]), abs(offset[1]))) if pad is None else pad
    w, h = obj.size
    out = layer(w + 2 * pad, h + 2 * pad)
    alpha = obj.getchannel("A").point(lambda a: int(a * opacity))
    sh = Image.new("RGBA", obj.size, rgba(color))
    sh.putalpha(alpha)
    shadow = layer(*out.size)
    shadow.paste(sh, (pad + offset[0], pad + offset[1]), sh)
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur))
    out.alpha_composite(shadow)
    out.alpha_composite(obj, (pad, pad))
    return out


def sticker(obj: Image.Image, stroke: int, color: Color = (255, 255, 255)) -> Image.Image:
    """Die-cut sticker outline around everything opaque in the layer (the 'cutout' look)."""
    pad = stroke + 2
    w, h = obj.size
    out = layer(w + 2 * pad, h + 2 * pad)
    alpha = Image.new("L", out.size, 0)
    alpha.paste(obj.getchannel("A"), (pad, pad))
    grown = alpha.filter(ImageFilter.MaxFilter(_odd(stroke * 2 + 1)))
    grown = grown.filter(ImageFilter.GaussianBlur(1)).point(lambda a: 255 if a > 110 else int(a * 2.2))
    base = Image.new("RGBA", out.size, rgba(color))
    base.putalpha(grown)
    out.alpha_composite(base)
    out.alpha_composite(obj, (pad, pad))
    return out


def _odd(n: int) -> int:
    n = max(3, int(n))
    return n if n % 2 else n + 1


def tilt(img: Image.Image, amount: float = 0.12, direction: str = "left") -> Image.Image:
    """Perspective tilt: one vertical edge shrinks, like a device turned slightly away."""
    w, h = img.size
    dy = h * amount / 2
    dx = w * amount * 0.35
    if direction == "left":   # left edge farther away
        dst = [(dx, dy), (w, 0), (w, h), (dx, h - dy)]
    else:
        dst = [(0, 0), (w - dx, dy), (w - dx, h - dy), (0, h)]
    src = [(0, 0), (w, 0), (w, h), (0, h)]
    coeffs = _perspective_coeffs(dst, src)
    return img.transform((w, h), Image.PERSPECTIVE, coeffs, Image.BICUBIC)


def _solve(a, b):
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        m[col], m[piv] = m[piv], m[col]
        for r in range(n):
            if r != col and m[r][col]:
                f = m[r][col] / m[col][col]
                m[r] = [x - f * y for x, y in zip(m[r], m[col])]
    return [m[i][n] / m[i][i] for i in range(n)]


def _perspective_coeffs(pa, pb):
    """Solve the 8 perspective coefficients mapping pa (output) -> pb (input), pure Python."""
    rows, rhs = [], []
    for (x, y), (u, v) in zip(pa, pb):
        rows.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        rows.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        rhs += [u, v]
    return _solve(rows, rhs)


def rotate(img: Image.Image, degrees: float) -> Image.Image:
    return img.rotate(degrees, resample=Image.BICUBIC, expand=True)


def vgradient(size, top: Color, bottom: Color, alpha: int = 255) -> Image.Image:
    mask = Image.linear_gradient("L").resize(size)
    img = Image.composite(Image.new("RGBA", size, rgba(bottom, alpha)), Image.new("RGBA", size, rgba(top, alpha)), mask)
    return img


def diag_gradient(size, a: Color, b: Color) -> Image.Image:
    """Smooth top-left -> bottom-right gradient (a 2x2 colour mesh, upscaled)."""
    mid = tuple((x + y) // 2 for x, y in zip(a, b))
    mesh = Image.new("RGB", (2, 2))
    mesh.putdata([a, mid, mid, b])
    big = mesh.resize((max(2, size[0] * 2), max(2, size[1] * 2)), Image.BILINEAR)
    w, h = big.size
    return big.crop((w // 4, h // 4, w // 4 + size[0], h // 4 + size[1])).convert("RGBA")


def rounded_mask(size, r: int) -> Image.Image:
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=max(0, int(r)), fill=255)
    return m


def fill_rounded(img: Image.Image, box, r, fill_img: Image.Image) -> None:
    """Paste a (gradient) image into a rounded rectangle area of img."""
    x0, y0, x1, y1 = (int(v) for v in box)
    size = (max(1, x1 - x0), max(1, y1 - y0))
    src = fill_img.resize(size) if fill_img.size != size else fill_img
    mask = ImageChops.multiply(rounded_mask(size, r), src.getchannel("A")) if src.mode == "RGBA" else rounded_mask(size, r)
    img.paste(src.convert("RGB") if img.mode == "RGB" else src, (x0, y0), mask)


def gloss(obj: Image.Image, strength: float = 0.22) -> Image.Image:
    """Soft top highlight across the object's opaque area (glossy plastic/glass feel)."""
    w, h = obj.size
    hl = Image.linear_gradient("L").rotate(180).resize((w, h)).point(lambda v: int(max(0, v - 128) * 2 * strength))
    alpha = ImageChops.multiply(hl, obj.getchannel("A"))
    white = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    white.putalpha(alpha)
    out = obj.copy()
    out.alpha_composite(white)
    return out


def paste_center(canvas: Image.Image, obj: Image.Image, cx: float, cy: float) -> None:
    canvas.alpha_composite(obj, (int(cx - obj.width / 2), int(cy - obj.height / 2))) if canvas.mode == "RGBA" \
        else canvas.paste(obj, (int(cx - obj.width / 2), int(cy - obj.height / 2)), obj)


def fit_into(obj: Image.Image, max_w: float, max_h: float) -> Image.Image:
    k = min(max_w / obj.width, max_h / obj.height)
    if abs(k - 1) < 0.01:
        return obj
    return obj.resize((max(1, int(obj.width * k)), max(1, int(obj.height * k))), Image.LANCZOS)
