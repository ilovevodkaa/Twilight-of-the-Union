"""Renders the README art into docs/images/readme/ in the frontend's "broadcast" style: the menu's dusk photo, the
pixel logo, the caption fonts of gfx/fonts, the keyer-blue caption plate with its hard two-step tail, soft black
scrims. No frames, brackets, stamps or other ornaments.

Usage:
    python tools/render_readme.py --shots DIR            # everything
    python tools/render_readme.py --only hero,headers    # some parts (hero, headers, gallery, flags, spirits, stats)

Outputs (docs/images/readme/):
    hero.jpg              1600x640 banner: the menu background (build_background of tools/src/red_square.webp on a
                          wider canvas, HERO_*), the menu logo (gfx/interface/totu/menu_logo.dds) and a lower third:
                          the Russian title on the keyer plate, the start date under it
    header_<key>.png      1600x96 section headers, transparent (read on GitHub's light and dark theme): a caption
                          plate at x 0, 6 px cells (HEADERS)
    shot_<name>.jpg       gallery crops of in-game screenshots (GALLERY) and the loading screen composite
    flags.png             the 1990 flags of all COUNTRIES (tools/world1990/countries.py) as a wall of monitors, the
                          USSR on the 2x2 screen in the middle, no labels
    spirits.png           the Soviet starting spirits (history order; icons from tools/src/icons/idea) with their
                          Russian names in totu_caption_small
    stats.png, stats_en   big numbers in the logo's finish, counted from the repository (history, localisation)

The gallery reads clean 3440x1440 screenshots (UI scale 1.0) from --shots: menu_full.png, scenario_full.png,
country_full.png, lobby_full.png, politics_full.png. The crops in GALLERY keep out the overlays a capture can carry
(Steam's ownership popup bottom right, Discord top left, NVIDIA top right); look at every image before publishing.

Text is drawn from the built atlases (run tools/build_fonts.py first): totu_caption (4 px cells) as is, larger
cells as an integer nearest-neighbour blow-up of totu_caption_small (6 px = x3) or totu_caption (8 px = x2), so the
glyphs keep their square cells. Flags come from gfx/flags of the mod, then of the game (env HOI4_DIR, default
D:/steam/.../Hearts of Iron IV), looked up like the engine: <TAG>_<ruling ideology>, then <TAG>.
Requires Pillow and numpy (pip install pillow numpy).
"""
import argparse
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_menu_gfx as bmg  # noqa: E402
from build_fonts import load_font  # noqa: E402
from world1990.countries import COUNTRIES  # noqa: E402

ROOT = bmg.ROOT
OUT = ROOT / "docs" / "images" / "readme"
GAME = bmg.GAME

WHITE = bmg.CAPTION_WHITE           # colour P: caption white = logo glyph white
DIM = bmg.CAPTION_DIM               # colour D
KEY = bmg.KEY_BLUE                  # the one accent
BLACK_BG = bmg.CS_BOARD_RGB         # the backgrounds' cold lifted black
JPG_Q = 88

# Section headers: key -> caption. Russian first; one header for the English section.
HEADERS = {
    "about": "О моде",
    "map": "Карта 1990",
    "screens": "Экраны",
    "spirits": "Нацдухи",
    "flags": "Флаги 1990",
    "install": "Установка",
    "dev": "Разработка",
    "plans": "Планы",
    "sources": "Источники",
    "english": "English",
}

# Gallery: output name -> (screenshot in --shots, crop box in screenshot px, output size). None = the loading screen
# composite of build_menu_gfx.build_loading_preview (the built textures and fonts, 2560x1440).
GALLERY = {
    "menu": ("menu_full.png", (120, 0, 2680, 1440), (1600, 900)),          # 16:9, left of the Steam popup
    "scenario": ("scenario_full.png", (0, 0, 3440, 1440), (1600, 670)),     # 21:9: logo and inset both
    "country": ("country_full.png", (920, 288, 2520, 1188), (1600, 900)),   # 1:1 around the window
    "lobby": ("lobby_full.png", (0, 0, 3440, 1440), (1600, 670)),           # 21:9: the 1990 map of Europe
    "politics": ("politics_full.png", (0, 134, 1600, 1034), (1600, 900)),   # 1:1, below the flag tooltip
    "loading": (None, (0, 0, 2560, 1440), (1600, 900)),
}


# ---------------------------------------------------------------- text and plates
_FONTS = {}


def font(cell):
    """(atlas font, scale) for a caption at cell px per font cell: totu_caption for multiples of 4, else
    totu_caption_small blown up."""
    if not _FONTS:
        if not (ROOT / "gfx/fonts/totu_caption.fnt").exists():
            raise SystemExit("run tools/build_fonts.py first: gfx/fonts/totu_caption.fnt is missing")
        _FONTS[4], _FONTS[2] = load_font("totu_caption"), load_font("totu_caption_small")
    if cell % 4 == 0:
        return _FONTS[4], cell // 4
    assert cell % 2 == 0, "caption cells are even"
    return _FONTS[2], cell // 2


def text_w(text, cell):
    """Ink width of one line: 6 cells per glyph, no trailing gap (the wide № is not used here)."""
    return len(text) * 6 * cell - cell


def draw_text(img, text, x, y, cell, colour=WHITE, edge=True):
    """One caption line, capitals' top at y, from x; edge: the menu's black drop copy at +cell/2 (2 px at 4 px cells).
    Glyph tiles come from the atlas, tinted like the engine does, blown up nearest-neighbour."""
    f, k = font(cell)
    _, chars, atlas = f
    passes = ((cell // 2, (0, 0, 0)), (0, colour)) if edge else ((0, colour),)
    for d, col in passes:
        px = x + d
        for ch in text.upper():
            c = chars[ord(ch)]
            tile = atlas.crop((c["x"], c["y"], c["x"] + c["width"], c["y"] + c["height"]))
            tile = ImageChops.multiply(tile, Image.new("RGBA", tile.size, col + (255,)))
            if k > 1:
                tile = tile.resize((tile.width * k, tile.height * k), Image.NEAREST)
            img.alpha_composite(tile, (px + c["xoffset"] * k, y + d + c["yoffset"] * k))
            px += c["xadvance"] * k


def plate_geometry(text, cell):
    """The menu's caption plate scaled to cell (4 px = the menu): height, text inset, solid width, tail steps."""
    k = cell / 4
    h, pad_l, pad_r, step = round(bmg.PLATE_H * k), round(bmg.PAD_L * k), round(bmg.PAD_R * k), round(bmg.TAIL / 2 * k)
    return h, pad_l, pad_l + text_w(text, cell) + pad_r, (step, step)


def caption_plate(img, text, x, y, cell):
    """Keyer-blue plate with its hard two-step tail at (x, y) and the caption on it, capitals centred in the plate.
    Returns the plate's full width."""
    h, pad_l, solid, steps = plate_geometry(text, cell)
    img.alpha_composite(bmg.keyer_strip(solid, h, KEY, steps), (x, y))
    draw_text(img, text, x + pad_l, y + (h - 7 * cell) // 2, cell)
    return solid + sum(steps)


GLOW_PAD = 72                       # margin of glow_text: wide enough that the 22 px bloom is not clipped on flat black


def glow_text(lines, cell):
    """Text in the logo's finish (build_menu_gfx.build_logo: dark halo, warm and white bloom, chromatic fringe,
    scanlined glyphs), any lines of the 5x7 face, GLOW_PAD px margin."""
    saved = bmg.LOGO_LINES, bmg.LOGO_CELL, bmg.LOGO_PAD
    bmg.LOGO_LINES, bmg.LOGO_CELL, bmg.LOGO_PAD = lines, cell, GLOW_PAD
    try:
        return bmg.build_logo()
    finally:
        bmg.LOGO_LINES, bmg.LOGO_CELL, bmg.LOGO_PAD = saved


def add_grain(img, sigma=2.2, seed=1990):
    """The backgrounds' fine luma grain (RGB in, RGB out)."""
    a = np.asarray(img.convert("RGB"), np.float32)
    n = np.random.default_rng(seed).normal(0, sigma, a.shape[:2] + (1,)).astype(np.float32)
    return Image.fromarray(np.clip(a + n, 0, 255).astype(np.uint8))


def dark_canvas(w, h):
    return Image.new("RGBA", (w, h), BLACK_BG + (255,))


def save(img, name):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    if path.suffix == ".jpg":
        img.convert("RGB").save(path, quality=JPG_Q, optimize=True, progressive=True, subsampling=0)
    else:
        img.save(path, optimize=True)
    print(f"wrote {path.relative_to(ROOT).as_posix()} {img.size[0]}x{img.size[1]} {path.stat().st_size // 1024} KB")


# ---------------------------------------------------------------- hero
HERO = (1600, 640)
# The hero's text is ~1.6x larger against the photo than the menu's at 2560x1440, so the menu texture would put St
# Basil's under the logo and the lower third. The background is built like the menu's (build_background) on a wider
# canvas instead: the photo centred on HERO_CANVAS px, its sides continued by extend_photo, softened and darkened
# toward the canvas edge. The hero shows columns HERO_COLS and the menu's 21:9 rows HERO_ROWS of it: St Basil's starts
# right of the text block, the Spasskaya tower stays in frame, the text sits on the soft kinescope edge.
HERO_CANVAS = 2700
HERO_COLS = (0, 2000)
HERO_ROWS = (318, 1118)
HERO_X, HERO_Y = 96, 72             # logo glyphs' top-left (the title-safe corner)
HERO_PLATE = ("Сумерки Союза", 6)   # the Russian title on the plate, 6 px cells: as wide as the logo
HERO_DATE = ("1 января 1990", 4)    # the lower third's second line, under the plate
HERO_BOTTOM = 64                    # date capitals end this far above the bottom edge
HERO_LINE_GAP = 18                  # plate bottom -> date capitals


def paste_clipped(img, layer, x, y):
    """alpha_composite that accepts negative positions (the scrims reach past the frame)."""
    img.alpha_composite(layer.crop((max(0, -x), max(0, -y), layer.width, layer.height)), (max(0, x), max(0, y)))


def hero():
    """The menu's frame on a wide strip: the logo at the title-safe corner on the title scrim; a lower third at the
    same edge on the menu scrim: the Russian title on the keyer plate and the date under it."""
    w, h = HERO
    saved = bmg.BG_W
    bmg.BG_W = HERO_CANVAS
    try:
        tex = bmg.build_background(bmg.SRC / "red_square.webp")
    finally:
        bmg.BG_W = saved
    bg = tex.crop((HERO_COLS[0], HERO_ROWS[0], HERO_COLS[1], HERO_ROWS[1])).resize((w, h), Image.LANCZOS)
    # the menu's kinescope fall-off (at most 28 % over 300 texture px) on the right edge too, which is inside the canvas
    s = w / (HERO_COLS[1] - HERO_COLS[0])
    d = (w - 1 - np.arange(w, dtype=np.float32)) / (300 * s)
    fall = 1 - 0.28 * (1 - np.clip(d, 0, 1)) ** 2
    bg = Image.fromarray(np.clip(np.asarray(bg, np.float32) * fall[None, :, None], 0, 255).astype(np.uint8))
    bg = bg.convert("RGBA")
    logo = Image.open(ROOT / "gfx/interface/totu/menu_logo.dds").convert("RGBA")
    # the title scrim placed against the logo as in frontendmainview.gui (logo glyphs at SAFE_X, SAFE_Y); the menu
    # scrim at the menu's x, centred on the lower third
    paste_clipped(bg, bmg.build_scrim(*bmg.SCRIM_TITLE), bmg.SCRIM_TITLE_POS[0] - bmg.SAFE_X + HERO_X,
                  bmg.SCRIM_TITLE_POS[1] - bmg.SAFE_Y + HERO_Y)
    text, cell = HERO_PLATE
    date, dcell = HERO_DATE
    ph, pad_l = plate_geometry(text, cell)[:2]
    date_y = h - HERO_BOTTOM - 7 * dcell
    plate_y = date_y - HERO_LINE_GAP - ph
    scrim = bmg.build_scrim(*bmg.SCRIM_MENU)
    paste_clipped(bg, scrim, HERO_X - bmg.SAFE_X + bmg.SCRIM_MENU_POS[0],
                  (plate_y + date_y + 7 * dcell) // 2 - scrim.height // 2)
    paste_clipped(bg, logo, HERO_X - bmg.LOGO_PAD, HERO_Y - bmg.LOGO_PAD)
    caption_plate(bg, text, HERO_X - pad_l, plate_y, cell)
    draw_text(bg, date, HERO_X, date_y, dcell)
    save(bg.convert("RGB"), "hero.jpg")


# ---------------------------------------------------------------- section headers
HEADER = (1600, 96)
HEADER_CELL = 6


def headers():
    for key, text in HEADERS.items():
        img = Image.new("RGBA", HEADER, (0, 0, 0, 0))
        ph = plate_geometry(text, HEADER_CELL)[0]
        caption_plate(img, text, 0, (HEADER[1] - ph) // 2, HEADER_CELL)
        save(img, f"header_{key}.png")


# ---------------------------------------------------------------- gallery
def gallery(shots):
    for name, (src, box, size) in GALLERY.items():
        if src is None:
            img = bmg.build_loading_preview().convert("RGB")
        else:
            path = Path(shots) / src if shots else None
            if not path or not path.exists():
                print(f"gallery {name}: no {src} in --shots, skipped")
                continue
            img = Image.open(path).convert("RGB")
            assert img.size == (3440, 1440), f"{src}: {img.size}, the crops are set for 3440x1440"
        img = img.crop(box)
        if img.size != size:
            img = img.resize(size, Image.LANCZOS)
        save(img, f"shot_{name}.jpg")


# ---------------------------------------------------------------- flags
FLAG_COLS, FLAG_ROWS = 20, 8
FLAG_W, FLAG_H, FLAG_GAP, FLAG_MARGIN = 72, 46, 6, 23
FLAG_BIG = ("SOV", 9, 3)            # tag, column, row of the 2x2 monitor (the centre of the wall)


def ruling(tag):
    path = next((ROOT / "history/countries").glob(f"{tag} - *.txt"))
    return re.search(r"ruling_party\s*=\s*(\w+)", path.read_text(encoding="utf-8-sig")).group(1)


def flag_file(tag):
    """The flag the engine shows in 1990: <TAG>_<ruling ideology>, then <TAG>; the mod's file over the game's."""
    for name in (f"{tag}_{ruling(tag)}", tag):
        for base in (ROOT / "gfx/flags", GAME / "gfx/flags"):
            if (base / f"{name}.tga").exists():
                return base / f"{name}.tga"
    raise SystemExit(f"no flag for {tag} (game folder: {GAME}, set HOI4_DIR)")


def flags():
    """FLAG_COLS x FLAG_ROWS screens on black, COUNTRIES in their order (by region) row by row around the 2x2 screen
    of FLAG_BIG: 156 + 4 cells for the 157 countries."""
    big_tag, bc, br = FLAG_BIG
    cells = [(c, r) for r in range(FLAG_ROWS) for c in range(FLAG_COLS)
             if not (bc <= c < bc + 2 and br <= r < br + 2)]
    tags = [t for t in COUNTRIES if t != big_tag]
    assert len(cells) == len(tags), f"{len(tags)} flags for {len(cells)} cells"
    w = FLAG_COLS * FLAG_W + (FLAG_COLS - 1) * FLAG_GAP + 2 * FLAG_MARGIN
    h = FLAG_ROWS * FLAG_H + (FLAG_ROWS - 1) * FLAG_GAP + 2 * FLAG_MARGIN
    screens = Image.new("RGBA", (w, h), (0, 0, 0, 0))

    def put(tag, c, r, span=1):
        fw, fh = span * FLAG_W + (span - 1) * FLAG_GAP, span * FLAG_H + (span - 1) * FLAG_GAP
        img = Image.open(flag_file(tag)).convert("RGB").resize((fw, fh), Image.LANCZOS)
        screens.paste(screen(img), (FLAG_MARGIN + c * (FLAG_W + FLAG_GAP), FLAG_MARGIN + r * (FLAG_H + FLAG_GAP)))

    for tag, (c, r) in zip(tags, cells):
        put(tag, c, r)
    put(big_tag, bc, br, 2)
    # the wall in a dark studio: the screens' light spills into the gaps, the wall falls off toward its ends
    out = dark_canvas(w, h)
    spill = screens.filter(ImageFilter.GaussianBlur(9))
    spill.putalpha(spill.getchannel("A").point(lambda v: v * 0.45))
    out.alpha_composite(spill)
    out.alpha_composite(screens)
    a = np.asarray(out.convert("RGB"), np.float32)
    x = np.abs(np.arange(w, dtype=np.float32) / (w - 1) * 2 - 1)
    y = np.abs(np.arange(h, dtype=np.float32) / (h - 1) * 2 - 1)
    fall = 1 - 0.30 * np.clip(x[None, :] ** 2 * 0.8 + y[:, None] ** 2 * 0.35, 0, 1)
    save(add_grain(Image.fromarray(np.clip(a * fall[..., None], 0, 255).astype(np.uint8)), 2.0), "flags.png")


def screen(img):
    """A flag as a lit picture tube: a touch below full white, a soft fall-off toward the corners."""
    a = np.asarray(img, np.float32) * 0.93
    h, w = a.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt(((xx + 0.5) / w * 2 - 1) ** 2 + ((yy + 0.5) / h * 2 - 1) ** 2) / np.sqrt(2)
    a *= (1 - 0.22 * np.clip((r - 0.45) / 0.55, 0, 1) ** 2)[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


# ---------------------------------------------------------------- spirits
SPIRITS_W = 1360                    # 7 columns of 185 px: names of up to 15 characters per line
SPIRIT_ICON = 148
SPIRIT_CELL = 2


def spirit_keys():
    """Starting spirits of the USSR in the order of its history file."""
    text = next((ROOT / "history/countries").glob("SOV - *.txt")).read_text(encoding="utf-8-sig")
    return re.findall(r"^\s*(TOTU_SOV_\w+)\s*$", text, re.M)


def wrap(text, max_chars):
    """Fewest lines of at most max_chars, then the most even ones (НИ ПЛАНА, / НИ РЫНКА, not НИ ПЛАНА, НИ / РЫНКА)."""
    words = text.split()
    best = None
    for mask in range(1 << (len(words) - 1)):           # a break after word i where bit i is set
        lines, cur = [], [words[0]]
        for i, word in enumerate(words[1:]):
            if mask >> i & 1:
                lines.append(" ".join(cur))
                cur = [word]
            else:
                cur.append(word)
        lines.append(" ".join(cur))
        longest = max(len(line) for line in lines)
        if longest <= max_chars and (best is None or (len(lines), longest) < (len(best), max(map(len, best)))):
            best = lines
    assert best, f"{text!r}: a word is longer than {max_chars} characters"
    return best


def spirits():
    keys = spirit_keys()
    pictures = dict(re.findall(r"(TOTU_SOV_\w+)\s*=\s*\{\s*picture\s*=\s*(\w+)",
                               (ROOT / "common/ideas/TOTU_SOV.txt").read_text(encoding="utf-8")))
    n = len(keys)
    margin = 32
    col = (SPIRITS_W - 2 * margin) // n
    max_chars = (col - 4) // (6 * SPIRIT_CELL)
    names = [wrap(bmg.loc_value("russian", k), max_chars) for k in keys]
    top, gap, line_h = 40, 22, 9 * SPIRIT_CELL + 4
    h = top + SPIRIT_ICON + gap + max(len(l) for l in names) * line_h + 36
    img = dark_canvas(SPIRITS_W, h)
    for i, (key, lines) in enumerate(zip(keys, names)):
        cx = margin + col * i + col // 2
        icon = Image.open(ROOT / "tools/src/icons/idea" / f"{pictures[key]}.png").convert("RGBA")
        icon = icon.resize((SPIRIT_ICON, SPIRIT_ICON), Image.LANCZOS)
        img.alpha_composite(icon, (cx - SPIRIT_ICON // 2, top))
        for j, line in enumerate(lines):
            draw_text(img, line, cx - text_w(line, SPIRIT_CELL) // 2, top + SPIRIT_ICON + gap + j * line_h,
                      SPIRIT_CELL)
    save(add_grain(img, 1.6), "spirits.png")


# ---------------------------------------------------------------- stats
STATS_W = 1600
STAT_CELL, LABEL_CELL = 10, 4


def stats_numbers(lang):
    """(big number, label) counted from the repository: start year, countries (history/countries, = COUNTRIES),
    states (history/states), loading screen quotes, languages the mod is written in."""
    states = len(list((ROOT / "history/states").glob("*.txt")))
    countries = len(list((ROOT / "history/countries").glob("*.txt")))
    assert countries == len(COUNTRIES), f"{countries} country files, {len(COUNTRIES)} COUNTRIES"
    tips = len(re.findall(r"^\s*LOADING_TIP_\d+:", (ROOT / "localisation/russian/loading_tips_l_russian.yml")
                          .read_text(encoding="utf-8-sig"), re.M))
    langs = len([d for d in ("russian", "english") if (ROOT / "localisation" / d).exists()])
    if lang == "english":
        return [("1990", "1 January"), (str(countries), "countries"), (str(states), "states"),
                (str(tips), "quotes"), (str(langs), "languages")]
    return [("1990", "1 января"), (str(countries), plural(countries, "страна", "страны", "стран")),
            (str(states), plural(states, "область", "области", "областей")),
            (str(tips), plural(tips, "цитата эпохи", "цитаты эпохи", "цитат эпохи")),
            (str(langs), plural(langs, "язык", "языка", "языков"))]


def plural(n, one, few, many):
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def stats():
    for lang, name in (("russian", "stats.png"), ("english", "stats_en.png")):
        stats_strip(stats_numbers(lang), name)


def stats_strip(items, name):
    """Left-aligned blocks (number over label) between the 96 px margins, equal gaps between the blocks."""
    margin, top, gap, bottom = 96, 56, 24, 60
    widths = [max(text_w(num, STAT_CELL), text_w(label, LABEL_CELL)) for num, label in items]
    space = (STATS_W - 2 * margin - sum(widths)) / (len(items) - 1)
    assert space >= 80, f"stats too wide: {space:.0f} px between blocks"
    glyph_h = 7 * STAT_CELL
    h = top + glyph_h + gap + 7 * LABEL_CELL + bottom
    img = dark_canvas(STATS_W, h)
    x = float(margin)
    for (num, label), bw in zip(items, widths):
        paste_clipped(img, glow_text([num], STAT_CELL), round(x) - GLOW_PAD, top - GLOW_PAD)
        draw_text(img, label, round(x), top + glyph_h + gap, LABEL_CELL, DIM)
        x += bw + space
    save(add_grain(img, 1.6), name)


PARTS = {"hero": hero, "headers": headers, "flags": flags, "spirits": spirits, "stats": stats}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", help="folder with the 3440x1440 screenshots of GALLERY")
    ap.add_argument("--only", help="comma-separated parts: " + ", ".join([*PARTS, "gallery"]))
    args = ap.parse_args()
    only = set(args.only.split(",")) if args.only else {*PARTS, "gallery"}
    for name, fn in PARTS.items():
        if name in only:
            fn()
    if "gallery" in only:
        gallery(args.shots)


if __name__ == "__main__":
    main()
