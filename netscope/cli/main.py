"""
Main CLI application using Typer.
"""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path
from typing import Iterable, List, Optional

import questionary
import typer
from questionary import Choice
from rich.console import Console
from rich.live import Live
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.spinner import Spinner

from netscope.cli.formatters import (
    format_quick_check_summary,
    format_test_result,
    get_error_guidance,
    iter_results,
    print_header,
    print_network_status,
    print_system_info,
)
from netscope.core.config import AppConfig
from netscope.core.detector import SystemDetector
from netscope.core.executor import TestExecutor
from netscope.modules.arp_scan_enhanced import ARPScanTestEnhanced
from netscope.modules.bandwidth import (
    BandwidthTest,
    is_speedtest_available,
    list_speedtest_servers,
    try_install_speedtest_cli,
)
from netscope.modules.connectivity import PingTest, TracerouteTest
from netscope.modules.dns import DNSTest
from netscope.modules.mtr import MTRTest
from netscope.modules.nmap_scan import (
    NMAP_VULN_SCRIPT_EXPRESSION,
    NmapScanTest,
    normalize_targets,
    validate_vulnerability_scope,
)
from netscope.modules.ping_sweep import PingSweepTest
from netscope.modules.ports import PORT_PRESET_TOP20, PORT_PRESET_TOP100, PortScanTest
from netscope.modules.website_audit import WebsiteAuditTest
from netscope.parallel.executor import BatchTestRunner, ParallelTestConfig
from netscope.storage.csv_handler import CSVHandler
from netscope.storage.logger import setup_logging
from netscope.tui.terminal import exit_requested
from netscope.tui.theme import NETSCOPE_THEME

app = typer.Typer(
    name="netscope",
    help="Network Diagnostics & Reporting Tool",
    add_completion=False,
)

console = Console(theme=NETSCOPE_THEME)


def _init_context(output_dir: Optional[Path], verbose: bool):
    """
    Initialize shared objects: config, logger, system info, detector and executor factory.
    Uses optional config file (~/.netscope.yaml or ./.netscope.yaml) for defaults when CLI does not set values.
    """
    from netscope.core.config import load_config_file
    file_cfg = load_config_file()
    resolved_output = output_dir if output_dir is not None else file_cfg.get("output_dir") or Path("output")
    if isinstance(resolved_output, str):
        resolved_output = Path(resolved_output)
    resolved_verbose = verbose or file_cfg.get("verbose", False)
    config = AppConfig(
        output_dir=resolved_output,
        verbose=resolved_verbose,
    )

    logger = setup_logging(config.output_dir, verbose)
    detector = SystemDetector()
    system_info = detector.detect_system()

    return config, logger, detector, system_info


def _create_run_artifacts(config: AppConfig, logger, test_name: str):
    """
    Create per-run artifacts: directory, CSV handler and executor.
    """
    test_run_dir = config.create_test_run_dir(test_name)
    logger.info(f"Created test run directory: {test_run_dir}")

    csv_handler = CSVHandler(test_run_dir / "results.csv")
    executor = TestExecutor(SystemDetector().detect_system(), logger)

    return test_run_dir, csv_handler, executor


def _save_raw_output(test_run_dir: Path, filename: str, raw_output: Optional[str]) -> None:
    """Preserve tool evidence alongside structured CSV metrics when present."""
    if not raw_output:
        return
    raw_dir = test_run_dir / "raw_output"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / filename).write_text(raw_output, encoding="utf-8", errors="replace")


def _recent_run_directories(output_dir: Path, limit: int = 20) -> list[Path]:
    """Return recent result folders for the interactive report picker."""
    if limit <= 0 or not output_dir.is_dir():
        return []
    runs = [
        path for path in output_dir.iterdir()
        if path.is_dir() and (path / "results.csv").is_file()
    ]
    return sorted(runs, key=lambda path: path.name, reverse=True)[:limit]


def _output_results_json(results: Iterable, pretty: bool = True) -> None:
    """
    Print one or more TestResult objects as JSON to the console.
    """
    serializable = [
        r.model_dump(mode="json")
        for r in iter_results(results)
    ]
    if len(serializable) == 1:
        payload = serializable[0]
    else:
        payload = serializable

    text = json.dumps(payload, indent=2 if pretty else None)
    console.print(text)


def _run_interactive(
    output_dir: Optional[Path],
    verbose: bool,
) -> None:
    """Run the interactive menu (default `netscope` / `netscope main`)."""
    # Print header
    print_header()

    # Initialize configuration and context
    config, logger, detector, system_info = _init_context(output_dir, verbose)

    # First-run welcome (once per machine)
    _first_run_welcome(config.output_dir)

    # Print system information
    print_system_info(system_info)

    # Network status widget (right-aligned: colored dot + local/public IP)
    print_network_status(console)

    # Check for required tools
    console.print("\n[bold cyan]Checking for required tools...[/bold cyan]")

    missing_tools = detector.check_required_tools(["ping", "traceroute", "dig"])

    if missing_tools:
        console.print("\n[bold yellow]⚠️  Missing Tools:[/bold yellow]")
        for tool in missing_tools:
            console.print(f"  • {tool.name}: {tool.suggestion}")

        if not questionary.confirm(
            "Continue anyway?",
            default=False,
        ).ask():
            logger.warning("User cancelled due to missing tools")
            raise typer.Exit(1)
    else:
        console.print("[bold green]✓ All required tools available[/bold green]")

    # Main menu loop
    while True:
        choice = show_main_menu()

        if choice == "Exit":
            console.print("\n[bold cyan]👋 Thank you for using NetScope![/bold cyan]")
            logger.info("NetScope exited normally")
            break

        if choice == "Dashboard":
            # Launch the aggregated dashboard
            from netscope.cli.dashboard_cmd import run_aggregated_dashboard

            console.print("\n[bold cyan]Launching NetScope Aggregated Dashboard…[/bold cyan]\n")
            
            # Ask if user wants to scan ports
            scan_ports = questionary.confirm(
                "Scan ports on discovered devices? (slower but more detailed)",
                default=True
            ).ask()
            
            if scan_ports is None:
                continue
            
            try:
                run_aggregated_dashboard(
                    console=console,
                    scan_ports=scan_ports,
                    live_mode=False,
                )
            except KeyboardInterrupt:
                console.print("\n[cyan]Dashboard stopped.[/cyan]")
            
            console.print("\n[dim]Press Enter to return to menu...[/dim]")
            input()
            continue

        if choice == "Generate HTML Report":
            run_dirs = _recent_run_directories(config.output_dir)
            if not run_dirs:
                console.print("[dim]No saved test runs are available to report yet.[/dim]")
                continue
            report_choices = []
            for run_dir in run_dirs:
                label = run_dir.name
                try:
                    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
                    label = " · ".join(filter(None, [
                        str(metadata.get("test_type", "Run")),
                        str(metadata.get("target", "")),
                        run_dir.name,
                    ]))
                except (OSError, json.JSONDecodeError):
                    pass
                report_choices.append(Choice(label, value=run_dir))
            selected_run = questionary.select("Choose a saved run to report:", choices=report_choices).ask()
            if selected_run is None:
                continue
            try:
                from netscope.report.html_report import generate_html_report
                report_path = generate_html_report(selected_run)
                console.print(f"[green]HTML report generated:[/green] {report_path}")
            except (OSError, ValueError) as exc:
                console.print(f"[red]Could not generate the report:[/red] {exc}")
            continue

        # Determine target / input per test
        target: Optional[str] = None

        if choice in {"Ping Test", "Traceroute Test", "DNS Lookup", "Port Scan", "Nmap Scan", "Quick Network Check", "MTR Route Quality", "Website Exposure Audit"}:
            console.print(
                "[dim]  Examples: 8.8.8.8, 1.1.1.1, google.com, example.com[/dim]"
            )
            console.print(
                "[dim]  Shortcuts: localhost, gateway, dns[/dim]"
            )
            target_input = questionary.text(
                "Enter target IP/hostname:",
                validate=lambda x: len(x) > 0,
            ).ask()
            if not target_input:
                continue
            target = _resolve_target(target_input)
        elif choice == "ARP Scan":
            # Local-only scan; no target needed
            target = "local"
        elif choice == "Ping Sweep":
            console.print("\n[dim]Enter a CIDR range (e.g., 192.168.1.0/24). Maximum /24 (256 hosts).[/dim]\n")
            cidr = questionary.text(
                "Enter CIDR range:",
                validate=lambda x: len(x) > 0 and "/" in x,
            ).ask()
            if not cidr:
                continue
            target = cidr  # reuse as 'target' label for consistency
        elif choice == "Speedtest":
            server_opt = questionary.select(
                "Server:",
                choices=[
                    Choice("Auto (closest server)", value="auto"),
                    Choice("List servers and choose by ID", value="list"),
                ],
            ).ask()
            if not server_opt:
                continue
            if server_opt == "list":
                servers = list_speedtest_servers()
                if not servers:
                    console.print("[yellow]speedtest-cli not found or failed. Install with: pip install speedtest-cli[/yellow]")
                    continue
                from rich.table import Table as RichTable
                tbl = RichTable(show_header=True, header_style="bold")
                tbl.add_column("ID", style="cyan")
                tbl.add_column("Sponsor / Location", style="white")
                for s in servers[:40]:
                    tbl.add_row(s["id"], s["label"])
                console.print(tbl)
                target = questionary.text("Enter server ID (or leave blank for auto):").ask() or "auto"
            else:
                target = "auto"

        # Create test run directory and helpers
        test_run_dir = config.create_test_run_dir(choice.lower().replace(" ", "_"))
        logger.info(f"Created test run directory: {test_run_dir}")

        csv_handler = CSVHandler(test_run_dir / "results.csv")
        executor = TestExecutor(system_info, logger)

        # Execute test based on choice
        if target is not None and choice not in {"ARP Scan", "Ping Sweep"}:
            if choice == "Speedtest" and target == "auto":
                console.print(f"\n[bold cyan]Running {choice} (auto server)...[/bold cyan]\n")
            else:
                console.print(f"\n[bold cyan]Running {choice} on {target}...[/bold cyan]\n")
        else:
            console.print(f"\n[bold cyan]Running {choice}...[/bold cyan]\n")

        try:
            live_session = None
            if choice == "Ping Test":
                # Ask if user wants advanced options
                from netscope.cli.advanced_options import prompt_mode_selection, prompt_ping_options
                from netscope.modules.connectivity_enhanced import PingTestEnhanced
                
                use_advanced = questionary.confirm(
                    "Use advanced ping options?",
                    default=False
                ).ask()
                
                if use_advanced:
                    simple_mode = prompt_mode_selection()
                    ping_options = prompt_ping_options(simple_mode)
                    test = PingTestEnhanced(executor, csv_handler)
                    _result_holder: list = []
                    def _run():
                        _result_holder.append(test.run(target, ping_options))
                    _t = threading.Thread(target=_run)
                    _t.start()
                    with Live(Spinner("dots", text=f"Pinging ({ping_options.count} packets)…"), console=console, refresh_per_second=8):
                        while _t.is_alive():
                            _t.join(timeout=0.05)
                else:
                    test = PingTest(executor, csv_handler)
                    _result_holder: list = []
                    def _run():
                        _result_holder.append(test.run(target))
                    _t = threading.Thread(target=_run)
                    _t.start()
                    with Live(Spinner("dots", text="Pinging…"), console=console, refresh_per_second=8):
                        while _t.is_alive():
                            _t.join(timeout=0.05)
                result = _result_holder[0]
                results = [result]
            elif choice == "Traceroute Test":
                test = TracerouteTest(executor, csv_handler)
                _result_holder = []
                def _run():
                    _result_holder.append(test.run(target))
                _t = threading.Thread(target=_run)
                _t.start()
                with Live(Spinner("dots", text="Tracing route…"), console=console, refresh_per_second=8):
                    while _t.is_alive():
                        _t.join(timeout=0.05)
                result = _result_holder[0]
                results = [result]
            elif choice == "DNS Lookup":
                # Ask if user wants advanced options
                from netscope.cli.advanced_options import prompt_dns_options
                from netscope.modules.dns_enhanced import DNSTestEnhanced
                
                use_advanced = questionary.confirm(
                    "Use advanced DNS options? (Query types, custom DNS server, etc.)",
                    default=False
                ).ask()
                
                if use_advanced:
                    simple_mode = prompt_mode_selection()
                    dns_options = prompt_dns_options(simple_mode)
                    test = DNSTestEnhanced(executor, csv_handler)
                    _result_holder = []
                    def _run():
                        _result_holder.append(test.run(target, dns_options))
                    _t = threading.Thread(target=_run)
                    _t.start()
                    with Live(Spinner("dots", text=f"Querying {dns_options.record_type} records…"), console=console, refresh_per_second=8):
                        while _t.is_alive():
                            _t.join(timeout=0.05)
                else:
                    test = DNSTest(executor, csv_handler)
                    _result_holder = []
                    def _run():
                        _result_holder.append(test.run(target))
                    _t = threading.Thread(target=_run)
                    _t.start()
                    with Live(Spinner("dots", text="Resolving DNS…"), console=console, refresh_per_second=8):
                        while _t.is_alive():
                            _t.join(timeout=0.05)
                result = _result_holder[0]
                results = [result]
            elif choice == "Port Scan":
                preset_choice = questionary.select(
                    "Port preset:",
                    choices=[
                        Choice("Top 20 common ports", value="top20"),
                        Choice("Top 100 common ports", value="top100"),
                    ],
                ).ask()
                preset = preset_choice or "top20"
                
                # Ask if user wants advanced options
                from netscope.cli.advanced_options import prompt_port_scan_options
                from netscope.modules.ports_enhanced import PortScanTestEnhanced
                
                use_advanced = questionary.confirm(
                    "Use advanced port scan options? (Service detection, timeout, etc.)",
                    default=False
                ).ask()
                
                if use_advanced:
                    simple_mode = prompt_mode_selection()
                    port_options = prompt_port_scan_options(simple_mode)
                    ports = PORT_PRESET_TOP100 if preset == "top100" else PORT_PRESET_TOP20
                    total_ports = len(ports)
                    test = PortScanTestEnhanced(executor, csv_handler)
                    _result_holder: list = []
                    with Progress(
                        TextColumn("[bold cyan]{task.description}[/bold cyan]"),
                        BarColumn(bar_width=24),
                        TaskProgressColumn(),
                        console=console,
                        transient=True,
                    ) as progress:
                        task = progress.add_task("Scanning ports…", total=total_ports)
                        def _run():
                            def _cb(completed: int, _total: int) -> None:
                                progress.update(task, completed=completed)
                            _result_holder.append(test.run(target, ports, port_options, _cb))
                        _t = threading.Thread(target=_run)
                        _t.start()
                        while _t.is_alive():
                            _t.join(timeout=0.05)
                else:
                    total_ports = len(PORT_PRESET_TOP100 if preset == "top100" else PORT_PRESET_TOP20)
                    test = PortScanTest(executor, csv_handler)
                    _result_holder: list = []
                    with Progress(
                        TextColumn("[bold cyan]{task.description}[/bold cyan]"),
                        BarColumn(bar_width=24),
                        TaskProgressColumn(),
                        console=console,
                        transient=True,
                    ) as progress:
                        task = progress.add_task("Scanning ports…", total=total_ports)
                        def _run():
                            def _cb(completed: int, _total: int) -> None:
                                progress.update(task, completed=completed)
                            _result_holder.append(test.run(target, preset=preset, progress_callback=_cb))
                        _t = threading.Thread(target=_run)
                        _t.start()
                        while _t.is_alive():
                            _t.join(timeout=0.05)
                result = _result_holder[0]
                results = [result]
            elif choice == "Nmap Scan":
                console.print("\n[dim]Note: This test requires the external `nmap` tool to be installed.[/dim]\n")
                profile = questionary.select(
                    "Nmap scan profile:",
                    choices=[
                        Choice("Service details · light version probe", value="service"),
                        Choice("Quick TCP inventory · no version probe", value="connect"),
                        Choice("Top 20 UDP ports · slower, privilege may be required", value="udp"),
                        Choice("Safe vulnerability checks · top 20 TCP ports, no exploit/DoS scripts", value="vuln"),
                    ],
                    default="service",
                ).ask()
                if profile is None:
                    continue
                if profile == "vuln":
                    try:
                        validate_vulnerability_scope([target])
                    except ValueError as exc:
                        console.print(f"[red]Invalid vulnerability-scan scope: {exc}[/red]")
                        continue
                    if not questionary.confirm(
                        "Confirm you are authorized to run vulnerability checks against this target?", default=False,
                    ).ask():
                        console.print("[dim]Vulnerability scan cancelled; no scan was started.[/dim]")
                        continue
                test = NmapScanTest(executor, csv_handler)
                from netscope.tui.nmap_live import run_live_nmap_dashboard
                live_nmap = run_live_nmap_dashboard(
                    [target], test, console, profile=profile,
                    timeout=600 if profile == "vuln" else 120,
                )
                result = live_nmap.result
                _save_raw_output(test_run_dir, "nmap.xml", result.raw_output)
                results = [result]
            elif choice == "MTR Route Quality":
                cycles = questionary.select(
                    "How many MTR cycles per live refresh?",
                    choices=[Choice("3 cycles · faster refresh", value=3), Choice("5 cycles · standard", value=5), Choice("10 cycles · steadier sample", value=10)],
                    default=5,
                ).ask()
                if cycles is None:
                    continue
                test = MTRTest(executor, csv_handler)
                if sys.stdin.isatty() and sys.stdout.isatty():
                    from netscope.tui.mtr_live import run_live_mtr_dashboard
                    console.print("[dim]Entering the live route dashboard · press q to return.[/dim]")
                    live_session = run_live_mtr_dashboard(target, test, console, cycles=cycles)
                    if live_session.result is None:
                        console.print("[dim]Live MTR stopped before the first report was complete.[/dim]")
                        continue
                    result = live_session.result
                else:
                    result = test.run(target, cycles=cycles)
                _save_raw_output(test_run_dir, "mtr.txt", result.raw_output)
                results = [result]
            elif choice == "Website Exposure Audit":
                include_subdomains = questionary.confirm(
                    "Include passive Certificate Transparency name discovery?", default=True,
                ).ask()
                if include_subdomains is None:
                    continue
                from netscope.modules.website_audit import normalize_website_target
                normalize_website_target(target)
                test = WebsiteAuditTest(executor, csv_handler)
                _result_holder = []
                with Progress(SpinnerColumn(), TextColumn("[dim]{task.description}[/dim]"), console=console) as progress:
                    task = progress.add_task("Preparing website checks…", total=None)
                    _t = threading.Thread(target=lambda: _result_holder.append(
                        test.run(
                            target, include_subdomains=include_subdomains,
                            progress_callback=lambda message: progress.update(task, description=message),
                        )
                    ))
                    _t.start()
                    while _t.is_alive():
                        _t.join(timeout=0.05)
                results = [_result_holder[0]]
            elif choice == "ARP Scan":
                console.print("\n[dim]Scanning local ARP table for devices...[/dim]\n")
                test = ARPScanTestEnhanced(executor, csv_handler)
                _result_holder = []

                def _run():
                    _result_holder.append(test.run("local"))

                _t = threading.Thread(target=_run)
                _t.start()
                with Live(Spinner("dots", text="Scanning ARP table…"), console=console, refresh_per_second=8):
                    while _t.is_alive():
                        _t.join(timeout=0.05)
                result = _result_holder[0]
                results = [result]
            elif choice == "Ping Sweep":
                # target already contains the CIDR range from the prompt above
                cidr = target
                test = PingSweepTest(executor, csv_handler)
                _result_holder = []

                def _run():
                    _result_holder.append(test.run(cidr))

                _t = threading.Thread(target=_run)
                _t.start()
                with Live(Spinner("dots", text="Ping sweeping…"), console=console, refresh_per_second=8):
                    while _t.is_alive():
                        _t.join(timeout=0.05)
                result = _result_holder[0]
                results = [result]
            elif choice == "Speedtest":
                if not is_speedtest_available():
                    if questionary.confirm(
                        "speedtest-cli is not installed. Install it now? (uses pip for this environment)",
                        default=True,
                    ).ask():
                        console.print("[dim]Installing speedtest-cli…[/dim]")
                        if try_install_speedtest_cli() and is_speedtest_available():
                            console.print("[green]speedtest-cli installed.[/green]")
                        else:
                            console.print("[yellow]Install failed or speedtest-cli still not in PATH. Speedtest skipped.[/yellow]")
                            results = []
                    else:
                        console.print("[dim]Speedtest skipped.[/dim]")
                        results = []
                if not is_speedtest_available():
                    # Skipped or install failed; results already set to []
                    pass
                else:
                    from datetime import datetime as _dt

                    from netscope.modules.base import TestResult as _TestResult
                    test = BandwidthTest(executor, csv_handler, method="speedtest")
                    _result_holder = []

                    def _run():
                        try:
                            _result_holder.append(test.run(target=target))
                        except Exception as e:
                            _result_holder.append(_TestResult(
                                test_name="Speedtest",
                                target=target,
                                status="failure",
                                timestamp=_dt.now(),
                                duration=0.0,
                                metrics={},
                                summary=str(e),
                                error=str(e),
                                raw_output=str(e),
                            ))

                    _t = threading.Thread(target=_run)
                    _t.start()
                    with Live(Spinner("dots", text="Running speedtest…"), console=console, refresh_per_second=8):
                        while _t.is_alive():
                            _t.join(timeout=0.05)
                    result = _result_holder[0]
                    if result.status == "failure":
                        console.print(f"[red]Speedtest failed: {result.error}[/red]")
                        results = []
                    else:
                        results = [result]
            elif choice == "Quick Network Check":
                results = []
                with Progress(
                    TextColumn("[bold cyan]{task.description}[/bold cyan]"),
                    SpinnerColumn(),
                    TaskProgressColumn(),
                    console=console,
                    transient=True,
                ) as progress:
                    task = progress.add_task("Running: Ping Test…", total=3)
                    test = PingTest(executor, csv_handler)
                    results.append(test.run(target))
                    progress.update(task, advance=1, description="Running: Traceroute Test…")

                    test = TracerouteTest(executor, csv_handler)
                    results.append(test.run(target))
                    progress.update(task, advance=1, description="Running: DNS Lookup…")

                    test = DNSTest(executor, csv_handler)
                    results.append(test.run(target))
                    progress.update(task, advance=1, description="Done")

            # Display results and save metadata only when we have results (e.g. skipped Speedtest has results = [])
            if results:
                if choice == "Quick Network Check":
                    format_quick_check_summary(results, console)
                else:
                    format_test_result(results[0], console)

                primary_result = results[0]
                metadata = {
                    "test_type": choice,
                    "target": target,
                    "status": primary_result.status,
                    "duration_seconds": primary_result.duration,
                    "system_info": system_info.model_dump(mode="json"),
                }
                if choice == "Nmap Scan":
                    metadata["scan_profile"] = profile
                    metadata["targets"] = primary_result.metrics.get("targets", [target])
                    metadata["target_count"] = primary_result.metrics.get("target_count", 1)
                    metadata["vulnerability_script_expression"] = (
                        "vuln and safe and not intrusive and not external and not dos and not exploit"
                        if profile == "vuln" else None
                    )
                if choice == "MTR Route Quality" and live_session is not None:
                    metadata["live_session"] = True
                    metadata["live_sample_count"] = live_session.sample_count
                    metadata["cycles_per_sample"] = cycles
                    metadata["duration_seconds"] = live_session.duration_seconds
                config.save_metadata(test_run_dir, metadata)
                console.print(f"\n[bold green]✓ Results saved to:[/bold green] {test_run_dir}")
                console.print(f"[dim]Hint: netscope report \"{test_run_dir}\"[/dim]")
                print_network_status(console)

        except Exception as e:  # pragma: no cover - defensive
            logger.error(f"Test failed: {e}")
            console.print(f"\n[bold red]❌ Test failed: {e}[/bold red]")
            guidance = get_error_guidance(e, choice, target)
            if guidance:
                from rich.panel import Panel
                console.print(Panel("\n".join(guidance), title="What to try", border_style="dim"))

        if exit_requested():
            raise KeyboardInterrupt

        # Ask if user wants to continue
        if not questionary.confirm("\nRun another test?", default=True).ask():
            console.print("\n[bold cyan]👋 Thank you for using NetScope![/bold cyan]")
            logger.info("NetScope exited normally")
            break


@app.callback(invoke_without_command=True)
def _default(
    ctx: typer.Context,
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory for results",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output",
    ),
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        "--v",
        help="Show version and exit",
    ),
):
    """
    NetScope - Network Diagnostics & Reporting Tool.
    Run with no command for the interactive menu, or use a subcommand for direct tests.
    """
    if version:
        from netscope import __version__
        console.print(f"netscope {__version__}")
        raise typer.Exit(0)
    if ctx.invoked_subcommand is None:
        _run_interactive(output_dir, verbose)


@app.command("main")
def main_cmd(
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory for results",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output",
    ),
):
    """
    Interactive menu (same as running netscope with no command).
    """
    _run_interactive(output_dir, verbose)


@app.command()
def explain(
    test_name: str = typer.Argument(
        ...,
        help="Test to explain: ping, traceroute, dns, ports, quick-check",
    ),
):
    """
    Explain what a test does, when to use it, how to interpret results, and related tests.
    """
    from rich.panel import Panel

    from netscope.cli.explain_content import get_explain_content

    pair = get_explain_content(test_name)
    if pair is None:
        console.print(
            f"[red]Unknown test: {test_name}[/red]\n"
            "[dim]Valid options: ping, traceroute, dns, ports, quick-check[/dim]"
        )
        raise typer.Exit(1)
    title, content = pair
    console.print()
    console.print(
        Panel(
            content.strip(),
            title=f"📚 {title}",
            border_style="cyan",
            expand=False,
        )
    )


@app.command()
def glossary(
    term: Optional[str] = typer.Argument(
        None,
        help="Term to look up (e.g. latency, TTL, DNS). Omit to list all terms.",
    ),
):
    """
    Explain networking terms. Run with no argument to list all terms.
    """
    from rich.panel import Panel

    from netscope.cli.glossary_content import get_glossary_entry, list_glossary_terms

    if term is None or term.strip() == "":
        terms = list_glossary_terms()
        console.print("[bold cyan]📖 Glossary terms[/bold cyan]\n")
        console.print("[dim]Run: netscope glossary <term> for definition[/dim]\n")
        console.print(", ".join(terms))
        return
    entry = get_glossary_entry(term)
    if entry is None:
        console.print(f"[red]Unknown term: {term}[/red]")
        console.print("[dim]Run [cyan]netscope glossary[/cyan] to list terms.[/dim]")
        raise typer.Exit(1)
    display_name, definition = entry
    console.print()
    console.print(Panel(definition.strip(), title=f"📖 {display_name}", border_style="cyan", expand=False))


@app.command()
def history(
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory where runs are stored (default: output)",
    ),
    limit: int = typer.Option(
        10,
        "--limit",
        "-n",
        help="Maximum number of runs to show",
    ),
):
    """
    Show the last N test runs (from the output directory).
    """
    from rich.table import Table

    out = output_dir if output_dir is not None else Path("output")
    if not out.exists() or not out.is_dir():
        console.print(f"[yellow]No output directory at {out}[/yellow]")
        return

    # Subdirs named like 2026-02-12_223600_quick_network_check
    import re
    pattern = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}_.+")
    run_dirs = sorted(
        [d for d in out.iterdir() if d.is_dir() and pattern.match(d.name)],
        key=lambda p: p.name,
        reverse=True,
    )[:limit]

    if not run_dirs:
        console.print("[dim]No test runs found.[/dim]")
        return

    table = Table(title="Recent test runs", show_header=True)
    table.add_column("Time", style="cyan")
    table.add_column("Test", style="white")
    table.add_column("Target", style="white")
    table.add_column("Status", style="white")

    for run_dir in run_dirs:
        meta_file = run_dir / "metadata.json"
        time_str = run_dir.name[:16].replace("_", " ")  # 2026-02-12 223600
        test_name = run_dir.name
        target = "—"
        status = "—"
        if meta_file.exists():
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                test_name = meta.get("test_type", test_name)
                target = meta.get("target", "—")
                status = meta.get("status", "—")
            except Exception:
                pass
        table.add_row(time_str, test_name, target, status)

    console.print()
    console.print(table)


def _resolve_target(target: str) -> str:
    """Resolve smart target shortcuts (localhost, gateway, dns) to actual targets."""
    from netscope.cli.target_resolver import resolve_target_shortcut
    resolved = resolve_target_shortcut(target)
    if resolved:
        console.print(f"[dim]Resolved '{target}' to: {resolved}[/dim]")
        return resolved
    return target


def _first_run_welcome(output_dir: Path) -> None:
    """Show welcome message on first run and create sentinel file."""
    sentinel = Path.home() / ".netscope_first_run_done"
    if sentinel.exists():
        return
    try:
        from rich.panel import Panel
        console.print(
            Panel(
                "Welcome to [bold cyan]NetScope[/bold cyan].\n\n"
                "Choose a test from the menu, enter a target (IP or hostname), "
                "and view results in the terminal. Results are also saved under "
                f"[dim]{output_dir}/[/dim]\n\n"
                "Use [cyan]netscope explain <test>[/cyan] to learn what each test does, "
                "and [cyan]netscope glossary[/cyan] for networking terms.",
                title="👋 Welcome",
                border_style="green",
                expand=False,
            )
        )
        console.print()
    finally:
        try:
            sentinel.touch()
        except OSError:
            pass


def show_main_menu() -> str:
    """Display main menu and return user choice (with short descriptions)."""
    console.print("\n[bold cyan]═══════════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]           Main Menu[/bold cyan]")
    console.print("[bold cyan]═══════════════════════════════════════[/bold cyan]\n")

    choices = [
        Choice("Quick Network Check — Run ping, traceroute, and DNS in one go", value="Quick Network Check"),
        Choice("Ping Test — Check if host is reachable and measure latency", value="Ping Test"),
        Choice("Traceroute Test — Show path and hops to target", value="Traceroute Test"),
        Choice("DNS Lookup — Resolve hostname to IP address(es)", value="DNS Lookup"),
        Choice("Port Scan — Check which TCP ports are open", value="Port Scan"),
        Choice("Nmap Scan — Detailed port & service scan (requires nmap)", value="Nmap Scan"),
        Choice("Website Audit — HTTP headers, TLS certificate & passive subdomains", value="Website Exposure Audit"),
        Choice("MTR — Live route dashboard; press q to stop", value="MTR Route Quality"),
        Choice("ARP Scan — Discover devices on local network", value="ARP Scan"),
        Choice("Ping Sweep — Find alive hosts in a network range", value="Ping Sweep"),
        Choice("Speedtest — Download/upload speed (choose server or auto)", value="Speedtest"),
        Choice("Dashboard — Aggregated network, system, devices & security view", value="Dashboard"),
        Choice("Generate HTML Report — Select a saved run", value="Generate HTML Report"),
        Choice("Exit", value="Exit"),
    ]

    return questionary.select("Select a test:", choices=choices).ask()


@app.command()
def ping(
    target: str = typer.Argument(..., help="Target IP or hostname (shortcuts: localhost, gateway, dns)"),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory for results",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output",
    ),
    output_format: str = typer.Option(
        "rich",
        "--format",
        "-f",
        help="Output format: 'rich' (default) or 'json'",
    ),
):
    """
    Run a ping test in non-interactive mode.
    """
    target = _resolve_target(target)
    config, logger, _detector, system_info = _init_context(output_dir, verbose)
    test_run_dir = config.create_test_run_dir("ping_test")
    csv_handler = CSVHandler(test_run_dir / "results.csv")
    executor = TestExecutor(system_info, logger)

    console.print(f"\n[bold cyan]Running Ping Test on {target}...[/bold cyan]\n")
    test = PingTest(executor, csv_handler)
    _result_holder: list = []

    def _run() -> None:
        _result_holder.append(test.run(target))

    _t = threading.Thread(target=_run)
    _t.start()
    with Live(Spinner("dots", text="[dim]Pinging…[/dim]"), console=console, refresh_per_second=8):
        while _t.is_alive():
            _t.join(timeout=0.05)
    result = _result_holder[0]

    if output_format == "json":
        _output_results_json(result)
    else:
        format_test_result(result, console)

    config.save_metadata(
        test_run_dir,
        {
            "test_type": "Ping Test",
            "target": target,
            "status": result.status,
            "system_info": system_info.model_dump(mode="json"),
        },
    )

    console.print(f"[dim]Hint: netscope report \"{test_run_dir}\"  # HTML + notebook[/dim]")


@app.command()
def traceroute(
    target: str = typer.Argument(..., help="Target IP or hostname (shortcuts: localhost, gateway, dns)"),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory for results",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output",
    ),
    output_format: str = typer.Option(
        "rich",
        "--format",
        "-f",
        help="Output format: 'rich' (default) or 'json'",
    ),
):
    """
    Run a traceroute test in non-interactive mode.
    """
    target = _resolve_target(target)
    config, logger, _detector, system_info = _init_context(output_dir, verbose)
    test_run_dir = config.create_test_run_dir("traceroute_test")
    csv_handler = CSVHandler(test_run_dir / "results.csv")
    executor = TestExecutor(system_info, logger)

    console.print(f"\n[bold cyan]Running Traceroute Test on {target}...[/bold cyan]\n")
    test = TracerouteTest(executor, csv_handler)
    _result_holder = []

    def _run() -> None:
        _result_holder.append(test.run(target))

    _t = threading.Thread(target=_run)
    _t.start()
    with Live(Spinner("dots", text="[dim]Tracing route…[/dim]"), console=console, refresh_per_second=8):
        while _t.is_alive():
            _t.join(timeout=0.05)
    result = _result_holder[0]

    if output_format == "json":
        _output_results_json(result)
    else:
        format_test_result(result, console)

    config.save_metadata(
        test_run_dir,
        {
            "test_type": "Traceroute Test",
            "target": target,
            "status": result.status,
            "system_info": system_info.model_dump(mode="json"),
        },
    )

    console.print(f"[dim]Hint: netscope report \"{test_run_dir}\"  # HTML + notebook[/dim]")


@app.command()
def dns(
    target: str = typer.Argument(..., help="Target hostname (shortcuts: localhost, gateway, dns)"),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory for results",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output",
    ),
    output_format: str = typer.Option(
        "rich",
        "--format",
        "-f",
        help="Output format: 'rich' (default) or 'json'",
    ),
):
    """
    Run a DNS lookup test in non-interactive mode.
    """
    target = _resolve_target(target)
    config, logger, _detector, system_info = _init_context(output_dir, verbose)
    test_run_dir = config.create_test_run_dir("dns_lookup")
    csv_handler = CSVHandler(test_run_dir / "results.csv")
    executor = TestExecutor(system_info, logger)

    console.print(f"\n[bold cyan]Running DNS Lookup on {target}...[/bold cyan]\n")
    test = DNSTest(executor, csv_handler)
    _result_holder = []

    def _run() -> None:
        _result_holder.append(test.run(target))

    _t = threading.Thread(target=_run)
    _t.start()
    with Live(Spinner("dots", text="[dim]Resolving DNS…[/dim]"), console=console, refresh_per_second=8):
        while _t.is_alive():
            _t.join(timeout=0.05)
    result = _result_holder[0]

    if output_format == "json":
        _output_results_json(result)
    else:
        format_test_result(result, console)

    config.save_metadata(
        test_run_dir,
        {
            "test_type": "DNS Lookup",
            "target": target,
            "status": result.status,
            "system_info": system_info.model_dump(mode="json"),
        },
    )

    console.print(f"[dim]Hint: netscope report \"{test_run_dir}\"  # HTML + notebook[/dim]")


@app.command()
def ports(
    target: str = typer.Argument(..., help="Target IP or hostname (shortcuts: localhost, gateway, dns)"),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory for results",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output",
    ),
    output_format: str = typer.Option(
        "rich",
        "--format",
        "-f",
        help="Output format: 'rich' (default) or 'json'",
    ),
    preset: str = typer.Option(
        "top20",
        "--preset",
        "-p",
        help="Port list preset: 'top20' or 'top100'",
    ),
):
    """
    Run a port scan in non-interactive mode (TCP connect, no nmap required).
    """
    target = _resolve_target(target)
    config, logger, _detector, system_info = _init_context(output_dir, verbose)
    test_run_dir = config.create_test_run_dir("port_scan")
    csv_handler = CSVHandler(test_run_dir / "results.csv")
    executor = TestExecutor(system_info, logger)

    console.print(f"\n[bold cyan]Running Port Scan on {target} (preset: {preset})...[/bold cyan]\n")
    test = PortScanTest(executor, csv_handler)
    _result_holder = []

    def _run() -> None:
        _result_holder.append(test.run(target, preset=preset))

    _t = threading.Thread(target=_run)
    _t.start()
    with Live(Spinner("dots", text="[dim]Scanning ports…[/dim]"), console=console, refresh_per_second=8):
        while _t.is_alive():
            _t.join(timeout=0.05)
    result = _result_holder[0]

    if output_format == "json":
        _output_results_json(result)
    else:
        format_test_result(result, console)

    config.save_metadata(
        test_run_dir,
        {
            "test_type": "Port Scan",
            "target": target,
            "status": result.status,
            "system_info": system_info.model_dump(mode="json"),
        },
    )

    console.print(f"[dim]Hint: netscope report \"{test_run_dir}\"  # HTML + notebook[/dim]")


@app.command(name="nmap-scan")
def nmap_scan(
    targets: List[str] = typer.Argument(..., help="One or more target hostnames/IPs (maximum 32)."),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory for results",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output",
    ),
    output_format: str = typer.Option(
        "rich",
        "--format",
        "-f",
        help="Output format: 'rich' (default) or 'json'",
    ),
    ports: Optional[str] = typer.Option(
        None,
        "--ports",
        "-p",
        help="Ports to scan (e.g. '22,80,443' or '1-1024'). If omitted, nmap defaults are used.",
    ),
    profile: str = typer.Option(
        "service",
        "--profile",
        help="Scan profile: connect, service, udp, or vuln (bounded safe NSE checks).",
    ),
    timeout: int = typer.Option(120, "--timeout", min=1, max=3600, help="Maximum scan duration in seconds."),
    live: bool = typer.Option(True, "--live/--once", help="Use the fullscreen live dashboard in a TTY; --once runs a finite scan."),
):
    """
    Run a bounded Nmap scan against one or more explicitly named hosts.
    """
    if profile not in {"connect", "service", "udp", "vuln"}:
        console.print("[red]Profile must be one of: connect, service, udp, vuln.[/red]")
        raise typer.Exit(2)
    try:
        resolved_targets = normalize_targets([_resolve_target(target) for target in targets])
        if profile == "vuln":
            resolved_targets = validate_vulnerability_scope(resolved_targets, ports)
            if timeout > 900:
                raise ValueError("Vulnerability-scan timeout is capped at 900 seconds.")
    except ValueError as exc:
        console.print(f"[red]Invalid Nmap scope: {exc}[/red]")
        raise typer.Exit(2)

    config, logger, _detector, system_info = _init_context(output_dir, verbose)
    test_run_dir = config.create_test_run_dir("nmap_vulnerability_scan" if profile == "vuln" else "nmap_scan")
    csv_handler = CSVHandler(test_run_dir / "results.csv")
    executor = TestExecutor(system_info, logger)

    scope = ports or {
        "connect": "fast top 100 TCP", "service": "Nmap default TCP ports",
        "udp": "top 20 UDP", "vuln": "top 20 TCP + safe NSE vulnerability checks",
    }[profile]
    use_live = live and output_format != "json" and sys.stdin.isatty() and sys.stdout.isatty()
    if output_format != "json":
        console.print(
            f"\n[bold cyan]Nmap · {profile} · targets {len(resolved_targets)} · "
            f"scope {scope} · timeout {timeout}s[/bold cyan]"
        )
        console.print("[dim]Scan only systems you are authorized to assess. Vulnerability scripts are selected from safe NSE categories; results are evidence, not proof.[/dim]\n")
        if live and not use_live:
            console.print("[dim]No interactive terminal detected; running one finite batch. Use --live in a TTY or --once for scripts.[/dim]")
    test = NmapScanTest(executor, csv_handler)
    live_session = None
    if use_live:
        from netscope.tui.nmap_live import run_live_nmap_dashboard
        live_session = run_live_nmap_dashboard(
            resolved_targets, test, console, profile=profile, ports=ports, timeout=timeout,
        )
        result = live_session.result
    elif output_format == "json":
        result = test.run(resolved_targets, ports=ports, profile=profile, timeout=timeout)
    else:
        result_holder = []
        worker = threading.Thread(
            target=lambda: result_holder.append(
                test.run(resolved_targets, ports=ports, profile=profile, timeout=timeout)
            )
        )
        worker.start()
        with Live(Spinner("dots", text="[dim]Running Nmap batch…[/dim]"), console=console, refresh_per_second=8):
            while worker.is_alive():
                worker.join(timeout=0.05)
        result = result_holder[0]
    _save_raw_output(test_run_dir, "nmap.xml", result.raw_output)

    if output_format == "json":
        _output_results_json(result)
    else:
        format_test_result(result, console)

    metadata = {
        "test_type": result.test_name,
        "target": ", ".join(resolved_targets),
        "targets": resolved_targets,
        "target_count": len(resolved_targets),
        "scan_profile": profile,
        "ports": ports,
        "timeout_seconds": timeout,
        "status": result.status,
        "duration_seconds": result.duration,
        "live_session": bool(live_session),
        "cancelled": live_session.cancelled if live_session else False,
        "system_info": system_info.model_dump(mode="json"),
    }
    if profile == "vuln":
        metadata["vulnerability_script_expression"] = NMAP_VULN_SCRIPT_EXPRESSION
        metadata["scope_limit"] = "up to 16 explicit hosts and 100 numeric TCP ports per host"
    config.save_metadata(test_run_dir, metadata)
    if output_format != "json":
        console.print(f"[dim]Hint: netscope report \"{test_run_dir}\"  # HTML + notebook[/dim]")


@app.command(name="mtr")
def mtr_scan(
    target: str = typer.Argument(..., help="Target IP or hostname"),
    cycles: int = typer.Option(5, "--cycles", "-c", min=1, max=100, help="Probe cycles per live refresh (1–100)."),
    live: bool = typer.Option(True, "--live/--once", help="Use a persistent full-screen dashboard in a terminal; --once emits one report and exits."),
    output_dir: Optional[Path] = typer.Option(None, "--output", "-o", help="Output directory for results"),
    output_format: str = typer.Option("rich", "--format", "-f", help="Output format: rich or json"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
):
    """Run a persistent live MTR dashboard, or use --once for a finite report."""
    config, logger, _detector, system_info = _init_context(output_dir, verbose)
    test_run_dir = config.create_test_run_dir("mtr_route_quality")
    csv_handler = CSVHandler(test_run_dir / "results.csv")
    executor = TestExecutor(system_info, logger)
    resolved_target = _resolve_target(target)
    scanner = MTRTest(executor, csv_handler)
    use_live = live and output_format != "json" and sys.stdin.isatty() and sys.stdout.isatty()
    live_session = None
    if use_live:
        from netscope.tui.mtr_live import run_live_mtr_dashboard
        console.print(f"\n[bold]MTR live route dashboard · {resolved_target} · {cycles} cycles per refresh[/bold]")
        live_session = run_live_mtr_dashboard(resolved_target, scanner, console, cycles=cycles)
        result = live_session.result
        if result is None:
            config.save_metadata(test_run_dir, {
                "test_type": "MTR Route Quality", "target": resolved_target, "status": "cancelled",
                "live_session": True, "live_sample_count": 0,
                "system_info": system_info.model_dump(mode="json"),
            })
            console.print("[dim]Live MTR stopped before a complete report was available.[/dim]")
            return
    else:
        if output_format == "json":
            result = scanner.run(resolved_target, cycles=cycles)
        else:
            if live and not (sys.stdin.isatty() and sys.stdout.isatty()):
                console.print("[dim]No interactive terminal detected; running one finite MTR report. Use --live in a TTY or --once for scripts.[/dim]")
            console.print(f"\n[bold]MTR route quality · {resolved_target} · {cycles} cycles[/bold]")
            console.print("[dim]The report is emitted when MTR completes; no estimated percentage is shown.[/dim]")
            _result_holder = []
            _t = threading.Thread(target=lambda: _result_holder.append(scanner.run(resolved_target, cycles=cycles)))
            _t.start()
            with Live(Spinner("dots", text=f"Sampling route · {cycles} cycles…"), console=console, refresh_per_second=8):
                while _t.is_alive():
                    _t.join(timeout=0.05)
            result = _result_holder[0]
    _save_raw_output(test_run_dir, "mtr.txt", result.raw_output)
    if output_format == "json":
        _output_results_json(result)
    else:
        format_test_result(result, console)
    metadata = {
        "test_type": "MTR Route Quality", "target": resolved_target, "status": result.status,
        "cycles": cycles, "duration_seconds": live_session.duration_seconds if live_session else result.duration,
        "system_info": system_info.model_dump(mode="json"),
    }
    if live_session:
        metadata.update({
            "live_session": True, "live_sample_count": live_session.sample_count,
            "cycles_per_sample": cycles,
        })
    config.save_metadata(test_run_dir, metadata)
    if output_format != "json":
        console.print(f"[dim]Hint: netscope report \"{test_run_dir}\"[/dim]")


@app.command(name="website-audit")
def website_audit(
    target: str = typer.Argument(..., help="Hostname or http(s) URL"),
    no_subdomains: bool = typer.Option(False, "--no-subdomains", help="Skip passive Certificate Transparency lookup."),
    output_dir: Optional[Path] = typer.Option(None, "--output", "-o", help="Output directory for results"),
    output_format: str = typer.Option("rich", "--format", "-f", help="Output format: rich or json"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
):
    """Inspect HTTP security headers and TLS posture; optionally list passive CT names."""
    config, logger, _detector, system_info = _init_context(output_dir, verbose)
    test_run_dir = config.create_test_run_dir("website_exposure_audit")
    csv_handler = CSVHandler(test_run_dir / "results.csv")
    executor = TestExecutor(system_info, logger)
    console.print(f"\n[bold]Website exposure audit · {target}[/bold]")
    console.print("[dim]CT name discovery reads public certificate records; discovered names are not probed.[/dim]")
    try:
        from netscope.modules.website_audit import normalize_website_target
        normalize_website_target(target)
        _result_holder = []
        with Progress(SpinnerColumn(), TextColumn("[dim]{task.description}[/dim]"), console=console) as progress:
            task = progress.add_task("Preparing website checks…", total=None)
            _t = threading.Thread(target=lambda: _result_holder.append(
                WebsiteAuditTest(executor, csv_handler).run(
                    target, include_subdomains=not no_subdomains,
                    progress_callback=lambda message: progress.update(task, description=message),
                )
            ))
            _t.start()
            while _t.is_alive():
                _t.join(timeout=0.05)
        result = _result_holder[0]
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(2) from exc
    if output_format == "json":
        _output_results_json(result)
    else:
        format_test_result(result, console)
    config.save_metadata(test_run_dir, {
        "test_type": "Website Exposure Audit", "target": result.target,
        "status": result.status, "duration_seconds": result.duration,
        "system_info": system_info.model_dump(mode="json"),
    })
    console.print(f"[dim]Hint: netscope report \"{test_run_dir}\"[/dim]")


@app.command(name="arp-scan")
def arp_scan(
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory for results",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output",
    ),
    with_os: bool = typer.Option(
        False,
        "--with-os",
        help="Use nmap -O to detect OS/device type per host (slower, up to 10 hosts)",
    ),
    output_format: str = typer.Option(
        "rich",
        "--format",
        "-f",
        help="Output format: 'rich' (default) or 'json'",
    ),
):
    """
    Scan local ARP table to discover devices (vendor from OUI). Use --with-os to add nmap OS detection.
    """
    config, logger, _detector, system_info = _init_context(output_dir, verbose)
    test_run_dir = config.create_test_run_dir("arp_scan")
    csv_handler = CSVHandler(test_run_dir / "results.csv")
    executor = TestExecutor(system_info, logger)

    console.print("\n[bold cyan]Running ARP Scan...[/bold cyan]\n")
    test = ARPScanTestEnhanced(executor, csv_handler)
    _result_holder = []

    def _run() -> None:
        _result_holder.append(test.run("local", with_os_detection=with_os))

    _t = threading.Thread(target=_run)
    _t.start()
    with Live(Spinner("dots", text="[dim]Scanning ARP table…[/dim]"), console=console, refresh_per_second=8):
        while _t.is_alive():
            _t.join(timeout=0.05)
    result = _result_holder[0]

    if output_format == "json":
        _output_results_json(result)
    else:
        format_test_result(result, console)

    config.save_metadata(
        test_run_dir,
        {
            "test_type": "ARP Scan",
            "target": "local",
            "status": result.status,
            "system_info": system_info.model_dump(mode="json"),
        },
    )

    console.print(f"[dim]Hint: netscope report \"{test_run_dir}\"  # HTML + notebook[/dim]")


@app.command(name="speedtest")
def speedtest(
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory for results",
    ),
    list_servers: bool = typer.Option(
        False,
        "--list",
        "-l",
        help="List available speedtest servers (ID, sponsor, location) then exit",
    ),
    server: Optional[str] = typer.Option(
        None,
        "--server",
        "-s",
        help="Use this server ID (from 'netscope speedtest --list'). Default: auto-select",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output",
    ),
):
    """
    Run a speedtest (download/upload). Use --list to choose a server by ID, then --server <id>.
    """
    if list_servers:
        from rich.table import Table as RichTable
        if not is_speedtest_available():
            if sys.stdin.isatty() and questionary.confirm(
                "speedtest-cli is not installed. Install it now? (uses pip for this environment)",
                default=True,
            ).ask():
                console.print("[dim]Installing speedtest-cli…[/dim]")
                try_install_speedtest_cli()
        servers = list_speedtest_servers() if is_speedtest_available() else []
        if not servers:
            console.print("[yellow]speedtest-cli not found or failed. Install with: pip install speedtest-cli[/yellow]")
            raise typer.Exit(1)
        console.print("\n[bold cyan]Available speedtest servers (use --server ID)[/bold cyan]\n")
        t = RichTable(show_header=True, header_style="bold")
        t.add_column("ID", style="cyan")
        t.add_column("Sponsor / Location", style="white")
        for s in servers[:50]:
            t.add_row(s["id"], s["label"])
        console.print(t)
        console.print("\n[dim]Example: netscope speedtest --server 1234[/dim]\n")
        return

    if not is_speedtest_available():
        if sys.stdin.isatty() and questionary.confirm(
            "speedtest-cli is not installed. Install it now? (uses pip for this environment)",
            default=True,
        ).ask():
            console.print("[dim]Installing speedtest-cli…[/dim]")
            try_install_speedtest_cli()
        if not is_speedtest_available():
            console.print("[yellow]speedtest-cli is required. Install with: pip install speedtest-cli[/yellow]")
            raise typer.Exit(1)

    config, logger, _detector, system_info = _init_context(output_dir, verbose)
    test_run_dir = config.create_test_run_dir("speedtest")
    csv_handler = CSVHandler(test_run_dir / "results.csv")
    executor = TestExecutor(system_info, logger)

    target = server if server else "auto"
    console.print("\n[bold cyan]Running Speedtest...[/bold cyan]")
    if target != "auto":
        console.print(f"[dim]Server ID: {target}[/dim]\n")
    else:
        console.print("[dim]Server: auto (closest)[/dim]\n")

    test = BandwidthTest(executor, csv_handler, method="speedtest")
    try:
        result = test.run(target=target)
    except Exception as e:
        console.print(f"[red]Speedtest failed: {e}[/red]")
        raise typer.Exit(1)

    format_test_result(result, console)
    config.save_metadata(
        test_run_dir,
        {
            "test_type": "Speedtest",
            "target": target,
            "status": result.status,
            "system_info": system_info.model_dump(mode="json"),
        },
    )
    console.print(f"[dim]Hint: netscope report \"{test_run_dir}\"  # HTML + notebook[/dim]")


@app.command(name="ping-sweep")
def ping_sweep(
    cidr: str = typer.Argument(..., help="CIDR range (e.g., 192.168.1.0/24). Maximum /24 (256 hosts)."),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory for results",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output",
    ),
    output_format: str = typer.Option(
        "rich",
        "--format",
        "-f",
        help="Output format: 'rich' (default) or 'json'",
    ),
    max_workers: int = typer.Option(
        50,
        "--workers",
        "-w",
        help="Maximum concurrent ping threads",
    ),
    timeout: float = typer.Option(
        1.0,
        "--timeout",
        "-t",
        help="Timeout per ping in seconds",
    ),
):
    """
    Ping sweep a CIDR range to find alive hosts.
    """
    config, logger, _detector, system_info = _init_context(output_dir, verbose)
    test_run_dir = config.create_test_run_dir("ping_sweep")
    csv_handler = CSVHandler(test_run_dir / "results.csv")
    executor = TestExecutor(system_info, logger)

    console.print(f"\n[bold cyan]Running Ping Sweep on {cidr}...[/bold cyan]\n")
    test = PingSweepTest(executor, csv_handler)
    _result_holder = []

    def _run() -> None:
        _result_holder.append(test.run(cidr, max_workers=max_workers, timeout=timeout))

    _t = threading.Thread(target=_run)
    _t.start()
    with Live(Spinner("dots", text="[dim]Ping sweeping…[/dim]"), console=console, refresh_per_second=8):
        while _t.is_alive():
            _t.join(timeout=0.05)
    result = _result_holder[0]

    if output_format == "json":
        _output_results_json(result)
    else:
        format_test_result(result, console)

    config.save_metadata(
        test_run_dir,
        {
            "test_type": "Ping Sweep",
            "target": cidr,
            "status": result.status,
            "system_info": system_info.model_dump(mode="json"),
        },
    )

    console.print(f"[dim]Hint: netscope report \"{test_run_dir}\"  # HTML + notebook[/dim]")


@app.command(name="report-html")
def report_html_cmd(
    run_dir: Path = typer.Argument(..., help="Path to a single NetScope run directory"),
    output_file: Optional[Path] = typer.Option(
        None,
        "--output-file",
        "-o",
        help="Output HTML file (default: report.html inside the run directory)",
    ),
):
    """
    Generate an HTML report for a single run directory.
    """
    from netscope.report.html_report import generate_html_report

    if not run_dir.exists() or not run_dir.is_dir():
        console.print(f"[red]Run directory not found:[/red] {run_dir}")
        raise typer.Exit(1)

    html_path = generate_html_report(run_dir, output_file)
    console.print(f"\n[bold green]✓ HTML report generated:[/bold green] {html_path}\n")


@app.command(name="report")
def report_cmd(
    run_dir: Path = typer.Argument(..., help="Path to a single NetScope run directory"),
    html: bool = typer.Option(
        True,
        "--html/--no-html",
        help="Generate HTML report (default: on)",
    ),
    notebook: bool = typer.Option(
        True,
        "--notebook/--no-notebook",
        help="Generate Jupyter notebook report (default: on)",
    ),
):
    """
    Generate all available reports (HTML and notebook) for a single run directory.
    """
    from netscope.report.html_report import generate_html_report
    from netscope.report.notebook_report import generate_notebook_report

    if not run_dir.exists() or not run_dir.is_dir():
        console.print(f"[red]Run directory not found:[/red] {run_dir}")
        raise typer.Exit(1)

    generated: list[str] = []
    if html:
        html_path = generate_html_report(run_dir)
        generated.append(str(html_path))
    if notebook:
        nb_path = generate_notebook_report(run_dir)
        generated.append(str(nb_path))

    if not generated:
        console.print("[yellow]No reports were generated (both --no-html and --no-notebook were set).[/yellow]")
    else:
        console.print("\n[bold green]✓ Reports generated:[/bold green]")
        for path in generated:
            console.print(f"  [dim]{path}[/dim]")


@app.command(name="report-notebook")
def report_notebook_cmd(
    run_dir: Path = typer.Argument(..., help="Path to a single NetScope run directory"),
    output_file: Optional[Path] = typer.Option(
        None,
        "--output-file",
        "-o",
        help="Output .ipynb file (default: report.ipynb inside the run directory)",
    ),
):
    """
    Generate a Jupyter notebook for a single run directory.
    """
    from netscope.report.notebook_report import generate_notebook_report

    if not run_dir.exists() or not run_dir.is_dir():
        console.print(f"[red]Run directory not found:[/red] {run_dir}")
        raise typer.Exit(1)

    nb_path = generate_notebook_report(run_dir, output_file)
    console.print(f"\n[bold green]✓ Notebook generated:[/bold green] {nb_path}\n")


@app.command(name="quick-check")
def quick_check(
    target: str = typer.Argument(..., help="Target IP or hostname (shortcuts: localhost, gateway, dns)"),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory for results",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output",
    ),
    output_format: str = typer.Option(
        "rich",
        "--format",
        "-f",
        help="Output format: 'rich' (default) or 'json'",
    ),
):
    """
    Run all core tests (ping, traceroute, DNS) in parallel.
    """
    target = _resolve_target(target)
    config, logger, _detector, system_info = _init_context(output_dir, verbose)
    test_run_dir = config.create_test_run_dir("quick_network_check")
    csv_handler = CSVHandler(test_run_dir / "results.csv")
    executor = TestExecutor(system_info, logger)

    console.print(f"\n[bold cyan]Running Quick Network Check on {target}...[/bold cyan]\n")

    # Prepare test instances
    ping_test = PingTest(executor, csv_handler)
    trace_test = TracerouteTest(executor, csv_handler)
    dns_test = DNSTest(executor, csv_handler)

    runner = BatchTestRunner(ParallelTestConfig(max_workers=3, timeout=config.timeout))

    tests_spec = [
        {"name": "Ping Test", "func": ping_test.run, "target": target},
        {"name": "Traceroute Test", "func": trace_test.run, "target": target},
        {"name": "DNS Lookup", "func": dns_test.run, "target": target},
    ]

    from rich.progress import Progress, SpinnerColumn, TaskProgressColumn, TextColumn

    with Progress(
        TextColumn("[dim]{task.description}[/dim]"),
        SpinnerColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Running: Ping, Traceroute, DNS…", total=len(tests_spec))

        def _cb(completed: int, total: int) -> None:
            progress.update(task, completed=completed)

        batch_results = runner.run_batch(tests_spec, progress_callback=_cb)

    # Flatten results in deterministic order: Ping, Traceroute, DNS
    results = [
        (batch_results.get("Ping Test") or [ping_test.run(target)])[0],
        (batch_results.get("Traceroute Test") or [trace_test.run(target)])[0],
        (batch_results.get("DNS Lookup") or [dns_test.run(target)])[0],
    ]

    if output_format == "json":
        _output_results_json(results)
    else:
        format_quick_check_summary(results, console)

    primary = results[0]
    config.save_metadata(
        test_run_dir,
        {
            "test_type": "Quick Network Check",
            "target": target,
            "status": primary.status,
            "system_info": system_info.model_dump(mode="json"),
        },
    )

    console.print(f"[dim]Hint: netscope report \"{test_run_dir}\"  # HTML + notebook[/dim]")


@app.command()
def glossary(
    term: Optional[str] = typer.Argument(None, help="Term to look up (e.g., latency, dns, ports)"),
):
    """
    Show glossary of networking terms. Use without a term to list all available terms.
    """
    from rich.panel import Panel

    from netscope.cli.glossary_content import get_glossary_term, list_all_terms

    if term is None:
        terms = list_all_terms()
        console.print("\n[bold cyan]Available glossary terms:[/bold cyan]\n")
        for t in terms:
            console.print(f"  • [cyan]{t}[/cyan]")
        console.print("\n[dim]Use: netscope glossary <term> to see details[/dim]\n")
        return

    result = get_glossary_term(term)
    if result is None:
        console.print(f"\n[red]Term '{term}' not found.[/red]")
        console.print("[dim]Use 'netscope glossary' (no term) to see all available terms.[/dim]\n")
        return

    term_name, content = result
    console.print()
    console.print(Panel(content, title=f"Glossary: {term_name}", border_style="cyan", expand=False))
    console.print()


@app.command()
def troubleshoot(
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory for results",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output",
    ),
):
    """
    Interactive troubleshooting wizard. Answer questions to get suggested tests.
    """
    from netscope.cli.formatters import format_quick_check_summary, format_test_result
    from netscope.modules.connectivity import PingTest, TracerouteTest
    from netscope.modules.dns import DNSTest

    console.print("\n[bold cyan]🔧 Troubleshooting Wizard[/bold cyan]\n")
    console.print("Tell me what's wrong, and I'll suggest tests to run.\n")

    problem = questionary.select(
        "What's the problem?",
        choices=[
            Choice("Website or server is down / not responding", value="down"),
            Choice("Connection is slow", value="slow"),
            Choice("Can't reach a specific hostname", value="hostname"),
            Choice("Can't connect to a service (port)", value="port"),
            Choice("General connectivity issues", value="general"),
            Choice("Exit", value="exit"),
        ],
    ).ask()

    if problem == "exit" or not problem:
        return

    config, logger, detector, system_info = _init_context(output_dir, verbose)
    test_run_dir = config.create_test_run_dir("troubleshoot")
    csv_handler = CSVHandler(test_run_dir / "results.csv")
    executor = TestExecutor(system_info, logger)

    # Get target
    console.print("\n[dim]Examples: 8.8.8.8, google.com, example.com[/dim]")
    console.print("[dim]Shortcuts: localhost, gateway, dns[/dim]")
    target = questionary.text(
        "Enter target IP or hostname:",
        validate=lambda x: len(x) > 0,
    ).ask()

    if not target:
        return

    # Resolve smart shortcuts
    target = _resolve_target(target)

    suggestions = []
    tests_to_run = []

    if problem == "down":
        suggestions.append("Running Quick Network Check to diagnose reachability...")
        tests_to_run = ["quick"]
    elif problem == "slow":
        suggestions.append("Running Ping and Traceroute to find where slowness occurs...")
        tests_to_run = ["ping", "traceroute"]
    elif problem == "hostname":
        suggestions.append("Running DNS lookup to check name resolution...")
        tests_to_run = ["dns"]
    elif problem == "port":
        suggestions.append("Running Port Scan to check if service is listening...")
        tests_to_run = ["port"]
    else:  # general
        suggestions.append("Running Quick Network Check for overall diagnosis...")
        tests_to_run = ["quick"]

    console.print("\n[bold]Suggested tests:[/bold]")
    for s in suggestions:
        console.print(f"  • {s}")

    if not questionary.confirm("\nRun suggested tests?", default=True).ask():
        return

    console.print()

    results = []
    if "quick" in tests_to_run:
        test = PingTest(executor, csv_handler)
        results.append(test.run(target))
        test = TracerouteTest(executor, csv_handler)
        results.append(test.run(target))
        test = DNSTest(executor, csv_handler)
        results.append(test.run(target))
        format_quick_check_summary(results, console)
    else:
        for test_name in tests_to_run:
            if test_name == "ping":
                test = PingTest(executor, csv_handler)
                results.append(test.run(target))
            elif test_name == "traceroute":
                test = TracerouteTest(executor, csv_handler)
                results.append(test.run(target))
            elif test_name == "dns":
                test = DNSTest(executor, csv_handler)
                results.append(test.run(target))
            elif test_name == "port":
                from netscope.modules.ports import PortScanTest
                test = PortScanTest(executor, csv_handler)
                results.append(test.run(target))

        for result in results:
            format_test_result(result, console)

    if results:
        config.save_metadata(
            test_run_dir,
            {
                "test_type": "Troubleshoot",
                "target": target,
                "problem": problem,
                "status": results[0].status,
                "system_info": system_info.model_dump(mode="json"),
            },
        )
        console.print(f"\n[bold green]✓ Results saved to:[/bold green] {test_run_dir}")


@app.command()
def examples():
    """
    Show common usage examples and scenarios.
    """
    from rich.table import Table

    console.print("\n[bold cyan]📚 NetScope Examples[/bold cyan]\n")

    examples_table = Table(show_header=True, box=None)
    examples_table.add_column("Scenario", style="cyan", width=30)
    examples_table.add_column("Command", style="white")
    examples_table.add_column("What it does", style="dim")

    examples_data = [
        (
            "Check if website is down",
            "netscope quick-check google.com",
            "Runs ping, traceroute, and DNS to diagnose",
        ),
        (
            "Measure latency to server",
            "netscope ping 8.8.8.8",
            "Tests reachability and shows min/avg/max latency",
        ),
        (
            "Find slow hops",
            "netscope traceroute example.com",
            "Shows path and delay at each router",
        ),
        (
            "Check DNS resolution",
            "netscope dns google.com",
            "Resolves hostname to IP addresses (IPv4/IPv6)",
        ),
        (
            "Scan for open ports",
            "netscope ports 192.168.1.1 --preset top20",
            "Checks which TCP ports are open",
        ),
        (
            "Interactive menu",
            "netscope",
            "Launches menu to choose tests interactively",
        ),
        (
            "Learn about a test",
            "netscope explain ping",
            "Shows what ping does and how to interpret results",
        ),
        (
            "Look up a term",
            "netscope glossary latency",
            "Explains networking terms",
        ),
        (
            "Troubleshoot a problem",
            "netscope troubleshoot",
            "Wizard guides you through diagnosis",
        ),
        (
            "Save results to custom dir",
            "netscope ping 8.8.8.8 -o ./my-results",
            "Outputs results to specified directory",
        ),
        (
            "JSON output for scripts",
            "netscope ping 8.8.8.8 --format json",
            "Outputs machine-readable JSON",
        ),
    ]

    for scenario, cmd, desc in examples_data:
        examples_table.add_row(scenario, f"[bold]{cmd}[/bold]", desc)

    console.print(examples_table)
    console.print()


if __name__ == "__main__":
    app()
