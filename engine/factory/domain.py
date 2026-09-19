"""Domain packs: everything domain-specific (vocabulary, psychology registry, visual grammars, location/prop availability)
lives in domains/<id>/domain.json, so the engine stays domain-agnostic. Add history/science/... by adding a pack."""
import json
import os

from engine.shorts.raster import ROOT

DOMAINS = os.path.join(ROOT, "domains")


class Domain:
    def __init__(self, dom_id):
        self.id = dom_id
        self.dir = os.path.join(DOMAINS, dom_id)
        self.d = json.load(open(os.path.join(self.dir, "domain.json")))

    def __getitem__(self, k):
        return self.d[k]

    def get(self, k, default=None):
        return self.d.get(k, default)

    # ---- locations
    def location_set(self, name):
        n = (name or "").lower()
        for kind, e in self.d["environments"].items():
            if kind == n or n in [a.lower() for a in e["aliases"]] or any(a.lower() in n for a in e["aliases"]):
                return kind, e["set"], e["time"]
        return None, None, None

    def env_kinds(self):
        return list(self.d["environments"])

    # ---- props
    def prop_status(self, name):
        n = (name or "").lower().replace(" ", "_")
        for k, v in self.d["props"].items():
            if k == n or k in n or n in k:
                return k, v
        return None, "unknown"

    # ---- psychology
    def psych(self, key):
        return self.d["psychology"].get(key)

    def grammar(self, mech):
        p = self.psych(mech)
        return self.d["visual_grammars"].get(p["grammar"]) if p else None

    def outfit(self, key):
        return self.d["outfits"].get(key, self.d["outfits"]["sweater_speckled"])

    def detect_topics(self, text):
        t = text.lower()
        return {k: sum(t.count(w.lower()) for w in ws) for k, ws in self.d["topic_keywords"].items()}


def load(dom_id="money_psychology"):
    return Domain(dom_id)


_NUKTA = "\u093c"


def nn(s):
    """Nukta/whitespace-insensitive form for Hindi cue matching (फ़ == फ)."""
    import unicodedata
    return unicodedata.normalize("NFC", s).replace(_NUKTA, "").replace("\u00a0", " ").lower()


def has_cue(text, cues):
    t = nn(text)
    return any(nn(c) in t for c in cues)


def cue_hits(text, cue_map):
    t = nn(text)
    return [k for k, cs in cue_map.items() if any(nn(c) in t for c in cs)]
