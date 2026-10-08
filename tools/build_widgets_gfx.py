"""Builds the shared widget kit of the broadcast restyle (design "broadcast": late-Soviet TV captions).

Usage:
    python tools/build_widgets_gfx.py            # textures, interface/totu_widgets.gfx / .gui, previews
    python tools/build_widgets_gfx.py --no-preview

Writes
    gfx/interface/totu/widgets/*.dds    uncompressed A8R8G8B8, no mipmaps (exact keyer colour, 2 px edges)
    interface/totu_widgets.gfx          every GFX_totu_* sprite below (plate bank, boards, rows, buttons, sliders,
                                        scrollbar parts, the save entry)
    interface/totu_widgets.gui          scrollbar types: totu_vertical_slider, totu_horizontal_slider
                                        (extendedScrollbarType), totu_listbox_slider, totu_text_slider,
                                        totu_value_slider (scrollbarType)
    tools/preview/widgets.png           every widget frame at 1x and 3x on the in-game board
    tools/preview/widgets_bank.png      the whole plate bank at 1x
    tools/preview/widgets_mock.png      a mock in-game dialog assembled from the kit (1x and a 2x crop)
Idempotent: files whose bytes would not change are not rewritten; textures in gfx/interface/totu/widgets that this
script no longer makes are removed. Checks, all on the in-memory text before anything is written: every sprite
declared exactly once, every referenced texture made, frame strips divide evenly, no sprite / gui type name
collides with the vanilla game (incl. DLC) or another mod interface file, the bank equals the menu's plates. After
the DDS writes: every texture exists with an uncompressed, mipmap-free header; the .gfx / .gui are written last.
The palette, plate math and drawing primitives live in tools/totu_broadcast.py; usage notes: docs/ui_kit.md.
"""
import argparse
import re
import sys
import time
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import totu_broadcast as tb  # noqa: E402

OUT = tb.WIDGETS_TEX
TEX = "gfx/interface/totu/widgets"
GFX = tb.INTERFACE / "totu_widgets.gfx"
GUI = tb.INTERFACE / "totu_widgets.gui"
FIELD_WIDTHS = (96, 150, 190, 216, 260, 300, 376, 416, 456, 600)     # GFX_totu_field_<w> / GFX_totu_hairline_<w>
SAVE_ENTRY = (376, 48)
BTN = 20                    # square buttons: expand, dropdown, free-standing steppers, plus / minus
STEP4 = 16                  # 4-frame slider end buttons: as tall as the 16 px value slider (knob, track)
CLOSE = 24
KNOB = (12, 16)             # value-slider knob frame
SCROLL_W = 8                # scrollbar knob / track width
SCROLL_KNOB_L = 24          # scrollbar knob length
ARROW = 12                  # scrollbar arrows (ink placed so the K drop fits: the column axis is x 5|6 -> see .gui)

textures = {}               # file name -> image
sprites = []                # (group, name, block)
shown = []                  # (group, name, image, frames) for the previews


def texture(fname, img):
    if fname in textures:
        assert textures[fname] is img, f"{fname} made twice"
    textures[fname] = img
    return f"{TEX}/{fname}"


def sprite(group, name, img, fname, kind="spriteType", frames=1, effect=None, size=None, border=None, tiling=None,
           comment=None, show=True):
    assert all(n != name for _, n, _ in sprites), f"{name} declared twice"
    tex = texture(fname, img)
    sprites.append((group, name, tb.sprite_block(name, tex, kind, frames, effect, size, border, tiling, comment)))
    if show:
        shown.append((group, name, img, frames, size, border, tiling))


# ---------------------------------------------------------------- the textures
def build_bank():
    for kind, (size, n_max, frame_cols, stype) in tb.BANK.items():
        h = tb.PLATE_H if size == "big" else tb.SMALL_PLATE_H
        for n in range(1, n_max + 1):
            w = tb.bank_width(n, size)
            name = tb.bank_sprite(kind, n)
            img = tb.plate_frames(w, h, frame_cols)
            effect = tb.EFFECT_ONLYDISABLE
            sprite(f"bank_{kind}", name, img, f"{name[len('GFX_totu_'):]}.dds", stype, len(frame_cols), effect,
                   comment=f"{n} glyph{'s' if n > 1 else ''}", show=False)


def build_surfaces():
    tile = dict(kind="corneredTileSpriteType", size=(16, 16), border=(0, 0), tiling=True, effect=tb.EFFECT_NODOWN)
    sprite("surface", "GFX_totu_board_ig", tb.flat(16, 16, tb.BOARD_RGB, tb.BOARD_ALPHA_IG), "board_ig.dds",
           comment="in-game board, BOARD_RGB at 90 %", **tile)
    sprite("surface", "GFX_totu_board_solid", tb.flat(16, 16, tb.BOARD_RGB), "board_solid.dds",
           comment="opaque board (dropdown lists, popups over busy art)", **tile)
    sprite("surface", "GFX_totu_raised", tb.flat(16, 16, tb.RAISED_RGB, tb.RAISED_ALPHA), "raised.dds",
           comment="raised sub-panel on a board", **tile)
    field = tb.flat(16, 16, tb.D, tb.FIELD_ALPHA)
    sprite("surface", "GFX_totu_field_tile", field, "field_tile.dds", comment="field, D at 14 % (container background)",
           **tile)
    for w in FIELD_WIDTHS:
        sprite("surface", f"GFX_totu_field_{w}", field, "field_tile.dds", "corneredTileSpriteType", size=(w, 32),
               border=(0, 0), tiling=True, effect=tb.EFFECT_NODOWN, comment=f"iconType field {w}x32", show=w == 300)
    hair = tb.flat(16, 16, tb.D, tb.HAIRLINE_ALPHA)
    sprite("surface", "GFX_totu_hairline", hair, "hairline.dds", "corneredTileSpriteType", size=(16, 1),
           border=(0, 0), tiling=True, comment="separator, D at 22 %: container background, height 1-2")
    for w in FIELD_WIDTHS:
        sprite("surface", f"GFX_totu_hairline_{w}", hair, "hairline.dds", "corneredTileSpriteType", size=(w, 1),
               border=(0, 0), tiling=True, comment=f"iconType separator {w}x1", show=False)
    sprite("surface", "GFX_totu_row_hl", tb.flat(16, 16, tb.KEY_BLUE), "row_hl.dds",
           comment="selected list row, keyer at 100 %", **tile)
    sprite("surface", "GFX_totu_row_hover", tb.flat(16, 16, tb.D, tb.HOVER_ALPHA), "row_hover.dds",
           comment="list row hover, D at 8 %", **tile)
    # stretchable plates: the stepped tail is the corneredTile's right border
    for name, rgb in (("keyer", tb.KEY_BLUE), ("slate", tb.SLATE_RGB)):
        sprite("surface", f"GFX_totu_{name}_tile", tb.plate(48, 16, rgb, tb.TAIL), f"{name}_tile.dds",
               "corneredTileSpriteType", size=(160, 40), border=(tb.TAIL, 0), tiling=True, effect=tb.EFFECT_NODOWN,
               comment=f"stretchable {name} plate with the 12 px tail")
        sprite("surface", f"GFX_totu_{name}_tile_s", tb.plate(24, 16, rgb, tb.SMALL_TAIL), f"{name}_tile_s.dds",
               "corneredTileSpriteType", size=(118, 24), border=(tb.SMALL_TAIL, 0), tiling=True,
               effect=tb.EFFECT_NODOWN, comment=f"stretchable {name} plate with the 6 px tail")


def three(w, h, picto, colour=tb.P, dy=0):
    """transparent / keyer / pressed frames with the pictogram centred."""
    return [tb.button_frame(w, h, picto, None, colour=colour, dy=dy),
            tb.button_frame(w, h, picto, tb.KEY_BLUE, colour=colour, dy=dy),
            tb.button_frame(w, h, picto, tb.KEY_BLUE_DOWN, colour=colour, dy=dy)]


def disabled(w, h, picto):
    return tb.button_frame(w, h, picto, None, colour=tb.D, k_edge=False, alpha=tb.DISABLED_ALPHA)


def build_buttons():
    od = tb.EFFECT_ONLYDISABLE
    sprite("button", "GFX_totu_close", tb.frames(three(CLOSE, CLOSE, "close")), "close.dds", frames=3, effect=od,
           comment="24x24 close / delete: transparent / keyer / pressed")
    sprite("button", "GFX_totu_expand",
           tb.frames(tb.button_frame(BTN, BTN, "chevron_down"), tb.button_frame(BTN, BTN, "chevron_right")),
           "expand.dds", frames=2, comment="20x20 like GFX_expand_collapse_sideways: expanded v / collapsed >")
    sprite("button", "GFX_totu_dropdown", tb.frames(three(BTN, BTN, "chevron_down")), "dropdown.dds", frames=3,
           effect=od, comment="20x20 dropdown expand button")
    for side in ("left", "right"):
        f3 = three(BTN, BTN, f"chevron_{side}")
        sprite("button", f"GFX_totu_step_{side}", tb.frames(f3), f"step_{side}.dds", frames=3, effect=od,
               comment="20x20 stepper (replaces button_left / button_right)")
        f4 = three(STEP4, STEP4, f"chevron_{side}_s") + [disabled(STEP4, STEP4, f"chevron_{side}_s")]
        sprite("button", f"GFX_totu_step_{side}_4f", tb.frames(f4), f"step_{side}_4f.dds", frames=4,
               effect=tb.EFFECT_BUTTONSTATE,
               comment="16x16, 4 frames like yearslider_leftbutton: value slider end buttons")
    for p in ("plus", "minus"):
        sprite("button", f"GFX_totu_{p}", tb.frames(three(BTN, BTN, p)), f"{p}.dds", frames=3, effect=od,
               comment=f"20x20 {p}")


def knob_frame(fill, stripe=None, full=False, alpha=1.0):
    w, h = KNOB
    img = tb.transparent(w, h)
    bw = w if full else 8
    img.alpha_composite(tb.flat(bw, h, fill, alpha), ((w - bw) // 2, 0))
    if stripe:
        img.alpha_composite(tb.flat(2, h, stripe), (w // 2 - 1, 0))
    return img


def build_sliders():
    knob = tb.frames(knob_frame(tb.P), knob_frame(tb.KEY_BLUE, tb.P, True), knob_frame(tb.KEY_BLUE_DOWN, tb.P, True),
                     knob_frame(tb.D, alpha=tb.DISABLED_ALPHA))
    sprite("slider", "GFX_totu_slider_knob", knob, "slider_knob.dds", frames=4,
           comment="value slider knob 12x16, 4 frames like yearslider_slider2")
    track = tb.transparent(16, 16)
    track.alpha_composite(tb.flat(16, 2, tb.D, tb.SLIDER_LINE_ALPHA), (0, 7))
    sprite("slider", "GFX_totu_slider_track", track, "slider_track.dds", "corneredTileSpriteType", size=(276, 16),
           border=(0, 0), tiling=True, comment="value slider track: 2 px D line at 35 %")
    # scrollbars: the knob is a plain 3-frame spriteType like every vanilla thumb (GFX_scroll_drager)
    for name, (w, h) in (("GFX_totu_scroll_knob", (SCROLL_W, SCROLL_KNOB_L)),
                         ("GFX_totu_scroll_knob_h", (SCROLL_KNOB_L, SCROLL_W))):
        knob = tb.frames(tb.flat(w, h, tb.P, tb.SCROLL_KNOB_ALPHA), tb.flat(w, h, tb.KEY_BLUE),
                         tb.flat(w, h, tb.KEY_BLUE_DOWN))
        sprite("scroll", name, knob, f"{name[len('GFX_totu_'):]}.dds", frames=3, effect=tb.EFFECT_ONLYDISABLE,
               comment=f"{w}x{h}: P at 70 % / keyer / pressed")
    tv = tb.transparent(SCROLL_W, SCROLL_W)
    tv.alpha_composite(tb.flat(2, SCROLL_W, tb.D, tb.TRACK_ALPHA), (SCROLL_W // 2 - 1, 0))
    sprite("scroll", "GFX_totu_scroll_track", tv, "scroll_track.dds", "corneredTileSpriteType",
           size=(SCROLL_W, SCROLL_W), border=(0, 0), tiling=True, comment="2 px D line at 18 %, centred in 8")
    th = tb.transparent(SCROLL_W, SCROLL_W)
    th.alpha_composite(tb.flat(SCROLL_W, 2, tb.D, tb.TRACK_ALPHA), (0, SCROLL_W // 2 - 1))
    sprite("scroll", "GFX_totu_scroll_track_h", th, "scroll_track_h.dds", "corneredTileSpriteType",
           size=(SCROLL_W, SCROLL_W), border=(0, 0), tiling=True, comment="horizontal track")
    for name, picto in (("up", "triangle_up"), ("down", "triangle_down"), ("left", "triangle_left"),
                        ("right", "triangle_right")):
        sprite("scroll", f"GFX_totu_scroll_{name}", tb.button_frame(ARROW, ARROW, picto),
               f"scroll_{name}.dds", comment="12x12 pixel triangle, P with the K drop (ink x/y 0..9)")


def build_entries():
    w, h = SAVE_ENTRY
    sprite("entry", "GFX_totu_save_entry", tb.frames(tb.transparent(w, h), tb.plate(w, h, tb.KEY_BLUE, tb.TAIL)),
           "save_entry.dds", frames=2, comment="376x48 savegame_item: normal transparent / selected keyer plate")


# ---------------------------------------------------------------- .gfx / .gui text
GFX_HEAD = [
    "Twilight of the Union: shared widget kit of the broadcast restyle (frontend menus and the in-game UI).",
    "Generated by tools/build_widgets_gfx.py from tools/totu_broadcast.py; edit the scripts, not this file or the",
    "textures (gfx/interface/totu/widgets). Usage: docs/ui_kit.md.",
    "Plate bank: GFX_totu_plate_<w> (40 px, w = 24 n + 40, n = 1..18 glyphs), GFX_totu_plate_s_<w> (24 px,",
    "w = 12 n + 22, n = 1..40), slate variants GFX_totu_slate_<w> / GFX_totu_slate_s_<w> (idle-visible),",
    "checkboxType tabs GFX_totu_tab_s_<w>, 2-frame toggles GFX_totu_toggle_s_<w> (off / on) and",
    "GFX_totu_toggle_r_s_<w> (frame 1 on, frame 2 off; n = 1..24).",
    "n = the longer RU / EN label in 5-column glyphs: tools/totu_broadcast.py plate_sprite(('...', '...')).",
    "Frames: 1 normal, 2 hover (keyer blue), 3 pressed; buttonText in totu_button / totu_button_small.",
]
GROUP_TITLES = {
    "bank_plate": "Plate bank: 40 px keyer plates, transparent / keyer / pressed (buttonFont totu_button)",
    "bank_plate_s": "Plate bank: 24 px keyer plates (buttonFont totu_button_small)",
    "bank_slate": "Plate bank: 40 px slate plates, slate / keyer / pressed (visible when idle)",
    "bank_slate_s": "Plate bank: 24 px slate plates",
    "bank_tab_s": "Plate bank: checkboxType tabs, off transparent / on keyer / disabled transparent",
    "bank_toggle_s": "Plate bank: 2-frame toggles, off transparent / on keyer",
    "bank_toggle_r_s": "Plate bank: 2-frame toggles reversed, keyer / transparent (engine-set tabs, frame 1 active)",
    "surface": "Surfaces: boards, fields, hairlines, list rows (corneredTile, borderSize 0) and stretchable plates "
               "(corneredTile, borderSize = the tail)",
    "button": "Buttons with pixel pictograms (P with the K drop at +2,+2)",
    "slider": "Value slider parts (scrollbarType totu_value_slider in interface/totu_widgets.gui)",
    "scroll": "Scrollbar parts (totu_vertical_slider, totu_horizontal_slider, totu_listbox_slider, totu_text_slider)",
    "entry": "List entries",
}


def gfx_text():
    blocks, last = [], None
    for group, _, block in sprites:
        if group != last:
            block = f"\t# {GROUP_TITLES[group]}\n" + block
            last = group
        blocks.append(block)
    return tb.gfx_file(blocks, GFX_HEAD)


GUI_TEXT = """# Twilight of the Union: scrollbar types of the broadcast widget kit (generated by tools/build_widgets_gfx.py;
# edit the script). Sprites in interface/totu_widgets.gfx, usage in docs/ui_kit.md.
# Each type mirrors the vanilla one named in its comment (interface/core.gui, settings.gui of 1.19.3): same element
# names and fields, broadcast parts, no background art. Child positions follow the vanilla convention (slider
# relative to the track; the increase button anchored at the far corner, negative offset = its size).
#   containerWindowType: verticalScrollbar = "totu_vertical_slider" / horizontalScrollbar = "totu_horizontal_slider"
#   listboxType: scrollbartype = "totu_listbox_slider"; long text boxes: scrollbartype = "totu_text_slider"
#   totu_value_slider: copy its body into an inline scrollbarType (settings.gui sliders are looked up by their own
#   name, e.g. mastervolume_slider) and set name, size, position, maxValue, stepSize there.

guiTypes = {
	# mirrors right_vertical_slider: 12 px wide, no background. One axis at x 5|6 of the 12 px column: arrows (ink
	# x 0..9 + K drop to 11), track at x 1 (2 px line at x 4..5), knob 8x24 at the track's x (vanilla: the slider is
	# placed relative to the track); knob frames P at 70 % / keyer / pressed
	extendedScrollbarType = {
		name = "totu_vertical_slider"
		position = { x = -5 y = 0 }
		size = { width = 12 height = 12 }
		startValue = 0
		orientation = upper_right
		origo = upper_right
		smooth_scrolling = 0.25

		slider = {
			name = "Slider"
			quadTextureSprite = "GFX_totu_scroll_knob"
			position = { x = 0 y = 0 }
		}

		track = {
			name = "Track"
			quadTextureSprite = "GFX_totu_scroll_track"
			position = { x = 1 y = 0 }
			alwaystransparent = yes
		}

		decreaseButton = {
			name = "Decrease"
			quadTextureSprite = "GFX_totu_scroll_up"
			position = { x = 0 y = 0 }
		}

		increaseButton = {
			name = "Increase"
			quadTextureSprite = "GFX_totu_scroll_down"
			position = { x = -12 y = -12 }
		}
	}

	# mirrors bottom_horizontal_slider; the same column geometry turned (axis at y 5|6)
	extendedScrollbarType = {
		name = "totu_horizontal_slider"
		position = { x = 0 y = -2 }
		size = { width = 12 height = 12 }
		tileSize = { width = 12 height = 12 }
		maxValue = 1
		minValue = 0
		stepSize = 0.01
		startValue = 0
		horizontal = yes
		orientation = lower_left
		origo = lower_left

		slider = {
			name = "Slider"
			quadTextureSprite = "GFX_totu_scroll_knob_h"
			position = { x = 0 y = 0 }
		}

		track = {
			name = "Track"
			quadTextureSprite = "GFX_totu_scroll_track_h"
			position = { x = 0 y = 1 }
			alwaystransparent = yes
		}

		decreaseButton = {
			name = "Decrease"
			quadTextureSprite = "GFX_totu_scroll_left"
			position = { x = 0 y = 0 }
		}

		increaseButton = {
			name = "Increase"
			quadTextureSprite = "GFX_totu_scroll_right"
			position = { x = -12 y = -12 }
		}
	}

	# mirrors standardlistbox_slider (listboxType scrollbartype); vanilla positions kept
	scrollbarType = {
		name = "totu_listbox_slider"
		slider = "listboxSliderButton"
		track = "listboxTrackButton"
		leftbutton = "downButton"
		rightbutton = "upButton"
		size = { x = 12 y = 12 }
		position = { x = -6 y = -6 }
		priority = 100
		borderSize = { x = 12 y = 12 }
		maxValue = 1
		minValue = 0
		stepSize = 0.01
		scroll_speed = 40
		startValue = 0
		horizontal = 0

		guiButtonType = {
			name = "listboxSliderButton"
			quadTextureSprite = "GFX_totu_scroll_knob"
			position = { x = -12 y = 0 }
		}

		guiButtonType = {
			name = "listboxTrackButton"
			quadTextureSprite = "GFX_totu_scroll_track"
			position = { x = 12 y = 12 }
		}

		guiButtonType = {
			parent = "listboxSliderButton"
			name = "upButton"
			quadTextureSprite = "GFX_totu_scroll_up"
			position = { x = 0 y = 0 }
		}

		guiButtonType = {
			parent = "listboxSliderButton"
			name = "downButton"
			quadTextureSprite = "GFX_totu_scroll_down"
			position = { x = 0 y = 120 }
		}
	}

	# mirrors standardtext_slider (scrolling text boxes, e.g. popup descriptions)
	scrollbarType = {
		name = "totu_text_slider"
		slider = "listboxSliderButton"
		track = "listboxTrackButton"
		leftbutton = "downButton"
		rightbutton = "upButton"
		size = { x = 12 y = 12 }
		position = { x = 0 y = 0 }
		priority = 100
		borderSize = { x = 12 y = 12 }
		maxValue = 1
		minValue = 0
		stepSize = 8
		startValue = 0
		horizontal = 0

		guiButtonType = {
			name = "listboxSliderButton"
			quadTextureSprite = "GFX_totu_scroll_knob"
			position = { x = 0 y = 0 }
		}

		guiButtonType = {
			name = "listboxTrackButton"
			quadTextureSprite = "GFX_totu_scroll_track"
			position = { x = 12 y = 12 }
		}

		guiButtonType = {
			parent = "listboxSliderButton"
			name = "upButton"
			quadTextureSprite = "GFX_totu_scroll_up"
			position = { x = 0 y = 0 }
		}

		guiButtonType = {
			parent = "listboxSliderButton"
			name = "downButton"
			quadTextureSprite = "GFX_totu_scroll_down"
			position = { x = 0 y = 120 }
		}
	}

	# mirrors the horizontal sliders of settings.gui (e.g. mastervolume_slider): knob 12x16 (4 frames), 2 px track,
	# 16x16 step buttons (4 frames like yearslider_leftbutton / rightbutton; borderSize 16 = their width): every
	# part is 16 px tall, so knob, line and chevrons share one centre line whether or not the engine centres
	# them. Copy the body for each slider.
	scrollbarType = {
		name = "totu_value_slider"
		slider = "landslider_SliderButton"
		track = "landslider_TrackButton"
		leftbutton = "landslider_upButton"
		rightbutton = "landslider_downButton"
		size = { x = 276 y = 16 }
		position = { x = 0 y = 0 }
		priority = 100
		borderSize = { x = 16 y = 16 }
		maxValue = 100
		minValue = 0
		stepSize = 1
		startValue = 20
		horizontal = 1

		guiButtonType = {
			name = "landslider_SliderButton"
			quadTextureSprite = "GFX_totu_slider_knob"
			position = { x = 0 y = 0 }
		}

		guiButtonType = {
			name = "landslider_TrackButton"
			quadTextureSprite = "GFX_totu_slider_track"
			position = { x = 0 y = 20 }
		}

		guiButtonType = {
			name = "landslider_upButton"
			quadTextureSprite = "GFX_totu_step_left_4f"
			position = { x = 0 y = 0 }
			clicksound = click_scroll
		}

		guiButtonType = {
			name = "landslider_downButton"
			quadTextureSprite = "GFX_totu_step_right_4f"
			position = { x = 0 y = 120 }
			clicksound = click_scroll
		}
	}
}
"""
GUI_TYPES = ("totu_vertical_slider", "totu_horizontal_slider", "totu_listbox_slider", "totu_text_slider",
             "totu_value_slider")


# ---------------------------------------------------------------- checks
def check(gfx, gui):
    """Checks on the in-memory .gfx / .gui text and textures (run before anything is written)."""
    names = [n for _, n, _ in sprites]
    assert len(names) == len(set(names))
    declared = tb.declared_names(gfx)
    for n in names:
        assert declared.count(n) == 1, f"{n} declared {declared.count(n)} times"
    assert set(declared) == set(names), set(declared) ^ set(names)
    refs = set(re.findall(r'textureFile\s*=\s*"([^"]+)"', gfx))
    assert refs == {f"{TEX}/{t}" for t in textures}, refs ^ {f"{TEX}/{t}" for t in textures}
    for _, name, block in sprites:              # frame strips divide evenly
        fname = re.search(r'textureFile = "[^"]*/([^"/]+)"', block).group(1)
        m = re.search(r"noOfFrames = (\d+)", block)
        assert textures[fname].width % (int(m.group(1)) if m else 1) == 0, (name, textures[fname].size)
    other = tb.existing_names("*.gfx", exclude=[GFX])
    clash = {n: other[n] for n in names if n in other}
    assert not clash, f"sprite names already declared elsewhere: {clash}"
    gui_names = tb.declared_names(gui)
    for t in GUI_TYPES:
        assert gui_names.count(t) == 1, t
    other_gui = tb.existing_names("*.gui", exclude=[GUI])
    clash = {t: other_gui[t] for t in GUI_TYPES if t in other_gui}
    assert not clash, f"gui type names already declared elsewhere: {clash}"
    refs = set(re.findall(r'quadTextureSprite\s*=\s*"(GFX_[^"]+)"', gui))
    assert refs <= set(names), refs - set(names)
    # the bank matches the plate math
    for kind, (size, n_max, frame_cols, _) in tb.BANK.items():
        for n in (1, n_max):
            img = textures[f"{tb.bank_sprite(kind, n)[len('GFX_totu_'):]}.dds"]
            assert img.size == (tb.bank_width(n, size) * len(frame_cols),
                                tb.PLATE_H if size == "big" else tb.SMALL_PLATE_H), (kind, n, img.size)
    # the bank's 40 px plates equal the menu's caption plates pixel for pixel
    for w in tb.CAPTION_PLATES:
        menu = Image.open(tb.TOTU_TEX / f"caption_{w}.dds").convert("RGBA")
        assert menu.tobytes() == textures[f"plate_{w}.dds"].tobytes(), f"plate_{w} differs from caption_{w}"
    for w in tb.SMALL_PLATES:
        menu = Image.open(tb.TOTU_TEX / f"caption_small_{w}.dds").convert("RGBA")
        assert menu.tobytes() == textures[f"plate_s_{w}.dds"].tobytes(), f"plate_s_{w} differs"
    return len(other)


def check_dds():
    """Every texture exists on disk with the header uncompressed A8R8G8B8, no mipmaps, the image's size."""
    for fname, img in textures.items():
        assert (OUT / fname).exists(), fname
        hd = tb.dds_header(OUT / fname)
        assert (hd["w"], hd["h"]) == img.size and hd["mips"] == 0 and hd["pfflags"] == 0x41 and hd["bits"] == 32 \
            and hd["masks"] == (0xFF0000, 0xFF00, 0xFF, 0xFF000000) and hd["caps"] == 0x1000, (fname, hd)


# ---------------------------------------------------------------- previews
def font(name):
    return tb.load_font(name)


def centred_text(img, f, text, x, y, w, colour=tb.P):
    """buttonText as the engine centres it in a plate of width w (line box = plate height)."""
    adv = sum(f[1][ord(ch)]["xadvance"] for ch in text)
    tb.draw_text(img, f, text, x + (w - adv) // 2, y, colour)


SAMPLE_SIZE = {"board_ig": (160, 48), "board_solid": (160, 48), "raised": (160, 48), "field_tile": (160, 48),
               "row_hl": (160, 28), "row_hover": (160, 28), "hairline": (160, 2), "scroll_track": (8, 96),
               "scroll_track_h": (96, 8)}


def frame_cells(img, n):
    return tb.split_frames(img, n) if n > 1 else [img]


def draw_value_slider(img, x, y, w, value, knob=0, left=0, right=0):
    """totu_value_slider at (x, y), w x 16: 16 px end buttons at both ends (borderSize 16), the track between
    them, the knob at value 0..1 on the track; every part at the same y, as the scrollbarType places them."""
    tex = textures
    img.alpha_composite(tb.cornered(tex["slider_track.dds"], w - 2 * STEP4, 16), (x + STEP4, y))
    img.alpha_composite(tb.split_frames(tex["step_left_4f.dds"], 4)[left], (x, y))
    img.alpha_composite(tb.split_frames(tex["step_right_4f.dds"], 4)[right], (x + w - STEP4, y))
    kx = x + STEP4 + round(value * (w - 2 * STEP4 - KNOB[0]))
    img.alpha_composite(tb.split_frames(tex["slider_knob.dds"], 4)[knob], (kx, y))


def draw_scrollbar(img, x, y, h, knob_y, knob=0):
    """totu_vertical_slider at (x, y), 12 x h: arrows at the ends of the column, the track at x + 1 between them,
    the knob at the track's x (frame knob: 0 idle, 1 hover, 2 pressed)."""
    tex = textures
    img.alpha_composite(tex["scroll_up.dds"], (x, y))
    img.alpha_composite(tex["scroll_down.dds"], (x, y + h - ARROW))
    img.alpha_composite(tb.cornered(tex["scroll_track.dds"], SCROLL_W, h - 2 * ARROW), (x + 1, y + ARROW))
    img.alpha_composite(tb.split_frames(tex["scroll_knob.dds"], 3)[knob], (x + 1, y + ARROW + knob_y))


def preview_widgets(path):
    btn, btn_s = font("totu_button"), font("totu_button_small")
    items = []
    groups = [("surface", "SURFACES ON THE IN-GAME BOARD (CORNEREDTILE AT SAMPLE SIZES)"),
              ("button", "BUTTONS: EVERY FRAME AT 1X, THEN THE STRIP AT 3X"),
              ("slider", "VALUE SLIDER PARTS"), ("scroll", "SCROLLBAR PARTS"), ("entry", "LIST ENTRY")]
    for group, title in groups:
        items.append(title)
        for g, name, img, n, size, border, tiling in shown:
            if g != group:
                continue
            short = name[len("GFX_totu_"):]
            if border is not None:                  # corneredTile: drawn at a sample size, then its right edge 3x
                w, h = SAMPLE_SIZE.get(short, size)
                pic = tb.over(tb.preview_bg(w + 16, h + 16), tb.cornered(img, w, h, border, tiling is not False),
                              (8, 8))
                items.append((f"{short} drawn {w}x{h}", pic))
                items.append(("3x", tb.zoom(pic.crop((max(0, pic.width - 40), 0, pic.width, pic.height)), 3)))
                continue
            cells = frame_cells(img, n)
            fw, fh = cells[0].size
            row = tb.preview_bg(n * (fw + 8) + 8, fh + 16)
            for i, c in enumerate(cells):
                row.alpha_composite(c, (8 + i * (fw + 8), 8))
            items.append((f"{short} {fw}x{fh} x{n}", row))
            big = tb.over(tb.preview_bg(img.width + 8, img.height + 8), img, (4, 4))
            if big.width > 400:                     # wide entries: the tail end of the last frame only
                big = big.crop((big.width - 64, 0, big.width, big.height))
            items.append((f"{short} 3x", tb.zoom(big, 3)))
    # assembled controls
    items.append("ASSEMBLED: VALUE SLIDER, SCROLLBAR (AS LAID OUT IN THE .GUI TYPES)")
    sl = tb.preview_bg(276 + 16, 32)
    draw_value_slider(sl, 8, 8, 276, 0.45, knob=0, right=1)
    items.append(("totu_value_slider 276x16: idle knob, right step hovered", sl))
    items.append(("3x", tb.zoom(sl.crop((0, 0, 96, 32)), 3)))
    for knob, label in ((0, "idle"), (1, "hover")):
        sb = tb.preview_bg(12 + 16, 200)
        draw_scrollbar(sb, 8, 8, 184, 48, knob)
        items.append((f"totu_vertical_slider, knob {label}", sb))
        items.append(("3x", tb.zoom(sb.crop((0, 0, 28, 100)), 3)))
    # bank samples with engine-centred text
    items.append("PLATE BANK SAMPLES WITH ENGINE-CENTRED BUTTONTEXT (FRAMES 1 / 2 / 3)")
    samples = [("plate", ("Назад", "Back"), "big"), ("plate", ("Применить", "Apply"), "big"),
               ("slate", ("Сохранить", "Save"), "big"), ("plate_s", ("Сбросить", "Reset"), "small"),
               ("slate_s", ("Загрузить шаблон", "Load preset"), "small"), ("tab_s", ("Графика", "Video"), "small"),
               ("toggle_s", ("Сведения", "Details"), "small"), ("toggle_r_s", ("Управление", "Controls"), "small")]
    for kind, labels, size in samples:
        name = tb.plate_sprite(labels, size, kind[:-2] if kind.endswith("_s") else kind)
        img = textures[f"{name[len('GFX_totu_'):]}.dds"]
        n = len(tb.BANK[kind][2])
        f = btn if size == "big" else btn_s
        cells = frame_cells(img, n)
        fw, fh = cells[0].size
        row = tb.preview_bg(n * (fw + 8) + 8, fh + 16)
        for i, c in enumerate(cells):
            row.alpha_composite(c, (8 + i * (fw + 8), 8))
            centred_text(row, f, labels[0], 8 + i * (fw + 8), 8, fw)
        items.append((name[len("GFX_totu_"):], row))
    big_row = items[-len(samples)][1]
    items.append(("3x", tb.zoom(big_row, 3)))
    items.append("PICTOGRAMS (PICTO, 2 PX CELLS, P WITH K DROP) AT 1X AND 3X")
    for name in tb.PICTO:
        pic = tb.over(tb.preview_bg(24, 24), tb.button_frame(24, 24, name))
        items.append((name, pic))
    strip = tb.preview_bg(len(tb.PICTO) * 24, 24)
    for i, name in enumerate(tb.PICTO):
        strip.alpha_composite(tb.button_frame(24, 24, name), (i * 24, 0))
    items.append(("3x", tb.zoom(strip, 3)))
    items.append("PIXEL TEXT: PIXEL_TEXT(TEXT, CELL) ANY GLYPH, SQUARE AND TELETEXT (2, 3) CELLS")
    for cell in (2, (2, 3), 3):
        t = tb.pixel_text("Настройки игры — Ёж, Щит, №12", cell)
        items.append((f"cell {cell}", tb.over(tb.preview_bg(t.width + 16, t.height + 16), t, (8, 8))))
    tb.contact_sheet(items, path, width=1900, bg="board", label_cell=1)


def preview_bank(path):
    items = []
    for kind in tb.BANK:
        items.append(GROUP_TITLES[f"bank_{kind}"].upper())
        size, n_max, frame_cols, _ = tb.BANK[kind]
        for n in range(1, n_max + 1):
            name = tb.bank_sprite(kind, n)
            img = textures[f"{name[len('GFX_totu_'):]}.dds"]
            items.append((f"{name[len('GFX_totu_'):]} n{n}", tb.over(tb.preview_bg(img.width + 8, img.height + 8),
                                                                     img, (4, 4))))
    tb.contact_sheet(items, path, width=1900, bg="board", label_cell=1, gap=10)


def preview_mock(path):
    """A 1280x720 screen with an options-like dialog built only from kit sprites and the totu fonts."""
    label, btn, btn_s = font("totu_caption_small_k"), font("totu_button"), font("totu_button_small")
    bg_src = tb.ROOT / "gfx" / "loadingscreens" / "totu_red_square.dds"
    sw, sh = 1280, 720
    if bg_src.exists():
        shot = tb.cover(Image.open(bg_src).convert("RGB"), sw, sh).convert("RGBA")
    else:
        shot = tb.checker(sw, sh)
    W, H = 640, 520
    x0, y0 = (sw - W) // 2, (sh - H) // 2
    tex = textures
    shot.alpha_composite(tb.cornered(tex["board_ig.dds"], W, H), (x0, y0))
    pad = tb.BOARD_PAD

    def frame(fname, n, i):
        return tb.split_frames(tex[fname], n)[i]

    def text(s, x, y, colour=tb.P):
        tb.draw_text(shot, label, s, x0 + x, y0 + y, colour)

    def plate_at(labels, size, kind, x, y, fr, draw=True):
        name = tb.plate_sprite(labels, size, kind)
        n = len(tb.BANK[tb.bank_kind(kind, size)][2])
        img = frame(f"{name[len('GFX_totu_'):]}.dds", n, fr)
        shot.alpha_composite(img, (x0 + x, y0 + y))
        if draw:
            centred_text(shot, btn if size == "big" else btn_s, labels[0], x0 + x, y0 + y, img.width)
        return img.width

    text("НАСТРОЙКИ", pad, pad)
    shot.alpha_composite(frame("close.dds", 3, 0), (x0 + W - pad - 24 + 6, y0 + 14))
    # tab row
    x = pad
    for i, labels in enumerate([("Игра", "Game"), ("Графика", "Video"), ("Звук", "Audio"),
                                ("Управление", "Controls")]):
        x += plate_at(labels, "small", "tab", x, 52, 1 if i == 1 else 0) + 12
    shot.alpha_composite(tb.cornered(tex["hairline.dds"], W - 2 * pad, 1), (x0 + pad, y0 + 84))
    # rows, pitch 32 from y 96
    y = 96
    text("РАЗРЕШЕНИЕ", pad, y + 9)
    shot.alpha_composite(frame("step_left.dds", 3, 0), (x0 + 342, y0 + y + 6))
    tb.draw_text(shot, label, "2560 X 1440", x0 + 342 + 20 + (236 - tb.text_advance("2560 X 1440", 2)) // 2,
                 y0 + y + 9, tb.P)
    shot.alpha_composite(frame("step_right.dds", 3, 1), (x0 + 598, y0 + y + 6))
    y += 32
    text("ОБЩАЯ ГРОМКОСТЬ", pad, y + 9)
    draw_value_slider(shot, x0 + 342, y0 + y + 8, 276, 0.62)            # scrollbarType at (342, row + 8)
    y += 32
    text("МУЗЫКА", pad, y + 9)
    draw_value_slider(shot, x0 + 342, y0 + y + 8, 276, 0.0, knob=1, left=3)
    y += 32
    check = Image.open(tb.TOTU_TEX / "checkbox.dds").convert("RGBA")
    for on, s in ((1, "ПАУЗА ПРИ ВСПЛЫВАЮЩИХ ОКНАХ"), (0, "ПОКАЗЫВАТЬ РЕГИОНЫ")):
        shot.alpha_composite(check.crop((on * 20, 0, on * 20 + 20, 20)), (x0 + pad, y0 + y + 6))
        text(s, pad + 28, y + 9)
        y += 32
    text("ИМЯ СОХРАНЕНИЯ", pad, y + 9, tb.D)
    shot.alpha_composite(tb.cornered(tex["field_tile.dds"], 276, 32), (x0 + 342, y0 + y))
    tb.draw_text(shot, label, "СССР 1990_", x0 + 350, y0 + y + 9, tb.P)
    y += 44
    # list on a raised panel with a scrollbar
    lw, lh = W - 2 * pad, 120
    shot.alpha_composite(tb.cornered(tex["raised.dds"], lw, lh), (x0 + pad, y0 + y))
    rows = ["СССР, 1 ЯНВАРЯ 1990", "США, 3 МАРТА 1990", "ПОЛЬША, 12 МАЯ 1990", "ГДР, 9 НОЯБРЯ 1989"]
    for i, s in enumerate(rows):
        ry = y + 4 + i * 28
        if i == 1:
            shot.alpha_composite(tb.cornered(tex["row_hl.dds"], lw - 20, 28), (x0 + pad, y0 + ry))
        elif i == 2:
            shot.alpha_composite(tb.cornered(tex["row_hover.dds"], lw - 20, 28), (x0 + pad, y0 + ry))
        text(s, pad + 12, ry + 7, tb.P if i != 3 else tb.D)
    draw_scrollbar(shot, x0 + pad + lw - 14, y0 + y + 2, lh - 4, 6)
    # bottom plate row inside the board's lower edge
    by = H - 40 - 8
    plate_at(("Назад", "Back"), "big", "plate", 0, by, 0)
    plate_at(("Сбросить", "Reset"), "small", "slate", 196, by + 8, 0)
    wa = tb.plate_w(("Применить", "Apply"))
    plate_at(("Применить", "Apply"), "big", "plate", W - wa, by, 1)
    crop = shot.crop((x0 - 8, y0 - 8, x0 + 360, y0 + 260))
    out = Image.new("RGBA", (sw, sh + crop.height * 2 + 16), (0, 0, 0, 255))
    out.paste(shot, (0, 0))
    out.paste(tb.zoom(crop, 2), (0, sh + 16))
    out.convert("RGB").save(path)
    tb._say("wrote", tb.rel(path), f"{out.width}x{out.height}")


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-preview", action="store_true")
    args = ap.parse_args()
    if not __debug__:
        raise SystemExit("run without python -O: the checks of this builder are asserts")
    t0 = time.time()
    build_bank()
    build_surfaces()
    build_buttons()
    build_sliders()
    build_entries()

    # every check on the in-memory text and textures first: nothing reaches the mod folder (OneDrive) if one fails
    gfx, gui = gfx_text(), GUI_TEXT
    n_other = check(gfx, gui)
    written = sum(tb.save_dds(img, OUT / fname, quiet=True) for fname, img in sorted(textures.items()))
    stale = [p for p in OUT.glob("*.dds") if p.name not in textures]
    for p in stale:
        p.unlink()
        tb._say("removed stale", tb.rel(p))
    check_dds()                                     # the files on disk; the .gfx / .gui are written last
    gfx_changed = tb.write_text(GFX, gfx)
    gui_changed = tb.write_text(GUI, gui)
    tb._say(f"{len(sprites)} sprites ({sum(1 for g, _, _ in sprites if g.startswith('bank_'))} in the plate bank), "
            f"{len(textures)} textures ({written} written, {len(textures) - written} unchanged, {len(stale)} removed)")
    tb._say(f"interface/totu_widgets.gfx {'written' if gfx_changed else 'unchanged'}, interface/totu_widgets.gui "
            f"{'written' if gui_changed else 'unchanged'}; no collision with {n_other} other sprite names")
    total = sum((OUT / f).stat().st_size for f in textures)
    tb._say(f"textures: {total / 1e6:.1f} MB in {tb.rel(OUT)}")
    if not args.no_preview:
        tb.PREVIEW.mkdir(parents=True, exist_ok=True)
        preview_widgets(tb.PREVIEW / "widgets.png")
        preview_bank(tb.PREVIEW / "widgets_bank.png")
        preview_mock(tb.PREVIEW / "widgets_mock.png")
    tb._say(f"done in {time.time() - t0:.1f} s")


if __name__ == "__main__":
    main()
