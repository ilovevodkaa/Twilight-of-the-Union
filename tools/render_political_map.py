"""Renders the 1990 political map (vanilla provinces, mod ownership and colours, darkened vanilla colormap) to
docs/images/map_1990.jpg. Rough approximation of the in-game political map mode, for checking borders and palette.

Usage:  python tools/render_political_map.py [--game PATH] [--crop x0 y0 x1 y1] [--out file]
"""
import argparse
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
GAME_GUESSES = [r"D:\steam\steamapps\common\Hearts of Iron IV",
                r"C:\Program Files (x86)\Steam\steamapps\common\Hearts of Iron IV"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=next((g for g in GAME_GUESSES if Path(g).exists()), None))
    ap.add_argument("--crop", type=int, nargs=4)
    ap.add_argument("--out", default=str(ROOT / "docs/images/map_1990.jpg"))
    ap.add_argument("--scale", type=float, default=0.5)
    args = ap.parse_args()
    game = Path(args.game)

    img = np.array(Image.open(game / "map/provinces.bmp").convert("RGB"))
    key = (img[..., 0].astype(np.int64) << 16) | (img[..., 1].astype(np.int64) << 8) | img[..., 2]
    col2id, sea = {}, set()
    for line in (game / "map/definition.csv").read_text(encoding="latin-1").splitlines():
        p = line.split(";")
        if len(p) > 4 and p[0].isdigit():
            col2id[(int(p[1]) << 16) | (int(p[2]) << 8) | int(p[3])] = int(p[0])
            if p[4] in ("sea", "lake"):
                sea.add(int(p[0]))
    uk, inv = np.unique(key.ravel(), return_inverse=True)
    P = np.array([col2id.get(int(k), 0) for k in uk])[inv].reshape(key.shape)

    colors = {}
    text = (ROOT / "common/countries/colors.txt").read_text(encoding="utf-8")
    for tag, rgb in re.findall(r"([A-Z0-9]{3}) = \{\s*color = rgb \{ ([^}]*) \}", text):
        colors[tag] = [int(v) for v in rgb.split()]
    owner = {}
    for f in (ROOT / "history/states").glob("*.txt"):
        s = f.read_text(encoding="utf-8")
        o = re.search(r"owner = (\w+)", s).group(1)
        for p in re.search(r"provinces\s*=\s*\{([^}]*)\}", s).group(1).split():
            owner[int(p)] = o
    n = P.max() + 1
    lut = np.zeros((n, 3), np.float32)
    land = np.zeros(n, bool)
    tag_id = np.zeros(n, np.int32)
    tags = sorted(set(owner.values()))
    for p, o in owner.items():
        if p < n:
            lut[p] = colors.get(o, [90, 90, 90])
            land[p] = True
            tag_id[p] = tags.index(o) + 1

    cm = Image.open(ROOT / "map/terrain/colormap_rgb_cityemissivemask_a.dds") \
        if (ROOT / "map/terrain/colormap_rgb_cityemissivemask_a.dds").exists() \
        else Image.open(game / "map/terrain/colormap_rgb_cityemissivemask_a.dds")
    cm = np.asarray(cm.convert("RGB").resize((P.shape[1], P.shape[0]), Image.BILINEAR), np.float32)
    wm_path = ROOT / "map/terrain/colormap_water_0.dds"
    wm = Image.open(wm_path if wm_path.exists() else game / "map/terrain/colormap_water_0.dds")
    wm = np.asarray(wm.convert("RGB").resize((P.shape[1], P.shape[0]), Image.BILINEAR), np.float32)
    hm = np.asarray(Image.open(game / "map/heightmap.bmp").convert("L"), np.float32)
    shade = np.asarray(Image.fromarray(hm.astype(np.uint8)).filter(ImageFilter.EMBOSS).convert("L"), np.float32) / 128

    is_land = land[P]
    out = np.where(is_land[..., None], cm * 0.45 + lut[P] * 0.75, wm)
    out *= np.clip(shade, 0.7, 1.3)[..., None] ** 0.6
    # country borders
    t = tag_id[P]
    edge = np.zeros(t.shape, bool)
    edge[:, 1:] |= t[:, 1:] != t[:, :-1]
    edge[1:, :] |= t[1:, :] != t[:-1, :]
    edge &= is_land | np.roll(is_land, 1, 0) | np.roll(is_land, 1, 1)
    out[edge] = out[edge] * 0.35
    im = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))
    if args.crop:
        im = im.crop(args.crop)
    im = im.resize((int(im.width * args.scale), int(im.height * args.scale)), Image.LANCZOS)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    im.save(args.out, quality=90)
    print(args.out, im.size)


if __name__ == "__main__":
    main()
