"""ONE CHARACTER, MANY PLACES: production character A in bedroom / office / bank / street / ATM (a cafe does not exist) x 6 situations through the real compositor, with an identity check
(hue histogram of the character's own pixels, lighting-independent, compared across all stills).
    PYTHONPATH=. .venv/bin/python tools/asset_audit/identity_test.py -> output/tests/one_character_many_situations.png, docs/asset_audit/identity_test.json
"""
import colorsys
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from engine.environments import bedroom_wide as BW   # noqa: E402
from engine.skeleton import lab, lab_dna as LD, parts_art2 as PA2, short   # noqa: E402

OUT = os.path.join(ROOT, "output/tests")
PLACES = [("bedroom", "bedroom_wide", "night"), ("office", "office_day", "day"), ("bank", "bank_branch", "day"), ("street", "street_dusk", "dusk"), ("ATM at night", "atm_area", "night")]
LIGHT = {"night": dict(mood="dim", moon=1.0, phone=0.6), "day": dict(mood="neutral", moon=0.0, phone=0.2, sun=0.9), "dusk": dict(mood="neutral", moon=0.0, phone=0.2, sun=0.6)}
SITS = [("standing", "stand", [dict(action="idle", t=0.0, dur=2.4), dict(action="look_ahead", t=0.2, dur=1.0)]),
        ("sitting", "sit", [dict(action="idle", t=0.0, dur=2.4)]),
        ("walking", "stand", [dict(action="walk_to", t=0.0, dur=2.4, target="A_STOP", stop_before=0.0, fill=True, stride_scale=0.8)]),
        ("phone reading", "stand", [dict(action="reach", t=0.0, dur=0.7, target="PHONE", grip="hold_phone"), dict(action="grab", t=0.8, dur=0.1, prop="phone", from_table=True),
                                    dict(action="hold_phone", t=1.0, dur=1.4, pos="chest"), dict(action="read_phone", t=1.2, dur=1.2)]),
        ("talking", "stand", [dict(action="speak", t=0.2, dur=2.0), dict(action="gesture", t=0.4, dur=1.8, hand="R")]),
        ("fear", "stand", [dict(action="fear", t=0.1, dur=1.8, emotion="fearful", intensity=0.85), dict(action="face_atom", t=0.5, dur=1.4, name="fear")])]


def hue_hist(rgba, bins=24):
    a = rgba[rgba[..., 3] > 200][:, :3] / 255.0
    if len(a) > 20000:
        a = a[:: len(a) // 20000]
    hs = [colorsys.rgb_to_hsv(*p) for p in a]
    h = np.array([x[0] for x in hs if x[1] > 0.25 and x[2] > 0.25])
    hist = np.histogram(h, bins=bins, range=(0, 1))[0].astype(float)
    return hist / max(hist.sum(), 1)


def main():
    dna = LD.production_characters()["A"]
    PA2.bake_face_atoms(dna, "three_quarter", ["fear"])
    cells, hists = [], []
    for pname, fam, light in PLACES:
        t = 0.0
        shots, actions = [], []
        for i, (sname, start, acts) in enumerate(SITS):
            pass
        # one plan per (place, situation): start pose differs (sit/stand), so render each separately
        for sname, start, acts in SITS:
            cast = {"A": dict(name="A", dna=dna, facing=1, origin=[420.0 if fam != "atm_area" else 300.0, BW.FLOOR_Y], view="three_quarter", hand_set="full", start=start, start_x=0.0)}
            actions = [dict(char="A", **a) for a in acts]
            sh = [dict(id="S01", treatment="skeleton", t0=0.0, t1=2.6, beats=[], segs=[], gp=[], transition_in="cut", sfx=[], phase="-", location=pname, purpose=sname, camera=dict(target="A.full", size="full", move="hold"),
                       lighting=LIGHT[light], actions=actions)]
            plan = dict(kind="skeleton_short", version=3, title="id", story_id="id", seed=3, fps=30, format=dict(w=1080, h=1920, name="9x16"), duration=2.6, name="id", environment=dict(family=fam, variation=dict(palette=0), seed=0),
                        characters=cast, cast_in_short=["A"], narration=dict(segments=[], audio=None, tts="none", tempo=1.0), targets=dict(PHONE=[720.0, 1150.0], nightstand_phone=[720.0, 1150.0], A_STOP=[860.0, BW.FLOOR_Y]),
                        shots=sh, sfx=[], mood_track=[(0.0, 2.6, "dim")], rim=dict(moon=0.0), duration_range=[0, 99])
            tt = 1.9 if sname in ("phone reading", "walking") else 1.0
            try:
                r = short.render_stills(plan, os.path.join(OUT, f"audit_work/identity/{fam}_{sname.replace(' ', '_')}"), [tt], lambda *_: None, samples=6, with_captions=False)
                img = Image.open(r["paths"][0]).convert("RGB")
                fdir = os.path.join(OUT, f"audit_work/identity/{fam}_{sname.replace(' ', '_')}/work_preview/actor_frames")
                fr = np.asarray(Image.open(os.path.join(fdir, f"a{int(round(tt * 30)):05d}.png")).convert("RGBA"))
                hists.append(hue_hist(fr))
            except Exception as e:
                img = None
                print("ERR", fam, sname, e)
            cells.append((pname, sname, img))
    W, H = 216, 384
    S = Image.new("RGB", (len(SITS) * W, len(PLACES) * H + 48), (30, 30, 34))
    d = ImageDraw.Draw(S)
    d.text((10, 8), f"ONE CHARACTER (DNA {dna['id']}) in 5 places x 6 situations, same rig / same grammar. A cafe set does not exist.", fill=(235, 235, 235), font=lab.font(16, True))
    for i, (pname, sname, img) in enumerate(cells):
        x, y = (i % len(SITS)) * W, 40 + (i // len(SITS)) * H
        if img is not None:
            S.paste(img.resize((W - 3, H - 20)), (x + 1, y))
        d.text((x + 5, y + H - 18), f"{pname} / {sname}", fill=(235, 235, 235), font=lab.font(12))
    S.save(os.path.join(OUT, "one_character_many_situations.png"))
    sims = [float(np.minimum(hists[i], hists[j]).sum()) for i in range(len(hists)) for j in range(i + 1, len(hists))]
    json.dump(dict(dna_id=dna["id"], places=[p[0] for p in PLACES], situations=[s[0] for s in SITS], stills=len(cells), hue_histogram_overlap=dict(min=round(min(sims), 3), mean=round(float(np.mean(sims)), 3)),
                   note="hue-histogram overlap of the character's own pixels between every pair of stills (1.0 = identical colour identity); lighting-independent by construction. Identity is by construction (one DNA); this measures that the render keeps it."),
              open(os.path.join(ROOT, "docs/asset_audit/identity_test.json"), "w"), indent=1)
    print(round(min(sims), 3), round(float(np.mean(sims)), 3))


if __name__ == "__main__":
    main()
