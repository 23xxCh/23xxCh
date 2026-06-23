from pathlib import Path


README = Path("/home/user/h2track-xian/README.md")
CHECKLIST = Path("/home/user/h2track-xian/docs/rehearsal-checklist.md")


def test_readme_documents_standard_demo_rehearsal_flow():
    text = README.read_text(encoding="utf-8")

    assert "## Standard Demo Rehearsal Flow" in text
    assert "ros2 run h2track_utils demo_prep" in text
    assert "ros2 launch h2track_bringup demo.launch.py" in text
    assert "ros2 run h2track_utils demo_selfcheck --timeout 5.0" in text
    assert "If any step fails, do not start the formal demo." in text


def test_rehearsal_checklist_exists_with_stop_rules():
    text = CHECKLIST.read_text(encoding="utf-8")

    assert "# Rehearsal Checklist" in text
    assert "Step 1: demo_prep" in text
    assert "Step 2: demo.launch.py" in text
    assert "Step 3: demo_selfcheck" in text
    assert "DEMO PREP OK" in text
    assert "DEMO SELFCHECK OK" in text
    assert "Not ready for demo" in text
