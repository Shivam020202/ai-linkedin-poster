"""Realistic UI mockups: app screens inside a phone, web layouts inside a browser window.

Screens are drawn in design units (phone 390 wide, browser 1280 wide) and scaled, so they look like
real product UI rather than wireframe bars. Labels come from the post, so the mockup is about the topic.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from PIL import Image, ImageDraw

from .contrast import ensure_contrast, mix
from .effects import diag_gradient, gloss, layer, rgba, rounded_mask, vgradient
from .fonts import load_font
from .icons import icon

INK = (22, 24, 33)
MUTED = (112, 117, 130)
LINE = (229, 231, 236)
SCREEN = (247, 247, 250)
CARD = (255, 255, 255)
GOOD = (22, 150, 80)
BAD = (214, 48, 49)


@dataclass
class UI:
    accent: tuple
    accent2: tuple
    font: str
    heading: str
    dark: bool = False


class Canvas:
    """Draws UI in design units; u = pixels per unit."""

    def __init__(self, w: int, h: int, units_w: float, ui: UI, bg=SCREEN):
        self.img = Image.new("RGBA", (int(w), int(h)), rgba(bg))
        self.d = ImageDraw.Draw(self.img)
        self.u = w / units_w
        self.ui = ui
        self.H = h / self.u  # height in units
        self.on_accent = ensure_contrast((255, 255, 255), ui.accent, 4.5)

    def _r(self, *v):
        return [x * self.u for x in v]

    def text(self, x, y, s, size, weight=500, color=INK, anchor="la", family=None, max_w=None):
        font = load_font(family or self.ui.font, weight, max(6, size * self.u))
        s = str(s)
        if max_w:
            while s and font.getlength(s) > max_w * self.u:
                s = s[:-2] + "…" if len(s) > 2 else ""
        self.d.text((x * self.u, y * self.u), s, font=font, fill=rgba(color), anchor=anchor)

    def rect(self, x0, y0, x1, y1, r=0, fill=None, outline=None, width=1):
        if fill is None and outline is None:
            return
        self.d.rounded_rectangle(self._r(x0, y0, x1, y1), radius=r * self.u, fill=rgba(fill) if fill else None,
                                 outline=rgba(outline) if outline else None, width=max(1, int(width * self.u)))

    def circle(self, cx, cy, r, fill=None, outline=None, width=1):
        self.d.ellipse(self._r(cx - r, cy - r, cx + r, cy + r), fill=rgba(fill) if fill else None,
                       outline=rgba(outline) if outline else None, width=max(1, int(width * self.u)))

    def bar(self, x, y, w, h=8, color=LINE):
        self.rect(x, y, x + w, y + h, h / 2, fill=color)

    def icon(self, name, x, y, size, color):
        ic = icon(name, int(size * self.u), color)
        self.img.alpha_composite(ic, (int(x * self.u), int(y * self.u)))

    def card(self, x0, y0, x1, y1, r=16, fill=CARD, shadow=True):
        if shadow:
            self.rect(x0, y0 + 2, x1, y1 + 3, r, fill=mix(SCREEN, (0, 0, 0), 0.07))
        self.rect(x0, y0, x1, y1, r, fill=fill)

    def grad(self, x0, y0, x1, y1, r, a, b):
        g = diag_gradient((max(1, int((x1 - x0) * self.u)), max(1, int((y1 - y0) * self.u))), a, b)
        g.putalpha(rounded_mask(g.size, int(r * self.u)))
        self.img.alpha_composite(g, (int(x0 * self.u), int(y0 * self.u)))

    def button(self, x0, y0, x1, y1, label, primary=True, r=12, size=15):
        if primary:
            self.rect(x0, y0, x1, y1, r, fill=self.ui.accent)
            self.text((x0 + x1) / 2, (y0 + y1) / 2, label, size, 650, self.on_accent, "mm")
        else:
            self.rect(x0, y0, x1, y1, r, fill=CARD, outline=self.ui.accent, width=1.5)
            self.text((x0 + x1) / 2, (y0 + y1) / 2, label, size, 650, ensure_contrast(self.ui.accent, CARD, 4.5), "mm")

    def toggle(self, x, y, on=True):
        self.rect(x, y, x + 44, y + 26, 13, fill=self.ui.accent if on else (215, 218, 224))
        self.circle(x + (31 if on else 13), y + 13, 10.5, fill=(255, 255, 255))

    def avatar(self, cx, cy, r, i, letter):
        hues = [self.ui.accent, self.ui.accent2, mix(self.ui.accent, (255, 255, 255), 0.35), (99, 102, 241),
                (16, 185, 129), (236, 72, 153)]
        c = hues[i % len(hues)]
        self.circle(cx, cy, r, fill=c)
        self.text(cx, cy, letter[:1].upper(), r * 0.95, 700, ensure_contrast((255, 255, 255), c, 3), "mm")


def _items(items, n, defaults):
    out = [str(x) for x in (items or []) if str(x).strip()]
    return (out + [d for d in defaults if d not in out])[:n]


def status_bar(c: Canvas, color=INK):
    c.text(30, 22, "9:41", 15, 650, color, "lm")
    for i in range(4):
        c.rect(300 + i * 6, 26 - i * 3, 304 + i * 6, 28, 1, fill=color)
    c.rect(330, 16, 356, 28, 3.5, outline=color, width=1.2)
    c.rect(332.5, 18.5, 350, 25.5, 2, fill=color)


# ---- phone screens (390 x 844 units) -------------------------------------------
def scr_list(c, title, items):
    c.text(20, 70, title or "Inbox", 32, 800, INK, family=c.ui.heading, max_w=350)
    c.rect(20, 120, 370, 160, 12, fill=(235, 236, 240)); c.icon("search", 32, 130, 20, MUTED)
    c.text(62, 140, "Search", 16, 450, MUTED, "lm")
    rows = _items(items, 6, ["Design review", "Weekly sync", "Brand refresh", "Launch notes", "Roadmap", "Feedback"])
    for i, label in enumerate(rows):
        y = 190 + i * 92
        c.avatar(48, y + 34, 24, i, label)
        c.text(86, y + 22, label, 17, 650, INK, max_w=220)
        c.bar(86, y + 44, 190 - (i % 3) * 30, 9, LINE)
        c.text(370, y + 22, f"{9 + i}:{(i * 13) % 60:02d}", 13, 500, MUTED, "ra")
        c.d.line(c._r(86, y + 80, 370, y + 80), fill=rgba(LINE), width=max(1, int(c.u)))


def scr_cards(c, title, items):
    c.text(20, 70, title or "Discover", 32, 800, INK, family=c.ui.heading, max_w=350)
    labels = _items(items, 4, ["Typography", "Colour", "Layout", "Motion"])
    icons = ["type", "palette", "grid", "play"]
    for i, label in enumerate(labels):
        x = 20 + (i % 2) * 180
        y = 130 + (i // 2) * 250
        c.card(x, y, x + 170, y + 230, 18)
        a, b = (c.ui.accent, c.ui.accent2) if i % 2 == 0 else (c.ui.accent2, mix(c.ui.accent, (255, 255, 255), 0.3))
        c.grad(x + 10, y + 10, x + 160, y + 140, 12, a, b)
        c.icon(icons[i % 4], x + 63, y + 53, 44, (255, 255, 255))
        c.text(x + 14, y + 160, label, 16, 700, INK, max_w=145)
        c.bar(x + 14, y + 190, 100, 8)
    c.button(20, 650, 370, 704, "Explore all", True, 14, 16)


def scr_form(c, title, items, bad=False):
    c.text(20, 70, title or "Create account", 30, 800, INK, family=c.ui.heading, max_w=350)
    c.bar(20, 118, 260, 10)
    fields = _items(items, 4, ["Full name", "Email", "Password", "Company"])
    values = ["Maya Rao", "maya@studio.design", "••••••••••", ""]
    for i, label in enumerate(fields):
        y = 160 + i * 104
        if bad:
            c.rect(20, y + 20, 370, y + 74, 8, fill=(240, 240, 243))
            c.text(36, y + 47, label, 16, 400, (170, 172, 180), "lm")
        else:
            c.text(20, y, label, 14, 650, INK)
            focus = i == 1
            c.rect(20, y + 22, 370, y + 76, 12, fill=CARD, outline=c.ui.accent if focus else LINE, width=2 if focus else 1.2)
            c.text(36, y + 49, values[i % 4] or "", 16, 450, INK, "lm")
    c.button(20, 610, 370, 666, "Continue", True, 14, 17)
    c.text(195, 700, "Already have an account? Log in", 13, 500, MUTED, "ma")


def scr_table(c, title, items):
    """Cramped desktop-style table squeezed onto a phone (the 'before')."""
    c.text(20, 70, title or "Orders", 28, 800, INK, family=c.ui.heading)
    cols = ["ID", "Date", "Customer", "Status", "Amount", "Pay"]
    for j, col in enumerate(cols):
        c.text(16 + j * 66, 130, col, 10, 700, MUTED)
    for i in range(10):
        y = 150 + i * 46
        c.d.line(c._r(12, y, 400, y), fill=rgba(LINE), width=1)
        for j in range(6):
            c.bar(16 + j * 66, y + 18, 50 - (i * j) % 18, 7, (205, 208, 215))
    c.rect(380, 160, 386, 380, 3, fill=(200, 200, 208))


def scr_table_cards(c, title, items):
    c.text(20, 70, title or "Orders", 30, 800, INK, family=c.ui.heading)
    names = _items(items, 4, ["Order #1042", "Order #1043", "Order #1044", "Order #1045"])
    chips = [("Paid", GOOD), ("Pending", (202, 138, 4)), ("Paid", GOOD), ("Refunded", BAD)]
    for i, name in enumerate(names):
        y = 120 + i * 150
        c.card(20, y, 370, y + 134, 16)
        c.text(38, y + 30, name, 17, 700, INK, max_w=200)
        label, col = chips[i]
        c.rect(268, y + 16, 352, y + 44, 14, fill=mix(col, (255, 255, 255), 0.85))
        c.text(310, y + 30, label, 12, 700, col, "mm")
        c.text(38, y + 70, "Customer", 12, 500, MUTED); c.bar(38, y + 90, 120, 9, (210, 212, 220))
        c.text(220, y + 70, "Amount", 12, 500, MUTED); c.bar(220, y + 90, 80, 9, (210, 212, 220))


def scr_dashboard(c, title, items):
    c.text(20, 66, title or "Good morning", 28, 800, INK, family=c.ui.heading, max_w=350)
    c.grad(20, 110, 370, 300, 22, c.ui.accent, c.ui.accent2)
    on = c.on_accent
    c.text(40, 140, "This week", 14, 600, on); c.text(40, 166, "Overview", 26, 800, on)
    pts = [(40 + i * 46, 270 - h) for i, h in enumerate([20, 45, 30, 70, 55, 90, 75])]
    c.d.line([(x * c.u, y * c.u) for x, y in pts], fill=rgba(on), width=max(2, int(3.5 * c.u)), joint="curve")
    for x, y in pts[-1:]:
        c.circle(x, y, 7, fill=on)
    labels = _items(items, 4, ["Tasks", "Messages", "Projects", "Reviews"])
    ics = ["check", "chat", "layers", "star"]
    for i in range(2):
        x = 20 + i * 180
        c.card(x, 320, x + 170, 440, 18)
        c.rect(x + 16, 336, x + 56, 376, 12, fill=mix(c.ui.accent, (255, 255, 255), 0.85))
        c.icon(ics[i], x + 24, 344, 24, c.ui.accent)
        c.text(x + 16, 400, labels[i], 15, 650, INK, max_w=140)
    for i in range(3):
        y = 470 + i * 78
        c.card(20, y, 370, y + 64, 14)
        c.icon(ics[(i + 2) % 4], 36, y + 20, 24, c.ui.accent2)
        c.text(76, y + 32, labels[(i + 2) % 4], 15, 600, INK, "lm", max_w=200)
        c.bar(290, y + 28, 60, 8)


def scr_chat(c, title, items):
    c.rect(0, 44, 390, 110, 0, fill=CARD)
    c.avatar(48, 78, 22, 1, title or "Alex")
    c.text(82, 78, title or "Alex", 18, 700, INK, "lm", max_w=250)
    msgs = _items(items, 5, ["Can we test this today?", "Yes — sending the link", "Love the new layout",
                             "The spacing feels calmer", "Ship it"])
    y = 140
    for i, m in enumerate(msgs):
        mine = i % 2 == 1
        font = load_font(c.ui.font, 500, 16 * c.u)
        w = min(260, font.getlength(m) / c.u + 36)
        x0 = 370 - w if mine else 20
        c.rect(x0, y, x0 + w, y + 50, 20, fill=c.ui.accent if mine else CARD)
        c.text(x0 + 18, y + 25, m, 16, 500, c.on_accent if mine else INK, "lm", max_w=w - 30)
        y += 70
    c.rect(20, 760, 370, 808, 24, fill=CARD, outline=LINE)
    c.text(40, 784, "Message", 15, 450, MUTED, "lm")
    c.circle(345, 784, 18, fill=c.ui.accent); c.icon("arrow", 335, 774, 20, c.on_accent)


def scr_empty(c, title, items):
    c.text(20, 70, title or "Projects", 30, 800, INK, family=c.ui.heading, max_w=350)
    c.circle(195, 330, 110, fill=mix(c.ui.accent, (255, 255, 255), 0.88))
    c.circle(195, 330, 70, fill=mix(c.ui.accent, (255, 255, 255), 0.7))
    c.icon((items or ["layers"])[0] if (items and items[0] in _ICON_NAMES) else "layers", 160, 295, 70, c.ui.accent)
    c.text(195, 480, "Nothing here yet", 22, 750, INK, "ma", family=c.ui.heading)
    c.text(195, 518, "Create your first project to get started", 14, 450, MUTED, "ma")
    c.button(95, 570, 295, 624, "New project", True, 14, 16)


def scr_settings(c, title, items):
    c.text(20, 70, title or "Settings", 32, 800, INK, family=c.ui.heading, max_w=350)
    labels = _items(items, 6, ["Notifications", "Dark mode", "Reduce motion", "Larger text", "Privacy", "Help"])
    ics = ["bell", "moon", "play", "type", "lock", "chat"]
    c.card(20, 120, 370, 120 + 66 * 4, 16)
    for i in range(4):
        y = 120 + i * 66
        c.rect(36, y + 16, 70, y + 50, 9, fill=[c.ui.accent, c.ui.accent2, (99, 102, 241), (16, 185, 129)][i])
        c.icon(ics[i], 42, y + 22, 22, (255, 255, 255))
        c.text(86, y + 33, labels[i], 16, 550, INK, "lm", max_w=190)
        c.toggle(306, y + 20, on=i % 2 == 0)
        if i < 3:
            c.d.line(c._r(86, y + 66, 370, y + 66), fill=rgba(LINE), width=1)
    c.card(20, 420, 370, 420 + 66 * 2, 16)
    for i in range(2):
        y = 420 + i * 66
        c.text(36, y + 33, labels[4 + i], 16, 550, INK, "lm")
        c.text(350, y + 33, "›", 22, 500, MUTED, "rm")


def scr_search(c, title, items):
    c.rect(20, 60, 370, 106, 14, fill=CARD, outline=c.ui.accent, width=2)
    c.icon("search", 34, 71, 24, c.ui.accent)
    c.text(68, 83, title or "running shoes", 16, 550, INK, "lm", max_w=280)
    chips = _items(items, 4, ["Recent", "Popular", "Under ₹2k", "New"])
    x = 20
    for i, ch in enumerate(chips):
        w = load_font(c.ui.font, 600, 14 * c.u).getlength(ch) / c.u + 30
        c.rect(x, 124, x + w, 158, 17, fill=c.ui.accent if i == 0 else CARD, outline=None if i == 0 else LINE)
        c.text(x + w / 2, 141, ch, 14, 600, c.on_accent if i == 0 else INK, "mm")
        x += w + 8
    for i in range(4):
        y = 180 + i * 110
        c.card(20, y, 370, y + 96, 16)
        c.grad(32, y + 12, 104, y + 84, 12, mix(c.ui.accent, (255, 255, 255), 0.5), mix(c.ui.accent2, (255, 255, 255), 0.4))
        c.bar(120, y + 26, 170, 11, (200, 202, 210)); c.bar(120, y + 50, 110, 9)
        c.icon("star", 310, y + 62, 14, (234, 160, 30)); c.text(354, y + 69, "4.8", 13, 650, MUTED, "ra")


def scr_onboarding(c, title, items):
    c.grad(-60, 90, 450, 520, 260, c.ui.accent, c.ui.accent2)
    c.icon((items or ["sparkle"])[0] if items and items[0] in _ICON_NAMES else "sparkle", 135, 230, 120, (255, 255, 255))
    c.text(195, 580, title or "Design faster", 28, 800, INK, "ma", family=c.ui.heading, max_w=340)
    c.text(195, 625, "Everything you need, nothing you don't", 14, 450, MUTED, "ma")
    for i in range(3):
        c.rect(167 + i * 20, 676, 179 + i * 20 + (12 if i == 0 else 0), 684, 4, fill=c.ui.accent if i == 0 else LINE)
    c.button(20, 720, 370, 776, "Get started", True, 16, 17)


def scr_pricing(c, title, items):
    c.text(195, 70, title or "Choose a plan", 28, 800, INK, "ma", family=c.ui.heading, max_w=350)
    plans = _items(items, 2, ["Starter", "Pro"])
    for i, plan in enumerate(plans):
        y = 140 + i * 300
        hi = i == 1
        if hi:
            c.grad(20, y, 370, y + 270, 22, c.ui.accent, c.ui.accent2)
        else:
            c.card(20, y, 370, y + 270, 22)
        col = c.on_accent if hi else INK
        c.text(44, y + 40, plan, 20, 750, col, max_w=200)
        c.text(44, y + 80, "₹499" if not hi else "₹999", 34, 800, col, family=c.ui.heading)
        for k in range(3):
            c.icon("check", 44, y + 140 + k * 30, 18, col)
            c.bar(72, y + 146 + k * 30, 150 + k * 20, 8, mix(col, (255, 255, 255) if not hi else c.ui.accent, 0.6))
        if hi:
            c.rect(250, y + 26, 350, y + 54, 14, fill=(255, 255, 255))
            c.text(300, y + 40, "Popular", 12, 750, c.ui.accent, "mm")


def scr_nav(c, title, items):
    scr_cards(c, title, items)
    c.rect(0, 744, 390, 844, 0, fill=CARD)
    c.d.line(c._r(0, 744, 390, 744), fill=rgba(LINE), width=1)
    for i, name in enumerate(["home", "search", "heart", "user"]):
        x = 40 + i * 96
        c.icon(name, x, 768, 28, c.ui.accent if i == 0 else MUTED)


def scr_cluttered(c, title, items):
    """A noisy screen: competing colours, borders and type sizes (the 'before')."""
    cols = [(239, 68, 68), (59, 130, 246), (234, 179, 8), (16, 185, 129), (168, 85, 247)]
    c.text(14, 64, (title or "Welcome!!").upper(), 30, 900, cols[0], max_w=360)
    for i in range(7):
        y = 120 + i * 88
        x = 14 + (i * 23) % 50
        c.rect(x, y, x + 300 - (i * 37) % 90, y + 70, 4, fill=mix(cols[i % 5], (255, 255, 255), 0.75),
               outline=cols[(i + 2) % 5], width=3)
        c.text(x + 12, y + 22, ["SALE", "New!", "Click here", "Hot", "Offer", "Look", "Now"][i], 14 + (i % 3) * 6,
               800, cols[(i + 1) % 5])


def scr_product(c, title, items):
    c.grad(0, 0, 390, 420, 0, mix(c.ui.accent, (255, 255, 255), 0.55), mix(c.ui.accent2, (255, 255, 255), 0.45))
    c.icon("cube", 125, 120, 140, (255, 255, 255))
    c.rect(0, 390, 390, 844, 30, fill=SCREEN)
    c.text(24, 430, title or "Lumen Lamp", 26, 800, INK, family=c.ui.heading, max_w=340)
    for k in range(5):
        c.icon("star", 24 + k * 22, 466, 18, (234, 160, 30))
    c.text(24, 520, "₹2,499", 28, 800, INK, family=c.ui.heading)
    for k, label in enumerate(_items(items, 3, ["Warm", "Cool", "Daylight"])):
        x = 24 + k * 116
        c.rect(x, 580, x + 106, 620, 12, fill=c.ui.accent if k == 0 else CARD, outline=None if k == 0 else LINE)
        c.text(x + 53, 600, label, 14, 650, c.on_accent if k == 0 else INK, "mm", max_w=96)
    c.button(24, 700, 366, 756, "Add to cart", True, 16, 17)


SCREENS = {
    "list": scr_list, "cards": scr_cards, "form": scr_form, "table": scr_table, "table_cards": scr_table_cards,
    "dashboard": scr_dashboard, "chat": scr_chat, "empty_state": scr_empty, "settings": scr_settings,
    "search": scr_search, "onboarding": scr_onboarding, "pricing": scr_pricing, "nav_bottom": scr_nav,
    "cluttered": scr_cluttered, "product": scr_product,
    "placeholder_form": lambda c, t, i: scr_form(c, t, i, bad=True),
}
_ICON_NAMES: set = set()


def phone(screen: str, ui: UI, height: int, title: str = "", items=None, dark_frame=True) -> Image.Image:
    """A phone with the given screen. Returns RGBA, `height` px tall."""
    from .icons import ICONS
    _ICON_NAMES.update(ICONS)
    w = int(height * 0.49)
    h = int(height)
    bezel = int(w * 0.035)
    r_out = int(w * 0.16)
    obj = layer(w, h)
    d = ImageDraw.Draw(obj)
    frame = (28, 29, 34) if dark_frame else (230, 230, 235)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=r_out, fill=rgba(frame))
    d.rounded_rectangle((2, 2, w - 3, h - 3), radius=r_out - 2, outline=rgba(mix(frame, (255, 255, 255), 0.25)),
                        width=max(2, w // 160))
    sw, sh = w - 2 * bezel, h - 2 * bezel
    c = Canvas(sw, sh, 390, ui)
    status_bar(c)
    SCREENS.get(screen, scr_list)(c, title, items or [])
    scr = c.img
    scr.putalpha(rounded_mask(scr.size, r_out - bezel))
    obj.alpha_composite(scr, (bezel, bezel))
    d.rounded_rectangle((w * 0.36, bezel + sh * 0.012, w * 0.64, bezel + sh * 0.045), radius=h, fill=rgba((10, 10, 12)))
    return gloss(obj, 0.12)


# ---- browser layouts (1280 x 800 units) -------------------------------------------
def web_hero(c, title, items):
    c.circle(60, 50, 14, fill=c.ui.accent); c.bar(84, 44, 80, 12, (200, 202, 210))
    for i, lab in enumerate(_items(items, 3, ["Product", "Pricing", "Blog"])):
        c.text(760 + i * 110, 50, lab, 16, 550, MUTED, "lm", max_w=100)
    c.button(1100, 30, 1230, 70, "Sign up", True, 20, 15)
    c.text(60, 200, title or "Design that ships", 64, 850, INK, family=c.ui.heading, max_w=640)
    c.bar(60, 330, 520, 16, (205, 207, 214)); c.bar(60, 360, 420, 16, (215, 217, 223))
    c.button(60, 420, 250, 480, "Get started", True, 30, 18); c.button(270, 420, 430, 480, "Live demo", False, 30, 18)
    c.grad(760, 140, 1230, 640, 32, c.ui.accent, c.ui.accent2)
    c.card(820, 230, 1170, 560, 24)
    for i in range(3):
        c.rect(850, 270 + i * 90, 900, 320 + i * 90, 14, fill=mix(c.ui.accent, (255, 255, 255), 0.8))
        c.bar(920, 282 + i * 90, 200, 12, (190, 192, 200)); c.bar(920, 304 + i * 90, 130, 10)


def web_bento(c, title, items):
    c.text(60, 60, title or "Everything in one place", 40, 850, INK, family=c.ui.heading, max_w=1100)
    labels = _items(items, 5, ["Fast", "Secure", "Collaborative", "Accessible", "Beautiful"])
    ics = ["bolt", "shield", "user", "accessibility", "sparkle"]
    tiles = [(60, 140, 560, 470), (580, 140, 900, 300), (920, 140, 1220, 300), (580, 320, 1220, 470),
             (60, 490, 1220, 740)]
    for i, (x0, y0, x1, y1) in enumerate(tiles):
        if i in (0, 4):
            c.grad(x0, y0, x1, y1, 26, c.ui.accent if i == 0 else c.ui.accent2, c.ui.accent2 if i == 0 else c.ui.accent)
            col = c.on_accent
        else:
            c.card(x0, y0, x1, y1, 26)
            col = INK
        c.icon(ics[i], x0 + 30, y0 + 30, 44 if i else 70, col if i in (0, 4) else c.ui.accent)
        c.text(x0 + 30, y1 - 50, labels[i], 26 if i in (0, 4) else 20, 800, col, family=c.ui.heading, max_w=x1 - x0 - 60)


def web_editorial(c, title, items):
    c.d.line(c._r(60, 70, 1220, 70), fill=rgba(INK), width=max(1, int(2 * c.u)))
    c.text(640, 46, "THE  REVIEW", 22, 400, INK, "mm", family="dm-serif-display")
    c.text(60, 110, title or "The return of the grid", 66, 400, INK, family="dm-serif-display", max_w=760)
    c.grad(60, 220, 760, 620, 4, mix(c.ui.accent, (0, 0, 0), 0.1), c.ui.accent2)
    c.icon("image", 360, 370, 100, (255, 255, 255))
    for col in range(2):
        x = 800 + col * 215
        for i in range(14):
            c.bar(x, 230 + i * 28, 190 - (i * 17 + col * 23) % 50, 9, (200, 202, 210))
    c.text(60, 660, "Words — Studio Notes", 16, 600, MUTED)


def web_asymmetric(c, title, items):
    c.text(60, 80, title or "Break the grid", 72, 900, INK, family=c.ui.heading, max_w=700)
    c.grad(700, 60, 1240, 420, 0, c.ui.accent, c.ui.accent2)
    c.card(820, 330, 1180, 620, 0)
    c.bar(850, 370, 220, 14, (190, 192, 200)); c.bar(850, 400, 160, 10)
    c.rect(60, 300, 420, 740, 0, fill=INK)
    c.text(90, 340, "01", 90, 900, c.ui.accent2, family=c.ui.heading)
    for i in range(4):
        c.bar(460, 480 + i * 34, 300 - i * 40, 12, (200, 202, 210))


def web_dashboard(c, title, items):
    c.rect(0, 0, 230, 800, 0, fill=INK)
    for i, name in enumerate(["home", "chart", "layers", "user", "gear"]):
        c.rect(24, 110 + i * 64, 206, 160 + i * 64, 12, fill=c.ui.accent if i == 1 else None)
        c.icon(name, 40, 122 + i * 64, 26, (255, 255, 255) if i == 1 else (160, 164, 176))
    c.text(270, 60, title or "Analytics", 36, 850, INK, family=c.ui.heading, max_w=600)
    labels = _items(items, 3, ["Visitors", "Sign-ups", "Retention"])
    for i, lab in enumerate(labels):
        x = 270 + i * 320
        c.card(x, 120, x + 300, 250, 20)
        c.text(x + 24, 150, lab, 16, 600, MUTED, max_w=250)
        c.bar(x + 24, 190, 120, 22, mix(c.ui.accent, (255, 255, 255), 0.4 + i * 0.15))
    c.card(270, 280, 1230, 740, 20)
    pts = [(310 + i * 85, 680 - (math.sin(i * 0.9) * 80 + i * 22)) for i in range(11)]
    poly = [(x * c.u, y * c.u) for x, y in pts]
    fill = Image.new("RGBA", c.img.size, (0, 0, 0, 0))
    ImageDraw.Draw(fill).polygon(poly + [(pts[-1][0] * c.u, 700 * c.u), (pts[0][0] * c.u, 700 * c.u)],
                                 fill=rgba(c.ui.accent, 40))
    c.img.alpha_composite(fill)
    c.d.line(poly, fill=rgba(c.ui.accent), width=max(2, int(4 * c.u)), joint="curve")


def web_grid(c, title, items):
    c.text(60, 60, title or "Collection", 40, 850, INK, family=c.ui.heading, max_w=900)
    for i in range(8):
        x = 60 + (i % 4) * 295
        y = 140 + (i // 4) * 320
        c.card(x, y, x + 275, y + 300, 20)
        a = c.ui.accent if i % 2 else c.ui.accent2
        c.grad(x + 12, y + 12, x + 263, y + 200, 14, mix(a, (255, 255, 255), 0.35), a)
        c.bar(x + 16, y + 222, 160, 12, (190, 192, 200)); c.bar(x + 16, y + 250, 90, 10)


WEB = {"hero": web_hero, "bento": web_bento, "editorial": web_editorial, "asymmetric": web_asymmetric,
       "dashboard": web_dashboard, "grid": web_grid}


def browser(layout: str, ui: UI, width: int, title: str = "", items=None) -> Image.Image:
    w = int(width)
    h = int(width * 0.68)
    bar_h = int(w * 0.045)
    r = int(w * 0.022)
    obj = layer(w, h)
    d = ImageDraw.Draw(obj)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=r, fill=rgba((236, 237, 241)))
    for i, col in enumerate([(255, 95, 87), (254, 188, 46), (40, 200, 64)]):
        cx = bar_h * 0.6 + i * bar_h * 0.55
        d.ellipse((cx - bar_h * 0.16, bar_h / 2 - bar_h * 0.16, cx + bar_h * 0.16, bar_h / 2 + bar_h * 0.16),
                  fill=rgba(col))
    d.rounded_rectangle((w * 0.3, bar_h * 0.22, w * 0.7, bar_h * 0.78), radius=bar_h, fill=rgba((255, 255, 255)))
    c = Canvas(w, h - bar_h, 1280, ui, bg=(250, 250, 252))
    WEB.get(layout, web_hero)(c, title, items or [])
    content = c.img
    mask = Image.new("L", content.size, 255)
    ImageDraw.Draw(mask).rounded_rectangle((0, -r, content.width - 1, content.height - 1), radius=r, fill=255)
    obj.paste(content, (0, bar_h), mask)
    return obj
