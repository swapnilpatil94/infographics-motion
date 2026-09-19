"""Stage timing for every run: where the wall-clock time goes, per stage and per shot, written next to the video
(timing_log.json) and appended to output/run_history.jsonl so runs can be compared over time."""
import datetime
import json
import os
import subprocess
import time
from contextlib import contextmanager

from engine.shorts.raster import ROOT


class TimeLog:
    def __init__(self):
        self.t0 = time.perf_counter()
        self.started = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
        self.stages = []

    @contextmanager
    def stage(self, name, **meta):
        t = time.perf_counter()
        rec = dict(name=name, seconds=0.0, **meta)
        self.stages.append(rec)
        try:
            yield rec
        finally:
            rec["seconds"] = round(time.perf_counter() - t, 2)

    def add(self, name, seconds, **meta):
        self.stages.append(dict(name=name, seconds=round(seconds, 2), **meta))

    def total(self):
        return round(time.perf_counter() - self.t0, 2)

    def report(self, extra=None):
        tot = self.total() or 1e-9
        rows = [dict(r, pct=round(100 * r["seconds"] / tot, 1)) for r in self.stages]
        return dict(started=self.started, total_seconds=self.total(), stages=rows, **(extra or {}))

    def table(self, rep=None):
        rep = rep or self.report()
        lines = [f"{'stage':<24}{'seconds':>9}{'%':>7}  notes"]
        for r in rep["stages"]:
            note = ", ".join(f"{k}={v}" for k, v in r.items() if k not in ("name", "seconds", "pct"))
            lines.append(f"{r['name']:<24}{r['seconds']:>9.1f}{r['pct']:>7.1f}  {note}")
        lines.append(f"{'TOTAL':<24}{rep['total_seconds']:>9.1f}")
        return "\n".join(lines)


def commit():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    except Exception:
        return ""


def append_history(rep, **meta):
    p = os.path.join(ROOT, "output", "run_history.jsonl")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "a") as f:
        f.write(json.dumps(dict(rep, commit=commit(), **meta), ensure_ascii=False) + "\n")
