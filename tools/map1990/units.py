"""The 1990 administrative units of each rebuild zone (one unit = one state). Germany: BKG VG-Hist Kreise on
31.12.1989 grouped by Land / GDR Bezirk (VGHID2). Korea: Natural Earth admin-1, the post-1990 city splits merged back.
Small units are merged into a neighbour on purpose (user: real 1990 units, the small ones merged)."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Unit:
    key: str
    tag: str            # 1990 owner
    name_en: str
    name_ru: str
    source: str         # "vghist": codes are VGHID2 values; "ne1": Natural Earth iso_3166_2 codes
    codes: tuple
    capital: str        # name of the unit's main city (as cities.select names it)


@dataclass(frozen=True)
class ExtraCity:        # a city GeoNames does not have as such (West Berlin is boroughs there)
    name_en: str
    name_ru: str
    lat: float
    lon: float
    pop: int


@dataclass(frozen=True)
class Zone:
    name: str
    units: tuple
    windows: tuple      # lon0, lat0, lon1, lat1
    density: float      # new provinces per vanilla province of the zone
    city_min_pop: int
    zone_codes: tuple   # Natural Earth adm0_a3 of the countries the units replace
    extra_cities: tuple = field(default_factory=tuple)
    country_capitals: tuple = field(default_factory=tuple)   # (tag, unit key)


def _v(key, tag, en, ru, codes, capital):
    return Unit("DE-" + key, tag, en, ru, "vghist", codes, capital)


def _k(key, tag, en, ru, codes, capital):
    return Unit(key, tag, en, ru, "ne1", codes, capital)


GERMANY = (
    _v("QSH", "GER", "Schleswig-Holstein", "Шлезвиг-Гольштейн", ("QSH",), "Kiel"),
    _v("QHH", "GER", "Hamburg", "Гамбург", ("QHH",), "Hamburg"),
    _v("QNI", "GER", "Lower Saxony", "Нижняя Саксония", ("QNI", "QHB"), "Hannover"),
    _v("QNW", "GER", "North Rhine-Westphalia", "Северный Рейн-Вестфалия", ("QNW",), "Köln"),
    _v("QHE", "GER", "Hesse", "Гессен", ("QHE",), "Frankfurt am Main"),
    _v("QRP", "GER", "Rhineland-Palatinate", "Рейнланд-Пфальц", ("QRP",), "Mainz"),
    _v("QSL", "GER", "Saarland", "Саар", ("QSL",), "Saarbrücken"),
    _v("QBW", "GER", "Baden-Württemberg", "Баден-Вюртемберг", ("QBW",), "Stuttgart"),
    _v("QBY", "GER", "Bavaria", "Бавария", ("QBY",), "München"),
    _v("QBE", "GER", "West Berlin", "Западный Берлин", ("QBE",), "West Berlin"),
    _v("QQR", "DDR", "Rostock", "Росток", ("QQR",), "Rostock"),
    _v("QQS", "DDR", "Schwerin", "Шверин", ("QQS",), "Schwerin"),
    _v("QQN", "DDR", "Neubrandenburg", "Нойбранденбург", ("QQN",), "Neubrandenburg"),
    _v("QQP", "DDR", "Potsdam", "Потсдам", ("QQP",), "Potsdam"),
    _v("QQF", "DDR", "Frankfurt (Oder)", "Франкфурт-на-Одере", ("QQF",), "Frankfurt (Oder)"),
    _v("QQC", "DDR", "Cottbus", "Котбус", ("QQC",), "Cottbus"),
    _v("QQM", "DDR", "Magdeburg", "Магдебург", ("QQM",), "Magdeburg"),
    _v("QQH", "DDR", "Halle", "Галле", ("QQH",), "Halle (Saale)"),
    _v("QQE", "DDR", "Erfurt", "Эрфурт", ("QQE",), "Erfurt"),
    _v("QQG", "DDR", "Gera", "Гера", ("QQG",), "Gera"),
    _v("QQU", "DDR", "Suhl", "Зуль", ("QQU",), "Suhl"),
    _v("QQD", "DDR", "Dresden", "Дрезден", ("QQD",), "Dresden"),
    _v("QQL", "DDR", "Leipzig", "Лейпциг", ("QQL",), "Leipzig"),
    _v("QQK", "DDR", "Karl-Marx-Stadt", "Карл-Маркс-Штадт", ("QQK",), "Karl-Marx-Stadt"),
    _v("QQB", "DDR", "East Berlin", "Восточный Берлин", ("QQB",), "Berlin"),
)

KOREA = (
    _k("KR-11", "KOR", "Seoul", "Сеул", ("KR-11",), "Seoul"),
    _k("KR-26", "KOR", "Busan", "Пусан", ("KR-26",), "Busan"),
    _k("KR-41", "KOR", "Gyeonggi", "Кёнгидо", ("KR-41", "KR-28"), "Incheon"),
    _k("KR-42", "KOR", "Gangwon", "Канвондо", ("KR-42",), "Chuncheon"),
    _k("KR-43", "KOR", "North Chungcheong", "Северная Чхунчхон", ("KR-43",), "Cheongju-si"),
    _k("KR-44", "KOR", "South Chungcheong", "Южная Чхунчхон", ("KR-44", "KR-30", "KR-50"), "Daejeon"),
    _k("KR-45", "KOR", "North Jeolla", "Северная Чолла", ("KR-45",), "Jeonju"),
    _k("KR-46", "KOR", "South Jeolla", "Южная Чолла", ("KR-46", "KR-29"), "Gwangju"),
    _k("KR-47", "KOR", "North Gyeongsang", "Северная Кёнсан", ("KR-47", "KR-27"), "Daegu"),
    _k("KR-48", "KOR", "South Gyeongsang", "Южная Кёнсан", ("KR-48", "KR-31"), "Ulsan"),
    _k("KR-49", "KOR", "Jeju", "Чеджудо", ("KR-49",), "Jeju City"),
    _k("KP-01", "PRK", "Pyongyang", "Пхеньян", ("KP-01",), "Pyongyang"),
    _k("KP-02", "PRK", "South Pyongan", "Южная Пхёнан", ("KP-02",), "Nampo"),
    _k("KP-03", "PRK", "North Pyongan", "Северная Пхёнан", ("KP-03",), "Sinuiju"),
    _k("KP-04", "PRK", "Chagang", "Чагандо", ("KP-04",), "Kanggye"),
    _k("KP-10", "PRK", "Ryanggang", "Рянгандо", ("KP-10",), "Hyesan"),
    _k("KP-08", "PRK", "South Hamgyong", "Южная Хамгён", ("KP-08",), "Hamhung"),
    _k("KP-09", "PRK", "North Hamgyong", "Северная Хамгён", ("KP-09", "KP-13"), "Chongjin"),
    _k("KP-07", "PRK", "Kangwon", "Канвон", ("KP-07",), "Wonsan"),
    _k("KP-05", "PRK", "South Hwanghae", "Южная Хванхэ", ("KP-05",), "Haeju"),
    _k("KP-06", "PRK", "North Hwanghae", "Северная Хванхэ", ("KP-06",), "Sariwon"),
)

ZONES = {
    "pilot": Zone(
        name="pilot",
        units=GERMANY + KOREA,
        windows=((5.0, 46.8, 16.0, 55.5), (124.0, 33.0, 131.5, 43.2)),
        density=2.0,
        city_min_pop=100_000,
        zone_codes=("DEU", "KOR", "PRK"),
        extra_cities=(ExtraCity("West Berlin", "Западный Берлин", 52.507, 13.29, 2_130_000),),
        country_capitals=(("GER", "DE-QNW"), ("DDR", "DE-QQB"), ("KOR", "KR-11"), ("PRK", "KP-01")),
    ),
}
