"""CopycatAI pipeline implementation exposing primary entrypoints."""
from .copycat import (
    CopycatAIPipeline,
    Document,
    EvolutionResult,
    PersonaProfile,
    PipelineResult,
    StylometryMetrics,
    TopicCluster,
    lang_fix,
    sponsored_detector,
    evolution_tracker,
)

__all__ = [
    "CopycatAIPipeline",
    "Document",
    "EvolutionResult",
    "PersonaProfile",
    "PipelineResult",
    "StylometryMetrics",
    "TopicCluster",
    "lang_fix",
    "sponsored_detector",
    "evolution_tracker",
]
