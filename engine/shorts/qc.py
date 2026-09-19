"""Objective release checks for a rendered Short. Everything here is
measured from the actual MP4 / render stats, not assumed."""
import json
import os
import subprocess

import numpy as np

from engine.shorts import captions


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def probe(path):
    r = _run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height,r_frame_rate,pix_fmt,duration,nb_frames",
              "-show_entries", "format=duration,size,bit_rate", "-of", "json", path])
    return json.loads(r.stdout)


def loudness(path):
    r = _run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "loudnorm=I=-14:TP=-1.5:print_format=json", "-f", "null", "-"])
    txt = r.stderr[r.stderr.rindex("{"):]
    j = json.loads(txt[: txt.rindex("}") + 1])
    return dict(integrated_lufs=float(j["input_i"]), true_peak_db=float(j["input_tp"]), lra=float(j["input_lra"]))


def motion_and_luma(path, shots, fps):
    w, h = 270, 480
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                       capture_output=True)
    arr = np.frombuffer(r.stdout, np.uint8).reshape(-1, h, w).astype(np.float32)
    diffs = np.abs(np.diff(arr, axis=0)).mean(axis=(1, 2))
    luma = arr.mean(axis=(1, 2)) / 255.0
    per_shot = {}
    for sid, t0, t1 in shots:
        i0, i1 = int(t0 * fps), min(int(t1 * fps), len(arr) - 1)
        seg = diffs[i0:max(i1 - 1, i0 + 1)]
        # a cut shows as one huge diff at the boundary; exclude first 2 frames
        seg = seg[2:] if len(seg) > 3 else seg
        per_shot[sid] = dict(mean_luma=float(luma[i0:i1].mean()), mean_motion=float(seg.mean()) if len(seg) else 0.0,
                             max_still_run_s=_longest_still(seg, fps))
    fade = int(0.7 * fps)   # intentional fade-in/out windows are not defects
    interior = luma[fade:len(luma) - fade]
    return dict(frames=len(arr), dark_frames=int((interior < 0.02).sum()), per_shot=per_shot), diffs


def _longest_still(seg, fps, eps=0.06):
    best = run = 0
    for d in seg:
        run = run + 1 if d < eps else 0
        best = max(best, run)
    return best / fps


def run(mp4, show, stats):
    fps = show.fps
    info = probe(mp4)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    dur = float(info["format"]["duration"])
    shots = [(s["id"], t0, t1) for t0, t1, s in show.shots]
    shots[-1] = (shots[-1][0], shots[-1][1], dur)
    mot, _ = motion_and_luma(mp4, shots, fps)
    loud = loudness(mp4)
    caps = [s for s in stats if s["caption"]]
    unsafe = [s["f"] for s in caps if s["bbox"] and not captions.in_safe_zone(s["bbox"])]
    checks = {
        "vertical_9x16_1080x1920": (v["width"], v["height"]) == (1080, 1920),
        "fps_30": v["r_frame_rate"] == "30/1",
        "duration_under_60s": dur < 60,
        "h264_yuv420p": v["codec_name"] == "h264" and v["pix_fmt"] == "yuv420p",
        "has_audio": a is not None,
        "loudness_-16_to_-12_LUFS": -16.5 <= loud["integrated_lufs"] <= -11.5,
        "true_peak_<=-1dB": loud["true_peak_db"] <= -1.0,
        "no_dead_frames": mot["dark_frames"] == 0,
        "captions_inside_safe_zone": len(unsafe) == 0 and len(caps) > 0,
        "no_shot_static_over_1.0s": all(s["max_still_run_s"] <= 1.0 for s in mot["per_shot"].values()),
        "all_shots_readable_luma_>0.10": all(s["mean_luma"] > 0.10 for s in mot["per_shot"].values()),
    }
    return dict(file=os.path.basename(mp4), duration_s=round(dur, 2), size_mb=round(int(info["format"]["size"]) / 1e6, 1),
                video=dict(w=v["width"], h=v["height"], fps=v["r_frame_rate"], codec=v["codec_name"]),
                loudness=loud, motion_luma=mot, caption_frames=len(caps), unsafe_caption_frames=len(unsafe),
                checks=checks, passed=all(checks.values()))
