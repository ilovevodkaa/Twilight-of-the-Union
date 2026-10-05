<div align="center">

# Twilight of the Union

**Сумерки Союза** — мод для Hearts of Iron IV о последних годах Советского Союза

*1 января 1990 года. Стена пала. Партия всё ещё у власти. Надолго ли — решать вам.*

![Главное меню](docs/images/main_menu.jpg)

![HOI4](https://img.shields.io/badge/Hearts_of_Iron_IV-1.19.*-3a3a3a?style=flat-square)
![Статус](https://img.shields.io/badge/статус-ранняя_разработка-a3432f?style=flat-square)
![Версия](https://img.shields.io/badge/версия-0.1-c3b091?style=flat-square)

[О моде](#о-моде) · [Скриншоты](#скриншоты) · [Установка](#установка) · [Разработка](#разработка) · [English](#english)

</div>

---

## О моде

Пять лет перестройки расшатали всё и ничего не исправили. Прибалтика считает дни до независимости, Кавказ горит, полки магазинов пусты, армия возвращается из Афганистана в страну, которую больше не узнаёт. Варшавский договор расползается по швам, а Вашингтон ещё не решил, что делать с победой в холодной войне.

Союз ещё можно реформировать, удержать силой или отпустить. Оставить как есть уже нельзя.

**Что уже есть в версии 0.1:**

| | |
|---|---|
| **Главное меню** | Красная площадь, свой логотип, панель с описанием версии |
| **Экраны загрузки** | Четыре архивных кадра 1989–1993 годов в едином стиле |
| **Цитаты эпохи** | 25 высказываний от Рейгана и Тэтчер до Лигачёва и Черномырдина вместо цитат Второй мировой |
| **Сценарий** | Единственная стартовая дата — 1 января 1990 года |
| **Выбор страны** | США и СССР, восемь стран Восточного блока и Запада, справки на 1990 год |
| **Лидеры** | Михаил Горбачёв и Джордж Буш |
| **Языки** | Русский и английский |

> [!NOTE]
> Карта мира заменена на новую, сгенерированную по реальным географическим данным: 1990 год, ~14 800 сухопутных и ~2 900 морских провинций, ~2 300 штатов, ~3 250 городов с очками победы, 172 страны. Страны пока «заглушки»: тег, цвет, столица и территория, без армий, фокусов, идей и технологий. Ванильных файлов 1936 года мод больше не использует.

## Карта 1990 года

![Политическая карта 1990](docs/images/map_1990.jpg)
<p align="center"><sub>Политическая карта со границами штатов (превью, собирается скриптом)</sub></p>

Границы 1990 года получены из современных данных Natural Earth: СССР (15 республик), Югославия, Чехословакия, ФРГ и ГДР, Северный и Южный Йемен, Эритрея в составе Эфиопии, Южный Судан в составе Судана, Намибия под ЮАР, Западная Сахара в составе Марокко, Гонконг у Великобритании, Макао у Португалии. Теги, где есть ванильный, остались ванильными (`ENG`, `GER`, `JAP`, `PRC`, `CHI`...), для остальных введены новые трёхбуквенные.

## Скриншоты

<table>
<tr>
<td width="50%"><img src="docs/images/scenario.jpg" alt="Выбор сценария"><p align="center"><sub>Выбор сценария</sub></p></td>
<td width="50%"><img src="docs/images/loading_screen.jpg" alt="Экран загрузки"><p align="center"><sub>Экран загрузки с цитатой эпохи</sub></p></td>
</tr>
</table>

![Выбор страны](docs/images/country_select.jpg)
<p align="center"><sub>Выбор страны</sub></p>

![Экраны загрузки](docs/images/loading_screens.jpg)
<p align="center"><sub>Экраны загрузки</sub></p>

<sub>Скриншоты собраны скриптом из текстур мода; в игре используются игровые шрифты и флаги.</sub>

## Установка

1. Скачайте репозиторий: **Code → Download ZIP** или `git clone`.
2. Положите папку в каталог модов:
   ```
   Документы\Paradox Interactive\Hearts of Iron IV\mod\Twilight of the Union
   ```
3. Рядом с папкой, в каталоге `mod`, создайте файл `Twilight of the Union.mod`: скопируйте `descriptor.mod` и добавьте в конец строку с путём к папке мода:
   ```
   path="C:/Users/<ваше_имя>/Documents/Paradox Interactive/Hearts of Iron IV/mod/Twilight of the Union"
   ```
   Если в пути есть кириллица (например, «Документы»), лаунчер может его не прочитать. Тогда укажите короткий путь 8.3, его показывает команда `dir /x`.
4. Включите мод в лаунчере.

Мод несовместим с другими модами, которые меняют главное меню, экраны загрузки или стартовые даты.

## Разработка

### Структура

```
common/            сценарий 1990 года, персонажи, стартовая дата (defines)
gfx/               текстуры интерфейса, экраны загрузки, портреты
history/           страны (заглушки, USA и SOV с прежним содержимым) и штаты (генерируются)
map/               провинции, определения, регионы, здания, рельеф (генерируется)
interface/         GUI главного меню, загрузки, выбора сценария и страны
localisation/      тексты на русском и английском, цитаты эпохи
tools/             скрипты сборки графики, сценария и карты
  src/             исходные фотографии
  map/             модули генератора карты
  cache/           скачанные данные (в git не попадает)
docs/images/       скриншоты для README
```

### Графика собирается скриптами

Все текстуры интерфейса генерируются из исходных фото в `tools/src`: затемнение, плёночный тон, развёртка ЭЛТ, зерно. DDS-файлы руками не правятся.

```bash
pip install pillow
python tools/build_menu_gfx.py     # все текстуры: меню, загрузка, выбор страны, портреты
python tools/build_bookmarks.py    # файл сценария common/bookmarks/totu_1990.txt
python tools/render_docs.py        # скриншоты для README
```

### Карта собирается скриптом

Карта генерируется целиком: `tools/build_map.py` скачивает Natural Earth (границы стран и областей, города, реки, озёра) и тайлы высот Terrarium, строит провинции (диаграммы Вороного с релаксацией Ллойда, плотность по населению, внутри областей admin-1, чтобы провинция не пересекала границу), штаты, города, стратегические регионы, рельеф и все текстовые файлы. Результат детерминирован (фиксированный seed).

```bash
pip install numpy scipy shapely scikit-image opencv-python-headless pillow requests
python tools/build_map.py        # 5-10 минут, данные кэшируются в tools/cache/
python tools/validate_map.py     # проверка целостности без игры
```

Проекция: равнопромежуточная (plate carrée), охват 77° с. ш. - 56° ю. ш., 5632x2048. Изменить страны, названия или правила 1990 года можно в `tools/map/countries.py`, размер и число штатов - в `tools/map/states.py`, плотность провинций - в `tools/map/provinces.py`. Сгенерированные файлы вручную не правятся.

Допущения, которые не удалось проверить без игры: индексы палитры `terrain.bmp`, размер `trees.bmp` (3520x1280), формат `cities.bmp` и позиции в `unitstacks.txt`/`buildings.txt`. Рельеф, леса и пустыни получены из высот и грубых климатических зон, а не из карты биомов.

Чтобы заменить фон, экран загрузки или портрет, положите новое фото в `tools/src` и перезапустите `build_menu_gfx.py`. Списки экранов загрузки (`LOADING_SCREENS`) и портретов (`PORTRAITS`) — в начале соответствующих разделов скрипта.

### Планы

- [x] Главное меню, экраны загрузки, выбор сценария и страны
- [x] Стартовая дата 1 января 1990 года
- [x] Политическая карта 1990 года: союзные республики, Восточный блок, две Германии (карта, штаты, города, страны-заглушки)
- [ ] Лидеры, партии и правительства всех стран на 1990 год
- [ ] Национальные духи и фокусы СССР и США
- [ ] События 1990–1991 годов

## Источники

- Фото танков M1A1 Abrams: [«Abrams in formation»](https://commons.wikimedia.org/wiki/File:Abrams_in_formation.jpg), PHC D. W. Holmes II, ВМС США, 1991 — общественное достояние.
- Остальные фотографии — архивные материалы эпохи.

---

## English

**Twilight of the Union** is a Hearts of Iron IV mod set in the last years of the Soviet Union, starting on 1 January 1990.

Version 0.1 delivers the frontend: a new main menu, period loading screens with quotes from 1983–1993, a single 1990 scenario, a reworked country selection screen with the USA and the USSR, and Gorbachev and Bush as leaders. English and Russian are supported.

The world map is now a new, procedurally generated 1990 map: about 14,800 land and 2,900 sea provinces, about 2,300 states, about 3,250 victory-point cities and 172 country stubs (tag, colour, capital and territory only: no armies, focuses, ideas or technologies yet). Borders are derived from Natural Earth (USSR with its 15 republics, Yugoslavia, Czechoslovakia, West and East Germany, North and South Yemen, and so on); heights come from Terrarium elevation tiles.

![1990 political map](docs/images/map_1990.jpg)

**Install:** put the folder into `Documents/Paradox Interactive/Hearts of Iron IV/mod/`, create `Twilight of the Union.mod` next to it from `descriptor.mod` with a `path="..."` line pointing to the folder, then enable it in the launcher.

**Rebuild graphics:** `pip install pillow`, then `python tools/build_menu_gfx.py`.

**Rebuild the map:** `pip install numpy scipy shapely scikit-image opencv-python-headless pillow requests`, then `python tools/build_map.py` (downloads data into `tools/cache/`, takes 5-10 minutes) and `python tools/validate_map.py`. Projection: plate carree, 77N-56S, 5632x2048. Unverified without the game: `terrain.bmp` palette indices, `trees.bmp` size (3520x1280), `cities.bmp` format, and the position files `unitstacks.txt` / `buildings.txt`.
