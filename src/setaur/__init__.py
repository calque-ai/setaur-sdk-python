from typing import Any
from ._types import SourceType, EventSourceType, EventSeverity, SpanKind
from ._client import init, get_client, shutdown, flush
from ._span import Span, Tracer, get_active_span
from ._log_handler import SetaurLogHandler, install_logging_handler, set_log_context, clear_log_context


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
    """Publish an INFO-severity event.

    Shorthand for ``event(..., severity=EventSeverity.INFO)``.
    See :func:`event` for full parameter documentation.
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
    """Publish a WARNING-severity event.

    Shorthand for ``event(..., severity=EventSeverity.WARNING)``.
    See :func:`event` for full parameter documentation.
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
    """Publish an ERROR-severity event.

    Shorthand for ``event(..., severity=EventSeverity.ERROR)``.
    See :func:`event` for full parameter documentation.
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
    """Publish a CRITICAL-severity event.

    Shorthand for ``event(..., severity=EventSeverity.CRITICAL)``.
    See :func:`event` for full parameter documentation.
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

    Trace context is wired automatically — nested spans inherit ``trace_id`` and
    ``parent_id`` from the enclosing span with no manual bookkeeping. Pass
    ``trace_id`` / ``parent_id`` explicitly only when linking across thread or
    process boundaries.

    For components that emit many spans, prefer :func:`get_tracer` to avoid
    repeating ``source_id`` at every call site.

    Example::

        # Simple span
        with setaur.span("nav", "path_planning", "Plan route to dock") as s:
            s.set_attr("goal", "charging_dock")
            do_planning()

        # Nested spans — trace context flows automatically
        with setaur.span("nav", "mission_leg", "Execute leg"):
            with setaur.span("drive", "waypoint_exec", "Drive to wp-1"):
                do_drive()
                # this event is also linked to the active trace automatically
                setaur.error("drive", "waypoint_failed", "Missed wp-1")

    Args:
        source_id: Component emitting the span (e.g. ``"navigation_controller"``).
        event_type: Machine-readable operation name (e.g. ``"navigate_to_waypoint"``).
        message: Human-readable description of the operation.
        severity: Defaults to ``INFO``.
        source_type: Origin of the event. Defaults to ``EventSourceType.USER``.
        kind: Operation kind hint — use ``SpanKind.ACTUATOR``, ``SENSOR``, etc.
        trace_id: Override the inherited trace ID (cross-thread / cross-process only).
        parent_id: Override the inherited parent span ID (cross-thread / cross-process only).
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


def get_tracer(source_id: str) -> Tracer:
    """Return a :class:`Tracer` scoped to ``source_id``.

    A tracer binds a ``source_id`` once so you don't repeat it on every span
    or event call. All spans and events emitted through a tracer participate in
    automatic trace context propagation identically to :func:`span` and
    :func:`event`.

    Example::

        nav   = setaur.get_tracer("nav")
        drive = setaur.get_tracer("drive_controller")

        with nav.span("mission_leg", "Execute leg"):
            with drive.span("waypoint_exec", "Drive to wp-1"):
                do_drive()
                drive.error("waypoint_failed", "Missed wp-1")
                # trace_id and parent_id inherited automatically

    Args:
        source_id: Identifier for the component (e.g. ``"navigation_controller"``).

    Returns:
        A :class:`Tracer` bound to ``source_id``.

    Raises:
        RuntimeError: If ``setaur.init()`` has not been called.
    """
    return Tracer(get_client(), source_id)


def get_active_trace_id() -> str | None:
    """Return the trace ID of the currently active span, or ``None``.

    Useful for correlating structured log lines with the active trace without
    importing :func:`get_active_span` and handling the ``None`` check yourself::

        logger.info("planning route", extra={"trace_id": setaur.get_active_trace_id()})

    Returns:
        A 32-char hex trace ID string, or ``None`` if called outside a span context.
    """
    span = get_active_span()
    return span.trace_id if span is not None else None


__all__ = [
    "SourceType", "EventSourceType", "EventSeverity", "SpanKind", "Span", "Tracer",
    "init", "shutdown", "flush", "get_client", "get_tracer", "get_active_span", "get_active_trace_id",
    "sensor", "event",
    "info", "warning", "error", "critical",
    "span",
    "SetaurLogHandler", "install_logging_handler", "set_log_context", "clear_log_context",
]
