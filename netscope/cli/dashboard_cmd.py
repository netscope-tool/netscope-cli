"""
CLI command for aggregated dashboard with comprehensive network view.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from typing import List, Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from netscope.tui.aggregated_dashboard import AggregatedDashboard, DiscoveredDevice
from netscope.utils.network_info import get_network_info
from netscope.utils.system_info import get_system_info
from netscope.utils.mac_vendor import get_vendor_from_mac
from netscope.utils.device_classifier import categorize_device
from netscope.core.executor import TestExecutor
from netscope.core.detector import SystemDetector
from netscope.storage.csv_handler import CSVHandler
from netscope.modules.arp_scan import ARPScanTest
from netscope.modules.ports import PortScanTest


def scan_device_ports(ip: str, executor: TestExecutor, csv_handler: CSVHandler) -> List[int]:
    """
    Quick port scan for a device (common ports only).
    
    Args:
        ip: IP address to scan
        executor: Test executor
        csv_handler: CSV handler
        
    Returns:
        List of open ports
    """
    try:
        port_scanner = PortScanTest(executor, csv_handler)
        
        # Scan common ports quickly
        common_ports = [
            21, 22, 23, 25, 53, 80, 110, 143, 443, 445, 
            3306, 3389, 5432, 8080, 8443, 9100
        ]
        
        result = port_scanner.run(ip, common_ports, timeout=1)
        
        if result.status == "success" and result.metrics.get("open_ports"):
            return result.metrics["open_ports"]
    except Exception:
        pass
    
    return []


def discover_network_devices(
    console: Console,
    executor: TestExecutor,
    csv_handler: CSVHandler,
    scan_ports: bool = True,
) -> List[DiscoveredDevice]:
    """
    Discover devices on the local network.
    
    Args:
        console: Rich console
        executor: Test executor
        csv_handler: CSV handler
        scan_ports: Whether to scan ports on discovered devices
        
    Returns:
        List of discovered devices
    """
    devices = []
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Get network info for gateway
        task1 = progress.add_task("Getting network information...", total=None)
        network_info = get_network_info()
        progress.update(task1, completed=True)
        
        # ARP scan
        task2 = progress.add_task("Scanning local network (ARP)...", total=None)
        try:
            arp_scanner = ARPScanTest(executor, csv_handler)
            arp_result = arp_scanner.run()
            progress.update(task2, completed=True)
            
            if arp_result.status == "success" and arp_result.metrics.get("devices"):
                discovered = arp_result.metrics["devices"]
                
                # Port scanning if enabled
                if scan_ports and discovered:
                    task3 = progress.add_task(
                        f"Scanning ports on {len(discovered)} device(s)...",
                        total=len(discovered)
                    )
                    
                    # Scan ports in parallel
                    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
                        futures = {}
                        for dev in discovered:
                            future = pool.submit(
                                scan_device_ports,
                                dev["ip"],
                                executor,
                                csv_handler,
                            )
                            futures[future] = dev
                        
                        for future in concurrent.futures.as_completed(futures):
                            dev = futures[future]
                            try:
                                open_ports = future.result()
                                dev["open_ports"] = open_ports
                            except Exception:
                                dev["open_ports"] = []
                            
                            progress.advance(task3)
                
                # Convert to DiscoveredDevice objects
                for dev in discovered:
                    ip = dev.get("ip", "")
                    mac = dev.get("mac", "")
                    vendor = dev.get("vendor", "Unknown")
                    hostname = dev.get("hostname")
                    open_ports = dev.get("open_ports", [])
                    
                    # Categorize device
                    category_result = categorize_device(
                        ip=ip,
                        mac=mac,
                        vendor=vendor,
                        hostname=hostname,
                        open_ports=open_ports,
                    )
                    
                    # Check if gateway
                    is_gateway = (ip == network_info.gateway_ip)
                    
                    device = DiscoveredDevice(
                        ip=ip,
                        mac=mac,
                        vendor=vendor,
                        hostname=hostname,
                        category=category_result.primary,
                        category_confidence=category_result.confidence,
                        open_ports=open_ports,
                        is_gateway=is_gateway,
                    )
                    devices.append(device)
        
        except Exception as e:
            progress.update(task2, description=f"[red]ARP scan failed: {str(e)}[/red]")
    
    return devices


def identify_security_issues(
    devices: List[DiscoveredDevice],
    network_info,
) -> List[dict]:
    """
    Identify potential security issues from discovered devices.
    
    Args:
        devices: List of discovered devices
        network_info: Network information
        
    Returns:
        List of security issues
    """
    issues = []
    
    # Check for dangerous open ports
    dangerous_ports = {
        21: ("FTP", "high"),
        23: ("Telnet", "critical"),
        25: ("SMTP", "medium"),
        445: ("SMB", "high"),
        3389: ("RDP", "high"),
    }
    
    for device in devices:
        for port in device.open_ports:
            if port in dangerous_ports:
                service, severity = dangerous_ports[port]
                issues.append({
                    "severity": severity,
                    "description": f"{service} (port {port}) open on {device.ip}",
                })
    
    # Check for too many servers
    server_count = sum(1 for d in devices if d.category == "server")
    if server_count > 5:
        issues.append({
            "severity": "low",
            "description": f"{server_count} servers detected - ensure all are authorized",
        })
    
    # Check for unknown devices
    unknown_count = sum(1 for d in devices if d.category == "unknown")
    if unknown_count > 0:
        issues.append({
            "severity": "low",
            "description": f"{unknown_count} unknown device(s) - verify identity",
        })
    
    return issues


def run_aggregated_dashboard(
    console: Optional[Console] = None,
    scan_ports: bool = True,
    live_mode: bool = False,
) -> None:
    """
    Run the aggregated dashboard with comprehensive network view.
    
    Args:
        console: Rich console instance
        scan_ports: Whether to scan ports on discovered devices
        live_mode: Whether to run in live refresh mode
    """
    if console is None:
        console = Console()
    
    # Initialize dashboard
    dashboard = AggregatedDashboard(console=console)
    
    # Create temporary executor and CSV handler
    detector = SystemDetector()
    system_info_obj = detector.detect_system()
    
    from netscope.storage.logger import setup_logging
    from pathlib import Path
    logger = setup_logging(Path("output"), verbose=False)
    
    executor = TestExecutor(system_info_obj, logger)
    csv_handler = CSVHandler(Path("output") / "dashboard.csv")
    
    console.print("\n[bold cyan]NetScope Aggregated Dashboard[/bold cyan]")
    console.print("[dim]Gathering network and system information...[/dim]\n")
    
    # Gather information
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Network info
        task1 = progress.add_task("Loading network information...", total=None)
        network_info = get_network_info()
        dashboard.update_network_info(network_info)
        progress.update(task1, completed=True)
        
        # System info
        task2 = progress.add_task("Loading system information...", total=None)
        system_info = get_system_info()
        dashboard.update_system_info(system_info)
        progress.update(task2, completed=True)
    
    # Discover devices
    console.print()
    devices = discover_network_devices(console, executor, csv_handler, scan_ports)
    dashboard.update_devices(devices)
    
    # Identify security issues
    security_issues = identify_security_issues(devices, network_info)
    dashboard.update_security_issues(security_issues)
    
    # Render dashboard
    console.print("\n")
    
    if live_mode:
        console.print("[dim]Dashboard running in live mode. Press Ctrl+C to exit.[/dim]\n")
        try:
            dashboard.run_live()
        except KeyboardInterrupt:
            console.print("\n[cyan]Dashboard stopped.[/cyan]")
    else:
        dashboard.render()
        console.print("\n[dim]Dashboard rendered. Use --live flag for auto-refresh mode.[/dim]")
