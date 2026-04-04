"""Tests for web config module."""

import pytest
from h2track_tracking.web.config import (
    DEMO_PREP_COMMAND,
    DEFAULT_LAUNCH_PROFILE,
    normalize_launch_profile,
    build_demo_launch_command,
    _coerce_bool_token,
)


def test_demo_prep_command():
    assert DEMO_PREP_COMMAND[0] == "ros2"
    assert "demo_prep" in DEMO_PREP_COMMAND


def test_default_launch_profile():
    assert DEFAULT_LAUNCH_PROFILE["scene"] == "warehouse"
    assert DEFAULT_LAUNCH_PROFILE["use_gaden"] == "true"


def test_coerce_bool_token_true():
    assert _coerce_bool_token(True, default="false") == "true"
    assert _coerce_bool_token("yes", default="false") == "true"
    assert _coerce_bool_token("1", default="false") == "true"


def test_coerce_bool_token_false():
    assert _coerce_bool_token(False, default="true") == "false"
    assert _coerce_bool_token("no", default="true") == "false"
    assert _coerce_bool_token("0", default="true") == "false"


def test_normalize_launch_profile_defaults():
    result = normalize_launch_profile(None)
    assert result["scene"] == "warehouse"
    assert result["use_gaden"] == "true"


def test_normalize_launch_profile_override():
    result = normalize_launch_profile({"scene": "baseline", "use_gaden": "false"})
    assert result["scene"] == "baseline"
    assert result["use_gaden"] == "false"


def test_normalize_launch_profile_invalid_scene():
    result = normalize_launch_profile({"scene": "invalid"})
    assert result["scene"] == "warehouse"


def test_build_demo_launch_command():
    cmd = build_demo_launch_command()
    assert "ros2" in cmd
    assert "launch" in cmd
    assert "demo.launch.py" in cmd
