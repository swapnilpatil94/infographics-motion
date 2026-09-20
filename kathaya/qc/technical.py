"""KATHAYA TECHNICAL QC: deterministic checks on the plan and on the rendered film, layered on the engine's measured gates (`engine.skeleton.qc_v4`, which stays in force). Creative quality is judged elsewhere."""
import json
import os
import subprocess


def _probe(mp4):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,r_frame_rate,nb_frames,duration", "-of", "json", mp4], capture_output=True, text=True)
    st = json.loads(r.stdout or "{}").get("streams", [])
    v = next((s for s in st if s.get("codec_type") == "video"), {})
    a = next((s for s in st if s.get("codec_type") == "audio"), None)
    num, den = (v.get("r_frame_rate") or "0/1").split("/")
    return dict(width=v.get("width"), height=v.get("height"), fps=round(float(num) / max(float(den), 1), 2), frames=int(v.get("nb_frames") or 0), has_audio=a is not None, audio_duration=float(a.get("duration") or 0) if a else 0.0,
                video_duration=float(v.get("duration") or 0))


def plan_checks(plan, report, timeline, catalog_ids):
    c = []

    def add(i, name, ok, ev=None):
        c.append(dict(id=i, name=name, ok=bool(ok), evidence=ev))
    add("missing_assets", "no missing or unsupported assets", not report["requests"], [r["id"] for r in report["requests"]])
    add("missing_characters", "every cast member has a character asset", all(x["status"] in ("AVAILABLE", "SUBSTITUTED") for x in plan["cast"]), [x["id"] for x in plan["cast"] if x["status"] not in ("AVAILABLE", "SUBSTITUTED")])
    add("valid_capabilities", "every action / camera / effect / transition is a renderer capability", not report["capability_errors"], [e["message"] for e in report["capability_errors"]][:6])
    ids = {n["id"] for n in timeline["narration"]}
    cast = {x["id"] for x in plan["cast"]}
    broken = []
    for v in plan["visuals"]:
        if v["narration_id"] not in ids:
            broken.append(f"{v['id']}: unknown narration {v['narration_id']}")
        if v["environment"].get("asset_id") not in catalog_ids:
            broken.append(f"{v['id']}: environment asset {v['environment'].get('asset_id')}")
        broken += [f"{v['id']}: prop asset {p.get('asset_id')}" for p in v.get("props", []) if p.get("asset_id") not in catalog_ids]
        broken += [f"{v['id']}: cast {x}" for x in v.get("characters", []) if x not in cast]
    add("broken_references", "every reference (narration, environment, prop, character) resolves", not broken, broken[:6])
    covered = {v["narration_id"] for v in plan["visuals"]}
    contiguous = all(abs(a["end"] - b["start"]) < 1e-3 for a, b in zip(plan["visuals"], plan["visuals"][1:])) and plan["visuals"][0]["start"] == 0.0 and abs(plan["visuals"][-1]["end"] - timeline["duration"]) < 0.01
    add("narration_coverage", "every narration segment is shown and the visuals tile the timeline", covered == ids and contiguous, dict(uncovered=sorted(ids - covered), contiguous=contiguous))
    seg = {n["id"]: n for n in timeline["narration"]}
    first = {}
    for v in plan["visuals"]:
        first.setdefault(v["narration_id"], v)
    drift = {k: round(v["start"] - seg[k]["start"], 2) for k, v in first.items() if k in seg and k != plan["visuals"][0]["narration_id"] and abs(v["start"] - seg[k]["start"]) > 0.15}
    add("visual_narration_sync", "each visual begins when its narration begins (<= 0.15 s)", not drift, drift)
    return c


def film_checks(mp4, plan, timeline, engine_qc, fmt="short", w=1080, h=1920, fps=30):
    c = []

    def add(i, name, ok, ev=None):
        c.append(dict(id=i, name=name, ok=bool(ok), evidence=ev))

    def gate(prefix):
        return next((v for k, v in engine_qc["checks"].items() if k.startswith(prefix)), None)
    pr = _probe(mp4) if os.path.exists(mp4) else {}
    add("render_completion", "the film was rendered and decodes cleanly", os.path.exists(mp4) and os.path.getsize(mp4) > 0 and gate("video_decodes_cleanly") is not False, dict(bytes=os.path.getsize(mp4) if os.path.exists(mp4) else 0))
    exp = int(round(plan["duration"] * fps))
    add("frame_generation", "the frame count matches the plan (and no rendered frame is missing)", abs(pr.get("frames", 0) - exp) <= 1 and gate("no_missing_rendered_frames") is not False, dict(frames=pr.get("frames"), expected=exp))
    add("output_dimensions", f"the output is {w}x{h}", (pr.get("width"), pr.get("height")) == (w, h), (pr.get("width"), pr.get("height")))
    add("fps", f"the frame rate is {fps}", abs(pr.get("fps", 0) - fps) < 0.01, pr.get("fps"))
    add("audio_present", "the final file has an audio track", pr.get("has_audio"), pr.get("audio_duration"))
    add("audio_duration_match", "audio duration matches the video", gate("audio_duration_matches_video") is not False and abs(pr.get("audio_duration", 0) - pr.get("video_duration", 0)) < 0.5, dict(audio=pr.get("audio_duration"), video=pr.get("video_duration")))
    add("black_or_dead_frames", "no black or frozen frames", gate("no_dead_frames") is not False, engine_qc["evidence"].get("dead_frames"))
    add("duplicate_frames", "no duplicate consecutive shots / slideshow", gate("no_duplicate_consecutive_shots") is not False and gate("no_slideshow") is not False, engine_qc["evidence"].get("duplicate_shots"))
    add("narration_synchronization", "narration is aligned and every segment is audible", gate("narration_aligned") is not False and gate("every_narration_segment_is_audible") is not False, engine_qc["evidence"].get("narration"))
    return c


def summarize(checks, engine_qc):
    bad = [c["id"] for c in checks if not c["ok"]]
    eng = [k for k, v in engine_qc["checks"].items() if not v]
    return dict(technical_passed=not bad, technical_failed=bad, engine_passed=engine_qc["passed"], engine_failed=eng, n_technical=len(checks), n_engine=engine_qc["n_checks"], checks=checks)
