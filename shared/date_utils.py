"""
Shared date/time parsing and formatting utilities.
"""

from datetime import datetime, date, timedelta
from typing import Optional, Union


def parse_date(value: str, formats: Optional[list] = None) -> date:
    """
    Parse date from string with multiple format support.
    
    Tries formats in order: YYYY-MM-DD, MM/DD/YYYY, MM-DD-YYYY
    """
    if isinstance(value, date):
        return value
    
    formats = formats or ['%Y-%m-%d', '%m/%d/%Y', '%m-%d-%Y', '%d-%m-%Y']
    
    for fmt in formats:
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    
    raise ValueError(f"Unable to parse date: {value}")


def format_date(value: Union[date, datetime], fmt: str = '%Y-%m-%d') -> str:
    """Format date/datetime as string."""
    if isinstance(value, datetime):
        return value.strftime(fmt)
    elif isinstance(value, date):
        return value.strftime(fmt)
    else:
        return parse_date(str(value)).strftime(fmt)


def date_range(start: date, end: date) -> list:
    """Generate list of dates between start and end (inclusive)."""
    current = start
    result = []
    while current <= end:
        result.append(current)
        current += timedelta(days=1)
    return result


def business_days_between(start: date, end: date) -> int:
    """Count business days (Mon-Fri) between dates."""
    count = 0
    current = start
    while current <= end:
        if current.weekday() < 5:  # Mon=0, Fri=4
            count += 1
        current += timedelta(days=1)
    return count
