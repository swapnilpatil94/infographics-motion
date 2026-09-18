"""Shared filesystem paths for the engine. No bpy dependency."""
import os

ENGINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(ENGINE_DIR)
MANIFESTS_DIR = os.path.join(PROJECT_ROOT, "manifests")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
PREVIEWS_DIR = os.path.join(OUTPUT_DIR, "previews")
FRAMES_DIR = os.path.join(OUTPUT_DIR, "frames")
RENDERS_DIR = os.path.join(OUTPUT_DIR, "renders")
ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")


def ensure_dirs():
    for d in (MANIFESTS_DIR, PREVIEWS_DIR, FRAMES_DIR, RENDERS_DIR):
        os.makedirs(d, exist_ok=True)
