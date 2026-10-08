"""States of the rebuild zone: provinces, owner and cores, economy split from the vanilla states they replace,
victory points and names. Works on the in-memory states of tools/build_world_1990.py."""
import re
from collections import Counter, defaultdict

import numpy as np
from scipy import ndimage

from .assemble import anchor_of, vp_markers
from .common import px_of

CATEGORIES = [(8_000_000, "megalopolis", 12), (5_000_000, "metropolis", 10), (3_000_000, "large_city", 8),
              (1_500_000, "city", 6), (800_000, "large_town", 5), (300_000, "town", 4), (100_000, "rural", 2),
              (0, "pastoral", 1)]
SLOT_TYPES = ("arms_factory", "industrial_complex", "dockyard")
FORTS = ("bunker", "coastal_bunker")     # stay with the country that built them when a province goes to the zone
SINGLE_LEVELS = ("air_base", "anti_air_building", "synthetic_refinery", "fuel_silo", "radar_station", "rocket_site",
                 "nuclear_reactor")
RESOURCES = ("oil", "aluminium", "rubber", "tungsten", "steel", "chromium")
TEMPLATE = """state = {{
\tid = {sid}
\tname = "STATE_{sid}"
\tmanpower = {manpower}
{resources}\tstate_category = {category}

\thistory = {{
\t}}

\tprovinces = {{
\t}}

\tlocal_supplies = {supplies:.1f}
}}
"""


def category(pop):
    return next((name, slots) for lim, name, slots in CATEGORIES if pop >= lim)


def largest_remainder(total, weights):
    w = np.asarray(weights, float)
    if total <= 0 or w.sum() <= 0:
        return [0] * len(w)
    q = total * w / w.sum()
    out = np.floor(q).astype(int)
    for i in np.argsort(-(q - out))[: int(total - out.sum())]:
        out[i] += 1
    return out.tolist()


def state_numbers(text):
    mp = int(re.search(r"manpower\s*=\s*(\d+)", text).group(1))
    res = Counter()
    m = re.search(r"resources\s*=\s*\{([^}]*)\}", text)
    if m:
        for k, v in re.findall(r"(\w+)\s*=\s*([\d.]+)", m.group(1)):
            res[k] += float(v)
    ls = re.search(r"local_supplies\s*=\s*([\d.]+)", text)
    return mp, res, float(ls.group(1)) if ls else 0.0


def hist_buildings(hist):
    b = next((v for k, _, v in hist if k == "buildings"), [])
    state_lv = {k: int(float(v)) for k, _, v in b if not k.isdigit() and isinstance(v, str)}
    prov_lv = {int(k): v for k, _, v in b if k.isdigit()}
    return state_lv, prov_lv


def hist_vps(hist):
    return {int(v[0][0]): float(v[1][0]) for k, _, v in hist if k == "victory_points" and isinstance(v, list)}


def _num(v):
    return str(int(v)) if float(v).is_integer() else str(v)


def apply(zm, vm, zone, states, names, vp_names=None):
    """vp_names: vanilla province -> (en, ru) victory point names (vanilla localisation + names.VP_NAMES)."""
    vp_names = vp_names or {}
    tags = {u.tag for u in zone.units}
    zstates = sorted(s for s, st in states.items() if st["owner"] in tags)
    tot = defaultdict(lambda: {"manpower": 0, "res": Counter(), "supplies": 0.0, "lv": Counter(), "infra": [],
                               "single": Counter()})
    prov_items, vanilla_vp = [], {}
    for s in zstates:
        st = states[s]
        mp, res, ls = state_numbers(st["text"])
        t = tot[st["owner"]]
        t["manpower"] += mp
        t["res"] += res
        t["supplies"] += ls
        lv, pl = hist_buildings(st["hist"])
        for k in SLOT_TYPES:
            t["lv"][k] += lv.get(k, 0)
        for k in SINGLE_LEVELS:
            t["single"][k] = max(t["single"][k], lv.get(k, 0))
        t["infra"].append((lv.get("infrastructure", 1), len(st["provs"])))
        prov_items += list(pl.items())
        vanilla_vp.update(hist_vps(st["hist"]))
    for s, st in states.items():             # outside states that lost provinces to the zone
        if s in zstates:
            continue
        lost = {p for p in st["provs"] if p in zm.pool}
        if lost:
            _, pl = hist_buildings(st["hist"])
            prov_items += [(p, [x for x in v if x[0] not in FORTS]) for p, v in pl.items() if p in lost]
            vanilla_vp.update({p: v for p, v in hist_vps(st["hist"]).items() if p in lost})
            _drop_province_history(st["hist"], lost)
            st["provs"] = [p for p in st["provs"] if p not in lost]
            assert st["provs"], f"state {s} lost all its provinces to the zone"
    for p, s_out in zm.moved_out.items():
        states[s_out]["provs"].append(p)
    old = {s: states.pop(s) for s in zstates}

    objs = ndimage.find_objects(zm.ids)
    unit_px = Counter()
    for p, ui in zm.zone_provs.items():
        bb = objs[p - 1]
        unit_px[ui] += int((zm.ids[bb] == p).sum())
    city_pop = Counter()
    for c, p in zm.city_prov:
        city_pop[zm.zone_provs[p]] += c.pop
    coastal_unit = {ui for p, ui in zm.zone_provs.items() if zm.provs[p].coastal}
    keys = [u.key for u in zone.units]
    capitals = {tag: zm.unit_state[keys.index(key)] for tag, key in zone.country_capitals}
    for tag in sorted(tags):
        uis = [ui for ui, u in enumerate(zone.units) if u.tag == tag]
        t = tot[tag]
        area = np.array([unit_px[ui] for ui in uis], float)
        cpop = np.array([city_pop[ui] for ui in uis], float)
        rural = max(0.0, t["manpower"] - cpop.sum())
        mps = largest_remainder(t["manpower"], cpop + rural * area / area.sum())
        cats = [category(m) for m in mps]
        slots = [c[1] for c in cats]
        lv = {k: _split_capped(t["lv"][k], [(cpop[j] + 1) * (k != "dockyard" or uis[j] in coastal_unit)
                                           for j in range(len(uis))], slots) for k in SLOT_TYPES}
        res = {k: largest_remainder(int(round(t["res"][k])), area) for k in RESOURCES if t["res"][k]}
        sup = (t["supplies"] * area / area.sum()).tolist()
        infra = int(round(sum(a * b for a, b in t["infra"]) / max(1, sum(b for _, b in t["infra"]))))
        main = next((ui for ui in uis if zm.unit_state[ui] == capitals.get(tag)), uis[int(np.argmax(cpop))])
        for j, ui in enumerate(uis):
            u, sid = zone.units[ui], zm.unit_state[ui]
            provs = sorted(p for p, x in zm.zone_provs.items() if x == ui)
            provs += sorted(lake for lake, x in zm.lake_unit.items() if x == ui)
            base = _best_old_state(zm, vm, provs, old)
            cores = [tag] + ([c for c in old[base]["cores"] if c != tag] if base else [])
            claims = [c for c in old[base]["claims"] if c not in cores] if base else []
            blv = [("infrastructure", "=", str(max(1, infra)))]
            blv += [(k, "=", str(lv[k][j])) for k in SLOT_TYPES if lv[k][j]]
            if ui == main:
                blv += [(k, "=", str(v)) for k, v in t["single"].items() if v]
            rtxt = "".join(f"\t\t{k} = {res[k][j]}\n" for k in res if res[k][j])
            text = TEMPLATE.format(sid=sid, manpower=mps[j], category=cats[j][0], supplies=sup[j],
                                   resources=f"\tresources = {{\n{rtxt}\t}}\n" if rtxt else "")
            states[sid] = dict(file=f"{sid}-{_ascii(u.name_en)}.txt", text=text, provs=provs,
                               hist=[("buildings", "=", blv)], owner=tag, cores=cores, claims=claims)
            names.STATE_NAMES[sid] = (u.name_en, u.name_ru)
    _province_items(zm, vm, states, prov_items)
    _victory_points(zm, vm, states, vanilla_vp, vp_names, names)
    report = [f"states: {len(old)} vanilla states rebuilt into {len(zone.units)}, "
              f"{len(zm.moved_out)} provinces moved to outside states"]
    return {"capitals": capitals, "report": report}


def _ascii(name):
    name = name.replace("ü", "ue").replace("ö", "oe").replace("ä", "ae")
    return re.sub(r"[^A-Za-z0-9 ()\-]", "", name)


def _split_capped(total, weight, slots_left):
    """Levels by weight, each state within its free slots; what does not fit goes to the next best state."""
    out = [0] * len(weight)
    for _ in range(int(total)):
        free = [i for i in range(len(weight)) if slots_left[i] > 0 and weight[i] > 0]
        if not free:
            break
        i = max(free, key=lambda k: weight[k] / (out[k] + 1))
        out[i] += 1
        slots_left[i] -= 1
    return out


def _best_old_state(zm, vm, provs, old):
    pm = np.isin(zm.ids, provs)
    under = Counter(vm.ids[pm].tolist())
    score = Counter({s: sum(under.get(p, 0) for p in st["provs"]) for s, st in old.items()})
    best = score.most_common(1)
    return best[0][0] if best and best[0][1] else None


def _drop_province_history(hist, provs):
    keys = {str(p) for p in provs}
    hist[:] = [it for it in hist if not (it[0] == "victory_points" and isinstance(it[2], list)
                                         and it[2][0][0] in keys)]
    for k, _, v in hist:
        if k == "buildings":
            v[:] = [it for it in v if it[0] not in keys]


def _province_items(zm, vm, states, prov_items):
    """Province buildings (naval bases, bunkers, landmarks) follow the vanilla place of their old province."""
    naval_at = {}
    for f in vm.buildings:
        if f[1] == "naval_base_spawn":
            r, c = px_of(float(f[2]), float(f[4]))
            naval_at.setdefault(int(vm.ids[r, c]), (r, c))
    objs = ndimage.find_objects(vm.ids)
    state_of = {p: s for s, st in states.items() for p in st["provs"]}
    for p, items in prov_items:
        point = naval_at.get(p)
        if point is None:
            bb = objs[p - 1]
            a = anchor_of(vm.ids[bb] == p)
            point = (a[0] + bb[0].start, a[1] + bb[1].start)
        target = int(zm.ids[point])
        for key, _, val in items:
            t = target
            if key == "naval_base" and not zm.provs[t].coastal:
                t = _nearest_coastal(zm, state_of.get(t), point)
            if t is None or t not in state_of:
                continue
            hist = states[state_of[t]]["hist"]
            b = next((v for k, _, v in hist if k == "buildings"), None)
            if b is None:
                b = []
                hist.append(("buildings", "=", b))
            blk = next((v for k2, _, v in b if k2 == str(t)), None)
            if blk is None:
                blk = []
                b.append((str(t), "=", blk))
            blk.append((key, "=", val))


def _nearest_coastal(zm, sid, point):
    cands = [p for p, ui in zm.zone_provs.items() if zm.provs[p].coastal and zm.unit_state.get(ui) == sid]
    if not cands:
        return None
    return min(cands, key=lambda p: (zm.anchor[p][0] - point[0]) ** 2 + (zm.anchor[p][1] - point[1]) ** 2)


def _victory_points(zm, vm, states, vanilla_vp, vp_names, names):
    """A vanilla victory point is a place: in the zone it goes to the province now under its marker (a reused id may
    lie elsewhere), unless a 1990 city is there; the cities of the zone get theirs."""
    state_of = {p: s for s, st in states.items() for p in st["provs"]}
    city_at = {p for _, p in zm.city_prov}
    marks = vp_markers(vm)
    place = {p: int(zm.ids[marks[p]]) if p in zm.pool and p in marks else p for p in vanilla_vp}
    vps, came_from = {}, {}
    for p, v in sorted(vanilla_vp.items()):
        q = place[p]
        if q not in state_of or (p in zm.pool and (q in city_at or q not in zm.zone_provs)):
            continue                 # a 1990 city is there, or the place lies outside the zone (vanilla's Freiburg
                                     # marker is west of the real Rhine) where the provinces keep their own points
        if v > vps.get(q, 0):
            vps[q], came_from[q] = v, p
    for q, p in came_from.items():
        if q != p and p in vp_names:
            names.VP_NAMES[q] = vp_names[p]
    for c, p in zm.city_prov:
        vps[p] = max(vps.get(p, 0), c.vp)
        if place.get(p) != p or p not in vp_names:
            names.VP_NAMES[p] = (c.name_en, c.name_ru)
    for p in list(names.VP_NAMES):
        if p in zm.pool and p not in vps:
            del names.VP_NAMES[p]
    for p, v in sorted(vps.items()):
        hist = states[state_of[p]]["hist"]
        if any(k == "victory_points" and isinstance(x, list) and x[0][0] == str(p) for k, _, x in hist):
            continue
        hist.append(("victory_points", "=", [(str(p), None, None), (_num(v), None, None)]))
