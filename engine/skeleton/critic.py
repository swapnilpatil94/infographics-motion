"""THE CRITIC: reviews the film the system is about to make (and the film it made) and FIXES what it can. Nothing here is hand-tuned per story: every fix is a parameter keyed by beat id.

Three reviewers, in order of trust:
  1. MEASURED geometry (no rendering): where are the heads / feet / phone on screen at 3 moments of every shot; is anything clipped, is the face under the caption, is the face big enough.
     -> exact fixer: search camera (zoom_mul, dx, dy) that satisfies every constraint at every sample.
  2. MEASURED pixels (preview stills rendered by the real pipeline): face-region luminance, frame luminance, phone-screen text contrast, frame emptiness.
     -> fixers: fill light on the face, exposure, bloom off the screen.
  3. VLM review (local qwen3.5:9b on the stills): a second opinion in the viewer's terms ('is the face readable', 'is anything cut off'). ADVISORY: a VLM finding is auto-fixed only when a measurement
     agrees; the rest is reported as-is with the agreement rate (the VLM is noisy: see docs/TOPIC_SYSTEM.md).
Plan-level reviewer: rhythm (shot lengths, repeated framings, total duration, hook length).
`improve()` loops critique -> fix -> re-render stills up to N rounds and writes critique/{report.json, report.md, round_*.png, before_after.png}. `review_final()` samples the FINISHED mp4.
"""
import base64
import io
import json
import math
import os
import subprocess

import numpy as np
from PIL import Image, ImageDraw

from engine.shorts.layers import C0, H, W
from engine.skeleton import events as EVT, short
from engine.environments import bedroom_wide as BW

SAFE_X = (46.0, W - 46.0)
SAFE_Y = (110.0, 1830.0)
CAP_TOP = 1335.0                                       # captions sit at y~1440 (68 px, up to 2 lines): a face must end above this
MIN_HEAD_PX = dict(close=330.0, medium=230.0, two_reach=170.0, full=95.0, two=120.0, reveal=90.0, wide=0.0, wide2=0.0)
FACE_LUMA_MIN = 0.38
FRAME_LUMA_MIN = 0.16
TEXT_CONTRAST_MIN = 0.60
SAMPLES_U = (0.08, 0.5, 0.92)
SIZE_ORDER = ["close", "medium", "two_reach", "two", "full", "reveal", "wide"]


def size_fallback(sh, kinds):
    """no camera position satisfies the constraints at this shot size: a wider size (clipping) or a tighter one (face too small) does"""
    cur = sh["camera"]["size"]
    if cur in SIZE_ORDER and any(k.endswith("clipped_x") or k.endswith("out_y") for k in kinds):
        return dict(size=SIZE_ORDER[min(SIZE_ORDER.index(cur) + 1, len(SIZE_ORDER) - 1)], dx=0.0, dy=0.0)
    if cur in SIZE_ORDER and "face_too_small" in kinds:
        return dict(size=SIZE_ORDER[max(SIZE_ORDER.index(cur) - 1, 0)], dx=0.0, dy=0.0)
    return None
SET_X = (-150.0, 1230.0)                              # world x extent of the set's wall/floor layers (bedroom_wide / study_room): a frame edge beyond it shows the black void
OLLAMA = "http://localhost:11434/api/chat"
VLM = "qwen3.5:9b"


# ------------------------------------------------------------------------------------------------------------------ geometry (no rendering)
def _screen(cam, f, wx, wy, zoom_mul=1.0, dx=0.0, dy=0.0):
    z0 = 1.0 + (float(cam["zoom"][f]) * zoom_mul - 1.0) * float(cam["gain"][f])
    return (wx - float(cam["cx"][f]) - dx) * z0 + C0[0], (wy - float(cam["cy"][f]) - dy) * z0 + C0[1], z0


def _d_visible(actors, t, cid="D"):
    D = actors.get(cid)
    return D is not None and short.on_screen(D, t)


def subjects(sh, actors, t):
    tgt = (sh.get("camera") or {}).get("target", "stage")
    if "+" in tgt:
        ids = tgt.split("+")
        return [ids[0]] + [c for c in ids[1:] if _d_visible(actors, t, c)]
    if "." in tgt:
        return [tgt.split(".")[0]]
    return ["A"]


def required_points(sh, actors, t):
    """[(wx, wy, xlo, xhi, ylo, yhi, kind)] - world points that must land inside the given screen ranges at time t."""
    c = sh["camera"]
    size, tgt = c["size"], c["target"]
    pts = []
    for cid in subjects(sh, actors, t):
        a = actors[cid]
        hx, hy = a.anchor("head", t)
        r = 0.56 * a.P["head"]
        for ox, oy in ((-r, -r), (r, -r), (-r, r), (r, r)):
            pts.append((hx + ox, hy + oy, SAFE_X[0], SAFE_X[1], SAFE_Y[0], CAP_TOP, "head"))
        if size == "full" or tgt.endswith(".full"):
            rx, _ = a.rig_to_world(a.perf.v("root_x", t), 0.0)
            pts.append((rx, BW.FLOOR_Y + 8, SAFE_X[0], SAFE_X[1], SAFE_Y[0], SAFE_Y[1], "feet"))
    if tgt in ("A.reach", "A.phone") or size == "two_reach":
        for a_ in actors.values():
            if a_.perf.ch["phone_vis"](t) > 0.5:
                px, py = a_.anchor("phone", t)
                break
        else:
            px, py = BW.PHONE_POS
        pts.append((px, py, SAFE_X[0] + 60, SAFE_X[1] - 60, SAFE_Y[0], SAFE_Y[1] - 60, "phone"))
    return pts


def _interval(v_lo, v_hi):
    return (v_lo, v_hi) if v_lo <= v_hi else None


def solve_camera(sh, actors, cam, fps, cur_head_min, bounds=True):
    """Smallest camera change (zoom_mul m, dx, dy in world px) so every required point of every sample is inside its screen range and the head is big enough. -> dict | None (no solution)."""
    samples = []
    for u in SAMPLES_U:
        t = sh["t0"] + u * (sh["t1"] - sh["t0"])
        f = min(int(round(t * fps)), len(cam["cx"]) - 1)
        samples.append((t, f, required_points(sh, actors, t)))
    best = None
    for m in sorted(np.arange(0.55, 1.75, 0.02), key=lambda x: abs(math.log(x))):
        dxlo, dxhi, dylo, dyhi = -1e9, 1e9, -1e9, 1e9
        ok = True
        for t, f, pts in samples:
            z = 1.0 + (float(cam["zoom"][f]) * m - 1.0) * float(cam["gain"][f])
            for (wx, wy, xlo, xhi, ylo, yhi, kind) in pts:
                xlo, xhi, ylo, yhi = xlo + 16, xhi - 16, ylo + 16, yhi - 16                   # margin for the handheld shake
                # sx = (wx - cx - dx) * z + 540 in [xlo, xhi]  ->  dx in [(wx-cx) - (xhi-540)/z, (wx-cx) - (xlo-540)/z]
                dxlo = max(dxlo, (wx - float(cam["cx"][f])) - (xhi - C0[0]) / z)
                dxhi = min(dxhi, (wx - float(cam["cx"][f])) - (xlo - C0[0]) / z)
                dylo = max(dylo, (wy - float(cam["cy"][f])) - (yhi - C0[1]) / z)
                dyhi = min(dyhi, (wy - float(cam["cy"][f])) - (ylo - C0[1]) / z)
            if bounds:
                dxlo = max(dxlo, (SET_X[0] + C0[0] / z) - float(cam["cx"][f]) + 8.0)            # frame left edge inside the set:  cx + dx - 540/z >= SET_X0
                dxhi = min(dxhi, (SET_X[1] - C0[0] / z) - float(cam["cx"][f]) - 8.0)            # frame right edge inside the set: cx + dx + 540/z <= SET_X1
            heads = [p for p in pts if p[6] == "head"]
            if heads and MIN_HEAD_PX.get(sh["camera"]["size"], 0) > 0:
                span = max(p[1] for p in heads[:4]) - min(p[1] for p in heads[:4])
                if span * z < MIN_HEAD_PX[sh["camera"]["size"]]:
                    ok = False
        if not ok or dxlo > dxhi or dylo > dyhi:
            continue
        cur = sh["camera"]
        dx = min(max(0.0, dxlo), dxhi) if dxlo > 0 else max(min(0.0, dxhi), dxlo)      # the interval point closest to "no change"
        dy = min(max(0.0, dylo), dyhi) if dylo > 0 else max(min(0.0, dyhi), dylo)
        best = dict(zoom_mul=round(float(m), 3), dx=round(float(dx), 1), dy=round(float(dy), 1))
        break
    return best


def measure_geometry(plan, actors, cam):
    """-> [{shot, beat, act, ok, problems:[...], metrics}] for every skeleton shot with a camera (measured at 3 moments)."""
    fps = plan["fps"]
    rep = []
    for sh in plan["shots"]:
        if sh["treatment"] != "skeleton" or not sh.get("camera"):
            continue
        probs, met, warns = [], [], []
        for u in SAMPLES_U:
            t = sh["t0"] + u * (sh["t1"] - sh["t0"])
            f = min(int(round(t * fps)), len(cam["cx"]) - 1)
            for (wx, wy, xlo, xhi, ylo, yhi, kind) in required_points(sh, actors, t):
                sx, sy, z = _screen(cam, f, wx, wy)
                if sx < xlo - 1 or sx > xhi + 1:
                    probs.append(dict(kind=f"{kind}_clipped_x", u=u, sx=round(sx), limit=[xlo, xhi]))
                if sy < ylo - 1 or sy > yhi + 1:
                    probs.append(dict(kind=f"{kind}_out_y" if kind != "head" or sy < CAP_TOP else "face_under_caption", u=u, sy=round(sy), limit=[ylo, yhi]))
            zf = _screen(cam, f, 0.0, 0.0)[2]
            left, right = float(cam["cx"][f]) - C0[0] / zf, float(cam["cx"][f]) + C0[0] / zf
            if left < SET_X[0] or right > SET_X[1]:
                warns.append(dict(kind="frame_beyond_set", u=u, left=round(left), right=round(right), limit=list(SET_X)))
            cid = subjects(sh, actors, t)[0]
            hpx = 2 * 0.56 * actors[cid].P["head"] * (1.0 + (float(cam["zoom"][f]) - 1.0) * float(cam["gain"][f]))
            met.append(round(hpx))
            need = MIN_HEAD_PX.get(sh["camera"]["size"], 0)
            if need and hpx < need:
                probs.append(dict(kind="face_too_small", u=u, head_px=round(hpx), need=need))
        uniq = {}
        for p in probs:
            uniq.setdefault(p["kind"], p)
        rep.append(dict(shot=sh["id"], beat=sh.get("key", sh["beats"][0]), act=sh.get("act"), size=sh["camera"]["size"], target=sh["camera"]["target"], ok=not uniq, problems=list(uniq.values()), head_px=met,
                        warnings=list({w["kind"]: w for w in warns}.values())))
    return rep


# ------------------------------------------------------------------------------------------------------------------ pixels
def _luma(a):
    a = a[..., :3].astype(np.float32) / 255.0
    return 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]


def face_box(actors, cid, t, cam, f):
    a = actors[cid]
    hx, hy = a.anchor("head", t)
    sx, sy, z = _screen(cam, f, hx, hy)
    r = 0.5 * a.P["head"] * z
    return [int(max(0, sx - r)), int(max(0, sy - r)), int(min(W, sx + r)), int(min(H, sy + r))]


def measure_pixels(plan, still, actors, cam):
    """still = dict(path, t, f, shot). -> dict(face_luma, frame_luma, text_contrast, flags)."""
    im = np.asarray(Image.open(still["path"]).convert("RGB"))
    L = _luma(im)
    sh = next(s for s in plan["shots"] if s["id"] == still["shot"])
    out = dict(shot=sh["id"], t=still["t"], treatment=sh["treatment"], frame_luma=round(float(L.mean()), 3), flags=[])
    if sh["treatment"] == "skeleton":
        cid = subjects(sh, actors, still["t"])[0]
        fb = face_box(actors, cid, still["t"], cam, still["f"])
        if fb[2] - fb[0] > 20 and fb[3] - fb[1] > 20:
            fl = float(L[fb[1]:fb[3], fb[0]:fb[2]].mean())
            out["face_luma"] = round(fl, 3)
            out["face_box"] = fb
            if fl < FACE_LUMA_MIN:
                out["flags"].append("face_too_dark")
        if out["frame_luma"] < FRAME_LUMA_MIN:
            out["flags"].append("frame_too_dark")
    elif sh["treatment"] == "insert_ui":
        box = L[520:1150, 200:880]
        c = float((np.median(box) - np.percentile(box, 3)) / max(float(np.median(box)), 1e-3))
        out["text_contrast"] = round(c, 3)
        if c < TEXT_CONTRAST_MIN:
            out["flags"].append("screen_text_low_contrast")
    return out


# ------------------------------------------------------------------------------------------------------------------ VLM
VLM_SCHEMA = {"type": "object", "properties": {
    "subject_fully_visible": {"type": "boolean"}, "face_readable": {"type": "boolean"}, "too_dark": {"type": "boolean"}, "text_legible": {"type": "boolean"}, "cluttered": {"type": "boolean"},
    "issues": {"type": "array", "items": {"type": "string"}, "maxItems": 4}, "score": {"type": "integer", "minimum": 1, "maximum": 10}},
    "required": ["subject_fully_visible", "face_readable", "too_dark", "text_legible", "cluttered", "issues", "score"]}


def vlm_available():
    try:
        import urllib.request
        tags = json.load(urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2))
        return any(m["name"].startswith(VLM.split(":")[0]) for m in tags["models"])
    except Exception:
        return False


def vlm_review(path, intent, timeout=180):
    """One still -> dict (VLM_SCHEMA) or dict(error). The image is downscaled to 540x960."""
    import urllib.request
    im = Image.open(path).convert("RGB").resize((540, 960))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=88)
    prompt = (f"You are a strict film-quality reviewer of a vertical 2D animated short frame. Intent of this shot: {intent}. Judge ONLY what is visible. "
              "subject_fully_visible: the main character's head and face are fully inside the frame, not cut off by an edge. face_readable: the face is large and lit enough to read the expression. too_dark: the frame is too dark to see the "
              "characters clearly. text_legible: any phone-screen or caption text is easy to read (true if there is no such text). cluttered: characters or objects overlap confusingly. issues: up to 4 short concrete problems. score 1-10.")
    prompt += ' Reply with ONLY a JSON object with exactly these keys: subject_fully_visible, face_readable, too_dark, text_legible, cluttered (booleans), issues (array of up to 4 short strings), score (integer 1-10).'
    body = {"model": VLM, "stream": False, "think": False, "options": {"temperature": 0.0, "seed": 7, "num_ctx": 4096},
            "messages": [{"role": "user", "content": prompt, "images": [base64.b64encode(buf.getvalue()).decode()]}]}
    try:
        req = urllib.request.Request(OLLAMA, json.dumps(body).encode(), {"Content-Type": "application/json"})
        txt = json.load(urllib.request.urlopen(req, timeout=timeout))["message"]["content"]
        a_, b_ = txt.find("{"), txt.rfind("}")
        d = json.loads(txt[a_:b_ + 1])
        return {k: d[k] for k in VLM_SCHEMA["required"]}
    except Exception as e:
        return dict(error=str(e)[:160])


# ------------------------------------------------------------------------------------------------------------------ plan-level (rhythm)
def review_rhythm(plan):
    f = []
    dur = plan["duration"]
    lo, hi = plan.get("duration_range", [45.0, 60.0])
    if not lo <= dur <= hi:
        f.append(dict(kind="duration_out_of_range", value=round(dur, 1), range=[lo, hi], fixable="re-pace (tempo)"))
    first = plan["shots"][0]
    if first["t1"] - first["t0"] > 4.5:
        f.append(dict(kind="slow_hook", value=round(first["t1"] - first["t0"], 1), fixable="rewrite the first beat shorter"))
    prev = None
    for sh in plan["shots"]:
        L = sh["t1"] - sh["t0"]
        if L < 0.9:
            f.append(dict(kind="shot_too_short", shot=sh["id"], value=round(L, 2), fixable="merge beats"))
        if L > 6.5:
            f.append(dict(kind="shot_too_long", shot=sh["id"], value=round(L, 2), fixable="split beat"))
        c = sh.get("camera")
        key = (c["target"], c["size"], c["move"]) if c else None
        if key and key == prev:
            f.append(dict(kind="repeated_framing", shot=sh["id"], target=key[0], size=key[1], move=key[2], fixable="camera move"))
        prev = key
    return f


def fix_rhythm(plan, findings, fixes):
    cyc = ["push", "isolate", "drift", "hold", "pull"]
    done = []
    for x in findings:
        if x["kind"] == "repeated_framing":
            sh = next(s for s in plan["shots"] if s["id"] == x["shot"])
            beat = sh.get("key", sh["beats"][0])
            cur = sh["camera"]["move"]
            new = cyc[(cyc.index(cur) + 2) % len(cyc)] if cur in cyc else "push"
            fixes.setdefault(beat, {}).setdefault("camera", {})["move"] = new
            done.append(dict(shot=x["shot"], fix=f"move {cur} -> {new}"))
    return done


# ------------------------------------------------------------------------------------------------------------------ the loop
def _merge(fixes, beat, key, val):
    d = fixes.setdefault(beat, {})
    if key == "camera":
        c = d.setdefault("camera", {})
        for k, v in val.items():
            if k in ("dx", "dy"):
                c[k] = round(c.get(k, 0.0) + v, 2)
            elif k == "zoom_mul":
                c[k] = round(c.get(k, 1.0) * v, 4)
            else:
                c[k] = v
    elif key == "lighting":
        d.setdefault("lighting", {}).update(val)
    elif key == "ui":
        d.setdefault("ui", {}).update(val)


def _stills_times(plan):
    return [round(sh["t0"] + 0.6 * (sh["t1"] - sh["t0"]), 2) for sh in plan["shots"]]


def sheet(paths, out, cols=10, w=216, marks=None):
    ims = [Image.open(p).convert("RGB").resize((w, int(w * 16 / 9))) for p in paths]
    h = int(w * 16 / 9)
    rows = (len(ims) + cols - 1) // cols
    S = Image.new("RGB", (cols * w, rows * h), (20, 20, 24))
    d = ImageDraw.Draw(S)
    for i, im in enumerate(ims):
        S.paste(im, ((i % cols) * w, (i // cols) * h))
        if marks and marks.get(i):
            d.rectangle(((i % cols) * w, (i // cols) * h, (i % cols) * w + w - 1, (i // cols) * h + h - 1), outline=(255, 90, 60), width=4)
    S.save(out)
    return out


def _run_vlm(plan, stills):
    out = {}
    for s in stills:
        sh = next(x for x in plan["shots"] if x["id"] == s["shot"])
        out[s["shot"]] = vlm_review(s["path"], sh.get("purpose", ""))
    return out


def improve(plan, story, nar, out_dir, rounds=3, log=print, samples=10, seed=11, use_vlm=True, builder=None):
    """Critique -> fix -> re-render loop. Returns dict(plan, fixes, summary)."""
    from engine.skeleton import auto_director as AD
    cdir = os.path.join(out_dir, "critique")
    os.makedirs(cdir, exist_ok=True)
    fixes = dict(story.get("fixes", {}))
    history = []
    vlm_ok = use_vlm and vlm_available()
    log(f"[critic] rounds<={rounds}  VLM={'on (' + VLM + ')' if vlm_ok else 'off'}")
    for r in range(rounds + 1):
        plan = (builder or AD.build_plan)(story, nar, seed=seed, tts=nar["tts"], name=story["slug"], fixes=fixes)
        times = _stills_times(plan)
        EVT.current().progress("scene_direction", fraction=0.15 + 0.8 * r / (rounds + 1), force=True, message=f"critic round {r + 1}/{rounds + 1}: rendering {len(times)} preview stills and measuring framing", current_operation="critic: preview stills (Blender) + measured framing")
        rd = os.path.join(cdir, f"round_{r}")
        R = short.render_stills(plan, rd, times, log, samples=samples)
        actors, cam = R["actors"], R["cam"]
        geo = measure_geometry(plan, actors, cam)
        stills = [dict(path=p, t=m["t"], f=m["f"], shot=m["shot"]) for p, m in zip(R["paths"], R["meta"])]
        pix = [measure_pixels(plan, s, actors, cam) for s in stills]
        rhythm = review_rhythm(plan)
        n_geo = sum(1 for g in geo if not g["ok"])
        n_pix = sum(len(p["flags"]) for p in pix)
        n_rh = len([x for x in rhythm if x["kind"] == "repeated_framing"])
        rec = dict(round=r, geometry_bad_shots=n_geo, pixel_flags=n_pix, repeated_framings=n_rh, geometry=geo, pixels=pix, rhythm=rhythm, vlm={}, applied=[], stills=stills, fixes_snapshot=json.loads(json.dumps(fixes)))
        gbad = {g["shot"] for g in geo if not g["ok"]}
        marks = {i: (s["shot"] in gbad) or bool(pix[i]["flags"]) for i, s in enumerate(stills)}
        rec["sheet"] = os.path.relpath(sheet(R["paths"], os.path.join(cdir, f"round_{r}_sheet.png"), marks=marks), out_dir)
        if r == 0 and vlm_ok:
            rec["vlm"] = _run_vlm(plan, stills)
        log(f"[critic] round {r}: geometry-bad shots={n_geo}  pixel flags={n_pix}  repeated framings={n_rh}")
        history.append(rec)
        n_warn = sum(1 for g in geo if g.get("warnings"))
        if r == rounds or (n_geo == 0 and n_pix == 0 and n_rh == 0 and (n_warn == 0 or r > 0 and history[-2].get("_warn", -1) == n_warn)):
            break
        rec["_warn"] = n_warn
        for g in geo:                                                                  # ---- fixers
            if g["ok"] and not g.get("warnings"):
                continue
            sh = next(s for s in plan["shots"] if s["id"] == g["shot"])
            sol = solve_camera(sh, actors, cam, plan["fps"], None)
            if sol is None and not g["ok"]:
                sol = solve_camera(sh, actors, cam, plan["fps"], None, bounds=False)      # no framing satisfies the set edges too: clipping the subject is worse than showing the void
            if sol:
                _merge(fixes, g["beat"], "camera", sol)
                rec["applied"].append(dict(shot=g["shot"], beat=g["beat"], problems=[p["kind"] for p in g["problems"]], fix=dict(camera=sol)))
            else:
                new = size_fallback(sh, [p["kind"] for p in g["problems"]])
                if new:
                    _merge(fixes, g["beat"], "camera", new)
                rec["applied"].append(dict(shot=g["shot"], beat=g["beat"], problems=[p["kind"] for p in g["problems"]], fix=dict(camera=new) if new else None, note="no camera satisfies every constraint: shot size changed" if new else "no camera satisfies every constraint"))
        for p in pix:
            sh = next(s for s in plan["shots"] if s["id"] == p["shot"])
            beat = sh.get("key", sh["beats"][0])
            if "face_too_dark" in p["flags"] or "frame_too_dark" in p["flags"]:
                lt = fixes.get(beat, {}).get("lighting", {})
                new = dict(fill=round(min(2.4, lt.get("fill", 0.0) + 0.7), 2), exposure_mul=round(min(1.6, lt.get("exposure_mul", 1.0) * 1.15), 3))
                _merge(fixes, beat, "lighting", new)
                rec["applied"].append(dict(shot=p["shot"], beat=beat, problems=p["flags"], fix=dict(lighting=new), face_luma=p.get("face_luma"), frame_luma=p["frame_luma"]))
            if "screen_text_low_contrast" in p["flags"]:
                cur = sh.get("ui", {}).get("bloom", 0.4)
                new = dict(bloom=round(max(0.0, cur - 0.25), 2))
                _merge(fixes, beat, "ui", new)
                rec["applied"].append(dict(shot=p["shot"], beat=beat, problems=p["flags"], fix=dict(ui=new), text_contrast=p.get("text_contrast")))
        rec["applied"] += [dict(fix=d, problems=["repeated_framing"]) for d in fix_rhythm(plan, rhythm, fixes)]
        if not any(a.get("fix") for a in rec["applied"]):
            log("[critic] nothing more the critic can fix automatically")
            break
    final = history[-1]
    if vlm_ok and final is not history[0]:
        final["vlm"] = _run_vlm(plan, final["stills"])
    ba = None
    if final is not history[0]:
        changed = [i for i, (a, b) in enumerate(zip(history[0]["stills"], final["stills"]))
                   if np.abs(np.asarray(Image.open(a["path"]).convert("L"), np.float32) - np.asarray(Image.open(b["path"]).convert("L"), np.float32)).mean() > 0.6]
        if changed:
            paths = [history[0]["stills"][i]["path"] for i in changed] + [final["stills"][i]["path"] for i in changed]
            ba = sheet(paths, os.path.join(cdir, "before_after.png"), cols=len(changed), w=max(90, min(200, 2400 // len(changed))))
    unres = [dict(shot=g["shot"], problems=[p["kind"] for p in g["problems"]]) for g in final["geometry"] if not g["ok"]] + [dict(shot=p["shot"], problems=p["flags"]) for p in final["pixels"] if p["flags"]]
    vlm_flags = [dict(shot=s, issues=v.get("issues", []), score=v.get("score")) for s, v in final["vlm"].items() if "score" in v and (v["score"] <= 6 or not v["subject_fully_visible"] or not v["face_readable"])]
    g0 = {g["shot"]: g for g in history[0]["geometry"]}
    agree = [(not g0[k]["ok"], not v.get("subject_fully_visible", True)) for k, v in history[0]["vlm"].items() if k in g0 and "score" in v]
    vlm_vs_measured = dict(shots_compared=len(agree), measured_clipped=sum(a for a, _ in agree), vlm_said_clipped=sum(b for _, b in agree), both=sum(a and b for a, b in agree),
                           vlm_missed=sum(a and not b for a, b in agree), vlm_false_alarm=sum(b and not a for a, b in agree)) if agree else None
    summary = dict(rounds_run=len(history) - 1, vlm_vs_measured_clipping=vlm_vs_measured, before=dict(geometry_bad_shots=history[0]["geometry_bad_shots"], pixel_flags=history[0]["pixel_flags"], repeated_framings=history[0]["repeated_framings"]),
                   after=dict(geometry_bad_shots=final["geometry_bad_shots"], pixel_flags=final["pixel_flags"], repeated_framings=final["repeated_framings"]),
                   unresolved_measured=unres, vlm_advisory=vlm_flags, vlm_mean_score_first=_mean_vlm(history[0]), vlm_mean_score_last=_mean_vlm(final),
                   before_after=os.path.relpath(ba, out_dir) if ba else None, fixes=fixes, rhythm_unfixable=[x for x in final["rhythm"] if x["kind"] != "repeated_framing"])
    for h in history:
        h.pop("stills", None)
    json.dump(dict(summary=summary, rounds=history), open(os.path.join(cdir, "report.json"), "w"), ensure_ascii=False, indent=1)
    write_md(summary, history, os.path.join(cdir, "report.md"))
    return dict(plan=plan, fixes=fixes, summary=summary)


def _round_paths(cdir, n, r):
    d = os.path.join(cdir, f"round_{r}")
    return sorted(os.path.join(d, f) for f in os.listdir(d) if f.startswith("still_"))


def _mean_vlm(rec):
    v = [x["score"] for x in rec["vlm"].values() if "score" in x]
    return round(float(np.mean(v)), 2) if v else None


def write_md(summary, history, path):
    L = ["# Critique report", "",
         f"Rounds run: {summary['rounds_run']}.  Measured problems before -> after: geometry-bad shots {summary['before']['geometry_bad_shots']} -> {summary['after']['geometry_bad_shots']}, "
         f"pixel flags {summary['before']['pixel_flags']} -> {summary['after']['pixel_flags']}, repeated framings {summary['before']['repeated_framings']} -> {summary['after']['repeated_framings']}.",
         f"VLM mean score (advisory): {summary['vlm_mean_score_first']} -> {summary['vlm_mean_score_last']}.", ""]
    for h in history:
        L += [f"## Round {h['round']}", f"geometry-bad shots: {h['geometry_bad_shots']}, pixel flags: {h['pixel_flags']}", ""]
        for a in h["applied"]:
            L.append(f"- {a.get('shot', '')} {a.get('problems', '')} -> {a.get('fix')} {a.get('note', '')}")
        L.append("")
    if summary["unresolved_measured"]:
        L += ["## Unresolved (measured)", *[f"- {u['shot']}: {u['problems']}" for u in summary["unresolved_measured"]], ""]
    if summary["vlm_advisory"]:
        L += ["## VLM advisory (not auto-fixed unless a measurement agreed)", *[f"- {v['shot']} score {v['score']}: {v['issues']}" for v in summary["vlm_advisory"]], ""]
    if summary["rhythm_unfixable"]:
        L += ["## Rhythm findings the critic cannot fix by itself", *[f"- {x}" for x in summary["rhythm_unfixable"]], ""]
    open(path, "w", encoding="utf-8").write("\n".join(L))


def review_final(plan, out_dir, log=print, use_vlm=True):
    """Sample the finished mp4 (one frame per shot at 60%) -> measured luminance + VLM. Writes critique/final_review.json + final_sheet.png. Advisory: nothing is changed after the final render."""
    cdir = os.path.join(out_dir, "critique", "final")
    os.makedirs(cdir, exist_ok=True)
    mp4 = os.path.join(out_dir, "final.mp4")
    res, paths = [], []
    vlm_ok = use_vlm and vlm_available()
    for sh in plan["shots"]:
        t = round(sh["t0"] + 0.6 * (sh["t1"] - sh["t0"]), 2)
        p = os.path.join(cdir, f"{sh['id']}.png")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t}", "-i", mp4, "-frames:v", "1", p], check=True)
        L = _luma(np.asarray(Image.open(p).convert("RGB")))
        r = dict(shot=sh["id"], t=t, frame_luma=round(float(L.mean()), 3))
        if vlm_ok:
            r["vlm"] = vlm_review(p, sh.get("purpose", ""))
        res.append(r)
        paths.append(p)
    sheet(paths, os.path.join(out_dir, "critique", "final_sheet.png"))
    sc = [r["vlm"]["score"] for r in res if "vlm" in r and "score" in r["vlm"]]
    out = dict(frames=res, vlm_mean_score=round(float(np.mean(sc)), 2) if sc else None, low_scoring=[dict(shot=r["shot"], score=r["vlm"]["score"], issues=r["vlm"].get("issues")) for r in res if "vlm" in r and r["vlm"].get("score", 10) <= 5])
    json.dump(out, open(os.path.join(out_dir, "critique", "final_review.json"), "w"), ensure_ascii=False, indent=1)
    log(f"[critic] final review: VLM mean {out['vlm_mean_score']}  low-scoring shots: {[x['shot'] for x in out['low_scoring']]}")
    return out
