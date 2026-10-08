"""The Plenum window in the decisions screen (category TOTU_plenum_category, see
docs/superpowers/specs/2026-10-08-plenum-design.md): sprites, decision icons, .gui, scripted GUI, scripted localisation,
the generated scripted effects (support wrappers and TOTU_pl_update_gfx) and their localisation.

Outputs (all GENERATED, edit this script, not them):
  gfx/interface/totu/plenum/header.dds                banner 500x52 from tools/src/events/totu_plenum_hall.png
  gfx/interface/totu/plenum/floor.dds                 the dark hemicycle behind the seats
  gfx/interface/totu/plenum/presidium.dds            presidium table + tribune in the pit
  gfx/interface/totu/plenum/majority.dds, majority_tick.dds   gold majority notches (floor rim / legend, pit)
  gfx/interface/totu/plenum/seat.dds                  4 frames: a hall seat in the muted colour of dem, gorb, cons, orth
  gfx/interface/totu/plenum/card_<f>.dds              faction cards (dark, thin border in the faction colour)
  gfx/interface/totu/plenum/card_ruling_<f>.dds       the ruling faction's card: lighter, double cream-gold border
  gfx/interface/totu/plenum/support_<f>.dds           21 frames: horizontal support bar 0 %, 5 %, ... 100 % with the
                                                      gold majority notch (31 of 61)
  gfx/interface/totu/plenum/bar_rad.dds, bar_str.dds  21 frames: segmented bars 0..100 (radicalization coloured by
                                                      its state, crisis zone from 70; strength in gold, 50 mark)
  gfx/interface/totu/plenum/logo_<f>.dds              48 px outline logos traced from tools/src/plenum/<f>.png
  gfx/interface/totu/plenum/rule.dds                  hairline under the section labels
  gfx/interface/totu/plenum/icon_<name>.dds           window icons: emblem, status gavel, rad fist, str shield,
                                                      ruling star
  gfx/interface/totu/plenum/decisions/*.dds           decision icons 32x31, category icon 52x40, picture 114x101
  interface/totu_plenum.gfx                           GFX_totu_pl_*, GFX_decision_totu_pl_*, GFX_decision_category_
                                                      totu_plenum, GFX_decision_cat_picture_totu_plenum
  interface/totu_plenum.gui                           containerWindowType TOTU_plenum_window
  common/scripted_guis/TOTU_plenum_scripted_gui.txt   scripted_gui TOTU_plenum_gui (frames <- variables, ruling triggers)
  common/scripted_localisation/TOTU_plenum_scripted_loc.txt   status line, seat counts, state words, ruling note
  common/scripted_effects/TOTU_plenum_generated.txt   TOTU_pl_<f|rad|str>_<add|sub>_<n>, TOTU_pl_update_gfx
  localisation/{russian,english}/totu_plenum_generated_l_<lang>.yml (+ English copies for the other languages)
  tools/preview/plenum_window.png                     the window at the start values, drawn by tools/render_gui.py
  tools/preview/plenum_window_ruling.png              after the vote: conservatives rule, radicalization 75, str 30
  tools/preview/plenum_window_en.png                  the start values in English
  tools/preview/plenum_logos.png                      the logos at 1x and 4x on the panel colours
  tools/preview/plenum_icons.png                      decision and window icons at 4x and 1x (on the panel and on a
                                                      decision row, next to three vanilla icons), category icon/picture

Sources (tools/src/plenum/, committed): dem.png (rose in a fist) and gorb.png (CPSU banner) are the user's reference
logos; cons.png (flat two-colour emblem), orth.png and the monoline icon_*.png (handshake, rubber stamp, microphone and
TV camera, raised fist, torn party card) were generated once with the image API of tools/gen_icons.py
(prompts in SOURCE_PROMPTS / ICON_PROMPTS; only missing files are requested, 1024x1024: env TOTU_IMAGE_API_KEY or
TOTU_IMAGE_KEY_FILE). The 48 px card logos are traced into line art at 8x and box-filtered down: dark line art is
thinned to its centre line, filled shapes give their contour. All small icons (decisions 32x31, window icons) share one
rendering, solid(): a solid mid-tone fill, 1 px dark interior lines, a 1 px dark rim and a soft halo. The handshake,
stamp and fist are traced from icon_*.png into that rendering; the rose, party card, star, Lenin profile, torn card,
microphone with camera, gavel, shield and star badge are drawn here (icon_card.png and icon_tribune.png are no longer
used), as are the category icon and the hall pieces. The banner and the category picture are cut from
tools/src/events/totu_plenum_hall.png.

Usage:
  python tools/build_plenum.py                 # everything
  python tools/build_plenum.py --no-preview    # skip the render_gui previews
Requires Pillow, numpy and scipy.
"""
import argparse
import base64
import json
import subprocess
import sys
import urllib.request
from math import cos, pi, sin
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from build_menu_gfx import save_dds  # noqa: E402

SRC = ROOT / "tools/src/plenum"
HALL_PHOTO = ROOT / "tools/src/events/totu_plenum_hall.png"
GFX_DIR = "gfx/interface/totu/plenum"
PREVIEW = ROOT / "tools/preview"
MARK = "GENERATED by tools/build_plenum.py"
VANILLA_DECISIONS = Path(r"D:\steam\steamapps\common\Hearts of Iron IV\gfx\interface\decisions")   # sheet only
MIRROR_LANGS = ["braz_por", "french", "german", "japanese", "korean", "polish", "simp_chinese", "spanish"]

# --- factions (order = number = left-to-right order in the hall) -----------------------------------------------------
# key, colour, name ru, name en, genitive ru (tooltips), short en, start support, card name ru, card name en
FACTIONS = [
    ("dem", (0x4F, 0x8F, 0xD6), "Демократическая платформа", "Democratic Platform", "Демплатформы",
     "Democratic Platform", 12, "Демплатформа", "Dem. Platform"),
    ("gorb", (0xD8, 0x36, 0x2F), "Горбачёвцы", "Gorbachevites", "горбачёвцев", "Gorbachevite", 43,
     "Горбачёвцы", "Gorbachevites"),
    ("cons", (0xC9, 0x95, 0x2B), "Консерваторы", "Conservatives", "консерваторов", "Conservative", 33,
     "Консерваторы", "Conservatives"),
    ("orth", (0x9B, 0x9F, 0xA6), "Ортодоксы", "Orthodox Communists", "ортодоксов", "Orthodox", 12,
     "Ортодоксы", "Orthodox"),
]
KEYS = [f[0] for f in FACTIONS]
START_RAD, START_STR = 30, 65
AMOUNTS = [2, 3, 5, 8, 10, 15]
RAD_CRISIS, STR_MARK = 70, 50                 # crisis zone of the radicalization bar, mark on the strength bar
RAD_WORDS = [(40, "calm"), (70, "tense"), (101, "critical")]     # value < limit -> word
STR_WORDS = [(35, "weak"), (65, "stable"), (101, "strong")]

# --- colours ---------------------------------------------------------------------------------------------------------
TAN = (195, 176, 145)             # the mod's text tan (build_menu_gfx.TAN, textcolor L)
GOLD = (214, 178, 102)            # emblem, gold accents
MARK_GOLD = (0xC8, 0xA0, 0x50)    # majority marks (hall, legend, the support bars of the cards), strength bar fill
CREAM = (0xE6, 0xCF, 0x8A)        # the ruling faction: card border and star
ICON_RED = (0x9A, 0x3A, 0x30)     # non-faction icons in red (stamp, purge)
ICON_TAN = (0xB9, 0xA5, 0x7F)     # non-faction icons in tan (handshake, tribune)
RAD_ICON = (0xC2, 0x5E, 0x3A)     # the radicalization fist
PARTY_RED = (0xB4, 0x2E, 0x28)    # the strength shield
# radicalization bar: the fill takes the colour of the state (calm / tense / critical)
RAD_FILL = [(40, (0x9C, 0x8A, 0x6A)), (70, (0xD2, 0x80, 0x3A)), (101, (0xC0, 0x39, 0x2B))]
STR_FILL, STR_EDGE = MARK_GOLD, (0x8A, 0x6E, 0x38)
PANEL = (34, 31, 28)              # the vanilla decisions panel behind the window (previews only)
# hall seats: the faction colours about 12 % less saturated (logos and borders keep the full colours)
SEAT_COLOURS = {"dem": (0x54, 0x86, 0xBE), "gorb": (0xC4, 0x46, 0x3C), "cons": (0xBF, 0x92, 0x38),
                "orth": (0x95, 0x9A, 0xA0)}

# --- window layout (the decision category content is ~500 px wide; 8 px grid) ---------------------------------------
WIN_W, WIN_H = 500, 472
M = 8                             # outer margin
HEADER_H = 52
SEC_LABEL_H = 17                  # section label (hoi_16mbs) + the hairline under it
SEC_HALL_Y = 58
# hall
SEATS = 61
ROWS = [11, 14, 17, 19]           # inner -> outer
RADII = [66, 88, 110, 132]
SEAT = 16                         # seat sprite size
HALL_CX = WIN_W // 2
HALL_CY = SEC_HALL_Y + SEC_LABEL_H + 10 + RADII[-1] + SEAT // 2     # 225: top seat edge 10 px under the hairline
PIT_R = RADII[0] - SEAT // 2      # free radius inside the inner row (58)
FLOOR_R = RADII[-1] + SEAT // 2 + 6                                 # floor rim 4 px under the hairline
FLOOR_DROP = 12                   # the floor continues this far below the centre line
MAJ_W, MAJ_H = 7, 5               # the gold majority notch on the floor rim (and in the legend)
TICK_W, TICK_H = 2, 6             # the second majority notch, in the pit under the inner row
LEGEND_W = HALL_CX - FLOOR_R - 2 - 6 - M                            # 88: the quiet legends beside the hall
# faction cards
SEC_FAC_Y = HALL_CY + 18          # 6 px under the floor
CARD_Y = SEC_FAC_Y + SEC_LABEL_H + 11                               # room for the ruling star above the card
CARD_W, CARD_H, CARD_GAP = 115, 122, 8
LOGO = 48
SUP_W, SUP_H = CARD_W - 16, 10    # the support bar under the name: 6 px bar, 2 px above/below for the majority notch
# party state
SEC_PARTY_Y = CARD_Y + CARD_H + 8
ROW_Y = [SEC_PARTY_Y + SEC_LABEL_H + 6, SEC_PARTY_Y + SEC_LABEL_H + 32]
ROW_ICON = 20
SEG, SEG_N = 10, 20               # bar: 20 segments of 10 px (9 px cell + 1 px gap) = 5 % each
BAR_W, BAR_H = SEG * SEG_N - 1, 16
BAR_X = 146
FRAMES = 21
assert ROW_Y[-1] + 22 == WIN_H, (ROW_Y, WIN_H)

# decision icons: decision -> (kind, source, colour)
DECISION_ICONS = [
    ("lean_dem", "logo", "dem", FACTIONS[0][1]),
    ("lean_gorb", "logo", "gorb", FACTIONS[1][1]),
    ("lean_cons", "logo", "cons", FACTIONS[2][1]),
    ("lean_orth", "logo", "orth", FACTIONS[3][1]),
    ("unity_appeal", "mono", "icon_hands", ICON_TAN),
    ("strengthen_apparatus", "mono", "icon_stamp", ICON_RED),
    ("purge", "drawn", None, ICON_RED),
    ("open_tribune", "drawn", None, ICON_TAN),
]


def hexrgb(c):
    return "#%02X%02X%02X" % c


def mix(c, d, t):
    return tuple(round(a + (b - a) * t) for a, b in zip(c, d))


# ======================================================================================================================
# Hall geometry
# ======================================================================================================================
def row_sequence():
    """The order in which the rows receive seats when 1, 2, ... 61 seats are shared among them in proportion to
    their size by the Sainte-Lague (Webster) divisor method. Divisor methods are house-monotone, so the first C seats
    of this sequence give every row its fair share of any running total C, and C = 61 fills every row exactly."""
    given, seq = [0] * len(ROWS), []
    for _ in range(SEATS):
        r = max(range(len(ROWS)), key=lambda i: (ROWS[i] / (given[i] + 0.5), ROWS[i]))
        given[r] += 1
        seq.append(r)
    assert given == ROWS, given
    return seq


def hall_seats():
    """[(x, y)] top-left positions of seats 1..61. Seat number K sits in the row that receives the K-th seat of
    row_sequence(), at the next free place from the left. TOTU_pl_update_gfx gives seat K to the first faction whose
    running seat total reaches K, so every faction gets a share of every row in proportion to the row size, filled
    from the left: the four factions form radial wedges with straight boundaries (the parliament-diagram method)
    while the seat counts stay exact."""
    pos, used = [], [0] * len(ROWS)
    for row in row_sequence():
        n, r, j = ROWS[row], RADII[row], used[row]
        used[row] += 1
        a = pi - pi * j / (n - 1)
        pos.append((round(HALL_CX + r * cos(a) - SEAT / 2), round(HALL_CY - r * sin(a) - SEAT / 2)))
    return pos


def allocate(supports):
    """Largest remainder, exactly as TOTU_pl_update_gfx does it (ties go to the earlier faction)."""
    q = [s * 61 / 100 for s in supports]
    s = [int(v) for v in q]
    r = [a - b for a, b in zip(q, s)]
    left = SEATS - sum(s)
    for _ in range(4):
        if left <= 0:
            break
        best = 0
        for i in range(1, 4):
            if r[i] > r[best]:
                best = i
        s[best] += 1
        r[best] = -1
        left -= 1
    return s


def seat_frames(supports):
    s = allocate(supports)
    c1, c2, c3 = s[0], s[0] + s[1], s[0] + s[1] + s[2]
    return [1 if i <= c1 else 2 if i <= c2 else 3 if i <= c3 else 4 for i in range(1, SEATS + 1)]


def value_frame(v):
    """Frame 1..21 of a 0..100 value, rounded down to 5 % steps (as TOTU_pl_update_gfx), so the colour of a bar
    frame never claims a state the value has not reached."""
    return max(1, min(FRAMES, int(v // 5) + 1))


def seat_form(n):
    """Russian plural form of 'место' for n: single (exactly 1), one (21, 31...), few (2-4, 22-24...), many."""
    if n == 1:
        return "single"
    if n % 10 == 1 and n % 100 != 11:
        return "one"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "few"
    return "many"


SEAT_WORDS = {"ru": {"single": "место", "one": "место", "few": "места", "many": "мест"},
              "en": {"single": "seat", "one": "seats", "few": "seats", "many": "seats"}}


def state_word(value, table):
    return next(w for lim, w in table if value < lim)


# ======================================================================================================================
# Drawing helpers (everything is drawn at SS x and box-filtered down)
# ======================================================================================================================
SS = 8


def to_img(rgb, alpha):
    """float arrays (h, w, 3) 0..255 and (h, w) 0..1 -> RGBA image."""
    return Image.fromarray(np.dstack([np.clip(rgb, 0, 255), np.clip(alpha, 0, 1) * 255]).astype(np.uint8), "RGBA")


def down(img, w, h):
    """Premultiplied box downsampling of a supersampled RGBA image (no dark fringes)."""
    a = np.asarray(img, np.float64)
    pm = a.copy()
    pm[:, :, :3] *= a[:, :, 3:4] / 255
    small = np.asarray(Image.fromarray(pm.clip(0, 255).astype(np.uint8), "RGBA").resize((w, h), Image.BOX), np.float64)
    al = np.asarray(Image.fromarray(a[:, :, 3].astype(np.uint8)).resize((w, h), Image.BOX), np.float64)
    rgb = np.where(al[:, :, None] > 0, small[:, :, :3] * 255 / np.maximum(al[:, :, None], 1), 0)
    return Image.fromarray(np.dstack([rgb.clip(0, 255), al]).astype(np.uint8), "RGBA")


def fdown(arr, w, h):
    """Box downsampling of a float mask 0..1."""
    return np.asarray(Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8)).resize((w, h), Image.BOX),
                      np.float64) / 255


def grid(w, h, ss=SS):
    """Pixel-centre coordinates of a w x h canvas at ss x, in output pixels."""
    y, x = np.mgrid[0:h * ss, 0:w * ss]
    return (x + 0.5) / ss, (y + 0.5) / ss


def poly_mask(w, h, pts, ss=SS):
    """Filled polygon (output-pixel coordinates) at ss x as a bool array."""
    im = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(im).polygon([(x * ss, y * ss) for x, y in pts], fill=255)
    return np.asarray(im) > 127


def star_pts(cx, cy, r, inner=0.40, rot=-pi / 2):
    pts = []
    for k in range(10):
        rr = r if k % 2 == 0 else r * inner
        a = rot + k * pi / 5
        pts.append((cx + rr * cos(a), cy + rr * sin(a)))
    return pts


def shadow(alpha, grow=1, blur=0.6, strength=0.7):
    """A soft dark halo under an icon (alpha image)."""
    a = Image.fromarray((np.clip(alpha, 0, 1) * 255).astype(np.uint8))
    if grow:
        a = a.filter(ImageFilter.MaxFilter(2 * grow + 1))
    return np.asarray(a.filter(ImageFilter.GaussianBlur(blur)), np.float64) / 255 * strength


def layer(base, colour, alpha):
    """Composite a flat colour with alpha (h, w) over base (h, w, 4 float rgb 0..255 / a 0..1)."""
    a = np.clip(np.asarray(alpha, np.float64), 0, 1)[:, :, None]
    out_a = a + base[:, :, 3:4] * (1 - a)
    rgb = (np.array(colour, np.float64) * a + base[:, :, :3] * base[:, :, 3:4] * (1 - a)) / np.maximum(out_a, 1e-6)
    return np.dstack([rgb, out_a])


def canvas(w, h):
    return np.zeros((h, w, 4), np.float64)


def finish(c):
    return to_img(c[:, :, :3], c[:, :, 3])


# ======================================================================================================================
# Hall sprites
# ======================================================================================================================
def seat_img(colour):
    """A flat round seat: faction colour, a slightly darker lower half and a dark rim. No highlight."""
    x, y = grid(SEAT, SEAT)
    d = np.hypot(x - SEAT / 2, y - SEAT / 2)
    r = SEAT / 2 - 0.7
    alpha = np.clip(r - d + 0.5, 0, 1)
    rim = np.clip(d - (r - 1.3) + 0.5, 0, 1)
    shade = np.clip((y - SEAT * 0.35) / (SEAT * 0.6), 0, 1) * 0.22          # darker towards the bottom
    body = np.array(colour, np.float64)[None, None] * (1 - shade[:, :, None])
    rimc = np.array(mix(colour, (0, 0, 0), 0.55), np.float64)[None, None]
    rgb = body * (1 - rim[:, :, None]) + rimc * rim[:, :, None]
    return down(to_img(rgb, alpha), SEAT, SEAT)


def build_seat():
    strip = Image.new("RGBA", (SEAT * 4, SEAT), (0, 0, 0, 0))
    for i, f in enumerate(FACTIONS):
        strip.alpha_composite(seat_img(SEAT_COLOURS[f[0]]), (i * SEAT, 0))
    return strip


def floor_size():
    return 2 * FLOOR_R + 4, FLOOR_R + FLOOR_DROP + 2


def build_floor():
    """The hemicycle behind the seats: a dark warm band under the rows with faint grooves between them, a darker red
    pit in the middle; the band continues straight down a little below the centre line."""
    w, h = floor_size()
    cx, cy = w / 2, FLOOR_R + 1
    x, y = grid(w, h, 4)
    d = np.where(y <= cy, np.hypot(x - cx, y - cy), np.abs(x - cx))
    inside = np.clip(FLOOR_R - d + 0.5, 0, 1) * np.clip(cy + FLOOR_DROP - y + 0.5, 0, 1)
    band = np.clip(d - (PIT_R - 4) + 0.5, 0, 1)
    rgb = np.zeros(d.shape + (3,))
    t = np.clip((d - PIT_R) / (FLOOR_R - PIT_R), 0, 1)[:, :, None]          # lighter towards the back rows
    rgb[:] = np.array((46, 37, 32)) * (1 - t) + np.array((58, 47, 40)) * t
    pit = np.array((52, 26, 22))
    rgb = rgb * band[:, :, None] + pit * (1 - band[:, :, None])
    alpha = inside * (0.62 * band + 0.55 * (1 - band))
    for r in [(a + b) / 2 for a, b in zip(RADII, RADII[1:])] + [FLOOR_R - 1.5]:   # grooves between the rows
        g = np.clip(1.0 - np.abs(d - r), 0, 1) * (y <= cy + FLOOR_DROP)
        rgb = rgb * (1 - 0.35 * g[:, :, None])
    edge = np.clip(1.2 - np.abs(d - (PIT_R - 4)), 0, 1) * 0.5                 # rim of the pit
    rgb = rgb + (np.array(GOLD) - rgb) * (edge * 0.35)[:, :, None]
    return down(to_img(rgb, alpha), w, h)


PRESIDIUM_W, PRESIDIUM_H = 76, 22


def build_presidium():
    """A small presidium: a row of seated members behind a long red table, the tribune in front of its centre."""
    w, h = PRESIDIUM_W, PRESIDIUM_H
    c = canvas(w * SS, h * SS)
    x, y = grid(w, h)
    for k in range(9):                                       # heads and shoulders behind the table
        px = 8 + k * (w - 16) / 8
        head = np.clip(1.6 - np.hypot(x - px, y - 4.2) + 0.5, 0, 1)
        body = np.clip(3.0 - np.hypot((x - px) * 0.9, (y - 9.0) * 1.2) + 0.5, 0, 1) * (y < 10)
        c = layer(c, (78, 70, 62), np.maximum(head, body))
    table = poly_mask(w, h, [(3, 9), (w - 3, 9), (w - 3, 15), (3, 15)])
    c = layer(c, (124, 40, 32), table)
    c = layer(c, (88, 26, 22), table & (y > 13.4))
    c = layer(c, GOLD, poly_mask(w, h, [(3, 9), (w - 3, 9), (w - 3, 9.9), (3, 9.9)]) * 0.8)
    trib = poly_mask(w, h, [(w / 2 - 6, 12), (w / 2 + 6, 12), (w / 2 + 5, 21), (w / 2 - 5, 21)])
    c = layer(c, (20, 14, 12), ndi.binary_dilation(trib, iterations=SS))
    c = layer(c, (104, 72, 46), trib)
    c = layer(c, GOLD, np.clip(1.4 - np.hypot(x - w / 2, y - 16.2) + 0.5, 0, 1) * 0.9)   # the state emblem on it
    return down(finish(c), w, h)


def build_majority():
    """The majority notch: a small solid gold triangle pointing down, on the floor rim at the centre axis (and in the
    legend beside the hall). It marks the axis without touching a seat."""
    w, h = MAJ_W, MAJ_H
    a = m_poly(w, h, [(0.2, 0.2), (w - 0.2, 0.2), (w / 2, h - 0.1)])
    c = layer(canvas(w, h), MARK_GOLD, fdown(a, w, h))
    return finish(c)


def build_majority_tick():
    """The second majority notch: a short gold tick in the pit, just under the centre seat of the inner row."""
    px = np.zeros((TICK_H, TICK_W, 4), np.float64)
    px[:, :] = MARK_GOLD + (230,)
    px[-1, :, 3] = 120
    return Image.fromarray(px.astype(np.uint8), "RGBA")


# ======================================================================================================================
# Cards, columns, bars, rules
# ======================================================================================================================
def build_card(colour):
    """A dark card with a thin border tinted in the faction colour and a 2 px accent along the top."""
    px = np.zeros((CARD_H, CARD_W, 4), np.float64)
    px[:, :] = (18, 16, 15, 190)
    px[1:24, 1:CARD_W - 1, :3] += np.linspace(14, 0, 23)[:, None, None] * np.array(colour) / 255   # faint tint on top
    border = mix(colour, (24, 22, 20), 0.5) + (255,)
    px[0, :] = border
    px[-1, :] = border
    px[:, 0] = border
    px[:, -1] = border
    px[1:3, 1:CARD_W - 1] = mix(colour, (24, 22, 20), 0.15) + (255,)
    return Image.fromarray(px.clip(0, 255).astype(np.uint8), "RGBA")


def build_card_ruling(colour):
    """The ruling faction's card, drawn over its normal card: a lighter fill and a double border in cream gold
    (1 px #E6CF8A, 1 px gap, 1 px dark gold), so the state shows whatever the faction colour is."""
    px = np.zeros((CARD_H, CARD_W, 4), np.float64)
    px[:, :] = (0x2B, 0x26, 0x20, 240)
    px[3:26, 3:CARD_W - 3, :3] += np.linspace(16, 0, 23)[:, None, None] * np.array(colour) / 255
    outer, inner = CREAM + (255,), (0x8A, 0x6A, 0x2A, 255)
    for k, c in ((0, outer), (2, inner)):
        px[k, k:CARD_W - k] = c
        px[CARD_H - 1 - k, k:CARD_W - k] = c
        px[k:CARD_H - k, k] = c
        px[k:CARD_H - k, CARD_W - 1 - k] = c
    return Image.fromarray(px.clip(0, 255).astype(np.uint8), "RGBA")


def support_frame(colour, pct):
    """SUP_W x SUP_H: the support bar of a card. A 6 px dark well (rows 2..7) with a rim in the faction colour, the
    fill from the left in the faction colour shading to 80 % of it downwards; faint 2 px ticks under the bar at 25
    and 75 %; the gold majority notch at 31 of 61 seats (50.8 %) runs 2 px past the bar on both sides."""
    px = np.zeros((SUP_H, SUP_W, 4), np.float64)
    inner_w = SUP_W - 2
    px[2:8, :] = (10, 9, 8, 190)
    fill = round(inner_w * pct / 100)
    for y in range(3, 7):
        t = (y - 3) / 3
        px[y, 1:1 + fill] = mix(colour, mix(colour, (0, 0, 0), 0.2), t) + (255,)
    rim = mix(colour, (30, 28, 26), 0.45) + (255,)
    px[2, :] = rim
    px[7, :] = rim
    px[2:8, 0] = rim
    px[2:8, -1] = rim
    for q in (25, 75):
        x = 1 + round(inner_w * q / 100)
        px[8:10, x] = (0x4A, 0x43, 0x3A, 255)
    x = 1 + round(inner_w * 31 / 61) - 1
    px[0:SUP_H, x:x + 2] = MARK_GOLD + (255,)
    return Image.fromarray(px.clip(0, 255).astype(np.uint8), "RGBA")


def build_support(colour):
    strip = Image.new("RGBA", (SUP_W * FRAMES, SUP_H), (0, 0, 0, 0))
    for k in range(FRAMES):
        strip.alpha_composite(support_frame(colour, k * 5), (k * SUP_W, 0))
    return strip


def rad_fill(pct):
    return next(c for lim, c in RAD_FILL if pct < lim)


def bar_frame(kind, pct):
    """BAR_W x BAR_H: 20 cells of 5 % (rows 2..13), filled up to pct. Radicalization: the fill takes the colour of
    the state (muted ochre / orange / red), the empty cells of the crisis zone (from 70) are shaded red. Strength:
    gold fill, so a high value reads as good. A cream tick marks the threshold over the full height."""
    px = np.zeros((BAR_H, BAR_W, 4), np.float64)
    n = round(pct / 5)
    crisis = RAD_CRISIS if kind == "rad" else None
    mark = RAD_CRISIS if kind == "rad" else STR_MARK
    colour = rad_fill(pct) if kind == "rad" else STR_FILL
    for i in range(SEG_N):
        x0 = i * SEG
        zone = crisis is not None and i * 5 >= crisis
        if i < n:
            for y in range(2, 14):
                t = (y - 2) / 11
                px[y, x0:x0 + SEG - 1] = mix(mix(colour, (255, 255, 255), 0.08), mix(colour, (0, 0, 0), 0.28), t) + (255,)
        else:
            if zone:
                well, edge = (44, 18, 15, 215), (96, 42, 34, 255)
            elif kind == "str":
                well, edge = (18, 16, 14, 200), mix(STR_EDGE, (18, 16, 14), 0.35) + (255,)
            else:
                well, edge = (18, 16, 14, 200), (62, 55, 48, 255)
            px[2:14, x0:x0 + SEG - 1] = well
            px[2, x0:x0 + SEG - 1] = edge
            px[13, x0:x0 + SEG - 1] = edge
            px[2:14, x0] = edge
            px[2:14, x0 + SEG - 2] = edge
    x = mark // 5 * SEG - 1                                      # the gap before the first cell of the zone
    px[0:BAR_H, x] = CREAM + (240,)
    return Image.fromarray(px.clip(0, 255).astype(np.uint8), "RGBA")


def build_bar(kind):
    strip = Image.new("RGBA", (BAR_W * FRAMES, BAR_H), (0, 0, 0, 0))
    for k in range(FRAMES):
        strip.alpha_composite(bar_frame(kind, k * 5), (k * BAR_W, 0))
    return strip


RULE_W = WIN_W - 2 * M


def build_rule():
    """Hairline under a section label: tan, fading out to the right."""
    a = np.array([120 * (1 - 0.75 * x / (RULE_W - 1)) * min(1.0, (RULE_W - 1 - x) / 40) for x in range(RULE_W)])
    px = np.zeros((1, RULE_W, 4))
    px[0, :, :3] = TAN
    px[0, :, 3] = a
    return Image.fromarray(px.astype(np.uint8), "RGBA")


# ======================================================================================================================
# Photo crops: header banner, category picture
# ======================================================================================================================
def photo():
    return Image.open(HALL_PHOTO).convert("RGB")


def lum(img):
    return np.asarray(img.convert("L"), np.float64) / 255


def build_header():
    """500x52 strip of the presidium, darkened into a muted red duotone; darker on the left where the title sits."""
    im = photo().crop((0, 392, 1536, 552))                    # presidium heads and the red table
    im = im.resize((WIN_W, HEADER_H), Image.LANCZOS)
    L = lum(im)
    L = (L - L.min()) / max(1e-6, L.max() - L.min())
    L = L ** 1.15
    dark, light = np.array((16, 9, 8)), np.array((150, 70, 55))
    rgb = dark + (light - dark) * L[:, :, None]
    x = np.linspace(0, 1, WIN_W)[None, :]
    shade = 0.27 + 0.53 * np.clip((x - 0.10) / 0.75, 0, 1) ** 1.3          # dark under the title and status
    rgb = rgb * shade[:, :, None]
    y = np.linspace(0, 1, HEADER_H)[:, None]
    rgb = rgb * (1 - 0.25 * y[:, :, None] ** 2)
    alpha = np.ones((HEADER_H, WIN_W))
    rgb[0, :] = (10, 8, 7)
    rgb[-1, :] = mix(GOLD, (20, 16, 14), 0.35)
    rgb[-2, :] = rgb[-2, :] * 0.6
    return to_img(rgb, alpha)


CAT_PIC = (114, 101)


def build_cat_picture():
    """114x101 like the vanilla category pictures: the tribune, Lenin's bust and the presidium, faded warm photo,
    dark vignette, a 1 px dark frame with rounded corners."""
    w, h = CAT_PIC
    box_w = 850
    box_h = round(box_w * h / w)
    im = photo().crop((40, 20, 40 + box_w, 20 + box_h)).resize((w, h), Image.LANCZOS)
    a = np.asarray(im, np.float64)
    g = a.mean(2, keepdims=True)
    a = g + (a - g) * 0.38                                   # mostly desaturated
    a = a * np.array((1.04, 0.97, 0.86))                     # warm, like the vanilla sepia pictures
    a = (a - 128) * 1.08 + 120
    x, y = grid(w, h, 1)
    v = np.hypot((x - w / 2) / (w / 2), (y - h / 2) / (h / 2))
    a = a * (1 - 0.35 * np.clip(v - 0.55, 0, 1) ** 1.4)[:, :, None]
    # rounded frame
    r = 4
    cx = np.clip(x, r, w - r)
    cy = np.clip(y, r, h - r)
    dist = r - np.hypot(x - cx, y - cy)
    alpha = np.clip(dist + 0.5, 0, 1)
    frame = np.clip(1.5 - dist, 0, 1)
    a = a * (1 - frame[:, :, None]) + np.array((22, 19, 17)) * frame[:, :, None]
    return to_img(a, alpha)


# ======================================================================================================================
# Logo tracing
# ======================================================================================================================
LOGO_SS = 8                      # work resolution = LOGO * LOGO_SS
WORK = LOGO * LOGO_SS
LINE_W = 9                       # line width at work resolution (~1.1 px in the 48 px logo)

SOURCE_PROMPTS = {
    "cons": ("Flat vector emblem, like a clean logo: a large bold five-pointed star, point up, in solid dark red, with "
             "a hammer and sickle in solid golden yellow inside its centre (the classic Soviet hammer and sickle, "
             "large, simple bold shapes, clearly separated from the star edges by red). Only these two flat solid "
             "colours on a plain pure white background. No outlines, no shading, no gradients, no 3D, no texture, no "
             "text, no frame."),
    "orth": ("Minimal monoline outline icon on a plain white background: the nested double profile of Lenin and "
             "Stalin as on Soviet medals and banners, both heads facing right. Lenin in front, bald domed head, short "
             "pointed goatee and moustache. Stalin directly behind him, his head offset up and slightly forward so "
             "that Stalin's forehead, nose and big moustache show as a second profile line just beyond Lenin's "
             "face, and his thick swept-back hair rises above Lenin's bald dome. Drawn only with a few uniform thick "
             "black strokes of one constant width, like a simple line icon designed to be read at 48 pixels: the "
             "outer contours of both heads, Lenin's ear and Stalin's moustache. No fills, no shading, no hatching, "
             "no small details, no text, no circle, no frame."),
}
ICON_STYLE = ("Minimal monoline outline icon on a plain pure white background: {s} Drawn only with a few uniform thick "
              "black strokes of one constant width, like a simple line icon designed to be read at 24 pixels: large "
              "simple shapes, generous gaps between the lines, very few strokes. No fills, no shading, no hatching, "
              "no small details, no text, no circle, no frame.")
ICON_PROMPTS = {
    "icon_hands": ("two hands clasped in a firm handshake, seen from the side, one coming in from the left and one "
                   "from the right, each with a plain shirt cuff at the wrist, the clasp in the centre."),
    "icon_stamp": ("a heavy old office rubber stamp standing upright, seen from the side: a round knob handle on a "
                   "short neck, a wide rectangular base block, and under it a short horizontal line for the paper."),
    "icon_tribune": ("a vintage 1980s broadcast microphone on a short desk stand in front on the left, and behind it "
                     "on the right a boxy 1980s television studio camera on a tripod, seen from the side."),
    "icon_fist": ("a raised clenched fist seen from the front, knuckles up, the forearm going straight down to a plain "
                  "sleeve cuff."),
    "icon_card": ("a small closed party membership card booklet, a plain upright rectangle with a small five-pointed "
                  "star on its cover, torn in two halves by one jagged tear running from top to bottom, the two halves "
                  "pulled slightly apart and tilted."),
}


def ensure_sources():
    prompts = dict(SOURCE_PROMPTS)
    prompts.update({k: ICON_STYLE.format(s=v) for k, v in ICON_PROMPTS.items()})
    missing = [k for k in KEYS + list(ICON_PROMPTS) if not (SRC / f"{k}.png").exists()]
    if not missing:
        return
    if any(k not in prompts for k in missing):
        sys.exit(f"missing logo sources in tools/src/plenum: {missing} (dem/gorb are the user's reference logos)")
    import gen_icons   # api key and endpoint config (never printed)
    key = gen_icons.api_key()
    for k in missing:
        body = json.dumps({"model": gen_icons.MODEL, "prompt": prompts[k], "size": "1024x1024", "n": 1,
                           "output_format": "png"}).encode()
        req = urllib.request.Request(gen_icons.BASE_URL + "/images/generations", data=body, method="POST",
                                     headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=400) as r:
            data = json.loads(r.read())["data"][0]
        if data.get("b64_json"):
            png = base64.b64decode(data["b64_json"])
        else:
            with urllib.request.urlopen(data["url"], timeout=120) as r:
                png = r.read()
        SRC.mkdir(parents=True, exist_ok=True)
        (SRC / f"{k}.png").write_bytes(png)
        print("generated", f"tools/src/plenum/{k}.png")


def load_classes(path, palette):
    """Nearest-palette-colour masks of a flat logo (composited on white)."""
    im = Image.open(path).convert("RGBA")
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    bg.alpha_composite(im)
    a = np.asarray(bg.convert("RGB")).astype(np.int32)
    names = list(palette)
    cols = np.array([palette[n] for n in names])
    idx = ((a[:, :, None, :] - cols[None, None]) ** 2).sum(-1).argmin(-1)
    return {n: idx == i for i, n in enumerate(names)}


def fit(masks, box_from, margin_px=2):
    """Masks cropped to the bbox of box_from, centred and scaled into the WORK x WORK square (margin in 48 px)."""
    ys, xs = np.nonzero(box_from)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    side = max(y1 - y0, x1 - x0)
    cy, cx = (y0 + y1) / 2, (x0 + x1) / 2
    inv = side / (WORK - 2 * margin_px * LOGO_SS)
    data = (inv, 0, cx - WORK / 2 * inv, 0, inv, cy - WORK / 2 * inv)
    out = {}
    for n, m in masks.items():
        im = Image.fromarray((m * 255).astype(np.uint8))
        out[n] = np.asarray(im.transform((WORK, WORK), Image.AFFINE, data, resample=Image.BILINEAR)) > 127
    return out


def disk(r):
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    return x * x + y * y <= r * r


def smooth(mask, sigma):
    return ndi.gaussian_filter(mask.astype(np.float32), sigma) > 0.5


def label8(mask):
    return ndi.label(mask, np.ones((3, 3), bool))


def drop_small(mask, min_area):
    lab, n = label8(mask)
    if n == 0:
        return mask
    keep = np.zeros(n + 1, bool)
    keep[1:] = ndi.sum(mask, lab, range(1, n + 1)) >= min_area
    return keep[lab]


def keep_largest(mask, n):
    lab, k = label8(mask)
    if k <= n:
        return mask
    keep = np.zeros(k + 1, bool)
    keep[1 + np.argsort(ndi.sum(mask, lab, range(1, k + 1)))[::-1][:n]] = True
    return keep[lab]


def thin(mask):
    """Zhang-Suen thinning to a one-pixel centre line."""
    img = np.pad(mask.astype(np.uint8), 1)
    changed = True
    while changed:
        changed = False
        for step in (0, 1):
            p = img
            p2, p6 = np.roll(p, 1, 0), np.roll(p, -1, 0)
            p4, p8 = np.roll(p, -1, 1), np.roll(p, 1, 1)
            p3, p5 = np.roll(p2, -1, 1), np.roll(p6, -1, 1)
            p7, p9 = np.roll(p6, 1, 1), np.roll(p2, 1, 1)
            nb = [p2, p3, p4, p5, p6, p7, p8, p9]
            b = sum(nb)
            seq = nb + [p2]
            a = sum(((seq[i] == 0) & (seq[i + 1] == 1)).astype(np.uint8) for i in range(8))
            c = ((p2 * p4 * p6 == 0) & (p4 * p6 * p8 == 0)) if step == 0 else \
                ((p2 * p4 * p8 == 0) & (p2 * p6 * p8 == 0))
            rm = (p == 1) & (b >= 2) & (b <= 6) & (a == 1) & c
            if rm.any():
                img = img.copy()
                img[rm] = 0
                changed = True
    return img[1:-1, 1:-1].astype(bool)


def prune(skel, k):
    """Strip k pixels from every free end (spurs), then grow the surviving ends back along the skeleton."""
    def nbcount(s):
        return ndi.convolve(s.astype(np.uint8), np.ones((3, 3), np.uint8), mode="constant") - s
    x = skel.copy()
    for _ in range(k):
        x &= ~(x & (nbcount(x) <= 1))
    grow = x & (nbcount(x) == 1)
    for _ in range(k):
        grow = ndi.binary_dilation(grow, np.ones((3, 3), bool)) & skel
    return x | grow


def centre_lines(mask, min_area=40, spur=10):
    return prune(drop_small(thin(mask), min_area), spur)


def line_alpha(skel, width):
    return np.clip(width / 2 + 0.5 - ndi.distance_transform_edt(~skel), 0, 1)


def edge_alpha(region, width):
    """A line of the given width centred on the boundary of region."""
    sd = np.where(region, ndi.distance_transform_edt(region) - 0.5, 0.5 - ndi.distance_transform_edt(~region))
    return np.clip(width / 2 + 0.5 - np.abs(sd), 0, 1)


_cache = {}


def cached(key, fn):
    if key not in _cache:
        _cache[key] = fn()
    return _cache[key]


def skel_dem():
    def make():
        c = load_classes(SRC / "dem.png", {"white": (255, 255, 255), "black": (43, 40, 40), "red": (216, 38, 40),
                                           "green": (0, 158, 98), "dkgreen": (53, 95, 78)})
        m = fit(c, ~c["white"])
        sk = centre_lines(smooth(m["black"], 2), 40, 10)
        leaves = ndi.binary_fill_holes(ndi.binary_closing(m["green"] | m["dkgreen"], disk(4)))
        return sk, ndi.binary_erosion(leaves, disk(6)), m
    return cached("dem", make)


def trace_dem(lw=LINE_W, simple=False):
    """Rose in a fist: the logo is black line art with colour fills; its black lines are the outline. The leaf veins
    are drawn thinner and fainter so the two leaves stay readable at 48 px (the 32 px decision icon is a rose drawn in
    dec_lean_dem)."""
    sk, inner, m = skel_dem()
    a = line_alpha(sk & ~inner, lw)
    return np.maximum(a, line_alpha(sk & inner, lw * 0.6) * 0.75)


def trace_gorb(lw=LINE_W, simple=False):
    """CPSU banner: the yellow border and letters are thinned to centre lines, Lenin's head (the only wide yellow
    shape) gives its contour plus the red facial lines inside; the tiny star and hammer and sickle are dropped."""
    def make():
        c = load_classes(SRC / "gorb.png", {"white": (255, 255, 255), "red": (203, 0, 0), "yellow": (246, 198, 50)})
        m = fit(c, ~c["white"])
        y = smooth(m["yellow"], 1.5)
        lab, n = label8(y)
        width = ndi.maximum(ndi.distance_transform_edt(y), lab, range(1, n + 1))
        area = ndi.sum(y, lab, range(1, n + 1))
        wide = np.zeros(n + 1, bool)
        wide[1:] = np.asarray(width) > 9
        tiny = np.zeros(n + 1, bool)
        tiny[1:] = np.asarray(area) < 0.004 * y.size
        head = ndi.binary_fill_holes(wide[lab])
        strokes = y & ~wide[lab] & ~tiny[lab]
        features = centre_lines(smooth(head & m["red"] & ndi.binary_erosion(head, disk(3)), 1), 15, 5)
        return centre_lines(strokes, 20, 6), head, features
    strokes, head, features = cached("gorb", make)
    a = np.maximum(line_alpha(strokes, lw), edge_alpha(head, lw))
    if simple:
        return a
    return np.maximum(a, line_alpha(features, lw * 0.8))


def cons_masks():
    def make():
        c = load_classes(SRC / "cons.png", {"white": (255, 255, 255), "red": (200, 0, 0), "yellow": (250, 200, 30)})
        m = fit({"ink": ~c["white"], "yellow": c["yellow"]}, ~c["white"])
        star = ndi.binary_fill_holes(smooth(m["ink"], 2))
        return star, smooth(m["yellow"], 2), c["yellow"]
    return cached("cons", make)


def trace_cons(lw=LINE_W, simple=False):
    """Hammer and sickle in a star: the star's contour, the hammer and sickle as centre lines."""
    star, yellow, _ = cons_masks()
    hs = centre_lines(yellow, 20, 8)
    return np.maximum(edge_alpha(star, lw), line_alpha(hs, lw * 1.2))


def trace_orth(lw=LINE_W, simple=False):
    """Lenin and Stalin: the source is already monoline line art; its strokes are thinned to centre lines."""
    def make():
        c = load_classes(SRC / "orth.png", {"white": (255, 255, 255), "black": (0, 0, 0)})
        m = fit(c, c["black"])
        return centre_lines(smooth(m["black"], 1.5), 40, 8)
    return line_alpha(cached("orth", make), lw)


TRACERS = {"dem": trace_dem, "gorb": trace_gorb, "cons": trace_cons, "orth": trace_orth}


def hammer_sickle(size, box, centre):
    """The hammer and sickle of cons.png as a filled float mask on a size x size canvas (box = its side in px)."""
    _, _, y_full = cons_masks()
    y_full = keep_largest(y_full, 1)                         # the hammer and sickle, not the anti-aliasing specks
    ys, xs = np.nonzero(y_full)
    crop = y_full[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    hh, ww = crop.shape
    s = box / max(hh, ww)
    im = Image.fromarray((crop * 255).astype(np.uint8)).resize((max(1, round(ww * s * SS)), max(1, round(hh * s * SS))),
                                                                Image.LANCZOS)
    big = Image.new("L", (size * SS, size * SS), 0)
    big.paste(im, (round((centre[0] - ww * s / 2) * SS), round((centre[1] - hh * s / 2) * SS)))
    return np.asarray(big, np.float64) / 255


def lw_for(size, px):
    """Work-resolution line width that ends up px wide in a size px icon."""
    return px * WORK / size


def clean(alpha):
    """Drop specks (tiny stray components) from a traced alpha."""
    keep = drop_small(alpha > 0.3, 0.0015 * alpha.size)
    return alpha * ndi.binary_dilation(keep, iterations=3)


def emblem(alpha, colour, size, fill_dark=0.62, fill_a=0.85, lift=0.18, halo=0.75, out=None):
    """A traced line-art alpha (WORK x WORK) as an icon: light line in the colour, a dark tinted fill inside its closed
    outline, a soft dark halo. Returns a size x size RGBA image (or out=(w, h) with the icon centred in it)."""
    alpha = clean(alpha)
    region = ndi.binary_fill_holes(ndi.binary_closing(alpha > 0.35, disk(3))).astype(np.float64)
    la = np.clip(fdown(alpha, size, size) * 1.2, 0, 1)
    ra = fdown(region, size, size) * fill_a
    c = canvas(size, size)
    c = layer(c, (8, 6, 5), shadow(np.maximum(la, ra), 1, 0.5, halo))
    if fill_a:
        c = layer(c, mix(colour, (0, 0, 0), fill_dark), ra)
    c = layer(c, mix(colour, (255, 255, 255), lift), la)
    img = finish(c)
    if out:
        o = Image.new("RGBA", out, (0, 0, 0, 0))
        o.alpha_composite(img, ((out[0] - size) // 2, (out[1] - size) // 2))
        return o
    return img


def logo_icon(k, colour):
    """The 48 px card logo: line art in the faction colour (lifted a little so the dark red reads on the panel), a
    faint dark fill and a soft dark halo."""
    return emblem(TRACERS[k](LINE_W), colour, LOGO, fill_dark=0.7, fill_a=0.55, lift=0.18, halo=0.6)


# ======================================================================================================================
# Icons
# ======================================================================================================================
DEC_W, DEC_H = 32, 31
DEC_ICON = 30                    # traced icons: the square they are fitted into, centred in DEC_W x DEC_H
INK = (26, 22, 18)               # interior detail lines of the solid icons (#1A1612)
RIM = (18, 15, 13)               # their outer rim (#120F0D)


def mid(c, t=0.12):
    """A faction colour slightly darkened: the mid-tone fill of the solid icons."""
    return mix(c, (0, 0, 0), t)


# --- procedural masks: float arrays at SS x (h * SS, w * SS), coordinates in output pixels ------------------------
def _mask(w, h, draw):
    im = Image.new("L", (w * SS, h * SS), 0)
    draw(ImageDraw.Draw(im))
    return np.asarray(im, np.float64) / 255


def _sc(pts):
    return [(x * SS, y * SS) for x, y in pts]


def m_poly(w, h, pts):
    return _mask(w, h, lambda d: d.polygon(_sc(pts), fill=255))


def m_ellipse(w, h, box):
    return _mask(w, h, lambda d: d.ellipse([v * SS for v in box], fill=255))


def m_lines(w, h, lines, width=1.0):
    """Polylines of the given width (px); round joints and caps."""
    r = width * SS / 2

    def draw(d):
        for pts in lines:
            sp = _sc(pts)
            d.line(sp, fill=255, width=max(1, round(width * SS)), joint="curve")
            for x, y in (sp[0], sp[-1]):
                d.ellipse([x - r, y - r, x + r, y + r], fill=255)
    return _mask(w, h, draw)


def m_arc(w, h, box, start, end, width=1.0):
    return _mask(w, h, lambda d: d.arc([v * SS for v in box], start, end, fill=255, width=max(1, round(width * SS))))


def rot(pts, ang, c):
    """Rotate points by ang degrees (clockwise on screen) around c."""
    a = ang * pi / 180
    return [(c[0] + (x - c[0]) * cos(a) - (y - c[1]) * sin(a), c[1] + (x - c[0]) * sin(a) + (y - c[1]) * cos(a))
            for x, y in pts]


def rect(cx, cy, w, h):
    return [(cx - w / 2, cy - h / 2), (cx + w / 2, cy - h / 2), (cx + w / 2, cy + h / 2), (cx - w / 2, cy + h / 2)]


def lens(p0, p1, width, n=12):
    """A leaf: a pointed lens from p0 to p1, width px at its middle."""
    (x0, y0), (x1, y1) = p0, p1
    L = np.hypot(x1 - x0, y1 - y0)
    ux, uy = (x1 - x0) / L, (y1 - y0) / L
    pts = []
    for side in (1, -1):
        rng = range(n + 1) if side == 1 else range(n, -1, -1)
        for k in rng:
            t = k / n
            off = side * width / 2 * sin(pi * t)
            pts.append((x0 + ux * L * t - uy * off, y0 + uy * L * t + ux * off))
    return pts


def m_hammer_sickle(w, h, box, centre, ang=0.0):
    """The hammer and sickle of cons.png, filled, box px on its long side, rotated ang degrees (clockwise)."""
    _, _, y_full = cons_masks()
    y_full = keep_largest(y_full, 1)
    ys, xs = np.nonzero(y_full)
    crop = Image.fromarray((y_full[ys.min():ys.max() + 1, xs.min():xs.max() + 1] * 255).astype(np.uint8))
    s = box * SS / max(crop.size)
    crop = crop.resize((max(1, round(crop.width * s)), max(1, round(crop.height * s))), Image.LANCZOS)
    if ang:
        crop = crop.rotate(-ang, Image.BICUBIC, expand=True)
    big = Image.new("L", (w * SS, h * SS), 0)
    big.paste(crop, (round(centre[0] * SS - crop.width / 2), round(centre[1] * SS - crop.height / 2)))
    return np.asarray(big, np.float64) / 255


def place(work_mask, size, w, h):
    """A WORK x WORK traced mask scaled to size px and centred in a w x h canvas at SS x."""
    im = Image.fromarray((np.clip(work_mask, 0, 1) * 255).astype(np.uint8)).resize((size * SS, size * SS), Image.BOX)
    big = Image.new("L", (w * SS, h * SS), 0)
    big.paste(im, (((w - size) * SS) // 2, ((h - size) * SS) // 2))
    return np.asarray(big, np.float64) / 255


def solid(w, h, region, colour, lines=None, extras=(), rim=1.0, halo=0.7):
    """The one rendering of every small icon: a solid mid-tone fill (a little lighter at the top, darker at the
    bottom, no highlight), extra flat-colour shapes, 1 px dark interior lines, a 1 px dark rim and a soft halo.
    All masks are floats at SS x."""
    reg = region > 0.5
    rim_m = ndi.binary_dilation(reg, disk(max(1, round(rim * SS)))) if rim else reg
    R = fdown(region, w, h)
    RM = fdown(rim_m.astype(np.float64), w, h)
    ys, _ = np.nonzero(reg)
    y0, y1 = ys.min() / SS, ys.max() / SS
    yy = (np.arange(h)[:, None] + 0.5 - y0) / max(1.0, y1 - y0)
    k = (1.06 - 0.20 * np.clip(yy, 0, 1))[:, :, None] * np.ones((1, w, 1))
    fill = np.clip(np.array(colour, np.float64)[None, None] * k, 0, 255)
    c = canvas(w, h)
    c = layer(c, (8, 6, 5), shadow(RM, 1, 0.6, halo))
    c = layer(c, RIM, RM)
    c = layer(c, fill, R)
    for col, m in extras:
        c = layer(c, col, fdown(m, w, h))
    if lines is not None:
        c = layer(c, INK, np.clip(fdown(lines, w, h) * 1.15, 0, 1))
    return finish(c)


def traced_solid(name, colour, size, w, h, line_px=1.0):
    """A generated monoline icon (tools/src/plenum/icon_*.png) in the solid rendering: its closed outline is the
    fill, all its strokes become the dark lines."""
    def make():
        c = load_classes(SRC / f"{name}.png", {"white": (255, 255, 255), "black": (0, 0, 0)})
        m = fit(c, c["black"], 1)
        return centre_lines(smooth(m["black"], 1.5), 40, 8)
    skel = cached(name, make)
    lines = clean(line_alpha(skel, lw_for(size, line_px)))
    region = ndi.binary_fill_holes(ndi.binary_closing(lines > 0.35, disk(3))).astype(np.float64)
    return solid(w, h, place(region, size, w, h), colour, place(lines, size, w, h), rim=0.6)


# --- decision icons (32 x 31) ----------------------------------------------------------------------------------------
def dec_lean_dem(colour):
    """A rose: a solid head with three dark petal strokes on a short stem with two leaves."""
    w, h = DEC_W, DEC_H
    head = np.maximum.reduce([m_ellipse(w, h, (9.4, 4.6, 22.6, 16.4)), m_poly(w, h, [(10.0, 11.0), (22.0, 11.0), (16, 18.6)]),
                              m_ellipse(w, h, (9.8, 2.6, 16.6, 9.4)), m_ellipse(w, h, (15.4, 2.6, 22.2, 9.4))])
    stem = m_lines(w, h, [[(16, 17.5), (15.5, 22.5), (16.2, 28.6)]], 1.8)
    leaf_l = m_poly(w, h, lens((15.7, 23.2), (8.6, 19.6), 4.4))
    leaf_r = m_poly(w, h, lens((16.0, 25.6), (23.4, 22.6), 4.2))
    green = np.maximum(stem, np.maximum(leaf_l, leaf_r))
    lines = np.maximum.reduce([
        m_arc(w, h, (13.0, 5.4, 19.0, 11.4), 160, 430),                         # the spiral at the centre
        m_lines(w, h, [[(11.6, 8.4), (12.4, 12.0), (14.2, 14.6), (16, 15.6)],     # the outer petals
                       [(20.4, 8.4), (19.6, 12.0), (17.8, 14.6), (16, 15.6)]], 1.1),
        m_lines(w, h, [[(16, 3.4), (16, 5.0)]], 1.0),                               # the notch between the top petals
        m_lines(w, h, [[(15.4, 22.9), (11.0, 20.6)], [(16.4, 25.3), (21.2, 23.2)]], 0.8),   # leaf veins
    ])
    return solid(w, h, np.maximum(head, green), mid(colour), lines,
                 extras=[(mix(colour, (0, 0, 0), 0.45), green * (1 - head))])


def dec_lean_gorb(colour):
    """A red party card tilted 10 degrees with a gold hammer and sickle; two dark lines stand for the text."""
    w, h = DEC_W, DEC_H
    c, ang = (16, 15.5), -10
    card = m_poly(w, h, rot(rect(16, 15.5, 18.5, 24), ang, c))
    border = m_lines(w, h, [rot(rect(16, 15.5, 14.5, 20) + [rect(16, 15.5, 14.5, 20)[0]], ang, c)], 0.8)
    text = m_lines(w, h, [rot([(11.5, 21.6), (20.5, 21.6)], ang, c), rot([(12.8, 24.0), (19.2, 24.0)], ang, c)], 1.0)
    hs = m_hammer_sickle(w, h, 10.5, rot([(16, 13.2)], ang, c)[0], ang)
    return solid(w, h, card, mid(colour, 0.15), np.maximum(border * 0.8, text), extras=[(GOLD, hs)])


def dec_lean_cons(colour):
    """The star with the hammer and sickle in dark."""
    w, h = DEC_W, DEC_H
    star = m_poly(w, h, star_pts(16, 16.6, 15.2, 0.42))
    hs = m_hammer_sickle(w, h, 12.0, (16, 16.6))
    return solid(w, h, star, mid(colour, 0.05), extras=[((70, 26, 18), hs)])


LENIN = [(9.0, 30.0), (9.2, 27.2), (11.0, 24.2), (10.4, 21.0), (8.8, 17.6), (8.4, 13.0), (9.4, 8.6), (11.8, 5.1),
         (15.4, 3.2), (19.4, 3.3), (22.4, 5.1), (24.1, 8.3), (24.6, 11.4), (24.1, 12.7), (25.2, 14.6), (26.8, 17.1),
         (25.1, 17.9), (25.7, 19.1), (25.0, 20.3), (25.5, 21.6), (24.4, 24.8), (22.4, 25.0), (20.4, 23.4),
         (19.1, 23.8), (20.6, 26.6), (23.8, 30.0)]


def dec_lean_orth(colour):
    """One solid profile of Lenin facing right: bald dome, moustache and pointed goatee; ear, brow, mouth, beard
    line and the coat collar as dark lines."""
    w, h = DEC_W, DEC_H
    head = m_poly(w, h, LENIN)
    lines = np.maximum.reduce([
        m_arc(w, h, (12.6, 12.2, 16.4, 17.8), 90, 270),                           # ear
        m_lines(w, h, [[(21.8, 11.9), (23.8, 12.3)]]),                              # brow
        m_lines(w, h, [[(25.0, 20.2), (23.4, 20.4)]]),                              # mouth
        m_lines(w, h, [[(11.0, 25.8), (15.6, 25.0), (19.6, 25.4)], [(16.4, 25.2), (18.8, 30.0)]]),   # collar, lapel
    ])
    beard = m_poly(w, h, [(25.1, 17.9), (25.7, 19.1), (25.0, 20.3), (25.5, 21.6), (24.4, 24.8), (22.4, 25.0),
                          (20.4, 23.4), (18.8, 21.0), (18.2, 18.4), (20.6, 18.9), (23.0, 18.3)])
    return solid(w, h, head, mid(colour, 0.0), lines, extras=[(mix(colour, (0, 0, 0), 0.5), beard * head)])


def dec_purge(colour):
    """A party card torn in two by a zig-zag tear, the halves turned apart at the top; a small hammer and sickle on
    the left half."""
    w, h = DEC_W, DEC_H
    L, R, T, B = 6.6, 25.4, 4.6, 27.4
    tear = [(17.0, T), (15.0, 8.4), (17.8, 11.8), (15.0, 15.4), (17.8, 19.0), (15.4, 22.6), (16.6, B)]
    left = [(L, T)] + tear + [(L, B)]
    right = tear + [(R, B), (R, T)]

    def lt(pts):
        return rot([(x - 1.2, y) for x, y in pts], -8, (16.0, B))

    def rt(pts):
        return rot([(x + 1.2, y) for x, y in pts], 8, (16.6, B))
    region = np.maximum(m_poly(w, h, lt(left)), m_poly(w, h, rt(right)))
    lines = m_lines(w, h, [lt([(8.8, 21.4), (13.0, 21.4)]), lt([(8.8, 23.8), (12.2, 23.8)]),
                           rt([(19.4, 22.6), (23.2, 22.6)]), rt([(20.0, 25.0), (23.2, 25.0)])], 0.9)
    hs = m_hammer_sickle(w, h, 7.5, lt([(11.0, 11.0)])[0], -8)
    return solid(w, h, region, colour, lines, extras=[(TAN, hs)])


def dec_open_tribune(colour):
    """A period stand microphone in front of a TV studio camera on a tripod (the camera at half strength)."""
    w, h = DEC_W, DEC_H
    cam_body = m_poly(w, h, [(15.6, 5.4), (28.6, 5.4), (28.6, 14.4), (15.6, 14.4)])
    cam_lens = m_poly(w, h, [(11.6, 7.0), (15.8, 7.6), (15.8, 12.2), (11.6, 12.8)])
    cam_hood = m_poly(w, h, [(18.0, 3.2), (25.0, 3.2), (25.0, 5.6), (18.0, 5.6)])
    tripod = m_lines(w, h, [[(22.2, 14.6), (17.8, 29.2)], [(22.2, 14.6), (22.2, 29.2)],
                            [(22.2, 14.6), (27.6, 29.2)]], 1.3)
    cam = np.maximum.reduce([cam_body, cam_lens, cam_hood, tripod])
    cam_img = solid(w, h, cam, mix(colour, PANEL, 0.5), m_lines(w, h, [[(19.0, 9.9), (26.0, 9.9)]], 0.8),
                    rim=0.8, halo=0.4)
    head = m_ellipse(w, h, (6.6, 4.2, 15.0, 15.6))
    neck = m_poly(w, h, [(9.9, 15.0), (11.7, 15.0), (11.7, 18.2), (9.9, 18.2)])
    pole = m_lines(w, h, [[(10.8, 18.0), (10.8, 26.4)]], 1.6)
    base = m_ellipse(w, h, (5.6, 25.2, 16.0, 29.4))
    mic = np.maximum.reduce([head, neck, pole, base])
    grille = m_lines(w, h, [[(7.4, 7.8), (14.2, 7.8)], [(6.9, 10.0), (14.7, 10.0)], [(7.4, 12.2), (14.2, 12.2)]], 0.8)
    mic_img = solid(w, h, mic, colour, grille, rim=1.0, halo=0.6)
    cam_img.alpha_composite(mic_img)
    return cam_img


DEC_DRAW = {"lean_dem": dec_lean_dem, "lean_gorb": dec_lean_gorb, "lean_cons": dec_lean_cons,
            "lean_orth": dec_lean_orth, "purge": dec_purge, "open_tribune": dec_open_tribune}


def decision_icon(d, src, colour):
    if d in DEC_DRAW:
        return DEC_DRAW[d](colour)
    return traced_solid(src, colour, DEC_ICON, DEC_W, DEC_H)


# --- window icons ----------------------------------------------------------------------------------------------------
def icon_rad():
    """The raised fist in the solid rendering."""
    return traced_solid("icon_fist", RAD_ICON, ROW_ICON, ROW_ICON, ROW_ICON, 0.9)


STATUS_ICON = 16


def icon_status():
    """The chairman's gavel: a solid tan head tilted over its sound block, the handle to the lower right."""
    s = STATUS_ICON
    c, ang = (6.4, 6.4), 45
    head = m_poly(s, s, rot(rect(6.4, 6.4, 4.6, 9.4), ang, c))
    bands = m_lines(s, s, [rot([(4.1, 3.6), (8.7, 3.6)], ang, c), rot([(4.1, 9.2), (8.7, 9.2)], ang, c)], 0.8)
    handle = m_lines(s, s, [[(8.0, 8.0), (14.2, 14.2)]], 1.7)
    block = m_poly(s, s, [(1.2, 12.6), (9.0, 12.6), (9.0, 15.0), (1.2, 15.0)])
    return solid(s, s, np.maximum.reduce([head, handle, block]), mix(TAN, (255, 255, 255), 0.05), bands, rim=0.8)


def icon_str():
    """A shield in party red with a thin light outline and the hammer and sickle in tan."""
    s = ROW_ICON
    top, bot, l, r = 1.6, 18.6, 3.0, 17.0
    pts = [(l, top), (r, top), (r, 9.5)]
    for k in range(1, 13):                                  # the two curved sides meet in a point at the bottom
        t = k / 12
        pts.append((r + (s / 2 - r) * t, 9.5 + (bot - 9.5) * (t ** 0.8)))
    left = [(l + (s / 2 - l) * (k / 12), 9.5 + (bot - 9.5) * ((k / 12) ** 0.8)) for k in range(12, 0, -1)]
    pts += left[1:] + [(l, 9.5)]
    shield = poly_mask(s, s, pts)
    inner = ndi.binary_erosion(shield, iterations=round(1.1 * SS)).astype(np.float64)
    hs = m_hammer_sickle(s, s, 9.6, (s / 2, 8.8))
    return solid(s, s, shield.astype(np.float64), mix(PARTY_RED, (255, 255, 255), 0.18),
                 extras=[(mix(PARTY_RED, (0, 0, 0), 0.45), inner), (TAN, hs * inner)], rim=0.8)


BADGE = 14


def icon_ruling():
    """The ruling badge: a solid cream-gold star with a 1 px dark outline, straddling the top edge of the card."""
    s = BADGE
    outer = m_poly(s, s, star_pts(s / 2, s / 2 + 0.5, 6.9, 0.45))
    inner = m_poly(s, s, star_pts(s / 2, s / 2 + 0.5, 5.6, 0.45))
    c = canvas(s, s)
    c = layer(c, (8, 6, 5), shadow(fdown(outer, s, s), 1, 0.5, 0.6))
    c = layer(c, (26, 22, 18), fdown(outer, s, s))
    c = layer(c, CREAM, fdown(inner, s, s))
    return finish(c)


EMBLEM = 32


def icon_emblem():
    """The gold hammer and sickle left of the title."""
    s = EMBLEM
    hs = hammer_sickle(s, 27, (s / 2, s / 2))
    c = canvas(s * SS, s * SS)
    c = layer(c, mix(GOLD, (255, 255, 255), 0.05), hs)
    img = down(finish(c), s, s)
    a = np.asarray(img, np.float64)[:, :, 3] / 255
    base = finish(layer(canvas(s, s), (6, 4, 4), shadow(a, 1, 0.8, 0.8)))
    base.alpha_composite(img)
    return base


CAT_ICON = (52, 40)


def build_cat_icon():
    """52x40 category icon: a dark red medallion with a gold ring and a small hemicycle in the four faction colours
    (shares as at the start), the presidium as a gold bar under it."""
    w, h = CAT_ICON
    x, y = grid(w, h)
    cx, cy, R = w / 2, h / 2, 18.5
    d = np.hypot(x - cx, y - cy)
    c = canvas(w * SS, h * SS)
    c = layer(c, (6, 5, 4), np.clip(R + 1.6 - d + 0.5, 0, 1) * 0.75)
    c = layer(c, mix(GOLD, (0, 0, 0), 0.1), np.clip(R - d + 0.5, 0, 1))
    disc = np.clip(R - 1.6 - d + 0.5, 0, 1)
    c = layer(c, (78, 24, 20), disc)
    c = layer(c, (0, 0, 0), disc * np.clip((d - 8) / 10, 0, 1) * 0.35)      # darker towards the ring
    hy = cy + 3.5
    supports = [f[6] for f in FACTIONS]
    edges = np.cumsum([0] + supports) / 100 * pi                            # from the left
    for r, n in ((6.0, 5), (9.5, 8), (13.0, 11)):                           # three rows of seats, as in the hall
        for j in range(n):
            a = pi * (j + 0.5) / n                                          # from the left
            f = FACTIONS[min(3, int(np.searchsorted(edges[1:], a, side="right")))]
            sx, sy = cx - r * cos(a), hy - r * sin(a)
            c = layer(c, mix(f[1], (40, 30, 26), 0.1), np.clip(1.4 - np.hypot(x - sx, y - sy) + 0.5, 0, 1))
    c = layer(c, GOLD, poly_mask(w, h, [(cx - 7, hy + 2.2), (cx + 7, hy + 2.2), (cx + 7, hy + 4.0),
                                        (cx - 7, hy + 4.0)]))
    return down(finish(c), w, h)


# ======================================================================================================================
# Text files
# ======================================================================================================================
def write(path, text, bom=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(("﻿" if bom else "").encode("utf-8") + text.encode("utf-8"))
    print("wrote", path.relative_to(ROOT).as_posix())


def window_sprites():
    """(name, texture, frames) of everything the window and the decisions use."""
    s = [("GFX_totu_pl_header", "header", 1), ("GFX_totu_pl_emblem", "icon_emblem", 1),
         ("GFX_totu_pl_status_icon", "icon_status", 1), ("GFX_totu_pl_rule", "rule", 1),
         ("GFX_totu_pl_floor", "floor", 1), ("GFX_totu_pl_presidium", "presidium", 1),
         ("GFX_totu_pl_majority", "majority", 1), ("GFX_totu_pl_majority_tick", "majority_tick", 1),
         ("GFX_totu_pl_seat", "seat", 4)]
    for k in KEYS:
        s += [(f"GFX_totu_pl_card_{k}", f"card_{k}", 1), (f"GFX_totu_pl_card_ruling_{k}", f"card_ruling_{k}", 1),
              (f"GFX_totu_pl_support_{k}", f"support_{k}", FRAMES), (f"GFX_totu_pl_logo_{k}", f"logo_{k}", 1)]
    s += [("GFX_totu_pl_ruling", "icon_ruling", 1),
          ("GFX_totu_pl_bar_rad", "bar_rad", FRAMES), ("GFX_totu_pl_bar_str", "bar_str", FRAMES),
          ("GFX_totu_pl_icon_rad", "icon_rad", 1), ("GFX_totu_pl_icon_str", "icon_str", 1)]
    s += [(f"GFX_decision_totu_pl_{d}", f"decisions/totu_pl_{d}", 1) for d, *_ in DECISION_ICONS]
    s += [("GFX_decision_category_totu_plenum", "decisions/category_totu_plenum", 1),
          ("GFX_decision_cat_picture_totu_plenum", "decisions/cat_picture_totu_plenum", 1)]
    return s


def build_gfx():
    rows = [f"# {MARK} - edit the script, not this file.", "spriteTypes = {"]
    for name, tex, frames in window_sprites():
        rows.append("\tspriteType = {")
        rows.append(f'\t\tname = "{name}"')
        rows.append(f'\t\ttexturefile = "{GFX_DIR}/{tex}.dds"')
        if frames > 1:
            rows.append(f"\t\tnoOfFrames = {frames}")
        rows.append("\t}")
    rows.append("}")
    write(ROOT / "interface/totu_plenum.gfx", "\n".join(rows) + "\n")


def card_x(i):
    return M + i * (CARD_W + CARD_GAP)


ROW_LABEL_X, ROW_LABEL_W = 34, 106
VALUE_X, VALUE_W = BAR_X + BAR_W + 4, 28
STATE_X = VALUE_X + VALUE_W + 8


def build_gui():
    o = [f"# {MARK} - edit the script, not this file.",
         "# The Plenum window shown in the decision category TOTU_plenum_category (scripted_gui TOTU_plenum_gui).",
         "guiTypes = {", "\tcontainerWindowType = {", '\t\tname = "TOTU_plenum_window"',
         "\t\tposition = { x = 0 y = 0 }", f"\t\tsize = {{ width = 100% height = {WIN_H} }}", ""]

    def text(name, x, y, w, h, font, key, fmt="left", tooltip=None, colour=None):
        o.extend(["\t\tinstantTextBoxType = {", f'\t\t\tname = "{name}"', f"\t\t\tposition = {{ x = {x} y = {y} }}",
                  f'\t\t\tfont = "{font}"', f'\t\t\ttext = "{key}"', f"\t\t\tmaxWidth = {w}", f"\t\t\tmaxHeight = {h}",
                  f"\t\t\tformat = {fmt}"])
        if colour:
            o.append(f'\t\t\ttext_color_code = "{colour}"')
        if tooltip:
            o.append(f"\t\t\tpdx_tooltip = {tooltip}")
        o.append("\t\t}")

    def icon(name, sprite, x, y):
        o.extend(["\t\ticonType = {", f'\t\t\tname = "{name}"', f'\t\t\tspriteType = "{sprite}"',
                  f"\t\t\tposition = {{ x = {x} y = {y} }}", "\t\t}"])

    def tip(name, x, y, w, h, key):
        """An empty text box over an area: the vanilla way to give icons a tooltip (raj_local_leaders_*.gui)."""
        o.extend(["\t\tinstantTextBoxType = {", f'\t\t\tname = "{name}"', f"\t\t\tposition = {{ x = {x} y = {y} }}",
                  f"\t\t\tmaxWidth = {w}", f"\t\t\tmaxHeight = {h}", f"\t\t\tpdx_tooltip = {key}", "\t\t}"])

    def section(name, y, key):
        text(f"section_{name}", M, y, RULE_W, 16, "hoi_16mbs", key, "left", colour="L")
        icon(f"rule_{name}", "GFX_totu_pl_rule", M, y + SEC_LABEL_H)

    o.append("\t\t# header: banner, emblem, title (tan), status line (grey) with the gavel")
    icon("header", "GFX_totu_pl_header", 0, 0)
    icon("emblem", "GFX_totu_pl_emblem", 10, (HEADER_H - EMBLEM) // 2)
    text("plenum_title", 52, 7, WIN_W - 52 - M, 20, "hoi_20bs", "TOTU_plenum_title", "left", colour="L")
    icon("status_icon", "GFX_totu_pl_status_icon", 52, 31)
    text("plenum_status", 74, 31, WIN_W - 74 - M, 16, "hoi_16mbs", "TOTU_pl_status_line", "left", colour="g")
    tip("status_tooltip", 48, 28, WIN_W - 48 - M, 20, "TOTU_pl_status_tt")
    o.append("")
    o.append(f"\t\t# the hall: {SEATS} seats in rows of {', '.join(map(str, ROWS))}; seat K is the K-th seat handed to the "
             "rows")
    o.append("\t\t# by the Sainte-Lague method (build_plenum.hall_seats), so the factions form radial wedges")
    section("hall", SEC_HALL_Y, "TOTU_pl_sec_hall")
    fw, fh = floor_size()
    icon("hall_floor", "GFX_totu_pl_floor", HALL_CX - fw // 2, HALL_CY - FLOOR_R - 1)
    icon("majority_mark", "GFX_totu_pl_majority", HALL_CX - MAJ_W // 2, HALL_CY - FLOOR_R + 1)
    icon("majority_tick", "GFX_totu_pl_majority_tick", HALL_CX - TICK_W // 2, HALL_CY - PIT_R + 3)
    for i, (x, y) in enumerate(hall_seats(), 1):
        icon(f"seat_{i}", "GFX_totu_pl_seat", x, y)
    icon("presidium", "GFX_totu_pl_presidium", HALL_CX - PRESIDIUM_W // 2, HALL_CY + 9 - PRESIDIUM_H)
    o.append("\t\t# legends beside the hall: seats on the left, the majority (with its gold notch) on the right")
    rx = WIN_W - M - LEGEND_W
    text("seats_total_value", M, HALL_CY - 30, LEGEND_W, 20, "hoi_20bs", "TOTU_pl_seats_total_value", "right",
         colour="L")
    text("seats_total_label", M, HALL_CY - 8, LEGEND_W, 16, "hoi_16mbs", "TOTU_pl_seats_total_label", "right",
         colour="g")
    icon("majority_legend_mark", "GFX_totu_pl_majority", rx, HALL_CY - 22)
    text("majority_value", rx + MAJ_W + 4, HALL_CY - 30, LEGEND_W - MAJ_W - 4, 20, "hoi_20bs",
         "TOTU_pl_majority_value", "left", colour="L")
    text("majority_label", rx, HALL_CY - 8, LEGEND_W, 16, "hoi_16mbs", "TOTU_pl_majority_label", "left", colour="g")
    top = HALL_CY - FLOOR_R
    tip("hall_tooltip", M, top, WIN_W - 2 * M, FLOOR_R + FLOOR_DROP, "TOTU_pl_hall_tt")
    o.append("")
    o.append("\t\t# faction cards: logo, percentage, name, seats, support bar; lighter card, cream border and star "
             "when ruling")
    section("factions", SEC_FAC_Y, "TOTU_pl_sec_factions")
    for i, k in enumerate(KEYS):
        x0, y0 = card_x(i), CARD_Y
        o.append(f"\t\t# {k}")
        icon(f"card_{k}", f"GFX_totu_pl_card_{k}", x0, y0)
        icon(f"card_ruling_{k}", f"GFX_totu_pl_card_ruling_{k}", x0, y0)
        icon(f"logo_{k}", f"GFX_totu_pl_logo_{k}", x0 + (CARD_W - LOGO) // 2, y0 + 6)
        text(f"pct_{k}", x0 + 4, y0 + 55, CARD_W - 8, 24, "hoi_24header", f"TOTU_pl_{k}_pct", "centre")
        text(f"name_{k}", x0 + 4, y0 + 78, CARD_W - 8, 16, "hoi_16mbs", f"TOTU_pl_{k}_card", "centre")
        text(f"seats_{k}", x0 + 4, y0 + 93, CARD_W - 8, 16, "hoi_16mbs", f"TOTU_pl_{k}_seats_line", "centre",
             colour="g")
        icon(f"support_{k}", f"GFX_totu_pl_support_{k}", x0 + (CARD_W - SUP_W) // 2, y0 + 109)
        icon(f"ruling_{k}", "GFX_totu_pl_ruling", x0 + CARD_W // 2 - BADGE // 2, y0 - BADGE // 2)
        tip(f"tooltip_{k}", x0, y0, CARD_W, CARD_H, f"TOTU_pl_{k}_tt")
    o.append("")
    o.append("\t\t# party state: icon, label, segmented bar, value, state word")
    section("party", SEC_PARTY_Y, "TOTU_pl_sec_party")
    for y, k in zip(ROW_Y, ("rad", "str")):
        icon(f"icon_{k}", f"GFX_totu_pl_icon_{k}", M, y + 1)
        text(f"label_{k}", ROW_LABEL_X, y + 3, ROW_LABEL_W, 16, "hoi_16mbs", f"TOTU_pl_{k}_label", "left")
        icon(f"bar_{k}", f"GFX_totu_pl_bar_{k}", BAR_X, y + 3)
        text(f"value_{k}", VALUE_X, y + 3, VALUE_W, 16, "hoi_16mbs", f"TOTU_pl_{k}_value", "right")
        text(f"state_{k}", STATE_X, y + 3, WIN_W - M - STATE_X, 16, "hoi_16mbs", f"TOTU_pl_{k}_state_line", "left")
        tip(f"tooltip_{k}", M, y, WIN_W - 2 * M, 22, f"TOTU_pl_{k}_tt")
    o.extend(["\t}", "}"])
    write(ROOT / "interface/totu_plenum.gui", "\n".join(o) + "\n")


def build_scripted_gui():
    o = [f"# {MARK} - edit the script, not this file.",
         "# Frames of the Plenum window come from variables kept by TOTU_pl_update_gfx",
         "# (common/scripted_effects/TOTU_plenum_generated.txt), which also bumps TOTU_pl_dirty.",
         "scripted_gui = {", "\tTOTU_plenum_gui = {", "\t\tcontext_type = decision_category",
         '\t\twindow_name = "TOTU_plenum_window"', "", "\t\tproperties = {"]
    for i in range(1, SEATS + 1):
        o.append(f"\t\t\tseat_{i} = {{ frame = TOTU_pl_seat_{i} }}")
    for k in KEYS:
        o.append(f"\t\t\tsupport_{k} = {{ frame = TOTU_pl_col_{k} }}")
    o.append("\t\t\tbar_rad = { frame = TOTU_pl_rad_frame }")
    o.append("\t\t\tbar_str = { frame = TOTU_pl_str_frame }")
    o.extend(["\t\t}", "", "\t\t# the faction that won the vote (TOTU_pl_conclude) gets the ruling card and the star",
              "\t\ttriggers = {"])
    for num, k in enumerate(KEYS, 1):
        cond = f"has_country_flag = TOTU_plenum_concluded check_variable = {{ TOTU_pl_ruling = {num} }}"
        o.append(f"\t\t\tcard_ruling_{k}_visible = {{ {cond} }}")
        o.append(f"\t\t\truling_{k}_visible = {{ {cond} }}")
    o.extend(["\t\t}", "", "\t\tdirty = TOTU_pl_dirty", "\t}", "}"])
    write(ROOT / "common/scripted_guis/TOTU_plenum_scripted_gui.txt", "\n".join(o) + "\n")


def build_scripted_loc():
    o = [f"# {MARK} - edit the script, not this file.",
         "# Texts of the Plenum window that depend on the state (country scope).",
         "", "# status line (loc key TOTU_pl_status_line = \"[TOTU_pl_status]\")",
         "defined_text = {", "\tname = TOTU_pl_status",
         "\ttext = {", "\t\ttrigger = { has_country_flag = TOTU_plenum_in_session }",
         "\t\tlocalization_key = TOTU_pl_status_session", "\t}",
         "\ttext = {", "\t\ttrigger = { has_country_flag = TOTU_plenum_preparing }",
         "\t\tlocalization_key = TOTU_pl_status_preparing", "\t}"]
    for k in KEYS:
        o.extend(["\ttext = {", "\t\ttrigger = {", "\t\t\thas_country_flag = TOTU_plenum_concluded",
                  f"\t\t\thas_country_flag = TOTU_plenum_winner_{k}", "\t\t}",
                  f"\t\tlocalization_key = TOTU_pl_status_ruling_{k}", "\t}"])
    o.extend(["\ttext = {", "\t\tlocalization_key = TOTU_pl_status_idle", "\t}", "}"])

    o.extend(["", "# seat counts with the Russian plural (место / места / мест; English: seat / seats)"])
    forms = {f: [n for n in range(SEATS + 1) if seat_form(n) == f] for f in ("one", "few")}
    for k in KEYS:
        o.extend(["defined_text = {", f"\tname = TOTU_pl_seats_{k}",
                  "\ttext = {", f"\t\ttrigger = {{ check_variable = {{ TOTU_pl_seats_{k} = 1 }} }}",
                  f"\t\tlocalization_key = TOTU_pl_seats_{k}_single", "\t}"])
        for f in ("one", "few"):
            ors = " ".join(f"check_variable = {{ TOTU_pl_seats_{k} = {n} }}" for n in forms[f])
            o.extend(["\ttext = {", f"\t\ttrigger = {{ OR = {{ {ors} }} }}",
                      f"\t\tlocalization_key = TOTU_pl_seats_{k}_{f}", "\t}"])
        o.extend(["\ttext = {", f"\t\tlocalization_key = TOTU_pl_seats_{k}_many", "\t}", "}"])

    o.extend(["", "# one-word state of the party next to the bars"])
    for var, table in (("rad", RAD_WORDS), ("str", STR_WORDS)):
        o.extend(["defined_text = {", f"\tname = TOTU_pl_{var}_state"])
        for (lim, word), (prev, _) in zip(reversed(table[1:]), reversed(table[:-1])):
            o.extend(["\ttext = {", f"\t\ttrigger = {{ check_variable = {{ TOTU_pl_{var} > {prev - 0.01:.2f} }} }}",
                      f"\t\tlocalization_key = TOTU_pl_{var}_{word}", "\t}"])
        o.extend(["\ttext = {", f"\t\tlocalization_key = TOTU_pl_{var}_{table[0][1]}", "\t}", "}"])

    o.extend(["", "# a line in the tooltip of the faction that won the vote"])
    for num, k in enumerate(KEYS, 1):
        o.extend(["defined_text = {", f"\tname = TOTU_pl_ruling_note_{k}",
                  "\ttext = {", "\t\ttrigger = {", "\t\t\thas_country_flag = TOTU_plenum_concluded",
                  f"\t\t\tcheck_variable = {{ TOTU_pl_ruling = {num} }}", "\t\t}",
                  "\t\tlocalization_key = TOTU_pl_ruling_note", "\t}",
                  "\ttext = {", "\t\tlocalization_key = TOTU_pl_empty", "\t}", "}"])
    write(ROOT / "common/scripted_localisation/TOTU_plenum_scripted_loc.txt", "\n".join(o) + "\n")


def build_effects():
    o = [f"# {MARK} - edit the script, not this file.",
         "# Plenum API (docs/superpowers/specs/2026-10-08-plenum-design.md). Hand-written parts:",
         "# common/scripted_effects/TOTU_plenum_effects.txt (TOTU_pl_shift, TOTU_pl_monthly, TOTU_pl_conclude, ...).",
         "", "# --- faction support: +-n points, the others change proportionally (TOTU_pl_shift) ---"]
    for num, k in enumerate(KEYS, 1):
        for n in AMOUNTS:
            for op, sign in (("add", ""), ("sub", "-")):
                o.extend([f"TOTU_pl_{k}_{op}_{n} = {{", f"\tcustom_effect_tooltip = TOTU_pl_{k}_{op}_{n}_tt",
                          "\thidden_effect = {", f"\t\tset_temp_variable = {{ pl_faction = {num} }}",
                          f"\t\tset_temp_variable = {{ pl_amount = {sign}{n} }}", "\t\tTOTU_pl_shift = yes",
                          "\t}", "}"])
    o.append("")
    o.append("# --- radicalization / party strength, kept in 0..100 ---")
    for k in ("rad", "str"):
        for n in AMOUNTS:
            for op, eff in (("add", "add_to_variable"), ("sub", "subtract_from_variable")):
                o.extend([f"TOTU_pl_{k}_{op}_{n} = {{", f"\tcustom_effect_tooltip = TOTU_pl_{k}_{op}_{n}_tt",
                          "\thidden_effect = {", f"\t\t{eff} = {{ TOTU_pl_{k} = {n} }}",
                          f"\t\tclamp_variable = {{ var = TOTU_pl_{k} min = 0 max = 100 }}",
                          "\t\tTOTU_pl_update_modifier = yes", "\t\tTOTU_pl_update_gfx = yes", "\t}", "}"])
    o.append("")
    o.extend(update_gfx_lines())
    write(ROOT / "common/scripted_effects/TOTU_plenum_generated.txt", "\n".join(o) + "\n")


def update_gfx_lines():
    """Seats by the largest remainder method, then the frames of the window. Temp variables plg_* only."""
    o = ["# Recomputes the window: TOTU_pl_seat_1..61 (faction 1..4 of each seat, dem gorb cons orth from the left),",
         "# TOTU_pl_seats_<f> (seats per faction), TOTU_pl_col_<f>, TOTU_pl_rad_frame, TOTU_pl_str_frame (frames 1..21,",
         "# 5 % steps); bumps TOTU_pl_dirty.",
         "TOTU_pl_update_gfx = {", "\t# quotas q = support * 61 / 100, seats s = floor(q), remainders r = q - s"]
    for i, k in enumerate(KEYS, 1):
        o.extend([f"\tset_temp_variable = {{ plg_q{i} = TOTU_pl_{k} }}",
                  f"\tmultiply_temp_variable = {{ plg_q{i} = 0.61 }}",
                  f"\tset_temp_variable = {{ plg_s{i} = plg_q{i} }}",
                  f"\tround_temp_variable = plg_s{i}",
                  f"\tif = {{ limit = {{ check_variable = {{ plg_s{i} > plg_q{i} }} }} "
                  f"subtract_from_temp_variable = {{ plg_s{i} = 1 }} }}",
                  f"\tset_temp_variable = {{ plg_r{i} = plg_q{i} }}",
                  f"\tsubtract_from_temp_variable = {{ plg_r{i} = plg_s{i} }}"])
    o.append(f"\tset_temp_variable = {{ plg_left = {SEATS} }}")
    for i in range(1, 5):
        o.append(f"\tsubtract_from_temp_variable = {{ plg_left = plg_s{i} }}")
    o.append("\t# the seats left over go one by one to the largest remainders (ties: the faction further left)")
    for _ in range(4):
        o.extend(["\tif = {", "\t\tlimit = { check_variable = { plg_left > 0 } }",
                  "\t\tset_temp_variable = { plg_best = 1 }", "\t\tset_temp_variable = { plg_bestr = plg_r1 }"])
        for i in range(2, 5):
            o.append(f"\t\tif = {{ limit = {{ check_variable = {{ plg_r{i} > plg_bestr }} }} "
                     f"set_temp_variable = {{ plg_best = {i} }} set_temp_variable = {{ plg_bestr = plg_r{i} }} }}")
        for i in range(1, 5):
            kw = "if" if i == 1 else "else_if"
            o.append(f"\t\t{kw} = {{ limit = {{ check_variable = {{ plg_best = {i} }} }} "
                     f"add_to_temp_variable = {{ plg_s{i} = 1 }} set_temp_variable = {{ plg_r{i} = -1 }} }}")
        o.extend(["\t\tsubtract_from_temp_variable = { plg_left = 1 }", "\t}"])
    o.append("\t# seats per faction (the cards and their tooltips)")
    for i, k in enumerate(KEYS, 1):
        o.append(f"\tset_variable = {{ TOTU_pl_seats_{k} = plg_s{i} }}")
    o.extend(["\t# cumulative seat counts: seat i belongs to the first faction whose running total reaches i",
              "\tset_temp_variable = { plg_c1 = plg_s1 }",
              "\tset_temp_variable = { plg_c2 = plg_c1 }", "\tadd_to_temp_variable = { plg_c2 = plg_s2 }",
              "\tset_temp_variable = { plg_c3 = plg_c2 }", "\tadd_to_temp_variable = { plg_c3 = plg_s3 }"])
    for i in range(1, SEATS + 1):
        o.extend([f"\tif = {{ limit = {{ check_variable = {{ plg_c1 > {i - 1} }} }} "
                  f"set_variable = {{ TOTU_pl_seat_{i} = 1 }} }}",
                  f"\telse_if = {{ limit = {{ check_variable = {{ plg_c2 > {i - 1} }} }} "
                  f"set_variable = {{ TOTU_pl_seat_{i} = 2 }} }}",
                  f"\telse_if = {{ limit = {{ check_variable = {{ plg_c3 > {i - 1} }} }} "
                  f"set_variable = {{ TOTU_pl_seat_{i} = 3 }} }}",
                  f"\telse = {{ set_variable = {{ TOTU_pl_seat_{i} = 4 }} }}"])
    o.append("\t# support bars and party bars: frame = floor(value / 5) + 1, 1..21")
    pairs = [(f"TOTU_pl_col_{k}", f"TOTU_pl_{k}") for k in KEYS] + \
            [("TOTU_pl_rad_frame", "TOTU_pl_rad"), ("TOTU_pl_str_frame", "TOTU_pl_str")]
    for dst, src in pairs:
        o.extend([f"\tset_variable = {{ {dst} = {src} }}", f"\tdivide_variable = {{ {dst} = 5 }}",
                  f"\tset_temp_variable = {{ plg_f = {dst} }}", f"\tround_variable = {dst}",
                  f"\tif = {{ limit = {{ check_variable = {{ {dst} > plg_f }} }} subtract_from_variable = {{ {dst} = 1 }} }}",
                  f"\tadd_to_variable = {{ {dst} = 1 }}",
                  f"\tclamp_variable = {{ var = {dst} min = 1 max = {FRAMES} }}"])
    o.extend(["\tadd_to_variable = { TOTU_pl_dirty = 1 }", "}"])
    return o


# --- localisation ----------------------------------------------------------------------------------------------------
LOC_FACTION_TT = {
    "dem": ("Радикальные реформаторы в КПСС (Афанасьев, Шостаковский, Лысенко): отмена 6-й статьи, многопартийность и "
            "рынок. Их рост поднимает радикализацию партии.\nПобеда на пленуме: реформы и правый курс "
            "(рыночная демократия).",
            "Radical reformers inside the CPSU (Afanasyev, Shostakovsky, Lysenko): an end to Article 6, a multi-party "
            "system and the market. Their growth raises the party's radicalization.\nIf they win the plenum: reforms "
            "and the right course (market democracy)."),
    "gorb": ("Сторонники генсека: перестройка сверху, обновлённый Союз и социализм с человеческим лицом.\nПобеда на "
             "пленуме: реформы и левый курс (социал-демократия).",
             "The General Secretary's supporters: perestroika from above, a renewed Union and socialism with a human "
             "face.\nIf they win the plenum: reforms and the left course (social democracy)."),
    "cons": ("Аппарат и хозяйственники (Лигачёв, Полозков): порядок, сильный центр и великая держава без "
             "развала.\nПобеда на пленуме: жёсткая линия и правый курс (великая держава).",
             "The apparatus and the managers (Ligachev, Polozkov): order, a strong centre and a great power that "
             "does not fall apart.\nIf they win the plenum: the hard line and the right course (great power)."),
    "orth": ("Общество «Единство» Нины Андреевой и депутатская группа «Союз»: назад к ленинским нормам, без уступок "
             "рынку. Их рост поднимает радикализацию партии.\nПобеда на пленуме: жёсткая линия и левый курс (ленинские нормы).",
             "Nina Andreyeva's Edinstvo society and the Soyuz group of deputies: back to Leninist norms, no "
             "concessions to the market. "
             "Their growth raises the party's radicalization.\nIf they win the plenum: the hard line and the left "
             "course (Leninist norms)."),
}
STATE_WORDS = {
    "ru": {"calm": "§Gспокойная§!", "tense": "§Yнапряжённая§!", "critical": "§Rкритическая§!",
           "weak": "§Rслабая§!", "stable": "§Yустойчивая§!", "strong": "§Gкрепкая§!"},
    "en": {"calm": "§Gcalm§!", "tense": "§Ytense§!", "critical": "§Rcritical§!",
           "weak": "§Rweak§!", "stable": "§Ystable§!", "strong": "§Gstrong§!"},
}


def loc_rows(lang):
    ru = lang == "ru"
    r = [f" # {MARK}."]

    def add(key, text):
        r.append(f' {key}:0 "{text}"')
    add("TOTU_plenum_title", "Пленум ЦК КПСС" if ru else "CPSU Central Committee Plenum")
    add("TOTU_pl_sec_hall", "ЗАЛ ПЛЕНУМА" if ru else "THE HALL")
    add("TOTU_pl_sec_factions", "ФРАКЦИИ" if ru else "FACTIONS")
    add("TOTU_pl_sec_party", "СОСТОЯНИЕ ПАРТИИ" if ru else "STATE OF THE PARTY")
    add("TOTU_pl_status_line", "[TOTU_pl_status]")
    # the status line is grey (text_color_code g, secondary to the tan title); the phase is in tan, a faction in yellow
    add("TOTU_pl_status_preparing", "§LИдёт подготовка к пленуму§!: фракции собирают сторонников"
        if ru else "§LThe plenum is being prepared§!: the factions gather supporters")
    add("TOTU_pl_status_session", "§LПленум заседает§!: итог решит голосование в ЦК"
        if ru else "§LThe plenum is in session§!: a vote in the Central Committee will decide")
    for k, _, name_ru, name_en, *_, card_ru, _card_en in FACTIONS:      # short Russian names: the line is 422 px
        add(f"TOTU_pl_status_ruling_{k}", f"§LКурс партии определён§!. Ведущая фракция: §Y{card_ru}§!"
            if ru else f"§LThe party line is set§!. Leading faction: §Y{name_en}§!")
    add("TOTU_pl_status_idle", "§LМежду пленумами§!: фракции борются за влияние в ЦК"
        if ru else "§LBetween plenums§!: the factions fight for influence")
    add("TOTU_pl_status_tt", "§YХод пленума§!\\n\\nМежду пленумами фракции борются за влияние. Затем идёт подготовка, "
        "пленум заседает, и голосование в ЦК определяет §Yведущую фракцию§!: её курс задаёт линию партии, а в зале её "
        "карточка светлее, в кремовой рамке и со звездой." if ru else
        "§YThe course of the plenum§!\\n\\nBetween plenums the factions fight for influence. Then the plenum is "
        "prepared and sits, and a vote in the Central Committee decides the §Yleading faction§!: its course sets the "
        "party line, and its card turns lighter, with a cream border and a star.")
    add("TOTU_pl_majority_value", "31")
    add("TOTU_pl_majority_label", "большинство" if ru else "majority")
    add("TOTU_pl_seats_total_value", str(SEATS))
    add("TOTU_pl_seats_total_label", "место в зале" if ru else "seats")
    add("TOTU_pl_hall_tt", "§Y61 место§! в зале распределено между фракциями пропорционально их поддержке, в каждом "
        "ряду поровну по доле. Для большинства нужно §Y31§! (золотые отметки на оси зала и на полосках фракций)."
        if ru else
        "The §Y61 seats§! of the hall are shared out among the factions in proportion to their support, every row "
        "by the same shares. A majority needs §Y31§! (the gold marks on the axis of the hall and on the faction "
        "bars).")
    add("TOTU_pl_empty", "")
    add("TOTU_pl_ruling_note", "\\n\\n§YВедущая фракция§!: победила на голосовании пленума, её курс определяет линию "
        "партии." if ru else "\\n\\n§YLeading faction§!: it won the plenum vote, and its course sets the party line.")
    for k, _, name_ru, name_en, gen_ru, short_en, _, card_ru, card_en in FACTIONS:
        add(f"TOTU_pl_{k}_name", name_ru if ru else name_en)
        add(f"TOTU_pl_{k}_card", card_ru if ru else card_en)
        add(f"TOTU_pl_{k}_pct", f"[?TOTU_pl_{k}|0]%")
        add(f"TOTU_pl_{k}_seats_line", f"[TOTU_pl_seats_{k}]")
        for form, word in SEAT_WORDS[lang].items():
            add(f"TOTU_pl_seats_{k}_{form}", f"[?TOTU_pl_seats_{k}|0] {word}")
        body = LOC_FACTION_TT[k][0 if ru else 1].replace("\n", "\\n")
        head = (f"§Y{name_ru}§!: §Y[?TOTU_pl_{k}|0]%§! поддержки в ЦК, §Y[TOTU_pl_seats_{k}]§! в зале из 61. Полоска: поддержка, золотая отметка на ней: большинство (31 из 61)" if ru
                else f"§Y{name_en}§!: §Y[?TOTU_pl_{k}|0]%§! support in the Central Committee, "
                     f"§Y[TOTU_pl_seats_{k}]§! of 61 in the hall. The bar shows the support, its gold mark a "
                     "majority (31 of 61)")
        add(f"TOTU_pl_{k}_tt", head + "\\n\\n" + body + f"[TOTU_pl_ruling_note_{k}]")
    add("TOTU_pl_rad_label", "Радикализация" if ru else "Radicalization")
    add("TOTU_pl_str_label", "Сила партии" if ru else "Party strength")
    add("TOTU_pl_rad_value", "[?TOTU_pl_rad|0]")
    add("TOTU_pl_str_value", "[?TOTU_pl_str|0]")
    add("TOTU_pl_rad_state_line", "[TOTU_pl_rad_state]")
    add("TOTU_pl_str_state_line", "[TOTU_pl_str_state]")
    for word, text in STATE_WORDS[lang].items():
        add(f"TOTU_pl_{'rad' if word in ('calm', 'tense', 'critical') else 'str'}_{word}", text)
    add("TOTU_pl_rad_tt", "Радикализация партии: §Y[?TOTU_pl_rad|0]§! из 100, [TOTU_pl_rad_state].\\n\\nРастёт, когда "
        "сильны крайние фракции (Демплатформа и ортодоксы), и во время заседаний пленума. Снижает §Yстабильность§!. "
        "До 40 партия §Gспокойна§!, до 70 §Yнапряжена§!; от §R70§! (красная зона) в ЦК возможны кризисы: демарши, "
        "заговоры, раскол." if ru else
        "Party radicalization: §Y[?TOTU_pl_rad|0]§! of 100, [TOTU_pl_rad_state].\\n\\nGrows while the extreme "
        "factions (the Democratic Platform and the Orthodox) are strong, and while the plenum is in session. Lowers "
        "§Ystability§!. Below 40 the party is §Gcalm§!, below 70 §Ytense§!; from §R70§! on (the red zone) crises can "
        "break out in the Central Committee: walkouts, plots, a split.")
    add("TOTU_pl_str_tt", "Сила партии: §Y[?TOTU_pl_str|0]§! из 100, [TOTU_pl_str_state].\\n\\nСильная партия даёт "
        "§Yполитическую власть§! и §Yстабильность§!. Слабая теряет контроль: ниже §Y50§! (золотая отметка) страна "
        "дрейфует к демократии. До 35 партия §Rслаба§!, до 65 §Yустойчива§!, выше §Gкрепка§!." if ru else
        "Party strength: §Y[?TOTU_pl_str|0]§! of 100, [TOTU_pl_str_state].\\n\\nA strong party gives §Ypolitical "
        "power§! and §Ystability§!. A weak one loses control: below §Y50§! (the gold mark) the country drifts towards "
        "democracy. Below 35 the party is §Rweak§!, below 65 §Ystable§!, above that §Gstrong§!.")
    # effect tooltips
    for k, _, name_ru, name_en, gen_ru, short_en, *_ in FACTIONS:
        for n in AMOUNTS:
            add(f"TOTU_pl_{k}_add_{n}_tt", f"Поддержка {gen_ru}: §G+{n}%§!" if ru else
                f"{short_en} support: §G+{n}%§!")
            add(f"TOTU_pl_{k}_sub_{n}_tt", f"Поддержка {gen_ru}: §R-{n}%§!" if ru else
                f"{short_en} support: §R-{n}%§!")
    for n in AMOUNTS:
        add(f"TOTU_pl_rad_add_{n}_tt", f"Радикализация партии: §R+{n}§!" if ru else f"Party radicalization: §R+{n}§!")
        add(f"TOTU_pl_rad_sub_{n}_tt", f"Радикализация партии: §G-{n}§!" if ru else f"Party radicalization: §G-{n}§!")
    for n in AMOUNTS:
        add(f"TOTU_pl_str_add_{n}_tt", f"Сила партии: §G+{n}§!" if ru else f"Party strength: §G+{n}§!")
        add(f"TOTU_pl_str_sub_{n}_tt", f"Сила партии: §R-{n}§!" if ru else f"Party strength: §R-{n}§!")
    return r


def build_loc():
    for lang, code in (("russian", "ru"), ("english", "en")):
        write(ROOT / f"localisation/{lang}/totu_plenum_generated_l_{lang}.yml",
              f"l_{lang}:\n" + "\n".join(loc_rows(code)) + "\n", bom=True)
    body = "\n".join(loc_rows("en")[1:]) + "\n"
    for lang in MIRROR_LANGS:
        note = f" # {MARK}: English copy of localisation/english/totu_plenum_generated_l_english.yml.\n"
        write(ROOT / f"localisation/{lang}/totu_plenum_generated_l_{lang}.yml", f"l_{lang}:\n" + note + body, bom=True)


# ======================================================================================================================
# Previews
# ======================================================================================================================
PREVIEW_STATES = {
    # name: (supports, rad, str, status loc key, ruling faction or None, language)
    "plenum_window": ([f[6] for f in FACTIONS], START_RAD, START_STR, "TOTU_pl_status_idle", None, "russian"),
    "plenum_window_ruling": ([10, 30, 48, 12], 75, 30, "TOTU_pl_status_ruling_cons", "cons", "russian"),
    "plenum_window_en": ([f[6] for f in FACTIONS], START_RAD, START_STR, "TOTU_pl_status_idle", None, "english"),
}


def build_preview(name, supports, rad, strength, status, ruling, lang):
    code = "ru" if lang == "russian" else "en"
    out = ROOT / f"tools/data/{name}_render.png"
    cmd = [sys.executable, str(ROOT / "tools/render_gui.py"), "TOTU_plenum_window", "--file", "interface/totu_plenum.gui",
           "--res", f"{WIN_W}x{WIN_H}", "--bg", "none", "--no-placeholders", "--out", str(out), "--lang", lang,
           "--text", f"plenum_status={status}"]
    hide = [f"card_ruling_{k},ruling_{k}" for k in KEYS if k != ruling]
    cmd += ["--hide", ",".join(hide)]
    seats = allocate(supports)
    for i, f in enumerate(seat_frames(supports), 1):
        cmd += ["--state", f"frame:seat_{i}={f}"]
    for k, v, n in zip(KEYS, supports, seats):
        cmd += ["--state", f"frame:support_{k}={value_frame(v)}", "--text", f"pct_{k}={v}%",
                "--text", f"seats_{k}={n} {SEAT_WORDS[code][seat_form(n)]}"]
    for k, v, table in (("rad", rad, RAD_WORDS), ("str", strength, STR_WORDS)):
        cmd += ["--state", f"frame:bar_{k}={value_frame(v)}", "--text", f"value_{k}={v}",
                "--text", f"state_{k}=TOTU_pl_{k}_{state_word(v, table)}"]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    issues = [ln for ln in (res.stdout + res.stderr).splitlines()
              if any(w in ln for w in ("WARN", "Error", "Traceback", " CUT", "GROWS", "OVERFLOWS"))]
    for line in issues:
        print(f"  render_gui ({name}):", line.strip())
    if res.returncode != 0 or not out.exists():
        print("preview failed:", name)
        return
    win = Image.open(out).convert("RGBA")
    rng = np.random.default_rng(1990)                     # the decisions panel behind it: dark warm grey, grain
    pad = 16
    bg = np.full((WIN_H + 2 * pad, WIN_W + 2 * pad, 3), PANEL, np.float64)
    bg += rng.normal(0, 2.2, bg.shape)
    panel = Image.fromarray(bg.clip(0, 255).astype(np.uint8), "RGB").convert("RGBA")
    panel.alpha_composite(win, (pad, pad))
    PREVIEW.mkdir(parents=True, exist_ok=True)
    panel.convert("RGB").save(PREVIEW / f"{name}.png")
    out.unlink()
    print(f"wrote tools/preview/{name}.png", seats, "seats")


def logo_sheet(icons, path):
    """Each logo at 4x (nearest) and at 1x on the dark panel colour and a lighter one."""
    bgs = [(36, 33, 30), (74, 66, 56)]
    cell = LOGO * 4 + 16
    img = Image.new("RGB", (len(icons) * cell + 16, LOGO * 4 + LOGO + 44), (20, 19, 18))
    for i, ic in enumerate(icons):
        x = 16 + i * cell
        big = Image.new("RGBA", (LOGO * 4, LOGO * 4), bgs[0] + (255,))
        big.alpha_composite(ic.resize((LOGO * 4, LOGO * 4), Image.NEAREST))
        img.paste(big.convert("RGB"), (x, 16))
        for j, bg in enumerate(bgs):
            t = Image.new("RGBA", (LOGO + 8, LOGO + 8), bg + (255,))
            t.alpha_composite(ic, (4, 4))
            img.paste(t.convert("RGB"), (x + j * (LOGO + 14), LOGO * 4 + 24))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    print("wrote", path.relative_to(ROOT).as_posix())


def icon_sheet(groups, path):
    """Rows of icons, each at 4x (nearest) with the 1x original under it, on the panel colour; the 1x icon is shown
    a second time on the lighter colour of a decision row."""
    pad, gap = 16, 14
    rows = []
    for title, icons in groups:
        h = max(ic.height for ic in icons)
        rows.append((title, icons, h))
    width = pad + max(sum(ic.width * 4 + gap for ic in icons) for _, icons, _ in rows) + pad
    height = pad + sum(h * 4 + h + 3 * gap for _, _, h in rows) + pad
    img = Image.new("RGBA", (width, height), PANEL + (255,))
    y = pad
    for _, icons, h in rows:
        x = pad
        for ic in icons:
            img.alpha_composite(ic.resize((ic.width * 4, ic.height * 4), Image.NEAREST), (x, y))
            cx = x + (ic.width * 4 - 2 * ic.width - 8) // 2
            img.alpha_composite(ic, (cx, y + h * 4 + gap))
            row = Image.new("RGBA", (ic.width + 8, ic.height + 8), (58, 51, 44, 255))
            row.alpha_composite(ic, (4, 4))
            img.alpha_composite(row, (cx + ic.width + 4, y + h * 4 + gap - 4))
            x += ic.width * 4 + gap
        y += h * 4 + h + 3 * gap
    img.convert("RGB").save(path)
    print("wrote", path.relative_to(ROOT).as_posix())


# ======================================================================================================================
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--no-preview", action="store_true")
    args = ap.parse_args()

    ensure_sources()
    out = ROOT / GFX_DIR
    save_dds(build_header(), out / "header.dds")
    save_dds(build_rule(), out / "rule.dds")
    save_dds(build_floor(), out / "floor.dds")
    save_dds(build_presidium(), out / "presidium.dds")
    save_dds(build_majority(), out / "majority.dds")
    save_dds(build_majority_tick(), out / "majority_tick.dds")
    save_dds(build_seat(), out / "seat.dds")
    for k, colour, *_ in FACTIONS:
        save_dds(build_card(colour), out / f"card_{k}.dds")
        save_dds(build_card_ruling(colour), out / f"card_ruling_{k}.dds")
        save_dds(build_support(colour), out / f"support_{k}.dds")
    save_dds(build_bar("rad"), out / "bar_rad.dds")
    save_dds(build_bar("str"), out / "bar_str.dds")
    logos = []
    for k, colour, *_ in FACTIONS:
        ic = logo_icon(k, colour)
        save_dds(ic, out / f"logo_{k}.dds")
        logos.append(ic)
    logo_sheet(logos, PREVIEW / "plenum_logos.png")
    win_icons = {"icon_emblem": icon_emblem(), "icon_status": icon_status(), "icon_rad": icon_rad(),
                 "icon_str": icon_str(), "icon_ruling": icon_ruling()}
    for n, ic in win_icons.items():
        save_dds(ic, out / f"{n}.dds")
    dec_icons = []
    for d, kind, src, colour in DECISION_ICONS:
        ic = decision_icon(d, src, colour)
        save_dds(ic, out / f"decisions/totu_pl_{d}.dds")
        dec_icons.append(ic)
    cat_icon, cat_pic = build_cat_icon(), build_cat_picture()
    save_dds(cat_icon, out / "decisions/category_totu_plenum.dds")
    save_dds(cat_pic, out / "decisions/cat_picture_totu_plenum.dds")
    vanilla = [Image.open(VANILLA_DECISIONS / f"decision_generic_{n}.dds").convert("RGBA")
               for n in ("arrest", "civil_support", "fundraising") if (VANILLA_DECISIONS / f"decision_generic_{n}.dds").exists()]
    icon_sheet([("decisions", dec_icons + vanilla), ("window", list(win_icons.values())),
                ("category", [cat_icon, cat_pic])], PREVIEW / "plenum_icons.png")
    # sprites of earlier versions: divider (v1, now rule), the vertical support columns and the shared ruling border
    for stale in [out / "divider.dds", out / "card_ruling.dds"] + [out / f"col_{k}.dds" for k in KEYS]:
        if stale.exists():
            stale.unlink()

    build_gfx()
    build_gui()
    build_scripted_gui()
    build_scripted_loc()
    build_effects()
    build_loc()
    if not args.no_preview:
        for name, state in PREVIEW_STATES.items():
            build_preview(name, *state)


if __name__ == "__main__":
    main()
