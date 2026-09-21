"""Per-act compilers of the scene director: one beat -> one or two SHOTS (camera, light, GP, insert) + the semantic ACTIONS of every character in it. Location- and prop-independent: positions come from the scene layout,
props from the beat, partners from the story graph."""
import math

from engine.environments import bedroom_wide as BW
from engine.skeleton import lighting_presets as LP
from engine.skeleton.scene_director import CAMS, FACE_ATOM_FOR, GP, MOOD_OF, PARK, TAIL, TWO_PERSON, _cam, _lighting, apply_fixes

HAS_FREE_PHONE = ("bedroom_wide", "study", "study_room", "office", "classroom", "cafe")


def _resolve_cam(tg, sz, mv, P, extra=None):
    if tg is None:
        return None
    tg = tg.replace("P.", f"{P}.").replace("+P", f"+{P}").replace("A+atm", "A.reach")
    return _cam(tg, sz, mv, **(extra or {}))


def _walk_x(d, cid, sc):
    return sc["lay"]["visitor_from"]


def block_scene(d, k, sc, t0, chars):
    """hard-cut re-blocking at the start of scene k: protagonist, partner(s) at their marks, everybody else parked"""
    lay = sc["lay"]
    A_pose = sc["A_start"]
    if k > 0 or sc["arrive"]:
        x = lay["visitor_from"] if sc["arrive"] and lay["visitor_from"] < 0 else (lay["seat_x"] if A_pose == "sit" and lay.get("seat_x") else lay["A_stop"])
        if sc["arrive"]:
            x = -260.0
        d.add("A", action="teleport", t=t0, dur=0.05, x=x, pose="sit" if (A_pose == "sit" and lay.get("seat_x")) else "stand")
    d.pose = getattr(d, "pose", {})
    d.pose["A"] = "sit" if (A_pose == "sit" and lay.get("seat_x")) else "stand"
    for cid, c in chars.items():
        if cid == "A":
            continue
        park_x = c["origin"][0]
        if cid in sc["partners"]:
            enters = sc["enters"] == "PERSON_ENTERS"
            if enters:
                d.add(cid, action="teleport", t=t0, dur=0.05, x=park_x, pose="stand")   # stays out of the set until his entrance beat
                d.pose[cid] = "parked"
            elif lay.get("D_sit_x"):
                d.add(cid, action="teleport", t=t0, dur=0.05, x=lay["D_sit_x"], pose="sit")
                d.pose[cid] = "sit"
            else:
                x = lay["D_stop"] if cid == "D" else lay["D_stop"] + (60 if cid == "X1" else 120)
                d.add(cid, action="teleport", t=t0, dur=0.05, x=x, pose="stand")
                d.pose[cid] = "stand"
        else:
            d.add(cid, action="teleport", t=t0, dur=0.05, x=park_x, pose="stand")
            d.pose[cid] = "parked"
    d.add("A", action="idle", t=t0, dur=d.cuts[sc["i1"] + 1] - t0)
    for cid in sc["partners"]:                                                      # everybody present breathes, sways and shifts weight for the whole scene (never a frozen statue)
        d.add(cid, action="idle", t=t0 + 0.06, dur=d.cuts[sc["i1"] + 1] - t0)


def emotion_atom(b):
    return FACE_ATOM_FOR.get(b["emotion"])


def compile_beat(d, i, b, t0, t1, chars):
    n_before = len(d.acts)
    act = b["act"]
    sc = d.scenes[d.scene_of[i]]
    lay = sc["lay"]
    P = d.partner(i)
    L = t1 - t0
    A = lambda **k: d.add("A", **k)
    Pp = lambda **k: d.add(P, **k)
    holding = getattr(d, "holding", False)
    partner_in = P in sc["partners"]
    gp = [dict(effect=e, anchor=an, start=s, duration=min(dur, L - 0.1 if L > 0.4 else dur), intensity=inten, relationship=rel) for (e, an, s, dur, inten, rel) in GP.get(act, [])]
    if act in ("PHONE_ALERT",) and sc["family"] not in HAS_FREE_PHONE:
        gp = [dict(g, anchor="chest") for g in gp]
    if act == "RESOLVE" and sc["time"] != "night":
        gp = [dict(g, anchor="head") for g in gp]
    treat, extra_shot = "skeleton", {}
    mood_key = "relief" if act == "RESOLVE" else MOOD_OF.get(b["emotion"], "dim")
    seat = d.pose.get("A") == "sit"
    atom = emotion_atom(b)
    # ------------------------------------------------------------------ acts
    if act in ("ESTABLISH", "OBSERVE", "CROWD_WATCH"):
        A(action="face", t=t0, dur=0.3, name="tired" if act == "ESTABLISH" else "neutral")
        if act == "OBSERVE":
            A(action="look_left", t=t0 + 0.2, dur=0.7)
            A(action="look_right", t=t0 + min(1.4, L * 0.55), dur=0.7)
            if b["emotion"] == "hope":
                A(action="face_atom", t=t0 + 0.4, dur=max(0.8, L - 0.6), name="smile")
        if act == "CROWD_WATCH":
            crowd = [v for k_, v in d.ids.items() if k_.startswith("crowd")]
            for n, cid in enumerate(crowd):
                x0, x1, face = (-220.0 - 160 * n, 1420.0, 1) if n % 2 == 0 else (1300.0 + 120 * n, -260.0, -1)
                d.add(cid, action="teleport", t=t0 - 0.02, dur=0.05, x=x0, pose="stand")
                d.add(cid, action="walk_to", t=t0, dur=max(2.4, L + 0.8), target=dict(world=(x1, BW.FLOOR_Y)), stop_before=0.0, fill=True, stride_scale=0.8, emotion="neutral", intensity=0.4)
                d.add(cid, action="teleport", t=t0 + max(2.4, L + 0.8) + 0.05, dur=0.05, x=chars[cid]["origin"][0], pose="stand")
    elif act == "ARRIVE":
        A(action="walk_to", t=t0 + 0.05, dur=max(1.2, L - 0.1), target="A_STOP", stop_before=0.0, fill=True, stride_scale=0.9, emotion="neutral", intensity=0.5)
        if b["emotion"] == "fear":
            A(action="face", t=t0 + 0.3, dur=0.4, name="worried")
    elif act == "PHONE_ALERT":
        A(action="buzz", t=t0 + 0.05, dur=1.0, intensity=0.9)
        A(action="flinch", t=t0 + 0.25, dur=0.6, emotion="fearful" if b["emotion"] == "fear" else "curious", intensity=0.4)
        if b["emotion"] == "hope":
            A(action="face", t=t0 + 0.5, dur=0.4, name="curious")
    elif act == "LOOK_AT_PHONE":
        A(action="look_at", t=t0 + 0.05, dur=max(0.4, L - 0.05), target="PHONE", track=True, emotion="curious", intensity=0.6)
        A(action="face", t=t0 + 0.1, dur=0.35, name="curious")
    elif act == "EYES_CHANGE":
        A(action="face", t=t0 + 0.05, dur=0.3, name="curious" if b["emotion"] == "hope" else "determination")
        A(action="face", t=t0 + min(0.9, L * 0.5), dur=0.4, name="surprise" if b["emotion"] == "hope" else "worried")
    elif act == "REACH_PHONE":
        if seat and sc["family"] in HAS_FREE_PHONE:
            A(action="reach", t=t0 + 0.02, dur=max(0.8, L - 0.3), target="PHONE", emotion="hesitant", intensity=0.8, grip="hold_phone")
        else:
            A(action="hand_pose", t=t0, dur=0.1, side="R", pose="open")
            A(action="look_at", t=t0 + 0.1, dur=L, target="PHONE")
    elif act == "TAKE_PHONE":
        if seat and sc["family"] in HAS_FREE_PHONE:
            A(action="grab", t=t0 + 0.12, dur=0.1, prop="phone", from_table=True)
        else:
            A(action="grab", t=t0 + 0.12, dur=0.1, prop="phone", from_table=False)
        A(action="hold_phone", t=t0 + 0.3, dur=max(0.5, L - 0.3), pos="chest", emotion="hesitant", intensity=0.6)
        d.holding = True
    elif act == "PICK_UP":
        A(action="grab", t=t0 + 0.12, dur=0.1, prop="phone", from_table=True)
        A(action="hold_phone", t=t0 + 0.3, dur=max(0.5, L - 0.3), pos="chest", emotion="hesitant", intensity=0.6)
        d.holding = True
    elif act == "READ_MESSAGE":
        A(action="read_phone", t=t0 + 0.05, dur=L - 0.05, emotion="nervous", intensity=0.6)
        A(action="face", t=t0 + 0.1, dur=0.3, name="concerned" if b["emotion"] != "hope" else "curious")
        if b["emotion"] == "hope":
            A(action="face_atom", t=t0 + 0.6, dur=max(0.8, L - 0.8), name="smile")
    elif act == "PHONE_CALL":
        if not holding:
            A(action="grab", t=t0 + 0.05, dur=0.1, prop="phone", from_table=False)
            d.holding = True
        A(action="call", t=t0 + 0.2, dur=max(1.0, L - 0.2), emotion="nervous", intensity=0.6)
    elif act == "REALIZE":
        A(action="realization", t=t0 + 0.05, dur=max(1.3, L - 0.05), emotion="shocked", intensity=0.8)
        A(action="face_atom", t=t0 + 0.35, dur=min(1.4, max(0.8, L - 0.6)), name=atom if atom in ("fear", "dread") else "dread")
    elif act == "STAND_UP":
        if seat:
            A(action="fear", t=t0, dur=1.0, emotion="fearful" if b["emotion"] == "fear" else "curious", intensity=0.7, body=False)
            A(action="stand", t=t0 + 0.08, dur=min(1.3, max(1.0, L - 0.1)), emotion="fearful" if b["emotion"] == "fear" else "curious", intensity=0.7)
            d.pose["A"] = "stand"
        else:
            A(action="flinch", t=t0 + 0.1, dur=0.5, emotion="curious", intensity=0.5)
            A(action="head_tilt", t=t0 + 0.3, dur=0.6, angle=-6.0)
    elif act in ("WALK_ACROSS", "RUN_AWAY"):
        if seat:
            A(action="stand", t=t0 + 0.02, dur=1.0)
            d.pose["A"] = "stand"
            A(action="walk_to", t=t0 + 1.05, dur=max(1.0, L - 1.1), target="A_STOP", stop_before=0.0, fill=True, stride_scale=0.6, hold_R=holding, emotion="nervous", intensity=0.7)
        elif act == "RUN_AWAY":
            A(action="run", t=t0 + 0.05, dur=max(1.0, L - 0.1), speed_scale=0.5)
        else:
            A(action="walk_to", t=t0 + 0.05, dur=L - 0.1, target="A_STOP", stop_before=0.0, fill=True, stride_scale=0.6, hold_R=holding, emotion="nervous", intensity=0.7)
    elif act == "SIT_DOWN":
        if lay.get("seat_x") and d.pose.get("A") != "sit":
            A(action="sit", t=t0 + 0.05, dur=max(1.0, L - 0.1))
            d.pose["A"] = "sit"
        else:
            A(action="idle", t=t0, dur=L)
    elif act == "PERSON_ENTERS":
        src = lay.get("D_from", lay["visitor_from"])
        far = src + (-120.0 if src < 0 else 120.0)
        walk = max(1.6, abs(far - lay["D_stop"]) / 190.0)                     # natural pace: he arrives (and can act) at the END of this beat
        ts = max(d.cuts[sc["i0"]] + 0.1, t1 - walk)
        Pp(action="teleport", t=ts - 0.06, dur=0.05, x=far, pose="stand")
        Pp(action="walk_to", t=ts, dur=max(1.2, t1 - ts), target="D_STOP", stop_before=0.0, speed=abs(far - lay["D_stop"]) / max(1.2, t1 - ts), stride_scale=0.7, emotion="hesitant", intensity=0.5)
        Pp(action="face", t=t0 + 0.3, dur=0.4, name="concerned")
        Pp(action="notice", t=t0 + 0.35, dur=0.7, target="PERSON_A", emotion="hesitant", intensity=0.5)
        A(action="notice", t=t0 + 0.2, dur=0.7, target="DOOR" if lay.get("D_from", lay["visitor_from"]) > 0 else "PERSON_" + P, emotion="shocked" if b["emotion"] == "fear" else "curious", intensity=0.5)
        A(action="eye_contact", t=t0 + 0.95, dur=max(1.0, L - 0.85), target="PERSON_" + P)
        Pp(action="eye_contact", t=t0 + 1.1, dur=max(1.0, L - 0.9), target="PERSON_A")
        d.pose[P] = "stand"
    elif act == "MEET":
        A(action="eye_contact", t=t0 + 0.2, dur=max(0.8, L - 0.2), target="PERSON_" + P, emotion="hesitant", intensity=0.5)
        Pp(action="eye_contact", t=t0 + 0.05, dur=max(0.8, L - 0.05), target="PERSON_A")
        Pp(action="talk", t=t0 + 0.5, dur=max(0.6, L - 0.6), emotion="neutral", intensity=0.5)
    elif act == "EYE_CONTACT":
        A(action="eye_contact", t=t0 + 0.02, dur=L - 0.02, target="PERSON_" + P, emotion="nervous", intensity=0.5)
        Pp(action="eye_contact", t=t0 + 0.05, dur=L - 0.05, target="PERSON_A", emotion="hesitant", intensity=0.5)
        Pp(action="confusion", t=t0 + 0.4, dur=min(1.1, max(1.1, L - 0.5)), emotion="hesitant", intensity=0.5)
    elif act == "CONVERSE":
        speaker, listener = (("D", "A") if b.get("subject") == "partner" else ("A", "D"))
        sp, li = (P, "A") if speaker == "D" else ("A", P)
        d.add(sp, action="talk", t=t0 + 0.1, dur=max(0.8, L - 0.2), emotion="neutral", intensity=0.6)
        d.add(sp, action="gesture", t=t0 + 0.3, dur=max(0.8, L - 0.5), hand="R", emotion="hesitant", intensity=0.5)
        d.add(li, action="listen", t=t0 + 0.1, dur=max(0.8, L - 0.2))
        d.add(li, action="eye_contact", t=t0 + 0.15, dur=max(0.8, L - 0.2), target="PERSON_" + sp)
        if L > 3.4:                                                            # long exchange: the listener answers in the second half
            d.add(li, action="talk", t=t0 + L * 0.55, dur=L * 0.35, emotion="hesitant", intensity=0.5)
    elif act == "OTHER_LOOKS_AT_PHONE":
        Pp(action="look_at", t=t0 + 0.05, dur=L - 0.05, target="PHONE", track=True, emotion="suspicious", intensity=0.6)
        A(action="hold_phone", t=t0 + 0.2, dur=0.6, pos="face", emotion="hesitant", intensity=0.4)
        A(action="look_at", t=t0 + 0.6, dur=0.5, target="PERSON_" + P, emotion="nervous", intensity=0.4)
    elif act in ("HAND_OVER", "GIVE_OBJECT", "RECEIVE_OBJECT"):
        prop = (b.get("data") or {}).get("prop") or ("phone" if holding else "money")
        giver, taker = ("A", P) if act != "RECEIVE_OBJECT" else (P, "A")
        t_meet = round(t0 + max(0.8, L * 0.55), 3)
        if giver == "A" and prop != "phone":
            A(action="grab", t=t0 + 0.02, dur=0.1, prop=prop)                  # the object comes out of the pocket / bag into the hand first
        if giver == P and prop != "phone":
            Pp(action="grab", t=t0 + 0.02, dur=0.1, prop=prop)
        d.add(giver, action="hand_over", t=t0 + 0.12, dur=t_meet - t0 - 0.12, target="PERSON_" + taker, point="HANDOVER", prop=prop, emotion="hesitant", intensity=0.6)
        d.add(taker, action="receive", t=t0 + 0.2, dur=t_meet - t0 - 0.15, point="HANDOVER", prop=prop, emotion="hesitant", intensity=0.5)
        d.add(giver, action="release", t=t_meet + 0.55, dur=0.5, prop=prop)
        d.add(taker, action="hold_phone" if prop == "phone" else "look_at", t=t_meet + 0.65, dur=max(0.4, t1 - t_meet - 0.65), **(dict(pos="chest", emotion="hesitant", intensity=0.5) if prop == "phone" else dict(target="HANDOVER")))
        if prop == "phone":
            d.holding = giver != "A" and holding
    elif act == "OTHER_REACTS":
        Pp(action="fear", t=t0 + 0.05, dur=1.2, emotion="fearful", intensity=0.6)
        Pp(action="face", t=t0 + 0.3, dur=0.4, name="worried")
        A(action="look_at", t=t0 + 0.1, dur=L - 0.1, target="PERSON_" + P, track=True)
        if atom:
            Pp(action="face_atom", t=t0 + 0.5, dur=min(1.4, max(0.8, L - 0.7)), name=atom if atom != "smile" else "worried")
    elif act == "SUSPECT":
        A(action="face", t=t0 + 0.05, dur=0.4, name="suspicious")
        A(action="look_at", t=t0 + 0.3, dur=max(0.6, L - 0.3), target="PERSON_" + P if partner_in else "DOOR", emotion="suspicious", intensity=0.6)
        A(action="head_tilt", t=t0 + 0.5, dur=0.6, angle=8.0)
        A(action="face_atom", t=t0 + 0.55, dur=min(1.3, max(0.8, L - 0.7)), name="suspicious")
    elif act == "USE_ATM":
        A(action="prop_cycle", t=t0 + 0.1, dur=max(1.4, L - 0.1), prop="ATM", hand="R")
        A(action="look_at", t=t0 + 0.1, dur=L, target="SCREEN")
    elif act == "COUNT_MONEY":
        A(action="prop_cycle", t=t0 + 0.05, dur=max(1.4, L - 0.1), prop="MONEY", hand="R")
        A(action="face", t=t0 + 0.2, dur=0.5, name="concerned")
    elif act == "READ_DOCUMENT":
        reader = P if b.get("subject") == "partner" else "A"
        d.add(reader, action="prop_cycle", t=t0 + 0.05, dur=max(1.4, L - 0.1), prop="DOCUMENT", hand="R")
        if reader != "A" and partner_in:
            A(action="look_at", t=t0 + 0.2, dur=L - 0.2, target="PERSON_" + reader)
    elif act == "TYPE_LAPTOP":
        A(action="prop_cycle", t=t0 + 0.05, dur=max(1.4, L - 0.1), prop="LAPTOP", hand="R", both=True)
    elif act == "BOTH_REALIZE":
        A(action="realization", t=t0 + 0.05, dur=max(1.3, L - 0.05), emotion="shocked", intensity=0.8)
        if partner_in:
            Pp(action="freeze", t=t0 + 0.05, dur=0.6)
            Pp(action="look_at", t=t0 + 0.7, dur=max(0.4, L - 0.7), target="PERSON_A", emotion="fearful", intensity=0.6)
            Pp(action="face_atom", t=t0 + 0.4, dur=min(1.2, max(0.7, L - 0.6)), name="suspicious")
    elif act == "CLOSE_UP":
        A(action="face", t=t0 + 0.05, dur=0.5, name="determination")
        A(action="look_at", t=t0 + 0.1, dur=max(0.4, L - 0.1), target="CAMERA")
        if b.get("ambient_gaze"):                                                      # Kathaya plans: a held close-up still breathes and drifts (never a frozen frame)
            A(action="idle", t=t0, dur=L)
    elif act == "RESOLVE":
        A(action="relief", t=t0 + 0.2, dur=L + TAIL - 0.4, emotion="relieved", intensity=0.6)
        if partner_in:
            Pp(action="relief", t=t0 + 0.6, dur=L + TAIL - 1.0, emotion="relieved", intensity=0.5)
            A(action="look_at", t=t0 + 0.2, dur=1.0, target="PERSON_" + P, head=True)
    elif act == "INSERT_SCREEN":
        treat = "insert_ui"
        data = b.get("data") or {}
        extra_shot = dict(ui=dict(screen="sms", data=dict(sender=data.get("sender", "UNKNOWN"), time=data.get("time", "अभी"), text=data.get("text", ""))))
        gp = [dict(effect="ring", anchor="ui", start=0.5, duration=min(1.0, max(0.3, L - 0.5)), intensity=0.9, relationship="the demand")]
    elif act == "VISUALIZE_FLOW":
        treat = "procedural"
        data = b.get("data") or {}
        extra_shot = dict(procedural=dict(type="money_flow", data={"amount": data.get("amount", 100000), "from_label": data.get("from_label", "आपकी बचत"), "to": data.get("to", ["खाता 1", "खाता 2", "खाता 3"])}))
    else:                                                                       # any act without a dedicated compile: neutral, watched beat
        A(action="idle", t=t0, dur=L)
    if b.get("ambient_gaze") and treat == "skeleton" and L >= 1.0 and not any(a["action"] == "look_at" for a in d.acts[n_before:]):
        tgt = ("PHONE", "CAMERA", "WINDOW", "DOOR", "LAMP")[i % 5]                     # basic acting: a person's eyes are never frozen - a target-driven glance in every shot that has no gaze of its own (Kathaya plans)
        A(action="look_at", t=t0 + 0.3, dur=min(1.4, max(0.4, L - 0.6)), target=tgt)
    # ------------------------------------------------------------------ shot(s)
    co = b.get("camera")                                                        # an explicit camera from the visual scene plan (Kathaya): executed as given, never rotated or split
    two = L > 4.4 and treat == "skeleton" and act not in ("RESOLVE",) and not co
    spans = [(t0, t0 + 0.5 * L + 0.2), (t0 + 0.5 * L + 0.2, t1)] if two else [(t0, t1)]
    for x in b.get("effects") or []:                                            # requested effects ("rays@phone"): the renderer's own Grease Pencil effects
        e_, an_ = x.split("@")
        gp.append(dict(effect=e_, anchor=an_, start=0.1, duration=min(1.2, max(0.3, L - 0.2)), intensity=0.8, relationship="requested by the visual plan"))
    adj = getattr(d, "camera_adjustments", None)
    if adj is None:
        adj = d.camera_adjustments = []
    for k, (s0, s1) in enumerate(spans):
        tg, sz, mv = ((co["target"], co["size"], co["move"]) if co else d.pick_cam(act, i)) if treat == "skeleton" else (None, None, None)
        if tg == "A.reach" and not (d.pose.get("A") == "sit" and sc["family"] in HAS_FREE_PHONE):
            if co:
                adj.append(dict(beat=b["id"], asked=[tg, sz, mv], used=["A.head", "medium", "push"], why="the phone is not on a table to reach for (standing / no free phone in this set)"))
            tg, sz, mv = "A.head", "medium", "push"                                 # standing: the phone is in the pocket / hand, not on a table to reach for
        if treat != "skeleton":
            cam = None
        else:
            if act in ("READ_DOCUMENT", "COUNT_MONEY") and b.get("subject") == "partner" and partner_in and tg and tg.startswith("A."):
                tg = P + tg[1:]
            cam = _resolve_cam(tg, sz, mv, P, dict(dir=-1) if mv == "reveal" and lay.get("D_from", lay["visitor_from"]) > 0 else dict(dir=1) if mv in ("reveal", "truck") else None)
            if cam and not partner_in and ("+" + P in cam["target"] or cam["target"].startswith(P + ".")):
                if co:
                    adj.append(dict(beat=b["id"], asked=[co["target"], co["size"], co["move"]], used=["A.head", "medium", "isolate"], why="no partner is on the set in this scene"))
                cam = _cam("A.head", "medium", "isolate")                       # no partner in this scene: never frame an empty spot
        lt = _lighting(sc, b["emotion"], act, False)
        if sc["time"] == "night" and act not in ("INSERT_SCREEN", "VISUALIZE_FLOW"):
            lt["phone"] = 1.0
        sh = dict(id=f"S{len(d.shots) + 1:02d}", key=b["id"] + ("" if not two else f".{'ab'[k]}"), treatment=treat, t0=round(s0, 3), t1=round(s1, 3), beats=[b["id"]], segs=[b["id"]], purpose=f"{act} ({sc['loc']}, {sc['time']})",
                  act=act, gp=gp if k == 0 else [], transition_in=(b.get("transition") if b.get("transition") in ("cut", "fade", "dip") and k == 0 else "cut") if b.get("transition") else ("fade" if (len(d.shots) == 0) else ("dip" if (i > 0 and d.scene_of[i] != d.scene_of[i - 1]) else "cut")), sfx=[], phase="-", location=sc["loc"], lighting=lt, audio_mood=mood_key,
                  environment=sc["env"], **extra_shot)
        if cam:
            sh["camera"] = cam
        d.shots.append(apply_fixes(sh, d.fixes.get(sh["key"]) or (d.fixes.get(b["id"]) if not two else None)))


def sfx_for(d):
    out = []
    for i, b in enumerate(d.beats):
        t = d.cuts[i]
        a = b["act"]
        if a == "PHONE_ALERT":
            out += [dict(t=round(t + 0.05, 3), kind="buzz", gain=0.9), dict(t=round(t + 0.1, 3), kind="ding", gain=0.55)]
        if a in ("EYES_CHANGE", "BOTH_REALIZE", "REALIZE"):
            out.append(dict(t=round(t + 0.1, 3), kind="heartbeat", gain=0.7))
        if a in ("STAND_UP", "OTHER_REACTS", "PERSON_ENTERS", "MEET", "USE_ATM", "GIVE_OBJECT", "HAND_OVER"):
            out.append(dict(t=round(t + 0.1, 3), kind="impact", gain=0.4))
    for i in range(1, len(d.beats)):
        out.append(dict(t=round(d.cuts[i] - 0.06, 3), kind="whoosh", gain=0.2))
    return out
