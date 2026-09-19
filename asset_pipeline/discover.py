"""Records what was actually investigated for each asset source and why it
was accepted/rejected. This is NOT a live web scraper — asset discovery in
this project happened via the browser tool with a human-legible license
check per source (see each entry's `findings`), and this module is the
durable record of that research so future runs don't have to re-derive it.

Extending to a new source: add an entry here first (even before any file
is downloaded), decide accept/reject, THEN use downloader.py only for
accepted sources.
"""
SOURCES = {
    "open_peeps": {
        "url": "https://openpeeps.com/",
        "license": "CC0",
        "commercial_use": True,
        "attribution_required": False,
        "share_alike": False,
        "verdict": "ACCEPTED",
        "findings": (
            "Hand-drawn mix-and-match illustration library by Pablo Stanley. "
            "CC0, explicitly commercial-use-clear, no attribution needed. "
            "Real component structure (pose/head/face/body/facial-hair/"
            "accessories as separate SVGs) verified in the downloaded pack. "
            "Only distribution channel is Gumroad 'pay what you want' "
            "checkout ($0 works) — not bulk-scrapable, downloaded once "
            "manually via browser with the user's email."
        ),
    },
    "humaaans": {
        "url": "https://www.humaaans.com/",
        "license": "CC0",
        "commercial_use": True,
        "attribution_required": False,
        "share_alike": False,
        "verdict": "ACCEPTED (not used yet)",
        "findings": (
            "Same author/license as Open Peeps. More geometric/faceless "
            "style — weaker for close-up facial acting. Documented as a "
            "fallback for background/incidental figures, not pulled in."
        ),
    },
    "openmoji": {
        "url": "https://github.com/hfg-gmuend/openmoji",
        "license": "CC BY-SA 4.0",
        "commercial_use": True,
        "attribution_required": True,
        "share_alike": True,
        "verdict": "ACCEPTED for icon-scale props only (not used yet)",
        "findings": (
            "Confirmed via repo LICENSE.txt. Attribution + share-alike "
            "required — fine for a single credited icon, wrong for bulk "
            "asset use. Emoji-scale artwork, not full illustrations."
        ),
    },
    "svg_repo": {
        "url": "https://www.svgrepo.com/",
        "license": "mixed per-uploader",
        "commercial_use": None,
        "attribution_required": None,
        "share_alike": None,
        "verdict": "REJECTED",
        "findings": (
            "Site sits behind a Vercel bot-verification checkpoint — not "
            "bypassed (matches the project's own rule against defeating "
            "bot detection). Licensing is per-uploader and inconsistent "
            "even when reachable."
        ),
    },
    "wikimedia_commons": {
        "url": "https://commons.wikimedia.org/",
        "license": "mixed per-file",
        "commercial_use": None,
        "attribution_required": None,
        "share_alike": None,
        "verdict": "REJECTED for this use",
        "findings": (
            "Per-file licensing is workable in principle, but the corpus "
            "is photos/diagrams/historical scans — wrong content type for "
            "flat character/furniture illustration."
        ),
    },
    "openclipart": {
        "url": "https://openclipart.org/",
        "license": "CC0",
        "commercial_use": True,
        "attribution_required": False,
        "share_alike": False,
        "verdict": "REJECTED on quality, not license",
        "findings": (
            "Sitewide CC0 confirmed. Live search ('bedroom') returned "
            "dated, inconsistent amateur clip-art that would visually "
            "clash with Open Peeps' clean linework."
        ),
    },
    "svg_character_animator": {
        "url": "https://github.com/molauu/svg-character-animator",
        "license": "MIT (code); example art CC BY-NC-4.0 (not used)",
        "commercial_use": True,
        "attribution_required": False,
        "share_alike": False,
        "verdict": "EVALUATED as tooling, not adopted this pass",
        "findings": (
            "An MIT-licensed Claude Agent Skill for SVG state-morph "
            "animation (React/PNG-sequence/SwiftUI export). Purpose-built "
            "for exactly this rigging problem, but a separate toolchain "
            "from Blender. Not used so the existing Blender camera/"
            "lighting/render pipeline stays intact, per project direction. "
            "Worth reconsidering if smooth cross-fade morphing between "
            "expressions becomes a priority over hard-cut swaps."
        ),
    },
    "triangletechguy_2d_animation": {
        "url": "https://github.com/triangletechguy/2D_animation",
        "license": "none visible (all-rights-reserved by default)",
        "commercial_use": None,
        "attribution_required": None,
        "share_alike": None,
        "verdict": "REJECTED",
        "findings": (
            "Full browser rig editor (React/Fastify/MySQL), no LICENSE "
            "file, requires standing up a MySQL server for one shot."
        ),
    },
}


def get(source_id):
    return SOURCES.get(source_id)


def accepted_sources():
    return {k: v for k, v in SOURCES.items() if v["verdict"].startswith("ACCEPTED")}


if __name__ == "__main__":
    for sid, info in SOURCES.items():
        print(f"{sid:30s} {info['verdict']}")
