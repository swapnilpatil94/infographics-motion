"""Story state + continuity: a structured world model advanced segment by segment.

State drives the film: financial numbers shown on screen come from here (never invented), `pressure` (0..1) drives lighting/camera
tension, phone/holding state constrains which acting verbs are legal, and every shot records state_before/after so the QC can
verify continuity (outfit, location, phone, money, lighting).
"""
import copy

PRESSURE = dict(urgency=0.25, fear=0.25, isolation=0.2, authority=0.15, commitment=0.15, shame=0.05)


def initial(analysis):
    prot = next((c for c in analysis["characters"] if c["role"] == "protagonist"), analysis["characters"][0] if analysis["characters"] else None)
    return dict(protagonist=prot["id"] if prot else None, location=None, holding_phone=False, phone_at_ear=False, ui=None,
                money=dict(sent=[], sent_total=0.0, lost_total=0.0, attempted=0.0), pressure=0.0, knows_scam=False, suspects_scam=False,
                emotion="blank", phase="HOOK", time_of_day=None, minutes=None)


def advance(state, seg):
    """Return the state AFTER this segment (pure function of state + annotated segment)."""
    s = copy.deepcopy(state)
    tg = seg["tags"]
    s["phase"] = seg["phase"]
    s["emotion"] = tg["emotion"]
    if tg["location"]:
        s["location"] = tg["location"]
    for a in tg["amounts"]:
        if a["kind"] == "sent":
            s["money"]["sent"].append(a["value"])
            s["money"]["sent_total"] = sum(s["money"]["sent"])
        elif a["kind"] == "lost":
            s["money"]["lost_total"] = max(s["money"]["lost_total"], a["value"])
        elif a["kind"] == "attempted":
            s["money"]["attempted"] = a["value"]
    for m in tg["psychology"]:
        if seg["phase"] not in ("EXPLANATION", "PAYOFF"):                # the mechanism acts on the character only while it happens
            s["pressure"] = min(1.0, s["pressure"] + PRESSURE.get(m, 0.1))
    if seg["phase"] in ("EXPLANATION", "PAYOFF"):
        s["pressure"] = max(0.0, s["pressure"] - 0.12)
    if tg["emotion"] in ("uneasy", "suspicious", "fear", "concerned") and seg["phase"] in ("ESCALATION", "COMPLICATION", "CLIMAX"):
        s["suspects_scam"] = True
    if seg["phase"] in ("REVEAL", "EXPLANATION", "PAYOFF"):
        s["knows_scam"] = True
    return s


def continuity_check(shots):
    """Cross-shot rules. Returns warnings (each names the shots involved)."""
    w = []
    prev = None
    for sh in shots:
        st_b, st_a = sh["state_before"], sh["state_after"]
        if sh["treatment"] == "performance":
            acts = [a["verb"] for a in sh["actions"]]
            if any(v in ("read_phone", "phone_to_ear", "phone_down") for v in acts) and not (st_b["holding_phone"] or "pickup_phone" in acts):
                w.append(f"{sh['id']}: phone verb without a phone in hand (no pickup earlier)")
            if prev and prev["treatment"] == "performance" and prev["character"] == sh["character"] and prev["location"] != sh["location"] and sh["transition_in"] == "cut" and not sh.get("time_jump"):
                w.append(f"{sh['id']}: location change {prev['location']}->{sh['location']} without an establishing beat")
        if st_a["money"]["sent_total"] < st_b["money"]["sent_total"]:
            w.append(f"{sh['id']}: money state went backwards")
        if sh["treatment"] == "procedural" and sh["procedural"]["type"] in ("stack",) and st_a["money"]["sent_total"] and \
                abs(sum(i["value"] for i in sh["procedural"]["data"]["items"]) - st_a["money"]["sent_total"]) > 1 and sh["procedural"]["data"].get("cumulative", True):
            w.append(f"{sh['id']}: stack total does not match story state ({st_a['money']['sent_total']})")
        prev = sh
    return w
