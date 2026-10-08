# In-game texture pipeline (broadcast style)

`tools/build_ingame_gfx.py` writes a broadcast version of every live vanilla chrome texture into the mod, at the
vanilla path and the vanilla pixel size, so no `.gfx` or `.gui` file has to change. A texture is drawn by the
**area module** that claims it (`tools/ingame/<area>.py`), or else by the **generic treatment**
(`tools/ingame/generic.py`), which already makes the whole vanilla UI read as flat, cold broadcast chrome.

**Which kit do I use?** This pipeline restyles *vanilla textures in place* (same path, same size). New sprites of
your own (`GFX_totu_*` under `gfx/interface/totu/<area>/`, new `.gfx` entries, pixel text, plates for `.gui`
rewrites) come from the sprite-level kit `tools/totu_broadcast.py` (docs: `docs/ui_kit.md`). Both use the same
palette; `generic.check_palette()` warns on every run if they ever disagree.

```
tools/build_ingame_gfx.py        orchestrator (owner rules, dark-text scan, jobs, writing, previews, checks)
tools/ingame/generic.py          generic treatment + Ctx + drawing helpers + palette
tools/ingame/<area>.py           area modules (stream agents); tools/ingame/_*.py = private helpers
tools/data/chrome_manifest.json  1,792 chrome textures from the mapping pass (1,549 live + 3 EXTRA_LIVE)
tools/data/ingame_owners.json    owner area of every live texture, dark-text hosts, generic modes, paper list
tools/data/ingame_outputs.txt    every file the pipeline wrote + its producer (drives stale-file deletion)
tools/preview/ingame_*.png       contact sheets (git-ignored)
```

## Commands (from the mod root)

| Command | What it does |
|---|---|
| `python tools/build_ingame_gfx.py` | Full run: every live texture plus module extras (about 20 s on 11 workers). Deletes files **listed in `ingame_outputs.txt`** that are no longer produced, and nothing else; rewrites `ingame_owners.json`. The full run belongs to the pipeline owner. |
| `--only kit,views` | Builds only the paths these areas produce. **Stream agents use this**: areas never share a path, so parallel runs never write the same file. Unknown area names are rejected. |
| `--generic-only` | Builds only the paths no module claims. |
| `--paths "techtree/*,tiles/tiled_window.dds"` | Restricts any command (fnmatch on the path relative to `gfx/interface`). |
| `--list kit` | Job table of an area: path, owner, producer, class, size, frames, vanilla format, vanilla mips, generic mode, dark text (yes / no / ?), and why that mode was chosen. |
| `--preview kit` | `tools/preview/ingame_kit[_N].png`: vanilla and result side by side over the board with a mid-grey checker (stand-in for the map), what the game sees (DXT5 decoded); `paper` marks a kept light surface. Writes no texture. `--per-sheet N` (default 120); `--preview all --paths ...` for a sample. |
| `--verify` | Every listed output: exists, same size as vanilla, no mipmaps, allowed format, decodes, and the **semantic colour check** (below). Exit 1 on a problem. |
| `--sizes` | Disk size of the outputs by area and format. |
| `--owners` | Re-derives `ingame_owners.json` and prints counts and MB per area. |
| `--import-manifest PATH` | Refreshes `chrome_manifest.json` from a full mapping-pass manifest. |

Other options: `--jobs N`, `--game PATH` (or env `HOI4_DIR`), `--skip-broken` (full run that skips modules that
fail to import; stale deletion is then disabled and the broken modules' outputs stay), `--no-dxt-odd` (old format
policy, see Budget). `tools/build_hud_gfx.py` is a stub that forwards to this script.

## Areas and owners

Every live texture has exactly one owner area. The rules are `OWNER_RULES` in `build_ingame_gfx.py`; the first
match wins, and `rule_of` in the JSON says which rule matched. `AREAS` in `tools/ingame/__init__.py` lists them in
rule order.

| Area | Textures | Vanilla MB | Rules |
|---|---|---|---|
| events | 12 | 10.4 | sprite defined in `eventwindow.gfx`; used only by `eventwindow.gui`; `events/**`; root `event_*.dds` |
| topbar | 218 | 13.2 | topbar **and the HUD on the map**: `topbar/**`, `alerts/**`, `mapmode/**`, `gfx/minimap/**`; classes minimap / menubar / topbar / **outliner** (army-group panel, `leadergroups.gui`); `unitcontrol/**`; `ingameclock_bg`, `date_pause_button*`, `world_tension_icon_big_strip`, `wt_anim_strip`, `decisionview/decisions_glow*`, `reopen_lobby`; used only by topbar / ingameclock / minimap / mapmodes_interface / alerts / menubar / **battleplantools / leadergroups / theatreselector** .gui |
| rules | 3 | 0.1 | game rules: `EXTRA_LIVE` (`changed_slider_indicator`, `custom_difficulty_slider_bg`, `expand_collapse_sideways`: scope frontend_done, but the mod's `frontendgamesetupview.gui` still shows them in the game-rule / difficulty windows); used only by `savedgamerules.gui` (its other textures are shared with `ingamemenu.gui` and belong to esc) |
| esc | 7 | 0.7 | used only by `ingamemenu.gui`; `load_save_*`, `save_load_file_*`, `no_frame_special_bg`, `in_game_menu_dark_overlay` |
| settings | 8 | 1.2 | used only by `settings.gui`; `settings_popup_bg`, `tab_small_110`, `fullborder_tiled` |
| popups | 18 | 5.4 | sprite defined in `popupwindow.gfx` (not `tiles/**`); `diplo_popup_*`; `notifications/**`; used only by popupwindow / notifications .gui |
| mp | 28 | 4.7 | used only by frontendmultiplayerview / matchmaking(_chat) / playerlobby / hotjoin / chat / ingamelobby .gui |
| misc | 64 | 25.9 | `career_profile/**`; `music_station_*`; used only by achievements / musicplayer / music_station / credits / subscription / browser / social / friends / pops_login / pdx_online .gui |
| trees | 210 | 48.8 | `focusview/**`, `techtree/**`, `decisionview/**` (rest), `doctrines/**`, `trait_window/**`, `tiles/tiled_focus_bg`; used only by nationalfocusview / countrytechtreeview / countrydecisionview / countrydoctrinetreeview / doctrines_view / *traittreewindow .gui |
| kit | 334 | 22.1 | `tiles/**`; used by 3 or more .gui files; root-folder textures of class button, checkbox, scrollbar, slider, dropdown, tab, textfield, tooltip, tiled_window, frame; other root-folder in-game textures |
| views | 649 | 136.2 | classes view_bg, panel_bg, list_entry, header, bar, separator, frame (not menu scope); the remaining per-view folders (`naviesview/`, `operations/`, `special_project/`, ...) |
| generic | 1 | 0.05 | what is left (one menu texture, `generic_bg_417.dds`) |

The views area is big but mostly per-view parts; a views stream can work through it folder by folder
(`--list views --paths "naviesview/*"`).

A module may claim paths outside its owner area (the build prints a warning: agree on it with that area), and
vanilla paths outside the manifest (the build prints a note: make sure it is chrome, not content). Two modules may
never claim the same path (the build stops).

## Writing an area module

```python
# tools/ingame/kit.py
from ingame import generic as g      # helpers and palette; or use only ctx

AREA = "kit"                          # must equal the file name

def button_plate(ctx, src):
    # src: vanilla RGBA (PIL), ctx.w x ctx.h; return an RGBA image of exactly that size, or None = keep vanilla
    img = ctx.blank()
    img.paste(ctx.plate(ctx.w, ctx.h - 4, rgb=ctx.SLATE), (0, 2))   # SLATE plate with the stepped tail
    return img

def header(ctx, src):
    out = ctx.generic(src)            # start from the generic treatment
    return g.hairline(out, (0, ctx.h - 2, ctx.w, ctx.h))            # D at 22 %, 2 px

TEXTURES = {
    "button_123x34.dds": button_plate,
    "header_bg.dds": header,
}
LOSSLESS = {"header_bg.dds"}          # optional: never DXT5 (pixel-exact edges, pixel type)
```

Then run `python tools/build_ingame_gfx.py --preview kit`, look at the sheet, and run `--only kit` to write.

Keys are paths relative to `gfx/interface` (a `gfx/interface/` prefix is accepted) or `gfx/minimap/...`. Case
does not matter; the on-disk spelling is used. `gfx/interface/totu/**` and `..` are refused. Files in
`tools/ingame/` starting with `_` are not modules (use them for shared private helpers).

### `ctx` (generic.Ctx)

| Field | Meaning |
|---|---|
| `path`, `entry` | key, manifest dict (None outside the manifest): `class`, `frames`, `border`, `sprites`, `guis`, `effect_files`, `sprite_kinds`, `mips`, `dark_text`, ... |
| `vanilla_path`, `out_path` | absolute source and destination |
| `area`, `owner` | producing area, owner area by the rules |
| `w`, `h`, `frames`, `frame_w`, `frame_h` | vanilla size; frames sit side by side (`noOfFrames`) |
| `border`, `borders` | corneredTile `borderSize` of the first sprite as `(x, y)`, all of them |
| `cls` | manifest class |
| `lossless` | set `True` to force uncompressed output for this texture |
| `dxt` | set `True` to force DXT5 (even small or odd sizes), `False` for uncompressed; `None` (default) = policy |
| `dark_text` | `True` when a .gui draws dark text (typewriter / `*_black` fonts, colour code `b`) over this texture, `False` when no .gui does, `None` when unknown (engine-only sprites) |
| palette | `BOARD`, `BOARD_ALPHA` (0.90 in game), `BOARD_ALPHA_FE` (0.84), `RAISED`, `RAISED_ALPHA`, `SLATE`, `FIELD`, `FIELD_A`, `FIELD_ALPHA`, `P`, `D`, `K`, `KEY_BLUE`, `KEY_BLUE_DOWN`, `TAIL_ALPHA`, `HAIRLINE_ALPHA`, `TRACK_ALPHA`, `SCROLL_KNOB_ALPHA`, `DISABLED_ALPHA`, `SEM_G`, `SEM_R`, `SEM_Y`, `DONE_G` |
| `generic(src, mode=None, **opts)` | generic treatment as a starting point; `mode` / `Opts` fields override (e.g. `mode="flatten", levels=1`, `tones=("raised",)`, `mode="state", state="done"`) |
| `generic_mode(src)` | the mode generic would pick |
| `split(img)`, `join(parts)`, `per_frame(img, fn)` | frame helpers |
| `blank()`, `flat(rgb, alpha)`, `plate(w, h, rgb, alpha, tail)` | surfaces; the plate tail is 12 px (6 + 6) for h >= 30 (40 px frontend plates and the 32-36 px vanilla buttons), else 6 px (3 + 3) |
| `vanilla(key)` | RGBA of another vanilla texture |
| `warn(msg)` | printed by the build |

`generic.py` also exports: `flat`, `plate`, `big_plate_w(n)` (40 px plate: 22 + (24n - 4) + 10 + 12),
`small_plate_w(n)` (24 px plate: 12 + (12n - 2) + 6 + 6), `hairline`, `pictogram(rows, cell=2, rgb=P, drop=True)`
(pixel grid, '#' = lit, K drop at +cell), `paste_center`, `split_frames`, `join_frames`, `per_frame`, `treat`,
`mode_for`, `Opts`, `state_of(path)`, `STATE_TONES`, the modes `regrade`, `caption`, `quiet`, `flatten`, `keyer`,
`knob`, `state_plate`, `clear`, and colour tools (`luma`, `hue_sat_val`, `semantic_weight`, `legible`,
`colour_profile`, `gauss`, `masked_gauss`, `ramp`).

## The generic treatment

Picked per texture by `mode_for(path, entry, img)`, in this order: `OVERRIDES` (fnmatch table), content `.gfx`
guard (`CONTENT_GFX`: textures defined only in `Technologies.gfx` stay vanilla), class mode (with glows, frames
around holes and plain caption plates detected), selected / active names, colour guard. `--list` prints the mode
and the reason for every texture.

| Mode | Used for | Result |
|---|---|---|
| regrade | button, checkbox, scrollbar, slider, dropdown, bar, separator, topbar, minimap, outliner, menubar, small panels | Luma onto board -> slate -> D -> P with a plateau on the vanilla mid-tones; gold / brown / tan / copper lose their colour. Plate silhouettes lose rim, bevel and scratches: body = SLATE (paper and gold bodies too, their dark glyphs turn light), icons and glyphs stay, a gold / orange "selected" rim becomes keyer blue. **Semantic pixels keep their vanilla hue and saturation** (value lifted to at least 0.45): red (and orange-red in red-dominated textures such as `arrow_down_small`, `bop` orange), green (incl. teal), blue, yellow where enabled (bars, priority lights). A plate body in a signal colour becomes one flat muted version of that hue. |
| caption | plain one-frame text buttons (wide plates, no glyphs; dark-body and paper / gold bodies) | SLATE caption plate with the stepped tail over the vanilla box (no rivets, no rounded ends) |
| quiet | frames around a hole (flag, leader, portrait frames) | dark slate frame; signal red / green kept |
| flatten | view_bg, panel_bg, tiled_window, header, big list entries, tab, tooltip, textfield | flat tones board (9,11,16) a .90 / raised (18,22,30) a .92 / field (D 14 % over board); layout regions snapped to rectangles; painted art, ornaments, thin rims and frame-edge bars removed. Big backgrounds (view_bg / panel_bg >= 150 px) keep their sub-panels as separate tones and their long straight dividers as 1 px D hairlines at 22 %. Small signal marks (red / green lights, ticks) inside a panel keep their colour; a signal-coloured surface keeps a dark tint of its hue. Selected 2-frame tab = keyer plate; selected 2-frame list entry and `*_selected` / `*_active` entries = 4 px keyer bar at the left. Multi-frame textures whose frames would come out identical fall back to a regrade. **Paper**: see below. |
| state | tree state plates (`focusview/titlebar/focus_*_bg`, joint plates, `techtree/technology_*_item_bg`, `subtechnology_*`, `operatives/upgrade_button_*`, `techtree/*researching*anim_strip`) | the plate body becomes one flat rectangle in the state tone (`STATE_TONES`): ready (available / can_start) SLATE, done (completed / researched) `DONE_G` (40,75,46, semantic G over the board), blocked (unavailable) RAISED, branch RAISED with a D hatch, active (researching / current) KEY_BLUE. Joint focus plates keep their flag ribbons (content) below the body. |
| keyer | neutral / gold glows and highlights; selection frames and fills (`tiles/tiled_selection*`, `*_selected` / `*_active` outlines, `abilitylist/ability_active_bg*`); a flat selection fill becomes exactly KEY_BLUE | keyer blue in the vanilla shape |
| knob | glossy scroll / slider knobs (`scroll_drager`, `scrollbar_slider*`, `career_profile/scroll_thumb`, colour picker drager) | flat disc in the vanilla silhouette: P at 70 %, hover P, pressed keyer, disabled D at 30 % |
| keep | click blockers (`tiles/tiled_window_transparent*`), flag-shading overlays, **signal glows** (red / green / yellow / alert / failed / completed glows keep their vanilla colour), content the manifest calls chrome (colour picker ramps, album covers, `seized_equipment_item`, doctrine medallions, debug placeholders), textures defined only in a content `.gfx` | vanilla file stays (nothing is written) |

**Colour guard.** A texture with at least 15 % coloured pixels spread over several hues (> 1.3 bits), or a strip
whose frames differ by hue (theatre colours, doctrine pills, state strips; gold rims do not count), keeps its hues:
plate textures keep red / green / blue / yellow at a lower saturation threshold, strips keep every hue except dull
gold. A texture with one green or red signal cluster (green up arrow, copper-red down arrow, green tick) keeps it
even at moderate saturation.

**Paper and dark text.** Vanilla draws dark text (typewriter fonts, `*_black` fonts, colour code `b`) on some light
surfaces. The orchestrator scans every vanilla `.gui` (the mod's copy where it has one) and marks the textures dark
text is drawn on (`dark_text_hosts` in `ingame_owners.json`; a container's background and icons, also through
child containers without an opaque background of their own). Only there a light vanilla surface stays light
("paper": D at 0.95, silhouette snapped to its bounding rectangle, no torn edges); everywhere else paper becomes the
dark field tone. The outputs that kept paper are listed in `ingame_owners.json` under `paper` (37 after the last
full run). **To restyle one of them, change that text to a light font / colour in your `.gui` copy; the next build
reads the mod's `.gui`, no longer sees dark text and re-tones the texture dark by itself** (or force it in a module:
`ctx.generic(src, tones=("raised",))`). The events stream's `eventwindow.gui` copy already did this.

Tune with `--preview` and the constants at the top of `generic.py` (ramps, `PLATEAU`, `PAPER_LUMA`, `TONE_LUMA`,
semantic bands, `FLAT_MIN_PX`, `RECT_FILL`, `GUIDE_MIN`, `STATE_TONES`, `OVERRIDES`, `CLASS_OPTS`,
`CLASS_FLAT_OPTS`).

## Checks

`--verify` checks size, mipmaps, format and decoding of every listed output, plus the **semantic colour check**:
for every output whose vanilla has at least 2 % signal pixels (red: hue -20..12, up to 20 in red-orange textures,
s > 0.55, v > 0.45; green: hue 85..170, s > 0.45, v > 0.3; copper, bronze, leather and vanilla's olive paint are
decoration and are not counted), the output must keep 60 % of their saturation and 50 % of their value (flattened
panels: saturation only, since a signal surface becomes a dark tint by design). Generic outputs that fail are
errors; module outputs are printed as `NOTE` for the owning stream. Modes state / keyer / knob / caption and the
documented `SEM_EXEMPT` paths are exempt. Last full run: 157 outputs checked, 0 generic failures, 5 module notes.

## Output format policy

- Same relative path and same pixel size as vanilla (asserted). Never mipmaps: 77 written textures had mipmaps in
  vanilla (e.g. `tiles/tiles_dialog.dds` 7, `naviesview/btn_close.dds` 5; `--list` shows the vanilla count), so
  a texture drawn smaller than 1:1 (UI scale below 1) can alias a little.
- `.dds`: **DXT5 when w x h >= 16384 and the texture is not lossless, also for sides that are not multiples of 4**
  (vanilla itself ships and references 55+ such DXT textures, e.g. `combat_header.dds` 411 x 27,
  `unit_stats_list_bg.dds` 273 x 392, `filters_grid_bg.dds` 533 x 140; Pillow encodes the partial edge blocks
  correctly, mean error ~2 levels); otherwise uncompressed A8R8G8B8 (the vanilla layout). DXT headers are written
  like vanilla's (flags 0x81007, linear size, bit count 0, caps 0x1000). `ctx.dxt` / `LOSSLESS` override per
  texture; `--no-dxt-odd` restores the multiples-of-4 rule.
- `.png` / `.tga` sources stay PNG / TGA (RGBA).
- A result identical to vanilla is not written.

## Budget

Last full run: **96.3 MB** for 1,552 files (1,057 A8R8G8B8 = 30.7 MB, 480 DXT5 = 65.6 MB of which 395 with odd
sides, 15 PNG), under the ~140 MB target. By area: views 40.1, trees 18.9, kit 8.9, events 8.5, topbar 8.0, misc
7.4, mp 1.7, popups 1.3, settings 1.2, esc 0.2, rules 0.04. With `--no-dxt-odd` it would be about 230 MB.

## Safety

- `ingame_outputs.txt` lists `path<TAB>producer` for every written file. A full run deletes only listed files it no
  longer produces, and never a file that was rewritten after the run started (a parallel `--only` run); a partial
  run deletes only the listed files of its own jobs that are now kept as vanilla. Unlisted files are never touched,
  and deletion refuses anything outside `gfx/interface` / `gfx/minimap`, under `gfx/interface/totu`, through `..`
  or links.
- A module that fails to import: a full run stops (or, with `--skip-broken`, skips it and deletes nothing); other
  streams' `--only` runs skip it and never rebuild its area's paths **or any path it produced last time** (the
  producer column), so a cross-area claim survives a broken module.
- The outputs file is updated under `ingame_outputs.lock`, which holds the writer's pid; a lock whose process is
  gone is broken at once.

## Rules for stream agents

- Only run `--only <your areas>` (or `--preview`, `--list`, `--verify`, `--sizes`). The full run belongs to the
  pipeline owner: it deletes stale outputs and rewrites `ingame_owners.json`.
- Never hand-edit generated textures; never write into `gfx/interface/**` outside this pipeline (new sprites go to
  `gfx/interface/totu/<area>/` through `tools/totu_broadcast.py`).
- A path you claim that another area owns prints a warning: agree on it with that area, because the same path is
  then rebuilt by `--only <you>`, not by `--only <owner>`.
- Content (icons, portraits, flags, event photos) keeps its colours: do not claim content textures. Semantic
  red / green / yellow stays (`--verify` notes your outputs that lose it).
- Paper surfaces in your area (`paper` in `ingame_owners.json`) need a text-colour change in your `.gui` copy
  before they can go dark.
