"""ASSET BUILDER: reference -> stylised reconstruction -> Kathaya production asset (stored permanently in assets/library/kathaya, registered in the catalog, attributed).

The web image is only a REFERENCE. The production asset is a deterministic Kathaya rendering of it: perspective-agnostic portrait crop at the strongest vertical structure, edge-preserving smoothing, palette quantisation, ink outlines
in Kathaya's line colour, a time-of-day grade and paper grain - the same look as the hand-drawn sets, not the photograph. What it does NOT do: it does not model the building in 3D and it is a single backdrop plane (the parallax is
that of the flat layer); this is stated in the asset record (`fidelity`)."""
import hashlib
import json
import os
import re
import time
import urllib.request

import cv2
import numpy as np

from kathaya.assets import library_env, references as REF
from kathaya.assets.catalog import LIBRARY, norm
from kathaya import schemas

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BUILDER_VERSION = "photo-backdrop-1"
W, H = 1400, 1700                                                                          # backdrop size in world units (x -160..1240, y -160..1540)
INK = (26, 18, 19)                                                                         # BGR of #13121a


def slug(s):
    return re.sub(r"[^a-z0-9]+", "_", norm(s)).strip("_")[:40] or "asset"


def stylise(src_bgr, time_of_day="day", seed=7):
    h, w = src_bgr.shape[:2]
    tw = int(round(h * W / H))                                                             # crop to the portrait aspect of the backdrop, centred on the strongest vertical structure
    if tw < w:
        g = cv2.Sobel(cv2.cvtColor(src_bgr, cv2.COLOR_BGR2GRAY), cv2.CV_32F, 1, 0)
        col = np.abs(g).sum(axis=0)
        k = np.convolve(col, np.ones(tw), mode="valid")
        x0 = int(np.argmax(k))
        src_bgr = src_bgr[:, x0:x0 + tw]
    else:
        th = int(round(w * H / W))
        y0 = max(0, (h - th) // 2)
        src_bgr = src_bgr[y0:y0 + th]
    img = cv2.resize(src_bgr, (W, H), interpolation=cv2.INTER_AREA)
    sm = img
    for _ in range(3):
        sm = cv2.bilateralFilter(sm, 9, 60, 9)
    small = cv2.resize(sm, (W // 4, H // 4), interpolation=cv2.INTER_AREA).reshape(-1, 3).astype(np.float32)
    cv2.setRNGSeed(seed)
    _, lab, cen = cv2.kmeans(small, 12, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0), 1, cv2.KMEANS_PP_CENTERS)
    q = cen[lab.flatten()].reshape(H // 4, W // 4, 3).astype(np.uint8)
    q = cv2.resize(q, (W, H), interpolation=cv2.INTER_NEAREST)
    q = cv2.medianBlur(q, 5)
    edges = cv2.Canny(cv2.cvtColor(sm, cv2.COLOR_BGR2GRAY), 60, 140)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8))
    out = q.astype(np.float32)
    m = (edges > 0)[..., None]
    out = np.where(m, out * 0.15 + np.array(INK, np.float32) * 0.85, out)
    hsv = cv2.cvtColor(np.clip(out, 0, 255).astype(np.uint8), cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[..., 1] *= 0.82
    out = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR).astype(np.float32)
    if time_of_day == "night":
        out = out * np.array([0.62, 0.50, 0.42], np.float32) + np.array([18, 10, 6], np.float32)
    elif time_of_day == "dusk":
        out = out * np.array([0.85, 0.80, 0.92], np.float32)
    rng = np.random.default_rng(seed)
    out = out + rng.normal(0, 3.0, out.shape[:2])[..., None]
    yy = np.linspace(0, 1, H)[:, None, None]
    out = out * (1.0 - 0.28 * (yy ** 3))                                                   # the base of the image sinks into the ground plane
    return np.clip(out, 0, 255).astype(np.uint8)


def _attrib_line(asset):
    return f"- **{asset['name']}** (`{asset['id']}`): {asset['derived_from']['attribution'] or 'no attribution required'} - source: {asset['derived_from']['page_url']} - licence: {asset['derived_from']['licence']}; the asset is a stylised derivative{' (share-alike)' if asset['derived_from'].get('share_alike') else ''}.\n"


def build_from_request(pid, rid, reference, log=print, progress=None):
    """approved reference -> library asset. Returns the asset record."""
    from kathaya import pipeline as KP
    req = KP._read(pid, f"requests/{rid}.json")
    if req["type"] != "environment":
        raise ValueError(f"the builder creates environments; a '{req['type']}' request needs its own builder")
    if not reference.get("production_ok"):
        raise ValueError(f"licence not accepted for production: {reference.get('licence_reason')}")
    tod = (req.get("required_conditions") or {}).get("time_of_day") or "day"
    aid = "env_lib_" + slug(req["subject"])
    d = os.path.join(LIBRARY, aid)
    os.makedirs(d, exist_ok=True)
    if progress:
        progress(0.1, "downloading the approved reference")
    raw = REF._get(reference["full"] if reference.get("full") else reference["thumb"], timeout=90)
    if len(raw) > 40 * 1024 * 1024:
        raw = REF._get(reference["thumb"], timeout=60)
    ref_dir = os.path.join(REF.REF_DIR, rid)
    os.makedirs(ref_dir, exist_ok=True)
    ref_path = os.path.join(ref_dir, "approved_" + hashlib.sha1(raw).hexdigest()[:12] + ".jpg")
    open(ref_path, "wb").write(raw)
    src = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if src is None:
        raise ValueError("the reference image could not be decoded")
    if src.shape[1] > 2400:
        src = cv2.resize(src, (2400, int(src.shape[0] * 2400 / src.shape[1])), interpolation=cv2.INTER_AREA)
    if progress:
        progress(0.4, "stylising: crop, smoothing, palette, ink outlines")
    out = stylise(src, tod)
    bp = os.path.join(d, "backdrop.png")
    cv2.imwrite(bp, out)
    floor = "#%02x%02x%02x" % tuple(int(x) for x in out[-40:, :, ::-1].reshape(-1, 3).mean(axis=0) * 0.85)
    loc = "lib_" + slug(req["subject"])
    is_lm = req.get("asset_kind") == "real_landmark"
    subjects = sorted({norm(req["subject"]), norm(req["subject"].split(" at ")[0])})
    asset = dict(id=aid, type="environment", name=req["subject"], tags=sorted({*norm(req["subject"]).split(), "generated", "reference-derived", *(["landmark"] if is_lm else [])}), subjects=subjects, landmark=req["subject"].split(" at ")[0] if is_lm else None,
                 source="Kathaya asset builder from an approved reference", license=reference["licence"], local_path=os.path.relpath(d, ROOT), status="production_ready",
                 supports=dict(time_of_day=[tod], default_time=tod, kind="real_landmark" if is_lm else "generic"), anchors={}, capabilities=["stand", "walk"],
                 binding=dict(location=loc, family="photo_backdrop", backdrop=os.path.relpath(bp, ROOT), floor=floor),
                 derived_from=dict(request=rid, project=pid, title=reference["title"], page_url=reference["page_url"], licence=reference["licence"], licence_key=reference["licence_key"], author=reference["author"], attribution=reference.get("attribution"),
                                   share_alike=reference.get("share_alike"), reference_file=os.path.relpath(ref_path, ROOT), reference_sha256=hashlib.sha256(raw).hexdigest(), approved_by="user"),
                 builder=dict(version=BUILDER_VERSION, built_at=time.strftime("%Y-%m-%dT%H:%M:%S"), fidelity="stylised single-plane backdrop from one reference photograph; no 3D reconstruction; the parallax is that of a flat layer"),
                 backdrop_sha256=hashlib.sha256(open(bp, "rb").read()).hexdigest())
    bad = schemas.validate("AssetCatalog", dict(schema="kathaya.asset_catalog/1", assets=[asset]))
    if bad:
        raise ValueError(f"asset record invalid: {bad[:2]}")
    json.dump(asset, open(os.path.join(d, "asset.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    att = os.path.join(ROOT, "assets/licenses/ATTRIBUTIONS.md")
    head = "# Attributions\n\nAssets created by the Kathaya asset builder from approved reference images. Attribution is kept for every asset whose licence requires it.\n\n"
    cur = open(att, encoding="utf-8").read() if os.path.exists(att) else head
    if f"(`{aid}`)" not in cur:
        open(att, "w", encoding="utf-8").write(cur.rstrip("\n") + "\n" + _attrib_line(asset))
    library_env.register_all()
    if progress:
        progress(0.9, "registered in the asset catalog")
    log(f"[builder] {aid} built from '{reference['title']}' ({reference['licence']})")
    return asset
