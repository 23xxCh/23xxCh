from pathlib import Path

from h2track_tracking.demo_prep import (
    MatchedProcess,
    check_required_packages,
    evaluate_prep_result,
    find_stale_processes,
    main,
)


PS_OUTPUT = """
user       10001    1282  0 00:00 ?        00:00:01 gzserver --verbose -s libgazebo_ros_init.so -s libgazebo_ros_factory.so /home/user/h2track-xian/install/h2track_sim/share/h2track_sim/worlds/h2track_lab.world
user       10002    1282  0 00:00 ?        00:00:00 gazebo --verbose -s libgazebo_ros_init.so -s libgazebo_ros_factory.so /tmp/other.world
user       10003    1282  0 00:00 ?        00:00:00 /opt/ros/humble/lib/nav2_lifecycle_manager/lifecycle_manager --ros-args -r __node:=lifecycle_manager_navigation
user       10004    1282  0 00:00 ?        00:00:00 /opt/ros/humble/lib/nav2_lifecycle_manager/lifecycle_manager --ros-args -r __node:=other_lifecycle_manager
"""


def test_matches_only_h2track_demo_processes():
    processes = find_stale_processes(PS_OUTPUT)

    assert processes == [
        MatchedProcess(pid=10001, kind="gazebo", command="gzserver --verbose -s libgazebo_ros_init.so -s libgazebo_ros_factory.so /home/user/h2track-xian/install/h2track_sim/share/h2track_sim/worlds/h2track_lab.world"),
        MatchedProcess(pid=10003, kind="nav2_lifecycle_manager", command="/opt/ros/humble/lib/nav2_lifecycle_manager/lifecycle_manager --ros-args -r __node:=lifecycle_manager_navigation"),
    ]


def test_dry_run_reports_not_ready_when_stale_processes_exist():
    report = evaluate_prep_result(
        processes=[MatchedProcess(pid=10001, kind="gazebo", command="gzserver ...")],
        package_status={"h2track_sim": True, "h2track_tracking": True, "simulated_gas_sensor": True, "gaden_player": True},
        dry_run=True,
        kill_failures=[],
    )

    assert report.ok is False
    assert "dry-run found stale processes" in report.errors


def test_missing_packages_fail_the_report():
    report = evaluate_prep_result(
        processes=[],
        package_status={"h2track_sim": True, "h2track_tracking": True, "simulated_gas_sensor": False, "gaden_player": True},
        dry_run=False,
        kill_failures=[],
    )

    assert report.ok is False
    assert "Missing packages: simulated_gas_sensor" in report.errors


def test_package_check_marks_missing_packages():
    status = check_required_packages(lambda name: None if name == "gaden_player" else f"/prefix/{name}")

    assert status["h2track_sim"] is True
    assert status["h2track_tracking"] is True
    assert status["simulated_gas_sensor"] is True
    assert status["gaden_player"] is False




SCENE_PS_OUTPUT = """
user       11001    1282  0 00:00 ?        00:00:01 gzserver --verbose -s libgazebo_ros_init.so -s libgazebo_ros_factory.so /tmp/h2track/scenes/baseline/h2track_lab.world
user       11002    1282  0 00:00 ?        00:00:01 gzserver --verbose -s libgazebo_ros_init.so -s libgazebo_ros_factory.so /tmp/h2track/scenes/warehouse/warehouse.world
user       11003    1282  0 00:00 ?        00:00:00 /opt/ros/humble/lib/nav2_lifecycle_manager/lifecycle_manager --ros-args -r __node:=lifecycle_manager_navigation
"""


def test_matches_only_selected_scene_world_processes():
    processes = find_stale_processes(
        SCENE_PS_OUTPUT,
        Path('/tmp/h2track/scenes/warehouse/warehouse.world'),
    )

    assert processes == [
        MatchedProcess(
            pid=11002,
            kind='gazebo',
            command='gzserver --verbose -s libgazebo_ros_init.so -s libgazebo_ros_factory.so /tmp/h2track/scenes/warehouse/warehouse.world',
        ),
        MatchedProcess(
            pid=11003,
            kind='nav2_lifecycle_manager',
            command='/opt/ros/humble/lib/nav2_lifecycle_manager/lifecycle_manager --ros-args -r __node:=lifecycle_manager_navigation',
        ),
    ]


def test_cli_warehouse_auto_mode_skips_gaden_package_requirement(capsys):
    exit_code = main(
        ['--scene', 'warehouse'],
        ps_output='',
        package_resolver=lambda name: None if name in ('simulated_gas_sensor', 'gaden_player') else f'/prefix/{name}',
        scene_profile_loader=lambda scene_name: {
            'world': 'scenes/warehouse/warehouse.world',
            'use_gaden': False,
        },
        package_share_resolver=lambda package_name: '/tmp/h2track',
    )

    captured = capsys.readouterr().out
    assert exit_code == 0
    assert 'package ok: h2track_sim' in captured
    assert 'package ok: h2track_tracking' in captured
    assert 'DEMO PREP OK' in captured
    assert 'missing package: simulated_gas_sensor' not in captured
    assert 'missing package: gaden_player' not in captured

def test_cli_warehouse_auto_mode_requires_gaden_packages_when_scene_defaults_true(capsys):
    exit_code = main(
        ['--scene', 'warehouse'],
        ps_output='',
        package_resolver=lambda name: None if name in ('simulated_gas_sensor', 'gaden_player') else f'/prefix/{name}',
        scene_profile_loader=lambda scene_name: {
            'world': 'scenes/warehouse/warehouse.world',
            'use_gaden': True,
        },
        package_share_resolver=lambda package_name: '/tmp/h2track',
    )

    captured = capsys.readouterr().out
    assert exit_code == 1
    assert 'missing package: simulated_gas_sensor' in captured
    assert 'missing package: gaden_player' in captured
    assert 'DEMO PREP FAILED' in captured

def test_cli_dry_run_does_not_kill_processes(capsys):
    killed = []

    exit_code = main(
        ["--dry-run"],
        ps_output=PS_OUTPUT,
        kill_process=lambda pid: killed.append(pid),
        package_resolver=lambda name: f"/prefix/{name}",
        scene_profile_loader=lambda scene_name: {
            'world': '/home/user/h2track-xian/install/h2track_sim/share/h2track_sim/worlds/h2track_lab.world',
            'use_gaden': True,
        },
        package_share_resolver=lambda package_name: '/tmp/h2track',
    )

    captured = capsys.readouterr().out
    assert exit_code == 1
    assert killed == []
    assert "would kill pid=10001" in captured
    assert "would kill pid=10003" in captured
    assert "DEMO PREP FAILED" in captured
