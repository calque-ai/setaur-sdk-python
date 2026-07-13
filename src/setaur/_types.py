from enum import StrEnum

class SourceType(StrEnum):
    SENSOR        = "sensor"
    METADATA      = "metadata"

class EventSourceType(StrEnum):
    USER     = "user"
    PLATFORM = "platform"
    SYSTEM   = "system"
    STATE_MACHINE = "state_machine"

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