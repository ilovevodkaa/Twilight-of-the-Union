import json
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from map1990 import common  # noqa: E402

POINTS = json.loads((common.DATA / "georef_gcp.json").read_text(encoding="utf-8"))["points"]


class GeorefTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from map1990.georef import Georef
        cls.g = Georef()
        cls.pts = np.array([p[:4] for p in POINTS])

    def test_fits_its_control_points(self):
        x, row = self.g.to_px(self.pts[:, 0], self.pts[:, 1])
        err = np.hypot(x - self.pts[:, 2], row - self.pts[:, 3])
        self.assertLess(np.median(err), 5.0)        # vanilla VP markers are placed by eye: 3-5 px noise

    def test_berlin_and_seoul(self):
        for name, lon, lat in (("Berlin", 13.405, 52.52), ("Seoul", 126.978, 37.566)):
            k = [i for i, p in enumerate(POINTS) if p[4] == name]
            self.assertTrue(k, name)
            x, row = self.g.to_px([lon], [lat])
            self.assertLess(np.hypot(x[0] - self.pts[k[0], 2], row[0] - self.pts[k[0], 3]), 6.0, name)

    def test_vectorised(self):
        x, row = self.g.to_px(np.linspace(5, 15, 1000), np.linspace(47, 55, 1000))
        self.assertEqual(x.shape, (1000,))
        self.assertTrue(np.all(np.diff(x) > 0))


if __name__ == "__main__":
    unittest.main()
