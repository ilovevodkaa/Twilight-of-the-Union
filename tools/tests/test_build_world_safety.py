"""build_world_1990.py runs in a folder other sessions also write to: it must only touch the files it writes."""
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
class SafetyTest(unittest.TestCase):
    def test_strip_on_startup_keeps_other_files(self):
        import build_world_1990 as w
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            d = root / "common/on_actions"
            d.mkdir(parents=True)
            for name in ("TOTU_DDR_on_actions.txt", "totu_x.txt", "my_own_on_actions.txt"):
                (d / name).write_text("on_actions = {}\n", encoding="utf-8")
            w.strip_on_startup(GAME, root)
            for name in ("TOTU_DDR_on_actions.txt", "totu_x.txt", "my_own_on_actions.txt"):
                self.assertTrue((d / name).exists(), name)

    def test_vanilla_on_actions_come_from_strip_vanilla(self):
        import build_world_1990 as w
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            w.strip_on_startup(GAME, root)
            text = (root / "common/on_actions/00_on_actions.txt").read_text(encoding="utf-8")
            self.assertTrue(text.startswith("# NEUTRALISED COPY"))     # strip_vanilla.py also cuts the event calls
            code = " ".join(line.split("#")[0] for line in text.splitlines())
            self.assertNotIn("country_event", code)

    def test_write_flags_keeps_other_flags(self):
        import build_world_1990 as w
        from world1990 import flags
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            other = root / "gfx/flags/medium/TOTU_GER_UNIFIED.tga"
            other.parent.mkdir(parents=True)
            other.write_bytes(b"x")
            flags.write_flags(GAME, root, w.NEW_TAGS)
            self.assertTrue(other.exists())


@unittest.skipUnless(GAME, "HOI4 not installed")
class TagsSafetyTest(unittest.TestCase):
    def test_new_tags_keeps_other_files(self):
        import build_world_1990 as w
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mine = [root / "common/country_tags/other_tags.txt", root / "common/countries/Other Land.txt"]
            for f in mine:
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text("x", encoding="utf-8")
            w.new_tags(root, GAME)
            self.assertTrue(all(f.exists() for f in mine))
            self.assertTrue((root / "common/country_tags/totu_1990_countries.txt").exists())


@unittest.skipUnless(GAME, "HOI4 not installed")
class HistorySafetyTest(unittest.TestCase):
    def test_write_states_keeps_files_of_other_ids(self):
        import build_world_1990 as w
        states = w.load_states(GAME)
        w.assign(states)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "history/states"
            out.mkdir(parents=True)
            other = out / "9999-Elsewhere.txt"
            other.write_text("state = { id = 9999 }", encoding="utf-8")
            old = out / "1-Old name.txt"
            old.write_text("state = { id = 1 }", encoding="utf-8")
            w.write_states(states, out)
            self.assertTrue(other.exists())
            self.assertFalse(old.exists())          # state 1 under another name: replaced by the new file
            self.assertEqual(len(list(out.glob("*.txt"))), len(states) + 1)

    def test_forts_capped_at_a_level_the_engine_takes(self):
        import build_world_1990 as w
        states = w.load_states(GAME)
        w.assign(states)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            w.write_states(states, out)
            text = (out / states[28]["file"]).read_text(encoding="utf-8")
        self.assertNotIn("bunker = 10", text)      # 1990 refuses level 10: "Trying to set invalid province building"
        self.assertIn("bunker = 3", text)

    def test_only_generated_country_histories_are_replaced(self):
        import shutil
        import build_world_1990 as w
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            for name in ("POL - Poland.txt", "DDR - East Germany.txt"):
                shutil.copy(w.ROOT / "history/countries" / name, out / name)
            (out / "XXX - Other.txt").write_text("capital = 1  set_cosmetic_tag = x", encoding="utf-8")
            self.assertEqual([p.name for p in w.generated_histories(out)], ["POL - Poland.txt"])


if __name__ == "__main__":
    unittest.main()
