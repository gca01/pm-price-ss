"""
Games page scraper for Polymarket NBA.

Handles parsing the main NBA games page and extracting game information.
"""

import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout

from .config import (
    POLYMARKET_NBA_URL,
    PAGE_LOAD_TIMEOUT,
    NETWORK_IDLE_TIMEOUT,
)
from .selectors import get_game_view_locator
from .utils import (
    get_today_date_str,
    log_info,
    log_success,
    log_warning,
    log_error,
)


@dataclass
class GameInfo:
    """Information about a single NBA game."""

    home: str
    away: str
    start_time: Optional[str]
    game_date: str
    url: Optional[str] = None

    @property
    def game_id(self) -> str:
        """Generate unique game ID: 'YYYY-MM-DD_Away_Home'."""
        return f"{self.game_date}_{self.away}_{self.home}"

    def __str__(self) -> str:
        return f"{self.away} @ {self.home} ({self.game_date})"


def wait_for_games_to_load(page: Page, timeout: int = PAGE_LOAD_TIMEOUT) -> bool:
    """
    Wait for the games page to fully load.

    Args:
        page: Playwright page object
        timeout: Maximum time to wait in milliseconds

    Returns:
        True if games loaded successfully, False otherwise
    """
    try:
        # Wait for network to be idle
        page.wait_for_load_state("networkidle", timeout=NETWORK_IDLE_TIMEOUT)

        # Wait for at least one "Game View" element to appear
        game_view = get_game_view_locator(page)
        game_view.first.wait_for(timeout=timeout)

        # Additional wait for any animations/rendering
        time.sleep(2)

        return True
    except PlaywrightTimeout:
        log_warning("Timeout waiting for games to load")
        return False
    except Exception as e:
        log_error(f"Error waiting for games: {e}")
        return False


def extract_game_info_from_row(page: Page, game_index: int) -> Optional[GameInfo]:
    """
    Extract game information from a game row.

    This function analyzes the page around a "Game View" button to extract
    team names and game information.

    Args:
        page: Playwright page object
        game_index: Index of the game (0-based)

    Returns:
        GameInfo object or None if extraction fails
    """
    try:
        # Get game info by evaluating JavaScript on the page
        game_data = page.evaluate(
            """(index) => {
            // Find all elements containing exactly "Game View" text
            const gameViewElements = [];
            const walker = document.createTreeWalker(
                document.body,
                NodeFilter.SHOW_TEXT,
                null,
                false
            );

            while (walker.nextNode()) {
                if (walker.currentNode.textContent.trim() === 'Game View') {
                    gameViewElements.push(walker.currentNode.parentElement);
                }
            }

            if (index >= gameViewElements.length) return null;

            const gameViewEl = gameViewElements[index];

            // Navigate up to find the game row container
            // Look for a container that has exactly 2 moneyline price buttons
            let container = gameViewEl;
            for (let i = 0; i < 20 && container; i++) {
                container = container.parentElement;
                if (!container) break;

                // Look for moneyline price buttons in this container
                // Moneyline buttons have format like "SAC39¢" (no +/- spread)
                const allButtons = container.querySelectorAll('button');
                const moneylinePrices = [];

                for (const btn of allButtons) {
                    const text = btn.innerText?.replace(/\\s+/g, '');
                    if (text && text.includes('¢')) {
                        // Match team code followed by price, no +/- (excludes spreads)
                        const match = text.match(/^([A-Z]{2,3})(\\d+)¢$/);
                        if (match) {
                            moneylinePrices.push({
                                team: match[1],
                                price: parseInt(match[2]),
                                element: btn
                            });
                        }
                    }
                }

                // We need exactly 2 moneyline prices for a valid game row
                if (moneylinePrices.length === 2) {
                    // Find time element (format like "1:00 PM")
                    const timeMatch = container.innerText.match(/(\\d{1,2}:\\d{2}\\s*(?:AM|PM))/i);
                    const startTime = timeMatch ? timeMatch[1] : null;

                    // First team in the row is away, second is home
                    return {
                        away: moneylinePrices[0].team,
                        home: moneylinePrices[1].team,
                        awayPrice: moneylinePrices[0].price,
                        homePrice: moneylinePrices[1].price,
                        startTime: startTime
                    };
                }
            }

            return null;
        }""",
            game_index,
        )

        if game_data:
            return GameInfo(
                home=game_data["home"],
                away=game_data["away"],
                start_time=game_data.get("startTime"),
                game_date=get_today_date_str(),
            )

    except Exception as e:
        log_warning(f"Could not extract game info for index {game_index}: {e}")

    return None


def get_games_for_today(page: Page) -> List[GameInfo]:
    """
    Get all NBA games scheduled for today.

    Args:
        page: Playwright page object (should be on the NBA games page)

    Returns:
        List of GameInfo objects for today's games
    """
    games = []
    today = get_today_date_str()

    log_info(f"Looking for games on {today}...")

    # Navigate to the NBA games page
    log_info(f"Navigating to {POLYMARKET_NBA_URL}")
    page.goto(POLYMARKET_NBA_URL)

    if not wait_for_games_to_load(page):
        log_error("Failed to load games page")
        return games

    # Count how many "Game View" buttons we have
    game_view_locator = get_game_view_locator(page)
    game_count = game_view_locator.count()

    log_info(f"Found {game_count} games on the page")

    if game_count == 0:
        log_warning("No games found on the page")
        return games

    # Extract info for each game
    for i in range(game_count):
        game_info = extract_game_info_from_row(page, i)
        if game_info:
            games.append(game_info)
            log_success(f"Found game: {game_info}")
        else:
            log_warning(f"Could not extract info for game {i + 1}")

    # Deduplicate games (in case same game was found multiple times)
    seen_ids = set()
    unique_games = []
    for game in games:
        if game.game_id not in seen_ids:
            seen_ids.add(game.game_id)
            unique_games.append(game)

    log_info(f"Successfully extracted {len(unique_games)} unique games")
    return unique_games


def click_game_view(page: Page, game_index: int = 0) -> bool:
    """
    Click the "Game View" button for a specific game.

    Args:
        page: Playwright page object
        game_index: Index of the game to click (0-based)

    Returns:
        True if click succeeded, False otherwise
    """
    try:
        game_view_locator = get_game_view_locator(page)
        game_views = game_view_locator.all()

        if game_index >= len(game_views):
            log_error(f"Game index {game_index} out of range (only {len(game_views)} games)")
            return False

        # Click the specific game view
        game_views[game_index].click()

        # Wait for navigation
        page.wait_for_load_state("networkidle", timeout=NETWORK_IDLE_TIMEOUT)
        time.sleep(2)  # Additional wait for content to render

        log_success(f"Clicked Game View for game {game_index + 1}")
        return True

    except PlaywrightTimeout:
        log_error(f"Timeout clicking Game View for game {game_index}")
        return False
    except Exception as e:
        log_error(f"Error clicking Game View: {e}")
        return False
