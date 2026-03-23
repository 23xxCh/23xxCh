from h2track_tracking.nav2_startup_gate import (
    GateAction,
    Nav2StartupGateConfig,
    Nav2StartupGateState,
)


def test_gate_waits_until_both_tf_and_service_are_ready():
    state = Nav2StartupGateState(Nav2StartupGateConfig(timeout_sec=5.0, stable_ready_count=1))

    assert state.step(tf_ready=False, service_ready=True, startup_result=None, elapsed_sec=0.5) is GateAction.WAIT
    assert state.step(tf_ready=True, service_ready=False, startup_result=None, elapsed_sec=1.0) is GateAction.WAIT


def test_gate_requires_stable_ready_samples_before_startup():
    state = Nav2StartupGateState(Nav2StartupGateConfig(timeout_sec=5.0, stable_ready_count=2))

    assert state.step(tf_ready=True, service_ready=True, startup_result=None, elapsed_sec=0.5) is GateAction.WAIT
    assert state.step(tf_ready=True, service_ready=True, startup_result=None, elapsed_sec=1.0) is GateAction.STARTUP


def test_gate_resets_stability_counter_when_dependency_drops():
    state = Nav2StartupGateState(Nav2StartupGateConfig(timeout_sec=5.0, stable_ready_count=2))

    assert state.step(tf_ready=True, service_ready=True, startup_result=None, elapsed_sec=0.5) is GateAction.WAIT
    assert state.step(tf_ready=False, service_ready=True, startup_result=None, elapsed_sec=1.0) is GateAction.WAIT
    assert state.step(tf_ready=True, service_ready=True, startup_result=None, elapsed_sec=1.5) is GateAction.WAIT
    assert state.step(tf_ready=True, service_ready=True, startup_result=None, elapsed_sec=2.0) is GateAction.STARTUP


def test_gate_tracks_startup_request_until_success():
    state = Nav2StartupGateState(Nav2StartupGateConfig(timeout_sec=5.0, stable_ready_count=1))

    assert state.step(tf_ready=True, service_ready=True, startup_result=None, elapsed_sec=0.5) is GateAction.STARTUP
    assert state.step(tf_ready=True, service_ready=True, startup_result=None, elapsed_sec=1.0) is GateAction.MONITOR
    assert state.step(tf_ready=True, service_ready=True, startup_result=True, elapsed_sec=1.5) is GateAction.COMPLETE


def test_gate_fails_when_startup_service_returns_failure():
    state = Nav2StartupGateState(Nav2StartupGateConfig(timeout_sec=5.0, stable_ready_count=1))

    assert state.step(tf_ready=True, service_ready=True, startup_result=None, elapsed_sec=0.5) is GateAction.STARTUP
    assert state.step(tf_ready=True, service_ready=True, startup_result=False, elapsed_sec=1.0) is GateAction.FAIL


def test_gate_retries_startup_before_failing_when_retry_budget_exists():
    state = Nav2StartupGateState(
        Nav2StartupGateConfig(timeout_sec=5.0, stable_ready_count=1, max_startup_retries=1)
    )

    assert state.step(tf_ready=True, service_ready=True, startup_result=None, elapsed_sec=0.5) is GateAction.STARTUP
    # first startup failure should not fail immediately; gate should retry
    assert state.step(tf_ready=True, service_ready=True, startup_result=False, elapsed_sec=1.0) is GateAction.WAIT
    assert state.step(tf_ready=True, service_ready=True, startup_result=None, elapsed_sec=1.5) is GateAction.STARTUP
    # second failure exhausts retry budget
    assert state.step(tf_ready=True, service_ready=True, startup_result=False, elapsed_sec=2.0) is GateAction.FAIL


def test_gate_fails_when_timeout_is_reached_before_ready():
    state = Nav2StartupGateState(Nav2StartupGateConfig(timeout_sec=1.0, stable_ready_count=1))

    assert state.step(tf_ready=False, service_ready=False, startup_result=None, elapsed_sec=1.0) is GateAction.FAIL
