from setaur._envelope import EnvelopeBuilder
from setaur._types import SourceType

TS = 1_000_000_000

def test_sensor_envelope_fields():
    builder = EnvelopeBuilder()
    env = builder.sensor('imu_0', SourceType.SENSOR, TS, {'x': 1.0})

    assert env['source_id']    == 'imu_0'
    assert env['source_type']  == 'sensor'
    assert env['sequence_num'] == 1
    assert env['timestamp_ns'] == TS
    assert env['data']         == {'x': 1.0}

def test_timestamp_is_passed_through_unchanged():
    builder = EnvelopeBuilder()
    env = builder.sensor('imu_0', SourceType.SENSOR, TS, {})

    assert env['timestamp_ns'] == TS

def test_sequence_increments_per_source():
    builder = EnvelopeBuilder()
    env1 = builder.sensor('imu_0', SourceType.SENSOR, TS, {})
    env2 = builder.sensor('imu_0', SourceType.SENSOR, TS, {})
    env3 = builder.sensor('imu_0', SourceType.SENSOR, TS, {})

    assert env1['sequence_num'] == 1
    assert env2['sequence_num'] == 2
    assert env3['sequence_num'] == 3

def test_sequence_is_independent_per_source():
    builder = EnvelopeBuilder()
    builder.sensor('imu_0', SourceType.SENSOR, TS, {})
    builder.sensor('imu_0', SourceType.SENSOR, TS, {})
    env = builder.sensor('imu_1', SourceType.SENSOR, TS, {})

    assert env['sequence_num'] == 1

def test_source_type_serializes_as_string():
    builder = EnvelopeBuilder()
    env = builder.sensor('sm.navigation', SourceType.STATE_MACHINE, TS, {})

    assert env['source_type'] == 'state_machine'
    assert isinstance(env['source_type'], str)

def test_data_is_passed_through_unchanged():
    builder = EnvelopeBuilder()
    data = {'accel': {'x': 0.1, 'y': 0.2, 'z': 9.8}, 'temperature': 38.0}
    env = builder.sensor('imu_0', SourceType.SENSOR, TS, data)

    assert env['data'] == data