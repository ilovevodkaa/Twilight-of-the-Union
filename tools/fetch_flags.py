"""Downloads 1990 flags from Wikimedia Commons (public domain national flags) into tools/src/flags/<TAG>.png.

Only needed once; the PNGs are committed. tools/world1990/flags.py converts them to the game's TGA sizes.
Usage:  python tools/fetch_flags.py [TAG ...]
"""
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent / "src/flags"
UA = "TwilightOfTheUnionModBuilder/1.0 (Hearts of Iron IV mod; flag thumbnails)"

# tag -> candidate Commons file names (first that exists wins); flags as flown on 1 January 1990
FILES = {
    "EGY": ["Flag of Egypt.svg"],
    "IRQ": ["Flag of Iraq (1963–1991).svg", "Flag of Iraq (1963-1991).svg"],
    "SYR": ["Flag of the United Arab Republic.svg"],
    "YEM": ["Flag of North Yemen.svg"],
    "FSA": ["Flag of South Yemen.svg"],
    "SUD": ["Flag of Sudan.svg"],
    "KUW": ["Flag of Kuwait.svg"],
    "LBA": ["Flag of Libya (1977–2011).svg", "Flag of Libya (1977-2011).svg"],
    "OMA": ["Flag of Oman.svg"],
    "QAT": ["Flag of Qatar.svg"],
    "PER": ["Flag of Iran.svg"],
    "ROM": ["Flag of Romania.svg"],
    "SPR": ["Flag of Spain.svg"],
    "SAF": ["Flag of South Africa (1928–1994).svg", "Flag of South Africa (1928-1994).svg"],
    "SOM": ["Flag of Somalia.svg"],
    "COG": ["Flag of Zaire.svg"],
    "VOL": ["Flag of Burkina Faso.svg"],
    "DAH": ["Flag of the People's Republic of Benin.svg", "Flag of Benin.svg"],
    "GYA": ["Flag of Guyana.svg"],
    "UGA": ["Flag of Uganda.svg"],
    "BAN": ["Flag of Bangladesh.svg"],
    "BRM": ["Flag of Myanmar (1974–2010).svg", "Flag of Burma (1974–2010).svg"],
    "CBV": ["Flag of Cape Verde (1975–1992).svg", "Flag of Cape Verde (1975-1992).svg"],
    "FIJ": ["Flag of Fiji.svg"],
    "MLD": ["Flag of Maldives.svg"],
    "NIC": ["Flag of Nicaragua.svg"],
    "HAI": ["Flag of Haiti.svg"],
    "GRE": ["Flag of Greece.svg"],
    "CHL": ["Flag of Chile.svg"],
    "BAS": ["Flag of Antigua and Barbuda.svg"],
    "MRI": ["Flag of Mauritius.svg"],
    "SEY": ["Flag of Seychelles (1977–1996).svg", "Flag of Seychelles (1977-1996).svg"],
    "COM": ["Flag of the Comoros (1978–1992).svg", "Flag of the Comoros (1978-1992).svg", "Flag of the Comoros.svg"],
    "STP": ["Flag of São Tomé and Príncipe.svg", "Flag of Sao Tome and Principe.svg"],
    "KIR": ["Flag of Kiribati.svg"],
    "TUV": ["Flag of Tuvalu.svg"],
    "NRU": ["Flag of Nauru.svg"],
    "BRB": ["Flag of Barbados.svg"],
}


def fetch(name):
    url = "https://commons.wikimedia.org/wiki/Special:FilePath/" + urllib.parse.quote(name) + "?width=328"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
        if not data.startswith(b"\x89PNG"):
            raise ValueError("not a PNG")
        return data


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tags = sys.argv[1:] or list(FILES)
    for tag in tags:
        for name in FILES[tag]:
            try:
                data = fetch(name)
            except Exception as e:  # noqa: BLE001
                print(f"{tag}: {name} -> {e}")
                continue
            (OUT / f"{tag}.png").write_bytes(data)
            print(f"{tag}: {name} ({len(data)} bytes)")
            break
        time.sleep(0.5)


if __name__ == "__main__":
    main()
