"""AI-generated event pictures in the mod's press-photo look (same API config as tools/gen_icons.py).

Raw generations are kept in tools/src/events/<name>.png; the game textures are cropped from them:
  report events (210x176) -> gfx/event_pictures/totu/<name>.dds   + GFX_report_event_<name>
  news events   (397x153) -> gfx/event_pictures/totu/<name>.dds   + GFX_news_event_<name>
both listed in interface/totu_events.gfx.

Usage:
  python tools/gen_event_pictures.py                 # generate missing pictures, then convert all
  python tools/gen_event_pictures.py NAME ...        # regenerate these
  python tools/gen_event_pictures.py --convert-only
"""
import argparse
import base64
import json
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_icons as g  # noqa: E402  (API key, base URL, model)
from build_menu_gfx import cover, save_dds  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "tools/src/events"

LOOK = ("It must look like a scanned 1990-1991 press photo (TASS, AP): faded colour film, soft focus, visible film "
        "grain, natural uneven light, real people with real skin. Not a painting, not an illustration, not CGI, no HDR, "
        "no lens flare, no glow. No text, no captions, no watermark.")
SIZES = {"report": (210, 176), "news": (397, 153)}

# name -> (kind, subject)
PICTURES = {
    # SOV political tree (events/TOTU_SOV_politics.txt)
    "totu_sov_vice_president": ("report", "Wide shot of the Congress of People's Deputies of the USSR in the Kremlin "
                                "Palace of Congresses, December 1990: rows of deputies in suits raising red voting "
                                "cards, a long presidium table under a huge Soviet coat of arms."),
    "totu_sov_vilnius_tv_tower": ("report", "Night in Vilnius, January 1991: Soviet BTR armoured personnel carriers and "
                                  "soldiers in front of the floodlit Vilnius television tower, a crowd of civilians "
                                  "with Lithuanian tricolour flags, smoke drifting through the headlights."),
    # Plenum of the Central Committee (events/TOTU_SOV_plenum.txt)
    "totu_plenum_hall": ("report", "The plenum of the Central Committee of the Communist Party of the Soviet Union, "
                         "1990: a large Kremlin hall with rows of grey-suited party officials, a long presidium table "
                         "with red cloth and a bronze bust of Lenin behind it."),
    "totu_plenum_tribune": ("report", "A stern elderly Soviet party official in a dark suit speaking at a wooden "
                            "tribune with several microphones, gesturing with a raised hand, a red banner behind."),
    "totu_plenum_rally": ("report", "A crowd of Moscow democrats at a February 1990 rally on a snowy square, "
                          "hand-painted placards and Russian white-blue-red flags, a man speaking through a megaphone."),
    "totu_plenum_documents": ("report", "Close-up of a desk in a Central Committee office: stacks of typed draft "
                              "resolutions with red pencil marks, a red party membership card, glasses of tea and an "
                              "old black telephone."),
    "totu_plenum_backroom": ("report", "Three party officials in suits talking quietly in a dim wood-panelled Kremlin "
                             "corridor, cigarette smoke, one glancing over his shoulder."),
    "totu_plenum_vote": ("report", "Rows of Central Committee members raising red party cards in an open vote, seen "
                         "from the presidium, 1990."),
    "totu_plenum_crisis": ("report", "A tense meeting of the Soviet Politburo around a long table, men in suits arguing, "
                           "one standing and pointing, papers scattered on the green cloth."),
    "totu_news_plenum": ("news", "Wide press photo of the plenum of the Central Committee of the CPSU in session in the "
                         "Kremlin, 1990, a sea of grey suits and a red presidium table, Lenin's bust in the centre."),
    # SOV political tree events (events/TOTU_SOV_politics.txt)
    "totu_sov_yeltsin_walkout": ("report", "Boris Yeltsin (tall, broad face, thick swept-back grey hair, dark suit) "
                                 "walking up the aisle of a congress hall away from the tribune, delegates turning "
                                 "their heads, July 1990."),
    "totu_sov_500_days": ("report", "Two Soviet economists in suits at a long table covered with thick typed reports and "
                          "charts, a desk calculator, cigarette smoke, a Moscow government office in 1990."),
    "totu_sov_referendum": ("report", "A Soviet polling station in March 1991: a woman in a winter coat dropping a ballot "
                            "into a red-draped ballot box, a portrait of Lenin on the wall, an old man waiting."),
    "totu_sov_march_rally": ("report", "Moscow, 28 March 1991: a huge crowd with Russian tricolours and placards on a "
                             "wide street, lines of militia trucks and riot police blocking the way, grey sky."),
    "totu_sov_foros": ("report", "A white government dacha on the Crimean coast at Foros behind a fence, a black Volga "
                       "car and guards in dark coats at the gate, the sea behind, August 1991."),
    "totu_sov_war_of_laws": ("report", "A Moscow newspaper kiosk with two front pages side by side, Izvestia and a Russian "
                             "parliament newspaper, people reading over each other's shoulders, 1990."),
    # world news about the USSR (events/TOTU_SOV_news.txt)
    "totu_news_article_six": ("news", "Wide press photo of the Congress of People's Deputies of the USSR voting in the "
                              "Kremlin Palace of Congresses, March 1990, a forest of raised red cards."),
    "totu_news_president": ("news", "Mikhail Gorbachev (bald, birthmark on his forehead, grey suit) taking the oath as "
                            "President of the USSR at a tribune, hand raised, March 1990, wide press photo."),
    "totu_news_vilnius": ("news", "Wide press photo at night in Vilnius, January 1991: Soviet armoured vehicles and a "
                          "dense crowd at the floodlit television tower, smoke in the air."),
    "totu_news_referendum": ("news", "Wide press photo of a queue of Soviet voters in winter coats at a polling station, "
                             "March 1991, red banners on the building."),
    "totu_news_putsch": ("news", "Wide press photo of Soviet tanks on a Moscow street in August 1991, a crowd of "
                         "civilians around them, the white parliament building in the distance."),
    "totu_news_union_treaty": ("news", "Wide press photo of leaders of the Soviet republics in suits signing a treaty at "
                               "a long table under flags, Kremlin hall, 1991."),
    "totu_news_emergency": ("news", "Wide press photo of an old Soviet television showing the Swan Lake ballet in a "
                            "Moscow flat, a family watching, August 1991."),
    "totu_news_yeltsin": ("news", "Boris Yeltsin (tall, thick swept-back grey hair, dark suit) speaking at the tribune "
                          "of the Russian Congress of People's Deputies, May 1990, wide press photo."),
}


def generate(name):
    kind, subject = PICTURES[name]
    size = "1536x1024"
    body = json.dumps({"model": g.MODEL, "prompt": subject + " " + LOOK, "size": size, "n": 1,
                       "output_format": "png"}).encode()
    req = urllib.request.Request(g.BASE_URL + "/images/generations", data=body, method="POST",
                                 headers={"Authorization": f"Bearer {g.api_key()}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        data = json.loads(r.read())["data"][0]
    png = base64.b64decode(data["b64_json"]) if data.get("b64_json") else urllib.request.urlopen(data["url"]).read()
    SRC.mkdir(parents=True, exist_ok=True)
    (SRC / f"{name}.png").write_bytes(png)
    print("generated", name, flush=True)


def convert():
    blocks = []
    for name, (kind, _) in PICTURES.items():
        src = SRC / f"{name}.png"
        if not src.exists():
            continue
        w, h = SIZES[kind]
        save_dds(cover(Image.open(src).convert("RGB"), w, h), ROOT / f"gfx/event_pictures/totu/{name}.dds")
        prefix = "GFX_report_event_" if kind == "report" else "GFX_news_event_"
        blocks.append(f'\tspriteType = {{\n\t\tname = "{prefix}{name}"\n'
                      f'\t\ttexturefile = "gfx/event_pictures/totu/{name}.dds"\n\t}}\n')
    (ROOT / "interface/totu_events.gfx").write_text(
        "# GENERATED by tools/gen_event_pictures.py - edit PICTURES there, not this file.\n"
        "# Report events 210x176, news events 397x153. Sources: tools/src/events/*.png.\nspriteTypes = {\n"
        + "\n".join(blocks) + "}\n", encoding="utf-8", newline="\n")
    print("wrote interface/totu_events.gfx", len(blocks), "sprites")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*")
    ap.add_argument("--convert-only", action="store_true")
    args = ap.parse_args()
    if not args.convert_only:
        todo = args.names or [n for n in PICTURES if not (SRC / f"{n}.png").exists()]
        with ThreadPoolExecutor(8) as pool:
            list(pool.map(generate, todo))
    convert()


if __name__ == "__main__":
    main()
