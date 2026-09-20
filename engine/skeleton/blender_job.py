"""Python side of the Blender rig pipeline: characters + channels + camera -> job.json -> `blender -b -P skeleton_scene.py` -> RGBA frame sequence."""
import json
import os
import subprocess
import time

from engine.shorts.raster import ROOT

BLENDER = os.environ.get("BLENDER", "/Applications/Blender.app/Contents/MacOS/Blender")
SCRIPT = os.path.join(ROOT, "engine/blender/skeleton_scene.py")


class _Done:
    def __init__(self, stdout, stderr=""):
        self.stdout, self.stderr = stdout, stderr


def _run_watched(cmd, job, workdir, progress, poll=0.4):
    """run Blender and report REAL progress: every rendered frame is a PNG in job['out'] written after the render started, so the count of those files (not console text) is the progress.
    progress(done, total, last_frame, fps, phase) is called about every 0.4 s; the Blender process is killed if this function is interrupted (job cancelled)."""
    todo = [int(f) for f in job.get("render_frames") or []]
    prefix = job.get("prefix", "f")
    out_txt = os.path.join(workdir, "blender_stdout_live.txt")
    t0 = time.time()
    seen = {}
    with open(out_txt, "w") as fh:
        proc = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT, text=True)
        try:
            while proc.poll() is None:
                for f in todo:
                    if f not in seen:
                        p = os.path.join(job["out"], "%s%05d.png" % (prefix, f))
                        try:
                            m = os.stat(p).st_mtime
                        except OSError:
                            continue
                        if m >= t0 - 1.0:
                            seen[f] = m
                done = len(seen)
                fps = None
                if done >= 3:
                    ms = sorted(seen.values())
                    span = ms[-1] - ms[0]
                    fps = round((done - 1) / span, 2) if span > 0.05 else None
                nxt = next((f for f in todo if f not in seen), todo[-1] if todo else 0)
                progress(done, len(todo), nxt, fps, "rendering" if done else "building")
                time.sleep(poll)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
    txt = open(out_txt, errors="replace").read()
    return _Done(txt), len(seen)


def run(job, workdir, log=print, progress=None):
    """job: dict(width,height,fps,start,end,out,prefix,characters,camera,...). Returns the render report. `progress` (optional) receives the real render progress (see `_run_watched`)."""
    os.makedirs(workdir, exist_ok=True)
    jp = os.path.join(workdir, "job.json")
    json.dump(job, open(jp, "w"))
    t = time.time()
    cmd = [BLENDER, "--background", "--python", SCRIPT, "--", jp]
    stale = os.path.join(job["out"], "report.json")
    if os.path.exists(stale):
        os.remove(stale)                                                            # a report left by an earlier run must never make a crashed job look successful
    if progress is None:
        r = subprocess.run(cmd, capture_output=True, text=True)
    else:
        r, _ = _run_watched(cmd, job, workdir, progress)
    rep_path = os.path.join(job["out"], "report.json")
    if not os.path.exists(rep_path):
        raise RuntimeError("Blender rig job failed:\n" + (r.stdout + r.stderr)[-2500:])
    rep = json.load(open(rep_path))
    rep["wall_seconds"] = round(time.time() - t, 1)
    open(os.path.join(workdir, "blender_stdout.txt"), "w").write(r.stdout[-8000:])
    log(f"[blender] {rep['frames']} frames, {rep['objects']} objects, render {rep['render_seconds']}s, wall {rep['wall_seconds']}s")
    return rep
