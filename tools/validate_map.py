"""Validates the generated 1990 map (no game needed). Exit code 1 on any error.

Usage: python tools/validate_map.py
"""
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from skimage import measure

Image.MAX_IMAGE_PIXELS = None
ROOT = Path(__file__).resolve().parent.parent
W, H = 5632, 2048
errors, warnings = [], []


def err(msg):
    if len(errors) < 200:
        errors.append(msg)
    elif len(errors) == 200:
        errors.append("... more errors suppressed")


def warn(msg):
    if len(warnings) < 50:
        warnings.append(msg)


def read(p):
    return Path(p).read_text(encoding="utf-8-sig")


def bmp_info(path):
    b = Path(path).read_bytes()[:60]
    assert b[:2] == b"BM", f"{path}: not a BMP"
    w = int.from_bytes(b[18:22], "little", signed=True)
    h = int.from_bytes(b[22:26], "little", signed=True)
    bpp = int.from_bytes(b[28:30], "little")
    return w, abs(h), bpp


def check_bmp(name, size, bpp):
    p = ROOT / "map" / name
    if not p.exists():
        return err(f"missing map/{name}")
    w, h, b = bmp_info(p)
    if (w, h) != size:
        err(f"{name}: size {w}x{h}, expected {size[0]}x{size[1]}")
    if b != bpp:
        err(f"{name}: {b} bit, expected {bpp} bit")


def main():
    # ---------------- bitmaps
    check_bmp("provinces.bmp", (W, H), 24)
    check_bmp("heightmap.bmp", (W, H), 8)
    check_bmp("terrain.bmp", (W, H), 8)
    check_bmp("rivers.bmp", (W, H), 8)
    check_bmp("trees.bmp", (3520, 1280), 8)
    check_bmp("cities.bmp", (W, H), 8)
    check_bmp("world_normal.bmp", (W // 2, H // 2), 24)
    rv = Image.open(ROOT / "map/rivers.bmp")
    ra = np.asarray(rv)
    pal = np.array(rv.getpalette()[:768]).reshape(256, 3)
    if tuple(pal[255]) != (255, 255, 255) or tuple(pal[254]) != (122, 122, 122) or tuple(pal[0]) != (0, 255, 0):
        err("rivers.bmp palette does not match the vanilla river palette")
    bad = ~np.isin(ra, list(range(0, 12)) + [254, 255])
    if bad.any():
        err(f"rivers.bmp: {int(bad.sum())} pixels with invalid index")
    hm = np.asarray(Image.open(ROOT / "map/heightmap.bmp"))
    del ra, hm

    # ---------------- provinces / definition
    img = np.asarray(Image.open(ROOT / "map/provinces.bmp").convert("RGB"))
    if img.shape != (H, W, 3):
        err(f"provinces.bmp array shape {img.shape}")
    key = (img[..., 0].astype(np.int64) << 16) | (img[..., 1].astype(np.int64) << 8) | img[..., 2].astype(np.int64)
    rows = read(ROOT / "map/definition.csv").splitlines()
    if rows[0] != "0;0;0;0;land;false;unknown;0":
        err("definition.csv: first row must be the id 0 row")
    ids, col2id, kind, terr, cont, coastal = [], {}, {}, {}, {}, {}
    allowed_terrain = {"plains", "forest", "hills", "mountain", "desert", "marsh", "jungle", "urban", "ocean", "lakes"}
    for line in rows[1:]:
        f = line.split(";")
        if len(f) != 8:
            err(f"definition.csv: bad row {line!r}")
            continue
        i = int(f[0])
        c = (int(f[1]) << 16) | (int(f[2]) << 8) | int(f[3])
        ids.append(i)
        if c in col2id:
            err(f"definition.csv: duplicate colour {f[1:4]} (ids {col2id[c]}, {i})")
        col2id[c] = i
        if c == 0:
            err(f"definition.csv: province {i} uses colour (0,0,0)")
        kind[i], terr[i], cont[i], coastal[i] = f[4], f[6], int(f[7]), f[5] == "true"
        if f[4] not in ("land", "sea", "lake"):
            err(f"province {i}: bad type {f[4]}")
        if f[6] not in allowed_terrain:
            err(f"province {i}: unknown terrain {f[6]}")
        if not (0 <= int(f[7]) <= 6):
            err(f"province {i}: continent {f[7]}")
        if (f[4] == "land") != (int(f[7]) > 0):
            err(f"province {i}: continent/type mismatch")
    N = len(ids)
    if ids != list(range(1, N + 1)):
        err("definition.csv: ids are not contiguous 1..N")
    u, inv, counts = np.unique(key, return_inverse=True, return_counts=True)
    missing = [int(c) for c in u if int(c) not in col2id]
    if missing:
        err(f"provinces.bmp: {len(missing)} colours not in definition.csv (first {missing[:3]})")
    unused = set(col2id) - set(int(c) for c in u)
    if unused:
        err(f"definition.csv: {len(unused)} colours not present in provinces.bmp")
    P = np.zeros((H, W), np.int32)
    lut = np.array([col2id.get(int(c), 0) for c in u], np.int32)
    P = lut[inv.reshape(H, W)]
    del key, inv, img
    area = np.bincount(P.ravel(), minlength=N + 1)
    for i in range(1, N + 1):
        if area[i] < 8:
            err(f"province {i} has only {area[i]} px")
        elif area[i] < 40 and kind[i] == "land":
            warn(f"land province {i} has {area[i]} px (<40)")
    # contiguity: number of 4-connected components must equal number of provinces
    lab = measure.label(P, connectivity=1)
    ncomp = int(lab.max())
    if ncomp != N:
        pairs = np.unique(np.stack([lab.ravel(), P.ravel()], 1), axis=0)
        cnt = np.bincount(pairs[:, 1], minlength=N + 1)
        bad = np.nonzero(cnt > 1)[0]
        err(f"{len(bad)} provinces are not contiguous (e.g. {bad[:5].tolist()})")
    del lab
    # X crossings
    a, b, c, d = P[:-1, :-1], P[:-1, 1:], P[1:, :-1], P[1:, 1:]
    xc = int((((a != b) & (a != c) & (a != d) & (b != c) & (b != d) & (c != d)) | ((a == d) & (b == c) & (a != b))).sum())
    if xc:
        warn(f"{xc} 2x2 pixel blocks with an X crossing of provinces")
    # adjacency + coastal flag
    pairs = []
    for x, y in ((P[:, :-1], P[:, 1:]), (P[:-1, :], P[1:, :])):
        m = x != y
        pairs.append(np.minimum(x[m], y[m]).astype(np.int64) * (N + 1) + np.maximum(x[m], y[m]))
    codes = np.unique(np.concatenate(pairs))
    adj = set(zip((codes // (N + 1)).tolist(), (codes % (N + 1)).tolist()))
    sea_touch = set()
    for p, q in adj:
        if kind[p] == "land" and kind[q] == "sea":
            sea_touch.add(p)
        if kind[q] == "land" and kind[p] == "sea":
            sea_touch.add(q)
    for i in range(1, N + 1):
        if kind[i] == "land" and coastal[i] != (i in sea_touch):
            err(f"province {i}: coastal flag wrong")
    land_ids = {i for i in kind if kind[i] == "land"}

    # ---------------- states
    sdir = ROOT / "history/states"
    state_of, owner, vps_of_state, state_ids = {}, {}, {}, set()
    for f in sorted(sdir.glob("*.txt")):
        t = read(f)
        m = re.search(r"\bid\s*=\s*(\d+)", t)
        sid = int(m.group(1))
        if sid in state_ids:
            err(f"duplicate state id {sid}")
        state_ids.add(sid)
        if not f.name.startswith(f"{sid}-"):
            err(f"{f.name}: file name does not start with its id")
        if f'name="STATE_{sid}"' not in t.replace(" ", ""):
            err(f"state {sid}: bad name key")
        owners = re.findall(r"\bowner\s*=\s*([A-Z0-9]{3})", t)
        if len(owners) != 1:
            err(f"state {sid}: {len(owners)} owners")
        owner[sid] = owners[0] if owners else None
        provs = [int(x) for x in re.search(r"provinces\s*=\s*\{([^}]*)\}", t).group(1).split()]
        if not provs:
            err(f"state {sid}: no provinces")
        for p in provs:
            if p not in kind:
                err(f"state {sid}: unknown province {p}")
            elif kind[p] != "land":
                err(f"state {sid}: province {p} is not land")
            if p in state_of:
                err(f"province {p} is in states {state_of[p]} and {sid}")
            state_of[p] = sid
        vps_of_state[sid] = [int(x) for x in re.findall(r"victory_points\s*=\s*\{\s*(\d+)\s+\d+", t)]
        for vp in vps_of_state[sid]:
            if vp not in provs:
                err(f"state {sid}: victory point province {vp} is not in the state")
        if not re.search(r"manpower\s*=\s*\d+", t) or not re.search(r"state_category\s*=\s*\w+", t):
            err(f"state {sid}: manpower/state_category missing")
    nstates = len(state_ids)
    all_tags = set(re.findall(r'^([A-Z0-9]{3})\s*=', "".join(read(tf) for tf in (ROOT / "common/country_tags").glob("*.txt")), re.M))
    for f in sorted(sdir.glob("*.txt")):
        t = read(f)
        sid = int(re.search(r"\bid\s*=\s*(\d+)", t).group(1))
        for tg in re.findall(r"add_(?:core_of|claim_by)\s*=\s*(\w+)", t):
            if tg not in all_tags:
                err(f"state {sid}: core / claim for unknown tag {tg}")
        if f"add_core_of = {owner[sid]}" not in t:
            err(f"state {sid}: owner {owner[sid]} has no core")
    for p in land_ids:
        if p not in state_of:
            err(f"land province {p} is in no state")
    vp_total = sum(len(v) for v in vps_of_state.values())

    # ---------------- state buildings (tools/build_state_buildings.py)
    slot_of = {m.group(1): int(m.group(2)) for m in re.finditer(
        r"(\w+) = \{\s*color = \{[^}]*\}\s*local_building_slots = (\d+)",
        read(ROOT / "common/state_category/totu_state_categories.txt"))}
    slot_buildings = ("arms_factory", "industrial_complex", "dockyard")
    max_level = {"infrastructure": 5, "air_base": 10, "naval_base": 10}
    for f in sorted(sdir.glob("*.txt")):
        t = read(f)
        sid = int(re.search(r"\bid\s*=\s*(\d+)", t).group(1))
        cat = re.search(r"state_category\s*=\s*(\w+)", t).group(1)
        if cat not in slot_of:
            err(f"state {sid}: unknown state_category {cat}")
            continue
        mb = re.search(r"\bbuildings\s*=\s*\{(.*?)\n\t\t\}", t, re.S)
        if not mb:
            err(f"state {sid}: no buildings block")
            continue
        body = mb.group(1)
        provs_s = [int(x) for x in re.search(r"provinces\s*=\s*\{([^}]*)\}", t).group(1).split()]
        used = 0
        for b in slot_buildings:
            m = re.search(rf"^\s*{b}\s*=\s*(\d+)", body, re.M)
            used += int(m.group(1)) if m else 0
        if used > slot_of[cat]:
            err(f"state {sid}: {used} slot buildings exceed {slot_of[cat]} slots ({cat})")
        for b, mx in max_level.items():
            for m in re.finditer(rf"^\s*{b}\s*=\s*(\d+)", body, re.M):
                if int(m.group(1)) > mx:
                    err(f"state {sid}: {b} level {m.group(1)} > {mx}")
        if re.search(r"^\s*dockyard\s*=", body, re.M) and not any(coastal.get(p) for p in provs_s):
            err(f"state {sid}: dockyard in a state without coast")
        for m in re.finditer(r"(\d+)\s*=\s*\{\s*naval_base\s*=\s*(\d+)", body):
            if int(m.group(1)) not in provs_s or not coastal.get(int(m.group(1))):
                err(f"state {sid}: naval_base in non-coastal / foreign province {m.group(1)}")

    # ---------------- countries
    tags = {}
    for tf in sorted((ROOT / "common/country_tags").glob("*.txt")):
        tags.update(re.findall(r'^([A-Z0-9]{3})\s*=\s*"countries/([^"]+)"', read(tf), re.M))
    stub_tags = {t for t in tags if t not in {x for x in re.findall(r'^([A-Z0-9]{3})\s*=', read(ROOT / "common/country_tags/totu_countries.txt"), re.M)}}
    colors = set(re.findall(r"^([A-Z0-9]{3})\s*=\s*\{", read(ROOT / "common/countries/colors.txt"), re.M))
    loc = {}
    for lang in ("english", "russian"):
        txt = ""
        for lf in sorted((ROOT / f"localisation/{lang}/replace").glob("*.yml")):
            part = read(lf)
            if not part.startswith(f"l_{lang}:"):
                err(f"{lf.name}: bad header")
            txt += part
        loc[lang] = set(re.findall(r"^\s([A-Za-z0-9_]+):0", txt, re.M))
    known_ideas = set()
    for f in (ROOT / "common/ideas").glob("*.txt"):
        known_ideas |= set(re.findall(r"^\t+(\w+)\s*=\s*\{", read(f), re.M))
    known_chars = set()
    for f in (ROOT / "common/characters").glob("*.txt"):
        known_chars |= set(re.findall(r"^\t(\w+)\s*=\s*\{", read(f), re.M))
    hist = {}
    for f in (ROOT / "history/countries").glob("*.txt"):
        tag = f.name.split(" - ")[0]
        hist[tag] = f
        t = read(f)
        m = re.search(r"^capital\s*=\s*(\d+)", t, re.M)
        if not m or int(m.group(1)) not in state_ids:
            err(f"{f.name}: capital is not an existing state")
        elif owner[int(m.group(1))] != tag:
            err(f"{f.name}: capital state {m.group(1)} is owned by {owner[int(m.group(1))]}")
        # only ideas / characters that exist in this mod (vanilla content is purged, docs/VANILLA_PURGE.md)
        for blk in re.findall(r"add_ideas\s*=\s*\{([^}]*)\}", t):
            for idea in re.sub(r"#.*", "", blk).split():
                if idea not in known_ideas:
                    err(f"{f.name}: unknown idea {idea}")
        for ch in re.findall(r"(?:recruit|promote)_character\s*=\s*(\w+)", t):
            if ch not in known_chars:
                err(f"{f.name}: unknown character {ch}")
    owners = set(owner.values())
    for tag in sorted(set(hist) | set(tags) | owners):
        if tag not in tags:
            err(f"{tag}: missing in country_tags")
        else:
            if not (ROOT / "common/countries" / tags[tag]).exists():
                err(f"{tag}: common/countries/{tags[tag]} missing")
        if tag not in colors:
            err(f"{tag}: no colour in colors.txt")
        if tag not in hist and tag not in stub_tags:
            err(f"{tag}: no history file")
        for lang in loc:
            for suf in ("", "_DEF", "_ADJ"):
                if tag + suf not in loc[lang]:
                    err(f"{tag}: missing {lang} localisation {tag + suf}")
        if tag not in owners and tag not in stub_tags:
            warn(f"{tag}: owns no state")
        if tag in stub_tags and tag in owners:
            err(f"{tag}: stub tag owns a state")
        if not (ROOT / "gfx/flags" / f"{tag}.tga").exists():
            err(f"{tag}: no flag")
    # state / VP / region localisation
    for lang in ("english", "russian"):
        txt = read(ROOT / f"localisation/{lang}/totu_map_l_{lang}.yml")
        keys = set(re.findall(r"^\s([A-Za-z0-9_]+):0", txt, re.M))
        for sid in state_ids:
            if f"STATE_{sid}" not in keys:
                err(f"{lang}: missing STATE_{sid}")
        for sid, v in vps_of_state.items():
            for p in v:
                if f"VICTORY_POINTS_{p}" not in keys:
                    err(f"{lang}: missing VICTORY_POINTS_{p}")
    # bookmark tags
    bm = read(ROOT / "common/bookmarks/totu_1990.txt")
    for t in set(re.findall(r'"([A-Z]{3})"\s*=\s*\{', bm)):
        if t not in tags:
            err(f"bookmark references unknown tag {t}")

    # ---------------- strategic regions
    seen = {}
    nland = nsea = 0
    for f in (ROOT / "map/strategicregions").glob("*.txt"):
        t = read(f)
        rid = int(re.search(r"\bid\s*=\s*(\d+)", t).group(1))
        provs = [int(x) for x in re.search(r"provinces\s*=\s*\{([^}]*)\}", t).group(1).split()]
        if "weather" not in t:
            err(f"{f.name}: no weather block")
        if provs and kind.get(provs[0]) == "sea":
            nsea += 1
        else:
            nland += 1
        for p in provs:
            if p in seen:
                err(f"province {p} in strategic regions {seen[p]} and {rid}")
            seen[p] = rid
    for p in range(1, N + 1):
        if p not in seen:
            err(f"province {p} is in no strategic region")
    # ---------------- other map files
    for i, line in enumerate(read(ROOT / "map/adjacencies.csv").splitlines()[1:-1]):
        f = line.split(";")
        if int(f[0]) not in kind or int(f[1]) not in kind:
            err(f"adjacencies.csv: unknown province in {line}")
    if not read(ROOT / "map/adjacencies.csv").rstrip().endswith("-1;-1;;;;;;;;"):
        err("adjacencies.csv: missing terminator")
    for line in read(ROOT / "map/buildings.txt").splitlines():
        f = line.split(";")
        if len(f) != 7:
            err(f"buildings.txt: bad line {line}")
            break
        if f[1] in ("bunker", "coastal_bunker", "naval_base"):
            if int(f[0]) not in land_ids:
                err(f"buildings.txt: province {f[0]} not land")
        elif int(f[0]) not in state_ids:
            err(f"buildings.txt: unknown state {f[0]}")
    up = {int(l.split(";")[0]) for l in read(ROOT / "map/unitstacks.txt").splitlines()}
    if up != set(range(1, N + 1)):
        err("unitstacks.txt does not cover every province")
    nodes = [int(l.split()[1]) for l in read(ROOT / "map/supply_nodes.txt").splitlines()]
    if len(set(state_of[p] for p in nodes)) != nstates:
        err("supply_nodes.txt: not exactly one node per state")
    for line in read(ROOT / "map/railways.txt").splitlines():
        f = [int(x) for x in line.split()]
        path = f[2:]
        if f[1] != len(path):
            err(f"railways.txt: length mismatch {line[:40]}")
        for x, y in zip(path, path[1:]):
            if (min(x, y), max(x, y)) not in adj:
                err(f"railways.txt: provinces {x},{y} are not adjacent")
                break
    for fn in ("airports.txt", "rocketsites.txt"):
        for l in read(ROOT / "map" / fn).splitlines():
            s, p = map(int, l.split(";"))
            if state_of.get(p) != s:
                err(f"{fn}: province {p} not in state {s}")
    dm = read(ROOT / "map/default.map")
    if f"max_provinces = {N + 1}" not in dm:
        err("default.map: max_provinces mismatch")
    for r in ("history/states", "history/countries", "common/country_tags", "common/countries",
              "map/strategicregions", "map/supplyareas", "common/state_category"):
        if f'replace_path="{r}"' not in read(ROOT / "descriptor.mod"):
            err(f"descriptor.mod: replace_path {r} missing")

    # ---------------- stats
    nl = sum(1 for k in kind.values() if k == "land")
    ns = sum(1 for k in kind.values() if k == "sea")
    nk = sum(1 for k in kind.values() if k == "lake")
    print(f"provinces: {N} (land {nl}, sea {ns}, lake {nk})")
    print(f"states: {nstates}, victory points: {vp_total}, countries: {len(owners)} (tags defined {len(tags)})")
    print(f"strategic regions: land {nland}, sea {nsea}; X-crossings: {xc}")
    print(f"province area px: min {int(area[1:].min())}, median {int(np.median(area[1:]))}, max {int(area[1:].max())}")
    for w_ in warnings:
        print("WARNING:", w_)
    if errors:
        print(f"\n{len(errors)} ERRORS:")
        for e in errors:
            print(" -", e)
        sys.exit(1)
    print("\nVALIDATION PASSED")


if __name__ == "__main__":
    main()
