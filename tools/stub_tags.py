"""Stub tags: countries that do not exist on 1 January 1990 (successors of the SSRs, Yugoslav republics,
Czechoslovak halves, Western Sahara). They own no state at the start, only appear as cores in history/states, and can be
created by script later. Used by tools/build_cores_claims.py, build_country_colors.py and build_flags.py.

tag: (English, Russian, adjective, russian adjective, flag-icons code, colour RGB, graphical culture)
"""
STUBS = {
    "RUS": ("Russia", "Россия", "Russian", "российский", "ru", (206, 104, 92), "eastern_european"),
    "UKR": ("Ukraine", "Украина", "Ukrainian", "украинский", "ua", (226, 196, 76), "eastern_european"),
    "BLR": ("Belarus", "Беларусь", "Belarusian", "белорусский", "by", (166, 200, 136), "eastern_european"),
    "MOL": ("Moldova", "Молдавия", "Moldovan", "молдавский", "md", (200, 122, 152), "eastern_european"),
    "EST": ("Estonia", "Эстония", "Estonian", "эстонский", "ee", (112, 150, 204), "western_european"),
    "LAT": ("Latvia", "Латвия", "Latvian", "латвийский", "lv", (170, 72, 94), "western_european"),
    "LIT": ("Lithuania", "Литва", "Lithuanian", "литовский", "lt", (90, 152, 102), "western_european"),
    "GEO": ("Georgia", "Грузия", "Georgian", "грузинский", "ge", (190, 62, 72), "eastern_european"),
    "ARM": ("Armenia", "Армения", "Armenian", "армянский", "am", (232, 142, 62), "eastern_european"),
    "AZR": ("Azerbaijan", "Азербайджан", "Azerbaijani", "азербайджанский", "az", (62, 162, 172), "middle_eastern"),
    "KAZ": ("Kazakhstan", "Казахстан", "Kazakh", "казахстанский", "kz", (92, 182, 212), "middle_eastern"),
    "UZB": ("Uzbekistan", "Узбекистан", "Uzbek", "узбекский", "uz", (82, 132, 202), "middle_eastern"),
    "TMS": ("Turkmenistan", "Туркмения", "Turkmen", "туркменский", "tm", (62, 142, 92), "middle_eastern"),
    "KYR": ("Kyrgyzstan", "Киргизия", "Kyrgyz", "киргизский", "kg", (212, 92, 82), "middle_eastern"),
    "TAJ": ("Tajikistan", "Таджикистан", "Tajik", "таджикский", "tj", (152, 112, 172), "middle_eastern"),
    "SLV": ("Slovenia", "Словения", "Slovenian", "словенский", "si", (82, 172, 172), "western_european"),
    "CRO": ("Croatia", "Хорватия", "Croatian", "хорватский", "hr", (202, 92, 122), "western_european"),
    "BOS": ("Bosnia and Herzegovina", "Босния и Герцеговина", "Bosnian", "боснийский", "ba", (112, 132, 192), "eastern_european"),
    "SER": ("Serbia", "Сербия", "Serbian", "сербский", "rs", (152, 92, 132), "eastern_european"),
    "MNT": ("Montenegro", "Черногория", "Montenegrin", "черногорский", "me", (112, 112, 92), "eastern_european"),
    "MAC": ("North Macedonia", "Северная Македония", "Macedonian", "македонский", "mk", (212, 152, 92), "eastern_european"),
    "SLO": ("Slovakia", "Словакия", "Slovak", "словацкий", "sk", (132, 162, 212), "eastern_european"),
    "CZR": ("Czechia", "Чехия", "Czech", "чешский", "cz", (172, 122, 182), "eastern_european"),
    "SAH": ("Western Sahara", "Западная Сахара", "Sahrawi", "западносахарский", "eh", (192, 176, 112), "middle_eastern"),
}
