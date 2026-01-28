"""
Drill-Down Table Mixin - Add double-click detail view to any dashboard table
Provides consistent drill-down behavior across all widgets
"""

from PyQt6.QtWidgets import QTableWidget
from PyQt6.QtCore import Qt, QModelIndex
from drill_down_widgets import CharterDetailDialog


class DrillDownTableMixin:
    """Mixin to add double-click drill-down capability to tables"""
    
    def enable_drill_down(self, table_widget, key_column=0, detail_callback=None):
        """
        Enable double-click detail view on table
        
        Args:
            table_widget: QTableWidget to enable drill-down on
            key_column: Column index containing the business key (default: 0)
            detail_callback: Optional callback function(key_value) for custom detail views
        """
        self.detail_table = table_widget
        self.detail_key_column = key_column
        self.detail_callback = detail_callback
        
        # Connect double-click signal
        table_widget.doubleClicked.connect(self.on_row_double_clicked)
    
    def on_row_double_clicked(self, index: QModelIndex):
        """Handle double-click on table row"""
        row = index.row()
        col = self.detail_key_column
        
        # Get the key value from the specified column
        key_widget = self.detail_table.item(row, col)
        if key_widget:
            key_value = key_widget.text()
            
            # Call custom callback if provided, otherwise use default charter detail
            if self.detail_callback:
                self.detail_callback(key_value)
            else:
                self.open_charter_detail(key_value)
    
    def open_charter_detail(self, reserve_number):
        """Open charter detail dialog for the given reserve number"""
        if hasattr(self, 'db'):
            dialog = CharterDetailDialog(self.db, reserve_number, self)
            dialog.exec()
        else:
            print("❌ Database connection not available")


class FilterableTableMixin:
    """Mixin to add filtering capability to tables"""
    
    def add_filter_row(self, table_widget, filter_columns=None):
        """Add filter row above table"""
        # Insert a row at the top for filters
        table_widget.insertRow(0)
        
        if filter_columns is None:
            filter_columns = list(range(table_widget.columnCount()))
        
        for col in filter_columns:
            from PyQt6.QtWidgets import QLineEdit
            filter_edit = QLineEdit()
            filter_edit.setPlaceholderText(f"Filter...")
            filter_edit.textChanged.connect(
                lambda text, c=col: self.apply_filter(table_widget, c, text)
            )
            table_widget.setCellWidget(0, col, filter_edit)
    
    def apply_filter(self, table_widget, column, filter_text):
        """Apply filter to table rows"""
        for row in range(1, table_widget.rowCount()):
            item = table_widget.item(row, column)
            if item:
                item.setHidden(filter_text.lower() not in item.text().lower())
            else:
                # Try cell widget
                widget = table_widget.cellWidget(row, column)
                if widget:
                    table_widget.setRowHidden(row, True)
