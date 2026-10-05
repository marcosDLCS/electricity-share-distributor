"""Console configuration, themes, and visual formatting utilities using Rich for esd."""

from __future__ import annotations

from rich.console import Console
from rich.theme import Theme

CUSTOM_THEME = Theme(
    {
        "info": "cyan",
        "warning": "yellow",
        "danger": "bold red",
        "success": "bold green",
        "highlight": "bold magenta",
        "metric": "bold bright_cyan",
        "dimmed": "dim white",
        "header": "bold white on dark_blue",
        "bar.high": "bold green",
        "bar.mid": "bold yellow",
        "bar.low": "bold red",
    }
)

console = Console(theme=CUSTOM_THEME)


def format_kwh(val: float) -> str:
    """Format energy value in kilowatt-hours with thousands separator and 2 decimal places."""
    return f"{val:,.2f} kWh"


def format_pct(val: float) -> str:
    """Format percentage value with 2 decimal places."""
    return f"{val:5.2f}%"


def format_beta(val: float) -> str:
    """Format allocation coefficient beta (0.0000 - 1.0000)."""
    return f"{val:6.4f}"


def make_percentage_bar(pct: float, width: int = 16) -> str:
    """Create a sleek visual block bar showing a percentage share (0.0 to 100.0).

    Args:
        pct: Percentage (0.0 to 100.0).
        width: Character width of the progress bar.

    Returns:
        Colorized string with filled and empty blocks.
    """
    pct_clamped = max(0.0, min(100.0, pct))
    filled_len = round((pct_clamped / 100.0) * width)
    empty_len = width - filled_len

    if pct >= 50.0:
        bar_color = "bright_cyan"
    elif pct >= 20.0:
        bar_color = "yellow"
    elif pct > 0.0:
        bar_color = "magenta"
    else:
        bar_color = "dim"

    bar = "█" * filled_len + "░" * empty_len
    return f"[{bar_color}]{bar}[/{bar_color}]"
