"""Cores and claims in history/states, plus the stub tags (tools/stub_tags.py).

 * every SOV state gets a core of its Soviet republic (RUS, UKR, BLR, MOL, EST, LAT, LIT, GEO, ARM, AZR, KAZ, UZB, TMS,
   KYR, TAJ); every YUG state of its republic (SLV, CRO, BOS, SER, MNT, MAC; Kosovo is Serbian); CZE states of CZR / SLO;
   Western Sahara of SAH. The owner always keeps its own core.
 * claims for the disputed territories listed in CLAIMS / MUTUAL below.
 * stub tags: common/country_tags/totu_future_countries.txt, common/countries/<name>.txt, localisation (replace/),
   colours are appended by tools/build_country_colors.py, flags by tools/build_flags.py.
Admin data comes from tools/state_admin.json (tools/dump_state_admin.py). Idempotent.

Design decisions (documented in docs/CORES_AND_CLAIMS.md): DDR states are a CLAIM of GER (not a core), the claim
goes both ways only for Korea, Yemen and China/Taiwan.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stub_tags import STUBS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ADM = {int(k): v for k, v in json.loads((ROOT / "tools/state_admin.json").read_text(encoding="utf-8")).items()}

SSR = {"RUS": "RUS", "KAB": "RUS", "UKR": "UKR", "BLR": "BLR", "MDA": "MOL", "LTU": "LIT", "LVA": "LAT", "EST": "EST", "GEO": "GEO",
       "ARM": "ARM", "AZE": "AZR", "KAZ": "KAZ", "UZB": "UZB", "TKM": "TMS", "KGZ": "KYR", "TJK": "TAJ"}
YUGO = {"SRB": "SER", "KOS": "SER", "BIH": "BOS", "HRV": "CRO", "SVN": "SLV", "MNE": "MNT", "MKD": "MAC"}
CZSK = {"CZE": "CZR", "SVK": "SLO"}
WSAH = {"SAH": "SAH"}
CRIMEA = {"Autonomous Republic of Crimea", "Sevastopol", "Crimea"}
MIN_SHARE = 0.30   # a second republic counts as core when it covers this share of the state


def republic_cores(owner, sid):
    table = {"SOV": SSR, "YUG": YUGO, "CZE": CZSK, "MOR": WSAH}.get(owner)
    if not table:
        return []
    rows = ADM[sid]["g"]
    total = sum(r[1] for r in rows) or 1
    share = {}
    for adm0, area in rows:
        tag = table.get(adm0)
        if tag:
            share[tag] = share.get(tag, 0) + area
    if owner == "SOV" and any(r[1] in CRIMEA for r in ADM[sid]["r"]):
        share = {"UKR": total}
    if not share:
        return []
    best = max(share.values())
    return sorted(t for t, a in share.items() if a == best or a / total >= MIN_SHARE)


# claimant -> list of (state ids | predicate-on-(owner, rows)). Each entry: (claimant, [state ids], comment)
CLAIMS = [
    ("GER", "owner:DDR", "FRG Basic Law: reunification (claim, not core)"),
    ("JAP", [1836, 1784], "Southern Kuril Islands / Northern Territories"),
    ("PAK", [1413, 1416], "Kashmir (Indian-administered)"),
    ("RAJ", [1114, 1119], "Kashmir (Pakistani-administered: Gilgit-Baltistan, Azad Kashmir)"),
    ("RAJ", [1283, 1298], "Aksai Chin"),
    ("PRC", [1433], "Arunachal Pradesh (South Tibet)"),
    ("ARG", [621, 622], "Falkland Islands, South Georgia"),
    ("SYR", [783], "Golan Heights"),
    ("SYR", [2015], "Hatay"),
    ("TUR", [543], "Northern Cyprus (TRNC)"),
    ("SOM", [636, 640, 642], "Ogaden"),
    ("PHI", [888], "Sabah"),
    ("IRQ", [840], "Kuwait"),
    ("VEN", [740, 741], "Guayana Esequiba"),
    ("GUA", [189], "Belize"),
    ("ALB", "adm0:KOS", "Kosovo"),
    ("ROM", "adm0:MDA", "Bessarabia"),
    ("KOR", "owner:PRK", "Korean reunification"),
    ("PRK", "owner:KOR", "Korean reunification"),
    ("YES", "owner:YEM", "Yemeni unification"),
    ("YEM", "owner:YES", "Yemeni unification"),
    ("PRC", "owner:CHI", "Taiwan"),
    ("CHI", "owner:PRC", "Republic of China claims the mainland"),
]


def claim_states(sel, owners):
    if isinstance(sel, list):
        return sel
    kind, val = sel.split(":")
    if kind == "owner":
        return [s for s, o in owners.items() if o == val]
    return [s for s in owners if any(r[0] == val and r[1] >= 0.10 * sum(x[1] for x in ADM[s]["g"]) for r in ADM[s]["g"])]


def main():
    files = {}
    owners = {}
    for f in (ROOT / "history/states").glob("*.txt"):
        t = f.read_text(encoding="utf-8-sig")
        sid = int(re.search(r"\bid\s*=\s*(\d+)", t).group(1))
        files[sid] = (f, t)
        owners[sid] = re.search(r"\bowner\s*=\s*(\w+)", t).group(1)
    cores = {s: [o] for s, o in owners.items()}
    claims = {s: [] for s in owners}
    for s, o in owners.items():
        for tag in republic_cores(o, s):
            if tag not in cores[s]:
                cores[s].append(tag)
    # a republic that covers no state by itself (tiny share everywhere) still gets a core where it is largest
    for table in (SSR, YUGO, CZSK):
        for tag in sorted(set(table.values())):
            if not any(tag in c for c in cores.values()):
                cand = [(a, s) for s in owners for iso, a in ADM[s]["g"] if table.get(iso) == tag and owners[s] in ("SOV", "YUG", "CZE")]
                if cand:
                    cores[max(cand)[1]].append(tag)
    for claimant, sel, _ in CLAIMS:
        for s in claim_states(sel, owners):
            if s not in owners:
                raise SystemExit(f"claim: unknown state {s}")
            if owners[s] != claimant and claimant not in claims[s] and claimant not in cores[s]:
                claims[s].append(claimant)
    n = 0
    for s, (f, t) in files.items():
        t2 = re.sub(r"[ \t]*(?:add_core_of|add_claim_by)\s*=\s*\w+[ \t]*\n", "", t)
        add = "".join(f"\t\tadd_core_of = {c}\n" for c in cores[s]) + "".join(f"\t\tadd_claim_by = {c}\n" for c in claims[s])
        t2, k = re.subn(r"(\t\t\}\n)(\t\}\n\n\tprovinces)", lambda m: m.group(1) + add + m.group(2), t2, count=1)
        assert k == 1, f
        if t2 != t:
            f.write_text(t2, encoding="utf-8")
            n += 1
    print("states changed", n, "cores", sum(len(c) for c in cores.values()), "claims", sum(len(c) for c in claims.values()))
    write_stubs()


def write_stubs():
    tags = ["# GENERATED by tools/build_cores_claims.py (tools/stub_tags.py): countries that do not exist on 1 Jan 1990."]
    for tag in sorted(STUBS):
        en, ru, adj, adjru, iso, col, cult = STUBS[tag]
        fn = f"{en}.txt"
        tags.append(f'{tag} = "countries/{fn}"')
        (ROOT / "common/countries" / fn).write_text(
            f"graphical_culture = {cult}_gfx\ngraphical_culture_2d = {cult}_2d\ncolor = {{ {col[0]} {col[1]} {col[2]} }}\n", encoding="utf-8")
    (ROOT / "common/country_tags/totu_future_countries.txt").write_text("\n".join(tags) + "\n", encoding="utf-8")
    for lang, i_name, i_adj in (("english", 0, 2), ("russian", 1, 3)):
        lines = [f"l_{lang}:"]
        for tag in sorted(STUBS):
            nm, adj = STUBS[tag][i_name], STUBS[tag][i_adj]
            lines += [f' {tag}:0 "{nm}"', f' {tag}_DEF:0 "{nm}"', f' {tag}_ADJ:0 "{adj}"']
        p = ROOT / f"localisation/{lang}/replace/totu_future_countries_l_{lang}.yml"
        p.write_text("﻿" + "\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
