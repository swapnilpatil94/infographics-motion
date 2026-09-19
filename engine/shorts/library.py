"""The capability library: everything the renderer can actually depict, as data.

This is the single source of truth for (a) the planner's prompts + JSON-schema enums and
(b) the validator. An LLM can only ever select from these lists; anything else is repaired
or rejected before it reaches the compiler. Extending the system = adding art + one entry here.
"""
from engine.shorts import sets

BODIES = {
    "device": "holding a smartphone (scrolling, reading a message, a notification)",
    "coffee": "holding a mug (morning, break, relaxed, chatting)",
    "explaining": "hand gesturing while talking (explaining, telling, reasoning)",
    "laptop": "typing on a laptop (work, study, emails, deadlines)",
    "paper": "holding a phone-sized card/paper (bill, document, reading something)",
    "pointing": "raised index finger (an idea, a warning, 'listen', a realisation)",
    "crossed": "arms crossed (resistance, defensiveness, skepticism, stubbornness)",
    "shrug": "open-palm shrug (whatever, unsure, helpless, 'who knows')",
    "gaming": "holding a game controller (games, distraction, wasting time)",
    "neutral": "arms down, idle (listening, waiting, neutral)",
    "hoodie": "casual hoodie, arms down (relaxed, casual, at home)",
    "hug": "arms wrapped around himself in a speckled sweater - SAME sweater as 'device' (cold, lonely, anxious, lying awake, waiting)",
}
FACES = {
    "calm": "peaceful, relaxed", "smile": "gentle smile", "happy": "big happy smile", "tired": "exhausted, sleepy, drained",
    "blank": "numb, spaced out, staring", "serious": "stern, focused, grave", "concerned": "worried, thinking hard",
    "uneasy": "anxious, afraid something is wrong", "shock": "wide-eyed sudden shock", "fear": "scared, alarmed",
    "awe": "amazed, impressed", "angry": "furious", "suspicious": "doubtful, side-eye", "contempt": "disdain, smug disapproval",
    "driven": "determined, motivated", "explaining": "talking, animated, mid-sentence", "solemn": "sombre, sad, reflective",
    "cheeky": "playful, mischievous",
}
LOOKS = ["ahead", "phone", "down", "window", "ceiling"]
SIZES = {"wide": "whole room, character small (establish place, isolation)", "medium": "chest-up (default storytelling)",
         "close": "face fills frame (emotion)", "ecu": "extreme close-up on the eyes (peak shock/realisation only)"}
MOVES = {"push": "slow push-in (rising tension)", "pull": "slow pull-back (release, reflection)", "hold": "almost still",
         "drift": "gentle sideways drift"}
ACTS = ["none", "startle", "lean", "tremble"]      # role recipes (interruption/attention/curiosity/unease/realization) add richer acting
CARD_STYLES = {"stat": "one big number/short phrase (big) + label (small)", "title": "one big statement or question (big)",
               "versus": "two things compared (left, right) + optional small line", "list": "title + up to 3 short items"}
ICONS = ["clock", "phone", "coin", "moon", "heart", "warning", "bulb", "calendar", "chart_down", "chart_up", "hourglass",
         "question", "eye", "lock"]
TONES = ["alert", "calm", "gold", "info"]
CAST = {"young_man": "rahul", "young_woman": "priya", "older_man": "uncle"}
ROLES = ["hook", "setup", "escalation", "turn", "payoff", "takeaway", "interruption", "attention", "curiosity", "unease", "realization"]
SET_IDS = list(sets.SETS)


def catalog_text():
    lines = ["SETS (locations):"]
    for k, v in sets.catalog().items():
        lines.append(f"- {k} [{v['time']}]: {v['desc']} Good for: {v['good_for']}.")
    lines.append("BODIES (character pose/prop): " + "; ".join(f"{k} = {v}" for k, v in BODIES.items()))
    lines.append("FACES (emotion): " + "; ".join(f"{k} = {v}" for k, v in FACES.items()))
    lines.append("SIZES: " + "; ".join(f"{k} = {v}" for k, v in SIZES.items()))
    lines.append("MOVES: " + "; ".join(f"{k} = {v}" for k, v in MOVES.items()))
    lines.append("CARDS (concept cards, for ideas the scenes cannot show): " + "; ".join(f"{k} = {v}" for k, v in CARD_STYLES.items()))
    lines.append("CARD ICONS: " + ", ".join(ICONS) + ". CARD TONES: alert(red) calm(teal) gold info(blue).")
    return "\n".join(lines)
