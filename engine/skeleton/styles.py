"""ART DIRECTION PRESETS for the topic system. A STYLE is data: which environment (and where its furniture, door, phone, stops and hand-over point are), who is cast, how it is lit, how it is shot,
what the character's psychology looks like (extra acting / replacement faces at beats), and which GP motifs are used. Two topics are 'two different films' when their styles differ - nothing else changes:
the same asset library, the same rig, the same act grammar. `PACK_STYLE` maps each scam domain to a style; the story generator records the choice in story['style'].
"""
from engine.environments import bedroom_wide as BW, study_room as SR

NIGHT_BEDROOM = dict(
    id="night_bedroom", family="bedroom_wide", A_origin=380.0, D_origin=1440.0, A_start="sit", presets=True, arc=None,
    targets=dict(PHONE=list(BW.PHONE_POS), nightstand_phone=list(BW.PHONE_POS), DOOR=[960.0, 1000.0], NIGHTSTAND=[670.0, 1180.0], BED=[200.0, 1230.0], LAMP=[600.0, 1110.0], WINDOW=[865.0, 560.0],
                 A_STOP=[830.0, BW.FLOOR_Y], D_STOP=[1070.0, BW.FLOOR_Y], HANDOVER=[905.0, 860.0], SCREEN=[540.0, 900.0], MONEY=[540.0, 900.0]),
    cast=dict(protagonist=None, other=None), relight=None, camera_bias={}, motif={}, extras={}, time_word=None, lamp_from_start=False,
    psychology="dread: the message frightens (fear / worry faces, cold light)")

DAY_STUDY = dict(
    id="day_study", family="study_room", A_origin=300.0, D_origin=1290.0, A_start="sit", presets=False, arc="ARC_TIGHT",
    targets=dict(PHONE=list(SR.PHONE_POS), nightstand_phone=list(SR.PHONE_POS), DOOR=[960.0, 1000.0], NIGHTSTAND=[720.0, 1060.0], BED=[200.0, 1230.0], LAMP=[700.0, 940.0], WINDOW=[865.0, 560.0],
                 A_STOP=[620.0, BW.FLOOR_Y], D_STOP=[950.0, BW.FLOOR_Y], HANDOVER=[780.0, 880.0], SCREEN=[540.0, 900.0], MONEY=[540.0, 900.0]),
    cast=dict(protagonist=dict(gender="female"), other=dict(relation="father")),
    relight=dict(day=True), camera_bias={"EYES_CHANGE": ("A.head", "medium", "drift"), "REALIZE": ("A.head", "medium", "isolate"), "OTHER_REACTS": ("D.head", "medium", "push"), "CLOSE_UP": ("A.head", "medium", "hold")},
    motif={"rays": "arcs", "worry": "scribble", "ticks": "ticks"}, lamp_from_start=True,
    extras={"READ_MESSAGE": [("A", dict(action="face_atom", dt=0.35, dur=1.0, name="smile"))],                     # greed: she SMILES at the bait ...
            "REALIZE": [("A", dict(action="face_atom", dt=0.3, dur=1.1, name="dread"))],                             # ... and the smile turns to dread
            "BOTH_REALIZE": [("D", dict(action="face_atom", dt=0.3, dur=1.0, name="suspicious"))]},
    psychology="greed / hope first (smile at the prize), then dread; warm daylight, table between the two")

STYLES = {s["id"]: s for s in (NIGHT_BEDROOM, DAY_STUDY)}
PACK_STYLE = {"investment": "night_bedroom", "bank_kyc": "night_bedroom", "parcel": "night_bedroom", "loan_app": "night_bedroom", "lottery": "day_study", "job_offer": "day_study", "upi_refund": "day_study"}
FACE_ATOMS_USED = ("smile", "dread", "suspicious")


def get(name):
    return STYLES.get(name or "night_bedroom", NIGHT_BEDROOM)


def relight(style, lt, act):
    """style-specific lighting for one shot's lighting dict"""
    if not style.get("relight"):
        return lt
    out = dict(lt)
    if style["relight"].get("day"):
        mood = out.get("mood", "dim")
        out.update(moon=0.0, phone=min(out.get("phone", 0.5), 0.5), hall=0.0, sun=0.85, lamp=0.9)
        out["mood"] = {"dim": "warm", "fear": "pressure", "relief": "bright"}.get(mood, mood)
    return out
