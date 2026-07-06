import threading
from collections import defaultdict
from typing import Any
from ._types import SourceType, EventSourceType, EventSeverity, SpanKind

class EnvelopeBuilder:
    def __init__(self):
        self._seq: defaultdict[str, int] = defaultdict(int)
        self._lock = threading.Lock()

    def sensor(self, source_id: str, source_type: SourceType, timestamp_ns: int, data: dict) -> dict:
        key = f"sensor:{source_id}"
        with self._lock:
            self._seq[key] += 1
            seq = self._seq[key]
        return {
            'timestamp_ns': timestamp_ns,
            'source_id':    source_id,
            'source_type':  str(source_type),
            'sequence_num': seq,
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
        with self._lock:
            self._seq[key] += 1
            seq = self._seq[key]
        envelope: dict[str, Any] = {
            'start_ns':     start_ns,
            'source_id':    source_id,
            'source_type':  str(source_type),
            'event_type':   event_type,
            'severity':     str(severity),
            'message':      message,
            'kind':         str(kind),
            'sequence_num': seq,
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

    def log(
        self,
        component: str,
        timestamp_ns: int,
        severity_text: str,
        logger_name: str,
        message: str,
        *,
        firmware_version: str | None = None,
        source_file: str | None = None,
        source_line: int | None = None,
        source_function: str | None = None,
        trace_id: str | None = None,
        span_id: str | None = None,
        attrs: dict[str, Any] | None = None,
    ) -> dict:
        key = f"log:{component}"
        with self._lock:
            self._seq[key] += 1
            seq = self._seq[key]
        envelope: dict[str, Any] = {
            'timestamp_ns':  timestamp_ns,
            'severity_text': severity_text,
            'message':       message,
            'sequence_num':  seq,
        }
        if logger_name:
            envelope['logger_name'] = logger_name
        if component:
            envelope['component'] = component
        if firmware_version:
            envelope['firmware_version'] = firmware_version
        if source_file:
            envelope['source_file'] = source_file
        if source_line:
            envelope['source_line'] = source_line
        if source_function:
            envelope['source_function'] = source_function
        if trace_id is not None:
            envelope['trace_id'] = trace_id
        if span_id is not None:
            envelope['span_id'] = span_id
        if attrs:
            envelope['attrs'] = attrs
        return envelope