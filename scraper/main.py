#!/usr/bin/env python3
"""
Polymarket NBA Price Scraper - Main Entry Point

Captures moneyline price graphs from Polymarket NBA games hourly.

Usage:
    python -m scraper.main [OPTIONS]

Options:
    --headless / --no-headless  Run browser in headless mode (default: headless)
    --dry-run                   Run without saving to Excel
    --max-games N               Maximum number of games to process
"""

import sys
import time
from pathlib import Path
from typing import List, Optional

import typer
from playwright.sync_api import sync_playwright
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import (
    DEFAULT_HEADLESS,
    DEFAULT_VIEWPORT,
    REQUEST_DELAY,
    EXCEL_FILE_PATH,
)
from .games_scraper import get_games_for_today, GameInfo
from .game_screenshotter import process_game, GameScreenshotResult
from .excel_writer import append_results, get_row_count
from .utils import (
    get_today_date_str,
    get_eastern_now,
    ensure_screenshot_dir,
    log_info,
    log_success,
    log_warning,
    log_error,
)

app = typer.Typer(help="Polymarket NBA Price Scraper")
console = Console()


def print_banner():
    """Print the application banner."""
    console.print(
        Panel.fit(
            "[bold blue]Polymarket NBA Price Scraper[/bold blue]\n"
            "Captures moneyline price graphs hourly",
            title="PM Price SS",
        )
    )


def print_summary(results: List[GameScreenshotResult]):
    """Print a summary table of results."""
    table = Table(title="Scraping Results")
    table.add_column("Game", style="cyan")
    table.add_column("Home Price", justify="right")
    table.add_column("Away Price", justify="right")
    table.add_column("Screenshot", style="green")
    table.add_column("Status")

    for result in results:
        status = "[green]OK[/green]" if result.success else f"[red]{result.error_message}[/red]"
        home_price = f"{result.home_price:.2f}" if result.home_price else "-"
        away_price = f"{result.away_price:.2f}" if result.away_price else "-"
        screenshot = "Yes" if result.screenshot_path else "No"

        table.add_row(
            str(result.game),
            home_price,
            away_price,
            screenshot,
            status,
        )

    console.print(table)


def run_scraper(
    headless: bool = DEFAULT_HEADLESS,
    dry_run: bool = False,
    max_games: Optional[int] = None,
) -> List[GameScreenshotResult]:
    """
    Run the main scraping process.

    Args:
        headless: Whether to run the browser in headless mode
        dry_run: If True, don't save to Excel
        max_games: Maximum number of games to process (None for all)

    Returns:
        List of GameScreenshotResult objects
    """
    results = []
    today = get_today_date_str()
    now = get_eastern_now()

    log_info(f"Starting scrape at {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    log_info(f"Headless mode: {headless}")

    # Ensure screenshot directory exists
    ensure_screenshot_dir(today)

    with sync_playwright() as p:
        # Launch browser
        log_info("Launching browser...")
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(viewport=DEFAULT_VIEWPORT)
        page = context.new_page()

        try:
            # Get today's games
            games = get_games_for_today(page)

            if not games:
                log_warning("No games found for today. Exiting.")
                browser.close()
                return results

            log_info(f"Found {len(games)} games to process")

            # Limit games if specified
            if max_games is not None and max_games > 0:
                games = games[:max_games]
                log_info(f"Limited to {len(games)} games")

            # Process each game
            for i, game in enumerate(games):
                log_info(f"\n--- Processing game {i + 1}/{len(games)} ---")

                result = process_game(page, game, i)
                results.append(result)

                # Rate limiting between games
                if i < len(games) - 1:
                    log_info(f"Waiting {REQUEST_DELAY}s before next game...")
                    time.sleep(REQUEST_DELAY)

        except Exception as e:
            log_error(f"Error during scraping: {e}")

        finally:
            browser.close()
            log_info("Browser closed")

    return results


@app.command()
def main(
    headless: bool = typer.Option(
        DEFAULT_HEADLESS,
        "--headless/--no-headless",
        help="Run browser in headless mode",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Run without saving to Excel",
    ),
    max_games: Optional[int] = typer.Option(
        None,
        "--max-games",
        "-n",
        help="Maximum number of games to process",
    ),
):
    """
    Run the Polymarket NBA price scraper.

    Captures moneyline price graphs for all NBA games scheduled today.
    """
    print_banner()

    # Run the scraper
    results = run_scraper(
        headless=headless,
        dry_run=dry_run,
        max_games=max_games,
    )

    # Print summary
    console.print("\n")
    print_summary(results)

    # Count successes
    successful = sum(1 for r in results if r.success)
    failed = len(results) - successful

    console.print(f"\n[bold]Total:[/bold] {len(results)} games processed")
    console.print(f"[green]Successful:[/green] {successful}")
    if failed > 0:
        console.print(f"[red]Failed:[/red] {failed}")

    # Save to Excel (unless dry run)
    if not dry_run and results:
        log_info("\nSaving results to Excel...")
        appended = append_results(results, EXCEL_FILE_PATH)
        total_rows = get_row_count(EXCEL_FILE_PATH)
        console.print(f"[bold]Excel file:[/bold] {EXCEL_FILE_PATH}")
        console.print(f"[bold]Total rows:[/bold] {total_rows}")
    elif dry_run:
        log_info("\n[yellow]Dry run - results not saved to Excel[/yellow]")

    # Exit with appropriate code
    if successful == 0 and len(results) > 0:
        sys.exit(1)  # All failed


if __name__ == "__main__":
    app()
