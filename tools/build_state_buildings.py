"""Writes the 1990 buildings block of every history/states file (deterministic, no randomness).

Inputs are read from the state files themselves (owner, manpower = population, state_category, victory points,
provinces) and map/definition.csv (which provinces are coastal). Slot counts come from
common/state_category/totu_state_categories.txt.

  infrastructure  by state category and the development tier of the country
  arms_factory / industrial_complex / dockyard
                  per country: total factories ~ GDP (billion USD, 1990, gamified for SOV / PRC) / 12, capped at 85%
                  of the country's building slots; military share per country; dockyards in the best coastal
                  states (naval table); state weights favour big states
  air_base        capitals (level by country size) and, for big air powers, large cities
  naval_base      coastal victory-point cities (level from the city's VP value and the country's navy class)

Usage: python tools/build_state_buildings.py   (then tools/validate_map.py)
"""
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------- tables
TIER = {}
for tier, tags in {
    "A": "USA CAN JAP GER AUS AST NZL ENG FRA ITA SWE NOR DEN FIN HOL BEL SWI LUX ICE IRE SPR POR SIN MCO LIE AND SMR KUW QAT UAE",
    "B": "SOV DDR CZE HUN POL YUG GRE KOR CHI ISR BHR OMA SAU LBA CYP MLT BRU TTO BHS BRB",
    "C": "BUL ROM TUR BRA MEX ARG CHL URG VEN MAL SAF PER IRQ PAN COS JAM CUB LEB TRJ GAB MUS FIJ SUR ATG KNA LCA GRD DMA VCT SYC",
    "E": "AFG BDI BEN BFA CAF CHD COM DJI ETH GIN GMB GNB GNQ LIB LSO MAD MLI MOZ MRT MWI NIG NEP RWA SEN SLE SOM STP "
         "SUD TGO TZA UGA YEM YES ZAI ZAM ZIM BHU LAO CAM BRM ANG HAI SWZ KEN CGO CMR CIV GHA NGA TUN PNG SLB VUT "
         "WSM TON TUV KIR NRU MHL FSM PLW MDV CPV",
}.items():
    for t in tags.split():
        TIER[t] = tier
PER_CAPITA = {"A": 17000, "B": 7000, "C": 3500, "D": 1300, "E": 450}
GDP = {"USA": 5900, "JAP": 3000, "GER": 1500, "FRA": 1200, "ITA": 1100, "ENG": 1000, "SOV": 5000, "CAN": 590,
       "PRC": 1500, "RAJ": 500, "SPR": 520, "BRA": 450, "KOR": 270, "AST": 310, "MEX": 260, "DDR": 200}
MIL_SHARE = {"SOV": 0.55, "USA": 0.30, "PRC": 0.40, "PRK": 0.60, "ISR": 0.45, "IRQ": 0.50, "KOR": 0.35, "CHI": 0.35,
             "ENG": 0.30, "FRA": 0.35, "GER": 0.25, "JAP": 0.12, "ITA": 0.25, "CZE": 0.40, "POL": 0.35, "DDR": 0.35,
             "ROM": 0.35, "BUL": 0.35, "YUG": 0.35, "SYR": 0.50, "EGY": 0.40, "PAK": 0.40, "RAJ": 0.30, "SAU": 0.30,
             "HUN": 0.30, "SWE": 0.30, "SWI": 0.15, "AUS": 0.12, "TUR": 0.30, "GRE": 0.30, "VIN": 0.40, "PER": 0.40,
             "LBA": 0.45, "CUB": 0.40}
DEFAULT_MIL = 0.20
DOCKS = {"USA": 40, "SOV": 40, "JAP": 18, "ENG": 14, "FRA": 12, "PRC": 12, "KOR": 8, "ITA": 7, "GER": 6, "CHI": 6,
         "SPR": 6, "RAJ": 6, "NEI": 4, "BRA": 4, "HOL": 3, "AST": 3, "CAN": 3, "TUR": 3, "GRE": 3, "SWE": 3, "POL": 3,
         "YUG": 3, "PRK": 3, "ARG": 2, "NOR": 2, "DEN": 2, "DDR": 2, "ROM": 2, "VIN": 2, "EGY": 2, "MEX": 2, "POR": 2,
         "FIN": 2, "BUL": 1, "ISR": 1, "PER": 1, "CHL": 1, "PHI": 1, "SIA": 1, "BEL": 1, "SAF": 1, "PAK": 1}
NAVY_CLASS = {"USA": 1.2, "SOV": 1.2, "ENG": 1.2, "FRA": 1.2, "JAP": 1.2, "PRC": 1.0, "ITA": 1.0, "GER": 1.0,
              "KOR": 1.0, "CHI": 1.0, "SPR": 1.0, "RAJ": 1.0}
INFRA_BASE = {"wasteland": 1, "tiny_island": 1, "small_island": 1, "pastoral": 1, "rural": 2, "town": 2,
              "large_town": 3, "city": 3, "large_city": 4, "metropolis": 4, "megalopolis": 5}
AIR_POWER = {"USA": 9, "SOV": 9, "ENG": 6, "FRA": 6, "GER": 5, "JAP": 5, "PRC": 6, "ITA": 4, "RAJ": 4, "ISR": 5,
             "KOR": 4, "CHI": 4, "CAN": 4, "SPR": 3, "PAK": 3, "EGY": 3, "POL": 3, "CZE": 3, "DDR": 3, "TUR": 3,
             "AST": 3, "BRA": 3, "SAU": 3, "PRK": 3, "SWE": 4}
BIG_AIR = {"USA", "SOV", "PRC"}      # large cities get an air base as well
FILL_CAP = 0.85


def tier(tag):
    return TIER.get(tag, "D")


def slots_table():
    txt = (ROOT / "common/state_category/totu_state_categories.txt").read_text(encoding="utf-8")
    return {m.group(1): int(m.group(2)) for m in re.finditer(r"(\w+) = \{\s*color = \{[^}]*\}\s*local_building_slots = (\d+)", txt)}


def read_states():
    coast = set()
    for line in (ROOT / "map/definition.csv").read_text(encoding="utf-8-sig").splitlines()[1:]:
        f = line.split(";")
        if f[4] == "land" and f[5] == "true":
            coast.add(int(f[0]))
    out = []
    for f in sorted((ROOT / "history/states").glob("*.txt"), key=lambda p: int(p.name.split("-")[0])):
        t = f.read_text(encoding="utf-8-sig")
        provs = [int(x) for x in re.search(r"provinces\s*=\s*\{([^}]*)\}", t).group(1).split()]
        vps = {int(a): int(b) for a, b in re.findall(r"victory_points\s*=\s*\{\s*(\d+)\s+(\d+)", t)}
        out.append(dict(file=f, text=t, id=int(re.search(r"\bid\s*=\s*(\d+)", t).group(1)),
                        owner=re.search(r"\bowner\s*=\s*(\w+)", t).group(1),
                        pop=int(re.search(r"manpower\s*=\s*(\d+)", t).group(1)),
                        cat=re.search(r"state_category\s*=\s*(\w+)", t).group(1), provs=provs, vps=vps,
                        coastal=[p for p in provs if p in coast]))
    return out


def alloc(total, weights, caps):
    """Largest-remainder allocation of `total` units to keys by weight, each key capped; deterministic."""
    res = {k: 0 for k in weights}
    left = total
    active = {k for k in weights if caps[k] > 0 and weights[k] > 0}
    while left > 0 and active:
        wsum = sum(weights[k] for k in active)
        share = {k: left * weights[k] / wsum for k in active}
        given = 0
        for k in sorted(active):
            n = min(int(share[k]), caps[k] - res[k])
            res[k] += n
            given += n
        left -= given
        rest = sorted(active, key=lambda k: (-(share[k] - int(share[k])), k))
        for k in rest:
            if left <= 0:
                break
            if res[k] < caps[k]:
                res[k] += 1
                left -= 1
        active = {k for k in active if res[k] < caps[k]}
    return res


def build_country(tag, sts, slots, capital_id):
    cap = {s["id"]: slots[s["cat"]] for s in sts}
    pop = sum(s["pop"] for s in sts)
    gdp = GDP.get(tag, pop * PER_CAPITA[tier(tag)] / 1e9)
    total_cap = sum(cap.values())
    nfact = int(gdp / 12 + 0.5)
    if pop >= 2_000_000:
        nfact = max(nfact, 1)
    nfact = min(nfact, int(total_cap * FILL_CAP))
    # dockyards: coastal states, weight = best coastal victory point (city size) + state size
    ndock = min(DOCKS.get(tag, 1 if (tier(tag) in "AB" and pop > 2_000_000) else 0), int(total_cap * 0.3))
    port = {}
    for s in sts:
        if s["coastal"] and cap[s["id"]] >= 3:
            best = max([v for p, v in s["vps"].items() if p in s["coastal"]] or [0])
            port[s["id"]] = best + cap[s["id"]]
    if not port:
        ndock = 0
    dock = alloc(ndock, {k: v ** 1.5 for k, v in port.items()}, {k: max(1, cap[k] // 2) for k in port}) if ndock else {}
    free = {s["id"]: cap[s["id"]] - dock.get(s["id"], 0) for s in sts}
    fw = {k: (v ** 1.4) * (1.4 if k == capital_id else 1.0) for k, v in free.items()}
    fcap = {k: int(v * FILL_CAP + 0.5) if v > 1 else v for k, v in free.items()}
    nfact = min(nfact, sum(fcap.values()))
    fact = alloc(nfact, fw, fcap)
    share = MIL_SHARE.get(tag, DEFAULT_MIL)
    res, carry = {}, 0.0
    for s in sts:
        n = fact.get(s["id"], 0)
        want = n * share + carry
        mil = min(n, int(round(want)))
        carry = want - mil
        res[s["id"]] = (mil, n - mil, dock.get(s["id"], 0))
    return res


def infra(s, tag):
    b = INFRA_BASE[s["cat"]]
    t = tier(tag)
    if t == "A":
        b = b + 1
    elif t == "D" and b >= 4:
        b -= 1
    elif t == "E" and b >= 3:
        b -= 1
    return max(1, min(5, b))


def air_level(s, tag, is_cap):
    p = AIR_POWER.get(tag)
    if p is None:
        p = {"A": 3, "B": 2}.get(tier(tag), 1)
    if is_cap:
        return p
    if tag in BIG_AIR and s["cat"] in ("city", "large_city", "metropolis", "megalopolis"):
        return max(1, p - 4)
    return 0


def naval_levels(s, tag, is_cap):
    """coastal VP provinces -> naval base level"""
    mult = NAVY_CLASS.get(tag, 0.8)
    out = {}
    for p, v in s["vps"].items():
        if p in s["coastal"] and v >= 4:
            out[p] = max(1, min(10, int(round(v * mult / 3.0))))
    if is_cap and not out:
        c = [p for p in s["vps"] if p in s["coastal"]]
        if c:
            out[max(c, key=lambda p: s["vps"][p])] = 1
    return out


def block(infra_lvl, mil, civ, dock, air, naval):
    lines = [f"\t\t\tinfrastructure = {infra_lvl}"]
    if civ:
        lines.append(f"\t\t\tindustrial_complex = {civ}")
    if mil:
        lines.append(f"\t\t\tarms_factory = {mil}")
    if dock:
        lines.append(f"\t\t\tdockyard = {dock}")
    if air:
        lines.append(f"\t\t\tair_base = {air}")
    for p in sorted(naval):
        lines.append(f"\t\t\t{p} = {{\n\t\t\t\tnaval_base = {naval[p]}\n\t\t\t}}")
    return "\t\tbuildings = {\n" + "\n".join(lines) + "\n\t\t}\n"


def capitals():
    cap = {}
    for f in (ROOT / "history/countries").glob("*.txt"):
        m = re.search(r"^capital\s*=\s*(\d+)", f.read_text(encoding="utf-8-sig"), re.M)
        if m:
            cap[f.name.split(" - ")[0]] = int(m.group(1))
    return cap


def main():
    slots = slots_table()
    states = read_states()
    caps = capitals()
    by = {}
    for s in states:
        by.setdefault(s["owner"], []).append(s)
    totals = {}
    for tag in sorted(by):
        sts = by[tag]
        res = build_country(tag, sts, slots, caps.get(tag))
        for s in sts:
            mil, civ, dock = res[s["id"]]
            is_cap = s["id"] == caps.get(tag)
            new = block(infra(s, tag), mil, civ, dock, air_level(s, tag, is_cap), naval_levels(s, tag, is_cap))
            t = re.sub(r"\t\tbuildings = \{.*?\n\t\t\}\n", lambda m: new, s["text"], count=1, flags=re.S)
            assert t != s["text"] or new in s["text"], s["file"]
            s["file"].write_text(t, encoding="utf-8")
            a = totals.setdefault(tag, [0, 0, 0])
            a[0] += mil; a[1] += civ; a[2] += dock
    for tag in ("USA", "SOV", "JAP", "GER", "PRC", "ENG", "FRA", "ITA", "RAJ", "POL", "CZE", "DDR"):
        print(tag, "mil/civ/dock", totals[tag])
    print("total factories", sum(a[0] + a[1] for a in totals.values()), "docks", sum(a[2] for a in totals.values()))


if __name__ == "__main__":
    main()
