#!/usr/bin/env python3
"""Bootstrap acquisition through the real pipeline: discover -> verify_license -> download -> checksum -> normalize -> tag -> register.
Acquires (a) a curated OpenMoji icon set (CC BY-SA 4.0, share-alike flagged) and (b) Noto Sans Devanagari (OFL-1.1) so on-screen Hindi text
no longer depends on a proprietary system font. Idempotent: existing sha256 hashes are not re-registered."""
import datetime
import json
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools/assets"))
import download as DL
import normalize as NM
import register as RG
from engine.assets import library
from engine.licensing import policy

NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()


def openmoji(curation):
    src = next(s for s in json.load(open(os.path.join(ROOT, "assets/sources.json")))["sources"] if s["id"] == "openmoji")
    out = []
    for code, (name, *tags) in curation.items():
        url = f"https://raw.githubusercontent.com/hfg-gmuend/openmoji/master/color/svg/{code}.svg"
        try:
            got = DL.download("openmoji", url, f"{name}_{code}.svg")
        except Exception as e:
            out.append((name, f"download failed: {e}"))
            continue
        norm_path = os.path.join(ROOT, "assets/props/icons", f"{name}.svg")
        nm = NM.normalize(os.path.join(ROOT, got["path"]), norm_path, tags)
        rec = dict(id=f"icon_openmoji_{name}", type="icon", style="openmoji-flat-color", tags=["icon", "prop", "share_alike"] + list(tags), path=os.path.relpath(norm_path, ROOT),
                   source="OpenMoji", source_url="https://openmoji.org/", download_url=url, author=src["author"], license="CC-BY-SA-4.0",
                   attribution_text=src["attribution_text"], proof_url="https://github.com/hfg-gmuend/openmoji/blob/master/LICENSE.txt",
                   sha256=library.sha256_file(norm_path), downloaded_at=NOW)
        out.append(RG.register(rec, got["decision"]))
    return out


def noto():
    src = next(s for s in json.load(open(os.path.join(ROOT, "assets/sources.json")))["sources"] if s["id"] == "noto_sans_devanagari")
    url = "https://raw.githubusercontent.com/google/fonts/main/ofl/notosansdevanagari/NotoSansDevanagari%5Bwdth%2Cwght%5D.ttf"
    got = DL.download("noto_sans_devanagari", url, "NotoSansDevanagari-VF.ttf")
    dst = os.path.join(ROOT, "assets/typography/NotoSansDevanagari-VF.ttf")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    os.replace(os.path.join(ROOT, got["path"]), dst)
    rec = dict(id="font_noto_sans_devanagari", type="typography", tags=["font", "devanagari", "variable"], path=os.path.relpath(dst, ROOT), source="Google Fonts",
               source_url=src["url"], download_url=url, author=src["author"], license="OFL-1.1", attribution_text=src["attribution_text"], proof_url=src["proof_url"],
               sha256=library.sha256_file(dst), downloaded_at=NOW)
    return RG.register(rec, policy.decide("OFL-1.1", "asset", True, src["attribution_text"]))


if __name__ == "__main__":
    print(noto())
    cur = json.load(open(sys.argv[1]))
    res = openmoji(cur)
    print(len(res), "icons processed;", sum(1 for r in res if isinstance(r, tuple) and len(r) == 3), "registered")
    for r in res[:5]:
        print(r)
