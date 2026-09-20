"""The DRAMATIC-ACT vocabulary of the skeleton film system.

A story is a sequence of BEATS; every beat carries one ACT (a closed vocabulary). The director compiles each act into a shot (camera, lighting, GP, insert) and semantic actions for the two
characters - nothing here contains raw rotations or frame numbers. The vocabulary is what makes the system topic-general: any domain topic that can be staged as one or two people, a phone/screen,
a room and a door is written as a sequence of these acts (by the LLM writer or by the deterministic fallback in topic_story.py) and the SAME compiler renders it.

`GRAMMAR` states which acts need which earlier acts (a person cannot hand over a phone he has not picked up); `repair()` makes any sequence valid.
"""

ACTS = {
    "ESTABLISH": dict(doc="wide establishing shot: the protagonist alone in the room at night", needs=[], sets=["alone", "seated"], once=True, alt="CLOSE_UP"),
    "PHONE_ALERT": dict(doc="the phone lights up / buzzes on the nightstand", needs=["alone"], sets=["alert"], once=True, alt="EYES_CHANGE"),
    "LOOK_AT_PHONE": dict(doc="the protagonist notices and looks at the phone", needs=["alert"], sets=[], alt="CLOSE_UP"),
    "EYES_CHANGE": dict(doc="close-up: the eyes narrow, something is off", needs=["alert"], sets=[], alt="CLOSE_UP"),
    "REACH_PHONE": dict(doc="the hand reaches for the phone (still sitting)", needs=["alert", "seated"], sets=["reached"], once=True, alt="LOOK_AT_PHONE"),
    "PICK_UP": dict(doc="the hand closes on the phone and lifts it", needs=["reached"], sets=["holding"], once=True, alt="READ_MESSAGE"),
    "READ_MESSAGE": dict(doc="reads the message on the screen", needs=["holding"], sets=[], alt="INSERT_SCREEN"),
    "REALIZE": dict(doc="close-up: it sinks in (realization sequence)", needs=["alone"], sets=[], alt="EYES_CHANGE"),
    "STAND_UP": dict(doc="stands up in fear, phone in hand", needs=["holding", "seated"], sets=["standing"], clears=["seated"], once=True, alt="CLOSE_UP"),
    "WALK_ACROSS": dict(doc="walks across the room, phone in hand", needs=["standing"], sets=[], once=True, alt="CLOSE_UP"),
    "PERSON_ENTERS": dict(doc="a second person walks in through the door (off-screen -> notices him -> eye contact)", needs=["standing"], sets=["other"], once=True, alt="EYE_CONTACT"),
    "EYE_CONTACT": dict(doc="they look at each other and hold it", needs=["other"], sets=[], alt="CLOSE_UP"),
    "OTHER_LOOKS_AT_PHONE": dict(doc="the second person looks at the phone in his hand", needs=["other", "holding"], sets=[], alt="EYE_CONTACT"),
    "HAND_OVER": dict(doc="he hands the phone to the second person", needs=["other", "holding"], sets=["handed"], clears=["holding"], once=True, alt="OTHER_REACTS"),
    "OTHER_REACTS": dict(doc="close-up: the second person reads and reacts with fear", needs=["handed"], sets=[], alt="EYE_CONTACT"),
    "INSERT_SCREEN": dict(doc="full-screen insert of the message (data: sender, time, text)", needs=["alert"], sets=[], alt="CLOSE_UP"),
    "VISUALIZE_FLOW": dict(doc="procedural money / account network visualisation (data: amount, from, to)", needs=["alert"], sets=[], alt="CLOSE_UP"),
    "BOTH_REALIZE": dict(doc="both understand the danger at the same moment", needs=["other"], sets=[], alt="EYES_CHANGE"),
    "CLOSE_UP": dict(doc="final close-up: determination, looks into the camera", needs=["alone"], sets=[]),
    # ---- v4 production vocabulary: location-independent acts used by the story parser (props, places, other people)
    "ARRIVE": dict(doc="the protagonist arrives / is established at the location (standing, walking in)", needs=[], sets=["alone", "standing"], alt="CLOSE_UP"),
    "MEET": dict(doc="another person is already there (clerk, shopkeeper, officer, friend): first two-shot", needs=["alone"], sets=["other"], once=True, alt="EYE_CONTACT"),
    "CONVERSE": dict(doc="the two people talk (speaker gestures, listener nods / reacts)", needs=["other"], sets=[], alt="EYE_CONTACT"),
    "SUSPECT": dict(doc="a flicker of doubt: side glance, hesitation", needs=["alone"], sets=[], alt="CLOSE_UP"),
    "OBSERVE": dict(doc="the protagonist looks around / thinks (neutral beat)", needs=["alone"], sets=[], alt="CLOSE_UP"),
    "SIT_DOWN": dict(doc="sits down (chair / bench / seat of the set)", needs=["alone"], sets=["seated"], alt="CLOSE_UP"),
    "USE_ATM": dict(doc="uses the ATM: card in, keypad, cash", needs=["alone"], sets=["cash"], alt="CLOSE_UP"),
    "COUNT_MONEY": dict(doc="holds / counts money", needs=["alone"], sets=["cash"], alt="CLOSE_UP"),
    "READ_DOCUMENT": dict(doc="reads / signs a document", needs=["alone"], sets=[], alt="CLOSE_UP"),
    "TYPE_LAPTOP": dict(doc="types on a laptop / keyboard at a desk", needs=["alone"], sets=[], alt="CLOSE_UP"),
    "PHONE_CALL": dict(doc="phone call: the phone at the ear, talking / listening", needs=["alone"], sets=[], alt="CLOSE_UP"),
    "GIVE_OBJECT": dict(doc="hands an object (card / money / document / phone) to the other person", needs=["other"], sets=["gave", "handed"], alt="EYE_CONTACT"),
    "RECEIVE_OBJECT": dict(doc="receives an object from the other person", needs=["other"], sets=["handed"], alt="EYE_CONTACT"),
    "TAKE_PHONE": dict(doc="takes the phone (from the pocket while standing / from the table): it is now in the hand", needs=["alert"], sets=["holding"], once=True, alt="LOOK_AT_PHONE"),
    "RUN_AWAY": dict(doc="runs (panic / rush)", needs=["alone"], sets=[], alt="CLOSE_UP"),
    "CROWD_WATCH": dict(doc="background people react (crowd / bystanders)", needs=["alone"], sets=[], alt="CLOSE_UP"),
    "RESOLVE": dict(doc="they stop and think; warm light returns; wide pull-out", needs=["alone"], sets=[]),
}
VOCAB = list(ACTS)
FIRST, LAST = "ESTABLISH", "RESOLVE"
FIRSTS = ("ESTABLISH", "ARRIVE")

# a beat's role in the story arc (for the writer): what the act SHOULD express
ARC_HINT = {"ESTABLISH": "hook / setup", "PHONE_ALERT": "interruption", "LOOK_AT_PHONE": "attention", "EYES_CHANGE": "unease", "REACH_PHONE": "curiosity", "PICK_UP": "curiosity", "READ_MESSAGE": "the bait",
            "REALIZE": "dread", "STAND_UP": "panic", "WALK_ACROSS": "restlessness", "PERSON_ENTERS": "a witness arrives", "EYE_CONTACT": "tension", "OTHER_LOOKS_AT_PHONE": "suspicion", "HAND_OVER": "trust",
            "OTHER_REACTS": "alarm", "INSERT_SCREEN": "the exact words of the scam", "VISUALIZE_FLOW": "where the money would go", "BOTH_REALIZE": "understanding", "CLOSE_UP": "resolve", "RESOLVE": "takeaway"}


def validate(seq):
    """-> list of problems (empty = valid). seq = list of act names."""
    bad, have, ever, seen = [], set(), set(), []
    if not seq or seq[0] not in FIRSTS:
        bad.append(f"first act must be one of {FIRSTS}")
    if not seq or seq[-1] != LAST:
        bad.append(f"last act must be {LAST}")
    for i, a in enumerate(seq):
        if a not in ACTS:
            bad.append(f"beat {i}: unknown act {a!r}")
            continue
        d = ACTS[a]
        if d.get("once") and a in seen:
            bad.append(f"beat {i}: {a} cannot repeat")
        for n in d["needs"]:
            if n not in have:
                bad.append(f"beat {i}: {a} needs '{n}' first" if n not in ever else f"beat {i}: {a} needs '{n}' but it has ended")
        have |= set(d["sets"])
        ever |= set(d["sets"])
        have -= set(d.get("clears", []))
        seen.append(a)
    return bad


def repair(seq):
    """Make ANY act sequence valid without inventing or dropping beats (a beat keeps its narration slot): unknown acts are dropped, FIRST/LAST are enforced; an act that is not playable is
    replaced - by the act that PROVIDES its missing prerequisite, or, when the prerequisite has ended / the act cannot repeat, by its `alt`. Returns (new_seq, [changes])."""
    provider = {}
    for a, d in ACTS.items():
        for s in d["sets"]:
            provider.setdefault(s, a)
    seq = [a for a in seq if a in ACTS] or [FIRST, LAST]
    changes = []
    if seq[0] not in FIRSTS:
        changes.append(f"prepended {FIRST}")
        seq = [FIRST] + seq
    if seq[-1] != LAST:
        changes.append(f"appended {LAST}")
        seq = seq + [LAST]
    out, have, ever = [], set(), set()
    for i, a in enumerate(seq):
        for _ in range(10):
            d = ACTS[a]
            why = None
            if d.get("once") and a in out:
                why = ("once", d.get("alt", "CLOSE_UP"))
            else:
                for n in d["needs"]:
                    if n not in have:
                        why = (f"needs '{n}'", provider[n] if n not in ever else d.get("alt", "CLOSE_UP"))
                        break
            if why is None:
                break
            changes.append(f"beat {i}: {a} -> {why[1]} ({why[0]})")
            a = why[1]
        out.append(a)
        have |= set(ACTS[a]["sets"])
        ever |= set(ACTS[a]["sets"])
        have -= set(ACTS[a].get("clears", []))
    return out, changes
