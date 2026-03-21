from pathlib import Path


DEMO_SCRIPT = Path("/home/user/h2track-xian/docs/demo-script-2min.md")


def test_demo_script_exists_with_required_sections():
    text = DEMO_SCRIPT.read_text(encoding="utf-8")

    assert "# 2-Minute Demo Script" in text
    assert "## 开场" in text
    assert "## 演示过程" in text
    assert "## 结束总结" in text
    assert "demo_prep" in text
    assert "demo.launch.py" in text
    assert "demo_selfcheck" in text
    assert "巡检" in text
    assert "追踪" in text
    assert "报警" in text
