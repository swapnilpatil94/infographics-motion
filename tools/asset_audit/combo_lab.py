"""COMBINATION LAB: 50 structurally distinct characters + 15 archetypes + 3 production characters, all on the SAME rig, rendered through the real Blender pipeline.

    PYTHONPATH=. .venv/bin/python tools/asset_audit/combo_lab.py
-> output/tests/asset_combination_50.png (+ _front), output/tests/archetypes_15.png, output/tests/production_characters_3.png, docs/asset_audit/combination_lab.json
Distinctness is measured on STRUCTURE (12 axes, colour never counts) and verified on the RENDERED silhouettes (pairwise IoU of height-normalised masks).
"""
import json
import os
import sys
import time

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from engine.skeleton import lab, lab_dna as LD, dna2   # noqa: E402

OUT = os.path.join(ROOT, "output/tests")
WORK = os.path.join(ROOT, "output/tests/audit_work/combo")


def silhouette(rgba, h=160):
    a = lab.crop_char(rgba, pad=0)[..., 3] > 40
    ys, xs = np.where(a)
    a = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    im = Image.fromarray((a * 255).astype(np.uint8))
    w = max(1, int(im.width * h / im.height))
    m = np.zeros((h, 120), bool)
    m[:, :min(w, 120)] = np.asarray(im.resize((w, h)))[:, :120] > 127
    return m


def main():
    os.makedirs(WORK, exist_ok=True)
    t0 = time.time()
    cands = LD.pool(420, "lab50")
    chosen, rep = LD.select_distinct(cands, 50, min_axes=5)
    print("selected", rep)
    specs = [dict(label=f"{i + 1:02d} {d['role'][:14]}", dna=d, view="three_quarter", t=1.0) for i, d in enumerate(chosen)]
    ims = lab.render_specs(specs, WORK, samples=8)
    lab.sheet(ims, [s["label"] for s in specs], os.path.join(OUT, "asset_combination_50.png"), cols=10, cell=(236, 480), title=f"50 structurally distinct characters, one rig (three-quarter view). Min {rep['min_axes_differing']} of 12 structural axes differ between ANY two; colour never counts.")
    fs = [dict(s, view="front") for s in specs]
    fims = lab.render_specs(fs, WORK + "_front", samples=8)
    lab.sheet(fims, [s["label"] for s in specs], os.path.join(OUT, "asset_combination_50_front.png"), cols=10, cell=(236, 480), title="Same 50 characters, front view")
    # rendered-silhouette distinctness
    sil = [silhouette(i) for i in ims]
    iou = np.zeros((50, 50))
    for i in range(50):
        for j in range(50):
            iou[i, j] = (sil[i] & sil[j]).sum() / max((sil[i] | sil[j]).sum(), 1)
    off = iou[~np.eye(50, dtype=bool)]
    per_pair = [LD.distance(LD.features(chosen[i]), LD.features(chosen[j])) for i in range(50) for j in range(i + 1, 50)]
    # archetypes
    arche = {n: LD.archetype(n) for n in LD.ARCHETYPES}
    aims = lab.render_specs([dict(label=n, dna=d, view="three_quarter") for n, d in arche.items()], WORK + "_arch", samples=8)
    lab.sheet(aims, list(arche), os.path.join(OUT, "archetypes_15.png"), cols=8, cell=(236, 480), title="15 archetypes from the existing library (same rig, same grammar)")
    prod = LD.production_characters()
    pims = lab.render_specs([dict(label=f"Character {k}", dna=d, view="three_quarter") for k, d in prod.items()] + [dict(label=f"Character {k} (front)", dna=d, view="front") for k, d in prod.items()], WORK + "_prod", samples=8)
    lab.sheet(pims, [f"Character {k}" for k in prod] + [f"Character {k} (front)" for k in prod], os.path.join(OUT, "production_characters_3.png"), cols=3, cell=(300, 620), title="Production characters A (young male), B (middle-aged female), C (young female)")
    heads = sorted({d["hair"]["style"] for d in chosen})
    js = dict(selection=rep, pool=len(cands), rendered_silhouette_iou=dict(mean=round(float(off.mean()), 3), max=round(float(off.max()), 3), pairs_iou_gt_0_85=int((off > 0.85).sum() // 2)),
              axes_differing_percentiles={p: int(np.percentile(per_pair, p)) for p in (0, 5, 25, 50, 75, 100)},
              characters=[dict(n=i + 1, id=d["id"], role=d["role"], age=d["age"], hair=d["hair"]["style"], facial_hair=d["facial_hair"], glasses=d["glasses"], silhouette=d["silhouette"], top=d["wardrobe"]["top"], bottom=d["wardrobe"]["bottom"],
                               shoes=d["wardrobe"]["shoes"], accessories=d["wardrobe"]["accessories"], eyes=d["eyes"], brows=d["eyebrows"], mouth=d["mouth"]) for i, d in enumerate(chosen)],
              atoms_used=dict(hair_heads=len(heads), facial_hair=len({d["facial_hair"] for d in chosen}), glasses=len({d["glasses"] for d in chosen}), tops=len({d["wardrobe"]["top"] for d in chosen}),
                              bottoms=len({d["wardrobe"]["bottom"] for d in chosen}), shoes=len({d["wardrobe"]["shoes"] for d in chosen}), silhouettes=len({d["silhouette"] for d in chosen})),
              archetypes={n: dict(id=d["id"], role=d["role"]) for n, d in arche.items()}, production={k: d["id"] for k, d in prod.items()}, seconds=round(time.time() - t0, 1))
    json.dump(js, open(os.path.join(ROOT, "docs/asset_audit/combination_lab.json"), "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in js.items() if k not in ("characters", "archetypes")}, indent=1))


if __name__ == "__main__":
    main()
