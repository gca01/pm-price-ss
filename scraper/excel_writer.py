"""
Excel writer for Polymarket NBA price data.

Handles creating and appending data to the Excel output file.
"""

from pathlib import Path
from typing import List, Optional

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter

from .config import EXCEL_FILE_PATH, EXCEL_HEADERS
from .utils import get_iso_timestamp, log_info, log_success, log_error
from .game_screenshotter import GameScreenshotResult


def create_workbook_with_headers(filepath: Path) -> Workbook:
    """
    Create a new workbook with headers.

    Args:
        filepath: Path where the workbook will be saved

    Returns:
        New Workbook object with headers
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "NBA Prices"

    # Add headers
    for col, header in enumerate(EXCEL_HEADERS, start=1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")
        cell.fill = PatternFill(start_color="DDDDDD", end_color="DDDDDD", fill_type="solid")

    # Set column widths
    column_widths = {
        "Timestamp": 25,
        "Game ID": 30,
        "Home Team": 12,
        "Away Team": 12,
        "Home Price": 12,
        "Away Price": 12,
        "Game Start": 15,
        "Screenshot Path": 60,
    }

    for col, header in enumerate(EXCEL_HEADERS, start=1):
        width = column_widths.get(header, 15)
        ws.column_dimensions[get_column_letter(col)].width = width

    # Save the workbook
    wb.save(filepath)
    log_success(f"Created new Excel file: {filepath}")

    return wb


def ensure_workbook(filepath: Optional[Path] = None) -> Path:
    """
    Ensure the Excel workbook exists, creating it if necessary.

    Args:
        filepath: Path to the Excel file. Uses default if None.

    Returns:
        Path to the Excel file
    """
    if filepath is None:
        filepath = EXCEL_FILE_PATH

    filepath = Path(filepath)

    if not filepath.exists():
        # Create parent directories if needed
        filepath.parent.mkdir(parents=True, exist_ok=True)
        create_workbook_with_headers(filepath)
    else:
        log_info(f"Using existing Excel file: {filepath}")

    return filepath


def append_result(result: GameScreenshotResult, filepath: Optional[Path] = None) -> bool:
    """
    Append a single game result to the Excel file.

    Args:
        result: GameScreenshotResult to append
        filepath: Path to the Excel file. Uses default if None.

    Returns:
        True if append succeeded, False otherwise
    """
    try:
        filepath = ensure_workbook(filepath)

        wb = load_workbook(filepath)
        ws = wb.active

        # Prepare row data
        row_data = [
            get_iso_timestamp(),
            result.game.game_id,
            result.game.home,
            result.game.away,
            result.home_price if result.home_price is not None else "",
            result.away_price if result.away_price is not None else "",
            result.game.start_time or "",
            str(result.screenshot_path) if result.screenshot_path else "",
        ]

        # Append the row
        ws.append(row_data)

        # Save
        wb.save(filepath)
        wb.close()

        log_success(f"Appended row for {result.game.game_id}")
        return True

    except Exception as e:
        log_error(f"Error appending to Excel: {e}")
        return False


def append_results(results: List[GameScreenshotResult], filepath: Optional[Path] = None) -> int:
    """
    Append multiple game results to the Excel file.

    Args:
        results: List of GameScreenshotResult objects to append
        filepath: Path to the Excel file. Uses default if None.

    Returns:
        Number of successfully appended rows
    """
    if not results:
        log_info("No results to append")
        return 0

    try:
        filepath = ensure_workbook(filepath)

        wb = load_workbook(filepath)
        ws = wb.active

        appended = 0
        timestamp = get_iso_timestamp()

        for result in results:
            if not result.success:
                continue

            row_data = [
                timestamp,
                result.game.game_id,
                result.game.home,
                result.game.away,
                result.home_price if result.home_price is not None else "",
                result.away_price if result.away_price is not None else "",
                result.game.start_time or "",
                str(result.screenshot_path) if result.screenshot_path else "",
            ]

            ws.append(row_data)
            appended += 1

        # Save once at the end
        wb.save(filepath)
        wb.close()

        log_success(f"Appended {appended} rows to Excel")
        return appended

    except Exception as e:
        log_error(f"Error appending results to Excel: {e}")
        return 0


def get_row_count(filepath: Optional[Path] = None) -> int:
    """
    Get the number of data rows in the Excel file.

    Args:
        filepath: Path to the Excel file. Uses default if None.

    Returns:
        Number of data rows (excluding header)
    """
    try:
        if filepath is None:
            filepath = EXCEL_FILE_PATH

        filepath = Path(filepath)

        if not filepath.exists():
            return 0

        wb = load_workbook(filepath)
        ws = wb.active
        row_count = ws.max_row - 1  # Subtract header row

        wb.close()
        return max(0, row_count)

    except Exception as e:
        log_error(f"Error getting row count: {e}")
        return 0
