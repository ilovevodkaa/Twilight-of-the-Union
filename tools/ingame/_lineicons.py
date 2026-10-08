"""Broadcast line icons: one hand-drawn set for the HUD (toolbar, army/navy/air, map modes, minimap, music player).

Every icon is drawn on a 24 x 24 grid with one stroke weight (2 grid units, round joints), like a modern line icon
set, in paper white P with a 1 px K drop. It is rendered 8x supersampled and downscaled, so the strokes stay crisp
and anti-aliased at 16..30 px. These replace the first pass's 2 px pixel silhouettes (they read as blobs) and are
not recoloured vanilla art: each shape is drawn here.

    icon(name, size, colour=P, stroke=2.0, k_drop=True) -> RGBA (size x size)
    ICONS: name -> draw function
"""
import math

import numpy as np
from PIL import Image, ImageDraw

P = (246, 242, 234)
D = (172, 180, 196)
SS = 8


class Pen:
    """Strokes and fills on a 24-unit grid, drawn into an L mask at size * SS."""

    def __init__(self, size, stroke):
        self.s = size * SS / 24.0
        self.w = max(1.0, stroke * self.s)
        self.img = Image.new("L", (size * SS, size * SS), 0)
        self.d = ImageDraw.Draw(self.img)

    def p(self, x, y):
        return (x * self.s, y * self.s)

    def dot(self, x, y, r=None):
        r = (self.w / 2) if r is None else r * self.s
        cx, cy = self.p(x, y)
        self.d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)

    def line(self, *pts, closed=False):
        pts = [self.p(*q) for q in pts]
        if closed:
            pts = pts + [pts[0]]
        self.d.line(pts, fill=255, width=round(self.w))
        r = self.w / 2
        for cx, cy in pts:
            self.d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)

    def poly(self, *pts):
        self.d.polygon([self.p(*q) for q in pts], fill=255)

    def circle(self, x, y, r, fill=False):
        cx, cy = self.p(x, y)
        rr = r * self.s
        if fill:
            self.d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), fill=255)
        else:
            self.d.ellipse((cx - rr - self.w / 2, cy - rr - self.w / 2, cx + rr + self.w / 2, cy + rr + self.w / 2),
                           fill=255)
            inner = rr - self.w / 2
            if inner > 0:
                self.d.ellipse((cx - inner, cy - inner, cx + inner, cy + inner), fill=0)

    def arc(self, x, y, r, a0, a1, steps=40):
        """Arc of a circle (degrees, 0 = +x, clockwise on screen because y points down)."""
        pts = [(x + r * math.cos(math.radians(a0 + (a1 - a0) * i / steps)),
                y + r * math.sin(math.radians(a0 + (a1 - a0) * i / steps))) for i in range(steps + 1)]
        self.line(*pts)

    def curve(self, fn, t0=0.0, t1=1.0, steps=48):
        self.line(*[fn(t0 + (t1 - t0) * i / steps) for i in range(steps + 1)])

    def clear(self, *pts):
        self.d.polygon([self.p(*q) for q in pts], fill=0)

    def clear_circle(self, x, y, r):
        cx, cy = self.p(x, y)
        rr = r * self.s
        self.d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), fill=0)


# --- icons -------------------------------------------------------------------------------------------------------
def eye(p):
    p.curve(lambda t: (2 + 20 * t, 12 - 7.5 * math.sin(math.pi * t)))
    p.curve(lambda t: (2 + 20 * t, 12 + 7.5 * math.sin(math.pi * t)))
    p.circle(12, 12, 3.2)
    p.dot(12, 12, 1.2)


def gavel(p):
    # head: a block rotated 45 degrees, handle to the lower left, sounding block underneath
    c, s = math.cos(math.radians(45)), math.sin(math.radians(45))
    def rot(x, y, cx=14.5, cy=8.5):
        return (cx + x * c - y * s, cy + x * s + y * c)
    p.line(rot(-5, -2.6), rot(5, -2.6), rot(5, 2.6), rot(-5, 2.6), closed=True)
    p.line(rot(-6.5, -3.4), rot(-6.5, 3.4))
    p.line(rot(6.5, -3.4), rot(6.5, 3.4))
    p.line((12.0, 11.0), (4.0, 19.0))
    p.line((11.5, 21.5), (21.0, 21.5))


def flask(p):
    p.line((8.5, 2.5), (15.5, 2.5))
    p.line((9.5, 2.5), (9.5, 9.0), (4.0, 19.0), (5.5, 21.0), (18.5, 21.0), (20.0, 19.0), (14.5, 9.0), (14.5, 2.5))
    p.line((6.6, 15.0), (17.4, 15.0))
    p.dot(10.5, 18.0, 1.1)
    p.dot(14.0, 17.6, 0.8)


def treaty(p):
    p.line((5, 2.5), (15, 2.5), (19, 6.5), (19, 21.5), (5, 21.5), closed=True)
    p.line((8, 8), (14, 8))
    p.line((8, 11.5), (16, 11.5))
    p.line((8, 15), (12, 15))
    p.circle(15.5, 17.5, 2.4, fill=True)


def exchange(p):
    p.line((3.5, 8), (20, 8))
    p.line((15.5, 3.5), (20, 8), (15.5, 12.5))
    p.line((20.5, 16), (4, 16))
    p.line((8.5, 11.5), (4, 16), (8.5, 20.5))


def scales(p):
    p.line((12, 3.5), (12, 20.5))
    p.line((7.5, 20.5), (16.5, 20.5))
    p.line((3.5, 6.5), (20.5, 6.5))
    for x in (5, 19):
        p.line((x, 6.5), (x - 3.2, 13.5))
        p.line((x, 6.5), (x + 3.2, 13.5))
        p.curve(lambda t, x=x: (x - 3.6 + 7.2 * t, 13.5 + 3.2 * math.sin(math.pi * t)))
        p.line((x - 3.6, 13.5), (x + 3.6, 13.5))


def crane(p):
    p.line((7, 21.5), (7, 3.5))
    p.line((2.5, 3.5), (21.5, 3.5))
    p.line((7, 9), (12.5, 3.5))
    p.line((18, 3.5), (18, 10.5))
    p.arc(16.6, 12.2, 1.9, -80, 160)
    p.line((3, 21.5), (11, 21.5))
    p.poly((2.5, 3.5), (5.0, 3.5), (5.0, 7.0), (2.5, 7.0))


def factory(p):
    p.line((2.5, 21), (2.5, 11), (8, 14), (8, 11), (13.5, 14), (13.5, 11), (17, 13), (17, 3), (21.5, 3), (21.5, 21),
           closed=True)
    for x in (6, 11, 16):
        p.poly((x - 1.2, 16.2), (x + 1.2, 16.2), (x + 1.2, 18.6), (x - 1.2, 18.6))


def gear(p):
    p.circle(12, 12, 5.2)
    p.circle(12, 12, 1.8)
    for k in range(8):
        a = math.radians(k * 45)
        p.line((12 + 6.6 * math.cos(a), 12 + 6.6 * math.sin(a)), (12 + 9.4 * math.cos(a), 12 + 9.4 * math.sin(a)))


def deploy(p):
    p.line((12, 2.5), (12, 14))
    p.line((7, 9), (12, 14), (17, 9))
    p.line((3.5, 15), (3.5, 20.5), (20.5, 20.5), (20.5, 15))


def truck(p):
    p.line((2, 6), (14, 6), (14, 17), (2, 17), closed=True)
    p.line((14, 10), (18.5, 10), (22, 13.5), (22, 17), (14, 17))
    p.clear_circle(6.5, 18.5, 3.0)
    p.clear_circle(17.5, 18.5, 3.0)
    p.circle(6.5, 18.5, 1.9)
    p.circle(17.5, 18.5, 1.9)


def officer_cap(p):
    """Staff office: a general's shoulder board (pointed top, button) with two stars."""
    p.line((7, 21.5), (7, 6), (12, 2.5), (17, 6), (17, 21.5), closed=True)
    p.dot(12, 6.2, 1.2)
    star(p, 12, 11.5, 3.0, fill=True)
    star(p, 12, 17.5, 3.0, fill=True)


def helmet(p):
    p.arc(12, 15, 9, 180, 360)
    p.line((1.5, 15.5), (22.5, 15.5))
    p.line((6, 15.5), (6, 18.5))
    p.line((18, 15.5), (18, 18.5))
    star(p, 12, 10.5, 2.6, fill=True)


def anchor(p):
    p.circle(12, 4.6, 2.1)
    p.line((12, 6.8), (12, 21))
    p.line((7.5, 10), (16.5, 10))
    p.arc(12, 13.5, 7.5, 0, 180)
    p.line((2.5, 13), (4.5, 13.5), (5.2, 11.5))
    p.line((21.5, 13), (19.5, 13.5), (18.8, 11.5))


def plane(p):
    p.line((12, 2.5), (12, 21))
    p.line((12, 9), (2.5, 13.5), (2.5, 15), (12, 13))
    p.line((12, 9), (21.5, 13.5), (21.5, 15), (12, 13))
    p.line((8.5, 21.5), (12, 19.5), (15.5, 21.5))


def soldier(p):
    p.circle(12, 4.5, 2.3)
    p.line((12, 7.5), (12, 14))
    p.line((12, 14), (8.5, 21.5))
    p.line((12, 14), (15.5, 21.5))
    p.line((12, 9.5), (17.5, 11.5))
    p.line((7, 13.5), (21.5, 8))            # rifle


def question(p):
    p.arc(12, 8.5, 4.8, 180, 405)
    p.line((15.4, 11.9), (12, 14.6), (12, 16))
    p.dot(12, 20.2, 1.4)


def exclamation(p):
    p.line((12, 3), (12, 14.5))
    p.dot(12, 20, 1.4)


def flag(p):
    p.line((5, 2.5), (5, 21.5))
    p.line((5, 3.5), (19.5, 3.5), (16, 8), (19.5, 12.5), (5, 12.5))


def pennant(p):
    p.line((6, 2.5), (6, 21.5))
    p.line((6, 3.5), (20, 8), (6, 12.5))


def bars(p):
    p.line((3, 21), (21, 21))
    for x, top in ((6, 14), (10.5, 9), (15, 12), (19.5, 5)):
        p.line((x, 18.5), (x, top))


def flame(p):
    # a hand-shaped flame: outer tongue and inner tongue
    p.line((12, 2.5), (15.5, 7.5), (18.5, 12), (18.5, 16.5), (15.5, 20.5), (12, 21.5), (8.5, 20.5), (5.5, 16.5),
           (6, 12.5), (8.5, 9.5), (9.5, 12.5), (12, 2.5))
    p.line((12, 14), (13.8, 16.6), (12, 19.2), (10.2, 16.6), closed=True)


def canister(p):
    p.line((5, 21), (5, 8), (9, 3.5), (19, 3.5), (19, 21), closed=True)
    p.line((13, 3.5), (13, 1.5), (16, 1.5), (16, 3.5))
    p.line((8, 10), (16, 18))
    p.line((16, 10), (8, 18))


def locomotive(p):
    p.line((2, 8), (14, 8), (14, 17), (2, 17), closed=True)
    p.line((14, 5), (21.5, 5), (21.5, 17), (14, 17))
    p.line((4.5, 8), (4.5, 3.5), (8, 3.5), (8, 8))
    for x in (5.5, 12, 18.5):
        p.clear_circle(x, 19.5, 2.7)
        p.circle(x, 19.5, 1.6)


def star(p, x=12, y=12, r=9.5, fill=False):
    pts = []
    for k in range(10):
        a = math.radians(-90 + k * 36)
        rr = r if k % 2 == 0 else r * 0.42
        pts.append((x + rr * math.cos(a), y + rr * math.sin(a)))
    if fill:
        p.poly(*pts)
    else:
        p.line(*pts, closed=True)


def star_icon(p):
    star(p)


def people(p):
    p.circle(8.5, 7, 3)
    p.arc(8.5, 19.5, 6, 180, 360)
    p.circle(16.5, 8, 2.6)
    p.arc(17.5, 19.5, 5, 205, 340)


def person(p):
    p.circle(12, 6.5, 3.5)
    p.arc(12, 21, 8, 180, 360)


def globe(p):
    p.circle(12, 12, 9)
    p.line((3, 12), (21, 12))
    p.curve(lambda t: (12 + 4.2 * math.sin(math.pi * 2 * t), 12 - 9 * math.cos(math.pi * 2 * t)), 0, 1)
    p.line((5, 7.5), (19, 7.5))
    p.line((5, 16.5), (19, 16.5))


def trees(p):
    for x, h in ((8, 1.0), (16.5, 0.8)):
        top = 21 - 18 * h
        p.line((x, top), (x - 5 * h, 21 - 6 * h), (x + 5 * h, 21 - 6 * h), closed=True)
        p.line((x, 21 - 6 * h), (x, 21.5))


def crosshair(p):
    p.circle(12, 12, 7)
    for (a, b) in (((12, 1.5), (12, 6.5)), ((12, 17.5), (12, 22.5)), ((1.5, 12), (6.5, 12)), ((17.5, 12), (22.5, 12))):
        p.line(a, b)
    p.dot(12, 12, 1.5)


def magnifier(p):
    p.circle(10, 10, 6.5)
    p.line((14.8, 14.8), (21, 21))


def sun(p):
    p.circle(12, 12, 4)
    for k in range(8):
        a = math.radians(k * 45)
        p.line((12 + 7 * math.cos(a), 12 + 7 * math.sin(a)), (12 + 9.5 * math.cos(a), 12 + 9.5 * math.sin(a)))


def moon(p):
    p.circle(12, 12, 8.5, fill=True)
    p.clear_circle(16.5, 8.5, 7.5)


def menu(p):
    for y in (6, 12, 18):
        p.line((4, y), (20, y))


def plus(p):
    p.line((12, 4), (12, 20))
    p.line((4, 12), (20, 12))


def minus(p):
    p.line((4, 12), (20, 12))


def play(p):
    p.poly((7, 4), (19.5, 12), (7, 20))


def pause(p):
    p.line((8.5, 5), (8.5, 19))
    p.line((15.5, 5), (15.5, 19))


def next_track(p):
    p.poly((5, 5), (15, 12), (5, 19))
    p.line((18, 5), (18, 19))


def prev_track(p):
    p.poly((19, 5), (9, 12), (19, 19))
    p.line((6, 5), (6, 19))


def note(p):
    p.line((9, 18), (9, 4), (19, 2.5), (19, 15.5))
    p.circle(6.5, 18, 2.6, fill=True)
    p.circle(16.5, 15.5, 2.6, fill=True)


def playlist(p):
    for y, x1 in ((5, 15), (10, 15), (15, 10)):
        p.line((3, y), (x1, y))
    p.line((18, 13), (18, 21))
    p.line((14, 17), (22, 17))


def swords(p):
    p.line((4, 4), (19, 19))
    p.line((20, 4), (5, 19))
    p.line((15, 20.5), (20.5, 15))
    p.line((3.5, 15), (9, 20.5))


def shield(p):
    p.line((12, 2.5), (20, 5.5), (20, 12), (12, 21.5), (4, 12), (4, 5.5), closed=True)


def check(p):
    p.line((4, 12.5), (9.5, 18), (20, 6))


def infantry(p):
    """NATO map symbol for infantry: a frame with a saltire (staff maps, the army)."""
    p.line((2.5, 6), (21.5, 6), (21.5, 18), (2.5, 18), closed=True)
    p.line((2.5, 6), (21.5, 18))
    p.line((21.5, 6), (2.5, 18))


def dial(p, lit=0, ticks=10):
    """World tension: a ring of ticks, the first `lit` drawn long (the rest short)."""
    for k in range(ticks):
        a = math.radians(-90 + k * 360 / ticks)
        r0 = 8.6 if k < lit else 10.2
        p.line((12 + r0 * math.cos(a), 12 + r0 * math.sin(a)), (12 + 11.2 * math.cos(a), 12 + 11.2 * math.sin(a)))


def tank(p):
    """Side view of a tank: hull, track run with road wheels, turret and gun."""
    p.line((2.5, 13.5), (21.5, 13.5), (19.5, 16.5), (4.5, 16.5), closed=True)
    p.line((4, 16.5), (3, 18.5), (5, 21), (19, 21), (21, 18.5), (20, 16.5))
    for x in (7, 10.5, 14, 17.5):
        p.dot(x, 18.8, 0.9)
    p.line((7, 13.5), (8, 9.5), (15, 9.5), (16.5, 13.5))
    p.line((15.5, 11), (22.5, 10))


def columns(p):
    """Government: a portico (pediment, four columns, steps)."""
    p.line((2.5, 8), (12, 3), (21.5, 8), closed=True)
    for x in (5.5, 9.8, 14.2, 18.5):
        p.line((x, 10.5), (x, 17.5))
    p.line((3.5, 19.5), (20.5, 19.5))
    p.line((2, 22), (22, 22))


ICONS = {
    "eye": eye, "gavel": gavel, "flask": flask, "treaty": treaty, "exchange": exchange, "scales": scales,
    "crane": crane, "factory": factory, "gear": gear, "deploy": deploy, "truck": truck, "officer_cap": officer_cap,
    "helmet": helmet, "anchor": anchor, "plane": plane, "soldier": soldier, "question": question,
    "exclamation": exclamation, "flag": flag, "pennant": pennant, "bars": bars, "flame": flame, "canister": canister,
    "locomotive": locomotive, "star": star_icon, "people": people, "person": person, "globe": globe, "trees": trees,
    "crosshair": crosshair, "magnifier": magnifier, "sun": sun, "moon": moon, "menu": menu, "plus": plus,
    "minus": minus, "play": play, "pause": pause, "next": next_track, "prev": prev_track, "note": note,
    "playlist": playlist, "swords": swords, "shield": shield, "check": check, "infantry": infantry, "tank": tank, "columns": columns,
}


def mask(name, size, stroke=2.0):
    pen = Pen(size, stroke)
    ICONS[name](pen)
    return pen.img.resize((size, size), Image.LANCZOS)


def icon(name, size, colour=P, stroke=2.0, k_drop=True, alpha=1.0):
    """RGBA size x size: the icon in colour with a 1 px K drop (the drop stays inside the box)."""
    m = np.asarray(mask(name, size, stroke), np.float32) / 255.0 * alpha
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    if k_drop:
        drop = np.zeros((size, size, 4), np.uint8)
        drop[..., 3] = (m * 255 * 0.85).astype(np.uint8)
        out.alpha_composite(Image.fromarray(drop, "RGBA"), (1, 1))
    layer = np.zeros((size, size, 4), np.uint8)
    layer[..., :3] = colour
    layer[..., 3] = (m * 255).astype(np.uint8)
    out.alpha_composite(Image.fromarray(layer, "RGBA"))
    return out


def on(frame_size, name, icon_size, bg=None, bg_alpha=1.0, colour=P, stroke=2.0, inset=(0, 0, 0, 0), dx=0, dy=0,
       k_drop=True, alpha=1.0):
    """One button frame: flat bg (None = transparent) inset by (l, t, r, b), the icon centred (+dx, dy)."""
    w, h = frame_size
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if bg is not None:
        l, t, r, b = inset
        out.paste(Image.new("RGBA", (w - l - r, h - t - b), (*bg, round(255 * bg_alpha))), (l, t))
    ic = icon(name, icon_size, colour, stroke, k_drop, alpha)
    out.alpha_composite(ic, ((w - icon_size) // 2 + dx, (h - icon_size) // 2 + dy))
    return out
