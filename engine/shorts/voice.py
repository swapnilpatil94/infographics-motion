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
import re
import subprocess
import sys

import numpy as np

from engine.shorts import audio
from engine.shorts.raster import ROOT

MYTHIC = os.environ.get("MYTHIC_STUDIO_DIR", os.path.expanduser("~/mythic-video-studio"))
PY312 = os.environ.get("TTS_PYTHON", os.path.expanduser("~/.pyenv/versions/3.12.0/bin/python"))
REFERENCE = os.environ.get("TTS_REFERENCE_AUDIO", os.path.join(MYTHIC, "assets/reference-voices/hindi-male-narrator.wav"))

# Chatterbox controls: higher exaggeration adds expression; cfg_weight around 0.3 can help pacing.
# Tuned for short-form Hindi/Hinglish reels: clarity first, controlled emphasis,
# less sampling variance, and a little more room between connected takes.
# These are starting presets; the best values still depend on the reference voice.
STORYTELLING_PRESETS = {
    "storytelling": dict(exaggeration=0.60, cfg_weight=0.35, temperature=0.55, tempo=0.96, silence_pad_seconds=0.12),
    "conversational": dict(exaggeration=0.52, cfg_weight=0.38, temperature=0.50, tempo=0.98, silence_pad_seconds=0.10),
    "dramatic": dict(exaggeration=0.66, cfg_weight=0.32, temperature=0.50, tempo=0.92, silence_pad_seconds=0.15),
}

# Optional spoken forms for frequent English/technical terms in Hindi narration.
# Original script remains unchanged. Mappings preserve one whitespace token per token.
_HINDI_SPOKEN_FORMS = {
    "AI": "एआई", "Detector": "डिटेक्टर", "Assignment": "असाइनमेंट", "email": "ईमेल",
    "report": "रिपोर्ट", "text": "टेक्स्ट", "copy-paste": "कॉपी-पेस्ट", "Words": "वर्ड्स",
    "file": "फ़ाइल", "End": "एंड", "system": "सिस्टम", "Model": "मॉडल", "step": "स्टेप",
    "word": "वर्ड", "options": "ऑप्शन्स", "score": "स्कोर", "secret": "सीक्रेट", "key": "की",
    "groups": "ग्रुप्स", "group": "ग्रुप", "pattern": "पैटर्न", "quality": "क्वालिटी",
    "Benchmarks": "बेंचमार्क्स", "Pause": "पॉज़", "Guess": "गेस", "Maths": "मैथ्स",
    "choice": "चॉइस", "flexibility": "फ्लेक्सिबिलिटी", "percent": "परसेंट", "number": "नंबर",
    "detection": "डिटेक्शन", "synonyms": "सिनोनिम्स", "OpenAI": "ओपनएआई", "Watermark": "वॉटरमार्क",
    "public": "पब्लिक", "approved": "अप्रूव्ड", "researchers": "रिसर्चर्स", "Photo": "फ़ोटो",
    "twist": "ट्विस्ट",
}
_SPOKEN_FORM_RE = re.compile(r"(?<!\w)(" + "|".join(re.escape(k) for k in sorted(_HINDI_SPOKEN_FORMS, key=len, reverse=True)) + r")(?!\w)", re.IGNORECASE)


def _tts_text(text, pronunciation_mode):
    if pronunciation_mode != "hindi_mixed":
        return text
    def replace(match):
        token = match.group(0)
        replacement = next((v for k, v in _HINDI_SPOKEN_FORMS.items() if k.casefold() == token.casefold()), None)
        return replacement if replacement is not None else token
    return _SPOKEN_FORM_RE.sub(replace, text)


def _prepare_beats(beats, pronunciation_mode):
    """Normalize pronunciation for TTS; keep one consistent voice/delivery across the script."""
    return [dict(b, tts_text=_tts_text(b["text"], pronunciation_mode)) for b in beats]


VOICE_DIR = os.path.join(ROOT, "output", "voice")


def _active_reference():
    config = os.path.join(VOICE_DIR, "active_reference.json")
    try:
        with open(config, encoding="utf-8") as f:
            path = json.load(f).get("path")
        if path and os.path.isfile(path):
            return os.path.abspath(path)
    except (OSError, ValueError, TypeError):
        pass
    return REFERENCE


def available(reference_audio=None):
    reference_audio = reference_audio or _active_reference()
    return all(os.path.exists(p) for p in (PY312, os.path.join(MYTHIC, "tools/chatterbox_tts.py"),
                                          os.path.join(MYTHIC, "tools/whisper_align.py"), reference_audio))


def _env():
    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.join(ROOT, ".vendor_py") + os.pathsep + env.get("PYTHONPATH", "")
    env["TOKENIZERS_PARALLELISM"] = "false"
    return env


def _key(beats, seed, style, pronunciation_mode, group_lines=False, reference_audio=None, group_max_lines=5, group_max_words=45):
    reference_audio = reference_audio or _active_reference()
    try:
        reference_version = str(os.path.getmtime(reference_audio)) + ":" + str(os.path.getsize(reference_audio))
    except OSError:
        reference_version = "missing"
    blob = json.dumps([[b["id"], b["text"], b.get("tts_text", b["text"]), b.get("performance", "default")] for b in beats], ensure_ascii=False)
    blob += reference_audio + reference_version + str(seed) + style + pronunciation_mode + str(group_lines) + str(group_max_lines) + str(group_max_words)
    blob += json.dumps(STORYTELLING_PRESETS.get(style, STORYTELLING_PRESETS["storytelling"]), sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def _read_wav_any(path):
    """-> mono float32 @ audio.SR (ffmpeg does the resample)."""
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(audio.SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def synthesize(beats, seed=42, log=print, allow_partial_alignment=False, style="storytelling", pronunciation_mode="hindi_mixed", group_lines=False, reference_audio=None, group_max_lines=5, group_max_words=45, performance_mode=False, expression_intensity=65):
    """beats: [{id, text}] -> dict(samples, voice, beats=[{id,text,start,end,words:[{word,start,end}]}], duration).

    allow_partial_alignment is for standalone script-to-audio export only: when WhisperX
    omits a beat, preserve the generated audio and provide clearly flagged estimated
    timestamps for that beat instead of failing the entire WAV export.
    """
    if style not in STORYTELLING_PRESETS:
        raise ValueError(f"unknown narration style: {style}")
    if pronunciation_mode not in ("hindi_mixed", "original"):
        raise ValueError(f"unknown pronunciation mode: {pronunciation_mode}")
    beats = _prepare_beats(beats, pronunciation_mode)
    reference_audio = os.path.abspath(reference_audio or _active_reference())
    settings = STORYTELLING_PRESETS[style]
    key = _key(beats, seed, style, pronunciation_mode, group_lines, reference_audio, group_max_lines, group_max_words) + ("-perf" + str(max(0, min(100, int(expression_intensity)))) if performance_mode else "-flat")
    d = os.path.join(VOICE_DIR, key)
    os.makedirs(d, exist_ok=True)
    wav, align = os.path.join(d, "narration.wav"), os.path.join(d, "align.json")
    model_info_path = os.path.join(d, "model_info.json")
    log(f"[voice] backend_check chatterbox_available={available(reference_audio)} python={PY312} mythic_studio={MYTHIC}")
    log(f"[voice] reference_audio={reference_audio} exists={os.path.exists(reference_audio)} style={style} pronunciation_mode={pronunciation_mode}")
    log(f"[voice] settings={json.dumps(settings, sort_keys=True)} group_lines={group_lines} group_max_lines={group_max_lines} group_max_words={group_max_words} cache_key={key} cache_dir={d}")
    if available(reference_audio):
        if not (os.path.exists(wav) and os.path.exists(align)):
            job = dict(output_path=wav, reference_audio=reference_audio, seed=seed, group_lines=group_lines, group_max_lines=group_max_lines, group_max_words=group_max_words, performance_mode=performance_mode, expression_intensity=max(0, min(100, int(expression_intensity))), **settings,
                       narration_style=style,
                       segments=[dict(beat_id=b["id"], text=b["tts_text"], display_text=b["text"], performance=b.get("performance", "default")) for b in beats])
            json.dump(job, open(os.path.join(d, "job.json"), "w"), ensure_ascii=False)
            log(f"[voice] backend=Chatterbox multilingual TTS; generating {len(beats)} beats")
            log(f"[voice] detailed TTS log: {os.path.join(d, 'tts.log')}")
            subprocess.run([PY312, os.path.join(MYTHIC, "tools/chatterbox_tts.py"), os.path.join(d, "job.json")],
                           env=_env(), check=True, stderr=open(os.path.join(d, "tts.log"), "w"))
            if os.path.exists(model_info_path):
                info = json.load(open(model_info_path, encoding="utf-8"))
                log(f"[voice] LOADED MODEL: {info.get('model_family')} | package={info.get('package_version')} | selector={info.get('selector_used')} | language_id={info.get('language_id')} | device={info.get('device')}")
                log(f"[voice] dedicated_hindi_checkpoint={info.get('dedicated_hindi_checkpoint')} | model_info={model_info_path}")
            log("[voice] forced alignment (whisperx)")
            subprocess.run([PY312, os.path.join(MYTHIC, "tools/whisper_align.py"), wav, wav + ".segments.json", align],
                           env=_env(), check=True, stderr=open(os.path.join(d, "align.log"), "w"))
        else:
            log(f"[voice] CACHE HIT: reusing existing WAV/alignment; no model was loaded this run")
            if os.path.exists(model_info_path):
                info = json.load(open(model_info_path, encoding="utf-8"))
                log(f"[voice] CACHED MODEL: {info.get('model_family')} | package={info.get('package_version')} | selector={info.get('selector_used')} | language_id={info.get('language_id')} | device={info.get('device')}")
                log(f"[voice] dedicated_hindi_checkpoint={info.get('dedicated_hindi_checkpoint')} | model_info={model_info_path}")
            else:
                log(f"[voice] WARNING: this cached narration has no model_info.json; model identity cannot be confirmed from this cache entry")
        data = _read_wav_any(wav)
        al = {b["beat_id"]: b["words"] for b in json.load(open(align))["beats"]}
        out = []
        missing = [i for i, b in enumerate(beats) if not al.get(b["id"])]
        if missing and not allow_partial_alignment:
            raise RuntimeError(f"alignment returned no words for beat {beats[missing[0]]['id']}")
        # Estimate only missing beat timings. Keep WhisperX's exact timings for every
        # aligned beat. First try the gap between aligned neighbors; if no usable gap
        # exists, estimate a window by the beat's share of the full audio duration.
        weights = [max(len((b.get("text") or "").split()), 1) for b in beats]
        total_weight = sum(weights) or 1
        for i, b in enumerate(beats):
            aligned = al.get(b["id"], [])
            display_words = b["text"].split()
            can_map_display = len(aligned) == len(display_words)
            words = [dict(word=(display_words[j] if can_map_display else w["word"]),
                          start=float(w["start"]), end=float(w["end"])) for j, w in enumerate(aligned)]
            estimated = False
            if not words:
                if not allow_partial_alignment:
                    raise RuntimeError(f"alignment returned no words for beat {b['id']}")
                prev_end = next((float(w["end"]) for j in range(i - 1, -1, -1)
                                 for w in reversed(al.get(beats[j]["id"], []))), None)
                next_start = next((float(w["start"]) for j in range(i + 1, len(beats))
                                   for w in al.get(beats[j]["id"], [])), None)
                if prev_end is not None and next_start is not None and next_start > prev_end + 0.08:
                    t0, t1 = prev_end, next_start
                else:
                    before = sum(weights[:i])
                    t0 = len(data) / audio.SR * before / total_weight
                    t1 = len(data) / audio.SR * (before + weights[i]) / total_weight
                tokens = (b.get("text") or "").split() or [b.get("text") or "…"]
                char_weights = [max(len(token), 1) for token in tokens]
                char_total = sum(char_weights) or 1
                cursor = t0
                words = []
                for token, weight in zip(tokens, char_weights):
                    nxt = cursor + (t1 - t0) * weight / char_total
                    words.append(dict(word=token, start=cursor, end=nxt))
                    cursor = nxt
                estimated = True
                log(f"[voice] WARNING: estimated word timings for {b['id']} (WhisperX returned no words)")
            out.append(dict(id=b["id"], text=b["text"], start=words[0]["start"], end=words[-1]["end"],
                            words=words, alignment_estimated=estimated))
        return dict(samples=data, voice=f"Chatterbox Hindi · {style} · WhisperX alignment", beats=out,
                    duration=len(data) / audio.SR, placeholder=False, narration_style=style,
                    pronunciation_mode=pronunciation_mode, group_lines=group_lines, group_max_lines=group_max_lines, group_max_words=group_max_words)
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
