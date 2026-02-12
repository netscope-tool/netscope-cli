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

    # Interpretation panel (what this means)
    interpretation = get_interpretation(result)
    if interpretation:
        console.print()
        console.print(Panel(interpretation, title="💡 What this means", border_style="dim"))


def get_interpretation(result: TestResult) -> str:
    """
    Generate a short, human-readable interpretation of the test result.
    Returns empty string if no interpretation is available.
    """
    metrics = result.metrics or {}

    if result.test_name == "Ping Test":
        loss = metrics.get("packet_loss", 100)
        latency = metrics.get("avg_latency") or 0
        if result.status == "failure":
            return (
                "❌ Host unreachable or test failed. Check network connection, "
                "verify the target IP/hostname, and ensure the host is not blocking ICMP."
            )
        if loss == 100:
            return (
                "❌ 100% packet loss — host did not respond. It may be down, "
                "blocking ping (ICMP), or unreachable from your network."
            )
        if loss > 0:
            return (
                f"⚠️ Unstable connection — {loss}% packet loss. Some packets did not return; "
                "this can cause lag or failed requests. Try running again or use traceroute to locate the issue."
            )
        if latency < 20:
            return "✅ Excellent connection — host is reachable with very low latency."
        if latency < 50:
            return "✅ Good connection — latency is normal for most applications."
        if latency < 100:
            return "⚠️ Fair connection — you may notice some delay in real-time apps."
        return (
            f"⚠️ High latency ({latency:.0f}ms) — consider using traceroute to find where the delay occurs."
        )

    if result.test_name == "Traceroute Test":
        if result.status == "failure":
            return (
                "❌ Traceroute failed. The target or an intermediate router may be unreachable "
                "or not responding to traceroute probes."
            )
        hop_count = metrics.get("hop_count", 0)
        reached = metrics.get("destination_reached", False)
        if reached and hop_count:
            return (
                f"✅ Path to target has {hop_count} hop(s) and the destination responded. "
                "High latency at a specific hop indicates a bottleneck there."
            )
        if hop_count:
            return (
                f"⚠️ Path shows {hop_count} hop(s) but the final destination may not have responded. "
                "Timeouts near the end often mean the target or a firewall is not replying to probes."
            )
        return "No hops were recorded; the route may be blocked or the target unreachable."

    if result.test_name == "DNS Lookup":
        if result.status == "failure":
            return (
                "❌ DNS lookup failed. Check hostname spelling, DNS server, and network connectivity."
            )
        resolved = metrics.get("resolved", False)
        ip_count = metrics.get("ip_count", 0)
        if resolved and ip_count:
            return (
                f"✅ Hostname resolved to {ip_count} address(es). "
                "You can now ping or traceroute those IPs to test connectivity."
            )
        return (
            "⚠️ No IP addresses returned. The hostname may be wrong, the domain may not exist, "
            "or there may be a DNS server or network issue."
        )

    return ""


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


def get_error_guidance(exception: Exception, test_name: str = "", target: str = "") -> list[str]:
    """
    Return actionable suggestions for common test failures.
    Used to display a "What to try" panel after an error.
    """
    msg = str(exception).lower()
    lines: list[str] = []
    if "timeout" in msg or "timed out" in msg:
        lines.append("• Host may be down, blocking probes, or unreachable.")
        lines.append("• Check your internet connection and the target IP/hostname.")
        if target:
            lines.append(f"• Try: [cyan]netscope traceroute {target}[/cyan] to see where it fails.")
    elif "name" in msg or "resolve" in msg or "dns" in msg:
        lines.append("• Check that the hostname is spelled correctly.")
        lines.append("• Try: [cyan]netscope dns <hostname>[/cyan] to test DNS separately.")
    elif "permission" in msg or "denied" in msg:
        lines.append("• Some tests require elevated permissions on this system.")
    else:
        lines.append("• Verify the target IP or hostname is correct.")
        lines.append("• Run with [cyan]-v[/cyan] for detailed logs.")
    return lines


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