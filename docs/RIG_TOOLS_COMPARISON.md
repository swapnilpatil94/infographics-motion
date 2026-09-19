# 2D cutout rigging tools: what can we legally and technically reuse?

Checked 2026-09-19 against the live repos (GitHub API + READMEs) and **tested on this machine's Blender 5.2.2 LTS**.
Licence notes are engineering reading of public licence files, not legal advice.

| Tool | What it is | Licence | Blender 5.2 fit | Activity (last push) | Cutout rig / IK / facial states / GP | Reuse verdict |
|---|---|---|---|---|---|---|
| **COA Tools 2** (Aodaruma fork of ndee85's COA Tools) | Blender add-on: sprite import, auto mesh, bones, exporters (Godot etc.) | GPL-3.0 | README: tested on Blender 5.1, goal 3.4+; legacy-zip install; not verified on 5.2.2 | 2026-09-08 (original ndee85: 2024-05) | Bone-driven sprite meshes; slots/shape-key style variants; **no** GP, IK not documented | **Concepts only / optional human authoring aid.** GPL code must not be copied into our engine |
| **Tiny 2D Rig Tools** (NickTiny) | GP cut-out rig helper: basic human armature, auto IK with drivers, time-offset properties for mouth/hand drawing swaps, turn-around | **None** (GitHub reports no licence -> all rights reserved) | Written for GPv2 (2023); Blender 4.3+/5.x use GPv3, so almost certainly broken | 2023-07-13 | Best conceptual match (IK + drawing-swap facial states on GP) | **Do not copy code.** Concepts are free to reimplement (bone->IK, time-offset drawing swaps) |
| **Puppet Mode** | Not found as a distinct project. Nearest hits: *Puppet Studio* (commercial, Superhive/Gumroad, 3D humanoid auto-rig, no 2D/GP mention) and Flattiefolks' puppet controller | Proprietary / n/a | Puppet Studio lists Blender <= 5.1 | Puppet Studio 0.9.12 (2026-09) | 3D rigging, presets; not cutout/GP | **Not usable.** If you meant a specific repo, send the URL |
| **SPA 2D Animation Addon** (The SPA Studios) | Frame-by-frame Grease Pencil tooling: pegs, layer panel, onion skin, reference quads | GPL-3.0 (+ no-endorsement term) | **Needs SPA's custom Blender fork**; "won't work as expected in vanilla" | 2024-06-28 | No rigging, no IK, no cutout | **Skip.** Its "peg" idea (keyable 2D layer transforms) is now native GPv3 |
| **Proscenio** (firebound) | Photoshop -> Blender -> Godot cutout pipeline; slots, weighting, atlas; pydantic schemas -> JSON Schema | GPL-3.0-or-later (README; API says NOASSERTION) | Requires Blender 4.2+ | 2026-09-14 (solo, early stage) | Skeleton/slots authoring in Blender; Godot-specific output | **Architecture ideas only:** one versioned JSON contract as single source of truth, idempotent steps, format-not-tool coupling |
| **svg-character-animator** (molauu) | Agent skill: morph 2-10 SVG poses by matching `id`s, per-path strategy (exact/morph/fade), idle presets | **MIT** code; example art **CC BY-NC** | Not Blender (JS/React/SwiftUI) | 2026-08-19 | No bones; **facial/pose states by ID-matched path morph** | **Best legal reuse:** MIT algorithm can be reimplemented/ported with attribution. Do not use its artwork |
| triangletechguy/2D_animation | TypeScript "Hugging Face tech project" | **None** | n/a | 2026-08-05 | unclear | Unusable (no licence) |

## What stock Blender 5.2.2 already gives us (verified, `tools/verify_native_gp_rig.py`)
* IK constraint on a 2-bone chain follows its target exactly (wrist landed on (400,300,0) when targeted).
* **Grease Pencil layers can be parented to bones** (`layer.parent` + `layer.parent_bone`); in the renders the parented layers followed the IK chain
  (pose A ink bbox y 388-412 flat; pose B y 88-411 raised). Per-layer `translation/rotation/scale` exist natively (SPA's "pegs").
* `GREASE_PENCIL_TIME` (Time Offset) modifier for drawing swaps = facial states; `GREASE_PENCIL_ARMATURE` modifier for deformation.
Caveat: GPv3 layers do not have `parent_type` (setting `parent_bone` is enough); Blender's Python has no PIL.

## Recommendation: the smallest combination
**Install nothing.** Third-party add-ons are either GPL code we should not copy, unlicensed, stale on GPv3, fork-bound, or the wrong dimension.
1. **Blender core GPv3** for anything GP-drawn (bone-parented layers + IK + Time Offset/Armature modifiers) - already proven above.
2. **Our runtime rig (`rig2.py` + `rig_art.py`)** stays the production path (deterministic, no Blender in the render loop): rest-pose parts,
   2-bone IK, parametric brows/eyes/mouth, verbs library. It already implements the cutout architecture these tools automate.
3. **Adopt two designs, not code:**
   * *Proscenio's discipline* - a single versioned, schema-validated **RigSpec** (parts, rest poses, joints, IK chains, face parameters/states,
     actions) as the source of truth, consumed by both the Python runtime and a small Blender builder. (Our own pydantic/JSON-Schema file.)
   * *molauu's MIT idea* - ID-matched path morphing between SVG face poses, to enrich facial states beyond the parametric set (port ~150 lines, with attribution).
4. **Optional, outside the pipeline:** COA Tools 2 as a *human* authoring aid if we ever hand-rig a new hero sprite; only its exported result (our RigSpec) enters the repo.

Licence handling rule for the factory: every third-party asset/tool goes through `assets/licenses/registry.json`; GPL/unlicensed code is never vendored;
concepts are reimplemented; MIT/CC0 items are recorded with attribution.
