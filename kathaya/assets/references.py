"""REFERENCE SEARCH for an AssetRequest. A web image is a REFERENCE, not a production asset. Candidates come from Wikimedia Commons (searchable without a key, licence + author + source per file), each classified by the
project's licence policy (`engine.licensing.decide`): only accepted licences may be turned into a production asset; anything else stays a reference the human can look at.
Thumbnails are downloaded into assets/references/<request id>/ (with a metadata JSON) for the approval screen; nothing enters the library before a human approves one."""
import hashlib
import json
import os
import re
import urllib.parse
import urllib.request

from engine.licensing import policy as licensing

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REF_DIR = os.path.join(ROOT, "assets/references")
API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "KathayaStudio/1.0 (asset reference search; local tool)"}
LICENCE_MAP = {"cc0": "cc0-1.0", "cc0 1.0": "cc0-1.0", "public domain": "cc0-1.0", "pd": "cc0-1.0", "pdm": "cc0-1.0", "cc by 4.0": "cc-by-4.0", "cc by 3.0": "cc-by-3.0", "cc by-sa 4.0": "cc-by-sa-4.0", "cc by-sa 3.0": "cc-by-sa-3.0",
               "cc by 2.0": "cc-by-2.0", "cc by-sa 2.0": "cc-by-sa-2.0", "cc by 2.5": "cc-by-2.5", "cc by-sa 2.5": "cc-by-sa-2.5"}


def _strip(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html or "")).strip()


def classify(short_name, author, source_url):
    """Commons licence name -> (policy decision, key, obligations). Public-domain / CC0 dedications count as cc0-1.0."""
    n = (short_name or "").lower().strip()
    key = LICENCE_MAP.get(n)
    if key is None:
        if n.startswith("public domain") or n.startswith("pd-") or n == "pd":
            key = "cc0-1.0"
        else:
            key = licensing.norm(short_name) or "unknown"                                    # e.g. 'CC BY-SA 4.0' -> 'cc-by-sa-4.0'
    attribution = f"{author or 'unknown author'}, {short_name}, via Wikimedia Commons ({source_url})"
    d = licensing.decide(key, attribution_text=attribution if key.startswith("cc-by") else None)
    # cc-by-2.x are not in the core policy list: accepted with attribution only when the licence is plainly CC BY (not SA / NC / ND)
    if d["decision"] == "QUARANTINE" and re.fullmatch(r"cc-by-[23]\.\d", key):
        d = dict(d, decision="ACCEPT_WITH_OBLIGATIONS", attribution_required=True, share_alike=False, attribution_text=attribution, reason="attribution required")
    return d, key, attribution


def _relevant(title, description, subject):
    toks = [t for t in re.findall(r"[a-z]{4,}", subject.lower())]
    hay = title.lower()                                                                        # the file name is a far better signal than the free-text description
    hit = sum(1 for t in set(toks) if t in hay)
    return hit >= min(2, len(set(toks)))


def _get(url, timeout=25):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()


def search(request, per_query=12, want=None):
    """-> up to `reference_count` candidates [{index, title, thumb, page_url, licence, author, size, production_ok, licence_reason, local_thumb}]"""
    want = want or max(3, int(request.get("reference_count", 3)))
    seen, cands = set(), []
    d = os.path.join(REF_DIR, request["id"])
    os.makedirs(d, exist_ok=True)
    for q in request["reference_queries"]:
        params = dict(action="query", format="json", generator="search", gsrsearch=q, gsrnamespace=6, gsrlimit=per_query, prop="imageinfo", iiprop="url|extmetadata|size|mime", iiurlwidth=900)
        try:
            data = json.loads(_get(API + "?" + urllib.parse.urlencode(params)))
        except Exception as e:                                                                  # noqa: BLE001 - a failed query is reported, the others still run
            cands.append(dict(error=f"search failed for '{q}': {e}"))
            continue
        for pg in sorted((data.get("query", {}).get("pages", {})).values(), key=lambda p: p.get("index", 0)):
            ii = (pg.get("imageinfo") or [{}])[0]
            if pg["title"] in seen or ii.get("mime") not in ("image/jpeg", "image/png") or ii.get("width", 0) < 900:
                continue
            md = ii.get("extmetadata", {})
            if not _relevant(pg["title"], _strip((md.get("ImageDescription") or {}).get("value", "")), request["subject"]):
                continue
            seen.add(pg["title"])
            lic = (md.get("LicenseShortName") or {}).get("value", "")
            author = _strip((md.get("Artist") or {}).get("value", ""))
            dec, key, attribution = classify(lic, author, ii.get("descriptionurl"))
            cands.append(dict(title=pg["title"], query=q, thumb=ii.get("thumburl"), full=ii.get("url"), page_url=ii.get("descriptionurl"), licence=lic, licence_key=key, author=author, width=ii.get("width"), height=ii.get("height"),
                              production_ok=dec["decision"] in ("ACCEPT", "ACCEPT_WITH_OBLIGATIONS"), licence_decision=dec["decision"], licence_reason=dec["reason"], attribution=attribution if dec.get("attribution_required") else None,
                              share_alike=bool(dec.get("share_alike")), description=_strip((md.get("ImageDescription") or {}).get("value", ""))[:200]))
    cands = [c for c in cands if "error" not in c]
    cands.sort(key=lambda c: (not c["production_ok"], c["share_alike"]))
    out = []
    for c in cands[:max(want, 3)]:
        try:
            fn = hashlib.sha1(c["thumb"].encode()).hexdigest()[:12] + ".jpg"
            open(os.path.join(d, fn), "wb").write(_get(c["thumb"]))
            c["local_thumb"] = os.path.relpath(os.path.join(d, fn), ROOT)
        except Exception as e:                                                                  # noqa: BLE001
            c["local_thumb"] = None
            c["thumb_error"] = str(e)
        out.append(dict(c, index=len(out)))
    json.dump(out, open(os.path.join(d, "candidates.json"), "w"), ensure_ascii=False, indent=1)
    return out
