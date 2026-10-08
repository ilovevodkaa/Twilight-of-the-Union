"""Provinces inside one 1990 unit: multi-source Dijkstra over the unit's pixels. A step costs its length times
(1 + smooth noise + slope), so borders wander like real ones instead of the straight lines of a Voronoi diagram.
City seeds stay put; the other seeds start by farthest-point sampling and are relaxed towards their cells' centres."""
import numpy as np
from scipy import ndimage
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

from .common import MIN_PROVINCE_PX

NOISE_SIGMA, NOISE_AMP, SLOPE_K, LLOYD = 3.0, 1.2, 0.08, 3
FOUR = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], bool)
EIGHT = np.ones((3, 3), bool)


def _graph(mask, height, rng):
    idx = np.full(mask.shape, -1, np.int64)
    rows, cols = np.nonzero(mask)
    idx[rows, cols] = np.arange(len(rows))
    noise = ndimage.gaussian_filter(rng.random(mask.shape), NOISE_SIGMA)
    noise = (noise - noise.min()) / (np.ptp(noise) + 1e-9) * NOISE_AMP
    h = height.astype(float)
    ii, jj, ww = [], [], []
    for dr, dc, step in ((0, 1, 1.0), (1, 0, 1.0), (1, 1, 1.4142), (1, -1, 1.4142)):
        r2, c2 = rows + dr, cols + dc
        ok = (r2 < mask.shape[0]) & (c2 >= 0) & (c2 < mask.shape[1])
        r1, c1, r2, c2 = rows[ok], cols[ok], r2[ok], c2[ok]
        ok = mask[r2, c2]
        r1, c1, r2, c2 = r1[ok], c1[ok], r2[ok], c2[ok]
        ii.append(idx[r1, c1])
        jj.append(idx[r2, c2])
        ww.append(step * (1 + 0.5 * (noise[r1, c1] + noise[r2, c2]) + SLOPE_K * np.abs(h[r1, c1] - h[r2, c2])))
    n = len(rows)
    g = csr_matrix((np.concatenate(ww), (np.concatenate(ii), np.concatenate(jj))), shape=(n, n))
    return g, idx, rows, cols


def _assign(g, seeds):
    """Index of the nearest seed for every node (-1 if unreachable) and the distance to it."""
    dist, _, src = dijkstra(g, directed=False, indices=seeds, min_only=True, return_predecessors=True)
    order = np.full(g.shape[0], -1, np.int64)
    order[np.asarray(seeds)] = np.arange(len(seeds))
    lab = np.where(src >= 0, order[np.maximum(src, 0)], -1)
    return lab, dist


def partition(mask, height, fixed, n_target, seed):
    """mask: bool (h, w); height: uint8 (h, w); fixed: (row, col) seeds that must stay (cities), in order.
    Returns labels (0 outside the mask, provinces 1..k; the fixed seeds' provinces first, in their order) and the
    seed (row, col) of every province (None for a fixed seed whose province was merged away)."""
    rng = np.random.default_rng(seed)
    out = np.zeros(mask.shape, np.int32)
    if not mask.any():
        return out, []
    g, idx, rows, cols = _graph(mask, height, rng)
    seeds = []
    for r, c in fixed:
        if mask[r, c] and idx[r, c] not in seeds:
            seeds.append(int(idx[r, c]))
    n_fixed = len(seeds)
    comp, ncomp = ndimage.label(mask, structure=EIGHT)
    sizes = ndimage.sum(mask, comp, range(1, ncomp + 1))
    for k in range(1, ncomp + 1):                       # every island of a province's size gets a seed
        if sizes[k - 1] >= MIN_PROVINCE_PX and not any(comp[rows[s], cols[s]] == k for s in seeds):
            d = ndimage.distance_transform_edt(np.pad(comp == k, 1))[1:-1, 1:-1]
            r, c = np.unravel_index(np.argmax(d), d.shape)
            seeds.append(int(idx[r, c]))
    if not seeds:
        rr, cc = np.nonzero(mask)
        seeds.append(int(idx[rr[len(rr) // 2], cc[len(cc) // 2]]))
    n_target = max(n_target, len(seeds), 1)
    n_target = min(n_target, max(len(seeds), int(mask.sum()) // MIN_PROVINCE_PX))
    while len(seeds) < n_target:                        # farthest-point sampling
        _, dist = _assign(g, seeds)
        dist[~np.isfinite(dist)] = -1
        seeds.append(int(np.argmax(dist)))
    for _ in range(LLOYD):                              # relax the free seeds towards their cells' centres
        lab, _ = _assign(g, seeds)
        for k in range(n_fixed, len(seeds)):
            cell = np.nonzero(lab == k)[0]
            if len(cell):
                cr, cc = rows[cell].mean(), cols[cell].mean()
                seeds[k] = int(cell[np.argmin((rows[cell] - cr) ** 2 + (cols[cell] - cc) ** 2)])
    lab, _ = _assign(g, seeds)
    out[rows, cols] = lab + 1                           # unreachable pixels (tiny islands) are 0 for now
    seed_rc = [(int(rows[s]), int(cols[s])) for s in seeds]
    out = _cleanup(out, mask, seed_rc)
    return _renumber(out, seed_rc)


def _fill_from_nearest(out, mask):
    hole = mask & (out == 0)
    if hole.any():
        _, (ri, ci) = ndimage.distance_transform_edt(out == 0, return_indices=True)
        out[hole] = out[ri[hole], ci[hole]]


def _cleanup(out, mask, seed_rc):
    comp, ncomp = ndimage.label(mask, structure=EIGHT)
    sizes = ndimage.sum(mask, comp, range(1, ncomp + 1))
    tiny = np.isin(comp, np.nonzero(sizes < MIN_PROVINCE_PX)[0] + 1)
    for k in range(1, out.max() + 1):                   # keep the seed's part of every province
        parts, n = ndimage.label((out == k) & ~tiny, structure=FOUR)
        if n > 1:
            r, c = seed_rc[k - 1]
            keep = parts[r, c] if parts[r, c] else np.argmax(np.bincount(parts.ravel())[1:]) + 1
            out[(parts != keep) & (parts > 0)] = 0
    _fill_from_nearest(out, mask)
    while True:                                         # merge provinces under the minimum into a neighbour
        sizes = np.bincount(out.ravel(), minlength=out.max() + 1)
        small = [k for k in range(1, len(sizes)) if 0 < sizes[k] < MIN_PROVINCE_PX]
        if not small or (sizes[1:] > 0).sum() <= 1:
            break
        k = min(small, key=lambda j: sizes[j])
        ring = ndimage.binary_dilation(out == k, FOUR) & (out != k) & (out > 0)
        if not ring.any():
            break
        out[out == k] = np.bincount(out[ring]).argmax()
    return out


def _renumber(out, seed_rc):
    present = [k for k in range(1, out.max() + 1) if (out == k).any()]
    new = np.zeros(out.max() + 1, np.int32)
    seeds = []
    for j, k in enumerate(present, 1):
        new[k] = j
        r, c = seed_rc[k - 1]
        seeds.append((r, c) if out[r, c] == k else None)
    return new[out], seeds
