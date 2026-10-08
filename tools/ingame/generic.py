"""Generic broadcast treatment of vanilla in-game chrome, plus the drawing helpers area modules share.

Every live texture that no area module claims goes through treat(). It turns the vanilla painted metal, paper and
gold into the mod's broadcast look (late-Soviet TV captions: flat cold boards, keyer blue, no frames) without
hand-drawing anything, so the whole vanilla UI already reads as broadcast before the stream modules refine it.

Modes (mode_for(): OVERRIDES, content .gfx guard, class rules in CLASS_MODE / _class_mode / CLASS_OPTS, selected /
active names, colour guard; the chosen Opts carry a `why`):
  regrade  buttons, checkboxes, scrollbars, bars, small parts, icons inside chrome. Cold palette: luma is mapped
           onto board -> slate -> D -> P with a plateau over the vanilla mid-tones; weak texture noise is
           suppressed; gold / brown / tan / copper lose all colour. Semantic pixels (red, orange-red in red-dominated
           textures, green, blue, yellow where enabled) keep their vanilla hue and saturation, value lifted to
           SEM_VMIN. Plate-like silhouettes lose rim, bevel and scratches: the body becomes SLATE (paper and gold
           bodies too, with their dark glyphs turned light; only under dark .gui text a paper body stays D), a
           signal-coloured body a flat muted version of its hue, icons and glyphs stay, and a saturated gold /
           orange rim (vanilla's "selected") becomes keyer blue. Bars use a ramp without the plateau so fills read
           as D / P over dark tracks. Alpha is kept.
  caption  plain one-frame text buttons (wide plates with no glyph): a solid SLATE caption plate with the stepped
           tail over the vanilla opaque box; the engine shader brightens it on hover.
  quiet    frames around a hole (flag, leader and portrait frames): capped at a dark slate, so a frame still masks
           the flag edge but no longer reads as a silver or gold frame; signal red / green stays.
  flatten  view backgrounds, panels, tiled windows, headers, big list entries, tabs: painted detail is removed
           (alpha-aware blur, luma quantised into at most 3 levels shared by all frames, thin lines, ornaments and
           frame-edge bars opened away, regions snapped to rectangles, irregular painted regions dropped). Each
           level becomes a flat tone by its vanilla luma: board / raised / field, and "paper" (D, rectangular
           silhouette) for really light surfaces only where a .gui draws dark text on them (Opts.dark_text).
           Big backgrounds keep sub-panels as separate tones and long dividers as D hairlines. Small signal marks
           keep their colour, signal surfaces a dark tint. Opaque areas get alpha 0.90 - 0.95. Two-frame tabs:
           the brighter (selected) frame becomes a keyer plate; two-frame list entries and *_selected / *_active
           entries: a 4 px keyer bar on the left.
  state    tree state plates: one flat rectangle per state (STATE_TONES: ready / done / blocked / branch / active).
  keyer    neutral / gold glows, highlight overlays, selection frames and fills: the shape is kept, the colour
           becomes keyer blue (signal glows - red, green, yellow, alert - are kept as vanilla instead).
  knob     glossy scroll / slider knobs: flat discs (P 70 %, hover P, pressed keyer, disabled D 30 %).
  clear    fully transparent (pure ornament).
  keep     content or engine-critical: the vanilla file stays (nothing is written).

The palette below is the binding broadcast spec; check_palette() compares it with tools/build_menu_gfx.py and
tools/totu_broadcast.py (the sprite-level kit for new GFX_totu_* sprites; this module restyles vanilla textures).
"""
import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

# ---------------------------------------------------------------------------------------------------------------
# Palette (broadcast spec)
# ---------------------------------------------------------------------------------------------------------------
BOARD = (9, 11, 16)               # flat board (= build_menu_gfx.CS_BOARD_RGB)
BOARD_ALPHA_FE = 0.84             # board alpha in the frontend (= build_menu_gfx.BOARD_ALPHA)
BOARD_ALPHA = 0.90                # board alpha in game
RAISED = (18, 22, 30)             # raised sub-panel
RAISED_ALPHA = 0.92
SLATE = (40, 47, 62)              # visible plate of one-frame vanilla buttons
P = (246, 242, 234)               # primary text / pictograms (= CAPTION_WHITE)
D = (172, 180, 196)               # secondary, never darker (= CAPTION_DIM)
K = (0, 0, 0)                     # drop copy / baked edge at +2,+2
KEY_BLUE = (30, 62, 168)          # keyer plate: hover, active, selected
KEY_BLUE_DOWN = (17, 38, 108)     # pressed
TAIL_ALPHA = (153, 77)            # stepped plate tail: 60 % then 30 %
FIELD_ALPHA = 0.14                # field = D at 14 % over the board
HAIRLINE_ALPHA = 0.22             # separators: D at 22 %, 1-2 px
TRACK_ALPHA = 0.18                # empty bar track: D at 18 %
SCROLL_KNOB_ALPHA = 0.70          # scrollbar / slider knob: P at 70 % (= totu_broadcast.SCROLL_KNOB_ALPHA)
DISABLED_ALPHA = 0.30             # disabled knobs / pictograms: D at 30 %
# Semantic text colours of vanilla core.gfx (textcolors G / R / Y): they carry meaning and stay
SEM_G = (86, 172, 91)
SEM_R = (222, 86, 70)
SEM_Y = (238, 201, 35)
SEM_VMIN = 0.45                   # kept semantic colours are lifted to at least this HSV value (legible on the board)


def _over(top, a_top, bottom, a_bottom):
    """Straight-alpha 'top over bottom' of two flat colours -> (rgb, alpha)."""
    a = a_top + a_bottom * (1 - a_top)
    rgb = tuple(round((t * a_top + b * a_bottom * (1 - a_top)) / a) for t, b in zip(top, bottom))
    return rgb, a


FIELD, FIELD_A = _over(D, FIELD_ALPHA, BOARD, BOARD_ALPHA)           # (31,35,41) at 0.914
DONE_G = _over(SEM_G, 0.40, BOARD, 1.0)[0]                          # (40,76,46): completed / researched plates

# Flatten tones: name -> (rgb, alpha of an opaque vanilla area)
TONES = {
    "board": (BOARD, BOARD_ALPHA),
    "raised": (RAISED, RAISED_ALPHA),
    "field": (FIELD, FIELD_A),
    "slate": (SLATE, 0.94),
    "paper": (D, 0.95),           # light vanilla paper keeps a light surface: vanilla draws dark text on it
    "done": (DONE_G, 0.94),       # completed / researched state plates
    "keyer": (KEY_BLUE, 0.95),    # active / selected plates
}


def check_palette():
    """Compare with tools/build_menu_gfx.py (the frontend's source of truth) and, when present, the sprite-level kit
    tools/totu_broadcast.py. Returns a list of mismatch strings; an import failure is not an error (other agents may
    be editing those files, and this pipeline must not depend on them)."""
    out = []
    try:
        import build_menu_gfx as bmg   # noqa: PLC0415 - optional, heavy
        want = {"KEY_BLUE": KEY_BLUE, "KEY_BLUE_DOWN": KEY_BLUE_DOWN, "CAPTION_WHITE": P, "CAPTION_DIM": D,
                "CS_BOARD_RGB": BOARD, "BOARD_ALPHA": BOARD_ALPHA_FE, "TAIL_ALPHA": TAIL_ALPHA}
        out += [f"{k}: generic {v} != build_menu_gfx {getattr(bmg, k)}" for k, v in want.items()
                if hasattr(bmg, k) and tuple(np.atleast_1d(getattr(bmg, k))) != tuple(np.atleast_1d(v))]
    except Exception:   # noqa: BLE001
        pass
    try:
        import totu_broadcast as tb   # noqa: PLC0415 - optional
        want = {"KEY_BLUE": KEY_BLUE, "KEY_BLUE_DOWN": KEY_BLUE_DOWN, "P": P, "D": D, "K": K, "BOARD_RGB": BOARD,
                "BOARD_ALPHA_IG": BOARD_ALPHA, "TAIL_ALPHA": TAIL_ALPHA, "RAISED_RGB": RAISED,
                "RAISED_ALPHA": RAISED_ALPHA, "SLATE_RGB": SLATE, "FIELD_ALPHA": FIELD_ALPHA,
                "HAIRLINE_ALPHA": HAIRLINE_ALPHA, "TRACK_ALPHA": TRACK_ALPHA, "SCROLL_KNOB_ALPHA": SCROLL_KNOB_ALPHA,
                "DISABLED_ALPHA": DISABLED_ALPHA, "SEM_G": SEM_G, "SEM_R": SEM_R, "SEM_Y": SEM_Y}
        for k, v in want.items():
            got = getattr(tb, k, None)
            if got is None or isinstance(got, (dict, str)) or callable(got):
                continue
            try:
                if tuple(np.round(np.atleast_1d(got), 4)) != tuple(np.round(np.atleast_1d(v), 4)):
                    out.append(f"{k}: generic {v} != totu_broadcast {got}")
            except Exception:   # noqa: BLE001
                pass
    except Exception:   # noqa: BLE001
        pass
    return out


# ---------------------------------------------------------------------------------------------------------------
# Small numpy / PIL helpers (public: area modules may use them)
# ---------------------------------------------------------------------------------------------------------------
def to_array(img):
    """RGBA image -> float32 array h x w x 4 in 0..255."""
    return np.asarray(img.convert("RGBA"), np.float32)


def to_image(arr):
    """float array h x w x 4 (0..255) -> RGBA image (rounded, clipped)."""
    return Image.fromarray(np.clip(np.rint(arr), 0, 255).astype(np.uint8), "RGBA")


def luma(rgb):
    """Rec.601 luma of an h x w x 3 array (same scale as the input)."""
    return rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114


def smoothstep(e0, e1, x):
    t = np.clip((np.asarray(x, np.float32) - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def box_blur(a, r, axis):
    """Mean over a 2r+1 window along one axis, edges replicated (float32)."""
    if r <= 0:
        return a
    pad = [(0, 0)] * a.ndim
    pad[axis] = (r + 1, r)
    c = np.cumsum(np.pad(a, pad, mode="edge"), axis=axis, dtype=np.float64)
    n = a.shape[axis]
    hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
    lo = np.take(c, np.arange(0, n), axis=axis)
    return ((hi - lo) / (2 * r + 1)).astype(np.float32)


def gauss(a, sigma):
    """Approximate Gaussian blur of a 2-D float array (three box passes per axis)."""
    if sigma <= 0.3:
        return a.astype(np.float32)
    r = max(1, int(round((np.sqrt(12 * sigma * sigma / 3 + 1) - 1) / 2)))
    out = a.astype(np.float32)
    for _ in range(3):
        out = box_blur(box_blur(out, r, 0), r, 1)
    return out


def masked_gauss(v, w, sigma):
    """Blur v weighted by w (alpha): transparent pixels do not darken the edges."""
    num = gauss(v * w, sigma)
    den = gauss(w, sigma)
    return np.where(den > 1e-4, num / np.maximum(den, 1e-4), v)


def split_frames(img, frames):
    """A strip of `frames` equal frames side by side -> list of images (vanilla noOfFrames layout)."""
    frames = max(1, int(frames or 1))
    if frames == 1 or img.width % frames:
        return [img]
    fw = img.width // frames
    return [img.crop((i * fw, 0, (i + 1) * fw, img.height)) for i in range(frames)]


def join_frames(parts):
    """Inverse of split_frames."""
    if len(parts) == 1:
        return parts[0]
    out = Image.new("RGBA", (sum(p.width for p in parts), parts[0].height), (0, 0, 0, 0))
    x = 0
    for p in parts:
        out.paste(p, (x, 0))
        x += p.width
    return out


def per_frame(img, frames, fn):
    """Apply fn(frame_image, index) -> image to every frame and join them again."""
    return join_frames([fn(f, i) for i, f in enumerate(split_frames(img, frames))])


def blank(w, h):
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))


def flat(w, h, rgb=BOARD, alpha=BOARD_ALPHA):
    """A flat w x h surface; alpha 0..1."""
    return Image.new("RGBA", (w, h), tuple(rgb) + (round(255 * alpha),))


def plate(w, h, rgb=SLATE, alpha=1.0, tail=None, tail_alpha=TAIL_ALPHA):
    """A caption plate: solid for w - tail px, then the hard stepped tail (tail // len(tail_alpha) px per step).
    tail defaults to 12 px (6 + 6) for plates >= 30 px tall (the frontend's 40 px plates and the 32-36 px vanilla
    buttons) and 6 px (3 + 3) for smaller ones (the frontend's 24 px plates)."""
    if tail is None:
        tail = 12 if h >= 30 else 6
    img = blank(w, h)
    solid = max(0, w - tail)
    img.paste(tuple(rgb) + (round(255 * alpha),), (0, 0, solid, h))
    step = tail // len(tail_alpha) if tail_alpha else 0
    x = solid
    for a in tail_alpha:
        if step <= 0:
            break
        img.paste(tuple(rgb) + (round(a * alpha),), (x, 0, min(w, x + step), h))
        x += step
    return img


def big_plate_w(n):
    """Width of a 40 px caption plate for an n-character label (4 px pixel-font cells)."""
    return 22 + (n * 24 - 4) + 10 + 12


def small_plate_w(n):
    """Width of a 24 px caption plate for an n-character label (2 px cells)."""
    return 12 + (n * 12 - 2) + 6 + 6


def hairline(img, box, rgb=D, alpha=HAIRLINE_ALPHA):
    """Composite a flat rectangle (x0, y0, x1, y1 exclusive) onto img in place, e.g. a 1-2 px separator."""
    layer = blank(img.width, img.height)
    layer.paste(tuple(rgb) + (round(255 * alpha),), box)
    img.alpha_composite(layer)
    return img


def pictogram(rows, cell=2, rgb=P, drop=True):
    """A pixel-grid pictogram: rows of strings, '#' = lit cell, drawn at `cell` px in rgb with a black (K) drop
    copy at +cell,+cell when drop is set. Returns the smallest RGBA image holding both."""
    gh, gw = len(rows), max(len(r) for r in rows)
    pad = cell if drop else 0
    img = blank(gw * cell + pad, gh * cell + pad)
    lit = [(x, y) for y, r in enumerate(rows) for x, ch in enumerate(r) if ch == "#"]
    if drop:
        for x, y in lit:
            img.paste(K + (255,), (x * cell + pad, y * cell + pad, (x + 1) * cell + pad, (y + 1) * cell + pad))
    for x, y in lit:
        img.paste(tuple(rgb) + (255,), (x * cell, y * cell, (x + 1) * cell, (y + 1) * cell))
    return img


def paste_center(dst, src, dx=0, dy=0):
    """Alpha-composite src centred on dst (in place)."""
    dst.alpha_composite(src, ((dst.width - src.width) // 2 + dx, (dst.height - src.height) // 2 + dy))
    return dst


# ---------------------------------------------------------------------------------------------------------------
# Colour analysis
# ---------------------------------------------------------------------------------------------------------------
def hue_sat_val(rgb):
    """HSV of an h x w x 3 array in 0..255: hue in degrees, saturation and value in 0..1."""
    c = rgb / 255.0
    mx = c.max(-1)
    mn = c.min(-1)
    d = mx - mn
    s = np.where(mx > 1e-6, d / np.maximum(mx, 1e-6), 0)
    r, g, b = c[..., 0], c[..., 1], c[..., 2]
    dd = np.maximum(d, 1e-6)
    h = np.where(mx == r, ((g - b) / dd) % 6, np.where(mx == g, (b - r) / dd + 2, (r - g) / dd + 4)) * 60
    return np.where(d > 1e-6, h, 0), s, mx


def _band(h, a0, a1, b1, b0):
    """1 between a1 and b1 degrees, linear fades to 0 at a0 and b0 (no wrap)."""
    up = np.clip((h - a0) / max(a1 - a0, 1e-6), 0, 1)
    down = np.clip((b0 - h) / max(b0 - b1, 1e-6), 0, 1)
    return np.minimum(up, down)


# Semantic hue bands in degrees (fade-in start, full, full, fade-out end). Gold / brown / tan (about 22..65 deg)
# is outside every band, so it always ends up neutral.
RED_BAND = (-22, -8, 8, 15)        # evaluated on hue shifted into -180..180
ORANGE_BAND = (-22, -8, 20, 27)    # orange-red (arrows down, bop orange, alarm glows): strongly saturated pixels of
                                   # textures whose warm colour is red-orange, not gold (see colour_profile)
GREEN_BAND = (72, 88, 166, 180)
BLUE_BAND = (182, 196, 250, 264)
YELLOW_BAND = (30, 40, 60, 70)     # only when the yellow option is on (priority lights, bars)


def semantic_weight(rgb, yellow=False, sat_lo=0.30, sat_hi=0.55, yellow_sat=(0.6, 0.78), orange=False,
                    any_hue=False, orange_sat=(0.55, 0.70)):
    """0..1 per pixel: how much of the pixel's colour carries meaning (saturated red / green / blue, optionally
    orange-red and yellow; any_hue: every saturated hue, for content-like strips whose frames differ by colour).
    Weak tints such as the green paint of vanilla buttons (s ~ 0.28) stay below sat_lo."""
    h, s, v = hue_sat_val(rgb)
    if any_hue:     # every hue, except dull gold / brown / bronze ornament (bright yellow still counts)
        dull_gold = _band(h, 18, 26, 52, 60) * (1 - smoothstep(0.55, 0.72, v) * smoothstep(0.5, 0.65, s))
        return smoothstep(sat_lo, sat_hi, s) * smoothstep(0.10, 0.25, v) * (1 - dull_gold)
    hr = np.where(h > 180, h - 360, h)
    red = _band(hr, *RED_BAND)
    if orange:
        red = np.maximum(red, _band(hr, *ORANGE_BAND) * smoothstep(orange_sat[0], orange_sat[1], s))
    w = np.maximum(red, np.maximum(_band(h, *GREEN_BAND), _band(h, *BLUE_BAND)))
    w = w * smoothstep(sat_lo, sat_hi, s)
    if yellow:      # only a strong yellow is a signal; gold ornament (s ~0.4-0.6) stays neutral
        w = np.maximum(w, _band(h, *YELLOW_BAND) * smoothstep(yellow_sat[0], yellow_sat[1], s))
    return w * smoothstep(0.10, 0.25, v)


def legible(rgb, vmin=SEM_VMIN):
    """Vanilla colours with their hue and saturation kept and the HSV value lifted to at least vmin (dark shadow
    parts of a red marker would vanish on the board otherwise)."""
    mx = rgb.max(-1, keepdims=True)
    return rgb * (np.clip(mx, vmin * 255, 255) / np.maximum(mx, 1.0))


def colour_profile(img, frames=1):
    """Texture-level colour facts used by mode_for(): share of opaque pixels with a real colour (s > 0.3), the hue
    entropy of those (bits, 30-degree bins), the median hue of strongly saturated warm pixels (red-orange < 22 deg
    < gold) and whether the frames of a strip differ mainly by hue (theatre colours, doctrine pills)."""
    a = to_array(img)
    rgb, al = a[..., :3], a[..., 3] / 255.0
    h, s, v = hue_sat_val(rgb)
    op = al > 0.5
    res = {"share": 0.0, "entropy": 0.0, "warm_median": None, "hue_frames": False, "sat_share": 0.0,
           "sem_cluster": None}
    if op.sum() < 16:
        return res
    col = op & (s > 0.3) & (v > 0.2)
    res["share"] = float(col.sum() / op.sum())
    res["sat_share"] = float((op & (s > 0.5) & (v > 0.3)).sum() / op.sum())
    if col.any():
        hist = np.histogram(h[col], bins=12, range=(0, 360))[0].astype(np.float64)
        p = hist[hist > 0] / hist.sum()
        res["entropy"] = float(-(p * np.log2(p)).sum())
    hr = np.where(h > 300, h - 360, h)
    # one semantic hue cluster (a green "up" arrow, a copper-red "down" arrow, a green tick): even moderately
    # saturated pixels of that cluster carry the meaning. Brown metal and wood (darker, hue 20-30) stay out.
    loose = op & (s > 0.22) & (v > 0.2)
    res["sem_cluster"] = None
    if loose.sum() >= max(12, 0.03 * op.sum()):
        hl = hr[loose]
        green = float(((hl >= 72) & (hl <= 172)).mean())
        redo = (hl >= -22) & (hl <= 20)
        if green >= 0.5:
            res["sem_cluster"] = "green"
        elif redo.mean() >= 0.5 and np.median(s[loose][redo]) >= 0.4 and np.median(v[loose][redo]) >= 0.5:
            res["sem_cluster"] = "red"
    warm = op & (s > 0.5) & (v > 0.3) & (hr > -30) & (hr < 60)
    if warm.sum() >= 6:
        res["warm_median"] = float(np.median(hr[warm]))
    frames = max(1, int(frames or 1))
    if frames >= 2 and img.width % frames == 0:
        fw = img.width // frames
        hues, cols = [], 0
        # gold / bronze / orange (selection rims, ornament) does not make a frame "coloured"
        col_ng = col & ~((h >= 12) & (h <= 62))
        for i in range(frames):
            m = col_ng[:, i * fw:(i + 1) * fw]
            if m.sum() >= 0.08 * max(op[:, i * fw:(i + 1) * fw].sum(), 1) and m.sum() >= 8:
                hh = np.deg2rad(h[:, i * fw:(i + 1) * fw][m])
                hues.append(np.arctan2(np.sin(hh).mean(), np.cos(hh).mean()))
                cols += 1
        if cols >= 2:
            hs = np.rad2deg(np.array(hues)) % 360
            d = np.abs(((hs[:, None] - hs[None, :]) + 180) % 360 - 180)
            res["hue_frames"] = bool(d.max() > 60)
    return res


# ---------------------------------------------------------------------------------------------------------------
# Tone ramps
# ---------------------------------------------------------------------------------------------------------------
# input luma (0..1) -> colour. The plateau between 0.14 and 0.34 is where vanilla paints the body of its plates
# (green, brown and grey metal, lum ~0.15-0.30): it all lands on slate with little variation, so bevels and
# scratches go quiet. Dark wells drop to the board; text, glyphs and icon highlights rise to D and P.
REGRADE_RAMP = [(0.00, BOARD), (0.055, BOARD), (0.14, (31, 37, 50)), (0.34, SLATE), (0.58, D), (0.86, P),
                (1.00, P)]
# bars: no plateau, a vanilla fill (mid-tone colour) reads as D / P over a board track
BAR_RAMP = [(0.00, BOARD), (0.07, BOARD), (0.18, (64, 72, 90)), (0.32, D), (0.55, P), (1.00, P)]
# frames: never brighter than a dark slate
QUIET_RAMP = [(0.00, BOARD), (0.08, BOARD), (0.40, (30, 36, 48)), (1.00, (58, 66, 84))]


def ramp(x, stops):
    """Piecewise-linear luma (0..1) -> RGB (0..255) lookup; returns h x w x 3 float32."""
    xs = np.array([s for s, _ in stops], np.float32)
    cols = np.array([c for _, c in stops], np.float32)
    x = np.clip(x, 0, 1)
    return np.stack([np.interp(x, xs, cols[:, i]) for i in range(3)], -1).astype(np.float32)


# ---------------------------------------------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------------------------------------------
@dataclass
class Opts:
    """Per-texture options of the generic treatment (OVERRIDES may set any of them). After treat(), `paper` and
    `why` report what happened (paper tone used; which automatic rule picked the options)."""
    mode: str = "regrade"
    yellow: bool = False            # regrade: treat saturated yellow as semantic (priority lights, bars)
    yellow_sat: tuple = (0.6, 0.78) # regrade: saturation where yellow starts / fully counts (gold stays neutral)
    orange: bool = False            # regrade: strongly saturated orange-red (up to ~25 deg) is semantic red too
    orange_sat: tuple = (0.55, 0.70)  # regrade: saturation where orange-red starts / fully counts
    any_hue: bool = False           # regrade / flatten: every saturated hue is kept (content-like colour strips)
    sem_keep: float = 1.0           # regrade: share of a semantic pixel's vanilla colour that survives (hue and
                                    # saturation kept, value lifted to SEM_VMIN); 0 = fully neutral
    sat_lo: float = 0.30            # regrade: saturation where a semantic hue starts to count ...
    sat_hi: float = 0.55            # ... and where it counts fully
    detail_keep: float = 0.35       # regrade: share of weak detail (texture noise) that survives
    ramp: str = "regrade"           # regrade: tone ramp, "regrade" (plateau on slate) or "bar" (fills to D / P)
    plate: bool = True              # regrade: plate-like silhouettes lose rim, bevel and scratches
    body: str = ""                  # regrade plates: "keyer" = the body becomes KEY_BLUE (selected states)
    levels: int = 3                 # flatten: at most this many tones
    tones: tuple = ()               # flatten: explicit tone names from dark to light, e.g. ("field",)
    alpha_scale: float = 1.0        # flatten / regrade: extra alpha multiplier
    open_px: int = 0                # flatten: ornament opening size override (odd px, 0 = from the size)
    merge: float = 0.07             # flatten: luma levels closer than this merge (gradients stay one tone)
    tint: float = 1.6               # flatten: semantic colour kept in flat regions (0 = none)
    rects: bool = True              # flatten: snap regions to rectangles, drop irregular (painted) ones
    rect_alpha: bool = False        # flatten: the alpha silhouette becomes its bounding rectangle (torn paper,
                                    # rounded pills); always on for frames whose main tone is paper
    guides: bool = False            # flatten: long straight vanilla dividers become D hairlines (big backgrounds)
    bump: float = 0.1               # flatten: vanilla levels at least this far apart never share a tone (sub-panels
                                    # of big backgrounds use 0.04, so a header strip stays raised over the board)
    active: bool = True             # flatten: a brighter vanilla frame that flattened away gets a keyer accent
    accent: str = "none"            # flatten: "fill" (2-frame tabs: keyer plate) / "bar" (2-frame list entries) /
                                    # "bar1" (a selected single entry: 4 px keyer bar on every frame) / "none"
    state: str = ""                 # state mode: ready / done / blocked / branch / active (see STATE_TONES)
    keep_below: bool = False        # state mode: vanilla pixels below the plate body stay (joint focus flag ribbons)
    dark_text: object = None        # vanilla draws dark text on this texture (True: light paper surfaces stay light;
                                    # False: no .gui puts dark text on it, so paper becomes a dark tone; None: unknown,
                                    # e.g. engine-only sprites: paper stays light). Set from the orchestrator's scan.
    note: str = ""
    paper: bool = False             # result: a light "paper" tone was used (vanilla draws dark text there)
    why: str = ""                   # result: which automatic rule chose these options


def erode(mask, r):
    """Binary erosion of a bool array by a (2r+1) square."""
    if r <= 0:
        return mask
    im = Image.fromarray((mask * 255).astype(np.uint8), "L").filter(ImageFilter.MinFilter(2 * r + 1))
    return np.asarray(im) > 0


def plate_shape(al, min_fill=0.78, thr=0.5):
    """Plate-like silhouette of one frame (alpha 0..1): a nearly convex body (alpha > thr) filling its bounding
    box. Returns dict(mask, bbox=(x0, y0, x1, y1) exclusive, interior, rim) or None."""
    m = al > thr
    if m.sum() < 48:
        return None
    ys, xs = np.nonzero(m)
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    bw, bh = x1 - x0, y1 - y0
    if bw < 10 or bh < 8 or m.sum() / (bw * bh) < min_fill:
        return None
    r = int(np.clip(round(min(bw, bh) / 9), 2, 4))
    inner = erode(m, r)
    if inner.sum() < 16:
        return None
    return {"mask": m, "bbox": (int(x0), int(y0), int(x1), int(y1)), "interior": inner, "rim": r}


def plate_stats(fr, thr=0.12):
    """(shape or None, body luma, share of interior pixels deviating more than thr from the body) of one frame."""
    a = to_array(fr)
    al = a[..., 3] / 255.0
    shape = plate_shape(al)
    if shape is None:
        return None, 0.0, 1.0
    lum = luma(a[..., :3]) / 255.0
    sm = masked_gauss(lum, np.maximum(al, 0.02), 1.3)
    body = float(np.median(sm[shape["interior"]]))
    dev = np.abs(gauss(lum, 0.6) - body)
    return shape, body, float((dev[shape["interior"]] > thr).mean())


PLATEAU = (0.11, 0.42)      # plate bodies with a luma in this range become exactly SLATE
PAPER_LUMA = 0.55           # lighter plate bodies (paper, parchment, gold) also become SLATE in regrade / caption;
                            # their dark glyphs turn light. (flatten keeps a light "paper" tone instead, see TONES)


def _sem(rgb, opts):
    return semantic_weight(rgb, yellow=opts.yellow, sat_lo=opts.sat_lo, sat_hi=opts.sat_hi,
                           yellow_sat=opts.yellow_sat, orange=opts.orange, any_hue=opts.any_hue,
                           orange_sat=opts.orange_sat)


def regrade(img, frames=1, opts=None, stops=None):
    """Cold-palette regrade (see module doc). Returns a new RGBA image of the same size."""
    opts = opts or Opts()
    stops = stops or (BAR_RAMP if opts.ramp == "bar" else REGRADE_RAMP)
    use_plate = opts.plate and stops is REGRADE_RAMP

    def one(fr, _i):
        a = to_array(fr)
        rgb, al = a[..., :3], a[..., 3] / 255.0
        lum = luma(rgb) / 255.0
        small = min(fr.width, fr.height) < 40
        smooth = masked_gauss(lum, np.maximum(al, 0.02), 0.8 if small else 1.3)
        det = lum - smooth
        keep = opts.detail_keep + (1 - opts.detail_keep) * smoothstep(0.035, 0.11, np.abs(det))
        lum2 = smooth + det * keep
        sem = _sem(rgb, opts)
        shape = plate_shape(al) if use_plate else None
        if shape is not None:
            # plate: rim, bevel and scratches go; strong interior detail (icons, glyphs, arrows) stays
            inner = shape["interior"]
            body = float(np.median(smooth[inner]))
            body_px = np.median(rgb[inner], 0)
            # deviation from the body in luma or in colour (a gold plus on a brown disc, a red cross on grey)
            sig = 0.0 if small else 0.6               # small icons: thin 1-2 px strokes must not blur away
            sm_rgb = np.stack([gauss(rgb[..., i], sig) for i in range(3)], -1)
            cdist = np.sqrt(((sm_rgb - body_px) ** 2).sum(-1)) / 441.7
            dev = np.maximum(np.abs(gauss(lum, sig) - body), cdist * 1.3)
            # interior: icons and glyphs stay; rim zone: only clearly different pixels (bevels and rims go)
            t_in = np.clip(gauss(inner.astype(np.float32), 0.8), 0, 1)
            paper = body > PAPER_LUMA
            keep_light = paper and opts.dark_text is True      # dark vanilla text sits on it: stays a light plate
            lo, hi = (0.14, 0.24) if paper else (0.04, 0.10) if small else (0.06, 0.14)   # paper grain stays flat
            if opts.body == "keyer":    # metal grain must not show through a flat keyer body
                lo, hi = max(lo, 0.12), max(hi, 0.22)
            if paper:   # on paper only darker marks are glyphs; lighter ones are gloss
                dev = np.maximum(np.maximum(body - gauss(lum, sig), 0), cdist * 1.3 * smoothstep(0.1, 0.2, cdist))
            wdet = t_in * smoothstep(lo, hi, dev) + (1 - t_in) * smoothstep(0.22, 0.34, dev)
            if paper:   # the dark outline of a paper / gold plate is a rim, not a glyph: it goes
                wdet = t_in * smoothstep(lo, hi, dev)
            if opts.body in STATE_BODY:
                body_rgb = np.array(STATE_BODY[opts.body], np.float32)
            elif keep_light:
                body_rgb = np.array(D, np.float32)
                opts.paper = True
            elif PLATEAU[0] <= body <= PLATEAU[1] or paper:
                body_rgb = np.array(SLATE, np.float32)
            else:
                body_rgb = ramp(np.array(body), stops).astype(np.float32)
            body_rgb = body_rgb.reshape(1, 1, 3)
            # a body in a semantic colour (state strips: green / red / blue frames) keeps a dark version of it
            bsem = float(_sem(body_px.reshape(1, 1, 3), opts)[0, 0]) * min(opts.sem_keep, 1.0)
            if bsem > 0.3 and opts.body != "keyer":
                # a body in a signal / content colour (state discs, green "go" plates, doctrine discs): one flat,
                # muted version of its hue (no painted texture)
                body_rgb = body_rgb * 0.2 + legible(body_px.reshape(1, 1, 3), 0.42) * 0.8
            elif bsem > 0 and opts.body != "keyer":
                bl = max(float(luma(body_px.reshape(1, 1, 3))[0, 0]), 8.0)
                scale = float(luma(body_rgb)[0, 0]) / bl
                body_rgb = np.clip(body_rgb + (body_px - bl).reshape(1, 1, 3) * bsem * np.clip(scale, 0.4, 2.5),
                                   0, 255)
            det_lum = lum2
            if paper and not keep_light:    # dark glyphs on light paper -> light glyphs on the slate plate
                det_lum = np.where(lum2 < body, np.clip(1.0 - lum2, 0, 1), lum2)
            out = body_rgb * (1 - wdet[..., None]) + ramp(det_lum, stops) * wdet[..., None]
            # only clear details (icons, glyphs) keep their colour: weak texture noise on the body stays flat;
            # a strong signal colour that clearly differs from the body (a red alarm edge on a paper plate) stays
            # even on the rim
            strong = smoothstep(0.6, 0.9, sem) * smoothstep(0.08, 0.16, cdist)
            sem = sem * np.maximum(smoothstep(0.3, 0.8, wdet), strong)
            # a saturated gold rim is vanilla's selection / active highlight: it becomes keyer blue
            h, sat, val = hue_sat_val(rgb)
            gold = _band(h, 12, 20, 52, 62) * smoothstep(0.35, 0.6, sat) * smoothstep(0.3, 0.5, val)
            sel = (1 - t_in) * wdet * gold
            if sel.max() > 0.05:
                key = np.array(KEY_BLUE, np.float32) * (0.75 + 0.5 * np.clip(lum2, 0, 1))[..., None]
                out = out * (1 - sel[..., None]) + key * sel[..., None]
                sem = sem * (1 - sel)
        else:
            out = ramp(lum2, stops)
        # semantic pixels keep their vanilla hue and saturation (value lifted into a legible band)
        k = np.clip(sem * opts.sem_keep, 0, 1)
        if k.max() > 0:
            out = out * (1 - k[..., None]) + legible(rgb) * k[..., None]
        if opts.body == "keyer" and shape is None and (al > 0.05).any():
            # selected frame without an opaque plate (translucent body, light rim): the lit rim becomes keyer
            ys, xs = np.nonzero(al > 0.05)
            y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
            band = np.ones(al.shape, bool)
            band[y0 + 2:y1 - 2, x0 + 2:x1 - 2] = False
            rim = band & (lum > 0.3) & (al > 0.3)
            out[rim] = KEY_BLUE
        res = np.concatenate([np.clip(out, 0, 255), (al * 255 * opts.alpha_scale)[..., None]], -1)
        return to_image(res)

    return per_frame(img, frames, one)


def caption(img, frames=1, opts=None):
    """Plain one-frame vanilla plates (text buttons): a solid SLATE caption plate over the opaque bounding box,
    ending in the stepped tail (the engine shader brightens it on hover). Soft shadows, rivets and rounded ends go."""
    def one(fr, _i):
        shape = plate_shape(to_array(fr)[..., 3] / 255.0)
        if shape is None:
            return regrade(fr, 1, opts)
        x0, y0, x1, y1 = shape["bbox"]
        out = blank(fr.width, fr.height)
        out.paste(plate(x1 - x0, y1 - y0, SLATE, 1.0 * (opts.alpha_scale if opts else 1.0)), (x0, y0))
        return out
    return per_frame(img, frames, one)


def quiet(img, frames=1, opts=None):
    """Frames around a hole: dark slate at most; only signal red / green (a red alarm line) keeps its colour."""
    o = Opts(**{**(opts.__dict__ if opts else {}), "plate": False})
    return regrade(img, frames, o, QUIET_RAMP)


def keyer(img, frames=1, opts=None):
    """Glows, highlight overlays and selection frames: shape kept, colour keyer blue (pressed blue in the dim
    parts)."""
    a = to_array(img)
    lum = luma(a[..., :3]) / 255.0
    top = max(float(np.percentile(lum[a[..., 3] > 8], 99)) if (a[..., 3] > 8).any() else 1.0, 0.05)
    vis = a[..., 3] > 8
    spread = top - (float(np.percentile(lum[vis], 50)) if vis.any() else top)
    n = np.clip(lum / top, 0, 1)
    t = smoothstep(0.0, 0.7, n)[..., None]
    rgb = np.array(KEY_BLUE_DOWN, np.float32) * (1 - t) + np.array(KEY_BLUE, np.float32) * t
    if spread > 0.1:        # a glow's hot core lifts towards P; a flat selection fill stays exactly KEY_BLUE
        rgb = rgb + (np.array(P, np.float32) - rgb) * (0.25 * smoothstep(0.9, 1.0, n))[..., None]
    return to_image(np.concatenate([rgb, a[..., 3:4] * (opts.alpha_scale if opts else 1.0)], -1))


# knob frames in vanilla button order (normal, hover, pressed, disabled)
KNOB_STATES = ((P, SCROLL_KNOB_ALPHA), (P, 1.0), (KEY_BLUE, 1.0), (D, DISABLED_ALPHA))


def knob(img, frames=1, opts=None):
    """Glossy scroll / slider knobs: the vanilla silhouette as a flat disc (P at 70 %, hover P, pressed keyer,
    disabled D at 30 %). Sphere shading, specular dots and drop shadows go."""
    out = []
    for i, fr in enumerate(split_frames(img, frames)):
        a = to_array(fr)
        al = a[..., 3] / 255.0
        # the soft outer rim / shadow (alpha below ~0.6) goes; the opaque disc stays, anti-aliased
        m = smoothstep(0.55, 0.85, al)
        rgb, alpha = KNOB_STATES[min(i, len(KNOB_STATES) - 1)]
        res = np.zeros(a.shape, np.float32)
        res[..., :3] = rgb
        res[..., 3] = m * 255 * alpha * (opts.alpha_scale if opts else 1.0)
        out.append(to_image(res))
    return join_frames(out)


# state plates of the trees (focus title plates, tech items): one flat tone per state, so completed / available /
# blocked stay apart (vanilla: gold / green-grey / brown, tan / green / grey stripes)
STATE_TONES = {
    "ready": (SLATE, 0.94),          # available, can_start, start
    "done": (DONE_G, 0.94),          # completed, researched (semantic G, dark)
    "blocked": (RAISED, 0.92),       # unavailable
    "branch": (RAISED, 0.92),        # other branch taken: raised with a D hatch
    "active": (KEY_BLUE, 0.95),      # currently researching / current
}
STATE_WORDS = (     # first match wins (unavailable contains available)
    ("blocked", r"unavailable|locked|disabled|inactive|deselected|unselected|cooldown"),
    ("done", r"completed|researched|done"),
    ("active", r"currently_researching|researching|current|selected|active"),
    ("branch", r"branch"),
    ("ready", r"can_start|start|available|enabled|unlocked|ready"),
)
# sibling textures that differ only by a state word (the orchestrator sets entry["sibling_state"]): flat panels and
# plates get one tone per state, so enabled / disabled, available / locked, ... never come out identical
SIBLING_TONES = {"ready": "slate", "done": "done", "blocked": "board", "branch": "raised"}
STATE_BODY = {"keyer": KEY_BLUE, "active": KEY_BLUE, "done": DONE_G, "blocked": RAISED, "branch": RAISED,
              "ready": SLATE}


def state_of(path):
    """State word of a texture name -> ready / done / blocked / branch / active, or ''."""
    name = Path(path).name.lower()
    for st, rx in STATE_WORDS:
        if re.search(r"(^|_)(" + rx + r")(_|\.)", name):
            return st
    return ""


def state_plate(img, frames=1, opts=None):
    """Tree state plates: the plate body (the widest rows of the silhouette) becomes one flat rectangle in the
    state tone; wings, rims and painted texture go. keep_below keeps the vanilla pixels under the body (joint focus
    plates: the participants' flag ribbons, content colours)."""
    opts = opts or Opts(mode="state", state="ready")
    rgb, alpha = STATE_TONES.get(opts.state or "ready", STATE_TONES["ready"])

    def one(fr, _i):
        a = to_array(fr)
        m = a[..., 3] > 128
        out = np.zeros(a.shape, np.float32)
        if m.sum() < 16:
            return to_image(out)
        widths = m.sum(1)
        rows = np.nonzero(widths >= 0.9 * widths.max())[0]
        runs = np.split(rows, np.nonzero(np.diff(rows) > 1)[0] + 1)
        run = max(runs, key=len)
        y0, y1 = int(run[0]), int(run[-1]) + 1
        cols = np.nonzero(m[y0:y1].any(0))[0]
        x0, x1 = int(cols[0]), int(cols[-1]) + 1
        out[y0:y1, x0:x1, :3] = rgb
        out[y0:y1, x0:x1, 3] = 255 * alpha * opts.alpha_scale
        if opts.state == "branch":
            yy, xx = np.mgrid[y0:y1, x0:x1]
            hatch = ((xx + yy) % 18) < 6
            sub = out[y0:y1, x0:x1, :3]
            sub[hatch] = sub[hatch] * (1 - FIELD_ALPHA) + np.array(D, np.float32) * FIELD_ALPHA
        if opts.keep_below and y1 + 1 < a.shape[0]:
            out[y1 + 1:] = a[y1 + 1:]
        return to_image(out)

    return per_frame(img, frames, one)


def _levels(values, weights, k, merge=0.055, min_share=0.035):
    """1-D weighted k-means with merging: returns sorted level centres (at most k)."""
    if values.size == 0:
        return [0.0]
    if values.size > 250000:                       # deterministic subsample
        step = values.size // 250000 + 1
        values, weights = values[::step], weights[::step]
    c = np.percentile(values, np.linspace(15, 85, k)) if k > 1 else np.array([np.average(values, weights=weights)])
    c = np.unique(np.round(c, 4))
    for _ in range(25):
        lab = np.argmin(np.abs(values[:, None] - c[None, :]), 1)
        new = np.array([np.average(values[lab == i], weights=weights[lab == i]) if (lab == i).any() else c[i]
                        for i in range(len(c))])
        if np.allclose(new, c, atol=1e-4):
            break
        c = new
    c = list(np.sort(c))
    while len(c) > 1:                              # merge close or tiny levels
        lab = np.argmin(np.abs(values[:, None] - np.array(c)[None, :]), 1)
        share = np.array([weights[lab == i].sum() for i in range(len(c))]) / max(weights.sum(), 1e-6)
        gaps = np.diff(c)
        i_gap = int(np.argmin(gaps))
        i_small = int(np.argmin(share))
        if gaps[i_gap] < merge:
            i, j = i_gap, i_gap + 1
        elif share[i_small] < min_share:
            j = i_small
            i = j - 1 if j == len(c) - 1 or (j > 0 and c[j] - c[j - 1] < c[j + 1] - c[j]) else j + 1
            i, j = min(i, j), max(i, j)
        else:
            break
        wi, wj = share[i] + 1e-9, share[j] + 1e-9
        c[i:j + 1] = [(c[i] * wi + c[j] * wj) / (wi + wj)]
    return c


TONE_ORDER = ("board", "raised", "field", "paper")
TONE_LUMA = (0.24, 0.45, 0.6)   # vanilla level luma: < 0.24 board, < 0.45 raised, < 0.6 field, else paper


def _tone_names(centres, opts):
    """Level centres (vanilla luma, ascending) -> tone names. Absolute luma decides (dark metal -> board, mid
    plates -> raised, paper / light plates -> field), so a light state plate stays lighter than a dark one of the
    same set; levels far apart never share a tone."""
    if opts.tones:
        names = list(opts.tones)
        return (names + [names[-1]] * len(centres))[:len(centres)]
    idx = [int(np.searchsorted(TONE_LUMA, c)) for c in centres]
    if opts.dark_text is False:         # no dark text on it: paper becomes the field tone (dark, on spec)
        idx = [min(i, 2) for i in idx]
    for i in range(1, len(idx)):
        if idx[i] <= idx[i - 1] < 2 and centres[i] - centres[i - 1] > opts.bump:
            idx[i] = idx[i - 1] + 1           # bumps never reach "paper": that needs a really light vanilla level
        idx[i] = max(idx[i], idx[i - 1])
    return [TONE_ORDER[i] for i in idx]


def components(mask):
    """4-connected components of a bool array -> (int32 labels, count). Uses scipy when present."""
    try:
        from scipy import ndimage   # noqa: PLC0415 - optional speed-up
        lab, n = ndimage.label(mask)
        return lab.astype(np.int32), int(n)
    except Exception:   # noqa: BLE001
        pass
    h, w = mask.shape
    m = mask.tolist()
    out = np.zeros((h, w), np.int32).tolist()
    n = 0
    for y in range(h):
        for x in range(w):
            if m[y][x] and not out[y][x]:
                n += 1
                stack = [(y, x)]
                out[y][x] = n
                while stack:
                    cy, cx = stack.pop()
                    for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                        if 0 <= ny < h and 0 <= nx < w and m[ny][nx] and not out[ny][nx]:
                            out[ny][nx] = n
                            stack.append((ny, nx))
    return np.array(out, np.int32), n


RECT_FILL = 0.62     # a region filling at least this much of its bounding box becomes that rectangle


def snap_rects(lab, vis, major, ksize):
    """Vanilla layout regions -> axis-aligned rectangles; irregular regions (painted art, rings, blobs) fall back
    to the major tone. Larger rectangles are painted first so nested panels survive."""
    h, w = lab.shape
    s = max(1, int(np.ceil(np.sqrt(h * w / 60000.0))))
    low, lvis = lab[::s, ::s], vis[::s, ::s]
    rects = []
    for li in np.unique(lab[vis]):
        if li == major:
            continue
        comp, n = components((low == li) & lvis)
        if n == 0:
            continue
        ys, xs = np.nonzero(comp)
        ids = comp[ys, xs]
        size = np.bincount(ids, minlength=n + 1)
        bx0 = np.full(n + 1, 1 << 30, np.int64)
        by0 = np.full(n + 1, 1 << 30, np.int64)
        bx1 = np.zeros(n + 1, np.int64)
        by1 = np.zeros(n + 1, np.int64)
        np.minimum.at(bx0, ids, xs)
        np.minimum.at(by0, ids, ys)
        np.maximum.at(bx1, ids, xs)
        np.maximum.at(by1, ids, ys)
        for ci in range(1, n + 1):
            if size[ci] * s * s < 2 * ksize * ksize:
                continue
            X0, Y0 = max(0, int(bx0[ci] - 1) * s), max(0, int(by0[ci] - 1) * s)
            X1, Y1 = min(w, int(bx1[ci] + 2) * s), min(h, int(by1[ci] + 2) * s)
            sub = lab[Y0:Y1, X0:X1] == li
            yy, xx = np.nonzero(sub)
            if yy.size == 0:
                continue
            x0, x1, y0, y1 = X0 + xx.min(), X0 + xx.max() + 1, Y0 + yy.min(), Y0 + yy.max() + 1
            area = (x1 - x0) * (y1 - y0)
            fill = sub[y0 - Y0:y1 - Y0, x0 - X0:x1 - X0].sum() / area
            if fill >= RECT_FILL:
                rects.append((area, int(li), (x0, y0, x1, y1)))
    # thin bars along the outer edge are the vanilla frame / border: no frames in broadcast, they go
    vy, vx = np.nonzero(vis)
    if vy.size:
        ex0, ex1, ey0, ey1 = vx.min(), vx.max() + 1, vy.min(), vy.max() + 1
        edge = max(ksize, 4)
        thin = max(ksize, 6)

        def frame_bar(r):
            x0, y0, x1, y1 = r
            touches = x0 - ex0 <= edge or ex1 - x1 <= edge or y0 - ey0 <= edge or ey1 - y1 <= edge
            return touches and min(x1 - x0, y1 - y0) <= thin
        rects = [r for r in rects if not frame_bar(r[2])]
    new = np.full_like(lab, major)
    for _area, li, (x0, y0, x1, y1) in sorted(rects, key=lambda r: -r[0]):
        new[y0:y1, x0:x1] = li
    return new


def flatten(img, frames=1, opts=None):
    """Flat panels in the vanilla layout (see module doc). Levels are shared by all frames so a selected frame stays
    distinguishable from the normal one."""
    opts = opts or Opts(mode="flatten")
    parts = split_frames(img, frames)
    fw, fh = parts[0].size
    arrs = [to_array(p) for p in parts]
    sigma = float(np.clip(min(fw, fh) / 18.0, 1.2, 7.0))
    smooth = []
    for a in arrs:
        al = a[..., 3] / 255.0
        smooth.append(masked_gauss(luma(a[..., :3]) / 255.0, np.maximum(al, 0.01), sigma))
    vals = np.concatenate([s[a[..., 3] > 128] for s, a in zip(smooth, arrs)])
    wts = np.ones_like(vals)
    if vals.size < 16:                             # translucent texture: use everything visible
        vals = np.concatenate([s[a[..., 3] > 4] for s, a in zip(smooth, arrs)])
        wts = np.concatenate([a[..., 3][a[..., 3] > 4] for a in arrs]) / 255.0
    visible = np.concatenate([a[..., 3][a[..., 3] > 4] for a in arrs])
    mean_alpha = float(visible.mean()) / 255.0 if visible.size else 0.0
    k = opts.levels if mean_alpha >= 0.6 else 1    # translucent photo overlays: one tone, no blobs
    centres = _levels(vals, wts, max(1, k), merge=opts.merge)
    names = _tone_names(centres, opts)
    cols = np.array([TONES[n][0] for n in names], np.float32)
    alphas = np.array([TONES[n][1] for n in names], np.float32)
    ksize = opts.open_px or int(np.clip(round(min(fw, fh) / 9.0), 3, 11))
    ksize += (ksize + 1) % 2                       # odd
    c = np.array(centres, np.float32)
    major = 0
    if len(c) > 1:                                 # one background tone for every frame
        allv = np.concatenate([np.argmin(np.abs(s[a[..., 3] > 4][:, None] - c[None, :]), -1)
                               for s, a in zip(smooth, arrs)])
        major = int(np.argmax(np.bincount(allv, minlength=len(c)))) if allv.size else 0
    out_parts = []
    paper_ids = [i for i, n in enumerate(names) if n == "paper"]
    for s, a in zip(smooth, arrs):
        lab = np.argmin(np.abs(s[..., None] - c[None, None, :]), -1).astype(np.uint8)
        al = a[..., 3] / 255.0
        vis = al > 0.02
        if len(c) > 1 and vis.any():
            for li in range(len(c)):
                if li == major:
                    continue
                m = Image.fromarray(((lab == li) * 255).astype(np.uint8), "L")
                opened = m.filter(ImageFilter.MinFilter(ksize)).filter(ImageFilter.MaxFilter(ksize))
                gone = (np.asarray(m) > 0) & (np.asarray(opened) == 0)
                lab[gone] = major
            if opts.rects:
                lab = snap_rects(lab, vis, major, ksize).astype(np.uint8)
        al_eff = np.clip(al / 0.85, 0, 1)
        # paper surfaces and rect_alpha: the silhouette becomes its bounding rectangle (no torn paper edges)
        paper_px = (np.isin(lab, paper_ids) & vis) if paper_ids else np.zeros_like(vis)
        if opts.rect_alpha or (paper_px.sum() > 0.3 * max(vis.sum(), 1)):
            solid = al > 0.5
            if solid.sum() >= 16:
                ys, xs = np.nonzero(solid)
                y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
                if solid[y0:y1, x0:x1].mean() >= 0.55:
                    rect = np.zeros_like(solid)
                    rect[y0:y1, x0:x1] = True
                    lab[rect & ~vis] = major
                    al_eff = rect.astype(np.float32)
                    vis = rect
                    if paper_ids:
                        paper_px = np.isin(lab, paper_ids) & vis
        if paper_px.any():
            opts.paper = True
        rgb = cols[lab]
        t_alpha = alphas[lab]
        if opts.tint > 0 or opts.any_hue:
            rgb = _semantic_tint(rgb, lab, a, vis, cols, opts.tint, any_hue=opts.any_hue)
        a_out = t_alpha * al_eff * opts.alpha_scale
        # small signal marks (red / green lights, ticks, crosses) inside a flat panel keep their vanilla colour;
        # a painted colour surface (more than 25 % of the frame) is left to the dark tint
        sw = semantic_weight(a[..., :3], orange=opts.orange) * (al > 0.5)
        sig = smoothstep(0.6, 0.9, sw)
        if not opts.guides and sig.max() > 0 and 0 < (sig > 0.5).mean() <= 0.25:   # not on big painted bgs
            rgb = rgb * (1 - sig[..., None]) + legible(a[..., :3]) * sig[..., None]
            a_out = np.maximum(a_out, sig * al)
        res = np.concatenate([rgb, (a_out * 255)[..., None]], -1)
        if opts.guides:
            res = _guides(a, res)
        out_parts.append(to_image(res))
    if len(parts) >= 2 and not opts.tones:
        # frames that differ in vanilla (states) must not come out identical: regrade keeps their differences
        def spread(xs):
            return max(float(np.abs(x - xs[0]).mean()) for x in xs[1:])
        if spread([to_array(o) for o in out_parts]) < 1.0 and spread(arrs) > 8.0 and                 not (opts.accent in ("fill", "bar") and len(parts) == 2):
            o2 = Opts(**{**opts.__dict__, "mode": "regrade", "plate": False, "any_hue": True,
                         "sat_lo": 0.18, "sat_hi": 0.35})
            o2.why = opts.why
            return regrade(img, frames, o2)
    if opts.active and opts.accent in ("fill", "bar") and len(parts) == 2:
        out_parts = _accent_active(arrs, out_parts, opts)
    elif opts.accent == "bar1":
        out_parts = [_keyer_bar(a, o) for a, o in zip(arrs, out_parts)]
    return join_frames(out_parts)


GUIDE_MIN = 60          # a vanilla divider must run straight for at least this many px (and 30 % of the side)


def _runs(mask):
    """Longest run of True along axis 0 for every column -> (length, start) arrays."""
    h, w = mask.shape
    pad = np.zeros((h + 2, w), np.int8)
    pad[1:-1] = mask
    d = np.diff(pad, axis=0)
    best_len = np.zeros(w, np.int32)
    best_start = np.zeros(w, np.int32)
    for x in np.nonzero(mask.any(0))[0]:
        st = np.nonzero(d[:, x] == 1)[0]
        en = np.nonzero(d[:, x] == -1)[0]
        ln = en - st
        i = int(np.argmax(ln))
        best_len[x], best_start[x] = ln[i], st[i]
    return best_len, best_start


def _guides(a, res):
    """Long straight vanilla dividers (column and row separators) -> 1 px D hairlines at HAIRLINE_ALPHA over the
    flat tone, so the flat panels keep the vanilla layout guides. Painted grain rarely runs straight that far."""
    lum = luma(a[..., :3]) / 255.0
    op = a[..., 3] > 200
    out = res.copy()
    hl = np.array(D, np.float32)
    for axis in (0, 1):     # 0: vertical lines (runs down columns), 1: horizontal lines
        L = lum if axis == 0 else lum.T
        O = op if axis == 0 else op.T
        hp = np.abs(L - box_blur(L, 3, 1))
        ridge = (hp > 0.07) & O
        ln, st = _runs(ridge)
        need = max(GUIDE_MIN, int(0.3 * L.shape[0]))
        xs = [int(x) for x in np.argsort(-ln) if ln[x] >= need][:24]
        taken = set()
        for x in sorted(xs):
            if x - 1 in taken or x + 1 in taken:
                continue
            taken.add(x)
            y0, y1 = int(st[x]), int(st[x] + ln[x])
            seg = out[y0:y1, x] if axis == 0 else out[x, y0:y1]
            if (seg[:, 3] / 255.0).mean() < 0.3:
                continue
            seg[:, :3] = seg[:, :3] * (1 - HAIRLINE_ALPHA) + hl * HAIRLINE_ALPHA
    return out


def _keyer_bar(a, out_img):
    """A selected single list entry: 4 px keyer bar at the left of the plate's bounding box."""
    shape = plate_shape(a[..., 3] / 255.0, min_fill=0.6)
    if shape is None:
        return out_img
    x0, y0, x1, y1 = shape["bbox"]
    bar = blank(*out_img.size)
    bar.paste(KEY_BLUE + (255,), (x0, y0, min(x1, x0 + 4), y1))
    out = out_img.copy()
    out.alpha_composite(bar)
    return out


def _semantic_tint(rgb, lab, a, vis, cols, gain, any_hue=False):
    """Flat regions whose vanilla colour carries meaning (saturated red / green / blue, or strong yellow) keep a
    dark version of it, so state plates (researched, blocked, theatre colours) stay apart. any_hue (content-like
    colour strips: theatre colours, category rows): every coloured region keeps a legible version of its hue."""
    rgb = rgb.copy()
    w8 = a[..., 3] / 255.0
    if any_hue:
        _h, s_, v_ = hue_sat_val(a[..., :3])
        colourful = (s_ > 0.3) & (v_ > 0.2) & (w8 > 0.5)
    for li in np.unique(lab[vis]):
        m = (lab == li) & vis
        wt = w8[m]
        if wt.sum() < 4:
            continue
        if any_hue:
            # per region: the mean colour of its colourful pixels, if there are enough of them
            cm = m & colourful
            if cm.sum() >= max(8, 0.12 * m.sum()):
                tone = legible(a[..., :3][cm].mean(0).reshape(1, 1, 3), 0.55)[0, 0]
                rgb[m] = cols[li] * 0.45 + tone * 0.55
            continue
        mean = (a[..., :3][m] * wt[:, None]).sum(0) / wt.sum()
        px = mean.reshape(1, 1, 3)
        w = max(float(semantic_weight(px, sat_lo=0.18, sat_hi=0.4)[0, 0]),
                float(_band(hue_sat_val(px)[0][0, 0], *YELLOW_BAND) *
                      smoothstep(0.45, 0.65, hue_sat_val(px)[1][0, 0])))
        if w <= 0.05:
            continue
        ml = max(float(luma(px)[0, 0]), 8.0)
        base = np.maximum(cols[li], np.array(RAISED, np.float32)) if w > 0.5 else cols[li]
        rel = np.clip((mean - ml) / ml, -1, 2)
        rgb[m] = np.clip(base + w * gain * rel * float(luma(base.reshape(1, 1, 3))[0, 0]), 0, 255)
    return rgb


def _accent_active(arrs, outs, opts):
    """Two-frame tabs / list entries (normal + selected): the brighter vanilla frame is taken as the active one.
    Tabs get a keyer plate; list entries keep the flat panel plus a 4 px keyer bar on the left. (Vanilla tabs:
    frame 1 = selected, the brighter one, e.g. countrytechnologyview.gui research_slots_tab frame = 1.)"""
    def mean_luma(a):
        w = a[..., 3] / 255.0
        return float((luma(a[..., :3]) / 255.0 * w).sum() / max(w.sum(), 1e-6))
    lum = [mean_luma(a) for a in arrs]
    hi = int(np.argmax(lum))
    if abs(lum[0] - lum[1]) < 0.01:
        return outs
    a = arrs[hi]
    al = np.clip(a[..., 3] / 255.0 / 0.85, 0, 1)
    if opts.accent == "fill":
        res = np.zeros(a.shape, np.float32)
        res[..., :3] = KEY_BLUE
        res[..., 3] = al * 255 * 0.95
        outs[hi] = to_image(res)
        return outs
    shape = plate_shape(a[..., 3] / 255.0, min_fill=0.6)
    if shape is None:
        return outs
    x0, y0, x1, y1 = shape["bbox"]
    bar = blank(*outs[hi].size)
    bar.paste(KEY_BLUE + (255,), (x0, y0, min(x1, x0 + 4), y1))
    out = outs[hi].copy()
    out.alpha_composite(bar)
    outs[hi] = out
    return outs


def clear(img, frames=1, opts=None):
    return blank(img.width, img.height)


MODES = {"regrade": regrade, "caption": caption, "quiet": quiet, "keyer": keyer, "flatten": flatten,
         "clear": clear, "knob": knob, "state": state_plate}

# ---------------------------------------------------------------------------------------------------------------
# Mode selection
# ---------------------------------------------------------------------------------------------------------------
CLASS_MODE = {
    "view_bg": "flatten", "panel_bg": "flatten", "tiled_window": "flatten", "header": "flatten",
    "list_entry": "flatten", "tab": "flatten", "tooltip": "flatten", "textfield": "flatten",
    "event_frame": "flatten",
    "button": "regrade", "checkbox": "regrade", "scrollbar": "regrade", "slider": "regrade",
    "dropdown": "regrade", "bar": "regrade", "separator": "regrade", "topbar": "regrade", "minimap": "regrade",
    "outliner": "regrade", "menubar": "regrade", "frame": "regrade", "other_chrome": "regrade",
}
FLAT_MIN_PX = 3000       # flatten classes below this many px per frame are regraded (small plates, emblems)
GUIDES_MIN_SIDE = 150    # flatten view_bg / panel_bg at least this big keep their long dividers as hairlines

# .gfx files that define content (illustrations), not chrome: their textures stay vanilla
CONTENT_GFX = ("interface/technologies.gfx",)

# Per-texture overrides: (fnmatch pattern on the path relative to gfx/interface, Opts kwargs). First match wins.
OVERRIDES = [
    # invisible click blockers / engine overlays: leave exactly as vanilla
    ("tiles/tiled_window_transparent.dds", dict(mode="keep", note="alpha ~0 click blocker")),
    ("tiles/tiled_window_transparent_*.dds", dict(mode="keep")),
    # maskedShield flag overlays shade the flag itself (content; chrome.md: "flag overlays stay")
    ("flag_overlay*.dds", dict(mode="keep", note="flag shading")),
    ("flag_small*_overlay.dds", dict(mode="keep", note="flag shading")),
    ("career_profile/flag_overlay_*.dds", dict(mode="keep", note="flag shading")),
    ("construction_flag_overlay.dds", dict(mode="keep", note="flag shading")),
    # content the manifest calls chrome: colour is the function or the picture
    ("unitcontrol/color_picker_*_slider_bg.dds", dict(mode="keep", note="colour picker ramps (functional)")),
    ("topbar/musicplayer/*album_art*.dds", dict(mode="keep", note="album covers")),
    ("seized_equipment_item.dds", dict(mode="keep", note="equipment illustration (Technologies.gfx)")),
    ("doctrines/ui/doctrines_chess_piece_bg.dds", dict(mode="keep", note="coloured doctrine medallions")),
    ("placeholder_bordered*.dds", dict(mode="keep", note="debug placeholder colours")),
    # tree state plates: one flat tone per state (STATE_TONES); joint focus plates keep their flag ribbons
    ("focusview/titlebar/focus_*_joint_*bg.dds", dict(mode="state", keep_below=True, note="joint: ribbons kept")),
    ("focusview/titlebar/focus_*_bg.dds", dict(mode="state")),
    ("techtree/technology_*_item_bg.dds", dict(mode="state")),
    ("subtechnology_*_item_bg.dds", dict(mode="state")),
    ("techtree/subtechnology_*_item_bg.dds", dict(mode="state")),
    ("operatives/upgrade_button_*.dds", dict(mode="state")),
    ("techtree/*researching*anim_strip.dds", dict(mode="state", state="active", note="researching overlay")),
    # selection / active highlights: keyer blue
    ("tiles/tiled_selection*.dds", dict(mode="keyer", note="selection")),
    ("career_profile/tiled_frame_selected.dds", dict(mode="keyer", note="selection")),
    ("abilitylist/ability_active_bg*.dds", dict(mode="keyer", note="active ability")),
    ("mapmode/mapmode_buttons_selected_*.dds", dict(mode="regrade", body="keyer", note="selected map mode")),
    # glossy knobs: flat discs
    ("scroll_drager.dds", dict(mode="knob")),
    ("scrollbar_slider*.dds", dict(mode="knob")),
    ("unitcontrol/color_picker_scroll_drager.dds", dict(mode="knob")),
    ("career_profile/scroll_thumb.dds", dict(mode="knob")),
    # semantic colour lights and bars
    ("priority_strip.dds", dict(mode="regrade", yellow=True, yellow_sat=(0.3, 0.5), orange=True, sat_lo=0.12,
                                sat_hi=0.3, plate=False, ramp="bar", note="priority lights")),
    ("*progress*bar*yellow*", dict(mode="regrade", yellow=True, yellow_sat=(0.3, 0.5), orange=True, plate=False,
                                   ramp="bar")),
    ("bop/bop_bar_*_light.dds", dict(mode="regrade", orange=True, plate=False, ramp="bar", sat_lo=0.2, sat_hi=0.45,
                                     note="balance of power sides")),
    ("bop/bop_bar_*_arrow.dds", dict(mode="regrade", orange=True, plate=False, ramp="bar", sat_lo=0.2,
                                     sat_hi=0.45, note="balance of power sides")),
    # text fields read as fields
    ("small_tiles_dialog.dds", dict(mode="flatten", tones=("field",), levels=1)),
    ("edittextbox_bg*.dds", dict(mode="flatten", tones=("field",), levels=1)),
    ("*find_editbox.dds", dict(mode="flatten", tones=("field",), levels=1)),
    # tooltip and mini dialog: one uniform board
    ("tiles/tiles_dialog.dds", dict(mode="flatten", levels=1, note="tooltip")),
    ("tiles/tiled_mini_dialog*.dds", dict(mode="flatten", levels=1)),
]
TRACK_WORDS = ("_bg", "background", "frame", "track", "empty")
GLOW_WORDS = ("glow", "highlight", "flash", "pinged")
GLOW_CLASSES = {"frame", "button", "minimap", "outliner", "topbar", "menubar", "tab", "list_entry"}
SEMANTIC_NAME = re.compile(r"(^|_)(red|green|yellow|orange|failed|completed|success|alert)(_|\.)")
SELECTED_NAME = re.compile(r"(^|_)(selected|active)(_|\.)")
NOT_SELECTED_NAME = re.compile(r"(deselected|unselected|inactive|from_selected)")
SELECT_OUTLINE_CLASSES = {"frame", "tiled_window", "bar"}


def _has_hole(img, frames):
    """A frame drawn around a transparent window (flag / leader / portrait frames)."""
    f = split_frames(img, frames)[0]
    a = np.asarray(f.convert("RGBA"))[..., 3].astype(np.float32) / 255
    h, w = a.shape
    if w < 12 or h < 12:
        return False
    inner = a[h // 4: h - h // 4, w // 4: w - w // 4]
    bh, bw = max(2, h // 5), max(2, w // 5)
    band = np.concatenate([a[:bh].ravel(), a[-bh:].ravel(), a[:, :bw].ravel(), a[:, -bw:].ravel()])
    return inner.mean() < 0.25 and (a > 0.5).mean() > 0.05 and (band > 0.5).mean() > 0.2


def _semantic_glow(img, name=""):
    """True when a glow carries a signal colour: named red / green / yellow / alert / failed / completed, or its
    visible colour is mostly a semantic red (orange-red included) or green (red alerts, urgent decisions)."""
    if SEMANTIC_NAME.search(name):
        return True
    a = to_array(img)
    w = a[..., 3] / 255.0
    if w.sum() < 4:
        return False
    sem = semantic_weight(a[..., :3], sat_lo=0.3, sat_hi=0.5, orange=True)
    h = hue_sat_val(a[..., :3])[0]
    hr = np.where(h > 180, h - 360, h)
    redgreen = np.maximum(_band(hr, *ORANGE_BAND), _band(h, *GREEN_BAND))
    return float((sem * redgreen * w).sum() / w.sum()) > 0.12


def _class_mode(path, entry, img):
    """-> (mode, why)"""
    cls = (entry or {}).get("class")
    frames = int((entry or {}).get("frames") or 1)
    name = Path(path).name.lower()
    if any(wd in name for wd in GLOW_WORDS) and cls in GLOW_CLASSES:
        if img is None or not _semantic_glow(img, name):
            return "keyer", "neutral / gold glow"
        return "keep", "signal glow (red / green / yellow): vanilla colour"
    mode = CLASS_MODE.get(cls, "regrade")
    why = f"class {cls}"
    if img is not None:
        fw = img.width // max(frames, 1)
        if mode == "flatten" and fw * img.height < FLAT_MIN_PX:
            mode, why = "regrade", f"small {cls}"
        if cls in ("frame", "event_frame") and _has_hole(img, frames):
            mode, why = "quiet", "frame around a hole"
        if mode == "regrade" and cls in CAPTION_CLASSES and frames == 1:
            shape, body, detail = plate_stats(img)
            if shape is not None and body > PAPER_LUMA:       # paper / gold plates: grain is not a glyph
                detail = plate_stats(img, 0.25)[2] if (entry or {}).get("dark_text") is not True else 1.0
            if shape is not None and detail < 0.03:
                x0, y0, x1, y1 = shape["bbox"]
                if x1 - x0 >= 2.2 * (y1 - y0) and (PLATEAU[0] <= body <= PLATEAU[1] or body > PAPER_LUMA):
                    mode, why = "caption", "plain one-frame text plate"
    return mode, why


CAPTION_CLASSES = {"button", "dropdown"}
ACCENT = {"tab": "fill", "list_entry": "bar"}
# class defaults for regrade (bars carry meaning in their fill colour: no plate, semantic colour incl. yellow and
# orange-red kept)
CLASS_OPTS = {
    "bar": dict(plate=False, sat_lo=0.2, sat_hi=0.45, yellow=True, ramp="bar"),
    "separator": dict(plate=False),
}
# class defaults for flatten: entries, headers and tabs are single plates (two levels at most, gradients merge)
CLASS_FLAT_OPTS = {
    "list_entry": dict(levels=2, merge=0.09), "header": dict(levels=2, merge=0.09),
    "tab": dict(levels=2, merge=0.09), "textfield": dict(levels=1, tones=("field",)),
}
# small panels (pills, text backgrounds) lose their rounded silhouette
SMALL_RECT_CLASSES = {"panel_bg", "textfield", "header"}


def _paper_like(img):
    """A mostly light texture (vanilla luma > 0.6 on at least 30 % of its opaque area)."""
    if img is None:
        return False
    a = to_array(img)
    op = a[..., 3] > 128
    return bool(op.any() and ((luma(a[..., :3]) / 255.0 > 0.6) & op).sum() >= 0.3 * op.sum())


def mode_for(path, entry=None, img=None):
    """The Opts the generic treatment uses for one texture (path relative to gfx/interface). Order: OVERRIDES,
    content .gfx guard, class mode (glows, holes, captions), selected / active names, colour guard."""
    p = path.lower()
    name = Path(p).name
    frames = int((entry or {}).get("frames") or 1)
    for pat, kw in OVERRIDES:
        if fnmatch.fnmatch(p, pat):
            o = Opts(**kw)
            if o.mode == "state" and not o.state:
                o.state = state_of(p) or "ready"
            o.dark_text = (entry or {}).get("dark_text")
            o.why = f"override {pat}"
            return o
    defined = [d.lower() for d in ((entry or {}).get("defined_in") or [])]
    if defined and all(d in CONTENT_GFX for d in defined):
        return Opts(mode="keep", why="defined in a content .gfx")
    mode, why = _class_mode(path, entry, img)
    cls = (entry or {}).get("class")
    kw = dict(CLASS_OPTS.get(cls, {})) if mode == "regrade" else \
        dict(CLASS_FLAT_OPTS.get(cls, {})) if mode == "flatten" else {}
    if cls == "bar" and mode == "regrade" and any(wd in Path(p).stem for wd in TRACK_WORDS):
        kw["ramp"] = "regrade"      # a bar's track / frame stays dark; only fills rise to D / P
    if mode == "flatten":
        kw["accent"] = ACCENT.get(cls, "none")
        if img is not None and cls in SMALL_RECT_CLASSES and img.height <= 80 and all(
                plate_shape(to_array(f)[..., 3] / 255.0) is not None for f in split_frames(img, frames)):
            kw["rect_alpha"] = True     # rounded pills / plates become flat rectangles
        if img is not None and cls in ("view_bg", "panel_bg") and min(img.width // max(frames, 1),
                                                                       img.height) >= GUIDES_MIN_SIDE:
            kw.update(guides=True, bump=0.04, merge=0.035)
    if mode == "regrade" and cls in SMALL_RECT_CLASSES and img is not None and all(
            plate_shape(to_array(f)[..., 3] / 255.0) is not None for f in split_frames(img, frames)):
        # a small panel (rounded pill, text background): flat rectangle in one tone instead of a regraded blob
        mode, why = "flatten", f"small {cls}: flat rectangle"
        kw = dict(levels=1, rect_alpha=True, tones=("field",) if cls == "textfield" else ())
    # siblings that differ only by a state word: one tone / plate body per state
    sib = (entry or {}).get("sibling_state")
    if sib and sib != "active" and mode == "flatten" and not kw.get("tones") and             (entry or {}).get("dark_text") is not True and             not (_paper_like(img) and (entry or {}).get("dark_text") is None):   # paper that may carry text stays
        kw.update(tones=(SIBLING_TONES.get(sib, "raised"),), levels=1)
        why += f"; state sibling ({sib})"
    elif sib and sib not in ("active", "ready") and mode == "regrade" and kw.get("plate", True):
        kw["body"] = sib
        why += f"; state sibling ({sib})"
    # selected / active states: keyer
    if SELECTED_NAME.search(name) and not NOT_SELECTED_NAME.search(name) and mode not in ("keep", "keyer"):
        if cls in SELECT_OUTLINE_CLASSES or mode == "quiet":
            mode, kw, why = "keyer", {}, "selected / active outline"
        elif mode == "regrade" and kw.get("plate", True):
            kw["body"], why = "keyer", "selected / active plate"
        elif mode == "flatten" and frames == 1:
            kw["accent"], why = "bar1", "selected / active entry"
    # colour guard: multi-hue content-like textures and strips whose frames differ by hue keep their colours;
    # red-orange textures keep their orange-red as red
    if img is not None and mode in ("regrade", "caption", "flatten", "quiet"):
        prof = colour_profile(img, frames)
        if prof["warm_median"] is not None and prof["warm_median"] < 22 and mode != "flatten":
            kw["orange"] = True
            why += "; orange-red is red"
        if (prof["share"] >= 0.15 and prof["entropy"] > 1.3) or prof["hue_frames"]:
            strip = prof["hue_frames"] or mode == "flatten"
            if mode in ("caption", "quiet", "flatten"):
                # flat tones would drop the colour rows / frames: regrade keeps the layout and the hues
                kw = {k: v for k, v in kw.items() if k in ("body", "ramp")}
                kw["plate"] = mode != "flatten"
                mode = "regrade"
            # strips whose frames / rows differ by colour keep every hue (dull gold excepted); multi-colour icons
            # on plates keep red / green / blue / yellow at a lower saturation threshold
            kw.update(any_hue=strip, yellow=True, yellow_sat=(0.5, 0.65), sat_lo=0.18, sat_hi=0.35)
            why += "; colour guard (" + ("frames differ by hue" if prof["hue_frames"] else
                                         f"{prof['share']:.0%} coloured, {prof['entropy']:.1f} bits") + ")"
        elif prof["sem_cluster"] and mode == "regrade":
            kw.update(sat_lo=0.15, sat_hi=0.32)
            if prof["sem_cluster"] == "red":
                kw.update(orange=True, orange_sat=(0.25, 0.4))
            why += f"; {prof['sem_cluster']} signal icon"
    o = Opts(mode=mode, **kw)
    o.dark_text = (entry or {}).get("dark_text")
    o.why = why
    return o


def treat(src, path, entry=None, opts=None):
    """Generic broadcast version of one vanilla texture. Returns (image or None for keep, Opts used). After the
    call opts.paper tells whether a light paper tone was used."""
    opts = opts or mode_for(path, entry, src)
    if opts.mode == "keep":
        return None, opts
    frames = int((entry or {}).get("frames") or 1)
    opts.paper = False
    out = MODES[opts.mode](src, frames, opts)
    assert out.size == src.size, (path, out.size, src.size)
    return out, opts


# ---------------------------------------------------------------------------------------------------------------
# Context handed to area module functions
# ---------------------------------------------------------------------------------------------------------------
@dataclass
class Ctx:
    """What an area module's fn(ctx, src) receives besides the vanilla image.

    path          key: path relative to gfx/interface (or 'gfx/minimap/...')
    entry         manifest dict (tools/data/chrome_manifest.json) or None for textures outside the manifest
    vanilla_path  absolute Path of the vanilla source file
    out_path      absolute Path the result is written to (in the mod)
    area          area producing this texture; owner = area the rules in ingame_owners.json assign
    w, h          vanilla pixel size (the result must have exactly this size)
    frames        noOfFrames (frames side by side); frame_w = w // frames
    border        corneredTile borderSize of the first sprite as (x, y) ints, or None; borders = all of them
    cls           manifest class (button, view_bg, ...) or None
    lossless      set to True to force uncompressed output (pixel-exact edges, pixel type)
    dxt           None = the format policy decides; True = DXT5 even below the size threshold / odd sizes;
                  False = uncompressed A8R8G8B8 (same as lossless)
    dark_text     True when a vanilla .gui draws dark text (typewriter / *_black fonts, colour code b) over this
                  texture, False when no .gui does, None when unknown (engine-only sprites). A light surface under
                  dark text must stay light until the owning stream changes the text colour in its .gui.
    """
    path: str
    entry: dict = None
    vanilla_path: Path = None
    out_path: Path = None
    area: str = "generic"
    owner: str = "generic"
    w: int = 0
    h: int = 0
    frames: int = 1
    frame_w: int = 0
    border: tuple = None
    borders: list = field(default_factory=list)
    cls: str = None
    lossless: bool = False
    dxt: object = None
    warnings: list = field(default_factory=list)
    _loader: object = None      # callable(key) -> RGBA image of another vanilla texture

    # palette, so modules need no imports
    BOARD = BOARD
    BOARD_ALPHA = BOARD_ALPHA
    BOARD_ALPHA_FE = BOARD_ALPHA_FE
    RAISED = RAISED
    RAISED_ALPHA = RAISED_ALPHA
    SLATE = SLATE
    FIELD = FIELD
    FIELD_A = FIELD_A
    P = P
    D = D
    K = K
    KEY_BLUE = KEY_BLUE
    KEY_BLUE_DOWN = KEY_BLUE_DOWN
    TAIL_ALPHA = TAIL_ALPHA
    HAIRLINE_ALPHA = HAIRLINE_ALPHA
    TRACK_ALPHA = TRACK_ALPHA
    FIELD_ALPHA = FIELD_ALPHA
    SCROLL_KNOB_ALPHA = SCROLL_KNOB_ALPHA
    DISABLED_ALPHA = DISABLED_ALPHA
    SEM_G = SEM_G
    SEM_R = SEM_R
    SEM_Y = SEM_Y
    DONE_G = DONE_G

    @property
    def frame_h(self):
        return self.h

    @property
    def dark_text(self):
        return (self.entry or {}).get("dark_text")

    def generic(self, src, mode=None, **kw):
        """The generic treatment of this texture (or of src) as a starting point. mode / kw override the Opts;
        'keep' returns a copy of src."""
        opts = mode_for(self.path, self.entry, src)
        if mode or kw:
            opts = Opts(**{**opts.__dict__, **({"mode": mode} if mode else {}), **kw})
        out, _ = treat(src, self.path, self.entry, opts)
        return src.copy() if out is None else out

    def generic_mode(self, src=None):
        return mode_for(self.path, self.entry, src).mode

    def split(self, img):
        return split_frames(img, self.frames)

    def join(self, parts):
        return join_frames(parts)

    def per_frame(self, img, fn):
        return per_frame(img, self.frames, fn)

    def blank(self, w=None, h=None):
        return blank(w or self.w, h or self.h)

    def flat(self, rgb=BOARD, alpha=BOARD_ALPHA, w=None, h=None):
        return flat(w or self.w, h or self.h, rgb, alpha)

    def plate(self, w=None, h=None, rgb=SLATE, alpha=1.0, tail=None):
        return plate(w or self.frame_w, h or self.h, rgb, alpha, tail)

    def vanilla(self, key):
        """RGBA of another vanilla texture (key relative to gfx/interface or 'gfx/...')."""
        return self._loader(key)

    def warn(self, msg):
        self.warnings.append(str(msg))
