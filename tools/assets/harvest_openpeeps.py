"""Harvest real Open Peeps (CC0) hand / shoe drawings out of the whole-body atoms.

The atoms are mono line art (ink only). A crop box is rasterised, the cut edges are sealed, the outside is flood-filled from the border and everything ENCLOSED becomes skin (or
shoe) fill; ink that does not touch the enclosed region (stray phone / sleeve strokes) is discarded. The result is an RGBA replacement drawing in exactly the ink language of the heads.
"""
import os
import sys

import cv2
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from engine.shorts.raster import rasterize   # noqa: E402

ATOMS = os.path.join(ROOT, "assets/character/raw/open_peeps/extracted/Flat Assets")


def render_atom(rel, zoom=1.0):
    svg = open(os.path.join(ATOMS, rel), encoding="utf-8").read()
    arr, _ = rasterize(svg, zoom=zoom, crop=False)
    lum = arr[..., :3].astype(float).mean(axis=2)
    ink = np.where((arr[..., 3] > 128) & (lum < 110), 255, 0)              # the atoms are black ink + white fill shapes
    return ink.astype(np.uint8)


def harvest(rel, box, seal=(), zoom=1.5, ink_keep=14, min_area=1500, erode_fill=0, close_k=5):
    """box = (x0, y0, x1, y1) in atom coordinates. seal = edges of the crop to close ('left','right','top','bottom').
    Returns (fill_mask, ink_mask) uint8 0/255 in the crop's pixel grid (zoom applied)."""
    a = render_atom(rel, zoom)
    x0, y0, x1, y1 = (int(round(v * zoom)) for v in box)
    ink = (a[y0:y1, x0:x1] > 110).astype(np.uint8) * 255
    h, w = ink.shape
    sealed = ink.copy()
    t = max(3, int(6 * zoom))
    if "left" in seal:
        sealed[:, :t] = 255
    if "right" in seal:
        sealed[:, -t:] = 255
    if "top" in seal:
        sealed[:t, :] = 255
    if "bottom" in seal:
        sealed[-t:, :] = 255
    closed = cv2.morphologyEx(sealed, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (close_k, close_k)))
    pad = cv2.copyMakeBorder(closed, 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=0)
    ff = pad.copy()
    mask = np.zeros((ff.shape[0] + 2, ff.shape[1] + 2), np.uint8)
    cv2.floodFill(ff, mask, (0, 0), 128)
    outside = (ff[1:-1, 1:-1] == 128)
    enclosed = (~outside) & (closed == 0)
    # keep only the biggest enclosed region(s)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(enclosed.astype(np.uint8), 8)
    fill = np.zeros_like(enclosed)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] >= min_area:
            fill |= (lab == i)
    fill_u = fill.astype(np.uint8) * 255
    zone = cv2.dilate(fill_u, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ink_keep, ink_keep)))
    ink_out = cv2.bitwise_and(ink, zone)
    # undo the artificial seal ink
    if seal:
        cut = np.zeros_like(ink_out)
        if "left" in seal:
            cut[:, :t] = 255
        if "right" in seal:
            cut[:, -t:] = 255
        if "top" in seal:
            cut[:t, :] = 255
        if "bottom" in seal:
            cut[-t:, :] = 255
        ink_out = np.where((cut > 0) & (ink == 0), 0, ink_out)
    # fill also covers the closed ink footprint so there are no holes between fill and outline
    fill_u = cv2.bitwise_or(fill_u, cv2.bitwise_and(cv2.dilate(fill_u, np.ones((5, 5), np.uint8)), ink_out))
    return fill_u, ink_out


def compose(fill, ink, skin=(198, 134, 92), inkc=(20, 14, 12)):
    h, w = fill.shape
    out = np.zeros((h, w, 4), np.uint8)
    out[..., :3] = skin
    out[..., 3] = fill
    inkm = ink > 0
    out[inkm, :3] = inkc
    out[inkm, 3] = 255
    return out


if __name__ == "__main__":
    rel, box = sys.argv[1], tuple(int(v) for v in sys.argv[2:6])
    seal = tuple(sys.argv[6].split(",")) if len(sys.argv) > 6 and sys.argv[6] else ()
    f, i = harvest(rel, box, seal)
    im = Image.fromarray(compose(f, i))
    bg = Image.new("RGBA", im.size, (215, 225, 235, 255))
    bg.alpha_composite(im)
    bg.convert("RGB").save(sys.argv[7] if len(sys.argv) > 7 else "/tmp/hv/out.png")
    print(im.size)


def grid_crop(rel, box, out, step=25, zoom=2.0):
    """Debug helper: the atom region with a labelled coordinate grid (atom coordinates), to trace silhouettes by eye."""
    from PIL import ImageDraw
    a = render_atom(rel, zoom)
    x0, y0, x1, y1 = box
    crop = 255 - a[int(y0 * zoom):int(y1 * zoom), int(x0 * zoom):int(x1 * zoom)]
    im = Image.fromarray(crop).convert("RGB")
    d = ImageDraw.Draw(im)
    for x in range((x0 // step + 1) * step, x1, step):
        X = (x - x0) * zoom
        d.line([(X, 0), (X, im.height)], fill=(255, 120, 120), width=1)
        d.text((X + 2, 2), str(x), fill=(220, 0, 0))
    for y in range((y0 // step + 1) * step, y1, step):
        Y = (y - y0) * zoom
        d.line([(0, Y), (im.width, Y)], fill=(120, 120, 255), width=1)
        d.text((2, Y + 2), str(y), fill=(0, 0, 220))
    im.save(out)


def harvest_polygon(rel, box, poly, zoom=1.5, ink_pad=9):
    """Silhouette given as a polygon (atom coordinates, traced by eye): fill = polygon interior, ink = atom ink inside the polygon grown by ink_pad px. Returns (fill, ink) cropped to `box`."""
    a = render_atom(rel, zoom)
    x0, y0, x1, y1 = (int(round(v * zoom)) for v in box)
    ink = (a[y0:y1, x0:x1] > 110).astype(np.uint8) * 255
    m = np.zeros(ink.shape, np.uint8)
    pts = np.array([[(px * zoom - x0), (py * zoom - y0)] for px, py in poly], np.int32)
    cv2.fillPoly(m, [pts], 255)
    zone = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ink_pad, ink_pad)))
    ink_out = cv2.bitwise_and(ink, zone)
    fill = cv2.bitwise_and(m, cv2.bitwise_not(ink_out)) | cv2.bitwise_and(m, cv2.dilate(ink_out, np.ones((3, 3), np.uint8)))
    return fill, ink_out
