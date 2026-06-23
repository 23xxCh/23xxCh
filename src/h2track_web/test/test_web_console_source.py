from pathlib import Path


def test_web_console_source_mentions_gas_link_diagnostics_panel():
    # Web console source lives in h2track_tracking/web_console
    repo_root = Path(__file__).resolve().parents[2]
    app_path = repo_root / "h2track_tracking" / "web_console" / "src" / "App.jsx"
    text = app_path.read_text(encoding="utf-8")

    assert "气体链路诊断" in text
    assert "原始读数" in text
    assert "信号状态" in text
