"""Paths and constants shared by the map1990 modules."""
import math
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "tools" / "data"
GEO = DATA / "geo"
GAME_GUESSES = [r"D:\steam\steamapps\common\Hearts of Iron IV",
                r"C:\Program Files (x86)\Steam\steamapps\common\Hearts of Iron IV"]
MAP_W, MAP_H = 5632, 2048
MIN_PROVINCE_PX = 12


def find_game(arg=None):
    for g in ([arg] if arg else []) + GAME_GUESSES:
        if g and Path(g).exists():
            return Path(g)
    raise SystemExit("HOI4 install not found, pass --game")


def stable_seed(key):
    return zlib.crc32(key.encode("utf-8"))


def px_of(x, z):
    """Map position (x, z) of buildings.txt / unitstacks.txt -> (row, col) of provinces.bmp. A whole-number z lies on
    the edge between two rows and belongs to the northern one, as in the engine (vanilla ports sit on such edges)."""
    return min(MAP_H - 1, max(0, MAP_H - 1 - math.floor(z))), min(MAP_W - 1, max(0, math.floor(x)))
