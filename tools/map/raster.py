"""Stage 1: rasterise Natural Earth into the map grid.

Outputs (dict of arrays, cached by build_map.py):
  R  uint16  admin-1 region index per land pixel (65535 = not land)
  C  uint8   0 land, 1 sea, 2 lake
  LK int32   lake / water-body id for lake pixels (0 elsewhere)
  regions    list of dicts (name, name_en, name_ru, adm0, tag, continent, ...)
"""
import numpy as np
import cv2
from scipy import ndimage as ndi
from skimage import measure

from . import data, geo, countries

NONE = 65535
MIN_ISLAND = 40       # land components smaller than this (px) are dropped
MIN_LAKE = 150        # lakes smaller than this (px) are filled with land
NO_DISC = {"VAT", "GIB", "BRI", "PGA", "BJN", "SER", "SCR", "IOT", "USG", "SPI", "KAS", "BRT", "CNM"}
PROTECT_MIN = 20      # regions holding a capital / big city survive down to this many px
TINY_DISC = 3.6       # radius (px) of the disc painted for countries that vanish at this scale


def _load_regions():
    adm0 = data.load_ne("ne_10m_admin_0_countries")
    group, cont, info = {}, {}, {}
    for f in adm0:
        p = f["properties"]
        group[p["ADM0_A3"]] = p["SOV_A3"]
        cont[p["ADM0_A3"]] = p["CONTINENT"]
        info[p["ADM0_A3"]] = p
    regions, geoms = [], []
    have = set()
    for f in data.load_ne("ne_10m_admin_1_states_provinces"):
        p = f["properties"]
        if f["geometry"] is None or p["adm0_a3"] == "ATA":
            continue
        tag = countries.owner_tag(p, group)
        if tag is None:
            continue
        have.add(p["adm0_a3"])
        regions.append(dict(name=p["name"], name_en=p.get("name_en") or p["name"], name_ru=p.get("name_ru"),
                            adm0=p["adm0_a3"], tag=tag, continent=cont.get(p["adm0_a3"], "Asia"),
                            lon=p.get("longitude"), lat=p.get("latitude")))
        geoms.append(f["geometry"])
    for f in adm0:  # countries without admin-1 data
        p = f["properties"]
        if p["ADM0_A3"] in have or p["ADM0_A3"] == "ATA":
            continue
        tag = countries.owner_tag(dict(adm0_a3=p["ADM0_A3"], name=p["NAME"]), group)
        if tag is None:
            continue
        regions.append(dict(name=p["NAME"], name_en=p["NAME_EN"] or p["NAME"], name_ru=p.get("NAME_RU"),
                            adm0=p["ADM0_A3"], tag=tag, continent=p["CONTINENT"], lon=None, lat=None))
        geoms.append(f["geometry"])
    return adm0, regions, geoms, info


def merge_fragments(R, L, minsize=40, protect=()):
    """Absorb tiny pieces of a region that are cut off from the rest (polygon overlaps/gaps) into
    the neighbouring region. Whole islets (no land neighbour) are kept."""
    cross = ndi.generate_binary_structure(2, 1)
    for _ in range(2):
        lab = measure.label(np.where(L, R, NONE), background=NONE, connectivity=1)
        sizes = np.bincount(lab.ravel())
        objs = ndi.find_objects(lab)
        small = [c for c in range(1, len(sizes)) if sizes[c] < minsize]
        if protect:
            rv = np.zeros(len(sizes), np.int64)
            rv[lab[L]] = R[L]
            small = [c for c in small if not (rv[c] in protect and sizes[c] >= PROTECT_MIN)]
        small.sort(key=lambda c: sizes[c])
        for c in small:
            o = objs[c - 1]
            y0, y1 = max(0, o[0].start - 1), min(R.shape[0], o[0].stop + 1)
            x0, x1 = max(0, o[1].start - 1), min(R.shape[1], o[1].stop + 1)
            sl = lab[y0:y1, x0:x1]
            m = sl == c
            if not m.any():
                continue
            ring = ndi.binary_dilation(m, cross) & ~m & L[y0:y1, x0:x1]
            nb = sl[ring]
            nb = nb[nb > 0]
            if nb.size == 0:
                continue
            t = np.bincount(nb).argmax()
            rv = R[y0:y1, x0:x1][sl == t][0]
            R[y0:y1, x0:x1][m] = rv
            sl[m] = t
    return R


def merge_micro_regions(R, L, regions, minpx=170, protect=()):
    """Admin-1 regions that cover fewer than `minpx` pixels (Slovenian municipalities, Latvian
    districts...) are absorbed into the neighbouring region of the same country they border most."""
    n = len(regions)
    idx = np.where(L & (R != NONE), R.astype(np.int32) + 1, 0)
    objs = ndi.find_objects(idx)
    box = {i: o for i, o in enumerate(objs) if o is not None}
    cnt = np.bincount(idx.ravel(), minlength=n + 1)[1:].astype(np.int64)
    nb = {}
    for a, b in ((R[:, :-1], R[:, 1:]), (R[:-1, :], R[1:, :])):
        m = (a != b) & (a != NONE) & (b != NONE)
        codes, c = np.unique(a[m].astype(np.int64) * 70000 + b[m].astype(np.int64), return_counts=True)
        for code, k in zip(codes, c):
            x, y = int(code // 70000), int(code % 70000)
            nb.setdefault(x, {})
            nb.setdefault(y, {})
            nb[x][y] = nb[x].get(y, 0) + int(k)
            nb[y][x] = nb[y].get(x, 0) + int(k)
    merged = 0
    for r in sorted((i for i in range(n) if 0 < cnt[i] < minpx), key=lambda i: cnt[i]):
        if r in protect and cnt[r] >= PROTECT_MIN:
            continue
        cand = {t: c for t, c in nb.get(r, {}).items() if regions[t]["tag"] == regions[r]["tag"]}
        if not cand or r not in box:
            continue
        t = max(cand, key=cand.get)
        o = box[r]
        sub = R[o]
        sub[(sub == r) & L[o]] = t
        a, b = box[r], box.get(t, box[r])
        box[t] = (slice(min(a[0].start, b[0].start), max(a[0].stop, b[0].stop)),
                  slice(min(a[1].start, b[1].start), max(a[1].stop, b[1].stop)))
        cnt[t] += cnt[r]
        cnt[r] = 0
        for x, c in nb.pop(r, {}).items():
            nb[x].pop(r, None)
            if x != t:
                nb[x][t] = nb[x].get(t, 0) + c
                nb[t][x] = nb[t].get(x, 0) + c
        merged += 1
    print(f"merged {merged} micro regions", flush=True)
    return R


def _protected_regions(R, L, regions):
    """Regions that contain a national capital or a city of 600k+ must stay separate (state names, VPs)."""
    prot = set()
    for f in data.load_ne("ne_10m_populated_places"):
        p = f["properties"]
        pop = (p["POP1990"] or 0) * 1000 or int((p["POP_MAX"] or 0) * 0.75)
        if not (p["FEATURECLA"] in ("Admin-0 capital", "Admin-0 capital alt") or pop >= 600000):
            continue
        x, y = geo.lonlat_to_px(p["LONGITUDE"], p["LATITUDE"])
        xi, yi = int(x), int(y)
        if not (3 <= xi < geo.W - 3 and 3 <= yi < geo.H - 3):
            continue
        win = np.where(L[yi - 3:yi + 4, xi - 3:xi + 4], R[yi - 3:yi + 4, xi - 3:xi + 4], NONE).ravel()
        win = win[win != NONE]
        if win.size:
            prot.add(int(np.bincount(win).argmax()))
    print("protected regions:", len(prot), flush=True)
    return prot


def build():
    adm0, regions, geoms, info = _load_regions()
    W, H = geo.W, geo.H
    # --- land / lake masks
    land = np.zeros((H, W), np.uint8)
    for f in data.load_ne("ne_10m_land"):
        geo.fill_geom(land, f["geometry"], 1)
    lakes = np.zeros((H, W), np.uint8)
    caspian = np.zeros((H, W), np.uint8)
    for f in data.load_ne("ne_10m_lakes"):
        nm = (f["properties"].get("name") or "")
        geo.fill_geom(lakes, f["geometry"], 1)
        if nm in ("Caspian Sea",):
            geo.fill_geom(caspian, f["geometry"], 1)
    land |= caspian * 0  # (Caspian handled below)
    # big lakes only
    lab = measure.label(lakes, connectivity=1)
    sizes = np.bincount(lab.ravel())
    keep = sizes >= MIN_LAKE
    keep[0] = False
    biglake = keep[lab]
    cas_ids = np.unique(lab[(caspian > 0) & biglake])
    iscas = np.isin(lab, cas_ids[cas_ids > 0]) & biglake
    L = (land > 0) & ~biglake
    # --- region id raster (small regions drawn last so enclaves like Berlin survive)
    order = sorted(range(len(regions)), key=lambda i: -geo.geom_area_px(geoms[i]))
    R = np.full((H, W), NONE, np.uint16)
    for i in order:
        geo.fill_geom(R, geoms[i], i, holes=False)
        regions[i]["area_geom"] = 0
    # --- drop tiny islands
    lab = measure.label(L, connectivity=1)
    sizes = np.bincount(lab.ravel())
    ok = sizes >= MIN_ISLAND
    ok[0] = False
    dropped = L & ~ok[lab]
    L = ok[lab]
    # islets inside big lakes become lake water again (otherwise the tiny-water pass resurrects them)
    near = ndi.binary_dilation(biglake, iterations=4)
    biglake = biglake | (dropped & near)
    # --- tiny countries that would vanish: paint a disc
    nz = np.bincount(R[L & (R != NONE)].ravel().astype(np.int64), minlength=len(regions))
    adm0_px = {}
    for i, r in enumerate(regions):
        adm0_px[r["adm0"]] = adm0_px.get(r["adm0"], 0) + int(nz[i])
    first_region = {}
    for i, r in enumerate(regions):
        first_region.setdefault(r["adm0"], i)
    disc = np.zeros((H, W), np.uint8)
    painted = []
    for f in adm0:
        p = f["properties"]
        a3 = p["ADM0_A3"]
        if a3 not in first_region or p["TYPE"] in ("Dependency", "Lease", "Indeterminate") or a3 in NO_DISC or adm0_px.get(a3, 0) >= MIN_ISLAND:
            continue
        from shapely.geometry import shape
        g = shape(f["geometry"])
        if g.geom_type == "MultiPolygon":
            g = max(g.geoms, key=lambda q: q.area)
        pt = g.representative_point()
        x, y = geo.lonlat_to_px(pt.x, pt.y)
        if not (0 <= y < H):
            continue
        cv2.circle(disc, (int(x), int(y)), 0, 1, -1)
        cv2.circle(R, (int(x), int(y)), int(round(TINY_DISC)), int(first_region[a3]), -1)
        cv2.circle(disc, (int(x), int(y)), int(round(TINY_DISC)), 1, -1)
        painted.append(a3)
    L |= disc > 0
    # --- nearest-region fill for land pixels lacking a region
    R[~L] = NONE
    miss = L & (R == NONE)
    if miss.any():
        idx = ndi.distance_transform_edt(R == NONE, return_distances=False, return_indices=True)
        R = R[idx[0], idx[1]]
        R[~L] = NONE
    protect = _protected_regions(R, L, regions)
    R = merge_fragments(R, L, 60, protect)
    R = merge_micro_regions(R, L, regions, protect=protect)
    R = merge_fragments(R, L, 60, protect)
    # --- water: tiny seas become land
    water = ~L
    lab = measure.label(water & ~biglake, connectivity=1)
    sizes = np.bincount(lab.ravel())
    tiny = (sizes < 30)
    tiny[0] = False
    tinymask = tiny[lab] & ~biglake
    if tinymask.any():
        idx = ndi.distance_transform_edt(R == NONE, return_distances=False, return_indices=True)
        Rf = R[idx[0], idx[1]]
        R[tinymask] = Rf[tinymask]
        L |= tinymask
    C = np.ones((H, W), np.uint8)
    C[L] = 0
    lk = biglake & ~L
    C[lk & ~iscas] = 2
    LKid = measure.label((C == 2), connectivity=1).astype(np.int32)
    print(f"raster: land px {int(L.sum())}, lakes {int(LKid.max())}, painted tiny countries {painted}", flush=True)
    return dict(R=R, C=C, LK=LKid, regions=regions)
