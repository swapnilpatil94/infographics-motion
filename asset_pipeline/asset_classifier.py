"""Classifies a raw SVG file's asset_type/style from its path and content —
heuristic, not ML, and deliberately simple: the corpus here is small and
well-named enough that keyword rules are more auditable than a model.
"""
import os
import re

TYPE_KEYWORDS = {
    "character": ["person", "pose", "head", "face", "body", "facial-hair", "hand", "arm"],
    "environment": ["wall", "window", "curtain", "floor", "bed_edge", "room"],
    "prop": ["phone", "nightstand", "lamp", "pillow", "table"],
    "effect": ["ray", "particle", "spark", "glow", "ink"],
}


def classify_type(path):
    lower = path.lower()
    for asset_type, keywords in TYPE_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return asset_type
    return "unknown"


def classify_style(svg_text):
    """Very rough: count distinct fill colors used. Open Peeps ink art uses
    exactly 2 (white background shape + black ink) — anything with more
    distinct fills reads as 'multicolor' rather than 'ink'."""
    fills = set(re.findall(r'fill="(#[0-9A-Fa-f]{3,6}|[a-zA-Z]+)"', svg_text))
    fills.discard("none")
    if len(fills) <= 2:
        return "ink_linework"
    if len(fills) <= 6:
        return "flat_limited_palette"
    return "multicolor_illustration"


def classify_file(path):
    with open(path, encoding="utf-8", errors="ignore") as f:
        text = f.read()
    return {
        "path": path,
        "asset_type": classify_type(path),
        "style": classify_style(text),
    }


if __name__ == "__main__":
    import sys
    for p in sys.argv[1:]:
        print(classify_file(p))
