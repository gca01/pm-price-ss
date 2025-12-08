📁 PROJECT REQUIREMENTS
🔹 1. Core Purpose

Build a script that:

Loads https://polymarket.com/sports/nba/games

Detects all NBA games occurring today (using US Eastern Time as reference timezone)

For each game:

Open the Game View

Select the Moneyline tab (skip game if no Moneyline market available)

Select the Graph tab

Select the 6H timeframe

Wait for graph data to fully render (not just element existence)

Screenshot the graph visualization only

Scrape the moneyline prices shown above the graph

Append a row to an Excel file (configurable path, default: nba_polymarket_prices.xlsx) with:

| Timestamp | Game ID | Home | Away | Home Price | Away Price | Game Start | Screenshot Path |

Save screenshots to:

/screenshots/YYYY-MM-DD/<home>_<away>_<timestamp>.png

The script should be safe to run every hour (no overwriting of past entries).

Handle edge case: If no games are scheduled today, log a message and exit gracefully.

🔹 2. Technical Requirements
Python

Use Python 3.10+.

Libraries

Playwright (for browser automation)

openpyxl (for Excel reading/writing)

python-dateutil (timezone handling)

pytz (for US/Eastern timezone support)

typer (CLI runner)

rich (pretty logging)

Provide a requirements.txt.

Browser Configuration

Support both headless and headed modes via CLI flag (--headless / --no-headless)

Default to headless=True for cron/server usage

Use headed mode for debugging

Rate Limiting

Add configurable delay between game page loads (default: 2 seconds)

Prevents rate-limiting or blocking from Polymarket

🔹 3. File / Folder Structure (Generate All Files)

Create the following structure:

project/
├─ scraper/
│ ├─ **init**.py
│ ├─ main.py
│ ├─ games_scraper.py
│ ├─ game_screenshotter.py
│ ├─ excel_writer.py
│ ├─ config.py
│ ├─ utils.py
│ └─ selectors.py
├─ screenshots/
│ └─ (auto-generated daily folders)
├─ logs/
│ └─ (log files auto-generated)
├─ requirements.txt
├─ README.md
└─ run_hourly.sh (cron-friendly runner)

🔹 4. Implementation Details

⚠️ IMPORTANT: Client-Side Rendered Application
Polymarket is a Next.js React application with heavy client-side rendering.
Game data is NOT present in the initial HTML source - it loads dynamically via JavaScript.
This is why Playwright (browser automation) is required; static scraping will NOT work.
The scraper must wait for JavaScript to execute and DOM elements to render before interacting.

Games Page Parsing

Visit https://polymarket.com/sports/nba/games

Wait for page to fully load (network idle or specific element visibility)

Identify game cards via stable selectors

Extract:

Away team

Home team

Game start time

Game View link

Format game structure:

@dataclass
class GameInfo:
home: str
away: str
start_time: datetime  # Store in US/Eastern timezone
game_date: str  # YYYY-MM-DD format for unique identification
url: str

@property
def game_id(self) -> str:
    """Unique ID: 'YYYY-MM-DD_Home_Away'"""
    return f"{self.game_date}_{self.home}_{self.away}"

Game View Navigation

After loading the url:

Click Game View (if necessary)

Click Moneyline (if not available, log and skip this game)

Click Graph

Click 6H

Wait for graph data to fully load (use network idle or explicit wait for chart elements)

Scroll until graph is centered

Select the graph element via a stable CSS selector

Screenshot ONLY that element

Save to daily folder

Add configurable delay before moving to next game (rate limiting)

Moneyline Extraction

Scrape the prices shown in UI:

<button> NYK 62¢ </button>
<button> ORL 39¢ </button>

Parse into decimal:

62¢ → 0.62

39¢ → 0.39

Excel Logging

Use openpyxl to:

Create workbook if missing

Append new row each hour

Ensure Unicode column headers

DO NOT duplicate entries — always append

Columns:

Timestamp (ISO8601)
Game ID (e.g., "2025-12-07_Knicks_Magic")
Home Team
Away Team
Home Price
Away Price
Start Time (string, US/Eastern)
Screenshot Path

Screenshot Naming

Use:

screenshots/YYYY-MM-DD/home_away_YYYYMMDD_HHMMSS.png

Example:

screenshots/2025-12-07/Knicks_Magic_20251207_060000.png

Logging

Use rich to output:

Successful screenshot

Excel append

Errors (but do not stop execution)

Robustness Requirements

Implement:

Automatic retries on network failures

Wait-for-element with timeouts

Exception handling per game

Console output that a junior dev can follow

Full docstrings and comments

Cron Compatibility

Include a runnable shell script run_hourly.sh:

#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate # TODO: create venv manually
python scraper/main.py --headless >> logs/hourly.log 2>&1

Provide instructions in README.

🔹 5. Discovered Selectors (from live site analysis on 2025-12-09)

⚠️ NOTE: Polymarket uses dynamically generated CSS classes (e.g., "c-bDcLpV", "c-dhzjXW").
These may change with deployments. Use text-based and structural selectors when possible.

GAMES PAGE (https://polymarket.com/sports/nba/games):

Game Rows:
- The page uses a virtualized list: `[data-testid="virtuoso-item-list"]`
- Each game row can be identified by the presence of "Game View" text
- Use: `page.get_by_text("Game View")` to find all game entries

"Game View" Button:
- Selector: `page.get_by_text("Game View")` (Playwright locator)
- This is a clickable element that navigates to the game detail page
- The button does NOT have an href; it triggers JS navigation

Moneyline Price Buttons (on games list):
- Buttons containing "¢" character with team abbreviation
- Format: "SAC39¢" or "IND62¢" (team + price, no space)
- CSS class pattern: `c-bDcLpV` (dynamic, may change)
- Background colors are team-specific (purple for SAC, gold for IND, etc.)

Date Headers:
- Format: "Mon, December 8" or "Tue, December 9"
- Located in elements with class pattern `c-dqzIym`

GAME DETAIL PAGE (e.g., https://polymarket.com/event/nba-sac-ind-2025-12-08):

URL Pattern:
- Format: `https://polymarket.com/event/nba-{away}-{home}-{YYYY-MM-DD}`
- Example: `https://polymarket.com/event/nba-sac-ind-2025-12-08`

Market Tabs (Moneyline, Spreads, Totals):
- Use: `page.get_by_text("Moneyline", exact=True)`
- Also visible: "Spreads", "Totals" sections on the page

View Tabs (Order Book, Graph, About):
- Use: `page.get_by_text("Graph", exact=True)`
- Located below the Moneyline price buttons

Time Period Buttons (6H, 1D, 1W, 1M, ALL):
- Use: `page.get_by_text("6H", exact=True)` (or "1D", "1W", etc.)
- CSS class contains: `data-[state=active]:text-tabs-text-active`
- Time options: 1H, 6H, 1D, 1W, 1M, ALL

Chart/Graph Container:
- Main chart container: `div.flex.flex-col.w-full.min-h-[var(--chart-height)]`
- Chart SVG: `svg.overflow-visible` (690x192 pixels observed)
- For screenshot, target the container div (690x274 pixels observed)
- Alternative selector: `div[class*="chart"]` or look for SVG with `overflow-visible` class

Price Elements (on graph page):
- Moneyline buttons above graph: e.g., "SAC 39¢" and "IND 62¢"
- Use: `page.locator("button").filter(has_text="¢")`
- Price spans have class pattern: `c-PJLV`

RECOMMENDED PLAYWRIGHT SELECTORS (in order of reliability):

```python
# Games page - find all games
game_views = page.get_by_text("Game View").all()

# Click into a game
page.get_by_text("Game View").first.click()

# Navigate to Moneyline (usually already selected)
page.get_by_text("Moneyline", exact=True).click()

# Click Graph tab
page.get_by_text("Graph", exact=True).click()

# Select 6H timeframe
page.get_by_text("6H", exact=True).click()

# Wait for chart to render
page.wait_for_selector("svg.overflow-visible")
# OR
page.locator("div[class*='chart']").first.wait_for()

# Screenshot the chart container
chart = page.locator("div[class*='chart']").first
chart.screenshot(path="chart.png")

# Extract prices (look for buttons with ¢)
price_buttons = page.locator("button").filter(has_text="¢").all()
```

🔹 6. Configuration (config.py)

All configurable values should be centralized in config.py:

- EXCEL_FILE_PATH: Path to output Excel file (default: "nba_polymarket_prices.xlsx")
- SCREENSHOTS_DIR: Base directory for screenshots (default: "screenshots")
- LOGS_DIR: Directory for log files (default: "logs")
- TIMEZONE: Reference timezone (default: "US/Eastern")
- REQUEST_DELAY: Seconds to wait between game page loads (default: 2)
- PAGE_LOAD_TIMEOUT: Max seconds to wait for page elements (default: 30)
- GRAPH_RENDER_WAIT: Additional seconds to wait for graph data to render (default: 3)
- RETRY_ATTEMPTS: Number of retries on network failure (default: 3)
- RETRY_DELAY: Seconds between retries (default: 5)

🔹 7. Installation Notes

Post pip-install steps (include in README):

1. Create virtual environment: python -m venv venv
2. Activate: source venv/bin/activate
3. Install dependencies: pip install -r requirements.txt
4. Install Playwright browser: playwright install chromium

This is critical — Playwright requires browser binaries to be installed separately.

🔹 8. README Requirements

Include:

Setup instructions

Installation steps

How to create virtualenv

How to run manually

How to schedule via cron

How to schedule via GitHub Actions

Troubleshooting

FAQ

🔹 9. Deliverables

✓ Complete project structure
✓ All Python modules fully implemented
✓ Working hourly scraper
✓ Working Excel writer
✓ Logging system
✓ Proper error handling
✓ Example Excel output
✓ Example screenshots
✓ Complete README
✓ requirements.txt
✓ run_hourly.sh
