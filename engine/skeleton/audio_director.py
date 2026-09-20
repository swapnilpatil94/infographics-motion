"""AUDIO DIRECTOR: plan -> mix, deterministic (numpy synthesis, seeded by the story; no AI-music dependency, no downloaded audio).

  narration   the supplied paced narration audio (Chatterbox Hindi or any other voice) - always the loudest element, everything else ducks under it
  ambience    per SCENE (location + time of day): room tone / crickets / birds / traffic / crowd murmur / HVAC hum / machine hum, cross-faded at the scene cuts
  music       per MOOD segment: synthesized pad + a sparse melodic pluck (warm / relief / isolated) or a low pulse (fear / pressure), tied to the story's mood_track
  sfx/foley   from the plan's sfx hooks AND from the actions themselves: footsteps, cloth on stand/sit, paper, cash, keypad beeps, card slide, typing, cup clink, phone buzz / ding, heartbeat, impacts
  master      FFmpeg loudnorm (-16 LUFS) + true-peak limiter; `report()` measures speech-to-bed ratio, peak, clipped samples, silence, and duration match (QC gates read it)

`mix(plan, actors_events, out_dir)` is content-hash cached: an audio-only change (or a music/foley change) re-mixes without touching a single video frame.
"""
import hashlib
import json
import math
import os
import subprocess

import numpy as np

from engine.shorts import audio as A

SR = A.SR
GAIN = dict(music=0.30, ambience=0.55, sfx=0.55, narration_peak=0.72)
DUCK_DB = 7.0

AMBIENCE = {                                          # location -> layers (day / night variants resolved in `ambience`)
    "bedroom": dict(room=0.7, crickets="night", birds="day", traffic=0.15), "study": dict(room=0.7, crickets="night", birds="day", traffic=0.12), "living_room": dict(room=0.8, birds="day", crickets="night", traffic=0.2, clock=1),
    "office": dict(room=0.6, hum=0.6, murmur=0.3, keys=1), "classroom": dict(room=0.5, murmur=0.35, birds="day"), "cafe": dict(room=0.4, murmur=0.8, clink=1, traffic=0.15),
    "bank": dict(room=0.4, hum=0.5, murmur=0.35, keys=1), "shop": dict(room=0.4, murmur=0.4, traffic=0.25), "police": dict(room=0.5, hum=0.5, murmur=0.3, keys=1),
    "atm": dict(room=0.2, hum=0.5, traffic=0.5, crickets="night"), "call_center": dict(room=0.3, hum=0.4, murmur=0.9, keys=1), "street": dict(room=0.1, traffic=0.9, birds="day", crickets="night", murmur=0.2)}


def _rng(*k):
    return np.random.default_rng(int(hashlib.sha1("|".join(map(str, k)).encode()).hexdigest()[:8], 16))


def _norm(x, peak=1.0):
    return (x / (np.abs(x).max() + 1e-9) * peak).astype(np.float32)


def _noise(n, rng, lo, hi):
    return _norm(A._filt(rng.standard_normal(n).astype(np.float32), "band", lo, hi))


def _slow(n, rng, hz=0.2):
    t = np.arange(n) / SR
    return 0.5 + 0.5 * np.sin(2 * math.pi * hz * t + rng.uniform(0, 6.28))


def murmur(dur, rng, density=0.6):
    """crowd talk: three band-shaped 'voices' with syllable-rate amplitude bursts (unintelligible by construction)"""
    n = int(dur * SR)
    out = np.zeros(n, np.float32)
    for v in range(3):
        base = _noise(n, rng, 180 + 90 * v, 2600 + 300 * v)
        t = np.arange(n) / SR
        env = np.zeros(n, np.float32)
        tt = rng.uniform(0, 1)
        while tt < dur:
            L = rng.uniform(0.6, 2.4)
            syl = 0.5 + 0.5 * np.sin(2 * math.pi * rng.uniform(3.0, 6.0) * (t[int(tt * SR):int(min(dur, tt + L) * SR)] - tt))
            seg = syl * np.hanning(len(syl))
            env[int(tt * SR):int(tt * SR) + len(seg)] += seg[:max(0, n - int(tt * SR))]
            tt += L + rng.uniform(0.8, 3.5) / max(density, 0.1)
        out += base * env
    return _norm(out, 0.6)


def crickets(dur, rng):
    n = int(dur * SR)
    t = np.arange(n) / SR
    gate = (np.sin(2 * math.pi * 3.2 * t + rng.uniform(0, 6)) > 0.55) * _slow(n, rng, 0.11)
    return (np.sin(2 * math.pi * 4300 * t + 3 * np.sin(2 * math.pi * 40 * t)) * gate * 0.5).astype(np.float32)


def birds(dur, rng):
    n = int(dur * SR)
    out = np.zeros(n, np.float32)
    tt = rng.uniform(1, 4)
    while tt < dur - 0.6:
        m = int(rng.uniform(0.12, 0.3) * SR)
        f0 = rng.uniform(2400, 4200)
        ph = np.cumsum(2 * math.pi * (f0 + 900 * np.sin(2 * math.pi * rng.uniform(6, 14) * np.arange(m) / SR)) / SR)
        chirp = np.sin(ph) * np.hanning(m) * 0.5
        for k in range(int(rng.integers(2, 5))):
            i = int((tt + k * 0.22) * SR)
            if i + m < n:
                out[i:i + m] += chirp
        tt += rng.uniform(4, 11)
    return out


def traffic(dur, rng):
    n = int(dur * SR)
    bed = _noise(n, rng, 60, 700) * (0.55 + 0.45 * _slow(n, rng, 0.06))
    t = np.arange(n) / SR
    for _ in range(max(1, int(dur / 9))):                                               # car pass-bys: swelling band noise
        c = rng.uniform(1, max(dur - 3, 2))
        env = np.exp(-((t - c) / 1.1) ** 2)
        bed += _noise(n, rng, 120, 1400) * env * 0.9
    return _norm(bed, 0.7)


def hum(dur, rng, f=100.0):
    t = np.arange(int(dur * SR)) / SR
    return (0.5 * np.sin(2 * math.pi * f * t) + 0.25 * np.sin(2 * math.pi * 2 * f * t) + 0.08 * np.sin(2 * math.pi * 3 * f * t)).astype(np.float32) * 0.6


def clock(dur):
    n = int(dur * SR)
    out = np.zeros(n, np.float32)
    tk = A.tick() * 0.5
    for s in np.arange(0.5, dur, 1.0):
        i = int(s * SR)
        out[i:i + len(tk)] += tk[:max(0, n - i)] * (1.0 if int(s) % 2 else 0.8)
    return out


def _events(dur, rng, rate, fn, gain):
    n = int(dur * SR)
    out = np.zeros(n, np.float32)
    tt = rng.uniform(0.5, 3)
    while tt < dur - 1:
        s = fn(rng) * gain
        i = int(tt * SR)
        out[i:i + len(s)] += s[:max(0, n - i)]
        tt += rng.exponential(1.0 / rate)
    return out


def _clink(rng):
    m = int(0.35 * SR)
    t = np.arange(m) / SR
    f = rng.uniform(2200, 3600)
    return (np.sin(2 * math.pi * f * t) * np.exp(-t / 0.07) * 0.4 + np.sin(2 * math.pi * f * 1.51 * t) * np.exp(-t / 0.05) * 0.2).astype(np.float32)


def _keys(rng):
    n = int(0.9 * SR)
    out = np.zeros(n, np.float32)
    tk = A.tick()
    for k in range(int(rng.integers(4, 12))):
        i = int(rng.uniform(0, 0.8) * SR)
        out[i:i + len(tk)] += tk[:max(0, n - i)] * rng.uniform(0.4, 1.0)
    return out


def ambience(plan, seed=None):
    """scene-wise ambience bed for the whole film, cross-faded at scene cuts"""
    dur = plan["duration"]
    n = int(dur * SR)
    out = np.zeros(n + SR, np.float32)
    scenes = plan.get("scenes") or [dict(loc="bedroom", time="night", t0=0.0, t1=dur)]
    fade = int(0.6 * SR)
    for k, sc in enumerate(scenes):
        t0, t1 = sc["t0"], (dur if k == len(scenes) - 1 else sc["t1"])
        L = t1 - t0 + 1.4
        rng = _rng(plan["story_id"], "amb", k, sc["loc"], sc["time"])
        prof = AMBIENCE.get(sc["loc"], AMBIENCE["bedroom"])
        m = int(L * SR)
        bed = np.zeros(m, np.float32)
        bed += A.room_tone(L, seed=int(rng.integers(1, 99))) * 6.0 * prof.get("room", 0.5)
        if prof.get("traffic"):
            bed += traffic(L, rng)[:m] * 0.22 * prof["traffic"] * (1.0 if sc["loc"] in ("street", "atm") else 0.4)
        if prof.get("murmur"):
            bed += murmur(L, rng, prof["murmur"])[:m] * 0.32 * prof["murmur"]
        if prof.get("hum"):
            bed += hum(L, rng, 100.0)[:m] * 0.05 * prof["hum"]
        if prof.get("crickets") == sc["time"]:
            bed += crickets(L, rng)[:m] * 0.11
        if prof.get("birds") == sc["time"]:
            bed += birds(L, rng)[:m] * 0.14
        if prof.get("clock") and sc["time"] != "night":
            bed += clock(L)[:m] * 0.12
        if prof.get("clink"):
            bed += _events(L, rng, 0.35, _clink, 0.10)[:m]
        if prof.get("keys"):
            bed += _events(L, rng, 0.25, _keys, 0.07)[:m]
        env = np.ones(m, np.float32)
        env[:fade] = np.linspace(0, 1, fade) if k else 1.0
        env[-fade:] = np.linspace(1, 0, fade)
        i0 = int(t0 * SR)
        i0 = max(0, i0 - (fade if k else 0))
        seg = (bed * env)[:len(out) - i0]
        out[i0:i0 + len(seg)] += seg
    return out[:n]


# ------------------------------------------------------------------------------------------------------------------ music
SCALES = {"warm": [0, 2, 4, 7, 9], "relief": [0, 2, 4, 7, 9], "bright": [0, 2, 4, 7, 9], "isolated": [0, 3, 5, 7, 10], "dim": [0, 3, 7, 10], "neutral": [0, 2, 5, 7, 9], "formal": [0, 2, 5, 7]}


def _pluck(f, dur=1.2):
    t = np.arange(int(dur * SR)) / SR
    return ((np.sin(2 * math.pi * f * t) + 0.35 * np.sin(2 * math.pi * 2 * f * t)) * np.exp(-t / 0.42) * np.minimum(t / 0.004, 1)).astype(np.float32) * 0.3


def music(plan):
    from engine.factory import audio_pipeline as AP
    dur = plan["duration"]
    mt = [tuple(m) for m in plan["mood_track"]]
    bed = AP.underscore(dur, mt, seed=int(_rng(plan["story_id"], "music").integers(1, 999)))
    n = len(bed)
    out = bed.copy()
    for k, (t0, t1, mood) in enumerate(mt):
        rng = _rng(plan["story_id"], "mel", k)
        if mood in SCALES:                                                        # sparse melodic pluck over the pad
            root = {"warm": 261.63, "relief": 261.63, "bright": 261.63, "isolated": 220.0, "dim": 196.0, "neutral": 220.0, "formal": 196.0}[mood]
            tt = t0 + 0.4
            step = {"isolated": 1.9, "dim": 1.6}.get(mood, 1.05)
            while tt < t1 - 0.3:
                f = root * 2 ** (int(rng.choice(SCALES[mood])) / 12) * (2 if rng.random() > 0.55 else 1)
                p = _pluck(f)
                i = int(tt * SR)
                out[i:i + len(p)] += p[:max(0, n - i)] * (0.55 if mood in ("dim", "isolated") else 0.8)
                tt += step * rng.uniform(0.85, 1.25)
        if mood in ("fear", "pressure"):                                          # low pulse rising in the shot
            tt, bpm = t0, 84 if mood == "fear" else 72
            while tt < t1:
                i = int(tt * SR)
                tk = np.arange(int(0.35 * SR)) / SR
                thump = np.sin(2 * math.pi * (52 - 14 * tk) * tk) * np.exp(-tk / 0.12) * 0.5
                out[i:i + len(thump)] += thump[:max(0, n - i)] * (0.5 + 0.5 * (tt - t0) / max(t1 - t0, 1e-3))
                tt += 60.0 / bpm
    return _norm(out, 0.8) * 0.9


# ------------------------------------------------------------------------------------------------------------------ foley
def _cloth(seed=1):
    r = np.random.default_rng(seed)
    n = int(0.22 * SR)
    t = np.arange(n) / SR
    return (A._filt(r.standard_normal(n).astype(np.float32), "band", 300, 2600) * np.sin(math.pi * t / 0.22) ** 2 * 0.09).astype(np.float32)


def _paper(seed=2):
    r = np.random.default_rng(seed)
    n = int(0.45 * SR)
    t = np.arange(n) / SR
    env = (np.sin(math.pi * t / 0.45) ** 2) * (0.6 + 0.4 * r.random(n // 400 + 1).repeat(400)[:n])
    return (A._filt(r.standard_normal(n).astype(np.float32), "band", 1800, 8000) * env * 0.08).astype(np.float32)


def _cash(seed=3):
    r = np.random.default_rng(seed)
    n = int(0.5 * SR)
    out = np.zeros(n, np.float32)
    for k in range(int(r.integers(3, 6))):
        m = int(0.07 * SR)
        s = A._filt(r.standard_normal(m).astype(np.float32), "band", 2500, 9000) * np.exp(-np.arange(m) / SR / 0.02) * 0.09
        i = int(k * 0.09 * SR)
        out[i:i + m] += s
    return out


def _beep():
    t = np.arange(int(0.09 * SR)) / SR
    return (np.sin(2 * math.pi * 1760 * t) * np.minimum(t / 0.004, 1) * np.exp(-t / 0.05) * 0.14).astype(np.float32)


def _card(seed=4):
    r = np.random.default_rng(seed)
    n = int(0.3 * SR)
    t = np.arange(n) / SR
    return (A._filt(r.standard_normal(n).astype(np.float32), "band", 1500, 6000) * (t / 0.3) * np.exp(-t / 0.16) * 0.09).astype(np.float32)


def _chair():
    n = int(0.4 * SR)
    t = np.arange(n) / SR
    r = np.random.default_rng(6)
    return (A._filt(r.standard_normal(n).astype(np.float32), "band", 120, 900) * np.sin(math.pi * t / 0.4) * 0.09 + np.sin(2 * math.pi * (180 + 60 * t) * t) * np.exp(-t / 0.12) * 0.04).astype(np.float32)


def _cup():
    return _clink(np.random.default_rng(7)) * 0.45


FOLEY = dict(cloth=_cloth, paper=_paper, cash=_cash, beep=_beep, card=_card, chair=_chair, cup=_cup, tick=A.tick, footstep=A.footstep)
PROP_SOUND = dict(phone="tick", document="paper", money="cash", card="card", cup="cup", bag="cloth", laptop="tick")


def foley_events(plan, perf_events=None):
    """[(t, kind, gain)] derived from the actions in the plan (+ the runtime's own walk / grab events when given)"""
    ev = []
    seen = set()
    for s in plan["shots"]:
        for x in s.get("actions", []):
            key = (x["char"], x["action"], x["t"])
            if key in seen:
                continue
            seen.add(key)
            t, d, a = x["t"], x.get("dur", 0.5), x["action"]
            prop = (x.get("prop") or "").lower()
            g = 1.0 if x["char"] == "A" else 0.8
            if a in ("stand", "sit"):
                ev += [(t + 0.05, "cloth", g), (t + (0.1 if a == "stand" else d * 0.75), "chair", 0.9 * g)]
            elif a in ("grab", "receive", "release", "hand_over"):
                ev.append((t + (0.05 if a != "release" else 0.0), PROP_SOUND.get(prop, "cloth"), g))
            elif a == "prop_cycle":
                if prop == "atm":
                    ev += [(t + 0.7 + 0.42 * k, "beep", 0.8) for k in range(4)] + [(t + 0.2, "card", 0.9), (t + d - 0.9, "card", 0.8)]
                elif prop == "money":
                    ev += [(t + 0.3 + 0.55 * k, "cash", 0.9) for k in range(max(1, int((d - 0.4) / 0.55)))]
                elif prop == "document":
                    ev += [(t + 0.2, "paper", 0.9), (t + d * 0.5, "paper", 0.7)]
                elif prop == "laptop":
                    ev += [(t + 0.3 + 0.13 * k, "tick", 0.5 + 0.3 * ((k * 7) % 3) / 2) for k in range(int(max(d - 0.4, 0.5) / 0.13))]
            elif a in ("realization", "flinch", "fear", "relief", "gesture", "notice"):
                ev.append((t + 0.1, "cloth", 0.7 * g))
    for t, kind, g in ((s["t"], s["kind"], s["gain"]) for s in plan.get("sfx", [])):
        ev.append((t, kind, g))
    for t, kind, g in perf_events or []:
        ev.append((t, kind, g))
    return sorted((round(t, 3), k, round(g, 3)) for t, k, g in ev if 0 <= t < plan["duration"])


# ------------------------------------------------------------------------------------------------------------------ mix
def _hash(plan, perf_events, narration_path):
    core = dict(story=plan["story_id"], dur=plan["duration"], scenes=plan.get("scenes"), mood=plan["mood_track"], sfx=plan.get("sfx"), foley=foley_events(plan, perf_events), gains={**GAIN, **plan.get('audio_cfg', {})}, duck=DUCK_DB, v="ad-1")
    nb = open(narration_path, "rb").read() if narration_path and os.path.exists(narration_path) else b""
    return hashlib.sha1(json.dumps(core, sort_keys=True, default=list).encode() + hashlib.sha1(nb).digest()).hexdigest()[:16]


def render_stems(plan, narration, perf_events=None):
    dur = plan["duration"]
    n = int(dur * SR)
    fit = lambda a: np.pad(a, (0, max(0, n - len(a))))[:n]
    G = {**GAIN, **plan.get("audio_cfg", {})}
    nar = fit(narration.astype(np.float32))
    nar = nar * (G["narration_peak"] / max(float(np.abs(nar).max()), 1e-6))
    amb = fit(ambience(plan)) * G["ambience"]
    mus = fit(music(plan)) * G["music"]
    m = A.Mix(dur + 1.0)
    kinds = {"ding": A.ding, "buzz": A.buzz, "heartbeat": A.heartbeat, "impact": A.impact, "whoosh": A.whoosh, **FOLEY}
    for t, kind, g in foley_events(plan, perf_events):
        if kind in kinds and g > 0:
            m.add(t, kinds[kind](), g * G["sfx"])
    sfx = fit(m.buf)
    return nar, amb, mus, sfx


def _speech_envelope(nar):
    blk = int(0.05 * SR)
    nb = len(nar) // blk
    rms = np.sqrt((nar[:nb * blk].reshape(nb, blk) ** 2).mean(axis=1))
    rms = np.convolve(rms, np.ones(6) / 6, mode="same")
    act = np.clip(rms / (rms.max() + 1e-9) * 5.0, 0, 1)
    return np.pad(np.repeat(act, blk), (0, max(0, len(nar) - nb * blk)), mode="edge")[:len(nar)]


def mix(plan, narration, out_dir, perf_events=None, narration_path=None, cache_root=None):
    """-> (wav path, report dict). Cached by content hash (`cache_root`, default output/cache/audio)."""
    from engine.shorts.raster import ROOT
    cache = os.path.join(cache_root or os.path.join(ROOT, "output/cache/audio"))
    os.makedirs(cache, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    h = _hash(plan, perf_events, narration_path)
    cw, cj = os.path.join(cache, h + ".wav"), os.path.join(cache, h + ".json")
    if os.path.exists(cw) and os.path.exists(cj):
        rep = json.load(open(cj))
        rep["cache_hit"] = True
        return cw, rep
    nar, amb, mus, sfx = render_stems(plan, narration, perf_events)
    act = _speech_envelope(nar)
    duck = 1.0 - (1.0 - 10 ** (-DUCK_DB / 20)) * np.convolve(act, np.ones(int(0.25 * SR)) / int(0.25 * SR), mode="same")
    bed = (amb + mus) * duck + sfx * (1.0 - 0.35 * act)
    raw = np.clip(nar + bed, -1.0, 1.0)
    rp = os.path.join(out_dir, "mix_raw.wav")
    A.write_wav(rp, raw)
    out = cw
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", rp, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11,alimiter=limit=0.94", "-ar", "44100", out], check=True)
    rep = report(out, nar, bed, plan["duration"])
    rep["cache_hit"] = False
    rep["layers"] = dict(narration=bool(np.abs(nar).max() > 0), ambience_scenes=[(s["loc"], s["time"]) for s in plan.get("scenes", [])], music_moods=[m[2] for m in plan["mood_track"]], foley_events=len(foley_events(plan, perf_events)))
    json.dump(rep, open(cj, "w"), indent=1, default=list)
    return out, rep


def report(path, nar, bed, duration):
    y = A._read_wav(path)
    speech = _speech_envelope(nar) > 0.35
    s = min(len(speech), len(nar), len(bed))
    rn = float(np.sqrt((nar[:s][speech[:s]] ** 2).mean() + 1e-12))
    rb = float(np.sqrt((bed[:s][speech[:s]] ** 2).mean() + 1e-12))
    blk = int(0.5 * SR)
    lev = [float(np.sqrt((y[i:i + blk] ** 2).mean())) for i in range(0, len(y) - blk, blk)]
    return dict(duration=round(len(y) / SR, 3), expected=round(duration, 3), peak=round(float(np.abs(y).max()), 4), clipped_samples=int((np.abs(y) >= 0.999).sum()), speech_to_bed_db=round(20 * math.log10(rn / rb), 2),
                narration_active_pct=round(float(speech.mean()) * 100, 1), silent_half_seconds=int(sum(1 for v in lev if v < 0.002)), rms_db=round(20 * math.log10(float(np.sqrt((y ** 2).mean())) + 1e-9), 2))
