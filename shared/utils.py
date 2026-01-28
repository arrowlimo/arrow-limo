"""
Common utilities module for Arrow Limousine Management System

Shared utility functions used across API endpoints, scripts, and applications
to eliminate code duplication and standardize common operations.

Usage:
    from shared.utils import format_currency, safe_float, validate_email
"""

import re
import json
import uuid
import hashlib
from decimal import Decimal, InvalidOperation
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional, Union
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# ==================== DATA TYPE UTILITIES ====================

def safe_int(value: Any, default: int = 0) -> int:
    """Safely convert value to integer with default fallback."""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float with default fallback."""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def safe_decimal(value: Any, default: Optional[Decimal] = None) -> Optional[Decimal]:
    """Safely convert value to Decimal with default fallback."""
    if value is None:
        return default or Decimal('0.00')
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return default or Decimal('0.00')

def safe_str(value: Any, default: str = '') -> str:
    """Safely convert value to string with default fallback."""
    if value is None:
        return default
    return str(value).strip()

def safe_bool(value: Any, default: bool = False) -> bool:
    """Safely convert value to boolean with default fallback."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ('true', '1', 'yes', 'on', 'enabled')
    try:
        return bool(int(value))
    except (ValueError, TypeError):
        return default

# ==================== FORMATTING UTILITIES ====================

def format_currency(amount: Union[int, float, Decimal, str], currency: str = 'CAD') -> str:
    """Format amount as currency string."""
    try:
        value = safe_decimal(amount)
        if currency.upper() == 'CAD':
            return f"${value:,.2f} CAD"
        else:
            return f"{value:,.2f} {currency}"
    except Exception:
        return f"$0.00 {currency}"

def format_phone(phone: str) -> str:
    """Format phone number to standard format."""
    if not phone:
        return ''
    
    # Remove all non-digits
    digits = re.sub(r'\D', '', phone)
    
    # Handle North American format
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    elif len(digits) == 11 and digits[0] == '1':
        return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    else:
        return phone  # Return original if not standard format

def format_postal_code(postal: str) -> str:
    """Format Canadian postal code."""
    if not postal:
        return ''
    
    # Remove spaces and convert to uppercase
    postal = re.sub(r'\s', '', postal.upper())
    
    # Canadian postal code pattern
    if re.match(r'^[A-Z]\d[A-Z]\d[A-Z]\d$', postal):
        return f"{postal[:3]} {postal[3:]}"
    
    return postal  # Return original if not valid pattern

def format_datetime(dt: Union[datetime, date, str], format_str: str = '%Y-%m-%d %H:%M:%S') -> str:
    """Format datetime to string with fallback."""
    if not dt:
        return ''
    
    try:
        if isinstance(dt, str):
            # Try to parse common formats
            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y']:
                try:
                    dt = datetime.strptime(dt, fmt)
                    break
                except ValueError:
                    continue
            else:
                return dt  # Return original string if can't parse
        
        if isinstance(dt, date) and not isinstance(dt, datetime):
            dt = datetime.combine(dt, datetime.min.time())
        
        return dt.strftime(format_str)
    except Exception:
        return str(dt)

# ==================== VALIDATION UTILITIES ====================

def validate_email(email: str) -> bool:
    """Validate email format using regex."""
    if not email:
        return False
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validate_phone(phone: str) -> bool:
    """Validate phone number format."""
    if not phone:
        return False
    
    # Remove all non-digits
    digits = re.sub(r'\D', '', phone)
    
    # Check for valid North American format
    return len(digits) in [10, 11] and (len(digits) == 10 or digits[0] == '1')

def validate_postal_code(postal: str, country: str = 'CA') -> bool:
    """Validate postal code format by country."""
    if not postal:
        return False
    
    postal = postal.upper().replace(' ', '')
    
    if country.upper() == 'CA':
        # Canadian postal code: A1A 1A1
        return bool(re.match(r'^[A-Z]\d[A-Z]\d[A-Z]\d$', postal))
    elif country.upper() == 'US':
        # US ZIP code: 12345 or 12345-6789
        return bool(re.match(r'^\d{5}(-\d{4})?$', postal))
    
    return True  # Accept any format for other countries

def validate_gst_number(gst: str) -> bool:
    """Validate Canadian GST/HST number format."""
    if not gst:
        return False
    
    # Remove spaces and convert to uppercase
    gst = re.sub(r'\s', '', gst.upper())
    
    # GST/HST format: 123456789RT0001
    return bool(re.match(r'^\d{9}RT\d{4}$', gst))

# ==================== STRING UTILITIES ====================

def clean_string(text: str, max_length: Optional[int] = None) -> str:
    """Clean and normalize string input."""
    if not text:
        return ''
    
    # Remove extra whitespace and normalize
    cleaned = ' '.join(text.split())
    
    if max_length and len(cleaned) > max_length:
        cleaned = cleaned[:max_length].strip()
    
    return cleaned

def slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    if not text:
        return ''
    
    # Convert to lowercase and replace spaces/special chars with hyphens
    slug = re.sub(r'[^\w\s-]', '', text.lower())
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug.strip('-')

def truncate_text(text: str, max_length: int = 100, suffix: str = '...') -> str:
    """Truncate text to specified length with suffix."""
    if not text or len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix

# ==================== CALCULATION UTILITIES ====================

def calculate_gst(amount: Union[int, float, Decimal], rate: float = 0.05) -> Decimal:
    """Calculate GST amount from gross amount."""
    try:
        gross = safe_decimal(amount)
        gst_rate = Decimal(str(rate))
        return gross * gst_rate / (1 + gst_rate)
    except Exception:
        return Decimal('0.00')

def calculate_tax_exclusive_amount(gross_amount: Union[int, float, Decimal], tax_rate: float = 0.05) -> tuple[Decimal, Decimal]:
    """Calculate net amount and tax from gross amount."""
    try:
        gross = safe_decimal(gross_amount)
        rate = Decimal(str(tax_rate))
        tax_amount = gross * rate / (1 + rate)
        net_amount = gross - tax_amount
        return net_amount, tax_amount
    except Exception:
        return Decimal('0.00'), Decimal('0.00')

def calculate_percentage(part: Union[int, float, Decimal], whole: Union[int, float, Decimal]) -> float:
    """Calculate percentage with zero division protection."""
    try:
        part_val = safe_float(part)
        whole_val = safe_float(whole)
        if whole_val == 0:
            return 0.0
        return (part_val / whole_val) * 100
    except Exception:
        return 0.0

# ==================== ID GENERATION UTILITIES ====================

def generate_uuid() -> str:
    """Generate a UUID4 string."""
    return str(uuid.uuid4())

def generate_short_id(length: int = 8) -> str:
    """Generate a short alphanumeric ID."""
    import secrets
    import string
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def generate_hash(text: str, algorithm: str = 'sha256') -> str:
    """Generate hash of text using specified algorithm."""
    try:
        hash_obj = hashlib.new(algorithm)
        hash_obj.update(text.encode('utf-8'))
        return hash_obj.hexdigest()
    except Exception:
        return hashlib.sha256(text.encode('utf-8')).hexdigest()

# ==================== FILE UTILITIES ====================

def get_file_extension(filename: str) -> str:
    """Get file extension in lowercase."""
    if not filename or '.' not in filename:
        return ''
    return filename.rsplit('.', 1)[1].lower()

def is_safe_filename(filename: str) -> bool:
    """Check if filename is safe (no path traversal, etc.)."""
    if not filename:
        return False
    
    # Check for path traversal attempts
    if '..' in filename or '/' in filename or '\\' in filename:
        return False
    
    # Check for reserved names (Windows)
    reserved = ['CON', 'PRN', 'AUX', 'NUL'] + [f'COM{i}' for i in range(1, 10)] + [f'LPT{i}' for i in range(1, 10)]
    name_part = filename.split('.')[0].upper()
    if name_part in reserved:
        return False
    
    return True

def ensure_directory(path: Union[str, Path]) -> Path:
    """Ensure directory exists, create if needed."""
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path

# ==================== JSON UTILITIES ====================

def safe_json_loads(json_str: str, default: Any = None) -> Any:
    """Safely parse JSON string with default fallback."""
    if not json_str:
        return default
    
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return default

def safe_json_dumps(obj: Any, default: str = '{}') -> str:
    """Safely serialize object to JSON with default fallback."""
    try:
        return json.dumps(obj, default=str, ensure_ascii=False)
    except (TypeError, ValueError):
        return default

# ==================== DATE UTILITIES ====================

def parse_date(date_str: str, formats: Optional[List[str]] = None) -> Optional[date]:
    """Parse date string using multiple format attempts."""
    if not date_str:
        return None
    
    if formats is None:
        formats = [
            '%Y-%m-%d',
            '%m/%d/%Y',
            '%d/%m/%Y',
            '%Y-%m-%d %H:%M:%S',
            '%m/%d/%Y %H:%M:%S',
        ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return dt.date()
        except ValueError:
            continue
    
    return None

def get_fiscal_year(ref_date: Optional[date] = None) -> int:
    """Get fiscal year for given date (assumes April 1 - March 31)."""
    if ref_date is None:
        ref_date = date.today()
    
    if ref_date.month >= 4:  # April onwards
        return ref_date.year
    else:  # January - March
        return ref_date.year - 1

def get_business_days_between(start_date: date, end_date: date) -> int:
    """Calculate number of business days between two dates."""
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    
    days = 0
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:  # Monday = 0, Friday = 4
            days += 1
        current += timedelta(days=1)
    
    return days

# ==================== ERROR HANDLING UTILITIES ====================

def log_exception(logger: logging.Logger, message: str, exc: Exception, **kwargs):
    """Standardized exception logging with context."""
    context = {
        'exception_type': type(exc).__name__,
        'exception_message': str(exc),
        **kwargs
    }
    
    logger.error(f"{message}: {context}", exc_info=exc)

def create_error_response(message: str, code: str = 'error', details: Optional[Dict] = None) -> Dict[str, Any]:
    """Create standardized error response dictionary."""
    response = {
        'error': True,
        'code': code,
        'message': message,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    if details:
        response['details'] = details
    
    return response

# ==================== BUSINESS LOGIC UTILITIES ====================

def calculate_driver_pay(hours: float, hourly_rate: float, overtime_rate: float = 1.5, overtime_threshold: float = 8.0) -> Dict[str, float]:
    """Calculate driver pay with overtime."""
    regular_hours = min(hours, overtime_threshold)
    overtime_hours = max(0, hours - overtime_threshold)
    
    regular_pay = regular_hours * hourly_rate
    overtime_pay = overtime_hours * hourly_rate * overtime_rate
    total_pay = regular_pay + overtime_pay
    
    return {
        'regular_hours': regular_hours,
        'overtime_hours': overtime_hours,
        'regular_pay': regular_pay,
        'overtime_pay': overtime_pay,
        'total_pay': total_pay
    }

def format_reserve_number(number: Union[int, str]) -> str:
    """Format reserve number to standardized 6-digit format."""
    try:
        num = safe_int(number)
        return f"{num:06d}"
    except Exception:
        return str(number)

def validate_reserve_number(reserve_num: str) -> bool:
    """Validate reserve number format."""
    if not reserve_num:
        return False
    
    # Check if it's a valid 6-digit number
    return bool(re.match(r'^\d{6}$', reserve_num))

# ==================== EXPORT UTILITIES ====================

__all__ = [
    # Data type utilities
    'safe_int', 'safe_float', 'safe_decimal', 'safe_str', 'safe_bool',
    
    # Formatting utilities
    'format_currency', 'format_phone', 'format_postal_code', 'format_datetime',
    
    # Validation utilities
    'validate_email', 'validate_phone', 'validate_postal_code', 'validate_gst_number',
    
    # String utilities
    'clean_string', 'slugify', 'truncate_text',
    
    # Calculation utilities
    'calculate_gst', 'calculate_tax_exclusive_amount', 'calculate_percentage',
    
    # ID generation
    'generate_uuid', 'generate_short_id', 'generate_hash',
    
    # File utilities
    'get_file_extension', 'is_safe_filename', 'ensure_directory',
    
    # JSON utilities
    'safe_json_loads', 'safe_json_dumps',
    
    # Date utilities
    'parse_date', 'get_fiscal_year', 'get_business_days_between',
    
    # Error handling
    'log_exception', 'create_error_response',
    
    # Business logic
    'calculate_driver_pay', 'format_reserve_number', 'validate_reserve_number',
]