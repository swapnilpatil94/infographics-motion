import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.skeleton import short_director as SD, short as SH
d = json.load(open("narration/skeleton/paced_cb.json"))
nar = dict(segments=[dict(id=s["beat_id"], text=s["text"], start=s["start_seconds"], end=s["end_seconds"], words=s["words"]) for s in d["segments"]], audio=os.path.abspath("narration/skeleton/paced_cb.wav"), tts="chatterbox", tempo=d["tempo"])
plan = SD.build_plan(nar, seed=7, tts="chatterbox")
os.makedirs("/tmp/short_test", exist_ok=True)
json.dump(plan, open("/tmp/short_test/plan.json", "w"), ensure_ascii=False, indent=1)
print("plan ok", plan["duration"], len(plan["shots"]), [s["id"] + ":" + s["treatment"] + ":" + str(round(s["t1"] - s["t0"], 1)) for s in plan["shots"]])
t = time.time()
actors, cam, frames_dir, rep, secs = SH.build_everything(plan, "/tmp/short_test", samples=6)
print("blender", rep["frames"], rep["rendered_frames"], "render", rep["render_seconds"], "s; ik max err", max(max(e[k] for k in ("IK_HAND_L", "IK_HAND_R", "IK_FOOT_L", "IK_FOOT_R")) for e in rep["ik_error_px"]))
