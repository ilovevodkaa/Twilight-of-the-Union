"""The rebuild zone put together: which vanilla provinces go into the zone, the new province raster, vanilla id
reuse by overlap, attributes of the new provinces, the state of every unit, strategic regions."""
from collections import Counter, defaultdict
from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage
from scipy.optimize import linear_sum_assignment

from . import cities as cities_mod
from .common import px_of, stable_seed
from .partition import partition
from .raster import label_zone
from .vanilla import Province

VP_BONUS = 1_000_000
URBAN_POP = 1_000_000
FOUR = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], bool)


@dataclass
class ZoneMap:
    ids: np.ndarray                     # the new province raster
    provs: dict                         # every province definition after the rebuild
    labels: object = None               # raster.Labels of the zone
    cities: list = field(default_factory=list)
    zone_provs: dict = field(default_factory=dict)     # province of the zone -> unit index
    unit_state: dict = field(default_factory=dict)     # unit index -> state id
    pool: set = field(default_factory=set)             # vanilla province ids that went into the zone
    moved_out: dict = field(default_factory=dict)      # province of a rebuilt state left outside -> outside state
    city_prov: list = field(default_factory=list)      # (ZoneCity, province)
    anchor: dict = field(default_factory=dict)         # province -> (row, col) farthest from its border
    changed: set = field(default_factory=set)          # provinces whose shape changed (zone + reshaped neighbours)
    region_of: dict = field(default_factory=dict)      # zone province or lake -> strategic region
    lake_unit: dict = field(default_factory=dict)      # lake of a rebuilt state -> unit index


def vp_markers(vm):
    """Province -> (row, col) of its victory point marker (unitstacks type 38)."""
    out = {}
    for f in vm.unitstacks:
        if f[1] == "38":
            out[int(f[0])] = px_of(float(f[2]), float(f[4]))
    return out


def anchor_of(mask):
    d = ndimage.distance_transform_edt(np.pad(mask, 1))[1:-1, 1:-1]
    r, c = np.unravel_index(np.argmax(d), d.shape)
    return int(r), int(c)


def _bbox(m, pad=0):
    rr, cc = np.nonzero(m)
    return (slice(max(0, rr.min() - pad), rr.max() + 1 + pad), slice(max(0, cc.min() - pad), cc.max() + 1 + pad))


def assemble(vm, georef, zone, states, log=print):
    labels = label_zone(vm, georef, zone)
    n = max(vm.provs) + 1
    is_land = np.zeros(n, bool)
    for p, v in vm.provs.items():
        is_land[p] = v.kind == "land"
    land = is_land[vm.ids]
    zone_px = land & (labels.unit >= 0)
    total = np.bincount(vm.ids[land], minlength=n)
    inzone = np.bincount(vm.ids[zone_px], minlength=n)
    pool = set(np.nonzero((total > 0) & (2 * inzone >= total))[0].tolist())
    # a state outside the zone never loses all its provinces: where vanilla drew it over real zone land (vanilla
    # "Vorarlberg" covers the Allgäu), its least-zone province stays whole and the zone gives up those pixels
    tags = {u.tag for u in zone.units}
    protected = set()
    for st in states.values():
        lp = [p for p in st["provs"] if vm.provs[p].kind == "land"]
        if st["owner"] not in tags and lp and all(p in pool for p in lp):
            protected.add(min(lp, key=lambda p: inzone[p] / max(1, total[p])))
    pool -= protected
    if protected:
        zone_px &= ~np.isin(vm.ids, list(protected))
        log(f"zone: provinces {sorted(protected)} stay with their outside states")
    in_pool = np.zeros(n, bool)
    in_pool[list(pool)] = True
    pool_px = in_pool[vm.ids]
    ids = vm.ids.copy()
    changed = set()

    # pool pixels outside the zone -> nearest kept province; kept provinces lose their zone pixels
    for x0, y0, x1, y1 in labels.boxes:
        sl = np.s_[y0:y1, x0:x1]
        keep = land[sl] & ~zone_px[sl] & ~pool_px[sl]
        give = pool_px[sl] & ~zone_px[sl]
        if give.any():
            _, (ri, ci) = ndimage.distance_transform_edt(~keep, return_indices=True)
            sub = ids[sl]
            sub[give] = vm.ids[sl][ri[give], ci[give]]
            changed |= set(np.unique(sub[give]).tolist())
        changed |= set(np.unique(vm.ids[sl][zone_px[sl] & ~pool_px[sl]]).tolist())
    work = sorted(changed)                     # a reshaped kept province keeps only its biggest part; the
    for _ in range(10):                        # pieces it gives away may split the receiver, so repeat
        receivers = set()
        for p in work:
            bb = _bbox(ids == p, pad=12)
            m = (ids[bb] == p) & ~zone_px[bb]
            parts, k = ndimage.label(m, FOUR)
            if k > 1:
                main = int(np.argmax(np.bincount(parts.ravel())[1:])) + 1
                stray = (parts > 0) & (parts != main)
                other = land[bb] & ~zone_px[bb] & (ids[bb] != p) & ~in_pool[ids[bb]]
                _, (ri, ci) = ndimage.distance_transform_edt(~other, return_indices=True)
                sub = ids[bb]
                sub[stray] = sub[ri[stray], ci[stray]]
                receivers |= set(np.unique(sub[stray]).tolist())
        changed |= receivers
        if not receivers:
            break
        work = sorted(receivers)
    log(f"zone: {len(pool)} vanilla provinces in the pool, {len(changed)} neighbours reshaped")

    # every unit cut into provinces
    city_list = cities_mod.select(zone, labels, georef, land)
    by_unit = defaultdict(list)
    for c in city_list:
        by_unit[c.unit].append(c)
    owner_of = {p: s["owner"] for s in states.values() for p in s["provs"]}
    area, count = Counter(), Counter()
    for p in pool:
        area[owner_of.get(p)] += int(total[p])
        count[owner_of.get(p)] += 1
    newlab = np.zeros(ids.shape, np.int32)
    meta = []                                  # (unit index, seed (row, col) or None)
    for ui, u in enumerate(zone.units):
        um = zone_px & (labels.unit == ui)
        bb = _bbox(um)
        mask = um[bb]
        r0, c0 = bb[0].start, bb[1].start
        mean = area[u.tag] / count[u.tag] if count[u.tag] else 300.0
        n_target = int(round(mask.sum() / (mean / zone.density)))
        fixed = [(c.row - r0, c.col - c0) for c in by_unit[ui]]
        lab, seeds = partition(mask, vm.height[bb], fixed, n_target, stable_seed(u.key))
        sub = newlab[bb]
        sub[lab > 0] = lab[lab > 0] + len(meta)
        meta += [(ui, None if s is None else (s[0] + r0, s[1] + c0)) for s in seeds]
    log(f"zone: {len(meta)} new provinces for {len(zone.units)} units, {len(city_list)} cities")

    # vanilla province ids by overlap, plus a bonus where a vanilla victory point marker lies
    pool_list = sorted(pool)
    prow = {p: i for i, p in enumerate(pool_list)}
    m = newlab > 0
    cost = np.zeros((len(pool_list), len(meta)))
    for (p, j), k in Counter(zip(vm.ids[m].tolist(), (newlab[m] - 1).tolist())).items():
        if p in prow:
            cost[prow[p], j] -= k
    for p, (r, c) in vp_markers(vm).items():
        if p in prow and newlab[r, c] > 0:
            cost[prow[p], newlab[r, c] - 1] -= VP_BONUS
    rows_, cols_ = linear_sum_assignment(cost)
    assert len(rows_) == len(pool_list), "fewer new provinces than vanilla ones in the zone"
    final = np.zeros(len(meta), np.int64)
    final[cols_] = [pool_list[i] for i in rows_]
    nxt = n
    for j in range(len(meta)):
        if final[j] == 0:
            final[j] = nxt
            nxt += 1
    ids[m] = np.concatenate([[0], final])[newlab[m]]

    zm = ZoneMap(ids=ids, provs=dict(vm.provs), labels=labels, cities=city_list, pool=pool)
    zm.zone_provs = {int(final[j]): ui for j, (ui, _) in enumerate(meta)}
    zm.changed = (changed - pool) | set(zm.zone_provs)
    _define(zm, vm, city_list, zone.name)
    zm.city_prov = _one_city_per_province(city_list, ids, log)
    _states_of_units(zm, vm, zone, states, zone_px)
    _regions(zm, vm, zone)
    return zm


def _one_city_per_province(city_list, ids, log):
    """Cities closer than a province (the Ruhr, Mannheim/Heidelberg) share one: it keeps the biggest city's name and
    a victory point value for their summed population."""
    by_prov = defaultdict(list)
    for c in city_list:
        by_prov[int(ids[c.row, c.col])].append(c)
    out = []
    for p, cs in by_prov.items():
        top = max(cs, key=lambda c: c.pop)
        if len(cs) > 1:
            pop = sum(c.pop for c in cs)
            log(f"province {p}: {', '.join(c.name_en for c in cs)} share one province, named {top.name_en}")
            top = cities_mod.ZoneCity(top.name_en, top.name_ru, pop, cities_mod.vp_value(pop), top.unit, top.row,
                                      top.col)
        out.append((top, p))
    return out


def _define(zm, vm, city_list, key):
    """Definitions (colour, coastal, terrain, continent) and anchors of the zone and reshaped provinces."""
    ids = zm.ids
    used = {p.rgb for pid, p in vm.provs.items() if pid not in zm.pool}
    rng = np.random.default_rng(stable_seed(key))
    big = [(c.row, c.col) for c in city_list if c.pop >= URBAN_POP]
    sea = np.isin(ids, [p for p, v in vm.provs.items() if v.kind == "sea"])
    near_sea = ndimage.binary_dilation(sea, FOUR) & ~sea
    coastal = set(np.unique(ids[near_sea]).tolist())
    objs = ndimage.find_objects(ids)
    for pid in sorted(zm.changed):
        bb = objs[pid - 1]
        pm = ids[bb] == pid
        a = anchor_of(pm)
        zm.anchor[pid] = (a[0] + bb[0].start, a[1] + bb[1].start)
        old = vm.provs.get(pid)
        if pid not in zm.zone_provs:                     # a reshaped kept province: only the coast may change
            zm.provs[pid] = Province(pid, old.rgb, old.kind, pid in coastal, old.terrain, old.continent)
            continue
        under = vm.ids[bb][pm]
        terr = Counter(vm.provs[int(v)].terrain for v in under if vm.provs[int(v)].kind == "land")
        urban = any(ids[r, c] == pid for r, c in big)
        terrain = next((t for t, _ in terr.most_common() if t != "urban" or urban), "plains")
        cont = Counter(vm.provs[int(v)].continent for v in under).most_common(1)[0][0]
        rgb = old.rgb if old else None
        while rgb is None or rgb in used:
            rgb = tuple(int(v) for v in rng.integers(1, 255, 3))
        used.add(rgb)
        zm.provs[pid] = Province(pid, rgb, "land", pid in coastal, terrain, int(cont))


def _states_of_units(zm, vm, zone, states, zone_px):
    tags = {u.tag for u in zone.units}
    zstates = sorted(s for s, st in states.items() if st["owner"] in tags)
    state_of = {p: s for s, st in states.items() for p in st["provs"]}
    srow = {s: i for i, s in enumerate(zstates)}
    cost = np.zeros((len(zstates), len(zone.units)))
    for (p, ui), k in Counter(zip(vm.ids[zone_px].tolist(), zm.labels.unit[zone_px].tolist())).items():
        s = state_of.get(p)
        if s in srow:
            cost[srow[s], ui] -= k
    r, c = linear_sum_assignment(cost)
    assert len(r) == len(zstates), "fewer units than vanilla states of the zone countries"
    for i, ui in zip(r, c):
        zm.unit_state[int(ui)] = zstates[i]
    nxt = max(states) + 1
    for ui in range(len(zone.units)):
        if ui not in zm.unit_state:
            zm.unit_state[ui] = nxt
            nxt += 1
    # provinces of rebuilt states left outside the zone go to the outside state they border most
    rebuilt = set(zstates)
    left = [p for s in zstates for p in states[s]["provs"] if p not in zm.pool and vm.provs[p].kind == "land"]
    for p in left:
        bb = _bbox(zm.ids == p, pad=1)
        sub = zm.ids[bb]
        ring = ndimage.binary_dilation(sub == p, FOUR) & (sub != p)
        nb = Counter(state_of.get(int(q)) for q in sub[ring] if int(q) not in zm.pool)
        nb = [(k, s) for s, k in nb.items() if s is not None and s not in rebuilt]
        assert nb, f"province {p} of a rebuilt state is outside the zone and has no outside neighbour"
        zm.moved_out[p] = max(nb)[1]
    # lakes of rebuilt states -> the unit of the land around them
    for s in zstates:
        for p in states[s]["provs"]:
            if vm.provs[p].kind != "lake":
                continue
            bb = _bbox(vm.ids == p, pad=3)
            ring = ndimage.binary_dilation(vm.ids[bb] == p, FOUR, iterations=2)
            u = zm.labels.unit[bb][ring]
            u = u[u >= 0]
            if len(u):
                zm.lake_unit[p] = int(np.bincount(u).argmax())
            else:
                _, (ri, ci) = ndimage.distance_transform_edt(zm.labels.unit < 0, return_indices=True)
                r0, c0 = _bbox(vm.ids == p)[0].start, _bbox(vm.ids == p)[1].start
                zm.lake_unit[p] = int(zm.labels.unit[ri[r0, c0], ci[r0, c0]])


def _regions(zm, vm, zone):
    """Zone provinces: the vanilla region under most of their pixels; then a whole unit (with its lakes) moves into
    the region holding most of the unit's pixels."""
    region_v = {p: rid for rid, r in vm.regions.items() for p in r.items}
    objs = ndimage.find_objects(zm.ids)
    weight = defaultdict(Counter)
    for pid, ui in zm.zone_provs.items():
        bb = objs[pid - 1]
        under = vm.ids[bb][zm.ids[bb] == pid]
        for v, k in Counter(under.tolist()).items():
            weight[ui][region_v.get(v)] += k
    for ui in range(len(zone.units)):
        rid = weight[ui].most_common(1)[0][0]
        for pid, u in zm.zone_provs.items():
            if u == ui:
                zm.region_of[pid] = rid
        for lake, u in zm.lake_unit.items():
            if u == ui:
                zm.region_of[lake] = rid
