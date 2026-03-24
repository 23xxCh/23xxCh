from h2track_tracking.demo_regression import (
    RegressionRound,
    parse_source_found_output,
    summarize_rounds,
)


def test_parse_source_found_output_detects_true():
    assert parse_source_found_output("data: true\n---\n") is True
    assert parse_source_found_output("header\ndata: True\n") is True


def test_parse_source_found_output_rejects_false_or_empty():
    assert parse_source_found_output("data: false\n") is False
    assert parse_source_found_output("") is False


def test_summarize_rounds_computes_success_rate_and_latency():
    rounds = [
        RegressionRound(index=1, source_found=True, source_found_time=82.1, notes=""),
        RegressionRound(index=2, source_found=False, source_found_time=None, notes="timeout"),
        RegressionRound(index=3, source_found=True, source_found_time=95.6, notes=""),
    ]

    summary = summarize_rounds(rounds)

    assert summary["rounds"] == 3
    assert summary["successes"] == 2
    assert summary["success_rate"] == 2 / 3
    assert summary["mean_source_found_time"] == (82.1 + 95.6) / 2


def test_summarize_rounds_handles_zero_success():
    rounds = [
        RegressionRound(index=1, source_found=False, source_found_time=None, notes="timeout"),
        RegressionRound(index=2, source_found=False, source_found_time=None, notes="timeout"),
    ]

    summary = summarize_rounds(rounds)

    assert summary["rounds"] == 2
    assert summary["successes"] == 0
    assert summary["success_rate"] == 0.0
    assert summary["mean_source_found_time"] is None
