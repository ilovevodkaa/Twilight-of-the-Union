import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from map1990 import common  # noqa: E402

try:
    GAME = common.find_game()
except SystemExit:
    GAME = None


@unittest.skipUnless(GAME, "HOI4 not installed")
class CheckTest(unittest.TestCase):
    def test_segments_counted_like_the_report(self):
        from map1990.check import border_segments
        from map1990.vanilla import VanillaMap
        n = border_segments(VanillaMap(GAME).ids)
        self.assertTrue(35_000 < n < 46_000, n)          # the big-map report counted 40 694

    def test_vanilla_based_map_is_clean(self):
        # the mod's map is still the vanilla one (with 1990 owners): vanilla quirks must not count as problems
        from map1990 import check
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            shutil.copytree(GAME / "history/states", tmp / "history/states")
            self.assertEqual(check.run(tmp, GAME, mod_map=tmp / "no_map"), [])

    def test_broken_state_is_reported(self):
        from map1990 import check
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            shutil.copytree(common.ROOT / "history/states", tmp / "history/states")
            f = next((tmp / "history/states").glob("64-*.txt"))
            f.write_text(f.read_text(encoding="utf-8").replace("6521 ", ""), encoding="utf-8")
            problems = check.run(tmp, GAME, mod_map=common.ROOT / "map")
            self.assertTrue(any("6521" in p for p in problems), problems[:5])


if __name__ == "__main__":
    unittest.main()
