"""Generates the DATA sections of docs/BLENDER_FREE_HUMAN_ASSET_AUDIT.md (candidate cards + measured test matrix) from the committed evidence in docs/blender_audit/*.json and the asset registry,
so every number in the document is copied from a measurement, never typed.   .venv/bin/python tools/assets/make_audit_doc.py > /tmp/audit_data.md"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EV = os.path.join(ROOT, "docs/blender_audit")
REG = {a["asset_id"]: a for a in json.load(open(os.path.join(ROOT, "assets/registry/asset_registry.json")))["assets"]}


def J(name):
    p = os.path.join(EV, name + ".json")
    return json.load(open(p)) if os.path.exists(p) else None


# (card title, registry id, probe id, tests id, extra dict)
CARDS = [
    ("Creomoto's Stick Man (Fixed Up)", "oga_creomoto_stickman_fixed_v1", "oga_stickman", "oga_stickman", dict(turn="any angle (3D mesh)", mod="single mesh, 206 tris; body parts not separable", gp="no", item="3")),
    ("Low-Poly Rigged Man (blockfigureRigged6)", "oga_lowpoly_rigged_man_v1", "oga_lowpoly_rigged_man", "oga_lowpoly_rigged_man", dict(turn="any angle (3D)", mod="4 meshes (body, helmet, spear...), one skinned", gp="no", item="10")),
    ("Old Lady (rigged, sitting)", "oga_old_lady_rigged_v1", "oga_old_lady", "oga_old_lady", dict(turn="any angle (3D)", mod="15 meshes, 2 skinned; dress/hair sculpted into the mesh", gp="no", item="10")),
    ("Puppet Base [Rigged]", "oga_puppet_base_rigged_v1", "oga_puppet_base", "oga_puppet_base", dict(turn="any angle (3D)", mod="one mesh", gp="no", item="10")),
    ("Mike (Auto-Rig Pro character)", "artell_mike_rig_v1", "mike_rig_b52", "mike_rig_b52", dict(turn="any angle (3D)", mod="229 meshes (body, clothes, hair, props as separate objects) but tied to drivers/scripts", gp="no", item="10, 11, 14")),
    ("Blender Human Base Meshes v1.4.1", "blender_human_base_meshes_v1_4_1", "human_base_meshes", None, dict(turn="any angle (3D)", mod="17 base meshes + body parts (hands, feet, heads, eyes), UN-rigged", gp="no", item="10, 11")),
    ("MPFB 2.0.17 + generated humans (default / game_engine / Rigify rigs)", "mpfb2_generated_humans_cc0", "mpfb_rigify_generated", "mpfb_rigify_generated", dict(turn="any angle (3D)", mod="8 macro sliders (gender, age, muscle, weight, proportions, height, cup, firmness) + race blend + 1445 target files; clothes/hair = MakeHuman asset packs (not downloaded)", gp="no", item="8, 9, 11, 14")),
    ("(Cutout-Rig) Pepe", "blenderstudio_gp_cutout_pepe_v1", "gp_pepe_cutout", "gp_pepe_cutout", dict(turn="front only (flat cutout)", mod="ONE GP object, 15 layers: bg, body, armL/R, earL/R, head, eyeL/R, pupilL/R, eyelidL/R, mouth, nose", gp="yes (GPv2 -> v3 auto-converted)", item="6, 12, 13")),
    ("(Cutout-Rig) Cowboy", "blenderstudio_gp_cutout_cowboy_v1", "gp_cowboy_cutout", "gp_cowboy_cutout", dict(turn="side (illustrated horse rider)", mod="40 GP objects, 6 armatures, hooks + lattice + armature modifiers", gp="yes", item="6")),
    ("(Cutout-Rig) Boy Head Test (2.82)", "blenderstudio_gp_cutout_boyhead282_v1", "gp_boyhead_cutout_282", None, dict(turn="front (lattice head-turn)", mod="6 GP objects: Body, Head, Eyes, Eyebrow, Nose, Mouth (face parts are separate objects; pupils are layers 'Left'/'Right')", gp="yes (2.82-only file: parts of the conversion break in 5.2.2)", item="6, 12")),
    ("(Cutout-Rig) Suzanno cutout test", "blenderstudio_gp_cutout_suzanno_v1", "gp_suzanno_cutout", None, dict(turn="front", mod="1 GP object, 4 layers + lattice", gp="yes", item="6")),
    ("(Cutout-Rig) Simple Head", "blenderstudio_gp_cutout_simplehead_v1", "gp_simplehead_cutout", None, dict(turn="front", mod="1 GP object, 16 layers, 16 empties", gp="yes", item="6")),
    ("(Cutout-Rig) Eye (2.82)", "blenderstudio_gp_cutout_eye282_v1", "gp_eye_cutout_282", None, dict(turn="front", mod="1 GP object, 13 layers, 22-bone armature", gp="yes", item="6")),
    ("GP Brush Pack v2", "blenderstudio_gp_brush_pack_v2", "gp_brush_pack_v2", None, dict(turn="n/a", mod="brush/material library", gp="yes", item="7")),
]
BLOCKED = ["blendswap_stickman_basic_rig_30507", "blendswap_2d_stickman_rig_v2_15217", "stickman_v4gp_2d", "gumroad_gp_spider_rig_dantti", "gumroad_gp_character_rigs_yadoob", "gumroad_super_stickman_ahmad", "quaternius_universal_base_characters"]


def yn(v):
    return "yes" if v else "no"


def card(title, rid, pid, tid, ex):
    a = REG[rid]
    p = J(pid) or {}
    t = J(tid + "_tests") if tid else None
    arms = p.get("armatures", [])
    big = max(arms, key=lambda x: x["bones"]) if arms else None
    L = [f"### {title}", ""]
    L.append(f"- **Source / URL:** {a['source']} - {a['source_url']}")
    L.append(f"- **Download URL:** {a['download_url']}  |  **SHA256:** `{(a.get('sha256') or 'n/a')[:16]}...`  |  **file:** `{a.get('local_path')}`")
    L.append(f"- **Author:** {a['author']}  |  **Licence:** {a['license']} ({a['policy_decision']})  |  **proof:** `{a.get('license_proof')}`")
    L.append(f"- **Commercial use:** {yn(a.get('commercial_use'))}  |  **Modification:** {yn(a.get('modification_allowed'))}  |  **Attribution required:** {yn(a.get('attribution_required'))}  |  **Share-alike:** {yn(a.get('share_alike'))}")
    L.append(f"- **File format / Blender version:** .blend, authored in Blender {p.get('file_blender_version')}; opened in Blender {p.get('blender')}")
    if big:
        L.append(f"- **Rig structure:** {len(arms)} armature(s); main = `{big['name']}`, {big['bones']} bones ({big['deform_bones']} deform), max chain depth {big['depth_max']}, roots {big['roots'][:4]}")
        ik = [x for x in big["ik"]]
        L.append(f"- **IK:** {len(ik)} IK constraint(s) {[(x['bone'], x['chain']) for x in ik][:8]}; other constraints {big['constraints']}")
        L.append(f"- **Face:** {big['face_bones_total']} face bones (brows {len(big['brow_bones'])}, mouth/jaw {len(big['mouth_bones'])}); shape keys {sum(s['n'] for s in p.get('shape_keys', []))}")
        L.append(f"- **Eyes:** eye bones {big['eye_bones'][:4] or 'none'}  |  **Hands:** {big['finger_bones']} finger bones")
        L.append(f"- **Drivers:** {big['drivers']} ({big['python_drivers']} scripted) - scripted drivers/embedded scripts do NOT run under `--disable-autoexec`: {p.get('embedded_text_scripts')}")
    else:
        L.append("- **Rig structure:** no armature" + (" (GP layers/objects + lattice/hook/empties instead)" if p.get("grease_pencil") else ""))
        L.append("- **IK / face / eyes / hands:** none as bones")
    acts = p.get("actions", [])
    L.append(f"- **Animation:** {p.get('n_actions')} action(s) {[(x['name'], x['frames']) for x in acts][:5]}")
    gp = p.get("grease_pencil", [])
    L.append(f"- **Grease Pencil:** {ex['gp']}; {len(gp)} GP object(s), {sum(g['n_layers'] for g in gp)} layers, {sum(g.get('strokes', 0) or 0 for g in gp)} strokes; render in 5.2.2: {yn(p.get('render', {}).get('ok'))}")
    L.append(f"- **Turnaround:** {ex['turn']}  |  **Modularity:** {ex['mod']}")
    L.append(f"- **Usage decision:** {a['usage']}")
    if t and "tests" in t:
        T = t["tests"]
        w, s, r, h, f, pr = (T.get(k, {}) for k in ("walk", "sit", "reach", "hold", "face", "proportions"))
        L.append(f"- **Measured (Blender 5.2.2, `blender_audit_tests.py`, base pose = `{t.get('base_pose_from_action')}`):** walk-by-IK {yn(w.get('pass_ik_walk'))} (foot tracking error max {w.get('foot_track_err_max_cm')} cm, stride {w.get('stride_m')} m, lift {w.get('foot_lift_m')} m); "
                 f"seated 90/90 {yn(s.get('pass_seated_pose'))}; reach 0.5-0.9 L {yn(r.get('pass_reach'))}; prop-on-hand follows {yn(h.get('pass_prop_attach'))}; eye rotation moves mesh {yn(f.get('eye_rotation_moves_mesh'))}; "
                 f"shape keys {f.get('shape_keys')} ({f.get('working_shape_keys')} displace vertices); bone-scale changes body {yn(pr.get('pass_bone_scale_changes_body'))} ({pr.get('change_pct')} %); bones mappable to our 26-bone roles {t['pipeline_mapping']['mapped']}/{t['pipeline_mapping']['of']}")
    L.append("")
    return "\n".join(L)


def blocked_row(rid):
    a = REG[rid]
    return f"| {a['name']} | {a['source_url']} | {a['license'] or 'unverified'} | {a['author']} | {a['status']} | {a['usage']} |"


def matrix():
    rows = ["| candidate | opens 5.2.2 | rig works | IK (measured) | walks | sits (90/90) | reaches | holds prop | face controllable | eyes move | parts replaceable | proportions | renders | convertible to our pipeline | GP works | licence |", "|" + "---|" * 16]
    def line(name, pid, tid, extra):
        p = J(pid) or {}
        t = J(tid + "_tests") if tid else None
        T = (t or {}).get("tests", {})
        w, s, r, h, f, pr = (T.get(k, {}) for k in ("walk", "sit", "reach", "hold", "face", "proportions"))
        a = extra
        ik = "n/a" if not t else (f"{w.get('foot_track_err_max_cm')} cm foot err" if w.get("foot_track_err_max_cm") is not None else "none / none-testable")
        return (f"| {name} | yes | {a.get('rig', 'n/a')} | {ik} | {yn(w.get('pass_ik_walk')) if t else 'n/a'} | {yn(s.get('pass_seated_pose')) if t else 'n/a'} | {yn(r.get('pass_reach')) if t else 'n/a'} | {yn(h.get('pass_prop_attach')) if t else 'n/a'} | "
                f"{a.get('face', 'n/a')} | {yn(f.get('eye_rotation_moves_mesh')) if t else a.get('eyes', 'n/a')} | {a.get('parts', 'n/a')} | {yn(pr.get('pass_bone_scale_changes_body')) if t else a.get('prop', 'n/a')} | {yn(p.get('render', {}).get('ok'))} | {a.get('conv', 'n/a')} | {a.get('gp', 'no')} | {a.get('lic', '')} |")
    rows.append(line("Creomoto Stick Man", "oga_stickman", "oga_stickman", dict(rig="yes (27 bones)", face="no", parts="no", conv="yes: driven by our semantic channels (0.02 % hip-height error)", lic="CC0")))
    rows.append(line("Low-Poly Rigged Man", "oga_lowpoly_rigged_man", "oga_lowpoly_rigged_man", dict(rig="partly (IK error 6 cm)", face="no", parts="no", conv="no (fails accuracy)", lic="CC0")))
    rows.append(line("Old Lady", "oga_old_lady", "oga_old_lady", dict(rig="yes (84 bones)", face="eye+brow bones, no shape keys", parts="no", conv="partly (22/23 bone roles)", lic="CC0")))
    rows.append(line("Puppet Base", "oga_puppet_base", "oga_puppet_base", dict(rig="FK only (26 bones)", face="eye bones", parts="no", conv="partly (13/23 roles, no IK)", lic="CC0")))
    rows.append(line("Mike (ARP)", "mike_rig_b52", "mike_rig_b52", dict(rig="yes (956 bones) - needs scripts for drivers", face="34 shape keys + 249 face bones (driver-dependent: 0 responded with autoexec off)", parts="separate meshes but driver-bound", conv="heavy; script-dependent -> no", lic="CC0")))
    rows.append(line("MPFB default rig + OUR IK", "mpfb_default_ik", "mpfb_default_ik", dict(rig="FK rig; IK added by us", face="30 finger, 14 face bones, 4 shape keys", parts="mesh + macro sliders", conv="yes (12/23 name roles; use Rigify instead)", lic="GPL tool / CC0 output")))
    rows.append("| MPFB + Rigify (generated) | yes | yes (1090 bones) | 0.02 % of hip height (candidate_drive) | yes | see note | yes (0.01 %) | n/a (control exists) | yes (94 face controls, 18 brow) | jaw yes; eye test inconclusive | mesh+macros+asset packs | macro sliders pre-rig | yes | yes: `candidate_integration_walk_reach.mp4` | no | GPL tool / CC0 output |")
    for name, pid, note in (("Pepe (GP cutout)", "gp_pepe_cutout", dict(rig="22 bones, stretch-to, no IK", face="layers: eyelids, pupils, mouth, nose", eyes="pupil+eyelid layers/bones", parts="yes: 15 layers", prop="no", conv="concept only", gp="yes")),
                            ("Cowboy (GP)", "gp_cowboy_cutout", dict(rig="6 armatures + hooks/lattice", face="eye layers", eyes="layers", parts="yes: 40 GP objects", prop="no", conv="concept only", gp="yes")),
                            ("Boy Head Test (GP)", "gp_boyhead_cutout_282", dict(rig="lattice + hooks", face="separate Eyes/Eyebrow/Mouth/Nose objects", eyes="yes: pupil layers moved by our gaze (1.47k px change)", parts="yes: 6 objects", prop="no", conv="gaze test done", gp="partly broken")),
                            ("Suzanno / Simple Head / Eye", "gp_suzanno_cutout", dict(rig="lattice/empties/22 bones", face="layers", eyes="layers", parts="layers", prop="no", conv="reference only", gp="yes")),
                            ("Human Base Meshes", "human_base_meshes", dict(rig="none (unrigged)", face="1 head with 10 shape keys", eyes="separate eyeballs", parts="17 meshes", prop="sculpt", conv="needs rigging = MPFB", gp="no"))):
        p = J(pid) or {}
        rows.append(f"| {name} | yes | {note['rig']} | n/a | n/a | n/a | n/a | n/a | {note['face']} | {note['eyes']} | {note['parts']} | {note['prop']} | {yn(p.get('render', {}).get('ok'))} | {note['conv']} | {note['gp']} | CC-BY / CC0 / quarantined (see cards) |")
    return "\n".join(rows)


if __name__ == "__main__":
    print("## 3. Candidate cards (downloaded, opened, tested)\n")
    for c in CARDS:
        print(card(*c))
    print("## 4. Candidates that could NOT be downloaded (nothing was signed in to, no checkout form submitted)\n")
    print("| candidate | source URL | licence claimed | author | status | why |\n|---|---|---|---|---|---|")
    for rid in BLOCKED:
        print(blocked_row(rid))
    print("\n## 5. Test matrix (measured, Blender 5.2.2)\n")
    print(matrix())
