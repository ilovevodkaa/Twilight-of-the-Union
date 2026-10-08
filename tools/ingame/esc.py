"""Area 'esc': in-game Esc menu chrome (tools/build_ingame_gfx.py area module).

The Esc menu itself is restyled in interface/ingamemenu.gui (full-screen caption layer, kit plates); the textures
here are only the vanilla-path ones the engine still draws.

  in_game_menu_dark_overlay.dds  1x1, stretched by core.gui `dark_overlay` behind the Esc menu (also texturefile2 of
                                 GFX_profile_stats_bar): the soft black scrim, board colour (9,11,16) at alpha 160.
"""
from PIL import Image

AREA = "esc"

SCRIM_ALPHA = 160                 # ~63 %: the map stays readable as a shape, the captions read on top


def dark_overlay(ctx, src):
    return Image.new("RGBA", (ctx.w, ctx.h), (*ctx.BOARD, SCRIM_ALPHA))


TEXTURES = {
    "in_game_menu_dark_overlay.dds": dark_overlay,
}
LOSSLESS = {"in_game_menu_dark_overlay.dds"}
