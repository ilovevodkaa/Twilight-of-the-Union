"""Builds the 1 January 1990 political setup on top of the vanilla HOI4 map.

Reads the vanilla game install (states, buildings, colours, flags) and writes:
  history/states/*.txt             every vanilla state with 1990 owner / cores / claims, 1936 date blocks removed
  map/buildings.txt                vanilla positions, state ids fixed for provinces moved between states
  history/countries/*.txt          one file per 1990 country (SOV and USA are hand-written and left alone)
  common/country_tags/totu_1990_countries.txt + common/countries/*.txt   tags vanilla does not have
  common/countries/colors.txt      dark map colours for every tag
  localisation/*/replace/totu_countries_l_*.yml   1990 names for all ideologies
  gfx/flags/**                     flags for the new tags

Usage:  python tools/build_world_1990.py [--game "D:/steam/steamapps/common/Hearts of Iron IV"]
"""
import argparse
import colorsys
import re
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from world1990 import borders, countries, flags, names  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
GAME_GUESSES = [r"D:\steam\steamapps\common\Hearts of Iron IV",
                r"C:\Program Files (x86)\Steam\steamapps\common\Hearts of Iron IV"]
HANDWRITTEN = {"SOV", "USA"}          # history files with real content, not generated
IDEOLOGIES = ["democratic", "communism", "neutrality", "fascism"]
GOV_PARTY = {"D": "democratic", "C": "communism", "N": "neutrality"}
# 1936 setup that must not run in 1990. The IF/if blocks are DLC-dependent 1936 transfers (Belgian Congo states to
# COG with Gotterdammerung, Bosporus DMZ) - transfer_state_to on a 1990 owner crashes the game while loading.
DROP_KEYS = {"owner", "controller", "add_core_of", "add_claim_by", "set_compliance", "set_resistance",
             "start_resistance", "set_demilitarized_zone", "add_dynamic_modifier", "set_variable", "IF", "if"}
DATE = re.compile(r"^\d+\.\d+\.\d+(\.\d+)?$")

# tags vanilla does not have: tag -> (file name, graphical culture, 2d culture)
NEW_TAGS = {
    "PRK": ("North Korea", "asian_gfx", "asian_2d"),
    "MRI": ("Mauritius", "african_gfx", "african_2d"),
    "SEY": ("Seychelles", "african_gfx", "african_2d"),
    "COM": ("Comoros", "african_gfx", "african_2d"),
    "STP": ("Sao Tome and Principe", "african_gfx", "african_2d"),
    "KIR": ("Kiribati", "asian_gfx", "asian_2d"),
    "TUV": ("Tuvalu", "asian_gfx", "asian_2d"),
    "NRU": ("Nauru", "asian_gfx", "asian_2d"),
    "BRB": ("Barbados", "southamerican_gfx", "southamerican_2d"),
}

CAPITALS = {   # where the vanilla 1936 capital is wrong for 1990
    "GER": 51, "CHI": 524, "PRC": 608, "PAK": 440, "FSA": 992, "BRB": 692, "BAS": 308, "KIR": 639, "TUV": 643,
    "NRU": 725, "MRI": 707, "SEY": 709, "COM": 708, "STP": 705, "PRK": 527, "ISR": 454, "MOR": 461,
}


# ------------------------------------------------------------------ Clausewitz text
TOKEN = re.compile(r'"[^"]*"|[{}=<>]|[^\s{}=<>"]+')


def tokenize(text):
    return TOKEN.findall(re.sub(r"#[^\n]*", "", text))


def parse_block(tokens, i):
    """Parse statements until the closing brace. Returns (items, next index); item = (key, op, value)."""
    items = []
    while i < len(tokens):
        t = tokens[i]
        if t == "}":
            return items, i + 1
        if i + 1 < len(tokens) and tokens[i + 1] in ("=", "<", ">"):
            op = tokens[i + 1]
            if tokens[i + 2] == "{":
                val, i = parse_block(tokens, i + 3)
            else:
                val, i = tokens[i + 2], i + 3
            items.append((t, op, val))
        elif t == "{":                      # anonymous block (rare)
            val, i = parse_block(tokens, i + 1)
            items.append((None, None, val))
        else:                               # bare value inside a list
            items.append((t, None, None))
            i += 1
    return items, i


def dump(items, depth):
    pad = "\t" * depth
    out = []
    for k, op, v in items:
        if op is None and v is None:
            out.append(pad + k)
        elif isinstance(v, list):
            if v and all(o is None and w is None for _, o, w in v):   # flat list
                out.append(f"{pad}{k} {op} {{ {' '.join(x for x, _, _ in v)} }}")
            else:
                head = pad + "{" if k is None else f"{pad}{k} {op} {{"
                out += [head, *dump(v, depth + 1), pad + "}"]
        else:
            out.append(f"{pad}{k} {op} {v}")
    return out


def find_block(text, key):
    m = re.search(r"\b" + key + r"\s*=\s*\{", text)
    if not m:
        return None
    d = 0
    for k in range(m.end() - 1, len(text)):
        if text[k] == "{":
            d += 1
        elif text[k] == "}":
            d -= 1
            if d == 0:
                return m.start(), m.end(), k
    raise ValueError("unbalanced " + key)


# ------------------------------------------------------------------ states
def load_states(game):
    states = {}
    for f in (game / "history/states").glob("*.txt"):
        text = f.read_text(encoding="utf-8-sig")
        sid = int(re.search(r"\bid\s*=\s*(\d+)", text).group(1))
        a, b, c = find_block(text, "provinces")
        provs = [int(x) for x in re.sub(r"#[^\n]*", "", text[b:c]).split()]
        h = find_block(text, "history")
        hist, _ = parse_block(tokenize(text[h[1]:h[2] + 1]), 0)
        owner = next(v for k, _, v in hist if k == "owner")
        cores = [v for k, _, v in hist if k == "add_core_of"]
        states[sid] = dict(file=f.name, text=text, provs=provs, hist=hist, owner36=owner, cores36=cores)
    return states


def move_province_history(src, dst, prov):
    """Victory points and province buildings of a province follow it to its new state."""
    for it in [it for it in src if it[0] == "victory_points" and isinstance(it[2], list) and it[2][0][0] == prov]:
        src.remove(it)
        dst.append(it)
    sb = next((it[2] for it in src if it[0] == "buildings"), [])
    moving = [it for it in sb if it[0] == prov]
    if moving:
        db = next((it[2] for it in dst if it[0] == "buildings"), None)
        if db is None:
            db = []
            dst.append(("buildings", "=", db))
        for it in moving:
            sb.remove(it)
            db.append(it)


def assign(states):
    for sid, s in states.items():
        s["owner"] = borders.STATE_OWNER.get(sid, borders.OWNER_REMAP.get(s["owner36"], s["owner36"]))
    for p, dst in borders.PROVINCE_MOVES.items():
        src = next(sid for sid, s in states.items() if p in s["provs"])
        states[src]["provs"].remove(p)
        states[dst]["provs"].append(p)
        move_province_history(states[src]["hist"], states[dst]["hist"], str(p))
    sovereign = set(countries.COUNTRIES)
    missing = {s["owner"] for s in states.values()} - sovereign
    assert not missing, f"owners without a COUNTRIES entry: {missing}"
    for sid, s in states.items():
        o = s["owner"]
        cores = [] if sid in borders.NO_OWNER_CORE else [o]
        for c in s["cores36"]:
            if c not in sovereign and c not in cores:          # releasables (UKR, BLR, SCO, ...) keep their cores
                cores.append(c)
        for c in borders.EXTRA_CORES.get(sid, []):
            if c not in cores:
                cores.append(c)
        s["cores"] = cores
        s["claims"] = [c for c in borders.EXTRA_CLAIMS.get(sid, []) if c not in cores and c != o]


def write_states(states, out):
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    for sid, s in sorted(states.items()):
        keep = [it for it in s["hist"] if it[0] not in DROP_KEYS and not (it[0] and DATE.match(it[0]))]
        head = [("owner", "=", s["owner"])] + [("add_core_of", "=", c) for c in s["cores"]] + \
               [("add_claim_by", "=", c) for c in s["claims"]]
        hist = "history = {\n" + "\n".join(dump(head + keep, 2)) + "\n\t}"
        text = s["text"]
        h = find_block(text, "history")
        text = text[:h[0]] + hist + text[h[2] + 1:]
        a, b, c = find_block(text, "provinces")
        text = text[:b] + "\n\t\t" + " ".join(map(str, s["provs"])) + "\n\t" + text[c:]
        (out / s["file"]).write_text(text, encoding="utf-8")     # state files must not have a BOM


# ------------------------------------------------------------------ buildings.txt
def province_raster(game):
    img = np.array(Image.open(game / "map/provinces.bmp").convert("RGB"))
    key = (img[..., 0].astype(np.int64) << 16) | (img[..., 1].astype(np.int64) << 8) | img[..., 2]
    col2id = {}
    for line in (game / "map/definition.csv").read_text(encoding="latin-1").splitlines():
        p = line.split(";")
        if len(p) > 4 and p[0].isdigit():
            col2id[(int(p[1]) << 16) | (int(p[2]) << 8) | int(p[3])] = int(p[0])
    uk, inv = np.unique(key.ravel(), return_inverse=True)
    return np.array([col2id.get(int(k), 0) for k in uk])[inv].reshape(key.shape)


def write_buildings(game, states, out):
    moved = borders.PROVINCE_MOVES
    lines = (game / "map/buildings.txt").read_text(encoding="utf-8-sig").splitlines()
    if not moved:
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return
    P = province_raster(game)
    H, W = P.shape
    fixed = 0
    for i, line in enumerate(lines):
        f = line.split(";")
        if len(f) < 7:
            continue
        x, z = float(f[2]), float(f[4])
        prov = int(P[min(H - 1, max(0, int(H - z))), min(W - 1, max(0, int(x)))])
        if prov in moved and int(f[0]) != moved[prov]:
            f[0] = str(moved[prov])
            lines[i] = ";".join(f)
            fixed += 1
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("buildings.txt: moved", fixed, "positions")


# ------------------------------------------------------------------ countries
def capital_of(tag, states, vanilla_caps):
    own = {sid for sid, s in states.items() if s["owner"] == tag}
    for cand in (CAPITALS.get(tag), vanilla_caps.get(tag)):
        if cand in own:
            return cand
    # fall back to the biggest owned state
    return max(own, key=lambda sid: len(states[sid]["provs"]))


def vanilla_capitals(game):
    caps = {}
    for f in (game / "history/countries").glob("*.txt"):
        m = re.search(r"^\s*capital\s*=\s*(\d+)", f.read_text(encoding="utf-8-sig", errors="ignore"), re.M)
        if m:
            caps[f.name[:3]] = int(m.group(1))
    return caps


def write_country_history(states, game, out):
    caps = vanilla_capitals(game)
    for p in out.glob("*.txt"):
        if p.name[:3] not in HANDWRITTEN:
            p.unlink()
    for tag, (en, ru, adj, adj_ru, gov) in sorted(countries.COUNTRIES.items()):
        cap = capital_of(tag, states, caps)
        if tag in HANDWRITTEN:
            text = next(out.glob(tag + " - *.txt")).read_text(encoding="utf-8-sig")
            have = int(re.search(r"^\s*capital\s*=\s*(\d+)", text, re.M).group(1))
            assert have == cap, f"{tag}: hand-written capital {have}, expected {cap}"
            continue
        dem, com, neu, fas = countries.POP.get(tag, countries.GOV_POP[gov])
        party = GOV_PARTY[gov]
        elections = "yes" if gov == "D" else "no"
        body = (f"capital = {cap}\n\n"
                f"set_research_slots = 3\n"
                f"set_stability = 0.5\nset_war_support = 0.2\n\n"
                f"set_politics = {{\n\truling_party = {party}\n\tlast_election = \"1988.1.1\"\n"
                f"\telection_frequency = 48\n\telections_allowed = {elections}\n}}\n"
                f"set_popularities = {{\n\tdemocratic = {dem}\n\tcommunism = {com}\n"
                f"\tneutrality = {neu}\n\tfascism = {fas}\n}}\n")
        safe = re.sub(r"[^A-Za-z0-9 ]", "", en)
        (out / f"{tag} - {safe}.txt").write_text(body, encoding="utf-8-sig")


def new_tags(root, game):
    tags = root / "common/country_tags"
    shutil.rmtree(tags, ignore_errors=True)
    tags.mkdir(parents=True)
    lines = [f'{t} = "countries/{n}.txt"' for t, (n, _, _) in NEW_TAGS.items()]
    (tags / "totu_1990_countries.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    cdir = root / "common/countries"
    shutil.rmtree(cdir, ignore_errors=True)
    cdir.mkdir(parents=True)
    for t, (n, g3d, g2d) in NEW_TAGS.items():
        (cdir / f"{n}.txt").write_text(
            f"graphical_culture = {g3d}\ngraphical_culture_2d = {g2d}\n\ncolor = {{ 80 80 80 }}\n", encoding="utf-8")


# ------------------------------------------------------------------ colours
def parse_colors(game):
    """vanilla colors.txt + per-country files -> {tag: (r, g, b) 0..1}"""
    out = {}
    text = re.sub(r"#[^\n]*", "", (game / "common/countries/colors.txt").read_text(encoding="utf-8-sig"))
    for m in re.finditer(r"\b([A-Z0-9]{3})\s*=\s*\{\s*color\s*=\s*(rgb|RGB|HSV|hsv)?\s*\{([^}]*)\}", text):
        tag, kind, vals = m.group(1), (m.group(2) or "rgb").lower(), [float(v) for v in m.group(3).split()]
        out[tag] = colorsys.hsv_to_rgb(*vals) if kind == "hsv" else tuple(v / 255 for v in vals)
    tagfile = (game / "common/country_tags/00_countries.txt").read_text(encoding="utf-8-sig")
    for tag, path in re.findall(r'^\s*([A-Z0-9]{3})\s*=\s*"([^"]+)"', tagfile, re.M):
        if tag in out:
            continue
        f = game / "common" / path
        if f.exists():
            m = re.search(r"color\s*=\s*(?:rgb|RGB)?\s*\{([^}]*)\}", f.read_text(encoding="utf-8-sig", errors="ignore"))
            if m:
                out[tag] = tuple(float(v) / 255 for v in m.group(1).split()[:3])
    return out


def vivid(rgb):
    """Vanilla colour with its hue kept, pushed to a saturated, mid-bright tone that reads well on the black sea."""
    h, s, v = colorsys.rgb_to_hsv(*rgb)
    if s > 0.08:                       # leave greys/whites grey
        s = min(0.85, max(0.5, s * 1.15))
    v = min(0.88, max(0.6, v))
    return colorsys.hsv_to_rgb(h, s, v)


COLOR_DEPTH = 0.70        # brightness of every map colour (1.0 = palette as written)
COLOR_SAT = 1.12          # saturation boost that keeps the darker colours rich instead of muddy


def deepen(rgb):
    h, s, v = colorsys.rgb_to_hsv(*rgb)
    return colorsys.hsv_to_rgb(h, min(0.95, s * COLOR_SAT), v * COLOR_DEPTH)


def hexrgb(h):
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def write_colors(game, root):
    base = parse_colors(game)
    tags = set(base) | set(countries.COUNTRIES) | set(NEW_TAGS)
    lines = ["# Twilight of the Union: saturated map colours (generated by tools/build_world_1990.py)", ""]
    colors = {}
    for tag in sorted(tags):
        if tag in countries.COLOR:
            c = hexrgb(countries.COLOR[tag])
        else:
            c = vivid(base.get(tag, (0.5, 0.5, 0.5)))
        c = deepen(c)
        colors[tag] = c
        r, g, b = (int(round(x * 255)) for x in c)
        # UI colour: same hue, a little brighter, so it stays readable on the dark interface
        h, s, v = colorsys.rgb_to_hsv(*c)
        ur, ug, ub = (int(round(x * 255)) for x in colorsys.hsv_to_rgb(h, s, min(1, v * 1.15 + 0.05)))
        lines += [f"{tag} = {{", f"\tcolor = rgb {{ {r} {g} {b} }}", f"\tcolor_ui = rgb {{ {ur} {ug} {ub} }}", "}"]
    (root / "common/countries/colors.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return colors


# ------------------------------------------------------------------ localisation
THE = ("United", "Union", "Netherlands", "Philippines", "Bahamas", "Gambia", "Maldives", "Seychelles", "Comoros",
       "Solomon", "Central African", "Dominican", "Czech")


def sub_ideologies(game):
    """Leader sub-ideologies (conservatism, populism, ...). The game looks up TAG_<sub-ideology> before
    TAG_<ideology> for the country name, and vanilla has unrelated keys like TUR_populism, so all get a 1990 name."""
    subs = []
    for f in (game / "common/ideologies").glob("*.txt"):
        items, _ = parse_block(tokenize(f.read_text(encoding="utf-8-sig")), 0)
        for _, _, ideo in (it for it in items if it[0] == "ideologies"):
            for _, _, body in ideo:
                for k, _, v in body if isinstance(body, list) else []:
                    if k == "types" and isinstance(v, list):
                        subs += [name for name, _, _ in v if name]
    return sorted(set(subs))


def write_loc(root, game):
    en, ru = [], []
    suffixes = [""] + ["_" + i for i in IDEOLOGIES + sub_ideologies(game)]
    for tag, (n_en, n_ru, a_en, a_ru, _) in sorted(countries.COUNTRIES.items()):
        d_en = ("the " + n_en) if n_en.startswith(THE) else n_en
        for suffix in suffixes:
            en += [(f"{tag}{suffix}", n_en), (f"{tag}{suffix}_DEF", d_en), (f"{tag}{suffix}_ADJ", a_en)]
            ru += [(f"{tag}{suffix}", n_ru), (f"{tag}{suffix}_DEF", n_ru), (f"{tag}{suffix}_ADJ", a_ru)]
    places_en = [(f"STATE_{s}", e) for s, (e, _) in names.STATE_NAMES.items()] + \
                [(f"VICTORY_POINTS_{p}", e) for p, (e, _) in names.VP_NAMES.items()]
    places_ru = [(f"STATE_{s}", r) for s, (_, r) in names.STATE_NAMES.items()] + \
                [(f"VICTORY_POINTS_{p}", r) for p, (_, r) in names.VP_NAMES.items()]
    for lang, files in (("english", {"countries": en, "places": places_en}),
                        ("russian", {"countries": ru, "places": places_ru})):
        for what, rows in files.items():
            p = root / f"localisation/{lang}/replace/totu_{what}_l_{lang}.yml"
            p.parent.mkdir(parents=True, exist_ok=True)
            body = "\n".join(f' {k}:0 "{v}"' for k, v in rows)
            p.write_text(f"l_{lang}:\n{body}\n", encoding="utf-8-sig")


# ------------------------------------------------------------------ on_actions
def block_span(text, start):
    """End index (exclusive) of the {...} block opening at or after `start`, skipping comments and strings."""
    i = text.index("{", start)
    depth = 0
    while i < len(text):
        c = text[i]
        if c == "#":
            i = text.find("\n", i)
            if i < 0:
                break
            continue
        if c == '"':
            i = text.index('"', i + 1)
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise ValueError("unbalanced block")


def strip_on_startup(game, root):
    """Vanilla on_startup effects set up 1936 (Spanish Civil War, Chinese warlords, colonies, DLC puppets). On the
    1990 world they crash the game when a campaign starts, so the mod ships copies of those files without them."""
    out = root / "common/on_actions"
    out.mkdir(parents=True, exist_ok=True)
    for p in out.glob("*.txt"):
        if not p.name.startswith("totu_"):
            p.unlink()
    n = 0
    for f in sorted((game / "common/on_actions").glob("*.txt")):
        text = f.read_text(encoding="utf-8-sig")
        pos, cut = 0, []
        for m in re.finditer(r"^\s*on_startup\s*=\s*\{", text, re.M):
            if m.start() < pos:
                continue
            end = block_span(text, m.start())
            cut.append((m.start(), end))
            pos = end
        if not cut:
            continue
        for a, b in reversed(cut):
            text = text[:a] + "\n\t# on_startup removed by Twilight of the Union (1936 setup)\n" + text[b:]
        (out / f.name).write_text(text, encoding="utf-8")       # no BOM: on_actions with a BOM fail to parse
        n += len(cut)
    print("on_actions: removed", n, "on_startup blocks")


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=next((g for g in GAME_GUESSES if Path(g).exists()), None))
    args = ap.parse_args()
    game = Path(args.game)
    states = load_states(game)
    assign(states)
    write_states(states, ROOT / "history/states")
    (ROOT / "map").mkdir(exist_ok=True)
    write_buildings(game, states, ROOT / "map/buildings.txt")
    write_country_history(states, game, ROOT / "history/countries")
    new_tags(ROOT, game)
    write_colors(game, ROOT)
    write_loc(ROOT, game)
    flags.write_flags(game, ROOT, NEW_TAGS)
    strip_on_startup(game, ROOT)
    owners = {}
    for s in states.values():
        owners[s["owner"]] = owners.get(s["owner"], 0) + 1
    print(len(states), "states,", len(owners), "countries")


if __name__ == "__main__":
    main()
