from typing import Any
from ._types import SourceType, EventSourceType, EventSeverity, SpanKind
from ._client import init, get_client
from ._span import Span


def sensor(
    source_id: str,
    source_type: SourceType,
    timestamp_ns: int,
    data: dict,
) -> int:
    """Publish a sensor reading.

    Args:
        source_id: Unique identifier for the sensor (e.g. ``"lidar_front"``).
        source_type: Category of the sensor (``SourceType.SENSOR``, ``STATE_MACHINE``, etc.).
        timestamp_ns: Acquisition timestamp in nanoseconds (use ``time.time_ns()``).
        data: Sensor payload as a dict. Must be CBOR-serializable.

    Returns:
        Monotonically increasing sequence number for this source, useful for
        detecting dropped messages on the receiving side.

    Raises:
        TypeError: If ``data`` contains a type that cannot be CBOR-encoded.
        RuntimeError: If ``setaur.init()`` has not been called.
    """
    return get_client().sensor(source_id, source_type, timestamp_ns, data)


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
) -> int:
    """Publish a single event.

    Args:
        source_id: Component emitting the event (e.g. ``"navigation_controller"``).
        event_type: Machine-readable event class (e.g. ``"state_transition"``).
        message: Human-readable description of what happened.
        severity: Importance level — ``INFO``, ``WARNING``, ``ERROR``, or ``CRITICAL``.
        start_ns: Event timestamp in nanoseconds. Defaults to ``time.time_ns()`` when omitted.
        end_ns: End timestamp for a span event. ``0`` means instantaneous (point-in-time).
        source_type: Origin of the event. Defaults to ``EventSourceType.USER``.
        kind: Operation kind hint for the visualizer (``SENSOR``, ``ACTUATOR``, etc.).
        trace_id: 32-char hex string grouping related spans into one operation.
        span_id: 16-char hex string uniquely identifying this span.
        parent_id: ``span_id`` of the parent span; ``None`` means root.
        attrs: Typed key-value metadata (e.g. ``{"motor_id": "m2", "current_amps": 12.5}``).
        data: Arbitrary CBOR-serializable payload for large or unstructured data.

    Returns:
        Monotonically increasing sequence number for this source.

    Raises:
        TypeError: If ``data`` or ``attrs`` contain a type that cannot be CBOR-encoded.
        RuntimeError: If ``setaur.init()`` has not been called.
    """
    return get_client().event(
        source_id, event_type, message, severity,
        source_type=source_type, start_ns=start_ns, end_ns=end_ns, kind=kind,
        trace_id=trace_id, span_id=span_id, parent_id=parent_id,
        attrs=attrs, data=data,
    )


def info(
    source_id: str,
    event_type: str,
    message: str,
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
) -> int:
    """Publish an INFO-severity event. Shorthand for ``event(..., severity=EventSeverity.INFO)``.

    Returns:
        Sequence number for this source. See :func:`event` for full parameter docs.
    """
    return event(source_id, event_type, message, EventSeverity.INFO,
                 start_ns=start_ns, end_ns=end_ns, source_type=source_type, kind=kind,
                 trace_id=trace_id, span_id=span_id, parent_id=parent_id,
                 attrs=attrs, data=data)


def warning(
    source_id: str,
    event_type: str,
    message: str,
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
) -> int:
    """Publish a WARNING-severity event. Shorthand for ``event(..., severity=EventSeverity.WARNING)``.

    Returns:
        Sequence number for this source. See :func:`event` for full parameter docs.
    """
    return event(source_id, event_type, message, EventSeverity.WARNING,
                 start_ns=start_ns, end_ns=end_ns, source_type=source_type, kind=kind,
                 trace_id=trace_id, span_id=span_id, parent_id=parent_id,
                 attrs=attrs, data=data)


def error(
    source_id: str,
    event_type: str,
    message: str,
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
) -> int:
    """Publish an ERROR-severity event. Shorthand for ``event(..., severity=EventSeverity.ERROR)``.

    Returns:
        Sequence number for this source. See :func:`event` for full parameter docs.
    """
    return event(source_id, event_type, message, EventSeverity.ERROR,
                 start_ns=start_ns, end_ns=end_ns, source_type=source_type, kind=kind,
                 trace_id=trace_id, span_id=span_id, parent_id=parent_id,
                 attrs=attrs, data=data)


def critical(
    source_id: str,
    event_type: str,
    message: str,
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
) -> int:
    """Publish a CRITICAL-severity event. Shorthand for ``event(..., severity=EventSeverity.CRITICAL)``.

    Returns:
        Sequence number for this source. See :func:`event` for full parameter docs.
    """
    return event(source_id, event_type, message, EventSeverity.CRITICAL,
                 start_ns=start_ns, end_ns=end_ns, source_type=source_type, kind=kind,
                 trace_id=trace_id, span_id=span_id, parent_id=parent_id,
                 attrs=attrs, data=data)


def span(
    source_id: str,
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
    """Return a :class:`Span` context manager that publishes a timed event on exit.

    ``trace_id`` and ``span_id`` are auto-generated. The span's ``trace_id`` and
    ``span_id`` are accessible inside the ``with`` block so they can be passed to
    child spans.

    Example::

        with setaur.span("nav", "navigate_to_waypoint", "Go to wp-1") as s:
            s.set_attr("waypoint_id", "wp-42")
            do_work()
        # publishes one event with start_ns, end_ns, trace_id, span_id filled in

        # nested spans share a trace:
        with setaur.span("nav", "outer_op", "Outer") as parent:
            with setaur.span("nav", "inner_op", "Inner",
                             trace_id=parent.trace_id,
                             parent_id=parent.span_id):
                do_inner_work()

    Args:
        source_id: Component emitting the span (e.g. ``"navigation_controller"``).
        event_type: Machine-readable operation name (e.g. ``"navigate_to_waypoint"``).
        message: Human-readable description of the operation.
        severity: Defaults to ``INFO``.
        source_type: Origin of the event. Defaults to ``EventSourceType.USER``.
        kind: Operation kind hint — use ``SpanKind.ACTUATOR``, ``SENSOR``, etc.
        trace_id: Pass a parent span's ``trace_id`` to group spans into one trace.
        parent_id: Pass a parent span's ``span_id`` to establish a causal link.
        data: Arbitrary CBOR-serializable payload attached to the span event.

    Returns:
        A :class:`Span` context manager. After the ``with`` block, ``span.sequence_num``
        holds the published sequence number.
    """
    return Span(
        get_client(), source_id, event_type, message, severity,
        source_type=source_type, kind=kind,
        trace_id=trace_id, parent_id=parent_id, data=data,
    )


__all__ = [
    "SourceType", "EventSourceType", "EventSeverity", "SpanKind", "Span",
    "init", "sensor", "event",
    "info", "warning", "error", "critical",
    "span",
]
