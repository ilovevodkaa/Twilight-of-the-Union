"""Preview of the country selection screen (gamesetup_interesting_countries_window) from the built textures.

Usage:
    python tools/preview_country.py [--game PATH]

Composes the screen at UI scale 1.0 the way interface/frontendgamesetupview.gui lays it out (window 1225x717,
centred; the window coordinates below are the .gui's), from:
  * the textures built by tools/build_menu_gfx.py (country_select_bg, the entry sprites, scrim_country, caption
    plates) and the caption fonts built by tools/build_fonts.py (gfx/fonts/totu_caption*.fnt + .dds);
  * the vanilla hoi_20b font (+ _cryllic) and the flags (mod first, then vanilla) from the game folder;
  * texts from the mod's localisation (Russian), countries and national spirits from common/bookmarks/totu_1990.txt;
    the leader / ideology / government / elections / party values are sample data of the kind the engine fills in;
  * the backdrop tools/src/preview/lobby_1990.jpg: the mod's own lobby, a 3440x1440 capture at UI scale 1.0 saved
    at 1600x670 (scaled back up here, so it is soft).
Writes tools/preview/screen_country.png (2560x1440: SOV selected, Select hovered), screen_country_minor.png (POL
selected, the window only) and screen_country_1080.png (1920x1080 with the lobby's bars and panels pasted back at
their anchors), and prints a layout report. Run tools/build_fonts.py and tools/build_menu_gfx.py first.
Requires Pillow and numpy.
"""
import argparse
import re
import sys
from pathlib import Path

from PIL import Image, ImageChops

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_menu_gfx as g  # noqa: E402

ROOT = g.ROOT
OUT = ROOT / "tools" / "preview"
LOBBY = ROOT / "tools" / "src" / "preview" / "lobby_1990.jpg"
SW, SH = 2560, 1440
P, D = g.CAPTION_WHITE, g.CAPTION_DIM

# ---------------------------------------------------------------- window layout (= frontendgamesetupview.gui)
WIN_W, WIN_H = g.CS_W, g.CS_H
TITLE_XY = (0, 0)                           # title caption on the scrim, K edge at +2,+2
MAJOR_X, MAJOR_Y = 392, 41                  # countries grid, slots of MAJOR_W
MINOR_X, MINOR_Y, MINOR_PITCH = 10, 333, 153   # countries_medium grid
MINOR_FLAG = (26, 22)
COLS = [(36, 354), (434, 356), (834, 355)]  # info | centre | history: x, width
TOP = 456                                   # first caption line of the lower block
PAIR_PITCH, VALUE_DY = 44, 14               # label pitch; value box 14 px under its label
NATION = (434, TOP, 356, 36)                # nation_title
SPIRIT = (434 + 4, 500)                     # ideas grid (spirit container + ideas offset)
IDEA_SLOT = 68                              # slot width; spirit_idea_entry (60 wide) centres the icon at slot + 30
BTN_X = 412
BUTTONS = [("TOTU_FE_SELECT", "select", 586, 208), ("TOTU_FE_BACK", "back", 650, 160)]
LABEL_DX, LABEL_DY = g.PAD_L, 6
HISTORY_TITLE = (834, TOP, 355)
HISTORY = (834, 478, 355)
SCRIM_SCALE, SCRIM_CENTRE = 4, (612, 358)
LABEL_KEYS = ["TOTU_FE_LEADER", "TOTU_FE_IDEOLOGY", "TOTU_FE_GOVERNMENT", "TOTU_FE_ELECTIONS", "TOTU_FE_RULING_PARTY"]
# what the engine fills in (sample data): SOV as the lobby shows it; POL has no character, so its leader is generated
VALUES = {"SOV": ["Михаил Горбачёв", "Коммунизм", "Тоталитарный режим", "Никогда",
                  "Всесоюзная коммунистическая партия"],
          "POL": ["Ежи Ковальский", "Демократия", "Демократическое государство", "1 января 1992",
                  "Польская крестьянская партия"]}


# ---------------------------------------------------------------- fonts (BMFont text files, as the engine reads them)
class Font:
    """One bitmapfont: the .fnt/.dds pairs of its fontfiles merged (later files only add glyphs)."""

    def __init__(self, paths):
        self.chars = {}
        for i, p in enumerate(paths):
            atlas = Image.open(p.with_suffix(".dds")).convert("RGBA")
            for line in p.read_text(encoding="latin-1").splitlines():
                tag, _, rest = line.partition(" ")
                kv = dict(f.split("=", 1) for f in rest.split() if "=" in f)
                if tag == "common" and i == 0:
                    self.line_h, self.base = int(kv["lineHeight"]), int(kv["base"])
                elif tag == "char":
                    c = {k: int(v) for k, v in kv.items() if v.lstrip("-").isdigit()}
                    self.chars.setdefault(c["id"], (c, atlas))

    def adv(self, ch):
        return (self.chars.get(ord(ch)) or self.chars[ord("?")])[0]["xadvance"]

    def width(self, text):
        return sum(self.adv(ch) for ch in text)

    def draw_line(self, img, text, x, y, colour):
        for ch in text:
            c, atlas = self.chars.get(ord(ch)) or self.chars[ord("?")]
            if c["width"] and c["height"]:
                tile = atlas.crop((c["x"], c["y"], c["x"] + c["width"], c["y"] + c["height"]))
                tile = ImageChops.multiply(tile, Image.new("RGBA", tile.size, colour + (255,)))
                img.alpha_composite(tile, (int(x + c["xoffset"]), int(y + c["yoffset"])))
            x += c["xadvance"]

    def wrap(self, text, max_w):
        lines = []
        for para in text.split("\n"):
            cur = ""
            for word in para.split(" "):
                t = word if not cur else cur + " " + word
                if cur and self.width(t) > max_w:
                    lines.append(cur)
                    cur = word
                else:
                    cur = t
            lines.append(cur)
        return lines

    def box(self, img, text, x, y, max_w, max_h=None, fmt="left", colour=(255, 255, 255), edge=False):
        """instantTextBox, top-aligned: top-left at x,y; wraps at max_w; format left / center; a fixed max_h cuts
        whole lines. edge: the K copy (black) at +2,+2 underneath, as the menu's captions have it."""
        lines = self.wrap(text, max_w)
        if max_h is not None:
            lines = lines[: max(1, max_h // self.line_h)]
        for i, ln in enumerate(lines):
            lx = x if fmt == "left" else x + (max_w - self.width(ln)) // 2
            if edge:
                self.draw_line(img, ln, lx + g.CAPTION_SHADOW, y + i * self.line_h + g.CAPTION_SHADOW, (0, 0, 0))
            self.draw_line(img, ln, lx, y + i * self.line_h, colour)
        return lines


# ---------------------------------------------------------------- data
def loc(key, name="totu_menu_l_russian.yml"):
    return g.loc_value("russian", key, name).replace("\\n", "\n")


def country_name(tag, ideology):
    return loc(f"{tag}_{ideology}", "replace/totu_countries_l_russian.yml")


def bookmark():
    """[(TAG, ideology, minor, ideas)] of the first bookmark in common/bookmarks/totu_1990.txt (read only)."""
    text = (ROOT / "common" / "bookmarks" / "totu_1990.txt").read_text(encoding="utf-8")
    first = text.split("# Hidden clone")[0]
    out = []
    for m in re.finditer(r'"([A-Z0-9]{3})"\s*=\s*\{(.*?)\n\t\t\}', first, re.S):
        body = m.group(2)
        ideas = re.search(r"ideas\s*=\s*\{([^}]*)\}", body)
        out.append((m.group(1), re.search(r"ideology\s*=\s*(\w+)", body).group(1), "minor = yes" in body,
                    ideas.group(1).split() if ideas else []))
    return out


def flag(game, name):
    for root in (ROOT, game):
        p = root / "gfx" / "flags" / f"{name}.tga"
        if p.exists():
            return Image.open(p).convert("RGBA")
    raise FileNotFoundError(name)


def idea_icon(idea):
    """TOTU_SOV_glasnost -> gfx/interface/ideas/totu/totu_glasnost.dds (tools/gen_icons.py naming)."""
    p = ROOT / "gfx" / "interface" / "ideas" / "totu" / f"totu_{idea.split('_', 2)[2]}.dds"
    return Image.open(p).convert("RGBA") if p.exists() else None


# ---------------------------------------------------------------- backdrops
def capture_3440():
    """The lobby capture at its real size (3440x1440, UI scale 1.0)."""
    return Image.open(LOBBY).convert("RGB").resize((3440, 1440), Image.LANCZOS)


def map_backdrop(sw=SW, sh=SH):
    """Hero backdrop: the capture's map rows only (45..623 of 670), centred crop, scaled to the screen."""
    src = Image.open(LOBBY).convert("RGB")
    top, bottom = 45, 624
    h = bottom - top
    w = round(h * sw / sh)
    left = (src.width - w) // 2
    return src.crop((left, top, left + w, bottom)).resize((sw, sh), Image.LANCZOS)


def lobby_context(sw, sh):
    """The lobby around the window as in game at UI scale 1.0: the map (centre crop of the capture), the top bar,
    the bottom bar, gamesetup_country_details (upper right) and the gameplay settings (lower right). sw <= 3440,
    sh <= 1440."""
    cap = capture_3440()
    if (sw, sh) == (3440, 1440):
        return cap
    ox, oy = (3440 - sw) // 2, (1440 - sh) // 2
    shot = cap.crop((ox, oy, ox + sw, oy + sh))
    half = sw // 2
    for y0, y1, dy in ((0, 98, 0), (1342, 1440, sh - 1440)):
        shot.paste(cap.crop((0, y0, half, y1)), (0, y0 + dy))
        shot.paste(cap.crop((3440 - half, y0, 3440, y1)), (half, y0 + dy))
    shot.paste(cap.crop((1720 - 200, 0, 1720 + 200, 98)), (half - 200, 0))
    shot.paste(cap.crop((2900, 90, 3440, 400)), (sw - 540, 90))
    shot.paste(cap.crop((2830, 1150, 3440, 1342)), (sw - 610, sh - 290))
    return shot


# ---------------------------------------------------------------- composition
class Assets:
    def __init__(self, game):
        tex = lambda name: Image.open(ROOT / "gfx/interface/totu" / name).convert("RGBA")     # noqa: E731
        self.game = game
        self.board = tex("country_select_bg.dds")
        self.major = tex("country_entry_major.dds")
        self.minor = tex("country_entry_minor.dds")
        sc = tex("scrim_country.dds")
        self.scrim = sc.resize((sc.width * SCRIM_SCALE, sc.height * SCRIM_SCALE), Image.BILINEAR)
        self.plates = {w: tex(f"caption_{w}.dds") for *_, w in BUTTONS}
        self.cap = Font([ROOT / "gfx/fonts/totu_caption.fnt"])
        self.cap_s = Font([ROOT / "gfx/fonts/totu_caption_small.fnt"])
        self.body = Font([game / "gfx/fonts/hoi_20b.fnt", game / "gfx/fonts/hoi_20b_cryllic.fnt"])
        self.countries = bookmark()


def compose(A, sel="SOV", hover="select", backdrop=None):
    """sel: selected country tag; hover: None, "select" or "back". Returns (shot, window origin)."""
    shot = (backdrop if backdrop is not None else map_backdrop()).convert("RGBA")
    sw, sh = shot.size
    wx, wy = (sw - WIN_W) // 2, (sh - WIN_H) // 2
    win = Image.new("RGBA", (WIN_W, WIN_H), (0, 0, 0, 0))
    shot.alpha_composite(A.scrim, (wx + SCRIM_CENTRE[0] - A.scrim.width // 2, wy + SCRIM_CENTRE[1] - A.scrim.height // 2))
    win.alpha_composite(A.board)
    A.cap.box(win, loc("TOTU_FE_SELECT_COUNTRY"), *TITLE_XY, 700, colour=P, edge=True)
    for key, name, y, w in BUTTONS:
        frame = 1 if hover == name else 0
        win.alpha_composite(A.plates[w].crop((frame * w, 0, (frame + 1) * w, g.PLATE_H)), (BTN_X, y))
        A.cap.box(win, loc(key), BTN_X + LABEL_DX, y + LABEL_DY, w - LABEL_DX, colour=P, edge=True)

    majors = [c for c in A.countries if not c[2]]
    minors = [c for c in A.countries if c[2]]
    for i, (tag, ideology, _, _) in enumerate(majors):
        cx = MAJOR_X + i * g.MAJOR_W
        win.alpha_composite(flag(A.game, f"{tag}_{ideology}"), (cx + g.MAJOR_FLAG_POS[0], MAJOR_Y + g.MAJOR_FLAG_POS[1]))
        fr = 1 if tag == sel else 0
        win.alpha_composite(A.major.crop((fr * g.MAJOR_W, 0, (fr + 1) * g.MAJOR_W, g.MAJOR_H)), (cx, MAJOR_Y))
        x, y, mw, mh = g.MAJOR_NAME
        A.cap_s.box(win, country_name(tag, ideology), cx + x, MAJOR_Y + y, mw, mh, fmt="center", colour=D)
    for i, (tag, ideology, _, _) in enumerate(minors):
        ex = MINOR_X + i * MINOR_PITCH
        win.alpha_composite(flag(A.game, f"{tag}_{ideology}"), (ex + MINOR_FLAG[0], MINOR_Y + MINOR_FLAG[1]))
        fr = 1 if tag == sel else 0
        win.alpha_composite(A.minor.crop((fr * g.MINOR_W, 0, (fr + 1) * g.MINOR_W, g.MINOR_H)), (ex, MINOR_Y))

    tag, ideology, _, ideas = next(c for c in A.countries if c[0] == sel)
    tx, tw = COLS[0]
    for k, (lab, val) in enumerate(zip(LABEL_KEYS, VALUES.get(sel, VALUES["POL"]))):
        y = TOP + k * PAIR_PITCH
        A.cap_s.box(win, loc(lab), tx, y, tw, colour=D)
        A.body.box(win, val, tx, y + VALUE_DY, tw, max_h=40 if k == 4 else 20)
    nx, ny, nw, nh = NATION
    A.cap_s.box(win, country_name(tag, ideology), nx, ny, nw, nh, colour=P)
    for k, idea in enumerate(ideas):
        icon = idea_icon(idea)
        if icon:
            cx, cy = SPIRIT[0] + k * IDEA_SLOT + 30, SPIRIT[1] + IDEA_SLOT // 2
            win.alpha_composite(icon, (cx - icon.width // 2, cy - icon.height // 2))
    hx, hy, hw = HISTORY_TITLE
    A.cap_s.box(win, loc("TOTU_FE_HISTORY_TITLE"), hx, hy, hw, colour=P)
    A.body.box(win, loc(f"TOTU_{sel}_1990_DESC"), *HISTORY[:2], HISTORY[2])
    shot.alpha_composite(win, (wx, wy))
    return shot, (wx, wy)


def layout_report(A):
    """The numbers the .gui relies on: value widths, column bottoms, card name wraps."""
    rows = []
    for tag, values in VALUES.items():
        for k, val in enumerate(values):
            n = len(A.body.wrap(val, COLS[0][1]))
            rows.append(f"{tag} value {k}: {A.body.width(val)} px, {n} line(s)")
        hist = A.body.wrap(loc(f"TOTU_{tag}_1990_DESC"), HISTORY[2])
        rows.append(f"{tag} history: {len(hist)} lines, ends at y {HISTORY[1] + len(hist) * A.body.line_h}")
    for tag, ideology, minor, _ in A.countries:
        if not minor:
            name = country_name(tag, ideology)
            rows.append(f"{tag} card name: {len(A.cap_s.wrap(name, g.MAJOR_NAME[2]))} line(s), widest "
                        f"{max(A.cap_s.width(l) for l in A.cap_s.wrap(name, g.MAJOR_NAME[2]))} of {g.MAJOR_NAME[2]}")
    rows.append(f"party value bottom: {TOP + 4 * PAIR_PITCH + VALUE_DY + 40}, back plate bottom: {650 + g.PLATE_H}, "
                f"board bottom: {g.CS_BOARD[3]}")
    rows.append(f"minor flags span {MINOR_X + MINOR_FLAG[0]}..{MINOR_X + 7 * MINOR_PITCH + MINOR_FLAG[0] + 82}")
    return "\n".join(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=str(g.GAME), help="Hearts of Iron IV folder (vanilla fonts and flags)")
    args = ap.parse_args()
    A = Assets(Path(args.game))
    OUT.mkdir(parents=True, exist_ok=True)
    shot, _ = compose(A, "SOV", "select")
    shot.convert("RGB").save(OUT / "screen_country.png")
    shot, (wx, wy) = compose(A, "POL", None)
    shot.crop((wx - 40, wy - 30, wx + WIN_W + 40, wy + WIN_H + 30)).convert("RGB").save(OUT / "screen_country_minor.png")
    shot, _ = compose(A, "SOV", None, lobby_context(1920, 1080))
    shot.convert("RGB").save(OUT / "screen_country_1080.png")
    for name in ("screen_country.png", "screen_country_minor.png", "screen_country_1080.png"):
        print("wrote", f"tools/preview/{name}")
    sys.stdout.reconfigure(encoding="utf-8")
    print(layout_report(A))


if __name__ == "__main__":
    main()
