"""CHARACTER LAB renderer: many characters / states rendered through the REAL production rig (Blender armature + IK + hand-pose swaps + face shape keys), one character per frame, onto a neutral
backdrop, then laid out as a contact sheet. Used by the asset-utilisation audit (combination lab, archetypes, face matrix, head turn, situation and prop tests).

    render_sheet(specs, out_png, cols=10, ...)  ->  [RGBA arrays]
spec = dict(label, dna (CharacterDNA v2), view ('front'|'three_quarter'|'profile'|'back'), start ('stand'|'sit'), channels (optional dict channel -> value or list of per-frame values),
            actions (optional [(t, action, kwargs)]) , t (time at which to sample, default 1.0), focus ('body'|'head'|'torso'), facing (1|-1))
"""
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from engine.environments import bedroom_wide as BW
from engine.skeleton import short, motion as M, motion_v2 as MV, parts_art2 as PA2
from engine.shorts.raster import ROOT

GAP = 3000.0
FOCUS = dict(body=(1010.0, 1.25), head=(0.0, 3.2), torso=(0.0, 2.0), wide=(1010.0, 0.9))


def _plan(specs, dur):
    chars, cast = {}, []
    for i, s in enumerate(specs):
        cid = f"c{i:03d}"
        chars[cid] = dict(name=s.get("label", cid), dna=s["dna"], facing=s.get("facing", 1), origin=[540.0 + GAP * i, BW.FLOOR_Y], view=s.get("view", "three_quarter"), hand_set="full",
                          start=s.get("start", "stand"), start_x=0.0)
        cast.append(cid)
    shots = [dict(id="S01", treatment="skeleton", t0=0.0, t1=dur, beats=[], segs=[], gp=[], transition_in="cut", sfx=[], phase="-", location="lab", purpose="lab",
                  camera=dict(target="stage", size="wide", move="hold"), lighting=dict(mood="neutral"), actions=[])]
    return dict(kind="skeleton_short", version=3, title="lab", story_id="lab", seed=3, fps=30, format=dict(w=1080, h=1920, name="9x16"), duration=dur, name="lab", environment=dict(family="bedroom_wide", variation=dict(palette=0), seed=0),
                characters=chars, cast_in_short=cast, narration=dict(segments=[], audio=None, tts="none", tempo=1.0), targets=dict(PHONE=[670.0, 1166.0], A_STOP=[830.0, BW.FLOOR_Y]), shots=shots, sfx=[],
                mood_track=[(0.0, dur, "dim")], rim=dict(moon=0.0), duration_range=[0, 99])


def render_specs(specs, workdir, samples=8, log=lambda *_: None, canvas=(1080, 1920), batch=10, return_meta=False):
    """-> list of RGBA uint8 arrays (canvas size), one per spec, in order. Characters are far apart; the camera of frame i looks at character i only."""
    out, meta = [], []
    for b0 in range(0, len(specs), batch):
        chunk = specs[b0:b0 + batch]
        n = len(chunk)
        dur = max(n / 30.0 + 0.2, max((s.get("t", 1.0) for s in chunk)) + 0.5)
        n_frames = int(round(dur * 30))
        plan = _plan(chunk, dur)
        for i, s in enumerate(chunk):
            cid = f"c{i:03d}"
            for (t, act, kw) in s.get("actions", []):
                plan["shots"][0]["actions"].append(dict(char=cid, action=act, t=t, **kw))
        actors = short.build_actors(plan, log)
        for i, s in enumerate(chunk):
            a = actors[f"c{i:03d}"]
            if s.get("setup"):                                           # custom performance: setup(actor) may key any channel; the channels are then re-sampled
                s["setup"](a)
                a.channels = M.sample(a.perf, 30, 0.0, dur)
                short._clamp_reach(a, 30)
            for ch, v in (s.get("channels") or {}).items():
                arr = a.channels[ch]
                a.channels[ch] = list(v) if isinstance(v, (list, tuple, np.ndarray)) else [v] * len(arr)
        # camera: frame i = the sample time of character i, centred on it
        cx, cy, zm = np.zeros(n_frames), np.zeros(n_frames), np.ones(n_frames)
        frame_of = []
        for i, s in enumerate(chunk):
            f = int(round(s.get("t", 1.0) * 30))
            frame_of.append(f)
        # each character is rendered at ITS frame; the camera track must therefore follow the character whose frame it is
        used = {}
        for i, f in enumerate(frame_of):
            while f in used:
                f += 1
            used[f] = i
            frame_of[i] = f
        for f in range(n_frames):
            i = used.get(f)
            if i is None:
                cx[f], cy[f], zm[f] = 540.0, 1010.0, 1.0
                continue
            fk = chunk[i].get("focus", "body")
            act = actors[f"c{i:03d}"]
            tt = f / 30.0
            hx, hy = act.anchor("head", tt)
            if fk == "head":
                cx_, cy_, fz = hx, hy + 10, FOCUS["head"][1]
            elif fk == "torso":
                cx_, cy_ = act.anchor("chest", tt)
                fz = FOCUS["torso"][1]
            else:
                cx_, cy_, fz = 540.0 + GAP * i, FOCUS[fk][0], FOCUS[fk][1]
            cx[f], cy[f], zm[f] = cx_ + chunk[i].get("dx", 0.0), cy_, fz
        cam = dict(cx=cx, cy=cy, zoom=zm, gain=np.ones(n_frames), aperture=np.full(n_frames, 8.0), focus=np.full(n_frames, 1.6))
        wd = os.path.join(workdir, f"job_{b0:04d}")
        # rendering only the frames we need
        import engine.skeleton.short as S
        n0 = int(round(plan["duration"] * plan["fps"]))
        frames_dir, rep = S.render_actors(plan, actors, cam, wd, log, samples, only_frames=sorted(frame_of))
        for i, f in enumerate(frame_of):
            out.append(np.asarray(Image.open(os.path.join(frames_dir, f"a{f:05d}.png")).convert("RGBA")).copy())
            meta.append(dict(cx=float(cx[f]), cy=float(cy[f]), zoom=float(zm[f]), actor=actors[f"c{i:03d}"], t=f / 30.0))
    return (out, meta) if return_meta else out


def font(sz=14, bold=False):
    for p in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Helvetica.ttc"):
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def crop_char(rgba, pad=24):
    ys, xs = np.where(rgba[..., 3] > 8)
    if not len(xs):
        return rgba[:8, :8]
    return rgba[max(0, ys.min() - pad):ys.max() + pad, max(0, xs.min() - pad):xs.max() + pad]


def sheet(images, labels, out_png, cols=10, cell=(230, 470), bg=(238, 235, 228), title=None, crop=True, font_px=13):
    """images = RGBA arrays -> contact sheet PNG (each cell: cropped character on `bg`, label below)."""
    cw, ch = cell
    rows = (len(images) + cols - 1) // cols
    top = 44 if title else 0
    S = Image.new("RGB", (cols * cw, rows * ch + top), (30, 30, 34))
    d = ImageDraw.Draw(S)
    if title:
        d.text((10, 10), title, fill=(235, 235, 235), font=font(18, True))
    for i, im in enumerate(images):
        a = crop_char(im) if crop else im
        pil = Image.fromarray(a)
        pil.thumbnail((cw - 8, ch - 34))
        cellim = Image.new("RGBA", (cw - 4, ch - 4), bg + (255,))
        cellim.alpha_composite(pil, ((cellim.width - pil.width) // 2, max(2, cellim.height - 30 - pil.height)))
        x, y = (i % cols) * cw + 2, (i // cols) * ch + 2 + top
        S.paste(cellim.convert("RGB"), (x, y))
        d.text((x + 4, y + ch - 26), str(labels[i])[:34], fill=(20, 20, 20), font=font(font_px))
    S.save(out_png)
    return out_png


def render_states(dna, states, workdir, view="three_quarter", focus="head", samples=8, zoom=None, log=lambda *_: None, start="stand", atoms=None, action_t=None, gaze_mode="pupil"):
    """ONE character, N states (dict channel -> value) -> N RGBA frames. Used for the face matrix / head turn / pose tests. `atoms` = emotion names whose Open Peeps face atoms should be baked in."""
    n = len(states)
    if atoms:
        PA2.bake_face_atoms(dna, view, atoms)
    spec = dict(dna=dna, view=view, start=start)
    dur = n / 30.0 + 0.3
    plan = _plan([spec], dur)
    plan["gaze_mode"] = gaze_mode
    actors = short.build_actors(plan, log)
    a = actors["c000"]
    m = len(a.channels["root_x"])
    for ch in sorted({k for s in states for k in s}):
        base = list(a.channels[ch]) if ch in a.channels else [0.0] * m
        for i, s in enumerate(states):
            if ch in s:
                base[i] = s[ch]
        a.channels[ch] = base
    tt = 0.05
    hx, hy = a.anchor("head", tt)
    fz = zoom or {"head": 3.4, "torso": 2.0, "body": 1.25}[focus]
    cx = np.full(m, hx if focus == "head" else 540.0)
    cy = np.full(m, hy + 10 if focus == "head" else 1010.0)
    cam = dict(cx=cx, cy=cy, zoom=np.full(m, fz), gain=np.ones(m), aperture=np.full(m, 8.0), focus=np.full(m, 1.6))
    frames_dir, rep = short.render_actors(plan, actors, cam, workdir, log, samples, only_frames=list(range(n)))
    return [np.asarray(Image.open(os.path.join(frames_dir, f"a{f:05d}.png")).convert("RGBA")).copy() for f in range(n)]


def render_clip(chars, dur, workdir, cam="fixed", cam_xyz=(640.0, 1010.0, 1.05), follow="A", samples=8, log=lambda *_: None, targets=None, gaze_mode="pupil", atoms=None):
    """A short CLIP with named characters (ids 'A', 'D'): chars = {id: dict(dna, view, origin_x, facing, start, setup)}. `setup(actor, actors)` keys the performance. -> (frames RGBA list, actors, cam dict).
    cam 'follow': the camera tracks the hip of `follow`; 'fixed': constant (cx, cy, zoom)."""
    cast = {}
    for cid, s in chars.items():
        cast[cid] = dict(name=cid, dna=s["dna"], facing=s.get("facing", 1), origin=[s.get("origin_x", 380.0), BW.FLOOR_Y], view=s.get("view", "three_quarter"), hand_set="full", start=s.get("start", "stand"), start_x=0.0)
        if atoms:
            PA2.bake_face_atoms(s["dna"], s.get("view", "three_quarter"), atoms)
    n = int(round(dur * 30))
    tg = dict(PHONE=[670.0, 1166.0], A_STOP=[830.0, BW.FLOOR_Y], D_STOP=[1070.0, BW.FLOOR_Y], HANDOVER=[905.0, 860.0], DOOR=[960.0, 1000.0])
    tg.update(targets or {})
    shots = [dict(id="S01", treatment="skeleton", t0=0.0, t1=dur, beats=[], segs=[], gp=[], transition_in="cut", sfx=[], phase="-", location="lab", purpose="lab",
                  camera=dict(target="stage", size="wide", move="hold"), lighting=dict(mood="neutral"), actions=[])]
    plan = dict(kind="skeleton_short", version=3, title="clip", story_id="clip", seed=3, fps=30, format=dict(w=1080, h=1920, name="9x16"), duration=dur, name="clip", environment=dict(family="bedroom_wide", variation=dict(palette=0), seed=0),
                characters=cast, cast_in_short=list(cast), narration=dict(segments=[], audio=None, tts="none", tempo=1.0), targets=tg, shots=shots, sfx=[], mood_track=[(0.0, dur, "dim")], rim=dict(moon=0.0),
                duration_range=[0, 99], gaze_mode=gaze_mode)
    actors = short.build_actors(plan, log)
    for cid, s in chars.items():
        if s.get("setup"):
            s["setup"](actors[cid], actors)
    for a in actors.values():
        a.channels = M.sample(a.perf, 30, 0.0, dur)
        short._clamp_reach(a, 30)
    cx, cy, zm = np.zeros(n), np.zeros(n), np.ones(n)
    for f in range(n):
        if cam == "follow":
            hx, hy = actors[follow].anchor("hip", f / 30.0)
            cx[f], cy[f], zm[f] = hx + cam_xyz[0], cam_xyz[1], cam_xyz[2]
        else:
            cx[f], cy[f], zm[f] = cam_xyz
    camd = dict(cx=cx, cy=cy, zoom=zm, gain=np.ones(n), aperture=np.full(n, 8.0), focus=np.full(n, 1.6))
    frames_dir, rep = short.render_actors(plan, actors, camd, workdir, log, samples, only_frames=list(range(n)))
    frames = [np.asarray(Image.open(os.path.join(frames_dir, f"a{f:05d}.png")).convert("RGBA")).copy() for f in range(n)]
    return frames, actors, camd, rep
