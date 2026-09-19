"""COMPOSITING stage: the per-frame layer compositor lives in engine.shorts (layers/scene/post); this package holds the
delivery-format compositing (aspect-ratio derivatives)."""
from engine.compositing.reframe import reframe_16x9, reframe_vertical_window  # noqa: F401
