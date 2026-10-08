"""Area 'views': per-view backgrounds and panels (broadcast style).

Redrawn here: the politics panel (pol_view_bg*: flat board, raised national-spirit panel with a slate caption
plate, field cells in the bottom row, no ornaments), the focus-goal glows of the politics view (keyer), sub-tech
plates (available slate, researched keyer, unavailable slate dim, researching keyer pulse), idea group headers and
research slot rows. Everything else in the area stays on the generic treatment (flatten / regrade).
"""
import math

import numpy as np
from PIL import Image

from . import generic as g
from ._views_common import (KEY_LIGHT, alpha_bbox, arr, body_rect, hairline_rect, img_of, mix, put_rect,
                            tail_plate)

AREA = "views"

TEXTURES = {}
LOSSLESS = set()


# ---------------------------------------------------------------------------------------------------------------
# politics panel (550 x 344): vanilla regions measured on pol_view_bg.dds
# ---------------------------------------------------------------------------------------------------------------
POL_SPIRIT = (174, 103, 538, 254)        # national spirit / faction panel (right, middle)
POL_SPIRIT_TAB = (174, 103, 357, 126)    # its caption tab ("National spirit")
POL_SPIRIT_DIV = 197                     # divider between spirits and the faction row
POL_CELLS = [                            # bottom row: ideology icon, ideology name, party pie, party list
    ((12, 258, 86, 327), "field"),
    ((90, 258, 252, 327), "field"),
    ((261, 258, 338, 327), "field"),
    ((341, 258, 538, 327), "raised"),
]


def pol_view(ctx, src):
    a = arr(src)
    out = Image.new("RGBA", src.size, (0, 0, 0, 0))
    bb = alpha_bbox(a, 128)
    put_rect(out, bb, g.BOARD, g.BOARD_ALPHA)
    put_rect(out, POL_SPIRIT, g.RAISED, g.RAISED_ALPHA)
    tail_plate(out, POL_SPIRIT_TAB, g.SLATE, 0.94, tail=6)
    hairline_rect(out, (POL_SPIRIT[0], POL_SPIRIT_DIV, POL_SPIRIT[2], POL_SPIRIT_DIV + 1))
    for box, tone in POL_CELLS:
        rgb, al = g.TONES[tone]
        put_rect(out, box, rgb, al)
    if "no_dlc" in ctx.path:     # the no-DLC panel has a name box in the faction row
        put_rect(out, (187, 209, 387, 233), *g.TONES["field"])
    return out


TEXTURES["pol_view_bg.dds"] = pol_view
TEXTURES["pol_view_bg_no_dlc.dds"] = pol_view
LOSSLESS |= {"pol_view_bg.dds", "pol_view_bg_no_dlc.dds"}


def keyer_glow(ctx, src):
    """Cyan / gold glows behind the current focus goal: keyer blue in the vanilla shape and alpha."""
    a = arr(src)
    lum = a[..., :3].max(-1) / 255.0
    out = np.zeros_like(a)
    t = np.clip((lum - 0.5) / 0.5, 0, 1)[..., None]
    out[..., :3] = np.array(g.KEY_BLUE, np.float32) * (1 - t) + np.array(KEY_LIGHT, np.float32) * t
    out[..., 3] = a[..., 3]
    return img_of(out)


TEXTURES["ongoing_focus_goal.dds"] = keyer_glow
TEXTURES["ongoing_focus_goal_polview.dds"] = keyer_glow


def band_header(ctx, src):
    """Group header: raised band over the vanilla body with a 2 px keyer bar at the left."""
    a = arr(src)
    out = Image.new("RGBA", src.size, (0, 0, 0, 0))
    bb = body_rect(a, 0.9)
    if not bb:
        return out
    x0, y0, x1, y1 = bb
    put_rect(out, (x0, y0 + 1, x1, y1 - 1), g.RAISED, g.RAISED_ALPHA)
    put_rect(out, (x0, y0 + 1, x0 + 2, y1 - 1), g.KEY_BLUE, 1.0)
    return out


TEXTURES["idea_group_header.dds"] = band_header
LOSSLESS.add("idea_group_header.dds")


def research_row(ctx, src):
    """Research slot row: raised sub-panel (board around it)."""
    a = arr(src)
    out = Image.new("RGBA", src.size, (0, 0, 0, 0))
    bb = alpha_bbox(a, 128)
    if bb:
        x0, y0, x1, y1 = bb
        put_rect(out, (x0, y0 + 2, x1, y1 - 2), g.RAISED, g.RAISED_ALPHA)
    return out


TEXTURES["research_line_bg.dds"] = research_row


# ---------------------------------------------------------------------------------------------------------------
# sub-technology plates (40 x 27)
# ---------------------------------------------------------------------------------------------------------------
SUB = {
    "subtechnology_available_item_bg.dds": (g.SLATE, 0.94),
    "subtechnology_researched_item_bg.dds": (g.KEY_BLUE, 0.96),
}


def sub_plate(ctx, src):
    rgb, al = SUB[ctx.path]
    out = Image.new("RGBA", src.size, (0, 0, 0, 0))
    bb = alpha_bbox(arr(src))
    x0, y0, x1, y1 = bb
    put_rect(out, (x0 + 1, y0 + 1, x1 - 1, y1 - 1), rgb, al)
    return out


def sub_researching(ctx, src):
    def one(fr, i):
        out = Image.new("RGBA", fr.size, (0, 0, 0, 0))
        x0, y0, x1, y1 = alpha_bbox(arr(fr))
        put_rect(out, (x0 + 1, y0 + 1, x1 - 1, y1 - 1), mix(g.KEY_BLUE, KEY_LIGHT, 0.5 * i), 0.96)
        return out

    return ctx.per_frame(src, one)


for _p in SUB:
    TEXTURES[_p] = sub_plate
    LOSSLESS.add(_p)
TEXTURES["subtechnology_currently_researching_item_bg.dds"] = sub_researching
LOSSLESS.add("subtechnology_currently_researching_item_bg.dds")

_ = (math, tail_plate)


# ---------------------------------------------------------------------------------------------------------------
# Politics panel, second pass (2026-10-07): the user called the country menu "terrible". The national focus button
# still showed a regraded photo frame, "no focus" a laurel wreath, the advisor slots silhouette cards and the
# section icons gold sculpture. All of them are redrawn here: flat panels and the HUD line icons (_lineicons).
# ---------------------------------------------------------------------------------------------------------------
from . import _lineicons as LI  # noqa: E402

_RAISED = (18, 22, 30)
_SLATE = (40, 47, 62)
_KEY = (30, 62, 168)
_KEY_DOWN = (17, 38, 108)
_FIELD = (172, 180, 196)


def _flat_frames(sizes_bg):
    frames = []
    for (w, h), (rgb, a), bar in sizes_bg:
        f = Image.new("RGBA", (w, h), (*rgb, round(255 * a)))
        if bar:
            f.paste(Image.new("RGBA", (4, h), (*_KEY, 255)), (0, 0))
        frames.append(f)
    out = Image.new("RGBA", (sum(f.width for f in frames), frames[0].height), (0, 0, 0, 0))
    x = 0
    for f in frames:
        out.paste(f, (x, 0))
        x += f.width
    return out


def focus_button(ctx, src):
    """add_national_goal_button 777x83, 3 frames: raised panel with a 4 px keyer bar / slate / pressed keyer."""
    fw = ctx.w // 3
    return _flat_frames([((fw, ctx.h), (_RAISED, 0.95), True), ((fw, ctx.h), (_SLATE, 1.0), True),
                         ((fw, ctx.h), (_KEY_DOWN, 1.0), False)])


def raised_panel(ctx, src):
    return Image.new("RGBA", (ctx.w, ctx.h), (*_RAISED, 235))


def clear(ctx, src):
    return Image.new("RGBA", (ctx.w, ctx.h), (0, 0, 0, 0))


def goal_unknown(ctx, src):
    """94x76 'no focus chosen': a slate square with a line question mark (no laurel)."""
    s = 58
    out = Image.new("RGBA", (ctx.w, ctx.h), (0, 0, 0, 0))
    out.paste(Image.new("RGBA", (s, s), (*_SLATE, 255)), ((ctx.w - s) // 2, (ctx.h - s) // 2))
    out.alpha_composite(LI.icon("question", 34), ((ctx.w - 34) // 2, (ctx.h - 34) // 2))
    return out


def gov_button(ctx, src):
    """government_button 172x35 (1 frame, shader hover): slate plate with the stepped tail."""
    out = Image.new("RGBA", (ctx.w, ctx.h), (0, 0, 0, 0))
    body = ctx.w - 12
    out.paste(Image.new("RGBA", (body, ctx.h - 4), (*_SLATE, 255)), (0, 2))
    out.paste(Image.new("RGBA", (6, ctx.h - 4), (*_SLATE, 153)), (body, 2))
    out.paste(Image.new("RGBA", (6, ctx.h - 4), (*_SLATE, 77)), (body + 6, 2))
    return out


def slot(name, icon_size=24, colour=LI.D, plus=False):
    """63x63 / 63x66 empty slot: a field square (D at 14 %) with a line icon; plus=True adds a small P '+'."""
    def fn(ctx, src):
        out = Image.new("RGBA", (ctx.w, ctx.h), (0, 0, 0, 0))
        out.paste(Image.new("RGBA", (ctx.w - 6, ctx.h - 6), (*_FIELD, 36)), (3, 3))
        out.alpha_composite(LI.icon(name, icon_size, colour), ((ctx.w - icon_size) // 2, (ctx.h - icon_size) // 2))
        if plus:
            out.alpha_composite(LI.icon("plus", 14), (ctx.w - 20, ctx.h - 20))
        return out
    return fn


def add_idea(ctx, src):
    out = Image.new("RGBA", (ctx.w, ctx.h), (0, 0, 0, 0))
    out.paste(Image.new("RGBA", (ctx.w - 6, ctx.h - 6), (*_SLATE, 255)), (3, 3))
    out.alpha_composite(LI.icon("plus", 26), ((ctx.w - 26) // 2, (ctx.h - 26) // 2))
    return out


def idea_categories(ctx, src):
    """288x33, 6 frames of 48x33: section icons of the advisor list as P line icons."""
    names = ["flag", "columns", "columns", "gear", "tank", "eye"]
    fw = ctx.w // len(names)
    out = Image.new("RGBA", (ctx.w, ctx.h), (0, 0, 0, 0))
    for i, n in enumerate(names):
        out.alpha_composite(LI.icon(n, 26), (i * fw + (fw - 26) // 2, (ctx.h - 26) // 2))
    return out


TEXTURES.update({
    "add_national_goal_button.dds": focus_button,
    "pol_goal_bg.dds": raised_panel,
    "ongoing_focus_goal_polview.dds": clear,
    "goals/goal_unknown.dds": goal_unknown,
    "government_button.dds": gov_button,
    "officer_corp/select_advisor.dds": slot("person", 26, plus=True),
    "idea_slot_industrial_concern.dds": slot("factory", 26, plus=True),
    "idea_slot_materiel_manufacturer.dds": slot("gear", 26, plus=True),
    "idea_slot_naval_manufacturer.dds": slot("anchor", 26, plus=True),
    "idea_slot_aircraft_manufacturer.dds": slot("plane", 26, plus=True),
    "idea_slot_tank_manufacturer.dds": slot("tank", 26, plus=True),
    "add_pol_idea_button.dds": add_idea,
    "idea_categories.dds": idea_categories,
})
LOSSLESS |= {"add_national_goal_button.dds", "goals/goal_unknown.dds", "government_button.dds",
             "officer_corp/select_advisor.dds", "add_pol_idea_button.dds", "idea_categories.dds"}
LOSSLESS |= {k for k in TEXTURES if k.startswith("idea_slot_")}
