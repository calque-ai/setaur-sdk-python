"""
Performance benchmarks for _Client — run manually, not collected by pytest.

    uv run python tests/bench_client.py
"""
import asyncio
import logging
import statistics
import time

from setaur._client import _Client
from setaur._types import SourceType

# suppress drop warnings — bench_queue_overflow intentionally triggers them
logging.disable(logging.WARNING)

ROBOT_KEY = "rbt-benchtest01"
TS        = 1_000_000_000


class RecordingNatsClient:
    def __init__(self):
        self.count = 0

    async def publish(self, subject: str, payload: bytes) -> None:
        self.count += 1
        await asyncio.sleep(0)  # yield so the event loop stays responsive under load

    async def close(self) -> None:
        pass


def make_client() -> tuple[_Client, RecordingNatsClient]:
    nc = RecordingNatsClient()
    async def connector(url, credentials):
        return nc
    return _Client(ROBOT_KEY, creds_file=None, connector=connector), nc


# --- benchmark 1: sensor() call latency at 200Hz -----------------------------

def bench_sensor_call_latency(n: int = 1000) -> None:
    """Calls sensor() at a 200Hz pace and measures how long each call takes."""
    client, nc = make_client()
    data    = {"x": 1.0, "y": 2.0, "z": 3.0}
    interval = 1 / 200  # 5ms

    samples = []
    t0 = time.perf_counter()
    for i in range(n):
        t_call = time.perf_counter_ns()
        client.sensor("imu_0", SourceType.SENSOR, TS, data)
        samples.append(time.perf_counter_ns() - t_call)
        next_tick = t0 + (i + 1) * interval
        wait = next_tick - time.perf_counter()
        if wait > 0:
            time.sleep(wait)

    client.close()

    s_us = [s / 1000 for s in samples]
    print(f"\n[sensor() call latency @ 200Hz] n={n}, drained={nc.count}/{n}")
    print(f"  median : {statistics.median(s_us):.1f} µs")
    print(f"  p99    : {sorted(s_us)[int(n * 0.99)]:.1f} µs")
    print(f"  max    : {max(s_us):.1f} µs")
    print(f"  budget : 5000 µs per call (200Hz = 5ms loop)")


# --- benchmark 2: throughput at 1kHz (5x headroom above 200Hz) ---------------

def bench_throughput_1khz(n: int = 1000) -> None:
    """Paces sends at 1kHz to verify the pipeline can handle."""
    client, nc = make_client()
    data     = {"x": 1.0, "y": 2.0, "z": 3.0}
    interval = 0.001  # 1ms = 1kHz

    t0 = time.perf_counter()
    for i in range(n):
        client.sensor("imu_0", SourceType.SENSOR, TS, data)
        next_tick = t0 + (i + 1) * interval
        wait = next_tick - time.perf_counter()
        if wait > 0:
            time.sleep(wait)
    client.close()
    elapsed = time.perf_counter() - t0

    print(f"\n[throughput @ 1kHz] n={n}")
    print(f"  elapsed : {elapsed:.3f} s")
    print(f"  drained : {nc.count}/{n} ({nc.count/n*100:.1f}%)")


# --- benchmark 3: large payload (simulated JPEG thumbnail at 5fps) -----------

def bench_large_payload(n: int = 100, size_kb: int = 40) -> None:
    """Measures sensor() call time for ~40KB JPEG-sized payloads at 5fps."""
    client, nc = make_client()
    data     = {"frame": b"x" * (size_kb * 1024)}
    interval = 1 / 5  # 200ms = 5fps

    samples = []
    t0 = time.perf_counter()
    for i in range(n):
        t_call = time.perf_counter_ns()
        client.sensor("camera", SourceType.SENSOR, TS, data)
        samples.append(time.perf_counter_ns() - t_call)
        next_tick = t0 + (i + 1) * interval
        wait = next_tick - time.perf_counter()
        if wait > 0:
            time.sleep(wait)

    client.close()

    s_ms = [s / 1_000_000 for s in samples]
    print(f"\n[large payload ~{size_kb}KB @ 5fps] n={n}, drained={nc.count}/{n}")
    print(f"  median : {statistics.median(s_ms):.2f} ms")
    print(f"  p99    : {sorted(s_ms)[int(n * 0.99)]:.2f} ms")
    print(f"  max    : {max(s_ms):.2f} ms")
    print(f"  budget : 200ms per call (5fps = 200ms loop)")


if __name__ == "__main__":
    bench_sensor_call_latency()
    bench_throughput_1khz()
    bench_large_payload()
