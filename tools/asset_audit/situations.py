"""SITUATION COVERAGE: 31 situations through the production motion grammar + the generic prop primitive, rendered by the real rig into ONE evidence video, each clip labelled SUPPORTED / PARTIAL / MISSING
with the reason. Measured per clip: Blender IK error, planted-foot slide, whether the actions exist.  Props other than phone/card/money are TEST glyphs.
    PYTHONPATH=. .venv/bin/python tools/asset_audit/situations.py  -> output/tests/situation_coverage.mp4, docs/asset_audit/situation_coverage.json
"""
import json
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from engine.environments import bedroom_wide as BW   # noqa: E402
from engine.skeleton import lab, lab_dna as LD, motion as M, motion_v2 as MV, props4 as P4   # noqa: E402

OUT = os.path.join(ROOT, "output/tests")
WORK = os.path.join(OUT, "audit_work/situations")
DIMS = dict(atoms=["fear", "surprise", "worried", "dread"])
PROD = LD.production_characters()


def P(a, action, t, dur, emo="neutral", inten=0.6, **kw):
    return M.perform(a.perf, action, t, dur, emo, inten, **kw)


def prop_cycle(prop, t0=0.3, both=False, glyph=True):
    """setup fn: one interaction cycle; returns tracks for glyph drawing via the actor attribute `_props`."""
    def setup(a, actors):
        an = a.man["hand_anchors"]
        recs = P4.perform(a.perf, an, prop, t0, "R", False)
        if both:
            P4.perform(a.perf, an, prop, t0, "L", True)
        a._props = dict(prop=prop, recs=recs, an=an)
    return setup


# (label, status, note, chars-builder, duration, camera)
def S(label, status, note, build, dur=2.6, cam=("fixed", (640.0, 1010.0, 1.0)), rects=None, face_atom=None, targets=None):
    return dict(label=label, status=status, note=note, build=build, dur=dur, cam=cam, rects=rects or [], face_atom=face_atom, targets=targets)


def solo(setup, start="stand", origin=380.0, dna=None):
    return lambda: {"A": dict(dna=dna or PROD["A"], origin_x=origin, start=start, setup=setup)}


def duo(setup_a, setup_d, dna_d=None):
    return lambda: {"A": dict(dna=PROD["A"], origin_x=520.0, facing=1, setup=setup_a), "D": dict(dna=dna_d or PROD["B"], origin_x=880.0, facing=-1, setup=setup_d)}


def s_idle(a, ac):
    P(a, "idle", 0.0, 2.6)
    P(a, "look_ahead", 0.2, 1.0)


def s_sit(a, ac):
    P(a, "idle", 0.0, 2.6)
    P(a, "face", 0.3, 0.4, name="tired")


def s_walk(a, ac):
    P(a, "walk_to", 0.2, 2.2, target="A_STOP", stop_before=0.0, fill=True, stride_scale=0.8)


def s_run(a, ac):
    P(a, "run", 0.2, 1.7, speed_scale=0.55)                 # gait retargeted from the CC0 Creomoto run cycle (flight phase, arm drive, lean)


def s_reach(a, ac):
    P(a, "reach", 0.3, 1.4, target="PHONE", emo="hesitant", grip="hold_phone")


def s_bend(a, ac):
    pf = a.perf
    P_ = a.P
    for nm, v in (("pelvis_dy", -45.0 * P_["k"]), ("spine_rot", 36.0), ("chest_rot", 10.0), ("head_rot", -14.0)):
        pf.to(nm, 0.3, 1.2, pf.v(nm, 0.0) + v if nm == "pelvis_dy" else v, "smooth")
    M.hand_to(pf, "R", 0.4, 1.3, (pf.hip(0.0)[0] + 150 * P_["k"], 330 * P_["k"]), "smooth")
    M.hand_to(pf, "R", 1.8, 2.4, M._arm_rest(pf, "R", 2.4), "smooth")
    for nm in ("pelvis_dy", "spine_rot", "chest_rot", "head_rot"):
        pf.to(nm, 1.6, 2.5, 0.0 if nm != "pelvis_dy" else -9.0 * P_["k"], "smooth")


def s_turn(a, ac):
    P(a, "head_turn", 0.3, 1.0, direction=-1)
    P(a, "head_turn", 1.5, 1.0, direction=1)


def s_look(a, ac):
    P(a, "look_right", 0.2, 0.7)
    P(a, "look_left", 1.0, 0.7)
    P(a, "look_up", 1.8, 0.6)


def s_talk(a, ac):
    words = [dict(word=w, start=0.3 + 0.36 * i, end=0.3 + 0.36 * i + 0.3) for i, w in enumerate(["बेटा", "क्या", "हुआ", "तुम", "इतने", "घबराए", "क्यों", "हो"])]
    P(a, "speak", 0.3, 2.4, words=words)
    P(a, "gesture", 0.6, 1.8, hand="R", emo="hesitant")


def s_point(a, ac):
    P(a, "point", 0.4, 1.6, hand="R")
    P(a, "look_at", 0.3, 1.8, target="DOOR")


def s_hold_phone(a, ac):
    P(a, "reach", 0.1, 0.9, target="PHONE", grip="hold_phone")
    P(a, "grab", 1.05, 0.1, prop="phone", from_table=True)
    P(a, "hold_phone", 1.25, 1.2, pos="chest")


def s_read(a, ac):
    s_hold_phone(a, ac)
    P(a, "read_phone", 1.5, 1.1)


def s_sitdesk(a, ac):
    P(a, "idle", 0.0, 2.6)
    P4.perform(a.perf, a.man["hand_anchors"], "PEN", 0.2, "R", False)
    a._props = dict(prop="PEN", recs=[], an=a.man["hand_anchors"])
    P(a, "look_down", 0.2, 2.0)


def s_eat(a, ac):
    s_prop("FOOD")(a, ac)


def s_prop(prop, both=False, t0=0.2):
    def f(a, ac):
        an = a.man["hand_anchors"]
        recs = P4.perform(a.perf, an, prop, t0, "R", False)
        if both:
            P4.perform(a.perf, an, prop, t0, "L", True)
        a._props = dict(prop=prop, recs=recs, an=an)
        P(a, "look_down" if prop in ("LAPTOP", "KEYBOARD", "PEN") else "look_ahead", t0, 2.0)
    return f


def s_carry(a, ac):
    an = a.man["hand_anchors"]
    recs = P4.perform(a.perf, an, "BAG", 0.1, "R", False)
    a._props = dict(prop="BAG", recs=recs, an=an, carry=True)
    t_walk = 0.1 + 0.6 + 0.3 + 0.2 + 0.6                 # after HOLD
    P(a, "walk_to", t_walk, 1.6, target="A_STOP", stop_before=0.0, fill=True, stride_scale=0.8)
    pf = a.perf                                             # the carrying hand stays low at the bag handle while the legs walk
    P_ = a.P
    for i in range(int(1.6 * 30)):
        tt = t_walk + i / 30.0
        sh = pf.shoulder(tt)
        for nm, v in (("hand_R_x", sh[0] + 0.30 * (P_["upper_arm"] + P_["forearm"])), ("hand_R_y", sh[1] - 0.80 * (P_["upper_arm"] + P_["forearm"]))):
            MV._rekey(pf, nm, tt, v, "linear")


def s_handover_give(a, ac):
    P(a, "reach", 0.05, 0.6, target="PHONE", grip="hold_phone")
    P(a, "grab", 0.7, 0.1, prop="phone", from_table=True)
    P(a, "hold_phone", 0.85, 0.5, pos="chest")
    P(a, "hand_over", 1.4, 0.9, target="PERSON_D", point="HANDOVER", prop="phone", emo="hesitant")
    P(a, "release", 2.5, 0.4, prop="phone")


def s_handover_take(d, ac):
    P(d, "receive", 1.4, 1.2, point="HANDOVER", prop="phone", emo="hesitant")
    P(d, "hold_phone", 2.75, 0.6, pos="chest")


def s_recv_d(d, ac):                                 # D starts with the phone in her hand and gives it to A
    d.perf.ch["phone_vis"].key(0.0, 1.0, "linear")
    d.perf.ch["fingers_vis"].key(0.0, 1.0, "linear")
    MV.set_pose(d.perf, 0.0, "R", "hold_phone")
    P(d, "hold_phone", 0.0, 0.8, pos="chest")
    P(d, "hand_over", 1.0, 1.0, target="PERSON_A", point="HANDOVER", prop="phone", emo="hesitant")
    P(d, "release", 2.6, 0.4, prop="phone")


def s_recv_a(a, ac):
    P(a, "look_at", 0.2, 1.2, target="PHONE", track=True)
    P(a, "receive", 1.0, 1.2, point="HANDOVER", prop="phone", emo="hesitant")
    P(a, "hold_phone", 2.75, 0.6, pos="chest")


def s_listen(d, ac):
    P(d, "listen", 0.3, 2.3)
    P(d, "eye_contact", 0.3, 2.3, target="PERSON_A")


def s_talk2(a, ac):
    s_talk(a, ac)
    P(a, "eye_contact", 0.2, 2.4, target="PERSON_D")


def s_argue_a(a, ac):
    P(a, "anger", 0.2, 2.2, emo="angry", inten=0.9)
    P(a, "point", 0.6, 1.2, target="PERSON_D", hand="R", emo="angry", inten=0.9)
    P(a, "speak", 0.3, 2.2)


def s_argue_d(d, ac):
    P(d, "anger", 0.4, 2.0, emo="angry", inten=0.8)
    P(d, "gesture", 0.7, 1.6, hand="R", emo="angry", inten=0.8)
    P(d, "speak", 0.5, 2.0)


def s_emo(action, atom=None):
    def f(a, ac):
        P(a, "idle", 0.0, 2.6)
        P(a, action, 0.3, 1.7, emo="fearful" if action == "fear" else "shocked", inten=0.85)
        if atom:
            P(a, "face_atom", 0.55, 1.1, name=atom)
    return f


SITUATIONS = [
    S("SITTING", "SUPPORTED", "sit pose on the seat height of the set (a bench glyph is drawn)", solo(s_sit, "sit", 380.0), rects=[("bench", 250, 1230, 420, 40)]),
    S("STANDING", "SUPPORTED", "standing idle, breathing, gaze", solo(s_idle)),
    S("WALKING", "SUPPORTED", "planted-foot gait to a target", solo(s_walk), cam=("follow", (260.0, 1010.0, 1.0))),
    S("RUNNING", "PARTIAL", "run gait retargeted from the CC0 Creomoto cycle (flight phase); the torso/limb ART has no running lean / arm-swing drawings", solo(s_run), dur=2.1, cam=("follow", (300.0, 1010.0, 0.95))),
    S("REACHING", "SUPPORTED", "seated reach to the nightstand phone (the film geometry)", solo(s_reach, "sit", 380.0), rects=[("bench", 250, 1230, 420, 40), ("table", 640, 1166, 120, 60)]),
    S("BENDING", "PARTIAL", "spine/pelvis keys work, but the torso is ONE drawing: no bent-torso replacement art", solo(s_bend), dur=2.8),
    S("TURNING", "MISSING", "only an in-plane head tilt: the head is one drawing for every view, no body turn", solo(s_turn), dur=2.6),
    S("LOOKING", "SUPPORTED", "gaze + head (pupil moves inside the eye white)", solo(s_look)),
    S("TALKING", "SUPPORTED", "Hindi lip-sync from word timings + gesture", solo(s_talk), dur=3.0),
    S("POINTING", "SUPPORTED", "point at a target with gaze", solo(s_point), rects=[("door", 950, 800, 60, 700)], targets={"DOOR": [980.0, 1000.0]}),
    S("HOLDING PHONE", "SUPPORTED", "solved grip on real Open Peeps hand", solo(s_hold_phone, "sit", 380.0), dur=2.7, rects=[("bench", 250, 1230, 420, 40), ("table", 640, 1166, 120, 60)]),
    S("READING", "PARTIAL", "reading a PHONE works; reading a paper/book needs a document glyph + reading pose (DOCUMENT primitive below)", solo(s_read, "sit", 380.0), dur=3.0, rects=[("bench", 250, 1230, 420, 40), ("table", 640, 1166, 120, 60)]),
    S("TYPING", "PARTIAL", "hands/type pose solved on a keyboard glyph; no keyboard/desk art", solo(s_prop("KEYBOARD", True), "sit", 380.0), dur=3.2, rects=[("bench", 250, 1230, 420, 40), ("desk", 560, 1130, 320, 30)]),
    S("DRINKING", "PARTIAL", "cup interaction solved; no cup art, no head tilt/sip", solo(s_prop("CUP")), dur=3.2, rects=[("table", 620, 1110, 230, 30)]),
    S("EATING", "MISSING", "hand-to-mouth is solved, but there is no food art, no chewing / mouth animation", solo(s_eat), dur=3.2, rects=[("table", 620, 1110, 230, 30)]),
    S("CARRYING", "PARTIAL", "bag grip + walk with the carrying hand pinned; no bag-in-hand art beyond a strap accessory", solo(s_carry), dur=3.4, cam=("follow", (260.0, 1010.0, 1.0))),
    S("OPENING DOOR", "PARTIAL", "handle grab + pull solved; no door art in the skeleton sets, no door-swing", solo(s_prop("DOOR", t0=0.2)), dur=3.2, rects=[("door", 990, 700, 40, 800)]),
    S("SITTING AT DESK", "PARTIAL", "seated writing pose solved; the set has no desk/chair layers at this scale", solo(s_sitdesk, "sit", 380.0), dur=2.8, rects=[("bench", 250, 1230, 420, 40), ("desk", 560, 1160, 320, 30)]),
    S("USING LAPTOP", "PARTIAL", "two-hand type on a laptop glyph; no laptop art", solo(s_prop("LAPTOP", True, 0.2), "sit", 380.0), dur=3.2, rects=[("bench", 250, 1230, 420, 40), ("desk", 560, 1160, 340, 30)]),
    S("USING ATM", "PARTIAL", "fingertip-anchored keypad press solved; ATM art exists only in the atm_area set (bust scale)", solo(s_prop("ATM")), dur=3.2),
    S("HOLDING CARD", "PARTIAL", "grip solved; real 'hold_card' pose is procedural (not a harvested hand)", solo(s_prop("CARD")), dur=3.2),
    S("HOLDING MONEY", "PARTIAL", "grip solved; note art exists as a part", solo(s_prop("MONEY")), dur=3.2),
    S("HOLDING DOCUMENT", "PARTIAL", "pinch grip solved; no paper art", solo(s_prop("DOCUMENT")), dur=3.2),
    S("TALKING TO ANOTHER PERSON", "SUPPORTED", "two characters: speech + eye contact", duo(s_talk2, s_listen), dur=3.0, cam=("fixed", (700.0, 1010.0, 0.95))),
    S("RECEIVING OBJECT", "SUPPORTED", "phone hand-over, receiving side (the man receives from the woman)", duo(s_recv_a, s_recv_d), dur=3.6, cam=("fixed", (700.0, 1010.0, 0.95))),
    S("GIVING OBJECT", "SUPPORTED", "phone hand-over, giving side", duo(s_handover_give, s_handover_take), dur=3.6, cam=("fixed", (700.0, 1010.0, 0.95))),
    S("ARGUING", "PARTIAL", "anger, pointing, speech on both; no leaning-in / body turn", duo(s_argue_a, s_argue_d), dur=3.0, cam=("fixed", (700.0, 1010.0, 0.95))),
    S("SURPRISED", "SUPPORTED", "surprise sequence; peak frame swaps in the Open Peeps 'Awe' face atom", solo(s_emo("surprise", "surprise")), face_atom="surprise"),
    S("SCARED", "SUPPORTED", "fear sequence; peak frame swaps in the Open Peeps 'Fear' face atom", solo(s_emo("fear", "fear")), face_atom="fear"),
    S("CONFUSED", "SUPPORTED", "confusion sequence; peak frame swaps in the 'Concerned' face atom", solo(s_emo("confusion", "worried")), face_atom="worried"),
    S("REALIZATION", "SUPPORTED", "realization sequence; peak frame swaps in the 'Concerned Fear' face atom", solo(s_emo("realization", "dread")), face_atom="dread"),
]


def draw_rects(img, rects, cam, actors=None):
    d = ImageDraw.Draw(img)
    for kind, x, y, w, h in rects:
        sx, sy = (x - cam[0]) * cam[2] + 540, (y - cam[1]) * cam[2] + 960
        col = {"bench": (170, 140, 110), "table": (160, 130, 100), "desk": (150, 120, 90), "door": (150, 116, 80)}[kind]
        d.rectangle((sx, sy, sx + w * cam[2], sy + h * cam[2]), fill=col + (255,), outline=(30, 30, 34, 255), width=4)


def compose(frames, actors, camd, sit, banner_col):
    out = []
    n = len(frames)
    for f, fr in enumerate(frames):
        bg = Image.new("RGBA", (1080, 1920), (238, 235, 228, 255))
        d = ImageDraw.Draw(bg)
        cam = (float(camd["cx"][f]), float(camd["cy"][f]), float(camd["zoom"][f]))
        fy = (BW.FLOOR_Y - cam[1]) * cam[2] + 960
        d.rectangle((0, fy, 1080, 1920), fill=(214, 208, 196, 255))
        d.line((0, fy, 1080, fy), fill=(60, 60, 64, 255), width=4)
        draw_rects(bg, sit["rects"], cam)
        # prop glyphs
        for cid, a in actors.items():
            pr = getattr(a, "_props", None)
            if not pr:
                continue
            t = f / 30.0
            pdef = P4.PROPS[pr["prop"]]
            recs = pr["recs"]
            if not recs:
                continue
            contact = next(r for r in recs if r["phase"] == "CONTACT")["target"]
            use = next(r for r in recs if r["phase"] == "USE")["target"]
            t_grab = next(r for r in recs if r["phase"] == "GRAB")["t"]
            t_rel = next(r for r in recs if r["phase"] == "RELEASE")["t"]
            fixed = pr["prop"] in ("LAPTOP", "KEYBOARD", "ATM", "DOOR", "PEN")
            if fixed or t < t_grab:
                pos = contact
            elif t <= t_rel:
                pos, _ = P4.grip_point(a.perf, pr["an"], pdef["pose"], pdef["anchor"], t)
            else:
                pos = use
            if pr.get("carry"):
                pos, _ = P4.grip_point(a.perf, pr["an"], pdef["pose"], pdef["anchor"], t) if t >= t_grab else (contact, 0)
            g = P4.glyph(pr["prop"])
            wx, wy = a.rig_to_world(*pos)
            sx, sy = (wx - cam[0]) * cam[2] + 540, (wy - cam[1]) * cam[2] + 960
            gs = g.resize((int(g.width * cam[2] * 0.5), int(g.height * cam[2] * 0.5)))
            bg.alpha_composite(gs, (int(sx - gs.width / 2), int(sy - gs.height / 2)))
        bg.alpha_composite(Image.fromarray(fr))
        d = ImageDraw.Draw(bg)
        d.rectangle((0, 0, 1080, 190), fill=(24, 24, 28, 255))
        d.text((30, 20), sit["label"], fill=(255, 255, 255, 255), font=lab.font(60, True))
        d.rectangle((30, 100, 30 + 250, 150), fill=banner_col + (255,))
        d.text((44, 106), sit["status"], fill=(15, 15, 15, 255), font=lab.font(38, True))
        d.text((300, 112), (sit["note"][:70]), fill=(230, 230, 230, 255), font=lab.font(24))
        if len(sit["note"]) > 70:
            d.text((300, 142), sit["note"][70:140], fill=(230, 230, 230, 255), font=lab.font(24))
        out.append(np.asarray(bg.convert("RGB")))
    return out


def foot_slide(a, fps=30):
    """max flat-foot x drift while the foot is planted during walks (px) - 0 = perfectly planted"""
    worst = 0.0
    for e in a.perf.events:
        if e[1] != "walk":
            continue
        f0, f1 = int(e[0] * fps), min(int(e[2]["t1"] * fps), len(a.channels["root_x"]) - 1)
        for side in ("L", "R"):
            xs, ys = np.array(a.channels[f"foot_{side}_x"]), np.array(a.channels[f"foot_{side}_y"])
            run = []
            for f in range(f0, f1 + 1):
                if ys[f] <= a.P["foot_h"] + 1.0:
                    run.append(xs[f])
                elif run:
                    worst = max(worst, max(run) - min(run))
                    run = []
            if run:
                worst = max(worst, max(run) - min(run))
    return round(float(worst), 2)


def main():
    os.makedirs(WORK, exist_ok=True)
    col = {"SUPPORTED": (110, 210, 130), "PARTIAL": (240, 190, 80), "MISSING": (240, 110, 100)}
    rows = []
    only = {int(x) for x in os.environ.get("ONLY", "").split(",") if x}
    writer = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "1080x1920", "-r", "30", "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                               os.path.join(OUT, "situation_coverage.mp4")], stdin=subprocess.PIPE)
    for i, sit in enumerate(SITUATIONS):
        if only and (i + 1) not in only:
            continue
        chars = sit["build"]()
        cam_mode, cam_xyz = sit["cam"]
        try:
            frames, actors, camd, rep = lab.render_clip(chars, sit["dur"], os.path.join(WORK, f"clip_{i:02d}"), cam=cam_mode, cam_xyz=cam_xyz, atoms=DIMS["atoms"] if sit["face_atom"] else None, samples=6, targets=sit.get("targets"))
            ik = max([max(v for k, v in e.items() if k.startswith("IK")) for e in rep["ik_error_px"]] or [0.0])
            slide = max(foot_slide(a) for a in actors.values())
            err = None
        except Exception as e:                      # a situation the grammar cannot express is reported, not hidden
            import traceback
            traceback.print_exc()
            rows.append(dict(n=i + 1, label=sit["label"], status="MISSING", note=sit["note"], error=f"{type(e).__name__}: {e}"[:200]))
            continue
        declared = sit["status"]
        if ik > 10.0:                                # MEASURED evidence overrides the declared status
            sit = dict(sit, status="MISSING", note=f"{sit['note']}  [MEASURED: IK error {ik:.0f}px - the pose is not reachable]")
        elif ik > 2.5 and sit["status"] == "SUPPORTED":
            sit = dict(sit, status="PARTIAL", note=f"{sit['note']}  [MEASURED: IK error {ik:.1f}px]")
        if not only:
            img = compose(frames, actors, camd, sit, col[sit["status"]])
            for im in img:
                writer.stdin.write(im.tobytes())
            for _ in range(8):                          # a beat of hold between clips
                writer.stdin.write(img[-1].tobytes())
        rows.append(dict(n=i + 1, label=sit["label"], status=sit["status"], declared=declared, note=sit["note"], ik_max_error_px=round(float(ik), 2), flat_foot_slide_px=slide, frames=len(frames), face_atom=sit["face_atom"]))
        print(i + 1, sit["label"], sit["status"], "IK", round(float(ik), 2), "slide", slide, flush=True)
    writer.stdin.close()
    writer.wait()
    if only:
        return
    cnt = {k: sum(1 for r in rows if r["status"] == k) for k in ("SUPPORTED", "PARTIAL", "MISSING")}
    json.dump(dict(counts=cnt, situations=rows), open(os.path.join(ROOT, "docs/asset_audit/situation_coverage.json"), "w"), ensure_ascii=False, indent=1)
    print(cnt)


if __name__ == "__main__":
    main()
