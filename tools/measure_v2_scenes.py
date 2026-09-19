"""Measures the parallax and lighting evidence videos (spec: 'no 2.5D claim without measurable parallax', 'no lighting claim without actual change').
.venv/bin/python tools/measure_v2_scenes.py  ->  output/tests/{parallax_measurement,lighting_measurement}.json (+ docs/v2_evidence copies)

parallax: coloured marker bars are pinned to layers with different parallax factors. For sampled frames the bar centroid is detected in the decoded video and compared with the
          screen position PREDICTED from the camera arrays (Camera.view(par)); the measured shift between two frames must differ between layers in the predicted order.
lighting: mean luma / colour temperature per lighting state; face-light delta between the night shot and the phone-lit shot."""
import json
import os
import subprocess
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine.shorts.layers import Camera, C0   # noqa: E402
from engine.skeleton import short as SH, v2_scenes as VS   # noqa: E402

OUT = os.path.join(ROOT, "output/tests")
W, H, FPS = 1080, 1920, 30


def frames(path, times):
    res = {}
    for t in times:
        raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", path, "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
        res[t] = np.frombuffer(raw, np.uint8).reshape(H, W, 3).astype(int)
    return res


COL = {1.3: ("red", lambda r, g, b: (r > 150) & (g < 120) & (b < 120)), 1.0: ("green", lambda r, g, b: (g > 140) & (r < 130) & (b < 150)),
       0.86: ("blue", lambda r, g, b: (b > 150) & (r < 130) & (g < 170)), 0.6: ("yellow", lambda r, g, b: (r > 90) & (g > 70) & (b < r * 0.8))}


def bar_x(img, pred_x, pred_w, fn, hint=None):
    """Centroid of the marker bar near its predicted position (window +-90 px). The bar is a uniform vertical stripe: columns with LOW row-variance whose mean colour differs from the
    window's median column colour; among candidate groups the one whose colour is closest to the marker's graded colour (`hint`, hue check `fn` as a tie-break) wins."""
    lo, hi = int(max(0, pred_x - 90)), int(min(W, pred_x + 90))
    sub = img[300:1500, lo:hi].astype(float)
    mean = sub.mean(axis=0)                                                       # (cols, 3)
    std = sub.std(axis=0).mean(axis=1)
    med = np.median(mean, axis=0)
    dist = np.linalg.norm(mean - med, axis=1)
    cand = (std < 22) & (dist > 28)
    best, best_score = None, 0.0
    i = 0
    while i < len(cand):
        if cand[i]:
            j = i
            while j + 1 < len(cand) and cand[j + 1]:
                j += 1
            if 4 <= j - i + 1 <= 60:
                hue_ok = float(fn(sub[:, i:j + 1, 0], sub[:, i:j + 1, 1], sub[:, i:j + 1, 2]).mean())
                score = dist[i:j + 1].mean() * (1.0 + hue_ok)
                if score > best_score:
                    best, best_score = (i + j) / 2.0 + lo, score
            i = j + 1
        else:
            i += 1
    return best


def parallax():
    plan = VS.parallax_plan()
    actors = SH.build_actors(plan)
    cam = SH.build_camera(plan, actors)
    path = os.path.join(OUT, "parallax_depth_test.mp4")
    times = [0.5, 1.5, 2.5, 3.5, 4.5, 6.0, 7.5, 8.5]
    fr = frames(path, times)
    rows = []
    for t in times:
        f = int(round(t * FPS))
        c = Camera(float(cam["cx"][f]), float(cam["cy"][f]), float(cam["zoom"][f]), focus=float(cam["focus"][f]), aperture=float(cam["aperture"][f]), gain=float(cam["gain"][f]))
        for mk in plan["debug_markers"]:
            cx, cy, z = c.view(mk["par"])
            pred = (mk["x"] - cx) * z + C0[0]
            meas = bar_x(fr[t], pred, 26 * z, COL[mk["par"]][1])
            rows.append(dict(t=t, layer=COL[mk["par"]][0], par=mk["par"], predicted_x=round(float(pred), 1), measured_x=None if meas is None else round(meas, 1),
                             err_px=None if meas is None else round(abs(meas - float(pred)), 1)))
    ok = [r for r in rows if r["err_px"] is not None]
    by = {}
    for mk in plan["debug_markers"]:
        rs = sorted((r for r in ok if r["par"] == mk["par"] and r["t"] <= 4.5), key=lambda r: r["t"])
        if len(rs) >= 2:
            by[COL[mk["par"]][0]] = dict(par=mk["par"], measured_shift_px=round(rs[-1]["measured_x"] - rs[0]["measured_x"], 1), predicted_shift_px=round(rs[-1]["predicted_x"] - rs[0]["predicted_x"], 1))
    shifts = [abs(by[k]["measured_shift_px"]) for k in ("red", "green", "blue", "yellow") if k in by]
    res = dict(video="parallax_depth_test.mp4", samples=len(rows), detected=len(ok), mean_abs_err_px=round(float(np.mean([r["err_px"] for r in ok])), 2) if ok else None,
               max_abs_err_px=max((r["err_px"] for r in ok), default=None), per_layer_shift_t0p5_to_4p5=by, rows=rows,
               ordered_by_parallax=all(a > b for a, b in zip(shifts, shifts[1:])) and len(shifts) == 4,
               foreground_minus_background_shift_px=round(shifts[0] - shifts[-1], 1) if len(shifts) == 4 else None)
    return res


def lighting():
    path = os.path.join(OUT, "lighting_test.mp4")
    segs = [("1 daylight", 1.75), ("2 dusk", 5.25), ("3 night", 8.75), ("4 phone light on face", 12.5), ("5 lamp + hall", 16.5)]
    fr = frames(path, [t for _, t in segs])
    rows = []
    for (name, t), _ in zip(segs, segs):
        im = fr[t]
        body = im[250:1500, 150:930]
        lum = float((0.2126 * body[..., 0] + 0.7152 * body[..., 1] + 0.0722 * body[..., 2]).mean() / 255)
        rows.append(dict(state=name, t=t, luma=round(lum, 3), mean_rgb=[round(float(body[..., i].mean()), 1) for i in range(3)], b_over_r=round(float(body[..., 2].mean() / max(1e-6, body[..., 0].mean())), 3)))
    # face crops (fixed positions for this scene: the night wide shot and the phone medium shot both frame the head): brightness and blue-over-red of the skin area
    night, phone = fr[8.75], fr[12.5]
    face_n, face_p = night[560:740, 330:510], phone[900:1080, 430:610]
    lum = lambda im: float((0.2126 * im[..., 0] + 0.7152 * im[..., 1] + 0.0722 * im[..., 2]).mean() / 255)
    bor = lambda im: float(im[..., 2].mean() / max(1e-6, im[..., 0].mean()))
    ln, lp = lum(face_n), lum(face_p)
    L = {r["state"]: r for r in rows}
    return dict(video="lighting_test.mp4", states=rows, monotonic_day_dusk_night=L["1 daylight"]["luma"] > L["2 dusk"]["luma"] > L["3 night"]["luma"],
                lamp_hall_brighter_than_night_by=round(L["5 lamp + hall"]["luma"] - L["3 night"]["luma"], 3), phone_shot_bluer_than_night=L["4 phone light on face"]["b_over_r"] > L["3 night"]["b_over_r"],
                lamp_hall_warmer_than_night=L["5 lamp + hall"]["b_over_r"] < L["3 night"]["b_over_r"], face_crop=dict(luma_night=round(ln, 3), luma_phone=round(lp, 3), luma_delta=round(lp - ln, 3), b_over_r_night=round(bor(face_n), 3), b_over_r_phone=round(bor(face_p), 3)),
                luma_span=round(max(r["luma"] for r in rows) - min(r["luma"] for r in rows), 3))


if __name__ == "__main__":
    P, L = parallax(), lighting()
    for nm, r in (("parallax_measurement", P), ("lighting_measurement", L)):
        json.dump(r, open(os.path.join(OUT, nm + ".json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in P.items() if k != "rows"}, indent=1))
    print(json.dumps(L, indent=1))
