"""1990 country setup for the major tags: history/countries/*, leader characters and their localisation.

Same structure as the hand-written SOV / USA files. Rewrites only the tags in COUNTRIES (keeps the capital line
that tools/build_map.py generated). Characters are written to common/characters/TOTU_leaders.txt together with
the SOV / USA leaders that already carry portraits. Run after build_map.py:  python tools/build_countries_1990.py

Leader choices (de facto leader on 1 January 1990):
  GER  Helmut Kohl (Chancellor)                DDR  Hans Modrow (Chairman of the Council of Ministers; Krenz resigned
  POL  Tadeusz Mazowiecki (PM; President           6 Dec 1989, SED-PDS chair is Gregor Gysi)
       Jaruzelski keeps the presidency)        ROM  Ion Iliescu (Council of the National Salvation Front)
  YUG  Ante Markovic (Federal PM)              PRC  Jiang Zemin (General Secretary; Deng Xiaoping is CMC chairman)
  JAP  Toshiki Kaifu (PM)                      ENG  Margaret Thatcher     FRA  Francois Mitterrand
  ITA  Giulio Andreotti (PM)                   CZE  Vaclav Havel (President since 29 Dec 1989)
  HUN  Miklos Nemeth (PM; Szuros is acting     BUL  Petar Mladenov (Chairman of the State Council)
       president)                              CAN  Brian Mulroney       RAJ  V. P. Singh (PM since 2 Dec 1989)
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# tag: (char id, English, Russian, leader ideology, ruling party, last election, months, elections allowed,
#       (democratic, fascism, communism, neutrality), research slots, stability, war support, laws)
C = {
 "GER": ("GER_helmut_kohl", "Helmut Kohl", "Гельмут Коль", "conservatism", "democratic", "1987.1.25", 48, "yes",
         (89, 1, 2, 8), 4, 0.80, 0.15, "civilian_economy free_trade limited_conscription"),
 "DDR": ("DDR_hans_modrow", "Hans Modrow", "Ханс Модров", "marxism", "communism", "1986.6.8", 60, "no",
         (25, 2, 55, 18), 3, 0.35, 0.25, "partial_economic_mobilisation closed_economy extensive_conscription"),
 "POL": ("POL_tadeusz_mazowiecki", "Tadeusz Mazowiecki", "Тадеуш Мазовецкий", "conservatism", "democratic", "1989.6.4", 48, "yes",
         (62, 2, 28, 8), 3, 0.50, 0.25, "civilian_economy free_trade extensive_conscription"),
 "ROM": ("ROM_ion_iliescu", "Ion Iliescu", "Ион Илиеску", "oligarchism", "neutrality", "1989.3.9", 60, "no",
         (23, 2, 20, 55), 3, 0.30, 0.25, "partial_economic_mobilisation closed_economy extensive_conscription"),
 "YUG": ("YUG_ante_markovic", "Ante Marković", "Анте Маркович", "marxism", "communism", "1986.4.1", 48, "no",
         (28, 5, 50, 17), 3, 0.45, 0.20, "low_economic_mobilisation limited_exports extensive_conscription"),
 "PRC": ("PRC_jiang_zemin", "Jiang Zemin", "Цзян Цзэминь", "leninism", "communism", "1988.3.25", 60, "no",
         (12, 2, 78, 8), 4, 0.60, 0.35, "partial_economic_mobilisation limited_exports extensive_conscription"),
 "JAP": ("JAP_toshiki_kaifu", "Toshiki Kaifu", "Тосики Кайфу", "conservatism", "democratic", "1986.7.6", 48, "yes",
         (85, 2, 5, 8), 5, 0.75, 0.10, "civilian_economy free_trade volunteer_only"),
 "ENG": ("ENG_margaret_thatcher", "Margaret Thatcher", "Маргарет Тэтчер", "conservatism", "democratic", "1987.6.11", 60, "yes",
         (88, 1, 3, 8), 5, 0.70, 0.25, "low_economic_mobilisation free_trade volunteer_only"),
 "FRA": ("FRA_francois_mitterrand", "François Mitterrand", "Франсуа Миттеран", "socialism", "democratic", "1988.5.8", 84, "yes",
         (80, 2, 10, 8), 5, 0.65, 0.25, "low_economic_mobilisation free_trade limited_conscription"),
 "ITA": ("ITA_giulio_andreotti", "Giulio Andreotti", "Джулио Андреотти", "conservatism", "democratic", "1987.6.14", 60, "yes",
         (80, 2, 14, 4), 4, 0.55, 0.20, "civilian_economy free_trade limited_conscription"),
 "CZE": ("CZE_vaclav_havel", "Václav Havel", "Вацлав Гавел", "liberalism", "democratic", "1986.5.23", 48, "yes",
         (55, 2, 38, 5), 3, 0.50, 0.20, "low_economic_mobilisation limited_exports extensive_conscription"),
 "HUN": ("HUN_miklos_nemeth", "Miklós Németh", "Миклош Немет", "socialism", "democratic", "1985.6.8", 48, "yes",
         (50, 2, 35, 13), 3, 0.45, 0.25, "low_economic_mobilisation limited_exports extensive_conscription"),
 "BUL": ("BUL_petar_mladenov", "Petar Mladenov", "Петр Младенов", "marxism", "communism", "1986.6.8", 60, "no",
         (25, 2, 65, 8), 3, 0.40, 0.25, "partial_economic_mobilisation closed_economy extensive_conscription"),
 "CAN": ("CAN_brian_mulroney", "Brian Mulroney", "Брайан Малруни", "conservatism", "democratic", "1988.11.21", 60, "yes",
         (89, 1, 2, 8), 4, 0.75, 0.10, "civilian_economy free_trade volunteer_only"),
 "RAJ": ("RAJ_vishwanath_pratap_singh", "V. P. Singh", "Вишванат Пратап Сингх", "socialism", "democratic", "1989.11.22", 60, "yes",
         (62, 3, 10, 25), 4, 0.50, 0.30, "civilian_economy closed_economy volunteer_only"),
}

CHAR = """\
	{id} = {{
		name = {id}
		country_leader = {{
			ideology = {ideo}
			expire = "2030.1.1.1"
			id = -1
		}}
	}}
"""


def history(tag, d):
    cid, en, ru, ideo, party, last, freq, allowed, pops, rs, stab, ws, laws = d
    f = next((ROOT / "history/countries").glob(f"{tag} - *.txt"))
    cap = re.search(r"capital\s*=\s*(\d+)\s*(#.*)?", f.read_text(encoding="utf-8-sig"))
    capline = f"capital = {cap.group(1)} {cap.group(2) or ''}".rstrip()
    names = ["democratic", "fascism", "communism", "neutrality"]
    pop = "\n".join(f"\t{n} = {v}" for n, v in zip(names, pops))
    assert sum(pops) == 100, tag
    law = "\n".join(f"\t{x}" for x in laws.split())
    f.write_text(f"""# Twilight of the Union: 1 January 1990. Same structure as SOV / USA.
# Leader: {en} ({cid}, common/characters/TOTU_leaders.txt)

{capline}

set_research_slots = {rs}
set_stability = {stab}
set_war_support = {ws}

set_politics = {{
	ruling_party = {party}
	last_election = "{last}"
	election_frequency = {freq}
	elections_allowed = {allowed}
}}
set_popularities = {{
{pop}
}}

add_ideas = {{
{law}
}}

recruit_character = {cid}
promote_character = {cid}
""", encoding="utf-8")


def characters():
    p = ROOT / "common/characters/TOTU_leaders.txt"
    txt = p.read_text(encoding="utf-8-sig")
    head = txt[: txt.index("\tSOV_mikhail_gorbachev")] if "\tSOV_mikhail_gorbachev" in txt else None
    # keep SOV / USA blocks (they carry portraits), regenerate the rest
    body = txt.split("characters = {", 1)[1].rsplit("}", 1)[0]
    keep = "".join(m.group(0) for m in re.finditer(r"\t(?:SOV|USA)_\w+ = \{.*?\n\t\}\n", body, re.S))
    new = "\n".join(CHAR.format(id=d[0], ideo=d[3]) for d in C.values())
    comment = ("# Twilight of the Union: 1990 heads of state / government.\n"
               "# SOV / USA: portraits from interface/totu_portraits.gfx (tools/build_menu_gfx.py). Others: default portrait.\n"
               "# Generated for the rest by tools/build_countries_1990.py.\n")
    p.write_text(comment + "characters = {\n" + keep + "\n" + new + "}\n", encoding="utf-8")


def loc():
    for lang, idx in (("english", 1), ("russian", 2)):
        p = ROOT / f"localisation/{lang}/totu_characters_l_{lang}.yml"
        lines = [f"l_{lang}:"] + [f' {d[0]}:0 "{d[idx]}"' for d in C.values()]
        p.write_text("﻿" + "\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    for t, d in C.items():
        history(t, d)
    characters()
    loc()
    print("ok", len(C))
