"""Renders README screenshots into docs/images from the previews of the build scripts.

The previews are composed from the built textures and fonts, laid out like the .gui files (not game captures).
Run after tools/build_fonts.py, tools/build_menu_gfx.py and tools/preview_country.py.
Usage: python tools/render_docs.py
"""
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_menu_gfx as g  # noqa: E402

ROOT = g.ROOT
OUT = ROOT / "docs" / "images"


def L(rel):
    return Image.open(ROOT / rel).convert("RGBA")


def save(img, name):
    OUT.mkdir(parents=True, exist_ok=True)
    img = img.convert("RGB")
    img.thumbnail((1600, 1600), Image.LANCZOS)
    img.save(OUT / name, quality=86)
    print("wrote", (OUT / name).relative_to(ROOT))


def main_menu():
    shot = Image.open(ROOT / "tools/preview/menu_preview.png").convert("RGBA")
    save(shot, "main_menu.jpg")


def loading():
    shot = Image.open(ROOT / "tools/preview/loading_preview.png").convert("RGBA")       # build_menu_gfx.py
    save(shot, "loading_screen.jpg")


def loading_sheet():
    names = ["tanks_red_square", "yeltsin_podium", "yeltsin_tank", "white_house"]
    sheet = Image.new("RGB", (1928, 1088), (10, 8, 7))
    for i, n in enumerate(names):
        im = L(f"gfx/loadingscreens/totu_load_{n}.dds").crop((0, 180, 1920, 1260)).resize((960, 540), Image.LANCZOS)
        sheet.paste(im.convert("RGB"), (4 + (i % 2) * 964, 4 + (i // 2) * 544))
    save(sheet, "loading_screens.jpg")


def scenario():
    shot = Image.open(ROOT / "tools/preview/screen_scenario.png").convert("RGBA")      # build_menu_gfx.py
    save(shot, "scenario.jpg")


def country_select():
    shot = Image.open(ROOT / "tools/preview/screen_country.png").convert("RGBA")       # tools/preview_country.py
    save(shot, "country_select.jpg")


if __name__ == "__main__":
    main_menu()
    loading()
    loading_sheet()
    scenario()
    country_select()
