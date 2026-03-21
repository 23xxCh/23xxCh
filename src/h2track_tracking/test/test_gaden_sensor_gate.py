from h2track_tracking.gaden_sensor_gate import (
    GateAction,
    SensorGateConfig,
    SensorGateState,
    build_sensor_process_command,
)


def test_gate_waits_until_transform_is_available():
    gate = SensorGateState(SensorGateConfig(timeout_sec=20.0, poll_period_sec=0.5))

    action = gate.step(has_transform=False, elapsed_sec=5.0)

    assert action is GateAction.WAIT


def test_gate_launches_once_after_transform_becomes_available():
    gate = SensorGateState(SensorGateConfig(timeout_sec=20.0, poll_period_sec=0.5))

    assert gate.step(has_transform=False, elapsed_sec=2.0) is GateAction.WAIT
    assert gate.step(has_transform=True, elapsed_sec=3.0) is GateAction.LAUNCH
    assert gate.step(has_transform=True, elapsed_sec=4.0) is GateAction.RUNNING


def test_gate_requires_multiple_ready_checks_before_launch():
    gate = SensorGateState(SensorGateConfig(timeout_sec=30.0, poll_period_sec=0.5, stable_ready_count=3))

    assert gate.step(has_transform=True, elapsed_sec=1.0) is GateAction.WAIT
    assert gate.step(has_transform=True, elapsed_sec=1.5) is GateAction.WAIT
    assert gate.step(has_transform=True, elapsed_sec=2.0) is GateAction.LAUNCH


def test_gate_times_out_if_transform_never_appears():
    gate = SensorGateState(SensorGateConfig(timeout_sec=12.0, poll_period_sec=0.5))

    action = gate.step(has_transform=False, elapsed_sec=12.1)

    assert action is GateAction.FAIL


def test_sensor_process_command_preserves_sensor_parameters():
    command = build_sensor_process_command(
        executable_path='/opt/ros/humble/lib/simulated_gas_sensor/simulated_gas_sensor',
        use_sim_time=True,
        topic='/gaden/sensor_reading',
        fixed_frame='gaden_map',
        sensor_frame='base_link',
        sensor_model=30,
        rate=5.0,
        use_pid_correction_factors=False,
        sensor_node_name='gaden_pid_sensor',
    )

    assert command[:2] == [
        '/opt/ros/humble/lib/simulated_gas_sensor/simulated_gas_sensor',
        '--ros-args',
    ]
    assert '-r' in command
    assert '__node:=gaden_pid_sensor' in command
    assert 'use_sim_time:=true' in command
    assert 'topic:=/gaden/sensor_reading' in command
    assert 'fixed_frame:=gaden_map' in command
    assert 'sensor_frame:=base_link' in command
    assert 'sensor_model:=30' in command
    assert 'rate:=5.0' in command
    assert 'use_PID_correction_factors:=false' in command
