from pathlib import Path


def test_web_console_source_mentions_gas_link_diagnostics_panel():
    app_path = Path(__file__).resolve().parents[1] / "web_console" / "src" / "App.jsx"
    text = app_path.read_text(encoding="utf-8")

    assert "气体链路诊断" in text
    assert "原始读数" in text
    assert "信号状态" in text
