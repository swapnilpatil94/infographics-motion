"""Scene plans (skeleton_short v2) for the interaction / parallax / lighting evidence videos. Same renderer as the Short: plan -> Blender rig -> 2.5D compositor."""
import json
import os

from engine.environments import bedroom_wide as BW, study_room as SR
from engine.skeleton import dna2, short as SH
from engine.shorts.raster import ROOT

OUT = os.path.join(ROOT, "output/tests")


def _shots(spec, lighting_default=None):
    out = []
    for i, (t0, t1, cam, kw) in enumerate(spec):
        out.append(dict(id=f"S{i + 1:02d}", treatment="skeleton", t0=t0, t1=t1, beats=[], segs=[], gp=kw.get("gp", []), transition_in=kw.get("transition_in", "cut"), sfx=[], phase="-",
                        location="room", purpose=kw.get("purpose", ""), camera=cam, lighting=kw.get("lighting", lighting_default or dict(mood="dim", moon=1.0, phone=1.0)), actions=[]))
    return out


def _attach(shots, acts):
    for s in shots:
        s["actions"] = [a for a in acts if s["t0"] - 1.0 <= a["t"] < s["t1"]]


def _base(name, dur, env, chars, shots, targets, **kw):
    return dict(kind="skeleton_short", version=2, title=name, story_id=name, seed=5, fps=30, format=dict(w=1080, h=1920, name="9x16"), duration=dur, name=name, environment=env, characters=chars,
                cast_in_short=list(chars), narration=dict(segments=[], audio=None, tts="none", tempo=1.0), targets=targets, shots=shots, sfx=[], mood_track=[(0.0, dur, "dim")], rim=dict(moon=0.5), **kw)


def interaction_plan():
    A = dna2.make("int:A", "young_man", {"wardrobe.top": "sweater", "wardrobe.bottom": "jeans", "wardrobe.shoes": "sneakers", "wardrobe.palette": "sage", "wardrobe.accessories": [], "glasses": "* None"})
    B = dna2.make("int:B", "middle_aged_woman", {"wardrobe.top": "kurta", "wardrobe.bottom": "salwar", "wardrobe.shoes": "sandals", "wardrobe.palette": "plum", "wardrobe.accessories": ["earrings"]})
    chars = {"A": dict(name="A", dna=A, facing=1, origin=[300.0, BW.FLOOR_Y], view="three_quarter", hand_set="full", start="sit"),
             "D": dict(name="B", dna=B, facing=-1, origin=[1335.0, BW.FLOOR_Y], view="three_quarter", hand_set="full", start="stand")}
    targets = dict(PHONE=list(SR.PHONE_POS), TABLE=[730.0, SR.TABLE_TOP], CHAIR=[300.0, 1230.0], DOOR=[960.0, 1000.0], A_HAND=[640.0, 1500.0], B_STOP=[930.0, 1500.0], HANDOVER=[780.0, 880.0], LAMP=[700.0, 940.0])
    cam = lambda t, s, m, **k: dict(target=t, size=s, move=m, **k)
    shots = _shots([(0.0, 5.4, cam("A+D", "two", "push"), dict(purpose="A alone at the table: the phone rings, he looks, reaches, picks it up, reads")),
                    (5.4, 9.0, cam("A+D", "two", "reveal", dir=-1), dict(purpose="B enters; A looks at B; B looks at A")),
                    (9.0, 11.6, cam("D.head", "close", "isolate"), dict(purpose="B speaks (lip-sync); A reacts")),
                    (11.6, 14.6, cam("A.full", "full", "track"), dict(purpose="A stands and walks to B")),
                    (14.6, 17.0, cam("A+D", "two", "truck", dir=1), dict(purpose="A hands the phone to B")),
                    (17.0, 20.4, cam("D.head", "close", "push"), dict(purpose="B looks at the phone; both react")),
                    (20.4, 24.0, cam("A+D", "reveal", "pull"), dict(purpose="both realise; lamp on", lighting=dict(mood="relief", moon=0.6, phone=0.0, hall=0.4, lamp=1.0)))],
                   dict(mood="dim", moon=0.9, phone=1.0, hall=1.0))
    acts = []
    A_ = lambda **k: acts.append(dict(char="A", **k))
    B_ = lambda **k: acts.append(dict(char="D", **k))
    A_(action="idle", t=0.0, dur=1.2)
    A_(action="buzz", t=1.0, dur=1.0, intensity=0.9)
    A_(action="look_at", t=1.3, dur=1.2, target="PHONE", track=True, emotion="curious", intensity=0.6)
    A_(action="reach", t=2.6, dur=1.2, target="PHONE", emotion="hesitant", intensity=0.7, grip="hold_phone")
    A_(action="grab", t=3.85, dur=0.1, prop="phone", from_table=True)
    A_(action="hold_phone", t=4.05, dur=0.8, pos="chest", emotion="hesitant", intensity=0.6)
    A_(action="read_phone", t=4.6, dur=2.0, emotion="nervous", intensity=0.6)
    B_(action="walk_to", t=5.2, dur=2.3, target="B_STOP", stop_before=0.0, speed=230.0, stride_scale=0.7, emotion="hesitant", intensity=0.5)
    B_(action="look_at", t=6.4, dur=2.4, target="PERSON_A", track=True)
    A_(action="look_at", t=7.2, dur=2.0, target="PERSON_D", track=True, emotion="nervous", intensity=0.5)
    words = [dict(word=w, start=9.1 + 0.42 * i, end=9.1 + 0.42 * i + 0.36) for i, w in enumerate(["बेटा", "क्या", "हुआ", "तुम", "इतने", "घबराए", "क्यों", "हो"])]
    B_(action="speak", t=9.1, dur=3.4, words=words)
    B_(action="gesture", t=9.3, dur=2.6, emotion="hesitant", intensity=0.5, hand="R")
    A_(action="flinch", t=10.6, dur=0.6, emotion="fearful", intensity=0.5)
    A_(action="face", t=10.8, dur=0.4, name="worried")
    A_(action="stand", t=11.7, dur=1.3, emotion="fearful", intensity=0.6, hold_R=True)
    A_(action="walk_to", t=13.0, dur=1.4, target="A_HAND", stop_before=0.0, speed=170.0, stride_scale=0.5, hold_R=True)
    A_(action="hand_over", t=14.6, dur=1.0, target="PERSON_D", point="HANDOVER", prop="phone", emotion="hesitant", intensity=0.6)
    B_(action="receive", t=14.7, dur=1.0, point="HANDOVER", prop="phone", emotion="hesitant", intensity=0.5)
    A_(action="release", t=15.85, dur=0.5, prop="phone")
    B_(action="hold_phone", t=16.1, dur=0.7, pos="chest", emotion="hesitant", intensity=0.5)
    B_(action="look_at", t=16.3, dur=1.4, target="PHONE", track=True, emotion="suspicious", intensity=0.6)
    B_(action="read_phone", t=16.9, dur=2.0, emotion="nervous", intensity=0.5)
    B_(action="flinch", t=17.4, dur=0.6, emotion="fearful", intensity=0.6)
    A_(action="look_at", t=17.2, dur=2.0, target="PERSON_D", track=True)
    A_(action="realization", t=19.0, dur=1.6, emotion="shocked", intensity=0.7)
    B_(action="freeze", t=19.2, dur=0.7)
    B_(action="face", t=19.9, dur=0.4, name="fear")
    A_(action="relief", t=21.5, dur=2.0, emotion="relieved", intensity=0.5)
    B_(action="relief", t=21.9, dur=1.8, emotion="relieved", intensity=0.5)
    _attach(shots, acts)
    p = _base("multi_character_interaction", 24.0, dict(family="study_room", variation=dict(palette=1), seed=3), chars, shots, targets, lamp_on=20.7, hall_on=4.8)
    p["overlays"] = [dict(t0=0.0, t1=24.0, x=14, y=14, size=26, w=1050, text="Person A · Person B · Phone · Table · Chair · semantic targets: PHONE / PERSON_x / HANDOVER / B_STOP / A_HAND")]
    return p


def contact_plan():
    """hand <-> phone contact test: a man at a table; reach, approach, contact, grip, lift, read, put it back. Camera close on the hand and phone."""
    A = dna2.make("con:A", "young_man", {"wardrobe.top": "sweater", "wardrobe.bottom": "jeans", "wardrobe.shoes": "sneakers", "wardrobe.palette": "sage", "wardrobe.accessories": [], "glasses": "* None"})
    chars = {"A": dict(name="A", dna=A, facing=1, origin=[300.0, BW.FLOOR_Y], view="three_quarter", hand_set="full", start="sit")}
    targets = dict(PHONE=list(SR.PHONE_POS), TABLE=[730.0, SR.TABLE_TOP], CHAIR=[300.0, 1230.0], LAMP=[700.0, 940.0], nightstand_phone=list(SR.PHONE_POS))
    cam = lambda t, s, m, **k: dict(target=t, size=s, move=m, **k)
    shots = _shots([(0.0, 3.4, cam("A.reach", "two_reach", "push"), dict(purpose="reach and approach")), (3.4, 6.4, cam("A.phone", "close", "hold"), dict(purpose="contact, grip, lift")),
                    (6.4, 9.6, cam("A.phone", "close", "push"), dict(purpose="read")), (9.6, 12.6, cam("A.reach", "two_reach", "hold"), dict(purpose="put back, release"))], dict(mood="dim", moon=0.9, phone=1.0, hall=0.0))
    acts = [dict(char="A", action="idle", t=0.0, dur=12.6), dict(char="A", action="look_at", t=0.2, dur=1.0, target="PHONE", track=True, emotion="curious", intensity=0.5),
            dict(char="A", action="reach", t=1.0, dur=2.6, target="PHONE", emotion="calm", intensity=0.5, grip="grab"), dict(char="A", action="grab", t=3.62, dur=0.1, prop="phone", from_table=True),
            dict(char="A", action="hold_phone", t=3.9, dur=1.4, pos="chest", emotion="calm", intensity=0.5), dict(char="A", action="read_phone", t=5.6, dur=3.6, emotion="calm", intensity=0.5),
            dict(char="A", action="place", t=9.3, dur=1.6, target="PHONE")]
    _attach(shots, acts)
    return _base("hand_phone_contact", 12.6, dict(family="study_room", variation=dict(palette=1), seed=3), chars, shots, targets, lamp_on=99.0, hall_on=99.0)


def parallax_plan():
    A = dna2.make("par:A", "office_worker", {"wardrobe.accessories": []})
    chars = {"A": dict(name="A", dna=A, facing=1, origin=[540.0, BW.FLOOR_Y], view="three_quarter", hand_set="basic", start="stand")}
    cam = lambda t, s, m, **k: dict(target=t, size=s, move=m, **k)
    shots = _shots([(0.0, 5.0, cam("stage", "wide", "truck", dir=1), dict(purpose="lateral truck: layers slide by different amounts")),
                    (5.0, 9.0, cam("stage", "wide", "truck", dir=-1), dict(purpose="truck back")),
                    (9.0, 13.0, cam("A.full", "full", "dolly_through"), dict(purpose="dolly through the layers"))])
    acts = [dict(char="A", action="idle", t=0.0, dur=13.0)]
    _attach(shots, acts)
    p = _base("parallax_depth_test", 13.0, dict(family="bedroom_wide", variation=dict(palette=0), seed=4), chars, shots, dict(PHONE=list(BW.PHONE_POS), LAMP=[600.0, 1110.0]))
    p["debug_markers"] = [dict(par=1.3, x=340, color=[255, 60, 60], depth=0.7), dict(par=1.0, x=540, color=[60, 220, 90], depth=1.6), dict(par=0.86, x=740, color=[70, 120, 255], depth=2.4),
                          dict(par=0.6, x=940, color=[255, 210, 40], depth=3.2)]
    p["overlays"] = [dict(t0=0.0, t1=13.0, x=14, y=14, size=24, w=1050, text="RED par 1.3 (foreground) · GREEN par 1.0 (character) · BLUE par 0.86 (mid) · YELLOW par 0.6 (background)")]
    return p


def lighting_plan():
    A = dna2.make("lit:A", "young_woman", {"wardrobe.accessories": [], "wardrobe.top": "jacket"})
    chars = {"A": dict(name="A", dna=A, facing=1, origin=[520.0, BW.FLOOR_Y], view="three_quarter", hand_set="full", start="stand")}
    cam = lambda t, s, m, **k: dict(target=t, size=s, move=m, **k)
    L = lambda **k: dict(k)
    shots = _shots([(0.0, 3.5, cam("A.full", "full", "hold"), dict(purpose="daylight", lighting=L(mood="bright", ambient=(0.72, 0.70, 0.66), moon=0.0, phone=0.0, sun=0.9))),
                    (3.5, 7.0, cam("A.full", "full", "hold"), dict(purpose="dusk", lighting=L(mood="neutral", ambient=(0.36, 0.34, 0.42), moon=0.5, phone=0.0, sun=0.25))),
                    (7.0, 10.5, cam("A.full", "full", "hold"), dict(purpose="night", lighting=L(mood="dim", moon=1.0, phone=0.0))),
                    (10.5, 14.5, cam("A.head", "medium", "hold"), dict(purpose="phone light on the face", lighting=L(mood="dim", moon=0.8, phone=1.0))),
                    (14.5, 18.5, cam("A.full", "full", "hold"), dict(purpose="lamp + hall light", lighting=L(mood="relief", moon=0.6, phone=0.0, hall=1.0, lamp=1.0)))])
    acts = [dict(char="A", action="idle", t=0.0, dur=18.5), dict(char="A", action="grab", t=10.2, dur=0.1, prop="phone"),
            dict(char="A", action="hold_phone", t=10.4, dur=0.9, pos="chest", emotion="neutral", intensity=0.5), dict(char="A", action="read_phone", t=11.4, dur=3.0, emotion="nervous", intensity=0.5),
            dict(char="A", action="release", t=14.2, dur=0.5, prop="phone")]
    _attach(shots, acts)
    p = _base("lighting_test", 18.5, dict(family="bedroom_wide", variation=dict(palette=2), seed=6), chars, shots, dict(PHONE=list(BW.PHONE_POS), LAMP=[600.0, 1110.0]), lamp_on=14.9, hall_on=14.7)
    names = [(0.0, 3.5, "1 DAYLIGHT"), (3.5, 7.0, "2 DUSK"), (7.0, 10.5, "3 NIGHT (moon rim light, contact shadow)"), (10.5, 14.5, "4 PHONE LIGHT ON THE FACE"), (14.5, 18.5, "5 LAMP + HALLWAY LIGHT")]
    p["overlays"] = [dict(t0=a, t1=b, x=14, y=14, size=30, w=1050, text="lighting_test · " + n) for a, b, n in names]
    return p


def run(kind, log=print, samples=8):
    plan = dict(interaction=interaction_plan, parallax=parallax_plan, lighting=lighting_plan, contact=contact_plan)[kind]()
    name = plan["name"]
    out_dir = os.path.join(OUT, "work_" + name)
    os.makedirs(out_dir, exist_ok=True)
    json.dump(plan, open(os.path.join(out_dir, "plan.json"), "w"), ensure_ascii=False, indent=1)
    res = SH.render_film(plan, out_dir, log, samples=samples, qc=None, final_name=name + ".mp4")
    import shutil
    shutil.copy(os.path.join(out_dir, name + ".mp4"), os.path.join(OUT, name + ".mp4"))
    return os.path.join(OUT, name + ".mp4"), out_dir
