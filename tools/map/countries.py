"""1990 political rules: which Natural Earth admin-1 region belongs to which tag, plus names/colors.

Natural Earth is a 2020s dataset, so 1990 is derived by merging/splitting (see owner_tag).
"""
import colorsys
import hashlib

# Natural Earth "SOV_A3" group codes -> real sovereign ISO3 (dependencies follow their sovereign)
GROUP_TO_ISO = {
    "US1": "USA", "GB1": "GBR", "FR1": "FRA", "DN1": "DNK", "NL1": "NLD", "AU1": "AUS",
    "NZ1": "NZL", "CH1": "CHN", "FI1": "FIN", "KA1": "KAZ", "CU1": "CUB", "IS1": "ISR",
}

SOVIET = {"RUS", "UKR", "BLR", "MDA", "LTU", "LVA", "EST", "GEO", "ARM", "AZE", "KAZ", "UZB", "TKM", "KGZ", "TJK"}
YUGO = {"SRB", "KOS", "BIH", "HRV", "SVN", "MNE", "MKD"}
DDR_STATES = {"Brandenburg", "Mecklenburg-Vorpommern", "Sachsen", "Sachsen-Anhalt", "Thüringen", "Berlin"}
SOUTH_YEMEN = {"Hadramawt", "Al Mahrah", "Lahij", "`Adan", "Abyan", "Shabwah", "Al Dali'"}

# ISO3 -> tag. Vanilla HOI4 style where a vanilla tag exists, otherwise the ISO3 itself.
ISO_TAG = {
    "USA": "USA", "GBR": "ENG", "FRA": "FRA", "ITA": "ITA", "JPN": "JAP", "CHN": "PRC", "TWN": "CHI",
    "POL": "POL", "HUN": "HUN", "ROU": "ROM", "BGR": "BUL", "GRC": "GRE", "TUR": "TUR", "ESP": "SPR",
    "PRT": "POR", "SWE": "SWE", "NOR": "NOR", "DNK": "DEN", "FIN": "FIN", "NLD": "HOL", "BEL": "BEL",
    "CHE": "SWI", "AUT": "AUS", "ALB": "ALB", "IRL": "IRE", "ISL": "ICE", "CAN": "CAN", "AUS": "AST",
    "NZL": "NZL", "ZAF": "SAF", "MEX": "MEX", "BRA": "BRA", "ARG": "ARG", "CHL": "CHL", "PER": "PRU",
    "COL": "COL", "VEN": "VEN", "BOL": "BOL", "URY": "URG", "PRY": "PAR", "ECU": "ECU", "CUB": "CUB",
    "DOM": "DOM", "HTI": "HAI", "CRI": "COS", "GTM": "GUA", "HND": "HON", "NIC": "NIC", "PAN": "PAN",
    "SLV": "SAL", "EGY": "EGY", "ETH": "ETH", "LBR": "LIB", "IRQ": "IRQ", "IRN": "PER", "SAU": "SAU",
    "YEM": "YEM", "AFG": "AFG", "MNG": "MON", "THA": "SIA", "IND": "RAJ", "NPL": "NEP", "BTN": "BHU",
    "MYS": "MAL", "IDN": "NEI", "PHL": "PHI", "VNM": "VIN", "KOR": "KOR", "PRK": "PRK", "LUX": "LUX",
    "LBN": "LEB", "SYR": "SYR", "JOR": "TRJ", "ISR": "ISR", "OMN": "OMA", "ARE": "UAE", "QAT": "QAT",
    "KWT": "KUW", "BHR": "BHR", "CYP": "CYP", "LBY": "LBA", "TUN": "TUN", "DZA": "ALG", "MAR": "MOR",
    "SDN": "SUD", "SOM": "SOM", "KEN": "KEN", "TZA": "TZA", "NGA": "NGA", "GHA": "GHA", "SEN": "SEN",
    "MLI": "MLI", "NER": "NIG", "TCD": "CHD", "COD": "ZAI", "COG": "CGO", "AGO": "ANG", "ZMB": "ZAM",
    "ZWE": "ZIM", "MOZ": "MOZ", "MDG": "MAD", "UGA": "UGA", "BGD": "BAN", "LKA": "CEY", "MMR": "BRM",
    "PAK": "PAK", "KHM": "CAM", "LAO": "LAO", "SGP": "SIN", "BRN": "BRU", "PNG": "PNG", "FJI": "FIJ",
    "DEU": "GER", "CZE": "CZE", "SVK": "CZE", "SRB": "YUG", "NAM": "SAF", "ERI": "ETH", "SDS": "SUD",
    "SSD": "SUD", "TLS": "NEI", "SAH": "MOR", "HKG": "ENG", "MAC": "POR", "PSX": "ISR", "CNM": "CYP",
    "BJN": "COL", "SER": "COL", "SCR": "PHI", "PGA": "VIN", "KAS": "RAJ", "BRT": "SUD", "BRI": "BRA",
    "SPI": "CHL", "CYN": "CYP", "SOL": "SOM", "ATA": None,
}
for _i in SOVIET:
    ISO_TAG[_i] = "SOV"
for _i in YUGO:
    ISO_TAG[_i] = "YUG"

# Capital city (Natural Earth NAME) for tags whose capital cannot be read from ADM0CAP
CAPITAL_CITY = {
    "SOV": "Moscow", "GER": "Bonn", "DDR": "Berlin", "YUG": "Belgrade", "CZE": "Prague",
    "YEM": "Sanaa", "YES": "Aden", "ETH": "Addis Ababa", "SUD": "Khartoum", "MOR": "Rabat",
    "SAF": "Pretoria", "USA": "Washington, D.C.", "ENG": "London", "CHI": "Taipei", "PRC": "Beijing",
    "NEI": "Jakarta", "ISR": "Jerusalem", "POR": "Lisbon", "HOL": "Amsterdam", "BOL": "La Paz",
    "SWI": "Bern", "BEL": "Brussels", "FRA": "Paris", "CYP": "Nicosia", "LEB": "Beirut",
}

# tag -> (English, Russian, adjective en, adjective ru). Missing entries fall back to Natural Earth.
NAMES = {
    "USA": ("United States", "Соединённые Штаты Америки", "American", "американский"),
    "SOV": ("Soviet Union", "Советский Союз", "Soviet", "советский"),
    "ENG": ("United Kingdom", "Великобритания", "British", "британский"),
    "FRA": ("France", "Франция", "French", "французский"),
    "GER": ("West Germany", "ФРГ", "West German", "западногерманский"),
    "DDR": ("East Germany", "ГДР", "East German", "восточногерманский"),
    "ITA": ("Italy", "Италия", "Italian", "итальянский"),
    "JAP": ("Japan", "Япония", "Japanese", "японский"),
    "PRC": ("China", "Китай", "Chinese", "китайский"),
    "CHI": ("Taiwan", "Тайвань", "Taiwanese", "тайваньский"),
    "POL": ("Poland", "Польша", "Polish", "польский"),
    "CZE": ("Czechoslovakia", "Чехословакия", "Czechoslovak", "чехословацкий"),
    "HUN": ("Hungary", "Венгрия", "Hungarian", "венгерский"),
    "ROM": ("Romania", "Румыния", "Romanian", "румынский"),
    "BUL": ("Bulgaria", "Болгария", "Bulgarian", "болгарский"),
    "YUG": ("Yugoslavia", "Югославия", "Yugoslav", "югославский"),
    "GRE": ("Greece", "Греция", "Greek", "греческий"),
    "TUR": ("Turkey", "Турция", "Turkish", "турецкий"),
    "SPR": ("Spain", "Испания", "Spanish", "испанский"),
    "POR": ("Portugal", "Португалия", "Portuguese", "португальский"),
    "SWE": ("Sweden", "Швеция", "Swedish", "шведский"),
    "NOR": ("Norway", "Норвегия", "Norwegian", "норвежский"),
    "DEN": ("Denmark", "Дания", "Danish", "датский"),
    "FIN": ("Finland", "Финляндия", "Finnish", "финский"),
    "HOL": ("Netherlands", "Нидерланды", "Dutch", "нидерландский"),
    "BEL": ("Belgium", "Бельгия", "Belgian", "бельгийский"),
    "SWI": ("Switzerland", "Швейцария", "Swiss", "швейцарский"),
    "AUS": ("Austria", "Австрия", "Austrian", "австрийский"),
    "ALB": ("Albania", "Албания", "Albanian", "албанский"),
    "IRE": ("Ireland", "Ирландия", "Irish", "ирландский"),
    "ICE": ("Iceland", "Исландия", "Icelandic", "исландский"),
    "CAN": ("Canada", "Канада", "Canadian", "канадский"),
    "AST": ("Australia", "Австралия", "Australian", "австралийский"),
    "NZL": ("New Zealand", "Новая Зеландия", "New Zealand", "новозеландский"),
    "SAF": ("South Africa", "Южная Африка", "South African", "южноафриканский"),
    "MEX": ("Mexico", "Мексика", "Mexican", "мексиканский"),
    "BRA": ("Brazil", "Бразилия", "Brazilian", "бразильский"),
    "ARG": ("Argentina", "Аргентина", "Argentine", "аргентинский"),
    "CHL": ("Chile", "Чили", "Chilean", "чилийский"),
    "PRU": ("Peru", "Перу", "Peruvian", "перуанский"),
    "COL": ("Colombia", "Колумбия", "Colombian", "колумбийский"),
    "VEN": ("Venezuela", "Венесуэла", "Venezuelan", "венесуэльский"),
    "CUB": ("Cuba", "Куба", "Cuban", "кубинский"),
    "EGY": ("Egypt", "Египет", "Egyptian", "египетский"),
    "ETH": ("Ethiopia", "Эфиопия", "Ethiopian", "эфиопский"),
    "PER": ("Iran", "Иран", "Iranian", "иранский"),
    "IRQ": ("Iraq", "Ирак", "Iraqi", "иракский"),
    "SAU": ("Saudi Arabia", "Саудовская Аравия", "Saudi", "саудовский"),
    "YEM": ("North Yemen", "Северный Йемен", "North Yemeni", "севернойеменский"),
    "YES": ("South Yemen", "Южный Йемен", "South Yemeni", "южнойеменский"),
    "AFG": ("Afghanistan", "Афганистан", "Afghan", "афганский"),
    "RAJ": ("India", "Индия", "Indian", "индийский"),
    "PAK": ("Pakistan", "Пакистан", "Pakistani", "пакистанский"),
    "NEI": ("Indonesia", "Индонезия", "Indonesian", "индонезийский"),
    "SIA": ("Thailand", "Таиланд", "Thai", "тайский"),
    "VIN": ("Vietnam", "Вьетнам", "Vietnamese", "вьетнамский"),
    "PRK": ("North Korea", "КНДР", "North Korean", "севернокорейский"),
    "KOR": ("South Korea", "Республика Корея", "South Korean", "южнокорейский"),
    "MON": ("Mongolia", "Монголия", "Mongolian", "монгольский"),
    "ISR": ("Israel", "Израиль", "Israeli", "израильский"),
    "SYR": ("Syria", "Сирия", "Syrian", "сирийский"),
    "LBA": ("Libya", "Ливия", "Libyan", "ливийский"),
    "ALG": ("Algeria", "Алжир", "Algerian", "алжирский"),
    "MOR": ("Morocco", "Марокко", "Moroccan", "марокканский"),
    "SUD": ("Sudan", "Судан", "Sudanese", "суданский"),
    "NIG": ("Niger", "Нигер", "Nigerien", "нигерский"),
    "NGA": ("Nigeria", "Нигерия", "Nigerian", "нигерийский"),
    "ZAI": ("Zaire", "Заир", "Zairean", "заирский"),
    "TRJ": ("Jordan", "Иордания", "Jordanian", "иорданский"),
    "BRM": ("Burma", "Бирма", "Burmese", "бирманский"),
    "CEY": ("Sri Lanka", "Шри-Ланка", "Sri Lankan", "шри-ланкийский"),
    "MAL": ("Malaysia", "Малайзия", "Malaysian", "малайзийский"),
    "PHI": ("Philippines", "Филиппины", "Philippine", "филиппинский"),
    "BAN": ("Bangladesh", "Бангладеш", "Bangladeshi", "бангладешский"),
    "KUW": ("Kuwait", "Кувейт", "Kuwaiti", "кувейтский"),
    "CHD": ("Chad", "Чад", "Chadian", "чадский"),
    "CGO": ("Congo", "Конго", "Congolese", "конголезский"),
    "ANG": ("Angola", "Ангола", "Angolan", "ангольский"),
    "ZAM": ("Zambia", "Замбия", "Zambian", "замбийский"),
    "ZIM": ("Zimbabwe", "Зимбабве", "Zimbabwean", "зимбабвийский"),
    "TZA": ("Tanzania", "Танзания", "Tanzanian", "танзанийский"),
    "CAM": ("Cambodia", "Кампучия", "Cambodian", "кампучийский"),
    "UAE": ("United Arab Emirates", "ОАЭ", "Emirati", "эмиратский"),
    "OMA": ("Oman", "Оман", "Omani", "оманский"),
    "LEB": ("Lebanon", "Ливан", "Lebanese", "ливанский"),
    "URG": ("Uruguay", "Уругвай", "Uruguayan", "уругвайский"),
    "PAR": ("Paraguay", "Парагвай", "Paraguayan", "парагвайский"),
    "BOL": ("Bolivia", "Боливия", "Bolivian", "боливийский"),
    "ECU": ("Ecuador", "Эквадор", "Ecuadorian", "эквадорский"),
    "GUA": ("Guatemala", "Гватемала", "Guatemalan", "гватемальский"),
    "HAI": ("Haiti", "Гаити", "Haitian", "гаитянский"),
    "DOM": ("Dominican Republic", "Доминиканская Республика", "Dominican", "доминиканский"),
    "HON": ("Honduras", "Гондурас", "Honduran", "гондурасский"),
    "NIC": ("Nicaragua", "Никарагуа", "Nicaraguan", "никарагуанский"),
    "SAL": ("El Salvador", "Сальвадор", "Salvadoran", "сальвадорский"),
    "COS": ("Costa Rica", "Коста-Рика", "Costa Rican", "коста-риканский"),
    "PAN": ("Panama", "Панама", "Panamanian", "панамский"),
    "LIB": ("Liberia", "Либерия", "Liberian", "либерийский"),
    "KEN": ("Kenya", "Кения", "Kenyan", "кенийский"),
    "TUN": ("Tunisia", "Тунис", "Tunisian", "тунисский"),
    "GHA": ("Ghana", "Гана", "Ghanaian", "ганский"),
    "NEP": ("Nepal", "Непал", "Nepali", "непальский"),
    "SIN": ("Singapore", "Сингапур", "Singaporean", "сингапурский"),
    "LUX": ("Luxembourg", "Люксембург", "Luxembourgish", "люксембургский"),
    "CYP": ("Cyprus", "Кипр", "Cypriot", "кипрский"),
}

COLORS = {
    "USA": (60, 90, 170), "SOV": (200, 30, 30), "ENG": (200, 80, 90), "FRA": (60, 110, 200),
    "GER": (110, 110, 110), "DDR": (150, 70, 70), "ITA": (70, 150, 80), "JAP": (240, 200, 210),
    "PRC": (220, 190, 40), "CHI": (90, 160, 210), "POL": (220, 110, 110), "CZE": (110, 90, 170),
    "HUN": (90, 150, 110), "ROM": (210, 170, 60), "BUL": (80, 150, 90), "YUG": (60, 90, 150),
    "CAN": (222, 120, 50), "AST": (60, 120, 170), "RAJ": (210, 150, 60), "BRA": (60, 150, 60),
    "TUR": (190, 120, 70), "PER": (60, 140, 110), "SAU": (100, 160, 80), "EGY": (200, 180, 90),
    "SPR": (200, 160, 40), "SWE": (60, 120, 180), "MEX": (70, 130, 90), "ARG": (130, 190, 230),
}

GFX = {
    "Europe": ("western_european_gfx", "western_european_2d"),
    "Asia": ("asian_gfx", "asian_2d"),
    "Africa": ("african_gfx", "african_2d"),
    "North America": ("southamerican_gfx", "southamerican_2d"),
    "South America": ("southamerican_gfx", "southamerican_2d"),
    "Oceania": ("commonwealth_gfx", "commonwealth_2d"),
}
GFX_OVERRIDE = {"SOV": "eastern_european", "POL": "eastern_european", "CZE": "eastern_european",
                "HUN": "eastern_european", "ROM": "eastern_european", "BUL": "eastern_european",
                "DDR": "eastern_european", "YUG": "eastern_european", "USA": "western_european",
                "CAN": "commonwealth", "AST": "commonwealth", "NZL": "commonwealth", "SAF": "commonwealth",
                "RAJ": "commonwealth", "PER": "middle_eastern", "IRQ": "middle_eastern", "SAU": "middle_eastern",
                "SYR": "middle_eastern", "TRJ": "middle_eastern", "TUR": "middle_eastern",
                "YEM": "middle_eastern", "YES": "middle_eastern", "KUW": "middle_eastern", "OMA": "middle_eastern",
                "UAE": "middle_eastern", "LEB": "middle_eastern", "ISR": "middle_eastern", "EGY": "middle_eastern",
                "LBA": "middle_eastern", "ALG": "middle_eastern", "TUN": "middle_eastern", "MOR": "middle_eastern",
                "AFG": "middle_eastern", "PAK": "middle_eastern", "JAP": "asian"}


def owner_tag(p, group_of_adm0):
    """p = admin-1 properties; group_of_adm0 = {ADM0_A3: SOV_A3} from admin-0. Returns tag or None."""
    iso = p["adm0_a3"]
    if iso == "DEU":
        return "DDR" if p["name"] in DDR_STATES else "GER"
    if iso == "YEM":
        return "YES" if p["name"] in SOUTH_YEMEN else "YEM"
    if iso in ISO_TAG:
        return ISO_TAG[iso]
    grp = group_of_adm0.get(iso, iso)
    grp = GROUP_TO_ISO.get(grp, grp)
    if grp in ISO_TAG:
        return ISO_TAG[grp]
    return grp  # plain ISO3 tag


def tag_color(tag):
    if tag in COLORS:
        return COLORS[tag]
    h = int(hashlib.md5(tag.encode()).hexdigest(), 16)
    hue = (h % 360) / 360.0
    sat = 0.45 + ((h >> 9) % 30) / 100.0
    val = 0.55 + ((h >> 17) % 30) / 100.0
    r, g, b = colorsys.hsv_to_rgb(hue, sat, val)
    return int(r * 255), int(g * 255), int(b * 255)


def ui_color(c):
    return tuple(min(255, int(v * 1.15 + 8)) for v in c)


def gfx_for(tag, continent):
    ov = GFX_OVERRIDE.get(tag)
    if ov:
        return ov + "_gfx", ov + "_2d"
    return GFX.get(continent, GFX["Africa"])
