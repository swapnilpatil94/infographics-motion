"""Hand-authored environment/prop vector art — deliberately simple flat
shapes with ink-style strokes, NOT sourced from any clipart library (see
Gate 2 asset research: no CC0/permissive source matched Open Peeps'
hand-drawn style for furniture, and mismatched clipart would look worse
than nothing). Kept minimal/graphic on purpose: detailed character over a
simpler environment is a deliberate, common illustration technique.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_DIR = os.path.join(ROOT, "assets/environment/raw/kathaaya_minimal")
PROP_DIR = os.path.join(ROOT, "assets/props/raw/kathaaya_minimal")
os.makedirs(ENV_DIR, exist_ok=True)
os.makedirs(PROP_DIR, exist_ok=True)

INK = "#0d0c0b"
STROKE_W = 6


def svg(width, height, body):
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{width}px" height="{height}px" viewBox="0 0 {width} {height}" version="1.1" xmlns="http://www.w3.org/2000/svg">
<title>{{title}}</title>
{body}
</svg>'''


def write(name, width, height, body, title):
    text = svg(width, height, body).replace("{title}", title)
    path = os.path.join(ENV_DIR if title.startswith("environment/") else PROP_DIR, name)
    with open(path, "w") as f:
        f.write(text)
    print("wrote", path)


# --- Window: frame + cross mullions + a soft glow rect behind the glass.
write(
    "window.svg", 320, 420,
    f'''<g id="environment/window">
  <rect x="10" y="10" width="300" height="400" rx="6" fill="#dfe6f2" />
  <path d="M160,10 L160,410 M10,210 L310,210" stroke="{INK}" stroke-width="{STROKE_W-2}" />
  <rect x="10" y="10" width="300" height="400" rx="6" fill="none" stroke="{INK}" stroke-width="{STROKE_W}" stroke-linejoin="round" />
</g>''',
    "environment/window",
)

# --- Nightstand: simple box with a drawer line + a small foot.
write(
    "nightstand.svg", 260, 260,
    f'''<g id="environment/nightstand">
  <path d="M20,40 L240,40 L230,240 L30,240 Z" fill="#caa26a" stroke="{INK}" stroke-width="{STROKE_W}" stroke-linejoin="round" />
  <path d="M40,110 L220,110" stroke="{INK}" stroke-width="{STROKE_W-2}" />
  <circle cx="130" cy="75" r="6" fill="{INK}" />
</g>''',
    "environment/nightstand",
)

# --- Bed edge: a simple wedge/rect suggesting a mattress corner in frame.
write(
    "bed_edge.svg", 500, 220,
    f'''<g id="environment/bed_edge">
  <path d="M0,40 L500,10 L500,220 L0,220 Z" fill="#8798b8" stroke="{INK}" stroke-width="{STROKE_W}" stroke-linejoin="round" />
  <path d="M0,40 L500,10" stroke="{INK}" stroke-width="{STROKE_W-2}" />
</g>''',
    "environment/bed_edge",
)

# --- Phone: rounded body + screen (screen fill is swapped/lit separately).
write(
    "phone.svg", 90, 180,
    f'''<g id="props/phone">
  <rect x="6" y="6" width="78" height="168" rx="14" fill="#161514" stroke="{INK}" stroke-width="{STROKE_W-2}" stroke-linejoin="round" />
  <rect id="screen" x="14" y="22" width="62" height="136" rx="4" fill="#2a2a2a" />
</g>''',
    "props/phone",
)
