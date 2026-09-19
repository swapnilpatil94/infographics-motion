# Build report — masternew.md ("Strictly build this")

## Result
* **Film**: `output/projects/why_smart_people_v2/final/master.mp4` — "स्मार्ट लोग स्कैम में क्यों फँस जाते हैं", 9:16, 1080×1920@30, **334.8 s (5.6 min)**, 67 shots (46 performance / 9 phone-UI inserts / 12 procedural graphics), Hindi TTS narration, mixed and loudness-normalised (−16.2 LUFS, TP −1.4 dB). **QC: 20/20 checks pass.** Rendered in 35 min (6.3× realtime).
* `final/master_16x9_blurpad.mp4` — 1920×1080 **blur-pad derivative** of the vertical master, *not* a native widescreen composition.
* Earlier runs kept in `final/previous/` (each fixed a defect found by viewing frames: double phone pickup, captions printed over graphic cards, stack/checklist titles under the lifted caption).

## Commands
```bash
python3 studio.py --story stories/why_smart_people_fall_for_scams.md --narration narration/why_smart_people_fall_for_scams.wav.segments.json --name why_smart_people_v2
python3 studio.py --project-plan output/projects/why_smart_people_v2/project/shot_plan.json        # deterministic re-render, no LLM
python3 studio.py --api-request request.json                                                      # what a UI calls (engine/api.py)
.venv/bin/python -m unittest discover -s tests                                                    # 54 tests
```

## Built (this pass)
Character DNA · 7 environment families + variation · 23 props · crowd · semantic motion grammar (32 actions × 11 emotion styles × intensity) · intent-driven camera grammar (9 intents) · DSL validator · seeded variation (`style.seed`) · licence policy + registry + asset library (schema, sha256 dedupe) · acquisition tools with live GitHub licence lookup · 14 Grease Pencil effects chosen by meaning · API/CLI facade · stage packages (`engine/story|director|rendering|blender|qc|fx|compositing`) · reuse proof (`docs/ASSET_REUSE_PROOF.md`) · docs (`docs/FACTORY.md`).

## Reused
Open Peeps SVG atoms (CC0), the existing layered rig / compositor / GP bank / TTS+alignment tooling / three base sets. A second, different story reused 12 of 15 components (80 %).

## Components and licences
Open Peeps (CC0) · Noto Sans Devanagari (OFL-1.1) · OpenMoji icons (CC BY-SA 4.0, share-alike; in the library, **unused in the film**) · all sets, props, rigs, GP strokes are own work (procedural). Decisions per source: `assets/library/source_decisions.json`. COA Tools 2 / Proscenio (GPL-3) not vendored; Tiny 2D Rig Tools has no licence → not used (`docs/RIG_TOOLS_COMPARISON.md`).

## Tests
54 unit tests (licensing, library, variation, DNA, crowd, environments, props, motion grammar, camera grammar, DSL validation, determinism of the plan, GP stroke design, API, reframe, fixed-frame regression scene). Writing them exposed one real bug (the licence policy did not reject "Non-Commercial").

## Limitations (not hidden)
1. **Length**: 5.6 min, not 8–12. A longer film needs a longer story + ~1 h of TTS + ~1 h render; not done.
2. **Rendering**: the film is composited by the 2D layer compositor. Blender authors the Grease Pencil effect bank (real GPv3) and a native bone-parented-GP + IK rig is verified (`tools/verify_native_gp_rig.py`), but Blender does not render the film.
3. **16:9** is a blur-pad derivative; the art is portrait-native. No re-staged widescreen.
4. **Rigs are busts**: no walking, full body or sitting; those actions degrade to posture + camera. Hands/arms are crude.
5. **Only two characters, two locations** in the film (story-dictated); the crowd/bank/call-centre/ATM/living-room families are proven in stills and the second story, not in the master.
6. **Captions overlap phone-UI buttons** on insert shots (caption band at y=1440); graphic cards were fixed, UI inserts were not.
7. **Local-LLM analysis is noisy** (Hindi tags, location: 'बैंक की स्क्रीन' → bank branch). Mitigated by domain cue validation, not eliminated. Analysis takes ~10 min per story.
8. **QC composition check** was refined to include the graphic type / UI screen in a shot's signature (a countdown card and a ladder card are different compositions); the same ladder card still appears twice (S049, S052).
9. No human viewer testing. Second story uses synthetic narration timings (plan + stills only).
10. `S020` reported as a soft warning: 7 consecutive performance shots.

## Next
Longer story + full-length TTS; native-16:9 sets; walking/sitting rigs; GP-native rig render path in Blender; location-tag validation; caption placement on UI inserts; more environment/prop art quality (call-centre art is weak).
