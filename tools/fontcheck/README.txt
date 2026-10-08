tools/fontcheck: vanilla localisation keys drawn in the mod's pixel fonts
=========================================================================

The pixel fonts (gfx/fonts/totu_*, built by tools/build_fonts.py) hold printable ASCII, Russian Cyrillic, the
typography of the Russian texts, every accented Latin letter (drawn as its base capital; with real accent marks in
the in-game header fonts totu_h36 and totu_h24) and a few signs. A character outside that set renders as nothing.
So every string a pixel font draws is checked:

  * the mod's own caption keys TOTU_FE_* (menus) / TOTU_IG_* (in game) / TOTU_MENU_* in
    localisation/<lang>/totu_menu*_l_<lang>.yml (checked automatically; put new keys in your own file, e.g.
    totu_menu_options_l_english.yml and totu_menu_options_l_russian.yml; every key must be in both);
  * vanilla keys the engine or your .gui puts into a pixel-font box (font totu_caption_name, totu_label,
    totu_button*, totu_caption*, or a vanilla header font hoi_36header / hoi_30header / hoi_24header outside the
    .gui boxes the check already sees): REGISTER THEM HERE.

Your own text drawn in a VANILLA font (tooltips, descriptions, body text in totu_body / totu_list / hoi_18mbs ...):
name the key TOTU_TXT_* and put it in the same totu_menu_<area>_l_<lang>.yml files. TOTU_TXT_ keys are not
glyph-checked (any character the vanilla font has is fine, e.g. arrows), but they must exist in English and Russian
and get the English fallback for the other languages like the captions. Do not name tooltip text TOTU_IG_*: a
TOTU_IG_ key is glyph-checked against the pixel fonts.

A TOTU_FE_ / TOTU_IG_ / TOTU_MENU_ / TOTU_TXT_ key in any other file (a replace/ folder, totu_ig_topbar_l_*.yml, ...)
is a problem: there it would get neither the glyph check nor the fallback. A key defined twice in the mod's files of
one language (any file, replace/ included) is a problem too.

Format
------
One file per area, any name ending in .txt except this README (e.g. options.txt, esc_menu.txt, multiplayer.txt).
UTF-8, one entry per line. An entry is a vanilla localisation key or a Python regular expression; it must match the
WHOLE key. Everything after # is a comment; blank lines are ignored.

    # settings window labels drawn in totu_caption_name
    SM_OPTIONS
    SM_[A-Z_]+_LABEL          # a regular expression: every SM_..._LABEL key
    MENU_BAR_SAVE             # trailing comments are fine
    AUTOSAVE_TOCLOUD

The English, Russian, French, German, Spanish, Brazilian Portuguese and Polish values of every matching key (as the
game resolves them, the mod's replace files included) are glyph-checked; $...$, [...] and icon fields are left out.
An entry that is not a valid regular expression, or matches no English key, is reported as a problem.

Run
---
    python tools/build_fonts.py --check            checks only, writes nothing, exit code 1 on a problem
    python tools/build_fonts.py --loc              after adding or changing keys in totu_menu*_l_english.yml (or the
                                                   loading tips / country names): rewrites ONLY the generated English
                                                   fallback of the 8 other game languages
                                                   (localisation/<lang>/totu_menu_captions_l_<lang>.yml, loading tips,
                                                   new country names), then runs every check
    python tools/build_fonts.py --check --verbose  also lists the long notes (see below)
    python tools/build_fonts.py                    full build: atlases, generated localisation, previews (the fonts'
                                                   owner; needed only after changing glyphs)

So the usual loop for a stream is: add keys to your English and Russian files, run --loc, run --check, commit the
regenerated totu_menu_captions_l_<lang>.yml files together with yours. --check reports "generated localisation is
stale" when you forgot --loc.

Output lines: PROBLEM (fails the run: missing glyph, key missing in English or Russian, duplicate key, a caption key
outside the caption files, stale generated localisation, bad entry here, stale atlas, header box that only the pixel
font overflows in Russian), WARN (a box of a mod .gui in a pixel font overflows its maxWidth / maxHeight in English or
Russian, an English vanilla header box overflows, or interface/core.gfx drifted from the game's file), NOTE (summary
lines; --verbose lists them). Messages name keys and files, never the texts (the console is ASCII).

Box widths
----------
Every text box and button in a pixel font of the game's and the mod's .gui files is measured (the mod's file of the
same path replaces the game's; boxes moved off screen to x or y <= -5000 are skipped): text from the localisation
key, wrapped at maxWidth (buttons: size or sprite frame width), at most maxHeight / lineHeight lines (one without
maxHeight), in English, Russian and the Latin languages.

  * Russian vanilla header text that fitted in the vanilla font and no longer fits (PROBLEM): give the key a shorter,
    faithful Russian text in a replace file OF YOUR OWN, named after your area:
        localisation/russian/replace/totu_<area>_short_l_russian.yml   (UTF-8 with BOM, first line l_russian:)
    with the key copied and the value shortened, plus a comment with the box, its maxWidth and the vanilla text.
    Never edit English. localisation/russian/replace/totu_header_short_l_russian.yml belongs to the fonts (A2); do not
    add to it, and do not shorten a key another file already shortens (duplicate key = PROBLEM).
  * English overflows are WARNs (English is never touched); fix the box in your .gui copy if you own the window.
  * Latin languages (French, German, Spanish, Brazilian Portuguese, Polish): a known limitation, NOTE only. The pixel
    fonts advance 12 px per character against Orator's ~11, so about 30 vanilla header texts (mostly Polish and
    French tutorial titles in hoi_24header) wrap or overflow. The mod ships no translation for these languages.

Header fonts
------------
interface/core.gfx draws hoi_36header / nsb_hoi_36header in totu_h36 (2x3 px cells, accent marks above the
capitals), hoi_30header in totu_h30 (2x3 px cells; no headroom, so accented letters are their base capitals; the
stroke letters L/O/D-stroke keep their strokes) and hoi_24header / nsb_hoi_24header in totu_h24 (2x2 px cells,
accent marks above, one-row cedilla / ogonek below). Each lists the vanilla Orator file second as a glyph fallback;
the metrics are vanilla's. The menu font totu_button_small has the same glyphs as totu_h24 without the marks.

Stream TODO: header-font boxes holding paragraph text
-----------------------------------------------------
5x7 capitals read badly in sentences. These vanilla boxes use a header font for a sentence or a paragraph
(--verbose lists them as NOTE PARAGRAPH; 8+ words wrapping to 2+ lines). The stream that copies the window into the
mod should switch the box to a body font (totu_body, or vanilla hoi_18mbs / hoi_16mbs) in its .gui copy:

    factions/countryfactionview.gui         explain_text   FACTION_ARMY_TAB_TT, FACTION_RESEARCH_TAB_TT  (hoi_24header)
    factions/countryfactionview.gui         hidden_text    FACTION_INTEL_NO_DEPARTMENT_CREATED_VISIBILITY,
                                                           FACTION_ACCESS_TO_*_TAB                       (hoi_24header)
    ast_right_vs_left_campaign_empty_scripted_gui.gui  AST_bg_empty_text  AST_bg_empty_text_tt          (hoi_30header)
    career_profile/career_profile_view.gui  text           CAREER_PROFILE_PRIVATE and the other profile
                                                           sentences                                     (hoi_36header)
