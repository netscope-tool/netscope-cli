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

    # Print metrics table if available (skip hop_details; shown as separate table)
    if result.metrics:
        metrics_table = Table(show_header=True, box=None, padding=(0, 2))
        metrics_table.add_column("Metric", style="cyan")
        metrics_table.add_column("Value", style="white")

        for key, value in result.metrics.items():
            if key == "hop_details":
                continue
            if key == "open_ports" and isinstance(value, list):
                metrics_table.add_row("Open Ports", ", ".join(str(p) for p in value) if value else "None")
                continue
            if isinstance(value, (list, dict)):
                continue
            metrics_table.add_row(key.replace("_", " ").title(), str(value))

        if metrics_table.row_count > 0:
            console.print(metrics_table)

    # Per-hop table for traceroute
    hop_details = (result.metrics or {}).get("hop_details")
    if isinstance(hop_details, list) and len(hop_details) > 0:
        hops_table = Table(title="Hops", show_header=True, box=None, padding=(0, 2))
        hops_table.add_column("Hop", style="cyan")
        hops_table.add_column("Host", style="white")
        hops_table.add_column("RTT (ms)", style="white")
        for h in hop_details[:20]:  # cap at 20 rows
            host = h.get("host", "—")
            rtt = h.get("rtt_ms", 0)
            rtt_str = f"{rtt:.1f}" if isinstance(rtt, (int, float)) else str(rtt)
            hops_table.add_row(str(h.get("hop", "—")), str(host), rtt_str)
        if len(hop_details) > 20:
            hops_table.add_row("…", f"+{len(hop_details) - 20} more", "")
        console.print()
        console.print(hops_table)

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
    Generate a short, plain-language interpretation of the test result.
    Returns empty string if no interpretation is available.
    """
    metrics = result.metrics or {}

    if result.test_name == "Ping Test":
        loss = metrics.get("packet_loss", 100)
        latency = metrics.get("avg_latency") or 0
        if result.status == "failure":
            return (
                "In plain terms: the host did not respond or the test failed. "
                "Check that your network is working, the address is correct, and that the host is not blocking ping."
            )
        if loss == 100:
            return (
                "In plain terms: none of the test packets came back. "
                "The host might be off, might be blocking this kind of test, or might be unreachable from your network."
            )
        if loss > 0:
            return (
                f"In plain terms: some packets were lost ({loss}%), so the link is a bit unstable. "
                "You might see lag or failed requests. Running the test again or using traceroute can help find where the problem is."
            )
        if latency < 20:
            return (
                "In plain terms: the host is reachable and response time is very good. "
                "Your connection to this target is in great shape."
            )
        if latency < 50:
            return (
                "In plain terms: the host is reachable with normal delay. "
                "Response time is fine for most uses (browsing, video, etc.)."
            )
        if latency < 100:
            return (
                "In plain terms: the host is reachable but a bit slow. "
                "You might notice some delay in real-time apps or games."
            )
        return (
            f"In plain terms: the host answers, but delay is high (around {latency:.0f} ms). "
            "Running a traceroute can show where the slowness is on the path."
        )

    if result.test_name == "Traceroute Test":
        if result.status == "failure":
            return (
                "In plain terms: we could not trace the path to the target. "
                "The target or a router along the way may be down or not replying to this kind of test."
            )
        hop_count = metrics.get("hop_count", 0)
        reached = metrics.get("destination_reached", False)
        if reached and hop_count:
            return (
                f"In plain terms: the path to the target has {hop_count} step(s) (routers), and the destination replied. "
                "If something feels slow, look for a hop where the delay jumps up—that’s often the bottleneck."
            )
        if hop_count:
            return (
                f"In plain terms: we saw {hop_count} hop(s), but the final host may not have replied. "
                "Timeouts near the end often mean the target or a firewall is not answering these probes."
            )
        return (
            "In plain terms: no hops were recorded. "
            "The route might be blocked or the target unreachable."
        )

    if result.test_name == "DNS Lookup":
        if result.status == "failure":
            return (
                "In plain terms: the DNS lookup failed. "
                "Check the hostname spelling, that your DNS is working, and that you have network access."
            )
        resolved = metrics.get("resolved", False)
        ip_count = metrics.get("ip_count", 0)
        if resolved and ip_count:
            return (
                f"In plain terms: the name resolved to {ip_count} address(es). "
                "You can use those IPs to ping or traceroute and test connectivity."
            )
        return (
            "In plain terms: no IP addresses were returned for this name. "
            "The name might be wrong, the domain might not exist, or there could be a DNS or network issue."
        )

    if result.test_name == "Port Scan":
        open_count = metrics.get("open_count", 0)
        total = metrics.get("total_ports", 0)
        if open_count == 0 and total > 0:
            return (
                "In plain terms: no ports accepted a connection in the scanned set. "
                "The host may be filtering these ports, or no services are listening on them."
            )
        if open_count:
            return (
                f"In plain terms: {open_count} of {total} scanned port(s) are open and accepting connections. "
                "Common open ports (e.g. 22, 80, 443) often indicate SSH, HTTP, or HTTPS services."
            )
        return "In plain terms: no ports were scanned (empty port list)."

    return ""


def get_quick_check_interpretation(
    results: Sequence[TestResult],
    target: str,
) -> str:
    """
    Generate a single plain-language explanation for a Quick Network Check run.
    Uses the target and the three results (ping, traceroute, DNS) to tell the user what it all means.
    """
    if len(results) < 3:
        return ""

    ping_r, tr_r, dns_r = results[0], results[1], results[2]
    ping_ok = ping_r.status == "success"
    tr_ok = tr_r.status == "success"
    dns_ok = dns_r.status == "success"
    dns_warn = dns_r.status == "warning"
    metrics_dns = dns_r.metrics or {}
    ip_count = metrics_dns.get("ip_count", 0)
    # Target looks like an IPv4 address (simple check)
    looks_like_ip = (
        len(target.split(".")) == 4
        and all(
            p.isdigit() and 0 <= int(p) <= 255
            for p in target.split(".")
            if p.isdigit()
        )
    )

    parts: list[str] = []

    if ping_ok and tr_ok:
        parts.append(
            f"Your connection to [bold]{target}[/bold] is working: the host responds to ping and the path has a clear route."
        )
    elif ping_ok and not tr_ok:
        parts.append(
            f"You can reach [bold]{target}[/bold] (ping works), but the path could not be fully traced."
        )
    elif not ping_ok:
        parts.append(
            f"[bold]{target}[/bold] did not respond to ping. It may be down, blocking this kind of test, or unreachable from your network."
        )

    if dns_ok and ip_count:
        parts.append(
            f"DNS is working: the name resolved to {ip_count} address(es)."
        )
    elif dns_warn and looks_like_ip:
        parts.append(
            "DNS returned no addresses—that’s normal when you enter an IP address, since DNS is used for hostnames."
        )
    elif dns_warn or (not dns_ok and ping_ok):
        parts.append(
            "DNS did not return any addresses; if you used a hostname, check the spelling and that the domain exists."
        )

    if not parts:
        return "Run completed. Check the table above for each test’s status and metrics."

    return " ".join(parts)


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

    # Plain-language explanation for the whole run
    explanation = get_quick_check_interpretation(results, results[0].target)
    if explanation:
        console.print()
        console.print(Panel(explanation, title="💡 In plain language", border_style="dim"))


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