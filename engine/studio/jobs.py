"""JOB MANAGER: productions run as worker subprocesses (`engine.studio.worker`), one at a time (Blender + ffmpeg saturate the machine; the frame cache is shared), the rest wait in a queue.

A production is a folder  output/studio/productions/<id>/  holding job.json (the request), events.jsonl (the structured event log = the single source of truth for status), worker.log and the film.
The state of a production is always FOLDED FROM ITS EVENT LOG (`events.fold`), so it survives a server restart and is the same thing the live SSE stream shows.
"""
import json
import os
import signal
import subprocess
import sys
import threading
import time
import uuid

from engine.shorts.raster import ROOT
from engine.skeleton import events as EVT
from engine.studio import core as C

PY = os.environ.get("STUDIO_PYTHON") or os.path.join(ROOT, ".venv/bin/python")
if not os.path.exists(PY):
    PY = sys.executable


def pdir(pid):
    if not pid or not all(c.isalnum() or c in "_-" for c in pid):
        raise C.StudioError("unknown_production", f"unknown production '{pid}'", status=404)
    return os.path.join(C.PRODS, pid)


def _events_path(pid):
    return os.path.join(pdir(pid), "events.jsonl")


class Manager:
    def __init__(self, max_running=1, test_mode=False):
        self.max_running = max_running
        self.test_mode = test_mode
        self.procs = {}
        self.queue = []
        self.lock = threading.RLock()
        self._stop = threading.Event()
        os.makedirs(C.PRODS, exist_ok=True)
        self._recover()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    # ------------------------------------------------------------------ submit / run / cancel
    def submit(self, job, parent=None):
        pid = "p_" + time.strftime("%Y%m%d-%H%M%S") + "_" + uuid.uuid4().hex[:4]
        d = pdir(pid)
        os.makedirs(d, exist_ok=True)
        job = dict(job, id=pid, parent=parent)
        json.dump(job, open(os.path.join(d, "job.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        with self.lock:
            rep = EVT.Reporter(path=_events_path(pid), resume=True)
            if len(self.procs) >= self.max_running:
                self.queue.append(pid)
                rep.emit("queued", "job", message=f"waiting for {len(self.procs)} running production(s)", position=len(self.queue), title=job.get("title"), mode=job["mode"])
            else:
                self._start(pid)
            rep.close()
        return pid

    def _start(self, pid):
        d = pdir(pid)
        env = dict(os.environ, PYTHONPATH=ROOT, PYTHONUNBUFFERED="1")
        if self.test_mode:
            env["KATHAYA_STUDIO_TEST"] = "1"
        log = open(os.path.join(d, "worker.log"), "a")
        p = subprocess.Popen([PY, "-u", "-m", "engine.studio.worker", d], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        open(os.path.join(d, "worker.pid"), "w").write(str(p.pid))
        self.procs[pid] = p

    def cancel(self, pid):
        d = pdir(pid)
        if not os.path.isdir(d):
            raise C.StudioError("unknown_production", f"unknown production '{pid}'", status=404)
        with self.lock:
            st = self.state(pid)
            if st["status"] in ("completed", "failed", "cancelled"):
                raise C.StudioError("not_running", f"the production already {st['status']}", status=409)
            rep = EVT.Reporter(path=_events_path(pid), resume=True)
            if pid in self.queue:
                self.queue.remove(pid)
                rep.emit("cancelled", "job", message="cancelled while waiting in the queue")
                rep.close()
                return self.state(pid)
            proc = self.procs.get(pid)
            pgid = proc.pid if proc else self._pid_file(pid)
        if pgid:
            try:
                os.killpg(pgid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
            for _ in range(60):                                                             # the worker writes its own `cancelled` events, then kills its whole group
                time.sleep(0.1)
                if not self._alive(pid, proc, pgid):
                    break
            else:
                try:
                    os.killpg(pgid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
        with self.lock:
            self._reap(pid)
            st = self.state(pid)
            if st["status"] not in ("completed", "failed", "cancelled"):
                rep = EVT.Reporter(path=_events_path(pid), resume=True)
                rep.emit("cancelled", "job", message="cancelled by the user")
                rep.close()
            return self.state(pid)

    # ------------------------------------------------------------------ monitor
    def _pid_file(self, pid):
        try:
            return int(open(os.path.join(pdir(pid), "worker.pid")).read())
        except (OSError, ValueError):
            return None

    def _alive(self, pid, proc=None, pgid=None):
        if proc is not None:
            return proc.poll() is None
        pgid = pgid or self._pid_file(pid)
        if not pgid:
            return False
        try:
            os.kill(pgid, 0)
            return True
        except (ProcessLookupError, PermissionError):
            return False

    def _reap(self, pid):
        proc = self.procs.pop(pid, None)
        if proc is not None:
            proc.poll()

    def _loop(self):
        while not self._stop.wait(0.5):
            try:
                self.tick()
            except Exception:                                                               # noqa: BLE001 - the monitor must never die
                pass

    def tick(self):
        with self.lock:
            for pid, proc in list(self.procs.items()):
                if proc.poll() is None:
                    continue
                st = self.state(pid)
                if st["status"] not in ("completed", "failed", "cancelled"):                # the worker died without a terminal event (killed, crashed, out of memory)
                    rep = EVT.Reporter(path=_events_path(pid), resume=True)
                    act = rep.state.active
                    err = dict(stage=act, type="WorkerExited", message=f"the production process exited unexpectedly (exit code {proc.returncode}); see worker.log", reasons=[], hint="Look at worker.log in the production folder.")
                    if act and rep.state.stages[act]["status"] == "running":
                        rep.emit("failed", act, message=err["message"], error_type="WorkerExited", error=err["message"])
                    rep.emit("failed", "job", message=err["message"], error=err)
                    rep.close()
                self.procs.pop(pid, None)
            while self.queue and len(self.procs) < self.max_running:
                self._start(self.queue.pop(0))

    def _recover(self):
        """after a server restart: productions that were running / queued and are not alive any more are marked failed (never left 'running' forever)"""
        for pid in sorted(os.listdir(C.PRODS)) if os.path.isdir(C.PRODS) else []:
            ep = os.path.join(C.PRODS, pid, "events.jsonl")
            if not os.path.exists(ep):
                continue
            st = EVT.fold(EVT.read(ep))
            if st.status in ("running", "queued") and not self._alive(pid):
                rep = EVT.Reporter(path=ep, resume=True)
                msg = "the studio server restarted while this production was " + st.status
                act = rep.state.active
                if act and rep.state.stages[act]["status"] == "running":
                    rep.emit("failed", act, message=msg, error_type="ServerRestart", error=msg)
                rep.emit("failed", "job", message=msg, error=dict(stage=act, type="ServerRestart", message=msg, reasons=[], hint="Start it again; frames already rendered are in the frame cache."))
                rep.close()

    def shutdown(self):
        self._stop.set()

    # ------------------------------------------------------------------ queries
    def state(self, pid):
        if not os.path.exists(os.path.join(pdir(pid), "job.json")):
            raise C.StudioError("unknown_production", f"unknown production '{pid}'", status=404)
        s = EVT.fold(EVT.read(_events_path(pid)))
        snap = s.snapshot()
        snap["id"] = pid
        if snap["status"] == "queued" and pid in self.queue:
            snap["queue_position"] = self.queue.index(pid) + 1
        snap["now"] = time.time()
        return snap

    def job(self, pid):
        p = os.path.join(pdir(pid), "job.json")
        if not os.path.exists(p):
            raise C.StudioError("unknown_production", f"unknown production '{pid}'", status=404)
        return json.load(open(p, encoding="utf-8"))

    def list(self, limit=40):
        out = []
        for pid in sorted(os.listdir(C.PRODS), reverse=True)[:limit] if os.path.isdir(C.PRODS) else []:
            if not os.path.exists(os.path.join(C.PRODS, pid, "job.json")):
                continue
            try:
                j, st = self.job(pid), self.state(pid)
            except Exception:                                                               # noqa: BLE001
                continue
            if j.get("kind") in ("kplan", "kbuild"):                                            # internal planning / asset jobs are shown inside their project, not in the list
                continue
            out.append(dict(id=pid, title=j.get("title"), mode=j.get("mode"), kind=j.get("kind", "generate"), status=st["status"], overall=st["overall"], created=j.get("created"), parent=j.get("parent"),
                            poster=os.path.exists(os.path.join(C.PRODS, pid, "poster.jpg")), format=(j.get("settings") or {}).get("format")))
        return out
