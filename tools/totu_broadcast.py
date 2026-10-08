"""Shared kit of the "broadcast" style (late-Soviet TV captions) for every Twilight of the Union UI builder.

New builders import this module only:

    import totu_broadcast as tb
    tb.save_dds(tb.frames(tb.transparent(160, 40), tb.plate(160)), tb.TOTU_TEX / "myarea" / "thing.dds")

It re-exports (imports, does not move) the palette, geometry and primitives of tools/build_menu_gfx.py and the glyphs
and font readers of tools/build_fonts.py, and adds what the in-game restyle needs: in-game surface constants, a
root-safe DDS writer with a DXT5 policy, text / localisation writers with the mod's encoding rules, plate-bank math,
flat surfaces, pixel text for any glyph at any (also non-square) cell, pixel pictograms, .gfx block helpers, a
sprite-name collision scanner and contact sheets for previews. Documentation for stream agents: docs/ui_kit.md.

Import order: build_fonts imports build_menu_gfx at module level, build_menu_gfx imports build_fonts only inside
functions, so importing build_menu_gfx first and build_fonts second is safe. Neither imports this module.
Self-test: python tools/totu_broadcast.py  (writes nothing into the mod; prints ASCII only).
"""
import io
import math
import re
import struct
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import build_menu_gfx as bmg   # noqa: E402  (first: build_fonts imports it at module level)
import build_fonts as bf       # noqa: E402

# ---------------------------------------------------------------- paths
ROOT = bmg.ROOT
SRC = bmg.SRC
GAME = bmg.GAME                                     # vanilla game folder (env HOI4_DIR)
INTERFACE = ROOT / "interface"
LOCALISATION = ROOT / "localisation"
TOTU_TEX = ROOT / "gfx" / "interface" / "totu"      # stream builders write to TOTU_TEX / "<area>"
WIDGETS_TEX = TOTU_TEX / "widgets"                  # owned by tools/build_widgets_gfx.py
FONTS_DIR = bf.OUT                                  # gfx/fonts
PREVIEW = ROOT / "tools" / "preview"                # git-ignored

# ---------------------------------------------------------------- palette (re-exported)
KEY_BLUE = bmg.KEY_BLUE                 # (30, 62, 168) keyer plate: hover / active / selected; the one saturated colour
KEY_BLUE_DOWN = bmg.KEY_BLUE_DOWN       # (17, 38, 108) pressed
CAPTION_WHITE = P = bmg.CAPTION_WHITE   # (246, 242, 234) colour code P: primary text, pictograms
CAPTION_DIM = D = bmg.CAPTION_DIM       # (172, 180, 196) colour code D: secondary text; never darker
K = (0, 0, 0)                           # colour code K: the black drop copy / baked edge at +2,+2
CS_BOARD_RGB = BOARD_RGB = bmg.CS_BOARD_RGB     # (9, 11, 16) the cold lifted black of every board
BOARD_ALPHA = bmg.BOARD_ALPHA           # 0.84 frontend boards (GFX_totu_board)
TAIL_ALPHA = bmg.TAIL_ALPHA             # (153, 77) the plate's hard two-step tail: 60 %, then 30 %
SOVIET_RED = bmg.SOVIET_RED
DUSK_STOPS = bmg.DUSK_STOPS             # photo grade ramps
STILL_RAMP = bmg.STILL_RAMP

# In-game surfaces (binding spec of the restyle)
BOARD_ALPHA_IG = 0.90                   # in-game board: BOARD_RGB at 90 % (GFX_totu_board_ig)
RAISED_RGB, RAISED_ALPHA = (18, 22, 30), 0.92   # raised sub-panel on a board (GFX_totu_raised)
SLATE_RGB = (40, 47, 62)                # idle-visible plate for buttons that must show when not hovered
FIELD_ALPHA = 0.14                      # field: D at 14 % over the board (edit boxes, dropdown faces)
HAIRLINE_ALPHA = 0.22                   # separators: D at 22 %, 1-2 px
TRACK_ALPHA = 0.18                      # empty bar / scroll track: D at 18 %
HOVER_ALPHA = 0.08                      # list row hover: D at 8 %
SLIDER_LINE_ALPHA = 0.35                # value slider line: D at 35 %
SCROLL_KNOB_ALPHA = 0.70                # scrollbar knob: P at 70 %
DISABLED_ALPHA = 0.30                   # disabled pictograms / knobs: D at 30 %
SEM_G, SEM_R, SEM_Y = (86, 172, 91), (222, 86, 70), (238, 201, 35)     # semantic colours stay (vanilla hoi fonts)
COLOURS = {"P": P, "D": D, "K": K, "G": SEM_G, "R": SEM_R, "Y": SEM_Y}

# ---------------------------------------------------------------- geometry (re-exported)
SAFE_X, SAFE_Y = bmg.SAFE_X, bmg.SAFE_Y         # 192, 108 title-safe edges
CAP_CELL, SMALL_CELL = bmg.CAP_CELL, bmg.SMALL_CELL     # 4 (totu_caption / totu_button), 2 (small fonts)
PLATE_H, PLATE_PITCH = bmg.PLATE_H, bmg.PLATE_PITCH     # 40, 44
PLATE_BOTTOM, QUIT_GAP = bmg.PLATE_BOTTOM, bmg.QUIT_GAP
PAD_L, PAD_R, TAIL = bmg.PAD_L, bmg.PAD_R, bmg.TAIL     # 22, 10, 12 (PAD_L == PAD_R + TAIL)
SMALL_PLATE_H = bmg.SMALL_PLATE_H                       # 24
SMALL_PAD_L, SMALL_PAD_R, SMALL_TAIL = bmg.SMALL_PAD_L, bmg.SMALL_PAD_R, bmg.SMALL_TAIL    # 12, 6, 6
SMALL_PLATE_X = bmg.SMALL_PLATE_X
CAPTION_SHADOW = bmg.CAPTION_SHADOW                     # 2: K copy at +2,+2
TEXT_TRAIL = bmg.TEXT_TRAIL
CHECK = bmg.CHECK                                       # 20 checkbox square
BAND_H, BAND_ALPHA, BAND_HOLD = bmg.BAND_H, bmg.BAND_ALPHA, bmg.BAND_HOLD
CAPTION_PLATES, SMALL_PLATES = bmg.CAPTION_PLATES, bmg.SMALL_PLATES     # existing GFX_totu_caption_* widths
BOARD_PAD = 22                                          # inner measure of a board (text and controls start here)

# ---------------------------------------------------------------- primitives (re-exported)
build_caption_plate = bmg.build_caption_plate   # (w, h=40, tail=12, frames=(None, KEY_BLUE, KEY_BLUE_DOWN))
build_small_plate = bmg.build_small_plate       # (w, frames=...) h 24, tail 6
keyer_strip = bmg.keyer_strip                   # (solid_w, h, colour=KEY_BLUE, steps=(6, 6))
selection_frames = bmg.selection_frames         # (fw, fh, bar, pos)
build_scrim = bmg.build_scrim                   # (w, h, a0, plateau) soft black elliptical burn
build_band = bmg.build_band                     # (top: bool) 16 x 160 edge band
build_board_tile = bmg.build_board_tile
build_checkbox = bmg.build_checkbox
build_field = bmg.build_field
menu_rows = bmg.menu_rows
# photo grading
cover = bmg.cover
lerp_stops = bmg.lerp_stops
secam = bmg.secam
smoothstep = bmg.smoothstep
blur1d = bmg.blur1d
tone = bmg.tone
grain = bmg.grain
scanlines = bmg.scanlines
radial_mask = bmg.radial_mask
eye_bar = bmg.eye_bar
build_scenario_still = bmg.build_scenario_still     # template for in-game stills (event pictures)
# text drawing for previews (engine-like)
caption_fonts = bmg.caption_fonts
draw_caption = bmg.draw_caption                 # (img, font, text, x, y, colour=P, right=False, edge=True)
loc_value = bmg.loc_value                       # (lang, key, name=None) from totu_menu_l_<lang>.yml
colour_runs, wrap_runs, draw_runs = bmg.colour_runs, bmg.wrap_runs, bmg.draw_runs
load_vanilla_font, draw_vanilla_box = bmg.load_vanilla_font, bmg.draw_vanilla_box
PIXEL_FONT = bmg.PIXEL_FONT
pixel_text_mask_ascii = bmg.pixel_text_mask     # A-Z 0-9 - . space only; use pixel_mask() below for any glyph
# glyphs and fonts (build_fonts)
GLYPHS = bf.GLYPHS                              # every 5x7 glyph incl. Cyrillic, punctuation, Latin extras
CYRILLIC, PUNCTUATION, LATIN_EXTRA = bf.CYRILLIC, bf.PUNCTUATION, bf.LATIN_EXTRA
LATIN_ALIASES = bf.LATIN_ALIASES
CODEPOINTS = bf.CODEPOINTS                      # the 685 code points of every totu font
FONTS = bf.FONTS                                # name -> (cell, lineHeight, base, shadow)
FONT_PAD = bf.PAD
glyph_key = bf.glyph_key                        # code point -> GLYPHS key (lowercase -> capital, accents -> base)
glyph_mask = bf.glyph_mask                      # (rows, cell, ss=4) CRT-rounded mask of one glyph
glyph_tile, glyph_tile_k = bf.glyph_tile, bf.glyph_tile_k
read_fnt = bf.read_fnt                          # (path) -> (common, chars)
load_font = bf.load_font                        # (name) -> (common, chars, atlas RGBA) from gfx/fonts
draw_text = draw_glyphs = bf.draw_text          # (img, font, text, x, y, colour) engine-like; returns the pen x
engine_wrap = bf.engine_wrap
strip_codes = bf.strip_codes


def rgba(rgb, alpha=1.0):
    """(r, g, b) + alpha 0..1 -> (r, g, b, a) with a = round(255 * alpha)."""
    assert 0.0 <= alpha <= 1.0, alpha
    return tuple(rgb[:3]) + (round(255 * alpha),)


def _say(*parts):
    """print() that never fails on a non-UTF-8 console (paths of this mod contain Cyrillic)."""
    print(" ".join(str(p) for p in parts).encode("ascii", "backslashreplace").decode("ascii"))


def rel(path):
    """path relative to the mod root when inside it (ASCII), else the absolute path."""
    path = Path(path)
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


# ---------------------------------------------------------------- DDS
DDS_DXT_MIN_PIXELS = 16384


def dds_policy(w, h, lossless=False):
    """'DXT5' for big textures that tolerate block compression (both sides multiples of 4, w*h >= 16384, not
    lossless), else None (uncompressed A8R8G8B8). Plates, glyphs, hairlines and anything with exact keyer colour or
    1-2 px detail is lossless: DXT5 stores colour as RGB565 and smears hard 2 px edges."""
    return "DXT5" if (not lossless and w % 4 == 0 and h % 4 == 0 and w * h >= DDS_DXT_MIN_PIXELS) else None


def dds_header(src):
    """The header fields of a DDS file (path or bytes): w, h, mips, flags, pfflags, fourcc, bits, masks, caps."""
    b = Path(src).read_bytes()[:128] if not isinstance(src, (bytes, bytearray)) else bytes(src[:128])
    if b[:4] != b"DDS ":
        raise ValueError("not a DDS file")
    _, flags, h, w, _, _, mips = struct.unpack("<7I", b[4:32])
    _, pfflags, fourcc, bits, rm, gm, bm, am = struct.unpack("<II4sIIIII", b[76:108])
    caps = struct.unpack("<I", b[108:112])[0]
    return {"w": w, "h": h, "mips": mips, "flags": flags, "pfflags": pfflags,
            "fourcc": fourcc.decode("latin-1").strip("\0"), "bits": bits, "masks": (rm, gm, bm, am), "caps": caps}


def _check_dds(data, size, fmt):
    """Raises ValueError (not assert: survives python -O) unless the header matches size and fmt, without mipmaps."""
    hd = dds_header(data)
    ok = (hd["w"], hd["h"]) == tuple(size) and hd["mips"] <= 1
    if fmt == "DXT5":
        ok = ok and bool(hd["pfflags"] & 0x4) and hd["fourcc"] == "DXT5"
    else:
        ok = ok and hd["pfflags"] == 0x41 and hd["bits"] == 32 and hd["masks"] == (0xFF0000, 0xFF00, 0xFF, 0xFF000000)
    if not ok:
        raise ValueError(f"unexpected DDS header for {size} {fmt or 'A8R8G8B8'}: {hd}")
    return hd


def save_dds(img, path, fmt=None, quiet=False, only_if_changed=True):
    """Writes img as DDS without mipmaps; works for any path (inside the mod or not). fmt None: uncompressed
    A8R8G8B8 like every texture of the mod and most of vanilla; "DXT5" only if both sides are multiples of 4, else it
    falls back to uncompressed (printed). The header is checked after encoding. only_if_changed: the file is not
    rewritten when its bytes would not change (the mod folder syncs through OneDrive). Returns True if written."""
    path = Path(path)
    img = img.convert("RGBA")
    if fmt not in (None, "DXT5"):
        raise ValueError(f"fmt {fmt!r}: use None or 'DXT5'")
    if fmt == "DXT5" and (img.width % 4 or img.height % 4):
        if not quiet:
            _say(f"save_dds: {rel(path)} {img.size} is not a multiple of 4, written uncompressed")
        fmt = None
    buf = io.BytesIO()
    if fmt:
        img.save(buf, format="DDS", pixel_format=fmt)
    else:
        img.save(buf, format="DDS")
    data = buf.getvalue()
    _check_dds(data, img.size, fmt)
    if only_if_changed and path.exists() and path.read_bytes() == data:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    if not quiet:
        _say("wrote", rel(path), f"{img.width}x{img.height}", fmt or "A8R8G8B8")
    return True


# ---------------------------------------------------------------- text files
def write_text(path, text, bom=False, only_if_changed=True):
    """UTF-8 (with BOM if bom), LF line endings. .gui / .gfx must be ASCII and are written without BOM (ValueError
    otherwise, also under python -O; nothing is written). Returns True if the file changed."""
    path = Path(path)
    text = text.replace("\r\n", "\n")
    if path.suffix.lower() in (".gui", ".gfx"):
        bad = sorted({ch for ch in text if not ch.isascii()})
        if bad:
            raise ValueError(f"{path.name}: non-ASCII characters {[hex(ord(c)) for c in bad]}")
        if bom:
            raise ValueError(f"{path.name}: .gui / .gfx are written without BOM")
    data = (b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8")
    if only_if_changed and path.exists() and path.read_bytes() == data:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return True


def write_loc(path, lang, entries, header=None, only_if_changed=True):
    """A localisation file: UTF-8 with BOM, LF, first line l_<lang>:, then ' KEY:0 "value"' per entry.
    entries: dict key -> value or an iterable of (key, value). header: optional comment lines (without '#').
    The file name must end in _l_<lang>.yml (the engine needs it). ValueError on a bad name, key or value."""
    path = Path(path)
    if not path.name.endswith(f"_l_{lang}.yml"):
        raise ValueError(f"{path.name} must end in _l_{lang}.yml")
    items = entries.items() if isinstance(entries, dict) else entries
    lines = [f"l_{lang}:"] + [f" # {h}" for h in (header or [])]
    for key, value in items:
        if not re.fullmatch(r"[\w.\-]+", key):
            raise ValueError(f"bad localisation key {key!r}")
        if "\n" in value or "\r" in value:
            raise ValueError(f"{key}: use a literal \\n, not a newline")
        lines.append(f' {key}:0 "{value}"')
    return write_text(path, "\n".join(lines) + "\n", bom=True, only_if_changed=only_if_changed)


# ---------------------------------------------------------------- localisation lookup
# KEY:0 "value" with an optional trailing comment (the comment may not contain a quote; the value runs to the last
# quote before it, as the engine reads it)
_LOC_LINE = re.compile(r'^\s*([\w.\-]+):\d*\s*"(.*)"\s*(?:#[^"]*)?$')
_LOC_REF = re.compile(r"\$([\w.\-]+)(\|[^$]*)?\$")
_loc_cache = {}


def _loc_index(base, lang):
    key = (str(base), lang)
    if key not in _loc_cache:
        idx = {}
        folder = Path(base) / "localisation" / lang
        files = sorted(folder.rglob("*.yml")) if folder.exists() else []
        # replace/ files win over the others, as in the engine
        for f in sorted(files, key=lambda p: "replace" in p.parts):
            for line in f.read_text(encoding="utf-8-sig", errors="replace").splitlines():
                m = _LOC_LINE.match(line)
                if m:
                    idx[m.group(1)] = m.group(2)
        _loc_cache[key] = idx
    return _loc_cache[key]


def _loc_raw(key, lang):
    for base in (ROOT, GAME):
        idx = _loc_index(base, lang)
        if key in idx:
            return idx[key]
    raise KeyError(f"{key} ({lang})")


def loc(key, lang="english", resolve=True, _depth=0):
    """The value of a localisation key (colour codes kept): the mod's localisation/<lang>/** first, then the vanilla
    game's; lines with a trailing # comment count. resolve: every $OTHER_KEY$ (also $OTHER_KEY|Y$) that names a
    localisation key is replaced by its value, recursively; $...$ that name no key (engine-filled variables such as
    $VALUE$) stay as written. KeyError if neither the mod nor vanilla has the key."""
    value = _loc_raw(key, lang)
    if not resolve or "$" not in value:
        return value
    if _depth > 8:
        raise ValueError(f"{key} ({lang}): $...$ references nest deeper than 8 (a cycle?)")

    def sub(m):
        try:
            return loc(m.group(1), lang, True, _depth + 1)
        except KeyError:
            return m.group(0)
    return _LOC_REF.sub(sub, value)


def labels_for(key, langs=("russian", "english")):
    """(ru, en) values of a key without colour codes, $KEY$ references resolved, for plate sizing. ValueError if a
    value still holds an engine-filled $VARIABLE$ (its width is unknown, so no plate can be picked for it)."""
    out = []
    for lang in langs:
        value = strip_codes(loc(key, lang))
        if _LOC_REF.search(value):
            raise ValueError(f"{key} ({lang}) holds an engine-filled variable, plate width unknown: "
                             f"{value.encode('ascii', 'backslashreplace').decode('ascii')}")
        out.append(value)
    return tuple(out)


# ---------------------------------------------------------------- text measurement
_fnt_cache = {}


def font_metrics(name):
    """(common, chars) of gfx/fonts/<name>.fnt, cached; None if the font is not built."""
    if name not in _fnt_cache:
        p = FONTS_DIR / f"{name}.fnt"
        _fnt_cache[name] = read_fnt(p) if p.exists() else None
    return _fnt_cache[name]


def glyph_rows(ch):
    """The 5x7 (or 8-row / wider) grid of one character as the totu fonts draw it (lowercase -> capital, accented
    Latin -> base capital, build_fonts.SHAPE_ALIAS), None for a zero-width character. ValueError if it has none."""
    cp = ord(ch)
    if cp in getattr(bf, "ZERO_WIDTH", ()):
        return None
    if cp not in CODEPOINTS:
        raise ValueError(f"no glyph for U+{cp:04X} in the totu fonts")
    key = glyph_key(cp)
    alias = getattr(bf, "SHAPE_ALIAS", {})
    for k in (key, alias.get(key), alias.get(ch), key.upper() if isinstance(key, str) else None):
        if k in GLYPHS:
            return GLYPHS[k]
    raise ValueError(f"no glyph for U+{cp:04X} in the totu fonts")


def text_advance(text, cell=CAP_CELL, font=None):
    """Sum of the advances of a single-line string (the engine's text width, trailing 1-cell gap included).
    font: a built font name ('totu_button', ...) to use its real .fnt advances; else computed from GLYPHS with
    advance = (columns + 1) * cell. Colour codes are ignored. ValueError on characters the fonts lack."""
    text = strip_codes(text)
    metrics = font_metrics(font) if font else None
    if metrics:
        chars = metrics[1]
        miss = sorted({ch for ch in text if ord(ch) not in chars})
        if miss:
            raise ValueError(f"{font} has no glyph for {miss}")
        return sum(chars[ord(ch)]["xadvance"] for ch in text)
    cx = cell if isinstance(cell, int) else cell[0]
    return sum((len(rows[0]) + 1) * cx for rows in map(glyph_rows, text) if rows)


def ink_width(text, cell=CAP_CELL, font=None):
    """Width of the drawn line: the advances without the trailing gap (= len * 6 * cell - cell for 5-column glyphs;
    the wide '№' counts its 9 columns)."""
    cx = cell if isinstance(cell, int) else cell[0]
    return max(0, text_advance(text, cell, font) - cx) if strip_codes(text) else 0


# ---------------------------------------------------------------- plate bank
# Pre-built plates for every label length; tools/build_widgets_gfx.py generates exactly this table, so plate_sprite()
# always names a declared sprite. n = label length in 5-column glyphs (the longer of RU / EN).
BIG_N_MAX, SMALL_N_MAX, TAB_N_MAX = 18, 40, 24
BANK = {
    #  kind        size     n range            frames (None = transparent)               sprite type
    "plate":    ("big",   BIG_N_MAX,   (None, KEY_BLUE, KEY_BLUE_DOWN),      "textSpriteType"),
    "plate_s":  ("small", SMALL_N_MAX, (None, KEY_BLUE, KEY_BLUE_DOWN),      "textSpriteType"),
    "slate":    ("big",   BIG_N_MAX,   (SLATE_RGB, KEY_BLUE, KEY_BLUE_DOWN), "textSpriteType"),
    "slate_s":  ("small", SMALL_N_MAX, (SLATE_RGB, KEY_BLUE, KEY_BLUE_DOWN), "textSpriteType"),
    "tab_s":    ("small", TAB_N_MAX,   (None, KEY_BLUE, None),               "spriteType"),
    "toggle_s": ("small", TAB_N_MAX,   (None, KEY_BLUE),                     "spriteType"),
    "toggle_r_s": ("small", TAB_N_MAX, (KEY_BLUE, None),                     "spriteType"),     # frame 1 = on
}
BUTTON_FONT = {"big": "totu_button", "small": "totu_button_small"}
_SIZE = {"big": (CAP_CELL, PAD_L + PAD_R + TAIL, PLATE_H, TAIL),
         "small": (SMALL_CELL, SMALL_PAD_L + SMALL_PAD_R + SMALL_TAIL, SMALL_PLATE_H, SMALL_TAIL)}


def bank_width(n, size="big"):
    """Width of the bank plate for n glyphs: big 24 n + 40, small 12 n + 22."""
    cell, pad, _, _ = _SIZE[size]
    return 6 * cell * n - cell + pad


def _labels(labels):
    return (labels,) if isinstance(labels, str) else tuple(labels)


def plate_n(labels, size="big"):
    """Bank index for (ru, en, ...) labels: the longer label's ink measured with the real button font, rounded up
    to whole 6-cell glyph advances (so a '№' takes the next width)."""
    cell = _SIZE[size][0]
    w = max(ink_width(lab, cell, BUTTON_FONT[size]) for lab in _labels(labels))
    return max(1, math.ceil((w + cell) / (6 * cell)))


def plate_w(labels, size="big", exact=False):
    """Plate width for (ru, en, ...) labels. exact=False: the bank width plate_sprite() names (= the exact width
    for labels of 5-column glyphs); exact=True: PAD + the longer ink, for custom-built plates."""
    cell, pad, _, _ = _SIZE[size]
    if exact:
        return pad + max(ink_width(lab, cell, BUTTON_FONT[size]) for lab in _labels(labels))
    return bank_width(plate_n(labels, size), size)


def big_plate_w(labels):
    """Width of the 40 px plate for labels (ru, en, ...): 22 + longest ink + 10 + 12, on the bank's 24 px grid."""
    return plate_w(labels, "big")


def small_plate_w(labels):
    """Width of the 24 px plate for labels (ru, en, ...): 12 + longest ink + 6 + 6, on the bank's 12 px grid."""
    return plate_w(labels, "small")


def bank_sprite(kind, n):
    """Sprite name of bank entry n of a BANK key ('plate', 'plate_s', 'slate', ..., 'toggle_r_s')."""
    if kind not in BANK:
        raise ValueError(f"no bank {kind!r}; BANK keys: {sorted(BANK)}")
    size, n_max = BANK[kind][0], BANK[kind][1]
    if not 1 <= n <= n_max:
        raise ValueError(f"{kind}: n {n} outside 1..{n_max}")
    return f"GFX_totu_{kind}_{bank_width(n, size)}"


def bank_kind(kind, size="big"):
    """BANK key for a kind ('plate', 'slate', 'tab', 'toggle', 'toggle_r') and size ('big', 'small')."""
    if kind in ("tab", "toggle", "toggle_r"):
        if size != "small":
            raise ValueError(f"{kind} plates are small only")
        key = kind + "_s"
    else:
        key = kind if size == "big" else kind + "_s"
    if key not in BANK:
        raise ValueError(f"kind {kind!r}")
    return key


def plate_sprite(labels, size="big", kind="plate"):
    """The bank sprite for (ru, en, ...) labels.
    kind: 'plate' (3 frames: transparent / keyer / pressed), 'slate' (slate / keyer / pressed: visible when idle),
    'tab' (small only; checkboxType: off transparent / on keyer / disabled transparent), 'toggle' (small only; 2
    frames: off / keyer), 'toggle_r' (small only; 2 frames reversed: keyer / transparent, for engine-set tabs
    whose frame 1 is the active one). Raises ValueError if the label is longer than the bank."""
    key = bank_kind(kind, size)
    n = plate_n(labels, size)
    n_max = BANK[key][1]
    if n > n_max:
        raise ValueError(f"label of {n} glyphs is longer than the {key} bank ({n_max}): {_labels(labels)}; shorten "
                         "it, use the small size, or build a custom plate with build_caption_plate")
    return bank_sprite(key, n)


def plate_sprite_for_key(key, size="big", kind="plate"):
    """plate_sprite for the Russian and English values of a localisation key (mod first, then vanilla)."""
    return plate_sprite(labels_for(key), size, kind)


# ---------------------------------------------------------------- flat surfaces and plates
def flat(w, h, rgb, alpha=1.0):
    """w x h of one colour at alpha (0..1)."""
    return Image.new("RGBA", (w, h), rgba(rgb, alpha))


def transparent(w, h, frames=1):
    """Fully transparent w*frames x h (sprites the engine needs but nothing should show)."""
    return Image.new("RGBA", (w * frames, h), (0, 0, 0, 0))


def _tail(h, tail):
    return tail if tail is not None else (TAIL if h > SMALL_PLATE_H else SMALL_TAIL)


def plate(w, h=PLATE_H, colour=KEY_BLUE, tail=None):
    """One plate frame: solid colour for w - tail px, then the hard two-step tail (TAIL_ALPHA). tail defaults to 12
    on plates taller than 24 px, else 6; tail=0 gives a plain block."""
    tail = _tail(h, tail)
    if tail == 0:
        return flat(w, h, colour)
    return build_caption_plate(w, h, tail, (colour,))


def slate_plate(w, h=PLATE_H, tail=None):
    """The idle-visible SLATE plate (40, 47, 62) with the same tail, for one-frame vanilla buttons (the engine
    shader brightens it on hover) and the first frame of the slate bank."""
    return plate(w, h, SLATE_RGB, tail)


def plate_frames(w, h=PLATE_H, frames=(None, KEY_BLUE, KEY_BLUE_DOWN), tail=None):
    """Plate frames side by side for any height (None = transparent frame). tail=0: flat blocks without the tail
    (list rows such as an MP server row: plate_frames(972, 30, (None, KEY_BLUE), tail=0))."""
    tail = _tail(h, tail)
    if tail == 0:
        out = transparent(w, h, len(frames))
        for i, col in enumerate(frames):
            if col is not None:
                out.paste(flat(w, h, col), (i * w, 0))
        return out
    return build_caption_plate(w, h, tail, frames)


def bar_pair(w, h, fill=KEY_BLUE, track_alpha=TRACK_ALPHA, fill_alpha=1.0):
    """(full, empty) textures of a progressbartype at its full size w x h (the engine reveals textureFile1 over
    textureFile2; neither stretches): full = fill (KEY_BLUE or P) at fill_alpha, empty = the D track at
    track_alpha (18 %). Declare them with progressbar_block()."""
    return flat(w, h, fill, fill_alpha), flat(w, h, D, track_alpha)


def progressbar_block(name, full_texture, empty_texture, size, horizontal=True, comment=None):
    """A progressbartype definition as vanilla writes it (effectFile gfx/FX/progress.lua, white colours so the
    textures keep their colour). size: (x, y) = the textures' size."""
    if not name.startswith("GFX_"):
        raise ValueError(name)
    out = ["\tprogressbartype = {", f'\t\tname = "{name}"' + (f"\t# {comment}" if comment else ""),
           f'\t\ttextureFile1 = "{full_texture}"', f'\t\ttextureFile2 = "{empty_texture}"',
           f"\t\tsize = {{ x={size[0]} y={size[1]} }}", "\t\tcolor = { 1.0 1.0 1.0 }",
           "\t\tcolortwo = { 1.0 1.0 1.0 }", '\t\teffectFile = "gfx/FX/progress.lua"',
           f"\t\thorizontal = {'yes' if horizontal else 'no'}", "\t}"]
    return "\n".join(out)


def frames(*images):
    """Frames side by side (all the same size): the strip a noOfFrames sprite reads. Accepts images or one list."""
    if len(images) == 1 and isinstance(images[0], (list, tuple)):
        images = tuple(images[0])
    size = images[0].size
    assert all(im.size == size for im in images), [im.size for im in images]
    out = Image.new("RGBA", (size[0] * len(images), size[1]), (0, 0, 0, 0))
    for i, im in enumerate(images):
        out.paste(im.convert("RGBA"), (i * size[0], 0))
    return out


def split_frames(img, n):
    """The n frames of a strip."""
    fw = img.width // n
    return [img.crop((i * fw, 0, (i + 1) * fw, img.height)) for i in range(n)]


def over(base, layer, xy=(0, 0)):
    """layer composited over a copy of base at xy (negative positions clip)."""
    out = base.convert("RGBA").copy()
    x, y = xy
    crop = layer.crop((max(0, -x), max(0, -y), layer.width, layer.height))
    out.alpha_composite(crop, (max(0, x), max(0, y)))
    return out


# ---------------------------------------------------------------- pixel text (any glyph, any cell)
def _cells(cell):
    return (cell, cell) if isinstance(cell, int) else (int(cell[0]), int(cell[1]))


def _layout(text, line_gap):
    """[(x_cell, y_cell, rows)] of every glyph and the size in cells. Capitals start at y 0; 8-row glyphs hang their
    last row below the baseline (into the line gap, or one extra row on the last line)."""
    placed, w_cells, h_cells = [], 0, 0
    for li, line in enumerate(text.split("\n")):
        y0, x = li * (7 + line_gap), 0
        for ch in line:
            rows = glyph_rows(ch)
            if rows is None:                # zero-width
                continue
            placed.append((x, y0, rows))
            x += len(rows[0]) + 1
            h_cells = max(h_cells, y0 + len(rows))
        w_cells = max(w_cells, x - 1 if line else 0)
        h_cells = max(h_cells, y0 + 7)
    return placed, max(w_cells, 0), h_cells


def pixel_text_size(text, cell=SMALL_CELL, line_gap=2):
    """Ink size (w, h) in px of pixel_mask(text, cell)."""
    cx, cy = _cells(cell)
    _, wc, hc = _layout(text, line_gap)
    return wc * cx, hc * cy


def pixel_mask(text, cell=SMALL_CELL, line_gap=2, crt=True, ss=4):
    """L mask of text in the totu glyphs at cell px per font cell (int, or (cx, cy) for non-square cells such as
    teletext double height (2, 3)). '\\n' breaks lines (pitch 7 + line_gap cells). crt: the fonts' rounding (drawn ss
    times larger, blurred 0.12 cell, re-thresholded, downsampled) - identical to build_fonts.glyph_mask on square
    cells; crt=False: crisp cells."""
    cx, cy = _cells(cell)
    placed, wc, hc = _layout(text, line_gap)
    if not crt:
        m = Image.new("L", (max(1, wc * cx), max(1, hc * cy)), 0)
        d = ImageDraw.Draw(m)
        for x0, y0, rows in placed:
            for gy, row in enumerate(rows):
                for gx, v in enumerate(row):
                    if v == "#":
                        d.rectangle(((x0 + gx) * cx, (y0 + gy) * cy, (x0 + gx + 1) * cx - 1, (y0 + gy + 1) * cy - 1),
                                    fill=255)
        return m
    sx, sy = cx * ss, cy * ss
    big = Image.new("L", (max(1, wc * sx), max(1, hc * sy)), 0)
    d = ImageDraw.Draw(big)
    for x0, y0, rows in placed:
        for gy, row in enumerate(rows):
            for gx, v in enumerate(row):
                if v == "#":
                    d.rectangle(((x0 + gx) * sx, (y0 + gy) * sy, (x0 + gx + 1) * sx - 1, (y0 + gy + 1) * sy - 1),
                                fill=255)
    big = big.filter(ImageFilter.GaussianBlur(min(sx, sy) * 0.12)).point(lambda v: 255 if v > 110 else 0)
    return big.resize((max(1, wc * cx), max(1, hc * cy)), Image.LANCZOS)


def colourise(mask, colour, alpha=1.0):
    """RGBA of one colour with mask (L) as alpha, scaled by alpha (0..1)."""
    img = Image.new("RGBA", mask.size, tuple(colour[:3]) + (0,))
    img.putalpha(mask.point(lambda v: round(v * alpha)) if alpha != 1.0 else mask)
    return img


def with_k_edge(mask, colour=P, k_offset=CAPTION_SHADOW, alpha=1.0):
    """The coloured mask with the black K copy at +k_offset,+k_offset under it (straight alpha, like the K fonts).
    The result is k_offset px wider and taller; the coloured ink stays at (0, 0)."""
    w, h = mask.size
    out = Image.new("RGBA", (w + k_offset, h + k_offset), (0, 0, 0, 0))
    out.alpha_composite(colourise(mask, K, alpha), (k_offset, k_offset))
    out.alpha_composite(colourise(mask, colour, alpha), (0, 0))
    return out


def pixel_text(text, cell=SMALL_CELL, colour=P, k_edge=True, k_offset=CAPTION_SHADOW, line_gap=2, crt=True,
               bloom=False, pad=0, alpha=1.0):
    """RGBA text in the totu glyphs (any glyph of build_fonts.GLYPHS: Latin, Cyrillic, punctuation, accent aliases;
    lowercase draws as capitals). cell: int or (cx, cy). k_edge: black K copy at +k_offset,+k_offset (image grows by
    k_offset). bloom: the fonts' soft bloom (alpha 0.28, radius 0.9 cell); needs room, so pad defaults to FONT_PAD.
    The ink's top-left is at (pad, pad)."""
    m = pixel_mask(text, cell, line_gap, crt)
    if bloom and not pad:
        pad = FONT_PAD
    if pad:
        mm = Image.new("L", (m.width + 2 * pad, m.height + 2 * pad), 0)
        mm.paste(m, (pad, pad))
        m = mm
    if bloom:
        r = min(_cells(cell)) * 0.9
        m = ImageChops.lighter(m, m.filter(ImageFilter.GaussianBlur(r)).point(lambda v: v * bf.BLOOM))
    return with_k_edge(m, colour, k_offset, alpha) if k_edge else colourise(m, colour, alpha)


# ---------------------------------------------------------------- pictograms
# '#' = lit cell. Drawn crisp (no rounding) so they stay sharp at 2 px cells. Sizes are odd where they must centre.
_RIGHT = ["##...", ".##..", "..##.", "...##", "..##.", ".##..", "##..."]          # bold chevron, 5x7
_RIGHT_S = ["##..", ".##.", "..##", ".##.", "##.."]                              # small bold chevron, 4x5


def _mirror(rows):
    return [r[::-1] for r in rows]


def _transpose(rows):
    return ["".join(r[i] for r in rows) for i in range(len(rows[0]))]


PICTO = {
    "close": ["#.....#", "##...##", ".##.##.", "..###..", ".##.##.", "##...##", "#.....#"],
    "chevron_right": _RIGHT,
    "chevron_left": _mirror(_RIGHT),
    "chevron_down": _transpose(_RIGHT),                         # 7x5 "v"
    "chevron_up": _transpose(_RIGHT)[::-1],
    "chevron_right_s": _RIGHT_S,                                # small: 16 px buttons (slider ends)
    "chevron_left_s": _mirror(_RIGHT_S),
    "chevron_down_s": _transpose(_RIGHT_S),
    "chevron_up_s": _transpose(_RIGHT_S)[::-1],
    "plus": ["...#...", "...#...", "...#...", "#######", "...#...", "...#...", "...#..."],
    "minus": [".......", ".......", ".......", "#######", ".......", ".......", "......."],
    "menu": ["#######", ".......", ".......", "#######", ".......", ".......", "#######"],
    "question": bf.PUNCTUATION["?"],
    "exclamation": bf.PUNCTUATION["!"],
    "star": ["...#...", "..###..", "#######", ".#####.", "..###..", ".##.##.", ".#...#."],
    "play": ["#....", "##...", "###..", "####.", "###..", "##...", "#...."],
    "pause": ["##.##", "##.##", "##.##", "##.##", "##.##", "##.##", "##.##"],
    "check": ["......#", ".....##", "#...##.", "##.##..", ".###...", "..#....", "......."],
    "dot": [".##.", "####", "####", ".##."],
    "square": ["#####", "#####", "#####", "#####", "#####"],
    "triangle_up": ["..#..", ".###.", "#####"],
    "triangle_down": ["#####", ".###.", "..#.."],
    "triangle_left": ["..#", ".##", "###", ".##", "..#"],
    "triangle_right": ["#..", "##.", "###", "##.", "#.."],
    "gear": ["..#.#..", ".#####.", "##...##", ".#...#.", "##...##", ".#####.", "..#.#.."],
    "lock": ["..###..", ".#...#.", ".#...#.", "#######", "###.###", "###.###", "#######"],
    "cloud": ["....###..", ".##.####.", "#########", "#########", ".#######."],
    "trash": ["..###..", "#######", ".#####.", ".#.#.#.", ".#.#.#.", ".#.#.#.", ".#####."],
    "refresh": ["..###.#", ".#...##", "#...###", "#......", "#.....#", ".#...#.", "..###.."],
}
for _name, _rows in PICTO.items():
    assert len({len(r) for r in _rows}) == 1 and set("".join(_rows)) <= {"#", "."}, _name


def picto_size(name, cell=2):
    """Ink size (w, h) in px of a pictogram (without the K edge)."""
    cx, cy = _cells(cell)
    rows = PICTO[name]
    return len(rows[0]) * cx, len(rows) * cy


def picto_mask(name, cell=2):
    cx, cy = _cells(cell)
    rows = PICTO[name]
    m = Image.new("L", (len(rows[0]) * cx, len(rows) * cy), 0)
    d = ImageDraw.Draw(m)
    for gy, row in enumerate(rows):
        for gx, v in enumerate(row):
            if v == "#":
                d.rectangle((gx * cx, gy * cy, (gx + 1) * cx - 1, (gy + 1) * cy - 1), fill=255)
    return m


def draw_picto(name, cell=2, colour=P, k_edge=True, k_offset=CAPTION_SHADOW, alpha=1.0):
    """RGBA pictogram (PICTO[name]) at cell px per grid cell (int or (cx, cy)), crisp, in colour with the black K
    copy at +k_offset (the image is then k_offset px larger; the coloured ink sits at (0, 0))."""
    m = picto_mask(name, cell)
    return with_k_edge(m, colour, k_offset, alpha) if k_edge else colourise(m, colour, alpha)


def button_frame(w, h, picto=None, bg=None, bg_alpha=1.0, colour=P, cell=2, k_edge=True, alpha=1.0, tail=0,
                 dx=0, dy=0, k_offset=CAPTION_SHADOW):
    """One w x h button frame: bg (None = transparent, or an RGB at bg_alpha; tail > 0 gives it the stepped tail)
    with the pictogram's ink centred (+dx, dy). The ink moves up / left just enough that its K drop stays inside
    the frame (it is never clipped); ValueError if ink + drop are larger than the frame."""
    if bg is None:
        img = transparent(w, h)
    elif tail:
        img = plate(w, h, bg, tail)
    else:
        img = flat(w, h, bg, bg_alpha)
    if picto:
        iw, ih = picto_size(picto, cell)
        k = k_offset if k_edge else 0
        if iw + k > w or ih + k > h:
            raise ValueError(f"{picto} at cell {cell} ({iw}+{k} x {ih}+{k}) does not fit {w}x{h}")
        x = min(max(0, (w - iw) // 2 + dx), w - iw - k)
        y = min(max(0, (h - ih) // 2 + dy), h - ih - k)
        img.alpha_composite(draw_picto(picto, cell, colour, k_edge, k_offset, alpha), (x, y))
    return img


# ---------------------------------------------------------------- .gfx helpers
EFFECT_ONLYDISABLE = "gfx/FX/buttonstate_onlydisable.lua"     # multi-frame buttons (the engine picks the frame)
EFFECT_NODOWN = "gfx/FX/buttonstate_nodowneffect.lua"          # boards, drag knobs
EFFECT_BUTTONSTATE = "gfx/FX/buttonstate.lua"                  # one-frame vanilla buttons (shader hover / press)


def sprite_block(name, texture, kind="spriteType", frames=None, effect=None, size=None, border=None, tiling=None,
                 comment=None, extra=()):
    """One sprite definition as the mod's .gfx files write it (tabs, LF). kind: spriteType, textSpriteType or
    corneredTileSpriteType; size / border: (x, y); tiling: True / False / None (omitted)."""
    assert name.startswith("GFX_"), name
    out = [f"\t{kind} = {{", f'\t\tname = "{name}"' + (f"\t# {comment}" if comment else ""),
           f'\t\ttextureFile = "{texture}"']
    if frames and frames > 1:
        out.append(f"\t\tnoOfFrames = {frames}")
    if size:
        out.append(f"\t\tsize = {{ x={size[0]} y={size[1]} }}")
    if border is not None:
        out.append(f"\t\tborderSize = {{ x={border[0]} y={border[1]} }}")
    if tiling is not None:
        out.append(f"\t\ttilingCenter = {'yes' if tiling else 'no'}")
    out.extend(f"\t\t{line}" for line in extra)
    if effect:
        out.append(f'\t\teffectFile = "{effect}"')
    out.append("\t}")
    return "\n".join(out)


def gfx_file(blocks, header_lines=()):
    """A whole .gfx file: '# ' header lines, then spriteTypes = { blocks }."""
    head = "".join(f"# {h}\n" if h else "#\n" for h in header_lines)
    return head + "\nspriteTypes = {\n" + "\n\n".join(blocks) + "\n}\n"


_NAME = re.compile(r'\bname\s*=\s*"?([^"\s}]+)"?', re.I)


def _strip_comments(text):
    return re.sub(r"#[^\n]*", "", text)


def declared_names(text):
    """Every name = "..." in a .gfx / .gui text (comments removed), in order."""
    return _NAME.findall(_strip_comments(text))


def _interface_files(base, pattern):
    base = Path(base)
    roots = [base / "interface"]
    if base == GAME:
        roots += sorted(base.glob("dlc/*/interface")) + sorted(base.glob("integrated_dlc/*/interface"))
        roots += [base / "pdx_online_assets" / "interface"]
    for r in roots:
        if r.exists():
            yield from sorted(r.rglob(pattern))


def existing_names(pattern="*.gfx", exclude=()):
    """name -> [files] for every name declared in the vanilla game's interface folders (incl. DLC) and the mod's
    interface folder, except the mod files in exclude (paths). Sprites live in *.gfx, gui types in *.gui."""
    excl = {Path(p).resolve() for p in exclude}
    found = {}
    for base in (GAME, ROOT):
        for f in _interface_files(base, pattern):
            if f.resolve() in excl:
                continue
            text = f.read_bytes().decode("utf-8", errors="replace")
            for n in declared_names(text):
                found.setdefault(n, []).append(f"{'van' if base == GAME else 'mod'}:{f.relative_to(base).as_posix()}")
    return found


def assert_declared(path, names, once=True):
    """Every name is declared in the .gfx / .gui file at path (exactly once if once)."""
    got = declared_names(Path(path).read_text(encoding="utf-8"))
    for n in names:
        c = got.count(n)
        assert c == 1 if once else c >= 1, f"{n}: declared {c} times in {Path(path).name}"


# ---------------------------------------------------------------- previews
def checker(w, h, a=(26, 28, 34), b=(38, 40, 48), sq=8):
    """Dark checkerboard so alpha shows."""
    yy, xx = np.mgrid[0:h, 0:w]
    m = ((xx // sq + yy // sq) % 2).astype(bool)
    arr = np.where(m[..., None], np.array(b, np.uint8), np.array(a, np.uint8))
    return Image.fromarray(np.dstack([arr, np.full((h, w), 255, np.uint8)]).astype(np.uint8), "RGBA")


def preview_bg(w, h, board=True, alpha=BOARD_ALPHA_IG):
    """The checker with the board (BOARD_RGB at alpha) over it, as a widget sits on screen."""
    img = checker(w, h)
    if board:
        img.alpha_composite(flat(w, h, BOARD_RGB, alpha))
    return img


def zoom(img, k):
    """Nearest-neighbour blow-up."""
    return img.resize((img.width * k, img.height * k), Image.NEAREST)


def cornered(tex, w, h, border=(0, 0), tiling=True):
    """Preview of a corneredTileSpriteType drawn at w x h: the borderSize margins kept, the rest tiled (tiling) or
    stretched, like the engine's 9-slice."""
    bx, by = border
    tw, th = tex.size
    out = transparent(w, h)
    xs = [(0, bx, 0, bx), (bx, tw - bx, bx, w - bx), (tw - bx, tw, w - bx, w)]
    ys = [(0, by, 0, by), (by, th - by, by, h - by), (th - by, th, h - by, h)]
    for sx0, sx1, dx0, dx1 in xs:
        for sy0, sy1, dy0, dy1 in ys:
            if sx1 <= sx0 or sy1 <= sy0 or dx1 <= dx0 or dy1 <= dy0:
                continue
            part = tex.crop((sx0, sy0, sx1, sy1))
            dw, dh = dx1 - dx0, dy1 - dy0
            if (dw, dh) != part.size:
                if tiling:
                    tile = Image.new("RGBA", (dw, dh))
                    for ty in range(0, dh, part.height):
                        for tx in range(0, dw, part.width):
                            tile.paste(part, (tx, ty))
                    part = tile
                else:
                    part = part.resize((dw, dh), Image.NEAREST)
            out.paste(part, (dx0, dy0))
    return out


def contact_sheet(items, path, width=1800, bg="checker", gap=16, label_cell=1, label_colour=D, margin=24):
    """Flow layout of labelled images, written as PNG. items: (label, img) pairs, bare images, or strings (a
    section heading that starts a new row). bg: 'checker' (alpha visible), 'board' (the in-game board over the
    checker) or an RGB tuple. Labels are pixel text at label_cell. Returns the sheet."""
    lab_h = 7 * label_cell + 6
    rows, row, x, row_h = [], [], margin, 0
    for it in items:
        if isinstance(it, str):
            if row:
                rows.append((row, row_h))
            rows.append(([("heading", it)], 7 * 2 + 14))
            row, x, row_h = [], margin, 0
            continue
        label, img = it if isinstance(it, tuple) else ("", it)
        lw = pixel_text_size(label, label_cell)[0] + 2 if label else 0
        cw = max(img.width, lw)
        if row and x + cw > width - margin:
            rows.append((row, row_h))
            row, x, row_h = [], margin, 0
        row.append((x, label, img))
        x += cw + gap
        row_h = max(row_h, img.height + (lab_h if label else 0))
    if row:
        rows.append((row, row_h))
    height = margin * 2 + sum(h + gap for _, h in rows)
    if bg == "checker":
        sheet = checker(width, height)
    elif bg == "board":
        sheet = preview_bg(width, height)
    else:
        sheet = Image.new("RGBA", (width, height), tuple(bg[:3]) + (255,))
    y = margin
    for r, h in rows:
        if r and r[0][0] == "heading":
            sheet.alpha_composite(pixel_text(r[0][1], 2, P), (margin, y + 4))
        else:
            for x0, label, img in r:
                yy = y
                if label:
                    sheet.alpha_composite(pixel_text(label, label_cell, label_colour, k_edge=False), (x0, yy))
                    yy += lab_h
                sheet.alpha_composite(img.convert("RGBA"), (x0, yy))
        y += h + gap
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.convert("RGB").save(path)
    _say("wrote", rel(path), f"{sheet.width}x{sheet.height}")
    return sheet


# ---------------------------------------------------------------- self-test
def _self_test():
    import tempfile
    # glyph rendering matches the fonts / logo
    for t in ("AW0", "TOTU 1990"):
        a = pixel_mask(t, 4, line_gap=0)
        b = bmg.pixel_text_mask([t], 4, line_gap=0)
        assert ImageChops.difference(a, b).getbbox() is None, f"pixel_mask differs from pixel_text_mask on {t}"
    # widths: real font advances == GLYPHS advances; plate math == the menu's
    for item in bmg.MENU_ITEMS + bmg.SUBMENU_ITEMS + bmg.LOBBY_ITEMS:
        assert big_plate_w(item) == bmg.caption_plate_w(item), item
    for item in bmg.SMALL_ITEMS:
        assert small_plate_w(item) == bmg.small_plate_w(item), item
    for s in ("Назад", "№ 1", "Ёлка, щи"):
        assert text_advance(s, 4, "totu_button") == text_advance(s, 4), s
    assert plate_sprite(("Назад", "Back")) == "GFX_totu_plate_160"
    assert plate_sprite(("Применить", "Apply")) == "GFX_totu_plate_256"
    assert plate_sprite(("Сбросить", "Reset"), "small") == "GFX_totu_plate_s_118"
    assert plate_sprite("№", "small") == "GFX_totu_plate_s_46", plate_sprite("№", "small")   # 9 columns -> n = 2
    assert plate_sprite(("Игра", "Game"), "small", "tab") == "GFX_totu_tab_s_70"
    assert plate_sprite(("Управление", "Controls"), "small", "toggle_r") == "GFX_totu_toggle_r_s_142"
    for n in (1, 7, 18):
        assert plate_n("Ж" * n) == n and plate_n("Ж" * n, "small") == n
    # pixel text: Cyrillic, non-square cells, K edge
    img = pixel_text("Щука, ёж №5", (2, 3), k_edge=True)
    assert img.size == (pixel_text_size("Щука, ёж №5", (2, 3))[0] + 2, 8 * 3 + 2), img.size
    for name in PICTO:
        draw_picto(name, 2)
    extra = "".join(ch for ch in "−½×ə​" if ord(ch) in CODEPOINTS)    # newer glyphs
    if extra:
        pixel_text(extra, 2)
    # DDS: uncompressed and DXT5 headers, fallback for odd sizes
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        save_dds(flat(20, 12, KEY_BLUE), tmp / "a.dds", quiet=True)
        save_dds(flat(256, 128, BOARD_RGB, 0.9), tmp / "b.dds", fmt="DXT5", quiet=True)
        save_dds(flat(30, 30, D), tmp / "c.dds", fmt="DXT5", quiet=True)
        ha, hb, hc = dds_header(tmp / "a.dds"), dds_header(tmp / "b.dds"), dds_header(tmp / "c.dds")
        assert ha["pfflags"] == 0x41 and ha["mips"] == 0 and hb["fourcc"] == "DXT5" and hb["mips"] <= 1
        assert hc["pfflags"] == 0x41
        assert not save_dds(flat(20, 12, KEY_BLUE), tmp / "a.dds", quiet=True)      # unchanged -> not rewritten
        back = Image.open(tmp / "a.dds").convert("RGBA").getpixel((3, 3))
        assert back == KEY_BLUE + (255,), back
        write_text(tmp / "x.gfx", "a\r\nb\n")
        assert (tmp / "x.gfx").read_bytes() == b"a\nb\n"
        write_loc(tmp / "t_l_russian.yml", "russian", {"TOTU_X": "Проверка"})
        raw = (tmp / "t_l_russian.yml").read_bytes()
        assert raw.startswith(b"\xef\xbb\xbfl_russian:\n") and b"\r" not in raw
        for args, needle in (((tmp / "y.gui", "Ж"), "non-ASCII characters"), ((tmp / "y.gfx", "a", True), "BOM")):
            accepted = False
            try:
                write_text(*args)
                accepted = True
            except ValueError as e:
                assert needle in str(e), e
            assert not accepted and not args[0].exists(), f"write_text accepted {args[0].name}"
        rejected = 0
        for args in ((tmp / "t.yml", "russian", {}), (tmp / "u_l_english.yml", "english", {"BAD KEY": "x"}),
                     (tmp / "u_l_english.yml", "english", {"K": "a\nb"})):
            try:
                write_loc(*args)
            except ValueError:
                rejected += 1
        assert rejected == 3, rejected
    assert dds_policy(512, 512) == "DXT5" and dds_policy(512, 512, lossless=True) is None
    assert dds_policy(100, 100) is None and dds_policy(126, 200) is None
    # bank names: unknown kinds and out-of-range n raise
    for bad in (("plate_x", 1), ("plate", 0), ("plate", BIG_N_MAX + 1)):
        try:
            bank_sprite(*bad)
            raise SystemExit(f"bank_sprite{bad} accepted")
        except ValueError:
            pass
    # plate_frames without a tail, progress bar pair
    pf = plate_frames(30, 10, (None, KEY_BLUE), tail=0)
    assert pf.size == (60, 10) and pf.getpixel((0, 0))[3] == 0 and pf.getpixel((59, 9)) == KEY_BLUE + (255,)
    full, empty = bar_pair(40, 6)
    assert full.getpixel((0, 0)) == KEY_BLUE + (255,) and empty.getpixel((0, 0)) == rgba(D, TRACK_ALPHA)
    assert "progress.lua" in progressbar_block("GFX_totu_x_bar", "a.dds", "b.dds", (40, 6))
    # pictogram frames never clip the K drop
    for name in PICTO:
        pw, ph = picto_size(name)
        full_ink = int(np.asarray(draw_picto(name))[..., 3].astype(np.int64).sum())
        for fw, fh in ((pw + 2, ph + 2), (12, 12), (16, 16), (20, 20)):
            if pw + 2 <= fw and ph + 2 <= fh:
                drawn = int(np.asarray(button_frame(fw, fh, name))[..., 3].astype(np.int64).sum())
                assert drawn == full_ink, f"{name} clipped in {fw}x{fh}"
    # localisation: trailing comments, $KEY$ references
    m = _LOC_LINE.match(' KEY_A:0 "Bulgaria" # BUL_neutrality')
    assert m and m.group(2) == "Bulgaria", m
    m = _LOC_LINE.match(' KEY_B: "say "hi" now"')
    assert m and m.group(2) == 'say "hi" now', m
    if (GAME / "localisation" / "english").exists():
        assert loc("CAREER_PROFILE_COUNTRY_BUL") == "Bulgaria"                  # line with a trailing comment
        assert loc("NOR_alt_dem_focus_on_training") == loc("NOR_focus_on_training")    # "$NOR_focus_on_training$"
        assert loc("NOR_alt_dem_focus_on_training", resolve=False) == "$NOR_focus_on_training$"
        try:
            labels_for("ACTIVE_MODIFIER_ALERT_ENTRY")                            # "$NAME$": engine-filled
            raise SystemExit("labels_for accepted an engine-filled variable")
        except ValueError:
            pass
    _say("totu_broadcast self-test OK:", len(PICTO), "pictograms,", len(GLYPHS), "glyph shapes")


if __name__ == "__main__":
    _self_test()
