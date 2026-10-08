import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from map1990 import common  # noqa: E402

try:
    GAME = common.find_game()
except SystemExit:
    GAME = None

TAGS = ("GER", "DDR", "KOR", "PRK")


def manpower(states, tag):
    return sum(int(re.search(r"manpower\s*=\s*(\d+)", s["text"]).group(1)) for s in states.values() if s["owner"] == tag)


@unittest.skipUnless(GAME and (common.GEO / "vg-hist.gpkg").exists(), "game or geodata missing")
class StatesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import importlib

        import build_world_1990 as w
        from map1990 import states as st
        from map1990.assemble import assemble
        from map1990.georef import Georef
        from map1990.units import ZONES
        from map1990.vanilla import VanillaMap
        from world1990 import names
        cls.names = importlib.reload(names)
        cls.vm = VanillaMap(GAME)
        cls.states = w.load_states(GAME)
        w.assign(cls.states)
        cls.before = {t: manpower(cls.states, t) for t in TAGS}
        cls.lakes = {p for s in cls.states.values() if s["owner"] in TAGS for p in s["provs"]
                     if cls.vm.provs[p].kind == "lake"}
        cls.zone = ZONES["pilot"]
        cls.zm = assemble(cls.vm, Georef(), cls.zone, cls.states, log=lambda *a: None)
        cls.res = st.apply(cls.zm, cls.vm, cls.zone, cls.states, cls.names)

    def test_ids_contiguous(self):
        self.assertEqual(sorted(self.states), list(range(1, len(self.states) + 1)))

    def test_manpower_preserved(self):
        for t, v in self.before.items():
            self.assertLess(abs(manpower(self.states, t) - v), 1000, t)

    def test_capitals(self):
        caps = self.res["capitals"]
        self.assertEqual(self.names.STATE_NAMES[caps["DDR"]][0], "East Berlin")
        self.assertEqual(self.states[caps["KOR"]]["owner"], "KOR")

    def test_every_province_in_one_state(self):
        seen = {}
        for s, st in self.states.items():
            for p in st["provs"]:
                self.assertNotIn(p, seen, (p, s, seen.get(p)))
                seen[p] = s
        land = {p for p, v in self.zm.provs.items() if v.kind == "land"}
        self.assertFalse(land - set(seen))

    def test_lakes_kept(self):
        held = {p for st in self.states.values() for p in st["provs"]}
        self.assertTrue(self.lakes <= held)

    def test_naval_bases_are_coastal(self):          # Review Focus: naval bases after renumbering
        for s, st in self.states.items():
            b = next((v for k, _, v in st["hist"] if k == "buildings"), [])
            for k, _, v in b:
                if k.isdigit() and any(x[0] == "naval_base" for x in v):
                    self.assertTrue(self.zm.provs[int(k)].coastal, (s, k))

    def test_victory_points_and_names(self):
        vps = {}
        for st in self.states.values():
            for k, _, v in st["hist"]:
                if k == "victory_points":
                    vps[int(v[0][0])] = float(v[1][0])
        berlin = [p for c, p in self.zm.city_prov if c.name_en == "West Berlin"][0]
        self.assertIn(berlin, vps)
        self.assertEqual(self.names.VP_NAMES[berlin], ("West Berlin", "Западный Берлин"))
        self.assertGreater(sum(1 for p in vps if p in self.zm.zone_provs), 140)


if __name__ == "__main__":
    unittest.main()
