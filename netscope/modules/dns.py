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
            summary = f"Resolved {target} to {len(ip_addresses)} address(es): {', '.join(ip_addresses[:3])}"
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
        """Parse DNS lookup output."""
        metrics = {}
        ip_addresses = []
        
        if os_type == "Windows":
            # Parse nslookup output
            # Look for lines like "Address:  192.168.1.1"
            for line in output.split('\n'):
                if 'Address' in line and ':' in line:
                    parts = line.split(':')
                    if len(parts) > 1:
                        ip = parts[1].strip()
                        # Validate it's an IP address
                        if re.match(r'\d+\.\d+\.\d+\.\d+', ip):
                            ip_addresses.append(ip)
        else:
            # Parse dig output (simpler - just IP addresses)
            for line in output.strip().split('\n'):
                line = line.strip()
                # Match IPv4 addresses
                if re.match(r'^\d+\.\d+\.\d+\.\d+$', line):
                    ip_addresses.append(line)
        
        metrics['ip_addresses'] = ip_addresses
        metrics['resolved'] = len(ip_addresses) > 0
        metrics['ip_count'] = len(ip_addresses)
        
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