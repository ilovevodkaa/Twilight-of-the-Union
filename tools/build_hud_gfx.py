"""In-game HUD reskin for Twilight of the Union.

Writes flat replacements for vanilla HUD textures to the SAME relative paths under gfx/interface,
so the game picks them up without touching any .gfx/.gui file. Sizes and frame strips match vanilla;
layouts of complex pieces (top bar, army overview, politics panel) were measured from the vanilla files.

Usage: python tools/build_hud_gfx.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

import build_menu_gfx as g

ROOT = g.ROOT
VANILLA = Path("D:/steam/steamapps/common/Hearts of Iron IV")
OUT = ROOT / "gfx" / "interface"

INK, LINE, LINE_DIM, TAN = g.INK, g.LINE, g.LINE_DIM, g.TAN
PANEL = (22, 18, 16)
PANEL_2 = (28, 24, 21)
SLOT = (9, 8, 7)
BUTTON = (29, 25, 22)


def save(img, rel):
    g.save_dds(img, OUT / rel)


def vanilla(rel):
    return Image.open(VANILLA / "gfx" / "interface" / rel).convert("RGBA")


def rect(d, box, fill=None, outline=None):
    d.rectangle(box, fill=None if fill is None else fill + (255,) if len(fill) == 3 else fill,
                outline=None if outline is None else outline + (255,))


# ---------------------------------------------------------------- generic pieces

def window_tile(w, h, fill=PANEL, alpha=245, double=True):
    """Cornered-tile window background: flat fill, hairline frame (inner dim line if double)."""
    img = Image.new("RGBA", (w, h), fill + (alpha,))
    d = ImageDraw.Draw(img)
    rect(d, (0, 0, w - 1, h - 1), outline=LINE)
    if double:
        rect(d, (3, 3, w - 4, h - 4), outline=LINE_DIM)
    return img


def slot_box(w, h):
    """Inset value box: darker than panels, single hairline."""
    img = Image.new("RGBA", (w, h), SLOT + (240,))
    rect(ImageDraw.Draw(img), (0, 0, w - 1, h - 1), outline=LINE)
    return img


def button(w, h):
    """Single-frame button; the engine's button shader adds hover/press shading."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    rect(d, (0, 1, w - 1, h - 2), fill=BUTTON, outline=LINE)
    rect(d, (2, 3, w - 3, h - 4), outline=LINE_DIM)
    return img


def frames(w, h, n, draw):
    """Horizontal frame strip: draw(frame_w, h, index) -> image."""
    fw = w // n
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for i in range(n):
        img.alpha_composite(draw(fw, h, i), (i * fw, 0))
    return img


def toggle_button(fw, h, i, selected_frames=(1,)):
    img = button(fw, h)
    if i in selected_frames:
        d = ImageDraw.Draw(img)
        rect(d, (0, 1, fw - 1, h - 2), outline=TAN)
    return img


def header_bar(w, h):
    img = Image.new("RGBA", (w, h), PANEL_2 + (250,))
    d = ImageDraw.Draw(img)
    rect(d, (0, 0, w - 1, h - 1), outline=LINE)
    d.line((3, h - 4, w - 4, h - 4), fill=LINE_DIM + (255,))
    return img


def close_button(w, h):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    rect(d, (2, 2, w - 3, h - 3), fill=BUTTON, outline=LINE)
    m = 10
    d.line((m, m, w - m - 1, h - m - 1), fill=TAN + (255,), width=2)
    d.line((w - m - 1, m, m, h - m - 1), fill=TAN + (255,), width=2)
    return img


def arrow_button(w, h, up):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    rect(d, (0, 0, w - 1, h - 1), fill=BUTTON, outline=LINE)
    cx = w / 2
    pts = [(cx, 4), (w - 4, h - 5), (4, h - 5)] if up else [(4, 4), (w - 4, 4), (cx, h - 5)]
    d.polygon(pts, fill=TAN + (255,))
    return img


def mono_icon_frames(src, n, levels):
    """Recolour icon art frame by frame into warm monochrome; levels = highlight colour per frame."""
    fw = src.width // n
    out = Image.new("RGBA", src.size, (0, 0, 0, 0))
    for i in range(n):
        f = src.crop((i * fw, 0, (i + 1) * fw, src.height))
        alpha = f.getchannel("A")
        lum = ImageOps.autocontrast(ImageOps.grayscale(f.convert("RGB")), cutoff=1)
        col = ImageOps.colorize(lum, (12, 10, 9), levels[i]).convert("RGBA")
        col.putalpha(alpha)
        out.alpha_composite(col, (i * fw, 0))
    return out


# ---------------------------------------------------------------- top bar

def topbar_background():
    """2346x87. Measured from vanilla: flag box x5-97; upper bar y2-34 to x718; lower bar y36-78 to x680,
    45-degree bevel to (724, 36); thin strip y0-38 to x2341."""
    w, h = 2346, 87
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    sil = [(4, 0), (2341, 0), (2341, 38), (724, 38), (682, 80), (4, 80)]
    d.polygon(sil, fill=PANEL + (250,), outline=LINE + (255,))
    rect(d, (5, 3, 97, 77), fill=PANEL_2, outline=LINE)              # flag box
    rect(d, (9, 8, 93, 72), fill=SLOT, outline=LINE_DIM)             # flag slot
    rect(d, (100, 3, 718, 33), outline=LINE_DIM)                     # upper bar
    rect(d, (101, 37, 678, 76), fill=(17, 14, 12), outline=LINE_DIM)  # lower bar
    d.line((720, 3, 720, 35), fill=LINE_DIM + (255,))
    d.line((722, 35, 2340, 35), fill=LINE_DIM + (255,))
    return img


def army_overview_bg():
    """403x101 command panel. Slots measured from vanilla; laurels dropped."""
    w, h = 403, 101
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    sil = [(17, 2), (402, 2), (402, 99), (85, 99), (85, 42), (25, 42), (22, 30), (19, 16)]
    d.polygon(sil, fill=PANEL + (250,), outline=LINE + (255,))
    d.rounded_rectangle((80, 10, 278, 36), radius=6, fill=SLOT + (255,), outline=LINE + (255,))
    for cx in (142, 195, 239):
        d.ellipse((cx - 20, 46, cx + 20, 86), fill=SLOT + (255,), outline=LINE + (255,))
    d.ellipse((325 - 33, 12, 325 + 33, 78), fill=SLOT + (255,), outline=LINE + (255,))
    for cy in (20, 47, 74):
        d.ellipse((378 - 12, cy - 12, 378 + 12, cy + 12), fill=SLOT + (255,), outline=LINE + (255,))
    d.ellipse((280 - 13, 63, 280 + 13, 89), fill=SLOT + (255,), outline=LINE + (255,))
    d.rounded_rectangle((306, 80, 350, 96), radius=5, fill=SLOT + (255,), outline=LINE + (255,))
    return img


TOOLBAR_BUTTONS = ["diplomacy", "science", "production", "intelligence", "trade", "topbar_decisionview",
                   "construction", "deployment", "ledger", "staff_office"]


# ---------------------------------------------------------------- politics view

def pol_view_bg():
    """550x344. Measured: inner area 10-538 x 10-256; info panel 173-538 x 103-253 with header tab
    175-362 x 105-126 and divider at y=198; bottom row y=258-330: box 12-87, slot 90-252, emblem
    260-337 (circle r=33), right box 339-538."""
    img = window_tile(550, 344, alpha=250)
    d = ImageDraw.Draw(img)
    rect(d, (10, 10, 538, 256), fill=SLOT, outline=LINE_DIM)
    rect(d, (173, 103, 538, 253), fill=PANEL, outline=LINE)
    d.polygon([(175, 105), (352, 105), (362, 115), (362, 126), (175, 126)], fill=PANEL_2 + (255,),
              outline=LINE + (255,))
    d.line((174, 198, 537, 198), fill=LINE_DIM + (255,))
    rect(d, (12, 258, 87, 330), fill=PANEL_2, outline=LINE)
    rect(d, (90, 258, 252, 326), fill=SLOT, outline=LINE)
    rect(d, (260, 258, 337, 330), fill=PANEL_2, outline=LINE)
    d.ellipse((298 - 33, 292 - 33, 298 + 33, 292 + 33), fill=SLOT + (255,), outline=LINE + (255,))
    rect(d, (339, 258, 538, 330), fill=PANEL_2, outline=LINE)
    return img


# ---------------------------------------------------------------- build

def main():
    # Window tiles (cornered: corners keep, centre stretches; flat fills survive either way)
    for rel, size, kw in [
        ("tiles/tiled_window_1b_border.dds", 190, {}),
        ("tiles/tiled_window_1b_thin_border.dds", 190, {"double": False}),
        ("tiles/tiled_window2_1b_border.dds", 190, {"fill": PANEL_2}),
        ("tiles/tiled_window_2b_border.dds", 190, {}),
        ("tiles/tiled_plain_bg.dds", 190, {}),
        ("tiles/tiled_bg.dds", 192, {}),
        ("tiles/tiled_window.dds", 192, {}),
        ("tiles/outliner_tile.dds", 180, {"alpha": 225}),
        ("tiles/tiled_mini_dialog.dds", 26, {"alpha": 240, "double": False}),   # tooltips
        ("tiles/tiled_generic_bg_1.dds", 29, {"double": False}),
    ]:
        save(window_tile(size, size, **kw), rel)

    # Buttons (vanilla "x34" files are 36px tall except 261x34)
    for rel, w, h in [("button_123x34.dds", 123, 36), ("button_148x34.dds", 148, 36),
                      ("button_221x34.dds", 221, 36), ("button_261x34.dds", 261, 34),
                      ("government_button.dds", 172, 35)]:
        save(button(w, h), rel)
    save(frames(338, 32, 2, toggle_button), "sort_button_171x35.dds")
    save(frames(200, 29, 2, toggle_button), "sort_button_100x29_2.dds")
    save(frames(249, 29, 3, lambda fw, h, i: toggle_button(fw, h, i, selected_frames=(1, 2))),
         "sort_up_down_button_83x29.dds")

    # Value boxes and headers
    for rel, w, h in [("generic_box_smallest.dds", 70, 26), ("generic_box_96.dds", 96, 26),
                      ("generic_text_bg_108.dds", 108, 27), ("generic_bg_417.dds", 417, 29),
                      ("date_pause_button_bg.dds", 206, 28)]:
        save(slot_box(w, h), rel)
    for rel, w, h in [("header_bg.dds", 543, 41), ("main_screens_bottom.dds", 545, 54),
                      ("category_header.dds", 511, 44), ("idea_group_header.dds", 462, 55)]:
        save(header_bar(w, h), rel)
    save(close_button(32, 33), "closebutton.dds")

    # Scrollbars (used by nearly every list in the game)
    drag = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    rect(ImageDraw.Draw(drag), (2, 1, 13, 14), fill=(120, 106, 86), outline=TAN)
    save(drag, "scroll_drager.dds")
    save(arrow_button(16, 16, up=True), "scroll_up.dds")
    save(arrow_button(16, 16, up=False), "scroll_down.dds")
    track = Image.new("RGBA", (12, 12), SLOT + (220,))
    rect(ImageDraw.Draw(track), (0, 0, 11, 11), outline=LINE_DIM)
    save(track, "scroll_track.dds")
    vbg = Image.new("RGBA", (18, 156), SLOT + (200,))
    rect(ImageDraw.Draw(vbg), (4, 0, 13, 155), outline=LINE_DIM)
    save(vbg, "scrollbar_vertical_bg.dds")

    # Top bar
    save(topbar_background(), "topbar/background_extended.dds")
    save(army_overview_bg(), "topbar/armyoverview_buttons_bg.dds")
    for name in TOOLBAR_BUTTONS:
        rel = f"topbar/toolbar/{name}_button.dds"
        save(mono_icon_frames(vanilla(rel), 2, [(165, 150, 124), (236, 222, 196)]), rel)
    for name in ("army", "navy", "air"):
        rel = f"topbar/{name}overview_button.dds"
        save(mono_icon_frames(vanilla(rel), 2, [(165, 150, 124), (236, 222, 196)]), rel)

    # Politics view
    save(pol_view_bg(), "pol_view_bg.dds")


if __name__ == "__main__":
    main()
