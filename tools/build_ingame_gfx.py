"""In-game texture pipeline of Twilight of the Union: every live vanilla chrome texture in the broadcast style.

Each live texture of tools/data/chrome_manifest.json (scopes ingame, code, script, menu, plus EXTRA_LIVE) is written
to the same path in the mod (gfx/interface/... or gfx/minimap/...), same pixel size, so no .gfx/.gui change is
needed. It is produced by the area module that claims it (tools/ingame/<area>.py: AREA, TEXTURES = {path: fn},
optional LOSSLESS) or else by the generic broadcast treatment (tools/ingame/generic.py). See tools/ingame/README.md.

Usage (any working directory):
  python tools/build_ingame_gfx.py                   full run: every live texture + module extras; files listed in
                                                     tools/data/ingame_outputs.txt that are no longer produced are
                                                     deleted (never anything else, and nothing at all when a module
                                                     was skipped); rewrites tools/data/ingame_owners.json
  python tools/build_ingame_gfx.py --only kit,views  just the paths these areas produce (stream agents use this,
                                                     so parallel runs never write the same file)
  python tools/build_ingame_gfx.py --generic-only    just the paths no module claims
  python tools/build_ingame_gfx.py --paths "techtree/*,tiles/tiled_window.dds"   restrict any command (fnmatch)
  python tools/build_ingame_gfx.py --list kit        job table of an area (owner or producer), with generic mode
  python tools/build_ingame_gfx.py --preview kit     tools/preview/ingame_kit[_N].png: vanilla | result on the
                                                     board (what the game sees, DXT5 decoded); writes no texture
  python tools/build_ingame_gfx.py --sizes           disk size of the generated textures by area and format
  python tools/build_ingame_gfx.py --verify          sizes, formats, mipmaps, decoding, semantic colour check
  python tools/build_ingame_gfx.py --owners          re-derive tools/data/ingame_owners.json, print counts and MB
  python tools/build_ingame_gfx.py --import-manifest PATH   refresh tools/data/chrome_manifest.json from a full
                                                     mapping-pass manifest (bulky fields dropped)
Options: --jobs N (worker processes, default cpu-1), --game PATH (vanilla folder; env HOI4_DIR),
         --skip-broken (full run: skip area modules that fail to import; stale deletion is then disabled),
         --per-sheet N (preview, default 120), --no-dxt-odd (policy experiment: no DXT5 for sides that are not
         multiples of 4).
Builders print ASCII only.
"""
import argparse
import fnmatch
import importlib
import io
import json
import os
import re
import struct
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
DATA = TOOLS / "data"
PREVIEW = TOOLS / "preview"
MANIFEST = DATA / "chrome_manifest.json"
OWNERS = DATA / "ingame_owners.json"
OUTPUTS = DATA / "ingame_outputs.txt"
LOCK = DATA / "ingame_outputs.lock"
GAME_GUESSES = [os.environ.get("HOI4_DIR", ""), r"D:\steam\steamapps\common\Hearts of Iron IV",
                r"C:\Program Files (x86)\Steam\steamapps\common\Hearts of Iron IV"]

if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
from ingame import AREAS  # noqa: E402
from ingame import generic  # noqa: E402

LIVE_SCOPES = ("ingame", "code", "script", "menu")
# frontend_done textures the mod's own frontendgamesetupview.gui still shows in the game rule / difficulty windows
# (owned by the rules area): they are produced like live textures
EXTRA_LIVE = ("changed_slider_indicator.dds", "custom_difficulty_slider_bg.dds", "expand_collapse_sideways.dds")
KEEP_FIELDS = ("texture", "file", "class", "scope", "w", "h", "fmt", "mips", "bytes", "frames", "frame_w",
               "border", "sprites", "defined_in", "guis", "gui_refs", "mod_gui_refs", "effect_files",
               "sprite_kinds", "code_ref_sprites", "referenced_as")

# DXT5 policy: at least DXT_MIN_PX pixels and not lossless -> DXT5, also for sides that are not multiples of 4
# (vanilla itself ships and references 55+ such DXT textures, e.g. combat_header.dds 411x27, unit_stats_list_bg.dds
# 273x392; Pillow encodes the partial edge blocks correctly); else uncompressed A8R8G8B8 like vanilla.
DXT_MIN_PX = 16384
DXT_ODD_SIZES = True        # --no-dxt-odd: only sides that are multiples of 4 (the old policy, ~230 MB)


def find_game(arg=None):
    for g in [arg] + GAME_GUESSES:
        if g and (Path(g) / "gfx" / "interface").is_dir():
            return Path(g)
    sys.exit("vanilla game folder not found: pass --game or set HOI4_DIR")


# ---------------------------------------------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------------------------------------------
def norm_key(key):
    """Module / manifest key -> 'path/relative/to/gfx/interface.dds' or 'gfx/minimap/...'."""
    k = str(key).replace("\\", "/").lstrip("./")
    if k.lower().startswith("gfx/interface/"):
        k = k[len("gfx/interface/"):]
    return k


def rel_file(key):
    """Key -> path relative to the game / mod root."""
    return key if key.lower().startswith("gfx/") else "gfx/interface/" + key


def check_key(key):
    rf = rel_file(key).lower()
    if not (rf.startswith("gfx/interface/") or rf.startswith("gfx/minimap/")):
        raise ValueError(f"{key}: only gfx/interface/** and gfx/minimap/** are produced here")
    if rf.startswith("gfx/interface/totu/"):
        raise ValueError(f"{key}: gfx/interface/totu/** belongs to the frontend builders")
    if ".." in rf.split("/"):
        raise ValueError(f"{key}: '..' is not allowed")
    if Path(rf).suffix not in (".dds", ".png", ".tga"):
        raise ValueError(f"{key}: unsupported texture type")


def real_case(base, rel):
    """rel (posix) resolved case-insensitively under base -> the on-disk spelling, or None."""
    cur = base
    parts = []
    for comp in rel.split("/"):
        try:
            names = os.listdir(cur)
        except OSError:
            return None
        hit = next((n for n in names if n == comp), None) or next((n for n in names if n.lower() == comp.lower()),
                                                                     None)
        if hit is None:
            return None
        parts.append(hit)
        cur = cur / hit
    return "/".join(parts)


# ---------------------------------------------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------------------------------------------
def import_manifest(src):
    full = json.loads(Path(src).read_text(encoding="utf-8"))
    slim = [{k: e[k] for k in KEEP_FIELDS if k in e} for e in sorted(full, key=lambda e: e["texture"].lower())]
    DATA.mkdir(parents=True, exist_ok=True)
    text = "[\n" + ",\n".join(json.dumps(e, ensure_ascii=True, separators=(",", ":")) for e in slim) + "\n]\n"
    MANIFEST.write_text(text, encoding="utf-8", newline="\n")
    live = sum(e["scope"] in LIVE_SCOPES for e in slim)
    print(f"manifest: {len(slim)} textures ({live} live) -> {MANIFEST.relative_to(ROOT).as_posix()}, "
          f"{MANIFEST.stat().st_size / 1e6:.2f} MB")


def load_manifest():
    if not MANIFEST.exists():
        sys.exit(f"{MANIFEST} missing: run --import-manifest PATH first")
    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {norm_key(e["texture"]): e for e in entries}


def is_live(key, entry):
    return entry["scope"] in LIVE_SCOPES or key.lower() in EXTRA_LIVE


def live_keys(manifest):
    return sorted((k for k, e in manifest.items() if is_live(k, e)), key=str.lower)


# ---------------------------------------------------------------------------------------------------------------
# Dark text hosts: textures a vanilla (or mod-overridden) .gui draws dark text on. Light vanilla surfaces under
# such text must stay light until the owning stream changes the text colour; everywhere else paper goes dark.
# ---------------------------------------------------------------------------------------------------------------
DARK_FONTS = {"hoi4_typewriter16", "hoi4_typewriter22", "main_14_black", "vic_18_black", "vic_36_black"}
TEXT_TYPES = {"instanttextboxtype", "textboxtype", "edittextboxtype"}
BUTTON_TYPES = {"buttontype", "guibuttontype", "checkboxtype"}


def _tokens(text):
    import re   # noqa: PLC0415
    for m in re.finditer(r'"[^"]*"|[{}=]|[^\s{}="#]+|#[^\n]*', text):
        t = m.group(0)
        if not t.startswith("#"):
            yield t


def _parse(text):
    toks = list(_tokens(text))
    i = 0

    def block():
        nonlocal i
        items = []
        while i < len(toks):
            t = toks[i]
            if t == "}":
                i += 1
                return items
            if i + 1 < len(toks) and toks[i + 1] == "=":
                key = t.lower()
                i += 2
                if i < len(toks) and toks[i] == "{":
                    i += 1
                    items.append((key, block()))
                else:
                    items.append((key, toks[i].strip('"') if i < len(toks) else None))
                    i += 1
            elif t == "{":
                i += 1
                items.append((None, block()))
            else:
                i += 1
        return items
    return block()


def _get(items, key):
    for k, v in items:
        if k == key:
            return v
    return None


def _sprites_of(items):
    out = []
    for k in ("spritetype", "quadtexturesprite"):
        v = _get(items, k)
        if isinstance(v, str):
            out.append(v.lower())
    return out


def _is_dark(items, font_key):
    f = _get(items, font_key)
    code = _get(items, "text_color_code")
    return (isinstance(f, str) and f.lower() in DARK_FONTS) or code == "b"


def _walk_dark(items, hits):
    """Mark the sprites dark text is drawn on: a container with dark text directly in it, or in a child container
    that has no (or a transparent) background of its own, hosts it on its background and its icon sprites;
    buttons with a dark buttonFont host it themselves. Returns True when dark text shows through this container
    (it has no opaque background of its own). Over-marking is safe: it only keeps light surfaces light."""
    dark_here = False
    icons, bg = [], []
    for k, v in items:
        if not isinstance(v, list):
            continue
        if k in TEXT_TYPES and _is_dark(v, "font"):
            dark_here = True
        elif k in BUTTON_TYPES:
            if _is_dark(v, "buttonfont"):
                hits.update(_sprites_of(v))
            icons += _sprites_of(v)
        elif k == "icontype":
            icons += _sprites_of(v)
        elif k == "background":
            bg += _sprites_of(v)
        if k is None or k.endswith("type") or k == "guitypes":
            if _walk_dark(v, hits):
                dark_here = True
    if dark_here:
        hits.update(bg)
        hits.update(icons)
    covered = any("transparent" not in s for s in bg)
    return dark_here and not covered


def dark_text_hosts(game, manifest):
    """-> set of manifest keys a .gui draws dark text on (vanilla .gui files, the mod's copy where it has one)."""
    guis = {}
    for base in (game / "interface", ROOT / "interface"):
        for p in base.rglob("*.gui"):
            guis[p.relative_to(base).as_posix().lower()] = p
    sprites = set()
    for p in guis.values():
        try:
            _walk_dark(_parse(p.read_text(encoding="utf-8-sig", errors="replace")), sprites)
        except RecursionError:
            continue
    by_sprite = {}
    for k, e in manifest.items():
        for s in e.get("sprites") or []:
            by_sprite.setdefault(s.lower(), set()).add(k)
    out = set()
    for s in sprites:
        out |= by_sprite.get(s, set())
    return out


def annotate(manifest, dark):
    """Inject what generic.py and Ctx read into the manifest entries:
    dark_text      True (a .gui draws dark text on it), False (a .gui uses it, none with dark text), None (no .gui:
                   engine / script sprites, unknown);
    sibling_state  for live textures that differ from another live texture only by a state word
                   (enabled / disabled, available / locked, ...): their state, so each state gets its own tone."""
    import re   # noqa: PLC0415
    words = "|".join(rx for _, rx in generic.STATE_WORDS)
    rx = re.compile(r"(^|_)(" + words + r")(?=_|\.)")
    groups = {}
    for k, e in manifest.items():
        e["dark_text"] = True if k in dark else (False if e.get("guis") else None)
        e.pop("sibling_state", None)
        if is_live(k, e):
            base = rx.sub(r"#", k.lower())
            if base != k.lower():
                groups.setdefault(base, []).append(k)
    for keys in groups.values():
        states = {generic.state_of(k) for k in keys}
        if len(keys) >= 2 and len(states) >= 2:
            for k in keys:
                manifest[k]["sibling_state"] = generic.state_of(k)


# ---------------------------------------------------------------------------------------------------------------
# Owner rules (first match wins). Each rule: (rule id, area, predicate(key, entry)). Deterministic: depends only on
# the manifest. Re-run with --owners after changing them.
# ---------------------------------------------------------------------------------------------------------------
TOPBAR_GUIS = {"topbar.gui", "ingameclock.gui", "minimap.gui", "mapmodes_interface.gui", "alerts.gui",
               "menubar.gui"}
# the rest of the HUD on the map: battle plans, the army-group panel (outliner), theatre selector
HUD_GUIS = TOPBAR_GUIS | {"battleplantools.gui", "leadergroups.gui", "theatreselector.gui"}
RULES_GUIS = {"savedgamerules.gui"}
MP_GUIS = {"frontendmultiplayerview.gui", "matchmaking.gui", "matchmaking_chat.gui", "playerlobby.gui",
           "hotjoin.gui", "chat.gui", "ingamelobby.gui"}
MISC_GUIS = {"achievements.gui", "musicplayer.gui", "music_station_base.gui", "music_station_classic.gui",
             "credits.gui", "frontendcreditview.gui", "subscription_message_view.gui", "browser.gui",
             "social_view.gui", "frontend_friends_view.gui", "pops_login.gui"}
MISC_GUI_DIRS = ("career_profile/", "pdx_online/")
TREE_GUIS = {"nationalfocusview.gui", "countrytechtreeview.gui", "countrydecisionview.gui",
             "countrydoctrinetreeview.gui", "doctrines/doctrines_view.gui", "traittreewindow_common.gui"}
KIT_CLASSES = {"button", "checkbox", "scrollbar", "slider", "dropdown", "tab", "textfield", "tooltip",
               "tiled_window", "frame"}
VIEW_CLASSES = {"view_bg", "panel_bg", "list_entry", "header", "bar", "separator", "frame"}


def _guis(e):
    return set((e or {}).get("guis") or {})


def _only(e, allowed, dirs=(), suffix=None):
    """Used by at least one .gui and only by guis in `allowed` (or under `dirs`, or ending with `suffix`)."""
    g = _guis(e)
    return bool(g) and all(x in allowed or x.startswith(dirs) or (suffix and x.endswith(suffix)) for x in g)


def _base(k):
    return k.rsplit("/", 1)[-1].lower()


def _starts(k, *prefixes):
    return k.lower().startswith(prefixes)


OWNER_RULES = [
    ("events:eventwindow.gfx", "events", lambda k, e: "interface/eventwindow.gfx" in (e.get("defined_in") or [])),
    ("events:gui-only", "events", lambda k, e: _only(e, {"eventwindow.gui"})),
    ("events:folder", "events", lambda k, e: _starts(k, "events/")),
    ("events:name", "events", lambda k, e: "/" not in k and _base(k).startswith("event_")),   # root event_*.dds
    ("topbar:folder", "topbar", lambda k, e: _starts(k, "topbar/", "alerts/", "mapmode/", "gfx/minimap/")),
    ("topbar:class", "topbar", lambda k, e: e.get("class") in ("minimap", "menubar", "topbar")),
    ("topbar:name", "topbar", lambda k, e: _base(k).startswith(("ingameclock_bg", "date_pause_button",
                                                                 "world_tension_icon_big_strip", "wt_anim_strip",
                                                                 "reopen_lobby"))
     or _starts(k, "decisionview/decisions_glow")),
    ("topbar:gui-only", "topbar", lambda k, e: _only(e, TOPBAR_GUIS)),
    # HUD on the map (the topbar / HUD stream): army-group panel, battle plans, unit control, theatre selector
    ("topbar:hud-class", "topbar", lambda k, e: e.get("class") == "outliner"),
    ("topbar:hud-folder", "topbar", lambda k, e: _starts(k, "unitcontrol/")),
    ("topbar:hud-gui-only", "topbar", lambda k, e: _only(e, HUD_GUIS)),
    # game rules: saved rule presets and the mod's game-rule / difficulty windows
    ("rules:extra", "rules", lambda k, e: k.lower() in EXTRA_LIVE),
    ("rules:gui-only", "rules", lambda k, e: _only(e, RULES_GUIS)),
    ("esc:gui-only", "esc", lambda k, e: _only(e, {"ingamemenu.gui"})),
    ("esc:name", "esc", lambda k, e: _base(k).startswith(("load_save_", "save_load_file_", "no_frame_special_bg",
                                                           "in_game_menu_dark_overlay"))),
    ("settings:gui-only", "settings", lambda k, e: _only(e, {"settings.gui"})),
    ("settings:name", "settings", lambda k, e: _base(k).startswith(("settings_popup_bg", "tab_small_110",
                                                                     "fullborder_tiled"))),
    ("popups:popupwindow.gfx", "popups", lambda k, e: "interface/popupwindow.gfx" in (e.get("defined_in") or [])
     and not _starts(k, "tiles/")),
    ("popups:name", "popups", lambda k, e: _base(k).startswith("diplo_popup_")),
    ("popups:folder", "popups", lambda k, e: _starts(k, "notifications/")),
    ("popups:gui-only", "popups", lambda k, e: _only(e, {"popupwindow.gui"}, dirs=("notifications/",))),
    ("mp:gui-only", "mp", lambda k, e: _only(e, MP_GUIS)),
    ("misc:folder", "misc", lambda k, e: _starts(k, "career_profile/")),
    ("misc:name", "misc", lambda k, e: _base(k).startswith("music_station_")),
    ("misc:gui-only", "misc", lambda k, e: _only(e, MISC_GUIS, dirs=MISC_GUI_DIRS)),
    ("trees:folder", "trees", lambda k, e: _starts(k, "focusview/", "techtree/", "decisionview/", "doctrines/",
                                                   "trait_window/") or k.lower() == "tiles/tiled_focus_bg.dds"),
    ("trees:gui-only", "trees", lambda k, e: _only(e, TREE_GUIS, suffix="traittreewindow.gui")),
    ("kit:tiles", "kit", lambda k, e: _starts(k, "tiles/")),
    ("kit:3+guis", "kit", lambda k, e: len(_guis(e)) >= 3),
    ("kit:root-class", "kit", lambda k, e: "/" not in k and e.get("class") in KIT_CLASSES),
    ("views:class", "views", lambda k, e: e.get("class") in VIEW_CLASSES and e.get("scope") != "menu"),
    # what is left: per-view folders (naviesview/, operations/, ...) belong to the views stream, root-folder
    # parts shared by views to the kit
    ("views:folder", "views", lambda k, e: "/" in k and e.get("scope") != "menu"),
    ("kit:root", "kit", lambda k, e: "/" not in k and e.get("scope") != "menu"),
    ("generic:rest", "generic", lambda k, e: True),
]
assert [a for a in dict.fromkeys(r[1] for r in OWNER_RULES)] == list(AREAS), "rule order must match AREAS"


def owner_of(key, entry):
    for rid, area, pred in OWNER_RULES:
        if pred(key, entry or {}):
            return area, rid
    return "generic", "generic:rest"


def compute_owners(manifest):
    return {k: owner_of(k, manifest[k]) for k in live_keys(manifest)}


def write_owners(manifest, owners, extra=None):
    by_area = {a: sorted((k for k, (o, _) in owners.items() if o == a), key=str.lower) for a in AREAS}
    stats = {a: {"count": len(v), "mb": round(sum(manifest[k]["bytes"] for k in v) / 1e6, 2)}
             for a, v in by_area.items()}
    doc = {
        "_doc": "Generated by tools/build_ingame_gfx.py (--owners or a full run) from tools/data/chrome_manifest"
                ".json with OWNER_RULES (first match wins). Every live texture (scopes " + ", ".join(LIVE_SCOPES) +
                ", plus EXTRA_LIVE) has exactly one owner area; mb = vanilla bytes. dark_text_hosts: textures a "
                ".gui draws dark text on (light surfaces stay light there). After a full run: generic_modes (mode "
                "of every generically produced texture) and paper (outputs that kept a light paper surface because "
                "dark vanilla text sits on them: the owning stream must change that text colour in its .gui, then "
                "re-tone, e.g. ctx.generic(src, tones=('raised',))). Do not edit; change the rules instead.",
        "live_scopes": list(LIVE_SCOPES),
        "extra_live": list(EXTRA_LIVE),
        "rules": [f"{rid} -> {area}" for rid, area, _ in OWNER_RULES],
        "areas": stats,
        "owners": {k: owners[k][0] for k in sorted(owners, key=str.lower)},
        "rule_of": {k: owners[k][1] for k in sorted(owners, key=str.lower)},
        "by_area": by_area,
        "dark_text_hosts": sorted((k for k in owners if manifest[k].get("dark_text") is True), key=str.lower),
    }
    if OWNERS.exists() and extra is None:      # keep the last full run's results
        try:
            old = json.loads(OWNERS.read_text(encoding="utf-8"))
            for key in ("generic_modes", "paper"):
                if key in old:
                    doc[key] = old[key]
        except (OSError, ValueError):
            pass
    doc.update(extra or {})
    OWNERS.write_text(json.dumps(doc, indent=1, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")
    return stats


def print_owner_stats(manifest, owners):
    print(f"{'area':10} {'count':>6} {'vanilla MB':>11}   rules hit")
    total_n = total_b = 0
    for a in AREAS:
        ks = [k for k, (o, _) in owners.items() if o == a]
        b = sum(manifest[k]["bytes"] for k in ks)
        rules = {}
        for k in ks:
            rules[owners[k][1]] = rules.get(owners[k][1], 0) + 1
        total_n += len(ks)
        total_b += b
        print(f"{a:10} {len(ks):6} {b / 1e6:11.2f}   " + ", ".join(f"{r.split(':', 1)[1]} {n}"
                                                                    for r, n in rules.items()))
    print(f"{'total':10} {total_n:6} {total_b / 1e6:11.2f}")


# ---------------------------------------------------------------------------------------------------------------
# Area modules
# ---------------------------------------------------------------------------------------------------------------
def module_names():
    d = TOOLS / "ingame"
    return sorted(p.stem for p in d.glob("*.py") if not p.stem.startswith("_") and p.stem != "generic")


def check_areas(names, what):
    """Validate area names given on the command line."""
    valid = set(AREAS) | set(module_names())
    bad = sorted(set(names) - valid)
    if bad:
        sys.exit(f"{what}: unknown area {', '.join(bad)}; valid: {', '.join(list(AREAS) + sorted(valid - set(AREAS)))}")


def load_modules(names, strict, wanted_areas=None):
    """Import area modules. Returns (modules dict name -> module, broken dict name -> error text). A broken module
    is fatal when strict or when its area is wanted."""
    mods, broken = {}, {}
    for n in names:
        try:
            m = importlib.import_module(f"ingame.{n}")
            area = getattr(m, "AREA", None)
            if area != n:
                raise ValueError(f"AREA = {area!r} must equal the file name {n!r}")
            if not isinstance(getattr(m, "TEXTURES", None), dict):
                raise ValueError("TEXTURES must be a dict {path: fn}")
            mods[n] = m
        except Exception:   # noqa: BLE001
            err = traceback.format_exc(limit=3)
            if strict or (wanted_areas is not None and n in wanted_areas):
                sys.exit(f"area module tools/ingame/{n}.py failed to load:\n{err}")
            broken[n] = err.strip().splitlines()[-1]
    return mods, broken


@dataclass
class Job:
    key: str
    area: str             # area that produces it (claiming module, else the owner)
    owner: str            # owner by the rules (generic for non-manifest claims)
    producer: str         # module name or "generic"
    entry: dict
    lossless: bool = False

    @property
    def rel(self):
        return rel_file(self.key)


def transparencecheck_textures(game):
    """Keys (lower case, relative to gfx/interface or gfx/minimap like the manifest) of every texture that a sprite with
    transparencecheck = yes uses, in vanilla and in the mod's interface files."""
    files = list((Path(game) / "interface").rglob("*.gfx")) + list((ROOT / "interface").glob("*.gfx"))
    out = set()
    for f in files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r"\{([^{}]*transparencecheck\s*=\s*yes[^{}]*)\}", text, re.I):
            t = re.search(r'texturefile\s*=\s*"([^"]+)"', m.group(1), re.I)
            if not t:
                continue
            p = t.group(1).replace("\\", "/").lower()
            p = re.sub(r"/+", "/", p)
            if p.endswith(".tga"):
                p = p[:-4] + ".dds"
            for prefix in ("gfx/interface/", "gfx/minimap/"):
                if p.startswith(prefix):
                    out.add(p[len("gfx/interface/"):] if prefix == "gfx/interface/" else p)
    return out


def resolve_jobs(manifest, owners, mods, game, notes):
    """Every live texture plus module extras -> {key: Job}; also returns {key: fn}. Asserts single claimers."""
    lower = {k.lower(): k for k in manifest}
    claims, fns, lossless = {}, {}, set()
    for name, m in mods.items():
        ll = {norm_key(x).lower() for x in getattr(m, "LOSSLESS", ()) or ()}
        for raw, fn in m.TEXTURES.items():
            k = norm_key(raw)
            check_key(k)
            if not callable(fn):
                raise TypeError(f"tools/ingame/{name}.py: TEXTURES[{raw!r}] is not callable")
            canon = lower.get(k.lower())
            if canon is None:
                rc = real_case(game, rel_file(k))
                if rc is None:
                    raise FileNotFoundError(f"tools/ingame/{name}.py claims {raw!r}: no such vanilla file")
                canon = norm_key(rc)
                notes.append(f"note: {name} claims {canon}, which is not in the chrome manifest: make sure it is "
                             f"chrome, not content (icons, portraits, flags keep their colours)")
            elif not is_live(canon, manifest[canon]):
                notes.append(f"note: {name} claims {canon} (manifest scope {manifest[canon]['scope']}, not live)")
            if canon in claims:
                raise AssertionError(f"{canon} is claimed by both {claims[canon]} and {name}")
            claims[canon] = name
            fns[canon] = fn
            if k.lower() in ll:
                lossless.add(canon)
    # The engine refuses DXT for sprites with transparencecheck = yes ("forbidden compression, have you tried DXT3?",
    # error.log, naval_battle_bg2): keep every texture such a sprite uses uncompressed.
    tc = transparencecheck_textures(game)
    lossless |= {k for k in list(manifest) + list(claims) if k.lower() in tc}
    jobs = {}
    for k in live_keys(manifest):
        owner = owners[k][0]
        prod = claims.get(k, "generic")
        jobs[k] = Job(k, prod if prod != "generic" else owner, owner, prod, manifest[k], k in lossless)
    for k, name in claims.items():
        if k not in jobs:
            jobs[k] = Job(k, name, owners.get(k, ("generic",))[0], name, manifest.get(k), k in lossless)
    for k, j in jobs.items():
        if j.producer != "generic" and j.owner != j.area and k in owners:
            notes.append(f"warn: {k} is owned by {j.owner} (ingame_owners.json) but claimed by {j.producer}")
    return jobs, fns


def select_jobs(jobs, only=None, generic_only=False, patterns=None, areas_any=None):
    out = []
    for k, j in sorted(jobs.items(), key=lambda kv: kv[0].lower()):
        if only is not None and j.area not in only:
            continue
        if generic_only and j.producer != "generic":
            continue
        if areas_any is not None and j.area not in areas_any and j.owner not in areas_any:
            continue
        if patterns and not any(fnmatch.fnmatch(k.lower(), p.lower()) for p in patterns):
            continue
        out.append(j)
    return out


# ---------------------------------------------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------------------------------------------
def choose_format(ext, w, h, lossless, dxt_odd=DXT_ODD_SIZES, force=None):
    """force: ctx.dxt of a module fn (True = DXT5 regardless of size, False = uncompressed)."""
    if ext == ".png":
        return "PNG"
    if ext == ".tga":
        return "TGA"
    if force is False or lossless:
        return "A8R8G8B8"
    if force is True:
        return "DXT5"
    if w * h >= DXT_MIN_PX and (dxt_odd or (w % 4 == 0 and h % 4 == 0)):
        return "DXT5"
    return "A8R8G8B8"


def _fix_dxt_header(data, w, h):
    """Pillow's DXT5 header has a row pitch in dwPitchOrLinearSize and 32 in dwRGBBitCount; vanilla DXT files carry
    the top-level linear size and 0 (DDSD_LINEARSIZE is set). Write them the vanilla way."""
    b = bytearray(data)
    struct.pack_into("<I", b, 20, ((w + 3) // 4) * ((h + 3) // 4) * 16)
    struct.pack_into("<I", b, 88, 0)
    return bytes(b)


def encode(img, fmt):
    buf = io.BytesIO()
    if fmt == "DXT5":
        img.save(buf, format="DDS", pixel_format="DXT5")
        return _fix_dxt_header(buf.getvalue(), img.width, img.height)
    elif fmt == "A8R8G8B8":
        img.save(buf, format="DDS")
    elif fmt == "PNG":
        img.save(buf, format="PNG")
    elif fmt == "TGA":
        img.save(buf, format="TGA")
    else:
        raise ValueError(fmt)
    return buf.getvalue()


def dds_info(data):
    """(w, h, format, mips) of DDS bytes; format is the FourCC or A8R8G8B8 / RGB<bits>."""
    if data[:4] != b"DDS ":
        return None
    h, w = struct.unpack("<II", data[12:20])
    mips = struct.unpack("<I", data[28:32])[0]
    pfflags, fourcc, bits = struct.unpack("<I4sI", data[80:92])
    if pfflags & 0x4:
        fmt = fourcc.decode("latin-1")
    elif bits == 32 and pfflags & 0x1:
        fmt = "A8R8G8B8"
    else:
        fmt = f"RGB{bits}"
    return w, h, fmt, mips


def write_atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def read_outputs():
    """{path from the mod root: producer} of every texture the pipeline wrote (producer '' for old lines)."""
    if not OUTPUTS.exists():
        return {}
    out = {}
    for ln in OUTPUTS.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        path, _, prod = ln.partition("\t")
        out[path.strip()] = prod.strip()
    return out


def write_outputs(paths):
    head = ("# Generated by tools/build_ingame_gfx.py: every texture it wrote into the mod (path from the mod root,"
            " TAB, producer: generic or the area module).\n# A full run deletes listed files it no longer produces"
            " (never unlisted files). Do not edit.\n")
    OUTPUTS.write_text(head + "".join(f"{p}\t{paths[p]}\n" for p in sorted(paths, key=str.lower)),
                       encoding="utf-8", newline="\n")


def pid_alive(pid):
    """True when a process with this pid exists (never signals it: os.kill on Windows would terminate it)."""
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes   # noqa: PLC0415
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(0x1000, False, pid)        # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return k32.GetLastError() == 5             # access denied: it exists
        code = ctypes.c_ulong()
        ok = k32.GetExitCodeProcess(h, ctypes.byref(code))
        k32.CloseHandle(h)
        return bool(ok) and code.value == 259          # STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class OutputsLock:
    """Cross-process lock around read-modify-write of ingame_outputs.txt (stream agents run --only in parallel).
    The lock file holds the owner's pid; a lock whose process is gone is broken at once."""

    def __enter__(self):
        t0 = time.time()
        while True:
            try:
                self.fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self.fd, str(os.getpid()).encode())
                return self
            except FileExistsError:
                try:
                    pid = int((LOCK.read_text(encoding="ascii").strip() or "0"))
                except (OSError, ValueError):
                    pid = 0
                stale = (pid and not pid_alive(pid)) or (not pid and time.time() - LOCK.stat().st_mtime > 30)
                if stale:
                    try:
                        LOCK.unlink()
                        print(f"note: removed a stale lock (pid {pid or '?'} is gone)")
                    except OSError:
                        pass
                    continue
                if time.time() - t0 > 120:
                    sys.exit(f"could not lock {LOCK} for 120 s (held by pid {pid})")
                time.sleep(0.2)

    def __exit__(self, *exc):
        os.close(self.fd)
        try:
            LOCK.unlink()
        except OSError:
            pass


def safe_delete(rel):
    """Delete one generated file: only real files under the mod's gfx/interface or gfx/minimap, never under
    gfx/interface/totu, never through '..' or links."""
    gfx = (ROOT / "gfx").resolve()
    totu = (ROOT / "gfx" / "interface" / "totu").resolve()
    p = (ROOT / rel)
    try:
        rp = p.resolve()
    except OSError:
        return False
    r = rel.replace("\\", "/").lower()
    if ".." in r.split("/") or not r.startswith(("gfx/interface/", "gfx/minimap/")):
        print(f"warn: refusing to delete {rel} (outside gfx/interface, gfx/minimap)")
        return False
    if not rp.is_relative_to(gfx) or rp.is_relative_to(totu) or p.is_symlink():
        print(f"warn: refusing to delete {rel} (resolves outside the generated folders)")
        return False
    if rp.is_file():
        rp.unlink()
        return True
    return False


# ---------------------------------------------------------------------------------------------------------------
# Worker (runs in child processes; also used in-process with --jobs 1)
# ---------------------------------------------------------------------------------------------------------------
_W = {}


def _worker_init(cfg):
    sys.path.insert(0, str(TOOLS))
    game = Path(cfg["game"])
    manifest = load_manifest()
    dark = set(cfg["dark"])
    annotate(manifest, dark)
    owners = compute_owners(manifest)
    mods, _ = load_modules(cfg["modules"], strict=True)
    jobs, fns = resolve_jobs(manifest, owners, mods, game, [])
    _W.update(cfg=cfg, game=game, manifest=manifest, jobs=jobs, fns=fns, font=None)


def _load_vanilla(key):
    return Image.open(_W["game"] / rel_file(norm_key(key))).convert("RGBA")


def _produce(job):
    """-> (src, result image or None, mode text, ctx, paper flag)"""
    game = _W["game"]
    vpath = game / job.rel
    src = Image.open(vpath).convert("RGBA")
    e = job.entry or {}
    if e and (src.width, src.height) != (e["w"], e["h"]):
        raise AssertionError(f"vanilla size {src.size} != manifest {(e['w'], e['h'])}: refresh the manifest")
    frames = int(e.get("frames") or 1)
    borders = [tuple(int(float(v)) for v in b) for b in (e.get("border") or []) if len(b) == 2]
    ctx = generic.Ctx(path=job.key, entry=job.entry, vanilla_path=vpath, out_path=ROOT / job.rel, area=job.area,
                      owner=job.owner, w=src.width, h=src.height, frames=frames,
                      frame_w=src.width // frames if src.width % frames == 0 else src.width,
                      border=borders[0] if borders else None, borders=borders, cls=e.get("class"),
                      lossless=job.lossless, _loader=_load_vanilla)
    paper = False
    if job.producer == "generic":
        out, opts = generic.treat(src, job.key, job.entry)
        mode, paper = opts.mode, opts.paper
    else:
        out = _W["fns"][job.key](ctx, src.copy())
        mode = "module"
    if out is not None:
        if not isinstance(out, Image.Image):
            raise TypeError(f"{job.producer} returned {type(out).__name__}, not a PIL image")
        out = out.convert("RGBA") if out.mode != "RGBA" else out
        if out.size != src.size:
            raise AssertionError(f"result size {out.size} != vanilla {src.size}")
        if np.array_equal(np.asarray(out), np.asarray(src)):
            out, mode = None, mode + "=vanilla"
    return src, out, mode, ctx, paper


def _worker_build(key):
    job = _W["jobs"][key]
    res = {"key": key, "rel": job.rel, "area": job.area, "owner": job.owner, "producer": job.producer}
    try:
        src, out, mode, ctx, paper = _produce(job)
        res.update(mode=mode, paper=paper, warnings=ctx.warnings, vmips=(job.entry or {}).get("mips", 1))
        if out is None:
            res["status"] = "keep"
            return res
        fmt = choose_format(Path(job.rel).suffix.lower(), out.width, out.height, ctx.lossless or job.lossless,
                            _W["cfg"]["dxt_odd"], ctx.dxt)
        data = encode(out, fmt)
        if fmt in ("DXT5", "A8R8G8B8"):
            info = dds_info(data)
            assert info and info[:2] == out.size and info[3] <= 1, (key, info)
        write_atomic(ROOT / job.rel, data)
        res.update(status="written", fmt=fmt, bytes=len(data))
    except Exception:   # noqa: BLE001
        res.update(status="error", error=traceback.format_exc(limit=4))
    return res


PANE_W, PANE_H, GAP, LABEL_H = 300, 168, 8, 30


def _font():
    if _W.get("font") is None:
        try:
            _W["font"] = ImageFont.load_default(size=12)
        except Exception:   # noqa: BLE001
            _W["font"] = ImageFont.load_default()
    return _W["font"]


def _pane(img, frames):
    if img.width > 1500 and frames > 1 and img.width % frames == 0:
        fw = img.width // frames
        img = img.crop((0, 0, fw * min(frames, 3), img.height))
    s = min(PANE_W / img.width, PANE_H / img.height)
    if s >= 2:
        s = int(min(s, 6))
        img = img.resize((img.width * s, img.height * s), Image.NEAREST)
    elif s < 1:
        img = img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))), Image.LANCZOS)
    pane = _backdrop().copy()
    pane.alpha_composite(img, (0, 0))
    return pane


def _backdrop():
    """Board with a mid-tone checker (stand-in for the map), so flat dark panels and their alpha stay visible."""
    if _W.get("backdrop") is None:
        y, x = np.mgrid[0:PANE_H, 0:PANE_W]
        chk = ((x // 16 + y // 16) % 2).astype(bool)
        arr = np.empty((PANE_H, PANE_W, 4), np.uint8)
        arr[...] = generic.BOARD + (255,)
        arr[chk] = (52, 58, 70, 255)
        _W["backdrop"] = Image.fromarray(arr, "RGBA")
    return _W["backdrop"]


def _worker_preview(key):
    job = _W["jobs"][key]
    try:
        src, out, mode, ctx, paper = _produce(job)
        fmt = "vanilla"
        if out is not None:
            fmt = choose_format(Path(job.rel).suffix.lower(), out.width, out.height, ctx.lossless or job.lossless,
                                _W["cfg"]["dxt_odd"], ctx.dxt)
            if fmt == "DXT5":
                out = Image.open(io.BytesIO(encode(out, fmt))).convert("RGBA")
        e = job.entry or {}
        frames = int(e.get("frames") or 1)
        cell = Image.new("RGB", (2 * PANE_W + 3 * GAP, PANE_H + LABEL_H + GAP), (44, 46, 52))
        cell.paste(_pane(src, frames).convert("RGB"), (GAP, LABEL_H))
        cell.paste(_pane(out if out is not None else src, frames).convert("RGB"), (2 * GAP + PANE_W, LABEL_H))
        d = ImageDraw.Draw(cell)
        f = _font()
        d.text((GAP, 2), key[:92], fill=(246, 242, 234), font=f)
        line2 = (f"{src.width}x{src.height} f{frames} {e.get('class') or '-'}  |  {job.area}/{job.producer}:{mode}"
                 f"{' paper' if paper else ''}  |  {fmt}")
        d.text((GAP, 15), line2[:100], fill=(172, 180, 196), font=f)
        buf = io.BytesIO()
        cell.save(buf, format="PNG")
        return {"key": key, "status": "ok", "png": buf.getvalue(), "warnings": ctx.warnings}
    except Exception:   # noqa: BLE001
        return {"key": key, "status": "error", "error": traceback.format_exc(limit=4)}


def _worker_list(key):
    """Generic mode of one job (for --list)."""
    job = _W["jobs"][key]
    if job.producer != "generic":
        return key, "module", ""
    try:
        src = Image.open(_W["game"] / job.rel).convert("RGBA")
        o = generic.mode_for(job.key, job.entry, src)
        return key, o.mode, o.why
    except Exception as ex:   # noqa: BLE001
        return key, "error", str(ex)


def run_pool(fn, keys, cfg, workers):
    keys = list(keys)
    if workers <= 1 or len(keys) < 8:
        _worker_init(cfg)
        return [fn(k) for k in keys]
    with ProcessPoolExecutor(max_workers=workers, initializer=_worker_init, initargs=(cfg,)) as ex:
        return list(ex.map(fn, keys, chunksize=2))


# ---------------------------------------------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------------------------------------------
def sizes_report(manifest, owners, jobs):
    outs = read_outputs()
    rows = {}
    total = 0
    for rel in outs:
        p = ROOT / rel
        if not p.is_file():
            continue
        key = norm_key(rel)
        area = jobs[key].area if key in jobs else owners.get(key, ("generic",))[0]
        data = p.read_bytes()[:128]
        info = dds_info(data)
        fmt = info[2] if info else p.suffix.upper().lstrip(".")
        n = p.stat().st_size
        r = rows.setdefault(area, {})
        c = r.setdefault(fmt, [0, 0])
        c[0] += 1
        c[1] += n
        total += n
    print(f"{'area':10} {'format':9} {'files':>6} {'MB':>8}")
    for a in list(AREAS) + sorted(set(rows) - set(AREAS)):
        if a not in rows:
            continue
        for fmt, (cnt, n) in sorted(rows[a].items()):
            print(f"{a:10} {fmt:9} {cnt:6} {n / 1e6:8.2f}")
        print(f"{a:10} {'all':9} {sum(v[0] for v in rows[a].values()):6} "
              f"{sum(v[1] for v in rows[a].values()) / 1e6:8.2f}")
    fmts = {}
    for r in rows.values():
        for fmt, (cnt, n) in r.items():
            fmts.setdefault(fmt, [0, 0])
            fmts[fmt][0] += cnt
            fmts[fmt][1] += n
    for fmt, (cnt, n) in sorted(fmts.items()):
        print(f"{'TOTAL':10} {fmt:9} {cnt:6} {n / 1e6:8.2f}")
    print(f"{'TOTAL':10} {'all':9} {sum(v[0] for v in fmts.values()):6} {total / 1e6:8.2f}")


# semantic colour check: vanilla signal pixels (alpha > 0.5): red (hue -20..12, up to 20 in red-orange textures
# such as arrow_down / bop orange; s > 0.55, v > 0.45) or green (hue 85..170, s > 0.45, v > 0.3). Copper, bronze
# and leather (hue 12-30, darker) and vanilla's olive paint (hue 70-85) are decoration, not signals. Flattened
# panels turn a signal-coloured surface into a dark tint of the same hue by design: there only saturation counts.
SEM_MIN_SHARE = 0.02        # textures with at least this share of such opaque pixels are checked
SEM_SAT_KEEP = 0.6          # the output must keep at least this share of their mean saturation ...
SEM_VAL_KEEP = 0.5          # ... and of their mean value
SEM_EXEMPT_MODES = {"state", "keyer", "knob", "clear", "caption"}   # deliberate recolours (documented)
# painted art / decoration whose red is not a signal (checked by eye in the contact sheets)
SEM_EXEMPT = {
    "military_raids/raids_header_bg.dds": "red leather header plate (decoration)",
    "special_project/special_project_completed_popup_bg.dds": "painted illustration, flattened to a board",
}


def semantic_check(van, out):
    """-> None (not checked) or (share, sat ratio, value ratio) for one vanilla / output pair."""
    a = np.asarray(van.convert("RGBA"), np.float32) / 255.0
    b = np.asarray(out.convert("RGBA"), np.float32) / 255.0
    if a.shape != b.shape:
        return None
    h, s, v = generic.hue_sat_val(a[..., :3] * 255)
    hr = np.where(h > 180, h - 360, h)
    prof = generic.colour_profile(van)
    red_hi = 20 if (prof["warm_median"] is not None and prof["warm_median"] < 22) else 12
    red = (hr >= -20) & (hr <= red_hi) & (s > 0.55) & (v > 0.45)
    green = (h >= 85) & (h <= 170) & (s > 0.45) & (v > 0.3)
    m = (a[..., 3] > 0.5) & (red | green)
    op = (a[..., 3] > 0.5).sum()
    if op == 0 or m.sum() < 8 or m.sum() / op < SEM_MIN_SHARE:
        return None
    m &= b[..., 3] > 0.3
    if m.sum() < 8:
        return (float(m.sum() / op), 0.0, 0.0)
    _, s2, v2 = generic.hue_sat_val(b[..., :3] * 255)
    return float(m.sum() / op), float(s2[m].mean() / s[m].mean()), float(v2[m].mean() / v[m].mean())


def verify(game, jobs):
    """Every listed output: exists, same pixel size as vanilla, no mipmaps, a format the policy allows, decodes,
    and semantic red / green kept (generic outputs fail on a loss; module outputs are reported)."""
    outs = read_outputs()
    bad = 0
    fmts = {}
    sem_checked = sem_bad = 0
    for rel in sorted(outs, key=str.lower):
        p = ROOT / rel
        key = norm_key(rel)
        problems = []
        if not p.is_file():
            problems.append("missing")
        else:
            data = p.read_bytes()
            van = game / rel
            vw, vh = Image.open(van).size if van.is_file() else (None, None)
            info = dds_info(data[:128])
            if info:
                w, h, fmt, mips = info
                if mips > 1:
                    problems.append(f"{mips} mips")
                if fmt not in ("DXT5", "A8R8G8B8"):
                    problems.append(f"format {fmt}")
                if fmt == "DXT5" and (w % 4 or h % 4):
                    fmt = "DXT5odd"
            else:
                try:
                    w, h = Image.open(p).size
                except Exception:   # noqa: BLE001
                    w = h = None
                fmt = p.suffix.upper().lstrip(".")
            fmts[fmt] = fmts.get(fmt, 0) + 1
            if (w, h) != (vw, vh):
                problems.append(f"size {w}x{h} != vanilla {vw}x{vh}")
            try:
                im = Image.open(p)
                im.load()
            except Exception as e:   # noqa: BLE001
                im = None
                problems.append(f"does not decode: {e}")
            if key not in jobs:
                problems.append("no longer produced (a full run would delete it)")
            elif im is not None and van.is_file():
                job = jobs[key]
                vimg = Image.open(van).convert("RGBA")
                mode = "module"
                if job.producer == "generic":
                    mode = generic.mode_for(key, job.entry, vimg).mode
                r = None if (mode in SEM_EXEMPT_MODES or key.lower() in SEM_EXEMPT) else semantic_check(vimg, im)
                if r is not None:
                    sem_checked += 1
                    share, sr, vr = r
                    if sr < SEM_SAT_KEEP or (vr < SEM_VAL_KEEP and mode != "flatten"):
                        sem_bad += 1
                        msg = (f"semantic colour lost ({share:.0%} red/green px: saturation x{sr:.2f}, "
                               f"value x{vr:.2f}, {job.producer}:{mode})")
                        if job.producer == "generic":
                            problems.append(msg)
                        else:
                            print("NOTE", rel, msg)
        if problems:
            bad += 1
            print("BAD", rel, "; ".join(problems))
    print(f"verified {len(outs)} outputs: {bad} with problems; formats " +
          ", ".join(f"{k} {v}" for k, v in sorted(fmts.items())))
    print(f"semantic colour check: {sem_checked} outputs with >= {SEM_MIN_SHARE:.0%} strong red / green pixels, "
          f"{sem_bad} below saturation x{SEM_SAT_KEEP} or value x{SEM_VAL_KEEP} (modes "
          f"{', '.join(sorted(SEM_EXEMPT_MODES))} exempt)")
    return bad == 0


def list_area(jobs, area, patterns, cfg, workers):
    sel = select_jobs(jobs, areas_any={area}, patterns=patterns)
    modes = {k: (m, w) for k, m, w in run_pool(_worker_list, [j.key for j in sel], cfg, workers)} if sel else {}
    print(f"{'path':60} {'owner':8} {'producer':8} {'class':12} {'size':>10} {'fr':>3} {'vfmt':7} {'mips':>4} "
          f"{'mode':8} {'dark':4} why")
    for j in sel:
        e = j.entry or {}
        size = f"{e.get('w', '?')}x{e.get('h', '?')}"
        m, why = modes.get(j.key, ("?", ""))
        dark = {True: "yes", False: "no", None: "?"}[e.get("dark_text")]
        print(f"{j.key[:60]:60} {j.owner:8} {j.producer:8} {str(e.get('class') or '-'):12} {size:>10} "
              f"{e.get('frames', 1):>3} {str(e.get('fmt', '?')):7} {e.get('mips', '?'):>4} {m:8} {dark:4} {why}")
    print(f"{len(sel)} textures (mode: generic treatment; dark: a .gui draws dark text on it)")


# ---------------------------------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--only", help="comma-separated areas: build just the paths they produce")
    ap.add_argument("--generic-only", action="store_true", help="build just the paths no module claims")
    ap.add_argument("--paths", help="comma-separated fnmatch patterns (relative to gfx/interface) to restrict to")
    ap.add_argument("--list", metavar="AREA", help="print the job table of an area")
    ap.add_argument("--preview", metavar="AREA", help="contact sheets for an area, a comma list, or 'all'")
    ap.add_argument("--per-sheet", type=int, default=120)
    ap.add_argument("--sizes", action="store_true", help="size report of the generated textures")
    ap.add_argument("--verify", action="store_true",
                    help="check every listed output: size = vanilla, no mipmaps, allowed format, decodes, "
                         "semantic colours kept")
    ap.add_argument("--owners", action="store_true", help="rewrite tools/data/ingame_owners.json and print counts")
    ap.add_argument("--import-manifest", metavar="PATH")
    ap.add_argument("--game", default=None)
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--skip-broken", action="store_true",
                    help="full run: skip area modules that fail to import (their outputs stay, nothing is deleted)")
    ap.add_argument("--no-dxt-odd", action="store_true",
                    help="policy experiment: no DXT5 for sides that are not multiples of 4")
    ap.add_argument("--dxt-odd-sizes", action="store_true", help=argparse.SUPPRESS)   # old flag, now the default
    args = ap.parse_args()

    if args.import_manifest:
        import_manifest(args.import_manifest)
        return
    game = find_game(args.game)
    manifest = load_manifest()
    t_scan = time.time()
    dark = dark_text_hosts(game, manifest)
    annotate(manifest, dark)
    owners = compute_owners(manifest)
    for msg in generic.check_palette():
        print("warn: palette:", msg)
    patterns = [p.strip() for p in args.paths.split(",")] if args.paths else None
    only = {a.strip() for a in args.only.split(",") if a.strip()} if args.only else None
    if only:
        check_areas(only, "--only")
    if args.list:
        check_areas({args.list}, "--list")
    if args.preview and args.preview != "all":
        check_areas({a.strip() for a in args.preview.split(",")}, "--preview")
    partial = bool(only or args.generic_only or patterns)
    building = not (args.list or args.preview or args.sizes or args.owners or args.verify)
    full = building and not partial

    if args.owners or full:
        write_owners(manifest, owners)
        print_owner_stats(manifest, owners)
        print(f"wrote {OWNERS.relative_to(ROOT).as_posix()} ({len(dark)} dark-text hosts, scanned in "
              f"{time.time() - t_scan:.1f} s)")
        if args.owners and not building:
            return
    elif OWNERS.exists():
        saved = json.loads(OWNERS.read_text(encoding="utf-8")).get("owners", {})
        if saved != {k: v[0] for k, v in owners.items()}:
            print("warn: tools/data/ingame_owners.json is stale (rules or manifest changed): run --owners")

    wanted = only
    if args.preview and args.preview != "all":
        wanted = {a.strip() for a in args.preview.split(",")}
    mods, broken = load_modules(module_names(), strict=full and not args.skip_broken, wanted_areas=wanted)
    for n, err in broken.items():
        print(f"warn: skipped broken module tools/ingame/{n}.py ({err}); its paths are not rebuilt")
    notes = []
    jobs, _ = resolve_jobs(manifest, owners, mods, game, notes)
    for n in notes:
        print(n)
    if broken:
        # never regenerate paths a broken module might own: its area, and every path it produced last time
        # (ingame_outputs.txt records the producer, so claims outside its own area are protected too)
        prev_prod = read_outputs()
        protected = {norm_key(r) for r, prod in prev_prod.items() if prod in broken}
        jobs = {k: j for k, j in jobs.items() if j.area not in broken and k not in protected}
    cfg = {"game": str(game), "modules": sorted(mods), "dxt_odd": DXT_ODD_SIZES and not args.no_dxt_odd,
           "dark": sorted(dark)}

    if args.list:
        list_area(jobs, args.list, patterns, cfg, args.jobs)
        return
    if args.sizes:
        sizes_report(manifest, owners, jobs)
        return
    if args.verify:
        sys.exit(0 if verify(game, jobs) else 1)
    if args.preview:
        areas = None if args.preview == "all" else {a.strip() for a in args.preview.split(",")}
        sel = select_jobs(jobs, only=only, generic_only=args.generic_only, patterns=patterns, areas_any=areas)
        if not sel:
            sys.exit("nothing to preview (no job matches the area / --paths)")
        t0 = time.time()
        res = run_pool(_worker_preview, [j.key for j in sel], cfg, args.jobs)
        cells = [r for r in res if r["status"] == "ok"]
        for r in res:
            if r["status"] == "error":
                print("ERROR", r["key"], r["error"].strip().splitlines()[-1])
            for w in r.get("warnings", []):
                print("warn:", r["key"], w)
        if not cells:
            sys.exit("no preview could be rendered")
        name = args.preview.replace(",", "+") if areas else "all"
        if patterns and not areas:
            name = "paths"
        PREVIEW.mkdir(parents=True, exist_ok=True)
        for old in PREVIEW.glob(f"ingame_{name}*.png"):
            if old.stem == f"ingame_{name}" or old.stem[len(f"ingame_{name}"):].lstrip("_").isdigit():
                old.unlink()
        cols = 4
        per = max(1, args.per_sheet)
        for s in range(0, len(cells), per):
            chunk = cells[s:s + per]
            ims = [Image.open(io.BytesIO(c["png"])) for c in chunk]
            cw, ch = ims[0].size
            rows = (len(ims) + cols - 1) // cols
            sheet = Image.new("RGB", (cols * cw, rows * ch), (30, 32, 38))
            for i, im in enumerate(ims):
                sheet.paste(im, ((i % cols) * cw, (i // cols) * ch))
            out = PREVIEW / (f"ingame_{name}.png" if s == 0 else f"ingame_{name}_{s // per + 1}.png")
            sheet.save(out, optimize=True)
            print("wrote", out.relative_to(ROOT).as_posix(), f"({len(ims)} textures)")
        print(f"{len(cells)} previews in {time.time() - t0:.1f} s")
        return

    # ---- build
    sel = select_jobs(jobs, only=only, generic_only=args.generic_only, patterns=patterns)
    if not sel:
        sys.exit("nothing to build (no job matches the areas / --paths)")
    order = sorted(sel, key=lambda j: -((j.entry or {}).get("w", 64) * (j.entry or {}).get("h", 64)))
    t0 = time.time()
    prev_start = read_outputs()     # paths another agent lists while this run builds are never stale here
    res = run_pool(_worker_build, [j.key for j in order], cfg, args.jobs)
    written = {r["rel"]: r["producer"] for r in res if r["status"] == "written"}
    errors = [r for r in res if r["status"] == "error"]
    kept = {r["rel"] for r in res if r["status"] == "keep"}
    for r in res:
        for w in r.get("warnings", []):
            print("warn:", r["key"], w)
    for r in errors:
        print("ERROR", r["key"], "\n" + r["error"])
    removed = []
    with OutputsLock():
        prev = read_outputs()
        new = dict(prev)
        new.update(written)
        if full and not broken:
            # delete only files this pipeline listed and no longer produces (failed jobs keep their old file)
            produced = set(written) | {r["rel"] for r in errors if (ROOT / r["rel"]).is_file()}
            for rel in sorted((set(prev) & set(prev_start)) - produced, key=str.lower):
                p = ROOT / rel
                if p.is_file() and p.stat().st_mtime > t0:
                    continue            # rewritten by a parallel --only run while this run was building
                if safe_delete(rel):
                    removed.append(rel)
                new.pop(rel, None)
        else:
            if full and broken:
                print("note: stale deletion disabled because a module was skipped")
            # a path that is now kept as vanilla: its old generated file goes (only if this pipeline listed it)
            for rel in sorted(kept & set(prev), key=str.lower):
                if safe_delete(rel):
                    removed.append(rel)
                new.pop(rel, None)
        write_outputs(new)
    if full and not broken:
        gm = {r["key"]: r.get("mode", "?") for r in res if r["producer"] == "generic" and r["status"] != "error"}
        paper = sorted((r["key"] for r in res if r.get("paper")), key=str.lower)
        write_owners(manifest, owners, extra={"generic_modes": dict(sorted(gm.items(), key=lambda kv: kv[0].lower())),
                                              "paper": paper})
        print(f"{len(paper)} outputs keep a light paper surface (dark text): listed in ingame_owners.json 'paper'")
    # summary
    by = {}
    for r in res:
        if r["status"] != "written":
            continue
        a = by.setdefault(r["area"], {})
        c = a.setdefault(r["fmt"], [0, 0])
        c[0] += 1
        c[1] += r["bytes"]
    print(f"{'area':10} {'format':9} {'files':>6} {'MB':>8}")
    tot = {}
    for a in list(AREAS) + sorted(set(by) - set(AREAS)):
        for fmt, (n, b) in sorted(by.get(a, {}).items()):
            print(f"{a:10} {fmt:9} {n:6} {b / 1e6:8.2f}")
            t = tot.setdefault(fmt, [0, 0])
            t[0] += n
            t[1] += b
    for fmt, (n, b) in sorted(tot.items()):
        print(f"{'TOTAL':10} {fmt:9} {n:6} {b / 1e6:8.2f}")
    print(f"{'TOTAL':10} {'all':9} {sum(v[0] for v in tot.values()):6} {sum(v[1] for v in tot.values()) / 1e6:8.2f}")
    mips = sum(1 for r in res if r["status"] == "written" and (r.get("vmips") or 1) > 1)
    modes = {}
    for r in res:
        modes[r.get("mode", "error")] = modes.get(r.get("mode", "error"), 0) + 1
    print(f"written {len(written)}, kept vanilla {len(kept)}, errors {len(errors)}, removed {len(removed)} stale"
          f" ({'full run' if full else 'partial run'}) in {time.time() - t0:.1f} s")
    print("modes: " + ", ".join(f"{m} {n}" for m, n in sorted(modes.items())))
    print(f"{mips} written textures had mipmaps in vanilla (outputs never have mipmaps)")
    if removed:
        print("removed: " + ", ".join(removed[:12]) + (" ..." if len(removed) > 12 else ""))
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
