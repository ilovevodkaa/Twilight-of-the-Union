"""Localisation post-processing, run at the end of build_map.py (or by hand after it): python tools/post_build.py

Fixes what the generator cannot know:
  * country adjectives (ADJ_EN / ADJ_RU) for every tag that the generator left as a copy of the country name
  * state names: shorter administrative suffixes, direction suffixes replaced by the main city, hand-written
    historical region names for countries where the admin-1 data is coarse (STATE_NAMES), de-duplication,
    Russian stress marks removed.
Idempotent; edits localisation/*/totu_map_l_*.yml and localisation/*/replace/totu_countries_l_*.yml in place.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# tag -> (English adjective, Russian adjective)
ADJ = {
    "AND": ("Andorran", "андоррский"), "ATG": ("Antiguan", "антигуанский"), "BDI": ("Burundian", "бурундийский"),
    "BEN": ("Beninese", "бенинский"), "BFA": ("Burkinabe", "буркинийский"), "BHR": ("Bahraini", "бахрейнский"),
    "BHS": ("Bahamian", "багамский"), "BHU": ("Bhutanese", "бутанский"), "BLZ": ("Belizean", "белизский"),
    "BRB": ("Barbadian", "барбадосский"), "BRU": ("Bruneian", "брунейский"), "BWA": ("Botswanan", "ботсванский"),
    "CAF": ("Central African", "центральноафриканский"), "CAM": ("Cambodian", "камбоджийский"),
    "CIV": ("Ivorian", "ивуарийский"), "CMR": ("Cameroonian", "камерунский"), "COM": ("Comorian", "коморский"),
    "CPV": ("Cape Verdean", "кабо-вердианский"), "DJI": ("Djiboutian", "джибутийский"), "DMA": ("Dominican", "доминикский"),
    "DOM": ("Dominican", "доминиканский"), "FIJ": ("Fijian", "фиджийский"), "FSM": ("Micronesian", "микронезийский"),
    "GAB": ("Gabonese", "габонский"), "GIN": ("Guinean", "гвинейский"), "GMB": ("Gambian", "гамбийский"),
    "GNB": ("Bissau-Guinean", "гвинейско-бисауский"), "GNQ": ("Equatorial Guinean", "экваториальногвинейский"),
    "GRD": ("Grenadian", "гренадский"), "GUY": ("Guyanese", "гайанский"), "JAM": ("Jamaican", "ямайский"),
    "KIR": ("I-Kiribati", "кирибатийский"), "KNA": ("Kittitian", "сент-китсский"), "LAO": ("Laotian", "лаосский"),
    "LCA": ("Saint Lucian", "сент-люсийский"), "LIE": ("Liechtensteiner", "лихтенштейнский"), "LSO": ("Basotho", "лесотский"),
    "MAD": ("Malagasy", "мадагаскарский"), "MCO": ("Monegasque", "монакский"), "MDV": ("Maldivian", "мальдивский"),
    "MHL": ("Marshallese", "маршалловский"), "MLI": ("Malian", "малийский"), "MLT": ("Maltese", "мальтийский"),
    "MOZ": ("Mozambican", "мозамбикский"), "MRT": ("Mauritanian", "мавританский"), "MUS": ("Mauritian", "маврикийский"),
    "MWI": ("Malawian", "малавийский"), "NRU": ("Nauruan", "науруанский"), "NZL": ("New Zealand", "новозеландский"),
    "PLW": ("Palauan", "палауский"), "PNG": ("Papua New Guinean", "папуасский"), "QAT": ("Qatari", "катарский"),
    "RWA": ("Rwandan", "руандийский"), "SEN": ("Senegalese", "сенегальский"), "SLB": ("Solomon Islands", "соломоновский"),
    "SLE": ("Sierra Leonean", "сьерра-леонский"), "SMR": ("Sammarinese", "сан-маринский"), "SOM": ("Somali", "сомалийский"),
    "STP": ("São Toméan", "сан-томийский"), "SUR": ("Surinamese", "суринамский"), "SWZ": ("Swazi", "эсватинский"),
    "SYC": ("Seychellois", "сейшельский"), "TGO": ("Togolese", "тоголезский"), "TON": ("Tongan", "тонганский"),
    "TTO": ("Trinidadian", "тринидадско-тобагский"), "TUV": ("Tuvaluan", "тувалуанский"), "UGA": ("Ugandan", "угандийский"),
    "VCT": ("Vincentian", "сент-винсентский"), "VUT": ("Ni-Vanuatu", "вануатский"), "WSM": ("Samoan", "самоанский"),
    "SOV": ("Soviet", "советский"), "GER": ("West German", "западногерманский"), "DDR": ("East German", "восточногерманский"),
}
NAME_RU = {"CAM": "Камбоджа"}   # 1990: State of Cambodia (the name Kampuchea was dropped in 1989)
NAME_EN = {}

# state id -> (English, Russian): historical regions where the generator's admin-1 data is coarse or misleading
STATE_NAMES = {
    # Yugoslavia (9 states; admin-1 data labels most of it "Banja Luka" / "Zlatibor")
    2279: ("Slovenia and Zagreb", "Словения и Загреб"), 2280: ("Slavonia and Bosanska Krajina", "Славония и Боснийская Краина"),
    2281: ("Vojvodina", "Воеводина"), 2282: ("Dalmatia and Western Bosnia", "Далмация и Западная Босния"),
    2283: ("Herzegovina and Montenegro", "Герцеговина и Черногория"), 2284: ("Bosnia", "Босния"),
    2285: ("Raška and Western Kosovo", "Рашка и Западное Косово"), 2286: ("Belgrade", "Белград"),
    2287: ("Macedonia and Eastern Kosovo", "Македония и Восточное Косово"),
    # Bulgaria
    334: ("Vratsa", "Враца"), 335: ("Plovdiv", "Пловдив"), 336: ("Stara Zagora", "Стара-Загора"), 337: ("Varna", "Варна"),
    # Hungary
    757: ("Western Transdanubia", "Западное Задунавье"), 758: ("Southern Transdanubia", "Южное Задунавье"),
    759: ("Great Plain", "Альфёльд"),
    # Romania
    1505: ("Oltenia", "Олтения"), 1506: ("Târgu Mureș", "Тыргу-Муреш"), 1507: ("Muntenia", "Мунтения"), 1508: ("Brașov", "Брашов"),
    # Italy
    787: ("Genoa", "Генуя"), 788: ("Verona", "Верона"), 789: ("Ferrara", "Феррара"), 790: ("Venice", "Венеция"),
    792: ("Rome", "Рим"), 793: ("Sardinia", "Сардиния"), 794: ("Campania North", "Северная Кампания"), 796: ("Apulia", "Апулия"),
    797: ("Sicily", "Сицилия"), 798: ("Calabria", "Калабрия"),
    # Czechoslovakia
    544: ("Plzeň", "Пльзень"),
}

SUBST_EN = [(" Autonomous Okrug", ""), ("Autonomous Republic of Crimea", "Crimea"), (" Prefecture", ""),
            (" Voivodeship", ""), ("Pyrenees-Atlantics", "Pyrénées-Atlantiques"), (" Canton", "")]
SUBST_RU = [(" автономный округ", ""), ("Чукотский", "Чукотка"), ("Автономная Республика Крым", "Крым"),
            (" автономная область", ""), (" воеводство", "")]
DIR_SUFFIX = re.compile(r"^(.*?) \(((?:North|South)(?:-(?:East|West))?|East|West)(?: \d+)?\)$")
DIR_SUFFIX_RU = re.compile(r"^(.*?) \((север|юг|восток|запад|северо-восток|северо-запад|юго-восток|юго-запад)(?: \d+)?\)$")


def read_loc(p):
    txt = Path(p).read_text(encoding="utf-8-sig")
    head = txt.split("\n", 1)[0]
    rows = re.findall(r'^\s([A-Za-z0-9_]+):0 "(.*)"\s*$', txt, re.M)
    return head, rows


def write_loc(p, head, rows):
    Path(p).write_text("﻿" + head + "\n" + "\n".join(f' {k}:0 "{v}"' for k, v in rows) + "\n", encoding="utf-8")


def state_info():
    own, vps = {}, {}
    for f in (ROOT / "history/states").glob("*.txt"):
        t = f.read_text(encoding="utf-8-sig")
        sid = int(re.search(r"\bid\s*=\s*(\d+)", t).group(1))
        vps[sid] = sorted(((int(b), int(a)) for a, b in re.findall(r"victory_points\s*=\s*\{\s*(\d+)\s+(\d+)", t)), reverse=True)
    return vps


def fix_states(lang, vps):
    p = ROOT / f"localisation/{lang}/totu_map_l_{lang}.yml"
    head, rows = read_loc(p)
    d = dict(rows)
    ru = lang == "russian"
    out = {}
    for k, v in rows:
        m = re.fullmatch(r"STATE_(\d+)", k)
        if not m:
            continue
        sid = int(m.group(1))
        v = v.replace("́", "")
        for a, b in (SUBST_RU if ru else SUBST_EN):
            v = v.replace(a, b)
        if sid in STATE_NAMES:
            v = STATE_NAMES[sid][1 if ru else 0]
        else:
            mm = (DIR_SUFFIX_RU if ru else DIR_SUFFIX).match(v)
            if mm and vps.get(sid):
                city = d.get(f"VICTORY_POINTS_{vps[sid][0][1]}", "")
                region = mm.group(1)
                v = city if (city and city.lower() in region.lower()) or not city else f"{city} ({region})"
        out[k] = v.replace("́", "")
    # de-duplicate: second and later holders of a name get the main city, then a number
    seen = {}
    for k in sorted(out, key=lambda x: int(x.split("_")[1])):
        v = out[k]
        if v in seen:
            sid = int(k.split("_")[1])
            city = d.get(f"VICTORY_POINTS_{vps[sid][0][1]}", "") if vps.get(sid) else ""
            nv = f"{v} ({city})" if city and city not in v else v
            n = 2
            while nv in seen:
                nv = f"{v} {n}"
                n += 1
            out[k] = nv
            v = nv
        seen[v] = k
    rows = [(k, out.get(k, v)) for k, v in rows]
    write_loc(p, head, rows)
    return out


def fix_countries(lang):
    p = ROOT / f"localisation/{lang}/replace/totu_countries_l_{lang}.yml"
    head, rows = read_loc(p)
    res = []
    for k, v in rows:
        tag = k.split("_")[0]
        if k.endswith("_ADJ") and tag in ADJ:
            v = ADJ[tag][1 if lang == "russian" else 0]
        if lang == "russian" and tag in NAME_RU and k in (tag, tag + "_DEF"):
            v = NAME_RU[tag]
        if lang == "english" and tag in NAME_EN and k in (tag, tag + "_DEF"):
            v = NAME_EN[tag]
        res.append((k, v))
    write_loc(p, head, res)


def main():
    vps = state_info()
    for lang in ("english", "russian"):
        fix_states(lang, vps)
        fix_countries(lang)
    print("localisation fixes applied")


if __name__ == "__main__":
    main()
