#!/usr/bin/env python3
"""Offline renderer for HOI4 1.19 .gui windows (Twilight of the Union tooling): see a window without the game.

Draws a window (or a template such as savegame_item) the way the engine lays it out, from the EFFECTIVE interface:
vanilla interface/**/*.gui|gfx (plus unzipped DLC and pdx_online_assets interface files), mod files with the same
relative path replacing vanilla ones, mod-only files added. Sprites (spriteType, corneredTile 9-slice, textSprite,
frameAnimated first frame, progressbar, maskedShield as a grey flag, pie charts), bitmap fonts (.fnt + atlas, fontfiles
merged glyph by glyph, 0xAARRGGBB tint, textcolors, kerning, bitmapfont_override for l_<lang>) and localisation
(mod replace/ > vanilla replace/ > mod > vanilla; $KEY$, newline escapes, section-sign colour codes, pound-sign text
icons) are resolved like the game. Nothing in the game or mod folder is written.

    python tools/render_gui.py <window>[,<window>...] [options]       several windows are drawn in order
    python tools/render_gui.py <substring> --list                     window/template names containing <substring>

    --file interface/x.gui        take the window from this file (when the name exists in several files)
    --res 1920x1080               screen size (default 1920x1080; the UI does not scale with the screen)
    --scale 1                     UI scale: layout at res/scale, then the image is scaled up
    --lang russian|english|...    localisation and font overrides (default russian)
    --bg map|menu|black|none|<png>  backdrop: the in-game map, the main menu (the effective frontend_background
                                  window), black (default), transparent, or any image (cover-scaled)
    --state hover:<el>,pressed:<el>,checked:<el>,disabled:<el>,frame:<el>=N   (repeatable)
                                  buttons: frame 1 normal, 2 hover, 3 pressed, 4 disabled (as far as the sprite has
                                  frames; 1-frame sprites with a buttonstate effect are brightened/darkened);
                                  checkboxes: frame 1 off, 2 checked; frame:<el>=N picks any frame (tabs, toggles)
    --shown                       windows that slide in (show_position + animation_type) are drawn shown, and
                                  dropdowns are drawn open
    --hide <el>,<el>              do not draw these elements (fnmatch patterns, !pattern re-includes; repeatable),
                                  e.g. --hide "menu_settings_*,!menu_settings_ingame,!menu_settings_VIDEO"
    --text <el>=<text or KEY>     the text of an engine-filled box or button (repeatable; KEY = localisation key)
    --prop <el>.<key>=<value>     override a property of the element: a plain key (icon.spriteType=GFX_x,
                                  Title.font=hoi_20bs), a key inside a block (bottom_Window.position.y=400,
                                  options_grid.size.width=350) or a whole block (bottom_Window.position={ x=0 y=400 });
                                  a plain value for a block key is refused with a WARN
    --move <el>=dx,dy             shift an element (and its children) by dx,dy px after layout (repeatable)
    --grid <gridbox>=<template>[:count]   fill a gridbox with copies of a template (default: as many as fit);
                                  follows max_slots_horizontal/_vertical, max_slots = { x y } (caps) and format
                                  (UPPER_RIGHT fills right to left from the right edge, LOWER_* bottom-up)
    --no-relayout                 event windows keep their .gui positions (see the event re-flow below)
    --out tools/preview/render_<window>.png
    --outline                     thin coloured rectangles + names over every element (debug)
    --crop                        crop to the drawn elements (+16 px); windows without Orientation start at 32,32
    --no-placeholders             do not draw grey "<name>" placeholders for engine-filled texts
    --no-scrollbars               do not draw containers' scrollbars
    --progress 0.5                fill of progress bars / sliders without a startValue
    --compare <png> [--compare-box x0,y0,x1,y1] [--compare-zoom N]   also write <out>_compare.png with four panels:
                                  screenshot, render, 50% blend (ghosting = misplaced), difference (red); use
                                  --bg none to draw the render over the screenshot itself
    --quiet                       no layout table

Prints a layout table (name, type, x, y, w, h, sprite/font/text; CUT = text cut with "...", GROWS = more lines than
maxHeight holds, OVERFLOWS = a word wider than the box sticks out) and WARN lines: sprites not declared (drawn as
magenta boxes), missing textures/fonts/glyphs, buttonText wider than its button, texts that do not fit, sprites the mod
defines twice, unknown element types (skipped), backgrounds drawn at a size or place that is not verified (several,
positioned, or a plain sprite whose native size differs from the window), and --state/--text/--prop/--grid/--move/
--hide names that matched no element.

Engine rules it follows (checked against in-game 3440x1440 screenshots of the main menu, scenario picker, country
picker, lobby, topbar and politics view; the frontend renders match pixel for pixel):
  - position is relative to the parent corner/centre named by Orientation; origo/centerPosition subtract the element's
    own size (integer maths: an odd-sized centred window sits at parent//2 - size//2); x/y accept px and %; a size
    of N% is N% of the parent, N%% is N% of the space from the element's position to the parent's far edge (the
    topbar and the politics view end exactly at the screen edges that way); %-sizes are truncated like positions
    (50% of 303 px = 151; unverified for odd parents); a negative size is "parent minus"; size
    min/max/preserve_aspect_ratio; elements at |x| or |y| >= 5000 are skipped.
  - text boxes: box = maxWidth x maxHeight, text from borderSize; vertical_alignment defaults to top; greedy word wrap;
    fixedsize (or truncate = yes) keeps max(1, (maxHeight - 1) // lineHeight) lines and cuts the rest with "..."
    (the last line gets the whole remaining text); without fixedsize the box grows; format left/centre/right uses the
    sum of advances; buttonText is centred in the button (advances, (h - lineHeight) // 2).
  - only containers with clipping = yes or a scrollbar clip their children (RENDER_GUI_CLIP=default|scroll|explicit);
    gridboxes grow with their entries.
  - wrapping measures up to the last glyph's ink (RENDER_GUI_WRAP=extent|strict|adv).
  - duplicate sprite names: the definition from the later file (alphabetical) wins.
Rules taken from vanilla data, not from a screenshot (the tool WARNs where they apply):
  - every background block of a window is drawn, in file order, at the window corner + its position; a
    corneredTileSpriteType background takes the window size, any other sprite keeps its native frame size
    (settings_popup_bg 480x527 in the 480x600 menu_settings_ingame; deploy_entry's three side-by-side backgrounds);
    a tiny (<= 4x4) texture such as in_game_menu_dark_overlay is a runtime-sized fill and is stretched.
  - event re-flow (a window with a 'midsection' holding 'Description' and a 'bottom_Window': the eventwindow.gui
    family): midsection height = max(its height, Description.y + text height), bottom_Window moves to just below it
    and grows to its options grid (--grid options_grid=event_option_entry:N), bottom_window_end follows, the window
    grows to match. The exact engine rule is unverified; EventWindow_Operative is the least certain.
Not modelled: engine-filled data (flags, portraits, numbers, grids), engine visibility toggles, tooltips' engine width,
animations/effects (only the buttonstate hover/press tint), scrolled content.

Caches parsed files in tools/data/render_gui_cache/ (keyed on file sizes and mtimes; delete to force a rebuild; written
to a temp file and renamed, so parallel renders are safe). The --bg map backdrop is cut from an in-game screenshot once
(TOTU_MAP_SHOT) and kept there as map_backdrop.jpg.
HOI4_DIR overrides the game folder. Requires Pillow and numpy. Prints ASCII only.
"""
import argparse
import fnmatch
import hashlib
import os
import pickle
import re
import struct
import sys
import time
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
GAME = Path(os.environ.get("HOI4_DIR", r"D:\steam\steamapps\common\Hearts of Iron IV"))
CACHE = ROOT / "tools" / "data" / "render_gui_cache"
PREVIEW = ROOT / "tools" / "preview"
# source of the --bg map backdrop (an in-game 3440x1440 screenshot); the processed crop is cached in CACHE
MAP_SHOT = Path(os.environ.get("TOTU_MAP_SHOT", r"C:\Users\kot20\AppData\Local\Temp\claude\C--Users-kot20-OneDrive-"
                               r"----------Paradox-Interactive-Hearts-of-Iron-IV-mod-Twilight-of-the-Union"
                               r"\82b2b4da-b354-46bc-94b6-6c4155c82c08\scratchpad\readme_shots\ingame_full.png"))
CACHE_VERSION = 7

WINDOW_TYPES = {"containerwindowtype", "windowtype", "eu3dialogtype", "expandedwindow"}
BUTTON_TYPES = {"buttontype", "guibuttontype", "expandbutton", "textbuttontype"}
ICON_TYPES = {"icontype", "shieldtype"}
TEXT_TYPES = {"instanttextboxtype", "textboxtype"}
LIST_TYPES = {"gridboxtype", "listboxtype", "smoothlistboxtype", "overlappingelementsboxtype", "browsertype"}
SCROLL_TYPES = {"extendedscrollbartype", "scrollbartype"}
ELEMENT_TYPES = (WINDOW_TYPES | BUTTON_TYPES | ICON_TYPES | TEXT_TYPES | LIST_TYPES | SCROLL_TYPES |
                 {"checkboxtype", "editboxtype", "positiontype", "dropdownboxtype", "spinnertype"})
SPRITE_KINDS = {"spritetype", "corneredtilespritetype", "textspritetype", "frameanimatedspritetype", "progressbartype",
                "maskedshieldtype", "circularprogressbartype", "piecharttype", "linecharttype", "arrowtype",
                "tilespritetype", "scrollingtexturetype", "flagspritetype"}
# not element blocks (properties that are blocks)
PROPERTY_BLOCKS = {"position", "size", "bordersize", "margin", "slotsize", "background", "show_position",
                   "hide_position", "min", "max", "offset", "spacing", "slider", "track", "decreasebutton",
                   "increasebutton", "padding", "tilesize", "background_margin", "cursor", "drag_scroll",
                   "peek_position", "peek_check_top_left", "peek_check_size", "open_position", "closed_position",
                   "max_slots", "bound_tooltip", "textcolors"}
OFFSCREEN = 5000          # |coordinate| at or beyond this = the "-9000" hiding idiom: skipped
PLACEHOLDER_RGBA = (150, 150, 150, 200)
MISSING_RGBA = (255, 0, 255, 160)
OUTLINE_COLOURS = {"window": (0, 200, 255), "button": (255, 200, 0), "icon": (60, 230, 60), "text": (255, 90, 90),
                   "list": (210, 80, 255), "edit": (255, 140, 0), "other": (170, 170, 170)}


def shown_path(p):
    """A path for the log: relative to the mod folder when inside it (the mod path has Cyrillic letters)."""
    try:
        return Path(p).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return ascii_only(p)


def log(*a):
    print(*a)
    sys.stdout.flush()


def warn(msg, _seen=set()):
    if msg not in _seen:
        _seen.add(msg)
        print("WARN " + ascii_only(msg))


def ascii_only(s):
    return str(s).encode("ascii", "backslashreplace").decode("ascii")


# ====================================================================================== Paradox script parser
class Node(list):
    """A parsed block: a list of (key, value); key keeps its case (None for bare values); value is str or Node."""
    __slots__ = ()

    def get(self, key, default=None):
        key = key.lower()
        r = default
        for k, v in self:
            if k is not None and k.lower() == key:
                r = v
        return r

    def node(self, key):
        v = self.get(key)
        return v if isinstance(v, Node) else None

    def str(self, key, default=None):
        v = self.get(key)
        return v if isinstance(v, str) else default

    def has(self, key):
        key = key.lower()
        return any(k is not None and k.lower() == key for k, _ in self)

    def values(self):
        return [v for k, v in self if k is None]

    def set(self, key, value):
        """Replaces the value get() returns (the last occurrence), or appends the key."""
        kl = key.lower()
        for i in range(len(self) - 1, -1, -1):
            k = self[i][0]
            if k is not None and k.lower() == kl:
                self[i] = (k, value)
                return
        self.append((key, value))

    def all(self, key):
        """Every value of a repeated key, in file order (several background blocks)."""
        key = key.lower()
        return [v for k, v in self if k is not None and k.lower() == key]


_TOKEN = re.compile(r'"[^"\n]*"?|#[^\n]*|[{}=]|[^\s{}=#"]+')


def _unq(t):
    return t[1:-1] if len(t) >= 2 and t[0] == '"' and t[-1] == '"' else t.strip('"')


def parse(text):
    toks = [t for t in _TOKEN.findall(text) if t[0] != "#"]
    root = Node()
    stack = [root]
    i, n = 0, len(toks)
    variables = {}          # @name = value script constants (eventwindow.gui: @fade_time)
    while i < n:
        t = toks[i]
        if t == "}":
            if len(stack) > 1:
                stack.pop()
            i += 1
        elif t == "{":
            nd = Node()
            stack[-1].append((None, nd))
            stack.append(nd)
            i += 1
        elif t == "=":
            i += 1
        elif i + 1 < n and toks[i + 1] == "=":
            key = _unq(t)
            if i + 2 < n and toks[i + 2] == "{":
                nd = Node()
                stack[-1].append((key, nd))
                stack.append(nd)
                i += 3
            elif i + 2 < n:
                val = _unq(toks[i + 2])
                if val.startswith("@") and val in variables:
                    val = variables[val]
                if key.startswith("@"):
                    variables[key] = val
                else:
                    stack[-1].append((key, val))
                i += 3
            else:
                i += 2
        else:
            stack[-1].append((None, _unq(t)))
            i += 1
    return root


def node_copy(n):
    """A deep copy of a parsed block (the cached trees are shared and must not be changed)."""
    return Node((k, node_copy(v) if isinstance(v, Node) else v) for k, v in n)


def read_text(path):
    b = Path(path).read_bytes()
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            pass
    return b.decode("latin-1")


# ====================================================================================== file system
def _roots():
    r = [("mod", ROOT), ("game", GAME)]
    dlc = GAME / "dlc"
    if dlc.is_dir():
        r += [("dlc", d) for d in sorted(dlc.iterdir()) if d.is_dir()]
    if (GAME / "pdx_online_assets").is_dir():
        r.append(("online", GAME / "pdx_online_assets"))
    return r


ROOTS = _roots()


def norm_rel(p):
    p = str(p).replace("\\", "/")
    p = re.sub(r"/+", "/", p).lstrip("/")
    return p


def effective_files(sub, exts):
    """rel path (lower) -> (origin, Path, rel) over all roots; earlier roots win (mod > game > dlc > online)."""
    out = {}
    for origin, root in reversed(ROOTS):
        base = root / sub
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if p.suffix.lower() in exts and p.is_file():
                rel = p.relative_to(root).as_posix()
                out[rel.lower()] = (origin, p, rel)
    return out


_find_cache = {}


def find_file(rel, alt_exts=(".dds", ".tga", ".png")):
    """The effective file for a game-relative path (mod first), trying other image extensions if missing."""
    rel = norm_rel(rel)
    if rel in _find_cache:
        return _find_cache[rel]
    found = None
    for _, root in ROOTS:
        p = root / rel
        if p.is_file():
            found = p
            break
    if found is None and alt_exts:
        stem = rel.rsplit(".", 1)[0] if "." in rel.rsplit("/", 1)[-1] else rel
        for ext in alt_exts:
            for _, root in ROOTS:
                p = root / (stem + ext)
                if p.is_file():
                    found = p
                    break
            if found:
                break
    _find_cache[rel] = found
    return found


def files_signature(files):
    sig = []
    for rel in sorted(files):
        origin, p, _ = files[rel]
        st = p.stat()
        sig.append((rel, origin, st.st_size, int(st.st_mtime)))
    return hashlib.md5(repr(sig).encode("utf-8")).hexdigest(), len(sig)


def cache_load(name, sig):
    p = CACHE / name
    try:
        with open(p, "rb") as f:
            data = pickle.load(f)
        if data.get("version") == CACHE_VERSION and data.get("sig") == sig:
            return data["payload"]
    except Exception:
        pass
    return None


GITIGNORE = ("# tools/render_gui.py cache: the pickles are rebuilt on demand and stay out of git. map_backdrop.jpg (the\n"
             "# --bg map backdrop, cut from an in-game screenshot) may be committed: its source is not in the repo.\n"
             "*\n!.gitignore\n!map_backdrop.jpg\n")


def ensure_cache_dir():
    CACHE.mkdir(parents=True, exist_ok=True)
    gi = CACHE / ".gitignore"
    if not gi.exists() or gi.read_text(encoding="ascii", errors="replace") != GITIGNORE:
        gi.write_text(GITIGNORE, encoding="ascii", newline="\n")


def cache_store(name, sig, payload):
    """Writes a temp file next to the target and renames it over the target, so renders running at the same time
    never read a half-written pickle (a reader sees the old or the new file; a failed rename only costs a rebuild)."""
    tmp = CACHE / f"{name}.{os.getpid()}.tmp"
    try:
        ensure_cache_dir()
        with open(tmp, "wb") as f:
            pickle.dump({"version": CACHE_VERSION, "sig": sig, "payload": payload}, f, protocol=pickle.HIGHEST_PROTOCOL)
        for attempt in range(6):
            try:
                os.replace(tmp, CACHE / name)
                return
            except PermissionError:          # Windows: another process has the target open for reading
                time.sleep(0.1 * (attempt + 1))
        warn(f"cache write skipped ({name}): the file stays busy (another render is reading it)")
    except Exception as e:
        warn(f"cache write failed ({name}): {e}")
    try:
        tmp.unlink()
    except OSError:
        pass


# ====================================================================================== textures
_tex_cache = {}


def _dds_patch(data, fourcc):
    h = bytearray(data[:128])
    h[80:84] = struct.pack("<I", 4)
    h[84:88] = fourcc
    return bytes(h) + data[148:]


def _dds_masked(data):
    height, width = struct.unpack("<II", data[12:20])
    bpp = struct.unpack("<I", data[88:92])[0]
    flags = struct.unpack("<I", data[80:84])[0]
    masks = struct.unpack("<4I", data[92:108])
    nbytes = bpp // 8
    raw = np.frombuffer(data, dtype=np.uint8, count=width * height * nbytes, offset=128).reshape(height, width, nbytes)
    val = np.zeros((height, width), dtype=np.uint32)
    for i in range(nbytes):
        val |= raw[..., i].astype(np.uint32) << (8 * i)
    out = np.zeros((height, width, 4), dtype=np.uint8)
    if flags & 0x2 and not (flags & 0x40):          # DDPF_ALPHA: an alpha-only texture
        masks = (0, 0, 0, masks[3] or 0xff)
        flags |= 0x1
    for ch, m in enumerate(masks):
        if ch == 3 and not (flags & 0x1):
            m = 0
        if m == 0:
            out[..., ch] = 255 if ch == 3 else 0
            continue
        shift = (m & -m).bit_length() - 1
        bits = bin(m).count("1")
        v = (val & m) >> shift
        out[..., ch] = (v * 255 // ((1 << bits) - 1)).astype(np.uint8)
    if not (flags & 0x41) and (flags & 0x20000):      # luminance
        out[..., 1] = out[..., 2] = out[..., 0]
    return Image.fromarray(out, "RGBA")


def _decode_dds(data):
    flags = struct.unpack("<I", data[80:84])[0]
    if not (flags & 0x4):          # uncompressed: numpy (Pillow decodes masked formats pixel by pixel in Python)
        try:
            return _dds_masked(data)
        except Exception:
            pass
    try:
        im = Image.open(BytesIO(data))
        im.load()
        return im.convert("RGBA")
    except Exception:
        pass
    fourcc = data[84:88]
    if fourcc == b"DX10":
        dxgi = struct.unpack("<I", data[128:132])[0]
        height, width = struct.unpack("<II", data[12:20])
        if dxgi in (87, 88, 91, 93):
            a = np.frombuffer(data, np.uint8, width * height * 4, 148).reshape(height, width, 4)
            a = a[..., [2, 1, 0, 3]].copy()
            if dxgi in (88, 93):
                a[..., 3] = 255
            return Image.fromarray(a, "RGBA")
        if dxgi in (27, 28, 29):
            a = np.frombuffer(data, np.uint8, width * height * 4, 148).reshape(height, width, 4)
            return Image.fromarray(a.copy(), "RGBA")
        legacy = {70: b"DXT1", 71: b"DXT1", 72: b"DXT1", 73: b"DXT3", 74: b"DXT3", 75: b"DXT3",
                  76: b"DXT5", 77: b"DXT5", 78: b"DXT5"}.get(dxgi)
        if legacy:
            im = Image.open(BytesIO(_dds_patch(data, legacy)))
            im.load()
            return im.convert("RGBA")
        raise ValueError(f"DXGI format {dxgi}")
    if fourcc == b"RXGB":            # DXT5 with red in alpha (Doom 3 normal-map swizzle)
        h = bytearray(data)
        h[84:88] = b"DXT5"
        a = np.asarray(Image.open(BytesIO(bytes(h))).convert("RGBA")).copy()
        a[..., 0] = a[..., 3]
        a[..., 3] = 255
        return Image.fromarray(a, "RGBA")
    return _dds_masked(data)


def load_texture(path):
    """RGBA image of a texture path (game-relative or absolute), None if missing/undecodable (warned)."""
    if path is None:
        return None
    key = str(path)
    if key in _tex_cache:
        return _tex_cache[key]
    p = Path(path) if Path(path).is_absolute() else find_file(path)
    im = None
    if p is None:
        warn(f"texture not found: {path}")
    else:
        try:
            data = p.read_bytes()
            if data[:4] == b"DDS ":
                im = _decode_dds(data)
            else:
                im = Image.open(BytesIO(data))
                im.load()
                im = im.convert("RGBA")
        except Exception as e:
            warn(f"texture undecodable: {path} ({e})")
            im = None
    _tex_cache[key] = im
    return im


# ====================================================================================== gfx database
def _xy(node, a="x", b="y"):
    if not isinstance(node, Node):
        return None
    try:
        return (int(float(node.get(a, node.get("width", 0)))), int(float(node.get(b, node.get("height", 0)))))
    except ValueError:
        return None


def _colour_hex(s):
    try:
        v = int(str(s), 16) & 0xFFFFFFFF
    except ValueError:
        return (255, 255, 255, 255)
    return ((v >> 16) & 255, (v >> 8) & 255, v & 255, (v >> 24) & 255)


def _textcolors(node):
    out = {}
    if isinstance(node, Node):
        for k, v in node:
            if k is not None and isinstance(v, Node):
                nums = [x for x in v.values() if re.fullmatch(r"-?\d+(\.\d+)?", str(x))]
                if len(nums) >= 3:
                    out[k] = tuple(int(float(x)) for x in nums[:3])
    return out


def _yes(v):
    return str(v).lower() in ("yes", "true", "1")


def build_gfx_db():
    files = effective_files("interface", {".gfx"})
    sig = files_signature(files)
    db = cache_load("gfx_db.pickle", sig)
    if db is not None:
        return db
    t0 = time.time()
    sprites, fonts, overrides, colours, dups = {}, {}, [], {}, []
    for rel in sorted(files):
        origin, path, real_rel = files[rel]
        try:
            tree = parse(read_text(path))
        except Exception as e:
            warn(f"parse failed {real_rel}: {e}")
            continue
        tag = f"{origin}:{real_rel}"

        def walk(node, parent_key):
            for k, v in node:
                if not isinstance(v, Node) or k is None:
                    continue
                kl = k.lower()
                if kl in SPRITE_KINDS and v.str("name"):
                    d = {"kind": kl, "def": tag}
                    for kk, vv in v:
                        if kk is None:
                            continue
                        kkl = kk.lower()
                        if kkl in ("bordersize", "size"):
                            if isinstance(vv, Node):
                                d[kkl] = _xy(vv)
                            elif kkl == "size":
                                d["radius"] = vv          # pieChartType / circularProgressBarType: a radius
                        elif isinstance(vv, str):
                            d[kkl] = vv
                        elif kkl in ("color", "colortwo"):
                            d[kkl] = tuple(float(x) for x in vv.values()[:4] if re.fullmatch(r"-?[\d.]+", str(x)))
                    name = v.str("name")
                    if name in sprites:
                        # the later file wins: vanilla's _leader_portraits.gfx loads first so DLC files can replace
                        # its sprites, and DLC 2D-art packs redefine base focus icons the same way
                        dups.append((name, sprites[name]["def"], tag))
                        d["replaces"] = sprites[name]["def"]
                    sprites[name] = d
                elif kl == "bitmapfont" and v.str("name"):
                    files_ = [norm_rel(x) for x in (v.node("fontfiles").values() if v.node("fontfiles") else [])]
                    if v.str("path"):
                        files_ = [norm_rel(v.str("path"))] + files_
                    fonts[v.str("name")] = {"files": files_, "color": _colour_hex(v.str("color", "0xffffffff")),
                                            "textcolors": _textcolors(v.node("textcolors")), "def": tag,
                                            "overrides": {}}
                elif kl == "bitmapfont_override" and v.str("name"):
                    langs = v.node("languages").values() if v.node("languages") else []
                    ff = [norm_rel(x) for x in (v.node("fontfiles").values() if v.node("fontfiles") else [])]
                    overrides.append((v.str("name"), [x.lower() for x in langs], ff, tag))
                elif kl == "textcolors" and parent_key == "bitmapfonts":
                    colours.update(_textcolors(v))
                else:
                    walk(v, kl)
        walk(tree, None)
    for name, langs, ff, tag in overrides:
        if name in fonts:
            for lang in langs:
                fonts[name]["overrides"][lang] = ff
    db = {"sprites": sprites, "fonts": fonts, "textcolors": colours, "dups": dups}
    cache_store("gfx_db.pickle", sig, db)
    log(f"gfx db: {len(sprites)} sprites, {len(fonts)} fonts from {len(files)} files ({time.time() - t0:.1f}s)")
    return db


# ====================================================================================== gui index
def build_gui_index():
    files = effective_files("interface", {".gui"})
    sig = files_signature(files)
    idx = cache_load("gui_index.pickle", sig)
    if idx is not None:
        return idx
    t0 = time.time()
    names = {}           # name -> [(rel_lower, real_rel, origin, path_indices, type, depth)]
    for rel in sorted(files):
        origin, path, real_rel = files[rel]
        try:
            tree = parse(read_text(path))
        except Exception as e:
            warn(f"parse failed {real_rel}: {e}")
            continue

        def walk(node, trail, depth):
            for i, (k, v) in enumerate(node):
                if not isinstance(v, Node) or k is None:
                    continue
                kl = k.lower()
                if kl in ELEMENT_TYPES:
                    nm = v.str("name")
                    if nm and (kl in WINDOW_TYPES or depth == 0 or kl in SCROLL_TYPES):
                        names.setdefault(nm, []).append((rel, real_rel, origin, trail + (i,), kl, depth))
                    walk(v, trail + (i,), depth + 1)
                elif kl == "guitypes":
                    walk(v, trail + (i,), 0)
                elif kl not in PROPERTY_BLOCKS:
                    walk(v, trail + (i,), depth)
        walk(tree, (), 0)
    idx = {"names": names, "files": {rel: (o, str(p), r) for rel, (o, p, r) in files.items()}}
    cache_store("gui_index.pickle", sig, idx)
    log(f"gui index: {len(names)} names from {len(files)} files ({time.time() - t0:.1f}s)")
    return idx


_gui_tree_cache = {}


def gui_tree(path):
    if path not in _gui_tree_cache:
        _gui_tree_cache[path] = parse(read_text(path))
    return _gui_tree_cache[path]


def node_at(tree, trail):
    n = tree
    for i in trail:
        n = n[i][1]
    return n


# ====================================================================================== localisation
_LOC_LINE = re.compile(r'^\s*([^\s:#"]+):\d*\s*"(.*)"')


def build_loc(lang):
    files = {}
    for origin, root in reversed(ROOTS[:2]):
        base = root / "localisation"
        if not base.is_dir():
            continue
        for p in base.rglob(f"*_l_{lang}.yml"):
            rel = p.relative_to(root).as_posix().lower()
            files[(origin, rel)] = (origin, p, rel)
    sigfiles = {f"{o}:{r}": v for (o, r), v in files.items()}
    sig = files_signature(sigfiles)
    loc = cache_load(f"loc_{lang}.pickle", sig)
    if loc is not None:
        return loc
    t0 = time.time()

    def rank(item):
        origin, p, rel = item
        replace = "/replace/" in rel
        return (1 if replace else 0, 1 if origin == "mod" else 0, rel)   # later = higher priority
    loc = {}
    for origin, p, rel in sorted(files.values(), key=rank):
        try:
            text = p.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            continue
        for line in text.splitlines():
            m = _LOC_LINE.match(line)
            if not m:
                continue
            key, val = m.group(1), m.group(2)
            q = val.rfind('"')       # trailing comment after the closing quote
            if q >= 0 and "#" in val[q:]:
                val = val[:q]
            loc[key] = val
    cache_store(f"loc_{lang}.pickle", sig, loc)
    log(f"localisation {lang}: {len(loc)} keys from {len(files)} files ({time.time() - t0:.1f}s)")
    return loc


# ====================================================================================== fonts
_FNT_FIELD = re.compile(r'(\w+)=("[^"]*"|\S+)')


class Font:
    def __init__(self, name, files, colour, textcolors, globals_):
        self.name = name
        self.colour = colour
        self.textcolors = dict(globals_)
        self.textcolors.update(textcolors)
        self.chars = {}
        self.kern = {}
        self.line_height = 16
        self.base = 12
        self._tiles = {}
        first = True
        for f in files:
            fnt = find_file(f + ".fnt", alt_exts=())
            if fnt is None:
                warn(f"font {name}: missing {f}.fnt")
                continue
            common, chars, kern, pages = self._read_fnt(fnt)
            atlases = {}
            for pid, pfile in pages.items():
                atl = load_texture(f + ".dds") if pid == 0 else None
                if atl is None:
                    cand = norm_rel(str(Path(f).parent / pfile)) if pfile else None
                    atl = load_texture(cand) if cand else None
                atlases[pid] = atl
            if not pages:
                atlases[0] = load_texture(f + ".dds")
            if first:
                self.line_height = common.get("lineHeight", 16)
                self.base = common.get("base", 12)
                first = False
            for cp, c in chars.items():
                if cp not in self.chars:
                    c["atlas"] = atlases.get(c.get("page", 0))
                    self.chars[cp] = c
            for k, v in kern.items():
                self.kern.setdefault(k, v)

    @staticmethod
    def _read_fnt(path):
        common, chars, kern, pages = {}, {}, {}, {}
        data = path.read_bytes()
        if data[:3] == b"BMF":
            warn(f"binary .fnt not supported: {path}")
            return common, chars, kern, pages
        for line in data.decode("latin-1").splitlines():
            tag, _, rest = line.strip().partition(" ")
            fields = dict(_FNT_FIELD.findall(rest))
            try:
                if tag == "common":
                    common = {k: int(v) for k, v in fields.items() if re.fullmatch(r"-?\d+", v)}
                elif tag == "page":
                    pages[int(fields.get("id", 0))] = fields.get("file", "").strip('"')
                elif tag == "char":
                    c = {k: int(v) for k, v in fields.items() if re.fullmatch(r"-?\d+", v)}
                    chars[c["id"]] = c
                elif tag == "kerning":
                    kern[(int(fields["first"]), int(fields["second"]))] = int(fields["amount"])
            except (KeyError, ValueError):
                pass
        return common, chars, kern, pages

    def advance(self, ch, nxt=None):
        c = self.chars.get(ord(ch))
        if c is None:
            return 0
        a = c.get("xadvance", 0)
        if nxt is not None and self.kern:
            a += self.kern.get((ord(ch), ord(nxt)), 0)
        return a

    def width(self, text):
        w = 0
        for i, item in enumerate(text):
            ch = item[0] if isinstance(item, tuple) else item
            if isinstance(ch, Icon):
                w += ch.w
                continue
            nxt = text[i + 1] if i + 1 < len(text) else None
            nxt = (nxt[0] if isinstance(nxt, tuple) else nxt) if nxt is not None else None
            w += self.advance(ch, nxt if isinstance(nxt, str) else None)
        return w

    def tile(self, ch, rgba):
        key = (ch, rgba)
        t = self._tiles.get(key)
        if t is None:
            c = self.chars.get(ord(ch))
            if c is None or c.get("atlas") is None or c.get("width", 0) <= 0 or c.get("height", 0) <= 0:
                t = False
            else:
                tile = c["atlas"].crop((c["x"], c["y"], c["x"] + c["width"], c["y"] + c["height"]))
                a = np.asarray(tile, dtype=np.float32)
                mul = np.array(rgba, dtype=np.float32) / 255.0
                t = Image.fromarray(np.clip(a * mul + 0.5, 0, 255).astype(np.uint8), "RGBA")
            self._tiles[key] = t
        return t

    def colour_for(self, code):
        if code in self.textcolors:
            return self.textcolors[code] + (self.colour[3],)
        return None


class Icon:
    """A text icon (pound sign + sprite name) inside a text run."""
    def __init__(self, img, name):
        self.img = img
        self.name = name
        self.w = img.width if img is not None else 0


# ====================================================================================== context
class Used(dict):
    """A name -> value option table that remembers which names an element looked up (unmatched ones are warned)."""
    def __init__(self, *a):
        super().__init__(*a)
        self.used = set()

    def __contains__(self, k):
        hit = dict.__contains__(self, k)
        if hit:
            self.used.add(k)
        return hit

    def get(self, k, default=None):
        if dict.__contains__(self, k):
            self.used.add(k)
        return dict.get(self, k, default)


class SpecError(ValueError):
    pass


def _int(s, what):
    try:
        return int(str(s).strip())
    except ValueError:
        raise SpecError(f"{what}: '{s}' is not a whole number")


STATE_KINDS = ("hover", "pressed", "checked", "disabled", "frame")


def parse_specs(args):
    """--state/--text/--prop/--grid/--move -> tables; malformed specs raise SpecError (argparse reports them)."""
    states, frames, texts, props, grids, moves = {}, {}, {}, {}, {}, {}
    for spec in getattr(args, "state", None) or []:
        for part in spec.split(","):
            part = part.strip()
            if not part:
                continue
            kind, sep, name = part.partition(":")
            kind = kind.lower()
            if not sep or not name or kind not in STATE_KINDS:
                raise SpecError(f"--state {part}: expected hover:<el>, pressed:<el>, checked:<el>, disabled:<el> or "
                                "frame:<el>=N")
            if kind == "frame":
                nm, _, n = name.partition("=")
                frames[nm] = _int(n or 1, f"--state frame:{name}")
            else:
                states.setdefault(name, set()).add(kind)
    for spec in getattr(args, "text", None) or []:
        nm, sep, val = spec.partition("=")
        if not sep or not nm:
            raise SpecError(f"--text {spec}: expected <element>=<text or KEY>")
        texts[nm] = val
    for spec in getattr(args, "prop", None) or []:
        lhs, sep, val = spec.partition("=")
        nm, dot, key = lhs.partition(".")
        if not sep or not dot or not nm or not key or any(not p for p in key.split(".")):
            raise SpecError(f"--prop {spec}: expected <element>.<key>=<value>, e.g. icon.spriteType=GFX_x, "
                            "bottom_Window.position.y=400 or bottom_Window.position={ x=0 y=400 }")
        if val.strip().startswith("{"):
            blk = parse("v = " + val).node("v")
            if blk is None:
                raise SpecError(f"--prop {spec}: the block value does not parse")
            val = blk
        props.setdefault(nm, []).append((key, val))
    for spec in getattr(args, "grid", None) or []:
        nm, sep, val = spec.partition("=")
        tpl, colon, cnt = val.partition(":")
        if not sep or not nm or not tpl:
            raise SpecError(f"--grid {spec}: expected <gridbox>=<template>[:count]")
        n = _int(cnt, f"--grid {spec} count") if colon else None
        if n is not None and n < 0:
            raise SpecError(f"--grid {spec}: the count must be 0 or more")
        grids[nm] = (tpl, n)
    for spec in getattr(args, "move", None) or []:
        nm, sep, val = spec.partition("=")
        parts = val.split(",")
        if not sep or not nm or len(parts) != 2:
            raise SpecError(f"--move {spec}: expected <element>=dx,dy (pixels, may be negative)")
        moves[nm] = (_int(parts[0], f"--move {spec} dx"), _int(parts[1], f"--move {spec} dy"))
    return states, frames, texts, props, grids, moves


class Ctx:
    def __init__(self, args):
        self.args = args
        self.lang = args.lang
        states, frames, texts, props, grids, moves = parse_specs(args)
        self.gfx = build_gfx_db()
        self.gui = build_gui_index()
        self.loc = build_loc(args.lang)
        self.fonts = {}
        self.states = Used(states)
        self.frames = Used(frames)
        self.hidden = [x.strip() for x in ",".join(getattr(args, "hide", None) or []).split(",") if x.strip()]
        self.hidden_used = set()
        self.texts = Used(texts)
        self.props = Used(props)
        self.grids = Used(grids)
        self.moves = Used(moves)
        self.relayout = not getattr(args, "no_relayout", False)
        self.rows = []
        self.outlines = []
        self.unknown = {}
        self.missing_sprites = set()
        self.bounds = None
        self.skipped = []

    def warn_unused(self):
        """WARN for every --state/--text/--prop/--grid/--move/--hide name that matched no element."""
        for opt, table in (("--state", self.states), ("--state frame:", self.frames), ("--text", self.texts),
                           ("--prop", self.props), ("--grid", self.grids), ("--move", self.moves)):
            for nm in sorted(set(table) - table.used):
                warn(f"{opt} {nm}: no drawn element is named '{nm}' (names are case-sensitive; the layout table "
                     "lists them)")
        for pat in self.hidden:
            if pat not in self.hidden_used:
                warn(f"--hide {pat}: matched no element")

    # ---- fonts
    def font(self, name):
        if not name:
            name = "vic_18"
        if name in self.fonts:
            return self.fonts[name]
        d = self.gfx["fonts"].get(name)
        if d is None:
            warn(f"font not declared: {name} (using hoi_18mbs)")
            f = self.font("hoi_18mbs") if name != "hoi_18mbs" else None
            self.fonts[name] = f
            return f
        files = d["overrides"].get("l_" + self.lang, d["files"])
        f = Font(name, files, d["color"], d["textcolors"], self.gfx["textcolors"])
        if not f.chars:
            warn(f"font {name}: no glyphs loaded")
        self.fonts[name] = f
        return f

    # ---- sprites
    def sprite(self, name):
        if not name:
            return None
        d = self.gfx["sprites"].get(name)
        if d is None:
            if name not in self.missing_sprites:
                self.missing_sprites.add(name)
                warn(f"sprite not declared: {name} (magenta box)")
        elif d.get("replaces") and ("mod:" in d["def"] or "mod:" in d["replaces"]):
            warn(f"{name} is defined in {d['replaces']} and again in {d['def']}; the later file ({d['def']}) is "
                 "used (files load in alphabetical order, the last definition wins)")
        return d

    def sprite_image(self, d, which="texturefile"):
        if d is None:
            return None
        tex = d.get(which) or (d.get("texturefile1") if which == "texturefile" else None)
        return load_texture(tex) if tex else None

    # ---- localisation
    def localise(self, raw, depth=0):
        if raw is None:
            return None
        s = self.loc.get(raw, raw) if depth == 0 else raw

        def sub(m):
            k = m.group(1)
            key = k.split("|")[0]
            if key in self.loc and depth < 6:
                return self.localise(self.loc[key], depth + 1)
            return m.group(0)
        s = re.sub(r"\$([^$\s]+)\$", sub, s)
        return s.replace("\\n", "\n").replace('\\"', '"')


# ====================================================================================== geometry helpers
def dim(v, parent, default=0.0, size=False, remaining=None):
    """A gui number: px, N% of the parent, or for sizes N%% of the space left between the element's position and
    the parent's far edge (`remaining`; in game the topbar's 100%% window at x=217 ends at the screen edge and the
    politics view's height=100%% at y=78 ends at the screen bottom). Negative sizes are 'parent minus'."""
    if v is None:
        return default
    s = str(v).strip()
    m = re.match(r"(-?(?:\d+\.?\d*|\.\d+))\s*(%*)", s)      # tolerant like atoi: vanilla has "y=1s"
    if not m:
        return default
    r = float(m.group(1))
    if m.group(2) == "%%" and size and remaining is not None:
        r = remaining * r / 100.0
    elif m.group(2):
        r = parent * r / 100.0
    if size and r < 0:
        r = parent + r
    if size and m.group(2):
        # truncated like the positions (and the centring), not rounded half-to-even: 50% of 303 px is 151
        r = float(np.floor(r + 1e-6))
    return r


ANCHORS = {"upper_left": (0, 0), "upper_right": (1, 0), "lower_left": (0, 1), "lower_right": (1, 1),
           "center": (0.5, 0.5), "centre": (0.5, 0.5), "center_up": (0.5, 0), "center_down": (0.5, 1),
           "center_left": (0, 0.5), "center_right": (1, 0.5)}


def apos(a, size):
    return 0 if a == 0 else (size if a == 1 else size // 2)


def anchor(spec):
    if not spec:
        return (0, 0)
    a = ANCHORS.get(str(spec).strip().lower())
    if a is None:
        warn(f"unknown orientation/origo: {spec}")
        return (0, 0)
    return a


def frame_count(d):
    try:
        return max(1, int(d.get("noofframes", 1)))
    except (ValueError, TypeError):
        return 1


def sprite_frame_size(ctx, d):
    """Native (w, h) of one frame of a sprite definition, or None."""
    if d is None:
        return None
    kind = d["kind"]
    if not isinstance(d.get("size"), tuple):
        d = dict(d, size=None)
    if kind in ("piecharttype", "circularprogressbartype") and d.get("radius"):
        r = int(dim(d["radius"], 0, 16))
        return (2 * r, 2 * r)
    if kind == "corneredtilespritetype" and d.get("size"):
        return d["size"]
    if kind in ("progressbartype", "circularprogressbartype") and d.get("size"):
        return d["size"]
    if kind == "maskedshieldtype":
        im = load_texture(d.get("texturefile2") or d.get("texturefile1"))
        return im.size if im is not None else None
    im = ctx.sprite_image(d)
    if im is None:
        return d.get("size")
    n = frame_count(d)
    return (im.width // n, im.height)


def intersect(a, b):
    if a is None:
        return b
    if b is None:
        return a
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    return (x0, y0, max(x0, x1), max(y0, y1))


# ====================================================================================== drawing primitives
class Canvas:
    def __init__(self, w, h, bg=None):
        self.w, self.h = w, h
        self.img = Image.new("RGBA", (w, h), (0, 0, 0, 0)) if bg is None else bg

    def blit(self, im, x, y, clip=None):
        """alpha-composite im at (x, y), clipped to clip (x0, y0, x1, y1) and the canvas."""
        if im is None:
            return
        x, y = int(round(x)), int(round(y))
        c = intersect((0, 0, self.w, self.h), clip)
        x0, y0 = max(x, c[0]), max(y, c[1])
        x1, y1 = min(x + im.width, c[2]), min(y + im.height, c[3])
        if x0 >= x1 or y0 >= y1:
            return
        part = im if (x0 == x and y0 == y and x1 == x + im.width and y1 == y + im.height) else \
            im.crop((x0 - x, y0 - y, x1 - x, y1 - y))
        self.img.alpha_composite(part, (x0, y0))

    def blit_scaled(self, im, x, y, w, h, clip=None):
        """im stretched to w x h at (x, y); only the visible part is resampled."""
        if im is None or w <= 0 or h <= 0:
            return
        if (im.width, im.height) == (int(round(w)), int(round(h))):
            self.blit(im, x, y, clip)
            return
        c = intersect((0, 0, self.w, self.h), clip)
        vx0, vy0 = max(x, c[0]), max(y, c[1])
        vx1, vy1 = min(x + w, c[2]), min(y + h, c[3])
        if vx0 >= vx1 or vy0 >= vy1:
            return
        sx, sy = im.width / w, im.height / h
        # source box of the visible part (float box: PIL resamples exactly that area)
        box = ((vx0 - x) * sx, (vy0 - y) * sy, (vx1 - x) * sx, (vy1 - y) * sy)
        ow, oh = int(round(vx1 - vx0)), int(round(vy1 - vy0))
        if ow <= 0 or oh <= 0:
            return
        part = im.resize((ow, oh), Image.BILINEAR, box=box)
        self.blit(part, vx0, vy0, clip)

    def rect(self, x, y, w, h, rgba, clip=None):
        if w <= 0 or h <= 0:
            return
        self.blit(Image.new("RGBA", (int(max(1, round(w))), int(max(1, round(h)))), rgba), x, y, clip)


def tile_fill(src, w, h):
    """src tiled to w x h."""
    w, h = int(round(w)), int(round(h))
    out = Image.new("RGBA", (max(1, w), max(1, h)), (0, 0, 0, 0))
    if src.width <= 0 or src.height <= 0:
        return out
    for yy in range(0, h, src.height):
        for xx in range(0, w, src.width):
            out.paste(src, (xx, yy))
    return out


def nine_slice(img, w, h, border, tiling):
    """Cornered tile: corners as is, edges stretched (tiled with tilingCenter), centre stretched or tiled."""
    w, h = int(round(w)), int(round(h))
    if w <= 0 or h <= 0:
        return None
    bx, by = border or (0, 0)
    bx = min(bx, img.width // 2, w // 2)
    by = min(by, img.height // 2, h // 2)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sw, sh = img.width, img.height
    cols = [(0, bx, 0, bx), (bx, sw - bx, bx, w - bx), (sw - bx, sw, w - bx, w)]
    rows = [(0, by, 0, by), (by, sh - by, by, h - by), (sh - by, sh, h - by, h)]
    for ri, (sy0, sy1, dy0, dy1) in enumerate(rows):
        for ci, (sx0, sx1, dx0, dx1) in enumerate(cols):
            if sx1 <= sx0 or sy1 <= sy0 or dx1 <= dx0 or dy1 <= dy0:
                continue
            piece = img.crop((sx0, sy0, sx1, sy1))
            tw, th = dx1 - dx0, dy1 - dy0
            if (tw, th) != piece.size:
                if tiling and (ri == 1 or ci == 1):
                    piece = tile_fill(piece, tw, th)
                else:
                    piece = piece.resize((tw, th), Image.BILINEAR)
            out.paste(piece, (dx0, dy0))
    return out


def brighten(img, f):
    a = np.asarray(img, dtype=np.float32).copy()
    a[..., :3] = np.clip(a[..., :3] * f, 0, 255)
    return Image.fromarray(a.astype(np.uint8), "RGBA")


def missing_box(w, h):
    w, h = int(max(4, round(w or 24))), int(max(4, round(h or 24)))
    im = Image.new("RGBA", (w, h), MISSING_RGBA)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, w - 1, h - 1), outline=(255, 0, 255, 255))
    d.line((0, 0, w - 1, h - 1), fill=(255, 255, 255, 200))
    d.line((0, h - 1, w - 1, 0), fill=(255, 255, 255, 200))
    return im


def sprite_render(ctx, d, w, h, frame=1, state=None, progress=0.5):
    """An RGBA image of sprite definition d drawn at w x h (frame 1-based), or a magenta box if unusable."""
    if d is None:
        return missing_box(w, h)
    kind = d["kind"]
    w, h = int(round(w)), int(round(h))
    if w <= 0 or h <= 0:
        return None
    if kind == "maskedshieldtype":
        mask = load_texture(d.get("texturefile2"))
        over = load_texture(d.get("texturefile1"))
        base = Image.new("RGBA", (w, h), (118, 118, 118, 255))
        if mask is not None:
            m = mask.resize((w, h), Image.BILINEAR).getchannel("A")
            base.putalpha(m)
        if over is not None:
            base.alpha_composite(over.resize((w, h), Image.BILINEAR))
        return base
    if kind in ("progressbartype", "circularprogressbartype"):
        full = load_texture(d.get("texturefile1"))
        empty = load_texture(d.get("texturefile2"))
        out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        if empty is not None:
            out.alpha_composite(empty.resize((w, h), Image.BILINEAR))
        if full is not None:
            f = full.resize((w, h), Image.BILINEAR)
            horizontal = str(d.get("horizontal", "yes")).lower() != "no"
            if horizontal:
                cw = int(w * progress)
                if cw > 0:
                    out.alpha_composite(f.crop((0, 0, cw, h)), (0, 0))
            else:
                ch = int(h * progress)
                if ch > 0:
                    out.alpha_composite(f.crop((0, h - ch, w, h)), (0, h - ch))
        elif d.get("color"):
            col = tuple(int(c * 255) if c <= 1 else int(c) for c in d["color"][:3])
            out.paste(col + (255,), (0, 0, int(w * progress), h))
        return out
    if kind == "piecharttype":           # engine data: a neutral two-slice pie
        ss = 4
        im = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        dr.pieslice((0, 0, w * ss - 1, h * ss - 1), -90, 162, fill=(112, 112, 112, 255))
        dr.pieslice((0, 0, w * ss - 1, h * ss - 1), 162, 270, fill=(176, 176, 176, 255))
        return im.resize((w, h), Image.LANCZOS)
    if kind == "linecharttype":
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(im).rectangle((0, 0, w - 1, h - 1), outline=(200, 200, 200, 160))
        return im
    img = ctx.sprite_image(d)
    if img is None:
        return missing_box(w, h)
    n = frame_count(d)
    frame = max(1, min(frame, n))
    fw = img.width // n
    fr = img.crop(((frame - 1) * fw, 0, frame * fw, img.height)) if n > 1 else img
    if kind == "corneredtilespritetype":
        out = nine_slice(fr, w, h, d.get("bordersize"), _yes(d.get("tilingcenter", "no")))
    elif fr.size != (w, h):
        out = fr.resize((w, h), Image.BILINEAR)
    else:
        out = fr
    if state and n == 1 and "buttonstate" in str(d.get("effectfile", "")).lower() and \
            "onlydisable" not in str(d.get("effectfile", "")).lower():
        if "pressed" in state:
            out = brighten(out, 0.85)
        elif "hover" in state:
            out = brighten(out, 1.25)
    if state and "disabled" in state and n < 4:
        g = np.asarray(out, dtype=np.float32).copy()
        lum = g[..., :3].mean(axis=2, keepdims=True)
        g[..., :3] = lum * 0.7
        out = Image.fromarray(g.astype(np.uint8), "RGBA")
    return out


# ====================================================================================== text
def text_runs(ctx, font, text, default_rgba):
    """Section-sign colour codes (X ... !) and pound-sign text icons -> [(char_or_Icon, rgba)]."""
    out = []
    col = default_rgba
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\u00a7" and i + 1 < len(text):
            code = text[i + 1]
            if code == "!":
                col = default_rgba
            else:
                c = font.colour_for(code) if font else None
                if c is None:
                    c = ctx.gfx["textcolors"].get(code)
                    c = (c + (default_rgba[3],)) if c else default_rgba
                col = c
            i += 2
            continue
        if ch == "\u00a3":
            m = re.match(r"\u00a3([A-Za-z0-9_\-]+)(\|(\d+))?\u00a3?", text[i:])
            if m:
                nm = m.group(1)
                sname = nm if nm.startswith("GFX_") else "GFX_" + nm
                d = ctx.gfx["sprites"].get(sname)
                img = None
                if d is not None:
                    fs = sprite_frame_size(ctx, d)
                    if fs:
                        img = sprite_render(ctx, d, fs[0], fs[1], int(m.group(3) or 1))
                else:
                    warn(f"text icon not declared: {sname}")
                out.append((Icon(img, sname), col))
                i += len(m.group(0))
                continue
        out.append((ch, col))
        i += 1
    return out


def wrap_runs(font, runs, max_w):
    """Greedy word wrap at spaces like the engine ('\\n' forces a break). max_w None = no wrap."""
    lines = []
    para = []
    paras = []
    for r in runs:
        if r[0] == "\n":
            paras.append(para)
            para = []
        else:
            para.append(r)
    paras.append(para)
    for para in paras:
        if max_w is None:
            lines.append(para)
            continue
        words, cur = [], []
        for r in para:
            if r[0] == " ":
                words.append(cur)
                cur = []
            else:
                cur.append(r)
        words.append(cur)
        line = []
        space = [(" ", para[0][1] if para else (255, 255, 255, 255))]
        for word in words:
            trial = line + (space if line else []) + word
            if line and not fits(font, trial, max_w):
                lines.append(line)
                line = list(word)
            else:
                line = trial          # a single word wider than the box overflows (fixedsize boxes cut it with ...)
        lines.append(line)
    return lines


# How a line is measured against maxWidth when wrapping/truncating. The screenshots fit 'extent' and 'strict' (a
# K-edged caption exactly as wide as its box wraps; "...SOCIALIST..." 348 px of advances / 356 px of ink fits 356);
# 'extent' is the safer one for layout work.
WRAP_RULE = os.environ.get("RENDER_GUI_WRAP", "extent")
# Which containers cut their children at their edges. The screenshots show text and buttons drawn past the edges of
# sized containers without a clipping key (the lobby's "info" box, the topbar clock), so 'scroll' (default) clips only
# containers with clipping = yes or a scrollbar; 'default' clips every container without clipping = no; 'explicit'
# only clipping = yes.
CLIP_RULE = os.environ.get("RENDER_GUI_CLIP", "scroll")


def slides(node):
    """show_position is only used by windows that animate (animation_type / show_animation_type); others fade in
    at position (vanilla menu_settings_ingame has a show_position but no animation and opens at position)."""
    return node.node("show_position") is not None and (node.has("animation_type") or
                                                        node.has("show_animation_type"))


def hidden_match(ctx, name):
    if not name:
        return False
    hit = False
    for pat in ctx.hidden:
        neg = pat.startswith("!")
        if fnmatch.fnmatchcase(name, pat[1:] if neg else pat):
            hit = not neg
            ctx.hidden_used.add(pat)
    return hit


def clips(node):
    """Whether a container cuts its children at its edges (see CLIP_RULE)."""
    v = str(node.get("clipping", "")).lower()
    if v == "no":
        return False
    if v == "yes" or CLIP_RULE == "default":
        return True
    if CLIP_RULE == "scroll":
        return bool(node.str("verticalScrollbar") or node.str("horizontalScrollbar"))
    return False


def fits(font, line, max_w):
    """Whether a line fits a box max_w wide (WRAP_RULE). 'extent' (default): up to the last glyph's right edge
    (advances + that glyph's xoffset + width - xadvance) <= max_w; 'strict': advances < max_w; 'adv': <= max_w."""
    w = font.width(line)
    if WRAP_RULE == "strict":
        return w < max_w
    if WRAP_RULE == "extent" and line:
        ch = line[-1][0]
        c = font.chars.get(ord(ch)) if isinstance(ch, str) else None
        if c is not None:
            w += c.get("xoffset", 0) + c.get("width", 0) - c.get("xadvance", 0)
    return w <= max_w


def truncate_line(font, line, max_w):
    dots = [(".", line[-1][1] if line else (255, 255, 255, 255))] * 3
    cur = list(line)
    while cur and not fits(font, cur + dots, max_w):
        cur.pop()
    while cur and cur[-1][0] == " ":
        cur.pop()
    return cur + dots


def draw_lines(ctx, canvas, font, lines, x, y, box_w, fmt, clip):
    """Draws lines (lists of runs) with line tops from y; x/box_w define the alignment box."""
    lh = font.line_height
    if not lines:
        return
    widths = [font.width(ln) for ln in lines]
    starts = []
    for wd in widths:
        if fmt in ("center", "centre") and box_w:
            starts.append((box_w - wd) // 2)
        elif fmt == "right" and box_w:
            starts.append(box_w - wd)
        else:
            starts.append(0)
    # the layer spans the real extent: centred/right text wider than its box starts left of x (drawn, not dropped)
    left = min(starts + [0])
    right = max([s + wd for s, wd in zip(starts, widths)] + [box_w or 0])
    pad = 48
    lw = int(right - left) + 2 * pad
    layer = Image.new("RGBA", (max(1, lw), len(lines) * lh + 2 * pad), (0, 0, 0, 0))
    missing = set()
    for li, ln in enumerate(lines):
        px = starts[li] - left + pad
        py = pad + li * lh
        for i, (ch, col) in enumerate(ln):
            if isinstance(ch, Icon):
                if ch.img is not None:
                    iy = py + (lh - ch.img.height) // 2
                    if 0 <= iy and iy + ch.img.height <= layer.height and px >= 0:
                        layer.alpha_composite(ch.img, (px, max(0, iy)))
                px += ch.w
                continue
            c = font.chars.get(ord(ch))
            if c is None:
                if ch not in (" ", "\t"):
                    missing.add(ch)
                continue
            t = font.tile(ch, col)
            if t:
                gx, gy = px + c.get("xoffset", 0), py + c.get("yoffset", 0)
                if gx >= 0 and gy >= 0 and gx + t.width <= layer.width and gy + t.height <= layer.height:
                    layer.alpha_composite(t, (gx, gy))
            nxt = ln[i + 1][0] if i + 1 < len(ln) else None
            px += font.advance(ch, nxt if isinstance(nxt, str) else None)
    if missing:
        warn(f"font {font.name}: no glyph for {ascii_only(''.join(sorted(missing)))}")
    canvas.blit(layer, x + left - pad, y - pad, clip)


# ====================================================================================== renderer
def short_type(et):
    return {"containerwindowtype": "window", "windowtype": "window", "instanttextboxtype": "text",
            "textboxtype": "textbox", "buttontype": "button", "guibuttontype": "guibutton", "icontype": "icon",
            "checkboxtype": "checkbox", "editboxtype": "editbox", "gridboxtype": "grid", "listboxtype": "listbox",
            "smoothlistboxtype": "smoothlist", "overlappingelementsboxtype": "overlap", "positiontype": "position",
            "extendedscrollbartype": "extscroll", "scrollbartype": "scrollbar", "dropdownboxtype": "dropdown",
            "expandbutton": "expandbtn", "expandedwindow": "expanded"}.get(et, et)


def outline_kind(et):
    if et in WINDOW_TYPES:
        return "window"
    if et in BUTTON_TYPES or et == "checkboxtype":
        return "button"
    if et in ICON_TYPES:
        return "icon"
    if et in TEXT_TYPES:
        return "text"
    if et in LIST_TYPES:
        return "list"
    if et == "editboxtype":
        return "edit"
    return "other"


class Renderer:
    def __init__(self, ctx, canvas):
        self.ctx = ctx
        self.canvas = canvas

    # ---- properties
    def props(self, node):
        """The element with its --prop overrides: key, sub.key (position.y, size.width, ...) or key={ block }."""
        nm = node.str("name")
        if nm and nm in self.ctx.props:
            node = Node(node)
            for key, val in self.ctx.props[nm]:
                parts = key.split(".")
                cur = node
                ok = True
                for p in parts[:-1]:
                    sub = cur.get(p)
                    if sub is None:
                        sub = Node()
                    elif not isinstance(sub, Node):
                        warn(f"--prop {nm}.{key}: {p} is '{sub}', not a block; ignored")
                        ok = False
                        break
                    sub = Node(sub)            # copied: the parsed tree is shared
                    cur.set(p, sub)
                    cur = sub
                if not ok:
                    continue
                old = cur.get(parts[-1])
                if isinstance(old, Node) and not isinstance(val, Node):
                    sub_keys = "/".join(dict.fromkeys(k for k, _ in old if k is not None)) or "x/y"
                    warn(f"--prop {nm}.{key}={val}: {parts[-1]} is a block; set one value with "
                         f"{nm}.{key}.<{sub_keys}>=N or the whole block with {nm}.{key}={{ ... }}; ignored")
                    continue
                cur.set(parts[-1], node_copy(val) if isinstance(val, Node) else val)
        return node

    def element_sprite(self, node):
        for key in ("quadTextureSprite", "spriteType", "spritetype"):
            v = node.str(key)
            if v:
                return v
        return None

    def own_size(self, et, node, pw, ph, rem=(None, None)):
        """(w, h) of an element before placement; rem = space left from its position to the parent's far edges."""
        ctx = self.ctx
        scale = dim(node.get("scale"), 1, 1.0) if node.has("scale") else 1.0
        size = node.node("size")
        if et in WINDOW_TYPES or et in LIST_TYPES or et in SCROLL_TYPES or et in ("editboxtype", "dropdownboxtype"):
            if size is None:
                return (0.0, 0.0)
            w = dim(size.get("width", size.get("x")), pw, 0, size=True, remaining=rem[0])
            h = dim(size.get("height", size.get("y")), ph, 0, size=True, remaining=rem[1])
            mn, mx = size.node("min"), size.node("max")
            w0, h0 = w, h
            if mn is not None:
                w = max(w, dim(mn.get("width", mn.get("x")), pw, 0, size=True))
                h = max(h, dim(mn.get("height", mn.get("y")), ph, 0, size=True))
            if _yes(size.get("preserve_aspect_ratio", "no")) and w0 > 0 and h0 > 0:
                s = max(w / w0, h / h0)
                w, h = w0 * s, h0 * s
            if mx is not None:
                w = min(w, dim(mx.get("width", mx.get("x")), pw, w, size=True))
                h = min(h, dim(mx.get("height", mx.get("y")), ph, h, size=True))
            return (w, h)
        if et in TEXT_TYPES:
            return (dim(node.get("maxWidth"), pw, 0), dim(node.get("maxHeight"), ph, 0))
        if et in BUTTON_TYPES or et in ICON_TYPES or et == "checkboxtype":
            if size is not None:
                return (dim(size.get("width", size.get("x")), pw, 0, size=True) * scale,
                        dim(size.get("height", size.get("y")), ph, 0, size=True) * scale)
            d = ctx.sprite(self.element_sprite(node))
            fs = sprite_frame_size(ctx, d)
            if fs is None:
                return (24.0 * scale, 24.0 * scale) if self.element_sprite(node) else (0.0, 0.0)
            return (fs[0] * scale, fs[1] * scale)
        return (0.0, 0.0)

    def place(self, et, node, prect):
        px, py, pw, ph = prect
        posn = node.node("position")
        if self.ctx.args.shown and slides(node):
            posn = node.node("show_position")
        ox = dim(posn.get("x"), pw, 0) if posn is not None else 0.0
        oy = dim(posn.get("y"), ph, 0) if posn is not None else 0.0
        offscreen = abs(ox) >= OFFSCREEN or abs(oy) >= OFFSCREEN
        ax, ay = anchor(node.get("orientation"))
        gx, gy = anchor(node.get("origo"))
        rem = (pw - apos(ax, int(pw)) - ox, ph - apos(ay, int(ph)) - oy)
        w, h = self.own_size(et, node, pw, ph, rem)
        # %-sizes are already whole (truncated in dim); what is left is scale = 0.85 icons, rounded to nearest
        w, h = int(np.floor(w + 0.5)), int(np.floor(h + 0.5))
        # integer maths like the engine: a centred window of odd size sits at parent/2 - size//2
        x = int(px) + apos(ax, int(pw)) + int(np.floor(ox + 1e-6)) - apos(gx, w)
        y = int(py) + apos(ay, int(ph)) + int(np.floor(oy + 1e-6)) - apos(gy, h)
        if _yes(node.get("centerPosition", "no")) and (et in ICON_TYPES or et in BUTTON_TYPES or
                                                         et == "checkboxtype"):
            x -= w // 2
            y -= h // 2
        return [x, y, w, h], offscreen

    # ---- table / outline bookkeeping
    def record(self, depth, name, et, rect, note=""):
        self.ctx.rows.append((depth, name or "-", short_type(et), rect[0], rect[1], rect[2], rect[3], note))
        self.ctx.outlines.append((outline_kind(et), name or "-", rect))

    def extend_bounds(self, x, y, w, h):
        if w <= 0 or h <= 0:
            return
        b = self.ctx.bounds
        nb = (x, y, x + w, y + h)
        self.ctx.bounds = nb if b is None else (min(b[0], nb[0]), min(b[1], nb[1]), max(b[2], nb[2]), max(b[3], nb[3]))

    # ---- elements
    def render(self, et, node, prect, clip, depth):
        ctx = self.ctx
        node = self.props(node)
        name = node.str("name")
        if hidden_match(ctx, name):
            ctx.skipped.append((name, "hidden (--hide)"))
            return
        if et == "expandedwindow" and not ctx.args.shown:
            ctx.skipped.append((name, "expandedWindow (dropdown closed; --shown opens it)"))
            return
        if et in WINDOW_TYPES and ctx.relayout:
            node = self.event_relayout(node, prect)
        rect, off = self.place(et, node, prect)
        if off:
            ctx.skipped.append((name, f"off-screen position ({rect[0]},{rect[1]})"))
            return
        if name in ctx.moves:
            dx, dy = ctx.moves[name]
            rect[0] += dx
            rect[1] += dy
        if slides(node) and not ctx.args.shown:
            sp = node.node("show_position")
            pp = node.node("position")
            if pp is None or (sp.get("x"), sp.get("y")) != (pp.get("x"), pp.get("y")):
                log(f"note: {ascii_only(name)} has show_position {sp.get('x')},{sp.get('y')} (drawn at position; "
                    "--shown draws it where the engine shows it)")
        if et in WINDOW_TYPES:
            self.window(et, node, rect, clip, depth)
        elif et in BUTTON_TYPES or et == "checkboxtype":
            self.button(et, node, rect, clip, depth)
        elif et in ICON_TYPES:
            self.icon(et, node, rect, clip, depth)
        elif et in TEXT_TYPES:
            self.textbox(et, node, rect, clip, depth)
        elif et == "editboxtype":
            self.editbox(et, node, rect, clip, depth)
        elif et in LIST_TYPES:
            self.listbox(et, node, rect, clip, depth)
        elif et == "dropdownboxtype":
            self.record(depth, name, et, rect)
            self.children(node, rect, clip, depth + 1)
        elif et == "positiontype":
            self.record(depth, name, et, rect)
        elif et in SCROLL_TYPES:
            self.slider(et, node, rect, clip, depth)
        else:
            ctx.unknown[et] = ctx.unknown.get(et, 0) + 1
            self.record(depth, name, et, rect, "unknown type, skipped")

    def children(self, node, rect, clip, depth):
        for k, v in node:
            if k is None or not isinstance(v, Node):
                continue
            kl = k.lower()
            if kl in ELEMENT_TYPES:
                self.render(kl, v, rect, clip, depth)
            elif kl not in PROPERTY_BLOCKS and v.str("name") and kl not in SPRITE_KINDS:
                self.ctx.unknown[kl] = self.ctx.unknown.get(kl, 0) + 1
                self.record(depth, v.str("name"), kl, rect, "unknown type, skipped")

    def window(self, et, node, rect, clip, depth):
        ctx = self.ctx
        x, y, w, h = rect
        name = node.str("name")
        note = self.backgrounds(node, rect, clip)
        self.record(depth, name, et, rect, note)
        own_clip = clip
        if w > 0 and h > 0 and clips(node):
            own_clip = intersect(clip, (x, y, x + w, y + h))
        self.children(node, rect, own_clip, depth + 1)
        sb = node.str("verticalScrollbar")
        if sb and not ctx.args.no_scrollbars and w > 0 and h > 0:
            self.scrollbar(sb, rect, own_clip, depth + 1)

    def background_rect(self, bg, rect):
        """(sprite def, x, y, w, h, kind) of one background block: at the window corner + its position; a
        corneredTile is sized to the window, any other sprite keeps its native frame size (vanilla deploy_entry puts
        three backgrounds side by side at x = 0/110/280, techtree folder items draw a 183x84 background in a 72x72
        window); a tiny texture (1x1 in_game_menu_dark_overlay) is a runtime-sized fill and is stretched."""
        ctx = self.ctx
        x, y, w, h = rect
        d = ctx.sprite(self.element_sprite(bg))
        p = bg.node("position")
        ox = int(np.floor(dim(p.get("x"), w, 0) + 1e-6)) if p is not None else 0
        oy = int(np.floor(dim(p.get("y"), h, 0) + 1e-6)) if p is not None else 0
        fs = sprite_frame_size(ctx, d) if d is not None else None
        if d is None:
            bw, bh, kind = w, h, "missing"
        elif d["kind"] == "corneredtilespritetype":
            bw = w if w > 0 else (fs[0] if fs else 0)
            bh = h if h > 0 else (fs[1] if fs else 0)
            kind = "tile"
        elif fs and fs[0] <= 4 and fs[1] <= 4 and w > 0 and h > 0:
            bw, bh, kind = w, h, "fill"
        elif fs:
            bw, bh, kind = fs[0], fs[1], "native"
        else:
            bw, bh, kind = w, h, "native"
        return d, x + ox, y + oy, bw, bh, kind, (ox, oy), fs

    def backgrounds(self, node, rect, clip):
        """Draws every background block of a window in file order; returns the table note."""
        ctx = self.ctx
        x, y, w, h = rect
        name = node.str("name") or "?"
        bgs = [b for b in node.all("background") if isinstance(b, Node)]
        notes = []
        for bg in bgs:
            sname = self.element_sprite(bg)
            d, bx, by, bw, bh, kind, off, fs = self.background_rect(bg, rect)
            notes.append(f"bg={sname}" + (f"@{off[0]},{off[1]}" if off != (0, 0) else "") +
                         (f"({bw}x{bh})" if kind == "native" and (bw, bh) != (w, h) else ""))
            if bw > 0 and bh > 0:
                self.draw_sprite(d, bx, by, bw, bh, clip, frame=1)
                self.extend_bounds(bx, by, bw, bh)
            if kind == "native" and w > 0 and h > 0 and fs and (bw, bh) != (w, h):
                warn(f"{name}: background {sname} is drawn at its native {bw}x{bh} in a {w}x{h} window (plain "
                     "spriteType backgrounds are not stretched; only corneredTile ones take the window size)")
        if len(bgs) > 1:
            warn(f"{name}: {len(bgs)} background blocks, drawn in file order (several backgrounds per window are "
                 "not verified against an in-game screenshot)")
        elif any(self.background_rect(b, rect)[6] != (0, 0) for b in bgs):
            warn(f"{name}: background drawn at its position offset (positioned backgrounds are not verified against "
                 "an in-game screenshot)")
        return " ".join(notes)

    # ---- event windows
    def event_relayout(self, node, prect):
        """The engine re-flows the eventwindow.gui family (a window with a 'midsection' holding 'Description' and a
        'bottom_Window'): the midsection grows to the description (max(its height, Description.y + text height)),
        bottom_Window moves just below it and grows with the options grid, bottom_window_end follows, the window
        grows to match. Returns a modified copy (the .gui positions with --no-relayout)."""
        ctx = self.ctx
        kids = {}
        for i, (k, v) in enumerate(node):
            if k is not None and k.lower() in WINDOW_TYPES and isinstance(v, Node) and v.str("name"):
                kids.setdefault(v.str("name").lower(), (i, v))
        if "midsection" not in kids or "bottom_window" not in kids:
            return node
        mi, mid = kids["midsection"]
        bi, bot = kids["bottom_window"]
        mid, bot = self.props(mid), self.props(bot)
        desc = next((self.props(v) for k, v in mid if k is not None and k.lower() in TEXT_TYPES and
                     isinstance(v, Node) and v.str("name") == "Description"), None)
        if desc is None:
            return node
        _, _, pw, ph = prect
        wsize = node.node("size")
        win_w = dim(wsize.get("width"), pw, 0, size=True) if wsize is not None else 0
        win_h0 = int(dim(wsize.get("height"), ph, 0, size=True)) if wsize is not None else 0

        def ypos(n):
            p = n.node("position")
            return int(dim(p.get("y"), win_h0, 0)) if p is not None else 0

        def height(n, parent_h=win_h0):
            s = n.node("size")
            return int(dim(s.get("height", s.get("y")), parent_h, 0, size=True)) if s is not None else 0

        # the description's text height, laid out exactly like textbox() does it
        raw = ctx.texts["Description"] if "Description" in ctx.texts else desc.str("text")
        font = ctx.font(desc.str("font"))
        if font is None:
            return node
        bnode = desc.node("borderSize")
        border = (int(dim(bnode.get("x"), 0, 0)), int(dim(bnode.get("y"), 0, 0))) if bnode is not None else (0, 0)
        mw, mh = dim(desc.get("maxWidth"), win_w, 0), dim(desc.get("maxHeight"), win_h0, 0)
        if raw:
            lines = self.text_layout(desc, font, ctx.localise(raw), mw, mh, _yes(desc.get("fixedsize", "no")),
                                     border)
            desc_h = len(lines) * font.line_height + 2 * border[1]
        else:
            lines, desc_h = [], font.line_height
        mid_y, mid_h0 = ypos(mid), height(mid)
        mid_h = max(mid_h0, ypos(desc) + desc_h)
        bot_y0, bot_y = ypos(bot), mid_y + mid_h
        bot_h0 = height(bot)
        # the options grid: --grid entries (else one row), slot height from slotsize
        content = bot_h0
        grid = next((v for k, v in bot if k is not None and k.lower() in LIST_TYPES and isinstance(v, Node)), None)
        grid_bottom = None
        if grid is not None:
            gname = grid.str("name")
            slot = grid.node("slotsize")
            sh = dim(slot.get("height", slot.get("y")), 0, 0) if slot is not None else 0
            n = 1
            if gname in ctx.grids:
                tpl, cnt = ctx.grids[gname]
                n = cnt if cnt is not None else max(1, int(height(grid, bot_h0) // sh) if sh else 1)
            grid_bottom = ypos(grid) + int(n * sh)
        bot_h = max(bot_h0, grid_bottom or 0)
        # what bottom_Window shows: native plain backgrounds, its grid (for the window height)
        shown_bottom = grid_bottom or 0
        for b in bot.all("background"):
            if isinstance(b, Node):
                d, bx, by, bw, bh, kind, off, fs = self.background_rect(b, (0, 0, int(win_w), bot_h))
                if kind != "tile":
                    shown_bottom = max(shown_bottom, by + bh)
                elif bot_h > 0:
                    shown_bottom = max(shown_bottom, bot_h)
        new = node_copy(node)
        mid2 = node_copy(mid)
        if mid_h != mid_h0:
            s = mid2.node("size") or Node()
            s = Node(s)
            s.set("height", str(mid_h))
            mid2.set("size", s)
        bot2 = node_copy(bot)
        p = Node(bot2.node("position") or Node())
        p.set("y", str(bot_y))
        bot2.set("position", p)
        if bot_h != bot_h0:
            s = Node(bot2.node("size") or Node())
            s.set("height", str(bot_h))
            bot2.set("size", s)
        new[mi] = (new[mi][0], mid2)
        new[bi] = (new[bi][0], bot2)
        end_note = ""
        win_h = max(win_h0, bot_y + shown_bottom)
        if "bottom_window_end" in kids:
            ei, end = kids["bottom_window_end"]
            end2 = node_copy(self.props(end))
            p = Node(end2.node("position") or Node())
            end_y = bot_y + bot_h
            p.set("y", str(end_y))
            end2.set("position", p)
            new[ei] = (new[ei][0], end2)
            win_h = max(win_h0, end_y + height(end))
            end_note = f", bottom_window_end y {end_y}"
        if win_h != win_h0 and wsize is not None:
            s = Node(new.node("size"))
            s.set("height", str(win_h))
            new.set("size", s)
        log(f"note: {ascii_only(node.str('name'))} event layout (engine re-flow): Description {len(lines)} lines "
            f"({desc_h} px) -> midsection h {mid_h0}->{mid_h}, bottom_Window y {bot_y0}->{bot_y}"
            + (f" h {bot_h0}->{bot_h}" if bot_h != bot_h0 else "") + end_note +
            f", window h {win_h0}->{win_h}; --text Description=... sets the text, --no-relayout keeps the .gui "
            "positions")
        return new

    def scrollbar(self, name, rect, clip, depth):
        ctx = self.ctx
        hits = ctx.gui["names"].get(name)
        if not hits:
            warn(f"scrollbar template not found: {name}")
            return
        rel, real, origin, trail, et, _ = hits[0]
        sb = node_at(gui_tree(ctx.gui["files"][rel][1]), trail)
        x, y, w, h = rect
        size = sb.node("size")
        bw = int(dim(size.get("width", size.get("x")), w, 18)) if size is not None else 18
        bh = h
        ax, ay = anchor(sb.get("orientation"))
        gx, gy = anchor(sb.get("origo"))
        p = sb.node("position")
        ox = dim(p.get("x"), w, 0) if p is not None else 0
        oy = dim(p.get("y"), h, 0) if p is not None else 0
        bx = int(x + ax * w + ox - gx * bw)
        by = int(y + ay * h + oy - gy * bh)
        for part in ("background", "track"):
            pn = sb.node(part)
            if pn is None:
                continue
            d = ctx.sprite(self.element_sprite(pn))
            if d is None:
                continue
            p = pn.node("position")
            ox = dim(p.get("x"), bw, 0) if p is not None else 0
            oy = dim(p.get("y"), bh, 0) if p is not None else 0
            fs = sprite_frame_size(ctx, d) or (bw, bh)
            pw_ = bw if part == "background" else fs[0]
            self.draw_sprite(d, bx + ox, by + oy, pw_, bh - 2 * max(0, oy), clip)
        for part, at_bottom in (("decreaseButton", False), ("increaseButton", True)):
            pn = sb.node(part)
            if pn is None:
                continue
            d = ctx.sprite(self.element_sprite(pn))
            fs = sprite_frame_size(ctx, d)
            if not fs:
                continue
            p = pn.node("position")
            ox = dim(p.get("x"), bw, 0) if p is not None else 0
            oy = dim(p.get("y"), bh, 0) if p is not None else 0
            if at_bottom:
                px_ = bx + (bw + ox if ox < 0 else ox)
                py_ = by + (bh + oy if oy < 0 else bh - fs[1])
            else:
                px_, py_ = bx + ox, by + oy
            self.draw_sprite(d, px_, py_, fs[0], fs[1], clip)
        self.record(depth, name, "extendedscrollbartype", [bx, by, bw, bh], "container scrollbar")

    def slider(self, et, node, rect, clip, depth):
        """A standalone slider/scrollbar, laid out like the engine does it (approximation): background over the
        rect, decrease/left button at the start, increase/right button at the end, track stretched between them,
        slider at startValue/maxValue (else --progress)."""
        ctx = self.ctx
        x, y, w, h = rect
        name = node.str("name")
        if w <= 0 or h <= 0:
            self.record(depth, name, et, rect, "no size, skipped")
            return
        parts = {}
        if et == "scrollbartype":           # old format: role keys name child guiButtonTypes
            kids = {v.str("name"): v for k, v in node if isinstance(v, Node) and v.str("name")}
            for role, key in (("slider", "slider"), ("track", "track"), ("dec", "leftbutton"), ("inc", "rightbutton")):
                ref = node.str(key)
                if ref and ref in kids:
                    parts[role] = self.element_sprite(kids[ref])
        for role, key in (("background", "background"), ("slider", "slider"), ("track", "track"),
                          ("dec", "decreaseButton"), ("inc", "increaseButton")):
            pn = node.node(key)
            if pn is not None and self.element_sprite(pn):
                parts[role] = self.element_sprite(pn)
        hz = node.get("horizontal")
        horizontal = (str(hz).lower() in ("1", "yes", "true")) if hz is not None else w >= h
        sizes = {r: sprite_frame_size(ctx, ctx.sprite(sn)) or (16, 16) for r, sn in parts.items()}
        if "background" in parts:
            self.draw_sprite(ctx.sprite(parts["background"]), x, y, w, h, clip)
        lo = sizes["dec"][0 if horizontal else 1] if "dec" in parts else 0
        hi = sizes["inc"][0 if horizontal else 1] if "inc" in parts else 0
        if "track" in parts:
            tw, th = sizes["track"]
            if horizontal:
                self.draw_sprite(ctx.sprite(parts["track"]), x + lo, y + (h - th) // 2, w - lo - hi, th, clip)
            else:
                self.draw_sprite(ctx.sprite(parts["track"]), x + (w - tw) // 2, y + lo, tw, h - lo - hi, clip)
        for role, at_end in (("dec", False), ("inc", True)):
            if role in parts:
                bw, bh = sizes[role]
                bx = (x + w - bw if at_end else x) if horizontal else x + (w - bw) // 2
                by = y + (h - bh) // 2 if horizontal else (y + h - bh if at_end else y)
                self.draw_sprite(ctx.sprite(parts[role]), bx, by, bw, bh, clip)
        if "slider" in parts:
            try:
                lo_v = float(node.get("minValue", 0))
                frac = (float(node.get("startValue")) - lo_v) / (float(node.get("maxValue")) - lo_v)
            except (TypeError, ValueError, ZeroDivisionError):
                frac = ctx.args.progress
            frac = min(1.0, max(0.0, frac))
            sw_, sh_ = sizes["slider"]
            if horizontal:
                sx = x + lo + int((w - lo - hi - sw_) * frac)
                self.draw_sprite(ctx.sprite(parts["slider"]), sx, y + (h - sh_) // 2, sw_, sh_, clip)
            else:
                sy = y + lo + int((h - lo - hi - sh_) * frac)
                self.draw_sprite(ctx.sprite(parts["slider"]), x + (w - sw_) // 2, sy, sw_, sh_, clip)
        self.extend_bounds(x, y, w, h)
        self.record(depth, name, et, rect, "slider (approximate layout) " + " ".join(f"{k}={v}" for k, v in
                                                                                    parts.items()))

    def draw_sprite(self, d, x, y, w, h, clip, frame=1, state=None):
        if w <= 0 or h <= 0:
            return
        if d is None:
            self.canvas.blit(missing_box(w, h), x, y, clip)
            return
        # big stretched spriteTypes (scrims): resample only the visible part
        if d["kind"] in ("spritetype", "textspritetype", "frameanimatedspritetype") and not state and \
                (w * h > 1_500_000):
            img = self.ctx.sprite_image(d)
            if img is None:
                self.canvas.blit(missing_box(w, h), x, y, clip)
                return
            n = frame_count(d)
            fw = img.width // n
            f = max(1, min(frame, n))
            fr = img.crop(((f - 1) * fw, 0, f * fw, img.height)) if n > 1 else img
            self.canvas.blit_scaled(fr, x, y, w, h, clip)
            return
        if d["kind"] == "corneredtilespritetype" and _yes(d.get("tilingcenter", "no")) is False and \
                (d.get("bordersize") in (None, (0, 0))) and w * h > 1_500_000:
            img = self.ctx.sprite_image(d)
            if img is not None:
                self.canvas.blit_scaled(img, x, y, w, h, clip)
                return
        im = sprite_render(self.ctx, d, w, h, frame, state, self.ctx.args.progress)
        self.canvas.blit(im, x, y, clip)

    def state_of(self, name):
        return self.ctx.states.get(name, set()) if name else set()

    def button(self, et, node, rect, clip, depth):
        ctx = self.ctx
        x, y, w, h = rect
        name = node.str("name")
        sname = self.element_sprite(node)
        d = ctx.sprite(sname) if sname else None
        st = self.state_of(name)
        n = frame_count(d) if d else 1
        if name in ctx.frames:
            frame = ctx.frames[name]
        elif et == "checkboxtype":
            frame = 2 if "checked" in st else 1
            if "hover" in st and n >= 4:
                frame += 2 if n >= 4 else 0
        elif et == "guibuttontype":
            frame = 1
        else:
            frame = 1
            if "disabled" in st and n >= 4:
                frame = 4
            elif "pressed" in st and n >= 3:
                frame = 3
            elif ("hover" in st or "pressed" in st) and n >= 2:
                frame = 2
        if sname:
            self.draw_sprite(d, x, y, w, h, clip, frame, st or None)
            self.extend_bounds(x, y, w, h)
        raw = node.str("buttonText") or node.str("text")      # vanilla tabs use text/font on a buttonType
        if name in ctx.texts:
            raw = ctx.texts[name]
        note = f"{sname or ''} f{frame}/{n}"
        fname = node.str("buttonFont") or node.str("font")
        if raw:
            text = ctx.localise(raw)
            font = ctx.font(fname)
            if font is not None:
                code = node.str("text_color_code")
                col = (font.colour_for(code) if code else None) or font.colour
                runs = text_runs(ctx, font, text, col)
                lines = wrap_runs(font, runs, None)
                fmt = str(node.get("format", "center")).lower()
                tw = max(font.width(ln) for ln in lines) if lines else 0
                th = font.line_height * len(lines)
                ty = y + (h - th) // 2
                tx = x
                draw_lines(ctx, self.canvas, font, lines, tx, ty, w if fmt in ("center", "centre", "right") else 0,
                           fmt, clip)
                note += f" font={fname} text={raw}"
                if tw > w > 0:
                    warn(f"{name}: buttonText '{ascii_only(raw)}' is {tw} px wide, button {w} px")
        self.record(depth, name, et, rect, note)

    def icon(self, et, node, rect, clip, depth):
        ctx = self.ctx
        x, y, w, h = rect
        name = node.str("name")
        sname = self.element_sprite(node)
        d = ctx.sprite(sname) if sname else None
        if name in ctx.frames:
            frame = ctx.frames[name]
        elif node.has("frame"):
            frame = int(dim(node.get("frame"), 1, 1))
        else:
            frame = 1
        if d is not None and d["kind"] == "piecharttype":
            # measured in game: a pie of radius r hangs from its position (top = y), centred about 2 px right of x
            x = x - w // 2 + 2
            rect = [x, y, w, h]
        if sname:
            self.draw_sprite(d, x, y, w, h, clip, max(1, frame))
            self.extend_bounds(x, y, w, h)
        self.record(depth, name, et, rect, f"{sname or ''}" + (f" f{frame}" if frame != 1 else "") +
                    (f" scale={node.get('scale')}" if node.has("scale") else ""))

    def text_layout(self, node, font, text, maxw, maxh, fixed, border):
        """-> (lines, inner box height)"""
        bx, by = border
        code = node.str("text_color_code")
        col = (font.colour_for(code) if code else None) or font.colour
        runs = text_runs(self.ctx, font, text, col)
        wrap_w = (maxw - 2 * bx) if maxw > 0 else None
        lines = wrap_runs(font, runs, wrap_w)
        lh = font.line_height
        truncate = fixed or _yes(node.get("truncate", "no"))
        if truncate and maxh > 0:
            avail = maxh - 2 * by
            max_lines = max(1, (avail - 1) // lh)       # the engine keeps lines * lineHeight < maxHeight
            if len(lines) > max_lines:
                # the last line that fits gets the rest of the text, cut with "..." (the engine does not stop at
                # the word wrap: "Union of Soviet Sociali..." rather than "Union of Soviet...")
                rest = []
                for ln in lines[max_lines - 1:]:
                    if rest and ln:
                        rest.append((" ", ln[0][1]))
                    rest += ln
                lines = lines[:max_lines - 1] + [truncate_line(font, rest, wrap_w if wrap_w else 10 ** 6)]
                self.truncated = True
        if truncate and wrap_w and any(not fits(font, ln, wrap_w) for ln in lines):
            lines = [truncate_line(font, ln, wrap_w) if not fits(font, ln, wrap_w) else ln for ln in lines]
            self.truncated = True
        return lines

    def textbox(self, et, node, rect, clip, depth):
        ctx = self.ctx
        x, y, w, h = rect
        name = node.str("name")
        raw = node.str("text")
        if name in ctx.texts:
            raw = ctx.texts[name]
        fname = node.str("font")
        font = ctx.font(fname)
        bnode = node.node("borderSize")
        border = (int(dim(bnode.get("x"), 0, 0)), int(dim(bnode.get("y"), 0, 0))) if bnode is not None else (0, 0)
        fixed = _yes(node.get("fixedsize", "no"))
        placeholder = False
        if raw is None or raw == "":
            if ctx.args.no_placeholders:
                self.record(depth, name, et, rect, f"font={fname} (engine-filled)")
                return
            text = f"<{name}>"
            placeholder = True
        else:
            text = ctx.localise(raw)
        note = f"font={fname} " + ("(engine-filled)" if placeholder else f"text={raw}")
        if font is None:
            self.record(depth, name, et, rect, note + " NO FONT")
            return
        if placeholder:          # one line, cut to the box: the name only shows where the engine's text goes
            lines = [[(ch, PLACEHOLDER_RGBA) for ch in text]]
            if w > 0 and not fits(font, lines[0], w - 2 * border[0]):
                lines = [truncate_line(font, lines[0], w - 2 * border[0])]
        else:
            self.truncated = False
            lines = self.text_layout(node, font, text, w, h, fixed, border)
            if self.truncated:
                note += " CUT"
                warn(f"{name}: text {raw} does not fit {w}x{h} in {fname}; the engine cuts it with '...'")
            elif not fixed and h > 0 and len(lines) > max(1, (h - 2 * border[1]) // font.line_height):
                note += " GROWS"
                warn(f"{name}: text {raw} needs {len(lines)} lines of {font.line_height} px, more than maxHeight {h} "
                     "holds; the box grows (not fixedsize)")
            wrap_w = w - 2 * border[0]
            if w > 0 and wrap_w > 0 and not self.truncated and any(not fits(font, ln, wrap_w) for ln in lines):
                widest = max(font.width(ln) for ln in lines)
                note += " OVERFLOWS"
                warn(f"{name}: text {raw} has a line {widest} px wide in a {wrap_w} px box ({fname}); a word longer "
                     "than the box is not broken and sticks out" +
                     (" on both sides (centred)" if str(node.get("format", "left")).lower() in ("center", "centre")
                      else " to the left (right-aligned)" if str(node.get("format", "")).lower() == "right"
                      else " to the right"))
        lh = font.line_height
        text_h = len(lines) * lh
        inner_h = (h - 2 * border[1]) if h > 0 else text_h
        if not fixed and text_h > inner_h:
            inner_h = text_h
        va = str(node.get("vertical_alignment", "top")).lower()
        ty = y + border[1]
        if va in ("center", "centre"):
            ty += (inner_h - text_h) // 2
        elif va == "bottom":
            ty += inner_h - text_h
        fmt = str(node.get("format", "left")).lower()
        box_w = (w - 2 * border[0]) if w > 0 else 0
        tw = max([font.width(ln) for ln in lines] + [0])
        tex = node.str("textureFile")
        if tex:
            # a textured box (core.gui ToolTip): the texture as a cornered tile with borderSize corners, around the
            # text (shrink-wrapped unless fixedsize)
            img = load_texture(tex)
            if img is not None:
                bw = w if fixed and w > 0 else tw + 2 * border[0]
                bh = h if fixed and h > 0 else text_h + 2 * border[1]
                if bw > 0 and bh > 0:
                    self.canvas.blit(nine_slice(img, bw, bh, border, False), x, y, clip)
                    if not fixed:
                        box_w = tw
        draw_lines(ctx, self.canvas, font, lines, x + border[0], ty, box_w, fmt, clip)
        if w <= 0:
            rect = [x, y, tw + 2 * border[0], text_h + 2 * border[1]]
        elif not fixed and text_h + 2 * border[1] > h:
            rect = [x, y, w, text_h + 2 * border[1]]
        self.extend_bounds(*rect)
        self.record(depth, name, et, rect, note + (f" lines={len(lines)}" if len(lines) > 1 else ""))

    def editbox(self, et, node, rect, clip, depth):
        ctx = self.ctx
        x, y, w, h = rect
        name = node.str("name")
        tex = node.str("textureFile")
        if tex:
            img = load_texture(tex)
            if img is not None:
                self.canvas.blit_scaled(img, x, y, w, h, clip)
        raw = ctx.texts.get(name, node.str("text"))
        font = ctx.font(node.str("font"))
        bnode = node.node("borderSize")
        bx, by = (int(dim(bnode.get("x"), 0, 0)), int(dim(bnode.get("y"), 0, 0))) if bnode is not None else (0, 0)
        if font is not None:
            if raw:
                runs = text_runs(ctx, font, ctx.localise(raw), font.colour)
            elif not ctx.args.no_placeholders:
                runs = [(ch, PLACEHOLDER_RGBA) for ch in f"<{name}>"]
            else:
                runs = []
            if runs:
                draw_lines(ctx, self.canvas, font, [runs], x + bx, y + by, 0, "left", intersect(clip, (x, y, x + w,
                                                                                                    y + h)))
        self.extend_bounds(x, y, w, h)
        self.record(depth, name, et, rect, f"font={node.str('font')}")

    def listbox(self, et, node, rect, clip, depth):
        ctx = self.ctx
        x, y, w, h = rect
        name = node.str("name")
        slot = node.node("slotsize")
        sw = dim(slot.get("width", slot.get("x")), w, 0) if slot is not None else 0
        sh = dim(slot.get("height", slot.get("y")), h, 0) if slot is not None else 0
        note = f"slot={int(sw)}x{int(sh)}" if slot is not None else ""
        if name in ctx.grids:
            tpl, count = ctx.grids[name]
            self.fill_grid(node, rect, clip, depth, tpl, count, sw, sh)
            note += f" filled with {tpl}"
        else:
            self.placeholder_box(x, y, w, h, clip, name, (sw, sh))
        self.extend_bounds(x, y, max(w, 1), max(h, 1))
        self.record(depth, name, et, rect, note)

    def placeholder_box(self, x, y, w, h, clip, name, slot=(0, 0)):
        if w <= 0 or h <= 0:
            w, h = max(w, 120), max(h, 24)
        layer = Image.new("RGBA", (int(w), int(h)), (0, 0, 0, 0))
        dr = ImageDraw.Draw(layer)
        col = (200, 120, 255, 200)
        sw, sh = slot
        if sw > 4 and sh > 4:
            for gx in range(0, int(w), int(sw)):
                for gy in range(0, int(h), int(sh)):
                    dr.rectangle((gx + 1, gy + 1, gx + int(sw) - 2, gy + int(sh) - 2), outline=(200, 120, 255, 70))
        for i in range(0, int(w), 8):
            dr.line((i, 0, min(i + 4, w - 1), 0), fill=col)
            dr.line((i, h - 1, min(i + 4, w - 1), h - 1), fill=col)
        for i in range(0, int(h), 8):
            dr.line((0, i, 0, min(i + 4, h - 1)), fill=col)
            dr.line((w - 1, i, w - 1, min(i + 4, h - 1)), fill=col)
        dr.text((4, 3), ascii_only(name or "?"), fill=col, font=small_font())
        self.canvas.blit(layer, x, y, clip)

    def fill_grid(self, node, rect, clip, depth, tpl, count, sw, sh):
        ctx = self.ctx
        x, y, w, h = rect
        tnode, tet = find_element(ctx, tpl, None)
        if tnode is None:
            warn(f"grid template not found: {tpl}")
            return
        tw, th = self.own_size(tet, tnode, w, h)
        sw = sw or tw or 100
        sh = sh or th or 50
        name = node.str("name") or "?"

        def num(v):
            try:
                return max(0, int(float(v)))
            except (TypeError, ValueError):
                return 0
        hor, ver = num(node.get("max_slots_horizontal")), num(node.get("max_slots_vertical"))
        ms = node.node("max_slots")              # max_slots = { x = 6 y = 2 }: column and row caps
        ms_x, ms_y = (num(ms.get("x")), num(ms.get("y"))) if ms is not None else (0, 0)
        column_major = False
        if hor:
            cols = hor
        elif ms_x:
            cols = ms_x
        elif ver:
            column_major = True                  # fills down ver rows, then the next column
            cols = None
        else:
            cols = max(1, int(w // sw)) if w > 0 else 1
        row_cap = ms_y or (ver if not column_major else 0)
        if count is None:
            if column_major:
                count = ver * max(1, int(w // sw) if w > 0 else 1)
            else:
                rows = row_cap or (max(1, int(h // sh)) if h > 0 else 1)
                count = cols * rows
        cap = (cols * row_cap) if (cols and row_cap) else None
        if cap is not None and count > cap:
            warn(f"--grid {name}: {count} entries, but the gridbox holds {cols}x{row_cap} (max_slots); drawing {cap}")
            count = cap
        fmt = str(node.get("format", "upper_left")).lower()
        from_right, from_bottom = fmt.endswith("right"), fmt.startswith("lower")
        gclip = clip            # a gridbox grows with its entries (event options: a 300x30 grid shows 47 px rows)
        for i in range(count):
            if column_major:
                r, c = i % ver, i // ver
            else:
                r, c = divmod(i, cols)
            # UPPER_RIGHT fills right to left from the box's right edge, LOWER_* bottom-up from its lower edge
            # (a 0-sized LOWER_LEFT box grows upwards from its position)
            sx = x + w - (c + 1) * sw if from_right else x + c * sw
            sy = y + h - (r + 1) * sh if from_bottom else y + r * sh
            self.render(tet, tnode, (sx, sy, sw, sh), gclip, depth + 1)


_small_font = None


def small_font():
    global _small_font
    if _small_font is None:
        try:
            _small_font = ImageFont.load_default(size=11)
        except TypeError:
            _small_font = ImageFont.load_default()
    return _small_font


def find_element(ctx, name, file_hint):
    """(node, type) of a named window/template in the effective interface, preferring --file and top level."""
    hits = ctx.gui["names"].get(name)
    if not hits:
        return None, None
    if file_hint:
        fh = norm_rel(file_hint).lower()
        sel = [h for h in hits if h[0] == fh or h[0].endswith("/" + fh) or Path(h[0]).name == Path(fh).name]
        if sel:
            hits = sel
        else:
            warn(f"{name} is not in {file_hint}; using {hits[0][1]}")
    hits = sorted(hits, key=lambda h: (h[5], h[2] != "mod", h[0]))     # top level first, then mod files
    if len(hits) > 1:
        others = ", ".join(f"{h[2]}:{h[1]} (depth {h[5]})" for h in hits[1:4])
        log(f"note: '{ascii_only(name)}' also defined in {ascii_only(others)}; using {hits[0][2]}:{hits[0][1]} "
            "(--file to choose)")
        top_files = {h[0] for h in hits if h[5] == 0}
        if len(top_files) > 1:
            warn(f"'{name}' is a top-level window in {len(top_files)} files; which one the game uses is not "
                 "certain - give the mod's copy the vanilla file's path so it replaces it")
    rel, real, origin, trail, et, depth = hits[0]
    path = ctx.gui["files"][rel][1]
    return node_at(gui_tree(path), trail), et


# ====================================================================================== backgrounds
def cover(img, w, h):
    s = max(w / img.width, h / img.height)
    nw, nh = int(round(img.width * s)), int(round(img.height * s))
    im = img.resize((nw, nh), Image.BICUBIC)
    l, t = (nw - w) // 2, (nh - h) // 2
    return im.crop((l, t, l + w, t + h))


def map_backdrop():
    cached = CACHE / "map_backdrop.jpg"
    if cached.exists():
        return Image.open(cached).convert("RGB")
    if MAP_SHOT.exists():
        shot = Image.open(MAP_SHOT).convert("RGB")
        # the in-game 3440x1440 screenshot without the HUD: below the topbar, left of the right-hand toolbar,
        # above the bottom buttons; the province tooltip is patched with the map just below it
        crop = shot.crop((0, 90, 3300, 1300))
        tip = (1740 - 0, 725 - 90, 2070 - 0, 950 - 90)
        patch = crop.crop((tip[0], tip[3] + 10, tip[2], tip[3] + 10 + (tip[3] - tip[1])))
        crop.paste(patch, (tip[0], tip[1]))
        ensure_cache_dir()
        crop.save(cached, quality=90)
        return crop
    warn("no map screenshot found; using a flat map-coloured backdrop")
    rng = np.random.default_rng(7)
    a = np.zeros((540, 960, 3), np.float32) + np.array([62, 58, 92], np.float32)
    a += rng.normal(0, 6, a.shape)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")


def make_background(ctx, w, h):
    spec = ctx.args.bg
    if spec in (None, "", "black"):
        return Image.new("RGBA", (w, h), (0, 0, 0, 255))
    if spec in ("none", "transparent"):
        return Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if spec == "map":
        return cover(map_backdrop(), w, h).convert("RGBA")
    if spec == "menu":
        canvas = Canvas(w, h, Image.new("RGBA", (w, h), (0, 0, 0, 255)))
        node, et = find_element(ctx, "frontend_background", None)
        if node is not None:
            r = Renderer(ctx, canvas)
            rows = len(ctx.rows)
            r.render(et, node, (0, 0, w, h), None, 0)
            del ctx.rows[rows:]
            del ctx.outlines[rows:]
            ctx.bounds = None
            return canvas.img
        img = load_texture("gfx/loadingscreens/totu_red_square.dds")
        return cover(img.convert("RGB"), w, h).convert("RGBA") if img else canvas.img
    p = Path(spec)
    if not p.is_absolute():
        p = ROOT / p if (ROOT / p).exists() else Path.cwd() / p
    if p.exists():
        return cover(Image.open(p).convert("RGB"), w, h).convert("RGBA")
    warn(f"--bg {spec}: not found, black")
    return Image.new("RGBA", (w, h), (0, 0, 0, 255))


# ====================================================================================== outline / compare
def draw_outlines(ctx, img):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    dr = ImageDraw.Draw(layer)
    f = small_font()
    for kind, name, (x, y, w, h) in ctx.outlines:
        col = OUTLINE_COLOURS.get(kind, OUTLINE_COLOURS["other"])
        if w > 0 and h > 0:
            dr.rectangle((x, y, x + w - 1, y + h - 1), outline=col + (230,))
        else:
            dr.line((x - 3, y, x + 3, y), fill=col + (230,))
            dr.line((x, y - 3, x, y + 3), fill=col + (230,))
        label = ascii_only(name)
        tb = dr.textbbox((0, 0), label, font=f)
        lw, lh = tb[2] - tb[0] + 4, tb[3] - tb[1] + 3
        lx, ly = max(0, x), max(0, y)
        dr.rectangle((lx, ly, lx + lw, ly + lh), fill=(0, 0, 0, 170))
        dr.text((lx + 2, ly + 1 - tb[1]), label, fill=col + (255,), font=f)
    img.alpha_composite(layer)
    return img


def write_compare(render_img, shot_path, out_path, box, zoom=1):
    """4 panels: screenshot | render / 50 % blend (ghosting = misplaced) | difference (red = render and screenshot
    disagree). With --bg none the render is drawn over the screenshot first."""
    shot = Image.open(shot_path).convert("RGBA")
    if shot.size != render_img.size:
        warn(f"--compare: screenshot is {shot.size[0]}x{shot.size[1]}, render {render_img.size[0]}x"
             f"{render_img.size[1]}; scaling the screenshot")
        shot = shot.resize(render_img.size, Image.BICUBIC)
    full = render_img
    shown = render_img
    if np.asarray(render_img.getchannel("A")).min() < 255:
        full = shot.copy()
        full.alpha_composite(render_img)
        shown = Image.new("RGBA", render_img.size, (24, 24, 24, 255))
        shown.alpha_composite(render_img)
    blend = Image.blend(shot, full, 0.5)
    diff = np.abs(np.asarray(full, np.int16)[..., :3] - np.asarray(shot, np.int16)[..., :3]).max(axis=2)
    base = np.asarray(shot.convert("L"), np.float32) * 0.35
    rgb = np.stack([base, base, base], axis=2)
    m = np.clip(diff * 3, 0, 255)
    rgb[..., 0] = np.maximum(rgb[..., 0], m)
    rgb[..., 1] = np.maximum(rgb[..., 1], m * 0.25)
    diff_im = Image.fromarray(rgb.astype(np.uint8), "RGB").convert("RGBA")
    panels = [shot, shown, blend, diff_im]
    if box:
        panels = [p.crop(box) for p in panels]
        diff = diff[box[1]:box[3], box[0]:box[2]]
    if zoom != 1:
        panels = [p.resize((p.width * zoom, p.height * zoom), Image.NEAREST) for p in panels]
    pw, ph = panels[0].size
    sheet = Image.new("RGBA", (pw * 2 + 8, ph * 2 + 8), (40, 40, 40, 255))
    for i, p in enumerate(panels):
        sheet.paste(p, ((i % 2) * (pw + 8), (i // 2) * (ph + 8)))
    dr = ImageDraw.Draw(sheet)
    for i, lab in enumerate(("screenshot", "render", "50% blend", "difference (red)")):
        dr.text(((i % 2) * (pw + 8) + 6, (i // 2) * (ph + 8) + 4), lab, fill=(255, 255, 0, 255), font=small_font())
    sheet.convert("RGB").save(out_path)
    log(f"wrote {shown_path(out_path)}")
    return float((diff > 40).mean())


# ====================================================================================== main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("window", help="window or template name(s), comma separated, drawn in order")
    ap.add_argument("--file")
    ap.add_argument("--res", default="1920x1080")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--lang", default="russian")
    ap.add_argument("--bg", default="black")
    ap.add_argument("--state", action="append")
    ap.add_argument("--shown", action="store_true")
    ap.add_argument("--hide", action="append")
    ap.add_argument("--text", action="append")
    ap.add_argument("--prop", action="append")
    ap.add_argument("--grid", action="append")
    ap.add_argument("--move", action="append")
    ap.add_argument("--no-relayout", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--outline", action="store_true")
    ap.add_argument("--crop", action="store_true")
    ap.add_argument("--no-placeholders", action="store_true")
    ap.add_argument("--no-scrollbars", action="store_true")
    ap.add_argument("--progress", type=float, default=0.5, help="fill of progress bars (0..1)")
    ap.add_argument("--compare")
    ap.add_argument("--compare-box")
    ap.add_argument("--compare-zoom", type=int, default=1)
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--list", action="store_true", help="list names containing <window> and exit")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(errors="backslashreplace")
    except Exception:
        pass

    m = re.fullmatch(r"(\d+)[xX](\d+)", args.res)
    if not m or int(m.group(1)) <= 0 or int(m.group(2)) <= 0:
        ap.error(f"--res {args.res}: expected WxH, e.g. 1920x1080")
    if args.scale <= 0:
        ap.error("--scale must be above 0")
    if not 0 <= args.progress <= 1:
        ap.error("--progress must be between 0 and 1")
    if args.compare_zoom < 1:
        ap.error("--compare-zoom must be 1 or more")
    sw, sh = int(m.group(1)), int(m.group(2))
    lw, lh = int(round(sw / args.scale)), int(round(sh / args.scale))
    box = None
    if args.compare_box:
        try:
            box = tuple(int(v) for v in args.compare_box.split(","))
        except ValueError:
            box = ()
        if len(box) != 4 or box[2] <= box[0] or box[3] <= box[1] or min(box) < 0:
            ap.error(f"--compare-box {args.compare_box}: expected x0,y0,x1,y1 with x1 > x0 and y1 > y0")
    if args.compare and not Path(args.compare).is_file():
        ap.error(f"--compare {ascii_only(args.compare)}: no such file")
    if args.compare_box and not args.compare:
        ap.error("--compare-box needs --compare <screenshot.png>")
    try:
        parse_specs(args)
    except SpecError as e:
        ap.error(ascii_only(e))
    ctx = Ctx(args)

    if args.list:
        q = args.window.lower()
        for nm in sorted(ctx.gui["names"]):
            if q in nm.lower():
                for h in ctx.gui["names"][nm]:
                    log(f"{ascii_only(nm):48} {short_type(h[4]):10} depth {h[5]}  {h[2]}:{ascii_only(h[1])}")
        return 0

    bg = make_background(ctx, lw, lh)
    canvas = Canvas(lw, lh, bg)
    for name in [n.strip() for n in args.window.split(",") if n.strip()]:
        node, et = find_element(ctx, name, args.file)
        if node is None:
            log(f"ERROR: no window or template named '{ascii_only(name)}' (try --list)")
            return 2
        if args.crop and not node.get("orientation"):
            prect = (32, 32, lw, lh)        # room for parts that stick out to the left/top of a template
        else:
            prect = (0, 0, lw, lh)
        Renderer(ctx, canvas).render(et, node, prect, None, 0)

    plain = canvas.img.copy()
    img = canvas.img
    if args.outline:
        img = draw_outlines(ctx, img)
    if args.crop and ctx.bounds:
        b = ctx.bounds
        box = (max(0, b[0] - 16), max(0, b[1] - 16), min(lw, b[2] + 16), min(lh, b[3] + 16))
        img = img.crop(box)
    if args.scale != 1.0:
        img = img.resize((int(round(img.width * args.scale)), int(round(img.height * args.scale))), Image.BILINEAR)
    out = Path(args.out) if args.out else PREVIEW / f"render_{re.sub(r'[^A-Za-z0-9_]+', '_', args.window)}.png"
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    (img.convert("RGB") if args.bg not in ("none", "transparent") else img).save(out)

    if not args.quiet:
        log(f"{'element':44} {'type':10} {'x':>6} {'y':>6} {'w':>5} {'h':>5}  notes")
        for depth, nm, t, x, y, w, h, note in ctx.rows:
            label = ("  " * depth + nm)[:44]
            log(f"{ascii_only(label):44} {t:10} {x:6} {y:6} {w:5} {h:5}  {ascii_only(note)}")
        if ctx.skipped:
            log(f"skipped: " + ", ".join(f"{ascii_only(n)} ({why})" for n, why in ctx.skipped[:40]) +
                (" ..." if len(ctx.skipped) > 40 else ""))
    if ctx.unknown:
        warn("unknown element types skipped: " + ", ".join(f"{k} x{v}" for k, v in sorted(ctx.unknown.items())))
    ctx.warn_unused()
    log(f"wrote {shown_path(out)} ({img.width}x{img.height})")
    if args.compare:
        cmp_out = out.with_name(out.stem + "_compare.png")
        frac = write_compare(plain, args.compare, cmp_out, box, args.compare_zoom)
        log(f"compare: {frac * 100:.2f}% of the compared pixels differ by more than 40 (of 255)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
