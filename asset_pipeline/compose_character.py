"""Composes a full Open Peeps character SVG by substituting the face/hair/
pose sub-groups of a pre-aligned base illustration ("a person/*.svg") with
different atom files from "Separate Atoms/".

Why substitution instead of building from atoms directly: Open Peeps atom
SVGs each carry their OWN tight viewBox with no shared anchor metadata (the
alignment data lives in the original Sketch/Figma file, not the flat SVG
export) — a known hard problem (see the peeps-creator project's own
"head alignment is still being tuned" notes). The pre-composed examples
under "a person/" ARE correctly aligned. Their internal group structure
(<g id="Head" transform="..."><g id="head/..">..<g id="face/Smile">..)
wraps each part with ONE transform on the shared "Head" group and no
further per-atom transform — meaning every face atom, sharing the same
~290x293 local canvas as the original "Smile" face, drops in at the same
transform without needing new alignment math. This is verified against
the source files, not assumed.
"""
import re
import os


def _find_balanced_group(text, open_tag_end):
    """Given the index right after an opening <g ...> tag's '>', scans
    forward counting nested <g ...> / </g> pairs to find the MATCHING
    close tag (not just the next one, and not just whatever's before
    </svg> — a naive greedy regex breaks as soon as a group isn't the
    last one in the document, which is exactly the bug this replaced).
    Returns (inner_text, index_just_after_the_matching_</g>)."""
    depth = 1
    pos = open_tag_end
    tag_re = re.compile(r"<g[\s>]|</g>")
    for m in tag_re.finditer(text, open_tag_end):
        if m.group().startswith("<g"):
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                return text[open_tag_end:m.start()], m.end()
    raise ValueError("unbalanced <g> tags — no matching close found")


def _extract_group_inner(svg_text, group_id):
    """Returns the raw inner XML of the first top-level <g id="{group_id}">
    in a *standalone* atom SVG (i.e. one whose outermost <g> IS the atom)."""
    m = re.search(r'<g id="' + re.escape(group_id) + r'"[^>]*>', svg_text)
    if not m:
        raise ValueError(f"could not find group '{group_id}' in atom SVG")
    inner, _ = _find_balanced_group(svg_text, m.end())
    return inner


def _read_atom_inner(path):
    """Atom files use a <title> that doesn't always match the actual <g id=...>
    (e.g. title 'head/mono/Flat Top' vs id 'head/mono/Flat-Top') — read the
    id straight off the first top-level <g>, not the title."""
    text = open(path, encoding="utf-8").read()
    m = re.search(r"<svg[^>]*>.*?<g id=\"([^\"]+)\"", text, re.S)
    if not m:
        raise ValueError(f"no top-level <g id=...> found in {path}")
    return _extract_group_inner(text, m.group(1))


def _replace_group(doc_text, group_id, new_inner):
    pattern = re.compile(r'(<g id="' + re.escape(group_id) + r'"[^>]*>).*?(</g>)', re.S)
    if not pattern.search(doc_text):
        raise ValueError(f"group '{group_id}' not found in base document")
    return pattern.sub(lambda m: m.group(1) + new_inner + m.group(2), doc_text, count=1)


def _extract_top_level_group(doc, group_id_pattern, out_path, wrapper_id):
    """Pulls ONE top-level <g id="..."> block (transform attribute and all)
    out of a composed document into its own standalone SVG, keeping the
    original document's viewBox/canvas. Because the group's own transform
    is preserved verbatim, a piece extracted this way and imported into
    Blender lands at EXACTLY the position it had inside the original
    composition — no alignment math needed, no guessing: the composed
    document already proved these pieces align, we're just splitting the
    file, not the geometry."""
    m = re.search(r'<g id="(' + group_id_pattern + r')"([^>]*)>', doc)
    if not m:
        raise ValueError(f"no group matching '{group_id_pattern}' found")
    group_id, attrs = m.group(1), m.group(2)
    inner = _extract_group_inner(doc, group_id)
    header = re.search(r'(<\?xml.*?<svg[^>]*>)', doc, re.S).group(1)
    out_doc = header + f'\n<g id="{wrapper_id}"{attrs}>{inner}</g>\n</svg>'
    if out_path:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(out_doc)
    return out_doc


def extract_head_only(base_svg_path, face_atom_path=None, head_atom_path=None, out_path=None):
    """Writes a standalone SVG containing ONLY the base document's <g id="Head">
    group (hair+face, with substitutions applied) — for building a head
    that can be positioned/rotated independently of the body. The group's
    own translate() is kept, so this aligns with extract_body_only()'s
    output automatically when both are imported at the same Blender
    origin (see engine.character.rig)."""
    doc = open(base_svg_path, encoding="utf-8").read()
    if face_atom_path:
        doc = _replace_group(doc, "face/Smile", _read_atom_inner(face_atom_path))
    if head_atom_path:
        m = re.search(r'<g id="(head/mono/[^"]+)"', doc)
        if m:
            doc = _replace_group(doc, m.group(1), _read_atom_inner(head_atom_path))
    return _extract_top_level_group(doc, r"Head", out_path, "Head_standalone")


def extract_body_only(base_svg_path, out_path=None):
    """Writes a standalone SVG containing ONLY the base document's
    <g id="pose/..."> group (body/legs silhouette, no head) — the
    counterpart to extract_head_only(). Same base document, same canvas,
    transform preserved, so the two pieces recombine correctly."""
    doc = open(base_svg_path, encoding="utf-8").read()
    return _extract_top_level_group(doc, r"pose/[^\"]+", out_path, "Body_standalone")


def compose(base_svg_path, face_atom_path=None, head_atom_path=None, out_path=None):
    doc = open(base_svg_path, encoding="utf-8").read()
    if face_atom_path:
        doc = _replace_group(doc, "face/Smile", _read_atom_inner(face_atom_path))
    if head_atom_path:
        # base uses a fixed sub-id like "head/mono/Bun-2"; find whatever it
        # currently is rather than hardcoding, then replace THAT group.
        m = re.search(r'<g id="(head/mono/[^"]+)"', doc)
        if not m:
            raise ValueError("no head/mono/* group found in base document")
        doc = _replace_group(doc, m.group(1), _read_atom_inner(head_atom_path))
    if out_path:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(doc)
    return doc


if __name__ == "__main__":
    import sys
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ATOMS = os.path.join(ROOT, "assets/character/raw/open_peeps/extracted/Flat Assets/Separate Atoms")
    BASE = os.path.join(ATOMS, "a person/sitting.svg")

    expressions = {
        "relaxed": "Calm.svg",
        "curious": "Awe.svg",
        "uneasy": "Concerned.svg",
        "realization": "Fear.svg",
    }
    out_dir = os.path.join(ROOT, "assets/character/normalized/rahul_svg")
    for name, face_file in expressions.items():
        compose(
            BASE,
            face_atom_path=os.path.join(ATOMS, "face", face_file),
            head_atom_path=os.path.join(ATOMS, "head", "Flat Top.svg"),
            out_path=os.path.join(out_dir, f"rahul_{name}.svg"),
        )
        print("wrote", name)
