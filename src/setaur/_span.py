import os
import time
from typing import Any, TYPE_CHECKING

from ._span_context import _active_span, get_active_span
from ._types import EventSeverity, EventSourceType, SpanKind

if TYPE_CHECKING:
    from ._client import _Client

__all__ = ["Span", "Tracer", "get_active_span"]


class Span:
    """Context manager that records a timed span as an event on exit.

    Prefer constructing via :meth:`Tracer.span` rather than directly.

    Trace context (``trace_id``, ``parent_id``) is resolved automatically from
    the enclosing span when not supplied explicitly, so nested spans wire
    themselves into the correct trace without any manual bookkeeping.

    Attributes:
        trace_id: 32-char hex string identifying the trace. Inherited from the
            enclosing span when not supplied, or auto-generated for root spans.
        span_id: 16-char hex string uniquely identifying this span. Always auto-generated.
        sequence_num: Sequence number assigned when the span is published. Zero until
            the ``with`` block exits.
    """

    def __init__(
        self,
        client: "_Client",
        source_id: str,
        event_type: str,
        message: str,
        severity: EventSeverity,
        *,
        source_type: EventSourceType = EventSourceType.USER,
        kind: SpanKind = SpanKind.UNSPECIFIED,
        trace_id: str | None = None,
        parent_id: str | None = None,
        data: Any = None,
    ) -> None:
        self._client      = client
        self._source_id   = source_id
        self._event_type  = event_type
        self._message     = message
        self._severity    = severity
        self._source_type = source_type
        self._kind        = kind
        self._data        = data
        self._attrs: dict[str, Any] = {}
        self._start_ns: int | None  = None
        self._ctx_token             = None

        # Inherit trace context from the enclosing span unless overridden.
        parent = _active_span.get()
        self.trace_id = trace_id or (parent.trace_id if parent else _new_trace_id())
        self._parent_id = parent_id or (parent.span_id if parent else None)
        self.span_id    = _new_span_id()
        self.sequence_num: int = 0

    def __repr__(self) -> str:
        tid = self.trace_id[:8] if self.trace_id else "none"
        return (
            f"Span(source_id={self._source_id!r}, event_type={self._event_type!r}, "
            f"trace_id={tid!r}..., span_id={self.span_id!r})"
        )

    def set_attr(self, key: str, value: Any) -> None:
        """Attach a typed attribute to this span.

        Can be called any number of times inside the ``with`` block before the
        span is published. Overwrites the previous value if ``key`` already exists.

        Args:
            key: Attribute name (e.g. ``"waypoint_id"``).
            value: Attribute value. Any CBOR-serializable type is accepted.
        """
        self._attrs[key] = value

    def __enter__(self) -> "Span":
        self._start_ns  = time.time_ns()
        self._ctx_token = _active_span.set(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._start_ns is None:
            raise RuntimeError("setaur.Span.__exit__ called without a matching __enter__")

        # Restore the previous active span before publishing so any events emitted
        # inside the publish path don't incorrectly inherit this span as parent.
        _active_span.reset(self._ctx_token)

        end_ns = time.time_ns()
        if exc_type is not None:
            self._attrs["span.error"] = f"{exc_type.__name__}: {exc_val}"

        attrs = self._attrs if self._attrs else None
        self.sequence_num = self._client.event(
            self._source_id,
            self._event_type,
            self._message,
            self._severity,
            start_ns=self._start_ns,
            end_ns=end_ns,
            source_type=self._source_type,
            kind=self._kind,
            trace_id=self.trace_id,
            span_id=self.span_id,
            parent_id=self._parent_id,
            attrs=attrs,
            data=self._data,
        )


class Tracer:
    """A component-scoped handle for emitting spans and events.

    Obtain one via :func:`setaur.get_tracer`. All spans and events emitted
    through a tracer share the same ``source_id`` without repeating it at
    every call site.

    Example::

        nav = setaur.get_tracer("nav")

        with nav.span("path_planning", "Plan route to dock") as s:
            s.set_attr("goal", "charging_dock")
            do_planning()

        nav.info("startup", "Navigation system ready")
    """

    def __init__(self, client: "_Client", source_id: str) -> None:
        self._client    = client
        self._source_id = source_id

    def __repr__(self) -> str:
        return f"Tracer(source_id={self._source_id!r})"

    def span(
        self,
        event_type: str,
        message: str,
        severity: EventSeverity = EventSeverity.INFO,
        *,
        source_type: EventSourceType = EventSourceType.USER,
        kind: SpanKind = SpanKind.UNSPECIFIED,
        trace_id: str | None = None,
        parent_id: str | None = None,
        data: Any = None,
    ) -> Span:
        """Return a :class:`Span` context manager scoped to this tracer's ``source_id``.

        Trace context is inherited automatically from any enclosing span.
        Pass ``trace_id`` / ``parent_id`` explicitly only to link across
        thread or process boundaries.
        """
        return Span(
            self._client, self._source_id, event_type, message, severity,
            source_type=source_type, kind=kind,
            trace_id=trace_id, parent_id=parent_id, data=data,
        )

    def event(
        self,
        event_type: str,
        message: str,
        severity: EventSeverity,
        *,
        attrs: dict[str, Any] | None = None,
        data: Any = None,
        source_type: EventSourceType = EventSourceType.USER,
        kind: SpanKind = SpanKind.UNSPECIFIED,
    ) -> int:
        """Publish an event scoped to this tracer's ``source_id``.

        Automatically inherits ``trace_id`` and ``parent_id`` from the active
        span context so events emitted inside a ``with tracer.span(...)`` block
        are linked to the enclosing trace without any manual wiring.
        """
        parent = _active_span.get()
        return self._client.event(
            self._source_id, event_type, message, severity,
            source_type=source_type, kind=kind,
            trace_id=parent.trace_id if parent else None,
            parent_id=parent.span_id if parent else None,
            attrs=attrs, data=data,
        )

    def info(
        self,
        event_type: str,
        message: str,
        *,
        attrs: dict[str, Any] | None = None,
        data: Any = None,
        source_type: EventSourceType = EventSourceType.USER,
        kind: SpanKind = SpanKind.UNSPECIFIED,
    ) -> int:
        """Publish an INFO event. See :meth:`event` for parameter docs."""
        return self.event(event_type, message, EventSeverity.INFO,
                          attrs=attrs, data=data, source_type=source_type, kind=kind)

    def warning(
        self,
        event_type: str,
        message: str,
        *,
        attrs: dict[str, Any] | None = None,
        data: Any = None,
        source_type: EventSourceType = EventSourceType.USER,
        kind: SpanKind = SpanKind.UNSPECIFIED,
    ) -> int:
        """Publish a WARNING event. See :meth:`event` for parameter docs."""
        return self.event(event_type, message, EventSeverity.WARNING,
                          attrs=attrs, data=data, source_type=source_type, kind=kind)

    def error(
        self,
        event_type: str,
        message: str,
        *,
        attrs: dict[str, Any] | None = None,
        data: Any = None,
        source_type: EventSourceType = EventSourceType.USER,
        kind: SpanKind = SpanKind.UNSPECIFIED,
    ) -> int:
        """Publish an ERROR event. See :meth:`event` for parameter docs."""
        return self.event(event_type, message, EventSeverity.ERROR,
                          attrs=attrs, data=data, source_type=source_type, kind=kind)

    def critical(
        self,
        event_type: str,
        message: str,
        *,
        attrs: dict[str, Any] | None = None,
        data: Any = None,
        source_type: EventSourceType = EventSourceType.USER,
        kind: SpanKind = SpanKind.UNSPECIFIED,
    ) -> int:
        """Publish a CRITICAL event. See :meth:`event` for parameter docs."""
        return self.event(event_type, message, EventSeverity.CRITICAL,
                          attrs=attrs, data=data, source_type=source_type, kind=kind)


def _new_trace_id() -> str:
    return os.urandom(16).hex()


def _new_span_id() -> str:
    return os.urandom(8).hex()
