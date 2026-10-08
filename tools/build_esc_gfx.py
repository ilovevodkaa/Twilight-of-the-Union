"""tools/build_esc_gfx.py: textures of the in-game Esc menu area ('esc').

    python tools/build_esc_gfx.py            texture + preview
    python tools/build_esc_gfx.py --check    checks only, writes nothing

Writes gfx/interface/totu/esc/lobby_button.dds: the GFX_main_lobby_button strip (interface/frontendmainview.gfx,
textSpriteType, 3 frames, buttonstate_onlydisable) at the vanilla size 864x36 = 3 x 288x36:
slate plate with the stepped tail / keyer / pressed. Since the broadcast Esc menu uses kit plates, the sprite's
only live user is the peace conference end-turn button (peaceconferencewindow.gui end_turn_button), which must be
visible before it is hovered, hence the slate first frame.

The Esc menu dark overlay (vanilla path in_game_menu_dark_overlay.dds) is drawn by tools/ingame/esc.py through
tools/build_ingame_gfx.py --only esc.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import totu_broadcast as tb  # noqa: E402

AREA = "esc"
OUT = tb.TOTU_TEX / AREA
GFX_MAIN = tb.INTERFACE / "frontendmainview.gfx"
LOBBY_TEX = f"gfx/interface/totu/{AREA}/lobby_button.dds"
LOBBY_W, LOBBY_H = 288, 36        # vanilla main_lobby_button.dds frame


def lobby_button():
    return tb.plate_frames(LOBBY_W, LOBBY_H, frames=(tb.SLATE_RGB, tb.KEY_BLUE, tb.KEY_BLUE_DOWN))


def check(img):
    assert img.size == (LOBBY_W * 3, LOBBY_H), img.size
    text = GFX_MAIN.read_text(encoding="utf-8")
    block = text[text.index('"GFX_main_lobby_button"'):]
    block = block[:block.index("}")]
    assert LOBBY_TEX in block, "GFX_main_lobby_button must point at " + LOBBY_TEX
    assert "noOfFrames = 3" in block, "GFX_main_lobby_button: 3 frames"


def main(argv):
    img = lobby_button()
    check(img)
    if "--check" in argv:
        print("esc: checks OK (nothing written)")
        return
    tb.save_dds(img, OUT / "lobby_button.dds")
    zoomed = tb.zoom(tb.over(tb.preview_bg(img.width, img.height), img, (0, 0)), 2)
    tb.contact_sheet([("GFX_main_lobby_button 864x36: slate / keyer / pressed", zoomed)],
                     tb.PREVIEW / f"{AREA}_textures.png", bg="board")


if __name__ == "__main__":
    main(sys.argv[1:])
