"""Fullscreen Nmap dashboard driven by streamed XML events."""
from __future__ import annotations

import queue
import threading
import time
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

from rich.align import Align
from rich.box import SIMPLE_HEAD
from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from netscope.modules.base import TestResult
from netscope.modules.nmap_scan import NmapScanTest, normalize_targets
from netscope.tui.mtr_live import _elapsed_text
from netscope.tui.terminal import (
    is_alternate_screen_active,
    request_exit_after_interaction,
    single_key_reader,
)


@dataclass
class LiveNmapSession:
    """The final result and interaction state returned after a live Nmap run."""

    result: TestResult
    cancelled: bool
    duration_seconds: float


def _progress_text(progress: Optional[Dict[str, Any]]) -> Text:
    if not progress:
        return Text("Waiting for the first Nmap progress event…", style="dim")
    task = progress.get("task", "Nmap scan")
    try:
        percent = max(0.0, min(100.0, float(progress.get("percent", 0))))
        width = 22
        filled = round(width * percent / 100)
        bar = "█" * filled + "·" * (width - filled)
        pct_text = f"{percent:5.1f}%"
    except (TypeError, ValueError):
        bar = "······················"
        pct_text = "   —  "
    remaining = progress.get("remaining")
    try:
        remaining_text = f" · ETA {int(float(remaining))}s" if remaining is not None else ""
    except (TypeError, ValueError):
        remaining_text = ""
    return Text(f"{task}  [{bar}] {pct_text}{remaining_text}", style="yellow")


def render_live_nmap_view(
    targets: Sequence[str],
    profile: str,
    ports: Optional[str],
    progress: Optional[Dict[str, Any]],
    completed_hosts: Sequence[Dict[str, Any]],
    elapsed: float,
    state: str,
    height: int = 24,
) -> RenderableType:
    """Build one bounded frame; rows are capped to the visible terminal area."""
    header = Table.grid(expand=True)
    header.add_column(ratio=1)
    header.add_column(justify="right")
    label = "LIVE VULNERABILITY SCAN" if profile == "vuln" else "LIVE NMAP SCAN"
    header.add_row(Text(f"NETSCOPE  /  {label}", style="bold cyan"), Text(_elapsed_text(elapsed), style="dim"))
    header.add_row(Text(f"Targets  {len(targets)} explicit host(s)", style="bold white"), Text(f"Profile  {profile}", style="yellow"))
    header.add_row(Text(f"Scope  {ports or ('top 20 TCP ports' if profile == 'vuln' else 'profile default')}", style="dim"), Text(f"State  {state}", style="dim"))

    target_table = Table(
        title=f"Batch targets · {min(len(completed_hosts), len(targets))}/{len(targets)} host result(s)",
        box=SIMPLE_HEAD, expand=True, show_lines=False, padding=(0, 1),
    )
    target_table.add_column("Target", ratio=2, overflow="fold")
    target_table.add_column("State", width=10)
    target_table.add_column("Open", justify="right", width=6)
    target_table.add_column("Ports", ratio=2, overflow="fold")
    target_table.add_column("NSE", justify="right", width=6)
    visible_hosts = max(2, min(len(targets), height - 16))
    host_lookup: Dict[str, Dict[str, Any]] = {}
    for host in completed_hosts:
        aliases = [host.get("target"), host.get("address"), *host.get("hostnames", [])]
        aliases.extend(address.get("address") for address in host.get("addresses", []))
        for alias in aliases:
            if alias:
                host_lookup[str(alias).lower()] = host
    for target in targets[:visible_hosts]:
        host = host_lookup.get(target.lower())
        services = host.get("services", []) if host else []
        open_ports = host.get("open_ports", []) if host else []
        target_name = host.get("target") or host.get("address") if host else target
        host_state = host.get("status", "unknown").upper() if host else "SCANNING"
        target_table.add_row(
            Text(str(target_name)),
            Text(host_state, style="green" if host_state == "UP" else "dim"),
            str(len(open_ports)),
            ", ".join(str(service.get("port")) for service in services if service.get("state") == "open") or "—",
            str(len(host.get("vulnerability_findings", []))) if host else "—",
        )
    if len(targets) > visible_hosts:
        target_table.caption = f"Showing {visible_hosts} of {len(targets)} explicit batch targets."

    findings = [
        (host.get("target") or host.get("address") or "unknown", item)
        for host in completed_hosts
        for item in host.get("vulnerability_findings", [])
    ]
    findings_table = Table(title="NSE script evidence", box=SIMPLE_HEAD, expand=True, show_lines=False, padding=(0, 1))
    findings_table.add_column("Target", ratio=1, overflow="fold")
    findings_table.add_column("Port", width=8)
    findings_table.add_column("Script", ratio=1, overflow="fold")
    findings_table.add_column("Evidence", ratio=3, overflow="ellipsis")
    for host_name, item in findings[-max(1, height - 17):]:
        port = item.get("port")
        port_label = f"{port}/{item.get('protocol') or 'tcp'}" if port else "host"
        finding_style = "red" if item.get("state") == "vulnerable" else "yellow"
        findings_table.add_row(
            Text(str(host_name)), port_label, Text(str(item.get("id", "script"))),
            Text(str(item.get("output") or "Script returned structured evidence"), style=finding_style),
        )
    if not findings:
        findings_table.add_row("—", "—", "—", Text("No vulnerability-script output received yet.", style="dim"))
    if len(findings) > max(1, height - 17):
        findings_table.caption = f"Showing latest {max(1, height - 17)} script evidence item(s)."

    footer = Text(
        "Progress is reported by Nmap; completed host results appear as they arrive.\n"
        "Press q or Ctrl+C to stop or close  ·  Safe NSE script evidence is not an exploit confirmation",
        style="dim",
        justify="center",
    )
    return Group(
        Panel(header, border_style="cyan", padding=(0, 1)),
        _progress_text(progress),
        target_table,
        findings_table,
        Align.center(footer),
    )


def run_live_nmap_dashboard(
    targets: Union[str, Sequence[str]],
    scanner: NmapScanTest,
    console: Console,
    profile: str = "service",
    ports: Optional[str] = None,
    timeout: int = 120,
    key_reader: Optional[Callable[[], Optional[str]]] = None,
) -> LiveNmapSession:
    """Run one multi-target Nmap process while rendering streamed XML events in place."""
    target_list = normalize_targets(targets)
    started = time.monotonic()
    event_queue: queue.Queue = queue.Queue()
    cancel_event = threading.Event()
    result_holder: List[TestResult] = []
    completed_hosts: List[Dict[str, Any]] = []
    progress: Optional[Dict[str, Any]] = None
    state = "Starting Nmap process"

    def on_progress(data: Dict[str, Any]) -> None:
        event_queue.put(("progress", data))

    def on_host(data: Dict[str, Any]) -> None:
        event_queue.put(("host", data))

    def run_scan() -> None:
        try:
            result = scanner.run_streaming(
                target_list,
                ports=ports,
                timeout=timeout,
                profile=profile,
                progress_callback=on_progress,
                host_callback=on_host,
                cancel_event=cancel_event,
            )
        except Exception as exc:
            now = datetime.now()
            result = TestResult(
                test_name="Nmap Vulnerability Scan" if profile == "vuln" else "Nmap Scan",
                target=", ".join(target_list),
                status="failure",
                timestamp=now,
                duration=time.monotonic() - started,
                metrics={"profile": profile, "targets": target_list, "target_count": len(target_list)},
                summary=f"Could not complete Nmap scan: {exc}",
                error=str(exc),
            )
        result_holder.append(result)
        event_queue.put(("done", None))

    worker = threading.Thread(target=run_scan, name="netscope-nmap-stream", daemon=True)
    worker.start()
    keyboard = nullcontext(key_reader) if key_reader is not None else single_key_reader()
    cancelled = False
    exit_requested = False
    last_frame_key = None

    try:
        with keyboard as read_key:
            with Live(
                render_live_nmap_view(target_list, profile, ports, progress, completed_hosts, 0, state, console.height),
                console=console,
                screen=not is_alternate_screen_active(),
                transient=False,
                redirect_stdout=False,
                redirect_stderr=False,
                auto_refresh=False,
                refresh_per_second=10,
            ) as live:
                while worker.is_alive() or not exit_requested:
                    key = read_key()
                    if key and key.lower() == "q" and not cancelled:
                        exit_requested = True
                        if worker.is_alive():
                            cancelled = True
                            cancel_event.set()
                            state = "Cancelling scan; preserving completed evidence…"
                        else:
                            state = "Closing completed scan view"

                    received_event = False
                    try:
                        kind, payload = event_queue.get(timeout=0.1)
                        received_event = True
                        pending = [(kind, payload)]
                        while True:
                            try:
                                pending.append(event_queue.get_nowait())
                            except queue.Empty:
                                break
                    except queue.Empty:
                        pending = []

                    for kind, payload in pending:
                        if kind == "progress":
                            progress = payload
                            state = str(payload.get("task", "Nmap scan"))
                        elif kind == "host":
                            completed_hosts.append(payload)
                            state = f"Received {len(completed_hosts)} of {len(target_list)} host result(s)"
                        elif kind == "done":
                            state = "Scan complete" if not cancelled else "Scan stopped by operator"

                    elapsed = time.monotonic() - started
                    frame_key = (
                        state,
                        len(completed_hosts),
                        tuple(sorted(progress.items())) if progress else None,
                        int(elapsed),
                    )
                    if received_event or frame_key != last_frame_key:
                        live.update(
                            render_live_nmap_view(
                                target_list, profile, ports, progress, completed_hosts,
                                elapsed, state, console.height,
                            ),
                            refresh=True,
                        )
                        last_frame_key = frame_key
                    if exit_requested and not worker.is_alive():
                        break
    except KeyboardInterrupt:
        exit_requested = True
        cancelled = worker.is_alive()
        if cancelled:
            cancel_event.set()
    finally:
        if worker.is_alive():
            cancel_event.set()
            worker.join(timeout=5)

    if result_holder:
        result = result_holder[0]
    else:
        now = datetime.now()
        result = TestResult(
            test_name="Nmap Vulnerability Scan" if profile == "vuln" else "Nmap Scan",
            target=", ".join(target_list),
            status="warning",
            timestamp=now,
            duration=time.monotonic() - started,
            metrics={"profile": profile, "targets": target_list, "target_count": len(target_list)},
            summary="Nmap scan is still stopping; completed evidence may be incomplete.",
            error="Operator cancelled the scan.",
        )
    cancelled = cancelled and result.status == "warning"
    if exit_requested:
        request_exit_after_interaction()
    return LiveNmapSession(result, cancelled, time.monotonic() - started)
