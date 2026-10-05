"""Stage 4: cities (victory points) and states (groups of provinces inside one country)."""
import heapq
import math

import numpy as np
from scipy import ndimage as ndi
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

from . import countries, data, geo

MAXP = 13        # states with more provinces are split
SPLIT_TARGET = 8
MINP = 3         # states with fewer provinces are merged into a neighbour
MAXMERGE = 11
ISLAND_JOIN = 90  # px: tiny island groups join the nearest same-country group within this distance

DIR_EN = ["North", "North-East", "East", "South-East", "South", "South-West", "West", "North-West"]
DIR_RU = ["север", "северо-восток", "восток", "юго-восток", "юг", "юго-запад", "запад", "северо-запад"]


def km2_per_px(lat):
    return (111.195 * math.cos(math.radians(lat)) / (geo.W / 360.0)) * (111.195 / (geo.H / (geo.LAT_TOP - geo.LAT_BOT)))


# ---------------------------------------------------------------- cities
def load_places(w, rast):
    """Natural Earth populated places mapped to land provinces. Returns list of dicts."""
    C, P = rast["C"], w["P"]
    idx = ndi.distance_transform_edt(C != 0, return_distances=True, return_indices=True)
    dist, ind = idx
    out = []
    for f in data.load_ne("ne_10m_populated_places"):
        p = f["properties"]
        if p["FEATURECLA"] in ("Scientific station", "Meteorological Station", "Historic place"):
            continue
        pop = (p["POP1990"] or 0) * 1000 or int((p["POP_MAX"] or 0) * 0.75)
        cap = p["FEATURECLA"] in ("Admin-0 capital", "Admin-0 capital alt")
        x, y = geo.lonlat_to_px(p["LONGITUDE"], p["LATITUDE"])
        xi, yi = int(x), int(y)
        if not (0 <= xi < geo.W and 0 <= yi < geo.H):
            continue
        if C[yi, xi] != 0:
            if dist[yi, xi] > 6:
                continue
            yi, xi = int(ind[0][yi, xi]), int(ind[1][yi, xi])
        out.append(dict(name=p["NAME"], ascii=p["NAMEASCII"], ru=p.get("NAME_RU"), pop=pop, cap=cap,
                        adm0=p["ADM0_A3"], prov=int(P[yi, xi]), lon=p["LONGITUDE"], lat=p["LATITUDE"], x=xi, y=yi))
    return out


# ---------------------------------------------------------------- partition helpers
def kmeans(pts, wts, k, rng, iters=12):
    n = len(pts)
    k = min(k, n)
    c = [pts[rng.choice(n, p=wts / wts.sum())]]
    for _ in range(1, k):
        d = np.min(((pts[:, None, :] - np.array(c)[None]) ** 2).sum(-1), axis=1) * wts
        if d.sum() <= 0:
            c.append(pts[rng.integers(n)])
        else:
            c.append(pts[rng.choice(n, p=d / d.sum())])
    c = np.array(c, float)
    for _ in range(iters):
        lab = np.argmin(((pts[:, None, :] - c[None]) ** 2).sum(-1), axis=1)
        for j in range(k):
            m = lab == j
            if m.any():
                c[j] = (pts[m] * wts[m, None]).sum(0) / wts[m].sum()
    lab = np.argmin(((pts[:, None, :] - c[None]) ** 2).sum(-1), axis=1)
    return lab


def make_contiguous(provs, lab, nbr):
    """Re-assign provinces cut off from the main body of their cluster to a neighbouring cluster."""
    provs = list(provs)
    pos = {p: i for i, p in enumerate(provs)}
    for _ in range(4):
        rows, cols = [], []
        for p in provs:
            for q in nbr.get(p, ()):
                if q in pos and lab[pos[p]] == lab[pos[q]]:
                    rows.append(pos[p]); cols.append(pos[q])
        g = coo_matrix((np.ones(len(rows)), (rows, cols)), shape=(len(provs),) * 2)
        nc, cl = connected_components(g, directed=False)
        key = {}
        for i in range(len(provs)):
            key.setdefault((lab[i], cl[i]), []).append(i)
        main = {}
        for (l, c), mem in key.items():
            if l not in main or len(mem) > len(key[(l, main[l])]):
                main[l] = c
        changed = False
        for (l, c), mem in key.items():
            if main[l] == c:
                continue
            for i in mem:
                votes = {}
                for q in nbr.get(provs[i], ()):
                    if q in pos and lab[pos[q]] != l:
                        votes[lab[pos[q]]] = votes.get(lab[pos[q]], 0) + 1
                if votes:
                    lab[i] = max(votes, key=votes.get)
                    changed = True
        if not changed:
            break
    return lab


# ---------------------------------------------------------------- states
def build(w, rast, places, seed=1990):
    rng = np.random.default_rng(seed)
    regions = rast["regions"]
    kind, region, unit, area = w["kind"], w["region"], w["unit"], w["area"]
    cx, cy = w["cx"], w["cy"]
    N = w["N"]
    land = [i for i in range(1, N + 1) if kind[i] == "land"]
    tag_of = {i: regions[region[i]]["tag"] for i in land}
    nbr = {}
    for a, b in zip(w["adj_a"], w["adj_b"]):
        a, b = int(a), int(b)
        if kind[a] == "land" and kind[b] == "land" and tag_of[a] == tag_of[b]:
            nbr.setdefault(a, set()).add(b)
            nbr.setdefault(b, set()).add(a)
    # initial groups: (region, unit)
    atoms = {}
    for i in land:
        atoms.setdefault((int(region[i]), int(unit[i])), []).append(i)
    groups = []   # dict(provs, tag, region, sfx_en, sfx_ru)
    for (r, u), provs in sorted(atoms.items()):
        tag = regions[r]["tag"]
        if len(provs) <= MAXP:
            groups.append(dict(provs=provs, tag=tag, sfx=None, sfx_region=None))
            continue
        k = math.ceil(len(provs) / SPLIT_TARGET)
        pts = np.array([[cx[p], cy[p] * (geo.W / 360) / (geo.H / (geo.LAT_TOP - geo.LAT_BOT))] for p in provs])
        wts = np.array([area[p] for p in provs], float)
        lab = kmeans(pts, wts, k, rng)
        lab = make_contiguous(provs, lab, nbr)
        ac = (pts * wts[:, None]).sum(0) / wts.sum()
        parts = {}
        for p, l in zip(provs, lab):
            parts.setdefault(int(l), []).append(p)
        names = {}
        for l, mem in parts.items():
            m = np.array([[cx[p], cy[p]] for p in mem])
            c = (m * np.array([area[p] for p in mem])[:, None]).sum(0) / sum(area[p] for p in mem)
            dx, dy = c[0] - ac[0], -(c[1] - ac[1])
            if len(parts) == 2:
                d = (2 if dx > 0 else 6) if abs(dx) > abs(dy) else (0 if dy > 0 else 4)
            else:
                ang = math.degrees(math.atan2(dy, dx))
                d = int(round(((90 - ang) % 360) / 45.0)) % 8
            names.setdefault(d, []).append(l)
        for d, ls in names.items():
            for j, l in enumerate(ls):
                sfx = (DIR_EN[d], DIR_RU[d]) if len(ls) == 1 else (f"{DIR_EN[d]} {j + 1}", f"{DIR_RU[d]} {j + 1}")
                groups.append(dict(provs=parts[l], tag=tag, sfx=sfx, sfx_region=r))
    # merge small groups
    gid = {}
    for g_i, g in enumerate(groups):
        for p in g["provs"]:
            gid[p] = g_i
    alive = set(range(len(groups)))

    def neighbours(g_i):
        s = set()
        for p in groups[g_i]["provs"]:
            for q in nbr.get(p, ()):
                if gid[q] != g_i:
                    s.add(gid[q])
        return s

    def centroid(g_i):
        ps = groups[g_i]["provs"]
        a = np.array([area[p] for p in ps], float)
        return (np.array([cx[p] for p in ps]) * a).sum() / a.sum(), (np.array([cy[p] for p in ps]) * a).sum() / a.sum()

    def merge(a, b):  # b absorbs a
        ga, gb = groups[a], groups[b]
        if sum(area[p] for p in ga["provs"]) > sum(area[p] for p in gb["provs"]):
            gb["sfx"] = ga["sfx"]
            gb["sfx_region"] = ga["sfx_region"]
        gb["provs"] = gb["provs"] + ga["provs"]
        for p in ga["provs"]:
            gid[p] = b
        alive.discard(a)

    changed = True
    while changed:
        changed = False
        order = sorted((g for g in alive if len(groups[g]["provs"]) < MINP), key=lambda g: len(groups[g]["provs"]))
        for g in order:
            if g not in alive or len(groups[g]["provs"]) >= MINP:
                continue
            cands = [h for h in neighbours(g) if len(groups[h]["provs"]) + len(groups[g]["provs"]) <= MAXMERGE]
            if cands:
                h = min(cands, key=lambda h: len(groups[h]["provs"]))
                merge(g, h)
                changed = True
                continue
            # island: nearest group of the same country
            c0 = centroid(g)
            best, bd = None, ISLAND_JOIN
            for h in alive:
                if h == g or groups[h]["tag"] != groups[g]["tag"]:
                    continue
                if len(groups[h]["provs"]) + len(groups[g]["provs"]) > MAXMERGE:
                    continue
                c1 = centroid(h)
                d = math.hypot(c0[0] - c1[0], c0[1] - c1[1])
                if d < bd:
                    best, bd = h, d
            if best is not None:
                merge(g, best)
                changed = True
    states = []
    for g in alive:
        grp = groups[g]
        states.append(dict(provs=sorted(grp["provs"]), tag=grp["tag"], sfx=grp["sfx"], sfx_region=grp["sfx_region"]))
    # main region (by area) names the state
    for s in states:
        by = {}
        for p in s["provs"]:
            by[int(region[p])] = by.get(int(region[p]), 0) + int(area[p])
        s["region"] = max(by, key=by.get)
        s["area_px"] = int(sum(area[p] for p in s["provs"]))
        s["cx"] = float(sum(cx[p] * area[p] for p in s["provs"]) / s["area_px"])
        s["cy"] = float(sum(cy[p] * area[p] for p in s["provs"]) / s["area_px"])
    # ids: grouped by country (alphabetical), then north->south, west->east
    states.sort(key=lambda s: (s["tag"], round(s["cy"] / 40), s["cx"]))
    for i, s in enumerate(states, start=1):
        s["id"] = i
    state_of = np.zeros(N + 1, np.int32)
    for s in states:
        for p in s["provs"]:
            state_of[p] = s["id"]
    print(f"states: {len(states)} (provinces/state avg {len(land) / len(states):.1f})", flush=True)
    return states, state_of
