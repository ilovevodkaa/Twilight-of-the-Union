"""Download and cache the raw geodata used by tools/build_map.py.

Everything lands in tools/cache/ (gitignored):
  * Natural Earth 10m vector layers (GeoJSON, github mirror nvkelso/natural-earth-vector)
  * Mapzen/AWS "Terrarium" elevation tiles (zoom 5, public S3 bucket elevation-tiles-prod),
    stitched and resampled to the map's equirectangular grid -> dem.npy (int16 metres,
    negative = bathymetry). Terrarium is derived from SRTM/ETOPO1/GEBCO; this is the
    "ETOPO-like low-res DEM" the heightmap is built from.
"""
import json
import math
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import requests

from . import geo

CACHE = Path(__file__).resolve().parent.parent / "cache"
NE_BASE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
NE_LAYERS = [
    "ne_10m_admin_0_countries",
    "ne_10m_admin_1_states_provinces",
    "ne_10m_populated_places",
    "ne_10m_land",
    "ne_10m_lakes",
    "ne_10m_rivers_lake_centerlines",
    "ne_10m_geography_marine_polys",
]
TILE_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
ZOOM = 5


def _get(url, tries=5):
    last = None
    for i in range(tries):
        try:
            r = requests.get(url, timeout=120)
            r.raise_for_status()
            return r.content
        except Exception as e:  # network hiccup: back off and retry
            last = e
            time.sleep(2 ** i)
    raise RuntimeError(f"download failed: {url}: {last}")


def fetch_ne():
    CACHE.mkdir(parents=True, exist_ok=True)
    for name in NE_LAYERS:
        p = CACHE / f"{name}.geojson"
        if not p.exists() or p.stat().st_size < 1000:
            print("download", name, flush=True)
            p.write_bytes(_get(NE_BASE + name + ".geojson"))


def load_ne(name):
    with open(CACHE / f"{name}.geojson", encoding="utf-8") as f:
        return json.load(f)["features"]


def _tile(args):
    z, x, y = args
    p = CACHE / "tiles" / f"{z}_{x}_{y}.png"
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(_get(TILE_URL.format(z=z, x=x, y=y)))
    return p


def build_dem():
    """Stitch Terrarium tiles and resample to the map grid. Cached as dem.npy."""
    out = CACHE / "dem.npy"
    if out.exists():
        return np.load(out)
    import cv2
    n = 2 ** ZOOM
    def ty(lat):
        s = math.sin(math.radians(lat))
        return (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n
    y0 = int(math.floor(ty(geo.LAT_TOP))) - 0
    y1 = int(math.floor(ty(geo.LAT_BOT)))
    jobs = [(ZOOM, x, y) for y in range(y0, y1 + 1) for x in range(n)]
    print("fetching", len(jobs), "elevation tiles", flush=True)
    with ThreadPoolExecutor(8) as ex:
        paths = list(ex.map(_tile, jobs))
    from PIL import Image
    full = np.zeros(((y1 - y0 + 1) * 256, n * 256), np.float32)
    for (z, x, y), p in zip(jobs, paths):
        a = np.asarray(Image.open(p).convert("RGB")).astype(np.float32)
        full[(y - y0) * 256:(y - y0 + 1) * 256, x * 256:(x + 1) * 256] = a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768
    # map grid pixel -> lon/lat -> mercator tile coords
    cols = (np.arange(geo.W) + 0.5) / geo.W * n * 256
    lats = geo.LAT_TOP - (np.arange(geo.H) + 0.5) * (geo.LAT_TOP - geo.LAT_BOT) / geo.H
    s = np.sin(np.radians(lats))
    rows = (0.5 - np.log((1 + s) / (1 - s)) / (4 * np.pi)) * n * 256 - y0 * 256
    mapx = np.tile(cols.astype(np.float32), (geo.H, 1))
    mapy = np.tile(rows.astype(np.float32)[:, None], (1, geo.W))
    dem = cv2.remap(full, mapx, mapy, cv2.INTER_LINEAR)
    dem = np.clip(dem, -11000, 9000).astype(np.int16)
    np.save(out, dem)
    return dem


if __name__ == "__main__":
    fetch_ne()
    build_dem()
