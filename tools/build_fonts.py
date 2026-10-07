"""Builds the caption bitmap fonts of the frontend (design "broadcast": Soviet TV captions).

Usage:
    python tools/build_fonts.py

The face is the 5x7 character-generator font of the logo (PIXEL_FONT in tools/build_menu_gfx.py) plus the Cyrillic
and punctuation below. Every glyph gets the logo's CRT rounding and a soft white bloom baked into its alpha.
    totu_caption          4 px cells: 20x28 glyphs, advance 24, lineHeight 36, base 28  (menu and setup captions)
    totu_caption_small    2 px cells: 10x14 glyphs, advance 12, lineHeight 18, base 14  (date, changelog, labels)
    totu_caption_quote    totu_caption glyphs, lineHeight 44, black K edge baked in      (loading screen tip)
    totu_caption_small_k  totu_caption_small glyphs, black K edge baked in               (loading screen status, and the
                          bitmapfonts totu_label / totu_caption_name of the lobby: labels, engine-filled names)
    totu_button           totu_caption glyphs + K edge, lineHeight 40 = the plate, capitals in its middle (buttonText)
    totu_button_small     totu_caption_small glyphs + K edge, lineHeight 24 = the small plate (buttonText)
The loading pair is declared in interface/load_screen_font.gfx (the engine reads that file before every other
interface file), the others in interface/totu_fonts.gfx.

Output follows the vanilla fonts (e.g. gfx/fonts/hoi_33.fnt in the game folder):
    gfx/fonts/<font>.fnt  text BMFont file: unicode=1, LF line endings, one page, no kerning
    gfx/fonts/<font>.dds  uncompressed 32-bit, power of two, no mipmaps; RGB white, glyph in alpha
                          (the engine tints it with the font colour or a colour code)
The engine loads <fontfile>.dds next to the .fnt; the page file name inside the .fnt is not used.
Lowercase letters point at the uppercase rects, so everything renders in capitals. Accented Latin letters
(U+00C0..U+017F, for engine country names in other game languages) point at their base capital.

The two _k fonts carry the menu's drop edge: a black copy of every glyph (+ bloom) at +2,+2 under the white glyph,
flattened into one straight-alpha RGBA tile. The engine multiplies the atlas RGB by the text colour (vanilla
hoi_24header bakes its shadow the same way), so the edge stays black under any colour code. Kept uncompressed: DXT
would smear the 2 px edge.

Afterwards the script checks that every menu string, loading tip, vanilla status / label string the caption fonts
show and every country name (English, Russian and the Latin-script game languages) has a glyph, checks the hand-set
loading tips (check_loading_tips) and renders tools/preview/font_test.png from the written .fnt and .dds. It also
writes English text for the game languages the mod has no translation for (write_fallback_loc: menu captions and
scenario texts, the loading tips, the names of the countries the game does not know): the fonts have no other
script, and a missing key would show as its name. The vanilla strings come from the game folder (env HOI4_DIR,
default D:/steam/.../Hearts of Iron IV). Requires Pillow and numpy (pip install pillow numpy).
"""
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from build_menu_gfx import (GAME, LOAD_LINE_MAX, PIXEL_FONT, PLATE_H, QUOTE_BOX_W, SMALL_PLATE_H, pixel_text_mask,
                            save_dds)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "gfx" / "fonts"
PREVIEW = ROOT / "tools" / "preview" / "font_test.png"

# name: (px per font cell, lineHeight, base, shadow). Capitals stand on the baseline, so glyph tops sit at
# base - 7 cells. shadow > 0: the black K edge is baked into the atlas at +shadow,+shadow (RGBA tiles).
FONTS = {
    "totu_caption": (4, 36, 28, 0),
    "totu_caption_small": (2, 18, 14, 0),
    "totu_caption_quote": (4, 44, 28, 2),
    "totu_caption_small_k": (2, 18, 14, 2),
    # Button text drawn by the engine (buttonText), K edge baked in: the line box is as tall as the plate and the
    # capitals sit in its middle, so the label is centred whether the engine centres the line box or the ink.
    "totu_button": (4, PLATE_H, PLATE_H - (PLATE_H - 28) // 2, 2),                     # 40 px plates: capitals 6..34
    "totu_button_small": (2, SMALL_PLATE_H, SMALL_PLATE_H - (SMALL_PLATE_H - 14) // 2, 2),   # 24 px: capitals 5..19
}
PAD = 8                     # transparent margin around each glyph for the bloom; negative x/yoffset compensate
SPACING = 1                 # px between atlas rects, as in vanilla fonts
BLOOM = 0.28                # bloom alpha; its radius is 0.9 cell, as in the mockup captions

# 5x7 Cyrillic capitals ('#' = lit cell), from the design mockup; this and PUNCTUATION are the only copies (the menu
# preview of build_menu_gfx.py draws from the built fonts). Letters drawn like Latin ones reuse PIXEL_FONT and
# share its atlas rects. Ц and Щ keep full-height stems and hang their tail below the baseline (an 8th row, as on
# 5x8 LCD character ROMs): squeezed into 7 rows, Щ read as Ш at 2 px cells.
CYRILLIC = {
    "А": PIXEL_FONT["A"], "В": PIXEL_FONT["B"], "Е": PIXEL_FONT["E"], "К": PIXEL_FONT["K"],
    "М": PIXEL_FONT["M"], "Н": PIXEL_FONT["H"], "О": PIXEL_FONT["O"], "Р": PIXEL_FONT["P"],
    "С": PIXEL_FONT["C"], "Т": PIXEL_FONT["T"], "Х": PIXEL_FONT["X"],
    "Б": ["#####", "#....", "#....", "####.", "#...#", "#...#", "####."],
    "Г": ["#####", "#....", "#....", "#....", "#....", "#....", "#...."],
    "Д": ["..##.", ".#.#.", ".#.#.", ".#.#.", ".#.#.", "#####", "#...#"],
    "Ё": [".#.#.", ".....", "#####", "#....", "####.", "#....", "#####"],
    "Ж": ["#.#.#", "#.#.#", "#.#.#", ".###.", "#.#.#", "#.#.#", "#.#.#"],
    "З": [".###.", "#...#", "....#", "..##.", "....#", "#...#", ".###."],
    "И": ["#...#", "#...#", "#..##", "#.#.#", "##..#", "#...#", "#...#"],
    "Й": [".#.#.", "..#..", "#...#", "#..##", "#.#.#", "##..#", "#...#"],
    "Л": ["..###", ".#..#", ".#..#", ".#..#", ".#..#", ".#..#", "#...#"],
    "П": ["#####", "#...#", "#...#", "#...#", "#...#", "#...#", "#...#"],
    "У": ["#...#", "#...#", "#...#", ".####", "....#", "#...#", ".###."],
    "Ф": ["..#..", ".###.", "#.#.#", "#.#.#", "#.#.#", ".###.", "..#.."],
    "Ц": ["#..#.", "#..#.", "#..#.", "#..#.", "#..#.", "#..#.", "#####", "....#"],
    "Ч": ["#...#", "#...#", "#...#", ".####", "....#", "....#", "....#"],
    "Ш": ["#.#.#", "#.#.#", "#.#.#", "#.#.#", "#.#.#", "#.#.#", "#####"],
    "Щ": ["#.#.#", "#.#.#", "#.#.#", "#.#.#", "#.#.#", "#.#.#", "#####", "....#"],
    "Ъ": ["##...", ".#...", ".#...", ".###.", ".#..#", ".#..#", ".###."],
    "Ы": ["#...#", "#...#", "#...#", "##..#", "#.#.#", "#.#.#", "##..#"],
    "Ь": ["#....", "#....", "#....", "####.", "#...#", "#...#", "####."],
    "Э": [".###.", "#...#", "....#", ".####", "....#", "#...#", ".###."],
    "Ю": ["#..#.", "#.#.#", "#.#.#", "###.#", "#.#.#", "#.#.#", "#..#."],
    "Я": [".####", "#...#", "#...#", ".####", "..#.#", ".#..#", "#...#"],
}

# Punctuation missing from PIXEL_FONT. An 8th row is a descender, below the baseline in the line gap (the comma gets
# one so it does not read as a slash at 2 px cells). A glyph wider than 5 cells advances by its width + 1 (№).
PUNCTUATION = {
    "!": ["..#..", "..#..", "..#..", "..#..", "..#..", ".....", "..#.."],
    '"': [".#.#.", ".#.#.", ".....", ".....", ".....", ".....", "....."],
    "#": [".#.#.", ".#.#.", "#####", ".#.#.", "#####", ".#.#.", ".#.#."],
    "$": ["..#..", ".####", "#.#..", ".###.", "..#.#", "####.", "..#.."],
    "%": ["##...", "##..#", "...#.", "..#..", ".#...", "#..##", "...##"],
    "&": [".##..", "#..#.", "#.#..", ".#...", "#.#.#", "#..#.", ".##.#"],
    "'": ["..#..", "..#..", ".....", ".....", ".....", ".....", "....."],
    "(": ["...#.", "..#..", ".#...", ".#...", ".#...", "..#..", "...#."],
    ")": [".#...", "..#..", "...#.", "...#.", "...#.", "..#..", ".#..."],
    "*": [".....", "..#..", "#.#.#", ".###.", "#.#.#", "..#..", "....."],
    "+": [".....", "..#..", "..#..", "#####", "..#..", "..#..", "....."],
    ",": [".....", ".....", ".....", ".....", ".....", "..#..", "..#..", ".#..."],
    "/": [".....", "....#", "...#.", "..#..", ".#...", "#....", "....."],
    ":": [".....", "..#..", "..#..", ".....", "..#..", "..#..", "....."],
    ";": [".....", "..#..", "..#..", ".....", "..#..", "..#..", ".#..."],
    "<": ["...#.", "..#..", ".#...", "#....", ".#...", "..#..", "...#."],
    "=": [".....", ".....", "#####", ".....", "#####", ".....", "....."],
    ">": [".#...", "..#..", "...#.", "....#", "...#.", "..#..", ".#..."],
    "?": [".###.", "#...#", "....#", "...#.", "..#..", ".....", "..#.."],
    "@": [".###.", "#...#", "....#", ".##.#", "#.#.#", "#.#.#", ".###."],
    "[": [".###.", ".#...", ".#...", ".#...", ".#...", ".#...", ".###."],
    "\\": [".....", "#....", ".#...", "..#..", "...#.", "....#", "....."],
    "]": [".###.", "...#.", "...#.", "...#.", "...#.", "...#.", ".###."],
    "^": ["..#..", ".#.#.", "#...#", ".....", ".....", ".....", "....."],
    "_": [".....", ".....", ".....", ".....", ".....", ".....", ".....", "#####"],
    "`": [".#...", "..#..", ".....", ".....", ".....", ".....", "....."],
    "{": ["...#.", "..#..", "..#..", ".#...", "..#..", "..#..", "...#."],
    "|": ["..#..", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    "}": [".#...", "..#..", "..#..", "...#.", "..#..", "..#..", ".#..."],
    "~": [".....", ".....", ".#...", "#.#.#", "...#.", ".....", "....."],
    "«": [".....", "..#.#", ".#.#.", "#.#..", ".#.#.", "..#.#", "....."],
    "»": [".....", "#.#..", ".#.#.", "..#.#", ".#.#.", "#.#..", "....."],
    "·": [".....", ".....", ".....", "..#..", ".....", ".....", "....."],
    "–": [".....", ".....", ".....", "#####", ".....", ".....", "....."],
    "—": [".....", ".....", ".....", "#####", ".....", ".....", "....."],
    "‘": ["...#.", "..#..", "..#..", ".....", ".....", ".....", "....."],
    "’": ["..#..", "..#..", ".#...", ".....", ".....", ".....", "....."],
    "“": [".#..#", "#..#.", "#..#.", ".....", ".....", ".....", "....."],
    "”": [".#..#", ".#..#", "#..#.", ".....", ".....", ".....", "....."],
    "„": [".....", ".....", ".....", ".....", ".....", ".#..#", ".#..#", "#..#."],
    "…": [".....", ".....", ".....", ".....", ".....", ".....", "#.#.#"],
    "№": ["#...#.###", "#...#.#.#", "##..#.###", "#.#.#....", "#..##.###", "#...#....", "#...#...."],
}
# Latin letters with no single base capital and the Spanish / currency signs of engine-filled names and dates in the
# other game languages (German ß in 450+ vanilla names, Danish æ, French œ). ß is drawn as the capital ẞ, like
# every other lowercase letter.
LATIN_EXTRA = {
    "ẞ": [".###.", "#...#", "#..#.", "#.#..", "#..#.", "#...#", "#.##."],
    "Æ": [".####", "#.#..", "#.#..", "#####", "#.#..", "#.#..", "#.###"],
    "Œ": [".####", "#.#..", "#.#..", "#.###", "#.#..", "#.#..", ".####"],
    "¡": [".....", "..#..", ".....", "..#..", "..#..", "..#..", "..#.."],
    "¿": [".....", "..#..", ".....", "..#..", ".#...", "#...#", ".###."],
    "°": [".##..", "#..#.", "#..#.", ".##..", ".....", ".....", "....."],
    "£": ["..##.", ".#..#", ".#...", "###..", ".#...", ".#...", "#####"],
}
GLYPHS = {**PIXEL_FONT, **CYRILLIC, **PUNCTUATION, **LATIN_EXTRA}

# Accented Latin letters (Latin-1 Supplement, Latin Extended-A and -B, Latin Extended Additional; without × and ÷)
# drawn as their base capital, so engine country names in the other game languages (card names and nation_title on
# the country selection screen, the lobby's selected country) render instead of leaving gaps. Base = the first letter
# of the canonical decomposition, plus the letters that have none; ß, æ and œ get their own glyphs (LATIN_EXTRA).
LATIN_EXTRA_BASE = {"Ł": "L", "ł": "L", "Ø": "O", "ø": "O", "Đ": "D", "đ": "D", "Ð": "D", "ð": "D", "Ħ": "H",
                    "ħ": "H", "ı": "I", "Ŧ": "T", "ŧ": "T", "ß": "ẞ", "æ": "Æ", "œ": "Œ"}


def latin_base(ch):
    if ch in LATIN_EXTRA_BASE:
        return LATIN_EXTRA_BASE[ch]
    b = unicodedata.normalize("NFD", ch)[0]
    return b.upper() if b != ch and b.isascii() and b.isalpha() else None


LATIN_ALIASES = {cp: latin_base(chr(cp)) for cp in (*range(0xC0, 0x250), *range(0x1E00, 0x1F00))
                 if cp not in (0xD7, 0xF7) and latin_base(chr(cp))}

# Code points in every font: printable ASCII, Ё, А-я, ё (the ids of the vanilla Cyrillic fonts), the typography
# of the Russian texts and the accented Latin aliases. Lowercase maps onto the uppercase glyph, a no-break space onto
# the space. The aliases and the LATIN_EXTRA letters come last, so the atlases of the menu fonts keep their earlier
# glyphs where they were.
CODEPOINTS = [*range(0x20, 0x7F), 0xA0, 0xAB, 0xB7, 0xBB, 0x401, *range(0x410, 0x450), 0x451,
              0x2013, 0x2014, 0x2018, 0x2019, 0x201C, 0x201D, 0x201E, 0x2026, 0x2116, *sorted(LATIN_ALIASES),
              0xC6, 0xE6, 0x152, 0x153, 0x1E9E, 0xA1, 0xBF, 0xB0, 0xA3]

# Strings drawn with these fonts besides the loc keys: the start date, the changelog line and the engine's version
# label (set by the game, not localisable). The vanilla strings the engine puts into caption-font boxes (loading
# statuses, the lobby's date line) are read from the game folder (vanilla_strings).
FIXED_STRINGS = ["1 января 1990", "Версия 0.1: карта 1990 года, новое меню", "Operation Postern v1.19.3.0.c01a (5632)",
                 "12:00, 1 января, 1990", "12:00, 1 January, 1990"]
# Vanilla keys whose values the engine draws in the caption fonts in English and Russian: the loading screen's status
# line (loadscreen_header), the "updating history" line and the vanilla labels of the lobby frame, the settings boards
# and the load / ironman-save windows (totu_caption_name).
STATUS_KEY = re.compile(r'^\s*(LOADING_[A-Z_]+|FE_LOADING_HISTORY|HOST_LOADING_SAVEGAME|PREPARING_AFTER_HOTJOIN|'
                        r'HOST_PREPARING_GAME|MENU_BAR_(?:LOCALGAMES|CLOUDGAMES|IRONMAN_SAVE|SAVE_GAME_FILENAME|'
                        r'DISK_QUOTA)|FE_NO_COUNTRY_SELECTED|FE_DIFFICULTY(?:_VERY_EASY|_EASY|_NORMAL|_HARD|_VERY_HARD)?|'
                        r'FE_IRONMAN|FE_HISTORICAL|FE_HOTJOIN_LABEL|FE_COOP_LABEL):\d*\s*"(.*)"\s*$')
# Country name keys (<TAG>, <TAG>_<ideology>, ..._DEF; not _ADJ): drawn by the engine in totu_caption_name on the
# country selection screen and in the lobby.
NAME_KEY = re.compile(r'^\s*([A-Z][A-Z0-9]{2}(?:_[a-z][a-z_]*)?(?:_DEF)?):\d*\s*"(.*)"\s*$')
# Game languages whose engine-filled names the pixel font draws (accent aliases); the CJK languages get vanilla fonts
# through the bitmapfont_override blocks of totu_caption_name (interface/totu_fonts.gfx).
LATIN_LANGUAGES = ["french", "german", "spanish", "braz_por", "polish"]
# Keys drawn in the caption fonts (glyph-checked, English fallback for the other languages). TOTU_1990_NAME is the
# bookmark name the lobby shows.
MENU_KEY = re.compile(r'^\s*(TOTU_(?:FE|MENU)_\w+|TOTU_1990_NAME):\d*\s*"(.*)"\s*$')
# Scenario and country texts drawn in vanilla fonts: English fallback only, no glyph check.
TEXT_KEY = re.compile(r'^\s*(TOTU_(?:[A-Z]{3}_)?1990_DESC):\d*\s*"(.*)"\s*$')
TIP_KEY = re.compile(r'^\s*LOADING_TIP_(\d+):\d*\s*"(.*)"\s*$')
QUOTE_MARKS = "«\"“„"           # a loading tip is a subtitle: it never opens with a quotation mark


def glyph_key(cp):
    if cp in LATIN_ALIASES:
        return LATIN_ALIASES[cp]
    ch = " " if cp == 0xA0 else chr(cp)
    return ch.upper() if ch.upper() in GLYPHS else ch


def glyph_mask(rows, cell, ss=4):
    """Lit cells of one glyph with the logo's CRT rounding: build_menu_gfx.pixel_text_mask for glyphs of any size
    (descenders, the wide №). main() checks that both give the same pixels on the plain 5x7 glyphs."""
    c = cell * ss
    w, h = len(rows[0]), len(rows)
    big = Image.new("L", (w * c, h * c), 0)
    d = ImageDraw.Draw(big)
    for gy, row in enumerate(rows):
        for gx, v in enumerate(row):
            if v == "#":
                d.rectangle((gx * c, gy * c, (gx + 1) * c - 1, (gy + 1) * c - 1), fill=255)
    big = big.filter(ImageFilter.GaussianBlur(c * 0.12)).point(lambda v: 255 if v > 110 else 0)
    return big.resize((w * cell, h * cell), Image.LANCZOS)


def glyph_tile(rows, cell):
    """Atlas tile: the glyph PAD px in from each edge, plus the baked bloom (caption() of the mockup). The glyph is
    rasterised between two blank columns, as inside a line of text, so its side edges come out as in the mockup."""
    w, h = len(rows[0]) * cell, len(rows) * cell
    m0 = glyph_mask(["." + r + "." for r in rows], cell).crop((cell, 0, cell + w, h))
    m = Image.new("L", (m0.width + 2 * PAD, m0.height + 2 * PAD), 0)
    m.paste(m0, (PAD, PAD))
    bloom = m.filter(ImageFilter.GaussianBlur(cell * 0.9)).point(lambda v: v * BLOOM)
    return ImageChops.lighter(m, bloom)


def glyph_tile_k(rows, cell, shadow):
    """RGBA atlas tile with the menu's drop edge baked in: the black K copy (glyph + bloom) at +shadow,+shadow under
    the white glyph + bloom, flattened into straight alpha (alpha = aw + ak (1 - aw), RGB = 255 aw / alpha). Drawn
    over a background this equals the menu's black copy plus the white caption on top, pixel for pixel. The tile is
    PAD px in at the left and top, PAD + shadow at the right and bottom."""
    m = np.asarray(glyph_tile(rows, cell), np.float32) / 255
    h, w = m.shape
    aw = np.zeros((h + shadow, w + shadow), np.float32)
    ak = np.zeros_like(aw)
    aw[:h, :w] = m
    ak[shadow:, shadow:] = m
    alpha = aw + ak * (1 - aw)
    rgb = np.where(alpha > 0, aw / np.maximum(alpha, 1e-6), 1.0)
    px = np.dstack([rgb, rgb, rgb, alpha]) * 255
    return Image.fromarray(np.round(px).astype(np.uint8), "RGBA")


def pack(sizes):
    """Shelf-packs tiles in order. Returns their positions and the smallest (then squarest) power-of-two atlas."""
    best = None
    for aw in (128, 256, 512, 1024, 2048):
        if max(w for w, _ in sizes) > aw:
            continue
        x = y = row_h = 0
        pos = []
        for w, h in sizes:
            if x + w > aw:
                x, y, row_h = 0, y + row_h + SPACING, 0
            pos.append((x, y))
            x += w + SPACING
            row_h = max(row_h, h)
        ah = 1 << (y + row_h - 1).bit_length()
        if best is None or (aw * ah, max(aw, ah)) < (best[1] * best[2], max(best[1], best[2])):
            best = (pos, aw, ah)
    return best


def fnt_text(name, cell, line_height, base, size, chars, shadow=0):
    """BMFont text file, laid out like the vanilla ones (BMFont's own column padding). padding = up,right,down,left."""
    lines = [
        f'info face="{name}" size={7 * cell} bold=0 italic=0 charset="" unicode=1 stretchH=100 smooth=0 aa=1 '
        f"padding={PAD},{PAD + shadow},{PAD + shadow},{PAD} spacing={SPACING},{SPACING} outline=0",
        f"common lineHeight={line_height} base={base} scaleW={size[0]} scaleH={size[1]} pages=1 packed=0 "
        "alphaChnl=1 redChnl=0 greenChnl=0 blueChnl=0",
        f'page id=0 file="{name}.dds"',
        f"chars count={len(chars)}",
    ]
    for cp, (x, y, w, h, xo, yo, adv) in sorted(chars.items()):
        lines.append(f"char id={cp:<4d} x={x:<5d} y={y:<5d} width={w:<5d} height={h:<5d} xoffset={xo:<5d} "
                     f"yoffset={yo:<5d} xadvance={adv:<5d} page={0:<2d} chnl=15")
    return "\n".join(lines) + "\n"


def build_font(name, cell, line_height, base, shadow=0):
    """Writes gfx/fonts/<name>.dds and .fnt. Identical bitmaps (a and A, Latin A and Cyrillic А) share one rect.
    shadow = 0: white RGB, glyph + bloom in alpha. shadow > 0: RGBA tiles from glyph_tile_k (baked K edge)."""
    keys = {cp: tuple(GLYPHS[glyph_key(cp)]) for cp in CODEPOINTS}
    shapes = list(dict.fromkeys(keys.values()))
    if shadow:
        tiles = [glyph_tile_k(rows, cell, shadow) for rows in shapes]
        pos, aw, ah = pack([t.size for t in tiles])
        atlas = Image.new("RGBA", (aw, ah), (255, 255, 255, 0))
        for tile, p in zip(tiles, pos):
            atlas.paste(tile, p)
    else:
        tiles = [glyph_tile(rows, cell) for rows in shapes]
        pos, aw, ah = pack([t.size for t in tiles])
        alpha = Image.new("L", (aw, ah), 0)
        for tile, p in zip(tiles, pos):
            alpha.paste(tile, p)
        atlas = Image.new("RGBA", (aw, ah), (255, 255, 255, 0))
        atlas.putalpha(alpha)

    top = base - 7 * cell
    rect = {rows: (*p, *t.size) for rows, p, t in zip(shapes, pos, tiles)}
    chars = {cp: (*rect[rows], -PAD, top - PAD, (len(rows[0]) + 1) * cell) for cp, rows in keys.items()}
    save_dds(atlas, OUT / f"{name}.dds")
    path = OUT / f"{name}.fnt"
    path.write_text(fnt_text(name, cell, line_height, base, (aw, ah), chars, shadow), encoding="ascii", newline="\n")
    print("wrote", path.relative_to(ROOT), f"{len(chars)} chars, {len(shapes)} glyphs")


# ---------------------------------------------------------------- checks, read back from the written files
FIELD = re.compile(r'(\w+)=("[^"]*"|\S+)')


def read_fnt(path):
    """The parts of a text .fnt the engine uses: the common line and the chars (id -> fields)."""
    common, chars = {}, {}
    for line in path.read_text(encoding="ascii").splitlines():
        tag, _, rest = line.partition(" ")
        fields = dict(FIELD.findall(rest))
        if tag == "common":
            common = {k: int(v) for k, v in fields.items()}
        elif tag == "char":
            chars[int(fields["id"])] = {k: int(v) for k, v in fields.items()}
    return common, chars


def load_font(name):
    common, chars = read_fnt(OUT / f"{name}.fnt")
    return common, chars, Image.open(OUT / f"{name}.dds").convert("RGBA")


def strip_codes(text):
    return re.sub(r"§.|\\n", "", text)


def bookmark_countries():
    """(TAG, ideology) of every country in common/bookmarks/totu_1990.txt (read only), in file order, no repeats."""
    text = (ROOT / "common" / "bookmarks" / "totu_1990.txt").read_text(encoding="utf-8")
    found = re.findall(r'"([A-Z0-9]{3})"\s*=\s*\{[^{}]*?\bideology\s*=\s*(\w+)', text)
    return list(dict.fromkeys(found))


def yml_values(path, pattern):
    """(key, value) of the lines of a localisation file that match pattern (groups: key, value)."""
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        m = pattern.match(line)
        if m:
            yield m.group(1), m.group(2)


def country_names():
    """(where, name) of every country name the engine can put into totu_caption_name: all <TAG> / <TAG>_<ideology> /
    _DEF names of the mod's English and Russian name files (any country can be picked on the map), the vanilla names
    of the Latin-script game languages and the names this script writes for them (write_fallback_loc)."""
    for lang in ("english", "russian"):
        f = ROOT / "localisation" / lang / "replace" / f"totu_countries_l_{lang}.yml"
        for key, value in yml_values(f, NAME_KEY):
            yield f"{lang} {key}", strip_codes(value)
    for lang in LATIN_LANGUAGES:
        files = sorted((GAME / "localisation" / lang).rglob("countries*_l_*.yml")) if GAME.exists() else []
        files += sorted((ROOT / "localisation" / lang).glob("totu_countries_new_l_*.yml"))
        for f in files:
            for key, value in yml_values(f, NAME_KEY):
                yield f"{lang} {key}", strip_codes(value)


def vanilla_strings():
    """(where, text) of the vanilla English and Russian strings the engine draws in the caption fonts (STATUS_KEY),
    with $...$ fields left out. Empty if the game folder is missing (env HOI4_DIR)."""
    for lang in ("english", "russian"):
        for f in sorted((GAME / "localisation" / lang).glob("*.yml")) if GAME.exists() else []:
            for key, value in yml_values(f, STATUS_KEY):
                yield f"{lang} {key}", re.sub(r"\$[^$]*\$", "", strip_codes(value))


def menu_strings(names=True):
    """(where, text) for every string the caption fonts draw, without § codes and \\n: TOTU_FE_* / TOTU_MENU_* and
    TOTU_1990_NAME values, the loading tips, FIXED_STRINGS, the vanilla statuses and (names) every country name."""
    for f in sorted((ROOT / "localisation").glob("*/totu_menu_l_*.yml")):
        for key, value in yml_values(f, MENU_KEY):
            yield f"{f.parent.name} {key}", strip_codes(value)
    for f in sorted((ROOT / "localisation").glob("*/loading_tips_l_*.yml")):
        for key, value in yml_values(f, TIP_KEY):
            yield f"{f.parent.name} LOADING_TIP_{key}", strip_codes(value)
    for s in FIXED_STRINGS:
        yield "fixed", s
    yield from vanilla_strings()
    if names:
        yield from country_names()


def missing_glyphs(name):
    _, chars = read_fnt(OUT / f"{name}.fnt")
    out = {}
    for where, text in menu_strings():
        miss = sorted({ch for ch in text if ord(ch) not in chars})
        if miss:
            out[where] = miss
    return out


def check_loading_tips():
    """The hand-set loading tips (localisation/<english|russian>/loading_tips_l_*.yml, interface/load_screen.gui):
    keys LOADING_TIP_0.. consecutive and as many in English as in Russian; each value is 1-3 quote lines and a last
    line §D<name strap>§!, split at a literal \\n; no line longer than LOAD_LINE_MAX characters or 40 advances of
    totu_caption_quote; a greedy wrap at the tip box width (QUOTE_BOX_W) gives back exactly the hand-set lines; no
    quotation mark opens the quote. Returns the list of problems."""
    quote = load_font("totu_caption_quote")
    advances = quote[1]
    max_px = LOAD_LINE_MAX * advances[ord(" ")]["xadvance"]
    problems, counts = [], {}
    for lang in ("russian", "english"):
        f = ROOT / "localisation" / lang / f"loading_tips_l_{lang}.yml"
        tips = [(int(m.group(1)), m.group(2)) for m in map(TIP_KEY.match, f.read_text(encoding="utf-8-sig")
                                                            .splitlines()) if m]
        counts[lang] = len(tips)
        if [i for i, _ in tips] != list(range(len(tips))):
            problems.append(f"{lang}: keys are not LOADING_TIP_0..{len(tips) - 1} in order")
        for i, value in tips:
            where = f"{lang} LOADING_TIP_{i}"
            parts = value.split("\\n")
            quote_lines, strap = parts[:-1], parts[-1]
            if not (strap.startswith("§D") and strap.endswith("§!") and "§" not in strap[2:-2]):
                problems.append(f"{where}: the last line is not one §D...§! name strap")
            if not 1 <= len(quote_lines) <= 3:
                problems.append(f"{where}: {len(quote_lines)} quote lines (1-3)")
            if quote_lines and quote_lines[0][:1] in QUOTE_MARKS:
                problems.append(f"{where}: opens with a quotation mark")
            lines = [strip_codes(p) for p in parts]
            for line in lines:
                width = sum(advances[ord(ch)]["xadvance"] for ch in line if ord(ch) in advances)
                if len(line) > LOAD_LINE_MAX or width > max_px:
                    problems.append(f"{where}: line of {len(line)} characters / {width} px: {line!r}")
            if engine_wrap(advances, lines, QUOTE_BOX_W) != lines:
                problems.append(f"{where}: the engine would wrap it differently at {QUOTE_BOX_W} px")
    if len(set(counts.values())) > 1:
        problems.append(f"different tip counts: {counts}")
    return problems


def engine_wrap(advances, paragraphs, max_w):
    """Greedy word wrap at spaces, as the engine wraps a text box: a word goes to the next line when the line plus a
    space and the word would be wider than max_w. paragraphs: lines already broken by \\n."""
    out = []
    for para in paragraphs:
        line = ""
        for word in para.split(" "):
            trial = word if not line else f"{line} {word}"
            if line and sum(advances[ord(ch)]["xadvance"] for ch in trial if ord(ch) in advances) > max_w:
                out.append(line)
                line = word
            else:
                line = trial
        out.append(line)
    return out


# ---------------------------------------------------------------- texts for the other game languages
# The mod is written in English and Russian. The menu buttons used vanilla keys translated into every game language;
# their TOTU_FE_* / TOTU_MENU_* replacements, the bookmark name and the scenario / country texts get the English text
# in the other languages (TEXT_KEY: drawn in vanilla fonts, so not glyph-checked).
FALLBACK_LANGUAGES = ["braz_por", "french", "german", "japanese", "korean", "polish", "simp_chinese", "spanish"]
# Country name keys the game looks up: <TAG>, <TAG>_<ideology group> (the four groups of the mod), each with _DEF / _ADJ
USED_NAME = re.compile(r"^[A-Z][A-Z0-9]{2}(?:_(?:democratic|communism|fascism|neutrality))?(?:_DEF|_ADJ)?$")


def vanilla_keys(lang):
    """Every key of the game's localisation in one language (empty without the game folder)."""
    keys = set()
    for f in (GAME / "localisation" / lang).rglob("*.yml") if GAME.exists() else []:
        for line in f.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            m = re.match(r"^\s*([\w.\-]+):\d*\s", line)
            if m:
                keys.add(m.group(1))
    return keys


def write_fallback_loc():
    """For every game language without a translation of the mod (FALLBACK_LANGUAGES), from the English files:
      totu_menu_captions_l_<lang>.yml   the menu captions and the scenario / country texts
      loading_tips_l_<lang>.yml         the 25 hand-set quotes; same file name as the vanilla file, so it replaces the
                                        163 gameplay tips of 1936 (the loading screen draws them in the pixel font)
      totu_countries_new_l_<lang>.yml   the country names the game has no key for in that language (the tags the
                                        mod adds: BRB, COM, KIR, ...), so they do not show as raw keys. Only the keys
                                        the game looks up (USED_NAME); the English file also has unused sub-ideology
                                        names
    All UTF-8 with BOM."""
    src = ROOT / "localisation" / "english" / "totu_menu_l_english.yml"
    lines = [line for line in src.read_text(encoding="utf-8-sig").splitlines()
             if MENU_KEY.match(line) or TEXT_KEY.match(line)]
    tips_src = ROOT / "localisation" / "english" / "loading_tips_l_english.yml"
    tips = [line for line in tips_src.read_text(encoding="utf-8-sig").splitlines() if TIP_KEY.match(line)]
    names_src = ROOT / "localisation" / "english" / "replace" / "totu_countries_l_english.yml"
    names = [(m.group(1), line) for line in names_src.read_text(encoding="utf-8-sig").splitlines()
             for m in [re.match(r"^\s*([\w.\-]+):\d*\s", line)] if m]

    def write(path, source, what, body):
        path.parent.mkdir(parents=True, exist_ok=True)
        head = [f"l_{path.parent.name}:",
                f" # Generated by tools/build_fonts.py from {source.relative_to(ROOT).as_posix()}: {what}.",
                " # Edit the English file."]
        path.write_text("\n".join(head + body) + "\n", encoding="utf-8-sig", newline="\n")

    new_names = 0
    for lang in FALLBACK_LANGUAGES:
        loc = ROOT / "localisation" / lang
        write(loc / f"totu_menu_captions_l_{lang}.yml", src,
              "the menu captions and the scenario texts in English (the caption fonts have Latin and Cyrillic only)",
              lines)
        write(loc / f"loading_tips_l_{lang}.yml", tips_src,
              "the loading screen quotes in English, replacing the vanilla gameplay tips", tips)
        known = vanilla_keys(lang)
        body = [line for key, line in names if key not in known and USED_NAME.match(key)] if known else []
        new_names = max(new_names, len(body))
        if body:
            write(loc / f"totu_countries_new_l_{lang}.yml", names_src,
                  "English names for the keys the game has none for in this language (countries the mod adds)", body)
    print(f"wrote {len(lines)} menu captions and scenario texts, {len(tips)} loading tips and up to {new_names} "
          f"country names for {len(FALLBACK_LANGUAGES)} languages: localisation/<lang>/")


def draw_text(img, font, text, x, y, colour=(255, 255, 255)):
    """Draws text as the engine does: each char's rect at pen + offset, tinted; pen += xadvance. y = line top."""
    _, chars, atlas = font
    for ch in text:
        c = chars[ord(ch)]
        tile = atlas.crop((c["x"], c["y"], c["x"] + c["width"], c["y"] + c["height"]))
        img.alpha_composite(ImageChops.multiply(tile, Image.new("RGBA", tile.size, colour + (255,))),
                            (x + c["xoffset"], y + c["yoffset"]))
        x += c["xadvance"]
    return x


# ---------------------------------------------------------------- preview
BG = (18, 22, 30)
BG_LIGHT = (112, 116, 128)
KEY_BLUE = (30, 62, 168)        # hover plate of the menu buttons
DIM = (172, 180, 196)           # textcolor D: the engine version line


def loc_values(lang, prefix):
    f = ROOT / "localisation" / lang / f"totu_menu_l_{lang}.yml"
    vals = [MENU_KEY.match(line) for line in f.read_text(encoding="utf-8-sig").splitlines()]
    return [m.group(2) for m in vals if m and m.group(1).startswith(prefix)]


def plate(img, x, y, text_w):
    """Hover plate as in the design: 22 px pad, text, 10 px pad, then 6 px at 60 % and 6 px at 30 %."""
    d = ImageDraw.Draw(img)
    solid = 22 + text_w + 10
    d.rectangle((x, y, x + solid - 1, y + 39), fill=KEY_BLUE + (255,))
    layer = Image.new("RGBA", (12, 40), KEY_BLUE + (0,))
    layer.paste(KEY_BLUE + (153,), (0, 0, 6, 40))
    layer.paste(KEY_BLUE + (77,), (6, 0, 12, 40))
    img.alpha_composite(layer, (x + solid, y))


def render_preview():
    big, small = load_font("totu_caption"), load_font("totu_caption_small")
    cell = FONTS["totu_caption"][0]
    # top of the label text box under the plate top, as in interface/frontendmainview.gui: capitals centred in the plate
    label_dy = (PLATE_H - 7 * cell) // 2 - (big[0]["base"] - 7 * cell)
    W, H = 2300, 4400                           # cropped to the content at the end
    img = Image.new("RGBA", (W, H), BG + (255,))
    d = ImageDraw.Draw(img)
    x0, y = 48, 32

    def label(text):
        nonlocal y
        draw_text(img, small, text, x0, y, DIM)
        y += 30

    # captions: Russian and English menus, first item hovered, second with the K drop edge at +2,+2
    label("TOTU_CAPTION  -  4 PX CELLS, ADVANCE 24, LINE 36, BASE 28  -  HOVER PLATE, K DROP EDGE ON ITEM 2")
    for col, lang in enumerate(("russian", "english")):
        yy = y
        for i, text in enumerate(loc_values(lang, "TOTU_FE_")):
            x = x0 + 22 + col * 760
            if i == 0:
                plate(img, x - 22, yy, len(text) * 24 - 4)
            ty = yy + label_dy
            if i == 1:
                draw_text(img, big, text, x + 2, ty + 2, (0, 0, 0))
            draw_text(img, big, text, x, ty)
            yy += 44
    y = yy + 24

    shapes = list(dict.fromkeys(glyph_key(cp) for cp in CODEPOINTS))
    for font, per_line, step in ((big, 60, 40), (small, 120, 22)):
        rows = ["".join(shapes[i:i + per_line]) for i in range(0, len(shapes), per_line)]
        rows.append("abc xyz абв эюя ё ъ » lowercase -> capitals, accents -> base: ÉÜÇ łøđ ąčő")
        for band in (BG, BG_LIGHT):
            d.rectangle((0, y - 10, W, y + step * len(rows) + 2), fill=band + (255,))
            for r in rows:
                draw_text(img, font, r, x0, y)
                y += step
            y += 14
        y += 16

    label("TOTU_CAPTION_SMALL  -  2 PX CELLS, ADVANCE 12, LINE 18, BASE 14")
    sample_top = y
    for text, colour in ((FIXED_STRINGS[0], (255, 255, 255)), (FIXED_STRINGS[1], (255, 255, 255)),
                         (FIXED_STRINGS[2], DIM)):
        draw_text(img, small, text, x0, y, colour)
        y += 24
    sample = img.crop((x0 - 8, sample_top - 8, x0 + 520, y))
    for lang in ("russian", "english"):
        draw_text(img, small, "   ".join(loc_values(lang, "TOTU_FE_")), x0, y)
        y += 24
    for where, text in menu_strings(names=False):
        if "TOTU_FE_" in where or "LOADING_TIP_" in where:      # shown above / below
            continue
        if len(text) > 130:
            text = text[:127] + "..."
        draw_text(img, small, text, x0, y)
        y += 22
    y += 8
    label("COUNTRY NAMES (SAMPLE OF THE GLYPH-CHECKED ONES), AS THE ENGINE FILLS THEM")
    names = dict(country_names())
    for where in ("german GER", "german ENG", "german DEN_fascism", "french DEN_fascism", "french FRA", "polish POL",
                  "spanish SPR", "braz_por BRA", "russian SOV_communism", "english USA_democratic"):
        if where in names:
            draw_text(img, small, f"{where}: {names[where]}", x0, y)
            y += 22
    y += 16

    label("ZOOM X3: DATE, CHANGELOG, ENGINE VERSION")
    zoom = sample.resize((sample.width * 3, sample.height * 3), Image.NEAREST)
    img.alpha_composite(zoom, (x0, y))
    y += zoom.height + 24

    # loading screen fonts: the black K edge is in the atlas, so the text is drawn once, in P (quote, status) and D
    # (name strap), over a light and a dark band; the right half repeats it without the edge (totu_caption*)
    label("TOTU_CAPTION_QUOTE (LINE 44) AND TOTU_CAPTION_SMALL_K - K EDGE BAKED IN; RIGHT: THE SAME WITHOUT THE EDGE")
    quote, small_k = load_font("totu_caption_quote"), load_font("totu_caption_small_k")
    tips = {lang: [m.group(2) for m in map(TIP_KEY.match, (ROOT / "localisation" / lang /
                                                           f"loading_tips_l_{lang}.yml").read_text(
        encoding="utf-8-sig").splitlines()) if m] for lang in ("russian", "english")}
    status = {"russian": "Загрузка исторических данных", "english": "Loading History"}     # LOADING_HISTORY
    for band in (BG_LIGHT, BG):
        for lang, k in (("russian", 8), ("english", 21)):
            parts = tips[lang][k].split("\\n")
            band_h = len(parts) * quote[0]["lineHeight"] + 40
            d.rectangle((0, y - 10, W, y + band_h), fill=band + (255,))
            for x, (qf, sf) in ((x0, (quote, small_k)), (x0 + 1100, (big, small))):
                yy = y
                for i, part in enumerate(parts):
                    colour = DIM if part.startswith("§D") else (246, 242, 234)
                    draw_text(img, qf, strip_codes(part), x, yy, colour)
                    yy += quote[0]["lineHeight"]
                draw_text(img, sf, status[lang], x, yy + 4, (246, 242, 234))
            y += band_h + 14
    y += 16

    PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    img.crop((0, 0, W, min(H, y))).convert("RGB").save(PREVIEW)
    print("wrote", PREVIEW.relative_to(ROOT))


def main():
    for ch in "AW0":        # the generalised glyph renderer must match the logo's one
        assert ImageChops.difference(glyph_mask(PIXEL_FONT[ch], 4), pixel_text_mask([ch], 4, line_gap=0)).getbbox() \
            is None, f"glyph_mask differs from pixel_text_mask on {ch}"
    for name, (cell, line_height, base, shadow) in FONTS.items():
        build_font(name, cell, line_height, base, shadow)

    ok = True
    for name in FONTS:
        miss = missing_glyphs(name)
        for where, chars in miss.items():
            print(f"MISSING in {name}: {where}: {' '.join(chars)}")
        ok = ok and not miss
    print("glyph check:", "every menu string, loading tip, status and country name is covered" if ok else "FAILED")
    problems = check_loading_tips()
    for p in problems:
        print("LOADING TIP:", p)
    print("loading tips:", "hand-set lines, straps and measure OK" if not problems else "FAILED")
    ok = ok and not problems
    write_fallback_loc()
    render_preview()
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
