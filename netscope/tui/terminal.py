"""Cross-platform single-key input for alternate-screen terminal sessions."""
from __future__ import annotations

import os
import select
import sys
from contextlib import contextmanager
from typing import Callable, Iterator, Optional


@contextmanager
def single_key_reader() -> Iterator[Callable[[], Optional[str]]]:
    """Read a key without echo or Enter and restore the terminal on every exit path."""
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
