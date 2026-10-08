"""Readers for the geodata in tools/data/geo (tools/fetch_geo.py): GeoJSON, the BKG GeoPackage, GeoNames."""
import json
import math
import sqlite3
import struct
import zipfile
from dataclasses import dataclass

import numpy as np


# ------------------------------------------------------------------ GeoJSON
def _polys(geom):
    t, c = geom["type"], geom["coordinates"]
    polys = [c] if t == "Polygon" else c if t == "MultiPolygon" else []
    return [[np.asarray(r, float)[:, :2] for r in poly] for poly in polys]


def read_geojson(path):
    """[(properties with lower-case keys, polygons)]; a polygon is [outer ring, holes...], rings are N x 2 lon/lat."""
    out = []
    for f in json.loads(path.read_text(encoding="utf-8"))["features"]:
        if f.get("geometry"):
            out.append(({k.lower(): v for k, v in f["properties"].items()}, _polys(f["geometry"])))
    return out


def decimate(ring, tol):
    """Drop vertices closer than tol (degrees, Manhattan) to the last kept one; the first and last vertex stay."""
    keep, last = [0], ring[0]
    for i in range(1, len(ring) - 1):
        if abs(ring[i, 0] - last[0]) + abs(ring[i, 1] - last[1]) >= tol:
            keep.append(i)
            last = ring[i]
    keep.append(len(ring) - 1)
    return ring[keep]


# ------------------------------------------------------------------ WKB / GeoPackage
def parse_wkb(b):
    """2D Polygon / MultiPolygon WKB -> list of polygons, each a list of rings (N x 2 float arrays)."""
    return _wkb_geom(b, 0, [])[1]


def _wkb_geom(b, o, polys):
    fmt = "<" if b[o] == 1 else ">"
    t = struct.unpack_from(fmt + "I", b, o + 1)[0]
    o += 5
    if t == 3:
        rings = []
        (nr,) = struct.unpack_from(fmt + "I", b, o)
        o += 4
        for _ in range(nr):
            (k,) = struct.unpack_from(fmt + "I", b, o)
            o += 4
            rings.append(np.frombuffer(b, dtype=fmt + "f8", count=2 * k, offset=o).reshape(k, 2).astype(float))
            o += 16 * k
        polys.append(rings)
        return o, polys
    if t == 6:
        (n,) = struct.unpack_from(fmt + "I", b, o)
        o += 4
        for _ in range(n):
            o, _ = _wkb_geom(b, o, polys)
        return o, polys
    raise ValueError(f"WKB geometry type {t} is not supported (2D Polygon / MultiPolygon only)")


def gpkg_wkb(blob):
    assert blob[:2] == b"GP", "not a GeoPackage geometry"
    env = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}[(blob[3] >> 1) & 7]
    return blob[8 + env:]


# EPSG:5243 ETRS89 / LCC Germany (E-N): GRS80, standard parallels 48 2/3 and 53 2/3, origin 51 N 10.5 E, no offsets
_A, _F = 6378137.0, 1 / 298.257222101
_E = math.sqrt(2 * _F - _F * _F)


def _m(phi):
    return np.cos(phi) / np.sqrt(1 - (_E * np.sin(phi)) ** 2)


def _t(phi):
    es = _E * np.sin(phi)
    return np.tan(np.pi / 4 - phi / 2) / ((1 - es) / (1 + es)) ** (_E / 2)


_P1, _P2, _P0, _L0 = (math.radians(v) for v in (48 + 2 / 3, 53 + 2 / 3, 51.0, 10.5))
_N = (math.log(_m(_P1)) - math.log(_m(_P2))) / (math.log(_t(_P1)) - math.log(_t(_P2)))
_FF = _m(_P1) / (_N * _t(_P1) ** _N)
_RHO0 = _A * _FF * _t(_P0) ** _N


def lcc_forward(lon, lat):
    phi, lam = np.radians(np.asarray(lat, float)), np.radians(np.asarray(lon, float))
    rho = _A * _FF * _t(phi) ** _N
    th = _N * (lam - _L0)
    return rho * np.sin(th), _RHO0 - rho * np.cos(th)


def lcc_inverse(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    rho = np.sign(_N) * np.sqrt(x * x + (_RHO0 - y) ** 2)
    th = np.arctan2(x, _RHO0 - y)
    t = (rho / (_A * _FF)) ** (1 / _N)
    phi = np.pi / 2 - 2 * np.arctan(t)
    for _ in range(10):
        es = _E * np.sin(phi)
        phi = np.pi / 2 - 2 * np.arctan(t * ((1 - es) / (1 + es)) ** (_E / 2))
    return np.degrees(th / _N + _L0), np.degrees(phi)


def read_vghist(gpkg, date="1989-12-31"):
    """Kreise valid on the date: props stg (DEU = FRG, DDR, XWB = West Berlin), land (VGHID2: Land / GDR Bezirk
    code), skz, name; geometry converted to lon/lat."""
    d = f"{date}T00:00:00.000"
    con = sqlite3.connect(str(gpkg))
    rows = con.execute("select STG, VGHID2, SKZ, GEN, geom from vg_hist where BEG <= ? and END >= ?",
                       (d, d)).fetchall()
    con.close()
    out = []
    for stg, land, skz, name, blob in rows:
        polys = [[np.stack(lcc_inverse(r[:, 0], r[:, 1]), 1) for r in poly] for poly in parse_wkb(gpkg_wkb(blob))]
        out.append(({"stg": stg, "land": land, "skz": skz, "name": name}, polys))
    return out


# ------------------------------------------------------------------ GeoNames
@dataclass
class City:
    gid: int
    name: str
    alt: list
    lat: float
    lon: float
    fcode: str
    cc: str
    admin1: str
    pop: int


def read_geonames(path):
    text = zipfile.ZipFile(path).read("cities15000.txt").decode("utf-8")
    out = []
    for line in text.splitlines():
        f = line.split("\t")
        out.append(City(int(f[0]), f[1], f[3].split(",") if f[3] else [], float(f[4]), float(f[5]), f[7], f[8],
                        f[10], int(f[14] or 0)))
    return out
