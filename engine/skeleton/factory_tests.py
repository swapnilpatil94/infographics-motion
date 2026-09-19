"""Reuse tests for the character factory (spec sec. 10): ONE rig, ONE asset family, MANY characters.

    output/tests/character_factory_contact_sheet.png   >= 20 characters from the same modular system (Blender-rendered, each with its own armature)
    output/tests/rig_motion_test.mp4                   the same rig: idle, look, walk, reach, hold_phone, sit, stand
    output/tests/crowd_test.mp4                        >= 30 characters: different scale, clothing, hair, pose, colour, position, orientation
"""
import json
import math
import os
import random
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from engine.characters import dna as DNA
from engine.dsl import variation as VAR
from engine.shorts.raster import ROOT
from engine.skeleton import blender_job, motion as M, parts_art as PA

OUT = os.path.join(ROOT, "output/tests")
ARCH = ["young_man", "young_woman", "middle_aged_man", "middle_aged_woman", "elderly_man", "elderly_woman", "student", "office_worker", "banker", "shopkeeper",
        "police_officer", "call_centre_agent", "manager", "family_member", "customer"]


def _font(size):
    for p in ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Helvetica.ttc"):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _gender(arch, r):
    return {"young_man": "male", "middle_aged_man": "male", "elderly_man": "male", "shopkeeper": "male", "young_woman": "female", "middle_aged_woman": "female", "elderly_woman": "female"}.get(arch, r.choice(["male", "female"]))


def make_dna(i, salt="factory"):
    r = random.Random(f"{salt}|{i}")
    arch = ARCH[i % len(ARCH)]
    return DNA.make(arch, f"{salt}:{i}", gender=_gender(arch, r), overrides=dict(height_scale=round(r.uniform(0.82, 1.08), 3)))


def channels_for(dna, seed, plan_fn, fps, dur):
    man = PA.bake(dna)
    perf = M.Performance(man["P"], seed=seed, world=dict(seat_h=270))
    M.pose_stand(perf, -1.0, 0.0)
    plan_fn(perf, man["P"])
    M.auto_blinks(perf, 0.0, dur, seed)
    return man, perf, M.sample(perf, fps, 0.0, dur)


# ------------------------------------------------------------------------------------------------------------------ 1. contact sheet
POSES = ["idle", "gesture", "point", "hold_phone", "shrug", "look_down", "fear", "confusion", "realization", "listen", "surprise", "talk"]
FACES = ["calm", "smile", "concerned", "uneasy", "shock", "serious", "confused", "happy", "determined", "suspicious", "tired", "fear"]


def contact_sheet(n=24, log=print):
    os.makedirs(OUT, exist_ok=True)
    work = os.path.join(OUT, "work_sheet")
    cols, rows = 6, math.ceil(n / 6)
    chars, dnas = [], []
    for i in range(n):
        dn = make_dna(i)

        def fn(perf, P, i=i):
            act = POSES[i % len(POSES)]
            M.set_face(perf, 0.1, FACES[(i * 5) % len(FACES)], 0.2)
            if act == "hold_phone":
                M.perform(perf, "grab", 0.2, 0.1)
                M.perform(perf, "hold_phone", 0.3, 0.9, "neutral", 0.5, pos="chest")
            elif act in ("idle", "gesture", "look_down", "point", "shrug", "talk", "listen"):
                M.perform(perf, act, 0.3, 1.2, "neutral", 0.6)
            else:
                M.perform(perf, act, 0.3, 1.2, "shocked", 0.6)
        man, perf, ch = channels_for(dn, 100 + i, fn, 30, 3.0)
        f = 62                                                   # a moment well into the action
        chars.append(dict(id=f"c{i:02d}", manifest=os.path.join(ROOT, man["dir"], "parts.json"), facing=1 if (i // cols) % 2 == 0 else -1, origin=[500 * (i % cols) + 280, 1400 + 1200 * (i // cols)],
                          channels={k: [round(float(v[f]), 4)] for k, v in ch.items()}))
        dnas.append((dn, POSES[i % len(POSES)]))
    W_, H_ = 1600, int(1600 * (rows * 1200 + 330) / (cols * 500))
    job = dict(width=W_, height=H_, fps=30, start=0, end=0, out=os.path.join(work, "frames"), prefix="s", samples=12, characters=chars, camera=dict(cx=cols * 500 / 2, cy=(rows * 1200 + 330) / 2 + 30, zoom=W_ / (cols * 500)),
               save_blend=os.path.join(work, "sheet.blend"))
    rep = blender_job.run(job, work, log)
    im = Image.open(os.path.join(work, "frames/s00000.png")).convert("RGBA")
    bg = Image.new("RGBA", im.size, (238, 236, 230, 255))
    bg.alpha_composite(im)
    d = ImageDraw.Draw(bg)
    ft = _font(21)
    sc = W_ / (cols * 500)
    for i, (dn, act) in enumerate(dnas):
        x, y = (500 * (i % cols) + 280) * sc, (1400 + 1200 * (i // cols) + 40 + 30) * sc
        d.text((x - 120 * sc * 1.4, y), dn["archetype"], fill=(50, 50, 60, 255), font=ft)
        d.text((x - 120 * sc * 1.4, y + 26), f"{dn['gender'][0]} · skin {dn['skin'][-2:]} · {act}", fill=(110, 110, 125, 255), font=_font(18))
    d.text((14, 8), f"character factory: {n} characters, ONE rig ({rep['bones']['c00']} bones, {rep['ik_constraints']['c00']} IK chains each), Blender {rep['blender']}", fill=(20, 20, 30, 255), font=_font(26))
    out = os.path.join(OUT, "character_factory_contact_sheet.png")
    bg.convert("RGB").save(out)
    json.dump(dict(n=n, unique_dna=len({d[0]['id'] for d in dnas}), archetypes=sorted({d[0]['archetype'] for d in dnas}), blender=rep["blender"], objects=rep["objects"],
                   bones_each=26), open(os.path.join(OUT, "character_factory_contact_sheet.json"), "w"), indent=1)
    return out


# ------------------------------------------------------------------------------------------------------------------ 2. rig motion test
def rig_motion_test(log=print, w=720, h=1280):
    os.makedirs(OUT, exist_ok=True)
    work = os.path.join(OUT, "work_motion")
    dn = make_dna(0, "motion")
    fps, dur = 30, 17.0
    man = PA.bake(dn)
    perf = M.Performance(man["P"], seed=5, world=dict(seat_h=270))
    M.pose_stand(perf, -1.0, 0.0)
    labels = []
    t = 0.3
    seq = [("idle", lambda t: M.perform(perf, "idle", t, 1.6)), ("look_left", lambda t: M.perform(perf, "look_left", t, 0.6)), ("look_right", lambda t: M.perform(perf, "look_right", t, 0.6)),
           ("look_down", lambda t: M.perform(perf, "look_down", t, 0.6)), ("head_tilt", lambda t: M.perform(perf, "head_tilt", t, 0.6, "curious", 0.7, angle=12)),
           ("walk", lambda t: M.perform(perf, "walk", t, 3.2, "neutral", 0.6, speed=240)),
           ("reach_for_phone", lambda t: M.perform(perf, "reach_for_phone", t, 1.1, "hesitant", 0.7, target=(perf.v("root_x", t) + 250, 700))),
           ("grab", lambda t: M.perform(perf, "grab", t, 0.1)), ("hold_phone", lambda t: M.perform(perf, "hold_phone", t, 0.9, "neutral", 0.5, pos="chest")),
           ("read_phone", lambda t: M.perform(perf, "read_phone", t, 1.2)), ("sit", lambda t: M.perform(perf, "sit", t, 1.4, "neutral", 0.6, seat=270)),
           ("fear", lambda t: M.perform(perf, "fear", t, 1.0, "fearful", 0.7)), ("stand", lambda t: M.perform(perf, "stand", t, 1.4, "neutral", 0.6))]
    starts = []
    for name, fn in seq:
        starts.append((t, name))
        t_end = fn(t)
        t = max(t_end, t + 0.5) + 0.25
    dur = t + 0.6
    M.auto_blinks(perf, 0.0, dur, 4)
    ch = M.sample(perf, fps, 0.0, dur)
    n = len(ch["root_x"])
    origin = [260.0, 1500.0]
    cxs = [420 + max(0.0, ch["root_x"][i] - 150) * 0.55 for i in range(n)]
    job = dict(width=w, height=h, fps=fps, start=0, end=n - 1, out=os.path.join(work, "frames"), prefix="m", samples=8,
               characters=[dict(id="A", manifest=os.path.join(ROOT, man["dir"], "parts.json"), facing=1, origin=origin, channels={k: [round(float(x), 4) for x in v] for k, v in ch.items()})],
               camera=dict(cx=[round(c, 2) for c in cxs], cy=1000.0, zoom=(w / 1080.0) * 1.0), save_blend=os.path.join(work, "motion.blend"))
    rep = blender_job.run(job, work, log)
    P = man["P"]
    ft, fs = _font(34), _font(24)
    outv = os.path.join(OUT, "rig_motion_test.mp4")
    proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "medium",
                             "-crf", "19", "-pix_fmt", "yuv420p", outv], stdin=subprocess.PIPE)
    k = w / 1080.0
    for i in range(n):
        tt = i / fps
        base = np.zeros((h, w, 3), np.float32)
        yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
        base[:] = (0.90 - 0.10 * yy)[:, :, None] * np.array([0.93, 0.94, 1.0], np.float32)
        img = Image.fromarray((base * 255).astype(np.uint8)).convert("RGBA")
        d = ImageDraw.Draw(img)
        cx, cy, z = cxs[i], 1000.0, k
        sx = lambda x: (x - cx) * z + w / 2
        sy = lambda y: (y - cy) * z + h / 2
        d.rectangle((0, sy(1500), w, h), fill=(196, 186, 170, 255))
        d.line((0, sy(1500), w, sy(1500)), fill=(60, 60, 70, 255), width=3)
        for gx in range(-2000, 4000, 200):                                    # floor ticks so walking reads
            d.line((sx(gx), sy(1500), sx(gx - 60), sy(1560)), fill=(150, 140, 125, 255), width=2)
        bx0, bx1 = 500 - 320, 500 + 40                                        # bench at seat height (used by sit / stand)
        bx0 += 0
        d.rectangle((sx(180), sy(1230), sx(560), sy(1290)), fill=(122, 90, 60, 255), outline=(30, 25, 20, 255), width=3)
        d.rectangle((sx(200), sy(1290), sx(224), sy(1500)), fill=(90, 66, 44, 255))
        d.rectangle((sx(516), sy(1290), sx(540), sy(1500)), fill=(90, 66, 44, 255))
        fr = Image.open(os.path.join(work, "frames", f"m{i:05d}.png")).convert("RGBA")
        img.alpha_composite(fr)
        d = ImageDraw.Draw(img)
        for nm, (xx, yy_) in dict(hand_R=("hand_R_x", "hand_R_y"), hand_L=("hand_L_x", "hand_L_y"), foot_L=("foot_L_x", "foot_L_y"), foot_R=("foot_R_x", "foot_R_y")).items():
            px, py = sx(origin[0] + ch[xx][i]), sy(origin[1] - ch[yy_][i])
            d.ellipse((px - 7, py - 7, px + 7, py + 7), outline=(230, 40, 60, 255), width=3)                # IK targets the Blender solver is chasing
        cur = ([nm for (s0, nm) in starts if s0 <= tt + 0.2] or ["stand"])[-1]
        d.rectangle((0, 0, w, 96), fill=(20, 22, 30, 255))
        d.text((18, 12), f"ONE rig · Blender armature + IK · action: {cur}", fill=(255, 255, 255, 255), font=ft)
        d.text((18, 58), f"t={tt:4.1f}s   red rings = IK targets (hands/feet) solved by Blender", fill=(190, 200, 220, 255), font=fs)
        proc.stdin.write(np.asarray(img.convert("RGB")).tobytes())
    proc.stdin.close()
    proc.wait()
    json.dump(dict(duration=n / fps, actions=[s[1] for s in starts], ik_max_error_px=max(max(e[k_] for k_ in ("IK_HAND_L", "IK_HAND_R", "IK_FOOT_L", "IK_FOOT_R")) for e in rep["ik_error_px"]),
                   blender=rep["blender"]), open(os.path.join(OUT, "rig_motion_test.json"), "w"), indent=1)
    return outv


# ------------------------------------------------------------------------------------------------------------------ 3. crowd test
def crowd_test(n=32, log=print, w=1920, h=1080, seconds=6.0):
    os.makedirs(OUT, exist_ok=True)
    work = os.path.join(OUT, "work_crowd")
    fps = 24
    N = int(seconds * fps)
    r = random.Random("crowd")
    cols = 8
    rows = math.ceil(n / cols)
    chars, meta = [], []
    for i in range(n):
        dn = make_dna(i + 40, "crowd")
        row, col = i // cols, i % cols
        gy = 1180 + row * 300
        x0 = 300 + col * 380 + r.uniform(-70, 70) + (row % 2) * 170
        facing = r.choice([1, -1])
        kind = r.choice(["walk", "walk", "idle", "talk", "phone", "point", "wave"])

        def fn(perf, P, kind=kind):
            M.set_face(perf, 0.1, r.choice(FACES), 0.2)
            if kind == "walk":
                M.perform(perf, "walk", 0.2, seconds - 0.4, "neutral", r.uniform(0.3, 0.8), speed=r.uniform(120, 230))
            elif kind == "phone":
                M.perform(perf, "grab", 0.2, 0.1)
                M.perform(perf, "hold_phone", 0.3, 0.9, "neutral", 0.5, pos=r.choice(["chest", "ear"]))
                M.perform(perf, "read_phone", 1.3, seconds - 1.6)
            elif kind == "point":
                M.perform(perf, "point", 0.4, 1.5)
                M.perform(perf, "gesture", 2.0, 3.0, "confident", 0.6)
            elif kind == "talk":
                M.perform(perf, "talk", 0.2, seconds - 0.4)
                M.perform(perf, "gesture", 0.2, seconds - 0.4, "confident", 0.5)
            elif kind == "wave":
                M.perform(perf, "gesture", 0.2, seconds - 0.4, "confident", 0.9, hand="R")
            else:
                M.perform(perf, "idle", 0.2, seconds - 0.4)
        man, perf, ch = channels_for(dn, 300 + i, fn, fps, seconds)
        chars.append(dict(id=f"p{i:02d}", manifest=os.path.join(ROOT, man["dir"], "parts.json"), facing=facing, origin=[round(x0, 1), gy],
                          channels={k: [round(float(v), 4) for v in vals] for k, vals in ch.items()}))
        meta.append(dict(id=dn["id"], archetype=dn["archetype"], scale=man["fb"]["height_scale"], hair=dn["hair"], clothing=dn["clothing"]["top"], facing=facing, action=kind, origin=[round(x0), gy]))
    chars.sort(key=lambda c: c["origin"][1])                                       # back row first: Blender depth = build order
    job = dict(width=w, height=h, fps=fps, start=0, end=N - 1, out=os.path.join(work, "frames"), prefix="c", samples=6, characters=chars,
               camera=dict(cx=1650.0, cy=1075.0, zoom=w / 3560.0), probe_frames=[0, N // 2], save_blend=os.path.join(work, "crowd.blend"))
    rep = blender_job.run(job, work, log)
    outv = os.path.join(OUT, "crowd_test.mp4")
    proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "medium",
                             "-crf", "19", "-pix_fmt", "yuv420p", outv], stdin=subprocess.PIPE)
    ft = _font(30)
    for i in range(N):
        yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
        base = np.zeros((h, w, 3), np.float32)
        base[:] = (0.92 - 0.14 * yy)[:, :, None] * np.array([0.95, 0.95, 1.0], np.float32)
        img = Image.fromarray((base * 255).astype(np.uint8)).convert("RGBA")
        d = ImageDraw.Draw(img)
        z = w / 3560.0
        floor = (1180 - 20 - 1075) * z + h / 2
        d.rectangle((0, floor, w, h), fill=(204, 194, 178, 255))
        img.alpha_composite(Image.open(os.path.join(work, "frames", f"c{i:05d}.png")).convert("RGBA"))
        d = ImageDraw.Draw(img)
        d.rectangle((0, 0, w, 54), fill=(20, 22, 30, 255))
        d.text((16, 8), f"crowd test: {n} characters from ONE factory (DNA -> parts -> Blender rig) · varied scale / clothing / hair / pose / colour / position / facing", fill=(255, 255, 255, 255), font=_font(24))
        proc.stdin.write(np.asarray(img.convert("RGB")).tobytes())
    proc.stdin.close()
    proc.wait()
    json.dump(dict(n=n, unique_dna=len({m["id"] for m in meta}), scales=sorted({m["scale"] for m in meta}), hair_styles=len({m["hair"] for m in meta}), outfits=len({m["clothing"] for m in meta}),
                   facing_left=sum(1 for m in meta if m["facing"] < 0), actions={a: sum(1 for m in meta if m["action"] == a) for a in {m["action"] for m in meta}}, blender=rep["blender"],
                   objects=rep["objects"], render_seconds=rep["render_seconds"], characters=meta), open(os.path.join(OUT, "crowd_test.json"), "w"), indent=1)
    return outv


def run_all(log=print):
    a = contact_sheet(24, log)
    b = rig_motion_test(log)
    c = crowd_test(32, log)
    return a, b, c
