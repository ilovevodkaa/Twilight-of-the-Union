"""The vanilla HOI4 map files read into plain structures. The game folder is only read."""
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image

from .common import MAP_H, MAP_W


@dataclass
class Province:
    id: int
    rgb: tuple
    kind: str           # land / sea / lake
    coastal: bool
    terrain: str
    continent: int


@dataclass
class IdFile:
    file: str           # file name in its folder
    text: str
    items: list = field(default_factory=list)   # province ids (strategic region) or state ids (supply area)


def read_lines(path):
    return path.read_text(encoding="utf-8-sig").splitlines()


def read_definitions(path):
    provs = {}
    for line in path.read_text(encoding="latin-1").splitlines():
        p = line.split(";")
        if len(p) >= 8 and p[0].isdigit() and p[0] != "0":
            provs[int(p[0])] = Province(int(p[0]), (int(p[1]), int(p[2]), int(p[3])), p[4], p[5] == "true",
                                        p[6], int(p[7]))
    return provs


def rgb_key(img):
    img = img.astype(np.int64)
    return (img[..., 0] << 16) | (img[..., 1] << 8) | img[..., 2]


def read_province_ids(bmp, provs):
    key = rgb_key(np.asarray(Image.open(bmp).convert("RGB")))
    lut = {(p.rgb[0] << 16) | (p.rgb[1] << 8) | p.rgb[2]: pid for pid, p in provs.items()}
    uk, inv = np.unique(key.ravel(), return_inverse=True)
    return np.array([lut.get(int(k), 0) for k in uk], np.int32)[inv].reshape(key.shape)


def read_id_files(folder, block):
    out = {}
    for f in sorted(folder.glob("*.txt")):
        text = f.read_text(encoding="utf-8-sig")
        m = re.search(r"\bid\s*=\s*(\d+)", text)
        b = re.search(block + r"\s*=\s*\{([^}]*)\}", text)
        out[int(m.group(1))] = IdFile(f.name, text, [int(x) for x in re.sub(r"#[^\n]*", "", b.group(1)).split()])
    return out


class VanillaMap:
    def __init__(self, game):
        m = Path(game) / "map"
        self.game = Path(game)
        self.provs = read_definitions(m / "definition.csv")
        self.ids = read_province_ids(m / "provinces.bmp", self.provs)
        assert self.ids.shape == (MAP_H, MAP_W), self.ids.shape
        self.height = np.asarray(Image.open(m / "heightmap.bmp").convert("L"))
        self.regions = read_id_files(m / "strategicregions", "provinces")
        self.supply_areas = read_id_files(m / "supplyareas", "states")
        self.buildings = [line.split(";") for line in read_lines(m / "buildings.txt") if line.strip()]
        self.unitstacks = [line.split(";") for line in read_lines(m / "unitstacks.txt") if line.strip()]
        self.railways = []
        for line in read_lines(m / "railways.txt"):
            f = line.split()
            if len(f) >= 3:
                self.railways.append((int(f[0]), [int(x) for x in f[2:2 + int(f[1])]]))
        self.supply_nodes = [(int(f[0]), int(f[1])) for f in (line.split() for line in read_lines(m / "supply_nodes.txt"))
                             if len(f) >= 2]
        self.adjacency_lines = read_lines(m / "adjacencies.csv")
