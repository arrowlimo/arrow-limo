"""
UI Standards and Helpers for Desktop Application
Provides consistent sizing, tab order, and fuzzy search functionality
"""


from PyQt6.QtCore import QEvent, QObject, QSettings, Qt, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QAbstractSpinBox,
    QCompleter,
    QDateEdit,
    QDoubleSpinBox,
    QHeaderView,
    QLineEdit,
    QMenu,
    QSpinBox,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QTimeEdit,
    QWidget,
)

# ============================================================
# STANDARD COLUMN WIDTHS (in pixels)
# ============================================================
COLUMN_WIDTHS = {
    # ID fields
    "id": 60,
    "reserve_number": 90,
    "receipt_id": 70,
    "payment_id": 70,
    "employee_id": 70,
    "client_id": 70,
    "vehicle_id": 70,
    # Date fields
    "date": 100,
    "datetime": 140,
    "time": 80,
    # Currency/Amount fields
    "amount": 110,
    "currency": 110,
    "balance": 110,
    "total": 110,
    # Status/Category fields
    "status": 90,
    "category": 100,
    "type": 100,
    # Name fields
    "name": 150,
    "employee_name": 150,
    "client_name": 150,
    "vendor_name": 180,
    # Phone/Email
    "phone": 120,
    "email": 200,
    # Vehicle fields
    "vehicle": 100,
    "plate": 90,
    # Location fields
    "city": 120,
    "address": 250,
    "location": 180,
    # Boolean/Checkbox
    "checkbox": 50,
    "boolean": 70,
    # Description/Notes (stretchy)
    "description": 300,
    "notes": 300,
}


# ============================================================
# STANDARD FORM FIELD WIDTHS
# ============================================================
FIELD_WIDTHS = {
    "id": 100,
    "date": 150,
    "time": 100,
    "phone": 150,
    "email": 250,
    "postal_code": 120,
    "amount": 150,
    "short_text": 200,
    "medium_text": 300,
    "long_text": 400,
}


class SmartTableWidget(QTableWidget):
    """
    Enhanced QTableWidget with smart column sizing and auto-configuration
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.column_configs = {}

    def setup_columns(
        self, headers: list[str], column_types: dict[str, str] | None = None
    ) -> None:
        """
        Setup columns with smart sizing based on data type

        Args:
            headers: List of column header names
            column_types: Dict mapping header name to type (date, amount, id,
            name, description, etc.)
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
                if "date" in col_name_lower and "time" in col_name_lower:
                    col_type = "datetime"
                elif "date" in col_name_lower:
                    col_type = "date"
                elif "time" in col_name_lower:
                    col_type = "time"
                elif any(
                    x in col_name_lower
                    for x in [
                        "amount",
                        "total",
                        "balance",
                        "price",
                        "cost",
                        "revenue",
                    ]
                ):
                    col_type = "amount"
                elif (
                    any(x in col_name_lower for x in ["id", "#", "number"])
                    and "phone" not in col_name_lower
                ):
                    col_type = "id"
                elif "reserve" in col_name_lower:
                    col_type = "reserve_number"
                elif "status" in col_name_lower:
                    col_type = "status"
                elif "phone" in col_name_lower:
                    col_type = "phone"
                elif "email" in col_name_lower:
                    col_type = "email"
                elif "name" in col_name_lower:
                    col_type = "name"
                elif any(
                    x in col_name_lower
                    for x in ["description", "notes", "comment", "message"]
                ):
                    col_type = "description"
                elif "vehicle" in col_name_lower:
                    col_type = "vehicle"
                elif "address" in col_name_lower:
                    col_type = "address"
                elif "city" in col_name_lower:
                    col_type = "city"

            # Apply sizing
            if col_type in COLUMN_WIDTHS:
                width = COLUMN_WIDTHS[col_type]
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
                self.setColumnWidth(i, width)
            elif col_type in ["description", "notes"]:
                # Stretchy columns for long text
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                # Default: Interactive resize
                header.setSectionResizeMode(
                    i, QHeaderView.ResizeMode.Interactive
                )
                self.setColumnWidth(i, 150)

            self.column_configs[col_name] = col_type

    def set_column_stretch(self, column_index: int) -> None:
        """Make a specific column stretch to fill space"""
        header = self.horizontalHeader()
        header.setSectionResizeMode(
            column_index, QHeaderView.ResizeMode.Stretch
        )

    def set_column_resize_to_contents(self, column_index: int) -> None:
        """Make a column auto-size to contents"""
        header = self.horizontalHeader()
        header.setSectionResizeMode(
            column_index, QHeaderView.ResizeMode.ResizeToContents
        )


class FuzzySearchLineEdit(QLineEdit):
    """
    QLineEdit with fuzzy search/autocomplete functionality
    """

    search_triggered = pyqtSignal(str)

    def __init__(self, parent=None, suggestions: list[str] | None = None) -> None:
        super().__init__(parent)
        self.suggestions = suggestions or []
        self.completer = None
        self._setup_fuzzy_search()

        # Trigger search on text change
        self.textChanged.connect(self._on_text_changed)

    def _setup_fuzzy_search(self) -> None:
        """Setup QCompleter for fuzzy matching"""
        if self.suggestions:
            self.completer = QCompleter(self.suggestions, self)
            self.completer.setCaseSensitivity(
                Qt.CaseSensitivity.CaseInsensitive
            )
            self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
            self.setCompleter(self.completer)

    def update_suggestions(self, suggestions: list[str]) -> None:
        """Update autocomplete suggestions"""
        self.suggestions = suggestions
        self._setup_fuzzy_search()

    def _on_text_changed(self, text: str) -> None:
        """Emit search signal when text changes"""
        if len(text) >= 2:  # Only search after 2 characters
            self.search_triggered.emit(text)


class CurrencySpinBox(QDoubleSpinBox):
    """
    QDoubleSpinBox optimized for currency entry.
    Auto-selects all text when focused so typing replaces the value.
    Example: Field shows "0.00", user types "19.87" and gets "19.87"
    (not "19870.00").
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setDecimals(2)
        self.setPrefix("$ ")
        self.setRange(0.0, 999999.99)
        self.setAlignment(Qt.AlignmentFlag.AlignRight)

    def focusInEvent(self, event) -> None:
        """Select all text when field gains focus"""
        super().focusInEvent(event)
        # Select all text so typing replaces instead of inserting
        self.selectAll()

    def mousePressEvent(self, event) -> None:
        """Select all text when clicked"""
        super().mousePressEvent(event)
        # Also select on mouse click for consistency
        self.selectAll()


class SmartFormField:
    """
    Factory for creating properly-sized form fields
    """

    @staticmethod
    def date_edit(parent=None) -> QDateEdit:
        """Create a date field with proper width"""
        from common_widgets import StandardDateEdit

        widget = StandardDateEdit(parent)
        widget.setFixedWidth(FIELD_WIDTHS["date"])
        widget.setCalendarPopup(True)
        return widget

    @staticmethod
    def time_edit(parent=None) -> object:
        """Create a time field with proper width"""
        from PyQt6.QtWidgets import QTimeEdit

        widget = QTimeEdit(parent)
        widget.setFixedWidth(FIELD_WIDTHS["time"])
        widget.setDisplayFormat("HH:mm")
        widget.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        widget.setReadOnly(False)
        return widget

    @staticmethod
    def phone_field(parent=None) -> QLineEdit:
        """Create a phone field with proper width"""
        widget = QLineEdit(parent)
        widget.setFixedWidth(FIELD_WIDTHS["phone"])
        widget.setPlaceholderText("(403) 555-1234")
        widget.setMaxLength(20)
        return widget

    @staticmethod
    def email_field(parent=None) -> QLineEdit:
        """Create an email field with proper width"""
        widget = QLineEdit(parent)
        widget.setFixedWidth(FIELD_WIDTHS["email"])
        widget.setPlaceholderText("email@example.com")
        return widget

    @staticmethod
    def postal_code_field(parent=None) -> QLineEdit:
        """Create a postal code field"""
        widget = QLineEdit(parent)
        widget.setFixedWidth(FIELD_WIDTHS["postal_code"])
        widget.setPlaceholderText("T2P 1J9")
        widget.setMaxLength(7)
        return widget

    @staticmethod
    def amount_field(
        parent=None, min_val=0.0, max_val=999999.99
    ) -> QDoubleSpinBox:
        """
        Create a currency field with auto-select-all behavior.
        When focused, all text is selected so typing replaces the value.
        """
        widget = CurrencySpinBox(parent)
        widget.setFixedWidth(FIELD_WIDTHS["amount"])
        widget.setRange(min_val, max_val)
        return widget

    @staticmethod
    def short_text_field(parent=None, max_length=50) -> QLineEdit:
        """Create a short text field (e.g., name, title)"""
        widget = QLineEdit(parent)
        widget.setFixedWidth(FIELD_WIDTHS["short_text"])
        widget.setMaxLength(max_length)
        return widget

    @staticmethod
    def medium_text_field(parent=None, max_length=100) -> QLineEdit:
        """Create a medium text field"""
        widget = QLineEdit(parent)
        widget.setFixedWidth(FIELD_WIDTHS["medium_text"])
        widget.setMaxLength(max_length)
        return widget

    @staticmethod
    def long_text_field(parent=None, max_length=200) -> QLineEdit:
        """Create a long text field"""
        widget = QLineEdit(parent)
        widget.setFixedWidth(FIELD_WIDTHS["long_text"])
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
        def adjust_height() -> None:
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
    def set_tab_order(form_widget: QWidget, field_order: list[QWidget]) -> None:
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
            if hasattr(current, "isReadOnly") and current.isReadOnly():
                continue
            if not current.isEnabled():
                continue

            # Skip table widgets (query results)
            if isinstance(current, QTableWidget):
                continue

            form_widget.setTabOrder(current, next_widget)

    @staticmethod
    def make_widget_skip_tab(widget: QWidget) -> None:
        """Make a widget skip in tab order"""
        widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)


# ============================================================
# QUICK SETUP FUNCTIONS
# ============================================================


def setup_standard_table(
    table: QTableWidget,
    headers: list[str],
    column_types: dict[str, str] | None = None,
) -> None:
    """
    Quick setup for a standard table with smart sizing

    Usage:
        table = QTableWidget()
        setup_standard_table(table,
            ["Date", "Reserve #", "Amount", "Status"],
            {"Date": "date", "Amount": "amount"})
    """
    SmartTableWidget()
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
            if "date" in col_name_lower and "time" in col_name_lower:
                col_type = "datetime"
            elif "date" in col_name_lower:
                col_type = "date"
            elif any(
                x in col_name_lower
                for x in ["amount", "total", "balance", "price"]
            ):
                col_type = "amount"
            elif (
                any(x in col_name_lower for x in ["id", "#", "number"])
                and "phone" not in col_name_lower
            ):
                col_type = "id"
            elif "reserve" in col_name_lower:
                col_type = "reserve_number"
            elif "status" in col_name_lower:
                col_type = "status"
            elif "phone" in col_name_lower:
                col_type = "phone"
            elif "email" in col_name_lower:
                col_type = "email"
            elif "name" in col_name_lower:
                col_type = "name"
            elif any(x in col_name_lower for x in ["description", "notes"]):
                col_type = "description"

        # Apply sizing
        if col_type in COLUMN_WIDTHS:
            width = COLUMN_WIDTHS[col_type]
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
            table.setColumnWidth(i, width)
        elif col_type in ["description", "notes"]:
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
        else:
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
            table.setColumnWidth(i, 150)


def enable_fuzzy_search(line_edit: QLineEdit, suggestions: list[str]) -> None:
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


def make_read_only_table(table: QTableWidget) -> None:
    """
    Configure a table as read-only (for query results)
    Also removes it from tab order
    """
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)


def enable_currency_auto_select(spinbox: QDoubleSpinBox) -> None:
    """
    Enable auto-select-all behavior on existing QDoubleSpinBox.
    When user clicks or tabs into the field, all text is selected
    so typing replaces instead of inserting at cursor.

    Fixes the annoying issue where typing "19.87" in a field
    showing "0.00" results in "19870.00" instead of "19.87".

    Usage:
        amount_field = QDoubleSpinBox()
        enable_currency_auto_select(amount_field)
    """

    # Store original event handlers
    original_focus_in = spinbox.focusInEvent
    original_mouse_press = spinbox.mousePressEvent

    def focus_in_handler(event) -> None:
        original_focus_in(event)
        spinbox.selectAll()

    def mouse_press_handler(event) -> None:
        original_mouse_press(event)
        spinbox.selectAll()

    # Replace event handlers
    spinbox.focusInEvent = focus_in_handler
    spinbox.mousePressEvent = mouse_press_handler


class _ReplaceAllFocusFilter(QObject):
    """Select-all-on-focus for single-line input widgets."""

    def eventFilter(self, obj, event) -> object:
        if event.type() in (QEvent.Type.FocusIn, QEvent.Type.MouseButtonPress):
            if isinstance(obj, (QLineEdit, QSpinBox, QDoubleSpinBox, QDateEdit, QTimeEdit)):
                if _is_notes_like_field(obj):
                    return False
                try:
                    obj.selectAll()
                except Exception:
                    pass
        return False


_replace_all_filter = _ReplaceAllFocusFilter()


def _is_notes_like_field(widget: QWidget) -> bool:
    """Keep notes/comment style fields editable normally (no replace-all)."""
    tokens = []
    try:
        tokens.append(widget.objectName().lower())
    except Exception:
        pass
    try:
        if hasattr(widget, "placeholderText"):
            tokens.append(widget.placeholderText().lower())
    except Exception:
        pass
    joined = " ".join(tokens)
    return any(k in joined for k in ("note", "comment", "remark", "message"))


def install_replace_all_behavior(root_widget: QWidget) -> None:
    """Install replace-all behavior on standard single-line fields in a widget tree."""
    if root_widget is None:
        return
    for child in root_widget.findChildren(QWidget):
        if isinstance(child, (QLineEdit, QSpinBox, QDoubleSpinBox, QDateEdit, QTimeEdit)):
            child.installEventFilter(_replace_all_filter)


class GridStandardsManager(QObject):
    """Apply consistent table behavior: scrollbars, sorting, adjustable columns,
    column visibility control, auto-saved layouts, reset, and simple undo.
    """

    def __init__(self, org_name: str = "ArrowLimo", app_name: str = "Desktop") -> None:
        super().__init__()
        self.settings = QSettings(org_name, app_name)

    def apply_to_widget(self, root_widget: QWidget) -> None:
        """Apply standards to all table widgets under root_widget."""
        if root_widget is None:
            return
        for table in root_widget.findChildren((QTableWidget, QTableView)):
            self._configure_table(table)

    def reset_layout_for_widget(self, focused_widget: QWidget) -> bool:
        table = self._find_parent_table(focused_widget)
        if table is None:
            return False
        self.reset_table_layout(table)
        return True

    def show_column_selector_for_widget(self, focused_widget: QWidget) -> bool:
        table = self._find_parent_table(focused_widget)
        if table is None:
            return False
        self._show_column_selector(table, table.mapFromGlobal(table.cursor().pos()))
        return True

    def undo_for_widget(self, focused_widget: QWidget) -> bool:
        table = self._find_parent_table(focused_widget)
        if table is None:
            return False
        if not isinstance(table, QTableWidget):
            return False
        stack = table.property("_layout_undo_stack") or []
        if not stack:
            return False
        row, col, old_text, new_text = stack.pop()
        table.setProperty("_layout_undo_stack", stack)
        item = table.item(row, col)
        if item is None:
            item = QTableWidgetItem("")
            table.setItem(row, col, item)
        table.blockSignals(True)
        item.setText(old_text)
        table.blockSignals(False)
        return True

    def reset_table_layout(self, table: QWidget) -> None:
        key = self._table_key(table)
        self.settings.remove(f"grid_layouts/{key}")
        self._apply_default_header_state(table)

    def _configure_table(self, table: QWidget) -> None:
        if table is None:
            return
        if table.property("_grid_standards_applied"):
            return

        table.setProperty("_grid_standards_applied", True)
        table.setProperty("_layout_undo_stack", [])

        # Scrollbars present as needed on both axes.
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Sorting and adjustable headers.
        if hasattr(table, "setSortingEnabled"):
            table.setSortingEnabled(True)

        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionsMovable(True)
        # Stretch the last column so grids fill the panel width instead of
        # leaving a blank gap to the right; columns stay interactive/movable.
        header.setStretchLastSection(True)
        header.setSortIndicatorShown(True)

        # Column chooser + reset layout from header context menu.
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.customContextMenuRequested.connect(
            lambda pos, t=table: self._show_column_selector(t, pos)
        )

        # Auto-save layout changes.
        header.sectionMoved.connect(lambda *_args, t=table: self._save_table_layout(t))
        header.sectionResized.connect(lambda *_args, t=table: self._save_table_layout(t))
        if hasattr(table, "sortByColumn"):
            header.sortIndicatorChanged.connect(lambda *_args, t=table: self._save_table_layout(t))

        # For editable QTableWidget: capture simple per-cell undo history.
        if isinstance(table, QTableWidget):
            table.itemPressed.connect(lambda item, t=table: self._capture_before_edit(t, item))
            table.itemChanged.connect(lambda item, t=table: self._record_after_edit(t, item))

        self._restore_table_layout(table)

    def _capture_before_edit(self, table: QTableWidget, item: QTableWidgetItem) -> None:
        if item is None:
            return
        table.setProperty("_layout_pending_edit", (item.row(), item.column(), item.text()))

    def _record_after_edit(self, table: QTableWidget, item: QTableWidgetItem) -> None:
        if item is None:
            return
        pending = table.property("_layout_pending_edit")
        if not pending:
            return
        prow, pcol, old_text = pending
        if prow != item.row() or pcol != item.column():
            return
        new_text = item.text()
        if old_text == new_text:
            return
        stack = table.property("_layout_undo_stack") or []
        stack.append((prow, pcol, old_text, new_text))
        if len(stack) > 200:
            stack = stack[-200:]
        table.setProperty("_layout_undo_stack", stack)
        table.setProperty("_layout_pending_edit", None)

    def _show_column_selector(self, table: QWidget, pos) -> None:
        header = table.horizontalHeader()
        menu = QMenu(header)

        title = QAction("Columns", menu)
        title.setEnabled(False)
        menu.addAction(title)

        for logical in range(header.count()):
            label = ""
            if hasattr(table, "horizontalHeaderItem"):
                item = table.horizontalHeaderItem(logical)
                label = item.text() if item else f"Column {logical + 1}"
            if not label:
                label = f"Column {logical + 1}"

            action = QAction(label, menu)
            action.setCheckable(True)
            action.setChecked(not header.isSectionHidden(logical))
            action.toggled.connect(
                lambda checked, c=logical, h=header, t=table: self._toggle_column(h, t, c, checked)
            )
            menu.addAction(action)

        menu.addSeparator()
        reset_action = QAction("Reset Layout", menu)
        reset_action.triggered.connect(lambda _=False, t=table: self.reset_table_layout(t))
        menu.addAction(reset_action)

        menu.exec(header.mapToGlobal(pos))

    def _toggle_column(self, header: QHeaderView, table: QWidget, col: int, visible: bool) -> None:
        header.setSectionHidden(col, not visible)
        self._save_table_layout(table)

    def _save_table_layout(self, table: QWidget) -> None:
        key = self._table_key(table)
        header = table.horizontalHeader()
        self.settings.setValue(f"grid_layouts/{key}/header_state", header.saveState())
        self.settings.setValue(f"grid_layouts/{key}/sort_col", header.sortIndicatorSection())
        # Qt enum wrappers differ across bindings/versions; normalize to int.
        order_value = self._sort_order_to_int(header.sortIndicatorOrder())
        self.settings.setValue(
            f"grid_layouts/{key}/sort_order", order_value
        )

    def _restore_table_layout(self, table: QWidget) -> None:
        key = self._table_key(table)
        header = table.horizontalHeader()
        state = self.settings.value(f"grid_layouts/{key}/header_state")
        if state:
            try:
                header.restoreState(state)
            except Exception:
                pass
        sort_col = self.settings.value(f"grid_layouts/{key}/sort_col")
        sort_order = self.settings.value(f"grid_layouts/{key}/sort_order")
        if sort_col is not None and sort_order is not None and hasattr(table, "sortByColumn"):
            try:
                table.sortByColumn(
                    int(sort_col), self._coerce_sort_order(sort_order)
                )
            except Exception:
                pass

    def _sort_order_to_int(self, order) -> int:
        """Convert a Qt sort order enum/value to a stable persisted integer."""
        # PyQt6 enums expose `.value`; older wrappers may already be int-like.
        raw = getattr(order, "value", order)
        try:
            return int(raw)
        except Exception:
            # Safe default to ascending when value is unexpected.
            return int(Qt.SortOrder.AscendingOrder.value)

    def _coerce_sort_order(self, stored_order) -> Qt.SortOrder:
        """Convert persisted sort order (int/str/enum) back to Qt.SortOrder."""
        raw = getattr(stored_order, "value", stored_order)
        try:
            order_int = int(raw)
            return Qt.SortOrder(order_int)
        except Exception:
            pass

        text = str(raw).strip().lower()
        if "desc" in text:
            return Qt.SortOrder.DescendingOrder
        return Qt.SortOrder.AscendingOrder

    def _apply_default_header_state(self, table: QWidget) -> None:
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        for logical in range(header.count()):
            header.setSectionHidden(logical, False)

    def _find_parent_table(self, widget: QWidget) -> object:
        cur = widget
        while cur is not None:
            if isinstance(cur, (QTableWidget, QTableView)):
                return cur
            cur = cur.parentWidget()
        return None

    def _table_key(self, table: QWidget) -> str:
        name = table.objectName() or ""
        if not name:
            name = f"{table.__class__.__name__}_{id(table)}"
            table.setObjectName(name)
        return name
