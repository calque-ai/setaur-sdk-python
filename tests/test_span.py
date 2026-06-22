"""Tests for Span, Tracer, and automatic trace-context propagation."""
import asyncio
import threading
import time

import pytest

import setaur
from setaur._client import _Client
from setaur._span import Span, Tracer, _new_span_id, _new_trace_id
from setaur._span_context import _active_span, get_active_span
from setaur._types import EventSeverity, EventSourceType, SpanKind
from conftest import FakeNatsClient, make_client, drain, published_envelope, all_envelopes


# ---------------------------------------------------------------------------
# get_active_span
# ---------------------------------------------------------------------------

def test_get_active_span_returns_none_outside_context():
    assert get_active_span() is None


def test_get_active_span_returns_span_inside_context():
    client, _ = make_client()
    with Span(client, "nav", "op", "msg", EventSeverity.INFO) as span:
        assert get_active_span() is span
    drain(client)


def test_get_active_span_is_none_after_context_exits():
    client, _ = make_client()
    with Span(client, "nav", "op", "msg", EventSeverity.INFO):
        pass
    drain(client)
    assert get_active_span() is None


# ---------------------------------------------------------------------------
# Automatic trace-context propagation (nested Span without explicit ids)
# ---------------------------------------------------------------------------

def test_nested_span_inherits_trace_id_automatically():
    client, nc = make_client()
    with Span(client, "nav", "outer", "Outer op", EventSeverity.INFO) as outer:
        with Span(client, "drive", "inner", "Inner op", EventSeverity.INFO):
            pass
    drain(client)

    envs = all_envelopes(nc)
    assert envs["inner"]["trace_id"] == envs["outer"]["trace_id"]


def test_nested_span_sets_parent_id_automatically():
    client, nc = make_client()
    with Span(client, "nav", "outer", "Outer op", EventSeverity.INFO) as outer:
        with Span(client, "drive", "inner", "Inner op", EventSeverity.INFO):
            pass
    drain(client)

    envs = all_envelopes(nc)
    assert envs["inner"]["parent_id"] == outer.span_id


def test_root_span_has_no_parent_id():
    client, nc = make_client()
    with Span(client, "nav", "root_op", "Root", EventSeverity.INFO):
        pass
    drain(client)

    env = published_envelope(nc)
    assert "parent_id" not in env


def test_triple_nesting_propagates_trace_id():
    client, nc = make_client()
    with Span(client, "a", "level1", "L1", EventSeverity.INFO):
        with Span(client, "b", "level2", "L2", EventSeverity.INFO):
            with Span(client, "c", "level3", "L3", EventSeverity.INFO):
                pass
    drain(client)

    envs = all_envelopes(nc)
    assert envs["level1"]["trace_id"] == envs["level2"]["trace_id"] == envs["level3"]["trace_id"]


def test_sibling_spans_share_trace_id():
    client, nc = make_client()
    with Span(client, "nav", "parent_op", "Parent", EventSeverity.INFO) as parent:
        with Span(client, "drive", "child1", "C1", EventSeverity.INFO):
            pass
        with Span(client, "drive", "child2", "C2", EventSeverity.INFO):
            pass
    drain(client)

    envs = all_envelopes(nc)
    assert envs["child1"]["trace_id"] == parent.trace_id
    assert envs["child2"]["trace_id"] == parent.trace_id
    assert envs["child1"]["parent_id"] == parent.span_id
    assert envs["child2"]["parent_id"] == parent.span_id


def test_span_explicit_trace_id_overrides_parent():
    client, nc = make_client()
    custom_tid = _new_trace_id()
    with Span(client, "nav", "outer", "Outer", EventSeverity.INFO):
        with Span(client, "nav", "inner", "Inner", EventSeverity.INFO, trace_id=custom_tid):
            pass
    drain(client)

    envs = all_envelopes(nc)
    assert envs["inner"]["trace_id"] == custom_tid
    assert envs["inner"]["trace_id"] != envs["outer"]["trace_id"]


def test_active_span_restored_after_exception():
    client, _ = make_client()
    try:
        with Span(client, "nav", "op", "msg", EventSeverity.INFO):
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    drain(client)
    assert get_active_span() is None


# ---------------------------------------------------------------------------
# Tracer — basic construction and delegation
# ---------------------------------------------------------------------------

def test_tracer_span_publishes_one_event():
    client, nc = make_client()
    tracer = Tracer(client, "nav")
    with tracer.span("navigate", "Go to wp-1"):
        pass
    drain(client)

    assert len(nc.published) == 1


def test_tracer_span_uses_tracer_source_id():
    client, nc = make_client()
    tracer = Tracer(client, "drive_controller")
    with tracer.span("move", "Move fwd"):
        pass
    drain(client)

    assert published_envelope(nc)["source_id"] == "drive_controller"


def test_tracer_span_default_severity_is_info():
    client, nc = make_client()
    tracer = Tracer(client, "nav")
    with tracer.span("op", "msg"):
        pass
    drain(client)

    assert published_envelope(nc)["severity"] == "info"


def test_tracer_span_accepts_explicit_severity():
    client, nc = make_client()
    tracer = Tracer(client, "nav")
    with tracer.span("op", "msg", EventSeverity.WARNING):
        pass
    drain(client)

    assert published_envelope(nc)["severity"] == "warning"


def test_tracer_span_set_attr_included_in_envelope():
    client, nc = make_client()
    tracer = Tracer(client, "nav")
    with tracer.span("op", "msg") as s:
        s.set_attr("goal", "dock")
    drain(client)

    assert published_envelope(nc)["attrs"]["goal"] == "dock"


def test_tracer_event_publishes_one_event():
    client, nc = make_client()
    tracer = Tracer(client, "nav")
    tracer.event("state_change", "Entered IDLE", EventSeverity.INFO)
    drain(client)

    assert len(nc.published) == 1


def test_tracer_event_uses_tracer_source_id():
    client, nc = make_client()
    tracer = Tracer(client, "arm_ctrl")
    tracer.event("joint_limit", "Joint 3 at limit", EventSeverity.WARNING)
    drain(client)

    assert published_envelope(nc)["source_id"] == "arm_ctrl"


def test_tracer_event_returns_sequence_num():
    client, _ = make_client()
    tracer = Tracer(client, "nav")
    seq = tracer.event("e", "msg", EventSeverity.INFO)
    drain(client)

    assert seq == 1


# ---------------------------------------------------------------------------
# Tracer severity shortcuts
# ---------------------------------------------------------------------------

def test_tracer_info_publishes_info_severity():
    client, nc = make_client()
    Tracer(client, "nav").info("e", "msg")
    drain(client)
    assert published_envelope(nc)["severity"] == "info"


def test_tracer_warning_publishes_warning_severity():
    client, nc = make_client()
    Tracer(client, "nav").warning("e", "msg")
    drain(client)
    assert published_envelope(nc)["severity"] == "warning"


def test_tracer_error_publishes_error_severity():
    client, nc = make_client()
    Tracer(client, "nav").error("e", "msg")
    drain(client)
    assert published_envelope(nc)["severity"] == "error"


def test_tracer_critical_publishes_critical_severity():
    client, nc = make_client()
    Tracer(client, "nav").critical("e", "msg")
    drain(client)
    assert published_envelope(nc)["severity"] == "critical"


# ---------------------------------------------------------------------------
# Tracer — inherits trace context from enclosing Span
# ---------------------------------------------------------------------------

def test_tracer_event_inherits_trace_id_from_active_span():
    client, nc = make_client()
    tracer = Tracer(client, "nav")
    with Span(client, "outer_src", "outer_op", "outer", EventSeverity.INFO) as outer:
        tracer.event("inner_event", "inside span", EventSeverity.INFO)
    drain(client)

    envs = all_envelopes(nc)
    assert envs["inner_event"]["trace_id"] == outer.trace_id


def test_tracer_event_inherits_parent_id_from_active_span():
    client, nc = make_client()
    tracer = Tracer(client, "nav")
    with Span(client, "outer_src", "outer_op", "outer", EventSeverity.INFO) as outer:
        tracer.event("inner_event", "inside span", EventSeverity.INFO)
    drain(client)

    envs = all_envelopes(nc)
    assert envs["inner_event"]["parent_id"] == outer.span_id


def test_tracer_span_inherits_context_from_enclosing_span():
    client, nc = make_client()
    nav = Tracer(client, "nav")
    drive = Tracer(client, "drive")

    with nav.span("mission", "Full mission") as outer:
        with drive.span("waypoint", "Drive to wp"):
            pass
    drain(client)

    envs = all_envelopes(nc)
    assert envs["waypoint"]["trace_id"] == outer.trace_id
    assert envs["waypoint"]["parent_id"] == outer.span_id


def test_tracer_event_outside_span_has_no_trace_context():
    client, nc = make_client()
    Tracer(client, "nav").event("standalone", "no span", EventSeverity.INFO)
    drain(client)

    env = published_envelope(nc)
    assert "trace_id" not in env
    assert "parent_id" not in env


# ---------------------------------------------------------------------------
# Module-level setaur.span shortcut
# ---------------------------------------------------------------------------

def test_module_span_requires_init(tmp_path):
    import setaur as sdk
    sdk._client._instance = None
    with pytest.raises(RuntimeError, match="setaur.init()"):
        sdk.span("nav", "op", "msg")


def test_module_span_publishes_via_client():
    client, nc = make_client()
    # Directly test the Span returned by setaur.span by patching the client
    import setaur._client as _mod
    original = _mod._instance
    _mod._instance = client
    try:
        with setaur.span("nav", "module_span_op", "via module") as s:
            pass
        drain(client)
        env = published_envelope(nc)
        assert env["event_type"] == "module_span_op"
        assert env["source_id"] == "nav"
    finally:
        _mod._instance = original


# ---------------------------------------------------------------------------
# Module-level severity shortcuts inherit active span context
# ---------------------------------------------------------------------------

def test_module_info_inherits_active_span_context():
    client, nc = make_client()
    import setaur._client as _mod
    original = _mod._instance
    _mod._instance = client
    try:
        with Span(client, "outer_src", "outer_op", "outer", EventSeverity.INFO) as outer:
            setaur.info("inner_src", "inner_event", "via module info")
        drain(client)
        envs = all_envelopes(nc)
        assert envs["inner_event"]["trace_id"] == outer.trace_id
        assert envs["inner_event"]["parent_id"] == outer.span_id
    finally:
        _mod._instance = original


# ---------------------------------------------------------------------------
# Context isolation between threads
# ---------------------------------------------------------------------------

def test_span_context_is_isolated_across_threads():
    """Active span in one thread must not bleed into another."""
    client, _ = make_client()
    spans_seen: list[object] = []

    def worker():
        # This thread has no active span — should see None.
        spans_seen.append(get_active_span())

    with Span(client, "nav", "op", "msg", EventSeverity.INFO):
        t = threading.Thread(target=worker)
        t.start()
        t.join()
    drain(client)

    assert spans_seen == [None]


# ---------------------------------------------------------------------------
# Context isolation between asyncio tasks
# ---------------------------------------------------------------------------

def test_span_context_is_isolated_across_async_tasks():
    """ContextVar propagates into child tasks but mutations don't leak back."""
    client, _ = make_client()
    inner_spans: list[object] = []

    async def run():
        async def child():
            inner_spans.append(get_active_span())

        with Span(client, "nav", "parent_task", "msg", EventSeverity.INFO):
            # asyncio.create_task copies the current context at creation time,
            # so the child task sees the parent's active span.
            task = asyncio.create_task(child())
            await task

        # After the with-block, active span is cleared in this task.
        inner_spans.append(get_active_span())

    asyncio.run(run())
    drain(client)

    # child task ran inside the span context so it sees the span
    assert inner_spans[0] is not None
    # after exiting, the context in this task is cleared
    assert inner_spans[1] is None


# ---------------------------------------------------------------------------
# SpanKind forwarded correctly
# ---------------------------------------------------------------------------

def test_tracer_span_kind_forwarded():
    client, nc = make_client()
    tracer = Tracer(client, "nav")
    with tracer.span("sense", "Sensor read", kind=SpanKind.SENSOR):
        pass
    drain(client)

    assert published_envelope(nc)["kind"] == "sensor"


def test_span_kind_defaults_to_unspecified():
    client, nc = make_client()
    with Span(client, "nav", "op", "msg", EventSeverity.INFO):
        pass
    drain(client)

    assert published_envelope(nc)["kind"] == "unspecified"


# ---------------------------------------------------------------------------
# Data payload forwarded correctly
# ---------------------------------------------------------------------------

def test_tracer_span_data_included_in_envelope():
    client, nc = make_client()
    tracer = Tracer(client, "nav")
    with tracer.span("op", "msg", data={"extra": 42}):
        pass
    drain(client)

    assert published_envelope(nc)["data"] == {"extra": 42}


def test_tracer_event_data_included_in_envelope():
    client, nc = make_client()
    tracer = Tracer(client, "nav")
    tracer.event("e", "msg", EventSeverity.INFO, data={"key": "val"})
    drain(client)

    assert published_envelope(nc)["data"] == {"key": "val"}


# ---------------------------------------------------------------------------
# set_attr edge cases
# ---------------------------------------------------------------------------

def test_set_attr_overwrites_previous_value():
    client, nc = make_client()
    with Span(client, "nav", "op", "msg", EventSeverity.INFO) as s:
        s.set_attr("speed", 1.0)
        s.set_attr("speed", 2.5)
    drain(client)

    assert published_envelope(nc)["attrs"]["speed"] == 2.5


def test_no_attrs_key_when_set_attr_never_called():
    client, nc = make_client()
    with Span(client, "nav", "op", "msg", EventSeverity.INFO):
        pass
    drain(client)

    assert "attrs" not in published_envelope(nc)


def test_tracer_event_attrs_forwarded():
    client, nc = make_client()
    Tracer(client, "nav").event("e", "msg", EventSeverity.INFO, attrs={"k": "v"})
    drain(client)

    assert published_envelope(nc)["attrs"] == {"k": "v"}


# ---------------------------------------------------------------------------
# sequence_num is 0 before __exit__
# ---------------------------------------------------------------------------

def test_span_sequence_num_is_zero_before_exit():
    client, _ = make_client()
    with Span(client, "nav", "op", "msg", EventSeverity.INFO) as span:
        assert span.sequence_num == 0
    drain(client)


# ---------------------------------------------------------------------------
# parent_id explicit override in a nested context
# ---------------------------------------------------------------------------

def test_nested_span_explicit_parent_id_overrides_active_span():
    client, nc = make_client()
    custom_parent = _new_span_id()
    with Span(client, "nav", "outer", "Outer", EventSeverity.INFO):
        with Span(client, "nav", "inner", "Inner", EventSeverity.INFO, parent_id=custom_parent):
            pass
    drain(client)

    envs = all_envelopes(nc)
    assert envs["inner"]["parent_id"] == custom_parent
    assert envs["inner"]["parent_id"] != envs["outer"]["span_id"]


# ---------------------------------------------------------------------------
# span.error attribute on exception with no message
# ---------------------------------------------------------------------------

def test_span_error_attr_when_exception_has_no_message():
    client, nc = make_client()
    try:
        with Span(client, "nav", "op", "msg", EventSeverity.INFO):
            raise ValueError()
    except ValueError:
        pass
    drain(client)

    env = published_envelope(nc)
    assert "span.error" in env["attrs"]
    assert "ValueError" in env["attrs"]["span.error"]


# ---------------------------------------------------------------------------
# ID generator uniqueness
# ---------------------------------------------------------------------------

def test_new_trace_id_produces_unique_values():
    ids = {_new_trace_id() for _ in range(100)}
    assert len(ids) == 100


def test_new_span_id_produces_unique_values():
    ids = {_new_span_id() for _ in range(100)}
    assert len(ids) == 100


# ---------------------------------------------------------------------------
# Tracer severity shortcuts reject unknown kwargs
# ---------------------------------------------------------------------------

def test_tracer_info_rejects_unknown_kwarg():
    client, _ = make_client()
    with pytest.raises(TypeError):
        Tracer(client, "nav").info("e", "msg", sevrity="info")  # typo


def test_tracer_error_rejects_unknown_kwarg():
    client, _ = make_client()
    with pytest.raises(TypeError):
        Tracer(client, "nav").error("e", "msg", sevrity="error")  # typo


# ---------------------------------------------------------------------------
# __repr__
# ---------------------------------------------------------------------------

def test_tracer_repr_contains_source_id():
    client, _ = make_client()
    tracer = Tracer(client, "nav")
    drain(client)
    assert "nav" in repr(tracer)
    assert "Tracer" in repr(tracer)


def test_span_repr_contains_key_fields():
    client, _ = make_client()
    with Span(client, "nav", "path_plan", "msg", EventSeverity.INFO) as s:
        r = repr(s)
    drain(client)
    assert "Span" in r
    assert "nav" in r
    assert "path_plan" in r
    assert s.span_id in r


# ---------------------------------------------------------------------------
# get_active_trace_id
# ---------------------------------------------------------------------------

def test_get_active_trace_id_returns_none_outside_span():
    assert setaur.get_active_trace_id() is None


def test_get_active_trace_id_returns_trace_id_inside_span():
    client, _ = make_client()
    with Span(client, "nav", "op", "msg", EventSeverity.INFO) as s:
        tid = setaur.get_active_trace_id()
    drain(client)
    assert tid == s.trace_id
    assert len(tid) == 32


def test_get_active_trace_id_returns_none_after_span_exits():
    client, _ = make_client()
    with Span(client, "nav", "op", "msg", EventSeverity.INFO):
        pass
    drain(client)
    assert setaur.get_active_trace_id() is None
