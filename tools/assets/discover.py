#!/usr/bin/env python3
"""Discover: list candidate sources (assets/sources.json), re-verify each one's license LIVE, print a decision table. No downloading."""
import json
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, ROOT)
from engine.licensing import policy


def main():
    src = json.load(open(os.path.join(ROOT, "assets/sources.json")))["sources"]
    rows = []
    for s in src:
        try:
            if s.get("repo"):
                lic, has_file, pushed = policy.github_license(s["repo"])
            else:
                lic, has_file, pushed = s["license"], True, None
            d = policy.decide(lic, s.get("kind", "asset"), has_file, s.get("attribution_text"))
        except Exception as e:
            d, lic, pushed = dict(decision="QUARANTINE", reason=f"lookup failed: {e}"), None, None
        rows.append((s["id"], lic, d["decision"], d["reason"][:70], pushed and pushed[:10]))
    w = max(len(r[0]) for r in rows)
    for r in rows:
        print(f"{r[0]:<{w}}  {str(r[1]):<14} {r[2]:<24} {r[4] or '':<10} {r[3]}")
    json.dump([dict(id=r[0], license=r[1], decision=r[2], reason=r[3]) for r in rows], open(os.path.join(ROOT, "assets/library/source_decisions.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
