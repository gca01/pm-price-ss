"""
Utility functions for the Polymarket NBA scraper.
"""

import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import pytz
from rich.console import Console

from .config import TIMEZONE, SCREENSHOTS_DIR, RETRY_ATTEMPTS, RETRY_DELAY

console = Console()


def get_eastern_now() -> datetime:
    """Get current datetime in US/Eastern timezone."""
    eastern = pytz.timezone(TIMEZONE)
    return datetime.now(eastern)


def get_today_date_str() -> str:
    """Get today's date as YYYY-MM-DD string in Eastern time."""
    return get_eastern_now().strftime("%Y-%m-%d")


def get_timestamp_str() -> str:
    """Get current timestamp as YYYYMMDD_HHMMSS string."""
    return get_eastern_now().strftime("%Y%m%d_%H%M%S")


def get_iso_timestamp() -> str:
    """Get current timestamp in ISO8601 format."""
    return get_eastern_now().isoformat()


def parse_price_text(price_text: str) -> Optional[float]:
    """
    Parse a price string like "SAC39¢" or "39¢" into a decimal (0.39).

    Args:
        price_text: Text containing a price with ¢ symbol

    Returns:
        Float between 0 and 1, or None if parsing fails
    """
    # Remove whitespace and newlines
    price_text = price_text.strip().replace("\n", "")

    # Find the number before ¢
    match = re.search(r"(\d+)\s*¢", price_text)
    if match:
        cents = int(match.group(1))
        return cents / 100.0

    return None


def extract_team_from_price(price_text: str) -> Optional[str]:
    """
    Extract team abbreviation from price text like "SAC39¢".

    Args:
        price_text: Text containing team and price

    Returns:
        Team abbreviation (e.g., "SAC") or None
    """
    price_text = price_text.strip().replace("\n", "")

    # Match 2-3 letter team code at the start
    match = re.match(r"^([A-Z]{2,3})", price_text)
    if match:
        return match.group(1)

    return None


def ensure_screenshot_dir(date_str: Optional[str] = None) -> Path:
    """
    Ensure the screenshot directory for a given date exists.

    Args:
        date_str: Date string in YYYY-MM-DD format. Uses today if None.

    Returns:
        Path to the screenshot directory
    """
    if date_str is None:
        date_str = get_today_date_str()

    dir_path = SCREENSHOTS_DIR / date_str
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def generate_screenshot_path(home_team: str, away_team: str, date_str: Optional[str] = None) -> Path:
    """
    Generate a unique screenshot file path.

    Args:
        home_team: Home team abbreviation
        away_team: Away team abbreviation
        date_str: Date string in YYYY-MM-DD format. Uses today if None.

    Returns:
        Full path for the screenshot file
    """
    if date_str is None:
        date_str = get_today_date_str()

    timestamp = get_timestamp_str()
    filename = f"{home_team}_{away_team}_{timestamp}.png"

    dir_path = ensure_screenshot_dir(date_str)
    return dir_path / filename


def sanitize_team_name(name: str) -> str:
    """
    Sanitize a team name for use in filenames.

    Args:
        name: Team name or abbreviation

    Returns:
        Sanitized string safe for filenames
    """
    # Remove any characters that aren't alphanumeric, space, or hyphen
    sanitized = re.sub(r"[^\w\s-]", "", name)
    # Replace spaces with underscores
    sanitized = sanitized.replace(" ", "_")
    return sanitized


def retry_on_failure(func, *args, max_attempts: int = RETRY_ATTEMPTS, delay: int = RETRY_DELAY, **kwargs):
    """
    Retry a function on failure with exponential backoff.

    Args:
        func: Function to call
        *args: Positional arguments for the function
        max_attempts: Maximum number of attempts
        delay: Initial delay between retries in seconds
        **kwargs: Keyword arguments for the function

    Returns:
        Result of the function call

    Raises:
        The last exception if all attempts fail
    """
    last_exception = None

    for attempt in range(1, max_attempts + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            if attempt < max_attempts:
                wait_time = delay * attempt  # Simple linear backoff
                console.print(
                    f"[yellow]Attempt {attempt}/{max_attempts} failed: {e}. "
                    f"Retrying in {wait_time}s...[/yellow]"
                )
                time.sleep(wait_time)
            else:
                console.print(f"[red]All {max_attempts} attempts failed.[/red]")

    raise last_exception


def log_success(message: str):
    """Log a success message."""
    console.print(f"[green]✓[/green] {message}")


def log_error(message: str):
    """Log an error message."""
    console.print(f"[red]✗[/red] {message}")


def log_warning(message: str):
    """Log a warning message."""
    console.print(f"[yellow]![/yellow] {message}")


def log_info(message: str):
    """Log an info message."""
    console.print(f"[blue]ℹ[/blue] {message}")
