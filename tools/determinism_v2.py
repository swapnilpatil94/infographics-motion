"""Determinism comparison of Skeleton Factory V2 runs.  usage: determinism_v2.py <labelA=dirA> <labelB=dirB> [<labelC=dirC>] -> output/tests/determinism_v2.json

Per run: plan hash, deterministic-manifest hash (timings stripped), Blender frame count + per-frame pixel hashes, decoded video frame count + per-frame md5 (ffmpeg framemd5), decoded audio md5,
QC verdicts.  Every run is compared to the first."""
import hashlib
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TIMING_KEYS = {"render_seconds", "stages", "performance", "seconds", "sha256_plan"}          # sha256_plan hashes a plan that contains the out-dir path; the normalised plan hash covers it


def strip(o):
    if isinstance(o, dict):
        return {k: strip(v) for k, v in o.items() if k not in TIMING_KEYS}
    if isinstance(o, list):
        return [strip(v) for v in o]
    return o


def sha(b):
    return hashlib.sha256(b).hexdigest()


def summarize(d, all_rels):
    out = {}
    rel = os.path.relpath(d, ROOT)                                                   # the only legitimate difference between runs is the output directory NAME inside paths (a from-plan run keeps the original audio path)
    norm = lambda text: __import__("re").sub("|".join(sorted((__import__("re").escape(r) for r in all_rels), key=len, reverse=True)), "<OUT>", text)
    raw_plan = open(os.path.join(d, "plan.json"), "rb").read()
    out["plan_sha256_raw_bytes"] = sha(raw_plan)
    out["plan_sha256"] = sha(norm(raw_plan.decode("utf-8")).encode("utf-8"))
    man = json.load(open(os.path.join(d, "manifest.json")))
    out["manifest_core_sha256"] = sha(norm(json.dumps(strip(man), sort_keys=True, ensure_ascii=False, default=str)).encode())
    af = os.path.join(d, "work", "actor_frames")
    files = sorted(f for f in os.listdir(af) if f.endswith(".png"))
    px = [hashlib.sha256(np.asarray(Image.open(os.path.join(af, f)).convert("RGBA")).tobytes()).hexdigest() for f in files]
    out["blender_frames"] = len(files)
    out["blender_frames_pixel_sha256"] = sha("".join(px).encode())
    out["blender_frames_file_sha256"] = sha("".join(sha(open(os.path.join(af, f), "rb").read()) for f in files).encode())
    mp4 = os.path.join(d, "final.mp4")
    fm = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", mp4, "-map", "0:v", "-f", "framemd5", "-"], capture_output=True, text=True).stdout
    lines = [ln.split(",")[-1].strip() for ln in fm.splitlines() if ln and not ln.startswith("#")]
    out["video_frames"] = len(lines)
    out["video_frames_md5_sha256"] = sha("".join(lines).encode())
    am = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", mp4, "-map", "0:a", "-f", "md5", "-"], capture_output=True, text=True).stdout.strip()
    out["audio_decoded_md5"] = am
    out["mp4_file_sha256"] = sha(open(mp4, "rb").read())
    qc = json.load(open(os.path.join(d, "qc_report.json")))
    out["qc_passed"] = qc["passed"]
    out["qc_failed_checks"] = [k for k, v in qc["checks"].items() if not v]
    out["_video_frame_md5"] = lines
    return out


def main(args):
    runs = {}
    pairs = [a.split("=", 1) for a in args]
    all_rels = [os.path.relpath(os.path.abspath(p), ROOT) for _, p in pairs]
    for label, path in pairs:
        runs[label] = summarize(os.path.abspath(path), all_rels)
    labels = list(runs)
    base = labels[0]
    keys = ["plan_sha256", "plan_sha256_raw_bytes", "manifest_core_sha256", "blender_frames", "blender_frames_pixel_sha256", "blender_frames_file_sha256", "video_frames", "video_frames_md5_sha256", "audio_decoded_md5", "mp4_file_sha256"]
    cmp = {}
    for lb in labels[1:]:
        cmp[f"{base}_vs_{lb}"] = {k: runs[base][k] == runs[lb][k] for k in keys}
        diff = [i for i, (x, y) in enumerate(zip(runs[base]["_video_frame_md5"], runs[lb]["_video_frame_md5"])) if x != y]
        cmp[f"{base}_vs_{lb}"]["differing_video_frames"] = len(diff)
        cmp[f"{base}_vs_{lb}"]["first_differing_video_frames"] = diff[:10]
    for r in runs.values():
        r.pop("_video_frame_md5")
    res = dict(runs=runs, comparisons=cmp)
    json.dump(res, open(os.path.join(ROOT, "output/tests", os.environ.get("DET_OUT", "determinism_v2.json")), "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
