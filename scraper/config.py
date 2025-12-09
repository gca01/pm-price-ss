"""
Configuration settings for the Polymarket NBA scraper.

All configurable values are centralized here for easy modification.
"""

from pathlib import Path

# Base directories
PROJECT_ROOT = Path(__file__).parent.parent
SCREENSHOTS_DIR = PROJECT_ROOT / "screenshots"
LOGS_DIR = PROJECT_ROOT / "logs"
EXCEL_FILE_PATH = PROJECT_ROOT / "nba_polymarket_prices.xlsx"

# URLs
POLYMARKET_NBA_URL = "https://polymarket.com/sports/nba/games"

# Timezone
TIMEZONE = "US/Eastern"

# Timing configuration
REQUEST_DELAY = 2  # Seconds to wait between game page loads
PAGE_LOAD_TIMEOUT = 60000  # Max milliseconds to wait for page elements
GRAPH_RENDER_WAIT = 3  # Additional seconds to wait for graph data to render
NETWORK_IDLE_TIMEOUT = 30000  # Milliseconds to wait for network idle

# Retry configuration
RETRY_ATTEMPTS = 3  # Number of retries on network failure
RETRY_DELAY = 5  # Seconds between retries

# Browser configuration
DEFAULT_VIEWPORT = {"width": 1920, "height": 1080}
DEFAULT_HEADLESS = True

# Excel column headers
EXCEL_HEADERS = [
    "Timestamp",
    "Game ID",
    "Home Team",
    "Away Team",
    "Home Price",
    "Away Price",
    "Game Start",
    "Screenshot Path"
]
