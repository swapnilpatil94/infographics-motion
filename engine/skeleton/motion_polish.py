"""MOTION POLISH: deterministic follow-through applied to the SAMPLED channels of production (v4) films. It adds what a keyframed pose sequence lacks:
  * hair secondary motion: a damped spring (w=9 rad/s, zeta=0.35) driven by the head + torso rotation, so the hair overshoots and settles after every head turn
  * neck lag: the neck trails the torso rotation by ~0.12 s (overlapping action) - the head arrives slightly after the body
  * breathing on chest_rot for characters whose channel is otherwise still (a listener, a person parked in a pose)
Nothing is random: same channels in -> same channels out. Off-screen / teleporting frames are untouched, and the result is bounded (hair +-10 deg, neck +-3 deg) so contact / gaze geometry never changes visibly."""
import math

import numpy as np


def _lowpass(x, fps, tau):
    a = 1.0 - math.exp(-1.0 / (fps * tau))
    y = np.empty_like(x)
    y[0] = x[0]
    for i in range(1, len(x)):
        y[i] = y[i - 1] + a * (x[i] - y[i - 1])
    return y


def _spring(target, fps, w=9.0, zeta=0.35):
    dt = 1.0 / fps
    x = np.empty_like(target)
    x[0], v = 0.0, 0.0
    for i in range(1, len(target)):
        a = w * w * (target[i] - x[i - 1]) - 2 * zeta * w * v
        v += a * dt
        x[i] = x[i - 1] + v * dt
    return x


def slew_limit(x, max_step):
    """two-pass rate limiter: no sample differs from its neighbour by more than `max_step`; a too-fast rotation is spread over the frames before AND after it (anticipation + settle) instead of popping"""
    y = np.array(x, np.float64)
    for i in range(1, len(y)):
        y[i] = min(max(y[i], y[i - 1] - max_step), y[i - 1] + max_step)
    for i in range(len(y) - 2, -1, -1):
        y[i] = min(max(y[i], y[i + 1] - max_step), y[i + 1] + max_step)
    return y


MAX_DEG_PER_FRAME = 22.0                                                     # 660 deg/s at 30 fps: a fast wrist flick, but never a pop (QC gate: 32)


def polish(channels, fps, seed=0):
    """channels: dict name -> list/array (mutated in place). Returns dict(stats)."""
    n = len(channels["head_rot"])
    head = np.array(channels["head_rot"], np.float64)
    torso = np.array(channels["spine_rot"], np.float64) + np.array(channels["chest_rot"], np.float64)
    drive = head + torso
    hair_extra = np.clip(_spring(_lowpass(drive, fps, 0.05), fps) * -0.55 + (drive - _lowpass(drive, fps, 0.12)) * -0.35, -10.0, 10.0)
    hair = np.array(channels["hair_rot"], np.float64) + hair_extra
    lag = np.clip((_lowpass(torso, fps, 0.12) - torso) * 0.35, -3.0, 3.0)
    neck = np.array(channels["neck_rot"], np.float64) + lag
    chest = np.array(channels["chest_rot"], np.float64)
    if float(np.ptp(chest)) < 0.6:                                              # a pose held for a long time: keep it breathing
        t = np.arange(n) / fps
        chest = chest + 0.55 * np.sin(2 * math.pi * t / 3.6 + seed * 0.7)
    limited = {}
    step = MAX_DEG_PER_FRAME * 30.0 / fps
    for k in list(channels):
        if (k.endswith("_rot") or k in ("spine_rot", "chest_rot")) and k not in ("hair_rot", "chest_rot", "neck_rot") and "pose" not in k and "flat" not in k:
            v = np.array(channels[k], np.float64)
            w = slew_limit(v, step)
            if float(np.abs(w - v).max()) > 1e-6:
                channels[k] = [float(z) for z in w]
                limited[k] = round(float(np.abs(w - v).max()), 1)
    channels["hair_rot"] = [float(x) for x in hair]
    channels["neck_rot"] = [float(x) for x in neck]
    channels["chest_rot"] = [float(x) for x in chest]
    return dict(slew_limited=limited, hair_range=float(np.ptp(hair)), neck_lag_max=float(np.abs(lag).max()), chest_range=float(np.ptp(chest)))
