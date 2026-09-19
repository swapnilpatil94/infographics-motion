"""STORY stage facade: story.md + narration segments -> validated contract -> story analysis (characters, locations, phases, psychology, money events)."""
from engine.factory.contract import load as load_contract        # noqa: F401
from engine.factory.analysis import analyze, rederive              # noqa: F401
from engine.factory.state import continuity_check                  # noqa: F401
