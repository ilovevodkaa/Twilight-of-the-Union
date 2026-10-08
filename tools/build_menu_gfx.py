"""Builds the frontend textures of Twilight of the Union: main menu, loading screens, scenario picker, country
selection (design "broadcast": a late-Soviet TV picture with keyed captions).

Usage:
    python tools/build_menu_gfx.py                      # default sources
    python tools/build_menu_gfx.py --bg other.jpg       # other menu background (see BG_* constants first)

Outputs DDS files into gfx/ and preview PNGs into tools/preview/ (menu_preview.png, loading_preview.png,
screen_scenario.png; the country selection preview is tools/preview_country.py). The previews draw their captions
with the fonts in gfx/fonts, so run tools/build_fonts.py first after changing them; the scenario preview draws its
body text with the vanilla hoi_20b font from the game folder (env HOI4_DIR, default D:/steam/.../Hearts of Iron IV).
Requires Pillow and numpy (pip install pillow numpy).
"""
import argparse
import os
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "tools" / "src"
GAME = Path(os.environ.get("HOI4_DIR", r"D:\steam\steamapps\common\Hearts of Iron IV"))   # vanilla fonts (previews)

# Palette of the in-game menu button (menu_button.dds)
LINE = (74, 64, 55)         # hairline
ACCENT = (163, 67, 47)      # the one red
TAN = (195, 176, 145)       # same as the §L text colour

# In-game menu buttons: GFX_main_lobby_button (interface/frontendmainview.gfx) is also used by the vanilla
# ingamemenu.gui and peaceconferencewindow.gui, so menu_button.dds stays although the main menu no longer uses it.
BTN_W, BTN_H = 356, 50


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


# Main menu background ("broadcast"): Red Square at dusk as a late-Soviet TV picture. GFX_frontend_bg shows the
# 1920x1440 texture at 100 % screen width (preserve_aspect_ratio, centred), so 21:9 sees texture rows 318..1122,
# 16:9 rows 180..1260 and 16:10 rows 120..1320: the Spasskaya star (BG_STAR_ROW) and the horizon fit all three.
# No scanlines and no tube mask; legibility comes from the scrims in the UI layer (build_scrim).
BG_W, BG_H = 1920, 1440
BG_PHOTO_SCALE = 0.87           # photo narrower than the texture; its sides are extended
BG_STAR_SRC_Y = 115             # tip of the Spasskaya star in the source
BG_STAR_ROW = 335
BG_HORIZON_SRC_Y = 990
# Source areas, tuned for tools/src/red_square.webp (2000x1333): architecture stays sharp, the sky above it gets
# its cloud wisps softened; the blue/cyan of St Basil's domes is greyed so the keyer blue is the one accent.
BG_ARCH = [(0, 735, 395, 1000), (560, 375, 685, 600), (395, 570, 815, 1000), (785, 845, 1255, 1000),
           (1415, 105, 1535, 450), (1345, 440, 1605, 1000), (1235, 560, 2000, 1000)]
BG_PAVEMENT_SRC_Y = 960
BG_BLUE_DOMES = (380, 560, 820, 760)
# The dusk ramp (luminance -> colour) of the menu background and the loading pictures: teal-black silhouettes,
# blue-grey mid-tones, mauve light
DUSK_STOPS = [(0.0, (5, 10, 16)), (0.25, (20, 32, 44)), (0.5, (56, 68, 90)),
              (0.7, (108, 98, 124)), (0.85, (168, 140, 162)), (1.0, (222, 202, 216))]


def lerp_stops(lum, stops):
    """Colour ramp: lum (0..1 array) -> RGB through [(position, (r, g, b)), ...]."""
    out = np.zeros(lum.shape + (3,), np.float32)
    for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
        t = np.clip((lum - p0) / (p1 - p0), 0, 1)[..., None]
        m = ((lum >= p0) & (lum <= p1))[..., None] if p0 > 0 else (lum <= p1)[..., None]
        seg = np.array(c0, np.float32) + (np.array(c1, np.float32) - np.array(c0, np.float32)) * t
        out = np.where(m, seg, out)
    return np.where((lum > stops[-1][0])[..., None], np.array(stops[-1][1], np.float32), out)


def prep_bg_photo(src):
    """Source photo with softened sky wisps and grey domes, scaled to BG_PHOTO_SCALE."""
    src = Image.open(src).convert("RGB")
    sw, sh = src.size
    # Hard dark cloud streaks read as a 'glitch filter' once graded; turn them into soft bands.
    keep = Image.new("L", src.size, 0)
    kd = ImageDraw.Draw(keep)
    for box in BG_ARCH:
        kd.rectangle(box, fill=255)
    kd.rectangle((0, BG_PAVEMENT_SRC_Y, sw, sh), fill=255)
    sky = ImageChops.invert(keep.filter(ImageFilter.MaxFilter(13))).filter(ImageFilter.GaussianBlur(14))
    soft = src.filter(ImageFilter.GaussianBlur(7))
    src = Image.composite(soft, src, sky.point(lambda v: v * 0.9))
    # blue/cyan -> near grey on the domes (saturation <= ~15 %)
    hsv = np.asarray(src.convert("HSV"), np.float32)
    h, s = hsv[..., 0] * 360 / 255, hsv[..., 1]
    yy, xx = np.mgrid[0:sh, 0:sw]
    x0, y0, x1, y1 = BG_BLUE_DOMES
    region = (xx >= x0) & (xx <= x1) & (yy >= y0) & (yy <= y1)
    blue = (h > 150) & (h < 260) & region
    hsv[..., 1] = np.where(blue, np.minimum(s, 0.15 * 255), s)
    src = Image.fromarray(hsv.astype(np.uint8), "HSV").convert("RGB")
    return src.resize((round(sw * BG_PHOTO_SCALE), round(sh * BG_PHOTO_SCALE)), Image.LANCZOS)


def extend_photo(photo, left, top):
    """Place the photo on the BG_W x BG_H texture and continue it outward: mirrored, increasingly defocused strips,
    the way the picture softens toward the edge of a kinescope. Top: mirrored sky, heavily blurred."""
    pw, ph = photo.size
    canvas = Image.new("RGB", (BG_W, BG_H))
    canvas.paste(photo, (left, top))
    for side in ("l", "r"):
        n = left if side == "l" else BG_W - left - pw
        if n <= 0:
            continue
        strip = photo.crop((0, 0, n, ph)) if side == "l" else photo.crop((pw - n, 0, pw, ph))
        canvas.paste(strip.transpose(Image.FLIP_LEFT_RIGHT), (0, top) if side == "l" else (left + pw, top))
    # horizontal defocus that grows toward both edges, starting well inside the photo so there is no seam
    blurred = canvas.filter(ImageFilter.BoxBlur(14)).filter(ImageFilter.GaussianBlur(5))
    reach = left + 150
    x = np.arange(BG_W, dtype=np.float32)
    d = np.clip(1 - np.minimum(x, BG_W - 1 - x) / reach, 0, 1)
    wgt = d * d * (3 - 2 * d)
    ramp = Image.fromarray((np.tile(wgt, (BG_H, 1)) * 255).astype(np.uint8))
    canvas = Image.composite(blurred, canvas, ramp)
    # sky above the photo
    if top > 0:
        band = canvas.crop((0, top, BG_W, top + top)).transpose(Image.FLIP_TOP_BOTTOM)
        canvas.paste(band.filter(ImageFilter.GaussianBlur(28)), (0, 0))
        soft = canvas.crop((0, top - 40, BG_W, top + 40)).filter(ImageFilter.GaussianBlur(10))
        canvas.paste(soft, (0, top - 40))
    below = BG_H - (top + ph)
    if below > 0:
        canvas.paste(canvas.crop((0, top + ph - 2, BG_W, top + ph)).resize((BG_W, below)), (0, top + ph))
    return canvas


def secam(img):
    """Colour-only SECAM pass: Y untouched. Cb/Cr band-limited horizontally (1x9), line-doubled vertically
    (delay-line decoder), lagging 3 px right, with faint red/blue fringes on strong vertical luma edges."""
    ycc = np.asarray(img.convert("YCbCr"), np.float32)
    Y = ycc[..., 0]
    k = np.ones(9, np.float32) / 9
    out = ycc.copy()
    gx = np.zeros_like(Y)
    gx[:, 1:-1] = (Y[:, 2:] - Y[:, :-2]) * 0.5
    gx = np.where(np.abs(gx) > 10, gx, 0)
    gx = np.apply_along_axis(lambda r: np.convolve(r, np.ones(5) / 5, mode="same"), 1, gx)
    for ci, sign in ((1, -1.0), (2, 1.0)):
        c = ycc[..., ci] - 128
        c = np.apply_along_axis(lambda r: np.convolve(r, k, mode="same"), 1, c)
        c[1::2] = c[0::2][: c[1::2].shape[0]]                  # chroma of every second line repeated
        c = np.roll(c, 3, axis=1)
        c = c + sign * 0.22 * np.roll(gx, 3, axis=1)
        out[..., ci] = np.clip(c + 128, 0, 255)
    return Image.fromarray(out.astype(np.uint8), "YCbCr").convert("RGB")


def build_background(src):
    """BG_W x BG_H RGB: dusk graded for a cold-white kinescope (teal-black silhouettes, mauve light low in the sky),
    horizontal edge fall-off of at most 28 %, colour-only SECAM pass, fine luma grain."""
    photo = prep_bg_photo(src)
    left = (BG_W - photo.width) // 2
    top = BG_STAR_ROW - round(BG_STAR_SRC_Y * BG_PHOTO_SCALE)
    img = extend_photo(photo, left, top)
    horizon = top + round(BG_HORIZON_SRC_Y * BG_PHOTO_SCALE)

    a = np.asarray(img, np.float32) / 255
    lum0 = a @ np.array([0.299, 0.587, 0.114], np.float32)
    L = np.clip((lum0 - 0.05) / 0.9, 0, 1) ** 1.65
    tint = lerp_stops(L, DUSK_STOPS) / 255
    grey = lum0[..., None]
    orig = (grey + (a - grey) * 0.7) * (L / np.maximum(lum0, 1e-3))[..., None]
    out = tint * 0.74 + np.clip(orig, 0, 1) * 0.26
    yy, xx = np.mgrid[0:BG_H, 0:BG_W].astype(np.float32)
    ground = np.clip((yy - horizon + 10) / 240, 0, 1)             # pavement falls off toward the camera
    sky_top = np.clip(1 - (yy - 150) / 620, 0, 1)                  # upper sky darker
    edge = np.minimum(xx, BG_W - 1 - xx)                           # kinescope edge fall-off, horizontal only
    edge_f = 1 - 0.28 * (1 - np.clip(edge / 300, 0, 1)) ** 2
    dark = (1 - 0.62 * ground ** 0.9) * (1 - 0.40 * sky_top ** 1.3) * edge_f
    out = out * dark[..., None]
    out = out + np.array([0.010, 0.018, 0.026], np.float32) * (1 - L[..., None])   # lifted, bluish black level
    img = Image.fromarray(np.clip(out * 255, 0, 255).astype(np.uint8))

    img = secam(img)
    rng = np.random.default_rng(4)
    n = rng.normal(0, 2.2, (BG_H, BG_W, 1)).astype(np.float32)     # fine luma grain, full res
    return Image.fromarray(np.clip(np.asarray(img, np.float32) + n, 0, 255).astype(np.uint8))


# Loading screens: source file in tools/src/loading -> gfx/loadingscreens/totu_load_<name>.dds, 1920x1440 RGB, drawn
# by the engine at screen width, centred like the menu background (21:9 sees texture rows 318..1122, 16:9 180..1260,
# 16:10 120..1320). (name, bars, exposure, dy, dx):
#   bars: eye bars for public figures only, in source-image pixels: ((x1, y1), (x2, y2), thickness)
#   exposure: luminance factor before the dusk grade
#   dy: moves the photo down in the texture, so every head's top is at row 330 or lower (21:9 top edge 318)
#   dx: moves the photo right; the podium speaker then clears the logo glyphs (screen x <= 662) down to 1280x720
LOADING_SCREENS = [
    ("tanks_red_square", [], 0.92, 60, 0),
    ("yeltsin_podium", [((772, 292), (1018, 262), 50)], 1.0, 120, 320),
    ("yeltsin_tank", [((938, 313), (1072, 307), 26)], 0.92, 150, 0),
    ("white_house", [], 0.88, 110, 0),
]
LOAD_W, LOAD_H = 1920, 1440
LOAD_EXT = 160              # photo rows / columns averaged into the field that fills the uncovered texture
LOAD_FEATHER = 90           # photo edges inside the texture fade into that field over this many px
LOAD_GRAIN_SEED = 5         # + index in LOADING_SCREENS; the menu background has seed 4, so the grain changes on the cut


def eye_bar(img, start, end, thickness):
    """Black bar through both eyes, slightly overshooting the face like a press redaction."""
    import math
    (x1, y1), (x2, y2) = start, end
    ang = math.atan2(y2 - y1, x2 - x1)
    nx, ny = -math.sin(ang) * thickness / 2, math.cos(ang) * thickness / 2
    poly = [(x1 + nx, y1 + ny), (x2 + nx, y2 + ny), (x2 - nx, y2 - ny), (x1 - nx, y1 - ny)]
    ImageDraw.Draw(img).polygon(poly, fill=(6, 5, 4))
    return img


def blur1d(a, sigma, axis):
    """Gaussian blur of a float array along one axis (edge-clamped)."""
    r = int(sigma * 3)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    pad = [(0, 0)] * a.ndim
    pad[axis] = (r, r)
    return np.apply_along_axis(lambda v: np.convolve(v, k, mode="valid"), axis, np.pad(a, pad, mode="edge"))


def place_photo(src, bars, dy, dx=0):
    """LOAD_W x LOAD_H RGB: eye bars drawn on the source, the photo scaled to the texture width and pasted with its
    top-left at (dx, (LOAD_H - ph) // 2 + dy). The uncovered texture is a shapeless field, not a mirrored or blurred
    copy (a mirror echoed a head as a dark ghost): the mean colour of the photo's nearest LOAD_EXT columns (per row)
    or rows (per column), blurred along the edge (sigma 60) and dimmed away from the photo to 55 % at 240 px. The
    photo's edges inside the texture are feathered into the field over LOAD_FEATHER px. dx > 0 cuts the photo's right
    dx columns."""
    photo = Image.open(src).convert("RGB")
    for start, end, thick in bars:
        eye_bar(photo, start, end, thick)
    ph = round(photo.height * LOAD_W / photo.width)
    a = np.asarray(photo.resize((LOAD_W, ph), Image.LANCZOS), np.float32)
    ramp = np.arange(LOAD_FEATHER, dtype=np.float32) / LOAD_FEATHER
    if dx:                                          # horizontal gap: per-row field
        n = abs(dx)
        strip = np.zeros_like(a)
        if dx > 0:
            strip[:, dx:] = a[:, :LOAD_W - dx]
            src_cols, gap, edge = a[:, :LOAD_EXT], slice(0, dx), slice(dx, dx + LOAD_FEATHER)
            dist = np.arange(n, dtype=np.float32)[::-1]
            w = ramp[None, :, None]
        else:
            strip[:, :LOAD_W - n] = a[:, n:]
            src_cols, gap = a[:, -LOAD_EXT:], slice(LOAD_W - n, LOAD_W)
            edge = slice(LOAD_W - n - LOAD_FEATHER, LOAD_W - n)
            dist = np.arange(n, dtype=np.float32)
            w = ramp[None, ::-1, None]
        field = blur1d(src_cols.mean(axis=1), 60, 0)                      # ph x 3
        strip[:, gap] = field[:, None] * (1 - 0.45 * np.clip((dist + 1) / 240, 0, 1))[None, :, None]
        strip[:, edge] = field[:, None] * (1 - w) + strip[:, edge] * w
        a = strip
    top = (LOAD_H - ph) // 2 + dy                   # vertical gaps: per-column fields above and below
    up = blur1d(a[:LOAD_EXT].mean(axis=0), 60, 0)                         # LOAD_W x 3
    down = blur1d(a[-LOAD_EXT:].mean(axis=0), 60, 0)
    rows = np.arange(LOAD_H, dtype=np.float32)
    ext = np.where((rows < top + ph / 2)[:, None, None], up[None], down[None])
    out_d = np.maximum(top - rows, rows - (top + ph - 1)).clip(0)
    ext = ext * (1 - 0.45 * np.clip(out_d / 240, 0, 1))[:, None, None]
    fade = np.ones(ph, np.float32)
    if top > 0:
        fade[:LOAD_FEATHER] = np.minimum(fade[:LOAD_FEATHER], ramp)
    if top + ph < LOAD_H:
        fade[-LOAD_FEATHER:] = np.minimum(fade[-LOAD_FEATHER:], ramp[::-1])
    y0, y1 = max(top, 0), min(top + ph, LOAD_H)
    f = fade[y0 - top:y1 - top][:, None, None]
    ext[y0:y1] = ext[y0:y1] * (1 - f) + a[y0 - top:y1 - top] * f
    return Image.fromarray(np.clip(ext, 0, 255).astype(np.uint8))


def grade_tv(img, exposure, seed):
    """The menu background's dusk grade for a loading photo: luminance through DUSK_STOPS (74 %) over the original at
    70 % saturation (26 %), the upper rows and the foreground held down by 30 %, horizontal kinescope edge fall-off
    of at most 28 %, lifted bluish black, colour-only SECAM pass, fine luma grain (own seed). No scanlines, no tube
    mask, no chroma shift."""
    a = np.asarray(img, np.float32) / 255
    lum0 = a @ np.array([0.299, 0.587, 0.114], np.float32)
    L = np.clip((lum0 * exposure - 0.05) / 0.9, 0, 1) ** 1.65
    tint = lerp_stops(L, DUSK_STOPS) / 255
    grey = lum0[..., None]
    orig = (grey + (a - grey) * 0.7) * (L / np.maximum(lum0, 1e-3))[..., None]
    out = tint * 0.74 + np.clip(orig, 0, 1) * 0.26
    yy, xx = np.mgrid[0:LOAD_H, 0:LOAD_W].astype(np.float32)
    top = np.clip(1 - (yy - 180) / 560, 0, 1)
    low = np.clip((yy - 880) / 380, 0, 1)
    edge = np.minimum(xx, LOAD_W - 1 - xx)
    edge_f = 1 - 0.28 * (1 - np.clip(edge / 300, 0, 1)) ** 2
    dark = (1 - 0.30 * top ** 1.3) * (1 - 0.30 * low ** 1.2) * edge_f
    out = out * dark[..., None]
    out = out + np.array([0.010, 0.018, 0.026], np.float32) * (1 - L[..., None])
    img = secam(Image.fromarray(np.clip(out * 255, 0, 255).astype(np.uint8)))
    n = np.random.default_rng(seed).normal(0, 2.2, (LOAD_H, LOAD_W, 1)).astype(np.float32)
    return Image.fromarray(np.clip(np.asarray(img, np.float32) + n, 0, 255).astype(np.uint8))


def build_loading(src, bars, exposure, dy, dx, seed):
    return grade_tv(place_photo(src, bars, dy, dx), exposure, seed)


def vertical_gradient(w, h, top, bottom, alpha):
    col = Image.new("RGBA", (1, h))
    for y in range(h):
        t = y / max(1, h - 1)
        col.putpixel((0, y), tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)) + (alpha,))
    return col.resize((w, h))


def build_button(fw=BTN_W, fh=BTN_H):
    """Three frames: normal, hover, pressed. Dark plate with a tan tick; hover lights a red bar and border."""
    img = Image.new("RGBA", (fw * 3, fh), (0, 0, 0, 0))
    frames = [
        ((34, 29, 25), (22, 18, 16), LINE, None),
        ((52, 40, 33), (30, 23, 19), ACCENT, ACCENT),
        ((16, 13, 11), (12, 10, 9), ACCENT, ACCENT),
    ]
    for i, (top, bottom, border, mark) in enumerate(frames):
        plate = vertical_gradient(fw, fh, top, bottom, 248)
        d = ImageDraw.Draw(plate)
        d.rectangle((0, 0, fw - 1, fh - 1), outline=border + (255,))
        d.line((1, 1, fw - 2, 1), fill=(70, 60, 52, 255) if i != 2 else (8, 6, 5, 255))   # top bevel
        if mark:
            d.rectangle((1, 1, 5, fh - 2), fill=mark + (255,))
        else:
            d.rectangle((1, fh // 2 - 6, 3, fh // 2 + 6), fill=TAN + (255,))
        # chevron on the right
        cy, cx = fh // 2, fw - 18
        col = (TAN if not mark else (226, 205, 170)) + (255,)
        d.line((cx - 4, cy - 6, cx + 2, cy, cx - 4, cy + 6), fill=col, width=2)
        img.alpha_composite(plate, (i * fw, 0))
    return img


# Terminal-style 5x7 pixel font for the logo (drawn here, no font file needed). '#' = lit cell.
PIXEL_FONT = {
    "A": [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "B": ["####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
    "C": [".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."],
    "D": ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
    "E": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    "F": ["#####", "#....", "#....", "####.", "#....", "#....", "#...."],
    "G": [".###.", "#...#", "#....", "#.###", "#...#", "#...#", ".###."],
    "H": ["#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "I": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"],
    "J": ["..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."],
    "K": ["#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"],
    "L": ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
    "M": ["#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"],
    "N": ["#...#", "#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#"],
    "O": [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "P": ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
    "Q": [".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"],
    "R": ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
    "S": [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
    "T": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    "U": ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "V": ["#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."],
    "W": ["#...#", "#...#", "#...#", "#.#.#", "#.#.#", "#.#.#", ".#.#."],
    "X": ["#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"],
    "Y": ["#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."],
    "Z": ["#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"],
    "0": [".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."],
    "1": ["..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."],
    "2": [".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"],
    "3": ["#####", "...#.", "..#..", "...#.", "....#", "#...#", ".###."],
    "4": ["...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."],
    "5": ["#####", "#....", "####.", "....#", "....#", "#...#", ".###."],
    "6": ["..##.", ".#...", "#....", "####.", "#...#", "#...#", ".###."],
    "7": ["#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."],
    "8": [".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."],
    "9": [".###.", "#...#", "#...#", ".####", "....#", "...#.", ".##.."],
    "-": [".....", ".....", ".....", ".###.", ".....", ".....", "....."],
    ".": [".....", ".....", ".....", ".....", ".....", ".....", "..#.."],
    " ": [".....", ".....", ".....", ".....", ".....", ".....", "....."],
}
# The menu caption fonts extend this face with Cyrillic and punctuation (CYRILLIC, PUNCTUATION in tools/build_fonts.py,
# the only copy); the menu preview below draws its captions from those built fonts.
LOGO_LINES = ["TWILIGHT", "OF THE", "UNION"]
LOGO_CELL = 10              # px per font cell: glyphs are 50x70
LOGO_LINE_GAP = 2           # cells between lines
LOGO_PAD = 36               # transparent margin for the glow


def pixel_text_mask(lines, cell, line_gap=2, letter_gap=1, ss=4):
    """Alpha mask of the pixel-font text. Drawn ss times larger, slightly softened and re-thresholded so the
    cell corners are a touch rounded like a real CRT glyph, then downsampled."""
    cols = max(len(l) for l in lines) * (5 + letter_gap) - letter_gap
    rows = len(lines) * 7 + (len(lines) - 1) * line_gap
    c = cell * ss
    big = Image.new("L", (cols * c, rows * c), 0)
    d = ImageDraw.Draw(big)
    for li, line in enumerate(lines):
        y0 = li * (7 + line_gap)
        for ci, ch in enumerate(line.upper()):
            glyph = PIXEL_FONT[ch]
            x0 = ci * (5 + letter_gap)
            for gy, row in enumerate(glyph):
                for gx, v in enumerate(row):
                    if v == "#":
                        d.rectangle(((x0 + gx) * c, (y0 + gy) * c, (x0 + gx + 1) * c - 1, (y0 + gy + 1) * c - 1),
                                    fill=255)
    big = big.filter(ImageFilter.GaussianBlur(c * 0.12)).point(lambda v: 255 if v > 110 else 0)
    return big.resize((cols * cell, rows * cell), Image.LANCZOS)


def build_logo():
    """TWILIGHT / OF THE / UNION in a terminal pixel font: off-white glyphs with a soft white glow, a faint
    chromatic fringe and CRT scanlines, matching the menu photos."""
    mask = pixel_text_mask(LOGO_LINES, LOGO_CELL, LOGO_LINE_GAP)
    W, H = mask.width + LOGO_PAD * 2, mask.height + LOGO_PAD * 2
    m = Image.new("L", (W, H), 0)
    m.paste(mask, (LOGO_PAD, LOGO_PAD))

    def layer(colour, alpha):
        img = Image.new("RGBA", (W, H), colour + (0,))
        img.putalpha(alpha)
        return img

    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    # dark halo so the light text reads on bright photos
    out.alpha_composite(layer((0, 0, 0), m.filter(ImageFilter.GaussianBlur(14)).point(lambda v: min(255, v * 1.6))))
    # wide warm glow + tight white glow (the "bloom" of the reference)
    out.alpha_composite(layer((236, 214, 196), m.filter(ImageFilter.GaussianBlur(22)).point(lambda v: v * 0.55)))
    out.alpha_composite(layer((255, 250, 244), m.filter(ImageFilter.GaussianBlur(5)).point(lambda v: v * 0.75)))
    # chromatic fringe, like the photos (red right, blue left)
    out.alpha_composite(layer((255, 70, 60), ImageChops.offset(m, 2, 0).point(lambda v: v * 0.35)))
    out.alpha_composite(layer((60, 120, 255), ImageChops.offset(m, -2, 0).point(lambda v: v * 0.35)))
    # the glyphs, with faint scanlines
    lines = Image.new("L", (1, H), 255)
    for y in range(0, H, 3):
        lines.putpixel((0, y), 200)
    out.alpha_composite(layer((246, 242, 234), ImageChops.multiply(m, lines.resize((W, H)))))
    return out


# Loading screen UI (interface/load_screen.gui, sprites in interface/load_screen.gfx), screen px at UI scale 1.0.
# Everything starts at x = SAFE_X (192). From the bottom: a 576x6 keyer-blue bar ending 72 px above the screen bottom
# (the menu's last plate bottom), 12 px gap, the status line (totu_caption_small_k, 14 px capitals), 32 px gap, then
# the tip box: the quote as a subtitle (1-3 hand-set lines of at most 40 characters, totu_caption_quote, pitch 44) over
# a name strap in D, bottom-aligned so the strap's baseline sits at H - 136. One soft lower-third scrim at the menu's
# alpha under the stack; the logo at the menu's place, on the menu's title scrim.
QUOTE_LINE = 44             # totu_caption_quote lineHeight: 28 px capitals + 16
QUOTE_BOX_W = 1056          # tip box maxWidth = 44 advances; hand-set lines use at most LOAD_LINE_MAX (4 spare)
QUOTE_LINES = 4             # tip box maxHeight = 4 lines: at most 3 quote lines + the name strap
LOAD_LINE_MAX = 40          # characters per hand-set tip line: ink ends at x <= 192 + 40 * 24 - 4 = 1148 < 1280 - 96
LOAD_BAR = (576, 6)         # GFX_loadingstatus_progress: 24 caption advances wide
LOAD_BAR_BOTTOM = 72        # bar ends this far above the screen bottom
LOAD_BAR_GAP = 12           # status capitals bottom -> bar top
LOAD_STATUS_GAP = 32        # name strap baseline -> status capitals top
LOAD_TRACK = (172, 180, 196, 46)    # empty part of the bar: colour D at 18 %
# Lower-third scrim (w, h, centre alpha, plateau radius): the menu's alpha; the full-alpha plateau (800 x 380 px)
# covers the 40-character measure (x 192..1148) and the 4-line stack (H-296..H-72). Root-level LOWER_LEFT iconType.
LOAD_SCRIM = (1600, 760, 0.58, 0.50)
LOAD_SCRIM_POS = (-120, -576)       # centre at (680, H - 196)


def build_loading_bar(filled):
    """LOAD_BAR px: loading_progress_full.dds (keyer blue, solid, no tail: it would only show at 100 %) and
    loading_progress_empty.dds (a faint D track). gfx/FX/progress.lua shows texture 1 left of the progress and
    texture 2 right of it, UVs unchanged, so neither is stretched."""
    return Image.new("RGBA", LOAD_BAR, (KEY_BLUE + (255,)) if filled else LOAD_TRACK)


def load_geometry(sh):
    """Screen y of the loading screen's bottom stack for a screen sh px tall (the .gui offsets are these minus sh)."""
    bar_top = sh - LOAD_BAR_BOTTOM - LOAD_BAR[1]                    # H-78
    status_top = bar_top - LOAD_BAR_GAP - 7 * SMALL_CELL            # H-104
    strap_base = status_top - LOAD_STATUS_GAP                       # H-136
    box_bottom = strap_base - 7 * CAP_CELL + QUOTE_LINE             # H-120
    box_top = box_bottom - QUOTE_LINES * QUOTE_LINE                 # H-296
    return dict(bar_top=bar_top, status_top=status_top, strap_base=strap_base, box_top=box_top,
                box_bottom=box_bottom)


# Scenario picker (interface/frontendgamesetupview.gui, gamesetup_scenario_window: full screen, transparent). The
# main menu's title block (logo + date) stays on screen, so this screen repeats neither the title nor the date. It
# adds one inset in the lower right corner (LOWER_RIGHT), its right edge on the title-safe edge W - 192 and its bottom
# on the menu's last plate bottom (H - 72): the still with a flat near-black text board flush under it, in its own
# soft scrim; and two captions in the menu's rows (Select, Back). The UI does not scale with the screen, so the inset
# is sized for 1280x720: its left edge (W - 704 = 576 there) stays right of the logo's "OF THE" line (glyphs to x 542)
# and its top (H - 488 = 232) below the "TWILIGHT" line (y 108..178); from 1366x768 up it clears the whole logo box.
SCEN_PIC = (512, 288)                   # still = bookmark entry; column right edge at W - 192
SCEN_BOARD_PAD = 14                     # board edge -> body text box, top and bottom
SCEN_BODY_LINES = 7                     # body box capacity in lines (in game RU wraps to 6 at 468 px; centred)
SCEN_BODY_LH = 20                       # totu_body (vanilla hoi_20b) lineHeight
SCEN_BOARD = (512, SCEN_BOARD_PAD + SCEN_BODY_LINES * SCEN_BODY_LH + SCEN_BOARD_PAD, 0.82, (7, 9, 14))  # w, h, a, rgb
SCEN_COL_H = SCEN_PIC[1] + SCEN_BOARD[1]    # 416: picture + board, one inset
SCEN_SCRIM_MARGIN = (240, 260)          # the column's soft burn: column + this margin on every side
SCEN_SCRIM = (SCEN_PIC[0] + 2 * SCEN_SCRIM_MARGIN[0], SCEN_COL_H + 2 * SCEN_SCRIM_MARGIN[1], 0.55, 0.30)
SCEN_TEXT_IN = 22                       # body text 22 px in from both board edges (= PAD_L): 468 px wide
SCENARIO_ITEMS = [("Выбрать", "Select"), ("Назад", "Back")]
# The still: the August 1991 tank column only (the tanks_red_square source, below St Basil's gallery, right of the
# crowd, left of GUM): no landmark, season or public figure. Graded on the menu's kinescope ramp, held well under the
# caption white (peak 178 luma), greens/cyans/blues greyed so the keyer blue stays the only saturated colour.
STILL_SRC = SRC / "loading" / "tanks_red_square.webp"
STILL_CROP = (560, 690, 1513, 1226)
STILL_RAMP = [(0.0, (8, 12, 18)), (0.25, (34, 41, 55)), (0.5, (80, 86, 104)), (0.72, (126, 122, 140)),
              (0.88, (156, 148, 164)), (1.0, (178, 170, 184))]
STILL_BLACK = 0.03                      # source luma mapped to 0
STILL_PEAK = 178                        # the photo share is scaled to the ramp's top
STILL_TINT = 0.72                       # share of the ramp; the rest is the photo at STILL_SAT saturation
STILL_SAT = 0.40


def build_scenario_still(src=STILL_SRC, crop=STILL_CROP):
    """SCEN_PIC RGB (select_date_1990.dds, GFX_select_date_1990): luma kept, colour pulled toward STILL_RAMP, hues
    90..270 held to 12 % saturation, colour-only SECAM pass, fine grain. No band, scanlines, vignette or border."""
    w, h = SCEN_PIC
    img = cover(Image.open(src).convert("RGB").crop(crop), w, h)
    a = np.asarray(img, np.float32) / 255
    lum0 = a @ np.array([0.299, 0.587, 0.114], np.float32)
    L = np.clip((lum0 - STILL_BLACK) / (0.97 - STILL_BLACK), 0, 1)
    tint = lerp_stops(L, STILL_RAMP) / 255
    grey = lum0[..., None]
    orig = (grey + (a - grey) * STILL_SAT) * (L / np.maximum(lum0, 1e-3))[..., None] * (STILL_PEAK / 255)
    out = tint * STILL_TINT + np.clip(orig, 0, 1) * (1 - STILL_TINT)
    img = Image.fromarray(np.clip(out * 255, 0, 255).astype(np.uint8))
    hsv = np.asarray(img.convert("HSV"), np.float32)
    hue = hsv[..., 0] * 360 / 255
    cold = (hue > 90) & (hue < 270)
    hsv[..., 1] = np.where(cold, np.minimum(hsv[..., 1], 0.12 * 255), hsv[..., 1])
    img = secam(Image.fromarray(hsv.astype(np.uint8), "HSV").convert("RGB"))
    n = np.random.default_rng(7).normal(0, 2.4, (h, w, 1)).astype(np.float32)
    return Image.fromarray(np.clip(np.asarray(img, np.float32) + n, 0, 255).astype(np.uint8))


def build_bookmark_entry():
    """bookmark_entry.dds (GFX_bookmark_entry_bg): 2 frames of SCEN_PIC, fully transparent. The engine needs the
    entry's background to click (it selects the bookmark), but nothing marks a selection: there is one scenario, and
    keyer blue means 'under the cursor' only."""
    return Image.new("RGBA", (SCEN_PIC[0] * 2, SCEN_PIC[1]), (0, 0, 0, 0))


def build_scenario_board():
    """scenario_bg.dds (GFX_select_date_bg): the text board, flat near-black, no border, no gradient."""
    w, h, a, rgb = SCEN_BOARD
    return Image.new("RGBA", (w, h), rgb + (round(255 * a),))


# Country selection (gamesetup_interesting_countries_window, 1225x717, centred), window px at UI scale 1.0; the .gui
# positions come from these numbers. One opaque near-black board (no border, no dividers, no panels) with the two
# banners full-bleed in its top band, dissolving toward the major cards; a soft scrim around the window dims the map.
# The title caption sits above the board on the scrim. Selection = an 8 px keyer bar under the selected flag; the
# caption plates (hover / action) are the main menu's.
CS_W, CS_H = 1225, 717
CS_BOARD = (14, 41, 1211, 712)          # x0, y0, x1, y1 (exclusive)
CS_BOARD_RGB = (9, 11, 16)              # the backgrounds' cold lifted black
CS_BOARD_ALPHA = 1.0                    # opaque: the scrim does the transition, no map labels ghost behind the text
CS_TOP = (41, 318)                      # top and bottom y of the banner band
CS_ART_LEFT = (14, 452)                 # USA banner x range
CS_ART_RIGHT = (772, 1211)              # SOV banner x range
CS_ART_FADE = 170                       # a banner's inner edge dissolves into the board over this many px
CS_BANNER_GRADE = dict(sat=0.45, bright=0.95, contrast=1.08, shadow=(5, 10, 16), highlight=(222, 202, 216), mix=0.40)
SOVIET_RED = (204, 0, 0)                # plain red base of the USSR banner (no glyphs under the photos)
USA_PORTRAIT = "USA_george_bush"        # tools/src/portraits/<this>.(jpg|png|webp): George H. W. Bush, official portrait
USA_PORTRAIT_BARS = None                # optional eye bar, ((x1, y1), (x2, y2), thickness) in source px
# Eye bars are a loading-screen rule; the country-selection banners show the leaders unbarred (approved by the user).
SOV_PORTRAIT_BARS = None
SCRIM_COUNTRY = (1000, 562, 0.70, 0.40)     # drawn at iconType scale 4 (4000x2248), centred on the window
CS_BAR_H = 8                            # selection bar under the flag
MAJOR_W, MAJOR_H = 220, 274             # countries grid slot; two cards centred on the board axis x 612
MAJOR_FLAG_POS = (69, 104)              # country_flag (82x52), centred in the card
MAJOR_BAR = (69, 164)                   # selection bar: 82 solid (= flag width) + 12 tail
MAJOR_NAME = (12, 180, 196, 56)         # country_name: x, y, maxWidth, maxHeight (3 lines of 18), centred on x 110
MINOR_W, MINOR_H = 138, 97              # countries_medium entry; flag 82x52 at 26,22
MINOR_BAR = (26, 82)
MINI_W, MINI_H = 59, 44                 # countries_mini entry; flag 41x26 at 9,8
MINI_BAR = (9, 38)                      # the minor bar at half scale (4 px, 3 + 3 px tail)
FILTER_W, FILTER_H = 149, 34            # country_filter (off-screen in this mod)
COUNTRY_ITEMS = [("Выбрать", "Select"), ("Назад", "Back")]


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


def smoothstep(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


def build_banner(flag, layers, w, h, inner_side, bright=0.62):
    """RGBA banner. layers: [(photo, crop, x, width, strength[, flatten[, bars]])]; each photo is cover-fitted into
    x..x+width and carried by the flag colours. flatten (0..1) evens out a busy flag under the photo (stripes would
    cut through a face); bars: eye bars drawn on the source before the crop (eye_bar, source px). Finish: the cold, low-saturation CS_BANNER_GRADE, colour-only SECAM pass and fine luma grain
    like the backgrounds; the inner edge (toward the major cards) dissolves into the board through alpha over
    CS_ART_FADE px. Top and bottom edges stay hard."""
    base = ImageEnhance.Brightness(ImageEnhance.Color(cover(flag, w, h)).enhance(0.8)).enhance(bright)
    for layer in layers:
        src, crop, x, lw, strength = layer[:5]
        flatten = layer[5] if len(layer) > 5 else 0.0
        ph = Image.open(src).convert("RGB")
        for start, end, thick in ((layer[6] or []) if len(layer) > 6 else []):
            eye_bar(ph, start, end, thick)
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
    base = secam(tone(base, **CS_BANNER_GRADE))
    n = np.random.default_rng(w).normal(0, 2.2, (h, w, 1)).astype(np.float32)
    out = Image.fromarray(np.clip(np.asarray(base, np.float32) + n, 0, 255).astype(np.uint8)).convert("RGBA")
    x = np.arange(w, dtype=np.float32)
    d = (w - 1 - x) if inner_side == "right" else x
    alpha = np.tile(smoothstep(d / CS_ART_FADE) ** 1.2, (h, 1))
    out.putalpha(Image.fromarray((alpha * 255).astype(np.uint8)))
    return out


def usa_banner_layers(lw):
    """The Abrams photo (Abrams_in_formation.jpg, Wikimedia Commons, US Navy, public domain; crop tuned for it) and the
    president's portrait (tools/src/portraits/USA_PORTRAIT.*) on the outer (left) edge, mirroring the Soviet banner;
    without the portrait the Abrams spreads across the whole banner."""
    banners = SRC / "banners"
    army = next(iter(sorted(banners.glob("usa_army.*"))), None) if banners.exists() else None
    portrait = next(iter(sorted((SRC / "portraits").glob(f"{USA_PORTRAIT}.*"))), None)
    layers = []
    if portrait:
        if army:
            layers.append((army, (600, 450, 2220, 1810), 130, 330, 0.9, 0.4))
        layers.append((portrait, (200, 140, 1400, 1700), 0, 220, 0.95, 0.7, USA_PORTRAIT_BARS))
    elif army:
        layers.append((army, (600, 450, 2220, 1810), 0, lw - 1, 0.9, 0.4))
    return layers


def build_country_select_bg():
    """country_select_bg.dds (GFX_country_selection_bg), CS_W x CS_H RGBA: transparent except CS_BOARD, filled with
    CS_BOARD_RGB; the USA banner (flag reversed, canton toward the centre as on a right-sleeve patch) and the USSR
    banner (plain red base) in its top band, composited over the board colour."""
    img = Image.new("RGBA", (CS_W, CS_H), (0, 0, 0, 0))
    x0, y0, x1, y1 = CS_BOARD
    img.paste(CS_BOARD_RGB + (round(255 * CS_BOARD_ALPHA),), (x0, y0, x1, y1))
    top, bottom = CS_TOP
    h = bottom - top
    lw = CS_ART_LEFT[1] - CS_ART_LEFT[0]
    rw = CS_ART_RIGHT[1] - CS_ART_RIGHT[0]
    left = build_banner(us_flag(lw, h).transpose(Image.FLIP_LEFT_RIGHT), usa_banner_layers(lw), lw, h,
                        inner_side="right", bright=0.5)
    right = build_banner(Image.new("RGB", (rw, h), SOVIET_RED), [
        (SRC / "loading" / "tanks_red_square.webp", None, 0, 300, 0.9),
        (SRC / "portraits" / "SOV_mikhail_gorbachev.webp", (200, 150, 1300, 1500), rw - 210, 210, 0.95, 0.0,
         SOV_PORTRAIT_BARS),
    ], rw, h, inner_side="left")
    for art, x in ((left, CS_ART_LEFT[0]), (right, CS_ART_RIGHT[0])):
        under = np.asarray(img.crop((x, top, x + art.width, bottom)))[..., 3].astype(np.float32) / 255
        solid = Image.new("RGBA", art.size, CS_BOARD_RGB + (255,))
        solid.alpha_composite(art)
        a_art = np.asarray(art)[..., 3].astype(np.float32) / 255
        solid.putalpha(Image.fromarray(np.round((a_art + under * (1 - a_art)) * 255).astype(np.uint8)))
        img.paste(solid, (x, top))
    return img


def keyer_strip(solid_w, h, colour=None, steps=(6, 6)):
    """The keyer colour as a bar: solid_w px solid, then the hard two-step tail (steps px at TAIL_ALPHA)."""
    colour = colour or KEY_BLUE
    img = Image.new("RGBA", (solid_w + sum(steps), h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, solid_w - 1, h - 1), fill=colour + (255,))
    x = solid_w
    for s, a in zip(steps, TAIL_ALPHA):
        d.rectangle((x, 0, x + s - 1, h - 1), fill=colour + (a,))
        x += s
    return img


def selection_frames(fw, fh, bar, pos):
    """2 frames of fw x fh: normal fully transparent, selected = the keyer bar at pos. The flag (drawn by the engine
    under this sprite) and everything else stay transparent."""
    img = Image.new("RGBA", (fw * 2, fh), (0, 0, 0, 0))
    img.alpha_composite(bar, (fw + pos[0], pos[1]))
    return img


def build_major_entry():
    """country_entry_major.dds (GFX_country_selection_entry): bar solid x69..150 (= flag), tail x151..162, y164..171."""
    return selection_frames(MAJOR_W, MAJOR_H, keyer_strip(82, CS_BAR_H), MAJOR_BAR)


def build_minor_entry():
    """country_entry_minor.dds (GFX_country_selection_minor_entry): bar solid x26..107, tail x108..119, y82..89."""
    return selection_frames(MINOR_W, MINOR_H, keyer_strip(82, CS_BAR_H), MINOR_BAR)


def build_mini_entry():
    """country_entry_mini.dds (GFX_mini_country_selector): the minor bar at half scale, solid x9..49 (= the 41 px
    flag), tail 3 + 3 px x50..55, y38..41."""
    return selection_frames(MINI_W, MINI_H, keyer_strip(41, CS_BAR_H // 2, steps=(3, 3)), MINI_BAR)


def build_filter():
    """country_filter.dds (GFX_country_filter_entry, off-screen in this mod): selected = a keyer plate."""
    return selection_frames(FILTER_W, FILTER_H, keyer_strip(FILTER_W - TAIL, FILTER_H), (0, 0))


def minor_portrait_overlay():
    """minor_portrait_overlay.dds, 126x166, fully transparent (the element is off-screen, the sprite must exist)."""
    return Image.new("RGBA", (126, 166), (0, 0, 0, 0))


# Leader portraits (in-game character portraits, shown in the lobby's country details too): gfx/leaders/totu/<out>.dds,
# 156x210, from tools/src/portraits/<source>.(webp|jpg|png). out: (source, crop around head and shoulders or None).
PORTRAITS = {
    "SOV_mikhail_gorbachev": ("SOV_mikhail_gorbachev", (330, 140, 1250, 1378)),
    "USA_george_bush": ("USA_george_bush", (250, 180, 1350, 1660)),   # official portrait (Valdez, 1989), public domain
    "SOV_gennady_yanayev": ("SOV_gennady_yanayev", (90, 60, 934, 1196)),   # generated source (no free photo)
    # GDR: Bundesarchiv photos on Wikimedia Commons, CC BY-SA 3.0 DE (Bild 183-1989-1117-431 cropped; "Maziere.jpg"
    # from Bild 183-1990-08..; Bild 183-1990-0222-016 crop)
    "DDR_hans_modrow": ("DDR_hans_modrow", (60, 0, 515, 612)),
    "DDR_lothar_de_maiziere": ("DDR_lothar_de_maiziere", (40, 10, 383, 472)),
    "DDR_ibrahim_boehme": ("DDR_ibrahim_boehme", (0, 10, 263, 364)),
    # FRG: "Helmut Kohl (1989).jpg", Lothar Schaack, Wikimedia Commons, CC BY-SA 3.0 DE
    "GER_helmut_kohl": ("GER_helmut_kohl", (20, 0, 362, 460)),
}


def build_portrait_placeholder():
    """156x210 head-and-shoulders silhouette on the portraits' dark ground, finished like build_portrait."""
    img = Image.new("RGB", (156, 210), (70, 66, 64))
    d = ImageDraw.Draw(img)
    d.ellipse((46, 38, 110, 120), fill=(34, 32, 31))
    d.rounded_rectangle((10, 128, 146, 260), radius=48, fill=(34, 32, 31))
    return finish_portrait(img.filter(ImageFilter.GaussianBlur(2)))


def build_portrait(src, crop):
    img = Image.open(src).convert("RGB")
    img = cover(img.crop(crop) if crop else img, 156, 210)
    return finish_portrait(img)


def finish_portrait(img):
    img = tone(img, sat=0.8, bright=0.82, contrast=1.1, shadow=(14, 11, 9), highlight=(236, 196, 150), mix=0.28)
    img = Image.composite(Image.new("RGB", img.size, (10, 8, 7)), img,
                          radial_mask(156, 210, inner=0.5, outer=1.2).point(lambda v: v * 0.7))
    img = scanlines(img, period=2, strength=0.07)
    return grain(img, amount=6, seed=21)


# National spirit and focus icons are generated by tools/gen_icons.py.


# Main menu UI ("broadcast", interface/frontendmainview.gui), screen px at UI scale 1.0. The .gui positions are
# derived from these numbers; change both together.
KEY_BLUE = (30, 62, 168)            # keyer plate (hover): the one saturated colour on screen
KEY_BLUE_DOWN = (17, 38, 108)       # pressed
CAPTION_WHITE = (246, 242, 234)     # colour code P of the caption fonts (interface/totu_fonts.gfx) = logo glyph white
CAPTION_DIM = (172, 180, 196)       # code D: engine version line; no darker (4.5:1 in its worst 10 % at 1080p)
SAFE_X, SAFE_Y = 192, 108           # title-safe text edge: logo glyphs, date line, captions
CAP_CELL, SMALL_CELL = 4, 2         # totu_caption: 20x28 glyphs, advance 24; totu_caption_small: 10x14, advance 12
PLATE_H, PLATE_PITCH = 40, 44
PLATE_BOTTOM, QUIT_GAP = 72, 20     # last plate ends 72 px above the screen bottom; Quit / Back set 20 px apart
PAD_L, PAD_R, TAIL = 22, 10, 12     # label text box starts PAD_L into the plate (at SAFE_X); the plate fits the
                                    # longer of the RU / EN label with PAD_R + TAIL after it (PAD_L == PAD_R + TAIL)
TAIL_ALPHA = (153, 77)              # hard two-step colour tail: 6 px at 60 %, then 6 px at 30 %
CAPTION_SHADOW = 2                  # drop edge: a black (code K) copy of every caption text box at +2,+2
CHANGELOG_GAP = 24                  # bottom right: the changelog box sits this far above the version line's box
TEXT_TRAIL = SMALL_CELL             # right-aligned boxes end this far right of the ink (the width counts the gap
                                    # after the last glyph): box right edge at screen width - SAFE_X + TEXT_TRAIL
# Scrims: (w, h, centre alpha, plateau radius) and their .gui positions (title: UPPER_LEFT, menu: LOWER_LEFT)
SCRIM_TITLE = (1100, 640, 0.58 * 0.85, 0.30)
SCRIM_MENU = (1180, 640, 0.58, 0.36)
SCRIM_TITLE_POS = (-123, -67)
SCRIM_MENU_POS = (-222, -500)
# (RU, EN) labels. A plate fits the longer one: HOI4 cannot switch sprites per language.
MENU_ITEMS = [("Одиночная игра", "Single Player"), ("Сетевая игра", "Multiplayer"), ("Настройки", "Options"),
              ("Авторы", "Credits"), ("Выход", "Quit")]
SUBMENU_ITEMS = [("Продолжить", "Continue"), ("Новая игра", "New Game"), ("Загрузить", "Load Game"),
                 ("Назад", "Back")]
CAPTION_PLATES = (376, 328, 280, 256, 208, 160)     # GFX_totu_caption_<w> (interface/totu_menu.gfx)

# Lobby frame (interface/frontendgamesetupview.gui: frontendgamesetupview > top / bottom, gamesetup_country_details,
# the gameplay / multiplayer settings, the load and ironman-save windows, the "updating history" line), screen px at
# UI scale 1.0. The map stays the picture; on it only what a broadcast frame carries: a soft black band along the top
# and the bottom edge (no rule, no rivets), captions on the menu's title-safe edges (x 192 and W - 192), the keyer
# plate for hover / selection, and flat near-black boards without a border where a block of information needs a
# surface. Button text is drawn by the engine (buttonText) in the K-edged button fonts of tools/build_fonts.py,
# because the engine shows and hides some of these buttons (Start / Ready, Load, Observer): a separate label box
# would stay behind on its own.
SMALL_PLATE_H = 24                  # small caption plates: totu_button_small, capitals 14 px, 5 px above and below
SMALL_PAD_L, SMALL_PAD_R, SMALL_TAIL = 12, 6, 6     # PAD_L == PAD_R + TAIL, as on the big plates
SMALL_PLATE_X = SAFE_X - SMALL_PAD_L                # 180: small plates whose text starts at x 192
BAND_H = 160                        # top / bottom band height (the containers' height)
BAND_ALPHA, BAND_HOLD = 0.62, 40    # band alpha at the screen edge, held for BAND_HOLD px, then a smoothstep to 0
BOARD_ALPHA = 0.84                  # flat near-black info board (CS_BOARD_RGB): container backgrounds, stretched
CHECK = 20                          # checkbox square (ironman, historical, co-op, hotjoin, ready)
CHIP_W = 110                        # difficulty chips: five side by side, 2 frames (off: transparent, on: keyer)
TAB_W = 118                         # load window tabs (Local / Cloud), 3 frames (off / on / disabled)
FIELD = (376, 32, 0.14)             # ironman save name field: w, h, alpha of CAPTION_DIM
# (RU, EN) labels of the lobby's small caption buttons; the plate fits the longer one (RU is never shorter, so the
# Russian label lands on x 192 when the engine centres it)
SMALL_ITEMS = [("Интересные страны", "Notable countries"), ("Случайная страна", "Random country"),
               ("Наблюдатель", "Observer"), ("Сведения", "Details"), ("Правила игры", "Game rules")]
SMALL_PLATES = (226, 214, 166, 154, 118)            # GFX_totu_caption_small_<w> (interface/totu_menu.gfx)
# Big caption buttons of the bottom band (the menu's plates): Back, Load, Options on the menu's last row from x 170;
# Start / Ready right-aligned to W - 192
LOBBY_ITEMS = [("Назад", "Back"), ("Загрузить", "Load Game"), ("Настройки", "Options"), ("Старт", "Start"),
               ("Готов", "Ready")]
# Preview text only; the game takes these from localisation and the engine
DATE_LINE = "1 января 1990"
CHANGELOG = "Версия 0.1: карта 1990 года, новое меню"
ENGINE_VERSION = "Operation Postern v1.19.3.0.c01a (5632)"     # the launcher's string, written by the engine


def pixel_text_w(text, cell):
    """Width of one line in the 5x7 caption font: 5 cells + 1 gap per glyph, no trailing gap."""
    return len(text) * 6 * cell - cell


def caption_plate_w(item):
    return PAD_L + max(pixel_text_w(label, CAP_CELL) for label in item) + PAD_R + TAIL


def small_plate_w(item):
    return SMALL_PAD_L + max(pixel_text_w(label, SMALL_CELL) for label in item) + SMALL_PAD_R + SMALL_TAIL


def build_scrim(w, h, a0, plateau):
    """Shapeless dark burn behind the title or the menu: black, elliptical, alpha a0 inside `plateau`, then a
    smoothstep to 0 at the ellipse edge. Computed at quarter size and upscaled, so it has no visible edge."""
    sw, sh = w // 4, h // 4
    yy, xx = np.mgrid[0:sh, 0:sw].astype(np.float32)
    r = np.sqrt(((xx + 0.5) / sw - 0.5) ** 2 / 0.25 + ((yy + 0.5) / sh - 0.5) ** 2 / 0.25)
    t = np.clip((r - plateau) / (1 - plateau), 0, 1)
    alpha = a0 * (1 - t * t * (3 - 2 * t))
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    img.putalpha(Image.fromarray((alpha * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC))
    return img


def build_caption_plate(w, h=PLATE_H, tail=TAIL, frames=(None, KEY_BLUE, KEY_BLUE_DOWN)):
    """w x h frames side by side; each frame transparent (None) or a plate of that colour. The default is the menu's
    button: normal (transparent), hover (keyer blue), pressed (darker). The plate ends in a hard-stepped colour tail
    (tail px, two steps at TAIL_ALPHA), like a band-limited chroma edge."""
    img = Image.new("RGBA", (w * len(frames), h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    solid = w - tail
    step = tail // len(TAIL_ALPHA)
    for i, col in enumerate(frames):
        if col is None:
            continue
        x0 = i * w
        d.rectangle((x0, 0, x0 + solid - 1, h - 1), fill=col + (255,))
        for k, a in enumerate(TAIL_ALPHA):
            d.rectangle((x0 + solid + k * step, 0, x0 + solid + (k + 1) * step - 1, h - 1), fill=col + (a,))
    return img


def build_small_plate(w, frames=(None, KEY_BLUE, KEY_BLUE_DOWN)):
    """A small caption plate (SMALL_PLATE_H, 3 + 3 px tail): buttons of the lobby frame (3 frames), difficulty chips
    (2 frames: off, on), load window tabs (3 frames: off, on, disabled)."""
    return build_caption_plate(w, SMALL_PLATE_H, SMALL_TAIL, frames)


def build_band(top):
    """16 x BAND_H, black: alpha BAND_ALPHA at the screen edge for BAND_HOLD px, then a smoothstep to 0. Tiled
    across the top / bottom container (corneredTileSpriteType, no border), so it reaches every screen width."""
    y = np.arange(BAND_H, dtype=np.float32)
    d = y if top else BAND_H - 1 - y                                    # distance from the screen edge
    t = np.clip((d - BAND_HOLD) / (BAND_H - BAND_HOLD), 0, 1)
    alpha = BAND_ALPHA * (1 - t * t * (3 - 2 * t))
    img = Image.new("RGBA", (16, BAND_H), (0, 0, 0, 0))
    img.putalpha(Image.fromarray(np.tile((alpha * 255).round().astype(np.uint8)[:, None], (1, 16))))
    return img


def build_board_tile():
    """16 x 16 flat near-black (CS_BOARD_RGB at BOARD_ALPHA), stretched over a container (GFX_totu_board)."""
    return Image.new("RGBA", (16, 16), CS_BOARD_RGB + (round(255 * BOARD_ALPHA),))


def build_checkbox():
    """2 frames of CHECK x CHECK, no border: off = a flat square of CAPTION_DIM at 30 %, on = keyer blue."""
    img = Image.new("RGBA", (CHECK * 2, CHECK), (0, 0, 0, 0))
    img.paste(CAPTION_DIM + (77,), (0, 0, CHECK, CHECK))
    img.paste(KEY_BLUE + (255,), (CHECK, 0, 2 * CHECK, CHECK))
    return img


def build_field():
    """The ironman save name field (an editBox has no background of its own): flat CAPTION_DIM at FIELD alpha."""
    w, h, a = FIELD
    return Image.new("RGBA", (w, h), CAPTION_DIM + (round(255 * a),))


def caption_fonts():
    """(totu_caption, totu_caption_small) as built into gfx/fonts by tools/build_fonts.py (run that first), so the
    previews show the glyphs the engine gets. Imported here because build_fonts imports this module."""
    from build_fonts import load_font
    big, small = load_font("totu_caption"), load_font("totu_caption_small")
    for (common, _, _), cell in ((big, CAP_CELL), (small, SMALL_CELL)):
        assert common["base"] == 7 * cell, "the .gui caption boxes assume the capitals start at the line top"
    return big, small


def draw_caption(img, font, text, x, y, colour=CAPTION_WHITE, right=False, edge=True):
    """One caption text box as interface/frontendmainview.gui has it: top-aligned, line top (= top of the capitals)
    at y, text from x; right=True: x is the box's right edge and the text ends there by the sum of the advances, like
    format = right. edge: the black drop-edge copy at +CAPTION_SHADOW underneath."""
    from build_fonts import draw_text
    if right:
        x -= sum(font[1][ord(ch)]["xadvance"] for ch in text)
    if edge:
        draw_text(img, font, text, x + CAPTION_SHADOW, y + CAPTION_SHADOW, (0, 0, 0))
    draw_text(img, font, text, x, y, colour)


def menu_rows(n):
    """Plate tops relative to the screen bottom (LOWER_LEFT); the last item (Quit / Back) set apart."""
    ys = [-PLATE_BOTTOM - PLATE_H]
    for k in range(n - 2, -1, -1):
        ys.insert(0, ys[0] - PLATE_PITCH - (QUIT_GAP if k == n - 2 else 0))
    return ys


def build_preview(bg, logo, scrims, plates, sw=2560, sh=1440, items=MENU_ITEMS, hovered=0):
    """Screen-size composite of the main menu (Russian labels) from the built textures and caption fonts, laid out
    like interface/frontendmainview.gui, to eyeball without launching the game."""
    big, small = caption_fonts()
    shot = cover(bg, sw, sh).convert("RGBA")
    shot.alpha_composite(scrims["title"], SCRIM_TITLE_POS)
    shot.alpha_composite(scrims["menu"], (SCRIM_MENU_POS[0], sh + SCRIM_MENU_POS[1]))
    ys = menu_rows(len(items))
    for i, (item, y) in enumerate(zip(items, ys)):
        w, frame = caption_plate_w(item), 1 if i == hovered else 0
        shot.alpha_composite(plates[w].crop((frame * w, 0, (frame + 1) * w, PLATE_H)), (SAFE_X - PAD_L, sh + y))
    shot.alpha_composite(logo, (SAFE_X - LOGO_PAD, SAFE_Y - LOGO_PAD))
    draw_caption(shot, small, DATE_LINE, SAFE_X, SAFE_Y + logo.height - 2 * LOGO_PAD + 3 * LOGO_CELL)
    text_dy = (PLATE_H - 7 * CAP_CELL) // 2                 # label box: capitals centred in the plate
    for (ru, _), y in zip(items, ys):
        draw_caption(shot, big, ru, SAFE_X, sh + y + text_dy)
    # bottom right: changelog above the engine version line, whose capitals end on the Quit / Back baseline
    version_top = sh + ys[-1] + text_dy + 7 * CAP_CELL - 7 * SMALL_CELL
    right = sw - SAFE_X + TEXT_TRAIL
    draw_caption(shot, small, CHANGELOG, right, version_top - CHANGELOG_GAP, right=True)
    draw_caption(shot, small, ENGINE_VERSION, right, version_top, CAPTION_DIM, right=True, edge=False)
    return shot


def build_parts_sheet(scrims, plates):
    """The caption plates as stored (three frames each, on grey so frame 1 shows as empty), a 4x zoom of one
    tail, and both scrims at half size over a light grey."""
    _, small = caption_fonts()
    grey = (128, 128, 128, 255)
    sheet = Image.new("RGBA", (1400, 1000), (24, 24, 24, 255))
    y = 24
    for w in CAPTION_PLATES:
        sheet.paste(grey, (100, y - 4, 100 + w * 3, y + PLATE_H + 4))
        sheet.alpha_composite(plates[w], (100, y))
        draw_caption(sheet, small, str(w), 24, y + 13, edge=False)
        y += PLATE_H + 16
    w = CAPTION_PLATES[0]
    zoom = plates[w].crop((2 * w - 24, 0, 2 * w + 16, PLATE_H)).resize((160, PLATE_H * 4), Image.NEAREST)
    sheet.paste(grey, (100, y, 100 + 160, y + PLATE_H * 4))
    sheet.alpha_composite(zoom, (100, y))
    y += PLATE_H * 4 + 24
    x, bottom = 24, y
    for name in ("title", "menu"):
        s = scrims[name].resize((scrims[name].width // 2, scrims[name].height // 2), Image.LANCZOS)
        sheet.paste((200, 200, 200, 255), (x, y, x + s.width, y + s.height))
        sheet.alpha_composite(s, (x, y))
        x, bottom = x + s.width + 24, max(bottom, y + s.height + 24)
    return sheet.crop((0, 0, sheet.width, bottom))


CAPTION_COLOURS = {"P": CAPTION_WHITE, "D": CAPTION_DIM, "K": (0, 0, 0)}     # textcolors of the caption fonts


def loc_value(lang, key, name=None):
    """A value from localisation/<lang>/<name or totu_menu_l_<lang>.yml> as written (\\n not expanded)."""
    path = ROOT / "localisation" / lang / (name or f"totu_menu_l_{lang}.yml")
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line.startswith(key + ":"):
            return line.split('"', 1)[1].rsplit('"', 1)[0]
    raise KeyError(f"{key} in {path.name}")


def colour_runs(text, default):
    """'§X ... §!' colour codes -> [(char, colour)], like the engine's text box (codes of the caption fonts)."""
    out, stack, i = [], [default], 0
    while i < len(text):
        if text[i] == "§" and i + 1 < len(text):
            stack = stack[:1] if text[i + 1] == "!" else stack + [CAPTION_COLOURS[text[i + 1]]]
            i += 2
            continue
        out.append((text[i], stack[-1]))
        i += 1
    return out


def wrap_runs(font, text, max_w, default=CAPTION_WHITE):
    """Greedy word wrap at spaces like the engine; '\\n' forces a break. Returns lines of (char, colour)."""
    adv = font[1]
    lines = []
    for para in text.split("\n"):
        line, word, w_line, w_word = [], [], 0, 0
        for ch, col in colour_runs(para, default) + [(" ", default)]:
            if ch == " ":
                if line and w_line + adv[32]["xadvance"] + w_word > max_w:
                    lines.append(line)
                    line, w_line = list(word), w_word
                else:
                    if line:
                        line.append((" ", col))
                        w_line += adv[32]["xadvance"]
                    line += word
                    w_line += w_word
                word, w_word = [], 0
            else:
                word.append((ch, col))
                w_word += adv[ord(ch)]["xadvance"]
        lines.append(line)
    return lines


def draw_runs(img, font, line, x, y):
    from build_fonts import draw_text
    for ch, col in line:
        x = draw_text(img, font, ch, x, y, col)
    return x


def build_loading_preview(sw=2560, sh=1440, picture="tanks_red_square", tip=8, progress=0.62):
    """Screen-size composite of the loading screen from the built DDS and the built loading fonts (Russian tip and
    status), laid out like interface/load_screen.gui (LOAD_* and QUOTE_* constants)."""
    from build_fonts import load_font
    if not (ROOT / "gfx/fonts/totu_caption_quote.fnt").exists():
        raise SystemExit("run tools/build_fonts.py first: gfx/fonts/totu_caption_quote.fnt is missing")
    quote, small_k = load_font("totu_caption_quote"), load_font("totu_caption_small_k")
    tex = lambda rel: Image.open(ROOT / rel).convert("RGBA")       # noqa: E731
    geo = load_geometry(sh)
    shot = cover(tex(f"gfx/loadingscreens/totu_load_{picture}.dds").convert("RGB"), sw, sh).convert("RGBA")
    shot.alpha_composite(tex("gfx/interface/totu/scrim_title.dds"), SCRIM_TITLE_POS)
    shot.alpha_composite(tex("gfx/interface/totu/scrim_caption.dds"), (LOAD_SCRIM_POS[0], sh + LOAD_SCRIM_POS[1]))
    bar = tex("gfx/interface/totu/loading_progress_empty.dds")
    filled = round(LOAD_BAR[0] * progress)
    bar.paste(tex("gfx/interface/totu/loading_progress_full.dds").crop((0, 0, filled, LOAD_BAR[1])), (0, 0))
    shot.alpha_composite(bar, (SAFE_X, geo["bar_top"]))
    shot.alpha_composite(tex("gfx/interface/totu/menu_logo.dds"), (SAFE_X - LOGO_PAD, SAFE_Y - LOGO_PAD))
    text = loc_value("russian", f"LOADING_TIP_{tip}", "loading_tips_l_russian.yml").replace("\\n", "\n")
    lines = wrap_runs(quote, text, QUOTE_BOX_W)
    assert len(lines) <= QUOTE_LINES, f"LOADING_TIP_{tip}: {len(lines)} lines"
    first = geo["box_bottom"] - QUOTE_LINE * len(lines)                 # vertical_alignment = bottom
    for i, line in enumerate(lines):
        draw_runs(shot, quote, line, SAFE_X, first + i * QUOTE_LINE)
    draw_runs(shot, small_k, colour_runs("Загрузка исторических данных", CAPTION_WHITE), SAFE_X, geo["status_top"])
    return shot


def load_vanilla_font(names):
    """A vanilla bitmapfont from GAME/gfx/fonts as (common, chars): each char keeps its own atlas; later files only add
    glyphs, as fontfiles do. None if the game folder is missing."""
    from build_fonts import read_fnt
    if not (GAME / "gfx" / "fonts" / f"{names[0]}.fnt").exists():
        return None
    common, chars = None, {}
    for name in names:
        c, ch = read_fnt(GAME / "gfx" / "fonts" / f"{name}.fnt")
        atlas = Image.open(GAME / "gfx" / "fonts" / f"{name}.dds").convert("RGBA")
        common = common or c
        for cp, v in ch.items():
            chars.setdefault(cp, dict(v, atlas=atlas))
    return common, chars


def draw_vanilla_box(img, font, text, x, y, max_w, box_h, colour):
    """Engine-like text box in a vanilla font: greedy word wrap at max_w, lines lineHeight apart, the block centred
    in box_h (vertical_alignment = center), glyph rect at pen + offset, tinted. Returns the lines."""
    common, chars = font
    width = lambda s: sum(chars[ord(c)]["xadvance"] for c in s if ord(c) in chars)     # noqa: E731
    lines, cur = [], ""
    for word in text.split(" "):
        trial = word if not cur else f"{cur} {word}"
        if cur and width(trial) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    lines.append(cur)
    y += (box_h - len(lines) * common["lineHeight"]) // 2
    for i, line in enumerate(lines):
        px = x
        for ch in line:
            c = chars.get(ord(ch))
            if c is None:
                continue
            tile = c["atlas"].crop((c["x"], c["y"], c["x"] + c["width"], c["y"] + c["height"]))
            tile = ImageChops.multiply(tile, Image.new("RGBA", tile.size, colour + (255,)))
            img.alpha_composite(tile, (px + c["xoffset"], y + i * common["lineHeight"] + c["yoffset"]))
            px += c["xadvance"]
    return lines


def build_scenario_preview(bg, logo, scrims, plates, still, board, scrim_scen, sw=2560, sh=1440, hovered=0):
    """Screen-size composite of the scenario picker (Russian, Select hovered) from the built textures, laid out like
    gamesetup_scenario_window in interface/frontendgamesetupview.gui (SCEN_* constants), with the main menu's title
    block, which stays on screen. Body text in vanilla hoi_20b from the game folder (skipped if it is missing)."""
    big, small = caption_fonts()
    col_x, col_y = sw - SAFE_X - SCEN_PIC[0], sh - PLATE_BOTTOM - SCEN_COL_H   # LOWER_RIGHT: -704, -488
    shot = cover(bg, sw, sh).convert("RGBA")
    shot.alpha_composite(scrim_scen, (col_x - SCEN_SCRIM_MARGIN[0], col_y - SCEN_SCRIM_MARGIN[1]))
    shot.alpha_composite(scrims["title"], SCRIM_TITLE_POS)                       # the menu's title block
    shot.alpha_composite(logo, (SAFE_X - LOGO_PAD, SAFE_Y - LOGO_PAD))
    draw_caption(shot, small, DATE_LINE, SAFE_X, SAFE_Y + logo.height - 2 * LOGO_PAD + 3 * LOGO_CELL)
    shot.alpha_composite(scrims["menu"], (SCRIM_MENU_POS[0], sh + SCRIM_MENU_POS[1]))
    ys = menu_rows(5)[-2:]                                                       # the Credits and Quit rows
    text_dy = (PLATE_H - 7 * CAP_CELL) // 2
    for i, (item, y) in enumerate(zip(SCENARIO_ITEMS, ys)):
        w, frame = caption_plate_w(item), 1 if i == hovered else 0
        shot.alpha_composite(plates[w].crop((frame * w, 0, (frame + 1) * w, PLATE_H)), (SAFE_X - PAD_L, sh + y))
    for (ru, _), y in zip(SCENARIO_ITEMS, ys):
        draw_caption(shot, big, ru, SAFE_X, sh + y + text_dy)
    shot.alpha_composite(still.convert("RGBA"), (col_x, col_y))
    shot.alpha_composite(board, (col_x, col_y + SCEN_PIC[1]))
    body = load_vanilla_font(["hoi_20b", "hoi_20b_cryllic"])
    if body:
        draw_vanilla_box(shot, body, loc_value("russian", "TOTU_1990_DESC"), col_x + SCEN_TEXT_IN,
                         col_y + SCEN_PIC[1] + SCEN_BOARD_PAD, SCEN_PIC[0] - 2 * SCEN_TEXT_IN,
                         SCEN_BODY_LINES * SCEN_BODY_LH, CAPTION_WHITE)
    else:
        print("scenario preview: no game folder at", GAME, "(set HOI4_DIR); body text left out")
    return shot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bg", default=SRC / "red_square.webp", type=Path,
                    help="menu background photo; the BG_* constants are tuned for red_square.webp")
    args = ap.parse_args()

    (ROOT / "tools/preview").mkdir(parents=True, exist_ok=True)
    bg = build_background(args.bg)
    save_dds(bg, ROOT / "gfx/loadingscreens/totu_red_square.dds")
    save_dds(bg.resize((192, 144), Image.LANCZOS), ROOT / "gfx/interface/totu/menu_bg_small.dds")

    # Main menu: logo, scrims, caption plates (also used by the scenario picker and the country selection)
    logo = build_logo()
    save_dds(logo, ROOT / "gfx/interface/totu/menu_logo.dds")
    print(f"menu logo: {logo.size}, gui position x = {SAFE_X - LOGO_PAD} y = {SAFE_Y - LOGO_PAD}")
    scrims = {"title": build_scrim(*SCRIM_TITLE), "menu": build_scrim(*SCRIM_MENU)}
    for name, img in scrims.items():
        save_dds(img, ROOT / f"gfx/interface/totu/scrim_{name}.dds")
    widths = {item: caption_plate_w(item)
              for item in MENU_ITEMS + SUBMENU_ITEMS + SCENARIO_ITEMS + COUNTRY_ITEMS + LOBBY_ITEMS}
    assert set(widths.values()) == set(CAPTION_PLATES), f"caption plates changed: {sorted(set(widths.values()))}"
    plates = {w: build_caption_plate(w) for w in CAPTION_PLATES}
    for w, img in plates.items():
        save_dds(img, ROOT / f"gfx/interface/totu/caption_{w}.dds")
    for (_, en), w in widths.items():
        print(f"  GFX_totu_caption_{w}: {en}")     # ASCII only: a non-UTF-8 Windows console can't print Cyrillic
    save_dds(build_button(), ROOT / "gfx/interface/totu/menu_button.dds")     # in-game menu, see BTN_W

    # Lobby frame: small caption plates, chips, tabs, the toggle, checkbox, bands, board, field (interface/totu_menu.gfx)
    small = {item: small_plate_w(item) for item in SMALL_ITEMS}
    assert set(small.values()) == set(SMALL_PLATES), f"small plates changed: {sorted(set(small.values()))}"
    for w in SMALL_PLATES:
        save_dds(build_small_plate(w), ROOT / f"gfx/interface/totu/caption_small_{w}.dds")
    for (_, en), w in small.items():
        print(f"  GFX_totu_caption_small_{w}: {en}")
    save_dds(build_small_plate(CHIP_W, (None, KEY_BLUE)), ROOT / "gfx/interface/totu/chip.dds")
    save_dds(build_small_plate(TAB_W, (None, KEY_BLUE, None)), ROOT / "gfx/interface/totu/tab.dds")
    save_dds(build_small_plate(small[SMALL_ITEMS[3]], (None, KEY_BLUE)), ROOT / "gfx/interface/totu/toggle.dds")
    save_dds(build_checkbox(), ROOT / "gfx/interface/totu/checkbox.dds")
    save_dds(build_band(True), ROOT / "gfx/interface/totu/band_top.dds")
    save_dds(build_band(False), ROOT / "gfx/interface/totu/band_bottom.dds")
    save_dds(build_board_tile(), ROOT / "gfx/interface/totu/board.dds")
    save_dds(build_field(), ROOT / "gfx/interface/totu/field.dds")
    gfx = (ROOT / "interface/totu_menu.gfx").read_text(encoding="utf-8")
    for w in list(CAPTION_PLATES) + [f"small_{w}" for w in SMALL_PLATES]:
        assert f'"GFX_totu_caption_{w}"' in gfx, f"GFX_totu_caption_{w} is not declared in interface/totu_menu.gfx"

    # Loading screens: pictures, then the UI (interface/load_screen.gfx)
    for i, (name, bars, exposure, dy, dx) in enumerate(LOADING_SCREENS):
        load = build_loading(SRC / "loading" / f"{name}.webp", bars, exposure, dy, dx, LOAD_GRAIN_SEED + i)
        save_dds(load, ROOT / f"gfx/loadingscreens/totu_load_{name}.dds")
        load.crop((0, 180, 1920, 1260)).resize((960, 540), Image.LANCZOS).save(ROOT / f"tools/preview/load_{name}.jpg", quality=88)
    save_dds(build_scrim(*LOAD_SCRIM), ROOT / "gfx/interface/totu/scrim_caption.dds")
    save_dds(Image.new("RGBA", (8, 8), (0, 0, 0, 0)), ROOT / "gfx/interface/totu/loading_blank.dds")
    save_dds(build_loading_bar(True), ROOT / "gfx/interface/totu/loading_progress_full.dds")
    save_dds(build_loading_bar(False), ROOT / "gfx/interface/totu/loading_progress_empty.dds")

    # Scenario picker
    still, board = build_scenario_still(), build_scenario_board()
    scrim_scen = build_scrim(*SCEN_SCRIM)
    save_dds(still, ROOT / "gfx/interface/totu/select_date_1990.dds")
    save_dds(build_bookmark_entry(), ROOT / "gfx/interface/totu/bookmark_entry.dds")
    save_dds(board, ROOT / "gfx/interface/totu/scenario_bg.dds")
    save_dds(scrim_scen, ROOT / "gfx/interface/totu/scrim_scenario.dds")

    # Country selection
    save_dds(build_country_select_bg(), ROOT / "gfx/interface/totu/country_select_bg.dds")
    save_dds(build_major_entry(), ROOT / "gfx/interface/totu/country_entry_major.dds")
    save_dds(build_minor_entry(), ROOT / "gfx/interface/totu/country_entry_minor.dds")
    save_dds(build_mini_entry(), ROOT / "gfx/interface/totu/country_entry_mini.dds")
    save_dds(build_filter(), ROOT / "gfx/interface/totu/country_filter.dds")
    save_dds(minor_portrait_overlay(), ROOT / "gfx/interface/totu/minor_portrait_overlay.dds")
    save_dds(build_scrim(*SCRIM_COUNTRY), ROOT / "gfx/interface/totu/scrim_country.dds")

    for out, (source, crop) in PORTRAITS.items():
        src = next(iter(sorted((SRC / "portraits").glob(f"{source}.*"))), None)
        if src is None:
            print(f"portrait {out}: no tools/src/portraits/{source}.* yet, faceless placeholder")
        save_dds(build_portrait(src, crop) if src else build_portrait_placeholder(),
                 ROOT / f"gfx/leaders/totu/{out}.dds")

    previews = {
        "menu_preview.png": build_preview(bg, logo, scrims, plates),
        "menu_parts.png": build_parts_sheet(scrims, plates),
        "loading_preview.png": build_loading_preview(),
        "screen_scenario.png": build_scenario_preview(bg, logo, scrims, plates, still, board, scrim_scen),
    }
    for name, img in previews.items():
        img.convert("RGB").save(ROOT / "tools/preview" / name)
        print("wrote", f"tools/preview/{name}")


if __name__ == "__main__":
    main()
