# Cinematic Shorts engine - architecture (2D/2.5D compositor path)

```
brief / topic  ->  planner (LLMs propose, code disposes)  ->  plan.json (DSL v3, validated)
                     |  fit + capability class + asset_requirements.json
plan.json + real narration (Chatterbox Hindi + whisperx word times, designed pauses)
   ->  film.py (deterministic compiler: acting recipes, shots, light events, sfx)
   ->  render3.py (2.5D layer compositor, light-maps, DOF, ink FX, captions) -> ffmpeg
   ->  qc.py + reports.py (11 base checks + 7 visual-QA checks, contact sheet, timing/asset reports)
```
Commands
- `python3 studio.py --brief briefs/rahul_night_notification.md` - story brief -> finished Short (all artifacts in `output/made/<slug>/`)
- `python3 studio.py --make "<topic>"` - topic -> Short (topic-fit gate, cards for what scenes cannot show)
- `python3 studio.py --from-plan output/made/<slug>/plan.json [--stills 1,2.5]` - re-render a saved plan, no LLM calls
Determinism: frames are pure functions of (plan, timings, t); narration is cached by content hash (`output/voice/<hash>`).

Where things live
| concern | file |
|---|---|
| capability library (closed vocabulary) | `engine/shorts/library.py`, `sets.py`, `topics.py` |
| planner / validator / repair | `engine/shorts/planner.py` |
| acting primitives (freeze, hesitate, glance, look, startle, lean, tremble) | `engine/shorts/performance.py` |
| acting recipes per story role, shots, camera (shake, rack focus) | `engine/shorts/film.py` |
| living-ink FX (line-boil rays, buzz arcs, impact ticks) | `engine/shorts/ink_fx.py` |
| concept cards + icons | `engine/shorts/cards.py`, `asset_pipeline/icons.py` |
| art generators | `asset_pipeline/room_art.py`, `set_art.py`, `cast_builder.py`, `ink.py` |
| license registry | `assets/licenses/registry.json` (`asset_pipeline/register_sets.py`) |

Legacy: the Blender backend (`--visual-test`) and the hand-authored `manifests/shorts_rahul.json` are kept but are not the working path.
