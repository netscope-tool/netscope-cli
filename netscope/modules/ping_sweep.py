"""
Ping sweep: discover alive hosts in a CIDR range (e.g., 192.168.1.0/24).
"""

import ipaddress
import platform
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List

from netscope.modules.base import BaseTest, TestResult


def ping_host(host: str, timeout: float = 1.0) -> tuple[str, bool]:
    """
    Ping a single host and return (host, alive).
    
    Args:
        host: IP address to ping
        timeout: Timeout in seconds
        
    Returns:
        Tuple of (host_ip, is_alive)
    """
    os_type = platform.system()
    if os_type == "Windows":
        command = ["ping", "-n", "1", "-w", str(int(timeout * 1000)), host]
    else:
        command = ["ping", "-c", "1", "-W", str(int(timeout)), host]
    
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            timeout=timeout + 1.0,
        )
        return (host, result.returncode == 0)
    except subprocess.TimeoutExpired:
        return (host, False)
    except Exception:
        return (host, False)


def sweep_cidr(cidr: str, max_workers: int = 50, timeout: float = 1.0) -> List[str]:
    """
    Ping sweep a CIDR range and return list of alive hosts.
    
    Args:
        cidr: CIDR notation (e.g., "192.168.1.0/24")
        max_workers: Maximum concurrent ping threads
        timeout: Timeout per ping in seconds
        
    Returns:
        List of alive IP addresses
    """
    try:
        network = ipaddress.ip_network(cidr, strict=False)
    except ValueError:
        return []
    
    # Limit to /24 or smaller (max 256 hosts)
    if network.num_addresses > 256:
        return []
    
    alive_hosts: List[str] = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(ping_host, str(ip), timeout): str(ip) for ip in network.hosts()}
        
        for future in as_completed(futures):
            host, is_alive = future.result()
            if is_alive:
                alive_hosts.append(host)
    
    return sorted(alive_hosts, key=lambda x: ipaddress.IPv4Address(x))


class PingSweepTest(BaseTest):
    """Ping sweep test to discover alive hosts in a CIDR range."""
    
    def run(
        self,
        target: str,
        max_workers: int = 50,
        timeout: float = 1.0,
    ) -> TestResult:
        """
        Run ping sweep on a CIDR range.
        
        Args:
            target: CIDR notation (e.g., "192.168.1.0/24")
            max_workers: Maximum concurrent ping threads
            timeout: Timeout per ping in seconds
        """
        start_time = datetime.now()
        
        # Validate CIDR
        try:
            network = ipaddress.ip_network(target, strict=False)
            if network.num_addresses > 256:
                summary = f"CIDR range too large (max /24, got {network.num_addresses} addresses)"
                return TestResult(
                    test_name="Ping Sweep",
                    target=target,
                    status="failure",
                    timestamp=start_time,
                    duration=0.0,
                    metrics={},
                    summary=summary,
                    raw_output=None,
                    error=summary,
                )
        except ValueError as e:
            summary = f"Invalid CIDR notation: {target}"
            return TestResult(
                test_name="Ping Sweep",
                target=target,
                status="failure",
                timestamp=start_time,
                duration=0.0,
                metrics={},
                summary=summary,
                raw_output=None,
                error=str(e),
            )
        
        # Run sweep
        alive_hosts = sweep_cidr(target, max_workers=max_workers, timeout=timeout)
        duration = (datetime.now() - start_time).total_seconds()
        
        status = "success" if len(alive_hosts) > 0 else "warning"
        summary = f"Found {len(alive_hosts)} alive host(s) in {target}"
        
        metrics: Dict[str, Any] = {
            "alive_count": len(alive_hosts),
            "alive_hosts": alive_hosts,
            "total_addresses": network.num_addresses - 2,  # Exclude network and broadcast
        }
        
        test_result = TestResult(
            test_name="Ping Sweep",
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
        """Ping sweep doesn't parse CLI output."""
        return {}
    
    def _log_to_csv(self, result: TestResult) -> None:
        """Log each alive host as a CSV row."""
        alive_hosts = result.metrics.get("alive_hosts", [])
        for host in alive_hosts:
            self.csv_handler.write_result(
                timestamp=result.timestamp,
                test_name=result.test_name,
                target=host,
                metric="alive",
                value="true",
                status=result.status,
                details=result.summary or "",
            )
