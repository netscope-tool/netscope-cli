"""
Connectivity tests (ping, traceroute).
"""

import re
import platform
from datetime import datetime
from typing import Any, Dict, List

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
            avg_ = metrics.get('avg_latency')
            if avg_ is not None:
                min_ = metrics.get('min_latency')
                max_ = metrics.get('max_latency')
                if min_ is not None and max_ is not None:
                    summary = f"Host {target} is reachable. Latency min/avg/max: {min_:.1f}/{avg_:.1f}/{max_:.1f} ms"
                else:
                    summary = f"Host {target} is reachable. Average latency: {avg_:.1f} ms"
            else:
                summary = f"Host {target} is reachable."
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
        latency_match = re.search(
            r'min/avg/max[/=\s]+[\w]+[\s=]+([\d.]+)/([\d.]+)/([\d.]+)(?:/([\d.]+))?\s*ms',
            output,
        )
        if latency_match:
            metrics['min_latency'] = float(latency_match.group(1))
            metrics['avg_latency'] = float(latency_match.group(2))
            metrics['max_latency'] = float(latency_match.group(3))
            if latency_match.group(4) is not None:
                metrics['mdev_latency'] = float(latency_match.group(4))
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
        """Parse traceroute output. Includes per-hop details when parseable."""
        metrics: Dict[str, Any] = {}
        lines = output.strip().split('\n')
        hop_details: List[Dict[str, Any]] = []

        # Linux/macOS: " 1  192.168.1.1  1.234 ms" or " 1  10.0.0.1  2.3 ms  2.1 ms"
        # Windows: "  1    <1 ms    <1 ms    <1 ms  192.168.1.1"
        hop_line_linux = re.compile(
            r'^\s*(\d+)\s+(\S+)\s+([\d.<]+)\s*ms'
        )
        hop_line_win = re.compile(
            r'^\s*(\d+)\s+(?:[\d.<]+\s*ms\s+)+(\d+\.\d+\.\d+\.\d+)'
        )

        for line in lines:
            if not line.strip():
                continue
            # Linux/macOS style
            m = hop_line_linux.search(line)
            if m:
                hop_num = int(m.group(1))
                host = m.group(2)
                rtt_str = m.group(3).strip()
                rtt_ms: float = 0.0
                if rtt_str.startswith('<'):
                    rtt_ms = 0.0
                else:
                    try:
                        rtt_ms = float(rtt_str)
                    except ValueError:
                        rtt_ms = 0.0
                hop_details.append({"hop": hop_num, "host": host, "rtt_ms": rtt_ms})
                continue
            # Windows style (hop number then times then IP at end)
            m = hop_line_win.search(line)
            if m:
                hop_num = int(m.group(1))
                host = m.group(2)
                hop_details.append({"hop": hop_num, "host": host, "rtt_ms": 0.0})
                continue
            # Fallback: any line starting with number (count only)
            if re.match(r'^\s*\d+', line):
                pass  # already counted via hop_details

        metrics['hop_count'] = len(hop_details) if hop_details else sum(
            1 for line in lines if re.match(r'^\s*\d+', line)
        )
        if hop_details:
            metrics['hop_details'] = hop_details

        if lines:
            last_line = lines[-1]
            metrics['destination_reached'] = bool(
                re.search(r'\d+\.\d+\.\d+\.\d+', last_line)
            )
        else:
            metrics['destination_reached'] = False

        return metrics
    
    def _log_to_csv(self, result: TestResult):
        """Log result to CSV. Skip hop_details (logged via hop_count)."""
        for metric_name, metric_value in result.metrics.items():
            if metric_name == "hop_details":
                continue
            self.csv_handler.write_result(
                timestamp=result.timestamp,
                test_name=result.test_name,
                target=result.target,
                metric=metric_name,
                value=metric_value,
                status=result.status,
                details=result.summary or "",
            )