"""
Enhanced connectivity tests with advanced options.
Includes customizable ping count, MTU/packet size, interval, timeout, and more.
"""

import re
import platform
from datetime import datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from netscope.modules.base import BaseTest, TestResult


@dataclass
class PingOptions:
    """Advanced options for ping test."""
    count: int = 4  # Number of ping packets
    packet_size: Optional[int] = None  # Packet size in bytes (None = default)
    interval: Optional[float] = None  # Interval between pings in seconds
    timeout: Optional[int] = None  # Timeout per ping in seconds
    ttl: Optional[int] = None  # Time to live
    dont_fragment: bool = False  # Don't fragment flag (for MTU discovery)
    flood: bool = False  # Flood ping (requires root/admin)
    
    def __post_init__(self):
        """Validate options."""
        if self.count < 1:
            raise ValueError("Count must be at least 1")
        if self.packet_size is not None and (self.packet_size < 0 or self.packet_size > 65507):
            raise ValueError("Packet size must be between 0 and 65507 bytes")
        if self.interval is not None and self.interval < 0:
            raise ValueError("Interval must be non-negative")
        if self.timeout is not None and self.timeout < 1:
            raise ValueError("Timeout must be at least 1 second")
        if self.ttl is not None and (self.ttl < 1 or self.ttl > 255):
            raise ValueError("TTL must be between 1 and 255")


class PingTestEnhanced(BaseTest):
    """Enhanced ping test with advanced options."""
    
    def run(self, target: str, options: Optional[PingOptions] = None) -> TestResult:
        """
        Run enhanced ping test with custom options.
        
        Args:
            target: Target host (IP or hostname)
            options: PingOptions with advanced settings
            
        Returns:
            TestResult with metrics and summary
        """
        if options is None:
            options = PingOptions()
        
        start_time = datetime.now()
        
        # Build ping command based on OS and options
        os_type = platform.system()
        command = self._build_command(target, options, os_type)
        
        # Execute command with appropriate timeout
        cmd_timeout = 30
        if options.timeout:
            cmd_timeout = options.count * options.timeout + 10
        elif options.count > 10:
            cmd_timeout = options.count * 2 + 10
        
        result = self.executor.run_command(command, timeout=cmd_timeout)
        
        # Parse output
        metrics = self.parse_output(result.stdout, options) if result.success else {}
        
        # Add options to metrics for reference
        metrics['ping_count'] = options.count
        if options.packet_size:
            metrics['packet_size'] = options.packet_size
        if options.interval:
            metrics['interval'] = options.interval
        if options.ttl:
            metrics['ttl'] = options.ttl
        
        # Determine status and create summary
        status, summary = self._determine_status(target, result, metrics, options)
        
        test_result = TestResult(
            test_name="Ping Test (Enhanced)",
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
    
    def _build_command(self, target: str, options: PingOptions, os_type: str) -> List[str]:
        """Build ping command with options based on OS."""
        if os_type == "Windows":
            command = ["ping"]
            
            # Count
            command.extend(["-n", str(options.count)])
            
            # Packet size
            if options.packet_size is not None:
                command.extend(["-l", str(options.packet_size)])
            
            # Timeout (in milliseconds)
            if options.timeout is not None:
                command.extend(["-w", str(options.timeout * 1000)])
            
            # TTL
            if options.ttl is not None:
                command.extend(["-i", str(options.ttl)])
            
            # Don't fragment
            if options.dont_fragment:
                command.append("-f")
            
            command.append(target)
        
        else:  # Linux/macOS
            command = ["ping"]
            
            # Count
            command.extend(["-c", str(options.count)])
            
            # Packet size
            if options.packet_size is not None:
                command.extend(["-s", str(options.packet_size)])
            
            # Interval (requires root for < 0.2 on some systems)
            if options.interval is not None:
                command.extend(["-i", str(options.interval)])
            
            # Timeout (per packet)
            if options.timeout is not None:
                if os_type == "Linux":
                    command.extend(["-W", str(options.timeout)])
                else:  # macOS
                    command.extend(["-W", str(options.timeout * 1000)])
            
            # TTL
            if options.ttl is not None:
                if os_type == "Linux":
                    command.extend(["-t", str(options.ttl)])
                else:  # macOS
                    command.extend(["-m", str(options.ttl)])
            
            # Don't fragment (Linux only)
            if options.dont_fragment and os_type == "Linux":
                command.extend(["-M", "do"])
            
            # Flood (requires root)
            if options.flood:
                command.append("-f")
            
            command.append(target)
        
        return command
    
    def _determine_status(
        self, 
        target: str, 
        result, 
        metrics: Dict[str, Any], 
        options: PingOptions
    ) -> tuple[str, str]:
        """Determine test status and create summary."""
        if not result.success:
            return "failure", f"Ping test failed: {result.stderr}"
        
        packet_loss = metrics.get("packet_loss", 100)
        
        if packet_loss == 100:
            return "warning", f"Host {target} is unreachable (100% packet loss)"
        
        # Build summary
        summary_parts = [f"Host {target} is reachable"]
        
        # Packet loss info
        if packet_loss > 0:
            summary_parts.append(f"{packet_loss}% packet loss")
        
        # Latency info
        avg_latency = metrics.get('avg_latency')
        if avg_latency is not None:
            min_latency = metrics.get('min_latency')
            max_latency = metrics.get('max_latency')
            
            if min_latency is not None and max_latency is not None:
                summary_parts.append(
                    f"Latency min/avg/max: {min_latency:.1f}/{avg_latency:.1f}/{max_latency:.1f} ms"
                )
            else:
                summary_parts.append(f"Average latency: {avg_latency:.1f} ms")
        
        # Packet size info
        if options.packet_size:
            summary_parts.append(f"Packet size: {options.packet_size} bytes")
        
        # Jitter info
        mdev = metrics.get('mdev_latency')
        if mdev is not None:
            summary_parts.append(f"Jitter: {mdev:.1f} ms")
        
        summary = ". ".join(summary_parts) + "."
        
        # Determine status based on packet loss and latency
        if packet_loss > 20:
            status = "warning"
        elif avg_latency and avg_latency > 200:
            status = "warning"
        else:
            status = "success"
        
        return status, summary
    
    def parse_output(self, output: str, options: PingOptions) -> Dict[str, Any]:
        """Parse ping output with enhanced metrics."""
        metrics = {}
        
        # Parse packet loss
        loss_match = re.search(r'(\d+)%.*loss', output)
        if loss_match:
            metrics['packet_loss'] = int(loss_match.group(1))
        
        # Parse latency statistics
        # Linux/Mac: rtt min/avg/max/mdev = 10.123/15.456/20.789/2.345 ms
        latency_match = re.search(
            r'(?:rtt|round-trip).*?min/avg/max[/=\s]+(?:[\w]+[\s=]+)?([\d.]+)/([\d.]+)/([\d.]+)(?:/([\d.]+))?\s*ms',
            output,
            re.IGNORECASE
        )
        if latency_match:
            metrics['min_latency'] = float(latency_match.group(1))
            metrics['avg_latency'] = float(latency_match.group(2))
            metrics['max_latency'] = float(latency_match.group(3))
            if latency_match.group(4) is not None:
                metrics['mdev_latency'] = float(latency_match.group(4))
        else:
            # Windows: Minimum = 10ms, Maximum = 20ms, Average = 15ms
            min_match = re.search(r'Minimum\s*=\s*([\d]+)ms', output)
            max_match = re.search(r'Maximum\s*=\s*([\d]+)ms', output)
            avg_match = re.search(r'Average\s*=\s*([\d]+)ms', output)
            
            if min_match:
                metrics['min_latency'] = float(min_match.group(1))
            if max_match:
                metrics['max_latency'] = float(max_match.group(1))
            if avg_match:
                metrics['avg_latency'] = float(avg_match.group(1))
        
        # Calculate jitter if we have min/max but not mdev
        if 'mdev_latency' not in metrics and 'min_latency' in metrics and 'max_latency' in metrics:
            metrics['jitter'] = metrics['max_latency'] - metrics['min_latency']
        
        # Count successful packets
        packets_match = re.search(r'(\d+)\s+(?:packets\s+)?received', output)
        if packets_match:
            metrics['packets_received'] = int(packets_match.group(1))
        
        # Count transmitted packets
        transmitted_match = re.search(r'(\d+)\s+(?:packets\s+)?transmitted', output)
        if transmitted_match:
            metrics['packets_transmitted'] = int(transmitted_match.group(1))
        
        # Parse time statistics if available
        time_match = re.search(r'time\s+([\d.]+)ms', output, re.IGNORECASE)
        if time_match:
            metrics['total_time_ms'] = float(time_match.group(1))
        
        # Detect MTU issues (packet too large)
        if re.search(r'message too long|packet too large|fragmentation needed', output, re.IGNORECASE):
            metrics['mtu_issue_detected'] = True
        
        # Detect TTL exceeded
        if re.search(r'time to live exceeded|ttl exceeded', output, re.IGNORECASE):
            metrics['ttl_exceeded'] = True
        
        return metrics
    
    def _log_to_csv(self, result: TestResult):
        """Log result to CSV."""
        for metric_name, metric_value in result.metrics.items():
            # Skip boolean flags for CSV
            if isinstance(metric_value, bool):
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


class TracerouteTestEnhanced(BaseTest):
    """Enhanced traceroute test with advanced options."""
    
    def run(
        self, 
        target: str, 
        max_hops: int = 30,
        timeout: int = 5,
        queries: int = 3,
        packet_size: Optional[int] = None,
    ) -> TestResult:
        """
        Run enhanced traceroute test.
        
        Args:
            target: Target host
            max_hops: Maximum number of hops
            timeout: Timeout per hop in seconds
            queries: Number of queries per hop
            packet_size: Packet size in bytes
            
        Returns:
            TestResult with hop details
        """
        start_time = datetime.now()
        
        # Build traceroute command
        os_type = platform.system()
        command = self._build_command(target, max_hops, timeout, queries, packet_size, os_type)
        
        # Execute with extended timeout
        cmd_timeout = max_hops * timeout * queries + 30
        result = self.executor.run_command(command, timeout=cmd_timeout)
        
        # Parse output
        metrics = self.parse_output(result.stdout) if result.success else {}
        
        # Add options to metrics
        metrics['max_hops'] = max_hops
        metrics['timeout'] = timeout
        metrics['queries_per_hop'] = queries
        if packet_size:
            metrics['packet_size'] = packet_size
        
        # Determine status
        if result.success:
            status = "success"
            hop_count = metrics.get('hop_count', 0)
            summary = f"Traced route to {target} in {hop_count} hops"
            
            if not metrics.get('destination_reached', False):
                summary += " (destination not reached)"
                status = "warning"
        else:
            status = "failure"
            summary = f"Traceroute failed: {result.stderr}"
        
        test_result = TestResult(
            test_name="Traceroute Test (Enhanced)",
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
    
    def _build_command(
        self, 
        target: str, 
        max_hops: int, 
        timeout: int, 
        queries: int,
        packet_size: Optional[int],
        os_type: str
    ) -> List[str]:
        """Build traceroute command with options."""
        if os_type == "Windows":
            command = ["tracert", "-d", "-h", str(max_hops)]
            if timeout:
                command.extend(["-w", str(timeout * 1000)])
            command.append(target)
        else:
            command = ["traceroute", "-n", "-m", str(max_hops)]
            if timeout:
                command.extend(["-w", str(timeout)])
            if queries:
                command.extend(["-q", str(queries)])
            if packet_size:
                command.append(str(packet_size))
            command.append(target)
        
        return command
    
    def parse_output(self, output: str) -> Dict[str, Any]:
        """Parse traceroute output with enhanced details."""
        metrics: Dict[str, Any] = {}
        lines = output.strip().split('\n')
        hop_details: List[Dict[str, Any]] = []

        # Regex patterns for different formats
        hop_line_linux = re.compile(r'^\s*(\d+)\s+(\S+)\s+([\d.<]+)\s*ms')
        hop_line_win = re.compile(r'^\s*(\d+)\s+(?:[\d.<]+\s*ms\s+)+(\d+\.\d+\.\d+\.\d+)')
        
        for line in lines:
            if not line.strip():
                continue
            
            # Linux/macOS style
            m = hop_line_linux.search(line)
            if m:
                hop_num = int(m.group(1))
                host = m.group(2)
                rtt_str = m.group(3).strip()
                
                rtt_ms = 0.0
                if rtt_str.startswith('<'):
                    rtt_ms = 0.0
                else:
                    try:
                        rtt_ms = float(rtt_str)
                    except ValueError:
                        rtt_ms = 0.0
                
                hop_details.append({"hop": hop_num, "host": host, "rtt_ms": rtt_ms})
                continue
            
            # Windows style
            m = hop_line_win.search(line)
            if m:
                hop_num = int(m.group(1))
                host = m.group(2)
                hop_details.append({"hop": hop_num, "host": host, "rtt_ms": 0.0})
                continue

        metrics['hop_count'] = len(hop_details) if hop_details else sum(
            1 for line in lines if re.match(r'^\s*\d+', line)
        )
        
        if hop_details:
            metrics['hop_details'] = hop_details
            
            # Calculate average RTT across all hops
            rtts = [h['rtt_ms'] for h in hop_details if h['rtt_ms'] > 0]
            if rtts:
                metrics['avg_hop_rtt'] = sum(rtts) / len(rtts)
                metrics['max_hop_rtt'] = max(rtts)

        if lines:
            last_line = lines[-1]
            metrics['destination_reached'] = bool(
                re.search(r'\d+\.\d+\.\d+\.\d+', last_line)
            )
        else:
            metrics['destination_reached'] = False

        return metrics
    
    def _log_to_csv(self, result: TestResult):
        """Log result to CSV."""
        for metric_name, metric_value in result.metrics.items():
            if metric_name == "hop_details":
                continue
            if isinstance(metric_value, bool):
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
