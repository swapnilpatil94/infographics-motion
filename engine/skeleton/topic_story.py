"""TOPIC -> STORY. Turns a topic ("fake WhatsApp investment group", "courier parcel scam", ...) into a validated story: cast, a sequence of dramatic ACTS (`acts.py`) and one Hindi narration line per act.

Layers (each one degrades to the next, so the system always produces something valid or refuses honestly):
  1. domain PACK (deterministic): keyword-matched scam/fraud domain with its own message, bait, amount, money flow, realisation and lesson lines, and its own act arc;
  2. LLM CUSTOMISATION (qwen3:14b, JSON schema): title, names, message text, bait line, hook, lesson, amount, act arc - every field validated (Devanagari-only spoken text, no digits/latin in narration,
     amount snapped to a spoken-number table, arc repaired by `acts.repair`); a rejected field falls back to the pack's value and the decision is recorded in `story["provenance"]`;
  3. line TEMPLATES: the Hindi narration line of every act is composed from the (validated) fields with gender/relation agreement.
A topic the stage cannot carry (mythology, history, science...) raises TopicNotSupported instead of pretending.
"""
import hashlib
import json
import os
import re
import urllib.request

from engine.skeleton import acts as AC, styles as ST

OLLAMA = "http://localhost:11434/api/chat"
DIRECTOR = "qwen3:14b"
DEVA = re.compile(r"[ऀ-ॿ]")
SPOKEN_OK = re.compile(r"^[ऀ-ॿ\s,।?!\.\-'’]+$")           # narration must be pure Devanagari (+ punctuation): TTS aligner tokens = whitespace tokens


class TopicNotSupported(Exception):
    pass


AMOUNTS = {25000: "पच्चीस हज़ार", 50000: "पचास हज़ार", 75000: "पचहत्तर हज़ार", 100000: "एक लाख", 150000: "डेढ़ लाख", 250000: "ढाई लाख", 500000: "पाँच लाख", 1000000: "दस लाख"}

# canonical arc (the hand-authored reference film) + two structural variants
ARC_FULL = ["ESTABLISH", "PHONE_ALERT", "LOOK_AT_PHONE", "EYES_CHANGE", "REACH_PHONE", "PICK_UP", "READ_MESSAGE", "REALIZE", "STAND_UP", "WALK_ACROSS", "PERSON_ENTERS", "EYE_CONTACT", "OTHER_LOOKS_AT_PHONE",
            "HAND_OVER", "OTHER_REACTS", "INSERT_SCREEN", "VISUALIZE_FLOW", "BOTH_REALIZE", "CLOSE_UP", "RESOLVE"]
ARC_TIGHT = ["ESTABLISH", "PHONE_ALERT", "LOOK_AT_PHONE", "REACH_PHONE", "PICK_UP", "READ_MESSAGE", "INSERT_SCREEN", "REALIZE", "STAND_UP", "PERSON_ENTERS", "EYE_CONTACT", "HAND_OVER", "OTHER_REACTS",
             "VISUALIZE_FLOW", "BOTH_REALIZE", "CLOSE_UP", "RESOLVE"]
ARC_SLOW = ["ESTABLISH", "PHONE_ALERT", "EYES_CHANGE", "REACH_PHONE", "PICK_UP", "READ_MESSAGE", "REALIZE", "STAND_UP", "WALK_ACROSS", "PERSON_ENTERS", "EYE_CONTACT", "OTHER_LOOKS_AT_PHONE", "HAND_OVER",
            "OTHER_REACTS", "INSERT_SCREEN", "BOTH_REALIZE", "VISUALIZE_FLOW", "CLOSE_UP", "RESOLVE"]

PACKS = {
    "bank_kyc": dict(keys=["otp", "kyc", "bank", "बैंक", "ओटीपी", "account block", "खाता"], title="एक ग़लत कॉल", alert="तभी फ़ोन बज उठा।", eyes="अनजान नंबर। आँखें सिकुड़ गईं।", teaser="आपका खाता तुरंत ब्लॉक होगा!",
                     sender="BANK-KYC", sms="आपका KYC अधूरा है। ओटीपी बताइए, वरना खाता बंद कर दिया जाएगा। bit.ly/kyc-now", hook="ओटीपी बताइए, वरना खाता बंद।", amount=250000, flow_from="आपकी बचत",
                     realize="दोनों समझ गए, ये असली बैंक नहीं है।", lesson="एक ग़लत कॉल, और सब बदल सकता था।", arc=ARC_FULL),
    "lottery": dict(keys=["lottery", "prize", "jackpot", "kbc", "लॉटरी", "इनाम", "जीत"], title="जो इनाम माँगा ही नहीं", alert="तभी फ़ोन पर मैसेज चमका।", eyes="अनजान भेजने वाला। आँखें सिकुड़ गईं।", teaser="आपने पाँच लाख जीत लिए!",
                    sender="PRIZE-DESK", sms="बधाई! आपने इनाम जीता है। इनाम पाने के लिए पहले प्रोसेसिंग फ़ीस भेजें। tinyurl.com/claim-now", hook="इनाम पाने के लिए पहले फ़ीस भेजिए।", amount=50000, flow_from="आपकी फ़ीस",
                    realize="दोनों समझ गए, इनाम नहीं, ये ठगी है।", lesson="जो इनाम माँगा नहीं, उसकी फ़ीस कभी मत भरिए।", arc=ARC_TIGHT),
    "job_offer": dict(keys=["job", "naukri", "work from home", "part-time", "नौकरी", "जॉब", "task", "वर्क फ्रॉम होम"], title="घर बैठे कमाई का जाल", alert="तभी फ़ोन में नोटिफ़िकेशन चमका।", eyes="अनजान नंबर। भौंहें तन गईं।",
                      teaser="घर बैठे रोज़ की कमाई पक्की!", sender="JOB-HR", sms="पार्ट-टाइम जॉब! रोज़ कमाइए। पहले रजिस्ट्रेशन फ़ीस भेजें। t.me/job-hr", hook="नौकरी के लिए पहले फ़ीस भेजिए।", amount=75000,
                      flow_from="आपकी फ़ीस", realize="दोनों समझ गए, असली नौकरी में पैसे पहले नहीं लगते।", lesson="जहाँ नौकरी के लिए पैसे माँगे जाएँ, वहाँ रुक जाइए।", arc=ARC_SLOW),
    "parcel": dict(keys=["parcel", "courier", "customs", "arrest", "cbi", "police", "पार्सल", "कूरियर", "गिरफ़्तार", "डिजिटल अरेस्ट", "digital arrest"], title="फ़ोन पर पुलिस", alert="तभी फ़ोन बज उठा।", eyes="अनजान नंबर। साँस थम गई।",
                   teaser="आपके नाम का पार्सल पकड़ा गया!", sender="COURIER", sms="आपके नाम के पार्सल में ग़ैरक़ानूनी सामान मिला है। तुरंत बात करें, वरना गिरफ़्तारी होगी।", hook="तुरंत पैसे भेजिए, वरना गिरफ़्तारी।",
                   amount=150000, flow_from="आपकी बचत", realize="दोनों समझ गए, पुलिस फ़ोन पर पैसे नहीं माँगती।", lesson="डर के आगे रुकिए, और किसी अपने से पूछिए।", arc=ARC_FULL),
    "investment": dict(keys=["invest", "stock", "trading", "crypto", "share", "whatsapp group", "ponzi", "निवेश", "शेयर", "ग्रुप", "दोगुना"], title="दोगुना पैसे का वादा", alert="तभी फ़ोन में नोटिफ़िकेशन चमका।", eyes="अनजान ग्रुप। आँखें सिकुड़ गईं।",
                       teaser="सात दिन में पैसा दोगुना!", sender="VIP-GROUP", sms="VIP ग्रुप में जुड़िए! सात दिन में पैसा दोगुना। आज ही निवेश करें। wa.me/vip-invest", hook="सात दिन में पैसा दोगुना।", amount=100000,
                       flow_from="आपका निवेश", realize="दोनों समझ गए, दोगुना पैसा हमेशा जाल होता है।", lesson="जो वादा असली न लगे, वो असली नहीं होता।", arc=ARC_FULL),
    "upi_refund": dict(keys=["upi", "refund", "qr", "paytm", "phonepe", "gpay", "रिफ़ंड", "यूपीआई", "collect request"], title="रिफ़ंड का लिंक", alert="तभी फ़ोन पर मैसेज चमका।", eyes="अनजान लिंक। आँखें सिकुड़ गईं।",
                       teaser="आपका रिफ़ंड तैयार है!", sender="REFUND-INFO", sms="आपका रिफ़ंड तैयार है। पाने के लिए लिंक खोलें और अपना पिन डालें। pay-refund.in/claim", hook="रिफ़ंड के लिए अपना पिन डालिए।", amount=25000,
                       flow_from="आपका खाता", realize="दोनों समझ गए, पैसा पाने के लिए पिन नहीं डालते।", lesson="पिन और ओटीपी, किसी को भी नहीं बताना।", arc=ARC_TIGHT),
    "loan_app": dict(keys=["loan", "लोन", "instant loan", "blackmail", "ब्लैकमेल"], title="तुरंत लोन का फंदा", alert="तभी फ़ोन बज उठा।", eyes="अनजान नंबर। माथे पर शिकन आ गई।", teaser="तुरंत लोन, कोई काग़ज़ नहीं!",
                     sender="QUICK-LOAN", sms="तुरंत लोन, कोई काग़ज़ नहीं! ऐप डाउनलोड करें और सारे कॉन्टैक्ट्स की अनुमति दें। quick-loan.app", hook="ऐप में सारे कॉन्टैक्ट्स की अनुमति दीजिए।", amount=25000,
                     flow_from="आपका लोन", realize="दोनों समझ गए, ये लोन नहीं, फंदा है।", lesson="अनजान ऐप को कभी अपनी पूरी दुनिया मत सौंपिए।", arc=ARC_SLOW),
}
GENERIC = ["scam", "fraud", "phishing", "fake", "cyber", "ठगी", "धोखा", "फ्रॉड", "साइबर", "स्कैम", "नकली", "नक़ली"]
NAMES = {"male": ["अर्जुन", "रोहन", "आरव", "विवेक", "कबीर"], "female": ["अनन्या", "पूजा", "नेहा", "काव्या", "श्रुति"]}
REL = {"mother": dict(noun="माँ", came="आईं", obj="माँ को", rel="माँ"), "father": dict(noun="पापा", came="आए", obj="पापा को", rel="पापा"), "sister": dict(noun="बहन", came="आई", obj="बहन को", rel="बहन"),
       "friend": dict(noun="दोस्त", came="आया", obj="दोस्त को", rel="दोस्त")}


# ------------------------------------------------------------------ LLM plumbing
def _chat(prompt, schema, temperature=0.4, timeout=240):
    body = {"model": DIRECTOR, "messages": [{"role": "user", "content": prompt}], "stream": False, "think": False, "format": schema, "options": {"temperature": temperature, "num_ctx": 8192, "seed": 7}}
    req = urllib.request.Request(OLLAMA, json.dumps(body).encode(), {"Content-Type": "application/json"})
    return json.loads(json.load(urllib.request.urlopen(req, timeout=timeout))["message"]["content"])


def llm_available():
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
        return True
    except Exception:
        return False


def classify(topic):
    """-> (pack_id, why). Keyword scoring on the topic; raises TopicNotSupported when no domain pack fits."""
    t = topic.lower()
    score = {pid: sum(1 for k in p["keys"] if k.lower() in t) for pid, p in PACKS.items()}
    best = max(score, key=lambda k: (score[k], -list(PACKS).index(k)))
    if score[best] > 0:
        return best, f"topic matches pack '{best}' ({score[best]} keyword(s))"
    if any(g.lower() in t for g in GENERIC):
        return "bank_kyc", "generic scam topic -> default pack 'bank_kyc'"
    return None, "no keyword match"


def _spoken_ok(s, max_words=14, min_words=2):
    s = (s or "").strip()
    n = len(s.split())
    return bool(s) and SPOKEN_OK.match(s) is not None and min_words <= n <= max_words


def _snap_amount(v, default):
    try:
        v = int(v)
    except Exception:
        return default
    return min(AMOUNTS, key=lambda a: abs(a - v))


def _customise(topic, pack_id, pack, log):
    """qwen3:14b (schema) -> field overrides; returns (fields, provenance)."""
    schema = {"type": "object", "properties": {
        "title": {"type": "string"}, "protagonist_name": {"type": "string"}, "protagonist_gender": {"type": "string", "enum": ["male", "female"]}, "other": {"type": "string", "enum": list(REL)},
        "sender": {"type": "string"}, "sms_text": {"type": "string"}, "teaser": {"type": "string"}, "hook": {"type": "string"}, "flow_from": {"type": "string"}, "lesson": {"type": "string"},
        "amount": {"type": "integer", "enum": list(AMOUNTS)}, "arc": {"type": "array", "items": {"type": "string", "enum": AC.VOCAB}, "minItems": 15, "maxItems": 21}},
        "required": ["title", "protagonist_name", "protagonist_gender", "other", "sender", "sms_text", "teaser", "hook", "flow_from", "lesson", "amount", "arc"]}
    acts_doc = "\n".join(f"- {a}: {d['doc']}" + (f" [needs {','.join(d['needs'])}]" if d["needs"] else "") for a, d in AC.ACTS.items())
    prompt = (f"You write a 45-second Hindi cyber-safety micro-story about: \"{topic}\".\nStage: one bedroom at night, a young protagonist, a phone message, a family member who walks in.\n"
              f"Default for this domain ({pack_id}): title='{pack['title']}', bait='{pack['teaser']}', hook='{pack['hook']}', lesson='{pack['lesson']}', message='{pack['sms']}'.\n"
              "Write your own versions that fit THIS topic. Rules: title/teaser/hook/flow_from/lesson are HINDI in Devanagari only (no digits, no English letters), teaser<=8 words, hook<=9 words, lesson<=11 words, title<=5 words, "
              "flow_from<=3 words (what the victim would lose, e.g. 'आपकी बचत'). sender = a generic ASCII sender id like 'BANK-KYC' or 'JOB-HR' (NEVER a real company). sms_text = the fake message as it appears "
              "on the phone (Hindi, may include one short fake link), <=110 chars. protagonist_name = a common Hindi first name in Devanagari.\n"
              f"arc = the ordered dramatic acts (15-21) of the film. It must start with ESTABLISH, end with RESOLVE, contain INSERT_SCREEN and BOTH_REALIZE, no act repeated except READ_MESSAGE/EYE_CONTACT/CLOSE_UP. "
              f"Acts and prerequisites:\n{acts_doc}")
    d = _chat(prompt, schema)
    return d


def _pick(topic, key, options):
    h = int(hashlib.sha1(f"{topic}|{key}".encode()).hexdigest(), 16)
    return options[h % len(options)]


def arc_ok(arc):
    """A generated arc is accepted only if it is a real story shape (not 'startle every beat')."""
    from collections import Counter
    c = Counter(arc)
    return (15 <= len(arc) <= 21 and c["INSERT_SCREEN"] >= 1 and c["BOTH_REALIZE"] >= 1 and "PERSON_ENTERS" in arc and "PICK_UP" in arc
            and max(c.values()) <= 2 and not AC.validate(arc))


# ------------------------------------------------------------------ line templates
def lines_for(story_fields):
    f = story_fields
    a, fem = f["protagonist"]["name"], f["protagonist"]["gender"] == "female"
    r = REL[f["other"]["relation"]]
    g = (lambda m_, f_: f_ if fem else m_)
    tw = f["time_word"]
    L = {
        "ESTABLISH": [f"रात के {tw}। कमरे में {g('अकेला', 'अकेली')} {a}।"],
        "PHONE_ALERT": [f["alert"]],
        "LOOK_AT_PHONE": [f"{a} ने स्क्रीन की तरफ़ देखा।"],
        "EYES_CHANGE": [f["eyes"]],
        "REACH_PHONE": ["उसने काँपता हाथ बढ़ाया।"],
        "PICK_UP": ["और फ़ोन उठा लिया।"],
        "READ_MESSAGE": [f"मैसेज: {f['teaser']}"],
        "REALIZE": ["चेहरे का रंग उड़ गया।", "साँसें तेज़ हो गईं।"],
        "STAND_UP": [g("वो घबराकर उठ खड़ा हुआ।", "वो घबराकर उठ खड़ी हुई।")],
        "WALK_ACROSS": ["बेचैन क़दम, कमरे के आर-पार।"],
        "PERSON_ENTERS": [f"तभी दरवाज़ा खुला। {r['noun']} अंदर {r['came']}।"],
        "EYE_CONTACT": [f"{a} ने {r['rel']} की तरफ़ देखा।"],
        "OTHER_LOOKS_AT_PHONE": [f"{r['rel']} की नज़र उसके हाथ के फ़ोन पर पड़ी।"],
        "HAND_OVER": [f"उसने चुपचाप फ़ोन {r['obj']} थमा दिया।"],
        "OTHER_REACTS": [f"{r['rel']} का चेहरा बदल गया।"],
        "INSERT_SCREEN": [f"स्क्रीन पर लिखा था: {f['hook']}"],
        "VISUALIZE_FLOW": [f"{AMOUNTS[f['amount']]} रुपये, तीन खाते... एक पूरा जाल।"],
        "BOTH_REALIZE": [f["realize"]],
        "CLOSE_UP": [f["lesson"]],
        "RESOLVE": ["पर इस बार, दोनों ने रुककर सोचा।"],
    }
    return L


def write(topic, use_llm=True, seed=7, log=print):
    """-> story dict (JSON-serialisable): title, story_id, slug, cast, beats[{id, act, text, data}], provenance."""
    prov = []
    pack_id, why = classify(topic)
    if pack_id is None:
        raise TopicNotSupported(f"'{topic}': the stage (a bedroom at night, a phone message, a family member) can only carry phone-scam / fraud-awareness topics. Supported domains: "
                                + ", ".join(PACKS) + ". Mythology/history/science/travel topics need new sets and props (see docs/TOPIC_SYSTEM.md).")
    pack = PACKS[pack_id]
    prov.append(dict(step="domain", result=pack_id, why=why))
    F = dict(title=pack["title"], alert=pack["alert"], eyes=pack["eyes"], teaser=pack["teaser"], hook=pack["hook"], realize=pack["realize"], lesson=pack["lesson"], amount=pack["amount"], flow_from=pack["flow_from"],
             sender=pack["sender"], sms=pack["sms"], protagonist_gender=_pick(topic, "gender", ["male", "female"]), relation=_pick(topic, "rel", ["mother", "mother", "father", "sister", "friend"]))
    F["protagonist_name"] = _pick(topic, "name", NAMES[F["protagonist_gender"]])
    F["arc"] = list(pack["arc"])
    F["time_word"] = _pick(topic, "time", ["ग्यारह बजे", "दस बजे", "बारह बजे"])
    llm = None
    if use_llm and llm_available():
        try:
            llm = _customise(topic, pack_id, pack, log)
            prov.append(dict(step="llm", model=DIRECTOR, raw=llm))
        except Exception as e:
            prov.append(dict(step="llm", error=str(e)[:200]))
    elif use_llm:
        prov.append(dict(step="llm", error="ollama not reachable -> deterministic packs only"))
    if llm:
        acc, rej = [], []
        for k, lim in (("title", 6), ("teaser", 9), ("hook", 10), ("lesson", 12), ("flow_from", 3)):
            (acc if _spoken_ok(llm.get(k), lim, 1) else rej).append(k)
            if k in acc:
                F[k] = llm[k].strip()
        nm = (llm.get("protagonist_name") or "").strip()
        if _spoken_ok(nm, 1, 1) and len(nm) <= 8:
            F["protagonist_name"], F["protagonist_gender"] = nm, llm.get("protagonist_gender", F["protagonist_gender"])
            acc.append("protagonist")
        else:
            rej.append("protagonist_name")
        if llm.get("other") in REL:
            F["relation"] = llm["other"]
            acc.append("other")
        snd = re.sub(r"[^A-Z0-9\-]", "", (llm.get("sender") or "").upper())[:14]
        if snd:
            F["sender"] = snd
            acc.append("sender")
        sms = (llm.get("sms_text") or "").strip()
        if 8 <= len(sms) <= 130:
            F["sms"] = sms
            acc.append("sms_text")
        F["amount"] = _snap_amount(llm.get("amount"), F["amount"])
        arc = [a for a in llm.get("arc", []) if a in AC.ACTS]
        arc, ch = AC.repair(arc)
        if arc_ok(arc):
            F["arc"] = arc
            acc.append("arc")
            if ch:
                prov.append(dict(step="arc_repair", changes=ch))
        else:
            rej.append("arc")
        prov.append(dict(step="llm_validation", accepted=acc, rejected_fallback_to_pack=rej))
    style_id = ST.PACK_STYLE.get(pack_id, "night_bedroom")
    style = ST.get(style_id)
    prov.append(dict(step="art_direction", style=style_id, family=style["family"], psychology=style["psychology"]))
    if style["cast"]["protagonist"]:                                       # the style casts the protagonist / the visitor (the LLM's names for them are replaced)
        F["protagonist_gender"] = style["cast"]["protagonist"]["gender"]
        F["protagonist_name"] = _pick(topic, "name", NAMES[F["protagonist_gender"]])
    if style["cast"]["other"]:
        F["relation"] = style["cast"]["other"]["relation"]
    if style["arc"]:
        F["arc"] = list(globals()[style["arc"]])
    arc, ch = AC.repair(F["arc"])
    assert not AC.validate(arc)
    fem = F["protagonist_gender"] == "female"
    fields = dict(protagonist=dict(name=F["protagonist_name"], gender=F["protagonist_gender"]), other=dict(relation=F["relation"], name=REL[F["relation"]]["noun"]), time_word=F["time_word"], alert=F["alert"],
                  eyes=F["eyes"], teaser=F["teaser"], hook=F["hook"], realize=F["realize"], lesson=F["lesson"], amount=F["amount"])
    L = lines_for(fields)
    beats, used = [], {}
    for i, act in enumerate(arc):
        opts = L[act]
        k = used.get(act, 0)
        used[act] = k + 1
        text = opts[k % len(opts)]
        d = {}
        if act == "INSERT_SCREEN":
            d = dict(sender=F["sender"], time="अभी", text=F["sms"])
        elif act == "VISUALIZE_FLOW":
            d = dict(amount=F["amount"], to=["खाता 1", "खाता 2", "खाता 3"], **{"from": F["flow_from"]})
        beats.append(dict(id=f"n{i + 1:02d}", act=act, text=text, data=d))
    for b in beats:                                                     # the narration is what the TTS reads: it must be clean Devanagari (validated) except the ':' colon of "मैसेज:"
        assert SPOKEN_OK.match(b["text"].replace(":", "")), b["text"]
    words = sum(len(b["text"].split()) for b in beats)
    sid = f"{pack_id}_" + hashlib.sha1(topic.encode()).hexdigest()[:5]
    story = dict(topic=topic, title=F["title"], story_id=sid, slug=re.sub(r"[^a-z0-9]+", "_", topic.lower()).strip("_")[:40] or sid, domain=pack_id,
                 cast=dict(protagonist=dict(name=F["protagonist_name"], gender=F["protagonist_gender"]), other=dict(relation=F["relation"], name=REL[F["relation"]]["noun"])), beats=beats, words=words,
                 est_duration_s=round(words / 3.0 + 6.0, 1), provenance=prov, presets=style["presets"], style=style_id)
    return story


def save(story, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(story, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return path
