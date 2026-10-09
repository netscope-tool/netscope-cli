"""Entry point for the NetScope CLI application."""

import sys

from netscope.cli.main import app, console
from netscope.tui.terminal import AlternateScreenSession, should_use_alternate_screen


def main():
    """Run the CLI in a private terminal buffer when attached to a TTY."""
    session = AlternateScreenSession(
        console,
        enabled=should_use_alternate_screen(sys.argv[1:]),
        wait_on_close=True,
    )
    try:
        with session:
            try:
                app()
            except KeyboardInterrupt:
                session.request_exit()
                console.print("\n[dim]Cancelled by user. Terminal restored.[/dim]")
            except Exception as exc:
                session.request_exit()
                console.print(f"\n[bold red]Unexpected error:[/bold red] {exc}")
                sys.exit(1)
    except SystemExit:
        # Typer uses SystemExit for normal --help/version exits and error codes.
        # The session context has already restored the user's primary screen.
        raise


if __name__ == "__main__":
    main()
