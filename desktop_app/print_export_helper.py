"""
Print & Export Functionality for Management Widgets
Provides: Print, Print Preview, Export to CSV/Excel
"""
import csv
import os
from datetime import datetime
from typing import List, Tuple
from PyQt6.QtCore import Qt, QMarginsF, QSizeF
from PyQt6.QtGui import QPageSize, QFont, QColor
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog, QPrintPreviewDialog
from PyQt6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QMessageBox, QFileDialog, QDialog, 
    QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QCheckBox, QPushButton
)
from PyQt6.QtGui import QTextDocument, QTextTable, QTextTableFormat, QTextCursor


class PrintExportHelper:
    """Handles printing and exporting of table data."""
    
    @staticmethod
    def print_table(table: QTableWidget, title: str, parent=None):
        """Print table with custom settings."""
        dialog = QFileDialog()
        dialog.setFileMode(QFileDialog.FileMode.AnyFile)
        dialog.setDefaultSuffix("pdf")
        
        filename, _ = QFileDialog.getSaveFileName(
            parent, 
            f"Print {title}", 
            f"{title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            "PDF Files (*.pdf);;All Files (*)"
        )
        
        if filename:
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(filename)
            printer.setPageSize(QPageSize.A4)
            printer.setPageMargins(10, 10, 10, 10, QPrinter.Unit.Millimeter)
            
            # Create document
            doc = QTextDocument()
            doc.setDefaultFont(QFont("Arial", 10))
            
            # Add title
            cursor = QTextCursor(doc)
            title_fmt = cursor.blockFormat()
            title_fmt.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cursor.setBlockFormat(title_fmt)
            cursor.insertText(f"{title}\n")
            cursor.insertText(f"Printed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Add table
            table_data = PrintExportHelper._extract_table_data(table, selected_only=False)
            PrintExportHelper._insert_table_into_document(cursor, table_data, table)
            
            # Print
            doc.print(printer)
            QMessageBox.information(parent, "Success", f"Document printed to:\n{filename}")
    
    @staticmethod
    def print_preview(table: QTableWidget, title: str, parent=None):
        """Show print preview dialog."""
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPageSize(QPageSize.A4)
        printer.setPageMargins(10, 10, 10, 10, QPrinter.Unit.Millimeter)
        
        # Create document
        doc = QTextDocument()
        doc.setDefaultFont(QFont("Arial", 9))
        
        cursor = QTextCursor(doc)
        title_fmt = cursor.blockFormat()
        title_fmt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cursor.setBlockFormat(title_fmt)
        cursor.insertText(f"{title}\n")
        cursor.insertText(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # Add table
        table_data = PrintExportHelper._extract_table_data(table, selected_only=False)
        PrintExportHelper._insert_table_into_document(cursor, table_data, table)
        
        # Show preview
        preview_dialog = QPrintPreviewDialog(printer, parent)
        preview_dialog.paintRequested.connect(lambda p: doc.print(p))
        preview_dialog.exec()
    
    @staticmethod
    def export_csv(table: QTableWidget, title: str, selected_only: bool = False, parent=None):
        """Export table data to CSV."""
        filename, _ = QFileDialog.getSaveFileName(
            parent,
            f"Export {title} to CSV",
            f"{title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if filename:
            try:
                table_data = PrintExportHelper._extract_table_data(table, selected_only=selected_only)
                
                with open(filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    # Write headers
                    writer.writerow(table_data['headers'])
                    # Write data rows
                    writer.writerows(table_data['rows'])
                
                row_count = len(table_data['rows'])
                QMessageBox.information(
                    parent,
                    "Export Success",
                    f"Exported {row_count} rows to:\n{filename}"
                )
            except Exception as e:
                QMessageBox.critical(parent, "Export Error", f"Failed to export:\n{e}")
    
    @staticmethod
    def export_excel(table: QTableWidget, title: str, selected_only: bool = False, parent=None):
        """Export table data to Excel (requires openpyxl)."""
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill, Alignment
        except ImportError:
            QMessageBox.warning(
                parent,
                "Missing Library",
                "openpyxl not installed.\nInstall with: pip install openpyxl\n\nUsing CSV export instead."
            )
            PrintExportHelper.export_csv(table, title, selected_only, parent)
            return
        
        filename, _ = QFileDialog.getSaveFileName(
            parent,
            f"Export {title} to Excel",
            f"{title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            "Excel Files (*.xlsx);;All Files (*)"
        )
        
        if filename:
            try:
                wb = Workbook()
                ws = wb.active
                ws.title = title[:31]  # Excel sheet name limit
                
                table_data = PrintExportHelper._extract_table_data(table, selected_only=selected_only)
                
                # Write headers with formatting
                header_font = Font(bold=True, color="FFFFFF")
                header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
                header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                
                for col, header in enumerate(table_data['headers'], 1):
                    cell = ws.cell(row=1, column=col, value=header)
                    cell.font = header_font
                    cell.fill = header_fill
                    cell.alignment = header_alignment
                
                # Write data rows
                for row_idx, row_data in enumerate(table_data['rows'], 2):
                    for col_idx, value in enumerate(row_data, 1):
                        cell = ws.cell(row=row_idx, column=col_idx, value=value)
                        cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
                
                # Auto-adjust column widths
                for col in ws.columns:
                    max_length = 0
                    column = col[0].column_letter
                    for cell in col:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(cell.value)
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    ws.column_dimensions[column].width = adjusted_width
                
                wb.save(filename)
                row_count = len(table_data['rows'])
                QMessageBox.information(
                    parent,
                    "Export Success",
                    f"Exported {row_count} rows to:\n{filename}"
                )
            except Exception as e:
                QMessageBox.critical(parent, "Export Error", f"Failed to export:\n{e}")
    
    @staticmethod
    def _extract_table_data(table: QTableWidget, selected_only: bool = False) -> dict:
        """Extract data from table widget."""
        data = {
            'headers': [],
            'rows': []
        }
        
        # Get headers
        for col in range(table.columnCount()):
            header_item = table.horizontalHeaderItem(col)
            if header_item:
                data['headers'].append(header_item.text())
            else:
                data['headers'].append(f"Column {col + 1}")
        
        # Get rows
        if selected_only:
            selected_rows = set()
            for item in table.selectedItems():
                selected_rows.add(item.row())
            rows_to_export = sorted(list(selected_rows))
        else:
            rows_to_export = range(table.rowCount())
        
        for row in rows_to_export:
            row_data = []
            for col in range(table.columnCount()):
                item = table.item(row, col)
                if item:
                    row_data.append(item.text())
                else:
                    row_data.append("")
            data['rows'].append(row_data)
        
        return data
    
    @staticmethod
    def _insert_table_into_document(cursor, table_data: dict, table_widget: QTableWidget):
        """Insert table into QTextDocument."""
        # Create table format
        table_format = QTextTableFormat()
        table_format.setAlignment(Qt.AlignmentFlag.AlignLeft)
        table_format.setBorder(1)
        table_format.setCellPadding(5)
        table_format.setCellSpacing(0)
        
        # Insert table
        num_rows = len(table_data['rows']) + 1  # +1 for header
        num_cols = len(table_data['headers'])
        table = cursor.insertTable(num_rows, num_cols, table_format)
        
        # Set column widths
        for i in range(num_cols):
            table.columns[i].setWidth(400 / num_cols)  # Distribute evenly
        
        # Write headers
        for col, header in enumerate(table_data['headers']):
            cell = table.cellAt(0, col)
            cell_cursor = cell.firstCursorPosition()
            
            fmt = cell_cursor.charFormat()
            fmt.setFontWeight(900)  # Bold
            cell_cursor.setCharFormat(fmt)
            cell_cursor.insertText(header)
        
        # Write data
        for row_idx, row_data in enumerate(table_data['rows'], 1):
            for col_idx, value in enumerate(row_data):
                cell = table.cellAt(row_idx, col_idx)
                cell_cursor = cell.firstCursorPosition()
                cell_cursor.insertText(str(value))


class PrintOptionsDialog(QDialog):
    """Dialog for print options selection."""
    
    def __init__(self, table: QTableWidget, parent=None):
        super().__init__(parent)
        self.table = table
        self.setWindowTitle("Print Options")
        self.setGeometry(100, 100, 400, 300)
        self._build_ui()
    
    def _build_ui(self):
        """Build the dialog UI."""
        layout = QVBoxLayout(self)
        
        # Title
        layout.addWidget(QLabel("Print Settings:"))
        
        # Options
        self.print_all = QCheckBox("Print All Rows")
        self.print_all.setChecked(True)
        layout.addWidget(self.print_all)
        
        self.print_selected = QCheckBox("Print Selected Rows Only")
        self.print_selected.setChecked(False)
        layout.addWidget(self.print_selected)
        
        # Scale
        layout.addWidget(QLabel("Scale (% of page width):"))
        self.scale_spinner = QSpinBox()
        self.scale_spinner.setRange(50, 200)
        self.scale_spinner.setValue(100)
        layout.addWidget(self.scale_spinner)
        
        # Page size
        layout.addWidget(QLabel("Page Size:"))
        self.page_size = QCheckBox("Landscape (A4)")
        self.page_size.setChecked(False)
        layout.addWidget(self.page_size)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        print_btn = QPushButton("Print")
        print_btn.clicked.connect(self.accept)
        button_layout.addWidget(print_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addStretch()
        layout.addLayout(button_layout)
    
    def get_options(self):
        """Return selected options."""
        return {
            'selected_only': self.print_selected.isChecked(),
            'scale': self.scale_spinner.value(),
            'landscape': self.page_size.isChecked()
        }
