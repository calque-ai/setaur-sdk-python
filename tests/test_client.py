import asyncio
import time
import cbor2
import pytest
from setaur._client import _Client, _NATS_URL
from setaur._types import SourceType


# --- fake transport ----------------------------------------------------------

class FakeNatsClient:
    def __init__(self):
        self.published: list[tuple[str, bytes]] = []
        self.closed = False

    async def publish(self, subject: str, payload: bytes) -> None:
        self.published.append((subject, payload))

    async def close(self) -> None:
        self.closed = True


def make_connector(fake_nc: FakeNatsClient):
    async def connector(url: str, credentials: str | None) -> FakeNatsClient:
        return fake_nc
    return connector


def make_client(robot_key: str = "rbt-test000001", fake_nc: FakeNatsClient = None) -> tuple[_Client, FakeNatsClient]:
    nc = fake_nc or FakeNatsClient()
    client = _Client(robot_key, creds_file=None, connector=make_connector(nc))
    return client, nc


def drain(client: _Client) -> None:
    """Close the client and give the drain loop time to flush."""
    client.close()


# --- init and connect --------------------------------------------------------

def test_connect_succeeds_with_fake_connector():
    client, _ = make_client()
    drain(client)


def test_connect_failure_raises_on_calling_thread():
    async def failing_connector(url, credentials):
        raise ConnectionRefusedError("no server")

    with pytest.raises(RuntimeError, match="no server"):
        _Client("rbt-test000001", creds_file=None, connector=failing_connector)


def test_invalid_robot_key_raises_before_connecting():
    with pytest.raises(ValueError, match="robot_key"):
        _Client("bad key!", creds_file=None, connector=make_connector(FakeNatsClient()))


def test_missing_creds_file_raises_before_connecting(tmp_path):
    with pytest.raises(FileNotFoundError, match="credentials file not found"):
        _Client("rbt-test000001", creds_file=str(tmp_path / "missing.creds"), connector=make_connector(FakeNatsClient()))


# --- sensor publishing -------------------------------------------------------

def test_sensor_publishes_to_correct_subject():
    client, nc = make_client(robot_key="rbt-bot42xxxxx")
    client.sensor("imu_0", SourceType.SENSOR, 1_000_000_000, {"x": 1.0})
    drain(client)

    assert len(nc.published) == 1
    subject, _ = nc.published[0]
    assert subject == "sensors.rbt-bot42xxxxx.imu_0"


def test_sensor_payload_is_valid_cbor():
    client, nc = make_client()
    client.sensor("imu_0", SourceType.SENSOR, 1_000_000_000, {"x": 1.0})
    drain(client)

    _, payload = nc.published[0]
    envelope = cbor2.loads(payload)
    assert envelope["source_id"] == "imu_0"
    assert envelope["source_type"] == "sensor"
    assert envelope["timestamp_ns"] == 1_000_000_000
    assert envelope["data"] == {"x": 1.0}


def test_sensor_sequence_increments_across_calls():
    client, nc = make_client()
    for _ in range(3):
        client.sensor("imu_0", SourceType.SENSOR, 1_000_000_000, {})
    drain(client)

    seqs = [cbor2.loads(p)["sequence_num"] for _, p in nc.published]
    assert seqs == [1, 2, 3]


def test_multiple_sources_have_independent_sequences():
    client, nc = make_client()
    client.sensor("imu_0", SourceType.SENSOR, 1_000_000_000, {})
    client.sensor("imu_0", SourceType.SENSOR, 1_000_000_000, {})
    client.sensor("lidar", SourceType.SENSOR, 1_000_000_000, {})
    drain(client)

    by_source = {cbor2.loads(p)["source_id"]: cbor2.loads(p)["sequence_num"] for _, p in nc.published}
    assert by_source["imu_0"] == 2
    assert by_source["lidar"] == 1


def test_invalid_source_id_raises():
    client, _ = make_client()
    with pytest.raises(ValueError, match="source_id"):
        client.sensor("bad id!", SourceType.SENSOR, 1_000_000_000, {})
    drain(client)


def test_subject_cached_after_first_call():
    client, nc = make_client(robot_key="rbt-bot1xxxxxx")
    client.sensor("imu_0", SourceType.SENSOR, 1_000_000_000, {})
    client.sensor("imu_0", SourceType.SENSOR, 1_000_000_000, {})
    drain(client)

    assert "imu_0" in client._subjects
    assert client._subjects["imu_0"] == "sensors.rbt-bot1xxxxxx.imu_0"


# --- queue full / drop -------------------------------------------------------

def test_full_queue_drops_and_logs_warning(caplog):
    import logging

    class BlockingNatsClient(FakeNatsClient):
        async def publish(self, subject, payload):
            await asyncio.sleep(60)  # hold the drain loop so the queue fills

    client, _ = make_client(fake_nc=BlockingNatsClient())

    with caplog.at_level(logging.WARNING, logger="setaur._client"):
        # fill past capacity; the drain loop is blocked so nothing drains
        for _ in range(client._q.maxsize + 10):
            client.sensor("imu_0", SourceType.SENSOR, 1_000_000_000, {})
        time.sleep(0.05)  # let the event loop process the enqueue callbacks

    assert any("publish queue full" in r.message for r in caplog.records)
    client.close()


# --- close -------------------------------------------------------------------

def test_close_drains_all_queued_messages():
    client, nc = make_client()
    for i in range(5):
        client.sensor("imu_0", SourceType.SENSOR, i, {"i": i})
    drain(client)

    assert len(nc.published) == 5


def test_close_closes_nats_connection():
    client, nc = make_client()
    drain(client)
    assert nc.closed
