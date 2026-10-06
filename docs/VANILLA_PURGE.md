# Vanilla content purge

The mod starts in 1990 on a generated map, so vanilla 1936-1945 content (tags, states, characters, province ids)
must not load. HOI4 has no way to delete single vanilla entries, so whole folders are removed with `replace_path`
in `descriptor.mod`; each one is given a minimal stub where the engine or our own content needs something.
`tools/purge_vanilla.py` (re)creates every stub below. Nothing here could be tested in-game (no HOI4 install in
the repo); the "risk" column says what to check first when the mod is first launched.

## Replaced folders

| Folder | Stub added | Why / risk |
|---|---|---|
| `common/ideas` | `totu_laws.txt`: economy, trade and mobilization law ideas (same names as vanilla: `civilian_economy` ... `tot_economic_mobilisation`, `free_trade` ... `closed_economy`, `volunteer_only` ... `scraping_the_barrel`, `disarmed_nation`) with approximated modifiers. `TOTU_SOV.txt` is kept. | Country history uses laws via `add_ideas`; the vanilla files are full of 1936 spirits. Category names (`economy`, `trade_laws`, `mobilization_laws`) come from vanilla `common/idea_tags`, which is NOT replaced. Check: laws appear in the political screen. |
| `common/characters` | Our `TOTU_leaders.txt` stays | Vanilla characters are 1936 people. |
| `common/country_leader` | `totu_traits.txt` (one placeholder trait) | Vanilla leader traits; none are used by 1990 leaders yet. |
| `common/names` | `totu_names.txt`: placeholder generic name pools for every tag | Operatives / generated characters need names per tag. Replace with real lists later. |
| `common/national_focus` | comment-only | 1936 focus trees. No focuses yet (by design). |
| `common/decisions`, `common/decisions/categories` | comment-only | Reference vanilla tags, states, flags. |
| `common/scripted_effects`, `common/scripted_triggers` | comment-only | Vanilla ones are called only by vanilla content that is now purged. Risk: a vanilla interface or game rule calling one logs an error. |
| `common/on_actions` | comment-only | Vanilla hooks call purged events and effects. |
| `common/ai_strategy`, `common/ai_strategy_plans`, `common/ai_areas`, `common/ai_focuses` | comment-only | Tag / state specific AI data. Risk: AI is passive or generic until we add 1990 AI data. |
| `common/dynamic_modifiers`, `common/scripted_localisation`, `common/scripted_guis` | comment-only | Used by vanilla focus / event content only. |
| `common/military_industrial_organization/organizations` | comment-only | Tag-locked organizations. Policies and other MIO folders are kept. |
| `common/special_projects`, `common/aces`, `common/raids`, `common/bop` | comment-only | Tag / state specific vanilla content. |
| `common/units/names`, `names_divisions`, `names_ships`, `names_railway_guns` | comment-only | Unit name pools keyed on vanilla tags. Risk: units get default numeric names. |
| `events` | comment-only | 1936+ events. |
| `history/general` | comment-only | Vanilla 1936 diplomacy, wars and starting states. |
| `history/countries`, `history/states`, `history/units`, `common/countries`, `common/country_tags`, `common/bookmarks`, `map/*` | (already replaced earlier) | Generated 1990 world. |

## Deliberately NOT replaced (engine-required or tag-agnostic)

| Folder | Reason |
|---|---|
| `common/autonomous_states`, `common/occupation_laws`, `common/peace_conference`, `common/ai_peace`, `common/ai_templates` | Engine defaults (puppet levels, default occupation law, peace costs, AI division templates). Replacing them would break puppets, occupation and AI. |
| `common/doctrines`, `common/technologies`, `common/units` (definitions), `common/ideologies`, `common/idea_tags` | Rules / trees, not 1936 tag content. Technologies: see `docs/TECHNOLOGY.md`. |
| `common/factions` | Faction templates are generic; no country creates a faction at start. |
| `common/opinion_modifiers`, `common/medals`, `common/ribbons`, `common/unit_medals`, `common/unit_leader` | Engine-referenced and tag-agnostic; unused vanilla modifiers are harmless. |
| `common/intelligence_agencies`, `common/operations` | The engine needs at least the default agency / operation set. |

## Country history

`history/countries/SOV` and `USA` were rewritten from scratch: the vanilla 1936 text they contained (hundreds of
`recruit_character`, OOB, variables, focus and event hooks) referenced purged content. All country files now use only
laws from `totu_laws.txt`, spirits from `TOTU_SOV.txt` and characters from `common/characters`.
