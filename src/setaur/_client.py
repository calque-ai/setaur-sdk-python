import asyncio
import logging
import os
import re
import threading
from typing import Protocol
import cbor2
import nats

from ._envelope import EnvelopeBuilder
from ._types import SourceType

log = logging.getLogger(__name__)

_instance: "_Client | None" = None

_QUEUE_MAX = 2048
_NATS_URL  = "nats://localhost:4222"
_CREDS_ENV = "SETAUR_CREDS_FILE"
_ROBOT_KEY_RE  = re.compile(r'^rbt-[a-z0-9]+$')
_SOURCE_ID_RE  = re.compile(r'^[a-zA-Z0-9_-]+$')


class NatsClient(Protocol):
    async def publish(self, subject: str, payload: bytes) -> None: ...
    async def close(self) -> None: ...


class NatsConnector(Protocol):
    async def __call__(self, url: str, credentials: str | None) -> NatsClient: ...


async def _default_connector(url: str, credentials: str | None) -> NatsClient:
    opts: dict = {"servers": [url]}
    if credentials:
        opts["credentials"] = credentials
    return await nats.connect(**opts)


def _validate_robot_key(value: str) -> None:
    if not _ROBOT_KEY_RE.match(value):
        raise ValueError(
            f"setaur: robot_key '{value}' must match rbt-[a-z0-9]+ (e.g. rbt-nkjttwwvw4z7)."
        )


def _validate_source_id(value: str) -> None:
    if not _SOURCE_ID_RE.match(value):
        raise ValueError(
            f"setaur: source_id '{value}' contains characters not allowed in a source_id. "
            "Use only letters, digits, hyphens, and underscores."
        )


class _Client:
    def __init__(
        self,
        robot_key: str,
        creds_file: str | None,
        connector: NatsConnector = _default_connector,
    ):
        _validate_robot_key(robot_key)

        creds = creds_file or os.environ.get(_CREDS_ENV)
        if creds and not os.path.isfile(creds):
            raise FileNotFoundError(f"setaur: credentials file not found: {creds}")

        self._robot_key = robot_key
        self._creds     = creds
        self._connector = connector
        self._envelope  = EnvelopeBuilder()
        self._subjects: dict[str, str] = {}
        self._q: asyncio.Queue[tuple[str, bytes] | None] = asyncio.Queue(maxsize=_QUEUE_MAX)
        self._loop      = asyncio.new_event_loop()
        self._ready     = threading.Event()
        self._error: BaseException | None = None
        self._thread    = threading.Thread(target=self._run, name="setaur-sdk", daemon=True)
        self._thread.start()

        if not self._ready.wait(timeout=10):
            msg = str(self._error) if self._error else f"timed out connecting to {_NATS_URL}"
            raise RuntimeError(f"setaur: {msg}")

        if self._error:
            raise RuntimeError(f"setaur: {self._error}") from self._error

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connect())
            self._loop.run_until_complete(self._drain())
        except Exception as exc:
            self._error = exc
            self._ready.set()

    async def _connect(self) -> None:
        self._nc = await self._connector(_NATS_URL, self._creds)
        self._ready.set()

    async def _drain(self) -> None:
        while True:
            item = await self._q.get()      # yield until at least one item arrives
            if item is None:
                break
            while item is not None:         # batch: consume all already-queued items
                subject, payload = item
                await self._nc.publish(subject, payload)
                try:
                    item = self._q.get_nowait()
                except asyncio.QueueEmpty:
                    item = None
        await self._nc.close()

    def sensor(
        self,
        source_id: str,
        source_type: SourceType,
        timestamp_ns: int,
        data: dict,
    ) -> None:
        if source_id not in self._subjects:
            _validate_source_id(source_id)
            self._subjects[source_id] = f"sensors.{self._robot_key}.{source_id}"

        envelope = self._envelope.sensor(source_id, source_type, timestamp_ns, data)
        item     = (self._subjects[source_id], cbor2.dumps(envelope))

        def _enqueue():
            try:
                self._q.put_nowait(item)
            except asyncio.QueueFull:
                log.warning("setaur: publish queue full, dropping message for %s", source_id)

        self._loop.call_soon_threadsafe(_enqueue)

    def close(self) -> None:
        self._loop.call_soon_threadsafe(self._q.put_nowait, None)
        self._thread.join(timeout=5)
        if self._thread.is_alive():
            log.warning("setaur: background thread did not stop cleanly within timeout")


def init(robot_key: str, creds_file: str | None = None) -> None:
    global _instance
    if _instance is not None:
        _instance.close()
    _instance = _Client(robot_key, creds_file)


def get_client() -> _Client:
    if _instance is None:
        raise RuntimeError("setaur.init() has not been called")
    return _instance
