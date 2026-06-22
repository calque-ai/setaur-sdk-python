from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._span import Span

# Tracks the innermost active Span for the current thread/task.
_active_span: ContextVar["Span | None"] = ContextVar("_active_span", default=None)


def get_active_span() -> "Span | None":
    """Return the currently active Span, or None if outside a span context."""
    return _active_span.get()
