# Grease Pencil layer (real Blender GP)

The designed art (SVG cast, sets, props) is composited in 2D; the **hand-drawn, living layer on top of it is rendered by
Blender's Grease Pencil** (Blender 5.2, GPv3), then tracked to the action by the compositor.

```
engine/shorts/gp_strokes.py     stroke DESIGN (pure Python: rays, arcs, ticks, worry marks, moon hatch, ring) - seeded takes
engine/render/gp_bank_blender.py  blender -b -P ... : builds a real GP object per sprite/variant (layer, frame, strokes with
                                  per-point radius/opacity, GP material), adds GP modifiers, renders transparent RGBA PNGs
engine/shorts/gp_bank.py        builds the bank once (cached by content hash in output/cache/gp/<hash>), loads sprites,
                                additive blend + anchor/camera tracking at 30 fps, boil playback at 8 fps
engine/shorts/story.py          decides WHEN and WHERE each effect plays (light event, hand at phone, temple, message banner)
```
GP features actually used: GP objects/layers/frames/strokes, materials (flat, unlit), **Noise modifier** (hand wobble per take),
**Build modifier** (the ring around the sender draws itself on - one drawing, animated by frame), orthographic transparent render.
Sprites are 'takes' of the same drawing: cycling 8 takes at 8 fps gives the line-boil; positions are recomputed every frame from the
live anchors (nightstand phone, gripped phone, eyes) and the camera, so strokes stay glued to moving things.

Gotchas (Blender 5.2): a new GP material has `show_stroke=False` (renders black/nothing) - set it True; drop GP's default 'Black'
material slot; set `layer.use_lights=False` for flat ink; `film_transparent=True` + PNG RGBA for compositing.

Add an effect: write a generator in `gp_strokes.py` (returns strokes in local px), register it in `SPRITES`, and call
`bank.draw(canvas, name, t, screen_xy, scale, opacity)` from the story compiler (any anchor + `gp_bank.screen_of(cam, par, world_pt)`).
If Blender is missing the pipeline falls back to the procedural `ink_fx.py` strokes and the QC check
`grease_pencil_layer_rendered_by_blender` FAILS, so a fallback is never mistaken for the real thing.

# Timing log
Every run writes `timing_log.json` next to the video (stage seconds and %, frames, s/frame, realtime ratio, per-shot render cost)
and appends a line to `output/run_history.jsonl` (with git commit) so runs can be compared over time. Stages: plan (LLMs), voice
(TTS + alignment; 'cached' flag), retime, compile (incl. GP bank build vs cache hit), render, qc + reports.
