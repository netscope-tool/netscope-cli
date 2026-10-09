"""Tests for NetScope's persistent MTR terminal dashboard."""
import json
from datetime import datetime
from io import StringIO
from types import SimpleNamespace

from rich.console import Console

from netscope.cli import main as cli_main
from netscope.core.config import AppConfig
from netscope.modules.base import TestResult as MTRResult
from netscope.modules.mtr import MTRTest
from netscope.tui import mtr_live
from netscope.tui.terminal import AlternateScreenSession

_REPORT = """HOST: workstation
  1.|-- 192.0.2.1  0.0%  5  1.0  1.2  0.9  1.8  0.2
  2.|-- 198.51.100.2  0.0%  5  8.0  9.5  7.1  12.0  1.4
"""


class MemoryCsv:
    def __init__(self):
        self.rows = []

    def write_result(self, **row):
        self.rows.append(row)


def test_live_mtr_view_shows_latest_route_and_exit_hint():
    result = MTRResult(
        test_name="MTR Route Quality",
        target="example.com",
        status="success",
        timestamp=datetime(2026, 10, 9, 11, 0),
        duration=4.0,
        metrics={"hop_details": [{
            "hop": 1, "host": "192.0.2.1", "packet_loss_percent": 0.0,
            "sent": 5, "last_ms": 1.0, "avg_ms": 1.2, "best_ms": 0.9, "worst_ms": 1.8,
        }]},
        summary="Route sample complete.",
    )
    output = StringIO()
    console = Console(file=output, force_terminal=True, width=110, height=30)
    console.print(mtr_live.render_live_mtr_view("example.com", 5, 1, 7.2, result, "sampling next batch", 30))
    rendered = output.getvalue()
    assert "NETSCOPE  /  LIVE MTR" in rendered
    assert "192.0.2.1" in rendered
    assert "Route sample complete." in rendered
    assert "Press q or Ctrl+C to stop" in rendered


def test_live_dashboard_replaces_view_until_q(monkeypatch):
    screen_options = []

    class FakeLive:
        def __init__(self, renderable, **kwargs):
            screen_options.append(kwargs.get("screen"))

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def update(self, renderable, refresh=False):
            pass

    class CompletedProcess:
        def poll(self):
            return 0

        def communicate(self):
            return _REPORT, ""

    monkeypatch.setattr(mtr_live, "Live", FakeLive)
    monkeypatch.setattr(mtr_live.shutil, "which", lambda _: "/usr/bin/mtr")
    monkeypatch.setattr(mtr_live.subprocess, "Popen", lambda *args, **kwargs: CompletedProcess())
    monkeypatch.setattr(mtr_live.time, "sleep", lambda _: None)

    keys = iter([None, None, "q"])
    csv = MemoryCsv()
    scanner = MTRTest(None, csv)
    console = Console(file=StringIO(), force_terminal=True, width=100, height=30)
    session = mtr_live.run_live_mtr_dashboard(
        "example.com", scanner, console, cycles=3, key_reader=lambda: next(keys),
    )

    assert screen_options == [True]
    assert session.sample_count == 2
    assert session.result is not None
    assert session.result.metrics["live_sample_count"] == 2
    assert "Sample 1" in session.result.raw_output
    assert "Sample 2" in session.result.raw_output
    assert len(csv.rows) > 0

    nested_console = Console(file=StringIO(), force_terminal=True, width=100, height=30)
    with AlternateScreenSession(nested_console, enabled=True, wait_on_close=False):
        mtr_live.run_live_mtr_dashboard(
            "example.com", scanner, nested_console, cycles=3, key_reader=lambda: "q",
        )
    assert screen_options == [True, False]


def test_mtr_command_uses_report_batch_and_delimits_target():
    command = MTRTest.build_command("-example.invalid", cycles=3, executable="/usr/bin/mtr")
    assert "--report-cycles" in command
    assert command[command.index("--report-cycles") + 1] == "3"
    assert command[-2:] == ["--", "-example.invalid"]


def test_mtr_json_mode_keeps_stdout_machine_readable(monkeypatch, tmp_path, capsys):
    config = AppConfig(output_dir=tmp_path)
    system_info = SimpleNamespace(model_dump=lambda mode: {})
    monkeypatch.setattr(cli_main, "_init_context", lambda *args: (config, None, None, system_info))

    def fake_run(self, target, cycles=10, timeout=None):
        return MTRResult(
            test_name="MTR Route Quality", target=target, status="success",
            timestamp=datetime(2026, 10, 9, 12, 0), duration=1.0,
            metrics={"hop_count": 1}, summary="One route hop.",
        )

    monkeypatch.setattr(MTRTest, "run", fake_run)
    cli_main.mtr_scan(
        target="example.com", cycles=1, live=False, output_dir=None,
        output_format="json", verbose=False,
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "success"
    assert payload["target"] == "example.com"
