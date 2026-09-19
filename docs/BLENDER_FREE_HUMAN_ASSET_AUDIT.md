# Blender free human / stickman / Grease-Pencil rig audit

Scope: the 14 candidate groups requested before finalising the Character Factory. Every candidate that could be fetched **without signing in or submitting a form** was downloaded, hashed, opened in **Blender 5.2.2 LTS** and tested; the numbers below are generated from the committed measurements in [`docs/blender_audit/`](blender_audit/) by `tools/assets/make_audit_doc.py` (nothing in the tables is typed by hand). Assets are registered in `assets/registry/asset_registry.json` (SHA256, licence proof, policy decision).

**Our working custom rig was NOT replaced.** The V2 Short (`output/shorts/skeleton_factory_v2/final.mp4`) is unaffected by this audit.

## 1. Headline findings

1. **No free file gives us a modular 2D full-body character.** The best free 2D/GP material (Blender Studio cutout rigs) is either a bust/head (Pepe, Boy Head, Simple Head, Eye, Suzanno) or a one-off illustration (Cowboy). None has interchangeable wardrobe, two-segment limbs with IK, hand poses and a full face system. Our generated 26-bone rig + Open Peeps atoms stays the 2D foundation.
2. **The face decomposition we built is the same one the Blender Studio pros use** (Pepe: separate eyelid / pupil / eye / mouth / nose layers; Boy Head: Eyes / Eyebrow / Mouth / Nose as separate GP objects). Confirms the design; gives a reference for lattice head-turns and layer transforms. A live test drove the Boy Head pupil layers from a gaze vector in Blender 5.2.2 (`gp_boyhead_gaze_*.png`, ~1.5k pixels change per direction).
3. **MPFB2 + Rigify is the only candidate that is parametric, modular *and* fully IK-rigged with face controls** (macro sliders: 5 body variants 8.2-23.6 Blender-units tall; Rigify: 1090 bones, 94 face controls). Driven by *our* semantic walk -> reach -> hold script its foot and hand controls tracked the targets within **0.02 % / 0.01 % of hip height** (`candidate_integration_walk_reach.mp4`). It is a **3D** character: using it means a render-to-2D (toon/outline) backend - a separate decision, not a drop-in.
4. **Creomoto's Stick Man (CC0)** is a compact, clean IK stick rig (foot error 0.03 cm) - a good skeleton *reference*; it has no face/eyes/hands.
5. **Mike (CC0, Auto-Rig Pro) is the most complete file but is script-dependent**: 956 bones, 371 Python drivers and an embedded reset script that only work with Python auto-exec on. We open every third-party file with `--disable-autoexec`, so Mike's face shape keys/proportion controls did not respond (34 keys, 0 displacing vertices). Rejected as a foundation (weight + script dependence + non-deterministic risk).
6. **Blend Swap, Gumroad and Quaternius/itch are gated** (sign-in / e-mail checkout / lightbox). I did not create accounts or submit forms; they are listed as blocked with the reason. **"2D Stickman V4GP" could not be located anywhere** - I need its URL.
7. **Legacy GP files convert imperfectly to GPv3**: Boy Head (2.82-only) renders with stray blobs in 5.2.2; Cowboy, Suzanno, Simple Head and Eye convert cleanly.

## 2. Method and safety

- Download only; nothing executed. Every `.blend` is opened with `blender -b --disable-autoexec`; embedded text datablocks are counted, never run.
- `tools/assets/blender_audit_probe.py` - inventory (objects, armatures, bones, IK, constraints, drivers, shape keys, GP layers/strokes, actions, embedded scripts) + Workbench/EEVEE render.
- `tools/assets/blender_audit_tests.py` - behavioural tests on the evaluated depsgraph: IK response (25 cm target moves), synthetic **walk** (IK foot targets through stride/lift, tracking error), **seated 90/90** (thigh horizontal / shin vertical), **reach** (0.5 / 0.9 arm-lengths forward + up), **prop attach** (cube bone-parented to the hand follows the IK target), **face** (each shape key displaces vertices? eye-bone rotation moves the mesh?), **proportions** (leg/spine bone scale changes the evaluated mesh height), **pipeline mapping** (how many of our 26 bone roles exist by name). The file's own idle action supplies the base pose, then is removed so the test - not the file's animation - drives the rig.
- `tools/assets/rigify_ik_test.py` (Rigify controls), `tools/assets/candidate_drive.py` + `make_semantic_channels.py` + `candidate_compare.py` (**conversion test**: our motion grammar's foot/hand/hip channels retarget onto external IK controls), `tools/assets/gp_gaze_test.py` (GP pupil layers driven by a gaze vector), `tools/assets/mpfb_build.py` (MPFB used as an external generator; GPL code not copied).
- Licences are decided by `engine/licensing/policy.py` (CC0 accept; CC-BY accept-with-attribution; GPL **code** is quarantined and only ever run as an external tool; unknown/unverified = quarantine). Licence proofs are page-scraped and stored next to each download (`assets/raw/blender_audit/LICENSE_PROOF_*.txt`).
- Side effects on the machine: ~520 MB in `assets/raw/blender_audit/` (git-ignored; registry keeps URL + SHA256). MPFB is installed under the project-local `.blender_ext/` (git-ignored) via `BLENDER_USER_EXTENSIONS`; an earlier trial install into the user Blender profile was removed.

### Mapping of your 14 items to what was found

| # | requested | result |
|---|---|---|
| 1 | CC0 Stickman Characters with Basic Rig and Freestyle | Blend Swap #30507 (EMOPRODUCTION, CC0) - **blocked: sign-in required** |
| 2 | CC0 Stickman RIG 2 | closest match is Blend Swap #15217 "2D StickMan Rig v2" (LDev) which is **CC-BY, not CC0**, Blender-2.7x/Blender-Internal - **blocked: sign-in**; no CC0 "Stickman RIG 2" found |
| 3 | Creomoto Stick Man Fixed Up | **downloaded + tested** (OpenGameArt, CC0) |
| 4 | 2D Stickman V4GP | **not found** (searched Blend Swap, Gumroad, Blender Studio, OGA, web) |
| 5 | CC0 GP Spider Rig | Gumroad (dantti) - **blocked: e-mail checkout**; CC0 claim only from a search snippet -> quarantined |
| 6 | Blender Studio GP cutout-rig examples | **6 downloaded + tested** (Pepe, Cowboy, Boy Head, Suzanno, Simple Head, Eye); Pepe/Cowboy/Boy Head verified CC-BY on their Studio pages, the other three have no licence text on the archive page -> quarantined, inspection only |
| 7 | Blender Studio GP brushes/materials | **Brush Pack v2 downloaded + opened** (CC-BY) |
| 8 | MakeHuman | standalone app **not downloaded** (GUI desktop install); its bundled CC0 targets/rigs are inside MPFB, which was tested |
| 9 | MPFB2 | **downloaded (45 MB), installed, generated 5 humans + 4 rig variants** |
| 10 | CC0 rigged human Blender files | Mike, Old Lady, Low-Poly Rigged Man, Puppet Base, Human Base Meshes (unrigged) - all **downloaded + tested** |
| 11 | CC0 humanoid rigs | Mike (ARP), MPFB outputs (CC0), Rigify (built into Blender, GPL tool) - tested |
| 12 | free GP human rigs | Pepe, Boy Head tested; Yadoob GP rigs **blocked** (Gumroad, no licence stated) |
| 13 | free 2D cutout human rigs | Pepe (cartoon human as 15 layers incl. body and arms, drawn as head + shoulders in the file) tested |
| 14 | free CC0 skeletal/armature systems | Rigify + MPFB rig library (default / default_no_toes / game_engine / Rigify) + Creomoto - tested |

Also blocked: Quaternius Universal Base Characters (CC0; itch/Patreon gate; the `.blend` source version is paid).

## 3. Candidate cards (downloaded, opened, tested)

### Creomoto's Stick Man (Fixed Up)

- **Source / URL:** OpenGameArt - https://opengameart.org/content/creomotos-stick-man-fixed-up
- **Download URL:** https://opengameart.org/sites/default/files/StickMan_0.blend  |  **SHA256:** `2965a6b4490ce8d4...`  |  **file:** `assets/raw/blender_audit/oga_stickman_fixed.blend`
- **Author:** Creomoto (original) / mrpoly (rig fix, 2015-03-09)  |  **Licence:** CC0-1.0 (ACCEPT)  |  **proof:** `assets/raw/blender_audit/LICENSE_PROOF_oga_creomoto_stickman.txt`
- **Commercial use:** yes  |  **Modification:** yes  |  **Attribution required:** no  |  **Share-alike:** no
- **File format / Blender version:** .blend, authored in Blender 2.71.0; opened in Blender 5.2.2 LTS
- **Rig structure:** 1 armature(s); main = `Armature`, 27 bones (27 deform), max chain depth 7, roots ['LegIK_L', 'Master', 'LegIK_R', 'ArmIK_R']
- **IK:** 8 IK constraint(s) [('Thigh_L', 1), ('Shin_L', 2), ('Thigh_R', 1), ('Shin_R', 2), ('Arm_R', 1), ('Hand_R', 2), ('Arm_L', 1), ('Hand_L', 2)]; other constraints {'IK': 8}
- **Face:** 0 face bones (brows 0, mouth/jaw 0); shape keys 0
- **Eyes:** eye bones none  |  **Hands:** 0 finger bones
- **Drivers:** 0 (0 scripted) - scripted drivers/embedded scripts do NOT run under `--disable-autoexec`: []
- **Animation:** 2 action(s) [('SitckMan_Idle', [1, 111]), ('StickMan_Run', [1, 20])]
- **Grease Pencil:** no; 0 GP object(s), 0 layers, 0 strokes; render in 5.2.2: yes
- **Turnaround:** any angle (3D mesh)  |  **Modularity:** single mesh, 206 tris; body parts not separable
- **Usage decision:** E: stickman/skeleton REFERENCE. Blender 2.71 file: 27 bones, 8 IK constraints (leg+arm IK targets, knee/elbow pole helper targets), idle+run actions. Driven by our semantic channels in output/tests/candidate_integration_walk_reach.mp4. No face/eyes/hands.
- **Measured (Blender 5.2.2, `blender_audit_tests.py`, base pose = `SitckMan_Idle`):** walk-by-IK yes (foot tracking error max 0.03 cm, stride 0.684 m, lift 0.187 m); seated 90/90 yes; reach 0.5-0.9 L yes; prop-on-hand follows yes; eye rotation moves mesh no; shape keys 0 (0 displace vertices); bone-scale changes body yes (42.1 %); bones mappable to our 26-bone roles 14/23

### Low-Poly Rigged Man (blockfigureRigged6)

- **Source / URL:** OpenGameArt - https://opengameart.org/content/low-poly-rigged-man
- **Download URL:** https://opengameart.org/sites/default/files/blockfigureRigged6.blend  |  **SHA256:** `d2ae9ab97de11972...`  |  **file:** `assets/raw/blender_audit/oga_lowpoly_rigged_man.blend`
- **Author:** infernaltoast  |  **Licence:** CC0-1.0 (ACCEPT)  |  **proof:** `assets/raw/blender_audit/LICENSE_PROOF_oga_lowpoly_rigged_man.txt`
- **Commercial use:** yes  |  **Modification:** yes  |  **Attribution required:** no  |  **Share-alike:** no
- **File format / Blender version:** .blend, authored in Blender 2.67.0; opened in Blender 5.2.2 LTS
- **Rig structure:** 1 armature(s); main = `Armature`, 19 bones (11 deform), max chain depth 2, roots ['Torso', 'UpperArm.L', 'UpperLeg.L', 'UpperArm.R']
- **IK:** 4 IK constraint(s) [('LowerArm.L', 4), ('LowerLeg.L', 2), ('LowerArm.R', 2), ('LowerLeg.R', 4)]; other constraints {'IK': 4}
- **Face:** 0 face bones (brows 0, mouth/jaw 0); shape keys 0
- **Eyes:** eye bones none  |  **Hands:** 0 finger bones
- **Drivers:** 0 (0 scripted) - scripted drivers/embedded scripts do NOT run under `--disable-autoexec`: ['Text', 'Text.001']
- **Animation:** 2 action(s) [('ArmatureAction', [1, 10]), ('stand', [1, 8])]
- **Grease Pencil:** no; 0 GP object(s), 0 layers, 0 strokes; render in 5.2.2: yes
- **Turnaround:** any angle (3D)  |  **Modularity:** 4 meshes (body, helmet, spear...), one skinned
- **Usage decision:** Tested: 19 bones, 4 IK, blocky low-poly; leg IK tracking error 6 cm in the synthetic walk (fails our <1 cm gate). Not adopted.
- **Measured (Blender 5.2.2, `blender_audit_tests.py`, base pose = `ArmatureAction`):** walk-by-IK no (foot tracking error max 6.11 cm, stride 0.556 m, lift 0.156 m); seated 90/90 yes; reach 0.5-0.9 L yes; prop-on-hand follows yes; eye rotation moves mesh no; shape keys 0 (0 displace vertices); bone-scale changes body yes (9.0 %); bones mappable to our 26-bone roles 15/23

### Old Lady (rigged, sitting)

- **Source / URL:** OpenGameArt - https://opengameart.org/content/old-lady
- **Download URL:** https://opengameart.org/sites/default/files/oldlady-v2.blend  |  **SHA256:** `02e6acd66a07cdc1...`  |  **file:** `assets/raw/blender_audit/oga_old_lady.blend`
- **Author:** CDmir (with TinyWorlds)  |  **Licence:** CC0-1.0 (ACCEPT)  |  **proof:** `assets/raw/blender_audit/LICENSE_PROOF_oga_old_lady.txt`
- **Commercial use:** yes  |  **Modification:** yes  |  **Attribution required:** no  |  **Share-alike:** no
- **File format / Blender version:** .blend, authored in Blender 2.76.0; opened in Blender 5.2.2 LTS
- **Rig structure:** 1 armature(s); main = `Armature`, 84 bones (67 deform), max chain depth 11, roots ['Root']
- **IK:** 8 IK constraint(s) [('shin.L', 2), ('shin.R', 2), ('chest', 2), ('forearm.R', 2), ('forearm.L', 2), ('neck', 1), ('head_L', 1), ('head_R', 1)]; other constraints {'IK': 8, 'COPY_ROTATION': 27, 'TRACK_TO': 6}
- **Face:** 18 face bones (brows 4, mouth/jaw 2); shape keys 0
- **Eyes:** eye bones ['eye.R', 'eye.L', 'Target_Eye_R', 'Target_Eye_L']  |  **Hands:** 30 finger bones
- **Drivers:** 0 (0 scripted) - scripted drivers/embedded scripts do NOT run under `--disable-autoexec`: ['Text']
- **Animation:** 1 action(s) [('Sitting', [0, 2051])]
- **Grease Pencil:** no; 0 GP object(s), 0 layers, 0 strokes; render in 5.2.2: yes
- **Turnaround:** any angle (3D)  |  **Modularity:** 15 meshes, 2 skinned; dress/hair sculpted into the mesh
- **Usage decision:** Tested: 84 bones incl. 30 finger + eye/brow bones, 8 IK; legs+forearms IK pass, no shape keys, fixed sculpted dress/hair (not modular). Reference for a face/hand bone layout only.
- **Measured (Blender 5.2.2, `blender_audit_tests.py`, base pose = `Sitting`):** walk-by-IK yes (foot tracking error max 0.81 cm, stride 36.67 m, lift 10.004 m); seated 90/90 yes; reach 0.5-0.9 L yes; prop-on-hand follows yes; eye rotation moves mesh no; shape keys 0 (0 displace vertices); bone-scale changes body yes (5.5 %); bones mappable to our 26-bone roles 22/23

### Puppet Base [Rigged]

- **Source / URL:** OpenGameArt - https://opengameart.org/content/puppet-base-rigged
- **Download URL:** https://opengameart.org/sites/default/files/baseRelease.7z  |  **SHA256:** `d47296afb8804d48...`  |  **file:** `assets/raw/blender_audit/oga_puppet_base.7z`
- **Author:** practicing01  |  **Licence:** CC0-1.0 (ACCEPT)  |  **proof:** `assets/raw/blender_audit/LICENSE_PROOF_oga_puppet_base.txt`
- **Commercial use:** yes  |  **Modification:** yes  |  **Attribution required:** no  |  **Share-alike:** no
- **File format / Blender version:** .blend, authored in Blender 2.76.0; opened in Blender 5.2.2 LTS
- **Rig structure:** 1 armature(s); main = `Armature`, 26 bones (26 deform), max chain depth 8, roots ['root']
- **IK:** 0 IK constraint(s) []; other constraints {}
- **Face:** 2 face bones (brows 0, mouth/jaw 0); shape keys 0
- **Eyes:** eye bones ['eye.r', 'eye.l']  |  **Hands:** 0 finger bones
- **Drivers:** 0 (0 scripted) - scripted drivers/embedded scripts do NOT run under `--disable-autoexec`: []
- **Animation:** 0 action(s) []
- **Grease Pencil:** no; 0 GP object(s), 0 layers, 0 strokes; render in 5.2.2: yes
- **Turnaround:** any angle (3D)  |  **Modularity:** one mesh
- **Usage decision:** Tested: 26 bones, eye bones move the mesh, no IK/actions. Structural reference only.
- **Measured (Blender 5.2.2, `blender_audit_tests.py`, base pose = `None`):** walk-by-IK no (foot tracking error max None cm, stride None m, lift None m); seated 90/90 no; reach 0.5-0.9 L no; prop-on-hand follows yes; eye rotation moves mesh yes; shape keys 0 (0 displace vertices); bone-scale changes body yes (82.8 %); bones mappable to our 26-bone roles 13/23

### Mike (Auto-Rig Pro character)

- **Source / URL:** Artell (lucky3d.fr) via BlenderNation - https://www.blendernation.com/2019/02/13/free-download-mike-fully-rigged-character-cc-0/
- **Download URL:** http://lucky3d.fr/auto-rig-pro/mike.zip  |  **SHA256:** `4e56244e9f2baf8e...`  |  **file:** `assets/raw/blender_audit/mike_rig.zip`
- **Author:** Artell (Lucas)  |  **Licence:** CC0-1.0 (ACCEPT)  |  **proof:** `assets/raw/blender_audit/LICENSE_PROOF_artell_mike.txt`
- **Commercial use:** yes  |  **Modification:** yes  |  **Attribution required:** no  |  **Share-alike:** no
- **File format / Blender version:** .blend, authored in Blender 5.2.44; opened in Blender 5.2.2 LTS
- **Rig structure:** 1 armature(s); main = `mike_rig`, 956 bones (171 deform), max chain depth 17, roots ['Picker', 'c_pos', 'c_eye_target.x', 'c_arms_pole.l']
- **IK:** 11 IK constraint(s) [('root.x', 1), ('leg_ik.l', 2), ('leg_ik_nostr.l', 2), ('leg_ik.r', 2), ('leg_ik_nostr.r', 2), ('forearm_ik.r', 2), ('forearm_ik_nostr.r', 2), ('forearm_ik.l', 2)]; other constraints {'LIMIT_LOCATION': 117, 'COPY_SCALE': 80, 'IK': 11, 'COPY_ROTATION': 135, 'COPY_LOCATION': 130, 'DAMPED_TRACK': 51, 'STRETCH_TO': 32, 'COPY_TRANSFORMS': 33, 'ACTION': 40, 'LOCKED_TRACK': 4, 'CHILD_OF': 15, 'LIMIT_ROTATION': 12, 'TRANSFORM': 12, 'TRACK_TO': 4}
- **Face:** 249 face bones (brows 30, mouth/jaw 108); shape keys 34
- **Eyes:** eye bones ['c_eye_proxy.r', 'c_eye_ref_proxy.r', 'c_eyelid_top_proxy.r', 'c_eye_proxy.l']  |  **Hands:** 196 finger bones
- **Drivers:** 371 (371 scripted) - scripted drivers/embedded scripts do NOT run under `--disable-autoexec`: ['reset_2.2.py', 'Text']
- **Animation:** 4 action(s) [('Mike_Crouch', [2, 2]), ('Mike_Run', [1, 1]), ('rig_fist', [0, 10]), ('walk', [101, 125])]
- **Grease Pencil:** no; 0 GP object(s), 0 layers, 0 strokes; render in 5.2.2: yes
- **Turnaround:** any angle (3D)  |  **Modularity:** 229 meshes (body, clothes, hair, props as separate objects) but tied to drivers/scripts
- **Usage decision:** C candidate: 956 bones, 196 finger + 249 face bones, 34 shape keys, 11 IK - BUT 371 Python drivers + an embedded reset script that need script auto-exec (we open with --disable-autoexec). Legs IK/hold pass; face/proportion tests inconclusive without drivers. Too heavy for a lightweight deterministic factory.
- **Measured (Blender 5.2.2, `blender_audit_tests.py`, base pose = `Mike_Crouch`):** walk-by-IK yes (foot tracking error max 0.01 cm, stride 0.426 m, lift 0.116 m); seated 90/90 yes; reach 0.5-0.9 L yes; prop-on-hand follows yes; eye rotation moves mesh no; shape keys 34 (0 displace vertices); bone-scale changes body no (3.7 %); bones mappable to our 26-bone roles 21/23

### Blender Human Base Meshes v1.4.1

- **Source / URL:** Blender Foundation / Blender Studio - https://www.blender.org/download/demo-files/
- **Download URL:** https://download.blender.org/demo/asset-bundles/human-base-meshes/human-base-meshes-bundle-v1.4.1.zip  |  **SHA256:** `811f43accbb31a88...`  |  **file:** `assets/raw/blender_audit/human_base_meshes_v1.4.1.zip`
- **Author:** Blender Studio + community  |  **Licence:** CC0-1.0 (ACCEPT)  |  **proof:** `assets/raw/blender_audit/LICENSE_PROOF_blender_human_base_meshes.txt`
- **Commercial use:** yes  |  **Modification:** yes  |  **Attribution required:** no  |  **Share-alike:** no
- **File format / Blender version:** .blend, authored in Blender 4.2.67; opened in Blender 5.2.2 LTS
- **Rig structure:** no armature
- **IK / face / eyes / hands:** none as bones
- **Animation:** 0 action(s) []
- **Grease Pencil:** no; 0 GP object(s), 0 layers, 0 strokes; render in 5.2.2: yes
- **Turnaround:** any angle (3D)  |  **Modularity:** 17 base meshes + body parts (hands, feet, heads, eyes), UN-rigged
- **Usage decision:** C support: 17 UN-rigged sculpting meshes (382 mesh objects, 150k tris) CC0. Rigging it ourselves = the MPFB path anyway; not adopted alone.

### MPFB 2.0.17 + generated humans (default / game_engine / Rigify rigs)

- **Source / URL:** generated locally with MPFB 2.0.17 in Blender 5.2.2 - https://static.makehumancommunity.org/about/license.html
- **Download URL:** n/a (generated: tools/assets/mpfb_build.py)  |  **SHA256:** `aba05c81090d4927...`  |  **file:** `assets/raw/blender_audit/mpfb_out/mpfb_rigify.blend`
- **Author:** MakeHuman Community targets/assets  |  **Licence:** CC0-1.0 (ACCEPT)  |  **proof:** `assets/raw/blender_audit/LICENSE_PROOF_mpfb2_output.txt`
- **Commercial use:** yes  |  **Modification:** yes  |  **Attribution required:** no  |  **Share-alike:** no
- **File format / Blender version:** .blend, authored in Blender 5.2.45; opened in Blender 5.2.2 LTS
- **Rig structure:** 2 armature(s); main = `Human.rigify`, 930 bones (181 deform), max chain depth 23, roots ['DEF-elbow-helper.L', 'DEF-elbow-helper.R', 'DEF-knee-helper.L', 'DEF-knee-helper.R']
- **IK:** 8 IK constraint(s) [('MCH-shin_ik.L', 2), ('MCH-shin_ik.L', 2), ('MCH-shin_ik.R', 2), ('MCH-shin_ik.R', 2), ('MCH-forearm_ik.L', 2), ('MCH-forearm_ik.L', 2), ('MCH-forearm_ik.R', 2), ('MCH-forearm_ik.R', 2)]; other constraints {'ARMATURE': 19, 'TRANSFORM': 18, 'COPY_TRANSFORMS': 409, 'STRETCH_TO': 146, 'COPY_LOCATION': 314, 'COPY_SCALE': 58, 'DAMPED_TRACK': 132, 'COPY_ROTATION': 28, 'IK': 8, 'LIMIT_ROTATION': 124, 'LOCKED_TRACK': 20, 'LIMIT_DISTANCE': 20}
- **Face:** 401 face bones (brows 86, mouth/jaw 98); shape keys 5
- **Eyes:** eye bones ['eye_master.L', 'ORG-eye.L', 'DEF-eye_master.L', 'MCH-eye.L']  |  **Hands:** 172 finger bones
- **Drivers:** 152 (110 scripted) - scripted drivers/embedded scripts do NOT run under `--disable-autoexec`: ['Human.rigify_ui.py']
- **Animation:** 0 action(s) []
- **Grease Pencil:** no; 0 GP object(s), 0 layers, 0 strokes; render in 5.2.2: yes
- **Turnaround:** any angle (3D)  |  **Modularity:** 8 macro sliders (gender, age, muscle, weight, proportions, height, cup, firmness) + race blend + 1445 target files; clothes/hair = MakeHuman asset packs (not downloaded)
- **Usage decision:** C: 3D human foundation candidate (parametric proportions via macro details, 5 rig options incl. Rigify 1090 bones). Driven by our semantic channels: 0.02 % of hip height IK error. Not yet the production path.
- **Measured (Blender 5.2.2, `blender_audit_tests.py`, base pose = `None`):** walk-by-IK no (foot tracking error max 0.0 cm, stride 0.0 m, lift 0.0 m); seated 90/90 no; reach 0.5-0.9 L yes; prop-on-hand follows no; eye rotation moves mesh no; shape keys 4 (3 displace vertices); bone-scale changes body no (0.0 %); bones mappable to our 26-bone roles 23/23

### (Cutout-Rig) Pepe

- **Source / URL:** Blender Studio - Grease Pencil Fundamentals - https://studio.blender.org/training/grease-pencil-fundamentals/5cba1d2e53491006f35d95d0/
- **Download URL:** https://studio.blender.org/download-source/files/a9/a9e64c4c1c654e0dabc3fbaeaee85fb5/a9e64c4c1c654e0dabc3fbaeaee85fb5.blend  |  **SHA256:** `c0ff650b7f348e91...`  |  **file:** `assets/raw/blender_audit/gp_pepe_cutout.blend`
- **Author:** Daniel Martinez Lara (Pepeland) / Blender Studio  |  **Licence:** CC-BY-4.0 (ACCEPT_WITH_OBLIGATIONS)  |  **proof:** `assets/raw/blender_audit/LICENSE_PROOF_blenderstudio_gp_cutout_pepe_v1.txt`
- **Commercial use:** yes  |  **Modification:** yes  |  **Attribution required:** yes  |  **Share-alike:** no
- **File format / Blender version:** .blend, authored in Blender 2.83.15; opened in Blender 5.2.2 LTS
- **Rig structure:** 1 armature(s); main = `Armature`, 22 bones (22 deform), max chain depth 3, roots ['head', 'Bone.002', 'body', 'body.001']
- **IK:** 0 IK constraint(s) []; other constraints {'STRETCH_TO': 4}
- **Face:** 10 face bones (brows 0, mouth/jaw 2); shape keys 0
- **Eyes:** eye bones ['DEF_eye.L.001', 'eye.L', 'pupil.L', 'DEF_eye.R.001']  |  **Hands:** 0 finger bones
- **Drivers:** 0 (0 scripted) - scripted drivers/embedded scripts do NOT run under `--disable-autoexec`: []
- **Animation:** 2 action(s) [('ArmatureAction', [-11, 97]), ('Camera.001Action', [0, 0])]
- **Grease Pencil:** yes (GPv2 -> v3 auto-converted); 1 GP object(s), 15 layers, 349 strokes; render in 5.2.2: yes
- **Turnaround:** front only (flat cutout)  |  **Modularity:** ONE GP object, 15 layers: bg, body, armL/R, earL/R, head, eyeL/R, pupilL/R, eyelidL/R, mouth, nose
- **Usage decision:** B/D: Grease Pencil cutout technical reference (separate GP objects/layers per face part, hooks/lattices, pupil layers). Opens in Blender 5.2.2 via automatic GPv2->GPv3 conversion; gaze test: output/tests/blender_audit/gp_boyhead_gaze_*.png. CC-BY: attribution required if any art is reused; nothing is vendored into the engine.
- **Measured (Blender 5.2.2, `blender_audit_tests.py`, base pose = `ArmatureAction`):** walk-by-IK no (foot tracking error max None cm, stride None m, lift None m); seated 90/90 no; reach 0.5-0.9 L no; prop-on-hand follows no; eye rotation moves mesh no; shape keys 0 (0 displace vertices); bone-scale changes body no (0.0 %); bones mappable to our 26-bone roles 6/23

### (Cutout-Rig) Cowboy

- **Source / URL:** Blender Studio - Grease Pencil Fundamentals - https://studio.blender.org/training/grease-pencil-fundamentals/5d9c6ee20f9018baaca071c3/
- **Download URL:** https://studio.blender.org/download-source/files/11/119c054515814654afdd498964a57879/119c054515814654afdd498964a57879.blend  |  **SHA256:** `7f94cadbad4e4026...`  |  **file:** `assets/raw/blender_audit/gp_cowboy_cutout.blend`
- **Author:** Maisam Hosaini / Blender Studio  |  **Licence:** CC-BY-4.0 (ACCEPT_WITH_OBLIGATIONS)  |  **proof:** `assets/raw/blender_audit/LICENSE_PROOF_blenderstudio_gp_cutout_cowboy_v1.txt`
- **Commercial use:** yes  |  **Modification:** yes  |  **Attribution required:** yes  |  **Share-alike:** no
- **File format / Blender version:** .blend, authored in Blender 2.83.15; opened in Blender 5.2.2 LTS
- **Rig structure:** 6 armature(s); main = `Armature.001`, 10 bones (10 deform), max chain depth 9, roots ['Bone']
- **IK:** 1 IK constraint(s) [('Bone.001', 0)]; other constraints {'LIMIT_ROTATION': 5, 'IK': 1}
- **Face:** 0 face bones (brows 0, mouth/jaw 0); shape keys 0
- **Eyes:** eye bones none  |  **Hands:** 0 finger bones
- **Drivers:** 0 (0 scripted) - scripted drivers/embedded scripts do NOT run under `--disable-autoexec`: ['Text']
- **Animation:** 0 action(s) []
- **Grease Pencil:** yes; 40 GP object(s), 139 layers, 4152 strokes; render in 5.2.2: yes
- **Turnaround:** side (illustrated horse rider)  |  **Modularity:** 40 GP objects, 6 armatures, hooks + lattice + armature modifiers
- **Usage decision:** B/D: Grease Pencil cutout technical reference (separate GP objects/layers per face part, hooks/lattices, pupil layers). Opens in Blender 5.2.2 via automatic GPv2->GPv3 conversion; gaze test: output/tests/blender_audit/gp_boyhead_gaze_*.png. CC-BY: attribution required if any art is reused; nothing is vendored into the engine.

### (Cutout-Rig) Boy Head Test (2.82)

- **Source / URL:** Blender Studio - Grease Pencil Fundamentals - https://studio.blender.org/training/grease-pencil-fundamentals/5d9c6fbd2ed9a72b3fae65b0/
- **Download URL:** https://studio.blender.org/download-source/files/a6/a6ee4be7a0e5405e813ebdc6e4129568/a6ee4be7a0e5405e813ebdc6e4129568.blend  |  **SHA256:** `888a127817854ad0...`  |  **file:** `assets/raw/blender_audit/gp_boyhead_cutout_282.blend`
- **Author:** Maisam Hosaini / Blender Studio  |  **Licence:** CC-BY-4.0 (ACCEPT_WITH_OBLIGATIONS)  |  **proof:** `assets/raw/blender_audit/LICENSE_PROOF_blenderstudio_gp_cutout_boyhead282_v1.txt`
- **Commercial use:** yes  |  **Modification:** yes  |  **Attribution required:** yes  |  **Share-alike:** no
- **File format / Blender version:** .blend, authored in Blender 2.81.14; opened in Blender 5.2.2 LTS
- **Rig structure:** no armature (GP layers/objects + lattice/hook/empties instead)
- **IK / face / eyes / hands:** none as bones
- **Animation:** 2 action(s) [('Head Left and Right ControllerAction', [1, 135]), ('Head Up and Down ControllerAction', [1, 135])]
- **Grease Pencil:** yes (2.82-only file: parts of the conversion break in 5.2.2); 6 GP object(s), 24 layers, 2018 strokes; render in 5.2.2: yes
- **Turnaround:** front (lattice head-turn)  |  **Modularity:** 6 GP objects: Body, Head, Eyes, Eyebrow, Nose, Mouth (face parts are separate objects; pupils are layers 'Left'/'Right')
- **Usage decision:** B/D: Grease Pencil cutout technical reference (separate GP objects/layers per face part, hooks/lattices, pupil layers). Opens in Blender 5.2.2 via automatic GPv2->GPv3 conversion; gaze test: output/tests/blender_audit/gp_boyhead_gaze_*.png. CC-BY: attribution required if any art is reused; nothing is vendored into the engine.

### (Cutout-Rig) Suzanno cutout test

- **Source / URL:** Blender Institute Archive (grease-pencil-samples) - https://download.blender.org/archive/gallery/grease-pencil-samples/cutout-rig-suzanno-cutout-test-by-francisco-antonio-peinado-currobot-for-2-83-or-above/
- **Download URL:** https://download.blender.org/demo-files/archives/art-gallery/grease-pencil-samples/grease-pencil-blender-free-samples/cutout-rig-suzanno-cutout-test-by-francisco-antonio-peinado-currobot-for-2-83-or-above/cutout-rig-suzanno-by-francisco-antonio-peinado-currobot-49d7d95171da4b11a26e8e56ac73d559.blend  |  **SHA256:** `6e64eaa60c9a6e14...`  |  **file:** `assets/raw/blender_audit/gp_suzanno_cutout.blend`
- **Author:** Francisco Antonio Peinado (Currobot)  |  **Licence:** None (QUARANTINE)  |  **proof:** `None`
- **Commercial use:** no  |  **Modification:** yes  |  **Attribution required:** no  |  **Share-alike:** no
- **File format / Blender version:** .blend, authored in Blender 2.83.15; opened in Blender 5.2.2 LTS
- **Rig structure:** no armature (GP layers/objects + lattice/hook/empties instead)
- **IK / face / eyes / hands:** none as bones
- **Animation:** 3 action(s) [('EmptyAction', [1, 38]), ('GPencilAction', [1, 55]), ('LatticeAction', [10, 10])]
- **Grease Pencil:** yes; 1 GP object(s), 4 layers, 1576 strokes; render in 5.2.2: yes
- **Turnaround:** front  |  **Modularity:** 1 GP object, 4 layers + lattice
- **Usage decision:** Downloaded for INSPECTION ONLY: the archive page states no licence, so the file is quarantined and not used. (Probe: output/tests/blender_audit/gp_cutout_suzanno.json)

### (Cutout-Rig) Simple Head

- **Source / URL:** Blender Institute Archive (grease-pencil-samples) - https://download.blender.org/archive/gallery/grease-pencil-samples/cutout-rig-simple-head-by-maisam-hosaini-for-2-83-or-above/
- **Download URL:** https://download.blender.org/demo-files/archives/art-gallery/grease-pencil-samples/grease-pencil-blender-free-samples/cutout-rig-simple-head-by-maisam-hosaini-for-2-83-or-above/cutout-rig-simple-head-by-maisam-hosaini-f220e2ef0c254e54b6da628fa784013b.blend  |  **SHA256:** `7435c2b88cda5070...`  |  **file:** `assets/raw/blender_audit/gp_simplehead_cutout.blend`
- **Author:** Maisam Hosaini  |  **Licence:** None (QUARANTINE)  |  **proof:** `None`
- **Commercial use:** no  |  **Modification:** yes  |  **Attribution required:** no  |  **Share-alike:** no
- **File format / Blender version:** .blend, authored in Blender 2.83.15; opened in Blender 5.2.2 LTS
- **Rig structure:** no armature (GP layers/objects + lattice/hook/empties instead)
- **IK / face / eyes / hands:** none as bones
- **Animation:** 1 action(s) [('Head ControllerAction', [11, 196])]
- **Grease Pencil:** yes; 1 GP object(s), 16 layers, 39 strokes; render in 5.2.2: yes
- **Turnaround:** front  |  **Modularity:** 1 GP object, 16 layers, 16 empties
- **Usage decision:** Downloaded for INSPECTION ONLY: the archive page states no licence, so the file is quarantined and not used. (Probe: output/tests/blender_audit/gp_cutout_simplehead.json)

### (Cutout-Rig) Eye (2.82)

- **Source / URL:** Blender Institute Archive (grease-pencil-samples) - https://download.blender.org/archive/gallery/grease-pencil-samples/cutout-rig-eye-by-jefferson-nascimento-only-for-2-82/
- **Download URL:** https://download.blender.org/demo-files/archives/art-gallery/grease-pencil-samples/grease-pencil-blender-free-samples/cutout-rig-eye-by-jefferson-nascimento-only-for-2-82/cutout-rig-eye-by-jefferson-nascimento-e4087d677ddb4328ab5d57984ab6004f.blend  |  **SHA256:** `92f5d170678552ea...`  |  **file:** `assets/raw/blender_audit/gp_eye_cutout_282.blend`
- **Author:** Jefferson Nascimento  |  **Licence:** None (QUARANTINE)  |  **proof:** `None`
- **Commercial use:** no  |  **Modification:** yes  |  **Attribution required:** no  |  **Share-alike:** no
- **File format / Blender version:** .blend, authored in Blender 2.80.75; opened in Blender 5.2.2 LTS
- **Rig structure:** 1 armature(s); main = `eyeArmature`, 22 bones (13 deform), max chain depth 1, roots ['ctrl_upperLid.L', 'PALPsUP2', 'PALPsUP1', 'ctrl_bottonLid.R']
- **IK:** 0 IK constraint(s) []; other constraints {'COPY_LOCATION': 8, 'STRETCH_TO': 6, 'TRACK_TO': 1}
- **Face:** 8 face bones (brows 0, mouth/jaw 0); shape keys 0
- **Eyes:** eye bones ['iris', 'pupil']  |  **Hands:** 0 finger bones
- **Drivers:** 6 (6 scripted) - scripted drivers/embedded scripts do NOT run under `--disable-autoexec`: ['Considerations']
- **Animation:** 1 action(s) [('eyeArmatureAction', [21, 131])]
- **Grease Pencil:** yes; 1 GP object(s), 13 layers, 62 strokes; render in 5.2.2: yes
- **Turnaround:** front  |  **Modularity:** 1 GP object, 13 layers, 22-bone armature
- **Usage decision:** Downloaded for INSPECTION ONLY: the archive page states no licence, so the file is quarantined and not used. (Probe: output/tests/blender_audit/gp_cutout_eye282.json)

### GP Brush Pack v2

- **Source / URL:** Blender Studio - Grease Pencil Fundamentals - https://studio.blender.org/training/grease-pencil-fundamentals/5f235cc297f8815e74ffb90b/
- **Download URL:** https://studio.blender.org/download-source/files/1f/1fc0d9422d724dd680f3240b07fb8017/1fc0d9422d724dd680f3240b07fb8017.zip  |  **SHA256:** `f4509fa3172f3dde...`  |  **file:** `assets/raw/blender_audit/gp_brush_pack_v2.zip`
- **Author:** Daniel Martinez Lara (Pepeland) / Blender Studio  |  **Licence:** CC-BY-4.0 (ACCEPT_WITH_OBLIGATIONS)  |  **proof:** `assets/raw/blender_audit/LICENSE_PROOF_blenderstudio_gp_brush_pack_v2.txt`
- **Commercial use:** yes  |  **Modification:** yes  |  **Attribution required:** yes  |  **Share-alike:** no
- **File format / Blender version:** .blend, authored in Blender 2.91.1; opened in Blender 5.2.2 LTS
- **Rig structure:** no armature (GP layers/objects + lattice/hook/empties instead)
- **IK / face / eyes / hands:** none as bones
- **Animation:** 2 action(s) [('StrokeAction', [1, 302]), ('StrokeAction.001', [1, 302])]
- **Grease Pencil:** yes; 2 GP object(s), 8 layers, 1155 strokes; render in 5.2.2: yes
- **Turnaround:** n/a  |  **Modularity:** brush/material library
- **Usage decision:** D: GP brush/material reference (the pack loads in Blender 5.2.2 as an asset .blend). Not used by the deterministic compositor.

## 4. Candidates that could NOT be downloaded (nothing was signed in to, no checkout form submitted)

| candidate | source URL | licence claimed | author | status | why |
|---|---|---|---|---|---|
| Stickman Characters with Basic rig and Freestyle | https://blendswap.com/blend/30507 | CC0-1.0 | EMOPRODUCTION | BLOCKED_LOGIN | Blend Swap requires signing in to download; account creation/sign-in is not something the agent does. CC0 per the page (author EMOPRODUCTION, 560 KB, Blender 3.0x). User can drop the .blend into assets/raw/blender_audit/ to have it audited. |
| 2D StickMan Rig v2 | https://blendswap.com/blend/15217 | CC-BY-4.0 | LDev | BLOCKED_LOGIN | Blend Swap sign-in required. CC-BY (LDev), Blender 2.7x Blender-Internal file (137 KB) - would need conversion anyway. |
| 2D Stickman V4GP | None | unverified | None | NOT_FOUND | Searched Blend Swap / Gumroad / Blender Studio / OpenGameArt / general web: no asset named '2D Stickman V4GP' could be located. Ask the user for the URL. |
| GP Spider Rig | https://dantti.gumroad.com/l/gp_spider_rig | unverified | dantti | BLOCKED_CHECKOUT | Gumroad free download needs an e-mail checkout form (personal data); not submitted. Licence claim (CC0) comes from a search snippet only -> unverified -> quarantined. |
| Grease Pencil Character Rigs (man, child, anime girl) | https://gumroad.com/l/zGJZB | unverified | Yadoob | BLOCKED_CHECKOUT | Gumroad checkout required and the BlenderNation article states no licence -> unknown -> quarantined. |
| Super Stickman Game-ready rig | https://ahmadanimation.gumroad.com/l/xptxd | unverified | Ahmad Animation | BLOCKED_CHECKOUT | Gumroad checkout required; CC0 claim only from a search snippet -> unverified -> quarantined. |
| Universal Base Characters | https://quaternius.com/packs/universalbasecharacters.html | CC0-1.0 | Quaternius | BLOCKED_GATED | CC0 (per the pack page) but the download is behind an itch.io / Patreon lightbox flow; the .blend source version is paid. Not fetched. |

## 5. Test matrix (measured, Blender 5.2.2)

| candidate | opens 5.2.2 | rig works | IK (measured) | walks | sits (90/90) | reaches | holds prop | face controllable | eyes move | parts replaceable | proportions | renders | convertible to our pipeline | GP works | licence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Creomoto Stick Man | yes | yes (27 bones) | 0.03 cm foot err | yes | yes | yes | yes | no | no | no | yes | yes | yes: driven by our semantic channels (0.02 % hip-height error) | no | CC0 |
| Low-Poly Rigged Man | yes | partly (IK error 6 cm) | 6.11 cm foot err | no | yes | yes | yes | no | no | no | yes | yes | no (fails accuracy) | no | CC0 |
| Old Lady | yes | yes (84 bones) | 0.81 cm foot err | yes | yes | yes | yes | eye+brow bones, no shape keys | no | no | yes | yes | partly (22/23 bone roles) | no | CC0 |
| Puppet Base | yes | FK only (26 bones) | none / none-testable | no | no | no | yes | eye bones | yes | no | yes | yes | partly (13/23 roles, no IK) | no | CC0 |
| Mike (ARP) | yes | yes (956 bones) - needs scripts for drivers | 0.01 cm foot err | yes | yes | yes | yes | 34 shape keys + 249 face bones (driver-dependent: 0 responded with autoexec off) | no | separate meshes but driver-bound | no | yes | heavy; script-dependent -> no | no | CC0 |
| MPFB default rig + OUR IK | yes | FK rig; IK added by us | 15.41 cm foot err | no | yes | yes | yes | 30 finger, 14 face bones, 4 shape keys | yes | mesh + macro sliders | yes | yes | yes (12/23 name roles; use Rigify instead) | no | GPL tool / CC0 output |
| MPFB + Rigify (generated) | yes | yes (1090 bones) | 0.02 % of hip height (candidate_drive) | yes | see note | yes (0.01 %) | n/a (control exists) | yes (94 face controls, 18 brow) | jaw yes; eye test inconclusive | mesh+macros+asset packs | macro sliders pre-rig | yes | yes: `candidate_integration_walk_reach.mp4` | no | GPL tool / CC0 output |
| Pepe (GP cutout) | yes | 22 bones, stretch-to, no IK | n/a | n/a | n/a | n/a | n/a | layers: eyelids, pupils, mouth, nose | pupil+eyelid layers/bones | yes: 15 layers | no | yes | concept only | yes | CC-BY / CC0 / quarantined (see cards) |
| Cowboy (GP) | yes | 6 armatures + hooks/lattice | n/a | n/a | n/a | n/a | n/a | eye layers | layers | yes: 40 GP objects | no | yes | concept only | yes | CC-BY / CC0 / quarantined (see cards) |
| Boy Head Test (GP) | yes | lattice + hooks | n/a | n/a | n/a | n/a | n/a | separate Eyes/Eyebrow/Mouth/Nose objects | yes: pupil layers moved by our gaze (1.47k px change) | yes: 6 objects | no | yes | gaze test done | partly broken | CC-BY / CC0 / quarantined (see cards) |
| Suzanno / Simple Head / Eye | yes | lattice/empties/22 bones | n/a | n/a | n/a | n/a | n/a | layers | layers | layers | no | yes | reference only | yes | CC-BY / CC0 / quarantined (see cards) |
| Human Base Meshes | yes | none (unrigged) | n/a | n/a | n/a | n/a | n/a | 1 head with 10 shape keys | separate eyeballs | 17 meshes | sculpt | yes | needs rigging = MPFB | no | CC-BY / CC0 / quarantined (see cards) |

Notes on the matrix: (a) "IK (measured)" is the largest foot-target error over a 24-frame stride/lift cycle; Rigify's is measured through its foot/hand IK **controls** in the integration drive. (b) `rigify_ik_test.py` reported a 131 cm reach error and a 124 degree "seated" knee for the Rigify rig - the later integration drive (same controls, `hand_target_err` 0.01 % of hip height, arm visibly reaching in the video) contradicts it, so I treat that standalone reach/seated trial as a harness fault, not a rig result. (c) Old Lady's base pose is *Sitting* and Mike's is *Crouch* (their only "idle" actions), so their walk/sit numbers are IK-response numbers from a non-standing pose. (d) Mike's `working_shape_keys = 0` and 3.7 % proportion change are consequences of script drivers not running with auto-exec disabled - not proof the face rig is broken.

## 6. Ranking by INDIVIDUAL factor (no composite score)

Order is best -> worst among candidates tested for that factor; `=` means indistinguishable in this audit. Evidence is in the cards/matrix above.

| factor | ordering (evidence) |
|---|---|
| **Technical rig quality** | MPFB+Rigify (1090 bones, IK/FK switch, 94 face controls, 0.02 % drive error) = Mike (956 bones, IK 0.0 cm, 249 face bones - but needs scripts) > Old Lady (84 bones, 30 finger + eye/brow bones, IK 0.2 cm) > Creomoto (27 bones, IK 0.03 cm) > Puppet Base (26 bones, FK only) > Low-Poly Man (19 bones, IK 6 cm off). GP: Pepe (22 bones, stretch-to) > Cowboy (6 small armatures + hooks) > lattice-only rigs |
| **Modularity** | MPFB (8 macro sliders + race blend + 1445 targets + asset packs + 5 rig options) > Pepe / Boy Head (one part per face feature) > Cowboy (40 GP objects) > Mike (229 meshes, driver-bound) > Old Lady (15 meshes) > single-mesh files (Creomoto, Low-Poly, Puppet) |
| **Visual quality** (judged on `rest_renders_sheet.png`, subjective) | GP Cowboy = Simple Head = Suzanno (finished stylised illustration) > Boy Head face > Mike (textured 3D) > Old Lady (sculpt, untextured in Workbench) > MPFB (neutral grey base; needs skin/clothes) > Puppet Base > Creomoto > Low-Poly Man |
| **Animation quality** (only shipped actions counted; artistry not judged) | Mike (4 actions) > Creomoto (idle + run) = Low-Poly (2 actions) > Boy Head (2) > Old Lady (1 sitting) > files with no actions. IK-driven motion quality (measured): MPFB+Rigify = Creomoto = Mike (all < 0.05 cm / 0.02 %) > Old Lady (0.8 cm) > Low-Poly (6 cm) |
| **Blender 5.2.2 compatibility** | opens and behaves cleanly: MPFB (extension, Blender >= 4.2), Rigify, all OGA files (Blender 2.67-2.76), Creomoto, Human Base Meshes, Cowboy, Suzanno, Simple Head, Eye > Pepe (converts; only a bust is visible in the default view over a black background layer) > Mike (opens; drivers/scripts inactive) > Boy Head 2.82 (stray blobs after GPv2->v3 conversion) |
| **Grease Pencil compatibility** | Cowboy = Simple Head = Suzanno (clean conversion + EEVEE render) > Eye > Pepe > Boy Head (artefacts; gaze layers still work) |
| **Licence safety** | CC0 files (Creomoto, Low-Poly, Old Lady, Puppet, Mike, Human Base Meshes, MPFB output) > CC-BY Blender Studio files (attribution text stored) > GPL-3 *tools* used externally (MPFB add-on, Rigify; no code vendored; outputs CC0) > quarantined (Suzanno/Simple Head/Eye archive files without licence text; Gumroad items with unverified claims) |
| **Suitability for our factory** (deterministic, local, 2.5D editorial 2D; no ML) | our own rig (baseline) > GP cutout **structure** as a concept (per-feature layers, pupil/eyelid layers, lattice head turn) > MPFB+Rigify as an optional 3D->2D backend (needs toon/outline pass) > Creomoto (skeleton reference) > Old Lady / Puppet Base (structure references) > Mike (rejected: 956 bones + scripts) > Low-Poly Man (fails accuracy) |

## 7. Selections

| slot | selection | why (measured) | not chosen |
|---|---|---|---|
| **A. 2D foundation** | **No external file.** Keep Open Peeps (CC0) atoms + our generated 26-bone rig | none of the audited files has swappable wardrobe + two-segment IK limbs + hands + face; ours passes the IK/gaze/hand tests already | Kenney (single-segment limbs, baked face), Blender Studio busts (front-only, head-only) |
| **B. 2D/GP technical reference** | **Blender Studio Pepe + Boy Head cutout rigs** (CC-BY; attribution text in the registry) | per-feature layers incl. eyelids/pupils, stretch-to deformation, lattice head-turn, layer transforms drive pupils (tested) | Suzanno/Simple Head/Eye (licence unverified) |
| **C. 3D human foundation** | **MPFB2 + Rigify** (GPL tool, CC0 output) | parametric bodies, 1090-bone Rigify with IK/FK + 94 face controls, drove from our semantic script at 0.02 % error, all-permissive outputs | Mike (script drivers, 956 bones), Old Lady/Puppet/Low-Poly (fixed art, weak or missing IK) |
| **D. GP reference** | **Blender Studio Cowboy** (GP illustration quality; hooks, lattice, armature-modifier on GP) **+ Brush Pack v2** | converts cleanly to GPv3, renders in EEVEE | Boy Head for rendering (conversion artefacts) |
| **E. stickman/skeleton reference** | **Creomoto's Stick Man (Fixed Up)** (CC0) | 27 bones, 8 IK constraints, idle+run, foot/hand error 0.03 cm, retargeted from our channels | Low-Poly man (6 cm IK error), Puppet Base (no IK) |

**Integration test scenes (real files, real Blender 5.2.2 renders):**
- `docs/blender_audit/candidate_integration_walk_reach.mp4` (`output/tests/candidate_integration_walk_reach.mp4`) - **ours | Creomoto | MPFB+Rigify**, all driven by the same semantic script (idle -> walk -> reach PHONE -> hold), 120 frames.
- `docs/blender_audit/gp_boyhead_gaze_{center,left,right,up,down}.png` - GP pupil layers moved by a gaze vector.
- `docs/blender_audit/capability_pose_sheet.png` - rest / walk contact / walk pass / seated / reach for five rigged candidates.
- `docs/blender_audit/rest_renders_sheet.png` - every opened file in Blender 5.2.2.
- `docs/blender_audit/kenney_rig_test.png` - Kenney limbs on our rig (earlier test, same protocol).

## 8. What this means for the factory (recommendation, not yet done)

1. **Do not swap the rig.** Nothing here beats the custom rig for an editorial 2D look.
2. **Borrow structure:** keep the eyelid/pupil/brow/mouth layer split (already ours) and consider Pepe's stretch-to bone idea for squash on limbs and Boy Head's lattice for 3/4 head turns - both remove our known "head turn = feature shift" limitation without new art.
3. **Spike MPFB+Rigify as a second backend for close-up hero shots** (true turnaround, walking from any angle): render to sprite with an outline/toon pass into the existing compositor. Costs: a stylisation pass, clothes/hair asset packs (not downloaded here), Blender-time per frame. It should be a separate, measured experiment - not folded into the V2 gate.
4. Attribution obligations if any CC-BY Blender Studio art is ever reused: the texts are stored in the registry (`attribution_text`).

## 9. Known gaps in this audit (honest list)

- Not downloaded: Blend Swap items (#30507, #15217, #13744), Gumroad items (GP Spider Rig, Super Stickman, Yadoob GP rigs), Quaternius/itch - all need sign-in / e-mail checkout / a lightbox flow. Standalone MakeHuman app, MPFB clothes/hair asset packs, Blender Studio character rigs (Sprite Fright etc.), BlenderKit and Sketchfab items were not fetched. **"2D Stickman V4GP" was not found.**
- MPFB: post-rig proportion change (rig refit) not tested; Rigify seated-pose and eye-rotation trials inconclusive (see note b); walking is verified through the integration drive, not through a full gait cycle with hip drop.
- GP candidates: only pupil-layer gaze was driven; body/limb GP deformation and GP -> our compositor were not integrated.
- Old Lady / Mike tested from a non-standing base pose (note c). Creomoto's forward axis in the comparison video was not verified (the stick blob has no clear front).
- Tests use the file's own units; ratios are normalised by leg/arm length, but absolute centimetre errors (e.g. "0.81 cm" for Old Lady, whose units are ~cm-scale) are in each file's units.
