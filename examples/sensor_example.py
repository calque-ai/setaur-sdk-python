"""
sensor_example.py — Publishing sensor readings with the Setaur SDK.

Simulates an IMU publishing at 100 Hz continuously.
Run with the setaur-edge application running and your credentials file set:

    SETAUR_CREDS_FILE=/path/to/robot.creds uv run python examples/sensor_example.py

Or pass the credentials file path directly in the setaur.init() call below.
"""

import math
import os
import time

import setaur
from setaur import SourceType

ROBOT_KEY  = "rbt-examplerobot"       # replace with your robot key
CREDS_FILE = "path/to/robot.creds"    # replace or set SETAUR_CREDS_FILE env var
RATE_HZ    = 100
INTERVAL   = 1.0 / RATE_HZ            # 10 ms


def read_imu() -> tuple[dict, int]:
    """Read from the IMU and capture the timestamp immediately after acquisition.

    Returns a (data, timestamp_ns) tuple. The timestamp is taken as close to
    the hardware read as possible, before any processing so it reflects the
    true acquisition time rather than the time the data was handled.

    In production replace the simulated values with your actual driver call,
    keeping the time.time_ns() capture on the very next line after it returns.
    """
    t = time.time()

    # --- replace everything below this line with your real driver read ---
    data = {
        "accel": {
            "x": round(math.sin(t * 1.3) * 0.15, 4),
            "y": round(math.cos(t * 0.9) * 0.12, 4),
            "z": round(9.81 + math.sin(t * 2.1) * 0.02, 4),
        },
        "gyro": {
            "x": round(math.sin(t * 3.7) * 0.002, 5),
            "y": round(math.cos(t * 2.3) * 0.003, 5),
            "z": round(math.sin(t * 1.1) * 0.001, 5),
        },
        "temperature_c": round(38.0 + math.sin(t * 0.1) * 0.5, 2),
    }
    # --- capture timestamp immediately after the read returns ---
    timestamp_ns = time.time_ns()

    return data, timestamp_ns


def main() -> None:
    # Load credentials from env var if not set explicitly above.
    creds = CREDS_FILE if os.path.isfile(CREDS_FILE) else None

    # Connect to setaur-edge once at startup. Blocks until connected or raises on failure.
    setaur.init(ROBOT_KEY, creds_file=creds)
    print(f"Connected. Publishing IMU at {RATE_HZ} Hz (Ctrl-C to stop) ...")

    count    = 0
    t0       = time.perf_counter()

    while True:
        data, timestamp_ns = read_imu()

        # sensor() returns the sequence number for this source.
        # A gap in sequence numbers on the receiving side means a message was dropped.
        seq = setaur.sensor(
            source_id    = "imu_main",
            source_type  = SourceType.SENSOR,
            timestamp_ns = timestamp_ns,
            data         = data,
        )

        count += 1
        if count % RATE_HZ == 0:
            elapsed = time.perf_counter() - t0
            print(f"  t={elapsed:6.1f}s  seq={seq:6d}  "
                  f"accel=({data['accel']['x']:+.3f}, {data['accel']['y']:+.3f}, {data['accel']['z']:.3f})  "
                  f"temp={data['temperature_c']:.1f}°C")

        # Pace the loop to RATE_HZ. Using absolute deadlines avoids drift.
        next_tick = t0 + count * INTERVAL
        wait = next_tick - time.perf_counter()
        if wait > 0:
            time.sleep(wait)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
