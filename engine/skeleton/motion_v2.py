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
    perf.to("gaze_x", t, t + d * 0.7, gx, e)
    perf.to("gaze_y", t, t + d * 0.7, gy, e)
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
    bob = 11.0 * P["k"] * st["amp"]
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
        keys["pelvis_dy"].append((tt, base_h - bob * w * (1 - math.cos(4 * math.pi * ph)) * 0.5))                       # lowest at contact, highest at passing
        keys["pelvis_dx"].append((tt, 5.0 * P["k"] * w * math.sin(2 * math.pi * ph + 0.6)))                          # weight shift over the stance leg
        keys["spine_rot"].append((tt, 3.0 * st["lean"] * w + 2.4 * w * sfoot))
        keys["chest_rot"].append((tt, -2.4 * w * sfoot))                                                              # torso counter-rotation
        keys["head_rot"].append((tt, -0.8 * 2.4 * w * sfoot - 1.2 * w * math.sin(4 * math.pi * ph)))                  # head stabilised against the torso
        keys["neck_rot"].append((tt, 0.4 * w * math.sin(4 * math.pi * ph)))
        keys["hair_rot"].append((tt, 4.0 * w * math.sin(4 * math.pi * ph - 0.9)))
        wb = ease("smooth", min(1.0, u / max(ramp, 1e-3), (dur - u) / max(ramp, 1e-3))) if ramp > 0 else 1.0
        for k, side in enumerate(("L", "R")):
            phk = (ph + 0.5 * k) % 1.0
            if phk < 0.6:
                rel = a - 2 * a * (phk / 0.6)
                fy = P["foot_h"]
                rot = (9.0 * (1 - phk / 0.15) if phk < 0.15 else 0.0) - (24.0 * ((phk - 0.45) / 0.15) if phk > 0.45 else 0.0)
            else:
                uu = (phk - 0.6) / 0.4
                rel = -a + 2 * a * ease("smooth", uu)
                fy = P["foot_h"] + lift * math.sin(math.pi * uu) ** 0.8
                rot = -24.0 * (1 - uu) + 9.0 * uu
            walk_x = x + rel + stand_off[side] * 0.4
            f0 = fL0 if side == "L" else fR0
            sx = x + stand_off[side]
            keys[f"foot_{side}_x"].append((tt, (1 - wb) * (f0[0] if u < dur / 2 else sx) + wb * walk_x))
            keys[f"foot_{side}_y"].append((tt, (1 - wb) * P["foot_h"] + wb * fy))
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
    a_walk(perf, t, d, st, speed=spd, end_x=end_x, **{k: v for k, v in kw.items() if k in ("stride_scale", "hold_R", "hold_L", "speed_scale")})
    perf.events.append((t, "walk_to", dict(target=str(target), end_x=end_x, dur=d)))
    return t + d


def a_reach(perf, t, dur, st, target=None, hand="R", grip=None, **kw):
    """anticipation (0.16 s pull-back + lean back) -> reach (eyes first, torso commits, overshoot) -> contact (slow-in, 0.12 s hold) -> grip pose. Returns the contact time."""
    P = perf.P
    tgt = perf.target_rig(target, t + dur) if target is not None else (perf.hip(t)[0] + 240, P["hip_y"] * 0.7)
    if target is not None and isinstance(target, str) and target in ("PHONE", "CARD", "MONEY"):
        tgt = (tgt[0] - 18 * P["k"], tgt[1] + 36 * P["k"])                               # wrist target so the fingers close on the object
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
    gaze_toward(perf, t, 0.35, dict(rig=(tgt[0] + 18 * P["k"], tgt[1] - 36 * P["k"])) if target in ("PHONE", "CARD", "MONEY") else dict(rig=tgt))
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
    perf.to(f"hand_{hand}_rot", t, arrive, -10.0, "smooth")
    if grip:
        set_pose(perf, arrive - 0.03, hand, grip)
    perf.events.append((arrive, "contact", dict(target=str(target), hand=hand)))
    return arrive


def hand_to(perf, side, t0, t1, target, e="smooth"):
    perf.to(f"hand_{side}_x", t0, t1, target[0], e)
    perf.to(f"hand_{side}_y", t0, t1, target[1], e)


def a_grab(perf, t, dur, st, hand="R", prop="phone", **kw):
    """Close the fingers over the object: grip pose, prop attaches to the hand, screen glow (phone). Emits the pick-up event."""
    pose = {"phone": "hold_phone", "card": "hold_card", "money": "hold_money"}.get(prop, "grab")
    set_pose(perf, t, hand, "grab")
    set_pose(perf, t + 0.08, hand, pose)
    for nm in ("phone_vis", "card_vis", "money_vis"):
        perf.ch[nm].key(t - 0.001, perf.ch[nm](t), "linear")
        perf.ch[nm].key(t, 1.0 if nm == prop + "_vis" else 0.0, "linear")
    perf.ch["fingers_vis"].key(t - 0.001, 0.0, "linear")
    perf.ch["fingers_vis"].key(t + 0.06, 1.0, "linear")
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
    set_pose(perf, t + 0.45, hand, "closed")
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
    """Phone to chest / face / ear: forearm lifts, wrist tilts the screen toward the eyes, head adjusts, eyes focus on the screen."""
    P = perf.P
    sh = perf.shoulder(t)
    d = dur / st["speed"]
    if pos == "ear":
        tgt, rot = (sh[0] + 38 * P["k"], sh[1] + 58 * P["k"]), -78.0
    elif pos == "face":
        tgt, rot = (sh[0] + 150 * P["k"], sh[1] - 20 * P["k"]), -25.0
    else:
        tgt, rot = (sh[0] + 130 * P["k"], sh[1] - 175 * P["k"]), -38.0
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
            a_talk(perf, tt, seg, st)
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


def a_hand_over(perf, t, dur, st, point="HANDOVER", hand="R", prop="phone", **kw):
    """Give an object: eyes to the receiver, arm extends to the meeting point (target id), the hand holds until the receiver has it, then releases."""
    arrive = a_reach(perf, t, dur, st, target=dict(rig=perf.target_rig(point, t + dur)), hand=hand)
    set_pose(perf, arrive, hand, {"phone": "hold_phone", "card": "hold_card", "money": "hold_money"}[prop])
    perf.events.append((arrive, "handover_give", dict(prop=prop, hand=hand, point=str(point))))
    return arrive


def a_receive(perf, t, dur, st, point="HANDOVER", hand="R", prop="phone", **kw):
    """Take an object: hand opens toward the meeting point, closes on the prop (prop attaches at contact), brings it to the eyes."""
    arrive = a_reach(perf, t, dur, st, target=dict(rig=perf.target_rig(point, t + dur)), hand=hand)
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
            if side == "R" and (perf.ch["phone_vis"](t) > 0.5 or perf.ch["card_vis"](t) > 0.5 or perf.ch["money_vis"](t) > 0.5):
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


def register():
    A = M.ACTIONS
    A["sit"], A["stand"] = _relax_wrap(M.a_sit, "sit"), _relax_wrap(M.a_stand, "stand")
    A.update({"idle": a_idle, "breathe": a_breathe, "walk": a_walk, "walk_to": a_walk_to, "reach": a_reach, "reach_for_phone": lambda p, t, d, st, **k: a_reach(p, t, d, st, **k),
              "grab": a_grab, "pickup_phone": a_grab, "hold": a_hold, "release": a_release, "hold_phone": a_hold_phone, "read_phone": a_read_phone, "type": a_type, "call": a_call,
              "hesitate": a_hesitate, "freeze": a_freeze, "flinch": a_flinch, "relief": a_relief, "anger": a_anger, "point": a_point, "gesture": a_gesture, "speak": a_speak,
              "hand_over": a_hand_over, "receive": a_receive, "look_at": a_look_at, "look_at_phone": lambda p, t, d, st, **k: a_look_at(p, t, d, st, target="PHONE", **{x: y for x, y in k.items() if x != "target"}),
              "hand_pose": lambda p, t, d, st, side="R", pose="open", **k: (set_pose(p, t, side, pose), t + d)[1]})
    for nm in ("worried", "sadness", "determination", "neutral", "curious"):
        A["emotion_" + nm] = a_emotion_named(nm)


register()
