"""Shared warm-neutral terminal palette for NetScope."""
from rich.theme import Theme

NETSCOPE_THEME = Theme(
    {
        "cyan": "#D97757",
        "bold cyan": "bold #D97757",
        "blue": "#B07A64",
        "bold blue": "bold #D97757",
        "green": "#8DB596",
        "bold green": "bold #8DB596",
        "yellow": "#E2BD72",
        "red": "#E27D72",
        "magenta": "#D6A184",
        "white": "#EEEAE2",
        "dim": "#AAA59A",
    },
    inherit=True,
)
