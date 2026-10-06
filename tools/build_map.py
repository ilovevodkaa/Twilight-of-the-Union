"""Generates the 1990 world map of Twilight of the Union from Natural Earth + elevation data.

Everything under map/, history/states/, history/countries/ (stubs), common/countries/,
common/country_tags/, the strategic regions / supply areas and the map localisation is written
by this script - edit the script, not the generated files. Deterministic (fixed seeds).

Pipeline (tools/map/*):
  data.py       download Natural Earth GeoJSON + Terrarium elevation tiles into tools/cache/ (gitignored)
  raster.py     rasterise land / lakes / admin-1 regions into the 5632x2048 plate-carree grid
  provinces.py  population-weighted Voronoi/Lloyd provinces clipped to admin-1 regions, sea + lake provinces
  world.py      compact ids, colours, adjacency, representative points
  states.py     cities (victory points) and states (province groups per country)
  terrain.py    province terrain from elevation + climate zones
  content.py    countries, population, VPs
  regions.py    strategic regions, straits, railways
  writers.py    text files;  images.py  bitmaps and the preview

Usage:
  pip install numpy scipy shapely scikit-image opencv-python-headless pillow requests
  python tools/build_map.py            # full build (about 5-10 minutes the first time)
  python tools/build_map.py --rebuild  # ignore the cached province raster
Then:  python tools/validate_map.py
"""
import argparse
import pickle
import shutil
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from map import (content, countries, data, geo, images, provinces, raster, regions, states, terrain,  # noqa: E402
                 world, writers)

ROOT = Path(__file__).resolve().parent.parent
WORK = data.CACHE / "work"
SEED = 1990


def stage_world(rebuild):
    pk = WORK / "world.pkl"
    if pk.exists() and not rebuild:
        print("using cached province raster", pk)
        with open(pk, "rb") as f:
            return pickle.load(f)
    data.fetch_ne()
    rast = raster.build()
    P, meta, U = provinces.build(rast)
    for _ in range(3):
        provinces.cleanup(P, meta, U)
        left = provinces.fix_crossings(P, U)
    if left:   # remaining crossings sit on unit borders: allow moving a pixel inside the same land/sea class
        provinces.fix_crossings(P, rast["C"].astype(np.int32))
        provinces.cleanup(P, meta, U)
        left = provinces.fix_crossings(P, rast["C"].astype(np.int32), force=True)
    print("contiguity repairs:", provinces.repair_contiguity(P))
    print("X-crossings left:", left)
    w = world.build(rast, P, meta)
    WORK.mkdir(parents=True, exist_ok=True)
    with open(pk, "wb") as f:
        pickle.dump((rast, w), f, protocol=5)
    return rast, w


def clean_outputs():
    for d in ["history/states", "map/strategicregions", "map/supplyareas", "common/countries", "common/country_tags"]:
        shutil.rmtree(ROOT / d, ignore_errors=True)
    for p in (ROOT / "history/countries").glob("*.txt"):
        if p.name.split(" - ")[0] not in ("USA", "SOV"):
            p.unlink()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true", help="recompute provinces instead of using tools/cache/work")
    ap.add_argument("--skip-images", action="store_true")
    args = ap.parse_args()
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    rast, w = stage_world(args.rebuild)
    N = w["N"]
    print("provinces", N, f"({time.time() - t0:.0f}s)", flush=True)
    dem = data.build_dem()
    places = states.load_places(w, rast)
    print("places", len(places), flush=True)
    terr, emean, estd = terrain.classify(w, rast, dem, places)
    S, state_of = states.build(w, rast, places, SEED)
    table = content.country_table(S, rast)
    vps, cap_state = content.finish(S, state_of, w, rast, places, table)
    print("victory points", len(vps), "countries", len(table), flush=True)
    w["coast_pos"] = writers.coast_positions(w)

    clean_outputs()
    mp = ROOT / "map"
    # ---- map files
    writers.definition(w, terr, mp / "definition.csv")
    writers.default_map(N, mp / "default.map")
    writers.continents(mp / "continent.txt")
    straits = regions.straits(w)
    writers.adjacencies(straits, mp / "adjacencies.csv")
    writers.adjacency_rules(mp / "adjacency_rules.txt")
    writers.buildings(S, w, mp / "buildings.txt")
    writers.unitstacks(w, mp / "unitstacks.txt")
    writers.per_state(S, mp / "airports.txt")
    writers.per_state(S, mp / "rocketsites.txt")
    writers.supply_nodes(S, mp / "supply_nodes.txt")
    rails = regions.railways(S, w, state_of)
    writers.railways(rails, mp / "railways.txt")
    print("straits", len(straits), "railways", len(rails), flush=True)
    # ---- states
    for s in S:
        writers.state_file(s, vps, ROOT / "history/states")
    # ---- strategic regions
    kind = w["kind"]
    sid = {s["id"]: s for s in S}
    land_groups = regions.land_regions(S, w, rast, rng)
    land_groups.sort(key=lambda g: min(g))
    sea_groups = regions.sea_regions(w, rng)
    sea_groups.sort(key=lambda g: min(g))
    sea_names = regions.name_sea_regions(sea_groups, w, regions.sea_names())
    prov_region = {}
    out_regions = []   # (id, provs, name_en, name_ru, lat, sea)
    for g in land_groups:
        rid = len(out_regions) + 1
        provs = [p for st in g for p in sid[st]["provs"]]
        big = max(g, key=lambda st: len(sid[st]["provs"]))
        out_regions.append([rid, provs, sid[big]["name_en"] + " Region", "Регион " + sid[big]["name_ru"], False, g])
        for p in provs:
            prov_region[p] = rid
    # lakes join the region of a neighbouring land province
    lake_nb = {}
    for a, b in zip(w["adj_a"], w["adj_b"]):
        a, b = int(a), int(b)
        for x, y in ((a, b), (b, a)):
            if kind[x] == "lake" and kind[y] == "land":
                lake_nb.setdefault(x, []).append(y)
    for lk in [i for i in range(1, N + 1) if kind[i] == "lake"]:
        cand = lake_nb.get(lk)
        if cand:
            rid = prov_region[cand[0]]
        else:
            lands = [p for p in prov_region]
            q = min(lands, key=lambda p: (w["cx"][p] - w["cx"][lk]) ** 2 + (w["cy"][p] - w["cy"][lk]) ** 2)
            rid = prov_region[q]
        out_regions[rid - 1][1].append(lk)
        prov_region[lk] = rid
    n_land_regions = len(out_regions)
    for mem, (en, ru) in zip(sea_groups, sea_names):
        rid = len(out_regions) + 1
        out_regions.append([rid, list(mem), en, ru, True, None])
        for p in mem:
            prov_region[p] = rid
    assert set(prov_region) == set(range(1, N + 1)), "strategic regions must cover every province exactly once"
    wp = []
    dist_c = np.hypot  # noqa
    for rid, provs, en, ru, sea, grp in out_regions:
        a = np.array([w["area"][p] for p in provs], float)
        cyy = float((np.array([w["cy"][p] for p in provs]) * a).sum() / a.sum())
        cxx = float((np.array([w["cx"][p] for p in provs]) * a).sum() / a.sum())
        lat = float(geo.px_to_lonlat(0, cyy)[1])
        naval = None
        if sea:
            mean_depth_px = float(np.mean([w["area"][p] for p in provs]))
            naval = "water_deep_ocean" if mean_depth_px > 2500 else "water_shallow_sea"
        writers.strategic_region(rid, provs, lat, sea, 0.0 if sea else 1.0, naval, mp / "strategicregions", en)
        # weather position: representative point of the biggest province
        big = provs[int(np.argmax(a))]
        x, z = writers.xz(w, big)
        wp.append(f"{rid};{x:.2f};{HEIGHT_Y:.2f};{z:.2f};{'large' if len(provs) > 25 else 'small'}")
    writers.w_text(mp / "weatherpositions.txt", "\n".join(wp) + "\n")
    for i, (rid, provs, en, ru, sea, grp) in enumerate(out_regions[:n_land_regions], start=1):
        writers.supply_area(i, grp, mp / "supplyareas")
    print("strategic regions: land", n_land_regions, "sea", len(out_regions) - n_land_regions, flush=True)

    # ---- countries
    writers.country_files(table, cap_state, ROOT)
    writers.history_files(table, cap_state, ROOT)
    # ---- localisation
    en_entries, ru_entries = [], []
    for s in S:
        en_entries.append((f"STATE_{s['id']}", s["name_en"]))
        ru_entries.append((f"STATE_{s['id']}", s["name_ru"]))
    for p in sorted(vps):
        en_entries.append((f"VICTORY_POINTS_{p}", vps[p]["name"]))
        ru_entries.append((f"VICTORY_POINTS_{p}", vps[p]["ru"]))
    for rid, provs, en, ru, sea, grp in out_regions:
        en_entries.append((f"STRATEGICREGION_{rid}", en))
        ru_entries.append((f"STRATEGICREGION_{rid}", ru))
    writers.loc_file(ROOT / "localisation/english/totu_map_l_english.yml", "english", en_entries)
    writers.loc_file(ROOT / "localisation/russian/totu_map_l_russian.yml", "russian", ru_entries)
    c_en = [("SOV_communism", "Union of Soviet Socialist Republics"), ("USA_democratic", "United States of America")]
    c_ru = [("SOV_communism", "Союз Советских Социалистических Республик"), ("USA_democratic", "Соединённые Штаты Америки")]
    for tag in sorted(table):
        c = table[tag]
        c_en += [(tag, c["name"]), (f"{tag}_DEF", ("the " + c["name"]) if c["the"] else c["name"]), (f"{tag}_ADJ", c["adj"])]
        c_ru += [(tag, c["ru"]), (f"{tag}_DEF", c["ru"]), (f"{tag}_ADJ", c["adj_ru"])]
    writers.loc_file(ROOT / "localisation/english/replace/totu_countries_l_english.yml", "english", c_en)
    writers.loc_file(ROOT / "localisation/russian/replace/totu_countries_l_russian.yml", "russian", c_ru)

    # ---- bitmaps
    if not args.skip_images:
        images.provinces_bmp(w, mp / "provinces.bmp")
        hm = images.heightmap(w, rast, dem)
        images.save_bmp(hm, mp / "heightmap.bmp", "L")
        images.save_bmp(images.terrain_bmp(w, terr, rast), mp / "terrain.bmp", "P", images.TERRAIN_RGB)
        images.save_bmp(images.rivers_bmp(rast), mp / "rivers.bmp", "P", images.RIVER_PALETTE)
        images.save_bmp(images.trees_bmp(w, terr), mp / "trees.bmp", "P", {0: (0, 0, 0), 3: (0, 160, 0), 4: (0, 255, 0)})
        images.save_bmp(images.cities_bmp(places), mp / "cities.bmp", "L")
        images.save_bmp(images.normal_map(hm), mp / "world_normal.bmp")
        (ROOT / "docs/images").mkdir(parents=True, exist_ok=True)
        images.preview(w, S, state_of, table, rast, ROOT / "docs/images/map_1990.jpg")
    # ---- descriptor
    update_descriptor()
    print(f"done in {time.time() - t0:.0f}s")


HEIGHT_Y = 9.5

REPLACE = ["history/units", "history/states", "history/countries", "common/country_tags", "common/countries",
           "map/strategicregions", "map/supplyareas"]


def update_descriptor():
    p = ROOT / "descriptor.mod"
    txt = p.read_text(encoding="utf-8")
    for r in REPLACE:
        line = f'replace_path="{r}"'
        if line not in txt:
            txt = txt.replace('supported_version=', line + "\nsupported_version=")
    p.write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()
