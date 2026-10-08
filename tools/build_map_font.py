"""Map lettering in the spirit of TNO: country names and city (victory point) names in Play Bold - white letters with a
soft dark edge, instead of vanilla's dark half-transparent Tahoma with a light ring.

Font: Play Bold (c) Jonas Hecksher, SIL Open Font License 1.1 - tools/src/fonts/Play-Bold.ttf and Play-OFL.txt.

Writes:
  gfx/fonts/hoi_mapfont4.fnt/.dds   country names. The engine draws them with the font "tahoma_60" of vanilla
                                    interface/core.gfx, whose path is gfx/fonts/hoi_mapfont4, so the mod's files replace
                                    vanilla's. Same character set (minus archaic Cyrillic Play lacks), lineHeight, base
                                    and cap height as vanilla (a size smaller if the
                                    glyphs overflow); 2048x1024 atlas with mipmaps like vanilla: the engine refuses a
                                    larger one (MAX_TEXTURE_SIZE).
  gfx/fonts/map_city.fnt/.dds       city names: font "totu_map_city" of interface/totu_map_fonts.gfx (written here),
                                    the vanilla hoi_20bs + hoi_20bs_cryllic character set and metrics, no mipmaps
                                    (an interface font). The file name has no totu_ prefix on purpose: tools/build_fonts.py
                                    treats gfx/fonts/totu_* fonts as its pixel fonts.
  interface/mapicons.gui            vanilla copy, the victory point and capital map icons use totu_map_city
Simplified Chinese, Korean and Japanese keep their vanilla map fonts (core_chinese.gfx / core_korean.gfx and the
l_japanese overrides).

Usage:  python tools/build_map_font.py [--game PATH]   (writes tools/preview/map_font.png too)
"""
import argparse
import re
from pathlib import Path

import numpy as np
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import distance_transform_edt

from build_map_style import GAME_GUESSES, write_dds_rgba

ROOT = Path(__file__).resolve().parent.parent
TTF = ROOT / "tools/src/fonts/Play-Bold.ttf"
FONTS = ROOT / "gfx/fonts"

BODY = (242, 242, 236)          # letter colour (the engine multiplies by the font colour, white)
EDGE = (10, 12, 18)             # soft dark edge around every letter

# name: vanilla files (charset, metrics), atlas size, edge radius / falloff (px), body / edge alpha, mipmaps, shadow,
# space: word gap as a multiple of vanilla's (Play's wide capitals made the country names' gaps look closed)
STYLES = {
    "country": dict(vanilla=["hoi_mapfont4.fnt"], atlas=(2048, 1024), edge=2.5, fall=2.0, body_a=0.92, edge_a=0.6,
                    mips=True, shadow=(0, 0), space=1.6, out="hoi_mapfont4"),
    "city": dict(vanilla=["hoi_20bs.fnt", "hoi_20bs_cryllic.fnt"], atlas=(512, 512), edge=1.0, fall=1.0,
                 body_a=1.0, edge_a=0.75, mips=False, shadow=(1, 1), space=1.0, out="map_city"),
}
ALIASES = {0x2015: 0x2014}      # horizontal bar -> em dash


def read_fnt(path):
    text = path.read_text(encoding="utf-8-sig")
    common = dict(re.findall(r"(\w+)=(-?\d+)", re.search(r"^common .*$", text, re.M).group(0)))
    pad = int(re.search(r"padding=(\d+)", text).group(1))
    chars = {}
    for line in re.findall(r"^char .*$", text, re.M):
        f = dict(re.findall(r"(\w+)=(-?\d+)", line))
        chars[int(f["id"])] = {k: int(v) for k, v in f.items()}
    return int(common["lineHeight"]), int(common["base"]), pad, chars


def cap_height(game, files):
    """Height of the vanilla 'H' without padding."""
    lh, base, pad, chars = read_fnt(game / "gfx/fonts" / files[0])
    return chars[ord("H")]["height"] - 2 * pad


def fit_size(target_cap):
    lo, hi = 4, 400
    while lo < hi:
        mid = (lo + hi + 1) // 2
        b = ImageFont.truetype(str(TTF), mid).getbbox("H", anchor="ls")
        if b[3] - b[1] <= target_cap:
            lo = mid
        else:
            hi = mid - 1
    return lo


def render_glyph(font, ch, st, pad):
    """Straight-alpha RGBA tile of one glyph plus its offsets relative to the pen position on the baseline."""
    x0, y0, x1, y1 = font.getbbox(ch, anchor="ls")
    if x1 <= x0 or y1 <= y0:
        return None, 0, 0
    w, h = x1 - x0 + 2 * pad, y1 - y0 + 2 * pad
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).text((pad - x0, pad - y0), ch, font=font, fill=255, anchor="ls")
    body = np.asarray(m, np.float32) / 255
    sx, sy = st["shadow"]
    src = np.roll(np.roll(body, sy, axis=0), sx, axis=1) if (sx or sy) else body
    dist = distance_transform_edt(src < 0.5)                  # px from the glyph's ink
    edge = np.clip(1 - (dist - st["edge"]) / st["fall"], 0, 1) * st["edge_a"]
    edge = np.maximum(edge, src * st["edge_a"])
    ab = body * st["body_a"]
    a = ab + edge * (1 - ab)
    rgb = (np.array(BODY, np.float32) * ab[..., None] + np.array(EDGE, np.float32) * (edge * (1 - ab))[..., None])
    rgb = np.where(a[..., None] > 0, rgb / np.maximum(a[..., None], 1e-6), 0)
    tile = np.dstack([rgb, a * 255]).astype(np.float32)
    return tile, x0 - pad, y0 - pad


def build(game, name, st):
    lh, base, vpad, vchars = 0, 0, 0, {}
    for f in st["vanilla"]:
        l, b, p, c = read_fnt(game / "gfx/fonts" / f)
        lh, base, vpad = lh or l, base or b, vpad or p
        vchars.update({k: v for k, v in c.items() if k not in vchars})
    pad = int(np.ceil(st["edge"] + st["fall"])) + 1 + max(st["shadow"])
    cmap = TTFont(str(TTF)).getBestCmap()
    W, H = st["atlas"]
    size = fit_size(cap_height(game, st["vanilla"]))
    while True:                     # the vanilla cap height, or a little less if the atlas would overflow
        font = ImageFont.truetype(str(TTF), size)
        glyphs, skipped = [], []
        for cid in sorted(vchars):
            src = ALIASES.get(cid, cid)
            if cid < 32 or src not in cmap:
                if cid < 32:        # control characters vanilla lists: zero-size, no advance
                    glyphs.append((cid, None, 0, 0, 0))
                else:
                    skipped.append(cid)
                continue
            ch = chr(src)
            tile, xo, yo = render_glyph(font, ch, st, pad)
            adv = round(font.getlength(ch))
            if tile is None:        # spaces: an empty quad like vanilla's (7x5), the map name layout needs a width
                v = vchars[cid]
                tile = np.zeros((max(v["height"], 1), max(v["width"], 1), 4), np.float32)
                xo, yo = v["xoffset"], v["yoffset"] - base
                adv = round(max(adv, v["xadvance"]) * st["space"])
            glyphs.append((cid, tile, xo, yo, adv))
        packed = pack(glyphs, W, H, base)
        if packed:
            atlas, entries, used = packed
            break
        size -= 1

    out = FONTS / st["out"]
    if st["mips"]:
        write_dds_rgba(out.with_suffix(".dds"), atlas)
    else:
        Image.fromarray(np.clip(np.round(atlas), 0, 255).astype(np.uint8), "RGBA").save(out.with_suffix(".dds"))
    lines = [f'info face="Play Bold" size={size} bold=1 italic=0 charset="" unicode=1 stretchH=100 smooth=1 aa=1 '
             f'padding={pad},{pad},{pad},{pad} spacing=1,1 outline=0',
             f"common lineHeight={lh} base={base} scaleW={W} scaleH={H} pages=1 packed=0 alphaChnl=1 redChnl=0 "
             f"greenChnl=0 blueChnl=0",
             f'page id=0 file="{st["out"]}.dds"',
             f"chars count={len(entries)}"]
    for cid, gx, gy, gw, gh, xo, yo, adv in sorted(entries):
        lines.append(f"char id={cid} x={gx} y={gy} width={gw} height={gh} xoffset={xo} yoffset={yo} "
                     f"xadvance={adv} page=0 chnl=15")
    out.with_suffix(".fnt").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"{name}: {out.with_suffix('.fnt').relative_to(ROOT)} size {size}, {len(entries)} chars, "
          f"rows used {used}/{H}, skipped {len(skipped)} (Play has no glyph)")
    return font, atlas


def pack(glyphs, W, H, base):
    """Shelf packing, tallest first. None if the glyphs do not fit."""
    atlas = np.zeros((H, W, 4), np.float32)
    x = y = row_h = 0
    entries = []
    for cid, tile, xo, yo, adv in sorted(glyphs, key=lambda g: -(g[1].shape[0] if g[1] is not None else 0)):
        if tile is None:
            entries.append((cid, W - 1, H - 1, 0, 0, 0, base, adv))
            continue
        th, tw = tile.shape[:2]
        if x + tw + 1 > W:
            x, y, row_h = 0, y + row_h + 1, 0
        if y + th > H:
            return None
        atlas[y:y + th, x:x + tw] = tile
        entries.append((cid, x, y, tw, th, xo, base + yo, adv))
        x, row_h = x + tw + 1, max(row_h, th)
    return atlas, entries, y + row_h


MAP_FONTS_GFX = """# Twilight of the Union: city (victory point) names on the map, Play Bold with a dark edge.
# Written by tools/build_map_font.py; the country names replace vanilla gfx/fonts/hoi_mapfont4 directly.
bitmapfonts = {
\tbitmapfont = {
\t\tname = "totu_map_city"
\t\tfontfiles = { "gfx/fonts/map_city" }
\t\tcolor = 0xffffffff
\t\ttextcolors = {
\t\t\tG = { 86 172 91 }
\t\t\tR = { 222 86 70 }
\t\t\tY = { 238 201 35 }
\t\t\tH = { 238 203 35 }
\t\t\tT = { 255 255 255 }
\t\t}
\t}
\tbitmapfont_override = {
\t\tname = "totu_map_city"
\t\tfontfiles = { "gfx/fonts/japanese/hoi_20bs" }
\t\tlanguages = { "l_japanese" }
\t}
\tbitmapfont_override = {
\t\tname = "totu_map_city"
\t\tfontfiles = { "gfx/fonts/hoi_20bs" }
\t\tlanguages = { "l_simp_chinese" "l_korean" }
\t}
}
"""
ICON_WINDOWS = ("victory_point_mapicon", "capital_mapicon")


def mapicons_gui(game):
    text = (game / "interface/mapicons.gui").read_text(encoding="utf-8-sig")
    for win in ICON_WINDOWS:
        start = text.index(f'name = "{win}"')
        end = text.index("containerWindowType", start)
        block = text[start:end]
        assert block.count('font = "hoi_20bs"') == 1, f"mapicons.gui: {win} changed, update mapicons_gui()"
        text = text[:start] + block.replace('font = "hoi_20bs"', 'font = "totu_map_city"') + text[end:]
    header = ("# Twilight of the Union: vanilla interface/mapicons.gui, written by tools/build_map_font.py; only the\n"
              "# victory point and capital name fonts differ (totu_map_city). Regenerate after a game patch.\n")
    (ROOT / "interface/mapicons.gui").write_text(header + text, encoding="utf-8", newline="\n")
    (ROOT / "interface/totu_map_fonts.gfx").write_text(MAP_FONTS_GFX, encoding="utf-8", newline="\n")
    print("wrote interface/mapicons.gui and interface/totu_map_fonts.gfx")


def preview(fonts):
    """Sample lines composited on a country colour, as the engine draws them (atlas glyphs at their offsets)."""
    from PIL import Image as I
    canvas = I.new("RGB", (1400, 360), (120, 40, 52))
    d = ImageDraw.Draw(canvas)
    d.rectangle((0, 180, 1400, 360), fill=(52, 82, 128))
    for (font, atlas, st), (y, txt) in zip(fonts, [(20, "СОЮЗ СОВЕТСКИХ"), (200, "Ленинград  Berlin  Kraków")]):
        fnt = read_fnt(FONTS / f"{st['out']}.fnt")
        lh, base, pad, chars = fnt
        img = I.fromarray(np.clip(np.round(atlas), 0, 255).astype(np.uint8), "RGBA")
        x = 20
        scale = 1.0 if st["out"] != "map_city" else 3.0
        for ch in txt:
            c = chars.get(ord(ch))
            if not c:
                continue
            if c["width"]:
                g = img.crop((c["x"], c["y"], c["x"] + c["width"], c["y"] + c["height"]))
                if scale != 1:
                    g = g.resize((round(g.width * scale), round(g.height * scale)), I.NEAREST)
                canvas.paste(g, (round(x + c["xoffset"] * scale), round(y + c["yoffset"] * scale)), g)
            x += c["xadvance"] * scale
    out = ROOT / "tools/preview/map_font.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    print("preview", out.relative_to(ROOT))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=next((g for g in GAME_GUESSES if Path(g).exists()), None))
    game = Path(ap.parse_args().game)
    FONTS.mkdir(parents=True, exist_ok=True)
    built = []
    for name, st in STYLES.items():
        font, atlas = build(game, name, st)
        built.append((font, atlas, st))
    mapicons_gui(game)
    preview(built)


if __name__ == "__main__":
    main()
