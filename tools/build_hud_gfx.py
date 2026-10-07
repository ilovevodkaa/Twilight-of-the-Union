"""HUD restyle: vanilla interface textures re-graded into the mod's palette.

Earlier versions redrew HUD textures as flat boxes, which clashed with the ornate vanilla art left around them.
This version keeps every vanilla texture's shapes, bevels and ornaments and only re-colours it: desaturated,
slightly darker, toned from near-black warm shadows to the menu's tan highlights (tools/build_menu_gfx.py
palette). Output mirrors the vanilla paths under gfx/interface/, so no .gfx/.gui changes are needed.

Usage:  python tools/build_hud_gfx.py [--game PATH]
"""
import argparse
import shutil
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "gfx" / "interface"
GAME_GUESSES = [r"D:\steam\steamapps\common\Hearts of Iron IV",
                r"C:\Program Files (x86)\Steam\steamapps\common\Hearts of Iron IV"]

SHADOW = np.array([12, 10, 9], np.float32)       # palette ends: warm near-black to tan (the in-game HUD)
HIGHLIGHT = np.array([232, 214, 184], np.float32)
SATURATION = 0.35        # share of the original colour kept
TONE_MIX = 0.55          # how far luminance is pulled onto the shadow->highlight ramp
BRIGHTNESS = 0.86

# whole vanilla folders (relative to gfx/interface) and single files
FOLDERS = ["topbar", "tiles"]
FILES = [
    "button_123x34.dds", "button_148x34.dds", "button_221x34.dds", "button_261x34.dds", "government_button.dds",
    "sort_button_171x35.dds", "sort_button_100x29_2.dds", "sort_up_down_button_83x29.dds",
    "generic_box_smallest.dds", "generic_box_96.dds", "generic_text_bg_108.dds", "generic_bg_417.dds",
    "date_pause_button_bg.dds", "header_bg.dds", "main_screens_bottom.dds", "category_header.dds",
    "idea_group_header.dds", "closebutton.dds", "scroll_drager.dds", "scroll_up.dds", "scroll_down.dds",
    "scroll_track.dds", "scrollbar_vertical_bg.dds", "pol_view_bg.dds",
]


def grade(img):
    a = np.asarray(img.convert("RGBA"), np.float32)
    rgb, alpha = a[..., :3], a[..., 3:]
    lum = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
    grey = lum[..., None]
    rgb = grey + (rgb - grey) * SATURATION
    t = (lum / 255.0)[..., None]
    ramp = SHADOW + (HIGHLIGHT - SHADOW) * t
    rgb = rgb * (1 - TONE_MIX) + ramp * TONE_MIX
    rgb *= BRIGHTNESS
    out = np.concatenate([np.clip(rgb, 0, 255), alpha], axis=-1).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def is_dxt(path):
    with open(path, "rb") as f:
        head = f.read(88)
    return path.suffix.lower() == ".dds" and head[84:88] in (b"DXT1", b"DXT3", b"DXT5")


def convert(src, dst):
    img = Image.open(src)
    out = grade(img)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.suffix.lower() == ".dds":
        out.save(dst, pixel_format="DXT5") if is_dxt(src) else out.save(dst)
    else:
        out.save(dst)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=next((g for g in GAME_GUESSES if Path(g).exists()), None))
    args = ap.parse_args()
    van = Path(args.game) / "gfx/interface"
    # remove the previous (flat) wave before regenerating
    for folder in FOLDERS:
        shutil.rmtree(OUT / folder, ignore_errors=True)
    # vanilla ships a junk backup folder (topbar/toolbar/bak: "Copy of ledger_button.dds", ...) that nothing references
    targets = [p for folder in FOLDERS for p in (van / folder).rglob("*") if p.suffix.lower() in (".dds", ".tga")
               and "bak" not in p.relative_to(van).parts]
    targets += [van / f for f in FILES]
    done = 0
    for src in targets:
        rel = src.relative_to(van)
        try:
            convert(src, OUT / rel)
            done += 1
        except Exception as e:  # noqa: BLE001 - unusual formats stay vanilla
            print("skipped", rel, e)
    print("graded", done, "textures")


if __name__ == "__main__":
    main()
