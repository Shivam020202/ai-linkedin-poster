"""Filled icon set drawn as vectors on a 24-unit grid (Lucide/Phosphor-like proportions).

icon(name, size, color) returns an RGBA layer, so 'cut-out' parts are truly transparent.
"""
from __future__ import annotations

import math

from PIL import Image, ImageDraw

from .effects import rgba

CLEAR = (0, 0, 0, 0)


class _P:
    """Tiny drawing helper in 24-unit icon space."""

    def __init__(self, size: int, color):
        self.ss = 4  # draw at 4x, downsample: smooth edges
        self.s = size * self.ss / 24
        self.img = Image.new("RGBA", (size * self.ss, size * self.ss), CLEAR)
        self.d = ImageDraw.Draw(self.img)
        self.c = rgba(color)
        self.size = size

    def _b(self, x0, y0, x1, y1):
        s = self.s
        return (x0 * s, y0 * s, x1 * s, y1 * s)

    def circle(self, cx, cy, r, clear=False):
        self.d.ellipse(self._b(cx - r, cy - r, cx + r, cy + r), fill=CLEAR if clear else self.c)

    def ring(self, cx, cy, r, w):
        self.circle(cx, cy, r)
        self.circle(cx, cy, r - w, clear=True)

    def rect(self, x0, y0, x1, y1, r=0, clear=False):
        self.d.rounded_rectangle(self._b(x0, y0, x1, y1), radius=r * self.s, fill=CLEAR if clear else self.c)

    def poly(self, pts, clear=False):
        self.d.polygon([(x * self.s, y * self.s) for x, y in pts], fill=CLEAR if clear else self.c)

    def line(self, pts, w=2.2, clear=False):
        s = self.s
        self.d.line([(x * s, y * s) for x, y in pts], fill=CLEAR if clear else self.c, width=max(1, int(w * s)),
                    joint="curve")
        for x, y in (pts[0], pts[-1]):  # round caps
            self.d.ellipse(((x - w / 2) * s, (y - w / 2) * s, (x + w / 2) * s, (y + w / 2) * s),
                           fill=CLEAR if clear else self.c)

    def arc(self, cx, cy, r, start, end, w=2.2):
        self.d.arc(self._b(cx - r, cy - r, cx + r, cy + r), start, end, fill=self.c, width=max(1, int(w * self.s)))

    def out(self):
        return self.img.resize((self.size, self.size), Image.LANCZOS)


def _star(cx, cy, r_out, r_in, n=5, rot=-90):
    pts = []
    for i in range(n * 2):
        r = r_out if i % 2 == 0 else r_in
        a = math.radians(rot + i * 180 / n)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def _search(p):
    p.ring(10.5, 10.5, 7.5, 2.6); p.line([(16, 16), (21, 21)], 3)
def _menu(p):
    for y in (6, 12, 18): p.rect(3, y - 1.4, 21, y + 1.4, 1.4)
def _user(p):
    p.circle(12, 8, 4.5); p.d.pieslice(p._b(3.5, 13.5, 20.5, 30.5), 180, 360, fill=p.c)
def _heart(p):
    p.circle(8, 9, 4.6); p.circle(16, 9, 4.6); p.poly([(3.6, 10.5), (20.4, 10.5), (12, 20.5)])
def _star_i(p):
    p.poly(_star(12, 12.6, 10, 4.3))
def _bell(p):
    p.d.pieslice(p._b(5, 3, 19, 17), 180, 360, fill=p.c); p.rect(5, 10, 19, 16); p.poly([(5, 15), (19, 15), (21, 18), (3, 18)])
    p.circle(12, 20, 2.2)
def _gear(p):
    for k in range(8):
        a = math.radians(k * 45)
        cx, cy = 12 + 8.6 * math.cos(a), 12 + 8.6 * math.sin(a)
        p.circle(cx, cy, 2.4)
    p.circle(12, 12, 8); p.circle(12, 12, 3.2, clear=True)
def _home(p):
    p.poly([(12, 2.5), (22, 11), (19.5, 11), (19.5, 21), (4.5, 21), (4.5, 11), (2, 11)]); p.rect(10, 14, 14, 21, 1, clear=True)
def _chart(p):
    p.rect(3, 13, 7.5, 21, 1.2); p.rect(9.8, 7, 14.2, 21, 1.2); p.rect(16.5, 3, 21, 21, 1.2)
def _lock(p):
    p.arc(12, 9, 5.2, 180, 360, 2.6); p.line([(6.8, 9), (6.8, 11)], 2.6); p.line([(17.2, 9), (17.2, 11)], 2.6)
    p.rect(4, 10.5, 20, 21.5, 2.5); p.circle(12, 15.2, 1.8, clear=True); p.rect(11.2, 15.5, 12.8, 18.5, 0.6, clear=True)
def _eye(p):
    p.d.ellipse(p._b(1.5, 5, 22.5, 19), fill=p.c); p.circle(12, 12, 4.8, clear=True); p.circle(12, 12, 2.6)
def _cursor(p):
    p.poly([(5, 2.5), (19, 13), (13, 14), (16.5, 21), (13.8, 22), (10.5, 15), (5.5, 19)])
def _layers(p):
    for i, y in enumerate((5, 10.5, 16)):
        p.poly([(12, y - 4), (22, y), (12, y + 4), (2, y)])
        if i < 2: p.poly([(12, y + 2.2), (22, y + 4.4), (12, y + 6.6), (2, y + 4.4)], clear=True)
def _grid(p):
    for x, y in ((3, 3), (13, 3), (3, 13), (13, 13)): p.rect(x, y, x + 8, y + 8, 2)
def _palette(p):
    p.circle(12, 12, 10); p.circle(17.5, 15.5, 3.2, clear=True)
    for cx, cy in ((7.5, 9), (12, 6.5), (16.5, 9), (7.5, 14.5)): p.circle(cx, cy, 1.7, clear=True)
def _type(p):
    p.rect(3, 3, 21, 7, 1); p.rect(10, 3, 14, 21, 1); p.rect(7.5, 18, 16.5, 21, 1)
def _phone(p):
    p.rect(5.5, 1.5, 18.5, 22.5, 3); p.rect(7.5, 4, 16.5, 20, 1.2, clear=True); p.rect(10, 2.6, 14, 3.6, 0.5, clear=True)
def _monitor(p):
    p.rect(2, 3, 22, 17, 2); p.rect(4, 5, 20, 15, 0.8, clear=True); p.rect(10.5, 17, 13.5, 20); p.rect(7, 19.5, 17, 21.5, 1)
def _sparkle(p):
    p.poly(_star(10, 13, 9, 2.4, 4, -90)); p.poly(_star(19, 5, 4, 1.1, 4, -90))
def _bolt(p):
    p.poly([(13.5, 1.5), (4, 13.5), (11, 13.5), (9.5, 22.5), (20, 9.5), (12.8, 9.5)])
def _clock(p):
    p.ring(12, 12, 10, 2.4); p.line([(12, 6.5), (12, 12), (16, 14)], 2.4)
def _check(p):
    p.line([(4, 12.5), (9.5, 18), (20, 6)], 3.2)
def _cross(p):
    p.line([(5, 5), (19, 19)], 3.2); p.line([(19, 5), (5, 19)], 3.2)
def _arrow(p):
    p.line([(3, 12), (20, 12)], 2.8); p.line([(13.5, 5.5), (20, 12), (13.5, 18.5)], 2.8)
def _toggle(p):
    p.rect(1.5, 6, 22.5, 18, 6); p.circle(16.5, 12, 4.2, clear=True)
def _chat(p):
    p.rect(2, 3, 22, 17, 4); p.poly([(6, 16), (6, 22), (12, 16)])
def _cart(p):
    p.poly([(2, 3), (5.5, 3), (7.5, 14), (19, 14), (21.5, 6), (6.5, 6), (6, 4.5)]); p.circle(9, 19, 2); p.circle(17, 19, 2)
def _filter(p):
    p.poly([(2.5, 3.5), (21.5, 3.5), (14, 12.5), (14, 20.5), (10, 18), (10, 12.5)])
def _bulb(p):
    p.circle(12, 9.5, 7.5); p.rect(8.5, 13, 15.5, 18, 1); p.rect(9, 19, 15, 21.5, 1.2)
def _target(p):
    p.ring(12, 12, 10, 2.2); p.ring(12, 12, 6, 2.2); p.circle(12, 12, 2.2)
def _compass(p):
    p.ring(12, 12, 10, 2.2); p.poly([(15.5, 8.5), (13.3, 13.3), (8.5, 15.5), (10.7, 10.7)])
def _puzzle(p):
    p.rect(3, 7, 17, 21, 2); p.circle(10, 6.5, 3); p.circle(17.5, 14, 3); p.circle(10, 21.5, 2.6, clear=True)
def _ruler(p):
    p.poly([(2, 16), (16, 2), (22, 8), (8, 22)])
    for i in range(1, 5):
        x, y = 4.5 + i * 2.8, 13.5 - i * 2.8
        p.line([(x, y), (x + 2.2 if i % 2 else x + 1.3, y + 2.2 if i % 2 else y + 1.3)], 1.2, clear=True)
def _wand(p):
    p.line([(3, 21), (14, 10)], 2.8); p.poly(_star(17.5, 6.5, 5, 1.6, 4, -45))
def _refresh(p):
    p.arc(12, 12, 8, 30, 315, 2.8); p.poly([(14.5, 2.5), (21.5, 3.5), (19.5, 10.5)])
def _moon(p):
    p.circle(11, 13, 9); p.circle(16, 8.5, 7.5, clear=True)
def _sun(p):
    p.circle(12, 12, 5)
    for k in range(8):
        a = math.radians(k * 45)
        p.line([(12 + 8 * math.cos(a), 12 + 8 * math.sin(a)), (12 + 10.5 * math.cos(a), 12 + 10.5 * math.sin(a))], 2.2)
def _image(p):
    p.rect(2, 4, 22, 20, 2.5); p.rect(4, 6, 20, 18, 1, clear=True)
    p.poly([(4.5, 17.5), (10, 10.5), (14, 15), (16, 12.8), (19.5, 17.5)]); p.circle(16.5, 8.8, 1.6)
def _play(p):
    p.circle(12, 12, 10.5); p.poly([(9.5, 7), (17.5, 12), (9.5, 17)], clear=True)
def _globe(p):
    p.ring(12, 12, 10, 2); p.d.ellipse(p._b(7.5, 2, 16.5, 22), outline=p.c, width=int(2 * p.s))
    p.line([(2.5, 12), (21.5, 12)], 2)
def _shield(p):
    p.poly([(12, 1.5), (21, 5), (20, 13), (12, 22.5), (4, 13), (3, 5)]); p.line([(8, 12), (11, 15), (16.5, 9)], 2.4, clear=True)
def _bookmark(p):
    p.poly([(5, 2), (19, 2), (19, 22), (12, 16.5), (5, 22)])
def _cube(p):
    p.poly([(12, 2), (21, 7), (12, 12), (3, 7)]); p.poly([(3, 8.5), (11.3, 13.3), (11.3, 22.5), (3, 17.5)])
    p.poly([(21, 8.5), (12.7, 13.3), (12.7, 22.5), (21, 17.5)])
def _brush(p):
    p.poly([(14, 2), (22, 10), (13.5, 15.5), (8.5, 10.5)]); p.d.pieslice(p._b(2, 12, 12, 22), 90, 270, fill=p.c)
    p.poly([(7, 12.5), (11.5, 17), (7, 22), (2, 22), (2, 17.5)])
def _accessibility(p):
    p.circle(12, 4, 2.4); p.line([(4, 8.5), (12, 10), (20, 8.5)], 2.4); p.line([(12, 10), (12, 15)], 2.6)
    p.line([(12, 15), (8, 22)], 2.6); p.line([(12, 15), (16, 22)], 2.6)


ICONS = {
    "search": _search, "menu": _menu, "user": _user, "heart": _heart, "star": _star_i, "bell": _bell,
    "gear": _gear, "home": _home, "chart": _chart, "lock": _lock, "eye": _eye, "cursor": _cursor,
    "layers": _layers, "grid": _grid, "palette": _palette, "type": _type, "phone": _phone, "monitor": _monitor,
    "sparkle": _sparkle, "bolt": _bolt, "clock": _clock, "check": _check, "cross": _cross, "arrow": _arrow,
    "toggle": _toggle, "chat": _chat, "cart": _cart, "filter": _filter, "bulb": _bulb, "target": _target,
    "compass": _compass, "puzzle": _puzzle, "ruler": _ruler, "wand": _wand, "refresh": _refresh,
    "moon": _moon, "sun": _sun, "image": _image, "play": _play, "globe": _globe, "shield": _shield,
    "bookmark": _bookmark, "cube": _cube, "brush": _brush, "accessibility": _accessibility,
}


def icon(name: str, size: int, color) -> Image.Image:
    p = _P(max(8, int(size)), color)
    ICONS.get(name, _sparkle)(p)
    return p.out()
