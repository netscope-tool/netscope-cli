"""Nmap scanning with structured XML results and bounded streaming support."""
from __future__ import annotations

import json
import queue
import re
import shutil
import subprocess
import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

from netscope.modules.base import BaseTest, TestResult

NMAP_VULN_SCRIPT_EXPRESSION = "vuln and safe and not intrusive and not external and not dos and not exploit"
MAX_NMAP_BATCH_TARGETS = 32
MAX_VULN_TARGETS = 16
MAX_VULN_PORTS = 100
MAX_STREAM_XML_BYTES = 64 * 1024 * 1024
MAX_STREAM_STDERR_BYTES = 1024 * 1024

NMAP_PROFILES = {
    "connect": ["-sT", "-T3", "-F", "-n", "--stats-every", "1s"],
    "service": ["-sT", "-sV", "--version-light", "-T3", "-n", "--stats-every", "1s"],
    "udp": ["-sU", "--top-ports", "20", "-T2", "-n", "--stats-every", "1s"],
    "vuln": [
        "-sT", "-sV", "--version-light", "-T2", "-n", "--top-ports", "20",
        "--script", NMAP_VULN_SCRIPT_EXPRESSION,
        "--max-retries", "2", "--stats-every", "1s",
    ],
}
_CVE_PATTERN = re.compile(r"\bCVE-\d{4}-\d{4,}\b", re.IGNORECASE)
_TARGET_RANGE_PATTERN = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}-\d{1,3}$")


def normalize_targets(targets: Union[str, Sequence[str]]) -> List[str]:
    """Normalize one or more explicit targets and enforce a bounded batch size."""
    if isinstance(targets, str):
        normalized = [targets.strip()]
    else:
        normalized = [str(target).strip() for target in targets]
    if not normalized or any(not target for target in normalized):
        raise ValueError("Provide at least one non-empty Nmap target.")
    if len(normalized) > MAX_NMAP_BATCH_TARGETS:
        raise ValueError(f"Nmap batches are limited to {MAX_NMAP_BATCH_TARGETS} explicit targets.")
    if len(set(normalized)) != len(normalized):
        raise ValueError("Duplicate targets are not allowed in an Nmap batch.")
    return normalized


def _count_numeric_ports(ports: str) -> int:
    """Count a conservative numeric TCP port expression used by the vuln profile."""
    total = 0
    for item in ports.split(","):
        match = re.fullmatch(r"\s*(\d+)(?:\s*-\s*(\d+))?\s*", item)
        if not match:
            raise ValueError("Vulnerability scans accept numeric TCP ports only (for example: 22,80,443 or 1-100).")
        start = int(match.group(1))
        end = int(match.group(2) or start)
        if not 1 <= start <= end <= 65535:
            raise ValueError(f"Invalid Nmap port range: {item!r}.")
        total += end - start + 1
    return total


def validate_vulnerability_scope(targets: Union[str, Sequence[str]], ports: Optional[str] = None) -> List[str]:
    """Require a small explicit target set and keep the safe NSE scan port scope bounded."""
    normalized = normalize_targets(targets)
    if len(normalized) > MAX_VULN_TARGETS:
        raise ValueError(f"Vulnerability scans are limited to {MAX_VULN_TARGETS} explicit targets per batch.")
    for target in normalized:
        if (
            target.startswith(("-", "@"))
            or any(char in target for char in "/,*;\t\r\n")
            or _TARGET_RANGE_PATTERN.fullmatch(target)
        ):
            raise ValueError("Vulnerability scans require individual hosts; CIDR, ranges, lists, and target files are not accepted.")
    if ports is not None and _count_numeric_ports(ports) > MAX_VULN_PORTS:
        raise ValueError(f"Vulnerability scans are limited to {MAX_VULN_PORTS} selected TCP ports per target.")
    return normalized


def has_nmap() -> bool:
    """Return True if the `nmap` binary is available in PATH."""
    return shutil.which("nmap") is not None


def _with_port_scope(args: Sequence[str], ports: Optional[str]) -> List[str]:
    normalized = list(args)
    if not ports:
        return normalized
    result: List[str] = []
    index = 0
    while index < len(normalized):
        item = normalized[index]
        if item == "-F":
            index += 1
            continue
        if item in {"--top-ports", "--port-ratio"}:
            index += 2
            continue
        result.append(item)
        index += 1
    result.extend(["-p", ports])
    return result


def build_nmap_command(
    targets: Union[str, Sequence[str]],
    ports: Optional[str] = None,
    profile: str = "service",
    executable: str = "nmap",
) -> List[str]:
    """Build an argument-vector command; no shell parsing or target interpolation is used."""
    target_list = normalize_targets(targets)
    if profile not in NMAP_PROFILES:
        raise ValueError(f"Unknown Nmap profile {profile!r}; choose one of {', '.join(NMAP_PROFILES)}.")
    if profile == "vuln":
        target_list = validate_vulnerability_scope(target_list, ports)
    args = _with_port_scope(NMAP_PROFILES[profile], ports)
    return [executable, "-oX", "-", *args, "--", *target_list]


def run_nmap_xml(
    target: Union[str, Sequence[str]],
    ports: Optional[str] = None,
    extra_args: Optional[List[str]] = None,
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    """Run Nmap once for one or more targets and capture its machine-readable XML."""
    if extra_args is None:
        extra_args = ["-sT", "-sV"]
    command = ["nmap", "-oX", "-", *_with_port_scope(extra_args, ports), "--", *normalize_targets(target)]
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout)


def _script_result(script: ET.Element, port: Optional[int] = None, protocol: Optional[str] = None) -> Dict[str, Any]:
    output = script.attrib.get("output", "")
    nested_text = " ".join((node.text or "").strip() for node in script.iter() if node.text)
    evidence = "\n".join(part for part in (output, nested_text) if part)
    upper = evidence.upper()
    if "NOT VULNERABLE" in upper:
        state = "not_vulnerable"
    elif re.search(r"\bVULNERABLE\b", upper):
        state = "vulnerable"
    else:
        state = "reported"
    return {
        "id": script.attrib.get("id", "unknown"),
        "output": output or nested_text,
        "port": port,
        "protocol": protocol,
        "state": state,
        "cve_ids": sorted({value.upper() for value in _CVE_PATTERN.findall(evidence)}),
        "severity": "not rated by Nmap output",
    }


def parse_nmap_host_element(host: ET.Element) -> Dict[str, Any]:
    """Extract one completed host from a full or incrementally parsed Nmap XML tree."""
    status_element = host.find("status")
    status = status_element.attrib.get("state", "unknown") if status_element is not None else "unknown"
    addresses = [
        {"address": element.attrib.get("addr", ""), "type": element.attrib.get("addrtype", "unknown")}
        for element in host.findall("address")
    ]
    primary_address = next((item["address"] for item in addresses if item["type"] in {"ipv4", "ipv6"}), "")
    hostnames = [element.attrib.get("name", "") for element in host.findall("./hostnames/hostname") if element.attrib.get("name")]
    services: List[Dict[str, Any]] = []
    script_results: List[Dict[str, Any]] = []
    open_ports: List[int] = []

    for port_element in host.findall("./ports/port"):
        try:
            port_number = int(port_element.attrib.get("portid", "0"))
        except ValueError:
            continue
        protocol = port_element.attrib.get("protocol", "")
        state_element = port_element.find("state")
        port_state = state_element.attrib.get("state", "unknown") if state_element is not None else "unknown"
        if port_state == "open":
            open_ports.append(port_number)
        service_element = port_element.find("service")
        service = {
            "port": port_number,
            "protocol": protocol,
            "state": port_state,
            "service": service_element.attrib.get("name", "") if service_element is not None else "",
            "product": service_element.attrib.get("product", "") if service_element is not None else "",
            "version": service_element.attrib.get("version", "") if service_element is not None else "",
        }
        services.append(service)
        for script in port_element.findall("script"):
            script_results.append(_script_result(script, port_number, protocol))

    for script in host.findall("./hostscript/script"):
        script_results.append(_script_result(script))

    display_name = hostnames[0] if hostnames else primary_address
    for script_result in script_results:
        script_result["target"] = display_name or "unknown"
        script_result["address"] = primary_address
    vulnerability_findings = [
        item for item in script_results
        if item["state"] != "not_vulnerable"
        and (item["output"] or item["cve_ids"] or item["state"] == "vulnerable")
    ]
    return {
        "target": display_name or "unknown",
        "address": primary_address,
        "addresses": addresses,
        "hostnames": hostnames,
        "status": status,
        "open_ports": sorted(open_ports),
        "services": services,
        "script_results": script_results,
        "vulnerability_findings": vulnerability_findings,
    }


def _empty_metrics() -> Dict[str, Any]:
    return {
        "hosts_up": 0,
        "hosts_down": 0,
        "open_ports": [],
        "closed_ports": [],
        "filtered_ports": [],
        "services": [],
        "hosts": [],
        "script_results": [],
        "vulnerability_findings": [],
    }


def parse_nmap_xml(xml_text: str) -> Dict[str, Any]:
    """Parse complete Nmap XML into aggregate counts, per-host rows, and NSE evidence."""
    metrics = _empty_metrics()
    if not (xml_text or "").strip():
        return metrics
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return metrics

    runstats = root.find("runstats/hosts")
    if runstats is not None:
        try:
            metrics["hosts_up"] = int(runstats.attrib.get("up", "0"))
            metrics["hosts_down"] = int(runstats.attrib.get("down", "0"))
        except ValueError:
            pass

    hosts = [parse_nmap_host_element(host) for host in root.findall("host")]
    metrics["hosts"] = hosts
    metrics["host_count"] = len(hosts)
    if runstats is None:
        metrics["hosts_up"] = sum(item["status"] == "up" for item in hosts)
        metrics["hosts_down"] = sum(item["status"] == "down" for item in hosts)

    open_ports: List[int] = []
    closed_ports: List[int] = []
    filtered_ports: List[int] = []
    for host in root.findall("host"):
        for port_element in host.findall("./ports/port"):
            try:
                port_number = int(port_element.attrib.get("portid", "0"))
            except ValueError:
                continue
            state_element = port_element.find("state")
            state = state_element.attrib.get("state", "") if state_element is not None else ""
            if state == "open":
                open_ports.append(port_number)
            elif state == "closed":
                closed_ports.append(port_number)
            elif state == "filtered":
                filtered_ports.append(port_number)

    metrics["open_ports"] = sorted(open_ports)
    metrics["closed_ports"] = sorted(closed_ports)
    metrics["filtered_ports"] = sorted(filtered_ports)
    metrics["open_count"] = len(open_ports)
    metrics["closed_count"] = len(closed_ports)
    metrics["filtered_count"] = len(filtered_ports)
    metrics["services"] = [service for host in hosts for service in host["services"]]
    metrics["script_results"] = [script for host in hosts for script in host["script_results"]]
    metrics["vulnerability_findings"] = [
        finding for host in hosts for finding in host["vulnerability_findings"]
    ]
    return metrics


def run_nmap_os_scan(ip: str, timeout: int = 30) -> Optional[str]:
    """Run nmap OS detection (-O -Pn) on one host and return the best OS guess."""
    if not has_nmap():
        return None
    try:
        proc = subprocess.run(
            ["nmap", "-O", "-Pn", "-n", "-oX", "-", "--", ip],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if proc.returncode != 0:
            return None
        return parse_nmap_os_from_xml(proc.stdout or "")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def parse_nmap_os_from_xml(xml_text: str) -> Optional[str]:
    """Parse Nmap XML for the first OS match."""
    if not (xml_text or "").strip():
        return None
    try:
        root = ET.fromstring(xml_text)
        for host in root.findall("host"):
            os_element = host.find("os")
            if os_element is None:
                continue
            for osmatch in os_element.findall("osmatch"):
                name = osmatch.attrib.get("name")
                if name:
                    return name
        return None
    except ET.ParseError:
        return None


def _read_process_stream(stream, name: str, events: queue.Queue) -> None:
    """Pump a pipe in chunks so neither stdout nor stderr can block Nmap."""
    try:
        while True:
            reader = getattr(stream, "read1", stream.read)
            chunk = reader(8192)
            if not chunk:
                break
            events.put((name, chunk))
    finally:
        events.put((name, None))


def _fallback_stream_metrics(hosts: List[Dict[str, Any]]) -> Dict[str, Any]:
    metrics = _empty_metrics()
    metrics["hosts"] = hosts
    metrics["host_count"] = len(hosts)
    metrics["hosts_up"] = sum(host["status"] == "up" for host in hosts)
    metrics["hosts_down"] = sum(host["status"] == "down" for host in hosts)
    metrics["open_ports"] = sorted(port for host in hosts for port in host["open_ports"])
    metrics["open_count"] = len(metrics["open_ports"])
    metrics["services"] = [service for host in hosts for service in host["services"]]
    metrics["closed_ports"] = sorted(
        service["port"] for service in metrics["services"] if service.get("state") == "closed"
    )
    metrics["filtered_ports"] = sorted(
        service["port"] for service in metrics["services"] if service.get("state") == "filtered"
    )
    metrics["closed_count"] = len(metrics["closed_ports"])
    metrics["filtered_count"] = len(metrics["filtered_ports"])
    metrics["script_results"] = [script for host in hosts for script in host["script_results"]]
    metrics["vulnerability_findings"] = [finding for host in hosts for finding in host["vulnerability_findings"]]
    return metrics


class NmapScanTest(BaseTest):
    """Nmap scanner supporting one-process multi-target batches and live XML progress."""

    def _failure(self, target_label: str, profile: str, started: datetime, summary: str, error: Optional[str] = None) -> TestResult:
        result = TestResult(
            test_name="Nmap Vulnerability Scan" if profile == "vuln" else "Nmap Scan",
            target=target_label,
            status="failure",
            timestamp=started,
            duration=(datetime.now() - started).total_seconds(),
            metrics={"profile": profile},
            summary=summary,
            raw_output=None,
            error=error or summary,
        )
        self._log_to_csv(result)
        return result

    def _prepare(
        self,
        targets: Union[str, Sequence[str]],
        ports: Optional[str],
        profile: str,
    ) -> tuple[List[str], List[str]]:
        target_list = normalize_targets(targets)
        if profile not in NMAP_PROFILES:
            raise ValueError(f"Unknown Nmap profile {profile!r}; choose one of {', '.join(NMAP_PROFILES)}.")
        if profile == "vuln":
            target_list = validate_vulnerability_scope(target_list, ports)
        return target_list, build_nmap_command(target_list, ports, profile)[1:]

    def run(
        self,
        target: Union[str, Sequence[str]],
        ports: Optional[str] = None,
        extra_args: Optional[List[str]] = None,
        timeout: int = 120,
        profile: str = "service",
    ) -> TestResult:
        started = datetime.now()
        target_list = normalize_targets(target)
        if profile not in NMAP_PROFILES:
            raise ValueError(f"Unknown Nmap profile {profile!r}; choose one of {', '.join(NMAP_PROFILES)}.")
        if profile == "vuln":
            if extra_args is not None:
                raise ValueError("Custom Nmap arguments are not allowed with the bounded vulnerability profile.")
            if timeout > 900:
                raise ValueError("Vulnerability-scan timeout is capped at 900 seconds.")
            target_list = validate_vulnerability_scope(target_list, ports)
        target_label = ", ".join(target_list)
        test_name = "Nmap Vulnerability Scan" if profile == "vuln" else "Nmap Scan"
        if not has_nmap():
            return self._failure(
                target_label, profile, started,
                "nmap is not installed or not found in PATH. Install Nmap to use this scan.",
            )

        args = extra_args if extra_args is not None else NMAP_PROFILES[profile]
        try:
            proc = run_nmap_xml(target_list, ports=ports, extra_args=list(args), timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            return self._failure(
                target_label, profile, started, f"nmap scan timed out after {timeout}s",
                str(getattr(exc, "stderr", "") or exc),
            )
        except FileNotFoundError as exc:
            return self._failure(target_label, profile, started, "Could not start nmap.", str(exc))

        duration = (datetime.now() - started).total_seconds()
        xml_output = proc.stdout or ""
        metrics = parse_nmap_xml(xml_output)
        metrics.update({"profile": profile, "targets": target_list, "target_count": len(target_list)})
        successful = proc.returncode == 0
        if successful:
            status = "success"
            if profile == "vuln":
                count = len(metrics.get("vulnerability_findings", []))
                summary = (
                    f"Nmap completed the safe vulnerability-script scan across {len(target_list)} target(s); "
                    f"{count} script-evidence item(s) reported. Findings require review; no exploit was run."
                )
            else:
                summary = (
                    f"Nmap found {metrics.get('open_count', 0)} open port(s) across "
                    f"{len(target_list)} target(s)."
                )
        else:
            status = "failure"
            summary = f"nmap failed with exit code {proc.returncode}"
        result = TestResult(
            test_name=test_name,
            target=target_label,
            status=status,
            timestamp=started,
            duration=duration,
            metrics=metrics,
            summary=summary,
            raw_output=xml_output or proc.stderr,
            error=None if successful else (proc.stderr or summary),
        )
        self._log_to_csv(result)
        return result

    def run_streaming(
        self,
        target: Union[str, Sequence[str]],
        ports: Optional[str] = None,
        timeout: int = 120,
        profile: str = "service",
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        host_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> TestResult:
        """Stream taskprogress and completed hosts from Nmap XML while keeping stdout/stderr drained."""
        started = datetime.now()
        target_list = normalize_targets(target)
        if profile not in NMAP_PROFILES:
            raise ValueError(f"Unknown Nmap profile {profile!r}; choose one of {', '.join(NMAP_PROFILES)}.")
        if profile == "vuln":
            if timeout > 900:
                raise ValueError("Vulnerability-scan timeout is capped at 900 seconds.")
            target_list = validate_vulnerability_scope(target_list, ports)
        target_label = ", ".join(target_list)
        test_name = "Nmap Vulnerability Scan" if profile == "vuln" else "Nmap Scan"
        if not has_nmap():
            return self._failure(target_label, profile, started, "nmap is not installed or not found in PATH. Install Nmap to use this scan.")

        command = build_nmap_command(target_list, ports, profile)
        process: Optional[subprocess.Popen] = None
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except OSError as exc:
            return self._failure(target_label, profile, started, "Could not start nmap.", str(exc))

        assert process.stdout is not None and process.stderr is not None
        events: queue.Queue = queue.Queue()
        readers = [
            threading.Thread(target=_read_process_stream, args=(process.stdout, "stdout", events), daemon=True),
            threading.Thread(target=_read_process_stream, args=(process.stderr, "stderr", events), daemon=True),
        ]
        for reader in readers:
            reader.start()

        parser = ET.XMLPullParser(events=("end",))
        parse_error: Optional[str] = None
        xml_parts: List[str] = []
        xml_bytes = 0
        stderr_parts: List[str] = []
        stderr_bytes = 0
        streamed_hosts: List[Dict[str, Any]] = []
        finished_streams = set()
        cancelled = False
        timed_out = False
        cancellation_requested = False
        termination_started: Optional[float] = None
        queue_timeout = max(1, int(timeout))
        started_monotonic = time.monotonic()

        while len(finished_streams) < 2 or process.poll() is None:
            if cancel_event is not None and cancel_event.is_set() and not cancellation_requested:
                cancellation_requested = True
                cancelled = True
                termination_started = time.monotonic()
                try:
                    process.terminate()
                except OSError:
                    pass
            if time.monotonic() - started_monotonic >= queue_timeout and process.poll() is None and not cancellation_requested:
                cancellation_requested = True
                timed_out = True
                termination_started = time.monotonic()
                try:
                    process.terminate()
                except OSError:
                    pass
            if cancellation_requested and process.poll() is None and termination_started is not None and time.monotonic() - termination_started > 2:
                try:
                    process.kill()
                except OSError:
                    pass
            try:
                name, chunk = events.get(timeout=0.05)
            except queue.Empty:
                continue
            if chunk is None:
                finished_streams.add(name)
                continue
            if name == "stderr":
                chunk_text = chunk.decode("utf-8", errors="replace")
                encoded_size = len(chunk)
                if stderr_bytes < MAX_STREAM_STDERR_BYTES:
                    remaining = MAX_STREAM_STDERR_BYTES - stderr_bytes
                    stderr_parts.append(chunk_text[:remaining])
                    stderr_bytes += min(encoded_size, remaining)
                continue

            chunk_text = chunk.decode("utf-8", errors="replace")
            if xml_bytes < MAX_STREAM_XML_BYTES:
                remaining = MAX_STREAM_XML_BYTES - xml_bytes
                xml_parts.append(chunk_text[:remaining])
                xml_bytes += min(len(chunk), remaining)
            if parse_error is not None:
                continue
            try:
                parser.feed(chunk_text)
                for _event, element in parser.read_events():
                    if element.tag == "taskprogress":
                        if progress_callback is not None:
                            progress_callback(dict(element.attrib))
                        element.clear()
                    elif element.tag == "host":
                        parsed_host = parse_nmap_host_element(element)
                        streamed_hosts.append(parsed_host)
                        if host_callback is not None:
                            host_callback(parsed_host)
                        element.clear()
            except ET.ParseError as exc:
                parse_error = str(exc)

        try:
            returncode = process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            returncode = process.wait()
        for reader in readers:
            reader.join(timeout=1)
        try:
            parser.close()
        except ET.ParseError as exc:
            if not cancelled and not timed_out:
                parse_error = parse_error or str(exc)

        xml_output = "".join(xml_parts)
        stderr_output = "".join(stderr_parts)
        metrics = parse_nmap_xml(xml_output)
        if (not metrics.get("hosts") or xml_bytes > MAX_STREAM_XML_BYTES) and streamed_hosts:
            metrics = _fallback_stream_metrics(streamed_hosts)
        metrics.update({"profile": profile, "targets": target_list, "target_count": len(target_list)})
        if xml_bytes > MAX_STREAM_XML_BYTES:
            metrics["raw_xml_truncated"] = True
        duration = (datetime.now() - started).total_seconds()

        if cancelled:
            status = "warning"
            summary = f"Nmap scan cancelled by operator after {len(streamed_hosts)} host result(s); partial evidence was kept."
            error = "Cancelled by operator."
        elif timed_out:
            status = "failure"
            summary = f"nmap scan timed out after {timeout}s"
            error = stderr_output or summary
        elif returncode != 0:
            status = "failure"
            summary = f"nmap failed with exit code {returncode}"
            error = stderr_output or summary
        elif parse_error:
            status = "failure"
            summary = "Nmap completed but its XML output could not be parsed completely."
            error = parse_error
        else:
            status = "success"
            error = stderr_output or None
            if profile == "vuln":
                finding_count = len(metrics.get("vulnerability_findings", []))
                summary = (
                    f"Nmap completed the safe vulnerability-script scan across {len(target_list)} target(s); "
                    f"{finding_count} script-evidence item(s) reported. Findings require review; no exploit was run."
                )
            else:
                summary = (
                    f"Nmap found {metrics.get('open_count', 0)} open port(s) across "
                    f"{len(target_list)} target(s)."
                )
        result = TestResult(
            test_name=test_name,
            target=target_label,
            status=status,
            timestamp=started,
            duration=duration,
            metrics=metrics,
            summary=summary,
            raw_output=xml_output or stderr_output,
            error=error,
        )
        self._log_to_csv(result)
        return result

    def parse_output(self, output: str) -> Dict[str, Any]:
        """Nmap uses XML parsing via :func:`parse_nmap_xml`."""
        return parse_nmap_xml(output)

    def _log_to_csv(self, result: TestResult) -> None:
        """Persist concise counts and structured evidence for report generation."""
        metrics = result.metrics or {}
        for key in (
            "open_count", "closed_count", "filtered_count", "hosts_up", "hosts_down",
            "profile", "services", "closed_ports", "filtered_ports", "hosts",
            "script_results", "vulnerability_findings", "targets", "target_count",
        ):
            if key in metrics:
                value = metrics[key]
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, sort_keys=True)
                self.csv_handler.write_result(
                    timestamp=result.timestamp,
                    test_name=result.test_name,
                    target=result.target,
                    metric=key,
                    value=value,
                    status=result.status,
                    details=result.summary or "",
                )
        open_ports = metrics.get("open_ports") or []
        if open_ports:
            self.csv_handler.write_result(
                timestamp=result.timestamp,
                test_name=result.test_name,
                target=result.target,
                metric="open_ports",
                value=",".join(str(port) for port in open_ports),
                status=result.status,
                details=result.summary or "",
            )
        for host in metrics.get("hosts", []):
            host_target = host.get("target") or host.get("address") or result.target
            self.csv_handler.write_result(
                timestamp=result.timestamp,
                test_name=result.test_name,
                target=host_target,
                metric="host_summary",
                value=json.dumps(host, sort_keys=True),
                status=host.get("status", result.status),
                details=result.summary or "",
            )
            for finding in host.get("vulnerability_findings", []):
                self.csv_handler.write_result(
                    timestamp=result.timestamp,
                    test_name=result.test_name,
                    target=host_target,
                    metric="nse_script_evidence",
                    value=json.dumps(finding, sort_keys=True),
                    status=finding.get("state", result.status),
                    details=str(finding.get("id", "NSE script")),
                )
