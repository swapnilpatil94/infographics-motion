"""STUDIO CORE: everything the web UI needs *before* an expensive render - options, story / script input, validation, the story review, story + script edits, drafts. No web framework in here, no business logic
in the browser: the server is a thin JSON layer over these functions and over `engine.skeleton.backend`.

  create_draft(req)      CREATE (topic) | SCRIPT (text / story.md / story.json) | PRODUCTION (story + narration segments JSON)  ->  draft (story graph, review card, script segments)
  edit_story(id, ...)    beat / cast / title edits, re-validated through the existing story-graph constructor (the act grammar, the supported locations)
  edit_script(id, ...)   segment text edits (re-analysed) and LLM re-writes of selected segments (validated, or refused)
  job_request(draft)     the approved draft -> the request a production worker runs

Unsupported input never becomes a film: it raises StudioError with the reasons (code + reasons[] + hint).
"""
import copy
import hashlib
import json
import os
import re
import time
import urllib.request
import uuid

from engine.characters import dna as D1
from engine.environments import locations as LOC
from engine.shorts.raster import ROOT
from engine.skeleton import acts as AC, audio_director as AUD, backend as BE, director_opts as DO, dna2, lab_dna as LD, narration_io as NI, story_semantics as SS, topic_build as TB, topic_story as TS

STUDIO_DIR = os.environ.get("KATHAYA_STUDIO_DIR") or os.path.join(ROOT, "output/studio")
DRAFTS = os.path.join(STUDIO_DIR, "drafts")
PRODS = os.path.join(STUDIO_DIR, "productions")
UPLOADS = os.path.join(STUDIO_DIR, "uploads")
TAIL = 3.0
DEVA = re.compile(r"[ऀ-ॿ]")
ALLOWED = re.compile(r"^[ऀ-ॿ\s,।?!\.\-'’‘“”\":;…()]+$")
LEVELS = ("simple", "director", "expert")
DURATIONS = (None, 45, 50, 55, 60)
EXAMPLES = [dict(id="a_whatsapp_investment", label="Fake WhatsApp investment group", hint="bedroom at night, then a cafe"), dict(id="b_lottery_fee", label="Lottery / prize processing fee", hint="living room, then a bank counter"),
            dict(id="c_atm_helper", label="ATM 'helper' card swap", hint="street, ATM, bank")]


class StudioError(Exception):
    """a request the studio refuses, with the reasons (HTTP 422)"""

    def __init__(self, code, message, reasons=None, hint=None, status=422):
        super().__init__(message)
        self.code, self.message, self.reasons, self.hint, self.status = code, message, list(reasons or []), hint, status

    def to_dict(self):
        return dict(code=self.code, message=self.message, reasons=self.reasons, hint=self.hint)


# ------------------------------------------------------------------------------------------------ options
def options():
    pal = list(dna2.PALETTES)
    envs = {n: dict(times=list(t), default=d, family=f) for n, (f, t, d, _lay, _) in LOC.LOCATIONS.items()}
    return dict(
        levels=list(LEVELS), modes=[dict(id="create", label="Create", hint="a topic or idea"), dict(id="script", label="Script", hint="an existing story or script"), dict(id="production", label="Production", hint="story + narration segments JSON")],
        languages=[dict(id="hi", label="हिन्दी (Hindi)", supported=True), dict(id="en", label="English", supported=False, why="the story parser and the narrator voice are Hindi (Devanagari) only")],
        formats=[dict(id="9:16", label="9:16 vertical", native=True, note="native master (1080x1920)"), dict(id="16:9", label="16:9 landscape", native=False, note="the 9:16 master, pillar-boxed on a blurred backdrop (1920x1080); scenes are still staged for 9:16")],
        durations=[dict(id="auto", label="Auto", seconds=None)] + [dict(id=str(s), label=f"about {s} s", seconds=s) for s in DURATIONS if s],
        voices=[dict(id="chatterbox_hindi", label="Chatterbox Hindi narrator", kind="tts", default=True), dict(id="provided", label="Provided audio (Production mode)", kind="segments_json")],
        styles=[dict(id="kathaya_cinematic", label="Kathaaya Cinematic", default=True, note="deterministic rig + Open Peeps art, per-scene lighting")],
        typography=dict(captions=True, styles=[dict(id="kathaya_bold", label="Kathaaya Bold (Kohinoor Devanagari, outlined)", default=True)], caption_language="same as the narration (Hindi)"),
        pacing=[dict(id="auto", label="Auto"), dict(id="calm", label="Calm"), dict(id="normal", label="Normal"), dict(id="fast", label="Fast"), dict(id="intense", label="Intense")],
        camera=[dict(id="auto", label="Auto"), dict(id="locked", label="Locked-off (no camera moves)"), dict(id="push_in", label="Push-in emphasis")],
        audio=dict(defaults={k: AUD.GAIN[k] for k in ("music", "sfx", "ambience")}, min=0.0, max=2.0, note="multipliers of the Audio Director's default levels (1.0 = Auto)"),
        environments=envs, archetypes=sorted(LD.ARCHETYPES), skins=list(D1.SKIN), palettes=pal, tops=list(dna2.TOPS), emotions=list(SS.EMOTIONS) + ["neutral"], acts=sorted(AC.ACTS),
        limits=dict(segments=[8, 40], max_extras=2, words_per_segment_warn=18, supported_topics=sorted(TS.PACKS), locations=list(LOC.ALL)),
        examples=EXAMPLES, sample_topics=["fake WhatsApp investment group", "lottery prize processing fee scam", "OTP / bank KYC call scam", "digital arrest courier parcel scam", "work-from-home job registration fee scam", "UPI refund link scam", "instant loan app blackmail"])


# ------------------------------------------------------------------------------------------------ script text
def split_script(text):
    """text -> narration lines: one line per non-empty row; a long row is split at sentence ends"""
    out = []
    for raw in (text or "").splitlines():
        raw = re.sub(r"^\s*(\d+[.)]|[-*•])\s*", "", raw.strip())
        if not raw or raw.startswith("#"):
            continue
        parts = re.split(r"(?<=[।?!])\s+", raw) if len(raw.split()) > 14 else [raw]
        out += [p.strip() for p in parts if p.strip()]
    return out


def parse_story_text(text):
    """story.md / plain script -> (notes, lines).  `# Title`, `key: value` notes (protagonist, other, location, time, sender, amount) and an optional `---` separator are understood."""
    tmp = os.path.join(STUDIO_DIR, "_tmp_story_%s.md" % uuid.uuid4().hex[:8])
    os.makedirs(STUDIO_DIR, exist_ok=True)
    body = text
    if "\n---" in text:
        head, body = text.split("\n---", 1)
        open(tmp, "w", encoding="utf-8").write(text)
        try:
            notes = SS.load_script(tmp)
        finally:
            os.remove(tmp)
        notes.pop("description", None)
        return {k: v for k, v in notes.items() if v}, split_script(body)
    notes, rest = {}, []
    keys = ("protagonist", "other", "location", "time", "sender", "amount")
    head_lines = []
    for ln in text.splitlines():
        m = re.match(r"\s*(\w+)\s*:\s*(.+)$", ln)
        if m and m.group(1).lower() in keys and re.match(r"^[a-z]+$", m.group(1).lower()):
            head_lines.append(ln)
        else:
            rest.append(ln)
    if head_lines or any(l.startswith("#") for l in rest):
        title = next((re.sub(r"^#+\s*", "", l).strip() for l in rest if l.startswith("#")), None)
        open(tmp, "w", encoding="utf-8").write((f"# {title}\n" if title else "") + "\n".join(head_lines) + "\n")
        try:
            notes = SS.load_script(tmp)
        finally:
            os.remove(tmp)
        notes.pop("description", None)
        notes = {k: v for k, v in notes.items() if v}
    return notes, split_script("\n".join(rest))


def lint_script(lines):
    """-> (errors, warnings). The narrator (Chatterbox Hindi) and the forced aligner need clean Devanagari: Latin letters, digits and symbols are refused with a suggestion."""
    errs, warns = [], []
    if not lines:
        return ["the script is empty"], warns
    letters = sum(len(DEVA.findall(l)) for l in lines)
    latin = sum(len(re.findall(r"[A-Za-z]", l)) for l in lines)
    if latin > letters:
        errs.append("the script is not Hindi: the story parser and the narrator voice support Hindi (Devanagari) only")
        return errs, warns
    for i, l in enumerate(lines, 1):
        bad = sorted({c for c in l if not ALLOWED.match(c)})
        if bad:
            errs.append(f"line {i}: '{' '.join(bad)}' cannot be narrated - write it in Devanagari words (e.g. OTP -> ओटीपी, 50,000 -> पचास हज़ार): {l[:60]}")
        if len(l.split()) > 18:
            warns.append(f"line {i} has {len(l.split())} words - long lines make long shots; consider splitting it")
    return errs[:8], warns


def draft_timing(lines):
    n = TB.draft_narration(dict(beats=[dict(id=f"n{i + 1:02d}", text=t) for i, t in enumerate(lines)]))
    return n


# ------------------------------------------------------------------------------------------------ graph: analysis, preferences, edits
def _wrap(fn, *a, **k):
    try:
        return fn(*a, **k)
    except SS.StoryNotSupported as e:
        raise StudioError("unsupported_story", "This story cannot be staged by the studio.", reasons=[r.strip() for r in str(e).split(";") if r.strip()],
                          hint=f"The studio tells money-scam / money-psychology stories in these places: {', '.join(LOC.ALL)}; 8-40 narration segments; at most 3 supporting roles.")
    except TS.TopicNotSupported as e:
        raise StudioError("unsupported_topic", "This topic is outside the supported domains.", reasons=[str(e).split(" Supported domains")[0]], hint="Supported topic domains: " + ", ".join(sorted(TS.PACKS)) + ". Use Script mode for your own story.")
    except NI.NarrationInvalid as e:
        raise StudioError("narration_invalid", "The narration segments JSON is not usable.", reasons=[r.strip() for r in str(e).split(";") if r.strip()],
                          hint='Expected {"segments":[{"id","text","start","end"}], "audio":"path/to.wav"} with start < end, in order, and an existing audio file.')
    except LOC.LocationUnsupported as e:
        raise StudioError("unsupported_location", str(e), hint="Supported locations: " + ", ".join(LOC.ALL))
    except DO.OptionsInvalid as e:
        raise StudioError("invalid_options", str(e))
    except ValueError as e:
        raise StudioError("invalid_input", str(e))


def _rebuild(graph, beats, cast=None):
    """new graph from edited beats through the existing constructor (act grammar + locations validated); the story id (= every character's and set's seed) is kept, so an edit never re-casts the film"""
    c = cast or graph["cast"]
    g = SS.graph_from_beats(graph["title"], beats, c["protagonist"], (c.get("principal") or {}).get("role"), [e["role"] for e in c.get("extras", [])], graph["slug"], graph.get("notes"))
    g["story_id"] = graph["story_id"]
    if c.get("principal"):
        g["cast"]["principal"] = dict(c["principal"])
    g["cast"]["extras"] = [dict(e) for e in c.get("extras", [])]
    g["cast"]["protagonist"] = dict(c["protagonist"])
    for k in ("fixes", "director", "dna_patch", "variation"):
        if k in graph:
            g[k] = copy.deepcopy(graph[k])
    g["provenance"] = list(graph.get("provenance", [])) + [dict(step="edited")]
    return g


def edit_beats(graph, changes):
    """changes = {beat_id: {act, loc, time, emotion}}  ->  new graph or StudioError"""
    known = {b["id"] for b in graph["beats"]}
    beats = [dict(b) for b in graph["beats"]]
    for bid, ch in (changes or {}).items():
        if bid not in known:
            raise StudioError("unknown_beat", f"there is no beat '{bid}'")
        b = next(x for x in beats if x["id"] == bid)
        for k, v in ch.items():
            if k not in ("act", "loc", "time", "emotion"):
                continue
            if k == "act" and v not in AC.ACTS:
                raise StudioError("invalid_act", f"'{v}' is not an act the studio can stage", hint="Acts: " + ", ".join(sorted(AC.ACTS)))
            if k == "emotion" and v not in list(SS.EMOTIONS) + ["neutral"]:
                raise StudioError("invalid_emotion", f"'{v}' is not a supported emotion", hint="Emotions: " + ", ".join(list(SS.EMOTIONS) + ["neutral"]))
            b[k] = v
    try:
        return _rebuild(graph, beats)
    except SS.StoryNotSupported as e:
        raise StudioError("invalid_edit", "That edit breaks the story's act grammar, so it was not applied.", reasons=[r.strip() for r in str(e).replace("invalid act sequence:", "").split(";") if r.strip()],
                          hint="An act needs what came before it (a phone must be held before it can be handed over; a partner must be present before they react). Change the neighbouring acts too, or pick another act.")
    except LOC.LocationUnsupported as e:
        raise StudioError("unsupported_location", str(e), hint="Supported locations: " + ", ".join(LOC.ALL))


def _check_char(kind, ch):
    out = {}
    if ch.get("archetype"):
        if ch["archetype"] not in LD.ARCHETYPES:
            raise StudioError("invalid_character", f"{kind}: '{ch['archetype']}' is not a character type", hint="Types: " + ", ".join(sorted(LD.ARCHETYPES)))
        out["archetype"] = ch["archetype"]
    if ch.get("gender"):
        ok = ("male", "female") if kind == "protagonist" else ("masculine", "feminine", "either")
        if ch["gender"] not in ok:
            raise StudioError("invalid_character", f"{kind}: gender must be one of {ok}")
        out["gender"] = ch["gender"]
    if ch.get("name") and kind == "protagonist":
        out["name"] = str(ch["name"])[:24]
    return out


def apply_prefs(graph, prefs, base_story_id=None):
    """UI preferences -> graph.  Defaults (everything AUTO) leave the graph untouched, so the plan stays byte-identical to the CLI's."""
    g = copy.deepcopy(graph)
    base = base_story_id or g["story_id"]
    ch = (prefs or {}).get("character") or {}
    if ch.get("protagonist"):
        g["cast"]["protagonist"].update(_check_char("protagonist", ch["protagonist"]))
    if ch.get("partner") and g["cast"].get("principal"):
        g["cast"]["principal"].update(_check_char("partner", ch["partner"]))
    for i, ex in enumerate(ch.get("extras") or []):
        if i < len(g["cast"]["extras"]):
            g["cast"]["extras"][i].update(_check_char("extra", ex))
    env = (prefs or {}).get("environment") or {}
    if env.get("mode") == "force" and env.get("location"):
        if env["location"] not in LOC.ALL:
            raise StudioError("unsupported_location", f"'{env['location']}' is not a supported environment", hint="Supported: " + ", ".join(LOC.ALL))
        beats = [dict(b, loc=env["location"]) for b in g["beats"]]
        g = _wrap(_rebuild, g, beats)
        g["provenance"].append(dict(step="forced_environment", location=env["location"]))
    var = int((prefs or {}).get("variation") or 0)
    g["story_id"] = base + (f"v{var}" if var else "")
    if var:
        g["variation"] = var
    d = DO.normalize((prefs or {}).get("director"))
    if d:
        g["director"] = d
    else:
        g.pop("director", None)
    patch = (prefs or {}).get("dna_patch")
    if patch:
        g["dna_patch"] = patch
    return g


# ------------------------------------------------------------------------------------------------ review card
PSYCH = [("Urgency and fear", "a deadline or a threat pushes the victim to act before thinking", ["तुरंत", "वरना", "ब्लॉक", "बंद", "गिरफ़्तार", "गिरफ्तार", "फौरन", "जल्दी", "आज ही", "धमकी", "डर", "घबरा"]),
         ("Greed / too good to be true", "an unrealistic reward lowers the victim's guard", ["दोगुना", "इनाम", "जीत", "लॉटरी", "मुनाफ़ा", "मुनाफा", "कमाई", "बधाई", "बोनस", "कमाइए", "लालच"]),
         ("False authority", "the scammer poses as a bank, the police or an official", ["बैंक", "पुलिस", "अधिकारी", "केवाईसी", "मैनेजर", "क्लर्क", "इंस्पेक्टर", "सरकारी", "कस्टमर केयर"]),
         ("Misplaced trust in a helper", "a friendly stranger 'helps' and takes control", ["मदद", "हेल्पर", "अजनबी", "सहायता", "कार्ड बदल", "मशीन"]),
         ("Social proof", "a crowd or a group makes the offer look normal", ["ग्रुप", "सदस्य", "वीआईपी", "सब कमा", "लोग"])]


def review_of(graph, timing=None, estimated=True):
    beats = graph["beats"]
    full = SS.norm(" ".join(b["text"] for b in beats))
    psy = []
    for name, why, cues in PSYCH:
        hit = [c for c in cues if SS.norm(c) in full]
        if hit:
            psy.append(dict(name=name, why=why, cues=hit[:4], score=len(hit)))
    psy.sort(key=lambda x: -x["score"])
    scr = next((b for b in beats if b["act"] == "INSERT_SCREEN"), None)
    fear = next((b for b in beats if b["emotion"] in ("fear", "suspicion") and b["act"] not in ("INSERT_SCREEN",)), None)
    conflict = scr or fear or beats[min(2, len(beats) - 1)]
    hook_b = next((b for b in beats if b["act"] in ("INSERT_SCREEN", "READ_MESSAGE", "PHONE_ALERT")), beats[0])
    lesson_b = next((b for b in reversed(beats) if b["act"] == "CLOSE_UP"), beats[-2] if len(beats) > 1 else beats[-1])
    c = graph["cast"]
    cast = [dict(id="A", role="protagonist", name=c["protagonist"].get("name") or "", archetype=c["protagonist"]["archetype"], gender=c["protagonist"]["gender"])]
    if c.get("principal"):
        cast.append(dict(id="D", role=c["principal"]["role"], name="", archetype=c["principal"]["archetype"], gender=c["principal"]["gender"]))
    cast += [dict(id=f"X{i}", role=e["role"], name="", archetype=e["archetype"], gender=e["gender"]) for i, e in enumerate(c.get("extras", []), 1)]
    dur = (timing["segments"][-1]["end"] + TAIL) if timing else None
    return dict(title=graph["title"], hook=dict(text=hook_b["text"], beat=hook_b["id"]), protagonist=cast[0], supporting=cast[1:], conflict=dict(text=conflict["text"], beat=conflict["id"], emotion=conflict["emotion"]),
                psychology=psy[:2] or [dict(name="Not detected", why="no persuasion cue from the studio's list appears in the wording", cues=[], score=0)], acts=[dict(id=b["id"], act=b["act"], emotion=b["emotion"], loc=b["loc"], time=b["time"], text=b["text"]) for b in beats],
                scenes=[dict(loc=s["loc"], time=s["time"], beats=len(s["beats"])) for s in graph["scenes"]], ending=dict(text=lesson_b["text"], beat=lesson_b["id"]), est_duration_s=round(dur, 1) if dur else None, duration_is_estimate=estimated,
                words=graph.get("words"), provenance=[p for p in graph.get("provenance", []) if p.get("step") in ("unclassified", "location_time", "act_repair", "forced_environment", "edited")][:8])


def script_view(lines, timing, act_of=None, estimated=True):
    segs = timing["segments"]
    return dict(estimated=estimated, segments=[dict(id=s["id"], text=s["text"], start=round(s["start"], 2), end=round(s["end"], 2), duration=round(s["end"] - s["start"], 2), act=(act_of or {}).get(s["id"])) for s in segs],
                total=round(segs[-1]["end"] + TAIL, 1))


# ------------------------------------------------------------------------------------------------ drafts
def _dpath(did):
    if not re.match(r"^d_[0-9a-f]{8}$", did or ""):
        raise StudioError("unknown_draft", f"unknown draft '{did}'", status=404)
    return os.path.join(DRAFTS, did)


def save_draft(d):
    p = _dpath(d["id"])
    os.makedirs(p, exist_ok=True)
    d["updated"] = time.time()
    tmp = os.path.join(p, "draft.json.tmp")
    json.dump(d, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, os.path.join(p, "draft.json"))
    return d


def load_draft(did):
    f = os.path.join(_dpath(did), "draft.json")
    if not os.path.exists(f):
        raise StudioError("unknown_draft", f"unknown draft '{did}'", status=404)
    return json.load(open(f, encoding="utf-8"))


def view(d):
    """what the browser gets: the draft without its private working state"""
    return dict(id=d["id"], mode=d["mode"], settings=d["settings"], review=d["review"], script=d["script"], graph=d["graph"], warnings=d.get("warnings", []), variation=d.get("variation", 0), provenance=d.get("provenance", []),
                provided_audio=bool(d.get("narration")), story_edits=d.get("story_edits", {}), updated=d.get("updated"))


def _prefs(d):
    s = d["settings"]
    return dict(character=s.get("character"), environment=s.get("environment"), variation=d.get("variation", 0), director=s.get("director"), dna_patch=s.get("dna_patch"))


def _analyze_lines(d):
    """approved lines (+ timing) -> graph with the draft's notes, preferences and story edits applied"""
    notes = dict(d.get("notes") or {})
    env = (d["settings"].get("environment") or {})
    if env.get("mode") == "prefer" and env.get("location"):
        if env["location"] not in LOC.ALL:
            raise StudioError("unsupported_location", f"'{env['location']}' is not a supported environment", hint="Supported: " + ", ".join(LOC.ALL))
        notes["location"] = env["location"]
    if d.get("narration"):
        segs = json.load(open(d["narration"], encoding="utf-8"))["segments"]
        timing = dict(segments=[dict(id=s["id"], text=s["text"], start=s["start"], end=s["end"]) for s in segs])
        est = False
    else:
        timing = draft_timing([l["text"] for l in d["lines"]])
        for s, l in zip(timing["segments"], d["lines"]):
            s["id"] = l["id"]
        est = True
    graph0 = _wrap(SS.analyze, [dict(id=s["id"], text=s["text"], start=s["start"], end=s["end"]) for s in timing["segments"]], notes)
    graph0["slug"] = notes.get("slug") or graph0["slug"]
    if d.get("story_edits"):
        graph0 = edit_beats(graph0, {k: v for k, v in d["story_edits"].items() if k in {b["id"] for b in graph0["beats"]}})
    if d.get("cast_edit"):
        graph0["cast"] = d["cast_edit"]
    graph = apply_prefs(graph0, _prefs(d), base_story_id=graph0["story_id"])
    d["graph"], d["timing"] = graph, timing
    d["review"] = review_of(graph, timing, estimated=est)
    d["script"] = script_view(d["lines"], timing, {b["id"]: b["act"] for b in graph["beats"]}, estimated=est)
    return d


def _settings(req):
    s = dict(language=req.get("language") or "hi", format=req.get("format") or "9:16", duration=req.get("duration"), voice=req.get("voice") or "chatterbox_hindi", style=req.get("style") or "kathaya_cinematic",
             level=req.get("level") or "simple", character=req.get("character") or {}, environment=req.get("environment") or {}, typography=req.get("typography") or {}, director=dict(req.get("director") or {}))
    if s["language"] != "hi":
        raise StudioError("unsupported_language", "Only Hindi is supported.", reasons=["the story parser and the narrator voice (Chatterbox Hindi) are Hindi / Devanagari only"], hint="Write the story in Hindi (Devanagari).")
    if s["format"] not in ("9:16", "16:9"):
        raise StudioError("invalid_options", f"format must be 9:16 or 16:9, got {s['format']!r}")
    if s["duration"] not in (None, "auto") and int(s["duration"]) not in [d for d in DURATIONS if d]:
        raise StudioError("invalid_options", f"duration must be auto or one of {[d for d in DURATIONS if d]} seconds")
    s["duration"] = None if s["duration"] in (None, "auto") else int(s["duration"])
    if s["style"] != "kathaya_cinematic":
        raise StudioError("invalid_options", f"unknown style '{s['style']}'", hint="Available: kathaya_cinematic")
    if (s["typography"] or {}).get("captions") is False:
        s["director"]["captions"] = False
    _wrap(DO.normalize, s["director"])
    return s


def _topic_lines(topic, variation):
    salted = topic if not variation else f"{topic} #v{variation}"
    st = _wrap(TS.write, salted, use_llm=False)
    inst = next((b for b in st["beats"] if b["act"] == "INSERT_SCREEN"), None)
    flow = next((b for b in st["beats"] if b["act"] == "VISUALIZE_FLOW"), None)
    notes = dict(title=st["title"], slug=st["slug"], protagonist=dict(name=st["cast"]["protagonist"]["name"], gender=st["cast"]["protagonist"]["gender"]),
                 other=dict(name=st["cast"]["other"]["name"], role=st["cast"]["other"]["relation"]), sender=(inst or {}).get("data", {}).get("sender", "UNKNOWN"), amount=(flow or {}).get("data", {}).get("amount", 100000))
    return [dict(id=b["id"], text=b["text"]) for b in st["beats"]], notes, dict(step="topic_story", domain=st["domain"], model="deterministic domain pack (no LLM)", provenance=st["provenance"][:2])


def load_segments_input(req, dest_dir):
    """Production mode: segments JSON (object / list / text / example / server path) + audio -> a validated narration file inside the draft"""
    ex = req.get("example")
    story_text = req.get("story_md") or ""
    if ex:
        if ex not in {e["id"] for e in EXAMPLES}:
            raise StudioError("unknown_example", f"unknown example '{ex}'")
        d0 = os.path.join(ROOT, "stories/production", ex)
        seg = json.load(open(os.path.join(d0, "segments.json"), encoding="utf-8"))
        story_text = open(os.path.join(d0, "story.md"), encoding="utf-8").read()
    elif req.get("segments_path"):
        p = req["segments_path"] if os.path.isabs(req["segments_path"]) else os.path.join(ROOT, req["segments_path"])
        if not os.path.exists(p):
            raise StudioError("narration_invalid", "The narration segments file does not exist.", reasons=[f"not found: {req['segments_path']}"])
        seg = json.load(open(p, encoding="utf-8"))
    else:
        seg = req.get("segments_json")
        if isinstance(seg, str):
            try:
                seg = json.loads(seg)
            except ValueError as e:
                raise StudioError("narration_invalid", "The narration segments JSON is not valid JSON.", reasons=[str(e)])
        if seg is None:
            raise StudioError("narration_invalid", "Production mode needs the narration segments JSON.", hint='{"segments":[{"id","text","start","end"}], "audio":"path/to.wav"}')
    if isinstance(seg, list):
        seg = dict(segments=seg)
    if req.get("audio_upload"):
        ap = os.path.join(UPLOADS, os.path.basename(req["audio_upload"]))
        if not os.path.exists(ap):
            raise StudioError("narration_invalid", "The uploaded audio file is missing.")
        seg["audio"] = ap
    elif req.get("audio_path"):
        seg["audio"] = req["audio_path"]
    if not seg.get("audio"):
        raise StudioError("narration_invalid", "Production mode needs the narration audio.", reasons=["'audio' is missing from the segments JSON (or upload the audio file)"])
    a = seg["audio"]
    seg["audio"] = a if os.path.isabs(a) else os.path.join(ROOT, a)
    os.makedirs(dest_dir, exist_ok=True)
    out = os.path.join(dest_dir, "segments.json")
    json.dump(seg, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    _wrap(NI.load, out)
    return out, story_text


def create_draft(req):
    mode = req.get("mode") or "create"
    if mode not in ("create", "script", "production"):
        raise StudioError("invalid_options", f"mode must be create, script or production, got {mode!r}")
    d = dict(id="d_" + uuid.uuid4().hex[:8], mode=mode, created=time.time(), settings=_settings(req), variation=int(req.get("variation") or 0), story_edits={}, provenance=[], warnings=[], narration=None, input={})
    dd = os.path.join(DRAFTS, d["id"])
    os.makedirs(dd, exist_ok=True)
    if mode == "create":
        topic = (req.get("topic") or "").strip()
        if len(topic) < 3:
            raise StudioError("empty_input", "Describe the topic or idea first.", hint='For example: "fake WhatsApp investment group"')
        d["input"] = dict(topic=topic)
        d["lines"], d["notes"], prov = _topic_lines(topic, d["variation"])
        d["provenance"].append(prov)
    elif mode == "script":
        raw = (req.get("script_text") or req.get("story_md") or "").strip()
        if req.get("story_json"):
            raw, notes_j = _story_json_text(req["story_json"])
            d["notes"] = notes_j
        if not raw:
            raise StudioError("empty_input", "Paste the story or script, or upload a story.md / story.json / script file.")
        notes, lines = parse_story_text(raw)
        d["notes"] = {**(d.get("notes") or {}), **notes}
        d["input"] = dict(chars=len(raw))
        d["lines"] = [dict(id=f"n{i + 1:02d}", text=t) for i, t in enumerate(lines)]
        errs, warns = lint_script(lines)
        if errs:
            raise StudioError("script_invalid", "The script cannot be narrated as written.", reasons=errs, hint="Write numbers, abbreviations and English words in Devanagari.")
        d["warnings"] += warns
    else:
        path, story_text = load_segments_input(req, dd)
        d["narration"] = path
        notes, _ = parse_story_text(story_text) if story_text.strip() else ({}, [])
        d["notes"] = notes
        segs = json.load(open(path, encoding="utf-8"))["segments"]
        d["lines"] = [dict(id=s["id"], text=s["text"]) for s in segs]
        d["input"] = dict(segments=len(segs), audio=os.path.basename(json.load(open(path, encoding="utf-8"))["audio"]))
        d["settings"]["voice"] = "provided"
    n = len(d["lines"])
    if not 8 <= n <= 40:
        raise StudioError("unsupported_story", "This story cannot be staged by the studio.", reasons=[f"{n} narration segments: a Short needs 8-40"], hint="Add or merge lines so the script has 8-40 segments.")
    if not (d.get("notes") or {}).get("title"):
        d["warnings"].append("No title given: the end card will read 'कहानी'. Set one with Edit Story.")
    _analyze_lines(d)
    return save_draft(d)


def _story_json_text(sj):
    """story.json (topic-story format, a story-graph, {lines:[..]} or {segments:[..]}) -> (script text, notes)"""
    if isinstance(sj, str):
        try:
            sj = json.loads(sj)
        except ValueError as e:
            raise StudioError("invalid_input", "story.json is not valid JSON.", reasons=[str(e)])
    if isinstance(sj, list):
        sj = dict(lines=sj)
    lines = sj.get("lines") or [b.get("text") for b in sj.get("beats", [])] or [s.get("text") for s in sj.get("segments", [])]
    lines = [l for l in lines if isinstance(l, str) and l.strip()]
    if not lines:
        raise StudioError("invalid_input", "story.json has no lines / beats / segments with text.")
    notes = {}
    if sj.get("title"):
        notes["title"] = sj["title"]
    c = (sj.get("cast") or {})
    if isinstance(c.get("protagonist"), dict) and c["protagonist"].get("gender") in ("male", "female"):
        notes["protagonist"] = {k: v for k, v in c["protagonist"].items() if k in ("name", "gender", "archetype")}
    for k in ("sender", "amount", "location", "time"):
        if sj.get(k):
            notes[k] = sj[k]
    return "\n".join(lines), notes


# ------------------------------------------------------------------------------------------------ edits
def edit_story(did, edits=None, regenerate=False, settings=None):
    """edits = {"title":..., "beats": {id: {act, loc, time, emotion}}, "cast": {"protagonist": {...}, "partner": {...}, "extras": [...]}}; regenerate -> next variation"""
    d = load_draft(did)
    edits = edits or {}
    if settings:
        d["settings"] = {**d["settings"], **{k: v for k, v in settings.items() if k in ("character", "environment", "director", "typography", "duration", "format", "level")}}
        if (d["settings"].get("typography") or {}).get("captions") is False:
            d["settings"]["director"]["captions"] = False
        elif "captions" in (d["settings"].get("director") or {}):
            d["settings"]["director"].pop("captions")
    if regenerate:
        d["variation"] = int(d.get("variation", 0)) + 1
        if d["mode"] == "create":
            d["lines"], d["notes"], prov = _topic_lines(d["input"]["topic"], d["variation"])
            d["story_edits"] = {}
            d["provenance"].append(prov)
    if edits.get("beats"):
        unknown = [b for b in edits["beats"] if b not in {x["id"] for x in d["graph"]["beats"]}]
        if unknown:
            raise StudioError("unknown_beat", f"there is no beat '{unknown[0]}'")
        keep = dict(d.get("story_edits") or {})
        for bid, ch in edits["beats"].items():
            keep[bid] = {**keep.get(bid, {}), **{k: v for k, v in ch.items() if k in ("act", "loc", "time", "emotion")}}
        d["story_edits"] = keep
    if edits.get("title"):
        d["notes"] = {**(d.get("notes") or {}), "title": str(edits["title"])[:80]}
    if edits.get("cast"):
        d["settings"]["character"] = {**(d["settings"].get("character") or {}), **edits["cast"]}
    _analyze_lines(d)
    return save_draft(d)


def edit_script(did, segments=None, regenerate=None, log=print):
    """segments = [{id, text}] (only changed ones needed); regenerate = [ids] -> LLM re-write, validated"""
    d = load_draft(did)
    if d.get("narration"):
        raise StudioError("provided_narration", "In Production mode the narration is provided (audio + timings), so its text cannot be edited here.", hint="Switch to Script mode to write and narrate your own text.")
    by = {l["id"]: l for l in d["lines"]}
    notes = []
    for s in segments or []:
        if s["id"] not in by:
            raise StudioError("unknown_beat", f"there is no segment '{s['id']}'")
        t = re.sub(r"\s+", " ", (s.get("text") or "").strip())
        if not t:
            raise StudioError("script_invalid", "A segment cannot be empty.", reasons=[f"segment {s['id']} is empty"])
        by[s["id"]]["text"] = t
    if regenerate:
        for bid in regenerate:
            if bid not in by:
                raise StudioError("unknown_beat", f"there is no segment '{bid}'")
            new, why = _llm_rewrite(d, bid, log)
            if new:
                by[bid]["text"] = new
                notes.append(f"{bid}: rewritten")
            else:
                notes.append(f"{bid}: kept - {why}")
    errs, warns = lint_script([l["text"] for l in d["lines"]])
    if errs:
        raise StudioError("script_invalid", "The script cannot be narrated as written.", reasons=errs, hint="Write numbers, abbreviations and English words in Devanagari.")
    d["warnings"] = warns + notes
    _analyze_lines(d)
    return save_draft(d)


def _llm_models():
    try:
        tags = json.load(urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2))
        return [m["name"] for m in tags.get("models", [])]
    except Exception:
        return []


def _llm_rewrite(d, bid, log=print, tries=3):
    have = _llm_models()
    model = next((m for m in ("qwen3:14b", "qwen3.5:9b", "gemma4:12b-mlx") if m in have), None)
    if not model:
        raise StudioError("llm_unavailable", "Regenerating a segment needs a local LLM (ollama with qwen3 or gemma), and none is reachable.", hint="Edit the text of the segment directly instead.", status=503)
    lines = d["lines"]
    i = next(k for k, l in enumerate(lines) if l["id"] == bid)
    act = next((b["act"] for b in d["graph"]["beats"] if b["id"] == bid), "")
    ctx = "\n".join(f"{k + 1}. {l['text']}" + ("   <-- REWRITE THIS LINE" if k == i else "") for k, l in enumerate(lines))
    old = lines[i]["text"]
    for t in range(tries):
        body = {"model": model, "stream": False, "think": False, "format": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}, "options": {"temperature": 0.7 + 0.1 * t, "seed": 11 + t, "num_ctx": 4096},
                "messages": [{"role": "user", "content": f"Below is a short Hindi cyber-safety micro-story, one narration line per row. Rewrite ONLY the marked line in different words. Keep its meaning, its dramatic role ({act}), the same people and the same "
                                                          f"tense. Hindi in Devanagari only: no digits, no English letters, 4 to 14 words, one sentence, plain spoken language.\n\n{ctx}\n\nReturn JSON {{\"text\": \"...\"}}."}]}
        try:
            req = urllib.request.Request("http://localhost:11434/api/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})
            new = json.loads(json.load(urllib.request.urlopen(req, timeout=120))["message"]["content"])["text"].strip()
        except Exception as e:                                                           # noqa: BLE001
            return None, f"the LLM did not answer ({type(e).__name__})"
        new = re.sub(r"\s+", " ", new)
        if new == old or not (4 <= len(new.split()) <= 16) or not ALLOWED.match(new):
            continue
        trial = copy.deepcopy(d)
        trial["lines"][i]["text"] = new
        try:
            _analyze_lines(trial)
        except StudioError:
            continue
        if next(b["act"] for b in trial["graph"]["beats"] if b["id"] == bid) != act:
            continue
        return new, None
    return None, f"no valid alternative found in {tries} tries (it must stay clean Devanagari and keep the same dramatic role)"


# ------------------------------------------------------------------------------------------------ approve -> job request
def job_request(d, kind="generate"):
    g = d["graph"]
    dur = d["settings"].get("duration")
    return dict(kind=kind, mode=d["mode"], draft_id=d["id"], settings=d["settings"], lines=d["lines"], notes=d.get("notes") or {}, story_edits=d.get("story_edits") or {}, variation=d.get("variation", 0), graph=g,
                narration=d.get("narration"), seed=11, samples=10, critique_rounds=1,
                tts=dict(voice=d["settings"]["voice"], tempo=1.08, lo=(dur - 2.5) if dur else 44.0, hi=(dur + 2.5) if dur else 60.0, target=dur), title=g["title"], created=time.time())
