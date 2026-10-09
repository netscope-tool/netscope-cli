"""Offline unit tests for new network-exploration parsers and validation."""
import json
from pathlib import Path

import pytest

from netscope.cli.main import _recent_run_directories
from netscope.modules.mtr import MTRTest, parse_mtr_report
from netscope.modules.nmap_scan import NMAP_PROFILES, run_nmap_xml
from netscope.modules.website_audit import WebsiteAuditTest, normalize_website_target
from netscope.report.html_report import generate_html


def test_parse_mtr_wide_report():
    report = """HOST: workstation\n  1.|-- 192.0.2.1  0.0%  10  1.1  1.2  0.9  1.8  0.2\n  2.|-- 198.51.100.1  10.0%  10  8.0  9.5  7.1  12.0  1.4\n"""
    hops = parse_mtr_report(report)
    assert len(hops) == 2
    assert hops[0]["hop"] == 1
    assert hops[0]["host"] == "192.0.2.1"
    assert hops[0]["packet_loss_percent"] == 0.0
    assert hops[0]["sent"] == 10
    assert hops[0]["avg_ms"] == 1.2
    assert hops[1]["packet_loss_percent"] == 10.0


def test_parse_mtr_unknown_hop_keeps_loss_and_address():
    hops = parse_mtr_report("  3.|-- ???  100.0%  5  0.0  0.0  0.0  0.0  0.0\n")
    assert hops[0]["host"] == "???"
    assert hops[0]["packet_loss_percent"] == 100.0


def test_normalize_website_target_accepts_hostname_and_url():
    assert normalize_website_target("example.com") == ("example.com", "https://example.com/")
    host, url = normalize_website_target("https://example.com/status?q=1")
    assert host == "example.com"
    assert url == "https://example.com/status?q=1"


def test_explicit_https_port_is_preserved():
    host, url = normalize_website_target("https://example.com:8443/health")
    assert host == "example.com"
    assert url == "https://example.com:8443/health"


@pytest.mark.parametrize("target", [
    "", "example.com/path with space", "ftp://example.com",
    "https://user:pw@example.com", "https://example.com:invalid",
])
def test_normalize_website_target_rejects_ambiguous_or_unsafe_input(target):
    with pytest.raises(ValueError):
        normalize_website_target(target)


def test_html_report_uses_terminal_palette_and_escapes_untrusted_values(tmp_path: Path):
    (tmp_path / "metadata.json").write_text(json.dumps({
        "test_type": "Website <Audit>", "target": "example.com", "status": "warning",
        "timestamp": "2026-01-01T00:00:00Z", "system_info": {"hostname": "host & node"},
    }), encoding="utf-8")
    (tmp_path / "results.csv").write_text(
        'timestamp,test_name,target,metric,value,status,details\n'
        '2026-01-01,Website,example.com,findings,"[\"missing header <script>\"]",warning,summary\n',
        encoding="utf-8",
    )
    raw_dir = tmp_path / "raw_output"
    raw_dir.mkdir()
    (raw_dir / "mtr.txt").write_text("route output </pre><script>alert(1)</script>", encoding="utf-8")
    html = generate_html(tmp_path)
    assert "#d97757" in html
    assert "NETSCOPE / RUN REPORT" in html
    assert "https://cdn.jsdelivr.net" not in html
    assert "Website &lt;Audit&gt;" in html
    assert "host &amp; node" in html
    assert "Raw evidence · mtr.txt" in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_nmap_profile_arguments_replace_defaults_and_delimit_target(monkeypatch):
    observed = {}

    def fake_run(command, **kwargs):
        observed["command"] = command
        return object()

    monkeypatch.setattr("netscope.modules.nmap_scan.subprocess.run", fake_run)
    run_nmap_xml("-example.invalid", ports="443", extra_args=NMAP_PROFILES["connect"])
    command = observed["command"]
    assert "-sT" in command and "-F" in command
    assert "-sV" not in command
    assert command[-2:] == ["--", "-example.invalid"]


def test_website_audit_surfaces_findings_and_stage_updates(monkeypatch):
    class MemoryCsv:
        def __init__(self):
            self.rows = []

        def write_result(self, **row):
            self.rows.append(row)

    monkeypatch.setattr("netscope.modules.website_audit.inspect_certificate", lambda *a, **k: {
        "available": False, "verified": False, "verification_error": "expired certificate",
        "expired": True,
    })
    monkeypatch.setattr("netscope.modules.website_audit.inspect_http", lambda *a, **k: {
        "status_code": 200, "missing_security_headers": ["content-security-policy"],
        "security_headers": {}, "final_url": "https://example.com/",
    })
    monkeypatch.setattr("netscope.modules.website_audit.discover_ct_subdomains", lambda *a, **k: {
        "names": [], "status": "unavailable", "note": "offline",
    })
    stages = []
    csv = MemoryCsv()
    result = WebsiteAuditTest(None, csv).run(
        "example.com", progress_callback=stages.append,
    )
    assert result.status == "warning"
    assert len(result.metrics["findings"]) >= 3
    assert result.metrics["recommendations"]
    assert len(stages) == 3
    assert csv.rows


def test_mtr_missing_binary_returns_clear_failure(monkeypatch):
    class MemoryCsv:
        def write_result(self, **row):
            pass

    monkeypatch.setattr("netscope.modules.mtr.shutil.which", lambda _: None)
    result = MTRTest(None, MemoryCsv()).run("192.0.2.1", cycles=1)
    assert result.status == "failure"
    assert "mtr is not installed" in result.summary


def test_recent_run_picker_only_lists_result_directories(tmp_path: Path):
    older = tmp_path / "2026-10-08_120000_ping"
    newer = tmp_path / "2026-10-09_110000_mtr"
    for directory in (older, newer):
        directory.mkdir()
        (directory / "results.csv").write_text("metric,value\n", encoding="utf-8")
    (tmp_path / "logs").mkdir()
    assert _recent_run_directories(tmp_path) == [newer, older]
