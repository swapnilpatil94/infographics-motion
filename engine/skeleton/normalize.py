"""Style normalisers for imported / harvested art so every asset lives in ONE ink language (milestone sec. 17):
line_weight_normalizer, palette_normalizer, scale_normalizer, stroke_join_normalizer, stroke_cap_normalizer, shadow_normalizer + a measurement report.
All functions are deterministic numpy/OpenCV."""
import math

import cv2
import numpy as np

INK_RGB = (12, 8, 8)


def ink_mask(rgba, dark=150, alpha=150):
    return ((rgba[..., 3] > alpha) & (rgba[..., :3].astype(int).sum(axis=2) < dark)).astype(np.uint8)


def stroke_width_px(rgba, scale=1.0):
    """median ink stroke width in RIG px: 2 x the distance-transform ridge values (ridge = local maxima of the DT inside the ink mask)."""
    m = ink_mask(rgba)
    if m.sum() < 50:
        return None
    dt = cv2.distanceTransform(m, cv2.DIST_L2, 5)
    mx = cv2.dilate(dt, np.ones((3, 3), np.uint8))
    ridge = (dt >= mx - 1e-6) & (dt > 0.6)
    vals = dt[ridge]
    return float(2.0 * np.median(vals) / scale) if len(vals) else None


def line_weight_normalizer(rgba, target_px, scale):
    """grow/shrink the ink so the median stroke width becomes target_px (rig px); returns a new RGBA"""
    out = rgba.copy()
    for _ in range(4):
        w = stroke_width_px(out, scale)
        if w is None or abs(w - target_px) < 0.35:
            break
        m = ink_mask(out)
        k = np.ones((3, 3), np.uint8)
        if w < target_px:
            m2 = cv2.dilate(m, k)
        else:
            m2 = cv2.erode(m, k)
        grow = (m2 > 0) & (m == 0)
        shrink = (m > 0) & (m2 == 0)
        out[grow, :3] = INK_RGB
        out[grow, 3] = 255
        out[shrink, 3] = 0
    return out


def stroke_join_normalizer(rgba):
    """round the joins: a 3x3 close on the ink mask fills the tiny notches where strokes meet"""
    m = ink_mask(rgba)
    c = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    add = (c > 0) & (m == 0)
    out = rgba.copy()
    out[add, :3] = INK_RGB
    out[add, 3] = 255
    return out


def stroke_cap_normalizer(rgba):
    """round the caps: a 3x3 open would remove spikes; instead blur-threshold the ink mask so square/pointed ends become round"""
    m = ink_mask(rgba).astype(np.float32)
    b = cv2.GaussianBlur(m, (0, 0), 0.9)
    r = (b > 0.5)
    out = rgba.copy()
    add = r & (m == 0)
    sub = (~r) & (m > 0)
    out[add, :3] = INK_RGB
    out[add, 3] = 255
    out[sub, 3] = 0
    return out


def palette_normalizer(rgba, skin_rgb, sclera=None):
    """every non-ink opaque pixel becomes the DNA skin tone (the atoms are mono line art: fill == skin); ink -> the shared ink colour"""
    out = rgba.copy()
    m = ink_mask(out).astype(bool)
    fill = (out[..., 3] > 0) & ~m
    out[fill, :3] = skin_rgb
    out[m, :3] = INK_RGB
    return out


def shadow_normalizer(rgba, skin_rgb, factor=0.86, toward=(0.0, 1.0)):
    """the same painted shade every part uses (0.86 x skin) on the side facing away from the light: a linear ramp along `toward`"""
    out = rgba.copy()
    h, w = out.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    u = (xx * toward[0] + yy * toward[1]) / max(1.0, h * abs(toward[1]) + w * abs(toward[0]))
    shade = tuple(int(c * factor) for c in skin_rgb)
    m = (out[..., 3] > 0) & ~ink_mask(out).astype(bool) & (u < 0.22)
    out[m, :3] = shade
    return out


def scale_normalizer(length_px_now, length_px_target):
    return length_px_target / max(1e-6, length_px_now)
