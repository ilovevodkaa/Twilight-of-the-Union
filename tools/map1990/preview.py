"""Before/after picture of a rebuilt window: provinces (thin dark), states (thick light), victory points (dots)."""
import numpy as np
from PIL import Image, ImageDraw


def borders(ids):
    e = np.zeros(ids.shape, bool)
    e[:, 1:] |= ids[:, 1:] != ids[:, :-1]
    e[1:, :] |= ids[1:, :] != ids[:-1, :]
    return e


def render(before, after, state_of_before, state_of_after, land, vps, box, out, scale=3):
    x0, y0, x1, y1 = box
    ln = land[y0:y1, x0:x1]
    tiles = []
    for ids, st in ((before, state_of_before), (after, state_of_after)):
        sl = ids[y0:y1, x0:x1]
        img = np.where(ln[..., None], np.array([82, 88, 98]), np.array([12, 14, 22])).astype(np.uint8)
        img[borders(sl) & ln] = (40, 44, 52)
        lut = {int(p): st.get(int(p), 0) for p in np.unique(sl)}
        sv = np.vectorize(lut.get)(sl)
        img[borders(sv) & ln] = (235, 235, 235)
        tiles.append(Image.fromarray(img).resize(((x1 - x0) * scale, (y1 - y0) * scale), Image.NEAREST))
    d = ImageDraw.Draw(tiles[1])
    for r, c in vps:
        if y0 <= r < y1 and x0 <= c < x1:
            cx, cy = (c - x0) * scale + scale // 2, (r - y0) * scale + scale // 2
            d.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=(255, 196, 60))
    sheet = Image.new("RGB", (tiles[0].width * 2 + 10, tiles[0].height), (0, 0, 0))
    sheet.paste(tiles[0], (0, 0))
    sheet.paste(tiles[1], (tiles[0].width + 10, 0))
    sheet.save(out)
