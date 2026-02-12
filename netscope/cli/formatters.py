"""
Rich formatting utilities for CLI output.
"""

from typing import Iterable, Sequence

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from netscope.modules.base import TestResult
from netscope.core.detector import SystemInfo


def print_header() -> None:
    """Print application header."""
    console = Console()

    header_text = """
    ╔═══════════════════════════════════════════════════════╗
    ║                                                       ║
    ║        NetScope - Network Diagnostics Tool            ║
    ║                    Version 0.1.0                      ║
    ║                                                       ║
    ╚═══════════════════════════════════════════════════════╝
    """

    console.print(header_text, style="bold cyan")


def print_system_info(system_info: SystemInfo) -> None:
    """Print detected system information."""
    console = Console()

    table = Table(title="System Information", show_header=False, box=None)
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Operating System", system_info.os_type)
    table.add_row("Platform", system_info.platform)
    table.add_row("Python Version", system_info.python_version)
    table.add_row("Hostname", system_info.hostname)

    console.print()
    console.print(table)
    console.print()


def _status_icon_and_color(status: str) -> tuple[str, str]:
    """Map a status value to icon and color."""
    if status == "success":
        return "✓", "green"
    if status == "warning":
        return "⚠", "yellow"
    return "✗", "red"


def format_test_result(result: TestResult, console: Console) -> None:
    """Format and display a single test result."""

    status_icon, status_color = _status_icon_and_color(result.status)

    # Create panel with results
    panel_title = f"{status_icon} {result.test_name} Results"

    # Build content
    content: list[str] = []
    content.append(f"[bold]Target:[/bold] {result.target}")
    content.append(f"[bold]Status:[/bold] [{status_color}]{result.status.upper()}[/{status_color}]")
    content.append(f"[bold]Duration:[/bold] {result.duration:.2f}s")

    if result.summary:
        content.append(f"\n[bold]Summary:[/bold]\n{result.summary}")

    # Add metrics heading if metrics exist (table printed separately)
    if result.metrics:
        content.append("\n[bold]Metrics:[/bold]")

    panel = Panel(
        "\n".join(content),
        title=panel_title,
        border_style=status_color,
        expand=False,
    )

    console.print()
    console.print(panel)

    # Print metrics table if available
    if result.metrics:
        metrics_table = Table(show_header=True, box=None, padding=(0, 2))
        metrics_table.add_column("Metric", style="cyan")
        metrics_table.add_column("Value", style="white")

        for key, value in result.metrics.items():
            metrics_table.add_row(key.replace("_", " ").title(), str(value))

        console.print(metrics_table)

    # Print raw output if present
    if result.raw_output:
        console.print("\n[bold cyan]Raw Output:[/bold cyan]")
        console.print(Panel(result.raw_output[:500], border_style="dim"))


def format_quick_check_summary(
    results: Sequence[TestResult],
    console: Console,
) -> None:
    """
    Display a compact summary table for Quick Network Check results.

    Each row shows test name, status and a few key metrics if available.
    """
    if not results:
        return

    table = Table(title="Quick Network Check Summary", show_header=True, box=None)
    table.add_column("Test", style="cyan")
    table.add_column("Status", style="white")
    table.add_column("Key Metrics", style="white")

    for result in results:
        status_icon, status_color = _status_icon_and_color(result.status)
        status_text = f"[{status_color}]{status_icon} {result.status.upper()}[/{status_color}]"

        metrics = result.metrics or {}
        key_fields: list[str] = []

        # Heuristic selection of key metrics per test
        if "avg_latency" in metrics:
            key_fields.append(f"avg={metrics['avg_latency']}ms")
        if "packet_loss" in metrics:
            key_fields.append(f"loss={metrics['packet_loss']}%")
        if "hop_count" in metrics:
            key_fields.append(f"hops={metrics['hop_count']}")
        if "ip_count" in metrics:
            key_fields.append(f"IPs={metrics['ip_count']}")

        key_metrics = ", ".join(key_fields) if key_fields else "-"

        table.add_row(result.test_name, status_text, key_metrics)

    console.print()
    console.print(table)


def iter_results(results: TestResult | Iterable[TestResult]) -> Iterable[TestResult]:
    """
    Helper to normalize a single TestResult or an iterable of them.

    Useful for callers that want to support both single-test and multi-test
    outputs without branching on type everywhere.
    """
    if isinstance(results, TestResult):
        yield results
    else:
        yield from results