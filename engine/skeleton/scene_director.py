"""SCENE DIRECTOR: story graph (`story_semantics.analyze`) + narration timing -> a skeleton plan (version 4). Nothing here is written for one story: every location, prop, partner, camera and light decision is derived from
the graph (acts, locations, times, roles, emotions, props).

  * scenes: a run of beats in one (location, time). Each scene has a stage LAYOUT (environments/locations.py): seat, phone spot, entrance, stops, hand-over point, counter / ATM ...
    A scene change is a hard cut with the actors re-blocked (teleport at the cut). Per-shot environment + per-scene target registry travel in the plan.
  * cast: A = protagonist (faces right); D = principal partner; X1/X2 = further roles; anyone not in the current scene waits parked far outside the set.
  * camera language: every act offers several framings; `pick_cam` chooses deterministically (seeded by the story) and never repeats the same framing on consecutive shots; long beats are covered by TWO shots.
  * lighting: `lighting_presets.preset(time, ...)`: day scenes get sun + day sky, night scenes moon; mood follows the beat's emotion.
  * psychology: emotions map to acting (procedural face) and to Open Peeps replacement faces on peak beats.
"""
import hashlib
import json

from engine.dsl import variation as VAR
from engine.environments import bedroom_wide as BW, locations as LOC
from engine.skeleton import acts as AC, dna2, lab_dna as LD, lighting_presets as LP

FPS = 30
TAIL = 3.0
PARK = 2600.0                       # parked characters wait this far right (facing left) / left (facing right) of the set
TWO_PERSON = {"MEET", "PERSON_ENTERS", "CONVERSE", "EYE_CONTACT", "OTHER_LOOKS_AT_PHONE", "HAND_OVER", "GIVE_OBJECT", "RECEIVE_OBJECT", "OTHER_REACTS", "BOTH_REALIZE"}
MOOD_OF = dict(neutral="dim", fear="fear", suspicion="fear", hope="warm", relief="relief", anger="pressure", sadness="isolated", confusion="dim", realization="fear")
FACE_ATOM_FOR = dict(fear="fear", suspicion="suspicious", hope="smile", relief="calm", anger="anger", sadness="tired", confusion="worried", realization="dread")

# camera options per act: (target, size, move). P = the partner's id. The first option is the default; `pick_cam` rotates through the others to avoid repeats.
CAMS = {
    "ESTABLISH": [("stage", "wide", "push"), ("A.full", "full", "hold")], "ARRIVE": [("A.full", "full", "track"), ("stage", "wide", "hold")],
    "PHONE_ALERT": [("A.reach", "two_reach", "reveal"), ("A.head", "medium", "push")], "LOOK_AT_PHONE": [("A.head", "medium", "isolate"), ("A.head", "close", "hold")],
    "EYES_CHANGE": [("A.head", "close", "push"), ("A.head", "medium", "drift")], "REACH_PHONE": [("A.reach", "two_reach", "drift"), ("A.full", "full", "hold")],
    "PICK_UP": [("A.phone", "close", "push")], "TAKE_PHONE": [("A.phone", "close", "push"), ("A.head", "medium", "hold")],
    "READ_MESSAGE": [("A.head", "medium", "rack_focus"), ("A.head", "close", "push")], "REALIZE": [("A.head", "close", "push"), ("A.head", "medium", "isolate")],
    "STAND_UP": [("A.full", "full", "pull"), ("A.head", "medium", "pull")], "WALK_ACROSS": [("A.full", "full", "track"), ("A+P", "two", "track")],
    "PERSON_ENTERS": [("A+P", "two", "reveal"), ("A.full", "full", "hold")], "EYE_CONTACT": [("A+P", "two", "hold"), ("P.head", "medium", "isolate")],
    "OTHER_LOOKS_AT_PHONE": [("P.head", "medium", "isolate"), ("A+P", "two", "hold")], "HAND_OVER": [("A+P", "two", "truck"), ("A+P", "two_reach", "hold")],
    "GIVE_OBJECT": [("A+P", "two", "truck"), ("A+P", "two_reach", "hold")], "RECEIVE_OBJECT": [("A+P", "two", "truck"), ("A.head", "medium", "push")],
    "OTHER_REACTS": [("P.head", "close", "push"), ("P.head", "medium", "isolate")], "INSERT_SCREEN": [(None, None, None)], "VISUALIZE_FLOW": [(None, None, None)],
    "BOTH_REALIZE": [("A+P", "two", "pull"), ("A+P", "two", "hold")], "CLOSE_UP": [("A.head", "close", "isolate"), ("A.head", "medium", "hold")],
    "RESOLVE": [("A+P", "reveal", "pull"), ("A.full", "full", "pull")], "MEET": [("A+P", "two", "reveal"), ("A+P", "two", "hold")],
    "CONVERSE": [("A+P", "two", "hold"), ("P.head", "medium", "push"), ("A.head", "medium", "isolate"), ("A+P", "two", "drift")], "SUSPECT": [("A.head", "close", "push"), ("A.head", "medium", "isolate")],
    "OBSERVE": [("A.head", "medium", "drift"), ("A.full", "full", "hold")], "SIT_DOWN": [("A.full", "full", "pull")], "USE_ATM": [("A+atm", "two_reach", "push"), ("A.full", "full", "hold")],
    "COUNT_MONEY": [("A.head", "medium", "push"), ("A.phone", "close", "push")], "READ_DOCUMENT": [("A.head", "medium", "push"), ("A.full", "full", "hold")], "TYPE_LAPTOP": [("A.head", "medium", "hold"), ("A.full", "full", "hold")],
    "PHONE_CALL": [("A.head", "medium", "isolate"), ("A.head", "close", "push")], "RUN_AWAY": [("A.full", "full", "track")], "CROWD_WATCH": [("stage", "wide", "drift"), ("A.full", "full", "hold")],
}
GP = {"PHONE_ALERT": [("arcs", "phone_free", 0.05, 1.1, 0.85, "the phone vibrating")], "EYES_CHANGE": [("ticks", "eyes", 0.1, 0.7, 0.6, "the eyes narrow")], "PICK_UP": [("rays", "phone", 0.3, 1.0, 0.35, "light from the screen")],
      "TAKE_PHONE": [("rays", "phone", 0.3, 1.0, 0.35, "light from the screen")], "REALIZE": [("worry", "temple", 0.4, 1.1, 0.9, "dread")], "OTHER_REACTS": [("scribble", "head", 0.6, 1.0, 0.6, "alarm")],
      "OTHER_LOOKS_AT_PHONE": [("arrow", "phone", 0.3, 1.0, 0.8, "attention drawn to the object")], "BOTH_REALIZE": [("ticks", "eyes", 0.1, 0.7, 0.9, "the jolt of realisation")],
      "RESOLVE": [("rays", "lamp", 0.3, 2.4, 0.5, "warm light returns")], "SUSPECT": [("ticks", "eyes", 0.2, 0.7, 0.5, "doubt")], "INSERT_SCREEN": [("ring", "ui", 0.5, 1.0, 0.9, "the demand")]}


def _cam(target, size, move, **k):
    return dict(target=target, size=size, move=move, **k)


class Director:
    def __init__(self, graph, nar, seed, fixes, style_hint=None):
        self.g, self.nar, self.seed, self.fixes = graph, nar, seed, fixes or {}
        self.beats = graph["beats"]
        self.segs = {s["id"]: s for s in nar["segments"]}
        miss = [b["id"] for b in self.beats if b["id"] not in self.segs]
        if miss:
            raise ValueError(f"narration is missing beats {miss}")
        st, en = (lambda i: self.segs[i]["start"]), (lambda i: self.segs[i]["end"])
        self.dur = round(en(self.beats[-1]["id"]) + TAIL, 3)
        self.cuts = [0.0] + [round(max(st(b["id"]) - 0.12, 0.0), 3) for b in self.beats[1:]] + [self.dur]
        self.rng = VAR.rng(graph["story_id"], "scene_director", "cams")
        self.acts, self.shots, self.hist = [], [], []
        self.ids = {}                                        # role -> actor id
        self._cast()
        self._scenes()

    # ------------------------------------------------------------------ cast
    def _cast(self):
        c = self.g["cast"]
        self.ids = {}
        if c.get("principal"):
            self.ids[c["principal"]["role"]] = "D"
        for k, e in enumerate(c.get("extras", []), 1):
            self.ids[e["role"]] = f"X{k}"

    def characters(self):
        c, sid = self.g["cast"], self.g["story_id"]
        sc0 = self.scenes[0]
        pro = c["protagonist"]
        a_dna = LD.archetype(pro["archetype"], seed=f"{sid}:A")
        if pro.get("gender") == "female" and a_dna["gender_presentation"] != "feminine":
            a_dna = dna2.make(f"{sid}:A", "young_woman" if "young" in pro["archetype"] else "elderly_woman")
        if pro.get("gender") == "male" and a_dna["gender_presentation"] == "feminine":
            a_dna = dna2.make(f"{sid}:A", "young_man" if "young" in pro["archetype"] else "elderly_man")
        first = self.scenes[0]
        a_x = first["lay"]["seat_x"] if (first["A_start"] == "sit" and first["lay"].get("seat_x")) else (-260.0 if first["arrive"] else first["lay"]["A_stop"])
        out = {"A": dict(name=pro.get("name") or "A", role="protagonist", dna=a_dna, facing=1, origin=[float(first["lay"]["A_stop"] if first["A_start"] != "sit" else first["lay"]["seat_x"]), BW.FLOOR_Y],
                         view="three_quarter", hand_set="full", start=first["A_start"])}
        ents = ([("D", c["principal"])] if c.get("principal") else []) + [(f"X{k}", e) for k, e in enumerate(c.get("extras", []), 1)]
        for cid, e in ents:
            face = self._facing(cid)
            dna = self._dna(e, f"{sid}:{cid}")
            out[cid] = dict(name=e["role"], role=e["role"], dna=dna, facing=face, origin=[PARK if face < 0 else -1400.0, BW.FLOOR_Y], view="three_quarter", hand_set="full", start="stand")
        if any(b["act"] == "CROWD_WATCH" for b in self.beats):                       # background people: two passers-by (only when the story has a crowd beat)
            for k, off in enumerate((0, 1), 1 + len(ents)):
                cid = f"X{k}"
                if cid not in out:
                    out[cid] = dict(name="passer-by", role="crowd", dna=LD.archetype(("customer", "student")[off % 2], seed=f"{sid}:{cid}"), facing=-1, origin=[PARK, BW.FLOOR_Y], view="three_quarter", hand_set="full", start="stand")
                    self.ids[f"crowd{k}"] = cid
        return out

    def _dna(self, e, seed):
        d = LD.archetype(e["archetype"], seed=seed)
        want = e.get("gender", "either")
        if want == "feminine" and d["gender_presentation"] != "feminine":
            d = dna2.make(seed, {"parent": "middle_aged_woman", "teacher": "middle_aged_woman"}.get(e["archetype"], "young_woman"))
        if want == "masculine" and d["gender_presentation"] == "feminine":
            d = dna2.make(seed, {"parent": "middle_aged_man", "teacher": "middle_aged_man"}.get(e["archetype"], "middle_aged_man"))
        return d

    def _facing(self, cid):
        """a partner faces the protagonist: right if standing left of A, left if standing right of A (or seated across the table)"""
        for sc in self.scenes:
            if cid in sc["partners"]:
                lay = sc["lay"]
                return 1 if (lay["D_stop"] < lay["A_stop"] and not lay.get("D_sit_x")) else -1
        return -1

    # ------------------------------------------------------------------ scenes
    def _scenes(self):
        self.scenes = []
        for s in self.g["scenes"]:
            loc = LOC.resolve(s["loc"], s["time"])
            idx = [i for i, b in enumerate(self.beats) if b["id"] in s["beats"]]
            i0, i1 = idx[0], idx[-1]
            acts = [self.beats[i]["act"] for i in idx]
            partners = []
            for i in idx:
                b = self.beats[i]
                if b["act"] in TWO_PERSON or b["act"] == "PHONE_CALL" and False:
                    pid = next((self.ids[r] for r in b.get("roles", []) if r in self.ids), None) or self._principal_or_x(idx, i)
                    if pid and pid not in partners:
                        partners.append(pid)
            lay = loc["layout"]
            a_start = "sit" if (lay.get("sit") and acts[0] in ("ESTABLISH", "SIT_DOWN") and not lay.get("D_sit_x")) else "stand"      # a table for two: the protagonist arrives standing beside it (a hand-over across the table is out of reach)
            self.scenes.append(dict(loc=s["loc"], time=loc["time"], family=loc["family"], lay=lay, notes=loc["notes"], i0=i0, i1=i1, partners=partners, A_start=a_start, arrive=acts[0] == "ARRIVE",
                                    enters=next((b["act"] for b in (self.beats[i] for i in idx) if b["act"] in ("PERSON_ENTERS", "MEET")), None), env=dict(family=loc["family"], variation=dict(palette=VAR.seed_int(self.g["story_id"], s["loc"], "pal") % 3, time=loc["time"], **LOC.EXTRA.get(s["loc"], {})), seed=VAR.seed_int(self.g["story_id"], s["loc"], "seed") % 1000)))
        self.scene_of = {}
        for k, sc in enumerate(self.scenes):
            for i in range(sc["i0"], sc["i1"] + 1):
                self.scene_of[i] = k

    def _principal_or_x(self, idx, i):
        return "D" if "D" in self.ids.values() else None

    def partner(self, i):
        sc = self.scenes[self.scene_of[i]]
        rid = next((self.ids[r] for r in self.beats[i].get("roles", []) if r in self.ids), None)
        return rid or (sc["partners"][0] if sc["partners"] else "D")

    # ------------------------------------------------------------------ helpers
    def add(self, cid, **k):
        self.acts.append(dict(char=cid, **k))

    def pick_cam(self, act, i):
        opts = CAMS.get(act) or [("A.head", "medium", "hold")]
        recent = self.hist[-2:]
        start = self.rng.randrange(len(opts))
        for j in range(len(opts)):
            tg, sz, mv = opts[(start + j) % len(opts)]
            if (tg, sz) not in [(r[0], r[1]) for r in recent] or len(opts) == 1:
                break
        self.hist.append((tg, sz, mv))
        return tg, sz, mv

    def targets(self, sc):
        lay = sc["lay"]
        t = dict(PHONE=list(lay["phone"]), nightstand_phone=list(lay["phone"]), DOOR=list(lay["door"]), A_STOP=[lay["A_stop"], BW.FLOOR_Y], D_STOP=[lay["D_stop"], BW.FLOOR_Y], HANDOVER=list(lay["handover"]), LAMP=list(lay["lamp"]),
                 SCREEN=[540.0, 900.0], MONEY=[540.0, 900.0], WINDOW=[865.0, 560.0], NIGHTSTAND=[670.0, 1180.0], BED=[200.0, 1230.0])
        if "atm" in lay:
            t["ATM"] = [lay["atm"][0] + 180.0, 780.0]
        if lay.get("counter"):
            t["COUNTER"] = list(lay["counter"])
        return t


def _lighting(sc, emotion, act, resolve_night):
    mood = MOOD_OF.get(emotion, "dim")
    lt = LP.preset(sc["time"], mood, phone=1.0 if sc["time"] == "night" else 0.4)
    if act == "RESOLVE":
        lt = LP.preset(sc["time"], "relief", lamp=1.0 if sc["time"] == "night" else 0.0, phone=0.0)
    return lt


def apply_fixes(sh, fx):
    from engine.skeleton import auto_director as AD
    return AD.apply_fixes(sh, fx)


def build_plan(graph, nar, seed=11, name=None, tts=None, fixes=None):
    """story graph + paced narration -> plan v4. Deterministic: same graph + narration + fixes -> same plan."""
    from engine.skeleton import scene_acts
    d = Director(graph, nar, seed, fixes)
    fixes = fixes or {}
    chars = d.characters()
    n = len(d.beats)
    # ---- blocking at every scene start (teleport at the cut) and the per-scene target registry
    target_scenes = []
    for k, sc in enumerate(d.scenes):
        t0 = d.cuts[sc["i0"]]
        t1 = d.cuts[sc["i1"] + 1]
        target_scenes.append(dict(t0=t0, t1=t1, targets=d.targets(sc)))
        scene_acts.block_scene(d, k, sc, t0, chars)
    for i, b in enumerate(d.beats):
        scene_acts.compile_beat(d, i, b, d.cuts[i], d.cuts[i + 1], chars)
    shots = d.shots
    for s_ in shots:
        s_["actions"] = [x for x in d.acts if s_["t0"] - 1.0 <= x["t"] < s_["t1"]]
    sfx = scene_acts.sfx_for(d)
    mood = []
    cur = None
    for s_ in shots:
        m = s_.get("audio_mood", "dim")
        if cur and cur[2] == m:
            cur[1] = s_["t1"]
        else:
            cur = [s_["t0"], s_["t1"], m]
            mood.append(cur)
    mood[-1][1] = d.dur
    sc0 = d.scenes[0]
    res_t = next((d.cuts[i] for i, b in enumerate(d.beats) if b["act"] == "RESOLVE"), None)
    night_res = d.scenes[-1]["time"] == "night"
    plan = dict(kind="skeleton_short", version=4, title=graph["title"], story_id=graph["story_id"], seed=seed, fps=FPS, format=dict(w=1080, h=1920, name="9x16"), duration=d.dur, name=name or graph.get("slug", graph["story_id"]),
                environment=sc0["env"], characters=chars, cast_in_short=list(chars), narration=dict(segments=nar["segments"], audio=nar.get("audio"), tts=tts or nar.get("tts", "unknown"), tempo=nar.get("tempo", 1.0)),
                targets=target_scenes[0]["targets"], target_scenes=target_scenes, shots=shots, sfx=sfx, mood_track=[tuple(m) for m in mood], title_card=dict(t0=round(d.dur - 1.9, 3), t1=d.dur, text=graph["title"]),
                lamp_on=round(res_t + 0.3, 3) if (res_t is not None and night_res) else 1e9, hall_on=1e9, rim=dict(moon=0.5), duration_range=[40.0, 62.0], acts=[b["act"] for b in d.beats],
                scenes=[dict(loc=s["loc"], time=s["time"], family=s["family"], t0=target_scenes[k]["t0"], t1=target_scenes[k]["t1"], notes=s["notes"], cast=["A"] + list(s["partners"]) + ([c for c in chars if chars[c]["role"] == "crowd"] if any(d.beats[i]["act"] == "CROWD_WATCH" for i in range(s["i0"], s["i1"] + 1)) else [])) for k, s in enumerate(d.scenes)], story_graph=graph["story_id"], audio_cfg=dict(fixes.get("_audio", {})))
    if getattr(d, "camera_adjustments", None):                                       # explicit camera intents the geometry could not honour as asked (recorded, never silent)
        plan["camera_adjustments"] = d.camera_adjustments
    return plan
