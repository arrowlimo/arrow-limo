# Fix: Receipt Search Results Table Height in Non-Fullscreen Mode

## Issue
In non-fullscreen (windowed) mode, the receipt search results table was consuming 600px of vertical height, causing it to overflow and hide the right panel (receipt details) below it.

## Root Cause
The PyQt6 `QTableWidget` for search results had:
1. `setMaximumHeight(600)` hardcoded on line 306 of the widget initialization
2. `_auto_resize_table_height()` method capped the height at 600px even when fewer rows were displayed

This 600px constraint was appropriate for fullscreen windows but too large for windowed layouts.

## Solution Applied
**Reduced maximum height from 600px to 250px** to:
- Fit within typical non-fullscreen window heights
- Allow right panel details to remain visible
- Display 3-5 search results before requiring scrolling
- Maintain visual balance between left (search/results) and right (details) panels

### Changes Made
**File: `l:\limo\archive_old_scripts\old_backups\backup_20260130_235425\receipt_search_match_widget.py`**

1. **Line ~306** - Updated results_table maximum height:
```python
# BEFORE:
self.results_table.setMaximumHeight(600)

# AFTER:
self.results_table.setMaximumHeight(250)  # Reduced from 600px for non-fullscreen mode
```

2. **Line ~1031-1039** - Updated _auto_resize_table_height() cap:
```python
# BEFORE:
target_height = min(total_height + 4, 600)  # +4 for scrollbar padding
self.results_table.setMaximumHeight(target_height)

# AFTER:
target_height = min(total_height + 4, 250)  # Cap at 250px maximum (reduced from 600px for non-fullscreen mode)
self.results_table.setMaximumHeight(target_height)
```

## Files Created
- `desktop_app/receipt_search_match_widget_FIXED_HEIGHT.py` - Fixed version for immediate use if needed

## Testing Recommendations
1. **Test in windowed mode**: Resize window to various heights (800px, 1000px, 1200px)
   - Verify search results table displays 3-5 rows before scrolling
   - Confirm right panel remains visible below table
   - Check horizontal split proportions (left/right balance)

2. **Test in fullscreen mode**: Verify expected behavior unchanged
   - Table should still scroll if > 10 results

3. **Test with different result counts**:
   - 1-3 results: Table should auto-fit (< 250px)
   - 5-10 results: Table should scroll within 250px bounds
   - 50+ results: Table should be scrollable

## Deployment
If currently using the desktop app from `archive_old_scripts/old_backups/backup_20260130_235425/`:
- The fix has been applied to the backup file
- Consider rebuilding/redeploying the desktop application

If using the modern web frontend:
- The web version uses CSS-based responsive sizing and doesn't have this issue

## Related Issues Fixed Previously
- ✅ GL code loss when adding split receipt components (committed: 36fc495)
- ⏳ Receipt search results too large in non-fullscreen mode (this fix)

## Notes
- Height constraint adjusted for typical windowed layouts (desktop monitors: 1920x1080, 2560x1440, etc.)
- If using ultra-wide monitors, may need further adjustment
- The change only affects PyQt6 desktop app; web frontend unaffected
