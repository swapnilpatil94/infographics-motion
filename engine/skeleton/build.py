"""Entry points for the skeleton-factory proof short.

    python3 studio.py --skeleton-short [--tts chatterbox|vibevoice] [--tempo 1.16]     # narration -> pacing -> plan.json -> Blender rig -> film
    python3 studio.py --from-plan output/shorts/skeleton_factory_proof/plan.json        # deterministic re-render: no LLM, no TTS
"""
import hashlib
import json
import os
import shutil
import subprocess

from engine.shorts.raster import ROOT
from engine.skeleton import pace, short, short_director as SD

OUT = os.path.join(ROOT, "output/shorts/skeleton_factory_proof")
STORY = os.path.join(ROOT, "stories/skeleton_proof_call.md")
BEATS_JSON = os.path.join(ROOT, "narration/skeleton/vv_job.json")


def beats():
    return [(b["beat_id"], b["text"]) for b in json.load(open(BEATS_JSON, encoding="utf-8"))["segments"]]


def _script_hash():
    return hashlib.sha1(json.dumps(beats(), ensure_ascii=False).encode()).hexdigest()[:12]


def tts_chatterbox(log=print, force=False):
    """13 per-beat Chatterbox Hindi clips (voice-cloned reference) + whisperx word alignment. Cached by script hash."""
    raw_wav, raw_json = os.path.join(OUT, "narration/raw_chatterbox.wav"), os.path.join(OUT, "narration/raw_chatterbox.wav.segments.json")
    stamp = os.path.join(OUT, "narration/raw_chatterbox.hash")
    if not force and os.path.exists(raw_wav) and os.path.exists(stamp) and open(stamp).read() == _script_hash():
        return raw_wav, raw_json
    os.makedirs(os.path.dirname(raw_wav), exist_ok=True)
    cache_wav, cache_json = os.path.join(ROOT, "narration/skeleton/cb.wav"), os.path.join(ROOT, "narration/skeleton/cb.wav.segments.json")
    if not force and os.path.exists(cache_wav):                                    # identical script already synthesised on this machine
        shutil.copy(cache_wav, raw_wav)
        shutil.copy(cache_json, raw_json)
    else:
        from engine.shorts import voice
        log("[tts] Chatterbox Hindi (per beat) ...")
        b = [dict(id=i, text=t) for i, t in beats()]
        v = voice.synthesize(b, seed=42, log=log)
        key = voice._key(b, 42)
        shutil.copy(os.path.join(voice.VOICE_DIR, key, "narration.wav"), raw_wav)
        json.dump(dict(segments=[dict(beat_id=x["id"], text=x["text"], start_seconds=round(x["start"], 3), end_seconds=round(x["end"], 3),
                                      words=[dict(word=w["word"], start=round(w["start"], 3), end=round(w["end"], 3)) for w in x["words"]]) for x in v["beats"]],
                       duration_seconds=round(v["duration"], 3)), open(raw_json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(stamp, "w").write(_script_hash())
    return raw_wav, raw_json


def tts_vibevoice(log=print):
    """VibeVoice Hindi 7B (mythic-video-studio) in 4 short batches (long-form runs degrade), then whisperx alignment. See docs/NARRATION_TTS_TEST.md for the measured comparison."""
    env = dict(os.environ)
    env.update(PYTHONPATH=os.pathsep.join([os.path.join(ROOT, ".vendor_tf"), os.path.join(ROOT, ".vendor_py"), os.path.expanduser("~/mythic-video-studio/tools/vibevoice-repo")]),
               VIBEVOICE_REPO_DIR=os.path.expanduser("~/mythic-video-studio/tools/vibevoice-repo"), VIBEVOICE_PYTHON=os.path.expanduser("~/.pyenv/versions/3.12.0/bin/python3"),
               VIBEVOICE_MODEL_PATH=os.path.expanduser("~/mythic-video-studio/tools/vibevoice-model"), VIBEVOICE_SPEAKER_NAME="kathaya-hindi-narrator", VIBEVOICE_DEVICE="mps")
    b = beats()
    groups = [b[0:4], b[4:8], b[8:11], b[11:13]]
    wd = os.path.join(OUT, "narration/vv")
    os.makedirs(wd, exist_ok=True)
    wavs = []
    for i, g in enumerate(groups):
        out = os.path.join(wd, f"b{i}.wav")
        if not os.path.exists(out):
            job = os.path.join(wd, f"b{i}.json")
            json.dump(dict(segments=[dict(beat_id=x, text=t) for x, t in g], output_path=out, reference_audio=""), open(job, "w", encoding="utf-8"), ensure_ascii=False)
            log(f"[tts] VibeVoice batch {i + 1}/4 ...")
            subprocess.run(["python3", os.path.expanduser("~/mythic-video-studio/tools/vibevoice_tts.py"), job], check=True, env=env)
        wavs.append(out)
    concat = os.path.join(wd, "all.wav")
    lst = os.path.join(wd, "list.txt")
    open(lst, "w").write("".join(f"file '{w}'\n" for w in wavs))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-ar", "24000", "-ac", "1", concat], check=True)
    seg = concat + ".segments.json"
    json.dump(dict(segments=[dict(beat_id=x, text=t, start_seconds=0, end_seconds=1) for x, t in b], duration_seconds=1), open(seg, "w", encoding="utf-8"), ensure_ascii=False)
    align = os.path.join(wd, "align.json")
    e2 = dict(os.environ, PYTHONPATH=os.path.join(ROOT, ".vendor_py"), TOKENIZERS_PARALLELISM="false")
    subprocess.run([os.path.expanduser("~/.pyenv/versions/3.12.0/bin/python"), os.path.expanduser("~/mythic-video-studio/tools/whisper_align.py"), concat, seg, align], check=True, env=e2)
    al = json.load(open(align))
    words = [w for bt in al["beats"] for w in bt["words"]]
    json.dump(dict(segments=[dict(beat_id="all", text=" ".join(t for _, t in b), start_seconds=0, end_seconds=1, words=words)]), open(concat + ".words.json", "w", encoding="utf-8"), ensure_ascii=False)
    return concat, concat + ".words.json"


def make(tts="chatterbox", tempo=1.16, seed=7, log=print, force_tts=False, samples=10):
    os.makedirs(os.path.join(OUT, "narration"), exist_ok=True)
    raw_wav, raw_json = tts_chatterbox(log, force_tts) if tts == "chatterbox" else tts_vibevoice(log)
    paced_wav, paced_json = os.path.join(OUT, "narration/paced.wav"), os.path.join(OUT, "narration/paced.json")
    d = pace.build(raw_wav, raw_json, beats(), paced_wav, paced_json, tempo=tempo)
    log(f"[pace] {d['raw_words_per_s']} -> {d['paced_words_per_s']} words/s  ({d['raw_duration']:.1f}s raw -> {d['duration_seconds']:.1f}s)")
    nar = dict(segments=[dict(id=s["beat_id"], text=s["text"], start=s["start_seconds"], end=s["end_seconds"], words=s["words"]) for s in d["segments"]],
               audio=os.path.relpath(paced_wav, ROOT), tts=tts, tempo=tempo)
    plan = SD.build_plan(nar, seed=seed, tts=tts)
    plan["narration"]["pacing"] = {k: d[k] for k in ("raw_duration", "raw_words_per_s", "paced_words_per_s", "gap_cap", "beat_gap", "tempo")}
    return short.render_film(plan, OUT, log, samples=samples)


def from_plan(path, log=print, samples=10):
    plan = json.load(open(path, encoding="utf-8"))
    return short.render_film(plan, os.path.dirname(os.path.abspath(path)), log, samples=samples)
