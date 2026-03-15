#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Extensions to common_widgets.py - Natural Sorting and Smart Input
Add these classes to common_widgets.py or import from here
"""

import re
from PyQt6.QtWidgets import QComboBox
from PyQt6.QtCore import Qt


class NaturalSortComboBox(QComboBox):
    """
    ComboBox with natural sorting:
    Displays L-1, L-2, L-3, L-10 (correct)
    NOT L-1, L-10, L-2, L-3 (wrong - lexicographic)
    
    Usage:
    combo = NaturalSortComboBox()
    combo.addItem("L-1")
    combo.addItem("L-10")
    combo.addItem("L-2")
    combo.addItem("L-3")
    # Will display in natural order: L-1, L-2, L-3, L-10
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.items_data = []  # Store (text, userData, sort_key)
    
    def addItem(self, text, userData=None):
        """Add item with natural sorting"""
        sort_key = self._natural_sort_key(text)
        self.items_data.append((text, userData, sort_key))
        self._refresh_sorted_view()
    
    def addItems(self, items):
        """Add multiple items with natural sorting"""
        for item in items:
            self.addItem(str(item))
    
    def _refresh_sorted_view(self):
        """Refresh display with naturally sorted items"""
        # Sort by the sort key
        sorted_items = sorted(self.items_data, key=lambda x: x[2])
        
        # Update combobox without triggering signals
        self.blockSignals(True)
        self.clear()
        for text, userData, _ in sorted_items:
            super().addItem(text, userData)
        self.blockSignals(False)
    
    @staticmethod
    def _natural_sort_key(text):
        """
        Convert text to natural sort key
        Example: "L-10" → ("L-", 10)
                 "L-2"  → ("L-", 2)
        This ensures L-2 < L-10 naturally
        """
        def atoi(part):
            return int(part) if part.isdigit() else part
        
        return [atoi(c) for c in re.split(r'(\d+)', str(text))]


class NaturalSortHelper:
    """
    Helper functions for natural sorting in tables and lists
    
    Usage examples:
    # Sort a list of vehicle numbers
    vehicles = ["L-1", "L-10", "L-2", "L-3"]
    sorted_vehicles = NaturalSortHelper.sort_items(vehicles)
    # Result: ["L-1", "L-2", "L-3", "L-10"]
    
    # Sort database query results by vehicle_number (column index 1)
    results = cur.fetchall()  # list of tuples
    sorted_results = NaturalSortHelper.sort_rows(results, column_index=1)
    """
    
    @staticmethod
    def get_sort_key(text):
        """Get natural sort key for any text"""
        def atoi(part):
            return int(part) if part.isdigit() else part.lower()
        
        return [atoi(c) for c in re.split(r'(\d+)', str(text))]
    
    @staticmethod
    def sort_items(items):
        """Sort list of items naturally"""
        return sorted(items, key=NaturalSortHelper.get_sort_key)
    
    @staticmethod
    def sort_rows(rows, column_index):
        """
        Sort database query results naturally
        Args:
            rows: list of tuples from database query
            column_index: which column to sort by (0-based)
        
        Example:
            cur.execute("SELECT * FROM vehicles")
            results = cur.fetchall()
            # Sort by vehicle_number (column 1)
            results = NaturalSortHelper.sort_rows(results, column_index=1)
        """
        def get_key(row):
            value = row[column_index] if len(row) > column_index else ""
            return NaturalSortHelper.get_sort_key(str(value))
        
        return sorted(rows, key=get_key)


# ============================================================================
# SQL HELPER FOR NATURAL SORT IN PYTHON LAYER
# ============================================================================

def apply_natural_sort_to_sql_results(cursor_results, column_to_sort, column_index):
    """
    Apply natural sorting to SQL results
    
    Args:
        cursor_results: list of tuples from cur.fetchall()
        column_to_sort: name of column to sort by (for reference only)
        column_index: 0-based index of column in tuple
    
    Returns:
        Naturally sorted list of tuples
    
    Example:
        cur.execute("SELECT vehicle_id, vehicle_number, make FROM vehicles")
        results = cur.fetchall()
        results = apply_natural_sort_to_sql_results(results, 'vehicle_number', column_index=1)
        for row in results:
            print(row)  # Will be in natural order
    """
    return NaturalSortHelper.sort_rows(cursor_results, column_index)
