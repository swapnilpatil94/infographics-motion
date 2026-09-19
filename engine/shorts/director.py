"""Compiles a version-2 shot-list DSL into a renderable Show.

The DSL separates what the character DOES (performance track) from how it
is SHOT (coverage track), the way a real edit does, and both are expressed
in narration-relative time ("s2.start+1.1"), so retiming the voice retimes
the whole film. An LLM/planner may author the JSON; only this compiler
turns it into motion, and only through the fixed action/event vocabulary
below - it never emits or runs code.
"""
import math
import re

import numpy as np

from engine.shorts import audio, captions, performance as P
from engine.shorts.character import BustRig, c2w, PHONE_CENTER
from engine.shorts.layers import Camera
from engine.shorts.lighting import Light
from engine.shorts.performance import Channel, ease
from engine.shorts.phone import PhoneScreen
from engine.shorts.scene import Scene
from engine.shorts.dust import Dust
from engine.shorts.insert import ScreenInsert

TIME_RE = re.compile(r"^(?:(?P<a>[a-z0-9_]+(?:\.[a-z]+)?)?(?P<off>[+-]\d+(?:\.\d+)?)?|(?P<num>\d+(?:\.\d+)?))$")


def resolve_time(expr, anchors):
    expr = str(expr).strip()
    try:
        return float(expr)
    except ValueError:
        pass
    m = re.match(r"^([a-z0-9_.]+)([+-]\d+(?:\.\d+)?)?$", expr)
    if not m or m.group(1) not in anchors:
        raise ValueError(f"cannot resolve time '{expr}' (known anchors: {sorted(anchors)})")
    return anchors[m.group(1)] + (float(m.group(2)) if m.group(2) else 0.0)


class Show:
    pass


class DSLError(ValueError):
    pass


PERF_ACTIONS = {"emotion", "look", "startle", "lean", "tremble", "blink"}
EVENTS = {"notification", "shock", "drone"}
CAM_TARGETS = {"room", "head", "phone", "chest", "eyes"}


def _validate(dsl, rig, anchors):
    """Fail early with a readable message; never reach the renderer with a bad plan."""
    for k in ("version", "format", "narration", "performance", "events", "coverage"):
        if k not in dsl:
            raise DSLError(f"missing top-level key '{k}'")
    for s in dsl["performance"]:
        if s["do"] not in PERF_ACTIONS:
            raise DSLError(f"unknown performance action '{s['do']}' (allowed: {sorted(PERF_ACTIONS)})")
        if s["do"] == "emotion" and s["to"] not in rig.heads:
            raise DSLError(f"emotion '{s['to']}' has no face variant (rig has: {sorted(rig.heads)})")
        if s["do"] == "look" and s["target"] not in P.LOOK_TARGETS:
            raise DSLError(f"look target '{s['target']}' unknown (allowed: {sorted(P.LOOK_TARGETS)})")
    for e in dsl["events"]:
        if e["do"] not in EVENTS:
            raise DSLError(f"unknown event '{e['do']}' (allowed: {sorted(EVENTS)})")
    prev = None
    for sh in dsl["coverage"]:
        t0, t1 = resolve_time(sh["from"], anchors), resolve_time(sh["to"], anchors)
        if t1 <= t0:
            raise DSLError(f"shot {sh['id']}: end <= start")
        if prev is not None and abs(t0 - prev) > 1e-6:
            raise DSLError(f"shot {sh['id']}: starts at {t0:.2f} but previous ended at {prev:.2f} (gap/overlap)")
        prev = t1
        for side in ("from", "to"):
            if sh["camera"][side]["target"] not in CAM_TARGETS:
                raise DSLError(f"shot {sh['id']}: camera target '{sh['camera'][side]['target']}' unknown")


def compile_show(dsl):
    show = Show()
    show.dsl = dsl
    fmt = dsl["format"]
    show.fps = fmt["fps"]
    anchors, clips = audio.build_narration(dsl["narration"])
    show.anchors, show.voice_clips = anchors, clips
    show.duration = anchors["end"]
    T = lambda e: resolve_time(e, anchors)

    rig = BustRig(dsl["character"]["rig_spec"])
    scene = Scene(rig)
    show.rig, show.scene = rig, scene
    phone = PhoneScreen()
    scene.extra.append(("@char", phone))
    show.phone = phone
    show.insert = ScreenInsert(phone)
    show.dust = Dust(dsl.get("seed", 0) + 4)
    scene.lights.ambient = np.array((0.18, 0.19, 0.32), np.float32)

    _validate(dsl, rig, anchors)
    perf = P.Performance(seed=dsl.get("seed", 0))
    show.perf = perf
    ch_bright, ch_banner, ch_pulse = Channel(0.0), Channel(0.0), Channel(0.0)
    show.ch_bright, show.ch_banner, show.ch_pulse = ch_bright, ch_banner, ch_pulse
    show.sfx = []                # (t, kind, gain)
    show.duck_windows = []       # (t0, t1, gain) for the room tone
    show.drones = []             # (t0, t1)
    show.shock_t = None
    show.notify_t = None

    # ------------------------------------------------------------ performance
    for step in sorted(dsl["performance"], key=lambda s: T(s["t"])):
        t, do = T(step["t"]), step["do"]
        if do == "emotion":
            P.emotion(perf, t, step["to"], step.get("dur", 0.12))
        elif do == "look":
            P.look(perf, t, step["target"], step.get("dur", 0.5), step.get("amount", 1.0), step.get("ease", "out_back"))
        elif do == "startle":
            P.startle(perf, t, step.get("amount", 1.0))
        elif do == "lean":
            P.lean(perf, t, step.get("dur", 1.0), step.get("amount", 1.0))
        elif do == "tremble":
            P.tremble(perf, t, step.get("dur", 2.0), step.get("amount", 1.0), step.get("ramp", 0.5))
        elif do == "blink":
            P.blink_at(perf, t)
        else:
            raise ValueError(f"unknown performance action '{do}'")

    # ----------------------------------------------------------------- events
    for ev in dsl["events"]:
        t, do = T(ev["t"]), ev["do"]
        if do == "notification":
            show.notify_t = t
            ch_bright.key(t - 0.001, 0.0)
            ch_bright.key(t + 0.10, 1.0, "out")
            ch_banner.key(t + 0.10, 0.0)
            ch_banner.key(t + 0.55, 1.0, "out_back")
            show.sfx += [(t, "ding", 1.0), (t + 0.02, "buzz", 1.0)]
            bx = perf.channel("bdx:buzz")
            for k in range(2):
                for j in range(5):
                    bx.key(t + k * 0.21 + j / show.fps, (1.4 if j % 2 == 0 else -1.4) * (1 - j / 6), "linear")
                bx.key(t + k * 0.21 + 5 / show.fps, 0.0, "linear")
        elif do == "shock":
            show.shock_t = t
            ch_pulse.key(t - 0.001, 0.0)
            ch_pulse.key(t + 0.05, 1.0, "out")
            ch_pulse.key(t + 1.4, 0.15, "smooth")
            show.sfx += [(t, "impact", 1.0), (t + 0.42, "heartbeat", 1.0), (t + 1.32, "heartbeat", 0.9)]
            show.duck_windows.append((t, anchors["end"] + 1, 0.22))
            show.sfx.append((t + 0.2, "tinnitus", 1.0))
        elif do == "drone":
            show.drones.append((t, T(ev["until"])))
        else:
            raise ValueError(f"unknown event '{do}'")

    # -------------------------------------------------------------- coverage
    fps = show.fps
    plans = []
    for shot in dsl["coverage"]:
        plans.append((T(shot["from"]), T(shot["to"]), shot))
    show.shots = plans
    for t0, t1, shot in plans[1:]:
        show.sfx.append((t0 - 0.06, "whoosh", 1.0))
    show.sfx += [(float(k), "tick", 1.0) for k in range(0, int(show.notify_t or 0))]

    # --------------------------------------------------------------- lighting
    L = scene.lights
    L.add(Light("shaft", (0.29, 0.33, 0.57), lambda t: 0.96 + 0.04 * math.sin(0.5 * t), reach=(2.05, 3.4), attach_par=0.85,
                poly=[(722, 290), (1018, 290), (500, 1250), (-60, 1250)], axis=[(870, 290), (220, 1250)],
                feather=46, fade_end=0.3))
    L.add(Light("radial", (0.10, 0.11, 0.22), 1.0, reach=(0, 3.4), attach_par=0.7, center=(870, 520), radius=760, power=1.6))
    L.add(Light("radial", (0.26, 0.33, 0.52), 0.55, reach=(1.5, 1.7), attach_par=1.0,
                center=c2w((800, 470)), radius=330, power=1.5))                          # moon rim on his face
    L.add(Light("radial", (0.50, 0.88, 1.0), lambda t: show.phone_light(t), reach=(0, 2.3), attach_par=1.0,
                center=c2w(PHONE_CENTER), radius=600, power=1.7))

    # --------------------------------------------------------------- captions
    show.caption_track = []
    for cap in dsl["captions"]:
        t0, t1 = anchors[f"{cap['seg']}.start"], anchors[f"{cap['seg']}.end"]
        chunks = cap["chunks"]
        total = sum(len(c) for c in chunks)
        cur = t0
        for c in chunks:
            d = (t1 - t0) * len(c) / total
            show.caption_track.append((cur - 0.04, cur + d + 0.05, c))
            cur += d

    # ------------------------------------------------------------- auto blinks
    if show.shock_t:
        perf.no_blink.append((show.shock_t - 0.4, anchors["end"]))
    P.auto_blinks(perf, 0.0, anchors["end"], seed=dsl.get("seed", 0) + 1)
    return show


def _phone_light(show, t):
    base = show.ch_bright(t) * 1.15
    pulse = 0.55 * show.ch_pulse(t)
    flicker = 1.0 + 0.03 * math.sin(11.0 * t) if show.ch_bright(t) > 0.5 else 1.0
    return (base + pulse * show.ch_bright(t)) * flicker


Show.phone_light = lambda self, t: _phone_light(self, t)


def _anchor_world(rig, name):
    if name == "room":
        return (540.0, 960.0)
    return rig.anchor(name)


def camera_at(show, t):
    for t0, t1, shot in show.shots:
        if t0 <= t < t1 or shot is show.shots[-1][2]:
            cam = shot["camera"]
            u = ease(cam.get("ease", "smooth"), (t - t0) / max(t1 - t0, 1e-6))
            a, b = cam["from"], cam["to"]
            pa = _anchor_world(show.rig, a["target"])
            pb = _anchor_world(show.rig, b["target"])
            oa, ob = a.get("offset", [0, 0]), b.get("offset", [0, 0])
            cx = (pa[0] + oa[0]) * (1 - u) + (pb[0] + ob[0]) * u
            cy = (pa[1] + oa[1]) * (1 - u) + (pb[1] + ob[1]) * u
            z = a["zoom"] * (1 - u) + b["zoom"] * u
            return Camera(cx, cy, z, focus=1.6, aperture=cam.get("aperture", 12)), shot["id"]
    return Camera(), "none"


def fade_at(show, t):
    end = show.duration
    fin = min(1.0, t / 0.5)
    fout = min(1.0, max(0.0, (end - t) / 0.55))
    return ease("smooth", fin) * ease("smooth", fout)


def configure(show, t):
    """Push every animated value for time t into the scene objects."""
    show.rig.state.update(show.perf.state(t))
    show.rig.apply()
    show.scene.camera, shot_id = camera_at(show, t)
    b = show.ch_bright(t)
    show.phone.update(b, show.ch_banner(t))
    show.phone.emissive_gain = 1.0
    show.scene.emissive_gain["phone_screen"] = 1.5 + 0.7 * show.ch_pulse(t)
    show.scene.emissive_gain["sky"] = 1.0
    return shot_id


def caption_at(show, t):
    for t0, t1, text in show.caption_track:
        if t0 <= t <= t1:
            fin = min(1.0, (t - t0) / 0.10)
            fout = min(1.0, (t1 - t) / 0.10)
            return text, max(0.0, min(fin, fout))
    return None, 0.0
