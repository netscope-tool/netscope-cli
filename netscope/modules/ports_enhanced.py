"""
Enhanced port scanning with service detection, UDP support, and advanced options.
"""

import socket
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass

from netscope.modules.base import BaseTest, TestResult


# Service name mapping for common ports
COMMON_SERVICES = {
    20: "FTP-DATA", 21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP",
    53: "DNS", 80: "HTTP", 110: "POP3", 143: "IMAP", 443: "HTTPS",
    445: "SMB", 3306: "MySQL", 3389: "RDP", 5432: "PostgreSQL",
    5900: "VNC", 8080: "HTTP-Proxy", 8443: "HTTPS-Alt", 9100: "JetDirect",
    27017: "MongoDB", 6379: "Redis", 5000: "UPnP", 1433: "MSSQL",
    3000: "Node.js", 5601: "Kibana", 9200: "Elasticsearch",
}


@dataclass
class PortScanOptions:
    """Advanced options for port scanning."""
    timeout: float = 2.0  # Connection timeout in seconds
    max_workers: int = 64  # Maximum concurrent threads
    service_detection: bool = True  # Attempt to detect service
    scan_udp: bool = False  # Also scan UDP ports (slower)
    aggressive: bool = False  # More aggressive scanning (faster but noisier)
    
    def __post_init__(self):
        """Validate options."""
        if self.timeout < 0.1 or self.timeout > 30:
            raise ValueError("Timeout must be between 0.1 and 30 seconds")
        if self.max_workers < 1 or self.max_workers > 1000:
            raise ValueError("Max workers must be between 1 and 1000")


@dataclass
class PortInfo:
    """Information about a scanned port."""
    port: int
    state: str  # open, closed, filtered
    protocol: str  # tcp, udp
    service: Optional[str] = None
    banner: Optional[str] = None
    version: Optional[str] = None


def detect_service(host: str, port: int, timeout: float = 2.0) -> Tuple[Optional[str], Optional[str]]:
    """
    Attempt to detect service and grab banner.
    Returns (service_name, banner)
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        
        # Try to grab banner
        banner = None
        try:
            # Some services send banner immediately
            sock.settimeout(1.0)
            data = sock.recv(1024)
            if data:
                banner = data.decode('utf-8', errors='ignore').strip()
        except:
            pass
        
        # If no banner, try sending a probe
        if not banner:
            try:
                sock.send(b"HEAD / HTTP/1.0\r\n\r\n")
                sock.settimeout(1.0)
                data = sock.recv(1024)
                if data:
                    banner = data.decode('utf-8', errors='ignore').strip()
            except:
                pass
        
        sock.close()
        
        # Detect service from banner
        service = COMMON_SERVICES.get(port)
        
        if banner:
            banner_lower = banner.lower()
            if 'ssh' in banner_lower:
                service = "SSH"
            elif 'http' in banner_lower or 'html' in banner_lower:
                service = "HTTP"
            elif 'ftp' in banner_lower:
                service = "FTP"
            elif 'smtp' in banner_lower:
                service = "SMTP"
            elif 'mysql' in banner_lower:
                service = "MySQL"
            elif 'postgres' in banner_lower:
                service = "PostgreSQL"
        
        return service, banner
    
    except Exception:
        return COMMON_SERVICES.get(port), None


def scan_tcp_port(
    host: str, 
    port: int, 
    timeout: float = 2.0,
    detect_service_flag: bool = True
) -> PortInfo:
    """Scan a single TCP port."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            # Port is open
            service = None
            banner = None
            
            if detect_service_flag:
                service, banner = detect_service(host, port, timeout)
            
            if not service:
                service = COMMON_SERVICES.get(port, "Unknown")
            
            return PortInfo(
                port=port,
                state="open",
                protocol="tcp",
                service=service,
                banner=banner[:100] if banner else None  # Truncate banner
            )
        else:
            return PortInfo(port=port, state="closed", protocol="tcp")
    
    except socket.timeout:
        return PortInfo(port=port, state="filtered", protocol="tcp")
    except Exception:
        return PortInfo(port=port, state="closed", protocol="tcp")


def scan_udp_port(host: str, port: int, timeout: float = 2.0) -> PortInfo:
    """
    Scan a single UDP port (basic check).
    UDP scanning is less reliable than TCP.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        
        # Send empty packet
        sock.sendto(b"", (host, port))
        
        try:
            # Wait for response
            data, _ = sock.recvfrom(1024)
            sock.close()
            
            # Got response, port is open
            service = COMMON_SERVICES.get(port, "Unknown")
            return PortInfo(port=port, state="open", protocol="udp", service=service)
        
        except socket.timeout:
            # No response - could be open or filtered
            sock.close()
            return PortInfo(port=port, state="open|filtered", protocol="udp")
    
    except Exception:
        return PortInfo(port=port, state="closed", protocol="udp")


class PortScanTestEnhanced(BaseTest):
    """Enhanced port scanning with service detection and advanced options."""
    
    def run(
        self,
        target: str,
        ports: List[int],
        options: Optional[PortScanOptions] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> TestResult:
        """
        Run enhanced port scan.
        
        Args:
            target: Target host
            ports: List of ports to scan
            options: PortScanOptions with advanced settings
            progress_callback: Optional callback for progress updates
            
        Returns:
            TestResult with detailed port information
        """
        if options is None:
            options = PortScanOptions()
        
        start_time = datetime.now()
        
        # Scan TCP ports
        port_results = []
        total = len(ports)
        completed = 0
        
        max_workers = min(options.max_workers, total) if total > 0 else 1
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_port = {
                executor.submit(
                    scan_tcp_port,
                    target,
                    port,
                    options.timeout,
                    options.service_detection
                ): port for port in ports
            }
            
            for future in as_completed(future_to_port):
                port_info = future.result()
                port_results.append(port_info)
                completed += 1
                
                if progress_callback:
                    progress_callback(completed, total)
        
        # Optionally scan UDP ports (subset)
        if options.scan_udp:
            # Only scan common UDP ports to save time
            common_udp = [53, 67, 68, 69, 123, 161, 162, 500, 514, 520]
            udp_ports = [p for p in ports if p in common_udp]
            
            for port in udp_ports:
                port_info = scan_udp_port(target, port, options.timeout)
                port_results.append(port_info)
        
        # Calculate metrics
        metrics = self._calculate_metrics(port_results, options)
        
        # Determine status and summary
        status, summary = self._determine_status(target, port_results, metrics)
        
        test_result = TestResult(
            test_name="Port Scan (Enhanced)",
            target=target,
            status=status,
            timestamp=start_time,
            duration=(datetime.now() - start_time).total_seconds(),
            metrics=metrics,
            summary=summary,
            raw_output=self._format_results(port_results),
            error=None,
        )
        
        # Log to CSV
        self._log_to_csv(test_result)
        
        return test_result
    
    def _calculate_metrics(
        self, 
        port_results: List[PortInfo],
        options: PortScanOptions
    ) -> Dict[str, Any]:
        """Calculate metrics from scan results."""
        metrics = {}
        
        # Count by state
        open_ports = [p for p in port_results if p.state == "open"]
        closed_ports = [p for p in port_results if p.state == "closed"]
        filtered_ports = [p for p in port_results if p.state == "filtered"]
        
        metrics['total_scanned'] = len(port_results)
        metrics['open_count'] = len(open_ports)
        metrics['closed_count'] = len(closed_ports)
        metrics['filtered_count'] = len(filtered_ports)
        
        # List of open ports
        metrics['open_ports'] = [p.port for p in open_ports]
        
        # Service breakdown
        services = {}
        for port_info in open_ports:
            if port_info.service:
                services[port_info.service] = services.get(port_info.service, 0) + 1
        
        metrics['services_detected'] = len(services)
        metrics['service_breakdown'] = services
        
        # Detailed port information
        metrics['port_details'] = [
            {
                'port': p.port,
                'state': p.state,
                'protocol': p.protocol,
                'service': p.service,
                'banner': p.banner[:50] if p.banner else None
            }
            for p in open_ports
        ]
        
        # Security assessment
        risky_ports = [21, 23, 25, 445, 3389, 5900]  # FTP, Telnet, SMTP, SMB, RDP, VNC
        risky_open = [p for p in open_ports if p.port in risky_ports]
        metrics['risky_ports_open'] = len(risky_open)
        
        return metrics
    
    def _determine_status(
        self,
        target: str,
        port_results: List[PortInfo],
        metrics: Dict[str, Any]
    ) -> Tuple[str, str]:
        """Determine test status and create summary."""
        open_count = metrics['open_count']
        risky_count = metrics.get('risky_ports_open', 0)
        
        # Build summary
        summary_parts = [f"Scanned {metrics['total_scanned']} ports on {target}"]
        summary_parts.append(f"{open_count} open, {metrics['closed_count']} closed")
        
        if metrics['filtered_count'] > 0:
            summary_parts.append(f"{metrics['filtered_count']} filtered")
        
        if open_count > 0:
            open_list = metrics['open_ports'][:5]
            summary_parts.append(f"Open ports: {', '.join(map(str, open_list))}")
            
            if len(metrics['open_ports']) > 5:
                summary_parts[-1] += f" (+{len(metrics['open_ports']) - 5} more)"
        
        if metrics['services_detected'] > 0:
            summary_parts.append(f"{metrics['services_detected']} services detected")
        
        if risky_count > 0:
            summary_parts.append(f"⚠️ {risky_count} potentially risky ports open")
        
        summary = ". ".join(summary_parts) + "."
        
        # Determine status
        if risky_count > 0:
            status = "warning"
        elif open_count > 0:
            status = "success"
        else:
            status = "success"
        
        return status, summary
    
    def _format_results(self, port_results: List[PortInfo]) -> str:
        """Format port scan results as text."""
        lines = ["Port Scan Results:", "=" * 60]
        
        open_ports = sorted([p for p in port_results if p.state == "open"], key=lambda x: x.port)
        
        if not open_ports:
            lines.append("No open ports found.")
        else:
            lines.append(f"\nOpen Ports ({len(open_ports)}):")
            lines.append("-" * 60)
            
            for port_info in open_ports:
                line = f"  {port_info.port}/{port_info.protocol}"
                
                if port_info.service:
                    line += f" - {port_info.service}"
                
                if port_info.banner:
                    banner_preview = port_info.banner[:50].replace('\n', ' ').replace('\r', '')
                    line += f" [{banner_preview}...]"
                
                lines.append(line)
        
        return "\n".join(lines)
    
    def _log_to_csv(self, result: TestResult):
        """Log result to CSV."""
        # Log aggregate metrics
        for metric_name, metric_value in result.metrics.items():
            if metric_name in ['port_details', 'service_breakdown', 'open_ports']:
                continue  # Skip complex structures
            
            if isinstance(metric_value, (int, float)):
                self.csv_handler.write_result(
                    timestamp=result.timestamp,
                    test_name=result.test_name,
                    target=result.target,
                    metric=metric_name,
                    value=metric_value,
                    status=result.status,
                    details=result.summary or "",
                )
