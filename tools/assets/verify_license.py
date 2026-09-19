#!/usr/bin/env python3
"""Verify a source's license against the policy. Usage: verify_license.py <github owner/repo> [--kind code|asset] | verify_license.py --spdx CC0-1.0"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from engine.licensing import policy


def main(argv):
    kind = "code" if "--kind" in argv and argv[argv.index("--kind") + 1] == "code" else "asset"
    if argv and argv[0] == "--spdx":
        out = policy.decide(argv[1], kind, True, argv[2] if len(argv) > 2 and not argv[2].startswith("--") else None)
    else:
        lic, has_file, pushed = policy.github_license(argv[0])
        out = dict(policy.decide(lic, kind, has_file), repo=argv[0], spdx=lic, pushed_at=pushed)
    print(json.dumps(out, indent=1))
    return 0 if out["decision"].startswith("ACCEPT") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
