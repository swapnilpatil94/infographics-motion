"""RGS (CC0 'Free 2D Animated Vector Game Character Sprites') LAB: separate the parts, try them with OUR head/torso/hand and Open Peeps parts, test whether the style can be normalised into our ink language.
    PYTHONPATH=. .venv/bin/python tools/asset_audit/rgs_lab.py -> output/tests/rgs_combination_test.png, docs/asset_audit/rgs_lab.json
The pack is unzipped to a scratch dir (it is 80 MB; nothing is copied into the repo).
"""
import glob
import json
import os
import subprocess
import sys
import tempfile

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from engine.skeleton import lab, lab_dna as LD, normalize as NZ, dna2   # noqa: E402

ZIP = os.path.join(ROOT, "assets/raw/rgs/free_2d_animated_vector_game_character_sprites.zip")
OUT = os.path.join(ROOT, "output/tests")


def unzip():
    d = os.path.join(tempfile.gettempdir(), "rgs_unzipped")
    if not os.path.isdir(d):
        subprocess.run(["unzip", "-q", "-o", ZIP, "-d", d], check=True)
    return glob.glob(os.path.join(d, "*", "Animated body parts"))[0]


def part(base, rel, frame="idle_0"):
    im = Image.open(os.path.join(base, rel, frame + ".png")).convert("RGBA")
    return im.crop(im.getbbox())


def stats(im):
    """style metrics of an RGBA sprite: rim thickness relative to the part size, distinct luminance tones inside the fill, gloss (near-white blobs inside a mid-tone fill), palette size"""
    a = np.asarray(im)
    al = a[..., 3] > 128
    ys, xs = np.where(al)
    size = float(np.sqrt((xs.max() - xs.min() + 1) * (ys.max() - ys.min() + 1)))
    sw = NZ.stroke_width_px(a)
    lum = a[..., :3].astype(float).mean(axis=2)
    inner = al & (lum > 60)
    tones = len(np.unique((lum[inner] // 24).astype(int))) if inner.any() else 0
    gloss = bool(((lum > 245) & al).sum() > 0.004 * al.sum() and tones >= 3)
    cols = len({tuple((p // 40).tolist()) for p in a[al][:: max(1, al.sum() // 3000), :3]})
    return dict(part_px=round(size), rim_px=None if sw is None else round(sw, 1), rim_ratio=None if sw is None else round(sw / size, 3), tones=tones, gloss=gloss, colours=cols)


def normalise(im, skin=(198, 134, 92), ink=(12, 8, 8), rim_ratio=0.03):
    """flatten the cel shading to ONE fill tone, redraw a thin uniform rim at our stroke ratio (silhouette rim only: interior ink details are dropped)"""
    a = np.asarray(im).copy()
    al = (a[..., 3] > 128).astype(np.uint8)
    ys, xs = np.where(al)
    size = np.sqrt((xs.max() - xs.min() + 1) * (ys.max() - ys.min() + 1))
    k = max(2, int(rim_ratio * size))
    er = cv2.erode(al, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * k + 1, 2 * k + 1)))
    out = np.zeros_like(a)
    out[al > 0] = (*ink, 255)
    out[er > 0] = (*skin, 255)
    return Image.fromarray(out)


def scaled(im, h):
    return im.resize((max(1, int(im.width * h / im.height)), h), Image.LANCZOS)


def main():
    base = unzip()
    dna = LD.production_characters()["A"]
    bald = dna2.make("rgs:bald", "young_man", {"hair.style": "No Hair 1", "hair.length": "bald", "facial_hair": "* None", "glasses": "* None"})
    ims, meta = lab.render_specs([dict(label="ours", dna=dna, focus="body"), dict(label="bald", dna=bald, focus="body")], os.path.join(OUT, "audit_work/rgs"), samples=8, return_meta=True)
    parts = dict(head1=part(base, "Heads/head1"), head3=part(base, "Heads/head3"), hair1=part(base, "Hairs/hair1"), hair2=part(base, "Hairs/hair2"), eyes5=part(base, "Eyes/eyes5"), eyes6=part(base, "Eyes/eyes6"),
                 mouth1=part(base, "Mouths/mouth1"), mouth4=part(base, "Mouths/mouth4"), handR=part(base, "Right hands/handR1"), body1=part(base, "Bodies/body1"), footR=part(base, "Right feet/footR1"))
    skin = tuple(int(dna["skin"]["hex"][i:i + 2], 16) for i in (1, 3, 5))

    def screen(m, pt):
        wx, wy = m["actor"].rig_to_world(*pt)
        return (wx - m["cx"]) * m["zoom"] + 540, (wy - m["cy"]) * m["zoom"] + 960

    def head_box(m):
        a = m["actor"]
        hx, hy = screen(m, (0, 0)) if False else (None, None)
        wx, wy = a.anchor("head", m["t"])
        sx, sy = (wx - m["cx"]) * m["zoom"] + 540, (wy - m["cy"]) * m["zoom"] + 960
        return sx, sy, a.P["head"] * m["zoom"]

    def paste(base_img, spr, cx, cy, h):
        s = scaled(spr, int(h))
        base_img.alpha_composite(s, (int(cx - s.width / 2), int(cy - s.height / 2)))

    def canvas(i):
        c = Image.new("RGBA", (1080, 1920), (238, 235, 228, 255))
        c.alpha_composite(Image.fromarray(ims[i]))
        return c

    tests = []
    for norm in (False, True):
        f = (lambda s, **k: normalise(s, skin=skin, **k)) if norm else (lambda s, **k: s)
        # T1 RGS head + our torso
        c = canvas(0)
        hx, hy, hh = head_box(meta[0])
        paste(c, f(parts["head1"]), hx, hy - 10, hh * 1.25)
        paste(c, parts["eyes5"], hx + 20, hy, hh * 0.20)
        tests.append(("T1 RGS head + our torso", norm, c, (hx, hy, hh)))
        # T2 RGS hair + Open Peeps (bald) head
        c = canvas(1)
        hx, hy, hh = head_box(meta[1])
        paste(c, f(parts["hair1"], ) if not norm else normalise(parts["hair1"], skin=(60, 40, 30)), hx - 5, hy - hh * 0.28, hh * 0.75)
        tests.append(("T2 RGS hair + Open Peeps head", norm, c, (hx, hy, hh)))
        # T3 RGS hand + our arm
        c = canvas(0)
        m = meta[0]
        a = m["actor"]
        wx, wy = a.anchor("hip", m["t"])
        sh = a.perf.shoulder(m["t"])
        wrist = (a.perf.v("hand_R_x", m["t"]), a.perf.v("hand_R_y", m["t"]))
        sx, sy = screen(m, wrist)
        paste(c, f(parts["handR"]), sx, sy + 30, 95 * m["zoom"])
        tests.append(("T3 RGS hand + our arm", norm, c, (sx, sy, 95)))
        # T5 RGS eyes + mouth on the Open Peeps head
        c = canvas(1)
        hx, hy, hh = head_box(meta[1])
        paste(c, parts["eyes6"], hx + 18, hy - hh * 0.02, hh * 0.24)
        paste(c, parts["mouth4"], hx + 24, hy + hh * 0.26, hh * 0.09)
        tests.append(("T5 RGS eyes+mouth + Open Peeps head", norm, c, (hx, hy, hh)))
    # sheet
    cw, ch = 300, 400
    S = Image.new("RGB", (5 * cw + 20, 5 * ch + 130), (30, 30, 34))
    d = ImageDraw.Draw(S)
    d.text((10, 8), "RGS lab.  Row 1: raw RGS parts.  Rows 2-3: RGS parts combined with OUR rig / Open Peeps (raw, then normalised to our ink language).  T4 (RGS clothing): none exists.", fill=(235, 235, 235), font=lab.font(15, True))
    x = 0
    for name in ("head1", "head3", "hair1", "eyes6", "handR"):
        im = parts[name].copy()
        bg = Image.new("RGBA", (cw - 4, ch - 4), (238, 235, 228, 255))
        s = scaled(im, min(ch - 60, 300))
        s.thumbnail((cw - 20, ch - 60))
        bg.alpha_composite(s, ((bg.width - s.width) // 2, 20))
        S.paste(bg.convert("RGB"), (x * cw + 2, 40))
        d.text((x * cw + 8, 44 + ch - 24), f"RGS {name}", fill=(20, 20, 20), font=lab.font(14))
        x += 1
    row = 1
    for norm in (False, True):
        for i, (title, n, c, (hx, hy, hh)) in enumerate([t for t in tests if t[1] == norm]):
            crop = c.crop((int(hx - 330), int(hy - 300), int(hx + 330), int(hy + 480 if "T3" not in title else hy + 380))).convert("RGB")
            crop.thumbnail((cw - 8, ch - 40))
            S.paste(crop, (i * cw + 4, 40 + (row) * ch + 4))
            d.text((i * cw + 8, 40 + row * ch + ch - 30), f"{title} {'[normalised]' if n else '[raw]'}", fill=(235, 235, 235), font=lab.font(12))
        row += 1
    S.crop((0, 0, S.width, 40 + 3 * ch + 8)).save(os.path.join(OUT, "rgs_combination_test.png"))
    # style metrics: RGS raw vs normalised vs our own head/torso/hand
    ours = {}
    man = json.load(open(os.path.join(ROOT, __import__("engine.skeleton.parts_art2", fromlist=["x"]).bake2(dna, "three_quarter", "full")["dir"], "parts.json")))
    for nm in ("torso", "hand_R_relaxed", "skull"):
        pth = os.path.join(ROOT, man["parts"][nm]["png"])
        ours[f"own {nm}"] = stats(Image.open(pth).convert("RGBA"))
    ours["Open Peeps head (composed bust)"] = stats(lab.Image.fromarray(ims[0]).crop((300, 60, 800, 420)).convert("RGBA")) if False else None
    metr = {"RGS head1 (raw)": stats(parts["head1"]), "RGS head1 (normalised)": stats(normalise(parts["head1"], skin=skin)), "RGS hair1 (raw)": stats(parts["hair1"]), "RGS handR (raw)": stats(parts["handR"]),
            "RGS eyes6 (raw)": stats(parts["eyes6"]), **{k: v for k, v in ours.items() if v}}
    verdict = {
        "head": "UNUSABLE as a head: a bare sphere with a 10 % rim and cel gloss; after normalising it is a plain circle (no expression, no neck, no ears, no hair slot) - Open Peeps heads are strictly better",
        "hair": "UNUSABLE: tufts/mushroom shapes for monsters; no coherent hair for people",
        "eyes": "PARTLY USABLE as eye-state references only: eyes5 (plain dots) / eyes6 (glossy) - our editorial eye already covers this; no gain",
        "mouths": "REFERENCE: 8 simple mouth curves (mouth1-4 are ink strokes that fit our style); weaker than the Open Peeps face atoms",
        "hands": "UNUSABLE: a solid black blob without fingers",
        "body": "UNUSABLE: a pill-shaped torso without arms; feet solid black",
        "clothing": "none exists in the pack",
        "animation": "42 frames per part (idle/walk/roll/hit/death...) on registered 2048 px canvases: a clean sprite-sheet pipeline, but frame-by-frame raster: incompatible with our IK rig"}
    json.dump(dict(pack="RGS free_2d_animated_vector_game_character_sprites (CC0)", parts_available=dict(bodies=1, heads=3, hairs=3, eyes=7, mouths=8, horns=5, hands=2, feet=2, wings=2, weapons=3, frames_per_part=42, canvas="2048x2048"),
                   style_metrics=metr, verdict=verdict, tests=[dict(name=t[0], normalised=t[1]) for t in tests]), open(os.path.join(ROOT, "docs/asset_audit/rgs_lab.json"), "w"), indent=1)
    print(json.dumps(metr, indent=1))


if __name__ == "__main__":
    main()
