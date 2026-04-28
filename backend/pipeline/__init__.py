"""E2E pipeline orchestration package."""

from pipeline.models import FinalScoreTimeline, PipelineRun
from pipeline.score_merger import ScoreMerger

__all__ = [
    "FinalScoreTimeline",
    "PipelineRun",
    "ScoreMerger",
]


def get_orchestrator(*args, **kwargs):
    """Lazy import to avoid pulling in FastAPI at import time."""
    from pipeline.orchestrator import PipelineOrchestrator
    return PipelineOrchestrator(*args, **kwargs)
