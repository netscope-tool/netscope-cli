"""
Connectivity tests (ping, traceroute).
"""

import re
import platform
from datetime import datetime
from typing import Dict, Any

from netscope.modules.base import BaseTest, TestResult


class PingTest(BaseTest):
    """Ping connectivity test."""
    
    def run(self, target: str) -> TestResult:
        """Run ping test."""
        start_time = datetime.now()
        
        # Build ping command based on OS
        os_type = platform.system()
        if os_type == "Windows":
            command = ["ping", "-n", "4", target]
        else:
            command = ["ping", "-c", "4", target]
        
        # Execute command
        result = self.executor.run_command(command)
        
        # Parse output
        metrics = self.parse_output(result.stdout) if result.success else {}
        
        # Determine status
        if result.success and metrics.get("packet_loss", 100) < 100:
            status = "success"
            summary = f"Host {target} is reachable. Average latency: {metrics.get('avg_latency', 'N/A')}ms"
        elif result.success and metrics.get("packet_loss", 100) == 100:
            status = "warning"
            summary = f"Host {target} is unreachable (100% packet loss)"
        else:
            status = "failure"
            summary = f"Ping test failed: {result.stderr}"
        
        test_result = TestResult(
            test_name="Ping Test",
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
    
    def parse_output(self, output: str) -> Dict[str, Any]:
        """Parse ping output."""
        metrics = {}
        
        # Parse packet loss
        loss_match = re.search(r'(\d+)%.*loss', output)
        if loss_match:
            metrics['packet_loss'] = int(loss_match.group(1))
        
        # Parse latency (works for both Linux/Mac and Windows)
        # Linux/Mac: rtt min/avg/max/mdev = 10.123/15.456/20.789/2.345 ms
        latency_match = re.search(r'min/avg/max[/=\s]+[\w]+[\s=]+[\d.]+/([\d.]+)/([\d.]+)', output)
        if latency_match:
            metrics['avg_latency'] = float(latency_match.group(1))
            metrics['max_latency'] = float(latency_match.group(2))
        else:
            # Windows: Average = 15ms
            avg_match = re.search(r'Average\s*=\s*([\d]+)ms', output)
            if avg_match:
                metrics['avg_latency'] = float(avg_match.group(1))
        
        # Count successful packets
        packets_match = re.search(r'(\d+)\s+(?:packets\s+)?received', output)
        if packets_match:
            metrics['packets_received'] = int(packets_match.group(1))
        
        return metrics
    
    def _log_to_csv(self, result: TestResult):
        """Log result to CSV."""
        for metric_name, metric_value in result.metrics.items():
            self.csv_handler.write_result(
                timestamp=result.timestamp,
                test_name=result.test_name,
                target=result.target,
                metric=metric_name,
                value=metric_value,
                status=result.status,
                details=result.summary or "",
            )


class TracerouteTest(BaseTest):
    """Traceroute path analysis test."""
    
    def run(self, target: str) -> TestResult:
        """Run traceroute test."""
        start_time = datetime.now()
        
        # Build traceroute command based on OS
        os_type = platform.system()
        if os_type == "Windows":
            command = ["tracert", "-d", "-h", "15", target]
        else:
            command = ["traceroute", "-n", "-m", "15", target]
        
        # Execute command
        result = self.executor.run_command(command, timeout=60)
        
        # Parse output
        metrics = self.parse_output(result.stdout) if result.success else {}
        
        # Determine status
        if result.success:
            status = "success"
            hop_count = metrics.get('hop_count', 0)
            summary = f"Traced route to {target} in {hop_count} hops"
        else:
            status = "failure"
            summary = f"Traceroute failed: {result.stderr}"
        
        test_result = TestResult(
            test_name="Traceroute Test",
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
    
    def parse_output(self, output: str) -> Dict[str, Any]:
        """Parse traceroute output."""
        metrics = {}
        
        # Count hops
        lines = output.strip().split('\n')
        hop_count = 0
        
        for line in lines:
            # Match hop lines (starting with number)
            if re.match(r'^\s*\d+', line):
                hop_count += 1
        
        metrics['hop_count'] = hop_count
        
        # Extract final destination if reached
        if lines:
            last_line = lines[-1]
            # Check if we reached the destination (has IP address)
            if re.search(r'\d+\.\d+\.\d+\.\d+', last_line):
                metrics['destination_reached'] = True
            else:
                metrics['destination_reached'] = False
        
        return metrics
    
    def _log_to_csv(self, result: TestResult):
        """Log result to CSV."""
        for metric_name, metric_value in result.metrics.items():
            self.csv_handler.write_result(
                timestamp=result.timestamp,
                test_name=result.test_name,
                target=result.target,
                metric=metric_name,
                value=metric_value,
                status=result.status,
                details=result.summary or "",
            )