"""OPEN PEEPS ATLAS: every atom of the Open Peeps library we actually have is parsed, rendered, measured and put through the real composition path (asset_pipeline.cast_builder._compose).

    PYTHONPATH=. .venv/bin/python tools/asset_audit/openpeeps_atlas.py

Writes docs/asset_audit/openpeeps_atoms.json (one record per atom: source svg, normalised svg, components, bbox, stroke width, fills, anchors, rig compatibility, production use) and
output/tests/openpeeps_asset_contact_sheet.png (every atom, composed on the same bust, border colour = verdict).
"""
import io
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

import numpy as np
import resvg_py
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from asset_pipeline import cast_builder as cb, compose_character as cc   # noqa: E402
from engine.characters import dna as D1                                   # noqa: E402
from engine.skeleton import dna2, normalize as NZ                         # noqa: E402

ATOMS = os.path.join(ROOT, "assets/character/raw/open_peeps/extracted/Flat Assets/Separate Atoms")
TEMPL = os.path.join(ROOT, "assets/character/raw/open_peeps/extracted/Flat Assets/Templates")
NORM = os.path.join(ROOT, "assets/library/openpeeps_normalized")
OUT_JSON = os.path.join(ROOT, "docs/asset_audit/openpeeps_atoms.json")
OUT_PNG = os.path.join(ROOT, "output/tests/openpeeps_asset_contact_sheet.png")
CATS = ["head", "face", "facial-hair", "accessories", "body", "a person", "pose/standing", "pose/sitting"]
USED_HEADS = set(dna2.FEM_HAIR | dna2.MASC_HAIR | {"Gray Medium"})
ANCHOR_DOC = dict(head="neck_anchor = bottom-centre of the ink bbox; hair_top = top of bbox", face="eye_centre / mouth_centre = ink centroids of the upper / lower half",
                  **{"facial-hair": "chin_anchor = bottom-centre of the ink bbox"}, accessories="bridge = centre of the ink bbox (glasses sit on the nose bridge)", body="shoulder_left/right ~ top corners of the bbox; hand_extremes = ink extremes",
                  **{"a person": "whole bust / sitting / standing template with the head, face, body groups replaceable"})


def render(svg_text, width=None, zoom=None):
    kw = dict(svg_string=svg_text)
    if zoom:
        kw["zoom"] = zoom
    elif width:
        kw["width"] = width
    return Image.open(io.BytesIO(bytes(resvg_py.svg_to_bytes(**kw)))).convert("RGBA")


def svg_dims(root_el):
    vb = root_el.get("viewBox")
    if vb:
        _, _, w, h = (float(v) for v in vb.split())
        return w, h
    return float(re.sub(r"[^0-9.]", "", root_el.get("width", "0")) or 0), float(re.sub(r"[^0-9.]", "", root_el.get("height", "0")) or 0)


def parse(path):
    txt = open(path, encoding="utf-8").read()
    root = ET.fromstring(txt)
    ns = "{http://www.w3.org/2000/svg}"
    paths = [e for e in root.iter() if e.tag in (ns + "path", "path")]
    d_all = [p.get("d", "") for p in paths]
    sub = sum(len(re.findall(r"[Mm]", d)) for d in d_all)
    closed = sum(len(re.findall(r"[Zz]", d)) for d in d_all)
    fills = sorted({(p.get("fill") or "").upper() for p in paths if (p.get("fill") or "") not in ("", "none")})
    strokes = sorted({(p.get("stroke") or "").upper() for p in paths if (p.get("stroke") or "") not in ("", "none")})
    tops = [g.get("id") for g in root.iter() if g.tag in (ns + "g", "g") and g.get("id")]
    w, h = svg_dims(root)
    return dict(width=w, height=h, viewBox=root.get("viewBox"), n_paths=len(paths), n_subpaths=sub, closed_subpaths=closed, fill_colours=fills, stroke_colours=strokes, group_ids=tops[:6],
                n_group_ids=len(tops), has_ink_group=any("Ink" in (t or "") for t in tops), has_background_group=any("Background" in (t or "") for t in tops)), txt


def measure(img):
    a = np.asarray(img)
    al = a[..., 3] > 8
    if not al.any():
        return dict(bbox=None)
    ys, xs = np.where(al)
    bbox = [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]
    sw = NZ.stroke_width_px(a)
    lum = a[..., :3].astype(float).mean(axis=2)
    ink = (al & (lum < 110)).sum()
    cols = len({tuple((px // 32).tolist()) for px in a[al][:: max(1, al.sum() // 4000), :3]})
    return dict(bbox=bbox, ink_stroke_px=None if sw is None else round(float(sw), 2), ink_coverage=round(float(ink) / max(al.sum(), 1), 3), colours_quantised=cols)


def anchors(cat, bbox, img):
    if not bbox:
        return {}
    x0, y0, x1, y1 = bbox
    a = np.asarray(img)
    lum = a[..., :3].astype(float).mean(axis=2)
    ink = (a[..., 3] > 8) & (lum < 110)
    if cat == "head":
        return dict(neck_anchor=[(x0 + x1) // 2, y1], hair_top=[(x0 + x1) // 2, y0])
    if cat == "face":
        ys, xs = np.where(ink)
        mid = (y0 + y1) / 2
        up, lo = ys < mid, ys >= mid
        c = lambda m: [int(xs[m].mean()), int(ys[m].mean())] if m.any() else None
        return dict(eye_centre=c(up), mouth_centre=c(lo))
    if cat == "facial-hair":
        return dict(chin_anchor=[(x0 + x1) // 2, y1])
    if cat == "accessories":
        return dict(bridge=[(x0 + x1) // 2, (y0 + y1) // 2])
    if cat in ("body", "pose/standing", "pose/sitting", "a person"):
        return dict(shoulder_left=[x0 + int(0.15 * (x1 - x0)), y0], shoulder_right=[x1 - int(0.15 * (x1 - x0)), y0], extent=[x0, y0, x1, y1])
    return {}


def composed(cat, name):
    """Run the atom through the production composition path on the same default bust -> RGBA image (or None + error)."""
    try:
        if cat == "head":
            doc, _, _ = cb._compose(name, "* None", "* None", "Serious", "Tee 1")
        elif cat == "face":
            doc, _, _ = cb._compose("Short 1", "* None", "* None", name, "Tee 1")
        elif cat == "facial-hair":
            doc, _, _ = cb._compose("Short 1", name, "* None", "Serious", "Tee 1")
        elif cat == "accessories":
            doc, _, _ = cb._compose("Short 1", "* None", name, "Serious", "Tee 1")
        elif cat == "body":
            doc, _, _ = cb._compose("Short 1", "* None", "* None", "Serious", name)
        else:
            return None, "not composable (whole-figure atom)"
        return render(doc, width=360), None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"[:120]


def production_use(cat, name):
    """Static reachability in the production vocabulary (DNA v2) - the runtime proof is docs/asset_audit/usage_trace.json."""
    if cat == "head":
        return "reachable" if name in USED_HEADS else "unreachable (not in dna2 hair vocabulary)"
    if cat == "face":
        return "base-only (Serious is composed under our own procedural face; the atom's expression is NOT used)"
    if cat == "facial-hair":
        return "reachable" if name in ("* None", "Moustache 1", "Moustache 2", "Full", "Chin") else "unreachable (dna2 only picks 5 of 17)"
    if cat == "accessories":
        return "reachable" if name in ("* None", "Glasses") else "unreachable (dna2 only emits Glasses)"
    if cat == "body":
        return "Tee 1 only as the composition base; the arm/torso art is NOT used (own-work limbs); 'Device' hand harvested"
    if cat == "a person":
        return "bust.svg used as composition base"
    return "not used (whole-figure illustration)"


def verdict(cat, rec, err):
    if err and "not composable" not in err:
        return "UNUSABLE", err
    if cat == "head":
        return ("COMPONENT" if rec["production"] == "reachable" else "COMPONENT (tested, unreachable)"), "composes cleanly on the bust; closed contours" if rec["closed_ratio"] >= 0.95 else "composes; some open subpaths"
    if cat == "face":
        return "FACE (replacement-drawing candidate)", "same coordinate system as the head: swaps in over any Open Peeps head"
    if cat == "facial-hair":
        return "COMPONENT", "composes on any head"
    if cat == "accessories":
        return "COMPONENT", "composes on any head"
    if cat == "body":
        return "REFERENCE (hand harvest candidate)", "torso+arm+hands are one ink silhouette: only raster hand harvesting is possible"
    if cat == "a person":
        return "FOUNDATION", "composition base"
    return "REFERENCE ONLY", "whole illustrated figure: not separable into rig parts"


def font(sz=13):
    for p in ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Helvetica.ttc"):
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def main():
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    os.makedirs(os.path.dirname(OUT_PNG), exist_ok=True)
    recs, thumbs = [], []
    for cat in CATS:
        d = os.path.join(ATOMS, cat)
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".svg"):
                continue
            name = fn[:-4]
            p = os.path.join(d, fn)
            info, txt = parse(p)
            img_native = render(txt, width=min(int(info["width"]), 700) or 400)
            m = measure(img_native)
            scale = img_native.width / max(info["width"], 1)
            if m.get("ink_stroke_px") is not None:
                m["ink_stroke_svg_units"] = round(m["ink_stroke_px"] / scale, 2)
            comp, err = composed(cat, name)
            rec = dict(category=cat, name=name, source_svg=os.path.relpath(p, ROOT), **info, **m, anchors=anchors(cat, m.get("bbox"), img_native))
            rec["closed_ratio"] = round(rec["closed_subpaths"] / max(rec["n_subpaths"], 1), 3)
            rec["production"] = production_use(cat, name)
            rec["composes"] = comp is not None
            rec["compose_error"] = err
            rec["class"], rec["why"] = verdict(cat, rec, err)
            rec["rig_compatibility"] = dict(head="hair/head slot of the 3-view head (used)", face="face slot (own procedural face is drawn instead)", **{"facial-hair": "head slot"}, accessories="head slot",
                                            body="none (own limbs are generated)", **{"a person": "composition base", "pose/standing": "none", "pose/sitting": "none"})[cat]
            # normalised copy for the components we can put in the factory (same crop + padding, ink as-is: the atoms already ARE the ink language)
            if cat in ("head", "face", "facial-hair", "accessories"):
                nd = os.path.join(NORM, cat.replace("/", "_"))
                os.makedirs(nd, exist_ok=True)
                npth = os.path.join(nd, fn)
                bb = m["bbox"]
                if bb:
                    pad = 6
                    x0, y0, x1, y1 = (v / scale for v in bb)
                    vb = f"{x0 - pad:.1f} {y0 - pad:.1f} {x1 - x0 + 2 * pad:.1f} {y1 - y0 + 2 * pad:.1f}"
                    open(npth, "w", encoding="utf-8").write(re.sub(r'viewBox="[^"]+"', f'viewBox="{vb}"', re.sub(r'width="[^"]+"', f'width="{x1 - x0 + 2 * pad:.0f}px"', re.sub(r'height="[^"]+"', f'height="{y1 - y0 + 2 * pad:.0f}px"', txt, count=1), count=1), count=1))
                    rec["normalized_svg"] = os.path.relpath(npth, ROOT)
            recs.append(rec)
            thumbs.append((cat, name, comp if comp is not None else img_native, rec))
    # ---- contact sheet
    cw, chh, cols, hdr = 150, 168, 14, 34
    sheets = []
    rows_by_cat = {}
    for t in thumbs:
        rows_by_cat.setdefault(t[0], []).append(t)
    total_rows = sum((len(v) + cols - 1) // cols for v in rows_by_cat.values())
    S = Image.new("RGB", (cols * cw, total_rows * chh + len(rows_by_cat) * hdr + 60), (24, 24, 28))
    dr = ImageDraw.Draw(S)
    dr.text((10, 8), f"Open Peeps: every atom we have ({len(recs)}) composed on the same bust through the production path.  green = reachable in the factory, amber = tested but unused, blue = reference/whole figure, red = fails", fill=(230, 230, 230), font=font(15))
    y = 40
    col = {"reachable": (70, 200, 110), "unused": (230, 170, 60), "ref": (90, 150, 230), "bad": (230, 80, 70)}
    for cat, items in rows_by_cat.items():
        dr.text((10, y + 6), f"{cat.upper()}  ({len(items)})", fill=(255, 255, 255), font=font(17))
        y += hdr
        for i, (c_, name, im, rec) in enumerate(items):
            x0, y0 = (i % cols) * cw, y + (i // cols) * chh
            im2 = im.copy()
            im2.thumbnail((cw - 8, chh - 32))
            bg = Image.new("RGB", (cw - 6, chh - 6), (244, 242, 236))
            bg.paste(im2, ((bg.width - im2.width) // 2, 2), im2)
            k = "bad" if not rec["composes"] and rec["class"] == "UNUSABLE" else "ref" if rec["class"].startswith(("REFERENCE", "FOUNDATION")) else "reachable" if rec["production"].startswith(("reachable", "base-only", "Tee", "bust")) else "unused"
            S.paste(bg, (x0 + 3, y0 + 3))
            dr.rectangle((x0 + 3, y0 + 3, x0 + cw - 4, y0 + chh - 4), outline=col[k], width=3)
            dr.text((x0 + 6, y0 + chh - 24), name[:22], fill=(235, 235, 235), font=font(12))
        y += ((len(items) + cols - 1) // cols) * chh
    S.crop((0, 0, S.width, y + 6)).save(OUT_PNG)
    summary = {c: dict(n=sum(1 for r in recs if r["category"] == c), composes=sum(1 for r in recs if r["category"] == c and r["composes"]),
                       reachable=sum(1 for r in recs if r["category"] == c and str(r["production"]).startswith(("reachable", "base-only"))),
                       mean_stroke_svg_units=round(float(np.mean([r["ink_stroke_svg_units"] for r in recs if r["category"] == c and r.get("ink_stroke_svg_units")] or [0])), 2)) for c in CATS}
    tcount = {t: len([f for f in os.listdir(os.path.join(TEMPL, t)) if f.endswith(".svg")]) for t in os.listdir(TEMPL) if os.path.isdir(os.path.join(TEMPL, t))}
    json.dump(dict(anchor_definitions=ANCHOR_DOC, summary=summary, templates_svg_counts=tcount, atoms=recs), open(OUT_JSON, "w"), ensure_ascii=False, indent=1)
    print(json.dumps(summary, indent=1))
    print("templates", tcount, "->", OUT_JSON, OUT_PNG)


if __name__ == "__main__":
    main()
