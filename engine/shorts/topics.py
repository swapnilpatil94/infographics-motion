"""Topic capability registry.

Answers, for any requested topic: how much of it can this engine actually depict?
  A  FULLY SUPPORTED          scenes + poses + sets already in the library
  B  PROCEDURAL GRAPHICS      carried by concept cards / procedural graphics (numbers, comparisons, flows)
  C  REQUIRES SPECIALIST ASSETS  named assets are missing -> emitted as structured asset requirements
  D  CURRENTLY UNSUPPORTED    needs visuals we cannot produce honestly (real footage, live action...)
The planner never invents a missing asset: it records it as a requirement and stays inside the library.
A topic PACK is a named group of assets. Adding one = art + entries below (see docs/ADDING_TOPIC_PACKS.md).
"""
import re

# nouns the current library can draw (poses, props, sets, icons). Matching is by substring, lower-case.
HAVE = {
    "prop": ["phone", "smartphone", "mobile", "laptop", "mug", "coffee", "cup", "paper", "controller", "game", "clock", "calendar",
             "coin", "money icon", "chart", "graph", "bulb", "lamp", "lock", "hourglass", "eye", "warning", "heart", "plant",
             "notification", "message", "pillow", "blanket", "curtain", "window", "nightstand", "desk", "corkboard", "note"],
    "environment": ["bedroom", "bed", "night room", "office", "desk", "workplace", "street", "city", "rooftop", "parapet", "dusk"],
    "character": ["young man", "young woman", "older man", "man", "woman", "boy", "girl", "person"],
    "effect": ["glow", "light rays", "notification", "buzz", "impact", "dust", "rack focus", "parallax"],
}
PACKS = {
    "everyday": dict(status="A", have=["bedroom", "office", "street", "phone", "laptop", "mug", "clock", "calendar"], missing=[]),
    "psychology": dict(status="B", have=["faces x19", "poses x11", "icons: eye, heart, lock, hourglass, bulb, question"],
                       missing=["brain diagram", "neuron/cell art", "crowd / social group", "thought-bubble system"]),
    "money": dict(status="B", have=["coin icon", "chart up/down", "paper/bill pose", "office set"],
                  missing=["cash notes", "ATM", "bank counter", "debit/credit card", "UPI QR", "shop counter", "money-flow diagram"]),
    "tech": dict(status="B", have=["phone (hand + nightstand)", "laptop pose", "notification FX"],
                 missing=["server/racks", "network graph", "code screen", "social-media UI", "data-flow diagram"]),
    "business": dict(status="C", have=["office set", "laptop pose", "charts"],
                     missing=["boardroom", "factory", "product shots", "customers/crowd", "org chart"]),
    "history": dict(status="C", have=[], missing=["period environments", "period clothing", "maps", "documents", "architecture"]),
    "mythology": dict(status="C", have=[], missing=["deity/persona pack", "temples", "weapons/props", "period architecture", "symbolic FX"]),
    "science": dict(status="C", have=["icons only"], missing=["laboratory set", "molecule/cell art", "planets", "instrument props", "diagram engine"]),
}
PACK_NAMES = list(PACKS)


# things the ENGINE (camera / editing / acting system) does rather than assets
ENGINE_TERMS = ["zoom", "fade", "expression", "face", "moonlight", "light", "ceiling", "shadow", "close-up", "camera", "cut", "glow", "shake"]


def _supported(kind, name):
    n = name.lower()
    return any(term in n for term in ENGINE_TERMS) or any(term in n for terms in HAVE.values() for term in terms)


def assess(pack, fit, needs, renderable=True, ignore=()):
    """-> dict(class, pack, asset_requirements). Deterministic given the LLM's structured `needs`."""
    reqs, seen = [], set()
    for nd in needs or []:
        name, kind = str(nd.get("name", "")).strip(), str(nd.get("type", "prop")).strip()
        if not name or name.lower() in seen or name.lower() in {i.lower() for i in ignore} or _supported(kind, name):
            continue
        seen.add(name.lower())
        reqs.append(dict(asset_required=True, type=kind, name=name, reason=str(nd.get("reason", ""))[:160],
                         priority=nd.get("priority", "medium") if nd.get("priority") in ("high", "medium", "low") else "medium",
                         pack=pack))
    if not renderable:
        cls = "D"
    elif reqs and any(r["priority"] == "high" for r in reqs):
        cls = "C"
    elif fit == "scene" and not reqs:
        cls = "A"
    elif fit == "cards_only" and reqs:
        cls = "C"
    else:
        cls = "B"
    return dict(**{"class": cls}, pack=pack, pack_status=PACKS.get(pack, {}).get("status"), asset_requirements=reqs,
                explanation={"A": "fully supported by scenes/poses/sets",
                             "B": "supported with procedural graphics (cards, charts, ink FX)",
                             "C": "requires specialist assets - see asset_requirements",
                             "D": "currently unsupported"}[cls])
