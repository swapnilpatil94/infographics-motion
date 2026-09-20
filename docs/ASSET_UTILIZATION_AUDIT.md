# ASSET UTILIZATION + CHARACTER COMBINATION LAB

Question: **are we using the assets we already have to their full potential?**  Short answer, measured: **no**.  In every film we rendered, the whole Open Peeps library contributed **2 of 46 heads, 0 of 17 facial hairs,
1 of 9 accessories and none of its 30 expression faces**; the rest of the assets (RGS, Kenney, Blender Studio, Creomoto, MPFB, Humaaans) contributed nothing to a film. This milestone (a) proves that with a runtime trace,
(b) tests every asset family, (c) turns the parts that were wasted into working capability, and (d) says exactly what is still missing. Nothing was pushed; long-form was not started; no large new asset library was created.

> "A registered asset is NOT used." Production use below means: the production pipeline really opens the file (runtime trace), it contributes visible pixels, it survives the render, it is deterministic and reusable by the factory.
> Evidence lives in `docs/asset_audit/` (JSON + tables) and `output/tests/` (sheets and videos, listed at the end). Regenerate with the commands in *Files*.

---

## 1-3. Inventory, usage proof, classes

* **43 records** (`docs/asset_audit/inventory.json`, table: `inventory_table.md`, section-23 table: `utilization_table.md`): the 32 registry v2 sources + 11 collections that no registry v2 record lists (Open Peeps face / body / pose /
  template / head / facial-hair / accessory folders, own generated parts, own environments, OpenMoji, the font). Every record carries: source, URL, licence, local path, file types, dimensions, vector/raster, Blender compatibility,
  Grease-Pencil compatibility, rig compatibility, modifiable, commercial use, class (FOUNDATION / COMPONENT / REPLACEMENT / RIG / MOTION / FACE / HAND / HAIR / CLOTHING / PROP / ENVIRONMENT / GREASE_PENCIL / FX / REFERENCE ONLY / UNUSABLE),
  production use and the reason it is unused. 31 of 43 are on disk; 12 are blocked (login / checkout / gate), quarantined (no licence) or never downloaded.
* **Runtime proof** (`tools/asset_audit/trace_usage.py` -> `usage_trace.json`): the current production path (topic story -> plan -> cold-cache character bake -> Blender rig -> compositor with a skeleton, an insert-UI and a procedural shot)
  with every file-open instrumented opens **22 asset files**: 2 harvested-hand masks, **7 Open Peeps atoms** (`a person/bust.svg`, `body/Tee 1`, `face/Serious`, `accessories/* None`, `facial-hair/* None`, `head/Short 1`, `head/Short 4`)
  and 13 own-work environment layers. Nothing else. The plans of the 12 films we rendered contain **2 heads (`Bun 2`, `Short 4`), facial hair `* None` only, glasses `Glasses` only**.
* Everything below the neck (torso, limbs, 20 hand poses, shoes, clothing) and the whole environment set is **own work**. External assets contribute the head/hair/glasses drawings, one harvested hand, and the ink style.

| class | what we have |
|---|---|
| FOUNDATION | Open Peeps (CC0) bust template + ink language; own rig (26 bones + 4 IK) |
| COMPONENT / HAIR / FACE | 46 heads-hair-hats, 17 facial hairs, 9 accessories, 30 faces (Open Peeps) |
| REPLACEMENT | 20 baked face atoms (new), 1 harvested hand (Device), 20 procedural hand poses |
| HAND / CLOTHING / PROP | own generated (7 tops, 5 bottoms, 4 shoes, 6 accessories, phone/card/money parts) |
| RIG / MOTION | Creomoto armature (proportions + run cycle), MPFB2/Rigify (reference), own semantic grammar |
| GREASE_PENCIL / FX | Blender Studio cutouts (technique only), procedural GP-style FX bank |
| ENVIRONMENT | own sets (9), OpenMoji icons (CC-BY-SA, legacy cards) |
| REFERENCE ONLY | Kenney, RGS, OGA low-poly/old lady/puppet, Mike, Human Base Meshes, Blender Studio brushes/cutouts, Open Peeps poses/templates |
| UNUSABLE | Blend Swap / Gumroad / Quaternius (gated), 3 Blender Studio cutouts without a licence (quarantined) |

## 4. Open Peeps: full audit  (`openpeeps_atoms.json`, `output/tests/openpeeps_asset_contact_sheet.png`)

All **169 separate atoms** (+189 template drawings) were parsed (paths, subpaths, closed ratio, fills, groups, bbox, anchors, ink stroke), normalised where they are components
(`assets/library/openpeeps_normalized/`, source SVG -> cropped viewBox) and **composed on one bust through the production path** (`cast_builder._compose`): 169/169 compose.

| category | atoms | compose | reachable by the production vocabulary | use before this audit |
|---|---|---|---|---|
| head / hair / hats | 46 | 46 | 36 (10 unreachable: Bear, Mohawk 2, No Hair 2/3, Shaved 3, **Turban**, Twists 1/2, **hat-beanie, hat-hip**) | 2 in films |
| face (expression) | 30 | 30 | 1 (`Serious`, only as the composition base; **the expression itself was thrown away**) | 0 |
| facial hair | 17 | 17 | 5 | 0 (`None` only) |
| accessories | 9 | 9 | 2 (None / Glasses) | Glasses in 1 film |
| body (torso+arms+hands as ONE ink silhouette, Background + Ink groups) | 30 | 30 | 0 | `Tee 1` as base; 1 hand harvested (`Device`) |
| pose (whole standing / sitting figures) | 34 | render | 0 | 0 (reference only) |
| a person (bust / sitting / standing templates) | 3 | - | `bust.svg` | base |

Findings: heads, faces, facial hair, glasses are **clean closed-contour components that compose on any head** (same canvas): they are the reusable part of the library. Bodies and poses are **not separable into rig parts**
(one silhouette); the only extraction route is raster hand harvesting per atom (done for `Device`; open contours stopped the vector route). Stroke widths: the atoms are ink-filled shapes (hair solid black), so the distance-transform
stroke measure is only meaningful for line art (faces 12.3 svg units, accessories 10.3).

**What changed because of the audit**: `dna2` gained `EXTRA_HAIR_*`, `ALL_FACIAL` (17), `ALL_GLASSES` (8), `EXTRA_PALETTES` and five roles **without changing any existing character** (test: `dna2.make("x:1","young_man")` still `cdna_9c86892076`).
`lab_dna` reaches all 45 non-novelty heads, all 17 facial hairs, all 8 glasses. **20 face atoms are now baked as replacement drawings** (`parts_art2.bake_face_atoms`, Blender `face_atom_id` channel, `face_atom` action).

## 5. RGS  (`rgs_lab.json`, `output/tests/rgs_combination_test.png`)

RGS = CC0 game sprites: 1 body, 3 heads, 3 hairs, 7 eyes, 8 mouths, 5 horns, hands/feet/wings/weapons, **42 frames per part on a registered 2048 px canvas**. Its parts *are* separated, so we tested them literally:

| test | result |
|---|---|
| RGS head + our torso | a sphere with dots; even normalised (flattened, thin rim) it is a generic circle: no expression range, no ears/hair slot -> **unusable as a person** |
| RGS hair + Open Peeps head | raw: clashes (grey cel-shaded tufts, rim 7.4 % of part). **Normalised (flat dark fill + 3 % rim) reads as spiky hair and matches our ink**: the one usable component (weak: 3 hairs, punk/monster shapes) |
| RGS hand + our arm | a solid black blob (no fingers) -> unusable; normalised it is a mitten |
| RGS clothing + our rig | **none exists** in the pack |
| RGS eyes/mouths + Open Peeps head | eyes clash (glossy black); mouth curves (mouth1-4) fit the ink but are weaker than the 30 Open Peeps face atoms |

Measured style (`style_table.md`): our parts rim/part 0.028-0.062, flat 1-4 tones, no gloss; RGS raw 0.074-0.076 (2.5x heavier), 9 tones, specular gloss; normalised 0.029. **Verdict: REFERENCE ONLY** (hair1 = optional normalised component).
Normalising works mechanically but leaves nothing a person needs.

## 6. Blender Studio  (`gaze_test.json`, `output/tests/gaze_pupil_in_sclera_test.png`)

Pepe / Boy Head / Cowboy / Brush Pack (CC-BY-4.0) and 3 unlicensed cutouts (quarantined, never used). The Boy Head shows the **pupil moving inside a fixed eye white**. Our face slid the *whole eyeball* (white + outline + pupil)
across the face. **Production test built and adopted**: `gaze_mode = "pupil"` (default): the pupil object moves inside a fixed sclera; measured eye-white shift for a full look-right **18.8 px -> 8.7 px** (measured before the pupil's travel was trimmed by a further 13 % so it stays inside the white), the bottom row of the test sheet is visibly a gaze
instead of hopping eyeballs. The drawings themselves (3D-head GP style) and the brushes (need a live GP session, not deterministic in our compositor) are not used. Attribution obligation (CC-BY-4.0) applies to the technique's source if the files are redistributed: we redistribute none.

## 7. Creomoto stickman  (`creomoto_test.json`, `output/tests/creomoto_test.png`)

The `.blend` is a **27-bone armature with 8 IK constraints and two actions**; its visible mesh is a *bone-shape widget* (renders as a grey block): there is no stickman geometry.
* **Proportions match our rig** (ratio to leg length: thigh 0.50 / 0.51, upper arm 0.378 / 0.381, forearm 0.357 / 0.346) - independent confirmation of our proportions.
* **It supplies what we could not make: a running gait with a flight phase.** One 20-frame run cycle was extracted (`assets/library/creomoto_run_cycle.json`, CC0-derived data) and retargeted by leg length -> `motion_v2.a_run` (planted-stance speed from the cycle,
  hips bob, both feet leave the ground, arm drive, lean). RUNNING went from **MISSING (the old fast-walk: IK error 19-36 px, no flight phase)** to **PARTIAL (IK 0.0 px, flight frames present)**.
* A 14-figure stick-figure crowd can be drawn from the bone positions (2D) as a distant background; it reads as a different style from our ink characters, so use only far away.
Verdict: **useful beyond reference** as *motion data*; not a character.

## 8. MPFB2 + Rigify  (`mpfb_pose_reference.json`, `output/tests/mpfb_pose_reference.png`)

Our semantic channels (stand / sit / walk / reach / hold-phone / turn) drive the Rigify IK controls of an MPFB human; 4 orthographic views per pose (front, 3/4, side, back), Workbench render.
* **Works as a pose / turnaround / anatomy reference generator**: end-effector error <= 0.1 px in rig units, 24 renders in one run. Front, 3/4, side, back of the same body come for free - what our 2D rig lacks.
* **Limits (measured on the sheet)**: only feet/hands/hips are driven, so `sit` reads as kneeling and `hold_phone` leaves the arm out; a proper seated / phone reference needs channels for spine, head and elbows. Not tested: crowd generation and difficult poses beyond the six.
* Integration: **optional reference backend** (call `mpfb_pose_reference.py`); nothing 3D enters the film. GPL-3 code is an external tool only; outputs are CC0.

## 9. Humaaans

Not on disk (only a licence proof exists; the earlier "evaluation" was a web read). Read via the GitHub tree without downloading (mirror `jktzes/humaaans`, MIT code over Pablo Stanley's CC0 art):
**17 head/hair, 10 torsos (with arms; Hoodie, Jacket, Jacket2, LabCoat, LongSleeve, PointingForward, PointingUp, Pregnant, TrenchCoat, TurtleNeck), 8 standing + 4 sitting leg sets (Jogging, Sprint, SkinnyJeansWalk, Skirt, SweatPants, Wheelchair ...)**.
One component checked (`Sprint.js`): fills only, no strokes, colours hard-coded, **legs are separate paths**. So it is *not* limb-separable (arms are inside the torso) but is **harvestable as replacement drawings**: lab coat, trench coat, running and wheelchair legs -
exactly the garments (`LabCoat`, `TrenchCoat`, uniform) and the running/wheelchair legs our vocabulary lacks. It needs (1) a download - **I did not download it: it needs your approval** (44 small JS/SVG files) - and (2) ink-outline synthesis.

## 10-11. Combination lab, archetypes, production characters  (`combination_lab.json`)

* `output/tests/asset_combination_50.png` (+ `_front.png`): **50 characters, one rig, rendered through Blender**, chosen by farthest-point sampling on **12 structural axes** (head, hair length, facial hair, glasses, face types, body proportion bin, top, bottom, shoes,
  accessories, age group, headwear) from a coherent pool of 420. **Any two differ on >= 8 of 12 axes (mean 9.95); a palette change counts as zero** (test). 37 distinct heads, 46 body bins, 22 top/pattern combinations, 15 facial hairs, 8 glasses, 6 silhouettes.
* **Honest limit measured on the rendered output**: the *silhouettes* are less varied than the axes suggest (height-normalised mask IoU mean 0.59; 21 of 1225 pairs > 0.85): head/hair/headwear/accessories carry most of the identity; torsos and legs are the same
  blocks scaled. Hands vary only by skin tone and scale (one hand set).
* `archetypes_15.png`: young man/woman, middle-aged man/woman, older man/woman, office worker, student, shopkeeper, bank employee, delivery worker, parent, teacher, customer, security guard - **same rig, no new architecture**. Five roles were added (appended, non-disturbing).
  Uniform-ness is only colour + cap + accessories: there is no badge, epaulette, apron, saree/dupatta, high-vis vest or lab coat (missing garments).
* `production_characters_3.png`: **A young male** (Short 4, hoodie), **B middle-aged female** (Bun 2, Glasses 4, kurta), **C young female** (Long Curly, sweater, bag) - three views each, same rig / grammar / prop system.

## 12-13. Situations and props  (`situation_coverage.json`, `output/tests/situation_coverage.mp4` (99 s), `prop_matrix.json`, `output/tests/prop_interaction_matrix.png`)

**Prop matrix**: a general primitive (`props4.py`: hand pose + contact point + approach angle -> wrist position + wrist angle, expressed in arm lengths) runs REACH -> CONTACT -> GRAB -> HOLD -> USE -> RELEASE for
PHONE, CARD, MONEY, DOCUMENT, CUP, LAPTOP, DOOR, ATM, KEYBOARD, BAG: **all 10 props x 6 phases reachable, forward-kinematics contact error <= 0.5 px, Blender IK error 0.01 px**. The same hand/arm/IK system works for every prop;
this is a **reusable interaction primitive**. Caveats: (1) only phone / card / money have prop art (the rest are TEST glyphs); (2) the hand *drawings* do not wrap the prop (`hold_cup`, `grab`, `type` read as mitten shapes) - the kinematics are solved, the grip pictures are not;
(3) a bug found on the way: `hold_phone` reach on the table was 1.4 px out of reach for this body (fixed by moving the table point).

**Situation coverage** (31 requested, one labelled clip each, MEASURED status; a declared status is demoted by a measured IK error):

| status | situations |
|---|---|
| SUPPORTED (15) | sitting, standing, walking, reaching, looking, talking (Hindi lip-sync), pointing, holding phone, talking to another person, receiving object, giving object, surprised, scared, confused, realization |
| PARTIAL (13) | running (run cycle, no running art), reading (phone yes, paper = glyph), typing, drinking, carrying, opening door, sitting at desk, using laptop, using ATM, holding card / money / document, arguing |
| MISSING (3) | **turning** (head is one drawing for every view; no body turn), **eating** (no food art, no chewing), **bending** (IK error 21 px on the return from the bend; the torso is one drawing) |

Bugs the tests found and fixed: hand targets with easing overshoot went 15-55 px past the arm's reach (Blender IK missed); a new guard (`short._clamp_reach`) keeps every hand within [0.32, 0.985] x arm length of ITS shoulder.

## 14-15. Face system and head turn  (`face_lab.json`, `output/tests/face_expression_matrix.png`, `face_expression_atoms_vs_procedural.png`, `head_turn_existing_assets.png`)

* **Face system today**: eye white (+`wide` shape key) + ring + pupil, brow strips (raise / tilt / asym), mouth line (smile / frown / worried) + cavity (6 visemes), nose part, blink. 
* **512 combinations** (8 eye states x 8 brow states x 8 mouth states) rendered through the rig. Measured: ~320 of 512 are distinguishable (>= 150 changed px), eyes and brows are strongly separable (0 % of state pairs identical) but **the mouth axis is weak: 21 % of mouth-state pairs are effectively identical** -
  `smile`, `frown` and `worried` differ from `closed` by only 40-90 px (a thin dark lip on dark skin). Only mouth *opening* reads. This is why fear / realization / surprise look alike in the procedural row.
* **The 30 Open Peeps face atoms fix exactly that** (bottom row of `face_expression_atoms_vs_procedural.png`): anger, suspicion, smile, tired read instantly and are in our head's ink language by construction (same canvas). Drawbacks: gaze is baked in;
  `Awe` and `Concerned Fear` are mis-mapped for surprise / realization. Decision: **replacement drawings for PEAK beats, procedural face for continuous gaze acting** (used by `styles.DAY_STUDY`).
* **Head turn: existing assets are insufficient.** FRONT / 3/4 / SIDE / 3/4 / FRONT differ only in the body; **the head is the same drawing in every view** (`head_turn_existing_assets.png`). *We have*: 3 body view-sets, a back-of-head (hair fill), view swap without interpolation.
  *We are missing*: a **front head and a profile head (skull + hair + face placement) per character**, or a yaw-card trick with depth-separated face layers (not built: a flat plane goes edge-on at 90 degrees, so it would only cover about +-35 degrees).

## 16. Torso / limb audit

| capability | covered by | status |
|---|---|---|
| standing, walking (planted gait), running (Creomoto cycle), sitting, reaching, holding | rig + grammar | OK (running lacks art) |
| pushing / pulling | hand poses `push` `pull` exist; not shown in a film | untested visually |
| bending | spine/pelvis keys work; torso is one drawing | PARTIAL |
| turning | none | MISSING |

**Minimum replacement set that unlocks everything above** (smallest -> largest): (1) **torso bend/compress shape key** (procedural, 0 drawings) for bending; (2) **front + profile head per character** (2 drawings) for head turns; (3) **4 prop-grip hands** (cup wrap, keyboard-flat,
door lever, bag handle) for the props we solved kinematically; (4) **5 garments** (lab coat, apron, saree/dupatta, high-vis vest, uniform with badge) - Humaaans has 2 of them; (5) a **thicker / darker mouth line** (procedural) or atoms for smile/frown.

## 17. Asset economics  (`economics.json`)

The theoretical permutation count of the axes is 5.9 x 10^12 and means nothing. Measured instead on 6000 coherent characters (colour excluded): **every one was unique**, so the space is much larger than the sample, but its size can't be estimated from repeats.
Greedy **packing** (pool 6000, lower bounds): **5669 characters that pairwise differ on >= 4 of 12 axes, 1396 on >= 6, 98 on >= 8, 12 on >= 10.**
Realistic reading: **~100 strongly different people, ~1400 clearly different people, thousands of mild variants**, limited by identical torsos/legs and one hand set.

## 18. Visual style  (`style_table.md`)

| asset family | rim / part | tones | gloss |
|---|---|---|---|
| own torso / hands / face atoms | 0.028 / 0.047 / 0.062 | 4 / 2 / 0 | no |
| Open Peeps composed head | 0.015 | flat | no |
| RGS raw / normalised | 0.076 / 0.029 | 9 / 1 | yes / no |
| Blender Studio GP render | 0.004 | soft | highlights |
| prop glyphs (placeholders) | 0.016 | 1 | no |

Ink weight of production art sits in 0.015-0.062; RGS raw is 2.5x heavier and glossy (does not belong); GP renders are 7x thinner (would not match without re-stroking). Perspective: everything is orthographic 3/4-side; environments are more detailed than characters (unchanged finding).

## 19. Unused assets: the decision for each

| asset | can it improve | decision |
|---|---|---|
| Open Peeps face atoms | face quality, extreme expressions | **built** (`face_atom`, 20 baked, DAY_STUDY uses smile / dread / suspicious) |
| Open Peeps heads/hats/turban, facial hair, glasses | character variety, Indian cast (turban) | **built** (lab_dna, dna2 vocab) |
| Open Peeps bodies | hands for cup / laptop / paper | candidates for raster harvest: **needs per-atom crop boxes** |
| Open Peeps poses/templates | pose reference | reference only |
| Creomoto run cycle | running | **built** (`run` action) |
| Blender Studio Boy Head pupils | gaze | **built and adopted** |
| MPFB2/Rigify | turnarounds, anatomy | **built as a reference generator** |
| RGS hair1 | spiky hair | optional after normalising; not adopted (weak) |
| RGS everything else, Kenney | - | no: documented above |
| Humaaans | lab coat, trench coat, running / wheelchair legs | **blocked on a download approval** |
| Blender Studio brush pack | ink FX | no (live GP session, non-deterministic) |
| OGA old lady / Mike / low-poly / puppet / Human Base Meshes | bone layouts, anatomy | reference only |

## 20-21. One character, many situations  (`identity_test.json`, `output/tests/one_character_many_situations.png`)

Production character A (DNA `cdna_ff50cb5293`) in **5 places x 6 situations** (bedroom, office, bank, street, ATM; standing, sitting, walking, phone reading, talking, fear with an atom face) through the real compositor: 30 stills.
Identity (hue-histogram overlap of the character's own pixels, lighting-independent): **min 0.947, mean 0.982** - recognisably the same person. **A cafe set does not exist.**
`environment_coverage.png`: **all 9 sets accept the full-body actor** (no errors, floors align), but only `bedroom_wide` and `study_room` are built for it (furniture in the character plane). In `office_day`, `bank_branch`, `street_dusk` the foreground counter
**hides the legs**, seated poses float (no chair), and the ATM is taller than the person: they work as backdrops for upper-body shots, not as full-body stages.

## 22. Two different Shorts from the same library

Both films were generated by `python3 studio.py --skeleton-topic ...` with **no story-specific artwork**. What changed between them is only the **art-direction style** (`engine/skeleton/styles.py`, chosen per scam domain by `PACK_STYLE`):
environment, cast, blocking, camera language, lighting, psychology (extra acting / replacement faces at beats), motifs and act arc. Films: `output/shorts/topic/fake_whatsapp_investment_group/final.mp4` (A) and `.../lottery_prize_processing_fee_scam/final.mp4` (B); evidence in `docs/asset_audit/two_shorts/`, side-by-side sheet `sheets/two_shorts_side_by_side.jpg`.

| axis | Short A | Short B |
|---|---|---|
| story / domain | दोगुना पैसे का वादा / investment | जो इनाम माँगा ही नहीं / lottery |
| art direction (style) | night_bedroom | day_study |
| arc | 20 beats: ESTABL PHONE_ LOOK_A EYES_C REACH_ PICK_U READ_M REALIZ STAND_ WALK_A PERSON EYE_CO OTHER_ HAND_O OTHER_ INSERT VISUAL BOTH_R CLOSE_ RESOLV | 17 beats: ESTABL PHONE_ LOOK_A REACH_ PICK_U READ_M INSERT REALIZ STAND_ PERSON EYE_CO HAND_O OTHER_ VISUAL BOTH_R CLOSE_ RESOLV |
| character selection | protagonist: masculine 22, Short 4, hoodie; mother: feminine 47, Bun 2, kurta | protagonist: feminine 24, Medium 1, sweater; father: masculine 50, Short 2, shirt |
| environment | bedroom_wide | study_room |
| blocking | {"A_origin": 380.0, "D_origin": 1440.0, "A_stop": [830.0, 1500], "D_stop": [1070.0, 1500], "handover": [905.0, 860.0], "A_start": "sit"} | {"A_origin": 300.0, "D_origin": 1290.0, "A_stop": [620.0, 1500], "D_stop": [950.0, 1500], "handover": [780.0, 880.0], "A_start": "sit"} |
| camera sizes / moves | {"wide": 1, "two_reach": 2, "medium": 3, "close": 5, "full": 2, "two": 4, "reveal": 1} / {"push": 5, "reveal": 2, "isolate": 3, "drift": 1, "rack_focus": 1, "pull": 3, "track": 1, "hold": 1, "truck": 1} | {"wide": 1, "two_reach": 2, "medium": 5, "close": 1, "full": 1, "two": 4, "reveal": 1} / {"push": 3, "reveal": 2, "isolate": 2, "drift": 1, "rack_focus": 1, "pull": 3, "hold": 2, "truck": 1} |
| props / furniture | phone at [670.0, 1166.0], bed + nightstand | phone at [720.0, 1050.0], chair + table + lamp |
| psychology (replacement faces) | procedural only | dread, smile, suspicious |
| GP motifs | arcs, arrow, rays, ring, scribble, ticks, worry | arcs, ring, scribble, ticks |
| lighting | moods ['dim', 'fear', 'relief'], moon True, sun False | moods ['bright', 'pressure', 'warm'], moon False, sun True |
| composition | 20 shots, mean 2.34 s, insert at beat 16 | 17 shots, mean 2.72 s, insert at beat 7 |
| duration | 46.83 s | 46.169 s |
| QC | True (52 gates; n/a: []) | True (50 gates; n/a: ['real_skeletal_walk', 'lamp_raises_brightness']) |

* **Same library** in both: one rig (26 bones + 4 IK), 20 hand poses, Open Peeps heads (Short 4 / Bun 2 in A; Medium 1 / Short 2 in B), the same act grammar, the same critic. **Different**: 3 of the 9 required axes are genuinely new capability from this audit - *psychology*
  (B uses the Open Peeps `smile` -> `dread` -> `suspicious` replacement faces, A stays procedural), *environment* (`study_room`: chair, table, lamp in the character plane) and *character selection* (a woman and her father, glasses, different heads/clothes).
* Critic on B (the first time on a NEW room): 5 shots framed wrong at round 0 (the A/bedroom presets do not transfer: `presets` are per style), all solved in 1 round without rendering (`critique/report.md`); a new **set-edge guard** (`SET_X`) keeps the frame inside the set
  when a solution exists. QC: A **52/52**; B **50/50 applicable gates** (2 gates are recorded as *not applicable*, not silently passed: no walk in the 17-beat arc, and no 'lamp comes on' in a daylight film).
* **Honest defects visible in B**: (1) the study room's window is still a **night sky with a moon** - the set art has no day variant, so "day" is lighting only (missing asset: a day sky); (2) the entrance shot still shows a thin black strip at the right edge (no camera
  satisfies both the framing and the set edge); (3) the day lighting is only warm/bright: the shadows and light shaft are still the moon's; (4) the two films are structurally similar (same scam-message-then-visitor skeleton): the acts differ by 3 beats, not by story shape.
* Two gates had to be made **arc/style-aware** in `qc_v3` (walk gate, lamp gate) and one threshold generalised (`starts off-screen`: beyond the set edge, not a fixed x) - each is documented in the report evidence.


## 24. The 16 answers

1. **Are we using Open Peeps properly?** No, and it was measured: 2 of 46 heads, 0 of 17 facial hairs, 1 of 9 accessories, 0 of 30 faces in every rendered film (7 files opened at runtime). It is fixed for heads / facial hair / glasses (all reachable in `lab_dna`) and faces (20 baked replacement drawings);
   bodies (30), poses (34) and templates (189) remain reference-only.
2. **RGS?** Not properly used, and not usable: game-monster sprites (rim 2.5x ours, cel gloss); no clothing; heads/hands unusable even normalised. Only `hair1`, normalised, reads as spiky hair (optional). **Reference only.**
3. **Blender Studio useful to production?** The **technique**, yes: pupil moving inside a fixed eye white is now the production default (eye-white shift 18.8 -> 8.7 px). The cutouts/brushes: no (different 3D-head GP style / non-deterministic); 3 cutouts are unlicensed and stay quarantined.
4. **MPFB2/Rigify improve the factory without replacing 2D?** Yes, as a **reference generator**: our channels drive Rigify IK (<= 0.1 px), 4 views per pose in one run. It cannot yet give proper sitting / phone poses (only feet, hands, hips are driven) and is never the final look.
5. **Creomoto useful beyond reference?** Yes, as **motion data**: its 20-frame run cycle now drives our `run` action with a flight phase (IK 0.0 px); its proportions independently match ours. The stickman mesh itself is a bone-widget block - a stick crowd must be drawn from bone positions.
6. **Humaaans useful for components?** Probably: 10 torsos (LabCoat, TrenchCoat, Pregnant ...), Sprint/Jogging/Wheelchair legs, 17 heads; fills only, hard-coded colours, legs are separate paths. **Not downloaded - it needs your approval** (44 small files) and outline synthesis.
7. **Which assets are wasted?** Open Peeps: 44 of 46 heads (before), 12 of 17 facial hairs, 8 of 9 accessories, 29 of 30 face atoms (until now), 30 bodies, 34 poses, 189 templates. Also RGS (80 MB), Kenney, OGA rigs, Mike, Human Base Meshes, the brush pack: downloaded, tested, unused (correctly, but 550 MB of raw files).
8. **Smallest missing asset set?** (a) **front + profile head per character** (or a tested yaw trick) for any head turn; (b) **4 prop-grip hand drawings** (cup wrap, keyboard-flat, door lever, bag handle); (c) **5 garments** (lab coat, apron, saree/dupatta, high-vis vest, uniform badge - Humaaans has two);
   (d) a **day sky** for the room sets and a **cafe / seating** layer; (e) procedural: torso bend shape key, a heavier mouth line. That is ~12 drawings + 2 procedural changes.
9. **Situations already covered?** 15 fully, 13 partially (kinematics solved, prop art missing) of the 31 requested: `situation_coverage.mp4`.
10. **Impossible today?** Turning (head/body), eating (no food art, no chewing), bending (torso is one drawing; hand return misses 21 px). Running exists but has no running art.
11. **How many believable characters?** 50 rendered and verified distinct (any two differ on >= 8 of 12 structural axes, palette changes counted as zero). Packing in a 6000-pool: **98 strongly different (>= 8 axes), 1396 clearly different (>= 6), 5669 (>= 4)**. Silhouettes vary less than the axes (IoU mean 0.59): identity is head/hair/headwear/accessories.
12. **How many environments?** 9 sets accept the actor; **2 are built for it** (bedroom_wide, study_room), 5 are backdrops only (legs hidden by foreground counters, no seats), atm_area is dark/bust-scale, **no cafe**; each has ~3 palette variants; the study window is night-only.
13. **Which props need new interaction anchors?** All except phone need prop-side contact points AND matching hand drawings: CUP (wrap), DOCUMENT (pinch/two-hand), LAPTOP/KEYBOARD (flat hands on a real keyboard surface), DOOR (lever), ATM (fingertip on real keys), BAG (handle), FOOD. Kinematics already solved for all 10 (<= 0.5 px).
14. **Production assets:** Open Peeps heads/hair/hats/facial hair/glasses/face atoms/harvested hands; own parts and the two full-body sets; the Creomoto run cycle (data); the Boy Head gaze technique. **Keep as reference-only:** RGS, Kenney, OGA rigs, Mike, Human Base Meshes, MPFB2 output, Open Peeps poses/templates/bodies, Creomoto mesh, brush pack.
15. See 14. Humaaans: pending your download approval (then production candidate for garments/legs).
16. **What must NEVER be added:** more Open Peeps-style heads (46 exist, 2 were used); more palettes/colour variants; another rig architecture or a second character format; a 3D character backend for the final look; game-sprite packs (RGS/Kenney); Grease-Pencil brush packs that need a live session;
    a big prop-art library before the matching hand drawings exist; more environment families before the two full-body sets have day/night variants; long-form work.


## Files

`docs/asset_audit/`: `inventory.json`, `inventory_table.md`, `utilization_table.md`, `usage_trace.json`, `openpeeps_atoms.json`, `rgs_lab.json`, `gaze_test.json`, `creomoto_test.json`, `mpfb_pose_reference.json`, `combination_lab.json`, `face_lab.json`, `prop_matrix.json`,
`situation_coverage.json`, `identity_test.json`, `environment_coverage.json`, `economics.json`, `style_table.{json,md}`.
`output/tests/` (git-ignored, regenerate): `openpeeps_asset_contact_sheet.png`, `asset_combination_50.png`, `asset_combination_50_front.png`, `archetypes_15.png`, `production_characters_3.png`, `face_expression_matrix.png`, `face_expression_atoms_vs_procedural.png`,
`head_turn_existing_assets.png`, `gaze_pupil_in_sclera_test.png`, `prop_interaction_matrix.png`, `situation_coverage.mp4`, `one_character_many_situations.png`, `environment_coverage.png`, `rgs_combination_test.png`, `creomoto_test.png`, `mpfb_pose_reference.png`.
Code: `engine/skeleton/{lab,lab_dna,props4,styles}.py`, `tools/asset_audit/*.py`, `tests/test_asset_audit.py`. Copies of the small sheets are in `docs/asset_audit/sheets/`.
