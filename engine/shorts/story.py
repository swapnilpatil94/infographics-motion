"""Story compiler for the LAYERED performer (rig2): turns a role-tagged plan + real narration timings into
continuous, motivated acting and camera - the reusable 'phone interruption' grammar.

Design rules (why it is built this way):
  * The interruption is shown ON SCREEN and ACTED, not cut to: the nightstand phone lights, buzzes, spills cold
    light; Rahul's EYES react first, the body freezes, the head turns in doubt, the shoulders rise, and the arm
    reaches (hover, hesitation, contact, grasp) and lifts the phone to his chest - one continuous master shot.
  * The camera is motivated by the action: it starts as a two-shot (person + the thing that will interrupt him),
    drifts toward the reaching hand, settles on the chest as the phone arrives, then pushes INTO the phone and
    dissolves into the readable message - no hard insert cut.
  * Close-ups are reserved for reading (medium) and the realisation (ECU); the ending pulls back to the room.
  * Times are ABSOLUTE and independent of word timing except where the story ties to narration (message insert,
    reading, realisation), so re-voicing never breaks the physical action.
"""
import math
from types import SimpleNamespace

import numpy as np

from engine.shorts import ink_fx, performance as P, sets
from engine.shorts.dust import Dust
from engine.shorts.film import Film, FPS, TAIL, _chunk_words, camera_at, fade_at
from engine.shorts.insert import ScreenInsert
from engine.shorts.lighting import Light
from engine.shorts.performance import Channel
from engine.shorts.post import Post
from engine.shorts.rig2 import LayeredRig, REST_A, REST_B
from engine.shorts.scene import Scene

STAND_WORLD = (1065.0, 1135.0)
STAND_CANVAS = (1530.0, 942.0)               # nightstand phone in bust-canvas coordinates
T_EV = 0.75                                  # the light comes on (visual leads the narrator)
INSERT_LEN, DISSOLVE = 1.7, 0.25


def _role(beats, role):
    return next((b for b in beats if b["role"] == role), None)


def compile(plan, voice, log=print):
    film = Film()
    film.plan, film.fps, film.samples = plan, FPS, voice["samples"]
    film.duration = voice["duration"] + TAIL
    film.post = Post()
    film.sfx, film.duck_windows, film.drones, film.shots, film.beats = [], [], [], [], []
    seed = plan.get("seed", 0)
    vb = {b["id"]: b for b in voice["beats"]}
    for beat in plan["beats"]:
        w = vb[beat["id"]]["words"]
        film.beats.append(dict(id=beat["id"], kind="scene", t0=w[0]["start"], t1=w[-1]["end"], words=w, spec=beat,
                               role=beat.get("role"), set="night_bedroom"))
    by = {e["role"]: e for e in film.beats}
    hook, att, cur, une, rea, tak = (by.get(r) for r in ("hook", "attention", "curiosity", "unease", "realization", "takeaway"))

    # ---------------------------------------------------------------- stage
    msg = next((b["scene"].get("phone") for b in plan["beats"] if b.get("scene", {}).get("phone")), {})
    rig = LayeredRig(plan["cast"])
    if msg.get("title"):
        from engine.shorts.phone import PhoneScreen
        rig.ui = PhoneScreen(time_text=msg.get("time", "2:47"), body=msg.get("body", ""), title=msg["title"])
    spec = sets.SETS["night_bedroom"]
    scene = Scene(rig, room=sets.layers_for("night_bedroom"), order=sets.order_for("night_bedroom"), ambient=spec["ambient"],
                  bloom_strength=spec["bloom"], post=film.post)
    ch = SimpleNamespace(stand=Channel(0.0), buzz=Channel(0.0), bright=Channel(0.0), banner=Channel(0.0), pulse=Channel(0.0),
                         amb=Channel(1.0), flash=Channel(0.0))
    base_amb = np.array(spec["ambient"], np.float32)
    for L in spec["lights"](None):                                             # moon / window light follows the room-dim channel
        o = L.intensity
        L.intensity = (lambda t, o=o: (o(t) if callable(o) else o) * ch.amb(t))
        scene.lights.add(L)
    T_grab = T_EV + 3.2
    scene.lights.add(Light("radial", (0.45, 0.80, 1.0), lambda t: 0.95 * ch.stand(t) if t < T_grab + 0.05 else 0.0,
                           reach=(0, 3.4), attach_par=0.95, center=STAND_WORLD, radius=780, power=1.5))
    held = scene.lights.add(Light("radial", (0.50, 0.88, 1.0), lambda t: ch.bright(t) * 1.15 * ch.amb(t) + 0.5 * ch.pulse(t) if t >= T_grab else 0.0,
                                  reach=(0, 2.3), attach_par=1.0, center=(600, 1000), radius=640, power=1.6))
    perf = P.Performance(seed=seed + 5)
    P.init_arms(perf, REST_A, REST_B)
    perf.faces = [(0.0, hook["spec"]["scene"]["face"], 0.0)]
    dust = Dust(seed + 4)

    # ----------------------------------------------------------- the interruption
    t = T_EV
    ch.stand.key(t - 0.001, 0.0)
    ch.stand.key(t + 0.05, 1.0, "out")
    ch.stand.key(T_grab, 1.0, "linear")
    ch.stand.key(T_grab + 0.06, 0.0, "out")
    ch.banner.key(t, 0.0)
    ch.banner.key(t + 0.5, 1.0, "out_back")
    ch.flash.key(t - 0.001, 0.0)                                                # the screen firing: one brief exposure lift
    ch.flash.key(t + 0.04, 1.0, "out")
    ch.flash.key(t + 0.32, 0.0, "smooth")
    for k in range(2):                                                          # phone vibrates on the wood
        for j in range(6):
            ch.buzz.key(t + k * 0.26 + j / FPS, (1 if j % 2 == 0 else -1) * (1 - j / 7.0), "linear")
        ch.buzz.key(t + k * 0.26 + 6 / FPS, 0.0, "linear")
    film.sfx += [(t, "ding", 0.55), (t + 0.02, "buzz", 0.85)]
    for k in range(3):
        film.sfx.append((0.05 + 0.35 * k, "tick", 0.5))                         # the quiet room before the light

    # ---------------------------------------------------- Rahul: eyes -> freeze -> head -> shoulders -> arm
    P.freeze(perf, t + 0.06, 0.55)                                              # startled stillness
    P.emotion(perf, t + 0.18, "blank", 0.28)                                    # eyes go wide-open first
    P.blink_at(perf, t + 0.62)
    P.hesitate(perf, t + 0.55, "stand", 1.35, 1.0)                              # gaze arrives first, head follows in doubt
    P.shrug(perf, t + 0.72, 0.9, 1.1)
    P.emotion(perf, t + 1.5, att["spec"]["scene"].get("face_end") or "concerned", 0.5)
    hover = (1170.0, 1040.0)
    P.arm_to(perf, "B", t + 1.25, t + 1.5, REST_B[0] - 16, REST_B[1] + 12, "smooth")            # anticipation: gather
    P.arm_to(perf, "B", t + 1.5, t + 2.1, *hover, "smooth")                                     # first move
    P.hand_curl(perf, t + 1.4, t + 2.0, 0.0)                                                    # fingers open
    P.arm_to(perf, "B", t + 2.1, t + 2.42, hover[0] + 10, hover[1] - 8, "smooth")               # hover: hesitation
    P.arm_to(perf, "B", t + 2.42, T_grab, STAND_CANVAS[0] - 70.0, STAND_CANVAS[1] + 2.0, "smooth")   # commit and reach
    P.hand_curl(perf, T_grab - 0.2, T_grab + 0.1, 0.85, "out")                                  # grip closes on the phone
    P.hold_phone(perf, T_grab)
    P.phone_rot(perf, T_grab, T_grab + 1.2, -6.0)
    T_A = T_grab + 1.5                                                                          # phone at his chest
    P.arm_to(perf, "B", T_grab + 0.12, T_A, 770.0, 1012.0, "smooth")
    P.look(perf, T_grab + 0.25, "phone", 0.9, 1.0, "smooth")
    P.converge(perf, T_grab + 0.6, T_A + 0.3, 0.9)
    P.lean(perf, T_grab + 0.5, 1.6, 0.8)                                        # posture: he curls in toward the phone
    film.sfx += [(t + 1.3, "whoosh", 0.22), (T_grab + 0.1, "whoosh", 0.25)]
    for c_, v in ((ch.bright, 0.0),):
        pass
    ch.bright.key(T_grab - 0.001, 0.0)
    ch.bright.key(T_grab + 0.12, 1.0, "out")

    # -------------------------------------------------- the message (push into the phone, dissolve to the readable screen)
    T_ins0 = max(T_A + 1.0, cur["t0"] - 0.35)
    T_ins1 = T_ins0 + INSERT_LEN
    film.sfx.append((T_ins0 - 0.1, "whoosh", 0.3))
    # ------------------------------------------------ reading -> unease
    T_read = T_ins1
    for k in range(6):                                                          # eyes scan the lines of text
        perf.channel("gx:read").key(T_read + 0.05 + 0.34 * k, (-0.3 if k % 2 == 0 else 0.32), "out")
    perf.channel("gy:read").key(T_read, 0.35, "smooth")
    P.emotion(perf, T_read, une["spec"]["scene"]["face"], 0.4)
    piv = une["words"][min(len(une["words"]) - 1, max(1, len(une["words"]) // 2))]["start"]
    P.emotion(perf, piv, une["spec"]["scene"].get("face_end") or "concerned", 0.45)
    P.tremble(perf, T_read + 0.4, max(1.5, rea["t0"] - T_read), 0.55, 0.9)
    P.glance(perf, piv + 0.2, "away", 0.8, 0.8)
    P.shrug(perf, piv, 0.7, 0.9)
    # ------------------------------------------------ realisation
    rp = rea["words"][min(len(rea["words"]) - 1, max(1, int(len(rea["words"]) * 0.3)))]["start"] - 0.05
    P.emotion(perf, rea["t0"] - 0.1, "uneasy", 0.35)
    P.emotion(perf, rp, "shock", 0.12)
    P.startle(perf, rp, 0.9)
    P.freeze(perf, rp + 0.25, max(0.8, rea["t1"] - rp))
    perf.no_blink.append((rp - 0.3, rea["t1"] + 0.3))
    for k in range(9):                                                          # the hand trembles after the jolt
        P.arm_to(perf, "B", rp + 0.05 + 0.07 * k, rp + 0.12 + 0.07 * k, 770.0 + (7 if k % 2 == 0 else -7), 1012.0 + (5 if k % 2 else -5), "linear")
    ch.pulse.key(rp - 0.001, 0.0)
    ch.pulse.key(rp + 0.05, 1.0, "out")
    ch.pulse.key(rp + 1.4, 0.15, "smooth")
    ch.amb.key(rp - 0.001, 1.0)
    ch.amb.key(rp + 1.2, 0.72, "smooth")                                        # the room drops away around the phone light
    film.sfx += [(rp, "impact", 0.8), (rp + 0.45, "heartbeat", 0.9), (rp + 1.35, "heartbeat", 0.8)]
    # ------------------------------------------------ takeaway
    P.emotion(perf, tak["t0"] - 0.1, "solemn", 0.7)
    P.look(perf, tak["t0"] + 0.2, "ahead", 1.2, 0.6, "smooth")
    P.blink_at(perf, tak["t0"] + 0.9)
    P.auto_blinks(perf, 0.0, film.duration, seed=seed + 1)

    # ---------------------------------------------------------------- shots
    cur_end = cur["t1"] + 0.2
    T_S3 = T_ins1
    T_S4 = rea["t0"] - 0.2
    T_S5 = rea["t1"] + 0.15
    kf = lambda tt, tg, z, off=(0, 0), ap=10, fc=1.6: dict(t=tt, target=tg, zoom=z, offset=off, aperture=ap, focus=fc)
    two = (735.0, 1020.0)
    film.shots = [
        dict(id="S1_master", t0=0.0, t1=T_ins0, beat=hook, insert=False, cam=dict(subject="eyes", shake=0.55, kf=[
            kf(0.0, two, 1.22, ap=7), kf(T_EV + 1.0, (715.0, 1010.0), 1.30, ap=8), kf(T_EV + 2.5, (790.0, 1035.0), 1.42, ap=8),
            kf(T_grab + 0.3, (770.0, 1015.0), 1.45, ap=8), kf(T_A, "chest", 1.72, (10, -150), ap=13),
            kf(T_ins0 - 0.05, "phone", 3.4, (0, 0), ap=16)])),
        dict(id="S2_message", t0=T_ins0, t1=T_ins1, beat=cur, insert=True, cam=dict(subject="phone", shake=0.0, kf=[
            kf(T_ins0, "phone", 3.4, ap=16), kf(T_ins1, "phone", 3.4, ap=16)])),
        dict(id="S3_read", t0=T_S3, t1=T_S4, beat=une, insert=False, cam=dict(subject="eyes", shake=1.1, kf=[
            kf(T_S3, "eyes", 1.9, (0, 175), ap=15), kf(T_S4, "eyes", 2.15, (0, 175), ap=18)])),
        dict(id="S4_realize", t0=T_S4, t1=T_S5, beat=rea, insert=False, cam=dict(subject="eyes", shake=2.6, settle=True, kf=[
            kf(T_S4, "eyes", 3.0, (0, 25), ap=26), kf(T_S5, "eyes", 3.35, (0, 25), ap=28)])),
        dict(id="S5_pullback", t0=T_S5, t1=film.duration, beat=tak, insert=False, cam=dict(subject="eyes", shake=0.35, kf=[
            kf(T_S5, "chest", 1.85, (10, -160), ap=14), kf(film.duration - 0.6, (600.0, 985.0), 1.06, ap=8)])),
    ]
    for s in film.shots:
        s["cam"]["size"] = s["id"]
    film.sfx += [(T_S4 - 0.06, "whoosh", 0.5), (T_S5 - 0.06, "whoosh", 0.4), (T_S3 - 0.05, "whoosh", 0.3)]

    # -------------------------------------------------------------------- fx
    fx = [lambda c, cam, tt, o=STAND_WORLD: ink_fx.light_rays(c, cam, tt, (o[0], o[1] - 30), ch.stand(tt) * 0.9 if tt < T_grab else 0.0, spread=(-175, -5)),
          lambda c, cam, tt, o=STAND_WORLD, te=T_EV: ink_fx.buzz_marks(c, cam, tt, (o[0], o[1] - 50), 1.0 if te <= tt <= te + 0.8 and ch.buzz(tt) != 0 else 0.0),
          lambda c, cam, tt: ink_fx.light_rays(c, cam, tt, rig.anchor("phone"), (ch.bright(tt) * 0.5 if tt >= T_grab else 0.0), n=9, length=(70, 170), spread=(-200, -70)),
          lambda c, cam, tt, tp=rp: ink_fx.impact_ticks(c, cam, tt, rig.anchor("eyes"), max(0.0, 1.0 - (tt - tp) / 0.75) if tp <= tt <= tp + 0.75 else 0.0)]
    film.stage = SimpleNamespace(rig=rig, perf=perf, scene=scene, ch=ch, base_amb=base_amb, held=held, dust=dust, fx=fx, T_grab=T_grab,
                                 ins=None, insert_window=(T_ins0, T_ins1), punch=(rea["spec"]["scene"].get("punch"), rp, rea["t1"] + 0.2))
    film.sfx.append((T_ins0 - 0.02, "whoosh", 0.0))
    film.caption_track = []
    for ent in film.beats:
        chunks = _chunk_words(ent["words"])
        for j, cw in enumerate(chunks):
            c0 = cw[0]["start"] - 0.04
            c1 = chunks[j + 1][0]["start"] - 0.02 if j + 1 < len(chunks) else cw[-1]["end"] + 0.30
            film.caption_track.append((c0, c1, " ".join(x["word"] for x in cw)))
    for e in film.beats:
        e.update(rig=rig, exposure=1.0, stand=True)
    return film


def render_frame(film, shot, t, f, fade):
    """One frame of the layered story: -> float HxWx3 (post-processed, before captions)."""
    st = film.stage
    rig, scene, ch = st.rig, st.scene, st.ch
    rig.update(st.perf, t)
    rig.update_screen(min(1.0, ch.bright(t)), ch.banner(t))
    gp = rig.anchor("phone")
    st.held.p["center"] = gp
    scene.lights.ambient = st.base_amb * ch.amb(t)
    room, vis = scene.room, t < st.T_grab + 0.05
    for n in ("stand_phone", "stand_screen"):
        room[n].visible = vis
        room[n].world_xf = np.array([[1, 0, 3.0 * ch.buzz(t)], [0, 1, 0], [0, 0, 1.0]])
    room["stand_screen"].opacity = float(min(1.0, ch.stand(t))) if vis else 0.0
    room["clouds"].world_xf = np.array([[1, 0, 16.0 * math.sin(0.13 * t + 0.6)], [0, 1, 0], [0, 0, 1.0]])
    scene.camera = camera_at(film, shot, t)
    film.post.exposure = 1.0 + 0.11 * ch.flash(t)
    t0, t1 = st.insert_window
    a = 0.0                                                     # dissolve: scene -> readable message -> scene
    if t0 - DISSOLVE * 0.5 <= t <= t1 + DISSOLVE * 0.5:
        a = min(1.0, (t - (t0 - DISSOLVE * 0.5)) / DISSOLVE, ((t1 + DISSOLVE * 0.5) - t) / DISSOLVE)
    fx = st.fx
    img = scene.render(t, f, fade, insert=None, dust=st.dust, fx=fx)
    if a > 0.001:
        if st.ins is None:
            st.ins = ScreenInsert(rig.ui)
        u = (t - t0) / max(t1 - t0, 1e-6)
        ins = lambda c: st.ins.apply(c, t, u, 1.0, 1.0, 0.0, 0.04)
        img2 = scene.render(t, f, fade, insert=ins, dust=st.dust, fx=())
        img = img * (1 - a) + img2 * a
    return img
