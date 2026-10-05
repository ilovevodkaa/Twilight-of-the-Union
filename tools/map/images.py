"""Raster assets: provinces / heightmap / terrain / rivers / trees / cities / world_normal / preview."""
import cv2
import numpy as np
from PIL import Image
from skimage.morphology import thin

from . import data, geo

SEA_LEVEL = 95
TREES_SIZE = (3520, 1280)    # (w, h); assumption, see README
NORMAL_SIZE = (geo.W // 2, geo.H // 2)

# terrain.bmp palette index per terrain name (assumed vanilla-like order, see README)
TERRAIN_INDEX = {"plains": 0, "forest": 1, "hills": 2, "mountain": 3, "desert": 4, "marsh": 5,
                 "jungle": 6, "urban": 7, "ocean": 15, "lakes": 16, "unknown": 255}
TERRAIN_RGB = {0: (86, 124, 27), 1: (0, 86, 6), 2: (112, 74, 31), 3: (65, 42, 17), 4: (206, 169, 99),
               5: (13, 96, 62), 6: (0, 255, 0), 7: (80, 80, 80), 15: (8, 31, 130), 16: (0, 130, 160), 255: (0, 0, 0)}


def save_bmp(arr, path, mode=None, palette=None):
    im = Image.fromarray(arr) if mode is None else Image.fromarray(arr, mode)
    if palette is not None:
        flat = [0] * 768
        for i, (r, g, b) in palette.items():
            flat[i * 3:i * 3 + 3] = [r, g, b]
        im.putpalette(flat)
    im.save(path, format="BMP")


def provinces_bmp(w, path):
    save_bmp(w["colors"][w["P"]], path)


def heightmap(w, rast, dem):
    C = rast["C"]
    e = dem.astype(np.float32)
    land = np.maximum(e, 0)
    hl = SEA_LEVEL + 1 + 159.0 * (1.0 - np.exp(-land / 1700.0))
    hl = cv2.GaussianBlur(hl, (0, 0), 1.1)
    depth = np.maximum(-e, 0)
    hs = SEA_LEVEL - 1 - np.clip(depth / 6000.0, 0, 1) * 30.0
    hs = cv2.GaussianBlur(hs, (0, 0), 3.0)
    h = np.where(C == 0, np.maximum(hl, SEA_LEVEL + 1), np.where(C == 2, SEA_LEVEL, np.minimum(hs, SEA_LEVEL)))
    h = np.clip(np.rint(h), 0, 255).astype(np.uint8)
    return h


def terrain_bmp(w, terr, rast):
    idx = np.array([TERRAIN_INDEX.get(t, 255) if t else 255 for t in terr], np.uint8)
    return idx[w["P"]]


def normal_map(hm):
    small = cv2.resize(hm, NORMAL_SIZE, interpolation=cv2.INTER_AREA).astype(np.float32)
    small = cv2.GaussianBlur(small, (0, 0), 0.8)
    gx = cv2.Sobel(small, cv2.CV_32F, 1, 0, ksize=3) / 8.0
    gy = cv2.Sobel(small, cv2.CV_32F, 0, 1, ksize=3) / 8.0
    k = 2.0
    n = np.dstack([-gx * k, gy * k, np.ones_like(gx)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    return np.clip((n * 0.5 + 0.5) * 255, 0, 255).astype(np.uint8)


RIVER_PALETTE = {0: (0, 255, 0), 1: (255, 0, 0), 2: (255, 252, 0), 3: (0, 225, 255), 4: (0, 200, 255),
                 5: (0, 150, 255), 6: (0, 100, 255), 7: (0, 0, 255), 8: (0, 0, 225), 9: (0, 0, 200),
                 10: (0, 0, 150), 11: (0, 0, 100), 254: (122, 122, 122), 255: (255, 255, 255)}


def rivers_bmp(rast):
    C = rast["C"]
    ri = np.zeros((geo.H, geo.W), np.uint8)
    src = np.zeros((geo.H, geo.W), bool)
    feats = [f for f in data.load_ne("ne_10m_rivers_lake_centerlines") if f["properties"].get("featurecla") == "River"]
    feats.sort(key=lambda f: -(f["properties"].get("scalerank") or 9))   # big rivers last
    for f in feats:
        sr = f["properties"].get("scalerank") or 9
        width = int(np.clip(11 - sr, 3, 10))
        g = f["geometry"]
        lines = g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]
        for ln in lines:
            a = np.asarray(ln)[:, :2]
            x, y = geo.lonlat_to_px(a[:, 0], a[:, 1])
            pts = np.round(np.stack([x, y], 1)).astype(np.int32)
            cv2.polylines(ri, [pts], False, width, 1)
            px, py = pts[0]
            if 0 <= px < geo.W and 0 <= py < geo.H:
                src[py, px] = True
    ri[C != 0] = 0
    mask = thin(ri > 0)
    ri = np.where(mask, ri, 0).astype(np.uint8)
    out = np.where(C == 0, 255, 254).astype(np.uint8)
    out[mask] = ri[mask]
    out[mask & src] = 0
    return out


def trees_bmp(w, terr):
    t = np.array([0 if x not in ("forest", "jungle") else (3 if x == "forest" else 4) for x in terr], np.uint8)
    small = cv2.resize(w["P"].astype(np.int32).astype(np.float32), TREES_SIZE, interpolation=cv2.INTER_NEAREST).astype(np.int32)
    return t[small]


def cities_bmp(places):
    img = np.zeros((geo.H, geo.W), np.float32)
    for p in places:
        if p["pop"] >= 50000:
            img[p["y"], p["x"]] += np.sqrt(p["pop"] / 50000.0)
    img = cv2.GaussianBlur(img, (0, 0), 2.2)
    img = np.clip(img / max(np.percentile(img[img > 0], 99), 1e-6) * 255, 0, 255).astype(np.uint8)
    return img


def preview(w, S, state_of, table, rast, path, width=1600):
    P = w["P"]
    tags = sorted(table)
    tag_idx = {t: i + 1 for i, t in enumerate(tags)}
    cols = np.zeros((len(tags) + 1, 3), np.uint8)
    for t, i in tag_idx.items():
        cols[i] = table[t]["color"]
    prov_state = state_of
    prov_tag = np.zeros(w["N"] + 1, np.int32)
    for s in S:
        for p in s["provs"]:
            prov_tag[p] = tag_idx[s["tag"]]
    T = prov_tag[P]
    St = prov_state[P]
    kind = w["kind"]
    img = cols[T].astype(np.float32)
    sea = np.array([k == "sea" for k in kind])[P]
    lake = np.array([k == "lake" for k in kind])[P]
    h = cv2.resize(np.load(data.CACHE / "dem.npy").astype(np.float32), (geo.W, geo.H))
    shade = np.clip(1.0 + cv2.Sobel(cv2.GaussianBlur(np.maximum(h, 0), (0, 0), 1.5), cv2.CV_32F, 1, 0, ksize=3) / 9000.0, 0.8, 1.2)
    img *= shade[..., None]
    img[sea] = (28, 52, 96)
    img[lake] = (70, 120, 190)
    # borders
    sb = np.zeros(P.shape, bool)
    cb = np.zeros(P.shape, bool)
    for a, b, sl_a, sl_b in ((St, St, (slice(None), slice(None, -1)), (slice(None), slice(1, None))),
                             (St, St, (slice(None, -1), slice(None)), (slice(1, None), slice(None)))):
        d = a[sl_a] != b[sl_b]
        sb[sl_a] |= d
    for sl_a, sl_b in (((slice(None), slice(None, -1)), (slice(None), slice(1, None))),
                       ((slice(None, -1), slice(None)), (slice(1, None), slice(None)))):
        d = (T[sl_a] != T[sl_b]) & (T[sl_a] > 0) & (T[sl_b] > 0)
        cb[sl_a] |= d
    sb &= ~sea & ~lake
    img[sb] = img[sb] * 0.62
    cb = cv2.dilate(cb.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    img[cb & ~sea] = (20, 20, 20)
    out = cv2.resize(np.clip(img, 0, 255).astype(np.uint8), (width, int(width * geo.H / geo.W)), interpolation=cv2.INTER_AREA)
    Image.fromarray(out).save(path, quality=88, optimize=True)
