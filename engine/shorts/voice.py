"""Narration: real Hindi TTS + word-level forced alignment.

Reuses the sibling project's adapters (mythic-video-studio/tools):
  chatterbox_tts.py  - Chatterbox Multilingual (hi), voice-cloned from a reference WAV
  whisper_align.py   - whisperx wav2vec2 forced alignment against the KNOWN script
                       (word start/end), also trims dead air between words
They run in that project's Python 3.12 environment. This machine's scipy build cannot
dlopen some native extensions, so a working scipy wheel is put first on PYTHONPATH from
`.vendor_py/` (pip --target; the shared environment is not modified).

Output is cached by content hash, so re-running a plan never re-synthesizes.
Fallback (flagged in the result): macOS `say` with proportional word timing.
"""
import hashlib
import json
import os
import subprocess
import sys

import numpy as np

from engine.shorts import audio
from engine.shorts.raster import ROOT

MYTHIC = os.environ.get("MYTHIC_STUDIO_DIR", os.path.expanduser("~/mythic-video-studio"))
PY312 = os.environ.get("TTS_PYTHON", os.path.expanduser("~/.pyenv/versions/3.12.0/bin/python"))
REFERENCE = os.environ.get("TTS_REFERENCE_AUDIO", os.path.join(MYTHIC, "assets/reference-voices/hindi-male-narrator.wav"))
VOICE_DIR = os.path.join(ROOT, "output", "voice")


def available():
    return all(os.path.exists(p) for p in (PY312, os.path.join(MYTHIC, "tools/chatterbox_tts.py"),
                                          os.path.join(MYTHIC, "tools/whisper_align.py"), REFERENCE))


def _env():
    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.join(ROOT, ".vendor_py") + os.pathsep + env.get("PYTHONPATH", "")
    env["TOKENIZERS_PARALLELISM"] = "false"
    return env


def _key(beats, seed):
    blob = json.dumps([[b["id"], b["text"]] for b in beats], ensure_ascii=False) + REFERENCE + str(seed)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def _read_wav_any(path):
    """-> mono float32 @ audio.SR (ffmpeg does the resample)."""
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(audio.SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def synthesize(beats, seed=42, log=print):
    """beats: [{id, text}] -> dict(samples, voice, beats=[{id,text,start,end,words:[{word,start,end}]}], duration)."""
    key = _key(beats, seed)
    d = os.path.join(VOICE_DIR, key)
    os.makedirs(d, exist_ok=True)
    wav, align = os.path.join(d, "narration.wav"), os.path.join(d, "align.json")
    if available():
        if not (os.path.exists(wav) and os.path.exists(align)):
            job = dict(output_path=wav, reference_audio=REFERENCE, seed=seed,
                       segments=[dict(beat_id=b["id"], text=b["text"]) for b in beats])
            json.dump(job, open(os.path.join(d, "job.json"), "w"), ensure_ascii=False)
            log(f"[voice] Chatterbox Hindi TTS for {len(beats)} beats (cached at {key} afterwards)")
            subprocess.run([PY312, os.path.join(MYTHIC, "tools/chatterbox_tts.py"), os.path.join(d, "job.json")],
                           env=_env(), check=True, stderr=open(os.path.join(d, "tts.log"), "w"))
            log("[voice] forced alignment (whisperx)")
            subprocess.run([PY312, os.path.join(MYTHIC, "tools/whisper_align.py"), wav, wav + ".segments.json", align],
                           env=_env(), check=True, stderr=open(os.path.join(d, "align.log"), "w"))
        data = _read_wav_any(wav)
        al = {b["beat_id"]: b["words"] for b in json.load(open(align))["beats"]}
        out = []
        for b in beats:
            words = [dict(word=w["word"], start=float(w["start"]), end=float(w["end"])) for w in al.get(b["id"], [])]
            if not words:
                raise RuntimeError(f"alignment returned no words for beat {b['id']}")
            out.append(dict(id=b["id"], text=b["text"], start=words[0]["start"], end=words[-1]["end"], words=words))
        return dict(samples=data, voice="chatterbox-hi (voice-cloned reference) + whisperx alignment", beats=out,
                    duration=len(data) / audio.SR, placeholder=False)
    # ---- fallback: system voice, proportional word timing (flagged placeholder)
    log("[voice] WARNING: Chatterbox stack unavailable - using macOS `say` placeholder with estimated word timing")
    t, clips, out = 0.0, [], []
    for b in beats:
        _, data = audio.synth_segment(b["text"], "Lekha", 150)
        dur = len(data) / audio.SR
        toks = b["text"].split()
        tot = sum(len(w) for w in toks) or 1
        cur, words = t, []
        for w in toks:
            dw = dur * len(w) / tot
            words.append(dict(word=w, start=cur, end=cur + dw))
            cur += dw
        out.append(dict(id=b["id"], text=b["text"], start=t, end=t + dur, words=words))
        clips.append((t, data))
        t += dur + 0.35
    buf = np.zeros(int((t + 0.5) * audio.SR), np.float32)
    for t0, data in clips:
        i = int(t0 * audio.SR)
        buf[i:i + len(data)] += data
    return dict(samples=buf, voice="macOS say (Lekha) PLACEHOLDER", beats=out, duration=t, placeholder=True)


def retime(v, gap_before, preroll=0.3, default_gap=0.3, tail=0.4):
    """Re-lay narration with DESIGNED pauses (silence is part of the edit): each beat keeps its
    words/timings but is placed after gap_before[beat_id] seconds of silence. Deterministic."""
    sr, src = audio.SR, v["samples"]
    total = preroll + sum(gap_before.get(b["id"], default_gap) for b in v["beats"][1:]) + sum(b["end"] - b["start"] + 0.2 for b in v["beats"]) + tail + 1
    out = np.zeros(int(total * sr), np.float32)
    beats, t = [], preroll
    for i, b in enumerate(v["beats"]):
        if i:
            t += gap_before.get(b["id"], default_gap)
        s0, s1 = max(b["start"] - 0.06, 0.0), min(b["end"] + 0.10, v["duration"])
        seg = src[int(s0 * sr):int(s1 * sr)].copy()
        fade = min(len(seg) // 2, int(0.01 * sr))
        seg[:fade] *= np.linspace(0, 1, fade)
        seg[-fade:] *= np.linspace(1, 0, fade)
        at = t - (b["start"] - s0)
        i0 = int(at * sr)
        out[i0:i0 + len(seg)] += seg
        delta = t - b["start"]
        words = [dict(w, start=w["start"] + delta, end=w["end"] + delta) for w in b["words"]]
        beats.append(dict(b, start=words[0]["start"], end=words[-1]["end"], words=words))
        t = beats[-1]["end"]
    n = int((t + tail) * sr)
    return dict(v, samples=out[:n], beats=beats, duration=n / sr)
