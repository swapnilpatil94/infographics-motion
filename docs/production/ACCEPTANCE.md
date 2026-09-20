# Production acceptance

`python3 studio.py --production-acceptance` — started 2026-09-20 18:03:28, total 2549.2 s

## Verdict

- **stories**: PASS
- **determinism**: PASS
- **caching**: PASS
- **failure_modes**: PASS
- **matrix**: PASS
- **regression**: PASS
- **unit_tests**: PASS
- **ACCEPTED: True**

## Stories (story + narration JSON -> final MP4)

| story | film | QC gates | duration | shots | scenes | QC rounds |
|---|---|---|---|---|---|---|
| A: fake WhatsApp investment group | `output/production/a_whatsapp_investment/final.mp4` | 30/30 PASS | 45.471 s | 19 | [['bedroom', 'night'], ['cafe', 'day']] | 1 |
| B: lottery / prize processing fee | `output/production/b_lottery_fee/final.mp4` | 31/31 PASS | 49.623 s | 19 | [['living_room', 'day'], ['bank', 'day']] | 1 |
| C: ATM 'helper' card swap (new story) | `output/production/c_atm_helper/final.mp4` | 31/31 PASS | 53.371 s | 21 | [['street', 'day'], ['atm', 'day'], ['bank', 'day']] | 1 |

materially different: `{'distinct_act_sequences': True, 'distinct_scene_sets': True, 'act_overlap_A_B': 0.65, 'shot_counts': [19, 19, 21]}`

## determinism

```json
{
 "no_llm_no_parser": true,
 "sampled_frames": 2004,
 "identical_frames": 2004,
 "pixel_identical": true,
 "qc_passed": true,
 "rerender_seconds": 391.7,
 "frame_cache": {
  "frames": 1182,
  "reused": 1182,
  "rendered": 0
 },
 "plan_sha": "075830d9c7d0"
}
```

## caching

```json
{
 "camera": {
  "frames_total": 1182,
  "frames_changed": 90,
  "all_inside_that_shot": true,
  "shot": "S07",
  "shot_frames": 90
 },
 "character": {
  "character": "D (skin changed)",
  "frames_changed": 594,
  "frames_total": 1182,
  "frames_where_D_is_on_set": 594,
  "changed_only_where_D_is_visible": true,
  "first_changed_t": 22.93
 },
 "audio": {
  "video_frames_changed": 0,
  "hash_before": "04ce2bedad803e15",
  "hash_after": "07ca75a1dfea2986",
  "mix_rehash": true
 },
 "story": {
  "deterministic_same_input_same_plan": true,
  "plan_seconds": 0.001
 }
}
```

## failure_modes

```json
{
 "cases": [
  {
   "case": "unsupported_places_no_money_theme",
   "raised": true,
   "type": "StoryNotSupported",
   "reason": "no money / scam / psychology cue anywhere in the script (this factory tells money-psychology stories); places with no stage: ['मंदिर', 'अस्पताल'] (supported: ['"
  },
  {
   "case": "too_few_segments",
   "raised": true,
   "type": "StoryNotSupported",
   "reason": "3 narration segments: a Short needs 8-40; no money / scam / psychology cue anywhere in the script (this factory tells money-psychology stories); places with no "
  },
  {
   "case": "invalid_narration_json",
   "raised": true,
   "type": "NarrationInvalid",
   "reason": "segment 0 lacks 'start'; segment 0 lacks 'end'; segment 1 lacks 'start'; segment 1 lacks 'end'; segment 2 lacks 'start'; segment 2 lacks 'end'"
  },
  {
   "case": "unknown_location",
   "raised": true,
   "type": "LocationUnsupported",
   "reason": "unknown location 'moon_base' (supported: ['bedroom', 'study', 'living_room', 'office', 'classroom', 'cafe', 'bank', 'shop', 'police', 'atm', 'call_center', 'str"
  }
 ],
 "all_fail_clearly": true
}
```

## matrix

```json
{
 "scenarios": 16,
 "distinct_protagonists": 16,
 "distinct_partners": 14,
 "meaningful_situations": 142,
 "locations": [
  "atm",
  "bank",
  "bedroom",
  "cafe",
  "call_center",
  "classroom",
  "living_room",
  "office",
  "police",
  "shop",
  "street",
  "study"
 ],
 "times": [
  "day",
  "dusk",
  "night"
 ],
 "props": [
  "card",
  "document",
  "laptop",
  "money",
  "phone"
 ],
 "emotions": [
  "confusion",
  "fear",
  "hope",
  "neutral",
  "realization",
  "relief",
  "suspicion"
 ],
 "acts": [
  "ARRIVE",
  "BOTH_REALIZE",
  "CLOSE_UP",
  "CONVERSE",
  "COUNT_MONEY",
  "CROWD_WATCH",
  "ESTABLISH",
  "EYE_CONTACT",
  "GIVE_OBJECT",
  "HAND_OVER",
  "LOOK_AT_PHONE",
  "MEET",
  "OBSERVE",
  "OTHER_LOOKS_AT_PHONE",
  "OTHER_REACTS",
  "PERSON_ENTERS",
  "PHONE_ALERT",
  "PHONE_CALL",
  "REACH_PHONE",
  "READ_DOCUMENT",
  "READ_MESSAGE",
  "REALIZE",
  "RECEIVE_OBJECT",
  "RESOLVE",
  "RUN_AWAY",
  "SIT_DOWN",
  "STAND_UP",
  "SUSPECT",
  "TAKE_PHONE",
  "TYPE_LAPTOP",
  "USE_ATM",
  "WALK_ACROSS"
 ],
 "single_person_scenarios": 4,
 "two_person_scenarios": 11,
 "crowd_scenarios": 1,
 "prop_contacts": 42,
 "prop_contacts_bad": 0,
 "unreachable_events": 0,
 "snaps": 0,
 "ghost_actor_scenes": 0,
 "geometry_bad_shots": 0
}
```

## regression_original_film

```json
{
 "film": "output/production/regression_v3/final.mp4",
 "passed": true,
 "gates": "52/52",
 "failed": [],
 "seconds": 438.0
}
```

## unit_tests

```json
{
 "ran": 222,
 "failures": 0,
 "errors": 0,
 "passed": true
}
```
