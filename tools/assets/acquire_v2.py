#!/usr/bin/env python3
"""Character-asset acquisition (Factory V2): download -> hash -> licence proof -> policy decision -> registry.

    .venv/bin/python tools/assets/acquire_v2.py

Every external asset gets: asset_id, source, source_url, download_url, author, license, commercial_use, modification_allowed, attribution_required, share_alike,
sha256, downloaded_at, license_proof, usage. UNKNOWN licence -> QUARANTINE (not used). NC/ND -> REJECT."""
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from engine.licensing import policy   # noqa: E402

RAW = os.path.join(ROOT, "assets/raw")
UA = {"User-Agent": "kathaya-asset-tools"}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def fetch(url, dest):
    if not os.path.exists(dest):
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
            f.write(r.read())
    return dest


def page_proof(url, dest, pattern):
    """Save the licence sentence found on the source page (plus URL + date) as the proof file."""
    html = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read().decode("utf-8", "replace")
    hits = re.findall(pattern, html, flags=re.I)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    open(dest, "w", encoding="utf-8").write(f"source page: {url}\nfetched: {datetime.datetime.now(datetime.timezone.utc).isoformat()}\nmatched licence text:\n" + "\n".join(f"  - {h.strip()}" for h in hits[:6]) + "\n")
    return bool(hits)


def zip_member(zip_path, member, dest):
    import zipfile
    with zipfile.ZipFile(zip_path) as z:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        open(dest, "wb").write(z.read(member))


def record(**k):
    lic = k["license"]
    dec = policy.decide(lic, kind=k.pop("kind", "asset"), has_license_file=k.pop("has_file", bool(k.get("license_proof"))), attribution_text=k.get("attribution_text"))
    k.update(commercial_use=dec.get("commercial_use"), modification_allowed=dec.get("modification_allowed"), attribution_required=dec.get("attribution_required"),
             share_alike=dec.get("share_alike"), policy_decision=dec["decision"], policy_reason=dec["reason"])
    return k


def main():
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    reg = []
    # ---- Kenney Platformer Characters (CC0) - downloaded
    z = fetch("https://kenney.nl/media/pages/assets/platformer-characters/b85f388c42-1677693768/kenney_platformer-characters.zip", os.path.join(RAW, "kenney/kenney_platformer-characters.zip"))
    zip_member(z, "License.txt", os.path.join(RAW, "kenney/platformer-characters.LICENSE.txt"))
    reg.append(record(asset_id="kenney_platformer_characters_v1", source="Kenney (kenney.nl)", name="Platformer Characters", source_url="https://kenney.nl/assets/platformer-characters",
                      download_url="https://kenney.nl/media/pages/assets/platformer-characters/b85f388c42-1677693768/kenney_platformer-characters.zip", author="Kenney Vleugels", license="CC0-1.0",
                      sha256=sha256(z), downloaded_at=now, local_path=os.path.relpath(z, ROOT), license_proof="assets/raw/kenney/platformer-characters.LICENSE.txt",
                      usage="EVALUATED + rigging test (output/tests/kenney_rig_test.*). Limbs are separate PNG but arm/leg are ONE segment, chibi proportions, baked face -> second source for chibi styles only; not the primary foundation.",
                      status="DOWNLOADED_EVALUATED"))
    # ---- Kenney Modular Characters (CC0) - downloaded
    z = fetch("https://kenney.nl/media/pages/assets/modular-characters/d84577feef-1677670340/kenney_modular-characters.zip", os.path.join(RAW, "kenney/kenney_modular-characters.zip"))
    zip_member(z, "license.txt", os.path.join(RAW, "kenney/modular-characters.LICENSE.txt"))
    reg.append(record(asset_id="kenney_modular_characters_v1", source="Kenney (kenney.nl)", name="Modular Characters", source_url="https://kenney.nl/assets/modular-characters",
                      download_url="https://kenney.nl/media/pages/assets/modular-characters/d84577feef-1677670340/kenney_modular-characters.zip", author="Kenney Vleugels", license="CC0-1.0",
                      sha256=sha256(z), downloaded_at=now, local_path=os.path.relpath(z, ROOT), license_proof="assets/raw/kenney/modular-characters.LICENSE.txt",
                      usage="EVALUATED. Front-view chibi wardrobe sprites (skin/face/shirts/pants/shoes/hair); wrong scale/style for an editorial documentary and no limb split -> not used in films.",
                      status="DOWNLOADED_EVALUATED"))
    # ---- Open Peeps (CC0) - primary foundation for heads / hair / faces / accessories / ink style
    op_zip = os.path.join(ROOT, "assets/character/raw/open_peeps/open_peeps_flat_assets.zip")
    ok = page_proof("https://www.openpeeps.com/", os.path.join(RAW, "open_peeps/LICENSE_PROOF.txt"), r"[^<>]{0,40}CC0[^<>]{0,60}")
    reg.append(record(asset_id="open_peeps_flat_v1", source="Open Peeps (Pablo Stanley)", name="Open Peeps flat assets", source_url="https://www.openpeeps.com/",
                      download_url="https://www.openpeeps.com/ (Gumroad pay-what-you-want download, saved once via browser)", author="Pablo Stanley", license="CC0-1.0", sha256=sha256(op_zip),
                      downloaded_at="2026-09-19T08:01:33+00:00", local_path=os.path.relpath(op_zip, ROOT), license_proof="assets/raw/open_peeps/LICENSE_PROOF.txt" if ok else None,
                      usage="PRIMARY FOUNDATION: 41 hair/head atoms, faces, facial hair, accessories, the nose, and the monochrome ink STYLE language. Whole-body templates (60 standing/sitting poses) are single illustrations, so limbs/torso are generated in the same style.",
                      status="USED"))
    # ---- Humaaans (CC0 by author; only community mirrors are downloadable)
    reg.append(record(asset_id="humaaans_site", source="Humaaans (Pablo Stanley)", name="Humaaans", source_url="https://www.humaaans.com/", download_url="https://www.humaaans.com/ (Figma/Sketch; not downloadable without an account)",
                      author="Pablo Stanley", license="CC0-1.0", sha256=None, downloaded_at=None, local_path=None,
                      license_proof="assets/raw/humaaans/LICENSE_PROOF.txt" if page_proof("https://www.humaaans.com/", os.path.join(RAW, "humaaans/LICENSE_PROOF.txt"), r"[^<>]{0,40}CC0[^<>]{0,60}") else None,
                      usage="EVALUATED (mirror jktzes/humaaans, MIT React library): parts are whole torso-with-arms / whole legs -> not riggable limb by limb. Not vendored.", status="EVALUATED_NOT_USED"))
    # ---- rig research repos: references only
    for rid, url, spdx, note in (("coa_tools2", "https://github.com/Aodaruma/coa_tools2", "GPL-3.0", "architecture reference only (GPL code never vendored)"),
                                 ("tiny_2d_rig_tools", "https://github.com/NickTiny/Tiny-2D-Rig-Tools", None, "no licence -> reference only"),
                                 ("puppet_mode", "https://github.com/8bitbyadog/puppet-mode", None, "no licence -> reference only"),
                                 ("skeleton_rig_frycz", "https://github.com/frycz/skeleton-rig", None, "no licence -> reference only; data-model idea (skeleton/picture/motion JSON)")):
        try:
            lic, has, pushed = policy.github_license(url.split("github.com/")[1])
        except Exception:
            lic, has = spdx, False
        reg.append(record(asset_id=rid, source="GitHub", name=rid, source_url=url, download_url=url + ".git", author=url.split("github.com/")[1].split("/")[0], license=lic or "NOASSERTION",
                          sha256=None, downloaded_at=None, local_path=None, license_proof=None, kind="code", has_file=bool(has), usage=note, status="REFERENCE_ONLY"))
    return reg


if __name__ == "__main__":
    reg = main()
    import acquire_blender_audit as BA
    reg += BA.entries()                                                              # keep the Blender rig-audit assets when the registry is regenerated
    os.makedirs(os.path.join(ROOT, "assets/registry"), exist_ok=True)
    out = dict(schema="kathaya.asset_registry/2", generated=datetime.datetime.now(datetime.timezone.utc).isoformat(), assets=reg)
    json.dump(out, open(os.path.join(ROOT, "assets/registry/asset_registry.json"), "w"), indent=1, ensure_ascii=False)
    lic = dict(policy_source="engine/licensing/policy.py",
               summary={d: sum(1 for a in reg if a["policy_decision"] == d) for d in sorted({a["policy_decision"] for a in reg})},
               usable_in_films=[a["asset_id"] for a in reg if a["status"] == "USED"], evaluated_downloaded=[a["asset_id"] for a in reg if a["status"] == "DOWNLOADED_EVALUATED"],
               quarantined=[dict(asset_id=a["asset_id"], reason=a["policy_reason"]) for a in reg if a["policy_decision"] == "QUARANTINE"],
               rejected=[a["asset_id"] for a in reg if a["policy_decision"] == "REJECT"], attribution_required=[a["asset_id"] for a in reg if a.get("attribution_required")],
               share_alike=[a["asset_id"] for a in reg if a.get("share_alike")])
    json.dump(lic, open(os.path.join(ROOT, "assets/registry/license_report.json"), "w"), indent=1)
    print(json.dumps(lic, indent=1))
