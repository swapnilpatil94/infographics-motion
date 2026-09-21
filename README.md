# Kathaaya Studio - story to cinematic 2.5D Short

Give it a **story (Hindi narration text)** - optionally with your own narration audio - and it produces a finished **9:16 vertical Short (1080x1920, 30 fps)** with a voice, music/foley, captions, camera work and quality checks. Everything is drawn by code (Blender + a 2D/2.5D compositor); no stock footage, no image-generation model in the render path.

```
Narration (text | audio | timing JSON)
  -> NarrationTimeline            the temporal spine (start/end of every narration segment)
  -> Creative Director            local LLM (qwen3:14b via Ollama)  OR  ChatGPT by copy / paste
  -> VisualScenePlan              location, characters, props, action, emotion, camera, transition per visual
  -> Capability + Asset Resolver  every requirement is AVAILABLE | UNSUPPORTED | MISSING (structured errors, no silent substitution)
  -> [human approval, ONLY when a NEW asset is needed]  licence-classified references -> approve -> build
  -> Compiler                     pure table transformation onto the renderer
  -> Deterministic renderer       Blender rig + 2.5D compositor + audio director + frame cache
  -> Finishing look               word-highlight captions, amount callouts, punch-ins, grade
  -> QC (technical 15 checks + engine 30 checks) -> final.mp4
```

Everything below was run on **one machine** (see "Tested environment"). Nothing here is claimed for other machines.

---------------------------------------------------------------------------------------------------

## 1. Tested environment and model versions

| component | version actually used | what it is for |
|---|---|---|
| Machine | Apple M4 Pro, 24 GB RAM, macOS 27.0 | Blender runs on the CPU; a 26 s Short renders in ~4-5 min (cached frames) |
| Python | **3.12.0** (`.venv`, pyenv) | the whole system |
| Blender | **5.2.2 LTS**, at `/Applications/Blender.app` (override with env `BLENDER=/path/to/Blender`) | armature-driven character rendering, Grease Pencil effects |
| ffmpeg | **8.1.2** | encoding (libx264, AAC), stills, previews |
| Ollama | **0.30.10** | serves the local LLMs |
| **Creative-director LLM** | **`qwen3:14b`** (9.3 GB) through Ollama, schema-constrained JSON, `temperature 0`, `seed 7`, replies cached by prompt hash in `output/kathaya/llm_cache` | Kathaya's default director (one visual per call) and the topic-story customiser |
| VLM critic (advisory) | `qwen3.5:9b` (6.6 GB) through Ollama | optional second opinion on preview stills; never blocks a film |
| Studio "regenerate a segment" | first available of `qwen3:14b`, `qwen3.5:9b`, `gemma4:12b-mlx` | UI convenience |
| **Text-to-speech** | **Chatterbox Multilingual (Hindi)**: Python package **`chatterbox-tts 0.1.7`**, checkpoint `ResembleAI/chatterbox` (`t3_mtl23ls_v2.safetensors`, `s3gen.pt`, `ve.pt`), voice-cloned from a reference WAV. *It is not "Chatterbox v3" - those are the package and checkpoint file names found on this machine.* | narration when you supply text only |
| Forced alignment | `whisperx 3.8.2` (wav2vec2 Hindi model `theainerd/Wav2Vec2-large-xlsr-hindi`) | word start/end times against the known script |
| Other libs | torch 2.6.0, numpy 1.26.4, opencv 4.14, Pillow 12.3, scipy 1.15.3, fastapi 0.115, uvicorn 0.41, jsonschema 4.26 | see `requirements.txt` |

**TTS runs through a sibling project.** `engine/shorts/voice.py` calls `~/mythic-video-studio/tools/chatterbox_tts.py` and `tools/whisper_align.py` and the reference voice `~/mythic-video-studio/assets/reference-voices/hindi-male-narrator.wav` with the Python given by `TTS_PYTHON` (default `~/.pyenv/versions/3.12.0/bin/python`). Override with the env vars `MYTHIC_STUDIO_DIR`, `TTS_PYTHON`, `TTS_REFERENCE_AUDIO`. A working scipy wheel is placed first on `PYTHONPATH` from `.vendor_py/` (`pip install --target .vendor_py scipy`; git-ignored) because this machine's shared scipy cannot `dlopen` some extensions. If the Chatterbox stack is missing, the legacy path falls back to macOS `say` with estimated word timing and **flags it in the result**; the Kathaya UI offers **"Estimated (no voice yet)"** which never synthesises.

## 2. Install

```bash
git clone git@github.com:swapnilpatil94/infographics-motion.git
cd infographics-motion
git checkout cinematic-shorts-engine

python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt

brew install ffmpeg ollama            # ffmpeg >= 8, ollama
# Blender 5.2 LTS from blender.org -> /Applications/Blender.app
ollama serve &                         # if it is not already running
ollama pull qwen3:14b                  # the creative director
ollama pull qwen3.5:9b                 # optional: advisory VLM critic
```

Narration (only needed when you give text without audio): set up `~/mythic-video-studio` with the Chatterbox multilingual checkpoint and a Hindi reference voice (see section 1). Without it use "Estimated" timing or supply your own audio / timing JSON.

## 3. Run it

### The UI (recommended)

```bash
python3 studio.py --ui                 # http://127.0.0.1:8765
```

The home page is deliberately minimal: **story / narration text**, optional **narration audio**, **Shorts | Long-form**, style **Kathaaya default**, **GENERATE**. Everything else is under **Advanced / Developer** (`#/dev`: the older authoring tools - script review, per-shot inspector, ChatGPT prompt pages). A project goes through `created -> planning -> (needs_assets | blocked | awaiting_chatgpt) -> ready -> rendering -> completed`, with real progress events (Blender frames, compositing, QC). Only when a **new asset is required** does the UI stop and ask you to approve a reference.

### The CLI (every legacy command still works)

| command | what it does |
|---|---|
| `python3 studio.py --ui [--port N]` | Kathaaya Studio web UI + API |
| `python3 studio.py --production stories/<n>/story.md --narration-json stories/<n>/segments.json` | story.md + narration JSON -> finished Short (parse -> plan -> render -> audio -> QC + auto-fix) |
| `python3 studio.py --production-acceptance` | 3 stories end-to-end + determinism + caching + failure modes + 24-situation matrix + regression + unit tests (~50 min) |
| `python3 studio.py --skeleton-topic "<topic>" [--draft] [--no-llm]` | the system writes a scam-awareness story from a topic, voices it, directs it, critiques its own stills, renders |
| `python3 studio.py --make "<topic>"` / `--brief briefs/x.md` | the earlier 2D planner pipeline |
| `python3 studio.py --api-request request.json` | the factory API a UI would call |

Kathaya acceptance (needs a running Studio server):

```bash
.venv/bin/python -m engine.studio.server --port 8791 --test-mode &
.venv/bin/python tools/kathaya_acceptance.py --port 8791      # lottery story -> 9:16 Short + QC; writes docs/kathaya/ACCEPTANCE_RESULT.json
.venv/bin/python -W ignore -m unittest discover -s tests       # 275 tests
```

Outputs: `output/kathaya/projects/<id>/` (timeline, visual plan, report, asset requests), `output/studio/productions/<job>/final.mp4` (+ poster, contact sheet, QC and audio reports, event log). Everything under `output/` is git-ignored and re-creatable.

### Kathaya HTTP API (what the UI calls)

`POST /api/k/project {text, format: "short"|"long", style, audio_upload?, timing_json?, provider: "ollama"|"chatgpt", narration_mode: "auto"|"estimated"}` -> `{project_id, job_id}`; `GET /api/k/project/{id}`; `POST .../render`; `GET .../chatgpt_prompt`; `POST .../chatgpt_reply {reply}`; `POST .../request/{rid}/references | approve | substitute`; `GET /api/k/manifest` (what the renderer can do), `GET /api/k/catalog` (which assets exist). Progress: `GET /api/production/{job_id}/events` (SSE).

## 4. How the input should be written

### 4.1 Story / narration text (the only required input)

* **Language: Hindi (Devanagari).** TTS and alignment are Hindi only. Hinglish words in Devanagari (`मैसेज`, `लॉटरी`) are fine.
* **One idea per line.** The text is split into narration segments at line breaks, at sentence ends (`।` `.` `?` `!`) and at dashes (`—`). Fragments under 2 words are joined to the previous segment. Each segment becomes 1-3 visuals depending on how long it is spoken (0.9 s minimum, 6 s maximum per visual; a Short's first visual is capped at 4.5 s).
* **Numbers as digits are fine** (`25 लाख`, `12,500`, `₹5000`): they are converted to spoken Devanagari words for the voice, and the same digits are shown on screen when the narrator says them.
* **Say where and when it happens.** The director places the scene from the narration: name the place (`बैंक`, `ATM`, `दुकान`, `कमरे में`) and the time (`रात`, `सुबह`) when it matters. If you say nothing, the previous place and time carry on (the story does not move unless the narration moves).
* **Quote messages exactly.** A phone message / sign shown on screen uses the words from your narration.
* **One protagonist** (the person things happen to), at most **one partner** and **two extras**. Refer to them consistently.
* **Length:** a Short should be **<= 60 s** of speech (about 100-140 Hindi words). Longer input gives a warning and should use Long-form.

Good:

```
एक लड़के के फोन पर अचानक एक मैसेज आया —
'आपने 25 लाख रुपये की लॉटरी जीती है।'
वह हैरान रह गया।
मैसेज में लिखा था कि इनाम लेने के लिए सिर्फ 12,500 रुपये की फीस भरनी होगी।
उसने पैसे भेज दिए।
कुछ मिनट बाद नंबर बंद हो गया।
तभी उसे समझ आया —
लॉटरी जीती ही नहीं थी।
उसका लालच ही उसका सबसे बड़ा जाल बन गया था।
```

Weak: one long paragraph with no line breaks; English-only text; a story that needs a place the catalog does not have and never names it; a story with five main characters.

### 4.2 Optional narration audio

Upload a WAV/MP3 **together with the text** (the text is required: the visuals follow the words). Timing is taken from silences in your audio snapped to the text segments (this is **not** forced alignment). If you want exact word timing, supply a timing JSON.

### 4.3 Optional timing JSON (exact times from your own TTS / editor)

```json
{
  "audio": "path/to/narration.wav",
  "narration": [
    {"id": "n01", "start": 0.26, "end": 2.95, "text": "एक लड़के के फोन पर अचानक एक मैसेज आया",
     "words": [{"word": "एक", "start": 0.26, "end": 0.44}, {"word": "लड़के", "start": 0.48, "end": 0.84}]},
    {"id": "n02", "start": 3.21, "end": 5.87, "text": "आपने 25 लाख रुपये की लॉटरी जीती है।"}
  ]
}
```

`narration` (or the legacy key `segments`, or a bare list) with `text`, `start`, `end` per segment; `words` optional (used for caption highlighting and to time the amount pop-ups; without it they are spread by word length). Times are seconds; the film's length follows the last `end`.

### 4.3b Optional scene direction (home page, under the story)

Free text, in your own words: where and when each part happens, who is on screen, the action, the camera or the mood. It goes into the director's prompt (both the local LLM and the ChatGPT copy/paste prompt) with the rule *follow it where it names a place, time, character, action, emotion or camera; where it is silent decide yourself; a place the catalog lacks is reported, never approximated*. The resolver still enforces what the renderer can do, so direction can steer but never force an impossible shot.

```
Scene 1 - bedroom, night. Rohan (a young man) sits on his bed. The phone rings; he picks it up, worried. Slow push-ins, close shots on his face.
Scene 2 - show the phone screen full-screen with the debit alert (sender BK-ALERT): the money leaving his account.
Scene 3 - ATM, night. He rushes to the ATM and checks the balance; shock.
Scene 4 - bank, next morning (daylight). A bank employee explains to him, two-shot; he understands.
Scene 5 - cyber cell / police station, day. He files the complaint (the form in his hands).
Finish on a calm wide shot with the warm light returning.
```

A complete worked example (story, scene direction, and the ChatGPT-format director reply) is in `stories/kathaya/otp_scam_four_places/`. Its result - 44.7 s, four environments (bedroom night -> ATM night -> bank day -> police day), two characters, technical QC 15/15 and renderer QC 30/30, driven entirely through the UI - is recorded in `docs/kathaya/UI_MULTI_ENV_RESULT.json`.

### 4.4 Timing sources, in the order they are used

1. timing JSON -> 2. audio + text -> 3. Chatterbox TTS from text -> (choose "Estimated" for a silent draft from word counts).
No scene duration is ever hardcoded: visual boundaries come from the narration.

### 4.5 Legacy production input (`--production`)

`stories/production/<name>/story.md` (front matter: `# title`, `protagonist: रोहन, male, young man`, `other: दोस्त, friend`, `sender: VIP-GROUP`, `amount: 100000`) + `segments.json` (`{"segments":[{id,text,start,end,words[]}], "audio": "paced.wav"}`). Examples: `stories/production/a_whatsapp_investment`, `b_lottery_fee`, `c_atm_helper`. Briefs (`briefs/*.md`: `title, premise, protagonist, location: night_bedroom, ladder, mood, message`) feed the older `--brief` path.

## 5. What is available (generated from the renderer itself: `GET /api/k/manifest`)

Anything outside these lists is **not silently approximated**: it becomes a structured `capability_error` or a `MISSING` asset request.

### Environments (12 built-in, drawn in code) - and which times of day exist

| id | subjects it answers to | times |
|---|---|---|
| `env_bedroom` | bed room, bedroom | night, day |
| `env_study` | study, study room | night, day |
| `env_living_room` | living room, drawing room, hall | day, night |
| `env_office` | office, workplace | day |
| `env_classroom` | classroom | day |
| `env_cafe` | cafe, restaurant, tea shop | day, night |
| `env_bank` | bank, bank branch, bank counter | day |
| `env_shop` | shop, store | day, night |
| `env_police` | police station, cyber cell | day, night |
| `env_atm` | ATM, ATM booth, cash machine | night, day |
| `env_call_center` | call center | day, night |
| `env_street` | street, lane, road | day, dusk, night |

Library environments built by the asset builder from approved references (2 so far): `env_lib_bombay_stock_exchange_mumbai` (CC BY 4.0) and `env_lib_gateway_of_india_mumbai` (CC BY-SA 4.0); attribution in `assets/licenses/ATTRIBUTIONS.md`. **A bank at night is UNSUPPORTED** (the bank only exists by day) and a generic bank offered for a real landmark is refused - the plan is blocked with an explanation instead of quietly changing the time.

### Characters (15 archetypes, Open Peeps CC0 art on Kathaya's own rig)

`young man` · `young woman` · `middle-aged man` · `middle-aged woman` · `older man` · `older woman` · `student` · `teacher` · `office worker` · `bank employee` · `customer` · `shopkeeper` · `delivery worker` · `security guard` · `parent`.
Cast limit per film: **1 protagonist + 1 partner + 2 extras.** The protagonist is always on set. Emotions: `anger, confusion, fear, hope, neutral, realization, relief, sadness, suspicion`. If no archetype fits, the director answers `OTHER` and you get an asset request, not a wrong person.

### Props (12)

`atm` · `bag` · `card` · `cup` · `document` · `door` · `food` · `keyboard` · `laptop` · `money` · `pen` · `phone`.

### Actions (the renderer's 36 dramatic acts; the director may only choose ones the current state allows)

Opening: `ESTABLISH`, `ARRIVE`. Phone: `PHONE_ALERT`, `LOOK_AT_PHONE`, `REACH_PHONE`, `PICK_UP`, `TAKE_PHONE`, `READ_MESSAGE`, `PHONE_CALL`, `INSERT_SCREEN` (full-screen message with sender + exact text). Reaction: `EYES_CHANGE`, `REALIZE`, `CLOSE_UP`, `SUSPECT`, `OBSERVE`, `BOTH_REALIZE`, `OTHER_REACTS`. Movement: `STAND_UP`, `SIT_DOWN`, `WALK_ACROSS`, `RUN_AWAY`, `PERSON_ENTERS`, `MEET`. People: `EYE_CONTACT`, `CONVERSE`, `OTHER_LOOKS_AT_PHONE`, `HAND_OVER`, `GIVE_OBJECT`, `RECEIVE_OBJECT`. Money / work: `COUNT_MONEY`, `USE_ATM`, `READ_DOCUMENT`, `TYPE_LAPTOP`, `VISUALIZE_FLOW` (animated money-flow infographic, `params: {amount, from_label, to[]}`), `CROWD_WATCH`. Ending: `RESOLVE` (always last; `ESTABLISH`/`ARRIVE` always first). Some acts are once-only (`PHONE_ALERT`, `PICK_UP`, `HAND_OVER`, ...) and some need a state (a phone cannot be handed over before it is held).

### Camera (chosen by intent, executed by the engine)

* **Shots** (zoom): `wide` 1.0 · `wide2` 1.06 · `reveal` 1.12 · `full` 1.2 · `two` 1.34 · `two_reach` 1.5 · `medium` 1.75 · `close` 2.5.
* **Movements:** `hold`, `push`, `pull`, `drift`, `track`, `truck` (lateral parallax = a pan in 2.5D), `reveal`, `rack_focus`, `isolate`, `dolly_through`.
* **Subjects / framings that exist:** environment/wide · protagonist_full/full · protagonist_head/close+medium · protagonist_phone/close · protagonist_reach/two_reach · partner_head/close+medium · two_shot/two+two_reach+reveal · protagonist_at_atm/two_reach.
* **Not available (reported as capability errors, never faked):** tilt, orbit, over-the-shoulder, extreme close-up, handheld chase.
* **Transitions:** `cut`, `fade`, `dip` (the first shot always fades in).
* **Effects (Grease Pencil):** `arcs@phone_free` (vibrating phone), `arrow@phone`, `rays@lamp`, `rays@phone`, `ring@ui`, `scribble@head`, `ticks@eyes`, `worry@temple`.
* **Lighting:** times `day | dusk | night`; moods `bright, dim, fear, formal, isolated, neutral, pressure, relief, warm`.

### The finishing look (`kathaya/renderer/look.py`)

3-word Devanagari captions at 92 px with the spoken word highlighted (amounts in green); amounts the narration says pop up as `₹25 लाख` / `₹12,500` at the moment they are spoken (digits copied from the narration, never invented) with a low hit; punch-in + flash when the phone lights up and on the realisation; the film opens from a tighter frame with a whoosh; hold shots drift 5%; contrast / colour / vignette grade. Only plans that carry `plan["look"]` get it - legacy films are byte-identical.

## 6. How to choose different environments

The system chooses the environment **from your narration** and checks it against the catalog. You steer it in these ways, from simplest to most manual:

1. **Name the place in the narration.** `बैंक की लाइन में`, `ATM पर`, `पुलिस स्टेशन`, `कैफे में`. The director maps it to the catalog (`env_bank`, `env_atm`, `env_police`, `env_cafe`). Say the time too (`रात`, `सुबह`) - and remember `bank`, `office` and `classroom` exist only by day.
2. **Change of place = say it moved.** The director keeps the previous place and time unless the narration clearly moves the story (`अगले दिन बैंक पहुँचा`).
3. **Use ChatGPT as the director** (home page -> *Advanced / Developer* -> *Creative director = ChatGPT (copy / paste)*, or `provider: "chatgpt"` in the API). The UI gives you a strict copy-paste prompt containing the narration timeline, the capability manifest and the asset catalog; paste ChatGPT's JSON reply back. In that JSON you can set each visual's environment explicitly, for example `"environment": {"type": "generic", "subject": "bank", "asset_id": "env_bank", "time_of_day": "day"}`. The reply is validated against the `VisualScenePlan` schema and the resolver; an invalid choice is returned as a structured error, not rendered.
4. **A place the catalog does not have** (a real landmark, a railway station, a temple, a specific brand's branch): the plan stops with `MISSING` and an **AssetRequest** (reference queries, `human_approval_required: true`). In the UI: *Find references* (Wikimedia Commons, licence-classified) -> choose one with an accepted licence -> *Approve* -> the builder stylises it into a library environment (`assets/library/kathaya/`), registers it, and the film renders with it. Accepted licences: CC0 / public domain, CC BY (3.0, 4.0) and CC BY-SA 4.0 (attribution + share-alike recorded); non-commercial / no-derivatives terms are rejected and anything not on the accept list (for example CC BY-SA 3.0, Free Art Licence) is quarantined and cannot become a production asset. **A reference image is only a reference** - it is never used as-is.
5. **Accept an existing asset instead** (*substitute*): you explicitly say "use `env_street` for this". It is recorded as `SUBSTITUTED` in the report - it is never automatic.
6. **Legacy production mode:** `location:` in a brief (for example `night_bedroom`) or the per-beat location editor under Advanced / Developer.

Real brands and logos (a bank's actual logo, a payments app) are **not** generated: the system uses generic props and fictional sender names. A reference for a real building becomes a stylised backdrop, not a trademark asset.

## 7. Repository map

```
studio.py                     CLI entry (legacy commands + --ui)
kathaya/                      the new pipeline
  schemas/                    NarrationTimeline, VisualScenePlan, CapabilityManifest, AssetCatalog, AssetRequest (JSON Schema 2020-12; python -m kathaya.schemas rewrites the .json files)
  story/                      narration.py (timing JSON / audio+text / TTS / estimate), hindi.py (numerals -> spoken words)
  director/                   prompt.py (ChatGPT prompt), providers.py (Ollama, paste), sequential.py (one visual per LLM call, legal menus), visual_planner.py (validation, correction, hashes)
  assets/                     catalog.py, resolver.py, references.py (Wikimedia + licences), builder.py, library_env.py
  renderer/                   manifest.py (generated capabilities), compile.py (plan -> renderer inputs), look.py (finishing layer)
  qc/technical.py             15 plan/film checks;  cache/keys.py  plan / visual / asset / catalog / renderer hashes
  pipeline.py                 project folder + state machine
engine/                       the deterministic renderer and legacy factory (skeleton rig, Blender jobs, 2.5D compositor, audio director, qc_v4, studio server + web UI)
assets/                       Open Peeps art, Kathaya library assets, licence registry + ATTRIBUTIONS.md
stories/  briefs/  narration/ example inputs;   tests/  270 tests;   tools/ acceptance + evidence scripts
docs/kathaya/                 ARCHITECTURE.md, ACCEPTANCE_RESULT.json, ASSET_FLOW_RESULT.json, screens/
docs/production, docs/studio  the accepted legacy production factory and Studio UI evidence
```

More: `docs/kathaya/ARCHITECTURE.md` (boundaries, principles, director reliability, evidence, limits), `docs/architecture/CURRENT_ARCHITECTURE.md`, `docs/production/PRODUCTION_FACTORY.md`, `docs/ADDING_CHARACTERS_SETS_PROPS.md`.

## 8. Determinism, caching, QC

* Same inputs -> same film. Cache keys: plan hash, per-visual hashes, asset hashes, catalog hash, renderer version (a hash of the renderer sources). Content-addressed actor-frame cache, audio-mix cache, TTS cache, LLM reply cache.
* Technical QC (15) checks include: no missing or unsupported assets, every cast member has an asset, narration coverage, valid capabilities, visual/narration sync, no broken references, video decodes, audio present and matching the video length, dimensions / fps, no dead frames, no duplicate shots, no slideshow; engine QC v4 (30) checks: captions inside the safe zone and off faces, no black / dead frames, target-driven gaze, no slideshow, audio levels, framing, and more. A film that fails is reported `completed_with_qc_failures`, never silently "done".

## 9. Evidence (from real runs; see `docs/kathaya/`)

* Lottery story (9 lines, TTS timeline 23.8 s): resolver **2 assets available, 0 new required, 0 capability errors** -> 1080x1920, 30 fps, 26.8 s film; **technical QC 15/15, engine QC 30/30**; render ~4.5 min with warm caches. Cold LLM planning of the same story took ~6 min.
* Missing-asset flow with real Wikimedia Commons data (BSE, Gateway of India): request -> references -> approval -> built -> registered -> rendered (`ASSET_FLOW_RESULT.json`, `screens/04-06`).
* Legacy `--production-acceptance`: ACCEPTED.

## 10. Honest limitations

* Tested on one Mac only. Hindi only. Blender renders on CPU.
* The renderer is natively **9:16**. "Long-form" uses the same architecture but is the 9:16 master plus a 16:9 pillarbox export, not a re-framed 16:9 render.
* Variety is bounded by the renderer's vocabulary: 12 environments, 15 archetypes, 36 acts. The protagonist stays on set, usually in one pose family per act; a whole story in one room looks like one room.
* On the four-place OTP story the local 14B director followed the requested places and times, but chose actions loosely (a money-flow infographic before the amount is spoken; narration lines shown as phone messages). The film in `docs/kathaya/UI_MULTI_ENV_RESULT.json` therefore used the ChatGPT copy / paste route with a director reply written by hand (`stories/kathaya/otp_scam_four_places/`). Cold local planning of that story took ~15 min (19 segments).
* The local 14B director is fragile: a small prompt change can change the whole plan (a stricter "hook" prompt made the plan worse and was reverted). ChatGPT-as-director is copy / paste only, tested with scripted replies; there is no OpenAI API provider.
* Audio + text timing is silence-snapped, not forced alignment.
* Library environments from references are stylised **single-plane backdrops**, not 3D.
* Some camera asks cannot be honoured by the geometry (for example a reach framing when the phone is not on a table); the renderer substitutes the nearest framing and the UI lists it under "Camera intents the geometry could not honour".
* Tilt / orbit / over-the-shoulder camera moves do not exist; asking for them is an error, not an approximation.
* "Viral" is not measured: the finishing look follows Shorts conventions but retention has not been tested.

## 11. Licences

No `LICENSE` file has been added yet for the project code - add one before distributing. Art: Open Peeps (CC0). Kathaya environments/props/effects: original work drawn in code. Library environments: per `assets/licenses/ATTRIBUTIONS.md` (CC BY 4.0 / CC BY-SA 4.0 - attribution and share-alike apply to those two backdrops). `assets/licenses/registry.json` records every third-party asset with its URL and hash.
