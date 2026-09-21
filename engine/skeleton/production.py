"""PRODUCTION DRIVER: story (+ notes) + narration segments JSON  ->  finished Short. No manual Blender work, no LLM required (the parser is deterministic; an LLM may only refine the story graph when asked).

    make(story_md, narration_json, out_dir)  parse -> characters/locations/props/acts -> plan (v4) -> critic loop (measured framing, cached stills) -> Blender rig render (frame-cached) -> Audio Director
                                              -> composite + encode -> QC v4 -> auto-fix + re-render (only changed frames) until the gates pass
    from_plan(plan_json, out_dir)             deterministic re-render of a saved plan.json - no parser, no LLM, no network
    Unsupported stories raise `story_semantics.StoryNotSupported` with the reason (nothing is silently faked).
"""
import hashlib
import json
import os
import time

from engine.shorts.raster import ROOT
from engine.skeleton import critic as CR, director_opts as DO, events as EVT, narration_io as NI, qc_v4, scene_director as SD, short, story_semantics as SS, topic_build as TB

MAX_QC_ROUNDS = 3


def _sha(o):
    return hashlib.sha1(json.dumps(o, sort_keys=True, ensure_ascii=False, default=list).encode()).hexdigest()[:12]


def parse(story_md, narration_json, use_llm=False):
    """-> (story graph, narration dict). Raises StoryNotSupported / NarrationInvalid with the reason."""
    notes = SS.load_script(story_md) if story_md and os.path.exists(story_md) else {}
    nar = NI.load(narration_json)
    graph = SS.analyze(nar["segments"], notes, use_llm=use_llm)
    graph.setdefault("fixes", {})
    return graph, nar


def build(graph, nar, **k):
    """scene director + the user's optional director options (none = the plan the CLI builds)"""
    plan = DO.apply(SD.build_plan(graph, nar, **k), graph.get("director"), graph.get("dna_patch"))
    if graph.get("narration_segments"):                                                   # Kathaya plans: captions / QC follow the real narration segments, the shots follow the visuals
        plan["narration"]["segments"] = graph["narration_segments"]
    plan.update(graph.get("plan_overrides") or {})
    if plan.get("look"):                                                                  # Kathaya finishing layer: its punches get their sounds
        from kathaya.renderer import look as LK
        plan["sfx"] = sorted(list(plan.get("sfx") or []) + LK.sfx(plan), key=lambda s: s["t"])
    return plan


def plan_for(graph, nar, seed=11, fixes=None):
    plan = build(graph, nar, seed=seed, name=graph["slug"], tts=nar.get("tts", "provided"), fixes=fixes if fixes is not None else graph.get("fixes"))
    TB.bake_cast(plan)
    return plan


def make(story_md, narration_json, out_dir=None, seed=11, samples=10, critique_rounds=2, use_llm=False, use_vlm=False, log=print, qc_rounds=MAX_QC_ROUNDS, graph=None):
    """graph: an already approved story graph (the Studio UI's reviewed / edited graph); its beat ids must match the narration segment ids"""
    t_all = time.time()
    EV = EVT.current()
    EV.start("scene_direction", message="casting, blocking, camera and lighting for every shot")
    if graph is not None:
        nar = NI.load(narration_json)
        miss = [b["id"] for b in graph["beats"] if b["id"] not in {s["id"] for s in nar["segments"]}]
        if miss:
            raise SS.StoryNotSupported(f"the approved story has beats {miss} that the narration does not cover")
        graph.setdefault("fixes", {})
    else:
        graph, nar = parse(story_md, narration_json, use_llm)
    out_dir = out_dir or os.path.join(ROOT, "output/production", graph["slug"])
    os.makedirs(out_dir, exist_ok=True)
    json.dump(graph, open(os.path.join(out_dir, "story_graph.json"), "w"), ensure_ascii=False, indent=1)
    log(f"[production] '{graph['title']}'  {len(graph['beats'])} beats  scenes={[(s['loc'], s['time']) for s in graph['scenes']]}  cast={graph['cast']['protagonist']['archetype']} + {[e['role'] for e in ([graph['cast']['principal']] if graph['cast']['principal'] else []) + graph['cast']['extras']]}")
    fixes = dict(graph.get("fixes", {}))
    plan = plan_for(graph, nar, seed, fixes)
    log(f"[production] plan v{plan['version']}: {len(plan['shots'])} shots, {plan['duration']}s, acts={plan['acts']}")
    crit = CR.improve(plan, graph, nar, out_dir, rounds=critique_rounds, log=log, samples=max(4, samples // 2), seed=seed, use_vlm=use_vlm, builder=build) if critique_rounds else dict(plan=plan, fixes=fixes, summary=None)
    plan, fixes = crit["plan"], crit["fixes"]
    graph["fixes"] = fixes
    EV.complete("scene_direction", message=f"{len(plan['shots'])} shots, {len(plan['scenes'])} scenes, {len(plan['cast_in_short'])} characters", shots=len(plan["shots"]), scenes=len(plan["scenes"]), characters=len(plan["cast_in_short"]),
                critic_after=(crit["summary"] or {}).get("after"))
    history = []
    for r in range(qc_rounds + 1):
        TB.bake_cast(plan)
        mp4, qc = short.render_film(plan, out_dir, log, samples=samples)
        fails = [k for k, v in qc["checks"].items() if not v]
        history.append(dict(round=r, passed=qc["passed"], failed=fails, frame_cache=qc["evidence"].get("frame_cache"), fixes_applied=[]))
        log(f"[production] QC round {r}: {'PASS' if qc['passed'] else 'FAIL'} ({qc['n_checks'] - len(fails)}/{qc['n_checks']})  failed={fails}")
        if qc["passed"] or r == qc_rounds:
            break
        audio_cfg = dict(fixes.get("_audio", {}))
        done = qc_v4.autofix(qc, fixes, plan, audio_cfg)
        if audio_cfg:
            fixes["_audio"] = audio_cfg
        history[-1]["fixes_applied"] = done
        EV.emit("qc_fix", "qc", message=f"{len(done)} automatic fix(es) after QC round {r}", fixes=done, failed_checks=fails)
        if not [d for d in done if not d.startswith("framing: handled")]:
            log("[production] no automatic fix available for the failed gates")
            break
        plan = plan_for(graph, nar, seed, fixes)
        EV.new_pass(r + 1, done)
    graph["fixes"] = fixes
    json.dump(graph, open(os.path.join(out_dir, "story_graph.json"), "w"), ensure_ascii=False, indent=1)
    man = json.load(open(os.path.join(out_dir, "manifest.json")))
    man["production"] = dict(story=os.path.relpath(story_md, ROOT) if story_md else None, narration=os.path.relpath(narration_json, ROOT), total_s=round(time.time() - t_all, 1), qc_rounds=history,
                             critique=crit["summary"] and dict(before=crit["summary"]["before"], after=crit["summary"]["after"]), fixes=fixes, plan_sha=_sha(plan),
                             commands=dict(rerender=f"python3 studio.py --from-plan {os.path.relpath(os.path.join(out_dir, 'plan.json'), ROOT)}"))
    json.dump(man, open(os.path.join(out_dir, "manifest.json"), "w"), ensure_ascii=False, indent=1, default=list)
    return dict(out_dir=out_dir, mp4=mp4, qc=qc, plan=plan, graph=graph, history=history, seconds=round(time.time() - t_all, 1))


def from_plan(plan_json, out_dir=None, samples=10, log=print):
    """deterministic re-render of a saved plan: no parser, no LLM"""
    plan = json.load(open(plan_json, encoding="utf-8"))
    TB.bake_cast(plan)
    return short.render_film(plan, out_dir or os.path.dirname(os.path.abspath(plan_json)), log, samples=samples)
