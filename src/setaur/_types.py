from enum import StrEnum

class SourceType(StrEnum):
    SENSOR        = "sensor"
    STATE_MACHINE = "state_machine"
    METADATA      = "metadata"