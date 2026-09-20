"""Section-23 table: Asset | Source | License | Downloaded | Tested | Production Used | Reusable | Best Uses | Missing Pieces.  Built from inventory.json + the audit's findings."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BEST = {   # id -> (tested, production used, reusable, best uses, missing pieces)
    "open_peeps_flat_v1": ("yes (atlas: all 169 atoms composed)", "PARTLY: 2 of 46 heads in films", "YES", "heads, hair, facial hair, glasses, 20 replacement faces, harvested hands", "front + profile heads; bodies are unusable as rig parts"),
    "openpeeps_face_atoms_30": ("yes (face_lab: 8 expressions, procedural vs atom)", "TEST ONLY (face_atom action + styles.DAY_STUDY)", "YES", "peak-expression replacement drawings (anger, suspicion, fear, smile, tired ...)", "baked eyes: no gaze while an atom is up; some atoms mismatch the intended emotion (Awe, Concerned Fear)"),
    "openpeeps_head_hair_46": ("yes (46/46 compose)", "2 of 46 in films; 36 reachable in the vocabulary, all 46 in lab_dna", "YES", "hair, turbans, hats, headwear", "one drawing per atom: no turn"),
    "openpeeps_facial_hair_17": ("yes (17/17 compose)", "0 of 17 in films (only 'None'); 5 reachable", "YES", "moustaches, beards", "-"),
    "openpeeps_accessories_9": ("yes (9/9 compose)", "Glasses only", "YES", "glasses x5, sunglasses x2, eyepatch", "-"),
    "openpeeps_bodies_30": ("yes (30/30 compose; hand harvest tried)", "NO (Tee 1 as composition base; 1 hand harvested)", "PARTLY", "raster hand harvesting (cup, laptop, pointing, paper hands)", "per-atom crop boxes for harvest"),
    "openpeeps_poses_34": ("yes (renders)", "NO", "reference", "pose reference", "not separable"),
    "openpeeps_templates_189": ("counted", "bust.svg only", "reference", "composition base", "-"),
    "own_parts_v2": ("yes (50-character lab)", "YES", "YES", "everything below the neck", "torso bend, torso turn, bent limbs, garments (lab coat, apron, saree, vest, uniform badge)"),
    "own_environment_sets": ("yes (environment_coverage: 9 sets)", "bedroom_wide only in films", "YES", "bedroom, study; 5 backdrop-only sets", "cafe; seats/counters at full-body scale; foreground layers hide legs"),
    "openpeeps_device_hand_harvest_v1": ("yes", "YES", "YES", "phone grip", "cup / bag / door / keyboard grips"),
    "rgs_cc0_modular_animated_vector_characters": ("yes (rgs_lab: 5 combination tests + normalisation)", "NO", "NO (hair1 only after normalising)", "spiky hair candidate; mouth curves as reference", "everything a human needs"),
    "humaaans_site": ("web-read only (GitHub tree + one component)", "NO (not downloaded)", "LIKELY", "lab coat / trench coat / running + wheelchair legs as replacement drawings", "needs a download approval + ink outline synthesis"),
    "oga_creomoto_stickman_fixed_v1": ("yes (proportions, 20-frame run, crowd)", "YES as DATA: run cycle -> 'run' action", "YES", "gait / run cycle, proportion check, stick-figure background crowd", "-"),
    "blenderstudio_gp_cutout_boyhead282_v1": ("yes (gaze_test)", "TECHNIQUE adopted: pupil moves inside a fixed eye white (default)", "YES (technique)", "gaze", "eyelid layers, highlights"),
    "blenderstudio_gp_cutout_pepe_v1": ("yes", "no", "reference", "face-part layering reference", "-"),
    "blenderstudio_gp_cutout_cowboy_v1": ("yes", "no", "reference", "hat/face reference", "-"),
    "blenderstudio_gp_brush_pack_v2": ("yes", "no", "no", "-", "needs a live GP session; not deterministic in our compositor"),
    "mpfb2_generated_humans_cc0": ("yes (mpfb_pose_reference: 6 poses x 4 views)", "no (reference generator only)", "YES as reference", "turnaround / pose / anatomy reference, difficult poses", "sit and hold-phone channels need their own retargeting"),
    "mpfb2_extension_2_0_17": ("yes", "external tool", "as tool", "generate humans", "-"),
    "oga_old_lady_rigged_v1": ("yes", "no", "reference", "finger/face bone layout", "-"),
    "artell_mike_rig_v1": ("yes", "no", "no", "-", "needs autoexec drivers"),
    "blender_human_base_meshes_v1_4_1": ("yes", "no", "reference", "anatomy", "unrigged"),
    "kenney_platformer_characters_v1": ("yes (kenney_rig_test)", "no", "no", "-", "one-segment limbs"),
    "kenney_modular_characters_v1": ("yes", "no", "no", "-", "style"),
}


def main():
    inv = json.load(open(os.path.join(ROOT, "docs/asset_audit/inventory.json")))["records"]
    L = ["| Asset | Source | License | Downloaded | Tested | Production Used | Reusable | Best Uses | Missing Pieces |", "|---|---|---|---|---|---|---|---|---|"]
    for r in inv:
        t = BEST.get(r["id"])
        tested = t[0] if t else ("inspected / blocked" if not r["downloaded"] else "inspected")
        used = t[1] if t else r["production_use"]
        reus = t[2] if t else ("no" if r["production_use"] in ("BLOCKED (login)", "BLOCKED (checkout)", "BLOCKED (gated)", "NOT FOUND", "QUARANTINED") else "reference")
        best = t[3] if t else "-"
        miss = t[4] if t else r["reason_unused"]
        L.append(f"| `{r['id']}` | {r['source']} | {r['license']} | {'yes' if r['downloaded'] else 'NO'} | {tested} | {used} | {reus} | {best} | {miss} |")
    open(os.path.join(ROOT, "docs/asset_audit/utilization_table.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(len(L) - 2, "rows")


if __name__ == "__main__":
    main()
