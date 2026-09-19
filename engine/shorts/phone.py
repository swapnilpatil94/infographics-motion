"""The phone screen: a dynamic emissive layer warped onto the phone quad
drawn in the character art. It is generated per frame (brightness and the
notification banner slide are animated), masked to the part of the screen
not covered by the drawn fingers, and treated as a light source: the
compositor draws it unlit and lets bloom carry the glow, while a matching
radial light (engine.shorts.lighting) spills onto his face.
"""
import io

import cv2
import numpy as np
import resvg_py
from PIL import Image

from asset_pipeline import phone_ui
from engine.shorts.character import PHONE_QUAD, PHONE_VISIBLE_IMG3, SC, RES, ORIGIN
from engine.shorts.layers import Layer, premultiply

UI_SCALE = 2.0


def _svg_rgba(svg, zoom=UI_SCALE):
    png = bytes(resvg_py.svg_to_bytes(svg_string=svg, zoom=zoom))
    return np.asarray(Image.open(io.BytesIO(png)).convert("RGBA")).copy()


class PhoneScreen(Layer):
    def __init__(self, time_text="2:47", body="एक ज़रूरी बात करनी है…", title="अज्ञात नंबर"):
        z = SC * RES
        quad = np.array(PHONE_QUAD, np.float32) * z
        bx0, by0 = int(quad[:, 0].min()) - 6, int(quad[:, 1].min()) - 6
        bw = int(quad[:, 0].max()) - bx0 + 6
        bh = int(quad[:, 1].max()) - by0 + 6
        self.bw, self.bh = bw, bh
        self.lock = _svg_rgba(phone_ui.lockscreen(time_text))
        self.banner = _svg_rgba(phone_ui.banner(title, body))
        uh, uw = self.lock.shape[:2]
        self.uw, self.uh = uw, uh
        src = np.array([[0, 0], [uw, 0], [uw, uh], [0, uh]], np.float32)
        dst = quad - np.array([bx0, by0], np.float32)
        self.H = cv2.getPerspectiveTransform(src, dst)
        poly = np.array([(690 + x / 3.0, 770 + y / 3.0) for x, y in PHONE_VISIBLE_IMG3], np.float32) * z
        poly = poly - np.array([bx0, by0], np.float32)
        mask = np.zeros((bh, bw), np.uint8)
        cv2.fillPoly(mask, [poly.astype(np.int32)], 255)
        self.mask = cv2.GaussianBlur(mask, (0, 0), 0.8).astype(np.float32) / 255.0
        origin = (ORIGIN[0] + bx0 / RES, ORIGIN[1] + by0 / RES)
        super().__init__("phone_screen", np.zeros((bh, bw, 4), np.uint8), origin, RES, par=1.0, depth=1.6, emissive=True)
        self.update(0.0, 1.0)

    def compose_ui(self, bright, banner_pos):
        """The lock screen + sliding notification as an HxWx4 float RGBA."""
        uh, uw = self.uh, self.uw
        if bright <= 0.001:
            ui = np.zeros((uh, uw, 4), np.float32)
            ui[:, :, :3] = (10, 14, 22)
            ui[:, :, 3] = 235
            return ui
        ui = self.lock.astype(np.float32).copy()
        ui[:, :, :3] *= bright
        bh_, bw_ = self.banner.shape[:2]
        y_dock = int(330 * UI_SCALE)
        y = int(-bh_ + (y_dock + bh_) * banner_pos)
        x = int(18 * UI_SCALE)
        if banner_pos > 0.001:
            y0, y1 = max(y, 0), min(y + bh_, uh)
            if y1 > y0:
                b = self.banner[y0 - y:y1 - y].astype(np.float32)
                a = (b[:, :, 3:4] / 255.0) * min(1.0, banner_pos * 3.0)
                reg = ui[y0:y1, x:x + bw_]
                reg[:, :, :3] = b[:, :, :3] * a + reg[:, :, :3] * (1 - a)
                reg[:, :, 3:4] = np.maximum(reg[:, :, 3:4], a * 255)
        return ui

    def update(self, bright, banner_pos):
        """bright 0..1 (screen lit); banner_pos 0..1 (0 = above screen, 1 = docked)."""
        ui = self.compose_ui(bright, banner_pos)
        warped = cv2.warpPerspective(ui, self.H, (self.bw, self.bh), flags=cv2.INTER_LINEAR,
                                     borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
        warped[:, :, 3] *= self.mask
        self.base = premultiply(np.clip(warped, 0, 255).astype(np.uint8))
        self._mips = {0: self.base}
        self._blur = {}
