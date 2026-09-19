"""Frame loop, audio mix, and encode for a compiled Show."""
import json
import os
import subprocess
import time

import numpy as np
from PIL import Image

from engine.shorts import audio, captions, director
from engine.shorts.layers import W, H
from engine.shorts.raster import ROOT

OUT = os.path.join(ROOT, "output", "shorts")


def frame_image(show, t, f):
    shot = director.configure(show, t)
    ins = None
    for t0, t1, sh in show.shots:
        if sh["id"] == shot and sh.get("insert") == "phone_screen":
            u = (t - t0) / max(t1 - t0, 1e-6)
            ins = lambda c, u=u: show.insert.apply(c, t, u, show.ch_bright(t), show.ch_banner(t), 0.0, 0.05)
    img = show.scene.render(t, f, director.fade_at(show, t), insert=ins, dust=show.dust)
    text, op = director.caption_at(show, t)
    bbox = None
    if text and op > 0:
        arr, bbox = captions.render(text)
        img = captions.overlay(img, arr, op * director.fade_at(show, t))
    return img, shot, (text, bbox)


def render_stills(show, times, tag="still"):
    os.makedirs(OUT, exist_ok=True)
    paths = []
    for t in times:
        img, shot, _ = frame_image(show, t, int(t * show.fps))
        p = os.path.join(OUT, f"{tag}_{t:05.2f}.png")
        Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).save(p)
        paths.append((t, shot, p))
    return paths


def build_audio(show, path):
    dur = show.duration
    mix = audio.Mix(dur + 1.0)
    rt = audio.room_tone(dur + 1.0)
    rt = rt * audio.duck_curve(len(rt), show.duck_windows)[: len(rt)]
    mix.buf[: len(rt)] += rt[: mix.n]
    for t, clip in show.voice_clips:
        mix.add(t, clip, 1.0)
    kinds = {"ding": audio.ding, "buzz": audio.buzz, "heartbeat": audio.heartbeat, "impact": audio.impact,
             "whoosh": audio.whoosh, "tick": audio.tick}
    for t, kind, g in show.sfx:
        if kind == "tinnitus":
            mix.add(t, audio.tinnitus(dur - t + 0.3), g)
        else:
            mix.add(t, kinds[kind](), g)
    for t0, t1 in show.drones:
        mix.add(t0, audio.drone(t1 - t0 + 0.3), 1.0)
    raw = mix.finish(os.path.join(OUT, "mix_raw.wav"))
    out = os.path.join(OUT, "mix.wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-af",
                    "loudnorm=I=-14:TP=-1.5:LRA=9", "-ar", "44100", out], check=True)
    return out


def render_video(show, out_mp4, limit=None):
    os.makedirs(OUT, exist_ok=True)
    n = int(round(show.duration * show.fps)) if limit is None else limit
    wav = build_audio(show, None)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(show.fps), "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "17",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", out_mp4]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t_start = time.time()
    stats = []
    for f in range(n):
        t = f / show.fps
        img, shot, (text, bbox) = frame_image(show, t, f)
        stats.append(dict(f=f, shot=shot, mean=float(img.mean()), caption=text, bbox=bbox))
        proc.stdin.write((np.clip(img, 0, 1) * 255).astype(np.uint8).tobytes())
    proc.stdin.close()
    proc.wait()
    return dict(frames=n, seconds=time.time() - t_start, stats=stats)
