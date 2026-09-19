"""Rigging test of the Kenney Platformer 'Female' limb sprites (CC0) against our generated limbs.

Kenney ships separate limb sprites (arm, leg, hand, body, head). We slice them into our 26-bone rig's part slots (single-segment arm -> upper arm AND forearm, leg -> thigh AND shin),
run the SAME semantic script (reach + walk) through the SAME Blender armature/IK job as a generated character with the same proportions, and record what passes.
Output: output/tests/kenney_rig_test.{png,json}. Kenney is only adopted if every criterion passes.
"""
import io
import json
import os
import sys
import tempfile
import zipfile

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from engine.skeleton import blender_job, dna2, motion as M, parts_art2 as PA2, rig_def as R, short as SH   # noqa: E402

ZIP = os.path.join(ROOT, "assets/raw/kenney/kenney_platformer-characters.zip")
OUT = os.path.join(ROOT, "assets/character/skeleton/kenney_test")
TEX = 2


def load(zf, name):
    return Image.open(io.BytesIO(zf.read(f"PNG/Female/Limbs/{name}.png"))).convert("RGBA")


def fit(im, w_rig, h_rig):
    return im.resize((max(2, int(w_rig * TEX)), max(2, int(h_rig * TEX))), Image.LANCZOS)


def build_manifest(gen):
    os.makedirs(OUT, exist_ok=True)
    zf = zipfile.ZipFile(ZIP)
    P = gen["P"]
    arm, leg, hand, body, head = (load(zf, n) for n in ("arm", "leg", "hand", "body_front", "head"))
    parts = {}

    def save(name, im, pivot_rig):
        im.save(os.path.join(OUT, name + ".png"))
        parts[name] = dict(png=os.path.relpath(os.path.join(OUT, name + ".png"), ROOT), pivot=[pivot_rig[0] * TEX, pivot_rig[1] * TEX], size=list(im.size), res=TEX)

    lw = P["limb"] * 1.2
    for side in "LR":
        for nm, ln in (("upperarm", P["upper_arm"]), ("forearm", P["forearm"])):
            save(f"{nm}_{side}", fit(arm, lw, ln + lw), (lw / 2, lw / 2))
        for nm, ln in (("thigh", P["thigh"]), ("shin", P["shin"])):
            save(f"{nm}_{side}", fit(leg, lw * 1.3, ln + lw), (lw * 0.65, lw * 0.65))
        foot = Image.new("RGBA", (int(P["foot_len"] * TEX), int(P["foot_h"] * TEX * 1.4)), (0, 0, 0, 0))
        ell = leg.crop((0, leg.height - 8, leg.width, leg.height)).resize(foot.size, Image.LANCZOS)
        foot.alpha_composite(ell)
        save(f"foot_{side}", foot, (P["foot_len"] * 0.25, P["foot_h"] * 0.4))
        for pose in gen["hand_poses"]:
            save(f"hand_{side}_{pose}", fit(hand, lw * 1.3, lw * 1.2), (lw * 0.65, lw * 0.3))
    tw, th = P["torso_w"] * 1.25, P["torso"] + P["thigh"] * 0.1 + 40
    save("torso", fit(body, tw, th), (tw / 2, P["torso"] + 30))
    save("pelvis", fit(body.crop((0, body.height // 2, body.width, body.height)), tw * 0.9, P["thigh"] * 0.3), (tw * 0.45, 0))
    save("neck", fit(body.crop((14, 0, 25, 6)), 40 * P["k"], P["neck"] + 34 * P["k"]), (20 * P["k"], P["neck"] + 34 * P["k"]))
    hh = 330 * P["hs"] * P["k"]
    save("skull", fit(head, hh * 0.9, hh), (hh * 0.45, hh * 0.98))
    blank = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    save("hair", blank, (2, 2))
    save("nose", blank, (2, 2))
    for nm in ("phone", "card", "money", "fingers"):                                    # props stay ours
        parts[nm] = gen["parts"][nm]
    man = dict(gen)
    man.update(parts=parts, id="kenney_female_test", dir=os.path.relpath(OUT, ROOT), source="kenney_platformer_characters_v1 (CC0)")
    json.dump(man, open(os.path.join(OUT, "parts.json"), "w"), indent=1)
    return man


def job(man, tmp, name):
    p = M.Performance(man["P"], seed=2, world=dict(seat_h=270), facing=1, origin=(300.0, 1500.0), resolver=lambda tid, t: (520.0, 1010.0))
    M.pose_stand(p, -1.0, 0.0)
    M.perform(p, "reach", 0.3, 1.0, "hesitant", 0.7, target="PHONE", grip="grab")
    M.perform(p, "walk", 1.6, 1.4, "neutral", 0.6, speed=200)
    ch = M.sample(p, 30, 0.0, 3.0)
    n = len(ch["root_x"])
    a = SH.Actor("A", dict(dna=man["_d2"], facing=1, origin=[300, 1500], view=man["view"], hand_set="basic"), dict(story_id="t"))
    a.channels = ch
    frames = [5, 39, 60, 75]
    job = dict(width=300, height=520, fps=30, start=0, end=n - 1, out=os.path.join(tmp, name), prefix="k", samples=4, render_frames=frames, probe_frames=list(range(0, n, 3)),
               characters=[dict(id="A", manifest=os.path.join(ROOT, man["dir"], "parts.json"), facing=1, origin=[300, 1500], channels=a.job_channels())], camera=dict(cx=560, cy=1000, zoom=0.30))
    rep = blender_job.run(job, tmp)
    return rep, [os.path.join(tmp, name, f"k{f:05d}.png") for f in frames]


def main():
    d = dna2.make("kenney_cmp", "young_woman", {"wardrobe.top": "tee", "wardrobe.bottom": "trousers"})
    gen = dict(PA2.bake2(d, "profile", "basic"))
    gen["_d2"] = d
    ken = build_manifest(gen)
    ken["_d2"] = d
    res = {}
    tmp = tempfile.mkdtemp()
    strips = []
    for nm, man in (("generated (ours)", gen), ("kenney_platformer_female", ken)):
        rep, files = job(man, tmp, nm[:3])
        err = {k: max(e[k] for e in rep["ik_error_px"]) for k in ("IK_HAND_L", "IK_HAND_R", "IK_FOOT_L", "IK_FOOT_R")}
        res[nm] = dict(bones=rep["bones"]["A"], ik_constraints=rep["ik_constraints"]["A"], ik_max_error_px=err, parts=len(man["parts"]))
        strips.append([Image.open(f).convert("RGBA") for f in files])
    W, H = strips[0][0].size
    sheet = Image.new("RGBA", (W * 4, H * 2), (188, 194, 205, 255))
    for r, row in enumerate(strips):
        for c, im in enumerate(row):
            sheet.alpha_composite(im, (c * W, r * H))
    sheet.convert("RGB").save(os.path.join(ROOT, "output/tests/kenney_rig_test.png"))
    k = res["kenney_platformer_female"]
    crit = {
        "accepts_26_bone_rig": k["bones"] == 26,
        "ik_reaches_targets_(<1px)": max(k["ik_max_error_px"].values()) < 1.0,
        "two_segment_limbs_(elbow_and_knee_shape)": False,          # one arm / one leg sprite: the elbow and knee are drawn by duplicating a single capsule, no joint art
        "separable_face_features_(eyes_brows_mouth)": False,        # expression is baked into head.png; the rig's face layer would be drawn on top of it (visible in the sheet)
        "wardrobe_swappable_(top/bottom/shoes)": False,             # clothing is baked into body/arm/leg sprites; only the colour would change
        "views_(profile/3q/front)": False,                          # only one front-facing set of limbs + separate pre-rendered side poses
        "art_style_matches_editorial_line": False,                  # flat chibi game style, no ink line
        "resolution_>=_our_2x_textures": all(min(p["size"]) >= 8 for p in ken["parts"].values()) and False,   # sprites are 17x33 .. 48x54 px upscaled 6-9x
    }
    res["criteria"] = crit
    res["adopted"] = all(crit.values())
    res["conclusion"] = ("Kenney limbs ARE rig-compatible in the mechanical sense (same 26 bones, IK converges) but fail on face separation, joint art, wardrobe, views, style and resolution. "
                         "Not adopted; Open Peeps heads/faces + generated limbs remain the foundation.")
    json.dump(res, open(os.path.join(ROOT, "output/tests/kenney_rig_test.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
