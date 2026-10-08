"""Invariants of the mod's map (what crashes or breaks the game if violated). Used by tools/check_map.py and by
the map build before it writes anything."""
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy import ndimage

from .common import MIN_PROVINCE_PX, px_of
from .vanilla import read_definitions, read_id_files, read_lines, read_province_ids

SINGLE_TYPES = ("air_base", "synthetic_refinery", "nuclear_reactor_spawn", "rocket_site_spawn", "radar_station",
                "fuel_silo", "stronghold_network")
PER_STATE_COUNTS = {**{t: 1 for t in SINGLE_TYPES}, "arms_factory": 6, "industrial_complex": 6,
                    "anti_air_building": 3}
PER_PROVINCE_TYPES = ("bunker", "supply_node", "special_project_facility_spawn")
COASTAL_TYPES = ("naval_base_spawn", "coastal_bunker", "naval_supply_hub", "naval_headquarters", "floating_harbor")


def land_near(ids, is_land, state_of, sid, r, c, radius=3):
    """The land province a building line belongs to: the one under it, else the nearest land province of its
    state within the radius (coastal models such as floating harbours stand in the water), else any land."""
    p = int(ids[r, c])
    if is_land[p]:
        return p
    sub = ids[max(0, r - radius):r + radius + 1, max(0, c - radius):c + radius + 1]
    cand = [int(q) for q in sub.ravel() if is_land[q]]
    own = [q for q in cand if state_of.get(q) == sid]
    pool = own or cand
    return max(set(pool), key=pool.count) if pool else None
MAX_SEGMENTS, MAX_PROVINCES = 62_000, 20_000


def _pairs(ids):
    out = []
    for a, b in ((ids[:, :-1], ids[:, 1:]), (ids[:-1, :], ids[1:, :])):
        m = a != b
        lo, hi = np.minimum(a[m], b[m]).astype(np.int64), np.maximum(a[m], b[m]).astype(np.int64)
        out.append(lo * 100_000 + hi)
    return np.unique(np.concatenate(out))


def x_crossings(ids):
    """2x2 blocks where four different provinces meet: the engine stops with "Map invalid X crossing" (vanilla has
    none)."""
    a, b, c, d = ids[:-1, :-1], ids[:-1, 1:], ids[1:, :-1], ids[1:, 1:]
    return (a != b) & (a != c) & (a != d) & (b != c) & (b != d) & (c != d)


def border_segments(ids):
    """Province pairs that share a border (the engine draws one border segment per touching pair)."""
    return len(_pairs(ids))


def adjacency_pairs(ids):
    p = _pairs(ids)
    return set(zip((p // 100_000).tolist(), (p % 100_000).tolist()))


class Effective:
    """The map the game loads: mod files where they exist, vanilla ones otherwise."""
    def __init__(self, root, game, mod_map=None):
        mm = Path(mod_map) if mod_map else Path(root) / "map"
        vm = Path(game) / "map"

        def pick(name):
            return mm / name if (mm / name).exists() else vm / name

        self.provs = read_definitions(pick("definition.csv"))
        self.ids = read_province_ids(pick("provinces.bmp"), self.provs)
        self.regions = read_id_files(vm / "strategicregions", "provinces")
        if (mm / "strategicregions").exists():
            self.regions.update(read_id_files(mm / "strategicregions", "provinces"))
        self.buildings = [line.split(";") for line in read_lines(pick("buildings.txt")) if line.strip()]
        self.railways = []
        for line in read_lines(pick("railways.txt")):
            f = line.split()
            if len(f) >= 3:
                self.railways.append([int(x) for x in f[2:2 + int(f[1])]])
        self.adjacency_lines = read_lines(pick("adjacencies.csv"))
        self.states = {}
        for f in (Path(root) / "history/states").glob("*.txt"):
            t = f.read_text(encoding="utf-8")
            sid = int(re.search(r"\bid\s*=\s*(\d+)", t).group(1))
            b = re.search(r"provinces\s*=\s*\{([^}]*)\}", t)
            self.states[sid] = [int(x) for x in b.group(1).split()]


def shape_problems(ids, land, sea=frozenset()):
    """Provinces under the minimum size, and provinces with a piece cut off inside other land (an exclave). Pieces
    surrounded by water are islands: vanilla has ~400 such provinces."""
    out = {}
    sizes = np.bincount(ids.ravel())
    objs = ndimage.find_objects(ids)
    is_sea = np.zeros(len(sizes), bool)
    is_sea[[s for s in sea if s < len(sizes)]] = True
    four = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], bool)
    for p in land:
        if p >= len(sizes) or sizes[p] < MIN_PROVINCE_PX:
            out[p] = f"{sizes[p] if p < len(sizes) else 0} px < {MIN_PROVINCE_PX}"
            continue
        bb = tuple(slice(max(0, s.start - 1), s.stop + 1) for s in objs[p - 1])
        sub = ids[bb]
        parts, k = ndimage.label(sub == p)
        if k > 1:
            main = int(np.argmax(np.bincount(parts.ravel())[1:])) + 1
            for j in range(1, k + 1):
                ring = ndimage.binary_dilation(parts == j, four) & (sub != p)
                if j != main and (~is_sea[sub[ring]]).any():
                    out[p] = f"{k} separate parts, one inside other land"
                    break
    return out


def problems_in(e, vanilla_bad=frozenset()):
    out = []
    ids, provs = e.ids, e.provs
    n = max(provs)
    if sorted(provs) != list(range(1, n + 1)):
        out.append("definition.csv: province ids have gaps")
    out += [f"definition.csv: colour {c} used {k} times" for c, k in Counter(p.rgb for p in provs.values()).items()
            if k > 1]
    if (ids == 0).any():
        out.append(f"provinces.bmp: {(ids == 0).sum()} pixels with a colour missing from definition.csv")
    land = {pid for pid, p in provs.items() if p.kind == "land"}
    lakes = {pid for pid, p in provs.items() if p.kind == "lake"}        # vanilla states hold their lakes too
    present = set(np.unique(ids).tolist())
    out += [f"province {p}: land province missing from provinces.bmp" for p in sorted(land - present)]
    if n > MAX_PROVINCES:
        out.append(f"{n} provinces > {MAX_PROVINCES}")
    rr, cc = np.nonzero(x_crossings(ids))
    out += [f"provinces.bmp: four provinces meet at x={c} y={r} (the engine's X crossing)" for r, c in zip(rr, cc)]
    seg = border_segments(ids)
    if seg > MAX_SEGMENTS:
        out.append(f"{seg} border segments > {MAX_SEGMENTS}")
    # states
    sids = sorted(e.states)
    if sids != list(range(1, len(sids) + 1)):
        out.append("history/states: state ids have gaps")
    owner = {}
    for sid, ps in e.states.items():
        if not ps:
            out.append(f"state {sid}: no provinces")
        for p in ps:
            if p not in land and p not in lakes:
                out.append(f"state {sid}: province {p} is neither land nor lake")
            if p in owner:
                out.append(f"province {p}: in states {owner[p]} and {sid}")
            owner[p] = sid
    out += [f"province {p}: in no state" for p in sorted((land & present) - set(owner))]
    # strategic regions
    region = {}
    for rid, r in e.regions.items():
        for p in r.items:
            if p in region:
                out.append(f"province {p}: in strategic regions {region[p]} and {rid}")
            region[p] = rid
    out += [f"province {p}: in no strategic region" for p in sorted(land - set(region))]
    for sid, ps in e.states.items():
        rs = {region.get(p) for p in ps} - {None}
        if len(rs) > 1:
            out.append(f"state {sid}: provinces in several strategic regions {sorted(rs)}")
    # buildings
    per_state, per_prov = defaultdict(Counter), defaultdict(Counter)
    is_land = np.zeros(int(ids.max()) + 1, bool)
    is_land[[p for p in land if p < len(is_land)]] = True
    for f in e.buildings:
        sid, typ = int(f[0]), f[1]
        per_state[sid][typ] += 1
        r, c = px_of(float(f[2]), float(f[4]))
        pid = int(ids[r, c])
        if typ in PER_PROVINCE_TYPES:
            per_prov[pid][typ] += 1
            if pid in owner and owner[pid] != sid:
                out.append(f"buildings.txt: {typ} of state {sid} stands in province {pid} of state {owner[pid]}")
        elif typ in PER_STATE_COUNTS:                  # the engine ignores it: "location is not within specified state"
            if pid in owner and owner[pid] != sid:
                out.append(f"buildings.txt: {typ} of state {sid} stands in province {pid} of state {owner[pid]}")
        elif typ == "naval_base_spawn":
            q = land_near(ids, is_land, owner, sid, r, c)
            if q is not None:
                per_prov[q][typ] += 1
                if q in owner and owner[q] != sid:      # the port goes to a province of the line's state
                    out.append(f"buildings.txt: naval_base_spawn of state {sid} stands at province {q} of state "
                               f"{owner[q]}")
    for sid in sids:
        for typ, k in PER_STATE_COUNTS.items():
            if per_state[sid][typ] != k:
                out.append(f"state {sid}: {per_state[sid][typ]} x {typ} in buildings.txt, needs {k}")
    for p in sorted(land & present):
        for typ in PER_PROVINCE_TYPES:
            if per_prov[p][typ] != 1:
                out.append(f"province {p}: {per_prov[p][typ]} x {typ} in buildings.txt, needs 1")
        if provs[p].coastal and not per_prov[p]["naval_base_spawn"]:      # "will likely crash the game"
            out.append(f"province {p}: coastal but no naval_base_spawn in buildings.txt")
    # railways: neighbours on the map or across a strait of adjacencies.csv
    adj = adjacency_pairs(ids) | strait_pairs(e.adjacency_lines)
    for line in e.railways:
        for a, b in zip(line, line[1:]):
            if a not in land or b not in land or (min(a, b), max(a, b)) not in adj:
                out.append(f"railways.txt: {a}-{b} are not neighbouring land provinces")
    # adjacencies.csv
    for line in e.adjacency_lines[1:]:
        f = line.split(";")
        if len(f) > 3 and f[0].lstrip("-").isdigit() and int(f[0]) >= 0:
            for p in (int(f[0]), int(f[1])):
                if p not in provs:
                    out.append(f"adjacencies.csv: province {p} does not exist")
    # coastal flag = the engine's bitmap rule (touching a sea pixel, diagonals included)
    sea_px = np.isin(ids, [pid for pid, v in provs.items() if v.kind == "sea"])
    near = ndimage.binary_dilation(sea_px, np.ones((3, 3), bool)) & ~sea_px
    coastal_px = set(np.unique(ids[near]).tolist())
    for p in sorted(land & present):
        if provs[p].coastal != (p in coastal_px):
            out.append(f"province {p}: definition.csv coastal={provs[p].coastal}, the bitmap says {p in coastal_px}")
    # shape
    water = {pid for pid, v in provs.items() if v.kind != "land"}
    for p, why in shape_problems(ids, land & present, water).items():
        if p not in vanilla_bad:
            out.append(f"province {p}: {why}")
    return out


def strait_pairs(lines):
    out = set()
    for line in lines[1:]:
        f = line.split(";")
        if len(f) > 3 and f[0].lstrip("-").isdigit() and f[1].lstrip("-").isdigit() and int(f[0]) >= 0:
            a, b = int(f[0]), int(f[1])
            out.add((min(a, b), max(a, b)))
    return out


def run(root, game, mod_map=None):
    """Problems of the mod's map that the vanilla map does not have (vanilla has its own quirks: building positions
    in a neighbouring province, a few railway segments across straits, lakes inside states)."""
    from .vanilla import VanillaMap
    vm = VanillaMap(game)
    vanilla_bad = frozenset(shape_problems(vm.ids, {p for p, v in vm.provs.items() if v.kind == "land"},
                                           {p for p, v in vm.provs.items() if v.kind != "land"}))
    baseline = set(problems_in(Effective(game, game, Path(game) / "map"), vanilla_bad))
    return [p for p in problems_in(Effective(root, game, mod_map), vanilla_bad) if p not in baseline]
