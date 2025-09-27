"""Top-level package for the Influencer AI tooling.

This module exposes the primary subpackages so that `import ai_influencer`
works for both runtime code and tests without needing to know the internal
layout of the repository.
"""

from . import scripts, webapp  # re-exported for convenient discovery

__all__ = ["scripts", "webapp"]
