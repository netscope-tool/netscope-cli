"""
Bandwidth testing module.
Provides upload/download speed tests and network performance metrics.
"""

from __future__ import annotations

import time
import socket
import threading
from typing import Optional, Callable
from dataclasses import dataclass

from netscope.modules.base import BaseTest, TestResult
from netscope.core.executor import TestExecutor
from netscope.storage.csv_handler import CSVHandler


@dataclass
class BandwidthMetrics:
    """Bandwidth test metrics."""
    download_mbps: float = 0.0
    upload_mbps: float = 0.0
    latency_ms: float = 0.0
    jitter_ms: float = 0.0
    packet_loss_percent: float = 0.0
    test_duration_sec: float = 0.0


class BandwidthTest(BaseTest):
    """
    Bandwidth testing using multiple methods.
    
    Methods:
    1. HTTP-based download/upload (default)
    2. Socket-based throughput test
    3. External speedtest-cli integration (if available)
    """
    
    def __init__(
        self,
        executor: TestExecutor,
        csv_handler: CSVHandler,
        method: str = "http",
    ):
        """
        Initialize bandwidth test.
        
        Args:
            executor: Test executor instance
            csv_handler: CSV handler for logging
            method: Test method ('http', 'socket', 'speedtest')
        """
        super().__init__(executor, csv_handler)
        self.method = method
    
    def run(
        self,
        target: str = "auto",
        duration: int = 10,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> TestResult:
        """
        Run bandwidth test.
        
        Args:
            target: Target server (or 'auto' for automatic selection)
            duration: Test duration in seconds
            progress_callback: Optional callback for progress updates
            
        Returns:
            TestResult with bandwidth metrics
        """
        start_time = time.time()
        
        try:
            if self.method == "speedtest":
                metrics = self._run_speedtest(target, progress_callback)
            elif self.method == "socket":
                metrics = self._run_socket_test(target, duration, progress_callback)
            else:  # http
                metrics = self._run_http_test(target, duration, progress_callback)
            
            elapsed = time.time() - start_time
            
            result = TestResult(
                test_name="bandwidth_test",
                target=target,
                status="success",
                message=f"Bandwidth test completed: ↓{metrics.download_mbps:.2f} Mbps ↑{metrics.upload_mbps:.2f} Mbps",
                metrics={
                    "download_mbps": metrics.download_mbps,
                    "upload_mbps": metrics.upload_mbps,
                    "latency_ms": metrics.latency_ms,
                    "jitter_ms": metrics.jitter_ms,
                    "packet_loss_percent": metrics.packet_loss_percent,
                    "test_duration_sec": elapsed,
                    "method": self.method,
                },
                raw_output=f"Download: {metrics.download_mbps:.2f} Mbps\n"
                          f"Upload: {metrics.upload_mbps:.2f} Mbps\n"
                          f"Latency: {metrics.latency_ms:.2f} ms\n"
                          f"Jitter: {metrics.jitter_ms:.2f} ms\n"
                          f"Packet Loss: {metrics.packet_loss_percent:.2f}%",
            )
            
            self.csv_handler.write_result(result)
            return result
            
        except Exception as e:
            self.executor.logger.error(f"Bandwidth test failed: {e}")
            result = TestResult(
                test_name="bandwidth_test",
                target=target,
                status="error",
                message=f"Bandwidth test failed: {str(e)}",
                metrics={},
                raw_output=str(e),
            )
            self.csv_handler.write_result(result)
            return result
    
    def _run_speedtest(
        self,
        target: str,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> BandwidthMetrics:
        """
        Run bandwidth test using speedtest-cli.
        
        Args:
            target: Server ID or 'auto'
            progress_callback: Progress callback
            
        Returns:
            BandwidthMetrics
        """
        import subprocess
        import json
        
        # Check if speedtest-cli is available
        try:
            subprocess.run(
                ["speedtest-cli", "--version"],
                capture_output=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError("speedtest-cli not installed. Install with: pip install speedtest-cli")
        
        # Run speedtest
        cmd = ["speedtest-cli", "--json"]
        if target != "auto":
            cmd.extend(["--server", target])
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode != 0:
            raise RuntimeError(f"speedtest-cli failed: {result.stderr}")
        
        data = json.loads(result.stdout)
        
        return BandwidthMetrics(
            download_mbps=data.get("download", 0) / 1_000_000,  # bits to Mbps
            upload_mbps=data.get("upload", 0) / 1_000_000,
            latency_ms=data.get("ping", 0),
            jitter_ms=0.0,  # speedtest-cli doesn't provide jitter
            packet_loss_percent=0.0,
        )
    
    def _run_http_test(
        self,
        target: str,
        duration: int,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> BandwidthMetrics:
        """
        Run HTTP-based bandwidth test.
        
        Args:
            target: Target URL or server
            duration: Test duration
            progress_callback: Progress callback
            
        Returns:
            BandwidthMetrics
        """
        # Use common speed test files
        if target == "auto":
            # Use a public test file (example - in production, use reliable CDN)
            download_url = "http://speedtest.tele2.net/10MB.zip"
            upload_url = None  # HTTP upload requires server support
        else:
            download_url = target
            upload_url = None
        
        # Measure download speed
        download_mbps = self._measure_download(download_url, duration, progress_callback)
        
        # Upload test (simplified - would need proper server)
        upload_mbps = 0.0  # Placeholder
        
        # Measure latency
        latency_ms = self._measure_latency(download_url)
        
        return BandwidthMetrics(
            download_mbps=download_mbps,
            upload_mbps=upload_mbps,
            latency_ms=latency_ms,
            jitter_ms=0.0,
            packet_loss_percent=0.0,
        )
    
    def _run_socket_test(
        self,
        target: str,
        duration: int,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> BandwidthMetrics:
        """
        Run socket-based throughput test.
        
        Args:
            target: Target host:port
            duration: Test duration
            progress_callback: Progress callback
            
        Returns:
            BandwidthMetrics
        """
        # Parse target
        if ":" in target:
            host, port = target.rsplit(":", 1)
            port = int(port)
        else:
            host = target
            port = 5201  # iperf3 default port
        
        # Simple throughput test
        throughput_mbps = self._measure_socket_throughput(host, port, duration)
        
        return BandwidthMetrics(
            download_mbps=throughput_mbps,
            upload_mbps=0.0,
            latency_ms=0.0,
            jitter_ms=0.0,
            packet_loss_percent=0.0,
        )
    
    def _measure_download(
        self,
        url: str,
        duration: int,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> float:
        """
        Measure download speed.
        
        Args:
            url: Download URL
            duration: Maximum test duration
            progress_callback: Progress callback
            
        Returns:
            Download speed in Mbps
        """
        try:
            import urllib.request
            
            start_time = time.time()
            bytes_downloaded = 0
            chunk_size = 8192
            
            with urllib.request.urlopen(url, timeout=duration) as response:
                while time.time() - start_time < duration:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    bytes_downloaded += len(chunk)
                    
                    if progress_callback:
                        elapsed = time.time() - start_time
                        progress = int((elapsed / duration) * 100)
                        progress_callback(min(progress, 100), 100)
            
            elapsed = time.time() - start_time
            if elapsed > 0:
                # Convert bytes/sec to Mbps
                mbps = (bytes_downloaded * 8) / (elapsed * 1_000_000)
                return mbps
            return 0.0
            
        except Exception as e:
            self.executor.logger.warning(f"Download measurement failed: {e}")
            return 0.0
    
    def _measure_latency(self, url: str) -> float:
        """
        Measure HTTP latency.
        
        Args:
            url: Target URL
            
        Returns:
            Latency in milliseconds
        """
        try:
            import urllib.request
            from urllib.parse import urlparse
            
            parsed = urlparse(url)
            host = parsed.hostname or parsed.path
            
            # Simple ping-like latency measurement
            latencies = []
            for _ in range(5):
                start = time.time()
                try:
                    urllib.request.urlopen(url, timeout=5)
                    latency = (time.time() - start) * 1000
                    latencies.append(latency)
                except:
                    pass
                time.sleep(0.5)
            
            if latencies:
                return sum(latencies) / len(latencies)
            return 0.0
            
        except Exception as e:
            self.executor.logger.warning(f"Latency measurement failed: {e}")
            return 0.0
    
    def _measure_socket_throughput(
        self,
        host: str,
        port: int,
        duration: int,
    ) -> float:
        """
        Measure socket throughput.
        
        Args:
            host: Target host
            port: Target port
            duration: Test duration
            
        Returns:
            Throughput in Mbps
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((host, port))
            
            start_time = time.time()
            bytes_transferred = 0
            data = b'x' * 1024  # 1KB chunks
            
            while time.time() - start_time < duration:
                sock.send(data)
                bytes_transferred += len(data)
            
            sock.close()
            
            elapsed = time.time() - start_time
            if elapsed > 0:
                mbps = (bytes_transferred * 8) / (elapsed * 1_000_000)
                return mbps
            return 0.0
            
        except Exception as e:
            self.executor.logger.warning(f"Socket throughput measurement failed: {e}")
            return 0.0


class JitterTest(BaseTest):
    """
    Jitter and packet loss testing for VoIP quality assessment.
    """
    
    def run(
        self,
        target: str,
        count: int = 100,
        interval: float = 0.02,  # 20ms for VoIP simulation
    ) -> TestResult:
        """
        Run jitter test.
        
        Args:
            target: Target host
            count: Number of packets
            interval: Interval between packets in seconds
            
        Returns:
            TestResult with jitter metrics
        """
        start_time = time.time()
        
        try:
            latencies = []
            lost_packets = 0
            
            for i in range(count):
                try:
                    # Measure round-trip time
                    rtt = self._measure_rtt(target)
                    if rtt is not None:
                        latencies.append(rtt)
                    else:
                        lost_packets += 1
                except:
                    lost_packets += 1
                
                time.sleep(interval)
            
            # Calculate jitter (variance in latency)
            if len(latencies) > 1:
                avg_latency = sum(latencies) / len(latencies)
                jitter = sum(abs(l - avg_latency) for l in latencies) / len(latencies)
                packet_loss = (lost_packets / count) * 100
            else:
                avg_latency = 0.0
                jitter = 0.0
                packet_loss = 100.0
            
            result = TestResult(
                test_name="jitter_test",
                target=target,
                status="success" if packet_loss < 5 else "warning",
                message=f"Jitter: {jitter:.2f}ms, Packet Loss: {packet_loss:.2f}%",
                metrics={
                    "avg_latency_ms": avg_latency,
                    "jitter_ms": jitter,
                    "packet_loss_percent": packet_loss,
                    "packets_sent": count,
                    "packets_received": count - lost_packets,
                },
                raw_output=f"Average Latency: {avg_latency:.2f} ms\n"
                          f"Jitter: {jitter:.2f} ms\n"
                          f"Packet Loss: {packet_loss:.2f}%\n"
                          f"Packets: {count - lost_packets}/{count}",
            )
            
            self.csv_handler.write_result(result)
            return result
            
        except Exception as e:
            self.executor.logger.error(f"Jitter test failed: {e}")
            result = TestResult(
                test_name="jitter_test",
                target=target,
                status="error",
                message=f"Jitter test failed: {str(e)}",
                metrics={},
                raw_output=str(e),
            )
            self.csv_handler.write_result(result)
            return result
    
    def _measure_rtt(self, target: str, timeout: float = 1.0) -> Optional[float]:
        """
        Measure round-trip time using ICMP (via ping command).
        
        Args:
            target: Target host
            timeout: Timeout in seconds
            
        Returns:
            RTT in milliseconds or None if failed
        """
        import subprocess
        import re
        
        try:
            # Use system ping command
            if self.executor.system_info.os_type == "Windows":
                cmd = ["ping", "-n", "1", "-w", str(int(timeout * 1000)), target]
                pattern = r"time[=<](\d+)ms"
            else:
                cmd = ["ping", "-c", "1", "-W", str(int(timeout)), target]
                pattern = r"time=(\d+\.?\d*)\s*ms"
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout + 1,
            )
            
            if result.returncode == 0:
                match = re.search(pattern, result.stdout)
                if match:
                    return float(match.group(1))
            
            return None
            
        except Exception:
            return None
