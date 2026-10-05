"""Stage 3: finalise provinces (compact ids, colours, adjacency, representative points)."""
import numpy as np
from scipy import ndimage as ndi
from skimage import measure

from . import geo
from .raster import NONE

CONT = {"europe": 1, "north_america": 2, "south_america": 3, "australia": 4, "asia": 5, "africa": 6}
CONT_NAMES = ["europe", "north_america", "south_america", "australia", "asia", "africa"]


def color_of(i):
    """Bijective hash id -> 24-bit colour (never 0 for i >= 1, unique for i < 2^24)."""
    c = (i * 0x9E3779B1 + 0x5BD1E9) & 0xFFFFFF
    if c == 0:
        c = 0x010203
    return (c >> 16) & 255, (c >> 8) & 255, c & 255


def continent_of(region, lon, lat):
    nc = region["continent"]
    tag, adm0 = region["tag"], region["adm0"]
    if adm0 == "RUS":
        return "europe" if lon < 60 else "asia"
    if adm0 == "TUR" and lat > 40.3 and lon < 29.9:
        return "europe"
    if adm0 in ("IDN", "TLS") and lon > 141 and lat < 0:
        return "australia"
    if nc == "Oceania":
        return "australia"
    if nc == "Europe":
        return "europe"
    if nc == "Africa":
        return "africa"
    if nc == "South America":
        return "south_america"
    if nc == "North America":
        if lon < -140 and lat < 30:
            return "australia"
        return "north_america"
    if nc == "Asia":
        return "asia"
    # seven seas
    if lon > 60 or lon < -120:
        return "australia"
    return "africa" if lat < 20 else "europe"


def build(rast, P, meta):
    R, C, LK = rast["R"], rast["C"], rast["LK"]
    regions = rast["regions"]
    H, W = P.shape
    n0 = int(P.max()) + 1
    # first pixel of every raw province -> ordering (land, sea, lake each in raster order)
    flat = P.ravel()
    uniq, first = np.unique(flat, return_index=True)
    kind_rank = {"land": 0, "sea": 1, "lake": 2}
    raw_kind = np.array([kind_rank[k] for k in meta])
    present = np.zeros(n0, bool)
    present[uniq] = True
    first_full = np.full(n0, flat.size, np.int64)
    first_full[uniq] = first
    keys = raw_kind * (flat.size + 1) + first_full
    order = [i for i in np.argsort(keys, kind="stable") if present[i]]
    remap = np.zeros(n0, np.int32)
    for new, old in enumerate(order, start=1):
        remap[old] = new
    P = remap[P]
    N = len(order)
    kind = np.array([None] + [["land", "sea", "lake"][raw_kind[o]] for o in order])
    print(f"world: {N} provinces", flush=True)
    area = np.bincount(P.ravel(), minlength=N + 1)
    yy, xx = np.indices((H, W), dtype=np.float32)
    cx = np.bincount(P.ravel(), xx.ravel(), N + 1) / np.maximum(area, 1)
    cy = np.bincount(P.ravel(), yy.ravel(), N + 1) / np.maximum(area, 1)
    del yy, xx
    # representative point (deepest interior pixel) via per-province EDT
    objs = ndi.find_objects(P)
    rx = np.zeros(N + 1, np.int32)
    ry = np.zeros(N + 1, np.int32)
    for i in range(1, N + 1):
        o = objs[i - 1]
        sub = np.pad(P[o] == i, 1)
        d = ndi.distance_transform_edt(sub)
        j = np.unravel_index(np.argmax(d), d.shape)
        ry[i] = o[0].start + j[0] - 1
        rx[i] = o[1].start + j[1] - 1
    # adjacency (4-neighbourhood)
    pairs = []
    for a, b in ((P[:, :-1], P[:, 1:]), (P[:-1, :], P[1:, :])):
        m = a != b
        lo = np.minimum(a[m], b[m]).astype(np.int64)
        hi = np.maximum(a[m], b[m]).astype(np.int64)
        pairs.append(lo * (N + 1) + hi)
    codes, counts = np.unique(np.concatenate(pairs), return_counts=True)
    adj_a, adj_b = (codes // (N + 1)).astype(np.int32), (codes % (N + 1)).astype(np.int32)
    # land region / unit / continent
    region = np.full(N + 1, -1, np.int32)
    unit = np.full(N + 1, -1, np.int32)
    labL = measure.label(np.where(C == 0, R, NONE), background=NONE, connectivity=1)
    land_ids = np.nonzero(kind == "land")[0]
    region[land_ids] = R[ry[land_ids], rx[land_ids]]
    unit[land_ids] = labL[ry[land_ids], rx[land_ids]]
    cont = np.zeros(N + 1, np.int8)
    for i in land_ids:
        lon, lat = geo.px_to_lonlat(cx[i], cy[i])
        cont[i] = CONT[continent_of(regions[region[i]], float(lon), float(lat))]
    colors = np.array([(0, 0, 0)] + [color_of(i) for i in range(1, N + 1)], np.uint8)
    # coastal: land province touching sea
    is_sea = kind == "sea"
    coastal = np.zeros(N + 1, bool)
    sea_adj = [[] for _ in range(N + 1)]
    for a, b in zip(adj_a, adj_b):
        if kind[a] == "land" and is_sea[b]:
            coastal[a] = True
            sea_adj[a].append(int(b))
        elif kind[b] == "land" and is_sea[a]:
            coastal[b] = True
            sea_adj[b].append(int(a))
        elif kind[a] == "sea" and kind[b] == "sea":
            pass
    return dict(P=P, N=N, kind=kind, area=area, cx=cx, cy=cy, rx=rx, ry=ry, adj_a=adj_a, adj_b=adj_b,
                adj_n=counts.astype(np.int32), region=region, unit=unit, cont=cont, colors=colors,
                coastal=coastal, sea_adj=sea_adj)
