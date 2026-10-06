"""Builds gfx/flags/{,medium/,small/}TAG.tga (82x52, 41x26, 10x7; 32-bit uncompressed, bottom-left origin).

Every flag is a real downloaded image (no hand-drawn flags). Sources:
  * tools/flag_sources.json: tag -> URL of a real 1990-era historical SVG (downloaded from GitHub raw mirrors of
    Wikimedia Commons files, since Wikimedia itself is blocked in the build sandbox), cached in tools/cache/flags_src/.
  * otherwise the modern flag from the npm package `flag-icons` (MIT), cached under tools/cache/.
  * if neither exists, a plain fallback flag in the map colour.
Needs: pip install cairosvg pillow.  Usage: python tools/build_flags.py
"""
import io
import json
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
SRC = ROOT / "tools" / "cache" / "flags_src"
MANIFEST = json.loads((ROOT / "tools" / "flag_sources.json").read_text(encoding="utf-8"))["flags"]


def historical_svg(tag):
    f = SRC / f"{tag}.svg"
    if not f.exists():
        SRC.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(MANIFEST[tag]["url"], f)
    return f.read_bytes()


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
    r = lambda y, h, col: f'<rect x="0" y="{y}" width="640" height="{h}" fill="{col}"/>'
    return SVG.format(r(0, 480, c) + r(200, 80, "#ffffffaa")).encode()


def render(svg, w, h):
    """High-res raster at the SVG's native aspect, trim the antialiased rim, Lanczos-resize (premultiplied) to w x h,
    force full opacity so no dark/white edge fringe remains."""
    big = Image.open(io.BytesIO(cairosvg.svg2png(bytestring=svg, output_width=w * 16))).convert("RGBA")
    bw, bh = big.size
    big = big.crop((3, 3, bw - 3, bh - 3)).convert("RGBa").resize((w, h), Image.LANCZOS).convert("RGBA")
    big.putalpha(255)
    return big


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
        if tag in MANIFEST:
            svg = historical_svg(tag)
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
            im = render(svg, w, h)
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
