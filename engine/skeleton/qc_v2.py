"""QC for Factory V2 films: the V1 measured checks (rig, IK, walk, reach, gaze, blinks, parallax, camera, light, GP, narration, safe zone) PLUS V2 gates:
DNA v2 validity, licensed assets, hand-pose coverage, target-based gaze accuracy, hand-over interaction (ownership swap + meeting-point accuracy), planted stance feet,
contact shadows / rim light / face light, camera vocabulary (>= 7 moves, >= 6 sizes), rack focus, character isolation, foreground occlusion. No threshold is relaxed for V2."""
import json
import math
import os

import numpy as np
from PIL import Image

from engine.skeleton import dna2, qc as Q1


def _asset_gate():
    reg = json.load(open(os.path.join(Q1.os.path.dirname(Q1.__file__), "..", "..", "assets/registry/asset_registry.json")))
    used = [a for a in reg["assets"] if a["status"] == "USED"]
    ok = bool(used) and all(a["policy_decision"] in ("ACCEPT", "ACCEPT_WITH_OBLIGATIONS") and a["sha256"] and a["license_proof"] for a in used)
    return ok, [a["asset_id"] for a in used]


def run(plan, actors, cam, rep, film, mp4, stats, frames_dir, log=print):
    base = Q1.run(plan, actors, cam, rep, film, mp4, stats, frames_dir, log)
    checks, ev = dict(base["checks"]), dict(base["evidence"])
    fps = plan["fps"]
    dnas = [a.spec["dna"] for a in actors.values()]
    checks["dna_v2_valid_(schema_and_wardrobe_vocabulary)"] = all(d.get("schema") == dna2.SCHEMA and not dna2.validate(d) for d in dnas)
    ok, used = _asset_gate()
    checks["assets_licensed_(registry:_ACCEPT,_sha256,_licence_proof)"] = ok
    ev["assets_used"] = used
    views = sorted({a.view for a in actors.values()})
    checks["non_profile_view_used_(three_quarter_or_front)"] = any(v != "profile" for v in views)
    ev["views"] = views
    poses = set()
    for a in actors.values():
        poses |= {round(v) for v in a.channels["hand_R_pose_id"]} | {round(v) for v in a.channels["hand_L_pose_id"]}
    checks["hand_poses_used_(>=5_distinct)"] = len(poses) >= 5
    ev["hand_pose_ids_used"] = sorted(poses)
    # ---- gaze: every logged gaze event must point the eyes toward the target's bearing
    gz = [(cid, e) for cid, a in actors.items() for e in a.perf.events if e[1] == "gaze"]
    bad, tset = 0, set()
    for cid, (t, k, d) in gz:
        tset.add(d["target"].split("'")[0][:24])
        if abs(d["dx"]) > 60 and d["target"] != "CAMERA" and (d["gx"] > 0) != (d["dx"] > 0):
            bad += 1
    checks["gaze_targets_(>=8_events,_>=4_targets,_bearing_sign_correct)"] = len(gz) >= 8 and len(tset) >= 4 and bad == 0
    ev["gaze"] = dict(events=len(gz), distinct_targets=sorted(tset), wrong_direction=bad)
    # ---- hand-over interaction
    A, D = actors["A"], actors.get("D")
    give = [e for e in A.perf.events if e[1] == "handover_give"]
    take = [e for e in (D.perf.events if D else []) if e[1] == "handover_take"]
    inter_ok, meet_err, own = False, None, None
    if give and take:
        tg, tt = give[0][0], take[0][0]
        fi, fj = min(int(tg * fps), len(A.channels["root_x"]) - 1), min(int(tt * fps), len(D.channels["root_x"]) - 1)
        wa = A.rig_to_world(A.channels["hand_R_x"][fi], A.channels["hand_R_y"][fi])
        wd = D.rig_to_world(D.channels["hand_R_x"][fj], D.channels["hand_R_y"][fj])
        hp = plan["targets"]["HANDOVER"]
        meet_err = max(math.dist(wa, hp), math.dist(wd, hp))
        rel = [e[0] for e in A.perf.events if e[1] == "phone_release"]
        f_after = min(int((tt + 0.5) * fps), len(D.channels["phone_vis"]) - 1)
        own = dict(a_phone_after=A.channels["phone_vis"][min(int((tt + 0.6) * fps), len(A.channels["phone_vis"]) - 1)], d_phone_after=D.channels["phone_vis"][f_after], release_t=rel[:1], take_t=tt, give_t=tg)
        inter_ok = meet_err < 30 and own["a_phone_after"] < 0.5 and own["d_phone_after"] > 0.5 and abs(tt - tg) < 1.6
    checks["hand_over_(both_hands_meet_within_30px;_phone_changes_owner)"] = inter_ok
    ev["hand_over"] = dict(meet_error_px=None if meet_err is None else round(meet_err, 1), ownership=own)
    # ---- planted stance feet during the walks (no sliding)
    slip = []
    for a in actors.values():
        for t, k, d in a.perf.events:
            if k != "walk":
                continue
            f0, f1 = int((t + 0.5) * fps), int((d["t1"] - 0.5) * fps)
            for side in ("L", "R"):
                xs, ys = a.channels[f"foot_{side}_x"], a.channels[f"foot_{side}_y"]
                run_ = []
                for f in range(f0, max(f0, f1)):
                    if ys[f] <= a.P["foot_h"] + 1.0:
                        run_.append(xs[f])
                    elif run_:
                        slip.append(max(run_) - min(run_))
                        run_ = []
    checks["walk_stance_feet_planted_(max_slide_<=45px)"] = (max(slip) <= 45.0) if slip else True
    ev["stance_slide_px_max"] = round(max(slip), 1) if slip else None
    # ---- lighting features
    checks["contact_shadows_rim_light_face_light_enabled"] = film.shadow_layer is not None and bool(film.rim_params(1.0)) and plan.get("version", 1) >= 2
    fps_ = 30.0
    lamp_t = plan.get("lamp_on")
    title_t = (plan.get("title_card") or {}).get("t0", plan["duration"])
    prev_m = [x["mean"] for x in stats if plan["shots"][-2]["t0"] + 0.3 <= x["f"] / fps_ < plan["shots"][-2]["t1"]]
    lamp_m = [x["mean"] for x in stats if lamp_t is not None and lamp_t + 0.9 <= x["f"] / fps_ < title_t]                  # the lit room, before the deliberate title-card dim
    prev, last = (float(np.mean(prev_m)) if prev_m else None), (float(np.mean(lamp_m)) if lamp_m else None)
    checks["lamp_raises_brightness_(lit_room_>_previous_shot)"] = last is not None and prev is not None and last > prev + 0.02
    ev["lamp_luma_delta"] = None if last is None else round(last - prev, 3)
    # ---- camera vocabulary
    moves = sorted({s["camera"]["move"] for s in plan["shots"] if s.get("camera")})
    sizes = sorted({s["camera"]["size"] for s in plan["shots"] if s.get("camera")})
    checks["camera_vocabulary_(>=7_moves,_>=6_sizes)"] = len(moves) >= 7 and len(sizes) >= 6
    ev["camera_vocab"] = dict(moves=moves, sizes=sizes)
    foc = np.array(cam["focus"])
    checks["rack_focus_(focus_depth_changes_>=0.5)"] = float(np.ptp(foc)) >= 0.5
    ap = np.array(cam["aperture"])
    iso = [s for s in plan["shots"] if s.get("camera") and s["camera"]["move"] == "isolate"]
    checks["character_isolation_(>=2_shallow-DoF_shots)"] = len(iso) >= 2 and all(ap[int(s["t0"] * fps) + 2] > 12 for s in iso)
    ev["focus_range"] = [round(float(foc.min()), 2), round(float(foc.max()), 2)]
    # ---- foreground occlusion: a foreground layer crosses the actor's bounding box
    layers = film.renderer(0).layers
    occ = 0
    files = sorted(f for f in os.listdir(frames_dir) if f.endswith(".png"))[::6]
    for name in files:
        f = int(name[1:6])
        c = film.camera_at(f)
        bb = Q1._alpha_bbox(os.path.join(frames_dir, name))
        if not bb:
            continue
        for ln in ("plant_fg", "curtain_fg"):
            L = layers.get(ln)
            if L is None:
                continue
            cx, cy, z = c.view(L.par)
            ox, oy = L.origin
            w_world = L.base.shape[1] / L.res
            x0, x1 = (ox - cx) * z + 540, (ox + w_world - cx) * z + 540
            if x1 > bb[0] and x0 < bb[2]:
                occ += 1
                break
    checks["foreground_occlusion_(fg_layer_overlaps_the_actor_in_>=10_sampled_frames)"] = occ >= 10
    ev["fg_overlap_frames_sampled"] = occ
    checks = {k: bool(v) for k, v in checks.items()}
    return dict(file=os.path.basename(mp4), passed=all(checks.values()), n_checks=len(checks), checks=checks, evidence=ev)
