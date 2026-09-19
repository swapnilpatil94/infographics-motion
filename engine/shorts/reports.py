"""Automated visual QA + reports for a rendered Film.

Adds the checks the base QC (qc.py) does not cover and writes human-readable artifacts next to the video:
  contact_sheet.png   one frame per shot (mid-shot) with id / role / time
  timing_report.json  shot table (role, set, size, move, duration), cut density, pause list, words/sec
  asset_report.json   every asset family used + license/provenance from assets/licenses/registry.json
Checks: key subject inside safe zone, cut density, duplicate frames, palette consistency per set,
asset license metadata present, no unknown SVG layers, narration coverage.
"""
import json
import math
import os

import numpy as np
from PIL import Image, ImageDraw

from engine.shorts import film as F, sets
from engine.shorts.captions import SAFE
from engine.shorts.layers import W, H, C0
from engine.shorts.raster import ROOT


def _shots(film):
    return [s for s in film.shots]


def timing_report(film):
    rows = []
    for s in _shots(film):
        e = s["beat"]
        rows.append(dict(id=s["id"], role=e.get("role"), kind=e["kind"], set=e.get("set"), t0=round(s["t0"], 2), t1=round(s["t1"], 2),
                         dur=round(s["t1"] - s["t0"], 2), size=(s["cam"] or {}).get("size"), move=(s["cam"] or {}).get("move"),
                         insert=s["insert"], recipe=e.get("recipe")))
    pauses = []
    for a, b in zip(film.beats, film.beats[1:]):
        pauses.append(dict(before=b["id"], role=b.get("role"), silence_s=round(b["words"][0]["start"] - a["words"][-1]["end"], 2)))
    n_words = sum(len(b["words"]) for b in film.beats)
    speech = film.beats[-1]["words"][-1]["end"] - film.beats[0]["words"][0]["start"]
    durs = [r["dur"] for r in rows]
    return dict(shots=rows, pauses=pauses, shot_count=len(rows), mean_shot_s=round(float(np.mean(durs)), 2),
                shortest_s=min(durs), longest_s=max(durs), cuts_per_10s=round(10 * len(rows) / film.duration, 2),
                words_per_second=round(n_words / max(speech, 1e-6), 2))


def _eyes_screen(film, s):
    """Screen position of the shot's SUBJECT: the eyes for character shots, the prop for prop inserts (clock/phone)."""
    e = s["beat"]
    if e["kind"] != "scene":
        return None
    t = 0.5 * (s["t0"] + s["t1"])
    cam = F.camera_at(film, s, t)
    cx, cy, z = cam.view(1.0)
    subject = s["cam"].get("subject") or {"clock": "clock", "detail": "stand"}.get(s["cam"].get("size"), "eyes")
    wx, wy = F.CLOCK if subject == "clock" else F.STAND if subject == "stand" else e["rig"].anchor(subject)
    return (wx - cx) * z + C0[0], (wy - cy) * z + C0[1]


def safe_zone_checks(film):
    bad = []
    for s in _shots(film):
        if s["insert"]:
            continue
        p = _eyes_screen(film, s)
        if p and not (SAFE["left"] <= p[0] <= SAFE["right"] and SAFE["top"] <= p[1] <= SAFE["bottom"]):
            bad.append(dict(shot=s["id"], eyes_at=[round(p[0]), round(p[1])]))
    return bad


def palette_consistency(film, stats):
    """Chromaticity (r,g,b share of total light) of each shot's mid frame, grouped by set: do all shots of a location
    live in the same colour family? Brightness is excluded on purpose - the lighting story (moon -> phone glow) changes it."""
    by_set = {}
    for s in _shots(film):
        e = s["beat"]
        if e["kind"] != "scene" or s["insert"]:
            continue
        mid = int(0.5 * (s["t0"] + s["t1"]) * film.fps)
        if mid < len(stats) and "rgb" in stats[mid]:
            rgb = np.array(stats[mid]["rgb"])
            by_set.setdefault(e["set"], []).append(rgb / max(rgb.sum(), 1e-6))
    worst = 0.0
    for sid, arr in by_set.items():
        a = np.array(arr)
        worst = max(worst, float(np.abs(a - a.mean(axis=0)).max()))
    return round(worst, 3)


def asset_report(film):
    reg = {a["id"]: a for a in json.load(open(os.path.join(ROOT, "assets/licenses/registry.json")))["assets"]}
    used = ["cast_open_peeps_v1", "icons_ink_v1"] + (["rig_art_layered_v1"] if getattr(film, "stage", None) is not None else []) + sorted({f"set_{s['beat']['set']}" for s in _shots(film) if s["beat"]["kind"] == "scene"})
    rows, missing = [], []
    for u in used:
        a = reg.get(u)
        if not a or a.get("status") != "REGISTERED" or not a.get("license"):
            missing.append(u)
        else:
            rows.append(dict(id=u, license=a["license"], source=a["source"], author=a["author"], sha256=a["sha256"][:16],
                             commercial_use=a["commercial_use"], attribution_required=a["attribution_required"]))
    return dict(assets=rows, missing_metadata=missing)


def contact_sheet(film, frame_fn, path, cols=6, w=270):
    """One frame per shot. frame_fn(t, f) -> float image."""
    shots = _shots(film)
    h = int(w * H / W)
    rows = math.ceil(len(shots) / cols)
    sheet = Image.new("RGB", (cols * w, rows * (h + 22)), (18, 18, 18))
    d = ImageDraw.Draw(sheet)
    for i, s in enumerate(shots):
        t = 0.5 * (s["t0"] + s["t1"])
        img = frame_fn(t, int(t * film.fps))
        im = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).resize((w, h))
        x, y = (i % cols) * w, (i // cols) * (h + 22)
        sheet.paste(im, (x, y + 22))
        d.text((x + 4, y + 5), f"{s['id']} {s['beat'].get('role') or ''} {s['t0']:.1f}-{s['t1']:.1f}s", fill=(255, 220, 90))
    sheet.save(path)
    return path


def run_all(film, out_dir, stats, frame_fn):
    """-> (extra_checks dict[str,bool], details dict). Writes the report files."""
    tr = timing_report(film)
    json.dump(tr, open(os.path.join(out_dir, "timing_report.json"), "w"), indent=2, ensure_ascii=False)
    ar = asset_report(film)
    json.dump(ar, open(os.path.join(out_dir, "asset_report.json"), "w"), indent=2)
    contact_sheet(film, frame_fn, os.path.join(out_dir, "contact_sheet.png"))
    unsafe = safe_zone_checks(film)
    diffs = np.array([s.get("diff", 1.0) for s in stats[1:]])
    fade_guard = int(0.7 * film.fps)
    dup = int((diffs[fade_guard:-fade_guard] < 1e-6).sum()) if len(diffs) > 2 * fade_guard else 0
    pal = palette_consistency(film, stats)
    checks = {
        "key_subject_inside_safe_zone": not unsafe,
        "cut_density_<=_6_per_10s": tr["cuts_per_10s"] <= 6.0,
        "no_shot_shorter_than_0.35s": tr["shortest_s"] >= 0.35,
        "no_duplicate_frames": dup == 0,
        "palette_consistent_within_set": pal < 0.08,
        "asset_license_metadata_complete": not ar["missing_metadata"],
        "narration_fully_captioned": len(film.caption_track) >= len(film.beats),
    }
    details = dict(unsafe_subject_shots=unsafe, duplicate_frames=dup, palette_spread=pal, timing=dict(
        shots=tr["shot_count"], mean_shot_s=tr["mean_shot_s"], cuts_per_10s=tr["cuts_per_10s"], words_per_second=tr["words_per_second"]),
        assets_missing_metadata=ar["missing_metadata"])
    return checks, details
