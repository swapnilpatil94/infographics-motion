"""BACKEND INTERFACES for a future web UI. Every function takes and returns plain JSON-able data (paths are project-relative); the CLI (`studio.py --production ...`) is built on the same functions.

  Story        story_analyze(text_or_path, narration_json)          -> story graph (characters, relationships, locations, props, acts, emotions, psychology motifs)  | raises StoryNotSupported
               story_edit(graph, beat_id, **changes)                -> graph with one beat changed (act / loc / time / emotion / text), re-validated
  Narration    narration_validate(path) / narration_synthesize(lines, out_dir)   (Chatterbox Hindi, cached) / narration_from_audio ready: any voice that supplies start/end per segment
  Characters   characters(graph) / character_catalog() / character_override(plan, cid, dna_patch)
  Assets       assets()                                             -> the licensed asset registry summary (only ACCEPTed assets are usable)
  Environment  environments()                                       -> supported locations, allowed times of day, stage layouts
  Voice/Style  voices() / styles()
  Generate     generate(request)                                    -> {plan_path, film_path, qc}   request = {"story_md","narration_json","out_dir"?, "style"?, "seed"?}
  Preview      preview_shot(plan, shot_id, out_dir)                 -> png (renders only that shot's mid frame; frame cache makes repeats free)
  Edit shot    edit_shot(plan, shot_id, camera=..., lighting=..., environment=...) -> new plan (only that shot's frames re-render)
  Final render render_final(plan_path)                              -> deterministic re-render, no LLM
  QC           qc_report(out_dir)                                   -> gates, evidence, failures
"""
import copy
import json
import os

from engine.environments import locations as LOC
from engine.shorts.raster import ROOT
from engine.skeleton import lab_dna as LD, narration_io as NI, production as PR, short, story_semantics as SS


def _rel(p):
    return os.path.relpath(p, ROOT) if os.path.isabs(p) else p


# ------------------------------------------------------------------------------------------------ story
def story_analyze(text_or_path, narration_json=None, notes=None, use_llm=False):
    if narration_json:
        graph, _ = PR.parse(text_or_path if text_or_path and os.path.exists(text_or_path) else None, narration_json, use_llm)
        return graph
    lines = [l.strip() for l in (open(text_or_path, encoding="utf-8").read() if os.path.exists(text_or_path) else text_or_path).splitlines() if l.strip() and not l.startswith("#")]
    return SS.analyze([dict(id=f"n{i + 1:02d}", text=l) for i, l in enumerate(lines)], notes or {}, use_llm)


def story_edit(graph, beat_id, **changes):
    beats = [dict(b) for b in graph["beats"]]
    for b in beats:
        if b["id"] == beat_id:
            b.update({k: v for k, v in changes.items() if k in ("act", "loc", "time", "emotion", "text", "props", "roles", "subject")})
    return SS.graph_from_beats(graph["title"], beats, graph["cast"]["protagonist"], (graph["cast"]["principal"] or {}).get("role"), [e["role"] for e in graph["cast"]["extras"]], graph["slug"], graph.get("notes"))


# ------------------------------------------------------------------------------------------------ narration
def narration_validate(path):
    n = NI.load(path)
    return dict(ok=True, segments=len(n["segments"]), duration=n["segments"][-1]["end"], audio=n["audio"], tts=n["tts"])


def narration_synthesize(lines, out_dir, tempo=1.08):
    return NI.synthesize([(f"n{i + 1:02d}", t) for i, t in enumerate(lines)], out_dir, tempo=tempo)


# ------------------------------------------------------------------------------------------------ characters / assets / environments / voices / styles
def character_catalog():
    return dict(archetypes=sorted(LD.ARCHETYPES), roles=sorted({r[1] for r in SS.ROLES}))


def characters(graph):
    c = graph["cast"]
    out = [dict(id="A", role="protagonist", **c["protagonist"])]
    if c.get("principal"):
        out.append(dict(id="D", role=c["principal"]["role"], archetype=c["principal"]["archetype"], gender=c["principal"]["gender"]))
    out += [dict(id=f"X{k}", role=e["role"], archetype=e["archetype"], gender=e["gender"]) for k, e in enumerate(c["extras"], 1)]
    return out


def character_override(plan, cid, dna_patch):
    """patch a character's DNA fields (skin, hair, wardrobe...) -> new plan; only that character's frames re-render"""
    from engine.skeleton import director_opts as DO
    return DO.patch_dna(copy.deepcopy(plan), cid, dna_patch)


def assets():
    reg = json.load(open(os.path.join(ROOT, "assets/registry/asset_registry.json")))
    return [dict(id=a["asset_id"], status=a["status"], policy=a["policy_decision"], sha256=a["sha256"][:12]) for a in reg["assets"] if a["status"] == "USED"]


def environments():
    return {n: dict(family=f, times=list(t), default=d, layout=lay) for n, (f, t, d, lay, _) in LOC.LOCATIONS.items()}


def voices():
    return [dict(id="chatterbox_hindi", kind="tts", cached=True, note="Chatterbox multilingual (Hindi); content-hash cached"), dict(id="provided", kind="segments_json", note="any voice: supply segments with start/end and an audio file")]


def styles():
    from engine.skeleton import styles as ST
    return sorted(getattr(ST, "STYLES", {}) or [])


# ------------------------------------------------------------------------------------------------ generate / preview / edit / final / QC
def generate(request, log=print):
    r = PR.make(os.path.join(ROOT, request["story_md"]) if request.get("story_md") else None, os.path.join(ROOT, request["narration_json"]), out_dir=request.get("out_dir"), seed=request.get("seed", 11),
                samples=request.get("samples", 10), critique_rounds=request.get("critique_rounds", 1), log=log)
    return dict(plan_path=_rel(os.path.join(r["out_dir"], "plan.json")), film_path=_rel(r["mp4"]), qc=dict(passed=r["qc"]["passed"], failed=[k for k, v in r["qc"]["checks"].items() if not v]), seconds=r["seconds"])


def preview_shot(plan, shot_id, out_dir, samples=6):
    sh = next(s for s in plan["shots"] if s["id"] == shot_id)
    t = round((sh["t0"] + sh["t1"]) / 2, 2)
    return short.render_stills(plan, out_dir, [t], samples=samples)["paths"][0]


def edit_shot(plan, shot_id, camera=None, lighting=None, environment=None):
    p = copy.deepcopy(plan)
    sh = next(s for s in p["shots"] if s["id"] == shot_id)
    if camera:
        sh["camera"] = {**sh.get("camera", {}), **camera}
    if lighting:
        sh["lighting"] = {**sh["lighting"], **lighting}
    if environment:
        sh["environment"] = {**(sh.get("environment") or p["environment"]), **environment}
    return p


def render_final(plan_path, log=print):
    return PR.from_plan(os.path.join(ROOT, plan_path) if not os.path.isabs(plan_path) else plan_path, log=log)


def qc_report(out_dir):
    q = json.load(open(os.path.join(ROOT, out_dir, "qc_report.json")))
    return dict(passed=q["passed"], n_checks=q["n_checks"], failed=[k for k, v in q["checks"].items() if not v], evidence=q["evidence"])
