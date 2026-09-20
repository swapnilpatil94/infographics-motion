"""STAGE TEST: every semantic location x every allowed time of day, the same character standing (and seated where the stage has a seat), through the real compositor with the time-consistent lighting preset.
    PYTHONPATH=. .venv/bin/python tools/production/stage_test.py -> output/production/stage_matrix.png + docs/production/stage_matrix.json
"""
import json
import os
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from engine.environments import bedroom_wide as BW, locations as LOC   # noqa: E402
from engine.skeleton import lab, lab_dna as LD, lighting_presets as LP, short   # noqa: E402

OUT = os.path.join(ROOT, "output/production")


def plan_for(loc, start):
    dna = LD.production_characters()["A"]
    lay = loc["layout"]
    x = lay["seat_x"] if (start == "sit" and lay.get("seat_x")) else (lay["A_stop"] if lay["A_stop"] > 0 else 500.0)
    cast = {"A": dict(name="A", dna=dna, facing=1, origin=[x, BW.FLOOR_Y], view="three_quarter", hand_set="full", start=start, start_x=0.0)}
    lt = LP.preset(loc["time"], "dim")
    sh = [dict(id="S01", treatment="skeleton", t0=0.0, t1=2.0, beats=[], segs=[], gp=[], transition_in="cut", sfx=[], phase="-", location=loc["name"], purpose="stage", camera=dict(target="A.full", size="full", move="hold"),
               lighting=lt, environment=dict(family=loc["family"], variation=dict(palette=0, time=loc["time"]), seed=0), actions=[dict(char="A", action="idle", t=0.0, dur=2.0)])]
    return dict(kind="skeleton_short", version=3, title="stage", story_id="stage", seed=3, fps=30, format=dict(w=1080, h=1920, name="9x16"), duration=2.0, name="stage", environment=sh[0]["environment"],
                characters=cast, cast_in_short=["A"], narration=dict(segments=[], audio=None, tts="none", tempo=1.0), targets=dict(PHONE=list(lay["phone"]), nightstand_phone=list(lay["phone"])), shots=sh, sfx=[],
                mood_track=[(0.0, 2.0, "dim")], rim=dict(moon=0.5), duration_range=[0, 99])


def main():
    cells, meta = [], []
    for name in LOC.ALL:
        for tm in LOC.LOCATIONS[name][1]:
            loc = LOC.resolve(name, tm)
            for start in (("stand", "sit") if loc["layout"].get("sit") else ("stand",)):
                r = short.render_stills(plan_for(loc, start), os.path.join(OUT, f"stage/{name}_{tm}_{start}"), [1.0], lambda *_: None, samples=6, with_captions=False)
                cells.append((f"{name} / {tm} / {start}", Image.open(r["paths"][0]).convert("RGB")))
                meta.append(dict(location=name, family=loc["family"], time=tm, start=start))
    W, H = 216, 384
    cols = 8
    rows = (len(cells) + cols - 1) // cols
    S = Image.new("RGB", (cols * W, rows * H + 30), (24, 24, 28))
    d = ImageDraw.Draw(S)
    d.text((8, 8), f"STAGE MATRIX: {len(cells)} location x time x pose stills, time-consistent lighting + sky", fill=(235, 235, 235), font=lab.font(15, True))
    for i, (lab_, im) in enumerate(cells):
        S.paste(im.resize((W - 2, H - 16)), ((i % cols) * W, 30 + (i // cols) * H))
        d.text(((i % cols) * W + 4, 30 + (i // cols) * H + H - 15), lab_, fill=(235, 235, 235), font=lab.font(11))
    os.makedirs(os.path.join(ROOT, "docs/production"), exist_ok=True)
    S.save(os.path.join(OUT, "stage_matrix.png"))
    json.dump(meta, open(os.path.join(ROOT, "docs/production/stage_matrix.json"), "w"), indent=1)
    print(len(cells))


if __name__ == "__main__":
    main()
