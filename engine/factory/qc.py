"""Factory QC: a hard gate on the finished film + reports (never hides a problem; every failure names its shots)."""
import json
import math
import os

import numpy as np
from PIL import Image, ImageDraw

from engine.shorts import captions, qc as base
from engine.shorts.layers import W, H

TREAT_COL = dict(performance=(90, 140, 220), insert_ui=(230, 170, 60), procedural=(90, 190, 130))


def run(mp4, plan, stats, rn, assets, warnings, continuity, log=print):
    fps = plan["fps"]
    info = base.probe(mp4)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    dur = float(info["format"]["duration"])
    loud = base.loudness(mp4)
    shots = plan["shots"]
    lens = [s["t1"] - s["t0"] for s in shots]
    fade_frames = set(range(int(fps * 1.0))) | set(range(int((dur - 1.1) * fps), len(stats)))
    dip = [int(s["t0"] * fps) for s in shots if s["transition_in"] == "dip"]
    for d in dip:
        fade_frames |= set(range(max(0, d - 8), d + 14))
    dark = [x["f"] for x in stats if x["mean"] < 0.03 and x["f"] not in fade_frames]
    diffs = [x["diff"] for x in stats[1:]]
    dup = sum(1 for d in diffs if d < 1e-6)
    still = {}
    run_, cur_shot = 0, None
    for x in stats[1:]:
        if x["diff"] < 4e-4 and x["shot"] == cur_shot:
            run_ += 1
        else:
            run_, cur_shot = 0, x["shot"]
        still[x["shot"]] = max(still.get(x["shot"], 0), run_)
    still_bad = {k: round(v / fps, 1) for k, v in still.items() if v / fps > 4.0}
    caps = [x for x in stats if x["caption"]]
    unsafe = [x["f"] for x in caps if x["bbox"] and not captions.in_safe_zone(x["bbox"])]
    unsafe_subject = []
    for i, sh in enumerate(shots):
        if sh["treatment"] == "performance":
            p = rn.renderer(i).subject_screen(0.5 * (sh["t0"] + sh["t1"]))
            if p and not (captions.SAFE["left"] <= p[0] <= captions.SAFE["right"] and captions.SAFE["top"] <= p[1] <= captions.SAFE["bottom"]):
                unsafe_subject.append(dict(shot=sh["id"], at=[round(p[0]), round(p[1])]))
    sig = [(s["treatment"], s["location"], s["camera"].get("size"), s["camera"].get("move")) for s in shots]
    rep3 = [shots[i]["id"] for i in range(2, len(sig)) if sig[i] == sig[i - 1] == sig[i - 2]]
    short_ui = [s["id"] for s in shots if s["treatment"] == "insert_ui" and (s["t1"] - s["t0"]) < 1.6]
    checks = {
        "aspect_ratio_as_planned": (v["width"], v["height"]) == (plan["format"]["w"], plan["format"]["h"]),
        "fps_30": v["r_frame_rate"] == "30/1",
        "h264_yuv420p": v["codec_name"] == "h264" and v["pix_fmt"] == "yuv420p",
        "has_audio": a is not None,
        "audio_video_duration_match": bool(a) and abs(float(a.get("duration", dur)) - dur) < 0.35,
        "loudness_-19_to_-13_LUFS": -19 <= loud["integrated_lufs"] <= -13,
        "true_peak_<=-1dB": loud["true_peak_db"] <= -1.0,
        "no_black_frames": not dark,
        "no_duplicate_frames": dup <= len(stats) * 0.005,
        "no_shot_static_over_4s": not still_bad,
        "cut_pacing_ok": float(np.mean(lens)) >= 2.0 and min(lens) >= 0.6,
        "captions_inside_safe_zone": not unsafe,
        "subject_inside_safe_zone": not unsafe_subject,
        "no_composition_repeated_3x": not rep3,
        "ui_inserts_readable_duration": not short_ui,
        "no_missing_assets": not assets["missing"],
        "asset_license_metadata_complete": assets["license_ok"],
        "continuity_clean": not continuity,
        "grease_pencil_rendered_by_blender": bool(plan.get("gp_bank")),
        "narration_fully_covered": plan["coverage"]["uncovered_segments"] == 0,
    }
    return dict(file=os.path.basename(mp4), duration_s=round(dur, 2), size_mb=round(int(info["format"]["size"]) / 1e6, 1), loudness=loud,
                checks=checks, passed=all(checks.values()),
                details=dict(dark_frames=len(dark), duplicate_frames=dup, static_shots_over_4s=still_bad, unsafe_caption_frames=len(unsafe),
                             unsafe_subject_shots=unsafe_subject, repeated_3x=rep3, short_ui_inserts=short_ui, shots=len(shots),
                             mean_shot_s=round(float(np.mean(lens)), 2), shortest_s=round(min(lens), 2), longest_s=round(max(lens), 2),
                             cuts_per_min=round(60 * len(shots) / dur, 1), treatments={k: sum(1 for s in shots if s["treatment"] == k) for k in TREAT_COL}),
                soft_warnings=warnings)


def contact_sheet(rn, plan, path, cols=10, w=190):
    shots = plan["shots"]
    h = int(w * H / W)
    rows = math.ceil(len(shots) / cols)
    sheet = Image.new("RGB", (cols * w, rows * (h + 16)), (16, 16, 16))
    d = ImageDraw.Draw(sheet)
    for i, s in enumerate(shots):
        t = 0.5 * (s["t0"] + s["t1"])
        img = rn.frame_at(t, int(t * plan["fps"]))
        im = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).resize((w, h))
        x, y = (i % cols) * w, (i // cols) * (h + 16)
        sheet.paste(im, (x, y + 16))
        d.text((x + 3, y + 3), f"{s['id']} {s['phase'][:4]} {s['treatment'][:4]}", fill=(255, 220, 90))
    sheet.save(path)


def timeline_png(plan, path):
    shots = plan["shots"]
    total = plan["duration"]
    img = Image.new("RGB", (1800, 240), (18, 18, 18))
    d = ImageDraw.Draw(img)
    for s in shots:
        x0, x1 = 20 + 1760 * s["t0"] / total, 20 + 1760 * s["t1"] / total
        d.rectangle((x0, 40, max(x1 - 1, x0 + 1), 110), fill=TREAT_COL[s["treatment"]])
    cur = None
    for s in shots:
        if s["phase"] != cur:
            cur = s["phase"]
            x = 20 + 1760 * s["t0"] / total
            d.line((x, 30, x, 200), fill=(255, 255, 255))
            d.text((x + 3, 120), cur, fill=(255, 255, 255))
    d.text((20, 8), "shot timeline: performance=blue  insert_ui=amber  procedural=green   |   phase boundaries in white", fill=(220, 220, 220))
    img.save(path)
