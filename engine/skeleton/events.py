"""PRODUCTION EVENTS: structured, machine-readable progress of a production. Nothing here scrapes console text.

The engine calls `current()` (a no-op reporter unless a worker installed a real one, so the CLI and the acceptance suite behave exactly as before) and reports what it is really doing:

    rep.start("blender_render", total_frames=..., ...)   /   rep.progress("blender_render", fraction=.., frame=.., fps=.., eta_seconds=..)   /   rep.complete(...)   /   rep.fail(...)   /   rep.skip(...)

Every event is one JSON line: {seq, ts, event: started|progress|completed|failed|cancelled|skipped|queued|log, stage, status, pass, overall, ...stage fields}. The overall percentage is folded by `State`
from the real state of every stage (completed = 1, running = its measured fraction, pending = 0), weighted by the typical cost of the stage; it never decreases.
"""
import json
import os
import threading
import time
from contextlib import contextmanager

STAGES = [("story_analysis", "Story analysis"), ("story_graph", "Story graph"), ("script", "Script"), ("narration", "Narration"), ("scene_direction", "Scene direction"),
          ("asset_preparation", "Asset preparation"), ("blender_render", "Blender rendering"), ("audio", "Audio"), ("compositing", "Compositing"), ("qc", "QC"), ("export", "Export")]
KSTAGES = [("narration", "Narration"), ("timeline", "Narration timeline"), ("visual_design", "Designing visuals"), ("asset_check", "Checking assets"), ("asset_build", "Creating assets"), ("compile", "Scene plan"),
           ("scene_direction", "Scene direction"), ("asset_preparation", "Asset preparation"), ("blender_render", "Blender rendering"), ("audio", "Audio"), ("compositing", "Compositing"), ("qc", "QC"), ("export", "Export")]
NAMES = dict(STAGES + KSTAGES)
ORDER = [k for k, _ in STAGES]
FLOWS = dict(legacy=ORDER, kplan=["narration", "timeline", "visual_design", "asset_check"], kbuild=["asset_build"], krender=["compile", "scene_direction", "asset_preparation", "blender_render", "audio", "compositing", "qc", "export"])
WEIGHTS = dict(story_analysis=.01, story_graph=.01, script=.01, narration=.05, scene_direction=.08, asset_preparation=.03, blender_render=.20, audio=.03, compositing=.45, qc=.10, export=.02,
               timeline=.05, visual_design=.70, asset_check=.05, asset_build=1.0, compile=.02)
RERENDER = ("asset_preparation", "blender_render", "audio", "compositing", "qc", "export")
ALL_STAGES = [k for k, _ in STAGES] + [k for k, _ in KSTAGES if k not in dict(STAGES)]          # stages that run again in a QC auto-fix pass
TERMINAL = ("completed", "failed", "cancelled")


class State:
    """the state of a production, folded from its events (the same fold runs in the worker and in the server)"""

    def __init__(self):
        self.status = "pending"
        self.overall = 0.0
        self.pass_no = 0
        self.flow = "legacy"
        self.order = list(ORDER)
        self.stages = {k: dict(status="pending", fraction=0.0, seconds=0.0, started=None, message=None, detail={}) for k in ALL_STAGES}
        self.active = None
        self.last = {}
        self.error = None
        self.result = None
        self.seq = 0
        self.t_start = None
        self.t_end = None
        self.passes = [dict(pass_no=0, qc=None, fixes=[])]
        self.cache = {}

    def apply(self, ev):
        self.seq = ev["seq"]
        st, kind = ev.get("stage"), ev["event"]
        if self.t_start is None:
            self.t_start = ev["ts"]
        if st == "job":
            if kind == "started" and ev.get("flow") in FLOWS:
                self.flow, self.order = ev["flow"], list(FLOWS[ev["flow"]])
            if kind in ("started", "queued"):
                self.status = "running" if kind == "started" else "queued"
            elif kind in TERMINAL:
                self.status, self.t_end = kind, ev["ts"]
                self.error = ev.get("error") if kind == "failed" else None
                self.result = ev.get("result")
            return self
        if kind == "new_pass":
            self.pass_no = ev["pass"]
            for k in RERENDER:
                self.stages[k] = dict(status="pending", fraction=0.0, seconds=self.stages[k]["seconds"], started=None, message=None, detail={})
            self.passes.append(dict(pass_no=ev["pass"], qc=None, fixes=ev.get("fixes", [])))
        if st in self.stages:
            s = self.stages[st]
            if kind == "started":
                s.update(status="running", fraction=0.0, started=ev["ts"], message=ev.get("message"))
                self.active = st
            elif kind == "progress":
                if ev.get("fraction") is not None:
                    s["fraction"] = max(s["fraction"], float(ev["fraction"]))
                s["status"] = "running"
                if s["started"] is None:
                    s["started"] = ev["ts"] - (ev.get("elapsed_seconds") or 0.0)
                s["message"] = ev.get("message", s["message"])
                self.active = st
                self.last = {k: v for k, v in ev.items() if k != "seq"}
            elif kind in ("completed", "skipped", "failed", "cancelled"):
                s["status"] = kind
                if kind in ("completed", "skipped"):
                    s["fraction"] = 1.0
                if s["started"] is not None:
                    s["seconds"] = round(s["seconds"] + max(0.0, ev["ts"] - s["started"]), 2)
                s["started"] = None
                s["message"] = ev.get("message") or s["message"]
                s["detail"] = {k: v for k, v in ev.items() if k not in ("seq", "ts", "event", "stage", "status", "pass", "overall")}
                if kind == "failed":
                    self.error = dict(stage=st, **{k: ev.get(k) for k in ("error_type", "error", "traceback") if ev.get(k)})
                if st == "qc" and kind == "completed":
                    self.passes[-1]["qc"] = dict(passed=ev.get("passed"), n_checks=ev.get("n_checks"), failed=ev.get("failed_checks", []))
                if st == "asset_preparation" and kind == "completed" and ev.get("frames"):
                    self.cache = dict(frames=ev.get("frames"), reused=ev.get("cache_reused"), to_render=ev.get("to_render"))
        if kind == "qc_fix":
            self.passes[-1]["fixes"] = ev.get("fixes", [])
        self.overall = max(self.overall, self._overall())
        return self

    def _overall(self):
        if self.status == "completed":
            return 1.0
        names = self.order if self.pass_no == 0 else [k for k in RERENDER if k in self.order]
        tot = sum(WEIGHTS[k] for k in names)
        done = 0.0
        for k in names:
            s = self.stages[k]
            f = 1.0 if s["status"] in ("completed", "skipped") else (s["fraction"] if s["status"] == "running" else 0.0)
            done += WEIGHTS[k] * f
        frac = done / tot
        return round(frac if self.pass_no == 0 else 0.90 + 0.10 * frac, 4)

    def snapshot(self):
        return dict(status=self.status, overall=self.overall, pass_no=self.pass_no, seq=self.seq, active=self.active, last=self.last, error=self.error, result=self.result, cache=self.cache, passes=self.passes,
                    started=self.t_start, ended=self.t_end, flow=self.flow,
                    stages=[dict(id=k, name=NAMES[k], **{f: v for f, v in self.stages[k].items() if f != "detail"}, detail=self.stages[k]["detail"]) for k in self.order])


def fold(events):
    s = State()
    for e in events:
        s.apply(e)
    return s


class Reporter:
    """appends events to a JSONL file (one line per event, flushed) and keeps the folded state"""

    def __init__(self, path=None, sink=None, min_interval=0.25, resume=False):
        self.path, self.sink, self.min_interval = path, sink, min_interval
        self.state = State()
        self.seq = 0
        if resume and path and os.path.exists(path):                                     # continue an existing event file: same numbering, same folded state
            for ev in read(path):
                self.state.apply(ev)
                self.seq = ev["seq"]
        self.t0 = time.time()
        self.stage_t0 = {}
        self._last = {}
        self._lock = threading.Lock()
        self._fh = open(path, "a", buffering=1, encoding="utf-8") if path else None

    def emit(self, event, stage=None, **f):
        with self._lock:
            self.seq += 1
            ev = dict(seq=self.seq, ts=round(time.time(), 3), event=event, stage=stage, **f)
            ev["pass"] = self.state.pass_no if event != "new_pass" else f["pass"]
            if stage and stage != "job" and "status" not in ev:
                ev["status"] = {"started": "running", "progress": "running", "completed": "completed", "failed": "failed", "cancelled": "cancelled", "skipped": "skipped"}.get(event, "running")
            self.state.apply(ev)
            ev["overall"] = self.state.overall
            if self._fh:
                self._fh.write(json.dumps(ev, ensure_ascii=False, default=str) + "\n")
            if self.sink:
                self.sink(ev)
            return ev

    # ---- stage API
    def start(self, stage, message=None, **f):
        self.stage_t0[stage] = time.time()
        self._last.pop(stage, None)
        return self.emit("started", stage, message=message, **f)

    def progress(self, stage, fraction=None, message=None, force=False, **f):
        now = time.time()
        if not force and now - self._last.get(stage, 0.0) < self.min_interval:
            return None
        self._last[stage] = now
        t0 = self.stage_t0.get(stage, now)
        return self.emit("progress", stage, fraction=None if fraction is None else round(min(max(fraction, 0.0), 0.999), 4), message=message, elapsed_seconds=round(now - t0, 2), job_elapsed_seconds=round(now - self.t0, 2), **f)

    def complete(self, stage, message=None, **f):
        t0 = self.stage_t0.get(stage, time.time())
        return self.emit("completed", stage, message=message, elapsed_seconds=round(time.time() - t0, 2), **f)

    def skip(self, stage, reason, **f):
        return self.emit("skipped", stage, message=reason, **f)

    def fail(self, stage, exc=None, message=None, **f):
        import traceback
        err = dict(error_type=type(exc).__name__, error=str(exc)[:1200], traceback="".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-1800:]) if exc is not None else {}
        return self.emit("failed", stage, message=message or (str(exc)[:200] if exc else None), **err, **f)

    def new_pass(self, n, fixes=()):
        return self.emit("new_pass", None, message=f"QC auto-fix pass {n}", fixes=list(fixes), **{"pass": n})

    def log(self, msg, stage=None):
        return self.emit("log", stage or self.state.active, message=str(msg)[:400])

    @contextmanager
    def stage(self, name, message=None, **f):
        """with rep.stage("x", "doing x") as done: ...; done["message"] = "what happened"   (extra keys are stored on the completed event)"""
        self.start(name, message, **f)
        done = {}
        try:
            yield done
        except Exception as e:                                                           # a cancel (BaseException) passes through: the worker reports it as `cancelled`, not `failed`
            self.fail(name, e)
            raise
        else:
            self.complete(name, **done)

    def close(self):
        if self._fh:
            self._fh.close()


@contextmanager
def _nullctx():
    yield {}


class _Null:
    """no reporter installed (CLI, acceptance, unit tests): every call is free and does nothing"""
    state = State()

    def __getattr__(self, name):
        if name == "stage":
            return lambda *a, **k: _nullctx()
        return lambda *a, **k: None


_NULL = _Null()
_current = _NULL


def install(reporter):
    global _current
    _current = reporter or _NULL
    return _current


def current():
    return _current


def read(path, after=0):
    """events of a JSONL file with seq > after (a torn last line is ignored)"""
    out = []
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as fh:
        for ln in fh:
            try:
                ev = json.loads(ln)
            except ValueError:
                continue
            if ev.get("seq", 0) > after:
                out.append(ev)
    return out


def tail(path, offset=0):
    """(events, new_offset): the complete lines written after byte `offset` (a torn last line waits for the next call)"""
    if not os.path.exists(path):
        return [], offset
    with open(path, "rb") as fh:
        fh.seek(offset)
        data = fh.read()
    cut = data.rfind(b"\n")
    if cut < 0:
        return [], offset
    out = []
    for ln in data[:cut + 1].splitlines():
        try:
            out.append(json.loads(ln))
        except ValueError:
            continue
    return out, offset + cut + 1


def shot_index(plan, f):
    """index (0-based) of the shot that frame f belongs to - the same rounding `short.build_camera` uses to assign frames to shots"""
    fps = plan["fps"]
    for i, sh in enumerate(plan["shots"]):
        if int(round(sh["t0"] * fps)) <= f < int(round(sh["t1"] * fps)):
            return i
    return len(plan["shots"]) - 1
