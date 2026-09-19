"""Chatterbox Hindi TTS per beat + whisperx alignment -> raw wav + segments json.   .venv/bin/python tools/tts_beats.py beats.json out_base"""
import json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.shorts import voice
beats = json.load(open(sys.argv[1], encoding="utf-8"))
base = sys.argv[2]
v = voice.synthesize(beats, seed=42)
key = voice._key(beats, 42)
shutil.copy(os.path.join(voice.VOICE_DIR, key, "narration.wav"), base + ".wav")
json.dump(dict(segments=[dict(beat_id=x["id"], text=x["text"], start_seconds=round(x["start"], 3), end_seconds=round(x["end"], 3),
                              words=[dict(word=w["word"], start=round(w["start"], 3), end=round(w["end"], 3)) for w in x["words"]]) for x in v["beats"]],
               duration_seconds=round(v["duration"], 3)), open(base + ".wav.segments.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("DONE", v["duration"])
