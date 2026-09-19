"""Narration timing + synthesized sound design + mix.

Narration here is macOS `say` (Lekha, hi_IN) used as a PLACEHOLDER VOICE: its
value is exact per-segment durations, so cuts/cues can be locked to speech
rather than guessed. A real narration recording drops in by replacing the
wav files; nothing else changes. All SFX are synthesized (numpy), so there
are no licensed sound assets to track.
"""
import hashlib
import os
import subprocess
import wave

import numpy as np

SR = 44100
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
AUDIO_DIR = os.path.join(ROOT, "output", "audio")


def _filt(x, kind, f1, f2=None, order=2):
    """Zero-phase Butterworth-magnitude filter via FFT (scipy.signal is
    unusable on this machine - broken native extension - and for shaping
    noise a magnitude-only filter is all that's needed)."""
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1.0 / SR)
    f = np.maximum(f, 1e-3)
    if kind == "low":
        m = 1.0 / np.sqrt(1 + (f / f1) ** (2 * order))
    elif kind == "high":
        m = 1.0 / np.sqrt(1 + (f1 / f) ** (2 * order))
    else:
        m = (1.0 / np.sqrt(1 + (f1 / f) ** (2 * order))) * (1.0 / np.sqrt(1 + (f / f2) ** (2 * order)))
    return np.fft.irfft(X * m, len(x)).astype(np.float32)


def _read_wav(path):
    with wave.open(path, "rb") as w:
        n, ch, sw = w.getnframes(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(n)
    a = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    return a.reshape(-1, ch).mean(axis=1) if ch > 1 else a


def write_wav(path, data):
    d = np.clip(data, -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((d * 32767).astype(np.int16).tobytes())


def synth_segment(text, voice="Lekha", rate=150):
    os.makedirs(AUDIO_DIR, exist_ok=True)
    key = hashlib.sha256(f"{voice}|{rate}|{text}".encode()).hexdigest()[:16]
    wav = os.path.join(AUDIO_DIR, f"nar_{key}.wav")
    if not os.path.exists(wav):
        aiff = wav.replace(".wav", ".aiff")
        subprocess.run(["say", "-v", voice, "-r", str(rate), "-o", aiff, text], check=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", aiff,
                        "-af", "silenceremove=start_periods=1:start_threshold=-45dB:stop_periods=1:stop_threshold=-45dB:stop_duration=0.15",
                        "-ar", str(SR), "-ac", "1", wav], check=True)
        os.remove(aiff)
    return wav, _read_wav(wav)


def build_narration(cfg):
    """-> (anchors dict like {'s1.start':..,'s1.end':..,'end':..}, [(start_t, samples)])"""
    t = cfg.get("preroll", 1.0)
    anchors, clips = {}, []
    for seg in cfg["segments"]:
        _, data = synth_segment(seg["text"], cfg.get("voice", "Lekha"), cfg.get("rate", 150))
        dur = len(data) / SR
        anchors[f"{seg['id']}.start"] = t
        anchors[f"{seg['id']}.end"] = t + dur
        clips.append((t, data))
        t += dur + cfg.get("gap", 0.4)
    anchors["speech_end"] = t - cfg.get("gap", 0.4)
    anchors["end"] = anchors["speech_end"] + cfg.get("tail", 1.5)
    return anchors, clips


# ------------------------------------------------------------------ sfx
def _env(n, attack=0.002, decay=0.3):
    t = np.arange(n) / SR
    return np.minimum(t / max(attack, 1e-4), 1.0) * np.exp(-t / decay)


def ding():
    n = int(SR * 0.9)
    t = np.arange(n) / SR
    out = np.zeros(n, np.float32)
    for f, t0, g in ((1318.5, 0.0, 1.0), (1975.5, 0.13, 0.85)):
        i0 = int(t0 * SR)
        tt = t[: n - i0]
        mod = 1.4 * np.sin(2 * np.pi * f * 2.01 * tt) * np.exp(-9 * tt)
        out[i0:] += (np.sin(2 * np.pi * f * tt + mod) * np.exp(-5.5 * tt) * g).astype(np.float32)
    return out * 0.34


def buzz(pulses=2):
    n = int(SR * (0.16 * pulses + 0.05 * (pulses - 1)))
    t = np.arange(n) / SR
    out = np.zeros(n, np.float32)
    for k in range(pulses):
        i0 = int(k * 0.21 * SR)
        m = int(0.16 * SR)
        tt = np.arange(m) / SR
        s = np.sin(2 * np.pi * 165 * tt) + 0.5 * np.sin(2 * np.pi * 330 * tt) + 0.25 * np.sin(2 * np.pi * 495 * tt)
        s *= 0.6 + 0.4 * np.sign(np.sin(2 * np.pi * 34 * tt))
        s *= np.minimum(tt / 0.006, 1) * np.minimum((0.16 - tt) / 0.02, 1)
        out[i0:i0 + m] += (s * 0.16).astype(np.float32)
    return out


def heartbeat():
    def thump(f0, dur, g):
        n = int(SR * dur)
        tt = np.arange(n) / SR
        f = f0 * (1.0 - 0.35 * tt / dur)
        return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.minimum(tt / 0.008, 1) * np.exp(-tt / 0.07) * g).astype(np.float32)
    out = np.zeros(int(SR * 0.6), np.float32)
    a, b = thump(58, 0.28, 0.9), thump(48, 0.28, 0.6)
    out[: len(a)] += a
    i = int(0.19 * SR)
    out[i:i + len(b)] += b
    return out * 0.85


def impact():
    n = int(SR * 1.1)
    tt = np.arange(n) / SR
    f = 62 * np.exp(-tt * 3.2) + 26
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt / 0.32)
    rng = np.random.default_rng(5)
    nz = _filt(rng.standard_normal(n), "low", 900) * np.exp(-tt / 0.09)
    return (sub * 0.95 + nz * 0.5).astype(np.float32) * 0.7


def whoosh(dur=0.34):
    n = int(SR * dur)
    tt = np.arange(n) / SR
    rng = np.random.default_rng(9)
    nz = rng.standard_normal(n)
    env = np.sin(np.pi * tt / dur) ** 2
    return (_filt(nz, "band", 300, 2600) * env * 0.05).astype(np.float32)


def room_tone(dur, seed=2):
    n = int(SR * dur)
    rng = np.random.default_rng(seed)
    brown = np.cumsum(rng.standard_normal(n))
    brown = _filt(brown, "band", 60, 500)
    brown /= np.abs(brown).max() + 1e-6
    t = np.arange(n) / SR
    hum = 0.05 * np.sin(2 * np.pi * 50 * t) + 0.02 * np.sin(2 * np.pi * 100 * t)
    return (brown * 0.06 + hum * 0.05).astype(np.float32)


def tick():
    n = int(SR * 0.05)
    tt = np.arange(n) / SR
    rng = np.random.default_rng(1)
    click = _filt(rng.standard_normal(n), "high", 2500)
    return (click * np.exp(-tt / 0.006) * 0.05 + np.sin(2 * np.pi * 1100 * tt) * np.exp(-tt / 0.012) * 0.03).astype(np.float32)


def drone(dur):
    n = int(SR * dur)
    t = np.arange(n) / SR
    s = sum(np.sin(2 * np.pi * f * t + p) for f, p in ((55.0, 0), (82.6, 1.1), (110.4, 2.3), (164.9, 0.4)))
    s *= 0.6 + 0.4 * np.sin(2 * np.pi * 0.35 * t)
    env = np.minimum(t / (dur * 0.85), 1.0) ** 2 * np.minimum((dur - t) / 0.25, 1.0)
    return (s * env * 0.035).astype(np.float32)


def tinnitus(dur):
    n = int(SR * dur)
    t = np.arange(n) / SR
    env = np.minimum(t / 0.4, 1.0) * np.minimum((dur - t) / 0.5, 1.0)
    return (np.sin(2 * np.pi * 7400 * t) * env * 0.006).astype(np.float32)


class Mix:
    def __init__(self, duration):
        self.n = int(duration * SR) + SR
        self.buf = np.zeros(self.n, np.float32)

    def add(self, t, data, gain=1.0):
        i = int(t * SR)
        if i < 0 or i >= self.n:
            return
        m = min(len(data), self.n - i)
        self.buf[i:i + m] += data[:m] * gain

    def finish(self, path):
        write_wav(path, self.buf)
        return path


def duck_curve(n, windows):
    """Gain envelope: 1.0 except in (t0,t1,gain) windows (fast in, slower out)."""
    g = np.ones(n, np.float32)
    for t0, t1, gain in windows:
        i0, i1 = int(t0 * SR), int(t1 * SR)
        fin, fout = int(0.05 * SR), int(0.6 * SR)
        g[i0:i1] = np.minimum(g[i0:i1], gain)
        ramp_in = np.linspace(1, gain, fin)
        g[max(i0 - fin, 0):i0] = np.minimum(g[max(i0 - fin, 0):i0], ramp_in[-(i0 - max(i0 - fin, 0)):] if i0 > 0 else 1)
        ramp_out = np.linspace(gain, 1, fout)
        m = min(fout, n - i1)
        g[i1:i1 + m] = np.minimum(g[i1:i1 + m], ramp_out[:m])
    return g
