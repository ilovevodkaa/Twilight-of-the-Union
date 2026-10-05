"""Builds main menu textures for Twilight of the Union.

Usage:
    python tools/build_menu_gfx.py                      # default sources
    python tools/build_menu_gfx.py --bg other.jpg --photo frame.jpg

Outputs DDS files into gfx/ and a preview PNG into tools/preview/.
Requires Pillow (pip install pillow).
"""
import argparse
import random
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "tools" / "src"
FONTS = Path("C:/Windows/Fonts")

# Palette (keep in sync with interface/frontendmainview.gui comments)
INK = (21, 17, 14)          # panel fill
LINE = (74, 64, 55)         # outer hairline
LINE_DIM = (48, 41, 35)     # inner hairline
PAPER = (230, 220, 203)     # logo text
DUST = (138, 125, 110)      # secondary text
ACCENT = (163, 67, 47)      # the one red

# Panel layout, in pixels; mirrored in frontendmainview.gui
PANEL_W, PANEL_H = 900, 420
COL_W = 320                 # button column
PHOTO_X, PHOTO_Y, PHOTO_W, PHOTO_H = 334, 14, 552, 250
TEXT_Y = 276
TEXT_SPLIT_X = 672          # divider between lore and changelog blocks
QUIT_DIVIDER_Y = 180        # hairline between Credits and Quit


def font(name, size):
    return ImageFont.truetype(str(FONTS / name), size)


def save_dds(img, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGBA").save(path, format="DDS")
    print("wrote", path.relative_to(ROOT), img.size)


def cover(img, w, h, focus_x=0.5, focus_y=0.5):
    scale = max(w / img.width, h / img.height)
    img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    left = round((img.width - w) * focus_x)
    top = round((img.height - h) * focus_y)
    return img.crop((left, top, left + w, top + h))


def radial_mask(w, h, inner=0.35, outer=1.0, cx=0.5, cy=0.5):
    """0 at the centre, 255 at the edges; elliptical."""
    small = Image.new("L", (w // 8, h // 8))
    px = small.load()
    sw, sh = small.size
    for y in range(sh):
        for x in range(sw):
            dx = (x / sw - cx) / 0.5
            dy = (y / sh - cy) / 0.5
            d = (dx * dx + dy * dy) ** 0.5
            t = min(max((d - inner) / (outer - inner), 0.0), 1.0)
            px[x, y] = round(255 * t * t)
    return small.resize((w, h), Image.BILINEAR)


def scanlines(img, period=3, strength=0.12):
    w, h = img.size
    lines = Image.new("L", (1, h), 255)
    for y in range(0, h, period):
        lines.putpixel((0, y), round(255 * (1 - strength)))
    lines = lines.resize((w, h))
    return ImageChops.multiply(img, Image.merge("RGB", (lines, lines, lines)))


def chroma_shift(img, px=2):
    r, g, b = img.split()
    r = ImageChops.offset(r, px, 0)
    b = ImageChops.offset(b, -px, 0)
    return Image.merge("RGB", (r, g, b))


def grain(img, amount=7, seed=1990):
    rnd = random.Random(seed)
    w, h = img.size
    noise = Image.new("L", (w // 2, h // 2))
    noise.putdata([128 + rnd.randint(-amount, amount) for _ in range(noise.width * noise.height)])
    noise = noise.resize((w, h), Image.NEAREST)
    noise = Image.merge("RGB", (noise, noise, noise))
    return ImageChops.add(img, noise, scale=1.0, offset=-128)


def tone(img, sat, bright, contrast, shadow, highlight, mix=0.45):
    """Desaturate, darken, then map black->shadow and white->highlight."""
    img = ImageEnhance.Color(img).enhance(sat)
    img = ImageEnhance.Brightness(img).enhance(bright)
    img = ImageEnhance.Contrast(img).enhance(contrast)
    lum = ImageOps.grayscale(img)
    tinted = ImageOps.colorize(lum, shadow, highlight)
    return Image.blend(img, tinted, mix)


def build_background(src):
    W, H = 1920, 1440
    img = cover(Image.open(src).convert("RGB"), W, H, focus_y=0.45)
    img = tone(img, sat=0.78, bright=0.56, contrast=1.15, shadow=(12, 9, 8), highlight=(226, 160, 104), mix=0.3)

    # Darken the edges and, more softly, the area behind the menu panel.
    black = Image.new("RGB", (W, H), (8, 6, 5))
    img = Image.composite(black, img, radial_mask(W, H, inner=0.30, outer=1.05).point(lambda v: v * 0.85))
    panel_shade = Image.new("L", (W, H), 0)
    ImageDraw.Draw(panel_shade).rectangle((460, 640, 1460, 1160), fill=110)
    panel_shade = panel_shade.filter(ImageFilter.GaussianBlur(140))
    img = Image.composite(black, img, panel_shade)

    # Top-left gets a little extra dark so the logo reads.
    logo_shade = Image.new("L", (W, H), 0)
    ImageDraw.Draw(logo_shade).rectangle((0, 180, 900, 520), fill=120)
    logo_shade = logo_shade.filter(ImageFilter.GaussianBlur(120))
    img = Image.composite(black, img, logo_shade)

    img = chroma_shift(img, 2)
    img = scanlines(img, period=3, strength=0.14)
    img = grain(img, amount=6)
    return img


# Loading screens: source file in tools/src/loading -> gfx/loadingscreens/totu_load_<name>.dds
# "bars" are eye bars for public figures only, in source-image pixels: ((x1, y1), (x2, y2), thickness)
LOADING_SCREENS = [
    ("tanks_red_square", []),
    ("yeltsin_podium", [((772, 292), (1018, 262), 50)]),
    ("yeltsin_tank", [((938, 313), (1072, 307), 26)]),
    ("white_house", []),
]


def eye_bar(img, start, end, thickness):
    """Black bar through both eyes, slightly overshooting the face like a press redaction."""
    import math
    (x1, y1), (x2, y2) = start, end
    ang = math.atan2(y2 - y1, x2 - x1)
    nx, ny = -math.sin(ang) * thickness / 2, math.cos(ang) * thickness / 2
    poly = [(x1 + nx, y1 + ny), (x2 + nx, y2 + ny), (x2 - nx, y2 - ny), (x1 - nx, y1 - ny)]
    ImageDraw.Draw(img).polygon(poly, fill=(6, 5, 4))
    return img


def build_loading(src, bars):
    """1920x1440 frame: photo at full width, centred; the rest is a dark blurred extension.
    A 16:9 screen sees the middle 1080 rows, so nothing important gets cropped."""
    W, H = 1920, 1440
    photo = Image.open(src).convert("RGB")
    for start, end, thick in bars:
        eye_bar(photo, start, end, thick)
    ph = round(photo.height * W / photo.width)
    photo = photo.resize((W, ph), Image.LANCZOS)

    img = cover(photo, W, H).filter(ImageFilter.GaussianBlur(40))
    img = ImageEnhance.Brightness(img).enhance(0.35)
    top = (H - ph) // 2
    fade = Image.new("L", (W, ph), 255)
    edge = 90
    fd = ImageDraw.Draw(fade)
    for i in range(edge):
        v = round(255 * i / edge)
        fd.line((0, i, W, i), fill=v)
        fd.line((0, ph - 1 - i, W, ph - 1 - i), fill=v)
    img.paste(photo, (0, top), fade)

    img = tone(img, sat=0.72, bright=0.62, contrast=1.12, shadow=(12, 9, 8), highlight=(226, 168, 112), mix=0.32)
    black = Image.new("RGB", (W, H), (8, 6, 5))
    img = Image.composite(black, img, radial_mask(W, H, inner=0.38, outer=1.1).point(lambda v: v * 0.8))
    img = chroma_shift(img, 2)
    img = scanlines(img, period=3, strength=0.14)
    img = grain(img, amount=6)
    return img


def build_photo(src, crop):
    img = Image.open(src).convert("RGB").crop(crop)
    img = cover(img, PHOTO_W, PHOTO_H)
    img = ImageOps.grayscale(img)
    img = ImageOps.autocontrast(img, cutoff=1)
    img = ImageOps.colorize(img, (16, 12, 10), (222, 205, 178)).convert("RGB")
    img = ImageEnhance.Brightness(img).enhance(0.82)
    vign = radial_mask(PHOTO_W, PHOTO_H, inner=0.45, outer=1.15)
    img = Image.composite(Image.new("RGB", img.size, (10, 8, 7)), img, vign.point(lambda v: v * 0.8))
    img = scanlines(img, period=2, strength=0.10)
    img = grain(img, amount=12, seed=7)
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, PHOTO_W - 1, PHOTO_H - 1), outline=LINE)
    return img


def build_panel():
    img = Image.new("RGBA", (PANEL_W, PANEL_H), INK + (238,))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, PANEL_W - 1, PANEL_H - 1), outline=LINE + (255,))
    d.rectangle((3, 3, PANEL_W - 4, PANEL_H - 4), outline=LINE_DIM + (255,))
    d.line((COL_W, 14, COL_W, PANEL_H - 15), fill=LINE_DIM + (255,))
    d.line((TEXT_SPLIT_X, TEXT_Y + 4, TEXT_SPLIT_X, PANEL_H - 15), fill=LINE_DIM + (255,))
    # Divider above Quit (button column, y=QUIT_DIVIDER_Y)
    d.line((16, QUIT_DIVIDER_Y, COL_W - 16, QUIT_DIVIDER_Y), fill=LINE_DIM + (255,))
    return img


def build_button(fw=288, fh=36):
    img = Image.new("RGBA", (fw * 3, fh), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    frames = [
        ((29, 25, 22), LINE, None),        # normal
        ((38, 31, 26), ACCENT, ACCENT),    # hover
        ((16, 13, 11), ACCENT, ACCENT),    # pressed
    ]
    for i, (fill, border, mark) in enumerate(frames):
        x = i * fw
        d.rectangle((x, 0, x + fw - 1, fh - 1), fill=fill + (245,), outline=border + (255,))
        if mark:
            d.rectangle((x + 1, 1, x + 3, fh - 2), fill=mark + (255,))
    return img


def tracked(draw, xy, text, fnt, fill, tracking):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill)
        x += draw.textlength(ch, font=fnt) + tracking
    return x


def tracked_width(draw, text, fnt, tracking):
    return sum(draw.textlength(ch, font=fnt) for ch in text) + tracking * (len(text) - 1)


def build_logo():
    W, H = 760, 214
    text = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(text)
    small = font("bahnschrift.ttf", 19)
    big = font("pala.ttf", 92)
    ital = font("palai.ttf", 44)

    tracked(d, (6, 8), "MOSCOW  \u00b7  JANUARY 1990", small, DUST + (255,), 5)
    tracked(d, (0, 30), "TWILIGHT", big, PAPER + (255,), 9)
    x = tracked(d, (4, 128), "of the", ital, (185, 171, 149, 255), 1)
    tracked(d, (x + 18, 112), "UNION", big, PAPER + (255,), 9)

    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    shadow.putalpha(text.getchannel("A").filter(ImageFilter.GaussianBlur(10)).point(lambda v: min(255, v * 2)))
    shadow = Image.composite(Image.new("RGBA", (W, H), (0, 0, 0, 170)), shadow, shadow.getchannel("A"))
    return Image.alpha_composite(shadow, text)


def frame_box(w, h, alpha=232, fill=INK):
    """Flat dark box with the double hairline used across the UI."""
    img = Image.new("RGBA", (w, h), fill + (alpha,))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, w - 1, h - 1), outline=LINE + (255,))
    d.rectangle((3, 3, w - 4, h - 4), outline=LINE_DIM + (255,))
    return img


# Loading screen (interface/load_screen.gui). Both boxes sit at the bottom centre.
LOAD_BOX_W = 1100
LOAD_TIP_H = 104
LOAD_STATUS_H = 100
LOAD_BAR_W, LOAD_BAR_H = 934, 20
TAN = (195, 176, 145)       # same as the §L text colour


def build_progress(filled):
    img = Image.new("RGBA", (LOAD_BAR_W, LOAD_BAR_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if filled:
        d.rectangle((0, 0, LOAD_BAR_W - 1, LOAD_BAR_H - 1), fill=(150, 133, 106, 255))
        d.rectangle((0, 0, LOAD_BAR_W - 1, LOAD_BAR_H // 2 - 1), fill=(166, 149, 121, 255))
        for x in range(0, LOAD_BAR_W, 6):      # faint ticks, like a VU meter
            d.line((x, 2, x, LOAD_BAR_H - 3), fill=(128, 112, 88, 255))
    else:
        d.rectangle((0, 0, LOAD_BAR_W - 1, LOAD_BAR_H - 1), fill=(12, 10, 9, 230))
    d.rectangle((0, 0, LOAD_BAR_W - 1, LOAD_BAR_H - 1), outline=LINE + (255,))
    return img


# Scenario picker (interface/frontendgamesetupview.gui, gamesetup_scenario_window)
SCEN_W, SCEN_H = 579, 512
SCEN_PAPER = (18, 300, 561, 446)   # where bookmark_title / bookmark_desc are drawn (dark typewriter font)
PAPER_TONE = (199, 189, 170)


def build_scenario_bg():
    img = frame_box(SCEN_W, SCEN_H, alpha=245)
    d = ImageDraw.Draw(img)
    d.line((14, 50, SCEN_W - 15, 50), fill=LINE_DIM + (255,))            # under title
    d.line((14, 268, SCEN_W - 15, 268), fill=LINE_DIM + (255,))          # above "Brief history"
    x1, y1, x2, y2 = SCEN_PAPER
    paper = Image.new("RGB", (x2 - x1, y2 - y1), PAPER_TONE)
    paper = grain(paper, amount=9, seed=3)
    vign = radial_mask(paper.width, paper.height, inner=0.55, outer=1.3)
    paper = Image.composite(Image.new("RGB", paper.size, (150, 138, 118)), paper, vign.point(lambda v: v * 0.6))
    img.paste(paper, (x1, y1))
    d.rectangle((x1, y1, x2 - 1, y2 - 1), outline=LINE + (255,))
    d.line((14, 448 + 6, SCEN_W - 15, 448 + 6), fill=LINE_DIM + (255,))  # above buttons
    return img


def build_bookmark_entry():
    """Two frames, 232x211 each: normal, selected. Icon sits at (27, 28), 180x104."""
    fw, fh = 232, 211
    img = Image.new("RGBA", (fw * 2, fh), (0, 0, 0, 0))
    for i, border in enumerate((LINE, TAN)):
        box = frame_box(fw - 8, fh - 30, alpha=240)
        bd = ImageDraw.Draw(box)
        if i:
            bd.rectangle((0, 0, box.width - 1, box.height - 1), outline=border + (255,))
            bd.rectangle((1, 1, box.width - 2, box.height - 2), outline=border + (255,))
        bd.rectangle((22, 23, 22 + 181, 23 + 105), outline=LINE + (255,))     # around the icon
        bd.line((14, 113 + 22, box.width - 15, 113 + 22), fill=LINE_DIM + (255,))
        img.alpha_composite(box, (i * fw + 4, 4))
    return img


def paper_sheet(w, h, seed=3):
    """Muted paper for the dark typewriter fonts the engine uses on setup screens."""
    paper = grain(Image.new("RGB", (w, h), PAPER_TONE), amount=9, seed=seed)
    vign = radial_mask(w, h, inner=0.55, outer=1.3)
    return Image.composite(Image.new("RGB", (w, h), (150, 138, 118)), paper, vign.point(lambda v: v * 0.6))


# Country selection (gamesetup_interesting_countries_window, 1225x717; texture keeps vanilla 1225x728)
# Top band: two art banners with the two major entries between them (countries grid at x=462).
# Middle band: minor country flags. Bottom: info / centre / history panels (light fonts, dark panels).
CS_W, CS_H = 1225, 728
CS_TOP = (41, 318)                      # top and bottom y of the banner band
CS_ART_LEFT = (14, 452)                 # USA banner x range
CS_ART_RIGHT = (772, 1211)              # SOV banner x range
CS_FLAG_BAND = (318, 446)
CS_PANELS = [(14, 452, 430, 712), (438, 452, 786, 712), (794, 452, 1211, 712)]


def us_flag(w, h):
    """50-star flag, drawn rather than upscaled from the 82x52 game flag."""
    import math
    img = Image.new("RGB", (w, h), (255, 255, 255))
    d = ImageDraw.Draw(img)
    stripe = h / 13
    for i in range(0, 13, 2):
        d.rectangle((0, round(i * stripe), w, round((i + 1) * stripe)), fill=(178, 34, 52))
    cw, ch = round(w * 0.4), round(stripe * 7)
    d.rectangle((0, 0, cw, ch), fill=(60, 59, 110))

    def star(cx, cy, r):
        pts = []
        for k in range(10):
            a = -math.pi / 2 + k * math.pi / 5
            rr = r if k % 2 == 0 else r * 0.38
            pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
        d.polygon(pts, fill=(255, 255, 255))

    for row in range(9):
        n = 6 if row % 2 == 0 else 5
        for col in range(n):
            x = cw / 12 * (2 * col + (1 if row % 2 == 0 else 2))
            y = ch / 10 * (row + 1)
            star(x, y, ch / 10 * 0.4)
    return img


def soviet_flag(w, h):
    img = Image.new("RGB", (w, h), (204, 0, 0))
    d = ImageDraw.Draw(img)
    gold = (255, 215, 0)
    d.text((round(h * 0.12), round(h * 0.16)), "☭", font=font("seguisym.ttf", round(h * 0.34)), fill=gold)
    d.text((round(h * 0.2), round(h * 0.02)), "☆", font=font("seguisym.ttf", round(h * 0.14)), fill=gold)
    return img


def tint_with(base, photo, mask, strength=1.0):
    """Photo luminance carried by the flag colours, faded in through mask."""
    lum = ImageOps.autocontrast(ImageOps.grayscale(photo), cutoff=1)
    lifted = ImageChops.multiply(base, Image.merge("RGB", (lum, lum, lum)))
    lifted = Image.blend(lifted, ImageChops.screen(lifted, Image.new("RGB", base.size, (25, 20, 18))), 0.3)
    return Image.composite(lifted, base, mask.point(lambda v: round(v * strength)))


def h_fade(w, h, solid_from, solid_to, feather):
    """Mask that is 255 between solid_from..solid_to (x) and fades out over feather px either side."""
    row = Image.new("L", (w, 1), 0)
    for x in range(w):
        if x < solid_from:
            v = max(0.0, 1 - (solid_from - x) / feather)
        elif x > solid_to:
            v = max(0.0, 1 - (x - solid_to) / feather)
        else:
            v = 1.0
        row.putpixel((x, 0), round(255 * v))
    return row.resize((w, h))


def build_banner(flag, layers, w, h, inner_side, bright=0.62):
    """layers: [(photo, crop, x, width, strength[, flatten])]; each photo is cover-fitted into x..x+width.
    flatten (0..1) evens out a busy flag under the photo (stripes would cut through a face)."""
    base = ImageEnhance.Brightness(ImageEnhance.Color(cover(flag, w, h)).enhance(0.8)).enhance(bright)
    for layer in layers:
        src, crop, x, lw, strength = layer[:5]
        flatten = layer[5] if len(layer) > 5 else 0.0
        ph = Image.open(src).convert("RGB")
        if crop:
            ph = ph.crop(crop)
        full = Image.new("RGB", (w, h), (128, 128, 128))
        full.paste(cover(ph, lw, h), (x, 0))
        # Fade only on edges that face the inside of the banner; a photo on the banner edge stays solid there.
        solid_from = 0 if x <= 0 else x + 40
        solid_to = w if x + lw >= w else x + lw - 60
        mask = h_fade(w, h, solid_from, solid_to, 70)
        if flatten:
            avg = base.resize((1, 1), Image.BOX).getpixel((0, 0))
            flat = Image.blend(base, Image.new("RGB", (w, h), avg), flatten)
            base = Image.composite(flat, base, mask)
        base = tint_with(base, full, mask, strength)
    base = tone(base, sat=0.85, bright=0.95, contrast=1.08, shadow=(12, 9, 8), highlight=(230, 180, 130), mix=0.18)

    # Darken toward the major entries and the bottom edge so cards and text stay readable.
    side = Image.new("L", (w, 1), 0)
    for i in range(140):
        side.putpixel((w - 1 - i if inner_side == "right" else i, 0), round(170 * (1 - i / 140)))
    side = side.resize((w, h))
    bottom = Image.new("L", (1, h), 0)
    for i in range(60):
        bottom.putpixel((0, h - 1 - i), round(120 * (1 - i / 60)))
    shade = ImageChops.lighter(side, bottom.resize((w, h)))
    base = Image.composite(Image.new("RGB", (w, h), (10, 8, 7)), base, shade)
    base = chroma_shift(base, 1)
    base = scanlines(base, period=3, strength=0.12)
    return grain(base, amount=6, seed=w)


def build_country_select_bg():
    img = frame_box(CS_W, CS_H, alpha=245)
    d = ImageDraw.Draw(img)
    hl = LINE_DIM + (255,)
    top, bottom = CS_TOP
    h = bottom - top
    lw = CS_ART_LEFT[1] - CS_ART_LEFT[0]
    rw = CS_ART_RIGHT[1] - CS_ART_RIGHT[0]
    # US banner mirrors the Soviet one: leader on the outer (left) edge, army photo in the middle.
    # The flag is reversed (canton toward the centre, as on the right-sleeve uniform patch) so the
    # stars don't sit on the leader's face.
    us_layers = []
    army = next(iter(sorted((SRC / "banners").glob("usa_army.*"))), None) if (SRC / "banners").exists() else None
    if army:
        # Crop is tuned for Abrams_in_formation.jpg (Wikimedia Commons, US Navy, public domain); adjust for another photo.
        us_layers.append((army, (600, 450, 2220, 1810), 130, 330, 0.9, 0.4))
    us_layers.append((SRC / "portraits" / "USA_george_bush.webp", (250, 120, 1350, 1560), 0, 220, 0.95, 0.7))
    left = build_banner(us_flag(lw, h).transpose(Image.FLIP_LEFT_RIGHT), us_layers, lw, h,
                        inner_side="right", bright=0.5)
    right = build_banner(soviet_flag(rw, h), [
        (SRC / "loading" / "tanks_red_square.webp", None, 0, 300, 0.9),
        (SRC / "portraits" / "SOV_mikhail_gorbachev.webp", (200, 150, 1300, 1500), rw - 210, 210, 0.95),
    ], rw, h, inner_side="left")
    img.paste(left, (CS_ART_LEFT[0], top))
    img.paste(right, (CS_ART_RIGHT[0], top))
    d.rectangle((CS_ART_LEFT[0], top, CS_ART_LEFT[1] - 1, bottom - 1), outline=LINE + (255,))
    d.rectangle((CS_ART_RIGHT[0], top, CS_ART_RIGHT[1] - 1, bottom - 1), outline=LINE + (255,))
    d.line((14, 40, CS_W - 15, 40), fill=hl)                                          # under title
    d.rectangle((14, CS_FLAG_BAND[0] + 6, CS_W - 15, CS_FLAG_BAND[1] - 2), fill=(12, 10, 9, 255), outline=LINE + (255,))
    for box in CS_PANELS:
        d.rectangle(box, fill=(12, 10, 9, 255), outline=LINE + (255,))
    for box in [(451, 487, 526, 562), (542, 486, 774, 553), (451, 572, 774, 666)]:  # faction, ideas, focuses
        d.rectangle(box, fill=(22, 18, 16, 255), outline=LINE_DIM + (255,))
    return img


def two_frames(fw, fh, draw_frame):
    img = Image.new("RGBA", (fw * 2, fh), (0, 0, 0, 0))
    for i in range(2):
        img.alpha_composite(draw_frame(fw, fh, selected=bool(i)), (i * fw, 0))
    return img


def entry_box(fw, fh, selected, inset=2):
    box = Image.new("RGBA", (fw, fh), (0, 0, 0, 0))
    inner = frame_box(fw - inset * 2, fh - inset * 2, alpha=235)
    box.alpha_composite(inner, (inset, inset))
    if selected:
        d = ImageDraw.Draw(box)
        d.rectangle((inset, inset, fw - inset - 1, fh - inset - 1), outline=TAN + (255,))
        d.rectangle((inset + 1, inset + 1, fw - inset - 2, fh - inset - 2), outline=TAN + (255,))
    return box


def chevrons(d, y, x_left, x_right, colour):
    d.polygon([(x_left, y - 6), (x_left + 6, y), (x_left, y + 6)], fill=colour)
    d.polygon([(x_right, y - 6), (x_right - 6, y), (x_right, y + 6)], fill=colour)


# Major card, flag only (no leader portrait). Mirrored in frontendgamesetupview.gui, "country_entry".
MAJOR_FLAG_SCALE = 1.0                  # the engine ignores scale on this flag icon, keep native 82x52
MAJOR_FLAG_POS = (34, 104)
MAJOR_NAME_Y = 168                      # three-line plate: full names wrap instead of being cut
MAJOR_NAME_H = 58


def major_entry(fw, fh, selected):
    """150x274. Big flag at MAJOR_FLAG_POS, name plate under it; the rest of the card is empty."""
    box = Image.new("RGBA", (fw, fh), (0, 0, 0, 0))
    d = ImageDraw.Draw(box)
    edge = TAN if selected else LINE
    fx, fy = MAJOR_FLAG_POS
    fw_, fh_ = round(82 * MAJOR_FLAG_SCALE), round(52 * MAJOR_FLAG_SCALE)
    # The engine draws the flag UNDER this sprite: keep its window transparent (outline only).
    d.rectangle((fx - 4, fy - 4, fx + fw_ + 3, fy + fh_ + 3), outline=edge + (255,))
    d.rectangle((fx - 2, fy - 2, fx + fw_ + 1, fy + fh_ + 1), outline=LINE_DIM + (255,))
    d.rectangle((6, MAJOR_NAME_Y - 4, 144, MAJOR_NAME_Y - 4 + MAJOR_NAME_H), fill=(22, 18, 16, 245), outline=edge + (255,))
    if selected:
        chevrons(d, fy + fh_ // 2, 3, 147, TAN + (255,))
    return box


def medium_entry(fw, fh, selected):
    """138x97. Flag 82x52 at (26,22)."""
    box = Image.new("RGBA", (fw, fh), (0, 0, 0, 0))
    d = ImageDraw.Draw(box)
    edge = TAN if selected else LINE
    d.rectangle((21, 17, 112, 78), outline=edge + (255,))                                 # flag drawn underneath
    d.rectangle((23, 19, 110, 76), outline=LINE_DIM + (255,))
    if selected:
        chevrons(d, 48, 8, 129, TAN + (255,))
    return box


def minor_portrait_overlay():
    """126x166 frame over the minor leader portrait (portrait at +9,+11, 0.696 scale -> 109x146)."""
    img = Image.new("RGBA", (126, 166), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle((7, 9, 7 + 112, 9 + 149), outline=LINE + (255,))
    d.rectangle((4, 6, 7 + 115, 9 + 152), outline=LINE_DIM + (255,))
    for cx, cy in [(4, 6), (122, 6), (4, 161), (122, 161)]:            # photo corners
        d.rectangle((cx - 3, cy - 3, cx + 3, cy + 3), fill=TAN + (255,))
    return img


# Leader portraits: tools/src/portraits/<character>.webp -> gfx/leaders/totu/<character>.dds (156x210)
PORTRAITS = {
    "SOV_mikhail_gorbachev": (330, 140, 1250, 1378),   # crop around head and shoulders
    "USA_george_bush": (270, 120, 1310, 1520),
}


def build_portrait(src, crop):
    img = cover(Image.open(src).convert("RGB").crop(crop), 156, 210)
    img = tone(img, sat=0.8, bright=0.82, contrast=1.1, shadow=(14, 11, 9), highlight=(236, 196, 150), mix=0.28)
    img = Image.composite(Image.new("RGB", img.size, (10, 8, 7)), img,
                          radial_mask(156, 210, inner=0.5, outer=1.2).point(lambda v: v * 0.7))
    img = scanlines(img, period=2, strength=0.07)
    return grain(img, amount=6, seed=21)


# National spirit icons: picture name -> glyph (Segoe UI Symbol). Output gfx/interface/ideas/totu/idea_<name>.dds,
# sprites GFX_idea_<name> in interface/totu_ideas.gfx. 65x67 matches most vanilla idea icons.
IDEA_ICONS = {
    "totu_no_plan_no_market": "⚖",    # scales: plan vs market
    "totu_glasnost": "✉",             # envelope: open letters, free press
    "totu_nomenklatura": "⚙",         # gear: the apparatus
    "totu_awakening_republics": "⚑",  # flag
    "totu_bloated_mic": "⚒",          # hammer and pick: heavy industry
    "totu_afghan_syndrome": "⛰",      # mountains: Afghanistan
    "totu_conscript_army": "★",       # star
}


def build_idea_icon(glyph, box=40):
    img = Image.new("RGBA", (65, 67), (0, 0, 0, 0))
    plate = frame_box(59, 59, alpha=250, fill=(22, 18, 16))
    pd = ImageDraw.Draw(plate)
    for y in range(4, 55, 2):                                   # faint scanlines, under the glyph
        pd.line((4, y, 54, y), fill=(14, 11, 10, 255))
    size = 60                                                   # shrink the font until the glyph fits the box
    while size > 10:
        f = font("seguisym.ttf", size)
        l, t, r, b = pd.textbbox((0, 0), glyph, font=f, stroke_width=1)
        if r - l <= box and b - t <= box:
            break
        size -= 2
    pd.text(((59 - (r - l)) / 2 - l, (59 - (b - t)) / 2 - t), glyph, font=f, fill=TAN + (255,),
            stroke_width=1, stroke_fill=TAN + (255,))
    img.alpha_composite(plate, (3, 4))
    return img


def write_idea_sprites():
    """interface/totu_ideas.gfx: one GFX_idea_<name> sprite per IDEA_ICONS entry."""
    blocks = []
    for name in IDEA_ICONS:
        blocks.append(
            "\tspriteType = {\n"
            f"\t\tname = \"GFX_idea_{name}\"\n"
            f"\t\ttexturefile = \"gfx/interface/ideas/totu/idea_{name}.dds\"\n"
            "\t}\n")
    text = ("# GENERATED by tools/build_menu_gfx.py (IDEA_ICONS) - edit the script, not this file."
            + "\nspriteTypes = {\n" + "\n".join(blocks) + "}\n")
    (ROOT / "interface/totu_ideas.gfx").write_text(text, encoding="utf-8", newline="\n")


def build_bookmark_icon(src, crop):
    img = Image.open(src).convert("RGB").crop(crop)
    img = cover(img, 180, 104)
    img = tone(img, sat=0.72, bright=0.7, contrast=1.15, shadow=(12, 9, 8), highlight=(226, 168, 112), mix=0.32)
    img = scanlines(img, period=2, strength=0.10)
    return grain(img, amount=8, seed=11)


def build_preview(bg, logo, panel, photo, button):
    """Rough 1920x1080 composite to eyeball the result without launching the game."""
    shot = bg.crop((0, 180, 1920, 1260)).convert("RGBA")
    shot.alpha_composite(logo, (30, 26))
    px, py = 960 - PANEL_W // 2, 540 - 200
    shot.alpha_composite(panel, (px, py))
    shot.alpha_composite(photo.convert("RGBA"), (px + PHOTO_X, py + PHOTO_Y))
    d = ImageDraw.Draw(shot)
    f = font("bahnschrift.ttf", 20)
    labels = [("SINGLE PLAYER", 18, 1), ("MULTIPLAYER", 58, 0), ("OPTIONS", 98, 0), ("CREDITS", 138, 0), ("QUIT", 194, 0)]
    for label, y, frame in labels:
        shot.alpha_composite(button.crop((frame * 288, 0, frame * 288 + 288, 36)), (px + 16, py + y))
        w = d.textlength(label, font=f)
        d.text((px + 16 + 144 - w / 2, py + y + 6), label, font=f, fill=(225, 215, 198))
    body = font("georgia.ttf", 15)
    d.text((px + PHOTO_X, py + TEXT_Y + 6), "Twilight of the Union  v0.1", font=font("bahnschrift.ttf", 18), fill=(195, 176, 145))
    d.multiline_text((px + PHOTO_X, py + TEXT_Y + 36),
                     "The Union has outlived its promises.\nThe Baltic is restless, the shelves are\nempty, and Moscow is out of answers.",
                     font=body, fill=(200, 192, 180), spacing=5)
    d.text((px + TEXT_SPLIT_X + 14, py + TEXT_Y + 6), "In this build", font=font("bahnschrift.ttf", 18), fill=(195, 176, 145))
    d.multiline_text((px + TEXT_SPLIT_X + 14, py + TEXT_Y + 36), "- 1990 start date\n- Main menu", font=body, fill=(200, 192, 180), spacing=5)
    return shot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bg", default=SRC / "red_square.webp", type=Path)
    ap.add_argument("--photo", default=SRC / "red_square.webp", type=Path)
    ap.add_argument("--photo-crop", default="300,370,1220,787",
                    help="left,top,right,bottom crop of the photo source")
    args = ap.parse_args()

    (ROOT / "tools/preview").mkdir(parents=True, exist_ok=True)
    bg = build_background(args.bg)
    save_dds(bg, ROOT / "gfx/loadingscreens/totu_red_square.dds")
    save_dds(bg.resize((192, 144), Image.LANCZOS), ROOT / "gfx/interface/totu/menu_bg_small.dds")

    photo = build_photo(args.photo, tuple(int(v) for v in args.photo_crop.split(",")))
    panel = build_panel()
    button = build_button()
    logo = build_logo()
    save_dds(photo, ROOT / "gfx/interface/totu/menu_photo.dds")
    save_dds(panel, ROOT / "gfx/interface/totu/menu_panel.dds")
    save_dds(button, ROOT / "gfx/interface/totu/menu_button.dds")
    save_dds(logo, ROOT / "gfx/interface/totu/menu_logo.dds")

    for name, bars in LOADING_SCREENS:
        load = build_loading(SRC / "loading" / f"{name}.webp", bars)
        save_dds(load, ROOT / f"gfx/loadingscreens/totu_load_{name}.dds")
        load.crop((0, 180, 1920, 1260)).resize((960, 540), Image.LANCZOS).save(ROOT / f"tools/preview/load_{name}.jpg", quality=88)

    # Loading screen UI
    save_dds(frame_box(LOAD_BOX_W, LOAD_TIP_H, alpha=215), ROOT / "gfx/interface/totu/loading_tip.dds")
    save_dds(frame_box(LOAD_BOX_W, LOAD_STATUS_H, alpha=215), ROOT / "gfx/interface/totu/loading_status.dds")
    save_dds(build_progress(False), ROOT / "gfx/interface/totu/loading_progress_empty.dds")
    save_dds(build_progress(True), ROOT / "gfx/interface/totu/loading_progress_full.dds")

    # Scenario picker
    save_dds(build_scenario_bg(), ROOT / "gfx/interface/totu/scenario_bg.dds")
    save_dds(build_bookmark_entry(), ROOT / "gfx/interface/totu/bookmark_entry.dds")
    save_dds(build_button(221, 34), ROOT / "gfx/interface/totu/button_221x34.dds")
    save_dds(build_bookmark_icon(SRC / "loading" / "tanks_red_square.webp", (560, 0, 1880, 760)),
             ROOT / "gfx/interface/totu/select_date_1990.dds")

    # Country selection
    save_dds(build_country_select_bg(), ROOT / "gfx/interface/totu/country_select_bg.dds")
    save_dds(two_frames(150, 274, major_entry), ROOT / "gfx/interface/totu/country_entry_major.dds")
    save_dds(two_frames(138, 97, medium_entry), ROOT / "gfx/interface/totu/country_entry_minor.dds")
    save_dds(two_frames(59, 44, lambda w, h, selected: entry_box(w, h, selected, inset=1)),
             ROOT / "gfx/interface/totu/country_entry_mini.dds")
    save_dds(two_frames(149, 34, lambda w, h, selected: entry_box(w, h, selected, inset=1)),
             ROOT / "gfx/interface/totu/country_filter.dds")
    save_dds(minor_portrait_overlay(), ROOT / "gfx/interface/totu/minor_portrait_overlay.dds")
    save_dds(build_button(148, 34), ROOT / "gfx/interface/totu/button_148x34.dds")

    for name, glyph in IDEA_ICONS.items():
        save_dds(build_idea_icon(glyph), ROOT / f"gfx/interface/ideas/totu/idea_{name}.dds")
    write_idea_sprites()

    for name, crop in PORTRAITS.items():
        save_dds(build_portrait(SRC / "portraits" / f"{name}.webp", crop), ROOT / f"gfx/leaders/totu/{name}.dds")

    preview = ROOT / "tools/preview/menu_preview.png"
    build_preview(bg, logo, panel, photo, button).convert("RGB").save(preview)
    print("wrote", preview.relative_to(ROOT))


if __name__ == "__main__":
    main()
