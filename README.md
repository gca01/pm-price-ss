# Polymarket NBA Price Scraper

Automatically captures NBA moneyline price graphs from Polymarket every hour and saves them to Excel.

## Features

- Scrapes all NBA games for the current day from Polymarket
- Navigates to each game's Moneyline → Graph → 6H view
- Captures screenshots of the price graphs
- Extracts current moneyline prices
- Appends data to an Excel file for tracking over time
- Supports headless mode for server/cron usage

## Requirements

- Python 3.10+
- Playwright (browser automation)
- Chromium browser (installed via Playwright)

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/pm-price-ss.git
cd pm-price-ss
```

### 2. Create virtual environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Playwright browser

This step is critical - Playwright requires browser binaries to be installed separately:

```bash
playwright install chromium
```

## Usage

### Run manually

```bash
# Run with visible browser (for debugging)
python3 -m scraper.main --no-headless

# Run in headless mode (default)
python3 -m scraper.main

# Dry run (don't save to Excel)
python3 -m scraper.main --dry-run

# Limit to first N games
python3 -m scraper.main --max-games 2
```

### View help

```bash
python3 -m scraper.main --help
```

## Output

### Screenshots

Screenshots are saved to:
```
screenshots/YYYY-MM-DD/AWAY_HOME_YYYYMMDD_HHMMSS.png
```

Example: `screenshots/2025-12-09/SAC_IND_20251209_140000.png`

### Excel File

Data is appended to `nba_polymarket_prices.xlsx` with columns:

| Column | Description |
|--------|-------------|
| Timestamp | ISO8601 timestamp of when the data was captured |
| Game ID | Unique identifier (YYYY-MM-DD_Away_Home) |
| Home Team | Home team abbreviation |
| Away Team | Away team abbreviation |
| Home Price | Home team moneyline price (0-1) |
| Away Price | Away team moneyline price (0-1) |
| Game Start | Scheduled game start time |
| Screenshot Path | Path to the saved screenshot |

## Scheduling

### Using Cron (Linux/macOS)

Run every hour at minute 0:

```bash
# Edit crontab
crontab -e

# Add this line (adjust path as needed)
0 * * * * /path/to/pm-price-ss/run_hourly.sh
```

### Using Task Scheduler (Windows)

1. Open Task Scheduler
2. Create a new task
3. Set trigger to run hourly
4. Set action to run `run_hourly.bat` (create a batch file similar to run_hourly.sh)

### Using GitHub Actions

Create `.github/workflows/scrape.yml`:

```yaml
name: Scrape Polymarket NBA

on:
  schedule:
    # Run every hour
    - cron: '0 * * * *'
  workflow_dispatch:  # Allow manual trigger

jobs:
  scrape:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          playwright install chromium
          playwright install-deps

      - name: Run scraper
        run: python3 -m scraper.main --headless

      - name: Upload screenshots
        uses: actions/upload-artifact@v4
        with:
          name: screenshots
          path: screenshots/

      - name: Upload Excel file
        uses: actions/upload-artifact@v4
        with:
          name: excel-data
          path: nba_polymarket_prices.xlsx
```

## Configuration

Edit `scraper/config.py` to customize:

| Setting | Default | Description |
|---------|---------|-------------|
| `EXCEL_FILE_PATH` | `nba_polymarket_prices.xlsx` | Output Excel file path |
| `SCREENSHOTS_DIR` | `screenshots/` | Screenshot output directory |
| `TIMEZONE` | `US/Eastern` | Reference timezone |
| `REQUEST_DELAY` | `2` | Seconds between games |
| `PAGE_LOAD_TIMEOUT` | `30000` | Max ms to wait for elements |
| `GRAPH_RENDER_WAIT` | `3` | Extra seconds for graph rendering |
| `RETRY_ATTEMPTS` | `3` | Retries on network failure |

## Troubleshooting

### "No games found"

- Check if there are NBA games scheduled for today
- The site may have changed structure - run with `--no-headless` to debug
- Check your internet connection

### Browser doesn't launch

- Ensure Playwright is installed: `playwright install chromium`
- On Linux servers, you may need: `playwright install-deps`

### Screenshots are empty or wrong

- The page may not have fully loaded - try increasing `GRAPH_RENDER_WAIT`
- Run with `--no-headless` to see what's happening

### Excel file errors

- Ensure the file isn't open in another program
- Check write permissions for the directory

## Project Structure

```
pm-price-ss/
├── scraper/
│   ├── __init__.py
│   ├── main.py           # CLI entry point
│   ├── config.py         # Configuration settings
│   ├── selectors.py      # CSS selectors
│   ├── utils.py          # Helper functions
│   ├── games_scraper.py  # Games page parsing
│   ├── game_screenshotter.py  # Screenshot capture
│   └── excel_writer.py   # Excel output
├── screenshots/          # Screenshot output (auto-created)
├── logs/                 # Log files (auto-created)
├── requirements.txt
├── run_hourly.sh        # Cron runner script
└── README.md
```

## License

MIT License
