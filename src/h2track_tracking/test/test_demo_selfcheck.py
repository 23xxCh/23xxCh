from h2track_tracking.demo_selfcheck import RuntimeSnapshot, evaluate_demo_health, merge_runtime_samples


def test_selfcheck_reports_missing_requirements():
    result = evaluate_demo_health(nodes=[], topics=[], tf_edges=[], active_lifecycle_nodes=[])

    assert result.ok is False
    assert any("nav2" in error.lower() for error in result.errors)
    assert any("/gas_concentration" in error for error in result.errors)
    assert any("map -> odom" in error.lower() for error in result.errors)


def test_selfcheck_passes_when_required_resources_exist():
    result = evaluate_demo_health(
        nodes=[
            "map_server",
            "amcl",
            "controller_server",
            "planner_server",
            "bt_navigator",
            "bt_node_runner",
            "gaden_adapter_node",
            "gaden_sensor_gate_node",
        ],
        topics=["/odom", "/scan", "/gas_concentration"],
        tf_edges=[("map", "odom"), ("odom", "base_link"), ("gaden_map", "base_link")],
        active_lifecycle_nodes=["amcl", "bt_navigator", "controller_server", "planner_server"],
    )

    assert result.ok is True
    assert result.errors == []


def test_merge_runtime_samples_unions_discovered_resources_across_polls():
    merged = merge_runtime_samples(
        [
            RuntimeSnapshot(
                nodes={"map_server", "amcl"},
                topics={"/odom"},
                tf_edges={("map", "odom")},
                active_lifecycle_nodes={"amcl"},
            ),
            RuntimeSnapshot(
                nodes={
                    "controller_server",
                    "planner_server",
                    "bt_navigator",
                    "bt_node_runner",
                    "gaden_adapter_node",
                    "gaden_sensor_gate_node",
                },
                topics={"/scan", "/gas_concentration"},
                tf_edges={("odom", "base_link"), ("gaden_map", "base_link")},
                active_lifecycle_nodes={"controller_server", "planner_server", "bt_navigator"},
            ),
        ]
    )

    assert "gaden_adapter_node" in merged.nodes
    assert "/gas_concentration" in merged.topics
    assert ("gaden_map", "base_link") in merged.tf_edges
    assert "bt_navigator" in merged.active_lifecycle_nodes
