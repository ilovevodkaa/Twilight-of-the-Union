#!/usr/bin/env python3
"""Static checker for the mod's interface (.gui / .gfx) and localisation (.yml). Run it after every edit.

It never launches the game; it reads the game folder and writes only to tools/data/. About 1 s per run (the first
run, or one after a game update or a CACHE_VERSION bump, parses vanilla into the cache in about 4-12 s).

    python tools/check_ui.py                         # NEW issues only (not baselined, not inherited from vanilla)
    python tools/check_ui.py --files ingamemenu.gui,interface/totu_ingame.gfx    # only issues in / caused by these
    python tools/check_ui.py --files gfx/interface/closebutton.dds   # what a texture-only edit breaks
    python tools/check_ui.py --strict                # exit 1 on new warnings too (default: exit 1 on new errors)
    python tools/check_ui.py --json                  # machine-readable result on stdout (stats + issues)
    python tools/check_ui.py --all                   # also baselined / ignored / inherited / vanilla-only issues
    python tools/check_ui.py --only E_SPRITE,W_LOC   # or --skip W_TEXSIZE
    python tools/check_ui.py --list-codes            # what every code means
    python tools/check_ui.py --baseline              # record every current new issue as known (LEAD ONLY)
    python tools/check_ui.py --prune-baseline        # drop baseline entries that no longer occur (LEAD ONLY)
    python tools/check_ui.py --rebuild-cache         # re-parse vanilla (automatic when vanilla or hoi4.exe change)
    python tools/check_ui.py --mod <folder>          # check another mod folder (tests); no baseline then

The EFFECTIVE interface is what the game loads: <game>/pdx_online_assets/interface, <game>/interface,
integrated_dlc/*/interface and dlc/*/interface (every DLC folder with a .dlc file); a later source replaces a file
with the same relative path, and the mod's interface/ finally replaces any same-path file and adds the rest.
Textures and font files are looked up in the mod, the DLC folders and zips and the game, case-insensitively, with
the engine's .tga / .png -> .dds fallback; the replace_path folders hide the vanilla files directly inside them
(read from ../<mod folder>.mod, which the launcher uses, else descriptor.mod; W_DESCRIPTOR when the two differ).
Localisation works the same way: a mod .yml with the path of a vanilla .yml replaces it.
@name = value constants of a .gui/.gfx are substituted (they are file-scoped).

Texture-only restyles: a mod texture at a vanilla path must keep the vanilla pixel size (W_TEXOVERRIDE), and a
vanilla sprite that the mod redefines or re-textures must keep its frame size and noOfFrames while a vanilla .gui
the mod does not replace still uses it (W_SPRITE_GEOMETRY). Run with --files gfx/interface/x.dds to see the issues
a texture causes. Engine lookups: a mod .gui replacing a vanilla .gui must keep every element name hoi4.exe
contains (E_ENGINE_NAME; named background blocks too, except the generic "Background") with the same element type
(E_ENGINE_TYPE). To drop a decoration, keep the element and hide it (x = -9000 y = -9000) or point it at a
transparent sprite.

Every issue gets a status:
    new        shown by default: made by the mod (in a mod file, or in a vanilla file because of a mod file)
    baselined  new, but listed in tools/data/check_ui_baseline.txt (known before the restyle streams started)
    ignored    silenced in the mod file by a "# check_ui: ignore [CODE,...]" comment on the reported line
    inherited  the same issue exists in vanilla's own copy of that mod file (the mod copied vanilla's bug)
    vanilla    in a vanilla file and present without the mod too
Only `new` issues count for the exit code. An issue is identified by CODE + file + subject (never the line), so
editing a file does not resurface baselined issues; the subject is "<parent>/<element>|<key>=<value>" or similar.

Markers in mod files (comments, so the game ignores them):
    # check_ui: ignore                    on a line: silence every issue reported on that line
    # check_ui: ignore W_TEXSIZE,W_LOC    on a line: silence those codes there
    # check_ui: allow-missing a b c       anywhere: the vanilla names a, b, c may be dropped (E_ENGINE_NAME/GFX)
    # check_ui: allow-type a b c          anywhere: the elements a, b, c may change their type (E_ENGINE_TYPE)

The baseline is the lead's tool: --baseline and --prune-baseline take a lock file, and --prune-baseline refuses
to run while a mod file does not parse (its entries would vanish only because the file is broken).

Caches in tools/data/: exe_names.txt (names of vanilla interface files that hoi4.exe contains as whole strings;
rebuilt when hoi4.exe or the extractor version changes, kept when the exe is missing) and
__pycache__/check_ui_cache.pickle (vanilla parse, git-ignored by the repository's __pycache__/ rule). HOI4_DIR
overrides the game folder.

Python API:  sys.path.insert(0, "tools"); import check_ui
             issues = check_ui.check(files=["interface/ingamemenu.gui"])   # list of dicts: code, severity, file,
             origin, line, message, subject, related [{file, origin, line}], status
             nodes, errors = check_ui.parse(text)   # the Paradox-script parser: nodes are (klow, key, value, line)
"""
import argparse
import fnmatch
import json
import os
import pickle
import re
import struct
import sys
import time
import zipfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GAME = Path(os.environ.get("HOI4_DIR", r"D:\steam\steamapps\common\Hearts of Iron IV"))
DATA = ROOT / "tools" / "data"
CACHE_FILE = DATA / "__pycache__" / "check_ui_cache.pickle"
EXE_NAMES = DATA / "exe_names.txt"
BASELINE = DATA / "check_ui_baseline.txt"
BASELINE_LOCK = DATA / "check_ui_baseline.lock"
CACHE_VERSION = 6                # bump when the extraction or the checks change
EXE_NAMES_VERSION = 2            # bump when the names offered to the exe scan change (written into exe_names.txt)

LOC_LANGS = ("english", "russian")

# Vanilla names hoi4.exe contains whose removal is known to be harmless (the engine only logs it), as
# (top-level window regex, element name regex, why). Per file, a comment "# check_ui: allow-missing name1 name2"
# in the mod file does the same; "# check_ui: ignore [CODE,...]" on a line silences issues reported on that line.
ENGINE_OPTIONAL = [
    (r"mainmenu_panel_bottom", r"subscription_size|subscription_divider|subscription_widget\w*|show_subscription",
     "while the subscription widget is shown the engine resizes mainmenu_panel_bottom to subscription_size; without "
     "these elements it only logs them (interface/frontendmainview.gui, as Road to 56 does on 1.19)"),
]
STATUSES = ("new", "baselined", "ignored", "inherited", "vanilla")
MARK_IGNORE = re.compile(r"#.*?\bcheck_ui:\s*ignore\b([^\n]*)")
MARK_ALLOW = re.compile(r"#.*?\bcheck_ui:\s*allow-missing\b([^\n#]*)")
MARK_ALLOW_TYPE = re.compile(r"#.*?\bcheck_ui:\s*allow-type\b([^\n#]*)")
HIDE = -9000                     # the mod's convention for elements the engine looks up but the mod does not show
OFFSCREEN = 5000
TEXSIZE_RATIO = 2.0              # W_TEXSIZE when element size / sprite frame differs by more than this factor
LOADSCREEN_GUI = "interface/load_screen.gui"
LOADSCREEN_GFX = ("interface/load_screen.gfx", "interface/load_screen_font.gfx")   # read before every other file

# DDS pixel formats some vanilla texture uses (a survey of the 33,094 vanilla .dds files, 1.19.3): legacy FourCC
# DXT1 / DXT3 / DXT5 / RXGB, uncompressed 16 / 24 / 32 bit, and DX10 headers only with DXGI 29 (R8G8B8A8_UNORM_SRGB)
# and 91 (B8G8R8A8_UNORM_SRGB); 28 and 87 are their linear twins. Anything else (BC7 = DXGI 98/99, BC4/BC5, float)
# is W_TEXFORMAT: it may not load.
DDS_FOURCC_BLOCK = {b"DXT1": 8, b"DXT2": 16, b"DXT3": 16, b"DXT4": 16, b"DXT5": 16, b"RXGB": 16}
DDS_DXGI_BPP = {28: 32, 29: 32, 87: 32, 91: 32}

CODES = {
    "E_PARSE": "Script does not parse: unbalanced braces, stray '=', a key without value, unterminated string",
    "E_SPRITE": "A sprite reference (spriteType, quadTextureSprite, background, scrollbar parts...) names no sprite",
    "E_FONT": "font / buttonFont names no bitmapfont",
    "E_TEXTURE": "A sprite's texture, a font's .fnt / atlas, or a .gui textureFile exists in neither mod nor game",
    "E_FRAMES": "Texture width is not divisible by noOfFrames",
    "E_SCROLLBAR": "verticalScrollbar / horizontalScrollbar / scrollbartype names no scrollbar type",
    "E_ENGINE_NAME": "A mod .gui replacing a vanilla .gui lost an element name hoi4.exe looks up (keep the element; "
                     "hide it at x = -9000 y = -9000)",
    "E_ENGINE_GFX": "A mod .gfx replacing a vanilla .gfx lost a sprite / font name hoi4.exe looks up",
    "E_ENGINE_TYPE": "A mod .gui kept an element name hoi4.exe looks up but changed its type (e.g. iconType -> "
                     "buttonType); the engine fetches it by name and type",
    "E_TEXFORMAT": "A texture the interface uses is empty, truncated or not a DDS / TGA / PNG image",
    "E_LOADSCREEN": "interface/load_screen.gui uses a sprite / font that load_screen.gfx / load_screen_font.gfx do "
                    "not define (they are read before every other interface file)",
    "E_ENCODING": "BOM or invalid UTF-8 in a mod .gui/.gfx; missing BOM or invalid UTF-8 in a mod .yml",
    "E_LOC_FILE": "Localisation file: first line is not l_<language>:, or the name lacks / contradicts _l_<language>",
    "W_DUP_SPRITE": "The same sprite or font name is defined twice in the effective interface (both places listed)",
    "W_DUP_WINDOW": "The same top-level guiTypes name (window or scrollbar type) is defined in two effective .gui files",
    "W_GFX_DROPPED": "A mod .gfx replacing a vanilla .gfx dropped a vanilla sprite / font (scripts may still use it)",
    "W_SPRITE_GEOMETRY": "A vanilla sprite the mod redefines or re-textures changed its frame size / noOfFrames "
                         "while vanilla .gui files the mod does not replace still use it",
    "W_TEXOVERRIDE": "A mod texture at a vanilla path has another pixel size than the vanilla file it replaces",
    "W_TEXFORMAT": "A mod texture uses a DDS format no vanilla texture uses (DX10 / BC7, BC4/5, float): it may not load",
    "W_LOC": "A text / buttonText / tooltip value that is a loc key (TOTU_*, UPPER_SNAKE, or a key some language "
             "has) is missing in english and/or russian",
    "W_LOC_DUP": "The same loc key is defined twice in the mod for one language",
    "W_LOC_OVERRIDE": "A mod loc key outside a replace/ folder redefines a vanilla key (which one wins is undefined)",
    "W_ENCODING": "Non-ASCII text in a mod .gui/.gfx (one issue per line), or CRLF line ends in a mod file",
    "W_OFFSCREEN": "position / show_position beyond +-5000 that is not the -9000 hide convention",
    "W_TEXSIZE": "iconType / buttonType size differs by more than 2x from its sprite's frame (times scale)",
    "W_COLOR": "text_color_code is defined neither by the element's font nor by the global textcolors",
    "W_FONT_OVERRIDE": "bitmapfont_override names a font that no bitmapfont defines",
    "W_CASE": "A sprite / font reference matches a definition only when case is ignored",
    "W_UNKNOWN_KEY": "A key no vanilla .gui (or .gfx) uses: a typo such as spriteTyp, or a key of another file kind",
    "W_NESTING": "An element type nested in a parent type vanilla never nests it in (e.g. an iconType inside a "
                 "buttonType: usually a misplaced brace)",
    "W_DESCRIPTOR": "replace_path differs between descriptor.mod and ../<mod>.mod (the launcher reads the .mod)",
}
CODE_ORDER = {"E_PARSE": 0}          # E_PARSE first: the issues after a parse error are often its cascade

# ----------------------------------------------------------------------------------------------------------------
# Parser
# ----------------------------------------------------------------------------------------------------------------
# groups: 1 newline, 2 comment, 3 quoted string, 4 lone quote (unterminated), 5 brace, 6 operator, 7 bare word
TOKEN_RE = re.compile(r'(\n)|[ \t\r\f\v\ufeff]+|(#[^\n]*)|("(?:[^"\\\n]|\\.)*")|(")|([{}])|([<>!?]=|==|[=<>])'
                      r'|([^\s{}=#"<>]+)')
STRING_RE = re.compile(r'"(?:[^"\\\n]|\\.)*"')
STRING_RE_B = re.compile(rb'"(?:[^"\\\n]|\\.)*"')


def parse(text):
    """Parse Paradox script into (nodes, errors); never raises.

    A node is a tuple (klow, key, value, line): klow is the lower-cased key (None for a bare list value), value a
    str (quotes removed, \\" unescaped) or a list of nodes. errors is a list of (line, message). Recovery: a stray
    '}' is skipped, blocks still open at the end of the file are closed there. An unquoted value @name is replaced
    by the value of an earlier "@name = value" of the file (vanilla defines some inside blocks)."""
    errors = []
    variables = {}
    root = []
    stack = []                       # (parent list, key, klow, line) for every open block
    cur = root
    pend = None                      # (token, line): a key or a bare value, not known yet
    eq = False                       # pend is a key and its '=' was seen
    line = 1
    for m in TOKEN_RE.finditer(text):
        g = m.lastindex
        if g is None or g == 2:
            continue
        if g == 1:
            line += 1
        elif g == 3 or g == 7:
            if g == 3:
                tok = m.group(3)[1:-1]
                if "\\" in tok:
                    tok = tok.replace('\\"', '"')
            else:
                tok = m.group(7)
            if eq:
                if g == 7 and tok[:1] == "@" and len(tok) > 1 and tok[1] != "[":
                    if tok[1:] in variables:                 # @name constants: unquoted, defined before use
                        tok = variables[tok[1:]]
                    else:
                        errors.append((line, "undefined variable %s (define it earlier in this file: %s = ...)"
                                       % (tok, tok)))
                if pend[0][:1] == "@" and len(pend[0]) > 1:
                    variables[pend[0][1:]] = tok
                cur.append((pend[0].lower(), pend[0], tok, pend[1]))
                pend, eq = None, False
            else:
                if pend is not None:
                    cur.append((None, None, pend[0], pend[1]))
                pend = (tok, line)
        elif g == 4:
            errors.append((line, 'unterminated string (a " without a closing quote on its line)'))
        elif g == 6:
            if eq:
                errors.append((line, "unexpected '%s' after '%s ='" % (m.group(6), pend[0])))
            elif pend is None:
                errors.append((line, "'%s' without a key before it" % m.group(6)))
            else:
                eq = True
        elif m.group(5) == "{":
            if eq:
                stack.append((cur, pend[0], pend[0].lower(), pend[1]))
            else:
                if pend is not None:
                    cur.append((None, None, pend[0], pend[1]))
                stack.append((cur, None, None, line))
            pend, eq = None, False
            cur = []
        else:
            if eq:
                errors.append((pend[1], "'%s =' has no value before '}'" % pend[0]))
            elif pend is not None:
                cur.append((None, None, pend[0], pend[1]))
            pend, eq = None, False
            if not stack:
                errors.append((line, "unexpected '}' (more '}' than '{')"))
                continue
            parent, key, klow, l0 = stack.pop()
            parent.append((klow, key, cur, l0))
            cur = parent
    if eq:
        errors.append((pend[1], "'%s =' has no value at the end of the file" % pend[0]))
    elif pend is not None:
        cur.append((None, None, pend[0], pend[1]))
    if stack:
        opened = [s[3] for s in stack]
        errors.append((opened[-1], "%d '{' never closed (opened at line%s %s)%s"
                       % (len(opened), "s" if len(opened) > 1 else "", ", ".join(map(str, opened[:6])),
                          brace_hint(text))))
    while stack:
        parent, key, klow, l0 = stack.pop()
        parent.append((klow, key, cur, l0))
        cur = parent
    if any(msg.startswith("unexpected '}'") for _, msg in errors):
        hint = brace_hint(text)
        errors = [(l, msg + hint if msg.startswith("unexpected '}'") else msg) for l, msg in errors]
    return root, errors


def _indent(s):
    n = 0
    for ch in s:
        if ch == " ":
            n += 1
        elif ch == "\t":
            n += 4
        else:
            break
    return n


def brace_hint(text):
    """Guess where a brace is missing: the first block opened at a line end whose '}' (alone at a line start) has
    another indentation than the line that opened it."""
    stack = []
    for i, raw in enumerate(text.split("\n"), 1):
        s = STRING_RE.sub('""', raw)
        h = s.find("#")
        if h >= 0:
            s = s[:h]
        ind = _indent(raw)
        for j, ch in enumerate(s):
            if ch == "{":
                stack.append((i, ind, s[j + 1:].strip() == ""))
            elif ch == "}":
                if not stack:
                    return "; the first unmatched '}' is at line %d" % i
                l0, ind0, ends0 = stack.pop()
                if ends0 and s[:j].strip() == "" and ind != ind0:
                    return "; probable spot: the block opened at line %d is closed at line %d with another " \
                           "indentation" % (l0, i)
    return ""


def read_text(path):
    data = Path(path).read_bytes()
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(enc), data
        except UnicodeDecodeError:
            pass
    return data.decode("latin-1"), data


def num(s):
    if not isinstance(s, str):
        return None
    try:
        return int(s)
    except ValueError:
        try:
            return float(s)
        except ValueError:
            return None


def norm_path(p):
    p = re.sub(r"/+", "/", p.strip().replace("\\", "/"))
    while p.startswith("./"):
        p = p[2:]
    return p.lstrip("/")


# ----------------------------------------------------------------------------------------------------------------
# Extraction: a compact, picklable summary of a file
# ----------------------------------------------------------------------------------------------------------------
SPRITE_DEF_KEYS = {"spritetype", "textspritetype", "corneredtilespritetype", "frameanimatedspritetype",
                   "progressbartype", "maskedshieldtype", "arrowtype", "piecharttype", "linecharttype",
                   "circularprogressbartype"}
IMAGE_EXT = (".dds", ".tga", ".png")
SPRITE_REF_KEYS = {"spritetype", "quadtexturesprite"}
FONT_REF_KEYS = {"font", "buttonfont"}
SCROLL_REF_KEYS = {"verticalscrollbar", "horizontalscrollbar", "scrollbartype"}
SCROLL_DEF_KEYS = {"scrollbartype", "extendedscrollbartype"}
LOC_REF_KEYS = {"text", "buttontext", "tooltip", "delayedtooltip", "tooltiptext", "delayedtooltiptext",
                "pdx_tooltip", "pdx_tooltip_delayed", "pdx_disabled_tooltip", "pdx_disabled_tooltip_delayed"}
GEOMETRY_KEYS = {"position", "size", "show_position", "bordersize", "margin", "offset", "slotsize", "spacing"}
TEXSIZE_ELEMS = {"icontype", "buttontype", "guibuttontype"}
LOC_KEY_RE = re.compile(r"^(?:TOTU_\w+|[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)$")
LOC_TOTU_RE = re.compile(r"^totu_\w+$", re.I)          # a TOTU_ key in any case is meant as a loc key
LOC_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")  # other identifiers: a loc key if some language has it


def _name(items):
    for k, _, v, _ in items:
        if k == "name" and not isinstance(v, list):
            return v
    return None


def collect_keys(nodes, gui):
    """({klow: (key, line, where)} first use of every key, {(parent element type, element type): (line, where)})
    for W_UNKNOWN_KEY / W_NESTING. Children of textcolors (colour letters) and @constants are not keys."""
    keys, nest = {}, {}

    def walk(items, parent_klow, where, etype):
        for klow, key, v, line in items:
            if klow is None:
                continue
            if parent_klow != "textcolors" and klow[:1] != "@":
                keys.setdefault(klow, (key, line, where))
            if isinstance(v, list):
                name = _name(v)
                w = "%s/%s" % (where, name) if name else where
                if gui and klow.endswith("type"):
                    nest.setdefault((etype, klow), (line, "%s %s" % (key, w)))
                    walk(v, klow, w, klow)
                else:
                    walk(v, klow, w, etype)
    walk(nodes, None, "", "<root>")
    return keys, nest


def extract_gui(nodes):
    """tops [(klow, name, line)], names {(top, name): (klow, line)}, types {(top, name): {klow}}, refs [(kind, key,
    value, line, here, etype)], sbdefs [(name, line)], pos [(here, etype, which, x, y, line)], texsize [...],
    colors [...], keys / nest (collect_keys). A named background block counts as an element of type 'background'
    (hoi4.exe looks some up by name, e.g. topbar.gui nukes_bg), except the generic name 'Background'."""
    S = {"tops": [], "names": {}, "types": {}, "refs": [], "sbdefs": [], "pos": [], "texsize": [], "colors": []}
    S["keys"], S["nest"] = collect_keys(nodes, True)

    def block(klow, key, v, line, top, here, name):
        etype = key or "{}"
        if name and (klow != "background" or name.lower() != "background"):
            S["names"].setdefault((top, name), (klow, line))
            S["types"].setdefault((top, name), set()).add(klow)
            if klow in SCROLL_DEF_KEYS:
                S["sbdefs"].append((name, line))
        sprite = font = code = None
        scale = 1.0
        size = None
        for k2, key2, v2, l2 in v:
            if isinstance(v2, list):
                if k2 in ("position", "show_position"):
                    x = y = None
                    for k3, _, v3, _ in v2:
                        if k3 == "x":
                            x = num(v3)
                        elif k3 == "y":
                            y = num(v3)
                    S["pos"].append((here, etype, key2, x, y, l2))
                elif k2 == "size":
                    w = h = None
                    for k3, _, v3, _ in v2:
                        if k3 in ("width", "x"):
                            w = num(v3)
                        elif k3 in ("height", "y"):
                            h = num(v3)
                    size = (w, h, l2)
                continue
            if k2 is None or v2 == "":
                continue
            if k2 in SPRITE_REF_KEYS or k2 == "background":
                S["refs"].append(("sprite", key2, v2, l2, here, etype))
                if k2 in SPRITE_REF_KEYS and sprite is None:
                    sprite = v2
            elif k2 in FONT_REF_KEYS:
                S["refs"].append(("font", key2, v2, l2, here, etype))
                font = font or v2
            elif k2 in SCROLL_REF_KEYS:
                S["refs"].append(("scrollbar", key2, v2, l2, here, etype))
            elif k2 in LOC_REF_KEYS:
                if LOC_KEY_RE.match(v2) or LOC_TOTU_RE.match(v2):
                    S["refs"].append(("loc", key2, v2, l2, here, etype))
                elif LOC_IDENT_RE.match(v2):
                    S["refs"].append(("locw", key2, v2, l2, here, etype))
            elif k2 == "texturefile":
                S["refs"].append(("texture", key2, v2, l2, here, etype))
            elif k2 == "text_color_code":
                code = (v2, l2)
            elif k2 == "scale":
                scale = num(v2) or 1.0
        if code and font:
            S["colors"].append((here, etype, font, code[0], code[1]))
        if klow in TEXSIZE_ELEMS and size and sprite and size[0] and size[1] and size[0] > 0 and size[1] > 0:
            S["texsize"].append((here, etype, sprite, size[0], size[1], scale, size[2]))

    def walk(items, top, parent, ctx):
        for klow, key, v, line in items:
            if not isinstance(v, list) or klow in GEOMETRY_KEYS:
                continue
            name = _name(v)
            here = "%s/%s" % (parent, name) if name else "%s>%s" % (ctx, key or "{}")
            block(klow, key, v, line, top, here, name)
            walk(v, top, name or parent, here)

    for klow, key, v, line in nodes:
        if not isinstance(v, list):
            continue
        for k2, key2, v2, l2 in (v if klow == "guitypes" else [(klow, key, v, line)]):
            if not isinstance(v2, list):
                continue
            name = _name(v2)
            top = name or "<%s@%d>" % (key2, l2)
            S["tops"].append((k2, top, l2))
            block(k2, key2, v2, l2, top, top, name)
            walk(v2, top, top, top)
    return S


def extract_gfx(nodes):
    """sprites [(name, klow, line, frames, [(key, path, line)])], fonts / overrides [(name, line, [(file, line)],
    [colour codes])], gcolors [codes of the global textcolors]."""
    S = {"sprites": [], "fonts": [], "overrides": [], "gcolors": []}
    S["keys"] = collect_keys(nodes, False)[0]

    def textures(items, out):
        for k, key, v, line in items:
            if isinstance(v, list):
                textures(v, out)
            elif k is not None and k != "name" and v.lower().endswith(IMAGE_EXT):
                out.append((key, v, line))

    def walk(items, parent):
        for klow, key, v, line in items:
            if not isinstance(v, list):
                continue
            name = _name(v)
            if name and (klow in SPRITE_DEF_KEYS or parent == "spritetypes"):
                tex = []
                textures(v, tex)
                frames = None
                for k2, _, v2, _ in v:
                    if k2 == "noofframes":
                        frames = num(v2)
                S["sprites"].append((name, klow, line, frames, tex))
            elif klow in ("bitmapfont", "bitmapfont_override"):
                files, colors = [], []
                for k2, _, v2, l2 in v:
                    if k2 == "fontfiles" and isinstance(v2, list):
                        files += [(x[2], x[3]) for x in v2 if x[0] is None and isinstance(x[2], str)]
                    elif k2 == "path" and isinstance(v2, str):
                        files.append((v2, l2))
                    elif k2 == "textcolors" and isinstance(v2, list):
                        colors += [x[1] for x in v2 if x[1] is not None]
                if name:
                    S["fonts" if klow == "bitmapfont" else "overrides"].append((name, line, files, colors))
            elif klow == "textcolors" and parent == "bitmapfonts":
                S["gcolors"] += [x[1] for x in v if x[1] is not None]
            else:
                walk(v, klow)
    walk(nodes, None)
    return S


def summarize(path, kind):
    text, raw = read_text(path)
    nodes, errors = parse(text)
    S = extract_gui(nodes) if kind == "gui" else extract_gfx(nodes)
    S["errors"] = errors
    return S, raw


# ----------------------------------------------------------------------------------------------------------------
# File discovery
# ----------------------------------------------------------------------------------------------------------------
def vanilla_sources():
    """[(origin, root)] in increasing priority."""
    out = []
    if (GAME / "pdx_online_assets").is_dir():
        out.append(("online", GAME / "pdx_online_assets"))
    out.append(("vanilla", GAME))
    for base, tag in ((GAME / "integrated_dlc", "integrated"), (GAME / "dlc", "dlc")):
        if base.is_dir():
            for d in sorted(base.iterdir(), key=lambda p: p.name.lower()):
                if d.is_dir() and any(f.suffix.lower() == ".dlc" for f in d.iterdir()):
                    out.append(("%s:%s" % (tag, d.name), d))
    return out


def interface_files(root):
    """{rel_lower: (rel, abs)} of root/interface/**/*.gui|gfx."""
    out = {}
    base = root / "interface"
    if not base.is_dir():
        return out
    for dirpath, _, filenames in os.walk(base):
        for fn in filenames:
            low = fn.lower()
            if low.endswith(".gui") or low.endswith(".gfx"):
                full = os.path.join(dirpath, fn)
                rel = "interface/" + os.path.relpath(full, base).replace("\\", "/")
                out[rel.lower()] = (rel, full)
    return out


def vanilla_files():
    """The effective vanilla interface: {rel_lower: (rel, abs, origin, kind)}."""
    eff = {}
    for origin, root in vanilla_sources():
        for low, (rel, full) in interface_files(root).items():
            eff[low] = (rel, full, origin, low[-3:])
    return eff


def _replace_set(path):
    out = set()
    for m in re.finditer(r'^\s*replace_path\s*=\s*"([^"]+)"', read_text(path)[0], re.M):
        out.add(norm_path(m.group(1)).lower().rstrip("/"))
    return out


def launcher_mod_file():
    """The ../<name>.mod the launcher and the game read for this mod folder: <folder name>.mod, else any .mod in
    the parent folder whose path = names this folder (the launcher writes 8.3 short paths)."""
    same = ROOT.parent / (ROOT.name + ".mod")
    if same.is_file():
        return same
    try:
        mods = sorted(ROOT.parent.glob("*.mod"))
    except OSError:
        return None
    for p in mods:
        m = re.search(r'^\s*path\s*=\s*"([^"]+)"', read_text(p)[0], re.M)
        try:
            if m and os.path.samefile(m.group(1), ROOT):
                return p
        except OSError:
            continue
    return None


def replace_paths():
    """(replace_path folders the game applies, issues): the launcher's ../<name>.mod wins over descriptor.mod."""
    desc = ROOT / "descriptor.mod"
    dset = _replace_set(desc) if desc.is_file() else None
    lmod = launcher_mod_file()
    lset = _replace_set(lmod) if lmod else None
    issues = []
    if dset is not None and lset is not None and dset != lset:
        diff = ["%s only in %s" % (", ".join(sorted(a - b)), n) for a, b, n in
                ((dset, lset, "descriptor.mod"), (lset, dset, lmod.name)) if a - b]
        issues.append(mk("W_DESCRIPTOR", ("descriptor.mod", "mod"), 1, "replace_path differs from ../%s, which the "
                         "launcher reads (%s); this check uses the .mod" % (lmod.name, "; ".join(diff)), "replace_path"))
    return (lset if lset is not None else dset or set()), issues


def hidden_by_replace(rel_low, rps):
    return "/" in rel_low and rel_low.rsplit("/", 1)[0] in rps


def stat_sig(path):
    try:
        st = os.stat(path)
        return (st.st_size, st.st_mtime_ns)
    except OSError:
        return None


# ----------------------------------------------------------------------------------------------------------------
# Textures
# ----------------------------------------------------------------------------------------------------------------
def image_size(path=None, data=None):
    try:
        if data is None:
            with open(path, "rb") as f:
                data = f.read(32)
        if data[:4] == b"DDS ":
            h, w = struct.unpack("<II", data[12:20])
            return (w, h)
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            return struct.unpack(">II", data[16:24])
        if len(data) >= 18 and data[2] in (1, 2, 3, 9, 10, 11):
            return struct.unpack("<HH", data[12:16])
    except (OSError, struct.error, IndexError):
        pass
    return None


def tex_info(path):
    """(size or None, problem or None) of an image file; problem = ("E" or "W", message). Checks what the engine
    needs: a DDS / TGA / PNG header, a non-zero size, a file long enough for the first mip level, and a DDS pixel
    format some vanilla texture uses (DDS_FOURCC_BLOCK / DDS_DXGI_BPP)."""
    try:
        fsize = os.path.getsize(path)
        with open(path, "rb") as f:
            data = f.read(148)
    except OSError as ex:
        return None, ("E", "cannot be read (%s)" % ex.__class__.__name__)
    if fsize == 0:
        return None, ("E", "is an empty file (0 bytes)")
    ext = os.path.splitext(path)[1].lower()
    if data[:4] == b"DDS ":
        if len(data) < 128:
            return None, ("E", "is truncated: %d bytes, a DDS header needs 128" % fsize)
        h, w = struct.unpack("<II", data[12:20])
        pflags, fourcc, bits = struct.unpack("<I4sI", data[80:92])
        if not w or not h:
            return None, ("E", "has a %dx%d DDS header" % (w, h))
        head, need, prob = 128, None, None
        if pflags & 0x4:
            if fourcc == b"DX10":
                head = 148
                dxgi = struct.unpack("<I", data[128:132])[0] if len(data) >= 132 else -1
                if dxgi in DDS_DXGI_BPP:
                    need = w * h * DDS_DXGI_BPP[dxgi] // 8
                else:
                    prob = ("W", "is a DDS with a DX10 header, DXGI format %d%s; no vanilla texture uses it, the game "
                                 "may not load it (save DXT5 / DXT1 or uncompressed RGBA: Pillow img.save(p, "
                                 "pixel_format=\"DXT5\") or plain RGBA)"
                            % (dxgi, " (BC7)" if dxgi in (97, 98, 99) else ""))
            elif fourcc in DDS_FOURCC_BLOCK:
                need = max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * DDS_FOURCC_BLOCK[fourcc]
            else:
                prob = ("W", "is a DDS with FourCC %r, which no vanilla texture uses; the game may not load it"
                        % fourcc.decode("latin-1"))
        elif pflags & 0x40 and bits in (16, 24, 32):
            need = (w * bits + 7) // 8 * h
        else:
            prob = ("W", "is a DDS with pixel format flags 0x%x / %d bit, which no vanilla texture uses" % (pflags, bits))
        if need is not None and fsize < head + need:
            prob = ("E", "is truncated: %d bytes, a %dx%d DDS of this format needs at least %d"
                    % (fsize, w, h, head + need))
        return (w, h), prob
    is_png = data[:8] == b"\x89PNG\r\n\x1a\n"
    if is_png and ext == ".png":
        sz = struct.unpack(">II", data[16:24]) if len(data) >= 24 else None
        return sz, None if sz and sz[0] and sz[1] else ("E", "is a truncated PNG")
    if ext == ".tga" and len(data) >= 18 and data[2] in (1, 2, 3, 9, 10, 11):
        w, h = struct.unpack("<HH", data[12:16])
        if not w or not h:
            return None, ("E", "has a %dx%d TGA header" % (w, h))
        if data[2] in (2, 3):
            need = 18 + data[0] + struct.unpack("<H", data[5:7])[0] * ((data[7] + 7) // 8) + w * h * ((data[16] + 7) // 8)
            if fsize < need:
                return (w, h), ("E", "is truncated: %d bytes, this %dx%d TGA needs %d" % (fsize, w, h, need))
        return (w, h), None
    what = "PNG data" if is_png else "no DDS / TGA / PNG image"
    return None, ("E", "is %s, but named %s (header bytes %s)" % (what, ext or "without extension", data[:4].hex()))


def tex_candidates(rel_low):
    """The engine falls back to .dds for a missing .tga / .png (vanilla relies on it for .png)."""
    return [rel_low, rel_low[:-4] + ".dds"] if rel_low.endswith((".tga", ".png")) else [rel_low]


class VanillaTextures:
    """Case-insensitive lookup over the vanilla roots (DLC folders and zips first, then the game). Its plain state
    (listings, lookups, image sizes) is pickled with the cache, so it is kept between runs."""

    @classmethod
    def restore(cls, state):
        self = cls.__new__(cls)
        self.__dict__.update(state)
        return self

    def __init__(self, sources):
        self.roots = [(origin, str(root)) for origin, root in reversed(sources)]   # highest priority first
        self.zips = []
        for origin, root in self.roots:
            for z in sorted(Path(root).glob("*.zip")):
                try:
                    with zipfile.ZipFile(z) as zf:
                        names = {n.lower().rstrip("/"): n for n in zf.namelist()}
                except (OSError, zipfile.BadZipFile):
                    continue
                self.zips.append((origin, str(z), names))
        self.listing = {}
        self.found = {}
        self.sizes = {}

    def _list(self, root, d):
        k = (root, d)
        if k not in self.listing:
            try:
                self.listing[k] = {e.name.lower(): e.name for e in os.scandir(os.path.join(root, d))}
            except OSError:
                self.listing[k] = None
        return self.listing[k]

    def find_exact(self, c):
        """c: a normalised lower-case path, no extension fallback. Returns (origin, location) or None; location is
        an absolute path or 'zip|<zip>|<member>'."""
        if c in self.found:
            return self.found[c]
        res = None
        d, _, fn = c.rpartition("/")
        for origin, root in self.roots:
            lst = self._list(root, d)
            if lst and fn in lst:
                res = (origin, os.path.join(root, d, lst[fn]))
                break
        if res is None:
            for origin, z, names in self.zips:
                if c in names:
                    res = (origin, "zip|%s|%s" % (z, names[c]))
                    break
        self.found[c] = res
        return res

    def find(self, rel_low):
        """rel_low: a normalised lower-case path; the .tga / .png -> .dds fallback applies."""
        for c in tex_candidates(rel_low):
            res = self.find_exact(c)
            if res:
                return res
        return None

    def size(self, found):
        loc = found[1]
        if loc not in self.sizes:
            if loc.startswith("zip|"):
                _, z, member = loc.split("|", 2)
                try:
                    with zipfile.ZipFile(z) as zf, zf.open(member) as f:
                        self.sizes[loc] = image_size(data=f.read(32))
                except (OSError, KeyError, zipfile.BadZipFile):
                    self.sizes[loc] = None
            else:
                self.sizes[loc] = image_size(loc)
        return self.sizes[loc]

    def state(self):
        return (len(self.listing), len(self.found), len(self.sizes))

    def why_missing(self, rel_low):
        return ""


class ModTextures:
    """Mod first, then vanilla minus the folders hidden by the mod's replace_path."""

    def __init__(self, vanilla, rps, size_cache):
        self.v = vanilla
        self.rps = rps
        self.size_cache = size_cache            # {abs path: (stat sig, size)}, persisted in the cache
        self.dirty = False
        self.index = {}
        self.extra = {}
        self.rels = {}                          # {abs path: path relative to the mod root, original case}
        base = str(ROOT)
        for dirpath, _, filenames in os.walk(base + os.sep + "gfx"):
            rd = dirpath[len(base) + 1:].replace("\\", "/")
            for fn in filenames:
                full = os.path.join(dirpath, fn)
                rel = rd + "/" + fn
                self.index[rel.lower()] = full
                self.rels[full] = rel

    def _mod(self, c):
        if c in self.index:
            return self.index[c]
        if c.startswith("gfx/"):
            return None
        if c not in self.extra:
            p = ROOT / c
            self.extra[c] = str(p) if p.is_file() else None
        return self.extra[c]

    def find(self, rel_low):
        """The exact path in the mod, then in the game; only then the .dds fallback (a vanilla x.tga wins over a
        mod x.dds, as the game's file system resolves the exact name first)."""
        for c in tex_candidates(rel_low):
            m = self._mod(c)
            if m:
                return ("mod", m)
            if not hidden_by_replace(c, self.rps):
                v = self.v.find_exact(c)
                if v:
                    return v
        return None

    def why_missing(self, rel_low):
        if hidden_by_replace(rel_low, self.rps) and self.v.find(rel_low):
            return " (the game has it, but the mod's replace_path \"%s\" hides that folder)" \
                   % rel_low.rsplit("/", 1)[0]
        return ""

    def rel(self, found):
        return self.rels.get(found[1]) or rel_root(found[1])

    def info(self, found):
        """(size, problem) of a mod file (tex_info), cached by stat signature."""
        loc = found[1]
        sig = stat_sig(loc)
        hit = self.size_cache.get(loc)
        if hit and hit[0] == sig:
            return hit[1], hit[2]
        sz, prob = tex_info(loc)
        self.size_cache[loc] = (sig, sz, prob)
        self.dirty = True
        return sz, prob

    def size(self, found):
        if found[0] != "mod":
            return self.v.size(found)
        return self.info(found)[0]


# ----------------------------------------------------------------------------------------------------------------
# Localisation and hoi4.exe
# ----------------------------------------------------------------------------------------------------------------
YML_KEY_RE = re.compile(r'^[ \t]*([^\s:#"]+)[ \t]*:[ \t]*\d*[ \t]*"', re.M)
YML_HEAD_RE = re.compile(r"^l_([a-z_]+)\s*:\s*$")


def yml_header(text):
    """(language or None, line, first meaningful line)."""
    for i, ln in enumerate(text.split("\n"), 1):
        s = ln.strip().lstrip("\ufeff")
        if not s or s.startswith("#"):
            continue
        m = YML_HEAD_RE.match(s)
        return (m.group(1) if m else None), i, s
    return None, 0, ""


def yml_keys(text):
    """[(key, line)]."""
    out = []
    line, last = 1, 0
    for m in YML_KEY_RE.finditer(text):
        line += text.count("\n", last, m.start())
        last = m.start()
        out.append((m.group(1), line))
    return out


def vanilla_loc_files():
    """[(lang, abs, rel)]: rel is relative to the localisation folder, lower-case ('english/x_l_english.yml')."""
    out = []
    roots = [GAME / "localisation"] + [r / "localisation" for _, r in vanilla_sources() if r != GAME]
    for base in roots:
        for lang in LOC_LANGS:
            d = base / lang
            if d.is_dir():
                for dirpath, _, filenames in os.walk(d):
                    for fn in sorted(filenames):
                        if fn.lower().endswith(".yml"):
                            full = os.path.join(dirpath, fn)
                            out.append((lang, full, os.path.relpath(full, base).replace("\\", "/").lower()))
    return out


def vanilla_loc(files):
    """({lang: {lower key: file id or tuple of ids}}, [rel of each file id])."""
    keys = {lang: {} for lang in LOC_LANGS}
    rels = []
    for lang, full, rel in files:
        fid = len(rels)
        rels.append(rel)
        text = read_text(full)[0]
        d = keys.get(yml_header(text)[0] or lang)
        if d is None:
            continue
        for m in YML_KEY_RE.finditer(text):
            k = m.group(1).lower()
            old = d.get(k)
            if old is None:
                d[k] = fid
            elif isinstance(old, int):
                if old != fid:
                    d[k] = (old, fid)
            elif fid not in old:
                d[k] = old + (fid,)
    return keys, rels


class LocIndex:
    """Vanilla keys minus those only in vanilla files that a mod file with the same path replaces."""

    def __init__(self, keys, rels, mod_rels=()):
        self.keys = keys
        mod_rels = set(mod_rels)
        self.replaced = {i for i, r in enumerate(rels) if r in mod_rels}

    def has(self, lang, low):
        v = self.keys[lang].get(low)
        if v is None:
            return False
        if not self.replaced:
            return True
        if isinstance(v, int):
            return v not in self.replaced
        return any(f not in self.replaced for f in v)


def exe_tag():
    sig = stat_sig(GAME / "hoi4.exe")
    return "# source: hoi4.exe size=%s mtime_ns=%s extractor=%d" % (sig + (EXE_NAMES_VERSION,)) if sig else None


def load_exe_names():
    """(names or None, fresh): the cached names, and whether they belong to the current hoi4.exe."""
    if not EXE_NAMES.exists():
        return None, False
    lines = EXE_NAMES.read_text(encoding="ascii", errors="replace").split("\n")
    tag = exe_tag()
    names = {ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")}
    return names, tag is None or (len(lines) > 1 and lines[1] == tag)


def build_exe_names(vanilla_names):
    """Names from vanilla interface files that hoi4.exe contains as a whole printable string."""
    tag = exe_tag()
    if tag is None:
        return None
    data = (GAME / "hoi4.exe").read_bytes()
    runs = set(re.findall(rb"[\x20-\x7e]{4,}", data))
    names = set()
    for n in vanilla_names:
        try:
            b = n.encode("ascii")
        except UnicodeEncodeError:
            continue
        if len(b) >= 4:
            if b in runs:
                names.add(n)
        elif len(b) >= 2 and (b"\x00" + b + b"\x00") in data:
            names.add(n)
    DATA.mkdir(parents=True, exist_ok=True)
    tmp = EXE_NAMES.with_name(EXE_NAMES.name + ".%d.tmp" % os.getpid())
    with open(tmp, "w", encoding="ascii", newline="\n") as f:
        f.write("# check_ui.py cache: names from vanilla interface files (.gui element, named background block and "
                "window names, .gfx sprite and font names) that hoi4.exe contains as a whole printable ASCII string "
                "(runs >= 4 chars; 2-3 char names as NUL-delimited strings). Rebuilt when the tag below changes; "
                "delete it to rebuild.\n")
        f.write(tag + "\n")
        f.write("\n".join(sorted(names)) + "\n")
    replace_file(tmp, EXE_NAMES)
    log("wrote %s (%d names)" % (rel_root(EXE_NAMES), len(names)))
    return names


def vanilla_names(summaries):
    names = set()
    for S in summaries.values():
        for top, name in S.get("names", {}):
            names.add(top)
            names.add(name)
        names.update(t[1] for t in S.get("tops", ()))
        names.update(s[0] for s in S.get("sprites", ()))
        names.update(s[0] for s in S.get("fonts", ()))
    names.discard(None)
    return names


def get_exe_names(summaries):
    names, fresh = load_exe_names()
    if names is not None and fresh:
        return names
    built = build_exe_names(vanilla_names(summaries))
    return built if built is not None else names


# ----------------------------------------------------------------------------------------------------------------
# Vanilla cache
# ----------------------------------------------------------------------------------------------------------------
def signature(vfiles, lfiles):
    sig = [CACHE_VERSION, str(GAME), stat_sig(GAME / "hoi4.exe")]
    sig += [(low, vfiles[low][2], stat_sig(vfiles[low][1])) for low in sorted(vfiles)]
    sig += [(full.lower(), stat_sig(full)) for _, full, _ in lfiles]
    return sig


def load_cache(vfiles, force=False, verbose=False):
    t0 = time.time()
    lfiles = vanilla_loc_files()
    sig = signature(vfiles, lfiles)
    if not force and CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "rb") as f:
                cache = pickle.load(f)
            if cache.get("sig") == sig:
                cache["tex"] = VanillaTextures.restore(cache["tex"])
                cache["_built"] = False
                if verbose:
                    log("vanilla cache hit (%.2f s)" % (time.time() - t0))
                return cache
        except Exception:
            pass
    log("parsing vanilla into the cache (one-off, a few seconds) ...")
    summaries = {low: summarize(full, kind)[0] for low, (rel, full, origin, kind) in vfiles.items()}
    t1 = time.time()
    loc, locrels = vanilla_loc(lfiles)
    t2 = time.time()
    vocab = {"gui": set(), "gfx": set()}
    nest = set()
    for S in summaries.values():
        vocab["gui" if "nest" in S else "gfx"].update(S["keys"])
        nest.update(S.get("nest", ()))
    cache = {"sig": sig, "summaries": summaries, "loc": loc, "locrels": locrels,
             "tex": VanillaTextures(vanilla_sources()), "modsizes": {}, "vocab": vocab, "nest": nest}
    get_exe_names(summaries)
    # the game's issues without the mod: they tell mod-made issues from vanilla's own
    files = {low: Entry(rel, origin, kind, summaries[low]) for low, (rel, full, origin, kind) in vfiles.items()}
    ctx = Ctx(files, cache["tex"], LocIndex(loc, locrels), {lang: {} for lang in LOC_LANGS}, None, {}, {},
              vanilla=True)
    cache["vissues"] = {iss["vkey"] for iss in run_checks(ctx)}
    if verbose:
        log("vanilla: %d files parsed in %.1f s, localisation %.1f s, self-check %d issues %.1f s"
            % (len(vfiles), t1 - t0, t2 - t1, len(cache["vissues"]), time.time() - t2))
    cache["_built"] = True
    return cache


def save_cache(cache):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_FILE.with_name(CACHE_FILE.name + ".%d.tmp" % os.getpid())
    with open(tmp, "wb") as f:
        plain = {k: v for k, v in cache.items() if not k.startswith("_")}
        plain["tex"] = dict(cache["tex"].__dict__)     # plain data only: the cache loads from __main__ and imports
        pickle.dump(plain, f, protocol=pickle.HIGHEST_PROTOCOL)
    replace_file(tmp, CACHE_FILE)


def replace_file(tmp, dest):
    """Atomic replace; when another checker holds the file (Windows), keep theirs: it is as good."""
    try:
        os.replace(tmp, dest)
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass


# ----------------------------------------------------------------------------------------------------------------
# Checks
# ----------------------------------------------------------------------------------------------------------------
class Entry:
    __slots__ = ("rel", "origin", "kind", "S")

    def __init__(self, rel, origin, kind, S):
        self.rel, self.origin, self.kind, self.S = rel, origin, kind, S

    @property
    def is_mod(self):
        return self.origin == "mod"


def engine_optional(top, name):
    return any(re.fullmatch(t, top) and re.fullmatch(n, name) for t, n, _ in ENGINE_OPTIONAL)


def scan_markers(rel, text, markers, allow, allow_type=None):
    """Collect '# check_ui: ignore [CODES]' (per line), '# check_ui: allow-missing names' and '# check_ui: allow-type
    names' (per file)."""
    if "check_ui:" not in text:
        return
    low = rel.lower()
    for m in MARK_IGNORE.finditer(text):
        codes = set(re.findall(r"\b[EW]_[A-Z_]+\b", m.group(1)))
        markers.setdefault(low, {})[text.count("\n", 0, m.start()) + 1] = codes or None
    for m in MARK_ALLOW.finditer(text):
        allow.setdefault(low, set()).update(n for n in re.split(r"[\s,]+", m.group(1)) if n)
    if allow_type is not None:
        for m in MARK_ALLOW_TYPE.finditer(text):
            allow_type.setdefault(low, set()).update(n for n in re.split(r"[\s,]+", m.group(1)) if n)


class Ctx:
    def __init__(self, files, tex, vloc, mloc, exe, vsum, vorigin, vanilla=False, allow=None, allow_type=None,
                 vocab=None, nest=None, rps=frozenset()):
        self.allow = allow or {}            # {rel_lower: names a mod file may drop} from allow-missing comments
        self.allow_type = allow_type or {}  # {rel_lower: names that may change type} from allow-type comments
        self.vocab = vocab                  # {"gui"/"gfx": keys vanilla uses} (W_UNKNOWN_KEY)
        self.nest = nest                    # {(parent type, child type)} vanilla nests (W_NESTING)
        self.rps = rps                      # replace_path folders
        self.files = files                  # {rel_lower: Entry} of the interface being checked
        self.tex = tex                      # VanillaTextures or ModTextures
        self.vloc = vloc                    # LocIndex of vanilla
        self.mloc = mloc                    # {lang: {lower-case key: [(file, line)]}} of the mod
        self.exe = exe                      # names hoi4.exe contains, or None
        self.vsum = vsum                    # {rel_lower: summary} of the vanilla interface
        self.vorigin = vorigin              # {rel_lower: origin} of the vanilla interface
        self.vanilla = vanilla              # True for the self-check of the game without the mod


def mk(code, where, line, msg, subject, related=(), vkey=None):
    """where: an Entry or (file, origin). vkey identifies the issue across the vanilla self-check."""
    file, origin = (where.rel, where.origin) if isinstance(where, Entry) else where
    return {"code": code, "severity": "error" if code.startswith("E") else "warning", "file": file,
            "origin": origin, "line": line, "message": msg, "subject": subject,
            "related": [{"file": r[0], "origin": r[1], "line": r[2]} for r in related],
            "vkey": vkey or "%s|%s|%s" % (code, file.lower(), subject)}


FRAME_SPRITES = ("spritetype", "textspritetype", "frameanimatedspritetype")
TYPE_NAMES = {k.lower(): k for k in (
    "containerWindowType", "windowType", "iconType", "buttonType", "guiButtonType", "instantTextBoxType",
    "textBoxType", "editBoxType", "checkboxType", "gridBoxType", "listBoxType", "smoothListboxType", "scrollbarType",
    "extendedScrollbarType", "dropDownBoxType", "OverlappingElementsBoxType", "positionType", "browserType")}


def tname(klow):
    return TYPE_NAMES.get(klow, klow)


def tnames(klows):
    return "/".join(sorted(tname(k) for k in klows))


def run_checks(ctx):
    out = []
    files = ctx.files
    ordered = sorted(files.values(), key=lambda x: x.rel.lower())
    gui = [e for e in ordered if e.kind == "gui"]
    gfx = [e for e in ordered if e.kind == "gfx"]
    tex = ctx.tex
    mod_run = not ctx.vanilla

    broken = set()                          # mod files whose structure is broken: their structural checks wait
    for e in ordered:
        for line, msg in e.S["errors"]:
            note = ""
            if e.is_mod and not msg.startswith("undefined variable"):
                broken.add(e.rel.lower())
                note = " [the engine-name, type, nesting and key checks of this file wait until it parses]"
            out.append(mk("E_PARSE", e, line, msg + note, msg.split(" (")[0].split(";")[0][:80]))

    # definitions -------------------------------------------------------------------------------------------------
    sprites, fonts, sbdefs, tops = {}, {}, {}, {}
    gcolors = set()
    for e in gfx:
        for sp in e.S["sprites"]:
            sprites.setdefault(sp[0], []).append((e, sp))
        for fo in e.S["fonts"]:
            fonts.setdefault(fo[0], []).append((e, fo))
        gcolors.update(e.S["gcolors"])
    for e in gui:
        for name, line in e.S["sbdefs"]:
            sbdefs.setdefault(name, []).append((e, line))
        for klow, name, line in e.S["tops"]:
            tops.setdefault(name, []).append((e, line))
    sprites_ci, fonts_ci = {}, {}
    for n in sprites:
        sprites_ci.setdefault(n.lower(), n)
    for n in fonts:
        fonts_ci.setdefault(n.lower(), n)

    def dup(code, what, name, defs):
        rels = sorted({d[0].rel.lower() for d in defs})
        subject = "%s|%s" % (name, ",".join(rels) if len(rels) > 1 else "%s*%d" % (rels[0], len(defs)))
        mods = [d for d in defs if d[0].is_mod]
        first = mods[-1] if mods else defs[-1]
        others = [(d[0].rel, d[0].origin, d[1]) for d in defs if d is not first]
        at = ", ".join("%s%s:%s" % ("" if o == "mod" else "[%s] " % o, f, l) for f, o, l in others)
        out.append(mk(code, first[0], first[1], "%s '%s' is also defined at %s" % (what, name, at), subject, others,
                      "%s|*|%s" % (code, subject)))

    for name, defs in sprites.items():
        if len(defs) > 1:
            dup("W_DUP_SPRITE", "sprite", name, [(e, sp[2]) for e, sp in defs])
    for name, defs in fonts.items():
        if len(defs) > 1:
            dup("W_DUP_SPRITE", "font", name, [(e, fo[1]) for e, fo in defs])
    for name, defs in tops.items():
        if len({d[0].rel.lower() for d in defs}) > 1:
            dup("W_DUP_WINDOW", "top-level type", name, defs)

    # sprite and font definitions: files, formats and frames ------------------------------------------------------
    texseen = set()

    def mod_texture(e, what, key, path, p, tline, found):
        """Format of a mod texture (E/W_TEXFORMAT) and its size against the vanilla file it replaces."""
        if found[1] in texseen:             # one report per mod file (x.tga and x.dds may both lead to it)
            return
        texseen.add(found[1])
        trel = tex.rel(found)
        sz, prob = tex.info(found)
        if prob:
            out.append(mk("E_TEXFORMAT" if prob[0] == "E" else "W_TEXFORMAT", e, tline, "%s: %s \"%s\" (%s) %s"
                          % (what, key, path, trel, prob[1]), p, [(trel, "mod", 0)]))
        vf = tex.v.find(p)
        vsz = tex.v.size(vf) if vf and sz else None
        if vsz and tuple(vsz) != tuple(sz):
            out.append(mk("W_TEXOVERRIDE", (trel, "mod"), 0, "%dx%d, but the %s file it replaces is %dx%d (used by %s "
                          "in %s; vanilla sprites and .gui sizes expect the vanilla size)"
                          % (sz[0], sz[1], vf[0], vsz[0], vsz[1], what, e.rel), p, [(e.rel, e.origin, tline)]))

    for e in gfx:
        for name, klow, line, frames, texs in e.S["sprites"]:
            main = None
            for key, path, tline in texs:
                p = norm_path(path).lower()
                found = tex.find(p)
                if not found:
                    out.append(mk("E_TEXTURE", e, tline, "sprite '%s': %s \"%s\" is in neither the mod nor the game%s"
                                  % (name, key, path, tex.why_missing(p)), "%s|%s" % (name, p)))
                    continue
                if main is None and key.lower() in ("texturefile", "texturefile1"):
                    main = found
                if mod_run and found[0] == "mod":
                    mod_texture(e, "sprite '%s'" % name, key, path, p, tline, found)
            if frames and frames > 1 and main:
                sz = tex.size(main)
                if sz and sz[0] % int(frames):
                    rel = [(tex.rel(main), "mod", 0)] if main[0] == "mod" else []
                    out.append(mk("E_FRAMES", e, line, "sprite '%s': texture is %dx%d, the width is not divisible by "
                                  "noOfFrames = %d" % (name, sz[0], sz[1], frames), name, rel))
        for name, line, ffiles, colors in e.S["fonts"] + e.S["overrides"]:
            for path, fl in ffiles:
                p = norm_path(path).lower()
                p = p[:-4] if p.endswith(".fnt") else p
                miss = []
                if not tex.find(p + ".fnt"):
                    miss.append(".fnt")
                atlas = None
                for ext in IMAGE_EXT:
                    atlas = tex.find(p + ext)
                    if atlas:
                        break
                if not atlas:
                    miss.append(".dds")
                elif mod_run and atlas[0] == "mod":
                    sz, prob = tex.info(atlas)
                    if prob and atlas[1] not in texseen:
                        texseen.add(atlas[1])
                        trel = tex.rel(atlas)
                        out.append(mk("E_TEXFORMAT" if prob[0] == "E" else "W_TEXFORMAT", e, fl, "font '%s': atlas "
                                      "%s %s" % (name, trel, prob[1]), p, [(trel, "mod", 0)]))
                if miss:
                    out.append(mk("E_TEXTURE", e, fl, "font '%s': font file \"%s\" has no %s"
                                  % (name, path, " / ".join(miss)), "%s|%s" % (name, p)))
        for name, line, ffiles, colors in e.S["overrides"]:
            if name not in fonts:
                out.append(mk("W_FONT_OVERRIDE", e, line, "bitmapfont_override for '%s', which no bitmapfont defines"
                              % name, name))

    # .gui references --------------------------------------------------------------------------------------------
    frame_cache = {}

    def sprite_frame(sname):
        """(frame w, frame h, related [(file, origin, line)] of the mod .gfx / texture behind it) or None."""
        if sname not in frame_cache:
            res = None
            defs = sprites.get(sname)
            if defs:
                de, (name, klow, line, frames, texs) = defs[-1]
                if klow in FRAME_SPRITES and texs:
                    found = tex.find(norm_path(texs[0][1]).lower())
                    sz = tex.size(found) if found else None
                    if sz:
                        f = int(frames) if frames and frames > 0 else 1
                        rel = [(de.rel, "mod", line)] if de.is_mod else []
                        if found[0] == "mod":
                            rel.append((tex.rel(found), "mod", 0))
                        res = (sz[0] / f, sz[1], rel)
            frame_cache[sname] = res
        return frame_cache[sname]

    definer = {}
    for low, S in ctx.vsum.items():
        if low.endswith(".gfx"):
            for sp in S["sprites"]:
                definer.setdefault(sp[0], low)
            for fo in S["fonts"]:
                definer.setdefault(fo[0], low)

    def cause(name):
        low = definer.get(name)
        if low and low in files and files[low].is_mod:
            return [(files[low].rel, "mod", 0)]
        return []

    for e in gui:
        S = e.S
        for kind, key, val, line, here, etype in S["refs"]:
            subj = "%s|%s=%s" % (here, key.lower(), val)
            el = "%s %s" % (etype, here)
            if kind == "sprite":
                if val not in sprites:
                    ci = sprites_ci.get(val.lower())
                    if ci:
                        out.append(mk("W_CASE", e, line, "%s: %s \"%s\" matches sprite '%s' only ignoring case"
                                      % (el, key, val, ci), subj))
                    else:
                        out.append(mk("E_SPRITE", e, line, "%s: %s \"%s\" is defined in no .gfx"
                                      % (el, key, val), subj, cause(val)))
            elif kind == "font":
                if val not in fonts:
                    ci = fonts_ci.get(val.lower())
                    if ci:
                        out.append(mk("W_CASE", e, line, "%s: %s \"%s\" matches font '%s' only ignoring case"
                                      % (el, key, val, ci), subj))
                    else:
                        out.append(mk("E_FONT", e, line, "%s: %s \"%s\" is no bitmapfont" % (el, key, val), subj,
                                      cause(val)))
            elif kind == "scrollbar":
                if val not in sbdefs:
                    out.append(mk("E_SCROLLBAR", e, line, "%s: %s \"%s\" is no scrollbarType / "
                                  "extendedScrollbarType" % (el, key, val), subj))
            elif kind == "texture":
                p = norm_path(val).lower()
                found = tex.find(p)
                if not found:
                    out.append(mk("E_TEXTURE", e, line, "%s: %s \"%s\" is in neither the mod nor the game%s"
                                  % (el, key, val, tex.why_missing(p)), subj))
                elif mod_run and found[0] == "mod":
                    mod_texture(e, el, key, val, p, line, found)
            elif kind == "loc":
                low = val.lower()
                missing = [lang for lang in LOC_LANGS if low not in ctx.mloc[lang] and not ctx.vloc.has(lang, low)]
                if missing:
                    out.append(mk("W_LOC", e, line, "%s: %s \"%s\" is missing in %s"
                                  % (el, key, val, " and ".join(missing)), subj))
            elif kind == "locw":
                low = val.lower()
                have = [lang for lang in LOC_LANGS if low in ctx.mloc[lang] or ctx.vloc.has(lang, low)]
                if have and len(have) < len(LOC_LANGS):
                    out.append(mk("W_LOC", e, line, "%s: %s \"%s\" is a loc key in %s but missing in %s"
                                  % (el, key, val, " and ".join(have),
                                     " and ".join(l for l in LOC_LANGS if l not in have)), subj))
        for here, etype, which, x, y, line in S["pos"]:
            bad = [(a, v) for a, v in (("x", x), ("y", y)) if v is not None and abs(v) > OFFSCREEN and v != HIDE]
            if bad:
                out.append(mk("W_OFFSCREEN", e, line, "%s %s: %s %s (the hide convention is x = %d y = %d)"
                              % (etype, here, which, " ".join("%s = %g" % b for b in bad), HIDE, HIDE),
                              "%s|%s" % (here, which.lower())))
        for here, etype, font, code, line in S["colors"]:
            fdefs = fonts.get(font)
            if fdefs:
                own = set(fdefs[-1][1][3])
                if code not in own and code not in gcolors:
                    out.append(mk("W_COLOR", e, line, "%s %s: text_color_code = %s, but font '%s' has only {%s} and "
                                  "the global textcolors lack it" % (etype, here, code, font, " ".join(sorted(own))),
                                  "%s|%s|%s" % (here, font, code)))
        for here, etype, sname, w, h, scale, line in S["texsize"]:
            fr = sprite_frame(sname)
            if not fr or fr[0] <= 0 or fr[1] <= 0 or scale <= 0:
                continue
            fw, fh = fr[0] * scale, fr[1] * scale
            if max(w / fw, fw / w, h / fh, fh / h) > TEXSIZE_RATIO:
                out.append(mk("W_TEXSIZE", e, line, "%s %s: size %gx%g, but a frame of sprite '%s' is %gx%g%s"
                              % (etype, here, w, h, sname, fr[0], fr[1],
                                 " (x scale %g)" % scale if scale != 1 else ""), "%s|%s" % (here, sname), fr[2]))

    # the loading screen is built before the other interface files are read ---------------------------------------
    ls = files.get(LOADSCREEN_GUI)
    if ls is not None:
        for kind, key, val, line, here, etype in ls.S["refs"]:
            if kind not in ("sprite", "font"):
                continue
            defs = (sprites if kind == "sprite" else fonts).get(val)
            if defs and not any(d[0].rel.lower() in LOADSCREEN_GFX for d in defs):
                de, d = defs[-1]
                out.append(mk("E_LOADSCREEN", ls, line, "%s %s: %s \"%s\" is defined only in %s, which the game reads "
                              "after the loading screen; declare it in %s" % (etype, here, key, val, de.rel,
                                                                              LOADSCREEN_GFX[kind == "font"]),
                              "%s|%s" % (here, val), [(de.rel, de.origin, d[2] if kind == "sprite" else d[1])]))

    if not mod_run:
        return out

    # vanilla sprites whose geometry the mod changed while vanilla .gui files still use them -----------------------
    vdef = {}
    for low in sorted(ctx.vsum):
        if low.endswith(".gfx"):
            for sp in ctx.vsum[low]["sprites"]:
                vdef[sp[0]] = sp
    users = {}
    for e in gui:
        if not e.is_mod:
            for kind, key, val, line, here, etype in e.S["refs"]:
                if kind == "sprite":
                    users.setdefault(val, {}).setdefault(e.rel, (e.origin, line))

    def geometry(sp, lookup):
        name, klow, line, frames, texs = sp
        if klow not in FRAME_SPRITES or not texs:
            return None
        found = lookup.find(norm_path(texs[0][1]).lower())
        sz = lookup.size(found) if found else None
        if not sz:
            return None
        f = int(frames) if frames and frames > 0 else 1
        return (sz[0] / f, sz[1], f), found

    for sname in sorted(users):
        defs, vsp = sprites.get(sname), vdef.get(sname)
        if not defs or not vsp:
            continue
        de, sp = defs[-1]
        eg = geometry(sp, tex)
        if not eg or not (de.is_mod or eg[1][0] == "mod"):
            continue
        vg = geometry(vsp, tex.v)
        if not vg or (abs(vg[0][0] - eg[0][0]) < 0.01 and vg[0][1] == eg[0][1] and vg[0][2] == eg[0][2]):
            continue
        rel = []
        if eg[1][0] == "mod":
            rel.append((tex.rel(eg[1]), "mod", 0))
        us = sorted(users[sname].items())
        rel += [(f, o, l) for f, (o, l) in us]
        out.append(mk("W_SPRITE_GEOMETRY", de, sp[2], "sprite '%s': a frame is now %gx%g (%d frame%s%s), in vanilla "
                      "%gx%g (%d frame%s); vanilla .gui files the mod does not replace still use it: %s (copy and "
                      "adapt them, or keep the vanilla frame size and frame count)"
                      % (sname, eg[0][0], eg[0][1], eg[0][2], "s" if eg[0][2] != 1 else "",
                         ", texture %s" % tex.rel(eg[1]) if eg[1][0] == "mod" else "",
                         vg[0][0], vg[0][1], vg[0][2], "s" if vg[0][2] != 1 else "",
                         ", ".join("%s:%d" % (f, l) for f, (o, l) in us[:6]) + (" and %d more" % (len(us) - 6)
                                                                               if len(us) > 6 else "")),
                      sname, rel))

    # what a mod file replacing a vanilla file lost or changed ---------------------------------------------------
    names_by_top, types_by_top = {}, {}     # top-level types are global: a window may move to another file
    for e in gui:
        for (top, name) in e.S["names"]:
            names_by_top.setdefault(top, set()).add(name)
        for (top, name), ts in e.S["types"].items():
            types_by_top.setdefault(top, {}).setdefault(name, set()).update(ts)
    for low, e in sorted(files.items()):
        if not e.is_mod or low not in ctx.vsum or low in broken:
            continue
        V = ctx.vsum[low]
        vo = ctx.vorigin.get(low, "vanilla")
        allowed = ctx.allow.get(low, ())
        atypes = ctx.allow_type.get(low, ())
        if e.kind == "gui" and ctx.exe is not None:
            have = set(e.S["names"])
            gone = set()
            for klow, top, line in V["tops"]:
                if top in ctx.exe and top not in tops:
                    gone.add(top)
                    if top in allowed or engine_optional(top, top):
                        continue
                    out.append(mk("E_ENGINE_NAME", e, 1, "the vanilla top-level %s '%s' is gone (hoi4.exe looks "
                                  "it up)" % (tname(klow), top), top, [(e.rel, vo, line)]))
            top_line = {t[1]: t[2] for t in e.S["tops"]}
            for (top, name), (klow, line) in sorted(V["names"].items(), key=lambda kv: kv[1][1]):
                if top in gone or name not in ctx.exe or name in allowed or engine_optional(top, name):
                    continue
                if name != top and name not in names_by_top.get(top, ()):
                    other = sorted({t for t, n in have if n == name})
                    what = "background block" if klow == "background" else tname(klow)
                    out.append(mk("E_ENGINE_NAME", e, top_line.get(top, 1), "%s '%s' of window '%s' (vanilla line "
                                  "%d) is gone%s; hoi4.exe looks this name up%s"
                                  % (what, name, top, line, " (now only in %s)" % ", ".join(other[:3]) if other
                                     else "", " (keep the block, point it at a transparent or flat sprite)"
                                     if klow == "background" else ""), "%s/%s" % (top, name), [(e.rel, vo, line)]))
                    continue
                vt = V["types"].get((top, name), {klow})
                mt = types_by_top.get(top, {}).get(name)
                if mt and not (mt & vt) and name not in atypes:
                    mline = e.S["names"].get((top, name), (None, top_line.get(top, 1)))[1]
                    out.append(mk("E_ENGINE_TYPE", e, mline, "%s '%s' of window '%s' was %s in vanilla (line %d); "
                                  "hoi4.exe looks this name up with its type (keep the type, or add '# check_ui: "
                                  "allow-type %s' when you know the engine accepts it)"
                                  % (tnames(mt), name, top, tnames(vt), line, name),
                                  "%s/%s|type" % (top, name), [(e.rel, vo, line)]))
        elif e.kind == "gfx":
            lost = [("sprite", s[0], s[2]) for s in V["sprites"] if s[0] not in sprites and s[0] not in allowed]
            lost += [("font", f[0], f[1]) for f in V["fonts"] if f[0] not in fonts and f[0] not in allowed]
            for what, name, line in lost:
                hit = ctx.exe is not None and name in ctx.exe
                out.append(mk("E_ENGINE_GFX" if hit else "W_GFX_DROPPED", e, 1, "%s '%s' (vanilla line %d) is "
                              "no longer defined anywhere%s" % (what, name, line, "; hoi4.exe looks it up" if hit
                                                                else ""), name, [(e.rel, vo, line)]))

    # typos and misplaced braces in mod files --------------------------------------------------------------------
    for e in ordered:
        if not e.is_mod or e.rel.lower() in broken:
            continue
        if ctx.vocab:
            voc = ctx.vocab.get(e.kind, set())
            other = ctx.vocab.get("gfx" if e.kind == "gui" else "gui", set())
            for klow, (key, line, w) in sorted(e.S["keys"].items(), key=lambda kv: kv[1][1]):
                if klow not in voc:
                    out.append(mk("W_UNKNOWN_KEY", e, line, "key '%s'%s: no vanilla .%s uses it%s"
                                  % (key, " in %s" % w.lstrip("/") if w else "", e.kind,
                                     " (it is a .%s key)" % ("gfx" if e.kind == "gui" else "gui") if klow in other
                                     else " (a typo?)"), klow))
        if ctx.nest and e.kind == "gui":
            for (p, c), (line, w) in sorted(e.S["nest"].items(), key=lambda kv: kv[1][0]):
                if (p, c) not in ctx.nest:
                    out.append(mk("W_NESTING", e, line, "%s sits inside a %s; no vanilla file nests %s in %s (a "
                                  "misplaced brace?)" % (w.replace(" /", " "), tname(p), tname(c), tname(p)),
                                  "%s>%s|%s" % (p, c, w)))
    for iss in out:
        if iss["code"] != "E_PARSE" and iss["origin"] == "mod" and iss["file"].lower() in broken:
            iss["message"] += " [after a parse error in this file: fix E_PARSE first]"
    return out


# ----------------------------------------------------------------------------------------------------------------
# Mod files: encoding and localisation
# ----------------------------------------------------------------------------------------------------------------
def check_encoding(rel, raw, kind):
    out = []
    where = (rel, "mod")
    bom = raw.startswith(b"\xef\xbb\xbf")
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError as ex:
        out.append(mk("E_ENCODING", where, raw.count(b"\n", 0, ex.start) + 1, "not valid UTF-8", "utf8"))
    if kind in ("gui", "gfx"):
        if bom:
            out.append(mk("E_ENCODING", where, 1, "UTF-8 BOM in a .%s (write UTF-8 without BOM)" % kind, "bom"))
        body = raw[3:] if bom else raw
        for i, ln in enumerate(body.split(b"\n"), 1):
            m = re.search(rb"[\x80-\xff]", ln)
            if m:                           # one issue per line, keyed by its text: a new line is a new issue
                comment = b"#" in STRING_RE_B.sub(b'""', ln[:m.start()])
                text = ln.decode("utf-8", "replace")
                at = len(ln[:m.start()].decode("utf-8", "replace"))
                snip = text[max(0, at - 24):at + 24].strip()
                out.append(mk("W_ENCODING", where, i, "non-ASCII text%s (keep .%s files ASCII): ...%s..."
                              % (" in a comment" if comment else "", kind, ascii_safe(snip)),
                              "nonascii|%08x" % zlib.crc32(ln.strip())))
    elif not bom:
        out.append(mk("E_ENCODING", where, 1, "localisation file without the UTF-8 BOM (write encoding utf-8-sig)",
                      "nobom"))
    if b"\r\n" in raw:
        out.append(mk("W_ENCODING", where, raw[:raw.index(b"\r\n")].count(b"\n") + 1,
                      "CRLF line ends (%d lines); the mod writes LF" % raw.count(b"\r\n"), "crlf"))
    return out


def mod_loc_files():
    """[(abs, rel to the mod root, rel to localisation/ in lower case)]."""
    out = []
    base = ROOT / "localisation"
    for dirpath, _, filenames in os.walk(base):
        for fn in sorted(filenames):
            if fn.lower().endswith(".yml"):
                full = os.path.join(dirpath, fn)
                out.append((full, "localisation/" + os.path.relpath(full, base).replace("\\", "/"),
                            os.path.relpath(full, base).replace("\\", "/").lower()))
    return out


def mod_localisation(files, vloc, markers, allow):
    """(issues, {lang: {lower key: [(file, line)]}} for LOC_LANGS)."""
    out = []
    keys = {lang: {} for lang in LOC_LANGS}
    seen = {}
    for full, rel, _ in files:
        fn = os.path.basename(full)
        text, raw = read_text(full)
        scan_markers(rel, text, markers, allow)
        out += check_encoding(rel, raw, "yml")
        where = (rel, "mod")
        lang, hl, first = yml_header(text)
        m = re.search(r"_l_([a-z_]+)\.yml$", fn.lower())
        if lang is None:
            out.append(mk("E_LOC_FILE", where, hl or 1, "the first line must be l_<language>: (found \"%s\")"
                          % first[:40], "header"))
        if not m:
            out.append(mk("E_LOC_FILE", where, 1, "the file name must end in _l_<language>.yml", "name"))
        elif lang and m.group(1) != lang:
            out.append(mk("E_LOC_FILE", where, hl, "the file name says l_%s, the first line l_%s"
                          % (m.group(1), lang), "mismatch"))
        lang = lang or (m.group(1) if m else None)
        if lang is None:
            continue
        replace = "/replace/" in "/" + rel.lower()
        known = seen.setdefault(lang, {})
        for key, line in yml_keys(text):
            low = key.lower()
            if low in known:
                f0, l0 = known[low]
                out.append(mk("W_LOC_DUP", where, line, "%s is also defined at %s:%d" % (key, f0, l0), key,
                              [(f0, "mod", l0)]))
            else:
                known[low] = (rel, line)
            if lang in keys:
                keys[lang].setdefault(low, []).append((rel, line))
                if not replace and vloc.has(lang, low):
                    out.append(mk("W_LOC_OVERRIDE", where, line, "%s redefines a vanilla key outside a replace/ "
                                  "folder (move it to localisation/%s/replace/)" % (key, lang), key))
    return out, keys


# ----------------------------------------------------------------------------------------------------------------
# Baseline, filtering, running
# ----------------------------------------------------------------------------------------------------------------
def bkey(iss):
    return "%s\t%s\t%s" % (iss["code"], iss["file"], re.sub(r"[\t\r\n]", " ", iss["subject"]))


def read_baseline():
    """{key: full line}; key = CODE<TAB>file<TAB>subject."""
    out = {}
    if BASELINE.exists():
        for ln in BASELINE.read_text(encoding="utf-8").split("\n"):
            parts = ln.split("\t")
            if ln and not ln.startswith("#") and len(parts) >= 3:
                out["\t".join(parts[:3])] = ln
    return out


class BaselineLock:
    """A lock file around the baseline's read-modify-write, so two --baseline runs do not lose each other's
    entries. A lock older than LOCK_STALE seconds (a killed run) is taken over."""
    LOCK_WAIT, LOCK_STALE = 30.0, 120.0

    def __enter__(self):
        DATA.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        while True:
            try:
                fd = os.open(str(BASELINE_LOCK), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, ("%d\n" % os.getpid()).encode("ascii"))
                os.close(fd)
                return self
            except FileExistsError:
                try:
                    if time.time() - os.path.getmtime(BASELINE_LOCK) > self.LOCK_STALE:
                        os.remove(BASELINE_LOCK)
                        continue
                except OSError:
                    continue
                if time.time() - t0 > self.LOCK_WAIT:
                    raise SystemExit("check_ui: %s is held by another run; retry, or delete it if no check_ui "
                                     "is running" % rel_root(BASELINE_LOCK))
                time.sleep(0.2)

    def __exit__(self, *exc):
        try:
            os.remove(BASELINE_LOCK)
        except OSError:
            pass


def write_baseline(issues, keep=None):
    """Write the issues plus the kept {key: line} rows; returns the number of entries."""
    DATA.mkdir(parents=True, exist_ok=True)
    rows = dict(keep or {})
    for iss in issues:
        rows[bkey(iss)] = "%s\t# line %s: %s" % (bkey(iss), iss["line"], ascii_safe(iss["message"])[:200])
    tmp = BASELINE.with_name(BASELINE.name + ".%d.tmp" % os.getpid())
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write("# check_ui.py baseline: known issues, not reported as new. One per line:\n"
                "# CODE<TAB>file<TAB>subject<TAB># line and message when recorded.\n"
                "# Add the current issues: python tools/check_ui.py --baseline (fix issues rather than baseline them);\n"
                "# drop entries that no longer occur: python tools/check_ui.py --prune-baseline\n")
        for k in sorted(rows):
            f.write(rows[k] + "\n")
    os.replace(tmp, BASELINE)
    return len(rows)


def ascii_safe(s):
    return s.encode("ascii", "backslashreplace").decode("ascii")


def rel_root(p):
    try:
        return Path(p).resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(p)


def file_filter(patterns):
    pats = []
    for p in patterns:
        p = p.strip()
        if p:
            if Path(p).is_absolute():
                p = rel_root(p)
            pats.append(norm_path(p).lower())

    def match(f):
        f = f.lower()
        base = f.rsplit("/", 1)[-1]
        return any(f == p or base == p or f.endswith("/" + p) or fnmatch.fnmatch(f, p) or fnmatch.fnmatch(base, p)
                   for p in pats)
    return match


def log(msg):
    print("[check_ui] " + ascii_safe(msg), file=sys.stderr)


def check(files=None, include_all=False, use_baseline=True, rebuild=False, verbose=False, stats=None):
    """Run every check. Returns issue dicts with a "status" (new, baselined, ignored, inherited, vanilla); without
    include_all only the new ones. files: mod files (paths, names or globs) to restrict the result to."""
    t0 = time.time()
    if not (GAME / "interface" / "core.gfx").is_file():
        raise SystemExit("check_ui: no game at %s (set HOI4_DIR to the Hearts of Iron IV folder)" % ascii_safe(str(GAME)))
    vfiles = vanilla_files()
    cache = load_cache(vfiles, force=rebuild, verbose=verbose)
    t1 = time.time()
    tstate = cache["tex"].state()
    summaries = cache["summaries"]
    rps, issues = replace_paths()
    eff, vorigin = {}, {}
    for low, (rel, full, origin, kind) in vfiles.items():
        vorigin[low] = origin
        if not hidden_by_replace(low, rps):
            eff[low] = Entry(rel, origin, kind, summaries[low])
    markers, allow, allow_type = {}, {}, {}
    inherited = set()
    mod_iface = interface_files(ROOT)
    for low, (rel, full) in sorted(mod_iface.items()):
        S, raw = summarize(full, low[-3:])
        eff[low] = Entry(rel, "mod", low[-3:], S)
        issues += check_encoding(rel, raw, low[-3:])
        scan_markers(rel, raw.decode("utf-8", "replace"), markers, allow, allow_type)
        if low in vfiles:                   # the vanilla original's own encoding issues count as inherited
            try:
                inherited.update(i["vkey"] for i in check_encoding(rel, Path(vfiles[low][1]).read_bytes(), low[-3:]))
            except OSError:
                pass
    mod_locs = mod_loc_files()
    vloc = LocIndex(cache["loc"], cache["locrels"], [r for _, _, r in mod_locs])
    loc_issues, mloc = mod_localisation(mod_locs, vloc, markers, allow)
    issues += loc_issues
    exe = get_exe_names(summaries)
    if exe is None:
        log("no tools/data/exe_names.txt and no hoi4.exe: E_ENGINE_NAME / E_ENGINE_GFX are skipped")
    root = str(ROOT)
    cache["modsizes"] = {k: v for k, v in cache.get("modsizes", {}).items() if k.startswith(root)}
    tex = ModTextures(cache["tex"], rps, cache["modsizes"])
    ctx = Ctx(eff, tex, vloc, mloc, exe, summaries, vorigin, allow=allow, allow_type=allow_type,
              vocab=cache["vocab"], nest=cache["nest"], rps=rps)
    issues += run_checks(ctx)
    t2 = time.time()
    if cache["_built"] or tex.dirty or cache["tex"].state() != tstate:
        save_cache(cache)

    base = read_baseline() if use_baseline else {}
    if stats is not None:
        stats["stale_baseline"] = len(set(base) - {bkey(i) for i in issues})
    for iss in issues:
        mark = markers.get(iss["file"].lower(), {}).get(iss["line"], False) if iss["origin"] == "mod" else False
        if mark is None or (mark and iss["code"] in mark):
            iss["status"] = "ignored"
        elif iss["vkey"] in cache["vissues"] or iss["vkey"] in inherited:
            iss["status"] = "inherited" if iss["origin"] == "mod" else "vanilla"
        elif bkey(iss) in base:
            iss["status"] = "baselined"
        else:
            iss["status"] = "new"
        del iss["vkey"]
    if files:
        match = file_filter(files)
        issues = [i for i in issues if match(i["file"]) or any(match(r["file"]) for r in i["related"])]
    sev = {"error": 0, "warning": 1}
    issues.sort(key=lambda i: (sev[i["severity"]], CODE_ORDER.get(i["code"], 1), i["code"], i["origin"] != "mod",
                               i["file"].lower(), i["line"]))
    if stats is not None:
        stats.update({"mod_interface_files": len(mod_iface), "mod_loc_files": len(mod_locs), "effective_files": len(eff),
                      "cache": "built" if cache["_built"] else "hit", "seconds": round(time.time() - t0, 2),
                      "cache_seconds": round(t1 - t0, 2), "check_seconds": round(t2 - t1, 2)})
        for st in STATUSES:
            stats[st] = sum(1 for i in issues if i["status"] == st)
    if not include_all:
        issues = [i for i in issues if i["status"] == "new"]
    return issues


def where(i):
    return "%s%s:%s" % ("" if i["origin"] == "mod" else "[%s] " % i["origin"], i["file"], i["line"])


def report(issues, stats, limit=30):
    w = sys.stdout.write
    w("check_ui: %d mod interface files, %d mod loc files, %d effective interface files, cache %s, %.1f s\n"
      % (stats["mod_interface_files"], stats["mod_loc_files"], stats["effective_files"], stats["cache"],
         stats["seconds"]))
    for sev, title in (("error", "ERRORS"), ("warning", "WARNINGS")):
        group = [i for i in issues if i["severity"] == sev]
        if not group:
            continue
        w("\n%s (%d)\n" % (title, len(group)))
        for code in dict.fromkeys(i["code"] for i in group):
            rows = [i for i in group if i["code"] == code]
            w("  %s (%d): %s\n" % (code, len(rows), CODES.get(code, "")))
            width = min(56, max(len(where(i)) for i in rows))
            for i in rows[:limit] if limit > 0 else rows:
                st = "" if i["status"] == "new" else "{%s} " % i["status"]
                why = ""
                if i["related"] and i["code"] in ("E_SPRITE", "E_FONT", "E_FRAMES", "W_TEXSIZE"):
                    why = " (%s %s)" % ({"E_FRAMES": "mod texture", "W_TEXSIZE": "mod files:"}.get(i["code"],
                                                                                                "caused by"),
                                        ", ".join(r["file"] for r in i["related"]))
                w("    %-*s  %s%s%s\n" % (width, where(i), st, ascii_safe(i["message"]), why))
            if 0 < limit < len(rows):
                w("    ... %d more %s (--limit 0 or --json shows all)\n" % (len(rows) - limit, code))
    shown = {i["status"] for i in issues}
    hidden = ["%d %s" % (stats[k], k) for k in STATUSES[1:] if stats.get(k) and k not in shown]
    if hidden:
        w("\nnot shown: %s (--all shows them)\n" % ", ".join(hidden))
    if stats.get("stale_baseline"):
        w("baseline: %d entries no longer occur (python tools/check_ui.py --prune-baseline drops them)\n"
          % stats["stale_baseline"])
    ne = sum(1 for i in issues if i["status"] == "new" and i["severity"] == "error")
    nw = sum(1 for i in issues if i["status"] == "new" and i["severity"] == "warning")
    w("\nresult: %d new error%s, %d new warning%s\n" % (ne, "" if ne == 1 else "s", nw, "" if nw == 1 else "s"))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Static checker for the mod's .gui / .gfx / localisation.",
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="\n\n".join(__doc__.split("\n\n")[1:3]))
    ap.add_argument("--files", help="comma-separated mod files (path, name or glob): only issues in them or caused "
                                    "by them")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--strict", action="store_true", help="exit 1 on new warnings too")
    ap.add_argument("--all", action="store_true", help="also show baselined, ignored, inherited and vanilla-only issues")
    ap.add_argument("--baseline", action="store_true", help="LEAD ONLY: record the current new issues as known "
                                                            "(with --files: only those files' entries are replaced)")
    ap.add_argument("--prune-baseline", action="store_true", help="LEAD ONLY: drop baseline entries that no longer "
                                                                  "occur (adds nothing; refused while a mod file "
                                                                  "does not parse)")
    ap.add_argument("--no-baseline", action="store_true", help="ignore the baseline file")
    ap.add_argument("--only", help="comma-separated codes to report, e.g. E_SPRITE,W_LOC")
    ap.add_argument("--limit", type=int, default=30, help="rows shown per code (0 = all; --json always has all)")
    ap.add_argument("--skip", help="comma-separated codes not to report")
    ap.add_argument("--rebuild-cache", action="store_true", help="re-parse vanilla even if nothing changed")
    ap.add_argument("--list-codes", action="store_true", help="print the issue codes and exit")
    ap.add_argument("--mod", help="check another mod folder instead of this repository (tests); the baseline is "
                                  "not used then")
    ap.add_argument("-v", "--verbose", action="store_true", help="timings on stderr")
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(errors="backslashreplace")
    except AttributeError:
        pass
    if a.list_codes:
        for c, d in CODES.items():
            print("%-16s %s" % (c, d))
        return 0
    if a.mod:
        global ROOT
        ROOT = Path(a.mod).resolve()
        if a.baseline or a.prune_baseline:
            ap.error("--baseline / --prune-baseline cannot be combined with --mod")
        a.no_baseline = True
    files = [f for f in (a.files or "").split(",") if f.strip()] or None
    stats = {}
    if a.baseline or a.prune_baseline:
        issues = check(include_all=True, use_baseline=False, rebuild=a.rebuild_cache, verbose=a.verbose, stats=stats)
        current = {bkey(i) for i in issues}
        broken = sorted({i["file"] for i in issues if i["code"] == "E_PARSE" and i["origin"] == "mod"
                         and not i["message"].startswith("undefined variable")})
        if a.prune_baseline and broken:
            print("check_ui: not pruning: %s do%s not parse, so their baselined issues may vanish only for now; fix "
                  "E_PARSE first" % (", ".join(broken), "es" if len(broken) == 1 else ""))
            return 1
        with BaselineLock():
            old = read_baseline()
            if a.prune_baseline:
                keep = {k: v for k, v in old.items() if k in current}
                n = write_baseline([], keep)
                print("check_ui: %s: %d entries kept, %d no longer occur and were dropped"
                      % (rel_root(BASELINE), n, len(old) - len(keep)))
                return 0
            new = [i for i in issues if i["status"] == "new"]
            keep = {}
            if files:
                match = file_filter(files)
                keep = {k: v for k, v in old.items() if not match(k.split("\t")[1])}
                new = [i for i in new if match(i["file"]) or any(match(r["file"]) for r in i["related"])]
            n = write_baseline(new, keep)
        print("check_ui: wrote %s: %d entries (%d errors, %d warnings recorded now%s)%s"
              % (rel_root(BASELINE), n, sum(i["severity"] == "error" for i in new),
                 sum(i["severity"] == "warning" for i in new), ", %d kept for other files" % len(keep) if keep else "",
                 "; WARNING: %s do not parse" % ", ".join(broken) if broken else ""))
        return 0
    issues = check(files=files, include_all=a.all, use_baseline=not a.no_baseline, rebuild=a.rebuild_cache,
                   verbose=a.verbose, stats=stats)
    if a.only:
        only = {c.strip().upper() for c in a.only.split(",")}
        issues = [i for i in issues if i["code"] in only]
    if a.skip:
        skip = {c.strip().upper() for c in a.skip.split(",")}
        issues = [i for i in issues if i["code"] not in skip]
    if a.json:
        json.dump({"stats": stats, "issues": issues}, sys.stdout, indent=1, ensure_ascii=True)
        sys.stdout.write("\n")
    else:
        report(issues, stats, a.limit)
    new = [i for i in issues if i["status"] == "new"]
    return 1 if any(i["severity"] == "error" for i in new) or (a.strict and new) else 0


if __name__ == "__main__":
    sys.exit(main())
