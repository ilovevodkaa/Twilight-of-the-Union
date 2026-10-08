import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from map1990.geodata import City  # noqa: E402


class CityRulesTest(unittest.TestCase):
    def test_vp_tiers(self):
        from map1990 import cities
        self.assertEqual([cities.vp_value(p) for p in (120_000, 300_000, 700_000, 2_000_000, 9_000_000)],
                         [1, 2, 3, 5, 10])

    def test_russian_name_picks_the_russian_spelling(self):
        # real GeoNames alternate names: Russian next to Bulgarian, Serbian, Belarusian and Ukrainian spellings
        from map1990 import cities
        cases = [("Leipzig", "DE", ["Лайпциг", "Лајпциг", "Лейпциг", "Лейпцыг"], "Лейпциг"),
                 ("Kiel", "DE", ["Кил", "Киль", "Кіль"], "Киль"),
                 ("Wolfsburg", "DE", ["Волфсбург", "Вольфсбург"], "Вольфсбург"),
                 ("Halle (Saale)", "DE", ["Галле", "Хале"], "Галле"),
                 ("Busan", "KR", ["Бусан", "Пусан"], "Пусан"),
                 ("Daegu", "KR", ["Тегу", "Тэгу", "Тэгү"], "Тэгу"),
                 ("Bremen", "DE", ["Бремен", "Брэмен", "Брэмэн"], "Бремен"),
                 ("Osnabrück", "DE", ["Аснабрук", "Оснабрик", "Оснабрюк"], "Оснабрюк"),
                 ("Düsseldorf", "DE", ["Дзюсельдорф", "Диселдорф", "Дюселдорф", "Дюссельдорф"], "Дюссельдорф"),
                 ("Essen", "DE", ["Есен", "Ессен", "Эссен", "Эсэн"], "Эссен"),
                 ("Rostock", "DE", ["Ростак", "Росток", "Рошток", "Рощок"], "Росток"),
                 ("Dresden", "DE", ["Дрезден", "Дрэздэн"], "Дрезден"),
                 ("Munich", "DE", ["München", "Минхен", "Мюнхен", "Мүнхен"], "Мюнхен"),
                 ("Trier", "DE", ["Трев", "Трир", "Трыр"], "Трир"),
                 ("Kassel", "DE", ["Касел", "Касель", "Кассель"], "Кассель"),
                 ("Mannheim", "DE", ["Мангейм", "Манхайм"], "Мангейм"),
                 ("Frankfurt am Main", "DE", ["Франкфурт", "Франкфурт на Майн", "Франкфурт-на-Майне"],
                  "Франкфурт-на-Майне"),
                 ("Incheon", "KR", ["Инчон", "Инчхон", "Инчхън"], "Инчхон"),
                 ("Namp’o", "KP", ["Намбо", "Нампхо"], "Нампхо")]
        for name, cc, alt, want in cases:
            c = City(1, name, alt, 0, 0, "PPL", cc, "", 200_000)
            self.assertEqual(cities.russian_name(c), want, name)

    def test_transliteration_fallback(self):
        from map1990 import cities
        c = City(2, "Wolfsburg", [], 52.4, 10.8, "PPL", "DE", "06", 123000)
        self.assertEqual(cities.russian_name(c), "Вольфсбург")

    def test_overrides(self):
        from map1990 import cities
        seoul = City(1, "Seoul", ["Сеул", "Соул"], 0, 0, "PPLC", "KR", "", 9_000_000)
        self.assertEqual(cities.russian_name(seoul), "Сеул")

    def test_korean_english_names_in_vanilla_style(self):
        from map1990 import cities
        for raw, want in (("Sariwŏn-si", "Sariwon"), ("P’yŏngsŏng", "Pyongsong"), ("Paech’ŏn-ŭp", "Paechon"),
                          ("Donghae City", "Donghae"), ("Jeju City", "Jeju"), ("Chaeryŏng-ni", "Chaeryong")):
            self.assertEqual(cities.english_name(raw, "KP"), want, raw)
        self.assertEqual(cities.english_name("Göttingen", "DE"), "Göttingen")

    def test_rename_1990(self):
        from map1990 import cities
        self.assertEqual(cities.RENAMES_1990[("DE", "Chemnitz")][0], "Karl-Marx-Stadt")


class PointInPolygonTest(unittest.TestCase):
    def test_square_with_inner_point(self):
        import numpy as np
        from map1990 import cities
        sq = [[np.array([[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]], float)]]
        self.assertTrue(cities.inside(2, 2, sq))
        self.assertFalse(cities.inside(5, 2, sq))


try:
    from map1990 import common as _common
    _GAME = _common.find_game()
    _DATA = (_common.GEO / "vg-hist.gpkg").exists()
except SystemExit:
    _GAME, _DATA = None, False


@unittest.skipUnless(_GAME and _DATA, "game or geodata missing")
class SelectTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import numpy as np
        from map1990 import cities
        from map1990.georef import Georef
        from map1990.raster import label_zone
        from map1990.units import ZONES
        from map1990.vanilla import VanillaMap
        vm = VanillaMap(_GAME)
        cls.zone = ZONES["pilot"]
        g = Georef()
        lab = label_zone(vm, g, cls.zone)
        land = np.isin(vm.ids, [p for p, v in vm.provs.items() if v.kind == "land"])
        cls.cities = cities.select(cls.zone, lab, g, land)
        cls.keys = [u.key for u in cls.zone.units]

    def unit_of(self, name):
        return [self.keys[c.unit] for c in self.cities if c.name_en == name]

    def test_berlins(self):
        self.assertEqual(self.unit_of("Berlin"), ["DE-QQB"])
        self.assertEqual(self.unit_of("West Berlin"), ["DE-QBE"])
        self.assertEqual(self.unit_of("Potsdam"), ["DE-QQP"])

    def test_neighbouring_capitals_both_kept(self):
        self.assertEqual(self.unit_of("Mainz"), ["DE-QRP"])
        self.assertEqual(self.unit_of("Wiesbaden"), ["DE-QHE"])

    def test_every_unit_has_its_capital(self):
        from map1990 import cities
        for i, u in enumerate(self.zone.units):
            here = {cities.norm(c.name_en) for c in self.cities if c.unit == i}
            self.assertIn(cities.norm(u.capital), here, u.key)


if __name__ == "__main__":
    unittest.main()
