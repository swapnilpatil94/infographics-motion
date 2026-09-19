"""Full-screen phone insert: the classic Shorts beat where the message is
shown large enough to read on a small screen. The room behind is the
current shot, defocused and dimmed; the phone is drawn in the same ink
language as the rest of the film and its screen is emissive (bloom + a
cyan spill onto the background), so it still reads as a light source.
"""
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw

from engine.shorts.layers import W, H

INK = (19, 18, 26)


def _phone_body(pw, ph):
    """Static ink-outlined phone body sprite (RGBA uint8) with the screen
    hole marked by alpha=0 so the UI can be placed underneath."""
    pad = 30
    img = Image.new("RGBA", (pw + pad * 2, ph + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = 96
    d.rounded_rectangle((pad, pad, pad + pw, pad + ph), r, fill=INK + (255,), outline=INK + (255,), width=14)
    d.rounded_rectangle((pad + 6, pad + 6, pad + pw - 6, pad + ph - 6), r - 6, outline=(70, 78, 96, 255), width=4)
    bez = 30
    d.rounded_rectangle((pad + bez, pad + bez, pad + pw - bez, pad + ph - bez), r - 34, fill=(0, 0, 0, 0))
    d.rounded_rectangle((pad + pw // 2 - 60, pad + 40, pad + pw // 2 + 60, pad + 40 + 26), 13, fill=(4, 5, 8, 255))
    return np.asarray(img).copy(), pad, bez


class ScreenInsert:
    def __init__(self, phone, width=800, angle=-5.0, center=(540, 940)):
        self.phone = phone
        self.pw = width
        self.ph = int(width * phone.uh / phone.uw * 1.04)
        self.angle = angle
        self.center = center
        self.body, self.pad, self.bez = _phone_body(self.pw, self.ph)
        self.sw = self.pw - 2 * self.bez
        self.sh = self.ph - 2 * self.bez
        yy, xx = np.mgrid[0:self.sh, 0:self.sw]
        r = 66
        cx = np.clip(xx, r, self.sw - r)
        cy = np.clip(yy, r, self.sh - r)
        self.screen_mask = (np.hypot(xx - cx, yy - cy) <= r).astype(np.float32)

    def apply(self, canvas, t, u, bright, banner_pos, shake=0.0, scale_push=0.0):
        """canvas: HxWx3 float scene render (pre-post). u: 0..1 progress in shot."""
        bg = cv2.GaussianBlur(canvas, (0, 0), 26) * 0.55
        ui = self.phone.compose_ui(bright, banner_pos)
        ui = cv2.resize(ui, (self.sw, self.sh), interpolation=cv2.INTER_AREA)
        a_ui = (ui[:, :, 3:4] / 255.0) * self.screen_mask[:, :, None]
        screen = np.zeros((self.ph + 2 * self.pad, self.pw + 2 * self.pad, 4), np.float32)
        y0, x0 = self.pad + self.bez, self.pad + self.bez
        screen[y0:y0 + self.sh, x0:x0 + self.sw, :3] = ui[:, :, :3] / 255.0 * 1.7 * a_ui
        screen[y0:y0 + self.sh, x0:x0 + self.sw, 3:4] = a_ui
        body = self.body.astype(np.float32) / 255.0
        ba = body[:, :, 3:4]
        rgb = body[:, :, :3] * ba + screen[:, :, :3] * (1 - ba)
        alpha = ba + screen[:, :, 3:4] * (1 - ba)
        sprite = np.concatenate([rgb, alpha], axis=2)
        sc = 1.0 + scale_push * u
        h, w = sprite.shape[:2]
        M = cv2.getRotationMatrix2D((w / 2, h / 2), self.angle, sc)
        M[0, 2] += self.center[0] - w / 2 + shake
        M[1, 2] += self.center[1] - h / 2
        warped = cv2.warpAffine(sprite, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        # cyan spill + soft shadow so the phone sits IN the scene
        glow = cv2.GaussianBlur(warped[:, :, 3], (0, 0), 90) * bright
        bg = bg + glow[:, :, None] * np.array([0.10, 0.22, 0.30], np.float32)
        shadow = cv2.GaussianBlur(warped[:, :, 3], (0, 0), 24)
        shadow = np.roll(shadow, (26, 18), axis=(0, 1))
        bg = bg * (1 - 0.5 * shadow[:, :, None])
        a = warped[:, :, 3:4]
        return warped[:, :, :3] * a + bg * (1 - a)
