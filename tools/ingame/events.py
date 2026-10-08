"""Area "events": the event windows (interface/eventwindow.gui) as dark broadcast boards.

Plan: scratchpad ui_map/reports/hero.md section 2.2 ("Recommended: dark boards"). The .gui copy
(interface/eventwindow.gui) switches the texts to light fonts (Title hoi_24header P, Description hoi_16mbs P), so
every surface here is the dark board; the Title sits on a keyer band baked into the top window.

Geometry the .gui relies on (keep in sync with interface/eventwindow.gui):
  top window 581x121   board; keyer band rows BAND_Y0..BAND_Y1-1, solid x 14..555, tail 556..567;
                       Title box y 54, maxHeight 48, vertical_alignment centre (centre 78 = band centre)
  midsection 580x66    uniform board (corneredTile 290/16: only a uniform texture stretches cleanly)
  bottom 581x206 / 59  uniform board; column 580 transparent, like the 580 px midsection
  option entry 352x48  SLATE plate rows 0..39 (Name centres on y 20), solid 0..339, tail 340..351, rows 40..47 clear
"""
from ingame import generic as g

AREA = "events"

A = 0.92                    # board alpha of the event windows (text over the map: a little above BOARD_ALPHA)
BAND_Y0, BAND_Y1 = 50, 106  # keyer title band (56 px: two 24 px lines of hoi_24header + 4 px air)
BAND_X0, BAND_SOLID, BAND_TAIL = 14, 556, 12
WIN_W = 580                 # width of the midsection; wider textures leave their extra columns transparent


def _board(ctx, w=None, h=None, cols=WIN_W):
    w, h = w or ctx.w, h or ctx.h
    img = g.blank(w, h)
    img.paste(g.BOARD + (round(255 * A),), (0, 0, min(w, cols), h))
    return img


def top_win(ctx, src):
    img = _board(ctx)
    band = g.plate(BAND_SOLID - BAND_X0 + BAND_TAIL, BAND_Y1 - BAND_Y0, rgb=g.KEY_BLUE, tail=BAND_TAIL)
    img.alpha_composite(band, (BAND_X0, BAND_Y0))
    return img


def board(ctx, src):
    return _board(ctx)


def board_full(ctx, src):
    return _board(ctx, cols=ctx.w)


def option_entry(ctx, src):
    img = ctx.blank()
    img.alpha_composite(g.plate(352, 40, rgb=g.SLATE, tail=12), (0, 0))
    return img


def clear(ctx, src):
    return ctx.blank()


def minimize(ctx, src):
    img = ctx.blank()
    bar = g.pictogram(["######", "######"], cell=2)        # 12x4 P bar, K copy at +2,+2
    # centre the ink (not ink + drop) on the 32x33 button
    img.alpha_composite(bar, ((ctx.w - 12) // 2, (ctx.h - 4) // 2))
    return img


def news_overlay(ctx, src):
    """CRT look over every news picture (397x153 at the overlay's origin): every 3rd row K at 12 %, soft corner
    vignette. The 2 px the overlay is larger than the picture stay transparent."""
    import numpy as np
    w, h = ctx.w, ctx.h
    pw, ph = 397, 153
    a = np.zeros((h, w), np.float32)
    a[0:ph:3, :pw] = 0.12
    yy, xx = np.mgrid[0:ph, 0:pw].astype(np.float32)
    nx = (xx - (pw - 1) / 2) / ((pw - 1) / 2)
    ny = (yy - (ph - 1) / 2) / ((ph - 1) / 2)
    r = np.sqrt((nx * 0.85) ** 2 + ny ** 2)
    vig = np.clip((r - 0.75) / 0.6, 0, 1) ** 1.6 * 0.42
    sub = a[:ph, :pw]
    a[:ph, :pw] = 1 - (1 - sub) * (1 - vig)
    out = np.zeros((h, w, 4), np.uint8)
    out[..., 3] = np.round(a * 255).astype(np.uint8)
    return g.to_image(out)


def operative_bg(ctx, src):
    """24 frames of 528x596 (80 fps, looping = no, play_on_show = no): every frame is the full board. Whether and
    when the engine plays the strip is unknown (the renderer shows frame 0), so no frame may be empty."""
    fw, h = ctx.frame_w, ctx.h
    return ctx.join([g.flat(fw, h, g.BOARD, A) for _ in range(ctx.frames)])


TEXTURES = {
    "event_report_top_win.dds": top_win,
    "event_report_tileable_midsection.dds": board,
    "event_report_bottom_win.dds": board,
    "event_report_bottom_win_2.dds": board,
    "event_option_entry.dds": option_entry,
    "event_pic_clip.dds": clear,
    "events/clip.dds": clear,
    "event_button_minimize.dds": minimize,
    "event_leader_frame.dds": clear,
    "event_news_bg.dds": board_full,
    "event_news_pic_overlay.dds": news_overlay,
    "events/event_operative_bg.dds": operative_bg,
}

# plates and pictograms keep exact keyer / slate / P pixels
LOSSLESS = {"event_report_top_win.dds", "event_option_entry.dds", "event_button_minimize.dds"}
