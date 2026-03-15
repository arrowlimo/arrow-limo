"""
UI Standards and Helpers for Desktop Application
Provides consistent sizing, tab order, and fuzzy search functionality
"""

from PyQt6.QtWidgets import (
    QTableWidget, QHeaderView, QLineEdit, QTextEdit, QDateEdit,
    QComboBox, QSpinBox, QDoubleSpinBox, QWidget, QCompleter
)
from PyQt6.QtCore import Qt, pyqtSignal
from typing import List, Dict, Optional


# ============================================================
# STANDARD COLUMN WIDTHS (in pixels)
# ============================================================
COLUMN_WIDTHS = {
    # ID fields
    'id': 60,
    'reserve_number': 90,
    'receipt_id': 70,
    'payment_id': 70,
    'employee_id': 70,
    'client_id': 70,
    'vehicle_id': 70,
    
    # Date fields
    'date': 100,
    'datetime': 140,
    'time': 80,
    
    # Currency/Amount fields
    'amount': 110,
    'currency': 110,
    'balance': 110,
    'total': 110,
    
    # Status/Category fields
    'status': 90,
    'category': 100,
    'type': 100,
    
    # Name fields
    'name': 150,
    'employee_name': 150,
    'client_name': 150,
    'vendor_name': 180,
    
    # Phone/Email
    'phone': 120,
    'email': 200,
    
    # Vehicle fields
    'vehicle': 100,
    'plate': 90,
    
    # Location fields
    'city': 120,
    'address': 250,
    'location': 180,
    
    # Boolean/Checkbox
    'checkbox': 50,
    'boolean': 70,
    
    # Description/Notes (stretchy)
    'description': 300,
    'notes': 300,
}


# ============================================================
# STANDARD FORM FIELD WIDTHS
# ============================================================
FIELD_WIDTHS = {
    'id': 100,
    'date': 150,
    'time': 100,
    'phone': 150,
    'email': 250,
    'postal_code': 120,
    'amount': 150,
    'short_text': 200,
    'medium_text': 300,
    'long_text': 400,
}


class SmartTableWidget(QTableWidget):
    """
    Enhanced QTableWidget with smart column sizing and auto-configuration
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.column_configs = {}
        
    def setup_columns(self, headers: List[str], column_types: Optional[Dict[str, str]] = None):
        """
        Setup columns with smart sizing based on data type
        
        Args:
            headers: List of column header names
            column_types: Dict mapping header name to type (date, amount, id, name, description, etc.)
        """
        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)
        
        header = self.horizontalHeader()
        
        for i, col_name in enumerate(headers):
            # Determine column type
            col_type = None
            if column_types and col_name in column_types:
                col_type = column_types[col_name]
            else:
                # Auto-detect from column name
                col_name_lower = col_name.lower()
                if 'date' in col_name_lower and 'time' in col_name_lower:
                    col_type = 'datetime'
                elif 'date' in col_name_lower:
                    col_type = 'date'
                elif 'time' in col_name_lower:
                    col_type = 'time'
                elif any(x in col_name_lower for x in ['amount', 'total', 'balance', 'price', 'cost', 'revenue']):
                    col_type = 'amount'
                elif any(x in col_name_lower for x in ['id', '#', 'number']) and 'phone' not in col_name_lower:
                    col_type = 'id'
                elif 'reserve' in col_name_lower:
                    col_type = 'reserve_number'
                elif 'status' in col_name_lower:
                    col_type = 'status'
                elif 'phone' in col_name_lower:
                    col_type = 'phone'
                elif 'email' in col_name_lower:
                    col_type = 'email'
                elif 'name' in col_name_lower:
                    col_type = 'name'
                elif any(x in col_name_lower for x in ['description', 'notes', 'comment', 'message']):
                    col_type = 'description'
                elif 'vehicle' in col_name_lower:
                    col_type = 'vehicle'
                elif 'address' in col_name_lower:
                    col_type = 'address'
                elif 'city' in col_name_lower:
                    col_type = 'city'
            
            # Apply sizing
            if col_type in COLUMN_WIDTHS:
                width = COLUMN_WIDTHS[col_type]
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
                self.setColumnWidth(i, width)
            elif col_type in ['description', 'notes']:
                # Stretchy columns for long text
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                # Default: Interactive resize
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
                self.setColumnWidth(i, 150)
            
            self.column_configs[col_name] = col_type
    
    def set_column_stretch(self, column_index: int):
        """Make a specific column stretch to fill space"""
        header = self.horizontalHeader()
        header.setSectionResizeMode(column_index, QHeaderView.ResizeMode.Stretch)
    
    def set_column_resize_to_contents(self, column_index: int):
        """Make a column auto-size to contents"""
        header = self.horizontalHeader()
        header.setSectionResizeMode(column_index, QHeaderView.ResizeMode.ResizeToContents)


class FuzzySearchLineEdit(QLineEdit):
    """
    QLineEdit with fuzzy search/autocomplete functionality
    """
    
    search_triggered = pyqtSignal(str)
    
    def __init__(self, parent=None, suggestions: Optional[List[str]] = None):
        super().__init__(parent)
        self.suggestions = suggestions or []
        self.completer = None
        self._setup_fuzzy_search()
        
        # Trigger search on text change
        self.textChanged.connect(self._on_text_changed)
    
    def _setup_fuzzy_search(self):
        """Setup QCompleter for fuzzy matching"""
        if self.suggestions:
            self.completer = QCompleter(self.suggestions, self)
            self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
            self.setCompleter(self.completer)
    
    def update_suggestions(self, suggestions: List[str]):
        """Update autocomplete suggestions"""
        self.suggestions = suggestions
        self._setup_fuzzy_search()
    
    def _on_text_changed(self, text: str):
        """Emit search signal when text changes"""
        if len(text) >= 2:  # Only search after 2 characters
            self.search_triggered.emit(text)


class SmartFormField:
    """
    Factory for creating properly-sized form fields
    """
    
    @staticmethod
    def date_edit(parent=None) -> QDateEdit:
        """Create a date field with proper width"""
        from desktop_app.common_widgets import StandardDateEdit
        widget = StandardDateEdit(parent)
        widget.setFixedWidth(FIELD_WIDTHS['date'])
        widget.setCalendarPopup(True)
        return widget
    
    @staticmethod
    def time_edit(parent=None):
        """Create a time field with proper width"""
        from PyQt6.QtWidgets import QTimeEdit
        widget = QTimeEdit(parent)
        widget.setFixedWidth(FIELD_WIDTHS['time'])
        widget.setDisplayFormat("hh:mm AP")
        return widget
    
    @staticmethod
    def phone_field(parent=None) -> QLineEdit:
        """Create a phone field with proper width"""
        widget = QLineEdit(parent)
        widget.setFixedWidth(FIELD_WIDTHS['phone'])
        widget.setPlaceholderText("(403) 555-1234")
        widget.setMaxLength(20)
        return widget
    
    @staticmethod
    def email_field(parent=None) -> QLineEdit:
        """Create an email field with proper width"""
        widget = QLineEdit(parent)
        widget.setFixedWidth(FIELD_WIDTHS['email'])
        widget.setPlaceholderText("email@example.com")
        return widget
    
    @staticmethod
    def postal_code_field(parent=None) -> QLineEdit:
        """Create a postal code field"""
        widget = QLineEdit(parent)
        widget.setFixedWidth(FIELD_WIDTHS['postal_code'])
        widget.setPlaceholderText("T2P 1J9")
        widget.setMaxLength(7)
        return widget
    
    @staticmethod
    def amount_field(parent=None, min_val=0.0, max_val=999999.99) -> QDoubleSpinBox:
        """Create a currency field"""
        widget = QDoubleSpinBox(parent)
        widget.setFixedWidth(FIELD_WIDTHS['amount'])
        widget.setPrefix("$ ")
        widget.setRange(min_val, max_val)
        widget.setDecimals(2)
        return widget
    
    @staticmethod
    def short_text_field(parent=None, max_length=50) -> QLineEdit:
        """Create a short text field (e.g., name, title)"""
        widget = QLineEdit(parent)
        widget.setFixedWidth(FIELD_WIDTHS['short_text'])
        widget.setMaxLength(max_length)
        return widget
    
    @staticmethod
    def medium_text_field(parent=None, max_length=100) -> QLineEdit:
        """Create a medium text field"""
        widget = QLineEdit(parent)
        widget.setFixedWidth(FIELD_WIDTHS['medium_text'])
        widget.setMaxLength(max_length)
        return widget
    
    @staticmethod
    def long_text_field(parent=None, max_length=200) -> QLineEdit:
        """Create a long text field"""
        widget = QLineEdit(parent)
        widget.setFixedWidth(FIELD_WIDTHS['long_text'])
        widget.setMaxLength(max_length)
        return widget
    
    @staticmethod
    def auto_expanding_text(parent=None, max_height=300) -> QTextEdit:
        """
        Create an auto-expanding text area for long content
        (e.g., dispatch notes, email conversations)
        """
        widget = QTextEdit(parent)
        widget.setMinimumHeight(60)
        widget.setMaximumHeight(max_height)
        widget.setAcceptRichText(False)
        
        # Auto-expand as content grows
        def adjust_height():
            doc_height = widget.document().size().height()
            new_height = min(int(doc_height) + 10, max_height)
            widget.setFixedHeight(max(60, new_height))
        
        widget.textChanged.connect(adjust_height)
        return widget


class TabOrderManager:
    """
    Manages tab order for form widgets
    Excludes read-only tables and result windows
    """
    
    @staticmethod
    def set_tab_order(form_widget: QWidget, field_order: List[QWidget]):
        """
        Set tab order for a form
        
        Args:
            form_widget: The parent widget containing the form
            field_order: List of widgets in desired tab order
        """
        for i in range(len(field_order) - 1):
            current = field_order[i]
            next_widget = field_order[i + 1]
            
            # Skip read-only or disabled widgets
            if hasattr(current, 'isReadOnly') and current.isReadOnly():
                continue
            if not current.isEnabled():
                continue
            
            # Skip table widgets (query results)
            if isinstance(current, QTableWidget):
                continue
            
            form_widget.setTabOrder(current, next_widget)
    
    @staticmethod
    def make_widget_skip_tab(widget: QWidget):
        """Make a widget skip in tab order"""
        widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)


# ============================================================
# QUICK SETUP FUNCTIONS
# ============================================================

def setup_standard_table(table: QTableWidget, headers: List[str], 
                         column_types: Optional[Dict[str, str]] = None):
    """
    Quick setup for a standard table with smart sizing
    
    Usage:
        table = QTableWidget()
        setup_standard_table(table, 
            ["Date", "Reserve #", "Amount", "Status"],
            {"Date": "date", "Amount": "amount"}
        )
    """
    smart_table = SmartTableWidget()
    # Copy properties to existing table
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    
    header = table.horizontalHeader()
    
    for i, col_name in enumerate(headers):
        # Determine column type
        col_type = None
        if column_types and col_name in column_types:
            col_type = column_types[col_name]
        else:
            # Auto-detect
            col_name_lower = col_name.lower()
            if 'date' in col_name_lower and 'time' in col_name_lower:
                col_type = 'datetime'
            elif 'date' in col_name_lower:
                col_type = 'date'
            elif any(x in col_name_lower for x in ['amount', 'total', 'balance', 'price']):
                col_type = 'amount'
            elif any(x in col_name_lower for x in ['id', '#', 'number']) and 'phone' not in col_name_lower:
                col_type = 'id'
            elif 'reserve' in col_name_lower:
                col_type = 'reserve_number'
            elif 'status' in col_name_lower:
                col_type = 'status'
            elif 'phone' in col_name_lower:
                col_type = 'phone'
            elif 'email' in col_name_lower:
                col_type = 'email'
            elif 'name' in col_name_lower:
                col_type = 'name'
            elif any(x in col_name_lower for x in ['description', 'notes']):
                col_type = 'description'
        
        # Apply sizing
        if col_type in COLUMN_WIDTHS:
            width = COLUMN_WIDTHS[col_type]
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
            table.setColumnWidth(i, width)
        elif col_type in ['description', 'notes']:
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
        else:
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
            table.setColumnWidth(i, 150)


def enable_fuzzy_search(line_edit: QLineEdit, suggestions: List[str]):
    """
    Enable fuzzy search on an existing QLineEdit
    
    Usage:
        client_search = QLineEdit()
        enable_fuzzy_search(client_search, ["Client A", "Client B", ...])
    """
    completer = QCompleter(suggestions, line_edit)
    completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    completer.setFilterMode(Qt.MatchFlag.MatchContains)
    line_edit.setCompleter(completer)


def make_read_only_table(table: QTableWidget):
    """
    Configure a table as read-only (for query results)
    Also removes it from tab order
    """
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
