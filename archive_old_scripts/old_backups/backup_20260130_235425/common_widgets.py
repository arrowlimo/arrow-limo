#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Common reusable widgets for the desktop application.
Provides standardized input fields with consistent behavior.
"""

from PyQt6.QtWidgets import QLineEdit, QDateEdit, QDialog, QVBoxLayout, QGridLayout, QPushButton, QLabel, QTextEdit
from PyQt6.QtCore import Qt, QTimer, QDate, pyqtSignal
from PyQt6.QtGui import QFont
import re


class CurrencyInput(QLineEdit):
    """
    Standardized currency input field with:
    - Auto-select all on click/focus
    - Auto-formatting to 2 decimal places
    - Validation colors (optional)
    - Number pad support
    - Delete/replace selected text on keypress
    """
    
    def __init__(self, parent=None, compact=False, show_validation=False):
        super().__init__(parent)
        self.setPlaceholderText("0.00")
        self.setText("0.00")
        self.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.show_validation = show_validation
        self.compact = compact
        
        if compact:
            self.setMaxLength(10)  # "999999.99" = 9 chars
            self.setMaximumWidth(100)
        else:
            self.setMaxLength(12)  # Up to $999,999.99
        
        # Default style
        self._set_style('neutral')
        
        # Tooltip
        self.setToolTip(
            "<b>💵 Currency Input</b><br>"
            "Enter amounts in any format:<br>"
            "<font color='green'><b>✓ Valid:</b></font> 10, 10.50, .50, 250<br>"
            "<font color='blue'><b>Limits:</b> $0.00 - $999,999.99</font><br>"
            "Auto-formats to 2 decimal places."
        )
        # No side-effects here; focus selection handled in focusInEvent
    
    def mousePressEvent(self, event):
        """Select all on any mouse click"""
        super().mousePressEvent(event)
        QTimer.singleShot(0, self.selectAll)
    
    def mouseDoubleClickEvent(self, event):
        """Select all on double click"""
        self.selectAll()
    
    def focusOutEvent(self, event):
        """Format when leaving the field"""
        super().focusOutEvent(event)
        self._validate_and_format()
    
    def keyPressEvent(self, event):
        """Handle numeric input - support paste and direct replacement"""
        # If text is selected and user types, replace it
        if self.selectedText() and event.text() and (event.text()[0].isdigit() or event.text()[0] == '.'):
            self.clear()
        super().keyPressEvent(event)
    
    def _validate_and_format(self):
        """Format currency: 10→10.00, 10.10→10.10, .50→0.50"""
        text = self.text().replace(',', '').replace('$', '').strip()
        
        if not text:
            self.setText("0.00")
            self._set_style('neutral')
            return
        
        try:
            val = float(text)
            if val < 0:
                val = 0.0
            elif val > 999999.99:
                val = 999999.99
                self._set_style('warning')
            else:
                self._set_style('valid')
            
            self.setText(f"{val:.2f}")
        except ValueError:
            self.setText("0.00")
            self._set_style('error')
    
    def _set_style(self, state):
        """Apply color style based on validation state"""
        if not self.show_validation:
            self.setStyleSheet("QLineEdit { text-align: right; }")
            return
        
        if state == 'valid':
            self.setStyleSheet("QLineEdit { border: 2px solid #4CAF50; background-color: #f0fdf4; text-align: right; }")
        elif state == 'warning':
            self.setStyleSheet("QLineEdit { border: 2px solid #FFC107; background-color: #fffbf0; text-align: right; }")
        elif state == 'error':
            self.setStyleSheet("QLineEdit { border: 2px solid #f44336; background-color: #fdf0f0; text-align: right; }")
        else:  # neutral
            self.setStyleSheet("QLineEdit { border: 1px solid #ccc; background-color: white; text-align: right; }")
    
    def get_value(self):
        """Get numeric value"""
        try:
            return float(self.text().replace(',', '').replace('$', ''))
        except:
            return 0.0
    
    def set_value(self, value):
        """Set numeric value"""
        try:
            val = float(value)
            self.setText(f"{val:.2f}")
        except:
            self.setText("0.00")


class StandardDateEdit(QLineEdit):
    """Unified date input: full-string typing with MM/dd/yyyy mask and QDate helpers.
    Drop-in replacement for prior QDateEdit usage in this app.
    """

    # Compatibility signal: matches QDateEdit's dateChanged signature
    dateChanged = pyqtSignal(QDate)

    def __init__(self, parent=None, prefer_month_text=False, allow_blank: bool = False):
        super().__init__(parent)
        self._allow_blank = allow_blank
        self._has_value = not allow_blank
        self._current_date = QDate.currentDate()
        self._is_formatting = False
        self.display_format = "MM/dd/yyyy"  # Keep consistent mask for typing
        self.setMaxLength(10)
        if allow_blank:
            self.setText("")
        else:
            self.setText(self._current_date.toString(self.display_format))
        self.setPlaceholderText("MM/DD/YYYY")
        self.setClearButtonEnabled(True)
        self.setMaximumWidth(130)
        # QDateEdit compatibility fields
        self._min_date = QDate(1752, 9, 14)  # Qt default Gregorian switch, harmless
        self._max_date = QDate(7999, 12, 31)
        self._special_value_text = None
        self.setToolTip(
            "<b>📅 Date Input</b><br>"
            "Type full date like 09/15/2012 or 09152012.<br>"
            "Mask applies after typing. +/- keys change day."
        )
        self.textChanged.connect(self._on_text_changed)

    # Compatibility shims with previous QDateEdit usage
    def setCalendarPopup(self, enabled: bool):
        pass  # No-op to keep API compatibility

    def setDisplayFormat(self, fmt: str):
        self.display_format = fmt or self.display_format

    def lineEdit(self):
        return self

    def setDate(self, qdate: QDate | None):
        if qdate is None and self._allow_blank:
            self._has_value = False
            self._is_formatting = True
            self.setText("")
            self._is_formatting = False
            return

        if qdate is None:
            qdate = QDate.currentDate()

        # clamp to range
        if qdate < self._min_date:
            qdate = self._min_date
        elif qdate > self._max_date:
            qdate = self._max_date

        self._current_date = qdate
        self._has_value = True
        self._is_formatting = True
        if self._special_value_text and qdate == self._min_date:
            self.setText(self._special_value_text)
        else:
            self.setText(qdate.toString(self.display_format))
        self._is_formatting = False
        # Emit compatibility signal
        self.dateChanged.emit(self._current_date)

    def date(self) -> QDate | None:
        return self._current_date if self._has_value else None

    # New helper used elsewhere in app
    def getDate(self) -> QDate | None:
        return self._current_date if self._has_value else None

    def focusInEvent(self, event):
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        QTimer.singleShot(0, self.selectAll)

    def keyPressEvent(self, event):
        # Support +/- day adjustments
        if event.key() == Qt.Key.Key_Plus:
            self.setDate(self._current_date.addDays(1))
            return
        if event.key() == Qt.Key.Key_Minus:
            self.setDate(self._current_date.addDays(-1))
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self._validate_final()

    def _on_text_changed(self, text: str):
        if self._is_formatting:
            return
        if self._allow_blank and not text.strip():
            self._has_value = False
            return
        try:
            digits = ''.join(c for c in text if c.isdigit())
            if not digits:
                return
            formatted = digits
            if len(digits) > 2:
                formatted = digits[:2] + '/' + digits[2:]
            if len(digits) > 4:
                formatted = digits[:2] + '/' + digits[2:4] + '/' + digits[4:8]
            if formatted != text:
                self._is_formatting = True
                self.setText(formatted)
                self.setCursorPosition(len(formatted))
                self._is_formatting = False
        except Exception:
            self._is_formatting = False

    def _validate_final(self):
        try:
            text = self.text().strip()
            if not text:
                if self._allow_blank:
                    self._has_value = False
                    self._is_formatting = True
                    self.setText("")
                    self._is_formatting = False
                    return
                self._is_formatting = True
                if self._special_value_text and self._current_date == self._min_date:
                    self.setText(self._special_value_text)
                else:
                    self.setText(self._current_date.toString(self.display_format))
                self._is_formatting = False
                return
            parsed = QDate.fromString(text, "MM/dd/yyyy")
            if parsed.isValid():
                changed = (parsed != self._current_date)
                self._current_date = parsed
                self._has_value = True
                self._is_formatting = True
                if self._special_value_text and parsed == self._min_date:
                    self.setText(self._special_value_text)
                else:
                    self.setText(parsed.toString(self.display_format))
                self._is_formatting = False
                if changed:
                    self.dateChanged.emit(self._current_date)
            else:
                # try lenient fallback: MMDDYYYY
                digits = ''.join(c for c in text if c.isdigit())
                if len(digits) == 8:
                    m, d, y = int(digits[:2]), int(digits[2:4]), int(digits[4:])
                    candidate = QDate(y, m, d)
                    if candidate.isValid():
                        changed = (candidate != self._current_date)
                        self._current_date = candidate
                        self._has_value = True
                        self._is_formatting = True
                        if self._special_value_text and candidate == self._min_date:
                            self.setText(self._special_value_text)
                        else:
                            self.setText(candidate.toString(self.display_format))
                        self._is_formatting = False
                        if changed:
                            self.dateChanged.emit(self._current_date)
                        return
                # restore previous on failure
                self._is_formatting = True
                if self._special_value_text and self._current_date == self._min_date:
                    self.setText(self._special_value_text)
                else:
                    self.setText(self._current_date.toString(self.display_format))
                self._is_formatting = False
        except Exception:
            self._is_formatting = False

    # QDateEdit compatibility helpers
    def setSpecialValueText(self, text: str):
        self._special_value_text = text
        # refresh display to reflect special text possibly
        self._is_formatting = True
        if self._current_date == self._min_date and text:
            self.setText(text)
        else:
            self.setText(self._current_date.toString(self.display_format))
        self._is_formatting = False

    def specialValueText(self) -> str | None:
        return self._special_value_text

    def setMinimumDate(self, qdate: QDate):
        self._min_date = qdate
        # Clamp current date
        if self._current_date < qdate:
            self.setDate(qdate)

    def setMaximumDate(self, qdate: QDate):
        self._max_date = qdate
        if self._current_date > qdate:
            self.setDate(qdate)

    def setDateRange(self, min_date: QDate, max_date: QDate):
        self._min_date = min_date
        self._max_date = max_date
        if self._current_date < min_date:
            self.setDate(min_date)
        elif self._current_date > max_date:
            self.setDate(max_date)


class SimpleCalculator(QDialog):
    """Simple calculator dialog with number pad for currency input"""
    
    def __init__(self, initial_value=0.0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Calculator")
        self.setMinimumWidth(300)
        self.setMinimumHeight(400)
        self.display_value = str(initial_value) if initial_value != 0.0 else "0"
        self.pending_operation = None
        self.pending_value = None
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Display
        self.display = QLineEdit()
        self.display.setReadOnly(True)
        self.display.setText(self.display_value)
        self.display.setAlignment(Qt.AlignmentFlag.AlignRight)
        display_font = QFont()
        display_font.setPointSize(18)
        display_font.setBold(True)
        self.display.setFont(display_font)
        self.display.setStyleSheet("padding: 10px; background-color: #f0f0f0; border: 2px solid #333;")
        layout.addWidget(self.display)
        
        # Button grid
        grid = QGridLayout()
        grid.setSpacing(5)
        
        buttons = [
            ('7', 0, 0), ('8', 0, 1), ('9', 0, 2), ('÷', 0, 3),
            ('4', 1, 0), ('5', 1, 1), ('6', 1, 2), ('×', 1, 3),
            ('1', 2, 0), ('2', 2, 1), ('3', 2, 2), ('-', 2, 3),
            ('0', 3, 0), ('.', 3, 1), ('C', 3, 2), ('+', 3, 3),
            ('=', 4, 0, 1, 4)  # Equals spans 4 columns
        ]
        
        for btn_data in buttons:
            if len(btn_data) == 5:  # Spanning button
                text, row, col, rowspan, colspan = btn_data
            else:
                text, row, col = btn_data
                rowspan, colspan = 1, 1
            
            btn = QPushButton(text)
            btn.setMinimumHeight(50)
            btn.setStyleSheet("font-size: 16px; font-weight: bold;")
            btn.clicked.connect(lambda checked, t=text: self.button_clicked(t))
            grid.addWidget(btn, row, col, rowspan, colspan)
        
        layout.addLayout(grid)
    
    def button_clicked(self, text):
        """Handle button clicks"""
        if text.isdigit():
            if self.display_value == "0" or self.pending_operation == '=':
                self.display_value = text
                if self.pending_operation == '=':
                    self.pending_operation = None
            else:
                self.display_value += text
        
        elif text == '.':
            if '.' not in self.display_value:
                self.display_value += '.'
        
        elif text == 'C':
            self.display_value = "0"
            self.pending_operation = None
            self.pending_value = None
        
        elif text in ['+', '-', '×', '÷']:
            if self.pending_operation and self.pending_value is not None:
                self.calculate()
            self.pending_value = float(self.display_value)
            self.pending_operation = text
            self.display_value = "0"
        
        elif text == '=':
            self.calculate()
            self.pending_operation = '='
        
        self.display.setText(self.display_value)
    
    def calculate(self):
        """Perform calculation"""
        if self.pending_operation is None or self.pending_value is None:
            return
        
        try:
            current = float(self.display_value)
            if self.pending_operation == '+':
                result = self.pending_value + current
            elif self.pending_operation == '-':
                result = self.pending_value - current
            elif self.pending_operation == '×':
                result = self.pending_value * current
            elif self.pending_operation == '÷':
                result = self.pending_value / current if current != 0 else 0
            else:
                return
            
            self.display_value = f"{result:.2f}"
            self.pending_value = result
        except:
            self.display_value = "ERROR"
    
    def get_result(self):
        """Get final result"""
        try:
            return float(self.display_value)
        except:
            return 0.0


class CalculatorButton(QPushButton):
    """Calculator button that opens calculator dialog for a currency input"""
    
    def __init__(self, currency_input, parent=None):
        super().__init__("🧮", parent)
        self.currency_input = currency_input
        self.setMaximumWidth(30)
        self.setToolTip("Open Calculator")
        self.clicked.connect(self.open_calculator)
    
    def open_calculator(self):
        """Open calculator dialog"""
        initial_value = self.currency_input.get_value()
        calc = SimpleCalculator(initial_value, self)
        if calc.exec() == QDialog.DialogCode.Accepted:
            result = calc.get_result()
            self.currency_input.set_value(result)


class StandardTextEdit(QTextEdit):
    """
    Standardized multi-line text input with:
    - Consistent font (Segoe UI, 9pt)
    - Plain text only (strips formatting on paste)
    - Optional height constraint
    """
    
    def __init__(self, parent=None, max_height=None):
        super().__init__(parent)
        
        # Set standard font
        font = QFont("Segoe UI", 9)
        self.setFont(font)
        
        # Disable rich text to strip formatting on paste
        self.setAcceptRichText(False)
        
        # Optional height limit
        if max_height:
            self.setMaximumHeight(max_height)
        
        # Tooltip
        self.setToolTip(
            "<b>📝 Text Input</b><br>"
            "Multi-line text field.<br>"
            "Pasted content will be converted to plain text."
        )
