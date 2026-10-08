"""Checks the mod's map against the rules that crash or break HOI4 (see tools/map1990/check.py). Exit 1 on a problem.

Usage:  python tools/check_map.py [--game PATH]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from map1990 import check, common  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game")
    args = ap.parse_args()
    problems = check.run(common.ROOT, common.find_game(args.game))
    for p in problems[:200]:
        print(p)
    print(f"{len(problems)} problems")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
