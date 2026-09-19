# Asset reuse proof

Two different films (different story, protagonist, locations, length) built by the same factory from the same library/code.

* Film A `why_smart_people_v2`: 67 shots, 335s, characters ['office_worker', 'middle_aged_man']
* Film B `reuse_proof` (`stories/reuse_proof_part_time_job.md`, synthetic narration timings, plan + stills only): 17 shots, 113s, characters ['student', 'middle_aged_man']

Components used by B: 15. Shared with A (reused unchanged): **12** (80%). New for B: 3.

## Reused by both
`camera_grammar:intents`, `crowd:crowd_factory`, `gp_effect:arrow`, `gp_effect:rays`, `gp_effect:ring`, `gp_effect:scribble`, `gp_effect:worry`, `lighting:mood_grammar`, `motion_grammar:semantic_actions`, `prop:laptop`, `rig:layered_rig2`, `ui_screen:in_call`

## Only in B
`environment_family:bank_branch`, `environment_family:night_bedroom`, `ui_screen:sms`

Film B's people are new individuals: `dna_d00afb8ea7, dna_785a2563b6` vs A: `dna_0f1023d463, dna_48203fd374` (same rig, same hair/outfit/accessory atoms, different DNA).

Caveat: B's 'bank' location comes from the local LLM reading 'बैंक की स्क्रीन' (a bank *app screen*) as a branch, so the plan renders a branch. Location tagging is a known weakness.
