"""National focus trees designed in the focus editor artifact (Focus Tree Studio) -> game files.

Source: tools/src/focus/<TAG>.json, a snapshot of the editor document trees/<TAG>: focuses with grid position,
prerequisites (groups are ANDed, focuses inside a group ORed), mutual exclusions and effects; national spirits
with modifiers; Russian and English texts. Everything below is GENERATED from it, edit the editor, not these:
  common/national_focus/TOTU_<TAG>.txt
  common/ideas/TOTU_<TAG>_focus.txt                       the spirits defined in the editor
  localisation/{russian,english}/totu_focus_<TAG>_l_<lang>.yml

The editor can only describe some effects and conditions in words ("text" effects, the available/bypass fields).
Those are written by hand and picked up by name:
  common/scripted_effects/TOTU_<TAG>_focus_effects.txt    <focus id>_effect, run at the end of the reward;
                                                          <focus id>_select_effect, run when the focus is picked
  common/scripted_triggers/TOTU_<TAG>_focus_triggers.txt  <focus id>_available / _bypass / _allow_branch
Icons: tools/gen_icons.py (FOCUS_<TAG>) -> GFX_focus_<focus id>; spirit pictures are totu_<spirit id without
TOTU_<TAG>_>, also from tools/gen_icons.py.

Usage: python tools/build_focus_tree.py [TAG ...]       (default SOV)
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "tools/src/focus"

# The editor grid is one focus wide per column; vanilla focus_spacing (interface/nationalfocusview.gui) is half
# a focus, so columns are doubled. Rows map 1:1 (the mod's focus_spacing is taller for the big icons).
X_SCALE = 2
ROW_PX = 145   # focus_spacing y in interface/nationalfocusview.gui (taller than vanilla's 130 for the big icons)
DAYS_PER_COST = 7
# languages the mod ships besides Russian and English; they get English copies of the tree's localisation
MIRROR_LANGS = ["braz_por", "french", "german", "japanese", "korean", "polish", "simp_chinese", "spanish"]
# hand-written localisation of each tree (localisation/english/<name>_l_english.yml), mirrored the same way
HAND_LOC = {"SOV": ["totu_sov_politics", "totu_sov_plenum", "totu_plenum_core", "totu_sov_news"],
            # totu_world: texts of the world, not of one country (the NATO and Warsaw Pact factions); mirrored here
            # until there is a builder for world-level content
            "DDR": ["totu_ddr_politics", "totu_ddr_tree", "totu_world"]}
# focus options the editor has no field for yet
FOCUS_OPTIONS = {"SOV": {"SOV_central_committee_plenum": ["cancelable = no"]}}
# name of the tree itself (focus_tree id TOTU_<TAG>_focus), shown where the game names the tree: (ru, en)
TREE_NAMES = {"SOV": ("Национальные фокусы СССР", "Soviet National Focus"),
              "DDR": ("Национальные фокусы ГДР", "East German National Focus")}
# Spirit pictures are totu_<spirit id without TOTU_<TAG>_>; trees after the Soviet one keep the tag in the name
# (totu_ddr_...), so countries cannot collide and tools/gen_icons.py can tell the setting from the name.
PIC_TAGGED = {"DDR"}

# editor modifier units: "%" values are typed in percent (see MODIFIERS in the editor)
PERCENT = {
    "political_power_factor", "stability_factor", "war_support_factor", "consumer_goods_factor",
    "production_speed_buildings_factor", "industrial_capacity_factory", "industrial_capacity_dockyard",
    "production_factory_max_efficiency_factor", "research_speed_factor", "local_resources_factor", "min_export",
    "conscription_factor", "training_time_factor", "mobilization_speed", "army_org_factor", "army_morale_factor",
    "army_attack_factor", "army_defence_factor", "supply_consumption_factor", "experience_gain_army_factor",
    "air_superiority_efficiency", "air_accidents_factor", "navy_org_factor", "repair_speed_factor",
    "monthly_population", "drift_defence_factor", "trade_opinion_factor", "enemy_justify_war_goal_time",
}
SLOTTED = {"industrial_complex", "arms_factory", "dockyard", "synthetic_refinery", "fuel_silo"}
FILTERS = {"pp": "FOCUS_FILTER_POLITICAL", "popularity": "FOCUS_FILTER_POLITICAL",
           "stability": "FOCUS_FILTER_STABILITY", "war": "FOCUS_FILTER_WAR_SUPPORT",
           "army_xp": "FOCUS_FILTER_ARMY_XP", "building": "FOCUS_FILTER_INDUSTRY",
           "research": "FOCUS_FILTER_RESEARCH", "manpower": "FOCUS_FILTER_MANPOWER"}


def num(v):
    v = round(float(v), 4)
    return str(int(v)) if v == int(v) else f"{v:g}"


def pct(v):
    return num(float(v) / 100)


def loc_text(s):
    """One-line loc value: real newlines become \\n, stray double quotes become typographic ones."""
    s = (s or "").strip().replace("\r", "").replace("\n", "\\n")
    return s.replace('"', "”")


def defined_names(path):
    """Top-level `name = {` blocks of a hand-written script file."""
    if not path.exists():
        return set()
    return set(re.findall(r"^([A-Za-z0-9_.]+)\s*=\s*\{", path.read_text(encoding="utf-8-sig"), re.M))


def effect_lines(e, focus):
    t, p = e["t"], e.get("p", {})
    if t == "pp":
        return [f"add_political_power = {num(p['value'])}"]
    if t == "stability":
        return [f"add_stability = {pct(p['value'])}"]
    if t == "war":
        return [f"add_war_support = {pct(p['value'])}"]
    if t == "add_idea":
        return [f"add_ideas = {p['idea']}"]
    if t == "remove_idea":
        return [f"remove_ideas = {p['idea']}"]
    if t == "swap_idea":   # the old spirit may already be gone (another branch, an event): then just add the new
        return ["if = {", f"\tlimit = {{ has_idea = {p['from']} }}",
                f"\tswap_ideas = {{ remove_idea = {p['from']} add_idea = {p['to']} }}", "}",
                "else = {", f"\tadd_ideas = {p['to']}", "}"]
    if t == "popularity":
        return [f"add_popularity = {{ ideology = {p['ideology']} popularity = {pct(p['value'])} }}"]
    if t == "building":
        n = max(1, round(float(p.get("count", 1))))
        out = ["capital_scope = {"]
        if p["type"] in SLOTTED:
            out.append(f"\tadd_extra_state_shared_building_slots = {n}")
        out += [f"\tadd_building_construction = {{ type = {p['type']} level = {n} instant_build = yes }}", "}"]
        return out
    if t == "research":
        return [f"add_tech_bonus = {{ name = {focus['id']} bonus = {pct(p['bonus'])} uses = {num(p['uses'])} "
                f"category = {p['category']} }}"]
    if t in ("army_xp", "air_xp", "navy_xp"):
        return [f"{t.replace('_xp', '_experience')} = {num(p['value'])}"]
    if t == "manpower":
        return [f"add_manpower = {num(p['value'])}"]
    if t == "flag":
        return [f"set_country_flag = {p['name']}"]
    if t == "event":
        days = f" days = {num(p['days'])}" if float(p.get("days") or 0) else ""
        return [f"country_event = {{ id = {p['id']}{days} }}"]
    if t == "text":
        return []   # written by hand as <focus id>_effect
    raise ValueError(f"{focus['id']}: unknown effect type {t}")


def build(tag):
    tree = json.loads((SRC / f"{tag}.json").read_text(encoding="utf-8"))
    focuses = tree["focuses"]
    by_key = {f["key"]: f for f in focuses}
    effects_file = ROOT / f"common/scripted_effects/TOTU_{tag}_focus_effects.txt"
    triggers_file = ROOT / f"common/scripted_triggers/TOTU_{tag}_focus_triggers.txt"
    hand_effects, hand_triggers = defined_names(effects_file), defined_names(triggers_file)
    spirit_ids = {s["id"] for s in tree.get("spirits", [])}
    problems = []

    def ref(key):
        return by_key[key]["id"]

    out = [f"# GENERATED by tools/build_focus_tree.py from tools/src/focus/{tag}.json (the focus editor document",
           f"# trees/{tag}). Edit the tree in the editor, not this file.",
           f"# Hand-written effects and conditions: {effects_file.relative_to(ROOT).as_posix()},",
           f"# {triggers_file.relative_to(ROOT).as_posix()}.", "",
           "focus_tree = {", f"\tid = TOTU_{tag}_focus", "",
           "\tcountry = {", "\t\tfactor = 0", "\t\tmodifier = {", "\t\t\tadd = 100", f"\t\t\ttag = {tag}", "\t\t}",
           "\t}", "", "\tdefault = no", "\treset_on_civilwar = no", ""]
    top = min(focuses, key=lambda f: (f["y"], abs(f["x"] - 12)))
    max_y = max(f["y"] for f in focuses)
    out += [f"\tinitial_show_position = {{ focus = {top['id']} }}",
            f"\tcontinuous_focus_position = {{ x = 50 y = {(max_y + 2) * ROW_PX} }}", ""]

    for f in sorted(focuses, key=lambda f: (f["y"], f["x"])):
        fid = f["id"]
        if f["name_ru"].strip() == "" or not f.get("name_en"):
            problems.append(f"{fid}: missing name")
        lines = [f"focus = {{", f"\tid = {fid}", f"\ticon = GFX_focus_{fid}",
                 f"\tx = {f['x'] * X_SCALE}", f"\ty = {f['y']}",
                 f"\tcost = {num(round(float(f['days']) / DAYS_PER_COST, 2))}"]
        for group in f.get("prereq", []):
            lines.append("\tprerequisite = { " + " ".join(f"focus = {ref(k)}" for k in group) + " }")
        if f.get("mutex"):
            lines.append("\tmutually_exclusive = { " + " ".join(f"focus = {ref(k)}" for k in f["mutex"]) + " }")
        for field in ("available", "bypass", "allow_branch"):   # allow_branch has no editor field: hand-only
            name = f"{fid}_{field}"
            if f.get(field) and name not in hand_triggers:
                problems.append(f"{fid}: the editor describes '{field}' but {triggers_file.name} has no {name}")
            if name in hand_triggers:
                lines.append(f"\t{field} = {{ {name} = yes }}")
        if f"{fid}_select_effect" in hand_effects:
            lines.append(f"\tselect_effect = {{ {fid}_select_effect = yes }}")
        lines += ["\t" + opt for opt in FOCUS_OPTIONS.get(tag, {}).get(fid, [])]
        filters =sorted({FILTERS[e["t"]] for e in f.get("effects", []) if e["t"] in FILTERS}) or [
            "FOCUS_FILTER_POLITICAL"]
        lines.append("\tsearch_filters = { " + " ".join(filters) + " }")
        ai = (f.get("ai") or "").strip()
        lines.append(f"\tai_will_do = {{ factor = {num(ai) if re.fullmatch(r'[0-9.]+', ai) else 1} }}")
        lines.append("\tcompletion_reward = {")
        for e in f.get("effects", []):
            for idea in (e.get("p", {}).get(k) for k in ("idea", "from", "to")):
                if idea and idea.startswith(f"TOTU_{tag}_") and idea not in spirit_ids and not idea_defined(idea):
                    problems.append(f"{fid}: unknown spirit {idea}")
            lines += ["\t\t" + ln for ln in effect_lines(e, f)]
        has_text = any(e["t"] == "text" for e in f.get("effects", []))
        if f"{fid}_effect" in hand_effects:
            lines.append(f"\t\t{fid}_effect = yes")
        elif has_text:
            problems.append(f"{fid}: the editor describes an effect in words but {effects_file.name} has no {fid}_effect")
        lines += ["\t}", "}"]
        out += ["\t" + ln for ln in lines] + [""]
    out.append("}")
    write(ROOT / f"common/national_focus/TOTU_{tag}.txt", "\n".join(out) + "\n")

    # spirits from the editor
    ideas = [f"# GENERATED by tools/build_focus_tree.py from tools/src/focus/{tag}.json: national spirits",
             f"# designed in the focus editor for the {tag} focus tree. Edit them in the editor, not here.",
             f"# Pictures: tools/gen_icons.py (totu_*) -> interface/totu_ideas.gfx.", "", "ideas = {", "\tcountry = {"]
    for s in tree.get("spirits", []):
        pic = ("totu_" + (f"{tag.lower()}_" if tag in PIC_TAGGED else "")
               + s["id"].removeprefix(f"TOTU_{tag}_"))
        ideas += ["", f"\t\t{s['id']} = {{", f"\t\t\tpicture = {pic}", "\t\t\tallowed = { always = no }",
                  "\t\t\tremoval_cost = -1", "\t\t\tmodifier = {"]
        for m in s.get("mods", []):
            k = m["k"]
            ideas.append(f"\t\t\t\t{k} = {pct(m['v']) if k in PERCENT else num(m['v'])}")
        ideas += ["\t\t\t}", "\t\t}"]
        if not (ROOT / f"tools/src/icons/idea/{pic}.png").exists():
            problems.append(f"{s['id']}: no picture tools/src/icons/idea/{pic}.png")
    ideas += ["\t}", "}"]
    write(ROOT / f"common/ideas/TOTU_{tag}_focus.txt", "\n".join(ideas) + "\n")

    # localisation
    for lang, suffix in (("russian", "ru"), ("english", "en")):
        rows = [f"l_{lang}:", f" # GENERATED by tools/build_focus_tree.py from tools/src/focus/{tag}.json."]
        rows.append(f' TOTU_{tag}_focus:0 "{loc_text(TREE_NAMES[tag][0 if suffix == "ru" else 1])}"')
        for f in sorted(focuses, key=lambda f: (f["y"], f["x"])):
            name = f.get(f"name_{suffix}") or f["name_ru"]
            desc = f.get(f"desc_{suffix}") or f.get("desc_ru", "")
            rows += [f' {f["id"]}:0 "{loc_text(name)}"', f' {f["id"]}_desc:0 "{loc_text(desc)}"']
        rows.append(" # national spirits")
        for s in tree.get("spirits", []):
            rows += [f' {s["id"]}:0 "{loc_text(s.get(f"name_{suffix}") or s["name_ru"])}"',
                     f' {s["id"]}_desc:0 "{loc_text(s.get(f"desc_{suffix}") or s.get("desc_ru", ""))}"']
        write(ROOT / f"localisation/{lang}/totu_focus_{tag}_l_{lang}.yml", "\n".join(rows) + "\n", bom=True)

    # The game has no fallback language: the other languages the mod ships get the English text (generated copies).
    hand = [ROOT / f"localisation/english/{name}_l_english.yml" for name in HAND_LOC.get(tag, [])]
    sources = [ROOT / f"localisation/english/totu_focus_{tag}_l_english.yml"] + hand
    for lang in MIRROR_LANGS:
        for src in sources:
            if not src.exists():
                problems.append(f"missing {src.relative_to(ROOT).as_posix()} (HAND_LOC)")
                continue
            body = src.read_text(encoding="utf-8-sig").split("\n", 1)[1]
            name = src.name.replace("_l_english.yml", f"_l_{lang}.yml")
            note = f" # GENERATED by tools/build_focus_tree.py: English copy of localisation/english/{src.name}.\n"
            write(ROOT / f"localisation/{lang}/{name}", f"l_{lang}:\n" + note + body, bom=True)

    for f in focuses:
        if not (ROOT / f"tools/src/icons/focus/{f['id']}.png").exists():
            problems.append(f"{f['id']}: no icon tools/src/icons/focus/{f['id']}.png")
    for p in problems:
        print("WARNING", p)
    print(f"{tag}: {len(focuses)} focuses, {len(tree.get('spirits', []))} spirits")
    return not problems


_IDEAS_TEXT = None


def idea_defined(idea):
    """Spirits written by hand in common/ideas (e.g. the starting ones)."""
    global _IDEAS_TEXT
    if _IDEAS_TEXT is None:
        _IDEAS_TEXT = "\n".join(p.read_text(encoding="utf-8-sig") for p in (ROOT / "common/ideas").glob("*.txt"))
    return re.search(rf"^\s*{re.escape(idea)}\s*=\s*\{{", _IDEAS_TEXT, re.M) is not None


def write(path, text, bom=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(("﻿" if bom else "").encode("utf-8") + text.encode("utf-8"))
    print("wrote", path.relative_to(ROOT).as_posix())


if __name__ == "__main__":
    ok = all([build(t) for t in (sys.argv[1:] or ["SOV"])])
    sys.exit(0 if ok else 1)
