"""GENERAL PROP INTERACTION PRIMITIVE. Only the phone was solved before: the wrist position and wrist angle were computed so that the hand drawing's grip anchor lands on the prop. This module tests whether the
SAME hand / arm / IK system does the same for every other prop, given nothing but (hand pose, contact point on the prop, approach angle):

    PHASES = REACH -> CONTACT -> GRAB -> HOLD -> USE -> RELEASE

    solve_wrist(perf, anchors, pose, contact, H_abs, t, anchor="grip") -> (wrist_xy, hand_rot, contact_error_px, reachable)
    perform(perf, prop, t0, hand="R")                                  -> [phase records]   (keys hand x/y/rot + the hand pose; the prop art is NOT part of the rig: glyph_at draws a TEST glyph)

Everything is expressed relative to the shoulder in units of the character's own arm length, so it holds for every body size. Hand anchors come from the baked hand set (`manifest['hand_anchors']`).
"""
import math

from engine.skeleton import motion as M, motion_v2 as MV, rig_def as R

# prop -> pose, anchor used for contact, approach angle (absolute hand angle, deg CCW from straight down), waypoints (dx, dy) in ARM LENGTHS from the shoulder for each phase, and the abs prop tilt per phase
PROPS = {
    "PHONE":    dict(pose="hold_phone", anchor="grip", H=20.0, contact=(0.72, -0.64), hold=(0.36, -0.30), use=(0.10, 0.20), size=(60, 120), note="SOLVED in v3 by motion_v2._phone_wrist; here solved generically to compare"),
    "CARD":     dict(pose="hold_card", anchor="grip", H=25.0, contact=(0.78, -0.58), hold=(0.45, -0.22), use=(0.97, -0.10), size=(90, 58), note="use = push into the ATM / reader slot"),
    "MONEY":    dict(pose="hold_money", anchor="grip", H=25.0, contact=(0.78, -0.58), hold=(0.50, -0.20), use=(0.92, -0.14), size=(100, 46), note="use = hold out to hand over"),
    "DOCUMENT": dict(pose="pinch", anchor="grip", H=20.0, contact=(0.74, -0.60), hold=(0.42, -0.10), use=(0.46, 0.30), size=(110, 150), note="use = raised to reading position"),
    "CUP":      dict(pose="hold_cup", anchor="grip", H=8.0, contact=(0.76, -0.62), hold=(0.44, -0.26), use=(0.26, 0.34), size=(50, 62), note="use = to the mouth (drinking)"),
    "LAPTOP":   dict(pose="type", anchor="tip", H=35.0, contact=(0.66, -0.56), hold=(0.66, -0.56), use=(0.70, -0.52), size=(220, 16), note="both hands; use = typing bob; the laptop stays on the desk"),
    "DOOR":     dict(pose="grab", anchor="grip", H=10.0, contact=(0.88, -0.24), hold=(0.88, -0.40), use=(0.56, -0.36), size=(30, 20), note="use = handle down then pull the door towards the body"),
    "ATM":      dict(pose="touch_screen", anchor="tip", H=30.0, contact=(0.90, -0.06), hold=(0.90, -0.06), use=(0.98, -0.06), size=(200, 300), note="use = press keypad (push forward); fingertip anchor"),
    "KEYBOARD": dict(pose="type", anchor="tip", H=35.0, contact=(0.66, -0.72), hold=(0.66, -0.72), use=(0.70, -0.68), size=(240, 14), note="both hands, lower desk"),
    "BAG":      dict(pose="grab", anchor="grip", H=0.0, contact=(0.30, -0.86), hold=(0.30, -0.78), use=(0.36, -0.30), size=(120, 100), note="use = lift the bag to the shoulder"),
}
# extra interaction targets used by the situation coverage test (not part of the 10-prop matrix)
EXTRA = {
    "FOOD": dict(pose="pinch", anchor="grip", H=25.0, contact=(0.74, -0.60), hold=(0.44, -0.22), use=(0.25, 0.30), size=(26, 26), note="use = to the mouth (eating); no chewing / mouth animation exists"),
    "PEN": dict(pose="hold_pen", anchor="tip", H=30.0, contact=(0.60, -0.66), hold=(0.60, -0.66), use=(0.66, -0.66), size=(70, 8), note="writing at a desk"),
}
PROPS.update(EXTRA)
PHASES = ["REACH", "CONTACT", "GRAB", "HOLD", "USE", "RELEASE"]
DUR = dict(REACH=0.6, CONTACT=0.3, GRAB=0.2, HOLD=0.6, USE=0.8, RELEASE=0.5)


def _anchor(anchors, pose, which, mirror=False):
    a = anchors[pose][which]
    return (-a[0] if mirror else a[0], a[1])


def solve_wrist(perf, anchors, pose, contact, H_abs, t, anchor="grip", hand="R", mirror=False):
    """Wrist position + wrist rotation so that the hand's `anchor` point lands on `contact` with the hand at absolute angle H_abs. Reach-clamped; returns (wrist, hand_rot, err_px, reachable)."""
    lx, ly = _anchor(anchors, pose, anchor, mirror)
    hr = math.radians(H_abs)
    off = (lx * math.cos(hr) + ly * math.sin(hr), lx * math.sin(hr) - ly * math.cos(hr))
    wrist = (contact[0] - off[0], contact[1] - off[1])
    sh = perf.shoulder(t)
    sh = (sh[0] + perf.so["s" + hand], sh[1])
    reach = perf.P["upper_arm"] + perf.P["forearm"]
    d = math.hypot(wrist[0] - sh[0], wrist[1] - sh[1])
    ok = 0.25 * reach <= d <= 0.995 * reach
    if d > 0.995 * reach:
        f = 0.995 * reach / d
        wrist = (sh[0] + (wrist[0] - sh[0]) * f, sh[1] + (wrist[1] - sh[1]) * f)
    _, _, a1, a2 = R.two_bone(sh, wrist, perf.P["upper_arm"], perf.P["forearm"], -1)
    rot = H_abs - a2 - R.REST["wrist"]
    c2 = (wrist[0] + off[0], wrist[1] + off[1])
    return wrist, rot, math.hypot(c2[0] - contact[0], c2[1] - contact[1]), ok


def grip_point(perf, anchors, pose, anchor, t, hand="R", mirror=False):
    """Forward kinematics from the ACTUAL channels: where is the hand's anchor point at time t (rig space)? (independent of the solver)"""
    wrist = (perf.v(f"hand_{hand}_x", t), perf.v(f"hand_{hand}_y", t))
    sh = perf.shoulder(t)
    sh = (sh[0] + perf.so["s" + hand], sh[1])
    _, _, a1, a2 = R.two_bone(sh, wrist, perf.P["upper_arm"], perf.P["forearm"], -1)
    H = math.radians(a2 + R.REST["wrist"] + perf.v(f"hand_{hand}_rot", t))
    lx, ly = _anchor(anchors, pose, anchor, mirror)
    return (wrist[0] + lx * math.cos(H) + ly * math.sin(H), wrist[1] + lx * math.sin(H) - ly * math.cos(H)), math.degrees(H)


def _rel(perf, t, hand, rel):
    sh = perf.shoulder(t)
    A = perf.P["upper_arm"] + perf.P["forearm"]
    return (sh[0] + perf.so["s" + hand] + rel[0] * A, sh[1] + rel[1] * A)


def perform(perf, anchors, prop, t0, hand="R", mirror=False, stand_rest=True, scale=1.0):
    """Key one full interaction cycle of `prop` with one hand. Returns [dict(phase, t, target, hand_angle, contact_err_px, reachable, pose)] (times = phase START)."""
    d = PROPS[prop]
    DURS = {k: v * scale for k, v in DUR.items()}
    vis = perf.ch.get(prop.lower() + "_vis") if prop in ("CARD", "MONEY", "DOCUMENT", "CUP", "BAG", "PHONE") else None
    recs = []
    t = t0
    side = hand
    rest = M._arm_rest(perf, side, t)
    contact = _rel(perf, t, side, d["contact"])
    hold = _rel(perf, t, side, d["hold"])
    use = _rel(perf, t, side, d["use"])
    open_pose = "open"

    def solve(pt, H, anchor=d["anchor"], pose=d["pose"]):
        return solve_wrist(perf, anchors, pose, pt, H, t, anchor, side, mirror)

    def go(t_a, t_b, wrist, rot, e="smooth"):
        M.hand_to(perf, side, t_a, t_b, wrist, e)
        perf.to(f"hand_{side}_rot", t_a, t_b, rot, e)

    # REACH: from rest to a pre-contact point 0.12 A above the contact, hand open
    MV.set_pose(perf, t, side, open_pose)
    pre = (contact[0] - 0.05 * (perf.P["upper_arm"] + perf.P["forearm"]), contact[1] + 0.12 * (perf.P["upper_arm"] + perf.P["forearm"]))
    w, rot, err, ok = solve(pre, d["H"], pose=open_pose, anchor="grip")
    go(t, t + DURS["REACH"], w, rot)
    recs.append(dict(phase="REACH", t=t, target=pre, contact_err_px=round(err, 2), reachable=ok, pose=open_pose, H=d["H"]))
    t += DURS["REACH"]
    # CONTACT: the anchor of the GRIP pose on the contact point
    w, rot, err, ok = solve(contact, d["H"])
    go(t, t + DURS["CONTACT"], w, rot, "smooth")
    recs.append(dict(phase="CONTACT", t=t, target=contact, contact_err_px=round(err, 2), reachable=ok, pose=d["pose"], H=d["H"]))
    t += DURS["CONTACT"]
    # GRAB: pose swap at the contact instant
    MV.set_pose(perf, t, side, d["pose"])
    if vis is not None:                                                            # the prop art attaches to the hand at the grab and leaves it at the release
        vis.key(t - 0.001, vis(t), "linear")
        vis.key(t, 1.0, "linear")
    M.hand_to(perf, side, t, t + DURS["GRAB"], w, "linear")
    recs.append(dict(phase="GRAB", t=t, target=contact, contact_err_px=round(err, 2), reachable=ok, pose=d["pose"], H=d["H"]))
    t += DURS["GRAB"]
    # HOLD: carry to the hold position (a fixed prop - laptop, keyboard, ATM - stays: hold == contact)
    w, rot, err, ok = solve(hold, d["H"])
    go(t, t + DURS["HOLD"], w, rot)
    recs.append(dict(phase="HOLD", t=t, target=hold, contact_err_px=round(err, 2), reachable=ok, pose=d["pose"], H=d["H"]))
    t += DURS["HOLD"]
    # USE: prop-specific target (+ a small oscillation for typing / keypad taps)
    H_use = d["H"] + (-25.0 if prop == "CUP" else 15.0 if prop in ("DOOR", "BAG") else 0.0)
    w, rot, err, ok = solve(use, H_use)
    go(t, t + DURS["USE"], w, rot)
    if prop in ("LAPTOP", "KEYBOARD", "ATM"):
        for j in range(4):
            tt = t + 0.1 + j * 0.16
            M.hand_to(perf, side, tt, tt + 0.08, (w[0] + (4 if j % 2 else -4), w[1] - 6), "linear")
    recs.append(dict(phase="USE", t=t, target=use, contact_err_px=round(err, 2), reachable=ok, pose=d["pose"], H=H_use))
    t += DURS["USE"]
    # RELEASE: open, withdraw to the relaxed arm
    MV.set_pose(perf, t, side, open_pose)
    if vis is not None:
        vis.key(t - 0.001, vis(t), "linear")
        vis.key(t + 0.05, 0.0, "linear")
    MV.set_pose(perf, t + 0.4, side, "relaxed")
    go(t + 0.1, t + DURS["RELEASE"], M._arm_rest(perf, side, t + DURS["RELEASE"]), 0.0)
    recs.append(dict(phase="RELEASE", t=t, target=None, contact_err_px=0.0, reachable=True, pose=open_pose, H=None))
    return recs


# ------------------------------------------------------------------ TEST glyphs (NOT production art): a flat, honest placeholder so a reviewer can see where the prop is
def glyph(prop, size=1.0):
    from PIL import Image, ImageDraw
    w, h = PROPS[prop]["size"]
    im = Image.new("RGBA", (int(w * 2 + 40), int(h * 2 + 40)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx, cy = im.width // 2, im.height // 2
    ink = (20, 20, 24, 255)
    if prop == "PHONE":
        d.rounded_rectangle((cx - w, cy - h, cx + w, cy + h), 16, fill=(70, 90, 130, 255), outline=ink, width=6)
    elif prop == "CARD":
        d.rounded_rectangle((cx - w, cy - h, cx + w, cy + h), 12, fill=(214, 160, 70, 255), outline=ink, width=5)
        d.rectangle((cx - w + 14, cy - h + 22, cx - w + 60, cy - h + 48), fill=(240, 220, 150, 255))
    elif prop == "MONEY":
        d.rectangle((cx - w, cy - h, cx + w, cy + h), fill=(150, 190, 140, 255), outline=ink, width=5)
        d.ellipse((cx - h, cy - h + 6, cx + h, cy + h - 6), outline=ink, width=4)
    elif prop == "DOCUMENT":
        d.rectangle((cx - w, cy - h, cx + w, cy + h), fill=(246, 244, 236, 255), outline=ink, width=5)
        for i in range(6):
            d.line((cx - w + 18, cy - h + 28 + i * 26, cx + w - 18, cy - h + 28 + i * 26), fill=(120, 120, 130, 255), width=4)
    elif prop == "CUP":
        d.polygon([(cx - w, cy - h), (cx + w, cy - h), (cx + w * 0.7, cy + h), (cx - w * 0.7, cy + h)], fill=(226, 226, 232, 255), outline=ink)
        d.arc((cx + w * 0.6, cy - h * 0.5, cx + w * 1.6, cy + h * 0.5), -90, 90, fill=ink, width=6)
    elif prop in ("LAPTOP", "KEYBOARD"):
        d.rectangle((cx - w, cy - h, cx + w, cy + h * 3), fill=(180, 184, 194, 255), outline=ink, width=5)
        if prop == "LAPTOP":
            d.rectangle((cx - w * 0.9, cy - 190, cx + w * 0.9, cy - h * 2), fill=(90, 110, 150, 255), outline=ink, width=5)
    elif prop == "DOOR":
        d.rectangle((cx - 12, cy - 210, cx + 12, cy + 210), fill=(150, 116, 80, 255), outline=ink, width=5)
        d.ellipse((cx - 30, cy - 12, cx + 30, cy + 12), fill=(210, 190, 90, 255), outline=ink, width=4)
    elif prop == "ATM":
        d.rectangle((cx - w, cy - h, cx + w, cy + h), fill=(120, 128, 150, 255), outline=ink, width=6)
        d.rectangle((cx - w + 26, cy - h + 24, cx + w - 26, cy - 10), fill=(70, 190, 210, 255), outline=ink, width=4)
        for r in range(3):
            for c in range(3):
                d.rectangle((cx - 50 + c * 40, cy + 20 + r * 34, cx - 26 + c * 40, cy + 40 + r * 34), fill=(230, 230, 236, 255), outline=ink)
    elif prop == "BAG":
        d.rounded_rectangle((cx - w, cy - h * 0.5, cx + w, cy + h * 0.6), 14, fill=(150, 90, 70, 255), outline=ink, width=5)
        d.arc((cx - w * 0.5, cy - h * 1.2, cx + w * 0.5, cy), 180, 360, fill=ink, width=7)
    return im
