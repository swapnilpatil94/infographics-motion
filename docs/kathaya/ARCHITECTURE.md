# Kathaya architecture (story -> film)

```
Narration (text | audio | timing JSON)
   -> NarrationTimeline            kathaya/story/narration.py        temporal spine; segments are whatever the narration is
   -> Creative Director            kathaya/director/                 local LLM (one visual at a time, legal-action menus) OR ChatGPT (copy / paste)
   -> VisualScenePlan              kathaya/director/visual_planner   exact times derived from the timeline; validated
   -> Capability + Asset Resolver  kathaya/assets/resolver.py        AVAILABLE | UNSUPPORTED | MISSING  (+ AssetRequest, structured capability errors)
   -> [human approval ONLY for a new asset]  references (Wikimedia Commons, licence-classified) -> approve -> build -> library
   -> Compiler                     kathaya/renderer/compile.py       pure transformation with fixed tables; refuses an unresolved plan
   -> Deterministic renderer       engine/skeleton (+ engine/blender)  unchanged core: rig, Blender, 2.5D compositor, audio director, QC, frame cache
   -> Technical QC                 kathaya/qc/technical.py + engine qc_v4
   -> final.mp4
```

## Boundaries (where the responsibilities live)

| responsibility | module | note |
|---|---|---|
| story / narration -> timeline | `kathaya/story/` | `narration.py` (timing JSON, audio+text, Chatterbox TTS, estimate), `hindi.py` (numerals -> spoken words) |
| creative decisions | `kathaya/director/` | `prompt.py` (whole-plan prompt for ChatGPT), `sequential.py` (local LLM), `providers.py`, `visual_planner.py` |
| camera intent | director chooses shot + movement (+ subject); `kathaya/renderer/manifest.py` lists what exists; `compile.py` maps to the engine framing; `engine/skeleton/build_camera` executes it | intent -> Blender/compositor camera animation |
| what the renderer can do | `kathaya/renderer/manifest.py` | GENERATED from the renderer's registries (acts, sizes, moves, effects, props, lighting) |
| assets | `kathaya/assets/` | `catalog.py`, `resolver.py`, `references.py`, `builder.py`, `library_env.py`; licences via `engine/licensing/policy.py`; `assets/licenses/ATTRIBUTIONS.md` |
| physical rendering | `engine/skeleton/`, `engine/blender/`, `engine/environments/`, `engine/shorts/` | the existing renderer; the only changes are additive hooks (explicit camera / transition / effects on a beat, fade/dip rendering, `photo_backdrop` family) |
| finishing look | `kathaya/renderer/look.py` | word-highlight captions, amount callouts synced to the spoken word, punch-ins + flash + hit sounds, opening push, hold-shot drift, colour grade; only for plans carrying `plan["look"]` |
| QC | `kathaya/qc/technical.py` + `engine/skeleton/qc_v4.py` (unchanged, still in force) | |
| cache / determinism | `kathaya/cache/keys.py` + the renderer's content-addressed frame / audio / TTS caches | plan hash, visual hashes, asset hashes, catalog hash, renderer version |
| orchestration | `kathaya/pipeline.py` (project folder + state machine), `engine/studio/worker.py` (kplan / kbuild / krender jobs), `engine/studio/kserver.py` (API) | |
| UI | `engine/studio/web/` | simple flow at `#/`; the previous authoring tools live under `#/dev` (Advanced / Developer) |

The physical renderer was NOT moved into a new `renderer/` tree: doing so would break the existing test-suite and the accepted deterministic films. `kathaya/renderer/` is the boundary object (manifest + compiler); the engine stays where it is.

## Schemas (`kathaya/schemas/*.schema.json`, JSON Schema 2020-12)

`NarrationTimeline` · `VisualScenePlan` · `CapabilityManifest` · `AssetCatalog` · `AssetRequest`.

## Principles enforced in code

* The narration is the spine: visual boundaries are the narration's; a segment gets 1-3 visuals only because its length needs them; the director never writes times.
* Nothing is force-fitted. A landmark the catalog does not have is `MISSING` + `AssetRequest` (reference queries, `human_approval_required: true`); a generic bank offered for a real landmark, or a bank at night, is `UNSUPPORTED`. The legacy `LOC.resolve` would silently move a bank to daytime; the new pipeline refuses.
* An action / camera move / effect / transition the renderer does not have (`OTHER`, tilt, orbit, ...) is a structured `capability_error`. The only explicit escape is the user's own substitution, recorded as `SUBSTITUTED`.
* The renderer never reads the story: the compiler works from tables; the story graph it feeds the engine is built from the plan, not from text.
* A reference image is only a reference. Only accepted licences may become a production asset; attribution is written to `assets/licenses/ATTRIBUTIONS.md`.

## How the director is made reliable (local LLM)

The plan is written one visual at a time. The LLM decides everything creative; the system narrows each step's menu to what is *legally possible next* (the renderer's action state, unused `once` actions, a valid framing that differs from the previous shot, a partner only if the cast has one, variety of action / size / movement). `OTHER` is always allowed. A deliberate `moved` flag keeps place and time constant unless the director says the story moves.

## Evidence (all produced by running the system; see the JSON files in this folder)

* `ACCEPTANCE_RESULT.json` - the lottery story through the API exactly as the UI sends it: Chatterbox TTS timeline -> local LLM director -> resolver (2 assets available, 0 new required, 0 capability errors) -> 9:16 1080x1920 30 fps film (26.8 s), technical QC 15/15, engine QC 30/30. Contact sheet: `screens/acceptance_contact_sheet.png`; the money counter ends on the narrated amount: `screens/acceptance_money_counter_12500.png`.
* `ASSET_FLOW_RESULT.json` + `screens/04-06` - a landmark the catalog does not have (BSE, Gateway of India) -> MISSING + AssetRequest -> Wikimedia Commons references (licence-classified) -> user approval -> asset built -> registered -> rendered.
* Legacy deterministic renderer: `python3 studio.py --production-acceptance` -> ACCEPTED (`docs/production/ACCEPTANCE.json`; only the timings differ from the previous accepted run).

## Visual critique of the first accepted film, and what was changed (measured on the same story)

Found by looking at the frames: captions small, plain white, mid-frame; the number that carries the story ("25 lakh") never appeared on screen; the opening 3 s was a static wide shot; the grade was flat and muddy.
Changed (all in `kathaya/renderer/look.py`, deterministic, Kathaya plans only): 3-word captions at 92 px with the spoken word highlighted; the amounts the narration says pop up at the moment they are spoken (digits copied from the narration, never invented) with a low hit; punch-in + flash when the phone lights up and on the realisation; the film opens from a tighter frame with a whoosh; hold shots drift 5 %; contrast / colour / vignette grade.
Tried and reverted: rewriting the director prompt to demand a close-up hook and a visible message. The local 14B model produced a worse plan (repeated REALIZE, READ_DOCUMENT for a phone message, no message insert), so the hook is delivered by the finishing layer, not by asking the model. Not solved: the character stays seated in one pose, the room never changes, the phone-alert shot still shows a face rather than the message.

## Known limits

* The renderer is natively 9:16; long-form is the 9:16 master plus a 16:9 pillarbox export, not a re-framed 16:9 render.
* `photo_backdrop` environments are a stylised single-plane backdrop (Ink image layer + ground plane), not 3D geometry.
* Camera tilt / orbit / over-the-shoulder are not executable by the renderer and are reported as capability errors.
* The protagonist is always on set; the action vocabulary is the renderer's 36 dramatic acts, which bounds creative variety.
* Audio + text timing is silence-snapped, not forced alignment. TTS is Hindi only.
* The ChatGPT provider is copy / paste (tested with scripted replies); there is no OpenAI API provider.
* Local-LLM (qwen3:14b) planning takes minutes on a cold cache; replies are cached, so repeats are seconds.
