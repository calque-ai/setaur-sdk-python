import logging
import re
import threading
import warnings
from typing import Any

from ._client import get_client, _validate_label, _LABEL_CHARS
from ._span_context import get_active_span

_log_context: dict[str, Any] = {}
_log_context_lock = threading.Lock()

_SEVERITY_MAP: dict[int, str] = {
    logging.DEBUG:    "DEBUG",
    logging.INFO:     "INFO",
    logging.WARNING:  "WARN",
    logging.ERROR:    "ERROR",
    logging.CRITICAL: "FATAL",
}

_RESERVED_CONTEXT_KEYS = frozenset({"firmware_version", "component"})

_COMPONENT_RE = re.compile(rf'[^{_LABEL_CHARS}]')


def set_log_context(**kwargs: Any) -> None:
    """Set process-global fields injected into every log record.

    ``firmware_version`` and ``component`` are routed to first-class
    ``LogMessage`` fields. All other keys are merged into ``attrs``.

    Example::

        setaur.set_log_context(
            firmware_version="1.2.3",
            component="nav",
            mission_id="m-42",
        )
    """
    if 'component' in kwargs:
        _validate_label("component", kwargs['component'])
    global _log_context
    with _log_context_lock:
        _log_context = dict(kwargs)


def clear_log_context() -> None:
    """Remove all process-global log context fields."""
    global _log_context
    with _log_context_lock:
        _log_context = {}


def _level_to_severity(levelno: int) -> str:
    if levelno in _SEVERITY_MAP:
        return _SEVERITY_MAP[levelno]
    if levelno < logging.INFO:
        return "DEBUG"
    if levelno < logging.WARNING:
        return "INFO"
    if levelno < logging.ERROR:
        return "WARN"
    if levelno < logging.CRITICAL:
        return "ERROR"
    return "FATAL"


def _derive_component(logger_name: str) -> str:
    comp = _COMPONENT_RE.sub('_', logger_name)
    return comp if comp else 'default'


class SetaurLogHandler(logging.Handler):
    """Python ``logging.Handler`` that publishes log records to NATS via setaur."""

    def __init__(self, level: int = logging.NOTSET, component: str | None = None) -> None:
        super().__init__(level)
        self._fixed_component = component
        self._component_cache: dict[str, str] = {}
        self._local = threading.local()
        self._no_client_warned = threading.Event()

    def emit(self, record: logging.LogRecord) -> None:
        if getattr(self._local, 'in_emit', False):
            return
        self._local.in_emit = True
        try:
            self._emit_inner(record)
        except Exception:
            self.handleError(record)
        finally:
            self._local.in_emit = False

    def _emit_inner(self, record: logging.LogRecord) -> None:
        try:
            client = get_client()
        except RuntimeError:
            if not self._no_client_warned.is_set():
                self._no_client_warned.set()
                warnings.warn(
                    "setaur: log record dropped — call setaur.init() before logging",
                    UserWarning,
                    stacklevel=8,
                )
            return

        ctx = _log_context  # lock-free read; dict replaced atomically by set_log_context

        if self._fixed_component is not None:
            component = self._fixed_component
        elif 'component' in ctx:
            component = ctx['component']
        else:
            name = record.name
            if name not in self._component_cache:
                self._component_cache[name] = _derive_component(name)
            component = self._component_cache[name]

        attrs: dict[str, Any] = {k: v for k, v in ctx.items() if k not in _RESERVED_CONTEXT_KEYS}

        if record.exc_info and record.exc_info[0] is not None:
            exc_type, exc_value, _ = record.exc_info
            attrs['exception'] = f"{exc_type.__name__}: {exc_value}"

        active = get_active_span()
        trace_id = active.trace_id if active is not None else None
        span_id  = active.span_id  if active is not None else None

        client.log_record(
            component=component,
            timestamp_ns=int(record.created * 1_000_000_000),
            severity_text=_level_to_severity(record.levelno),
            logger_name=record.name,
            message=record.getMessage(),
            firmware_version=ctx.get('firmware_version'),
            source_file=record.pathname or None,
            source_line=record.lineno or None,
            source_function=record.funcName or None,
            trace_id=trace_id,
            span_id=span_id,
            attrs=attrs or None,
        )


def install_logging_handler(
    level: int = logging.DEBUG,
    logger: logging.Logger | None = None,
    component: str | None = None,
) -> SetaurLogHandler:
    """Attach a :class:`SetaurLogHandler` to a logger and return it.

    Args:
        level: Minimum log level to forward. Defaults to ``logging.DEBUG``.
        logger: Target logger. Defaults to the root logger when ``None``.
        component: Pin the NATS subject component. When ``None``, the component
            is derived from each record's logger name (or from ``set_log_context``).

    Returns:
        The attached :class:`SetaurLogHandler`.

    Example::

        setaur.install_logging_handler()
        logging.getLogger("nav").warning("joint limit approaching")
    """
    target = logger or logging.getLogger()
    for existing in target.handlers:
        if isinstance(existing, SetaurLogHandler):
            warnings.warn(
                "setaur: SetaurLogHandler already attached to this logger; "
                "call logger.removeHandler() first to replace it.",
                UserWarning,
                stacklevel=2,
            )
            return existing
    handler = SetaurLogHandler(level=level, component=component)
    target.addHandler(handler)
    return handler
