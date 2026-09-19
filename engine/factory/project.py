"""Self-contained project folder layout (one run -> one folder; everything needed to re-render lives inside)."""
import os
import re
import shutil

from engine.shorts.raster import ROOT

SUBDIRS = ["final/shorts", "final/reels", "project", "assets/previews", "render/shots", "render/composited", "render/final", "qc", "logs"]


def slug(title):
    ascii_part = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    return ascii_part[:40] or "project"


class Project:
    def __init__(self, name, root=None):
        self.name = name
        self.dir = os.path.join(root or os.path.join(ROOT, "output", "projects"), name)
        for d in SUBDIRS:
            os.makedirs(os.path.join(self.dir, d), exist_ok=True)

    def path(self, *parts):
        return os.path.join(self.dir, *parts)

    def write_json(self, rel, obj):
        import json
        p = self.path(rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        json.dump(obj, open(p, "w"), ensure_ascii=False, indent=2)
        return p

    def read_json(self, rel):
        import json
        return json.load(open(self.path(rel)))

    def copy_in(self, src, rel):
        if src and os.path.exists(src):
            shutil.copy(src, self.path(rel))
            return self.path(rel)
