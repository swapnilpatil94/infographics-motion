"""LEGACY (not used by the Kathaya pipeline; kept for the Advanced / Developer tools and the accepted films): STORY SEMANTICS - (script segments + optional story notes) -> a validated STORY GRAPH by keyword rules.
The Kathaya pipeline replaces this with a creative director + a resolved VisualScenePlan (see kathaya/).

(script segments + optional story notes) -> a validated STORY GRAPH the scene director compiles.

    analyze(segments, notes=None)  ->  dict(title, story_id, slug, cast, scenes, beats[{id, text, act, loc, time, emotion, gaze, props, partner, data}], provenance)
    raises StoryNotSupported(reasons) when the request is outside what the factory can stage - it never invents a story.

Everything is CLOSED-VOCABULARY: locations (`environments/locations.py`), acts (`acts.py`), props (props4), roles (ROLES below), emotions (EMOTIONS). Hindi and English cues are matched on a nukta-normalised text.
An optional LLM pass (`llm_refine`) may relabel acts, but only with values from the closed vocabularies, the result is repaired by the act grammar, and the deterministic result is the fallback.
"""
import hashlib
import json
import re
import unicodedata
import urllib.request

from engine.environments import locations as LOC
from engine.skeleton import acts as AC


class StoryNotSupported(Exception):
    pass


def norm(s):
    s = unicodedata.normalize("NFC", s or "").lower().replace("़", "").replace("ँ", "ं")
    s = re.sub(r"[.,!?;:\"'“”‘’()\[\]\-–—…।]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _n(words):
    return [norm(w) for w in words]


PROPS = dict(
    phone=_n(["फोन", "मोबाइल", "मैसेज", "एसएमएस", "sms", "नोटिफिकेशन", "notification", "व्हाट्सएप", "व्हॉट्सऐप", "whatsapp", "स्क्रीन", "कॉल", "phone", "message", "ग्रुप"]),
    card=_n(["कार्ड", "डेबिट", "क्रेडिट", "पिन", "card"]), money=_n(["पैसे", "पैसा", "रुपये", "रुपए", "कैश", "नोट", "नकद", "रकम", "लाख", "हजार", "करोड", "money", "cash", "फीस", "फ़ीस"]),
    document=_n(["कागज", "दस्तावेज", "फॉर्म", "रसीद", "स्लिप", "फाइल", "नोटिस", "चिट्ठी", "आवेदन", "एप्लिकेशन", "document", "form"]),
    laptop=_n(["लैपटॉप", "कंप्यूटर", "वेबसाइट", "पोर्टल", "laptop", "लॉगिन"]), cup=_n(["चाय", "कॉफी", "कप", "गिलास", "coffee", "tea"]), bag=_n(["बैग", "थैला", "bag"]), atm=_n(["एटीएम", "atm"]))

MONEY_STORY = _n(["पैसे", "पैसा", "रुपये", "रुपए", "खाता", "खाते", "बैंक", "ठग", "धोखा", "धोखे", "फ्रॉड", "स्कैम", "ओटीपी", "otp", "लॉटरी", "निवेश", "इनाम", "लोन", "कर्ज", "कार्ड", "कैश", "नकद", "फीस", "फ़ीस",
                  "जाल", "लालच", "ठगी", "यूपीआई", "upi", "रिफंड", "पिन", "बचत", "कमाई", "मुनाफा", "दोगुना", "स्कीम", "scam", "fraud", "money", "bank", "invest", "loan", "cheat"])
UNSUPPORTED_PLACES = _n(["मंदिर", "अस्पताल", "हवाई अड्डा", "एयरपोर्ट", "रेलवे स्टेशन", "स्टेशन", "मॉल", "जंगल", "खेत", "गाँव", "गांव", "समुद्र", "पहाड़", "airport", "hospital", "temple", "mall", "railway"])

# role cues -> (role id, archetype (lab_dna.ARCHETYPES key), gender, note)
ROLES = [
    (_n(["माँ", "मां", "मम्मी", "माता"]), "mother", "parent", "feminine"), (_n(["पापा", "पिताजी", "पिता", "डैड"]), "father", "parent", "masculine"),
    (_n(["दादी", "नानी", "बुजुर्ग महिला"]), "grandmother", "older woman", "feminine"), (_n(["दादा", "नाना", "बुजुर्ग", "अंकल", "रिटायर"]), "grandfather", "older man", "masculine"),
    (_n(["बहन", "दीदी"]), "sister", "young woman", "feminine"), (_n(["भाई", "भैया"]), "brother", "young man", "masculine"), (_n(["दोस्त", "यार", "सहेली"]), "friend", "customer", "either"),
    (_n(["दुकानदार", "दुकान वाले", "दुकान वाला"]), "shopkeeper", "shopkeeper", "masculine"), (_n(["क्लर्क", "कैशियर", "बैंक कर्मचारी", "मैनेजर", "बैंक अधिकारी", "टेलर"]), "bank_employee", "bank employee", "either"),
    (_n(["पुलिस", "इंस्पेक्टर", "सिपाही", "थानेदार", "हवलदार", "साइबर सेल"]), "police_officer", "security guard", "masculine"), (_n(["टीचर", "शिक्षक", "मैडम"]), "teacher", "teacher", "either"),
    (_n(["अजनबी", "आदमी", "शख्स", "ठगों", "फ्रॉडस्टर", "लड़का", "युवक"]), "stranger", "customer", "masculine"), (_n(["औरत", "महिला", "लड़की"]), "stranger_woman", "young woman", "feminine"),
    (_n(["पड़ोसी", "पड़ोस"]), "neighbour", "customer", "either"), (_n(["बॉस", "साहब", "मालिक"]), "boss", "office worker", "masculine"), (_n(["एजेंट", "कॉलर"]), "caller", "customer", "either")]

EMOTIONS = dict(fear=_n(["डर", "घबरा", "काँप", "कांप", "सहम", "दहश", "बेचैन", "पसीना", "साँस थम"]), suspicion=_n(["शक", "संदेह", "अजीब", "झिझक", "सोच में", "हिचक", "सवाल"]),
                hope=_n(["खुश", "मुस्कु", "मुस्कान", "खिल", "उम्मीद", "लालच", "जीत", "बधाई", "चमक", "सपना", "कमाई", "दोगुना"]), relief=_n(["राहत", "बच गए", "बच गया", "बच गई", "सुकून", "शांति", "रुककर सोचा"]),
                anger=_n(["गुस्स", "चिल्ला", "ग़ुस्स", "आग बबूला", "झल्ला"]), sadness=_n(["रो ", "आँसू", "उदास", "टूट", "लुट", "पछता"]), confusion=_n(["उलझ", "समझ नहीं", "हैरान", "चौंक", "क्या हुआ"]),
                realization=_n(["समझ गए", "समझ गया", "समझ गई", "समझ आया", "पता चला", "एहसास", "सच्चाई", "धोखा", "ठगी", "जाल"]))

FEM = _n(["अकेली", "खड़ी", "बैठी", "घबराई", "गई ", "देखी", "रुकी", "उठी", "आई ", "सोचती", "सहमी", "दौड़ी", "पहुँची", "बोली", "काँपी"])
MASC = _n(["अकेला", "खड़ा", "बैठा", "घबराया", "गया ", "देखा ", "रुका", "उठा ", "आया ", "सोचता", "सहमा", "दौड़ा", "पहुँचा", "बोला", "काँपा"])


def _has(t, cues):
    return any(c in t for c in cues)


def _first(t, table):
    for cues, *rest in table:
        if any(c in t for c in cues):
            return rest
    return None


def props_of(t):
    return [p for p, cues in PROPS.items() if _has(t, cues)]


def roles_of(t):
    """roles named in a sentence: whole-word match (a role word is never a prefix of another word: 'माँगे' is not 'माँ')"""
    toks = set(t.split())
    pad = " " + t + " "
    out = []
    for cues, rid, arch, g in ROLES:
        if any((c in toks) or (" " in c and (" " + c + " ") in pad) or (c + "ों" in toks) for c in cues):
            out.append(rid)
    return out


def subject_is_partner(t):
    """the sentence's grammatical subject is a supporting role ('क्लर्क ने ...', 'दोस्त का चेहरा ...') and not the protagonist"""
    first = t.split()[:2]
    return bool(roles_of(" ".join(first)))


def emotion_of(t):
    for emo in ("realization", "fear", "suspicion", "anger", "sadness", "confusion", "hope", "relief"):
        if _has(t, EMOTIONS[emo]):
            return emo
    return "neutral"


# act rules, in priority order: (act, all-of cue groups); a group matches when ANY of its cues is in the text
def R(act, *groups):
    return act, [_n(g) for g in groups]


RULES = [
    R("OTHER_LOOKS_AT_PHONE", ["नजर", "नज़र", "देखा", "देखने"], ["फोन", "मोबाइल", "स्क्रीन"], ["माँ", "मां", "पापा", "दोस्त", "बहन", "भाई", "दादी", "दादा", "पिताजी", "पड़ोसी", "क्लर्क", "पुलिस", "अजनबी", "दुकानदार", "मैनेजर"]),
    R("OTHER_REACTS", ["चेहरा बदल", "चेहरे का रंग", "चेहरा उतर", "चेहरे पर", "सन्न", "हैरान रह"], ["माँ", "मां", "पापा", "दोस्त", "बहन", "भाई", "दादी", "दादा", "पड़ोसी", "क्लर्क", "पुलिस", "अजनबी", "दुकानदार", "मैनेजर", "इंस्पेक्टर"]),
    R("INSERT_SCREEN", ["लिखा था", "लिखा है", "स्क्रीन पर", "मैसेज में", "संदेश में", "सामने आया", "लिखा आया"]),
    R("REACH_PHONE", ["हाथ बढ़ाया", "हाथ बढ़ा", "हाथ आगे"], ["फोन", "मोबाइल", "काँपता", "कांपता", "धीरे", "हिचक", "डरते", "झिझक", "बढ़ाया"]),
    R("VISUALIZE_FLOW", ["खाते", "खातों", "जाल", "गायब", "उड़", "कट गए", "निकल गए", "ट्रांसफर"], ["पैसे", "रुपये", "रुपए", "लाख", "हजार", "रकम", "जाल"]),
    R("USE_ATM", ["एटीएम", "मशीन"], ["पिन", "डाला", "डाल", "निकाल", "कार्ड", "स्लॉट", "कैश", "रकम"]),
    R("GIVE_OBJECT", ["कार्ड", "पैसे", "नोट", "कैश", "रकम", "कागज", "दस्तावेज", "फॉर्म", "पिन", "फोन", "मोबाइल"], ["थमा", "दे दिया", "दिया", "बढ़ाया", "सौंप", "पकड़ाया", "थमाया"]),
    R("RECEIVE_OBJECT", ["कार्ड", "पैसे", "नोट", "कैश", "कागज", "रसीद", "फोन"], ["लौटा", "वापस", "लिया", "मिला", "थमाई"]),
    R("COUNT_MONEY", ["पैसे", "नोट", "कैश", "रकम", "रुपये", "नकद"], ["गिना", "गिन", "निकाले", "निकाला", "पकड़े", "हाथ में"]),
    R("READ_DOCUMENT", ["कागज", "दस्तावेज", "फॉर्म", "रसीद", "स्लिप", "नोटिस", "फाइल", "आवेदन"], ["पढ़", "देखा", "साइन", "दस्तखत", "भरा", "भरने"]),
    R("TYPE_LAPTOP", ["लैपटॉप", "कंप्यूटर", "वेबसाइट", "पोर्टल", "लॉगिन"], ["खोला", "टाइप", "डाला", "भरा", "क्लिक", "खोल"]),
    R("PHONE_CALL", ["कॉल"], ["उठाया", "आया", "आई", "किया", "बात", "रिसीव", "बजा"]),
    R("PHONE_ALERT", ["फोन", "मोबाइल", "मैसेज", "नोटिफिकेशन", "व्हाट्सएप", "व्हॉट्सऐप", "संदेश", "एसएमएस", "ग्रुप"], ["बज", "घंटी", "चमका", "आया", "आई", "वाइब्रेट", "ट्रिंग", "टिंग"]),
    R("TAKE_PHONE", ["फोन", "मोबाइल"], ["उठाया", "उठा लिया", "निकाला", "जेब से", "हाथ में", "थामा", "उठा"]),
    R("READ_MESSAGE", ["मैसेज", "संदेश", "एसएमएस", "स्क्रीन", "ग्रुप"], ["पढ़", "देखा", "खोला", "चेक"]),
    R("PERSON_ENTERS", ["दरवाज", "अंदर आ", "आ गया", "आ गई", "आ गए", "पहुँचे", "पहुँचा", "पहुंचा", "आते", "तभी"], ["आ", "खुला", "पहुँ", "पहुं", "दाखिल", "घुस"]),
    R("MEET", ["वहाँ", "वहां", "काउंटर", "सामने", "मिला", "मिली", "मिलने"], ["क्लर्क", "कैशियर", "दुकानदार", "पुलिस", "इंस्पेक्टर", "अजनबी", "आदमी", "मैनेजर", "टीचर", "अधिकारी", "दोस्त", "सिपाही", "औरत", "लड़का", "शख्स", "टेलर"]),
    R("EYE_CONTACT", ["नजरें", "नज़रें", "की तरफ देखा", "को देखा", "आँखों में", "आंखों में", "घूरा"]),
    R("STAND_UP", ["खड़ा", "खड़ी", "खड़े", "उठ खड़ा", "उठ खड़ी", "उठकर"]),
    R("RUN_AWAY", ["दौड़", "भागा", "भागी", "भाग "]),
    R("SIT_DOWN", ["बैठ", "कुर्सी पर", "सोफ़े पर", "सोफे पर"]),
    R("CROWD_WATCH", ["भीड़", "लोग", "आसपास", "राहगीर", "बाकी लोग", "सब देख"]),
    R("WALK_ACROSS", ["चल", "कदम", "क़दम", "टहल", "बढ़ा", "बढ़ी", "रास्ते"], ["पड़ा", "पड़ी", "दिया", "लगा", "लगी", "रहा", "रही", "कदम", "क़दम", "कमरे", "सड़क", "गली", "तरफ"]),
    R("SUSPECT", ["शक", "संदेह", "अजीब लगा", "झिझक", "हिचक", "सोच में", "कुछ ठीक नहीं", "सवाल उठा"]),
    R("BOTH_REALIZE", ["दोनों"], ["समझ", "जान", "पता चला", "एहसास", "समझे"]),
    R("REALIZE", ["समझ गया", "समझ गई", "समझ आया", "पता चला", "एहसास", "सच्चाई", "धोखा", "ठगी", "जाल", "चेहरे का रंग", "रंग उड़", "साँसें", "सांसें", "काँप", "घबरा", "डर"]),
    R("CONVERSE", ["बोला", "बोली", "कहा", "पूछा", "पूछी", "बताया", "बताई", "समझाया", "समझाई", "बात", "जवाब", "सुना", "सुनाया", "बोले", "कहती", "कहता"]),
    R("CLOSE_UP", ["कभी मत", "मत भरिए", "मत बताइए", "याद रखिए", "सीख", "हमेशा", "किसी को भी नहीं", "सोचिए", "सावधान", "जागरूक"]),
    R("RESOLVE", ["रुककर सोचा", "राहत", "बच गए", "बच गया", "बच गई", "सुकून", "इस बार", "अब वो", "आखिर", "आख़िर"]),
    R("LOOK_AT_PHONE", ["फोन", "मोबाइल", "स्क्रीन", "मैसेज"], ["देखा", "देखने", "नजर", "नज़र", "निहार"]),
    R("EYES_CHANGE", ["आँखें", "आंखें", "आँख", "भौंहें", "माथे"], ["सिकुड़", "तन", "चौड़ी", "फैल", "शिकन", "फटी"]),
    R("REACH_PHONE", ["हाथ बढ़ाया", "हाथ बढ़ा", "हाथ आगे", "बढ़ाया"]),
    R("ESTABLISH", ["अकेला", "अकेली", "रात के", "सुबह", "शाम", "कमरे में", "घर में", "बैठा था", "बैठी थी"]),
]


def classify(t, ctx):
    """act of one normalised segment given the running context (partner present? standing? first/last?)"""
    if t.startswith(("मैसेज", "संदेश", "message")):                                        # the message text itself is being read out (before any content rule)
        return "READ_MESSAGE" if ctx["holding"] else "LOOK_AT_PHONE"
    for act, groups in RULES:
        if all(any(c in t for c in g) for g in groups):
            if act in ("CONVERSE", "GIVE_OBJECT", "RECEIVE_OBJECT", "EYE_CONTACT") and not (ctx["partner"] or roles_of(t)):
                continue                                                      # a two-person act needs a second person
            if act == "PERSON_ENTERS" and not (roles_of(t) or ctx["partner_expected"]):
                continue
            if act == "MEET" and not roles_of(t):
                continue
            if act == "OTHER_LOOKS_AT_PHONE" and not ctx["partner"]:
                continue
            if act == "OTHER_REACTS" and not ctx["partner"]:
                continue
            if act == "READ_MESSAGE" and not ctx["holding"]:
                act = "LOOK_AT_PHONE"
            return act
    if t.startswith(("मैसेज", "संदेश", "message")):                                        # the message text itself is being read out
        return "READ_MESSAGE" if ctx["holding"] else "LOOK_AT_PHONE"
    return None


def llm_refine(story, model="qwen3:14b", timeout=240):
    """OPTIONAL: ask a local LLM to relabel each beat's act from the closed vocabulary. The answer is validated (unknown labels are dropped), then repaired by the act grammar. Returns the number of changed beats."""
    schema = {"type": "object", "properties": {"acts": {"type": "array", "items": {"type": "string", "enum": AC.VOCAB}}}, "required": ["acts"]}
    lines = "\n".join(f"{i + 1}. [{b['loc']}/{b['time']}] {b['text']}   (rule-based: {b['act']})" for i, b in enumerate(story["beats"]))
    doc = "\n".join(f"- {a}: {d['doc']}" for a, d in AC.ACTS.items())
    prompt = ("You label the beats of a short Hindi money-scam story with ONE dramatic act each. Keep the rule-based label unless another act is clearly better.\n" + doc + "\n\nBeats:\n" + lines +
              f"\n\nReturn JSON {{\"acts\": [...]}} with exactly {len(story['beats'])} labels.")
    body = {"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False, "think": False, "format": schema, "options": {"temperature": 0.1, "num_ctx": 8192, "seed": 7}}
    try:
        req = urllib.request.Request("http://localhost:11434/api/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})
        acts = json.loads(json.load(urllib.request.urlopen(req, timeout=timeout))["message"]["content"])["acts"]
    except Exception as e:
        story["provenance"].append(dict(step="llm_refine", error=str(e)[:120]))
        return 0
    if len(acts) != len(story["beats"]):
        story["provenance"].append(dict(step="llm_refine", error=f"wrong length {len(acts)}"))
        return 0
    changed = 0
    for b, a in zip(story["beats"], acts):
        if a in AC.ACTS and a != b["act"]:
            b["act"] = a
            changed += 1
    seq, ch = AC.repair([b["act"] for b in story["beats"]])
    for b, a in zip(story["beats"], seq):
        b["act"] = a
    story["provenance"].append(dict(step="llm_refine", model=model, changed=changed, repaired=ch))
    return changed


def _screen_text(text):
    m = re.search(r"[:：]\s*(.+)$", text)
    return (m.group(1) if m else text).strip()


def analyze(segments, notes=None, use_llm=False):
    notes = notes or {}
    segs = [dict(id=s.get("id") or s.get("beat_id") or f"n{i + 1:02d}", text=s["text"].strip(), start=s.get("start", s.get("start_seconds")), end=s.get("end", s.get("end_seconds")), words=s.get("words")) for i, s in enumerate(segments)]
    reasons = []
    if not 8 <= len(segs) <= 40:
        reasons.append(f"{len(segs)} narration segments: a Short needs 8-40")
    full = norm(" ".join(s["text"] for s in segs) + " " + notes.get("description", ""))
    if not _has(full, MONEY_STORY):
        reasons.append("no money / scam / psychology cue anywhere in the script (this factory tells money-psychology stories)")
    bad = [w for w in UNSUPPORTED_PLACES if w in full]
    if bad:
        reasons.append(f"places with no stage: {bad} (supported: {LOC.ALL})")
    if reasons:
        raise StoryNotSupported("; ".join(reasons))
    # ---- cast
    fem, masc = sum(1 for c in FEM if c in full + " "), sum(1 for c in MASC if c in full + " ")
    pro_g = notes.get("protagonist", {}).get("gender") or ("female" if fem > masc else "male")
    pro_arch = notes.get("protagonist", {}).get("archetype") or ("older man" if pro_g == "male" and _has(full, _n(["बुजुर्ग", "रिटायर", "पेंशन"])) and "बुजुर्ग" in norm(segs[0]["text"] + segs[1]["text"])
                                                                else "student" if _has(full, _n(["छात्र", "कॉलेज", "पढ़ाई", "स्टूडेंट"])) else ("young woman" if pro_g == "female" else "young man"))
    found = []
    for s in segs:
        for r in roles_of(norm(s["text"])):
            if r not in found:
                found.append(r)
    role_table = {rid: (arch, g) for _, rid, arch, g in ROLES}
    others = [r for r in found if not (r in ("mother", "father") and False)]
    if len(others) > 3:
        raise StoryNotSupported(f"{len(others)} distinct supporting roles {others}: at most 3 (1 principal + 2 extras)")
    principal = notes.get("other", {}).get("role") or (others[0] if others else None)
    # ---- beats
    beats, ctx, cur_loc, cur_time = [], dict(partner=False, partner_expected=bool(principal), standing=False, holding=False), None, None
    provenance = []
    default_loc = notes.get("location") or "bedroom"
    for i, s in enumerate(segs):
        t = norm(s["text"])
        loc, tm = LOC.find(t)
        if loc is None:
            loc = cur_loc or default_loc
        tm = tm or (notes.get("time") if cur_time is None else cur_time)
        res = LOC.resolve(loc, tm)
        if res["notes"]:
            provenance.append(dict(step="location_time", beat=s["id"], note=res["notes"][0]))
        cur_loc, cur_time = loc, res["time"]
        act = classify(t, ctx)
        roles = roles_of(t)
        if act is None:
            act = ("ARRIVE" if loc not in ("bedroom", "study", "living_room") else "ESTABLISH") if i == 0 else ("CLOSE_UP" if i == len(segs) - 2 else "CONVERSE" if ctx["partner"] else "OBSERVE")
            provenance.append(dict(step="unclassified", beat=s["id"], text=s["text"], fallback=act))
        moved = i > 0 and loc != beats[-1]["loc"]
        if moved:
            ctx["partner"] = False
            ctx["holding"] = False if act not in ("READ_MESSAGE",) else ctx["holding"]
            if act not in ("MEET", "ARRIVE", "INSERT_SCREEN", "VISUALIZE_FLOW", "RESOLVE"):
                act = "ARRIVE"
        if act in ("GIVE_OBJECT", "RECEIVE_OBJECT") and subject_is_partner(t):
            act = "RECEIVE_OBJECT" if act == "GIVE_OBJECT" else "GIVE_OBJECT"                    # 'क्लर्क ने फ़ॉर्म थमाया' = the protagonist RECEIVES
        if i == 0 and act not in AC.FIRSTS:
            act = "ESTABLISH" if loc in ("bedroom", "study", "living_room") else "ARRIVE"
        if i == len(segs) - 1:
            act = "RESOLVE"
        if act in ("PERSON_ENTERS", "MEET") or (roles and act in ("CONVERSE", "EYE_CONTACT", "GIVE_OBJECT")):
            ctx["partner"] = True
        if act in ("TAKE_PHONE", "PICK_UP", "PHONE_CALL"):
            ctx["holding"] = True
        if act in ("GIVE_OBJECT", "HAND_OVER") and "phone" in props_of(t):
            ctx["holding"] = False
        beats.append(dict(id=s["id"], text=s["text"], act=act, loc=loc, time=res["time"], emotion=emotion_of(t), props=props_of(t), roles=roles, subject="partner" if subject_is_partner(t) else "protagonist", data={}))
    # a location change starts with the protagonist ARRIVING there (unless the beat already establishes / meets someone)
    for i in range(1, len(beats)):
        if beats[i]["loc"] != beats[i - 1]["loc"] and beats[i]["act"] not in ("MEET", "PERSON_ENTERS", "ARRIVE", "RESOLVE", "INSERT_SCREEN", "VISUALIZE_FLOW"):
            beats[i]["scene_start"] = True
    for i, b in enumerate(beats):
        if b["act"] == "INSERT_SCREEN":
            b["data"] = dict(sender=notes.get("sender", "UNKNOWN"), time="अभी", text=_screen_text(b["text"]))
        if b["act"] == "VISUALIZE_FLOW":
            b["data"] = dict(amount=notes.get("amount", 100000), from_label="आपकी बचत", to=["खाता 1", "खाता 2", "खाता 3"])
        if b["act"] in ("GIVE_OBJECT", "RECEIVE_OBJECT"):
            b["data"]["prop"] = next((p for p in ("card", "money", "document", "phone") if p in b["props"]), "money")
    seq, changes = AC.repair([b["act"] for b in beats])
    if changes:
        provenance.append(dict(step="act_repair", changes=changes))
    if len(seq) != len(beats):                                                       # repair may PREPEND / APPEND to force the first / last act
        raise StoryNotSupported(f"act repair changed the number of beats ({len(beats)} -> {len(seq)}): {changes}")
    for b, a in zip(beats, seq):
        b["act"] = a
    # ---- scenes / cast graph
    scenes, prev = [], None
    for b in beats:
        key = (b["loc"], b["time"])
        if key != prev:
            scenes.append(dict(loc=b["loc"], time=b["time"], first=b["id"], beats=[]))
            prev = key
        scenes[-1]["beats"].append(b["id"])
    sid = "s_" + hashlib.sha1(json.dumps([s["text"] for s in segs], ensure_ascii=False).encode()).hexdigest()[:8]
    cast = dict(protagonist=dict(gender=pro_g, archetype=pro_arch, name=notes.get("protagonist", {}).get("name", "")),
                principal=dict(role=principal, archetype=role_table[principal][0], gender=role_table[principal][1]) if principal else None,
                extras=[dict(role=r, archetype=role_table[r][0], gender=role_table[r][1]) for r in others if r != principal][:2])
    story = dict(title=notes.get("title") or "कहानी", story_id=sid, slug=notes.get("slug") or sid, cast=cast, scenes=scenes, beats=beats, provenance=provenance, words=sum(len(s["text"].split()) for s in segs),
                 notes=notes, schema="kathaya.story_graph/1")
    if use_llm:
        llm_refine(story)
    return story


NOTE_TYPES = ("young man", "young woman", "middle-aged man", "middle-aged woman", "older man", "older woman", "student", "shopkeeper", "bank employee", "office worker", "teacher", "security guard", "customer", "parent")
ROLE_IDS = tuple(rid for _, rid, _, _ in ROLES)


def load_script(path):
    """story.md: '# Title' + optional `key: value` notes (protagonist/other/location/time/sender/amount) before a `---` line; the narration segments come from the segments JSON, not from here."""
    txt = open(path, encoding="utf-8").read()
    notes, title = {}, None
    head = txt.split("\n---", 1)[0]
    for ln in head.splitlines():
        m = re.match(r"#\s*(.+)", ln)
        if m and not title:
            title = m.group(1).strip()
            continue
        m = re.match(r"(\w+)\s*:\s*(.+)", ln)
        if m:
            k, v = m.group(1).lower(), m.group(2).strip()
            if k in ("protagonist", "other"):
                parts = [x.strip() for x in v.split(",")]
                d = dict(name=parts[0])
                for p in parts[1:]:
                    if p in ("male", "female"):
                        d["gender"] = p
                    elif p in NOTE_TYPES:
                        d["archetype"] = p
                    else:
                        d["role"] = p
                notes[k] = d
            else:
                notes[k] = int(v) if v.isdigit() else v
    notes["title"] = title or notes.get("title")
    notes["description"] = txt.split("\n---", 1)[1] if "\n---" in txt else ""
    return notes


def load_segments(path):
    d = json.load(open(path, encoding="utf-8"))
    return d["segments"] if isinstance(d, dict) else d


def graph_from_beats(title, beats, protagonist=None, principal=None, extras=(), slug=None, notes=None):
    """STRUCTURED entry (UI 'edit the acts' / test matrix): beats = [dict(act, loc, time, emotion, text, props=[], roles=[], subject, data={})] -> the same story graph `analyze` produces. The act sequence must be valid
    (acts.validate); locations/times must be supported. Raises StoryNotSupported otherwise."""
    protagonist = protagonist or dict(gender="male", archetype="young man")
    role_table = {rid: (arch, g) for _, rid, arch, g in ROLES}
    out = []
    for i, b in enumerate(beats):
        res = LOC.resolve(b["loc"], b.get("time"))
        out.append(dict(id=b.get("id") or f"n{i + 1:02d}", text=b.get("text") or f"{b['act']} {i + 1}", act=b["act"], loc=b["loc"], time=res["time"], emotion=b.get("emotion", "neutral"), props=list(b.get("props", [])),
                        roles=list(b.get("roles", [])), subject=b.get("subject", "protagonist"), data=dict(b.get("data", {}))))
    bad = AC.validate([b["act"] for b in out])
    if bad:
        raise StoryNotSupported("invalid act sequence: " + "; ".join(bad))
    scenes, prev = [], None
    for b in out:
        key = (b["loc"], b["time"])
        if key != prev:
            scenes.append(dict(loc=b["loc"], time=b["time"], first=b["id"], beats=[]))
            prev = key
        scenes[-1]["beats"].append(b["id"])
    sid = "s_" + hashlib.sha1(json.dumps([b["text"] for b in out] + [b["act"] for b in out] + [protagonist, principal, list(extras)], ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:8]
    cast = dict(protagonist=dict(gender=protagonist.get("gender", "male"), archetype=protagonist["archetype"], name=protagonist.get("name", "")),
                principal=dict(role=principal, archetype=role_table[principal][0], gender=role_table[principal][1]) if principal else None,
                extras=[dict(role=r, archetype=role_table[r][0], gender=role_table[r][1]) for r in extras][:2])
    return dict(title=title, story_id=sid, slug=slug or sid, cast=cast, scenes=scenes, beats=out, provenance=[dict(step="structured_input")], words=sum(len(b["text"].split()) for b in out), notes=notes or {}, schema="kathaya.story_graph/1", fixes={})
