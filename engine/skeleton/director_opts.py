"""DIRECTOR OPTIONS: optional overrides a user may set on top of the deterministic plan. Everything defaults to AUTO, and AUTO changes nothing (the plan is byte-identical to the CLI's).

    graph["director"] = dict(pacing="calm|normal|fast|intense", camera="auto|locked|push_in", captions=True|False, audio=dict(music=0..2, sfx=0..2, ambience=0..2))   (multipliers of the Audio Director's default gains)

`apply(plan, opts)` edits the finished plan only (camera MOVES, the caption flag, the audio gains). Shot sizes, targets, cuts and acting are never touched, so every geometry guarantee of the director still holds.
"""
import copy

PACING = ("calm", "normal", "fast", "intense")
CAMERA = ("auto", "locked", "push_in")
MOVES = {"calm": dict(push="drift", pull="hold", truck="drift", reveal="drift", drift="hold"), "normal": {}, "fast": dict(hold="drift", drift="push"), "intense": dict(hold="push", drift="push", isolate="push")}
KNOWN_MOVES = {"push", "pull", "drift", "hold", "track", "truck", "reveal", "rack_focus", "isolate", "dolly_through"}


class OptionsInvalid(ValueError):
    pass


def normalize(opts):
    """validate + drop defaults -> the minimal dict that changes anything ({} = AUTO)"""
    o = dict(opts or {})
    out = {}
    if o.get("pacing") not in (None, "auto", "normal"):
        if o["pacing"] not in PACING:
            raise OptionsInvalid(f"pacing must be one of {PACING}, got {o['pacing']!r}")
        out["pacing"] = o["pacing"]
    if o.get("camera") not in (None, "auto"):
        if o["camera"] not in CAMERA:
            raise OptionsInvalid(f"camera must be one of {CAMERA}, got {o['camera']!r}")
        out["camera"] = o["camera"]
    if o.get("captions") is False:
        out["captions"] = False
    aud = {k: float(v) for k, v in (o.get("audio") or {}).items() if k in ("music", "sfx", "ambience") and v is not None and abs(float(v) - 1.0) > 1e-9}
    for k, v in aud.items():
        if not 0.0 <= v <= 2.0:
            raise OptionsInvalid(f"audio.{k} must be between 0 and 2 (x the default level), got {v}")
    if aud:
        out["audio"] = aud
    return out


def apply(plan, opts, dna_patch=None):
    for cid, patch in (dna_patch or {}).items():
        if cid in plan["characters"]:
            patch_dna(plan, cid, patch)
    opts = normalize(opts)
    if not opts:
        return plan
    from engine.skeleton import audio_director as AUD
    plan["director"] = copy.deepcopy(opts)
    remap = dict(MOVES.get(opts.get("pacing", "normal"), {}))
    cam = opts.get("camera", "auto")
    for sh in plan["shots"]:
        c = sh.get("camera")
        if not c or c.get("move") not in KNOWN_MOVES:
            continue
        mv = c["move"]
        if cam == "locked" and mv not in ("rack_focus",):
            mv = "hold"
        elif cam == "push_in" and mv in ("hold", "drift", "isolate", "pull"):
            mv = "push"
        elif mv in remap:
            mv = remap[mv]
        if mv != c["move"]:
            sh["camera"] = dict(c, move=mv)
    if opts.get("captions") is False:
        plan["captions"] = False
    if opts.get("audio"):
        plan["audio_cfg"] = {**{k: round(AUD.GAIN[k] * m, 4) for k, m in opts["audio"].items()}, **plan.get("audio_cfg", {})}
    return plan


def patch_dna(plan, cid, patch):
    """patch a character's DNA fields (skin, wardrobe, ...) in a plan; the result must still satisfy the DNA schema"""
    from engine.skeleton import dna2
    dna = plan["characters"][cid]["dna"]
    for k, v in patch.items():
        dna[k] = {**dna[k], **v} if isinstance(dna.get(k), dict) and isinstance(v, dict) else v
    bad = dna2.validate(dna)
    if bad:
        raise ValueError(f"invalid DNA: {bad}")
    return plan
