"""
Shared report widget base with toolbar and table utilities.
Provides: refresh, filter, column toggles, export CSV, quick totals.
"""

import csv
from decimal import Decimal
from typing import Callable, Dict, List, Any

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QLabel,
    QToolBar,
    QFileDialog,
    QTableWidget,
    QTableWidgetItem,
    QAbstractItemView,
    QMessageBox,
    QToolButton,
    QMenu,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction


class BaseReportWidget(QWidget):
    """Reusable report widget with a standard toolbar and table helpers."""

    def __init__(self, db, title: str, columns: List[Dict[str, Any]]):
        super().__init__()
        self.db = db
        self.title = title
        self.columns = columns
        self.rows: List[Dict[str, Any]] = []
        self.raw_values = {}

        self.table = QTableWidget()
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels([c.get("header", "") for c in columns])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.itemSelectionChanged.connect(self.update_selection_summary)
        self.table.doubleClicked.connect(self.open_drill_down_dialog)  # Drill-down on double-click

        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter rows (live)")
        self.filter_input.textChanged.connect(self.apply_filter)

        self.summary_label = QLabel("Ready")
        self.summary_label.setStyleSheet("color: gray; font-size: 11px;")

        layout = QVBoxLayout()
        layout.addWidget(self._build_toolbar())
        layout.addLayout(self._build_filter_row())
        layout.addWidget(self.table)
        layout.addWidget(self.summary_label)
        self.setLayout(layout)

        # Initial load
        self.refresh()

    # ------------------------------------------------------------------
    # UI builders
    # ------------------------------------------------------------------
    def _build_toolbar(self):
        toolbar = QToolBar()

        refresh_action = QAction("Refresh", self)
        refresh_action.triggered.connect(self.refresh)
        toolbar.addAction(refresh_action)

        export_action = QAction("Export CSV", self)
        export_action.triggered.connect(self.export_csv)
        toolbar.addAction(export_action)

        self.columns_menu_button = QToolButton()
        self.columns_menu_button.setText("Columns")
        self.columns_menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        toolbar.addWidget(self.columns_menu_button)

        toolbar.addSeparator()

        return toolbar

    def _build_filter_row(self):
        row = QHBoxLayout()
        row.addWidget(QLabel("Filter:"))
        row.addWidget(self.filter_input)
        row.addStretch()
        return row

    # ------------------------------------------------------------------
    # Data lifecycle
    # ------------------------------------------------------------------
    def refresh(self):
        try:
            self.load_data()
            self.apply_filter()
            self.update_selection_summary()
            self.summary_label.setText("Refreshed")
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Could not load report:\n{e}")

    def load_data(self):
        """Fetch rows from subclass and populate the table."""
        self.rows = self.fetch_rows()
        self._populate_table(self.rows)
        self._build_column_menu()

    def fetch_rows(self) -> List[Dict[str, Any]]:
        """Subclasses must implement and return a list of dict rows."""
        raise NotImplementedError

    def _populate_table(self, rows: List[Dict[str, Any]]):
        self.raw_values.clear()
        self.table.setRowCount(len(rows))
        for r_idx, row in enumerate(rows):
            for c_idx, col in enumerate(self.columns):
                key = col.get("key")
                formatter: Callable[[Any], str] = col.get("format")
                val = row.get(key)
                display = formatter(val) if formatter else ("" if val is None else str(val))
                item = QTableWidgetItem(display)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(r_idx, c_idx, item)
                self.raw_values[(r_idx, c_idx)] = val
        self.table.resizeColumnsToContents()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def apply_filter(self):
        text = (self.filter_input.text() or "").lower()
        for row in range(self.table.rowCount()):
            match = False
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item and text in item.text().lower():
                    match = True
                    break
            self.table.setRowHidden(row, not match if text else False)

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", "report.csv", "CSV Files (*.csv)")
        if not path:
            return
        headers = [col.get("header", "") for col in self.columns]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for row_idx in range(self.table.rowCount()):
                if self.table.isRowHidden(row_idx):
                    continue
                writer.writerow([self.table.item(row_idx, c).text() if self.table.item(row_idx, c) else "" for c in range(self.table.columnCount())])
        QMessageBox.information(self, "Exported", f"Saved to {path}")

    def _build_column_menu(self):
        menu = self.columns_menu_button.menu()
        if menu:
            menu.clear()
        else:
            menu = QMenu(self)
            self.columns_menu_button.setMenu(menu)

        for idx, col in enumerate(self.columns):
            action = QAction(col.get("header", f"Col {idx+1}"), self, checkable=True, checked=True)
            action.toggled.connect(lambda checked, col_idx=idx: self.table.setColumnHidden(col_idx, not checked))
            menu.addAction(action)

    def print_report(self):
        """Print the current report"""
        try:
            from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
            from PyQt6.QtGui import QPageSize
            
            printer = QPrinter()
            dialog = QPrintDialog(printer, self)
            
            if dialog.exec() == dialog.DialogCode.Accepted:
                # Create HTML from table
                html = self._table_to_html()
                # Print HTML
                from PyQt6.QtGui import QTextDocument
                doc = QTextDocument()
                doc.setHtml(html)
                doc.print(printer)
                QMessageBox.information(self, "Success", "Report sent to printer")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Print failed: {e}")
    
    def _table_to_html(self):
        """Convert table to HTML"""
        html = f"<h2>{self.title}</h2><table border='1' style='border-collapse:collapse;'><tr>"
        
        # Headers
        for i in range(self.table.columnCount()):
            header = self.table.horizontalHeaderItem(i)
            if header:
                html += f"<th style='padding:8px;'>{header.text()}</th>"
        html += "</tr>"
        
        # Rows
        for i in range(self.table.rowCount()):
            html += "<tr>"
            for j in range(self.table.columnCount()):
                item = self.table.item(i, j)
                text = item.text() if item else ""
                html += f"<td style='padding:8px;'>{text}</td>"
            html += "</tr>"
        
        html += "</table>"
        return html


    def update_selection_summary(self):
        total = 0.0
        count = 0
        for index in self.table.selectedIndexes():
            val = self.raw_values.get((index.row(), index.column()))
            if isinstance(val, (int, float, Decimal)):
                total += float(val)
                count += 1
        if count:
            self.summary_label.setText(f"Selected {count} cells • Sum={total:,.2f}")
        else:
            self.summary_label.setText("Ready")
    
    def open_drill_down_dialog(self, index):
        """Open detail dialog for editing row data"""
        from PyQt6.QtWidgets import QDialog, QFormLayout, QLineEdit, QPushButton, QTextEdit
        from PyQt6.QtCore import Qt
        
        row = index.row()
        if row < 0 or row >= len(self.rows):
            return
        
        row_data = self.rows[row]
        
        # Create detail dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Detail View - {self.title}")
        dialog.setGeometry(100, 100, 500, 400)
        
        layout = QVBoxLayout()
        form = QFormLayout()
        
        # Create editable fields for each column
        fields = {}
        for col in self.columns:
            key = col.get("key")
            header = col.get("header", key)
            value = row_data.get(key, "")
            
            # Determine widget type
            if key in ['notes', 'description', 'comments']:
                widget = QTextEdit()
                widget.setPlainText(str(value or ""))
                widget.setMaximumHeight(80)
            else:
                widget = QLineEdit()
                widget.setText(str(value or ""))
            
            fields[key] = widget
            form.addRow(f"{header}:", widget)
        
        layout.addLayout(form)
        
        # Button row
        button_layout = QHBoxLayout()
        
        save_btn = QPushButton("💾 Save Corrections")
        save_btn.clicked.connect(lambda: self._save_drill_down_corrections(row, fields, dialog))
        button_layout.addWidget(save_btn)
        
        back_btn = QPushButton("⬅ Back (No Save)")
        back_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(back_btn)
        
        layout.addLayout(button_layout)
        
        dialog.setLayout(layout)
        dialog.exec()
    
    def _save_drill_down_corrections(self, row, fields, dialog):
        """Save corrections made in drill-down dialog"""
        try:
            # Update local row data
            row_data = self.rows[row]
            for key, widget in fields.items():
                if isinstance(widget, QTextEdit):
                    new_value = widget.toPlainText()
                else:
                    new_value = widget.text()
                
                # Update display table
                for c_idx, col in enumerate(self.columns):
                    if col.get("key") == key:
                        formatter = col.get("format")
                        display = formatter(new_value) if formatter else new_value
                        self.table.setItem(row, c_idx, QTableWidgetItem(display))
                        row_data[key] = new_value
                        break
            
            # Call subclass hook to save to database
            if hasattr(self, 'save_row_corrections'):
                self.save_row_corrections(row, row_data)
            
            QMessageBox.information(self, "Success", "Changes saved locally. Sync with database to persist.")
            dialog.close()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")