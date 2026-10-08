"""Area 'settings': the textures only interface/settings.gui uses.

The live Options window (menu_settings_ingame) no longer draws any of them: interface/settings.gui points it at the
kit (GFX_totu_board_ig, GFX_totu_toggle_r_s_*, GFX_totu_step_*, GFX_totu_slider_*, GFX_totu_checkbox) and moves the
tab art to -9000. These flat versions only make sure nothing ornate shows if the legacy menu_settings window (kept
vanilla) or a stray sprite reference ever draws them.
"""
from ingame import generic as g

AREA = "settings"

# bold 5x7-cell chevrons at 2 px cells (as the kit's chevron_left / chevron_right)
CHEVRON_LEFT = ["...##", "..##.", ".##..", "##...", ".##..", "..##.", "...##"]
CHEVRON_RIGHT = [r[::-1] for r in CHEVRON_LEFT]


def popup_bg(ctx, src):
    # GFX_settings_popup_bg (480x527 window art): the in-game board, flat
    return ctx.flat(ctx.BOARD, ctx.BOARD_ALPHA)


def clear_tile(ctx, src):
    # GFX_settings_tabs_bottom / GFX_fullborder_tiled (190x190 frame, corneredTile b64, alwaystransparent): no frames
    return ctx.blank()


def tab_small(ctx, src):
    # GFX_settings_ingame_tab, 2 x 105x37, frame set by the engine; frame 1 = active (as GFX_totu_toggle_r_s_*):
    # a 24 px keyer plate with the small tail on the frame's lower part; frame 2 transparent
    fw, h = ctx.frame_w, ctx.h
    on = ctx.blank(fw, h)
    on.alpha_composite(g.plate(fw - 2, 24, ctx.KEY_BLUE), (0, h - 24 - 6))
    return ctx.join([on, ctx.blank(fw, h)])


def tab_legacy(ctx, src):
    # GFX_settings_tab (legacy window, 2 x 32x20, buttonstate.lua, no text): keyer block on / slate block off
    fw, h = ctx.frame_w, ctx.h
    return ctx.join([g.plate(fw, h, ctx.KEY_BLUE, tail=0), g.plate(fw, h, ctx.SLATE, tail=0)])


def plain_button(ctx, src):
    # button_type_2 (80x32, one frame, buttonstate.lua): slate plate with the stepped tail
    return ctx.plate(ctx.w, ctx.h, ctx.SLATE)


def _stepper(rows):
    def fn(ctx, src):
        # button_left / button_right (23x21, one frame, buttonstate.lua brightens it): P chevron with the K drop,
        # no plate (as GFX_totu_step_left / _right)
        img = ctx.blank()
        return g.paste_center(img, g.pictogram(rows, 2, ctx.P))
    return fn


def slider_knob(ctx, src):
    # yearslider_slider2 (4 x 16x16, no effect): an 8 px block, P / keyer with a P stripe / pressed / D at 30 %
    fw, h = ctx.frame_w, ctx.h
    x0 = (fw - 8) // 2

    def block(rgb, alpha=1.0, stripe=False):
        fr = ctx.blank(fw, h)
        fr.paste(tuple(rgb) + (round(255 * alpha),), (x0, 0, x0 + 8, h))
        if stripe:
            fr.paste(tuple(ctx.P) + (255,), (x0 + 3, 0, x0 + 5, h))
        return fr

    return ctx.join([block(ctx.P), block(ctx.KEY_BLUE, stripe=True), block(ctx.KEY_BLUE_DOWN, stripe=True),
                     block(ctx.D, 0.30)])


TEXTURES = {
    "settings_popup_bg.dds": popup_bg,
    "fullborder_tiled.dds": clear_tile,
    "tab_small_110.dds": tab_small,
    "tab_settings.dds": tab_legacy,
    "button_type_2.dds": plain_button,
    "button_left.dds": _stepper(CHEVRON_LEFT),
    "button_right.dds": _stepper(CHEVRON_RIGHT),
    "scrollbar_slider_2.dds": slider_knob,
}
LOSSLESS = set(TEXTURES)     # flat colour, pixel chevrons and exact keyer: never DXT5
