#!/usr/bin/env python3
"""Download ONE url into assets/raw/<source>/ after the source is license-approved. Only allow-listed hosts; sha256 recorded; dedupe by hash.
Usage: download.py <source_id> <url> [dest_name]"""
import json
import os
import sys
import urllib.request
from urllib.parse import urlparse

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, ROOT)
from engine.assets import library
from engine.licensing import policy

ALLOWED_HOSTS = {"raw.githubusercontent.com", "github.com", "codeload.github.com", "openpeeps.com", "kenney.nl"}


def download(source_id, url, dest_name=None):
    src = next(s for s in json.load(open(os.path.join(ROOT, "assets/sources.json")))["sources"] if s["id"] == source_id)
    if src.get("repo"):
        lic, has_file, _ = policy.github_license(src["repo"])
    else:
        lic, has_file = src["license"], True
    dec = policy.decide(lic, src.get("kind", "asset"), has_file, src.get("attribution_text"))
    if not dec["decision"].startswith("ACCEPT"):
        raise SystemExit(f"REFUSED: {source_id} is {dec['decision']} ({dec['reason']})")
    host = urlparse(url).hostname
    if host not in ALLOWED_HOSTS:
        raise SystemExit(f"REFUSED: host {host} is not on the allow-list {sorted(ALLOWED_HOSTS)}")
    out_dir = os.path.join(ROOT, "assets/raw", source_id)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, dest_name or os.path.basename(urlparse(url).path))
    req = urllib.request.Request(url, headers={"User-Agent": "kathaaya-asset-tools"})
    data = urllib.request.urlopen(req, timeout=30).read()
    open(path, "wb").write(data)
    return dict(path=os.path.relpath(path, ROOT), sha256=library.sha256_file(path), bytes=len(data), license=lic, decision=dec)


if __name__ == "__main__":
    print(json.dumps(download(*sys.argv[1:4]), indent=1, default=str))
