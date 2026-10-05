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
> Мир на карте пока ванильный, 1936 года: границы, правители и армии ещё не переписаны под 1990 год. Сейчас готов интерфейс и стартовый сценарий, политическая карта — следующий этап.

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
history/           история стран (пока ванильная + лидеры 1990 года)
interface/         GUI главного меню, загрузки, выбора сценария и страны
localisation/      тексты на русском и английском, цитаты эпохи
tools/             скрипты сборки графики и сценария
  src/             исходные фотографии
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

Чтобы заменить фон, экран загрузки или портрет, положите новое фото в `tools/src` и перезапустите `build_menu_gfx.py`. Списки экранов загрузки (`LOADING_SCREENS`) и портретов (`PORTRAITS`) — в начале соответствующих разделов скрипта.

### Планы

- [x] Главное меню, экраны загрузки, выбор сценария и страны
- [x] Стартовая дата 1 января 1990 года
- [ ] Политическая карта 1990 года: союзные республики, Восточный блок, две Германии
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

The world map is still the vanilla 1936 setup; the 1990 political map is the next milestone.

**Install:** put the folder into `Documents/Paradox Interactive/Hearts of Iron IV/mod/`, create `Twilight of the Union.mod` next to it from `descriptor.mod` with a `path="..."` line pointing to the folder, then enable it in the launcher.

**Rebuild graphics:** `pip install pillow`, then `python tools/build_menu_gfx.py`.
