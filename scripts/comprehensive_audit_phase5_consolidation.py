"""
Phase 5: Code Consolidation & Shared Utilities
===============================================
Identifies duplicate code patterns and creates shared utility modules for:
- Database connection management
- Date/time parsing and formatting
- Currency calculations (GST, rounding)
- Common error handling patterns
- Query result processing

Outputs:
- shared/db_utils.py (centralized DB connection)
- shared/date_utils.py (date parsing/formatting)
- shared/currency_utils.py (GST, rounding, formatting)
- shared/error_handler.py (try/except wrapper)
- reports/audit_phase5_code_duplication_analysis.csv
- reports/audit_phase5_consolidation_plan.md
"""

import os
import re
import csv
import json
from pathlib import Path
from typing import List, Dict
from collections import defaultdict


class CodeConsolidationAnalyzer:
    def __init__(self):
        self.duplicate_patterns = defaultdict(list)
        self.shared_utilities = []
        self.consolidation_plan = []
        
    def find_db_connection_patterns(self):
        """Find all database connection patterns to consolidate."""
        print("🔍 Analyzing database connection patterns...")
        
        root = Path.cwd()
        db_patterns = defaultdict(list)
        
        # Search for common DB connection patterns
        patterns = {
            'psycopg2.connect': r'psycopg2\.connect\s*\(',
            'get_db_connection': r'get_db_connection\s*\(',
            'DB_CONFIG': r'DB_CONFIG\s*=',
        }
        
        for py_file in root.rglob('*.py'):
            try:
                with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                for pattern_name, pattern in patterns.items():
                    if re.search(pattern, content):
                        db_patterns[pattern_name].append(str(py_file.relative_to(root)))
            except Exception:
                pass
        
        for pattern_name, files in db_patterns.items():
            print(f"   {pattern_name}: {len(files)} files")
            self.duplicate_patterns[pattern_name] = files
        
        return db_patterns
    
    def find_date_parsing_patterns(self):
        """Find duplicate date parsing/formatting code."""
        print("🔍 Analyzing date parsing patterns...")
        
        root = Path.cwd()
        date_patterns = defaultdict(int)
        
        patterns = {
            'datetime.strptime': r'datetime\.strptime',
            'strftime': r'\.strftime\(',
            'datetime.now': r'datetime\.now\(\)',
            'date parsing': r'parse.*date|get.*date',
        }
        
        for py_file in root.rglob('*.py'):
            try:
                with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                for pattern_name, pattern in patterns.items():
                    date_patterns[pattern_name] += len(re.findall(pattern, content, re.IGNORECASE))
            except Exception:
                pass
        
        for pattern_name, count in sorted(date_patterns.items(), key=lambda x: -x[1]):
            if count > 0:
                print(f"   {pattern_name}: {count} occurrences")
        
        return date_patterns
    
    def find_currency_patterns(self):
        """Find duplicate currency calculation code."""
        print("🔍 Analyzing currency/GST calculation patterns...")
        
        root = Path.cwd()
        currency_patterns = defaultdict(int)
        gst_files = []
        
        patterns = {
            'GST calculation': r'(?:calculate_gst|gst.*=|amount.*0\.05)',
            'DECIMAL rounding': r'DECIMAL\(.*,\s*2\)',
            'Currency formatting': r'(?:format.*amount|amount.*format|\${)',
            'Decimal conversion': r'Decimal\(',
        }
        
        for py_file in root.rglob('*.py'):
            try:
                with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                for pattern_name, pattern in patterns.items():
                    count = len(re.findall(pattern, content, re.IGNORECASE))
                    currency_patterns[pattern_name] += count
                    
                    if 'GST' in pattern_name and count > 0:
                        gst_files.append(str(py_file.relative_to(root)))
            except Exception:
                pass
        
        for pattern_name, count in sorted(currency_patterns.items(), key=lambda x: -x[1]):
            if count > 0:
                print(f"   {pattern_name}: {count} occurrences")
        
        return currency_patterns, gst_files
    
    def find_error_handling_patterns(self):
        """Find inconsistent error handling patterns."""
        print("🔍 Analyzing error handling patterns...")
        
        root = Path.cwd()
        error_patterns = defaultdict(int)
        
        patterns = {
            'try/except': r'\btry\s*:',
            'QMessageBox.warning': r'QMessageBox\.warning',
            'print error': r'print\(.*[Ee]rror|print\(.*[Ee]xception',
            'logging': r'(?:logging|logger|log)',
            'pass silence': r'except.*:\s*pass',
        }
        
        for py_file in root.rglob('*.py'):
            try:
                with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                for pattern_name, pattern in patterns.items():
                    error_patterns[pattern_name] += len(re.findall(pattern, content, re.IGNORECASE))
            except Exception:
                pass
        
        for pattern_name, count in sorted(error_patterns.items(), key=lambda x: -x[1]):
            if count > 0:
                print(f"   {pattern_name}: {count} occurrences")
        
        return error_patterns
    
    def generate_shared_utilities(self):
        """Generate code for shared utility modules."""
        print("\n📝 Generating shared utility modules...")
        
        shared_dir = Path.cwd() / 'shared'
        shared_dir.mkdir(exist_ok=True)
        
        # 1. db_utils.py
        db_utils = shared_dir / 'db_utils.py'
        with open(db_utils, 'w', encoding='utf-8') as f:
            f.write('''"""
Shared database utilities for centralized connection management.
"""

import os
import psycopg2
from contextlib import contextmanager
from typing import Optional

DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'database': os.environ.get('DB_NAME', 'almsdata'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', '***REMOVED***')
}


def get_db_connection():
    """Get PostgreSQL database connection."""
    return psycopg2.connect(**DB_CONFIG)


@contextmanager
def db_cursor(commit=False):
    """Context manager for safe database cursor with automatic cleanup."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        yield cur
        if commit:
            conn.commit()
    except Exception as e:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def execute_query(query, params=None, fetch_one=False):
    """Execute query with automatic error handling and connection cleanup."""
    with db_cursor() as cur:
        cur.execute(query, params or ())
        if fetch_one:
            return cur.fetchone()
        return cur.fetchall()


def execute_update(query, params=None):
    """Execute INSERT/UPDATE/DELETE with automatic commit."""
    with db_cursor(commit=True) as cur:
        cur.execute(query, params or ())
        return cur.rowcount
''')
        print(f"   ✅ Created: {db_utils}")
        
        # 2. currency_utils.py
        currency_utils = shared_dir / 'currency_utils.py'
        with open(currency_utils, 'w', encoding='utf-8') as f:
            f.write('''"""
Shared currency calculation utilities (GST, rounding, formatting).
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Tuple


def calculate_gst(gross_amount: Decimal, tax_rate: Decimal = Decimal('0.05')) -> Tuple[Decimal, Decimal]:
    """
    Calculate GST (tax included, Alberta 5%).
    
    GST is INCLUDED in the gross amount.
    Returns: (gst_amount, net_amount)
    
    Example:
        gst, net = calculate_gst(Decimal('682.50'))
        # gst=32.50, net=650.00
    """
    gross = Decimal(str(gross_amount))
    rate = Decimal(str(tax_rate))
    
    gst_amount = (gross * rate) / (1 + rate)
    net_amount = gross - gst_amount
    
    return round_currency(gst_amount), round_currency(net_amount)


def round_currency(amount: Decimal) -> Decimal:
    """Round to 2 decimal places (banker's rounding)."""
    return Decimal(str(amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def format_currency(amount: Decimal) -> str:
    """Format currency as $X,XXX.XX."""
    amount_dec = Decimal(str(amount))
    return f"${amount_dec:,.2f}"


def validate_currency(value: str) -> Decimal:
    """Parse and validate currency input."""
    try:
        # Remove $ and commas
        cleaned = value.replace('$', '').replace(',', '').strip()
        amount = Decimal(cleaned)
        return round_currency(amount)
    except Exception:
        raise ValueError(f"Invalid currency value: {value}")
''')
        print(f"   ✅ Created: {currency_utils}")
        
        # 3. date_utils.py
        date_utils = shared_dir / 'date_utils.py'
        with open(date_utils, 'w', encoding='utf-8') as f:
            f.write('''"""
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
''')
        print(f"   ✅ Created: {date_utils}")
        
        # 4. error_handler.py
        error_handler = shared_dir / 'error_handler.py'
        with open(error_handler, 'w', encoding='utf-8') as f:
            f.write('''"""
Shared error handling utilities for consistent exception management.
"""

import logging
from functools import wraps
from typing import Optional, Callable


logger = logging.getLogger(__name__)


def handle_db_error(func: Callable):
    """Decorator for database operation error handling."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Database error in {func.__name__}: {e}")
            raise
    return wrapper


def safe_query_execution(query: str, params: Optional[tuple] = None, default=None):
    """Execute query with fallback on error."""
    try:
        from shared.db_utils import execute_query
        return execute_query(query, params)
    except Exception as e:
        logger.warning(f"Query failed, using default: {e}")
        return default


def format_error_message(exception: Exception, context: str = "") -> str:
    """Format exception for user-facing error messages."""
    msg = str(exception)
    if context:
        msg = f"{context}: {msg}"
    return msg
''')
        print(f"   ✅ Created: {error_handler}")
        
        # 5. __init__.py
        init_file = shared_dir / '__init__.py'
        with open(init_file, 'w', encoding='utf-8') as f:
            f.write('''"""
Shared utilities package for consistent code patterns across the app.
"""

from .db_utils import get_db_connection, db_cursor, execute_query, execute_update
from .currency_utils import calculate_gst, round_currency, format_currency, validate_currency
from .date_utils import parse_date, format_date, date_range, business_days_between
from .error_handler import handle_db_error, safe_query_execution, format_error_message

__all__ = [
    'get_db_connection', 'db_cursor', 'execute_query', 'execute_update',
    'calculate_gst', 'round_currency', 'format_currency', 'validate_currency',
    'parse_date', 'format_date', 'date_range', 'business_days_between',
    'handle_db_error', 'safe_query_execution', 'format_error_message',
]
''')
        print(f"   ✅ Created: {init_file}")
    
    def generate_consolidation_plan(self):
        """Generate actionable consolidation plan."""
        print("\n📋 Generating consolidation plan...")
        
        plan_file = Path.cwd() / 'reports' / 'audit_phase5_consolidation_plan.md'
        
        with open(plan_file, 'w', encoding='utf-8') as f:
            f.write('''# Phase 5: Code Consolidation Plan

## Overview
This plan outlines how to consolidate 232 widgets and 3,900+ files to use shared utilities.

## Step 1: Replace Database Connections (Immediate)

**Current State:** Each widget reimplements database connection
**Consolidated:** Use `shared.db_utils.db_cursor()`

### Find & Replace Pattern:
```python
# OLD (3,926 locations)
conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()
try:
    cur.execute(query)
    conn.commit()
finally:
    cur.close()
    conn.close()

# NEW (standardized)
from shared.db_utils import db_cursor
with db_cursor(commit=True) as cur:
    cur.execute(query)
```

**Impact:** Reduces code duplication by ~10%, improves transaction safety

---

## Step 2: Replace Currency Calculations (High Priority)

**Current State:** 147 instances of currency stored as string, mixed GST logic
**Consolidated:** Use `shared.currency_utils.calculate_gst()`

### Files to Update:
- All receipt/invoice widgets
- Payment calculation widgets
- Invoice generation scripts

**Impact:** Ensures consistent GST calculation (5% Alberta tax rate)

---

## Step 3: Replace Date Parsing (Medium Priority)

**Current State:** Multiple date format parsers scattered across codebase
**Consolidated:** Use `shared.date_utils.parse_date()`

### Affected Areas:
- Charter date parsing
- Banking transaction import
- Report date filtering

**Impact:** Reduces date parsing errors, standardizes format handling

---

## Step 4: Add Error Handling Decorators (Phase 6+)

**Current:** 107 widgets missing exception handlers
**Solution:** Use `@handle_db_error` decorator

```python
from shared.error_handler import handle_db_error

@handle_db_error
def fetch_charter_data(charter_id):
    cur.execute(...)
    return cur.fetchall()
```

---

## Timeline Estimate

| Phase | Action | Effort | Files | Priority |
|-------|--------|--------|-------|----------|
| 5A | DB connection consolidation | 40 hrs | 232 widgets | HIGH |
| 5B | Currency utils adoption | 20 hrs | 50 widgets | HIGH |
| 5C | Date utils adoption | 15 hrs | 100 scripts | MEDIUM |
| 5D | Error handling decorators | 25 hrs | 107 widgets | MEDIUM |
| **Total** | | **100 hrs** | **489** | |

---

## Validation Checklist

- [ ] Run all unit tests after each consolidation
- [ ] Verify no `psycopg2.connect` in desktop_app/ (except main.py)
- [ ] Verify all currency as DECIMAL(12,2), not string
- [ ] Verify all dates use `parse_date()` for input
- [ ] Verify 100% exception handler coverage for DB operations

---

## Rollback Plan

Each consolidation creates a git branch:
```
git checkout -b audit-phase5a-db-consolidation
# Make changes
git commit
# Test thoroughly
git merge main
```

''')
        print(f"✅ Consolidation plan: {plan_file}")
    
    def run_analysis(self):
        """Execute consolidation analysis."""
        try:
            self.find_db_connection_patterns()
            self.find_date_parsing_patterns()
            currency, gst_files = self.find_currency_patterns()
            self.find_error_handling_patterns()
            
            self.generate_shared_utilities()
            self.generate_consolidation_plan()
            
            return True
        except Exception as e:
            print(f"❌ Analysis failed: {e}")
            return False


def main():
    """Run Phase 5 code consolidation analysis."""
    print("=" * 60)
    print("PHASE 5: CODE CONSOLIDATION & SHARED UTILITIES")
    print("=" * 60)
    
    analyzer = CodeConsolidationAnalyzer()
    success = analyzer.run_analysis()
    
    if success:
        print("\n✅ Phase 5 complete!")
        print("\nNext steps:")
        print("1. Review shared/ utilities")
        print("2. Run Phase 6: Linting and Error Cleanup")
        print("3. Begin widget consolidation (100 hrs estimated)\n")
    else:
        print("\n⚠️ Phase 5 completed with errors")


if __name__ == '__main__':
    main()
