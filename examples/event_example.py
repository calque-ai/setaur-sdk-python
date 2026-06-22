"""
event_example.py — Publishing events with the Setaur SDK.

Events represent discrete occurrences in robot operation: state transitions,
faults, commands, or milestones. Unlike sensor readings (continuous, high-rate),
events are sparse and carry a human-readable message alongside structured attrs.

Run alongside the setaur-edge application and set SETAUR_CREDS_FILE for your robot credentials:

    uv run python examples/event_example.py
"""

import os
import time

import setaur
from setaur import EventSeverity

ROBOT_KEY  = "rbt-examplerobot"    # replace with your robot key
CREDS_FILE = "path/to/robot.creds" # replace or set SETAUR_CREDS_FILE env var


def main() -> None:
    # Load credentials from env var if not set explicitly above.
    creds = CREDS_FILE if os.path.isfile(CREDS_FILE) else None

    # Connect to setaur-edge once at startup. Blocks until connected or raises on failure.
    setaur.init(ROBOT_KEY, creds_file=creds)

    # --- INFO: normal operational event ---
    seq = setaur.event(
        source_id  = "navigation_controller",
        event_type = "state_transition",
        message    = "Switched to AUTONOMOUS mode",
        severity   = EventSeverity.INFO,
        attrs      = {
            "from_state": "MANUAL",
            "to_state":   "AUTONOMOUS",
        },
    )
    print(f"[INFO]     state_transition  seq={seq}")

    time.sleep(0.5)

    # --- WARNING: something worth watching ---
    seq = setaur.event(
        source_id  = "battery_monitor",
        event_type = "battery_low",
        message    = "Battery below 20% — return to base",
        severity   = EventSeverity.WARNING,
        attrs      = {
            "battery_pct":              18,
            "voltage_v":                11.2,
            "estimated_remaining_min":  15,
        },
    )
    print(f"[WARNING]  battery_low       seq={seq}")

    time.sleep(0.5)

    # --- ERROR: something went wrong ---
    seq = setaur.event(
        source_id  = "motor_controller",
        event_type = "motor_fault",
        message    = "Motor 2 current spike — command halted",
        severity   = EventSeverity.ERROR,
        attrs      = {
            "motor_id":       "motor_2",
            "current_amps":   12.5,
            "threshold_amps": 10.0,
            "fault_count":    3,
        },
    )
    print(f"[ERROR]    motor_fault       seq={seq}")

    time.sleep(0.5)

    # --- CRITICAL: immediate action required ---
    seq = setaur.event(
        source_id  = "safety_controller",
        event_type = "emergency_stop",
        message    = "E-stop triggered — obstacle within safety envelope",
        severity   = EventSeverity.CRITICAL,
        attrs      = {
            "trigger_source":   "lidar",
            "distance_cm":      12,
            "safe_distance_cm": 50,
        },
        # data accepts any serializable payload for larger unstructured blobs.
        data = {"lidar_scan_id": "scan-00472"},
    )
    print(f"[CRITICAL] emergency_stop    seq={seq}")

    print("\nAll events published.")


if __name__ == "__main__":
    main()
