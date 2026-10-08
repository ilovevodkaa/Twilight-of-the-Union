"""tools/build_popups_gfx.py: interface/popupwindow.gui in the broadcast style (area 'popups').

The mod's popupwindow.gui replaces the whole vanilla file, so it is generated from the vanilla 1.19.3 file:

  * the ten generic popups (quit / delete save, info, connection lost, OOS, AI controller, confirmation, research
    and focus finished, special project completed, standard diplomacy) are written anew below: board, pixel title at
    (22,22), P description with the kit text scrollbar, 24 px plates (decline = transparent, accept = slate) inside
    the board's bottom edge, flags and leaders without frames;
  * every other window keeps its vanilla layout: plain backgrounds become GFX_totu_board_ig, decorative iconTypes
    (header art, bottom strips, frames, peace-conference corners, focus laurel) move to -9000 with a TotU comment.

Every vanilla element (type, name) pair is asserted to survive, so the engine finds every element it looks up.
The textures of the popup-local sprites are drawn by tools/ingame/popups.py (build_ingame_gfx.py --only popups).

    python tools/build_popups_gfx.py            write interface/popupwindow.gui (only if it changed)
    python tools/build_popups_gfx.py --check    build and check in memory, write nothing
"""
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import totu_broadcast as tb  # noqa: E402

AREA = "popups"
VANILLA = tb.GAME / "interface" / "popupwindow.gui"
OUT = tb.INTERFACE / "popupwindow.gui"
BOARD = "GFX_totu_board_ig"
HIDE = "position = { x = -9000 y = -9000 }"

# backgrounds that are a plain surface (tiled window or a full-window painting)
PLAIN_BG = ("GFX_tiled_bg", "GFX_pol_goal_popup_bg", "GFX_popup_capitulation_bg", "GFX_popup_new_exile_hosted_bg",
            "GFX_popup_new_exile_hosted_small_bg", "GFX_tiled_window_pol_goal", "SandboxFloaterBackground")
# purely decorative iconTypes (header art, bottom strips, frames, corner ornaments, laurels)
DECOR = re.compile(r"^(diplo_popup_header_bg|diplo_popup_bottom|pc_decoration_top_(left|right)|focus_popup_bg|"
                   r"(sender|receiver|reciever)_(flag|leader)_frame|diplo_war_large_icon2?)$")


# ---------------------------------------------------------------- .gui text helpers (tabs, vanilla layout)
def ind(text, n):
    pad = "\t" * n
    return "\n".join(pad + ln if ln else ln for ln in text.strip("\n").split("\n"))


def board():
    return ('background = {\n\tname = "Background"\n\tquadTextureSprite = "%s"\t# TotU: broadcast board\n}' % BOARD)


def title(w, font="hoi_24header", y=22):
    h = 36 if font == "hoi_36header" else 24
    return (f'instantTextBoxType = {{\n\tname = "title"\n\tposition = {{ x = 22 y = {y} }}\n\ttextureFile = ""\n'
            f'\tfont = "{font}"\n\tborderSize = {{ x = 0 y = 0 }}\n\ttext = "Title"\n\tmaxWidth = {w - 44}\n'
            f'\tmaxHeight = {h}\n\tfixedsize = yes\n\ttruncate = yes\n\tformat = left\n}}')


def text_box(name, x, y, w, h, fmt="left", slider=True, extra=""):
    s = (f'instantTextBoxType = {{\n\tname = "{name}"\n\tposition = {{ x = {x} y = {y} }}\n\ttextureFile = ""\n'
         f'\tfont = "hoi_18mbs"\n\ttext_color_code = P\n\tborderSize = {{ x = 0 y = 0 }}\n\ttext = "Long text here!"\n'
         f'\tmaxWidth = {w}\n\tmaxHeight = {h}\n\tformat = {fmt}\n')
    if slider:
        s += '\tscrollbartype = "totu_text_slider"\n'
    return s + extra + "}"


def button(name, x, y, key, kind, extra=""):
    """24 px bank plate sized to the key's longest RU / EN value (kind 'plate' = transparent, 'slate')."""
    labels = ("OK", "OK") if key == "OK" else tb.labels_for(key)     # "OK" is no loc key: the engine shows it as is
    sprite = tb.plate_sprite(labels, "small", kind)
    note = "transparent plate (decline)" if kind == "plate" else "slate plate (accept)"
    return (f'buttonType = {{\n\tname = "{name}"\n\tposition = {{ x = {x} y = {y} }}\n\tquadTextureSprite = "{sprite}"'
            f'\t# TotU: {note}\n\tbuttonText = "{key}"\n\tbuttonFont = "hoi_24header"\n{extra}}}')


def plate_w(key):
    labels = ("OK", "OK") if key == "OK" else tb.labels_for(key)
    return int(tb.plate_sprite(labels, "small", "slate").rsplit("_", 1)[1])


def hidden_icon(name, sprite, kind="spriteType", extra=""):
    return (f'iconType = {{\n\tname = "{name}"\n\t{kind} = "{sprite}"\n\t{HIDE}\t# TotU: decoration hidden\n'
            f'{extra}}}')


def icon(name, sprite, x, y, kind="quadTextureSprite", extra=""):
    return f'iconType = {{\n\tname = "{name}"\n\t{kind} = "{sprite}"\n\tposition = {{ x = {x} y = {y} }}\n{extra}}}'


def window(head, parts):
    body = "\n\n".join(ind(p, 2) for p in parts)
    return f"\tcontainerWindowType = {{\n{ind(head, 2)}\n\n{body}\n\t}}"


def head(name, w, h, pos=None, origo=False, sounds=("", "menu_close_window"), comment=""):
    s = f'name = "{name}"\n'
    if pos is not None:
        s += f"position = {{ x = {pos[0]} y = {pos[1]} }}\n"
    s += f"size = {{ width = {w} height = {h} }}{comment}\norientation = center\n"
    if origo:
        s += "origo = center\n"
    s += "moveable = yes\nfade_time = 200\nfade_type = linear\n"
    if sounds[0]:
        s += f"show_sound = {sounds[0]}\n"
    if sounds[1]:
        s += f"hide_sound = {sounds[1]}\n"
    return s + "click_to_front = yes"


ESC = '\tshortcut = "ESCAPE"\n'
RET = '\tshortcut = "RETURN"\n'
OKS = '\tshortcut = "RETURN"\n\tclicksound = click_ok\n'


def bottom_pair(w, h, left, right):
    """left = (name, key, extra) transparent at x 22; right = (name, key, extra) slate right-aligned; y = h-22-24."""
    y = h - 46
    out = []
    if left:
        out.append(button(left[0], 22, y, left[1], "plate", left[2]))
    if right:
        out.append(button(right[0], w - 22 - plate_w(right[1]), y, right[1], "slate", right[2]))
    return out


# ---------------------------------------------------------------- the ten restyled windows
def w_default_confirmation():
    W, H = 520, 280
    return window(head("default_confirmation_popup", W, H, origo=True, sounds=("", ""),
                       comment="\t# TotU: vanilla 480x382"), [
        board(),
        title(W),
        text_box("description", 22, 62, W - 58, 148),
        *bottom_pair(W, H, ("decline_button", "PDXO_CANCEL", ESC + "\tclicksound = click_close\n"),
                     ("accept_button", "OK", RET + "\tclicksound = click_default\n")),
    ])


def w_info(name, W, H, sound, buttons, desc_h=None):
    desc_h = desc_h or H - 74 - 46 - 20
    return window(head(name, W, H, origo=True, sounds=(sound, "menu_close_window")), [
        board(),
        title(W, "hoi_36header"),
        text_box("description", 22, 74, W - 58, desc_h),
        *buttons,
    ])


def w_default_info():
    W, H = 584, 280
    return w_info("default_info_popup_window", W, H, "peace_summary_message",
                  bottom_pair(W, H, None, ("ok_button", "BUTTON_OK", OKS)))


def w_oos():
    W, H = 584, 400
    return w_info("oos_popup_window", W, H, "peace_summary_message",
                  bottom_pair(W, H, ("resync_button", "MULTIPLAYER_RESYC", OKS), ("ok_button", "BUTTON_OK", OKS)))


def w_connection_lost():
    W, H = 500, 280
    return w_info("connection_lost_popup_window", W, H, "peace_summary_message",
                  bottom_pair(W, H, ("save_button", "SAVE", "\tclicksound = click_ok\n"),
                              ("ok_button", "QUIT", "\tclicksound = click_ok\n")))


def w_project_completed():
    W, H = 584, 280
    return window(head("project_research_completed", W, H, origo=True,
                       sounds=("ui_special_project_finished_sound", "menu_close_window")), [
        board(),
        title(W, "hoi_36header"),
        text_box("description", 22, 74, W - 58, 100),
        icon("icon", "online_accountcreate_invalid", 200, 126, kind="spriteType"),    # engine: the project icon
        *bottom_pair(W, H, ("details_button", "DETAILS", OKS), ("ok_button", "BUTTON_OK", OKS)),
    ])


def w_aicontroller():
    W, H = 584, 280
    return window(head("aicontroller_popup_window", W, H, pos=(0, 0), origo=True,
                       sounds=("diplomatic_notification", "menu_close_window")), [
        board(),
        title(W),
        text_box("description", 22, 62, W - 58, 148),
        *bottom_pair(W, H, ("decline_button", "FE_DECLINE", ESC), ("accept_button", "FE_ACCEPT", OKS)),
    ])


def w_confirmation():
    W, H = 500, 320
    return window(head("confirmation_popup_window", W, H, pos=(-225, -160),
                       sounds=("diplomatic_notification", "menu_close_window")), [
        board(),
        hidden_icon("diplo_popup_header_bg", "GFX_diplo_popup_header_bg", extra="\talwaystransparent = yes\n"),
        title(W),
        hidden_icon("diplo_war_large_icon", "GFX_diplo_war_large_icon", "quadTextureSprite",
                    '\tOrientation = "UPPER_LEFT"\n\talwaystransparent = yes\n'),
        hidden_icon("diplo_war_large_icon2", "GFX_diplo_war_large_icon", "quadTextureSprite",
                    '\tOrientation = "UPPER_LEFT"\n\talwaystransparent = yes\n'),
        icon("sender_flag", "GFX_flag_small2", 22, 58, extra='\tOrientation = "UPPER_LEFT"\n'),
        hidden_icon("sender_flag_frame", "GFX_diplo_countrylist_flag_frame"),
        icon("receiver_flag", "GFX_flag_small2", W - 22 - 41, 58, extra='\tOrientation = "UPPER_LEFT"\n'),
        hidden_icon("receiver_flag_frame", "GFX_diplo_countrylist_flag_frame"),
        text_box("message", 22, 100, W - 58, H - 100 - 46 - 20),
        hidden_icon("diplo_popup_bottom", "GFX_diplo_popup_bottom"),
        *bottom_pair(W, H, None, ("ok_button", "OK", RET)),
    ])


def w_research_finished():
    W, H = 500, 260
    return window(head("research_finished_popup_window", W, H, pos=(-225, -160)), [
        board(),
        # TotU: the agency smoke texture is transparent (tools/ingame/popups.py); container kept for the engine
        'containerWindowType = {\n\tname = "paper_background"\n\tposition = { x = 13 y = 75 }\n'
        '\tsize = { width = 474 height = 123 }\n\n\tbackground = {\n\t\tname = "Background"\n'
        '\t\tspriteType = "GFX_agency_popup_bg"\n\t}\n}',
        hidden_icon("diplo_popup_header_bg", "GFX_diplo_popup_header_bg", extra="\talwaystransparent = yes\n"),
        title(W),
        icon("tech_icon", "GFX_adjuster_forest_bg", 250, 130, extra="\tcenterposition = yes\n"),
        icon("design_team_icon", "GFX_adjuster_forest_bg", 400, 130, extra="\tcenterposition = yes\n\thide = yes\n"),
        icon("facility_icon", "GFX_buildings_strip", 400, 130, extra="\tcenterposition = yes\n\thide = yes\n"),
        icon("equipment_icon", "GFX_land_equipment_role_icons", 312, 140, extra="\tcenterposition = yes\n"),
        icon("carrier_fighter_icon", "GFX_airwing_carrier_icon", 322, 140, extra="\tcenterposition = yes\n"),
        text_box("tech_name", 22, 170, W - 44, 24, "center", False, "\tfixedsize = yes\n\ttruncate = yes\n")
        .replace('"Long text here!"', '"Tech name"'),
        hidden_icon("diplo_popup_bottom", "GFX_diplo_popup_bottom"),
        *bottom_pair(W, H, ("details_button", "BUTTON_DETAILS", ""), ("ok_button", "BUTTON_OK", OKS)),
    ])


def w_focus_finished():
    W, H = 500, 260
    return window(head("focus_finished_popup_window", W, H, pos=(-225, -160),
                       sounds=("complete_focus", "menu_close_window")), [
        board(),
        hidden_icon("focus_popup_bg", "GFX_focus_popup_bg", extra="\talwaystransparent = yes\n"),
        hidden_icon("diplo_popup_header_bg", "GFX_diplo_popup_header_bg", extra="\talwaystransparent = yes\n"),
        title(W),
        icon("symbol", "GFX_goal_unknown", 250, 124, extra="\tcenterposition = yes\n"),
        text_box("focus_name", 22, 168, W - 44, 40, "center", False).replace('"Long text here!"', '"Focus name"'),
        hidden_icon("diplo_popup_bottom", "GFX_diplo_popup_bottom"),
        *bottom_pair(W, H, ("details_button", "BUTTON_DETAILS", ""), ("ok_button", "BUTTON_OK", OKS)),
    ])


def w_diplomacy_standard():
    W, H = 584, 320
    lx, rx = 22, W - 22 - 94             # leader portraits 156x210 at scale 0.6 = 94x126
    return window(head("diplomacy_standard_popup_window", W, H, pos=(-225, -160),
                       sounds=("diplomatic_notification", "menu_close_window")), [
        board(),
        hidden_icon("diplo_popup_header_bg", "GFX_diplo_popup_header_bg_large", extra="\talwaystransparent = yes\n"),
        title(W),
        icon("sender_flag", "GFX_shield_medium", 22, 58, extra='\tOrientation = "UPPER_LEFT"\n'),
        hidden_icon("sender_flag_frame", "GFX_large_flag_frame"),
        icon("receiver_flag", "GFX_shield_medium", W - 22 - 82, 58, extra='\tOrientation = "UPPER_LEFT"\n'),
        hidden_icon("receiver_flag_frame", "GFX_large_flag_frame"),
        icon("sender_leader", "GFX_leader_unknown", lx, 122, kind="spriteType", extra="\tscale = 0.6\n"),
        hidden_icon("sender_leader_frame", "GFX_leader_frame_0_6"),
        icon("reciever_leader", "GFX_leader_unknown", rx, 122, kind="spriteType", extra="\tscale = 0.6\n"),
        hidden_icon("reciever_leader_frame", "GFX_leader_frame_0_6"),
        text_box("description", 126, 58, W - 252 - 12, 190, "centre"),
        hidden_icon("diplo_popup_bottom", "GFX_diplo_popup_bottom_large"),
        *bottom_pair(W, H, ("decline_button", "FE_DECLINE", ESC), ("accept_button", "FE_ACCEPT", OKS)),
    ])


RESTYLED = {
    "diplomacy_standard_popup_window": w_diplomacy_standard,
    "research_finished_popup_window": w_research_finished,
    "confirmation_popup_window": w_confirmation,
    "default_confirmation_popup": w_default_confirmation,
    "focus_finished_popup_window": w_focus_finished,
    "default_info_popup_window": w_default_info,
    "oos_popup_window": w_oos,
    "aicontroller_popup_window": w_aicontroller,
    "connection_lost_popup_window": w_connection_lost,
    "project_research_completed": w_project_completed,
}


# ---------------------------------------------------------------- vanilla parsing
def block_end(text, start):
    """index just past the '}' closing the first '{' at or after start (no braces in vanilla strings/comments)."""
    i = text.index("{", start)
    depth = 0
    while True:
        c = text[i]
        if c == "#":
            i = text.index("\n", i)
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1


def top_windows(text):
    """[(name, start, end)] of the top-level containerWindowTypes (start = line start of the opening line)."""
    out = []
    for m in re.finditer(r"^\tcontainerWindowType\s*=\s*\{", text, re.M):
        end = block_end(text, m.start())
        name = re.search(r'name\s*=\s*"([^"]+)"', text[m.start():end]).group(1)
        out.append((name, m.start(), end))
    return out


ELEM = re.compile(r"\b([A-Za-z]+Type)\s*=\s*\{")


def elements(text):
    """Counter of (type lower-case, name) for every element block (comments stripped)."""
    clean = re.sub(r"#[^\n]*", "", text)
    out = Counter()
    for m in ELEM.finditer(clean):
        end = block_end(clean, m.start())
        nm = re.search(r'name\s*=\s*"?([^"\s]+)"?', clean[m.end():end])
        out[(m.group(1).lower(), nm.group(1) if nm else None)] += 1
    return out


def treat_vanilla(block):
    """Keep layout; plain backgrounds -> board; decorative iconTypes -> -9000."""
    def bg(m):
        return m.group(0) if m.group(2) not in PLAIN_BG else \
            f'{m.group(1)}quadTextureSprite = "{BOARD}"\t# TotU: broadcast board (vanilla {m.group(2)})'
    # backgrounds: the window's own background block is the first one after the head
    block = re.sub(r'(background\s*=\s*\{\s*name\s*=\s*"Background"\s*)quadTextureSprite\s*=\s*"([^"]+)"', bg, block)
    out, pos = [], 0
    for m in re.finditer(r"iconType\s*=\s*\{", block):
        end = block_end(block, m.start())
        body = block[m.start():end]
        nm = re.search(r'name\s*=\s*"\s*([^"]+?)\s*"', body)
        if nm and DECOR.match(nm.group(1)):
            new, n = re.subn(r"position\s*=\s*\{[^}]*\}", HIDE + "\t# TotU: decoration hidden", body, count=1)
            if n == 0:
                new = body.replace("{", "{\n\t\t\t" + HIDE + "\t# TotU: decoration hidden", 1)
            out.append(block[pos:m.start()] + new)
            pos = end
    out.append(block[pos:])
    return "".join(out)


def build():
    van = VANILLA.read_text(encoding="utf-8-sig")
    wins = top_windows(van)
    assert len(wins) == 30, len(wins)
    names = [w[0] for w in wins]
    missing = set(RESTYLED) - set(names)
    assert not missing, missing
    parts, pos = [], 0
    for name, s, e in wins:
        parts.append(van[pos:s])
        parts.append(RESTYLED[name]() if name in RESTYLED else treat_vanilla(van[s:e]))
        pos = e
    parts.append(van[pos:])
    head_note = ("# Twilight of the Union: broadcast popups. GENERATED by tools/build_popups_gfx.py from vanilla 1.19.3\n"
                 "# interface/popupwindow.gui (full copy: every vanilla element name and type is kept). Edit the builder.\n")
    text = head_note + "".join(parts).replace("\r\n", "\n")
    # every vanilla (type, name) survives, nothing new except totu_* helpers
    ve, me = elements(van), elements(text)
    lost = {k: v - me.get(k, 0) for k, v in ve.items() if me.get(k, 0) < v}
    assert not lost, f"vanilla elements lost: {lost}"
    extra = {k: v for k, v in (me - ve).items() if not (k[1] or "").startswith("totu_")}
    assert not extra, f"unexpected new elements: {extra}"
    assert text.count("{") == text.count("}"), "unbalanced braces"
    return text


def main():
    text = build()
    if "--check" in sys.argv:
        print(f"OK: popupwindow.gui builds ({len(text.splitlines())} lines), nothing written")
        return
    changed = tb.write_text(OUT, text)
    print("written" if changed else "unchanged", "interface/popupwindow.gui")


if __name__ == "__main__":
    main()
