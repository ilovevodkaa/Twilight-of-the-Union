"""Builds gfx/flags/{,medium/,small/}TAG.tga (82x52, 41x26, 10x7; 32-bit uncompressed, bottom-left origin).

Sources: modern SVG flags from the npm package `flag-icons` (MIT; Wikimedia Commons was not reachable from the
build sandbox), cached under tools/cache/ (gitignored). Flags that differed in 1990 are hand-written SVG in
HISTORICAL below (simplified emblems). If a tag has neither, a plain fallback flag is drawn from its map colour.
Needs: pip install cairosvg pillow.  Usage: python tools/build_flags.py
"""
import io
import re
import sys
import tarfile
import urllib.request
from pathlib import Path

import cairosvg
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "tools" / "cache"
PKG_URL = "https://registry.npmjs.org/flag-icons/-/flag-icons-7.5.0.tgz"
SIZES = {"": (82, 52), "medium": (41, 26), "small": (10, 7)}

_t = ("AFG af ALB al ALG dz AND ad ANG ao ARG ar AST au ATG ag AUS at BAN bd BDI bi BEL be BEN bj BFA bf BHR bh BHS bs "
      "BHU bt BLZ bz BOL bo BRA br BRB bb BRM mm BRU bn BUL bg BWA bw CAF cf CAM kh CAN ca CEY lk CGO cg CHD td CHI tw "
      "CHL cl CIV ci CMR cm COL co COM km COS cr CPV cv CUB cu CYP cy CZE cz DDR de DEN dk DJI dj DMA dm DOM do ECU ec "
      "EGY eg ENG gb ETH et FIJ fj FIN fi FRA fr FSM fm GAB ga GER de GHA gh GIN gn GMB gm GNB gw GNQ gq GRD gd GRE gr "
      "GUA gt GUY gy HAI ht HOL nl HON hn HUN hu ICE is IRE ie IRQ iq ISR il ITA it JAM jm JAP jp KEN ke KIR ki KNA kn "
      "KOR kr KUW kw LAO la LBA ly LCA lc LEB lb LIB lr LIE li LSO ls LUX lu MAD mg MAL my MCO mc MDV mv MEX mx MHL mh "
      "MLI ml MLT mt MON mn MOR ma MOZ mz MRT mr MUS mu MWI mw NEI id NEP np NGA ng NIC ni NIG ne NOR no NRU nr NZL nz "
      "OMA om PAK pk PAN pa PAR py PER ir PHI ph PLW pw PNG pg POL pl POR pt PRC cn PRK kp PRU pe QAT qa RAJ in ROM ro "
      "RWA rw SAF za SAL sv SAU sa SEN sn SIA th SIN sg SLB sb SLE sl SMR sm SOM so SOV ru SPR es STP st SUD sd SUR sr "
      "SWE se SWI ch SWZ sz SYC sc SYR sy TGO tg TON to TRJ jo TTO tt TUN tn TUR tr TUV tv TZA tz UAE ae UGA ug URG uy "
      "USA us VCT vc VEN ve VIN vn VUT vu WSM ws YEM ye YES ye YUG rs ZAI cd ZAM zm ZIM zw").split()
ISO = dict(zip(_t[0::2], _t[1::2]))

SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 480" preserveAspectRatio="none">{}</svg>'


def rect(x, y, w, h, c):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{c}"/>'


def hstripes(*cols):
    h = 480 / len(cols)
    return "".join(rect(0, i * h, 640, h + 1, c) for i, c in enumerate(cols))


def vstripes(*cols):
    w = 640 / len(cols)
    return "".join(rect(i * w, 0, w + 1, 480, c) for i, c in enumerate(cols))


def star(cx, cy, r, c, rot=-90):
    import math
    pts = []
    for i in range(10):
        a = math.radians(rot + i * 36)
        rr = r if i % 2 == 0 else r * 0.382
        pts.append(f"{cx + rr * math.cos(a):.1f},{cy + rr * math.sin(a):.1f}")
    return f'<polygon points="{" ".join(pts)}" fill="{c}"/>'


def circle(cx, cy, r, c):
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{c}"/>'


def hammer_sickle(cx, cy, s, c):
    return (f'<g fill="none" stroke="{c}" stroke-width="{s * 0.12}" stroke-linecap="round">'
            f'<path d="M{cx - s * 0.6},{cy + s * 0.5} A{s * 0.8},{s * 0.8} 0 0 1 {cx + s * 0.3},{cy - s * 0.7}"/>'
            f'<path d="M{cx - s * 0.5},{cy - s * 0.6} L{cx + s * 0.6},{cy + s * 0.6}"/></g>'
            f'<rect x="{cx - s * 0.7}" y="{cy - s * 0.75}" width="{s * 0.5}" height="{s * 0.22}" fill="{c}"/>')


HISTORICAL = {
    "SOV": hstripes("#cc0000") + hammer_sickle(160, 150, 90, "#ffd700") + star(160, 70, 28, "#ffd700"),
    "DDR": hstripes("#000", "#dd0000", "#ffce00") + circle(320, 240, 105, "#ffce00") + circle(320, 240, 88, "#dd0000")
           + rect(290, 190, 60, 100, "#000") + rect(250, 225, 140, 30, "#ffce00"),
    "YUG": hstripes("#0c4076", "#fff", "#c6363c") + star(320, 240, 62, "#ffd200") + star(320, 240, 44, "#c6363c"),
    "YEM": hstripes("#ce1126", "#fff", "#000") + star(320, 240, 62, "#007a3d"),
    "YES": hstripes("#ce1126", "#fff", "#000") + '<polygon points="0,0 300,240 0,480" fill="#4a9fd8"/>' + star(80, 240, 48, "#ce1126"),
    "AFG": hstripes("#000", "#d32011", "#007a36") + circle(120, 110, 70, "#e6b800") + circle(120, 110, 45, "#d32011"),
    "BUL": hstripes("#fff", "#00966e", "#d62612") + circle(90, 90, 52, "#e6b800") + star(90, 90, 30, "#d62612"),
    "IRQ": hstripes("#ce1126", "#fff", "#000") + star(180, 240, 34, "#007a3d") + star(320, 240, 34, "#007a3d") + star(460, 240, 34, "#007a3d"),
    "LBA": hstripes("#239e46"),
    "ZAI": hstripes("#2e9c3c") + circle(320, 240, 150, "#f7d618") + circle(320, 240, 118, "#2e9c3c") + rect(300, 140, 40, 200, "#ce1126"),
    "BRM": hstripes("#c8102e") + rect(0, 0, 320, 240, "#0b2a66") + circle(160, 120, 70, "#fff") + circle(160, 120, 48, "#0b2a66"),
    "ETH": hstripes("#078930", "#fcdd09", "#da121a") + circle(320, 240, 90, "#0f47af") + star(320, 240, 60, "#fcdd09"),
    "SAF": hstripes("#e07b24", "#fff", "#1d3f8f") + rect(280, 200, 80, 80, "#fff") + rect(300, 230, 40, 20, "#1b5e20"),
    "LSO": hstripes("#fff", "#0033a0", "#009543") + circle(320, 240, 60, "#000"),
    "BEN": hstripes("#008751") + star(110, 100, 60, "#e8112d"),
    "CGO": hstripes("#d21034") + star(100, 100, 60, "#ffd100"),
    "COM": hstripes("#3a9a3a") + circle(300, 240, 120, "#fff") + circle(340, 240, 100, "#3a9a3a"),
    "MRT": hstripes("#006233") + circle(320, 250, 110, "#ffc400") + circle(320, 210, 110, "#006233") + star(320, 150, 40, "#ffc400"),
    "RWA": vstripes("#d01c1f", "#fcd116", "#00a550") + rect(300, 200, 40, 90, "#000"),
    "CPV": vstripes("#d21034", "#f7d116", "#00a651") + star(210, 240, 56, "#000"),
    "SYC": hstripes("#009a44", "#fff", "#d62828"),
    "CAM": hstripes("#e00025", "#0032a0") + rect(200, 190, 240, 100, "#ffd100"),
    "POL": hstripes("#fff", "#dc143c"),
}
HISTORICAL["SYC"] = hstripes("#d62828", "#fff", "#009a44")
del HISTORICAL["POL"]  # modern Polish flag is identical to 1990


def fetch_icons():
    CACHE.mkdir(parents=True, exist_ok=True)
    tgz = CACHE / "flag-icons.tgz"
    if not tgz.exists():
        urllib.request.urlretrieve(PKG_URL, tgz)
    out = {}
    with tarfile.open(tgz) as t:
        for m in t.getmembers():
            mm = re.match(r"package/flags/4x3/([a-z]{2})\.svg$", m.name)
            if mm:
                out[mm.group(1)] = t.extractfile(m).read()
    return out


def fallback_svg(tag):
    txt = (ROOT / "common/countries/colors.txt").read_text(encoding="utf-8")
    m = re.search(tag + r" = \{\s*color = rgb \{ (\d+) (\d+) (\d+) \}", txt)
    c = "#%02x%02x%02x" % tuple(map(int, m.groups())) if m else "#808080"
    return (SVG.format(rect(0, 0, 640, 480, c) + rect(0, 200, 640, 80, "#ffffffaa"))).encode()


def write_tga(img, path):
    img = img.convert("RGBA")
    w, h = img.size
    hdr = bytes([0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, w & 255, w >> 8, h & 255, h >> 8, 32, 8])  # 8 alpha bits, bottom-left
    px = img.transpose(Image.FLIP_TOP_BOTTOM).tobytes("raw", "BGRA")
    Path(path).write_bytes(hdr + px)


def main():
    try:
        icons = fetch_icons()
    except Exception as e:
        print("flag-icons download failed:", e)
        icons = {}
    tags = re.findall(r'^([A-Z0-9]{3}) = ', (ROOT / "common/country_tags/totu_countries.txt").read_text(encoding="utf-8-sig"), re.M)
    src = {"sourced": 0, "historical": 0, "fallback": 0}
    fb = []
    for tag in tags:
        if tag in HISTORICAL:
            svg = SVG.format(HISTORICAL[tag]).encode()
            src["historical"] += 1
        elif ISO.get(tag) in icons:
            svg = icons[ISO[tag]]
            src["sourced"] += 1
        else:
            svg = fallback_svg(tag)
            src["fallback"] += 1
            fb.append(tag)
        for sub, (w, h) in SIZES.items():
            d = ROOT / "gfx" / "flags" / sub
            d.mkdir(parents=True, exist_ok=True)
            big = cairosvg.svg2png(bytestring=svg, output_width=w * 4, output_height=h * 4)
            im = Image.open(io.BytesIO(big)).convert("RGBA").resize((w, h), Image.LANCZOS)
            write_tga(im, d / f"{tag}.tga")
    # validate
    for sub, (w, h) in SIZES.items():
        files = list((ROOT / "gfx" / "flags" / sub).glob("*.tga"))
        assert len(files) == len(tags), (sub, len(files), len(tags))
        for f in files:
            b = f.read_bytes()[:18]
            assert b[2] == 2 and b[16] == 32 and b[12] | b[13] << 8 == w and b[14] | b[15] << 8 == h, f
    print(len(tags), "tags;", src, "fallback tags:", fb)


if __name__ == "__main__":
    main()
