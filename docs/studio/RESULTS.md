# Studio UI - test evidence

Every row below is a REAL run through the HTTP API the browser uses (worker subprocess, Blender, ffmpeg, Chatterbox); raw data in `E2E_RESULTS.json`.

| scenario | production | QC | duration | Blender frames rendered / reused | total | notes |
|---|---|---|---|---|---|---|
| accepted_b_lottery_fee | `p_20260920-175240_58a3` | 31/31 | 49.623 s | 0 / 1272 (100.0% reused) | 428.8 s |  |
| accepted_c_atm_helper | `p_20260920-175950_e253` | 31/31 | 53.367 s | 0 / 1601 (100.0% reused) | 578.9 s |  |
| script_mode | `p_20260920-180947_33c5` | 31/31 | 49.623 s | 1272 / 0 (0.0% reused) | 749.2 s | narration cache hit; 16:9 export |
| create_mode | `p_20260920-182217_671f` | 30/31 | 52.7 s | 1380 / 0 (0.0% reused) | 1026.4 s | FAILED: ik_reachable; requested ~55 s; real Chatterbox TTS 262.2 s |
| director_options_calm_nocaptions_music50 | `p_20260920-183924_2029` | 30/30 | 45.466 s | 674 / 508 (43.0% reused) | 563.6 s | director {"pacing": "calm", "captions": false, "audio": {"music": 0.5}}; captions off |
| create_mode_variation_retry | `p_20260920-184105_ce33` | 30/31 | 52.666 s | 1376 / 0 (0.0% reused) | 932.3 s | FAILED: ik_reachable; requested ~55 s |

## Cancel (real Blender render)

```json
{
 "production": "p_20260920-174915_b6c6",
 "status": "cancelled",
 "cancelled_stage": [
  "blender_render"
 ],
 "seconds_to_cancel": 0.12,
 "blender_processes_before": 2,
 "blender_processes_after": 1,
 "has_video": false,
 "last_events": [
  [
   "progress",
   "blender_render"
  ],
  [
   "cancelled",
   "blender_render"
  ],
  [
   "cancelled",
   "job"
  ]
 ],
 "frame_copies_cleaned": true,
 "rendered_when_cancelled": 18,
 "processes_naming_this_production_after": 0,
 "note": "the first run's process count also included the next scenario's Blender; checked separately: 0 processes name the cancelled production after the cancel (pgrep -f <production id>)"
}
```

## Failed render (Blender path missing)

```json
{
 "production": "p_20260920-174914_c77d",
 "status": "failed",
 "error": {
  "stage": "scene_direction",
  "type": "FileNotFoundError",
  "message": "[Errno 2] No such file or directory: '/nonexistent/Blender'",
  "reasons": [],
  "hint": "Blender could not run. Check that Blender is installed at /Applications/Blender.app (or set BLENDER); the Blender log is in the production's work/blender_stdout_live.txt."
 },
 "stages": {
  "story_analysis": "completed",
  "story_graph": "completed",
  "script": "skipped",
  "narration": "skipped",
  "scene_direction": "failed",
  "asset_preparation": "pending",
  "blender_render": "pending",
  "audio": "pending",
  "compositing": "pending",
  "qc": "pending",
  "export": "pending"
 }
}
```

## Production acceptance (`python3 studio.py --production-acceptance`, run after the Studio changes)

* verdict: **ACCEPTED** - stories=ok, determinism=ok, caching=ok, failure_modes=ok, matrix=ok, regression=ok, unit_tests=ok
* stories: A 30/30, B 31/31, C 31/31
* determinism: 2004/2004 sampled frames identical
* caching: camera change 90/1182 frames (all in shot S07); audio change 0 video frames
* regression: original film 52/52
* unit tests: 222 ran, 0 failures, 0 errors
