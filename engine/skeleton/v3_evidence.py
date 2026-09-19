"""Evidence renders for the ASSET + ACTING QUALITY LOCK milestone: hand library sheet, silhouette test, turnaround, human motion quality, 50 characters (new art).
Every render goes through the real Blender rig job; nothing is drawn by hand except backdrops."""
import json
import math
import os

import numpy as np
from PIL import Image, ImageDraw

from engine.skeleton import dna2, hands3 as H3, motion as M, parts_art2 as PA2, rig_def as R, short as SH, v2_evidence as E

OUT = E.OUT
GROUND = E.GROUND


def a_pose(a, t=0.0):
    """neutral A-pose for turnaround / silhouette work: mark the actor so its hand channels are DROPPED after sampling - Blender then uses the rig's rest wrist positions (arms hang naturally)."""
    a._rest_hands = True
    from engine.skeleton import motion_v2 as MV
    for side in ("L", "R"):
        MV.set_pose(a.perf, -1.0, side, "relaxed")


def rest_hands(actors):
    for a in actors:
        if getattr(a, "_rest_hands", False):
            for side in ("L", "R"):
                for ax in ("x", "y"):
                    a.channels.pop(f"hand_{side}_{ax}", None)


def _rgba(path, bg=(206, 214, 226)):
    im = Image.open(path).convert("RGBA")
    b = Image.new("RGBA", im.size, bg + (255,))
    b.alpha_composite(im)
    return b.convert("RGB")


# ------------------------------------------------------------------------------------------------------------------ 1. hand library sheet
def hand_library_sheet(path=None):
    d = dna2.make("hand_lib", "young_woman", {"wardrobe.top": "tee"})
    tiles = []
    for view in ("profile", "three_quarter"):
        k = PA2.Kit(d, view)
        for side in ("R", "L"):
            for pose in H3.POSES:
                mirror = (side == "L" and view != "profile")
                if pose in H3.HARVEST:
                    im, _, _ = H3.harvested_png(k, pose, mirror, 2.0)
                else:
                    svg, _, _ = H3.hand_svg(k, pose, mirror)
                    from engine.shorts.raster import rasterize
                    arr, _ = rasterize(svg, zoom=2.0, crop=True)
                    im = Image.fromarray(arr)
                tiles.append((f"{view[:3]} {side} {pose}", im))
    cols = 10
    W = max(t[1].width for t in tiles) + 14
    H = max(t[1].height for t in tiles) + 26
    rows = (len(tiles) + cols - 1) // cols
    c = Image.new("RGB", (W * cols, H * rows + 44), (206, 214, 226))
    dr = ImageDraw.Draw(c)
    dr.text((10, 10), "HAND LIBRARY v3 - 20 poses x left/right x profile + 3/4 (hold_phone = real Open Peeps CC0 drawing harvested from the 'Device' atom; the rest are parametric in the same ink)", fill=(20, 20, 30))
    for i, (n, im) in enumerate(tiles):
        x, y = (i % cols) * W, 44 + (i // cols) * H
        dr.text((x + 4, y + 2), n, fill=(110, 0, 0))
        c.paste(im, (x + 6, y + 20), im)
    path = path or os.path.join(OUT, "hand_library_v3_sheet.png")
    c.save(path)
    return path


# ------------------------------------------------------------------------------------------------------------------ 2. silhouette test
def silhouette_test(log=print):
    """three characters x eight situations, rendered by Blender and reduced to a solid silhouette; readability is MEASURED (one connected body, hands and feet protrude, aspect)."""
    import cv2
    dnas = [dna2.make("sil:1", "young_man", {"wardrobe.top": "hoodie"}), dna2.make("sil:2", "middle_aged_woman", {"wardrobe.top": "kurta", "wardrobe.bottom": "salwar"}),
            dna2.make("sil:3", "elderly_man", {"wardrobe.top": "sweater"})]
    cols = [("front", "front", 1), ("3q", "three_quarter", 1), ("side", "profile", 1), ("back", "back", 1), ("walking", "three_quarter", 1), ("sitting", "profile", 1), ("reaching", "three_quarter", 1),
            ("holding phone", "three_quarter", 1)]
    actors, meta = [], []
    W, H = 3600, 1500
    for r, d in enumerate(dnas):
        for c, (nm, view, facing) in enumerate(cols):
            ox = 300 + c * 640
            res = (lambda tid, t, ox=ox: (ox + 250.0, GROUND - 540.0))
            a = E.make_actor(f"S{r}{c}", d, view=view, facing=facing, origin=(ox, GROUND + r * 0.0), hand_set="full", start="sit" if nm == "sitting" else "stand", resolver=res)
            if nm == "walking":
                M.perform(a.perf, "walk", 0.0, 3.0, "neutral", 0.6, speed=150.0)
            elif nm == "reaching":
                M.perform(a.perf, "reach", 0.2, 1.3, "curious", 0.7, target="PHONE", grip="grab")
            elif nm == "holding phone":
                M.perform(a.perf, "grab", 0.2, 0.1, "neutral", 0.5, prop="phone")
                M.perform(a.perf, "hold_phone", 0.3, 1.0, "neutral", 0.5, pos="chest")
            if nm in ("front", "3q", "side", "back"):
                a_pose(a)
            actors.append((r, c, a))
    frames_for = 30
    CW, CH = 2560, 900
    sheet = Image.new("RGB", (CW, len(dnas) * (CH + 10) + 70), (236, 236, 232))
    dr = ImageDraw.Draw(sheet)
    dr.text((10, 8), "SILHOUETTE TEST - solid black from the real Blender render, no shading: front | 3/4 | side | back | walking | sitting | reaching | holding phone  (3 characters)", fill=(20, 20, 20))
    metrics = []
    span = 640 * len(cols)
    for r, d in enumerate(dnas):
        row_actors = [a for rr, c, a in actors if rr == r]
        E.finish(row_actors, 30, 2.0)
        rest_hands(row_actors)
        n = len(row_actors[0].channels["root_x"])
        cam = E.cams_const(n, 300 + span / 2 - 320, GROUND - 470, CW / (span + 100))
        work, rep = E.blender_frames(row_actors, cam, CW, CH, 30, f"sil_row{r}", samples=6, render_frames=[frames_for], log=log)
        img = Image.open(os.path.join(work, "frames", f"e{frames_for:05d}.png")).convert("RGBA")
        a_ = np.asarray(img)[..., 3] > 128
        sil = np.where(a_, 0, 236).astype(np.uint8)
        sheet.paste(Image.fromarray(sil).convert("RGB"), (0, 70 + r * (CH + 10)))
        colw = CW / len(cols)
        for c, (nm, view, facing) in enumerate(cols):
            x0, x1 = int(c * colw), int((c + 1) * colw)
            m = a_[:, x0:x1].astype(np.uint8)
            n_cc, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
            big = [i for i in range(1, n_cc) if st[i, cv2.CC_STAT_AREA] > 300]
            ys, xs = np.where(m > 0)
            w_, h_ = (xs.max() - xs.min() + 1, ys.max() - ys.min() + 1) if len(xs) else (0, 0)
            metrics.append(dict(character=r, case=nm, components=len(big), area=int(m.sum()), bbox=[int(w_), int(h_)], fill_ratio=round(float(m.sum()) / max(1, w_ * h_), 3)))
    for c, (nm, _, _) in enumerate(cols):
        dr.text((c * CW / len(cols) + 8, 40), nm, fill=(150, 0, 0))
    path = os.path.join(OUT, "silhouette_test_v3.png")
    sheet.save(path)
    ok = all(m["components"] == 1 for m in metrics)
    json.dump(dict(cases=metrics, all_single_connected_body=ok), open(os.path.join(OUT, "silhouette_test_v3.json"), "w"), indent=1)
    return path, metrics


# ------------------------------------------------------------------------------------------------------------------ 3. turnaround
def turnaround(log=print):
    """one identity, five views: front | 3/4 left | side | 3/4 right | back - same DNA, same clothes, same hair, same proportions (asserted by DNA id and part hashes)."""
    d = dna2.make("turn:1", "young_woman", {"wardrobe.top": "jacket", "wardrobe.bottom": "trousers", "wardrobe.shoes": "sneakers", "wardrobe.accessories": ["earrings"]})
    order = [("front", "front", 1), ("3/4 left", "three_quarter", -1), ("side", "profile", 1), ("3/4 right", "three_quarter", 1), ("back", "back", 1)]
    actors = []
    for i, (nm, view, facing) in enumerate(order):
        a = E.make_actor(f"T{i}", d, view=view, facing=facing, origin=(260 + i * 340, GROUND), hand_set="full", start="stand")
        a_pose(a)
        M.perform(a.perf, "breathe", 0.0, 3.0, "neutral", 0.5)
        actors.append(a)
    E.finish(actors, 30, 2.0)
    rest_hands(actors)
    n = len(actors[0].channels["root_x"])
    cam = E.cams_const(n, 260 + 340 * 2, GROUND - 470, 0.62)
    work, rep = E.blender_frames(actors, cam, 1900, 1060, 30, "turnaround", samples=10, render_frames=[30], log=log)
    fr = _rgba(os.path.join(work, "frames", "e00030.png"), (232, 232, 228)).convert("RGBA")
    dr = ImageDraw.Draw(fr)
    dr.text((14, 10), f"TURNAROUND - one identity ({d['id']}): front | 3/4 left | side | 3/4 right | back   (same DNA, clothes, hair, proportions)", fill=(20, 20, 20))
    for i, (nm, _, _) in enumerate(order):
        dr.text((60 + i * 340 * 0.62 * 1.0 + 100, 1010), nm, fill=(150, 0, 0))
    path = os.path.join(OUT, "turnaround_v3.png")
    fr.convert("RGB").save(path)
    same = len({a.man["dna_id"] for a in actors}) == 1 and len({json.dumps(a.man["wardrobe"], sort_keys=True) for a in actors}) == 1
    json.dump(dict(dna_id=d["id"], views=[o[0] for o in order], same_identity=same, proportions_height=[round(a.man["P"]["hip_y"], 1) for a in actors]), open(os.path.join(OUT, "turnaround_v3.json"), "w"), indent=1)
    return path, same


# ------------------------------------------------------------------------------------------------------------------ 4. human motion quality
def _seq_video(name, seqs, dur, w, h, cam_fn, backdrop_extra, header, log=print, samples=8):
    """seqs = list of (actor, [(t0, t1), ...]) - each actor is one VIEW-SET of a character shown only inside its windows (replacement-drawing turns)."""
    actors = [a for a, _ in seqs]
    fps = 30
    E.finish(actors, fps, dur)
    n = len(actors[0].channels["root_x"])
    for a, wins in seqs:
        a.channels["char_vis"] = [1.0 if any(t0 <= i / fps < t1 for t0, t1 in wins) else 0.0 for i in range(n)]
    cam = cam_fn(n)
    work, rep = E.blender_frames(actors, cam, w, h, fps, name, samples, log=log)
    path = os.path.join(OUT, name + ".mp4")

    def frames():
        for i in range(n):
            t = i / fps
            cx, cy, zz = cam["cx"][i], cam["cy"][i], SH.view_zoom(cam["zoom"][i], cam.get("gain", np.ones(n))[i])
            img, d, sx, sy = E.studio_backdrop(w, h, i, cx, cy, zz, extra=(lambda dd, a, b, z, t=t: backdrop_extra(dd, a, b, z, t)))
            img.alpha_composite(Image.open(os.path.join(work, "frames", f"e{i:05d}.png")).convert("RGBA"))
            d = ImageDraw.Draw(img)
            txt, sub = header(t)
            E.label(d, txt, w=w, sub=sub)
            yield img
    E.encode(frames(), w, h, fps, path)
    return path, rep


def human_motion_quality(log=print, w=1280, h=720):
    """walk -> stop -> TURN (replacement views 3/4 -> front -> 3/4) -> walk back -> sit -> reach -> grab -> hold -> look -> talk -> react -> stand, one continuous take."""
    d = dna2.make("hm:1", "young_man", {"wardrobe.top": "shirt", "wardrobe.bottom": "trousers", "wardrobe.shoes": "sneakers", "wardrobe.accessories": [], "glasses": "* None"})
    x_a, x_b = 260.0, 900.0                                                          # walk right from x_a to x_b, turn, walk back to the chair
    chair_x = 420.0
    ph = (lambda tid, t: (chair_x - 330.0, GROUND - 520.0))
    A = E.make_actor("Ar", d, view="three_quarter", facing=1, origin=(x_a, GROUND), hand_set="full", start="stand", resolver=ph)
    F = E.make_actor("Af", d, view="front", facing=1, origin=(x_b, GROUND), hand_set="full", start="stand", resolver=ph)
    B = E.make_actor("Bl", d, view="three_quarter", facing=-1, origin=(x_b, GROUND), hand_set="full", start="stand", resolver=ph)
    t_turn = 5.2
    M.perform(A.perf, "walk", 0.4, 3.9, "neutral", 0.6, speed=185.0, end_x=x_b - x_a)
    M.perform(A.perf, "look_at", 4.2, 0.8, "neutral", 0.5, target="CAMERA")
    M.perform(F.perf, "breathe", 0.0, 30.0, "neutral", 0.5)
    # after the turn: walk left to the chair (rig frame of B: forward = world left), sit, act
    walk_len = x_b - (chair_x + 190 * B.P["k"] + 60)
    M.perform(B.perf, "walk", t_turn + 0.25, 3.0, "neutral", 0.6, speed=185.0, end_x=walk_len)
    t_sit = t_turn + 0.25 + 3.4
    M.perform(B.perf, "sit", t_sit, 1.3, "neutral", 0.5)
    t = t_sit + 1.7
    M.perform(B.perf, "reach", t, 1.4, "curious", 0.6, target="PHONE", grip="grab")
    M.perform(B.perf, "grab", t + 1.5, 0.1, "neutral", 0.5, prop="phone")
    M.perform(B.perf, "hold_phone", t + 1.7, 1.0, "neutral", 0.5, pos="chest")
    M.perform(B.perf, "look_at", t + 2.5, 0.8, "neutral", 0.5, target="PHONE")
    M.perform(B.perf, "read_phone", t + 3.0, 2.2, "neutral", 0.5)
    words = [dict(word=wd, start=t + 5.4 + 0.4 * i, end=t + 5.4 + 0.4 * i + 0.34) for i, wd in enumerate(["ये", "तो", "बैंक", "नहीं", "लगता"])]
    M.perform(B.perf, "speak", t + 5.4, 2.2, "neutral", 0.5, words=words)
    M.perform(B.perf, "realization", t + 7.8, 1.8, "shocked", 0.8)
    M.perform(B.perf, "fear", t + 9.8, 1.3, "fearful", 0.7)
    M.perform(B.perf, "stand", t + 11.4, 1.3, "neutral", 0.5)
    dur = t + 13.2
    seqs = [(A, [(0.0, t_turn - 0.3)]), (F, [(t_turn - 0.3, t_turn + 0.25)]), (B, [(t_turn + 0.25, dur)])]
    labels = [(0.0, "WALK  (planted stance, contact / passing / push-off, arm counter-swing, head stabilised)"), (4.4, "STOP  (decelerates, weight settles)"), (t_turn - 0.3, "TURN  (replacement views 3/4 -> front -> 3/4)"),
              (t_turn + 0.25, "WALK back"), (t_sit, "SIT"), (t, "REACH -> GRAB (hand closes ON the phone)"), (t + 1.7, "HOLD / LOOK"), (t + 3.0, "READ"), (t + 5.4, "TALK (lip-sync)"), (t + 7.8, "REACT: realization"), (t + 9.8, "REACT: fear"),
              (t + 11.4, "STAND")]

    def header(tt):
        cur = [txt for t0, txt in labels if t0 <= tt][-1]
        return "human_motion_quality_v3  |  one continuous take, real Blender rig", cur

    def extra(dd, sx, sy, z, tt):
        cx = chair_x
        dd.rectangle((sx(cx - 150), sy(GROUND - 270), sx(cx + 20), sy(GROUND - 250)), fill=(120, 84, 56, 255), outline=(30, 24, 20, 255), width=3)          # chair seat
        dd.rectangle((sx(cx - 150), sy(GROUND - 620), sx(cx - 132), sy(GROUND - 250)), fill=(120, 84, 56, 255), outline=(30, 24, 20, 255), width=3)          # chair back
        dd.rectangle((sx(cx - 140), sy(GROUND - 250), sx(cx - 124), sy(GROUND)), fill=(100, 70, 46, 255))
        dd.rectangle((sx(cx + 10), sy(GROUND - 250), sx(cx + 26), sy(GROUND)), fill=(100, 70, 46, 255))
        dd.rectangle((sx(cx - 700), sy(GROUND - 500), sx(cx - 210), sy(GROUND - 480)), fill=(140, 100, 66, 255), outline=(30, 24, 20, 255), width=3)               # table top
        dd.rectangle((sx(cx - 690), sy(GROUND - 480), sx(cx - 672), sy(GROUND)), fill=(120, 84, 56, 255))
        dd.rectangle((sx(cx - 240), sy(GROUND - 480), sx(cx - 222), sy(GROUND)), fill=(120, 84, 56, 255))
        if tt < t + 1.6:                                                             # the phone on the table
            dd.rectangle((sx(cx - 360), sy(GROUND - 512), sx(cx - 300), sy(GROUND - 500)), fill=(21, 23, 28, 255), outline=(0, 0, 0, 255), width=2)

    def cam_fn(n):
        cx = np.array([x_a + 330 + (x_b - x_a - 200) * min(1.0, max(0.0, i / 30.0 / 5.0)) if i / 30.0 < t_turn + 0.5 else (x_b - 300 - (x_b - 700) * min(1.0, (i / 30.0 - t_turn) / 3.5)) for i in range(n)])
        return dict(cx=cx, cy=np.full(n, GROUND - 520.0), zoom=np.full(n, 0.56 * w / 1280), gain=np.ones(n))

    return _seq_video("human_motion_quality_v3", [(A, seqs[0][1]), (F, seqs[1][1]), (B, seqs[2][1])], dur, w, h, cam_fn, extra, header, log=log)


if __name__ == "__main__":
    import sys
    fns = dict(hands=hand_library_sheet, silhouette=silhouette_test, turnaround=turnaround, motion=human_motion_quality)
    for nm in sys.argv[1:] or list(fns):
        print(nm, fns[nm]())
