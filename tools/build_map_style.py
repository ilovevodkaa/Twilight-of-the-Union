"""Map style in the spirit of TNO: black sea, countries filled with their colour on every zoom (a little stronger at the
border), thin crisp border lines, black distance fog. Everything is built from the vanilla game files, nothing is
copied from other mods.

Writes:
  map/terrain/colormap_rgb_cityemissivemask_a.dds, colormap_water_{0,1,2}.dds   dimmed, desaturated land without the
                             city lights mask; dark sea
  gfx/FX/pdxwater.shader     vanilla copy: the sea colour (mostly the sky reflection) is near-black, glints x0.15
  gfx/FX/river.shader        vanilla copy: rivers a steady dark blue (RIVER_ANCHOR)
  gfx/FX/standardfuncsgfx.fxh vanilla copy: no snow / frost / sea ice (SNOW_ANCHOR); the rim of the country fill
                             (EDGE_ANCHOR, light-grey mix 0 = no rim: the border lines draw the borders)
  gfx/FX/constants.fxh       vanilla copy: political fill independent of the camera height, black fog, borders
                             unaffected by the fog of war, no mud, no city lights (CONSTANTS)
  map/terrain/border_{country,state,province}_{0,1,2}.dds   dark hairline profiles (BORDERS), 32-bit with mipmaps
The defines half of the style (gradient thickness, border mesh width) is common/defines/totu_map_style.lua.

Every shader edit is a replacement at an anchor; if a game patch moves an anchor the script stops with its name.

Usage:  python tools/build_map_style.py [--game PATH] [--only colormaps|shaders|borders]
"""
import argparse
import re
import struct
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
GAME_GUESSES = [r"D:\steam\steamapps\common\Hearts of Iron IV",
                r"C:\Program Files (x86)\Steam\steamapps\common\Hearts of Iron IV"]

LAND_GAIN = 0.72        # brightness multiplier for land
LAND_SAT = 0.75         # saturation kept
WATER_GAIN = 0.10       # near-black sea
WATER_SAT = 0.35
WATER_TINT = np.array([0.85, 0.95, 1.15], np.float32)   # a hint of cold blue so the coastline still reads


def grade(rgb, gain, sat, tint=None):
    rgb = rgb.astype(np.float32)
    lum = (rgb @ np.array([0.299, 0.587, 0.114], np.float32))[..., None]
    rgb = lum + (rgb - lum) * sat
    rgb *= gain
    if tint is not None:
        rgb *= tint
    return np.clip(rgb, 0, 255).astype(np.uint8)


def colormaps(game, root):
    src = game / "map/terrain"
    dst = root / "map/terrain"
    dst.mkdir(parents=True, exist_ok=True)

    # land: uncompressed RGBA, alpha = city lights emissive mask: cleared, no glowing cities at night (user request)
    im = np.asarray(Image.open(src / "colormap_rgb_cityemissivemask_a.dds").convert("RGBA")).copy()
    im[..., :3] = grade(im[..., :3], LAND_GAIN, LAND_SAT)
    im[..., 3] = 0
    Image.fromarray(im, "RGBA").save(dst / "colormap_rgb_cityemissivemask_a.dds")

    for i in range(3):
        name = f"colormap_water_{i}.dds"
        w = np.asarray(Image.open(src / name).convert("RGBA")).copy()
        w[..., :3] = grade(w[..., :3], WATER_GAIN, WATER_SAT, WATER_TINT)
        Image.fromarray(w, "RGBA").save(dst / name, pixel_format="DXT5")
    print("colormaps written to", dst)


# ------------------------------------------------------------------ shaders
# Most of the sea's blue comes from the sky cubemap reflection (fresnel >= 0.5), not from the colormap, so the
# water shader is patched: the reflected/refracted colour is replaced by near-black right after it is mixed, before
# borders, ice and selection highlights are drawn on top; the sun / moon glints are scaled down too (user request:
# "a really black sea").
SEA_BRIGHTNESS = 0.0
SEA_BASE = (0.003, 0.004, 0.006)
WATER_ANCHOR = "refractiveColor = refractiveColor * ( 1.0f - fresnel ) + reflectiveColor * fresnel;"
SPECULAR_ANCHOR = "lightingProperties._SpecularColor = vec3(vSpecularIntensity);"
# river.shader: without snow a river takes the dark sea colour and the country fill and disappears; it gets a
# steady dark blue instead (a lighter blue glowed too much, user request).
RIVER_ANCHOR = ("diffuse = ApplyRiverSnow( diffuse.rgb, reflectiveColor, Input.vPrePos_Fade.xyz, normal, vMudSnow, "
                "CityLightsAndSnowNoise, waterSideAlpha.x, vSnowSpecGloss );")
RIVER_BLUE = (0.07, 0.15, 0.30)
RIVER_MIX = 0.8
SEA_SPECULAR = 0.15

# constants.fxh: name -> new value. Political fill: vanilla fills a country fully only when the camera is high
# (GB_CAM_MIN..GB_CAM_MAX = 100..350) and shows just a band at the border when it is low. With MIN 0 / MAX 1 the
# camera always counts as "high", so the fill is the same on every zoom. The interior alpha is
# 1 - (1 - CLAMP - GB_THRESHOLD) / GB_THRESHOLD2 = 0.8 with CLAMP 0.90 (vanilla 0.8 -> 0.4), times the strength.
# GB_THRESHOLD / GB_THRESHOLD2 stay vanilla: the map modes with a fixed camera override (state, resistance,
# terrain...) depend on them.
CONSTANTS = {
    "GB_CAM_MIN": "0.0f",
    "GB_CAM_MAX": "1.0f",
    "GB_CAM_MAX_FILLING_CLAMP": "0.90f",
    "GB_OPACITY_NEAR": "1.0f",
    "GB_OPACITY_FAR": "1.0f",
    "GB_STRENGTH_CH1": "0.9",
    "GB_STRENGTH_CH2": "0.9",
    "FOG_COLOR": "float3( 0.0, 0.0, 0.0 )",
    "BORDER_FOW_REMOVAL_FACTOR": "1.0f",
    # no weather on the map (user request): no mud, no glowing cities (snow, frost and sea ice: SNOW_ANCHOR)
    "MUD_STRENGHTEN": "0.0",
    "CITY_LIGHTS_INTENSITY": "0.0",
    "CITY_LIGHTS_BLOOM_FACTOR": "0.0",
}
CONST_LINE = r"^(\s*static const float3?\s+{name}\s*=\s*)([^;]+);"

# standardfuncsgfx.fxh: the thin edge the gradient fill draws along a border is vanilla's fill colour x0.5 (a dark
# rim). It can be pulled towards EDGE_LIGHT by EDGE_MIX; 0 = no rim at all, the user asked for no white lines on the
# borders (0.55 and 0.22 read as a thick neon outline).
EDGE_ANCHOR = "// Make the outline edge darker\n\t\tvCh = lerp( vCh, vCh * .5, vThick );"
EDGE_LIGHT = (0.80, 0.82, 0.85)
EDGE_MIX = 0.0
# GetSnow() feeds the snow and frost of the terrain, trees, meshes and rivers and the sea ice: always 0.
SNOW_ANCHOR = "return lerp( vMudSnowColor.b, vMudSnowColor.g, vFoWOpacity_FoWTime_SnowMudFade_MaxGameSpeed.z ); //Get winter;"


def patch_constants(text):
    for name, value in CONSTANTS.items():
        pat = re.compile(CONST_LINE.format(name=re.escape(name)), re.M)
        hits = pat.findall(text)
        assert len(hits) == 1, f"constants.fxh: {name} found {len(hits)} times, update CONSTANTS"
        text = pat.sub(lambda m: f"{m.group(1)}{value}; // Twilight of the Union, vanilla {m.group(2).strip()}", text)
    return text


def shaders(game, root):
    out = root / "gfx/FX"
    out.mkdir(parents=True, exist_ok=True)

    text = (game / "gfx/FX/pdxwater.shader").read_text(encoding="utf-8-sig")
    assert text.count(WATER_ANCHOR) == 1, "pdxwater.shader changed, update WATER_ANCHOR"
    assert text.count(SPECULAR_ANCHOR) == 1, "pdxwater.shader changed, update SPECULAR_ANCHOR"
    r, g, b = SEA_BASE
    text = text.replace(WATER_ANCHOR, WATER_ANCHOR + "\n\t\t\t// Twilight of the Union: black sea"
                        f"\n\t\t\trefractiveColor = refractiveColor * {SEA_BRIGHTNESS:.3f}f"
                        f" + float3( {r:.3f}f, {g:.3f}f, {b:.3f}f );")
    text = text.replace(SPECULAR_ANCHOR, SPECULAR_ANCHOR[:-1] + f" * {SEA_SPECULAR:.2f}f; // Twilight of the Union")
    (out / "pdxwater.shader").write_text(text, encoding="utf-8")

    text = (game / "gfx/FX/river.shader").read_text(encoding="utf-8-sig")
    assert text.count(RIVER_ANCHOR) == 1, "river.shader changed, update RIVER_ANCHOR"
    r, g, b = RIVER_BLUE
    text = text.replace(RIVER_ANCHOR, RIVER_ANCHOR + "\n\t\t\t// Twilight of the Union: dark blue rivers"
                        f"\n\t\t\tdiffuse = lerp( diffuse, float3( {r:.2f}f, {g:.2f}f, {b:.2f}f ), "
                        f"{RIVER_MIX:.2f}f * ( 1.0f - waterSideAlpha.x ) );")
    (out / "river.shader").write_text(text, encoding="utf-8")

    text = (game / "gfx/FX/constants.fxh").read_text(encoding="utf-8-sig")
    (out / "constants.fxh").write_text(patch_constants(text), encoding="utf-8")

    text = (game / "gfx/FX/standardfuncsgfx.fxh").read_text(encoding="utf-8-sig")
    assert text.count(EDGE_ANCHOR) == 1, "standardfuncsgfx.fxh changed, update EDGE_ANCHOR"
    assert text.count(SNOW_ANCHOR) == 1, "standardfuncsgfx.fxh changed, update SNOW_ANCHOR"
    text = text.replace(SNOW_ANCHOR, "return 0.0f; // Twilight of the Union: no snow, frost or sea ice on the map")
    r, g, b = EDGE_LIGHT
    edge = ("// Twilight of the Union: a light outline edge (vanilla: vCh * .5, a dark one)\n"
            f"\t\tvCh = lerp( vCh, lerp( vCh, float3( {r:.2f}f, {g:.2f}f, {b:.2f}f ), {EDGE_MIX:.2f}f ), vThick );")
    (out / "standardfuncsgfx.fxh").write_text(text.replace(EDGE_ANCHOR, edge), encoding="utf-8")
    print("patched pdxwater.shader, river.shader, constants.fxh and standardfuncsgfx.fxh in", out)


# ------------------------------------------------------------------ border textures
# The border mesh samples its texture as (along the border, across it): v = 0..1 runs across the line, 0.5 is the
# line's middle. A profile is a list of bands from the middle outwards: (half width as a fraction of the texture
# height, RGB, alpha). Vanilla country borders are a dark navy band over ~45 % of the mesh; these are dark
# hairlines, a little stronger for countries (user: no white lines on the borders) than for states and provinces.
# Sizes per quality level follow the vanilla files (_0 high, _1 medium, _2 low).
BORDERS = {
    "border_country": ((256, 128), [(0.045, (6, 8, 12), 100)]),
    "border_state": ((128, 64), [(0.05, (6, 8, 12), 120)]),
    "border_province": ((64, 32), [(0.04, (6, 8, 12), 60)]),
}
SUPERSAMPLE = 16


def profile_column(height, bands):
    """RGBA for every row of the texture, antialiased: each row averages SUPERSAMPLE samples across its height."""
    col = np.zeros((height, 4), np.float32)
    for row in range(height):
        acc = np.zeros(4, np.float32)
        for s in range(SUPERSAMPLE):
            v = (row + (s + 0.5) / SUPERSAMPLE) / height
            d = abs(v - 0.5)
            for half, rgb, alpha in bands:          # innermost band that contains the sample wins
                if d <= half:
                    acc += np.array([*rgb, alpha], np.float32) * np.array([alpha / 255] * 3 + [1], np.float32)
                    break
        a = acc[3] / SUPERSAMPLE
        rgb = acc[:3] / max(acc[3] / 255, 1e-6) if acc[3] else np.zeros(3)   # un-premultiply
        col[row] = [*rgb, a]
    return col


def dds_mips(img):
    """Mip chain down to 1x1 (box filter on premultiplied alpha, as the GPU blends it)."""
    level = np.asarray(img, np.float32)
    mips = [level]
    while level.shape[0] > 1 or level.shape[1] > 1:
        h, w = max(level.shape[0] // 2, 1), max(level.shape[1] // 2, 1)
        pre = level.copy()
        pre[..., :3] *= pre[..., 3:4] / 255
        pre = pre[:h * 2 if level.shape[0] > 1 else 1, :w * 2 if level.shape[1] > 1 else 1]
        fy, fx = pre.shape[0] // h, pre.shape[1] // w
        pre = pre.reshape(h, fy, w, fx, 4).mean(axis=(1, 3))
        out = pre.copy()
        out[..., :3] = np.where(pre[..., 3:4] > 0, pre[..., :3] * 255 / np.maximum(pre[..., 3:4], 1e-6), 0)
        level = out
        mips.append(level)
    return mips


def write_dds_rgba(path, img):
    """Uncompressed A8R8G8B8 DDS with a full mip chain (the layout of vanilla border_country_0.dds)."""
    mips = dds_mips(img)
    h, w = mips[0].shape[:2]
    DDSD = 0x1 | 0x2 | 0x4 | 0x1000 | 0x8 | 0x20000          # caps, height, width, pixelformat, pitch, mipmapcount
    header = struct.pack("<4sIIIIIII", b"DDS ", 124, DDSD, h, w, w * 4, 0, len(mips))
    header += b"\0" * 44
    header += struct.pack("<II4sIIIII", 32, 0x41, b"\0\0\0\0", 32, 0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000)
    header += struct.pack("<IIIII", 0x1000 | 0x400000 | 0x8, 0, 0, 0, 0)  # texture, mipmap, complex
    body = b""
    for m in mips:
        px = np.clip(np.round(m), 0, 255).astype(np.uint8)
        body += px[..., [2, 1, 0, 3]].tobytes()                # BGRA in memory
    path.write_bytes(header + body)


def borders(root):
    dst = root / "map/terrain"
    dst.mkdir(parents=True, exist_ok=True)
    for name, ((w, h), bands) in BORDERS.items():
        for q in range(3):
            qw, qh = w >> q, h >> q
            col = profile_column(qh, bands)
            img = np.repeat(col[:, None, :], qw, axis=1)
            write_dds_rgba(dst / f"{name}_{q}.dds", img)
    print("border textures written to", dst)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=next((g for g in GAME_GUESSES if Path(g).exists()), None))
    ap.add_argument("--only", choices=["colormaps", "shaders", "borders"])
    args = ap.parse_args()
    game = Path(args.game)
    if args.only in (None, "colormaps"):
        colormaps(game, ROOT)
    if args.only in (None, "shaders"):
        shaders(game, ROOT)
    if args.only in (None, "borders"):
        borders(ROOT)


if __name__ == "__main__":
    main()
