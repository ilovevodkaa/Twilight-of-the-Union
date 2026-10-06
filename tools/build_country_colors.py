"""Assigns map-friendly, mutually distinct country colours.

Adjacency comes from map/provinces.bmp + history/states (owner + provinces). Iconic colours are pinned;
the rest are greedily picked from a muted Lab palette so that neighbours differ by dE >= ~20.
Rewrites common/countries/*.txt (color line) and common/countries/colors.txt, and re-renders docs/images/map_1990.jpg.
Usage: python tools/build_country_colors.py
"""
import re
import colorsys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
MIN_DE = 20.0

PINNED = {
    "SOV": (150, 28, 32), "USA": (62, 98, 168), "ENG": (214, 104, 124), "FRA": (96, 100, 186),
    "GER": (128, 128, 130), "DDR": (92, 70, 74), "PRC": (214, 186, 70), "CHI": (226, 200, 90),
    "JAP": (232, 226, 218), "POL": (226, 140, 170), "ITA": (84, 150, 90), "CAN": (206, 108, 70),
    "AST": (70, 120, 160), "RAJ": (222, 154, 70), "BRA": (70, 146, 76), "SPR": (210, 168, 60),
    "CZE": (120, 100, 170), "YUG": (70, 100, 150), "TUR": (178, 120, 78), "PRK": (160, 60, 80),
}


def to_lab(rgb):
    a = np.asarray(rgb, np.float64).reshape(-1, 3) / 255.0
    a = np.where(a > 0.04045, ((a + 0.055) / 1.055) ** 2.4, a / 12.92)
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = a @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[:, 1] - 16, 500 * (f[:, 0] - f[:, 1]), 200 * (f[:, 1] - f[:, 2])], 1)


def from_lab(L, a, b):
    fy = (L + 16) / 116
    fx, fz = fy + a / 500, fy - b / 200
    f = lambda t: t ** 3 if t ** 3 > 0.008856 else (t - 16 / 116) / 7.787
    xyz = np.array([f(fx) * 0.95047, f(fy), f(fz) * 1.08883])
    m = np.array([[3.2406, -1.5372, -0.4986], [-0.9689, 1.8758, 0.0415], [0.0557, -0.2040, 1.0570]])
    lin = m @ xyz
    if lin.min() < -0.001 or lin.max() > 1.001:
        return None
    lin = np.clip(lin, 0, 1)
    c = np.where(lin > 0.0031308, 1.055 * lin ** (1 / 2.4) - 0.055, 12.92 * lin)
    return tuple(int(round(v * 255)) for v in c)


def palette():
    out = []
    for L in (46, 54, 62, 70, 78):
        for ch in (22, 32, 42, 52):
            for h in range(0, 360, 10):
                a, b = ch * np.cos(np.radians(h)), ch * np.sin(np.radians(h))
                c = from_lab(L, a, b)
                if c:
                    out.append(c)
    # muted neutrals
    for L in (50, 62, 74):
        out.append(from_lab(L, 0, 6))
    return out


def owners():
    prov_owner = {}
    for f in (ROOT / "history/states").glob("*.txt"):
        t = f.read_text(encoding="utf-8-sig")
        o = re.search(r"owner\s*=\s*(\w+)", t)
        p = re.search(r"provinces\s*=\s*\{([^}]*)\}", t)
        if o and p:
            for n in p.group(1).split():
                prov_owner[int(n)] = o.group(1)
    return prov_owner


def adjacency(prov_owner):
    img = np.asarray(Image.open(ROOT / "map/provinces.bmp").convert("RGB")).astype(np.int64)
    key = (img[..., 0] << 16) | (img[..., 1] << 8) | img[..., 2]
    col2id = {}
    for line in (ROOT / "map/definition.csv").read_text(encoding="utf-8").splitlines()[1:]:
        f = line.split(";")
        if len(f) > 4:
            col2id[(int(f[1]) << 16) | (int(f[2]) << 8) | int(f[3])] = int(f[0])
    uk, inv = np.unique(key, return_inverse=True)
    ids = np.array([col2id.get(int(k), 0) for k in uk])
    P = ids[inv.reshape(key.shape)]
    tags = sorted(set(prov_owner.values()))
    ti = {t: i + 1 for i, t in enumerate(tags)}
    lut = np.zeros(P.max() + 1, np.int32)
    for p, t in prov_owner.items():
        if p < len(lut):
            lut[p] = ti[t]
    T = lut[P]
    pairs = set()
    for a, b in ((T[:, :-1], T[:, 1:]), (T[:-1], T[1:]), (T[:, -1:], T[:, :1])):
        m = (a != b) & (a > 0) & (b > 0)
        pairs |= set(zip(*np.sort(np.stack([a[m], b[m]]), 0)))
    adj = {t: set() for t in tags}
    for a, b in pairs:
        adj[tags[a - 1]].add(tags[b - 1])
        adj[tags[b - 1]].add(tags[a - 1])
    return adj


def main():
    adj = adjacency(owners())
    pal = palette()
    plab = to_lab(pal)
    SEA = to_lab([(28, 52, 96)])[0]
    order = sorted(adj, key=lambda t: (-len(adj[t]), t))
    color = {t: PINNED[t] for t in adj if t in PINNED}
    lab = {t: to_lab([c])[0] for t, c in color.items()}
    used = np.zeros(len(pal), int)
    rng = np.random.RandomState(1990)
    for t in order:
        if t in color:
            continue
        nb = [lab[n] for n in adj[t] if n in lab]
        d = np.full(len(pal), 99.0)
        for n in nb:
            d = np.minimum(d, np.linalg.norm(plab - n, axis=1))
        d = np.minimum(d, 0.7 * np.linalg.norm(plab - SEA, axis=1) + 8)  # keep off the sea colour
        # prefer sufficiently distinct, then globally rarer colours, with a little jitter
        score = np.minimum(d, MIN_DE + 6) * 10 - used * 3 + rng.rand(len(pal)) * 8
        i = int(np.argmax(score))
        color[t] = pal[i]
        lab[t] = plab[i]
        used[i] += 1
    bad = []
    for t in adj:
        for n in adj[t]:
            if t < n:
                de = float(np.linalg.norm(lab[t] - lab[n]))
                if de < MIN_DE - 2:
                    bad.append((t, n, round(de, 1)))
    print("tags", len(color), "close neighbour pairs:", bad)

    # write files
    tagfile = (ROOT / "common/country_tags/totu_countries.txt").read_text(encoding="utf-8-sig")
    tag_file = dict(re.findall(r'^([A-Z0-9]{3}) = "countries/(.+?)"', tagfile, re.M))
    out = ["# GENERATED by tools/build_country_colors.py", ""]
    for t in sorted(tag_file):
        c = color[t]
        ui = tuple(min(255, int(v * 1.15 + 8)) for v in c)
        p = ROOT / "common/countries" / tag_file[t]
        txt = p.read_text(encoding="utf-8-sig")
        txt = re.sub(r"color = \{[^}]*\}", f"color = {{ {c[0]} {c[1]} {c[2]} }}", txt)
        p.write_text(txt, encoding="utf-8")
        out.append(f"{t} = {{\n\tcolor = rgb {{ {c[0]} {c[1]} {c[2]} }}\n\tcolor_ui = rgb {{ {ui[0]} {ui[1]} {ui[2]} }}\n}}")
    (ROOT / "common/countries/colors.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
    render(color)


def render(color):
    """Recolour the existing preview from map/provinces.bmp ownership (no map regeneration)."""
    import cv2
    prov_owner = owners()
    img = np.asarray(Image.open(ROOT / "map/provinces.bmp").convert("RGB")).astype(np.int64)
    key = (img[..., 0] << 16) | (img[..., 1] << 8) | img[..., 2]
    col2id, kind = {}, {}
    for line in (ROOT / "map/definition.csv").read_text(encoding="utf-8").splitlines()[1:]:
        f = line.split(";")
        if len(f) > 4:
            i = int(f[0])
            col2id[(int(f[1]) << 16) | (int(f[2]) << 8) | int(f[3])] = i
            kind[i] = f[4]
    uk, inv = np.unique(key, return_inverse=True)
    ids = np.array([col2id.get(int(k), 0) for k in uk])
    P = ids[inv.reshape(key.shape)]
    n = P.max() + 1
    lut = np.zeros((n, 3), np.float32)
    for p, t in prov_owner.items():
        if p < n:
            lut[p] = color[t]
    sea = np.zeros(n, bool)
    lake = np.zeros(n, bool)
    for i, k in kind.items():
        sea[i] = k == "sea"
        lake[i] = k == "lake"
    out = lut[P]
    out[sea[P]] = (28, 52, 96)
    out[lake[P]] = (70, 120, 190)
    owner_id = np.zeros(n, np.int32)
    tl = {t: i + 1 for i, t in enumerate(sorted(set(prov_owner.values())))}
    for p, t in prov_owner.items():
        if p < n:
            owner_id[p] = tl[t]
    T = owner_id[P]
    cb = np.zeros(T.shape, bool)
    cb[:, :-1] |= (T[:, :-1] != T[:, 1:]) & (T[:, :-1] > 0) & (T[:, 1:] > 0)
    cb[:-1] |= (T[:-1] != T[1:]) & (T[:-1] > 0) & (T[1:] > 0)
    out[cb & ~sea[P]] = (28, 28, 28)
    w = 1600
    res = cv2.resize(np.clip(out, 0, 255).astype(np.uint8), (w, int(w * out.shape[0] / out.shape[1])), interpolation=cv2.INTER_AREA)
    Image.fromarray(res).save(ROOT / "docs/images/map_1990.jpg", quality=88, optimize=True)


if __name__ == "__main__":
    main()
