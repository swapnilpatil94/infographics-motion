# Adding a topic pack

A pack = named group of assets that lets the engine depict a domain (money, science, mythology...).
The registry (`engine/shorts/topics.py`) already lists packs with `have` / `missing` assets; the planner emits
`asset_requirements.json` for whatever a topic needs that is missing, so you always know what to build next.

1. **Read the requirements.** Run `python3 studio.py --make "<topic>" --plan-only` and open `output/made/<slug>/asset_requirements.json`
   (`{"asset_required": true, "type": "prop", "name": "ATM", "priority": "high"}`).
2. **Make the art** in the existing ink language (`asset_pipeline/ink.py`): props go in a set generator (`set_art.py`) as a layer with
   `par` (parallax) and `depth` (focus plane); icons go in `asset_pipeline/icons.py`; character poses come from Open Peeps atoms
   (`cast_builder.py` BODIES) or a new licensed source (register it - step 5).
3. **Expose it to the planner**: add the noun to `HAVE` in `topics.py` (so it stops being reported as missing), move it from
   `missing` to `have` in the pack, and (for new poses/icons/sets) add a line to `library.py` / `sets.py`. The planner's prompts and
   JSON-schema enums are generated from those tables, so no prompt edits are needed.
4. **Check** `python3 studio.py --make "<topic>" --plan-only`: the capability class should move from C to B or A.
5. **Register provenance**: add the asset/generator to `asset_pipeline/register_sets.py` (source, license, sha256). The render report
   fails `asset_license_metadata_complete` if anything used is unregistered.
Classes: A fully supported - B procedural graphics (cards/charts) - C needs specialist assets - D unsupported.
