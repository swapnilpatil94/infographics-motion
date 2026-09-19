#!/usr/bin/env python3
"""Registers every asset touched by the Blender human/stickman/GP rig audit (docs/BLENDER_FREE_HUMAN_ASSET_AUDIT.md).  Called by acquire_v2.py; can also be run alone (upserts into the registry).

Downloaded files live in assets/raw/blender_audit/ (large binaries are git-ignored; the registry keeps URL + SHA256 so they can be re-fetched and verified).
Candidates that could not be downloaded WITHOUT signing in / an e-mail checkout are recorded as BLOCKED_* - they are never used.  Licence unknown or unverified -> QUARANTINE."""
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import acquire_v2 as A   # noqa: E402

RAW = os.path.join(A.ROOT, "assets/raw/blender_audit")
CC0 = "CC0-1.0"
BY = "CC-BY-4.0"


def rel(p):
    return os.path.relpath(os.path.join(RAW, p), A.ROOT)


def proof(name, url, pattern):
    dest = os.path.join(RAW, f"LICENSE_PROOF_{name}.txt")
    try:
        ok = A.page_proof(url, dest, pattern)
    except Exception as e:
        open(dest, "w").write(f"source page: {url}\nfetch FAILED: {e}\n")
        ok = False
    return os.path.relpath(dest, A.ROOT) if ok else None


def dl(asset_id, filename, url, **k):
    """Existing local file -> sha256 + record."""
    path = os.path.join(RAW, filename)
    k.update(sha256=A.sha256(path), local_path=rel(filename), downloaded_at=datetime.datetime.fromtimestamp(os.path.getmtime(path), datetime.timezone.utc).isoformat(), download_url=url)
    return A.record(asset_id=asset_id, **k)


def blocked(asset_id, status, why, **k):
    k.setdefault("sha256", None)
    k.setdefault("license_proof", None)
    k.update(downloaded_at=None, local_path=None, status=status, usage=why)
    return A.record(asset_id=asset_id, **k)


def entries():
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    out = []
    oga = "https://opengameart.org/content/"
    cc0_pat = r"CC0[^<]{0,60}|Creative Commons Zero[^<]{0,60}"
    p = proof("oga_creomoto_stickman", oga + "creomotos-stick-man-fixed-up", cc0_pat)
    out.append(dl("oga_creomoto_stickman_fixed_v1", "oga_stickman_fixed.blend", "https://opengameart.org/sites/default/files/StickMan_0.blend", source="OpenGameArt", name="Creomoto's Stick Man (Fixed Up)",
                  source_url=oga + "creomotos-stick-man-fixed-up", author="Creomoto (original) / mrpoly (rig fix, 2015-03-09)", license=CC0, license_proof=p, status="DOWNLOADED_TESTED",
                  usage="E: stickman/skeleton REFERENCE. Blender 2.71 file: 27 bones, 8 IK constraints (leg+arm IK targets, knee/elbow pole helper targets), idle+run actions. Driven by our semantic channels in output/tests/candidate_integration_walk_reach.mp4. No face/eyes/hands."))
    p = proof("oga_lowpoly_rigged_man", oga + "low-poly-rigged-man", cc0_pat)
    out.append(dl("oga_lowpoly_rigged_man_v1", "oga_lowpoly_rigged_man.blend", "https://opengameart.org/sites/default/files/blockfigureRigged6.blend", source="OpenGameArt", name="Low-Poly Rigged Man (blockfigureRigged6)",
                  source_url=oga + "low-poly-rigged-man", author="infernaltoast", license=CC0, license_proof=p, status="DOWNLOADED_TESTED",
                  usage="Tested: 19 bones, 4 IK, blocky low-poly; leg IK tracking error 6 cm in the synthetic walk (fails our <1 cm gate). Not adopted."))
    p = proof("oga_old_lady", oga + "old-lady", cc0_pat)
    out.append(dl("oga_old_lady_rigged_v1", "oga_old_lady.blend", "https://opengameart.org/sites/default/files/oldlady-v2.blend", source="OpenGameArt", name="Old Lady (rigged, sitting)", source_url=oga + "old-lady",
                  author="CDmir (with TinyWorlds)", license=CC0, license_proof=p, status="DOWNLOADED_TESTED",
                  usage="Tested: 84 bones incl. 30 finger + eye/brow bones, 8 IK; legs+forearms IK pass, no shape keys, fixed sculpted dress/hair (not modular). Reference for a face/hand bone layout only."))
    out.append(dl("oga_puppet_base_rigged_v1", "oga_puppet_base.7z", "https://opengameart.org/sites/default/files/baseRelease.7z", source="OpenGameArt", name="Puppet Base [Rigged]", source_url=oga + "puppet-base-rigged", author="practicing01",
                  license=CC0, license_proof=proof("oga_puppet_base", oga + "puppet-base-rigged", cc0_pat), status="DOWNLOADED_TESTED",
                  usage="Tested: 26 bones, eye bones move the mesh, no IK/actions. Structural reference only."))
    studio = "https://studio.blender.org/training/grease-pencil-fundamentals/"
    by_pat = r"Creative Commons Attribution[^<]{0,60}|CC[- ]BY[^<]{0,40}|creativecommons\.org/licenses/by[^\"'<]{0,20}"
    for aid, fn, page, url, name, author in (
            ("blenderstudio_gp_cutout_pepe_v1", "gp_pepe_cutout.blend", "5cba1d2e53491006f35d95d0/", "https://studio.blender.org/download-source/files/a9/a9e64c4c1c654e0dabc3fbaeaee85fb5/a9e64c4c1c654e0dabc3fbaeaee85fb5.blend", "(Cutout-Rig) Pepe", "Daniel Martinez Lara (Pepeland) / Blender Studio"),
            ("blenderstudio_gp_cutout_cowboy_v1", "gp_cowboy_cutout.blend", "5d9c6ee20f9018baaca071c3/", "https://studio.blender.org/download-source/files/11/119c054515814654afdd498964a57879/119c054515814654afdd498964a57879.blend", "(Cutout-Rig) Cowboy", "Maisam Hosaini / Blender Studio"),
            ("blenderstudio_gp_cutout_boyhead282_v1", "gp_boyhead_cutout_282.blend", "5d9c6fbd2ed9a72b3fae65b0/", "https://studio.blender.org/download-source/files/a6/a6ee4be7a0e5405e813ebdc6e4129568/a6ee4be7a0e5405e813ebdc6e4129568.blend", "(Cutout-Rig) Boy Head Test (2.82)", "Maisam Hosaini / Blender Studio")):
        out.append(dl(aid, fn, url, source="Blender Studio - Grease Pencil Fundamentals", name=name, source_url=studio + page, author=author, license=BY, license_proof=proof(aid, studio + page, by_pat),
                      attribution_text=f"{name} by {author}, CC BY 4.0, Blender Studio ({studio + page})", status="DOWNLOADED_TESTED",
                      usage="B/D: Grease Pencil cutout technical reference (separate GP objects/layers per face part, hooks/lattices, pupil layers). Opens in Blender 5.2.2 via automatic GPv2->GPv3 conversion; gaze test: output/tests/blender_audit/gp_boyhead_gaze_*.png. CC-BY: attribution required if any art is reused; nothing is vendored into the engine."))
    out.append(dl("blenderstudio_gp_brush_pack_v2", "gp_brush_pack_v2.zip", "https://studio.blender.org/download-source/files/1f/1fc0d9422d724dd680f3240b07fb8017/1fc0d9422d724dd680f3240b07fb8017.zip", source="Blender Studio - Grease Pencil Fundamentals",
                  name="Brush Pack v2 (Blender 2.90+)", source_url=studio + "5f235cc297f8815e74ffb90b/", author="Daniel Martinez Lara (Pepeland) / Blender Studio", license=BY,
                  license_proof=proof("blenderstudio_gp_brush_pack_v2", studio + "5f235cc297f8815e74ffb90b/", by_pat), attribution_text="Brush Pack v2 by Daniel Martinez Lara (Pepeland), CC BY 4.0, Blender Studio", status="DOWNLOADED_TESTED",
                  usage="D: GP brush/material reference (the pack loads in Blender 5.2.2 as an asset .blend). Not used by the deterministic compositor."))
    arch = "https://download.blender.org/archive/gallery/grease-pencil-samples/"
    for aid, fn, page, url, name, author in (
            ("blenderstudio_gp_cutout_suzanno_v1", "gp_suzanno_cutout.blend", "cutout-rig-suzanno-cutout-test-by-francisco-antonio-peinado-currobot-for-2-83-or-above/",
             "https://download.blender.org/demo-files/archives/art-gallery/grease-pencil-samples/grease-pencil-blender-free-samples/cutout-rig-suzanno-cutout-test-by-francisco-antonio-peinado-currobot-for-2-83-or-above/cutout-rig-suzanno-by-francisco-antonio-peinado-currobot-49d7d95171da4b11a26e8e56ac73d559.blend",
             "(Cutout-Rig) Suzanno cutout test", "Francisco Antonio Peinado (Currobot)"),
            ("blenderstudio_gp_cutout_simplehead_v1", "gp_simplehead_cutout.blend", "cutout-rig-simple-head-by-maisam-hosaini-for-2-83-or-above/",
             "https://download.blender.org/demo-files/archives/art-gallery/grease-pencil-samples/grease-pencil-blender-free-samples/cutout-rig-simple-head-by-maisam-hosaini-for-2-83-or-above/cutout-rig-simple-head-by-maisam-hosaini-f220e2ef0c254e54b6da628fa784013b.blend",
             "(Cutout-Rig) Simple Head", "Maisam Hosaini"),
            ("blenderstudio_gp_cutout_eye282_v1", "gp_eye_cutout_282.blend", "cutout-rig-eye-by-jefferson-nascimento-only-for-2-82/",
             "https://download.blender.org/demo-files/archives/art-gallery/grease-pencil-samples/grease-pencil-blender-free-samples/cutout-rig-eye-by-jefferson-nascimento-only-for-2-82/cutout-rig-eye-by-jefferson-nascimento-e4087d677ddb4328ab5d57984ab6004f.blend",
             "(Cutout-Rig) Eye (2.82)", "Jefferson Nascimento")):
        out.append(dl(aid, fn, url, source="Blender Institute Archive (grease-pencil-samples)", name=name, source_url=arch + page, author=author, license=None, license_proof=None, status="DOWNLOADED_QUARANTINED",
                      usage="Downloaded for INSPECTION ONLY: the archive page states no licence, so the file is quarantined and not used. (Probe: output/tests/blender_audit/%s.json)" % aid.replace("blenderstudio_", "").replace("_v1", "")))
    out.append(dl("artell_mike_rig_v1", "mike_rig.zip", "http://lucky3d.fr/auto-rig-pro/mike.zip", source="Artell (lucky3d.fr) via BlenderNation", name="Mike - fully rigged character (Auto-Rig Pro)", source_url="https://www.blendernation.com/2019/02/13/free-download-mike-fully-rigged-character-cc-0/",
                  author="Artell (Lucas)", license=CC0, license_proof=proof("artell_mike", "https://www.blendernation.com/2019/02/13/free-download-mike-fully-rigged-character-cc-0/", r"CC-?0[^<]{0,60}"), status="DOWNLOADED_TESTED",
                  usage="C candidate: 956 bones, 196 finger + 249 face bones, 34 shape keys, 11 IK - BUT 371 Python drivers + an embedded reset script that need script auto-exec (we open with --disable-autoexec). Legs IK/hold pass; face/proportion tests inconclusive without drivers. Too heavy for a lightweight deterministic factory."))
    out.append(dl("blender_human_base_meshes_v1_4_1", "human_base_meshes_v1.4.1.zip", "https://download.blender.org/demo/asset-bundles/human-base-meshes/human-base-meshes-bundle-v1.4.1.zip", source="Blender Foundation / Blender Studio",
                  name="Human Base Meshes bundle v1.4.1", source_url="https://www.blender.org/download/demo-files/", author="Blender Studio + community", license=CC0,
                  license_proof=proof("blender_human_base_meshes", "https://www.blender.org/download/demo-files/", r"CC0[^<]{0,80}|Creative Commons Zero[^<]{0,60}"), status="DOWNLOADED_TESTED",
                  usage="C support: 17 UN-rigged sculpting meshes (382 mesh objects, 150k tris) CC0. Rigging it ourselves = the MPFB path anyway; not adopted alone."))
    out.append(A.record(asset_id="mpfb2_extension_2_0_17", source="MakeHuman Community (Blender Extensions)", name="MPFB 2.0.17 (human generator add-on)", source_url="https://extensions.blender.org/add-ons/mpfb/",
                        download_url="https://extensions.blender.org/download/sha256:4f0a879d64a39bf646fbf5f53601ac678855da329d650617dca5737548239a87/add-on-mpfb-v2.0.17.zip", author="Joel Palmius / MakeHuman Community", license="GPL-3.0-or-later",
                        sha256=A.sha256(os.path.join(RAW, "mpfb_2.0.17.zip")), downloaded_at=datetime.datetime.fromtimestamp(os.path.getmtime(os.path.join(RAW, "mpfb_2.0.17.zip")), datetime.timezone.utc).isoformat(),
                        local_path=rel("mpfb_2.0.17.zip"), license_proof=proof("mpfb2", "https://static.makehumancommunity.org/about/license.html", r"CC0[^<]{0,100}|GPLv3[^<]{0,80}|AGPL[^<]{0,80}"), kind="code",
                        has_file=True, status="EXTERNAL_TOOL",
                        usage="C candidate, used ONLY as an external generator inside Blender (no MPFB code copied). Code is GPL-3.0; the bundled assets and every exported human are CC0 per the MakeHuman licence page. Generated: output/tests/blender_audit/ + assets/raw/blender_audit/mpfb_out/*.blend."))
    out.append(A.record(asset_id="mpfb2_generated_humans_cc0", source="generated locally with MPFB 2.0.17 in Blender 5.2.2", name="MPFB-generated humans / rigs (default, game_engine, Rigify)", source_url="https://static.makehumancommunity.org/about/license.html",
                        download_url="n/a (generated: tools/assets/mpfb_build.py)", author="MakeHuman Community targets/assets", license=CC0, sha256=A.sha256(os.path.join(RAW, "mpfb_out/mpfb_rigify.blend")), downloaded_at=now,
                        local_path=rel("mpfb_out/mpfb_rigify.blend"), license_proof=proof("mpfb2_output", "https://static.makehumancommunity.org/about/license.html", r"CC0[^<]{0,100}"), status="DOWNLOADED_TESTED",
                        usage="C: 3D human foundation candidate (parametric proportions via macro details, 5 rig options incl. Rigify 1090 bones). Driven by our semantic channels: 0.02 % of hip height IK error. Not yet the production path."))
    # ---- ASSET + ACTING QUALITY LOCK (character art sources)
    rgs = os.path.join(A.ROOT, "assets/raw/rgs/free_2d_animated_vector_game_character_sprites.zip")
    out.append(A.record(asset_id="rgs_cc0_modular_animated_vector_characters", source="OpenGameArt (RGS_Dev)", name="Free CC0 Modular Animated Vector Characters 2D", source_url="https://opengameart.org/content/free-cc0-modular-animated-vector-characters-2d",
                        download_url="https://opengameart.org/sites/default/files/free_2d_animated_vector_game_character_sprites.zip", author="rgsdev", license=CC0, sha256=A.sha256(rgs),
                        downloaded_at=datetime.datetime.fromtimestamp(os.path.getmtime(rgs), datetime.timezone.utc).isoformat(), local_path=os.path.relpath(rgs, A.ROOT),
                        license_proof=proof("rgs_modular", "https://opengameart.org/content/free-cc0-modular-animated-vector-characters-2d", r"CC0[^<]{0,60}"), status="DOWNLOADED_EVALUATED",
                        usage="EVALUATED, NOT USED: 3 monster/creature heads, 3 hairs, 7 glossy eyes, 8 mouths, 1 body/hand/foot as 2048 px white-tinted game sprites with baked cel shading and thick black rims - a game-monster style that "
                              "does not match the flat editorial ink of the Open Peeps heads, and single hand/foot sprites cannot give a 20-pose hand library. Kept as a style reference for the eye highlight idea only."))
    out.append(A.record(asset_id="openpeeps_device_hand_harvest_v1", source="derived from Open Peeps (Pablo Stanley) 'Device' body atom", name="hold_phone hand drawing (harvested)", source_url="https://www.openpeeps.com/",
                        download_url="derived locally: tools/assets/harvest_openpeeps.py Separate Atoms/body/Device.svg crop (430,270,720,500)", author="Pablo Stanley", license=CC0, sha256=A.sha256(os.path.join(A.ROOT, "assets/character/harvest/openpeeps_device_hand.fill.npy")),
                        downloaded_at=now, local_path="assets/character/harvest/openpeeps_device_hand.fill.npy", license_proof="assets/raw/open_peeps/LICENSE_PROOF.txt", status="USED",
                        usage="USED: the real hand drawing for the hold_phone pose (fill + ink masks, recoloured to the DNA skin tone). Harvest attempts on the Explaining / Coffee / Macbook / Gaming / Killer atoms produced open contours (the atoms' hand outlines are not "
                              "closed), so only the Device hand is production quality; see docs/CHARACTER_ART_LOCK.md."))
    # ---- blocked / unverified
    out.append(blocked("blendswap_stickman_basic_rig_30507", "BLOCKED_LOGIN", "Blend Swap requires signing in to download; account creation/sign-in is not something the agent does. CC0 per the page (author EMOPRODUCTION, 560 KB, Blender 3.0x). User can drop the .blend into assets/raw/blender_audit/ to have it audited.",
                       source="Blend Swap", name="Stickman Characters with Basic rig and Freestyle", source_url="https://blendswap.com/blend/30507", download_url="https://blendswap.com/blend/30507/download", author="EMOPRODUCTION", license=CC0,
                       license_proof=proof("blendswap_30507", "https://blendswap.com/blend/30507", r"CC0[^<]{0,60}")))
    out.append(blocked("blendswap_2d_stickman_rig_v2_15217", "BLOCKED_LOGIN", "Blend Swap sign-in required. CC-BY (LDev), Blender 2.7x Blender-Internal file (137 KB) - would need conversion anyway.", source="Blend Swap", name="2D StickMan Rig v2",
                       source_url="https://blendswap.com/blend/15217", download_url="https://blendswap.com/blend/15217/download", author="LDev", license=BY, attribution_text="2D StickMan Rig v2 by LDev, CC BY, Blend Swap",
                       license_proof=proof("blendswap_15217", "https://blendswap.com/blend/15217", r"CC[- ]BY[^<]{0,40}|Attribution[^<]{0,40}")))
    out.append(blocked("gumroad_gp_spider_rig_dantti", "BLOCKED_CHECKOUT", "Gumroad free download needs an e-mail checkout form (personal data); not submitted. Licence claim (CC0) comes from a search snippet only -> unverified -> quarantined.", source="Gumroad", name="GP Spider Rig",
                       source_url="https://dantti.gumroad.com/l/gp_spider_rig", download_url="https://dantti.gumroad.com/l/gp_spider_rig", author="dantti", license=None))
    out.append(blocked("gumroad_super_stickman_ahmad", "BLOCKED_CHECKOUT", "Gumroad checkout required; CC0 claim only from a search snippet -> unverified -> quarantined.", source="Gumroad", name="Super Stickman Game-ready rig",
                       source_url="https://ahmadanimation.gumroad.com/l/xptxd", download_url="https://ahmadanimation.gumroad.com/l/xptxd", author="Ahmad Animation", license=None))
    out.append(blocked("gumroad_gp_character_rigs_yadoob", "BLOCKED_CHECKOUT", "Gumroad checkout required and the BlenderNation article states no licence -> unknown -> quarantined.", source="Gumroad", name="Grease Pencil Character Rigs (man, child, anime girl)",
                       source_url="https://gumroad.com/l/zGJZB", download_url="https://gumroad.com/l/zGJZB", author="Yadoob", license=None))
    out.append(blocked("quaternius_universal_base_characters", "BLOCKED_GATED", "CC0 (per the pack page) but the download is behind an itch.io / Patreon lightbox flow; the .blend source version is paid. Not fetched.", source="Quaternius", name="Universal Base Characters",
                       source_url="https://quaternius.com/packs/universalbasecharacters.html", download_url="https://quaternius.itch.io/universal-base-characters", author="Quaternius", license=CC0,
                       license_proof=proof("quaternius_ubc", "https://quaternius.com/packs/universalbasecharacters.html", r"CC0[^<]{0,60}|publicdomain/zero[^\"'<]{0,20}")))
    out.append(blocked("stickman_v4gp_2d", "NOT_FOUND", "Searched Blend Swap / Gumroad / Blender Studio / OpenGameArt / general web: no asset named '2D Stickman V4GP' could be located. Ask the user for the URL.", source="unknown", name="2D Stickman V4GP", source_url=None,
                       download_url=None, author=None, license=None))
    return out


def upsert(reg_path, new):
    reg = json.load(open(reg_path))
    by = {a["asset_id"]: a for a in reg["assets"]}
    for a in new:
        by[a["asset_id"]] = a
    reg["assets"] = list(by.values())
    reg["generated"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    json.dump(reg, open(reg_path, "w"), indent=1, ensure_ascii=False)
    return reg["assets"]


def report(reg):
    return dict(policy_source="engine/licensing/policy.py", summary={d: sum(1 for a in reg if a["policy_decision"] == d) for d in sorted({a["policy_decision"] for a in reg})},
                usable_in_films=[a["asset_id"] for a in reg if a["status"] == "USED"], evaluated_downloaded=[a["asset_id"] for a in reg if a["status"] in ("DOWNLOADED_EVALUATED", "DOWNLOADED_TESTED")],
                external_tools=[a["asset_id"] for a in reg if a["status"] == "EXTERNAL_TOOL"], blocked_not_downloaded=[dict(asset_id=a["asset_id"], status=a["status"]) for a in reg if str(a["status"]).startswith(("BLOCKED", "NOT_FOUND"))],
                quarantined=[dict(asset_id=a["asset_id"], reason=a["policy_reason"]) for a in reg if a["policy_decision"] == "QUARANTINE"], rejected=[a["asset_id"] for a in reg if a["policy_decision"] == "REJECT"],
                attribution_required=[a["asset_id"] for a in reg if a.get("attribution_required")], share_alike=[a["asset_id"] for a in reg if a.get("share_alike")])


if __name__ == "__main__":
    regp = os.path.join(A.ROOT, "assets/registry/asset_registry.json")
    allr = upsert(regp, entries())
    rep = report(allr)
    json.dump(rep, open(os.path.join(A.ROOT, "assets/registry/license_report.json"), "w"), indent=1)
    print(json.dumps(rep, indent=1))
