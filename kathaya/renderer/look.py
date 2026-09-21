"""KATHAYA LOOK: the finishing layer of a Short - what makes a frame read as a Short and not as a raw render. Applied per frame after the scene is composited, ONLY when the plan carries `plan["look"]` (legacy films never do).

    caption   1-3 words at a time, big, the word being spoken is highlighted, amounts in their own colour, a small pop-in (word times come from the narration timeline: TTS / timing JSON, else spread by length)
    callout   an amount the narration says ("25 lakh", "12,500") pops on screen exactly when it is said. Text is taken from the narration itself - nothing is invented (the same digits, the same unit)
    impact    a short punch-in on a callout, on the moment the phone lights up (with a flash) and on the realisation
    open      the film lands from a slightly tighter frame instead of starting dead-still
    grade     contrast / saturation / cool shadows-warm highlights / vignette

Everything is a pure function of (plan, time): deterministic, no randomness."""
import re

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, features

from engine.shorts import captions as CAP
from kathaya.story import hindi

VERSION = 1
W, H = CAP.W, CAP.H
CAPTION_Y = 1418                                                       # the band the engine's framing QC keeps faces out of
FONT_SIZE = 92
MAX_WORDS, MAX_CHARS = 3, 20
YELLOW, WHITE, MINT, INK = (255, 221, 51), (255, 255, 255), (96, 240, 150), (14, 12, 24)
_UNITS = ("लाख", "हज़ार", "हजार", "करोड़", "करोड")
_AMOUNT = re.compile(r"(₹\s*)?(\d[\d,]*)(?:\.(\d+))?(\s*(?:लाख|हज़ार|हजार|करोड़|करोड))?(\s*(?:रुपये|रुपए|रुपया|₹))?")
_PUNCT = "।,.!?—–-'\"“”‘’:;"
_NUMWORDS = set(hindi._0_99) | {"सौ", "हज़ार", "हजार", "लाख", "करोड़", "करोड"}


def _norm(w):
    return w.strip(_PUNCT + " ")


def words_of(seg):
    """[{word,start,end}] of a narration segment (real word times when the timeline has them, else spread by length like the legacy captions)"""
    if seg.get("words"):
        return [dict(word=w["word"], start=w["start"], end=w["end"]) for w in seg["words"]]
    toks = seg["text"].split()
    tot = sum(len(w) for w in toks) or 1
    cur, out = seg["start"], []
    for w in toks:
        d = (seg["end"] - seg["start"]) * len(w) / tot
        out.append(dict(word=w, start=cur, end=cur + d))
        cur += d
    return out


def callouts(segments, max_n=3):
    """amounts the narration says -> [{t0, t1, text, word}]: the text is written as in the story ("₹25 लाख"), the time is the moment the first spoken word of the amount starts"""
    out = []
    for seg in segments:
        text = seg["text"].translate(hindi._DIG)
        ws = words_of(seg)
        norm = [_norm(w["word"]) for w in ws]
        for m in _AMOUNT.finditer(text):
            if not m.group(2):
                continue
            n = int(m.group(2).replace(",", ""))
            unit = (m.group(4) or "").strip()
            is_money = bool(m.group(1) or m.group(5) or unit)
            if not is_money or n >= 10 ** 9:
                continue
            spoken_tokens = hindi.spoken(m.group(2) + (" " + unit if unit else "")).split()
            at = next((i for i in range(len(norm) - len(spoken_tokens) + 1) if norm[i:i + len(spoken_tokens)] == spoken_tokens), None)
            if at is None:
                continue
            digits = m.group(2) if "," in m.group(2) or n < 1000 else f"{n:,}"
            out.append(dict(t0=round(ws[at]["start"], 3), t1=round(ws[at]["start"] + 2.1, 3), text=f"₹{digits}" + (f" {unit}" if unit else ""), word=" ".join(spoken_tokens), segment=seg["id"]))
    return sorted(out, key=lambda c: c["t0"])[:max_n]


def design(segments):
    """the look section of a Kathaya plan (goes into plan_overrides; part of the plan hash)"""
    return dict(version=VERSION, caption=dict(style="word_highlight", size=FONT_SIZE, max_words=MAX_WORDS), callouts=callouts(segments), open_zoom=1.09, open_seconds=0.9, grade="night_punch")


def sfx(plan):
    """the sounds that go with the punches: a low hit as an amount pops, a whoosh as the film opens"""
    out = [dict(t=round(c["t0"], 3), kind="impact", gain=0.55) for c in plan["look"].get("callouts", [])]
    if plan["look"].get("open_seconds"):
        out.append(dict(t=0.0, kind="whoosh", gain=0.9))
    return out


# ---------------------------------------------------------------- captions
_font_c = {}


def _font(size):
    if size not in _font_c:
        layout = ImageFont.Layout.RAQM if features.check("raqm") else ImageFont.Layout.BASIC
        _font_c[size] = ImageFont.truetype(CAP.FONT, size, index=CAP.BOLD_INDEX, layout_engine=layout)
    return _font_c[size]


_BIG = {"सौ", "हज़ार", "हजार", "लाख", "करोड़", "करोड"}


def amount_words(words):
    """indices of the words of an amount inside a caption chunk: digits, the big units (सौ / हज़ार / लाख / करोड़) and the number words next to them - a lone 'एक' or 'दो' is just a word"""
    toks = [_norm(w["word"]) for w in words]
    if not any(t in _BIG or any(ch.isdigit() for ch in t) for t in toks):
        return set()
    return {i for i, t in enumerate(toks) if t in _NUMWORDS or any(ch.isdigit() for ch in t)}


def chunks(segments):
    """caption chunks [{t0, t1, words:[{word,start,end}]}] - a chunk never crosses a segment"""
    from engine.shorts import film as F
    out = []
    for seg in segments:
        ws = words_of(seg)
        cs = F._chunk_words(ws, max_words=MAX_WORDS, max_chars=MAX_CHARS)
        for j, ch in enumerate(cs):
            t0 = ch[0]["start"] - 0.04
            t1 = cs[j + 1][0]["start"] - 0.02 if j + 1 < len(cs) else ch[-1]["end"] + 0.25
            out.append(dict(t0=t0, t1=t1, words=ch))
    return out


_cap_cache = {}


def _caption_layer(words, active, size=FONT_SIZE):
    """RGBA crop (float 0..1) + (x, y) of its top-left in the frame, centred on the safe area, and its bbox. `active` = index of the highlighted word (-1 none)."""
    key = (tuple(w["word"] for w in words), active, size)
    if key in _cap_cache:
        return _cap_cache[key]
    while True:
        f = _font(size)
        gap = f.getlength(" ") + 6
        widths = [f.getlength(w["word"]) for w in words]
        total = sum(widths) + gap * (len(words) - 1)
        if total <= CAP.SAFE["right"] - CAP.SAFE["left"] - 30 or size <= 44:
            break
        size -= 4
    pad = 26
    asc, desc = f.getmetrics()
    h = asc + desc + 2 * pad
    wpx = int(total) + 2 * pad
    layer = Image.new("RGBA", (wpx, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x = pad
    amt = amount_words(words)
    for i, w in enumerate(words):
        col = YELLOW if i == active else (MINT if i in amt else WHITE)
        d.text((x, pad + 7), w["word"], font=f, fill=(0, 0, 0, 130), stroke_width=11, stroke_fill=(0, 0, 0, 130))
        d.text((x, pad), w["word"], font=f, fill=col + (255,), stroke_width=8, stroke_fill=INK + (255,))
        x += widths[i] + gap
    arr = np.asarray(layer).astype(np.float32) / 255.0
    cx = (CAP.SAFE["left"] + CAP.SAFE["right"]) // 2
    ox, oy = int(cx - wpx / 2), int(CAPTION_Y - h / 2)
    ink = np.asarray(layer)[:, :, 3] > 40
    ys, xs = np.where(ink)
    bbox = (ox + int(xs.min()), oy + int(ys.min()), ox + int(xs.max()), oy + int(ys.max()))
    _cap_cache[key] = (arr, ox, oy, bbox)
    return _cap_cache[key]


_call_cache = {}


def _callout_layer(text, size=170):
    key = (text, size)
    if key in _call_cache:
        return _call_cache[key]
    f = _font(size)
    while f.getlength(text) > W - 220 and size > 80:
        size -= 6
        f = _font(size)
    pad = 60
    asc, desc = f.getmetrics()
    wpx, h = int(f.getlength(text)) + 2 * pad, asc + desc + 2 * pad
    base = Image.new("RGBA", (wpx, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(base)
    d.text((pad, pad + 8), text, font=f, fill=(0, 0, 0, 150), stroke_width=16, stroke_fill=(0, 0, 0, 150))
    d.text((pad, pad), text, font=f, fill=MINT + (255,), stroke_width=12, stroke_fill=INK + (255,))
    glow = cv2.GaussianBlur(np.asarray(base).astype(np.float32)[:, :, 3], (0, 0), 22)
    arr = np.asarray(base).astype(np.float32) / 255.0
    _call_cache[key] = (arr, (glow / 255.0).astype(np.float32))
    return _call_cache[key]


def _over(img, arr, ox, oy, opacity=1.0, scale=1.0):
    """alpha-composite an RGBA crop onto img (in place) at top-left (ox, oy), optionally scaled about its centre"""
    if scale != 1.0:
        hh, ww = arr.shape[:2]
        nw, nh = max(2, int(ww * scale)), max(2, int(hh * scale))
        arr = cv2.resize(arr, (nw, nh), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
        ox, oy = int(ox + (ww - nw) / 2), int(oy + (hh - nh) / 2)
    hh, ww = arr.shape[:2]
    x0, y0, x1, y1 = max(0, ox), max(0, oy), min(W, ox + ww), min(H, oy + hh)
    if x1 <= x0 or y1 <= y0:
        return img
    sub = arr[y0 - oy:y1 - oy, x0 - ox:x1 - ox]
    a = sub[:, :, 3:4] * opacity
    img[y0:y1, x0:x1] = img[y0:y1, x0:x1] * (1 - a) + sub[:, :, :3] * a
    return img


def _pop(u):
    """ease-out-back 0..1 -> scale 0.8 .. 1.0 with a small overshoot"""
    u = min(1.0, max(0.0, u))
    c1, c3 = 1.9, 2.9
    return 1 + c3 * (u - 1) ** 3 + c1 * (u - 1) ** 2


# ---------------------------------------------------------------- grade
_vig = {}


def _vignette():
    if "v" not in _vig:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H * 0.47) / (H / 2)) ** 2)
        _vig["v"] = (1.0 - 0.30 * np.clip(r - 0.35, 0, 1) ** 1.6)[:, :, None].astype(np.float32)
    return _vig["v"]


def grade(img, name="night_punch"):
    """cinematic finish: gentle S-curve contrast, richer colour, cool shadows / warm highlights, vignette. Skips near-white pages (infographic cards) so paper stays paper"""
    x = img.astype(np.float32)
    mean = float(x[::16, ::16].mean())
    if mean < 0.30:                                                                 # a night / dark scene stays readable: lift the shadows in proportion to how dark the frame is
        x = np.power(np.clip(x, 0.0, 1.0), 1.0 - 0.40 * min(1.0, (0.30 - mean) / 0.20))
    luma = (x[:, :, 0] * 0.299 + x[:, :, 1] * 0.587 + x[:, :, 2] * 0.114)[:, :, None]
    x = luma + (x - luma) * 1.22
    x = x + (x - 0.42) * 0.16 * (1.0 - np.abs(luma - 0.42) * 0.9)
    shadow = np.clip(1.0 - luma * 2.2, 0, 1)
    high = np.clip(luma * 2.0 - 0.9, 0, 1)
    x = x + shadow * np.array([-0.012, 0.006, 0.030], np.float32) + high * np.array([0.028, 0.012, -0.018], np.float32)
    x = x * _vignette()
    return np.clip(x, 0.0, 1.0)


def _zoom(img, s):
    if s <= 1.0005:
        return img
    cw, ch = W / s, H / s
    x0, y0 = (W - cw) / 2, (H - ch) / 2
    m = np.array([[s, 0, -x0 * s], [0, s, -y0 * s]], np.float32)
    return cv2.warpAffine(img, m, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


# ---------------------------------------------------------------- the per-film object
class Look:
    def __init__(self, plan):
        self.cfg = plan["look"]
        self.chunks = chunks(plan["narration"]["segments"])
        self.callouts = self.cfg.get("callouts", [])
        # moments that get a punch: (t, strength, flash)
        self.impacts = [(c["t0"], 0.05, 0.0) for c in self.callouts]
        for sh in plan["shots"]:
            if sh.get("act") == "PHONE_ALERT":
                self.impacts.append((sh["t0"] + 0.05, 0.035, 0.42))
            elif sh.get("act") == "REALIZE":
                self.impacts.append((sh["t0"] + 0.05, 0.045, 0.0))
        self.title = plan.get("title_card")
        self.holds = [(sh["t0"], sh["t1"]) for sh in plan["shots"] if (sh.get("camera") or {}).get("move") == "hold" and sh["t1"] - sh["t0"] >= 1.0]      # a locked-off shot still breathes

    def zoom_at(self, tt):
        s = 1.0
        oz, os_ = self.cfg.get("open_zoom", 1.0), self.cfg.get("open_seconds", 0.0)
        if os_ and tt < os_:
            u = tt / os_
            s *= 1.0 + (oz - 1.0) * (1 - u) ** 2.2
        for a, b in self.holds:
            if a <= tt < b:
                s *= 1.0 + 0.05 * (tt - a) / (b - a)
        for t, k, _f in self.impacts:
            d = tt - t
            if 0 <= d < 0.42:
                s *= 1.0 + k * min(1.0, d / 0.05) * float(np.exp(-d * 8.0))
        return s

    def flash_at(self, tt):
        a = 0.0
        for t, _k, fl in self.impacts:
            d = tt - t
            if fl and 0 <= d < 0.22:
                a = max(a, fl * (1 - d / 0.22) ** 2)
        return a

    def caption_at(self, tt):
        for ch in self.chunks:
            if ch["t0"] <= tt <= ch["t1"]:
                active = -1
                for i, w in enumerate(ch["words"]):
                    if w["start"] - 0.03 <= tt:
                        active = i
                return ch, active
        return None, -1

    def apply(self, img, tt, hide_caption=False):
        """-> (img, bbox|None, caption_text|None). Order: zoom (scene only) -> grade -> flash -> callouts -> captions (never zoomed, so the QC caption band is stable)."""
        img = _zoom(img, self.zoom_at(tt))
        img = grade(img, self.cfg.get("grade", "night_punch"))
        fl = self.flash_at(tt)
        if fl:
            img = img * (1 - fl) + fl
        for c in self.callouts:
            d = tt - c["t0"]
            if 0 <= d <= c["t1"] - c["t0"]:
                arr, glow = _callout_layer(c["text"])
                life = c["t1"] - c["t0"]
                op = min(1.0, d / 0.06) * min(1.0, (life - d) / 0.25)
                hh, ww = arr.shape[:2]
                ox, oy = (W - ww) // 2, 1180 - hh // 2
                sc = 0.75 + 0.25 * _pop(d / 0.22)
                g = np.zeros((hh, ww, 4), np.float32)
                g[:, :, :3] = np.array(MINT, np.float32) / 255.0
                g[:, :, 3] = glow * 0.9
                img = _over(img, g, ox, oy, op, sc)
                img = _over(img, arr, ox, oy, op, sc)
        bbox = text = None
        if not hide_caption:
            ch, active = self.caption_at(tt)
            if ch:
                arr, ox, oy, bbox = _caption_layer(ch["words"], active)
                op = min(1.0, (tt - ch["t0"]) / 0.05, (ch["t1"] - tt) / 0.06)
                img = _over(img, arr, ox, oy, max(0.0, op), 0.86 + 0.14 * _pop((tt - ch["t0"]) / 0.14))
                text = " ".join(w["word"] for w in ch["words"])
        return img, bbox, text
