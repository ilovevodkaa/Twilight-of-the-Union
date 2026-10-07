"""AI-generated icons for national spirits and focuses (OpenAI-compatible image API, e.g. gpt-image-2.5-flare).

Every icon is listed in ICONS with a short subject; the shared style prompt keeps them one series, in the look
of vanilla HOI4 art. Raw generations are kept in tools/src/icons/<kind>/<name>.png (committed, so icons can be
rebuilt without new API calls); the game textures and sprite files are written from them:
  idea  -> gfx/interface/ideas/totu/<name>.dds   + GFX_idea_<name>   in interface/totu_ideas.gfx
  focus -> gfx/interface/goals/totu/<name>.dds   + GFX_focus_<name>  in interface/totu_goals.gfx

Config (environment): TOTU_IMAGE_API_KEY (or TOTU_IMAGE_KEY_FILE = path to a file with the key),
TOTU_IMAGE_BASE_URL (default https://codex.sale/v1), TOTU_IMAGE_MODEL (default gpt-image-2.5-flare).

Usage:
  python tools/gen_icons.py                 # generate missing icons, then convert all
  python tools/gen_icons.py NAME ...        # only these icons (regenerates them)
  python tools/gen_icons.py --convert-only  # no API calls, rebuild DDS + .gfx from the PNGs
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "tools/src/icons"
BASE_URL = os.environ.get("TOTU_IMAGE_BASE_URL", "https://codex.sale/v1").rstrip("/")
MODEL = os.environ.get("TOTU_IMAGE_MODEL", "gpt-image-2.5-flare")

STYLE = {
    "idea": (
        "Icon for a national spirit in the strategy game Hearts of Iron IV, matching the game's own idea icons: "
        "a small round emblem with a thin dark bronze rim, inside it a detailed painterly illustration of {subject}. "
        "Setting: the Soviet Union, winter 1989-1990. Muted, slightly desaturated period colours with a dark red "
        "accent, soft dramatic light. The icon is shown at only 64 pixels, so compose it like a poster: a close-up "
        "of one or two large subjects, bold simple shapes, high contrast, almost no background detail. "
        "Centred, the emblem fills the frame, isolated on a fully transparent background. "
        "No text, no letters, no numbers, no watermark."
    ),
    # cut-out objects without a frame, like stickers (an alternative look for ideas)
    "cutout": (
        "Icon for a national spirit in the strategy game Hearts of Iron IV, in the style of modern HOI4 mods: "
        "a cut-out collage of real objects with no frame and no background, like a die-cut sticker: {subject}. "
        "Setting: the Soviet Union, 1989-1990. Realistic painted look, rich but slightly muted period colours, "
        "soft top light, a thin dark outline and a subtle drop shadow around the objects. The icon is shown at "
        "only 64 pixels, so keep two or three large objects with bold silhouettes, slightly overlapping. "
        "Centred, filling the frame, isolated on a fully transparent background. "
        "No text, no letters, no numbers, no watermark."
    ),
    "focus": (
        "Icon for a national focus in the strategy game Hearts of Iron IV, matching the game's own focus icons: "
        "a metallic medallion of brushed silver and dark bronze with a laurel wreath, the central relief shows "
        "{subject}. Small red enamel accents, dramatic top light, crisp edges, readable at 90 pixels. "
        "Late Soviet era, 1990. Centred, isolated on a fully transparent background. "
        "No text, no letters, no numbers, no watermark."
    ),
}
SIZES = {"idea": (64, 64), "focus": (96, 86)}       # icon area; ideas are padded to vanilla's 65x67 canvas

# name -> (kind, subject[, style]); style defaults to the kind's style ("cutout" is an alternative for ideas)
ICONS = {
    # Soviet starting spirits (common/ideas/TOTU_SOV.txt)
    "totu_no_plan_no_market": ("idea", "a still life of the failure of the Soviet planned economy: an empty string "
                                       "shopping bag (avoska), a sheet of food ration coupons, and a worn red "
                                       "five-year-plan folder with a broken cog wheel", "cutout"),
    "totu_glasnost": ("idea", "a rolled-up Soviet magazine and a folded newspaper with an old studio microphone and "
                              "a broken open padlock", "cutout"),
    "totu_nomenklatura": ("idea", "a red Communist Party membership card, a heavy official rubber stamp and a stack "
                                  "of red document folders tied with string", "cutout"),
    "totu_awakening_republics": ("idea", "three small hand-held flags of Estonia, Latvia and Lithuania crossed "
                                         "together over a cracked red Soviet star badge", "cutout"),
    "totu_bloated_mic": ("idea", "a Soviet main battle tank in side view in front of a stack of artillery shells and "
                                 "a large factory cog wheel", "cutout"),
    "totu_afghan_syndrome": ("idea", "a sun-faded Soviet Afghanka field cap (panama hat), a curved Kalashnikov "
                                     "magazine and a combat medal on a worn ribbon", "cutout"),
    "totu_conscript_army": ("idea", "a Soviet army ushanka hat with a red star badge, a tall black kirza boot and a "
                                    "folded military draft notice", "cutout"),
}


def api_key():
    key = os.environ.get("TOTU_IMAGE_API_KEY")
    if not key and os.environ.get("TOTU_IMAGE_KEY_FILE"):
        key = Path(os.environ["TOTU_IMAGE_KEY_FILE"]).read_text(encoding="utf-8").strip()
    if not key:
        sys.exit("set TOTU_IMAGE_API_KEY (or TOTU_IMAGE_KEY_FILE)")
    return key


def generate(prompt, key, retries=3):
    body = json.dumps({"model": MODEL, "prompt": prompt, "size": "1024x1024", "n": 1,
                       "background": "transparent", "output_format": "png"}).encode()
    req = urllib.request.Request(BASE_URL + "/images/generations", data=body, method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                data = json.loads(r.read())["data"][0]
            if data.get("b64_json"):
                return base64.b64decode(data["b64_json"])
            with urllib.request.urlopen(data["url"], timeout=120) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            print(f"  attempt {attempt + 1} failed: {e}")
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("image generation failed")


def to_game(png, kind):
    """Trim transparent margins, fit the icon area, pad ideas to the vanilla 65x67 canvas."""
    img = Image.open(png).convert("RGBA")
    box = img.getchannel("A").point(lambda v: 255 if v > 12 else 0).getbbox() or (0, 0, img.width, img.height)
    img = img.crop(box)
    w, h = SIZES[kind]
    s = min(w / img.width, h / img.height)
    img = img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))), Image.LANCZOS)
    canvas = Image.new("RGBA", (65, 67) if kind == "idea" else (w, h), (0, 0, 0, 0))
    canvas.alpha_composite(img, ((canvas.width - img.width) // 2, (canvas.height - img.height) // 2))
    return canvas


def write_sprites():
    for kind, gfx, prefix, folder in (("idea", "totu_ideas.gfx", "GFX_idea_", "ideas"),
                                      ("focus", "totu_goals.gfx", "GFX_focus_", "goals")):
        names = [n for n, (k, *_) in ICONS.items() if k == kind and (SRC / kind / f"{n}.png").exists()]
        if not names:
            continue
        blocks = [f'\tspriteType = {{\n\t\tname = "{prefix}{n}"\n\t\ttexturefile = "gfx/interface/{folder}/totu/{n}.dds"\n\t}}\n'
                  for n in names]
        text = ("# GENERATED by tools/gen_icons.py - edit ICONS there, not this file.\nspriteTypes = {\n"
                + "\n".join(blocks) + "}\n")
        (ROOT / "interface" / gfx).write_text(text, encoding="utf-8", newline="\n")
        print("wrote interface/" + gfx, len(names), "sprites")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*")
    ap.add_argument("--convert-only", action="store_true")
    args = ap.parse_args()
    unknown = [n for n in args.names if n not in ICONS]
    if unknown:
        sys.exit(f"unknown icons: {unknown}")
    if not args.convert_only:
        key = api_key()
        todo = args.names or [n for n, (k, *_) in ICONS.items() if not (SRC / k / f"{n}.png").exists()]
        for n in todo:
            kind, subject, *style = ICONS[n]
            style = style[0] if style else kind
            print(f"generating {n} ({kind}, {MODEL})", flush=True)
            png = generate(STYLE[style].format(subject=subject), key)
            out = SRC / kind / f"{n}.png"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(png)
    for n, (kind, *_) in ICONS.items():
        png = SRC / kind / f"{n}.png"
        if png.exists():
            dst = ROOT / "gfx/interface" / ("ideas" if kind == "idea" else "goals") / "totu" / f"{n}.dds"
            dst.parent.mkdir(parents=True, exist_ok=True)
            to_game(png, kind).save(dst)
    write_sprites()


if __name__ == "__main__":
    main()
