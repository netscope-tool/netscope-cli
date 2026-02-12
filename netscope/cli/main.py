"""
Main CLI application using Typer.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Iterable, Optional, Sequence

import questionary
import typer
from rich.console import Console
from rich.live import Live
from rich.progress import Progress, SpinnerColumn, TextColumn, TaskProgressColumn
from rich.spinner import Spinner

from netscope.cli.formatters import (
    format_quick_check_summary,
    format_test_result,
    get_error_guidance,
    iter_results,
    print_header,
    print_system_info,
)
from netscope.core.config import AppConfig
from netscope.core.detector import SystemDetector
from netscope.core.executor import TestExecutor
from netscope.modules.connectivity import PingTest, TracerouteTest
from netscope.modules.dns import DNSTest
from netscope.storage.csv_handler import CSVHandler
from netscope.storage.logger import setup_logging

app = typer.Typer(
    name="netscope",
    help="Network Diagnostics & Reporting Tool",
    add_completion=False,
)

console = Console()


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

    # Print system information
    print_system_info(system_info)

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

        # Get target (with subtle guide)
        console.print(
            "[dim]  Examples: 8.8.8.8, 1.1.1.1, google.com, example.com[/dim]"
        )
        target = questionary.text(
            "Enter target IP/hostname:",
            validate=lambda x: len(x) > 0,
        ).ask()

        if not target:
            continue

        # Create test run directory and helpers
        test_run_dir = config.create_test_run_dir(choice.lower().replace(" ", "_"))
        logger.info(f"Created test run directory: {test_run_dir}")

        csv_handler = CSVHandler(test_run_dir / "results.csv")
        executor = TestExecutor(system_info, logger)

        # Execute test based on choice
        console.print(f"\n[bold cyan]Running {choice} on {target}...[/bold cyan]\n")

        try:
            if choice == "Ping Test":
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

            # Display results
            if choice == "Quick Network Check":
                format_quick_check_summary(results, console)
            else:
                format_test_result(results[0], console)

            primary_result = results[0]

            # Save metadata
            config.save_metadata(
                test_run_dir,
                {
                    "test_type": choice,
                    "target": target,
                    "status": primary_result.status,
                    "system_info": system_info.model_dump(mode="json"),
                },
            )

            console.print(f"\n[bold green]✓ Results saved to:[/bold green] {test_run_dir}")

        except Exception as e:  # pragma: no cover - defensive
            logger.error(f"Test failed: {e}")
            console.print(f"\n[bold red]❌ Test failed: {e}[/bold red]")
            guidance = get_error_guidance(e, choice, target)
            if guidance:
                from rich.panel import Panel
                console.print(Panel("\n".join(guidance), title="What to try", border_style="dim"))

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
    from netscope.cli.explain_content import get_explain_content
    from rich.panel import Panel

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
    from netscope.cli.glossary_content import get_glossary_entry, list_glossary_terms
    from rich.panel import Panel

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


def show_main_menu() -> str:
    """Display main menu and return user choice."""
    console.print("\n[bold cyan]═══════════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]           Main Menu[/bold cyan]")
    console.print("[bold cyan]═══════════════════════════════════════[/bold cyan]\n")
    
    choices = [
        "Quick Network Check",
        "Ping Test",
        "Traceroute Test",
        "DNS Lookup",
        "Exit",
    ]
    
    return questionary.select("Select a test:", choices=choices).ask()


@app.command()
def ping(
    target: str = typer.Argument(..., help="Target IP or hostname"),
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
    config, logger, _detector, system_info = _init_context(output_dir, verbose)
    test_run_dir = config.create_test_run_dir("ping_test")
    csv_handler = CSVHandler(test_run_dir / "results.csv")
    executor = TestExecutor(system_info, logger)

    console.print(f"\n[bold cyan]Running Ping Test on {target}...[/bold cyan]\n")
    test = PingTest(executor, csv_handler)
    result = test.run(target)

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


@app.command()
def traceroute(
    target: str = typer.Argument(..., help="Target IP or hostname"),
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
    config, logger, _detector, system_info = _init_context(output_dir, verbose)
    test_run_dir = config.create_test_run_dir("traceroute_test")
    csv_handler = CSVHandler(test_run_dir / "results.csv")
    executor = TestExecutor(system_info, logger)

    console.print(f"\n[bold cyan]Running Traceroute Test on {target}...[/bold cyan]\n")
    test = TracerouteTest(executor, csv_handler)
    result = test.run(target)

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


@app.command()
def dns(
    target: str = typer.Argument(..., help="Target hostname"),
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
    config, logger, _detector, system_info = _init_context(output_dir, verbose)
    test_run_dir = config.create_test_run_dir("dns_lookup")
    csv_handler = CSVHandler(test_run_dir / "results.csv")
    executor = TestExecutor(system_info, logger)

    console.print(f"\n[bold cyan]Running DNS Lookup on {target}...[/bold cyan]\n")
    test = DNSTest(executor, csv_handler)
    result = test.run(target)

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


@app.command(name="quick-check")
def quick_check(
    target: str = typer.Argument(..., help="Target IP or hostname"),
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
    Run all core tests (ping, traceroute, DNS) in sequence.
    """
    config, logger, _detector, system_info = _init_context(output_dir, verbose)
    test_run_dir = config.create_test_run_dir("quick_network_check")
    csv_handler = CSVHandler(test_run_dir / "results.csv")
    executor = TestExecutor(system_info, logger)

    console.print(f"\n[bold cyan]Running Quick Network Check on {target}...[/bold cyan]\n")

    tests = [PingTest(executor, csv_handler), TracerouteTest(executor, csv_handler), DNSTest(executor, csv_handler)]
    results = [test.run(target) for test in tests]

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


if __name__ == "__main__":
    app()