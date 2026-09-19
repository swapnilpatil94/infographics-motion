"""Frame loop, audio mix and encode for a compiled Film (v3 pipeline)."""
import os
import subprocess
import time

import numpy as np
from PIL import Image

from engine.shorts import audio, captions, cards, film as F
from engine.shorts.layers import W, H
from engine.shorts.raster import ROOT

SFX_GAIN = 0.5


def frame_image(film, t, f):
    shot = F.shot_at(film, t)
    ent, fade = shot["beat"], F.fade_at(film, t)
    if getattr(film, "stage", None) is not None:
        from engine.shorts import story
        img = story.render_frame(film, shot, t, f, fade)
    elif ent["kind"] == "card":
        img = cards.render(ent["card"], t - ent["t0"], ent["t1"] - ent["t0"], seed=film.plan.get("seed", 0) + 17)
        film.post.exposure = 1.0
        img = film.post.apply(img, f, fade)
    else:
        sc = ent["spec"]["scene"]
        rig = ent["rig"]
        rig.use(sc["body"], [sc["face"]] + ([sc["face_end"]] if sc.get("face_end") else []))
        rig.state.update(ent["perf"].state(t))
        rig.apply()
        scene = ent["scene"]
        scene.camera = F.camera_at(film, shot, t)
        ph = ent.get("phone")
        if ph is not None:
            ph.update(ent["ch_bright"](t), ent["ch_banner"](t))
        film.post.exposure = ent["exposure"]
        if ent["stand"]:
            room = scene.room
            vis = ent["stand_visible"]
            for n in ("stand_phone", "stand_screen"):
                room[n].visible = vis
                room[n].world_xf = np.array([[1, 0, 3.0 * ent["ch_buzz"](t)], [0, 1, 0], [0, 0, 1.0]])
            room["stand_screen"].opacity = float(min(1.0, ent["ch_stand"](t))) if vis else 0.0
            room["clouds"].world_xf = np.array([[1, 0, 16.0 * np.sin(0.13 * t + 0.6)], [0, 1, 0], [0, 0, 1.0]])
        ins = None
        if shot["insert"]:
            u = (t - shot["t0"]) / max(shot["t1"] - shot["t0"], 1e-6)
            from engine.shorts.insert import ScreenInsert
            si = ent.setdefault("_insert", ScreenInsert(ph))
            ins = lambda c, u=u: si.apply(c, t, u, ent["ch_bright"](t), ent["ch_banner"](t), 0.0, 0.05)
        img = scene.render(t, f, fade, insert=ins, dust=ent["dust"], fx=ent["fx"])
    pn = film.stage.punch if getattr(film, "stage", None) is not None else ent.get("punch")
    if pn and pn[0] and pn[1] <= t <= pn[2]:
        ptxt, p0, p1 = pn
        parr, _ = captions.render(ptxt, size=190, center_y=520)
        img = captions.overlay(img, parr, min(1.0, (t - p0) / 0.12) * min(1.0, (p1 - t) / 0.3) * fade)
    text, op = F.caption_at(film, t)
    bbox = None
    if text and op > 0:
        arr, bbox = captions.render(text)
        img = captions.overlay(img, arr, op * fade)
    return img, shot["id"], (text, bbox)


def build_audio(film, out_dir):
    dur = film.duration
    mix = audio.Mix(dur + 1.0)
    rt = audio.room_tone(dur + 1.0) * 0.6
    mix.buf[: len(rt)] += rt[: mix.n]
    v = film.samples
    v = v * (0.7 / max(float(np.abs(v).max()), 1e-6))
    mix.add(0.0, v, 1.0)
    kinds = {"ding": audio.ding, "buzz": audio.buzz, "heartbeat": audio.heartbeat, "impact": audio.impact,
             "whoosh": audio.whoosh, "tick": audio.tick}
    for t, kind, g in film.sfx:
        if g > 0 and kind in kinds:
            mix.add(max(t, 0.0), kinds[kind](), g * SFX_GAIN)
    raw = mix.finish(os.path.join(out_dir, "mix_raw.wav"))
    out = os.path.join(out_dir, "mix.wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-af", "loudnorm=I=-14:TP=-1.5:LRA=9",
                    "-ar", "44100", out], check=True)
    return out


def render_video(film, out_mp4, limit=None, log=print):
    out_dir = os.path.dirname(out_mp4)
    os.makedirs(out_dir, exist_ok=True)
    n = int(round(film.duration * film.fps)) if limit is None else limit
    wav = build_audio(film, out_dir)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(film.fps), "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "21",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", out_mp4]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0, stats, prev = time.time(), [], None
    for f in range(n):
        tf = time.perf_counter()
        img, shot, (text, bbox) = frame_image(film, f / film.fps, f)
        small = img[::40, ::40]
        diff = float(np.abs(small - prev).mean()) if prev is not None else 1.0
        prev = small.copy()
        stats.append(dict(f=f, shot=shot, mean=float(img.mean()), caption=text, bbox=bbox, diff=diff, rgb=[float(x) for x in img.mean(axis=(0, 1))],
                          ms=round((time.perf_counter() - tf) * 1000, 1)))
        proc.stdin.write((np.clip(img, 0, 1) * 255).astype(np.uint8).tobytes())
        if f % 150 == 0:
            log(f"[render] frame {f}/{n} ({time.time() - t0:.0f}s)")
    proc.stdin.close()
    proc.wait()
    return dict(frames=n, seconds=time.time() - t0, stats=stats)


def render_stills(film, times, out_dir, tag="still"):
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for t in times:
        img, shot, _ = frame_image(film, t, int(t * film.fps))
        p = os.path.join(out_dir, f"{tag}_{t:05.2f}.png")
        Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).save(p)
        paths.append((t, shot, p))
    return paths
