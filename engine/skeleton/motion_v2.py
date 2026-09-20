"""MOTION GRAMMAR v2 - registered on top of engine/skeleton/motion.py (same `perform()` entry point, same channels).

The planner speaks INTENTION and semantic TARGET IDS; nothing here is a Blender rotation:
    {"action":"look_at","target":"PHONE"}  {"action":"reach","target":"PHONE","emotion":"hesitant","intensity":0.7}  {"action":"walk_to","target":"DOOR"}
    {"action":"hand_over","target":"PERSON_B"}  {"action":"speak","words":[...]}  {"action":"flinch"}  {"action":"anger"}  ...
Targets resolve through `perf.resolver(target_id, t) -> world (x, y)` (the scene registry: PHONE, PERSON_A/B, DOOR, TABLE, CHAIR, MONEY, SCREEN, CAMERA, ...).

Quality: idle = breathing + micro sway + weight shifts; walk = contact / passing / pelvis bob + sway / arm counter-swing / torso counter-rotation / head stabilisation;
reach = anticipation -> reach (overshoot) -> contact -> hold -> release; phone = gaze first, hand, grip pose, orientation, eye focus, head adjust.
"""
import math
import random

from engine.animation.grammar import _style
from engine.shorts.performance import ease
from engine.skeleton import motion as M
from engine.skeleton.parts_art2 import HAND_POSES
from engine.skeleton import hands3 as H3, rig_def as _R

POSE_ID = {n: i for i, n in enumerate(HAND_POSES)}
VISEME_OPEN = dict(A=0.62, E=0.32, I=0.22, O=0.55, U=0.36, shocked=1.0)
DEV_VOWELS = {"ा": "A", "आ": "A", "ि": "I", "ी": "I", "इ": "I", "ई": "I", "ु": "U", "ू": "U", "उ": "U", "ऊ": "U", "े": "E", "ै": "E", "ए": "E", "ऐ": "E",
              "ो": "O", "ौ": "O", "ओ": "O", "औ": "O", "अ": "A", "ं": "O", "ँ": "O"}


def set_pose(perf, t, side, pose):
    """Step to a hand pose (one of the 10 reusable poses) at time t."""
    ch = perf.ch[f"hand_{side}_pose_id"]
    cur, new = ch(t), float(POSE_ID[pose])
    if abs(cur - new) > 1e-6:
        ch.key(t - 0.001, cur, "linear")
        ch.key(t, new, "linear")
    perf.hand_pose[side] = pose


def _eye_world(perf, t):
    P = perf.P
    hx, hy = perf.hip(t)
    lean = math.radians(perf.v("spine_rot", t) + perf.v("chest_rot", t))
    base = (hx + (P["neck_top_y"] - P["hip_y"]) * math.sin(lean), hy + (P["neck_top_y"] - P["hip_y"]) * math.cos(lean))
    return (base[0] + P["head"] * 0.30 * (1.0 if P["view"] != "front" else 0.3), base[1] + P["head"] * 0.62)



# ---------------------------------------------------------------------------------------------------------------- prop grips (v3)
def _phone_wrist(perf, C, phone_abs_ccw, t):
    """Where must the WRIST be (and how must the hand turn) so that the phone held by the hold_phone hand drawing has its centre at C with the given absolute tilt
    (deg counter-clockwise from vertical, y up)? -> (wrist_xy, hand_rot_deg). The hand drawing fixes the phone's place in the hand frame (hands3.phone_anchor)."""
    lx, ly, th = H3.phone_anchor(perf.P)
    H = phone_abs_ccw + th                                                    # absolute hand angle (ccw from straight down)
    hr = math.radians(H)
    off = (lx * math.cos(hr) + ly * math.sin(hr), lx * math.sin(hr) - ly * math.cos(hr))
    wrist = (C[0] - off[0], C[1] - off[1])
    sh = perf.shoulder(t)
    _, _, a1, a2 = _R.two_bone(sh, wrist, perf.P["upper_arm"], perf.P["forearm"], -1)
    return wrist, H - a2 - _R.REST["wrist"]


def _rekey(perf, name, t, v, e="smooth"):
    """set a key at t REPLACING any existing key at the same instant (a duplicate would be ignored by Channel evaluation: the first one wins)"""
    ch = perf.ch[name]
    ch.keys = [k for k in ch.keys if abs(k[0] - t) > 1e-6]
    ch.key(t, v, e)


def _is_phone(target):
    if isinstance(target, str) and target.split(".")[0] == "PHONE":
        from engine.skeleton import props3
        props3.parse(target)                                                       # validates the grip name (KeyError on an unknown grip)
        return True
    return False


def gaze_toward(perf, t, dur, target, e="out_back", head=True, log=True):
    """TARGET-BASED gaze: eyes (and head) orient toward the target's bearing. Returns (gx, gy) applied."""
    P = perf.P
    if target == "CAMERA":
        tgt = None
    else:
        tgt = perf.target_rig(target, t + dur * 0.5)
    ex, ey = _eye_world(perf, t)
    if tgt is None:
        gx, gy, dx, dy = (0.22 if P["view"] == "profile" else 0.05), 0.0, 1.0, 0.0
        pitch = 0.0
    else:
        dx, dy = tgt[0] - ex, tgt[1] - ey
        gx = max(-1.0, min(1.0, dx / 300.0))
        gy = max(-1.0, min(1.0, dy / 210.0))
        pitch = max(-14.0, min(16.0, -math.degrees(math.atan2(dy, max(abs(dx), 80.0))) * 0.55))
        if dx < 0:                                           # target behind: look back over the shoulder
            gx, pitch = -1.0, pitch * 0.4 - 4.0
    d = min(dur, 0.5)
    gx0, gy0 = perf.v("gaze_x", t), perf.v("gaze_y", t)
    for nm, a0, a1 in (("gaze_x", gx0, gx), ("gaze_y", gy0, gy)):                     # anticipation (a tiny counter-move) -> fast saccade with overshoot -> settle
        ch = perf.ch[nm]
        ch.key(t, a0, "linear")
        ch.key(t + 0.05, a0 - (a1 - a0) * 0.08, "smooth")
        ch.key(t + 0.05 + 0.09, a1 + (a1 - a0) * 0.10, "out")
        ch.key(t + 0.05 + 0.09 + 0.16, a1, "smooth")
    if head:
        perf.to("head_rot", t + 0.07, t + d + 0.1, pitch, "smooth")
        perf.to("neck_rot", t + 0.07, t + d + 0.12, pitch * 0.35, "smooth")
    if log:
        perf.events.append((t, "gaze", dict(target=str(target), gx=gx, gy=gy, dx=dx, dy=dy)))
    return gx, gy


def a_look_at(perf, t, dur, st, target="PHONE", track=False, head=True, point=None, **kw):
    if point is not None and target == "PHONE":              # v1 compatibility: an explicit rig-space point
        tg = dict(rig=tuple(point))
    else:
        tg = target
    d = min(dur, 0.55) / st["speed"]
    gaze_toward(perf, t, d, tg, head=head)
    if track and dur > 0.6:
        n = int((dur - d) / 0.12)
        for i in range(n):
            tt = t + d + 0.12 * (i + 1)
            gaze_toward(perf, tt, 0.12, tg, e="linear", head=head, log=False)
    return t + d


def a_breathe(perf, t, dur, st, **kw):
    n = int(dur / 0.4) + 1
    for i in range(n):
        tt = t + i * 0.4
        b = math.sin(2 * math.pi * tt / 3.6 + perf.seed)
        perf.ch["chest_rot"].key(tt, perf.ch["chest_rot"](t) + 0.9 * b, "smooth")
        perf.ch["shrug"].key(tt, max(0.0, perf.ch["shrug"](t) + 0.05 * (b + 1)), "smooth")
    return t + dur


def a_idle(perf, t, dur, st, **kw):
    """Breathing + micro sway + occasional weight shift + slow head drift: a standing/sitting person is never frozen."""
    a_breathe(perf, t, dur, st)
    r = random.Random(perf.seed * 13 + int(t * 7))
    base_dx = perf.ch["pelvis_dx"](t)
    n = int(dur / 0.5) + 1
    shift = 0.0
    for i in range(n):
        tt = t + i * 0.5
        if i % 8 == 4:
            shift = r.choice([-1, 1]) * 7.0 * perf.P["k"] * st["amp"]                # weight shift
        sway = 2.2 * math.sin(2 * math.pi * tt / 7.0 + perf.seed)
        perf.ch["pelvis_dx"].key(tt, base_dx + shift + sway, "smooth")
        perf.ch["head_rot"].key(tt, perf.ch["head_rot"](t) + 0.8 * math.sin(2 * math.pi * tt / 5.3 + 1.1 * perf.seed), "smooth")
        perf.ch["hair_rot"].key(tt, 1.2 * math.sin(2 * math.pi * tt / 3.1), "smooth")
    return t + dur


def a_walk(perf, t, dur, st, speed=None, end_x=None, stride_scale=1.0, hold_R=False, hold_L=False, speed_scale=1.0, **kw):
    """Gait with contact / passing / weight shift. Stance feet are planted in the world; swing feet arc; the pelvis drops at contact and rises at passing while
    shifting sideways-forward over the stance leg; the spine counter-rotates and the head is stabilised against the torso; arms counter-swing (an arm holding a prop stays raised).
    `end_x` (rig x) makes the character arrive exactly there (WALK_TO)."""
    P = perf.P
    leg = P["thigh"] + P["shin"]
    v = (speed if speed is not None else 300.0 * P["k"]) * (0.85 + 0.3 * st["speed"] - 0.3) * (1.0 if st["speed"] >= 1.0 else st["speed"]) * speed_scale * perf.personality.get("speed", 1.0)
    Ls = 0.5 * leg * 0.98 * stride_scale
    T = 2 * Ls / max(v, 1.0)
    a = 0.6 * Ls
    ramp = min(0.4, dur * 0.3)
    x_start = perf.v("root_x", t)
    lift = 42.0 * P["k"] * st["amp"]
    bob = 22.0 * P["k"] * max(st["amp"], 0.7)                                        # the pelvis drops at contact so the leading leg can reach (and it is what a body does)
    hip_v = P["hip_y"] - P["foot_h"]
    a = min(a, 0.97 * math.sqrt(max(leg * leg - (hip_v - 0.5 * bob) ** 2, 1.0)))              # stride limited by what the leg can span with the pelvis at its lowest
    base_h = perf.v("pelvis_dy", t)
    fL0 = (perf.v("foot_L_x", t), perf.v("foot_L_y", t))
    fR0 = (perf.v("foot_R_x", t), perf.v("foot_R_y", t))
    so = perf.so
    stand_off = dict(L=-16.0 * P["k"] + so["hL"], R=24.0 * P["k"] + so["hR"])
    n = int(dur * 30)
    # ---- path of the root (eased speed profile), optionally scaled to arrive exactly at end_x
    prof, path, prev, x = [], [x_start], 0.0, x_start
    for i in range(n + 1):
        u = i / 30.0
        w = ease("smooth", max(0.0, min(1.0, u / ramp, (dur - u) / ramp))) if ramp > 0 else 1.0
        prof.append(w)
        sp = v * w
        if i:
            x += 0.5 * (sp + prev) / 30.0
            path.append(x)
        prev = sp
    scale = 1.0
    if end_x is not None and abs(path[-1] - x_start) > 1e-3:
        scale = (end_x - x_start) / (path[-1] - x_start)
    Ls = min(Ls, 0.6 * math.sqrt(leg / 416.0) * max(v * scale, 1.0))                                                 # a step never takes longer than ~0.6 s: slow walks get SHORT steps, not giant slow ones
    a = min(0.6 * Ls, 0.97 * math.sqrt(max(leg * leg - (P["hip_y"] - P["foot_h"] - 0.5 * bob) ** 2, 1.0)))
    T = 2 * Ls / max(v * scale, 1.0)                                                       # cadence follows the EFFECTIVE speed (the path may be scaled to arrive exactly at end_x)
    scale_w = 1.0

    def x_at(uu_):                                                                    # root x at walk time uu_ (extrapolated with the final speed beyond the walk)
        i_ = max(0.0, uu_) * 30.0
        if i_ >= n:
            return x_start + (path[n] - x_start) * scale
        lo = int(i_)
        fr = i_ - lo
        return x_start + ((path[lo] * (1 - fr) + path[min(lo + 1, n)] * fr) - x_start) * scale

    def plant(k, side, cyc):
        """world x where foot k touches down at the start of stance cycle `cyc`: `a` ahead of the pelvis at that instant."""
        u_c = max(0.0, (cyc - 0.5 * k) * T)
        wc = prof[min(n, int(round(min(u_c, dur) * 30)))]                                # small steps while starting / stopping, full steps at cruising speed
        return x_at(u_c) + a * wc * scale_w + stand_off[side]

    keys = {k: [] for k in ("root_x", "pelvis_dy", "pelvis_dx", "spine_rot", "head_rot", "neck_rot", "hair_rot", "foot_L_x", "foot_L_y", "foot_R_x", "foot_R_y", "foot_L_rot", "foot_R_rot",
                            "hand_L_x", "hand_L_y", "hand_R_x", "hand_R_y", "chest_rot")}
    for i in range(n + 1):
        tt = t + i / 30.0
        u = i / 30.0
        w = prof[i]
        x = x_start + (path[i] - x_start) * scale
        ph = (u / T) if T > 0 else 0.0
        sfoot = math.sin(2 * math.pi * ph)
        keys["root_x"].append((tt, x))
        keys["pelvis_dy"].append((tt, base_h - bob * w * (1 + math.cos(4 * math.pi * ph)) * 0.5))                       # lowest at contact (double support), highest at passing
        keys["pelvis_dx"].append((tt, 5.0 * P["k"] * w * math.sin(2 * math.pi * ph + 0.6)))                          # weight shift over the stance leg
        keys["spine_rot"].append((tt, 3.0 * st["lean"] * w + 2.4 * w * sfoot))
        keys["chest_rot"].append((tt, -2.4 * w * sfoot))                                                              # torso counter-rotation
        keys["head_rot"].append((tt, -0.8 * 2.4 * w * sfoot - 1.2 * w * math.sin(4 * math.pi * ph)))                  # head stabilised against the torso
        keys["neck_rot"].append((tt, 0.4 * w * math.sin(4 * math.pi * ph)))
        keys["hair_rot"].append((tt, 4.0 * w * math.sin(4 * math.pi * ph - 0.9)))
        wb = ease("smooth", min(1.0, u / max(ramp, 1e-3), (dur - u) / max(ramp, 1e-3))) if ramp > 0 else 1.0
        for k, side in enumerate(("L", "R")):
            phk = (ph + 0.5 * k) % 1.0
            cyc = int(math.floor(ph + 0.5 * k))
            if phk < 0.6:                                                        # STANCE: the foot is PLANTED at the contact position (no slide by construction)
                walk_x = plant(k, side, cyc)
                fy = P["foot_h"]
                if phk > 0.42:                                                   # push-off: the heel rises while the toe stays on the ground
                    fy += 16.0 * P["k"] * ((phk - 0.42) / 0.18) ** 1.4
                rot = (9.0 * (1 - phk / 0.15) if phk < 0.15 else 0.0) - (24.0 * ((phk - 0.45) / 0.15) if phk > 0.45 else 0.0)
            else:                                                                # SWING: from this plant to the next one, lifting over the ground
                uu = (phk - 0.6) / 0.4
                walk_x = plant(k, side, cyc) + (plant(k, side, cyc + 1) - plant(k, side, cyc)) * ease("smooth", uu)
                fy = P["foot_h"] + 16.0 * P["k"] * (1 - uu) ** 2 + lift * math.sin(math.pi * uu) ** 0.8                  # continuous with the push-off heel height, lands flat
                rot = -24.0 * (1 - uu) + 9.0 * uu
            f0 = fL0 if side == "L" else fR0
            sx = x + stand_off[side]
            keys[f"foot_{side}_x"].append((tt, (1 - wb) * (f0[0] if u < dur / 2 else sx) + wb * walk_x))
            keys[f"foot_{side}_y"].append((tt, (1 - wb) * P["foot_h"] + wb * fy + 0.5 * lift * math.sin(math.pi * wb) * (1.0 if wb < 0.999 else 0.0)))   # the first / last step lifts the foot
            keys[f"foot_{side}_rot"].append((tt, rot * wb))
        for k, side in enumerate(("L", "R")):
            holding = hold_R if side == "R" else hold_L
            sh_x = x + so["s" + side]
            if holding:
                sh_y = P["shoulder_joint_y"] + base_h
                keys[f"hand_{side}_x"].append((tt, sh_x + 118 * P["k"] + 3.0 * math.sin(4 * math.pi * ph)))
                keys[f"hand_{side}_y"].append((tt, sh_y - 150 * P["k"] + 5.0 * math.sin(4 * math.pi * ph)))
                continue
            phk = (ph + 0.5 * (1 - k)) % 1.0
            th = math.radians(10.0 + 26.0 * st["amp"] * w * math.sin(2 * math.pi * phk))
            r = (P["upper_arm"] + P["forearm"]) * (0.90 - 0.10 * abs(math.sin(2 * math.pi * phk)))
            shy = P["shoulder_joint_y"] + base_h - bob * w * 0.4
            hx, hy = sh_x + r * math.sin(th), shy - r * math.cos(th)
            rest = (sh_x + (P["upper_arm"] + P["forearm"]) * 0.93 * math.sin(math.radians(7)), P["shoulder_joint_y"] + base_h - (P["upper_arm"] + P["forearm"]) * 0.93 * math.cos(math.radians(7)))
            keys[f"hand_{side}_x"].append((tt, (1 - w) * (rest[0] if u < dur / 2 else rest[0]) + w * hx))
            keys[f"hand_{side}_y"].append((tt, (1 - w) * rest[1] + w * hy))
    for name, lst in keys.items():
        for tt, val in lst:
            perf.ch[name].key(tt, val, "linear")
    for side in ("L", "R"):
        if not (hold_R if side == "R" else hold_L):
            set_pose(perf, t + 0.05, side, "closed" if perf.hand_pose[side] not in ("hold_phone", "hold_card", "hold_money") else perf.hand_pose[side])
    perf.events.append((t, "walk", dict(t1=t + dur, x0=x_start, x1=x_start + (path[-1] - x_start) * scale, T=T)))
    return t + dur


def a_walk_to(perf, t, dur, st, target="DOOR", stop_before=120.0, speed=None, **kw):
    """Walk until `stop_before` rig-px short of the target (semantic destination), arriving exactly there."""
    tx, _ = perf.target_rig(target, t + dur)
    sgn = 1.0 if tx >= perf.v("root_x", t) else -1.0
    end_x = tx - sgn * stop_before
    dist = abs(end_x - perf.v("root_x", t))
    spd = speed or 210.0 * perf.P["k"]
    d = max(1.0, dist / (spd * 0.82))
    if kw.get("fill"):                                                               # the walk takes exactly the time the story gives it (a beat 'across the room' is not a 1-second shuffle)
        d = max(1.0, dur)
        spd = max(60.0, dist / (0.82 * d))
    a_walk(perf, t, d, st, speed=spd, end_x=end_x, **{k: v for k, v in kw.items() if k in ("stride_scale", "hold_R", "hold_L", "speed_scale")})
    perf.events.append((t, "walk_to", dict(target=str(target), end_x=end_x, dur=d)))
    return t + d


def a_reach(perf, t, dur, st, target=None, hand="R", grip=None, **kw):
    """anticipation (0.16 s pull-back + lean back) -> reach (eyes first, torso commits, overshoot) -> contact (slow-in, 0.12 s hold) -> grip pose. Returns the contact time.
    A phone target (`PHONE` or `PHONE.right_hand_grip`) is reached so that the real hand drawing closes ON the phone: wrist and wrist angle are solved from the hand's grip anchor."""
    P = perf.P
    contact_rot = None
    if _is_phone(target):
        C = perf.target_rig(target.split(".")[0], t + dur)
        tgt, contact_rot = _phone_wrist(perf, C, kw.get("phone_abs", -90.0), t + dur)
        grip_focus = C
    else:
        tgt = perf.target_rig(target, t + dur) if target is not None else (perf.hip(t)[0] + 240, P["hip_y"] * 0.7)
        if target is not None and isinstance(target, str) and target in ("CARD", "MONEY"):
            tgt = (tgt[0] - 18 * P["k"], tgt[1] + 36 * P["k"])                               # wrist target so the fingers close on the object
        grip_focus = None
    d = dur / st["speed"]
    arrive = t + d
    sh = perf.shoulder(t)
    reach_len = P["upper_arm"] + P["forearm"]
    dist = math.hypot(tgt[0] - sh[0], tgt[1] - sh[1])
    if dist > reach_len * 0.98:                                                          # out of the arm's envelope: reach as far as the body can, and say so
        f = reach_len * 0.98 / dist
        perf.events.append((arrive, "reach_clamped", dict(target=str(target), short_px=round(dist - reach_len * 0.98, 1))))
        tgt = (sh[0] + (tgt[0] - sh[0]) * f, sh[1] + (tgt[1] - sh[1]) * f)
        dist = reach_len * 0.98
    lean = max(0.0, min(26.0, (dist - reach_len * 0.7) / 6.0)) * st["amp"]
    gaze_toward(perf, t, 0.35, dict(rig=grip_focus) if grip_focus is not None else (dict(rig=(tgt[0] + 18 * P["k"], tgt[1] - 36 * P["k"])) if target in ("CARD", "MONEY") else dict(rig=tgt)))
    start = (perf.v(f"hand_{hand}_x", t), perf.v(f"hand_{hand}_y", t))
    ant = 0.16
    set_pose(perf, t, hand, "open")
    hand_to(perf, hand, t, t + ant, (start[0] - 14 * P["k"], start[1] + 8 * P["k"]), "smooth")                           # anticipation
    perf.to("spine_rot", t, t + ant, perf.v("spine_rot", t) - 3.0, "smooth")
    perf.to("spine_rot", t + ant, arrive, lean, "smooth")
    perf.to("head_rot", t + ant, arrive, -8.0 * st["amp"], "smooth")
    if st["hesitate"] > 0.3:
        mid = (start[0] + (tgt[0] - start[0]) * 0.55, start[1] + (tgt[1] - start[1]) * 0.55 + 22)
        t1 = t + ant + (d - ant) * 0.45
        hand_to(perf, hand, t + ant, t1, mid, "smooth")
        hand_to(perf, hand, t1 + 0.22 * st["hesitate"] * 1.4, arrive, tgt, "out_back")                                     # the doubt pause, then commit
        M._tremble(perf, t1, t1 + 0.3 * st["hesitate"] * 1.4, st["tremble"] * 2.2, (f"hand_{hand}_x", f"hand_{hand}_y"))
    else:
        hand_to(perf, hand, t + ant, arrive, tgt, "out_back")
    perf.to(f"hand_{hand}_rot", t, arrive, contact_rot if contact_rot is not None else -10.0, "smooth")
    if contact_rot is not None:                                                          # refine with the shoulder as it actually is at contact (the lean is keyed by now)
        tgt2, rot2 = _phone_wrist(perf, C, kw.get("phone_abs", -90.0), arrive)
        sh2 = perf.shoulder(arrive)
        d2 = math.hypot(tgt2[0] - sh2[0], tgt2[1] - sh2[1])
        if d2 > reach_len * 0.98:                                                        # still out of the arm's envelope after the refinement: stay reachable
            f2 = reach_len * 0.98 / d2
            tgt2 = (sh2[0] + (tgt2[0] - sh2[0]) * f2, sh2[1] + (tgt2[1] - sh2[1]) * f2)
        for nm, v in ((f"hand_{hand}_x", tgt2[0]), (f"hand_{hand}_y", tgt2[1]), (f"hand_{hand}_rot", rot2)):
            _rekey(perf, nm, arrive, v)
        perf.events.append((arrive, "phone_contact", dict(centre=[round(C[0], 2), round(C[1], 2)], hand=hand, phone_abs=kw.get("phone_abs", -90.0))))
    if grip:
        set_pose(perf, arrive - 0.03, hand, "hold_phone" if (contact_rot is not None and grip == "grab") else grip)
    perf.events.append((arrive, "contact", dict(target=str(target), hand=hand)))
    return arrive


def hand_to(perf, side, t0, t1, target, e="smooth"):
    perf.to(f"hand_{side}_x", t0, t1, target[0], e)
    perf.to(f"hand_{side}_y", t0, t1, target[1], e)


HELD_VIS = ("phone_vis", "card_vis", "money_vis", "document_vis", "cup_vis", "bag_vis")


def a_grab(perf, t, dur, st, hand="R", prop="phone", **kw):
    """Close the fingers over the object: grip pose, prop attaches to the hand, screen glow (phone). Emits the pick-up event."""
    pose = {"phone": "hold_phone", "card": "hold_card", "money": "hold_money", "document": "pinch", "cup": "hold_cup", "bag": "grab"}.get(prop, "grab")
    set_pose(perf, t, hand, pose)
    for nm in HELD_VIS:
        perf.ch[nm].key(t - 0.001, perf.ch[nm](t), "linear")
        perf.ch[nm].key(t, 1.0 if nm == prop + "_vis" else 0.0, "linear")
    perf.ch["fingers_vis"].key(t - 0.001, 0.0, "linear")
    perf.ch["fingers_vis"].key(t + 0.06, 1.0, "linear")
    if kw.get("from_table") and prop == "phone":                                   # lifted off the table: starts as a thin slab seen from the side, turns face-on in ~0.9 s
        perf.ch["phone_flat"].key(t - 0.001, 0.0, "linear")
        perf.ch["phone_flat"].key(t, 1.0, "linear")
        perf.ch["phone_flat"].key(t + 0.45, 1.0, "linear")
        perf.ch["phone_flat"].key(t + 0.95, 0.0, "smooth")
    if prop == "phone":
        perf.to("phone_glow", t, t + 0.4, 1.0, "out")
    perf.events.append((t, "phone_grab" if prop == "phone" else f"{prop}_grab", dict(hand=hand)))
    return t + 0.1


def a_hold(perf, t, dur, st, hand="R", **kw):
    """Keep the grip: tiny tremor + breathing follow-through so the held object is never dead still."""
    M._tremble(perf, t, t + dur, 0.12 + 0.3 * st["tremble"], (f"hand_{hand}_x", f"hand_{hand}_y"), hz=6.0)
    return t + dur


def a_release(perf, t, dur, st, hand="R", prop="phone", **kw):
    """Open the hand, the prop leaves it (visibility off; the scene places the free prop via the event)."""
    set_pose(perf, t, hand, "open")
    set_pose(perf, t + 0.45, hand, "relaxed")
    perf.ch[prop + "_vis"].key(t - 0.001, perf.ch[prop + "_vis"](t), "linear")
    perf.ch[prop + "_vis"].key(t + 0.05, 0.0, "linear")
    perf.ch["fingers_vis"].key(t - 0.001, perf.ch["fingers_vis"](t), "linear")
    perf.ch["fingers_vis"].key(t + 0.05, 0.0, "linear")
    if prop == "phone":
        perf.to("phone_glow", t, t + 0.3, 0.0, "smooth")
    perf.events.append((t, prop + "_release", dict(hand=hand)))
    hand_to(perf, hand, t + 0.1, t + 0.1 + dur, M._arm_rest(perf, hand, t + dur), "smooth")
    return t + dur


def a_hold_phone(perf, t, dur, st, pos="chest", hand="R", **kw):
    """Phone to chest / face / ear: the wrist and wrist angle are solved so the phone (as held by the hand drawing) sits where a person actually holds it; the forearm lifts, the head
    adjusts, the eyes focus on the screen."""
    P = perf.P
    sh = perf.shoulder(t)
    d = dur / st["speed"]
    k = P["k"]
    C, tilt = {"ear": ((sh[0] + 30 * k, sh[1] + 122 * k), 6.0), "face": ((sh[0] + 92 * k, sh[1] + 30 * k), -14.0)}.get(pos, ((sh[0] + 92 * k, sh[1] - 70 * k), -20.0))
    tgt, rot = _phone_wrist(perf, C, tilt, t + d)
    set_pose(perf, t, hand, "hold_phone")
    hand_to(perf, hand, t, t + d, tgt, "smooth")
    perf.to(f"hand_{hand}_rot", t, t + d, rot, "smooth")
    perf.to("spine_rot", t, t + d, 2.0, "smooth")
    if pos in ("chest", "face"):
        perf.to("head_rot", t + 0.15, t + d, 9.0, "smooth")                          # head adjusts down toward the screen
        perf.to("gaze_y", t + 0.1, t + d * 0.8, -0.8, "out")
    return t + d


def a_read_phone(perf, t, dur, st, **kw):
    """Eyes drop to the screen, head pitches down, reading saccades (left->right jumps with a return sweep), a thumb-scroll nudge; the brows follow the content."""
    perf.to("head_rot", t, t + 0.35, 11.0 * st["amp"], "smooth")
    perf.to("neck_rot", t, t + 0.35, 4.0, "smooth")
    perf.to("gaze_y", t, t + 0.25, -0.9, "out_back")
    perf.to("gaze_x", t, t + 0.25, 0.25, "out_back")
    n = max(2, int(dur / 0.5))
    for i in range(n):
        tt = t + 0.3 + i * (dur - 0.3) / n
        perf.ch["gaze_x"].key(tt, -0.25, "out")
        perf.ch["gaze_x"].key(tt + 0.2 * (dur - 0.3) / n * 2, 0.55, "linear")
        perf.ch["gaze_y"].key(tt + 0.12, -0.85 - 0.12 * (i % 2), "smooth")
    hx, hy = perf.v("hand_R_x", t + 0.2), perf.v("hand_R_y", t + 0.2)
    for i in range(int(dur / 0.7)):
        perf.ch["hand_R_y"].key(t + 0.4 + 0.7 * i, hy + 6, "smooth")
        perf.ch["hand_R_y"].key(t + 0.6 + 0.7 * i, hy - 3, "smooth")
    return t + dur


def a_type(perf, t, dur, st, **kw):
    """Two-thumb typing: both hands near the chest, rapid small taps, eyes on the screen."""
    P = perf.P
    sh = perf.shoulder(t)
    for side in ("L", "R"):
        set_pose(perf, t, side, "point" if side == "R" else "hold_phone")
        M.hand_to(perf, side, t, t + 0.4, (sh[0] + 120 * P["k"] + (10 if side == "L" else 0), sh[1] - 150 * P["k"]), "smooth")
    perf.to("gaze_y", t, t + 0.3, -0.9, "out")
    n = int(dur * 6)
    for i in range(n):
        tt = t + 0.45 + i / 6.0
        perf.ch["hand_R_y"].key(tt, perf.ch["hand_R_y"](t + 0.4) - 5 * (i % 2), "linear")
    return t + dur


def a_call(perf, t, dur, st, **kw):
    """Phone call: raise to the ear, then alternate listening (head tilt, still) and speaking."""
    end = a_hold_phone(perf, t, min(0.6, dur), st, pos="ear")
    r = random.Random(perf.seed + int(t * 5))
    tt = end
    while tt < t + dur:
        seg = r.uniform(0.6, 1.4)
        if r.random() < 0.5:
            M.a_talk(perf, tt, seg, st)
        else:
            perf.to("head_rot", tt, tt + 0.3, 3.0, "smooth")
        tt += seg
    return t + dur


def a_hesitate(perf, t, dur, st, **kw):
    """A stop-start: motion halts, the body draws back a hair, brows worry, a slow blink."""
    perf.emotion(t, "worried", 0.25, 0.8)
    perf.to("spine_rot", t, t + 0.25, perf.v("spine_rot", t) - 3.0, "out")
    perf.to("pelvis_dx", t, t + 0.25, perf.v("pelvis_dx", t) - 6.0, "out")
    perf.ch["blink"].key(t + 0.3, 0.0, "linear"), perf.ch["blink"].key(t + 0.42, 1.0, "linear"), perf.ch["blink"].key(t + 0.62, 0.0, "out")
    M._tremble(perf, t + 0.2, t + dur, 0.2, ("hand_R_x", "hand_R_y"), hz=7.0)
    return t + dur


def a_freeze(perf, t, dur, st, **kw):
    """Total stillness (fear/shock): everything holds, eyes wide, no blinking."""
    for nm in ("hand_L_x", "hand_L_y", "hand_R_x", "hand_R_y", "head_rot", "spine_rot", "pelvis_dx", "gaze_x", "gaze_y"):
        perf.hold(nm, t)
        perf.ch[nm].key(t + dur, perf.ch[nm](t), "linear")
    perf.to("wide", t, t + 0.1, 0.8, "out")
    perf.no_blink.append((t, t + dur))
    return t + dur


def a_flinch(perf, t, dur, st, **kw):
    """Involuntary recoil: fast (0.06 s) jerk back, blink, shoulders up; slow recovery."""
    P = perf.P
    perf.to("spine_rot", t, t + 0.06, perf.v("spine_rot", t) - 10.0 * st["amp"], "out")
    perf.to("head_rot", t, t + 0.06, perf.v("head_rot", t) - 8.0, "out")
    perf.to("pelvis_dx", t, t + 0.08, perf.v("pelvis_dx", t) - 12.0 * P["k"], "out")
    perf.to("shrug", t, t + 0.06, 1.0, "out")
    perf.ch["blink"].key(t, 0.0, "linear"), perf.ch["blink"].key(t + 0.05, 1.0, "linear"), perf.ch["blink"].key(t + 0.2, 0.0, "out")
    for nm, v in (("spine_rot", 0.0), ("head_rot", 0.0), ("pelvis_dx", 0.0), ("shrug", 0.15)):
        perf.to(nm, t + 0.15, t + dur, v, "smooth")
    return t + dur


def a_relief(perf, t, dur, st, **kw):
    perf.emotion(t, "relief", 0.5)
    perf.to("shrug", t, t + 0.35, 0.7, "out")
    perf.to("shrug", t + 0.35, t + dur, 0.0, "smooth")
    perf.to("spine_rot", t, t + 0.6, 4.0, "smooth")
    perf.to("head_rot", t, t + 0.6, 6.0, "smooth")
    perf.to("chest_rot", t, t + 0.4, -2.0, "out")
    return t + dur


def a_anger(perf, t, dur, st, **kw):
    perf.emotion(t, "anger", 0.2)
    for side in ("L", "R"):
        set_pose(perf, t + 0.1, side, "fist")
    perf.to("spine_rot", t, t + 0.4, 5.0, "out")
    perf.to("head_rot", t, t + 0.3, 5.0, "out")
    M._tremble(perf, t + 0.4, t + dur, 0.5, ("hand_R_x", "hand_R_y"), hz=12.0)
    return t + dur


def a_point(perf, t, dur, st, target=None, hand="R", **kw):
    P = perf.P
    sh = perf.shoulder(t)
    tgt = perf.target_rig(target, t + dur) if target is not None else (sh[0] + (P["upper_arm"] + P["forearm"]) * 0.98, sh[1] + 10)
    d = min(dur, 0.6) / st["speed"]
    reach = P["upper_arm"] + P["forearm"]
    vx, vy = tgt[0] - sh[0], tgt[1] - sh[1]
    dl = math.hypot(vx, vy) or 1.0
    tgt = (sh[0] + vx / dl * min(dl, reach * 0.97), sh[1] + vy / dl * min(dl, reach * 0.97))
    set_pose(perf, t, hand, "point")
    hand_to(perf, hand, t, t + d, tgt, "out_back")
    perf.to(f"hand_{hand}_rot", t, t + d, -4.0, "smooth")
    perf.to("spine_rot", t, t + d, 5.0 * st["amp"], "smooth")
    if target is not None:
        gaze_toward(perf, t, d, target)
    return t + d


def a_gesture(perf, t, dur, st, hand="R", **kw):
    P = perf.P
    n = max(1, int(dur / 0.55 * st["speed"]))
    set_pose(perf, t, hand, "gesture")
    for i in range(n):
        tt = t + i * dur / n
        sh = perf.shoulder(tt)
        up = (sh[0] + 120 * P["k"] + 30 * st["amp"], sh[1] - 170 * P["k"] + 55 * st["amp"] * (1 if i % 2 == 0 else 0.2))
        hand_to(perf, hand, tt, tt + 0.5 * dur / n, up, "out")
        perf.to("head_rot", tt, tt + 0.4 * dur / n, 2.0 * (1 if i % 2 == 0 else -0.5), "smooth")
        if i % 2 == 0:
            set_pose(perf, tt + 0.3 * dur / n, hand, "palm_up" if (i // 2) % 2 else "gesture")
    hand_to(perf, hand, t + dur, t + dur + 0.4, M._arm_rest(perf, hand, t + dur), "smooth")
    set_pose(perf, t + dur + 0.2, hand, "closed")
    return t + dur


def _visemes(word):
    out = []
    for ch in word:
        v = DEV_VOWELS.get(ch)
        if v:
            out.append(v)
    return out or ["A"]


def a_speak(perf, t, dur, st, words=None, **kw):
    """LIP-SYNC from the narration's word timings: every syllable (Devanagari vowel / matra) drives a mouth shape A/E/I/O/U; consonant-only words open on 'A'."""
    if not words:
        return M.a_talk(perf, t, dur, st)
    for nm in ("vis_A", "vis_E", "vis_I", "vis_O", "vis_U", "mouth_open"):
        perf.ch[nm].key(t - 0.05, 0.0, "linear")
    last = t
    for w in words:
        vs = _visemes(w["word"])
        w0, w1 = w["start"], w["end"]
        step = max(0.06, (w1 - w0) / len(vs))
        for i, vname in enumerate(vs):
            a, b = w0 + i * step, w0 + (i + 1) * step
            for nm in ("vis_A", "vis_E", "vis_I", "vis_O", "vis_U"):
                perf.ch[nm].key(a, 1.0 if nm == "vis_" + vname else 0.0, "linear")
                perf.ch[nm].key(b - 0.02, 1.0 if nm == "vis_" + vname else 0.0, "linear")
            perf.ch["mouth_open"].key(a, VISEME_OPEN[vname], "out")
            perf.ch["mouth_open"].key(b - 0.02, VISEME_OPEN[vname] * 0.85, "linear")
            last = b
        for nm in ("vis_A", "vis_E", "vis_I", "vis_O", "vis_U", "mouth_open"):                    # brief closure between words
            perf.ch[nm].key(w1 + 0.01, 0.0, "linear")
    perf.ch["mouth_open"].key(last + 0.1, 0.0, "smooth")
    return last


def a_place(perf, t, dur, st, target="PHONE", hand="R", prop="phone", **kw):
    """Put the phone back on the table: the wrist carries it to the surface, it turns flat (perspective) as it lowers, the fingers open, the prop leaves the hand (the free prop reappears)."""
    C = perf.target_rig(target, t + dur)
    tgt, rot = _phone_wrist(perf, C, -90.0, t + dur)
    hand_to(perf, hand, t, t + dur, tgt, "smooth")
    perf.to(f"hand_{hand}_rot", t, t + dur, rot, "smooth")
    perf.ch["phone_flat"].key(t + dur * 0.35, perf.ch["phone_flat"](t + dur * 0.35), "linear")
    perf.ch["phone_flat"].key(t + dur, 1.0, "smooth")
    gaze_toward(perf, t, 0.35, dict(rig=C))
    arrive = t + dur
    set_pose(perf, arrive + 0.05, hand, "open")
    perf.ch[prop + "_vis"].key(arrive + 0.14, perf.ch[prop + "_vis"](arrive), "linear")
    perf.ch[prop + "_vis"].key(arrive + 0.15, 0.0, "linear")
    perf.events.append((arrive + 0.15, prop + "_place", dict(hand=hand)))
    set_pose(perf, arrive + 0.5, hand, "relaxed")
    hand_to(perf, hand, arrive + 0.25, arrive + 0.9, M._arm_rest(perf, hand, arrive + 0.9), "smooth")
    perf.to(f"hand_{hand}_rot", arrive + 0.25, arrive + 0.9, 0.0, "smooth")
    return arrive + 0.9


def a_hand_over(perf, t, dur, st, point="HANDOVER", hand="R", prop="phone", **kw):
    """Give an object: eyes to the receiver, the arm carries the object to the meeting point (the phone stays upright so both hands agree on its tilt), holds until the receiver has it."""
    C = perf.target_rig(point, t + dur)
    if prop == "phone":
        tgt, rot = _phone_wrist(perf, C, 0.0, t + dur)
        arrive = a_reach(perf, t, dur, st, target=dict(rig=tgt), hand=hand)
        _rekey(perf, f"hand_{hand}_rot", arrive, rot)
    else:
        arrive = a_reach(perf, t, dur, st, target=dict(rig=C), hand=hand)
    set_pose(perf, arrive, hand, {"phone": "hold_phone", "card": "hold_card", "money": "hold_money", "document": "pinch", "cup": "hold_cup", "bag": "grab"}[prop])
    perf.events.append((arrive, "handover_give", dict(prop=prop, hand=hand, point=str(point))))
    return arrive


def a_receive(perf, t, dur, st, point="HANDOVER", hand="R", prop="phone", **kw):
    """Take an object: the hand opens toward the meeting point, closes on the prop (the prop attaches at contact), brings it to the eyes."""
    C = perf.target_rig(point, t + dur)
    if prop == "phone":
        tgt, rot = _phone_wrist(perf, C, 0.0, t + dur)
        arrive = a_reach(perf, t, dur, st, target=dict(rig=tgt), hand=hand)
        _rekey(perf, f"hand_{hand}_rot", arrive, rot)
    else:
        arrive = a_reach(perf, t, dur, st, target=dict(rig=C), hand=hand)
    a_grab(perf, arrive + 0.05, 0.1, st, hand=hand, prop=prop)
    perf.events.append((arrive + 0.05, "handover_take", dict(prop=prop, hand=hand)))
    return arrive + 0.1


def a_emotion_named(name):
    def f(perf, t, dur, st, **kw):
        perf.emotion(t, name, 0.25)
        return t + dur
    return f


def _relax_wrap(orig, mode):
    """sit / stand move the ROOT; hand IK targets are absolute, so a hand that is not busy must FOLLOW the body (lap when seated, arm-rest when standing) or the arm would be dragged behind."""
    def f(perf, t, dur, st, **kw):
        end = orig(perf, t, dur, st, **kw)
        P = perf.P
        for side in ("L", "R"):
            if side == "R" and any(perf.ch[nm](t) > 0.5 for nm in HELD_VIS):
                continue
            if mode == "stand" and side == "R":
                continue                                         # the v1 stand pushes off the knee with the near hand, then rests it
            x0, y0 = perf.v(f"hand_{side}_x", t), perf.v(f"hand_{side}_y", t)
            tt = t
            while tt <= end + 0.05:
                u = ease("smooth", (tt - t) / max(end - t, 1e-6))
                if mode == "sit":
                    hx, hy = perf.hip(tt)
                    tx, ty = hx + (70 if side == "R" else 55) * P["k"] + perf.so["s" + side], hy + 55 * P["k"]
                else:
                    tx, ty = M._arm_rest(perf, side, tt)
                perf.ch[f"hand_{side}_x"].key(tt, x0 + (tx - x0) * u, "linear")
                perf.ch[f"hand_{side}_y"].key(tt, y0 + (ty - y0) * u, "linear")
                tt += 0.1
            set_pose(perf, end, side, "closed")
        return end
    return f


# ---------------------------------------------------------------------------------------------------------------- acting sequences (v3)
def _still(perf, names, t0, t1):
    """Hold `names` perfectly still over [t0, t1]: intermediate keys (idle breathing, sway) are removed first, otherwise the hold would be overridden."""
    for nm in names:
        ch = perf.ch[nm]
        v = ch(t0)
        ch.keys = [k for k in ch.keys if not (t0 < k[0] < t1)]
        ch.key(t0, v, "linear")
        ch.key(t1, v, "linear")


def _breath(perf, t0, t1, hz, amp):
    """explicit breathing on the chest/shoulders so the rate can change with the emotion (fear: fast and shallow, realization: held)"""
    nm = "chest_rot"
    base = perf.ch[nm](t0)
    perf.ch[nm].keys = [k for k in perf.ch[nm].keys if not (t0 < k[0] < t1)]
    n = int((t1 - t0) * 30)
    for i in range(0, n + 1, 2):
        tt = t0 + i / 30.0
        perf.ch[nm].key(tt, base + amp * math.sin(2 * math.pi * hz * (tt - t0)), "linear")


def a_realization(perf, t, dur, st, target="PHONE", **kw):
    """REALIZATION as a sequence: the look holds, everything stops (breathing held), the pupils shift, the brows rise BEFORE the eyes widen, the head stops and rocks back a hair, the mouth
    comes open on an 'O', the torso stays frozen, then a slow exhale as it sinks in."""
    dur = max(dur, 1.3)
    _still(perf, ("hand_L_x", "hand_L_y", "hand_R_x", "hand_R_y", "spine_rot", "pelvis_dx", "shrug"), t, t + dur * 0.62)
    _breath(perf, t, t + dur * 0.5, 0.0, 0.0)                                            # breathing reduced to a hold
    perf.no_blink.append((t, t + dur * 0.6))
    perf.to("gaze_y", t + 0.22, t + 0.34, perf.v("gaze_y", t) + 0.35, "out")            # pupils shift
    perf.to("gaze_x", t + 0.24, t + 0.36, perf.v("gaze_x", t) - 0.25, "out")
    perf.to("brow_raise", t + 0.32, t + 0.55, 0.95, "out")                                # brows first
    perf.to("brow_tilt", t + 0.32, t + 0.6, 0.4, "smooth")
    perf.to("wide", t + 0.5, t + 0.68, 0.9, "out")                                        # then the eyes
    perf.to("head_rot", t + 0.45, t + 0.62, perf.v("head_rot", t) - 4.0, "out")           # the head stops and recoils slightly
    perf.to("mouth_smile", t + 0.6, t + 0.85, -0.1, "smooth")
    for nm in ("vis_A", "vis_E", "vis_I", "vis_U"):
        perf.to(nm, t + 0.6, t + 0.7, 0.0, "linear")
    perf.to("vis_O", t + 0.62, t + 0.85, 0.75, "out")
    perf.to("mouth_open", t + 0.62, t + 0.85, 0.35, "out")
    t2 = t + dur * 0.62
    perf.to("shrug", t2, t2 + 0.5, 0.0, "smooth")
    _breath(perf, t2, t + dur, 0.35, 1.6)                                                 # the slow exhale
    perf.to("vis_O", t2, t2 + 0.5, 0.0, "smooth")
    perf.to("mouth_open", t2, t2 + 0.5, 0.08, "smooth")
    perf.to("head_rot", t2, t + dur, perf.v("head_rot", t) + 3.0, "smooth")
    perf.events.append((t, "acting", dict(kind="realization", steps=["look", "hold", "pupils", "brows", "eyes", "head_stop", "mouth", "exhale"])))
    return t + dur


def a_fear(perf, t, dur, st, body=True, **kw):
    """FEAR as a sequence: micro recoil -> shoulders rise -> head retracts -> eyes widen -> breathing quickens and stays shallow; the hands tremble."""
    dur = max(dur, 1.2)
    P = perf.P
    if body:
        perf.to("spine_rot", t, t + 0.07, perf.v("spine_rot", t) - 4.0, "out")            # micro recoil
        perf.to("pelvis_dx", t, t + 0.09, perf.v("pelvis_dx", t) - 5.0 * P["k"], "out")
    perf.to("shrug", t + 0.08, t + 0.32, 0.9, "out")                                       # shoulders rise
    perf.to("neck_rot", t + 0.12, t + 0.4, -5.0, "smooth")                                 # head retracts
    perf.to("head_rot", t + 0.12, t + 0.4, perf.v("head_rot", t) - 5.0, "smooth")
    perf.to("wide", t + 0.2, t + 0.36, 0.9, "out")                                         # eyes widen
    perf.to("brow_raise", t + 0.18, t + 0.4, 0.85, "out")
    perf.to("brow_tilt", t + 0.18, t + 0.4, 0.9, "smooth")
    perf.to("mouth_smile", t + 0.3, t + 0.6, -0.6, "smooth")
    perf.to("mouth_worried", t + 0.3, t + 0.6, 0.8, "smooth")
    perf.to("vis_E", t + 0.3, t + 0.55, 0.55, "out")                                       # lips parted, corners pulled back
    perf.to("mouth_open", t + 0.3, t + 0.55, 0.42, "out")
    _breath(perf, t + 0.3, t + dur, 1.7, 1.5)                                              # fast, shallow
    if body:                                                                               # (while the body is busy standing up the hands must stay under the stand's control)
        M._tremble(perf, t + 0.4, t + dur, max(st["tremble"], 0.3), ("hand_R_x", "hand_R_y"), hz=10.0)
        M._tremble(perf, t + 0.4, t + dur, max(st["tremble"], 0.3), ("hand_L_x", "hand_L_y"), hz=12.0)
    perf.no_blink.append((t + 0.1, t + 0.7))
    perf.events.append((t, "acting", dict(kind="fear", steps=["recoil", "shoulders", "head_retract", "eyes", "breathing"])))
    return t + dur


def a_confusion(perf, t, dur, st, **kw):
    """CONFUSION as a sequence: head tilt -> the eyes go left, then right -> brows compress -> a small pause -> a slight shrug."""
    dur = max(dur, 1.1)
    perf.to("head_rot", t, t + 0.35, perf.v("head_rot", t) + 8.0, "smooth")               # head tilt
    perf.to("neck_rot", t, t + 0.35, 3.0, "smooth")
    perf.to("gaze_x", t + 0.1, t + 0.2, -0.4, "out")                                        # eyes shift
    perf.to("gaze_x", t + 0.42, t + 0.52, 0.45, "out")
    perf.to("brow_raise", t + 0.2, t + 0.5, 0.35, "smooth")                                 # brow compression: one brow down, one up
    perf.to("brow_asym", t + 0.2, t + 0.5, 0.7, "smooth")
    perf.to("brow_tilt", t + 0.2, t + 0.5, -0.3, "smooth")
    perf.to("mouth_smile", t + 0.3, t + 0.6, -0.25, "smooth")
    _still(perf, ("head_rot", "gaze_x", "gaze_y"), t + 0.6, t + 0.95)                       # small pause
    perf.to("shrug", t + 0.95, t + 1.2, 0.5, "smooth")
    perf.to("shrug", t + 1.2, t + dur, 0.0, "smooth")
    perf.events.append((t, "acting", dict(kind="confusion", steps=["tilt", "eyes", "brows", "pause", "shrug"])))
    return t + dur


def a_notice(perf, t, dur, st, target="PERSON_D", **kw):
    """NOTICE something/someone: the eyes lead, the brows lift, the body checks (a half-beat stop), the head follows, a blink resets, then the gaze settles on the target."""
    _still(perf, ("spine_rot", "pelvis_dx"), t, t + 0.4)
    perf.to("brow_raise", t, t + 0.15, 0.55, "out")
    perf.to("wide", t, t + 0.15, 0.4, "out")
    gaze_toward(perf, t + 0.02, 0.5, target, head=False)
    gaze_toward(perf, t + 0.16, 0.6, target, head=True)
    perf.ch["blink"].key(t + 0.5, 0.0, "linear"), perf.ch["blink"].key(t + 0.55, 1.0, "linear"), perf.ch["blink"].key(t + 0.68, 0.0, "out")
    perf.to("brow_raise", t + 0.5, t + dur, 0.2, "smooth")
    perf.to("wide", t + 0.5, t + dur, 0.1, "smooth")
    perf.events.append((t, "acting", dict(kind="notice", target=str(target))))
    return t + dur


def a_eye_contact(perf, t, dur, st, target="PERSON_D", **kw):
    """EYE CONTACT: both eyes and head settle on the other person and HOLD; micro-saccades keep the eyes alive; the blink rate drops."""
    gaze_toward(perf, t, min(0.5, dur), target)
    for i in range(int(dur / 0.55)):
        tt = t + 0.5 + i * 0.55
        perf.ch["gaze_x"].key(tt, perf.ch["gaze_x"](tt) + 0.03 * (1 if i % 2 else -1), "linear")
    perf.no_blink.append((t + 0.3, t + dur))
    perf.events.append((t, "eye_contact", dict(target=str(target))))
    return t + dur


def a_teleport(perf, t, dur, st, x=0.0, pose="stand", **kw):
    """Hard-cut re-blocking: the body is at world x in the rest `pose` ('stand' | 'sit') from time t on (every body channel is held one frame earlier, then keyed at the new place); held props are put away."""
    names = ("root_x", "root_y", "pelvis_dx", "pelvis_dy", "spine_rot", "chest_rot", "neck_rot", "head_rot", "hair_rot", "shrug", "foot_L_x", "foot_L_y", "foot_R_x", "foot_R_y", "foot_L_rot", "foot_R_rot",
             "hand_L_x", "hand_L_y", "hand_R_x", "hand_R_y", "hand_L_rot", "hand_R_rot") + HELD_VIS + ("fingers_vis", "phone_glow", "phone_flat")
    for nm in names:
        ch = perf.ch[nm]
        ch.key(t - 0.001, ch(t - 0.001), "linear")
    xr = perf.to_rig((x, perf.origin[1]))[0]
    for nm in HELD_VIS + ("fingers_vis", "phone_glow", "phone_flat"):
        perf.ch[nm].key(t, 0.0, "linear")
    if pose == "sit":
        M.pose_sit(perf, t, seat=perf.world["seat_h"], x=xr)
    else:
        M.pose_stand(perf, t, xr)
    for side in ("L", "R"):
        set_pose(perf, t, side, "relaxed")
    for nm in ("spine_rot", "chest_rot", "neck_rot", "head_rot"):
        perf.ch[nm].key(t, 4.0 if (pose == "sit" and nm == "spine_rot") else 0.0, "linear")
    perf.events.append((t, "teleport", dict(x=x, pose=pose)))
    return t


def a_prop_cycle(perf, t, dur, st, prop="CUP", hand="R", both=False, **kw):
    """One full interaction cycle with `prop` (props4 primitive) stretched to `dur` seconds: REACH -> CONTACT -> GRAB -> HOLD -> USE -> RELEASE. Needs the character's hand anchors (perf.anchors)."""
    from engine.skeleton import props4 as P4
    if getattr(perf, "anchors", None) is None:                                     # a bare Performance (no baked hand set): nothing to solve the grip against - say so, do not fake a contact
        perf.events.append((t, "prop_cycle_unavailable", dict(prop=prop, reason="no baked hand anchors")))
        return t + dur
    scale = max(dur, 1.0) / sum(P4.DUR.values())
    recs = P4.perform(perf, perf.anchors, prop, t, hand, mirror=(hand == "L"), scale=scale)
    if both:
        P4.perform(perf, perf.anchors, prop, t, "L" if hand == "R" else "R", mirror=(hand == "R"), scale=scale)
    perf.events.append((t, "prop_cycle", dict(prop=prop, hand=hand, recs=[dict(phase=r["phase"], t=r["t"], err=r["contact_err_px"], ok=bool(r["reachable"])) for r in recs])))
    return t + dur


def a_face_atom(perf, t, dur, st, name="fear", **kw):
    """REPLACEMENT FACE DRAWING: swap the procedural face for the Open Peeps face atom of emotion `name` for `dur` seconds (a peak-expression frame; gaze is baked into the drawing while it is up).
    Needs the character baked with parts_art2.bake_face_atoms. Step keys (the id is an integer, never interpolated)."""
    from engine.skeleton import parts_art2 as PA2
    k = PA2.FACE_ATOM_IDS[name]
    ch = perf.ch["face_atom_id"]
    ch.key(t - 0.001, 0.0, "linear")
    ch.key(t, float(k), "linear")
    ch.key(t + dur, float(k), "linear")
    ch.key(t + dur + 0.001, 0.0, "linear")
    perf.events.append((t, "face_atom", dict(name=name, dur=dur)))
    return t + dur


_RUN = {}


def _run_cycle():
    if not _RUN:
        import json as _j
        import os as _o
        from engine.shorts.raster import ROOT as _ROOT
        d = _j.load(open(_o.path.join(_ROOT, "assets/library/creomoto_run_cycle.json")))
        cyc = d["cycle"]
        floor = min(c["hip_z"] + c[k][1] for c in cyc for k in ("ankle_L", "ankle_R"))
        _RUN.update(cycle=cyc, fps=d["fps"], v_legs=d["stance_travel_speed_legs_per_s"], floor=floor)
    return _RUN


def a_run(perf, t, dur, st, speed_scale=1.0, **kw):
    """RUN: joint motion from ONE cycle of the CC0 Creomoto stickman (assets/library/creomoto_run_cycle.json, 20 frames) retargeted onto our rig by leg length: hips bob, feet leave the ground (a flight
    phase the walk grammar cannot make), arms drive, the trunk leans. The root travels at the speed at which the stance foot stays planted (measured from the cycle). Eases in and out from / to standing."""
    C = _run_cycle()
    P = perf.P
    L = (P["thigh"] + P["shin"]) * 0.985
    cyc, fps_c = C["cycle"], C["fps"]
    n_c = len(cyc)
    T = n_c / fps_c / max(speed_scale, 0.3)
    v = C["v_legs"] * L * max(speed_scale, 0.3)
    ramp = min(0.35, dur * 0.3)
    x0 = perf.v("root_x", t)
    base_dy = perf.v("pelvis_dy", t)
    so = perf.so
    stand_x = dict(L=perf.v("foot_L_x", t) - x0, R=perf.v("foot_R_x", t) - x0)              # relative to the root: the blend in/out follows the body
    sh0 = perf.shoulder(t)
    stand_hand = {sd: (perf.v(f"hand_{sd}_x", t) - sh0[0], perf.v(f"hand_{sd}_y", t) - sh0[1]) for sd in ("L", "R")}
    lean_avg = sum(math.degrees(math.atan2(c["neck"][0], c["neck"][1])) for c in cyc) / n_c
    n = int(dur * 30)
    x = x0
    prev_w = 0.0
    for i in range(n + 1):
        u = i / 30.0
        w = M.ease("smooth", max(0.0, min(1.0, u / max(ramp, 1e-3), (dur - u) / max(ramp, 1e-3))))
        if i:
            x += 0.5 * (w + prev_w) * v / 30.0
        prev_w = w
        ph = (u / T) % 1.0 * n_c
        i0 = int(ph) % n_c
        i1 = (i0 + 1) % n_c
        fr = ph - int(ph)
        lerp = lambda a, b: a + (b - a) * fr
        pt = lambda c0, c1, k: (lerp(c0[k][0], c1[k][0]), lerp(c0[k][1], c1[k][1]))
        c0, c1 = cyc[i0], cyc[i1]
        tt = t + u
        hip_h = (lerp(c0["hip_z"], c1["hip_z"]) - C["floor"]) * L
        dy = P["foot_h"] + hip_h - P["hip_y"]
        perf.ch["root_x"].key(tt, x, "linear")
        perf.ch["pelvis_dy"].key(tt, (1 - w) * base_dy + w * dy, "linear")
        for side in ("L", "R"):
            a = pt(c0, c1, "ankle_" + side)
            fx = x + a[0] * L + so["h" + side]
            fy = P["foot_h"] + (lerp(c0["hip_z"] + c0["ankle_" + side][1], c1["hip_z"] + c1["ankle_" + side][1]) - C["floor"]) * L
            perf.ch[f"foot_{side}_x"].key(tt, (1 - w) * (x + stand_x[side]) + w * fx, "linear")
            perf.ch[f"foot_{side}_y"].key(tt, (1 - w) * P["foot_h"] + w * max(P["foot_h"], fy), "linear")
            perf.ch[f"foot_{side}_rot"].key(tt, 0.0, "linear")
            wr = pt(c0, c1, "wrist_" + side)
            shx, shy = perf.shoulder(tt)
            hx, hy = shx + so["s" + side] + wr[0] * L, shy + wr[1] * L
            perf.ch[f"hand_{side}_x"].key(tt, (1 - w) * (shx + stand_hand[side][0]) + w * hx, "linear")
            perf.ch[f"hand_{side}_y"].key(tt, (1 - w) * (shy + stand_hand[side][1]) + w * hy, "linear")
        nk = pt(c0, c1, "neck")
        lean = math.degrees(math.atan2(nk[0], nk[1]))
        perf.ch["spine_rot"].key(tt, w * (14.0 * st["lean"] + 0.5 * (lean - lean_avg)), "linear")
        perf.ch["head_rot"].key(tt, -0.6 * w * (14.0 * st["lean"]), "linear")
    perf.events.append((t, "walk", dict(t1=t + dur, T=T, x0=x0, x1=x, run=True)))
    return t + dur


def register():
    A = M.ACTIONS
    A["sit"], A["stand"] = _relax_wrap(M.a_sit, "sit"), _relax_wrap(M.a_stand, "stand")
    A.update({"idle": a_idle, "breathe": a_breathe, "walk": a_walk, "walk_to": a_walk_to, "reach": a_reach, "reach_for_phone": lambda p, t, d, st, **k: a_reach(p, t, d, st, **k),
              "grab": a_grab, "pickup_phone": a_grab, "hold": a_hold, "release": a_release, "hold_phone": a_hold_phone, "read_phone": a_read_phone, "type": a_type, "call": a_call,
              "hesitate": a_hesitate, "freeze": a_freeze, "flinch": a_flinch, "relief": a_relief, "anger": a_anger, "point": a_point, "gesture": a_gesture, "speak": a_speak,
              "hand_over": a_hand_over, "receive": a_receive, "place": a_place, "realization": a_realization, "fear": a_fear, "confusion": a_confusion, "notice": a_notice, "eye_contact": a_eye_contact, "look_at": a_look_at, "look_at_phone": lambda p, t, d, st, **k: a_look_at(p, t, d, st, target="PHONE", **{x: y for x, y in k.items() if x != "target"}),
              "hand_pose": lambda p, t, d, st, side="R", pose="open", **k: (set_pose(p, t, side, pose), t + d)[1], "face_atom": a_face_atom, "run": a_run, "teleport": a_teleport, "prop_cycle": a_prop_cycle})
    for nm in ("worried", "sadness", "determination", "neutral", "curious"):
        A["emotion_" + nm] = a_emotion_named(nm)


register()
