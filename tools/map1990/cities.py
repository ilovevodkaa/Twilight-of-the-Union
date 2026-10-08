"""Cities of a rebuild zone: GeoNames cities over the population threshold, 1990 names, victory point values."""
import re
import unicodedata
from dataclasses import dataclass

import numpy as np

from .common import GEO
from .geodata import read_geonames

RENAMES_1990 = {    # (country code, GeoNames name) -> (English, Russian) on 1 January 1990
    ("DE", "Chemnitz"): ("Karl-Marx-Stadt", "Карл-Маркс-Штадт"),
}
RU_OVERRIDE = {     # (country code, GeoNames name) -> Russian, where the alternate names mislead the scoring
    ("DE", "Duisburg"): "Дуйсбург", ("DE", "Stuttgart"): "Штутгарт", ("DE", "Karlsruhe"): "Карлсруэ",
    ("DE", "Heilbronn"): "Хайльбронн", ("DE", "Frankfurt (Oder)"): "Франкфурт-на-Одере",
    ("KR", "Seoul"): "Сеул", ("KR", "Gwangju"): "Кванджу", ("KR", "Cheongju-si"): "Чхонджу",
    ("KR", "Uijeongbu-si"): "Ыйджонбу", ("KR", "Pyeongtaek"): "Пхёнтхэк", ("KR", "Icheon-si"): "Ичхон",
    ("KR", "Jeongeup"): "Чонып", ("KR", "Geoje"): "Кодже", ("KR", "Gijang"): "Киджан", ("KR", "Sejong"): "Седжон",
    ("KR", "Osan"): "Осан", ("KR", "Donghae City"): "Тонхэ", ("KR", "Mokpo"): "Мокпхо",
    ("KR", "Hwaseong-si"): "Хвасон", ("KR", "Goyang-si"): "Коян",
    ("KP", "P’yŏngsŏng"): "Пхёнсон", ("KP", "Chaeryŏng-ni"): "Чэрён", ("KP", "Kangsŏn"): "Кансон",
    ("KP", "Kanggye"): "Кангье", ("KP", "Changam-ch’on"): "Чанамчхон", ("KP", "Paech’ŏn-ŭp"): "Пэчхон",
    ("KP", "Ch’ŏngdan-ŭp"): "Чхондан", ("KP", "Sinch’ŏn-ŭp"): "Синчхон", ("KP", "Kangnyŏng"): "Каннён",
    ("KP", "Paek'ak"): "Пэгак",
}
KOREAN_SUFFIX = re.compile(r"(-si|-ni|-up|-ch'on| City)$")
NOT_RUSSIAN = set("іїєґўјљњћђџѓќѕөүәқңғһұ")
CYRILLIC = re.compile(r"^[Ѐ-ӿ][Ѐ-ӿ \-]*$")
KONTSEVICH_INITIAL = {"b": "п", "g": "к", "d": "т", "j": "ч", "p": "п", "k": "к", "t": "т", "ch": "ч"}
MIN_SEED_DIST = 3.0


@dataclass
class ZoneCity:
    name_en: str
    name_ru: str
    pop: int
    vp: int
    unit: int
    row: int
    col: int


def vp_value(pop):
    return 10 if pop > 3_000_000 else 5 if pop > 1_000_000 else 3 if pop > 500_000 else 2 if pop > 250_000 else 1


TRANSLIT = [("tsch", "ч"), ("sch", "ш"), ("ch", "х"), ("ck", "к"), ("ei", "ай"), ("eu", "ой"), ("äu", "ой"),
            ("ie", "и"), ("ss", "сс"), ("ph", "ф"), ("qu", "кв"), ("th", "т"), ("tz", "ц"), ("st", "шт"), ("sp", "шп"),
            ("ä", "е"), ("ö", "ё"), ("ü", "ю"), ("ß", "сс"), ("a", "а"), ("b", "б"), ("c", "к"), ("d", "д"),
            ("e", "е"), ("f", "ф"), ("g", "г"), ("h", "х"), ("i", "и"), ("j", "й"), ("k", "к"), ("l", "ль"),
            ("m", "м"), ("n", "н"), ("o", "о"), ("p", "п"), ("r", "р"), ("s", "з"), ("t", "т"), ("u", "у"),
            ("v", "ф"), ("w", "в"), ("x", "кс"), ("y", "и"), ("z", "ц")]
VOWELS = "aeiouäöü"


def transliterate(name):
    """Rough German-style Latin -> Russian, only for names GeoNames has no Russian spelling for."""
    out, s, i = [], name.lower(), 0
    while i < len(s):
        for lat, cyr in TRANSLIT:
            if not s.startswith(lat, i):
                continue
            if lat in ("st", "sp") and i > 0 and s[i - 1].isalpha():
                continue
            if lat == "l" and i + 1 < len(s) and s[i + 1] in VOWELS:
                cyr = "л"                                   # soft before a consonant and at the end: Киль
            if lat == "s" and (i + 1 >= len(s) or s[i + 1] not in VOWELS):
                cyr = "с"
            if lat == "e" and (i == 0 or not s[i - 1].isalpha()):
                cyr = "э"                                   # initial E: Эссен, Эрфурт
            out.append(cyr)
            i += len(lat)
            break
        else:
            out.append(s[i])
            i += 1
    return "-".join(w[:1].upper() + w[1:] for w in "".join(out).split("-"))


CONSONANTS = set("бвгджзйклмнпрстфхцчшщ")


def _bigram_similarity(a, b):
    ga = {a[i:i + 2] for i in range(len(a) - 1)}
    gb = {b[i:i + 2] for i in range(len(b) - 1)}
    return len(ga & gb) / max(1, len(ga | gb))


def _russian_score(cand, city):
    """GeoNames lists Russian next to Bulgarian, Belarusian (Taraškievica) and Macedonian spellings. The Russian
    one keeps German double consonants and umlauts (Дюссельдорф, Мюнхен), writes е not э inside a German word
    (Дрезден) and o not a (Росток, Belarusian akanye), and follows the Kontsevich system for Korean (Пусан, Инчхон)."""
    a, lat = cand.lower(), re.sub(r"[’'ʼ]", "", city.name.lower())
    latin = " ".join(x.lower() for x in [city.name] + city.alt if x and not CYRILLIC.match(x))   # München, Nürnberg
    s = 3 * _bigram_similarity(transliterate(lat).lower(), a)
    s += sum(1 for k, ch in enumerate(a) if ch == "ь" and (k + 1 >= len(a) or a[k + 1] != "о"))
    s -= 3 * a.count("ъ") + 3 * a.count("цы")              # Bulgarian / Belarusian
    if city.cc == "DE":
        s -= 3 * a[1:].count("э")
        s += 2 * ("ü" in latin and "ю" in a) + ("ö" in latin and "ё" in a) + 2 * ("ei" in lat and "ей" in a)
        s += sum(1 for k in range(len(a) - 1) if a[k] == a[k + 1] and a[k] in CONSONANTS)
        s += ("am main" in lat and "-на-" in a) + (lat.startswith("h") and a.startswith("г"))
    if city.cc in ("KR", "KP"):
        ini = KONTSEVICH_INITIAL.get(lat[:2]) or KONTSEVICH_INITIAL.get(lat[:1])
        s += 2 * bool(ini and a.startswith(ini)) + a.count("э")
        s += sum(a.count(x) for x in ("чх", "пх", "кх", "тх"))
    return s


def russian_name(city):
    if (city.cc, city.name) in RU_OVERRIDE:
        return RU_OVERRIDE[(city.cc, city.name)]
    cands = [a for a in city.alt if CYRILLIC.match(a) and not (set(a.lower()) & NOT_RUSSIAN)]
    if cands:
        return max(cands, key=lambda a: (_russian_score(a, city), -cands.index(a)))
    return transliterate(city.name)


def english_name(name, cc):
    """Korean names the vanilla way: no breves, no apostrophes, no -si / -ni / -ŭp suffix (Sariwŏn-si -> Sariwon)."""
    if cc not in ("KR", "KP"):
        return name
    s = "".join(c for c in unicodedata.normalize("NFKD", name) if not unicodedata.combining(c))
    s = KOREAN_SUFFIX.sub("", s.replace("’", "'"))
    return s.replace("'", "")


def norm(name):
    """Name compared without diacritics, apostrophes and the Korean -si / -ni / -ŭp / City suffixes."""
    s = "".join(c for c in unicodedata.normalize("NFKD", name) if not unicodedata.combining(c)).lower()
    s = re.sub(r"[’'ʼ`]", "", s)
    s = re.sub(r"[-\s](si|ni|up|city)$", "", s)
    return re.sub(r"[^a-z]", "", s)


def _in_ring(x, y, r):
    xi, yi, xj, yj = r[:-1, 0], r[:-1, 1], r[1:, 0], r[1:, 1]
    cross = ((yi > y) != (yj > y)) & (x < (xj - xi) * (y - yi) / np.where(yj == yi, 1e-300, yj - yi) + xi)
    return bool(cross.sum() % 2)


def inside(lon, lat, polys):
    """Point in any outer ring of the polygons (ray casting)."""
    for poly in polys:
        r = poly[0]
        if r[:, 0].min() <= lon <= r[:, 0].max() and r[:, 1].min() <= lat <= r[:, 1].max() and _in_ring(lon, lat, r):
            return True
    return False


def select(zone, labels, georef, land):
    """Cities of the zone: over the threshold, plus every unit's capital whatever its size, plus the zone's extra
    cities. A city belongs to the unit whose real polygon holds it (smallest units first: West Berlin before the
    Bezirk around it), is snapped to that unit's nearest land pixel, and is dropped only if a bigger city of the same
    unit is within MIN_SEED_DIST px. Unit capitals come first."""
    cc_of = {"GER": "DE", "DDR": "DE", "KOR": "KR", "PRK": "KP"}
    ccs = {cc_of[u.tag] for u in zone.units if u.tag in cc_of}
    gn = [c for c in read_geonames(GEO / "cities15000.zip") if c.cc in ccs and c.fcode != "PPLX"]
    area = {i: int((labels.unit == i).sum()) for i in range(len(zone.units))}
    order = sorted(area, key=area.get)

    def unit_of(lon, lat):
        return next((i for i in order if inside(lon, lat, labels.unit_polys.get(i, []))), None)

    caps = {norm(u.capital) for u in zone.units}
    rows = []                                   # (is_capital, pop, lat, lon, en, ru)
    for c in gn:
        is_cap = norm(c.name) in caps
        if c.pop >= zone.city_min_pop or is_cap:
            en, ru = RENAMES_1990.get((c.cc, c.name), (english_name(c.name, c.cc), russian_name(c)))
            rows.append([is_cap, c.pop, c.lat, c.lon, en, ru])
    rows += [[norm(e.name_en) in caps, e.pop, e.lat, e.lon, e.name_en, e.name_ru] for e in zone.extra_cities]
    x, row = georef.to_px([r[3] for r in rows], [r[2] for r in rows])
    if labels.affine:                           # the coast refinement of the window the city is in
        x, row = _refine(labels, x, row)
    for r, cx, cr in zip(rows, x, row):
        ui = unit_of(r[3], r[2])
        if ui is None:                          # on a border river just outside the simplified polygon
            rr, cc = _snap(labels.unit >= 0, land, int(round(cr)), int(round(cx)), radius=3)
            ui = None if rr is None else int(labels.unit[rr, cc])
        r += [ui, cx, cr]
    rows = [r for r in rows if r[6] is not None]
    # a capital name matching in another unit or a small namesake elsewhere is no capital
    cap_of_unit = {i: norm(u.capital) for i, u in enumerate(zone.units)}
    for r in rows:
        r[0] = r[0] and cap_of_unit[r[6]] == norm(r[4])
    rows.sort(key=lambda r: (not r[0], -r[1]))
    out = []
    for is_cap, pop, lat, lon, en, ru, ui, cx, cr in rows:
        r, c = _snap(labels.unit == ui, land, int(round(cr)), int(round(cx)))
        if r is None:
            continue
        if any(o.unit == ui and np.hypot(o.row - r, o.col - c) < MIN_SEED_DIST for o in out):
            continue
        out.append(ZoneCity(en, ru, pop, vp_value(pop), ui, r, c))
    return out


def _refine(labels, x, row):
    x, row = x.copy(), row.copy()
    for (x0, y0, x1, y1), a in zip(labels.boxes, labels.affine):
        m = (x >= x0) & (x < x1) & (row >= y0) & (row < y1)
        p = np.c_[x[m] - x0, row[m] - y0, np.ones(m.sum())] @ a.T
        x[m], row[m] = p[:, 0] + x0, p[:, 1] + y0
    return x, row


def _snap(in_unit, land, r, c, radius=8):
    """The pixel itself if it is land of the unit, else the nearest land pixel of the unit within the radius."""
    best = None
    for dr in range(-radius, radius + 1):
        for dc in range(-radius, radius + 1):
            rr, cc = r + dr, c + dc
            if 0 <= rr < in_unit.shape[0] and 0 <= cc < in_unit.shape[1] and land[rr, cc] and in_unit[rr, cc]:
                d = dr * dr + dc * dc
                if best is None or d < best[0]:
                    best = (d, rr, cc)
    return (best[1], best[2]) if best else (None, None)
