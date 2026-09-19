"""Visual Director: annotated story -> validated SHOT PLAN (the DSL the deterministic renderer executes).

Not a template: every decision is derived from THIS story's segments (phase, importance, emotion, speaker, on-screen UI, amounts,
psychology mechanism) through the domain pack's visual grammars, then made varied by an anti-repetition pass. LLMs never
touch this stage - it is pure, deterministic and re-runnable (`--from-plan` re-renders the saved plan without any LLM).

Per shot it decides: purpose, treatment (performance | insert_ui | procedural), what to show, camera (size/move/subject/shake),
lighting mood, Grease Pencil effects (with timing), transitions, sound cues, and the story state before/after.
"""
from engine.animation import grammar as MG
from engine.camera import grammar as CG
from engine.characters import dna as DNA
from engine.dsl import variation as VAR
from engine.factory import procedural as PR, state as S
from engine.factory.domain import cue_hits

LEAD, TAIL = 0.12, 0.30
MAX_LEN = dict(performance=8.5, insert_ui=6.0, procedural=9.0)
SIZE_BY_PHASE = dict(HOOK="medium", SETUP="wide", INCITING="medium", ESCALATION="close", COMPLICATION="close", CLIMAX="ecu",
                     REVEAL="ecu", EXPLANATION="medium", PAYOFF="medium")
MOVE_BY_PHASE = dict(HOOK="push", SETUP="drift", INCITING="push", ESCALATION="push", COMPLICATION="push", CLIMAX="push",
                     REVEAL="hold", EXPLANATION="hold", PAYOFF="pull")
MOOD_BY_PHASE = dict(HOOK="neutral", SETUP="neutral", INCITING="formal", ESCALATION="pressure", COMPLICATION="fear", CLIMAX="fear",
                     REVEAL="isolated", EXPLANATION="neutral", PAYOFF="relief")
SHAKE_BY_MOOD = dict(neutral=0.45, formal=0.3, pressure=0.9, fear=1.8, isolated=0.5, dim=0.4, warm=0.4, bright=0.5, relief=0.35)
ALT_SIZE = dict(wide=["medium"], medium=["close", "wide"], close=["medium", "ecu"], ecu=["close"])
ALT_MOVE = dict(push=["drift", "hold"], pull=["hold", "drift"], hold=["push", "drift"], drift=["push", "hold"])


def _dur(seg):
    return seg["end"] - seg["start"]


def decide(dom, seg, ctx):
    """-> (kind, key, params) for one segment."""
    tg = seg["tags"]
    if tg["ui"] and tg["ui"]["screen"] in dom["cues"]["ui"] or (tg["ui"] and tg["ui"]["screen"] == "in_call"):
        n = ctx["ui_counts"].get(tg["ui"]["screen"], 0)
        if n < dom["cues"]["ui_limits"].get(tg["ui"]["screen"], 99) and seg["phase"] in dom["cues"]["ui_phases"].get(tg["ui"]["screen"], [seg["phase"]]):
            ctx["ui_counts"][tg["ui"]["screen"]] = n + 1
            return "insert_ui", ("ui", tg["ui"]["screen"]), dict(screen=tg["ui"]["screen"], data=tg["ui"]["data"])
    if seg["phase"] == "EXPLANATION" and tg["psychology"]:
        mech = tg["psychology"][0]
        gram = dom.grammar(mech)
        proc = (gram or {}).get("procedural") or []
        proc = [p for p in proc if p in PR.RENDERERS]
        if proc:
            return "procedural", ("psy", mech), dict(mechanism=mech, type=proc[0], grammar=dom.psych(mech)["grammar"])
    if seg["phase"] == "PAYOFF" and tg.get("advice", []):
        return "procedural", ("advice",), dict(type="checklist")
    for a in tg["amounts"]:
        if a["kind"] == "sent" and seg["tags"]["importance"] >= 3:
            return "procedural", ("sent", len(ctx["state"]["money"]["sent"])), dict(type="stack", amount=a["value"])
        if a["kind"] == "lost":
            return "procedural", ("lost",), dict(type="counter", amount=a["value"])
        if a["kind"] == "threshold" and 5 <= a["value"] <= 180:
            return "procedural", ("countdown", a["value"]), dict(type="countdown", minutes=a["value"])
    return "performance", ("perf",), {}


def plan_characters(dom, analysis, story_id):
    """Story characters -> DNA (deterministic in story_id + character id). Off-screen voices get no DNA."""
    out = {}
    arche = dom["character_archetypes"]
    for c in analysis["characters"]:
        if not c["on_screen"]:
            continue
        role, g, age = c["role"], c["gender"], c["age"]
        key = "m" if g == "m" else "f" if g == "f" else "unknown"
        if role == "protagonist":
            a = arche["protagonist_young"][key] if age == "young" and "protagonist_young" in arche else arche["protagonist"][key]
        elif role == "family":
            a = arche["family"][(key + "_elder") if age == "elder" and key != "unknown" else key]
        else:
            a = arche.get(role) or arche["other"]
        if not a:
            continue
        gender = {"m": "male", "f": "female"}.get(key)
        out[c["id"]] = dict(name=c["name"], role=role, dna=DNA.make(a, f"{story_id}:{c['id']}", gender=gender), description=c["description"])
    return out


def build_shots(dom, analysis, segs, log=print, story_id="story"):
    warnings = []
    chars = {c["id"]: c for c in analysis["characters"]}
    prot = next((c for c in analysis["characters"] if c["role"] == "protagonist" and c["on_screen"]), None)
    if prot is None:
        warnings.append("no on-screen protagonist: performance shots will use the first on-screen character")
        prot = next((c for c in analysis["characters"] if c["on_screen"]), None)
    st = S.initial(analysis)
    ui_counts = {}
    first_loc = next((s["tags"]["location"] for s in segs if s["tags"]["location"]), dom.env_kinds()[0])
    loc = first_loc
    # ---- 1. per-segment decision with running state
    rows = []
    for seg in segs:
        before = st
        if seg["tags"]["location"]:
            loc = seg["tags"]["location"]
        st = S.advance(st, seg)
        kind, key, params = decide(dom, seg, dict(state=st, ui_counts=ui_counts))
        rows.append(dict(seg=seg, kind=kind, key=key, params=params, loc=loc, before=before, after=st))
    # ---- 2. merge consecutive rows that share treatment/key/location into shots
    groups, cur = [], None
    for r in rows:
        dur_now = (r["seg"]["end"] - cur["rows"][0]["seg"]["start"]) if cur else 0
        important = r["seg"]["tags"]["importance"] >= 5 and r["kind"] == "performance"
        if cur and cur["kind"] == r["kind"] and cur["key"] == r["key"] and cur["loc"] == r["loc"] and dur_now < MAX_LEN[r["kind"]] and not important \
                and (r["kind"] != "performance" or r["seg"]["phase"] == cur["rows"][0]["seg"]["phase"]):
            cur["rows"].append(r)
        else:
            cur = dict(kind=r["kind"], key=r["key"], loc=r["loc"], rows=[r])
            groups.append(cur)
    # ---- 3. shot records
    shots = []
    holding, at_ear = False, False
    for gi, g in enumerate(groups):
        ss = [r["seg"] for r in g["rows"]]
        first, last = g["rows"][0], g["rows"][-1]
        phase = ss[0]["phase"]
        imp = max(s["tags"]["importance"] for s in ss)
        mech = next((m for s in ss for m in s["tags"]["psychology"]), None)
        mood = (dom.grammar(mech) or {}).get("lighting") if mech and phase != "EXPLANATION" else None
        mood = mood if mood in dom["lighting_moods"] else MOOD_BY_PHASE.get(phase, "neutral")
        hold0, ear0 = holding, at_ear
        sh = dict(id=f"S{gi + 1:03d}", segs=[s["id"] for s in ss], phase=phase, treatment=g["kind"], location=g["loc"], importance=imp,
                  mechanism=mech, lighting=dict(mood=mood, pressure=round(last["after"]["pressure"], 2)),
                  t0=ss[0]["start"] - LEAD, t1=ss[-1]["end"] + TAIL, gp=[], sfx=[], captions=True, transition_in="cut",
                  purpose=f"{phase.lower()}: " + (ss[0]["tags"]["visual_note"] or ss[0]["text"][:60]),
                  state_before=first["before"], state_after=last["after"], actions=[], character=None, camera={})
        if g["kind"] == "performance":
            ch = prot
            named = [c for s in ss for c in s["tags"]["characters"]]
            for c in analysis["characters"]:
                if c["on_screen"] and c["id"] != (prot or {}).get("id") and any(c["name"].lower() in n.lower() or n.lower() in c["name"].lower() for n in named) \
                        and not any(prot and (prot["name"].lower() in n.lower()) for n in named):
                    ch = c
            sh["character"] = ch["id"] if ch else None
            sh["cast"] = ch["cast"] if ch else None
            sh["outfit"] = ch["outfit"] if ch else None
            sh["emotion"] = ss[0]["tags"]["emotion"]
            sh["emotion_end"] = ss[-1]["tags"]["emotion"] if ss[-1]["tags"]["emotion"] != ss[0]["tags"]["emotion"] else None
            sh["camera"] = dict(size=SIZE_BY_PHASE.get(phase, "medium"), move=MOVE_BY_PHASE.get(phase, "push"), subject="eyes",
                                shake=SHAKE_BY_MOOD.get(mood, 0.5) + 0.8 * last["after"]["pressure"])
            # acting verbs from the story, in narration time
            for s in ss:
                t = s["start"]
                v = s["tags"]["action"]
                if s["tags"]["speaker"] == "caller" and not at_ear and s["phase"] in ("INCITING", "ESCALATION", "COMPLICATION", "CLIMAX"):
                    if not holding:
                        sh["actions"].append(dict(verb="pickup_phone", t=t, dur=1.0)); holding = True
                    sh["actions"].append(dict(verb="phone_to_ear", t=t + 1.0, dur=1.0)); at_ear = True
                if v in dom["verbs"] and v != "idle":
                    if v in ("read_phone", "phone_to_ear") and not holding:
                        sh["actions"].append(dict(verb="pickup_phone", t=t, dur=1.2)); holding = True
                    if v == "pickup_phone":
                        holding = True
                    if v == "phone_down":
                        holding = at_ear = False
                    if v == "phone_to_ear":
                        at_ear = True
                    sh["actions"].append(dict(verb=v, t=t + (0.6 if v == "pickup_phone" else 0.25), dur=min(_dur(s), 3.0)))
                if s["tags"]["importance"] >= 4 and s["tags"]["emotion"] in ("shock", "fear"):
                    sh["actions"].append(dict(verb="startle", t=t + 0.4, dur=1.0))
                elif s["tags"]["importance"] >= 4 and s["tags"]["emotion"] in ("uneasy", "concerned", "suspicious"):
                    sh["actions"].append(dict(verb="hesitate", t=t + 0.3, dur=1.2))
            if sh["actions"] and any(a["verb"] in ("pickup_phone", "read_phone") for a in sh["actions"]):
                holding = True
            sh["phone"] = dict(holding=holding, at_ear=at_ear)
            sh["state_before"] = dict(sh["state_before"], holding_phone=hold0, phone_at_ear=ear0)
            sh["state_after"] = dict(sh["state_after"], holding_phone=holding, phone_at_ear=at_ear)
        elif g["kind"] == "insert_ui":
            p = first["params"]
            sh["ui"] = dict(screen=p["screen"], data=_ui_data(p["screen"], p["data"], last["after"], analysis, ss))
            sh["camera"] = dict(size="insert", move="push", subject="phone", shake=0.0)
            sh["state_before"] = dict(sh["state_before"], holding_phone=hold0, phone_at_ear=ear0)
            sh["state_after"] = dict(sh["state_after"], holding_phone=holding, phone_at_ear=at_ear)
            sh["gp"].append(dict(effect="ring", start=0.5, duration=1.0, anchor="ui", intensity=0.9, relationship="highlights the key element of the screen"))
        else:
            p = first["params"]
            sh["procedural"] = dict(type=p["type"], data=_proc_data(p, g, last["after"], analysis, ss))
            sh["camera"] = dict(size="graphic", move="hold", subject="graphic", shake=0.0)
            sh["state_before"] = dict(sh["state_before"], holding_phone=hold0, phone_at_ear=ear0)
            sh["state_after"] = dict(sh["state_after"], holding_phone=holding, phone_at_ear=at_ear)
        shots.append(sh)
    # ---- 4. cross-shot design: transitions, GP, sound, variety, pacing
    _design(dom, shots, analysis, warnings)
    chars = plan_characters(dom, analysis, story_id)
    _compose(dom, shots, segs, chars, story_id)
    return shots, warnings, chars


def _ui_data(screen, data, after, analysis, ss):
    d = dict(data or {})
    if screen in ("incoming_call", "in_call"):
        d.setdefault("name", "बैंक")
    if screen == "bank_transfer":
        amt = next((a["value"] for s in ss for a in s["tags"]["amounts"] if a["kind"] == "sent"), None) or (after["money"]["sent"][-1] if after["money"]["sent"] else 0)
        d.update(amount=amt, to="सुरक्षित खाता", note="अस्थायी", pressed=True)
    if screen == "debit_alerts":
        d["items"] = [dict(amount=a) for a in after["money"]["sent"]] or d.get("items", [])
    if screen == "sms":
        d.setdefault("sender", "अज्ञात नंबर")
        d.setdefault("text", ss[0]["text"])
    return d


def _proc_data(p, g, after, analysis, ss):
    t = p["type"]
    if t == "stack":
        labels = ["पहली बार", "दूसरी बार", "तीसरी बार", "चौथी बार"]
        items = [dict(label=labels[i] if i < len(labels) else f"{i + 1} बार", value=v) for i, v in enumerate(after["money"]["sent"])]
        return dict(items=items, cumulative=True)
    if t == "counter":
        return dict(label=ss[0]["text"][:60] if False else "खाते से गायब रकम", **{"from": 0}, to=p["amount"], tone="alert", sub=None)
    if t == "countdown":
        mins = p.get("minutes") or next((e["value"] for e in analysis.get("financial_events", []) if e["kind"] == "threshold" and 5 <= e["value"] <= 180), 30)
        return dict(total_seconds=mins * 60, label=f"सिर्फ़ {int(mins)} मिनट", to_seconds=mins * 60 * 0.3)
    if t == "authority_ladder":
        return dict(levels=[dict(label="बैंक कर्मचारी"), dict(label="सीनियर अधिकारी"), dict(label="पुलिस / जाँच")])
    if t == "network_cut":
        return dict(center=next((c["name"] for c in analysis["characters"] if c["role"] == "protagonist"), ""), nodes=["परिवार", "दोस्त", "सहकर्मी", "बैंक"])
    if t == "tunnel":
        return dict(focus_label="सिर्फ़ फ़ोन")
    if t == "checklist":
        items = []
        for s in ss:
            items += s["tags"].get("advice", [])
        return dict(title="अगली बार क्या करें", items=items[:4] or ["फ़ोन काटें"])
    if t == "timeline":
        return dict(total_minutes=47, events=[])
    return {}


def _design(dom, shots, analysis, warnings):
    prev = None
    sigs = []
    for i, sh in enumerate(shots):
        # transitions
        if i == 0:
            sh["transition_in"] = "fade"
        elif sh["phase"] != shots[i - 1]["phase"] and sh["phase"] in ("REVEAL", "EXPLANATION", "PAYOFF"):
            sh["transition_in"] = "dip" if sh["phase"] == "REVEAL" else "dissolve"
        elif sh["treatment"] != shots[i - 1]["treatment"] and sh["treatment"] == "procedural":
            sh["transition_in"] = "dissolve"
        # establishing: new location -> wide first
        if sh["treatment"] == "performance" and prev and prev["treatment"] == "performance" and prev["location"] != sh["location"]:
            sh["camera"]["size"] = "wide"
            sh["time_jump"] = True
        elif sh["treatment"] == "performance" and (prev is None or all(p["treatment"] != "performance" or p["location"] != sh["location"] for p in shots[:i])) and sh["phase"] != "HOOK":
            sh["camera"]["size"] = "wide"
        # Grease Pencil by story function
        if sh["treatment"] == "performance":
            if sh["lighting"]["mood"] in ("fear",) and sh["importance"] >= 3:
                sh["gp"].append(dict(effect="worry", start=(sh["t1"] - sh["t0"]) * 0.35, duration=1.0, anchor="temple", intensity=0.9, relationship="tension near the subject's head"))
            if sh["phase"] == "REVEAL" and sh["importance"] >= 4:
                sh["gp"].append(dict(effect="ticks", start=0.3, duration=0.75, anchor="eyes", intensity=0.95, relationship="the jolt of realization"))
            if any(a["verb"] in ("pickup_phone", "read_phone") for a in sh["actions"]):
                sh["gp"].append(dict(effect="rays", start=0.8, duration=min(3.0, sh["t1"] - sh["t0"]), anchor="phone", intensity=0.34, relationship="light from the held screen"))
        _semantic_fx(dom, sh, i, shots)
        if sh["treatment"] == "insert_ui" and sh["ui"]["screen"] == "incoming_call":
            sh["gp"].append(dict(effect="arcs", start=0.0, duration=1.6, anchor="ui_top", intensity=0.9, relationship="the phone vibrating"))
            sh["sfx"] += [dict(kind="buzz", at=0.0, gain=0.8), dict(kind="ding", at=0.02, gain=0.55), dict(kind="buzz", at=0.9, gain=0.7)]
        if sh["treatment"] == "insert_ui" and sh["ui"]["screen"] == "debit_alerts":
            n = len(sh["ui"]["data"].get("items", []))
            sh["sfx"] += [dict(kind="ding", at=0.35 * k, gain=0.6) for k in range(n)]
        if sh["treatment"] == "insert_ui" and sh["ui"]["screen"] == "bank_transfer":
            sh["sfx"].append(dict(kind="tick", at=1.4, gain=0.8))
        if sh["treatment"] == "procedural" and sh["procedural"]["type"] == "countdown":
            n = int(sh["t1"] - sh["t0"])
            sh["sfx"] += [dict(kind="tick", at=float(k), gain=0.5) for k in range(n)]
        if sh["phase"] == "REVEAL" and (i == 0 or shots[i - 1]["phase"] != "REVEAL"):
            sh["sfx"] += [dict(kind="impact", at=0.15, gain=0.7), dict(kind="heartbeat", at=0.6, gain=0.7)]
        if sh["transition_in"] in ("cut", "dissolve") and i:
            sh["sfx"].append(dict(kind="whoosh", at=-0.05, gain=0.25 if sh["transition_in"] == "cut" else 0.35))
        # variety: never repeat the same (treatment, location, size, move) three times running; alternate sizes/moves
        sig = (sh["treatment"], sh["location"], sh["camera"].get("size"), sh["camera"].get("move"))
        if sh["treatment"] == "performance" and len(sigs) >= 2 and sigs[-1] == sig and sigs[-2] == sig:
            alt = next((s for s in ALT_SIZE.get(sig[2], []) if s != sig[2]), None)
            if alt:
                sh["camera"]["size"] = alt
            sh["camera"]["move"] = ALT_MOVE.get(sig[3], ["hold"])[0]
            sig = (sh["treatment"], sh["location"], sh["camera"]["size"], sh["camera"]["move"])
        if sh["treatment"] == "performance" and sigs and sigs[-1][:3] == sig[:3] and sigs[-1][3] == sig[3]:
            sh["camera"]["move"] = ALT_MOVE.get(sig[3], ["hold"])[0]
        sigs.append(sig)
        prev = sh
    # size rhythm: framing must breathe. ECU is a peak, not a state; the same size never repeats back-to-back within a scene.
    last = None
    chain = 0
    for sh in shots:
        if sh["treatment"] != "performance":
            last, chain = None, 0
            continue
        sz = sh["camera"]["size"]
        if last is not None and sz == last["camera"]["size"]:
            alts = {"ecu": ["close", "medium"], "close": ["medium", "ecu" if sh["importance"] >= 4 else "wide"], "medium": ["close", "wide"], "wide": ["medium"]}[sz]
            sh["camera"]["size"] = alts[chain % len(alts)]
            chain += 1
        elif last is not None and last["camera"]["size"] == "ecu" and sz == "close" and sh["importance"] < 4:
            sh["camera"]["size"] = "medium"
        else:
            chain = 0
        last = sh
    # continuous timeline: boundaries at the middle of narration gaps
    for a, b in zip(shots, shots[1:]):
        mid = 0.5 * ((a["t1"] - TAIL) + (b["t0"] + LEAD))
        a["t1"], b["t0"] = mid, mid
    shots[0]["t0"] = 0.0
    # repetition report
    run = 0
    for sh in shots:
        run = run + 1 if sh["treatment"] == "performance" else 0
        if run >= 7:
            warnings.append(f"{sh['id']}: {run} consecutive performance shots (repetitive stretch)")
            run = 0


def pause_plan(segs, shots):
    """Designed silences (seconds inserted BEFORE a segment): let the hook question, the reveal and the explanation land."""
    gaps = {}
    first_of = {}
    for sh in shots:
        first_of.setdefault(sh["phase"], sh["segs"][0])
    for ph, gap in (("SETUP", 0.7), ("REVEAL", 0.9), ("EXPLANATION", 0.7), ("PAYOFF", 0.6), ("CLIMAX", 0.4)):
        if ph in first_of:
            gaps[first_of[ph]] = gap
    for s in segs:
        if s["tags"]["importance"] >= 5:
            gaps.setdefault(s["id"], 0.5)
    return gaps


def _semantic_fx(dom, sh, i, shots):
    """Grease Pencil by MEANING (not by shot number): each effect names the story relationship it expresses."""
    add = lambda eff, start, dur, anchor, inten, why: sh["gp"].append(dict(effect=eff, start=round(start, 2), duration=round(dur, 2), anchor=anchor, intensity=inten, relationship=why))
    d = sh["t1"] - sh["t0"]
    mood, imp, phase, mech = sh["lighting"]["mood"], sh["importance"], sh["phase"], sh.get("mechanism")
    if sh["treatment"] == "performance":
        acts = {a["verb"] for a in sh["actions"]}
        if mood == "pressure" and imp >= 3:
            add("scribble", 0.4 * d, min(1.6, 0.5 * d), "head", 0.6, "mounting anxiety: thoughts racing under pressure")
        if mood == "isolated":
            add("dust", 0.0, d, "screen", 0.5, "quiet drifting time: being alone with the decision")
        if mood == "fear" and imp >= 4 and phase in ("REVEAL", "CLIMAX"):
            add("smoke", 0.2 * d, min(3.0, d), "low", 0.5, "unease rising in the room")
        if acts & {"pickup_phone"} and phase in ("INCITING", "ESCALATION"):
            add("arrow", 0.6, 1.2, "phone", 0.85, "attention pulled to the phone")
        if mech in ("social_proof", "fomo"):
            add("network", 0.2 * d, min(3.0, 0.7 * d), "top", 0.55, "everyone else is already in")
    if sh["treatment"] == "insert_ui":
        scr = sh["ui"]["screen"]
        if scr == "bank_transfer":
            add("money_flow", 0.9, 2.0, "ui", 0.8, "the money leaving the account")
        if scr in ("debit_alerts", "whatsapp_chat", "sms_thread"):
            add("underline", 0.7, 1.4, "ui", 0.85, "the detail that should have mattered")
    if i and sh["phase"] != shots[i - 1]["phase"] and sh["transition_in"] in ("dissolve",) and sh["phase"] == "EXPLANATION":
        add("sweep", 0.0, 0.7, "screen", 0.55, "hand-drawn wipe: the story steps back to explain")


MOOD_EMOTION_STYLE = dict(fear="fearful", fearful="fearful", uneasy="nervous", concerned="hesitant", shock="shocked", suspicious="suspicious", calm="relieved", smile="relieved",
                          happy="relieved", angry="angry", solemn="sad", driven="confident", explaining="confident", serious="neutral", blank="neutral", tired="sad")
CROWD_AFTER = {"office_day": "plant", "street_dusk": "lamp_tree", "bank_branch": "queue", "call_centre": "cubicles", "indian_living_room": "sofa", "atm_area": "glass"}
PROP_SLOT_ORDER = {"office_day": ["desk_left", "desk_right", "desk_center"], "street_dusk": ["parapet_left", "parapet_right"], "bank_branch": ["counter_left", "counter_right"],
                   "call_centre": ["desk_left", "desk_right"], "indian_living_room": ["table_left", "table_right"], "atm_area": ["shelf_left", "shelf_right"], "night_bedroom": ["nightstand"]}


def _compose(dom, shots, segs, chars, story_id):
    """Turn shot plan v1 fields into the full v2 DSL: environments, DNA character refs, props, crowd, semantic actions, camera intents."""
    by_id = {s["id"]: s for s in segs}
    hue_for = {}
    for sh in shots:
        if sh["treatment"] != "performance":
            continue
        base = dom["environments"][sh["location"]]["set"]
        loc = sh["location"]
        if loc not in hue_for:                                       # one variation per location per story: continuity within, difference between films
            hue_for[loc] = VAR.rng(story_id, loc, "hue").choice([-24, -12, 0, 12, 24]) if base in ("office_day", "street_dusk", "night_bedroom") else 0
        var = {"hue": hue_for[loc]} if base in ("office_day", "street_dusk", "night_bedroom") else {"palette": VAR.seed_int(story_id, loc, "pal") % 3}
        sh["environment"] = dict(family=base, variation=var, seed=VAR.seed_int(story_id, loc, "env"))
        sh["character_ref"] = sh["character"]
        sh["cast"] = sh["outfit"] = None
        text = " ".join(by_id[i]["text"] for i in sh["segs"])
        # props: only what the narration mentions, placed on the location's foreground surface
        slots = list(PROP_SLOT_ORDER.get(base, []))
        sh["props"] = []
        for prop in cue_hits(text, dom["cues"]["props"]):
            if slots:
                sh["props"].append(dict(prop=prop, at=slots.pop(0), scale=0.8, params={}))
        # crowd: ambient people, absent when the beat is about isolation, only in looser framings
        lo, hi = dom["crowd"]["counts"].get({"office": "office", "street": "street", "bank": "bank", "call_centre": "call_centre", "living_room": "living_room", "atm": "atm"}.get(loc, loc), [0, 0])
        if hi and sh["lighting"]["mood"] not in dom["crowd"]["no_crowd_moods"] and sh["camera"]["size"] in ("wide", "medium") and base in CROWD_AFTER:
            sh["crowd"] = dict(count=VAR.rng(story_id, loc, "crowd").randint(lo, hi), seed=VAR.seed_int(story_id, loc, "crowdseed"), after=CROWD_AFTER[base])
        # semantic actions: the story's emotion picks the performance style, importance sets intensity
        style = MOOD_EMOTION_STYLE.get(sh.get("emotion_end") or sh["emotion"], "neutral")
        acts = []
        for a in sh["actions"]:
            legacy = a.get("verb") or a.get("action")                # keep the story-level verb: continuity + holding-state logic reads it
            if legacy == "pickup_phone" and sh["state_before"]["holding_phone"]:
                continue                                             # continuity: the phone is already in her hand - don't pick it up a second time
            name = {"pickup_phone": "reach_for_phone"}.get(legacy, legacy)
            acts.append(dict(action=name, verb=legacy, t=a["t"], dur=a["dur"], emotion=style, intensity=round(min(1.0, sh["importance"] / 5.0), 2)))
        sh["actions"] = acts
        sh["camera"]["intent"] = CG.intent_for(sh["lighting"]["mood"], sh.get("emotion_end") or sh["emotion"], sh["phase"], sh["importance"])
        sh["camera"]["size_locked"] = True
