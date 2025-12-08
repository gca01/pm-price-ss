#!/bin/bash
#
# Polymarket NBA Price Scraper - Hourly Runner
#
# This script is designed to be run via cron for hourly scraping.
#
# Cron example (run every hour at minute 0):
#   0 * * * * /path/to/pm-price-ss/run_hourly.sh
#
# Make sure to:
#   1. Create the virtual environment: python3 -m venv venv
#   2. Install dependencies: pip install -r requirements.txt
#   3. Install Playwright browsers: playwright install chromium
#   4. Make this script executable: chmod +x run_hourly.sh

# Change to script directory
cd "$(dirname "$0")"

# Create logs directory if it doesn't exist
mkdir -p logs

# Timestamp for log filename
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOGFILE="logs/scrape_${TIMESTAMP}.log"

# Activate virtual environment
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo "Virtual environment not found. Please create it first:" | tee -a "$LOGFILE"
    echo "  python3 -m venv venv" | tee -a "$LOGFILE"
    echo "  source venv/bin/activate" | tee -a "$LOGFILE"
    echo "  pip install -r requirements.txt" | tee -a "$LOGFILE"
    echo "  playwright install chromium" | tee -a "$LOGFILE"
    exit 1
fi

# Run the scraper
echo "Starting scrape at $(date)" | tee -a "$LOGFILE"
python3 -m scraper.main --headless 2>&1 | tee -a "$LOGFILE"
EXIT_CODE=${PIPESTATUS[0]}

echo "Scrape finished at $(date) with exit code $EXIT_CODE" | tee -a "$LOGFILE"

# Deactivate virtual environment
deactivate 2>/dev/null || true

exit $EXIT_CODE
