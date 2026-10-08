"""Every tag the game loads needs a history file (history/countries is a replace_path): build_world_1990.py writes a
minimal one (capital and politics, nothing that spawns the country) for the releasables the 1990 world does not have."""
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from map1990 import common
    GAME = common.find_game()
except SystemExit:
    GAME = None


@unittest.skipUnless(GAME, "HOI4 not installed")
class ReleaseHistoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import build_world_1990 as w
        cls.w = w
        cls.states = w.load_states(GAME)
        w.assign(cls.states)

    def build(self, root):
        out = root / "history/countries"
        out.mkdir(parents=True, exist_ok=True)
        self.w.write_country_history(self.states, GAME, out)
        self.w.new_tags(root, GAME)
        self.w.write_release_histories(self.states, GAME, root)
        return out

    def test_country_tags_skip_dynamic_ones(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            d = root / "common/country_tags"
            d.mkdir(parents=True)
            (d / "totu_test.txt").write_text('ZZA = "countries/Zed Land.txt"\n', encoding="utf-8")
            tags = self.w.country_tags(GAME, root)
        self.assertEqual(tags["ZZA"], "countries/Zed Land.txt")
        self.assertIn("UKR", tags)
        self.assertNotIn("D01", tags)             # civil war tags after dynamic_tags = yes never get a history

    def test_every_tag_gets_a_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = self.build(root)
            have = {p.name[:3] for p in out.glob("*.txt")}
            self.assertEqual(set(self.w.country_tags(GAME, root)) - have, set())
            self.assertTrue((out / "UKR - Ukraine.txt").exists())

    def test_release_histories_are_generated_shape_and_do_not_spawn(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = self.build(Path(tmp))
            generated = {p.name for p in self.w.generated_histories(out)}
            for name in ("UKR - Ukraine.txt", "LIT - Lithuania.txt", "BAY - Bavaria.txt"):
                self.assertIn(name, generated)
            text = (out / "UKR - Ukraine.txt").read_text(encoding="utf-8-sig")
        for key in ("add_state_core", "transfer_state", "set_cosmetic_tag", "puppet", "oob", "recruit_character"):
            self.assertNotIn(key, text)

    def test_capital_is_a_core_else_the_vanilla_capital(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = self.build(Path(tmp))

            def capital(tag):
                text = next(out.glob(tag + " - *.txt")).read_text(encoding="utf-8-sig")
                return int(re.search(r"^capital = (\d+)", text, re.M).group(1))
            for tag in ("UKR", "LIT", "BAY", "SCO", "TIB", "KUR"):
                self.assertIn(tag, self.states[capital(tag)]["cores"], tag)
            caps = self.w.vanilla_capitals(GAME)
            self.assertEqual(capital("RKO"), caps["RKO"])     # Reichskommissariats have no cores
            ukr = (out / "UKR - Ukraine.txt").read_text(encoding="utf-8-sig")
        self.assertIn("ruling_party = communism", ukr)       # politics of the 1990 owner (SOV)

    def test_hand_written_and_other_files_are_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "history/countries"
            out.mkdir(parents=True)
            mine = {"UKR - Ukraine.txt": "capital = 202\nset_cosmetic_tag = UKR_x\n", "XXX - Other.txt": "x = 1\n"}
            for name, text in mine.items():
                (out / name).write_text(text, encoding="utf-8")
            self.build(root)
            for name, text in mine.items():
                self.assertEqual((out / name).read_text(encoding="utf-8"), text)

    def test_rle_vanilla_flags_get_a_readable_copy(self):
        from world1990 import flags
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            other = root / "gfx/flags/medium/BUK_fascism.tga"       # a file already in the mod is not replaced
            other.parent.mkdir(parents=True)
            other.write_bytes(b"x")
            flags.repair_vanilla(GAME, root)
            head = (root / "gfx/flags/medium/BUK_communism.tga").read_bytes()[:18]
            self.assertEqual(other.read_bytes(), b"x")
        self.assertEqual((head[2], head[16]), (2, 32))     # BUK has a history now: vanilla's RLE file is "Unsupported"

    def test_rebuild_replaces_its_own_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = sorted(p.name for p in self.build(root).glob("*.txt"))
            second = sorted(p.name for p in self.build(root).glob("*.txt"))
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
