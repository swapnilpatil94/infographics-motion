"""Renders a `skeleton_short` plan: semantic actions -> channels -> BLENDER (armature + IK + keyframes + RGBA) -> 2.5D compositor -> film.

    python3 studio.py --from-plan output/shorts/skeleton_factory_proof/plan.json        # deterministic; no LLM, no TTS, no analysis

Pipeline: plan -> Performance (motion grammar, per character) -> per-frame channels -> camera plan -> Blender job (only frames of skeleton shots)
-> actor frames -> Scene(environment layers + ActorLayer at '@char' + lights + GP + post) -> transitions/captions/title -> mix -> encode -> QC.
"""
import hashlib
import json
import math
import os
import subprocess
import time

import cv2
import numpy as np
from PIL import Image

from engine.dsl import variation as VAR
from engine.environments import factory as EF
from engine.factory import audio_pipeline as AP, render as FR
from engine.shorts import captions, sets
from engine.shorts.dust import Dust
from engine.shorts.layers import C0, Camera, H, Layer, W, premultiply
from engine.shorts.lighting import Light
from engine.shorts.performance import ease
from engine.shorts.raster import ROOT
from engine.shorts.scene import Scene
from engine.skeleton import blender_job, dna2, motion as M, parts_art as PA, parts_art2 as PA2, rig_def as R
from engine.environments import bedroom_wide as BW

FPS = 30
SIZES = dict(reveal=1.12, wide=1.0, wide2=1.06, full=1.2, two=1.34, two_reach=1.5, medium=1.75, close=2.5)
SHOOT_OFFSET = dict(reveal=(-110, 0), close=(30, 55), medium=(20, 10), full=(60, -20), two=(0, -10), two_reach=(0, 10), wide=(0, 0), wide2=(0, 0))


# ------------------------------------------------------------------------------------------------------------------ characters / motion
class Actor:
    """One character in the film: DNA -> baked parts -> Performance (channels) with world placement."""

    def __init__(self, cid, spec, plan, log=print):
        self.id, self.spec = cid, spec
        self.facing = spec["facing"]
        self.origin = tuple(spec["origin"])
        dn = spec["dna"]
        self.v2 = dn.get("schema") == dna2.SCHEMA
        if self.v2:
            self.view = spec.get("view", "profile")
            self.man = PA2.bake2(dn, self.view, spec.get("hand_set", "full"))
            pers = dna2.PERSONALITIES[dn["personality"]]
        else:
            self.view, self.man, pers = "profile", PA.bake(dn), None
        self.P = self.man["P"]
        self.perf = M.Performance(self.P, seed=VAR.seed_int(plan["story_id"], cid, "perf") % 1000, world=dict(seat_h=BW.FLOOR_Y - BW.SEAT_Y), facing=self.facing, origin=self.origin,
                                  personality=pers)
        self.channels = None

    def job_channels(self):
        """Channels as the Blender script wants them: canonical hand-pose ids -> indices into THIS character's pose set."""
        out = {k: [round(float(x), 4) for x in v] for k, v in self.channels.items()}
        poses = self.man.get("hand_poses")
        if poses:
            for side in ("L", "R"):
                ids = out.get(f"hand_{side}_pose_id")
                if ids is not None:
                    m = {}
                    for i, name in enumerate(PA2.HAND_POSES):
                        m[i] = poses.index(name) if name in poses else poses.index({"grab": "closed", "fist": "closed", "hold_phone": "closed", "hold_card": "gesture", "hold_money": "gesture", "point": "gesture", "palm_up": "open", "pinch": "gesture", "hold_pen": "point", "hold_cup": "closed", "type": "relaxed", "touch_screen": "point", "push": "open", "pull": "closed", "wave": "open", "palm_down": "relaxed"}.get(name, "open"))
                    out[f"hand_{side}_pose"] = [float(m[int(round(v))]) for v in ids]
        return out

    def rig_to_world(self, rx, ry):
        return (self.origin[0] + self.facing * rx, self.origin[1] - ry)

    def world_to_rig(self, wx, wy):
        return ((wx - self.origin[0]) * self.facing, self.origin[1] - wy)

    def anchor(self, name, t):
        perf, P = self.perf, self.P
        hx, hy = perf.hip(t)
        lean = math.radians(perf.v("spine_rot", t) + perf.v("chest_rot", t))
        up = lambda h: (hx + h * math.sin(lean), hy + h * math.cos(lean))
        if name == "hip":
            return self.rig_to_world(hx, hy)
        if name == "chest":
            return self.rig_to_world(*up(P["torso"] * 0.6))
        if name in ("head", "eyes", "temple"):
            hd = perf.v("head_rot", t) + perf.v("neck_rot", t)
            base = up(P["shoulder_y"] - P["hip_y"] + P["neck"])
            a = math.radians(hd + math.degrees(lean))
            k = {"head": 0.48, "eyes": 0.62, "temple": 0.75}[name]
            off = (P["head"] * k * math.sin(a), P["head"] * k * math.cos(a))
            x, y = base[0] + off[0], base[1] + off[1]
            if name == "eyes":
                x += 14 * P["k"]
            if name == "temple":
                x += 36 * P["k"]
            return self.rig_to_world(x, y)
        if name == "phone":
            return self.rig_to_world(perf.v("hand_R_x", t) + 14 * P["k"], perf.v("hand_R_y", t) - 14 * P["k"])
        if name == "root":
            return self.rig_to_world(perf.v("root_x", t), 0.0)
        raise KeyError(name)


def _resolve(actor, act, plan):
    """Named / world targets in an action -> this character's rig space (the grammar only knows rig space)."""
    kw = {k: v for k, v in act.items() if k not in ("char", "action", "t", "dur", "emotion", "intensity")}
    tg = kw.get("target")
    if plan.get("version", 1) >= 2:                          # V2: semantic target ids are resolved by the scene registry inside the grammar
        return kw
    if isinstance(tg, str):
        wx, wy = plan["targets"][tg]
        rx, ry = actor.world_to_rig(wx, wy)
        kw["target"] = (rx - 18 * actor.P["k"], ry + 36 * actor.P["k"])                 # wrist target so the fingers close on the phone
    if kw.pop("world", False):
        pt = kw.get("point")
        if pt:
            kw["point"] = actor.world_to_rig(pt[0], pt[1])
    return kw


def make_resolver(plan, actors):
    """The scene's SPATIAL-TARGET registry: semantic id -> world (x, y) at time t (PERSON_x, PHONE, HANDOVER, DOOR, TABLE, CHAIR, BED, NIGHTSTAND, LAMP, MONEY, SCREEN, custom ids)."""
    tg = plan.get("targets", {})

    def resolve(tid, t):
        if isinstance(tid, str) and tid.startswith("PERSON_"):
            return actors[tid[7:]].anchor("head", t)
        if tid == "PHONE":
            for a in actors.values():
                if a.perf.ch["phone_vis"](t) > 0.5:
                    return a.anchor("phone", t)
            return tuple(tg.get("PHONE", tg.get("nightstand_phone")))
        if tid in tg:
            return tuple(tg[tid])
        raise KeyError(f"unknown target id '{tid}' (registry: {sorted(tg)} + PERSON_<id>, PHONE)")
    return resolve


def _posture(a):
    dn = a.spec["dna"]
    if a.v2:
        pz = dna2.POSTURES[dn["posture"]]
        a.perf.ch["spine_rot"].key(-1.0, a.perf.ch["spine_rot"](-1.0) + pz["spine"], "linear")
        a.perf.ch["head_rot"].key(-1.0, pz["head"], "linear")


def _clamp_reach(a, fps):
    """A hand target can never be farther from the shoulder than the straight arm: clamp the sampled hand channels to 0.995 x arm length (Blender's IK otherwise leaves a few px of error while the body
    rises / leans, e.g. holding a phone during a stand-up). Body sizes vary, so this is a guard for every character, not a tweak for one."""
    reach = 0.995 * (a.P["upper_arm"] + a.P["forearm"])
    n = len(a.channels["root_x"])
    for side in ("L", "R"):
        hx, hy = a.channels[f"hand_{side}_x"], a.channels[f"hand_{side}_y"]
        for f in range(n):
            sx, sy = a.perf.shoulder(f / fps)
            sx += a.perf.so["s" + side]
            dx, dy = hx[f] - sx, hy[f] - sy
            d = math.hypot(dx, dy)
            if d > reach:
                hx[f], hy[f] = sx + dx * reach / d, sy + dy * reach / d


def build_actors(plan, log=print):
    actors = {}
    for cid in plan["cast_in_short"]:
        a = Actor(cid, plan["characters"][cid], plan, log)
        st = plan["characters"][cid].get("start", "sit" if cid == "A" else "stand")
        if st == "sit":
            M.pose_sit(a.perf, -1.0, seat=BW.FLOOR_Y - BW.SEAT_Y + plan["characters"][cid].get("seat_offset", 0.0))
        else:
            M.pose_stand(a.perf, -1.0, plan["characters"][cid].get("start_x", 0.0))
        _posture(a)
        actors[cid] = a
    resolver = make_resolver(plan, actors)
    for a in actors.values():
        a.perf.resolver = resolver
    acts = sorted((x for s in plan["shots"] for x in s.get("actions", [])), key=lambda x: (x["t"], x["char"]))
    seen = set()
    for x in acts:
        key = (x["char"], x["action"], x["t"])
        if key in seen:
            continue
        seen.add(key)
        a = actors[x["char"]]
        M.perform(a.perf, x["action"], x["t"], x["dur"], x.get("emotion", "neutral"), x.get("intensity", 0.5), **_resolve(a, x, plan))
    for a in actors.values():
        M.auto_blinks(a.perf, 0.0, plan["duration"], VAR.seed_int(plan["story_id"], a.id, "blink") % 1000)
        a.channels = M.sample(a.perf, plan["fps"], 0.0, plan["duration"])
    return actors


# ------------------------------------------------------------------------------------------------------------------ camera
def _target(plan, actors, spec, t):
    if spec == "stage":
        return (540.0, 1010.0)
    if spec == "A+D":
        pts = [actors[c].anchor("chest", t) for c in ("A", "D") if c in actors and (c == "A" or abs(actors[c].perf.v("root_x", t)) > 20)]
        if len(pts) == 1:
            pts.append((pts[0][0] + 130, pts[0][1]))
        return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
    if spec == "A.reach":
        c = actors["A"].anchor("chest", t)
        ph = plan["targets"]["nightstand_phone"]
        return ((c[0] + ph[0]) / 2, (c[1] + ph[1]) / 2)
    cid, part = spec.split(".")
    if part == "full":
        h, hip = actors[cid].anchor("head", t), actors[cid].anchor("hip", t)
        return ((h[0] + hip[0]) / 2 + 40, 1500 - 480)
    return actors[cid].anchor(part, t)


def build_camera(plan, actors):
    """Per-frame Camera parameters from the shots' camera intents (target, size, move). Deterministic; handheld micro-motion is seeded."""
    n = int(round(plan["duration"] * plan["fps"]))
    cx, cy, zm, gain = np.zeros(n), np.zeros(n), np.ones(n), np.ones(n)
    ap = np.full(n, 8.0)
    focus = np.full(n, 1.6)
    rng = VAR.rng(plan["story_id"], "camera", "shake")
    ph = [rng.uniform(0, 6.28) for _ in range(6)]
    prev = None
    for sh in plan["shots"]:
        f0, f1 = int(round(sh["t0"] * plan["fps"])), min(n, int(round(sh["t1"] * plan["fps"])))
        c = sh.get("camera")
        for f in range(f0, f1):
            t = f / plan["fps"]
            if not c:
                cx[f], cy[f] = 540, 1010
                continue
            u = (t - sh["t0"]) / max(sh["t1"] - sh["t0"], 1e-6)
            e = ease("smooth", u)
            size, mv = c["size"], c["move"]
            z0 = SIZES[size]
            off = SHOOT_OFFSET.get(size, (0, 0))
            if mv == "track":
                tx, ty = _target(plan, actors, c["target"], t)
            else:
                a0 = _target(plan, actors, c["target"], sh["t0"] + 0.05)
                a1 = _target(plan, actors, c["target"], sh["t1"] - 0.05)
                tx, ty = a0[0] + (a1[0] - a0[0]) * e, a0[1] + (a1[1] - a0[1]) * e
            z = z0 * c.get("zoom_mul", 1.0)
            z0 = z
            tx, ty = tx + c.get("dx", 0.0), ty + c.get("dy", 0.0)                    # critic fixes: framing nudges
            g = 1.0
            if mv == "push":
                z = z0 * (1.0 + 0.13 * e)
            elif mv == "pull":
                z = z0 * (1.13 - 0.13 * e)
            elif mv == "drift":
                z = z0 * (1.0 + 0.04 * e)
                tx += 34 * (e - 0.5)
            elif mv == "hold":
                z = z0 * (1.0 + 0.012 * e)
            elif mv == "track":
                z = z0 * (1.0 + 0.02 * e)
            elif mv == "truck":                                                    # lateral move through the layers: near layers slide faster than far ones
                z = z0 * (1.0 + 0.03 * e)
                tx += 220 * (e - 0.5) * (1 if c.get("dir", 1) > 0 else -1)
                g = 1.25
            elif mv == "reveal":                                                   # start beside the subject behind a foreground layer, slide out to reveal it
                z = z0 * (1.06 - 0.06 * e)
                tx += 300 * (1 - e) * (1 if c.get("dir", 1) > 0 else -1)
                g = 1.3
            elif mv == "rack_focus":
                z = z0 * (1.0 + 0.04 * e)
                focus[f] = 0.85 + (1.6 - 0.85) * ease("smooth", min(1.0, u * 1.4))     # focus pulls from the foreground layer to the character
                ap[f] = 16
            elif mv == "isolate":                                                  # character isolation: long lens (flat), shallow depth of field
                z = z0 * (1.0 + 0.05 * e)
                g = 0.6
            elif mv == "dolly_through":                                    # the camera travels IN through the depth layers: strong parallax gain
                z = z0 * (1.0 + 0.78 * ease("in", u) * 0.6 + 0.5 * e)
                g = 1.0 + 0.9 * e
                tx += 50 * e
            fear = 1.0 if sh["lighting"].get("mood") == "fear" else 0.6
            sx = fear * 3.2 * (math.sin(t * 2.3 + ph[0]) + 0.6 * math.sin(t * 5.1 + ph[1]))
            sy = fear * 2.6 * (math.sin(t * 1.9 + ph[2]) + 0.5 * math.sin(t * 4.3 + ph[3]))
            cx[f], cy[f], zm[f], gain[f] = tx + off[0] + sx, ty + off[1] + sy, z, g
            if mv not in ("rack_focus",):
                ap[f] = 7 + 9 * min(1.0, (z0 - 1.0) / 1.5) * (2.6 if mv == "isolate" else 1.0)
    # light smoothing of the centre inside shots only (cuts stay hard)
    return dict(cx=cx, cy=cy, zoom=zm, gain=gain, aperture=ap, focus=focus)


def view_zoom(zoom, gain):
    return 1.0 + (zoom - 1.0) * gain


# ------------------------------------------------------------------------------------------------------------------ Blender
def render_actors(plan, actors, cam, workdir, log=print, samples=10, only_frames=None):
    """One Blender job for all characters; only the frames of skeleton shots are rendered. Returns (frames_dir, report)."""
    n = int(round(plan["duration"] * plan["fps"]))
    fr = []
    for sh in plan["shots"]:
        if sh["treatment"] == "skeleton":
            fr += range(int(round(sh["t0"] * plan["fps"])), min(n, int(round(sh["t1"] * plan["fps"]))) + 1)
    fr = sorted(set(f for f in fr if f < n))
    if only_frames is not None:                                                    # critic previews: render just these frames
        fr = sorted(set(int(f) for f in only_frames if 0 <= int(f) < n))
    out = os.path.join(workdir, "actor_frames")
    os.makedirs(out, exist_ok=True)
    chars = []
    for cid, a in actors.items():
        chars.append(dict(id=cid, manifest=os.path.join(ROOT, a.man["dir"], "parts.json"), facing=a.facing, origin=list(a.origin), channels=a.job_channels()))
    zoom_eff = [view_zoom(cam["zoom"][i], cam["gain"][i]) for i in range(n)]
    job = dict(width=W, height=H, fps=plan["fps"], start=0, end=n - 1, out=out, prefix="a", samples=samples, characters=chars,
               camera=dict(cx=[round(float(x), 3) for x in cam["cx"]], cy=[round(float(x), 3) for x in cam["cy"]], zoom=[round(float(x), 4) for x in zoom_eff]),
               render_frames=fr, probe_frames=fr[::max(1, len(fr) // 40)], save_blend=os.path.join(workdir, "skeleton_scene.blend"))
    rep = blender_job.run(job, workdir, log)
    return out, rep


class ActorLayer:
    """Duck-typed compositor layer: the Blender-rendered RGBA actors of frame f, already in screen space (camera baked in), lit by the light-map.
    V2 adds depth-of-field (rack focus / isolation) and RIM LIGHT (a lit edge on the side facing each light: moon / hall / lamp)."""
    name, par, depth, emissive, opacity, visible = "actors", 1.0, 1.6, False, 1.0, True
    sway = 0.0

    def __init__(self, frames_dir, fps, film=None):
        self.dir, self.fps, self.film = frames_dir, fps, film
        self._cache = {}

    def rasterize_to_screen(self, cam, t=0.0, view_override=None):
        f = int(round(t * self.fps))
        if f not in self._cache:
            p = os.path.join(self.dir, f"a{f:05d}.png")
            if not os.path.exists(p):
                return None
            arr = np.asarray(Image.open(p).convert("RGBA"))
            self._cache = {f: premultiply(arr)}
        img = self._cache[f]
        film = self.film
        if film is not None and film.plan.get("version", 1) >= 2:
            sig = cam.blur_screen_px(self.depth)
            if sig > 0.7:
                img = cv2.GaussianBlur(img, (0, 0), sig)
            img = film.apply_rim(img, t)
        return img, 0, 0


class ShadowLayer:
    """Soft CONTACT SHADOWS on the floor under every visible character (body ellipse under the hips + a small one per foot that fades while the foot is lifted)."""
    name, par, depth, emissive, opacity, visible = "shadows", 1.0, 1.7, False, 1.0, True
    sway = 0.0

    def __init__(self, actors, fps, floor_y):
        self.actors, self.fps, self.floor = actors, fps, floor_y

    def rasterize_to_screen(self, cam, t=0.0, view_override=None):
        cx, cy, z = cam.view(1.0)
        a = np.zeros((H, W), np.uint8)
        any_ = False
        for act in self.actors.values():
            f = min(int(round(t * self.fps)), len(act.channels["root_x"]) - 1)
            ch, P = act.channels, act.P
            hx = ch["root_x"][f] + ch["pelvis_dx"][f]
            wx, wy = act.rig_to_world(hx, 0.0)
            sx, sy = (wx - cx) * z + C0[0], (self.floor + 6 - cy) * z + C0[1]
            if not (-400 < sx < W + 400):
                continue
            cv2.ellipse(a, (int(sx), int(sy)), (max(2, int(88 * P["k"] * z)), max(2, int(13 * z))), 0, 0, 360, 95, -1)
            for side in ("L", "R"):
                fx, fy = ch[f"foot_{side}_x"][f], ch[f"foot_{side}_y"][f]
                lift = max(0.0, 1.0 - (fy - P["foot_h"]) / 70.0)
                wx2, _ = act.rig_to_world(fx + 30 * P["k"], 0.0)
                sx2 = (wx2 - cx) * z + C0[0]
                cv2.ellipse(a, (int(sx2), int(sy)), (max(2, int(52 * P["k"] * z)), max(2, int(8 * z))), 0, 0, 360, int(80 * lift), -1)
            any_ = True
        if not any_:
            return None
        a = cv2.GaussianBlur(a, (0, 0), max(2.0, 7 * z))
        out = np.zeros((H, W, 4), np.uint8)
        out[..., 3] = a
        return out, 0, 0


class ActorRig:
    def __init__(self, layer, shadow=None):
        self.layers = ([shadow] if shadow is not None else []) + [layer]


# ------------------------------------------------------------------------------------------------------------------ shots
class SkeletonShot:
    def __init__(self, sh, film):
        self.sh, self.film = sh, film
        plan = film.plan
        set_id = film.set_id
        spec = sets.SETS[set_id]
        self.layers = sets.layers_for(set_id)
        self.scene = Scene(ActorRig(film.actor_layer, film.shadow_layer), room=self.layers, order=sets.order_for(set_id), ambient=(0.20, 0.22, 0.34), bloom_strength=0.5, post=film.ctx.post)
        lt = sh["lighting"]
        mood = FR.MOODS.get(lt.get("mood", "dim"), FR.MOODS["dim"])
        self.exposure, self.vig = mood[2] * lt.get("exposure_mul", 1.0), mood[3]                     # exposure_mul / fill: critic fixes (dark shots)
        amb = np.array(lt.get("ambient", (0.20, 0.22, 0.34)), np.float32) * np.array(mood[1], np.float32) * mood[0]
        self.scene.lights.ambient = amb
        A, Dm = film.actors["A"], film.actors.get("D")
        L = self.scene.lights
        moon = lt.get("moon", 1.0)
        L.add(Light("shaft", (0.28, 0.32, 0.56), lambda t: 0.9 * moon, reach=(0.0, 3.4), attach_par=0.85, poly=[(700, 330), (1040, 330), (760, 1500), (100, 1500)],
                    axis=[(870, 340), (420, 1500)], feather=50, fade_end=0.25))
        L.add(Light("radial", (0.10, 0.11, 0.22), 1.0, reach=(0, 3.4), attach_par=0.7, center=(760, 700), radius=1500, power=1.5))
        phone_gain = lt.get("phone", 1.0)
        self.phone_light = L.add(Light("radial", (0.50, 0.88, 1.0), lambda t: self._phone_level(t) * phone_gain, reach=(0, 2.6), attach_par=1.0, center=tuple(plan.get("targets", {}).get("PHONE", BW.PHONE_POS)), radius=560, power=1.6))
        if lt.get("sun"):                                                           # daylight through the window (lighting test / day scenes)
            L.add(Light("radial", (1.0, 0.90, 0.72), lambda t, v=lt["sun"]: v, reach=(0, 3.4), attach_par=0.8, center=(860, 640), radius=1900, power=1.2))
        self.face_light = None
        if film.plan.get("version", 1) >= 2:                                        # the phone screen lights the face: a tight cool radial that only reaches the actor layer
            self.face_light = L.add(Light("radial", (0.45, 0.82, 1.0), lambda t: self._face_level(t) * phone_gain, reach=(1.5, 1.7), attach_par=1.0, center=(540, 900), radius=250, power=1.3))
        self.fill_lights = {}
        if lt.get("fill") and film.plan.get("version", 1) >= 2:                      # soft cool fill on each face (critic fix for a face that is too dark to read)
            for cid in film.actors:
                self.fill_lights[cid] = L.add(Light("radial", (0.62, 0.72, 1.0), lambda t, c=cid: self._fill_level(c, t), reach=(1.5, 1.7), attach_par=1.0, center=(540, 900), radius=320, power=1.3))
        if lt.get("hall"):
            L.add(Light("radial", (0.95, 0.72, 0.42), lambda t: film.hall_level(t) * lt["hall"], reach=(0, 3.0), attach_par=0.9, center=(960, 1100), radius=760, power=1.5))
        if lt.get("lamp") or plan.get("lamp_on") is not None:
            L.add(Light("radial", (1.0, 0.72, 0.36), lambda t: film.lamp_level(t), reach=(0, 3.0), attach_par=0.96, center=tuple(plan.get("targets", {}).get("LAMP", (600, 1110))), radius=820, power=1.4))
        self.dust = Dust(VAR.seed_int(plan["story_id"], sh["id"], "dust") % 1000)
        for i, mk in enumerate(plan.get("debug_markers", [])):                      # parallax test: a coloured bar pinned to each layer's own parallax factor
            bar = np.zeros((1900, 26, 4), np.uint8)
            bar[..., :3] = mk["color"]
            bar[..., 3] = 255
            L_ = Layer(f"marker{i}", bar, (mk["x"] - 13, 0), 1.0, par=mk["par"], depth=mk.get("depth", 1.0))
            L_.emissive = True
            self.layers[f"marker{i}"] = L_
            self.scene.order = list(self.scene.order) + [f"marker{i}"]
        self.fx = self._fx()

    def _face_level(self, t):
        """The phone screen lights the face of whoever holds it (A, then D after the hand-over)."""
        for A in self.film.actors.values():
            g = A.perf.ch["phone_glow"](t)
            if g > 0.05 and A.perf.ch["phone_vis"](t) > 0.5 and self.face_light is not None:
                ex, ey = A.anchor("eyes", t)
                self.face_light.p["center"] = (ex + A.facing * 26, ey + 30)
                return 0.5 * g
        return 0.0

    def _fill_level(self, cid, t):
        ex, ey = self.film.actors[cid].anchor("eyes", t)
        self.fill_lights[cid].p["center"] = (ex, ey + 30)
        return 0.45 * float(self.sh["lighting"].get("fill", 0.0))

    def _phone_level(self, t):
        for A in self.film.actors.values():
            if A.perf.ch["phone_vis"](t) > 0.5:
                self.phone_light.p["center"] = A.anchor("phone", t)
                return 0.95 * A.perf.ch["phone_glow"](t)
        self.phone_light.p["center"] = tuple(self.film.plan.get("targets", {}).get("PHONE", BW.PHONE_POS))
        return 0.9 * self.film.actors["A"].perf.ch["phone_glow"](t)

    def _screen(self, cam, world_pt):
        cx, cy, z = cam.view(1.0)
        return (world_pt[0] - cx) * z + C0[0], (world_pt[1] - cy) * z + C0[1], z

    def _anchor_world(self, name, t):
        A = self.film.actors["A"]
        if name == "phone_free":
            return tuple(self.film.plan.get("targets", {}).get("PHONE", BW.PHONE_POS))
        if name == "phone":
            for a_ in self.film.actors.values():
                if a_.perf.ch["phone_vis"](t) > 0.5:
                    return a_.anchor("phone", t)
            return tuple(self.film.plan.get("targets", {}).get("PHONE", BW.PHONE_POS))
        if name == "lamp":
            return tuple(self.film.plan.get("targets", {}).get("LAMP", (600.0, 1110.0)))
        if name == "low":
            return (540.0, 1650.0)
        return A.anchor(name, t)

    def _fx(self):
        bank, sh = self.film.ctx.bank, self.sh
        if bank is None:
            return []
        out = []
        for g in sh["gp"]:
            a0, a1 = sh["t0"] + g["start"], sh["t0"] + g["start"] + g["duration"]

            def fx(c, cam, t, g=g, a0=a0, a1=a1):
                if not (a0 <= t <= a1):
                    return c
                u = (t - a0) / max(a1 - a0, 1e-6)
                fade = min(1.0, (t - a0) / 0.10, (a1 - t) / 0.25)
                x, y, z = self._screen(cam, self._anchor_world(g["anchor"], t))
                op = g["intensity"] * fade
                e = g["effect"]
                if e in ("arcs",):
                    bank.draw(c, "arcs", t, (x, y), min(z, 2.2) * 1.1, opacity=op)
                elif e == "rays":
                    bank.draw(c, "rays", t, (x, y), min(z, 1.8) * 0.9, opacity=op)
                elif e == "worry":
                    bank.draw(c, "worry", t, (x + 20 * z, y - 30 * z), min(z, 1.6) * 1.1, opacity=op)
                elif e == "ticks":
                    bank.draw(c, "ticks", t, (x, y), min(z, 1.5), opacity=g["intensity"] * max(0.0, 1 - u))
                elif e == "arrow":
                    bank.draw(c, "arrow", t, (x - 30 * z, y - 120 * z), min(z, 1.6) * 1.5, opacity=op)
                elif e == "scribble":
                    bank.draw(c, "scribble", t, (x + 130 * z, y - 160 * z), min(z, 1.5) * 0.9, opacity=op * 0.75)
                elif e == "smoke":
                    bank.draw(c, "smoke", t, (250, 1500), 1.5, opacity=op * 0.35)
                    bank.draw(c, "smoke", t + 0.4, (860, 1450), 1.3, opacity=op * 0.28)
                return c
            out.append(fx)
        return out

    def frame(self, t, f):
        film = self.film
        cam = film.camera_at(f)
        self.scene.camera = cam
        ph = self.layers.get("phone_free")
        if ph is not None:
            ph.visible = t < film.t_grab or t >= film.t_place
        film.ctx.post.exposure = self.exposure
        img = self.scene.render(t, f, 1.0, insert=None, dust=self.dust, fx=self.fx)
        return film.ctx.extra_vignette(img, self.vig) if hasattr(film.ctx, "extra_vignette") else img


class SkeletonFilm(FR.Renderer):
    """The factory Renderer with one extra treatment: 'skeleton' (Blender-rigged full-body actors in a 2.5D set)."""

    def __init__(self, plan, actors, cam, actor_layer, log=print):
        super().__init__(plan, log)
        self.actors, self.cam, self.actor_layer = actors, cam, actor_layer
        self.shadow_layer = ShadowLayer(actors, plan["fps"], BW.FLOOR_Y) if plan.get("version", 1) >= 2 else None
        actor_layer.film = self
        self.set_id = EF.resolve(plan["environment"])
        self.t_grab = min([e[0] for e in actors["A"].perf.events if e[1] == "phone_grab"] or [1e9])
        self.t_place = min([e[0] for e in actors["A"].perf.events if e[1] == "phone_place"] or [1e9])
        self.hall_t = plan.get("hall_on", 1e9)

    def rim_params(self, t):
        """[(direction (dx, dy), colour, strength)] of the lights that currently rim the actors."""
        lt = self.plan.get("rim", {})
        out = [((0.55, -0.83), (0.55, 0.70, 1.0), lt.get("moon", 0.5))]
        h = self.hall_level(t)
        if h > 0.02:
            out.append(((0.95, -0.15), (1.0, 0.78, 0.5), 0.45 * h))
        l = self.lamp_level(t)
        if l > 0.02:
            out.append(((-0.9, -0.2), (1.0, 0.76, 0.45), 0.55 * l))
        return out

    def apply_rim(self, img, t):
        a = img[..., 3].astype(np.float32) / 255.0
        add = np.zeros(img.shape[:2] + (3,), np.float32)
        for (dx, dy), col, strength in self.rim_params(t):
            if strength <= 0.01:
                continue
            m = np.float32([[1, 0, -dx * 5.0], [0, 1, -dy * 5.0]])
            a2 = cv2.warpAffine(a, m, (W, H), flags=cv2.INTER_LINEAR)
            edge = np.clip(a - a2, 0.0, 1.0) * strength
            add += edge[..., None] * np.array(col, np.float32)
        if not add.any():
            return img
        out = img.astype(np.float32)
        out[..., :3] = np.clip(out[..., :3] + add * 255.0 * 0.9, 0, 255)
        out[..., :3] = np.minimum(out[..., :3], out[..., 3:4])                           # stay premultiplied
        return out.astype(np.uint8)

    def hall_level(self, t):
        return float(ease("smooth", (t - self.hall_t) / 0.7))

    def lamp_level(self, t):
        return float(ease("smooth", (t - self.plan.get("lamp_on", 1e9)) / 0.8))

    def camera_at(self, f):
        f = min(f, len(self.cam["cx"]) - 1)
        return Camera(float(self.cam["cx"][f]), float(self.cam["cy"][f]), float(self.cam["zoom"][f]), focus=float(self.cam.get("focus", [1.6] * len(self.cam["cx"]))[f]), aperture=float(self.cam["aperture"][f]), gain=float(self.cam["gain"][f]))

    def renderer(self, i):
        if i not in self._r:
            for k in [k for k in self._r if k < i - 2]:
                del self._r[k]
            sh = self.shots[i]
            self._r[i] = SkeletonShot(sh, self) if sh["treatment"] == "skeleton" else FR.RENDERERS[sh["treatment"]](sh, self.ctx)
        return self._r[i]


# ------------------------------------------------------------------------------------------------------------------ audio
def sfx_list(plan, actors):
    out = [(s["t"], s["kind"], s["gain"]) for s in plan["sfx"]]
    for cid, a in actors.items():
        for t, kind, d in a.perf.events:
            if kind == "walk":
                T = d["T"]
                k = 0
                while t + k * T / 2 < d["t1"] - 0.1:
                    out.append((round(t + 0.05 + k * T / 2, 3), "footstep", 0.7 if cid == "A" else 0.55))
                    k += 1
            if kind == "phone_grab":
                out.append((round(t, 3), "tick", 0.7))
    return out


# ------------------------------------------------------------------------------------------------------------------ top level
def build_everything(plan, workdir, log=print, samples=10, skip_blender=False, only_frames=None):
    t0 = time.time()
    actors = build_actors(plan, log)
    cam = build_camera(plan, actors)
    if skip_blender and os.path.isdir(os.path.join(workdir, "actor_frames")):
        frames_dir, rep = os.path.join(workdir, "actor_frames"), json.load(open(os.path.join(workdir, "actor_frames", "report.json")))
    else:
        frames_dir, rep = render_actors(plan, actors, cam, workdir, log, samples, only_frames)
    return actors, cam, frames_dir, rep, time.time() - t0


# ------------------------------------------------------------------------------------------------------------------ film
def _jd(o):
    return o.item() if hasattr(o, "item") else str(o)


def _font(size):
    from PIL import ImageFont
    for p_ in ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Helvetica.ttc"):
        if os.path.exists(p_):
            try:
                return ImageFont.truetype(p_, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _draw_overlays(img, plan, t):
    """Debug/label text for test videos: plan['overlays'] = [{t0,t1,text,x,y,size,color}]. Text may be a callable-free string with {t} placeholder."""
    ov = [o for o in plan.get("overlays", []) if o["t0"] <= t <= o["t1"]]
    if not ov:
        return img
    from PIL import ImageDraw
    im = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    for o in ov:
        f = _font(o.get("size", 34))
        if o.get("bg", True):
            d.rectangle((o["x"] - 10, o["y"] - 6, o["x"] + o.get("w", 980), o["y"] + o.get("size", 34) * 1.35), fill=(12, 14, 20))
        d.text((o["x"], o["y"]), o["text"].replace("{t}", f"{t:4.1f}"), fill=tuple(o.get("color", (255, 255, 255))), font=f)
    return np.asarray(im).astype(np.float32) / 255.0


def _title_card(img, plan, t):
    tc = plan.get("title_card")
    if not tc or not (tc["t0"] <= t <= tc["t1"]):
        return img
    a = min(1.0, (t - tc["t0"]) / 0.5) * min(1.0, (tc["t1"] - t + 0.001) / 0.3 + 0.0)
    a = max(0.0, min(1.0, a))
    img = img * (1.0 - 0.45 * a)
    arr, _ = captions.render(tc["text"], size=104, center_y=930)
    return captions.overlay(img, arr, a)


def caption_at(plan, film, tt, caps):
    """The caption drawn at time tt -> (arr, bbox, text, opacity) or None (same rule as the film loop)."""
    if plan.get("title_card") and tt >= plan["title_card"]["t0"]:
        return None
    shot_i = film.index_at(tt)
    for c in caps:
        if c[0] <= tt <= c[1]:
            op = max(0.0, min(1.0, (tt - c[0]) / 0.08, (c[1] - tt) / 0.08))
            ptype = plan["shots"][shot_i].get("procedural", {}).get("type")
            from engine.factory import pipeline as FP
            cy = FP.CAPTION_Y_CARD if (plan["shots"][shot_i]["treatment"] == "procedural" and ptype != "money_flow") else 1440
            arr, bbox = captions.render(c[2], size=68, center_y=cy)
            return arr, bbox, c[2], op
    return None


def render_stills(plan, out_dir, times, log=print, samples=10, with_captions=True):
    """Preview stills at `times` (s) as the viewer would see them (title card + captions on). Only those frames are rasterised by Blender.
    -> dict(paths=[...], meta=[{t, shot, caption_bbox, caption}], actors, cam, film)."""
    from engine.factory import pipeline as FP
    os.makedirs(out_dir, exist_ok=True)
    work = os.path.join(out_dir, "work_preview")
    os.makedirs(work, exist_ok=True)
    only = [int(round(tt * plan["fps"])) for tt in times]
    actors, cam, frames_dir, rep, _ = build_everything(plan, work, log, samples, False, only)
    film = SkeletonFilm(plan, actors, cam, ActorLayer(frames_dir, plan["fps"]), log)
    caps = FP._captions([dict(s, start=s["start"] if "start" in s else s["start_seconds"], end=s["end"] if "end" in s else s["end_seconds"]) for s in plan["narration"]["segments"]])
    paths, meta = [], []
    for tt in times:
        f = int(round(tt * plan["fps"]))
        img = _title_card(film.frame_at(tt, f), plan, tt)
        cb = caption_at(plan, film, tt, caps) if with_captions else None
        if cb:
            img = captions.overlay(img, cb[0], cb[3])
        p = os.path.join(out_dir, f"still_{tt:07.2f}.png")
        Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).save(p)
        paths.append(p)
        meta.append(dict(t=tt, f=f, shot=plan["shots"][film.index_at(tt)]["id"], caption_bbox=list(cb[1]) if cb else None, caption=cb[2] if cb else None))
    return dict(paths=paths, meta=meta, actors=actors, cam=cam, film=film)


def render_film(plan, out_dir, log=print, skip_blender=False, samples=10, stills=None, qc="auto", final_name="final.mp4"):
    """plan (dict) -> out_dir/{final.mp4, contact_sheet.png, plan.json, manifest.json, qc_report.json}. Deterministic: same plan -> same frames."""
    from engine.factory import pipeline as FP, qc as FQC
    from engine.skeleton import qc as SQC
    t_all = time.time()
    os.makedirs(out_dir, exist_ok=True)
    work = os.path.join(out_dir, "work")
    os.makedirs(work, exist_ok=True)
    stages = {}
    t = time.time()
    only = [int(round(tt * plan["fps"])) for tt in stills] if stills else None
    actors, cam, frames_dir, rep, _ = build_everything(plan, work, log, samples, skip_blender, only)
    stages["rig+motion+blender"] = round(time.time() - t, 1)
    film = SkeletonFilm(plan, actors, cam, ActorLayer(frames_dir, plan["fps"]), log)
    if stills:
        outs = []
        for tt in stills:
            img = film.frame_at(tt, int(round(tt * plan["fps"])))
            p = os.path.join(out_dir, f"still_{tt:07.2f}.png")
            Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).save(p)
            outs.append(p)
        return outs
    # ---- audio
    t = time.time()
    audio_path = plan["narration"].get("audio")
    if audio_path:
        audio_path = audio_path if os.path.isabs(audio_path) else os.path.join(ROOT, audio_path)
        narr = AP.read_audio(audio_path)
    else:
        narr = np.zeros(int(plan["duration"] * AP.SR), np.float32)
    wav = AP.mix(plan["duration"], narr, sfx_list(plan, actors), [tuple(m) for m in plan["mood_track"]], out_dir=work)
    stages["audio"] = round(time.time() - t, 1)
    # ---- frames -> ffmpeg
    fps = plan["fps"]
    n = int(round(plan["duration"] * fps))
    out_mp4 = os.path.join(out_dir, final_name)
    caps = FP._captions([dict(s, start=s["start"] if "start" in s else s["start_seconds"], end=s["end"] if "end" in s else s["end_seconds"]) for s in
                         plan["narration"]["segments"]])
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "medium",
           "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", out_mp4]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    stats, ci, prev = [], 0, None
    t = time.time()
    for f in range(n):
        tt = f / fps
        img = film.frame_at(tt, f)
        img = _title_card(img, plan, tt)
        img = _draw_overlays(img, plan, tt)
        bbox = text = None
        while ci < len(caps) and caps[ci][1] < tt:
            ci += 1
        shot_i = film.index_at(tt)
        if plan["shots"][shot_i]["treatment"] != "procedural" or True:
            for c in caps[max(0, ci - 1):ci + 2]:
                if c[0] <= tt <= c[1] and not (plan.get("title_card") and tt >= plan["title_card"]["t0"]):
                    op = max(0.0, min(1.0, (tt - c[0]) / 0.08, (c[1] - tt) / 0.08))
                    ptype = plan["shots"][shot_i].get("procedural", {}).get("type")
                    cy = FP.CAPTION_Y_CARD if (plan["shots"][shot_i]["treatment"] == "procedural" and ptype != "money_flow") else 1440      # money_flow keeps its lower half empty
                    arr, bbox = captions.render(c[2], size=68, center_y=cy)
                    img = captions.overlay(img, arr, op)
                    text = c[2]
                    break
        small = img[::40, ::40]
        stats.append(dict(f=f, shot=plan["shots"][shot_i]["id"], mean=float(small.mean()), diff=float(np.abs(small - prev).mean()) if prev is not None else 1.0, bbox=bbox, text=text))
        prev = small.copy()
        proc.stdin.write((np.clip(img, 0, 1) * 255).astype(np.uint8).tobytes())
        if f % 200 == 0:
            log(f"[short] frame {f}/{n}  {time.time() - t:.0f}s")
    proc.stdin.close()
    proc.wait()
    stages["composite+encode"] = round(time.time() - t, 1)
    json.dump([dict(s, bbox=list(s["bbox"]) if s["bbox"] else None) for s in stats], open(os.path.join(work, "frame_stats.json"), "w"), default=_jd)
    FQC.contact_sheet(film, plan, os.path.join(out_dir, "contact_sheet.png"), cols=5, w=240)
    json.dump(plan, open(os.path.join(out_dir, "plan.json"), "w"), ensure_ascii=False, indent=1)
    if qc == "auto":
        qc = "v3" if plan.get("version", 1) >= 3 else ("v2" if plan.get("version", 1) >= 2 else "v1")
    if qc == "v3":
        from engine.skeleton import qc_v3
        qc = qc_v3.run(plan, actors, cam, rep, film, out_mp4, stats, frames_dir, log)
    elif qc == "v2":
        from engine.skeleton import qc_v2
        qc = qc_v2.run(plan, actors, cam, rep, film, out_mp4, stats, frames_dir, log)
    elif qc == "v1":
        qc = SQC.run(plan, actors, cam, rep, film, out_mp4, stats, frames_dir, log)
    else:
        qc = dict(file=os.path.basename(out_mp4), passed=True, n_checks=0, checks={}, evidence={"note": "test video: no QC gate"})
    json.dump(qc, open(os.path.join(out_dir, "qc_report.json"), "w"), ensure_ascii=False, indent=1, default=_jd)
    man = dict(title=plan["title"], kind=plan["kind"], version=plan["version"], story_id=plan["story_id"], seed=plan["seed"], render_seconds=round(time.time() - t_all, 1), stages=stages,
               blender=dict(version=rep["blender"], frames_rendered=rep.get("rendered_frames"), objects=rep["objects"], bones=rep["bones"], ik_constraints=rep["ik_constraints"], actions=rep["actions"],
                            render_seconds=rep["render_seconds"], keyframed=True),
               characters={cid: dict(dna_id=a.spec["dna"]["id"], archetype=a.spec["dna"].get("archetype", a.spec["dna"].get("role")), parts=len(a.man["parts"]), part_dir=a.man["dir"]) for cid, a in actors.items()},
               environment=dict(plan["environment"], set_id=film.set_id), narration=dict(tts=plan["narration"]["tts"], tempo=plan["narration"]["tempo"], audio=plan["narration"]["audio"]),
               commands=dict(render=f"python3 studio.py --skeleton-short", from_plan=f"python3 studio.py --from-plan {os.path.relpath(os.path.join(out_dir, 'plan.json'), ROOT)}"),
               files=dict(final="final.mp4", contact_sheet="contact_sheet.png", plan="plan.json", qc="qc_report.json"), sha256_plan=hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest())
    json.dump(man, open(os.path.join(out_dir, "manifest.json"), "w"), ensure_ascii=False, indent=1, default=_jd)
    log(f"[short] {out_mp4}  QC passed: {qc['passed']}  ({man['render_seconds']}s)")
    return out_mp4, qc
