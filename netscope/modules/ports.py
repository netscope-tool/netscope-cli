"""
Port scan test: pure-Python TCP port scanner (no nmap required).
"""

import socket
from datetime import datetime
from typing import Any, Dict, List, Optional

from netscope.modules.base import BaseTest, TestResult

# Common TCP ports: top 20 and top 100 presets
PORT_PRESET_TOP20: List[int] = [
    21, 22, 23, 25, 53, 80, 110, 111, 135, 139,
    143, 443, 445, 993, 995, 1723, 3306, 3389, 5900, 8080,
]

PORT_PRESET_TOP100: List[int] = [
    7, 9, 13, 21, 22, 23, 25, 26, 37, 53, 79, 80, 81, 88,
    106, 110, 111, 113, 119, 135, 139, 143, 144, 179, 199,
    389, 427, 443, 444, 445, 465, 513, 514, 515, 543, 544,
    548, 554, 587, 631, 646, 873, 990, 993, 995, 1025, 1026,
    1027, 1028, 1029, 1110, 1433, 1720, 1723, 1755, 1900,
    2000, 2049, 2121, 2717, 3000, 3128, 3306, 3389, 3986,
    4899, 5000, 5009, 5051, 5060, 5101, 5190, 5357, 5432,
    5631, 5666, 5800, 5900, 6000, 6646, 7070, 8000, 8008,
    8009, 8080, 8443, 8888, 9100, 9999, 32768, 49152, 49153,
    49154, 49155, 49156,
]


def scan_ports(
    host: str,
    ports: List[int],
    timeout: float = 2.0,
) -> tuple[List[int], List[int]]:
    """
    Try TCP connect to each port on host. Returns (open_ports, closed_ports).
    """
    open_ports: List[int] = []
    closed_ports: List[int] = []

    for port in ports:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                open_ports.append(port)
        except (socket.timeout, socket.error, OSError):
            closed_ports.append(port)

    return open_ports, closed_ports


class PortScanTest(BaseTest):
    """Port scan test using pure-Python TCP connect (no nmap)."""

    DEFAULT_TIMEOUT = 2.0
    DEFAULT_PRESET = "top20"

    def run(
        self,
        target: str,
        ports: Optional[List[int]] = None,
        timeout: float = DEFAULT_TIMEOUT,
        preset: str = DEFAULT_PRESET,
    ) -> TestResult:
        """Run port scan on target. If ports is None, use preset ('top20' or 'top100')."""
        start_time = datetime.now()

        if ports is None:
            ports = PORT_PRESET_TOP100 if preset == "top100" else PORT_PRESET_TOP20

        open_ports, closed_ports = scan_ports(target, ports, timeout=timeout)
        duration = (datetime.now() - start_time).total_seconds()

        total = len(ports)
        status = "success" if total > 0 else "warning"
        summary = (
            f"Found {len(open_ports)} open port(s) out of {total} scanned on {target}."
            + (f" Open: {', '.join(str(p) for p in sorted(open_ports))}" if open_ports else " None open.")
        )

        metrics: Dict[str, Any] = {
            "open_ports": sorted(open_ports),
            "closed_count": len(closed_ports),
            "total_ports": total,
            "open_count": len(open_ports),
        }

        test_result = TestResult(
            test_name="Port Scan",
            target=target,
            status=status,
            timestamp=start_time,
            duration=duration,
            metrics=metrics,
            summary=summary,
            raw_output=None,
            error=None,
        )

        self._log_to_csv(test_result)
        return test_result

    def parse_output(self, output: str) -> Dict[str, Any]:
        """Port scan does not parse CLI output; metrics are built in run()."""
        return {}

    def _log_to_csv(self, result: TestResult) -> None:
        """Log result to CSV (open_ports as comma-separated string, plus counts)."""
        open_ports = result.metrics.get("open_ports", [])
        open_str = ",".join(str(p) for p in open_ports) if open_ports else ""
        for metric_name, metric_value in result.metrics.items():
            if metric_name == "open_ports":
                self.csv_handler.write_result(
                    timestamp=result.timestamp,
                    test_name=result.test_name,
                    target=result.target,
                    metric="open_ports",
                    value=open_str,
                    status=result.status,
                    details=result.summary or "",
                )
            else:
                self.csv_handler.write_result(
                    timestamp=result.timestamp,
                    test_name=result.test_name,
                    target=result.target,
                    metric=metric_name,
                    value=metric_value,
                    status=result.status,
                    details=result.summary or "",
                )
