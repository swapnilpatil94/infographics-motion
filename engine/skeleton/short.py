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

import numpy as np
from PIL import Image

from engine.dsl import variation as VAR
from engine.environments import factory as EF
from engine.factory import audio_pipeline as AP, render as FR
from engine.shorts import captions, sets
from engine.shorts.dust import Dust
from engine.shorts.layers import C0, Camera, H, W, premultiply
from engine.shorts.lighting import Light
from engine.shorts.performance import ease
from engine.shorts.raster import ROOT
from engine.shorts.scene import Scene
from engine.skeleton import blender_job, motion as M, parts_art as PA, rig_def as R
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
        self.man = PA.bake(spec["dna"])
        self.P = self.man["P"]
        self.perf = M.Performance(self.P, seed=VAR.seed_int(plan["story_id"], cid, "perf") % 1000, world=dict(seat_h=BW.FLOOR_Y - BW.SEAT_Y))
        self.channels = None

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
    if isinstance(tg, str):
        wx, wy = plan["targets"][tg]
        rx, ry = actor.world_to_rig(wx, wy)
        kw["target"] = (rx - 18 * actor.P["k"], ry + 36 * actor.P["k"])                 # wrist target so the fingers close on the phone
    if kw.pop("world", False):
        pt = kw.get("point")
        if pt:
            kw["point"] = actor.world_to_rig(pt[0], pt[1])
    return kw


def build_actors(plan, log=print):
    actors = {}
    for cid in plan["cast_in_short"]:
        a = Actor(cid, plan["characters"][cid], plan, log)
        if cid == "A":
            M.pose_sit(a.perf, -1.0, seat=BW.FLOOR_Y - BW.SEAT_Y)
        else:
            M.pose_stand(a.perf, -1.0, 0.0)
        actors[cid] = a
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
            z = z0
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
            elif mv == "dolly_through":                                    # the camera travels IN through the depth layers: strong parallax gain
                z = z0 * (1.0 + 0.78 * ease("in", u) * 0.6 + 0.5 * e)
                g = 1.0 + 0.9 * e
                tx += 50 * e
            fear = 1.0 if sh["lighting"].get("mood") == "fear" else 0.6
            sx = fear * 3.2 * (math.sin(t * 2.3 + ph[0]) + 0.6 * math.sin(t * 5.1 + ph[1]))
            sy = fear * 2.6 * (math.sin(t * 1.9 + ph[2]) + 0.5 * math.sin(t * 4.3 + ph[3]))
            cx[f], cy[f], zm[f], gain[f] = tx + off[0] + sx, ty + off[1] + sy, z, g
            ap[f] = 7 + 9 * min(1.0, (z0 - 1.0) / 1.5)
    # light smoothing of the centre inside shots only (cuts stay hard)
    return dict(cx=cx, cy=cy, zoom=zm, gain=gain, aperture=ap)


def view_zoom(zoom, gain):
    return 1.0 + (zoom - 1.0) * gain


# ------------------------------------------------------------------------------------------------------------------ Blender
def render_actors(plan, actors, cam, workdir, log=print, samples=10):
    """One Blender job for all characters; only the frames of skeleton shots are rendered. Returns (frames_dir, report)."""
    n = int(round(plan["duration"] * plan["fps"]))
    fr = []
    for sh in plan["shots"]:
        if sh["treatment"] == "skeleton":
            fr += range(int(round(sh["t0"] * plan["fps"])), min(n, int(round(sh["t1"] * plan["fps"]))) + 1)
    fr = sorted(set(f for f in fr if f < n))
    out = os.path.join(workdir, "actor_frames")
    os.makedirs(out, exist_ok=True)
    chars = []
    for cid, a in actors.items():
        chars.append(dict(id=cid, manifest=os.path.join(ROOT, a.man["dir"], "parts.json"), facing=a.facing, origin=list(a.origin),
                          channels={k: [round(float(x), 4) for x in v] for k, v in a.channels.items()}))
    zoom_eff = [view_zoom(cam["zoom"][i], cam["gain"][i]) for i in range(n)]
    job = dict(width=W, height=H, fps=plan["fps"], start=0, end=n - 1, out=out, prefix="a", samples=samples, characters=chars,
               camera=dict(cx=[round(float(x), 3) for x in cam["cx"]], cy=[round(float(x), 3) for x in cam["cy"]], zoom=[round(float(x), 4) for x in zoom_eff]),
               render_frames=fr, probe_frames=fr[::max(1, len(fr) // 40)], save_blend=os.path.join(workdir, "skeleton_scene.blend"))
    rep = blender_job.run(job, workdir, log)
    return out, rep


class ActorLayer:
    """Duck-typed compositor layer: the Blender-rendered RGBA actors of frame f, already in screen space (camera baked in), lit by the light-map."""
    name, par, depth, emissive, opacity, visible = "actors", 1.0, 1.6, False, 1.0, True
    sway = 0.0

    def __init__(self, frames_dir, fps):
        self.dir, self.fps = frames_dir, fps
        self._cache = {}

    def rasterize_to_screen(self, cam, t=0.0, view_override=None):
        f = int(round(t * self.fps))
        if f not in self._cache:
            p = os.path.join(self.dir, f"a{f:05d}.png")
            if not os.path.exists(p):
                return None
            arr = np.asarray(Image.open(p).convert("RGBA"))
            self._cache = {f: premultiply(arr)}
        return self._cache[f], 0, 0


class ActorRig:
    def __init__(self, layer):
        self.layers = [layer]


# ------------------------------------------------------------------------------------------------------------------ shots
class SkeletonShot:
    def __init__(self, sh, film):
        self.sh, self.film = sh, film
        plan = film.plan
        set_id = film.set_id
        spec = sets.SETS[set_id]
        self.layers = sets.layers_for(set_id)
        self.scene = Scene(ActorRig(film.actor_layer), room=self.layers, order=sets.order_for(set_id), ambient=(0.20, 0.22, 0.34), bloom_strength=0.5, post=film.ctx.post)
        lt = sh["lighting"]
        mood = FR.MOODS.get(lt.get("mood", "dim"), FR.MOODS["dim"])
        self.exposure, self.vig = mood[2], mood[3]
        amb = np.array((0.20, 0.22, 0.34), np.float32) * np.array(mood[1], np.float32) * mood[0]
        self.scene.lights.ambient = amb
        A, Dm = film.actors["A"], film.actors.get("D")
        L = self.scene.lights
        moon = lt.get("moon", 1.0)
        L.add(Light("shaft", (0.28, 0.32, 0.56), lambda t: 0.9 * moon, reach=(0.0, 3.4), attach_par=0.85, poly=[(700, 330), (1040, 330), (760, 1500), (100, 1500)],
                    axis=[(870, 340), (420, 1500)], feather=50, fade_end=0.25))
        L.add(Light("radial", (0.10, 0.11, 0.22), 1.0, reach=(0, 3.4), attach_par=0.7, center=(760, 700), radius=1500, power=1.5))
        phone_gain = lt.get("phone", 1.0)
        self.phone_light = L.add(Light("radial", (0.50, 0.88, 1.0), lambda t: self._phone_level(t) * phone_gain, reach=(0, 2.6), attach_par=1.0, center=BW.PHONE_POS, radius=560, power=1.6))
        if lt.get("hall"):
            L.add(Light("radial", (0.95, 0.72, 0.42), lambda t: film.hall_level(t) * lt["hall"], reach=(0, 3.0), attach_par=0.9, center=(960, 1100), radius=760, power=1.5))
        if lt.get("lamp") or plan.get("lamp_on") is not None:
            L.add(Light("radial", (1.0, 0.72, 0.36), lambda t: film.lamp_level(t), reach=(0, 3.0), attach_par=0.96, center=(600, 1120), radius=820, power=1.4))
        self.dust = Dust(VAR.seed_int(plan["story_id"], sh["id"], "dust") % 1000)
        self.fx = self._fx()

    def _phone_level(self, t):
        A = self.film.actors["A"]
        tg = A.perf.ch["phone_glow"](t)
        if A.perf.ch["phone_vis"](t) > 0.5:
            self.phone_light.p["center"] = A.anchor("phone", t)
            return 0.95 * tg
        self.phone_light.p["center"] = BW.PHONE_POS
        return 0.9 * tg

    def _screen(self, cam, world_pt):
        cx, cy, z = cam.view(1.0)
        return (world_pt[0] - cx) * z + C0[0], (world_pt[1] - cy) * z + C0[1], z

    def _anchor_world(self, name, t):
        A = self.film.actors["A"]
        if name == "phone_free":
            return BW.PHONE_POS
        if name == "phone":
            return A.anchor("phone", t) if A.perf.ch["phone_vis"](t) > 0.5 else BW.PHONE_POS
        if name == "lamp":
            return (600.0, 1110.0)
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
            ph.visible = t < film.t_grab
        film.ctx.post.exposure = self.exposure
        img = self.scene.render(t, f, 1.0, insert=None, dust=self.dust, fx=self.fx)
        return film.ctx.extra_vignette(img, self.vig) if hasattr(film.ctx, "extra_vignette") else img


class SkeletonFilm(FR.Renderer):
    """The factory Renderer with one extra treatment: 'skeleton' (Blender-rigged full-body actors in a 2.5D set)."""

    def __init__(self, plan, actors, cam, actor_layer, log=print):
        super().__init__(plan, log)
        self.actors, self.cam, self.actor_layer = actors, cam, actor_layer
        self.set_id = EF.resolve(plan["environment"])
        self.t_grab = min([e[0] for e in actors["A"].perf.events if e[1] == "phone_grab"] or [1e9])
        self.hall_t = plan.get("hall_on", 1e9)

    def hall_level(self, t):
        return float(ease("smooth", (t - self.hall_t) / 0.7))

    def lamp_level(self, t):
        return float(ease("smooth", (t - self.plan.get("lamp_on", 1e9)) / 0.8))

    def camera_at(self, f):
        f = min(f, len(self.cam["cx"]) - 1)
        return Camera(float(self.cam["cx"][f]), float(self.cam["cy"][f]), float(self.cam["zoom"][f]), focus=1.6, aperture=float(self.cam["aperture"][f]), gain=float(self.cam["gain"][f]))

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
def build_everything(plan, workdir, log=print, samples=10, skip_blender=False):
    t0 = time.time()
    actors = build_actors(plan, log)
    cam = build_camera(plan, actors)
    if skip_blender and os.path.isdir(os.path.join(workdir, "actor_frames")):
        frames_dir, rep = os.path.join(workdir, "actor_frames"), json.load(open(os.path.join(workdir, "actor_frames", "report.json")))
    else:
        frames_dir, rep = render_actors(plan, actors, cam, workdir, log, samples)
    return actors, cam, frames_dir, rep, time.time() - t0


# ------------------------------------------------------------------------------------------------------------------ film
def _jd(o):
    return o.item() if hasattr(o, "item") else str(o)


def _title_card(img, plan, t):
    tc = plan.get("title_card")
    if not tc or not (tc["t0"] <= t <= tc["t1"]):
        return img
    a = min(1.0, (t - tc["t0"]) / 0.5) * min(1.0, (tc["t1"] - t + 0.001) / 0.3 + 0.0)
    a = max(0.0, min(1.0, a))
    img = img * (1.0 - 0.45 * a)
    arr, _ = captions.render(tc["text"], size=104, center_y=930)
    return captions.overlay(img, arr, a)


def render_film(plan, out_dir, log=print, skip_blender=False, samples=10, stills=None):
    """plan (dict) -> out_dir/{final.mp4, contact_sheet.png, plan.json, manifest.json, qc_report.json}. Deterministic: same plan -> same frames."""
    from engine.factory import pipeline as FP, qc as FQC
    from engine.skeleton import qc as SQC
    t_all = time.time()
    os.makedirs(out_dir, exist_ok=True)
    work = os.path.join(out_dir, "work")
    os.makedirs(work, exist_ok=True)
    stages = {}
    t = time.time()
    actors, cam, frames_dir, rep, _ = build_everything(plan, work, log, samples, skip_blender)
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
    audio_path = plan["narration"]["audio"]
    audio_path = audio_path if os.path.isabs(audio_path) else os.path.join(ROOT, audio_path)
    narr = AP.read_audio(audio_path)
    wav = AP.mix(plan["duration"], narr, sfx_list(plan, actors), [tuple(m) for m in plan["mood_track"]], out_dir=work)
    stages["audio"] = round(time.time() - t, 1)
    # ---- frames -> ffmpeg
    fps = plan["fps"]
    n = int(round(plan["duration"] * fps))
    out_mp4 = os.path.join(out_dir, "final.mp4")
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
    qc = SQC.run(plan, actors, cam, rep, film, out_mp4, stats, frames_dir, log)
    json.dump(qc, open(os.path.join(out_dir, "qc_report.json"), "w"), ensure_ascii=False, indent=1, default=_jd)
    man = dict(title=plan["title"], kind=plan["kind"], version=plan["version"], story_id=plan["story_id"], seed=plan["seed"], render_seconds=round(time.time() - t_all, 1), stages=stages,
               blender=dict(version=rep["blender"], frames_rendered=rep.get("rendered_frames"), objects=rep["objects"], bones=rep["bones"], ik_constraints=rep["ik_constraints"], actions=rep["actions"],
                            render_seconds=rep["render_seconds"], keyframed=True),
               characters={cid: dict(dna_id=a.spec["dna"]["id"], archetype=a.spec["dna"]["archetype"], parts=len(a.man["parts"]), part_dir=a.man["dir"]) for cid, a in actors.items()},
               environment=dict(plan["environment"], set_id=film.set_id), narration=dict(tts=plan["narration"]["tts"], tempo=plan["narration"]["tempo"], audio=plan["narration"]["audio"]),
               commands=dict(render=f"python3 studio.py --skeleton-short", from_plan=f"python3 studio.py --from-plan {os.path.relpath(os.path.join(out_dir, 'plan.json'), ROOT)}"),
               files=dict(final="final.mp4", contact_sheet="contact_sheet.png", plan="plan.json", qc="qc_report.json"), sha256_plan=hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest())
    json.dump(man, open(os.path.join(out_dir, "manifest.json"), "w"), ensure_ascii=False, indent=1, default=_jd)
    log(f"[short] {out_mp4}  QC passed: {qc['passed']}  ({man['render_seconds']}s)")
    return out_mp4, qc
