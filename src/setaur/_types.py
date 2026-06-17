from enum import StrEnum

class SourceType(StrEnum):
    SENSOR        = "sensor"
    STATE_MACHINE = "state_machine"
    METADATA      = "metadata"

class EventSourceType(StrEnum):
    USER     = "user"
    PLATFORM = "platform"
    SYSTEM   = "system"

class EventSeverity(StrEnum):
    INFO     = "info"
    WARNING  = "warning"
    ERROR    = "error"
    CRITICAL = "critical"

class SpanKind(StrEnum):
    UNSPECIFIED = "unspecified"
    INTERNAL    = "internal"
    PRODUCER    = "producer"
    CONSUMER    = "consumer"
    SENSOR      = "sensor"
    ACTUATOR    = "actuator"