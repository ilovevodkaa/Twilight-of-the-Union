"""Area modules of the in-game texture pipeline (tools/build_ingame_gfx.py). See README.md in this folder.

An area module is tools/ingame/<area>.py with
    AREA = "<area>"                                   # equal to the file name
    TEXTURES = {"button_123x34.dds": fn, ...}         # path relative to gfx/interface, or "gfx/minimap/..."
    LOSSLESS = {"button_123x34.dds"}                  # optional: never DXT5
where fn(ctx, src) returns a PIL RGBA image of exactly src.size (or None to keep the vanilla file). ctx is a
generic.Ctx; ctx.generic(src) gives the generic broadcast treatment as a starting point.

generic.py is not an area module: it is the treatment for every texture no module claims, plus shared helpers.
Files whose name starts with "_" are ignored by the module discovery (use them for private helpers).
"""
from .generic import (BOARD, BOARD_ALPHA, BOARD_ALPHA_FE, D, DONE_G, FIELD, FIELD_A, HAIRLINE_ALPHA, K,  # noqa: F401
                      KEY_BLUE, KEY_BLUE_DOWN, P, RAISED, RAISED_ALPHA, SEM_G, SEM_R, SEM_Y, SLATE, TAIL_ALPHA,
                      TRACK_ALPHA, Ctx, Opts, big_plate_w, blank, flat, hairline, join_frames, paste_center,
                      per_frame, pictogram, plate, small_plate_w, split_frames, state_of, treat)

# Owner areas of tools/data/ingame_owners.json, in rule order (first match wins). "generic" owns the rest.
# topbar = topbar + HUD on the map (outliner / army groups, battle plans, unit control, theatre selector);
# rules = saved game-rule presets and the game-rule / difficulty windows.
AREAS = ("events", "topbar", "rules", "esc", "settings", "popups", "mp", "misc", "trees", "kit", "views", "generic")
