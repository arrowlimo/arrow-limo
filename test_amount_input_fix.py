"""
Test script to verify amount input select-all behavior
Run with: python test_amount_input_fix.py
"""

import sys
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QDoubleSpinBox
from PyQt6.QtCore import Qt

class CurrencyInput(QLineEdit):
    """Currency input field with select-all on focus/click"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("0.00")
        self.setText("126.01")
        self.setAlignment(Qt.AlignmentFlag.AlignRight)
        
    def focusInEvent(self, event):
        """Select all text when field gets focus"""
        super().focusInEvent(event)
        self.selectAll()
    
    def mousePressEvent(self, event):
        """Select all on any mouse click - prevents cursor positioning"""
        # Don't call super first - we want selectAll to stick
        if not self.hasFocus():
            super().mousePressEvent(event)
        self.selectAll()
        event.accept()


class AmountSpinBox(QDoubleSpinBox):
    """Custom QDoubleSpinBox that selects all on focus/click for easy replacement"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDecimals(2)
        self.setMaximum(999999.99)
        self.setMinimum(0.00)
        self.setPrefix("$")
        self.setValue(126.01)
        
    def focusInEvent(self, event):
        """Select all text when field gets focus"""
        super().focusInEvent(event)
        self.selectAll()
    
    def mousePressEvent(self, event):
        """Select all on any mouse click"""
        if not self.hasFocus():
            super().mousePressEvent(event)
        self.selectAll()
        event.accept()


class TestWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Amount Input Test - Select All Fix")
        self.setGeometry(100, 100, 400, 300)
        
        layout = QVBoxLayout()
        
        # Instructions
        instructions = QLabel(
            "<h3>Test: Amount Input Select-All Behavior</h3>"
            "<p><b>Instructions:</b></p>"
            "<ol>"
            "<li>Click on any field below - the entire value should be selected (highlighted)</li>"
            "<li>Type a new number (e.g., 456.78) - it should REPLACE the old value, not insert characters</li>"
            "<li>Click on different parts of the field - it should always select all</li>"
            "</ol>"
            "<p><b>✅ FIXED:</b> No more character insertion on left side!</p>"
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # Test with CurrencyInput (QLineEdit-based)
        layout.addWidget(QLabel("<b>1. CurrencyInput (QLineEdit):</b>"))
        self.currency_input = CurrencyInput()
        layout.addWidget(self.currency_input)
        
        # Test with AmountSpinBox (QDoubleSpinBox-based)
        layout.addWidget(QLabel("<b>2. AmountSpinBox (QDoubleSpinBox):</b>"))
        self.amount_spin = AmountSpinBox()
        layout.addWidget(self.amount_spin)
        
        # Standard QDoubleSpinBox for comparison (OLD behavior)
        layout.addWidget(QLabel("<b>3. Standard QDoubleSpinBox (OLD behavior for comparison):</b>"))
        self.standard_spin = QDoubleSpinBox()
        self.standard_spin.setPrefix("$")
        self.standard_spin.setDecimals(2)
        self.standard_spin.setValue(126.01)
        layout.addWidget(self.standard_spin)
        
        layout.addStretch()
        self.setLayout(layout)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec())
