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
  python tools/gen_icons.py --jobs 6        # parallel API requests (default 6)
  python tools/gen_icons.py --convert-only  # no API calls, rebuild DDS + .gfx from the PNGs
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
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
        "Setting: {setting}. Muted, slightly desaturated period colours with a dark red "
        "accent, soft dramatic light. The icon is shown at only 64 pixels, so compose it like a poster: a close-up "
        "of one or two large subjects, bold simple shapes, high contrast, almost no background detail. "
        "Centred, the emblem fills the frame, isolated on a fully transparent background. "
        "No text, no letters, no numbers, no watermark."
    ),
    # cut-out objects without a frame, like stickers (an alternative look for ideas)
    "cutout": (
        "Icon for a national spirit in the strategy game Hearts of Iron IV, in the style of modern HOI4 mods: "
        "a cut-out collage of real objects with no frame and no background, like a die-cut sticker: {subject}. "
        "Setting: {setting}. Realistic painted look, rich but slightly muted period colours, "
        "soft top light, a thin dark outline and a subtle drop shadow around the objects. The icon is shown at "
        "only 64 pixels, so keep two or three large objects with bold silhouettes, slightly overlapping. "
        "Centred, filling the frame, isolated on a fully transparent background. "
        "No text, no letters, no numbers, no watermark."
    ),
    # collage of cut-out archival press photos, like hand-made focus icons of Cold War mods; the prompt fights the
    # tell-tale marks of generated art (sunbursts, glossy 3D lettering, airbrushed skin, neon colours, sticker strokes)
    "focus": (
        "Icon for a national focus in the strategy game Hearts of Iron IV, made the way human modders make them in "
        "Photoshop: two or three real archival press photographs cut out with the lasso tool and layered into a small "
        "collage, with no frame and no background. Subject ({setting}): {subject} "
        "It must look like scanned 1990 press photos ({press}): faded colour film, soft focus, "
        "visible film grain, slightly low resolution, natural uneven light, real skin with wrinkles and pores. Each "
        "photo keeps its own slightly different colour cast, as real photos from different sources do. Reds are dull "
        "brick red, never neon. Keep it simple and asymmetric: one main element large in front, one or two smaller "
        "elements behind or beside it, nothing else, no extra crowds, flags or towers beyond what the subject names. "
        "No glow or halo around anything. No light rays, no sunburst, no lens "
        "flare, no sparkles, no god rays. Cut-out edges are clean and natural with no outline stroke, no sticker "
        "border and no drop shadow. Not a painting, not an illustration, not CGI, not airbrushed, not glossy, no HDR, "
        "no oversharpening, no cinematic colour grading. Wide composition, about 1.2 times wider than tall; the "
        "bottom fifth is covered by a name plate in the game, so faces stay in the upper two thirds. "
        "Each named person appears exactly once and no other recognisable person is shown. "
        "Isolated on a fully transparent background. {text}"
    ),
}
# Where and when an icon is set ({setting} per style, {press} for focus collages). The country is taken from the
# icon name: "totu_<tag>_..." spirits and "<TAG>_..." focuses; everything else is Soviet.
SETTINGS = {
    "SOV": {"idea": "the Soviet Union, winter 1989-1990", "cutout": "the Soviet Union, 1989-1990",
            "focus": "the Soviet Union, 1990-1991", "press": "TASS, AP, Ogonyok magazine"},
    # the model stamps the hammer-and-compass emblem on every East German object unless told not to
    "DDR": {"idea": "East Germany (the GDR), winter 1989-1990", "cutout": "East Germany (the GDR), 1989-1990; no "
            "state emblem or hammer-and-compass badge on the objects unless the subject names one",
            "focus": "East Germany (the GDR), 1990", "press": "ADN, dpa, AP, Neues Deutschland"},
}


def country_of(name):
    for tag in SETTINGS:
        if name.startswith(f"totu_{tag.lower()}_") or name.startswith(f"{tag}_"):
            return tag
    return "SOV"


NO_TEXT = "No text, no letters, no numbers, no captions, no watermark."
SLOGAN = ("The only lettering in the image is \"{0}\", written naturally on the object in the scene (hand-painted, "
          "typed or printed, flat, never floating over the picture); spell it exactly. No other text, no watermark.")
SIZES = {"idea": (64, 64), "focus": (130, 103)}     # icon area; ideas are padded to vanilla's 65x67 canvas
# Focus icons are ~1.3x vanilla: interface/nationalfocusview.gui spaces the tree for them, and the politics,
# diplomacy and popup windows scale them back down to the vanilla footprint.

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
    # the armed services and the economy
    "totu_soviet_army": ("idea", "a Soviet T-80 main battle tank in three-quarter view with a red star on the turret, "
                                 "and a Soviet officer's olive peaked cap with a red star cockade in front of it",
                         "cutout"),
    "totu_soviet_air_force": ("idea", "a Soviet MiG-29 fighter jet in grey camouflage banking in flight, with a red "
                                      "star on the tail fin, and a white Soviet pilot flight helmet with a dark visor",
                              "cutout"),
    "totu_soviet_navy": ("idea", "the black conning tower of a Soviet Typhoon-class nuclear submarine rising from dark "
                                 "water, and a Soviet naval officer's white-topped cap with a golden anchor badge",
                         "cutout"),
    "totu_soviet_economy": ("idea", "a black oil pumpjack, a glowing steel ingot and a thick bundle of plain blank "
                                    "brown paper banknotes tied with string", "cutout"),
    # smaller spirits
    "totu_nuclear_parity": ("idea", "a Soviet Topol intercontinental ballistic missile in its green launch tube on a "
                                    "large mobile launcher truck, and a red launch key on a lanyard", "cutout"),
    "totu_chernobyl": ("idea", "a grey Soviet GP-5 rubber gas mask, a yellow radiation warning sign with the trefoil "
                               "symbol and a small handheld dosimeter", "cutout"),
    "totu_space_power": ("idea", "the white Soviet Buran space shuttle with black heat tiles, and a white Soviet "
                                 "cosmonaut helmet with a red star", "cutout"),
    # spirits given by the political focus tree (common/ideas/TOTU_SOV_focus.txt)
    "totu_sovereign_union": ("idea", "a red leather folder of a signed union treaty with a gold emblem on the cover, and "
                                     "a ring of small desk flags of the Soviet republics behind it", "cutout"),
    "totu_emergency_rule": ("idea", "a Soviet T-72 tank on a Moscow street and a red-and-white striped curfew barrier",
                            "cutout"),
    "totu_andropov_discipline": ("idea", "black-rimmed glasses lying on a stack of typed interrogation protocols, and a "
                                         "militia whistle on a chain", "cutout"),
    "totu_democratic_socialism": ("idea", "a red carnation and a red rose crossed over an open trade union membership "
                                          "card", "cutout"),
    "totu_market_reforms": ("idea", "a shop price tag with the old price crossed out, a thick stack of rouble banknotes "
                                    "and an old cash register", "cutout"),
    "totu_yeltsin_tandem": ("idea", "two small hand-held flags, the red Soviet flag and the Russian white-blue-red "
                                    "tricolour, crossed over a signed agreement with two pens", "cutout"),
    "totu_war_of_laws": ("idea", "two thick law codes, one red with the Soviet coat of arms and one white-blue-red, "
                                 "with a torn sheet of paper between them", "cutout"),
    "totu_party_control": ("idea", "a heavy round rubber stamp of a regional party committee on an appointment order, "
                                   "and a red desk telephone", "cutout"),
    "totu_great_power_patriotism": ("idea", "a red Soviet banner and a gilded double-headed eagle standard side by side, "
                                            "with a golden Orthodox cross", "cutout"),
    # timed spirits from the same tree
    "totu_social_payments": ("idea", "a green Soviet savings book, a pension certificate and a few rouble banknotes",
                             "cutout"),
    "totu_cooperatives": ("idea", "a small hand-painted cooperative cafe signboard, a bunch of keys and a stamped "
                                  "property deed", "cutout"),
    "totu_rsfsr_budget": ("idea", "a pile of rouble banknotes on an accounting ledger with a white-blue-red ribbon "
                                  "bookmark", "cutout"),
    "totu_baltic_crackdown": ("idea", "a Soviet BTR armoured personnel carrier at night beside a concrete barricade "
                                      "with a smouldering fire", "cutout"),
}

GORBY = "Mikhail Gorbachev (bald, the port-wine birthmark on his forehead, grey suit)"
YELTSIN = "Boris Yeltsin (tall, broad face, thick swept-back grey hair, dark suit)"
# Soviet political tree (common/national_focus/TOTU_SOV.txt); the icon name is the focus id
FOCUS_SOV = {
    "SOV_central_committee_plenum": f"{GORBY} speaking at a wooden tribune with a microphone; behind him a piece of "
                                    "red velvet curtain with a bronze Lenin profile.",
    "SOV_abolish_article_six": "a Moscow protester in a winter coat and fur hat holding up a hand-painted cardboard "
                               "placard; beside him a small red booklet of the USSR Constitution.",
    "SOV_renew_the_party": f"{GORBY} holding up an open red Communist Party membership card; a folded red party flag "
                           "behind him.",
    "SOV_third_congress_of_deputies": "Soviet people's deputies in suits in a congress hall, several of them raising "
                                      "red mandate cards, seen from the side.",
    "SOV_28th_party_congress": f"{YELTSIN} walking away from a congress tribune with a set face; a red party card "
                               "left lying on the edge of the tribune.",
    "SOV_multiparty_system": "a hand holding several small enamel lapel badges of new political parties in different "
                             "colours over a pile of homemade political leaflets.",
    "SOV_party_discipline": "Yegor Ligachev (stern grey-haired Politburo hardliner, dark suit) pointing his finger; a "
                            "red cardboard folder of party directives in front of him. He is the only "
                            "person in the picture.",
    "SOV_gorbachev_presidency": f"{GORBY} taking the presidential oath, right hand raised, the other hand on a "
                                "red-bound USSR Constitution; a Soviet flag behind him.",
    "SOV_union_referendum": "a hand dropping a paper ballot into a wooden ballot box with the Soviet coat of arms; a "
                            "flat ochre silhouette map of the USSR behind.",
    "SOV_state_emergency_committee": "the hardliners Gennady Yanayev (heavy face, combed-back hair, grey suit), "
                                     "Vladimir Kryuchkov (KGB chief, round glasses, grey hair) and Marshal Dmitry "
                                     "Yazov (army uniform with medals) behind a press-conference table with "
                                     "microphones; a tank turret behind them. Gorbachev is not in the picture.",
    "SOV_remove_gorbachev": "a white government dacha by the Black Sea seen over a wall with a guard in a dark coat at "
                            "the gate; in front an old white telephone with a cut cord.",
    "SOV_presidential_council": f"{GORBY} at a round table with three advisers in suits, papers and glasses of tea on "
                                "the table.",
    "SOV_federation_council": f"{GORBY} at the head of a table lined with small desk flags of the Soviet republics.",
    "SOV_kgb_budget": "Vladimir Kryuchkov (KGB chairman, round glasses, grey hair, dark suit); beside him a bronze "
                      "KGB sword-and-shield plaque and bundles of Soviet rouble banknotes.",
    "SOV_vice_president": "Gennady Yanayev (Soviet vice-president, heavy face, combed-back hair, dark suit) standing "
                          "next to an empty leather armchair.",
    "SOV_new_union_treaty_draft": "typed pages of a draft treaty covered with red pencil corrections, reading glasses "
                                  "and a fountain pen on them; a flat ochre map of the USSR behind.",
    "SOV_novo_ogaryovo_process": f"{GORBY} at a table with Nursultan Nazarbayev (Kazakh leader, black hair) and "
                                 f"{YELTSIN}; the white Novo-Ogaryovo manor house behind them.",
    "SOV_andropov_methods": "a framed black-and-white portrait of Yuri Andropov (thin face, glasses, grey hair); in "
                            "front a militiaman in a grey uniform checking a worker's papers.",
    "SOV_consolidate_security_services": "three Soviet peaked caps side by side: an army marshal's cap, a KGB "
                                         "officer's cap with a blue band and a militia cap; a BTR armoured vehicle "
                                         "behind them.",
    "SOV_close_the_plenum": "the Spasskaya Tower of the Kremlin at dusk with the red flag; in front heavy wooden "
                            "double doors, half closed.",
    "SOV_press_law": "a stack of freshly printed Soviet newspapers with a broken censor's rubber stamp lying on top.",
    "SOV_deal_with_yeltsin": f"{GORBY} and {YELTSIN} shaking hands; a Russian white-blue-red flag and a red Soviet "
                             "flag behind them.",
    "SOV_stop_yeltsin": f"{YELTSIN} speaking into microphones; in front of him a typed declaration crossed out with a "
                        "thick red marker. Yeltsin is the only person in the picture.",
    "SOV_union_of_sovereign_states": "a red leather treaty folder with a gold-stamped emblem; small flags of the "
                                     "Soviet republics in a desk stand behind it.",
    "SOV_soyuz_deputy_group": "Viktor Alksnis (thin, moustache, Soviet air force colonel's uniform) speaking at a "
                              "parliament microphone, holding a red deputy ID.",
    "SOV_order_in_the_baltics": "a Soviet BTR-70 armoured personnel carrier at night in front of the Vilnius TV tower, "
                                "a Lithuanian yellow-green-red flag on a pole, some smoke.",
    "SOV_state_of_emergency": "an old Soviet wooden television set showing a ballerina from Swan Lake; behind it a "
                              "T-72 tank on a Moscow street.",
    "SOV_constitutional_supervision": "Sergei Alekseyev (grey-haired Soviet lawyer, glasses, dark suit) holding the "
                                      "red USSR Constitution; brass scales of justice beside him.",
    "SOV_freedom_of_conscience": "Patriarch Alexy II in his white patriarchal cowl; golden onion domes of a Moscow "
                                 "church behind him.",
    "SOV_left_democratic_socialism": f"{GORBY} with a red carnation in his lapel, smiling; a red flag behind him.",
    "SOV_democratic_reform_movement": "Eduard Shevardnadze (white hair) and Alexander Yakovlev (bald, glasses) at a "
                                      "press table with microphones, a signed typed declaration in front.",
    "SOV_social_guarantees": "an elderly Soviet pensioner woman in a headscarf holding a green savings book; a loaf "
                             "of bread and a string shopping bag beside her.",
    "SOV_social_democratic_party": "a red enamel lapel badge with a rose, large in front; behind it a few young "
                                   "Moscow democrats with a banner.",
    "SOV_right_market_democracy": "brokers in suits shouting on the trading floor of the Moscow commodity exchange, "
                                  "a board of numbers behind them.",
    "SOV_law_on_property": "the door of a small Soviet cooperative cafe with a hand-painted sign above it, a bunch of "
                           "keys and a stamped deed in front.",
    "SOV_500_days_program": "Grigory Yavlinsky (young, dark curly hair, suit) holding a thick bound report; a desk "
                            "calculator beside him.",
    "SOV_free_prices": "Valentin Pavlov (Soviet prime minister, crew cut, heavy face, glasses); in front a shop price "
                       "tag with the old price crossed out and a higher one written by hand.",
    "SOV_yeltsin_heads_russia": f"{YELTSIN} raising his fist at a tribune with microphones; the white Russian "
                                "parliament building and a Russian tricolour behind him.",
    "SOV_rsfsr_sovereignty_in_union": "a typed declaration with a round red seal; the Russian tricolour and a red "
                                      "Soviet flag on crossed poles behind; a flat ochre map of Russia.",
    "SOV_gorbachev_yeltsin_tandem": f"{GORBY} and {YELTSIN} standing side by side at one tribune with two "
                                    "microphones.",
    "SOV_yeltsin_in_union_leadership": f"{YELTSIN} seated at a desk in a wood-panelled Kremlin office, a Soviet coat "
                                       "of arms on the wall. Yeltsin is the only person in the picture.",
    "SOV_war_of_laws": "two bronze coats of arms, of the USSR and of the RSFSR, facing each other; between them a "
                       "torn page of a typed law.",
    "SOV_bet_on_autonomies": "Mintimer Shaimiev (Tatar leader, round face, glasses, dark suit) with the green-white-"
                             "red flag of Tatarstan; a flat ochre map of the Volga region.",
    "SOV_remove_yeltsin": f"{YELTSIN} walking away, seen from the side; an empty high-backed chairman's chair at a "
                          "parliament presidium table.",
    "SOV_left_leninist_norms": "a bronze bust of Lenin on a tribune draped with red cloth; red flags behind.",
    "SOV_communist_party_of_rsfsr": "a solo portrait of Ivan Polozkov (Russian Communist leader, heavy-set, dark "
                                    "suit) alone at a party congress tribune, holding up a red party card; a red flag "
                                    "behind him. One man only, no second person anywhere.",
    "SOV_andreeva_unity": "Nina Andreeva (middle-aged Leningrad teacher, short dark hair, glasses) holding a folded "
                          "newspaper; red banners behind her. She is the only person in the picture.",
    "SOV_restore_party_control": "a stern regional party secretary at a large desk with three telephones; a portrait "
                                 "of Lenin on the wood-panelled wall.",
    "SOV_right_great_power": "a gilded double-headed eagle and a red Soviet star badge side by side over a flat ochre "
                             "map of the USSR.",
    "SOV_army_and_church": "a Soviet army general in a parade cap standing beside an Orthodox priest holding a gold "
                           "cross; church domes behind them.",
    "SOV_word_to_the_people": "an open newspaper page with a large headline; behind it protesters with red flags and "
                              "black-yellow-white imperial flags.",
}
for _name, _subject in FOCUS_SOV.items():
    ICONS[_name] = ("focus", _subject)

# Countries after the USSR keep their prompts as data, next to the focus-editor document: tools/src/focus/<TAG>_icons.json
# = {"focus": {focus id: subject}, "spirit": {picture name: subject}}; spirits use the cut-out style. The setting comes
# from SETTINGS by the name prefix (totu_ddr_ / DDR_).
for _tag in ("DDR",):
    _data = json.loads((SRC.parent / "focus" / f"{_tag}_icons.json").read_text(encoding="utf-8"))
    for _name, _subject in _data["spirit"].items():
        ICONS[_name] = ("idea", _subject, "cutout")
    for _name, _subject in _data["focus"].items():
        ICONS[_name] = ("focus", _subject)
# lettering that is part of the scene (a placard, a cover, a headline), exact Russian text
SLOGANS = {
    "SOV_abolish_article_six": "ДОЛОЙ 6 СТАТЬЮ!",
    "SOV_law_on_property": "КООПЕРАТИВ",
    "SOV_500_days_program": "500 ДНЕЙ",
    "SOV_word_to_the_people": "СЛОВО К НАРОДУ",
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


def shine_sprite(name, texture):
    """The sweep of light played when a focus completes, defined like vanilla interface/goals_shine.gfx."""
    anim = "".join(
        f'\t\tanimation = {{\n\t\t\tanimationmaskfile = "{texture}"\n'
        f'\t\t\tanimationtexturefile = "gfx/interface/goals/shine_overlay.dds"\n'
        f'\t\t\tanimationrotation = {rot}\n\t\t\tanimationlooping = no\n\t\t\tanimationtime = 0.75\n'
        f'\t\t\tanimationdelay = 0\n\t\t\tanimationblendmode = "add"\n\t\t\tanimationtype = "scrolling"\n'
        f'\t\t\tanimationrotationoffset = {{ x = 0.0 y = 0.0 }}\n\t\t\tanimationtexturescale = {{ x = 1.0 y = 1.0 }}\n'
        f'\t\t}}\n' for rot in ("-90.0", "90.0"))
    return (f'\tspriteType = {{\n\t\tname = "{name}_shine"\n\t\ttexturefile = "{texture}"\n'
            f'\t\teffectFile = "gfx/FX/buttonstate.lua"\n{anim}\t\tlegacy_lazy_load = no\n\t}}\n')


def write_sprites():
    for kind, gfx, prefix, folder in (("idea", "totu_ideas.gfx", "GFX_idea_", "ideas"),
                                      ("focus", "totu_goals.gfx", "GFX_focus_", "goals")):
        names = [n for n, (k, *_) in ICONS.items() if k == kind and (SRC / kind / f"{n}.png").exists()]
        if not names:
            continue
        blocks = [f'\tspriteType = {{\n\t\tname = "{prefix}{n}"\n\t\ttexturefile = "gfx/interface/{folder}/totu/{n}.dds"\n\t}}\n'
                  for n in names]
        if kind == "focus":
            blocks += [shine_sprite(prefix + n, f"gfx/interface/{folder}/totu/{n}.dds") for n in names]
        text = ("# GENERATED by tools/gen_icons.py - edit ICONS there, not this file.\nspriteTypes = {\n"
                + "\n".join(blocks) + "}\n")
        (ROOT / "interface" / gfx).write_text(text, encoding="utf-8", newline="\n")
        print("wrote interface/" + gfx, len(names), "sprites")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*")
    ap.add_argument("--convert-only", action="store_true")
    ap.add_argument("--jobs", type=int, default=6, help="parallel API requests")
    args = ap.parse_args()
    unknown = [n for n in args.names if n not in ICONS]
    if unknown:
        sys.exit(f"unknown icons: {unknown}")
    if not args.convert_only:
        key = api_key()
        todo = args.names or [n for n, (k, *_) in ICONS.items() if not (SRC / k / f"{n}.png").exists()]

        def one(n):
            kind, subject, *style = ICONS[n]
            style = style[0] if style else kind
            text = SLOGAN.format(SLOGANS[n]) if n in SLOGANS else NO_TEXT
            print(f"generating {n} ({kind}, {MODEL})", flush=True)
            try:
                where = SETTINGS[country_of(n)]
                png = generate(STYLE[style].format(subject=subject, text=text, setting=where[style],
                                                   press=where["press"]), key)
            except RuntimeError as e:
                print(f"  {n}: {e}", flush=True)
                return
            out = SRC / kind / f"{n}.png"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(png)
            print(f"  done {n}", flush=True)

        with ThreadPoolExecutor(args.jobs) as pool:
            list(pool.map(one, todo))
    for n, (kind, *_) in ICONS.items():
        png = SRC / kind / f"{n}.png"
        if png.exists():
            dst = ROOT / "gfx/interface" / ("ideas" if kind == "idea" else "goals") / "totu" / f"{n}.dds"
            dst.parent.mkdir(parents=True, exist_ok=True)
            to_game(png, kind).save(dst)
    write_sprites()


if __name__ == "__main__":
    main()
