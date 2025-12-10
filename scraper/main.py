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
from .game_screenshotter import process_game, process_game_by_url, GameScreenshotResult
from .excel_writer import append_results, get_entry_count, get_sheet_names, get_existing_games, GameState
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
    table.add_column("Current", justify="right")
    table.add_column("Low", justify="right", style="yellow")
    table.add_column("Screenshot", style="green")
    table.add_column("Final", justify="center")
    table.add_column("Status")

    for result in results:
        status = "[green]OK[/green]" if result.success else f"[red]{result.error_message}[/red]"
        # Current prices
        home_price = f"{int(result.home_price * 100)}¢" if result.home_price else "-"
        away_price = f"{int(result.away_price * 100)}¢" if result.away_price else "-"
        current = f"{result.game.away} {away_price} / {result.game.home} {home_price}"
        # Low prices
        home_low = f"{int(result.home_low_price * 100)}¢" if result.home_low_price else "-"
        away_low = f"{int(result.away_low_price * 100)}¢" if result.away_low_price else "-"
        low = f"{result.game.away} {away_low} / {result.game.home} {home_low}"
        screenshot = "Yes" if result.screenshot_path else "No"
        is_final = "[bold green]FINAL[/bold green]" if result.is_final else "-"

        table.add_row(
            str(result.game),
            current,
            low,
            screenshot,
            is_final,
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

    # Get existing games from Excel for today
    existing_games = get_existing_games(EXCEL_FILE_PATH, today)
    if existing_games:
        log_info(f"Found {len(existing_games)} existing games in Excel for today")
        for game_id, state in existing_games.items():
            status = "FINAL" if state.is_final else "in progress"
            log_info(f"  - {game_id}: {status}")

    with sync_playwright() as p:
        # Launch browser
        log_info("Launching browser...")
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(viewport=DEFAULT_VIEWPORT)
        page = context.new_page()

        try:
            # Get today's games from Polymarket
            games = get_games_for_today(page)
            today_game_ids = {game.game_id for game in games}

            log_info(f"Found {len(games)} games on Polymarket for today")

            # Limit games if specified
            if max_games is not None and max_games > 0:
                games = games[:max_games]
                log_info(f"Limited to {len(games)} games")

            # Process each game from today's page
            for i, game in enumerate(games):
                log_info(f"\n--- Processing game {i + 1}/{len(games)} ---")

                # Use game.page_index to click the correct game on the page
                result = process_game(page, game, game.page_index)
                results.append(result)

                # Rate limiting between games
                if i < len(games) - 1:
                    log_info(f"Waiting {REQUEST_DELAY}s before next game...")
                    time.sleep(REQUEST_DELAY)

            # Process games that are in Excel but no longer on today's page
            # (games that may have ended and been removed from the main list)
            games_to_check_by_url = []
            for game_id, state in existing_games.items():
                if game_id not in today_game_ids:
                    if state.is_final:
                        log_info(f"Skipping {game_id} - already marked as FINAL")
                    elif state.url:
                        log_info(f"Game {game_id} not on today's page, will check by URL")
                        games_to_check_by_url.append(state)
                    else:
                        log_warning(f"Game {game_id} not on today's page and no URL stored - skipping")

            # Process games by URL
            if games_to_check_by_url:
                log_info(f"\n=== Processing {len(games_to_check_by_url)} games by URL ===")

                for i, state in enumerate(games_to_check_by_url):
                    log_info(f"\n--- Processing game by URL {i + 1}/{len(games_to_check_by_url)} ---")

                    # Create a GameInfo from the stored state
                    # Parse game_id format: "YYYY-MM-DD_Away_Home"
                    parts = state.game_id.split("_")
                    if len(parts) >= 3:
                        game_date = parts[0]
                        away_team = parts[1]
                        home_team = parts[2]

                        game = GameInfo(
                            home=home_team,
                            away=away_team,
                            start_time=None,
                            game_date=game_date,
                            url=state.url,
                            page_index=-1,  # Not on page
                        )

                        result = process_game_by_url(page, game)
                        results.append(result)

                        # Rate limiting
                        if i < len(games_to_check_by_url) - 1:
                            log_info(f"Waiting {REQUEST_DELAY}s before next game...")
                            time.sleep(REQUEST_DELAY)
                    else:
                        log_warning(f"Could not parse game_id: {state.game_id}")

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
        today = get_today_date_str()
        entry_counts = get_entry_count(EXCEL_FILE_PATH, today)
        sheets = get_sheet_names(EXCEL_FILE_PATH)
        console.print(f"[bold]Excel file:[/bold] {EXCEL_FILE_PATH}")
        console.print(f"[bold]Date sheets:[/bold] {len(sheets)} ({', '.join(sheets[-3:]) if sheets else 'none'})")
        console.print(f"[bold]Entries today:[/bold] {sum(entry_counts.values())} across {len(entry_counts)} games")
    elif dry_run:
        log_info("\n[yellow]Dry run - results not saved to Excel[/yellow]")

    # Exit with appropriate code
    if successful == 0 and len(results) > 0:
        sys.exit(1)  # All failed


if __name__ == "__main__":
    app()
