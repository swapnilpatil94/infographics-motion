"""CAMERA GRAMMAR (spec sec. 9/10): narrative INTENT -> camera behaviour. The story decides WHY the camera moves; this decides HOW.

Intents: fear, realization, investigation, scale, urgency, authority, isolation, reveal, intimacy, neutral.
Movements: push, pull, hold, drift (lateral), pan, tilt, orbit (subtle parallax swing), rack (focus pull), dolly_through (push past foreground), tracking (lateral follow),
handheld shake (only when motivated), focal-length change (parallax gain). Output = keyframes consumed by engine.shorts.film._camera_kf.
"""
import math

SIZES = {"wide": dict(target=(640.0, 1010.0), zoom=1.24, offset=(0, 0), ap=7), "medium": dict(target="chest", zoom=1.72, offset=(10, -150), ap=13),
         "close": dict(target="eyes", zoom=1.95, offset=(0, 175), ap=16), "ecu": dict(target="eyes", zoom=3.0, offset=(0, 25), ap=26)}
ORDER = ["wide", "medium", "close", "ecu"]

INTENTS = {   # size_bias: steps tighter(+)/looser(-); move; shake; gain (focal feel); isolate: stronger DOF; slow: motion scale
    "fear": dict(bias=+1, move="push", shake=1.6, gain=1.15, aperture=1.4, speed=0.6),
    "realization": dict(bias=+1, move="push", shake=0.6, gain=1.0, aperture=1.6, speed=0.8, rack=True),
    "investigation": dict(bias=0, move="tracking", shake=0.5, gain=1.0, aperture=1.0, speed=1.0, rack=True),
    "scale": dict(bias=-2, move="pull", shake=0.2, gain=1.25, aperture=0.8, speed=0.5),
    "urgency": dict(bias=+1, move="push", shake=1.3, gain=1.05, aperture=1.1, speed=1.6),
    "authority": dict(bias=0, move="hold", shake=0.15, gain=0.9, aperture=1.0, speed=0.4, centered=True),
    "isolation": dict(bias=-1, move="pull", shake=0.3, gain=1.1, aperture=1.2, speed=0.5),
    "reveal": dict(bias=0, move="pan", shake=0.3, gain=1.0, aperture=1.0, speed=0.8, rack=True),
    "intimacy": dict(bias=+1, move="hold", shake=0.35, gain=0.9, aperture=1.3, speed=0.4),
    "neutral": dict(bias=0, move="drift", shake=0.45, gain=1.0, aperture=1.0, speed=1.0)}
MOVES = ["push", "pull", "hold", "drift", "pan", "tilt", "orbit", "tracking", "dolly_through"]


def intent_for(mood, emotion, phase, importance):
    """Story -> intent. (mood = lighting grammar, emotion = character state, phase = narrative phase.)"""
    if emotion in ("shock", "fear") and importance >= 4:
        return "realization" if phase in ("REVEAL", "CLIMAX") else "fear"
    if mood == "fear" or emotion in ("fear", "uneasy"):
        return "fear"
    if mood == "isolated":
        return "isolation"
    if mood in ("pressure",) and importance >= 3:
        return "urgency"
    if mood == "formal":
        return "authority"
    if phase in ("SETUP",):
        return "scale"
    if phase == "INCITING":
        return "investigation"
    if phase in ("PAYOFF",) and emotion in ("solemn", "calm", "smile", "happy"):
        return "intimacy"
    return "neutral"


def _shift(size, bias):
    return ORDER[max(0, min(len(ORDER) - 1, ORDER.index(size) + bias))]


def build(cam, t0, t1, seed=0):
    """cam: {size?, intent?, move?, subject?, shake?}; returns dict(size, kf, shake, settle). Deterministic in (cam, seed)."""
    it = INTENTS.get(cam.get("intent", "neutral"), INTENTS["neutral"])
    size = _shift(cam.get("size", "medium"), it["bias"] if cam.get("intent") and not cam.get("size_locked") else 0)
    move = cam.get("move") or it["move"]
    base = SIZES[size]
    dur = max(t1 - t0, 0.1)
    amt = 0.10 * it["speed"]
    z0, z1 = {"push": (1.0, 1.0 + amt), "pull": (1.0 + amt, 1.0), "hold": (1.0, 1.0 + 0.02 * it["speed"]), "drift": (1.0, 1.0 + 0.04 * it["speed"]),
              "pan": (1.0, 1.0 + 0.03), "tilt": (1.0, 1.0 + 0.03), "orbit": (1.0, 1.0 + 0.05), "tracking": (1.0, 1.0 + 0.03),
              "dolly_through": (1.0, 1.0 + 0.32 * it["speed"])}.get(move, (1.0, 1.02))
    ox, oy = base["offset"]
    dx0 = dx1 = dy0 = dy1 = 0.0
    if move in ("drift", "tracking"):
        d = 46 if move == "tracking" else 28
        s = 1 if seed % 2 == 0 else -1
        dx0, dx1 = -d * s, d * s
    if move == "pan":
        dx0, dx1 = -70, 70
    if move == "tilt":
        dy0, dy1 = 60, -60
    if it.get("centered"):
        dx0 = dx1 = 0.0
    rack = it.get("rack")
    ap = base["ap"] * it["aperture"]
    kf = [dict(t=t0, target=base["target"], zoom=base["zoom"] * z0, offset=(ox + dx0, oy + dy0), aperture=ap, focus=1.95 if rack else 1.6),
          dict(t=t1, target=base["target"], zoom=base["zoom"] * z1, offset=(ox + dx1, oy + dy1), aperture=ap, focus=1.6)]
    if move == "orbit":                       # subtle swing: a mid key on the opposite side gives an arc
        kf.insert(1, dict(t=t0 + dur / 2, target=base["target"], zoom=base["zoom"] * (z0 + z1) / 2, offset=(ox + 46, oy - 10), aperture=ap, focus=1.6))
    return dict(size=size, move=move, kf=kf, shake=cam.get("shake", it["shake"]) * (1.0 if cam.get("shake") is None else 1.0), gain=it["gain"], intent=cam.get("intent", "neutral"))
