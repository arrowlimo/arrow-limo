"""
Application-wide settings and configuration defaults.
Modify these values to customize the application's behavior.
"""
from datetime import datetime

from PyQt6.QtCore import QDate

# =============================================================================
# WORKING YEAR DEFAULTS
# =============================================================================

# Default working year for reports, filters, and new entries
WORKING_YEAR = 2026

# Year range for dropdowns and filters (adjust based on your business history)
MIN_YEAR = 2010  # Earliest year to show in year selectors
MAX_YEAR = 2030  # Latest year to show in year selectors

# =============================================================================
# DATE VALIDATION DEFAULTS
# =============================================================================

# Minimum date for date pickers (prevents entering very old dates accidentally)
# Default is Jan 1 of MIN_YEAR
MIN_DATE = QDate(MIN_YEAR, 1, 1)

# Maximum date for date pickers (prevents entering far-future dates)
# Default is Dec 31 of MAX_YEAR
MAX_DATE = QDate(MAX_YEAR, 12, 31)

# =============================================================================
# DASHBOARD & REPORT DEFAULTS
# =============================================================================

# Default year range for dashboard year selectors
DASHBOARD_YEARS = list(range(MIN_YEAR, MAX_YEAR + 1))

# Default date range for reports (current year)
DEFAULT_REPORT_START = QDate(WORKING_YEAR, 1, 1)
DEFAULT_REPORT_END = QDate(WORKING_YEAR, 12, 31)

# =============================================================================
# CHARTER & BOOKING DEFAULTS
# =============================================================================

# Default charter date when creating new charter (today)
DEFAULT_CHARTER_DATE = QDate.currentDate()

# How many days forward to allow charter booking (e.g., 365 = 1 year ahead)
MAX_CHARTER_DAYS_AHEAD = 365

# =============================================================================
# RECEIPT & EXPENSE DEFAULTS
# =============================================================================

# Default receipt date (today)
DEFAULT_RECEIPT_DATE = QDate.currentDate()

# Allow backdating receipts this many months (e.g., 24 = 2 years back)
RECEIPT_BACKDATE_MONTHS = 24

# =============================================================================
# FINANCIAL/ACCOUNTING YEAR
# =============================================================================

# Fiscal year start month (1=January, 7=July, etc.)
FISCAL_YEAR_START_MONTH = 1  # January

# Current fiscal year


def get_fiscal_year() -> object:
    """Calculate current fiscal year based on FISCAL_YEAR_START_MONTH"""
    today = datetime.now()
    if today.month >= FISCAL_YEAR_START_MONTH:
        return today.year
    else:
        return today.year - 1

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def get_year_range(start_year=None, end_year=None) -> object:
    """Get list of years for dropdowns"""
    start = start_year or MIN_YEAR
    end = end_year or MAX_YEAR
    return list(range(start, end + 1))


def is_valid_year(year: int) -> bool:
    """Check if year is within valid range"""
    return MIN_YEAR <= year <= MAX_YEAR


def get_working_year_dates() -> object:
    """Get start/end dates for the working year"""
    return QDate(WORKING_YEAR, 1, 1), QDate(WORKING_YEAR, 12, 31)


def get_current_year() -> object:
    """Get current calendar year"""
    return datetime.now().year


# =============================================================================
# USAGE EXAMPLES
# =============================================================================
"""
# In your dashboard widgets:
from app_settings import DASHBOARD_YEARS, WORKING_YEAR

year_combo.addItems([str(y) for y in DASHBOARD_YEARS])
year_combo.setCurrentText(str(WORKING_YEAR))

# In date pickers that need validation:
from app_settings import MIN_DATE, MAX_DATE

date_edit.setMinimumDate(MIN_DATE)
date_edit.setMaximumDate(MAX_DATE)

# In accounting/report filters:
from app_settings import get_working_year_dates

start_date, end_date = get_working_year_dates()
"""
