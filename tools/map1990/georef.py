"""lon/lat -> pixel of the vanilla HOI4 map (x, row from the top).

A parametric Miller cylindrical fit (the Americas are drawn 221 px further north) plus a thin-plate-spline residual
fitted on the vanilla victory point markers matched to GeoNames (tools/data/georef_gcp.json): median error 3-5 px
world-wide, about 1 px in Germany and Korea.
"""
import json

import numpy as np
from scipy.interpolate import RBFInterpolator

from .common import DATA

X0, SX = 2803.0, 15.608         # x = X0 + SX * lon
ROW0, SY = 1398.5, 15.895       # row = ROW0 - SY * miller(lat)
AMERICAS_DROW = -221.0          # the Americas are drawn 221 px further north (lon < -30)
GCP = DATA / "georef_gcp.json"


def miller_px(lon, lat):
    lon, lat = np.asarray(lon, float), np.asarray(lat, float)
    m = np.degrees(1.25 * np.log(np.tan(np.pi / 4 + 0.4 * np.radians(lat))))
    return X0 + SX * lon, ROW0 - SY * m + np.where(lon < -30, AMERICAS_DROW, 0.0)


class Georef:
    def __init__(self, gcp=GCP, smoothing=200.0):
        pts = np.array([p[:4] for p in json.loads(gcp.read_text(encoding="utf-8"))["points"]], float)
        bx, br = miller_px(pts[:, 0], pts[:, 1])
        self._res = RBFInterpolator(pts[:, :2], pts[:, 2:4] - np.stack([bx, br], 1),
                                    kernel="thin_plate_spline", smoothing=smoothing)

    def to_px(self, lon, lat):
        lon, lat = np.atleast_1d(np.asarray(lon, float)), np.atleast_1d(np.asarray(lat, float))
        x, row = miller_px(lon, lat)
        r = self._res(np.stack([lon, lat], 1))
        return x + r[:, 0], row + r[:, 1]
