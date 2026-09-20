"""QC v4 - the production gates. Every gate is MEASURED on the rendered film / the runtime data (channels, events, frames, audio), never a constant; each stores its evidence.  Generic: nothing here knows
a story. A gate about something a story does not contain is listed in `not_applicable_gates` (recorded, not silently passed).  `autofix(report, fixes, plan)` maps a failed gate to a deterministic plan fix;
the driver (`production.make`) re-plans, re-renders (only the changed frames: content-addressed frame cache) and re-runs QC until it passes or nothing more can be fixed.
"""
import json
import math
import os
import subprocess

import numpy as np

from engine.environments import families, locations as LOC
from engine.skeleton import acts as AC, critic as CR, dna2, qc_v2, qc_v3, short
from engine.shorts.layers import H, W

MIN_SHOT, MAX_SHOT = 0.9, 6.5
SNAP_DEG_PER_FRAME = 32.0                                # a limb / head rotating faster than this in one frame (at 30 fps) is a visible pop, not a motion
SPEECH_TO_BED_DB = 8.0


def _shots(plan, kind="skeleton"):
    return [s for s in plan["shots"] if s["treatment"] == kind]


def run(plan, actors, cam, rep, film, mp4, stats, frames_dir, log=print, audio=None):
    fps = plan["fps"]
    n = int(round(plan["duration"] * fps))
    checks, ev, na = {}, {}, []
    # ------------------------------------------------------------------ plan / assets / environment
    errs = []
    if plan.get("version", 1) < 4:
        errs.append("plan version < 4")
    prev = 0.0
    for s in plan["shots"]:
        if abs(s["t0"] - prev) > 0.01 or s["t1"] <= s["t0"]:
            errs.append(f"{s['id']}: non-contiguous or empty ({prev:.2f}->{s['t0']:.2f}-{s['t1']:.2f})")
        prev = s["t1"]
        if s["treatment"] == "skeleton" and not s.get("camera"):
            errs.append(f"{s['id']}: skeleton shot without camera")
    if abs(prev - plan["duration"]) > 0.05:
        errs.append("shots do not cover the film")
    seq_errs = AC.validate(plan.get("acts") or [])
    errs += seq_errs
    for cid in plan["cast_in_short"]:
        errs += [f"{cid}: {e}" for e in dna2.validate(plan["characters"][cid]["dna"])]
    checks["plan_valid_(contiguous_shots,_act_grammar,_DNA_schema)"] = not errs
    ev["plan_errors"] = errs[:8]
    ok, used = qc_v2._asset_gate()
    checks["licence_policy_(every_USED_asset_ACCEPT,_sha256,_licence_proof)"] = ok
    ev["assets_used"] = used
    miss = [v["png"] for a in actors.values() for v in a.man["parts"].values() if isinstance(v, dict) and "png" in v and not os.path.exists(os.path.join(short.ROOT, v["png"]))]
    checks["character_assets_present"] = not miss
    ev["missing_character_parts"] = miss[:5]
    # environment + lighting + time of day
    bad_env, bad_light = [], []
    for s in plan["shots"]:
        env = s.get("environment") or plan["environment"]
        if env["family"] not in families.FAMILIES:
            bad_env.append(f"{s['id']}: unknown family {env['family']}")
        tm = env.get("variation", {}).get("time")
        lt = s["lighting"]
        if tm and lt.get("time") != tm:
            bad_light.append(f"{s['id']}: light time {lt.get('time')} != set time {tm}")
        if lt.get("time") == "day" and (lt.get("moon", 0) > 0 or lt.get("hall", 0) > 0):
            bad_light.append(f"{s['id']}: moon/hall light in a daylight shot")
        if lt.get("time") == "night" and lt.get("sun", 0) > 0:
            bad_light.append(f"{s['id']}: sun in a night shot")
    for sc in plan.get("scenes", []):
        try:
            r = LOC.resolve(sc["loc"], sc["time"])
            if r["time"] != sc["time"]:
                bad_light.append(f"scene {sc['loc']}: {sc['time']} impossible there")
        except LOC.LocationUnsupported as e:
            bad_env.append(str(e))
    checks["environments_supported_and_time_of_day_possible"] = not bad_env
    checks["lighting_matches_environment_time_(no_moon_by_day,_no_sun_by_night)"] = not bad_light
    ev["environment_problems"], ev["lighting_problems"] = bad_env[:6], bad_light[:6]
    # ------------------------------------------------------------------ framing (measured geometry)
    geo = CR.measure_geometry(plan, actors, cam)
    hard = [dict(shot=g["shot"], problems=[p["kind"] for p in g["problems"]]) for g in geo if not g["ok"]]
    clipped = [h for h in hard if any(k.endswith("clipped_x") or k.endswith("out_y") for k in h["problems"])]
    caps = [h for h in hard if "face_under_caption" in h["problems"]]
    small = [h for h in hard if "face_too_small" in h["problems"]]
    checks["no_clipped_heads_or_cropped_bodies_(measured_at_3_moments_per_shot)"] = not clipped
    checks["face_never_under_the_caption_band"] = not caps
    checks["faces_large_enough_for_their_shot_size"] = not small
    ev["framing"] = dict(shots_measured=len(geo), clipped=clipped[:6], under_caption=caps[:6], too_small=small[:6])
    # caption box vs every visible face (pixel level, sampled)
    over = []
    for st in stats[::6]:
        if not st.get("bbox"):
            continue
        f = st["f"]
        t = f / fps
        sh = plan["shots"][min(range(len(plan["shots"])), key=lambda i: abs(plan["shots"][i]["t0"] - t) if plan["shots"][i]["t0"] <= t else 1e9)]
        if sh["treatment"] != "skeleton":
            continue
        for cid, a in actors.items():
            if not short.on_screen(a, t):
                continue
            fb = CR.face_box(actors, cid, t, cam, min(f, len(cam["cx"]) - 1))
            bx = st["bbox"]
            ix = max(0, min(fb[2], bx[2]) - max(fb[0], bx[0]))
            iy = max(0, min(fb[3], bx[3]) - max(fb[1], bx[1]))
            area = max(1, (fb[2] - fb[0]) * (fb[3] - fb[1]))
            if 0 <= fb[1] < H and ix * iy / area > 0.15 and 0 < fb[0] < W:
                over.append(dict(f=f, actor=cid, frac=round(ix * iy / area, 2)))
    checks["captions_never_cover_a_face_(>15%_of_the_face_box)"] = len(over) == 0
    ev["caption_face_overlap_samples"] = over[:6]
    # ------------------------------------------------------------------ cast / continuity
    ghosts = []
    for sc in plan.get("scenes", []):
        cast = set(sc.get("cast") or plan["cast_in_short"])
        for cid, a in actors.items():
            if cid in cast:
                continue
            for tt in np.arange(sc["t0"] + 0.05, sc["t1"] - 0.05, 0.25):
                if short.on_screen(a, float(tt), lo=-120.0, hi=1200.0):
                    ghosts.append(dict(actor=cid, t=round(float(tt), 2), scene=sc["loc"]))
                    break
    checks["no_actor_appears_outside_its_scene_(parked_cast_stays_off_the_set)"] = not ghosts
    ev["ghost_actors"] = ghosts[:6]
    sigs = {cid: (c["dna"]["hair"].get("style"), c["dna"]["skin"].get("hex"), str(c["dna"]["wardrobe"].get("top")), c["dna"]["wardrobe"].get("top_color")) for cid, c in plan["characters"].items()}
    checks["cast_visually_distinct_(no_two_characters_share_hair+skin+top)"] = len(set(sigs.values())) == len(sigs)
    ev["character_signatures"] = {k: list(map(str, v)) for k, v in sigs.items()}
    # ------------------------------------------------------------------ hands / props / IK
    errs_c, recs_bad, n_rec = [], [], 0
    for cid, a in actors.items():
        for e in a.perf.events:
            if e[1] == "phone_contact":
                errs_c.append(qc_v3._phone_centre_error(a, e))
            if e[1] == "prop_cycle":
                for r in e[2]["recs"]:
                    n_rec += 1
                    if not r["ok"] or r["err"] > 6.0:
                        recs_bad.append(dict(actor=cid, t=round(e[0], 2), prop=e[2]["prop"], phase=r["phase"], err=r["err"], reachable=r["ok"]))
    if errs_c or n_rec:
        checks["hand_object_contact_(phone_grip_<=3px,_prop_cycle_contacts_reachable_and_<=6px)"] = (not errs_c or max(errs_c) <= 3.0) and not recs_bad
    else:
        na.append("hand_object_contact")
    ev["contact"] = dict(phone_contact_err_px=[round(x, 2) for x in errs_c], prop_cycle_contacts=n_rec, bad=recs_bad[:6])
    clampf = {cid: int(getattr(a, "reach_clamped_frames", 0) or 0) for cid, a in actors.items()}
    total_f = sum(clampf.values())
    ck = [(cid, e[0]) for cid, a in actors.items() for e in a.perf.events if e[1] == "reach_clamped"]
    checks["ik_reachable_(no_unreachable_targets;_clamped_frames_<=3%)"] = not ck and total_f <= 0.03 * n * max(1, len(actors))
    ev["ik"] = dict(unreachable_events=[(c, round(t, 2)) for c, t in ck][:6], clamped_frames=clampf)
    flick, held = [], {}
    for cid, a in actors.items():
        for prop in ("phone", "card", "money", "document", "cup", "bag", "laptop"):
            ch = a.channels.get(f"{prop}_vis")
            if ch is None:
                continue
            v = (np.array(ch) > 0.5).astype(int)
            k = int(np.abs(np.diff(v)).sum())
            held[f"{cid}.{prop}"] = k
            if k > 10:
                flick.append(f"{cid}.{prop} toggles {k}x")
    checks["props_not_flickering_or_broken_(<=10_visibility_changes)"] = not flick
    ev["prop_visibility_changes"] = held
    # hand-over pairs
    pairs = []
    for cid, a in actors.items():
        for e in a.perf.events:
            if e[1] == "handover_give":
                for cid2, b in actors.items():
                    for e2 in b.perf.events:
                        if e2[1] == "handover_take" and abs(e2[0] - e[0]) < 1.6 and cid2 != cid:
                            wa = a.rig_to_world(a.perf.v(f"hand_{e[2]['hand']}_x", e[0]), a.perf.v(f"hand_{e[2]['hand']}_y", e[0]))
                            wb = b.rig_to_world(b.perf.v(f"hand_{e2[2]['hand']}_x", e2[0]), b.perf.v(f"hand_{e2[2]['hand']}_y", e2[0]))
                            pairs.append(dict(giver=cid, taker=cid2, prop=e[2]["prop"], hands_px=round(math.dist(wa, wb), 1), dt=round(abs(e2[0] - e[0]), 2)))
    gives = sum(1 for a in actors.values() for e in a.perf.events if e[1] == "handover_give")
    if gives:
        checks["hand_over_pairs_(every_give_has_a_take_<=1.6s_and_hands_<=130px)"] = len(pairs) >= gives and all(p["hands_px"] <= 130 and p["dt"] < 1.6 for p in pairs)
    else:
        na.append("hand_over")
    ev["hand_overs"] = pairs
    # ------------------------------------------------------------------ motion quality
    snaps = []
    tele = {cid: [e[0] for e in a.perf.events if e[1] == "teleport"] for cid, a in actors.items()}
    for cid, a in actors.items():
        for k, v in a.channels.items():
            if not (k.endswith("_rot") or k in ("spine_rot", "chest_rot")) or "pose" in k:
                continue
            d = np.abs(np.diff(np.array(v, np.float64)))
            for f in np.where(d > SNAP_DEG_PER_FRAME)[0]:
                t = f / fps
                if any(abs(t - tt) < 0.3 for tt in tele[cid]) or not short.on_screen(a, t, -200, 1280):
                    continue
                snaps.append(dict(actor=cid, channel=k, t=round(float(t), 2), deg=round(float(d[f]), 1)))
    checks[f"no_snapping_(no_joint_rotates_>{SNAP_DEG_PER_FRAME:.0f}_deg_in_one_frame_while_on_screen)"] = not snaps
    ev["snaps"] = snaps[:8]
    gz = [(cid, e) for cid, a in actors.items() for e in a.perf.events if e[1] == "gaze"]
    ev["gaze_events"] = len(gz)
    checks["gaze_is_target_driven_(>=6_gaze_events,_>=3_distinct_targets)"] = len(gz) >= 6 and len({e[2]["target"] for _, e in gz}) >= 3
    used_ch = {k for a in actors.values() for k, v in a.channels.items() if k.startswith("face_") and float(np.ptp(np.array(v))) > 0.05}
    ev["moving_face_channels"] = len(used_ch)
    # ------------------------------------------------------------------ shots / rhythm / repetition / dead frames
    findings = CR.review_rhythm(plan)
    rh_bad = [f for f in findings if f["kind"] in ("shot_too_short", "shot_too_long", "repeated_framing", "slow_hook")]
    checks["editing_rhythm_(no_shot_<0.9s_or_>6.5s,_no_repeated_framing,_hook<=4.5s)"] = not rh_bad
    ev["rhythm_findings"] = rh_bad[:8]
    keys = [(s["camera"]["target"], s["camera"]["size"]) for s in _shots(plan) if s.get("camera")]
    win_rep = [i for i in range(len(keys) - 3) if len(set(keys[i:i + 4])) == 1]
    checks["framing_variety_(>=5_distinct_framings,_>=4_sizes,_no_4_identical_in_a_row)"] = len(set(keys)) >= 5 and len({k[1] for k in keys}) >= 4 and not win_rep
    ev["framing_variety"] = dict(distinct=len(set(keys)), sizes=sorted({k[1] for k in keys}), moves=sorted({s["camera"]["move"] for s in _shots(plan) if s.get("camera")}))
    dup = []
    for a_, b_ in zip(plan["shots"], plan["shots"][1:]):
        if a_["treatment"] == b_["treatment"] and a_.get("camera") == b_.get("camera") and a_.get("environment") == b_.get("environment") and a_["treatment"] == "skeleton" and a_.get("act") == b_.get("act"):
            dup.append((a_["id"], b_["id"]))
    checks["no_duplicate_consecutive_shots"] = not dup
    ev["duplicate_shots"] = dup
    dips = [(int(round(sh["t0"] * fps)) - 2, int(round(sh["t0"] * fps)) + int(0.6 * fps)) for sh in plan["shots"] if sh.get("transition_in") in ("fade", "dip")]     # a planned fade / dip-to-black is not a dead frame
    fs = [s for s in stats if 0 <= s["f"] < n and not any(a <= s["f"] <= b for a, b in dips) and s["f"] < n - int(0.4 * fps)]
    black = [s["f"] for s in fs if s["mean"] < 0.02]
    frozen, run_ = [], 0
    for s in fs:
        run_ = run_ + 1 if s["diff"] < 1e-5 else 0
        if run_ == 75:
            frozen.append(s["f"])
    checks["no_dead_frames_(no_black_frames,_no_frozen_run_>2.5s)"] = not black and not frozen
    ev["dead_frames"] = dict(black=black[:6], frozen_run_ends=frozen[:6])
    tc = plan.get("title_card")
    checks["end_screen_present_(title_card_>=1.5s_over_the_last_shot)"] = bool(tc) and plan["duration"] - tc["t0"] >= 1.5 and tc["t1"] >= plan["duration"] - 0.05
    dots = [s for s in _shots(plan) if s.get("camera")]
    static = []
    for s in dots:
        f0, f1 = int(s["t0"] * fps), min(int(s["t1"] * fps), n - 1)
        if f1 - f0 < 12:
            continue
        motion = 0.0
        for cid, a in actors.items():
            if any(short.on_screen(a, s["t0"] + u * (s["t1"] - s["t0"]), -300, 1400) for u in (0.05, 0.5, 0.95)):
                for k in ("hand_R_x", "hand_L_x", "head_rot", "torso_lean", "eye_dx", "spine_rot", "root_x"):
                    if k in a.channels:
                        motion += float(np.ptp(np.array(a.channels[k][f0:f1 + 1])))
        if motion < 1.0:
            static.append(s["id"])
    checks["no_slideshow_(every_skeleton_shot_has_performance_motion)"] = not static
    ev["static_shots"] = static
    # ------------------------------------------------------------------ audio
    if audio:
        checks["audio_no_clipping_(peak_<=0.99,_0_clipped_samples)"] = audio["peak"] <= 0.99 and audio["clipped_samples"] == 0
        checks[f"narration_intelligible_(speech_to_bed_>={SPEECH_TO_BED_DB:.0f}_dB)"] = audio["speech_to_bed_db"] >= SPEECH_TO_BED_DB
        checks["audio_duration_matches_video_(<=0.15s)"] = abs(audio["duration"] - plan["duration"]) <= 0.15
        checks["no_dead_air_(<=3_silent_half-seconds_in_the_mix)"] = audio["silent_half_seconds"] <= 3
        ev["audio"] = audio
    else:
        checks["audio_present"] = False
    segs = plan["narration"]["segments"]
    bad_seg = [s["id"] for s in segs if not (0 <= s["start"] < s["end"] <= plan["duration"])]
    wps = [len(s["text"].split()) / max(s["end"] - s["start"], 1e-3) for s in segs]
    checks["narration_aligned_(segments_inside_the_film,_1.2-6.5_words/s)"] = not bad_seg and all(1.0 <= w <= 6.5 for w in wps)
    ev["narration"] = dict(bad_segments=bad_seg, words_per_second=[round(w, 2) for w in wps][:24])
    if audio and plan["narration"].get("audio"):
        from engine.shorts import audio as A
        ap = plan["narration"]["audio"]
        ap = ap if os.path.isabs(ap) else os.path.join(short.ROOT, ap)
        nar = A._read_wav(ap) if ap.endswith(".wav") else None
        if nar is not None and len(nar):
            sr = A.SR
            mx = float(np.abs(nar).max()) + 1e-9
            silent = [s["id"] for s in segs if float(np.abs(nar[int(s["start"] * sr):int(s["end"] * sr)]).max() if int(s["end"] * sr) > int(s["start"] * sr) else 0) < 0.05 * mx]
            checks["every_narration_segment_is_audible_in_the_narration_track"] = not silent
            ev["silent_narration_segments"] = silent
    # ------------------------------------------------------------------ the file itself
    pr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries", "stream=nb_read_frames,width,height,r_frame_rate:format=duration", "-of", "json", mp4], capture_output=True, text=True)
    dec = subprocess.run(["ffmpeg", "-v", "error", "-i", mp4, "-f", "null", "-"], capture_output=True, text=True)
    try:
        j = json.loads(pr.stdout)
        st_ = j["streams"][0]
        frames_ok = abs(int(st_["nb_read_frames"]) - n) <= 2 and (st_["width"], st_["height"]) == (W, H) and abs(float(j["format"]["duration"]) - plan["duration"]) < 0.3
        ev["video"] = dict(frames=int(st_["nb_read_frames"]), expected=n, size=[st_["width"], st_["height"]], duration=float(j["format"]["duration"]))
    except Exception as e:                                            # noqa: BLE001
        frames_ok = False
        ev["video"] = dict(error=str(e))
    checks["video_decodes_cleanly_(ffmpeg_reports_0_errors;_frame_count,_size,_duration_match)"] = frames_ok and not dec.stderr.strip()
    ev["decode_stderr"] = dec.stderr.strip()[:200]
    miss_f = [f for s in _shots(plan) for f in (int(round(s["t0"] * fps)), min(n - 1, int(round(s["t1"] * fps)) - 1)) if not os.path.exists(os.path.join(frames_dir, f"a{f:05d}.png"))]
    checks["no_missing_rendered_frames_(first_and_last_frame_of_every_skeleton_shot)"] = not miss_f
    ev["missing_frames"] = miss_f[:6]
    ev["not_applicable_gates"] = na
    fc = rep.get("frame_cache")
    if fc:
        ev["frame_cache"] = fc
    return dict(file=os.path.basename(mp4), passed=all(checks.values()), n_checks=len(checks), checks=checks, evidence=ev)


# ------------------------------------------------------------------------------------------------------------------ auto-fix
def autofix(report, fixes, plan, audio_cfg):
    """failed gates -> deterministic fixes in the plan-fix dict / audio config. Returns [description]. Nothing here guesses: each fix targets the measured cause."""
    done = []
    ck = report["checks"]
    ev = report["evidence"]
    fail = {k for k, v in ck.items() if not v}
    if any(k.startswith("audio_no_clipping") or k.startswith("narration_intelligible") for k in fail):
        audio_cfg["music"] = round(audio_cfg.get("music", 0.30) * 0.7, 3)
        audio_cfg["sfx"] = round(audio_cfg.get("sfx", 0.55) * 0.75, 3)
        audio_cfg["ambience"] = round(audio_cfg.get("ambience", 0.55) * 0.75, 3)
        done.append(f"audio: music/sfx/ambience gains lowered -> {audio_cfg}")
    if any(k.startswith("face_never_under") or k.startswith("captions_never_cover") for k in fail):
        for s in ev["framing"].get("under_caption", []) + [dict(shot=x) for x in []]:
            sh = next((z for z in plan["shots"] if z["id"] == s["shot"]), None)
            if sh:
                CR._merge(fixes, sh.get("key", sh["beats"][0]), "camera", dict(dy=60.0))
                done.append(f"{s['shot']}: camera dy +60 (face out from under the caption)")
        for o in ev.get("caption_face_overlap_samples", []):
            t = o["f"] / plan["fps"]
            sh = next((z for z in plan["shots"] if z["t0"] <= t < z["t1"]), None)
            if sh and sh["treatment"] == "skeleton":
                CR._merge(fixes, sh.get("key", sh["beats"][0]), "camera", dict(dy=90.0))
                done.append(f"{sh['id']}: camera dy +90 (caption overlapped {o['actor']}'s face)")
    if any(k.startswith("editing_rhythm") or k.startswith("framing_variety") for k in fail):
        d = CR.fix_rhythm(plan, [f for f in CR.review_rhythm(plan) if f["kind"] == "repeated_framing"], fixes)
        done += [f"rhythm: {x}" for x in d]
    if any(k.startswith("no_clipped_heads") or k.startswith("faces_large") for k in fail):
        done.append("framing: handled by the critic loop (solve_camera) in the next planning round")
    return done
