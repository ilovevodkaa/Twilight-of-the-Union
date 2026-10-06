# Technologies

Status: **unchanged vanilla tech tree**, deliberately. Vanilla `common/technologies` is not in this repo and is not
replaced (see `docs/VANILLA_PURGE.md`), so no tech effect, cost or year was copied or changed.

## Research-ahead-of-time penalty
HOI4 applies the "ahead of time" penalty by comparing the current game date with each technology's `start_year`
(`NDefines.NTechnology.*YEAR_AHEAD*` only scale the size of the penalty). Vanilla `start_year` values are 1933-1945.
The game starts on 1 January 1990 (`NDefines.NGame.START_DATE`, already set in `common/defines/totu_defines.lua`
together with `END_DATE = 2010.1.1.1`), so every vanilla technology is *behind* the clock and **no penalty applies to any
of them**. There is therefore no define that needs changing for the 1990 start, and no define exists that shifts
`start_year` globally; inventing one would be a no-op. Only the date defines are needed, and they are in place.

## What still has to be done (when tech files are added)
* Modern technologies (1980s-2000s equipment, doctrines) must be authored as mod files with `start_year` of the real
  introduction year (>= 1985 or so) so the penalty works for them; vanilla WW2 techs keep their old years.
* Starting techs per country (`set_technology`) are not set in `history/countries` yet: no country knows any technology at
  start. This needs a 1990 baseline list once the equipment / tech set is decided.
