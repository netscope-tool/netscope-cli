"""Offline tests for bounded Nmap vulnerability scans and live dashboard updates."""
import threading
import time
from datetime import datetime
from io import StringIO

import pytest
from rich.console import Console

from netscope.cli.formatters import format_test_result
from netscope.modules.base import TestResult as NmapResult
from netscope.modules.nmap_scan import (
    NMAP_PROFILES,
    NMAP_VULN_SCRIPT_EXPRESSION,
    NmapScanTest,
    build_nmap_command,
    parse_nmap_xml,
    validate_vulnerability_scope,
)
from netscope.tui import nmap_live

_XML = """<?xml version="1.0"?>
<nmaprun scanner="nmap" version="7.95" xmloutputversion="1.05">
<scaninfo type="connect" protocol="tcp" numservices="20" services="1-20"/>
<verbose level="0"/><debugging level="0"/>
<taskprogress task="Connect Scan" time="1" percent="42.5" remaining="2"/>
<host starttime="1" endtime="2">
 <status state="up" reason="syn-ack" reason_ttl="64"/>
 <address addr="192.0.2.10" addrtype="ipv4"/>
 <hostnames><hostname name="app.example.test" type="user"/></hostnames>
 <ports><port protocol="tcp" portid="443">
  <state state="open" reason="syn-ack" reason_ttl="64"/>
  <service name="https" product="ExampleTLS" version="1.2" method="probed" conf="10"/>
  <script id="http-vuln-test" output="VULNERABLE: CVE-2024-12345; review required"/>
 </port></ports>
</host>
<runstats><finished time="2" elapsed="1.00" exit="success"/><hosts up="1" down="0" total="1"/></runstats>
</nmaprun>
"""


class MemoryCsv:
    def __init__(self):
        self.rows = []

    def write_result(self, **row):
        self.rows.append(row)


class FakePipe:
    def __init__(self, chunks):
        self.chunks = iter(chunks)

    def read1(self, _size):
        return next(self.chunks, b"")

    def read(self, _size):
        return self.read1(_size)


class FakeProcess:
    def __init__(self, stdout_chunks, stderr_chunks=(b"",)):
        self.stdout = FakePipe(stdout_chunks)
        self.stderr = FakePipe(stderr_chunks)
        self.returncode = 0
        self.terminated = False

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = -15

    def kill(self):
        self.returncode = -9


def test_vulnerability_scope_is_explicit_and_bounded():
    assert validate_vulnerability_scope(["one.example", "192.0.2.10"], "22,80,443") == [
        "one.example", "192.0.2.10",
    ]
    for target in ("192.0.2.0/24", "192.0.2.1-10", "one.example,other.example", "@targets.txt"):
        try:
            validate_vulnerability_scope([target])
        except ValueError:
            pass
        else:
            raise AssertionError(f"unsafe target expression accepted: {target}")
    try:
        validate_vulnerability_scope(["one.example"], "1-101")
    except ValueError:
        pass
    else:
        raise AssertionError("over-limit port scope was accepted")


def test_vulnerability_profile_uses_safe_limited_nse_and_batch_arguments():
    command = build_nmap_command(["one.example", "192.0.2.10"], profile="vuln")
    assert command[-3:] == ["--", "one.example", "192.0.2.10"]
    assert "--script" in command
    assert command[command.index("--script") + 1] == NMAP_VULN_SCRIPT_EXPRESSION
    assert "--stats-every" in command and command[command.index("--stats-every") + 1] == "1s"
    assert "--top-ports" in command
    custom = build_nmap_command("one.example", ports="443", profile="vuln")
    assert "-p" in custom and "--top-ports" not in custom
    assert "exploit" in NMAP_VULN_SCRIPT_EXPRESSION and "dos" in NMAP_VULN_SCRIPT_EXPRESSION


def test_vulnerability_scanner_api_cannot_bypass_timeout_or_script_guards():
    scanner = NmapScanTest(None, MemoryCsv())
    with pytest.raises(ValueError, match="900 seconds"):
        scanner.run("one.example", profile="vuln", timeout=901)
    with pytest.raises(ValueError, match="Custom Nmap arguments"):
        scanner.run("one.example", profile="vuln", extra_args=["--script", "all"])
    with pytest.raises(ValueError, match="900 seconds"):
        scanner.run_streaming("one.example", profile="vuln", timeout=901)


def test_custom_ports_replace_conflicting_quick_profile_flags():
    command = build_nmap_command("one.example", ports="443", profile="connect")
    assert "-F" not in command
    assert command[command.index("-p") + 1] == "443"
    assert "--stats-every" in command
    assert set(NMAP_PROFILES) == {"connect", "service", "udp", "vuln"}


def test_parser_extracts_per_host_service_and_vulnerability_script_evidence():
    metrics = parse_nmap_xml(_XML)
    assert metrics["hosts_up"] == 1
    assert metrics["host_count"] == 1
    assert metrics["hosts"][0]["target"] == "app.example.test"
    assert metrics["open_ports"] == [443]
    finding = metrics["vulnerability_findings"][0]
    assert finding["state"] == "vulnerable"
    assert finding["cve_ids"] == ["CVE-2024-12345"]
    assert finding["severity"] == "not rated by Nmap output"


def test_vulnerability_summary_renders_cve_evidence_and_no_false_severity():
    metrics = parse_nmap_xml(_XML)
    result = NmapResult(
        test_name="Nmap Vulnerability Scan", target="app [bold]untrusted[/bold]", status="success",
        timestamp=datetime.now(), duration=1.0, metrics=metrics,
        summary="Nmap scan [red]finished[/red]", raw_output="<script output='[link]literal[/link]'>",
    )
    output = StringIO()
    format_test_result(result, Console(file=output, width=120, force_terminal=False))
    rendered = output.getvalue()
    assert "NSE Vulnerability Script Evidence" in rendered
    assert "CVE-2024-12345" in rendered
    assert "not rated by Nmap output" not in rendered
    assert "[bold]untrusted[/bold]" in rendered
    assert "[red]finished[/red]" in rendered
    assert "[link]literal[/link]" in rendered


def test_streaming_parser_emits_progress_and_host_updates(monkeypatch):
    process = FakeProcess([_XML[:140].encode(), _XML[140:900].encode(), _XML[900:].encode()])
    observed = {}
    monkeypatch.setattr("netscope.modules.nmap_scan.shutil.which", lambda _: "/usr/bin/nmap")
    def fake_popen(command, **kwargs):
        observed["command"] = command
        return process
    monkeypatch.setattr("netscope.modules.nmap_scan.subprocess.Popen", fake_popen)
    progress = []
    hosts = []
    scanner = NmapScanTest(None, MemoryCsv())
    result = scanner.run_streaming(
        ["app.example.test"], profile="vuln", progress_callback=progress.append,
        host_callback=hosts.append, timeout=5,
    )
    assert result.status == "success"
    assert result.metrics["target_count"] == 1
    assert result.metrics["vulnerability_findings"][0]["cve_ids"] == ["CVE-2024-12345"]
    assert progress[0]["percent"] == "42.5"
    assert hosts[0]["address"] == "192.0.2.10"
    assert "--stats-every" in observed["command"] and process.terminated is False


def test_streaming_parser_preserves_completed_evidence_when_cancelled(monkeypatch):
    process = FakeProcess([_XML.encode()])
    process.returncode = None
    monkeypatch.setattr("netscope.modules.nmap_scan.shutil.which", lambda _: "/usr/bin/nmap")
    monkeypatch.setattr("netscope.modules.nmap_scan.subprocess.Popen", lambda *a, **k: process)
    cancel = threading.Event()
    cancel.set()
    result = NmapScanTest(None, MemoryCsv()).run_streaming(
        "app.example.test", profile="vuln", cancel_event=cancel, timeout=5,
    )
    assert process.terminated is True
    assert result.status == "warning"
    assert "cancelled by operator" in result.summary


def test_dashboard_uses_alternate_screen_and_renders_streamed_events(monkeypatch):
    instances = []

    class FakeLive:
        def __init__(self, renderable, **kwargs):
            instances.append({"screen": kwargs.get("screen"), "auto_refresh": kwargs.get("auto_refresh"), "updates": 0})

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def update(self, renderable, refresh=False):
            instances[-1]["updates"] += 1

    class FakeScanner:
        def run_streaming(self, targets, **kwargs):
            kwargs["progress_callback"]({"task": "Connect Scan", "percent": "50"})
            time.sleep(0.05)
            kwargs["host_callback"]({
                "target": "app.example.test", "address": "192.0.2.10", "status": "up",
                "open_ports": [443], "services": [{"port": 443, "state": "open"}],
                "vulnerability_findings": [],
            })
            return NmapResult(
                test_name="Nmap Scan", target=", ".join(targets), status="success",
                timestamp=datetime.now(), duration=0.1, metrics={"host_count": 1}, summary="done",
            )

    monkeypatch.setattr(nmap_live, "Live", FakeLive)
    console = Console(file=StringIO(), force_terminal=True, width=110, height=32)
    session = nmap_live.run_live_nmap_dashboard(
        ["app.example.test"], FakeScanner(), console, profile="vuln", key_reader=lambda: None,
    )
    assert session.result.status == "success"
    assert instances[0]["screen"] is True
    assert instances[0]["auto_refresh"] is False
    assert instances[0]["updates"] >= 1
