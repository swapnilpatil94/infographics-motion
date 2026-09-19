"""SVG -> RGBA raster via resvg (correct fill-rule/stroke/clip/text handling,
unlike Blender's SVG curve importer), with an on-disk cache keyed by content
hash so iterating on shots doesn't re-rasterize unchanged art.
"""
import hashlib
import io
import os

import numpy as np
import resvg_py
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE = os.path.join(ROOT, "output", "cache", "raster")


def rasterize(svg_text, zoom=1.0, crop=True):
    """Returns (rgba uint8 HxWx4 straight alpha, (ox, oy) px offset of the
    cropped image inside the full canvas). Offset is what keeps separately
    rasterized pieces of one drawing (body / head) aligned after cropping."""
    key = hashlib.sha256((svg_text + f"|{zoom}|{crop}").encode("utf-8")).hexdigest()[:24]
    os.makedirs(CACHE, exist_ok=True)
    png_path = os.path.join(CACHE, key + ".png")
    meta_path = os.path.join(CACHE, key + ".off")
    if os.path.exists(png_path) and os.path.exists(meta_path):
        arr = np.asarray(Image.open(png_path).convert("RGBA")).copy()
        ox, oy = map(int, open(meta_path).read().split(","))
        return arr, (ox, oy)

    data = bytes(resvg_py.svg_to_bytes(svg_string=svg_text, zoom=zoom))
    arr = np.asarray(Image.open(io.BytesIO(data)).convert("RGBA")).copy()
    ox = oy = 0
    if crop:
        ys, xs = np.where(arr[:, :, 3] > 2)
        if len(xs) == 0:
            arr = np.zeros((2, 2, 4), np.uint8)
        else:
            x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
            arr = arr[y0:y1, x0:x1].copy()
            ox, oy = int(x0), int(y0)
    Image.fromarray(arr).save(png_path)
    with open(meta_path, "w") as f:
        f.write(f"{ox},{oy}")
    return arr, (ox, oy)


def rasterize_file(path, zoom=1.0, crop=True):
    with open(path, encoding="utf-8") as f:
        return rasterize(f.read(), zoom, crop)
