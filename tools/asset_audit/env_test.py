"""ENVIRONMENT COVERAGE: can the full-body skeleton actors be placed in every environment family we have? One still per family (character A standing, then seated) through the real compositor.
    PYTHONPATH=. .venv/bin/python tools/asset_audit/env_test.py -> output/tests/environment_coverage.png, docs/asset_audit/environment_coverage.json
"""
import json
import os
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from engine.environments import bedroom_wide as BW, factory as EF   # noqa: E402
from engine.skeleton import lab, lab_dna as LD, short   # noqa: E402

OUT = os.path.join(ROOT, "output/tests")
FAMILIES = ["bedroom_wide", "study_room", "bank_branch", "call_centre", "indian_living_room", "atm_area", "office_day", "street_dusk", "night_bedroom"]


def plan_for(family, start):
    dna = LD.production_characters()["A"]
    cast = {"A": dict(name="A", dna=dna, facing=1, origin=[540.0, BW.FLOOR_Y], view="three_quarter", hand_set="full", start=start, start_x=0.0)}
    sh = [dict(id="S01", treatment="skeleton", t0=0.0, t1=2.0, beats=[], segs=[], gp=[], transition_in="cut", sfx=[], phase="-", location="x", purpose="env", camera=dict(target="A.full", size="full", move="hold"),
               lighting=dict(mood="dim", moon=1.0, phone=0.0), actions=[dict(char="A", action="idle", t=0.0, dur=2.0)])]
    return dict(kind="skeleton_short", version=3, title="env", story_id="env", seed=3, fps=30, format=dict(w=1080, h=1920, name="9x16"), duration=2.0, name="env", environment=dict(family=family, variation=dict(palette=0), seed=0),
                characters=cast, cast_in_short=["A"], narration=dict(segments=[], audio=None, tts="none", tempo=1.0), targets=dict(PHONE=[670.0, 1166.0], nightstand_phone=[670.0, 1166.0]), shots=sh, sfx=[],
                mood_track=[(0.0, 2.0, "dim")], rim=dict(moon=0.0), duration_range=[0, 99])


def main():
    cells, notes = [], {}
    for fam in FAMILIES:
        for start in ("stand", "sit"):
            try:
                r = short.render_stills(plan_for(fam, start), os.path.join(OUT, f"audit_work/env/{fam}_{start}"), [1.0], lambda *_: None, samples=6, with_captions=False)
                cells.append((fam, start, Image.open(r["paths"][0]).convert("RGB")))
            except Exception as e:
                cells.append((fam, start, None))
                notes[f"{fam}/{start}"] = f"{type(e).__name__}: {e}"[:160]
    W, H = 270, 480
    S = Image.new("RGB", (len(FAMILIES) * W, 2 * H + 50), (30, 30, 34))
    d = ImageDraw.Draw(S)
    d.text((10, 8), "ENVIRONMENT COVERAGE: the same full-body character in every set we have (top: standing, bottom: seated)", fill=(235, 235, 235), font=lab.font(16, True))
    for i, (fam, start, im) in enumerate(cells):
        x, y = (i // 2) * W, 36 + (i % 2) * H
        if im is not None:
            S.paste(im.resize((W - 4, H - 24)), (x + 2, y))
        d.text((x + 6, y + H - 22), f"{fam} / {start}", fill=(235, 235, 235), font=lab.font(13))
    S.save(os.path.join(OUT, "environment_coverage.png"))
    json.dump(dict(families=FAMILIES, errors=notes), open(os.path.join(ROOT, "docs/asset_audit/environment_coverage.json"), "w"), indent=1)
    print(notes)


if __name__ == "__main__":
    main()
