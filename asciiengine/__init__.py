"""ASCII Engine - a game engine designed to be operated by AI agents.

Start with ``AI_GUIDE.md`` in the repository root. Everything is controllable
programmatically (Python API, JSON commands, or the ``python -m asciiengine`` CLI).
"""
__version__ = "0.2.0"

from .core.errors import EngineError
from .core.kinds import KindDef, KindRegistry, default_kinds
from .core.canvas import Canvas, Cell

__all__ = ["EngineError", "KindDef", "KindRegistry", "default_kinds", "Canvas", "Cell", "__version__"]
