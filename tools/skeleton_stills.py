import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from PIL import Image
from engine.skeleton import short as SH
work = sys.argv[1]; ts = [float(x) for x in sys.argv[2].split(",")]
plan = json.load(open(os.path.join(work, "plan.json")))
actors, cam, frames_dir, rep, _ = SH.build_everything(plan, work, skip_blender=True)
film = SH.SkeletonFilm(plan, actors, cam, SH.ActorLayer(frames_dir, plan["fps"]))
ims = []
for t in ts:
    img = film.frame_at(t, int(round(t * plan["fps"])))
    ims.append(Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).resize((360, 640)))
s = Image.new("RGB", (360 * len(ims), 640))
for i, im in enumerate(ims): s.paste(im, (360 * i, 0))
s.save(sys.argv[3])
