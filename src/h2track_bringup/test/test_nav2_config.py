from pathlib import Path

import yaml


def _bt_params():
    config_path = (
        Path(__file__).resolve().parents[1] / "config" / "nav2_params.yaml"
    )
    with config_path.open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)["bt_navigator"]["ros__parameters"]


def test_bt_navigator_includes_through_poses_plugins_required_by_humble_defaults():
    plugin_lib_names = set(_bt_params()["plugin_lib_names"])
    assert "nav2_compute_path_through_poses_action_bt_node" in plugin_lib_names
    assert "nav2_remove_passed_goals_action_bt_node" in plugin_lib_names


def test_bt_navigator_exposes_both_default_behavior_tree_paths_for_humble():
    params = _bt_params()
    assert params["default_nav_to_pose_bt_xml"].endswith(
        "navigate_to_pose_w_replanning_and_recovery.xml"
    )
    assert params["default_nav_through_poses_bt_xml"].endswith(
        "navigate_through_poses_w_replanning_and_recovery.xml"
    )
