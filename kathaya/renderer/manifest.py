"""CAPABILITY MANIFEST: what the renderer can physically do, GENERATED FROM THE RENDERER'S OWN REGISTRIES (acts, camera sizes and moves, effects, props, lighting, archetypes) - nothing is listed that the code cannot execute.
The creative director receives this manifest; the compiler and the validator enforce it. A requirement outside it is a structured capability error, never a silent substitution."""
import hashlib
import os

from engine.shorts.layers import H, W
from engine.skeleton import acts as AC, director_opts as DO, lab_dna as LD, lighting_presets as LP, parts_art2 as PA2, props4, scene_director as SD, short
from engine.environments import locations as LOC
from kathaya import schemas

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SUBJECTS = {"stage": "environment", "A.full": "protagonist_full", "A.head": "protagonist_head", "A.phone": "protagonist_phone", "A.reach": "protagonist_reach", "P.head": "partner_head", "A+P": "two_shot", "A+atm": "protagonist_at_atm"}
ENGINE_TARGET = {v: k for k, v in SUBJECTS.items()}
MOVE_DOC = {"hold": "locked-off, imperceptible drift (static)", "push": "slow push-in (zoom in ~13% over the shot)", "pull": "slow pull-out (zoom out ~13%)", "drift": "slow lateral drift with a slight push",
            "track": "follows the subject as it moves", "truck": "lateral move through the depth layers (parallax; what a pan looks like in 2.5D)", "reveal": "starts beside the subject behind a foreground layer and slides out to reveal it",
            "rack_focus": "depth of field pulls from the foreground layer to the character", "isolate": "long-lens isolation: flat perspective, shallow depth of field", "dolly_through": "travels in through the depth layers with strong parallax"}
SHOT_DOC = {"reveal": "very wide reveal", "wide": "wide establishing", "wide2": "wide, slightly closer", "full": "full body", "two": "two-shot", "two_reach": "two people + the reach / hand-over area", "medium": "waist-up", "close": "close-up of the face"}
ALIASES = dict(camera_shot={"closeup": "close", "close_up": "close", "establishing": "wide", "wide_establishing": "wide", "medium_shot": "medium", "two_shot": "two", "full_body": "full"},
               camera_movement={"static": "hold", "push_in": "push", "pull_out": "pull", "tracking": "track", "pan": "truck", "slow_push_in": "push", "slow_pull_out": "pull"})
EMOTIONS = sorted(set(SD.MOOD_OF) | set(SD.FACE_ATOM_FOR))


def renderer_version():
    """content hash of the source files that decide what pixels come out (a change here invalidates every cache key that records it)"""
    h = hashlib.sha1(PA2.ART_VERSION.encode())
    for f in ("engine/skeleton/short.py", "engine/skeleton/scene_acts.py", "engine/skeleton/scene_director.py", "engine/skeleton/motion_v2.py", "engine/skeleton/motion_polish.py", "engine/skeleton/props4.py", "engine/skeleton/parts_art2.py",
              "engine/blender/skeleton_scene.py", "engine/environments/stages.py", "engine/environments/families.py"):
        h.update(open(os.path.join(ROOT, f), "rb").read())
    return "kathaya-r" + h.hexdigest()[:10]


def framings():
    """the (subject, shot) pairs the camera director can execute, each with the moves proven for it"""
    out = {}
    for opts in SD.CAMS.values():
        for tg, sz, mv in opts:
            if tg is None:
                continue
            out.setdefault((SUBJECTS[tg], sz), set()).add(mv)
    return [dict(subject=s, shot=z, movements=sorted(m)) for (s, z), m in sorted(out.items())]


def effects():
    seen = {}
    for act, lst in SD.GP.items():
        for (e, an, _s, _d, inten, rel) in lst:
            seen.setdefault(f"{e}@{an}", dict(id=f"{e}@{an}", effect=e, anchor=an, description=rel, default_for=[]))["default_for"].append(act)
    return sorted(seen.values(), key=lambda x: x["id"])


def build():
    global _CACHE
    if _CACHE is None:
        _CACHE = _build()
    return _CACHE


_CACHE = None


def _build():
    acts = [dict(id=k, description=v["doc"], needs=v["needs"], sets=v["sets"], once=bool(v.get("once"))) for k, v in AC.ACTS.items()]
    m = dict(
        schema=f"kathaya.capability_manifest/{schemas.VERSION}", renderer_version=renderer_version(),
        characters=dict(capabilities=acts, emotions=EMOTIONS, archetypes=sorted(LD.ARCHETYPES), max_cast=dict(protagonist=1, partner=1, extra=2),
                        note="capabilities are the renderer's dramatic actions (each compiles to walking, reaching, gaze, expressions, prop handling); `needs`/`sets` are the state the choreography requires (a phone cannot be handed over before it is held)"),
        camera=dict(shots=[dict(id=k, zoom=v, description=SHOT_DOC.get(k, "")) for k, v in sorted(short.SIZES.items(), key=lambda kv: kv[1])], movements=[dict(id=k, description=MOVE_DOC[k]) for k in sorted(DO.KNOWN_MOVES)],
                    subjects=sorted(SUBJECTS.values()), framings=framings(), aliases=ALIASES, unsupported=["tilt", "orbit", "over_shoulder", "extreme_closeup", "handheld_chase"]),
        effects=effects(), props=sorted(k.lower() for k in props4.PROPS), environments=[dict(id=n, times=list(v[1])) for n, v in LOC.LOCATIONS.items()],
        transitions=["cut", "fade", "dip"], lighting=dict(times=["day", "dusk", "night"], moods=sorted(set(LP.DAY_MOOD) | set(LP.NIGHT_MOOD))),
        limits=dict(fps=SD.FPS, formats=dict(short=dict(width=W, height=H)), protagonist_always_on_set=True, first_transition="fade", ambient_gaze=True, sequence=dict(first=list(AC.FIRSTS), last=AC.LAST, once=[k for k, v in AC.ACTS.items() if v.get("once")]),
                    tail_seconds=SD.TAIL, note="long-form uses the same renderer; the 9:16 master is the only native size"))
    m["schema_errors"] = schemas.validate("CapabilityManifest", m)
    return m


def compact(m):
    """the manifest as the creative director reads it (short, no noise)"""
    return dict(actions=[dict(id=a["id"], does=a["description"], needs=a["needs"], sets=a["sets"], once=a["once"]) for a in m["characters"]["capabilities"]], emotions=m["characters"]["emotions"], archetypes=m["characters"]["archetypes"],
                shots=[s["id"] for s in m["camera"]["shots"]], movements={x["id"]: x["description"] for x in m["camera"]["movements"]}, camera_subjects=m["camera"]["subjects"], valid_framings=m["camera"]["framings"],
                effects={e["id"]: e["description"] for e in m["effects"]}, props=m["props"], transitions=m["transitions"], lighting=m["lighting"], limits=m["limits"], unsupported_camera=m["camera"]["unsupported"])
