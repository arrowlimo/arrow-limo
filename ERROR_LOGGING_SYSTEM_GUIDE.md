# Error Logging System - User Guide

## Overview
The Error Logging System captures all errors that occur in the desktop application, stores them persistently, and provides a UI for reviewing and fixing them.

## Status: ✅ OPERATIONAL

### Verified Components
- ✅ Database table: `app_errors` (11 columns)
- ✅ File backup: `L:\limo\error_log.jsonl`
- ✅ UI viewer: Admin → 🐛 Error Log tab
- ✅ Global logging: Initialized in main.py
- ✅ Test passed: 1 error logged successfully

## How It Works

### 1. Automatic Capture
When an error occurs anywhere in the app, it's automatically logged if you use the error logging wrapper:

```python
from error_logger import log_error

try:
    # Your code that might fail
    result = do_something()
except Exception as e:
    # Log the error
    log_error(
        error=e,
        widget_name="WidgetNameHere",
        action="what_you_were_doing",
        user_context="Additional context (optional)"
    )
    # Continue with existing error handling
    QMessageBox.warning(self, "Error", str(e))
```

### 2. Storage
Errors are stored in TWO places:
- **Database**: `app_errors` table (primary storage)
- **File**: `error_log.jsonl` (backup in case DB fails)

### 3. Viewing Errors
**Method 1: Admin Panel**
1. Open desktop app
2. Go to Admin tab
3. Click "🐛 Error Log" sub-tab
4. View all errors with filters (all/unresolved/resolved)

**Method 2: Verification Script**
```powershell
cd L:\limo
python verify_error_logger.py
```

## Error Data Captured

Each error logs:
- **error_id**: Unique ID (auto-increment)
- **timestamp**: When error occurred
- **error_type**: Exception class name (e.g., "ZeroDivisionError")
- **error_message**: Error message text
- **traceback**: Full Python traceback
- **widget_name**: Which widget/component had the error
- **action**: What was being attempted
- **user_context**: Additional context provided by developer
- **resolved**: FALSE (unresolved) or TRUE (resolved)
- **resolution_notes**: How the error was fixed
- **resolved_at**: When it was marked resolved

## Using the Error Log UI

### View Statistics
- Total Errors
- Unresolved Errors  
- Resolved Errors

### Filter Errors
- **All**: Show all errors
- **Unresolved**: Show only unfixed errors (default)
- **Resolved**: Show errors that were fixed

### Mark as Resolved
1. Select an error in the table
2. Click "Mark Resolved"
3. Add notes explaining the fix
4. Error moves to "resolved" state

### View Details
- Double-click any error to see full traceback
- View complete context and resolution notes

### Export
- Click "Export CSV" to save error list for external analysis

### Clear Old Errors
- Click "Clear Resolved" to delete all resolved errors

## Adding Error Logging to Widgets

### Pattern 1: Wrap Exception Handlers
```python
# In your widget's __init__ or methods:
from error_logger import log_error

try:
    cur = self.db.get_cursor()
    cur.execute("SELECT * FROM some_table")
    data = cur.fetchall()
except Exception as e:
    log_error(e, widget_name=self.__class__.__name__, action="load_data")
    QMessageBox.warning(self, "Error", f"Failed to load data: {e}")
```

### Pattern 2: Async Operations
```python
def save_changes(self):
    try:
        # Save logic
        cur = self.db.get_cursor()
        cur.execute("UPDATE ...")
        self.db.commit()
        QMessageBox.information(self, "Success", "Changes saved")
    except Exception as e:
        log_error(
            error=e,
            widget_name="CustomerDetailWidget",
            action="save_customer_changes",
            user_context=f"Customer ID: {self.customer_id}"
        )
        self.db.rollback()
        QMessageBox.critical(self, "Error", f"Failed to save: {e}")
```

### Pattern 3: Silent Logging (No User Message)
```python
# For non-critical errors you want to track but not show
try:
    self.load_optional_data()
except Exception as e:
    log_error(e, widget_name=self.__class__.__name__, action="load_optional_data")
    # Continue without showing error to user
```

## Querying Errors Programmatically

### Get Recent Errors
```python
from error_logger import get_error_logger

logger = get_error_logger()
recent_errors = logger.get_recent_errors(limit=10)
# Returns list of tuples: (error_id, timestamp, error_type, error_message, widget_name, action, resolved)
```

### Get Error Details
```python
logger = get_error_logger()
error_details = logger.get_error_details(error_id=5)
# Returns tuple with all columns including full traceback
```

### Mark Error Resolved
```python
logger = get_error_logger()
success = logger.mark_resolved(
    error_id=5,
    resolution_notes="Fixed by updating column name from 'phone' to 'primary_phone'"
)
```

### Get Statistics
```python
logger = get_error_logger()
stats = logger.get_error_stats()
# Returns dict: {
#   'total': 10,
#   'unresolved': 3,
#   'resolved': 7,
#   'by_type': {'KeyError': 5, 'ValueError': 3, ...},
#   'by_widget': {'ClientDetailWidget': 4, ...}
# }
```

## Database Schema

```sql
CREATE TABLE app_errors (
    error_id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    error_type VARCHAR(100),
    error_message TEXT,
    traceback TEXT,
    widget_name VARCHAR(200),
    action VARCHAR(200),
    user_context TEXT,
    resolved BOOLEAN DEFAULT FALSE,
    resolution_notes TEXT,
    resolved_at TIMESTAMP
);
```

## Testing

### Test Error Logging
```powershell
cd L:\limo
python test_error_logger_init.py
```

Expected output:
```
✅ Database connection created
✅ Error logger initialized
❌ ERROR LOGGED: ZeroDivisionError in TestWidget
✅ Test error logged successfully
✅ Retrieved 1 recent errors
✅ All tests passed!
```

### Verify System Status
```powershell
cd L:\limo
python verify_error_logger.py
```

Shows:
- Table structure
- Error statistics
- Recent errors (last 5)
- File backup status

## File Locations

- **Error Logger**: `L:\limo\desktop_app\error_logger.py`
- **Error Viewer UI**: `L:\limo\desktop_app\error_log_viewer.py`
- **Database Table**: `almsdata.public.app_errors`
- **File Backup**: `L:\limo\error_log.jsonl`
- **Verification**: `L:\limo\verify_error_logger.py`
- **Test Script**: `L:\limo\test_error_logger_init.py`

## Next Steps

### Phase 1: Add to Critical Widgets ✅ READY
Add error logging to these high-priority widgets:
- client_drill_down.py (customer details)
- enhanced_charter_widget.py (charter management)
- receipt_management.py (receipts)
- payment_tracking.py (payments)
- dashboard_classes.py (dashboard widgets)

### Phase 2: Add to All Widgets
Systematically add error logging to all 82+ widget files

### Phase 3: Monitor and Fix
- Review error log daily
- Mark errors as resolved after fixes
- Export monthly reports for trends

## Troubleshooting

**Q: Error logging not working?**
- Check if app_errors table exists: `python verify_error_logger.py`
- Check if error_logger initialized in main.py
- Verify database connection is working

**Q: Errors not showing in UI?**
- Refresh the Error Log tab (click filter button)
- Check database directly: `SELECT * FROM app_errors;`

**Q: File backup not created?**
- Check if L:\limo\ directory is writable
- File is created on first error

**Q: How to clear all errors?**
```python
# Connect to database and run:
DELETE FROM app_errors;
```

Or via UI: Mark all as resolved, then "Clear Resolved"

---

**Last Updated**: January 23, 2026, 12:52 AM  
**Status**: ✅ Fully Operational  
**Version**: 1.0
