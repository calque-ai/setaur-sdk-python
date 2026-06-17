import os
import time
from typing import Any, TYPE_CHECKING

from ._types import EventSeverity, EventSourceType, SpanKind

if TYPE_CHECKING:
    from ._client import _Client


class Span:
    """Context manager that records a timed span as an event on exit.

    Prefer constructing via :func:`setaur.span` rather than directly.

    Attributes:
        trace_id: 32-char hex string identifying the trace. Auto-generated unless
            supplied at construction. Readable inside the ``with`` block so it can
            be forwarded to child spans.
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
        self._parent_id   = parent_id
        self._data        = data
        self._attrs: dict[str, Any] = {}
        self._start_ns: int | None = None

        self.trace_id = trace_id or _new_trace_id()
        self.span_id  = _new_span_id()
        self.sequence_num: int = 0

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
        self._start_ns = time.time_ns()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._start_ns is None:
            raise RuntimeError("setaur.Span.__exit__ called without a matching __enter__")
        end_ns = time.time_ns()
        if exc_type is not None:
            self._attrs["span.error"] = f"{exc_type.__name__}: {exc_val}"
        # omit attrs from envelope when none were set
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


def _new_trace_id() -> str:
    return os.urandom(16).hex()


def _new_span_id() -> str:
    return os.urandom(8).hex()
