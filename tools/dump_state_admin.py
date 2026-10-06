"""Dumps tools/state_admin.json: state id -> {"r": [[adm0, admin-1 name, area_px], ...], "g": [[ISO3, area_px], ...]}.
"r" is the admin-1 region the generator used (coarse in the Balkans), "g" is the geographic truth: the Natural Earth
admin-0 polygon (2020s borders: Slovenia, Croatia, Kosovo, Moldova ...) containing each province's representative point.
Both largest first, from the cached province raster (tools/cache/work/world.pkl, produced by build_map.py). The cores / claims script uses this committed
file so it does not need the cache.   Usage: python tools/dump_state_admin.py
"""
import collections
import glob
import json
import pickle

from shapely.geometry import Point, shape
from shapely.strtree import STRtree
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
rast, w = pickle.load(open(ROOT / "tools/cache/work/world.pkl", "rb"))
R = rast["regions"]
import sys
sys.path.insert(0, str(ROOT / "tools"))
from map import geo  # noqa: E402

adm = json.load(open(ROOT / "tools/cache/ne_10m_admin_0_countries.geojson", encoding="utf-8"))["features"]
geoms = [shape(f["geometry"]) for f in adm]
isos = [f["properties"]["ADM0_A3"] for f in adm]
tree = STRtree(geoms)


def iso_at(x, y):
    lon, lat = geo.px_to_lonlat(float(x), float(y))
    pt = Point(float(lon), float(lat))
    for i in tree.query(pt):
        if geoms[int(i)].contains(pt):
            return isos[int(i)]
    return None

out = {}
for f in sorted(glob.glob(str(ROOT / "history/states/*.txt"))):
    t = open(f, encoding="utf-8-sig").read()
    sid = int(re.search(r"\bid\s*=\s*(\d+)", t).group(1))
    provs = [int(x) for x in re.search(r"provinces\s*=\s*\{([^}]*)\}", t).group(1).split()]
    c = collections.Counter()
    g = collections.Counter()
    for p in provs:
        r = R[int(w["region"][p])]
        c[(r["adm0"], r["name_en"])] += int(w["area"][p])
        g[iso_at(w["rx"][p], w["ry"][p]) or r["adm0"]] += int(w["area"][p])
    out[sid] = {"r": [[a, n, v] for (a, n), v in c.most_common()], "g": [[a, v] for a, v in g.most_common()]}
(ROOT / "tools/state_admin.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(len(out))
