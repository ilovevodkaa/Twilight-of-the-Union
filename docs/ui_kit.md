# Broadcast UI kit: shared widgets and builder API

Every restyled menu and in-game window uses this kit, in the "broadcast" style of late-Soviet TV captions.

- **Code:** `tools/totu_broadcast.py`, the one module a builder imports.
- **Generator:** `tools/build_widgets_gfx.py` makes the shared textures and declares them in `interface/totu_widgets.gfx` and `interface/totu_widgets.gui`.
- **Previews:** `tools/preview/widgets.png` (every frame at 1x and 3x), `widgets_bank.png` (the whole plate bank) and `widgets_mock.png` (a mock dialog built only from the kit).

```
python tools/totu_broadcast.py         # self-test of the module (writes nothing into the mod)
python tools/build_widgets_gfx.py      # textures + .gfx + .gui + previews (about 6 s; --no-preview: 1 s)
```

The builder is idempotent. Files whose bytes would not change are not rewritten, which matters because the mod folder syncs through OneDrive. Stale textures in `gfx/interface/totu/widgets/` are deleted.

The builder checks everything on the in-memory text before it writes a file, so a failed check leaves the mod folder untouched. It asserts that:
- every sprite is declared exactly once and every referenced texture is made;
- frame strips divide evenly by `noOfFrames`;
- the bank's 40 px and 24 px plates match the menu's `caption_*.dds` pixel for pixel;
- no sprite or gui type name collides with vanilla (including DLC) or with another mod interface file.

After the DDS writes it checks that every texture exists with an uncompressed, mipmap-free header. The `.gfx` and `.gui` are written last.

## Rules for stream builders

1. **Imports.** Import `totu_broadcast` only (`sys.path` already contains `tools/` when you run `python tools/x.py`). Do not edit `build_menu_gfx.py`, `build_fonts.py`, `build_widgets_gfx.py` or `totu_broadcast.py` from a stream. Ask the kit owner instead.
2. **Your own files.** Write textures to `gfx/interface/totu/<area>/` and declare them in `interface/totu_<area>.gfx`, named `GFX_totu_<area>_*`. Write previews to `tools/preview/<area>*.png`.
   - Check your names with `tb.existing_names("*.gfx", exclude=[your_gfx])` and `tb.assert_declared(your_gfx, names)`.
3. **Reuse before you draw.** Use a bank plate (`tb.plate_sprite`) or a kit sprite whenever one fits. Only draw what is specific to your area.
4. **Encoding.**
   - Write `.gui` and `.gfx` with `tb.write_text`: UTF-8 without BOM, LF, ASCII. Anything else raises ValueError, and nothing is written.
   - Write localisation with `tb.write_loc`: UTF-8 with BOM, LF, `l_<lang>:`.
   - Write DDS with `tb.save_dds`: uncompressed by default; `fmt="DXT5"` only through `tb.dds_policy(...)`.
   - Builders print ASCII only. Use `tb._say` for paths, because the mod path contains Cyrillic.
   - Never edit Cyrillic files through PowerShell `Get-Content` / `Set-Content`.
5. **Element names.** Keep every vanilla element name in a copied `.gui`. Move unused elements to `position = { x = -9000 y = -9000 }` with a `# TotU:` comment.
   - **Never change the element type** (`buttonType`, `checkboxType`, `iconType`, `instantTextBoxType`, ...) of an element the engine looks up by name. Restyle it in place: new sprite, font, text and position, same type. For example, `settings_tab_1..4` stay `buttonType`, and `localgames_tab` stays `checkboxType`.
   - Mod-only helper elements (extra labels, hairlines) get a `totu_` name prefix, so they can never shadow an engine name.
6. **Text and fonts.**
   - Text that the engine fills from vanilla keys goes in `totu_caption_name`, which has CJK fallbacks.
   - `totu_label`, `totu_button`, `totu_button_small` and `totu_caption` are for `TOTU_FE_*` / `TOTU_MENU_*` keys. Those keys get a glyph check and an English fallback from `tools/build_fonts.py`.

## Style spec (binding)

| Element | Spec | Constant(s) |
|---|---|---|
| Board | (9,11,16), alpha 0.84 in the frontend, 0.90 in game | `BOARD_RGB`, `BOARD_ALPHA`, `BOARD_ALPHA_IG` |
| Raised sub-panel | (18,22,30) at 0.92 | `RAISED_RGB`, `RAISED_ALPHA` |
| Field | D at 14 % over the board | `FIELD_ALPHA` |
| Hairline | D at 22 %, 1-2 px | `HAIRLINE_ALPHA` |
| Bar or scroll track | D at 18 %; bar fill is keyer or P | `TRACK_ALPHA` |
| Row hover | D at 8 % | `HOVER_ALPHA` |
| Slider line | D at 35 % | `SLIDER_LINE_ALPHA` |
| Scroll knob | P at 70 % | `SCROLL_KNOB_ALPHA` |
| Disabled pictogram | D at 30 % | `DISABLED_ALPHA` |
| Keyer (hover, active, selected) | (30,62,168); pressed (17,38,108) | `KEY_BLUE`, `KEY_BLUE_DOWN` |
| Slate (idle-visible plate) | (40,47,62) | `SLATE_RGB` |
| Plate tail | 2 steps at alpha 153 then 77: 6+6 px on 40 px plates, 3+3 on 24 px | `TAIL_ALPHA`, `TAIL`, `SMALL_TAIL` |
| Text | P (246,242,234) primary, D (172,180,196) secondary (never darker), K black drop at +2,+2 | `P`, `D`, `K`, `CAPTION_SHADOW` |
| Semantic colours (stay) | G (86,172,91), R (222,86,70), Y (238,201,35) | `SEM_G`, `SEM_R`, `SEM_Y`, `COLOURS` |

**Not allowed:** frames, borders, bevels, rivets, gradients (except the plate tail), paper, wood, metal, laurels, eagles or painted art.

**Keeps its colours:** content such as icons, portraits, flags and event photos.

**Pictograms:** pixel grids at 2 px cells, in P, with a K drop.

**Geometry:**
- Boards hold content on a 22 px inner measure (`BOARD_PAD`).
- Title in `totu_caption_name` P at (22,22).
- Rows on a 32 px pitch: label at row+9, control at row+6.
- Plates sit inside the board's bottom edge: Back at x 0, the action plate right-aligned.

## `tools/totu_broadcast.py` API

```python
import totu_broadcast as tb
```

**Paths:** `ROOT`, `SRC`, `GAME` (env `HOI4_DIR`), `INTERFACE`, `LOCALISATION`, `TOTU_TEX` (gfx/interface/totu), `WIDGETS_TEX`, `FONTS_DIR`, `PREVIEW`.

**Re-exported from `build_menu_gfx` (the same objects):**
- Palette: `KEY_BLUE`, `KEY_BLUE_DOWN`, `CAPTION_WHITE`=`P`, `CAPTION_DIM`=`D`, `CS_BOARD_RGB`=`BOARD_RGB`, `BOARD_ALPHA`, `TAIL_ALPHA`, `SOVIET_RED`, `DUSK_STOPS`, `STILL_RAMP`.
- Geometry: `SAFE_X/Y`, `CAP_CELL`, `SMALL_CELL`, `PLATE_H`, `PLATE_PITCH`, `PLATE_BOTTOM`, `QUIT_GAP`, `PAD_L/PAD_R/TAIL`, `SMALL_PLATE_H`, `SMALL_PAD_L/R`, `SMALL_TAIL`, `SMALL_PLATE_X`, `CAPTION_SHADOW`, `TEXT_TRAIL`, `CHECK`, `BAND_H/ALPHA/HOLD`, `CAPTION_PLATES`, `SMALL_PLATES`.
- Plates and surfaces: `build_caption_plate(w, h=40, tail=12, frames)`, `build_small_plate(w, frames)`, `keyer_strip(solid_w, h, colour, steps)`, `selection_frames`, `build_scrim(w, h, a0, plateau)`, `build_band(top)`, `build_board_tile`, `build_checkbox`, `build_field`, `menu_rows`.
- Photo grading: `cover`, `lerp_stops`, `secam`, `smoothstep`, `blur1d`, `tone`, `grain`, `scanlines`, `radial_mask`, `eye_bar`, `build_scenario_still` (the template for in-game stills).
- Preview text: `caption_fonts`, `draw_caption(img, font, text, x, y, colour=P, right=False, edge=True)`, `loc_value`, `colour_runs`, `wrap_runs`, `draw_runs`, `load_vanilla_font`, `draw_vanilla_box`, `PIXEL_FONT`.

**Re-exported from `build_fonts`:** `GLYPHS`, `CYRILLIC`, `PUNCTUATION`, `LATIN_EXTRA`, `LATIN_ALIASES`, `CODEPOINTS`, `FONTS`, `FONT_PAD`, `glyph_key`, `glyph_mask`, `glyph_tile`, `glyph_tile_k`, `read_fnt`, `load_font(name) -> (common, chars, atlas)`, `draw_text` (also `draw_glyphs`)`(img, font, text, x, y, colour) -> pen x`, `engine_wrap`, `strip_codes`.

### New functions

| Function | What it does |
|---|---|
| `rgba(rgb, alpha)` | `(r, g, b, round(255*alpha))` |
| `save_dds(img, path, fmt=None, quiet=False, only_if_changed=True) -> bool` | Works for any path. `fmt=None` writes uncompressed A8R8G8B8. `"DXT5"` only works when both sides are multiples of 4; otherwise it falls back to uncompressed and prints a note. Never writes mipmaps. The header is checked (ValueError). |
| `dds_policy(w, h, lossless=False)` | Returns `"DXT5"` when both sides are multiples of 4, `w*h >= 16384` and `lossless` is false; otherwise `None`. Plates, glyphs, hairlines and anything with exact keyer colour or 1-2 px detail is lossless. |
| `dds_header(path or bytes) -> dict` | w, h, mips, pfflags, fourcc, bits, masks, caps |
| `write_text(path, text, bom=False) -> bool` | LF line endings. A `.gui` / `.gfx` with non-ASCII text or a BOM raises ValueError (also under `python -O`), and nothing is written. |
| `write_loc(path, lang, entries, header=None) -> bool` | Writes BOM, LF, `l_<lang>:`, then ` KEY:0 "value"` lines. `entries` is a dict or (key, value) pairs. ValueError on a file name not ending in `_l_<lang>.yml`, a bad key or a real newline in a value. |
| `loc(key, lang="english", resolve=True)` | Looks the key up in the mod's localisation first, then vanilla. Lines with a trailing `# comment` count. `$OTHER_KEY$` (also `$OTHER_KEY\|Y$`) references to existing keys are resolved recursively. Engine-filled `$VARIABLE$`s stay as written. KeyError if the key is missing. |
| `labels_for(key) -> (ru, en)` | The resolved values without colour codes, for plate sizing. ValueError if a value still holds an engine-filled `$VARIABLE$`, because its width is unknown. |
| `text_advance(text, cell=4, font=None)`, `ink_width(...)` | `text_advance` is the engine's text width (sum of advances). `ink_width` drops the trailing 1-cell gap. With `font="totu_button"` (etc.) the real `.fnt` advances are used, so `№` counts as 10 cells. Raises ValueError on a missing glyph. |
| `big_plate_w(labels)`, `small_plate_w(labels)` | Bank width for `(ru, en, ...)`: 24n+40 or 12n+22. |
| `plate_w(labels, size, exact=False)` | With `exact=True`, returns PAD + the longest ink, for custom plates. |
| `plate_n(labels, size)`, `bank_width(n, size)` | Bank index (n) and its width. |
| `plate_sprite(labels, size="big", kind="plate")` | Returns the bank sprite name (see below). `kind`: `plate`, `slate`, `tab`, `toggle`, `toggle_r`. |
| `plate_sprite_for_key(key, size, kind)` | The same, from the RU and EN values of a loc key. |
| `bank_sprite(kind, n)`, `bank_kind(kind, size)`, `BANK` | The bank table that the builder generates. `bank_sprite` raises ValueError for an unknown kind or an n outside the bank. |
| `flat(w, h, rgb, alpha=1.0)`, `transparent(w, h, frames=1)` | Flat colour, or fully transparent. |
| `plate(w, h=40, colour=KEY_BLUE, tail=None)` | One plate frame with the stepped tail. The tail defaults to 12 above 24 px height, else 6. `tail=0` gives a plain block. |
| `slate_plate(w, h=40, tail=None)` | Slate plate for one-frame vanilla buttons; the engine shader brightens it on hover. |
| `plate_frames(w, h, frames=(None, KEY_BLUE, KEY_BLUE_DOWN), tail=None)` | Frames side by side; `None` is a transparent frame. `tail=0` gives flat blocks (list rows). |
| `bar_pair(w, h, fill=KEY_BLUE, track_alpha=0.18, fill_alpha=1.0) -> (full, empty)` | The two textures of a `progressbartype` at its full size. The engine reveals full over empty and stretches neither. `fill` is KEY_BLUE or P. |
| `progressbar_block(name, full_texture, empty_texture, size, horizontal=True)` | A `progressbartype` definition as vanilla writes it (`gfx/FX/progress.lua`, white colours). |
| `frames(*images)`, `split_frames(img, n)`, `over(base, layer, xy)` | Build or split frame strips; composite with clipping. |
| `pixel_text(text, cell=2, colour=P, k_edge=True, k_offset=2, line_gap=2, crt=True, bloom=False, pad=0, alpha=1.0) -> RGBA` | Draws any glyph in `GLYPHS`: Cyrillic, punctuation, `№`, accent aliases (as base capitals); lowercase draws as capitals. Details below. |
| `pixel_mask(text, cell, line_gap=2, crt=True)`, `pixel_text_size(text, cell)` | L mask and ink size. |
| `PICTO`, `draw_picto(name, cell=2, colour=P, k_edge=True, k_offset=2, alpha=1.0)`, `picto_size`, `picto_mask` | Pixel pictograms, drawn crisp. |
| `button_frame(w, h, picto=None, bg=None, bg_alpha=1, colour=P, cell=2, k_edge=True, alpha=1, tail=0, dx=0, dy=0)` | One button frame: background (or transparent) with the pictogram's ink centred. The ink moves up or left just enough that the K drop stays inside the frame, so it is never clipped. ValueError if ink plus drop are larger than the frame. |
| `sprite_block(name, texture, kind="spriteType", frames=None, effect=None, size=None, border=None, tiling=None, comment=None)` | One `.gfx` sprite definition in the mod's layout. |
| `gfx_file(blocks, header_lines)` | A whole `.gfx` file (`spriteTypes = { ... }`). |
| `EFFECT_ONLYDISABLE`, `EFFECT_NODOWN`, `EFFECT_BUTTONSTATE` | Effect file paths, as the mod and vanilla write them (`.lua`). |
| `declared_names(text)`, `existing_names(pattern="*.gfx", exclude=())`, `assert_declared(path, names, once=True)` | Collision and declaration checks. `existing_names` scans vanilla, DLC and mod interface folders. |
| `checker(w, h)`, `preview_bg(w, h, board=True, alpha=0.90)`, `zoom(img, k)`, `cornered(tex, w, h, border, tiling)` | Preview helpers. `cornered` draws a corneredTile at a size, as the engine does. |
| `contact_sheet(items, path, width=1800, bg="checker"\|"board"\|rgb, label_cell=1)` | Writes a PNG. `items` are `(label, img)` pairs, bare images, or strings (a section heading). |

`pixel_text` details:
- `cell` is an int or `(cx, cy)`; `(2, 3)` gives teletext double height.
- `crt=True` uses the fonts' rounding and gives the same pixels as `glyph_mask` on square cells.
- The K edge enlarges the image by `k_offset`. The ink's top-left is at `(pad, pad)`.
- It draws no real accent marks; only the in-game `totu_h36` font does.

**Pictogram names:** `close`, `chevron_left/right/up/down` (bold, 5x7), `chevron_left_s/right_s/up_s/down_s` (bold, 4x5, for 16 px buttons), `plus`, `minus`, `menu`, `question`, `exclamation`, `star`, `play`, `pause`, `check`, `dot`, `square`, `triangle_up/down/left/right`, `gear`, `lock`, `cloud`, `trash`, `refresh`.

## Plate bank (`interface/totu_widgets.gfx`)

`n` is the length of the longer RU / EN label, counted in 5-column glyphs. Use `plate_sprite`, which measures with the real font and rounds `№` up.

| Sprite | Height | n | Width | Frames | Type | Font |
|---|---|---|---|---|---|---|
| `GFX_totu_plate_<w>` | 40 | 1-18 | 24n+40 (64..472) | transparent / keyer / pressed | textSpriteType, onlydisable | `buttonFont = "totu_button"` |
| `GFX_totu_plate_s_<w>` | 24 | 1-40 | 12n+22 (34..502) | transparent / keyer / pressed | textSpriteType, onlydisable | `totu_button_small` |
| `GFX_totu_slate_<w>` | 40 | 1-18 | 24n+40 | slate / keyer / pressed | textSpriteType, onlydisable | `totu_button` |
| `GFX_totu_slate_s_<w>` | 24 | 1-40 | 12n+22 | slate / keyer / pressed | textSpriteType, onlydisable | `totu_button_small` |
| `GFX_totu_tab_s_<w>` | 24 | 1-24 | 12n+22 | off transparent / on keyer / disabled transparent | spriteType, onlydisable | for `checkboxType` tabs: a label box of the full plate width w, `format = centre` |
| `GFX_totu_toggle_s_<w>` | 24 | 1-24 | 12n+22 | off transparent / on keyer | spriteType, onlydisable | `checkboxType` chips / toggles: label box as for tabs |
| `GFX_totu_toggle_r_s_<w>` | 24 | 1-24 | 12n+22 | keyer / transparent (frame 1 = on) | spriteType, onlydisable | `buttonType` tabs whose frame the engine sets (`settings_tab_*`): `font` + `text` on the button |

```python
tb.plate_sprite(("Применить", "Apply"))               # GFX_totu_plate_256
tb.plate_sprite(("Сбросить", "Reset"), "small")       # GFX_totu_plate_s_118
tb.plate_sprite(("Сохранить", "Save"), kind="slate")  # GFX_totu_slate_256
tb.plate_sprite(("Игра", "Game"), "small", "tab")     # GFX_totu_tab_s_70
tb.plate_sprite(("Управление", "Controls"), "small", "toggle_r")   # GFX_totu_toggle_r_s_142
tb.plate_sprite_for_key("TOTU_FE_BACK")               # GFX_totu_plate_160
```

Some common widths:
- Big: n 4 = 136, 5 = 160, 7 = 208, 9 = 256, 10 = 280, 12 = 328, 14 = 376.
- Small: n 4 = 70, 5 = 82, 8 = 118, 11 = 154, 12 = 166, 14 = 190, 16 = 214, 17 = 226.

`GFX_totu_plate_<w>` and `GFX_totu_plate_s_<w>` are pixel-identical to the menu's `GFX_totu_caption_<w>` / `GFX_totu_caption_small_<w>`. New screens should use the bank names.

- **Transparent plates** (frame 1 is white text on the board) are for menus where the label must read as a caption.
- **Slate plates** are for dialogs and in-game windows, where a button must be visible before it is hovered.
- **Labels longer than the bank** (18 big / 40 small / 24 tab) raise ValueError. Shorten the label, use the small size, or build your own plate with `plate_frames`.
- **Keys:** a vanilla key on a plate (e.g. `SM_APPLY` "ОК") needs `totu_caption_name`-style CJK fallbacks. `totu_button*` have none, so put `TOTU_FE_*` keys on plates.

## Other kit sprites

All sprites are declared in `interface/totu_widgets.gfx`; the textures are in `gfx/interface/totu/widgets/`.

**Surfaces.** All are corneredTile with `tilingCenter = yes`, so they stretch to any container. The flat surfaces have `borderSize 0`. The stretchable keyer and slate tiles have `borderSize {12 0}` / `{6 0}`, so the tail is their unstretched right border. The boards, field tile, rows and stretchable plates use the nodowneffect effect.

| Sprite | Texture | Use |
|---|---|---|
| `GFX_totu_board_ig` | 16x16, board at 0.90 | in-game window background |
| `GFX_totu_board_solid` | 16x16, board at 1.0 | dropdown lists, chat input, popups over busy art |
| `GFX_totu_raised` | 16x16, (18,22,30) at 0.92 | sub-panel on a board (list area, info block) |
| `GFX_totu_field_tile` | 16x16, D at 14 % | container background for a field (dropdown face) |
| `GFX_totu_field_<w>` | same texture, `size` w x 32, for w in 96, 150, 190, 216, 260, 300, 376, 416, 456, 600 | `iconType` under an editBox |
| `GFX_totu_hairline` | 16x16, D at 22 %, size 16x1 | container background (container height 1 or 2) |
| `GFX_totu_hairline_<w>` | same, w x 1, same widths as the fields | `iconType` separator |
| `GFX_totu_row_hl` | keyer at 100 % | selected list row |
| `GFX_totu_row_hover` | D at 8 % | list row hover |
| `GFX_totu_keyer_tile` / `GFX_totu_slate_tile` | 48x16, `borderSize {12 0}`; the right border is the 12 px tail | plate with tail at any size (default 160x40) |
| `GFX_totu_keyer_tile_s` / `GFX_totu_slate_tile_s` | 24x16, `borderSize {6 0}` | the same with the small 6 px tail (default 118x24) |

**Buttons.** Pictograms are P with the K drop, on transparent / keyer / pressed backgrounds.

| Sprite | Frame size | Frames | Effect | Use |
|---|---|---|---|---|
| `GFX_totu_close` | 24x24 | 3: x on transparent / keyer / pressed | onlydisable | close and delete buttons |
| `GFX_totu_expand` | 20x20 | 2: expanded "v" / collapsed ">" (as `GFX_expand_collapse_sideways`) | none | group headers |
| `GFX_totu_dropdown` | 20x20 | 3: "v" | onlydisable | `dropDownBoxType` expandButton |
| `GFX_totu_step_left` / `_right` | 20x20 | 3: chevron | onlydisable | free-standing value steppers (replaces `button_left` / `button_right`) |
| `GFX_totu_step_left_4f` / `_right_4f` | 16x16 | 4: small chevron (`chevron_*_s`) + disabled (D at 30 %) | `buttonstate.lua`, like `yearslider_leftbutton` | value slider end buttons. They are as tall as the slider, so knob, line and chevron share one centre line. |
| `GFX_totu_plus` / `GFX_totu_minus` | 20x20 | 3 | onlydisable | +/- steppers |
| `GFX_totu_save_entry` | 376x48 | 2: transparent / keyer plate with tail | none | a proposal for the shared `savegame_item` BackgroundButton (see "Not in the kit") |

**Slider and scrollbar parts.**

| Sprite | Size | Notes |
|---|---|---|
| `GFX_totu_slider_knob` | 12x16, 4 frames | P 8 px block / keyer with P stripe / pressed / D at 30 %. Like `yearslider_slider2`: no effect. |
| `GFX_totu_slider_track` | corneredTile, 16x16 texture, size 276x16 | 2 px D line at 35 % on rows 7-8; tiles, so the line stays crisp |
| `GFX_totu_scroll_knob` | spriteType, 8x24, 3 frames | P at 70 % / keyer / pressed, onlydisable. It is a plain spriteType like every vanilla thumb (`GFX_scroll_drager`), so its length is fixed. |
| `GFX_totu_scroll_knob_h` | spriteType, 24x8, 3 frames | the same, horizontal |
| `GFX_totu_scroll_track` | corneredTile, 8x8 | 2 px D line at 18 %, centred (vertical) |
| `GFX_totu_scroll_track_h` | corneredTile, 8x8 | 2 px D line at 18 %, centred (horizontal) |
| `GFX_totu_scroll_up/_down/_left/_right` | 12x12 | pixel triangles in P with the K drop. The ink is at x (or y) 0..9 and the drop reaches 11, so nothing is clipped. No effect, as vanilla `GFX_scroll_up`. |

**Scrollbar column geometry** (`totu_vertical_slider`; the horizontal type is the same turned): the column is 12 px wide, and every part is centred on the line between x 5 and x 6.
- The arrows' ink is at x 0..9.
- The track sits at x 1, so its 2 px line is at x 4..5.
- The knob is placed relative to the track, as in vanilla (`right_vertical_slider` puts its 16 px drager at -2 on a 12 px track), so it sits at x 1..8.

**Existing frontend sprites that are still valid** (`interface/totu_menu.gfx`):
- `GFX_totu_board` (0.84, frontend)
- `GFX_totu_checkbox` (20x20, 2 frames: D at 30 % / keyer)
- `GFX_totu_field` (376x32)
- `GFX_totu_tab` (118), `GFX_totu_chip` (110), `GFX_totu_toggle` (118)
- `GFX_totu_band_top/bottom`, `GFX_totu_scrim_*`, `GFX_totu_caption_*`

## Scrollbar types (`interface/totu_widgets.gui`)

| Type | Kind | Mirrors (vanilla 1.19.3) | Use |
|---|---|---|---|
| `totu_vertical_slider` | extendedScrollbarType | `right_vertical_slider` (no background) | `verticalScrollbar = "totu_vertical_slider"` on a containerWindowType |
| `totu_horizontal_slider` | extendedScrollbarType | `bottom_horizontal_slider` | `horizontalScrollbar = "totu_horizontal_slider"` |
| `totu_listbox_slider` | scrollbarType | `standardlistbox_slider` | `listboxType`: `scrollbartype = "totu_listbox_slider"` |
| `totu_text_slider` | scrollbarType | `standardtext_slider` | long text boxes (popup descriptions): `scrollbartype = "totu_text_slider"` |
| `totu_value_slider` | scrollbarType | the horizontal sliders of `settings.gui` | template: copy its body into each inline slider |

The engine looks `settings.gui` sliders up by their own name, so the value slider cannot be referenced by name. Copy the block and change `name`, `size`, `position`, `maxValue` and `stepSize`. The element names (`landslider_SliderButton`, `listboxSliderButton`, `Slider`, `Track`, `Decrease`, `Increase`, ...) are vanilla and must stay.

## .gui snippets

**Plate button with engine-centred text:**

```
buttonType = {
	name = "accept_button"				# keep the vanilla name
	position = { x = 384 y = 552 }
	quadTextureSprite = "GFX_totu_plate_256"	# tb.plate_sprite(("Применить", "Apply"))
	buttonText = "TOTU_FE_APPLY"
	buttonFont = "totu_button"			# totu_button_small on GFX_totu_plate_s_* / slate_s_*
	clicksound = click_default
	oversound = ui_menu_over
}
```

The engine centres the label's advance in the whole plate. Because PAD_L = PAD_R + TAIL, the ink of the longer label sits on the plate's PAD_L. The advance includes the trailing 1-cell gap, so the ink starts at 20 px (11 px on small plates), measured with the real fonts. This matches the menu's plates. If the engine shows or hides the button, use `buttonText`, never a separate label box.

**Board container with a title:**

```
containerWindowType = {
	name = "my_window"
	position = { x = -320 y = -300 }
	size = { width = 640 height = 600 }
	orientation = center
	moveable = no
	background = {
		name = "background"
		quadTextureSprite = "GFX_totu_board_ig"	# GFX_totu_board in the frontend
	}
	instantTextBoxType = {
		name = "title"
		position = { x = 22 y = 22 }
		font = "totu_caption_name"
		text_color_code = P
		borderSize = { x = 0 y = 0 }
		maxWidth = 596
		maxHeight = 18
		fixedsize = yes
		format = left
		text = "SM_OPTIONS"
	}
	# separator under a header: a 1 px container with the hairline as background
	containerWindowType = {
		name = "totu_rule"
		position = { x = 22 y = 84 }
		size = { width = 596 height = 1 }
		background = { name = "bg" quadTextureSprite = "GFX_totu_hairline" }
	}
}
```

**Checkbox with a label** (row y; the label starts 28 px right of the 20 px box):

```
checkboxType = {
	name = "pause_on_popup_active"
	position = { x = 22 y = 102 }			# row + 6
	quadTextureSprite = "GFX_totu_checkbox"
	clicksound = click_checkbox
}
instantTextBoxType = {
	name = "pause_on_popup_title"
	position = { x = 50 y = 105 }			# row + 9
	font = "totu_caption_name"
	text_color_code = P
	borderSize = { x = 0 y = 0 }
	maxWidth = 568
	maxHeight = 18
	fixedsize = yes
	format = left
	text = "PAUSE_ON_POPUPS"
	alwaystransparent = yes
}
```

**Field and editBox** (an editBox has no background of its own; the icon goes first so it is drawn under the box):

```
iconType = {
	name = "save_name_field"
	spriteType = "GFX_totu_field_300"
	position = { x = 318 y = 398 }
	alwaystransparent = yes
}
editBoxType = {
	name = "save_name"
	position = { x = 318 y = 398 }
	size = { x = 300 y = 32 }
	font = "totu_caption_name"			# or a vanilla body font for free text
	borderSize = { x = 8 y = 9 }
	text = ""
}
```

**Tabs.** Tabs come in two engine types. Keep the vanilla element's type (rule 5) and pick the snippet that matches it.

*`checkboxType` tabs* (the engine switches them as checkboxes, e.g. `localgames_tab` / `remotegames_tab` in vanilla `ingamemenu.gui` and the load board). A checkbox carries no text, so it gets a label box over it. The label box spans the full plate width w with `format = centre`, which puts the ink where `buttonText` would (on PAD_L). Gaps are 12 px.

```
checkboxType = {
	name = "localgames_tab"				# vanilla checkboxType: keep name and type
	position = { x = 22 y = 52 }
	quadTextureSprite = "GFX_totu_tab_s_118"	# tb.plate_sprite(("На диске", "Local"), "small", "tab")
	clicksound = click_checkbox
}
instantTextBoxType = {
	name = "localgames_label"			# the vanilla label of that tab (or a new totu_* name)
	position = { x = 22 y = 57 }			# tab x; tab y + 5
	font = "totu_label"				# TOTU_* key; totu_caption_name for a vanilla key
	text_color_code = P
	borderSize = { x = 0 y = 0 }
	maxWidth = 118					# = the plate width w
	maxHeight = 18
	fixedsize = yes
	format = centre
	text = "TOTU_FE_TAB_LOCAL"			# a new key of your area (RU "На диске")
	alwaystransparent = yes
}
```

The lobby's fixed-width `GFX_totu_tab` (118) and `GFX_totu_chip` (110) labels use a box of w - 6, centred on the solid part. That suits fixed plates with labels of any length. Bank plates are sized to their label, so use w.

*`buttonType` tabs whose frame the engine sets*. Vanilla `settings_tab_1..4` are like this: 2-frame `GFX_settings_ingame_tab`, with `font` + `text` on the button itself. They stay `buttonType`, and the label goes on the button:

```
buttonType = {
	name = "settings_tab_1"				# vanilla buttonType: keep name and type
	position = { x = 22 y = 52 }
	quadTextureSprite = "GFX_totu_toggle_r_s_70"	# tb.plate_sprite(("Игра", "Game"), "small", "toggle_r")
	font = "totu_button_small"
	text = "TOTU_FE_TAB_GAME"
	clicksound = click_checkbox
	oversound = ui_menu_over
}
```

- `GFX_totu_toggle_r_s_<w>` shows the keyer on frame 1. This assumes the vanilla art's frame 1 (`tab_small_110.dds`, the raised tab) is the active one.
- If the inactive tabs light up in game, switch to `GFX_totu_toggle_s_<w>` (frame 2 keyer). Both banks have every width, so no rebuild is needed.

**List with the kit scrollbar:**

```
containerWindowType = {
	name = "games"
	position = { x = 22 y = 96 }
	size = { width = 596 height = 360 }
	verticalScrollbar = "totu_vertical_slider"
	background = { name = "bg" quadTextureSprite = "GFX_totu_raised" }
	gridBoxType = {
		name = "games_grid"
		position = { x = 0 y = 0 }
		size = { width = 376 height = 100%% }
		slotsize = { width = 376 height = 52 }
		format = "UPPER_LEFT"
		max_slots_horizontal = 1
	}
}
# entry template: buttonType "BackgroundButton" with quadTextureSprite = "GFX_totu_save_entry" (376x48),
# or the save/load stream's own entry (see "Not in the kit")
```

**Stepper** (row y; value centred between the buttons):

```
buttonType = { name = "decrease_resolution_button" position = { x = 342 y = 102 } quadTextureSprite = "GFX_totu_step_left" }
instantTextBoxType = { name = "resolution_value" position = { x = 362 y = 105 } font = "totu_caption_name"
	text_color_code = P maxWidth = 236 maxHeight = 18 fixedsize = yes format = centre borderSize = { x = 0 y = 0 } }
buttonType = { name = "increase_resolution_button" position = { x = 598 y = 102 } quadTextureSprite = "GFX_totu_step_right" }
```

**Value slider** (copy of `totu_value_slider` under the vanilla name):

```
scrollbarType = {
	name = "mastervolume_slider"
	slider = "landslider_SliderButton"
	track = "landslider_TrackButton"
	leftbutton = "landslider_upButton"
	rightbutton = "landslider_downButton"
	size = { x = 276 y = 16 }
	position = { x = 342 y = 104 }
	priority = 100
	borderSize = { x = 16 y = 16 }
	maxValue = 100
	minValue = 0
	stepSize = 1
	startValue = 20
	horizontal = 1
	guiButtonType = { name = "landslider_SliderButton" quadTextureSprite = "GFX_totu_slider_knob" position = { x = 0 y = 0 } }
	guiButtonType = { name = "landslider_TrackButton" quadTextureSprite = "GFX_totu_slider_track" position = { x = 0 y = 20 } }
	guiButtonType = { name = "landslider_upButton" quadTextureSprite = "GFX_totu_step_left_4f" position = { x = 0 y = 0 } clicksound = click_scroll }
	guiButtonType = { name = "landslider_downButton" quadTextureSprite = "GFX_totu_step_right_4f" position = { x = 0 y = 120 } clicksound = click_scroll }
}
```

Every part is 16 px tall (knob 12x16, track line on rows 7-8, end buttons 16x16). The row is therefore centred whether or not the engine centres the buttons. The `y = 20` / `y = 120` positions are vanilla's and are kept.

## Not in the kit: build these in your area

The kit holds what several windows share. The items below were planned in `frontend.md` section 4 or `hero.md`, but belong to one window. Build them in your own area with the kit's primitives (rule 2: `gfx/interface/totu/<area>/`, `GFX_totu_<area>_*`).

| Item | Planned | Owner | Build with |
|---|---|---|---|
| Progress bars (fill + track) | spec: fill keyer or P, track D at 18 % | the stream whose window has the bar (topbar/HUD, achievements, ...) | `full, empty = tb.bar_pair(w, h)` (or `fill=tb.P`), `tb.save_dds` both, `tb.progressbar_block(name, full_tex, empty_tex, (w, h))`. `progressbartype` textures do not stretch, so make one pair per bar size. |
| MP column headers `sort_89`, `sort_134`, `sort_246` | w x 24, 3 frames transparent / keyer / pressed | multiplayer | `tb.plate_frames(w, 24)` (small tail), or the bank `GFX_totu_plate_s_<w>` when the width can follow the label |
| MP server row `row_972` | 972x30, 2 frames transparent / keyer | multiplayer | `tb.plate_frames(972, 30, (None, tb.KEY_BLUE), tail=0)` |
| Music player track row `row_557` | 557x30 | credits / music / achievements | `tb.plate_frames(557, 30, (None, tb.KEY_BLUE), tail=0)` |
| Settings tabs | 2 frames, engine-set | options | the bank: `GFX_totu_toggle_r_s_<w>` (see Tabs above); nothing to build |
| Save / load entry | `frontend.md`: 720x48 (2 x 360); `hero.md`: re-point `GFX_load_save_entry2` in place, 624x54 (2 x 312) | Esc menu + save/load | The kit's `GFX_totu_save_entry` (2 x 376x48) is only a proposal that fits the load board's 376 grid. If `savegame_item` keeps the vanilla size, re-point `GFX_load_save_entry2` in the mod's `frontendgamesetupview.gfx` at a 624x54 texture made with `tb.plate_frames(312, 54, (None, tb.KEY_BLUE))`. |

## A minimal stream builder

```python
"""tools/build_options_gfx.py: textures of the options window (area 'options')."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import totu_broadcast as tb

AREA = "options"
OUT = tb.TOTU_TEX / AREA
GFX = tb.INTERFACE / f"totu_{AREA}.gfx"

def main():
    img = tb.frames(tb.button_frame(24, 24, "gear"), tb.button_frame(24, 24, "gear", tb.KEY_BLUE))
    blocks = [tb.sprite_block("GFX_totu_options_gear", f"gfx/interface/totu/{AREA}/gear.dds",
                              frames=2, effect=tb.EFFECT_ONLYDISABLE)]
    text = tb.gfx_file(blocks, ["Twilight of the Union: options sprites (tools/build_options_gfx.py)."])
    # check first, write after: a failed check must not leave files in the mod folder (it syncs through OneDrive)
    names = tb.declared_names(text)
    assert len(names) == len(set(names)), names
    clash = {n: v for n, v in tb.existing_names("*.gfx", exclude=[GFX]).items() if n in names}
    assert not clash, clash
    tb.save_dds(img, OUT / "gear.dds")
    tb.write_text(GFX, text)
    tb.contact_sheet([("gear", tb.zoom(tb.over(tb.preview_bg(48, 24), img), 3))], tb.PREVIEW / f"{AREA}.png", bg="board")

if __name__ == "__main__":
    main()
```

## Check in game (could not be verified offline)

- Frame order: frame 2 is hover and frame 3 is pressed. This is confirmed by the menu's caption plates. Still to check:
  - whether frame 4 is "disabled" on the 4-frame step buttons;
  - whether a checkboxType tab shows frame 2 when on (the menu's load tabs suggest it does);
  - which frame of an engine-set `settings_tab_*` is the active one (`toggle_r` vs `toggle`);
  - whether the engine switches the scroll knob's frames on hover. If it does not, the knob simply stays at frame 1 (P at 70 %).
- Scrollbar layout: positions inside `totu_*_slider` follow the vanilla convention: the knob is placed relative to the track, and the increase button is anchored at the far corner. Look at the knob and arrow alignment on the first window that uses them. The listbox and text types keep vanilla's numbers.
- `GFX_totu_keyer_tile` / `slate_tile`: the right border of the corneredTile should stay unstretched, so the tail keeps 12 px.
- `iconType` with a `corneredTileSpriteType` (`GFX_totu_field_<w>`, `GFX_totu_hairline_<w>`) draws at the sprite's `size`.
