You are the principal engineer and technical director for this repository.

REPOSITORY:
infographics-motion

MISSION:
Transform this repository into a production-grade, autonomous 2D cutout + 2.5D cinematic storytelling engine.

The final system must allow this workflow:

    STORY.md
    +
    narration.segments.json
    +
    optional project/style configuration
                ↓
        ONE CLI COMMAND / FUTURE UI
                ↓
        STORY UNDERSTANDING
                ↓
        VISUAL DIRECTING
                ↓
        CHARACTER / WORLD / PROP FACTORIES
                ↓
        AUTOMATIC ASSET RESOLUTION
                ↓
        CHARACTER RIGGING
                ↓
        MOTION / ACTING
                ↓
        CAMERA / 2.5D
                ↓
        GREASE PENCIL / PROCEDURAL FX
                ↓
        NARRATION SYNCHRONIZATION
                ↓
        BLENDER RENDER
                ↓
        COMPOSITING
                ↓
        AUTOMATED QC
                ↓
        FINAL CINEMATIC MOVIE

The user should NOT need to manually animate Blender scenes.

The user should NOT need Claude to manually create every future video.

Claude is being used NOW to engineer the reusable factory.

After this system is complete, future video generation must be deterministic and executable locally from the story + narration JSON.

==================================================
1. NON-NEGOTIABLE PRODUCT GOAL
==================================================

This is NOT a one-video project.

Do NOT optimize the code only for the current demo.

Build a reusable cinematic storytelling FACTORY.

The system must eventually support hundreds/thousands of stories with:

- different characters
- different character combinations
- different environments
- different props
- different emotional situations
- different camera language
- different visual treatments
- different pacing
- different lighting
- different Grease Pencil effects
- different compositions
- different story structures

while maintaining a coherent visual identity.

We want:

    SAME ENGINE
    +
    DIFFERENT STORY
    =
    DIFFERENT FILM

Do NOT create a rigid template where every video looks like the previous video.

==================================================
2. FINAL VISUAL DIRECTION
==================================================

Primary rendering style:

    CINEMATIC 2D CUTOUT + 2.5D

NOT:

- slideshow
- static comic panels
- basic infographic animation
- children's cartoon
- generic corporate explainer
- repeated puppet animation
- machine-gun slideshow
- one static character with moving camera

The target feeling is:

    animated documentary
    +
    cinematic storytelling
    +
    illustrated world
    +
    subtle 2.5D depth
    +
    expressive character acting
    +
    intelligent camera
    +
    restrained Grease Pencil accents

The viewer should feel that they are watching a FILM.

==================================================
3. CORE ARCHITECTURE
==================================================

Implement/maintain this architecture:

STORY
 ↓
STORY ANALYZER
 ↓
NARRATIVE DIRECTOR
 ↓
VISUAL DSL
 ↓
CHARACTER FACTORY
 ↓
ENVIRONMENT FACTORY
 ↓
PROP FACTORY
 ↓
CROWD FACTORY
 ↓
MOTION / ACTING ENGINE
 ↓
CAMERA DIRECTOR
 ↓
LIGHTING / ATMOSPHERE
 ↓
GREASE PENCIL / PROCEDURAL FX
 ↓
NARRATION SYNC
 ↓
BLENDER SCENE GENERATION
 ↓
RENDER
 ↓
COMPOSITE
 ↓
QC
 ↓
FINAL VIDEO

Keep the boundaries between these systems clean.

==================================================
4. 2D CHARACTER FACTORY
==================================================

This is one of the most important systems.

Do NOT create individual characters as flat images.

Characters must be modular.

A character should conceptually consist of:

HEAD
HAIR
FACE
EYES
EYEBROWS
MOUTH
NECK
TORSO
UPPER ARM L/R
LOWER ARM L/R
HAND L/R
UPPER LEG L/R
LOWER LEG L/R
FOOT L/R
CLOTHING
ACCESSORIES
PROPS

Every important body component must be independently animatable.

We need reusable character archetypes.

Examples:

- young man
- young woman
- middle-aged man
- middle-aged woman
- elderly man
- elderly woman
- student
- office worker
- banker
- shopkeeper
- police officer
- scammer/call-center agent
- manager
- family member
- customer

Do NOT hardcode these as unique characters.

Create a CHARACTER DNA system.

Example concept:

{
    "gender": "male",
    "age_group": "adult",
    "body_type": "average",
    "head": "head_07",
    "hair": "hair_13",
    "skin": "skin_04",
    "eyes": "eyes_03",
    "clothing": "shirt_08",
    "pants": "pants_04",
    "accessories": ["watch_02"]
}

The system should be able to create many visual combinations from a relatively small curated library.

==================================================
5. CHARACTER ACTING
==================================================

This is CRITICAL.

We currently have a weakness where characters can look like static comic panels.

Fix that fundamentally.

Characters must support:

- idle breathing
- blinking
- eye direction
- eye focus
- head turn
- head tilt
- looking at object
- looking away
- hesitation
- surprise
- fear
- confusion
- curiosity
- suspicion
- realization
- relief
- sadness
- anger
- nervousness
- listening
- talking
- reaching
- grabbing
- holding phone
- reading
- typing
- walking
- sitting
- standing
- turning
- pointing
- gesturing

Actions must be composable.

For example:

    reach_for_phone
    +
    hesitation
    +
    fear

should create a different performance from:

    reach_for_phone
    +
    confidence

Do NOT encode every action as manually authored frame-by-frame animation.

Create a reusable MOTION GRAMMAR.

==================================================
6. MOTION GRAMMAR
==================================================

The visual DSL should say WHAT the character is doing.

It should NOT specify raw Blender keyframes.

BAD:

{
    "frame": 84,
    "rotation": 17.4
}

GOOD:

{
    "character": "rahul",
    "action": "reach_for_phone",
    "emotion": "hesitant",
    "intensity": 0.7
}

The motion engine translates semantic actions into Blender animation.

This is essential for future scalability.

==================================================
7. EYES AND FACE
==================================================

Do NOT leave the face as a fixed image.

Implement reusable facial controls.

At minimum:

- eye direction
- blink
- eyebrow position
- mouth state
- head orientation

Eyes should be capable of looking toward:

- another character
- phone
- laptop
- money
- camera
- environment point

This will dramatically improve perceived intelligence and acting.

==================================================
8. ENVIRONMENT FACTORY
==================================================

Build environments as modular systems.

Initial environment families should include:

- Indian bedroom
- Indian apartment
- office
- bank
- ATM area
- call center
- cafe
- shop
- street
- police station
- generic home
- hospital
- classroom
- shopping environment

Do NOT create one giant flat background.

Break environments into:

- background
- walls
- floor
- windows
- doors
- furniture
- lighting
- foreground elements
- decorative props
- atmospheric layers

Allow procedural variation.

Example:

{
    "environment": "indian_bedroom",
    "variation": {
        "wall": "...",
        "floor": "...",
        "bed": "...",
        "lamp": "...",
        "clutter": 0.35,
        "lighting": "night"
    }
}

==================================================
9. 2.5D DEPTH
==================================================

Every important visual element should be able to exist in depth.

Use:

    X
    Y
    Z
    scale
    rotation
    depth blur
    lighting contribution

Typical layer stack:

foreground
character
foreground props
midground
environment
background
atmosphere

The camera must be able to:

- push in
- pull out
- pan
- tilt
- orbit subtly
- rack focus
- change focal length
- create parallax
- perform motivated handheld movement
- perform dramatic reveal
- isolate a subject
- move through layers

Do NOT make every shot a camera zoom.

Create a camera grammar.

==================================================
10. CAMERA DIRECTOR
==================================================

The camera should respond to narrative intent.

Examples:

fear:
    tighter framing
    reduced visual space
    subtle handheld
    slower movement

realization:
    gradual push-in
    background de-emphasis
    subject isolation

investigation:
    lateral movement
    reveal
    rack focus

scale:
    wide shot
    layered depth
    slow movement

urgency:
    shorter camera transitions
    controlled handheld
    tighter framing

The story director should determine WHY the camera moves.

==================================================
11. GREASE PENCIL
==================================================

Grease Pencil should be used intelligently.

Do NOT turn the entire movie into random sketch animation.

Use Grease Pencil as a cinematic visual language.

Create reusable procedural GP/ink FX such as:

- ink strokes
- arrows
- circles
- underlines
- motion lines
- impact marks
- light rays
- smoke
- dust
- particles
- scribbles
- emphasis strokes
- money-flow lines
- network connections
- tension marks
- phone vibration marks
- attention indicators
- transition strokes

Effects should have semantic triggers.

Examples:

PHONE_RING
    → vibration marks + subtle glow

MONEY_TRANSFER
    → flowing ink/line from account A to B

SCAM_NETWORK
    → expanding network lines

REALIZATION
    → restrained emphasis stroke

FEAR
    → subtle environmental ink disturbance

Do NOT use GP just because it exists.

Every effect should have a visual purpose.

==================================================
12. VISUAL PSYCHOLOGY
==================================================

Create a reusable visual grammar for story emotions.

Examples:

FOMO:
    crowd
    social proof
    increasing movement
    scarcity
    countdown

FEAR:
    tighter framing
    negative space
    reduced movement
    attention isolation

AUTHORITY:
    structured composition
    formal environment
    centered subject

SCARCITY:
    countdown
    disappearing elements
    decreasing space

SUNK COST:
    accumulating objects/numbers
    increasing investment
    eventual collapse

SOCIAL PRESSURE:
    one person
    second person
    crowd
    protagonist follows

Do not turn this into manipulative dark-pattern UI.

This is storytelling grammar.

==================================================
13. PROPS
==================================================

Create a reusable prop factory.

Priority props:

- smartphone
- laptop
- desktop
- tablet
- smartwatch
- headphones
- wallet
- bank card
- cash
- ATM
- QR code
- payment terminal
- receipt
- bill
- cheque
- bank document
- loan document
- EMI document
- investment document
- shopping bags
- boxes
- office objects

Props must support:

- recoloring
- scaling
- screen variation
- position
- rotation
- interaction with characters

Example:

phone:
    incoming_call
    notification
    OTP
    bank_message
    WhatsApp-like message
    payment screen
    scam warning
    lock screen

==================================================
14. CROWD FACTORY
==================================================

We need crowd generation without manually creating hundreds of characters.

Use a limited set of character archetypes and generate variations.

Crowd variation should include:

- character selection
- scale
- position
- depth
- clothing
- color
- pose
- orientation
- animation phase
- silhouette

Background characters can use simplified animation.

Foreground characters get full acting.

==================================================
15. ASSET ACQUISITION
==================================================

Before downloading anything:

1. Inspect the current repository.
2. Inspect current Blender version.
3. Inspect current architecture.
4. Inspect existing assets.
5. Inspect current SVG pipeline.
6. Inspect existing character implementation.
7. Inspect existing motion grammar.
8. Inspect existing QA.

Then research compatible open-source resources.

Prioritize:

- CC0
- MIT
- permissive commercial-use licenses

Potential resources to investigate include:

- MakeHuman / MPFB
- COA Tools 2
- Tiny 2D Rig Tools
- Puppet Mode
- relevant Blender Grease Pencil resources
- suitable CC0 SVG/vector resources

DO NOT blindly install every addon.

For every external resource:

- inspect license
- inspect Blender compatibility
- inspect code quality
- determine whether to use, adapt, or merely study it

Maintain an asset/license registry.

Unknown license = quarantine.

Non-commercial license = reject.

Do not contaminate the core system with incompatible GPL/code dependencies without explicitly checking license compatibility.

==================================================
16. BUILD OUR OWN CANONICAL ASSET LIBRARY
==================================================

Open-source assets are the FOUNDATION.

They are NOT the final visual identity.

Where practical, create our own standardized KATHAAYA-compatible assets from the beginning.

The library must be reusable across thousands of videos.

Organize approximately:

assets/
    characters/
    character_parts/
    heads/
    hair/
    faces/
    eyes/
    mouths/
    hands/
    clothing/
    props/
    environments/
    environment_parts/
    fx/
    typography/
    materials/
    palettes/

Each asset must have metadata.

Example:

{
    "id": "hair_013",
    "type": "hair",
    "style": "short",
    "tags": ["male", "adult", "indian"],
    "license": "CC0",
    "source": "...",
    "sha256": "..."
}

==================================================
17. VISUAL VARIATION ENGINE
==================================================

Create controlled variation, not random chaos.

The engine should be able to vary:

characters
clothing
colors
hair
face
body proportions
props
environment
lighting
camera
composition
depth
FX
motion intensity

Variation must be deterministic from a seed.

Example:

    seed = story_id + shot_id

Same story + same seed:

    identical render

Different seed:

    controlled variation

This is critical for debugging and reproducibility.

==================================================
18. STORY-TO-SHOT SYSTEM
==================================================

A story should be converted into meaningful cinematic beats.

For an 8–12 minute documentary, the system should support:

- cold open
- setup
- context
- character introduction
- escalation
- discovery
- explanation
- psychological mechanism
- money/system visualization
- realization
- consequence
- payoff
- conclusion

Do NOT force every story into the exact same structure.

The director should infer structure from the story.

==================================================
19. SHOT DESIGN
==================================================

Every shot should have semantic intent.

Example:

{
    "shot_id": "S014",
    "purpose": "reveal_the_real_source_of_the_message",
    "emotion": "suspicion",
    "characters": [...],
    "environment": "...",
    "action": [...],
    "camera": "...",
    "lighting": "...",
    "fx": [...],
    "duration": 4.2
}

Every shot should answer:

WHAT should the viewer notice?

WHAT should the viewer feel?

WHAT information changed?

WHAT question is created?

Avoid meaningless shots.

==================================================
20. PACING
==================================================

Do NOT create machine-gun pacing.

Do NOT make every shot 1–2 seconds.

Use different shot durations depending on narrative function.

Example ranges:

HOOK:
    0.8–2.5 sec

TENSION:
    1.5–3.5 sec

ACTION:
    1.5–3 sec

EXPLANATION:
    3–6 sec

EMOTIONAL MOMENT:
    4–8 sec

REVELATION:
    3–7 sec

These are guidelines, not hard rules.

Pacing should be driven by narration and story.

==================================================
21. NARRATION SYNCHRONIZATION
==================================================

Input:

narration.segments.json

The system should understand:

- segment start
- segment end
- text
- sentence boundaries where available

Use narration timing to drive shot timing.

Do not randomly cut visuals every sentence.

Visual transitions should correspond to:

- information change
- emotional change
- action
- reveal
- emphasis

==================================================
22. VISUAL DIVERSITY
==================================================

This is NON-NEGOTIABLE.

Two different stories should NOT automatically produce the same sequence of:

wide
medium
close
wide
medium
close

The director must vary:

- shot scale
- camera movement
- composition
- environment
- lighting
- character blocking
- visual metaphors
- procedural graphics
- GP effects
- pacing

However, maintain KATHAAYA visual identity.

==================================================
23. CINEMATIC QUALITY
==================================================

Implement:

- depth of field
- subtle atmospheric haze
- controlled shadows
- lighting variation
- foreground occlusion
- parallax
- subtle camera shake only when motivated
- compositional framing
- cinematic transitions
- color grading
- controlled grain if useful

Avoid excessive effects.

The goal is premium, restrained, cinematic animation.

==================================================
24. AUTOMATED QUALITY CONTROL
==================================================

The existing QC system must remain important.

Expand it where useful.

Check:

VIDEO:
- render exists
- duration
- resolution
- frame rate
- black/dead frames
- duplicate frames/shots
- frozen character
- missing layers
- missing assets
- watermark detection
- visual discontinuities

AUDIO:
- narration present
- narration sync
- silence at wrong locations
- clipping
- loudness/dynamics
- end-screen silence

STORY:
- all narration covered
- no missing segments
- shot durations valid
- no orphan shots

ASSETS:
- license metadata
- missing assets
- unresolved assets

CONSISTENCY:
- character continuity
- environment continuity
- prop continuity

==================================================
25. DETERMINISTIC RENDERING
==================================================

This is critical.

The final movie must be reproducible from the generated plan.

Support:

    --from-plan plan.json

If the plan already exists:

DO NOT call an LLM.

DO NOT reinterpret the story.

DO NOT randomly change the scene.

Simply render the deterministic plan.

==================================================
26. LLM ROLE
==================================================

LLM is a PLANNER, not the renderer.

LLM may generate:

- story interpretation
- narrative structure
- visual DSL
- character selection
- environment selection
- shot intent
- motion semantics
- camera semantics
- FX semantics

LLM must NOT directly generate arbitrary Blender Python for every shot.

Blender generation must be deterministic from validated structured data.

==================================================
27. FUTURE UI
==================================================

Design the CLI/API so a future UI can simply send:

{
    "story": "...",
    "narration_segments": [...],
    "style": "kathaaya",
    "aspect_ratio": "16:9"
}

The UI should NOT need to know Blender internals.

Future interface:

    STORY TEXT
    NARRATION JSON
    ↓
    CREATE FILM
    ↓
    PLAN
    ↓
    RENDER
    ↓
    QC
    ↓
    MOVIE

The current CLI should be the backend for that future UI.

==================================================
28. CURRENT DEMO REQUIREMENT
==================================================

Do not stop after architecture.

After implementing the system, create ONE COMPLETE REAL FILM.

Choose a story suitable for the current asset library and current engine.

The film must be approximately 8–12 minutes if technically feasible.

It must demonstrate:

- multiple characters
- at least one environment
- multiple environment compositions
- props
- character interaction
- facial acting
- eye direction
- body movement
- camera movement
- 2.5D depth
- parallax
- lighting variation
- Grease Pencil/procedural FX
- narration synchronization
- visual storytelling
- beginning/middle/end
- cinematic pacing

Do not create a benchmark consisting of isolated test shots.

Create an ACTUAL FILM.

==================================================
29. IMPORTANT: DO NOT FAKE COMPLETION
==================================================

Do NOT report:

"implemented"

unless it actually works.

Do NOT create placeholder files and call the feature complete.

Do NOT create fake asset metadata.

Do NOT claim an addon works without testing it.

Do NOT claim a film is complete without rendering it.

If something cannot be implemented correctly:

1. identify the limitation
2. implement the best working fallback
3. document the limitation
4. continue building the system

==================================================
30. PERFORMANCE TARGET
==================================================

The target machine is:

Apple Silicon MacBook Pro
M4 Pro
24 GB RAM
512 GB SSD

The system must be practical locally.

Avoid architectures requiring:

- huge GPU models
- massive texture libraries
- unnecessary 4K intermediates
- hundreds of simultaneous Blender objects when unnecessary
- expensive simulation where procedural approximation is sufficient

Prefer:

- SVG/vector assets
- lightweight meshes
- reusable rigs
- instancing
- procedural generation
- compositing
- 2.5D layers
- deterministic caching
- incremental rendering

==================================================
31. NO MANUAL BLENDER WORK
==================================================

The final production path should NOT require:

- manually opening Blender
- manually importing assets
- manually placing characters
- manually keyframing
- manually drawing Grease Pencil
- manually fixing cameras
- manually rendering

Blender should be treated as the rendering engine.

==================================================
32. FILE/PROJECT ORGANIZATION
==================================================

Create a clean structure similar to:

engine/
    story/
    director/
    dsl/
    characters/
    environments/
    props/
    crowd/
    animation/
    camera/
    lighting/
    fx/
    blender/
    rendering/
    compositing/
    qc/
    assets/
    licensing/

manifests/
    characters/
    environments/
    props/
    capabilities/

assets/
    characters/
    environments/
    props/
    fx/

stories/

plans/

output/

docs/

Do not unnecessarily rewrite stable existing modules.

==================================================
33. IMPORTANT EXISTING WORK
==================================================

Before changing anything, inspect the current repository.

There is existing work around:

- story briefs
- planner story mode
- Hindi narration
- role-table staging
- topic capability registry
- asset requirements
- motion grammar
- camera system
- world system
- SVG character work
- procedural 2D effects
- QC
- consistency checks
- deterministic --from-plan rendering

Preserve good existing work.

Do NOT overwrite newer SVG work with older implementations.

Do NOT blindly merge older experimental architecture.

First understand what exists.

==================================================
34. RESEARCH BEFORE IMPLEMENTATION
==================================================

Inspect these projects for reusable architecture/ideas:

COA Tools 2:
https://github.com/Aodaruma/coa_tools2

Tiny 2D Rig Tools:
https://github.com/NickTiny/Tiny-2D-Rig-Tools

Puppet Mode:
https://github.com/8bitbyadog/puppet-mode

SPA 2D Animation Addon:
https://github.com/The-SPA-Studios/2d-anim-addon

Proscenio:
https://github.com/firebound/proscenio

Skeleton Rig:
https://github.com/frycz/skeleton-rig

MakeHuman:
https://github.com/makehumancommunity/makehuman

MPFB:
https://github.com/makehumancommunity/mpfb2

Study them.

Do not blindly install everything.

Determine:

- Blender compatibility
- license
- architecture
- reusable concepts
- code worth adapting
- code that should only be referenced

==================================================
35. LICENSE POLICY
==================================================

Every external asset/code dependency must be tracked.

Maintain:

assets/licenses.json

with:

{
    "asset_id": "...",
    "source": "...",
    "source_url": "...",
    "author": "...",
    "license": "...",
    "commercial_use": true,
    "attribution_required": false,
    "share_alike": false,
    "modification_allowed": true,
    "proof_url": "...",
    "sha256": "..."
}

Unknown license:

    REJECT / QUARANTINE

Non-commercial:

    REJECT

Do not silently use assets whose license is unclear.

==================================================
36. TEST STRATEGY
==================================================

Create automated tests for:

- character generation
- character variation
- rig creation
- facial controls
- eye targeting
- environment assembly
- prop assembly
- crowd generation
- motion grammar
- camera grammar
- GP FX
- narration synchronization
- DSL validation
- deterministic rendering
- asset licensing
- QC

Also create a small regression scene.

==================================================
37. ACCEPTANCE TEST
==================================================

The project is not complete until this works:

COMMAND:

python3 studio.py \
    --story stories/demo.md \
    --narration narration/demo.json

Expected:

1. analyze story
2. create visual plan
3. resolve characters
4. resolve environments
5. resolve props
6. generate motion
7. generate camera
8. generate FX
9. generate Blender scene
10. render
11. composite
12. run QC
13. produce final movie

Also:

python3 studio.py \
    --from-plan output/.../plan.json

must reproduce the film without an LLM.

==================================================
38. DELIVERABLES
==================================================

At the end provide:

1. Working production engine
2. Reusable asset library
3. Character factory
4. Environment factory
5. Prop factory
6. Crowd factory
7. Motion grammar
8. Camera grammar
9. 2.5D system
10. Grease Pencil/procedural FX system
11. Visual DSL
12. Asset/license registry
13. Automated QC
14. CLI
15. Documentation
16. One complete rendered film
17. Example story
18. Example narration JSON
19. Example generated plan
20. Exact command to reproduce the film

==================================================
39. FINAL ENGINEERING PRINCIPLE
==================================================

Think like a film studio building its own animation engine.

NOT:

"How do I make this one video?"

Instead:

"How do I build the smallest reusable system that can make the next 2,000 videos?"

Every implementation decision must be evaluated against:

    Can this be reused?

    Can this be parameterized?

    Can this be generated automatically?

    Can this be deterministic?

    Can a future story use it without code changes?

    Can the visual result be different from the previous film?

    Can it run locally on the M4 Pro?

==================================================
40. EXECUTION ORDER
==================================================

Do NOT attempt everything chaotically.

Follow this order:

PHASE 1
Inspect repository and current implementation.

PHASE 2
Audit existing architecture and preserve useful work.

PHASE 3
Research compatible open-source systems and licenses.

PHASE 4
Design the canonical asset schema.

PHASE 5
Build/upgrade character factory.

PHASE 6
Build character rig + acting system.

PHASE 7
Build environment factory.

PHASE 8
Build prop/crowd factory.

PHASE 9
Build visual DSL.

PHASE 10
Build motion grammar.

PHASE 11
Build camera/2.5D system.

PHASE 12
Build Grease Pencil/procedural FX layer.

PHASE 13
Connect narration → shot timing.

PHASE 14
Connect everything to deterministic Blender rendering.

PHASE 15
Build QC/regression tests.

PHASE 16
Generate ONE complete real film.

PHASE 17
Render and inspect the actual result.

PHASE 18
Fix the biggest visual weaknesses found in the rendered film.

PHASE 19
Render again.

PHASE 20
Document the final production workflow.

Do not stop after Phase 4.

Do not stop after architecture.

The final proof must be an actual movie.

==================================================
41. ACTUAL ASSET DOWNLOAD + CURATION
==================================================

DO NOT merely research open-source asset repositories.

ACTUALLY DOWNLOAD suitable assets into the project when licensing,
compatibility, and quality permit.

The goal is to bootstrap a real reusable KATHAAYA asset library.

Priority sources should include:

1. CC0 assets
2. MIT/permissive licensed assets
3. Other licenses allowing commercial use and modification,
   only when their obligations can be safely satisfied

Investigate and, where suitable, download from sources such as:

- MakeHuman / MPFB
- COA Tools-compatible assets
- suitable CC0 SVG/vector character libraries
- Open Peeps
- Humaaans
- Kenney
- unDraw
- ManyPixels
- Wikimedia Commons where the individual asset license permits it
- other reputable open-source repositories discovered during research

IMPORTANT:

Do not download entire repositories blindly.

CURATE.

Download only assets that are useful for the KATHAAYA production system.

==================================================
42. INITIAL ASSET LIBRARY TARGET
==================================================

Bootstrap a practical initial library.

Target approximately:

CHARACTERS:
    10–30 usable base character/archetype sources

CHARACTER PARTS:
    10+ heads
    15+ hairstyles
    8+ eye sets
    8+ mouth sets
    10+ clothing tops
    10+ clothing bottoms
    5+ shoes
    10+ accessories
    multiple hand poses

PROPS:
    30–50 useful props

ENVIRONMENTS:
    5–10 usable environment foundations

ENVIRONMENT PARTS:
    walls
    floors
    windows
    doors
    furniture
    lamps
    tables
    chairs
    shelves
    decorative objects

FX:
    useful ink/vector/Grease Pencil references
    particles
    arrows
    lines
    circles
    motion marks
    smoke
    impact effects

Do not blindly chase these numbers.

QUALITY and REUSABILITY matter more than quantity.

==================================================
43. DOWNLOAD PIPELINE
==================================================

Create an automated asset acquisition process.

Conceptually:

    source registry
          ↓
    license verification
          ↓
    download
          ↓
    checksum
          ↓
    normalize
          ↓
    inspect
          ↓
    tag
          ↓
    register
          ↓
    asset library

Create scripts/tools such as:

    tools/assets/discover.py
    tools/assets/download.py
    tools/assets/verify_license.py
    tools/assets/normalize.py
    tools/assets/register.py

Names may differ if the existing architecture has a better location.

The important requirement is the functionality.

==================================================
44. ASSET NORMALIZATION
==================================================

Downloaded assets MUST NOT be directly scattered throughout the
renderer.

Normalize them into our canonical asset format.

For SVG assets:

- normalize dimensions
- normalize coordinate system
- remove unnecessary metadata
- preserve attribution/license information
- validate SVG
- detect unsupported features
- assign semantic tags

For Blender assets:

- inspect scene
- remove unnecessary objects
- normalize scale
- normalize origin
- normalize collections
- normalize materials
- register dependencies

For character assets:

attempt to convert them into modular components where practical.

==================================================
45. LICENSE ENFORCEMENT
==================================================

Every downloaded asset must receive a registry record.

Example:

{
    "id": "character_head_007",
    "source": "OpenPeeps",
    "source_url": "...",
    "download_url": "...",
    "author": "...",
    "license": "CC0",
    "commercial_use": true,
    "attribution_required": false,
    "share_alike": false,
    "modification_allowed": true,
    "downloaded_at": "...",
    "sha256": "...",
    "tags": [
        "head",
        "character",
        "adult",
        "male"
    ]
}

If a source has attribution requirements:

    store the exact attribution text.

If ShareAlike is required:

    flag the asset clearly.

If the license is unclear:

    DO NOT USE IT.

==================================================
46. ASSET VARIATION
==================================================

Do not assume each downloaded asset is one final character.

Where legally and technically permitted, transform assets into reusable
components.

For example:

source character
       ↓
head
hair
eyes
mouth
torso
arms
hands
legs
clothing
accessories

Then combine components to create new characters.

Likewise:

source environment
       ↓
wall
floor
window
door
furniture
lighting
props

Then construct new environments.

The objective is:

    FEW SOURCE ASSETS
          ↓
    MANY COMBINATIONS
          ↓
    MANY FILMS

==================================================
47. ASSET GENERATION FALLBACK
==================================================

If a required asset does not exist in the approved library:

1. search approved sources
2. if not found, generate a procedural asset
3. if procedural generation is insufficient, create a new
   KATHAAYA-native asset
4. register it permanently in the library

Do not block the entire production pipeline because one asset is missing.

==================================================
48. NO RANDOM INTERNET SCRAPING
==================================================

Do not download images from arbitrary Google results,
Pinterest, social media, or unknown websites.

Only use assets where licensing can be established.

Every asset must have provenance.

==================================================
49. ASSET LIBRARY MUST BE REUSABLE
==================================================

The asset library is persistent.

Future stories should query:

    asset registry

before downloading anything new.

Order of resolution:

    existing canonical asset
          ↓
    existing variation
          ↓
    procedural generation
          ↓
    approved external asset
          ↓
    new generated asset

Do not repeatedly download the same asset.

Use SHA256/checksum and semantic IDs to detect duplicates.

==================================================
50. FIRST BUILD MUST PROVE ASSET REUSE
==================================================

For the first complete film, deliberately reuse the asset library.

The film should demonstrate that:

- the same character can perform multiple actions
- the same character can appear in multiple shots
- the same environment can be recomposed
- the same prop can appear in different contexts
- multiple characters can be generated from shared parts
- crowd scenes can reuse character archetypes
- colors/materials can vary
- camera/depth can make the same assets feel different

This is the proof that we are building a FACTORY,
not a one-off animation.


==================================================
START NOW
==================================================

First inspect the repository thoroughly.

Do not ask me to manually explain files that you can inspect yourself.

Make an implementation plan based on the actual current code.

Then implement the system.

Use the existing good work wherever possible.

Do not destroy the current SVG pipeline.

Do not create a one-off demo.

Build the reusable film factory and prove it with one complete movie.

At the end, report:

- what you found
- what you changed
- what you reused
- what open-source components/assets you selected
- their licenses
- what was generated
- exact commands
- test results
- render results
- known limitations
- what remains for the next iteration

Most importantly:

THE SYSTEM, NOT THE DEMO, IS THE PRODUCT.






The future architecture should be- cz we will add ui as well:

┌───────────────────────────────┐
│          KATHAAYA UI           │
│                               │
│  Story                        │
│  Narration JSON               │
│  Style                        │
│  Aspect Ratio                 │
│                               │
│       [ GENERATE FILM ]       │
└───────────────┬───────────────┘
                │
                ↓
        KATHAAYA API/CLI
                │
                ↓
        FILM FACTORY
                │
        ┌───────┴────────┐
        ↓                ↓
    PLAN CACHE       ASSET CACHE
        ↓                ↓
        └───────┬────────┘
                ↓
             BLENDER
                ↓
             RENDER
                ↓
               QC
                ↓
         ┌──────┴───────┐
         ↓              ↓
      16:9 MASTER    9:16 SHORTS