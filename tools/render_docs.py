"""Renders README screenshots into docs/images from the built textures.

These are approximations: the game uses its own fonts and real flags. Run after build_menu_gfx.py.
Usage: python tools/render_docs.py
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_menu_gfx as g  # noqa: E402

ROOT = g.ROOT
OUT = ROOT / "docs" / "images"
F = "C:/Windows/Fonts/"
TEXT = (235, 228, 215)
BODY = (225, 218, 206)


def L(rel):
    return Image.open(ROOT / rel).convert("RGBA")


def fnt(name, size):
    return ImageFont.truetype(F + name, size)


def screen(bg="gfx/loadingscreens/totu_red_square.dds"):
    return L(bg).crop((0, 180, 1920, 1260))


def centred(d, cx, y, text, f, fill=TEXT):
    d.text((cx - d.textlength(text, font=f) / 2, y), text, font=f, fill=fill)


def save(img, name):
    OUT.mkdir(parents=True, exist_ok=True)
    img = img.convert("RGB")
    img.thumbnail((1600, 1600), Image.LANCZOS)
    img.save(OUT / name, quality=86)
    print("wrote", (OUT / name).relative_to(ROOT))


def main_menu():
    shot = Image.open(ROOT / "tools/preview/menu_preview.png").convert("RGBA")
    save(shot, "main_menu.jpg")


def loading():
    shot = screen("gfx/loadingscreens/totu_load_tanks_red_square.dds")
    logo = L("gfx/interface/totu/menu_logo.dds")
    logo = logo.resize((int(logo.width * .75), int(logo.height * .75)), Image.LANCZOS)
    shot.alpha_composite(logo, (30, 26))
    cx, by = 960, 1080
    shot.alpha_composite(L("gfx/interface/totu/loading_tip.dds"), (cx - 550, by - 228))
    shot.alpha_composite(L("gfx/interface/totu/loading_status.dds"), (cx - 550, by - 120))
    shot.alpha_composite(L("gfx/interface/totu/loading_progress_empty.dds"), (cx - 467, by - 56))
    shot.alpha_composite(L("gfx/interface/totu/loading_progress_full.dds").crop((0, 0, 600, 20)), (cx - 467, by - 56))
    d = ImageDraw.Draw(shot)
    centred(d, cx, by - 200, "«Господин Горбачёв, снесите эту стену!»", fnt("georgia.ttf", 24), BODY)
    centred(d, cx, by - 166, "- Рональд Рейган, Берлин, 1987", fnt("georgia.ttf", 18), (195, 176, 145))
    centred(d, cx, by - 104, "ЗАГРУЗКА КАРТЫ", fnt("bahnschrift.ttf", 26))
    save(shot, "loading_screen.jpg")


def loading_sheet():
    names = ["tanks_red_square", "yeltsin_podium", "yeltsin_tank", "white_house"]
    sheet = Image.new("RGB", (1928, 1088), (10, 8, 7))
    for i, n in enumerate(names):
        im = L(f"gfx/loadingscreens/totu_load_{n}.dds").crop((0, 180, 1920, 1260)).resize((960, 540), Image.LANCZOS)
        sheet.paste(im.convert("RGB"), (4 + (i % 2) * 964, 4 + (i // 2) * 544))
    save(sheet, "loading_screens.jpg")


def scenario():
    shot = screen()
    sx, sy = 960 - 289, 540 - 256
    shot.alpha_composite(L("gfx/interface/totu/scenario_bg.dds"), (sx, sy))
    ex, ey = sx + 173, sy + 55
    shot.alpha_composite(L("gfx/interface/totu/bookmark_entry.dds").crop((232, 0, 464, 211)), (ex, ey))
    shot.alpha_composite(L("gfx/interface/totu/select_date_1990.dds"), (ex + 27, ey + 28))
    btn = L("gfx/interface/totu/button_221x34.dds")
    shot.alpha_composite(btn.crop((0, 0, 221, 34)), (sx + 30, sy + 455))
    shot.alpha_composite(btn.crop((221, 0, 442, 34)), (sx + 327, sy + 455))
    d = ImageDraw.Draw(shot)
    fb = fnt("bahnschrift.ttf", 20)
    centred(d, sx + 290, sy + 16, "Выбрать сценарий", fb)
    centred(d, ex + 116, ey + 150, "1 января 1990", fb)
    centred(d, sx + 280, sy + 276, "Краткая история", fb)
    d.text((sx + 25, sy + 307), "Сумерки Союза", font=fnt("cour.ttf", 20), fill=(30, 25, 20))
    d.multiline_text((sx + 25, sy + 334),
                     "1 января 1990 года. Семь недель назад пала Берлинская\nстена, Варшавский договор расползается по швам,\n"
                     "а Советский Союз входит в новое десятилетие с пустыми\nполками и беспокойными республиками...",
                     font=fnt("cour.ttf", 14), fill=(40, 34, 28), spacing=4)
    centred(d, sx + 140, sy + 461, "Назад", fb)
    centred(d, sx + 437, sy + 461, "Выбрать", fb)
    save(shot, "scenario.jpg")


def country_select():
    shot = screen()
    wx, wy = 960 - 612, 540 - 358
    shot.alpha_composite(L("gfx/interface/totu/country_select_bg.dds"), (wx, wy))
    d = ImageDraw.Draw(shot)
    fb, fbig = fnt("bahnschrift.ttf", 18), fnt("bahnschrift.ttf", 22)
    fs, fsb = fnt("segoeui.ttf", 14), fnt("segoeuib.ttf", 13)
    centred(d, wx + 612, wy + 11, "Выбрать страну", fbig)
    ent = L("gfx/interface/totu/country_entry_major.dds")
    cards = [(g.us_flag(82, 52), "Соединённые Штаты\nАмерики", 0),
             (g.soviet_flag(82, 52), "Союз Советских\nСоциалистических\nРеспублик", 1)]
    for i, (flag, name, sel) in enumerate(cards):
        x, y = wx + 462 + i * 150, wy + 41
        shot.paste(flag, (x + g.MAJOR_FLAG_POS[0], y + g.MAJOR_FLAG_POS[1]))
        shot.alpha_composite(ent.crop((sel * 150, 0, sel * 150 + 150, 274)), (x, y))
        d.multiline_text((x + 75, y + g.MAJOR_NAME_Y - 4 + g.MAJOR_NAME_H // 2), name, font=fsb, fill=TEXT,
                         anchor="mm", align="center", spacing=2)
    med = L("gfx/interface/totu/country_entry_minor.dds").crop((0, 0, 138, 97))
    stripes = [((255, 255, 255), (220, 20, 60)), ((255, 255, 255), (17, 69, 126)), ((206, 41, 57), (71, 112, 80)),
               ((0, 43, 127), (206, 17, 38)), ((255, 255, 255), (0, 150, 110)), ((222, 41, 16), (222, 41, 16)),
               ((1, 33, 105), (200, 16, 46)), ((0, 35, 149), (237, 41, 57))]
    for i, (a, b) in enumerate(stripes):
        x, y = wx + 12 + i * 150, wy + 333
        fl = Image.new("RGB", (82, 52), a)
        ImageDraw.Draw(fl).rectangle((0, 26, 82, 52), fill=b)
        shot.paste(fl, (x + 26, y + 22))
        shot.alpha_composite(med, (x, y))
    centred(d, wx + 157, wy + 462, "Сведения", fbig)
    yy = wy + 497
    for lab, val in [("Лидер", "Михаил Горбачёв"), ("Идеология", "Коммунизм"), ("Правительство", "Коммунистическое"),
                     ("Выборы", "Не проводятся"), ("Правящая партия", "КПСС")]:
        d.text((wx + 35, yy - 5), lab, font=fs, fill=(205, 198, 186))
        d.text((wx + 35, yy + 12), val, font=fnt("segoeuib.ttf", 15), fill=(240, 234, 224))
        yy += 40
    pp = L("gfx/leaders/totu/SOV_mikhail_gorbachev.dds").resize((109, 146), Image.LANCZOS)
    shot.alpha_composite(pp, (wx + 289, wy + 457))
    shot.alpha_composite(L("gfx/interface/totu/minor_portrait_overlay.dds"), (wx + 280, wy + 446))
    centred(d, wx + 612, wy + 458, "Союз Советских Социалистических Республик", fb)
    centred(d, wx + 1002, wy + 462, "Историческая справка", fbig)
    d.multiline_text((wx + 810, wy + 502),
                     "Пять лет перестройки расшатали всё и ничего\nне исправили. Прибалтика рвётся на свободу,\n"
                     "Кавказ горит, экономика падает, а монополию\nпартии на власть вот-вот вынесут на голосование.\n\n"
                     "Союз ещё можно реформировать, удержать силой\nили отпустить. Оставить как есть уже нельзя.",
                     font=fs, fill=BODY, spacing=4)
    btn = L("gfx/interface/totu/button_148x34.dds")
    for x, t, fr in [(wx + 454, "Назад", 0), (wx + 622, "Играть", 1)]:
        shot.alpha_composite(btn.crop((fr * 148, 0, fr * 148 + 148, 34)), (x, wy + 675))
        centred(d, x + 74, wy + 681, t, fb)
    save(shot, "country_select.jpg")


if __name__ == "__main__":
    main_menu()
    loading()
    loading_sheet()
    scenario()
    country_select()
