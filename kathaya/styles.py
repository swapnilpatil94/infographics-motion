"""Named creative profiles for KATHAAYA.

Profiles guide scene direction; they do not claim renderer capabilities that the
asset catalog/manifest has not implemented. Missing mythology assets must remain
MISSING and pass through the existing approval workflow.
"""

STYLES = {
    "kathaya_default": {
        "label": "KATHAAYA Story",
        "description": "General narrative 2D/2.5D storytelling.",
        "guidance": "",
    },
    "mythology_ink": {
        "label": "Mythology Ink",
        "description": "Indian epic storytelling with cinematic ink-on-parchment art direction.",
        "guidance": """MYTHOLOGY INK MODE — CREATIVE DIRECTION
Treat this as a respectful, source-aware Indian epic adaptation, not a generic modern story.
VISUAL LANGUAGE
- Target cinematic Indian ink storytelling: warm off-white/parchment ground, expressive black ink linework, progressive ink/stroke reveals, layered 2.5D depth and restrained vermilion red with muted divine gold only when narratively justified.
- This is an art-direction brief, not permission to invent renderer capabilities. Use only catalog assets and manifest capabilities. If a required character, costume, weapon, location, pose, divine effect or action is unavailable, report it as MISSING/UNSUPPORTED through the existing resolver; never silently replace it with a modern or unrelated asset.
- Give every shot a distinct narrative job: establish the court/world, reveal a character, show a readable action, show a reaction, clarify a moral dilemma, escalate tension, or resolve the beat. Avoid repeated static portraits and decorative particles as a substitute for storytelling.
- Preserve character identity across shots: same costume, ornaments, silhouette, age, hair, skin depiction, carried objects and relative scale unless the story explicitly changes them. Keep geography and eyelines coherent in multi-character scenes.
- Use wide establishing compositions for kingdoms/courts, medium shots for exchanges, close reactions for moral conflict, and slow reveals for divine or consequential moments only when supported by the camera manifest.
- Depict divine and sacred figures respectfully; do not use horror tropes or arbitrary superhero aesthetics. Do not claim a miracle, dialogue or textual detail as universal when versions of the epic differ.
- Narration is the source of truth. Do not invent dialogue or present uncertain interpretations as settled history. Show the question/conflict visually rather than plastering explanatory paragraphs on screen.
- Every visual must be feasible with the current renderer. Do not claim painterly motion, cloth simulation, complex combat, 3D gods, parallax or lighting effects unless the selected assets/capabilities can actually execute them.
QUALITY GATES
- Each narration segment must have a specific visual proof or purposeful dramatic reaction.
- Avoid repeating the same composition for consecutive beats unless the repetition intentionally communicates a change.
- The climax must be shown through an observable action/reaction or transformation, not only a title card.
- Keep captions short and phone-readable. End on a resolved image, not a prolonged static card.
- If required assets or actions are missing, stop for explicit asset approval/build; do not render a falsely complete film.""",
    },
}


def get_style(style):
    """Return a known profile or raise ValueError with supported options."""
    if style not in STYLES:
        raise ValueError(
            f"unknown style {style!r}; available: {', '.join(sorted(STYLES))}"
        )
    return STYLES[style]


def direct_for_style(style, direction=""):
    """Combine profile guidance with optional user direction deterministically."""
    profile = get_style(style)
    parts = [profile["guidance"].strip(), (direction or "").strip()]
    return "\n\n".join(part for part in parts if part)
