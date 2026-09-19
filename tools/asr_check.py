"""Intelligibility check for a TTS narration: transcribe with Whisper (local, Hindi) and compare with the script (character error rate).
Run with the TTS python (pyenv 3.12.0):  PYTHONPATH=.vendor_py python tools/asr_check.py narration.wav script.txt [model=small]"""
import difflib, json, re, sys, unicodedata
import whisper

def norm(s):
    s = unicodedata.normalize("NFC", s)
    return re.sub(r"[\s\"'“”‘’,.;:!?।…\-–—()\[\]]+", "", s).lower()

wav, script = sys.argv[1], sys.argv[2]
model = sys.argv[3] if len(sys.argv) > 3 else "small"
m = whisper.load_model(model)
r = m.transcribe(wav, language="hi", fp16=False, condition_on_previous_text=False)
ref = norm(open(script, encoding="utf-8").read().replace("#", ""))
hyp = norm(r["text"])
sm = difflib.SequenceMatcher(None, ref, hyp)
print("ASR:", r["text"].strip()[:600])
print("RESULT", json.dumps(dict(similarity=round(sm.ratio(), 3), ref_chars=len(ref), hyp_chars=len(hyp))))
