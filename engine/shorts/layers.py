"""2.5D layer compositing primitives.

A Layer is premultiplied RGBA art with a world-space placement. Depth cues
come from three things, all deterministic and cheap for flat art:
  * parallax  - each layer has a factor `par` (1 = moves with the camera,
                <1 = far, >1 = near) applied to camera centre AND zoom
  * defocus   - Gaussian blur chosen from the layer's depth vs the shot's
                focus depth (pre-blurred sources are cached per level)
  * lighting  - the compositor multiplies non-emissive layers by a
                light-map, so ink stays black and lit areas glow
"""
import math

import cv2
import numpy as np

W, H = 1080, 1920
C0 = np.array([W / 2.0, H / 2.0])
BLUR_LEVELS = (0, 0.75, 1.5, 2.5, 4, 6, 9, 13, 19, 27, 38)


def premultiply(rgba):
    a = rgba[:, :, 3:4].astype(np.uint16)
    rgb = (rgba[:, :, :3].astype(np.uint16) * a + 127) // 255
    return np.concatenate([rgb.astype(np.uint8), rgba[:, :, 3:4]], axis=2)


class Camera:
    def __init__(self, cx=W / 2, cy=H / 2, zoom=1.0, focus=1.6, aperture=10.0, gain=1.0):
        self.cx, self.cy, self.zoom, self.focus, self.aperture, self.gain = cx, cy, zoom, focus, aperture, gain     # gain = focal-length feel: >1 wide-angle parallax, <1 telephoto-flat

    def view(self, par):
        """(centre_x, centre_y, zoom) as seen by a layer with parallax `par`."""
        z = 1.0 + (self.zoom - 1.0) * par * self.gain
        cx = C0[0] + (self.cx - C0[0]) * par
        cy = C0[1] + (self.cy - C0[1]) * par
        return cx, cy, z

    def screen_matrix(self, par):
        cx, cy, z = self.view(par)
        return np.array([[z, 0, -cx * z + C0[0]], [0, z, -cy * z + C0[1]], [0, 0, 1.0]])

    def blur_screen_px(self, depth):
        return self.aperture * abs(depth - self.focus) / (max(depth, 0.2) * self.focus)


class Layer:
    def __init__(self, name, rgba, origin, res, par=1.0, depth=2.0, emissive=False, sway=0.0):
        self.name = name
        self.base = premultiply(rgba)
        self.origin = tuple(origin)         # world coords of image top-left
        self.res = float(res)               # image px per world unit
        self.par, self.depth, self.emissive, self.sway = par, depth, emissive, sway
        self.opacity = 1.0
        self.world_xf = None                # optional 3x3 world->world (rig motion)
        self.visible = True
        self.pin_screen = False
        self._mips = {0: self.base}
        self._blur = {}

    # -- source selection ---------------------------------------------------
    def _mip(self, k):
        if k in self._mips:
            return self._mips[k]
        prev = self._mip(k - 1)
        self._mips[k] = cv2.pyrDown(prev) if min(prev.shape[:2]) > 8 else prev
        return self._mips[k]

    def source(self, k, sigma_world, t=0.0):
        q = min(BLUR_LEVELS, key=lambda v: abs(v - sigma_world))
        key = (k, q)
        if key not in self._blur:
            base = self._mip(k)
            if q == 0:
                self._blur[key] = base
            else:
                s = max(q * self.res / (2 ** k), 0.3)
                self._blur[key] = cv2.GaussianBlur(base, (0, 0), s)
        src = self._blur[key]
        if self.sway:
            src = self._apply_sway(src, k, t)
        return src

    def _apply_sway(self, src, k, t):
        h, w = src.shape[:2]
        v = np.linspace(0, 1, h, dtype=np.float32)[:, None]
        amp = self.sway * self.res / (2 ** k)
        dx = amp * (v ** 1.35) * (np.sin(2 * math.pi * 0.22 * t + 3.1 * v) +
                                 0.35 * np.sin(2 * math.pi * 0.61 * t + 7.0 * v + 1.3))
        mx = np.arange(w, dtype=np.float32)[None, :] + dx
        my = np.repeat(np.arange(h, dtype=np.float32)[:, None], w, axis=1)
        return cv2.remap(src, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)

    # -- drawing ------------------------------------------------------------
    def rasterize_to_screen(self, cam, t=0.0, view_override=None):
        """Returns (patch_u8_premult, x0, y0) covering only the layer's
        on-screen bounding box, or None if fully off-screen/invisible."""
        if not self.visible or self.opacity <= 0.001:
            return None
        cx, cy, z = view_override or cam.view(self.par)
        sigma_screen = cam.blur_screen_px(self.depth)
        sigma_world = sigma_screen / max(z, 0.1)
        a = z / self.res
        k = max(0, int(round(math.log2(1.0 / a)))) if a < 1.0 else 0
        src = self.source(k, sigma_world, t)
        res_k = self.res / (2 ** k)
        ox, oy = self.origin
        img_to_world = np.array([[1 / res_k, 0, ox], [0, 1 / res_k, oy], [0, 0, 1.0]])
        M = self.world_xf if self.world_xf is not None else np.eye(3)
        cam_m = np.array([[z, 0, -cx * z + C0[0]], [0, z, -cy * z + C0[1]], [0, 0, 1.0]])
        A = cam_m @ M @ img_to_world
        h, w = src.shape[:2]
        corners = np.array([[0, 0, 1], [w, 0, 1], [w, h, 1], [0, h, 1]], dtype=np.float64).T
        sc = A @ corners
        x0, y0 = int(math.floor(sc[0].min())), int(math.floor(sc[1].min()))
        x1, y1 = int(math.ceil(sc[0].max())), int(math.ceil(sc[1].max()))
        x0c, y0c, x1c, y1c = max(x0, 0), max(y0, 0), min(x1, W), min(y1, H)
        if x1c <= x0c or y1c <= y0c:
            return None
        A2 = A[:2].copy()
        A2[0, 2] -= x0c
        A2[1, 2] -= y0c
        patch = cv2.warpAffine(src, A2, (x1c - x0c, y1c - y0c), flags=cv2.INTER_LINEAR,
                               borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
        return patch, x0c, y0c

    def anchor_screen(self, cam, world_pt):
        cx, cy, z = cam.view(self.par)
        return (world_pt[0] - cx) * z + C0[0], (world_pt[1] - cy) * z + C0[1]


def composite_over(canvas, patch, x0, y0, light=None, opacity=1.0, emissive_gain=1.0):
    h, w = patch.shape[:2]
    reg = canvas[y0:y0 + h, x0:x0 + w]
    p = patch.astype(np.float32) * (1.0 / 255.0)
    rgb, a = p[:, :, :3], p[:, :, 3:4]
    if light is not None:
        rgb = rgb * light[y0:y0 + h, x0:x0 + w]
    else:
        rgb = rgb * emissive_gain
    if opacity != 1.0:
        rgb, a = rgb * opacity, a * opacity
    reg[:] = rgb + reg * (1.0 - a)
