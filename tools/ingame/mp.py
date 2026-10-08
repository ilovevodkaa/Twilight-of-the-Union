"""Area 'mp': multiplayer chrome (tools/build_ingame_gfx.py area module).

The MP windows are restyled in interface/frontendmultiplayerview.gui, matchmaking.gui, playerlobby.gui and
hotjoin.gui (boards, kit plates, GFX_totu_mp_* from tools/build_mp_gfx.py). The textures here are the vanilla-path
ones those copies no longer draw, or still draw in a corner case: they become flat or transparent so nothing ornate
remains wherever the engine or another .gui still references them.

  clear       painted backgrounds and header art (matchmaking_browser_bg, player_lobby_header, mini/text bgs,
              sort headers, the server-ID copy button overlay)
  board       window backgrounds: hosting_bg / generic_popup_win (frontend board 0.84), hotjoin entries and the chat
              close tab (in-game board 0.90)
  raised      friend list entry
  plate       lobby_button: a slate plate with the stepped tail
  tabs        MP_matchmaking_tabs: frame 1 keyer plate, frame 2 transparent (vanilla frame 1 is the highlighted one)
  row         matchmaking_browser_list_item_bg: transparent / keyer (GFX_totu_mp_row_964 in the .gui)
Small buttons, checkboxes and flag frames of this area stay with the generic treatment.
"""
AREA = "mp"


def clear(ctx, src):
    return ctx.blank()


def board_fe(ctx, src):
    return ctx.flat(ctx.BOARD, ctx.BOARD_ALPHA_FE)


def board_ig(ctx, src):
    return ctx.flat(ctx.BOARD, ctx.BOARD_ALPHA)


def raised(ctx, src):
    return ctx.flat(ctx.RAISED, ctx.RAISED_ALPHA)


def lobby_plate(ctx, src):
    return ctx.plate(ctx.w, ctx.h, ctx.SLATE)


def tabs(ctx, src):
    fw = ctx.frame_w
    on = ctx.plate(fw, ctx.h, ctx.KEY_BLUE)
    return ctx.join([on, ctx.blank(fw, ctx.h)])


def row(ctx, src):
    fw = ctx.frame_w
    return ctx.join([ctx.blank(fw, ctx.h), ctx.flat(ctx.KEY_BLUE, 1.0, fw, ctx.h)])


TEXTURES = {
    "matchmaking_browser_bg.dds": clear,
    "player_lobby_header.dds": clear,
    "genric_mini_bg1.dds": clear,
    "genric_mini_bg2.dds": clear,
    "generic_text_bg_258.dds": clear,
    "generic_text_bg_203_transp.dds": clear,
    "sort_89.dds": clear,
    "sort_134.dds": clear,
    "sort_246.dds": clear,
    "hosting_bg.dds": board_fe,
    "generic_popup_win.dds": board_fe,
    "hotjoin_player_request_bg.dds": board_ig,
    "hotjoinrequest_bg.dds": board_ig,
    "chat_close_background.dds": board_ig,
    "matchmaking_friend_bg.dds": raised,
    "lobby_button.dds": lobby_plate,
    "mp_matchmaking_tabs.dds": tabs,
    "matchmaking_browser_list_item_bg.dds": row,
}
LOSSLESS = {"mp_matchmaking_tabs.dds", "matchmaking_browser_list_item_bg.dds", "lobby_button.dds"}
