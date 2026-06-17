from ._types import SourceType
from ._client import init, get_client


def sensor(
    source_id: str,
    source_type: SourceType,
    timestamp_ns: int,
    data: dict,
) -> None:
    get_client().sensor(source_id, source_type, timestamp_ns, data)


__all__ = ["SourceType", "init", "sensor"]
