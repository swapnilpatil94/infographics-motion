"""QC for the ASSET + ACTING QUALITY LOCK film = every V2 gate (unchanged thresholds) + measured V3 gates. Automated gates cannot prove the film LOOKS good - they only catch the hard failures
listed in the milestone (floating hand, wrong grip, sliding / teleporting feet, mother 'appearing', unreadable overlap, static expression swaps, missing grips)."""
import math

import numpy as np

from engine.skeleton import hands3 as H3, motion_v2 as MV, qc_v2, rig_def as R


def _phone_centre_error(a, ev):
    """px between the target phone centre and the phone centre implied by the actual wrist channels + wrist angle at the contact instant"""
    t = ev[0]
    perf = a.perf
    C = ev[2]["centre"]
    hand = ev[2]["hand"]
    wrist = (perf.v(f"hand_{hand}_x", t), perf.v(f"hand_{hand}_y", t))
    rot = perf.v(f"hand_{hand}_rot", t)
    _, _, a1, a2 = R.two_bone(perf.shoulder(t), wrist, a.P["upper_arm"], a.P["forearm"], -1)
    Hh = math.radians(a2 + R.REST["wrist"] + rot)
    lx, ly, th = H3.phone_anchor(a.P)
    c = (wrist[0] + lx * math.cos(Hh) + ly * math.sin(Hh), wrist[1] + lx * math.sin(Hh) - ly * math.cos(Hh))
    return math.dist(c, C)


def run(plan, actors, cam, rep, film, mp4, stats, frames_dir, log=print):
    base = qc_v2.run(plan, actors, cam, rep, film, mp4, stats, frames_dir, log)
    checks, ev = dict(base["checks"]), dict(base["evidence"])
    fps = plan["fps"]
    acts = set(plan.get("acts") or [])                    # topic films: a gate about an act that the story does not contain is 'not applicable' (recorded, not silently passed)
    has = (lambda *names: (not acts) or bool(acts & set(names)))
    na = []
    # ---- hand-over: with real grips the WRISTS are a hand-length apart by design; what must coincide is the PHONE (centre implied by each hand's grip anchor)
    key = "hand_over_(both_hands_meet_within_30px;_phone_changes_owner)"
    give = [e for e in actors["A"].perf.events if e[1] == "handover_give"]
    take = [e for e in actors["D"].perf.events if e[1] == "handover_take"]
    ok_h, err_h = False, None
    if not has("HAND_OVER"):
        na.append("hand_over")
    elif give and take:
        def centre(a, t, hand):
            perf = a.perf
            wrist = (perf.v(f"hand_{hand}_x", t), perf.v(f"hand_{hand}_y", t))
            _, _, a1, a2 = R.two_bone(perf.shoulder(t), wrist, a.P["upper_arm"], a.P["forearm"], -1)
            Hh = math.radians(a2 + R.REST["wrist"] + perf.v(f"hand_{hand}_rot", t))
            lx, ly, th = H3.phone_anchor(a.P)
            return a.rig_to_world(wrist[0] + lx * math.cos(Hh) + ly * math.sin(Hh), wrist[1] + lx * math.sin(Hh) - ly * math.cos(Hh))
        tg, tt = give[0][0], take[0][0]
        ca, cd = centre(actors["A"], tg, give[0][2]["hand"]), centre(actors["D"], tt, take[0][2]["hand"])
        err_h = math.dist(ca, cd)
        own = ev["hand_over"]["ownership"]
        ok_h = err_h <= 8.0 and own["a_phone_after"] < 0.5 and own["d_phone_after"] > 0.5 and abs(tt - tg) < 1.6
    checks.pop(key, None)
    if has("HAND_OVER"):
        checks["hand_over_(phone_centres_coincide_<=8px;_phone_changes_owner)"] = ok_h
    ev["hand_over_phone_centre_error_px"] = None if err_h is None else round(err_h, 2)
    # ---- the phone never vanishes between the giver's hand and the receiver's hand
    gaps = 0
    if give and take:
        f0, f1 = int(give[0][0] * fps) - 3, int((take[0][0] + 0.25) * fps)
        for f in range(max(0, f0), min(f1, len(actors["A"].channels["phone_vis"]))):
            if actors["A"].channels["phone_vis"][f] < 0.5 and actors["D"].channels["phone_vis"][f] < 0.5:
                gaps += 1
    if has("HAND_OVER"):
        checks["phone_never_disappears_during_hand-over"] = bool(give and take) and gaps == 0
    ev["hand_over_phone_gap_frames"] = gaps
    # ---- hands: real library, exact grips
    from engine.skeleton import parts_art2 as PA2
    checks["hand_library_(>=20_poses_per_hand)"] = len(PA2.HAND_POSES) >= 20
    errs = [_phone_centre_error(a, e) for a in actors.values() for e in a.perf.events if e[1] == "phone_contact"]
    if has("PICK_UP", "REACH_PHONE"):
        checks["phone_grip_contact_(hand_closes_on_the_phone_<=3px)"] = bool(errs) and max(errs) <= 3.0
    else:
        na.append("phone_grip_contact")
    ev["phone_contact_error_px"] = [round(e, 2) for e in errs]
    # ---- feet: planted stance, no teleporting
    slide, jump = [], 0.0
    for a in actors.values():
        for e in a.perf.events:
            if e[1] != "walk":
                continue
            f0, f1 = int(e[0] * fps), min(int(e[2]["t1"] * fps), len(a.channels["root_x"]) - 1)
            for side in ("L", "R"):
                xs, ys = np.array(a.channels[f"foot_{side}_x"]), np.array(a.channels[f"foot_{side}_y"])
                jump = max(jump, float(np.abs(np.diff(xs[f0:f1 + 1])).max()))
                run_, runs = [], []
                for f in range(f0, f1 + 1):
                    if ys[f] <= a.P["foot_h"] + 1.0:
                        run_.append(xs[f])
                    elif run_:
                        runs.append(run_)
                        run_ = []
                if run_:
                    runs.append(run_)
                slide += [max(r) - min(r) for r in runs if len(r) >= 4]
    walks_expected = has("WALK_ACROSS", "PERSON_ENTERS")
    if walks_expected:
        checks["planted_feet_(flat-foot_slide_<=8px)"] = (max(slide) <= 8.0) if slide else False
    checks["no_teleporting_feet_(<=60px_per_frame_=_human_swing_peak)"] = jump <= 60.0
    ev["flat_foot_slide_px_max"] = round(max(slide), 2) if slide else None
    ev["foot_step_px_per_frame_max"] = round(jump, 2)
    # ---- the mother ENTERS: starts off-screen, covers real distance, notices, eye contact both ways
    D = actors.get("D")
    walks = [e for e in D.perf.events if e[1] == "walk"] if D else []
    dist = max((abs(e[2]["x1"] - e[2]["x0"]) for e in walks), default=0.0)
    notice = [e for e in D.perf.events if e[1] == "acting" and e[2].get("kind") == "notice"] if D else []
    ec = {cid: [e for e in a.perf.events if e[1] == "eye_contact"] for cid, a in actors.items()}
    if has("PERSON_ENTERS"):
        checks["mother_enters_(starts_off-screen,_walks_>=300px,_notices_him)"] = bool(D) and D.origin[0] >= 1235 and dist >= 300 and len(notice) >= 1
    if has("PERSON_ENTERS", "EYE_CONTACT"):
        checks["eye_contact_both_ways"] = all(len(v) >= 1 for v in ec.values())
    ev["entrance"] = dict(start_x=D.origin[0] if D else None, walk_px=round(dist), notice_events=len(notice), eye_contact={k: len(v) for k, v in ec.items()})
    # ---- acting is a SEQUENCE, not a static swap
    kinds = {}
    for a in actors.values():
        for e in a.perf.events:
            if e[1] == "acting":
                kinds[e[2]["kind"]] = max(kinds.get(e[2]["kind"], 0), len(e[2].get("steps", [])))
    need = [k for k, acts_ in (("realization", ("REALIZE", "BOTH_REALIZE")), ("fear", ("STAND_UP", "OTHER_REACTS")), ("confusion", ("EYE_CONTACT",))) if has(*acts_)]
    checks["acting_sequences_(realization,fear,confusion_with_>=5_steps)"] = all(kinds.get(k, 0) >= 5 for k in need)
    ev["not_applicable_gates"] = na
    ev["acting_sequences"] = kinds
    # ---- no unreadable overlap: torsos never intersect
    xa = actors["A"].origin[0] + actors["A"].facing * np.array(actors["A"].channels["root_x"])
    xd = actors["D"].origin[0] + actors["D"].facing * np.array(actors["D"].channels["root_x"])
    half = 0.5 * 1.2 * (actors["A"].P["torso_w"] + actors["D"].P["torso_w"])
    checks["characters_never_intersect_(torso_spacing)"] = float(np.abs(xa - xd).min()) >= half
    ev["min_torso_centre_distance_px"] = round(float(np.abs(xa - xd).min()), 1)
    if acts and "WALK_ACROSS" not in acts:                           # arc without a walk: the protagonist never walks -> the walk gate is not applicable
        if checks.pop("real_skeletal_walk_(steps,distance,foot_lift)", None) is not None:
            na.append("real_skeletal_walk")
    if plan.get("lamp_on", 1.0) == 0.0:                               # daylight art direction: the room is lit from the first frame, there is no 'lamp comes on' moment
        if checks.pop("lamp_raises_brightness_(lit_room_>_previous_shot)", None) is not None:
            na.append("lamp_raises_brightness")
    ev["not_applicable_gates"] = na
    ok = all(checks.values())
    return dict(base, checks=checks, evidence=ev, passed=ok, n_checks=len(checks))
