"""
Comprehensive aggregated dashboard showing network status, system info, 
discovered devices with categorization, and security overview.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn

from netscope.utils.network_info import get_network_info, NetworkInfo
from netscope.utils.system_info import get_system_info, SystemInfo
from netscope.utils.device_classifier import (
    categorize_device, 
    get_category_icon, 
    get_category_color,
    get_category_description,
)


@dataclass
class DiscoveredDevice:
    """Information about a discovered network device."""
    ip: str
    mac: str
    vendor: str
    hostname: Optional[str] = None
    category: str = "unknown"
    category_confidence: float = 0.0
    open_ports: List[int] = field(default_factory=list)
    is_gateway: bool = False


class AggregatedDashboard:
    """
    Comprehensive network dashboard with aggregated information.
    Shows network info, system info, discovered devices, and security status.
    """
    
    def __init__(self, console: Optional[Console] = None):
        """Initialize aggregated dashboard."""
        self.console = console or Console()
        self.network_info: Optional[NetworkInfo] = None
        self.system_info: Optional[SystemInfo] = None
        self.devices: List[DiscoveredDevice] = []
        self.security_issues: List[Dict[str, str]] = []
        self.last_update: Optional[datetime] = None
    
    def create_header(self) -> Panel:
        """Create dashboard header."""
        title = Text()
        title.append("NetScope ", style="bold cyan")
        title.append("Live Network Dashboard", style="bold white")
        
        if self.last_update:
            subtitle = f"Last updated: {self.last_update.strftime('%H:%M:%S')}"
        else:
            subtitle = "Initializing..."
        
        return Panel(
            Align.center(title),
            subtitle=subtitle,
            border_style="cyan",
            padding=(0, 2),
        )
    
    def create_network_panel(self) -> Panel:
        """Create network information panel."""
        if not self.network_info:
            return Panel(
                Text("Loading network information...", style="dim"),
                title="[cyan]Network Information[/cyan]",
                border_style="cyan",
            )
        
        info = self.network_info
        
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Property", style="cyan", width=18)
        table.add_column("Value", style="white")
        
        table.add_row("Interface", info.interface or "N/A")
        table.add_row("Local IP", f"[green]{info.local_ip}[/green]" if info.local_ip else "N/A")
        table.add_row("Netmask", info.netmask or "N/A")
        table.add_row("Gateway", f"[yellow]{info.gateway_ip}[/yellow]" if info.gateway_ip else "N/A")
        
        if info.gateway_mac:
            table.add_row("Gateway MAC", info.gateway_mac)
        
        table.add_row("Public IP", f"[blue]{info.public_ip}[/blue]" if info.public_ip else "N/A")
        
        if info.provider:
            table.add_row("ISP", info.provider)
        
        if info.location:
            table.add_row("Location", info.location)
        
        if info.dns_servers:
            dns_str = ", ".join(info.dns_servers[:3])
            if len(info.dns_servers) > 3:
                dns_str += f" (+{len(info.dns_servers) - 3} more)"
            table.add_row("DNS Servers", dns_str)
        
        return Panel(
            table,
            title="[cyan]🌐 Network Information[/cyan]",
            border_style="cyan",
        )
    
    def create_system_panel(self) -> Panel:
        """Create system information panel."""
        if not self.system_info:
            return Panel(
                Text("Loading system information...", style="dim"),
                title="[green]System Information[/green]",
                border_style="green",
            )
        
        info = self.system_info
        
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Property", style="green", width=18)
        table.add_column("Value", style="white")
        
        table.add_row("Hostname", info.hostname or "N/A")
        table.add_row("OS", f"{info.os_name} {info.os_version}")
        table.add_row("Architecture", info.architecture or "N/A")
        
        if info.cpu_model:
            cpu_display = info.cpu_model
            if len(cpu_display) > 40:
                cpu_display = cpu_display[:37] + "..."
            table.add_row("CPU", cpu_display)
        
        if info.cpu_cores > 0:
            cpu_info = f"{info.cpu_cores} cores"
            if info.cpu_usage > 0:
                cpu_color = "green" if info.cpu_usage < 70 else "yellow" if info.cpu_usage < 90 else "red"
                cpu_info += f" ([{cpu_color}]{info.cpu_usage:.1f}% used[/{cpu_color}])"
            table.add_row("CPU Cores", cpu_info)
        
        if info.memory_total > 0:
            mem_color = "green" if info.memory_percent < 70 else "yellow" if info.memory_percent < 90 else "red"
            mem_str = f"{info.memory_used:,} MB / {info.memory_total:,} MB"
            if info.memory_percent > 0:
                mem_str += f" ([{mem_color}]{info.memory_percent:.1f}%[/{mem_color}])"
            table.add_row("Memory", mem_str)
        
        if info.disk_total > 0:
            disk_color = "green" if info.disk_percent < 70 else "yellow" if info.disk_percent < 90 else "red"
            disk_str = f"{info.disk_used} GB / {info.disk_total} GB"
            if info.disk_percent > 0:
                disk_str += f" ([{disk_color}]{info.disk_percent:.1f}%[/{disk_color}])"
            table.add_row("Disk", disk_str)
        
        if info.uptime:
            table.add_row("Uptime", info.uptime)
        
        return Panel(
            table,
            title="[green]💻 System Information[/green]",
            border_style="green",
        )
    
    def create_devices_panel(self) -> Panel:
        """Create discovered devices panel with categorization."""
        if not self.devices:
            return Panel(
                Text("No devices discovered yet. Run network scan to discover devices.", style="dim"),
                title="[magenta]Discovered Devices[/magenta]",
                border_style="magenta",
            )
        
        table = Table(show_header=True, box=None, padding=(0, 1))
        table.add_column("IP", style="cyan", width=15)
        table.add_column("Type", width=10)
        table.add_column("Vendor", style="white", width=20, overflow="fold")
        table.add_column("Hostname", style="dim", width=18, overflow="fold")
        table.add_column("Ports", style="yellow", width=12)
        
        # Sort devices: gateway first, then by category, then by IP
        category_priority = {
            "network": 1,
            "server": 2,
            "printer": 3,
            "client": 4,
            "mobile": 5,
            "iot": 6,
            "unknown": 7,
        }
        
        sorted_devices = sorted(
            self.devices,
            key=lambda d: (
                0 if d.is_gateway else 1,
                category_priority.get(d.category, 99),
                d.ip,
            )
        )
        
        # Show up to 15 devices
        for device in sorted_devices[:15]:
            ip_display = device.ip
            if device.is_gateway:
                ip_display = f"[bold yellow]{device.ip}[/bold yellow] ⭐"
            
            category_icon = get_category_icon(device.category)
            category_color = get_category_color(device.category)
            category_display = f"[{category_color}]{category_icon} {device.category.title()}[/{category_color}]"
            
            vendor_display = device.vendor if device.vendor else "Unknown"
            if len(vendor_display) > 20:
                vendor_display = vendor_display[:17] + "..."
            
            hostname_display = device.hostname if device.hostname else "-"
            if len(hostname_display) > 18:
                hostname_display = hostname_display[:15] + "..."
            
            ports_display = "-"
            if device.open_ports:
                if len(device.open_ports) <= 3:
                    ports_display = ", ".join(str(p) for p in sorted(device.open_ports))
                else:
                    ports_display = f"{len(device.open_ports)} open"
            
            table.add_row(
                ip_display,
                category_display,
                vendor_display,
                hostname_display,
                ports_display,
            )
        
        if len(self.devices) > 15:
            footer_text = f"\n[dim]Showing 15 of {len(self.devices)} devices[/dim]"
        else:
            footer_text = f"\n[dim]Total: {len(self.devices)} device(s)[/dim]"
        
        # Category summary
        category_counts = {}
        for device in self.devices:
            category_counts[device.category] = category_counts.get(device.category, 0) + 1
        
        summary_parts = []
        for cat in ["server", "network", "client", "iot", "printer", "mobile"]:
            if cat in category_counts:
                icon = get_category_icon(cat)
                color = get_category_color(cat)
                summary_parts.append(f"[{color}]{icon} {category_counts[cat]}[/{color}]")
        
        if summary_parts:
            footer_text += "\n[dim]Categories: " + " | ".join(summary_parts) + "[/dim]"
        
        return Panel(
            Text.from_markup(str(table) + footer_text),
            title="[magenta]📡 Discovered Devices[/magenta]",
            border_style="magenta",
        )
    
    def create_security_panel(self) -> Panel:
        """Create security overview panel."""
        if not self.security_issues:
            return Panel(
                Text("✓ No security issues detected", style="green"),
                title="[yellow]Security Overview[/yellow]",
                border_style="green",
            )
        
        table = Table(show_header=True, box=None, padding=(0, 1))
        table.add_column("Severity", width=10)
        table.add_column("Issue", style="white")
        
        # Sort by severity
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        sorted_issues = sorted(
            self.security_issues,
            key=lambda x: severity_order.get(x.get("severity", "low"), 99)
        )
        
        for issue in sorted_issues[:10]:
            severity = issue.get("severity", "low")
            
            if severity == "critical":
                sev_display = "[red bold]CRITICAL[/red bold]"
            elif severity == "high":
                sev_display = "[red]HIGH[/red]"
            elif severity == "medium":
                sev_display = "[yellow]MEDIUM[/yellow]"
            else:
                sev_display = "[cyan]LOW[/cyan]"
            
            table.add_row(sev_display, issue.get("description", "Unknown issue"))
        
        if len(self.security_issues) > 10:
            footer = f"\n[dim]Showing 10 of {len(self.security_issues)} issues[/dim]"
        else:
            footer = f"\n[dim]Total: {len(self.security_issues)} issue(s)[/dim]"
        
        border_color = "red" if any(i.get("severity") in ["critical", "high"] for i in self.security_issues) else "yellow"
        
        return Panel(
            Text.from_markup(str(table) + footer),
            title="[yellow]⚠️ Security Overview[/yellow]",
            border_style=border_color,
        )
    
    def create_layout(self) -> Layout:
        """Create complete dashboard layout."""
        layout = Layout()
        
        # Main structure
        layout.split_column(
            Layout(name="header", size=5),
            Layout(name="top_row"),
            Layout(name="middle_row"),
            Layout(name="bottom_row"),
        )
        
        # Top row: Network and System info side by side
        layout["top_row"].split_row(
            Layout(name="network"),
            Layout(name="system"),
        )
        
        # Middle row: Devices (full width)
        layout["middle_row"].update(Layout(name="devices"))
        
        # Bottom row: Security (full width)
        layout["bottom_row"].update(Layout(name="security"))
        
        # Populate panels
        layout["header"].update(self.create_header())
        layout["network"].update(self.create_network_panel())
        layout["system"].update(self.create_system_panel())
        layout["devices"].update(self.create_devices_panel())
        layout["security"].update(self.create_security_panel())
        
        return layout
    
    def update_network_info(self, info: NetworkInfo) -> None:
        """Update network information."""
        self.network_info = info
        self.last_update = datetime.now()
    
    def update_system_info(self, info: SystemInfo) -> None:
        """Update system information."""
        self.system_info = info
        self.last_update = datetime.now()
    
    def update_devices(self, devices: List[DiscoveredDevice]) -> None:
        """Update discovered devices list."""
        self.devices = devices
        self.last_update = datetime.now()
    
    def update_security_issues(self, issues: List[Dict[str, str]]) -> None:
        """Update security issues list."""
        self.security_issues = issues
        self.last_update = datetime.now()
    
    def render(self) -> None:
        """Render dashboard once."""
        layout = self.create_layout()
        self.console.print(layout)
    
    def run_live(self, duration: Optional[int] = None) -> None:
        """
        Run dashboard in live mode with auto-refresh.
        
        Args:
            duration: Optional duration in seconds (None for indefinite)
        """
        with Live(self.create_layout(), console=self.console, refresh_per_second=1) as live:
            start_time = datetime.now()
            
            try:
                while True:
                    # Update layout
                    live.update(self.create_layout())
                    
                    # Check duration
                    if duration:
                        elapsed = (datetime.now() - start_time).total_seconds()
                        if elapsed >= duration:
                            break
                    
                    # Sleep
                    import time
                    time.sleep(1)
            except KeyboardInterrupt:
                pass


# Import statement for Align
from rich.align import Align
