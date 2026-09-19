"""Compiles a validated PLAN (planner output, DSL v3) + real narration timings into a renderable Film.

Nothing here is story-specific. Timing comes from word-level alignment of the actual narration
(voice.py); acting is derived from each beat's declared emotion arc via the reusable action
library (performance.py); cameras come from the shot-size/move vocabulary; every look-and-feel
choice (set, pose, face, card) has already been constrained to the library by the validator.
"""
import math

import numpy as np

from engine.shorts import audio, cards, ink_fx, performance as P, sets
from engine.shorts.cast import CastRig
from engine.shorts.character import PHONE_CENTER, c2w
from engine.shorts.dust import Dust
from engine.shorts.insert import ScreenInsert
from engine.shorts.layers import Camera
from engine.shorts.lighting import Light
from engine.shorts.performance import Channel, ease
from engine.shorts.phone import PhoneScreen
from engine.shorts.post import Post
from engine.shorts.scene import Scene

FPS = 30
TAIL = 1.0
SIZES = {
    "wide": dict(target="room", zoom=1.0, offset=(0, 0), aperture=7),
    "medium": dict(target="chest", zoom=1.75, offset=(10, -150), aperture=14),
    "close": dict(target="head", zoom=2.1, offset=(0, 95), aperture=22),
    "ecu": dict(target="eyes", zoom=3.1, offset=(0, 25), aperture=28),
}
SIZES["detail"] = dict(target="stand", zoom=2.6, offset=(-10, -20), aperture=20)      # insert on the nightstand phone
SIZES["clock"] = dict(target="clock", zoom=3.3, offset=(0, 0), aperture=18)           # insert on the wall clock (2:47)
CLOCK = (420.0, 372.0)
SIZE_ORDER = ["wide", "medium", "close", "ecu"]
STAND = (1065.0, 1135.0)                       # world position of the phone on the nightstand
ROLE_RECIPE = {"interruption": "interruption", "attention": "attention", "curiosity": "curiosity",
               "unease": "unease", "realization": "realization"}
SHAKE = {"interruption": 0.4, "attention": 1.0, "curiosity": 0.7, "unease": 2.0, "realization": 3.0}
MOVES = {"push": (1.0, 1.10, 0), "pull": (1.10, 1.0, 0), "hold": (1.0, 1.03, 0), "drift": (1.0, 1.04, 28)}
LONG_SHOT = 3.6          # a scene shot longer than this is cut into two setups (pattern interrupt)
INSERT_LEN = 1.5


class Film:
    pass


def _room_or_anchor(rig, name):
    if name == "room":
        return (540.0, 960.0)
    if name == "stand":
        return STAND
    if name == "clock":
        return CLOCK
    return rig.anchor(name)


def _tighter(size):
    i = SIZE_ORDER.index(size)
    return SIZE_ORDER[min(i + 1, 3)] if i < 3 else "close"


def _kf_point(rig, tg, off):
    if isinstance(tg, (tuple, list)):
        px, py = tg
    else:
        px, py = _room_or_anchor(rig, tg)
    return px + off[0], py + off[1]


def _camera_kf(film, shot, t):
    """Keyframed camera: cam['kf'] = [dict(t, target=<anchor name | (x, y)>, offset, zoom, aperture, focus)], eased between keys.
    Anchors like 'phone' are LIVE (they follow the hand), so the camera can be motivated by the action."""
    cam, rig = shot["cam"], shot["beat"]["rig"]
    ks = cam["kf"]
    i = max(0, min(len(ks) - 2, next((j for j in range(len(ks) - 1) if t < ks[j + 1]["t"]), len(ks) - 2)))
    a, b = ks[i], ks[i + 1]
    u = ease(b.get("ease", "smooth"), (t - a["t"]) / max(b["t"] - a["t"], 1e-6))
    pa, pb = _kf_point(rig, a["target"], a.get("offset", (0, 0))), _kf_point(rig, b["target"], b.get("offset", (0, 0)))
    x, y = pa[0] + (pb[0] - pa[0]) * u, pa[1] + (pb[1] - pa[1]) * u
    z = a["zoom"] + (b["zoom"] - a["zoom"]) * u
    ap = a.get("aperture", 12) + (b.get("aperture", 12) - a.get("aperture", 12)) * u
    fc = a.get("focus", 1.6) + (b.get("focus", 1.6) - a.get("focus", 1.6)) * u
    amp = cam.get("shake", 0.5) * (1.0 - 0.75 * ease("smooth", (t - shot["t0"]) / max(shot["t1"] - shot["t0"], 1e-6)) if cam.get("settle") else cam.get("shake", 0.5))
    sx = amp * (math.sin(1.9 * t + 0.3) + 0.6 * math.sin(3.7 * t + 1.1))
    sy = amp * (math.sin(1.4 * t + 2.0) + 0.6 * math.sin(4.3 * t + 0.4))
    return Camera(x + sx, y + sy, z, focus=fc, aperture=ap)


def camera_at(film, shot, t):
    if shot["cam"] and "kf" in shot["cam"]:
        return _camera_kf(film, shot, t)
    cam, rig = shot["cam"], shot["beat"]["rig"]
    base = SIZES[cam["size"]]
    z0, z1, drift = MOVES[cam["move"]]
    u = ease("smooth", (t - shot["t0"]) / max(shot["t1"] - shot["t0"], 1e-6))
    px, py = _room_or_anchor(rig, base["target"])
    ox = base["offset"][0] + drift * (2 * u - 1) * (1 if cam.get("dir", 1) > 0 else -1)
    oy = base["offset"][1]
    amp = cam.get("shake", 0.5) * (1.0 - 0.75 * u if cam.get("settle") else 1.0)     # handheld imperfection (settles on holds)
    sx = amp * (math.sin(1.9 * t + 0.3) + 0.6 * math.sin(3.7 * t + 1.1))
    sy = amp * (math.sin(1.4 * t + 2.0) + 0.6 * math.sin(4.3 * t + 0.4))
    f0, f1 = cam.get("rack", (1.6, 1.6))
    focus = f0 + (f1 - f0) * ease("smooth", min(1.0, u * 1.6))                         # rack focus lands early in the shot
    return Camera(px + ox + sx, py + oy + sy, base["zoom"] * (z0 + (z1 - z0) * u), focus=focus, aperture=base["aperture"])


def _chunk_words(words, max_words=4, max_chars=24):
    """Caption phrases from aligned words: break at punctuation, else by size."""
    chunks, cur = [], []
    for w in words:
        cur.append(w)
        text = " ".join(x["word"] for x in cur)
        if w["word"][-1:] in "।?!,;" or len(cur) >= max_words or len(text) >= max_chars:
            chunks.append(cur)
            cur = []
    if cur:
        if chunks and len(cur) == 1 and len(chunks[-1]) < max_words:
            chunks[-1] += cur
        else:
            chunks.append(cur)
    return chunks


def compile_plan(plan, voice, rigs=None, log=print):
    if plan.get("rig") == "layered":
        from engine.shorts import story
        return story.compile(plan, voice, log)
    film = Film()
    film.plan, film.fps = plan, FPS
    film.samples = voice["samples"]
    film.duration = voice["duration"] + TAIL
    film.post = Post()
    film.sfx, film.duck_windows, film.drones, film.shots, film.beats = [], [], [], [], []
    rigs = rigs if rigs is not None else {}
    seed = plan.get("seed", 0)

    vb = {b["id"]: b for b in voice["beats"]}
    beats = plan["beats"]
    starts = [vb[b["id"]]["start"] for b in beats]
    ends = [vb[b["id"]]["end"] for b in beats]
    bounds = [0.0] + [(ends[i] + starts[i + 1]) / 2 for i in range(len(beats) - 1)] + [film.duration]
    phone_taken = False

    for i, beat in enumerate(beats):
        b0, b1 = bounds[i], bounds[i + 1]
        words = vb[beat["id"]]["words"]
        ent = dict(id=beat["id"], kind=beat["kind"], t0=b0, t1=b1, words=words, spec=beat, role=beat.get("role"))
        film.beats.append(ent)
        if beat["kind"] == "card":
            ent["card"] = beat["card"]
            film.shots.append(dict(id=f"{beat['id']}", t0=b0, t1=b1, beat=ent, cam=None, insert=False))
            film.sfx.append((b0 - 0.05, "whoosh", 0.7))
            continue
        sc = beat["scene"]
        recipe = ROLE_RECIPE.get(beat.get("role"))
        cid = plan["cast"]
        rig = rigs.get(cid) or rigs.setdefault(cid, CastRig(cid))
        faces = [sc["face"]] + ([sc["face_end"]] if sc.get("face_end") else []) + (["blank"] if recipe == "interruption" else [])
        rig.use(sc["body"], faces)
        spec = sets.SETS[sc["set"]]
        scene = Scene(rig, room=sets.layers_for(sc["set"]), order=sets.order_for(sc["set"]), ambient=spec["ambient"],
                      bloom_strength=spec["bloom"], post=film.post)
        for L in spec["lights"](None):
            scene.lights.add(L)
        ent.update(rig=rig, scene=scene, set=sc["set"], exposure=1.0 if spec["time"] != "day" else 0.92, recipe=recipe)
        ent["dust"] = Dust(seed + 4 + i) if spec["time"] == "night" else None
        night = spec["time"] in ("night", "dusk")

        # ------------------------------------------- practical light: phone on the nightstand
        stand = sc["set"] == "night_bedroom"
        ent["stand"] = stand
        ent["stand_visible"] = stand and not phone_taken and sc["body"] != "device"
        if sc["body"] == "device" and stand:
            phone_taken = True
        ent["ch_stand"], ent["ch_buzz"] = Channel(0.0), Channel(0.0)
        if stand:
            scene.lights.add(Light("radial", (0.45, 0.80, 1.0), lambda t, e=ent: 0.95 * e["ch_stand"](t) if e["stand_visible"] else 0.0,
                                   reach=(0, 3.4), attach_par=0.95, center=STAND, radius=760, power=1.5))
        ent["fx"] = []

        # ---------------------------------------------------------- acting
        perf = P.Performance(seed=seed + 31 * (i + 1))
        perf.faces = [(0.0, sc["face"], 0.0)]
        ent["perf"] = perf
        piv_i = min(max(int(sc.get("pivot_word", len(words) // 2)), 0), len(words) - 1)
        t_pivot = words[piv_i]["start"] - 0.05
        act = sc.get("act")
        look = sc.get("look", "ahead")
        if sc.get("face_end") and sc["face_end"] != sc["face"]:
            P.emotion(perf, t_pivot, sc["face_end"], 0.07)

        t_ev = max(t_pivot, b0 + 0.6)
        if recipe == "interruption":
            t_ev = b0 + 0.5            # the light arrives in the silence BEFORE the narrator names it
        if recipe == "interruption" and stand:
            # NORMAL -> INTERRUPTION: the light comes on the nightstand first; only then does he react
            ch, bz = ent["ch_stand"], ent["ch_buzz"]
            ch.key(t_ev - 0.001, 0.0)
            ch.key(t_ev + 0.06, 1.0, "out")
            ch.key(t_ev + 2.6, 0.55, "smooth")
            for k in range(2):
                for j in range(6):
                    bz.key(t_ev + k * 0.26 + j / FPS, (1 if j % 2 == 0 else -1) * (1 - j / 7.0), "linear")
                bz.key(t_ev + k * 0.26 + 6 / FPS, 0.0, "linear")
            film.sfx += [(t_ev, "ding", 0.55), (t_ev + 0.02, "buzz", 0.8)]
            P.emotion(perf, t_ev + 0.24, "blank", 0.07)                    # eyes react first...
            P.freeze(perf, t_ev + 0.20, 0.42)                              # ...micro-freeze...
            P.blink_at(perf, t_ev + 0.50)
            P.hesitate(perf, t_ev + 0.72, "stand", 1.2, 1.0)               # ...then the head turns, in doubt
            ent["fx"] += [lambda c, cam, t, e=ent, o=STAND: ink_fx.light_rays(c, cam, t, (o[0], o[1] - 30), e["ch_stand"](t) * 0.9, spread=(-175, -5)),
                          lambda c, cam, t, e=ent, o=STAND, te=t_ev: ink_fx.buzz_marks(c, cam, t, (o[0], o[1] - 50), e["ch_buzz"](t) and 1.0 * (te <= t <= te + 0.75))]
        elif look != "ahead":
            P.look(perf, b0 + 0.12, look, 0.6, 0.9, "smooth")
        if recipe == "attention":
            P.freeze(perf, b0 + 0.05, 0.3)
            P.hesitate(perf, b0 + 0.35, "stand" if stand and not sc["body"] == "device" else "phone", 1.3, 1.0)
        if recipe == "curiosity":
            P.lean(perf, b0 + 0.25, 1.4, 0.9)
            P.look(perf, b0 + 0.15, "phone", 0.7, 1.0, "smooth")
            bd = perf.channel("bdy:reach")                                  # the grab: a quick dip forward, then settle
            bd.key(b0 - 0.001, 0.0)
            bd.key(b0 + 0.10, 9.0, "out")
            bd.key(b0 + 0.55, 0.0, "smooth")
            film.sfx.append((b0 + 0.02, "whoosh", 0.35))
        if recipe == "unease":
            P.tremble(perf, b0 + 0.2, max(1.0, b1 - b0), 0.7, 0.9)
            P.glance(perf, t_pivot, "away", 0.9, 0.8)
        if recipe == "realization" or act == "startle" or sc.get("face_end") in ("shock", "fear", "awe"):
            P.startle(perf, t_pivot, 0.9 if recipe == "realization" else 1.1)
            film.sfx.append((t_pivot, "impact", 0.8))
            if recipe == "realization":
                P.freeze(perf, t_pivot + 0.25, max(0.6, b1 - t_pivot - 0.8))      # the stillness after the jolt
                film.sfx += [(t_pivot + 0.45, "heartbeat", 0.9), (t_pivot + 1.35, "heartbeat", 0.8)]
                ent["fx"].append(lambda c, cam, t, r=rig, tp=t_pivot: ink_fx.impact_ticks(
                    c, cam, t, r.anchor("eyes"), max(0.0, 1.0 - (t - tp) / 0.75) if tp <= t <= tp + 0.75 else 0.0))
        if act == "lean" and recipe != "curiosity":
            P.lean(perf, t_pivot, 1.0, 1.0)
        if act == "tremble" and recipe != "unease":
            P.tremble(perf, t_pivot, max(1.0, b1 - t_pivot), 0.7, 0.8)
        if sc.get("face") in ("shock", "fear") or sc.get("face_end") in ("shock", "fear"):
            perf.no_blink.append((t_pivot - 0.3, b1))
        P.auto_blinks(perf, b0, b1, seed=seed + i + 1)
        if sc.get("punch"):
            ent["punch"] = (str(sc["punch"])[:14], t_pivot, b1)

        # ------------------------------------------------ phone in hand / message
        ent["phone"] = None
        if sc["body"] == "device":
            cfg = sc.get("phone") or {}
            ph = PhoneScreen(time_text=cfg.get("time") or ("2:47" if spec["time"] == "night" else "11:20" if spec["time"] == "day" else "6:15"),
                             body=cfg.get("body", ""), title=cfg.get("title", ""))
            ent["phone"] = ph
            bright, banner, pulse = Channel(0.55 if night else 0.18), Channel(0.0), Channel(0.0)
            ent.update(ch_bright=bright, ch_banner=banner, ch_pulse=pulse)
            scene.extra.append(("@char", ph))
            scene.lights.add(Light("radial", (0.50, 0.88, 1.0),
                                   lambda t, e=ent: (e["ch_bright"](t) * 1.15 + 0.4 * e["ch_pulse"](t)) * (1.0 if night else 0.35),
                                   reach=(0, 2.3), attach_par=1.0, center=c2w(PHONE_CENTER), radius=600, power=1.7))
            ent["fx"].append(lambda c, cam, t, e=ent: ink_fx.light_rays(c, cam, t, c2w(PHONE_CENTER), e["ch_bright"](t) * (0.5 if night else 0.0),
                                                                        n=9, length=(70, 170), spread=(-200, -70)))
            if cfg.get("title"):
                t_n = t_pivot if recipe != "curiosity" else b0 + 0.12      # curiosity: the message arrives as he looks
                bright.key(t_n - 0.001, bright(t_n) if bright.keys else 0.55)
                bright.key(t_n + 0.10, 1.0, "out")
                banner.key(t_n + 0.10, 0.0)
                banner.key(t_n + 0.55, 1.0, "out_back")
                film.sfx += [(t_n, "ding", 0.8), (t_n + 0.02, "buzz", 0.8)]
                ent["notify_t"] = t_n
            if sc.get("face_end") in ("shock", "fear") or recipe == "realization":
                pulse.key(t_pivot - 0.001, 0.0)
                pulse.key(t_pivot + 0.05, 1.0, "out")
                pulse.key(t_pivot + 1.4, 0.15, "smooth")
        scene.emissive_gain = {"sky": 1.0, "clouds": 0.9, "phone_screen": 1.5, "stand_screen": 1.6}

        # ------------------------------------------------------------ coverage
        shake = SHAKE.get(recipe, 0.5)
        base = dict(size=sc.get("size", "medium"), move=sc.get("move", "push"), dir=1 if i % 2 == 0 else -1, shake=shake,
                    settle=recipe == "realization")
        segs = []                                    # (t0, t1, cam dict)
        if recipe == "interruption" and stand and b1 - t_ev > 1.9:
            segs = [(b0, t_ev + 0.04, dict(base, size="wide", move="hold", shake=0.3)),
                    (t_ev + 0.04, t_ev + 1.0, dict(base, size="detail", move="push", rack=(1.6, 1.95), shake=1.2)),
                    (t_ev + 1.0, b1, dict(base, size="medium", move="push", rack=(1.95, 1.6)))]
        elif recipe is None and beat.get("role") == "hook" and stand and b1 - b0 > 2.0 and plan.get("brief"):
            # the first second asks a question with a prop (the time) before we meet the face
            segs = [(b0, b0 + 1.3, dict(base, size="clock", move="push", rack=(3.1, 3.1), shake=0.4)),
                    (b0 + 1.3, b1, dict(base, move="push", dir=-base["dir"]))]
        else:
            cuts = [b0, b1]
            if b1 - b0 > LONG_SHOT and len(words) >= 4:
                cuts = [b0, words[len(words) // 2]["start"] - 0.05, b1]
            cur = base["size"]
            for k in range(len(cuts) - 1):
                segs.append((cuts[k], cuts[k + 1], dict(base, size=cur, move="push" if k else base["move"], dir=-base["dir"] if k else base["dir"])))
                cur = _tighter(cur) if cur != "ecu" else "close"
        for k, (a, b, c) in enumerate(segs):
            film.shots.append(dict(id=f"{beat['id']}{'abc'[k]}", t0=a, t1=b, beat=ent, cam=c, insert=False))
            if k == 0:
                film.sfx.append((a - 0.05, "whoosh", 0.7))
        insert_at, ins_len = None, INSERT_LEN
        if ent.get("notify_t") is not None:
            insert_at = ent["notify_t"] + 0.55
            ins_len = min(INSERT_LEN, b1 - insert_at - 0.5)          # the message must be readable: never dropped, only shortened
            if ins_len < 0.9:
                insert_at = None
        if insert_at is not None:
            for s in list(film.shots):
                if s["beat"] is ent and s["t0"] <= insert_at < s["t1"]:
                    film.shots.remove(s)
                    parts = [(s["t0"], insert_at, False), (insert_at, insert_at + ins_len, True), (insert_at + ins_len, s["t1"], False)]
                    for n, (a, b, ins) in enumerate(parts):
                        if b - a > 0.25:
                            film.shots.append(dict(id=f"{s['id']}{'pqr'[n]}", t0=a, t1=b, beat=ent, cam=s["cam"], insert=ins))
                    break
    film.shots.sort(key=lambda s: s["t0"])
    film.shots[-1]["t1"] = film.duration
    _vary_sizes(film)
    for e in film.beats:
        if e.get("role") == "hook" and e.get("stand"):
            film.sfx += [(e["t0"] + 0.30, "tick", 0.7), (e["t0"] + 1.05, "tick", 0.7)]    # the clock, heard before it is understood

    # -------------------------------------------------------------- captions
    film.caption_track = []
    for ent in film.beats:
        chunks = _chunk_words(ent["words"])
        for j, ch in enumerate(chunks):
            t0 = ch[0]["start"] - 0.04
            t1 = chunks[j + 1][0]["start"] - 0.02 if j + 1 < len(chunks) else ch[-1]["end"] + 0.30
            film.caption_track.append((t0, t1, " ".join(w["word"] for w in ch)))
    return film


ALTS = {"wide": ["medium"], "medium": ["close", "wide"], "close": ["medium", "ecu"], "ecu": ["close", "medium"]}


def _vary_sizes(film):
    """A cut must change something: two consecutive character shots with the same framing are a jump cut.
    Re-frame the later shot (never inserts, never a realization opener) to the nearest different size."""
    for _ in range(3):                 # re-check: fixing one cut can create another
        _vary_pass(film)


def _vary_pass(film):
    prev = None
    for s in film.shots:
        c = s["cam"]
        if s["insert"] or c is None or c["size"] in ("detail", "clock"):
            prev = None if c is None else prev
            continue
        if prev is not None and c is not prev and c["size"] == prev["size"]:
            keep_first = s["beat"].get("role") == "realization" and s["beat"]["t0"] == s["t0"]
            target = prev if keep_first else c
            other = c if keep_first else prev
            for alt in ALTS[target["size"]]:
                if alt != other["size"]:
                    target["size"] = alt
                    break
        prev = c


def shot_at(film, t):
    for s in film.shots:
        if s["t0"] <= t < s["t1"]:
            return s
    return film.shots[-1]


def fade_at(film, t):
    fin = min(1.0, t / 0.25)
    fout = min(1.0, max(0.0, (film.duration - t) / 0.55))
    return ease("smooth", fin) * ease("smooth", fout)


def caption_at(film, t):
    for t0, t1, text in film.caption_track:
        if t0 <= t <= t1:
            return text, max(0.0, min(1.0, (t - t0) / 0.08, (t1 - t) / 0.08))
    return None, 0.0
