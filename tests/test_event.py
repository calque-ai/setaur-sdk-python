import cbor2
import pytest
from setaur._client import _Client
from setaur._span import Span, _new_trace_id, _new_span_id
from setaur._types import SourceType, EventSeverity, EventSourceType, SpanKind


# --- fake transport ----------------------------------------------------------

class FakeNatsClient:
    def __init__(self):
        self.published: list[tuple[str, bytes]] = []

    async def publish(self, subject: str, payload: bytes) -> None:
        self.published.append((subject, payload))

    async def close(self) -> None:
        pass


def make_client(robot_key: str = "rbt-test000001") -> tuple[_Client, FakeNatsClient]:
    nc = FakeNatsClient()
    async def connector(url, credentials):
        return nc
    return _Client(robot_key, creds_file=None, connector=connector), nc


def drain(client: _Client) -> None:
    client.close()


def published_envelope(nc: FakeNatsClient, index: int = 0) -> dict:
    return cbor2.loads(nc.published[index][1])


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

    # inner exits first, outer exits second
    envs = {cbor2.loads(p)["event_type"]: cbor2.loads(p) for _, p in nc.published}
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
