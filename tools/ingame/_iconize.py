"""Clean broadcast icons from vanilla button art.

The first in-game pass drew toolbar and map-mode pictograms as 2 px pixel silhouettes, which read as blobs. This
helper keeps the vanilla icon's full drawing instead: it cuts the emblem (gold, green or white ink) out of its metal
plate, turns it into paper white P with the vanilla light and shade kept as a soft tone range, adds a 1 px K drop and
puts it on a flat background (transparent, keyer or slate). Used by tools/ingame/topbar.py.
"""
import numpy as np
from PIL import Image, ImageFilter

P = np.array([246, 242, 234], np.float32)
KEY_BLUE = (30, 62, 168)
KEY_BLUE_DOWN = (17, 38, 108)
SLATE = (40, 47, 62)


def _smooth(x, a, b):
    t = np.clip((x - a) / max(b - a, 1e-6), 0, 1)
    return t * t * (3 - 2 * t)


def ink_mask(frame, inset=3, round_plate=False, lum_lo=70, lum_hi=130, chroma_lo=18, chroma_hi=45):
    """Alpha (0..1) of the emblem in one vanilla frame: bright or coloured ink on a dark grey metal plate.
    inset: plate rim width that is never ink (bevels); round_plate: also drop everything outside an inscribed circle."""
    a = np.asarray(frame.convert("RGBA"), np.float32)
    rgb, al = a[..., :3], a[..., 3] / 255.0
    lum = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
    chroma = rgb.max(-1) - rgb.min(-1)
    m = np.maximum(_smooth(lum, lum_lo, lum_hi), _smooth(chroma, chroma_lo, chroma_hi) * _smooth(lum, 40, 80))
    m *= al
    h, w = m.shape
    yy, xx = np.mgrid[0:h, 0:w]
    edge = np.minimum.reduce([xx, yy, w - 1 - xx, h - 1 - yy]).astype(np.float32)
    m *= _smooth(edge, inset - 1, inset + 1)
    if round_plate:
        r = (np.hypot(xx - (w - 1) / 2, yy - (h - 1) / 2))
        m *= 1 - _smooth(r, min(w, h) / 2 - inset - 2, min(w, h) / 2 - inset)
    # drop isolated specks (scratches on the metal)
    img = Image.fromarray((m * 255).astype(np.uint8), "L").filter(ImageFilter.MedianFilter(3))
    return np.asarray(img, np.float32) / 255.0, lum


def emblem(frame, colour=P, shade=0.30, k=True, **mask_opts):
    """RGBA emblem layer of one frame: paper white with the vanilla relief as +-shade tone, plus a 1 px K drop."""
    m, lum = ink_mask(frame, **mask_opts)
    if m.max() <= 0:
        return Image.new("RGBA", frame.size, (0, 0, 0, 0))
    sel = lum[m > 0.5] if (m > 0.5).any() else lum[m > 0]
    lo, hi = np.percentile(sel, 5), np.percentile(sel, 95)
    t = np.clip((lum - lo) / max(hi - lo, 1), 0, 1)
    tone = (1 - shade) + shade * t
    rgb = np.clip(np.asarray(colour, np.float32)[None, None, :] * tone[..., None], 0, 255)
    layer = np.dstack([rgb, m * 255]).astype(np.uint8)
    out = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    if k:
        drop = np.zeros_like(layer)
        drop[..., 3] = (m * 255 * 0.85).astype(np.uint8)
        d = Image.fromarray(drop, "RGBA")
        out.alpha_composite(d, (1, 1))
    out.alpha_composite(Image.fromarray(layer, "RGBA"))
    return out


def plate_bg(size, rgb, alpha=1.0, inset=(0, 0, 0, 0)):
    """Flat background rectangle (l, t, r, b insets) on a transparent frame."""
    w, h = size
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    l, t, r, b = inset
    img.paste(Image.new("RGBA", (w - l - r, h - t - b), (*rgb, round(255 * alpha))), (l, t))
    return img


def button(frame_src, size=None, bg=None, bg_alpha=1.0, inset=(0, 0, 0, 0), **emblem_opts):
    """One output frame: background (None = transparent) + the emblem of frame_src, same size."""
    size = size or frame_src.size
    out = Image.new("RGBA", size, (0, 0, 0, 0)) if bg is None else plate_bg(size, bg, bg_alpha, inset)
    out.alpha_composite(emblem(frame_src, **emblem_opts))
    return out


def split(img, n):
    fw = img.width // n
    return [img.crop((i * fw, 0, (i + 1) * fw, img.height)) for i in range(n)]


def join(frames):
    out = Image.new("RGBA", (sum(f.width for f in frames), frames[0].height), (0, 0, 0, 0))
    x = 0
    for f in frames:
        out.paste(f, (x, 0))
        x += f.width
    return out
