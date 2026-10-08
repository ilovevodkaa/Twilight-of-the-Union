"""Area 'kit': the shared vanilla chrome every window uses, hand-drawn in the broadcast style.

Families (everything else of the area falls back to the generic treatment):
  tiles      tiles/** window boards: one uniform flat board (corneredTile borders stay meaningful because the
             surface is uniform); tooltip board 0.92; light paper tiles keep a light flat surface (dark text);
             selectable / glow variants get keyer.
  plates     one-frame vanilla text buttons: SLATE plate with the stepped tail on the vanilla plate box (the
             buttonstate shader brightens it on hover); "gray" = raised, "reset" (yellow) = keyer.
  states     multi-frame sort buttons / tabs: slate / keyer (/ raised for disabled); sort up / down get a P triangle.
  checks     checkboxes: a square D at 30 % / keyer at the centre of the vanilla box; check.dds = P check.
  close      close buttons: slate square with a P pixel x.
  scroll     scrollbars and value sliders: P knob, P triangles / chevrons, D 18 % track, D 35 % slider line,
             transparent backgrounds.
  fields     generic boxes and text backgrounds: field (D 14 % over the board).
  header     header_bg (GFX_header_bg / GFX_tiled_header): keyer caption band with the tail.
  rows       filter list entries: D 8 % rows, keyer bar on the marked frame.
  frames     flag and leader frames: transparent (flag masks are separate files and stay vanilla); gold /
             selectable frames keep a keyer outline.
  bars       research progress bar: keyer fill, D 18 % track, no frame.
"""
from functools import partial

import numpy as np
from PIL import Image

from ingame import generic as g

AREA = "kit"

HOVER_ALPHA = 0.08          # list row: D at 8 %
SLIDER_LINE_ALPHA = 0.35    # slider line: D at 35 %
OFF_ALPHA = 0.30            # unchecked box: D at 30 %

# pixel pictograms (same grids as totu_broadcast.PICTO; copied so worker processes stay light)
_RIGHT_S = ["##..", ".##.", "..##", ".##.", "##.."]
PICTO = {
    "close": ["#.....#", "##...##", ".##.##.", "..###..", ".##.##.", "##...##", "#.....#"],
    "check": ["......#", ".....##", "#...##.", "##.##..", ".###...", "..#....", "......."],
    "triangle_up": ["..#..", ".###.", "#####"],
    "triangle_down": ["#####", ".###.", "..#.."],
    "triangle_left": ["..#", ".##", "###", ".##", "..#"],
    "triangle_right": ["#..", "##.", "###", "##.", "#.."],
    "chevron_right_s": _RIGHT_S,
    "chevron_left_s": [r[::-1] for r in _RIGHT_S],
}


# ---------------------------------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------------------------------
def _rgba(rgb, alpha):
    return tuple(rgb) + (round(255 * alpha),)


def _bbox(fr, thr=128):
    """Alpha bounding box (x0, y0, x1, y1 exclusive) of a frame, or the whole frame."""
    a = np.asarray(fr.convert("RGBA"))[..., 3]
    m = a >= thr
    if not m.any():
        return 0, 0, fr.width, fr.height
    ys, xs = np.nonzero(m)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def _picto(name, rgb=g.P, alpha=1.0, cell=2, drop=True):
    img = g.pictogram(PICTO[name], cell=cell, rgb=rgb, drop=drop)
    if alpha < 1.0:
        a = np.asarray(img).copy()
        a[..., 3] = (a[..., 3] * alpha).astype(np.uint8)
        img = Image.fromarray(a, "RGBA")
    return img


def _put_center(dst, pic, box=None):
    """Paste pic so its ink (without the K drop) is centred in box (default: dst), drop kept inside dst."""
    x0, y0, x1, y1 = box or (0, 0, dst.width, dst.height)
    iw, ih = pic.width - 2, pic.height - 2
    x = min(max(0, x0 + (x1 - x0 - iw) // 2), dst.width - pic.width)
    y = min(max(0, y0 + (y1 - y0 - ih) // 2), dst.height - pic.height)
    dst.alpha_composite(pic, (x, y))
    return dst


def _plate_on(fr_w, fr_h, box, rgb, alpha=1.0, tail=None):
    """A frame-sized transparent image with a plate (stepped tail) filling box."""
    x0, y0, x1, y1 = box
    out = g.blank(fr_w, fr_h)
    if x1 - x0 > 0 and y1 - y0 > 0:
        out.alpha_composite(g.plate(x1 - x0, y1 - y0, rgb, alpha, tail), (x0, y0))
    return out


def _rect_on(fr_w, fr_h, box, rgba):
    out = g.blank(fr_w, fr_h)
    out.paste(rgba, box)
    return out


def _outline(w, h, rgb, width=2, alpha=1.0, inset=0):
    out = g.blank(w, h)
    c = _rgba(rgb, alpha)
    i, t = inset, width
    out.paste(c, (i, i, w - i, i + t))
    out.paste(c, (i, h - i - t, w - i, h - i))
    out.paste(c, (i, i, i + t, h - i))
    out.paste(c, (w - i - t, i, w - i, h - i))
    return out


def _vluma(src):
    """Mean luma 0..1 of the opaque centre of a texture."""
    a = g.to_array(src)
    h, w = a.shape[:2]
    c = a[h // 3: h - h // 3, w // 3: w - w // 3]
    m = c[..., 3] > 128
    if not m.any():
        return 0.0
    return float(g.luma(c[..., :3])[m].mean() / 255)


# ---------------------------------------------------------------------------------------------------------------
# tiles
# ---------------------------------------------------------------------------------------------------------------
def board(ctx, src, rgb=g.BOARD, alpha=g.BOARD_ALPHA):
    """Uniform flat board (light paper tiles: a light flat surface, vanilla draws dark text there)."""
    if _vluma(src) > g.PAPER_LUMA:
        return ctx.flat(g.D, 0.95)
    return ctx.flat(rgb, alpha)


def board_selectable(ctx, src):
    """Two frames: board / board with a 4 px keyer bar at the left (the lit vanilla frame)."""
    fw = ctx.frame_w
    lit = g.flat(fw, ctx.h, g.BOARD, g.BOARD_ALPHA)
    lit.paste(_rgba(g.KEY_BLUE, 1.0), (0, 0, 4, ctx.h))
    return ctx.join([g.flat(fw, ctx.h, g.BOARD, g.BOARD_ALPHA), lit])


def glow_outline(ctx, src):
    """Highlight overlay over a window: keyer outline, clear centre."""
    return _outline(ctx.w, ctx.h, g.KEY_BLUE, width=3)


def mini_with_header(ctx, src):
    """Board with a raised band where vanilla has its title strip."""
    out = ctx.flat()
    a = g.to_array(src)
    lum = g.luma(a[..., :3]).mean(1) / 255
    body = np.median(lum[ctx.h // 2:])
    rows = [y for y in range(1, ctx.h // 2) if abs(lum[y] - body) > 0.03]
    hb = (max(rows) + 1) if rows else 10
    out.paste(_rgba(g.RAISED, g.RAISED_ALPHA), (0, 0, ctx.w, min(hb, ctx.border[1] if ctx.border else hb)))
    return out


def slate_band(ctx, src, tail=None):
    return g.plate(ctx.w, ctx.h, g.SLATE, 1.0, tail)


# ---------------------------------------------------------------------------------------------------------------
# one-frame plates
# ---------------------------------------------------------------------------------------------------------------
def plate1(ctx, src, rgb=g.SLATE):
    """One-frame text button: plate with the stepped tail on the vanilla plate box."""
    return _plate_on(ctx.w, ctx.h, _bbox(src), rgb)


# ---------------------------------------------------------------------------------------------------------------
# multi-frame states
# ---------------------------------------------------------------------------------------------------------------
def states(ctx, src, tones=(g.SLATE, g.KEY_BLUE), picto=None):
    """Frames -> plates in tones (one per frame; the last repeats). picto: {frame index: pictogram name}, placed at
    the right end of the plate (vanilla sort arrows)."""
    parts = []
    for i, fr in enumerate(ctx.split(src)):
        box = _bbox(fr)
        rgb = tones[min(i, len(tones) - 1)]
        p = _plate_on(fr.width, fr.height, box, rgb)
        if picto and i in picto:
            x0, y0, x1, y1 = box
            _put_center(p, _picto(picto[i]), (x1 - 30, y0, x1 - 12, y1))
        parts.append(p)
    return ctx.join(parts)


# ---------------------------------------------------------------------------------------------------------------
# checkboxes
# ---------------------------------------------------------------------------------------------------------------
def checkbox(ctx, src, size=20):
    """Frames off / on: a square D at 30 % / keyer at the centre of the vanilla box."""
    parts = []
    for i, fr in enumerate(ctx.split(src)):
        x0, y0, x1, y1 = _bbox(fr)
        s = min(size, (min(x1 - x0, y1 - y0) - 4) // 2 * 2)
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        box = (cx - s // 2, cy - s // 2, cx - s // 2 + s, cy - s // 2 + s)
        rgba = _rgba(g.D, OFF_ALPHA) if i == 0 else _rgba(g.KEY_BLUE, 1.0)
        parts.append(_rect_on(fr.width, fr.height, box, rgba))
    return ctx.join(parts)


def check_mark(ctx, src):
    return _put_center(ctx.blank(), _picto("check"), _bbox(src))


# ---------------------------------------------------------------------------------------------------------------
# close buttons
# ---------------------------------------------------------------------------------------------------------------
def close(ctx, src):
    """Slate square (24 px, smaller in small buttons) with a P pixel x, centred on the vanilla button."""
    parts = []
    for fr in ctx.split(src):
        x0, y0, x1, y1 = _bbox(fr)
        s = min(24, (min(fr.width, fr.height) - 4) // 2 * 2)
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        bx, by = min(max(0, cx - s // 2), fr.width - s), min(max(0, cy - s // 2), fr.height - s)
        box = (bx, by, bx + s, by + s)
        p = _rect_on(fr.width, fr.height, box, _rgba(g.SLATE, 1.0))
        parts.append(_put_center(p, _picto("close"), box))
    return ctx.join(parts)


# ---------------------------------------------------------------------------------------------------------------
# scrollbars and sliders
# ---------------------------------------------------------------------------------------------------------------
def scroll_knob(ctx, src, size=10):
    o = (ctx.w - size) // 2, (ctx.h - size) // 2
    return _rect_on(ctx.w, ctx.h, (o[0], o[1], o[0] + size, o[1] + size), _rgba(g.P, g.SCROLL_KNOB_ALPHA))


def scroll_arrow(ctx, src, name):
    return _put_center(ctx.blank(), _picto(name))


def track(ctx, src, vertical=True, width=6):
    if vertical:
        x = (ctx.w - width) // 2
        box = (x, 0, x + width, ctx.h)
    else:
        y = (ctx.h - width) // 2
        box = (0, y, ctx.w, y + width)
    return _rect_on(ctx.w, ctx.h, box, _rgba(g.D, g.TRACK_ALPHA))


def clear(ctx, src):
    return ctx.blank()


def slider_line(ctx, src):
    y = ctx.h // 2 - 1
    return _rect_on(ctx.w, ctx.h, (0, y, ctx.w, y + 2), _rgba(g.D, SLIDER_LINE_ALPHA))


def slider_end(ctx, src, name):
    """Four frames (normal, hover, pressed, disabled): P chevron; keyer / pressed square behind hover / pressed;
    disabled D at 30 %."""
    parts = []
    for i, fr in enumerate(ctx.split(src)):
        s = min(16, fr.width, fr.height)
        bx, by = (fr.width - s) // 2, (fr.height - s) // 2
        box = (bx, by, bx + s, by + s)
        p = g.blank(fr.width, fr.height)
        if i in (1, 2):
            p.paste(_rgba(g.KEY_BLUE if i == 1 else g.KEY_BLUE_DOWN, 1.0), box)
        pic = _picto(name, g.D, g.DISABLED_ALPHA, drop=False) if i >= 3 else _picto(name)
        parts.append(_put_center(p, pic, box))
    return ctx.join(parts)


# ---------------------------------------------------------------------------------------------------------------
# dropdown / expand
# ---------------------------------------------------------------------------------------------------------------
def expand(ctx, src, name="triangle_down"):
    box = _bbox(src)
    p = _rect_on(ctx.w, ctx.h, box, _rgba(g.SLATE, 1.0))
    return _put_center(p, _picto(name), box)


# ---------------------------------------------------------------------------------------------------------------
# fields, header, rows, frames, bars
# ---------------------------------------------------------------------------------------------------------------
def field(ctx, src, full=False):
    """Field (D 14 % over the board) on the vanilla box (full: the whole texture, for corneredTiles)."""
    box = (0, 0, ctx.w, ctx.h) if full else _bbox(src)
    return ctx.join([_rect_on(fr.width, fr.height, box, _rgba(g.FIELD, g.FIELD_A)) for fr in ctx.split(src)])


def header(ctx, src):
    """Keyer caption band with the stepped tail (the tail sits in the corneredTile's right border)."""
    out = ctx.blank()
    out.alpha_composite(g.plate(ctx.w, min(40, ctx.h), g.KEY_BLUE, 1.0, 12), (0, 0))
    return out


def row(ctx, src, marked=None, full=False):
    """List entry: D 8 % row; the marked frame (vanilla's lit markers) gets a 4 px keyer bar at the left."""
    parts = []
    for i, fr in enumerate(ctx.split(src)):
        box = (0, 0, fr.width, fr.height) if full else _bbox(fr)
        p = _rect_on(fr.width, fr.height, box, _rgba(g.D, HOVER_ALPHA))
        if i == marked:
            p.paste(_rgba(g.KEY_BLUE, 1.0), (box[0], box[1], box[0] + 4, box[3]))
        parts.append(p)
    return ctx.join(parts)


def frame_outline(ctx, src, frames_lit=(0,)):
    """Frame that marks something (gold / selected): 2 px keyer outline on the vanilla box, else transparent."""
    parts = []
    for i, fr in enumerate(ctx.split(src)):
        if i in frames_lit:
            x0, y0, x1, y1 = _bbox(fr)
            o = g.blank(fr.width, fr.height)
            o.alpha_composite(_outline(x1 - x0, y1 - y0, g.KEY_BLUE, 2), (x0, y0))
            parts.append(o)
        else:
            parts.append(g.blank(fr.width, fr.height))
    return ctx.join(parts)


def bar_fill(ctx, src, rgb=g.KEY_BLUE):
    return _rect_on(ctx.w, ctx.h, _bbox(src, 32), _rgba(rgb, 1.0))


def bar_track(ctx, src):
    return _rect_on(ctx.w, ctx.h, _bbox(src, 32), _rgba(g.D, g.TRACK_ALPHA))


# ---------------------------------------------------------------------------------------------------------------
# texture table
# ---------------------------------------------------------------------------------------------------------------
_BOARD_TILES = [
    "tiles/raids_filter_tiled_bg.dds", "tiles/tiled_bg.dds", "tiles/tiled_bg_1_scrollbar.dds",
    "tiles/tiled_decisions_bg_small.dds", "tiles/tiled_generic_bg_1.dds", "tiles/tiled_generic_overlay_bg1.dds",
    "tiles/tiled_generic_overlay_bg1_small.dds", "tiles/tiled_insignia_window.dds", "tiles/tiled_paper_bg.dds",
    "tiles/tiled_paper_bg2.dds", "tiles/tiled_paper_flat_bg.dds", "tiles/tiled_paper_w_frame_bg.dds",
    "tiles/tiled_paper_w_frame_one_border.dds", "tiles/tiled_paper_w_frame_one_border_2.dds",
    "tiles/tiled_peace_upper_bar.dds", "tiles/tiled_plain_bg.dds", "tiles/tiled_plain_bg2.dds",
    "tiles/tiled_plain_bg_small.dds", "tiles/tiled_window.dds", "tiles/tiled_window2_1b_border.dds",
    "tiles/tiled_window2_2b_border.dds", "tiles/tiled_window_1_scrollbar.dds", "tiles/tiled_window_1b_border.dds",
    "tiles/tiled_window_1b_thin_border.dds", "tiles/tiled_window_2_scrollbars.dds",
    "tiles/tiled_window_pol_goal.dds", "tiles/tiled_window_small.dds", "tiles/tiled_window_small_small.dds",
    "tiles/tiled_window_thin_border.dds", "tiles/tiled_window_thin_border2.dds", "tiles/tiled_window_w_close.dds",
    "tiles/tiled_mini_dialog.dds", "tiles/tiled_window_color_picker.dds",
]
_PLATES = [
    "button_123x34.dds", "button_148x34.dds", "button_221x34.dds", "button_261x34.dds", "button_94x31.dds",
    "button_type_1.dds", "button_type_4.dds", "button_type_6.dds", "button_type_7.dds", "button_type_9.dds",
    "small_button_71x26.dds", "naval_name_list_button.dds", "select_all_armylist_btn.dds",
    "battle_log_battle_button.dds", "sort_160.dds",
]
_STATES2 = [
    "sort_button_100x29.dds", "sort_button_140x29.dds", "sort_button_171x35.dds",
    "sort_button_202x29.dds", "sort_button_428x29.dds", "sort_button_83x29.dds", "tab_large.dds",
    "battle_log_tab.dds",
]
_CHECKS = ["generic_checkbox.dds", "generic_checkbox3.dds", "checkbox_gold_32.dds"]
_CLOSE = ["closebutton.dds", "closebutton_small.dds", "close_button_small.dds", "main_close_button.dds",
          "nf_close_button.dds", "naviesview/btn_close.dds"]
_FIELDS = ["generic_box_smallest.dds", "generic_text_bg_60.dds", "generic_text_bg_88.dds",
           "generic_text_bg_154.dds", "generic_text_bg_203.dds", "generic_w_box.dds", "generic_mini_bg.dds",
           "generic_bg2.dds", "edittextbox_bg1.dds"]
_FLAG_FRAMES = ["large_flag_frame.dds", "small_flag_frame_thin.dds", "small_flag_frame_thin2.dds",
                "small_flag_frame_thin_2.dds", "diplo_countrylist_flag_frame.dds", "diplo_flag_frame.dds",
                "diplo_leader_frame.dds", "pol_leader_frame.dds", "land_battle_leader_frame.dds",
                "naval_unit_leader_frame.dds", "armyoverview_naval_leader_frame.dds",
                "unitcontrol/unit_leader_portrait_frame.dds", "unitcontrol/unit_leader_portrait_frame_badge.dds"]

TEXTURES = {}
TEXTURES.update({k: board for k in _BOARD_TILES})
TEXTURES.update({
    "tiles/tiles_dialog.dds": partial(board, alpha=g.RAISED_ALPHA),
    "tiles/tiled_mini_dialog_grey.dds": partial(board, rgb=g.RAISED, alpha=g.RAISED_ALPHA),
    "tiles/tiled_mini_dialog_with_header.dds": mini_with_header,
    "tiles/tiled_window_small_selectable.dds": board_selectable,
    "tiles/tiled_window_1_scrollbar_glow.dds": glow_outline,
    "tiles/tiled_header_1.dds": partial(slate_band, tail=8),
    "tiles/tiling_sort_button.dds": partial(slate_band, tail=6),
    "tiles/tiling_sort_button_thin.dds": partial(slate_band, tail=0),
})
TEXTURES.update({k: plate1 for k in _PLATES})
TEXTURES.update({
    "button_123x34_gray.dds": partial(plate1, rgb=g.RAISED),
    "button_reset_123x34.dds": partial(plate1, rgb=g.KEY_BLUE),
})
TEXTURES.update({k: states for k in _STATES2})
TEXTURES.update({
    "sort_button_202x29_3_frames.dds": partial(states, tones=(g.SLATE, g.KEY_BLUE, g.RAISED)),
    "sort_button_100x29_2.dds": partial(states, tones=(g.KEY_BLUE, g.SLATE)),     # vanilla marks frame 0
    "sort_up_down_button_83x29.dds": partial(states, tones=(g.SLATE, g.KEY_BLUE),
                                             picto={1: "triangle_up", 2: "triangle_down"}),
})
TEXTURES.update({k: checkbox for k in _CHECKS})
TEXTURES["check.dds"] = check_mark
TEXTURES.update({k: close for k in _CLOSE})
TEXTURES.update({
    "scroll_drager.dds": scroll_knob,
    "unitcontrol/color_picker_scroll_drager.dds": scroll_knob,
    "scroll_up.dds": partial(scroll_arrow, name="triangle_up"),
    "scroll_down.dds": partial(scroll_arrow, name="triangle_down"),
    "scroll_left.dds": partial(scroll_arrow, name="triangle_left"),
    "scroll_right.dds": partial(scroll_arrow, name="triangle_right"),
    "scroll_track.dds": track,
    "unitcontrol/color_picker_scroll_track.dds": track,
    "scroll_track_horisontal.dds": partial(track, vertical=False),
    "scrollbar_vertical_bg.dds": clear,
    "scrollbar_horisontal_bg.dds": clear,
    "scrollbar_sliderbackground.dds": slider_line,
    "scrollbar_leftbutton.dds": partial(slider_end, name="chevron_left_s"),
    "scrollbar_rightbutton.dds": partial(slider_end, name="chevron_right_s"),
    "expand_button.dds": expand,
})
TEXTURES.update({k: field for k in _FIELDS})
TEXTURES.update({
    "generic_box.dds": partial(field, full=True),
    "small_tiles_dialog.dds": partial(field, full=True),
    "header_bg.dds": header,
    "diplo_filter_entry.dds": partial(row, marked=0, full=True),
    "overview_filter_entry.dds": row,
    "unit_stats_list_entry2.dds": row,
})
TEXTURES.update({k: clear for k in _FLAG_FRAMES})
TEXTURES.update({
    "small_flag_frame_thin2_gold.dds": frame_outline,
    "small_flag_frame_selectable.dds": partial(frame_outline, frames_lit=(1,)),
    "research_progressbar.dds": bar_fill,
    "research_progressbar_bg.dds": bar_track,
    "research_progressbar_frame.dds": clear,
})

# pixel-exact edges, exact keyer and pictograms: never DXT5
LOSSLESS = set(TEXTURES) - set(_BOARD_TILES)
