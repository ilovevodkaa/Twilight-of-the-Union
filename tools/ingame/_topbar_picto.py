"""Private helpers of the topbar area: pixel pictograms derived from vanilla icon silhouettes, cell grids, rings.

Not an area module (leading underscore). Everything returns PIL RGBA images or numpy masks; ASCII only.
"""
import math

import numpy as np
from PIL import Image

from ingame import generic as g


def _arr(img):
    return np.asarray(img.convert("RGBA"), dtype=np.float32) / 255.0


def icon_mask(img, kind="gold", lum_min=0.25, warm_min=0.10):
    """Float mask (h, w) of the icon pixels of a vanilla frame.

    gold   bright warm metal (toolbar icons, overview buttons): r - b above warm_min and luma above lum_min
    light  anything clearly lighter than its surroundings (glyphs on dark discs)
    sat    any saturated colour (coloured icons on grey)
    alpha  the alpha channel
    """
    a = _arr(img)
    r, gch, b, al = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    lum = 0.299 * r + 0.587 * gch + 0.114 * b
    if kind == "gold":
        m = ((r - b) > warm_min) & (lum > lum_min)
    elif kind == "light":
        m = lum > lum_min
    elif kind == "sat":
        mx = np.maximum(np.maximum(r, gch), b)
        mn = np.minimum(np.minimum(r, gch), b)
        m = ((mx - mn) > warm_min) & (mx > lum_min)
    else:
        m = al > 0.5
    return (m & (al > 0.5)).astype(np.float32)


def cells_from_mask(mask, cell=2, fill=0.5, clean=True):
    """Downsample a pixel mask to a boolean cell grid (cell x cell px per cell, aligned to the pixel origin)."""
    h, w = mask.shape
    gh, gw = h // cell, w // cell
    m = mask[:gh * cell, :gw * cell].reshape(gh, cell, gw, cell).mean(axis=(1, 3)) >= fill
    if clean:
        p = np.pad(m, 1)
        nb = p[:-2, 1:-1].astype(int) + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:]
        m = m & (nb > 0)
    return m


def grid_from_rows(rows):
    return np.array([[ch == "#" for ch in r.ljust(max(len(x) for x in rows), ".")] for r in rows], dtype=bool)


def render_cells(grid, size, origin=(0, 0), cell=2, rgb=g.P, alpha=1.0, drop=True, drop_off=2):
    """Draw a boolean cell grid onto a transparent size image: K copy at +drop_off first, then rgb cells."""
    w, h = size
    out = np.zeros((h, w, 4), dtype=np.uint8)
    ys, xs = np.nonzero(grid)
    ox, oy = origin
    if drop:
        for y, x in zip(ys, xs):
            x0, y0 = ox + x * cell + drop_off, oy + y * cell + drop_off
            out[max(0, y0):max(0, min(h, y0 + cell)), max(0, x0):max(0, min(w, x0 + cell))] = (0, 0, 0, 255)
    col = tuple(rgb) + (round(255 * alpha),)
    for y, x in zip(ys, xs):
        x0, y0 = ox + x * cell, oy + y * cell
        out[max(0, y0):max(0, min(h, y0 + cell)), max(0, x0):max(0, min(w, x0 + cell))] = col
    return Image.fromarray(out, "RGBA")


def grid_bbox(grid):
    ys, xs = np.nonzero(grid)
    if len(xs) == 0:
        return 0, 0, 0, 0
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


def centred_cells(grid, size, cell=2, dx=0, dy=0, **kw):
    """Render the grid's ink centred in size (the K drop is not counted, so the ink itself is centred)."""
    x0, y0, x1, y1 = grid_bbox(grid)
    sub = grid[y0:y1, x0:x1]
    w, h = size
    ox = (w - sub.shape[1] * cell) // 2 + dx
    oy = (h - sub.shape[0] * cell) // 2 + dy
    return render_cells(sub, size, (ox, oy), cell, **kw)


def derived_picto(frame, size=None, kind="gold", cell=2, fill=0.5, recentre=True, crop=None, **kw):
    """Pictogram cell grid from a vanilla frame; returns the rendered P + K image of the frame size.

    crop  (x0, y0, x1, y1) in the frame: only this part is analysed (e.g. to drop a disc rim)."""
    m = icon_mask(frame, kind, **{k: v for k, v in kw.items() if k in ("lum_min", "warm_min")})
    if crop:
        x0, y0, x1, y1 = crop
        keep = np.zeros_like(m)
        keep[y0:y1, x0:x1] = 1
        m = m * keep
    grid = cells_from_mask(m, cell, fill)
    size = size or frame.size
    rk = {k: v for k, v in kw.items() if k in ("rgb", "alpha", "drop")}
    if recentre:
        return centred_cells(grid, size, cell, **rk), grid
    return render_cells(grid, size, (0, 0), cell, **rk), grid


def ring_cells(n_cells, r_in, r_out, ticks=10, lit=0, tick_frac=0.42, start_deg=-90.0):
    """Dial as cell grids: (lit_grid, unlit_grid, ring_grid) on an n x n cell canvas; ticks clockwise from 12 o'clock.

    Each tick is the cells whose centre lies in [r_in, r_out] and within tick_frac of the tick's angular pitch."""
    c = (n_cells - 1) / 2.0
    lit_g = np.zeros((n_cells, n_cells), bool)
    unlit_g = np.zeros_like(lit_g)
    ring_g = np.zeros_like(lit_g)
    pitch = 360.0 / ticks
    for y in range(n_cells):
        for x in range(n_cells):
            dx, dy = x - c, y - c
            r = math.hypot(dx, dy)
            ang = (math.degrees(math.atan2(dy, dx)) - start_deg) % 360.0
            k = int((ang + pitch / 2) // pitch) % ticks
            off = abs(((ang - k * pitch + 180) % 360) - 180)
            if r_in <= r <= r_out and off <= pitch * tick_frac / 2:
                (lit_g if k < lit else unlit_g)[y, x] = True
    return lit_g, unlit_g, ring_g


def disc(size, r, rgb, alpha=1.0, cx=None, cy=None, ss=4):
    """Antialiased filled disc (supersampled)."""
    w, h = size
    cx = (w - 1) / 2 if cx is None else cx
    cy = (h - 1) / 2 if cy is None else cy
    yy, xx = np.mgrid[0:h * ss, 0:w * ss]
    d = np.hypot((xx + 0.5) / ss - 0.5 - cx, (yy + 0.5) / ss - 0.5 - cy)
    m = (d <= r).astype(np.float32).reshape(h, ss, w, ss).mean(axis=(1, 3))
    out = np.zeros((h, w, 4), np.uint8)
    out[..., :3] = rgb
    out[..., 3] = np.round(m * 255 * alpha).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def tick_ring(size, centre, r_in, r_out, half_w, ticks=10, start_deg=-90.0, cell=2):
    """Per-tick boolean cell grids of a dial: tick k is the cells whose centre lies on the radial bar at angle
    start + k * 360 / ticks (clockwise on screen), between r_in and r_out px, within half_w px of its axis."""
    w, h = size
    gw, gh = w // cell, h // cell
    cx, cy = centre
    out = []
    for k in range(ticks):
        th = math.radians(start_deg + k * 360.0 / ticks)
        ux, uy = math.cos(th), math.sin(th)
        grid = np.zeros((gh, gw), bool)
        for y in range(gh):
            for x in range(gw):
                vx, vy = x * cell + cell / 2 - cx, y * cell + cell / 2 - cy
                along = vx * ux + vy * uy
                across = abs(vx * uy - vy * ux)
                grid[y, x] = r_in <= along <= r_out and across <= half_w
        out.append(grid)
    return out
