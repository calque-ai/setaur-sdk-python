from typing import Any
from ._types import SourceType, EventSourceType, EventSeverity, SpanKind
from ._client import init, get_client


def sensor(
    source_id: str,
    source_type: SourceType,
    timestamp_ns: int,
    data: dict,
) -> None:
    get_client().sensor(source_id, source_type, timestamp_ns, data)


def event(
    source_id: str,
    event_type: str,
    message: str,
    severity: EventSeverity,
    *,
    start_ns: int | None = None,
    end_ns: int = 0,
    source_type: EventSourceType = EventSourceType.USER,
    kind: SpanKind = SpanKind.UNSPECIFIED,
    trace_id: str | None = None,
    span_id: str | None = None,
    parent_id: str | None = None,
    attrs: dict[str, Any] | None = None,
    data: Any = None,
) -> None:
    get_client().event(
        source_id, event_type, message, severity,
        source_type=source_type, start_ns=start_ns, end_ns=end_ns, kind=kind,
        trace_id=trace_id, span_id=span_id, parent_id=parent_id,
        attrs=attrs, data=data,
    )


__all__ = [
    "SourceType", "EventSourceType", "EventSeverity", "SpanKind",
    "init", "sensor", "event",
]
