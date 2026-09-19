"""Python side of the Blender rig pipeline: characters + channels + camera -> job.json -> `blender -b -P skeleton_scene.py` -> RGBA frame sequence."""
import json
import os
import subprocess
import time

from engine.shorts.raster import ROOT

BLENDER = os.environ.get("BLENDER", "/Applications/Blender.app/Contents/MacOS/Blender")
SCRIPT = os.path.join(ROOT, "engine/blender/skeleton_scene.py")


def run(job, workdir, log=print):
    """job: dict(width,height,fps,start,end,out,prefix,characters,camera,...). Returns the render report."""
    os.makedirs(workdir, exist_ok=True)
    jp = os.path.join(workdir, "job.json")
    json.dump(job, open(jp, "w"))
    t = time.time()
    r = subprocess.run([BLENDER, "--background", "--python", SCRIPT, "--", jp], capture_output=True, text=True)
    rep_path = os.path.join(job["out"], "report.json")
    if not os.path.exists(rep_path):
        raise RuntimeError("Blender rig job failed:\n" + (r.stdout + r.stderr)[-2500:])
    rep = json.load(open(rep_path))
    rep["wall_seconds"] = round(time.time() - t, 1)
    open(os.path.join(workdir, "blender_stdout.txt"), "w").write(r.stdout[-8000:])
    log(f"[blender] {rep['frames']} frames, {rep['objects']} objects, render {rep['render_seconds']}s, wall {rep['wall_seconds']}s")
    return rep
