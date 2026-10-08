"""Area 'topbar': the topbar strip, toolbar view buttons, right cluster (date, speed, overview buttons, world
tension dial), alerts, minimap, in-game clock, music player buttons, in the broadcast style.

Flat boards in the vanilla silhouettes (no inset, rivets, bevels, laurels or metal), pixel pictograms at 2 px cells
in P with the K drop (derived from the vanilla icon silhouettes where that reads better than a hand grid), keyer
blue for open / selected / paused. Content (alert icons, resource icons) keeps its colours. Texture-only: every
output keeps the vanilla pixel size, frame layout and (for transparencecheck sprites) the alpha silhouette.
"""
import numpy as np
from PIL import Image

import totu_broadcast as tb
from ingame import generic as g
from ingame import _topbar_picto as tp

AREA = "topbar"

P, D, K = g.P, g.D, g.K
BOARD, BA = g.BOARD, g.BOARD_ALPHA
KEY, KEY_DOWN, SLATE = g.KEY_BLUE, g.KEY_BLUE_DOWN, g.SLATE
RED, GREEN = g.SEM_R, g.SEM_G
AMBER = (204, 152, 24)          # amber badge / bar: SEM_Y darkened so white engine digits stay legible on it
A = round(255 * BA)


def _rgba(rgb, alpha=1.0):
    return tuple(rgb) + (round(255 * alpha),)


def _silhouette(src, thr=128, alpha=BA, rgb=BOARD):
    """Flat board in the vanilla alpha silhouette (binarised, so no soft shadows and no inner art)."""
    a = np.asarray(src.convert("RGBA"))[..., 3]
    out = np.zeros(a.shape + (4,), np.uint8)
    out[..., :3] = rgb
    out[..., 3] = np.where(a >= thr, round(255 * alpha), 0)
    return Image.fromarray(out, "RGBA")


def _picto(rows, size, cell=2, rgb=P, dx=0, dy=0, drop=True, alpha=1.0):
    return tp.centred_cells(tp.grid_from_rows(rows), size, cell, dx=dx, dy=dy, rgb=rgb, drop=drop, alpha=alpha)


# ---------------------------------------------------------------------------------------------------------------
# Topbar strip and right cluster

def topbar_background(ctx, src):
    return _silhouette(src)


def cluster_plate(ctx, src):
    """armyoverview_buttons_bg 403x101: band y 3..44 under the date (45 deg left edge) plus the block under the
    overview buttons, world tension dial and side buttons (45 deg left edge, bottom y 97). Flat board."""
    w, h = ctx.w, ctx.h
    a = np.zeros((h, w), bool)
    for y in range(3, 45):
        a[y, max(0, 6 + (y - 3)):400] = True
    for y in range(44, 97):
        a[y, max(0, 80 + (y - 44)):400] = True
    out = np.zeros((h, w, 4), np.uint8)
    out[..., :3] = BOARD
    out[..., 3] = np.where(a, A, 0)
    return Image.fromarray(out, "RGBA")


SCIENCE = ["..#####............",
           "...#.#.............",
           "...#.#...........##",
           "...#.#...........##",
           "..#...#.......##.##",
           "..#...#.......##.##",
           ".#.....#...##.##.##",
           ".#######...##.##.##",
           "#########..##.##.##",
           "#########..##.##.##",
           ".#######...##.##.##"]
TRADE = ["..............##....",
         "..............####..",
         "####################",
         "####################",
         "..............####..",
         "..............##....",
         "....................",
         "....##..............",
         "..####..............",
         "####################",
         "####################",
         "..####..............",
         "....##.............."]
LEDGER = ["############",
          "#..........#",
          "#.########.#",
          "#..........#",
          "#.########.#",
          "#..........#",
          "#.########.#",
          "#..........#",
          "#.#####....#",
          "#..........#",
          "############"]
CAP = ["....#####....", "..#########..", ".###########.", "#############", "#############",
       ".###########.", ".............", "..#########..", "...#######..."]
KING = ["...#...", "..###..", "...#...", ".#####.", "..###..", "..###..", "..###..", ".#####.", "#######",
        "#######"]


def _hcat(a, b, gap=2):
    """Two row grids side by side, bottom-aligned."""
    h = max(len(a), len(b))
    wa, wb = max(map(len, a)), max(map(len, b))
    a = ["." * wa] * (h - len(a)) + [r.ljust(wa, ".") for r in a]
    b = ["." * wb] * (h - len(b)) + [r.ljust(wb, ".") for r in b]
    return [ra + "." * gap + rb for ra, rb in zip(a, b)]


STAFF = _hcat(CAP, KING)
TOOLBAR_GRIDS = {"science_button": SCIENCE, "trade_button": TRADE, "ledger_button": LEDGER,
                 "staff_office_button": STAFF}


def toolbar_button(ctx, src):
    """110x41, 2 frames of 55x41: transparent + P pictogram / keyer plate + P pictogram. The pictogram is the
    vanilla frame-2 gold icon silhouette at 2 px cells (plate rim cropped), or a hand grid where that reads
    badly (science, trade, logistics, staff office)."""
    f1, f2 = ctx.split(src)
    fw = ctx.frame_w
    name = ctx.path.rsplit("/", 1)[-1].rsplit(".", 1)[0].lower()
    if name in TOOLBAR_GRIDS:
        pic = _picto(TOOLBAR_GRIDS[name], (fw, ctx.h))
    else:
        pic, grid = tp.derived_picto(f2, (fw, ctx.h), "gold", lum_min=0.40, warm_min=0.08, fill=0.5,
                                     crop=(3, 3, fw - 3, ctx.h - 3))
        if grid.sum() < 12:
            ctx.warn("pictogram nearly empty")
    a = ctx.blank(fw, ctx.h)
    a.alpha_composite(pic)
    b = g.flat(fw, ctx.h, KEY, 1.0)
    b.alpha_composite(pic)
    return ctx.join([a, b])


def glow_bar(rgb):
    def fn(ctx, src):
        parts = []
        for i in range(ctx.frames):
            f = ctx.blank(ctx.frame_w, ctx.h)
            if i % 2 == 1:
                f.paste(_rgba(rgb), (0, ctx.h - 4, ctx.frame_w, ctx.h))
            parts.append(f)
        return ctx.join(parts)
    return fn


def alert_badges(ctx, src):
    cols = [KEY, RED, AMBER, GREEN]
    return ctx.join([g.flat(ctx.frame_w, ctx.h, cols[i % 4], 1.0) for i in range(ctx.frames)])


SOLDIER = ["...###...", "...###...", "....#....", ".#######.", "#..###..#", "#..###..#", "...###...",
           "...#.#...", "...#.#...", "..##.##.."]
ANCHOR = ["....###....", "....#.#....", "....###....", ".....#.....", "..#######..", ".....#.....",
          ".....#.....", "#....#....#", "##...#...##", ".#...#...#.", "..##.#.##..", "....###...."]
PLANE = ["......#......", ".....###.....", ".....###.....", ".###########.", "#############",
         ".....###.....", ".....###.....", "......#......", "....#####....", "...#######..."]
OVERVIEW_GRIDS = {"armyoverview_button": SOLDIER, "navyoverview_button": ANCHOR, "airoverview_button": PLANE}


def overview_button(ctx, src):
    """76x38, 2 frames of 38x38 (army / navy / air): transparent / keyer square, each with a P pictogram
    (soldier, anchor, plane)."""
    fw = ctx.frame_w
    name = ctx.path.rsplit("/", 1)[-1].rsplit(".", 1)[0].lower()
    pic = _picto(OVERVIEW_GRIDS[name], (fw, ctx.h))
    a = ctx.blank(fw, ctx.h)
    a.alpha_composite(pic)
    b = g.flat(fw, ctx.h, KEY, 1.0)
    b.alpha_composite(pic)
    return ctx.join([a, b])


GLOBE = ["...###...", ".##.#.##.", "#...#...#", "#...#...#", "#########", "#...#...#", "#...#...#",
         ".##.#.##.", "...###..."]


def world_tension_dial(ctx, src):
    """490x49, 10 frames of 49x49: test-card dial, a ring of 10 radial ticks with round(k * 10 / 9) lit clockwise
    from 12 o'clock (0 at frame 1, all 10 at frame 10); lit P, lit red from frame 7 on; unlit D at 40 %.
    Centre: a pixel globe in D. 2 px cells."""
    nfr = 10                      # outside the manifest: ctx.frames is 1
    fw = ctx.w // nfr
    ticks = tp.tick_ring((fw, ctx.h), (24, 24), 12.5, 22.5, 2.5, 10)
    globe = tp.grid_from_rows(GLOBE)
    parts = []
    for k in range(nfr):
        lit = round(k * 10 / (nfr - 1))
        f = ctx.blank(fw, ctx.h)
        for i, t in enumerate(ticks):
            if i < lit:
                f.alpha_composite(tp.render_cells(t, (fw, ctx.h), (0, 0), 2, rgb=RED if k >= 6 else P))
            else:
                f.alpha_composite(tp.render_cells(t, (fw, ctx.h), (0, 0), 2, rgb=D, alpha=0.40, drop=False))
        f.alpha_composite(tp.render_cells(globe, (fw, ctx.h), (15, 15), 2, rgb=D))
        parts.append(f)
    return ctx.join(parts)


def transparent(ctx, src):
    return ctx.blank()


PLAY_S = ["#..", "##.", "###", "##.", "#.."]
PAUSE_S = ["#.#", "#.#", "#.#", "#.#", "#.#"]


def date_pill(ctx, src):
    """206x28: flat board with a small P play triangle at x 30 (right of the speed-down button)."""
    img = ctx.flat(BOARD, BA)
    img.alpha_composite(tp.render_cells(tp.grid_from_rows(PLAY_S), (ctx.w, ctx.h), (31, 9), 2))
    return img


def date_paused(ctx, src):
    """412x28, 2 frames (blendframes): keyer / pressed keyer with a P 'II' where the play triangle sits."""
    parts = []
    for rgb in (KEY, KEY_DOWN):
        f = g.flat(ctx.frame_w, ctx.h, rgb, 1.0)
        f.alpha_composite(tp.render_cells(tp.grid_from_rows(PAUSE_S), (ctx.frame_w, ctx.h), (31, 9), 2))
        parts.append(f)
    return ctx.join(parts)


def speed_steps(ctx, src):
    """84x10, 3 frames of 28x10: a 24x4 bar, D at 30 % / P / keyer."""
    parts = []
    for rgb, al in ((D, 0.30), (P, 1.0), (KEY, 1.0)):
        f = ctx.blank(ctx.frame_w, ctx.h)
        f.paste(_rgba(rgb, al), (2, 3, ctx.frame_w - 2, 7))
        parts.append(f)
    return ctx.join(parts)


def picto_button(name, bg=None, cell=2):
    def fn(ctx, src):
        parts = [tb.button_frame(ctx.frame_w, ctx.h, name, bg=bg, cell=cell) for _ in range(ctx.frames)]
        return ctx.join(parts)
    return fn


def rows_button(frames_rows, bg=None, cell=2, keyer_last=False):
    """One P pictogram per frame (rows lists); bg None = transparent; keyer_last: the last frame on keyer."""
    def fn(ctx, src):
        parts = []
        for i in range(ctx.frames):
            rows = frames_rows[min(i, len(frames_rows) - 1)]
            back = KEY if (keyer_last and i == ctx.frames - 1 and ctx.frames > 1) else bg
            f = ctx.blank(ctx.frame_w, ctx.h) if back is None else g.flat(ctx.frame_w, ctx.h, back, 1.0)
            f.alpha_composite(_picto(rows, (ctx.frame_w, ctx.h), cell))
            parts.append(f)
        return ctx.join(parts)
    return fn


def faction_empty(ctx, src):
    return ctx.flat(SLATE, 1.0)


def keyer_plate(ctx, src):
    return g.plate(ctx.w, ctx.h, KEY, 1.0)


def flat_board(ctx, src):
    return ctx.flat(BOARD, BA)


# ---------------------------------------------------------------------------------------------------------------
# Music player

PLAY = tb.PICTO["play"]
PAUSE = tb.PICTO["pause"]
NEXT = ["#...#", "##..#", "###.#", "#####", "###.#", "##..#", "#...#"]
PREV = [r[::-1] for r in NEXT]
NOTE = ["...##.", "...###", "...#.#", "...#..", ".###..", "####..", ".##..."]
LIST_PLUS = ["#####..", ".......", "#####..", ".......", "###..#.", "....###", ".....#."]

# ---------------------------------------------------------------------------------------------------------------
# Minimap

def _land_mask(src):
    """Soft land mask of the vanilla sepia minimap (land lighter than the sea)."""
    a = np.asarray(src.convert("RGB"), np.float32) / 255.0
    lum = g.gauss(0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2], 0.7)
    t = (np.percentile(lum, 15) + np.percentile(lum, 85)) / 2
    return g.smoothstep(t - 0.04, t + 0.04, lum)


def minimap_world(ctx, src):
    """World map: land P at 70 % on the board sea (TV weather map). The land mask always comes from
    gfx/minimap/minimap.dds (the legacy interface/minimap.dds 268x98 has the same projection but a vignette)."""
    land = _land_mask(src if ctx is None or ctx.path.lower().startswith("gfx/minimap")
                      else ctx.vanilla("gfx/minimap/minimap.dds"))
    h, w = src.height, src.width
    if land.shape != (h, w):
        pad = np.zeros((h, w), np.float32)
        hh, ww = min(h, land.shape[0]), min(w, land.shape[1])
        pad[:hh, :ww] = land[:hh, :ww]
        land = pad
    k = (0.70 * land)[..., None]
    rgb = np.array(BOARD, np.float32) * (1 - k) + np.array(P, np.float32) * k
    out = np.zeros((h, w, 4), np.uint8)
    out[..., :3] = np.clip(np.round(rgb), 0, 255).astype(np.uint8)
    out[..., 3] = round(255 * 0.94)
    return Image.fromarray(out, "RGBA")


def recolour(rgb):
    """Vanilla alpha shape in one flat colour (ping circle, camera quad)."""
    def fn(ctx, src):
        a = np.asarray(src.convert("RGBA"))[..., 3]
        out = np.zeros(a.shape + (4,), np.uint8)
        out[..., :3] = rgb
        out[..., 3] = a
        return Image.fromarray(out, "RGBA")
    return fn


def solid(rgb, alpha=1.0):
    def fn(ctx, src):
        return ctx.flat(rgb, alpha)
    return fn


def minimap_handle(rgb):
    """24x64 handle tab: flat plate in the vanilla silhouette with a P grip (3 short bars)."""
    def fn(ctx, src):
        img = _silhouette(src, rgb=rgb, alpha=1.0 if rgb != BOARD else BA)
        grip = ["######", "......", "######", "......", "######"]
        img.alpha_composite(_picto(grip, (ctx.w, ctx.h), dy=4))
        return img
    return fn


SWORDS = ["#.......#", ".#.....#.", "..#...#..", "...#.#...", "....#....", "...#.#...", ".###.###.",
          "..#...#..", ".#.....#."]
SHIELD = ["#######", "#######", "#######", "#######", ".#####.", "..###..", "...#..."]


def ping_button(rows):
    def fn(ctx, src):
        parts = []
        for i in range(ctx.frames):
            f = g.flat(ctx.frame_w, ctx.h, KEY if i == ctx.frames - 1 and ctx.frames > 1 else BOARD,
                       1.0 if i == ctx.frames - 1 and ctx.frames > 1 else BA)
            f.alpha_composite(_picto(rows, (ctx.frame_w, ctx.h)))
            parts.append(f)
        return ctx.join(parts)
    return fn


# ---------------------------------------------------------------------------------------------------------------
# Alerts

def alert_icons(ctx, src):
    """3290x42, 70 frames of 47x42: flat board square 43x38 per frame with the vanilla background-free icon on
    top in its own colours."""
    icons = ctx.vanilla("alerts/global_alert_icons_no_backgrounds.dds")
    if icons.size != src.size:
        ctx.warn("no_backgrounds strip size differs; generic kept")
        return ctx.generic(src)
    parts = []
    fw = 47
    for ic in g.split_frames(icons, ctx.w // fw):
        f = ctx.blank(fw, ctx.h)
        f.paste(_rgba(BOARD, BA), (0, 0, 43, 38))
        f.alpha_composite(ic)
        parts.append(f)
    return ctx.join(parts)


def alert_glow(rgb):
    """94x42, 2 frames of 47x42 (blendframes): transparent / a 4 px bar at the bottom of the 43x38 tile."""
    def fn(ctx, src):
        fw = ctx.w // 2               # green_alert_glow is outside the manifest (ctx.frames 1)
        a = ctx.blank(fw, ctx.h)
        b = ctx.blank(fw, ctx.h)
        b.paste(_rgba(rgb), (0, 34, 43, 38))
        return ctx.join([a, b])
    return fn


# ---------------------------------------------------------------------------------------------------------------

TOOLBAR = ["topbar_decisionview_button", "intelligence_button", "science_button", "diplomacy_button",
           "trade_button", "international_market_button", "construction_button", "production_button",
           "deployment_button", "ledger_button", "staff_office_button"]

TEXTURES = {
    "topbar/background_extended.dds": topbar_background,
    "topbar/background.dds": topbar_background,
    "topbar/armyoverview_buttons_bg.dds": cluster_plate,
    **{f"topbar/toolbar/{n}.dds": toolbar_button for n in TOOLBAR},
    "decisionview/decisions_glow.dds": glow_bar(KEY),
    "decisionview/decisions_glow_yellow.dds": glow_bar(AMBER),
    "topbar/toolbar/topbar_alert_bg.dds": alert_badges,
    "topbar/armyoverview_button.dds": overview_button,
    "topbar/navyoverview_button.dds": overview_button,
    "topbar/airoverview_button.dds": overview_button,
    "world_tension_icon_big_strip.dds": world_tension_dial,
    "wt_anim_strip.dds": transparent,
    "date_pause_button_bg.dds": date_pill,
    "date_pause_button.dds": date_paused,
    "topbar/speed_step.dds": speed_steps,
    "topbar/zoom_in.dds": picto_button("plus", bg=SLATE),
    "topbar/zoom_out.dds": picto_button("minus", bg=SLATE),
    "topbar/button_menu.dds": picto_button("menu"),
    "topbar/button_help.dds": picto_button("question"),
    "topbar/show_dismissed_alerts_icon.dds": picto_button("exclamation"),
    "topbar/achievements_button.dds": picto_button("star"),
    "factions/ui/topbar_faction_empty.dds": faction_empty,
    "reopen_lobby.dds": keyer_plate,
    "ingameclock_bg.dds": flat_board,
    # music player
    "topbar/musicplayer/playlist_bg.dds": topbar_background,
    "topbar/musicplayer/music_pause_button.dds": rows_button([PLAY, PAUSE]),
    "topbar/musicplayer/music_next_button.dds": rows_button([NEXT]),
    "topbar/musicplayer/musicplayer_button.dds": rows_button([NOTE]),
    "topbar/musicplayer/playlist_button.dds": rows_button([LIST_PLUS]),
    "topbar/musicplayer/musicplayer_next_button.dds": rows_button([NEXT]),
    "topbar/musicplayer/musicplayer_previous_button.dds": rows_button([PREV]),
    "topbar/musicplayer/musicplayer_play_pause_button.dds": rows_button([PLAY, PAUSE]),
    # minimap
    "gfx/minimap/minimap.dds": minimap_world,
    "minimap.dds": minimap_world,
    "gfx/minimap/border.dds": transparent,
    "gfx/minimap/minimap_quad_pixel.dds": solid(P),
    "gfx/minimap/ping_circle.dds": recolour(KEY),
    "gfx/minimap/handle_default.dds": minimap_handle(BOARD),
    "gfx/minimap/handle_pinged.dds": minimap_handle(KEY),
    "gfx/minimap/offensive_ping_btn.dds": ping_button(SWORDS),
    "gfx/minimap/defensive_ping_btn.dds": ping_button(SHIELD),
    # alerts
    "alerts/global_alert_icons.dds": alert_icons,
    "red_alert_glow.dds": alert_glow(RED),
    "yellow_alert_glow.dds": alert_glow(AMBER),
    "green_alert_glow.dds": alert_glow(GREEN),
}

LOSSLESS = set(TEXTURES)


# ---------------------------------------------------------------------------------------------------------------
# Second pass (2026-10-07): the user found the 2 px pixel pictograms blobby. Every icon below is a hand-drawn line
# icon from tools/ingame/_lineicons.py (one stroke weight, 8x supersampled), on flat transparent / slate / keyer
# backgrounds. These entries override the first pass where both name the same texture.
# ---------------------------------------------------------------------------------------------------------------
from ingame import _lineicons as LI  # noqa: E402

_TOOLBAR_ICON = {
    "topbar/toolbar/topbar_decisionview_button.dds": "gavel",
    "topbar/toolbar/intelligence_button.dds": "eye",
    "topbar/toolbar/science_button.dds": "flask",
    "topbar/toolbar/diplomacy_button.dds": "treaty",
    "topbar/toolbar/trade_button.dds": "exchange",
    "topbar/toolbar/international_market_button.dds": "scales",
    "topbar/toolbar/construction_button.dds": "crane",
    "topbar/toolbar/production_button.dds": "factory",
    "topbar/toolbar/deployment_button.dds": "deploy",
    "topbar/toolbar/ledger_button.dds": "truck",
    "topbar/toolbar/staff_office_button.dds": "officer_cap",
}


def _frames(*imgs):
    out = Image.new("RGBA", (sum(i.width for i in imgs), imgs[0].height), (0, 0, 0, 0))
    x = 0
    for i in imgs:
        out.paste(i, (x, 0))
        x += i.width
    return out


def line_toolbar(name):
    """110x41: frame 1 transparent + P icon, frame 2 (view open) keyer plate + P icon; 26 px icons."""
    def fn(ctx, src):
        fw, fh = ctx.w // 2, ctx.h
        return _frames(LI.on((fw, fh), name, 26),
                       LI.on((fw, fh), name, 26, bg=KEY, inset=(2, 2, 2, 2)))
    return fn


def line_overview(name):
    """76x38 army / navy / air: transparent / keyer square, 24 px icons."""
    def fn(ctx, src):
        fw, fh = ctx.w // 2, ctx.h
        return _frames(LI.on((fw, fh), name, 24),
                       LI.on((fw, fh), name, 24, bg=KEY, inset=(3, 3, 3, 3)))
    return fn


def line_single(name, size, bg=None, colour=LI.P, inset=(0, 0, 0, 0)):
    def fn(ctx, src):
        return LI.on((ctx.w, ctx.h), name, size, bg=bg, colour=colour, inset=inset)
    return fn


def line_strip(names, size, bg=None, colour=LI.P, inset=(0, 0, 0, 0)):
    """One icon per frame (names in frame order)."""
    def fn(ctx, src):
        n = len(names)
        fw = ctx.w // n
        return _frames(*[LI.on((fw, ctx.h), nm, size, bg=bg, colour=colour, inset=inset) for nm in names])
    return fn


def line_toggle(name, size=16):
    """44x22 map toggles, 2 frames of 22x22: off = D icon, on = P icon on keyer."""
    def fn(ctx, src):
        fw = ctx.w // 2
        return _frames(LI.on((fw, ctx.h), name, size, colour=LI.D),
                       LI.on((fw, ctx.h), name, size, bg=KEY, inset=(1, 1, 1, 1)))
    return fn


def line_board(alpha=BA):
    def fn(ctx, src):
        return Image.new("RGBA", (ctx.w, ctx.h), _rgba(BOARD, alpha))
    return fn


_MM_BIG = ["tank", "plane", "anchor", "eye"]
_MM_SMALL = ["question", "question", "question", "eye", "flag", "bars", "flame", "pennant", "canister", "locomotive",
             "star", "people", "person", "people", "globe", "trees", "crosshair", "crosshair"]

TEXTURES.update({k: line_toolbar(v) for k, v in _TOOLBAR_ICON.items()})
TEXTURES.update({
    "topbar/armyoverview_button.dds": line_overview("tank"),
    "topbar/navyoverview_button.dds": line_overview("anchor"),
    "topbar/airoverview_button.dds": line_overview("plane"),
    "factions/ui/topbar_faction_empty.dds": line_single("flag", 20, colour=LI.D),
    "topbar/zoom_in.dds": line_single("plus", 15, bg=SLATE),
    "topbar/zoom_out.dds": line_single("minus", 15, bg=SLATE),
    "topbar/button_menu.dds": line_single("menu", 18),
    "topbar/button_help.dds": line_single("question", 18),
    "topbar/show_dismissed_alerts_icon.dds": line_single("exclamation", 18),
    "topbar/achievements_button.dds": line_single("star", 18),
    "topbar/musicplayer/music_pause_button.dds": line_strip(["play", "pause"], 18),
    "topbar/musicplayer/music_next_button.dds": line_single("next", 18),
    "topbar/musicplayer/musicplayer_button.dds": line_single("note", 18),
    "topbar/musicplayer/playlist_button.dds": line_single("playlist", 18),
    "topbar/musicplayer/musicplayer_next_button.dds": line_single("next", 18),
    "topbar/musicplayer/musicplayer_previous_button.dds": line_single("prev", 18),
    "topbar/musicplayer/musicplayer_play_pause_button.dds": line_strip(["play", "pause"], 18),
    # map modes (right edge): flat squares, keyer when selected
    "mapmode/mapmode_buttons_deselected_big.dds": line_strip(_MM_BIG, 22, bg=SLATE, inset=(1, 1, 1, 1)),
    "mapmode/mapmode_buttons_selected_big.dds": line_strip(_MM_BIG, 22, bg=KEY, inset=(1, 1, 1, 1)),
    "mapmode/mapmode_buttons_deselected_small.dds": line_strip(_MM_SMALL, 15),
    "mapmode/mapmode_buttons_selected_small.dds": line_strip(_MM_SMALL, 15, bg=KEY, inset=(1, 0, 1, 0)),
    "mapmode/mapmode_button_bg.dds": line_board(1.0),
    "mapmode/mapmode_button_depressed.dds": solid(SLATE),
    "mapmode/mapmode_main_bg.dds": line_board(),
    "mapmode/map_modes_bg.dds": line_board(),
    "mapmode/mapmode_bottom_bg.dds": line_board(),
    "mapmode/find_screen_button.dds": line_single("magnifier", 22, bg=SLATE, inset=(2, 2, 2, 2)),
    "mapmode/day_night_toggle.dds": line_strip(["sun", "moon"], 16),
    "mapmode/fog_of_war_toggle.dds": line_toggle("eye"),
    "mapmode/radar_toggle.dds": line_toggle("crosshair"),
    "mapmode/player_counters_toggle.dds": line_toggle("person"),
    "mapmode/allied_plans_button.dds": line_toggle("pennant"),
    "mapmode/counters_color_mode_button.dds": line_toggle("shield"),
    "mapmode/mapmode_button_all.dds": line_toggle("menu"),
})
LOSSLESS |= set(_TOOLBAR_ICON) | {k for k in TEXTURES if k.startswith("mapmode/")}


def line_tension_dial(ctx, src):
    """490x49, 10 frames of 49x49: frame k lights k + 1 of 10 ticks (vector), red from frame 7, with a small line
    globe in the middle. Replaces the pixel dial of the first pass."""
    import numpy as np
    n = 10
    fw = ctx.w // n
    frames = []
    for k in range(n):
        pen = LI.Pen(fw, 1.6)
        lit = k + 1
        LI.dial(pen, lit)
        mask_lit = pen.img.resize((fw, fw), Image.LANCZOS)
        pen2 = LI.Pen(fw, 1.6)
        LI.dial(pen2, 0)
        mask_all = pen2.img.resize((fw, fw), Image.LANCZOS)
        rgb = (222, 86, 70) if k >= 6 else LI.P
        out = Image.new("RGBA", (fw, ctx.h), (0, 0, 0, 0))
        dim = np.zeros((fw, fw, 4), np.uint8); dim[..., :3] = LI.D; dim[..., 3] = (np.asarray(mask_all) * 0.22).astype(np.uint8)
        out.alpha_composite(Image.fromarray(dim, "RGBA"), (0, (ctx.h - fw) // 2))
        hot = np.zeros((fw, fw, 4), np.uint8); hot[..., :3] = rgb; hot[..., 3] = np.asarray(mask_lit)
        out.alpha_composite(Image.fromarray(hot, "RGBA"), (0, (ctx.h - fw) // 2))
        out.alpha_composite(LI.icon("globe", 21), ((fw - 21) // 2, (ctx.h - 21) // 2))
        frames.append(out)
    return _frames(*frames)


TEXTURES["world_tension_icon_big_strip.dds"] = line_tension_dial
