import struct
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from map1990.common import GEO  # noqa: E402


class LccTest(unittest.TestCase):
    def test_origin(self):
        from map1990 import geodata
        lon, lat = geodata.lcc_inverse(np.array([0.0]), np.array([0.0]))
        self.assertAlmostEqual(lon[0], 10.5, places=6)
        self.assertAlmostEqual(lat[0], 51.0, places=6)

    def test_round_trip(self):
        from map1990 import geodata
        lon, lat = np.array([6.1, 13.4, 14.9]), np.array([47.5, 52.5, 54.6])
        x, y = geodata.lcc_forward(lon, lat)
        lon2, lat2 = geodata.lcc_inverse(x, y)
        self.assertTrue(np.allclose(lon, lon2, atol=1e-7) and np.allclose(lat, lat2, atol=1e-7))


class WkbTest(unittest.TestCase):
    def test_polygon_and_multipolygon(self):
        from map1990 import geodata
        ring = [(0, 0), (1, 0), (1, 1), (0, 0)]
        poly = struct.pack("<BII", 1, 3, 1) + struct.pack("<I", 4) + b"".join(struct.pack("<dd", *p) for p in ring)
        multi = struct.pack("<BII", 1, 6, 2) + poly + poly
        self.assertEqual(len(geodata.parse_wkb(poly)), 1)
        polys = geodata.parse_wkb(multi)
        self.assertEqual(len(polys), 2)
        self.assertEqual(polys[1][0].shape, (4, 2))

    def test_decimate_keeps_ends(self):
        from map1990 import geodata
        ring = np.array([[0, 0], [0.001, 0], [0.002, 0], [1, 0], [1, 1], [0, 0]], float)
        d = geodata.decimate(ring, 0.01)
        self.assertTrue((d[0] == ring[0]).all() and (d[-1] == ring[-1]).all() and len(d) == 4)


@unittest.skipUnless((GEO / "vg-hist.gpkg").exists(), "run tools/fetch_geo.py")
class DataTest(unittest.TestCase):
    def test_vghist_1989(self):
        from map1990 import geodata
        feats = geodata.read_vghist(GEO / "vg-hist.gpkg")
        self.assertEqual({p["stg"] for p, _ in feats}, {"DEU", "DDR", "XWB"})
        self.assertEqual(len({p["land"] for p, _ in feats if p["stg"] == "DDR"}), 15)   # 14 Bezirke + East Berlin
        wb = next(polys for p, polys in feats if p["stg"] == "XWB")
        lon, lat = wb[0][0].mean(0)
        self.assertTrue(13.0 < lon < 13.5 and 52.3 < lat < 52.7, (lon, lat))

    def test_korea_provinces(self):
        from map1990 import geodata
        feats = geodata.read_geojson(GEO / "ne_10m_admin_1_states_provinces.geojson")
        codes = {p["iso_3166_2"] for p, _ in feats if p["adm0_a3"] in ("KOR", "PRK")}
        self.assertTrue({"KR-11", "KP-01"} <= codes)

    def test_geonames(self):
        from map1990 import geodata
        cities = geodata.read_geonames(GEO / "cities15000.zip")
        leipzig = [c for c in cities if c.name == "Leipzig" and c.cc == "DE"]
        self.assertTrue(leipzig and leipzig[0].pop > 500_000)


if __name__ == "__main__":
    unittest.main()
