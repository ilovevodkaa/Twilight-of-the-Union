import sys
import unittest
from pathlib import Path

import numpy as np
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from map1990 import common  # noqa: E402

try:
    GAME = common.find_game()
except SystemExit:
    GAME = None


@unittest.skipUnless(GAME and (common.GEO / "vg-hist.gpkg").exists(), "game or geodata missing")
class AssembleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import build_world_1990 as w
        from map1990.assemble import assemble
        from map1990.georef import Georef
        from map1990.units import ZONES
        from map1990.vanilla import VanillaMap
        cls.vm = VanillaMap(GAME)
        cls.states = w.load_states(GAME)
        w.assign(cls.states)
        cls.zone = ZONES["pilot"]
        cls.zm = assemble(cls.vm, Georef(), cls.zone, cls.states, log=lambda *a: None)

    def test_sea_untouched(self):
        sea = np.isin(self.vm.ids, [p for p, v in self.vm.provs.items() if v.kind != "land"])
        self.assertTrue((self.zm.ids[sea] == self.vm.ids[sea]).all())

    def test_ids_contiguous_and_all_land_present(self):
        ids = sorted(self.zm.provs)
        self.assertEqual(ids, list(range(1, len(ids) + 1)))
        present = set(np.unique(self.zm.ids).tolist())
        land = {p for p, v in self.zm.provs.items() if v.kind == "land"}
        self.assertFalse(land - present)

    def test_density_and_cities(self):
        self.assertGreater(len(self.zm.zone_provs), 1.6 * len(self.zm.pool))
        names = {c.name_en for c, _ in self.zm.city_prov}
        self.assertTrue({"Leipzig", "Seoul", "Pyongyang", "West Berlin", "Karl-Marx-Stadt"} <= names)
        provs = [p for _, p in self.zm.city_prov]
        self.assertEqual(len(provs), len(set(provs)))           # every city its own province

    def test_new_provinces_connected_and_big(self):
        for p in self.zm.zone_provs:
            m = self.zm.ids == p
            self.assertGreaterEqual(int(m.sum()), common.MIN_PROVINCE_PX, p)

    def test_berlin_split(self):
        keys = [u.key for u in self.zone.units]
        self.assertNotEqual(self.zm.unit_state[keys.index("DE-QBE")], self.zm.unit_state[keys.index("DE-QQB")])

    def test_colours_unique(self):
        rgbs = [p.rgb for p in self.zm.provs.values()]
        self.assertEqual(len(rgbs), len(set(rgbs)))

    def test_lakes_of_rebuilt_states_have_a_unit(self):
        tags = {u.tag for u in self.zone.units}
        lakes = {p for s in self.states.values() if s["owner"] in tags for p in s["provs"]
                 if self.vm.provs[p].kind == "lake"}
        self.assertEqual(set(self.zm.lake_unit), lakes)

    def test_outside_states_keep_a_province(self):      # Review Focus: an outside state must not vanish
        tags = {u.tag for u in self.zone.units}
        for s, st in self.states.items():
            land = [p for p in st["provs"] if self.vm.provs[p].kind == "land"]
            if st["owner"] not in tags and land:
                self.assertTrue(any(p not in self.zm.pool for p in land), s)

    def test_unit_in_one_region(self):
        for ui in range(len(self.zone.units)):
            regions = {self.zm.region_of[p] for p, u in self.zm.zone_provs.items() if u == ui}
            self.assertEqual(len(regions), 1, self.zone.units[ui].key)

    def test_kept_neighbours_stay_connected(self):          # Review Focus: provinces on the zone's outer border
        for p in self.zm.changed - set(self.zm.zone_provs):
            m = self.zm.ids == p
            if m.sum() and not (self.vm.ids == p).sum() < common.MIN_PROVINCE_PX:
                self.assertEqual(ndimage.label(m)[1], ndimage.label(self.vm.ids == p)[1], p)


if __name__ == "__main__":
    unittest.main()
