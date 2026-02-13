"""
Enhanced dashboard for real-time network monitoring.
Minimalistic, terminal-like design inspired by Anthropic's UI principles.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn
from rich.align import Align


@dataclass
class NetworkMetrics:
    """Real-time network metrics."""
    latency_ms: float = 0.0
    packet_loss: float = 0.0
    bandwidth_down: float = 0.0
    bandwidth_up: float = 0.0
    active_connections: int = 0
    devices_discovered: int = 0
    last_update: datetime = None
    
    def __post_init__(self):
        if self.last_update is None:
            self.last_update = datetime.now()


class NetworkDashboard:
    """
    Real-time network monitoring dashboard.
    Clean, minimalistic design with essential metrics.
    """
    
    def __init__(self, console: Optional[Console] = None):
        """
        Initialize dashboard.
        
        Args:
            console: Rich console instance
        """
        self.console = console or Console()
        self.metrics = NetworkMetrics()
        self.test_history: List[Dict[str, Any]] = []
        self.max_history = 10
    
    def create_layout(self) -> Layout:
        """
        Create dashboard layout.
        
        Returns:
            Rich Layout object
        """
        layout = Layout()
        
        # Split into header and body
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3),
        )
        
        # Split body into left and right
        layout["body"].split_row(
            Layout(name="metrics", ratio=1),
            Layout(name="status", ratio=1),
        )
        
        return layout
    
    def update_metrics(self, metrics: NetworkMetrics) -> None:
        """
        Update dashboard metrics.
        
        Args:
            metrics: New metrics to display
        """
        self.metrics = metrics
    
    def add_test_result(self, test_name: str, status: str, duration: float) -> None:
        """
        Add test result to history.
        
        Args:
            test_name: Name of the test
            status: Test status (success, warning, error)
            duration: Test duration in seconds
        """
        self.test_history.insert(0, {
            "test_name": test_name,
            "status": status,
            "duration": duration,
            "timestamp": datetime.now(),
        })
        
        # Keep only recent history
        if len(self.test_history) > self.max_history:
            self.test_history = self.test_history[:self.max_history]
    
    def render_header(self) -> Panel:
        """Render dashboard header."""
        title = Text("NetScope Dashboard", style="bold cyan")
        subtitle = Text(f"Last updated: {self.metrics.last_update.strftime('%Y-%m-%d %H:%M:%S')}", style="dim")
        
        content = Group(
            Align.center(title),
            Align.center(subtitle),
        )
        
        return Panel(content, border_style="cyan", padding=(0, 1))
    
    def render_metrics(self) -> Panel:
        """Render network metrics panel."""
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")
        
        # Latency with color coding
        latency_color = self._get_latency_color(self.metrics.latency_ms)
        table.add_row(
            "Latency",
            f"[{latency_color}]{self.metrics.latency_ms:.1f} ms[/{latency_color}]"
        )
        
        # Packet loss with color coding
        loss_color = self._get_packet_loss_color(self.metrics.packet_loss)
        table.add_row(
            "Packet Loss",
            f"[{loss_color}]{self.metrics.packet_loss:.1f}%[/{loss_color}]"
        )
        
        # Bandwidth
        table.add_row(
            "Download",
            f"[green]{self.metrics.bandwidth_down:.1f} Mbps[/green]"
        )
        table.add_row(
            "Upload",
            f"[green]{self.metrics.bandwidth_up:.1f} Mbps[/green]"
        )
        
        # Connections and devices
        table.add_row(
            "Active Connections",
            f"[yellow]{self.metrics.active_connections}[/yellow]"
        )
        table.add_row(
            "Devices Discovered",
            f"[magenta]{self.metrics.devices_discovered}[/magenta]"
        )
        
        return Panel(
            table,
            title="[bold]Network Metrics[/bold]",
            border_style="blue",
            padding=(1, 2),
        )
    
    def render_status(self) -> Panel:
        """Render test history and status panel."""
        if not self.test_history:
            content = Text("No tests run yet", style="dim italic")
            return Panel(
                Align.center(content, vertical="middle"),
                title="[bold]Recent Tests[/bold]",
                border_style="blue",
                padding=(1, 2),
            )
        
        table = Table(show_header=True, box=None, padding=(0, 1))
        table.add_column("Test", style="cyan", no_wrap=True)
        table.add_column("Status", justify="center")
        table.add_column("Duration", justify="right", style="dim")
        
        for test in self.test_history[:5]:  # Show only 5 most recent
            status_icon = self._get_status_icon(test["status"])
            table.add_row(
                test["test_name"][:20],  # Truncate long names
                status_icon,
                f"{test['duration']:.2f}s"
            )
        
        return Panel(
            table,
            title="[bold]Recent Tests[/bold]",
            border_style="blue",
            padding=(1, 2),
        )
    
    def render_footer(self) -> Panel:
        """Render dashboard footer with controls."""
        controls = Text.assemble(
            ("Press ", "dim"),
            ("Q", "bold cyan"),
            (" to quit  ", "dim"),
            ("R", "bold cyan"),
            (" to refresh  ", "dim"),
            ("H", "bold cyan"),
            (" for help", "dim"),
        )
        
        return Panel(
            Align.center(controls),
            border_style="cyan",
            padding=(0, 1),
        )
    
    def render(self, layout: Layout) -> None:
        """
        Render dashboard to layout.
        
        Args:
            layout: Layout to render to
        """
        layout["header"].update(self.render_header())
        layout["metrics"].update(self.render_metrics())
        layout["status"].update(self.render_status())
        layout["footer"].update(self.render_footer())
    
    def run(self, duration: int = 60) -> None:
        """
        Run dashboard in live mode.
        
        Args:
            duration: How long to run (seconds), 0 for indefinite
        """
        layout = self.create_layout()
        
        start_time = time.time()
        
        with Live(layout, console=self.console, refresh_per_second=2, screen=True) as live:
            while True:
                # Update metrics (in real implementation, fetch from network)
                self.metrics.last_update = datetime.now()
                
                # Render dashboard
                self.render(layout)
                live.update(layout)
                
                # Check duration
                if duration > 0 and time.time() - start_time > duration:
                    break
                
                time.sleep(0.5)
    
    def _get_latency_color(self, latency: float) -> str:
        """Get color for latency value."""
        if latency < 20:
            return "green"
        elif latency < 50:
            return "yellow"
        elif latency < 100:
            return "orange"
        else:
            return "red"
    
    def _get_packet_loss_color(self, loss: float) -> str:
        """Get color for packet loss value."""
        if loss < 1:
            return "green"
        elif loss < 5:
            return "yellow"
        else:
            return "red"
    
    def _get_status_icon(self, status: str) -> str:
        """Get icon for test status."""
        if status == "success":
            return "[green]✓[/green]"
        elif status == "warning":
            return "[yellow]⚠[/yellow]"
        elif status == "error":
            return "[red]✗[/red]"
        else:
            return "[dim]?[/dim]"


class DeviceTable:
    """
    Enhanced device table with sorting and filtering.
    """
    
    def __init__(self, devices: List[Dict[str, Any]]):
        """
        Initialize device table.
        
        Args:
            devices: List of device dictionaries
        """
        self.devices = devices
    
    def render(
        self,
        sort_by: str = "ip",
        filter_vendor: Optional[str] = None,
        filter_type: Optional[str] = None,
    ) -> Table:
        """
        Render device table.
        
        Args:
            sort_by: Column to sort by (ip, mac, vendor, type)
            filter_vendor: Filter by vendor name
            filter_type: Filter by device type
            
        Returns:
            Rich Table object
        """
        # Filter devices
        filtered = self.devices
        if filter_vendor:
            filtered = [d for d in filtered if filter_vendor.lower() in d.get("vendor", "").lower()]
        if filter_type:
            filtered = [d for d in filtered if filter_type.lower() in d.get("device_type", "").lower()]
        
        # Sort devices
        if sort_by == "ip":
            filtered.sort(key=lambda d: self._ip_to_int(d.get("ip", "0.0.0.0")))
        elif sort_by in ["mac", "vendor", "device_type"]:
            filtered.sort(key=lambda d: d.get(sort_by, ""))
        
        # Create table
        table = Table(
            title=f"[bold cyan]Discovered Devices[/bold cyan] ({len(filtered)} devices)",
            show_header=True,
            header_style="bold cyan",
            border_style="blue",
            padding=(0, 1),
        )
        
        table.add_column("IP Address", style="cyan", no_wrap=True)
        table.add_column("MAC Address", style="yellow", no_wrap=True)
        table.add_column("Vendor", style="green")
        table.add_column("Device Type", style="magenta")
        table.add_column("Interface", style="dim")
        
        for device in filtered:
            table.add_row(
                device.get("ip", "N/A"),
                device.get("mac", "N/A"),
                device.get("vendor", "Unknown"),
                device.get("device_type", "Unknown"),
                device.get("interface", "N/A"),
            )
        
        return table
    
    def _ip_to_int(self, ip: str) -> int:
        """Convert IP address to integer for sorting."""
        try:
            parts = ip.split(".")
            return (int(parts[0]) << 24) + (int(parts[1]) << 16) + (int(parts[2]) << 8) + int(parts[3])
        except:
            return 0


class TestProgressDisplay:
    """
    Enhanced progress display for running tests.
    """
    
    def __init__(self, console: Optional[Console] = None):
        """
        Initialize progress display.
        
        Args:
            console: Rich console instance
        """
        self.console = console or Console()
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=40),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=self.console,
        )
    
    def run_with_progress(
        self,
        test_name: str,
        total_steps: int,
        step_callback: callable,
    ) -> Any:
        """
        Run test with progress display.
        
        Args:
            test_name: Name of the test
            total_steps: Total number of steps
            step_callback: Callback function that yields progress
            
        Returns:
            Test result
        """
        with self.progress:
            task = self.progress.add_task(f"Running {test_name}...", total=total_steps)
            
            result = None
            for completed in step_callback():
                self.progress.update(task, completed=completed)
                if isinstance(completed, tuple):
                    completed, result = completed
            
            return result
