"""Topic -> validated PLAN (DSL v3). No human authors the result.

Pipeline (each stage is auditable; everything the LLMs return is untrusted input):
  0. FIT      (qwen3:14b, schema-constrained)  can this topic be depicted with the library?
  1. WRITE    (gemma4:12b, Hindi)              narration beats + visual ideas
     - validated: Devanagari ratio, words/beat, total duration estimate; re-prompted with
       concrete feedback if out of range
  2. DIRECT   (qwen3:14b, JSON-schema enums)   per-beat set/pose/face/camera/card choices
  3. REPAIR   (pure code)                       coerce to library, enforce pacing/variety
       rules, cap set changes, guarantee a hook framing, drop unsupported combos
  Fallback: if a model call fails validation repeatedly, deterministic heuristics fill in and the
  report says so. The compiler (film.py) executes ONLY the repaired plan.
"""
import json
import re
import urllib.request

from engine.shorts import library as L, sets

OLLAMA = "http://localhost:11434/api/chat"
WRITER = "gemma4:12b-mlx"
DIRECTOR = "qwen3:14b"
WPS = 2.25                      # measured Chatterbox-hi pace: ~136 wpm
DEVA = re.compile(r"[ऀ-ॿ]")


def _chat(model, prompt, schema=None, temperature=0.6, timeout=900):
    body = {"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False, "think": False,
            "options": {"temperature": temperature, "num_ctx": 8192, "seed": 7}}
    if schema:
        body["format"] = schema
    req = urllib.request.Request(OLLAMA, json.dumps(body).encode(), {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=timeout))["message"]["content"]


def _json(text):
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1)
    a, b = text.find("{"), text.rfind("}")
    return json.loads(text[a:b + 1])


def _deva_ratio(s):
    letters = [c for c in s if c.isalpha()]
    return sum(1 for c in letters if DEVA.match(c)) / max(len(letters), 1)


# ------------------------------------------------------------------ stage 0
def assess_fit(topic, report, log):
    schema = {"type": "object", "properties": {"fit": {"type": "string", "enum": ["scene", "mixed", "cards_only"]},
                                               "reason": {"type": "string"},
                                               "primary_set": {"type": "string", "enum": L.SET_IDS},
                                               "secondary_set": {"type": "string", "enum": ["none"] + L.SET_IDS}},
              "required": ["fit", "reason", "primary_set", "secondary_set"]}
    prompt = (f"A video generator can ONLY show: a modern-day young person/older man/young woman (chest-up cartoon) in one of "
              f"these places, plus text 'concept cards'.\n{L.catalog_text()}\n\nTopic: \"{topic}\".\n"
              "fit=scene: relatable modern everyday story (habits, phones, money, work, sleep, relationships) that the "
              "character+places can carry. fit=mixed: partly abstract/statistical - mix scenes and cards. fit=cards_only: "
              "needs visuals we do not have (mythology, history, science phenomena, animals, war, other countries, "
              "period costumes...). Answer honestly. Also choose primary_set = the ONE location where most of this story happens "
              "(work/money/pressure -> office_day; sleep/night/private worries -> night_bedroom; outdoors/reflection/city -> street_dusk) "
              "and secondary_set = one other location only if the story clearly moves there, else none.")
    try:
        r = _json(_chat(DIRECTOR, prompt, schema, 0.1))
        fit, why = r["fit"], r["reason"]
        loc = [r["primary_set"]] + ([r["secondary_set"]] if r["secondary_set"] in sets.SETS and r["secondary_set"] != r["primary_set"] else [])
    except Exception as e:                                        # pragma: no cover
        fit, why, loc = "mixed", f"fit check failed ({e}); defaulting to mixed", ["office_day"]
    report["fit"] = dict(level=fit, reason=why[:300], sets=loc)
    log(f"[plan] topic fit: {fit}; sets {loc} - {why[:160]}")
    return fit, loc


# ------------------------------------------------------------------ stage 1
def write_script(topic, duration, report, log, attempts=3):
    n_words = round(duration * WPS)
    n_beats = max(6, round(duration / 4.4))
    feedback = ""
    best = None
    for k in range(attempts):
        prompt = (
            "You are a Hindi YouTube Shorts scriptwriter. Write spoken, conversational everyday Hindi in Devanagari "
            "(simple words a 16-year-old uses; avoid English words unless unavoidable).\n"
            f"Topic: {topic}\nLength: about {duration} seconds when read aloud = about {n_words} words in total, split into "
            f"exactly {n_beats} beats. Each beat is ONE spoken phrase or sentence of 6-14 words.\n"
            "Structure: beat 1 = HOOK (a surprising specific moment, claim or question - no greeting, no 'दोस्तों'), then setup, "
            "escalation, a turn/insight, payoff, and the last beat = one memorable takeaway.\n"
            "Tell it through ONE concrete protagonist with a Hindi first name and specific details (time, place, object) "
            "instead of lecturing. Do not invent statistics or facts; use only widely-known numbers, or none.\n"
            f"{feedback}"
            'Return ONLY JSON: {"title": "short Hindi title", "protagonist": {"name": "...", "kind": "young_man|young_woman|older_man"}, '
            '"beats": [{"text": "...", "role": "hook|setup|escalation|turn|payoff|takeaway", "visual_idea": "one English sentence: what the viewer sees"}]}')
        try:
            data = _json(_chat(WRITER, prompt, None, 0.7 - 0.15 * k))
            beats = [b for b in data["beats"] if isinstance(b.get("text"), str) and b["text"].strip()]
            problems = []
            tot = sum(len(b["text"].split()) for b in beats)
            if len(beats) < 5:
                problems.append(f"only {len(beats)} beats; need {n_beats}")
            bad = [b["text"] for b in beats if _deva_ratio(b["text"]) < 0.8]
            if bad:
                problems.append("these beats are not Devanagari Hindi: " + " | ".join(bad[:3]))
            if not (0.75 * n_words <= tot <= 1.3 * n_words):
                problems.append(f"total {tot} words; target {n_words}")
            if best is None or len(problems) < best[1]:
                best = (data, len(problems))
            if not problems:
                report["writer_attempts"] = k + 1
                return data
            feedback = "FIX THESE PROBLEMS FROM YOUR LAST ATTEMPT: " + "; ".join(problems) + ".\n"
            log(f"[plan] writer attempt {k + 1}: {'; '.join(problems)}")
        except Exception as e:
            feedback = f"Your last output was not valid JSON ({type(e).__name__}). Return only the JSON object.\n"
            log(f"[plan] writer attempt {k + 1} failed: {e}")
    if best is None:
        raise RuntimeError("writer produced no usable script")
    report["writer_attempts"] = attempts
    report.setdefault("warnings", []).append("script did not fully satisfy length/language checks after retries")
    return best[0]


# ------------------------------------------------------------------ stage 2
def _director_schema(n):
    S = lambda enum: {"type": "string", "enum": enum}
    beat = {"type": "object", "properties": {
        "kind": S(["scene", "card"]), "set": S(L.SET_IDS), "body": S(list(L.BODIES)), "face": S(list(L.FACES)),
        "face_end": S(["none"] + list(L.FACES)), "pivot_word": {"type": "integer"}, "look": S(L.LOOKS),
        "size": S(list(L.SIZES)), "move": S(list(L.MOVES)), "act": S(L.ACTS),
        "phone_title": {"type": "string"}, "phone_body": {"type": "string"}, "phone_time": {"type": "string"},
        "card_style": S(list(L.CARD_STYLES)), "card_big": {"type": "string"}, "card_small": {"type": "string"},
        "card_icon": S(L.ICONS), "card_tone": S(L.TONES), "card_items": {"type": "array", "items": {"type": "string"}},
        "card_left": {"type": "string"}, "card_right": {"type": "string"}},
        "required": ["kind", "set", "body", "face", "face_end", "pivot_word", "look", "size", "move", "act"]}
    return {"type": "object", "properties": {"beats": {"type": "array", "items": beat, "minItems": n, "maxItems": n}},
            "required": ["beats"]}


def direct(topic, script, fit, loc, report, log):
    beats = script["beats"]
    listing = "\n".join(f"{i + 1}. [{b.get('role', '')}] \"{b['text']}\"  (visual idea: {b.get('visual_idea', '')})" for i, b in enumerate(beats))
    guide = {"scene": "Use mostly kind=scene; at most 1-2 cards (a striking number or a closing takeaway).",
             "mixed": "Exactly 2 or 3 beats MUST be kind=card (a striking number, a comparison, the takeaway); the rest scenes.",
             "cards_only": "kind=card for every beat except possibly the hook."}[fit]
    prompt = (
        "You are the director of a vertical animated Short. For EACH numbered narration beat choose how it is shown, using ONLY "
        f"the library below.\n{L.catalog_text()}\n\nTopic: {topic}\nProtagonist: {script.get('protagonist')}\n"
        f"Beats:\n{listing}\n\nRules: {guide} Keep the same set for consecutive beats unless the story moves place (max 3 set "
        "changes overall); night stories use night_bedroom, work/money/pressure use office_day, outdoors/reflection use street_dusk. "
        "Choose the pose (body) that matches what the person is DOING in that beat and a face that matches the emotion; use "
        "face_end + pivot_word (index of the spoken word where the emotion changes) for a beat with a turn, else face_end=none. "
        "Vary size across beats (hook = close or medium, never wide; ecu only for the peak; wide once to establish). Use phone_title/"
        "phone_body/phone_time (short Hindi text) ONLY when body=device and a message arrives in that beat, else empty strings. "
        "For card beats fill the card_* fields with SHORT Hindi text (big <= 14 characters), else leave them empty.")
    for k in range(3):
        try:
            out = _json(_chat(DIRECTOR, prompt, _director_schema(len(beats)), 0.3 + 0.2 * k))
            if len(out["beats"]) == len(beats):
                report["director_attempts"] = k + 1
                return out["beats"]
        except Exception as e:
            log(f"[plan] director attempt {k + 1} failed: {e}")
    report.setdefault("warnings", []).append("director failed 3x - heuristic fallback used for all visual choices")
    report["director_attempts"] = 3
    return None


def card_for(text, topic, log):
    """Ask the director for the card that best carries one narration beat (schema-constrained)."""
    S = lambda enum: {"type": "string", "enum": enum}
    schema = {"type": "object", "properties": {"style": S(list(L.CARD_STYLES)), "big": {"type": "string"}, "small": {"type": "string"},
                                               "icon": S(L.ICONS), "tone": S(L.TONES), "items": {"type": "array", "items": {"type": "string"}},
                                               "left": {"type": "string"}, "right": {"type": "string"}},
              "required": ["style", "big", "small", "icon", "tone", "items", "left", "right"]}
    prompt = (f"Make ONE concept card for a Hindi Short about '{topic}'. The narrator says: \"{text}\". Card styles: "
              + "; ".join(f"{k} = {v}" for k, v in L.CARD_STYLES.items()) + ". Text must be SHORT Hindi (big <= 14 characters; "
              "small <= 8 words) and must restate or sharpen what the narrator says - never add new facts or numbers.")
    try:
        r = _json(_chat(DIRECTOR, prompt, schema, 0.3))
        return dict(style=r["style"], icon=r["icon"], tone=r["tone"], big=r["big"].strip(), small=r["small"].strip(),
                    items=[x for x in r["items"] if x.strip()][:3], left=r["left"].strip(), right=r["right"].strip(),
                    title=r["big"].strip() if r["style"] == "list" else "")
    except Exception as e:
        log(f"[plan] card_for failed ({e}); quoting narration")
        return dict(style="title", icon="question", tone="info", big=text.split("।")[0][:28], small="", items=[], left="", right="", title="")


# ------------------------------------------------------------------ stage 3
FACE_BY_ROLE = {"hook": "concerned", "setup": "tired", "escalation": "uneasy", "turn": "shock", "payoff": "calm", "takeaway": "smile",
                "interruption": "tired", "attention": "blank", "curiosity": "concerned", "unease": "serious", "realization": "uneasy"}
SIZE_BY_ROLE = {"hook": "close", "setup": "medium", "escalation": "medium", "turn": "close", "payoff": "medium", "takeaway": "medium",
                "interruption": "wide", "attention": "medium", "curiosity": "medium", "unease": "medium", "realization": "ecu"}


def _score_set(text, sid):
    good = set(re.findall(r"[a-z]+", (sets.SETS[sid]["good_for"] + " " + sets.SETS[sid]["desc"]).lower()))
    return len(good & set(re.findall(r"[a-z]+", text.lower())))


def repair(topic, script, fit, loc, raw, report, seed, log):
    beats, rep = script["beats"], report.setdefault("repairs", [])
    note = lambda s: (rep.append(s), log(f"[plan] repair: {s}"))
    out = []
    raw = raw or [{} for _ in beats]
    for i, (b, r) in enumerate(zip(beats, raw)):
        role = b.get("role") if b.get("role") in L.ROLES else ("hook" if i == 0 else "takeaway" if i == len(beats) - 1 else "escalation")
        words = b["text"].split()
        kind = r.get("kind", "scene")
        if fit == "cards_only" and i > 0:
            kind = "card"
        sc = dict(set=r.get("set"), body=r.get("body"), face=r.get("face"), face_end=r.get("face_end"), look=r.get("look"),
                  size=r.get("size"), move=r.get("move"), act=r.get("act"), pivot_word=r.get("pivot_word", len(words) // 2))
        if sc["set"] not in loc:
            note(f"beat {i + 1}: set {sc['set']} outside planned locations {loc} -> {loc[0]}")
            sc["set"] = loc[0]
        if sc["body"] not in L.BODIES:
            sc["body"] = "explaining"
        if sc["face"] not in L.FACES:
            sc["face"] = FACE_BY_ROLE[role]
        if sc["face_end"] in ("none", None) or sc["face_end"] not in L.FACES or sc["face_end"] == sc["face"]:
            sc["face_end"] = None
        if sc["look"] not in L.LOOKS:
            sc["look"] = "ahead"
        if sc["size"] not in L.SIZES:
            sc["size"] = SIZE_BY_ROLE[role]
        if sc["move"] not in L.MOVES:
            sc["move"] = "push"
        ARC = {"calm": "concerned", "happy": "concerned", "smile": "concerned", "tired": "concerned", "blank": "uneasy",
               "serious": "calm", "concerned": "uneasy", "uneasy": "calm", "shock": "solemn", "solemn": "calm", "driven": "serious"}
        if role == "payoff":      # payoffs resolve tension: arc toward relief, never toward worry
            RESOLVE = {"serious": "calm", "concerned": "calm", "uneasy": "calm", "tired": "smile", "blank": "smile",
                       "shock": "solemn", "fear": "calm", "suspicious": "calm", "driven": "smile"}
            if not sc["face_end"] and sc["face"] in RESOLVE and kind == "scene":
                sc["face_end"] = RESOLVE[sc["face"]]
                note(f"beat {i + 1}: payoff resolves {sc['face']}->{sc['face_end']}")
        elif role in ("escalation", "turn") and not sc["face_end"] and kind == "scene":
            sc["face_end"] = ARC.get(sc["face"], "concerned")
            note(f"beat {i + 1}: no emotion arc on a {role} beat -> {sc['face']}->{sc['face_end']}")
        sc["act"] = sc["act"] if sc["act"] in L.ACTS and sc["act"] != "none" else None
        sc["pivot_word"] = max(1, min(int(sc["pivot_word"] or 1), max(len(words) - 1, 1)))
        # phone message only for a device pose and only if fully specified
        pt, pb = (r.get("phone_title") or "").strip(), (r.get("phone_body") or "").strip()
        if sc["body"] == "device" and pt and pb:
            sc["phone"] = dict(title=pt[:22], body=pb[:44], time=(r.get("phone_time") or "2:47")[:5])
            if not sc["face_end"]:
                sc["face_end"] = "uneasy"
        ent = dict(id=f"b{i + 1}", text=b["text"].strip(), role=role, kind="scene")
        if kind == "card":
            style = r.get("card_style") if r.get("card_style") in L.CARD_STYLES else "title"
            card = dict(style=style, icon=r.get("card_icon") if r.get("card_icon") in L.ICONS else "question",
                        tone=r.get("card_tone") if r.get("card_tone") in L.TONES else "info")
            big, small = (r.get("card_big") or "").strip(), (r.get("card_small") or "").strip()
            items = [x for x in (r.get("card_items") or []) if isinstance(x, str) and x.strip()][:3]
            left, right = (r.get("card_left") or "").strip(), (r.get("card_right") or "").strip()
            if style == "versus" and not (left and right):
                style = card["style"] = "title"
            if style == "list" and not items:
                style = card["style"] = "title"
            if style in ("stat", "title") and not big:
                big = b["text"].split("।")[0][:28]
                note(f"beat {i + 1}: empty card text -> quoted the narration")
            if len(big) > 14 and style == "stat":
                card["style"] = "title"
            card.update(big=big, small=small, items=items, left=left, right=right, title=(r.get("card_big") or "").strip() if style == "list" else "")
            ent.update(kind="card", card=card)
        else:
            ent["scene"] = sc
        out.append(ent)

    # ---- act discipline: physical reactions are peak moments, not decoration
    acted = [e for e in out if e["kind"] == "scene" and e["scene"]["act"]]
    for e in acted[2:] + [e for e in acted[:2] if e["role"] not in ("turn", "escalation")]:
        e["scene"]["act"] = None
    if len(acted) > 2 or any(e["scene"]["act"] is None for e in acted):
        note(f"acts limited to peak beats ({len(acted)} requested)")

    # ---- card quota: ideas the scenes cannot carry go on cards
    need = 0 if script.get("story") else {"scene": 1, "mixed": 2, "cards_only": len(out) - 1}[fit]
    have = sum(1 for e in out if e["kind"] == "card")
    if have < need:
        cand = [e for e in reversed(out[1:]) if e["kind"] == "scene"]
        cand.sort(key=lambda e: {"takeaway": 0, "payoff": 1, "turn": 2}.get(e["role"], 3))
        for e in cand[:need - have]:
            card = card_for(e["text"], topic, log)
            e.pop("scene", None)
            e.update(kind="card", card=card)
            note(f"{e['id']}: converted to a card (fit={fit} needs >= {need})")

    # ---- global pacing / continuity rules
    if out[0]["kind"] == "scene" and out[0]["scene"]["size"] == "wide":
        out[0]["scene"]["size"] = "close"
        note("hook framing wide -> close (viewer must see a face immediately)")
    prev = None
    for e in out:
        if e["kind"] != "scene":
            prev = None
            continue
        if prev is not None and e["scene"]["size"] == prev and e["scene"]["size"] != "ecu":
            e["scene"]["size"] = {"medium": "close", "close": "medium", "wide": "medium"}[prev]
            note(f"{e['id']}: repeated size {prev} -> {e['scene']['size']}")
        if e["scene"]["size"] == "ecu" and e["scene"]["face_end"] not in ("shock", "fear", "awe") and e["scene"]["face"] not in ("shock", "fear", "awe"):
            e["scene"]["size"] = "close"
            note(f"{e['id']}: ecu without a peak emotion -> close")
        prev = e["scene"]["size"]
    scene_beats = [e for e in out if e["kind"] == "scene"]
    changes = sum(1 for a, b2 in zip(scene_beats, scene_beats[1:]) if a["scene"]["set"] != b2["scene"]["set"])
    if changes > 3:
        from collections import Counter
        major = Counter(e["scene"]["set"] for e in scene_beats).most_common(1)[0][0]
        for e in scene_beats:
            e["scene"]["set"] = major
        note(f"{changes} set changes > 3 -> single set {major}")
    return out


# ------------------------------------------------------------------ story mode
def parse_brief(path):
    """Brief = 'key: value' lines. It is INPUT (what the story is), never staging or DSL."""
    d = {}
    for line in open(path, encoding="utf-8"):
        if ":" in line and not line.startswith("#"):
            k, v = line.split(":", 1)
            d[k.strip()] = v.strip()
    name, _, kind = (d.get("protagonist", "Rahul | young_man")).partition("|")
    d["protagonist"] = dict(name=name.strip(), kind=(kind or "young_man").strip())
    d["ladder"] = [x.strip() for x in d["ladder"].split(",")]
    if "message" in d:
        t, _, b = d["message"].partition("|")
        d["message"] = dict(title=t.strip(), body=b.strip())
    return d


def write_story(brief, duration, report, log, attempts=3):
    ladder = brief["ladder"]
    n_words = round(duration * WPS * 0.82)                      # leave room for designed pauses
    feedback, best = "", None
    for k in range(attempts):
        prompt = (
            "You are a Hindi YouTube Shorts story writer. Write spoken, conversational Hindi in Devanagari (simple everyday words).\n"
            f"STORY PREMISE: {brief['premise']}\nTONE: {brief.get('tone', '')}\n"
            f"Protagonist: {brief['protagonist']['name']}. Write exactly {len(ladder)} beats, one per role, IN THIS ORDER: "
            + ", ".join(ladder) + f". About {n_words} words in total; every beat is ONE short spoken sentence of 5-13 words.\n"
            "Role meanings: hook = it is the middle of the night and his phone suddenly lights up in the dark (open with the mystery, "
            "not with scene-setting; no greeting); attention = he notices it, hesitates, then reaches for the phone; "
            "curiosity = he lifts it and reads: a message from an unknown number; unease = something about the message feels wrong; "
            "realization = he understands this is important and his life is about to change; "
            "takeaway = one understated closing line that leaves an open question.\n"
            "He lies in his BED (बिस्तर) inside his bedroom - never on a roof (छत). Say the time exactly in words as 'दो बजकर सैंतालीस मिनट' (the clock reads 2:47), never digits. "
            "Do not exaggerate. Do not reveal what the message says beyond the fact that it is from an unknown number and important.\n"
            f"{feedback}"
            'Return ONLY JSON: {"beats": [{"text": "...", "role": "<role>", "visual_idea": "one English sentence"}]}')
        try:
            data = _json(_chat(WRITER, prompt, None, 0.7 - 0.15 * k))
            beats = [b for b in data["beats"] if isinstance(b.get("text"), str) and b["text"].strip()]
            problems = []
            if len(beats) != len(ladder):
                problems.append(f"need exactly {len(ladder)} beats, got {len(beats)}")
            bad = [b["text"] for b in beats if _deva_ratio(b["text"]) < 0.8]
            if bad:
                problems.append("not Devanagari Hindi: " + " | ".join(bad[:3]))
            tot = sum(len(b["text"].split()) for b in beats)
            if not (0.7 * n_words <= tot <= 1.35 * n_words):
                problems.append(f"total {tot} words; target {n_words}")
            if any(re.search(r"[0-9]", b["text"]) for b in beats):
                problems.append("no digits: write numbers/times as Hindi words")
            if any("छत" in b["text"] for b in beats) and brief.get("location") == "night_bedroom":
                problems.append("he is in his bed, not on a roof (छत)")
            if best is None or len(problems) < best[1]:
                best = (data, len(problems))
            if not problems:
                report["writer_attempts"] = k + 1
                break
            feedback = "FIX THESE PROBLEMS FROM YOUR LAST ATTEMPT: " + "; ".join(problems) + ".\n"
            log(f"[plan] story writer attempt {k + 1}: {'; '.join(problems)}")
        except Exception as e:
            feedback = f"Your last output was not valid JSON ({type(e).__name__}). Return only the JSON object.\n"
            log(f"[plan] story writer attempt {k + 1} failed: {e}")
    if best is None:
        raise RuntimeError("story writer produced no usable script")
    data = best[0]
    beats = data["beats"][:len(ladder)]
    for b, role in zip(beats, ladder):                           # the ladder is authoritative, not the model's labels
        b["role"] = role
    return dict(title=brief.get("title", ""), protagonist=brief["protagonist"], beats=beats, story=True)


# What each story role REQUIRES on screen. The LLM proposes; these tables constrain it, because the
# acting recipes (film.py) depend on the pose/framing being right (e.g. the phone is on the nightstand
# until the 'curiosity' beat, so no earlier beat may hold it).
STORY_RULES = {
    # 'hug' is the same speckled sweater as 'device' -> no outfit jump when the phone reaches his hand.
    # 'calm' is deliberately absent: in Open Peeps it is a closed-eye smile, wrong for someone lying awake.
    "hook": dict(body=["hug"], faces=["tired", "blank"], size="close", move="push"),
    "setup": dict(body=["hug"], faces=["tired", "blank"], size="wide", move="hold"),      # establishes room + the dark phone on the nightstand
    "interruption": dict(body=["hug"], faces=["tired", "blank"], size="wide", move="hold"),
    "attention": dict(body=["hug"], faces=["blank", "concerned"], size="close", move="hold"),
    "curiosity": dict(body=["device"], faces=["serious", "blank"], size="medium", move="push"),
    "unease": dict(body=["device"], faces=["serious", "suspicious"], size="close", move="push", face_end="concerned"),   # closed mouth until the pivot: he is reading, not talking
    "realization": dict(body=["device"], faces=["uneasy"], size="ecu", move="push", face_end="shock"),
    "takeaway": dict(body=["device"], faces=["serious", "solemn"], size="close", move="pull"),
}


LAYERED_RULES = {          # role -> (face, face_end, pivot fraction). Body language comes from the rig, not from poses.
    "hook": ("tired", None, 0.5), "attention": ("blank", "concerned", 0.5), "curiosity": ("concerned", None, 0.5),
    "unease": ("serious", "concerned", 0.5), "realization": ("uneasy", "shock", 0.3), "takeaway": ("solemn", None, 0.5),
}


def apply_layered_rules(out, brief, note):
    for e in out:
        if e["kind"] != "scene" or e["role"] not in LAYERED_RULES:
            continue
        face, face_end, pv = LAYERED_RULES[e["role"]]
        sc = e["scene"]
        n = max(len(e["text"].split()), 2)
        if sc.get("face") != face:
            note(f"{e['id']} ({e['role']}): face {sc.get('face')} -> {face} (layered role rule)")
        sc.update(face=face, face_end=face_end, pivot_word=max(1, int(n * pv)), act=None)
        sc.pop("phone", None)
        if e["role"] == "curiosity" and brief.get("message"):
            sc["phone"] = dict(title=brief["message"]["title"][:22], body=brief["message"]["body"][:44], time="2:47")
        if e["role"] == "realization" and brief.get("punch"):
            sc["punch"] = brief["punch"]
    return out


def apply_story_rules(out, brief, note):
    if brief.get("rig", "layered") == "layered":
        return apply_layered_rules(out, brief, note)
    for e in out:
        rule = STORY_RULES.get(e["role"])
        if not rule or e["kind"] != "scene":
            continue
        sc = e["scene"]
        if sc["body"] not in rule["body"]:
            note(f"{e['id']} ({e['role']}): body {sc['body']} -> {rule['body'][0]} (role rule)")
            sc["body"] = rule["body"][0]
        if sc["face"] not in rule["faces"]:
            note(f"{e['id']} ({e['role']}): face {sc['face']} -> {rule['faces'][0]} (role rule)")
            sc["face"] = rule["faces"][0]
        sc["size"], sc["move"] = rule["size"], rule["move"]
        n = max(len(e["text"].split()), 2)
        sc["pivot_word"] = {"interruption": max(1, n - 3), "realization": max(1, int(n * 0.35)), "unease": n // 2}.get(e["role"], max(1, n // 2))
        sc["face_end"] = rule.get("face_end") if rule.get("face_end") != sc["face"] else None
        sc["act"] = None
        sc.pop("phone", None)
        if e["role"] == "curiosity" and brief.get("message"):
            sc["phone"] = dict(title=brief["message"]["title"][:22], body=brief["message"]["body"][:44], time="2:47")
        if e["role"] == "realization" and brief.get("punch"):
            sc["punch"] = brief["punch"]
    return out


# ------------------------------------------------------------------ capability
def capability_pass(topic, script, fit, report, log):
    S = lambda enum: {"type": "string", "enum": enum}
    from engine.shorts import topics
    schema = {"type": "object", "properties": {
        "pack": S(topics.PACK_NAMES), "renderable": {"type": "boolean"},
        "needs": {"type": "array", "items": {"type": "object", "properties": {
            "type": S(["prop", "environment", "character", "effect"]), "name": {"type": "string"},
            "reason": {"type": "string"}, "priority": S(["high", "medium", "low"])}, "required": ["type", "name", "reason", "priority"]}}},
        "required": ["pack", "renderable", "needs"]}
    listing = "\n".join(f"- {b['text']}  (visual: {b.get('visual_idea', '')})" for b in script["beats"])
    prompt = (f"A cartoon Short generator can draw ONLY: {L.catalog_text()}\nTopic: {topic}\nBeats:\n{listing}\n"
              "Pick the topic pack (everyday/psychology/money/tech/business/history/mythology/science). List every concrete PROP, "
              "ENVIRONMENT, CHARACTER or EFFECT the beats would need to be shown literally (English nouns, e.g. 'ATM', 'temple', "
              "'bank counter', 'smartphone'), with priority high if the story cannot be told without it. renderable=false only if the "
              "topic needs real footage/photos/live action.")
    try:
        r = _json(_chat(DIRECTOR, prompt, schema, 0.1))
        cap = topics.assess(r["pack"], fit, r["needs"], r["renderable"], ignore=[(script.get("protagonist") or {}).get("name", "")])
    except Exception as e:
        cap = topics.assess("everyday", fit, [], True)
        cap["explanation"] += f" (capability check failed: {e})"
    log(f"[plan] capability class {cap['class']} ({cap['pack']}): {len(cap['asset_requirements'])} unmet asset requirement(s)")
    return cap


# ------------------------------------------------------------------ entry
def make_plan(topic=None, duration=40, seed=1, log=print, brief=None):
    report = dict(models=dict(writer=WRITER, director=DIRECTOR), repairs=[], warnings=[])
    if brief:
        topic = brief.get("title") or topic
        fit, loc = "scene", [brief["location"]]
        report["fit"] = dict(level=fit, reason="story brief with a fixed location", sets=loc)
        script = write_story(brief, duration, report, log)
    else:
        fit, loc = assess_fit(topic, report, log)
        script = write_script(topic, duration, report, log)
    log(f"[plan] script: {script.get('title')} / {len(script['beats'])} beats")
    raw = None if (brief and brief.get("rig", "layered") == "layered") else direct(topic, script, fit, loc, report, log)   # stories: role-driven staging
    beats = repair(topic, script, fit, loc, raw, report, seed, log)
    if brief:
        apply_story_rules(beats, brief, lambda m: (report["repairs"].append(m), log(f"[plan] repair: {m}")))
    cap = capability_pass(topic, script, fit, report, log)
    kind = (script.get("protagonist") or {}).get("kind")
    cast = L.CAST.get(kind, "rahul")
    return dict(version=3, topic=topic, title=script.get("title", topic), seed=seed, cast=cast, protagonist=script.get("protagonist"),
                target_duration=duration, beats=beats, capability=cap, planner=report, brief=brief,
                rig="layered" if (brief and brief.get("rig", "layered") == "layered") else "poses")
