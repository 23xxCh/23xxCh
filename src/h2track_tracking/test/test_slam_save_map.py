from h2track_tracking.slam_save_map import _parse_args, build_save_map_request


def test_build_save_map_request_populates_nav2_service_fields():
    request = build_save_map_request(
        output_path="/tmp/warehouse_map",
        map_topic="/map",
        image_format="pgm",
        map_mode="trinary",
        free_thresh=0.2,
        occupied_thresh=0.7,
    )

    assert request.map_url == "/tmp/warehouse_map"
    assert request.map_topic == "/map"
    assert request.image_format == "pgm"
    assert request.map_mode == "trinary"
    assert request.free_thresh == 0.2
    assert request.occupied_thresh == 0.7


def test_parse_args_provides_expected_defaults():
    args = _parse_args(["--output", "/tmp/test_map"])

    assert args.service == "/map_saver/save_map"
    assert args.map_topic == "/map"
    assert args.image_format == "pgm"
    assert args.map_mode == "trinary"
    assert args.free_thresh == 0.25
    assert args.occupied_thresh == 0.65
    assert args.timeout == 15.0
