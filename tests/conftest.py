import cbor2
import pytest
import setaur._client as _client_module
from setaur._client import _Client


@pytest.fixture(autouse=True)
def reset_client():
    """Ensure the module-level singleton is clean before and after every test."""
    _client_module._instance = None
    yield
    if _client_module._instance is not None:
        _client_module._instance.close()
    _client_module._instance = None


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


def all_envelopes(nc: FakeNatsClient) -> dict[str, dict]:
    """Return envelopes keyed by event_type for easy lookup."""
    return {cbor2.loads(p)["event_type"]: cbor2.loads(p) for _, p in nc.published}
