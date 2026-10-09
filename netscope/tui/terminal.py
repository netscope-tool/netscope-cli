"""Terminal input and alternate-screen lifecycle helpers for NetScope."""
from __future__ import annotations

import os
import select
import sys
import threading
import time
from contextlib import contextmanager
from typing import Callable, Iterator, Optional

from rich.console import Console

_ALT_ENTER = "\x1b[?1049h"
_ALT_EXIT = "\x1b[0m\x1b[?25h\x1b[?1049l"
_CLEAR_ALT = "\x1b[2J\x1b[H\x1b[?25l"
_STATE_LOCK = threading.RLock()
_ACTIVE_SESSIONS = []


def is_alternate_screen_active() -> bool:
    """Return whether NetScope currently owns an alternate-screen session."""
    with _STATE_LOCK:
        return bool(_ACTIVE_SESSIONS)


def request_exit_after_interaction() -> None:
    """Skip the outer final-key prompt after an inner fullscreen view handled q/Ctrl+C."""
    with _STATE_LOCK:
        if _ACTIVE_SESSIONS:
            _ACTIVE_SESSIONS[-1]._exit_requested = True


def exit_requested() -> bool:
    """Return whether the active dashboard requested that NetScope exit."""
    with _STATE_LOCK:
        return bool(_ACTIVE_SESSIONS and _ACTIVE_SESSIONS[-1]._exit_requested)


def should_use_alternate_screen(args: Optional[list[str]] = None) -> bool:
    """Enable the full-screen lifecycle only for interactive terminal invocations."""
    args = list(sys.argv[1:] if args is None else args)
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return False
    if any(arg in {"--help", "-h", "--version", "-V", "--v"} for arg in args):
        return False
    for index, arg in enumerate(args):
        if arg.startswith("--format=") and arg.split("=", 1)[1].lower() == "json":
            return False
        if arg.startswith("-f=") and arg.split("=", 1)[1].lower() == "json":
            return False
        if arg in {"--format", "-f"} and index + 1 < len(args) and args[index + 1].lower() == "json":
            return False
    return True


class AlternateScreenSession:
    """Enter the terminal's alternate buffer once and restore it reliably on exit.

    The outer CLI session owns the buffer. Nested dashboards can detect that
    ownership and render with ``Live(screen=False)`` rather than switching
    buffers a second time. Direct commands keep their final frame visible until
    q/Ctrl+C; fullscreen sub-dashboards can consume that exit key themselves.
    """

    def __init__(
        self,
        console: Optional[Console] = None,
        *,
        enabled: Optional[bool] = None,
        wait_on_close: bool = True,
    ) -> None:
        self.console = console or Console()
        self.enabled = (
            bool(self.console.is_terminal and sys.stdin.isatty())
            if enabled is None else enabled
        )
        self.wait_on_close = wait_on_close
        self._entered = False
        self._closed = False
        self._exit_requested = False

    def __enter__(self) -> "AlternateScreenSession":
        if not self.enabled:
            return self
        with _STATE_LOCK:
            if not _ACTIVE_SESSIONS:
                output = self.console.file
                output.write(_ALT_ENTER + _CLEAR_ALT)
                output.flush()
            _ACTIVE_SESSIONS.append(self)
            self._entered = True
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        if self._closed or not self._entered:
            self._closed = True
            return False
        try:
            is_outermost = len(_ACTIVE_SESSIONS) == 1 and _ACTIVE_SESSIONS[-1] is self
            normal_completion = exc_type is None or (
                exc_type is not None
                and issubclass(exc_type, SystemExit)
                and getattr(exc_value, "code", None) in (None, 0)
            )
            if (
                is_outermost
                and self.wait_on_close
                and not self._exit_requested
                and normal_completion
            ):
                self._wait_for_exit_key()
        finally:
            with _STATE_LOCK:
                if self in _ACTIVE_SESSIONS:
                    _ACTIVE_SESSIONS.remove(self)
                if not _ACTIVE_SESSIONS:
                    output = self.console.file
                    output.write(_ALT_EXIT)
                    output.flush()
                self._closed = True
        return False

    def request_exit(self) -> None:
        """Close without a second key prompt after an inner screen used q/Ctrl+C."""
        self._exit_requested = True

    def _wait_for_exit_key(self) -> None:
        self.console.print("\n[dim]Press q or Ctrl+C to restore the terminal.[/dim]")
        try:
            with single_key_reader() as read_key:
                while True:
                    try:
                        key = read_key()
                    except KeyboardInterrupt:
                        break
                    if key and key.lower() in {"q", "\x03", "\x1b"}:
                        break
                    time.sleep(0.05)
        except (OSError, RuntimeError, ValueError):
            # A disconnected or non-interactive terminal must never strand the
            # process in raw mode or in the alternate buffer.
            pass


@contextmanager
def single_key_reader() -> Iterator[Callable[[], Optional[str]]]:
    """Read a key without echo or Enter and restore terminal mode on every exit path."""
    if not sys.stdin.isatty():
        raise RuntimeError("This live dashboard requires an interactive terminal.")

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
