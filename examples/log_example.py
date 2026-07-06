"""
log_example.py — Capturing Python log output with the Setaur SDK.

Wires the standard ``logging`` module into setaur so every log call is
forwarded to the edge as a structured LogMessage. No changes to existing
log call sites are needed after ``install_logging_handler()`` is called.

Run alongside the setaur-edge application and set SETAUR_CREDS_FILE:

    uv run python examples/log_example.py
"""

import logging
import os
import time

import setaur

ROBOT_KEY  = "rbt-examplerobot"    # replace with your robot key
CREDS_FILE = "path/to/robot.creds" # replace or set SETAUR_CREDS_FILE env var


def main() -> None:
    creds = CREDS_FILE if os.path.isfile(CREDS_FILE) else None
    setaur.init(ROBOT_KEY, creds_file=creds)

    # Set process-global context injected into every log record.
    # firmware_version and component are top-level LogMessage fields.
    # All other keys are forwarded as attrs (e.g. mission_id, zone).
    setaur.set_log_context(
        firmware_version = "1.4.2",
        component        = "nav",
        mission_id       = "m-0042",
    )

    # Attach the handler to the root logger once — all loggers in this
    # process will forward their output to setaur-edge automatically.
    setaur.install_logging_handler()

    # Use standard Python loggers anywhere in your codebase.
    nav_log  = logging.getLogger("navigation")
    arm_log  = logging.getLogger("arm_controller")
    main_log = logging.getLogger(__name__)

    # --- DEBUG: fine-grained diagnostic detail ---
    nav_log.debug("Waypoint list loaded: 12 waypoints")
    print("[DEBUG]  navigation: waypoint list loaded")
    time.sleep(0.3)

    # --- INFO: normal operational milestones ---
    nav_log.info("Path planning complete — executing route to dock")
    print("[INFO]   navigation: path planning complete")
    time.sleep(0.3)

    # --- WARNING: worth monitoring but not an error ---
    arm_log.warning("Joint 3 approaching soft limit (87% of range)")
    print("[WARNING] arm_controller: joint limit approaching")
    time.sleep(0.3)

    # --- ERROR: something failed, operation affected ---
    arm_log.error("Grasp attempt failed — object slipped (attempt 2/3)")
    print("[ERROR]  arm_controller: grasp failed")
    time.sleep(0.3)

    # --- CRITICAL: maps to severity_text "FATAL" in the log envelope (OTel convention) ---
    main_log.critical("E-stop triggered by safety monitor")
    print("[FATAL]    __main__: e-stop triggered")
    time.sleep(0.3)

    # --- Exception logging: exc_info is captured in attrs ---
    try:
        raise RuntimeError("IK solver did not converge")
    except RuntimeError:
        arm_log.exception("Inverse kinematics failure")
    print("[ERROR]  arm_controller: IK failure (with exception)")
    time.sleep(0.3)

    # --- Trace correlation: log inside a span to link records to a trace ---
    with setaur.span("nav", "dock_approach", "Approach charging dock"):
        nav_log.info("Aligning with dock — distance 0.8 m")
        nav_log.info("Docking complete")
    print("[INFO]   navigation: dock approach (trace-linked logs)")

    setaur.flush()
    print("\nAll log records published.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
