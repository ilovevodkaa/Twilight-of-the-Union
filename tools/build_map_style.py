"""Map style: rewrites the vanilla terrain and water colormaps into map/terrain/ - a near-black sea and slightly
dimmed, desaturated land, so the saturated political colours stand out.

Usage:  python tools/build_map_style.py [--game PATH]
"""
import argparse
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
GAME_GUESSES = [r"D:\steam\steamapps\common\Hearts of Iron IV",
                r"C:\Program Files (x86)\Steam\steamapps\common\Hearts of Iron IV"]

LAND_GAIN = 0.72        # brightness multiplier for land
LAND_SAT = 0.75         # saturation kept
WATER_GAIN = 0.10       # near-black sea
WATER_SAT = 0.35
WATER_TINT = np.array([0.85, 0.95, 1.15], np.float32)   # a hint of cold blue so the coastline still reads


def grade(rgb, gain, sat, tint=None):
    rgb = rgb.astype(np.float32)
    lum = (rgb @ np.array([0.299, 0.587, 0.114], np.float32))[..., None]
    rgb = lum + (rgb - lum) * sat
    rgb *= gain
    if tint is not None:
        rgb *= tint
    return np.clip(rgb, 0, 255).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=next((g for g in GAME_GUESSES if Path(g).exists()), None))
    args = ap.parse_args()
    src = Path(args.game) / "map/terrain"
    dst = ROOT / "map/terrain"
    dst.mkdir(parents=True, exist_ok=True)

    # land: uncompressed RGBA, alpha = city lights emissive mask (kept)
    im = np.asarray(Image.open(src / "colormap_rgb_cityemissivemask_a.dds").convert("RGBA")).copy()
    im[..., :3] = grade(im[..., :3], LAND_GAIN, LAND_SAT)
    Image.fromarray(im, "RGBA").save(dst / "colormap_rgb_cityemissivemask_a.dds")

    for i in range(3):
        name = f"colormap_water_{i}.dds"
        w = np.asarray(Image.open(src / name).convert("RGBA")).copy()
        w[..., :3] = grade(w[..., :3], WATER_GAIN, WATER_SAT, WATER_TINT)
        Image.fromarray(w, "RGBA").save(dst / name, pixel_format="DXT5")
    print("written to", dst)
    water_shader(Path(args.game), ROOT)


# Most of the sea's blue comes from the sky cubemap reflection (fresnel >= 0.5), not from the colormap, so the
# water shader is patched: the reflected/refracted colour is scaled down right after it is mixed, before borders,
# ice and selection highlights are drawn on top.
SEA_BRIGHTNESS = 0.08
SHADER_ANCHOR = "refractiveColor = refractiveColor * ( 1.0f - fresnel ) + reflectiveColor * fresnel;"


def water_shader(game, root):
    text = (game / "gfx/FX/pdxwater.shader").read_text(encoding="utf-8-sig")
    assert text.count(SHADER_ANCHOR) == 1, "pdxwater.shader changed, update SHADER_ANCHOR"
    patch = SHADER_ANCHOR + f"\n\t\t\trefractiveColor *= {SEA_BRIGHTNESS:.2f}f; // Twilight of the Union: black sea"
    out = root / "gfx/FX/pdxwater.shader"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text.replace(SHADER_ANCHOR, patch), encoding="utf-8")
    print("patched", out)


if __name__ == "__main__":
    main()
