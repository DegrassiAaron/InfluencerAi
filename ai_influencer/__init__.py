"""Top-level package for InfluencerAI components."""

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = ["pipeline"]


def __getattr__(name: str) -> Any:
    """Lazily expose subpackages while keeping import times minimal."""

    if name in __all__:
        module = import_module(f"{__name__}.{name}")
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if TYPE_CHECKING:
    # Help static analyzers understand the available submodules without
    # triggering runtime imports.
    from . import pipeline  # noqa: F401

"""Top-level package for the Influencer AI tooling.

This module exposes the primary subpackages so that `import ai_influencer`
works for both runtime code and tests without needing to know the internal
layout of the repository.
"""

from . import scripts, webapp  # re-exported for convenient discovery

__all__ = ["scripts", "webapp"]
