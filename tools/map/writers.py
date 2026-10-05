"""Text writers for every generated mod file."""
import re
import shutil
import unicodedata
from pathlib import Path

import numpy as np

from . import geo, regions as rg
from .world import CONT_NAMES, CONT

ROOT = Path(__file__).resolve().parent.parent.parent
HEIGHT = 9.5


def w_text(path, text, bom=False, newline="\n"):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig" if bom else "utf-8", newline=newline) as f:
        f.write(text)


def ascii_name(s, maxlen=40):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")
    return (s or "x")[:maxlen]


def q(s):
    return s.replace("\\", "").replace('"', "'").replace("\n", " ")


def xz(w, p):
    return w["rx"][p] + 0.5, geo.H - w["ry"][p] - 0.5


# ------------------------------------------------------------------ map files
def definition(w, terr, path):
    rows = ["0;0;0;0;land;false;unknown;0"]
    for i in range(1, w["N"] + 1):
        r, g, b = w["colors"][i]
        k = w["kind"][i]
        if k == "land":
            rows.append(f"{i};{r};{g};{b};land;{'true' if w['coastal'][i] else 'false'};{terr[i]};{int(w['cont'][i])}")
        elif k == "sea":
            rows.append(f"{i};{r};{g};{b};sea;false;ocean;0")
        else:
            rows.append(f"{i};{r};{g};{b};lake;false;lakes;0")
    w_text(path, "\n".join(rows) + "\n", newline="\r\n")


def default_map(N, path):
    w_text(path, f'''definitions = "definition.csv"
provinces = "provinces.bmp"
terrain = "terrain.bmp"
rivers = "rivers.bmp"
terrain_definition = "common/terrain/00_terrain.txt"
heightmap = "heightmap.bmp"
tree_definition = "trees.bmp"
continent = "continent.txt"
adjacency_rules = "adjacency_rules.txt"
adjacencies = "adjacencies.csv"
climate = "climate.txt"
ambient_object = "ambient_object.txt"
seasons = "seasons.txt"

# Palette indices of trees.bmp that count as trees (3 = forest, 4 = jungle)
tree = {{ 3 4 7 10 }}

max_provinces = {N + 1}
''')


def continents(path):
    w_text(path, "continents = {\n" + "".join(f"\t{c}\n" for c in CONT_NAMES) + "}\n")


def adjacencies(rows, path):
    lines = ["From;To;Type;Through;start_x;start_y;stop_x;stop_y;adjacency_rule_name;Comment"]
    for a, b, thr, name in rows:
        lines.append(f"{a};{b};sea;{thr};-1;-1;-1;-1;;{name}")
    lines.append("-1;-1;;;;;;;;")
    w_text(path, "\n".join(lines) + "\n")


def adjacency_rules(path):
    w_text(path, "# No special adjacency rules are used by the generated map.\n")


STATE_BUILDINGS = ["arms_factory", "industrial_complex", "air_base", "anti_air_building", "synthetic_refinery",
                   "fuel_silo", "radar_station", "rocket_site", "nuclear_reactor", "supply_node"]


def buildings(S, w, path):
    """state-level buildings sit around the state's main province; bunker / coastal_bunker / naval_base
    are province-level (first column = province id)."""
    P, kind = w["P"], w["kind"]
    lines = []
    off = [(0, 0), (4, 2), (-4, 2), (4, -2), (-4, -2), (0, 4), (0, -4), (6, 0), (-6, 0), (8, 3)]
    for s in S:
        p = s["capital_prov"]
        x0, z0 = xz(w, p)
        for j, b in enumerate(STATE_BUILDINGS):
            dx, dz = off[j % len(off)]
            sea = w["sea_adj"][p][0] if w["sea_adj"][p] else 0
            lines.append(f"{s['id']};{b};{x0 + dx:.2f};{HEIGHT:.2f};{z0 + dz:.2f};0.00;0")
        # dockyard on the coast (first coastal province of the state)
        cp = next((q for q in s["provs"] if w["coastal"][q]), None)
        if cp:
            x1, z1 = xz(w, cp)
            lines.append(f"{s['id']};dockyard;{x1:.2f};{HEIGHT:.2f};{z1:.2f};0.00;{w['sea_adj'][cp][0]}")
    cp_pos = w.get("coast_pos", {})
    for p in range(1, w["N"] + 1):
        if kind[p] != "land":
            continue
        x, z = xz(w, p)
        lines.append(f"{p};bunker;{x:.2f};{HEIGHT:.2f};{z:.2f};0.00;0")
        if w["coastal"][p]:
            cx_, cz_, sea = cp_pos.get(p, (x, z, w["sea_adj"][p][0]))
            lines.append(f"{p};coastal_bunker;{cx_:.2f};{HEIGHT:.2f};{cz_:.2f};0.00;{sea}")
            lines.append(f"{p};naval_base;{cx_:.2f};{HEIGHT:.2f};{cz_:.2f};0.00;{sea}")
    w_text(path, "\n".join(lines) + "\n")


def coast_positions(w):
    """For every coastal land province: a pixel on its sea shore and the sea province there."""
    P, kind = w["P"], w["kind"]
    res = {}
    best = {}
    for sa, sb in ((np.s_[:, :-1], np.s_[:, 1:]), (np.s_[:-1, :], np.s_[1:, :])):
        pa, pb = P[sa], P[sb]
        yy, xx = np.indices(pa.shape)
        for u, v in ((pa, pb), (pb, pa)):
            m = (kind[u] == "land") & (kind[v] == "sea")
            lp, sp, x, y = u[m], v[m], xx[m], yy[m]
            d = (x - w["rx"][lp]) ** 2 + (y - w["ry"][lp]) ** 2
            for l, s_, xx_, yy_, dd in zip(lp, sp, x, y, d):
                cur = best.get(l)
                if cur is None or dd < cur[0]:
                    best[l] = (dd, xx_, yy_, s_)
    for l, (dd, x, y, s_) in best.items():
        res[int(l)] = (x + 0.5, geo.H - y - 0.5, int(s_))
    return res


def unitstacks(w, path):
    lines = []
    for p in range(1, w["N"] + 1):
        x, z = xz(w, p)
        lines.append(f"{p};0;{x:.2f};{HEIGHT:.2f};{z:.2f};0.00;0.00")
    w_text(path, "\n".join(lines) + "\n")


def per_state(S, path):
    w_text(path, "".join(f"{s['id']};{s['capital_prov']}\n" for s in S))


def supply_nodes(S, path):
    w_text(path, "".join(f"1 {s['capital_prov']}\n" for s in S))


def railways(rails, path):
    w_text(path, "".join(f"{lvl} {len(p)} {' '.join(map(str, p))}\n" for lvl, p in rails))


# ------------------------------------------------------------------ states
def state_file(s, vps, path_dir):
    vp_txt = ""
    if s["vps"]:
        vp_txt = "\t\t" + "\n\t\t".join(f"victory_points = {{\n\t\t\t{p} {vps[p]['value']}\n\t\t}}" for p in s["vps"]) + "\n"
    txt = f"""state={{
\tid={s['id']}
\tname="STATE_{s['id']}"
\tmanpower = {s['pop']}
\tstate_category = {s['category']}

\thistory={{
\t\towner = {s['tag']}
{vp_txt}\t\tbuildings = {{
\t\t\tinfrastructure = {s['infra']}
\t\t}}
\t\tadd_core_of = {s['tag']}
\t}}

\tprovinces={{
\t\t{' '.join(map(str, s['provs']))}
\t}}
}}
"""
    w_text(Path(path_dir) / f"{s['id']}-{ascii_name(s['name_en'])}.txt", txt)


# ------------------------------------------------------------------ strategic regions / supply
def strategic_region(rid, provs, lat, sea, continental, naval, path_dir, fname):
    nt = ("\tnaval_terrain = " + naval + "\n") if naval else ""
    txt = f"""strategic_region={{
\tid={rid}
\tname="STRATEGICREGION_{rid}"
\tprovinces={{
\t\t{' '.join(map(str, sorted(provs)))}
\t}}
{nt}\tweather={{
{rg.weather_block(lat, sea, continental)}
\t}}
}}
"""
    w_text(Path(path_dir) / f"{rid}-{ascii_name(fname)}.txt", txt)


def supply_area(aid, states, path_dir):
    w_text(Path(path_dir) / f"{aid}-area.txt", f"""supply_area = {{
\tid = {aid}
\tname = "SUPPLYAREA_{aid}"
\tvalue = 6
\tstates = {{ {' '.join(map(str, sorted(states)))} }}
}}
""")


# ------------------------------------------------------------------ localisation
def loc_file(path, lang, entries, bom=True):
    lines = [f"l_{lang}:"] + [f' {k}:0 "{q(v)}"' for k, v in entries]
    w_text(path, "\n".join(lines) + "\n", bom=True)


# ------------------------------------------------------------------ countries
def country_files(table, caps, root):
    root = Path(root)
    tags_lines = ["# GENERATED by tools/build_map.py - edit the script, not this file."]
    colors = ["# GENERATED by tools/build_map.py - edit the script, not this file.", ""]
    for tag in sorted(table):
        c = table[tag]
        fname = ascii_name(c["name"], 60).replace("_", " ") + ".txt"
        c["file"] = fname
        tags_lines.append(f'{tag} = "countries/{fname}"')
        w_text(root / "common" / "countries" / fname,
               f"graphical_culture = {c['gfx']}\ngraphical_culture_2d = {c['gfx2']}\ncolor = {{ {c['color'][0]} {c['color'][1]} {c['color'][2]} }}\n")
        colors.append(f"{tag} = {{\n\tcolor = rgb {{ {c['color'][0]} {c['color'][1]} {c['color'][2]} }}\n"
                      f"\tcolor_ui = rgb {{ {c['ui'][0]} {c['ui'][1]} {c['ui'][2]} }}\n}}")
    w_text(root / "common" / "country_tags" / "totu_countries.txt", "\n".join(tags_lines) + "\n")
    w_text(root / "common" / "countries" / "colors.txt", "\n".join(colors) + "\n")


STUB_POLITICS = """
set_politics = {
	ruling_party = neutrality
	last_election = "1989.1.1"
	election_frequency = 48
	elections_allowed = no
}
set_popularities = {
	democratic = 0
	fascism = 0
	communism = 0
	neutrality = 100
}
"""


def history_files(table, caps, root):
    hdir = Path(root) / "history" / "countries"
    existing = {p.name.split(" - ")[0]: p for p in hdir.glob("*.txt")}
    for tag, c in table.items():
        cap = caps[tag]
        if tag in existing:   # keep the hand-written history, only fix the capital
            p = existing[tag]
            txt = p.read_text(encoding="utf-8-sig")
            label = {"USA": "Washington DC", "SOV": "Moscow"}.get(tag, c["name"])
            txt = re.sub(r"^capital\s*=\s*\d+[^\n]*", f"capital = {cap} # {label}", txt, count=1, flags=re.M)
            bom = p.read_bytes().startswith(b"\xef\xbb\xbf")
            w_text(p, txt, bom=bom)
            continue
        fname = f"{tag} - {ascii_name(c['name'], 60).replace('_', ' ')}.txt"
        w_text(hdir / fname, f"capital = {cap} # {c['name']}\n{STUB_POLITICS}", bom=True)
