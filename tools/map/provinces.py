"""Stage 2: province partition (Voronoi / weighted Lloyd inside "units").

A unit is a connected set of pixels that a province may never leave:
  * land: one connected piece of one admin-1 region (so provinces never cross state / country borders)
  * sea:  one connected water body
  * lake: one connected lake
Seeds are placed with a density that follows population (land) or distance to coast (sea), relaxed
with weighted Lloyd iterations, then every province is made contiguous and tiny ones are merged.
"""
import multiprocessing as mp

import cv2
import numpy as np
from scipy import ndimage as ndi
from scipy.spatial import cKDTree
from skimage import measure

from . import data, geo
from .raster import NONE

TARGET_LAND = 14800
TARGET_SEA = 2900
LAND_MIN_AREA, SEA_MIN_AREA, LAKE_MIN_AREA = 45, 120, 300
G = {}  # shared (fork) globals for workers


def population_weight(L):
    """float32 HxW: 0..1 smoothed city-weight raster."""
    P = np.zeros((geo.H, geo.W), np.float32)
    for f in data.load_ne("ne_10m_populated_places"):
        p = f["properties"]
        pop = p.get("POP1990") or p.get("POP_MAX") or 0
        pop = max(pop, p.get("POP_MIN") or 0, 20000)
        x, y = geo.lonlat_to_px(p["LONGITUDE"], p["LATITUDE"])
        xi, yi = int(x), int(y)
        if 0 <= xi < geo.W and 0 <= yi < geo.H:
            P[yi, xi] += np.sqrt(pop)
    P = cv2.GaussianBlur(P, (0, 0), 20)
    P /= max(np.percentile(P[L], 99.0), 1e-6)
    return np.clip(P, 0, 1)


def land_density(L):
    Pn = population_weight(L)
    lat = geo.row_lat()
    cosl = np.cos(np.radians(lat)).astype(np.float32)[:, None]
    lon = (np.arange(geo.W) + 0.5) / geo.W * 360 - 180
    eu = ((lon > -12) & (lon < 60))[None, :] & ((lat > 34) & (lat < 66))[:, None]
    eu = cv2.GaussianBlur(eu.astype(np.float32), (0, 0), 12)
    D = cosl * (0.28 + 2.4 * Pn ** 0.8) * (1.0 + 0.45 * eu)
    return D.astype(np.float32)


def sea_density(C):
    d = ndi.distance_transform_edt(C != 0).astype(np.float32)
    s = 1.0 + 13.0 * np.clip((d - 6.0) / 114.0, 0, 1)
    cosl = np.cos(np.radians(geo.row_lat())).astype(np.float32)[:, None]
    return (np.maximum(cosl, 0.35) / s).astype(np.float32), d


def _counts(sumD, area, S0, minarea):
    n = np.rint(sumD / S0)
    return np.maximum(1, np.minimum(n, area // minarea)).astype(np.int64)


def _calibrate(sumD, area, target, minarea):
    lo, hi = 1e-3, 1e7
    for _ in range(60):
        mid = (lo * hi) ** 0.5
        if _counts(sumD, area, mid, minarea).sum() > target:
            lo = mid
        else:
            hi = mid
    return hi


def _fix(out, minkeep, minsize):
    """Make every label contiguous: keep big extra pieces as new labels, merge small ones."""
    mask = out >= 0
    comp = measure.label(out, background=-1, connectivity=1)
    nc = int(comp.max())
    sizes = np.bincount(comp.ravel(), minlength=nc + 1).astype(np.int64)
    sizes[0] = 0
    lab_of = np.full(nc + 1, -1, np.int64)
    lab_of[comp[mask]] = out[mask]
    objs = ndi.find_objects(comp)
    bb = [None] + [[o[0].start, o[0].stop, o[1].start, o[1].stop] for o in objs]
    # largest comp of each label
    big = {}
    for c in range(1, nc + 1):
        l = lab_of[c]
        if l not in big or sizes[c] > sizes[big[l]]:
            big[l] = c
    small = []
    for c in range(1, nc + 1):
        l = lab_of[c]
        if big[l] == c:
            if sizes[c] < minsize:
                small.append(c)
        elif sizes[c] < minkeep:
            small.append(c)
    small.sort(key=lambda c: sizes[c])
    cross = ndi.generate_binary_structure(2, 1)
    for c in small:
        y0, y1, x0, x1 = bb[c]
        y0, x0 = max(0, y0 - 1), max(0, x0 - 1)
        y1, x1 = min(comp.shape[0], y1 + 1), min(comp.shape[1], x1 + 1)
        sub = comp[y0:y1, x0:x1]
        m = sub == c
        if not m.any():
            continue
        ring = ndi.binary_dilation(m, cross) & ~m
        nb = sub[ring]
        nb = nb[nb > 0]
        if nb.size == 0:
            continue
        t = np.bincount(nb).argmax()
        sub[m] = t
        sizes[t] += sizes[c]
        sizes[c] = 0
        lab_of[c] = lab_of[t]
        b, a = bb[t], bb[c]
        bb[t] = [min(b[0], a[0]), max(b[1], a[1]), min(b[2], a[2]), max(b[3], a[3])]
    res = np.full(out.shape, -1, np.int64)
    res[mask] = lab_of[comp[mask]]
    # components that remained separate under the same label become separate provinces
    cc = measure.label(res, background=-1, connectivity=1)
    cc = np.where(mask, cc - 1, -1)
    return cc.astype(np.int32)


def _work(args):
    kind, uid, n, seed = args
    sl = G["slices"][uid]
    lab = G["labels"][sl]
    m = lab == uid
    out = np.full(m.shape, -1, np.int32)
    if n <= 1:
        out[m] = 0
        return uid, sl, out, 1
    ys, xs = np.nonzero(m)
    w = G["dens"][sl][ys, xs].astype(np.float64)
    rng = np.random.default_rng(seed)
    cap = 700000 if kind == "sea" else 150000
    sidx = np.arange(len(ys)) if len(ys) <= cap else rng.choice(len(ys), cap, replace=False)
    px = np.stack([xs[sidx], ys[sidx]], 1).astype(np.float64)
    pw = w[sidx] + 1e-9
    n = min(n, len(px))
    seeds = px[rng.choice(len(px), n, replace=False, p=pw / pw.sum())]
    rho = pw ** 2
    for _ in range(7):
        _, l = cKDTree(seeds).query(px)
        sw = np.bincount(l, rho, n)
        sx = np.bincount(l, rho * px[:, 0], n)
        sy = np.bincount(l, rho * px[:, 1], n)
        ok = sw > 0
        seeds[ok, 0] = sx[ok] / sw[ok]
        seeds[ok, 1] = sy[ok] / sw[ok]
    _, l = cKDTree(seeds).query(np.stack([xs, ys], 1).astype(np.float64))
    out[ys, xs] = l
    mk = {"land": (60, 40), "sea": (180, 120), "lake": (200, 150)}[kind]
    out = _fix(out, *mk)
    return uid, sl, out, int(out.max()) + 1


def build(rast):
    R, C, LK = rast["R"], rast["C"], rast["LK"]
    L = C == 0
    Dland = land_density(L)
    Dsea, dist = sea_density(C)
    cpu = mp.cpu_count()
    units = []   # (kind, uid, label array key)

    def prep(kind, labels, dens, minarea, target):
        sl = ndi.find_objects(labels)
        ids = [i + 1 for i, s in enumerate(sl) if s is not None]
        area = np.bincount(labels.ravel())[ids].astype(np.int64)
        sumD = ndi.sum(dens, labels, ids)
        if target:
            S0 = _calibrate(np.asarray(sumD), area, target, minarea)
            n = _counts(np.asarray(sumD), area, S0, minarea)
        else:
            n = np.maximum(1, area // 900)
        return sl, ids, n, area

    # land units
    labL = measure.label(np.where(L, R, NONE), background=NONE, connectivity=1).astype(np.int32)
    slL, idL, nL, aL = prep("land", labL, Dland, LAND_MIN_AREA, TARGET_LAND)
    labS = measure.label(C == 1, connectivity=1).astype(np.int32)
    slS, idS, nS, aS = prep("sea", labS, Dsea, SEA_MIN_AREA, TARGET_SEA)
    slK, idK, nK, aK = prep("lake", LK, np.ones_like(Dland), LAKE_MIN_AREA, None)
    print(f"units: land {len(idL)} (target seeds {nL.sum()}), sea {len(idS)} ({nS.sum()}), lakes {len(idK)} ({nK.sum()})", flush=True)

    P = np.full(R.shape, -1, np.int32)
    meta = []   # per province: kind
    offset = 0
    for kind, labels, dens, sl, ids, ns, ar in [("land", labL, Dland, slL, idL, nL, aL),
                                                ("sea", labS, Dsea, slS, idS, nS, aS),
                                                ("lake", LK, np.ones_like(Dland), slK, idK, nK, aK)]:
        G.clear()
        G.update(labels=labels, dens=dens, slices={i: sl[i - 1] for i in ids})
        order = np.argsort(-ar)
        tasks = [(kind, ids[j], int(ns[j]), 1000 + ids[j]) for j in order]
        with mp.get_context("fork").Pool(cpu) as pool:
            for k, (uid, s, out, cnt) in enumerate(pool.imap_unordered(_work, tasks, chunksize=1)):
                m = out >= 0
                view = P[s]
                view[m] = out[m] + offset
                offset += cnt
                meta.extend([kind] * cnt)
        print(f"{kind}: {sum(1 for x in meta if x == kind)} provinces", flush=True)
    G.clear()
    assert (P >= 0).all(), "unassigned pixels"
    U = np.where(C == 0, labL, np.where(C == 1, labS + labL.max() + 1, LK + labL.max() + labS.max() + 2)).astype(np.int32)
    return P, np.array(meta), U


def fix_crossings(P, U, force=False):
    """Remove 2x2 blocks that touch 4 provinces or form a checkerboard (engine 'X crossings').
    A pixel may only be re-assigned to a province of the same unit, so borders never move."""
    left = 0
    for _ in range(10):
        a, b, c, d = P[:-1, :-1], P[:-1, 1:], P[1:, :-1], P[1:, 1:]
        four = (a != b) & (a != c) & (a != d) & (b != c) & (b != d) & (c != d)
        chk = (a == d) & (b == c) & (a != b)
        bad = four | chk
        left = int(bad.sum())
        if left == 0:
            return 0
        ys, xs = np.nonzero(bad)
        # corners of each bad block: (dy, dx) of the pixel and of the neighbour it copies
        moves = [((1, 1), (1, 0)), ((1, 1), (0, 1)), ((0, 0), (0, 1)), ((0, 0), (1, 0)),
                 ((0, 1), (0, 0)), ((0, 1), (1, 1)), ((1, 0), (0, 0)), ((1, 0), (1, 1))]
        done = np.zeros(len(ys), bool)
        for (py, px), (qy, qx) in moves:
            # still bad and not yet fixed
            pv = P[ys + py, xs + px]
            qv = P[ys + qy, xs + qx]
            ok = ~done & (pv != qv) & (U[ys + py, xs + px] == U[ys + qy, xs + qx])
            P[(ys + py)[ok], (xs + px)[ok]] = qv[ok]
            done |= ok
    if force:   # last resort: copy any neighbour inside the block (moves a coast / border by one pixel)
        a, b, c, d = P[:-1, :-1], P[:-1, 1:], P[1:, :-1], P[1:, 1:]
        bad = (((a != b) & (a != c) & (a != d) & (b != c) & (b != d) & (c != d)) | ((a == d) & (b == c) & (a != b)))
        ys, xs = np.nonzero(bad)
        cnt = np.bincount(P.ravel())
        for y, x in zip(ys, xs):
            if cnt[P[y + 1, x + 1]] > 40:
                cnt[P[y + 1, x + 1]] -= 1
                P[y + 1, x + 1] = P[y + 1, x]
    a, b, c, d = P[:-1, :-1], P[:-1, 1:], P[1:, :-1], P[1:, 1:]
    return int((((a != b) & (a != c) & (a != d) & (b != c) & (b != d) & (c != d)) | ((a == d) & (b == c) & (a != b))).sum())


def cleanup(P, kinds, U, minland=40, minsea=120):
    """Merge provinces that are still tiny into the neighbour (same unit) they share most border with."""
    cross = ndi.generate_binary_structure(2, 1)
    cnt = np.bincount(P.ravel())
    lim = np.array([minland if k == "land" else minsea for k in kinds])
    todo = [i for i in np.nonzero((cnt < lim) & (cnt > 0))[0]]
    todo.sort(key=lambda i: cnt[i])
    objs = ndi.find_objects(P + 1)
    merged = 0
    for i in todo:
        o = objs[i]
        y0, y1 = max(0, o[0].start - 1), min(P.shape[0], o[0].stop + 1)
        x0, x1 = max(0, o[1].start - 1), min(P.shape[1], o[1].stop + 1)
        sub = P[y0:y1, x0:x1]
        m = sub == i
        if not m.any():
            continue
        uid = U[y0:y1, x0:x1][m][0]
        ring = ndi.binary_dilation(m, cross) & ~m & (U[y0:y1, x0:x1] == uid)
        nb = sub[ring]
        if nb.size == 0:
            continue
        t = np.bincount(nb).argmax()
        sub[m] = t
        merged += 1
        a, b = objs[i], objs[t]
        objs[t] = (slice(min(a[0].start, b[0].start), max(a[0].stop, b[0].stop)),
                   slice(min(a[1].start, b[1].start), max(a[1].stop, b[1].stop)))
    return merged


def repair_contiguity(P):
    """Safety net after pixel moves: pieces cut off from their province join the neighbour they touch most."""
    lab = measure.label(P, connectivity=1)
    n = int(lab.max())
    prov = np.zeros(n + 1, np.int64)
    prov[lab.ravel()] = P.ravel()
    sizes = np.bincount(lab.ravel(), minlength=n + 1)
    main = {}
    for c in range(1, n + 1):
        p = prov[c]
        if p not in main or sizes[c] > sizes[main[p]]:
            main[p] = c
    objs = ndi.find_objects(lab)
    cross = ndi.generate_binary_structure(2, 1)
    fixed = 0
    for c in range(1, n + 1):
        if main[prov[c]] == c:
            continue
        o = objs[c - 1]
        y0, y1 = max(0, o[0].start - 1), min(P.shape[0], o[0].stop + 1)
        x0, x1 = max(0, o[1].start - 1), min(P.shape[1], o[1].stop + 1)
        m = lab[y0:y1, x0:x1] == c
        ring = ndi.binary_dilation(m, cross) & ~m
        nb = P[y0:y1, x0:x1][ring]
        nb = nb[nb != prov[c]]
        if nb.size:
            P[y0:y1, x0:x1][m] = np.bincount(nb).argmax()
            fixed += 1
    return fixed
