"""SEMANTIC LOCATIONS: what a story may name, which stage family draws it, which times of day it allows, and where the actors stand on it (stage layout in world px, floor y = 1500).
`resolve(name, time)` -> Location (family + a time that is POSSIBLE there: a bank is never open at night, a cafe has no moon).  Unknown names raise `LocationUnsupported` (no silent fallback).
"""
import re
from engine.environments import bedroom_wide as BW, study_room as SR, stages

FLOOR = BW.FLOOR_Y


class LocationUnsupported(Exception):
    pass


def _table(phone=(720.0, 1050.0)):
    return dict(seat_x=300.0, sit=True, phone=phone, visitor_from=1290.0, A_stop=620.0, D_stop=950.0, handover=(780.0, 880.0), lamp=(700.0, 940.0), door=(960.0, 1000.0), table=(560.0, 1060.0), D_sit_x=None)


def _counter():
    return dict(seat_x=None, sit=False, phone=(760.0, 1090.0), visitor_from=-260.0, D_from=1300.0, A_stop=490.0, D_stop=850.0, handover=(680.0, 900.0), lamp=(700.0, 700.0), door=(960.0, 1000.0), counter=(680.0, 1120.0), clerk_x=1010.0)


# name -> (family, allowed times, default time, layout, aliases (lower-case; English + Hindi))
LOCATIONS = {
    "bedroom": ("bedroom_wide", ("night", "day"), "night", dict(seat_x=380.0, sit=True, phone=BW.PHONE_POS, visitor_from=1440.0, A_stop=830.0, D_stop=1070.0, handover=(905.0, 860.0), lamp=(600.0, 1110.0), door=(960.0, 1000.0)),
                ["bedroom", "बेडरूम", "कमरे", "कमरा", "बिस्तर", "सोने", "bed"]),
    "study": ("study", ("night", "day"), "night", _table(SR.PHONE_POS), ["study", "स्टडी", "पढ़ाई", "मेज़", "टेबल", "desk"]),
    "living_room": ("living_room", ("day", "night"), "day", dict(seat_x=None, sit=False, phone=(700.0, 1120.0), visitor_from=1300.0, A_stop=520.0, D_stop=880.0, handover=(700.0, 900.0), lamp=(600.0, 900.0), door=(960.0, 1000.0)),
                    ["living room", "लिविंग", "ड्राइंग", "हॉल", "सोफ़ा", "घर", "home", "house"]),
    "office": ("office", ("day",), "day", _table(), ["office", "ऑफिस", "ऑफ़िस", "दफ़्तर", "कार्यालय", "workplace", "नौकरी"]),
    "classroom": ("classroom", ("day",), "day", _table(), ["classroom", "क्लास", "स्कूल", "कॉलेज", "टीचर", "school", "college"]),
    "cafe": ("cafe", ("day", "night"), "day", dict(_table(), D_sit_x=1130.0, A_stop=760.0, handover=(945.0, 900.0)), ["cafe", "café", "कैफ़े", "कैफे", "चाय", "कॉफ़ी", "कॉफी", "रेस्टोरेंट", "restaurant"]),
    "bank": ("bank_counter", ("day",), "day", _counter(), ["bank", "बैंक", "ब्रांच", "branch", "kyc"]),
    "shop": ("shop", ("day", "night"), "day", _counter(), ["shop", "दुकान", "दुकानदार", "स्टोर", "store", "मार्केट"]),
    "police": ("police", ("day", "night"), "day", _counter(), ["police", "पुलिस", "थाना", "थाने", "साइबर सेल", "cyber cell", "complaint", "शिकायत"]),
    "atm": ("atm", ("night", "day"), "night", dict(seat_x=None, sit=False, phone=(700.0, 1000.0), visitor_from=-260.0, A_stop=360.0, D_stop=110.0, handover=(240.0, 920.0), lamp=(700.0, 500.0), door=(960.0, 1000.0), atm=(560.0, 300.0)),
            ["atm", "एटीएम", "cash machine"]),
    "call_center": ("call_center", ("day", "night"), "day", dict(seat_x=None, sit=False, phone=(700.0, 1100.0), visitor_from=1300.0, A_stop=500.0, D_stop=900.0, handover=(700.0, 900.0), lamp=(600.0, 900.0), door=(960.0, 1000.0)),
                    ["call center", "call centre", "कॉल सेंटर", "कॉल-सेंटर", "callcentre"]),
    "street": ("street", ("day", "dusk", "night"), "dusk", dict(seat_x=None, sit=False, phone=(700.0, 1100.0), visitor_from=-260.0, A_stop=620.0, D_stop=900.0, handover=(760.0, 900.0), lamp=(310.0, 860.0), door=(960.0, 1000.0)),
               ["street", "सड़क", "गली", "बाज़ार", "बाहर", "road", "मोहल्ला"]),
}
TIME_WORDS = {"night": ["रात के", "रात में", "रात को", "night", "आधी रात", "देर रात", "midnight"], "day": ["सुबह", "दोपहर", "morning", "afternoon", "दिन के समय", "दिनदहाड़े", "दिन की रोशनी", "दिन चढ़"], "dusk": ["शाम", "evening", "dusk", "sunset"]}
EXTRA = {}                                                       # per-location render extras (Kathaya library assets: {"backdrop": path, "floor": colour}); empty for the built-in sets
ALL = ["bedroom", "study", "living_room", "office", "classroom", "cafe", "bank", "shop", "police", "atm", "call_center", "street"]


_LOCATIVE = ["में", "पर", "पहुँच", "पहुंच", "के अंदर", "के बाहर", "के सामने"]


def find(text):
    """(location, time) a sentence PLACES the story in, or (None, None). A place word only counts with a locative ('बैंक में', 'एटीएम पर', 'दुकान पहुँचा'), never as a topic ('ये असली बैंक नहीं है'). Longest alias wins."""
    import unicodedata
    t = unicodedata.normalize("NFC", text.lower()).replace("\u093c", "").replace("\u0901", "\u0902")
    t = re.split(r"[:：]", t, 1)[0]                                      # what follows a colon is a quoted message / sign, not the narrator placing the scene
    best, score = None, 0
    for name, (_, _, _, _, aliases) in LOCATIONS.items():
        for a in aliases:
            a = unicodedata.normalize("NFC", a).replace("\u093c", "").replace("\u0901", "\u0902")
            i = t.find(a)
            if i < 0 or len(a) <= score:
                continue
            tail = t[i + len(a): i + len(a) + 14]
            ascii_alias = a.isascii()
            if ascii_alias or any(m in tail for m in _LOCATIVE) or i == 0:
                best, score = name, len(a)
    tm = next((k for k, ws in TIME_WORDS.items() if any(w in t for w in ws)), None)
    return best, tm


def resolve(name, time=None):
    if name not in LOCATIONS:
        raise LocationUnsupported(f"unknown location '{name}' (supported: {ALL})")
    fam, times, default, layout, _ = LOCATIONS[name]
    notes = []
    tm = time or default
    if tm not in times:
        notes.append(f"'{name}' cannot be shown at '{tm}' (allowed: {list(times)}): using '{default}'")
        tm = default
    return dict(name=name, family=fam, time=tm, layout=dict(layout), notes=notes)


def register():
    """make the stage families known to the environment factory (idempotent)"""
    from engine.environments import factory as EF, families
    for fam, gen in stages.FAMILIES.items():
        families.FAMILIES[fam] = gen
        EF.LIGHTS.setdefault(fam, ((0.62, 0.62, 0.60), 0.30, "day", "lit by the day", fam, "story location"))


register()
