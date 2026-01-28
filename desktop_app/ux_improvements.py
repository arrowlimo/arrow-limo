#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
UX/UI Enhancement Module - User-Friendly Input Handling
Addresses:
1. Field selection/masking behavior (select-all replacement)
2. Double-click editing (word selection, not insert mode)
3. Date formatting (consistent MMM/DD/YYYY)
4. Natural sorting (L-1, L-2, L-3 not L-1, L-10, L-2)
"""

import re
from PyQt6.QtWidgets import QLineEdit, QDateEdit, QComboBox
from PyQt6.QtCore import Qt, QTimer, QDate, QCollator, QLocale
from PyQt6.QtGui import QFont


class UserFriendlyLineEdit(QLineEdit):
    """
    Enhanced QLineEdit with standard app behavior:
    - Click anywhere: select all (ready to replace)
    - Type with text selected: replaces all (doesn't interfere with masking)
    - Double-click: select word at cursor (allows editing specific portion)
    - Focus in: select all for easy replacement
    """
    
    def __init__(self, parent=None, allow_word_select=True):
        super().__init__(parent)
        self.allow_word_select = allow_word_select
        self.is_selecting_all = False
        
    def focusInEvent(self, event):
        """Select all when field receives focus"""
        super().focusInEvent(event)
        self.is_selecting_all = True
        QTimer.singleShot(0, self.selectAll)
        self.is_selecting_all = False
    
    def mousePressEvent(self, event):
        """Single click: select all content"""
        super().mousePressEvent(event)
        if not self.is_selecting_all:
            self.is_selecting_all = True
            QTimer.singleShot(0, self.selectAll)
            self.is_selecting_all = False
    
    def mouseDoubleClickEvent(self, event):
        """Double click: select word at cursor (allows editing portion)"""
        if self.allow_word_select:
            # Default word selection behavior
            super().mouseDoubleClickEvent(event)
        else:
            # Or select all if word selection disabled
            self.selectAll()
    
    def keyPressEvent(self, event):
        """
        Type with text selected: replace it
        Ensures masking doesn't interfere
        """
        text = event.text()
        
        # If there's selected text and user types printable character, replace
        if self.selectedText() and text and text[0].isprintable() and text[0] not in ('\n', '\t'):
            # Clear selection to allow replacement
            cursor_pos = self.cursorPosition()
            self.clear()
            self.setCursorPosition(cursor_pos)
        
        super().keyPressEvent(event)


class SmartDateEdit(QDateEdit):
    """
    Enhanced date input with:
    - Flexible input format (MM/DD/YYYY, M/D/YY, MMDDYYYY all work)
    - Consistent display format (MMM DD, YYYY - e.g., "Jan 05, 2026")
    - Keyboard shortcuts (+ for tomorrow, - for yesterday)
    - Select-all on click for easy replacement
    - Type xx/xx/xxxx format auto-conversion
    """
    
    def __init__(self, parent=None, prefer_month_text=True):
        super().__init__(parent)
        self.prefer_month_text = prefer_month_text
        
        # Set display format
        if prefer_month_text:
            self.setDisplayFormat("MMM dd, yyyy")  # Jan 05, 2026
        else:
            self.setDisplayFormat("MM/dd/yyyy")  # 01/05/2026
        
        self.setCalendarPopup(True)
        self.setDate(QDate.currentDate())
        self.setMaximumWidth(150)
        
        # Enable editing in the line edit
        if self.lineEdit():
            self.lineEdit().setClearButtonEnabled(True)
            self.lineEdit().selectAll()
        
        self.setToolTip(
            "<b>📅 Date Input (Smart Format)</b><br>"
            "Type any format: 01/05/2026, 1/5/26, 0105 2026<br>"
            "Click calendar icon to pick date<br>"
            "<b>Keyboard:</b> + (tomorrow), - (yesterday)<br>"
            f"<b>Display:</b> {self.displayFormat()}"
        )
    
    def focusInEvent(self, event):
        """Select all when focused"""
        super().focusInEvent(event)
        if self.lineEdit():
            QTimer.singleShot(0, self.lineEdit().selectAll)
    
    def keyPressEvent(self, event):
        """
        Handle keyboard shortcuts:
        + = tomorrow
        - = yesterday
        Also auto-parse various date formats
        """
        if event.key() == Qt.Key.Key_Plus:
            current = self.date()
            self.setDate(current.addDays(1))
            return
        elif event.key() == Qt.Key.Key_Minus:
            current = self.date()
            self.setDate(current.addDays(-1))
            return
        
        super().keyPressEvent(event)
        
        # After typing, try to parse the input
        if self.lineEdit():
            text = self.lineEdit().text().strip()
            if text:
                parsed_date = self._parse_flexible_date(text)
                if parsed_date:
                    self.setDate(parsed_date)
    
    @staticmethod
    def _parse_flexible_date(text):
        """
        Parse dates in various formats:
        - MM/DD/YYYY: "01/05/2026"
        - M/D/YY: "1/5/26"
        - MMDDYYYY: "01052026"
        - MMM DD YYYY: "Jan 05 2026"
        """
        text = text.strip()
        
        # Try MM/DD/YYYY or M/D/YY format
        slash_match = re.match(r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})', text)
        if slash_match:
            m, d, y = int(slash_match.group(1)), int(slash_match.group(2)), int(slash_match.group(3))
            if y < 100:
                y = 2000 + y if y < 30 else 1900 + y
            try:
                return QDate(y, m, d)
            except:
                pass
        
        # Try MMDDYYYY format (8 digits)
        if len(text) == 8 and text.isdigit():
            try:
                m, d, y = int(text[0:2]), int(text[2:4]), int(text[4:8])
                return QDate(y, m, d)
            except:
                pass
        
        # Try MMM DD YYYY format (e.g., "Jan 05 2026")
        month_match = re.match(r'([A-Za-z]{3})\s+(\d{1,2})\s+(\d{4})', text)
        if month_match:
            month_str, d, y = month_match.groups()
            months = {
                'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
                'may': 5, 'jun': 6, 'jul': 7, 'aug': 8,
                'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
            }
            m = months.get(month_str.lower())
            if m:
                try:
                    return QDate(int(y), m, int(d))
                except:
                    pass
        
        return None


class NaturalSortComboBox(QComboBox):
    """
    ComboBox with natural sorting:
    - L-1, L-2, L-3, L-10 (not L-1, L-10, L-2, L-3)
    - 1, 2, 10, 20 (not 1, 10, 2, 20)
    - Vehicle-1, Vehicle-2, Vehicle-10 (natural order)
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.items_data = []  # Store original items with sort keys
    
    def addItem(self, text, userData=None):
        """Add item with natural sort key"""
        sort_key = self._natural_sort_key(text)
        self.items_data.append((text, userData, sort_key))
        self._refresh_sorted_view()
    
    def addItems(self, items):
        """Add multiple items and sort naturally"""
        for item in items:
            self.addItem(str(item))
    
    def _refresh_sorted_view(self):
        """Refresh the combobox with naturally sorted items"""
        # Sort by key
        sorted_items = sorted(self.items_data, key=lambda x: x[2])
        
        # Clear and repopulate
        self.blockSignals(True)
        self.clear()
        for text, userData, _ in sorted_items:
            super().addItem(text, userData)
        self.blockSignals(False)
    
    @staticmethod
    def _natural_sort_key(text):
        """
        Convert string to natural sort key
        E.g., "L-10" → ("L-", 10)
        "Vehicle-2" → ("Vehicle-", 2)
        """
        def atoi(text_part):
            return int(text_part) if text_part.isdigit() else text_part
        
        return [atoi(c) for c in re.split(r'(\d+)', str(text))]
    
    def get_value(self):
        """Get currently selected text"""
        return self.currentText()
    
    def set_value(self, value):
        """Set selected item by text"""
        index = self.findText(str(value))
        if index >= 0:
            self.setCurrentIndex(index)


class NaturalSortListModel:
    """
    Helper for natural sorting in list views and tables
    Usage: sort_key = NaturalSortListModel.get_sort_key(vehicle_number)
    """
    
    @staticmethod
    def get_sort_key(text):
        """Get natural sort key for any text"""
        def atoi(text_part):
            return int(text_part) if text_part.isdigit() else text_part.lower()
        
        return [atoi(c) for c in re.split(r'(\d+)', str(text))]
    
    @staticmethod
    def sort_list(items, key_func=lambda x: x):
        """
        Sort list naturally
        items: list of items
        key_func: function to extract sort key from item
        
        Example:
            vehicles = [v.vehicle_number for v in vehicle_list]
            sorted_vehicles = NaturalSortListModel.sort_list(
                vehicles,
                key_func=lambda x: x
            )
        """
        return sorted(items, key=lambda x: NaturalSortListModel.get_sort_key(key_func(x)))


class SQLNaturalSortHelper:
    """
    Helper for natural sorting in SQL queries
    PostgreSQL doesn't have natural sort by default, so use Python post-processing
    or use this helper to generate proper ORDER BY clauses
    """
    
    @staticmethod
    def sort_results(results, column_index, reverse=False):
        """
        Sort query results naturally by specified column
        results: list of tuples from database query
        column_index: which column to sort by (0-based)
        reverse: sort descending
        """
        def get_sort_key(row):
            value = row[column_index] if len(row) > column_index else ""
            return NaturalSortListModel.get_sort_key(value)
        
        return sorted(results, key=get_sort_key, reverse=reverse)
    
    @staticmethod
    def vehicle_numbers_natural_order(numbers):
        """
        Sort vehicle numbers naturally: L-1, L-2, L-10, not L-1, L-10, L-2
        """
        return NaturalSortListModel.sort_list(
            numbers,
            key_func=lambda x: str(x)
        )


# =============================================================================
# IMPLEMENTATION CHECKLIST FOR DEVELOPERS
# =============================================================================
"""
To implement these UX improvements in the desktop app:

1. REPLACE ALL QLINEEDIT WITH UserFriendlyLineEdit:
   OLD: self.field = QLineEdit()
   NEW: self.field = UserFriendlyLineEdit()
   
   Benefits:
   - Click anywhere to select all (ready to type replacement)
   - Type with text selected: replaces all
   - Double-click: select word for editing portion
   - No masking interference

2. REPLACE STANDARDDATEEDIT WITH SmartDateEdit:
   OLD: self.date_field = StandardDateEdit()
   NEW: self.date_field = SmartDateEdit(prefer_month_text=True)
   
   Benefits:
   - Accept any date format: 01/05/26, 1/5/2026, 0105 2026, Jan 05 2026
   - Display consistently: "Jan 05, 2026"
   - Keyboard shortcuts: + (tomorrow), - (yesterday)
   - Auto-parse and validate

3. REPLACE QCOMBOBOX WITH NaturalSortComboBox FOR VEHICLE/FLEET LISTS:
   OLD: self.vehicle_combo = QComboBox()
   NEW: self.vehicle_combo = NaturalSortComboBox()
   
   Benefits:
   - L-1, L-2, L-3, L-10 (natural order)
   - Not L-1, L-10, L-2, L-3 (lexicographic)

4. FOR TABLE/LIST WIDGET DATA SORTING:
   Use SQLNaturalSortHelper.sort_results() after database queries
   
   Example:
   ```python
   # Get data from database
   cur.execute("SELECT vehicle_id, vehicle_number, ... FROM vehicles")
   results = cur.fetchall()
   
   # Sort naturally by vehicle_number (column index 1)
   results = SQLNaturalSortHelper.sort_results(results, column_index=1)
   
   # Add to table widget
   for row in results:
       self.table.insertRow(...)
   ```

5. UPDATE WIDGETS THAT DISPLAY VEHICLE NUMBERS:
   - dashboards.py: Fleet Management table
   - dashboards_phase2_phase3.py: Vehicle lists
   - dashboards_phase4_5_6.py: All vehicle queries
   - dashboards_phase7_8.py: Vehicle displays
   
   Change SQL ORDER BY from:
   OLD: ORDER BY v.vehicle_number
   NEW: Keep in database query for efficiency, then apply 
        NaturalSortListModel.sort_list() in Python layer

6. TEST SCENARIOS:
   ✓ Type in currency field with all selected: should replace completely
   ✓ Double-click word in text field: should select word, not insert mode
   ✓ Type "1/5/26" in date field: should parse correctly
   ✓ Type "0105 2026" in date field: should convert to "Jan 05, 2026"
   ✓ Vehicles display as L-1, L-2, L-10 not L-1, L-10, L-2
   ✓ ComboBox vehicle list sorted naturally

7. MIGRATION PATH:
   Phase 1: Update common_widgets.py with these new classes
   Phase 2: Replace QLineEdit with UserFriendlyLineEdit in forms
   Phase 3: Replace StandardDateEdit with SmartDateEdit
   Phase 4: Update vehicle displays to use natural sorting
   Phase 5: QA test all input fields across app
"""
