"""Factory V2 entry: narration beats -> (Chatterbox voice, cached) -> pacing -> plan.json -> Blender rig -> 2.5D film + QC.

    python3 studio.py --skeleton-short-v2 [--out-dir DIR] [--tempo 1.08]
    python3 studio.py --from-plan output/shorts/skeleton_factory_v2/plan.json          # deterministic: no LLM, no TTS
"""
import hashlib
import json
import os
import resource
import shutil
import subprocess
import time

from engine.shorts.raster import ROOT
from engine.skeleton import pace, parts_art2 as PA2, short, short_director_v2 as SD2

OUT = os.path.join(ROOT, "output/shorts/skeleton_factory_v2")
BEATS = os.path.join(ROOT, "narration/skeleton_v2/beats.json")


def _beats():
    return [(b["id"], b["text"]) for b in json.load(open(BEATS, encoding="utf-8"))]


def voice(log=print):
    """Chatterbox Hindi per beat + whisperx alignment; cached under narration/skeleton_v2/ by script hash."""
    raw, seg = os.path.join(ROOT, "narration/skeleton_v2/raw.wav"), os.path.join(ROOT, "narration/skeleton_v2/raw.wav.segments.json")
    stamp = os.path.join(ROOT, "narration/skeleton_v2/raw.hash")
    h = hashlib.sha1(json.dumps(_beats(), ensure_ascii=False).encode()).hexdigest()[:12]
    if not (os.path.exists(raw) and os.path.exists(stamp) and open(stamp).read() == h):
        log("[tts] Chatterbox Hindi (per beat) ...")
        subprocess.run([os.path.join(ROOT, ".venv/bin/python"), os.path.join(ROOT, "tools/tts_beats.py"), BEATS, os.path.join(ROOT, "narration/skeleton_v2/raw")], check=True, cwd=ROOT,
                       env=dict(os.environ, PYTHONPATH=ROOT))
        open(stamp, "w").write(h)
    return raw, seg


def make(out_dir=None, tempo=1.08, seed=11, log=print, samples=10):
    out_dir = out_dir or OUT
    os.makedirs(os.path.join(out_dir, "narration"), exist_ok=True)
    t0 = time.time()
    raw, seg = voice(log)
    pw, pj = os.path.join(out_dir, "narration/paced.wav"), os.path.join(out_dir, "narration/paced.json")
    d = pace.build(raw, seg, _beats(), pw, pj, tempo=tempo)
    nar = dict(segments=[dict(id=s["beat_id"], text=s["text"], start=s["start_seconds"], end=s["end_seconds"], words=s["words"]) for s in d["segments"]], audio=os.path.relpath(pw, ROOT), tts="chatterbox", tempo=tempo)
    plan = SD2.build_plan(nar, seed=seed, tts="chatterbox")
    plan["narration"]["pacing"] = {k: d[k] for k in ("raw_duration", "raw_words_per_s", "paced_words_per_s", "gap_cap", "beat_gap", "tempo")}
    t_plan = time.time() - t0
    t1 = time.time()
    for cid in plan["cast_in_short"]:                                # asset generation (part textures; cached after the first run)
        c = plan["characters"][cid]
        PA2.bake2(c["dna"], c.get("view", "profile"), c.get("hand_set", "full"))
    t_assets = time.time() - t1
    res = short.render_film(plan, out_dir, log, samples=samples)
    _perf(out_dir, t_plan, t_assets, time.time() - t0)
    return res


def _perf(out_dir, t_plan, t_assets, t_total):
    p = os.path.join(out_dir, "manifest.json")
    m = json.load(open(p))
    ru_s, ru_c = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    m["performance"] = dict(planning_s=round(t_plan, 1), asset_generation_s=round(t_assets, 1), blender_build_and_render_s=m["stages"].get("rig+motion+blender"), blender_render_only_s=m["blender"]["render_seconds"],
                            compositing_encode_s=m["stages"].get("composite+encode"), total_s=round(t_total, 1), peak_ram_python_mb=round(ru_s / 1e6), peak_ram_largest_child_mb=round(ru_c / 1e6),
                            output_mb=round(os.path.getsize(os.path.join(out_dir, "final.mp4")) / 1e6, 1))
    json.dump(m, open(p, "w"), ensure_ascii=False, indent=1)


def from_plan(path, log=print, samples=10):
    plan = json.load(open(path, encoding="utf-8"))
    out_dir = os.path.dirname(os.path.abspath(path))
    t = time.time()
    res = short.render_film(plan, out_dir, log, samples=samples)
    _perf(out_dir, 0.0, 0.0, time.time() - t)
    return res
