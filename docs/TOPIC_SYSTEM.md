# Topic → Film system (with a self-critiquing loop)

    python3 studio.py --skeleton-topic "fake WhatsApp investment group"            # story (LLM + packs) -> voice -> direct -> CRITIQUE+FIX -> render -> QC
    python3 studio.py --skeleton-topic "<topic>" --story-json output/shorts/topic/<slug>/story.json     # deterministic re-run (no LLM; fixes are stored in the story)
    python3 studio.py --skeleton-topic "<topic>" --no-llm --draft --critique-rounds 2                   # fast preview: packs only, estimated timing, no TTS

Nothing about a particular story is hand-authored: the story, the Hindi narration, the cast, the shot list, the camera, the lights and the fixes all come out of code. `short_director_v3.py` (the
hand-written "एक गलत कॉल" film) is now only the reference the auto-director was transcribed from.

## Pipeline

| stage | code | what it does | fallback when it fails |
|---|---|---|---|
| domain | `topic_story.classify` | keyword-scores the topic against 7 domain packs (bank KYC/OTP, lottery, job offer, courier/digital-arrest, investment group, UPI refund, loan app) | out-of-domain topic → `TopicNotSupported` (refused, not faked) |
| customise | `topic_story._customise` (qwen3:14b, JSON schema) | title, protagonist name/gender, who walks in, sender id, message text, bait line, hook, lesson, amount, act arc | each field validated (Devanagari-only spoken text, word limits, amount snapped to a spoken-number table, arc must pass `arc_ok`); rejected field → pack value; decision logged in `story["provenance"]` |
| acts | `acts.py` | closed vocabulary of 20 dramatic acts with prerequisites (`PICK_UP` needs `REACH_PHONE`, `HAND_OVER` needs the phone in hand, a handed phone cannot be read again, …). `repair()` makes ANY sequence valid | fuzz-tested (400 random sequences) |
| narration | `topic_story.lines_for` + `topic_build.real_narration` | one Hindi line per act (gender/relation agreement), Chatterbox TTS cached by content hash, pacing re-tempoed until the film lands in 45–60 s | — |
| direct | `auto_director.build_plan` | act → shot: camera intent, lighting, GP effect, insert screen / money-flow data, semantic actions for both characters, SFX, mood track | — |
| critique + fix | `critic.improve` | see below | unfixable findings are reported, not hidden |
| render | `short.render_film` | Blender rig + 2.5D compositor, unchanged from V3 | — |
| QC | `qc_v3.run` | every V3 gate; gates about an act the story does not contain are recorded as not-applicable (`evidence.not_applicable_gates`) | — |
| final review | `critic.review_final` | one frame per shot from the finished mp4 → luminance + VLM | advisory only |

## The critic

Fixes are **keyed by beat id** (not by time) and stored in `story.json`, so they survive re-timing and a re-run is deterministic.

1. **Measured geometry, no rendering** (`measure_geometry`, `solve_camera`). At 3 moments of every shot: are the head corners, feet (full shots) and phone (reach shots) inside the safe rectangle; is the face above the
   caption band (y < 1335); is the head big enough for the shot size. The fixer searches `(zoom_mul, dx, dy)` – smallest change first – that satisfies every constraint at every sample.
2. **Measured pixels** on preview stills rendered by the real pipeline (only the needed frames go through Blender, ~35 s for 20 stills): face-region luminance, frame luminance, phone-screen text contrast.
   Fixers: a soft fill light on the faces + exposure for dark shots, less bloom on a white phone screen (bloom washed the SMS text out).
3. **VLM review** (local `qwen3.5:9b`, stills downscaled to 540×960): subject visible / face readable / too dark / text legible / cluttered / issues / score. **Advisory.** It is reported next to the measurements.
   Measured agreement in the run below: it flagged 1 of the 4 shots whose head was measurably clipped and missed 3, so it is *not* trusted to drive fixes.
4. **Rhythm** (`review_rhythm`): repeated identical framings (fixed by changing the camera move), shot length extremes, hook length, total duration (fixed by re-pacing).

The loop renders stills → measures → fixes → re-renders (≤ N rounds, default 3, stops early when clean) and writes `critique/report.{json,md}`, `critique/round_K_sheet.png` (red frame = flagged),
`critique/before_after.png`, and after the render `critique/final_sheet.png` + `final_review.json`.

## Results on two new topics

Two topics, both generated from the topic string alone (evidence in `docs/topic_evidence/<slug>/`: `story.json`, `plan.json`, `qc_report.json`, `critique/report.{json,md}`, `round_0_sheet.png`, `before_after.png`, `final_sheet.png`).

| | "fake WhatsApp investment group" | "lottery prize processing fee scam" |
|---|---|---|
| domain pack / LLM fields accepted | investment / 10 of 10 | lottery / 10 of 10 |
| beats, duration | 20, 46.8 s | 20, 45.7 s |
| critic round 0 (measured) | 4 shots with a clipped head, 15 pixel flags (dark faces, washed-out SMS text) | 4 clipped heads, 15 pixel flags |
| round 3 | 0 / 0 | 0 / 0 |
| fixes applied | 4 camera solves, dark faces lit over up to 3 rounds (fill light +0.7 per round), SMS bloom 0.4 -> 0.15 | same pattern |
| VLM mean score (advisory) round 0 -> final | 5.85 -> 6.35 (final mp4: 6.55) | 6.75 -> 7.9 (final mp4: 7.45) |
| QC v3 | 52/52 | 52/52 |

* The critic found the SAME four framings clipped in both films (`PHONE_ALERT`, `PICK_UP`, `PERSON_ENTERS`, `HAND_OVER`): a director preset problem, not a story problem. Those four corrections are now the
  director's defaults (`auto_director.PRESETS`), so a new story starts clean; a structurally different arc (the 17-beat lottery arc: no walk) still needs and gets its own solves (`tests/test_topic_system.py`).
* **VLM vs measurement** (same numbers in both films): of the 4 shots whose head was measurably clipped, the VLM flagged 1 and missed 3 (0 false alarms). It also keeps saying "faces too small / too dim" on
  shots that pass the measured thresholds. It is a second opinion, not a judge.
* **What the critic did NOT change** and a viewer will still see: the night look is dark by design (face luminance is lifted to >= 0.38 but the shots remain moody); the two-shots are cramped; the
  insert screen's white ring is faint on the white SMS bubble; the money-flow counter shows a mid-count number when sampled.
* **Sameness.** Both stories have the same 20-act structure, the same two-character staging and the same protagonist name/relation: the LLM chose the full arc and the same defaults. Topic variety is in the
  text, message, amount, cast look and data, not in staging.
* The lottery film's LLM-written bait line is weak ("मैसेज: अजीब संदेश आया") and the money-flow amount (five lakh for a fee scam) is the LLM's, not a domain-correct number: field validation checks form, not sense.

### Other flaws fixed in this pass (found while running the loop)

| flaw | fix |
|---|---|
| standing arms clasped in front of the pelvis (rest pose hands 22-26 px forward, both arms overlapping) | `pose_stand` / `_arm_rest`: hands by the sides, per-side shoulder offset, `REST_REACH` 0.95 (0.965 made Blender's IK 5 px off on near-straight arms; the side offset was missing) |
| phone hand lagged behind the rising body in a stand-up (arm 15 px past its reach, IK error 3.5 px) | `a_stand` carries a held phone with the shoulder |
| "walks across the room" was a 1-step, 155 px shuffle | `walk_to(fill=True)`: the walk takes the beat's time; A_STOP 830 / D_STOP 1070 (2 steps, 205 px) |
| reach to the nightstand marginal for larger bodies (hand travel 162 < half arm 165) | seated hands rest nearer the lap (travel 184 px) |
| SMS text washed out by bloom | bold near-black text + `ui.bloom` critic parameter (text contrast 0.12 -> 0.71) |
| money-flow bank label sat under the caption | graph compressed above y 1335 |
| money-flow used the wrong label key | `from_label` |


## What the critic cannot fix (honest list)

- **Character art.** Heads are one drawing per view (no neck compression, no head replacement drawings for extreme expressions), torsos are single drawings (no bent/straight variants), only the phone grip is solved
  (no cup / pen / card / cash grips), the standing rest pose is a single arm drawing. The critic can reframe and relight; it cannot redraw.
- **The set.** One 2.5D bedroom (`bedroom_wide`), one or two characters, phone-centred acts. Topics outside "a message arrives on a phone, a family member walks in" are refused.
- **Style match.** The environment is more detailed than the characters (single depth plane for actors).
- **Narration.** Hindi lines are templates filled with validated LLM fields. They are correct and consistent but not literary; the LLM is not trusted to write Devanagari prose (qwen3 is weak in Hindi, gemma4 ignores schemas).
- **The VLM is noisy** (see the agreement numbers). Only measured findings drive fixes.
- **Thresholds are judgement calls** (face luminance ≥ 0.38, head px per shot size, contrast ≥ 0.6). They were set by looking at stills; a viewer may disagree.
- **Automated gates cannot prove the film looks good.** Judge the rendered film.

## Files

`engine/skeleton/{acts,topic_story,auto_director,critic,topic_build}.py`, tests `tests/test_topic_system.py` (19), studio flags `--skeleton-topic --story-json --critique-rounds --no-llm --draft`.
