"""
Vendor Lookup Widget with Fuzzy Search and Add New Vendor functionality.
"""

import logging
from difflib import SequenceMatcher

import psycopg2
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QWidget,
)

logger = logging.getLogger(__name__)


class AddVendorDialog(QDialog):
    """Dialog to add a new vendor to the master list."""

    def __init__(self, vendor_name: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add New Vendor")
        self.setModal(True)
        self.setMinimumWidth(400)

        layout = QFormLayout(self)

        self.vendor_name_edit = QLineEdit()
        self.vendor_name_edit.setText(vendor_name)
        layout.addRow("Vendor Name:", self.vendor_name_edit)

        self.category_edit = QLineEdit()
        layout.addRow("Category (Optional):", self.category_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_vendor_data(self) -> object:
        """Return vendor name and category."""
        return {
            "vendor_name": self.vendor_name_edit.text().strip().upper(),
            "category": self.category_edit.text().strip() or None,
        }


class VendorLookupWidget(QWidget):
    """
    Vendor lookup widget with fuzzy search and add new vendor functionality.
    Replaces simple QLineEdit for vendor names.
    Emits GL code suggestions when vendor is selected.
    """

    vendorChanged = pyqtSignal(str)  # Emitted when vendor selection changes
    glCodesChanged = pyqtSignal(
        list
    )  # Emitted with list of (gl_code, gl_name, priority) tuples

    def __init__(self, conn: psycopg2.extensions.connection, parent=None) -> None:
        super().__init__(parent)
        self.conn = conn
        self.vendors = []  # List of (vendor_id, vendor_name, category)
        self.current_vendor_id = None  # Track current vendor ID for GL lookups

        # Debounce timer — wait 500 ms after last keystroke before filtering,
        # so the popup doesn't steal focus while the user is still typing.
        from PyQt6.QtCore import QTimer

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(500)
        self._search_timer.timeout.connect(self._run_fuzzy_search)
        self._pending_search_text = ""

        self._build_ui()
        self._load_vendors()

    def _build_ui(self) -> None:
        """Build the widget UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Vendor dropdown with autocomplete
        self.vendor_combo = QComboBox()
        self.vendor_combo.setEditable(True)
        self.vendor_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.vendor_combo.setMaxVisibleItems(15)
        self.vendor_combo.setStyleSheet("""
            QComboBox {
                min-height: 24px;
                padding: 2px 5px;
            }
            QComboBox::drop-down {
                width: 20px;
            }
        """)

        # Enable fuzzy search on text change
        self.vendor_combo.lineEdit().textEdited.connect(self._on_text_changed)
        self.vendor_combo.currentTextChanged.connect(self._on_vendor_selected)

        # Add vendor button
        self.add_vendor_btn = QPushButton("+ Add")
        self.add_vendor_btn.setMaximumWidth(60)
        self.add_vendor_btn.setToolTip("Add new vendor to master list")
        self.add_vendor_btn.clicked.connect(self._add_new_vendor)

        # Refresh button
        self.refresh_btn = QPushButton("↻")
        self.refresh_btn.setMaximumWidth(30)
        self.refresh_btn.setToolTip("Refresh vendor list")
        self.refresh_btn.clicked.connect(self._load_vendors)

        layout.addWidget(self.vendor_combo, stretch=1)
        layout.addWidget(self.add_vendor_btn)
        layout.addWidget(self.refresh_btn)

    def _load_vendors(self) -> None:
        """Load vendors from database."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT account_id, display_name, default_category
                    FROM vendor_accounts
                    WHERE status = 'active' OR status IS NULL
                    ORDER BY display_name
                """)
                self.vendors = cur.fetchall()

            # Populate combo box
            current_text = self.vendor_combo.currentText()
            self.vendor_combo.clear()

            for vendor_id, vendor_name, category in self.vendors:
                display_text = vendor_name
                if category:
                    display_text = f"{vendor_name} ({category})"
                self.vendor_combo.addItem(display_text, vendor_id)

            # Restore selection if possible
            if current_text:
                index = self.vendor_combo.findText(
                    current_text, Qt.MatchFlag.MatchContains
                )
                if index >= 0:
                    self.vendor_combo.setCurrentIndex(index)

        except Exception as e:
            try:
                self.conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            QMessageBox.warning(self, "Error", f"Failed to load vendors: {e}")

    def _fuzzy_match_score(self, s1: str, s2: str) -> float:
        """Calculate fuzzy match score between two strings (0-1)."""
        return SequenceMatcher(None, s1.upper(), s2.upper()).ratio()

    def _on_text_changed(self, text: str) -> None:
        """Handle text change — debounced so popup waits until typing"
        "pauses."""

        if not text:
            self._search_timer.stop()
            self._load_vendors()
            return
        # Require at least 2 chars before even starting the timer
        if len(text) < 2:
            return
        self._pending_search_text = text
        self._search_timer.start()  # restarts the 500 ms countdown

    def _run_fuzzy_search(self) -> None:
        """Actually perform the fuzzy filter — called after debounce delay."""
        text = self._pending_search_text
        if not text or len(text) < 2:
            return

        # Find fuzzy matches
        text_upper = text.upper()
        matches = []

        for vendor_id, vendor_name, category in self.vendors:
            # Exact match
            if text_upper in vendor_name:
                score = 1.0 + (
                    1.0 if vendor_name.startswith(text_upper) else 0.0
                )
                matches.append((score, vendor_id, vendor_name, category))
            # Fuzzy match
            else:
                score = self._fuzzy_match_score(text, vendor_name)
                if score > 0.6:  # Threshold for fuzzy matching
                    matches.append((score, vendor_id, vendor_name, category))

        # Sort by score descending
        matches.sort(reverse=True, key=lambda x: x[0])

        # Update combo box with top matches
        if matches:
            current_text = self.vendor_combo.currentText()
            self.vendor_combo.clear()

            for score, vendor_id, vendor_name, category in matches[
                :50
            ]:  # Top 50 matches
                display_text = vendor_name
                if category:
                    display_text = f"{vendor_name} ({category})"
                self.vendor_combo.addItem(display_text, vendor_id)

            # Set the text back (triggers dropdown)
            self.vendor_combo.lineEdit().setText(current_text)
            self.vendor_combo.showPopup()

    def _get_vendor_gl_codes(self, vendor_id: int) -> object:
        """Get GL code suggestions for a vendor."""
        if not vendor_id:
            return []

        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT vgl.gl_account_code, coa.account_name, vgl.priority
                FROM vendor_gl_codes vgl
                JOIN chart_of_accounts coa ON vgl.gl_account_code =
                coa.account_code
                WHERE vgl.vendor_id = %s
                ORDER BY vgl.priority, coa.account_name
            """,
                (vendor_id,),
            )

            gl_codes = cur.fetchall()
            cur.close()
            return gl_codes
        except Exception as e:
            logger.warning(
                "Error loading GL codes for vendor %s: %s",
                vendor_id,
                e,
            )
            try:
                self.conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            return []

    def _on_vendor_selected(self, text: str) -> None:
        """Handle vendor selection."""
        # Extract vendor name (remove category part)
        vendor_name = text.split(" (")[0] if " (" in text else text

        # Get vendor ID from current selection
        vendor_id = self.vendor_combo.currentData()
        self.current_vendor_id = vendor_id

        # Emit vendor changed signal
        self.vendorChanged.emit(vendor_name)

        # Emit GL codes changed signal
        if vendor_id:
            gl_codes = self._get_vendor_gl_codes(vendor_id)
            self.glCodesChanged.emit(gl_codes)
        else:
            self.glCodesChanged.emit([])

    def _add_new_vendor(self) -> None:
        """Add a new vendor to the master list."""
        current_text = self.vendor_combo.currentText().strip()

        # Extract vendor name if it has category
        if " (" in current_text:
            current_text = current_text.split(" (")[0]

        dialog = AddVendorDialog(current_text, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            vendor_data = dialog.get_vendor_data()

            if not vendor_data["vendor_name"]:
                QMessageBox.warning(self, "Error", "Vendor name is required")
                return

            try:
                with self.conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO vendor_accounts (canonical_vendor,
                        display_name, default_category, status)
                        VALUES (%s, %s, %s, 'active')
                        ON CONFLICT DO NOTHING
                        RETURNING account_id
                    """,
                        (
                            vendor_data["vendor_name"],
                            vendor_data["vendor_name"],
                            vendor_data["category"],
                        ),
                    )

                    result = cur.fetchone()
                    if result:
                        self.conn.commit()
                        QMessageBox.information(
                            self,
                            "Success",
                            f"Vendor '{vendor_data['vendor_name']}' added to"
                            f"master list",
                        )
                        self._load_vendors()
                        # Select the newly added vendor
                        self.set_vendor(vendor_data["vendor_name"])
                    else:
                        QMessageBox.warning(
                            self,
                            "Info",
                            f"Vendor '{vendor_data['vendor_name']}' already"
                            f"exists",
                        )
                        self.set_vendor(vendor_data["vendor_name"])

            except Exception as e:
                self.conn.rollback()
                QMessageBox.critical(
                    self, "Error", f"Failed to add vendor: {e}"
                )

    def get_vendor(self) -> str:
        """Get the current vendor name (without category)."""
        text = self.vendor_combo.currentText().strip()
        # Remove category part if present
        return text.split(" (")[0] if " (" in text else text

    def setCompleter(self, completer) -> None:
        """Pass-through so callers can attach a QCompleter to the inner"
        "combo's line edit."""

        if completer is None:
            if self.vendor_combo.lineEdit():
                self.vendor_combo.lineEdit().setCompleter(None)
        else:
            if self.vendor_combo.lineEdit():
                self.vendor_combo.lineEdit().setCompleter(completer)

    def set_vendor(self, vendor_name: str) -> None:
        """Set the current vendor by name."""
        if not vendor_name:
            self.vendor_combo.setCurrentIndex(-1)
            return

        # Find exact match first
        for i in range(self.vendor_combo.count()):
            item_text = self.vendor_combo.itemText(i)
            item_vendor = (
                item_text.split(" (")[0] if " (" in item_text else item_text
            )
            if item_vendor.upper() == vendor_name.upper():
                self.vendor_combo.setCurrentIndex(i)
                return

        # No match found, set the text directly
        self.vendor_combo.setCurrentText(vendor_name)

    def clear(self) -> None:
        """Clear the vendor selection."""
        self.vendor_combo.hidePopup()
        self.vendor_combo.setCurrentIndex(-1)
        self.vendor_combo.clearEditText()
        self._load_vendors()  # Restore full vendor list after filtering

    def get_gl_codes(self) -> object:
        """
        Get GL code suggestions for the current vendor.
        Returns list of (gl_code, gl_name, priority) tuples,
        ordered by priority.
        """
        if self.current_vendor_id:
            return self._get_vendor_gl_codes(self.current_vendor_id)
        return []
