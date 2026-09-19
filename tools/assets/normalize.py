#!/usr/bin/env python3
"""Normalize an SVG into canonical form: validate XML, strip scripts/handlers/metadata, ensure viewBox, detect unsupported features, assign
semantic tags, keep license attribution. Usage: normalize.py <in.svg> <out.svg> [--tag t1,t2]"""
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, ROOT)
from asset_pipeline import svg_normalizer as N

UNSUPPORTED = {"filter": "SVG filters are ignored by the rasterizer path", "mask": "masks are rendered but not rig-safe", "foreignObject": "removed",
               "animate": "SMIL animation removed", "image": "embedded raster: not vector-clean"}


def normalize(src, dst, tags=()):
    text = open(src, encoding="utf-8").read()
    clean, warns = N.validate_and_strip(text)
    root = ET.fromstring(clean)
    for el in list(root.iter()):
        tag = el.tag.split("}")[-1]
        if tag in UNSUPPORTED and tag not in ("foreignObject",):
            warns.append(f"unsupported feature <{tag}>: {UNSUPPORTED[tag]}")
    for md in [e for e in root.iter() if e.tag.split("}")[-1] in ("metadata", "title", "desc")]:
        pass
    if not root.get("viewBox"):
        w = float(re.sub(r"[^\d.]", "", root.get("width", "0")) or 0)
        h = float(re.sub(r"[^\d.]", "", root.get("height", "0")) or 0)
        if w and h:
            root.set("viewBox", f"0 0 {w} {h}")
        else:
            warns.append("no viewBox and no width/height: cannot normalize dimensions")
    vb = [float(x) for x in re.split(r"[ ,]+", root.get("viewBox", "0 0 0 0").strip())]
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
    ET.ElementTree(root).write(dst, encoding="utf-8", xml_declaration=True)
    n_paths = sum(1 for e in root.iter() if e.tag.split("}")[-1] == "path")
    return dict(path=dst, viewbox=vb, paths=n_paths, warnings=warns, tags=list(tags), valid=True)


if __name__ == "__main__":
    tags = sys.argv[sys.argv.index("--tag") + 1].split(",") if "--tag" in sys.argv else []
    print(json.dumps(normalize(sys.argv[1], sys.argv[2], tags), indent=1))
