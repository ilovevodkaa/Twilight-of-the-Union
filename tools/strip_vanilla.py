"""Remove the 1936 vanilla content the mod no longer uses, keeping the vanilla systems that still run.

descriptor.mod / "Twilight of the Union.mod" drop vanilla events, focus trees and decisions with replace_path. Other
vanilla files still point at them, which the game reports as errors and which would misbehave if run. This tool
writes mod copies (same path, so they replace the vanilla file) of every such file with those references
neutralised; nothing else in them changes:
  - triggers on a removed decision, mission, focus or focus tree (has_decision, has_active_mission,
    has_completed_focus, has_focus_tree) become `always = no`, which is exactly what they evaluate to now;
  - effects on removed decisions, missions, categories, focuses or focus trees (activate_mission,
    unlock_decision_tooltip, load_focus_tree, complete_national_focus, ...) are cut;
  - every event call is cut from the files it rewrites (all vanilla events are gone).
Also writes common/national_focus/generic.txt (the vanilla generic tree for countries without their own)
and 00_titlebar_styles.txt (the focus plate styles).
common/on_actions/<vanilla name>.txt are always rebuilt from vanilla, also without the 1936 on_startup blocks;
the mod's own on_actions files (TOTU_*/totu_*) are never touched. tools/build_world_1990.py should call this
tool instead of rewriting on_actions itself.

Known leftover (only with -debug): the DLC song lists (dlc/*/music/*.txt: mtg_songs, lar_songs, sabatonsoundtrack,
lar_preorder_songs) check 1936 focuses. They are not copied on purpose: a mod copy would declare DLC songs for
players who don't own the DLC.

Usage: python tools/strip_vanilla.py           (re-run after a game update or after adding mod decisions)
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GAME = Path(r"D:\steam\steamapps\common\Hearts of Iron IV")

# folders the mod replaces outright (keep in sync with replace_path in descriptor.mod)
REPLACED = ["events", "common/national_focus", "common/decisions", "common/decisions/categories",
            "common/ai_strategy_plans", "history/countries", "history/states"]
SKIP_DIRS = set(REPLACED) | {"common/on_actions"}   # on_actions: always rewritten

EVENT_KEYS = {"country_event", "news_event", "state_event", "unit_leader_event", "operative_leader_event",
              "random_events", "events"}
TRIGGER_KEYS = {"has_decision", "has_active_mission", "has_completed_focus", "has_focus_tree"}
EFFECT_KEYS = {"activate_mission", "remove_mission", "activate_decision", "remove_decision", "unlock_decision_tooltip",
               "unlock_decision_category_tooltip", "activate_targeted_decision", "remove_targeted_decision",
               "add_days_mission_timeout", "add_days_remove", "load_focus_tree", "complete_national_focus",
               "unlock_national_focus", "uncomplete_national_focus"}
INNER_KEYS = {"decision", "mission", "tree", "category", "id"}
HEADER = ("# NEUTRALISED COPY of vanilla {src} made by tools/strip_vanilla.py: references to the removed vanilla\n"
          "# events, decisions and focus trees are cut. Edit the tool, not this file.\n")
OLD_HEADERS = ("# NEUTRALISED COPY", "# STRIPPED COPY")


def tokens(text):
    """(start, end, kind) for words, '=', '{', '}', strings; comments are skipped."""
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == "#":
            j = text.find("\n", i)
            i = n if j < 0 else j
        elif c.isspace():
            i += 1
        elif c == '"':
            j = text.find('"', i + 1)
            j = n - 1 if j < 0 else j
            yield i, j + 1, "str"
            i = j + 1
        elif c in "{}=":
            yield i, i + 1, c
            i += 1
        elif c in "<>!":
            j = i + 1 + (text[i + 1:i + 2] == "=")
            yield i, j, "="
            i = j
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in '{}=#"<>!':
                j += 1
            yield i, j, "word"
            i = j


def block_end(toks, k):
    """Index of the '}' closing the '{' at toks[k]."""
    depth = 0
    for m in range(k, len(toks)):
        if toks[m][2] == "{":
            depth += 1
        elif toks[m][2] == "}":
            depth -= 1
            if depth == 0:
                return m
    return len(toks) - 1


def top_level_keys(text, depth_wanted):
    """Keys of `key = {` blocks at the given brace depth."""
    toks, depth, out = list(tokens(text)), 0, []
    for k, (s, e, kind) in enumerate(toks):
        if kind == "{":
            depth += 1
        elif kind == "}":
            depth -= 1
        elif kind == "word" and depth == depth_wanted and k + 2 < len(toks) and toks[k + 1][2] == "=" \
                and toks[k + 2][2] == "{":
            out.append(text[s:e])
    return out


def defined_names(base):
    """Decision, category, focus tree and focus names defined under base (the game or the mod)."""
    names = set()
    for p in (base / "common/decisions").glob("*.txt"):
        t = p.read_text(encoding="utf-8-sig", errors="replace")
        names |= set(top_level_keys(t, 0)) | set(top_level_keys(t, 1))
    for p in (base / "common/decisions/categories").glob("*.txt"):
        names |= set(top_level_keys(p.read_text(encoding="utf-8-sig", errors="replace"), 0))
    for p in (base / "common/national_focus").glob("*.txt"):
        t = p.read_text(encoding="utf-8-sig", errors="replace")
        names |= set(re.findall(r"focus_tree\s*=\s*\{\s*(?:#[^\n]*\n\s*)*id\s*=\s*([\w.]+)", t))
        names |= set(re.findall(r"(?<![\w.])(?:focus|shared_focus|joint_focus)\s*=\s*\{\s*(?:#[^\n]*\n\s*)*id\s*=\s*([\w.\-]+)", t))
    return names


def neutralise(text, gone):
    """Rewrite one file; returns (text, number of changes)."""
    toks = list(tokens(text))
    edits, k = [], 0                      # (start, end, replacement)
    while k < len(toks):
        s, e, kind = toks[k]
        key = text[s:e] if kind == "word" else ""
        if key and k + 2 < len(toks) and toks[k + 1][2] == "=":
            vs, ve, vkind = toks[k + 2]
            if vkind == "{":
                end = block_end(toks, k + 2)
                span = (s, toks[end][1])
                inner = [text[toks[m + 2][0]:toks[m + 2][1]] for m in range(k + 3, end)
                         if toks[m][2] == "word" and text[toks[m][0]:toks[m][1]] in INNER_KEYS
                         and toks[m + 1][2] == "=" and toks[m + 2][2] == "word"]
            else:
                end, span, inner = k + 2, (s, ve), [text[vs:ve]]
            if key in EVENT_KEYS:
                edits.append((*span, ""))
                k = end + 1
                continue
            if key in TRIGGER_KEYS and any(v in gone for v in inner):
                edits.append((*span, "always = no"))
                k = end + 1
                continue
            if key in EFFECT_KEYS and any(v in gone for v in inner):
                edits.append((*span, ""))
                k = end + 1
                continue
        k += 1
    out, last = [], 0
    for s, e, rep in edits:
        out.append(text[last:s])
        out.append(rep)
        last = e
    out.append(text[last:])
    return "".join(out), len(edits)


def cut_on_startup(text):
    """Remove every on_startup block (vanilla sets up 1936 there: Spanish Civil War, warlords, colonies)."""
    toks = list(tokens(text))
    cuts, k = [], 0
    while k < len(toks):
        s, e, kind = toks[k]
        if kind == "word" and text[s:e] == "on_startup" and k + 2 < len(toks) and toks[k + 1][2] == "=" \
                and toks[k + 2][2] == "{":
            end = block_end(toks, k + 2)
            cuts.append((s, toks[end][1]))
            k = end + 1
            continue
        k += 1
    for s, e in reversed(cuts):
        text = text[:s] + "# on_startup removed by Twilight of the Union (1936 setup)" + text[e:]
    return text, len(cuts)


def strip_header(text):
    if text.startswith(OLD_HEADERS):
        return text.split("\n", 2)[2]
    return text


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def main():
    gone = defined_names(GAME) - defined_names(ROOT) - {"generic_focus"}
    print(f"{len(gone)} vanilla decisions, categories and focus trees are gone")
    total = 0

    # on_actions: always rebuilt from vanilla, without the 1936 on_startup setup (it crashes the 1990 world) and
    # without event calls. The mod's own on_actions files (TOTU_*/totu_*) are never touched.
    for van in sorted((GAME / "common/on_actions").glob("*.txt")):
        text, n_startup = cut_on_startup(van.read_text(encoding="utf-8-sig"))
        new, n = neutralise(text, gone)
        write(ROOT / "common/on_actions" / van.name, HEADER.format(src=f"common/on_actions/{van.name}") + new)
        total += n + n_startup

    # the generic tree stays for countries without their own, and the focus plate styles with it
    for name in ("generic.txt", "00_titlebar_styles.txt"):
        new, n = neutralise((GAME / "common/national_focus" / name).read_text(encoding="utf-8-sig"), gone)
        write(ROOT / "common/national_focus" / name, HEADER.format(src=f"common/national_focus/{name}") + new)
        total += n

    # every other vanilla file that points at something removed
    rewritten = []
    for van in sorted(list((GAME / "common").rglob("*.txt")) + list((GAME / "history").rglob("*.txt"))
                      + list((GAME / "music").rglob("*.txt"))):
        rel = van.relative_to(GAME).as_posix()
        if any(rel.startswith(d + "/") for d in SKIP_DIRS):
            continue
        mod = ROOT / rel
        if mod.exists() and not mod.read_text(encoding="utf-8-sig", errors="replace").startswith(OLD_HEADERS):
            continue                       # a real mod file with the same name: not ours to rewrite
        text = van.read_text(encoding="utf-8-sig", errors="replace")   # copies are always rebuilt from vanilla
        probe = text
        for g in ("has_decision", "has_active_mission", "load_focus_tree", "mission", "decision", "_focus"):
            if g in probe:
                break
        else:
            continue
        new, n = neutralise(text, gone)
        # only keep a copy when something besides event calls changed
        _, n_events_only = neutralise(text, set())
        if n > n_events_only:
            write(mod, HEADER.format(src=rel) + new)
            rewritten.append(rel)
            total += n
        elif mod.exists():
            mod.unlink()                    # stale copy from an earlier run
    print(f"{len(rewritten)} vanilla files rewritten:")
    for r in rewritten:
        print("  ", r)
    print("total changes", total)


if __name__ == "__main__":
    sys.exit(main())
