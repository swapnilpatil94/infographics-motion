"""Story analysis: Hindi/English story + narration segments -> validated structured understanding.

Two LLM roles (each output is UNTRUSTED and validated/repaired in code):
  * READER   gemma4:12b  - reads each paragraph (best local Hindi comprehension) and tags every narration segment with
                           speaker / emotion / action / location / characters / on-screen UI / amounts / psychology / importance.
  * SYNTHESIS qwen3:14b  - schema-constrained: characters, narrative phases, central question, visual treatment.
Everything is checked against the domain pack's closed vocabularies; anything unknown is coerced or dropped with a warning.
"""
import json
import re

from engine.factory.domain import cue_hits, has_cue
from engine.shorts.planner import _chat, _json

READER, SYNTH = "gemma4:12b-mlx", "qwen3:14b"


def _vocab(dom):
    return dict(emotions=dom["emotions"], verbs=dom["verbs"], envs=dom.env_kinds(), ui=dom["ui_screens"], psych=list(dom["psychology"]))


def read_paragraph(dom, para, segs, ctx, warn, log):
    v = _vocab(dom)
    numbered = "\n".join(f"{i + 1}. {s['text']}" for i, s in enumerate(segs))
    prompt = (
        "You are a story analyst reading a Hindi documentary script about money, scams and human psychology. "
        f"Known characters so far: {ctx['characters'] or 'none'}. Previous paragraph (English): {ctx['prev'] or 'none'}.\n"
        f"PARAGRAPH SENTENCES (Hindi, numbered):\n{numbered}\n\n"
        "For EVERY numbered sentence return one object. Use ONLY these vocabularies:\n"
        f"emotion: {v['emotions']}\naction (what the protagonist DOES, else 'none'): {v['verbs']}\n"
        f"location kind (where it happens, or null if unchanged/abstract): {v['envs']}\n"
        f"ui screen shown on a phone in this sentence (else null): {v['ui']}\npsychology mechanism (else empty list): {v['psych']}\n"
        'speaker: "narrator" (narration), "caller" (a scammer speaking on the phone, quoted), or "protagonist" (quoted speech)\n'
        "importance 1-5 (5 = the moment the story hinges on). advice: if the sentence tells the VIEWER what to do, list each action as a SHORT Hindi imperative phrase (max 6 words), else []. amounts: rupee amounts mentioned as numbers with kind in "
        "[attempted, sent, lost, balance, total, threshold]. characters: names of people present or acting.\n"
        'Return ONLY JSON: {"summary_en": "<one English sentence>", "sentences": [{"n": 1, "speaker": "...", "emotion": "...", '
        '"action": "...", "location": null, "characters": [], "ui": null, "amounts": [{"value": 0, "kind": "sent"}], '
        '"psychology": [], "importance": 3, "advice": [], "visual_note": "<short English visual idea>"}]}')
    for k in range(3):
        try:
            data = _json(_chat(READER, prompt, None, 0.3 + 0.2 * k, timeout=900))
            out = data["sentences"]
            if len(out) >= len(segs) - 1:
                return data["summary_en"], out, data.get("paragraph_mode") if data.get("paragraph_mode") in ("story", "explanation", "advice") else None
        except Exception as e:
            log(f"[analysis] reader retry {k + 1}: {type(e).__name__}")
    warn(f"paragraph reader failed after retries; defaults used ({segs[0]['id']}..)")
    return "", [], None


def clean_tags(dom, raw, seg, warn):
    """LLM tags are hypotheses. Each one that has a textual signature in the domain pack must be CORROBORATED by the segment text
    (or is dropped); cue hits can also override a wrong tag. Everything is coerced into the closed vocabularies."""
    v = _vocab(dom)
    cues = dom["cues"]
    text = seg["text"]
    t = dict(speaker=raw.get("speaker") if raw.get("speaker") in ("narrator", "caller", "protagonist") else "narrator",
             emotion=raw.get("emotion") if raw.get("emotion") in v["emotions"] else "blank",
             action=raw.get("action") if raw.get("action") in v["verbs"] else "none",
             location=None, characters=[c for c in (raw.get("characters") or []) if isinstance(c, str)][:4],
             ui=None, amounts=[], advice=[str(a)[:60] for a in (raw.get("advice") or []) if isinstance(a, str)][:4],
             psychology=[], importance=max(1, min(5, int(raw.get("importance") or 3))), visual_note=str(raw.get("visual_note") or "")[:160])
    # location: text cues first, then the LLM's guess (validated against the domain), else unchanged (None = carry forward)
    hits = cue_hits(text, cues["locations"])
    if hits:
        t["location"] = hits[-1]
    elif raw.get("location"):
        kind, _, _ = dom.location_set(str(raw["location"]))
        t["location"] = kind
    # UI screen: only if the sentence actually talks about it
    ui = raw.get("ui")
    screen = ui.get("screen") if isinstance(ui, dict) else ui if isinstance(ui, str) else None
    ui_hits = cue_hits(text, cues["ui"])
    if screen in v["ui"] and screen in cues["ui"] and screen in ui_hits:
        t["ui"] = dict(screen=screen, data=(ui.get("data") if isinstance(ui, dict) else None) or {})
    elif ui_hits and not screen:
        t["ui"] = dict(screen=ui_hits[0], data={})
    elif screen == "in_call" and t["speaker"] == "caller":
        t["ui"] = dict(screen="in_call", data={})
    # amounts: value plausible AND the kind corroborated by a cue
    for a in raw.get("amounts") or []:
        try:
            val, kind = float(str(a["value"]).replace(",", "")), a.get("kind", "total")
        except Exception:
            continue
        if kind in cues["amounts"] and has_cue(text, cues["amounts"][kind]) and (kind == "threshold" and 5 <= val <= 180 or 1000 <= val <= 1e8):
            t["amounts"].append(dict(value=val, kind=kind))
    # psychology: cues decide (explanation especially); the LLM may add one only outside explanations
    t["psychology"] = cue_hits(text, cues["psychology"])[:2]
    if not t["psychology"] and seg.get("phase") not in ("EXPLANATION",):
        t["psychology"] = [p for p in (raw.get("psychology") or []) if p in v["psych"]][:1] if False else []
    return t


def synthesize(dom, paragraph_summaries, names, locations, log, warn):
    S = lambda enum: {"type": "string", "enum": enum}
    schema = {"type": "object", "properties": {
        "title_en": {"type": "string"}, "logline": {"type": "string"}, "central_question": {"type": "string"},
        "characters": {"type": "array", "items": {"type": "object", "properties": {
            "name": {"type": "string"}, "role": S(["protagonist", "family", "antagonist_voice", "colleague", "official", "other"]),
            "gender": S(["f", "m", "unknown"]), "age": S(["young", "adult", "elder", "unknown"]), "description": {"type": "string"},
            "on_screen": {"type": "boolean"}}, "required": ["name", "role", "gender", "age", "description", "on_screen"]}},
        "phases": {"type": "array", "items": S(dom["phases"])},
        "treatment": {"type": "object", "properties": {
            "primary_style": {"type": "string"}, "secondary_style": {"type": "string"}, "palette_behavior": {"type": "string"},
            "camera_language": {"type": "string"}, "lighting_language": {"type": "string"}, "gp_language": {"type": "string"},
            "motion_language": {"type": "string"}, "visual_metaphors": {"type": "array", "items": {"type": "string"}}},
            "required": ["primary_style", "secondary_style", "palette_behavior", "camera_language", "lighting_language", "gp_language", "motion_language", "visual_metaphors"]}},
        "required": ["title_en", "logline", "central_question", "characters", "phases", "treatment"]}
    listing = "\n".join(f"P{i + 1}: {s}" for i, s in enumerate(paragraph_summaries))
    prompt = (f"A documentary about money psychology and scams has these paragraph summaries:\n{listing}\n\n"
              f"Names mentioned: {names}. Locations mentioned: {locations}.\n"
              f"Return: title_en, one-sentence logline, the central question the film answers, the characters (on_screen=false for "
              f"people who are only a voice on the phone or mentioned), one narrative phase per paragraph (exactly {len(paragraph_summaries)}, "
              f"from {dom['phases']}; the first must be HOOK; phases must be NON-DECREASING in this order: HOOK, SETUP, INCITING, ESCALATION, COMPLICATION, CLIMAX, REVEAL, EXPLANATION, PAYOFF; EXPLANATION only after the reveal, when the film explains the psychology), and a visual TREATMENT specific to THIS story: styles, how the "
              f"palette/camera/lighting/grease-pencil/motion should behave over the film, and 3-5 concrete visual metaphors for its ideas.")
    for k in range(3):
        try:
            r = _json(_chat(SYNTH, prompt, schema, 0.3 + 0.2 * k, timeout=900))
            order = ["HOOK", "SETUP", "INCITING", "ESCALATION", "COMPLICATION", "CLIMAX", "REVEAL", "EXPLANATION", "PAYOFF"]
            ph = (r["phases"] + ["ESCALATION"] * len(paragraph_summaries))[:len(paragraph_summaries)]
            hi = 0
            for i, p in enumerate(ph):                                            # monotone repair: a story cannot go back to an earlier phase
                idx = order.index(p) if p in order else hi
                hi = max(hi, idx)
                ph[i] = order[hi]
            ph[0] = "HOOK"
            r["phases"] = ph
            return r
        except Exception as e:
            log(f"[analysis] synthesis retry {k + 1}: {type(e).__name__}")
    warn("synthesis failed; generic treatment used")
    return None


def mode_from_cues(dom, text):
    import re
    from engine.factory.domain import nn
    toks = re.findall(r"[\w\u0900-\u097F]+", nn(text))
    c = dom["cues"]["mode"]
    ex = sum(1 for t in toks if t in {nn(x) for x in c["explanation_tokens"]})
    ad = sum(1 for t in toks if any(nn(a) in t for a in c["advice_tokens"]))
    if ex >= c["explanation_min"]:
        return "explanation"
    if ad >= c["advice_min"]:
        return "advice"
    return None


def paragraph_infos(dom, story, segs, llm_modes):
    by_para = {}
    for s in segs:
        by_para.setdefault(s["paragraph"], []).append(s)
    infos = []
    for pi in sorted(by_para):
        ps = by_para[pi]
        psy = {m_ for s in ps for m_ in s["tags"]["psychology"]}
        mode = mode_from_cues(dom, story["paragraphs"][pi]) or (llm_modes[pi] if llm_modes and pi < len(llm_modes) and llm_modes[pi] == "story" else None) or "story"
        infos.append(dict(mode=mode, ui={s["tags"]["ui"]["screen"] for s in ps if s["tags"]["ui"]},
                          amounts={a["kind"] for s in ps for a in s["tags"]["amounts"]}, advice=any(s["tags"].get("advice") for s in ps)))
    return infos


def rederive(dom, story, segs, analysis):
    """Re-derive modes/phases/warnings from cached LLM tags (no LLM call) after the evidence rules change."""
    infos = paragraph_infos(dom, story, segs, analysis.get("paragraph_modes"))
    analysis["phases"] = infer_phases(infos)
    analysis["paragraph_modes"] = [x["mode"] for x in infos]
    for s in segs:
        s["phase"] = analysis["phases"][s["paragraph"]]
    analysis["quality_warnings"] = quality_check(story, segs, analysis)
    return analysis


def infer_phases(infos):
    """Deterministic narrative phases from paragraph facts (mode, phone UI seen, money moved). LLM phase labels were unreliable
    (it tagged half the film PAYOFF), so structure is derived from evidence in the story, not asked for."""
    n = len(infos)
    ph = [None] * n
    ph[0] = "HOOK"
    story_i = [i for i, x in enumerate(infos) if x["mode"] == "story" and i > 0]
    inc = next((i for i in story_i if x_has(infos[i], "ui", ("incoming_call", "in_call", "sms"))), None)
    if inc is None:
        inc = story_i[1] if len(story_i) > 1 else (story_i[0] if story_i else 1)
    first_sent = next((i for i in story_i if x_has(infos[i], "amounts", ("sent",))), None)
    first_expl = next((i for i, x in enumerate(infos) if x["mode"] == "explanation"), None)
    lost_after = next((i for i in story_i if x_has(infos[i], "amounts", ("lost",)) and (first_sent is None or i > first_sent) and (first_expl is None or i < first_expl)), None)
    mid = [i for i in story_i if inc < i and (first_sent is None or i < first_sent)]
    for i in range(1, n):
        m = infos[i]["mode"]
        if m == "explanation":
            ph[i] = "EXPLANATION"
        elif m == "advice":
            ph[i] = "PAYOFF"
        elif i < inc:
            ph[i] = "SETUP"
        elif i == inc:
            ph[i] = "INCITING"
        elif first_expl is not None and i > first_expl:
            ph[i] = "PAYOFF"
        elif first_sent is not None and i == first_sent:
            ph[i] = "CLIMAX"
        elif lost_after is not None and i >= lost_after:
            ph[i] = "REVEAL"
        elif first_sent is not None and i > first_sent:
            ph[i] = "CLIMAX"
        else:
            ph[i] = "ESCALATION" if mid.index(i) < max(1, len(mid) // 2) else "COMPLICATION"
    return ph


def x_has(info, key, vals):
    return any(v in info[key] for v in vals)


def quality_check(story, segs, analysis):
    """Story-quality warnings BEFORE rendering (a weak film should be flagged, not silently generated)."""
    w = []
    ph = analysis["phases"]
    if ph and ph[0] != "HOOK":
        w.append("opening paragraph is not a HOOK")
    if not re.search(r"[?？]", story["paragraphs"][0]):
        w.append("no explicit central question in the opening paragraph")
    if sum(1 for p in ph if p in ("ESCALATION", "COMPLICATION")) < 2:
        w.append("weak escalation: fewer than two escalation/complication phases")
    if not any(p in ("REVEAL", "CLIMAX") for p in ph):
        w.append("no reveal/climax phase detected")
    if not any(p == "PAYOFF" for p in ph):
        w.append("no payoff phase detected")
    if not analysis["psychology"]:
        w.append("no psychological mechanism detected")
    if not any(c["role"] == "protagonist" for c in analysis["characters"]):
        w.append("no protagonist detected")
    long_seg = [s["id"] for s in segs if s["end"] - s["start"] > 12]
    if long_seg:
        w.append(f"very long narration segments (>12 s) limit pacing control: {long_seg[:5]}")
    return w


def analyze(dom, story, narration, log=print):
    warnings = []
    warn = lambda m: (warnings.append(m), log(f"[analysis] warning: {m}"))
    segs = narration["segments"]
    by_para = {}
    for s in segs:
        by_para.setdefault(s["paragraph"], []).append(s)
    ctx = dict(characters="", prev="")
    summaries, names, locs, llm_modes = [], set(), set(), []
    for pi in sorted(by_para):
        ps = by_para[pi]
        log(f"[analysis] reading paragraph {pi + 1}/{len(story['paragraphs'])} ({len(ps)} segments)")
        summary, tags, mode = read_paragraph(dom, story["paragraphs"][pi], ps, ctx, warn, log)
        for i, s in enumerate(ps):
            raw = tags[i] if i < len(tags) and isinstance(tags[i], dict) else {}
            s["tags"] = clean_tags(dom, raw, s, warn)
            names.update(s["tags"]["characters"])
            if s["tags"]["location"]:
                locs.add(s["tags"]["location"])
        summaries.append(summary or story["paragraphs"][pi][:120])
        llm_modes.append(mode)
        ctx = dict(characters=", ".join(sorted(names)), prev=summary)
    log("[analysis] synthesizing structure and treatment")
    syn = synthesize(dom, summaries, sorted(names), sorted(locs), log, warn) or dict(
        title_en=story["title"], logline="", central_question="", characters=[], phases=["ESCALATION"] * len(summaries),
        treatment=dict(primary_style="cinematic_editorial", secondary_style="psychological_thriller", palette_behavior="",
                       camera_language="", lighting_language="", gp_language="", motion_language="", visual_metaphors=[]))
    # narrative phase per segment (derived from evidence); psychology registry; characters mapped onto the cast
    llm_phases = syn["phases"]
    infos = paragraph_infos(dom, story, segs, llm_modes)
    syn["phases"] = infer_phases(infos)
    for pi, ps in by_para.items():
        for s in ps:
            s["phase"] = syn["phases"][pi]
    psych = {}
    for s in segs:
        for m in s["tags"]["psychology"]:
            psych.setdefault(m, []).append(s["id"])
    chars = []
    seen = []
    for c in sorted(syn["characters"], key=lambda c: -len(c["name"])):                 # merge 'Neha' / 'Neha Verma'
        toks = set(c["name"].lower().split())
        if any(toks <= t for t in seen if t):
            continue
        seen.append(toks)
        c["_ok"] = True
    for c in [c for c in syn["characters"] if c.get("_ok")]:
        role = c["role"]
        key = "voice_only" if not c["on_screen"] else ("protagonist_f" if role == "protagonist" and c["gender"] == "f" else
                                                       "protagonist_m" if role == "protagonist" else
                                                       "elder_m" if (c["age"] == "elder" or role == "family") and c["gender"] == "m" else
                                                       "elder_f" if c["age"] == "elder" else "protagonist_m" if c["gender"] == "m" else "protagonist_f")
        arche = dom["characters"][key]
        cid = re.sub(r"\W+", "_", c["name"].lower()).strip("_") or f"char{len(chars) + 1}"
        chars.append(dict(id=cid, name=c["name"], role=role, gender=c["gender"], age=c["age"], description=c["description"],
                          on_screen=bool(c["on_screen"] and arche["cast"]), archetype=key, cast=arche["cast"], outfit=arche.get("outfit"),
                          note=arche.get("note")))
        if c["on_screen"] and not arche["cast"]:
            warn(f"character '{c['name']}' needs an on-screen model but the domain has none ({arche.get('note')})")
    analysis = dict(
        llm_phases=llm_phases, llm_modes=llm_modes, paragraph_modes=[x["mode"] for x in infos],
        title_en=syn["title_en"], logline=syn["logline"], central_question=syn["central_question"],
        topics=dom.detect_topics(" ".join(story["paragraphs"])), phases=syn["phases"], characters=chars,
        locations=sorted(locs), paragraph_summaries=summaries, treatment=syn["treatment"],
        psychology=[dict(mechanism=k, label=dom.psych(k)["label"], grammar=dom.psych(k)["grammar"], segments=v) for k, v in psych.items()],
        financial_events=[dict(seg=s["id"], **a) for s in segs for a in s["tags"]["amounts"]])
    analysis["quality_warnings"] = quality_check(story, segs, analysis)
    analysis["warnings"] = warnings
    return analysis
