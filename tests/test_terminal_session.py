"""Regression tests for NetScope's alternate-screen lifecycle."""
from contextlib import contextmanager
from io import StringIO

import pytest
from rich.console import Console

from netscope import __main__ as entrypoint
from netscope.tui import terminal


def _fake_key_reader(key="q"):
    @contextmanager
    def reader():
        yield lambda: key
    return reader


def test_session_enters_and_restores_alternate_buffer_without_leaking_state():
    output = StringIO()
    console = Console(file=output, force_terminal=True)
    session = terminal.AlternateScreenSession(console, enabled=True, wait_on_close=False)

    with session:
        assert terminal.is_alternate_screen_active()
        console.print("inside TUI")

    rendered = output.getvalue()
    assert "\x1b[?1049h" in rendered
    assert "\x1b[?1049l" in rendered
    assert "inside TUI" in rendered
    assert not terminal.is_alternate_screen_active()


def test_screen_activation_requires_tty_and_preserves_json_and_help_modes(monkeypatch):
    class TTY:
        def isatty(self):
            return True

    monkeypatch.setattr(terminal.sys, "stdin", TTY())
    monkeypatch.setattr(terminal.sys, "stdout", TTY())
    assert terminal.should_use_alternate_screen(["ping", "example.test"])
    assert not terminal.should_use_alternate_screen(["ping", "example.test", "--format", "json"])
    assert not terminal.should_use_alternate_screen(["mtr", "example.test", "-f=json"])
    assert not terminal.should_use_alternate_screen(["--help"])

    class Pipe:
        def isatty(self):
            return False

    monkeypatch.setattr(terminal.sys, "stdout", Pipe())
    assert not terminal.should_use_alternate_screen(["ping", "example.test"])


def test_nested_sessions_switch_terminal_buffer_only_once():
    outer_output, inner_output = StringIO(), StringIO()
    outer = terminal.AlternateScreenSession(
        Console(file=outer_output, force_terminal=True), enabled=True, wait_on_close=False,
    )
    inner = terminal.AlternateScreenSession(
        Console(file=inner_output, force_terminal=True), enabled=True, wait_on_close=False,
    )

    with outer:
        with inner:
            assert terminal.is_alternate_screen_active()
        assert terminal.is_alternate_screen_active()

    assert outer_output.getvalue().count("\x1b[?1049h") == 1
    assert outer_output.getvalue().count("\x1b[?1049l") == 1
    assert "\x1b[?1049h" not in inner_output.getvalue()
    assert not terminal.is_alternate_screen_active()


def test_completed_direct_command_waits_for_q_then_restores(monkeypatch):
    monkeypatch.setattr(terminal, "single_key_reader", _fake_key_reader("q"))
    output = StringIO()
    console = Console(file=output, force_terminal=True)

    with terminal.AlternateScreenSession(console, enabled=True, wait_on_close=True):
        console.print("final report")

    rendered = output.getvalue()
    assert "final report" in rendered
    assert "Press q or Ctrl+C" in rendered
    assert rendered.index("Press q or Ctrl+C") < rendered.index("\x1b[?1049l")


def test_successful_typer_system_exit_still_waits_for_q(monkeypatch):
    monkeypatch.setattr(terminal, "single_key_reader", _fake_key_reader("q"))
    output = StringIO()
    console = Console(file=output, force_terminal=True)
    session = terminal.AlternateScreenSession(console, enabled=True, wait_on_close=True)

    with pytest.raises(SystemExit) as caught:
        with session:
            console.print("command completed")
            raise SystemExit(0)

    assert caught.value.code == 0
    assert "Press q or Ctrl+C" in output.getvalue()
    assert "\x1b[?1049l" in output.getvalue()


def test_inner_dashboard_exit_skips_duplicate_final_key_prompt(monkeypatch):
    def unexpected_reader():
        raise AssertionError("should not wait for a second q")

    monkeypatch.setattr(terminal, "single_key_reader", unexpected_reader)
    output = StringIO()
    console = Console(file=output, force_terminal=True)

    with terminal.AlternateScreenSession(console, enabled=True, wait_on_close=True):
        terminal.request_exit_after_interaction()
        assert terminal.exit_requested()

    assert "Press q or Ctrl+C" not in output.getvalue()
    assert "\x1b[?1049l" in output.getvalue()
    assert not terminal.exit_requested()


def test_exception_restores_primary_buffer_without_waiting_for_key():
    output = StringIO()
    console = Console(file=output, force_terminal=True)
    session = terminal.AlternateScreenSession(console, enabled=True, wait_on_close=True)

    with pytest.raises(RuntimeError):
        with session:
            raise RuntimeError("test failure")

    assert "\x1b[?1049l" in output.getvalue()
    assert not terminal.is_alternate_screen_active()


def test_entrypoint_wraps_application_and_restores_on_keyboard_interrupt(monkeypatch):
    output = StringIO()
    console = Console(file=output, force_terminal=True)
    monkeypatch.setattr(entrypoint, "console", console)
    monkeypatch.setattr(entrypoint, "should_use_alternate_screen", lambda _args: True)
    monkeypatch.setattr(entrypoint, "app", lambda: (_ for _ in ()).throw(KeyboardInterrupt()))
    monkeypatch.setattr(terminal, "single_key_reader", _fake_key_reader("q"))

    entrypoint.main()

    rendered = output.getvalue()
    assert "\x1b[?1049h" in rendered
    assert "Cancelled by user" in rendered
    assert "\x1b[?1049l" in rendered
    assert "Press q or Ctrl+C" not in rendered
