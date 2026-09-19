"""Final-look pass: tone curve, vignette, paper fibre, engraved hatch in
the shadows, film grain, fade. Seeded per frame index, so a frame is a pure
function of (scene, t) - re-rendering reproduces it pixel for pixel.
"""
import cv2
import numpy as np

from engine.shorts.layers import W, H


def _aces(x):
    x = np.clip(x, 0.0, None)
    return np.clip((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0)


class Post:
    def __init__(self, seed=3, hatch_strength=0.16, grain=0.017, vignette=0.55, exposure=1.0):
        rng = np.random.default_rng(seed)
        self.grain, self.exposure, self.hatch_strength = grain, exposure, hatch_strength
        ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((xs - W / 2) / (W / 2)) ** 2 + ((ys - H * 0.47) / (H / 2)) ** 2)
        self.vig = (1.0 - vignette * np.clip(r - 0.35, 0, 1) ** 1.6)[:, :, None].astype(np.float32)
        low = cv2.GaussianBlur(rng.standard_normal((H // 8, W // 8)).astype(np.float32), (0, 0), 6)
        low = cv2.resize(low, (W, H), interpolation=cv2.INTER_CUBIC)
        fib = cv2.GaussianBlur(rng.standard_normal((H, W)).astype(np.float32), (0, 0), 1.1)
        low = low / (np.abs(low).max() + 1e-6)
        fib = fib / (np.abs(fib).max() + 1e-6)
        self.paper = (1.0 - 0.05 * low - 0.035 * fib)[:, :, None].astype(np.float32)
        ang = np.deg2rad(38)
        self.hatch_phase = ((xs * np.cos(ang) + ys * np.sin(ang)) / 7.0).astype(np.float32)

    def apply(self, img, frame, fade=1.0):
        img = img * self.exposure
        img = _aces(img)
        img = img * self.vig * self.paper
        if self.hatch_strength > 0:
            lum = img.mean(axis=2)
            dark = np.clip((0.34 - lum) / 0.34, 0.0, 1.0)
            line = (np.sin(self.hatch_phase * 2 * np.pi) > 0.72).astype(np.float32)
            img = img * (1.0 - self.hatch_strength * (dark * line))[:, :, None]
        if self.grain > 0:
            g = np.random.default_rng(1000 + int(frame)).standard_normal((H // 2, W // 2)).astype(np.float32)
            g = cv2.resize(g, (W, H), interpolation=cv2.INTER_LINEAR)[:, :, None]
            img = img + g * self.grain * (0.5 + 0.5 * img)
        return np.clip(img * fade, 0.0, 1.0)
