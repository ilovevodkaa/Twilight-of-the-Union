import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from map1990.common import px_of  # noqa: E402


class FormatTest(unittest.TestCase):
    def test_building_line(self):
        from map1990 import mapfiles
        self.assertEqual(mapfiles.fmt_building(64, "air_base", 3010, 10.234, 1400, 1.5, 0),
                         "64;air_base;3010.00;10.23;1400.00;1.50;0")

    def test_stack_line(self):
        from map1990 import mapfiles
        self.assertEqual(mapfiles.fmt_stack(6521, 38, 3010.5, 10.0, 1400.25, 0.0, 0.3),
                         "6521;38;3010.50;10.00;1400.25;0.00;0.30")

    def test_position_round_trip(self):
        from map1990 import mapfiles
        for row, col in ((0, 0), (480, 3007), (2047, 5631)):
            x, z = mapfiles.pos_of(row, col)
            self.assertEqual(px_of(x, z), (row, col))

    def test_railway_path_avoids_gaps(self):
        from map1990 import mapfiles
        adj = {1: {2}, 2: {1, 3}, 3: {2}}
        self.assertEqual(mapfiles.bridge([1, 3], adj, land={1, 2, 3}), [1, 2, 3])

    def test_railway_drops_repeats_and_water(self):
        from map1990 import mapfiles
        adj = {1: {2, 9}, 2: {1, 3}, 3: {2, 9}, 9: {1, 3}}
        self.assertEqual(mapfiles.bridge([1, 1, 9, 3], adj, land={1, 2, 3}), [1, 2, 3])


try:
    from map1990 import common as _common
    _GAME = _common.find_game()
    _DATA = (_common.GEO / "vg-hist.gpkg").exists()
except SystemExit:
    _GAME, _DATA = None, False


@unittest.skipUnless(_GAME and _DATA, "game or geodata missing")
class WrittenMapTest(unittest.TestCase):
    def test_written_map_passes_the_checker(self):
        import importlib
        import tempfile

        import build_world_1990 as w
        from map1990 import check, mapfiles, states as st
        from map1990.assemble import assemble
        from map1990.georef import Georef
        from map1990.units import ZONES
        from map1990.vanilla import VanillaMap
        from world1990 import names
        names = importlib.reload(names)
        vm = VanillaMap(_GAME)
        states = w.load_states(_GAME)
        w.assign(states)
        zm = assemble(vm, Georef(), ZONES["pilot"], states, log=lambda *a: None)
        st.apply(zm, vm, ZONES["pilot"], states, names)
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            mapfiles.write_all(zm, vm, states, tmp / "map")
            w.write_states(states, tmp / "history/states")
            problems = check.run(tmp, _GAME, mod_map=tmp / "map")
        self.assertEqual(problems[:40], [])


if __name__ == "__main__":
    unittest.main()
