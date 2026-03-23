from h2track_tracking.autonomy_eval import (
    BenchmarkState,
    finalize_report,
    record_concentration_sample,
    record_mode_sample,
    record_signal,
)


def test_record_mode_sample_tracks_first_seen_and_transitions():
    state = BenchmarkState()

    record_mode_sample(state, "EXPLORE_MAPPING", 1.0)
    record_mode_sample(state, "EXPLORE_MAPPING", 1.2)
    record_mode_sample(state, "GAS_CONFIRM", 2.0)
    record_mode_sample(state, "SEEK_TRACK", 3.0)

    assert state.mode_transition_count == 2
    assert state.first_mode_time_by_name["EXPLORE_MAPPING"] == 1.0
    assert state.first_mode_time_by_name["GAS_CONFIRM"] == 2.0
    assert state.first_mode_time_by_name["SEEK_TRACK"] == 3.0
    assert state.latest_mode == "SEEK_TRACK"


def test_record_concentration_sample_tracks_peak_and_detection_threshold():
    state = BenchmarkState()

    record_concentration_sample(state, 0.2, 1.0, gas_threshold=0.5)
    record_concentration_sample(state, 0.8, 1.5, gas_threshold=0.5)
    record_concentration_sample(state, 0.6, 2.0, gas_threshold=0.5)

    assert state.max_concentration == 0.8
    assert state.first_gas_detected_time_sec == 1.5
    assert state.concentration_sample_count == 3


def test_record_signal_keeps_first_occurrence_only():
    state = BenchmarkState()

    record_signal(state, "map_frozen_time_sec", 10.0)
    record_signal(state, "map_frozen_time_sec", 12.0)

    assert state.map_frozen_time_sec == 10.0


def test_finalize_report_computes_duration_and_flags():
    state = BenchmarkState()
    state.start_time_sec = 5.0
    state.source_found_time_sec = 14.0
    state.tracking_handoff_failed_time_sec = None
    report = finalize_report(state, end_time_sec=15.0)

    assert report["duration_sec"] == 10.0
    assert report["source_found"] is True
    assert report["tracking_handoff_failed"] is False
    assert report["source_found_latency_sec"] == 9.0

