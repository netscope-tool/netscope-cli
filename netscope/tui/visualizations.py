"""
Terminal-based visualizations for network data.
ASCII/Unicode graphs and charts for latency, bandwidth, and other metrics.
"""

from __future__ import annotations

from typing import List, Optional, Tuple
from dataclasses import dataclass

from rich.console import Console
from rich.panel import Panel
from rich.text import Text


@dataclass
class DataPoint:
    """Single data point for visualization."""
    value: float
    label: str = ""
    timestamp: Optional[str] = None


class Sparkline:
    """
    Inline sparkline graph for showing trends.
    """
    
    # Unicode block characters for sparklines
    BLOCKS = ['▁', '▂', '▃', '▄', '▅', '▆', '▇', '█']
    
    @classmethod
    def render(
        cls,
        values: List[float],
        width: Optional[int] = None,
        min_val: Optional[float] = None,
        max_val: Optional[float] = None,
    ) -> str:
        """
        Render sparkline from values.
        
        Args:
            values: List of numeric values
            width: Optional width (defaults to len(values))
            min_val: Minimum value for scaling
            max_val: Maximum value for scaling
            
        Returns:
            String with sparkline characters
        """
        if not values:
            return ""
        
        # Determine min/max for scaling
        if min_val is None:
            min_val = min(values)
        if max_val is None:
            max_val = max(values)
        
        # Avoid division by zero
        if max_val == min_val:
            return cls.BLOCKS[0] * len(values)
        
        # Sample values if width is specified
        if width and width < len(values):
            step = len(values) / width
            values = [values[int(i * step)] for i in range(width)]
        
        # Scale values to block indices
        sparkline = ""
        for val in values:
            normalized = (val - min_val) / (max_val - min_val)
            block_idx = min(int(normalized * len(cls.BLOCKS)), len(cls.BLOCKS) - 1)
            sparkline += cls.BLOCKS[block_idx]
        
        return sparkline


class BarChart:
    """
    Horizontal bar chart for comparing values.
    """
    
    @classmethod
    def render(
        cls,
        data: List[DataPoint],
        width: int = 40,
        show_values: bool = True,
        color: str = "cyan",
    ) -> Text:
        """
        Render horizontal bar chart.
        
        Args:
            data: List of data points
            width: Width of bars
            show_values: Show numeric values
            color: Bar color
            
        Returns:
            Rich Text object with chart
        """
        if not data:
            return Text("No data", style="dim")
        
        # Find max value for scaling
        max_val = max(d.value for d in data)
        if max_val == 0:
            max_val = 1
        
        # Find max label length for alignment
        max_label_len = max(len(d.label) for d in data)
        
        # Build chart
        lines = []
        for point in data:
            # Label (right-aligned)
            label = point.label.rjust(max_label_len)
            
            # Bar
            bar_length = int((point.value / max_val) * width)
            bar = "█" * bar_length
            
            # Value
            value_str = f" {point.value:.1f}" if show_values else ""
            
            # Combine
            line = f"{label} │ [{color}]{bar}[/{color}]{value_str}"
            lines.append(line)
        
        return Text.from_markup("\n".join(lines))


class LineGraph:
    """
    ASCII line graph for time-series data.
    """
    
    @classmethod
    def render(
        cls,
        data: List[DataPoint],
        height: int = 10,
        width: int = 60,
        show_axes: bool = True,
    ) -> str:
        """
        Render ASCII line graph.
        
        Args:
            data: List of data points
            height: Graph height in characters
            width: Graph width in characters
            show_axes: Show X and Y axes
            
        Returns:
            Multi-line string with graph
        """
        if not data:
            return "No data"
        
        # Extract values
        values = [d.value for d in data]
        
        # Scale values to height
        min_val = min(values)
        max_val = max(values)
        value_range = max_val - min_val
        
        if value_range == 0:
            value_range = 1
        
        # Create grid
        grid = [[' ' for _ in range(width)] for _ in range(height)]
        
        # Sample data to fit width
        if len(values) > width:
            step = len(values) / width
            sampled_values = [values[int(i * step)] for i in range(width)]
        else:
            sampled_values = values + [values[-1]] * (width - len(values))
        
        # Plot points
        for x, val in enumerate(sampled_values):
            if x >= width:
                break
            
            # Scale to grid height
            y = int(((val - min_val) / value_range) * (height - 1))
            y = height - 1 - y  # Flip Y axis
            
            if 0 <= y < height:
                grid[y][x] = '●'
        
        # Connect points with lines
        for x in range(len(sampled_values) - 1):
            y1 = int(((sampled_values[x] - min_val) / value_range) * (height - 1))
            y2 = int(((sampled_values[x + 1] - min_val) / value_range) * (height - 1))
            
            y1 = height - 1 - y1
            y2 = height - 1 - y2
            
            # Draw line between points
            if y1 != y2:
                start_y = min(y1, y2)
                end_y = max(y1, y2)
                for y in range(start_y, end_y + 1):
                    if 0 <= y < height and 0 <= x < width:
                        if grid[y][x] == ' ':
                            grid[y][x] = '│' if abs(y2 - y1) > 1 else '─'
        
        # Convert grid to string
        lines = []
        for i, row in enumerate(grid):
            # Add Y axis labels
            if show_axes:
                y_val = max_val - (i / (height - 1)) * value_range
                label = f"{y_val:6.1f} │ "
            else:
                label = ""
            
            lines.append(label + ''.join(row))
        
        # Add X axis
        if show_axes:
            lines.append(" " * 8 + "└" + "─" * width)
        
        return "\n".join(lines)


class NetworkTopology:
    """
    ASCII network topology diagram.
    """
    
    @classmethod
    def render_simple(
        cls,
        devices: List[dict],
        gateway: Optional[str] = None,
    ) -> str:
        """
        Render simple network topology.
        
        Args:
            devices: List of device dictionaries
            gateway: Gateway IP address
            
        Returns:
            ASCII topology diagram
        """
        lines = []
        
        # Internet/Gateway
        lines.append("        ┌─────────┐")
        lines.append("        │ Internet│")
        lines.append("        └────┬────┘")
        lines.append("             │")
        
        # Gateway/Router
        if gateway:
            lines.append("        ┌────┴────┐")
            lines.append(f"        │ Gateway │  {gateway}")
            lines.append("        └────┬────┘")
        else:
            lines.append("        ┌────┴────┐")
            lines.append("        │ Router  │")
            lines.append("        └────┬────┘")
        
        lines.append("             │")
        lines.append("     ┌───────┼───────┐")
        lines.append("     │       │       │")
        
        # Devices (show up to 3 in diagram)
        device_lines = ["     ", "     ", "     "]
        
        for i, device in enumerate(devices[:3]):
            ip = device.get("ip", "N/A")
            dtype = device.get("device_type", "Device")[:8]
            
            if i == 0:
                device_lines[0] += f"┌──────┐"
                device_lines[1] += f"│{dtype:^6}│"
                device_lines[2] += f"└──────┘"
            elif i == 1:
                device_lines[0] += f"  ┌──────┐"
                device_lines[1] += f"  │{dtype:^6}│"
                device_lines[2] += f"  └──────┘"
            elif i == 2:
                device_lines[0] += f"  ┌──────┐"
                device_lines[1] += f"  │{dtype:^6}│"
                device_lines[2] += f"  └──────┘"
        
        lines.extend(device_lines)
        
        # Show count if more devices
        if len(devices) > 3:
            lines.append(f"\n     ... and {len(devices) - 3} more devices")
        
        return "\n".join(lines)


class LatencyHeatmap:
    """
    Color-coded heatmap for latency values.
    """
    
    # Color codes for different latency ranges
    COLORS = {
        "excellent": "green",
        "good": "cyan",
        "fair": "yellow",
        "poor": "orange",
        "bad": "red",
    }
    
    @classmethod
    def get_latency_category(cls, latency_ms: float) -> str:
        """Get latency category."""
        if latency_ms < 20:
            return "excellent"
        elif latency_ms < 50:
            return "good"
        elif latency_ms < 100:
            return "fair"
        elif latency_ms < 200:
            return "poor"
        else:
            return "bad"
    
    @classmethod
    def render(
        cls,
        targets: List[str],
        latencies: List[float],
    ) -> Text:
        """
        Render latency heatmap.
        
        Args:
            targets: List of target names
            latencies: List of latency values
            
        Returns:
            Rich Text with color-coded heatmap
        """
        text = Text()
        
        for target, latency in zip(targets, latencies):
            category = cls.get_latency_category(latency)
            color = cls.COLORS[category]
            
            text.append(f"{target:20} ", style="cyan")
            text.append("█" * int(latency / 10), style=color)
            text.append(f" {latency:.1f}ms\n", style="dim")
        
        return text


def create_summary_panel(
    title: str,
    metrics: dict,
    status: str = "success",
) -> Panel:
    """
    Create a summary panel with key metrics.
    
    Args:
        title: Panel title
        metrics: Dictionary of metrics
        status: Overall status (success, warning, error)
        
    Returns:
        Rich Panel object
    """
    # Status icon and color
    if status == "success":
        icon = "✓"
        color = "green"
    elif status == "warning":
        icon = "⚠"
        color = "yellow"
    else:
        icon = "✗"
        color = "red"
    
    # Build content
    lines = []
    for key, value in metrics.items():
        # Format key (convert snake_case to Title Case)
        formatted_key = key.replace("_", " ").title()
        lines.append(f"[cyan]{formatted_key}:[/cyan] [white]{value}[/white]")
    
    content = Text.from_markup("\n".join(lines))
    
    return Panel(
        content,
        title=f"[{color}]{icon}[/{color}] [bold]{title}[/bold]",
        border_style=color,
        padding=(1, 2),
    )
