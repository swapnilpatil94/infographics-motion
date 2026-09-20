"""Hindi text helpers for narration: numerals -> spoken words (the TTS and the aligner need Devanagari words, not digits), and `spoken()` normalisation."""
import re

_0_99 = ("शून्य एक दो तीन चार पाँच छह सात आठ नौ दस ग्यारह बारह तेरह चौदह पंद्रह सोलह सत्रह अठारह उन्नीस बीस इक्कीस बाईस तेईस चौबीस पच्चीस छब्बीस सत्ताईस अट्ठाईस उनतीस तीस इकतीस बत्तीस तैंतीस चौंतीस पैंतीस छत्तीस सैंतीस अड़तीस उनतालीस चालीस "
         "इकतालीस बयालीस तैंतालीस चौवालीस पैंतालीस छियालीस सैंतालीस अड़तालीस उनचास पचास इक्यावन बावन तिरेपन चौवन पचपन छप्पन सत्तावन अट्ठावन उनसठ साठ इकसठ बासठ तिरसठ चौंसठ पैंसठ छियासठ सड़सठ अड़सठ उनहत्तर सत्तर इकहत्तर बहत्तर तिहत्तर "
         "चौहत्तर पचहत्तर छिहत्तर सतहत्तर अठहत्तर उन्यासी अस्सी इक्यासी बयासी तिरासी चौरासी पचासी छियासी सत्तासी अट्ठासी नवासी नब्बे इक्यानवे बानवे तिरानवे चौरानवे पचानवे छियानवे सत्तानवे अट्ठानवे निन्यानवे").split()
assert len(_0_99) == 100
_DIG = str.maketrans("०१२३४५६७८९", "0123456789")


def number_words(n):
    """0 <= n < 10**9 in Indian grouping: 12500 -> 'बारह हज़ार पाँच सौ', 2500000 -> 'पच्चीस लाख'"""
    if n < 100:
        return _0_99[n]
    out = []
    for unit, name in ((10 ** 7, "करोड़"), (10 ** 5, "लाख"), (1000, "हज़ार"), (100, "सौ")):
        q, n = divmod(n, unit)
        if q:
            out.append(number_words(q) + " " + name)
    if n:
        out.append(_0_99[n])
    return " ".join(out)


_NUM = re.compile(r"(₹\s*)?(\d[\d,]*)(?:\.(\d+))?")


def spoken(text):
    """display text -> what the narrator reads: numerals as words, dashes as pauses, quote marks removed"""
    t = text.translate(_DIG)

    def sub(m):
        n = int(m.group(2).replace(",", ""))
        if n >= 10 ** 9:
            return m.group(0)
        w = number_words(n)
        if m.group(3):
            w += " दशमलव " + " ".join(number_words(int(c)) for c in m.group(3))
        return w + (" रुपये" if m.group(1) else "")
    t = _NUM.sub(sub, t)
    t = re.sub(r"\s*[—–]\s*", ", ", t)
    t = re.sub(r"[\"'“”‘’]", "", t)
    return re.sub(r"\s+", " ", t).strip(" ,")


DEVA = re.compile(r"[ऀ-ॿ]")
LATIN = re.compile(r"[A-Za-z]")


def language_of(text):
    d, l = len(DEVA.findall(text)), len(LATIN.findall(text))
    if d == 0 and l == 0:
        return "unknown"
    return "hi" if d >= l else ("en" if d == 0 else "hinglish")


def numbers_in(text):
    """every integer written with digits in the text (Indian / Western comma grouping, Devanagari digits): '12,500' -> 12500; 'लाख' / 'हज़ार' multipliers are applied to the number before them"""
    t = text.translate(_DIG)
    out = []
    for m in re.finditer(r"(\d[\d,]*)(\s*(करोड़|लाख|हज़ार|हजार))?", t):
        n = int(m.group(1).replace(",", "") or 0)
        mult = {"करोड़": 10 ** 7, "लाख": 10 ** 5, "हज़ार": 1000, "हजार": 1000}.get(m.group(3), 1)
        out.append(n * mult)
    return out
