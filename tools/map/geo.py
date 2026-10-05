"""Map grid + projection. Plate carree (equirectangular) crop 77N..56S, full 360 degrees.

x = (lon + 180) / 360 * W          y = (LAT_TOP - lat) / (LAT_TOP - LAT_BOT) * H
Horizontal 15.64 px/deg, vertical 15.40 px/deg (1.5 % anisotropy, invisible in play).
"""
import numpy as np

W, H = 5632, 2048
LAT_TOP, LAT_BOT = 77.0, -56.0


def lonlat_to_px(lon, lat):
    return (np.asarray(lon) + 180.0) / 360.0 * W, (LAT_TOP - np.asarray(lat)) / (LAT_TOP - LAT_BOT) * H


def px_to_lonlat(x, y):
    return np.asarray(x) / W * 360.0 - 180.0, LAT_TOP - np.asarray(y) / H * (LAT_TOP - LAT_BOT)


def row_lat():
    return LAT_TOP - (np.arange(H) + 0.5) * (LAT_TOP - LAT_BOT) / H


def rings_px(geom):
    """Yield (exterior_pts, [hole_pts]) in sub-pixel int coords (x16) for a (Multi)Polygon geometry."""
    if geom is None:
        return
    t = geom["type"]
    polys = geom["coordinates"] if t == "MultiPolygon" else [geom["coordinates"]] if t == "Polygon" else []
    for poly in polys:
        conv = []
        for ring in poly:
            a = np.asarray(ring, dtype=np.float64)[:, :2]
            x, y = lonlat_to_px(a[:, 0], a[:, 1])
            conv.append(np.round(np.stack([x, y], 1) * 16).astype(np.int32))
        yield conv[0], conv[1:]


def fill_geom(img, geom, value, holes=True):
    import cv2
    for ext, hs in rings_px(geom):
        cv2.fillPoly(img, [ext], value, shift=4)
        if holes:
            for h in hs:
                cv2.fillPoly(img, [h], 0, shift=4)


def geom_area_px(geom):
    img = np.zeros((1, 1), np.uint8)
    tot = 0.0
    for ext, hs in rings_px(geom):
        for r, sgn in [(ext, 1)] + [(h, -1) for h in hs]:
            x, y = r[:, 0] / 16.0, r[:, 1] / 16.0
            tot += sgn * abs(0.5 * np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))
    return tot
