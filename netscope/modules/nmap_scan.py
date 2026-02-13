"""
Nmap-based port and service scanner (optional dependency).
"""

from __future__ import annotations

import shutil
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, Dict, List, Optional

from netscope.modules.base import BaseTest, TestResult


def has_nmap() -> bool:
    """Return True if the `nmap` binary is available in PATH."""
    return shutil.which("nmap") is not None


def run_nmap_xml(
    target: str,
    ports: Optional[str] = None,
    extra_args: Optional[List[str]] = None,
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    """
    Run nmap with XML output (`-oX -`) and return the completed process.

    Args:
        target: Target host or CIDR.
        ports: Optional ports string for `-p` (e.g. "22,80,443" or "1-1024").
        extra_args: Additional nmap arguments (e.g. ["-sV"]).
        timeout: Timeout in seconds.
    """
    if extra_args is None:
        extra_args = ["-sT", "-sV"]

    cmd: List[str] = ["nmap", "-oX", "-"]
    cmd.extend(extra_args)
    if ports:
        cmd.extend(["-p", ports])
    cmd.append(target)

    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def parse_nmap_xml(xml_text: str) -> Dict[str, Any]:
    """
    Parse nmap XML output into a metrics dict.

    Extracts:
      - hosts_up / hosts_down
      - open_ports / closed_ports / filtered_ports lists (port numbers)
      - per-port service name and product (when available)
    """
    metrics: Dict[str, Any] = {
        "hosts_up": 0,
        "hosts_down": 0,
        "open_ports": [],
        "closed_ports": [],
        "filtered_ports": [],
        "services": [],
    }

    if not xml_text.strip():
        return metrics

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        # Keep metrics mostly empty; caller can inspect raw_output
        return metrics

    # Hosts up / down from runstats
    for runstats in root.findall("runstats"):
        finished = runstats.find("hosts")
        if finished is not None:
            try:
                metrics["hosts_up"] = int(finished.attrib.get("up", "0"))
                metrics["hosts_down"] = int(finished.attrib.get("down", "0"))
            except ValueError:
                pass

    open_ports: List[int] = []
    closed_ports: List[int] = []
    filtered_ports: List[int] = []
    services: List[Dict[str, Any]] = []

    # Iterate over hosts and their ports
    for host in root.findall("host"):
        for ports_el in host.findall("ports"):
            for port_el in ports_el.findall("port"):
                try:
                    port_num = int(port_el.attrib.get("portid", "0"))
                except ValueError:
                    continue
                state_el = port_el.find("state")
                state = state_el.attrib.get("state", "") if state_el is not None else ""
                service_el = port_el.find("service")
                svc_name = service_el.attrib.get("name", "") if service_el is not None else ""
                product = service_el.attrib.get("product", "") if service_el is not None else ""
                version = service_el.attrib.get("version", "") if service_el is not None else ""

                entry = {
                    "port": port_num,
                    "state": state,
                    "service": svc_name,
                    "product": product,
                    "version": version,
                }
                services.append(entry)

                if state == "open":
                    open_ports.append(port_num)
                elif state == "closed":
                    closed_ports.append(port_num)
                elif state == "filtered":
                    filtered_ports.append(port_num)

    metrics["open_ports"] = sorted(open_ports)
    metrics["closed_ports"] = sorted(closed_ports)
    metrics["filtered_ports"] = sorted(filtered_ports)
    metrics["open_count"] = len(open_ports)
    metrics["closed_count"] = len(closed_ports)
    metrics["filtered_count"] = len(filtered_ports)
    metrics["services"] = services

    return metrics


def run_nmap_os_scan(ip: str, timeout: int = 30) -> Optional[str]:
    """
    Run nmap OS detection (-O -Pn) on a single host and return the best OS guess.
    Returns None if nmap is unavailable, scan fails, or no OS match.
    """
    if not has_nmap():
        return None
    try:
        proc = subprocess.run(
            ["nmap", "-O", "-Pn", "-n", ip, "-oX", "-"],
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
    """
    Parse nmap XML for host/os/osmatch and return the best OS name (first match).
    """
    if not (xml_text or "").strip():
        return None
    try:
        root = ET.fromstring(xml_text)
        for host in root.findall("host"):
            os_el = host.find("os")
            if os_el is None:
                continue
            for osmatch in os_el.findall("osmatch"):
                name = osmatch.attrib.get("name")
                if name:
                    return name
        return None
    except ET.ParseError:
        return None


class NmapScanTest(BaseTest):
    """
    Nmap-based port / service scanner.

    Optional dependency: if `nmap` is not installed, the test returns a
    failure result with a helpful message.
    """

    def run(
        self,
        target: str,
        ports: Optional[str] = None,
        extra_args: Optional[List[str]] = None,
        timeout: int = 120,
    ) -> TestResult:
        start_time = datetime.now()

        if not has_nmap():
            summary = (
                "nmap is not installed or not found in PATH. "
                "Install nmap to use the Nmap Scan test."
            )
            return TestResult(
                test_name="Nmap Scan",
                target=target,
                status="failure",
                timestamp=start_time,
                duration=0.0,
                metrics={},
                summary=summary,
                raw_output=None,
                error=summary,
            )

        try:
            proc = run_nmap_xml(target, ports=ports, extra_args=extra_args, timeout=timeout)
        except subprocess.TimeoutExpired as e:
            duration = (datetime.now() - start_time).total_seconds()
            summary = f"nmap scan timed out after {timeout}s"
            result = TestResult(
                test_name="Nmap Scan",
                target=target,
                status="failure",
                timestamp=start_time,
                duration=duration,
                metrics={},
                summary=summary,
                raw_output=str(getattr(e, 'output', "")),
                error=str(e),
            )
            self._log_to_csv(result)
            return result

        duration = (datetime.now() - start_time).total_seconds()
        success = proc.returncode == 0
        metrics = parse_nmap_xml(proc.stdout) if success else {}

        if success:
            status = "success"
            open_count = metrics.get("open_count", 0)
            summary = f"Nmap found {open_count} open port(s) on {target}"
        else:
            status = "failure"
            summary = f"nmap failed with exit code {proc.returncode}"

        result = TestResult(
            test_name="Nmap Scan",
            target=target,
            status=status,
            timestamp=start_time,
            duration=duration,
            metrics=metrics,
            summary=summary,
            raw_output=proc.stdout or proc.stderr,
            error=None if success else proc.stderr,
        )

        self._log_to_csv(result)
        return result

    def parse_output(self, output: str) -> Dict[str, Any]:
        """
        Not used; nmap uses XML parsing via `parse_nmap_xml`.
        """
        return {}

    def _log_to_csv(self, result: TestResult) -> None:
        """
        Log aggregate metrics (counts and open ports) to CSV.
        """
        metrics = result.metrics or {}
        # Write counts
        for key in ("open_count", "closed_count", "filtered_count", "hosts_up", "hosts_down"):
            if key in metrics:
                self.csv_handler.write_result(
                    timestamp=result.timestamp,
                    test_name=result.test_name,
                    target=result.target,
                    metric=key,
                    value=metrics[key],
                    status=result.status,
                    details=result.summary or "",
                )
        # Open ports as a comma-separated list
        open_ports = metrics.get("open_ports") or []
        if open_ports:
            self.csv_handler.write_result(
                timestamp=result.timestamp,
                test_name=result.test_name,
                target=result.target,
                metric="open_ports",
                value=",".join(str(p) for p in open_ports),
                status=result.status,
                details=result.summary or "",
            )

