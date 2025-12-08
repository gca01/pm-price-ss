"""
CSS Selectors and Playwright locator strategies for Polymarket.

NOTE: Polymarket uses dynamically generated CSS classes (e.g., "c-bDcLpV").
These may change with deployments. Text-based selectors are preferred for stability.

Discovered from live site analysis on 2025-12-09.
"""


class GamesPageSelectors:
    """Selectors for the NBA games list page."""

    # The games list uses virtualization
    VIRTUOSO_LIST = '[data-testid="virtuoso-item-list"]'

    # Game View button text (most reliable)
    GAME_VIEW_TEXT = "Game View"

    # Price buttons contain the cent symbol
    PRICE_BUTTON_PATTERN = "button"  # Filter with has_text="¢"

    # Date header pattern (e.g., "Mon, December 8")
    DATE_HEADER_PATTERN = "p"  # Contains day/date text


class GamePageSelectors:
    """Selectors for individual game detail pages."""

    # Market type tabs
    MONEYLINE_TEXT = "Moneyline"
    SPREADS_TEXT = "Spreads"
    TOTALS_TEXT = "Totals"

    # View tabs (below market tabs)
    ORDER_BOOK_TEXT = "Order Book"
    GRAPH_TEXT = "Graph"
    ABOUT_TEXT = "About"

    # Time period buttons
    TIME_1H = "1H"
    TIME_6H = "6H"
    TIME_1D = "1D"
    TIME_1W = "1W"
    TIME_1M = "1M"
    TIME_ALL = "ALL"

    # Chart container selectors (in order of preference)
    CHART_CONTAINER = "div[class*='chart']"
    CHART_SVG = "svg.overflow-visible"
    CHART_CONTAINER_ALT = "div[class*='min-h-[var(--chart-height)]']"

    # Price elements
    PRICE_SPAN_PATTERN = "span"  # Filter with has_text="¢"

    # Back navigation
    BACK_TO_NBA = "Back to NBA"


def get_game_view_locator(page):
    """Get locator for Game View buttons on games page."""
    return page.get_by_text(GamesPageSelectors.GAME_VIEW_TEXT)


def get_moneyline_locator(page):
    """Get locator for Moneyline tab."""
    return page.get_by_text(GamePageSelectors.MONEYLINE_TEXT, exact=True)


def get_graph_locator(page):
    """Get locator for Graph tab."""
    return page.get_by_text(GamePageSelectors.GRAPH_TEXT, exact=True)


def get_time_period_locator(page, period: str = "6H"):
    """Get locator for a time period button."""
    return page.get_by_text(period, exact=True)


def get_chart_locator(page):
    """Get locator for the chart container (for screenshots)."""
    # Try multiple selectors in order of preference
    chart = page.locator(GamePageSelectors.CHART_CONTAINER).first
    return chart


def get_price_buttons_locator(page):
    """Get locator for price buttons containing ¢."""
    return page.locator("button").filter(has_text="¢")
