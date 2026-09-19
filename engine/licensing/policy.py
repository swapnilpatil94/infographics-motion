"""License policy (spec sec. 15/35/45): one function decides what may enter the library.

ACCEPT                    CC0, MIT, BSD, Apache-2.0, ISC, Unlicense, own work
ACCEPT_WITH_OBLIGATIONS   CC-BY-4.0 (attribution text stored), CC-BY-SA-4.0 (attribution + SHARE-ALIKE flag)
REJECT                    non-commercial (NC) or no-derivatives (ND) terms
QUARANTINE                unknown / unasserted / README-only claims / GPL & AGPL CODE (never vendored into the core)
"""
import json
import re
import urllib.request

ACCEPT = {"ofl-1.1", "cc0-1.0", "cc0", "mit", "bsd-2-clause", "bsd-3-clause", "apache-2.0", "isc", "unlicense", "own-work", "0bsd"}
OBLIGATIONS = {"cc-by-4.0": dict(attribution_required=True, share_alike=False), "cc-by-sa-4.0": dict(attribution_required=True, share_alike=True),
               "cc-by-3.0": dict(attribution_required=True, share_alike=False)}
COPYLEFT_CODE = {"gpl-2.0", "gpl-3.0", "agpl-3.0", "lgpl-3.0", "gpl-3.0-or-later", "gpl-2.0-or-later"}


def norm(lic):
    return (lic or "").strip().lower().replace(" ", "-")


def decide(lic, kind="asset", has_license_file=True, attribution_text=None):
    """-> dict(decision, commercial_use, attribution_required, share_alike, modification_allowed, reason). kind: 'asset' | 'code'."""
    l = norm(lic)
    base = dict(license=lic, commercial_use=True, attribution_required=False, share_alike=False, modification_allowed=True)
    if not l or l in ("none", "noassertion", "unknown", "other") or not has_license_file:
        return dict(base, decision="QUARANTINE", commercial_use=None, reason="license unknown/unasserted or no license file (README claims are not proof)")
    if re.search(r"(^|-)nc(-|$)", l) or "noncommercial" in l or "non-commercial" in l or "no-commercial" in l or re.search(r"(^|-)(nd|noderivs?)(-|$)", l):
        return dict(base, decision="REJECT", commercial_use=False, reason="non-commercial / no-derivatives terms")
    if l in ACCEPT:
        return dict(base, decision="ACCEPT", reason="permissive")
    if l in OBLIGATIONS:
        o = OBLIGATIONS[l]
        if o["attribution_required"] and not attribution_text:
            return dict(base, decision="QUARANTINE", **o, reason="attribution required but no attribution text recorded")
        return dict(base, decision="ACCEPT_WITH_OBLIGATIONS", **o, attribution_text=attribution_text,
                    reason="share-alike: derived artwork must be released under the same license" if o["share_alike"] else "attribution required")
    if l in COPYLEFT_CODE:
        if kind == "code":
            return dict(base, decision="QUARANTINE", share_alike=True, reason="copyleft CODE must not be vendored into the core; reimplement concepts or run as an external tool")
        return dict(base, decision="QUARANTINE", share_alike=True, reason="copyleft license on assets needs explicit review")
    return dict(base, decision="QUARANTINE", commercial_use=None, reason=f"unrecognised license '{lic}'")


def github_license(repo, timeout=20):
    """Live license lookup for owner/repo -> (spdx_id or None, has_license_file, pushed_at)."""
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}", headers={"User-Agent": "kathaaya-asset-tools"})
    d = json.load(urllib.request.urlopen(req, timeout=timeout))
    lic = (d.get("license") or {}).get("spdx_id")
    return lic, bool(d.get("license")), d.get("pushed_at")
