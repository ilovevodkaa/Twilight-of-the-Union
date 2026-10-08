"""Downloads the geodata the 1990 map is built from into tools/data/geo/ (not in git) and records sha256 in
tools/data/geo/manifest.json. Licences: Natural Earth - public domain; GeoNames - CC BY 4.0;
BKG VG-Hist - CC BY 4.0, "(c) GeoBasis-DE / BKG" in the mod description.

Usage:  python tools/fetch_geo.py [--force]
"""
import argparse
import hashlib
import io
import json
import sys
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from map1990.common import GEO  # noqa: E402

NE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
SOURCES = {     # local file: (url, member to extract from a zip or None)
    "ne_10m_admin_0_countries.geojson": (NE + "ne_10m_admin_0_countries.geojson", None),
    "ne_10m_admin_1_states_provinces.geojson": (NE + "ne_10m_admin_1_states_provinces.geojson", None),
    "cities15000.zip": ("https://download.geonames.org/export/dump/cities15000.zip", None),
    "vg-hist.gpkg": ("https://daten.gdz.bkg.bund.de/produkte/vg/vg-hist/aktuell/vg-hist.lamge.gpkg.gesamt.zip",
                     "vg-hist/vg-hist.gpkg"),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    GEO.mkdir(parents=True, exist_ok=True)
    mf = GEO / "manifest.json"
    manifest = json.loads(mf.read_text(encoding="utf-8")) if mf.exists() else {}
    for name, (url, member) in SOURCES.items():
        out = GEO / name
        if out.exists() and not args.force:
            continue
        print("downloading", url)
        with urllib.request.urlopen(url, timeout=300) as r:
            data = r.read()
        if member:
            data = zipfile.ZipFile(io.BytesIO(data)).read(member)
        out.write_bytes(data)
        manifest[name] = {"url": url, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
                          "date": date.today().isoformat()}
    mf.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print("geodata in", GEO)


if __name__ == "__main__":
    main()
