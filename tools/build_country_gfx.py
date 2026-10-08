"""Pictures for content outside the Soviet tree: faction logos (the real emblems from Wikimedia Commons), subject type
icons cut from them, and AI event pictures of other countries (same image API and key as tools/gen_icons.py).

Sources are kept in tools/src/ (committed), so the game files can be rebuilt without downloads or API calls:
  faction logos   tools/src/factions/<name>.png -> gfx/interface/factions/totu/<name>.dds, 200x100: the logo and its
                  highlighted copy side by side, as vanilla; <name>_miniature.dds, 32x32.
                  Sprites GFX_faction_logo_<name> and GFX_faction_logo_<name>_miniature in interface/totu_factions.gfx.
  subject types   35x35 icons cut from a faction logo -> gfx/interface/autonomy/totu/<id>.dds, GFX_<id>_icon in
                  interface/totu_autonomy.gfx (AUTONOMY_ICONS).
  event pictures  tools/src/events/<name>.png -> gfx/event_pictures/totu/<name>.dds (report 210x176, news 397x153).
                  Sprites in interface/totu_events_countries.gfx (interface/totu_events.gfx belongs to
                  tools/gen_event_pictures.py, the Soviet pictures).

Usage:
  python tools/build_country_gfx.py                 # generate missing pictures, then convert all
  python tools/build_country_gfx.py NAME ...        # regenerate these
  python tools/build_country_gfx.py --convert-only  # no API calls
"""
import argparse
import base64
import io
import json
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_icons as g  # noqa: E402  (API key, base URL, model, SETTINGS)
from build_menu_gfx import cover, save_dds  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

# Faction logos are the real emblems, downloaded from Wikimedia Commons (rendered PNG of the SVG), not generated:
# name -> (Commons file, how it becomes a logo: "trim" = the emblem on transparency, cut to its outline;
#          "disc" = a circle cut from the centre of a flag, radius as a share of the flag height)
# (common/factions/templates/TOTU_factions.txt)
FACTION_LOGOS = {
    # the Warsaw Pact emblem «Союз мира и социализма» with the members' flags, public domain
    "totu_warsaw_pact": ("Warsaw Pact Logo.svg", ("trim",)),
    # the compass rose of the NATO flag, public domain
    "totu_nato": ("Flag of NATO.svg", ("disc", 0.36)),
}
COMMONS_UA = {"User-Agent": "TotU-mod/0.1 (Twilight of the Union HOI4 mod build script)"}

# subject (autonomy) type icons, 35x35 like vanilla: autonomy id -> faction logo source it is cut from
# (common/autonomous_states/); sprites GFX_<id>_icon in interface/totu_autonomy.gfx
AUTONOMY_ICONS = {
    "autonomy_totu_socialist_commonwealth": "totu_warsaw_pact",
}

PHOTO_LOOK = ("It must look like a scanned 1990 press photo ({press}): faded colour film, soft focus, visible film "
              "grain, natural uneven light, real people with real skin. Not a painting, not an illustration, not CGI, "
              "no HDR, no lens flare, no glow. No text, no captions, no watermark, no readable lettering.")
EVENT_SIZES = {"report": (210, 176), "news": (397, 153)}
# name -> (kind, country tag for the press look, subject)
EVENT_PICTURES = {
    # GDR (events/TOTU_DDR.txt)
    "totu_ddr_normannenstrasse": ("report", "DDR", "East Berlin, 15 January 1990: a crowd of citizens in winter coats "
                                  "pouring through an opened steel gate into the courtyard of a grey multi-storey "
                                  "office complex, papers strewn on the ground, some people holding candles."),
    "totu_ddr_volkskammer_election": ("report", "DDR", "East Berlin, 18 March 1990: voters in winter coats in a school "
                                      "polling station, a woman dropping a folded ballot into a wooden ballot box, "
                                      "election officials at a long table behind her."),
    # GDR focus tree, political branch (events/TOTU_DDR_political.txt)
    "totu_ddr_boehme_affair": ("report", "DDR", "Ibrahim Böhme (receding grey hair, small grey moustache, dark suit and "
                               "tie) leaving a government building through a side door in East Berlin, two press "
                               "photographers with flashguns on the steps, March 1990."),
    "totu_ddr_pact_protocol": ("report", "DDR", "A Soviet army general in a uniform with rows of medal ribbons and an "
                               "East German civilian minister in a dark suit signing a protocol at a small table covered "
                               "with green cloth in a plain conference room; two officers standing behind them."),
}


def request(prompt, size, transparent):
    body = {"model": g.MODEL, "prompt": prompt, "size": size, "n": 1, "output_format": "png"}
    if transparent:
        body["background"] = "transparent"
    req = urllib.request.Request(g.BASE_URL + "/images/generations", data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {g.api_key()}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        data = json.loads(r.read())["data"][0]
    return base64.b64decode(data["b64_json"]) if data.get("b64_json") else urllib.request.urlopen(data["url"]).read()


def commons_png(title, width):
    """A PNG rendering of a Wikimedia Commons file (SVGs are rasterised by Commons), width px."""
    q = urllib.parse.urlencode({"action": "query", "prop": "imageinfo", "iiprop": "url", "iiurlwidth": width,
                                "format": "json", "titles": "File:" + title})
    req = urllib.request.Request("https://commons.wikimedia.org/w/api.php?" + q, headers=COMMONS_UA)
    info = next(iter(json.load(urllib.request.urlopen(req, timeout=60))["query"]["pages"].values()))["imageinfo"][0]
    return Image.open(io.BytesIO(urllib.request.urlopen(
        urllib.request.Request(info["thumburl"], headers=COMMONS_UA), timeout=120).read())).convert("RGBA")


def real_logo(name):
    """The emblem as a square RGBA source, cut as FACTION_LOGOS says."""
    title, (how, *arg) = FACTION_LOGOS[name]
    img = commons_png(title, 1600)
    if how == "trim":
        return img.crop(img.getchannel("A").point(lambda v: 255 if v > 12 else 0).getbbox())
    w, h = img.size
    r = round(arg[0] * h)
    disc = img.crop((w // 2 - r, h // 2 - r, w // 2 + r, h // 2 + r))
    mask = Image.new("L", disc.size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0, 2 * r - 1, 2 * r - 1), fill=255)
    disc.putalpha(mask)
    ring = Image.new("RGBA", disc.size, (0, 0, 0, 0))   # a thin light rim, so the dark disc reads on the dark UI
    ImageDraw.Draw(ring).ellipse((0, 0, 2 * r - 1, 2 * r - 1), outline=(206, 210, 218, 255), width=max(2, r // 40))
    disc.alpha_composite(ring)
    return disc


def generate(name):
    if name in FACTION_LOGOS:
        buf = io.BytesIO()
        real_logo(name).save(buf, format="PNG")
        png, out = buf.getvalue(), "factions"
    else:
        kind, tag, subject = EVENT_PICTURES[name]
        png = request(subject + " " + PHOTO_LOOK.format(press=g.SETTINGS[tag]["press"]), "1536x1024", False)
        out = "events"
    path = ROOT / "tools/src" / out / f"{name}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)
    print("generated", name, flush=True)


def fit(img, w, h):
    """Trim transparent margins and centre in a w x h transparent canvas."""
    box = img.getchannel("A").point(lambda v: 255 if v > 12 else 0).getbbox() or (0, 0, img.width, img.height)
    img = img.crop(box)
    s = min(w / img.width, h / img.height)
    img = img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))), Image.LANCZOS)
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    canvas.alpha_composite(img, ((w - img.width) // 2, (h - img.height) // 2))
    return canvas


def logo_frames(src):
    """200x100: the logo, then the same logo with the soft light rim vanilla shows on the selected faction."""
    logo = fit(Image.open(src).convert("RGBA"), 88, 88)
    plain = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    plain.alpha_composite(logo, (6, 6))
    rim = plain.getchannel("A").filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(2.5))
    rim = rim.point(lambda v: min(255, int(v * 0.85)))
    lit = Image.new("RGBA", (100, 100), (246, 232, 196, 0))
    lit.putalpha(rim)
    lit.alpha_composite(plain)
    strip = Image.new("RGBA", (200, 100), (0, 0, 0, 0))
    strip.alpha_composite(plain, (0, 0))
    strip.alpha_composite(lit, (100, 0))
    return strip, fit(Image.open(src).convert("RGBA"), 32, 32)


def convert():
    blocks = []
    for name in FACTION_LOGOS:
        src = ROOT / "tools/src/factions" / f"{name}.png"
        if not src.exists():
            print("no", src.relative_to(ROOT).as_posix(), "yet")
            continue
        strip, mini = logo_frames(src)
        save_dds(strip, ROOT / f"gfx/interface/factions/totu/{name}.dds")
        save_dds(mini, ROOT / f"gfx/interface/factions/totu/{name}_miniature.dds")
        blocks.append(f'\tspriteType = {{\n\t\tname = "GFX_faction_logo_{name}"\n'
                      f'\t\ttexturefile = "gfx/interface/factions/totu/{name}.dds"\n\t\tnoOfFrames = 2\n\t}}\n')
        blocks.append(f'\tspriteType = {{\n\t\tname = "GFX_faction_logo_{name}_miniature"\n'
                      f'\t\ttexturefile = "gfx/interface/factions/totu/{name}_miniature.dds"\n\t}}\n')
    write_gfx("totu_factions.gfx", "Faction logos 200x100 (2 frames) and miniatures 32x32.", blocks)

    blocks = []
    for name, logo in AUTONOMY_ICONS.items():
        src = ROOT / "tools/src/factions" / f"{logo}.png"
        if not src.exists():
            print("no", src.relative_to(ROOT).as_posix(), "yet")
            continue
        save_dds(fit(Image.open(src).convert("RGBA"), 35, 35), ROOT / f"gfx/interface/autonomy/totu/{name}.dds")
        blocks.append(f'\tspriteType = {{\n\t\tname = "GFX_{name}_icon"\n'
                      f'\t\ttexturefile = "gfx/interface/autonomy/totu/{name}.dds"\n\t}}\n')
    write_gfx("totu_autonomy.gfx", "Subject (autonomy) type icons 35x35, cut from the faction logos.", blocks)

    blocks = []
    for name, (kind, _, _) in EVENT_PICTURES.items():
        src = ROOT / "tools/src/events" / f"{name}.png"
        if not src.exists():
            print("no", src.relative_to(ROOT).as_posix(), "yet")
            continue
        w, h = EVENT_SIZES[kind]
        save_dds(cover(Image.open(src).convert("RGB"), w, h), ROOT / f"gfx/event_pictures/totu/{name}.dds")
        prefix = "GFX_report_event_" if kind == "report" else "GFX_news_event_"
        blocks.append(f'\tspriteType = {{\n\t\tname = "{prefix}{name}"\n'
                      f'\t\ttexturefile = "gfx/event_pictures/totu/{name}.dds"\n\t}}\n')
    write_gfx("totu_events_countries.gfx", "Event pictures of countries other than the USSR: report 210x176, news "
              "397x153.", blocks)


def write_gfx(name, what, blocks):
    text = (f"# GENERATED by tools/build_country_gfx.py - edit it, not this file.\n# {what}\nspriteTypes = {{\n"
            + "\n".join(blocks) + "}\n")
    (ROOT / "interface" / name).write_text(text, encoding="utf-8", newline="\n")
    print("wrote interface/" + name, len(blocks), "sprites")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*")
    ap.add_argument("--convert-only", action="store_true")
    args = ap.parse_args()
    known = {**FACTION_LOGOS, **EVENT_PICTURES}
    unknown = [n for n in args.names if n not in known]
    if unknown:
        sys.exit(f"unknown pictures: {unknown}")
    if not args.convert_only:
        todo = args.names or [n for n in known if not (
            ROOT / "tools/src" / ("factions" if n in FACTION_LOGOS else "events") / f"{n}.png").exists()]
        with ThreadPoolExecutor(6) as pool:
            list(pool.map(generate, todo))
    convert()


if __name__ == "__main__":
    main()
