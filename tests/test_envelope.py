from setaur._envelope import EnvelopeBuilder
from setaur._types import SourceType, EventSourceType, EventSeverity, SpanKind

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


# ---------------------------------------------------------------------------
# event()
# ---------------------------------------------------------------------------

def test_event_envelope_required_fields():
    builder = EnvelopeBuilder()
    env = builder.event('nav', 'state_transition', 'Entered AUTONOMOUS', EventSeverity.INFO, TS)

    assert env['source_id']   == 'nav'
    assert env['event_type']  == 'state_transition'
    assert env['message']     == 'Entered AUTONOMOUS'
    assert env['severity']    == 'info'
    assert env['start_ns']    == TS
    assert env['sequence_num'] == 1

def test_event_source_type_defaults_to_user():
    builder = EnvelopeBuilder()
    env = builder.event('nav', 'state_transition', 'msg', EventSeverity.INFO, TS)

    assert env['source_type'] == 'user'
    assert isinstance(env['source_type'], str)

def test_event_source_type_override():
    builder = EnvelopeBuilder()
    env = builder.event('nav', 'watchdog', 'msg', EventSeverity.WARNING, TS,
                        source_type=EventSourceType.SYSTEM)

    assert env['source_type'] == 'system'

def test_event_severity_serializes_as_string():
    builder = EnvelopeBuilder()
    env = builder.event('nav', 'fault', 'msg', EventSeverity.CRITICAL, TS)

    assert env['severity'] == 'critical'
    assert isinstance(env['severity'], str)

def test_event_kind_serializes_as_string():
    builder = EnvelopeBuilder()
    env = builder.event('nav', 'cmd', 'msg', EventSeverity.INFO, TS,
                        kind=SpanKind.ACTUATOR)

    assert env['kind'] == 'actuator'
    assert isinstance(env['kind'], str)

def test_event_sequence_increments_per_source():
    builder = EnvelopeBuilder()
    env1 = builder.event('nav', 'e', 'msg', EventSeverity.INFO, TS)
    env2 = builder.event('nav', 'e', 'msg', EventSeverity.INFO, TS)
    env3 = builder.event('nav', 'e', 'msg', EventSeverity.INFO, TS)

    assert env1['sequence_num'] == 1
    assert env2['sequence_num'] == 2
    assert env3['sequence_num'] == 3

def test_event_sequence_is_independent_per_source():
    builder = EnvelopeBuilder()
    builder.event('nav', 'e', 'msg', EventSeverity.INFO, TS)
    builder.event('nav', 'e', 'msg', EventSeverity.INFO, TS)
    env = builder.event('drive', 'e', 'msg', EventSeverity.INFO, TS)

    assert env['sequence_num'] == 1

def test_event_sequence_is_independent_from_sensor():
    builder = EnvelopeBuilder()
    builder.sensor('nav', SourceType.SENSOR, TS, {})
    builder.sensor('nav', SourceType.SENSOR, TS, {})
    env = builder.event('nav', 'e', 'msg', EventSeverity.INFO, TS)

    assert env['sequence_num'] == 1

def test_event_optional_fields_absent_by_default():
    builder = EnvelopeBuilder()
    env = builder.event('nav', 'e', 'msg', EventSeverity.INFO, TS)

    assert 'end_ns'    not in env
    assert 'trace_id'  not in env
    assert 'span_id'   not in env
    assert 'parent_id' not in env
    assert 'attrs'     not in env
    assert 'data'      not in env

def test_event_optional_fields_present_when_set():
    builder = EnvelopeBuilder()
    env = builder.event('nav', 'e', 'msg', EventSeverity.INFO, TS,
                        end_ns=TS + 1000,
                        trace_id='aabbcc',
                        span_id='11223344',
                        parent_id='00112233',
                        attrs={'key': 'val'},
                        data={'raw': True})

    assert env['end_ns']    == TS + 1000
    assert env['trace_id']  == 'aabbcc'
    assert env['span_id']   == '11223344'
    assert env['parent_id'] == '00112233'
    assert env['attrs']     == {'key': 'val'}
    assert env['data']      == {'raw': True}