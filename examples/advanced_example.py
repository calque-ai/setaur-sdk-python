"""
advanced_example.py — Severity shortcuts, tracers, and distributed tracing with spans.

Demonstrates:
  - Severity shortcut functions (info, warning, error, critical)
  - Span context manager for timing an operation
  - Nested spans with automatic trace-context propagation
  - Tracer for component-scoped spans and events without repeating source_id
  - Attaching attributes to a span at runtime

Run with a local NATS server or set SETAUR_CREDS_FILE for your robot credentials:

    uv run python examples/advanced_example.py
"""

import os
import time

import setaur
from setaur import SpanKind

ROBOT_KEY  = "rbt-examplerobot"    # replace with your robot key
CREDS_FILE = "path/to/robot.creds" # replace or set SETAUR_CREDS_FILE env var


# ---------------------------------------------------------------------------
# Simulated robot operations
# ---------------------------------------------------------------------------

def plan_path(start: str, goal: str) -> list[str]:
    """Stub: returns a list of waypoints."""
    time.sleep(0.02)
    return [start, "wp-intermediate", goal]


def execute_waypoint(waypoint: str) -> bool:
    """Stub: drives to a waypoint, returns True on success."""
    time.sleep(0.05)
    return waypoint != "wp-bad"  # simulate a failure on a specific waypoint


# ---------------------------------------------------------------------------
# Part 1 — Severity shortcuts
# ---------------------------------------------------------------------------

def demo_shortcuts() -> None:
    print("--- Severity shortcuts ---")

    seq = setaur.info("nav", "startup", "Navigation system initialised")
    print(f"  info()     seq={seq}")

    seq = setaur.warning("battery_monitor", "battery_low", "Battery at 18%",
                         attrs={"battery_pct": 18})
    print(f"  warning()  seq={seq}")

    seq = setaur.error("motor_controller", "motor_fault", "Motor 2 overcurrent",
                       attrs={"motor_id": "motor_2", "current_amps": 12.5})
    print(f"  error()    seq={seq}")

    seq = setaur.critical("safety_controller", "emergency_stop", "E-stop triggered",
                          attrs={"trigger_source": "lidar", "distance_cm": 12})
    print(f"  critical() seq={seq}")


# ---------------------------------------------------------------------------
# Part 2 — Span for a single timed operation
# ---------------------------------------------------------------------------

def demo_simple_span() -> None:
    print("\n--- Simple span ---")

    with setaur.span("nav", "path_planning", "Plan path to charging dock",
                     kind=SpanKind.INTERNAL) as s:
        waypoints = plan_path("current_pos", "charging_dock")
        s.set_attr("waypoint_count", len(waypoints))
        s.set_attr("goal", "charging_dock")

    print(f"  path_planning complete  seq={s.sequence_num}  trace={s.trace_id[:8]}...")


# ---------------------------------------------------------------------------
# Part 3 — Nested spans with automatic trace-context propagation
# ---------------------------------------------------------------------------

def demo_nested_spans() -> None:
    print("\n--- Nested spans (automatic trace propagation) ---")

    # The outer span starts a new trace. trace_id and parent_id flow automatically
    # to every span and event opened inside this block — no manual wiring needed.
    with setaur.span("mission_executor", "mission_leg",
                     "Execute leg: base → waypoint A",
                     kind=SpanKind.INTERNAL) as mission:

        waypoints = plan_path("base", "waypoint_A")

        for wp in waypoints:
            # trace_id and parent_id are inherited from the active span automatically.
            with setaur.span("drive_controller", "waypoint_execution",
                             f"Drive to {wp}", kind=SpanKind.ACTUATOR) as wp_span:
                success = execute_waypoint(wp)
                wp_span.set_attr("waypoint", wp)
                wp_span.set_attr("success", success)

                if not success:
                    # This event inherits trace_id and parent_id from wp_span automatically.
                    setaur.error("drive_controller", "waypoint_failed",
                                 f"Failed to reach {wp}", attrs={"waypoint": wp})

            status = "ok" if success else "FAILED"
            print(f"  waypoint={wp:<20} status={status}  seq={wp_span.sequence_num}")

    print(f"\n  Mission span complete  seq={mission.sequence_num}  "
          f"trace={mission.trace_id}")


# ---------------------------------------------------------------------------
# Part 4 — Tracer for component-scoped spans and events
# ---------------------------------------------------------------------------

def demo_tracer() -> None:
    print("\n--- Tracer (component-scoped handle) ---")

    # A tracer binds source_id once so every call site is shorter.
    nav   = setaur.get_tracer("nav")
    drive = setaur.get_tracer("drive_controller")

    with nav.span("mission_leg", "Execute leg via tracer",
                  kind=SpanKind.INTERNAL) as mission:

        waypoints = plan_path("base", "dock")

        for wp in waypoints:
            # drive.span inherits the active nav span's trace automatically.
            with drive.span("waypoint_execution", f"Drive to {wp}",
                            kind=SpanKind.ACTUATOR) as wp_span:
                success = execute_waypoint(wp)
                wp_span.set_attr("waypoint", wp)
                wp_span.set_attr("success", success)

                if not success:
                    # drive.error also inherits trace context from wp_span.
                    drive.error("waypoint_failed", f"Failed to reach {wp}",
                                attrs={"waypoint": wp})

            status = "ok" if success else "FAILED"
            print(f"  waypoint={wp:<20} status={status}  seq={wp_span.sequence_num}")

    nav.info("mission_complete", "Leg finished",
             attrs={"total_waypoints": len(waypoints)})
    print(f"\n  Mission span complete  seq={mission.sequence_num}  "
          f"trace={mission.trace_id}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    creds = CREDS_FILE if os.path.isfile(CREDS_FILE) else None
    setaur.init(ROBOT_KEY, creds_file=creds)

    demo_shortcuts()
    demo_simple_span()
    demo_nested_spans()
    demo_tracer()


if __name__ == "__main__":
    main()
