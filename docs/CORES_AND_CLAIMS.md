# Cores, claims and stub tags

Everything is written by `tools/build_cores_claims.py` into `history/states` (idempotent). Geography for the cores
comes from `tools/state_admin.json`, produced by `tools/dump_state_admin.py` from the cached province raster: each
province's representative point is looked up in the Natural Earth admin-0 polygons, so cores follow real republic borders
even where the map generator's admin-1 regions are coarse (the Balkans).

## Stub tags (do not exist on 1 January 1990)
`tools/stub_tags.py`: RUS UKR BLR MOL EST LAT LIT GEO ARM AZR KAZ UZB TMS KYR TAJ (Soviet republics), SLV CRO BOS SER
MNT MAC (Yugoslav republics), SLO CZR (Czechoslovakia; CZE stays Czechoslovakia), SAH (Western Sahara). They have
`common/country_tags/totu_future_countries.txt`, `common/countries/<name>.txt`, colours in `colors.txt`, en + ru names
and adjectives (`localisation/*/replace/totu_future_countries_*.yml`) and modern flags (`tools/build_flags.py`, flag-icons).
They have no history file and own no state, so they cannot appear at start.

## Cores
Every state keeps the owner's core. SOV states add the republic core (RUS, UKR, ...), YUG states the republic core
(Kosovo counts as Serbia), CZE states CZR / SLO, Western Sahara SAH. A second republic is added when it covers at least 30%
of the state. Crimea is Ukrainian (1990 borders). A republic that never reaches 30% anywhere (Moldova, North Macedonia,
Slovenia) still gets the state where it is largest.

## Claims (`add_claim_by`)
GER on all DDR states (a claim, not a core, as agreed in the task notes); JAP on the Kuril states; PAK on Indian Kashmir and Ladakh; IND on
Gilgit-Baltistan / Azad Kashmir and on the Aksai Chin states; PRC on Arunachal; ARG on the Falklands and South Georgia;
SYR on the Golan and Hatay; TUR on Northern Cyprus; SOM on the Ogaden; PHI on Sabah; IRQ on Kuwait; VEN on Guayana
Esequiba; GUA on Belize; ALB on the Kosovo states; ROM on the Moldovan state; mutual claims KOR/PRK, YEM/YES and CHI/PRC.

Not representable: Gibraltar, Ceuta, Melilla and Hong Kong are not separate states on this map (no region of their own),
so SPR / MOR / PRC claims on them are missing.
Some state ids are hard-coded in `CLAIMS` (Kurils, Kashmir ...); they only change if the map generator is re-run with different parameters.
