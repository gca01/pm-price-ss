"""
Game page screenshotter for Polymarket NBA.

Handles navigating to the graph view and capturing screenshots.
"""

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout

from .config import (
    PAGE_LOAD_TIMEOUT,
    GRAPH_RENDER_WAIT,
    NETWORK_IDLE_TIMEOUT,
    REQUEST_DELAY,
    POLYMARKET_NBA_URL,
)
from .selectors import (
    get_moneyline_locator,
    get_graph_locator,
    get_time_period_locator,
    get_chart_locator,
    get_price_buttons_locator,
    GamePageSelectors,
)
from .utils import (
    parse_price_text,
    extract_team_from_price,
    generate_screenshot_path,
    log_info,
    log_success,
    log_warning,
    log_error,
)
from .games_scraper import GameInfo


@dataclass
class GameScreenshotResult:
    """Result of capturing a game's graph screenshot."""

    game: GameInfo
    screenshot_path: Optional[Path]
    home_price: Optional[float]
    away_price: Optional[float]
    success: bool
    error_message: Optional[str] = None


def navigate_to_moneyline(page: Page) -> bool:
    """
    Navigate to the Moneyline tab on a game page.

    Args:
        page: Playwright page object (should be on a game detail page)

    Returns:
        True if navigation succeeded, False otherwise
    """
    try:
        moneyline = get_moneyline_locator(page)

        # Check if Moneyline exists
        if moneyline.count() == 0:
            log_warning("No Moneyline tab found - this game may not have a moneyline market")
            return False

        # Click Moneyline
        moneyline.first.click()
        time.sleep(1)  # Brief wait for tab to activate

        log_success("Navigated to Moneyline")
        return True

    except PlaywrightTimeout:
        log_warning("Timeout navigating to Moneyline")
        return False
    except Exception as e:
        log_error(f"Error navigating to Moneyline: {e}")
        return False


def navigate_to_graph(page: Page) -> bool:
    """
    Navigate to the Graph tab on a game page.

    Args:
        page: Playwright page object (should be on Moneyline tab)

    Returns:
        True if navigation succeeded, False otherwise
    """
    try:
        graph = get_graph_locator(page)

        if graph.count() == 0:
            log_warning("No Graph tab found")
            return False

        graph.first.click()
        time.sleep(1)

        log_success("Navigated to Graph")
        return True

    except PlaywrightTimeout:
        log_warning("Timeout navigating to Graph")
        return False
    except Exception as e:
        log_error(f"Error navigating to Graph: {e}")
        return False


def select_time_period(page: Page, period: str = "6H") -> bool:
    """
    Select a time period for the graph.

    Args:
        page: Playwright page object (should be on Graph tab)
        period: Time period to select (6H, 1D, 1W, 1M, ALL)

    Returns:
        True if selection succeeded, False otherwise
    """
    try:
        time_btn = get_time_period_locator(page, period)

        if time_btn.count() == 0:
            log_warning(f"No {period} button found")
            return False

        time_btn.first.click()
        time.sleep(GRAPH_RENDER_WAIT)  # Wait for graph to re-render

        log_success(f"Selected {period} time period")
        return True

    except PlaywrightTimeout:
        log_warning(f"Timeout selecting {period}")
        return False
    except Exception as e:
        log_error(f"Error selecting time period: {e}")
        return False


def wait_for_chart(page: Page) -> bool:
    """
    Wait for the chart to fully render.

    Args:
        page: Playwright page object

    Returns:
        True if chart is ready, False otherwise
    """
    try:
        # Wait for chart container
        chart = get_chart_locator(page)
        chart.wait_for(timeout=PAGE_LOAD_TIMEOUT)

        # Wait for SVG to render
        page.wait_for_selector(
            GamePageSelectors.CHART_SVG,
            timeout=PAGE_LOAD_TIMEOUT
        )

        # Additional wait for data to load
        time.sleep(GRAPH_RENDER_WAIT)

        return True

    except PlaywrightTimeout:
        log_warning("Timeout waiting for chart to render")
        return False
    except Exception as e:
        log_error(f"Error waiting for chart: {e}")
        return False


def capture_chart_screenshot(page: Page, game: GameInfo) -> Optional[Path]:
    """
    Capture a screenshot of the chart.

    Args:
        page: Playwright page object
        game: GameInfo object for the current game

    Returns:
        Path to the screenshot file, or None if capture failed
    """
    try:
        # Get the chart container
        chart = get_chart_locator(page)

        if chart.count() == 0:
            log_error("No chart element found for screenshot")
            return None

        # Generate screenshot path
        screenshot_path = generate_screenshot_path(game.home, game.away, game.game_date)

        # Scroll chart into view
        chart.first.scroll_into_view_if_needed()
        time.sleep(0.5)

        # Take screenshot of just the chart
        chart.first.screenshot(path=str(screenshot_path))

        log_success(f"Screenshot saved: {screenshot_path}")
        return screenshot_path

    except Exception as e:
        log_error(f"Error capturing screenshot: {e}")
        return None


def extract_moneyline_prices(page: Page, game: GameInfo) -> Tuple[Optional[float], Optional[float]]:
    """
    Extract the current moneyline prices from the game page.

    Args:
        page: Playwright page object
        game: GameInfo object with team information

    Returns:
        Tuple of (home_price, away_price) as floats, or (None, None) if extraction fails
    """
    home_price = None
    away_price = None

    try:
        # Find all price buttons
        price_buttons = get_price_buttons_locator(page)
        buttons = price_buttons.all()

        for btn in buttons:
            text = btn.inner_text()
            team = extract_team_from_price(text)
            price = parse_price_text(text)

            if team and price is not None:
                if team == game.home:
                    home_price = price
                elif team == game.away:
                    away_price = price

        if home_price is not None and away_price is not None:
            log_success(f"Prices: {game.home}={home_price:.2f}, {game.away}={away_price:.2f}")
        else:
            log_warning(f"Could not extract all prices (home={home_price}, away={away_price})")

    except Exception as e:
        log_error(f"Error extracting prices: {e}")

    return home_price, away_price


def process_game(page: Page, game: GameInfo, game_index: int) -> GameScreenshotResult:
    """
    Process a single game: navigate to graph, capture screenshot, extract prices.

    Args:
        page: Playwright page object (should be on NBA games page)
        game: GameInfo object for the game to process
        game_index: Index of the game on the games page

    Returns:
        GameScreenshotResult with all captured data
    """
    log_info(f"Processing game: {game}")

    result = GameScreenshotResult(
        game=game,
        screenshot_path=None,
        home_price=None,
        away_price=None,
        success=False,
    )

    try:
        # Make sure we're on the games page
        if "sports/nba/games" not in page.url:
            page.goto(POLYMARKET_NBA_URL)
            page.wait_for_load_state("networkidle", timeout=NETWORK_IDLE_TIMEOUT)
            time.sleep(2)

        # Click into the game
        from .games_scraper import click_game_view
        if not click_game_view(page, game_index):
            result.error_message = "Failed to click Game View"
            return result

        # Navigate to Moneyline
        if not navigate_to_moneyline(page):
            result.error_message = "No Moneyline market available"
            return result

        # Navigate to Graph
        if not navigate_to_graph(page):
            result.error_message = "Failed to navigate to Graph"
            return result

        # Select 6H time period
        if not select_time_period(page, "6H"):
            result.error_message = "Failed to select 6H time period"
            return result

        # Wait for chart to render
        if not wait_for_chart(page):
            result.error_message = "Chart failed to render"
            return result

        # Extract prices
        result.home_price, result.away_price = extract_moneyline_prices(page, game)

        # Capture screenshot
        result.screenshot_path = capture_chart_screenshot(page, game)

        if result.screenshot_path:
            result.success = True
            log_success(f"Successfully processed {game}")
        else:
            result.error_message = "Screenshot capture failed"

    except Exception as e:
        result.error_message = str(e)
        log_error(f"Error processing game {game}: {e}")

    finally:
        # Navigate back to games page for next game
        try:
            page.goto(POLYMARKET_NBA_URL)
            page.wait_for_load_state("networkidle", timeout=NETWORK_IDLE_TIMEOUT)
            time.sleep(REQUEST_DELAY)
        except Exception:
            pass

    return result
