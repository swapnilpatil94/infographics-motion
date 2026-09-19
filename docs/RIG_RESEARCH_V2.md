# 2D skeleton rig systems — tested against Blender 5.2.2 LTS (not just read)

Machine: Apple Silicon, **Blender 5.2.2 LTS** (`/Applications/Blender.app`). Each candidate was cloned (to `/tmp`, NOT vendored into the repo), registered inside
`blender --background`, and its rig-creation operator was run. The probe scripts and raw output are reproducible: `docs/rig_probe/probe.py`, `probe2.py`.

| Candidate | Licence (in repo) | Registers in 5.2.2 | What actually ran | Verdict |
|---|---|---|---|---|
| **COA Tools 2** (Aodaruma/coa_tools2 v2.2.1, updated 2026-06) | **GPL-3** (`LICENSE`) | yes | `create_sprite_object` created a `SpriteObject` armature; 60+ operators (bind mesh to bones, `create_stretch_ik`, slots/`extract_slots`, keyframe/timeline events, JSON + Creature + DragonBones export). `create_ortho_cam` needs a 3D-view context (fails headless). | Most complete cut-out architecture (sprite = mesh bound to bone, slot = swappable sprite, stretch-IK). **GPL-3: reuse the ARCHITECTURE, never vendor the code into the core.** |
| **Tiny 2D Rig Tools** (NickTiny, v0.0.2, 2023) | **none** (no LICENSE file → all rights reserved) | yes (`bl_info` 3.3, still loads) | `tiny2drig.create_2d_armature` produced a 21-bone human (Master/Root/Lower/Upper/Neck + `L_Arm.Up/.Lw/.Hand`, `L_Leg.Up/.Lw/.Foot`, nudge bones). `initialize_rig` (IK + drivers) needs a GP object + a "Property Bone" chosen in the UI. | Good reference hierarchy and the driver-based 'time offset' idea for mouth/hand swaps. **No licence = unusable code.** |
| **Puppet Mode** (8bitbyadog, v0.2, 2026) | none stated in repo | yes | `puppet.create_puppet` built `Puppet_Rig`, **55 bones** (Root/Spine/Chest/Neck/Head/Eye_L,R/Eyebrow_L,R/Jaw/Shoulder/Arm_Upper/Arm_Lower/Hand…), but its **Grease Pencil layer set came out empty in 5.2** (README promises 87 layers → GPv3 API drift). | Best **facial-bone vocabulary** (eyes, eyebrows, jaw as bones). Half-working on 5.2; no licence. |
| **skeleton-rig** (frycz) | none | n/a — it is a **browser app** (JS/SVG) | read `example-skeleton.json`: `{bones:[{id,parent,position,rotation,length}]}`, separate picture JSON + motion JSON | Cleanest **data model** (skeleton / pictures / motion as three JSON files). No licence; not Blender. |

## Decision (smallest combination)
**Install nothing. Generate a stock-Blender rig ourselves**, taking only *concepts*:
* COA Tools 2 → sprites are meshes skinned to bones; swap-able sprite slots; IK chain on limbs.
* Puppet Mode → facial bones (eyes, eyebrows, mouth/jaw) under the head bone.
* Tiny 2D Rig Tools → human hierarchy with limb pairs + one control layer.
* skeleton-rig → skeleton as pure data, separate from art and motion (our `rig_def.py` / `parts_art.py` / `motion.py`).
Stock Blender 5.2.2 provides everything else: Armature + IK constraint (2-bone, locked X/Y, Z limits), Armature modifier with vertex groups, shape keys,
keyframes, EEVEE transparent renders. No add-on, no GPL code in the repo, no dependency that a Blender update can break.

## What our rig is (built by `engine/blender/skeleton_scene.py` from `engine/skeleton/rig_def.py`)
26 bones per character: ROOT > PELVIS > SPINE > CHEST > NECK > HEAD > (HAIR, EYE_L/R, BROW_L/R, MOUTH); CHEST > SHOULDER_L/R > ARM > FOREARM > HAND;
PELVIS > THIGH > SHIN > FOOT (L = far side, R = near side, facing +x, mirrored for facing -x). IK: 4 chains (2 arms, 2 legs) with joint limits.
