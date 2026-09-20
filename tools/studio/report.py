"""docs/studio/E2E_RESULTS.json (+ docs/production/ACCEPTANCE.json) -> docs/studio/RESULTS.md"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
R = json.load(open(os.path.join(ROOT, "docs/studio/E2E_RESULTS.json")))
A = json.load(open(os.path.join(ROOT, "docs/production/ACCEPTANCE.json")))
L = ["# Studio UI - test evidence", "", "Every row below is a REAL run through the HTTP API the browser uses (worker subprocess, Blender, ffmpeg, Chatterbox); raw data in `E2E_RESULTS.json`.", "",
     "| scenario | production | QC | duration | Blender frames rendered / reused | total | notes |", "|---|---|---|---|---|---|---|"]
for k, v in R.items():
    if "qc" not in v or "cache" not in v:
        continue
    c = v["cache"]
    note = []
    if v.get("qc_failed"):
        note.append("FAILED: " + ", ".join(x.split("_(")[0] for x in v["qc_failed"]))
    if v.get("requested", {}) and v["requested"].get("duration"):
        note.append(f"requested ~{v['requested']['duration']} s")
    if v.get("director"):
        note.append("director " + json.dumps(v["director"]))
    if v.get("captions") is False:
        note.append("captions off")
    if v.get("narration_cache_hit"):
        note.append("narration cache hit")
    if v.get("files_16x9"):
        note.append("16:9 export")
    if k == "create_mode":
        note.append(f"real Chatterbox TTS {v['timings']['narration']} s")
    L.append(f"| {k} | `{v['production']}` | {v['qc']} | {v['duration']} s | {c.get('rendered')} / {c.get('reused')} ({c.get('reuse_pct')}% reused) | {v['timings']['total']} s | {'; '.join(note)} |")
L += ["", "## Cancel (real Blender render)", "", "```json", json.dumps(R.get("cancel_real_blender"), ensure_ascii=False, indent=1), "```", "", "## Failed render (Blender path missing)", "", "```json",
      json.dumps(R.get("failed_render_blender_missing"), ensure_ascii=False, indent=1), "```", "", "## Production acceptance (`python3 studio.py --production-acceptance`, run after the Studio changes)", ""]
v = A["verdict"]
L += [f"* verdict: **{'ACCEPTED' if v['ACCEPTED'] else 'NOT ACCEPTED'}** - " + ", ".join(f"{k}={'ok' if x else 'FAIL'}" for k, x in v.items() if k != "ACCEPTED"),
      "* stories: " + ", ".join(f"{t} {A['stories'][t]['gates']}" for t in "ABC"), f"* determinism: {A['determinism']['identical_frames']}/{A['determinism']['sampled_frames']} sampled frames identical",
      f"* caching: camera change {A['caching']['camera']['frames_changed']}/{A['caching']['camera']['frames_total']} frames (all in shot {A['caching']['camera']['shot']}); audio change {A['caching']['audio']['video_frames_changed']} video frames",
      f"* regression: original film {A['regression_original_film']['gates']}", f"* unit tests: {A['unit_tests']['ran']} ran, {A['unit_tests']['failures']} failures, {A['unit_tests']['errors']} errors", ""]
open(os.path.join(ROOT, "docs/studio/RESULTS.md"), "w").write("\n".join(L))
print("\n".join(L[:20]))
