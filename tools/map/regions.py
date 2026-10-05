"""Strategic regions (sea + land), supply areas, straits and railways."""
import math

import numpy as np
from scipy import ndimage as ndi
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from shapely.geometry import Point, shape
from skimage import measure

from . import data, geo
from .states import kmeans, make_contiguous

LAND_TARGET = 70   # provinces per land strategic region
SEA_TARGET = 20


def _scaled(w, ids):
    ar = (geo.W / 360.0) / (geo.H / (geo.LAT_TOP - geo.LAT_BOT))
    return np.array([[w["cx"][i], w["cy"][i] * ar] for i in ids])


def land_regions(S, w, rast, rng):
    """List of lists of state ids; every state in exactly one region. Grouped per landmass."""
    C = rast["C"]
    mass = measure.label(ndi.binary_dilation(C == 0, iterations=5), connectivity=2)
    st_mass = {}
    for s in S:
        p = s["capital_prov"]
        st_mass[s["id"]] = int(mass[w["ry"][p], w["rx"][p]])
    masses = {}
    for s in S:
        masses.setdefault(st_mass[s["id"]], []).append(s)
    # tiny landmasses join the nearest bigger one
    big = {m: v for m, v in masses.items() if sum(len(s["provs"]) for s in v) >= 18}
    cen = {m: np.mean([[s["cx"], s["cy"]] for s in v], 0) for m, v in masses.items()}
    for m, v in masses.items():
        if m in big:
            continue
        tgt = min(big, key=lambda b: np.hypot(*(cen[b] - cen[m])))
        big[tgt] = big[tgt] + v
    out = []
    for m, lst in big.items():
        n = sum(len(s["provs"]) for s in lst)
        k = max(1, int(round(n / LAND_TARGET)))
        if k == 1 or len(lst) < 2:
            out.append([s["id"] for s in lst])
            continue
        ar = (geo.W / 360.0) / (geo.H / (geo.LAT_TOP - geo.LAT_BOT))
        pts = np.array([[s["cx"], s["cy"] * ar] for s in lst])
        wts = np.array([len(s["provs"]) for s in lst], float)
        lab = kmeans(pts, wts, k, rng)
        for l in sorted(set(lab)):
            out.append([s["id"] for s, x in zip(lst, lab) if x == l])
    return out


def sea_regions(w, rng):
    """Group sea provinces into regions. Returns list of lists of province ids."""
    kind = w["kind"]
    sea = [i for i in range(1, w["N"] + 1) if kind[i] == "sea"]
    pos = {p: i for i, p in enumerate(sea)}
    nbr = {}
    rows, cols = [], []
    for a, b in zip(w["adj_a"], w["adj_b"]):
        a, b = int(a), int(b)
        if a in pos and b in pos:
            nbr.setdefault(a, set()).add(b)
            nbr.setdefault(b, set()).add(a)
            rows.append(pos[a]); cols.append(pos[b])
    g = coo_matrix((np.ones(len(rows)), (rows, cols)), shape=(len(sea),) * 2)
    nc, cl = connected_components_safe(g)
    out = []
    for c in range(nc):
        mem = [sea[i] for i in range(len(sea)) if cl[i] == c]
        k = max(1, int(round(len(mem) / SEA_TARGET)))
        if k == 1 or len(mem) < 2:
            out.append(mem)
            continue
        pts = _scaled(w, mem)
        wts = np.sqrt(np.array([w["area"][p] for p in mem], float))
        lab = kmeans(pts, wts, k, rng)
        lab = make_contiguous(mem, lab, nbr)
        for l in sorted(set(lab)):
            out.append([p for p, x in zip(mem, lab) if x == l])
    return out


def connected_components_safe(g):
    from scipy.sparse.csgraph import connected_components
    return connected_components(g, directed=False)


def sea_names():
    polys = []
    for f in data.load_ne("ne_10m_geography_marine_polys"):
        p = f["properties"]
        try:
            g = shape(f["geometry"])
        except Exception:
            continue
        polys.append((g.area, g, p.get("name") or p.get("NAME"), p.get("name_ru") or p.get("NAME_RU")))
    polys.sort(key=lambda t: t[0])
    return polys


def name_sea_regions(regs, w, polys):
    names = []
    used = {}
    for mem in regs:
        a = np.array([w["area"][p] for p in mem], float)
        x = float((np.array([w["cx"][p] for p in mem]) * a).sum() / a.sum())
        y = float((np.array([w["cy"][p] for p in mem]) * a).sum() / a.sum())
        # use the representative point of the biggest province for robustness
        big = mem[int(np.argmax(a))]
        lon, lat = geo.px_to_lonlat(w["rx"][big], w["ry"][big])
        pt = Point(float(lon), float(lat))
        nm = None
        for _, g, en, ru in polys:
            if g.contains(pt):
                nm = (en, ru or en)
                break
        if nm is None:
            best = min(polys, key=lambda t: t[1].distance(pt))
            nm = (best[2], best[3] or best[2])
        n = used.get(nm[0], 0) + 1
        used[nm[0]] = n
        names.append((nm[0], nm[1], n))
    # disambiguate duplicates with numbers
    out = []
    for en, ru, n in names:
        out.append((en if used[en] == 1 else f"{en} {n}", ru if used[en] == 1 else f"{ru} {n}"))
    return out


# ---------------------------------------------------------------- weather
def weather_block(lat, sea, continental):
    lines = []
    for m in range(12):
        season = math.cos((m - 0.0) / 12.0 * 2 * math.pi)       # +1 mid-winter (north)
        if lat < 0:
            season = -season
        base = 27.0 - 0.52 * abs(lat)
        amp = (0.12 + 0.30 * min(abs(lat), 60) / 60.0) * (0.55 if sea else 1.0) * (1.0 + 0.4 * continental) * abs(lat) * 0.55
        mean = base - amp * season * 0.5 - 2 * (1 if lat > 60 else 0)
        lo, hi = mean - 3.5, mean + 3.5
        cold = max(0.0, min(1.0, (2.0 - mean) / 14.0))
        snow = round(0.35 * cold, 3)
        blizz = round(0.12 * cold if lat > 52 and not sea else 0.0, 3)
        rain = round(0.25 * (1 - cold) * (0.6 if abs(lat) < 5 or 25 < abs(lat) < 33 else 1.0), 3)
        heavy = round(rain * 0.35, 3)
        mud = round(0.12 if 0 < mean < 8 else 0.02, 3)
        none = round(max(0.05, 1.0 - snow - blizz - rain - heavy - mud), 3)
        arctic = 0.2 if sea and lat > 66 else 0.0
        lines.append(f"""\t\tperiod = {{
\t\t\tbetween = {{ 0.{m} 30.{m} }}
\t\t\ttemperature = {{ {lo:.1f} {hi:.1f} }}
\t\t\tno_phenomenon = {none:.3f}
\t\t\train_light = {rain:.3f}
\t\t\train_heavy = {heavy:.3f}
\t\t\tsnow = {snow:.3f}
\t\t\tblizzard = {blizz:.3f}
\t\t\tarctic_water = {arctic:.3f}
\t\t\tmud = {mud:.3f}
\t\t\tsandstorm = 0.000
\t\t\tmin_snow_level = 0.000
\t\t}}""")
    return "\n".join(lines)


# ---------------------------------------------------------------- straits
STRAITS = [
    ("Bosporus", (29.2, 41.3), (29.05, 40.9), None),
    ("Dardanelles", (27.4, 40.5), (26.0, 39.9), None),
    ("Gibraltar", (-6.0, 36.0), (-4.6, 36.1), None),
    ("Oresund", (12.8, 55.4), (12.6, 56.3), None),
    ("Kerch", (36.5, 44.9), (36.9, 45.6), None),
    ("Messina", (15.45, 38.45), (15.75, 37.9), None),
    ("Bab-el-Mandeb", (43.2, 13.6), (43.8, 12.3), None),
    ("Hormuz", (56.3, 26.4), (57.1, 25.5), None),
    ("Suez Canal", (32.4, 31.5), (32.6, 29.8), (32.4, 30.6)),
    ("Panama Canal", (-79.8, 9.5), (-79.6, 8.8), (-79.7, 9.15)),
    ("Kiel Canal", (9.0, 54.0), (10.2, 54.5), (9.6, 54.2)),
    ("Corinth Canal", (22.9, 38.1), (23.2, 37.8), (23.0, 37.95)),
]


def find_prov(w, lon, lat, want, r=14):
    x, y = geo.lonlat_to_px(lon, lat)
    x, y = int(x), int(y)
    P, kind = w["P"], w["kind"]
    best, bd = None, 1e9
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            xx, yy = x + dx, y + dy
            if 0 <= xx < geo.W and 0 <= yy < geo.H and kind[P[yy, xx]] == want:
                d = dx * dx + dy * dy
                if d < bd:
                    best, bd = int(P[yy, xx]), d
    return best


def straits(w):
    adj = set(zip(w["adj_a"].tolist(), w["adj_b"].tolist()))
    rows = []
    for name, a, b, thr in STRAITS:
        pa = find_prov(w, *a, "sea")
        pb = find_prov(w, *b, "sea")
        through = find_prov(w, *thr, "land", 10) if thr else None
        if pa is None or pb is None or pa == pb:
            print("strait skipped (same/missing province):", name)
            continue
        if (min(pa, pb), max(pa, pb)) in adj and not thr:
            print("strait already connected:", name)
            continue
        rows.append((pa, pb, through if through else -1, name))
    return rows


# ---------------------------------------------------------------- railways
def railways(S, w, state_of):
    """Level-1..3 railway paths between the capital provinces of neighbouring states of one country."""
    kind = w["kind"]
    N = w["N"]
    a, b = w["adj_a"], w["adj_b"]
    keep = np.array([kind[x] == "land" and kind[y] == "land" for x, y in zip(a, b)])
    a, b = a[keep], b[keep]
    d = np.hypot(w["cx"][a] - w["cx"][b], (w["cy"][a] - w["cy"][b])) + 1.0
    g = coo_matrix((np.concatenate([d, d]), (np.concatenate([a, b]), np.concatenate([b, a]))), shape=(N + 1, N + 1)).tocsr()
    cap = {s["id"]: s["capital_prov"] for s in S}
    tag = {s["id"]: s["tag"] for s in S}
    pairs = set()
    for x, y in zip(a, b):
        sx, sy = int(state_of[x]), int(state_of[y])
        if sx != sy and tag[sx] == tag[sy]:
            pairs.add((min(sx, sy), max(sx, sy)))
    # keep only the nearest few neighbours per state
    nearest = {}
    for sx, sy in pairs:
        dd = math.hypot(S[sx - 1]["cx"] - S[sy - 1]["cx"], S[sx - 1]["cy"] - S[sy - 1]["cy"])
        nearest.setdefault(sx, []).append((dd, sy))
        nearest.setdefault(sy, []).append((dd, sx))
    chosen = set()
    for s, lst in nearest.items():
        for dd, t in sorted(lst)[:2]:
            chosen.add((min(s, t), max(s, t)))
    srcs = sorted({cap[s] for pr in chosen for s in pr})
    dist, pred = dijkstra(g, indices=srcs, return_predecessors=True)
    row = {p: i for i, p in enumerate(srcs)}
    out = []
    for sx, sy in sorted(chosen):
        s, t = cap[sx], cap[sy]
        path = [t]
        while path[-1] != s:
            p = pred[row[s], path[-1]]
            if p < 0:
                path = None
                break
            path.append(int(p))
        if not path or len(path) < 2 or len(path) > 40:
            continue
        lvl = 3 if max(S[sx - 1]["pop"], S[sy - 1]["pop"]) > 3_000_000 else 2 if max(S[sx - 1]["pop"], S[sy - 1]["pop"]) > 800_000 else 1
        out.append((lvl, path[::-1]))
    return out
