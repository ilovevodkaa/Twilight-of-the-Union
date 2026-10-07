"""Flags for the 1990 world.

Real flags from Wikimedia Commons (tools/src/flags/<TAG>.png, fetched by tools/fetch_flags.py) replace vanilla
flags that show 1936 or hypothetical states (Kingdom of Egypt, Republican Spain, Pahlavi Iran, ...) and give the
tags vanilla does not have their flag. Every ideology variant is overwritten, so a later government change keeps
the 1990 flag until the mod adds its own variants.
"""
import shutil
from pathlib import Path

from PIL import Image

SRC = Path(__file__).resolve().parent.parent / "src/flags"
SIZES = {"": (82, 52), "medium": (41, 26), "small": (10, 7)}
IDEOLOGIES = ["democratic", "communism", "neutrality", "fascism"]

# tag -> vanilla flag file to copy instead of a download
COPY = {"PRK": "KOR_communism"}
# tag -> vanilla flag file copied over the tag and every ideology variant: vanilla's own variants show a 1930s state
# (PRC_communism is the Chinese Soviet Republic's hammer and sickle; the five-star flag is PRC_proclaimed_communism)
COPY_ALL = {"PRC": "PRC_proclaimed_communism"}


def save_all(img, root, name):
    for sub, size in SIZES.items():
        p = root / "gfx/flags" / sub / f"{name}.tga"
        p.parent.mkdir(parents=True, exist_ok=True)
        img.resize(size, Image.LANCZOS).save(p)


def write_flags(game, root, new_tags):
    shutil.rmtree(root / "gfx/flags", ignore_errors=True)
    for tag, src in COPY.items():
        for sub in SIZES:
            dst = root / "gfx/flags" / sub / f"{tag}.tga"
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(game / "gfx/flags" / sub / f"{src}.tga", dst)
    for tag, src in COPY_ALL.items():
        for name in [tag] + [f"{tag}_{i}" for i in IDEOLOGIES]:
            for sub in SIZES:
                dst = root / "gfx/flags" / sub / f"{name}.tga"
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(game / "gfx/flags" / sub / f"{src}.tga", dst)
    missing = [t for t in new_tags if t not in COPY and not (SRC / f"{t}.png").exists()]
    assert not missing, f"no flag for new tags {missing}: run tools/fetch_flags.py"
    for png in sorted(SRC.glob("*.png")):
        tag = png.stem
        img = Image.open(png).convert("RGBA")
        bg = Image.new("RGBA", img.size, (0, 0, 0, 255))
        img = Image.alpha_composite(bg, img)
        for name in [tag] + [f"{tag}_{i}" for i in IDEOLOGIES]:
            save_all(img, root, name)
