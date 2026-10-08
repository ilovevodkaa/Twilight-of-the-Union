"""Area 'misc': vanilla textures of the achievements, subscription overlay and career-profile windows.

The restyled .gui files (achievements.gui, musicplayer.gui, subscription_message_view.gui, ...) no longer show most of
this art, but the textures stay reachable (career profile from Esc, other mods' or DLC .gui files), so they are made
flat or transparent at the vanilla size: backgrounds become the board, inner panels the raised tone, header and
footer bars, paper rows and painted frames become transparent. Buttons, checkboxes, scrollbars and flag overlays are
left to the generic treatment (regrade / keep). Music player art is under topbar/musicplayer/** (area 'topbar').
"""
from ingame import generic as g  # noqa: F401  (palette and helpers through ctx)

AREA = "misc"


def board(ctx, src):
    """Flat board at the in-game alpha over the whole texture (backgrounds, 9-slice tiles)."""
    return ctx.flat(ctx.BOARD, ctx.BOARD_ALPHA)


def board_fe(ctx, src):
    """Flat board at the frontend alpha (subscription overlay band)."""
    return ctx.flat(ctx.BOARD, ctx.BOARD_ALPHA_FE)


def raised(ctx, src):
    """Raised sub-panel tone over every frame (medal / ribbon slots, stats panels)."""
    return ctx.flat(ctx.RAISED, ctx.RAISED_ALPHA)


def field(ctx, src):
    return ctx.flat(ctx.FIELD, ctx.FIELD_A)


def clear(ctx, src):
    """Fully transparent: header / footer bars, paper rows, painted frames and overlays."""
    return ctx.blank()


def board_tint(ctx, src):
    """Keep the vanilla alpha silhouette (the promo band's diagonal cuts), colour = board."""
    out = src.convert("RGBA").copy()
    r, g_, b, a = out.split()
    flat = ctx.flat(ctx.BOARD, 1.0)
    flat.putalpha(a)
    return flat


def keyer_frame(ctx, src):
    """Selection frame (corneredTile): a 2 px keyer outline, transparent inside."""
    img = ctx.blank()
    px = img.load()
    k = ctx.KEY_BLUE + (255,)
    for x in range(ctx.w):
        for y in (0, 1, ctx.h - 2, ctx.h - 1):
            px[x, y] = k
    for y in range(ctx.h):
        for x in (0, 1, ctx.w - 2, ctx.w - 1):
            px[x, y] = k
    return img


TEXTURES = {
    # achievements.gui
    "achievements_top_bar.dds": clear,
    "achievements_bottom_bar.dds": clear,
    "achievement_entry_bg.dds": clear,
    # subscription_message_view.gui band
    "sub/startup/subscription_startup_bg_tile.dds": board_fe,
    "sub/startup/subscription_startup_bg_overlay.dds": board_tint,   # not in the manifest: band chrome over the promos
    # career profile / playthrough overview (career_profile/*.gui)
    "career_profile/career_profile_bg.dds": board,
    "career_profile/career_profile_bg_default.dds": board,
    "career_profile/career_bg_flyout.dds": board,
    "career_profile/playthrough_stats_bg.dds": board,
    "career_profile/playthrough_stats_bg_default.dds": board,
    "career_profile/social_bg.dds": board,
    "career_profile/tiled_bg.dds": board,
    "career_profile/tiled_career_profile_brown_60.dds": board,
    "career_profile/tiled_bg_dropdown.dds": board,
    "career_profile/tiled_stats_bg.dds": raised,
    "career_profile/tiled_stats_bg_dark.dds": raised,
    "career_profile/tiled_transparent_bg.dds": raised,
    "career_profile/tiled_transparent_bg_light.dds": field,
    "career_profile/ribbon_bg.dds": raised,
    "career_profile/profile_picture_bg_default_locked.dds": raised,
    "career_profile/tiled_war_bg_overlay.dds": clear,
    "career_profile/widget_frame_medal.dds": clear,
    "career_profile/widget_frame_ribbon.dds": clear,
    "career_profile/tiled_frame_selected.dds": keyer_frame,
}

LOSSLESS = {"career_profile/tiled_frame_selected.dds"}
