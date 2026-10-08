import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from map1990 import common  # noqa: E402

try:
    GAME = common.find_game()
except SystemExit:
    GAME = None


class UnitsDataTest(unittest.TestCase):
    def test_pilot_units(self):
        from map1990.units import ZONES
        z = ZONES["pilot"]
        keys = [u.key for u in z.units]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(sum(u.tag in ("GER", "DDR") for u in z.units), 25)
        self.assertEqual(sum(u.tag in ("KOR", "PRK") for u in z.units), 21)
        self.assertTrue(all(u.name_en and u.name_ru and u.capital for u in z.units))


@unittest.skipUnless(GAME and (common.GEO / "vg-hist.gpkg").exists(), "game or geodata missing")
class RasterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from map1990.georef import Georef
        from map1990.raster import label_zone
        from map1990.units import ZONES
        from map1990.vanilla import VanillaMap
        cls.vm = VanillaMap(GAME)
        cls.zone = ZONES["pilot"]
        cls.lab = label_zone(cls.vm, Georef(), cls.zone)

    def area(self, key):
        i = [u.key for u in self.zone.units].index(key)
        return int((self.lab.unit == i).sum())

    def test_every_unit_present(self):
        for i, u in enumerate(self.zone.units):
            self.assertGreater(int((self.lab.unit == i).sum()), 0, u.key)

    def test_sizes(self):
        self.assertTrue(2000 < self.area("DE-QBY") < 4500, self.area("DE-QBY"))   # Bavaria, 70 550 km2
        self.assertTrue(8 <= self.area("DE-QBE") <= 60, self.area("DE-QBE"))      # West Berlin, 480 km2

    def test_land_in_windows_is_labelled(self):
        land = np.isin(self.vm.ids, [p for p, v in self.vm.provs.items() if v.kind == "land"])
        for x0, y0, x1, y1 in self.lab.boxes:
            self.assertFalse(((self.lab.unit[y0:y1, x0:x1] == -1) & land[y0:y1, x0:x1]).any())

    def test_no_landlocked_speckles(self):
        # a gap between two burnt Kreis polygons must not leave a pixel of the neighbouring country inside a unit
        from scipy import ndimage
        land = np.isin(self.vm.ids, [p for p, v in self.vm.provs.items() if v.kind == "land"])
        four = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], bool)
        for x0, y0, x1, y1 in self.lab.boxes:
            u, ln = self.lab.unit[y0:y1, x0:x1], land[y0:y1, x0:x1]
            for v in np.unique(u[ln]):
                parts, k = ndimage.label((u == v) & ln, four)
                sizes = np.bincount(parts.ravel())
                for j in np.nonzero((sizes < common.MIN_PROVINCE_PX) & (np.arange(len(sizes)) > 0))[0]:
                    ring = ndimage.binary_dilation(parts == j, four) & (parts != j) & ln
                    self.assertFalse(ring.any(), (int(v), int(sizes[j])))     # small pieces only as islands

    def test_coast_matches(self):
        # the real coastline lands on the vanilla one after the per-window affine (ICP) refinement
        for misfit in self.lab.misfit:
            self.assertLessEqual(misfit, 1.5)


if __name__ == "__main__":
    unittest.main()
