from pathlib import Path


DEMO_BRIEF = Path("/home/user/h2track-xian/docs/demo-brief.md")


def test_demo_brief_exists_with_required_sections():
    text = DEMO_BRIEF.read_text(encoding="utf-8")

    assert "# Demo Brief" in text
    assert "## Project Goal" in text
    assert "## Live Demo Flow" in text
    assert "## What To Watch During The Demo" in text
    assert "## Closing Summary" in text
    assert "demo_prep" in text
    assert "demo.launch.py" in text
    assert "demo_selfcheck" in text
    assert "patrol" in text
    assert "tracking" in text
    assert "alarm" in text
