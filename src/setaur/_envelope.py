from collections import defaultdict
from typing import Any
from ._types import SourceType, EventSourceType, EventSeverity, SpanKind

class EnvelopeBuilder:
    def __init__(self):
        self._seq: defaultdict[str, int] = defaultdict(int)

    def sensor(self, source_id: str, source_type: SourceType, timestamp_ns: int, data: dict) -> dict:
        key = f"sensor:{source_id}"
        self._seq[key] += 1
        return {
            'timestamp_ns': timestamp_ns,
            'source_id':    source_id,
            'source_type':  str(source_type),
            'sequence_num': self._seq[key],
            'data':         data,
        }

    def event(
        self,
        source_id: str,
        event_type: str,
        message: str,
        severity: EventSeverity,
        start_ns: int,
        *,
        end_ns: int = 0,
        source_type: EventSourceType = EventSourceType.USER,
        kind: SpanKind = SpanKind.UNSPECIFIED,
        trace_id: str | None = None,
        span_id: str | None = None,
        parent_id: str | None = None,
        attrs: dict[str, Any] | None = None,
        data: Any = None,
    ) -> dict:
        key = f"event:{source_id}"
        self._seq[key] += 1
        envelope: dict[str, Any] = {
            'start_ns':     start_ns,
            'source_id':    source_id,
            'source_type':  str(source_type),
            'event_type':   event_type,
            'severity':     str(severity),
            'message':      message,
            'kind':         str(kind),
            'sequence_num': self._seq[key],
        }
        if end_ns:
            envelope['end_ns'] = end_ns
        if trace_id is not None:
            envelope['trace_id'] = trace_id
        if span_id is not None:
            envelope['span_id'] = span_id
        if parent_id is not None:
            envelope['parent_id'] = parent_id
        if attrs:
            envelope['attrs'] = attrs
        if data is not None:
            envelope['data'] = data
        return envelope