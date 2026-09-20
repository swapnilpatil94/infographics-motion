"""PRODUCTION USAGE TRACE. An asset counts as USED only if the production pipeline really reads it. This runs the current production path (topic story -> auto-director plan -> cold-cache character bake ->
Blender rig + 2.5D compositor stills incl. an insert-UI and a procedural shot) with every file-open instrumented, and writes the list of asset files that were opened.

    PYTHONPATH=. .venv/bin/python tools/asset_audit/trace_usage.py [--out docs/asset_audit/usage_trace.json]

Instrumented: builtins.open (audit hook), cv2.imread, PIL.Image.open, PIL.ImageFont.truetype, resvg_py.svg_to_bytes(svg_path=..), numpy.load. Character caches are redirected to a scratch dir so that the RAW atoms are read
(otherwise a warm cache would hide the source atoms). Blender's own reads are the generated part textures; provenance raw atom -> part is recorded in parts.json.
"""
import argparse
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
OPENED = {}
SCOPE = ("assets/", "narration/", "domains/")


def _note(p, how):
    try:
        p = os.path.relpath(os.path.abspath(str(p)), ROOT)
    except Exception:
        return
    if p.startswith(SCOPE):
        OPENED.setdefault(p, set()).add(how)


def install():
    def hook(ev, args):
        if ev == "open" and args and isinstance(args[0], (str, bytes, os.PathLike)) and not isinstance(args[0], int):
            try:
                mode = args[1] if len(args) > 1 else "r"
                if mode is None or "w" not in str(mode):
                    _note(args[0], "open")
            except Exception:
                pass
    sys.addaudithook(hook)
    import cv2
    from PIL import Image, ImageFont
    import resvg_py
    o_imread, o_open, o_tt, o_svg = cv2.imread, Image.open, ImageFont.truetype, resvg_py.svg_to_bytes

    def imread(p, *a, **k):
        _note(p, "cv2.imread")
        return o_imread(p, *a, **k)

    def iopen(fp, *a, **k):
        if isinstance(fp, (str, os.PathLike)):
            _note(fp, "PIL.open")
        return o_open(fp, *a, **k)

    def tt(font=None, *a, **k):
        if isinstance(font, (str, os.PathLike)):
            _note(font, "truetype")
        return o_tt(font, *a, **k)

    def svg(*a, **k):
        if k.get("svg_path"):
            _note(k["svg_path"], "resvg")
        return o_svg(*a, **k)
    cv2.imread, Image.open, ImageFont.truetype, resvg_py.svg_to_bytes = imread, iopen, tt, svg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "docs/asset_audit/usage_trace.json"))
    a = ap.parse_args()
    install()
    scratch = tempfile.mkdtemp(prefix="trace_cache_")
    from engine.characters import dna as D1
    from engine.skeleton import parts_art2 as PA2, topic_story as TS, topic_build as TB, auto_director as AD, short
    D1.GEN_DIR = os.path.join(scratch, "heads")
    PA2.GEN = os.path.join(scratch, "parts")
    story = TS.write("fake WhatsApp investment group", use_llm=False)
    plan = AD.build_plan(story, TB.draft_narration(story), name="usage_trace")
    TB.bake_cast(plan)
    times = []
    for tr in ("skeleton", "insert_ui", "procedural"):
        sh = next(s for s in plan["shots"] if s["treatment"] == tr)
        times.append(round(sh["t0"] + 0.6 * (sh["t1"] - sh["t0"]), 2))
    short.render_stills(plan, os.path.join(scratch, "stills"), times, lambda *_: None)
    out = {p: sorted(h) for p, h in sorted(OPENED.items())}
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump(dict(scenario="topic story 'fake WhatsApp investment group' -> plan -> cold bake of 2 characters -> 3 composited stills (skeleton / insert_ui / procedural)", files=out,
                   parts_manifests=[os.path.relpath(os.path.join(dp, f), scratch) for dp, _, fs in os.walk(scratch) for f in fs if f == "parts.json"]), open(a.out, "w"), indent=1)
    print(len(out), "asset files opened ->", a.out)


if __name__ == "__main__":
    main()
