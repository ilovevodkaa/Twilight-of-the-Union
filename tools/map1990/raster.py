"""Burns the zone's 1990 units and the neighbouring countries into a label raster of the vanilla map.

Per window the georeferenced polygons get an affine correction fitted by ICP of the real coastline onto the vanilla
one, so the new borders sit where the vanilla terrain, rivers and coasts are (misfit ~1 px)."""
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from scipy.spatial import cKDTree

from .common import GEO, MAP_H, MAP_W
from .geodata import decimate, read_geojson, read_vghist

NONE, FOREIGN = -1, -2
TOL = 0.008          # degrees; a map pixel is ~0.064 degrees of longitude
ICP_ITERS, ICP_MAX_D = 15, 6.0
FOUR = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], bool)


@dataclass
class Labels:
    unit: np.ndarray                              # int16 (MAP_H, MAP_W): unit index, FOREIGN, NONE
    boxes: list                                   # pixel windows (x0, y0, x1, y1)
    affine: list = field(default_factory=list)    # 3x3 per window, window-local pixel coordinates
    misfit: list = field(default_factory=list)    # median coast distance (px) per window after the correction
    unit_polys: dict = field(default_factory=dict)   # unit index -> lon/lat polygons (cities are placed by them)


def window_box(georef, w, margin=8):
    lon0, lat0, lon1, lat1 = w
    x, row = georef.to_px([lon0, lon1, lon0, lon1], [lat0, lat0, lat1, lat1])
    return (max(0, int(x.min()) - margin), max(0, int(row.min()) - margin),
            min(MAP_W, int(x.max()) + margin + 1), min(MAP_H, int(row.max()) + margin + 1))


def _bbox(polys):
    pts = np.concatenate([p[0] for p in polys])
    return pts[:, 0].min(), pts[:, 1].min(), pts[:, 0].max(), pts[:, 1].max()


def _overlaps(b, w):
    return not (b[2] < w[0] or b[0] > w[2] or b[3] < w[1] or b[1] > w[3])


def project(features, georef, box):
    """Outer rings of every polygon in window-local pixel coordinates (holes are left out: the enclaves inside a
    unit are other features drawn after it)."""
    x0, y0 = box[0], box[1]
    out = []
    for label, polys in features:
        rings = []
        for poly in polys:
            ring = decimate(poly[0], TOL)
            if len(ring) >= 4:
                x, row = georef.to_px(ring[:, 0], ring[:, 1])
                rings.append(np.stack([x - x0, row - y0], 1))
        out.append((label, rings))
    return out


def burn(shape, projected, affine=np.eye(3)):
    img = Image.new("I", (shape[1], shape[0]), NONE)
    d = ImageDraw.Draw(img)
    for label, rings in projected:
        for r in rings:
            p = np.c_[r, np.ones(len(r))] @ affine.T
            d.polygon(list(zip(p[:, 0].tolist(), p[:, 1].tolist())), fill=int(label))
    return np.asarray(img, np.int32)


def coast_points(land):
    """(col, row) of land pixels that touch non-land (4-neighbourhood)."""
    edge = land & ~ndimage.binary_erosion(land, FOUR, border_value=1)
    r, c = np.nonzero(edge)
    return np.stack([c, r], 1).astype(float)


def icp_affine(src, dst):
    """Affine (3x3) moving the src points onto the nearest dst points; returns it and the median residual."""
    tree = cKDTree(dst)
    a = np.eye(3)
    ones = np.ones((len(src), 1))
    d = tree.query(src)[0]
    for _ in range(ICP_ITERS):
        p = (np.c_[src, ones] @ a.T)[:, :2]
        d, j = tree.query(p)
        ok = d < ICP_MAX_D
        m, *_ = np.linalg.lstsq(np.c_[src[ok], ones[ok]], dst[j[ok]], rcond=None)
        a = np.vstack([m.T, [0, 0, 1]])
    d = tree.query((np.c_[src, ones] @ a.T)[:, :2])[0]
    return a, float(np.median(d))


def zone_features(zone):
    feats = {}
    if any(u.source == "vghist" for u in zone.units):
        code_unit = {c: i for i, u in enumerate(zone.units) if u.source == "vghist" for c in u.codes}
        for props, polys in read_vghist(GEO / "vg-hist.gpkg"):
            feats.setdefault(code_unit[props["land"]], []).extend(polys)
    if any(u.source == "ne1" for u in zone.units):
        code_unit = {c: i for i, u in enumerate(zone.units) if u.source == "ne1" for c in u.codes}
        for props, polys in read_geojson(GEO / "ne_10m_admin_1_states_provinces.geojson"):
            if props["iso_3166_2"] in code_unit:
                feats.setdefault(code_unit[props["iso_3166_2"]], []).extend(polys)
    return feats


def label_zone(vm, georef, zone):
    unit = np.full((MAP_H, MAP_W), NONE, np.int16)
    land = np.isin(vm.ids, np.array([p for p, v in vm.provs.items() if v.kind == "land"]))
    sea = np.isin(vm.ids, np.array([p for p, v in vm.provs.items() if v.kind == "sea"]))
    zfeat = zone_features(zone)
    foreign = [(FOREIGN, polys) for props, polys in read_geojson(GEO / "ne_10m_admin_0_countries.geojson")
               if props["adm0_a3"] not in zone.zone_codes]
    out = Labels(unit, [], unit_polys=zfeat)
    for w in zone.windows:
        box = window_box(georef, w)
        x0, y0, x1, y1 = box
        shape = (y1 - y0, x1 - x0)
        fs = project([(lab, polys) for lab, polys in foreign if _overlaps(_bbox(polys), w)], georef, box)
        zs = [(i, polys) for i, polys in zfeat.items() if _overlaps(_bbox(polys), w)]
        zs.sort(key=lambda f: -np.prod(np.ptp(np.concatenate([p[0] for p in f[1]]), axis=0)))
        zs = project(zs, georef, box)
        real = burn(shape, fs + zs) != NONE
        a, misfit = icp_affine(coast_points(real), coast_points(~sea[y0:y1, x0:x1]))
        lab = burn(shape, fs, a)
        zl = burn(shape, zs, a)
        lab = np.where(zl != NONE, zl, lab)                 # the zone's own (more precise) borders win
        wl = land[y0:y1, x0:x1]
        missing = wl & (lab == NONE)
        if missing.any():                                   # coast mismatch: nearest labelled pixel
            _, (ri, ci) = ndimage.distance_transform_edt(lab == NONE, return_indices=True)
            lab[missing] = lab[ri[missing], ci[missing]]
        lab[~wl] = NONE
        unit[y0:y1, x0:x1] = lab.astype(np.int16)
        out.boxes.append(box)
        out.affine.append(a)
        out.misfit.append(misfit)
    return out
