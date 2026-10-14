#!/usr/bin/env python3
"""Local Chatterbox Multilingual (Hindi) TTS adapter for infographics-motion.

Contract: invoked as `chatterbox_tts.py <job.json>` where job.json is written
by src/generate-voice.ts. Produces a single WAV narration file at
job.output_path by generating one clip per beat segment (voice-cloned from a
reference WAV), trimming Chatterbox's own excess boundary silence, applying a
tempo pass to hit a natural conversational pace, and concatenating with a
short breath pad. Also writes a `<output>.segments.json` sidecar with each
segment's precise start/end time in the final file, used as rough alignment
bounds by tools/whisper_align.py.

Requires: chatterbox-tts, torch, soundfile (already installed in the pyenv
3.12.0 environment used by other local video pipelines on this machine).
"""
import json
import subprocess
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent
DEFAULT_REFERENCE = REPO_ROOT / "assets" / "reference-voices" / "hindi-male-narrator.wav"

SILENCE_PAD_SECONDS = 0.18
TRIM_THRESHOLD = 0.01  # preserve quieter consonants and sentence tails
TRIM_MARGIN_SECONDS = 0.06
# Post-generation tempo multiplier (ffmpeg atempo): values above 1.0 make speech faster.
# Keep the default Reel-forward; preset-specific values from engine/shorts/voice.py override it.
# Audio splicing is confidence-gated in whisper_align.py so speed is not achieved by risking
# cuts through unaligned speech. 1.0 disables tempo processing.
import os as _os
TEMPO = float(_os.environ.get("TTS_ATEMPO", "1.08"))


def log(message: str) -> None:
    print(f"[chatterbox_tts] {message}", file=sys.stderr, flush=True)


def trim_silence(clip, sr: int, threshold: float = TRIM_THRESHOLD, margin: float = TRIM_MARGIN_SECONDS):
    import numpy as np
    mag = np.abs(clip)
    peak = mag.max() if mag.size else 0.0
    if peak <= 0:
        return clip
    loud = mag > (peak * threshold)
    if not loud.any():
        return clip
    idx = np.nonzero(loud)[0]
    margin_samples = int(margin * sr)
    start = max(0, idx[0] - margin_samples)
    end = min(len(clip), idx[-1] + margin_samples)
    return clip[start:end]


def main() -> int:
    if len(sys.argv) < 2:
        log("usage: chatterbox_tts.py <job.json>")
        return 2

    job_path = Path(sys.argv[1])
    job = json.loads(job_path.read_text(encoding="utf-8"))

    segments = job.get("segments") or []
    if not segments:
        log("no narration segments in job")
        return 1

    output_path = Path(job["output_path"])
    output_path.parent.mkdir(parents=True, exist_ok=True)

    reference_audio = (job.get("reference_audio") or "").strip()
    reference_path = Path(reference_audio) if reference_audio else DEFAULT_REFERENCE
    if not reference_path.exists():
        log(f"reference voice not found: {reference_path}")
        return 1

    # Reels storytelling defaults: prioritize intelligibility, controlled emphasis, and consistent delivery.
    exaggeration = float(job.get("exaggeration", 0.60))
    cfg_weight = float(job.get("cfg_weight", 0.35))
    temperature = float(job.get("temperature", 0.55))
    tempo = float(job.get("tempo", TEMPO))
    silence_pad_seconds = float(job.get("silence_pad_seconds", SILENCE_PAD_SECONDS))
    performance_mode = bool(job.get("performance_mode", False))
    expression_intensity = max(0, min(100, int(job.get("expression_intensity", 65))))
    seed = int(job.get("seed", 42))
    if not 0.0 <= exaggeration <= 1.5:
        log("exaggeration must be between 0 and 1.5")
        return 2
    if not 0.0 <= cfg_weight <= 1.0:
        log("cfg_weight must be between 0 and 1")
        return 2
    if not 0.1 <= temperature <= 2.0:
        log("temperature must be between 0.1 and 2")
        return 2
    if not 0.5 <= tempo <= 1.1:
        log("tempo must be between 0.5 and 1.1")
        return 2
    if not 0.0 <= silence_pad_seconds <= 0.6:
        log("silence_pad_seconds must be between 0 and 0.6")
        return 2

    import numpy as np
    import soundfile as sf
    import torch
    import inspect
    import importlib.metadata
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    try:
        package_version = importlib.metadata.version("chatterbox-tts")
    except importlib.metadata.PackageNotFoundError:
        package_version = "unknown"
    loader = ChatterboxMultilingualTTS.from_pretrained
    try:
        selector_available = "t3_model" in inspect.signature(loader).parameters
    except (TypeError, ValueError):
        selector_available = False
    requested_selector = "v3" if selector_available else None
    model_variant = str(job.get("model_variant") or _os.environ.get("CHATTERBOX_MODEL_VARIANT", "multilingual_v3")).strip().lower()
    if model_variant not in {"multilingual_v3", "dedicated_hindi"}:
        log(f"unknown model_variant={model_variant!r}; use multilingual_v3 or dedicated_hindi")
        return 2
    hindi_checkpoint = Path(_os.environ.get(
        "CHATTERBOX_HINDI_T3_CHECKPOINT",
        str(REPO_ROOT / "models" / "chatterbox-hindi" / "t3_hi.safetensors"),
    )).expanduser()
    log(f"CONFIG device={device} package=chatterbox-tts@{package_version} class={ChatterboxMultilingualTTS.__module__}.{ChatterboxMultilingualTTS.__name__}")
    log(f"CONFIG language_id=hi reference={reference_path} reference_exists={reference_path.exists()}")
    log(f"CONFIG model_variant={model_variant} checkpoint_selector={requested_selector or 'not supported by installed loader; package default will be used'}")
    if model_variant == "dedicated_hindi":
        log(f"CONFIG dedicated_hindi_checkpoint={hindi_checkpoint} exists={hindi_checkpoint.is_file()}")
        if not hindi_checkpoint.is_file():
            log("Dedicated Hindi checkpoint not found. Download t3_hi.safetensors or set CHATTERBOX_HINDI_T3_CHECKPOINT.")
            return 1

    t0 = time.time()
    # Start with the compatible shared V3 architecture/assets. For the Hindi
    # variant, replace only its T3 weights with the dedicated Hindi fine-tune.
    try:
        if selector_available:
            model = loader(device=device, t3_model="v3")
            selector_used = "v3"
        else:
            model = loader(device=device)
            selector_used = "installed-default"
    except (TypeError, ValueError) as exc:
        log(f"V3 selector call failed ({exc}); loading installed default checkpoint")
        model = loader(device=device)
        selector_used = "installed-default-after-selector-failure"

    if model_variant == "dedicated_hindi":
        try:
            from safetensors.torch import load_file
            state_dict = load_file(str(hindi_checkpoint), device="cpu")
            incompatible = model.t3.load_state_dict(state_dict, strict=True)
            if incompatible.missing_keys or incompatible.unexpected_keys:
                raise RuntimeError(
                    f"checkpoint keys mismatch: missing={incompatible.missing_keys[:8]}, "
                    f"unexpected={incompatible.unexpected_keys[:8]}"
                )
            selector_used = "dedicated-hindi-t3"
            log("MODEL dedicated Hindi T3 weights loaded successfully")
        except Exception as exc:
            log(f"failed to load dedicated Hindi checkpoint into installed Chatterbox T3 architecture: {exc}")
            log("No fallback will be used; fix the checkpoint/package compatibility before retrying.")
            return 1

    def _class_name(value):
        cls = type(value)
        return f"{cls.__module__}.{cls.__name__}"

    submodels = {}
    for attr in ("t3", "s3gen", "ve", "tokenizer", "conds"):
        try:
            value = getattr(model, attr, None)
            if value is not None:
                submodels[attr] = _class_name(value)
        except Exception:
            pass
    model_info = {
        "model_family": "ChatterboxMultilingualTTS",
        "model_variant": model_variant,
        "loader_class": f"{ChatterboxMultilingualTTS.__module__}.{ChatterboxMultilingualTTS.__name__}",
        "package_version": package_version,
        "device": device,
        "language_id": "hi",
        "selector_requested": requested_selector,
        "selector_used": selector_used,
        "dedicated_hindi_checkpoint": model_variant == "dedicated_hindi",
        "dedicated_hindi_checkpoint_path": str(hindi_checkpoint.resolve()) if model_variant == "dedicated_hindi" else None,
        "checkpoint_note": ("Dedicated ResembleAI/Chatterbox-Multilingual-hi T3 weights loaded into the shared V3 architecture." if model_variant == "dedicated_hindi" else "Multilingual Chatterbox V3 with Hindi language_id; not the dedicated Hindi fine-tune."),
        "sample_rate": int(getattr(model, "sr", 0) or 0),
        "reference_audio": str(reference_path.resolve()),
        "reference_bytes": reference_path.stat().st_size if reference_path.exists() else None,
        "reference_mtime": reference_path.stat().st_mtime if reference_path.exists() else None,
        "submodels": submodels,
        "settings": {
            "tempo": tempo, "exaggeration": exaggeration, "cfg_weight": cfg_weight,
            "temperature": temperature, "silence_pad_seconds": silence_pad_seconds,
            "seed": seed, "group_lines": bool(job.get("group_lines", False)),
            "performance_mode": performance_mode, "expression_intensity": expression_intensity,
            "group_max_lines": int(job.get("group_max_lines", 5)),
            "group_max_words": int(job.get("group_max_words", 45)),
        },
    }
    info_path = output_path.with_name("model_info.json")
    info_path.write_text(json.dumps(model_info, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"MODEL family={model_info['model_family']} selector={selector_used} dedicated_hindi_checkpoint={model_info['dedicated_hindi_checkpoint']} sample_rate={model_info['sample_rate']} submodels={submodels}")
    log(f"MODEL_INFO path={info_path}")
    log(f"model loaded in {time.time() - t0:.1f}s")

    pad = np.zeros(int(silence_pad_seconds * model.sr), dtype=np.float32)
    clips: list[np.ndarray] = []
    # (beat_id, text, start_seconds, end_seconds) at the pre-tempo sample rate/timeline.
    raw_segments: list[dict] = []
    cursor_samples = 0

    group_lines = bool(job.get("group_lines", False))
    group_max_lines = max(1, int(job.get("group_max_lines", 3)))
    group_max_words = max(1, int(job.get("group_max_words", 34)))
    groups: list[tuple[list[dict], str]] = []
    current: list[dict] = []
    current_words = 0
    current_performance = "default"
    for segment in segments:
        segment_text = (segment.get("text") or "").strip()
        if not segment_text:
            continue
        performance = str(segment.get("performance") or "default").lower() if performance_mode else "default"
        if performance not in {"hook", "curious", "suspense", "reveal", "explain", "urgent", "calm", "emphasis", "confident", "warm", "concerned", "shocked", "reflective", "playful", "default"}:
            performance = "default"
        word_count = max(len(segment_text.split()), 1)
        # Keep neighboring narration cues in the same take unless a safe chunk
        # boundary is reached. Splitting on every emotion tag causes audible resets
        # in pitch, rhythm and breath. The group's settings are blended below.
        limit_reached = group_lines and (len(current) >= group_max_lines or current_words + word_count > group_max_words)
        if current and limit_reached:
            groups.append((current, current_performance))
            current, current_words = [], 0
        if not current:
            current_performance = performance
        current.append(segment)
        current_words += word_count
    if current:
        groups.append((current, current_performance))

    # These are app-level delivery profiles, NOT native emotion tokens or guarantees.
    # They only blend controls supported by the installed multilingual/dedicated-Hindi
    # Chatterbox architecture. Voice reference, text, and context still dominate.
    performance_targets = {
        # Conservative parameter directions, not guaranteed semantic emotions.
        "hook": (0.78, 0.30, 0.55),
        "curious": (0.62, 0.34, 0.50),
        "suspense": (0.66, 0.32, 0.48),
        "reveal": (0.82, 0.30, 0.58),
        "explain": (0.50, 0.40, 0.45),
        "urgent": (0.78, 0.30, 0.52),
        "calm": (0.48, 0.40, 0.45),
        "emphasis": (0.84, 0.30, 0.58),
        "confident": (0.65, 0.34, 0.48),
        "warm": (0.58, 0.36, 0.48),
        "concerned": (0.65, 0.34, 0.50),
        "shocked": (0.85, 0.30, 0.62),
        "reflective": (0.52, 0.38, 0.46),
        "playful": (0.72, 0.33, 0.60),
    }
    blend = expression_intensity / 100.0

    for group_index, (group, performance) in enumerate(groups):
        combined_text = " ".join((segment.get("text") or "").strip() for segment in group)
        torch.manual_seed(seed + group_index)
        t1 = time.time()
        take_exaggeration, take_cfg, take_temperature = exaggeration, cfg_weight, temperature
        if performance_mode:
            # Blend cues in a connected take by word count. This keeps an overall
            # emotional direction without a separate TTS reset for every cue marker.
            weighted_targets = []
            for segment in group:
                cue = str(segment.get("performance") or "default").lower()
                target = performance_targets.get(cue, (exaggeration, cfg_weight, temperature))
                weight = max(len((segment.get("text") or "").split()), 1)
                weighted_targets.append((target, weight))
            total_weight = sum(weight for _, weight in weighted_targets) or 1
            target_exaggeration = sum(target[0] * weight for target, weight in weighted_targets) / total_weight
            target_cfg = sum(target[1] * weight for target, weight in weighted_targets) / total_weight
            target_temperature = sum(target[2] * weight for target, weight in weighted_targets) / total_weight
            take_exaggeration = exaggeration + (target_exaggeration - exaggeration) * blend
            take_cfg = cfg_weight + (target_cfg - cfg_weight) * blend
            take_temperature = temperature + (target_temperature - temperature) * blend
        wav = model.generate(
            combined_text,
            language_id="hi",
            audio_prompt_path=str(reference_path),
            exaggeration=take_exaggeration,
            cfg_weight=take_cfg,
            temperature=take_temperature,
        )
        clip = trim_silence(wav.squeeze(0).detach().cpu().numpy().astype(np.float32), model.sr)
        chunk_start = cursor_samples / model.sr
        chunk_duration = len(clip) / model.sr
        clips.append(clip)
        weights = [max(len((segment.get("text") or "").split()), 1) for segment in group]
        total_weight = sum(weights) or 1
        cumulative = 0
        # Approximate line bounds; WhisperX aligns the original script afterwards.
        for segment, weight in zip(group, weights):
            raw_start = chunk_start + chunk_duration * cumulative / total_weight
            cumulative += weight
            raw_end = chunk_start + chunk_duration * cumulative / total_weight
            raw_segments.append({
                "beat_id": segment.get("beat_id", str(len(raw_segments))),
                "text": (segment.get("text") or "").strip(),
                "start_seconds": round(max(chunk_start, raw_start - 0.18), 3),
                "end_seconds": round(min(chunk_start + chunk_duration, raw_end + 0.18), 3),
            })
        cursor_samples += len(clip)
        if group_index < len(groups) - 1:
            clips.append(pad)
            cursor_samples += len(pad)
        log(f"take {group_index + 1}/{len(groups)} [{performance}] (exaggeration={take_exaggeration:.2f}, cfg={take_cfg:.2f}, temp={take_temperature:.2f}; {len(group)} line(s), {len(combined_text.split())} words): {chunk_duration:.2f}s in {time.time() - t1:.1f}s")
    if not clips:
        log("no audio generated")
        return 1

    full = np.concatenate(clips)
    pre_tempo_path = output_path if tempo == 1.0 else output_path.with_suffix(".pretempo.wav")
    sf.write(str(pre_tempo_path), full, model.sr)

    if tempo != 1.0:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", str(pre_tempo_path), "-filter:a", f"atempo={tempo}", str(output_path)],
            capture_output=True, text=True,
        )
        pre_tempo_path.unlink(missing_ok=True)
        if result.returncode != 0 or not output_path.exists():
            log(f"ffmpeg atempo failed ({result.returncode}): {result.stderr.strip()[-500:]}")
            return 1
        for seg in raw_segments:
            seg["start_seconds"] = round(seg["start_seconds"] / tempo, 3)
            seg["end_seconds"] = round(seg["end_seconds"] / tempo, 3)

    total_words = sum(len(s["text"].split()) for s in raw_segments)
    final_duration = (cursor_samples / model.sr) / tempo
    wpm = total_words / (final_duration / 60) if final_duration > 0 else 0
    log(f"wrote {output_path} ({final_duration:.2f}s total, {total_words} words, ~{wpm:.0f} WPM)")

    segments_sidecar = output_path.with_name(output_path.name + ".segments.json")
    segments_sidecar.write_text(json.dumps({"segments": raw_segments, "duration_seconds": final_duration}, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"segment timing: {segments_sidecar}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
