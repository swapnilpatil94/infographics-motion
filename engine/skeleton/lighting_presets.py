"""LIGHTING PRESETS by time of day: one function turns (time, mood, extras) into the lighting dict a skeleton shot consumes. A day shot has NO moon light, a night shot has NO sun; the window sky of the set
(environments/stages.py) is drawn for the same time, so the two can never contradict each other (QC gate `lighting_matches_environment_time`)."""

DAY_MOOD = {"dim": "warm", "fear": "pressure", "relief": "bright", "isolated": "isolated", "neutral": "neutral", "warm": "warm", "pressure": "pressure", "bright": "bright", "formal": "formal"}
NIGHT_MOOD = {"warm": "dim", "bright": "relief", "neutral": "dim", "formal": "dim", "pressure": "fear", "isolated": "isolated"}


def preset(time, mood="dim", phone=0.0, lamp=0.0, hall=0.0, moon=None):
    if time == "day":
        return dict(time="day", mood=DAY_MOOD.get(mood, "neutral"), moon=0.0, sun=0.6, phone=min(phone, 0.4), lamp=lamp, lamp_const=True, hall=0.0, ambient=(0.46, 0.46, 0.46))
    if time == "dusk":
        return dict(time="dusk", mood={"dim": "warm", "fear": "pressure", "relief": "warm"}.get(mood, "warm"), moon=0.0, sun=0.45, phone=min(phone, 0.6), lamp=lamp, lamp_const=True, hall=0.0, ambient=(0.46, 0.38, 0.36))
    return dict(time="night", mood=NIGHT_MOOD.get(mood, mood), moon=1.0 if moon is None else moon, phone=phone, lamp=lamp, hall=hall, ambient=(0.20, 0.22, 0.34))
