"""Stage 5: game content derived from the geometry: countries, VPs, populations, state data."""
import math

import numpy as np

from . import countries, data, geo
from .states import km2_per_px

POP_FACTOR = {"Europe": 0.97, "North America": 0.75, "South America": 0.68, "Asia": 0.70,
              "Africa": 0.48, "Oceania": 0.75, "Seven seas (open ocean)": 0.8}
POP_FACTOR_TAG = {"PRC": 0.82, "JAP": 0.99, "RAJ": 0.62, "USA": 0.76, "CAN": 0.80, "AST": 0.72, "BRA": 0.72,
                  "NEI": 0.68, "PAK": 0.55, "NGA": 0.44, "ETH": 0.45, "BAN": 0.58, "CHI": 0.85, "KOR": 0.85,
                  "PRK": 0.80, "SIA": 0.77, "VIN": 0.68, "TUR": 0.72, "PER": 0.70, "EGY": 0.56, "SAU": 0.55}
POP_1990 = {"SOV": 289_000_000, "GER": 63_250_000, "DDR": 16_110_000, "YUG": 23_800_000, "CZE": 15_600_000,
            "YEM": 9_000_000, "YES": 2_400_000, "SAF": 36_000_000, "SUD": 25_000_000, "ETH": 48_000_000,
            "ENG": 57_500_000, "MOR": 25_000_000}


def vp_value(pop, cap):
    v = math.ceil(math.sqrt(max(pop, 1) / 20000.0))
    v = max(1, min(v, 24))
    return v + (5 if cap else 0)


def category(pop, area_px, ncoast_all):
    if pop < 20_000:
        return "wasteland" if area_px > 400 else "tiny_island"
    if pop < 150_000:
        return "small_island" if ncoast_all and area_px < 250 else "pastoral"
    if pop < 500_000:
        return "rural"
    if pop < 1_000_000:
        return "town"
    if pop < 2_000_000:
        return "large_town"
    if pop < 4_000_000:
        return "city"
    if pop < 8_000_000:
        return "large_city"
    if pop < 14_000_000:
        return "metropolis"
    return "megalopolis"


def country_table(S, rast):
    """tag -> dict(name, ru, adj, adj_ru, continent, color, ...) for every tag that owns a state."""
    adm0 = data.load_ne("ne_10m_admin_0_countries")
    group = {f["properties"]["ADM0_A3"]: f["properties"]["SOV_A3"] for f in adm0}
    pop, best = {}, {}
    for f in adm0:
        p = f["properties"]
        tag = countries.owner_tag(dict(adm0_a3=p["ADM0_A3"], name=p["NAME"]), group)
        if tag is None:
            continue
        pop[tag] = pop.get(tag, 0) + (p["POP_EST"] or 0) * POP_FACTOR_TAG.get(tag, POP_FACTOR.get(p["CONTINENT"], 0.7))
        score = (p["TYPE"] != "Dependency") * 1e12 + (p["POP_EST"] or 0)
        if tag not in best or score > best[tag][0]:
            best[tag] = (score, p)
    used = sorted({s["tag"] for s in S})
    table = {}
    cont_of = {}
    for s in S:
        cont_of.setdefault(s["tag"], rast["regions"][s["region"]]["continent"])
    for tag in used:
        p = best.get(tag, (0, {}))[1]
        en = ru = adj = adj_ru = None
        if tag in countries.NAMES:
            en, ru, adj, adj_ru = countries.NAMES[tag]
        else:
            en = p.get("NAME_EN") or p.get("NAME") or tag
            ru = p.get("NAME_RU") or en
            adj, adj_ru = en, ru
        c = countries.tag_color(tag)
        gfx, gfx2 = countries.gfx_for(tag, cont_of.get(tag, "Asia"))
        table[tag] = dict(tag=tag, name=en, ru=ru, adj=adj, adj_ru=adj_ru, color=c, ui=countries.ui_color(c),
                          gfx=gfx, gfx2=gfx2, pop=int(POP_1990.get(tag, pop.get(tag, 300_000))),
                          the=en in THE)
    return table


THE = {"United States", "United Kingdom", "Soviet Union", "Netherlands", "Philippines", "United Arab Emirates",
       "Gambia", "Bahamas", "Czechoslovakia"}


def finish(S, state_of, w, rast, places, table):
    """VPs, populations, categories, names, capitals. Mutates S, returns (vps, capitals)."""
    regions = rast["regions"]
    area, kind = w["area"], w["kind"]
    tag_of_state = {s["id"]: s["tag"] for s in S}
    # --- victory points
    best = {}
    for pl in places:
        s_id = int(state_of[pl["prov"]])
        pl["state"] = s_id
        if not s_id:
            continue
        pl["tag"] = tag_of_state[s_id]
    # capital per tag
    caps = {}
    byname = {}
    for pl in places:
        if pl.get("state"):
            byname.setdefault(pl["name"], []).append(pl)
            byname.setdefault(pl["ascii"], []).append(pl)
    for tag in table:
        pick = None
        nm = countries.CAPITAL_CITY.get(tag)
        if nm:
            c = [p for p in byname.get(nm, []) if p["tag"] == tag]
            if c:
                pick = max(c, key=lambda p: p["pop"])
        if pick is None:
            c = [p for p in places if p.get("tag") == tag and p["cap"] and p["adm0"] != "ATA"]
            if c:
                pick = max(c, key=lambda p: p["pop"])
        if pick is None:
            c = [p for p in places if p.get("tag") == tag]
            if c:
                pick = max(c, key=lambda p: p["pop"])
        caps[tag] = pick
    for pl in caps.values():
        if pl:
            pl["is_cap"] = True
    cand = {}
    for pl in places:
        if not pl.get("state"):
            continue
        if pl["pop"] >= 50000 or pl.get("is_cap"):
            cur = cand.get(pl["prov"])
            if cur is None or (bool(pl.get("is_cap")), pl["pop"]) > (bool(cur.get("is_cap")), cur["pop"]):
                cand[pl["prov"]] = pl
    per_state = {}
    for pl in cand.values():
        per_state.setdefault(pl["state"], []).append(pl)
    vps = {}
    for s_id, lst in per_state.items():
        lst.sort(key=lambda p: (-(1 if p.get("is_cap") else 0), -p["pop"]))
        for pl in lst[:8]:
            vps[pl["prov"]] = dict(value=vp_value(pl["pop"], pl.get("is_cap")), name=pl["name"], ru=pl["ru"] or pl["name"],
                                   pop=pl["pop"], state=s_id)
    # --- state populations
    cityw = {}
    for pl in places:
        if pl.get("state"):
            cityw[pl["state"]] = cityw.get(pl["state"], 0) + pl["pop"]
    for s in S:
        s["km2"] = sum(area[p] * km2_per_px(float(geo.px_to_lonlat(0, w["cy"][p])[1])) for p in s["provs"])
    by_tag = {}
    for s in S:
        by_tag.setdefault(s["tag"], []).append(s)
    for tag, lst in by_tag.items():
        tk = sum(s["km2"] for s in lst) or 1
        tc = sum(cityw.get(s["id"], 0) for s in lst)
        ws = []
        for s in lst:
            a = s["km2"] / tk
            c = (cityw.get(s["id"], 0) / tc) if tc else a
            ws.append(0.3 * a + 0.7 * c + 0.002)
        tot = sum(ws)
        for s, x in zip(lst, ws):
            s["pop"] = int(table[tag]["pop"] * x / tot)
    cap_by_state = {pl["state"]: pl for pl in caps.values() if pl}
    for s in S:
        s["category"] = category(s["pop"], s["area_px"], all(w["coastal"][p] for p in s["provs"]))
        s["vps"] = sorted([p for p in s["provs"] if p in vps], key=lambda p: -vps[p]["value"])
        nreg = int(w["region"][s["vps"][0]]) if s["vps"] else s["region"]   # named after the main city's region
        r = regions[nreg]
        nm_en = r["name_en"]
        nm_ru = r["name_ru"] or r["name_en"]
        if s["sfx"] and s["sfx_region"] == nreg:
            nm_en = f"{nm_en} ({s['sfx'][0]})"
            nm_ru = f"{nm_ru} ({s['sfx'][1]})"
        cp = cap_by_state.get(s["id"])
        if cp and cp["pop"] >= 1_000_000 and cp["name"].lower() not in nm_en.lower():
            nm_en, nm_ru = cp["name"], cp["ru"] or cp["name"]   # national capitals name their state
        s["name_en"], s["name_ru"] = nm_en, nm_ru
        s["vps"] = sorted([p for p in s["provs"] if p in vps], key=lambda p: -vps[p]["value"])
        # main province: biggest VP, else biggest area
        s["capital_prov"] = s["vps"][0] if s["vps"] else max(s["provs"], key=lambda p: area[p])
        s["infra"] = 4 if s["pop"] > 2_000_000 else 3 if s["pop"] > 400_000 else 2 if s["pop"] > 60_000 else 1
    cap_state = {}
    for tag in table:
        pl = caps.get(tag)
        if pl:
            cap_state[tag] = pl["state"]
        else:
            cap_state[tag] = max(by_tag[tag], key=lambda s: s["pop"])["id"]
    return vps, cap_state
