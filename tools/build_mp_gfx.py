"""tools/build_mp_gfx.py: sprites and localisation of the multiplayer screens (area 'mp', broadcast style).

Writes
  gfx/interface/totu/mp/*.dds                     sort headers, server row, lobby stats plate
  interface/totu_mp.gfx                           GFX_totu_mp_* sprites
  localisation/{english,russian}/totu_menu_mp_l_<lang>.yml   TOTU_FE_MP_* captions
  tools/preview/mp.png                            contact sheet

The windows themselves are interface/frontendmultiplayerview.gui, matchmaking.gui, playerlobby.gui and hotjoin.gui
(full copies of vanilla 1.19.3); the vanilla MP chrome textures they may still reference are flattened by
tools/ingame/mp.py (python tools/build_ingame_gfx.py --only mp).

    python tools/build_mp_gfx.py              build (idempotent: unchanged files are not rewritten)
    python tools/build_mp_gfx.py --check      build in memory and check, write nothing
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import totu_broadcast as tb  # noqa: E402

AREA = "mp"
OUT = tb.TOTU_TEX / AREA
GFX = tb.INTERFACE / f"totu_{AREA}.gfx"
TEX = f"gfx/interface/totu/{AREA}"

# TOTU_FE_MP_* captions (pixel fonts: totu_button / totu_button_small / totu_label); (english, russian)
LOC = {
    "TOTU_FE_MP_CONNECT_ID": ("Server ID", "По ID сервера"),
    "TOTU_FE_MP_JOIN": ("Join", "Войти"),
    "TOTU_FE_MP_HOST": ("Host", "Создать"),
    "TOTU_FE_MP_REFRESH": ("Refresh", "Обновить"),
    "TOTU_FE_MP_LAN": ("LAN", "Локальная сеть"),
    "TOTU_FE_MP_INTERNET": ("Internet", "Интернет"),
    "TOTU_FE_MP_FILTER": ("Filter", "Фильтр"),
    "TOTU_FE_MP_SEND": ("Send", "Отправить"),
    "TOTU_FE_MP_FRIENDS": ("Friends", "Друзья"),
    "TOTU_FE_MP_PLAYER_NAME": ("Player name", "Имя игрока"),
    "TOTU_FE_MP_LOBBY": ("Lobby", "Лобби"),
}

# lobby stats plate: "Lobby" at 11, players icon at 80, count at 104, chat icon at 142, count at 166 (32 wide)
LOBBY_W = 214
# column headers (small plates 12n+22 wide, the longer RU / EN label fits; hoi_24header text, centred by the engine):
# password 118, name 250, slots 106, version 118, tags 166, mod 106, status 106 = 970 px of the 978 px list
SORT_WIDTHS = (106, 118, 166, 250)
ROW_W, ROW_H = 964, 30            # server row: the list width minus the scrollbar column


def textures():
    """name -> (image, frames, comment)."""
    out = {}
    for w in SORT_WIDTHS:
        out[f"sort_{w}"] = (tb.plate_frames(w, 24), 3, f"column header {w}x24: transparent / keyer / pressed")
    out[f"row_{ROW_W}"] = (tb.plate_frames(ROW_W, ROW_H, (None, tb.KEY_BLUE), tail=0), 2,
                      f"server row {ROW_W}x{ROW_H}: transparent / keyer")
    out["lobby"] = (tb.plate_frames(LOBBY_W, 24, (tb.SLATE_RGB, tb.KEY_BLUE, tb.KEY_BLUE_DOWN)), 3,
                    f"lobby stats plate {LOBBY_W}x24: slate / keyer / pressed")
    return out


def gfx_text(tex):
    blocks = []
    for key, (img, frames, comment) in tex.items():
        blocks.append(tb.sprite_block(f"GFX_totu_{AREA}_{key}", f"{TEX}/{key}.dds", frames=frames,
                                      effect=tb.EFFECT_ONLYDISABLE, comment=comment))
    return tb.gfx_file(blocks, ["Twilight of the Union: multiplayer sprites (tools/build_mp_gfx.py). Generated; do not edit."])


def main(check_only=False):
    tex = textures()
    text = gfx_text(tex)
    names = tb.declared_names(text)
    assert len(names) == len(set(names)), names
    clash = {n: v for n, v in tb.existing_names("*.gfx", exclude=[GFX]).items() if n in names}
    assert not clash, clash
    for key, (img, frames, _) in tex.items():
        assert img.width % frames == 0, key
    for k, (en, ru) in LOC.items():
        assert k.startswith("TOTU_FE_MP_"), k
        tb.text_advance(en.upper(), font="totu_button")      # raises on a missing glyph
        tb.text_advance(ru.upper(), font="totu_button")
    if check_only:
        tb._say("mp: check ok (nothing written)")
        return
    for key, (img, _, _) in tex.items():
        tb.save_dds(img, OUT / f"{key}.dds")
    keep = {f"{k}.dds" for k in tex}
    for p in OUT.glob("*.dds"):
        if p.name not in keep:
            p.unlink()
    hdr = ["Twilight of the Union: multiplayer captions (tools/build_mp_gfx.py). Generated; do not edit."]
    tb.write_loc(tb.LOCALISATION / "english" / "totu_menu_mp_l_english.yml", "english",
                 [(k, en) for k, (en, ru) in LOC.items()], header=hdr)
    tb.write_loc(tb.LOCALISATION / "russian" / "totu_menu_mp_l_russian.yml", "russian",
                 [(k, ru) for k, (en, ru) in LOC.items()], header=hdr)
    tb.write_text(GFX, text)
    tb.assert_declared(GFX, names)
    items = []
    for key, (img, frames, _) in tex.items():
        items.append((key, tb.zoom(img if img.width <= 1200 else img.crop((0, 0, 600, img.height)), 2)))
    tb.contact_sheet(items, tb.PREVIEW / f"{AREA}.png", bg="board")
    tb._say(f"mp: {len(tex)} textures, {GFX}")


if __name__ == "__main__":
    main("--check" in sys.argv)
