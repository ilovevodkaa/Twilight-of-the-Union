import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from map1990 import common  # noqa: E402

try:
    GAME = common.find_game()
except SystemExit:
    GAME = None


@unittest.skipUnless(GAME, "HOI4 not installed")
class VanillaMapTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from map1990.vanilla import VanillaMap
        cls.vm = VanillaMap(GAME)

    def test_definitions_and_raster(self):
        vm = self.vm
        self.assertEqual(len(vm.provs), 13413)
        self.assertEqual(vm.ids.shape, (2048, 5632))
        self.assertEqual(sum(p.kind == "land" for p in vm.provs.values()), 10154)
        self.assertGreater((vm.ids > 0).mean(), 0.999)

    def test_berlin_is_land(self):
        vm = self.vm
        self.assertEqual(vm.provs[6521].kind, "land")
        self.assertTrue((vm.ids == 6521).sum() >= 10)

    def test_files(self):
        vm = self.vm
        self.assertGreater(len(vm.regions), 100)
        self.assertIn(6521, {p for r in vm.regions.values() for p in r.items})
        self.assertEqual(len(vm.buildings), 66664)
        self.assertTrue(all(len(f) >= 7 for f in vm.buildings))
        self.assertTrue(vm.railways and vm.supply_nodes)
        row, col = common.px_of(float(vm.buildings[0][2]), float(vm.buildings[0][4]))
        self.assertTrue(0 <= row < 2048 and 0 <= col < 5632)


if __name__ == "__main__":
    unittest.main()
