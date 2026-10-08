"""Area 'trees': national focus tree, tech tree, decisions (broadcast style).

Focus title plates: flat 40 px plates with the stepped tail (unavailable = slate 60 %, can start = slate with a
2 px keyer bar, completed = keyer-down with a 2 px P bar; the current focus is the can-start plate under the
engine's additive 'ongoing' animation, whose texture becomes a keyer glow). Joint plates keep their flag ribbons.
Tech items: flat plates (available slate, researched keyer, unavailable slate dim, branch raised + hatch),
researching strips pulse in keyer. Connectors: 2 px lines (D, completed / researched keyer).
"""
import math

import numpy as np
from PIL import Image

from . import generic as g
from ._views_common import (KEY_LIGHT, alpha_bbox, arr, body_rect, board_over_silhouette, fill_rect, img_of,
                            lines, mix, put_rect, tail_plate, vanilla_glob)

AREA = "trees"

TEXTURES = {}
LOSSLESS = set()


def claim(paths, fn, lossless=True):
    for p in paths:
        TEXTURES[p] = fn
        if lossless:
            LOSSLESS.add(p)


# ---------------------------------------------------------------------------------------------------------------
# focus tree
# ---------------------------------------------------------------------------------------------------------------
FOCUS_STATES = {
    # state: (rgb, alpha, bar rgb or None)
    "unavailable": (g.SLATE, 0.60, None),
    "can_start": (g.SLATE, 0.94, g.KEY_BLUE),
    "start": (g.SLATE, 0.94, g.KEY_BLUE),
    "completed": (g.KEY_BLUE_DOWN, 0.96, g.P),
}


def _focus_state(path):
    name = path.rsplit("/", 1)[-1]
    for st in ("unavailable", "completed", "can_start", "start"):
        if name.startswith("focus_" + st):
            return st
    return "can_start"


def focus_plate(ctx, src):
    a = arr(src)
    rgb, alpha, bar = FOCUS_STATES[_focus_state(ctx.path)]
    bb = body_rect(a, 0.85)
    x0, y0, x1, y1 = bb
    out = Image.new("RGBA", src.size, (0, 0, 0, 0))
    joint = "_joint_" in ctx.path and ctx.h > 50
    if joint:   # participants' flag ribbon below the plate: content, kept
        keep = a.copy()
        keep[:y1] = 0
        out = img_of(keep)
    tail_plate(out, (x0, y0, x1, y1), rgb, alpha, tail=12)
    if bar:
        put_rect(out, (x0, y0, x0 + 2, y1), bar, 1.0)
    return out


claim([p for p in vanilla_glob("focusview/titlebar/focus_*_bg.dds")], focus_plate)


def ongoing_texture(ctx, src):
    """Additive rotating texture of GFX_focus_current (and the intel / operation 'ongoing' sprites): keyer glow."""
    a = arr(src)
    lum = (a[..., :3].mean(-1) / 255.0) * (a[..., 3] / 255.0)
    k = np.clip(lum * 2.2, 0, 1)
    out = np.zeros_like(a)
    for c, v in enumerate((34, 70, 190)):
        out[..., c] = v * k
    out[..., 3] = 255 * k
    return img_of(out)


def no_add(ctx, src):
    """Additive sweep of the completed plate: nothing (flat plates)."""
    return Image.new("RGBA", src.size, (0, 0, 0, 0))


TEXTURES["focusview/titlebar/focus_ongoing_texture.dds"] = ongoing_texture
TEXTURES["focusview/titlebar/focus_completed_texture.dds"] = no_add


def focus_link(ctx, src):
    return lines(src, ctx.frames, r=1)


claim(vanilla_glob("focusview/focus_link_*.dds"), focus_link)
claim(vanilla_glob("focusview/focus_exlusive_link_line*.dds"), focus_link)
LINK_FRAMES = {}


def focus_bg(ctx, src):
    return board_over_silhouette(src)


TEXTURES["tiles/tiled_focus_bg.dds"] = focus_bg


# ---------------------------------------------------------------------------------------------------------------
# tech tree
# ---------------------------------------------------------------------------------------------------------------
TECH_STATES = {
    "available": (g.SLATE, 0.94),
    "researched": (g.KEY_BLUE, 0.96),
    "unavailable": (g.SLATE, 0.50),
    "branch": (g.RAISED, 0.92),
    "currently_researching": (g.KEY_BLUE, 0.96),
}


def _tech_state(path):
    name = path.rsplit("/", 1)[-1]
    for st in ("unavailable", "researched", "currently_researching", "branch", "available"):
        if "_" + st + "_" in name or name.startswith(st + "_"):
            return st
    if "researching" in name:
        return "currently_researching"
    return "available"


def _hatch(out, box):
    x0, y0, x1, y1 = box
    a = arr(out)
    yy, xx = np.mgrid[y0:y1, x0:x1]
    h = ((xx + yy) % 16) < 5
    sub = a[y0:y1, x0:x1, :3]
    sub[h] = sub[h] * (1 - 0.14) + np.array(g.D, np.float32) * 0.14
    return img_of(a)


def _tech_body(a):
    if a.shape[0] < 40:
        return alpha_bbox(a)
    bb = body_rect(a, 0.9)
    return bb


def tech_item(ctx, src):
    a = arr(src)
    st = _tech_state(ctx.path)
    rgb, alpha = TECH_STATES[st]

    def one(fr, _i):
        fa = arr(fr)
        bb = _tech_body(fa)
        out = Image.new("RGBA", fr.size, (0, 0, 0, 0))
        if not bb:
            return out
        x0, y0, x1, y1 = bb
        bb = (x0 + 1, y0 + 1, x1 - 1, y1 - 1)
        put_rect(out, bb, rgb, alpha)
        if st == "branch":
            out = _hatch(out, bb)
        if st == "available":
            out = fill_rect(out, (bb[0], bb[1], bb[0] + 2, bb[3]), g.KEY_BLUE, 1.0) if ctx.h >= 40 else out
        return out

    return ctx.per_frame(src, one)


def researching_strip(ctx, src):
    """Keyer plate pulsing over the strip's frames (sine, keyer -> keyer lightened with P)."""
    n = ctx.frames

    def one(fr, i):
        fa = arr(fr)
        bb = _tech_body(fa)
        out = Image.new("RGBA", fr.size, (0, 0, 0, 0))
        if not bb:
            return out
        x0, y0, x1, y1 = bb
        t = 0.5 - 0.5 * math.cos(2 * math.pi * i / max(n, 1))
        put_rect(out, (x0 + 1, y0 + 1, x1 - 1, y1 - 1), mix(g.KEY_BLUE, KEY_LIGHT, 0.55 * t), 0.96)
        return out

    return ctx.per_frame(src, one)


claim(["techtree/technology_%s_item_bg.dds" % s for s in ("available", "researched", "unavailable", "branch")],
      tech_item)
claim([p for p in vanilla_glob("techtree/technology_special_project_*_item_bg.dds")], tech_item)
claim(["subtechnology_unavailable_item_bg.dds"], tech_item)
claim(["techtree/researching_anim_strip.dds", "techtree/researching_special_projects_big_anim_strip.dds",
       "techtree/technology_special_project_naval_researching_anim_strip.dds",
       "techtree/technology_special_project_small_researching_anim_strip.dds"], researching_strip)


def tech_line(ctx, src):
    anim = "strip" in ctx.path.rsplit("/", 1)[-1]
    return lines(src, ctx.frames, r=3, anim=anim)


def tech_dotline(ctx, src):
    anim = "strip" in ctx.path.rsplit("/", 1)[-1]
    return lines(src, ctx.frames, r=1, anim=anim, sat=10)


claim(vanilla_glob("techtree/techtree_line_*.dds") + vanilla_glob("techtree/techline_center_*.dds"), tech_line)
claim(vanilla_glob("techtree/techtree_dotline_*.dds"), tech_dotline)


def tech_bg(ctx, src):
    return board_over_silhouette(src)


claim(vanilla_glob("techtree/*_techtree_bg.dds") + ["armortech_bg.dds", "wonderweapons_bg.dds"], tech_bg,
      lossless=False)


# ---------------------------------------------------------------------------------------------------------------
# decisions
# ---------------------------------------------------------------------------------------------------------------
def category_header(ctx, src):
    """Raised band with a slate caption plate where vanilla has its dark name plate; the icon box a field."""
    a = arr(src)
    out = Image.new("RGBA", src.size, (0, 0, 0, 0))
    x0, y0, x1, y1 = body_rect(a, 0.9)
    put_rect(out, (x0, y0, x1, y1), g.RAISED, g.RAISED_ALPHA)
    put_rect(out, (x0, y0, x0 + 2, y1), g.KEY_BLUE, 1.0)
    return out


DECISION_FRAMES = [(g.SLATE, 0.94), (g.KEY_BLUE, 0.96), (g.RAISED, 0.92)]


def decision_item(ctx, src):
    def one(fr, i):
        fa = arr(fr)
        out = Image.new("RGBA", fr.size, (0, 0, 0, 0))
        bb = alpha_bbox(fa)
        if not bb:
            return out
        rgb, al = DECISION_FRAMES[min(i, 2)] if ctx.frames > 1 else (
            (g.KEY_BLUE, 0.96) if "single" in ctx.path else (g._over(g.SEM_R, 0.40, g.BOARD, 1.0)[0], 0.94))
        x0, y0, x1, y1 = bb
        put_rect(out, (x0, y0 + 1, x1, y1 - 1), rgb, al)
        return out

    return ctx.per_frame(src, one)


TEXTURES["decisionview/category_header_bg.dds"] = category_header
claim(["decisionview/decision_item_bg.dds", "decisionview/decision_item_bg_single.dds",
       "decisionview/decision_ai_item_bg.dds"], decision_item)
TEXTURES["decisionview/category_header_bg.dds"] = category_header
LOSSLESS.add("decisionview/category_header_bg.dds")
