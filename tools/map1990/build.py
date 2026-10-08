"""Entry of the map rebuild, called by tools/build_world_1990.py right after assign(states): rebuilds the zone in
the in-memory states (and the names of tools/world1990/names.py), writes map/* and the before/after previews."""
import shutil
import time

import numpy as np

from . import mapfiles, preview, states as states_mod
from .assemble import assemble
from .common import ROOT
from .georef import Georef
from .units import ZONES
from .vanilla import VanillaMap

OUTPUTS = ("provinces.bmp", "definition.csv", "strategicregions", "unitstacks.txt", "railways.txt",
           "supply_nodes.txt", "adjacencies.csv", "buildings.txt")
PREVIEW_BOXES = {"germany": (2880, 420, 3070, 600), "korea": (4730, 650, 4870, 840)}


def run(game, states, root, names, zone="pilot", vp_names=None, log=print):
    t0 = time.time()
    vm = VanillaMap(game)
    z = ZONES[zone]
    before = {p: s for s, st in states.items() for p in st["provs"]}
    zm = assemble(vm, Georef(), z, states, log=log)
    res = states_mod.apply(zm, vm, z, states, names, vp_names=vp_names)
    mapfiles.write_all(zm, vm, states, root / "map")
    after = {p: s for s, st in states.items() for p in st["provs"]}
    land = np.isin(zm.ids, [p for p, v in zm.provs.items() if v.kind == "land"])
    vps = [(c.row, c.col) for c, _ in zm.city_prov]
    (root / "tools/preview").mkdir(parents=True, exist_ok=True)
    for name, box in PREVIEW_BOXES.items():
        preview.render(vm.ids, zm.ids, before, after, land, vps, box, root / f"tools/preview/map1990_{name}.png")
    for line in res["report"]:
        log(line)
    log(f"map1990: zone {zone} rebuilt in {time.time() - t0:.0f} s; country capitals {res['capitals']}")
    return res


def clean(map_dir=ROOT / "map"):
    """Remove the rebuild's files (build_world_1990.py --no-map goes back to the vanilla provinces)."""
    for name in OUTPUTS:
        p = map_dir / name
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists() and name != "buildings.txt":
            p.unlink()
