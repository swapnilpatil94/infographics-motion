# KATHAAYA Mythology Mode

## What this change adds

- A separate `mythology_ink` creative profile in `kathaya/styles.py`.
- Profile-specific direction is passed into the existing KATHAAYA scene planner by `kathaya/pipeline.py`; the default `kathaya_default` behavior remains unchanged.
- A first source-aware Hindi pilot script at `stories/mythology/draupadi_court_question.md`.
- Unit tests for profile lookup, direction composition and pipeline style validation.

## Important implementation boundary

This is a **creative-planning profile**, not a finished mythology renderer or a completed episode. It does not create missing art assets or add animation capabilities. The existing manifest and catalog remain authoritative: missing period costumes, characters, court environments, divine effects or actions must be reported through the existing asset workflow rather than silently substituted.

The profile is not yet exposed as a choice in the separate legacy `engine/studio/web` UI, whose request path uses the older skeleton-production pipeline. Do not add `mythology_ink` to that UI until it is routed to the KATHAAYA pipeline or the legacy renderer has explicit, tested support for it. This prevents a style selector from promising visuals the renderer cannot produce.

## Pilot acceptance criteria

Before calling a rendered episode production-ready:
1. Build the narration timeline from the pilot script.
2. Generate and inspect the resolved visual plan and all asset/capability requests.
3. Build/approve genuinely appropriate assets where needed; do not substitute unrelated assets.
4. Render a full episode and inspect frames at the hook, every major beat, climax and final seconds.
5. Run the existing technical QC and regression tests.
6. Have a human reviewer confirm source-aware framing and visual coherence.

## Editorial note

The pilot frames Draupadi's question as a question about power, responsibility and justice. It avoids presenting one version-specific supernatural detail as universal. Review narration against the chosen Mahabharata edition/translation before publishing.
