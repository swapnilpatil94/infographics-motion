"""Procedural phone UI screens (SVG -> resvg): the same UI objects are used on the held phone and in full-screen inserts.

A screen is DATA: UIScreen("incoming_call", {"name": "बैंक सिक्योरिटी", "number": "1800 ..."}). Text is real shaped Devanagari,
values (amounts, timers) are formatted from the story state, so continuity is enforced by construction. 
Types: incoming_call, in_call, sms, bank_transfer, debit_alerts, balance, otp.
API-compatible with engine.shorts.phone.PhoneScreen (compose_ui / uw / uh) so rig2 and ScreenInsert accept it unchanged.
"""
import io
import math
import random

import numpy as np
import resvg_py
from PIL import Image, ImageDraw

from engine.factory.procedural import inr
from engine.shorts.captions import _font

UW, UH, SCALE = 440, 800, 2.0
FONT = "Kohinoor Devanagari, Devanagari Sangam MN, sans-serif"
_meas = ImageDraw.Draw(Image.new("RGB", (4, 4)))


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def wrap(s, size, maxw):
    f = _font(int(size))
    lines, cur = [], ""
    for w in str(s).split():
        t = (cur + " " + w).strip()
        if _meas.textlength(t, font=f) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    return lines + ([cur] if cur else [])


def _svg(body, bg="#0b1220"):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{UW}" height="{UH}" viewBox="0 0 {UW} {UH}">'
            f'<rect width="{UW}" height="{UH}" fill="{bg}"/>{body}</svg>')


def _t(x, y, s, size, fill="#fff", weight=400, anchor="middle"):
    return f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{esc(s)}</text>'


def incoming_call(d, t):
    pulse = 1 + 0.06 * math.sin(t * 5)
    b = f'<circle cx="{UW / 2}" cy="230" r="{70 * pulse:.1f}" fill="#22324f"/><circle cx="{UW / 2}" cy="230" r="56" fill="#3a4d74"/>'
    b += f'<path d="M{UW / 2 - 18},218 q4,-14 16,-6 l8,8 q4,6 -2,10 l-6,4 q6,14 20,22 l4,-6 q4,-6 10,-2 l8,8 q8,10 -4,18 q-14,8 -40,-16 q-26,-24 -14,-38 z" fill="#cfe0f7" transform="scale(1) translate(2,-2)"/>'
    b += _t(UW / 2, 150, d.get("label", "आने वाली कॉल"), 24, "#9fb3d1")
    b += _t(UW / 2, 360, d.get("name", "बैंक सिक्योरिटी"), 38, "#fff", 700)
    b += _t(UW / 2, 408, d.get("number", ""), 26, "#9fb3d1")
    b += f'<circle cx="110" cy="660" r="46" fill="#e0483c"/><rect x="88" y="656" width="44" height="9" rx="4" fill="#fff"/>'
    b += f'<circle cx="{UW - 110}" cy="660" r="{46 * (1 + 0.05 * math.sin(t * 6)):.1f}" fill="#2fb44f"/><path d="M{UW - 128},672 q10,-30 36,-24" stroke="#fff" stroke-width="9" fill="none" stroke-linecap="round"/>'
    return _svg(b, "#0e1626")


def in_call(d, t):
    secs = int(d.get("start_s", 0) + t)
    b = f'<circle cx="{UW / 2}" cy="200" r="54" fill="#3a4d74"/>' + _t(UW / 2, 320, d.get("name", "बैंक सिक्योरिटी"), 36, "#fff", 700)
    b += _t(UW / 2, 366, "कॉल जारी है" if d.get("hide_timer", True) else f"{secs // 60:02d}:{secs % 60:02d}", 30, "#9fd0ff")
    r = random.Random(int(t * 10))
    for i in range(21):
        h = 8 + abs(math.sin(i * 0.6 + t * 6)) * 60 * (0.4 + 0.6 * r.random())
        b += f'<rect x="{50 + i * 17}" y="{470 - h / 2:.1f}" width="9" height="{h:.1f}" rx="4" fill="#5fb4ff"/>'
    for i, lab in enumerate(("म्यूट", "कीपैड", "स्पीकर")):
        b += f'<circle cx="{90 + i * 130}" cy="640" r="40" fill="#22324f"/>' + _t(90 + i * 130, 710, lab, 20, "#9fb3d1")
    b += f'<circle cx="{UW / 2}" cy="742" r="0" fill="none"/>'
    return _svg(b, "#0e1626")


def sms(d, t):
    b = f'<rect width="{UW}" height="120" fill="#1d6fdc"/>' + _t(UW / 2, 72, d.get("sender", "अज्ञात नंबर"), 32, "#fff", 700)
    lines = wrap(d.get("text", ""), 28, UW - 130)
    h = 40 + 38 * len(lines)
    b += f'<rect x="28" y="170" width="{UW - 90}" height="{h}" rx="26" fill="#e9eef6"/>'
    for i, ln in enumerate(lines):
        b += _t(52, 218 + 38 * i, ln, 28, "#1a2333", 400, "start")
    b += _t(60, 170 + h + 34, d.get("time", "अभी"), 20, "#7b8799", 400, "start")
    return _svg(b, "#f7f9fc")


def bank_transfer(d, t):
    press = 1.0 if d.get("pressed", False) else 0.0
    b = f'<rect width="{UW}" height="120" fill="#12315f"/>' + _t(UW / 2, 74, d.get("title", "फंड ट्रांसफ़र"), 32, "#fff", 700)
    b += _t(40, 190, "प्राप्तकर्ता", 22, "#6b7788", 400, "start") + _t(40, 236, d.get("to", "सुरक्षित खाता"), 32, "#111a28", 700, "start")
    b += _t(40, 330, "राशि", 22, "#6b7788", 400, "start") + _t(40, 400, inr(d.get("amount", 0)), 64, "#12315f", 700, "start")
    b += f'<line x1="40" y1="420" x2="{UW - 40}" y2="420" stroke="#c9d3e4" stroke-width="3"/>'
    b += _t(40, 470, d.get("note", ""), 24, "#c0392b", 400, "start")
    b += f'<rect x="40" y="620" width="{UW - 80}" height="86" rx="43" fill="{"#0c7a3a" if press else "#2fb44f"}"/>' + _t(UW / 2, 676, d.get("cta", "पुष्टि करें"), 34, "#fff", 700)
    return _svg(b, "#f4f7fb")


def debit_alerts(d, t):
    items = d.get("items", [])
    b = _t(UW / 2, 90, "नोटिफ़िकेशन", 30, "#dfe8f5", 700)
    n_show = min(len(items), 1 + int(t / 0.35))
    for i, it in enumerate(items[:n_show]):
        y = 150 + i * 190
        b += f'<rect x="20" y="{y}" width="{UW - 40}" height="166" rx="28" fill="#f5f8fc"/><rect x="40" y="{y + 26}" width="56" height="56" rx="14" fill="#d8493c"/>'
        b += _t(116, y + 52, "डेबिट अलर्ट", 26, "#111a28", 700, "start") + _t(116, y + 92, f"{inr(it['amount'])} निकाले गए", 30, "#c0392b", 700, "start")
        if it.get("balance") is not None:
            b += _t(116, y + 132, f"शेष राशि {inr(it['balance'])}", 24, "#2a3444", 400, "start")
        else:
            b += _t(116, y + 132, "आपके खाते से", 24, "#2a3444", 400, "start")
    return _svg(b, "#0b1a33")


def balance(d, t):
    b = f'<rect width="{UW}" height="120" fill="#12315f"/>' + _t(UW / 2, 74, "खाता बैलेंस", 32, "#fff", 700)
    b += _t(UW / 2, 250, "उपलब्ध राशि", 26, "#6b7788")
    b += _t(UW / 2, 350, inr(d.get("amount", 0)), 64, "#c0392b" if d.get("low", True) else "#0c7a3a", 700)
    if d.get("previous") is not None:
        b += _t(UW / 2, 430, f"पहले: {inr(d['previous'])}", 28, "#7b8799")
        b += f'<line x1="{UW / 2 - 120}" y1="418" x2="{UW / 2 + 120}" y2="418" stroke="#7b8799" stroke-width="3"/>'
    return _svg(b, "#f4f7fb")


def otp(d, t):
    b = f'<rect x="20" y="180" width="{UW - 40}" height="200" rx="28" fill="#f5f8fc"/>' + _t(UW / 2, 250, d.get("sender", "बैंक"), 28, "#111a28", 700)
    b += _t(UW / 2, 330, f"OTP: {d.get('code', '••••••')}", 44, "#12315f", 700)
    return _svg(b, "#0b1a33")


SCREENS = dict(incoming_call=incoming_call, in_call=in_call, sms=sms, bank_transfer=bank_transfer, debit_alerts=debit_alerts, balance=balance, otp=otp)


class UIScreen:
    """compose_ui(bright, banner_pos) -> HxWx4 float RGBA (0..255): drop-in for PhoneScreen (rig2 held phone + ScreenInsert)."""
    uw, uh = int(UW * SCALE), int(UH * SCALE)

    def __init__(self, kind, data=None):
        if kind not in SCREENS:
            raise KeyError(f"UI screen '{kind}' not in {sorted(SCREENS)}")
        self.kind, self.data, self.t = kind, dict(data or {}), 0.0
        self._cache = {}

    def set(self, kind=None, data=None, t=0.0):
        if kind:
            self.kind = kind
        if data is not None:
            self.data = dict(data)
        self.t = t

    def compose_ui(self, bright=1.0, banner_pos=0.0):
        key = (self.kind, round(self.t * 8) / 8, repr(sorted(self.data.items())))
        if key not in self._cache:
            if len(self._cache) > 60:
                self._cache.clear()
            svg = SCREENS[self.kind](self.data, self.t)
            png = bytes(resvg_py.svg_to_bytes(svg_string=svg, zoom=SCALE))
            self._cache[key] = np.asarray(Image.open(io.BytesIO(png)).convert("RGBA")).astype(np.float32)
        ui = self._cache[key].copy()
        ui[:, :, :3] *= max(0.0, min(1.2, bright))
        return ui


# element anchors in UI units (x, y, w, h) - where a hand-drawn GP ring should land for emphasis
ANCHORS = dict(incoming_call=(60, 320, 320, 110), in_call=(60, 290, 320, 100), sms=(28, 170, 350, 190), bank_transfer=(30, 320, 380, 110),
               debit_alerts=(20, 150, 400, 166), balance=(60, 290, 320, 100), otp=(20, 180, 400, 200))
