"""Shared drawing helpers of the 'trees' and 'views' area modules (broadcast style). Not an area module."""
import os
from pathlib import Path

import numpy as np
from PIL import Image

from . import generic as g

GAME = Path(os.environ.get("HOI4_DIR") or r"D:\steam\steamapps\common\Hearts of Iron IV")
GI = GAME / "gfx" / "interface"

KEY_LIGHT = tuple(round(k * 0.55 + p * 0.45) for k, p in zip(g.KEY_BLUE, g.P))     # pulse peak of keyer


def vanilla_glob(pattern):
    """Paths (relative to gfx/interface, forward slashes) of vanilla files matching a glob."""
    return sorted(p.relative_to(GI).as_posix() for p in GI.glob(pattern) if p.is_file())


def arr(img):
    return np.asarray(img.convert("RGBA")).astype(np.float32)


def img_of(a):
    return Image.fromarray(np.clip(np.round(a), 0, 255).astype(np.uint8), "RGBA")


def rgba(rgb, alpha):
    return tuple(rgb) + (round(255 * alpha),)


def mix(a, b, t):
    return tuple(round(x * (1 - t) + y * t) for x, y in zip(a, b))


def erode(mask, r):
    """Square erosion with edge-replicate padding (lines keep running across tile edges)."""
    if r <= 0:
        return mask.copy()
    p = np.pad(mask, r, mode="edge")
    h, w = mask.shape
    out = np.ones_like(mask)
    for dy in range(2 * r + 1):
        for dx in range(2 * r + 1):
            out &= p[dy:dy + h, dx:dx + w]
    return out


def body_rect(a, frac=0.9, thr=128):
    """(x0, y0, x1, y1) of the widest rows of the alpha silhouette (the plate body without wings / ribbons)."""
    m = a[..., 3] > thr
    widths = m.sum(1)
    if widths.max() == 0:
        return None
    rows = np.nonzero(widths >= frac * widths.max())[0]
    runs = np.split(rows, np.nonzero(np.diff(rows) > 1)[0] + 1)
    run = max(runs, key=len)
    y0, y1 = int(run[0]), int(run[-1]) + 1
    cols = np.nonzero(m[y0:y1].any(0))[0]
    return int(cols[0]), y0, int(cols[-1]) + 1, y1


def alpha_bbox(a, thr=128):
    m = a[..., 3] > thr
    if not m.any():
        return None
    ys, xs = np.nonzero(m)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def fill_rect(img, box, rgb, alpha=1.0):
    x0, y0, x1, y1 = box
    if x1 > x0 and y1 > y0:
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        layer.paste(rgba(rgb, alpha), (x0, y0, x1, y1))
        img.alpha_composite(layer)
    return img


def put_rect(img, box, rgb, alpha=1.0):
    """Replace (not composite) the pixels of box."""
    x0, y0, x1, y1 = box
    if x1 > x0 and y1 > y0:
        img.paste(rgba(rgb, alpha), (x0, y0, x1, y1))
    return img


def tail_plate(img, box, rgb, alpha=1.0, tail=None):
    """A caption plate with the stepped tail, placed in box (replaces those pixels)."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    if tail is None:
        tail = 12 if h >= 30 else 6
    p = g.plate(w, h, rgb=rgb, alpha=alpha, tail=tail)
    img.paste((0, 0, 0, 0), box)
    img.alpha_composite(p, (x0, y0))
    return img


def board_over_silhouette(src, rgb=g.BOARD, alpha=g.BOARD_ALPHA, thr=128):
    """Flat board covering the alpha bounding box of the vanilla (frames, rims, art, shadows dropped)."""
    a = arr(src)
    out = Image.new("RGBA", src.size, (0, 0, 0, 0))
    bb = alpha_bbox(a, thr)
    if bb:
        put_rect(out, bb, rgb, alpha)
    return out


# ---------------------------------------------------------------------------------------------------------------
# connector lines (focus links, tech lines): the coloured core of the vanilla pipe thinned to a 2 px line
# ---------------------------------------------------------------------------------------------------------------
def _coloured(a, sat=6):
    rgb = a[..., :3]
    return (a[..., 3] > 150) & ((rgb.max(-1) - rgb.min(-1)) >= sat)


def _state_colour(mean_rgb, mean_luma):
    r, gg, b = mean_rgb
    if gg > r + 15 and gg > b:
        return g.KEY_BLUE, 1.0                      # completed / researched
    if r > gg + 40 and r > b + 40:
        return g.SEM_R, 0.85                        # exclusive (red)
    if r > b + 40:
        return g.D, 0.80                            # available (tan)
    if b > r + 20:
        return g.D, 0.50                            # focus link, not completed (blue-grey)
    return (g.D, 0.40) if mean_luma > 90 else (g.D, 0.22)


def lines(src, frames, r, anim=False, sat=6):
    """Thin every frame's coloured pipe core to a line of the state colour. Grey frames (no colour) borrow the
    geometry of the texture's coloured frames. anim: keyer line whose brightness follows the vanilla chevrons."""
    a = arr(src)
    fw = a.shape[1] // frames
    fr = [a[:, i * fw:(i + 1) * fw] for i in range(frames)]
    fills = [_coloured(f, sat) for f in fr]
    big = max(int(f.sum()) for f in fills)
    union = np.zeros_like(fills[0])
    for f in fills:
        if f.sum() >= 0.5 * big:
            union |= f
    out = np.zeros_like(a)
    for i, f in enumerate(fr):
        fill = fills[i] if fills[i].sum() >= 0.3 * max(big, 1) else (union & (f[..., 3] > 150))
        if fill.sum() == 0:
            fill = union
        core = erode(fill, r)
        if core.sum() == 0:
            core = fill
        o = out[:, i * fw:(i + 1) * fw]
        if anim:
            lum = f[..., :3].mean(-1)
            # chevron brightness sampled across the pipe so the 2 px line carries the moving pattern
            t = np.clip((lum - 30) / 80.0, 0, 1)
            col = np.array(g.KEY_BLUE, np.float32)[None, None] * (1 - t[..., None]) + \
                np.array(KEY_LIGHT, np.float32)[None, None] * t[..., None]
            o[..., :3] = np.where(core[..., None], col, 0)
            o[..., 3] = np.where(core, 255, 0)
        else:
            sel = f[fill][:, :3] if fill.any() else f[..., :3].reshape(-1, 3)
            mean = sel.mean(0) if fills[i].sum() >= 0.3 * max(big, 1) else f[union][:, :3].mean(0)
            rgb, al = _state_colour(mean, mean.mean())
            o[..., :3] = np.where(core[..., None], np.array(rgb, np.float32), 0)
            o[..., 3] = np.where(core, 255 * al, 0)
    return img_of(out)


def hairline_rect(img, box, rgb=g.D, alpha=g.HAIRLINE_ALPHA):
    """Composite a D hairline (22 %) over box."""
    return fill_rect(img, box, rgb, alpha)
