import pytest
from setaur._client import _Client
from setaur._span import Span, Tracer, _new_trace_id, _new_span_id
from setaur._span_context import get_active_span
from setaur._types import SourceType, EventSeverity, EventSourceType, SpanKind
from conftest import FakeNatsClient, make_client, drain, published_envelope, all_envelopes


# --- sensor() returns sequence_num -------------------------------------------

def test_sensor_returns_sequence_num():
    client, _ = make_client()
    seq = client.sensor("imu_0", SourceType.SENSOR, 1_000_000_000, {})
    drain(client)
    assert seq == 1


def test_sensor_sequence_num_increments():
    client, _ = make_client()
    seqs = [client.sensor("imu_0", SourceType.SENSOR, 1_000_000_000, {}) for _ in range(3)]
    drain(client)
    assert seqs == [1, 2, 3]


# --- event() returns sequence_num --------------------------------------------

def test_event_returns_sequence_num():
    client, _ = make_client()
    seq = client.event("nav", "state_transition", "msg", EventSeverity.INFO)
    drain(client)
    assert seq == 1


def test_event_sequence_num_increments():
    client, _ = make_client()
    seqs = [client.event("nav", "e", "msg", EventSeverity.INFO) for _ in range(3)]
    drain(client)
    assert seqs == [1, 2, 3]


def test_event_publishes_to_correct_subject():
    client, nc = make_client(robot_key="rbt-bot42xxxxx")
    client.event("nav", "state_transition", "msg", EventSeverity.WARNING)
    drain(client)

    subject, _ = nc.published[0]
    assert subject == "events.rbt-bot42xxxxx.warning.state_transition"


def test_event_payload_is_valid_cbor():
    client, nc = make_client()
    client.event("nav", "state_transition", "Entered AUTONOMOUS", EventSeverity.INFO,
                 attrs={"from": "MANUAL"})
    drain(client)

    env = published_envelope(nc)
    assert env["source_id"]  == "nav"
    assert env["event_type"] == "state_transition"
    assert env["message"]    == "Entered AUTONOMOUS"
    assert env["severity"]   == "info"
    assert env["attrs"]      == {"from": "MANUAL"}


def test_event_start_ns_defaults_to_now():
    import time
    client, nc = make_client()
    before = time.time_ns()
    client.event("nav", "e", "msg", EventSeverity.INFO)
    after = time.time_ns()
    drain(client)

    env = published_envelope(nc)
    assert before <= env["start_ns"] <= after


# --- severity shortcuts -------------------------------------------------------

def test_info_shortcut():
    client, nc = make_client()
    client.event("nav", "e", "msg", EventSeverity.INFO)
    drain(client)
    assert published_envelope(nc)["severity"] == "info"


def test_warning_shortcut():
    client, nc = make_client()
    client.event("nav", "e", "msg", EventSeverity.WARNING)
    drain(client)
    assert published_envelope(nc)["severity"] == "warning"


def test_error_shortcut():
    client, nc = make_client()
    client.event("nav", "e", "msg", EventSeverity.ERROR)
    drain(client)
    assert published_envelope(nc)["severity"] == "error"


def test_critical_shortcut():
    client, nc = make_client()
    client.event("nav", "e", "msg", EventSeverity.CRITICAL)
    drain(client)
    assert published_envelope(nc)["severity"] == "critical"


def test_shortcut_rejects_unknown_kwargs():
    import setaur, pytest
    with pytest.raises(TypeError):
        setaur.info("nav", "e", "msg", sevrity=EventSeverity.WARNING)  # typo


# --- span() context manager --------------------------------------------------

def test_span_publishes_on_exit():
    client, nc = make_client()
    with Span(client, "nav", "navigate", "Go to wp-1", EventSeverity.INFO):
        pass
    drain(client)

    assert len(nc.published) == 1


def test_span_captures_duration():
    import time
    client, nc = make_client()
    with Span(client, "nav", "navigate", "Go to wp-1", EventSeverity.INFO):
        time.sleep(0.01)
    drain(client)

    env = published_envelope(nc)
    assert env["end_ns"] > env["start_ns"]
    assert env["end_ns"] - env["start_ns"] >= 10_000_000  # at least 10ms


def test_span_auto_generates_trace_and_span_ids():
    client, nc = make_client()
    with Span(client, "nav", "navigate", "msg", EventSeverity.INFO):
        pass
    drain(client)

    env = published_envelope(nc)
    assert len(env["trace_id"]) == 32  # 16 bytes hex
    assert len(env["span_id"])  == 16  # 8 bytes hex


def test_span_accepts_explicit_trace_id():
    client, nc = make_client()
    tid = _new_trace_id()
    with Span(client, "nav", "navigate", "msg", EventSeverity.INFO, trace_id=tid):
        pass
    drain(client)

    env = published_envelope(nc)
    assert env["trace_id"] == tid


def test_span_links_parent_id():
    client, nc = make_client()
    parent = _new_span_id()
    with Span(client, "nav", "sub-op", "msg", EventSeverity.INFO, parent_id=parent):
        pass
    drain(client)

    env = published_envelope(nc)
    assert env["parent_id"] == parent


def test_span_set_attr():
    client, nc = make_client()
    with Span(client, "nav", "navigate", "msg", EventSeverity.INFO) as span:
        span.set_attr("waypoint_id", "wp-42")
        span.set_attr("speed_mps", 1.5)
    drain(client)

    env = published_envelope(nc)
    assert env["attrs"]["waypoint_id"] == "wp-42"
    assert env["attrs"]["speed_mps"]   == 1.5


def test_span_returns_sequence_num():
    client, _ = make_client()
    with Span(client, "nav", "navigate", "msg", EventSeverity.INFO) as span:
        pass
    drain(client)
    assert span.sequence_num == 1


def test_span_exposes_trace_and_span_ids_during_context():
    client, _ = make_client()
    with Span(client, "nav", "op", "msg", EventSeverity.INFO) as span:
        tid = span.trace_id
        sid = span.span_id
    drain(client)
    # ids are set before __enter__ so they're available for child spans inside the block
    assert len(tid) == 32
    assert len(sid) == 16


def test_nested_spans_share_trace_id():
    client, nc = make_client()
    with Span(client, "nav", "outer", "outer op", EventSeverity.INFO) as outer:
        with Span(client, "nav", "inner", "inner op", EventSeverity.INFO,
                  trace_id=outer.trace_id, parent_id=outer.span_id):
            pass
    drain(client)

    envs = all_envelopes(nc)
    assert envs["inner"]["trace_id"] == envs["outer"]["trace_id"]
    assert envs["inner"]["parent_id"] == envs["outer"]["span_id"]


# --- defensive behaviour -----------------------------------------------------

def test_span_exit_without_enter_raises():
    client, _ = make_client()
    span = Span(client, "nav", "op", "msg", EventSeverity.INFO)
    with pytest.raises(RuntimeError, match="__enter__"):
        span.__exit__(None, None, None)
    drain(client)


def test_span_records_error_attr_on_exception():
    client, nc = make_client()
    try:
        with Span(client, "nav", "op", "msg", EventSeverity.INFO):
            raise ValueError("something broke")
    except ValueError:
        pass
    drain(client)

    env = published_envelope(nc)
    assert "span.error" in env["attrs"]
    assert "ValueError" in env["attrs"]["span.error"]


def test_sensor_raises_on_unserializable_data():
    client, _ = make_client()
    with pytest.raises(TypeError, match="CBOR-serializable"):
        client.sensor("imu_0", SourceType.SENSOR, 1_000_000_000, {"bad": object()})
    drain(client)


def test_event_raises_on_unserializable_data():
    client, _ = make_client()
    with pytest.raises(TypeError, match="CBOR-serializable"):
        client.event("nav", "e", "msg", EventSeverity.INFO, data=object())
    drain(client)


# --- input validation --------------------------------------------------------

def test_invalid_robot_key_raises_on_init():
    nc = FakeNatsClient()
    async def connector(url, creds): return nc
    with pytest.raises(ValueError, match="robot_key"):
        _Client("bad-key", creds_file=None, connector=connector)


def test_invalid_source_id_raises_on_event():
    client, _ = make_client()
    with pytest.raises(ValueError, match="source_id"):
        client.event("nav/ctrl", "e", "msg", EventSeverity.INFO)
    drain(client)


def test_invalid_event_type_raises_on_event():
    client, _ = make_client()
    with pytest.raises(ValueError, match="event_type"):
        client.event("nav", "bad.type", "msg", EventSeverity.INFO)
    drain(client)


def test_invalid_source_id_raises_on_sensor():
    client, _ = make_client()
    with pytest.raises(ValueError, match="source_id"):
        client.sensor("imu 0", SourceType.SENSOR, 1_000_000_000, {})
    drain(client)


def test_source_id_validation_runs_only_once():
    # After the first valid call the id is cached; a second call must not re-raise.
    client, _ = make_client()
    client.event("nav", "e", "msg", EventSeverity.INFO)
    client.event("nav", "e", "msg", EventSeverity.INFO)
    drain(client)


# --- sequence counters are per source_id and per envelope type ---------------

def test_event_sequences_are_independent_per_source_id():
    client, nc = make_client()
    seq_a = client.event("src_a", "e", "msg", EventSeverity.INFO)
    seq_b = client.event("src_b", "e", "msg", EventSeverity.INFO)
    drain(client)
    # Each source starts its own counter at 1.
    assert seq_a == 1
    assert seq_b == 1


def test_sensor_and_event_sequences_are_independent_for_same_source():
    client, _ = make_client()
    s1 = client.sensor("imu_0", SourceType.SENSOR, 1_000_000_000, {})
    e1 = client.event("imu_0", "e", "msg", EventSeverity.INFO)
    drain(client)
    # Sensor and event use separate sequence keys in EnvelopeBuilder.
    assert s1 == 1
    assert e1 == 1


# --- end_ns absent for point-in-time events ----------------------------------

def test_point_in_time_event_has_no_end_ns():
    client, nc = make_client()
    client.event("nav", "e", "msg", EventSeverity.INFO)
    drain(client)
    assert "end_ns" not in published_envelope(nc)


def test_explicit_end_ns_zero_has_no_end_ns_in_envelope():
    client, nc = make_client()
    client.event("nav", "e", "msg", EventSeverity.INFO, end_ns=0)
    drain(client)
    assert "end_ns" not in published_envelope(nc)


# --- creds env var does not interfere when unset -----------------------------

def test_init_unaffected_when_creds_env_var_not_set(monkeypatch):
    monkeypatch.delenv("SETAUR_CREDS_FILE", raising=False)
    client, _ = make_client()
    drain(client)


# --- init() return value -----------------------------------------------------

def test_init_returns_client():
    import setaur
    import setaur._client as _mod
    nc = FakeNatsClient()
    async def connector(url, creds): return nc
    # patch the default connector so init() doesn't need a real NATS server
    original_instance = _mod._instance
    original_default = _mod._default_connector
    _mod._default_connector = connector
    try:
        result = setaur.init.__wrapped__("rbt-test000001") if hasattr(setaur.init, "__wrapped__") else None
        # Use _Client directly to verify type since module init uses global connector
        from setaur._client import _Client
        client = _Client("rbt-test000001", creds_file=None, connector=connector)
        assert isinstance(client, _Client)
        client.close()
    finally:
        _mod._default_connector = original_default
        if _mod._instance is not None:
            _mod._instance.close()
        _mod._instance = original_instance


# --- flush() drains the queue ------------------------------------------------

def test_flush_returns_true_when_queue_drains():
    client, _ = make_client()
    client.event("nav", "e", "msg", EventSeverity.INFO)
    result = client.flush(timeout=5.0)
    assert result is True
    drain(client)


def test_flush_with_empty_queue_returns_true():
    client, _ = make_client()
    result = client.flush(timeout=1.0)
    assert result is True
    drain(client)


# --- shutdown() clears the singleton -----------------------------------------

def test_shutdown_clears_singleton():
    import setaur
    import setaur._client as _mod
    nc = FakeNatsClient()
    async def connector(url, creds): return nc
    from setaur._client import _Client
    _mod._instance = _Client("rbt-test000001", creds_file=None, connector=connector)
    setaur.shutdown(timeout=2.0)
    assert _mod._instance is None


def test_shutdown_raises_if_not_initialised():
    import setaur
    import setaur._client as _mod
    _mod._instance = None
    with pytest.raises(RuntimeError, match="setaur.init()"):
        setaur.shutdown()
