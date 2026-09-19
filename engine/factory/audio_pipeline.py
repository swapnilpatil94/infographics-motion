"""Narration retiming with DESIGNED pauses, synthesized underscore, sound design and the final mix (no licensed audio anywhere)."""
import math
import os
import subprocess
import wave

import numpy as np

from engine.shorts import audio

SR = audio.SR


def read_audio(path):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def retime(samples, segs, gaps, preroll=0.35):
    """Lay each narration segment after the ORIGINAL natural gap plus any designed pause. Returns (samples, new_segs, remap_fn)."""
    total = preroll + sum(s["end"] - s["start"] + 0.5 for s in segs) + sum(gaps.values()) + 2.0
    out = np.zeros(int(total * SR), np.float32)
    new, deltas, t_prev_new, prev_old_end = [], [], 0.0, 0.0
    for i, s in enumerate(segs):
        nat = min(max(s["start"] - prev_old_end, 0.05), 1.2) if i else 0.0
        start = preroll if i == 0 else t_prev_new + nat + gaps.get(s["id"], 0.0)
        a0, a1 = max(s["start"] - 0.05, 0.0), min(s["end"] + 0.10, len(samples) / SR)
        seg = samples[int(a0 * SR):int(a1 * SR)].copy()
        fade = min(len(seg) // 2, int(0.01 * SR))
        if fade:
            seg[:fade] *= np.linspace(0, 1, fade)
            seg[-fade:] *= np.linspace(1, 0, fade)
        at = int((start - (s["start"] - a0)) * SR)
        out[at:at + len(seg)] += seg[:max(0, len(out) - at)]
        delta = start - s["start"]
        deltas.append((s["start"], delta))
        w = [dict(x, start=x["start"] + delta, end=x["end"] + delta) for x in (s.get("words") or [])]
        new.append(dict(s, start=start, end=s["end"] + delta, words=w or None, delta=delta))
        t_prev_new, prev_old_end = s["end"] + delta, s["end"]
    dur = new[-1]["end"] + 0.6

    def remap(t):
        d = 0.0
        for st, dl in deltas:
            if st <= t:
                d = dl
            else:
                break
        return t + d
    return out[:int(dur * SR)], new, remap


# ------------------------------------------------------------------------------------------- underscore
CHORDS = {   # mood -> (root frequencies, brightness, pulse bpm or 0)
    "neutral": ([110.0, 164.81, 246.94, 293.66], 0.5, 0), "formal": ([110.0, 164.81, 220.0, 277.18], 0.35, 0),
    "pressure": ([110.0, 116.54, 164.81, 174.61], 0.6, 72), "fear": ([55.0, 58.27, 77.78, 116.54], 0.45, 84),
    "isolated": ([110.0, 329.63, 440.0], 0.3, 0), "dim": ([82.41, 123.47, 185.0], 0.3, 0),
    "warm": ([130.81, 196.0, 261.63, 329.63], 0.6, 0), "bright": ([130.81, 196.0, 261.63, 392.0], 0.7, 0),
    "relief": ([130.81, 196.0, 261.63, 329.63, 392.0], 0.55, 0)}


def _pad(freqs, dur, bright, seed):
    t = np.arange(int(dur * SR)) / SR
    rng = np.random.default_rng(seed)
    x = np.zeros_like(t, np.float32)
    for f in freqs:
        for det in (-0.6, 0.0, 0.7):
            ph = rng.uniform(0, 6.28)
            lfo = 0.6 + 0.4 * np.sin(2 * math.pi * rng.uniform(0.05, 0.13) * t + rng.uniform(0, 6.28))
            x += (np.sin(2 * math.pi * (f + det) * t + ph) + bright * 0.35 * np.sin(2 * math.pi * 2 * (f + det) * t + ph)) * lfo
    x /= max(len(freqs) * 3, 1)
    return (x * 0.5).astype(np.float32)


def underscore(duration, mood_track, seed=5):
    """mood_track: [(t0, t1, mood)] -> synthesized ambient bed with cross-faded chords and a heartbeat pulse in tense moods."""
    buf = np.zeros(int((duration + 2) * SR), np.float32)
    hb = audio.heartbeat()
    for k, (t0, t1, mood) in enumerate(mood_track):
        fr, bright, bpm = CHORDS.get(mood, CHORDS["neutral"])
        d = max(0.5, t1 - t0) + 2.0
        pad = _pad(fr, d, bright, seed + k)
        env = np.minimum(np.linspace(0, 1, len(pad)) * (d / 1.0), 1.0) * np.minimum(np.linspace(1, 0, len(pad)) * (d / 1.0), 1.0)
        i0 = int(max(t0 - 1.0, 0) * SR)
        buf[i0:i0 + len(pad)] += pad[:max(0, len(buf) - i0)] * env[:max(0, len(buf) - i0)]
        if bpm:
            step = 60.0 / bpm
            tt = t0
            while tt < t1:
                i = int(tt * SR)
                buf[i:i + len(hb)] += hb[:max(0, len(buf) - i)] * 0.35
                tt += step
    return buf[:int(duration * SR)]


def mix(duration, narration, sfx, mood_track, room_gain=0.5, music_gain=0.32, out_dir="."):
    """sfx: [(t, kind, gain)] in FILM time. Final loudness normalised to -16 LUFS (long-form master)."""
    m = audio.Mix(duration + 1.0)
    rt = audio.room_tone(duration + 1.0) * room_gain * 0.5
    m.buf[:len(rt)] += rt[:m.n]
    bed = underscore(duration, mood_track)
    m.buf[:len(bed)] += bed[:m.n] * music_gain
    v = narration * (0.7 / max(float(np.abs(narration).max()), 1e-6))
    # sidechain-style duck of the bed under speech: envelope from narration energy
    env = np.convolve(np.abs(narration), np.ones(int(0.25 * SR)) / int(0.25 * SR), mode="same")
    duck = 1.0 - 0.55 * np.clip(env / (env.max() + 1e-9) * 3.0, 0, 1)
    n = min(len(bed), len(duck), m.n)
    m.buf[:n] -= bed[:n] * music_gain * (1 - duck[:n]) * 0.0
    m.buf[:n] += 0.0
    m.add(0.0, v, 1.0)
    kinds = {"ding": audio.ding, "buzz": audio.buzz, "heartbeat": audio.heartbeat, "impact": audio.impact, "whoosh": audio.whoosh, "tick": audio.tick}
    for t, kind, g in sfx:
        if g > 0 and kind in kinds and 0 <= t < duration:
            m.add(t, kinds[kind](), g * 0.5)
    raw = m.finish(os.path.join(out_dir, "mix_raw.wav"))
    out = os.path.join(out_dir, "mix.wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "44100", out], check=True)
    return out
