# setaur-sdk-python

Python SDK for publishing telemetry from a robot to the **setaur-edge** agent. Send sensor readings, structured events, and distributed traces with a single import.

---

## What is this?

Setaur is a telemetry SDK for robotics. It gives every component on your robot a consistent way to emit three kinds of data:

| Kind       | Use for                                                                     | API                                     |
| ---------- | --------------------------------------------------------------------------- | --------------------------------------- |
| **Sensor** | High-rate, continuous measurements (IMU, lidar, encoders)                   | `setaur.sensor()`                       |
| **Event**  | Sparse, discrete occurrences (state changes, faults, commands)              | `setaur.info()` / `setaur.error()` / …  |
| **Span**   | Timed operations with a start, end, and duration (path planning, arm moves) | `setaur.span()` / `setaur.get_tracer()` |

All three are published to a local **setaur-edge** agent, which forwards them to the Setaur platform.

---

## Prerequisites

### 1. Create a Setaur account

Sign up at **[setaur.ai](https://setaur.ai)**.

### 2. Add a robot

In the Setaur platform, add a robot. This generates a unique **robot key** (`rbt-…`) and a **credentials file** (`.creds`) that the SDK uses to authenticate with setaur-edge.

Download both from the add/edit robot configuration page — you'll need them in the steps below.

### 3. Install and run setaur-edge on the robot

**setaur-edge** is the local agent that receives telemetry from the SDK and forwards it to the Setaur platform. Download it from the add/edit robot configuration page in the Setaur platform.

Run it on the same machine as your robot code before calling `setaur.init()`:

```bash
./setaur-edge --creds /etc/robot/robot.creds
```

Setaur-edge must be running before `setaur.init()` is called or it will raise a `RuntimeError`. See the [setaur-edge documentation](https://setaur.ai/docs/setauredge) for installation options, configuration flags, and running as a system service.

---

## Installation

```bash
pip install setaur
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv add setaur
```

---

## Quick start

```python
import time
import setaur
from setaur import SourceType

# Robot key and credentials are generated on the add/edit robot page at setaur.ai.
setaur.init("rbt-yourrobotkey")

# Publish one IMU reading
setaur.sensor(
    source_id    = "imu_main",
    source_type  = SourceType.SENSOR,
    timestamp_ns = time.time_ns(),
    data         = {"accel": {"x": 0.01, "y": -0.02, "z": 9.81}},
)

setaur.shutdown()
```

---

## Initialisation and shutdown

```python
import setaur

# Connect to setaur-edge. Blocks until connected or raises RuntimeError on failure.
# Returns the client, store it if you need direct access to flush() or close().
client = setaur.init("rbt-yourrobotkey")

# Optional: pass an explicit credentials file path.
# Falls back to the SETAUR_CREDS_FILE environment variable when omitted.
setaur.init("rbt-yourrobotkey", creds_file="/etc/robot/robot.creds")

# At process exit, flush all queued messages then close the connection.
setaur.shutdown()

# Mid-run flush (e.g. before a reboot) without stopping the client.
setaur.flush(timeout=3.0)
```

The `SETAUR_CREDS_FILE` environment variable is the recommended way to supply credentials in production:

```bash
SETAUR_CREDS_FILE=/etc/robot/robot.creds python my_robot.py
```

---

## Sensors

Use `sensor()` for continuous, high-rate streams. Capture the timestamp immediately after the hardware read, before any processing, so it reflects true acquisition time.

```python
import time
import setaur
from setaur import SourceType

setaur.init("rbt-yourrobotkey")

data, timestamp_ns = read_imu()   # your driver call

seq = setaur.sensor(
    source_id    = "imu_main",
    source_type  = SourceType.SENSOR,
    timestamp_ns = timestamp_ns,
    data         = data,           # any CBOR-serializable dict
)
# seq is a monotonically increasing counter per source_id.
# A gap on the receiving side means a message was dropped.
```

**Source types**

| Value                      | Meaning                               |
| -------------------------- | ------------------------------------- |
| `SourceType.SENSOR`        | Physical sensor (IMU, lidar, camera)  |
| `SourceType.STATE_MACHINE` | State machine or planner output       |
| `SourceType.METADATA`      | Configuration or descriptive metadata |

---

## Events

Use events for sparse, discrete occurrences, state transitions, faults, commands, milestones. Each event carries a machine-readable `event_type`, a human-readable `message`, a severity level, and optional structured `attrs`.

### Severity shortcuts

```python
setaur.info("nav", "startup", "Navigation system ready")

setaur.warning("battery_monitor", "battery_low", "Battery at 18%",
               attrs={"battery_pct": 18, "voltage_v": 11.2})

setaur.error("motor_controller", "motor_fault", "Motor 2 overcurrent",
             attrs={"motor_id": "motor_2", "current_amps": 12.5})

setaur.critical("safety_controller", "emergency_stop", "E-stop triggered",
                attrs={"trigger_source": "lidar", "distance_cm": 12})
```

### Generic event

```python
from setaur import EventSeverity

setaur.event(
    source_id  = "navigation_controller",
    event_type = "state_transition",
    message    = "Switched to AUTONOMOUS mode",
    severity   = EventSeverity.INFO,
    attrs      = {"from_state": "MANUAL", "to_state": "AUTONOMOUS"},
    data       = {"extra_blob": ...},   # optional: unstructured payload
)
```

`event_type` is a machine-readable label used for filtering and aggregation (e.g. `"motor_fault"`). `message` is the human-readable description shown in the UI.

**Severity levels**

| Level      | When to use                                      |
| ---------- | ------------------------------------------------ |
| `INFO`     | Normal operational events                        |
| `WARNING`  | Something worth watching but not yet broken      |
| `ERROR`    | Something went wrong; intervention may be needed |
| `CRITICAL` | Immediate action required (e.g. safety stop)     |

---

## Spans

Use spans to time operations, path planning, actuator moves, perception pipelines. A span records a start time, end time, and duration automatically. Nested spans form a distributed trace with no manual ID wiring.

### Simple span

```python
with setaur.span("nav", "path_planning", "Plan route to dock") as s:
    s.set_attr("goal", "charging_dock")
    waypoints = plan_path()
    s.set_attr("waypoint_count", len(waypoints))

# After the with block:
print(s.sequence_num)   # published sequence number
print(s.trace_id)       # 32-char hex trace ID
print(s.span_id)        # 16-char hex span ID
```

### Nested spans automatic trace propagation

Spans opened inside an active span automatically inherit the enclosing `trace_id` and set `parent_id` without any manual wiring:

```python
with setaur.span("mission_executor", "mission_leg", "Execute leg") as mission:
    for wp in waypoints:
        with setaur.span("drive_controller", "waypoint_exec", f"Drive to {wp}") as s:
            success = drive_to(wp)
            s.set_attr("success", success)

            if not success:
                # This event is also linked to the active trace automatically.
                setaur.error("drive_controller", "waypoint_failed", f"Failed at {wp}",
                             attrs={"waypoint": wp})
```

If an exception propagates out of a span, `span.error` is recorded in `attrs` automatically and the span is published normally.

### Span options

```python
from setaur import SpanKind

with setaur.span(
    "arm_controller",
    "joint_move",
    "Move joint 3 to 45°",
    kind = SpanKind.ACTUATOR,   # hint to the visualiser
) as s:
    move_joint(3, 45)
```

**Span kinds**

| Value                  | Meaning                                    |
| ---------------------- | ------------------------------------------ |
| `SpanKind.UNSPECIFIED` | Default                                    |
| `SpanKind.INTERNAL`    | Internal computation (planning, inference) |
| `SpanKind.SENSOR`      | Sensor acquisition                         |
| `SpanKind.ACTUATOR`    | Actuator command or motion                 |
| `SpanKind.PRODUCER`    | Publishes work to a queue                  |
| `SpanKind.CONSUMER`    | Consumes work from a queue                 |

---

## Tracer component-scoped handle

If a component emits many spans and events, use `get_tracer()` to bind `source_id` once and avoid repeating it at every call site:

```python
nav   = setaur.get_tracer("nav")
drive = setaur.get_tracer("drive_controller")

with nav.span("mission_leg", "Execute leg") as mission:
    for wp in waypoints:
        with drive.span("waypoint_exec", f"Drive to {wp}") as s:
            success = drive_to(wp)
            s.set_attr("success", success)

            if not success:
                drive.error("waypoint_failed", f"Failed at {wp}",
                            attrs={"waypoint": wp})

nav.info("mission_complete", "Leg finished")
```

Tracers are lightweight handles, create them at module level and reuse freely. Trace context propagates identically to the module-level functions.

---

## Log correlation

Get the current trace ID for attaching to structured log lines:

```python
import logging
logger = logging.getLogger(__name__)

with setaur.span("nav", "planning", "Plan route"):
    logger.info("starting planner", extra={"trace_id": setaur.get_active_trace_id()})
    plan()
```

`get_active_trace_id()` returns `None` when called outside a span context.

---

## API reference

### Init and lifecycle

| Function                                                | Description                                                         |
| ------------------------------------------------------- | ------------------------------------------------------------------- |
| `setaur.init(robot_key, *, creds_file=None) -> _Client` | Connect to setaur-edge. Blocks until connected.                     |
| `setaur.shutdown(timeout=5.0)`                          | Flush queued messages then close the connection.                    |
| `setaur.flush(timeout=5.0) -> bool`                     | Drain the queue without closing. Returns `True` if drained in time. |

### Sensors

| Function                                                           | Description                                        |
| ------------------------------------------------------------------ | -------------------------------------------------- |
| `setaur.sensor(source_id, source_type, timestamp_ns, data) -> int` | Publish a sensor reading. Returns sequence number. |

### Events

| Function                                                                | Description                              |
| ----------------------------------------------------------------------- | ---------------------------------------- |
| `setaur.event(source_id, event_type, message, severity, *, ...) -> int` | Publish an event with explicit severity. |
| `setaur.info(source_id, event_type, message, *, ...) -> int`            | Shorthand for INFO severity.             |
| `setaur.warning(source_id, event_type, message, *, ...) -> int`         | Shorthand for WARNING severity.          |
| `setaur.error(source_id, event_type, message, *, ...) -> int`           | Shorthand for ERROR severity.            |
| `setaur.critical(source_id, event_type, message, *, ...) -> int`        | Shorthand for CRITICAL severity.         |

### Spans and tracing

| Function                                                                     | Description                                            |
| ---------------------------------------------------------------------------- | ------------------------------------------------------ |
| `setaur.span(source_id, event_type, message, severity=INFO, *, ...) -> Span` | Return a timed span context manager.                   |
| `setaur.get_tracer(source_id) -> Tracer`                                     | Return a component-scoped tracer.                      |
| `setaur.get_active_span() -> Span \| None`                                   | Return the innermost active span for this thread/task. |
| `setaur.get_active_trace_id() -> str \| None`                                | Return the current trace ID, or `None` outside a span. |

### Return values

Every publish call returns a **sequence number** a monotonically increasing integer per `source_id`. A gap in sequence numbers on the receiving side means at least one message was dropped by the publish queue.

---

## Examples

Full working examples are in the [`examples/`](examples/) directory:

| File                                                  | Demonstrates                                        |
| ----------------------------------------------------- | --------------------------------------------------- |
| [`sensor_example.py`](examples/sensor_example.py)     | IMU at 100 Hz with accurate hardware timestamps     |
| [`event_example.py`](examples/event_example.py)       | All four severity levels with structured attrs      |
| [`advanced_example.py`](examples/advanced_example.py) | Nested spans, automatic trace propagation, `Tracer` |
