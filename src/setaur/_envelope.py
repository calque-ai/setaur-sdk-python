from collections import defaultdict
from ._types import SourceType

class EnvelopeBuilder:
    def __init__(self):
        self._seq: defaultdict[str, int] = defaultdict(int)

    def sensor(self, source_id: str, source_type: SourceType, timestamp_ns: int, data: dict) -> dict:
        self._seq[source_id] += 1
        return {
            'timestamp_ns': timestamp_ns,
            'source_id':    source_id,
            'source_type':  str(source_type),
            'sequence_num': self._seq[source_id],
            'data':         data,
        }