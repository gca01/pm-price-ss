"""
Game page screenshotter for Polymarket NBA.

Handles navigating to the graph view and capturing screenshots.
"""

import time
import requests
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, Dict, List

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
    is_final: bool = False  # True if game has ended (shows "Final" on page)
    home_low_price: Optional[float] = None  # Lowest price home team reached
    away_low_price: Optional[float] = None  # Lowest price away team reached


def fetch_price_history(market_id: str, interval: str = "max") -> List[Dict]:
    """
    Fetch price history from Polymarket CLOB API.

    Args:
        market_id: The market/token ID for the outcome
        interval: Time interval - "6h", "1d", "1w", "max"

    Returns:
        List of {t: timestamp, p: price} dicts
    """
    try:
        url = f"https://clob.polymarket.com/prices-history?interval={interval}&market={market_id}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get('history', [])
    except Exception as e:
        log_warning(f"Error fetching price history: {e}")
    return []


def get_min_price_from_history(history: List[Dict]) -> Optional[float]:
    """
    Get the minimum price from a price history list.

    Args:
        history: List of {t: timestamp, p: price} dicts

    Returns:
        Minimum price as float, or None if no data
    """
    if not history:
        return None

    prices = [entry.get('p', 1.0) for entry in history if 'p' in entry]
    if prices:
        return min(prices)
    return None


def extract_market_ids(page: Page) -> Dict[str, str]:
    """
    Extract market/token IDs from the page for each team.

    Args:
        page: Playwright page object (should be on game detail page)

    Returns:
        Dict mapping team abbreviation to market ID
    """
    try:
        # The market IDs are often in data attributes or can be found in network requests
        # We'll extract them from the price buttons which contain the token info
        market_ids = page.evaluate('''() => {
            const results = {};

            // Look for buttons with price info that might have data attributes
            const buttons = document.querySelectorAll('button');
            for (const btn of buttons) {
                const text = btn.innerText || '';
                // Match pattern like "PHX 87¢" or "OKC 13¢"
                const match = text.match(/^([A-Z]{2,3})\\s*(\\d+)¢$/);
                if (match) {
                    const team = match[1];
                    // Try to find token ID in parent elements or data attributes
                    let el = btn;
                    for (let i = 0; i < 10; i++) {
                        if (!el) break;
                        // Check for data attributes
                        const attrs = el.attributes;
                        for (let j = 0; j < attrs.length; j++) {
                            const attr = attrs[j];
                            if (attr.value && attr.value.length > 50 && /^\\d+$/.test(attr.value)) {
                                results[team] = attr.value;
                            }
                        }
                        el = el.parentElement;
                    }
                }
            }

            return results;
        }''')

        if market_ids:
            log_info(f"Found market IDs: {market_ids}")
            return market_ids

    except Exception as e:
        log_warning(f"Error extracting market IDs: {e}")

    return {}


def get_low_prices_from_api(page: Page, game: GameInfo) -> Tuple[Optional[float], Optional[float]]:
    """
    Get the lowest prices each team reached using the Polymarket API.

    The API returns away team prices. Home team price = 1 - away team price.
    So: away_low = min(away_prices), home_low = 1 - max(away_prices)

    Args:
        page: Playwright page object (on game detail page)
        game: GameInfo with team abbreviations

    Returns:
        Tuple of (home_low_price, away_low_price)
    """
    home_low = None
    away_low = None

    try:
        # Extract market/token ID from the page URL or page content
        # The token ID is needed to call the prices-history API directly

        # Method: Extract from page's JavaScript context
        market_id = page.evaluate('''() => {
            // Look for token IDs in the page - they're usually long numeric strings
            // Check script tags and data embedded in the page
            const scripts = document.querySelectorAll('script');
            for (const script of scripts) {
                const text = script.textContent || '';
                // Look for token patterns in JSON data
                const matches = text.match(/"token"\\s*:\\s*"(\\d{70,80})"/g);
                if (matches && matches.length > 0) {
                    // Extract the first token ID
                    const match = matches[0].match(/"(\\d{70,80})"/);
                    if (match) return match[1];
                }
            }

            // Also check for market IDs in URLs within the page
            const allText = document.body.innerText;
            const tokenMatch = allText.match(/\\b(\\d{70,80})\\b/);
            if (tokenMatch) return tokenMatch[1];

            return null;
        }''')

        if not market_id:
            # Try to get it from network requests by reloading the graph
            log_info("Trying to capture market ID from network...")
            captured_ids = []

            def capture_market_id(response):
                if 'prices-history' in response.url:
                    import re
                    match = re.search(r'market=(\d+)', response.url)
                    if match:
                        captured_ids.append(match.group(1))

            page.on("response", capture_market_id)

            # Click a different time period to force a new request
            try:
                # First click 1D, then Max to force new requests
                for btn_text in ["1D", "Max", "1W"]:
                    btn = page.get_by_text(btn_text, exact=True)
                    if btn.count() > 0:
                        btn.first.click()
                        time.sleep(1.5)
                        if captured_ids:
                            break
            except:
                pass

            page.remove_listener("response", capture_market_id)

            if captured_ids:
                market_id = captured_ids[0]
                log_info(f"Captured market ID: {market_id[:30]}...")

        if market_id:
            # Call the API directly - use 6h interval to match our graph timeframe
            log_info(f"Fetching price history from API (6h)...")
            url = f"https://clob.polymarket.com/prices-history?interval=6h&market={market_id}"
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                history = data.get('history', [])

                if history:
                    # Filter to last 6 hours just in case API returns more
                    import time as time_module
                    six_hours_ago = time_module.time() - (6 * 60 * 60)

                    # Filter prices to last 6 hours
                    recent_prices = [
                        entry.get('p', 0.5)
                        for entry in history
                        if 'p' in entry and entry.get('t', 0) >= six_hours_ago
                    ]

                    # If filtering removed all prices, use all prices from the response
                    if not recent_prices:
                        recent_prices = [entry.get('p', 0.5) for entry in history if 'p' in entry]

                    log_info(f"Got {len(recent_prices)} price points from last 6 hours")

                    if recent_prices:
                        away_low = min(recent_prices)  # Lowest away team price in last 6h
                        away_high = max(recent_prices)  # Highest away team price in last 6h
                        home_low = 1 - away_high  # Home team's low = 1 - away team's high

                        log_success(f"Low prices (6h) - {game.away}: {away_low:.2f}, {game.home}: {home_low:.2f}")
                else:
                    log_warning("API returned empty history")
            else:
                log_warning(f"API request failed with status {response.status_code}")
        else:
            log_warning("Could not find market ID for price history")

    except Exception as e:
        log_warning(f"Error getting low prices from API: {e}")

    return home_low, away_low


def check_if_game_final(page: Page) -> bool:
    """
    Check if the game page shows "Final" (game has ended).

    Args:
        page: Playwright page object (should be on a game detail page)

    Returns:
        True if the game shows "Final" status, False otherwise
    """
    try:
        # Look for "Final" text on the page (appears as a badge/pill at top of game card)
        final_locator = page.get_by_text("Final", exact=True)

        # Check if the Final element exists and is visible
        if final_locator.count() > 0:
            log_info("Game shows 'Final' status - game has ended")
            return True

        return False
    except Exception as e:
        log_warning(f"Error checking if game is final: {e}")
        return False


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
        # Make sure we're on the games page and games are loaded
        from .games_scraper import click_game_view, wait_for_games_to_load
        from .config import RETRY_ATTEMPTS, RETRY_DELAY

        # Retry loading the games page if needed
        games_loaded = False
        for attempt in range(RETRY_ATTEMPTS):
            if "sports/nba/games" not in page.url:
                page.goto(POLYMARKET_NBA_URL)
                page.wait_for_load_state("networkidle", timeout=NETWORK_IDLE_TIMEOUT)

            # Wait for game view buttons to be available
            if wait_for_games_to_load(page):
                games_loaded = True
                break
            else:
                log_warning(f"Retry {attempt + 1}/{RETRY_ATTEMPTS} loading games page...")
                page.goto(POLYMARKET_NBA_URL)
                time.sleep(RETRY_DELAY)

        if not games_loaded:
            result.error_message = "Failed to load games page"
            return result

        # Click into the game
        if not click_game_view(page, game_index):
            result.error_message = "Failed to click Game View"
            return result

        # Capture the game URL from the browser address bar
        game.url = page.url
        log_info(f"Captured game URL: {game.url}")

        # Check if the game has ended (shows "Final")
        result.is_final = check_if_game_final(page)

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

        # Get low prices from API (by switching to "Max" time period)
        result.home_low_price, result.away_low_price = get_low_prices_from_api(page, game)

        # Switch back to 6H for screenshot
        select_time_period(page, "6H")
        time.sleep(1)

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
            # Wait longer for the page to fully reload with all games
            time.sleep(3)
        except Exception:
            pass

    return result


def process_game_by_url(page: Page, game: GameInfo) -> GameScreenshotResult:
    """
    Process a game by navigating directly to its URL.

    Used for games that are no longer on the "Today's games" page
    but we have the URL stored from a previous scrape.

    Args:
        page: Playwright page object
        game: GameInfo object with url field populated

    Returns:
        GameScreenshotResult with all captured data
    """
    log_info(f"Processing game by URL: {game} -> {game.url}")

    result = GameScreenshotResult(
        game=game,
        screenshot_path=None,
        home_price=None,
        away_price=None,
        success=False,
    )

    if not game.url:
        result.error_message = "No URL available for game"
        return result

    try:
        from .config import RETRY_ATTEMPTS, RETRY_DELAY

        # Navigate directly to the game URL
        navigated = False
        for attempt in range(RETRY_ATTEMPTS):
            try:
                page.goto(game.url)
                page.wait_for_load_state("networkidle", timeout=NETWORK_IDLE_TIMEOUT)
                time.sleep(2)  # Wait for content to render
                navigated = True
                break
            except Exception as e:
                log_warning(f"Retry {attempt + 1}/{RETRY_ATTEMPTS} navigating to game URL: {e}")
                time.sleep(RETRY_DELAY)

        if not navigated:
            result.error_message = "Failed to navigate to game URL"
            return result

        # Check if the game has ended (shows "Final")
        result.is_final = check_if_game_final(page)

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

        # Get low prices from API (by switching to "Max" time period)
        result.home_low_price, result.away_low_price = get_low_prices_from_api(page, game)

        # Switch back to 6H for screenshot
        select_time_period(page, "6H")
        time.sleep(1)

        # Capture screenshot
        result.screenshot_path = capture_chart_screenshot(page, game)

        if result.screenshot_path:
            result.success = True
            if result.is_final:
                log_success(f"Successfully captured FINAL screenshot for {game}")
            else:
                log_success(f"Successfully processed {game}")
        else:
            result.error_message = "Screenshot capture failed"

    except Exception as e:
        result.error_message = str(e)
        log_error(f"Error processing game by URL {game}: {e}")

    return result
