"""1990 names for vanilla states and victory points whose 1936 names are wrong (renamed cities, new borders)."""

# state id: (English, Russian)
STATE_NAMES = {
    # USSR
    217: ("Volgograd", "Волгоград"), 227: ("Donetsk", "Донецк"), 199: ("Khmelnitsky", "Хмельницкий"),
    742: ("Dushanbe", "Душанбе"), 590: ("Tselinograd", "Целиноград"), 763: ("Kaliningrad", "Калининград"),
    188: ("Klaipėda", "Клайпеда"), 784: ("Vilnius", "Вильнюс"), 89: ("Ivano-Frankovsk", "Ивано-Франковск"),
    91: ("Lvov", "Львов"), 93: ("Volhynia", "Волынь"), 94: ("Brest", "Брест"), 95: ("Grodno", "Гродно"),
    96: ("Molodechno", "Молодечно"), 73: ("Transcarpathia", "Закарпатье"), 78: ("Moldavia", "Молдавия"),
    766: ("Izmail", "Измаил"), 80: ("Chernovtsy", "Черновцы"), 146: ("Vyborg", "Выборг"),
    722: ("Pechenga", "Печенга"), 329: ("Tuva", "Тува"), 654: ("Gorno-Altai", "Горный Алтай"),
    834: ("Transnistria", "Приднестровье"), 537: ("South Sakhalin", "Южный Сахалин"),
    # Poland, Czechoslovakia, Yugoslavia
    5: ("Warmia-Masuria", "Вармия и Мазуры"), 63: ("West Pomerania", "Западное Поморье"),
    68: ("Lubusz", "Любушская земля"), 85: ("Gdańsk", "Гданьск"), 66: ("Lower Silesia", "Нижняя Силезия"),
    67: ("Opole Silesia", "Опольская Силезия"),
    69: ("North Bohemia", "Северная Богемия"), 972: ("South Bohemia", "Южная Богемия"),
    74: ("Czech Silesia", "Чешская Силезия"), 72: ("Těšín", "Тешин"),
    736: ("Slovene Littoral", "Словенское Приморье"),
    # Africa
    295: ("Kinshasa", "Киншаса"), 538: ("Équateur", "Экваториальная"), 718: ("Kisangani", "Кисангани"),
    888: ("Kasai", "Касаи"), 889: ("Shaba", "Шаба"), 890: ("Kivu", "Киву"), 544: ("Maputo", "Мапуту"),
    545: ("Mashonaland", "Машоналенд"), 542: ("Botswana", "Ботсвана"), 268: ("Djibouti", "Джибути"),
    776: ("Benin", "Бенин"), 778: ("Burkina Faso", "Буркина-Фасо"), 660: ("Bangui", "Банги"),
    772: ("Congo", "Конго"), 290: ("Tétouan", "Тетуан"), 699: ("Western Sahara", "Западная Сахара"),
    559: ("Southern Somalia", "Южное Сомали"), 269: ("Somaliland", "Сомалиленд"), 274: ("Ghana", "Гана"),
    # Asia and the Americas
    608: ("Beijing", "Пекин"), 328: ("Jilin", "Цзилинь"), 714: ("Heilongjiang", "Хэйлунцзян"),
    728: ("Zhanjiang", "Чжаньцзян"), 1058: ("Jakarta", "Джакарта"), 669: ("Irian Jaya", "Ириан-Джая"),
    1057: ("South Irian", "Южный Ириан"), 1054: ("West Timor", "Западный Тимор"), 422: ("Sri Lanka", "Шри-Ланка"),
    320: ("Pondicherry", "Пондичерри"), 687: ("Guyana", "Гайана"), 311: ("Belize", "Белиз"),
    643: ("Tuvalu", "Тувалу"), 639: ("Kiribati", "Кирибати"),
}

# victory point province id: (English, Russian)
VP_NAMES = {
    362: ("Gdańsk", "Гданьск"), 422: ("Kovel", "Ковель"), 513: ("Kovel", "Ковель"), 552: ("Legnica", "Легница"),
    560: ("Pinsk", "Пинск"), 577: ("Chernovtsy", "Черновцы"), 988: ("Mbandaka", "Мбандака"),
    1384: ("Dushanbe", "Душанбе"), 1950: ("Kisangani", "Кисангани"), 3288: ("Klaipėda", "Клайпеда"),
    3320: ("Vilnius", "Вильнюс"), 3392: ("Brest", "Брест"), 3457: ("Khmelnitsky", "Хмельницкий"),
    3473: ("Kostrzyn", "Костшин"), 3483: ("Ternopol", "Тернополь"), 3529: ("Volgograd", "Волгоград"),
    3545: ("Wałbrzych", "Валбжих"), 3707: ("Kishinev", "Кишинёв"), 4333: ("Tselinograd", "Целиноград"),
    4401: ("Ho Chi Minh City", "Хошимин"), 4515: ("Likasi", "Ликаси"), 4572: ("Changchun", "Чанчунь"),
    4941: ("Kalemie", "Калемие"), 5117: ("Kinshasa", "Киншаса"), 6282: ("Szczecin", "Щецин"),
    6332: ("Kaliningrad", "Калининград"), 6375: ("Olsztyn", "Ольштын"), 6474: ("Donetsk", "Донецк"),
    6557: ("Rovno", "Ровно"), 6727: ("Belgorod-Dnestrovsky", "Белгород-Днестровский"),
    7381: ("Jakarta", "Джакарта"), 8245: ("Maputo", "Мапуту"), 9140: ("Pechenga", "Печенга"),
    9206: ("Vyborg", "Выборг"), 9304: ("Baranovichi", "Барановичи"), 9511: ("Opole", "Ополе"),
    9570: ("Wrocław", "Вроцлав"), 9843: ("Beijing", "Пекин"), 10309: ("Da Nang", "Дананг"),
    10929: ("Harare", "Хараре"), 10966: ("Huambo", "Уамбо"), 11343: ("Słupsk", "Слупск"),
    11372: ("Koszalin", "Кошалин"), 11386: ("Ełk", "Элк"), 11467: ("Gliwice", "Гливице"),
    11479: ("Lvov", "Львов"), 11771: ("Shenyang", "Шэньян"), 12446: ("Yuzhno-Sakhalinsk", "Южно-Сахалинск"),
}
