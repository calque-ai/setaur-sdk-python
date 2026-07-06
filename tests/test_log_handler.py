import logging
import threading
import time
import warnings

import pytest
from setaur._client import _Client
from setaur._envelope import EnvelopeBuilder
from setaur._log_handler import (
    SetaurLogHandler,
    _derive_component,
    _level_to_severity,
    clear_log_context,
    install_logging_handler,
    set_log_context,
)
from setaur._span import Span
from setaur._types import EventSeverity
from conftest import FakeNatsClient, drain, make_client, published_envelope


# ---------------------------------------------------------------------------
# EnvelopeBuilder.log() unit tests
# ---------------------------------------------------------------------------

def test_log_envelope_required_fields():
    eb = EnvelopeBuilder()
    env = eb.log("nav", 1_000_000_000, "WARN", "myapp.nav", "joint limit")
    assert env["timestamp_ns"] == 1_000_000_000
    assert env["severity_text"] == "WARN"
    assert env["message"] == "joint limit"
    assert env["sequence_num"] == 1


def test_log_envelope_omits_optional_fields_by_default():
    eb = EnvelopeBuilder()
    env = eb.log("nav", 1_000_000_000, "INFO", "myapp", "hello")
    assert "firmware_version" not in env
    assert "source_file" not in env
    assert "source_line" not in env
    assert "source_function" not in env
    assert "trace_id" not in env
    assert "span_id" not in env
    assert "attrs" not in env


def test_log_envelope_includes_optional_fields_when_set():
    eb = EnvelopeBuilder()
    env = eb.log(
        "nav", 1_000_000_000, "ERROR", "myapp", "crash",
        firmware_version="1.2.3",
        source_file="/app/nav.py",
        source_line=42,
        source_function="plan_route",
        trace_id="a" * 32,
        span_id="b" * 16,
        attrs={"motor_id": "m1"},
    )
    assert env["firmware_version"] == "1.2.3"
    assert env["source_file"] == "/app/nav.py"
    assert env["source_line"] == 42
    assert env["source_function"] == "plan_route"
    assert env["trace_id"] == "a" * 32
    assert env["span_id"] == "b" * 16
    assert env["attrs"] == {"motor_id": "m1"}


def test_log_envelope_sequence_increments_per_component():
    eb = EnvelopeBuilder()
    seqs = [eb.log("nav", 1_000_000_000, "INFO", "app", f"msg{i}")["sequence_num"] for i in range(3)]
    assert seqs == [1, 2, 3]


def test_log_envelope_sequence_independent_per_component():
    eb = EnvelopeBuilder()
    seq_nav = eb.log("nav", 1_000_000_000, "INFO", "app", "a")["sequence_num"]
    seq_arm = eb.log("arm", 1_000_000_000, "INFO", "app", "b")["sequence_num"]
    assert seq_nav == 1
    assert seq_arm == 1


def test_log_envelope_sequence_independent_from_event():
    eb = EnvelopeBuilder()
    from setaur._types import EventSeverity, EventSourceType, SpanKind
    eb.event("nav", "e", "msg", EventSeverity.INFO, 1_000_000_000)
    seq_log = eb.log("nav", 1_000_000_000, "INFO", "app", "msg")["sequence_num"]
    assert seq_log == 1  # log counter starts at 1 regardless of event counter


def test_log_envelope_includes_component_field():
    eb = EnvelopeBuilder()
    env = eb.log("nav", 1_000_000_000, "INFO", "myapp.nav", "hello")
    assert env["component"] == "nav"


def test_log_envelope_includes_logger_name():
    eb = EnvelopeBuilder()
    env = eb.log("nav", 1_000_000_000, "INFO", "myapp.nav", "hello")
    assert env["logger_name"] == "myapp.nav"


# ---------------------------------------------------------------------------
# _Client.log_record() integration tests
# ---------------------------------------------------------------------------

def test_log_record_publishes_to_correct_subject():
    client, nc = make_client(robot_key="rbt-bot42xxxxx")
    client.log_record("nav", 1_000_000_000, "WARN", "myapp.nav", "joint limit")
    drain(client)
    subject, _ = nc.published[0]
    assert subject == "logs.rbt-bot42xxxxx.nav"


def test_log_record_payload_is_valid_cbor():
    client, nc = make_client()
    client.log_record("nav", 1_000_000_000, "ERROR", "myapp.nav", "crash")
    drain(client)
    env = published_envelope(nc)
    assert env["message"] == "crash"
    assert env["severity_text"] == "ERROR"


def test_log_record_firmware_version_in_payload():
    client, nc = make_client()
    client.log_record("nav", 1_000_000_000, "INFO", "app", "boot", firmware_version="2.0.0")
    drain(client)
    assert published_envelope(nc)["firmware_version"] == "2.0.0"


def test_log_record_raises_on_unserializable_attrs():
    client, _ = make_client()
    with pytest.raises(TypeError, match="CBOR-serializable"):
        client.log_record("nav", 1_000_000_000, "INFO", "app", "msg", attrs={"bad": object()})
    drain(client)


# ---------------------------------------------------------------------------
# _level_to_severity helper
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("levelno,expected", [
    (logging.DEBUG,    "DEBUG"),
    (logging.INFO,     "INFO"),
    (logging.WARNING,  "WARN"),
    (logging.ERROR,    "ERROR"),
    (logging.CRITICAL, "FATAL"),
    (5,   "DEBUG"),   # below DEBUG
    (15,  "DEBUG"),   # between DEBUG and INFO
    (25,  "INFO"),    # between INFO and WARNING
    (35,  "WARN"),    # between WARNING and ERROR
    (45,  "ERROR"),   # between ERROR and CRITICAL
    (999, "FATAL"),   # above CRITICAL
])
def test_level_to_severity(levelno, expected):
    assert _level_to_severity(levelno) == expected


# ---------------------------------------------------------------------------
# _derive_component helper
# ---------------------------------------------------------------------------

def test_derive_component_replaces_dots():
    assert _derive_component("myapp.nav") == "myapp_nav"


def test_derive_component_replaces_slashes():
    assert _derive_component("myapp/nav") == "myapp_nav"


def test_derive_component_empty_string_returns_default():
    assert _derive_component("") == "default"


def test_derive_component_main_passes_through():
    assert _derive_component("__main__") == "__main__"


def test_derive_component_root_logger_name():
    assert _derive_component("root") == "root"


def test_derive_component_dotted_deep():
    assert _derive_component("myapp.nav.controller") == "myapp_nav_controller"


# ---------------------------------------------------------------------------
# SetaurLogHandler.emit() tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_log_context():
    clear_log_context()
    yield
    clear_log_context()


@pytest.fixture()
def handler_and_client():
    client, nc = make_client()
    handler = SetaurLogHandler()
    import setaur._client as mod
    mod._instance = client
    yield handler, client, nc
    drain(client)
    mod._instance = None


def test_emit_routes_warning_to_nats(handler_and_client):
    handler, client, nc = handler_and_client
    logger = logging.getLogger("test.nav")
    logger.addHandler(handler)
    logger.warning("joint limit approaching")
    logger.removeHandler(handler)
    drain(client)
    env = published_envelope(nc)
    assert env["message"] == "joint limit approaching"
    assert env["severity_text"] == "WARN"


@pytest.mark.parametrize("level,expected_severity", [
    (logging.DEBUG,    "DEBUG"),
    (logging.INFO,     "INFO"),
    (logging.WARNING,  "WARN"),
    (logging.ERROR,    "ERROR"),
    (logging.CRITICAL, "FATAL"),
])
def test_emit_severity_mapping(handler_and_client, level, expected_severity):
    handler, client, nc = handler_and_client
    logger = logging.getLogger(f"test.sev.{level}")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.log(level, "test message")
    logger.removeHandler(handler)
    drain(client)
    assert published_envelope(nc)["severity_text"] == expected_severity


def test_emit_derives_component_from_logger_name(handler_and_client):
    handler, client, nc = handler_and_client
    logger = logging.getLogger("myapp.navigation")
    logger.addHandler(handler)
    logger.warning("msg")
    logger.removeHandler(handler)
    drain(client)
    subject, _ = nc.published[0]
    assert subject.endswith(".myapp_navigation")
    assert published_envelope(nc)["component"] == "myapp_navigation"


def test_emit_fixed_component_wins(handler_and_client):
    _, client, nc = handler_and_client
    handler = SetaurLogHandler(component="fixed_comp")
    import setaur._client as mod
    mod._instance = client
    logger = logging.getLogger("myapp.other")
    logger.addHandler(handler)
    logger.warning("msg")
    logger.removeHandler(handler)
    drain(client)
    subject, _ = nc.published[0]
    assert subject.endswith(".fixed_comp")


def test_emit_timestamp_close_to_now(handler_and_client):
    handler, client, nc = handler_and_client
    before = time.time_ns()
    logger = logging.getLogger("test.ts")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.info("now")
    logger.removeHandler(handler)
    after = time.time_ns()
    drain(client)
    ts = published_envelope(nc)["timestamp_ns"]
    assert before <= ts <= after


def test_emit_captures_source_file_and_line(handler_and_client):
    handler, client, nc = handler_and_client
    logger = logging.getLogger("test.src")
    logger.addHandler(handler)
    logger.warning("msg")
    logger.removeHandler(handler)
    drain(client)
    env = published_envelope(nc)
    assert "source_file" in env
    assert env["source_line"] > 0


def test_emit_injects_trace_id_from_active_span(handler_and_client):
    handler, client, nc = handler_and_client
    logger = logging.getLogger("test.trace")
    logger.addHandler(handler)
    with Span(client, "nav", "op", "msg", EventSeverity.INFO) as span:
        logger.warning("inside span")
    logger.removeHandler(handler)
    drain(client)
    # first published message is the log (span publishes on exit, so order: log then span)
    log_env = published_envelope(nc, index=0)
    assert log_env["trace_id"] == span.trace_id
    assert log_env["span_id"] == span.span_id


def test_emit_no_trace_id_outside_span(handler_and_client):
    handler, client, nc = handler_and_client
    logger = logging.getLogger("test.notrace")
    logger.addHandler(handler)
    logger.warning("outside span")
    logger.removeHandler(handler)
    drain(client)
    env = published_envelope(nc)
    assert "trace_id" not in env
    assert "span_id" not in env


def test_emit_exception_info_in_attrs(handler_and_client):
    handler, client, nc = handler_and_client
    logger = logging.getLogger("test.exc")
    logger.addHandler(handler)
    try:
        raise ValueError("motor overheated")
    except ValueError:
        logger.exception("caught error")
    logger.removeHandler(handler)
    drain(client)
    env = published_envelope(nc)
    assert "exception" in env["attrs"]
    assert "ValueError" in env["attrs"]["exception"]
    assert "motor overheated" in env["attrs"]["exception"]


def test_emit_silently_drops_when_no_client():
    import setaur._client as mod
    original = mod._instance
    mod._instance = None
    handler = SetaurLogHandler()
    logger = logging.getLogger("test.nodrop")
    logger.addHandler(handler)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        logger.warning("no client yet")
        assert len(w) == 1
        assert "setaur.init()" in str(w[0].message)
    # second call — warn only once
    with warnings.catch_warnings(record=True) as w2:
        warnings.simplefilter("always")
        logger.warning("still no client")
        assert len(w2) == 0
    logger.removeHandler(handler)
    mod._instance = original


def test_emit_reentrancy_guard_prevents_loop(handler_and_client):
    handler, client, nc = handler_and_client

    original_log_record = client.log_record
    call_count = 0

    def patched_log_record(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        # simulate internal warning that would re-enter emit
        logging.getLogger("setaur._client").warning("internal warn")
        return original_log_record(*args, **kwargs)

    client.log_record = patched_log_record

    logger = logging.getLogger("test.reentrant")
    logger.addHandler(handler)
    logger.warning("trigger")
    logger.removeHandler(handler)
    drain(client)

    assert call_count == 1  # re-entrant call was blocked


def test_emit_calls_handleError_on_exception(handler_and_client):
    handler, client, nc = handler_and_client
    errors = []
    handler.handleError = lambda record: errors.append(record)

    def bad_log_record(*args, **kwargs):
        raise RuntimeError("unexpected")

    client.log_record = bad_log_record

    logger = logging.getLogger("test.handleerr")
    logger.addHandler(handler)
    logger.warning("will fail")  # must not propagate
    logger.removeHandler(handler)
    drain(client)

    assert len(errors) == 1


# ---------------------------------------------------------------------------
# Context system tests
# ---------------------------------------------------------------------------

def test_context_firmware_version_in_payload(handler_and_client):
    handler, client, nc = handler_and_client
    set_log_context(firmware_version="3.1.4")
    logger = logging.getLogger("test.fw")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.info("boot")
    logger.removeHandler(handler)
    drain(client)
    assert published_envelope(nc)["firmware_version"] == "3.1.4"


def test_context_component_overrides_subject(handler_and_client):
    handler, client, nc = handler_and_client
    set_log_context(component="arm_ctrl")
    logger = logging.getLogger("some.other.logger")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.info("msg")
    logger.removeHandler(handler)
    drain(client)
    subject, _ = nc.published[0]
    assert subject.endswith(".arm_ctrl")
    assert published_envelope(nc)["component"] == "arm_ctrl"


def test_context_extra_keys_go_to_attrs(handler_and_client):
    handler, client, nc = handler_and_client
    set_log_context(mission_id="m-99", zone="warehouse-A")
    logger = logging.getLogger("test.extra")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.info("msg")
    logger.removeHandler(handler)
    drain(client)
    attrs = published_envelope(nc)["attrs"]
    assert attrs["mission_id"] == "m-99"
    assert attrs["zone"] == "warehouse-A"


def test_context_extra_keys_not_promoted_to_top_level(handler_and_client):
    handler, client, nc = handler_and_client
    set_log_context(mission_id="m-99")
    logger = logging.getLogger("test.notpromoted")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.info("msg")
    logger.removeHandler(handler)
    drain(client)
    env = published_envelope(nc)
    assert "mission_id" not in env  # must stay inside attrs
    assert "mission_id" in env["attrs"]


def test_clear_log_context_removes_fields(handler_and_client):
    handler, client, nc = handler_and_client
    set_log_context(firmware_version="1.0.0", mission_id="m-1")
    clear_log_context()
    logger = logging.getLogger("test.clear")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.info("msg")
    logger.removeHandler(handler)
    drain(client)
    env = published_envelope(nc)
    assert "firmware_version" not in env
    assert "attrs" not in env


def test_context_exception_merges_with_extra_attrs(handler_and_client):
    handler, client, nc = handler_and_client
    set_log_context(mission_id="m-5")
    logger = logging.getLogger("test.merge")
    logger.addHandler(handler)
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        logger.exception("caught")
    logger.removeHandler(handler)
    drain(client)
    attrs = published_envelope(nc)["attrs"]
    assert "exception" in attrs
    assert attrs["mission_id"] == "m-5"


# ---------------------------------------------------------------------------
# install_logging_handler() tests
# ---------------------------------------------------------------------------

def test_install_attaches_to_root_logger(handler_and_client):
    _, client, _ = handler_and_client
    root = logging.getLogger()
    handler = install_logging_handler()
    assert handler in root.handlers
    root.removeHandler(handler)


def test_install_returns_handler_instance(handler_and_client):
    _, client, _ = handler_and_client
    root = logging.getLogger()
    handler = install_logging_handler()
    assert isinstance(handler, SetaurLogHandler)
    root.removeHandler(handler)


def test_install_attaches_to_specified_logger(handler_and_client):
    _, client, _ = handler_and_client
    target = logging.getLogger("test.install.specific")
    handler = install_logging_handler(logger=target)
    assert handler in target.handlers
    target.removeHandler(handler)


def test_install_idempotent_warns_on_second_call(handler_and_client):
    _, client, _ = handler_and_client
    target = logging.getLogger("test.install.idem")
    h1 = install_logging_handler(logger=target)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        h2 = install_logging_handler(logger=target)
        assert len(w) == 1
        assert issubclass(w[0].category, UserWarning)
        assert "already attached" in str(w[0].message)
    assert h1 is h2
    assert target.handlers.count(h1) == 1  # not duplicated
    target.removeHandler(h1)


def test_install_sets_level(handler_and_client):
    _, client, _ = handler_and_client
    root = logging.getLogger()
    handler = install_logging_handler(level=logging.ERROR)
    assert handler.level == logging.ERROR
    root.removeHandler(handler)


def test_install_fixed_component_passed_through(handler_and_client):
    _, client, nc = handler_and_client
    target = logging.getLogger("test.install.comp")
    handler = install_logging_handler(logger=target, component="pinned")
    target.warning("hello")
    target.removeHandler(handler)
    drain(client)
    subject, _ = nc.published[0]
    assert subject.endswith(".pinned")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_context_component_with_invalid_chars_raises():
    # component must pass _LABEL_RE — invalid characters raise immediately at set time.
    with pytest.raises(ValueError, match="component"):
        set_log_context(component="arm ctrl")  # space is not allowed


def test_set_log_context_replaces_entirely_not_merges(handler_and_client):
    # set_log_context replaces the whole dict — a second call wipes keys from the first.
    handler, client, nc = handler_and_client
    set_log_context(mission_id="m-1")
    set_log_context(zone="A")  # mission_id should now be gone
    logger = logging.getLogger("test.replace")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.info("msg")
    logger.removeHandler(handler)
    drain(client)
    env = published_envelope(nc)
    assert "attrs" not in env or "mission_id" not in env.get("attrs", {})
    assert env.get("attrs", {}).get("zone") == "A"


def test_module_level_funcname_is_sent(handler_and_client):
    # At module level, record.funcName is "<module>" — it's truthy so it is sent.
    # Confirm it reaches the envelope rather than being swallowed.
    handler, client, nc = handler_and_client
    record = logging.LogRecord(
        name="test.module", level=logging.WARNING,
        pathname="/app/main.py", lineno=0,
        msg="module-level log", args=(), exc_info=None,
        func="<module>",
    )
    handler.emit(record)
    drain(client)
    env = published_envelope(nc)
    assert env["source_function"] == "<module>"


def test_lineno_zero_is_omitted(handler_and_client):
    # lineno=0 means location unknown; should not appear in the envelope.
    handler, client, nc = handler_and_client
    record = logging.LogRecord(
        name="test.noline", level=logging.WARNING,
        pathname="", lineno=0,
        msg="no location", args=(), exc_info=None,
    )
    handler.emit(record)
    drain(client)
    env = published_envelope(nc)
    assert "source_line" not in env


def test_component_cache_is_not_poisoned_after_context_cleared(handler_and_client):
    # When context provides a component and is later cleared, derived component
    # (from logger name) should be used — not a stale cache entry.
    handler, client, nc = handler_and_client
    set_log_context(component="ctx_comp")
    logger = logging.getLogger("test.cache.poison")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.info("first")       # uses context component
    clear_log_context()
    logger.info("second")      # should derive from logger name now
    logger.removeHandler(handler)
    drain(client)
    first_subject, _ = nc.published[0]
    second_subject, _ = nc.published[1]
    assert first_subject.endswith(".ctx_comp")
    assert second_subject.endswith(".test_cache_poison")  # derived, not cached ctx


def test_no_client_warned_only_once_across_threads():
    # Multiple threads logging before init() must trigger at most one warning.
    import setaur._client as mod
    original = mod._instance
    mod._instance = None
    handler = SetaurLogHandler()

    warn_count = 0
    original_warn = warnings.warn

    def counting_warn(msg, *args, **kwargs):
        nonlocal warn_count
        warn_count += 1

    warnings.warn = counting_warn
    try:
        threads = [threading.Thread(target=handler.emit, args=(
            logging.LogRecord("t", logging.WARNING, "", 0, "msg", (), None),
        )) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    finally:
        warnings.warn = original_warn
        mod._instance = original

    assert warn_count <= 1


def test_emit_source_file_is_caller_not_handler(handler_and_client):
    # source_file must point to user code, not to _log_handler.py itself.
    handler, client, nc = handler_and_client
    logger = logging.getLogger("test.srcfile")
    logger.addHandler(handler)
    logger.warning("check my file")
    logger.removeHandler(handler)
    drain(client)
    env = published_envelope(nc)
    import os
    assert os.path.basename(env["source_file"]) == "test_log_handler.py"


def test_emit_logger_name_preserved_when_context_component_set(handler_and_client):
    # When context overrides component, logger_name should still reflect
    # the actual logger that emitted the record, not the component.
    handler, client, nc = handler_and_client
    set_log_context(component="override")
    logger = logging.getLogger("my.real.logger")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.info("msg")
    logger.removeHandler(handler)
    drain(client)
    env = published_envelope(nc)
    assert env["component"] == "override"
    assert env["logger_name"] == "my.real.logger"  # must not be overwritten


def test_emit_empty_message_is_published(handler_and_client):
    # Empty string is a valid log message — should not be dropped.
    handler, client, nc = handler_and_client
    logger = logging.getLogger("test.emptymsg")
    logger.addHandler(handler)
    logger.warning("")
    logger.removeHandler(handler)
    drain(client)
    env = published_envelope(nc)
    assert env["message"] == ""


def test_emit_exception_without_message_still_publishes(handler_and_client):
    # logger.exception() with an empty message string should still publish.
    handler, client, nc = handler_and_client
    logger = logging.getLogger("test.exconly")
    logger.addHandler(handler)
    try:
        raise OSError("disk full")
    except OSError:
        logger.exception("")
    logger.removeHandler(handler)
    drain(client)
    env = published_envelope(nc)
    assert env["message"] == ""
    assert "OSError" in env["attrs"]["exception"]
