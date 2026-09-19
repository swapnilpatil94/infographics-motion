# Topic coverage and asset strategy

## What the engine can actually support

The renderer is not topic-universal. It is capable only within the vocabulary of its registered assets and procedural visual primitives.

### Strong fit with a small reusable pack

- Money psychology, scams and financial behavior
- Technology and internet mechanisms
- Human behavior and psychology
- Business, power and consumer behavior

These stories can usually be decomposed into recurring humans, rooms, phones, laptops, documents, money, graphs, networks and numbers.

### Works with a dedicated asset pack

- Historical stories
- Mythology and ancient stories
- Science that needs specific physical objects

These require style-consistent characters, environments, props and sometimes maps or artifacts. The planner must request missing assets instead of silently substituting generic ones.

### Diagram-first

Science, statistics and abstract concepts are often better represented by procedural SVG or Manim-style graphics, diagrams, maps, timelines and graphs than by literal cinematic scenes.

## What makes a topic economically useful for the channel

No renderer can guarantee virality. For a scalable Shorts workflow, prefer stories with:

1. a clear curiosity gap;
2. concrete stakes or a surprising number;
3. a mechanism that can be shown visually;
4. a causal chain rather than a list of facts;
5. a human decision or conflict;
6. a reveal or payoff;
7. enough visual beats to change composition every few seconds;
8. reusable assets that can appear in future stories.

These are content-selection criteria, not predictions of views.

## What must be added for a new topic

| Requirement | Reusable? | Examples |
|---|---|---|
| Character archetype | Yes | adult, child, worker, founder |
| Wardrobe | Yes | office, historical, mythological |
| Environment | Yes | bedroom, office, street, temple |
| Prop | Yes | phone, card, cash, laptop, document |
| Specialist prop | Sometimes | machine, artifact, vehicle |
| Diagram primitive | Yes | graph, timeline, map, network |
| FX | Yes | glow, smoke, dust, ink, rain |
| Brand-specific asset | Usually topic-specific | product UI, logo, packaging |
| Historical/mythological figure | Yes within that family | recurring deity, king, hero |

## Asset ingestion contract

Every production asset needs:

- source and URL
- author
- license and license URL
- commercial-use status
- attribution and share-alike requirements
- modification restrictions
- source hash
- local path
- category and style family
- semantic layers
- riggability
- preview

Unknown licensing means quarantine.

## Recommended topic pipeline

topic -> story viability -> visual capability check -> asset gap report -> asset acquisition/normalization -> shot DSL -> deterministic compiler -> render -> QC

A planner should reject a shot when a required visual cannot be produced with registered assets or approved procedural primitives.

## Production-time planning assumptions

These are engineering estimates, not guarantees:

- Existing asset vocabulary: usually one planning/render iteration.
- Five to ten new props: asset acquisition, normalization and testing become the dominant work.
- New environment: requires composition, continuity coordinates, lighting and camera-safe zones in addition to artwork.
- New recurring character: requires semantic layers, rig controls, canonical poses, expressions and continuity tests.
- Specialist historical/mythological pack: expect the largest setup cost because the visual style and provenance must be consistent across many assets.

The engine should therefore optimize for reusable asset families, not one-off topic art.
