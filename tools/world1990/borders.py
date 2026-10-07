"""Who owns every vanilla state on 1 January 1990.

The map itself is vanilla HOI4 (provinces, states, terrain, strategic regions); only ownership, cores and a few
province transfers change. Default: the 1936 owner keeps the state, with the tags below remapped. Everything that
moved between 1936 and 1990 is listed explicitly in STATE_OWNER.
"""

# 1936 tags that no longer exist in 1990 -> their 1990 successor (whole tag)
OWNER_REMAP = {
    # Chinese warlords and puppets -> People's Republic
    "CHI": "PRC", "XSM": "PRC", "SIK": "PRC", "GXC": "PRC", "MAN": "PRC", "MEN": "PRC", "SHX": "PRC", "YUN": "PRC",
    "TIB": "PRC",
    # annexed by the USSR
    "LIT": "SOV", "LAT": "SOV", "EST": "SOV", "TAN": "SOV",
    "PAL": "ISR",
    "AFA": "ETH",
}


def _all(owner, *ids):
    return {i: owner for i in ids}


STATE_OWNER = {
    # ---------------------------------------------------------------- Europe
    # USSR: Baltics, eastern Poland, Bessarabia, Northern Bukovina, Carpathian Ruthenia, Karelia, Koenigsberg
    **_all("SOV", 763, 188, 784, 89, 91, 93, 94, 95, 96, 73, 78, 766, 80, 146, 147, 722, 537, 555),
    # Poland west of the Bug, east of the Oder-Neisse line
    **_all("POL", 5, 63, 66, 67, 68, 85),
    # German Democratic Republic
    **_all("DDR", 60, 61, 62, 64, 65),
    77: "BUL",                          # Southern Dobruja (1940)
    **_all("YUG", 736, 852, 163),        # Slovene Littoral, Istria, Zadar
    164: "GRE",                          # Dodecanese (1947)
    116: "MLT", 183: "CYP",
    331: "CAN", 332: "CAN",              # Newfoundland (1949)
    # ---------------------------------------------------------------- Middle East
    454: "ISR",
    **_all("FSA", 659, 992, 906),        # People's Democratic Republic of Yemen
    658: "UAE", 765: "QAT", 1014: "BHR",
    **_all("EGY", 446, 447, 452, 453, 456, 457, 552, 907),
    # ---------------------------------------------------------------- Africa
    269: "SOM", 559: "SOM", 844: "SOM",
    274: "GHA", 542: "BOT", 545: "ZIM", 546: "TZN", 548: "UGA",
    **_all("KEN", 547, 903, 904, 905),
    **_all("SUD", 549, 551, 767, 883, 884, 885, 886, 887),
    **_all("NGA", 558, 900, 901, 902),
    700: "SIE", 701: "GAM", 707: "MRI", 709: "SEY", 770: "MLW", 771: "ZAM", 981: "ZAM",
    268: "DJI", 272: "SEN", 458: "TUN", 665: "TUN",
    **_all("ALG", 459, 460, 513, 514),
    515: "NGR", 781: "NGR",
    539: "GAB", 543: "MAD", 708: "COM",
    **_all("MLI", 556, 782, 898, 899),
    557: "MRT", 786: "MRT", 660: "CAR", 772: "RCG", 773: "CMR", 774: "CHA", 775: "CHA",
    776: "DAH", 777: "TOG", 778: "VOL", 779: "IVO", 780: "GNA",
    **_all("LBA", 273, 448, 449, 450, 451, 661, 662, 663),
    550: "ETH", 908: "ETH",
    461: "MOR", 462: "MOR", 290: "MOR",
    297: "EQG", 699: "MOR", 783: "MOR",  # Spanish Sahara under Moroccan administration
    296: "GNB", 702: "CBV", 705: "STP",
    **_all("ANG", 540, 796, 891, 892),
    **_all("MZB", 544, 896, 897),
    **_all("COG", 295, 538, 718, 888, 889, 890),   # Zaire
    768: "RWA", 769: "BRD",
    # ---------------------------------------------------------------- South Asia
    **_all("PAK", 440, 442, 443, 444, 445, 787, 987, 988, 989, 1012),
    430: "BAN",
    320: "RAJ", 321: "RAJ", 733: "RAJ",
    281: "MLD", 422: "SRL",
    # ---------------------------------------------------------------- East and South-East Asia
    524: "CHI",                          # Republic of China on Taiwan
    609: "PRC", 745: "PRC", 728: "PRC",
    **_all("KOR", 525, 1029, 1030, 1031),
    527: "PRK", 1028: "PRK",
    **_all("VIN", 286, 671, 1017, 1066),
    741: "CAM", 1067: "CAM",
    **_all("LAO", 670, 1068, 1069),
    1021: "SNG", 1065: "MAL", 1023: "BRN",
    721: "INS",                          # East Timor, occupied since 1975
    633: "USA", 684: "USA", 647: "USA", 646: "USA",   # Trust Territory of the Pacific Islands
    # ---------------------------------------------------------------- Oceania
    **_all("PNG", 523, 737, 979, 1070, 1073),
    634: "SOL", 734: "SOL", 636: "FIJ", 1071: "VAN", 726: "SAM",
    639: "KIR", 642: "KIR", 727: "KIR", 643: "TUV", 725: "NRU",
    711: "AST", 712: "AST",              # Christmas and Cocos Islands (1955-58)
    # ---------------------------------------------------------------- Americas
    308: "BAS",                          # Antigua and Barbuda
    692: "BRB",                          # Barbados and the Windward Islands
    311: "BLZ", 687: "GYA", 689: "JAM", 690: "BAH", 693: "BAH", 691: "TRI", 309: "SUR",
    685: "PAN", 688: "PAR",
}

# province -> state it moves to (vanilla state borders that do not match 1990)
# NOTE: moving provinces between vanilla states makes HOI4 abort (0xc0000409, no crash dump) - Luebeck (11305 -> 58)
# and Trieste (6626 -> 160) while loading, Spanish Morocco (4199 7215 10113 12087 -> 461) when a campaign starts.
# Cause unknown, so vanilla state borders are kept: Luebeck stays in the GDR, Trieste in Yugoslavia, and the whole
# Spanish Africa state (Tetouan, Ceuta, Melilla) goes to Morocco.
PROVINCE_MOVES = {}

# states the owner holds without a core
NO_OWNER_CORE = {
    326,                      # Hong Kong
    729,                      # Macau
    541, 893, 894, 895,       # Namibia, South African administration until 21 March 1990
    699, 783,                 # Western Sahara
    721,                      # East Timor
    454,                      # Israel + occupied territories share one vanilla state; core added explicitly
    633, 684, 647,            # Pacific trust territory
}

EXTRA_CORES = {
    454: ["ISR"],
    **{s: ["KOR", "PRK"] for s in (525, 1029, 1030, 1031, 527, 1028)},
    524: ["CHI", "PRC"],
}

EXTRA_CLAIMS = {
    **{s: ["GER"] for s in (60, 61, 62, 64, 65)},          # Basic Law: one German nation
    524: ["PRC"],
    326: ["PRC"], 729: ["PRC"],
    555: ["JAP"],                                          # Northern Territories
    699: ["MOR"], 783: ["MOR"],
    441: ["PAK"], 787: ["RAJ"],
    299: ["ARG"],                                          # Falklands
    118: ["SPR"],                                          # Gibraltar
    183: ["TUR"],
    454: ["JOR", "SYR"],
}
