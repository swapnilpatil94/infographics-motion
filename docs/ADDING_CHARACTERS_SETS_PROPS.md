# Adding characters, sets and props

**Character** (`asset_pipeline/cast_builder.py`): add an entry to `CHARACTERS` (hair, facial hair, accessory atoms from the Open Peeps pack)
and the character id to `library.CAST`; run `PYTHONPATH=. .venv/bin/python asset_pipeline/cast_builder.py`. Every character gets all faces
and all body poses automatically (heads and bodies share one canvas frame). New body pose: add to `BODIES` and to `library.BODIES` with a
one-line description of when to use it.

**Set** (`asset_pipeline/set_art.py`): write a function returning `(set_id, [(layer_name, Ink, {par, depth, emissive?}), ...], order)` with an
`"@char"` slot; end with a foreground occluder (desk/parapet/blanket, top edge above world y~1370, `par` ~1.05-1.1) because the bust bodies
end at y~1390-1420. Register lights in `sets.py` (`SETS[...]["lights"]`) and describe the set (`time`, `mood`, `desc`, `good_for`) - the planner
chooses sets from that text. Rebuild with `PYTHONPATH=. .venv/bin/python asset_pipeline/set_art.py`.

**Prop with a light/animation event** (example: the phone on the nightstand in `room_art.py`): draw the body layer and an `emissive` screen layer
with `opacity: 0`; drive `opacity`, a jitter `world_xf`, and a spill `Light` from a `Channel` in `film.py` (see the `interruption` recipe).

**Acting** (`performance.py`, `film.py`): a new micro-action is a function that only writes keys onto channels; a new story role recipe is a branch
in `film.compile_plan` plus a row in `planner.STORY_RULES` (the pose/framing the recipe requires).
Always re-run `asset_pipeline/register_sets.py` afterwards.
