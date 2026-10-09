"""Persistent, full-screen MTR session with a non-scrolling live route table."""
from __future__ import annotations

import os
import select
import shutil
import subprocess
import sys
import time
from collections import deque
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Iterator, Optional

from rich.align import Align
from rich.box import SIMPLE_HEAD
from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from netscope.modules.base import TestResult
from netscope.modules.mtr import MTRTest


@dataclass
class LiveMTRSession:
    """Summary returned when the user leaves the live terminal session."""

    result: Optional[TestResult]
    sample_count: int
    duration_seconds: float


@contextmanager
def _single_key_reader() -> Iterator[Callable[[], Optional[str]]]:
    """Read one key without echoing it or waiting for Enter; restore the TTY."""
    if not sys.stdin.isatty():
        raise RuntimeError("The live MTR dashboard requires an interactive terminal.")

    if os.name == "nt":
        import msvcrt

        def read_key() -> Optional[str]:
            return msvcrt.getwch() if msvcrt.kbhit() else None

        yield read_key
        return

    import termios
    import tty

    fd = sys.stdin.fileno()
    previous = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)

        def read_key() -> Optional[str]:
            ready, _, _ = select.select([sys.stdin], [], [], 0)
            return sys.stdin.read(1) if ready else None

        yield read_key
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, previous)


def _elapsed_text(seconds: float) -> str:
    whole = max(0, int(seconds))
    hours, remainder = divmod(whole, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _metric(hop: dict, key: str) -> str:
    value = hop.get(key)
    return "—" if value is None else f"{float(value):.1f}"


def render_live_mtr_view(
    target: str,
    cycles: int,
    sample_count: int,
    elapsed: float,
    latest: Optional[TestResult],
    state: str,
    height: int = 24,
) -> RenderableType:
    """Build the current frame; only the latest completed sample is shown."""
    status = latest.status.upper() if latest else "STARTING"
    status_style = {
        "SUCCESS": "green",
        "WARNING": "yellow",
        "FAILURE": "red",
    }.get(status, "yellow")
    updated = latest.timestamp.strftime("%H:%M:%S") if latest else "—"
    summary = latest.summary if latest and latest.summary else "Waiting for the first MTR report batch…"

    header = Table.grid(expand=True)
    header.add_column(ratio=1)
    header.add_column(justify="right")
    header.add_row(
        Text("NETSCOPE  /  LIVE MTR", style="bold cyan"),
        Text(f"{status}  ·  {updated}", style=f"bold {status_style}"),
    )
    header.add_row(Text(f"Target  {target}", style="bold white"), Text(f"Session  {_elapsed_text(elapsed)}", style="dim"))
    header.add_row(Text(f"State  {state}", style="yellow"), Text(f"Completed reports  {sample_count}", style="dim"))

    table = Table(
        title="Latest route sample" if latest else "Waiting for route sample",
        box=SIMPLE_HEAD,
        expand=True,
        show_lines=False,
        padding=(0, 1),
    )
    table.add_column("Hop", justify="right", style="dim", width=4)
    table.add_column("Node", ratio=2, overflow="fold")
    table.add_column("Loss", justify="right", width=8)
    table.add_column("Sent", justify="right", width=6)
    table.add_column("Last ms", justify="right", width=8)
    table.add_column("Avg ms", justify="right", width=8)
    table.add_column("Best ms", justify="right", width=8)
    table.add_column("Worst ms", justify="right", width=9)

    hops = (latest.metrics or {}).get("hop_details", []) if latest else []
    visible_rows = max(3, height - 11)
    for hop in hops[:visible_rows]:
        loss = hop.get("packet_loss_percent")
        loss_text = "—" if loss is None else f"{float(loss):.1f}%"
        loss_style = "green" if loss is not None and loss == 0 else (
            "yellow" if loss is not None and loss < 50 else "red"
        )
        table.add_row(
            str(hop.get("hop", "—")),
            Text(str(hop.get("host", "—"))),
            Text(loss_text, style=loss_style),
            str(hop.get("sent", "—")),
            _metric(hop, "last_ms"),
            _metric(hop, "avg_ms"),
            _metric(hop, "best_ms"),
            _metric(hop, "worst_ms"),
        )
    if not hops:
        table.add_row("—", Text("Waiting for MTR to discover route hops…", style="dim"), "—", "—", "—", "—", "—", "—")

    if len(hops) > visible_rows:
        table.caption = f"Showing {visible_rows} of {len(hops)} hops; the screen is not a history log."
    footer = Text(
        f"{summary}\nBatch size: {cycles} cycles  ·  Press q or Ctrl+C to stop  ·  The view refreshes in place",
        style="dim",
        justify="center",
    )
    return Group(
        Panel(header, border_style="cyan", padding=(0, 1)),
        table,
        Align.center(footer),
    )


def _stop_process(process: Optional[subprocess.Popen]) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.communicate(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()


def run_live_mtr_dashboard(
    target: str,
    scanner: MTRTest,
    console: Console,
    cycles: int = 5,
    key_reader: Optional[Callable[[], Optional[str]]] = None,
) -> LiveMTRSession:
    """Run successive MTR report batches in a persistent alternate-screen UI.

    ``cycles`` is the number of probes in each report batch. The completed
    report table is replaced in place; raw snapshots are bounded to the most
    recent twelve so long sessions do not grow memory without limit.
    """
    if not 1 <= cycles <= 100:
        raise ValueError("MTR cycles must be between 1 and 100")
    session_started = time.monotonic()
    executable = shutil.which("mtr")
    if not executable:
        result = scanner.run(target, cycles=cycles)
        return LiveMTRSession(result, 0, time.monotonic() - session_started)

    command = scanner.build_command(target, cycles, executable)
    raw_snapshots = deque(maxlen=12)
    latest: Optional[TestResult] = None
    sample_count = 0
    process: Optional[subprocess.Popen] = None
    sample_started: Optional[datetime] = None
    state = f"Starting report batch · {cycles} cycles"
    keyboard = nullcontext(key_reader) if key_reader is not None else _single_key_reader()

    try:
        with keyboard as read_key:
            with Live(
                render_live_mtr_view(target, cycles, sample_count, 0, latest, state, console.height),
                console=console,
                screen=True,
                transient=False,
                redirect_stdout=False,
                redirect_stderr=False,
                refresh_per_second=4,
            ) as live:
                while True:
                    key = read_key()
                    if key and key.lower() == "q":
                        break

                    if process is None:
                        sample_started = datetime.now()
                        try:
                            process = subprocess.Popen(
                                command,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True,
                            )
                            state = f"Sampling report batch {sample_count + 1} · {cycles} cycles"
                        except OSError as exc:
                            latest = scanner.result_from_report(
                                target, cycles, "", str(exc), returncode=1, started=sample_started,
                                failure_summary=f"Could not start mtr: {exc}", failure_error=str(exc),
                            )
                            state = "MTR process could not start"
                            break

                    returncode = process.poll()
                    if returncode is not None:
                        stdout, stderr = process.communicate()
                        latest = scanner.result_from_report(
                            target, cycles, stdout or "", stderr or "", returncode,
                            started=sample_started,
                        )
                        sample_count += 1
                        if latest.raw_output:
                            raw_snapshots.append(
                                f"=== Sample {sample_count} · {latest.timestamp.isoformat()} ===\n"
                                f"{latest.raw_output}"
                            )
                        process = None
                        state = f"Updated from report batch {sample_count} · sampling next batch"

                    elapsed = time.monotonic() - session_started
                    live.update(
                        render_live_mtr_view(
                            target, cycles, sample_count, elapsed, latest, state, console.height,
                        ),
                        refresh=True,
                    )
                    time.sleep(0.25)
    except KeyboardInterrupt:
        state = "Stopped with Ctrl+C"
    finally:
        _stop_process(process)

    duration = time.monotonic() - session_started
    if latest is not None:
        latest.duration = duration
        latest.metrics["live_sample_count"] = sample_count
        latest.metrics["session_duration_seconds"] = round(duration, 2)
        if raw_snapshots:
            latest.raw_output = "\n\n".join(raw_snapshots)
        latest.summary = (
            f"Live MTR session ended after {sample_count} completed report batch(es). "
            f"Latest sample: {latest.summary or 'no summary available'}"
        )
    return LiveMTRSession(latest, sample_count, duration)
