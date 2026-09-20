"""TEST MATRIX: exercises the RUNTIME (plan -> rig motion -> Blender stills), not contact sheets of assets. 24 situations across 12 protagonists / 12+ partners, 9 locations, day + night, 1-person / 2-person / crowd,
phone / card / money / document / laptop / cup props, walking, sitting, standing, talking, looking, reaching, giving / receiving, fear, suspicion, realisation.

Each SCENARIO is a structured story graph (story_semantics.graph_from_beats) -> scene_director plan -> rig motion (build_actors) -> measured checks (hand-object contact, IK, snapping, ghost actors, framing)
-> Blender stills of every beat.  Output: output/production/matrix/{sheet_*.png, matrix.json}  and docs/production/matrix.json.
    python tools/production/matrix.py [--no-render]
"""
import json
import os
import sys
import time

import numpy as np
from PIL import Image, ImageDraw

from engine.skeleton import scene_director as SD, short, story_semantics as SS, topic_build as TB, qc_v4
from engine.skeleton.narration_io import NarrationInvalid  # noqa: F401

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "output/production/matrix")


def B(act, loc, time="day", emotion="neutral", props=(), roles=(), subject="protagonist", data=None):
    return dict(act=act, loc=loc, time=time, emotion=emotion, props=list(props), roles=list(roles), subject=subject, data=data or {})


# (name, protagonist, principal role, extras, beats) - every scenario is a valid act sequence (first ESTABLISH/ARRIVE ... last RESOLVE)
SCENARIOS = [
    ("s01_bedroom_night_phone", dict(gender="male", archetype="young man"), None, [], [B("ESTABLISH", "bedroom", "night"), B("PHONE_ALERT", "bedroom", "night", "fear"), B("LOOK_AT_PHONE", "bedroom", "night"), B("REACH_PHONE", "bedroom", "night", "confusion"), B("TAKE_PHONE", "bedroom", "night"), B("READ_MESSAGE", "bedroom", "night", "suspicion"), B("REALIZE", "bedroom", "night", "realization"), B("CLOSE_UP", "bedroom", "night", "suspicion"), B("RESOLVE", "bedroom", "night", "relief")]),
    ("s02_study_day_woman", dict(gender="female", archetype="young woman"), None, [], [B("ESTABLISH", "study", "day"), B("PHONE_ALERT", "study", "day", "hope"), B("TAKE_PHONE", "study", "day"), B("READ_MESSAGE", "study", "day", "hope"), B("SUSPECT", "study", "day", "suspicion"), B("STAND_UP", "study", "day", "fear"), B("CLOSE_UP", "study", "day"), B("RESOLVE", "study", "day", "relief")]),
    ("s03_livingroom_mother", dict(gender="male", archetype="student"), "mother", [], [B("ARRIVE", "living_room", "day"), B("PHONE_ALERT", "living_room", "day"), B("TAKE_PHONE", "living_room", "day"), B("READ_MESSAGE", "living_room", "day", "fear"), B("PERSON_ENTERS", "living_room", "day", "suspicion", roles=["mother"]), B("EYE_CONTACT", "living_room", "day", roles=["mother"]), B("OTHER_LOOKS_AT_PHONE", "living_room", "day", "suspicion", roles=["mother"]), B("GIVE_OBJECT", "living_room", "day", props=["phone"], roles=["mother"], data=dict(prop="phone")), B("OTHER_REACTS", "living_room", "day", "fear", roles=["mother"]), B("BOTH_REALIZE", "living_room", "day", "realization", roles=["mother"]), B("RESOLVE", "living_room", "day", "relief", roles=["mother"])]),
    ("s04_bank_giveform", dict(gender="female", archetype="older woman"), "bank_employee", [], [B("ARRIVE", "bank", "day"), B("MEET", "bank", "day", roles=["bank_employee"]), B("CONVERSE", "bank", "day", roles=["bank_employee"]), B("GIVE_OBJECT", "bank", "day", props=["document"], roles=["bank_employee"], data=dict(prop="document")), B("READ_DOCUMENT", "bank", "day", "suspicion", roles=["bank_employee"], subject="partner"), B("OTHER_REACTS", "bank", "day", "fear", roles=["bank_employee"]), B("REALIZE", "bank", "day", "realization"), B("CLOSE_UP", "bank", "day"), B("RESOLVE", "bank", "day", "relief", roles=["bank_employee"])]),
    ("s05_atm_night_stranger", dict(gender="male", archetype="older man"), "stranger", [], [B("ARRIVE", "atm", "night"), B("USE_ATM", "atm", "night", "confusion"), B("PERSON_ENTERS", "atm", "night", "suspicion", roles=["stranger"]), B("CONVERSE", "atm", "night", roles=["stranger"]), B("GIVE_OBJECT", "atm", "night", props=["card"], roles=["stranger"], data=dict(prop="card")), B("RECEIVE_OBJECT", "atm", "night", props=["card"], roles=["stranger"], data=dict(prop="card")), B("REALIZE", "atm", "night", "realization"), B("CLOSE_UP", "atm", "night", "fear"), B("RESOLVE", "atm", "night", "relief")]),
    ("s06_cafe_friend_day", dict(gender="female", archetype="student"), "friend", [], [B("ESTABLISH", "cafe", "day"), B("MEET", "cafe", "day", roles=["friend"]), B("CONVERSE", "cafe", "day", roles=["friend"]), B("PHONE_ALERT", "cafe", "day", "hope"), B("TAKE_PHONE", "cafe", "day"), B("OTHER_LOOKS_AT_PHONE", "cafe", "day", "suspicion", roles=["friend"]), B("GIVE_OBJECT", "cafe", "day", props=["phone"], roles=["friend"], data=dict(prop="phone")), B("OTHER_REACTS", "cafe", "day", "fear", roles=["friend"]), B("BOTH_REALIZE", "cafe", "day", "realization", roles=["friend"]), B("CLOSE_UP", "cafe", "day"), B("RESOLVE", "cafe", "day", "relief", roles=["friend"])]),
    ("s07_cafe_night_walk", dict(gender="male", archetype="office worker"), None, [], [B("ARRIVE", "cafe", "night"), B("SIT_DOWN", "cafe", "night"), B("PHONE_ALERT", "cafe", "night", "fear"), B("TAKE_PHONE", "cafe", "night"), B("READ_MESSAGE", "cafe", "night", "suspicion"), B("STAND_UP", "cafe", "night", "fear"), B("WALK_ACROSS", "cafe", "night", "fear"), B("CLOSE_UP", "cafe", "night"), B("RESOLVE", "cafe", "night", "relief")]),
    ("s08_street_crowd_dusk", dict(gender="female", archetype="middle-aged woman"), None, [], [B("ARRIVE", "street", "dusk"), B("CROWD_WATCH", "street", "dusk"), B("OBSERVE", "street", "dusk", "hope"), B("PHONE_ALERT", "street", "dusk"), B("TAKE_PHONE", "street", "dusk"), B("READ_MESSAGE", "street", "dusk", "suspicion"), B("RUN_AWAY", "street", "dusk", "fear"), B("CLOSE_UP", "street", "dusk"), B("RESOLVE", "street", "dusk", "relief")]),
    ("s09_office_laptop", dict(gender="male", archetype="office worker"), "boss", [], [B("ARRIVE", "office", "day"), B("SIT_DOWN", "office", "day"), B("TYPE_LAPTOP", "office", "day", props=["laptop"]), B("PHONE_ALERT", "office", "day"), B("TAKE_PHONE", "office", "day"), B("READ_MESSAGE", "office", "day", "fear"), B("MEET", "office", "day", "suspicion", roles=["boss"]), B("CONVERSE", "office", "day", roles=["boss"]), B("BOTH_REALIZE", "office", "day", "realization", roles=["boss"]), B("RESOLVE", "office", "day", "relief", roles=["boss"])]),
    ("s10_classroom_teacher", dict(gender="male", archetype="student"), "teacher", [], [B("ARRIVE", "classroom", "day"), B("SIT_DOWN", "classroom", "day"), B("PHONE_ALERT", "classroom", "day", "hope"), B("TAKE_PHONE", "classroom", "day"), B("READ_MESSAGE", "classroom", "day", "hope"), B("PERSON_ENTERS", "classroom", "day", "suspicion", roles=["teacher"]), B("OTHER_LOOKS_AT_PHONE", "classroom", "day", "suspicion", roles=["teacher"]), B("CONVERSE", "classroom", "day", roles=["teacher"]), B("CLOSE_UP", "classroom", "day"), B("RESOLVE", "classroom", "day", "relief", roles=["teacher"])]),
    ("s11_shop_counter_money", dict(gender="female", archetype="young woman"), "shopkeeper", [], [B("ARRIVE", "shop", "day"), B("MEET", "shop", "day", roles=["shopkeeper"]), B("COUNT_MONEY", "shop", "day", "suspicion", props=["money"]), B("GIVE_OBJECT", "shop", "day", props=["money"], roles=["shopkeeper"], data=dict(prop="money")), B("OTHER_REACTS", "shop", "day", "fear", roles=["shopkeeper"]), B("SUSPECT", "shop", "day", "suspicion"), B("REALIZE", "shop", "day", "realization"), B("CLOSE_UP", "shop", "day"), B("RESOLVE", "shop", "day", "relief", roles=["shopkeeper"])]),
    ("s12_police_report", dict(gender="male", archetype="middle-aged man"), "police_officer", [], [B("ARRIVE", "police", "day", "fear"), B("MEET", "police", "day", roles=["police_officer"]), B("CONVERSE", "police", "day", "fear", roles=["police_officer"]), B("RECEIVE_OBJECT", "police", "day", props=["document"], roles=["police_officer"], data=dict(prop="document")), B("READ_DOCUMENT", "police", "day", "suspicion", props=["document"]), B("CLOSE_UP", "police", "day", "hope"), B("RESOLVE", "police", "day", "relief", roles=["police_officer"])]),
    ("s13_callcenter_call", dict(gender="female", archetype="office worker"), "caller", [], [B("ARRIVE", "call_center", "day"), B("PHONE_ALERT", "call_center", "day"), B("PHONE_CALL", "call_center", "day", "fear"), B("REALIZE", "call_center", "day", "realization"), B("CLOSE_UP", "call_center", "day", "suspicion"), B("RESOLVE", "call_center", "day", "relief")]),
    ("s14_livingroom_night_grandpa", dict(gender="male", archetype="older man"), "grandmother", [], [B("ARRIVE", "living_room", "night"), B("PHONE_ALERT", "living_room", "night", "fear"), B("TAKE_PHONE", "living_room", "night"), B("READ_MESSAGE", "living_room", "night", "fear"), B("PERSON_ENTERS", "living_room", "night", "suspicion", roles=["grandmother"]), B("CONVERSE", "living_room", "night", roles=["grandmother"]), B("BOTH_REALIZE", "living_room", "night", "realization", roles=["grandmother"]), B("RESOLVE", "living_room", "night", "relief", roles=["grandmother"])]),
    ("s15_study_night_brother", dict(gender="female", archetype="student"), "brother", [], [B("ESTABLISH", "study", "night"), B("TYPE_LAPTOP", "study", "night", props=["laptop"]), B("PHONE_ALERT", "study", "night", "hope"), B("TAKE_PHONE", "study", "night"), B("READ_MESSAGE", "study", "night", "hope"), B("SUSPECT", "study", "night", "suspicion"), B("STAND_UP", "study", "night", "fear"), B("PERSON_ENTERS", "study", "night", roles=["brother"]), B("HAND_OVER", "study", "night", props=["phone"], roles=["brother"]), B("OTHER_REACTS", "study", "night", "fear", roles=["brother"]), B("RESOLVE", "study", "night", "relief", roles=["brother"])]),
    ("s16_bank_atm_two_locations", dict(gender="male", archetype="young man"), "bank_employee", [], [B("ARRIVE", "atm", "day"), B("USE_ATM", "atm", "day", "confusion"), B("PHONE_ALERT", "atm", "day", "fear"), B("TAKE_PHONE", "atm", "day"), B("READ_MESSAGE", "atm", "day", "fear"), B("ARRIVE", "bank", "day", "fear"), B("MEET", "bank", "day", roles=["bank_employee"]), B("CONVERSE", "bank", "day", roles=["bank_employee"]), B("RESOLVE", "bank", "day", "relief", roles=["bank_employee"])]),
]


def _settle(g, nar, name, rounds=3):
    """what the production critic loop does without rendering: measure framing, solve a camera for every shot that fails, re-plan (same fixers as critic.improve)"""
    from engine.skeleton import critic as CR
    fixes, applied = {}, 0
    for r in range(rounds + 1):
        plan = SD.build_plan(g, nar, seed=11, name=name, fixes=fixes)
        TB.bake_cast(plan)
        actors = short.build_actors(plan, log=lambda *a: None)
        cam = short.build_camera(plan, actors)
        geo = CR.measure_geometry(plan, actors, cam)
        bad = [x for x in geo if not x["ok"]]
        if not bad or r == rounds:
            return plan, actors, cam, applied
        for x in bad:
            sh = next(z for z in plan["shots"] if z["id"] == x["shot"])
            sol = CR.solve_camera(sh, actors, cam, plan["fps"], None) or CR.solve_camera(sh, actors, cam, plan["fps"], None, bounds=False)
            sol = sol or CR.size_fallback(sh, [p["kind"] for p in x["problems"]])
            if sol:
                CR._merge(fixes, x["beat"], "camera", sol)
                applied += 1


def _draft(g):
    return TB.draft_narration(g)


def run(render=True, log=print):
    os.makedirs(OUT, exist_ok=True)
    res, sheets = [], []
    protagonists, partners, situations, locs, times, props_used, emotions, acts_used = set(), set(), set(), set(), set(), set(), set(), set()
    crowd = single = two = 0
    for name, pro, principal, extras, beats in SCENARIOS:
        t0 = time.time()
        g = SS.graph_from_beats(name, beats, pro, principal, extras, slug=name)
        nar = _draft(g)
        plan, actors, cam, settled = _settle(g, nar, name)
        # ---- measured runtime checks on the ACTUAL motion (no rendering needed)
        contact = [(cid, e[2]["prop"], r["err"], r["ok"]) for cid, a in actors.items() for e in a.perf.events if e[1] == "prop_cycle" for r in e[2]["recs"]]
        phone_c = [round(qc_v4.qc_v3._phone_centre_error(a, e), 2) for a in actors.values() for e in a.perf.events if e[1] == "phone_contact"]
        clamped = [(cid, round(e[0], 2)) for cid, a in actors.items() for e in a.perf.events if e[1] == "reach_clamped"]
        snaps = []
        fps = plan["fps"]
        tele = {cid: [e[0] for e in a.perf.events if e[1] == "teleport"] for cid, a in actors.items()}
        for cid, a in actors.items():
            for k, v in a.channels.items():
                if not (k.endswith("_rot") or k in ("spine_rot", "chest_rot")) or "pose" in k:
                    continue
                d = np.abs(np.diff(np.array(v, np.float64)))
                for f in np.where(d > qc_v4.SNAP_DEG_PER_FRAME)[0]:
                    t = f / fps
                    if not any(abs(t - tt) < 0.3 for tt in tele[cid]) and short.on_screen(a, t, -200, 1280):
                        snaps.append((cid, k, round(float(t), 2), round(float(d[f]), 1)))
        ghosts = []
        for sc in plan["scenes"]:
            for cid, a in actors.items():
                if cid not in sc["cast"] and any(short.on_screen(a, float(tt), -120, 1200) for tt in np.arange(sc["t0"] + 0.05, sc["t1"] - 0.05, 0.25)):
                    ghosts.append((cid, sc["loc"]))
        from engine.skeleton import critic as CR
        geo = CR.measure_geometry(plan, actors, cam)
        bad_geo = [(x["shot"], [p["kind"] for p in x["problems"]]) for x in geo if not x["ok"]]
        cast = {cid: (c["dna"]["hair"].get("style"), c["dna"]["skin"].get("hex"), c["dna"]["wardrobe"].get("top"), c["dna"]["wardrobe"].get("top_color")) for cid, c in plan["characters"].items()}
        protagonists.add(cast["A"])
        partners |= {v for k, v in cast.items() if k != "A"}
        situations |= {(b["act"], b["loc"], b["time"], b["emotion"]) for b in g["beats"]}
        locs |= {b["loc"] for b in g["beats"]}
        times |= {b["time"] for b in g["beats"]}
        for b in g["beats"]:
            props_used |= set(b["props"])
            acts_used.add(b["act"])
            emotions.add(b["emotion"])
        n_on = max(len([c for c in sc["cast"]]) for sc in plan["scenes"])
        crowd += any(b["act"] == "CROWD_WATCH" for b in g["beats"])
        single += n_on == 1
        two += n_on == 2
        rec = dict(name=name, beats=len(g["beats"]), shots=len(plan["shots"]), duration=plan["duration"], protagonist=pro["archetype"], principal=principal, prop_contacts=len(contact), prop_contact_bad=[c for c in contact if (not c[3]) or c[2] > 6.0],
                   phone_contact_err_px=phone_c, unreachable_events=clamped, snaps=snaps[:6], n_snaps=len(snaps), ghost_actors=ghosts, geometry_bad_shots=bad_geo, plan_seconds=round(time.time() - t0, 1))
        if render:
            times_ = [round(s["t0"] + (s["t1"] - s["t0"]) * 0.55, 2) for s in plan["shots"] if s["treatment"] == "skeleton"]
            R = short.render_stills(plan, os.path.join(OUT, name), times_, log=lambda *a: None, samples=6)
            ims = [Image.open(p).convert("RGB").resize((162, 288)) for p in R["paths"]]
            cols = 10
            rows = (len(ims) + cols - 1) // cols
            sh_ = Image.new("RGB", (cols * 162, rows * 306), (12, 12, 14))
            dr = ImageDraw.Draw(sh_)
            skel = [s for s in plan["shots"] if s["treatment"] == "skeleton"]
            for i, im in enumerate(ims):
                x, y = (i % cols) * 162, (i // cols) * 306
                sh_.paste(im, (x, y + 16))
                dr.text((x + 3, y + 2), f"{skel[i].get('act', '')}", fill=(230, 230, 230))
            p = os.path.join(OUT, f"sheet_{name}.png")
            sh_.save(p)
            sheets.append(p)
            rec["sheet"] = os.path.relpath(p, ROOT)
        res.append(rec)
        log(f"[matrix] {name}: shots={rec['shots']} contacts={rec['prop_contacts']} bad={len(rec['prop_contact_bad'])} snaps={rec['n_snaps']} ghosts={len(ghosts)} geo_bad={len(bad_geo)}")
    summary = dict(scenarios=len(res), distinct_protagonists=len(protagonists), distinct_partners=len(partners), meaningful_situations=len(situations), locations=sorted(locs), times=sorted(times), props=sorted(props_used),
                   emotions=sorted(emotions), acts=sorted(acts_used), single_person_scenarios=single, two_person_scenarios=two, crowd_scenarios=crowd, prop_contacts=sum(r["prop_contacts"] for r in res), prop_contacts_bad=sum(len(r["prop_contact_bad"]) for r in res),
                   unreachable_events=sum(len(r["unreachable_events"]) for r in res), snaps=sum(r["n_snaps"] for r in res), ghost_actor_scenes=sum(len(r["ghost_actors"]) for r in res), geometry_bad_shots=sum(len(r["geometry_bad_shots"]) for r in res))
    out = dict(summary=summary, scenarios=res)
    json.dump(out, open(os.path.join(OUT, "matrix.json"), "w"), ensure_ascii=False, indent=1, default=list)
    os.makedirs(os.path.join(ROOT, "docs/production"), exist_ok=True)
    json.dump(out, open(os.path.join(ROOT, "docs/production/matrix.json"), "w"), ensure_ascii=False, indent=1, default=list)
    return out


if __name__ == "__main__":
    r = run(render="--no-render" not in sys.argv)
    print(json.dumps(r["summary"], ensure_ascii=False, indent=1))
