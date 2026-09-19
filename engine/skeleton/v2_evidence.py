"""RENDERED EVIDENCE for Factory V2 (spec sec. 30). Every video is produced by the same pipeline as the Short: CharacterDNA v2 -> parts -> motion grammar -> Blender armature + IK -> RGBA -> PIL/compositor.

    character_factory_50_sheet.png   10_character_same_rig.mp4   rig_motion_v2.mp4   face_expression_test.mp4   eye_gaze_test.mp4   hand_pose_test.mp4
    multi_character_interaction.mp4  parallax_depth_test.mp4     lighting_test.mp4   crowd_test_v2.mp4          same_identity_views.mp4
"""
import json
import math
import os
import random
import subprocess

import numpy as np
from PIL import Image, ImageDraw

from engine.shorts.raster import ROOT
from engine.skeleton import blender_job, dna2, motion as M, parts_art2 as PA2, rig_def as R, short as SH

OUT = os.path.join(ROOT, "output/tests")
GROUND = 1500.0


# ------------------------------------------------------------------------------------------------------------------ helpers
def make_actor(cid, d2, view="three_quarter", facing=1, origin=(0.0, GROUND), hand_set="full", start="stand", seat=270.0, resolver=None, x0=0.0):
    a = SH.Actor(cid, dict(dna=d2, facing=facing, origin=list(origin), view=view, hand_set=hand_set), dict(story_id="evidence"))
    if start == "sit":
        M.pose_sit(a.perf, -1.0, seat=seat, x=x0)
    else:
        M.pose_stand(a.perf, -1.0, x0)
    SH._posture(a)
    a.perf.resolver = resolver
    return a


def finish(actors, fps, dur, blink_seed=1):
    for a in actors:
        M.auto_blinks(a.perf, 0.0, dur, blink_seed + hash(a.id) % 97)
        a.channels = M.sample(a.perf, fps, 0.0, dur)


def blender_frames(actors, cam, w, h, fps, name, samples=8, render_frames=None, log=print):
    n = len(actors[0].channels["root_x"])
    work = os.path.join(OUT, f"work_{name}")
    chars = [dict(id=a.id, manifest=os.path.join(ROOT, a.man["dir"], "parts.json"), facing=a.facing, origin=list(a.origin), channels=a.job_channels()) for a in actors]
    zc = [SH.view_zoom(cam["zoom"][i], cam.get("gain", np.ones(n))[i]) for i in range(n)]
    job = dict(width=w, height=h, fps=fps, start=0, end=n - 1, out=os.path.join(work, "frames"), prefix="e", samples=samples, characters=chars,
               camera=dict(cx=[round(float(x), 3) for x in cam["cx"]], cy=[round(float(x), 3) for x in cam["cy"]], zoom=[round(float(x), 4) for x in zc]),
               probe_frames=list(range(0, n, max(1, n // 40))), save_blend=os.path.join(work, f"{name}.blend"))
    if render_frames is not None:
        job["render_frames"] = list(render_frames)
    rep = blender_job.run(job, work, log)
    return work, rep


def studio_backdrop(w, h, cam_i, cx, cy, z, extra=None, seat=None):
    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    base = np.zeros((h, w, 3), np.float32)
    base[:] = (0.92 - 0.10 * yy)[:, :, None] * np.array([0.94, 0.95, 1.0], np.float32)
    img = Image.fromarray((base * 255).astype(np.uint8)).convert("RGBA")
    d = ImageDraw.Draw(img)
    sx = lambda x: (x - cx) * z + w / 2
    sy = lambda y: (y - cy) * z + h / 2
    if sy(GROUND) < h:
        d.rectangle((0, sy(GROUND), w, h), fill=(198, 188, 172, 255))
        d.line((0, sy(GROUND), w, sy(GROUND)), fill=(60, 60, 70, 255), width=3)
    for gx in range(-4000, 6000, 200):
        d.line((sx(gx), sy(GROUND), sx(gx - 60), sy(GROUND + 60)), fill=(150, 140, 125, 255), width=2)
    if extra:
        extra(d, sx, sy, z)
    return img, d, sx, sy


def encode(frames_gen, w, h, fps, path):
    proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "medium",
                             "-crf", "19", "-pix_fmt", "yuv420p", path], stdin=subprocess.PIPE)
    n = 0
    for im in frames_gen:
        proc.stdin.write(np.asarray(im.convert("RGB")).tobytes())
        n += 1
    proc.stdin.close()
    proc.wait()
    return n


def label(d, text, y=14, w=1080, size=30, sub=None):
    d.rectangle((0, 0, w, 92 if sub else 62), fill=(16, 18, 26))
    d.text((18, y - 4), text, fill=(255, 255, 255), font=SH._font(size))
    if sub:
        d.text((18, y + 40), sub, fill=(180, 190, 215), font=SH._font(22))


def cams_const(n, cx, cy, zoom):
    return dict(cx=np.full(n, float(cx)), cy=np.full(n, float(cy)), zoom=np.full(n, float(zoom)), gain=np.ones(n))


def scene_video(name, actors, dur, fps, w, h, cam, extra=None, header=None, sub_fn=None, log=print, samples=8):
    finish(actors, fps, dur)
    work, rep = blender_frames(actors, cam, w, h, fps, name, samples, log=log)
    n = len(actors[0].channels["root_x"])
    path = os.path.join(OUT, name + ".mp4")

    def frames():
        for i in range(n):
            t = i / fps
            cx, cy, zz = cam["cx"][i], cam["cy"][i], SH.view_zoom(cam["zoom"][i], cam.get("gain", np.ones(n))[i])
            img, d, sx, sy = studio_backdrop(w, h, i, cx, cy, zz, extra=(lambda dd, a, b, z, i=i, t=t: extra(dd, a, b, z, t)) if extra else None)
            img.alpha_composite(Image.open(os.path.join(work, "frames", f"e{i:05d}.png")).convert("RGBA"))
            d = ImageDraw.Draw(img)
            if header:
                txt, sub = header(t) if callable(header) else (header, None)
                label(d, txt, w=w, sub=sub_fn(t) if sub_fn else sub)
            yield img
    encode(frames(), w, h, fps, path)
    return path, rep


def ik_err(rep):
    return max(max(e[k] for k in ("IK_HAND_L", "IK_HAND_R", "IK_FOOT_L", "IK_FOOT_R")) for e in rep["ik_error_px"])


# ------------------------------------------------------------------------------------------------------------------ 1. 50-character sheet
ROLES = list(dna2.ROLES)


def factory_dna(i, salt="sheet"):
    return dna2.make(f"{salt}:{i}", ROLES[i % len(ROLES)])


def sheet50(n=50, log=print):
    os.makedirs(OUT, exist_ok=True)
    work = os.path.join(OUT, "work_sheet50")
    cols, rows = 10, 5
    chars, meta = [], []
    views = ["front", "three_quarter", "three_quarter", "profile", "front"]
    for i in range(n):
        d2 = factory_dna(i)
        view = views[(i * 3 + i // cols) % len(views)]
        a = SH.Actor(f"c{i:02d}", dict(dna=d2, facing=1 if (i % 3) else -1, origin=[330 * (i % cols) + 250, 1400 + 1380 * (i // cols)], view=view, hand_set="basic"), dict(story_id="sheet50"))
        M.pose_stand(a.perf, -1.0, 0.0)
        SH._posture(a)
        a.perf.resolver = None
        r = random.Random(i)
        M.set_face(a.perf, 0.1, r.choice(["neutral", "smile", "curious", "worried", "relief", "determination", "calm", "serious"]), 0.2)
        if i % 5 == 1:
            M.perform(a.perf, "gesture", 0.3, 1.0, "confident", 0.6)
        elif i % 5 == 3:
            M.perform(a.perf, "grab", 0.2, 0.1)
            M.perform(a.perf, "hold_phone", 0.3, 0.9, "neutral", 0.5, pos="chest")
        a.channels = M.sample(a.perf, 30, 0.0, 2.6)
        f = 66
        ch = {k: [round(float(v[f]), 4)] for k, v in a.job_channels().items()}
        chars.append(dict(id=a.id, manifest=os.path.join(ROOT, a.man["dir"], "parts.json"), facing=a.facing, origin=list(a.origin), channels=ch))
        meta.append(dict(dna=d2, view=view, facing=a.facing, height_px=round(a.P["height"]), P=a.P))
    W_ = 3500
    H_ = int(W_ * (rows * 1380 + 330) / (cols * 350))
    job = dict(width=W_, height=H_, fps=30, start=0, end=0, out=os.path.join(work, "frames"), prefix="s", samples=10, characters=chars,
               camera=dict(cx=cols * 350 / 2, cy=(rows * 1380 + 330) / 2 + 30, zoom=W_ / (cols * 350)), save_blend=os.path.join(work, "sheet.blend"))
    rep = blender_job.run(job, work, log)
    im = Image.open(os.path.join(work, "frames/s00000.png")).convert("RGBA")
    bg = Image.new("RGBA", im.size, (240, 238, 232, 255))
    bg.alpha_composite(im)
    d = ImageDraw.Draw(bg)
    sc = W_ / (cols * 350)
    for i, m in enumerate(meta):
        x, y = (330 * (i % cols) + 250) * sc, (1400 + 1380 * (i // cols) + 40) * sc
        dn = m["dna"]
        d.text((x - 135, y + 4), dn["id"], fill=(30, 30, 40), font=SH._font(24))
        d.text((x - 135, y + 32), f"{dn['role']}", fill=(90, 90, 105), font=SH._font(19))
        d.text((x - 135, y + 55), f"{dn['wardrobe']['top']}/{dn['wardrobe']['bottom']}/{dn['wardrobe']['shoes']}", fill=(110, 110, 125), font=SH._font(17))
        d.text((x - 135, y + 76), f"{m['view']} · {dn['silhouette']} · {dn['age']}y", fill=(110, 110, 125), font=SH._font(17))
    d.text((18, 10), f"CHARACTER FACTORY V2: {n} CharacterDNA v2 people, ONE 26-bone rig (Blender {rep['blender']}), 4 views, 7 tops, 5 bottoms, 4 shoes, 6 accessories", fill=(20, 20, 30), font=SH._font(34))
    path = os.path.join(OUT, "character_factory_50_sheet.png")
    bg.convert("RGB").save(path)
    stats = dict(n=n, unique_dna=len({m["dna"]["id"] for m in meta}), roles=sorted({m["dna"]["role"] for m in meta}), tops=sorted({m["dna"]["wardrobe"]["top"] for m in meta}),
                 bottoms=sorted({m["dna"]["wardrobe"]["bottom"] for m in meta}), shoes=sorted({m["dna"]["wardrobe"]["shoes"] for m in meta}),
                 accessories=sorted({a for m in meta for a in m["dna"]["wardrobe"]["accessories"]}), hair_styles=len({m["dna"]["hair"]["style"] for m in meta}),
                 skin_tones=len({m["dna"]["skin"]["id"] for m in meta}), silhouettes=sorted({m["dna"]["silhouette"] for m in meta}), views=sorted({m["view"] for m in meta}),
                 palettes=len({m["dna"]["wardrobe"]["palette"] for m in meta}), heights_px=[min(m["height_px"] for m in meta), max(m["height_px"] for m in meta)], eyes=sorted({m["dna"]["eyes"] for m in meta}),
                 brows=sorted({m["dna"]["eyebrows"] for m in meta}), mouths=sorted({m["dna"]["mouth"] for m in meta}), bones_each=26, objects=rep["objects"], blender=rep["blender"],
                 dna_ids=[m["dna"]["id"] for m in meta])
    json.dump(stats, open(os.path.join(OUT, "character_factory_50_sheet.json"), "w"), indent=1)
    return path, stats


# ------------------------------------------------------------------------------------------------------------------ 2. ten characters, one rig
def ten_same_rig(log=print, w=1920, h=1080):
    fps = 30
    dnas = [factory_dna(i * 5 + 2, "ten") for i in range(10)]
    actors = []
    for i, d2 in enumerate(dnas):
        a = make_actor(f"p{i}", d2, view=("three_quarter" if i % 2 else "profile"), facing=1, origin=(260.0 + 340 * i, GROUND), hand_set="full",
                       resolver=lambda tid, t, i=i: {"LEFT": (100.0 + 340 * i, 900.0), "RIGHT": (600.0 + 340 * i, 900.0), "AHEAD": (900.0 + 340 * i, 800.0), "PHONE": (560.0 + 340 * i, 800.0)}[tid])
        actors.append(a)
    seq = [(0.0, "idle"), (1.3, "look_left/right"), (3.0, "head_turn + tilt"), (4.2, "walk"), (7.6, "sit"), (9.4, "stand"), (11.0, "reach"), (12.3, "grab"), (12.7, "hold_phone"), (14.6, "gesture"), (17.4, "idle")]
    for a in actors:
        p = a.perf
        M.perform(p, "idle", 0.1, 1.2)
        M.perform(p, "look_at", 1.3, 0.7, "neutral", 0.5, target="LEFT")
        M.perform(p, "look_at", 2.1, 0.7, "neutral", 0.5, target="RIGHT")
        M.perform(p, "head_turn", 3.0, 0.6, "neutral", 0.5, direction=1)
        M.perform(p, "head_tilt", 3.6, 0.5, "curious", 0.6, angle=10)
        M.perform(p, "walk", 4.2, 3.0, "neutral", 0.6, speed=200, stride_scale=0.8)
        M.perform(p, "sit", 7.6, 1.4, "neutral", 0.6, seat=270)
        M.perform(p, "stand", 9.4, 1.4, "neutral", 0.6)
        M.perform(p, "reach", 11.0, 1.2, "hesitant", 0.6, target="PHONE", grip="grab")
        M.perform(p, "grab", 12.3, 0.1, prop="phone")
        M.perform(p, "hold_phone", 12.7, 0.9, "neutral", 0.5, pos="chest")
        M.perform(p, "gesture", 14.6, 2.4, "confident", 0.6, hand="L")
    dur = 18.6
    n = int(round(dur * fps))
    cam = cams_const(n, 1800.0, 1010.0, w / 3760.0)

    def extra(d, sx, sy, z, t):
        d.rectangle((sx(-200), sy(GROUND - 270), sx(4000), sy(GROUND - 236)), fill=(122, 90, 60), outline=(30, 25, 20), width=3)   # bench (seat height)
        for i in range(10):
            d.text((sx(150 + 340 * i), sy(GROUND + 30)), dnas[i]["id"], fill=(40, 40, 50), font=SH._font(18))
    path, rep = scene_video("10_character_same_rig", actors, dur, fps, w, h, cam, extra=extra,
                            header=lambda t: (f"10 different CharacterDNA v2 people · SAME rig definition · action: {[nm for s0, nm in seq if s0 <= t][-1]}", None), log=log)
    same = all([b[0] for b in R.bones(x.P)] == [b[0] for b in R.bones(actors[0].P)] for x in actors)
    json.dump(dict(dna_ids=[d["id"] for d in dnas], same_bone_list=same, bones=26, ik_max_error_px=ik_err(rep), actions=[s[1] for s in seq], blender=rep["blender"], objects=rep["objects"]),
              open(os.path.join(OUT, "10_character_same_rig.json"), "w"), indent=1)
    return path


# ------------------------------------------------------------------------------------------------------------------ 3. rig motion V2
def rig_motion_v2(log=print, w=720, h=1280):
    fps = 30
    d2 = dna2.make("motion", "young_woman", {"wardrobe.top": "jacket", "wardrobe.bottom": "jeans", "wardrobe.shoes": "sneakers", "wardrobe.palette": "teal", "wardrobe.accessories": ["earrings"], "personality": "cheerful"})
    reg = {"LEFT": (-200.0, 900.0), "RIGHT": (620.0, 900.0), "PHONE": (640.0, 1130.0), "POINT": (900.0, 820.0)}
    a = make_actor("A", d2, "three_quarter", 1, (300.0, GROUND), resolver=lambda tid, t: reg[tid])
    p = a.perf
    seq = []
    t = 0.2

    def do(name, fn, gap=0.25):
        nonlocal t
        seq.append((t, name))
        te = fn(t)
        t = max(te, t + 0.5) + gap
    do("idle · breathing · micro sway", lambda t: M.perform(p, "idle", t, 2.0))
    do("look_at LEFT", lambda t: M.perform(p, "look_at", t, 0.7, "curious", 0.6, target="LEFT"), 0.6)
    do("look_at RIGHT", lambda t: M.perform(p, "look_at", t, 0.7, "curious", 0.6, target="RIGHT"), 0.6)
    do("head_turn + head_tilt", lambda t: (M.perform(p, "head_turn", t, 0.6, "neutral", 0.5, direction=1), M.perform(p, "head_tilt", t + 0.7, 0.6, "curious", 0.6, angle=12))[1])
    do("walk (contact / passing / sway)", lambda t: M.perform(p, "walk", t, 3.4, "neutral", 0.6, speed=230), 0.3)
    do("sit", lambda t: M.perform(p, "sit", t, 1.5, "neutral", 0.6, seat=270))
    do("idle seated", lambda t: M.perform(p, "idle", t, 1.2), 0.1)
    do("stand", lambda t: M.perform(p, "stand", t, 1.5, "neutral", 0.6))
    do("reach (anticipation > reach > contact)", lambda t: M.perform(p, "reach", t, 1.3, "hesitant", 0.7, target="PHONE", grip="grab"), 0.05)
    do("grab", lambda t: M.perform(p, "grab", t, 0.15, prop="phone"), 0.1)
    do("hold_phone", lambda t: M.perform(p, "hold_phone", t, 0.9, "neutral", 0.5, pos="chest"), 0.1)
    do("read_phone", lambda t: M.perform(p, "read_phone", t, 1.8))
    do("release", lambda t: M.perform(p, "release", t, 0.8, prop="phone"), 0.2)
    do("gesture", lambda t: M.perform(p, "gesture", t, 2.2, "confident", 0.7))
    do("point at POINT", lambda t: M.perform(p, "point", t, 0.9, "confident", 0.6, target="POINT"), 0.4)
    dur = t + 0.8
    n = int(round(dur * fps))
    finish([a], fps, dur)
    xs = a.channels["root_x"]
    cx = [300 + 140 + max(0.0, xs[i] - 0.0) * 0.65 for i in range(n)]
    cam = dict(cx=np.array(cx), cy=np.full(n, 1010.0), zoom=np.full(n, w / 1080.0 * 0.98), gain=np.ones(n))
    work, rep = blender_frames([a], cam, w, h, fps, "rig_motion_v2", 8, log=log)
    path = os.path.join(OUT, "rig_motion_v2.mp4")
    k = w / 1080.0

    def frames():
        for i in range(n):
            tt = i / fps
            cxi = cam["cx"][i]
            img, d, sx, sy = studio_backdrop(w, h, i, cxi, 1010.0, k * 0.98)
            d.rectangle((sx(430), sy(GROUND - 270), sx(1100), sy(GROUND - 236)), fill=(122, 90, 60), outline=(30, 25, 20), width=3)          # bench
            gr = a.channels["phone_vis"][i] < 0.5 and not any(e[1] == "phone_release" and e[0] <= tt for e in p.events) and not any(e[1] == "phone_grab" and e[0] <= tt for e in p.events)
            if gr:
                d.rectangle((sx(690), sy(1350), sx(730), sy(GROUND)), fill=(110, 80, 55), outline=(30, 25, 20), width=3)
                d.rectangle((sx(660), sy(1120), sx(760), sy(1150)), fill=(122, 90, 60), outline=(30, 25, 20), width=3)
                d.rectangle((sx(690), sy(1090), sx(730), sy(1120)), fill=(21, 23, 28), outline=(0, 0, 0), width=3)
            d.ellipse((sx(reg["POINT"][0]) - 8, sy(reg["POINT"][1]) - 8, sx(reg["POINT"][0]) + 8, sy(reg["POINT"][1]) + 8), outline=(220, 40, 60), width=3)
            img.alpha_composite(Image.open(os.path.join(work, "frames", f"e{i:05d}.png")).convert("RGBA"))
            d = ImageDraw.Draw(img)
            cur = [nm for s0, nm in seq if s0 <= tt + 0.15][-1] if any(s0 <= tt + 0.15 for s0, _ in seq) else seq[0][1]
            label(d, f"rig_motion_v2 · {cur}", w=w, size=27, sub=f"t={tt:4.1f}s · CharacterDNA v2 {d2['id']} · Blender IK max error {ik_err(rep):.2f}px")
            yield img
    encode(frames(), w, h, fps, path)
    json.dump(dict(duration=n / fps, actions=[s[1] for s in seq], ik_max_error_px=ik_err(rep), dna=d2["id"], events=sorted({e[1] for e in p.events}), blender=rep["blender"]),
              open(os.path.join(OUT, "rig_motion_v2.json"), "w"), indent=1)
    return path


# ------------------------------------------------------------------------------------------------------------------ 4. face expressions
EMOTIONS11 = ["neutral", "curious", "confused", "worried", "fear", "surprise", "realization", "relief", "sadness", "anger", "determination"]
VISEMES = ["A", "E", "I", "O", "U", "shocked"]
MOUTHS = [("closed", {}), ("neutral", dict(mouth_open=0.0)), ("smile", dict(mouth_smile=1.0)), ("worried", dict(mouth_worried=1.0)), ("open", dict(mouth_open=0.7)), ("shocked", dict(vis_shocked=1.0, mouth_open=1.0))]
EYES8 = [("neutral", {}), ("blink", dict(blink=1.0)), ("wide", dict(wide=1.0)), ("narrowed", dict(narrow=1.0)), ("look left", dict(gaze_x=-1.0)), ("look right", dict(gaze_x=1.0)), ("look up", dict(gaze_y=1.0)),
         ("look down", dict(gaze_y=-1.0))]
BROWS6 = [("neutral", {}), ("raised", dict(brow_raise=1.0)), ("worried", dict(brow_raise=0.4, brow_tilt=1.0)), ("angry", dict(brow_raise=-0.8, brow_tilt=-1.0)), ("confused", dict(brow_raise=0.3, brow_asym=0.9)),
          ("sad", dict(brow_raise=-0.2, brow_tilt=1.0))]


def _hold(perf, t0, t1, **vals):
    for nm, v in vals.items():
        ch = perf.ch[nm]
        ch.key(t0 - 0.001, ch(t0), "linear")
        ch.key(t0, v, "linear")
        ch.key(t1 - 0.01, v, "linear")


def _reset_face(perf, t):
    for nm in M.FACE_CH:
        ch = perf.ch[nm]
        ch.key(t - 0.001, ch(t), "linear")
        ch.key(t, 0.0, "linear")


def face_expression_test(log=print, w=1280, h=720):
    fps = 30
    dn = [dna2.make("face1", "young_man", {"wardrobe.accessories": [], "glasses": "* None"}), dna2.make("face2", "middle_aged_woman", {"wardrobe.accessories": ["earrings"]})]
    actors = [make_actor("L", dn[0], "front", 1, (0.0, GROUND)), make_actor("R", dn[1], "front", 1, (330.0, GROUND))]
    timeline = []
    t = 0.3
    for e in EMOTIONS11:
        for a in actors:
            _reset_face(a.perf, t)
            M.perform(a.perf, "face", t, 1.0, "neutral", 0.5, name=e)
        timeline.append((t, "emotion: " + e))
        t += 1.1
    for a in actors:
        _reset_face(a.perf, t)
    for v in VISEMES:
        for a in actors:
            _reset_face(a.perf, t)
            _hold(a.perf, t, t + 0.6, **{("vis_" + v): 1.0, "mouth_open": {"A": .62, "E": .32, "I": .22, "O": .55, "U": .36, "shocked": 1.0}[v]})
        timeline.append((t, "mouth viseme: " + v))
        t += 0.62
    for nm, vals in MOUTHS:
        for a in actors:
            _reset_face(a.perf, t)
            if vals:
                _hold(a.perf, t, t + 0.6, **vals)
        timeline.append((t, "mouth: " + nm))
        t += 0.62
    for nm, vals in EYES8:
        for a in actors:
            _reset_face(a.perf, t)
            if vals:
                _hold(a.perf, t, t + 0.6, **vals)
        timeline.append((t, "eyes: " + nm))
        t += 0.62
    for nm, vals in BROWS6:
        for a in actors:
            _reset_face(a.perf, t)
            if vals:
                _hold(a.perf, t, t + 0.6, **vals)
        timeline.append((t, "eyebrows: " + nm))
        t += 0.62
    dur = t + 0.3
    n = int(round(dur * fps))
    for a in actors:
        a.perf.no_blink.append((0, dur))
    cam = cams_const(n, 175.0, 610.0, 1.75 * w / 1280.0)
    path, rep = scene_video("face_expression_test", actors, dur, fps, w, h, cam, header=lambda tt: (("face system · " + [nm for s0, nm in timeline if s0 <= tt + 0.05][-1]) if tt >= 0.3 else "face system", None), log=log)
    json.dump(dict(emotions=EMOTIONS11, visemes=VISEMES, mouth_states=[m[0] for m in MOUTHS], eye_states=[e[0] for e in EYES8], brow_states=[b[0] for b in BROWS6], duration=dur,
                   characters=[d["id"] for d in dn], blender=rep["blender"]), open(os.path.join(OUT, "face_expression_test.json"), "w"), indent=1)
    return path


# ------------------------------------------------------------------------------------------------------------------ 5. eye gaze
def eye_gaze_test(log=print, w=1280, h=720):
    fps = 30
    dn_a = dna2.make("gaze", "office_worker", {"wardrobe.accessories": []})
    dn_b = dna2.make("gazeB", "middle_aged_woman", {"wardrobe.accessories": []})
    tg = {"PHONE": (520.0, 900.0), "DOOR": (1010.0, 700.0), "MONEY": (560.0, 1010.0), "SCREEN": (780.0, 480.0), "POINT": (330.0, 470.0), "PERSON_B": None}
    B = make_actor("B", dn_b, "three_quarter", -1, (900.0, GROUND))
    A = make_actor("A", dn_a, "three_quarter", 1, (150.0, GROUND))

    def res(tid, t):
        if tid == "PERSON_B":
            return B.anchor("head", t)
        return tg[tid]
    A.perf.resolver = res
    B.perf.resolver = res
    order = ["PHONE", "PERSON_B", "DOOR", "MONEY", "SCREEN", "POINT", "CAMERA", "PHONE"]
    t = 0.5
    marks = []
    for tid in order:
        M.perform(A.perf, "look_at", t, 1.6, "neutral", 0.6, target=tid, track=(tid == "PERSON_B"))
        if tid == "PERSON_B":
            M.perform(B.perf, "look_at", t + 0.3, 1.2, "neutral", 0.5, target="PERSON_A") if False else None
        marks.append((t, tid))
        t += 2.0
    dur = t + 0.5
    n = int(round(dur * fps))
    cam = cams_const(n, 560.0, 780.0, 1.0 * w / 1280.0)

    def extra(d, sx, sy, z, t_):
        cur = [tid for s0, tid in marks if s0 <= t_ + 0.1][-1] if t_ >= marks[0][0] else None
        for tid, p in tg.items():
            if p is None:
                continue
            col = (220, 40, 60) if tid == cur else (140, 145, 160)
            d.ellipse((sx(p[0]) - 16, sy(p[1]) - 16, sx(p[0]) + 16, sy(p[1]) + 16), outline=col, width=4)
            d.text((sx(p[0]) - 30, sy(p[1]) + 20), tid, fill=col, font=SH._font(22))
        d.rectangle((sx(950), sy(560), sx(1090), sy(GROUND)), outline=(120, 100, 80), width=4)
    path, rep = scene_video("eye_gaze_test", [A, B], dur, fps, w, h, cam, extra=extra, header=lambda tt: ("TARGET-BASED GAZE · look_at " + ([tid for s0, tid in marks if s0 <= tt + 0.1][-1] if tt >= 0.5 else "-"), None), log=log)
    ev = [dict(t=e[0], target=e[2]["target"], gx=round(e[2]["gx"], 3), gy=round(e[2]["gy"], 3), dx=round(e[2]["dx"], 1), dy=round(e[2]["dy"], 1)) for e in A.perf.events if e[1] == "gaze"]
    json.dump(dict(targets=order, gaze_events=ev, blender=rep["blender"]), open(os.path.join(OUT, "eye_gaze_test.json"), "w"), indent=1)
    return path


# ------------------------------------------------------------------------------------------------------------------ 6. hand poses
def hand_pose_test(log=print, w=1280, h=720):
    fps = 30
    dn = dna2.make("hands", "office_worker", {"wardrobe.top": "shirt", "wardrobe.accessories": ["watch"]})
    a = make_actor("H", dn, "front", 1, (0.0, GROUND))
    P = a.P
    p = a.perf
    ys = P["shoulder_joint_y"] - 120
    for side, x in (("L", 20.0), ("R", -20.0)):                                   # both hands lifted in front of the chest
        M.hand_to(p, side, 0.0, 0.5, (x, ys), "smooth")
    poses = M.motion_v2.HAND_POSES
    seq = []
    t = 0.7
    for pose in poses:
        M.motion_v2.set_pose(p, t, "R", pose)
        M.motion_v2.set_pose(p, t, "L", "open" if pose in ("open", "palm_up", "gesture") else pose)
        for nm, val in (("phone_vis", pose == "hold_phone"), ("card_vis", pose == "hold_card"), ("money_vis", pose == "hold_money")):
            ch = p.ch[nm]
            ch.key(t - 0.001, ch(t), "linear")
            ch.key(t, 1.0 if val else 0.0, "linear")
        ch = p.ch["fingers_vis"]
        ch.key(t - 0.001, ch(t), "linear")
        ch.key(t, 1.0 if pose in ("hold_phone", "hold_card", "hold_money") else 0.0, "linear")
        seq.append((t, pose))
        t += 1.3
    dur = t + 0.3
    n = int(round(dur * fps))
    cam = cams_const(n, 0.0, 800.0, 2.1 * w / 1280.0)
    path, rep = scene_video("hand_pose_test", [a], dur, fps, w, h, cam, header=lambda tt: ("10 reusable hand poses on the wrist bone · " + ([nm for s0, nm in seq if s0 <= tt + 0.05][-1] if tt >= 0.7 else "rest"), None), log=log)
    json.dump(dict(poses=poses, duration=dur, blender=rep["blender"]), open(os.path.join(OUT, "hand_pose_test.json"), "w"), indent=1)
    return path


# ------------------------------------------------------------------------------------------------------------------ 7. one identity, three views
def same_identity_views(log=print, w=1600, h=900):
    fps = 30
    d2 = dna2.make("views", "young_woman", {"wardrobe.top": "kurta", "wardrobe.bottom": "salwar", "wardrobe.shoes": "sandals", "wardrobe.palette": "rust", "wardrobe.accessories": ["earrings", "bag"]})
    acts = []
    for i, (view, facing) in enumerate([("profile", 1), ("three_quarter", 1), ("three_quarter", -1), ("front", 1)]):
        a = make_actor(f"v{i}", d2, view, facing, (300.0 + 480 * i, GROUND))
        M.perform(a.perf, "idle", 0.2, 6.0)
        M.perform(a.perf, "gesture", 1.0, 3.0, "confident", 0.6)
        M.set_face(a.perf, 0.5, "smile", 0.3)
        M.set_face(a.perf, 3.6, "worried", 0.4)
        acts.append(a)
    dur = 7.0
    n = int(round(dur * fps))
    cam = cams_const(n, 1000.0, 1010.0, w / 2100.0)
    names = ["PROFILE", "3/4 RIGHT", "3/4 LEFT", "FRONT"]

    def extra(d, sx, sy, z, t):
        for i, nm in enumerate(names):
            d.text((sx(300 + 480 * i - 60), sy(GROUND + 26)), nm, fill=(40, 40, 50), font=SH._font(26))
    path, rep = scene_video("same_identity_views", acts, dur, fps, w, h, cam, extra=extra, header=lambda t: (f"ONE CharacterDNA ({d2['id']}) in profile / 3-4 right / 3-4 left / front · same rig, same parts family", None), log=log)
    return path


# ------------------------------------------------------------------------------------------------------------------ 8. crowd v2
def crowd_v2(n=42, log=print, w=1920, h=1080, seconds=6.0):
    fps = 24
    r = random.Random("crowd2")
    cols, rows = 9, math.ceil(n / 9)
    actors = []
    for i in range(n):
        d2 = factory_dna(i + 100, "crowd2")
        d2["body"]["height"] = round(d2["body"]["height"] * r.uniform(0.9, 1.0), 3)
        row, col = i // cols, i % cols
        view = r.choice(["profile", "three_quarter", "three_quarter", "front"])
        a = make_actor(f"p{i:02d}", d2, view, r.choice([1, -1]), (300.0 + col * 380 + r.uniform(-70, 70) + (row % 2) * 170, 1180.0 + row * 300), hand_set="basic",
                       resolver=lambda tid, t: (0.0, 0.0))
        kind = r.choice(["walk", "walk", "idle", "talk", "phone", "point", "wave"]) if view != "front" else r.choice(["idle", "talk", "wave", "phone"])
        p = a.perf
        M.set_face(p, 0.1, r.choice(["neutral", "smile", "curious", "worried", "relief", "determination"]), 0.2)
        if kind == "walk":
            M.perform(p, "walk", 0.2, seconds - 0.4, "neutral", r.uniform(0.3, 0.8), speed=r.uniform(120, 230))
        elif kind == "phone":
            M.perform(p, "grab", 0.2, 0.1, prop="phone")
            M.perform(p, "hold_phone", 0.3, 0.9, "neutral", 0.5, pos=r.choice(["chest", "ear"]))
            M.perform(p, "read_phone", 1.3, seconds - 1.6)
        elif kind == "point":
            M.perform(p, "point", 0.4, 1.5)
            M.perform(p, "gesture", 2.0, 3.0, "confident", 0.6)
        elif kind == "talk":
            M.perform(p, "talk", 0.2, seconds - 0.4)
            M.perform(p, "gesture", 0.2, seconds - 0.4, "confident", 0.5)
        elif kind == "wave":
            M.perform(p, "gesture", 0.2, seconds - 0.4, "confident", 0.9, hand="R")
        else:
            M.perform(p, "idle", 0.2, seconds - 0.4)
        a.kind = kind
        actors.append(a)
    actors.sort(key=lambda a: a.origin[1])
    dur = seconds
    nfr = int(round(dur * fps))
    cam = cams_const(nfr, 1650.0, 1075.0, w / 3560.0)

    def extra(d, sx, sy, z, t):
        return None
    finish(actors, fps, dur)
    work, rep = blender_frames(actors, cam, w, h, fps, "crowd_v2", 6, log=log)
    path = os.path.join(OUT, "crowd_test_v2.mp4")

    def frames():
        for i in range(nfr):
            img, d, sx, sy = studio_backdrop(w, h, i, 1650.0, 1075.0, w / 3560.0)
            img.alpha_composite(Image.open(os.path.join(work, "frames", f"e{i:05d}.png")).convert("RGBA"))
            d = ImageDraw.Draw(img)
            label(d, f"crowd test v2: {n} CharacterDNA v2 people · profile / 3-4 / front · varied height, wardrobe, accessories, hair, pose, orientation · one rig", w=w, size=26)
            yield img
    encode(frames(), w, h, fps, path)
    meta = [dict(id=a.spec["dna"]["id"], view=a.view, facing=a.facing, top=a.spec["dna"]["wardrobe"]["top"], bottom=a.spec["dna"]["wardrobe"]["bottom"], shoes=a.spec["dna"]["wardrobe"]["shoes"],
                 height=round(a.P["height"]), action=a.kind) for a in actors]
    json.dump(dict(n=n, unique_dna=len({m["id"] for m in meta}), views=sorted({m["view"] for m in meta}), tops=sorted({m["top"] for m in meta}), heights=len({m["height"] for m in meta}),
                   actions={k: sum(1 for m in meta if m["action"] == k) for k in {m["action"] for m in meta}}, objects=rep["objects"], blender=rep["blender"], characters=meta),
              open(os.path.join(OUT, "crowd_test_v2.json"), "w"), indent=1)
    return path
