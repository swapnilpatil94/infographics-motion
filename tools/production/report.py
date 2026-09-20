"""ACCEPTANCE.json -> docs/production/ACCEPTANCE.md (human-readable evidence)."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    r = json.load(open(os.path.join(ROOT, "output/production/ACCEPTANCE.json")))
    L = ["# Production acceptance", "", f"`python3 studio.py --production-acceptance` — started {r['started']}, total {r['total_seconds']} s", "", "## Verdict", ""]
    for k, v in r["verdict"].items():
        L.append(f"- **{k}**: {'PASS' if v else 'FAIL'}" if k != "ACCEPTED" else f"- **ACCEPTED: {v}**")
    L += ["", "## Stories (story + narration JSON -> final MP4)", "", "| story | film | QC gates | duration | shots | scenes | QC rounds |", "|---|---|---|---|---|---|---|"]
    for t in "ABC":
        s = r["stories"][t]
        L.append(f"| {t}: {s['description']} | `{s['film']}` | {s['gates']} {'PASS' if s['passed'] else 'FAIL ' + str(s['failed_gates'])} | {s['duration_s']} s | {s['shots']} | {s['scenes']} | {len(s['qc_rounds'])} |")
    L += ["", f"materially different: `{r['stories']['materially_different']}`", ""]
    for name in ("determinism", "caching", "failure_modes", "matrix", "regression_original_film", "unit_tests"):
        L += [f"## {name}", "", "```json", json.dumps(r.get(name), ensure_ascii=False, indent=1, default=str)[:3500], "```", ""]
    open(os.path.join(ROOT, "docs/production/ACCEPTANCE.md"), "w", encoding="utf-8").write("\n".join(L))


if __name__ == "__main__":
    main()
