"""
DNS resolution tests.
"""

import re
import platform
from datetime import datetime
from typing import Dict, Any

from netscope.modules.base import BaseTest, TestResult


class DNSTest(BaseTest):
    """DNS lookup test."""
    
    def run(self, target: str) -> TestResult:
        """Run DNS lookup test."""
        start_time = datetime.now()
        
        # Build DNS lookup command based on OS
        os_type = platform.system()
        if os_type == "Windows":
            command = ["nslookup", target]
        else:
            command = ["dig", "+short", target]
        
        # Execute command
        result = self.executor.run_command(command)
        
        # Parse output
        metrics = self.parse_output(result.stdout, os_type) if result.success else {}
        
        # Determine status
        if result.success and metrics.get('resolved', False):
            status = "success"
            ip_addresses = metrics.get('ip_addresses', [])
            ipv4_count = metrics.get('ipv4_count', 0)
            ipv6_count = metrics.get('ipv6_count', 0)
            addr_types = []
            if ipv4_count > 0:
                addr_types.append(f"{ipv4_count} IPv4")
            if ipv6_count > 0:
                addr_types.append(f"{ipv6_count} IPv6")
            type_str = " + ".join(addr_types) if addr_types else ""
            summary = f"Resolved {target} to {len(ip_addresses)} address(es) ({type_str}): {', '.join(ip_addresses[:3])}"
        elif result.success:
            status = "warning"
            summary = f"Could not resolve {target}"
        else:
            status = "failure"
            summary = f"DNS lookup failed: {result.stderr}"
        
        test_result = TestResult(
            test_name="DNS Lookup",
            target=target,
            status=status,
            timestamp=start_time,
            duration=result.duration,
            metrics=metrics,
            summary=summary,
            raw_output=result.stdout,
            error=result.stderr if not result.success else None,
        )
        
        # Log to CSV
        self._log_to_csv(test_result)
        
        return test_result
    
    def parse_output(self, output: str, os_type: str) -> Dict[str, Any]:
        """Parse DNS lookup output. Detects both IPv4 (A) and IPv6 (AAAA) records."""
        metrics = {}
        ip_addresses = []
        ipv4_addresses = []
        ipv6_addresses = []
        
        # IPv4 regex: 4 groups of 1-3 digits
        ipv4_pattern = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
        # IPv6 regex: simplified - matches common formats (e.g., 2001:db8::1, ::1)
        ipv6_pattern = re.compile(r'\b(?:[0-9a-fA-F]{1,4}:){1,7}[0-9a-fA-F]{1,4}\b|::1|\b::\b')
        
        if os_type == "Windows":
            # Parse nslookup output
            # Look for lines like "Address:  192.168.1.1" or "AAAA Record: 2001:db8::1"
            for line in output.split('\n'):
                if 'Address' in line and ':' in line:
                    parts = line.split(':')
                    if len(parts) > 1:
                        ip = parts[1].strip()
                        # Check IPv4
                        if ipv4_pattern.match(ip):
                            ip_addresses.append(ip)
                            ipv4_addresses.append(ip)
                        # Check IPv6
                        elif ipv6_pattern.search(ip):
                            ip_addresses.append(ip)
                            ipv6_addresses.append(ip)
        else:
            # Parse dig output - check for A and AAAA records
            # For A records: dig +short returns IPv4
            # For AAAA records: dig +short AAAA returns IPv6
            # We'll also check if the output contains IPv6 patterns
            for line in output.strip().split('\n'):
                line = line.strip()
                if not line:
                    continue
                # Match IPv4 addresses
                if ipv4_pattern.match(line):
                    ip_addresses.append(line)
                    ipv4_addresses.append(line)
                # Match IPv6 addresses
                elif ipv6_pattern.search(line):
                    ip_addresses.append(line)
                    ipv6_addresses.append(line)
        
        metrics['ip_addresses'] = ip_addresses
        metrics['ipv4_addresses'] = ipv4_addresses
        metrics['ipv6_addresses'] = ipv6_addresses
        metrics['resolved'] = len(ip_addresses) > 0
        metrics['ip_count'] = len(ip_addresses)
        metrics['ipv4_count'] = len(ipv4_addresses)
        metrics['ipv6_count'] = len(ipv6_addresses)
        metrics['has_ipv4'] = len(ipv4_addresses) > 0
        metrics['has_ipv6'] = len(ipv6_addresses) > 0
        
        return metrics
    
    def _log_to_csv(self, result: TestResult):
        """Log result to CSV."""
        # Log each IP address separately
        ip_addresses = result.metrics.get('ip_addresses', [])
        
        if ip_addresses:
            for idx, ip in enumerate(ip_addresses):
                self.csv_handler.write_result(
                    timestamp=result.timestamp,
                    test_name=result.test_name,
                    target=result.target,
                    metric=f"ip_address_{idx+1}",
                    value=ip,
                    status=result.status,
                    details=result.summary or "",
                )
        
        # Also log the count
        self.csv_handler.write_result(
            timestamp=result.timestamp,
            test_name=result.test_name,
            target=result.target,
            metric="ip_count",
            value=result.metrics.get('ip_count', 0),
            status=result.status,
            details=result.summary or "",
        )