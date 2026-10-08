"""Builds the caption bitmap fonts (design "broadcast": Soviet TV captions) and checks every string they draw.

Usage:
    python tools/build_fonts.py            build the atlases, write the fallback localisation and the previews
    python tools/build_fonts.py --check    run every check only and write NOTHING (exit 1 on a problem); for anyone
                                           who adds localisation keys, tools/fontcheck/*.txt entries or .gui boxes
    python tools/build_fonts.py --loc      rewrite only the generated localisation of the 8 other game languages
                                           (run it after adding or changing a key; --check reports the files stale)
    python tools/build_fonts.py --core-gfx regenerate interface/core.gfx from the game's copy (after a game patch)
    add --verbose to list the header boxes that overflow in vanilla too, the overflows of the Latin languages and the
    header boxes holding paragraph text

The face is the 5x7 character-generator font of the logo (PIXEL_FONT in tools/build_menu_gfx.py) plus the Cyrillic
and punctuation below. Every glyph gets the logo's CRT rounding and a soft white bloom baked into its alpha.
    totu_caption          4 px cells: 20x28 glyphs, advance 24, lineHeight 36, base 28  (menu and setup captions)
    totu_caption_small    2 px cells: 10x14 glyphs, advance 12, lineHeight 18, base 14  (date, changelog, labels)
    totu_caption_quote    totu_caption glyphs, lineHeight 44, black K edge baked in      (loading screen tip)
    totu_caption_small_k  totu_caption_small glyphs, black K edge baked in               (loading screen status, and the
                          bitmapfonts totu_label / totu_caption_name of the lobby: labels, engine-filled names)
    totu_button           totu_caption glyphs + K edge, lineHeight 40 = the plate, capitals in its middle (buttonText)
    totu_button_small     totu_caption_small glyphs + K edge, lineHeight 24 = the small plate (buttonText)
    totu_h36              teletext "double height": cells 2 px wide x 3 px tall, capitals 10x21, advance 12,
                          lineHeight 36, base 28 = vanilla hoi_36header; K edge; real accent marks in the 7 px above
                          the capitals (MARKS_ABOVE / MARKS_BELOW), Ł Ø Đ with their strokes, Ё and Й full height
    totu_h30              the same 2x3 cells, lineHeight 29, base 23 = vanilla hoi_30header; K edge; 2 px headroom, so
                          accented letters are their base capitals (as in the menu fonts); Ł Ø Đ with their strokes
    totu_h24              totu_button_small's glyphs (2 px cells, lineHeight 24, base 19 = vanilla hoi_24header) with
                          the accent marks in its 5 px headroom and a 1-row cedilla / ogonek / dot / comma below
                          (MARKS_ABOVE_2PX / MARKS_BELOW_2PX), Ł Ø Đ, Ё and Й full height: the in-game hoi_24header
                          (totu_button_small itself stays mark-free, so the menu's small plates do not change)
The loading pair is declared in interface/load_screen_font.gfx (the engine reads that file before every other
interface file), the menu fonts in interface/totu_fonts.gfx, and the three in-game header fonts in interface/core.gfx
(a copy of the vanilla file, written by --core-gfx): each header font lists its pixel atlas first and the vanilla
Orator file second. The engine merges a font's files glyph by glyph, the earlier file winning (vanilla
hoi4_typewriter16 = AFL Font + Times New Roman for the letters AFL lacks; cg_16b + hoi_16tooltip3 for # and @), and
only warns when the files' lineHeight / base differ, so the vanilla file fills any glyph the atlas lacks and every
vanilla text box keeps its place. Simplified Chinese and Korean keep vanilla through core_chinese.gfx /
core_korean.gfx, Japanese through the kept l_japanese overrides.

Localisation infrastructure (for everyone adding menu text):
  * Caption keys TOTU_FE_* (menus) / TOTU_IG_* (in game) / TOTU_MENU_* / TOTU_1990_NAME (MENU_KEY: drawn in a pixel
    font, glyph-checked) and text keys TOTU_TXT_* (TEXT_KEY: tooltips, descriptions, any text drawn in a vanilla font;
    not glyph-checked) live in localisation/<lang>/totu_menu*_l_<lang>.yml: the main file totu_menu_l_<lang>.yml plus
    one file per area, e.g. totu_menu_options_l_english.yml and totu_menu_options_l_russian.yml (UTF-8 with BOM, first
    line l_<lang>:). A TOTU_FE_ / TOTU_IG_ / TOTU_MENU_ / TOTU_TXT_ key anywhere else is a problem (no glyph check, no
    fallback there). Every caption value is glyph-checked against every pixel font, every key of these files must
    exist in English and Russian, no key may be defined twice in the mod's files of a language, and --loc (and the
    full run) copies the English values into totu_menu_captions_l_<lang>.yml for the 8 other game languages
    (generated; never edit it): every caption, TOTU_TXT_ and scenario key, and the files' other keys (spirit, leader
    names) where the game has no key of that name. --check reports a generated file that differs from what --loc
    would write (check_fallback_loc), so run --loc after adding keys.
  * Vanilla keys drawn in a pixel font: STATUS_KEY below plus one key or regular expression per line in
    tools/fontcheck/*.txt (see tools/fontcheck/README.txt). Their English, Russian and Latin-language values are
    glyph-checked.
  * Box widths: every text box / button of a vanilla or mod .gui whose font is a pixel font (any bitmapfont whose first
    file is gfx/fonts/totu_*: the header fonts of core.gfx and the totu_* fonts) is measured in English, Russian and
    the Latin languages against its maxWidth (button: size or sprite frame width) and maxHeight lines. A Russian vanilla
    header box that fitted in the vanilla font and overflows in the pixel font is a problem: give the key a shorter,
    faithful text in a localisation/russian/replace/totu_<area>_short_l_russian.yml file of your own (the fonts' own
    fixes are in totu_header_short_l_russian.yml). English is never touched (warning); the Latin languages are a
    known limitation (12 px per character against Orator's ~11; --verbose lists them).
  * Header boxes holding paragraph text (paragraph_boxes; --verbose): the stream that owns the window should switch
    them to a body font in its .gui copy.

Output follows the vanilla fonts (e.g. gfx/fonts/hoi_33.fnt in the game folder):
    gfx/fonts/<font>.fnt  text BMFont file: unicode=1, LF line endings, one page, no kerning; the info line's face is
                          "<font> <digest>", the digest of the glyph definitions (layout_digest), so --check notices
                          an atlas built from other pixels
    gfx/fonts/<font>.dds  uncompressed 32-bit, power of two, no mipmaps; RGB white, glyph in alpha
                          (the engine tints it with the font colour or a colour code)
The engine loads <fontfile>.dds next to the .fnt; the page file name inside the .fnt is not used.
Lowercase letters point at the uppercase rects, so everything renders in capitals. Accented Latin letters
(U+00C0..U+024F, U+1E00..U+1EFF, for engine country names in other game languages) point at their base capital,
except in MARK_TABLES fonts (totu_h36, totu_h24), which draw their marks.

The two _k fonts carry the menu's drop edge: a black copy of every glyph (+ bloom) at +2,+2 under the white glyph,
flattened into one straight-alpha RGBA tile. The engine multiplies the atlas RGB by the text colour (vanilla
hoi_24header bakes its shadow the same way), so the edge stays black under any colour code. Kept uncompressed: DXT
would smear the 2 px edge.

Afterwards the script checks that every menu string, loading tip, vanilla status / label string the caption fonts
show and every country name (English, Russian and the Latin-script game languages) has a glyph, checks the hand-set
loading tips (check_loading_tips) and renders tools/preview/font_test.png and font_headers.png (the in-game header
fonts beside the vanilla ones, sample and real titles, 3x zoom) from the written .fnt and .dds. It also
writes English text for the game languages the mod has no translation for (write_fallback_loc: menu captions and
scenario texts, the loading tips, the names of the countries the game does not know): the fonts have no other
script, and a missing key would show as its name. The vanilla strings come from the game folder (env HOI4_DIR,
default D:/steam/.../Hearts of Iron IV). Requires Pillow and numpy (pip install pillow numpy).
The script prints ASCII only (a non-UTF-8 Windows console cannot print Cyrillic): problems name keys, not texts.
"""
import sys

CHECK_ONLY = __name__ == "__main__" and "--check" in sys.argv[1:]
if CHECK_ONLY:
    sys.dont_write_bytecode = True      # --check writes nothing, not even tools/__pycache__

import hashlib                          # noqa: E402
import re                               # noqa: E402
import unicodedata                      # noqa: E402
from functools import lru_cache         # noqa: E402
from pathlib import Path                # noqa: E402

import numpy as np                      # noqa: E402
from PIL import Image, ImageChops, ImageDraw, ImageFilter     # noqa: E402

from build_menu_gfx import (GAME, LOAD_LINE_MAX, PIXEL_FONT, PLATE_H, QUOTE_BOX_W, SMALL_PLATE_H,  # noqa: E402
                            pixel_text_mask, save_dds)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "gfx" / "fonts"
PREVIEW = ROOT / "tools" / "preview" / "font_test.png"
HEADER_PREVIEW = ROOT / "tools" / "preview" / "font_headers.png"
FONTCHECK = ROOT / "tools" / "fontcheck"
CORE_GFX = ROOT / "interface" / "core.gfx"
# The global header-font swap (an interface/core.gfx copy) is switched off: in game the vanilla HUD stays as it was
# (user request, 2026-10-07). The restyled menus use the totu_h24 / totu_h30 / totu_h36 fonts of interface/totu_fonts.gfx
# instead. Set to True and run --core-gfx to bring the swap back.
CORE_GFX_ENABLED = False
HEADER_SHORT = ROOT / "localisation" / "russian" / "replace" / "totu_header_short_l_russian.yml"

# name: (px per font cell, lineHeight, base, shadow). Capitals stand on the baseline, so glyph tops sit at
# base - 7 cells. shadow > 0: the black K edge is baked into the atlas at +shadow,+shadow (RGBA tiles). A cell is an
# int (square) or (width, height) in px: (2, 3) is teletext "double height".
FONTS = {
    "totu_caption": (4, 36, 28, 0),
    "totu_caption_small": (2, 18, 14, 0),
    "totu_caption_quote": (4, 44, 28, 2),
    "totu_caption_small_k": (2, 18, 14, 2),
    # Button text drawn by the engine (buttonText), K edge baked in: the line box is as tall as the plate and the
    # capitals sit in its middle, so the label is centred whether the engine centres the line box or the ink.
    "totu_button": (4, PLATE_H, PLATE_H - (PLATE_H - 28) // 2, 2),                     # 40 px plates: capitals 6..34
    "totu_button_small": (2, SMALL_PLATE_H, SMALL_PLATE_H - (SMALL_PLATE_H - 14) // 2, 2),   # 24 px: capitals 5..19
    # In-game header fonts (interface/core.gfx): 2 px wide x 3 px tall cells, so a Russian window title fits the
    # vanilla box (advance 12 against Orator's 16 / 14). lineHeight and base are those of the vanilla Orator files,
    # which core.gfx chains after these as the glyph fallback; check_header_metrics compares them with the game files.
    "totu_h36": ((2, 3), 36, 28, 2),    # hoi_36header, nsb_hoi_36header: capitals at y 7..27, marks in y 0..6
    "totu_h30": ((2, 3), 29, 23, 2),    # hoi_30header: capitals at y 2..22
    "totu_h24": (2, 24, 19, 2),         # hoi_24header, nsb_hoi_24header: capitals at y 5..19, marks in y 0..4
}
# Vanilla header fonts drawn in the pixel atlases by interface/core.gfx: font name -> (atlas, the vanilla file chained
# after it, whose lineHeight / base the atlas must have).
HEADER_FONTS = {
    "hoi_36header": ("totu_h36", "hoi_36header"),
    "nsb_hoi_36header": ("totu_h36", "hoi_36header"),
    "hoi_30header": ("totu_h30", "hoi_30header"),
    "hoi_24header": ("totu_h24", "hoi_24header"),
    "nsb_hoi_24header": ("totu_h24", "hoi_24header"),
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
    # rare signs of vanilla titles, state and country names (multiplication, division, fractions, ordinals)
    "×": [".....", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "....."],
    "÷": [".....", "..#..", ".....", "#####", ".....", "..#..", "....."],
    "½": ["#....#.", "#...#..", "#..#...", "..#.##.", ".#....#", "#....#.", "....###"],
    "¼": ["#....#.", "#...#..", "#..#...", "..#.#.#", ".#..###", "#.....#", "......#"],
    "º": [".###.", "#...#", ".###.", ".....", "#####", ".....", "....."],
    "ª": [".###.", "#..#.", ".####", ".....", "#####", ".....", "....."],
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
    "Þ": ["#....", "####.", "#...#", "#...#", "####.", "#....", "#...."],     # Icelandic thorn
    "€": ["..###", ".#...", "####.", ".#...", "####.", ".#...", "..###"],
    "•": [".....", ".....", ".###.", ".###.", ".###.", ".....", "....."],     # list bullet
}
GLYPHS = {**PIXEL_FONT, **CYRILLIC, **PUNCTUATION, **LATIN_EXTRA}
# Code points drawn with another glyph's shape (all fonts): the minus sign as the hyphen, the spacing acute as the
# apostrophe, the schwa as E. ZERO_WIDTH: drawn as nothing, advance 0.
SHAPE_ALIAS = {"−": "-", "´": "’", "ə": "E", "Ə": "E"}
ZERO_WIDTH = {0x200B}

# STROKE_FONTS only (the in-game header fonts). The stroke letters, drawn whole in the 7 rows (elsewhere they are their
# base capital): Ł with the stem moved right so the stroke crosses it, Ø = a 5-row bowl with the slash running out at
# the top right and the bottom left corner (a full-height slashed O is the slashed zero), Đ / Ð with the bar left of
# the stem.
STROKES = {
    "Ł": [".#...", ".#...", ".#.#.", ".##..", "##...", ".#...", ".####"],
    "Ø": ["....#", ".###.", "#..##", "#.#.#", "##..#", ".###.", "#...."],
    "Đ": [".###.", ".#..#", ".#..#", "###.#", ".#..#", ".#..#", ".###."],
}
STROKE_OF = {"Ł": "Ł", "ł": "Ł", "Ø": "Ø", "ø": "Ø", "Đ": "Đ", "đ": "Đ", "Ð": "Đ", "ð": "Đ"}
STROKE_FONTS = {"totu_h36", "totu_h30", "totu_h24"}
# totu_h36. Diacritics by combining code point (the canonical decomposition of the accented letter):
# (rows top first, 5 columns, cell height in px, gap in px). The cells are as wide as the font's (2 px). Marks above
# end `gap` px above the capitals and must fit the headroom (base - 7 cells = 7 px in totu_h36); marks below start
# `gap` px under the baseline. Marks above keep the letters' 2x3 px cell (two rows + 1 px gap fill the headroom), so a
# title reads as one pixel grid; the ring, the tilde and the breve take 2 px rows (three rows; curves that close up
# at 3 px), and so do the marks below, to fit the 8 px under the baseline with the K edge.
MARKS_ABOVE = {
    0x300: ([".#...", "..#.."], 3, 1),              # grave
    0x301: (["...#.", "..#.."], 3, 1),              # acute
    0x302: (["..#..", ".#.#."], 3, 1),              # circumflex
    0x303: ([".##.#", "#.##."], 2, 2),              # tilde (2 px rows: at 3 px it closes into a blob)
    0x304: (["#####"], 3, 2),                       # macron
    0x306: (["#...#", ".###."], 2, 2),              # breve (and the Cyrillic short mark of Й), as the tilde
    0x307: (["..#.."], 3, 2),                       # dot above
    0x308: ([".#.#."], 3, 2),                       # diaeresis
    0x30A: (["..#..", ".#.#.", "..#.."], 2, 1),     # ring
    0x30B: (["..#.#", ".#.#."], 3, 1),              # double acute
    0x30C: ([".#.#.", "..#.."], 3, 1),              # caron
}
MARKS_BELOW = {
    0x323: (["..#.."], 3, 1),                       # dot below
    0x326: (["..#..", ".#..."], 2, 1),              # comma below
    0x327: (["..#..", "...#.", ".##.."], 2, 0),     # cedilla
    0x328: (["...#.", "..#..", "...##"], 2, 0),     # ogonek
}
# totu_h24 (2x2 px cells, 5 px above the capitals, 5 px below the baseline of which the K edge takes 2): two-row marks
# with a 1 px gap fill the headroom, one-row marks sit 2 px up; the ring is a two-row arch (three rows do not fit);
# below the baseline one 2 px row: the cedilla and the ogonek hang from the letter (gap 0), the dots 1 px under it.
MARKS_ABOVE_2PX = {
    0x300: ([".#...", "..#.."], 2, 1),              # grave
    0x301: (["...#.", "..#.."], 2, 1),              # acute
    0x302: (["..#..", ".#.#."], 2, 1),              # circumflex
    0x303: ([".##.#", "#.##."], 2, 1),              # tilde
    0x304: (["#####"], 2, 2),                       # macron
    0x306: (["#...#", ".###."], 2, 1),              # breve (and the short mark of Й)
    0x307: (["..#.."], 2, 2),                       # dot above
    0x308: ([".#.#."], 2, 2),                       # diaeresis
    0x30A: ([".###.", ".#.#."], 2, 1),              # ring, as an arch
    0x30B: (["..#.#", ".#.#."], 2, 1),              # double acute
    0x30C: ([".#.#.", "..#.."], 2, 1),              # caron
}
MARKS_BELOW_2PX = {
    0x323: (["..#.."], 2, 1),                       # dot below
    0x326: ([".##.."], 2, 1),                       # comma below
    0x327: (["..##."], 2, 0),                       # cedilla
    0x328: (["...##"], 2, 0),                       # ogonek
}
# Fonts drawn with real diacritics: font -> (marks above, marks below) in the headroom above the capitals and the
# descender room; they also draw Ё / Й as full-height Е / И with their mark. The other fonts draw an accented letter
# as its base capital (LATIN_ALIASES) and squeeze the mark of Ё / Й into the 7 rows.
MARK_TABLES = {"totu_h36": (MARKS_ABOVE, MARKS_BELOW), "totu_h24": (MARKS_ABOVE_2PX, MARKS_BELOW_2PX)}
MARK_FONTS = set(MARK_TABLES)
CYRILLIC_MARKED = {"Ё": ("Е", 0x308), "Й": ("И", 0x306)}

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
              0xC6, 0xE6, 0x152, 0x153, 0x1E9E, 0xA1, 0xBF, 0xB0, 0xA3,
              # the gaps of vanilla titles, state and country names (Þ þ × ÷ ½ ¼ º ª, then SHAPE_ALIAS and U+200B), € •
              0xDE, 0xFE, 0xD7, 0xF7, 0xBD, 0xBC, 0xBA, 0xAA, 0x2212, 0xB4, 0x259, 0x18F, 0x200B, 0x20AC, 0x2022]

# Strings drawn with these fonts besides the loc keys: the start date, the changelog line and the engine's version
# label (set by the game, not localisable). The vanilla strings the engine puts into caption-font boxes (loading
# statuses, the lobby's date line) are read from the game folder (vanilla_strings).
FIXED_STRINGS = ["1 января 1990", "Версия 0.1: карта 1990 года, новое меню", "Operation Postern v1.19.3.0.c01a (5632)",
                 "12:00, 1 января, 1990", "12:00, 1 January, 1990"]
# Vanilla keys whose values the engine draws in the caption fonts: the loading screen's status line
# (loadscreen_header), the "updating history" line and the vanilla labels of the lobby frame, the settings boards
# and the load / ironman-save windows (totu_caption_name). More keys come from tools/fontcheck/*.txt (fontcheck_keys);
# their English, Russian and LATIN_LANGUAGES values are glyph-checked.
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
# Keys drawn in the caption fonts (glyph-checked, English fallback for the other languages), in
# localisation/<lang>/totu_menu*_l_<lang>.yml (menu_files). TOTU_1990_NAME is the bookmark name the lobby shows.
MENU_KEY = re.compile(r'^\s*(TOTU_(?:FE|IG|MENU)_\w+|TOTU_1990_NAME):\d*\s*"(.*)"\s*$')
# Texts drawn in vanilla fonts: the scenario and country texts and TOTU_TXT_* (tooltips, descriptions, body text of
# any stream). English fallback only, no glyph check.
TEXT_KEY = re.compile(r'^\s*(TOTU_(?:[A-Z]{3}_)?1990_DESC|TOTU_TXT_\w+):\d*\s*"(.*)"\s*$')
# Keys that must live in the caption files (menu_files), the only files with the glyph check and the fallback.
CAPTION_FILE_KEY = re.compile(r"^TOTU_(?:FE|IG|MENU|TXT)_")
TIP_KEY = re.compile(r'^\s*LOADING_TIP_(\d+):\d*\s*"(.*)"\s*$')
QUOTE_MARKS = "«\"“„"           # a loading tip is a subtitle: it never opens with a quotation mark


def cell_xy(cell):
    """(width, height) in px of a font cell; an int is a square cell."""
    return (cell, cell) if isinstance(cell, int) else tuple(cell)


def glyph_key(cp):
    """GLYPHS key of a code point in a font without marks: an accented Latin letter is its base capital, lowercase is
    uppercase, SHAPE_ALIAS applies, the no-break and zero-width spaces are the space."""
    if cp in LATIN_ALIASES:
        return LATIN_ALIASES[cp]
    ch = " " if cp == 0xA0 or cp in ZERO_WIDTH else chr(cp)
    ch = SHAPE_ALIAS.get(ch, ch)
    return ch.upper() if ch.upper() in GLYPHS else ch


def glyph_shape(cp, font=None):
    """Hashable shape of a code point in a FONTS font: a tuple of GLYPHS rows (STROKES in STROKE_FONTS), or in a
    MARK_TABLES font ("+", base rows, mark above, mark below), each mark (rows, cell height, gap) of the font's tables
    or None. Letters whose decomposition has a mark these tables lack keep the marks they have; a letter with none of
    them is its base capital. Equal shapes share one atlas rect."""
    ch = chr(cp)
    if font in STROKE_FONTS and ch in STROKE_OF:
        return tuple(STROKES[STROKE_OF[ch]])
    if font in MARK_TABLES:
        above_t, below_t = MARK_TABLES[font]

        def spec(table, mark):
            rows, h, gap = table[mark]
            return tuple(rows), h, gap
        if ch.upper() in CYRILLIC_MARKED:
            base, mark = CYRILLIC_MARKED[ch.upper()]
            return "+", tuple(GLYPHS[base]), spec(above_t, mark), None
        if cp in LATIN_ALIASES:
            rest = unicodedata.normalize("NFD", ch)[1:]
            if rest and all(unicodedata.combining(m) for m in rest):
                above = next((spec(above_t, ord(m)) for m in rest if ord(m) in above_t), None)
                below = next((spec(below_t, ord(m)) for m in rest if ord(m) in below_t), None)
                if above or below:
                    return "+", tuple(GLYPHS[LATIN_ALIASES[cp]]), above, below
    return tuple(GLYPHS[glyph_key(cp)])


def shape_layers(shape, cell):
    """The drawn parts of a shape: [(rows, (cell width, cell height), y)], y in px from the top of the capitals
    (marks above have y < 0, marks below start under the 7 rows)."""
    cx, cy = cell_xy(cell)
    if shape[0] != "+":
        return [(tuple(shape), (cx, cy), 0)]
    _, base, above, below = shape
    layers = [(base, (cx, cy), 0)]
    if above is not None:
        rows, h, gap = above
        layers.append((tuple(rows), (cx, h), -gap - len(rows) * h))
    if below is not None:
        rows, h, gap = below
        layers.append((tuple(rows), (cx, h), len(base) * cy + gap))
    return layers


def layers_mask(layers, ss=4):
    """Lit cells of shape layers with the logo's CRT rounding: drawn ss times larger, softened (0.12 of the smaller
    cell side), re-thresholded and downsampled. Returns the L mask and the y of its top (px from the capitals' top)."""
    y0 = min(y for _, _, y in layers)
    y1 = max(y + len(rows) * c[1] for rows, c, y in layers)
    w = max(len(rows[0]) * c[0] for rows, c, _ in layers)
    big = Image.new("L", (w * ss, (y1 - y0) * ss), 0)
    d = ImageDraw.Draw(big)
    for rows, (cx, cy), y in layers:
        for gy, row in enumerate(rows):
            for gx, v in enumerate(row):
                if v == "#":
                    d.rectangle((gx * cx * ss, (y - y0 + gy * cy) * ss, (gx + 1) * cx * ss - 1,
                                 (y - y0 + (gy + 1) * cy) * ss - 1), fill=255)
    blur = min(min(c) for _, c, _ in layers) * ss * 0.12
    big = big.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: 255 if v > 110 else 0)
    return big.resize((w, y1 - y0), Image.LANCZOS), y0


def glyph_mask(rows, cell, ss=4):
    """Lit cells of one glyph with the logo's CRT rounding: build_menu_gfx.pixel_text_mask for glyphs of any size
    (descenders, the wide №, non-square cells). main() checks that both give the same pixels on plain 5x7 glyphs."""
    return layers_mask([(tuple(rows), cell_xy(cell), 0)], ss)[0]


def glyph_tile(shape, cell):
    """Atlas tile: the glyph (every layer of its shape) PAD px in from each edge, plus the baked bloom (caption() of
    the mockup; radius 0.9 of the smaller cell side). The glyph is rasterised between two blank columns, as inside a
    line of text, so its side edges come out as in the mockup."""
    cx, cy = cell_xy(cell)
    layers = shape_layers(shape, cell)
    cols = {len(rows[0]) for rows, _, _ in layers}
    assert len(cols) == 1, f"shape layers of different widths: {shape}"
    m0, _ = layers_mask([(tuple("." + r + "." for r in rows), c, y) for rows, c, y in layers])
    m0 = m0.crop((cx, 0, cx + cols.pop() * cx, m0.height))
    m = Image.new("L", (m0.width + 2 * PAD, m0.height + 2 * PAD), 0)
    m.paste(m0, (PAD, PAD))
    bloom = m.filter(ImageFilter.GaussianBlur(min(cx, cy) * 0.9)).point(lambda v: v * BLOOM)
    return ImageChops.lighter(m, bloom)


def glyph_tile_k(shape, cell, shadow):
    """RGBA atlas tile with the menu's drop edge baked in: the black K copy (glyph + bloom) at +shadow,+shadow under
    the white glyph + bloom, flattened into straight alpha (alpha = aw + ak (1 - aw), RGB = 255 aw / alpha). Drawn
    over a background this equals the menu's black copy plus the white caption on top, pixel for pixel. The tile is
    PAD px in at the left and top, PAD + shadow at the right and bottom."""
    m = np.asarray(glyph_tile(shape, cell), np.float32) / 255
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
    """BMFont text file, laid out like the vanilla ones (BMFont's own column padding). padding = up,right,down,left.
    The face is "<name> <layout_digest>" (the engine does not use it; check_atlases does)."""
    lines = [
        f'info face="{name} {layout_digest(name)}" size={7 * cell_xy(cell)[1]} bold=0 italic=0 charset="" unicode=1 '
        "stretchH=100 smooth=0 "
        f"aa=1 padding={PAD},{PAD + shadow},{PAD + shadow},{PAD} spacing={SPACING},{SPACING} outline=0",
        f"common lineHeight={line_height} base={base} scaleW={size[0]} scaleH={size[1]} pages=1 packed=0 "
        "alphaChnl=1 redChnl=0 greenChnl=0 blueChnl=0",
        f'page id=0 file="{name}.dds"',
        f"chars count={len(chars)}",
    ]
    for cp, (x, y, w, h, xo, yo, adv) in sorted(chars.items()):
        lines.append(f"char id={cp:<4d} x={x:<5d} y={y:<5d} width={w:<5d} height={h:<5d} xoffset={xo:<5d} "
                     f"yoffset={yo:<5d} xadvance={adv:<5d} page={0:<2d} chnl=15")
    return "\n".join(lines) + "\n"


@lru_cache(maxsize=None)
def font_layout(name):
    """{code point: (shape, y of the shape's top in the line box, xadvance)} of a FONTS entry, without drawing it:
    what the checks measure and what build_font writes."""
    cell, line_height, base, shadow = FONTS[name]
    cx, cy = cell_xy(cell)
    top = base - 7 * cy
    out = {}
    for cp in CODEPOINTS:
        shape = glyph_shape(cp, name)
        layers = shape_layers(shape, cell)
        adv = 0 if cp in ZERO_WIDTH else (len(layers[0][0][0]) + 1) * cx
        out[cp] = (shape, top + min(y for _, _, y in layers), adv)
    return out


@lru_cache(maxsize=None)
def layout_digest(name):
    """10 hex digits of SHA-1 over everything that sets a font's pixels and metrics: its FONTS entry, PAD, SPACING,
    BLOOM and every glyph's shape (rows and marks), position and advance. Written into the .fnt face (fnt_text);
    check_atlases compares it, so an edited glyph without a rebuild is reported as a stale atlas."""
    data = repr((FONTS[name], PAD, SPACING, BLOOM, sorted(font_layout(name).items())))
    return hashlib.sha1(data.encode("utf-8")).hexdigest()[:10]


def font_advances(name):
    """{code point: {"xadvance": px}} of a FONTS entry (the shape read_fnt gives), from its definition."""
    return {cp: {"xadvance": adv} for cp, (_, _, adv) in font_layout(name).items()}


def check_layouts():
    """Every glyph inside its line box: marks above not over the line top, descenders, marks below and the K edge not
    under the line bottom (the next line's marks start there)."""
    problems = []
    for name, (cell, line_height, base, shadow) in FONTS.items():
        for cp, (shape, y_top, _) in font_layout(name).items():
            layers = shape_layers(shape, cell)
            bottom = y_top - min(y for _, _, y in layers) + max(y + len(r) * c[1] for r, c, y in layers) + shadow
            if y_top < 0 or bottom > line_height:
                problems.append(f"{name}: U+{cp:04X} spans y {y_top}..{bottom}, outside the line box 0..{line_height}")
    return problems


def build_font(name, cell, line_height, base, shadow=0):
    """Writes gfx/fonts/<name>.dds and .fnt. Identical shapes (a and A, Latin A and Cyrillic А) share one rect.
    shadow = 0: white RGB, glyph + bloom in alpha. shadow > 0: RGBA tiles from glyph_tile_k (baked K edge)."""
    layout = font_layout(name)
    shapes = list(dict.fromkeys(shape for shape, _, _ in layout.values()))
    if shadow:
        tiles = [glyph_tile_k(s, cell, shadow) for s in shapes]
        pos, aw, ah = pack([t.size for t in tiles])
        atlas = Image.new("RGBA", (aw, ah), (255, 255, 255, 0))
        for tile, p in zip(tiles, pos):
            atlas.paste(tile, p)
    else:
        tiles = [glyph_tile(s, cell) for s in shapes]
        pos, aw, ah = pack([t.size for t in tiles])
        alpha = Image.new("L", (aw, ah), 0)
        for tile, p in zip(tiles, pos):
            alpha.paste(tile, p)
        atlas = Image.new("RGBA", (aw, ah), (255, 255, 255, 0))
        atlas.putalpha(alpha)

    rect = {s: (*p, *t.size) for s, p, t in zip(shapes, pos, tiles)}
    chars = {cp: (*rect[s], -PAD, y_top - PAD, adv) for cp, (s, y_top, adv) in layout.items()}
    save_dds(atlas, OUT / f"{name}.dds")
    path = OUT / f"{name}.fnt"
    path.write_text(fnt_text(name, cell, line_height, base, (aw, ah), chars, shadow), encoding="ascii", newline="\n")
    print("wrote", path.relative_to(ROOT), f"{len(chars)} chars, {len(shapes)} glyphs, atlas {aw}x{ah}")


def check_atlases():
    """The written gfx/fonts/<font>.fnt / .dds files against the definitions (--check builds nothing): the face digest
    (layout_digest: the glyph pixels), code points, lineHeight, base and advances, and a .dds of the .fnt's size, else
    they are stale."""
    problems = []
    for name, (cell, line_height, base, shadow) in FONTS.items():
        path = OUT / f"{name}.fnt"
        if not path.exists() or not path.with_suffix(".dds").exists():
            problems.append(f"gfx/fonts/{name}.fnt or .dds is missing: run python tools/build_fonts.py")
            continue
        common, chars = read_fnt(path)
        face = re.search(r'^info face="([^"]*)"', path.read_text(encoding="latin-1"), re.M)
        layout = font_layout(name)
        head = path.with_suffix(".dds").read_bytes()[:20]
        dds_size = (int.from_bytes(head[16:20], "little"), int.from_bytes(head[12:16], "little"))
        same = (common.get("lineHeight"), common.get("base")) == (line_height, base) and set(chars) == set(layout) \
            and all(chars[cp]["xadvance"] == adv and chars[cp]["yoffset"] == y_top - PAD
                    for cp, (_, y_top, adv) in layout.items()) \
            and face is not None and face.group(1) == f"{name} {layout_digest(name)}" \
            and dds_size == (common.get("scaleW"), common.get("scaleH"))
        if not same:
            problems.append(f"gfx/fonts/{name}.fnt / .dds is stale (built from other glyph definitions): run python "
                            "tools/build_fonts.py")
    return problems

# ---------------------------------------------------------------- font files, localisation, strings
FIELD = re.compile(r'(\w+)=("[^"]*"|\S+)')
# A localisation line: key, value up to the last quote, an optional trailing comment.
LOC_LINE = re.compile(r'^\s*([^\s:#"]+):\d*\s*"(.*)"\s*(?:#[^"]*)?$')
GAME_LANGUAGES = ["english", "russian", *LATIN_LANGUAGES]      # the languages the pixel fonts draw
BOM = b"\xef\xbb\xbf"                                           # localisation files are UTF-8 with BOM


def rel(path):
    """A path for messages: relative to the mod or the game folder, forward slashes."""
    for base in (ROOT, GAME):
        try:
            return Path(path).relative_to(base).as_posix()
        except ValueError:
            pass
    return Path(path).as_posix()


def read_fnt(path):
    """The parts of a text .fnt the engine uses: the common line and the chars (id -> fields)."""
    common, chars = {}, {}
    for line in Path(path).read_text(encoding="latin-1").splitlines():
        tag, _, rest = line.partition(" ")
        fields = dict(FIELD.findall(rest))
        if tag == "common":
            common = {k: int(v) for k, v in fields.items() if v.lstrip("-").isdigit()}
        elif tag == "char":
            chars[int(fields["id"])] = {k: int(v) for k, v in fields.items() if v.lstrip("-").isdigit()}
    return common, chars


def load_font(name):
    common, chars = read_fnt(OUT / f"{name}.fnt")
    return common, chars, Image.open(OUT / f"{name}.dds").convert("RGBA")


def strip_codes(text):
    return re.sub(r"§.|\\n", "", text)


def plain(text):
    """What a loc value shows without its fields: § codes, \\n, $...$, [...] and £icon£ removed."""
    return re.sub(r"\$[^$]*\$|\[[^\]]*\]|£[^£\s]*£?", "", strip_codes(text))


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


@lru_cache(maxsize=None)
def game_loc(lang):
    """{key: value} of one game language as the engine resolves it: the game's localisation, then the mod's on top,
    each with its replace folder last. Only the mod's part without the game folder (env HOI4_DIR)."""
    loc = {}
    for root in (GAME / "localisation" / lang, ROOT / "localisation" / lang):
        if not root.exists():
            continue
        files = sorted(root.rglob("*.yml"), key=lambda f: ("replace" in f.relative_to(root).parts, f.as_posix()))
        for f in files:
            for line in f.read_text(encoding="utf-8-sig", errors="replace").splitlines():
                m = LOC_LINE.match(line)
                if m:
                    loc[m.group(1)] = m.group(2)
    return loc


def menu_files(lang):
    """The mod's caption files of one language: localisation/<lang>/totu_menu_l_<lang>.yml first, then every other
    totu_menu*_l_<lang>.yml (one per area, e.g. totu_menu_options_l_<lang>.yml), never the generated
    totu_menu_captions_l_<lang>.yml."""
    folder = ROOT / "localisation" / lang
    main = folder / f"totu_menu_l_{lang}.yml"
    rest = [f for f in sorted(folder.glob(f"totu_menu*_l_{lang}.yml"))
            if f != main and f.name != f"totu_menu_captions_l_{lang}.yml"]
    return ([main] if main.exists() else []) + rest


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


def fontcheck_entries():
    """(where, pattern) of tools/fontcheck/*.txt (README.txt excepted): one vanilla key or regular expression per line,
    matched against the whole key; # starts a comment. See tools/fontcheck/README.txt."""
    out = []
    for f in sorted(FONTCHECK.glob("*.txt")) if FONTCHECK.exists() else []:
        if f.name.lower() == "readme.txt":
            continue
        for n, line in enumerate(f.read_text(encoding="utf-8-sig").splitlines(), 1):
            entry = line.split("#", 1)[0].strip()
            if entry:
                out.append((f"tools/fontcheck/{f.name}:{n}", entry))
    return out


def fontcheck_problems():
    """tools/fontcheck entries that are not valid regular expressions, or match no English key."""
    problems, english = [], list(game_loc("english"))
    for where, pattern in fontcheck_entries():
        try:
            rx = re.compile(pattern)
        except re.error as e:
            problems.append(f"{where}: not a regular expression ({e})")
            continue
        if GAME.exists() and not any(rx.fullmatch(k) for k in english):
            problems.append(f"{where}: {pattern} matches no key of the English localisation")
    return problems


def status_key(key):
    """True for a vanilla key whose value a pixel font draws: STATUS_KEY or an entry of tools/fontcheck/*.txt."""
    return bool(STATUS_KEY.match(f'{key}:0 ""')) or bool(_fontcheck_rx() and _fontcheck_rx().fullmatch(key))


@lru_cache(maxsize=None)
def _fontcheck_rx():
    good = []
    for _, pattern in fontcheck_entries():
        try:
            re.compile(pattern)
            good.append(f"(?:{pattern})")
        except re.error:
            pass
    return re.compile("|".join(good)) if good else None


def vanilla_strings():
    """(where, text) of the vanilla strings the engine draws in the pixel fonts (status_key: STATUS_KEY and
    tools/fontcheck), in English, Russian and LATIN_LANGUAGES as the engine resolves them (the mod's replacements
    included), without their fields (plain). Empty without the game folder (env HOI4_DIR)."""
    if not GAME.exists():
        return
    for lang in GAME_LANGUAGES:
        for key, value in game_loc(lang).items():
            if status_key(key):
                yield f"{lang} {key}", plain(value)


def menu_strings(names=True):
    """(where, text) for every string the caption fonts draw, without § codes and \\n: the TOTU_* caption keys of
    every menu file (menu_files), the loading tips, FIXED_STRINGS, the vanilla status strings and (names) every
    country name."""
    for folder in sorted(p for p in (ROOT / "localisation").iterdir() if p.is_dir()):
        for f in menu_files(folder.name):
            for key, value in yml_values(f, MENU_KEY):
                yield f"{folder.name} {key}", strip_codes(value)
    for f in sorted((ROOT / "localisation").glob("*/loading_tips_l_*.yml")):
        for key, value in yml_values(f, TIP_KEY):
            yield f"{f.parent.name} LOADING_TIP_{key}", strip_codes(value)
    for s in FIXED_STRINGS:
        yield "fixed", s
    yield from vanilla_strings()
    if names:
        yield from country_names()


def missing_glyphs(name, strings=None):
    """{where: [characters]} of the strings (default menu_strings()) that a font has no glyph for."""
    chars = font_layout(name)
    out = {}
    for where, text in (menu_strings() if strings is None else strings):
        miss = sorted({ch for ch in text if ord(ch) not in chars})
        if miss:
            out[where] = miss
    return out


def check_menu_loc():
    """The English and Russian caption files (menu_files): UTF-8 with BOM and the l_<lang>: header first, every key in
    both languages (a missing one would show as its raw name). Only caption keys (MENU_KEY) are glyph-checked; other
    keys of these files (TEXT_KEY texts, spirit or leader names drawn in vanilla fonts) are only copied to the other
    languages. Duplicates and caption keys outside these files: check_mod_loc."""
    problems, keys = [], {}
    for lang in ("english", "russian"):
        seen = {}
        for f in menu_files(lang):
            raw = f.read_bytes()
            if not raw.startswith(BOM):
                problems.append(f"{rel(f)}: not UTF-8 with BOM")
            text = raw.decode("utf-8-sig", errors="replace")
            head = next((line.strip() for line in text.splitlines() if line.strip()), "")
            if head != f"l_{lang}:":
                problems.append(f"{rel(f)}: the first line is not l_{lang}:")
            for line in text.splitlines():
                m = LOC_LINE.match(line)
                if m:
                    seen.setdefault(m.group(1), rel(f))
        keys[lang] = seen
    for a, b in (("english", "russian"), ("russian", "english")):
        for k in sorted(set(keys[a]) - set(keys[b])):
            problems.append(f"{k}: in {keys[a][k]} but in no {b} caption file")
    return problems


def check_mod_loc():
    """Every .yml of the mod's localisation/<lang>/ folders (replace/ included): no key defined twice in one language
    (the engine keeps one of them, whichever it reads last; for the streams' replace files, e.g. two
    totu_<area>_short_l_russian.yml shortening the same title), and no TOTU_FE_ / TOTU_IG_ / TOTU_MENU_ / TOTU_TXT_ key
    outside the caption files (menu_files; the generated totu_menu_captions file aside): elsewhere it gets neither the
    glyph check nor the fallback of the other languages."""
    problems = []
    for folder in sorted(p for p in (ROOT / "localisation").iterdir() if p.is_dir()):
        lang, seen = folder.name, {}
        caption_files = set(menu_files(lang))
        for f in sorted(folder.rglob("*.yml")):
            stray = f not in caption_files and f.name != f"totu_menu_captions_l_{lang}.yml"
            for line in f.read_text(encoding="utf-8-sig", errors="replace").splitlines():
                m = LOC_LINE.match(line)
                if not m:
                    continue
                key = m.group(1)
                if key in seen:
                    problems.append(f"{key} is defined twice in {lang}: {seen[key]} and {rel(f)}")
                seen[key] = rel(f)
                if stray and CAPTION_FILE_KEY.match(key):
                    problems.append(f"{key} is in {rel(f)}: TOTU_FE_/IG_/MENU_/TXT_ keys belong in "
                                    f"localisation/{lang}/totu_menu_<area>_l_{lang}.yml (glyph check, fallback)")
    return problems


def check_loading_tips():
    """The hand-set loading tips (localisation/<english|russian>/loading_tips_l_*.yml, interface/load_screen.gui):
    keys LOADING_TIP_0.. consecutive and as many in English as in Russian; each value is 1-3 quote lines and a last
    line §D<name strap>§!, split at a literal \\n; no line longer than LOAD_LINE_MAX characters or 40 advances of
    totu_caption_quote; a greedy wrap at the tip box width (QUOTE_BOX_W) gives back exactly the hand-set lines; no
    quotation mark opens the quote. Returns the list of problems."""
    advances = font_advances("totu_caption_quote")
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
            for n, line in enumerate(lines):
                width = sum(advances[ord(ch)]["xadvance"] for ch in line if ord(ch) in advances)
                if len(line) > LOAD_LINE_MAX or width > max_px:
                    problems.append(f"{where}: line {n + 1} has {len(line)} characters / {width} px")
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


# ---------------------------------------------------------------- .gui / .gfx scan: box widths, header strings
SCRIPT_TOKEN = re.compile(r'"[^"]*"|[{}=]|#[^\n]*|[^\s{}="#]+')


def parse_script(text):
    """Paradox script -> [(key, value)]: value a string or a nested list, comments dropped, quotes stripped; a bare
    value has the key None."""
    toks = [t for t in SCRIPT_TOKEN.findall(text) if not t.startswith("#")]
    pos = 0

    def block():
        nonlocal pos
        items = []
        while pos < len(toks):
            t = toks[pos]
            if t == "}":
                pos += 1
                return items
            if pos + 1 < len(toks) and toks[pos + 1] == "=":
                pos += 2
                if pos < len(toks) and toks[pos] == "{":
                    pos += 1
                    items.append((t, block()))
                elif pos < len(toks):
                    items.append((t, toks[pos].strip('"')))
                    pos += 1
            elif t == "{":
                pos += 1
                items.append((None, block()))
            else:
                items.append((None, t.strip('"')))
                pos += 1
        return items
    return block()


def get(items, key):
    """The value of the first key of a parsed block, ignoring case."""
    for k, v in items:
        if k is not None and k.lower() == key.lower():
            return v
    return None


def number(value):
    """int of a script value, None for anything else (100%, missing)."""
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


@lru_cache(maxsize=None)
def interface_files(ext, game_only=False):
    """{relative path: file} of interface/**/*.<ext> as the engine loads them: the game's (DLC folders included), the
    mod's of the same relative path replacing them (game_only: the game's alone)."""
    files = {}
    if GAME.exists():
        for root in (GAME / "interface", *sorted((GAME / "dlc").glob("*/interface"))):
            for f in sorted(root.rglob(f"*.{ext}")):
                files.setdefault(f.relative_to(root).as_posix().lower(), f)
    if not game_only:
        for f in sorted((ROOT / "interface").rglob(f"*.{ext}")):
            files[f.relative_to(ROOT / "interface").as_posix().lower()] = f
    return files


@lru_cache(maxsize=None)
def font_defs(game_only=False):
    """{font name: {"files": [...], "l_<lang>": [...]}} of every bitmapfont and bitmapfont_override of the .gfx files
    as loaded (game_only: vanilla), fontfiles without extension (gfx/fonts/hoi_20b)."""
    defs = {}
    for _, f in sorted(interface_files("gfx", game_only).items()):
        text = f.read_text(encoding="utf-8-sig", errors="replace")
        if "bitmapfont" not in text:
            continue
        for key, items in parse_script(text):
            if not (key and key.lower() == "bitmapfonts" and isinstance(items, list)):
                continue
            for k, v in items:
                if k is None or not isinstance(v, list) or not get(v, "name"):
                    continue
                files = [x for _, x in get(v, "fontfiles") or []] or ([get(v, "path")] if get(v, "path") else [])
                entry = defs.setdefault(get(v, "name"), {})
                if k.lower() == "bitmapfont":
                    entry["files"] = files
                elif k.lower() == "bitmapfont_override":
                    for _, lang in get(v, "languages") or []:
                        entry[lang] = files
    return defs


def check_font_files():
    """Every fontfiles entry of every bitmapfont / override as loaded exists as .fnt plus a .dds or .tga page in the
    mod's or the game's gfx/fonts (the engine logs "Missing font file" and draws nothing)."""
    problems = []
    for font, entry in sorted(font_defs().items()):
        for lang, files in sorted(entry.items()):
            for fn in files:
                found = {ext for ext in (".fnt", ".dds", ".tga") for base in (ROOT, GAME)
                         if (base / f"{fn}{ext}").is_file()}
                if ".fnt" not in found or not found & {".dds", ".tga"}:
                    problems.append(f"font {font} ({lang}): {fn}.fnt or its .dds / .tga page is in neither the mod "
                                    "nor the game")
    return problems if GAME.exists() else []


def font_files(font, lang, game_only=False):
    """The fontfiles a font uses in a game language (its l_<lang> override, else its base files); None if unknown."""
    entry = font_defs(game_only).get(font)
    if not entry:
        return None
    return entry.get(f"l_{lang}") or entry.get("files")


def pixel_atlas(files):
    """The FONTS atlas a fontfiles list draws with (its first file gfx/fonts/<atlas>), else None."""
    if files and files[0].startswith("gfx/fonts/") and files[0][len("gfx/fonts/"):] in FONTS:
        return files[0][len("gfx/fonts/"):]
    return None


@lru_cache(maxsize=None)
def chain_metrics(files):
    """(lineHeight, {code point: xadvance}) of a fontfiles chain: the earlier file wins per glyph, as the engine
    merges them. A FONTS atlas is measured from its definition, a game file from GAME/<file>.fnt."""
    line_height, adv = None, {}
    for fn in files:
        name = fn[len("gfx/fonts/"):] if fn.startswith("gfx/fonts/") else None
        if name in FONTS:
            lh, a = FONTS[name][1], {cp: v for cp, (_, _, v) in font_layout(name).items()}
        else:
            p = GAME / f"{fn}.fnt"
            if not p.exists():
                continue
            common, chars = read_fnt(p)
            lh, a = common.get("lineHeight"), {cp: c["xadvance"] for cp, c in chars.items()}
        line_height = line_height or lh
        for cp, v in a.items():
            adv.setdefault(cp, v)
    return line_height, adv


@lru_cache(maxsize=None)
def sprite_frames():
    """{sprite name lowercased: (texture file, frames, size x)} of every sprite of the .gfx files as loaded."""
    out = {}
    for _, f in sorted(interface_files("gfx").items()):
        text = f.read_text(encoding="utf-8-sig", errors="replace")
        for k, v in parse_script(text):
            if not (k and k.lower() == "spritetypes" and isinstance(v, list)):
                continue
            for kind, s in v:
                if isinstance(s, list) and get(s, "name"):
                    size = get(s, "size")
                    out[get(s, "name").lower()] = (get(s, "texturefile") or get(s, "textureFile1"),
                                                   number(get(s, "noOfFrames")) or 1,
                                                   number(get(size, "x")) if isinstance(size, list) else None)
    return out


def sprite_width(name):
    """Frame width in px of a sprite (its size, else texture width / frames); None if unknown."""
    entry = sprite_frames().get((name or "").lower())
    if not entry:
        return None
    texture, frames, size_x = entry
    if size_x:
        return size_x
    for base in (ROOT, GAME):
        p = base / (texture or "")
        if texture and p.is_file():
            head = p.read_bytes()[:32]
            if head[:4] == b"DDS ":
                return int.from_bytes(head[16:20], "little") // frames
            try:
                with Image.open(p) as im:
                    return im.size[0] // frames
            except OSError:
                return None
    return None


@lru_cache(maxsize=None)
def gui_boxes():
    """Every text box and button of the .gui files as loaded that has a font and a text: dicts file, mod (True for the
    mod's files), name, kind, font, key, max_w (maxWidth; buttons: size or sprite frame width), max_h, hidden (moved
    off screen, x or y <= -5000, as the mod hides engine elements)."""
    out = []
    for relpath, f in sorted(interface_files("gui").items()):
        is_mod = ROOT in f.parents

        def walk(items):
            for k, v in items:
                if not isinstance(v, list):
                    continue
                font, text = get(v, "font") or get(v, "buttonFont"), get(v, "text") or get(v, "buttonText")
                if isinstance(font, str) and isinstance(text, str) and text:
                    kind = (k or "").lower()
                    pos = get(v, "position")
                    size = get(v, "size")
                    max_w = number(get(v, "maxWidth"))
                    if "button" in kind:
                        max_w = (number(get(size, "x")) or number(get(size, "width"))) if isinstance(size, list) \
                            else None
                        max_w = max_w or sprite_width(get(v, "quadTextureSprite") or get(v, "spriteType"))
                    hidden = isinstance(pos, list) and any((number(get(pos, a)) or 0) <= -5000 for a in "xy")
                    out.append(dict(file=relpath, mod=is_mod, name=get(v, "name") or "?", kind=kind, font=font,
                                    key=text, max_w=max_w, max_h=number(get(v, "maxHeight")), hidden=hidden))
                walk(v)
        walk(parse_script(f.read_text(encoding="utf-8-sig", errors="replace")))
    return out


def loc_paragraphs(key, loc, depth=0):
    """(paragraphs, dynamic) of a key's value as shown: § codes removed, $KEY$ of other keys resolved, other $...$,
    [...] and £icon£ fields dropped (dynamic = True), split at \\n. None if the key does not exist."""
    if key not in loc:
        return None
    dynamic = False

    def field(m):
        nonlocal dynamic
        name = m.group(1).split("|")[0]
        if depth < 4 and name in loc:
            sub = loc_paragraphs(name, loc, depth + 1)
            dynamic = dynamic or sub[1]
            return "\\n".join(sub[0])
        dynamic = True
        return ""

    text = re.sub(r"\$([^$]*)\$", field, loc[key])
    text, n = re.subn(r"\[[^\]]*\]|£[^£\s]*£?", "", text)
    dynamic = dynamic or n > 0
    text = re.sub(r"§.", "", text).replace('\\"', '"')
    return text.split("\\n"), dynamic


def fit(paragraphs, metrics, max_w, max_h):
    """(widest paragraph px unwrapped, lines, allowed lines, overflow) of text wrapped greedily at max_w, lines
    allowed = maxHeight / lineHeight (at least 1; one without maxHeight). Overflow: more lines than allowed or a line
    still wider than max_w (one long word)."""
    line_height, adv = metrics

    def width(s):
        return sum(adv.get(ord(ch), 0) for ch in s)

    lines = []
    for para in paragraphs:
        line = ""
        for word in para.split(" "):
            trial = word if not line else f"{line} {word}"
            if line and width(trial) > max_w:
                lines.append(line)
                line = word
            else:
                line = trial
        lines.append(line)
    allowed = max(1, (max_h or 0) // (line_height or 1))
    over = max(width(line) for line in lines) > max_w or len(lines) > allowed
    return max(width(para) for para in paragraphs), len(lines), allowed, over


def box_fits():
    """Every visible box of gui_boxes in a pixel font (font_files' first file a FONTS atlas) with a loc key and a
    width, measured in English, Russian and LATIN_LANGUAGES. Yields dicts: box, lang, atlas, px, lines, allowed, over,
    dynamic, words (of the text) and vanilla_over (the same box in the vanilla font of the game's own .gfx: True /
    False, None for the mod's own fonts)."""
    for box in gui_boxes():
        if box["hidden"] or not box["max_w"] or box["max_w"] <= 0:
            continue
        for lang in GAME_LANGUAGES:
            files = font_files(box["font"], lang)
            atlas = pixel_atlas(files)
            if not atlas:
                continue
            loc = game_loc(lang)
            shown = loc_paragraphs(box["key"], loc)
            if shown is None:
                continue
            paragraphs, dynamic = shown
            px, lines, allowed, over = fit(paragraphs, chain_metrics(tuple(files)), box["max_w"], box["max_h"])
            vfiles = font_files(box["font"], lang, game_only=True)
            vanilla_over = None
            if vfiles and not pixel_atlas(vfiles):
                vanilla_over = fit(paragraphs, chain_metrics(tuple(vfiles)), box["max_w"], box["max_h"])[3]
            words = sum(len(p.split()) for p in paragraphs)
            yield dict(box=box, lang=lang, atlas=atlas, px=px, lines=lines, allowed=allowed, over=over,
                       dynamic=dynamic, words=words, vanilla_over=vanilla_over)


# A header-font box whose English or Russian text has at least this many words and wraps to 2+ lines in the pixel
# font holds paragraph text (paragraph_boxes): 5x7 capitals read badly there.
PARAGRAPH_WORDS = 8


def check_box_widths(verbose=False):
    """box_fits as messages: (problems, warnings, notes). A problem: a Russian vanilla box that fitted in the
    vanilla font and overflows in the pixel font (fix: a shorter, faithful text in a
    localisation/russian/replace/totu_<area>_short_l_russian.yml of the stream that owns the window; the fonts' own
    are in HEADER_SHORT). Warnings: such an English vanilla box (English is not touched), and every overflowing box of
    the mod's own .gui files in a pixel font in English or Russian (fix its maxWidth / maxHeight or text; a warning,
    because a box without fixedsize may simply grow). Notes (one summary line each, listed with verbose): boxes that
    overflow in the vanilla font too, overflows in LATIN_LANGUAGES (a known limitation: 12 px per character against
    Orator's ~11) and paragraph_boxes."""
    problems, warnings, notes, latin, vanilla_too = [], [], [], [], []
    fits = list(box_fits())
    for r in fits:
        if not r["over"]:
            continue
        b = r["box"]
        msg = (f"{b['file']}:{b['name']} {b['key']} ({b['font']} -> {r['atlas']}) {r['lang']}: {r['px']} px / "
               f"maxWidth {b['max_w']}, {r['lines']} line(s) / {r['allowed']}" + (" (+fields)" if r["dynamic"] else ""))
        if r["vanilla_over"]:
            vanilla_too.append("also over in vanilla: " + msg)
        elif r["lang"] in LATIN_LANGUAGES:
            latin.append("LATIN " + msg)
        elif b["mod"] and r["vanilla_over"] is None:
            warnings.append("BOX " + msg)
        elif r["lang"] == "russian":
            problems.append("HEADER " + msg + " - give the key a shorter, faithful Russian text in a "
                            "localisation/russian/replace/totu_<area>_short_l_russian.yml file you own")
        else:
            warnings.append("HEADER " + msg)
    paragraphs = [f"PARAGRAPH {b['file']}:{b['name']} {b['key']} ({b['font']}): {words} words, {lines} lines in the "
                  "pixel font - the stream owning this window should switch the box to a body font (totu_body, "
                  "hoi_18mbs) in its .gui copy" for b, words, lines in paragraph_boxes(fits)]
    # a .gui may define the same box twice (tutorialscreen.gui): one message each
    problems, warnings, vanilla_too, latin = (list(dict.fromkeys(x)) for x in (problems, warnings, vanilla_too, latin))
    for found, what in ((vanilla_too, "box texts overflow in the vanilla font too"),
                        (latin, "header box texts overflow only in the pixel font in the Latin languages (known "
                                "limitation)"),
                        (paragraphs, "header-font boxes hold paragraph text (stream TODO, see "
                                     "tools/fontcheck/README.txt)")):
        if found:
            notes += found if verbose else [f"{len(found)} {what}; --verbose lists them"]
    return problems, warnings, notes


def paragraph_boxes(fits=None):
    """[(box, words, lines)] of the visible header-font boxes (HEADER_FONTS) whose English or Russian text has
    PARAGRAPH_WORDS+ words and wraps to 2+ lines in the pixel font, one entry per box (the larger language). fits:
    box_fits() if already computed."""
    out = {}
    for r in box_fits() if fits is None else fits:
        b = r["box"]
        if b["font"] in HEADER_FONTS and r["lang"] in ("english", "russian") and r["words"] >= PARAGRAPH_WORDS \
                and r["lines"] >= 2:
            k = (b["file"], b["name"], b["key"])
            if k not in out or (r["words"], r["lines"]) > out[k][1:]:
                out[k] = (b, r["words"], r["lines"])
    return list(out.values())


def header_strings():
    """(where, text) of the vanilla strings the header fonts draw (font_files' first file totu_h36 / totu_h30 /
    totu_h24 through HEADER_FONTS): the keys of every .gui box in a header font and every state name, in
    English, Russian and LATIN_LANGUAGES, without fields. Country names are checked with the menu strings."""
    keys = sorted({b["key"] for b in gui_boxes() if b["font"] in HEADER_FONTS})
    for lang in GAME_LANGUAGES:
        loc = game_loc(lang)
        for key in keys + sorted(k for k in loc if re.fullmatch(r"STATE_\d+", k)):
            if key in loc:
                yield f"{lang} {key}", plain(loc[key])


def check_header_metrics():
    """HEADER_FONTS against the game files and interface/core.gfx: each atlas has the lineHeight / base of the
    vanilla file it replaces, and core.gfx lists the atlas first and that vanilla file second in the font and its
    Russian / Polish overrides, and keeps a Japanese override."""
    problems = []
    for font, (atlas, vanilla) in HEADER_FONTS.items():
        p = GAME / "gfx" / "fonts" / f"{vanilla}.fnt"
        if p.exists():
            common = read_fnt(p)[0]
            if (common.get("lineHeight"), common.get("base")) != tuple(FONTS[atlas][1:3]):
                problems.append(f"{atlas}: lineHeight / base {FONTS[atlas][1:3]} differ from the game's {vanilla} "
                                f"({common.get('lineHeight')}, {common.get('base')})")
        if not CORE_GFX.exists():
            continue
        entry = font_defs().get(font, {})
        want = [f"gfx/fonts/{atlas}", f"gfx/fonts/{vanilla}"]
        for lang in ("english", "russian", "polish", "german", "french", "spanish", "braz_por"):
            if font_files(font, lang) != want:
                problems.append(f"interface/core.gfx: {font} draws {font_files(font, lang)} in {lang}, "
                                f"expected {want}")
        if not entry.get("l_japanese"):
            problems.append(f"interface/core.gfx: {font} lost its l_japanese override")
    return problems

# ---------------------------------------------------------------- interface/core.gfx: the game's file + font edits
CORE_HEAD = (
    "# Twilight of the Union: copy of vanilla 1.19.3 interface/core.gfx; edited blocks marked # TotU\n"
    "# Written by python tools/build_fonts.py --core-gfx from the game's file (run it again after a game patch).\n"
    "# Edits: the header fonts hoi_36header, nsb_hoi_36header, hoi_30header, hoi_24header and nsb_hoi_24header draw\n"
    "# the broadcast pixel atlases gfx/fonts/totu_h36 / totu_h30 / totu_h24 first and their vanilla Orator\n"
    "# file second (glyph fallback; same lineHeight and base), in paper white with the colour codes P D K G R (Y H T\n"
    "# -> P); their Russian / Polish overrides draw the same atlases (Cyrillic and Polish are in them); the Japanese\n"
    "# overrides, core_chinese.gfx and core_korean.gfx stay vanilla. Global colour codes: T W -> P, g -> D, B C ->\n"
    "# light keyer blue, P D K added. Everything else, sprites included, is the vanilla file byte for byte.\n"
)
# Global text colours: (vanilla line, TotU line). Values from tools/build_menu_gfx.py: CAPTION_WHITE (P),
# CAPTION_DIM (D), and KEY_BLUE (30, 62, 168) lightened to read as text on the dark board.
CORE_COLOURS = [
    ("\t\tC = { 35 206 255 }  # Cyan\n",
     "\t\tC = { 96 128 232 }  # Cyan  # TotU: light keyer blue (vanilla 35 206 255)\n"),
    ("\t\tW = { 255 255 255 } # White\n",
     "\t\tW = { 246 242 234 } # White  # TotU: paper white P (vanilla 255 255 255)\n"),
    ("\t\tB = { 0 0 255 }     # Blue\n",
     "\t\tB = { 96 128 232 }  # Blue  # TotU: light keyer blue (vanilla 0 0 255)\n"),
    ("\t\tg = { 176 176 176 } # Grey\n",
     "\t\tg = { 172 180 196 } # Grey  # TotU: dim grey D (vanilla 176 176 176)\n"),
    ("\t\tT = { 255 255 255 } # Title\n",
     "\t\tT = { 246 242 234 } # Title  # TotU: paper white P (vanilla 255 255 255)\n"),
]
CORE_COLOURS_AFTER = "\t\tt = { 255 76 77 }\t# Gradient Step 10 - red \t\t{ 229 0 0 }\n"
CORE_COLOURS_ADD = (
    "\t\t# TotU: the broadcast palette as global codes (section-sign codes and text_color_code P / D / K in any font)\n"
    "\t\tP = { 246 242 234 } # TotU: paper white, the caption white\n"
    "\t\tD = { 172 180 196 } # TotU: dim grey, never darker\n"
    "\t\tK = { 0 0 0 }       # TotU: black, the drop edge\n"
)
HEADER_TEXTCOLORS = (
    "\t\ttextcolors = {\t# TotU: broadcast palette; vanilla G R kept, Y H T -> paper white (vanilla 238 201 35 / 255)\n"
    "\t\t\tP = { 246 242 234 }\n"
    "\t\t\tD = { 172 180 196 }\n"
    "\t\t\tK = { 0 0 0 }\n"
    "\t\t\tG = { 86 172 91 }\n"
    "\t\t\tR = { 222 86 70 }\n"
    "\t\t\tY = { 246 242 234 }\n"
    "\t\t\tH = { 246 242 234 }\n"
    "\t\t\tT = { 246 242 234 }\n"
    "\t\t}\n"
)


def _block(text, kind, name, start=0):
    """(start, end) of the next `<kind> = {` block named name at or after start: from its line to the end of the line
    of its closing brace. None if there is none."""
    m = re.compile(r"^\t" + kind + r' = \{\n\t\tname = "' + re.escape(name) + '"\n', re.M).search(text, start)
    if not m:
        return None
    depth, i = 0, text.index("{", m.start())
    while True:
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        if depth == 0:
            return m.start(), text.index("\n", i) + 1
        i += 1


def _replace_once(block, old, new, what):
    if block.count(old) != 1:
        raise ValueError(f"{what}: expected one {old.strip()!r}, found {block.count(old)}")
    return block.replace(old, new)


def core_gfx_text(vanilla):
    """interface/core.gfx of the mod from the game's file: CORE_HEAD, the global colours (CORE_COLOURS), the
    HEADER_FONTS blocks and their Russian / Polish overrides. Raises ValueError when the game's file no longer has a
    line or block these edits expect (a game patch: adapt the edits)."""
    text = vanilla
    for old, new in CORE_COLOURS:
        text = _replace_once(text, old, new, "global textcolors")
    text = _replace_once(text, CORE_COLOURS_AFTER, CORE_COLOURS_AFTER + CORE_COLOURS_ADD, "global textcolors")
    for font, (atlas, vfile) in HEADER_FONTS.items():
        span = _block(text, "bitmapfont", font)
        if not span:
            raise ValueError(f"no bitmapfont {font}")
        block = text[span[0]:span[1]]
        block = _replace_once(block, f'\t\t\t"gfx/fonts/{vfile}"\n',
                              f'\t\t\t"gfx/fonts/{atlas}"\t# TotU: broadcast pixel atlas (tools/build_fonts.py)\n'
                              f'\t\t\t"gfx/fonts/{vfile}"\t# TotU: vanilla second: any glyph the atlas lacks\n', font)
        block = _replace_once(block, "\t\tcolor = 0xffffffff\n",
                              "\t\tcolor = 0xfff6f2ea\t# TotU: paper white P (vanilla 0xffffffff)\n", font)
        m = re.search(r"\t\ttextcolors = \{\n.*?\n\t\t\}\n", block, re.S)
        if not m:
            raise ValueError(f"{font}: no textcolors")
        block = block[:m.start()] + HEADER_TEXTCOLORS + block[m.end():]
        block = "\t# TotU: broadcast pixel font (vanilla: the Orator file alone)\n" + block
        text = text[:span[0]] + block + text[span[1]:]
        pos, n = 0, 0
        while (span := _block(text, "bitmapfont_override", font, pos)) is not None:
            block = text[span[0]:span[1]]
            if '"l_russian"' in block:
                m = re.search(r"\t\tfontfiles = \{\n(.*?)\t\t\}\n", block, re.S)
                old = " + ".join(re.findall(r'"gfx/fonts/([^"]+)"', m.group(1)))
                note = "; vanilla names this block hoi_36header, meant for nsb_hoi_36header" if n else ""
                block = (block[:m.start()] + f"\t\tfontfiles = {{\t# TotU: the atlas has Cyrillic and Polish (vanilla "
                         f'{old}){note}\n\t\t\t"gfx/fonts/{atlas}"\n\t\t\t"gfx/fonts/{vfile}"\n\t\t}}\n' + block[m.end():])
                text = text[:span[0]] + block + text[span[1]:]
                n += 1
            pos = span[0] + len(block)
        if font != "nsb_hoi_36header" and not n:
            raise ValueError(f"{font}: no l_russian override")
    return CORE_HEAD + text


def write_core_gfx():
    """--core-gfx: interface/core.gfx from the game's file (UTF-8 as the game's, no BOM, LF), then the changed lines."""
    vanilla = (GAME / "interface" / "core.gfx").read_bytes().decode("utf-8")
    text = core_gfx_text(vanilla)
    CORE_GFX.write_bytes(text.encode("utf-8"))
    print("wrote interface/core.gfx")
    import difflib
    ops = difflib.SequenceMatcher(None, vanilla.splitlines(), text.splitlines(), autojunk=False).get_opcodes()
    for tag, a0, a1, b0, b1 in ops:
        if tag != "equal":
            print(f"  {tag:8s} game lines {a0 + 1}-{a1} -> mod lines {b0 + 1}-{b1}")


def check_core_gfx():
    """(problems, warnings) of interface/core.gfx: missing, or different from core_gfx_text of the game's file (a game
    patch or a hand edit: run --core-gfx, then re-apply any hand edit)."""
    van = GAME / "interface" / "core.gfx"
    if not CORE_GFX_ENABLED:
        return ([], ["interface/core.gfx exists although CORE_GFX_ENABLED is False: delete it"]) if CORE_GFX.exists() else ([], [])
    if not CORE_GFX.exists():
        return ["interface/core.gfx is missing: run python tools/build_fonts.py --core-gfx"], []
    if not van.exists():
        return [], []
    try:
        want = core_gfx_text(van.read_bytes().decode("utf-8"))
    except ValueError as e:
        return [], [f"interface/core.gfx: the game's file changed ({e}); adapt core_gfx_text and run --core-gfx"]
    if CORE_GFX.read_bytes() != want.encode("utf-8"):
        return [], ["interface/core.gfx differs from the game's file + the font edits (game patch or hand edit): "
                    "python tools/build_fonts.py --core-gfx rewrites it"]
    return [], []


# ---------------------------------------------------------------- texts for the other game languages
# The mod is written in English and Russian. The menu buttons used vanilla keys translated into every game language;
# their TOTU_* caption replacements, the bookmark name and the scenario / country texts get the English text in the
# other languages (TEXT_KEY: drawn in vanilla fonts, so not glyph-checked).
FALLBACK_LANGUAGES = ["braz_por", "french", "german", "japanese", "korean", "polish", "simp_chinese", "spanish"]
# Country name keys the game looks up: <TAG>, <TAG>_<ideology group> (the four groups of the mod), each with _DEF / _ADJ
USED_NAME = re.compile(r"^[A-Z][A-Z0-9]{2}(?:_(?:democratic|communism|fascism|neutrality))?(?:_DEF|_ADJ)?$")


@lru_cache(maxsize=None)
def vanilla_keys(lang):
    """Every key of the game's localisation in one language (empty without the game folder)."""
    keys = set()
    for f in (GAME / "localisation" / lang).rglob("*.yml") if GAME.exists() else []:
        for line in f.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            m = re.match(r"^\s*([\w.\-]+):\d*\s", line)
            if m:
                keys.add(m.group(1))
    return keys


def fallback_loc():
    """{path: file text} of the generated localisation, for every game language without a translation of the mod
    (FALLBACK_LANGUAGES), from the English files:
      totu_menu_captions_l_<lang>.yml   the caption keys, TOTU_TXT_ keys and scenario / country texts of every English
                                        caption file (menu_files: totu_menu_l_english.yml and the per-area
                                        totu_menu*_l_ files), and their other keys where the game has none
      loading_tips_l_<lang>.yml         the 25 hand-set quotes; same file name as the vanilla file, so it replaces the
                                        163 gameplay tips of 1936 (the loading screen draws them in the pixel font)
      totu_countries_new_l_<lang>.yml   the country names the game has no key for in that language (the tags the
                                        mod adds: BRB, COM, KIR, ...), so they do not show as raw keys. Only the keys
                                        the game looks up (USED_NAME); the English file also has unused sub-ideology
                                        names. Only with the game folder (else nothing is known to be missing)
    The text has no BOM; the files are written UTF-8 with BOM, LF (write_fallback_loc). Writes nothing."""
    sources = [(src, [(m.group(1), line) for line in src.read_text(encoding="utf-8-sig").splitlines()
                      for m in [LOC_LINE.match(line)] if m]) for src in menu_files("english")]
    tips_src = ROOT / "localisation" / "english" / "loading_tips_l_english.yml"
    tips = [line for line in tips_src.read_text(encoding="utf-8-sig").splitlines() if TIP_KEY.match(line)]
    names_src = ROOT / "localisation" / "english" / "replace" / "totu_countries_l_english.yml"
    names = [(m.group(1), line) for line in names_src.read_text(encoding="utf-8-sig").splitlines()
             for m in [re.match(r"^\s*([\w.\-]+):\d*\s", line)] if m]

    def text(path, source, what, body):
        head = [f"l_{path.parent.name}:", f" # Generated by tools/build_fonts.py from {source}: {what}.",
                " # Edit the English file."]
        return "\n".join(head + body) + "\n"

    out = {}
    for lang in FALLBACK_LANGUAGES:
        loc = ROOT / "localisation" / lang
        known = vanilla_keys(lang)
        lines = []
        for src, entries in sources:        # caption and text keys always, other keys where the game has none
            keep = [line for key, line in entries if MENU_KEY.match(line) or TEXT_KEY.match(line) or key not in known]
            if keep:
                lines += [f" # {src.relative_to(ROOT).as_posix()}"] + keep
        path = loc / f"totu_menu_captions_l_{lang}.yml"
        out[path] = text(path, "localisation/english/totu_menu*_l_english.yml", "the menu captions, the scenario "
                         "texts and the mod's other keys of those files in English (the caption fonts have Latin and "
                         "Cyrillic only)", lines)
        path = loc / f"loading_tips_l_{lang}.yml"
        out[path] = text(path, tips_src.relative_to(ROOT).as_posix(), "the loading screen quotes in English, "
                         "replacing the vanilla gameplay tips", tips)
        body = [line for key, line in names if key not in known and USED_NAME.match(key)] if known else []
        if body:
            path = loc / f"totu_countries_new_l_{lang}.yml"
            out[path] = text(path, names_src.relative_to(ROOT).as_posix(), "English names for the keys the game has "
                             "none for in this language (countries the mod adds)", body)
    return out


def write_fallback_loc():
    """Writes fallback_loc (UTF-8 with BOM, LF): the full build and --loc."""
    files = fallback_loc()
    for path, text in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(BOM + text.encode("utf-8"))
    keys = max(sum(1 for line in t.splitlines()[1:] if LOC_LINE.match(line)) for p, t in files.items()
               if p.name.startswith("totu_menu_captions_"))
    print(f"wrote {len(files)} generated localisation files for {len(FALLBACK_LANGUAGES)} languages "
          f"(up to {keys} keys in totu_menu_captions_l_<lang>.yml): localisation/<lang>/")


def check_fallback_loc():
    """The generated localisation files against fallback_loc: missing or different = stale (a key was added or changed
    in an English caption file, the loading tips or the country names): run python tools/build_fonts.py --loc. Only
    with the game folder (the files depend on its keys)."""
    if not GAME.exists():
        return []
    stale = [rel(p) for p, text in fallback_loc().items()
             if not p.exists() or p.read_bytes() != BOM + text.encode("utf-8")]
    if not stale:
        return []
    return [f"generated localisation is stale ({len(stale)} files, e.g. {', '.join(stale[:3])}): run python "
            "tools/build_fonts.py --loc"]


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


def load_game_font(files):
    """A fontfiles chain of the game folder as (common, chars), each char with its own atlas, the earlier file winning
    per glyph (as the engine merges them). None if the game folder is missing."""
    common, chars = None, {}
    for fn in files:
        p = GAME / f"{fn}.fnt"
        if not p.exists():
            continue
        c, ch = read_fnt(p)
        atlas = Image.open(p.with_suffix(".dds")).convert("RGBA")
        common = common or c
        for cp, v in ch.items():
            chars.setdefault(cp, dict(v, atlas=atlas))
    return (common, chars) if common else None


def draw_game_text(img, font, text, x, y, colour):
    """draw_text for load_game_font fonts; characters the chain lacks are skipped."""
    for ch in text:
        c = font[1].get(ord(ch))
        if c is None:
            continue
        tile = c["atlas"].crop((c["x"], c["y"], c["x"] + c["width"], c["y"] + c["height"]))
        img.alpha_composite(ImageChops.multiply(tile, Image.new("RGBA", tile.size, colour + (255,))),
                            (x + c["xoffset"], y + c["yoffset"]))
        x += c["xadvance"]
    return x


# ---------------------------------------------------------------- previews
BG = (18, 22, 30)
BG_LIGHT = (112, 116, 128)
BOARD = (9, 11, 16)             # the broadcast board (tools/build_menu_gfx.py CS_BOARD_RGB)
KEY_BLUE = (30, 62, 168)        # hover plate of the menu buttons
DIM = (172, 180, 196)           # textcolor D: the engine version line
PAPER = (246, 242, 234)         # textcolor P
# Sample titles of tools/preview/font_headers.png (with the real in-game titles of header_samples)
HEADER_SAMPLES = {
    "russian": ["ПОЛИТИКА", "Исследования", "Производство", "Политическая власть", "Военный штаб: ёмкость, приём"],
    "latin": ["ÉTAT-MAJOR", "ÜBERSICHT", "ŁÓDŹ", "Åland, Øresund 0, Đakovo, Þórshöfn", "Ça Şa Ţara Ąę Őű Čšž Ğİ Ů",
              "Ñãõ Âêî Èà Ėā Ýÿ ½ ¼ × º ª − ´", "Zażółć gęślą jaźń"],
}


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
    W, H = 2300, 5600                           # cropped to the content at the end
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
    shown = 0
    for where, text in menu_strings(names=False):
        if "TOTU_FE_" in where or "LOADING_TIP_" in where or where.split()[0] not in ("english", "russian", "fixed"):
            continue                            # shown above / below; vanilla strings in English and Russian only
        if shown == 90:
            break
        if len(text) > 130:
            text = text[:127] + "..."
        draw_text(img, small, text, x0, y)
        y += 22
        shown += 1
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


def header_samples(font, lang, count):
    """Up to count in-game texts of vanilla .gui boxes in a header font (first box of each key), shown in lang."""
    loc, out = game_loc(lang), []
    for b in gui_boxes():
        if b["font"] == font and not b["mod"] and b["key"] in loc:
            text = " ".join(loc_paragraphs(b["key"], loc)[0]).strip()
            if text and text not in out and len(text) <= 40:
                out.append(text)
        if len(out) == count:
            break
    return out


def render_header_preview():
    """tools/preview/font_headers.png: the three in-game header fonts on the broadcast board, sample titles and real
    in-game titles in Russian and English / Latin languages, each line box marked (hairlines at the line top and the
    baseline) with the vanilla font of that language beside it for metrics, then the totu_h36 lines blown up 3x."""
    small = load_font("totu_caption_small")
    W = 2100
    img = Image.new("RGBA", (W, 5200), BOARD + (255,))
    d = ImageDraw.Draw(img)
    x0, xv, y = 48, 1100, 32
    zoom_rows = []
    for font, (atlas, vfile) in (("hoi_36header", HEADER_FONTS["hoi_36header"]),
                                 ("hoi_30header", HEADER_FONTS["hoi_30header"]),
                                 ("hoi_24header", HEADER_FONTS["hoi_24header"])):
        pix = load_font(atlas)
        cell, line_height, base, _ = FONTS[atlas]
        cx, cy = cell_xy(cell)
        draw_text(img, small, f"{font.upper()} -> {atlas.upper()}: {cx}X{cy} PX CELLS, ADVANCE {6 * cx}, LINE "
                              f"{line_height}, BASE {base}, K EDGE BAKED.  RIGHT: VANILLA FONT OF THE LANGUAGE", x0, y,
                  DIM)
        y += 30
        for lang, texts in (("russian", HEADER_SAMPLES["russian"] + header_samples(font, "russian", 6)),
                            ("english", HEADER_SAMPLES["latin"] + header_samples(font, "english", 4))):
            van = load_game_font(tuple(font_files(font, lang, game_only=True) or ()))
            block_top = y
            for i, text in enumerate(texts):
                if i == 2:                       # one line on a light band: the K edge over a bright picture
                    d.rectangle((0, y, W, y + line_height - 1), fill=BG_LIGHT + (255,))
                for yy in (y, y + base):
                    d.line((x0 - 16, yy, x0 - 6, yy), fill=DIM + (255,))
                    d.line((xv - 16, yy, xv - 6, yy), fill=DIM + (255,))
                draw_text(img, pix, text, x0, y, PAPER)
                if van:
                    draw_game_text(img, van, text, xv, y, (255, 255, 255))
                y += line_height
            if atlas in MARK_TABLES:
                zoom_rows.append(img.crop((x0 - 20, block_top, x0 + 600, block_top + 7 * line_height)))
            y += 16
        y += 24

    draw_text(img, small, "TOTU_H36, THEN TOTU_H24 X3 (NEAREST): RUSSIAN SAMPLES, THEN THE ACCENT MARKS", x0, y, DIM)
    y += 30
    for crop in zoom_rows:
        z = crop.resize((crop.width * 3, crop.height * 3), Image.NEAREST)
        img.alpha_composite(z, (x0, y))
        y += z.height + 12
    HEADER_PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    img.crop((0, 0, W, y)).convert("RGB").save(HEADER_PREVIEW)
    print("wrote", HEADER_PREVIEW.relative_to(ROOT))


# ---------------------------------------------------------------- main
def say(msg):
    """Prints ASCII only (a non-UTF-8 Windows console cannot print Cyrillic)."""
    print(msg.encode("ascii", "backslashreplace").decode("ascii"))


def char_list(chars):
    return ", ".join(f"U+{ord(c):04X} {unicodedata.name(c, '?')}" for c in chars)


def main():
    args = set(sys.argv[1:])
    unknown = args - {"--check", "--loc", "--core-gfx", "--verbose"}
    if unknown or len(args & {"--check", "--loc", "--core-gfx"}) > 1:
        raise SystemExit(f"arguments {sorted(args)}: use one of --check, --loc, --core-gfx, plus --verbose")
    if "--core-gfx" in args:
        write_core_gfx()
        return
    check, loc_only, verbose = "--check" in args, "--loc" in args, "--verbose" in args
    for ch in "AW0":        # the generalised glyph renderer must match the logo's one
        assert ImageChops.difference(glyph_mask(PIXEL_FONT[ch], 4), pixel_text_mask([ch], 4, line_gap=0)).getbbox() \
            is None, f"glyph_mask differs from pixel_text_mask on {ch}"
    problems, warnings, notes = [], [], []
    problems += check_layouts()
    if not check and not loc_only:
        for name, (cell, line_height, base, shadow) in FONTS.items():
            build_font(name, cell, line_height, base, shadow)
    problems += check_atlases()

    # glyphs: every caption string in every pixel font (the fonts share their code points, so a gap shows once with
    # the fonts it is in), the header strings in the header atlases
    gaps = {}
    strings = list(menu_strings())
    for name in FONTS:
        for where, chars in missing_glyphs(name, strings).items():
            gaps.setdefault((where, tuple(chars)), []).append(name)
    for (where, chars), names in gaps.items():
        hint = " (text drawn in a vanilla font? name the key TOTU_TXT_*)" if " TOTU_" in where else ""
        problems.append(f"MISSING in {'all fonts' if len(names) == len(FONTS) else ', '.join(names)}: {where}: "
                        f"{char_list(chars)}{hint}")
    header = list(header_strings())
    for atlas in sorted({a for a, _ in HEADER_FONTS.values()}):
        by_char = {}
        for where, chars in missing_glyphs(atlas, header).items():
            for c in chars:
                by_char.setdefault(c, []).append(where)
        for c, wheres in sorted(by_char.items()):
            problems.append(f"MISSING in header font {atlas}: {char_list(c)} in {len(wheres)} vanilla strings "
                            f"(e.g. {', '.join(wheres[:3])})")
    say(f"glyph check: {len(strings)} caption strings, {len(header)} header strings")

    problems += check_menu_loc()
    problems += check_mod_loc()
    problems += fontcheck_problems()
    problems += ["LOADING TIP: " + p for p in check_loading_tips()]
    problems += check_header_metrics()
    problems += check_font_files()
    p, w = check_core_gfx()
    problems, warnings = problems + p, warnings + w
    p, w, n = check_box_widths(verbose)
    problems, warnings, notes = problems + p, warnings + w, notes + n

    if not check:
        write_fallback_loc()
    if not check and not loc_only:
        render_preview()
        render_header_preview()
    problems += check_fallback_loc()
    for msg in notes:
        say("NOTE " + msg)
    for msg in warnings:
        say("WARN " + msg)
    for msg in problems:
        say("PROBLEM " + msg)
    say(f"{'check' if check else 'loc' if loc_only else 'build'}: {len(problems)} problems, {len(warnings)} warnings"
        + (" - nothing written" if check else " - only the generated localisation written" if loc_only else ""))
    if problems:
        sys.exit(1)


if __name__ == "__main__":
    main()
