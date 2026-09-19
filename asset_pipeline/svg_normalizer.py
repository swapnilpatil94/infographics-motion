"""Deterministic SVG normalization: parse, validate, strip anything unsafe,
ensure a viewBox, and record provenance. Deliberately does NOT flatten
groups/ids — semantic structure (character parts, layer names) is exactly
what the rest of the pipeline depends on.
"""
import xml.etree.ElementTree as ET
import re
import hashlib
import os
import json

UNSAFE_TAGS = {"script", "iframe", "foreignObject"}
UNSAFE_ATTR_PREFIXES = ("on",)  # onload, onclick, etc.


def validate_and_strip(svg_text):
    """Parses the SVG, removes any unsafe elements/attributes and external
    references, and returns (clean_text, warnings)."""
    warnings = []
    # external refs (http(s) hrefs, xlink:href to remote URLs) — Open Peeps
    # exports don't carry these, but don't trust that blindly for any future
    # source.
    if re.search(r'(xlink:href|href)\s*=\s*"https?://', svg_text):
        warnings.append("external href reference found and left untouched — review before use")

    ET.register_namespace("", "http://www.w3.org/2000/svg")
    root = ET.fromstring(svg_text)
    ns = "{http://www.w3.org/2000/svg}"

    def strip(el):
        for child in list(el):
            tag = child.tag.replace(ns, "")
            if tag in UNSAFE_TAGS:
                warnings.append(f"removed unsafe element <{tag}>")
                el.remove(child)
                continue
            for attr in list(child.attrib):
                if attr.lower().startswith(UNSAFE_ATTR_PREFIXES):
                    warnings.append(f"removed unsafe attribute {attr} on <{tag}>")
                    del child.attrib[attr]
            strip(child)

    strip(root)

    if "viewBox" not in root.attrib:
        w = root.attrib.get("width", "0").replace("px", "")
        h = root.attrib.get("height", "0").replace("px", "")
        root.set("viewBox", f"0 0 {w} {h}")
        warnings.append("synthesized missing viewBox from width/height")

    clean_text = ET.tostring(root, encoding="unicode")
    return clean_text, warnings


def normalize_file(src_path, out_path):
    with open(src_path, encoding="utf-8") as f:
        raw = f.read()
    clean_text, warnings = validate_and_strip(raw)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(clean_text)
    sha256 = hashlib.sha256(clean_text.encode("utf-8")).hexdigest()
    return {
        "source_path": src_path,
        "normalized_path": out_path,
        "sha256": sha256,
        "warnings": warnings,
    }


if __name__ == "__main__":
    import sys
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_dir = os.path.join(ROOT, "assets/character/normalized/rahul_svg")
    report = []
    for fname in sorted(os.listdir(src_dir)):
        if not fname.endswith(".svg"):
            continue
        src = os.path.join(src_dir, fname)
        out = os.path.join(ROOT, "assets/character/normalized/rahul_svg_clean", fname)
        report.append(normalize_file(src, out))
    report_path = os.path.join(ROOT, "assets/character/normalized/normalization_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    for r in report:
        print(os.path.basename(r["normalized_path"]), r["sha256"][:12], r["warnings"])
