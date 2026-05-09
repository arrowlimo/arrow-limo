"""
Charter Form Widget - Main charter/booking form

This module provides the comprehensive charter management interface including:
- Customer information with auto-fill search
- Itinerary/routing (line-by-line pickup/dropoff)
- Vehicle & driver assignment
- Invoicing & charges (with GST calculation)
- Notes & special instructions
- Status tracking
- Print/export capabilities

BUSINESS RULES:
- reserve_number is read-only (auto-generated)
- GST is calculated as tax-included
- All changes must be committed to database
"""

import os
import json
import logging
import smtplib
import ssl
import psycopg2
from datetime import datetime
from email.message import EmailMessage
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional

from PyQt6.QtCore import QDate, QDateTime, QEvent, Qt, QTime, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QKeySequence
from PyQt6.QtPrintSupport import QPrintDialog, QPrinter
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFileDialog, QFormLayout, QFrame, QGroupBox, QHBoxLayout,
    QHeaderView, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QRadioButton, QScrollArea, QSizePolicy,
    QSpinBox, QTableWidget, QTableWidgetItem, QTabWidget, QTextEdit,
    QTimeEdit, QVBoxLayout, QWidget
)

from db_connection import DatabaseConnection
from beverage_ordering import BeverageSelectionDialog
from enhanced_charter_widget import EnhancedCharterListWidget
from gst_calculator import GSTCalculator


current_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(current_dir, os.pardir))
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Spell-check syntax highlighter (requires pyspellchecker)
# ---------------------------------------------------------------------------
try:
    from spellchecker import SpellChecker as _SpellChecker
    _spell = _SpellChecker()
    _SPELLCHECK_AVAILABLE = True
except Exception:
    _spell = None
    _SPELLCHECK_AVAILABLE = False


class SpellCheckHighlighter(
        __import__('PyQt6.QtGui', fromlist=['QSyntaxHighlighter'])
        .QSyntaxHighlighter):
    """Underlines misspelled words in red in any QTextDocument."""

    def __init__(self, document):
        from PyQt6.QtGui import QSyntaxHighlighter
        super().__init__(document)
        self._fmt = __import__(
            'PyQt6.QtGui', fromlist=['QTextCharFormat', 'QColor']
        ).QTextCharFormat()
        from PyQt6.QtGui import QTextCharFormat, QColor
        self._fmt = QTextCharFormat()
        self._fmt.setUnderlineStyle(
            QTextCharFormat.UnderlineStyle.SpellCheckUnderline)
        self._fmt.setUnderlineColor(QColor("red"))

    def highlightBlock(self, text):
        if not _SPELLCHECK_AVAILABLE or _spell is None:
            return
        import re
        for m in re.finditer(r"[A-Za-z']+", text):
            word = m.group()
            if word.lower() in ("i",):
                continue
            if _spell.unknown([word]):
                self.setFormat(m.start(), len(word), self._fmt)


def _attach_spellcheck(text_edit):
    """Attach SpellCheckHighlighter to a QTextEdit if spell check is available."""
    if _SPELLCHECK_AVAILABLE:
        SpellCheckHighlighter(text_edit.document())


class CharterFormWidget(QWidget):
    """
    Main charter/booking form with grouped sections:
    - Customer Information (with auto-fill search)
    - Itinerary/Routing (line-by-line pickup/dropoff)
    - Vehicle & Driver Assignment
    - Invoicing & Charges (with GST calculation)
    - Notes & Special Instructions
    - Status tracking

    BUSINESS RULES:
    - reserve_number is read-only (auto-generated)
    - GST is calculated as tax-included
    - All changes must be committed to database
    """

    # Signal emitted when charter is saved (charter_id)
    saved = pyqtSignal(int)

    def __init__(
            self,
            db: DatabaseConnection,
            charter_id: Optional[int] = None,
            client_id: Optional[int] = None):
        super().__init__()
        self.db = db
        self.charter_id = charter_id
        self.client_id = client_id  # Pre-fill client if provided
        self.charges_data = []  # Track charges for proper calculation
        self.beverage_cart_data = {}  # Store beverage cart data
        self.beverage_cart_total = 0.0  # Store beverage total for invoice
        self.init_ui()
        if hasattr(self, "customer_widget") and not charter_id:
            self.customer_widget.enter_edit_mode()
        if charter_id:
            self.load_charter(charter_id)
        elif client_id:
            # Pre-fill client info if creating new charter with selected client
            self.load_client(client_id)

    def init_ui(self):
        """Initialize UI layout"""
        layout = QVBoxLayout()

        # ===== QUICK CHARTER LOOKUP (NEW) =====
        from quick_charter_lookup_widget import QuickCharterLookupWidget
        self.quick_lookup = QuickCharterLookupWidget(self.db, self)
        layout.addWidget(self.quick_lookup)

        # ===== HEADER WITH ACTION BUTTONS =====
        header_layout = QHBoxLayout()
        self.form_title_label = QLabel("<h2>Charter/Booking Form</h2>")
        header_layout.addWidget(self.form_title_label)

        self.active_charter_label = QLabel("No charter selected")
        self.active_charter_label.setStyleSheet(
            "color: #555; font-weight: 600;")
        header_layout.addWidget(self.active_charter_label)

        header_layout.addStretch()

        self.save_btn = QPushButton("💾 Save (Ctrl+S)")
        self.save_btn.clicked.connect(self.save_charter)
        self.save_btn.setShortcut(QKeySequence("Ctrl+S"))

        self.new_btn = QPushButton("➕ New Charter (Ctrl+N)")
        self.new_btn.clicked.connect(self.new_charter)
        self.new_btn.setShortcut(QKeySequence("Ctrl+N"))

        self.update_calendar_btn = QPushButton("🔄 Update Arrow Calendar")
        self.update_calendar_btn.clicked.connect(self.sync_charter_to_calendar)

        self.print_btn = QPushButton("🖨️ Print Confirmation Letter (Ctrl+P)")
        self.print_btn.clicked.connect(self.print_confirmation)
        self.print_btn.setShortcut(QKeySequence("Ctrl+P"))

        self.send_quote_btn = QPushButton("💰 Send Quote (Ctrl+Q)")
        self.send_quote_btn.clicked.connect(self.print_quote)
        self.send_quote_btn.setShortcut(QKeySequence("Ctrl+Q"))

        self.print_invoice_btn = QPushButton("📄 Print Single Invoice")
        self.print_invoice_btn.clicked.connect(self.print_invoice)

        # Run Sheet PDF buttons
        self.print_run_sheet_btn = QPushButton("🗒️ Print Run Charter PDF")
        self.print_run_sheet_btn.clicked.connect(self.print_run_sheet)

        self.print_blank_sheet_btn = QPushButton("🗒️ Blank Run Sheet")
        self.print_blank_sheet_btn.clicked.connect(self.print_blank_run_sheet)

        # Beverage print buttons
        self.print_dispatch_btn = QPushButton("🍷 Print Dispatch Order")
        self.print_dispatch_btn.clicked.connect(
            self.print_beverage_dispatch_order)

        self.print_guest_invoice_btn = QPushButton("🍷 Print Guest Invoice")
        self.print_guest_invoice_btn.clicked.connect(
            self.print_beverage_guest_invoice)

        self.print_driver_sheet_btn = QPushButton("🍷 Print Driver Sheet")
        self.print_driver_sheet_btn.clicked.connect(
            self.print_beverage_driver_sheet)

        self.print_client_beverage_list_btn = QPushButton(
            "🛒 Print Client Beverage List")
        self.print_client_beverage_list_btn.clicked.connect(
            self.print_client_beverage_list)

        self.print_driver_manifest_btn = QPushButton("📋 Print Driver Manifest")
        self.print_driver_manifest_btn.clicked.connect(
            self.print_driver_manifest)

        # Consolidated print/email action menu (desktop app)
        self.print_actions_combo = QComboBox()
        self.print_actions_combo.setMinimumWidth(250)
        self.print_actions_combo.addItems(
            [
                "🖨️ Print / Email...",
                "📋 Confirmation Letter",
                "📄 Print Single Invoice",
                "📚 Print Multi Invoice",
                "🗒️ Print Run Charter PDF (Form)",
                "🗒️ Print Blank Run Charter PDF",
                "🍷 Print Dispatch Order",
                "🍷 Print Guest Invoice",
                "🍷 Print Driver Sheet",
                "🛒 Print Client Beverage List",
                "📋 Print Driver Manifest",
                "✈️ Airport Sign",
            ]
        )
        self.print_actions_combo.activated.connect(
            self._handle_print_action_menu
        )

        self.airport_sign_btn = QPushButton("✈️ Airport Sign")
        self.airport_sign_btn.clicked.connect(self.generate_airport_sign)

        # Control buttons
        self.lock_btn = QPushButton("🔒 Lock")
        self.lock_btn.setCheckable(True)
        self.lock_btn.clicked.connect(self.toggle_lock)

        self.cancel_btn = QPushButton("❌ Cancel")
        self.cancel_btn.clicked.connect(self.cancel_charter)

        self.close_btn = QPushButton("✖ Close")
        self.close_btn.clicked.connect(self.close_charter_form)

        header_layout.addWidget(self.save_btn)
        header_layout.addWidget(self.new_btn)
        header_layout.addWidget(self.update_calendar_btn)
        header_layout.addWidget(self.send_quote_btn)
        header_layout.addWidget(self.print_actions_combo)
        layout.addLayout(header_layout)

        # ===== SCROLLABLE FORM AREA =====
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        form_container = QWidget()
        form_layout = QVBoxLayout()

        # ===== GROUP 1: CUSTOMER INFORMATION (IMPROVED) =====
        from improved_customer_widget import ImprovedCustomerWidget
        self.customer_widget = ImprovedCustomerWidget(self.db, self)
        self.customer_widget.changed.connect(self.on_form_changed)
        self.customer_widget.saved.connect(self.on_customer_saved)
        form_layout.addWidget(self.customer_widget)

        # ===== GROUP 2: CHARTER DETAILS (STATUS + DATES + VEHICLE/DRIVER + ITI
        charter_details_group = self.create_charter_details_section(
            lock_btn=self.lock_btn,
            cancel_btn=self.cancel_btn,
            close_btn=self.close_btn)
        form_layout.addWidget(charter_details_group)

        # ===== GROUP 3: ITINERARY/ROUTING =====
        itinerary_group = self.create_itinerary_section()
        form_layout.addWidget(itinerary_group)

        # ===== GROUP 4: CHARGES/INVOICING & BEVERAGES =====
        charges_group = self.create_charges_section()
        form_layout.addWidget(charges_group)

        # ===== GROUP 5: DISPATCH SECTION =====
        dispatch_group = self.create_dispatch_section()
        if dispatch_group.title():  # Only add if it has content
            form_layout.addWidget(dispatch_group)

        # ===== GROUP 6: NOTES =====
        notes_group = self.create_notes_section()
        form_layout.addWidget(notes_group)

        form_container.setLayout(form_layout)
        scroll.setWidget(form_container)

        # ===== CREATE BOOKING SUB-TABS: CHARTER LOOKUP + RUN CHARTER + DRIVER
        booking_tab_widget = QTabWidget()
        self.booking_tab_widget = booking_tab_widget  # Store reference

        # Tab 1: Run Charter (default first)
        booking_tab_widget.addTab(scroll, "📋 Run Charter")

        # Tab 2: Charter Lookup (Browse all charters)
        charter_lookup_tab = QWidget()
        charter_lookup_layout = QVBoxLayout()
        self.enhanced_charter_widget = EnhancedCharterListWidget(self.db)
        self.enhanced_charter_widget.print_run_sheet_signal.connect(
            self._handle_lookup_print_run_sheet
        )
        charter_lookup_layout.addWidget(self.enhanced_charter_widget)
        charter_lookup_tab.setLayout(charter_lookup_layout)
        booking_tab_widget.addTab(charter_lookup_tab, "🔍 Charter Lookup")

        # Tab 3: Driver & Vehicle Operations
        driver_vehicle_tab = self.create_driver_vehicle_ops_tab()
        booking_tab_widget.addTab(
            driver_vehicle_tab,
            "👨‍✈️ Driver & Vehicle Ops")

        # Set Run Charter as default tab
        booking_tab_widget.setCurrentIndex(0)

        # Add the booking tabs to the main layout
        layout.addWidget(booking_tab_widget)

        # Set the layout on the main widget
        self.setLayout(layout)
        self._install_enter_tab_filters()

    def _handle_print_action_menu(self, index):
        """Dispatch selected print action from header dropdown menu."""
        actions = {
            1: self.print_confirmation,
            2: self.print_single_invoice,
            3: self.open_multi_invoice_selection_dialog,
            4: self.print_run_sheet,
            5: self.print_blank_run_sheet,
            6: self.print_beverage_dispatch_order,
            7: self.print_beverage_guest_invoice,
            8: self.print_beverage_driver_sheet,
            9: self.print_client_beverage_list,
            10: self.print_driver_manifest,
            11: self.generate_airport_sign,
        }
        action = actions.get(index)
        try:
            if action:
                action()
        finally:
            # Reset prompt item after each selection.
            self.print_actions_combo.setCurrentIndex(0)

    def _install_enter_tab_filters(self):
        """Install this widget as an event filter on
        itself and all child widgets."""
        self.installEventFilter(self)
        for widget in self.findChildren(QWidget):
            widget.installEventFilter(self)

    def _mark_invoice_sent_today(self):
        """Quick-toggle invoice sent with today's date."""
        if hasattr(self, "invoice_sent_checkbox"):
            self.invoice_sent_checkbox.setChecked(True)
        if hasattr(self, "invoice_sent_date"):
            self.invoice_sent_date.setDate(QDate.currentDate())

    @staticmethod
    def _extract_internal_delivery_markers(notes_text: str):
        """Return cleaned notes and marker dictionary from system-tagged lines."""
        markers = {}
        clean_lines = []
        for raw_line in (notes_text or "").splitlines():
            line = raw_line.strip()
            if line.startswith("##SYS:") and "=" in line:
                key, value = line[6:].split("=", 1)
                markers[key.strip().upper()] = value.strip()
            else:
                clean_lines.append(raw_line)
        clean_notes = "\n".join(clean_lines).strip()
        return clean_notes, markers

    def _apply_internal_delivery_markers(self, notes_text: str):
        """Embed charter/invoice sent metadata into notes text."""
        clean_notes, markers = self._extract_internal_delivery_markers(notes_text)

        if hasattr(self, "charter_sent_checkbox") and self.charter_sent_checkbox.isChecked():
            markers["CHARTER_SENT"] = self.charter_sent_date.date().toString("yyyy-MM-dd")
        else:
            markers.pop("CHARTER_SENT", None)

        if hasattr(self, "invoice_sent_checkbox") and self.invoice_sent_checkbox.isChecked():
            markers["INVOICE_SENT"] = self.invoice_sent_date.date().toString("yyyy-MM-dd")
        else:
            markers.pop("INVOICE_SENT", None)

        marker_lines = [f"##SYS:{k}={v}" for k, v in sorted(markers.items())]
        if clean_notes and marker_lines:
            return f"{clean_notes}\n" + "\n".join(marker_lines)
        if marker_lines:
            return "\n".join(marker_lines)
        return clean_notes

    def _load_delivery_markers_into_ui(self, notes_text: str):
        """Load delivery tracking UI from notes markers and return cleaned notes."""
        clean_notes, markers = self._extract_internal_delivery_markers(notes_text or "")

        inv_date = markers.get("INVOICE_SENT")
        if hasattr(self, "invoice_sent_checkbox"):
            self.invoice_sent_checkbox.setChecked(bool(inv_date))
        if inv_date and hasattr(self, "invoice_sent_date"):
            qd = QDate.fromString(inv_date, "yyyy-MM-dd")
            if qd.isValid():
                self.invoice_sent_date.setDate(qd)

        ch_date = markers.get("CHARTER_SENT")
        if hasattr(self, "charter_sent_checkbox"):
            self.charter_sent_checkbox.setChecked(bool(ch_date))
        if ch_date and hasattr(self, "charter_sent_date"):
            qd = QDate.fromString(ch_date, "yyyy-MM-dd")
            if qd.isValid():
                self.charter_sent_date.setDate(qd)

        return clean_notes

    def eventFilter(self, obj, event):
        """Handle Enter key as Tab except in QTextEdit fields"""
        from PyQt6.QtGui import QKeyEvent

        if event.type() == QEvent.Type.Wheel:
            if (
                getattr(obj, 'property', None)
                and obj.property('routing_control')
                and not getattr(self, '_routing_edit_enabled', False)
            ):
                return True

        if event.type() == QEvent.Type.KeyPress:
            if isinstance(event, QKeyEvent):
                if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    # Check if we're in a QTextEdit or QPlainTextEdit (allow
                    # Enter in notes)
                    widget = self.focusWidget()
                    if widget:
                        # Preserve normal button activation behavior.
                        if isinstance(widget, QPushButton):
                            return super().eventFilter(obj, event)

                        # If a combo popup is open, Enter should
                        # select the popup item.
                        if (isinstance(widget, QComboBox)
                                and widget.view().isVisible()):
                            return super().eventFilter(obj, event)

                        if isinstance(widget, (QTextEdit,)):
                            # Allow normal Enter in text edit fields (for
                            # newlines)
                            return False
                        else:
                            # Convert Enter to Tab for other field types
                            self.focusNextChild()
                            return True
        return super().eventFilter(obj, event)

    def create_itinerary_section(self) -> QGroupBox:
        """Itinerary section with parent (Pickup/Dropoff)
        and stops (1a, 1b, 1c...)"""
        itinerary_group = QGroupBox("Itinerary")
        itinerary_layout = QVBoxLayout()

        # Route/Event table with billing documentation
        routing_header = QHBoxLayout()

        # Pickup outside Red Deer button + Add Route Event
        self.out_of_town_checkbox = QCheckBox("Pickup outside Red Deer")
        self.out_of_town_checkbox.setStyleSheet(
            "QCheckBox { font-weight: bold;}")
        self.out_of_town_checkbox.toggled.connect(
            self.handle_out_of_town_routing)
        routing_header.addWidget(self.out_of_town_checkbox)

        routing_header.addSpacing(10)

        self.routing_edit_btn = QPushButton("✏️ Edit Routing")
        self.routing_edit_btn.setCheckable(True)
        self.routing_edit_btn.clicked.connect(self.toggle_routing_edit_mode)
        routing_header.addWidget(self.routing_edit_btn)

        self.add_route_btn = QPushButton("➕ Add Stop")
        self.add_route_btn.clicked.connect(lambda: self.add_route_line())
        routing_header.addWidget(self.add_route_btn)

        # Move Up/Down buttons for reordering stops (not parents)
        self.move_up_btn = QPushButton("⬆️ Up")
        self.move_up_btn.clicked.connect(self.move_route_line_up)
        routing_header.addWidget(self.move_up_btn)

        self.move_down_btn = QPushButton("⬇️ Down")
        self.move_down_btn.clicked.connect(self.move_route_line_down)
        routing_header.addWidget(self.move_down_btn)

        # Delete Selected button
        self.delete_selected_btn = QPushButton("❌ Delete Selected")
        self.delete_selected_btn.clicked.connect(self.delete_selected_route_line)
        routing_header.addWidget(self.delete_selected_btn)

        routing_header.addStretch()
        itinerary_layout.addLayout(routing_header)

        self.route_table = QTableWidget()
        self.route_table.setColumnCount(5)
        self.route_table.setHorizontalHeaderLabels([
            "Event Type", "Destination / Description", "At/By", "Time", "Notes"])
        self.route_table.setMinimumHeight(260)
        self.route_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self.route_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection)
        self.route_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents)  # Event Type
        self.route_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Interactive)  # Details
        self.route_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Fixed)    # "at" label
        self.route_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Fixed)    # Time
        self.route_table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.Stretch)  # Driver Comments
        self.route_table.setColumnWidth(1, 450)  # Details - wider
        self.route_table.setColumnWidth(2, 65)   # At/By dropdown
        self.route_table.setColumnWidth(3, 80)   # Time
        self.route_table.verticalHeader().setVisible(False)  # hide row numbers

        # Connect cell changes to recalculate billable time
        self.route_table.cellChanged.connect(self.calculate_route_billing)
        itinerary_layout.addWidget(self.route_table)

        # Load event types from database
        self._route_event_types = []  # Cache for event types
        self.load_route_event_types()

        # Initialize routing with Parent 1 and Parent 2 (locked)
        self._routing_parents_initialized = False
        self._routing_edit_enabled = False
        self._init_parent_routing()
        self.set_routing_edit_mode(False)

        # Driver routing notes
        driver_notes_row = QHBoxLayout()
        driver_notes_row.setContentsMargins(0, 0, 0, 0)
        driver_notes_row.addWidget(QLabel("Driver routing notes:"))
        self.driver_routing_notes = QLineEdit()
        self.driver_routing_notes.setPlaceholderText(
            "Event timing, split-run specifics, standby expectations")
        driver_notes_row.addWidget(self.driver_routing_notes)
        itinerary_layout.addLayout(driver_notes_row)

        itinerary_group.setLayout(itinerary_layout)
        return itinerary_group

    def toggle_routing_edit_mode(self):
        """Toggle between routing view-only mode and editable mode."""
        enabled = bool(
            hasattr(self, 'routing_edit_btn')
            and self.routing_edit_btn.isChecked()
        )
        self.set_routing_edit_mode(enabled)

    def set_routing_edit_mode(self, enabled: bool):
        """Keep routing visible while protecting it unless edit mode is enabled."""
        self._routing_edit_enabled = bool(enabled)

        if hasattr(self, 'routing_edit_btn'):
            self.routing_edit_btn.blockSignals(True)
            self.routing_edit_btn.setChecked(bool(enabled))
            self.routing_edit_btn.setText(
                "🔒 Lock Routing" if enabled else "✏️ Edit Routing"
            )
            self.routing_edit_btn.blockSignals(False)

        for btn_name in (
            'add_route_btn',
            'move_up_btn',
            'move_down_btn',
            'delete_selected_btn',
        ):
            btn = getattr(self, btn_name, None)
            if btn is not None:
                btn.setEnabled(bool(enabled))

        if hasattr(self, 'out_of_town_checkbox'):
            self.out_of_town_checkbox.setEnabled(bool(enabled))

        if hasattr(self, 'route_table'):
            self.route_table.setEditTriggers(
                QTableWidget.EditTrigger.AllEditTriggers
                if enabled
                else QTableWidget.EditTrigger.NoEditTriggers
            )

            for row in range(self.route_table.rowCount()):
                for col in (1, 4):
                    item = self.route_table.item(row, col)
                    if item is not None:
                        flags = item.flags()
                        if enabled:
                            item.setFlags(flags | Qt.ItemFlag.ItemIsEditable)
                        else:
                            item.setFlags(flags & ~Qt.ItemFlag.ItemIsEditable)

                for col in (0, 2, 3):
                    widget = self.route_table.cellWidget(row, col)
                    if widget is not None:
                        widget.setEnabled(bool(enabled))

    def _open_routing_charges_dialog(self):
        """Open Charter Details dialog directly to Routing & Charges tab."""
        try:
            if not self.charter_id:
                QMessageBox.information(
                    self,
                    "Routing & Charges",
                    "Save the charter first, then open Routing & Charges.")
                return

            reserve_number = self._fetch_reserve_number(self.charter_id)
            if not reserve_number:
                QMessageBox.warning(
                    self,
                    "Routing & Charges",
                    "Could not find reserve number for this charter.")
                return

            from drill_down_widgets import CharterDetailDialog
            dialog = CharterDetailDialog(
                self.db, reserve_number, self, initial_tab="routing")
            dialog.exec()
        except Exception as e:
            QMessageBox.warning(
                self,
                "Routing & Charges",
                f"Failed to open routing details: {e}")

    def _init_parent_routing(self):
        """Initialize routing table with locked Parent 1 and Parent 2"""
        self.route_table.setRowCount(2)
        is_out_of_town = bool(
            hasattr(self, 'out_of_town_checkbox')
            and self.out_of_town_checkbox.isChecked()
        )

        # Parent 1: Pickup at (or Leave Red Deer if out of town)
        parent1_label = QTableWidgetItem(
            "Leave Red Deer for" if is_out_of_town else "Pickup at"
        )
        parent1_label.setFlags(parent1_label.flags() & ~
                               Qt.ItemFlag.ItemIsEditable)
        parent1_label.setData(
            Qt.ItemDataRole.UserRole,
            "depart_red_deer" if is_out_of_town else "pickup_client",
        )
        # Gray background for locked rows
        parent1_label.setBackground(QColor(220, 220, 220))
        self.route_table.setItem(0, 0, parent1_label)
        self.route_table.setItem(0, 1, QTableWidgetItem(""))
        self.route_table.setItem(0, 4, QTableWidgetItem(""))
        self._set_route_at_by_widget(0, "at")
        self._set_route_time_widget(0, self.base_time_from.time())

        # Parent 2: Drop off at (or Return to Red Deer if out of town)
        parent2_label = QTableWidgetItem(
            "Return to Red Deer" if is_out_of_town else "Drop off at"
        )
        parent2_label.setFlags(parent2_label.flags() & ~
                               Qt.ItemFlag.ItemIsEditable)
        parent2_label.setData(
            Qt.ItemDataRole.UserRole,
            "return_red_deer" if is_out_of_town else "dropoff_client",
        )
        # Gray background for locked rows
        parent2_label.setBackground(QColor(220, 220, 220))
        self.route_table.setItem(1, 0, parent2_label)
        self.route_table.setItem(1, 1, QTableWidgetItem(""))
        self.route_table.setItem(1, 4, QTableWidgetItem(""))
        self._set_route_at_by_widget(1, "at")
        self._set_route_time_widget(1, self.base_time_to.time())

        self._routing_parents_initialized = True

    def _set_route_at_by_widget(self, row_idx: int, value: str = "at"):
        """Ensure At/By is rendered as a dropdown for a route row."""
        combo = self.route_table.cellWidget(row_idx, 2)
        if not isinstance(combo, QComboBox):
            combo = QComboBox()
            combo.addItems(["at", "by"])
            combo.setProperty('routing_control', True)
            combo.installEventFilter(self)
            self.route_table.setCellWidget(row_idx, 2, combo)
        idx = combo.findText((value or "at").lower())
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        combo.setEnabled(bool(getattr(self, '_routing_edit_enabled', False)))

    def _set_route_time_widget(self, row_idx: int, value: QTime):
        """Ensure Time is rendered as a time editor for a route row."""
        time_edit = self.route_table.cellWidget(row_idx, 3)
        if not isinstance(time_edit, QTimeEdit):
            time_edit = QTimeEdit()
            time_edit.setDisplayFormat("HH:mm")
            time_edit.setProperty('routing_control', True)
            time_edit.installEventFilter(self)
            time_edit.timeChanged.connect(
                lambda *_: self.calculate_route_billing()
            )
            time_edit.timeChanged.connect(
                self._on_route_time_changed_reverse_sync
            )
            self.route_table.setCellWidget(row_idx, 3, time_edit)
        if isinstance(value, QTime) and value.isValid():
            time_edit.setTime(value)
        time_edit.setEnabled(bool(getattr(self, '_routing_edit_enabled', False)))

    def _sync_routing_from_pickup_dropoff_times(self, *_):
        """Keep parent itinerary row times aligned with pickup/dropoff time boxes."""
        if getattr(self, '_syncing_times', False):
            return
        if not hasattr(self, "route_table") or self.route_table.rowCount() == 0:
            return

        self._set_route_time_widget(0, self.base_time_from.time())

        last_row = self.route_table.rowCount() - 1
        if last_row >= 1:
            self._set_route_time_widget(last_row, self.base_time_to.time())

    def _on_route_time_changed_reverse_sync(self):
        """When row-0 or last-row time edits change, push back to Pickup/Dropoff boxes."""
        if getattr(self, '_syncing_times', False):
            return
        if not hasattr(self, 'route_table') or self.route_table.rowCount() == 0:
            return
        sender = self.sender()
        row_count = self.route_table.rowCount()

        w0 = self.route_table.cellWidget(0, 3)
        if w0 is sender and hasattr(w0, 'time'):
            self._syncing_times = True
            try:
                self.base_time_from.setTime(w0.time())
            finally:
                self._syncing_times = False
            return

        wlast = self.route_table.cellWidget(row_count - 1, 3)
        if wlast is sender and hasattr(wlast, 'time'):
            self._syncing_times = True
            try:
                self.base_time_to.setTime(wlast.time())
            finally:
                self._syncing_times = False

    def move_route_line_up(self):
        """Move selected stop up (but not parents)"""
        current_row = self.route_table.currentRow()
        if current_row <= 1:  # Can't move Parent 1 or anything before row 2
            return

        # Swap with row above (unless it's Parent 1 at row 0)
        if current_row > 1:
            self._swap_route_rows(current_row, current_row - 1)
            self.route_table.setCurrentCell(current_row - 1, 0)

    def move_route_line_down(self):
        """Move selected stop down (but not parents)"""
        current_row = self.route_table.currentRow()
        last_row = self.route_table.rowCount() - 1

        if current_row < 1 or current_row >= last_row - \
                1:  # Can't move Parent 2 at last row
            return

        self._swap_route_rows(current_row, current_row + 1)
        self.route_table.setCurrentCell(current_row + 1, 0)

    def create_charter_details_section(
            self,
            lock_btn=None,
            cancel_btn=None,
            close_btn=None) -> QGroupBox:
        """Charter Details: Rate Type + Client Request
        Info + Control Buttons"""
        details_group = QGroupBox("Charter Details & Client Request")
        main_layout = QHBoxLayout()  # Horizontal layout, full width

        # LEFT COLUMN: Status + booking info stretches most of the width
        left_column = QVBoxLayout()

        # === CONTROL BUTTONS SECTION (TOP) ===
        if lock_btn or cancel_btn or close_btn:
            control_buttons_layout = QHBoxLayout()
            control_buttons_layout.setContentsMargins(0, 0, 0, 5)
            control_buttons_layout.setSpacing(5)

            if lock_btn:
                control_buttons_layout.addWidget(lock_btn)
            if cancel_btn:
                control_buttons_layout.addWidget(cancel_btn)
            if close_btn:
                control_buttons_layout.addWidget(close_btn)

            control_buttons_layout.addStretch()
            left_column.addLayout(control_buttons_layout)

        # === TOP SECTION: CHARTER STATUS (LEFT) + VEHICLE & DRIVER (MIDDLE)
        # + CLIENT NOTES (FULL RIGHT) ===
        top_row_layout = QHBoxLayout()

        # === CHARTER STATUS GROUP BOX (LEFT SIDE) ===
        status_group = QGroupBox("Charter Status")
        status_layout = QVBoxLayout()

        # Row 1: Status, Charter Type, and Run Type
        status_controls_layout = QHBoxLayout()

        status_controls_layout.addWidget(QLabel("<b>Status:</b>"))
        self.charter_status_combo = QComboBox()
        self.charter_status_combo.addItems(
            [
                "Quote",
                "Booked",
                "Completed",
                "Cancelled",
            ]
        )
        self.charter_status_combo.setMaximumWidth(140)
        self.charter_status_combo.currentTextChanged.connect(
            self._on_charter_status_changed)
        status_controls_layout.addWidget(self.charter_status_combo)

        status_controls_layout.addSpacing(8)

        status_controls_layout.addWidget(QLabel("Charter Type:"))
        self.charter_type_combo = QComboBox()
        self.charter_type_combo.setMaximumWidth(180)
        self.load_charter_types()
        status_controls_layout.addWidget(self.charter_type_combo)

        status_controls_layout.addSpacing(8)

        status_controls_layout.addWidget(QLabel("Run Type:"))
        self.run_type_combo = QComboBox()
        self.run_type_combo.setMaximumWidth(180)
        self.load_run_types()
        self.run_type_combo.currentIndexChanged.connect(
            self._on_run_type_changed)
        status_controls_layout.addWidget(self.run_type_combo)

        edit_run_types_btn = QPushButton("Edit Types")
        edit_run_types_btn.setMaximumWidth(90)
        edit_run_types_btn.clicked.connect(self.open_run_type_editor)
        status_controls_layout.addWidget(edit_run_types_btn)

        status_controls_layout.addStretch()
        status_layout.addLayout(status_controls_layout)

        # Row 2: Rate Type, Hours, Quoted Hourly, Extended
        rate_pricing_layout = QHBoxLayout()
        rate_pricing_layout.setSpacing(6)

        rate_pricing_layout.addWidget(QLabel("<b>Rate Type:</b>"))
        self.rate_type_combo = QComboBox()
        self.rate_type_combo.addItems(
            ["Hourly", "Package", "Daily", "Custom/Flat", "Split Run"])
        self.rate_type_combo.setMaximumWidth(130)
        self.rate_type_combo.currentTextChanged.connect(
            self._update_rate_type_fields)
        rate_pricing_layout.addWidget(self.rate_type_combo)

        rate_pricing_layout.addSpacing(4)
        rate_pricing_layout.addWidget(QLabel("Min Hours:"))
        self.package_hours_combo = QComboBox()
        self.package_hours_combo.addItems(
            ["2 hrs", "3 hrs", "4 hrs", "5 hrs",
             "6 hrs", "8 hrs", "10 hrs", "12 hrs"])
        self.package_hours_combo.setMaximumWidth(80)
        self.package_hours_combo.setVisible(False)
        rate_pricing_layout.addWidget(self.package_hours_combo)

        rate_pricing_layout.addWidget(QLabel("Day Rate:"))
        self.day_rate_display = QLineEdit()
        self.day_rate_display.setPlaceholderText("$0.00")
        self.day_rate_display.setMaximumWidth(80)
        self.day_rate_display.setReadOnly(True)
        self.day_rate_display.setVisible(False)
        rate_pricing_layout.addWidget(self.day_rate_display)

        self.split_standby_checkbox = QCheckBox("Standby")
        self.split_standby_checkbox.setVisible(False)
        rate_pricing_layout.addWidget(self.split_standby_checkbox)

        self.split_standby_amount = QLineEdit()
        self.split_standby_amount.setPlaceholderText("$")
        self.split_standby_amount.setMaximumWidth(60)
        self.split_standby_amount.setVisible(False)
        rate_pricing_layout.addWidget(self.split_standby_amount)

        self.extended_hourly_checkbox = QCheckBox("Extra Time $/Hr:")
        rate_pricing_layout.addWidget(self.extended_hourly_checkbox)

        self.extended_hourly_price = QLineEdit()
        self.extended_hourly_price.setPlaceholderText("$0.00")
        self.extended_hourly_price.setMaximumWidth(80)
        self.extended_hourly_price.setEnabled(False)
        rate_pricing_layout.addWidget(self.extended_hourly_price)
        self.extended_hourly_checkbox.toggled.connect(
            self.extended_hourly_price.setEnabled)

        rate_pricing_layout.addWidget(QLabel("Quoted Hourly:"))
        self.quoted_hourly_price = QLineEdit()
        self.quoted_hourly_price.setPlaceholderText("$0.00")
        self.quoted_hourly_price.setMaximumWidth(80)
        rate_pricing_layout.addWidget(self.quoted_hourly_price)

        rate_pricing_layout.addWidget(QLabel("Base Rate:"))
        self.base_charge_display = QLineEdit()
        self.base_charge_display.setPlaceholderText("$0.00")
        self.base_charge_display.setMaximumWidth(80)
        self.base_charge_display.setReadOnly(True)
        self.base_charge_display.setVisible(False)
        rate_pricing_layout.addWidget(self.base_charge_display)

        rate_pricing_layout.addWidget(QLabel("Flat/Package:"))
        self.flat_rate_display = QLineEdit()
        self.flat_rate_display.setPlaceholderText("$0.00")
        self.flat_rate_display.setMaximumWidth(80)
        self.flat_rate_display.setReadOnly(True)
        self.flat_rate_display.setVisible(False)
        rate_pricing_layout.addWidget(self.flat_rate_display)

        rate_pricing_layout.addWidget(QLabel("Split Rate:"))
        self.split_rate_display = QLineEdit()
        self.split_rate_display.setPlaceholderText("$0.00")
        self.split_rate_display.setMaximumWidth(80)
        self.split_rate_display.setReadOnly(True)
        self.split_rate_display.setVisible(False)
        rate_pricing_layout.addWidget(self.split_rate_display)

        rate_pricing_layout.addWidget(QLabel("Standby Rate:"))
        self.standby_rate_display = QLineEdit()
        self.standby_rate_display.setPlaceholderText("$0.00")
        self.standby_rate_display.setMaximumWidth(80)
        self.standby_rate_display.setReadOnly(True)
        self.standby_rate_display.setVisible(False)
        rate_pricing_layout.addWidget(self.standby_rate_display)

        rate_pricing_layout.addWidget(QLabel("NRR Deposit:"))
        self.nrr_deposit = QLineEdit()
        self.nrr_deposit.setPlaceholderText("$0.00")
        self.nrr_deposit.setMaximumWidth(80)
        rate_pricing_layout.addWidget(self.nrr_deposit)

        rate_pricing_layout.addStretch()

        # Charter Date Range & Base Timing (allow multi-day charters)
        date_time_layout = QVBoxLayout()
        date_time_layout.setContentsMargins(0, 0, 0, 0)
        date_time_layout.setSpacing(5)

        # Row 1: Charter Date From/To
        date_row = QHBoxLayout()
        date_row.addWidget(QLabel("Charter Date:"))

        date_row.addWidget(QLabel("From"))
        self.charter_date_from = QDateEdit()
        self.charter_date_from.setCalendarPopup(True)
        self.charter_date_from.setDisplayFormat("MM/dd/yyyy")
        self.charter_date_from.setDate(QDate.currentDate())
        self.charter_date_from.setMaximumWidth(120)
        date_row.addWidget(self.charter_date_from)

        date_row.addSpacing(10)
        date_row.addWidget(QLabel("To"))
        self.charter_date_to = QDateEdit()
        self.charter_date_to.setCalendarPopup(True)
        self.charter_date_to.setDisplayFormat("MM/dd/yyyy")
        self.charter_date_to.setDate(QDate.currentDate())
        self.charter_date_to.setMaximumWidth(120)
        date_row.addWidget(self.charter_date_to)

        date_row.addStretch()
        date_time_layout.addLayout(date_row)

        # Row 2: Pickup/Dropoff Times (allows past midnight)
        time_row = QHBoxLayout()
        time_row.addWidget(QLabel("Pickup/Dropoff:"))

        time_row.addWidget(QLabel("Pickup"))
        self.base_time_from = QTimeEdit()
        self.base_time_from.setDisplayFormat("HH:mm")
        self.base_time_from.setTime(QTime.currentTime())
        self.base_time_from.setMaximumWidth(80)
        self.base_time_from.timeChanged.connect(
            self._calculate_charter_duration)
        self.base_time_from.timeChanged.connect(
            self._sync_routing_from_pickup_dropoff_times)
        time_row.addWidget(self.base_time_from)

        time_row.addSpacing(10)
        time_row.addWidget(QLabel("Dropoff"))
        self.base_time_to = QTimeEdit()
        self.base_time_to.setDisplayFormat("HH:mm")
        self.base_time_to.setTime(QTime.currentTime().addSecs(2 * 60 * 60))
        self.base_time_to.setMaximumWidth(80)
        self.base_time_to.timeChanged.connect(self._calculate_charter_duration)
        self.base_time_to.timeChanged.connect(
            self._sync_routing_from_pickup_dropoff_times)
        time_row.addWidget(self.base_time_to)

        # Duration display
        time_row.addSpacing(15)
        time_row.addWidget(QLabel("Duration:"))
        self.duration_label = QLabel("2.0 hrs")
        self.duration_label.setStyleSheet("font-weight: bold; color: #0066cc;")
        self.duration_label.setMinimumWidth(60)
        time_row.addWidget(self.duration_label)

        time_row.addStretch()
        date_time_layout.addLayout(time_row)

        # Keep legacy fields for backward compatibility
        self.pickup_datetime = self.charter_date_from  # Alias for old code
        self.charter_date = self.charter_date_from  # Alias for old code
        try:
            self.charter_date.getDate = self.charter_date_from.date
        except Exception:
            pass
        self.pickup_time_input = self.base_time_from
        self.pickup_time = self.base_time_from
        self.dropoff_datetime = self.charter_date_to  # Alias for old code

        # Row 3: Gratuity controls
        gratuity_row = QHBoxLayout()
        self.gratuity_checkbox = QCheckBox("Gratuity:")
        self.gratuity_checkbox.setChecked(True)  # Default enabled
        self.gratuity_checkbox.toggled.connect(
            self._on_gratuity_checkbox_toggled)
        gratuity_row.addWidget(self.gratuity_checkbox)

        self.gratuity_percent_input = QDoubleSpinBox()
        self.gratuity_percent_input.setMaximum(100.0)
        self.gratuity_percent_input.setDecimals(1)
        self.gratuity_percent_input.setValue(18.0)
        self.gratuity_percent_input.setSuffix("%")
        self.gratuity_percent_input.setMaximumWidth(70)
        self.gratuity_percent_input.valueChanged.connect(
            self._on_gratuity_percent_changed)
        gratuity_row.addWidget(self.gratuity_percent_input)

        gratuity_row.addStretch()

        # === VEHICLE & DRIVER ASSIGNMENT (WITH REQUESTED VEHICLE & PAX) ===
        dispatch_group = QGroupBox("Vehicle and Driver")
        dispatch_layout = QVBoxLayout()

        # Top row: Requested Vehicle Type | Pax
        top_dispatch_row = QHBoxLayout()

        top_dispatch_row.addWidget(QLabel("Requested Vehicle Type:"))
        self.vehicle_type_requested_combo = QComboBox()
        self.vehicle_type_requested_combo.setMaximumWidth(250)
        self.load_vehicle_types_requested()
        self.vehicle_type_requested_combo.currentIndexChanged.connect(
            self._on_requested_vehicle_type_changed)
        top_dispatch_row.addWidget(self.vehicle_type_requested_combo)

        top_dispatch_row.addSpacing(10)

        top_dispatch_row.addWidget(QLabel("Pax:"))
        self.num_passengers = QSpinBox()
        self.num_passengers.setMinimum(1)
        self.num_passengers.setMaximum(100)
        self.num_passengers.setValue(1)
        self.num_passengers.setFixedWidth(50)
        top_dispatch_row.addWidget(self.num_passengers)

        top_dispatch_row.addStretch()
        dispatch_layout.addLayout(top_dispatch_row)

        # Bottom row: Vehicle | Type | Driver
        bottom_dispatch_row = QHBoxLayout()

        bottom_dispatch_row.addWidget(QLabel("Vehicle:"))
        self.vehicle_combo = QComboBox()
        try:
            self.vehicle_combo.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToContents)
        except Exception:
            pass
        self.vehicle_combo.setMinimumContentsLength(4)
        self.vehicle_combo.setMaximumWidth(180)
        self.load_vehicles()
        bottom_dispatch_row.addWidget(self.vehicle_combo)

        bottom_dispatch_row.addSpacing(12)

        bottom_dispatch_row.addWidget(QLabel("Type:"))
        self.vehicle_type_label = QLabel("")
        self.vehicle_type_label.setStyleSheet("color: #555;")
        self.vehicle_type_label.setMinimumWidth(280)
        self.vehicle_type_label.setMaximumWidth(350)
        self.vehicle_type_label.setWordWrap(False)
        bottom_dispatch_row.addWidget(self.vehicle_type_label)
        try:
            self.vehicle_combo.currentIndexChanged.connect(
                self._update_vehicle_type_display)
        except Exception:
            pass

        bottom_dispatch_row.addSpacing(12)

        bottom_dispatch_row.addWidget(QLabel("Driver:"))
        self.driver_combo = QComboBox()
        self.load_drivers()
        self.driver_combo.setMaximumWidth(220)
        bottom_dispatch_row.addWidget(self.driver_combo)

        # Driver name display (to the right of driver combo)
        self.driver_name_display_label = QLabel("")
        self.driver_name_display_label.setStyleSheet(
            "color: #555; font-style: italic;")
        self.driver_name_display_label.setMinimumWidth(150)
        self.driver_name_display_label.setMaximumWidth(200)
        bottom_dispatch_row.addWidget(self.driver_name_display_label)

        # Connect driver combo to update display label
        try:
            self.driver_combo.currentIndexChanged.connect(
                self._update_driver_name_display)
        except Exception:
            pass

        bottom_dispatch_row.addStretch()
        dispatch_layout.addLayout(bottom_dispatch_row)

        dispatch_group.setLayout(dispatch_layout)
        # Reasonable width without squishing notes
        dispatch_group.setMaximumWidth(750)

        # Vehicle/driver row
        out_of_town_layout = QHBoxLayout()
        out_of_town_layout.addWidget(dispatch_group)
        out_of_town_layout.addStretch()

        # Required workflow order:
        # Status -> Date/Pickup/Dropoff -> Vehicle Requested
        # -> Rate details -> Gratuity
        status_layout.addLayout(date_time_layout)
        status_layout.addLayout(out_of_town_layout)
        status_layout.addLayout(rate_pricing_layout)
        status_layout.addLayout(gratuity_row)

        status_group.setLayout(status_layout)
        top_row_layout.addWidget(status_group)

        # === CLIENT NOTES & DISPATCHER NOTES (TOP SECTION - SIDE BY SIDE) ===
        notes_and_dispatch_container = QWidget()
        notes_and_dispatch_layout = QHBoxLayout()
        notes_and_dispatch_layout.setContentsMargins(0, 0, 0, 0)
        notes_and_dispatch_layout.setSpacing(5)

        # Client Notes (left side)
        client_notes_group = QGroupBox("Client Notes")
        client_notes_layout = QVBoxLayout()

        from PyQt6.QtWidgets import QTextEdit
        self.client_notes_input = QTextEdit()
        self.client_notes_input.setPlaceholderText("Client-facing notes...")
        # Span multiple rows toward invoicing area
        self.client_notes_input.setMinimumHeight(260)
        self.client_notes_input.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding)
        _attach_spellcheck(self.client_notes_input)
        client_notes_layout.addWidget(self.client_notes_input)
        client_notes_group.setLayout(client_notes_layout)
        notes_and_dispatch_layout.addWidget(client_notes_group, 1)

        # Dispatcher Notes (right side)
        dispatcher_notes_group = QGroupBox("Dispatcher Notes")
        dispatcher_notes_layout = QVBoxLayout()
        self.dispatcher_notes_input = QTextEdit()
        self.dispatcher_notes_input.setPlaceholderText(
            "Internal dispatcher instructions,"
            " special requests, timing notes...")
        # Span multiple rows toward invoicing area
        self.dispatcher_notes_input.setMinimumHeight(260)
        self.dispatcher_notes_input.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        _attach_spellcheck(self.dispatcher_notes_input)
        dispatcher_notes_layout.addWidget(self.dispatcher_notes_input)
        dispatcher_notes_group.setLayout(dispatcher_notes_layout)
        notes_and_dispatch_layout.addWidget(dispatcher_notes_group, 1)

        self.notes_save_status_label = QLabel("")
        self.notes_save_status_label.setStyleSheet("color: #2f6f44;")
        self.notes_save_status_label.setMinimumHeight(18)

        # Auto-save notes 2 s after the user stops typing
        self._notes_save_timer = QTimer(self)
        self._notes_save_timer.setSingleShot(True)
        self._notes_save_timer.setInterval(2000)
        self._notes_save_timer.timeout.connect(self._auto_save_notes)
        self.client_notes_input.textChanged.connect(self._on_notes_text_changed)
        self.dispatcher_notes_input.textChanged.connect(
            self._on_notes_text_changed)

        self._notes_status_clear_timer = QTimer(self)
        self._notes_status_clear_timer.setSingleShot(True)
        self._notes_status_clear_timer.setInterval(3000)
        self._notes_status_clear_timer.timeout.connect(
            self._clear_notes_save_status)

        notes_container_layout = QVBoxLayout()
        notes_container_layout.setContentsMargins(0, 0, 0, 0)
        notes_container_layout.setSpacing(4)
        notes_container_layout.addLayout(notes_and_dispatch_layout)
        notes_container_layout.addWidget(self.notes_save_status_label)
        notes_and_dispatch_container.setLayout(notes_container_layout)
        notes_and_dispatch_container.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        left_column.addLayout(top_row_layout)
        left_column.addSpacing(10)

        # Backward compatibility alias
        self.status_combo = self.charter_status_combo

        # Backward-compat aliases so older save/load code keeps working
        self.service_date = self.pickup_datetime
        self.charter_date = self.pickup_datetime
        try:
            # Provide getDate() similar to old DateInput
            self.charter_date.getDate = self.pickup_datetime.date
        except Exception:
            pass
        self.pickup_time_input = self.pickup_datetime
        self.pickup_time = self.pickup_datetime
        self.dropoff_time_input = self.dropoff_datetime

        left_column.addSpacing(10)

        # === ROUTING & CHARGES MANAGED IN CHARTER DETAILS WINDOW ===
        routing_shortcut_group = QGroupBox("Routing & Charges")
        routing_shortcut_layout = QHBoxLayout()
        routing_shortcut_layout.setContentsMargins(10, 10, 10, 10)

        routing_shortcut_layout.addWidget(
            QLabel(
                "Manage routing and charges"
                " in the Charter Details window."))
        routing_shortcut_layout.addStretch()

        open_routing_btn = QPushButton("Open Routing & Charges")
        open_routing_btn.clicked.connect(self._open_routing_charges_dialog)
        routing_shortcut_layout.addWidget(open_routing_btn)

        routing_shortcut_group.setLayout(routing_shortcut_layout)
        left_column.addWidget(routing_shortcut_group)

        # Notes and dispatcher notes below routing (dispatch-first layout)
        left_column.addSpacing(10)
        left_column.addWidget(notes_and_dispatch_container)

        # Layout left column without width constraints
        left_widget = QWidget()
        left_widget.setLayout(left_column)
        # Stretch factor 1 to expand full width
        main_layout.addWidget(left_widget, 1)

        # RIGHT COLUMN: Driver information stack
        right_column = QVBoxLayout()

        # === DRIVER INFO & DUTY LOG ===
        driver_info_group = QGroupBox("Driver Information")
        driver_info_group.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed)
        driver_info_layout = QVBoxLayout()

        # Driver name (read-only, syncs from dispatch)
        driver_name_row = QHBoxLayout()
        driver_name_row.addWidget(QLabel("<b>Driver:</b>"))
        self.driver_info_name_label = QLabel("(Not assigned)")
        self.driver_info_name_label.setStyleSheet("color: #555;")
        driver_name_row.addWidget(self.driver_info_name_label)
        driver_name_row.addStretch()
        driver_info_layout.addLayout(driver_name_row)

        # Work shift duty log
        duty_log_label = QLabel("<b>Work Shift Duty Log:</b>")
        driver_info_layout.addWidget(duty_log_label)

        on_duty_row = QHBoxLayout()
        on_duty_row.addWidget(QLabel("On Duty:"))
        self.on_duty_time_input = QLineEdit()
        self.on_duty_time_input.setPlaceholderText("HH:MM")
        self.on_duty_time_input.setMaximumWidth(80)
        on_duty_row.addWidget(self.on_duty_time_input)
        on_duty_row.addStretch()
        driver_info_layout.addLayout(on_duty_row)

        off_duty_row = QHBoxLayout()
        off_duty_row.addWidget(QLabel("Off Duty:"))
        self.off_duty_time_input = QLineEdit()
        self.off_duty_time_input.setPlaceholderText("HH:MM")
        self.off_duty_time_input.setMaximumWidth(80)
        off_duty_row.addWidget(self.off_duty_time_input)
        off_duty_row.addStretch()
        driver_info_layout.addLayout(off_duty_row)

        # Button to add duty status change
        add_duty_btn = QPushButton("+ Add Duty Status Change")
        add_duty_btn.setMaximumWidth(200)
        driver_info_layout.addWidget(add_duty_btn)

        driver_info_group.setLayout(driver_info_layout)
        right_column.addWidget(driver_info_group, 0)

        # === 14-DAY HOS TRACKING ===
        hos_group = QGroupBox(
            "Hours of Service (Last 14 Days) - Duty Status Log")
        hos_group.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding)
        hos_layout = QVBoxLayout()

        # Month/Year/Cycle selector
        hos_header = QHBoxLayout()
        hos_header.addWidget(QLabel("<b>Month:</b>"))
        self.hos_month_combo = QComboBox()
        self.hos_month_combo.addItems(["January",
                                       "February",
                                       "March",
                                       "April",
                                       "May",
                                       "June",
                                       "July",
                                       "August",
                                       "September",
                                       "October",
                                       "November",
                                       "December"])
        self.hos_month_combo.setMaximumWidth(100)
        hos_header.addWidget(self.hos_month_combo)
        hos_header.addWidget(QLabel("<b>Year:</b>"))
        self.hos_year_input = QLineEdit("2026")
        self.hos_year_input.setMaximumWidth(50)
        hos_header.addWidget(self.hos_year_input)
        hos_header.addStretch()
        hos_layout.addLayout(hos_header)

        # HOS Grid Table - simplified for radius exemption (160km)
        # Only need On-Duty and Off-Duty totals per day
        self.hos_table = QTableWidget()
        self.hos_table.setRowCount(3)  # Off-duty, On-duty, Total
        self.hos_table.setColumnCount(15)  # 14 days + Totals column

        # Row headers (duty status types) - simplified for radius exemption
        self.hos_table.setVerticalHeaderLabels([
            "Off-Duty",
            "On-Duty",
            "Total (24hr)"])

        # Column headers (days 1-31 condensed to show last 14 days)
        from datetime import datetime, timedelta
        today = datetime.now()
        day_headers = []
        for i in range(13, -1, -1):  # Last 14 days
            day_date = today - timedelta(days=i)
            day_headers.append(str(day_date.day))
        day_headers.append("Total")
        self.hos_table.setHorizontalHeaderLabels(day_headers)

        # Set column widths - keep readable without scrollbars
        for col in range(14):
            self.hos_table.setColumnWidth(col, 44)
            self.hos_table.setRowHeight(0, 32)
            self.hos_table.setRowHeight(1, 32)
            self.hos_table.setRowHeight(2, 32)
        self.hos_table.setColumnWidth(14, 90)  # Total column wider

        # Style the table header
        self.hos_table.horizontalHeader().setStyleSheet(
            (
                "QHeaderView::section { background-color: #e0e0e0; "
                "font-weight: bold; padding: 2px;}"
            )
        )
        self.hos_table.verticalHeader().setStyleSheet(
            (
                "QHeaderView::section { background-color: #f5f5f5; "
                "font-weight: bold; padding: 2px; font-size: 9pt;}"
            )
        )

        # Populate with default values (24 hours off-duty unless bookings
        # exist)
        for day_col in range(14):
            # Off-duty default: 24 hours (light blue background)
            off_duty_cell = QTableWidgetItem("24")
            off_duty_cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            off_duty_cell.setBackground(QColor("#E6F3FF"))  # Light blue
            off_duty_cell.setFont(QFont("Arial", 9, QFont.Weight.Bold))
            self.hos_table.setItem(0, day_col, off_duty_cell)

            # On-duty default: 0 hours (yellow background)
            on_duty_cell = QTableWidgetItem("0")
            on_duty_cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            on_duty_cell.setBackground(QColor("#FFFFCC"))  # Light yellow
            on_duty_cell.setFont(QFont("Arial", 9))
            self.hos_table.setItem(1, day_col, on_duty_cell)

            # Total: 24 hours (gray background, read-only)
            total_cell = QTableWidgetItem("24")
            total_cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            total_cell.setFlags(Qt.ItemFlag.ItemIsEnabled)  # Read-only
            total_cell.setBackground(QColor("#D3D3D3"))  # Gray
            total_cell.setFont(QFont("Arial", 9, QFont.Weight.Bold))
            self.hos_table.setItem(2, day_col, total_cell)

        # Totals column (last column) - summary across all 14 days
        total_off = QTableWidgetItem("336")  # 14 days × 24 hours
        total_off.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        total_off.setFlags(Qt.ItemFlag.ItemIsEnabled)
        total_off.setBackground(QColor("#FFE6CC"))  # Orange tint
        total_off.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        self.hos_table.setItem(0, 14, total_off)

        total_on = QTableWidgetItem("0")
        total_on.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        total_on.setFlags(Qt.ItemFlag.ItemIsEnabled)
        total_on.setBackground(QColor("#FFE6CC"))
        total_on.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        self.hos_table.setItem(1, 14, total_on)

        total_all = QTableWidgetItem("336")
        total_all.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        total_all.setFlags(Qt.ItemFlag.ItemIsEnabled)
        total_all.setBackground(QColor("#C0C0C0"))  # Darker gray
        total_all.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        self.hos_table.setItem(2, 14, total_all)

        self.hos_table.setMinimumWidth(820)
        self.hos_table.setMinimumHeight(320)
        self.hos_table.setMaximumHeight(360)
        self.hos_table.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred)
        self.hos_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.hos_table.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        hos_layout.addWidget(self.hos_table)

        # Manual time correction panel (no GPS; manual entry allowed)
        manual_row = QHBoxLayout()
        manual_row.addWidget(QLabel("<b>Manual Correction:</b>"))
        # Build last 14 dates list for selection
        self.hos_last14_dates = []
        try:
            from datetime import datetime, timedelta
            today = datetime.now().date()
            for i in range(13, -1, -1):
                d = today - timedelta(days=i)
                self.hos_last14_dates.append(d)
        except Exception:
            pass
        manual_row.addWidget(QLabel("Day:"))
        self.manual_day_combo = QComboBox()
        for d in self.hos_last14_dates:
            self.manual_day_combo.addItem(d.strftime("%Y-%m-%d"))
        self.manual_day_combo.setMaximumWidth(110)
        manual_row.addWidget(self.manual_day_combo)
        manual_row.addWidget(QLabel("Start (HH:MM):"))
        self.manual_start_input = QLineEdit()
        self.manual_start_input.setPlaceholderText("08:00")
        self.manual_start_input.setMaximumWidth(70)
        manual_row.addWidget(self.manual_start_input)
        manual_row.addWidget(QLabel("End (HH:MM):"))
        self.manual_end_input = QLineEdit()
        self.manual_end_input.setPlaceholderText("18:00")
        self.manual_end_input.setMaximumWidth(70)
        manual_row.addWidget(self.manual_end_input)
        manual_row.addWidget(QLabel("Break (h):"))
        self.manual_break_input = QLineEdit()
        self.manual_break_input.setPlaceholderText("1.0")
        self.manual_break_input.setMaximumWidth(50)
        manual_row.addWidget(self.manual_break_input)
        manual_apply_btn = QPushButton("Apply Correction")
        manual_apply_btn.setMaximumWidth(130)
        manual_apply_btn.clicked.connect(self._apply_manual_times)
        manual_row.addWidget(manual_apply_btn)
        manual_row.addStretch()
        hos_layout.addLayout(manual_row)
        # Light validators and prechecks for manual inputs
        try:
            self.manual_start_input.setInputMask("00:00")
            self.manual_end_input.setInputMask("00:00")
            from PyQt6.QtGui import QDoubleValidator
            dv = QDoubleValidator(0.0, 24.0, 2)
            dv.setNotation(QDoubleValidator.Notation.StandardNotation)
            self.manual_break_input.setValidator(dv)
            self.manual_start_input.editingFinished.connect(
                self._precheck_manual_inputs)
            self.manual_end_input.editingFinished.connect(
                self._precheck_manual_inputs)
            self.manual_break_input.editingFinished.connect(
                self._precheck_manual_inputs)
        except Exception:
            pass

        # Cycle/Remarks section (matching log book)
        remarks_row = QHBoxLayout()
        remarks_row.addWidget(QLabel("<b>Cycle:</b>"))
        self.cycle_combo = QComboBox()
        self.cycle_combo.addItems(["Cycle 1", "Cycle 2", "Cycle 1 & 2"])
        self.cycle_combo.setMaximumWidth(120)
        self.cycle_combo.setCurrentText("Cycle 1")  # Legal default
        remarks_row.addWidget(self.cycle_combo)
        remarks_row.addWidget(QLabel("<b>Total Hours (5 days):</b>"))
        self.total_hours_label = QLabel("0")
        self.total_hours_label.setStyleSheet("font-weight: bold; color: #d00;")
        remarks_row.addWidget(self.total_hours_label)
        # Add 7-day on-duty display for Cycle 1 reference
        remarks_row.addWidget(QLabel("<b>7-day On-Duty:</b>"))
        self.total_7day_label = QLabel("0")
        self.total_7day_label.setStyleSheet("font-weight: bold; color: #333;")
        remarks_row.addWidget(self.total_7day_label)
        remarks_row.addStretch()
        hos_layout.addLayout(remarks_row)
        # React to cycle changes
        self.cycle_combo.currentTextChanged.connect(
            self._validate_hos_compliance)

        # Compliance + export/send controls
        hos_status_row = QHBoxLayout()
        self.hos_compliance_label = QLabel("HOS status: pending check")
        self.hos_compliance_label.setStyleSheet("color: #555; font-size: 9pt;")
        hos_status_row.addWidget(self.hos_compliance_label)
        hos_status_row.addStretch()
        export_btn = QPushButton("Export PDF")
        export_btn.setMaximumWidth(100)
        export_btn.clicked.connect(self._export_hos_log_pdf)
        hos_status_row.addWidget(export_btn)
        email_btn = QPushButton("Email PDF")
        email_btn.setMaximumWidth(100)
        email_btn.clicked.connect(self._email_hos_pdf)
        hos_status_row.addWidget(email_btn)
        sms_btn = QPushButton("Text PDF")
        sms_btn.setMaximumWidth(100)
        sms_btn.clicked.connect(self._text_hos_pdf)
        hos_status_row.addWidget(sms_btn)
        hos_layout.addLayout(hos_status_row)

        # Print-ready templates for officers/dispatch
        forms_row = QHBoxLayout()
        forms_row.addWidget(QLabel("Driver Forms:"))
        print_hos_form_btn = QPushButton("Print Monthly HOS Form")
        print_hos_form_btn.setMaximumWidth(170)
        print_hos_form_btn.clicked.connect(self._print_monthly_hos_form)
        forms_row.addWidget(print_hos_form_btn)
        print_inspect_form_btn = QPushButton("Print Daily Inspection Form")
        print_inspect_form_btn.setMaximumWidth(170)
        print_inspect_form_btn.clicked.connect(
            self._print_daily_inspection_form)
        forms_row.addWidget(print_inspect_form_btn)
        complete_inspect_btn = QPushButton("Complete Inspection Online")
        complete_inspect_btn.setMaximumWidth(180)
        complete_inspect_btn.clicked.connect(
            self._mark_inspection_completed_online)
        forms_row.addWidget(complete_inspect_btn)
        forms_row.addStretch()
        hos_layout.addLayout(forms_row)
        try:
            self._validate_hos_compliance()
        except Exception:
            pass

        hos_group.setLayout(hos_layout)
        right_column.addWidget(hos_group, 2)

        # === VEHICLE INSPECTION & DEFECTS ===
        vehicle_inspection_group = QGroupBox("Vehicle Pre-Trip Inspection")
        vehicle_inspection_group.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        vehicle_inspection_layout = QVBoxLayout()

        # Simplified inspection box (filled from driver report)
        vehicle_inspection_layout.addWidget(
            QLabel("<b>Inspection Summary (Driver Report):</b>"))

        summary_row = QHBoxLayout()
        summary_row.addWidget(QLabel("Date:"))
        self.inspection_date_input = QLineEdit()
        self.inspection_date_input.setPlaceholderText("YYYY-MM-DD")
        self.inspection_date_input.setMaximumWidth(110)
        summary_row.addWidget(self.inspection_date_input)
        summary_row.addWidget(QLabel("Time:"))
        self.inspection_time_input = QLineEdit()
        self.inspection_time_input.setPlaceholderText("HH:MM")
        self.inspection_time_input.setMaximumWidth(70)
        summary_row.addWidget(self.inspection_time_input)
        summary_row.addWidget(QLabel("Mileage:"))
        self.inspection_mileage_input = QLineEdit()
        self.inspection_mileage_input.setPlaceholderText("Odometer")
        self.inspection_mileage_input.setMaximumWidth(90)
        summary_row.addWidget(self.inspection_mileage_input)
        summary_row.addStretch()
        vehicle_inspection_layout.addLayout(summary_row)

        # Vehicle condition checkboxes (simple)
        condition_row = QVBoxLayout()
        self.inspection_no_defects = QCheckBox("✓ No Defects Found")
        self.inspection_no_defects.setChecked(True)
        condition_row.addWidget(self.inspection_no_defects)

        self.inspection_minor_defects = QCheckBox(
            "⚠ Minor Defects Found (list below)")
        condition_row.addWidget(self.inspection_minor_defects)
        vehicle_inspection_layout.addLayout(condition_row)

        # Minor defect list
        vehicle_inspection_layout.addWidget(
            QLabel("<b>Minor Defects Listed:</b>"))
        self.defect_notes_input = QTextEdit()
        self.defect_notes_input.setPlaceholderText(
            "List minor defects from driver report")
        self.defect_notes_input.setMaximumHeight(70)
        vehicle_inspection_layout.addWidget(self.defect_notes_input)

        vehicle_inspection_group.setLayout(vehicle_inspection_layout)
        right_column.addWidget(vehicle_inspection_group, 1)

        # === HOS EXEMPTIONS & LEGAL COMPLIANCE ===
        exemption_group = QGroupBox("HOS Exemptions & Emergency Status")
        exemption_group.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed)
        exemption_layout = QVBoxLayout()

        exemption_label = QLabel("<b>Emergency/Exemption Status:</b>")
        exemption_layout.addWidget(exemption_label)

        exemption_checks = QVBoxLayout()
        self.exemption_adverse_weather = QCheckBox(
            "Adverse Weather (e.g., snow storm, severe rain)")
        exemption_checks.addWidget(self.exemption_adverse_weather)

        self.exemption_mechanical = QCheckBox(
            "Mechanical Emergency (vehicle breakdown en route)")
        exemption_checks.addWidget(self.exemption_mechanical)

        self.exemption_emergency = QCheckBox(
            "Emergency Relief (medical, accident, disaster response)")
        exemption_checks.addWidget(self.exemption_emergency)

        self.exemption_off_duty_deferral = QCheckBox(
            "Off-Duty Deferral Used (Day 1/Day 2)")
        exemption_checks.addWidget(self.exemption_off_duty_deferral)

        exemption_layout.addLayout(exemption_checks)

        # Recalculate compliance when exemption toggles change
        self.exemption_adverse_weather.toggled.connect(
            self._validate_hos_compliance)
        self.exemption_mechanical.toggled.connect(
            self._validate_hos_compliance)
        self.exemption_emergency.toggled.connect(self._validate_hos_compliance)
        self.exemption_off_duty_deferral.toggled.connect(
            self._validate_hos_compliance)

        # Exemption remarks
        exemption_layout.addWidget(QLabel("<b>Exemption Details:</b>"))
        self.exemption_remarks_input = QTextEdit()
        self.exemption_remarks_input.setPlaceholderText(
            "Explain circumstances (weather conditions, breakdown time, etc.)")
        self.exemption_remarks_input.setMaximumHeight(60)
        exemption_layout.addWidget(self.exemption_remarks_input)

        exemption_group.setLayout(exemption_layout)
        right_column.addWidget(exemption_group, 1)

        details_group.setLayout(main_layout)
        return details_group

    def _update_rate_type_fields(self, rate_type_text: str = None):
        """Show/hide conditional fields based on selected rate type"""
        if rate_type_text is None:
            rate_type_text = self.rate_type_combo.currentText()

        is_package = "Package" in rate_type_text
        is_daily = "Daily" in rate_type_text
        is_split = "Split Run" in rate_type_text
        is_flat = "Flat" in rate_type_text or "Custom" in rate_type_text

        self.package_hours_combo.setVisible(is_package)
        self.day_rate_display.setVisible(is_daily)
        self.split_standby_checkbox.setVisible(is_split)
        self.split_standby_amount.setVisible(is_split)
        self.split_rate_display.setVisible(is_split)
        self.standby_rate_display.setVisible(is_split)
        self.flat_rate_display.setVisible(is_flat or is_package)
        self.base_charge_display.setVisible("Hourly" in rate_type_text)

    def _update_run_type_details(self, run_type_name: str):
        """Update dynamic fields based on selected run type"""
        # Hide all detail widgets first
        self.airport_details_widget.setVisible(False)
        self.medical_details_widget.setVisible(False)
        self.generic_details_widget.setVisible(False)
        self.run_type_details_container.setVisible(False)

        if not run_type_name or run_type_name.strip() == "":
            return

        # Show appropriate widget based on run type
        if "airport" in run_type_name.lower():
            self.airport_details_widget.setVisible(True)
            self.run_type_details_container.setVisible(True)
            self.run_type_details_container.setTitle("Airport Run Details")
        elif ("medical" in run_type_name.lower()
              or "appointment" in run_type_name.lower()):
            self.medical_details_widget.setVisible(True)
            self.run_type_details_container.setVisible(True)
            self.run_type_details_container.setTitle(
                "Medical Appointment Details")
        else:
            # For other run types, show generic details
            self.generic_details_widget.setVisible(True)
            self.run_type_details_container.setVisible(True)
            self.run_type_details_container.setTitle(
                f"{run_type_name} Details")

    def _search_flight_times(self):
        """Search for flight times (placeholder -
        would integrate with airline APIs)"""
        city = self.airport_city_combo.currentText()

        # Placeholder for flight search - in production would call actual API
        # For now, show a message that this would search for flights
        info = self.flight_info_input.toPlainText()

        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Flight Search",
                                f"Searching for flights to {city}...\n\n"
                                f"Current info:\n{info}\n\n"
                                "Note: Flight search API integration"
                                " would go here.\n"
                                "This would search major airlines and"
                                " show real-time flight information.")

        # In production, this would:
        # 1. Extract flight number or criteria from flight_info_input
        # 2. Call an airline API (Amadeus, Skyscanner, etc.)
        # 3. Populate flight details back into flight_info_input
        # 4. Auto-calculate drive time and update routing

    def search_outlook_emails(self):
        """Search Outlook for recent conversations with customer
        email and copy to dispatch notes"""
        from PyQt6.QtWidgets import (
            QCheckBox,
            QDialog,
            QListWidget,
            QListWidgetItem,)

        # Get customer email from customer widget
        customer_email = ""
        try:
            if hasattr(self, 'customer_widget'):
                # Try to get selected customer's email
                customer_email = (
                    self.customer_widget.email_input.text()
                    if hasattr(self.customer_widget, 'email_input')
                    else "")
        except Exception:
            pass

        if not customer_email:
            # Show dialog to manually enter email
            from PyQt6.QtWidgets import QInputDialog
            customer_email, ok = QInputDialog.getText(
                self, "Email Search",
                "Enter email address to search for:")
            if not ok or not customer_email:
                return

        # Create search dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Outlook Email Search - {customer_email}")
        dialog.setMinimumWidth(800)
        dialog.setMinimumHeight(600)

        layout = QVBoxLayout()

        # Info label
        info_label = QLabel(
            f"Searching Outlook for emails with: <b>{customer_email}</b>")
        layout.addWidget(info_label)

        # Email list with checkboxes
        email_list = QListWidget()
        email_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)

        # Search Outlook
        try:
            emails = self._search_outlook_for_emails(customer_email)

            if not emails:
                QMessageBox.information(
                    self,
                    "No Emails",
                    f"No recent emails found for {customer_email}",
                )
                return

            for email in emails:
                item_text = (
                    f"{email.get('date', '')} | "
                    f"{email.get('subject', '')} | "
                    f"{email.get('from', '')}"
                )
                item = QListWidgetItem(item_text)
                item.setData(
                    Qt.ItemDataRole.UserRole,
                    email)  # Store full email data

                # Highlight payment-related emails
                subject_lower = email.get('subject', '').lower()
                if any(
                    word in subject_lower for word in [
                        'payment',
                        'receipt',
                        'invoice',
                        'paid',
                        'confirmation']):
                    item.setBackground(
                        QBrush(
                            QColor(
                                200,
                                255,
                                200)))  # Light green

                email_list.addItem(item)

        except Exception as e:
            QMessageBox.warning(
                self,
                "Search Error",
                f"Failed to search Outlook: {e}")
            return

        layout.addWidget(email_list)

        # Checkbox for payment receipts
        payment_checkbox = QCheckBox(
            "Mark selected emails as payment receipts (copy to billing)")
        layout.addWidget(payment_checkbox)

        # Buttons
        button_layout = QHBoxLayout()

        copy_btn = QPushButton("📋 Copy Selected to Dispatch Notes")
        copy_btn.clicked.connect(lambda: self._copy_emails_to_dispatch_notes(
            email_list, payment_checkbox.isChecked(), dialog))
        button_layout.addWidget(copy_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)
        dialog.setLayout(layout)
        dialog.exec()

    def _search_outlook_for_emails(self, email_address):
        """Search Outlook for emails with given address"""
        import json
        import subprocess
        import sys
        from pathlib import Path

        # Use extract_outlook_calendar.py with email search capability
        base = Path(__file__).parent.parent
        search_script = base / 'scripts' / 'search_outlook_emails.py'

        # If script doesn't exist, try using win32com directly
        if not search_script.exists():
            return self._search_outlook_direct(email_address)

        # Run search script
        result = subprocess.run(
            [sys.executable, str(search_script), '--email',
                                 email_address, '--limit', '50'],
            capture_output=True, text=True, encoding='utf-8')

        if result.returncode == 0:
            return json.loads(result.stdout)
        else:
            # Fallback to direct search
            return self._search_outlook_direct(email_address)

    def _search_outlook_direct(self, email_address):
        """Direct Outlook search using win32com"""
        try:
            import win32com.client

            outlook = win32com.client.Dispatch("Outlook.Application")
            namespace = outlook.GetNamespace("MAPI")
            inbox = namespace.GetDefaultFolder(6)  # 6 = Inbox
            sent = namespace.GetDefaultFolder(5)   # 5 = Sent Items

            emails = []

            # Search inbox and sent items
            for folder in [inbox, sent]:
                items = folder.Items
                items.Sort("[ReceivedTime]", True)  # Most recent first

                count = 0
                for item in items:
                    try:
                        # Check if email involves the search address
                        if (hasattr(item, 'SenderEmailAddress')
                            and email_address.lower()
                            in item.SenderEmailAddress.lower()) or \
                           (hasattr(item, 'To')
                            and email_address.lower()
                            in item.To.lower()):

                            emails.append(
                                {   'date': (
                                        str(item.ReceivedTime)
                                        if hasattr(item, 'ReceivedTime')
                                        else ''),
                                    'subject': (
                                        item.Subject
                                        if hasattr(item, 'Subject')
                                        else ''),
                                    'from': (
                                        item.SenderEmailAddress
                                        if hasattr(item, 'SenderEmailAddress')
                                        else ''),
                                    'body': (
                                        item.Body
                                        if hasattr(item, 'Body')
                                        else ''),
                                    'to': (
                                        item.To
                                        if hasattr(item, 'To')
                                        else '')})

                            count += 1
                            if count >= 25:  # Limit per folder
                                break
                    except Exception:
                        continue

            return emails[:50]  # Return max 50 most recent

        except Exception as e:
            print(f"Outlook search error: {e}")
            return []

    def _copy_emails_to_dispatch_notes(
            self, email_list, mark_as_payment, dialog):
        """Copy selected emails to dispatch notes"""
        selected_items = email_list.selectedItems()

        if not selected_items:
            QMessageBox.information(
                dialog,
                "No Selection",
                "Please select at least one email.")
            return

        # Build text from selected emails
        email_text = "\n" + "=" * 80 + "\n"
        current_date = QDate.currentDate().toString('yyyy-MM-dd')
        email_text += f"OUTLOOK EMAILS (Copied {current_date})\n"
        email_text += "=" * 80 + "\n\n"

        for item in selected_items:
            email_data = item.data(Qt.ItemDataRole.UserRole)
            email_text += f"Date: {email_data.get('date', '')}\n"
            email_text += f"From: {email_data.get('from', '')}\n"
            email_text += f"To: {email_data.get('to', '')}\n"
            email_text += f"Subject: {email_data.get('subject', '')}\n"
            email_text += f"\n{email_data.get('body', '')}\n"
            email_text += "\n" + "-" * 80 + "\n\n"

            # If marked as payment receipt, note it
            if mark_as_payment:
                email_text += "[PAYMENT RECEIPT - Copy to billing records]\n\n"

        # Append to dispatch notes
        current_notes = self.dispatch_notes_input.toPlainText()
        if current_notes:
            self.dispatch_notes_input.setPlainText(
                current_notes + "\n" + email_text)
        else:
            self.dispatch_notes_input.setPlainText(email_text)

        # Show success message
        count = len(selected_items)
        payment_note = (
            " (marked as payment receipts)"
            if mark_as_payment else "")
        QMessageBox.information(
            dialog, "Emails Copied",
            f"Copied {count} email(s) to dispatch notes{payment_note}.")

        dialog.accept()

    def toggle_lock(self):
        """Lock/unlock the charter form to prevent edits"""
        is_locked = self.lock_btn.isChecked()

        interactive_types = (
            QLineEdit,
            QTextEdit,
            QComboBox,
            QSpinBox,
            QDoubleSpinBox,
            QDateEdit,
            QTimeEdit,
            QCheckBox,
            QRadioButton,
            QTableWidget,
            QPushButton,
        )
        keep_enabled = {
            self.lock_btn,
            self.cancel_btn,
            self.close_btn,
        }

        if is_locked:
            self.lock_btn.setText("🔓 Unlock")
            self._lock_prev_enabled_states = []
            for widget in self.findChildren(QWidget):
                if widget in keep_enabled:
                    continue
                if isinstance(widget, interactive_types):
                    self._lock_prev_enabled_states.append(
                        (widget, widget.isEnabled())
                    )
                    widget.setEnabled(False)

            # Keep primary control buttons clickable while locked.
            self.lock_btn.setEnabled(True)
            self.cancel_btn.setEnabled(True)
            self.close_btn.setEnabled(True)
            QMessageBox.information(
                self,
                "Charter Locked",
                (
                    "This charter is now locked and cannot be edited.\n"
                    "Click Unlock to make changes."
                ),
            )
        else:
            self.lock_btn.setText("🔒 Lock")
            for widget, was_enabled in getattr(
                self,
                "_lock_prev_enabled_states",
                [],
            ):
                try:
                    widget.setEnabled(bool(was_enabled))
                except Exception:
                    continue
            self._lock_prev_enabled_states = []

            self.lock_btn.setEnabled(True)
            self.cancel_btn.setEnabled(True)
            self.close_btn.setEnabled(True)
            QMessageBox.information(
                self,
                "Charter Unlocked",
                "This charter is now unlocked and can be edited.",
            )

    def cancel_charter(self):
        """Cancel the charter and discard unsaved changes"""
        reply = QMessageBox.question(
            self,
            "Cancel Charter",
            "Are you sure you want to cancel this charter?\nAll unsaved "
            "changes will be lost.",
            ((QMessageBox.StandardButton.Yes
             | QMessageBox.StandardButton.No)),
            QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            # Reset form to blank state
            self.charter_id = None
            self.customer_widget.clear()
            # Clear all fields...
            QMessageBox.information(
                self,
                "Charter Cancelled",
                "Charter has been cancelled.")

    def close_charter_form(self):
        """Close the charter form"""
        reply = QMessageBox.question(
            self,
            "Close Charter",
            "Close this charter form?\nMake sure to save any changes first.",
            ((QMessageBox.StandardButton.Yes
             | QMessageBox.StandardButton.No)),
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.close()

    def show_link_charter_dialog(self):
        """Show dialog to link a new or existing charter"""
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox

        dialog = QDialog(self)
        dialog.setWindowTitle("Link Charter")
        dialog.setMinimumWidth(500)

        layout = QVBoxLayout()

        # Choice: New or Existing
        choice_group = QGroupBox("Link Type")
        choice_layout = QVBoxLayout()

        from PyQt6.QtWidgets import QButtonGroup, QRadioButton
        choice_button_group = QButtonGroup(dialog)

        new_radio = QRadioButton("Create New Linked Charter (Copy & Edit)")
        existing_radio = QRadioButton("Link to Existing Charter")

        choice_button_group.addButton(new_radio, 1)
        choice_button_group.addButton(existing_radio, 2)
        new_radio.setChecked(True)

        choice_layout.addWidget(new_radio)
        choice_layout.addWidget(existing_radio)
        choice_group.setLayout(choice_layout)
        layout.addWidget(choice_group)

        # New charter section
        new_section = QGroupBox("New Charter Details")
        new_layout = QVBoxLayout()
        new_info = QLabel(
            "This will save the current charter and create a copy for editing."
            "\n"
            "You can modify dates, times, and routing for the linked charter.")
        new_info.setWordWrap(True)
        new_layout.addWidget(new_info)
        new_section.setLayout(new_layout)
        layout.addWidget(new_section)

        # Existing charter section
        existing_section = QGroupBox("Select Existing Charter")
        existing_layout = QVBoxLayout()

        # Get client's other charters
        client_charters_combo = QComboBox()
        client_charters_combo.setEditable(True)
        client_charters_combo.setPlaceholderText(
            "Enter reserve number or select from list...")

        # Load client's charters if we have a client selected
        try:
            client_id = self.customer_widget.get_selected_client_id()
            if client_id:
                cur = self.db.get_cursor()
                cur.execute("""
                    SELECT reserve_number, charter_date, total_amount_due
                    FROM charters
                    WHERE client_id = %s
                    ORDER BY charter_date DESC
                    LIMIT 50
                """, (client_id,))

                for reserve_num, charter_date, amount in cur.fetchall():
                    date_str = charter_date.strftime(
                        "%Y-%m-%d") if charter_date else "No date"
                    label = f"{reserve_num} - {date_str} (${amount:,.2f})"
                    client_charters_combo.addItem(label, reserve_num)
                cur.close()
        except Exception as e:
            print(f"Error loading client charters: {e}")

        existing_layout.addWidget(QLabel("Client's Charters:"))
        existing_layout.addWidget(client_charters_combo)
        existing_section.setLayout(existing_layout)
        layout.addWidget(existing_section)

        # Toggle visibility based on selection
        def toggle_sections():
            is_new = new_radio.isChecked()
            new_section.setVisible(is_new)
            existing_section.setVisible(not is_new)

        new_radio.toggled.connect(toggle_sections)
        toggle_sections()

        # Dialog buttons
        button_box = QDialogButtonBox(
            (QDialogButtonBox.StandardButton.Ok
             | QDialogButtonBox.StandardButton.Cancel)
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        dialog.setLayout(layout)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            if new_radio.isChecked():
                self._create_linked_charter_copy()
            else:
                # Link to existing
                selected_text = client_charters_combo.currentText()
                if client_charters_combo.currentData():
                    reserve_num = client_charters_combo.currentData()
                else:
                    # Extract reserve number from manual entry
                    reserve_num = selected_text.split(
                        " - ")[0] if " - " in selected_text else selected_text

                if reserve_num:
                    self._link_to_existing_charter(reserve_num)

    def _create_linked_charter_copy(self):
        """Create a copy of current charter for linked charter"""
        # First save current charter
        if not self.charter_id:
            self.save_charter()

        if not self.charter_id:
            QMessageBox.warning(
                self,
                "Save First",
                "Please save the current charter before creating a link.")
            return

        # Create a new charter window with copied data
        QMessageBox.information(
            self,
            "Create Linked Charter",
            "A copy of this charter will be created.\n"
            "You can modify it and save as a new linked charter.",
        )

        # In production, this would:
        # 1. Open a new CharterFormWidget
        # 2. Copy all current data to it
        # 3. Clear the new charter ID
        # 4. Set linked_charter_combo to current charter's reserve_number
        # 5. Allow user to modify and save

    def _link_to_existing_charter(self, reserve_number: str):
        """Link current charter to an existing charter"""
        # Add to linked charter combo
        self.linked_charter_combo.addItem(reserve_number)
        self.linked_charter_combo.setCurrentText(reserve_number)

        QMessageBox.information(
            self,
            "Charter Linked",
            f"Charter {reserve_number} has been linked to this charter.",
        )

    def create_dispatch_section(self) -> QGroupBox:
        """DEPRECATED: Dispatch now embedded in charter details section"""
        # Return empty widget to avoid breaking existing code
        return QGroupBox()

    def handle_out_of_town_routing(self, checked: bool):
        """Toggle parent row labels between Pickup/Drop-off and Leave Red
        Deer/Return to Red Deer"""
        # Update PARENT 1 (row 0) label
        parent1_item = self.route_table.item(0, 0)
        if parent1_item:
            if checked:
                parent1_item.setText("Leave Red Deer for")
                parent1_item.setData(
                    Qt.ItemDataRole.UserRole,
                    "depart_red_deer",
                )
            else:
                parent1_item.setText("Pickup at")
                parent1_item.setData(
                    Qt.ItemDataRole.UserRole,
                    "pickup_client",
                )

        # Update PARENT 2 (last row) label
        last_row = self.route_table.rowCount() - 1
        parent2_item = self.route_table.item(last_row, 0)
        if parent2_item:
            if checked:
                parent2_item.setText("Return to Red Deer")
                parent2_item.setData(
                    Qt.ItemDataRole.UserRole,
                    "return_red_deer",
                )
            else:
                parent2_item.setText("Drop off at")
                parent2_item.setData(
                    Qt.ItemDataRole.UserRole, "dropoff_client")

        # Recalculate billing when toggle changes
        self.calculate_route_billing()

    def add_default_routing_events(self):
        """Add default Pickup Client and Drop-off Client routing events on
        initialization"""
        from PyQt6.QtWidgets import QTimeEdit

        # Row 0: Pickup Client event (STATIC LABEL - toggles between "Pickup
        # Client" and "Depart Red Deer for")
        pickup_row = self.route_table.rowCount()
        self.route_table.insertRow(pickup_row)

        # Column 0: Static label for Pickup (stored as data-attribute for
        # toggle)
        start_label = QTableWidgetItem("Pickup Client")
        start_label.setFlags(start_label.flags() & ~Qt.ItemFlag.ItemIsEditable)
        start_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        start_label.setData(
            Qt.ItemDataRole.UserRole,
            "pickup_client")  # Store event type
        self.route_table.setItem(pickup_row, 0, start_label)

        # Column 1: Details (empty)
        self.route_table.setItem(pickup_row, 1, QTableWidgetItem(""))

        # Column 2: at/by dropdown
        at_by_combo_pu = QComboBox()
        at_by_combo_pu.addItems(["at", "by"])
        self.route_table.setCellWidget(pickup_row, 2, at_by_combo_pu)

        # Column 3: Time (Pickup time, editable)
        time_edit = QTimeEdit()
        time_edit.setDisplayFormat("HH:mm")
        time_edit.setTime(self.pickup_datetime.time())
        # Trigger billing recalculation when time changes.
        time_edit.timeChanged.connect(
            lambda *_: self.calculate_route_billing()
        )
        self.route_table.setCellWidget(pickup_row, 3, time_edit)

        # Column 4: Driver Comments (empty)
        self.route_table.setItem(pickup_row, 4, QTableWidgetItem(""))

        # Row N: Drop-off Client event (STATIC LABEL - toggles between
        # "Drop-off Client" and "Return to Red Deer")
        dropoff_row = self.route_table.rowCount()
        self.route_table.insertRow(dropoff_row)

        # Column 0: Static label for Drop-off (stored as data-attribute for
        # toggle)
        finish_label = QTableWidgetItem("Drop-off Client")
        finish_label.setFlags(finish_label.flags() & ~
                              Qt.ItemFlag.ItemIsEditable)
        finish_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        finish_label.setData(
            Qt.ItemDataRole.UserRole,
            "dropoff_client")  # Store event type
        self.route_table.setItem(dropoff_row, 0, finish_label)

        # Column 1: Details (empty)
        self.route_table.setItem(dropoff_row, 1, QTableWidgetItem(""))

        # Column 2: at/by dropdown
        at_by_combo_do = QComboBox()
        at_by_combo_do.addItems(["at", "by"])
        self.route_table.setCellWidget(dropoff_row, 2, at_by_combo_do)

        # Column 3: Time (Drop-off time, editable)
        time_edit = QTimeEdit()
        time_edit.setDisplayFormat("HH:mm")
        time_edit.setTime(self.dropoff_datetime.time())
        # Trigger billing recalculation when time changes.
        time_edit.timeChanged.connect(
            lambda *_: self.calculate_route_billing()
        )
        self.route_table.setCellWidget(dropoff_row, 3, time_edit)

        # Column 4: Driver Comments (empty)
        self.route_table.setItem(dropoff_row, 4, QTableWidgetItem(""))

    def create_charges_section(self) -> QGroupBox:
        """Invoicing & Charges section with line-item table for Charter Charge,
        Gratuity, and Extra Charges"""
        charges_group = QGroupBox("Invoicing & Charges (GST-Included)")
        charges_layout = QVBoxLayout()

        # === CHARGES TABLE (LINE ITEMS) ===
        charges_header = QHBoxLayout()
        charges_header.addWidget(QLabel("<b>Charges & Line Items</b>"))

        add_charge_btn = QPushButton("➕ Add Charge")
        add_charge_btn.setMaximumWidth(140)
        add_charge_btn.clicked.connect(self.add_charge_dialog)
        charges_header.addWidget(add_charge_btn)

        delete_charge_btn = QPushButton("❌ Delete Selected")
        delete_charge_btn.setMaximumWidth(140)
        delete_charge_btn.clicked.connect(self.delete_selected_charge)
        charges_header.addWidget(delete_charge_btn)

        edit_charge_btn = QPushButton("✏️ Edit Defaults")
        edit_charge_btn.setMaximumWidth(140)
        edit_charge_btn.clicked.connect(self.open_charge_defaults_dialog)
        charges_header.addWidget(edit_charge_btn)

        charges_header.addStretch()
        charges_layout.addLayout(charges_header)

        # Charges table: Description | Type | Total (GST-included)
        self.charges_table = QTableWidget()
        self.charges_table.setColumnCount(3)
        self.charges_table.setHorizontalHeaderLabels(
            ["Description", "Type", "Total"])
        self.charges_table.setMinimumHeight(220)
        self.charges_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self.charges_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection)
        self.charges_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)  # Description
        self.charges_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents)  # Type
        self.charges_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Fixed)  # Total
        self.charges_table.setColumnWidth(0, 350)
        self.charges_table.setColumnWidth(1, 110)
        self.charges_table.setColumnWidth(2, 120)

        # Connect cell changes to recalculate totals
        self.charges_table.cellChanged.connect(self.recalculate_totals)
        charges_layout.addWidget(self.charges_table)

        # Initialize default charges (will be auto-populated on routing/load)
        self.charges_table.setRowCount(0)

        # Initialize Gratuity line on form load (pre-checked by default)
        try:
            if (
                hasattr(self, 'gratuity_checkbox')
                and self.gratuity_checkbox.isChecked()
            ):
                gratuity_percent = self.gratuity_percent_input.value(
                ) if hasattr(self, 'gratuity_percent_input') else 18.0
                self.add_charge_line(
                    description=f"Gratuity ({gratuity_percent}%)",
                    calc_type="Percent",
                    value=gratuity_percent)
        except Exception:
            pass  # Gratuity line will be added when pricing is available

        # === SUBTOTAL & GST ===
        summary_layout = QFormLayout()
        self.subtotal_display = QLabel("$0.00")
        self.subtotal_display.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        summary_layout.addRow("Subtotal:", self.subtotal_display)

        gst_checkbox_layout = QHBoxLayout()
        self.gst_exempt_checkbox = QCheckBox("GST Exempt")
        self.gst_exempt_checkbox.stateChanged.connect(self.recalculate_totals)
        gst_checkbox_layout.addWidget(self.gst_exempt_checkbox)
        gst_checkbox_layout.addStretch()
        summary_layout.addRow("", gst_checkbox_layout)

        self.gst_total_display = QLabel("$0.00")
        self.gst_total_display.setStyleSheet("color: #D32F2F;")
        summary_layout.addRow("GST (5%):", self.gst_total_display)

        self.gross_total_display = QLabel("$0.00")
        self.gross_total_display.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.gross_total_display.setStyleSheet("color: #1565C0;")
        summary_layout.addRow("Grand Total:", self.gross_total_display)
        charges_layout.addLayout(summary_layout)

        # === BEVERAGE CART (SEPARATE INVOICE) ===
        beverage_separator = QFrame()
        beverage_separator.setFrameShape(QFrame.Shape.HLine)
        charges_layout.addWidget(beverage_separator)

        beverage_header = QHBoxLayout()
        beverage_header.addWidget(
            QLabel("<b>🍷 Beverage Cart</b>"))

        add_beverage_btn = QPushButton("➕ Add/Amend Beverage Order")
        add_beverage_btn.setMaximumWidth(200)
        add_beverage_btn.clicked.connect(self.open_beverage_lookup)
        beverage_header.addWidget(add_beverage_btn)

        delete_beverage_btn = QPushButton("❌ Delete Selected")
        delete_beverage_btn.setMaximumWidth(140)
        delete_beverage_btn.clicked.connect(self.delete_selected_beverage)
        beverage_header.addWidget(delete_beverage_btn)

        beverage_header.addStretch()

        self.separate_beverage_checkbox = QCheckBox("Beverages Separate (not on charter invoice)")
        self.separate_beverage_checkbox.stateChanged.connect(
            self.on_separate_beverage_toggled)
        beverage_header.addWidget(self.separate_beverage_checkbox)

        charges_layout.addLayout(beverage_header)

        # Beverage items table: Item | Qty | Unit Price | Total
        self.beverage_table = QTableWidget()
        self.beverage_table.setColumnCount(4)
        self.beverage_table.setHorizontalHeaderLabels(
            ["Item", "Qty", "Unit Price", "Total"])
        self.beverage_table.setMinimumHeight(100)
        self.beverage_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self.beverage_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection)
        self.beverage_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)  # Item
        self.beverage_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents)  # Qty
        self.beverage_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents)  # Unit Price
        self.beverage_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Fixed)  # Total
        self.beverage_table.setColumnWidth(1, 50)
        self.beverage_table.setColumnWidth(2, 90)
        self.beverage_table.setColumnWidth(3, 90)

        # Connect changes to recalculate beverage totals
        self.beverage_table.cellChanged.connect(
            self.recalculate_beverage_totals)
        charges_layout.addWidget(self.beverage_table)

        # Beverage totals
        beverage_summary = QFormLayout()
        self.beverage_subtotal = QLabel("$0.00")
        self.beverage_subtotal.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        beverage_summary.addRow("Beverage Subtotal:", self.beverage_subtotal)

        self.beverage_gst = QLabel("$0.00")
        self.beverage_gst.setStyleSheet("color: #D32F2F;")
        beverage_summary.addRow("Beverage GST (5%):", self.beverage_gst)

        self.beverage_total = QLabel("$0.00")
        self.beverage_total.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.beverage_total.setStyleSheet(
            "color: #2E7D32; background-color: #F1F8E9; padding: 4px;")
        beverage_summary.addRow("Beverage Invoice Total:", self.beverage_total)
        charges_layout.addLayout(beverage_summary)

        # === PAYMENT TRACKING ===
        payment_header = QHBoxLayout()
        payment_header.addWidget(QLabel("<b>Payments Received</b>"))
        self.add_payment_btn = QPushButton("➕ Add Payment")
        self.add_payment_btn.setMaximumWidth(120)
        self.add_payment_btn.clicked.connect(self.add_payment_row)
        self.add_payment_btn.setEnabled(False)
        payment_header.addWidget(self.add_payment_btn)

        self.delete_payment_btn = QPushButton("❌ Delete Payment")
        self.delete_payment_btn.setMaximumWidth(130)
        self.delete_payment_btn.clicked.connect(self.delete_selected_payment)
        self.delete_payment_btn.setEnabled(False)
        payment_header.addWidget(self.delete_payment_btn)

        self.edit_payment_btn = QPushButton("✏️ Edit Payment")
        self.edit_payment_btn.setMaximumWidth(120)
        self.edit_payment_btn.setCheckable(True)
        self.edit_payment_btn.clicked.connect(self.toggle_payment_edit)
        payment_header.addWidget(self.edit_payment_btn)
        payment_header.addStretch()
        charges_layout.addLayout(payment_header)

        sent_layout = QHBoxLayout()
        sent_layout.addWidget(QLabel("<b>Delivery Tracking:</b>"))

        self.charter_sent_checkbox = QCheckBox("Charter Sent")
        self.charter_sent_checkbox.toggled.connect(
            lambda checked: self.charter_sent_date.setEnabled(checked)
        )
        sent_layout.addWidget(self.charter_sent_checkbox)

        self.charter_sent_date = QDateEdit()
        self.charter_sent_date.setCalendarPopup(True)
        self.charter_sent_date.setDate(QDate.currentDate())
        self.charter_sent_date.setMaximumWidth(130)
        self.charter_sent_date.setEnabled(False)
        sent_layout.addWidget(self.charter_sent_date)

        self.invoice_sent_checkbox = QCheckBox("Invoice Sent")
        self.invoice_sent_checkbox.toggled.connect(
            lambda checked: self.invoice_sent_date.setEnabled(checked)
        )
        sent_layout.addWidget(self.invoice_sent_checkbox)

        self.invoice_sent_date = QDateEdit()
        self.invoice_sent_date.setCalendarPopup(True)
        self.invoice_sent_date.setDate(QDate.currentDate())
        self.invoice_sent_date.setMaximumWidth(130)
        self.invoice_sent_date.setEnabled(False)
        sent_layout.addWidget(self.invoice_sent_date)

        mark_today_btn = QPushButton("Mark Invoice Sent Today")
        mark_today_btn.setMaximumWidth(200)
        mark_today_btn.clicked.connect(self._mark_invoice_sent_today)
        sent_layout.addWidget(mark_today_btn)

        sent_layout.addStretch()
        charges_layout.addLayout(sent_layout)

        self.payments_table = QTableWidget()
        self.payments_table.setColumnCount(6)
        self.payments_table.setHorizontalHeaderLabels(
            ["Type", "Date Paid", "Amount", "Method", "Notes", "GL Code"])
        self.payments_table.setMinimumHeight(80)
        self.payments_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.payments_table.setEnabled(False)  # Read-only by default
        self._loading_payments = False
        self._payments_dirty = False
        self.payments_table.itemChanged.connect(
            self._on_payments_table_item_changed
        )
        charges_layout.addWidget(self.payments_table)

        # === NRR (Non-Refundable Retainer) ===
        nrr_layout = QHBoxLayout()
        nrr_layout.addWidget(QLabel("NRR Received:"))
        self.nrr_received = QDoubleSpinBox()
        self.nrr_received.setMaximum(99999.99)
        self.nrr_received.setDecimals(2)
        self.nrr_received.setPrefix("$")
        self.nrr_received.setMaximumWidth(120)
        self.nrr_received.valueChanged.connect(self._on_nrr_received)
        nrr_layout.addWidget(self.nrr_received)
        nrr_layout.addWidget(
            QLabel("(Escrow hold if cancelled - separate from deposits)"))
        nrr_layout.addStretch()
        charges_layout.addLayout(nrr_layout)

        # === CLIENT CC INFO (Non-printable) ===
        cc_layout = QFormLayout()
        self.client_cc_checkbox = QCheckBox("Client Provided CC on File")
        self.client_cc_checkbox.stateChanged.connect(
            self._on_cc_checkbox_changed)
        cc_layout.addRow(self.client_cc_checkbox)

        # Full CC info (only visible before save)
        self.client_cc_full = QLineEdit()
        self.client_cc_full.setPlaceholderText(
            "Full card number (VISA/MC/AMEX) - hidden after save")
        self.client_cc_full.setMaximumWidth(250)
        self.client_cc_full.setEnabled(False)
        self.client_cc_full.setEchoMode(
            QLineEdit.EchoMode.Password)  # Masked input
        cc_layout.addRow("Full CC#:", self.client_cc_full)

        # Last 4 only (visible always, editable before save)
        self.client_cc_last4 = QLineEdit()
        self.client_cc_last4.setPlaceholderText(
            "Last 4 digits (stored, visible after save)")
        self.client_cc_last4.setMaximumWidth(100)
        self.client_cc_last4.setEnabled(False)
        self.client_cc_last4.setMaxLength(4)
        cc_layout.addRow("CC Last 4:", self.client_cc_last4)

        charges_layout.addLayout(cc_layout)

        charges_group.setLayout(charges_layout)
        return charges_group

    def create_notes_section(self) -> QGroupBox:
        """Beverage Notes section with itemized beverage list"""
        notes_group = QGroupBox("Beverage Notes")
        notes_layout = QVBoxLayout()

        # No free-form notes text field; only show the ordered items list
        self.beverage_notes_field = None
        notes_layout.addSpacing(4)

        # Beverages ordered label
        beverages_label = QLabel("Beverages Ordered:")
        beverages_label.setStyleSheet("font-weight: bold; font-size: 10px;")
        notes_layout.addWidget(beverages_label)

        # Itemized beverages list (vertical)
        self.beverages_list_widget = QListWidget()
        self.beverages_list_widget.setMaximumHeight(120)
        self.beverages_list_widget.setSpacing(2)
        self.beverages_list_widget.setFont(QFont("Arial", 8))  # Smaller font
        notes_layout.addWidget(self.beverages_list_widget)

        notes_group.setLayout(notes_layout)
        return notes_group

    def _init_default_charges(self):
        """Initialize default charges (legacy, use auto-populate instead)."""
        self.charges_table.setRowCount(0)

    def add_charge_dialog(self):
        """Dialog to add a charge line - pulls from stored charge defaults."""
        print("🔵 add_charge_dialog() called")
        try:
            dialog = QDialog(self)
            dialog.setWindowTitle("Add Charge")
            dialog.setGeometry(100, 100, 500, 300)

            layout = QVBoxLayout()

            # Initialize defaults if not present
            if not hasattr(self, '_charge_defaults'):
                self._charge_defaults = [
                    ("Charter Charge", "Fixed", "0.00"),
                    ("Gratuity", "18%", "0.00"),
                    ("Spill Charge", "Fixed", "250.00"),
                    ("Extra Stop", "Fixed", "0.00"),
                    ("Wait Time", "Hourly", "0.00"),
                    ("Airport Fee", "Fixed", "0.00"),
                    ("Parking Fee", "Fixed", "0.00"),
                    ("Tolls", "Fixed", "0.00"),]

            # Description dropdown (from defaults)
            type_label = QLabel("Charge Name:")
            type_combo = QComboBox()
            charge_names = [name for name, _, _ in self._charge_defaults]
            type_combo.addItems(charge_names)
            layout.addWidget(type_label)
            layout.addWidget(type_combo)

            # Type label (read-only, auto-filled from defaults)
            calc_label = QLabel("Type:")
            calc_display = QLineEdit()
            calc_display.setReadOnly(True)
            layout.addWidget(calc_label)
            layout.addWidget(calc_display)

            # Amount input (auto-filled from defaults, user can edit)
            amount_label = QLabel("Amount:")
            amount_input = QDoubleSpinBox()
            amount_input.setMaximum(99999.99)
            amount_input.setDecimals(2)
            layout.addWidget(amount_label)
            layout.addWidget(amount_input)

            # Connect description change to auto-fill type and amount
            def on_description_changed(text):
                for name, type_val, default_amount in self._charge_defaults:
                    if name == text:
                        calc_display.setText(type_val)
                        amount_input.setValue(float(default_amount))
                        break

            type_combo.currentTextChanged.connect(on_description_changed)

            # Initialize with first preset
            on_description_changed(type_combo.currentText())

            # Buttons
            button_layout = QHBoxLayout()
            ok_btn = QPushButton("✅ Add Charge")
            cancel_btn = QPushButton("❌ Cancel")
            button_layout.addWidget(ok_btn)
            button_layout.addWidget(cancel_btn)
            layout.addLayout(button_layout)

            dialog.setLayout(layout)

            def add_charge():
                print(
                    "✅ add_charge() called - Adding: "
                    f"{type_combo.currentText()}"
                )
                try:
                    # Hard-code the values when added (snapshot, not linked to
                    # defaults)
                    self.add_charge_line(
                        description=type_combo.currentText(),
                        calc_type=calc_display.text(),
                        value=amount_input.value(),)
                    print("✅ Charge line added successfully")
                    dialog.accept()
                except Exception as e:
                    print(f"❌ Error adding charge: {e}")
                    import traceback
                    traceback.print_exc()
                    QMessageBox.critical(
                        self, "Error", f"Failed to add charge: {e}")

            ok_btn.clicked.connect(add_charge)
            cancel_btn.clicked.connect(dialog.reject)

            print("🔵 Showing dialog...")
            dialog.exec()
            print("🔵 Dialog closed")
        except Exception as e:
            print(f"❌ Error in add_charge_dialog: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(
                self, "Error", f"Failed to open add charge dialog: {e}")

    def delete_selected_charge(self):
        """Delete the selected charge row"""
        current_row = self.charges_table.currentRow()
        if current_row >= 0:
            self.charges_table.removeRow(current_row)
            self.recalculate_totals()

    def open_charge_defaults_dialog(self):
        """Open dialog to manage charge defaults (Name | Type % | Default
        Amount)"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Manage Charge Defaults")
        dialog.setGeometry(100, 100, 700, 450)

        layout = QVBoxLayout()

        label = QLabel(
            "<b>Default Charge Templates (Name | Type | Default Amount)</b>")
        layout.addWidget(label)

        # Table: Name | Type (%) | Default Amount
        defaults_table = QTableWidget()
        defaults_table.setColumnCount(3)
        defaults_table.setHorizontalHeaderLabels(
            ["Charge Name", "Type (%)", "Default Amount"])
        defaults_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        defaults_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents)
        defaults_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents)
        defaults_table.setColumnWidth(1, 80)
        defaults_table.setColumnWidth(2, 120)

        # Store defaults in instance for reference
        if not hasattr(self, '_charge_defaults'):
            self._charge_defaults = [
                ("Charter Charge", "Fixed", "0.00"),
                ("Gratuity", "18%", "0.00"),
                ("Spill Charge", "Fixed", "250.00"),
                ("Extra Stop", "Fixed", "0.00"),
                ("Wait Time", "Hourly", "0.00"),
                ("Airport Fee", "Fixed", "0.00"),
                ("Parking Fee", "Fixed", "0.00"),
                ("Tolls", "Fixed", "0.00"),]

        # Populate table with stored defaults
        for name, type_val, amount in self._charge_defaults:
            row = defaults_table.rowCount()
            defaults_table.insertRow(row)
            defaults_table.setItem(row, 0, QTableWidgetItem(name))
            type_item = QTableWidgetItem(type_val)
            type_item.setFlags(
                type_item.flags() | Qt.ItemFlag.ItemIsEditable)
            defaults_table.setItem(row, 1, type_item)
            amount_item = QTableWidgetItem(amount)
            amount_item.setFlags(
                amount_item.flags() | Qt.ItemFlag.ItemIsEditable)
            defaults_table.setItem(row, 2, amount_item)

        layout.addWidget(defaults_table)

        # Add/Delete buttons
        button_row = QHBoxLayout()
        add_default_btn = QPushButton("➕ Add Default")
        add_default_btn.clicked.connect(
            lambda: self._add_default_charge_row(defaults_table))
        button_row.addWidget(add_default_btn)

        delete_default_btn = QPushButton("❌ Delete Selected")
        delete_default_btn.clicked.connect(
            lambda: self._delete_default_charge_row(defaults_table))
        button_row.addWidget(delete_default_btn)
        button_row.addStretch()
        layout.addLayout(button_row)

        info_label = QLabel(
            "💡 Edit charge names, types, and default amounts. "
            "These will appear in 'Add Charge' dropdown."
        )
        info_label.setStyleSheet("color: #555; font-size: 10px;")
        layout.addWidget(info_label)

        dialog_buttons = QHBoxLayout()
        save_btn = QPushButton("💾 Save Defaults")
        close_btn = QPushButton("Close")
        dialog_buttons.addWidget(save_btn)
        dialog_buttons.addWidget(close_btn)
        layout.addLayout(dialog_buttons)

        dialog.setLayout(layout)

        save_btn.clicked.connect(
            lambda: self._save_charge_defaults(
                defaults_table, dialog))
        close_btn.clicked.connect(dialog.reject)

        dialog.exec()

    def _add_default_charge_row(self, table: QTableWidget):
        """Add a new charge default row"""
        row = table.rowCount()
        table.insertRow(row)
        table.setItem(row, 0, QTableWidgetItem("New Charge"))
        table.setItem(row, 1, QTableWidgetItem("Fixed"))
        table.setItem(row, 2, QTableWidgetItem("0.00"))

    def _delete_default_charge_row(self, table: QTableWidget):
        """Delete selected default charge row"""
        current_row = table.currentRow()
        if current_row >= 0:
            table.removeRow(current_row)

    def _save_charge_defaults(self, defaults_table, dialog):
        """Save charge defaults to instance variable"""
        try:
            self._charge_defaults = []
            for row in range(defaults_table.rowCount()):
                name = defaults_table.item(row, 0).text()
                type_val = defaults_table.item(row, 1).text()
                amount = defaults_table.item(row, 2).text()
                self._charge_defaults.append((name, type_val, amount))

            QMessageBox.information(self, "Success", "Charge defaults saved.")
            dialog.accept()
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to save defaults: {e}")

    def create_driver_vehicle_ops_tab(self) -> QWidget:
        """Create Driver & Vehicle Operations tab with all right-column
        sections"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        ops_container = QWidget()
        ops_layout = QVBoxLayout()
        ops_layout.setSpacing(6)
        ops_layout.setContentsMargins(8, 8, 8, 8)
        top_row_layout = QHBoxLayout()
        top_row_layout.setSpacing(8)
        top_row_layout.setContentsMargins(0, 0, 0, 0)

        # === DRIVER INFO & DUTY LOG ===
        driver_info_group = QGroupBox("Driver Information")
        driver_info_group.setMaximumHeight(150)
        driver_info_group.setMaximumWidth(280)
        driver_info_group.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed)
        driver_info_layout = QVBoxLayout()
        driver_info_layout.setSpacing(4)

        # Driver name (read-only, syncs from dispatch)
        driver_name_row = QHBoxLayout()
        driver_name_row.addWidget(QLabel("<b>Driver:</b>"))
        self.driver_info_name_label = QLabel("(Not assigned)")
        self.driver_info_name_label.setStyleSheet("color: #555;")
        driver_name_row.addWidget(self.driver_info_name_label)
        driver_name_row.addStretch()
        driver_info_layout.addLayout(driver_name_row)

        # Work shift duty log
        duty_log_label = QLabel("<b>Work Shift Duty Log:</b>")
        driver_info_layout.addWidget(duty_log_label)

        on_duty_row = QHBoxLayout()
        on_duty_row.addWidget(QLabel("On Duty:"))
        self.on_duty_time_input = QLineEdit()
        self.on_duty_time_input.setPlaceholderText("HH:MM")
        self.on_duty_time_input.setMaximumWidth(80)
        on_duty_row.addWidget(self.on_duty_time_input)
        on_duty_row.addStretch()
        driver_info_layout.addLayout(on_duty_row)

        off_duty_row = QHBoxLayout()
        off_duty_row.addWidget(QLabel("Off Duty:"))
        self.off_duty_time_input = QLineEdit()
        self.off_duty_time_input.setPlaceholderText("HH:MM")
        self.off_duty_time_input.setMaximumWidth(80)
        off_duty_row.addWidget(self.off_duty_time_input)
        off_duty_row.addStretch()
        driver_info_layout.addLayout(off_duty_row)

        # Button to add duty status change
        add_duty_btn = QPushButton("+ Add Duty Status Change")
        add_duty_btn.setMaximumWidth(200)
        driver_info_layout.addWidget(add_duty_btn)

        driver_info_group.setLayout(driver_info_layout)
        top_row_layout.addWidget(driver_info_group)

        # === 14-DAY HOS TRACKING ===
        hos_group = QGroupBox(
            "Hours of Service (Last 14 Days) - Duty Status Log")
        hos_group.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred)
        hos_group.setMinimumHeight(280)
        hos_layout = QVBoxLayout()
        hos_layout.setContentsMargins(10, 10, 10, 10)
        hos_layout.setSpacing(6)

        # Month/Year/Cycle selector
        hos_header = QHBoxLayout()
        hos_header.addWidget(QLabel("<b>Month:</b>"))
        self.hos_month_combo = QComboBox()
        self.hos_month_combo.addItems(["January",
                                       "February",
                                       "March",
                                       "April",
                                       "May",
                                       "June",
                                       "July",
                                       "August",
                                       "September",
                                       "October",
                                       "November",
                                       "December"])
        self.hos_month_combo.setMaximumWidth(100)
        hos_header.addWidget(self.hos_month_combo)
        hos_header.addWidget(QLabel("<b>Year:</b>"))
        self.hos_year_input = QLineEdit("2026")
        self.hos_year_input.setMaximumWidth(50)
        hos_header.addWidget(self.hos_year_input)
        hos_header.addStretch()
        hos_layout.addLayout(hos_header)

        # HOS Grid Table
        self.hos_table = QTableWidget()
        self.hos_table.setRowCount(3)
        self.hos_table.setColumnCount(15)
        self.hos_table.setVerticalHeaderLabels([
            "Off-Duty",
            "On-Duty",
            "Total (24hr)"])

        from datetime import datetime, timedelta
        today = datetime.now()
        day_headers = []
        for i in range(13, -1, -1):
            day_date = today - timedelta(days=i)
            day_headers.append(str(day_date.day))
        day_headers.append("Total")
        self.hos_table.setHorizontalHeaderLabels(day_headers)

        for col in range(14):
            self.hos_table.setColumnWidth(col, 28)
        self.hos_table.setColumnWidth(14, 50)

        self.hos_table.horizontalHeader().setStyleSheet(
            (
                "QHeaderView::section { background-color: #e0e0e0; "
                "font-weight: bold; padding: 2px;}"
            )
        )
        self.hos_table.verticalHeader().setStyleSheet(
            (
                "QHeaderView::section { background-color: #f5f5f5; "
                "font-weight: bold; padding: 2px; font-size: 9pt;}"
            )
        )

        for day_col in range(14):
            for row in range(3):
                item = QTableWidgetItem("24" if row == 2 else "0")
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                self.hos_table.setItem(row, day_col, item)

        # Set total column width calculation and resize to fit contents
        self.hos_table.setColumnWidth(14, 50)
        self.hos_table.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding)
        self.hos_table.setMaximumHeight(140)
        self.hos_table.setMinimumHeight(140)

        hos_layout.addWidget(self.hos_table)

        forms_row = QHBoxLayout()
        print_hos_form_btn = QPushButton("Print HOS/CVIP Form")
        print_hos_form_btn.setMaximumWidth(150)
        print_hos_form_btn.clicked.connect(self._print_monthly_hos_form)
        forms_row.addWidget(print_hos_form_btn)
        print_inspect_form_btn = QPushButton("Print Daily Inspection Form")
        print_inspect_form_btn.setMaximumWidth(170)
        print_inspect_form_btn.clicked.connect(
            self._print_daily_inspection_form)
        forms_row.addWidget(print_inspect_form_btn)
        complete_inspect_btn = QPushButton("Complete Inspection Online")
        complete_inspect_btn.setMaximumWidth(180)
        complete_inspect_btn.clicked.connect(lambda: QMessageBox.information(
            None, "Feature", "Online inspection completion coming soon"))
        forms_row.addWidget(complete_inspect_btn)
        forms_row.addStretch()
        hos_layout.addLayout(forms_row)
        try:
            self._validate_hos_compliance()
        except Exception:
            pass

        hos_group.setLayout(hos_layout)
        top_row_layout.addWidget(hos_group, 1)

        # === VEHICLE INSPECTION & DEFECTS ===
        vehicle_inspection_group = QGroupBox("Vehicle Pre-Trip Inspection")
        vehicle_inspection_layout = QVBoxLayout()

        form_header = QHBoxLayout()
        form_header.addWidget(
            QLabel("<b>Inspection Form (eHOS Compliance):</b>"))
        upload_form_btn = QPushButton("📄 Upload Inspection Form")
        upload_form_btn.setMaximumWidth(150)
        upload_form_btn.clicked.connect(self._upload_inspection_form)
        form_header.addWidget(upload_form_btn)
        self.inspection_form_label = QLabel("(No form uploaded)")
        self.inspection_form_label.setStyleSheet(
            "color: #888; font-size: 9pt;")
        form_header.addWidget(self.inspection_form_label)
        form_header.addStretch()
        vehicle_inspection_layout.addLayout(form_header)

        view_form_btn = QPushButton("👁 View/Download Form")
        view_form_btn.setMaximumWidth(150)
        view_form_btn.clicked.connect(self._view_inspection_form)
        vehicle_inspection_layout.addWidget(view_form_btn)

        generate_form_btn = QPushButton("🖨 Generate Inspection PDF")
        generate_form_btn.setMaximumWidth(200)
        generate_form_btn.clicked.connect(self._generate_inspection_pdf)
        vehicle_inspection_layout.addWidget(generate_form_btn)

        inspection_header = QHBoxLayout()
        inspection_header.addWidget(QLabel("<b>Inspection Status:</b>"))
        self.inspection_status_combo = QComboBox()
        self.inspection_status_combo.addItems(
            ["Not Started", "In Progress", "Completed", "Deferred"])
        self.inspection_status_combo.setMaximumWidth(120)
        inspection_header.addWidget(self.inspection_status_combo)
        inspection_header.addStretch()
        vehicle_inspection_layout.addLayout(inspection_header)

        condition_label = QLabel("<b>Inspection Results:</b>")
        vehicle_inspection_layout.addWidget(condition_label)

        condition_row = QVBoxLayout()
        self.inspection_no_defects = QCheckBox(
            "✓ No Defects - Vehicle Safe to Operate")
        self.inspection_no_defects.setChecked(True)
        condition_row.addWidget(self.inspection_no_defects)

        self.inspection_minor_defects = QCheckBox(
            "⚠ Minor Defects Noted (See remarks)")
        condition_row.addWidget(self.inspection_minor_defects)

        self.inspection_major_defects = QCheckBox(
            "🚫 Major Defects - Vehicle Unsafe (New vehicle dispatched)")
        condition_row.addWidget(self.inspection_major_defects)

        vehicle_inspection_layout.addLayout(condition_row)

        vehicle_inspection_layout.addWidget(QLabel("<b>Defect Notes:</b>"))
        self.defect_notes_input = QTextEdit()
        self.defect_notes_input.setPlaceholderText(
            "Minor: tire wear, wiper blade, light out\n"
            "Major: brake issue, steering problem, engine trouble"
        )
        self.defect_notes_input.setMaximumHeight(70)
        vehicle_inspection_layout.addWidget(self.defect_notes_input)

        sig_row = QHBoxLayout()
        sig_row.addWidget(QLabel("<b>Driver Signature:</b>"))
        self.inspection_signature_input = QLineEdit()
        self.inspection_signature_input.setPlaceholderText(
            "Driver name / signature")
        sig_row.addWidget(self.inspection_signature_input)
        sig_row.addWidget(QLabel("Date:"))
        self.inspection_date_input = QLineEdit()
        self.inspection_date_input.setPlaceholderText(
            datetime.now().strftime("%Y-%m-%d"))
        self.inspection_date_input.setMaximumWidth(100)
        sig_row.addWidget(self.inspection_date_input)
        vehicle_inspection_layout.addLayout(sig_row)

        vehicle_inspection_group.setLayout(vehicle_inspection_layout)

        # === HOS EXEMPTIONS & LEGAL COMPLIANCE ===
        exemption_group = QGroupBox("HOS Exemptions & Emergency Status")
        exemption_layout = QVBoxLayout()

        exemption_label = QLabel("<b>Emergency/Exemption Status:</b>")
        exemption_layout.addWidget(exemption_label)

        exemption_checks = QVBoxLayout()
        self.exemption_adverse_weather = QCheckBox(
            "Adverse Weather (e.g., snow storm, severe rain)")
        exemption_checks.addWidget(self.exemption_adverse_weather)

        self.exemption_mechanical = QCheckBox(
            "Mechanical Emergency (vehicle breakdown en route)")
        exemption_checks.addWidget(self.exemption_mechanical)

        self.exemption_emergency = QCheckBox(
            "Emergency Relief (medical, accident, disaster response)")
        exemption_checks.addWidget(self.exemption_emergency)

        self.exemption_off_duty_deferral = QCheckBox(
            "Off-Duty Deferral Used (Day 1/Day 2)")
        exemption_checks.addWidget(self.exemption_off_duty_deferral)

        exemption_layout.addLayout(exemption_checks)

        self.exemption_adverse_weather.toggled.connect(
            self._validate_hos_compliance)
        self.exemption_mechanical.toggled.connect(
            self._validate_hos_compliance)
        self.exemption_emergency.toggled.connect(self._validate_hos_compliance)
        self.exemption_off_duty_deferral.toggled.connect(
            self._validate_hos_compliance)

        exemption_layout.addWidget(QLabel("<b>Exemption Details:</b>"))
        self.exemption_remarks_input = QTextEdit()
        self.exemption_remarks_input.setPlaceholderText(
            "Explain circumstances (weather conditions, breakdown time, etc.)")
        self.exemption_remarks_input.setMaximumHeight(60)
        exemption_layout.addWidget(self.exemption_remarks_input)

        exemption_group.setLayout(exemption_layout)

        # === VEHICLE INFORMATION ===
        vehicle_info_group = QGroupBox("Vehicle Information")
        vehicle_info_group.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed)
        vehicle_info_group.setMinimumWidth(200)
        vehicle_info_layout = QVBoxLayout()
        vehicle_info_layout.setContentsMargins(8, 8, 8, 8)
        vehicle_info_layout.setSpacing(4)

        vehicle_num_row = QHBoxLayout()
        vehicle_num_row.addWidget(QLabel("Vehicle #:"))
        self.vehicle_number_input = QLineEdit()
        self.vehicle_number_input.setMaximumWidth(120)
        vehicle_num_row.addWidget(self.vehicle_number_input)
        vehicle_num_row.addStretch()
        vehicle_info_layout.addLayout(vehicle_num_row)

        vehicle_type_row = QHBoxLayout()
        vehicle_type_row.addWidget(QLabel("Type:"))
        self.vehicle_info_type_label = QLabel("")
        self.vehicle_info_type_label.setStyleSheet("font-weight: bold;")
        vehicle_type_row.addWidget(self.vehicle_info_type_label)
        vehicle_type_row.addStretch()
        vehicle_info_layout.addLayout(vehicle_type_row)

        plate_row = QHBoxLayout()
        plate_row.addWidget(QLabel("Plate:"))
        self.vehicle_plate_input = QLineEdit()
        self.vehicle_plate_input.setMaximumWidth(120)
        plate_row.addWidget(self.vehicle_plate_input)
        plate_row.addStretch()
        vehicle_info_layout.addLayout(plate_row)

        start_odo_row = QHBoxLayout()
        start_odo_row.addWidget(QLabel("Start Odometer:"))
        self.start_odometer_input = QLineEdit()
        self.start_odometer_input.setMaximumWidth(100)
        start_odo_row.addWidget(self.start_odometer_input)
        start_odo_row.addStretch()
        vehicle_info_layout.addLayout(start_odo_row)

        end_odo_row = QHBoxLayout()
        end_odo_row.addWidget(QLabel("End Odometer:"))
        self.end_odometer_input = QLineEdit()
        self.end_odometer_input.setMaximumWidth(100)
        end_odo_row.addWidget(self.end_odometer_input)
        end_odo_row.addStretch()
        vehicle_info_layout.addLayout(end_odo_row)

        inspection_row = QHBoxLayout()
        self.vehicle_inspection_checkbox = QCheckBox("Print Inspection Report")
        self.vehicle_inspection_checkbox.setToolTip(
            "Print/Open Vehicle Inspection Report")
        inspection_row.addWidget(self.vehicle_inspection_checkbox)
        vehicle_info_layout.addLayout(inspection_row)

        inspection_time_row = QHBoxLayout()
        inspection_time_row.addWidget(QLabel("Inspection Time:"))
        self.inspection_time_input = QLineEdit()
        self.inspection_time_input.setPlaceholderText("HH:MM")
        self.inspection_time_input.setMaximumWidth(80)
        inspection_time_row.addWidget(self.inspection_time_input)
        inspection_time_row.addStretch()
        vehicle_info_layout.addLayout(inspection_time_row)

        vehicle_info_layout.addStretch()
        vehicle_info_group.setLayout(vehicle_info_layout)
        top_row_layout.addWidget(vehicle_info_group)

        # Add top row (Driver Info + HOS + Vehicle Info)
        ops_layout.insertLayout(0, top_row_layout)

        # === ACCOUNTING / FLOAT ===
        accounting_group = QGroupBox("Accounting & Float")
        accounting_layout = QVBoxLayout()

        float_row = QHBoxLayout()
        float_row.addWidget(QLabel("Float Given:"))
        self.float_given_input = QLineEdit()
        self.float_given_input.setPlaceholderText("$0.00")
        self.float_given_input.setMaximumWidth(100)
        self.float_given_input.textChanged.connect(self._update_float_totals)
        float_row.addWidget(self.float_given_input)
        float_row.addStretch()
        accounting_layout.addLayout(float_row)

        accounting_layout.addWidget(QLabel("<b>Receipts:</b>"))

        # Receipt entry form
        receipt_entry_row = QHBoxLayout()

        self.receipt_vendor_input = QLineEdit()
        self.receipt_vendor_input.setPlaceholderText("Vendor")
        self.receipt_vendor_input.setMaximumWidth(120)
        receipt_entry_row.addWidget(self.receipt_vendor_input)

        self.receipt_desc_input = QLineEdit()
        self.receipt_desc_input.setPlaceholderText("Description")
        self.receipt_desc_input.setMaximumWidth(150)
        receipt_entry_row.addWidget(self.receipt_desc_input)

        self.receipt_amount_input = QLineEdit()
        self.receipt_amount_input.setPlaceholderText("$0.00")
        self.receipt_amount_input.setMaximumWidth(70)
        receipt_entry_row.addWidget(self.receipt_amount_input)

        add_receipt_btn = QPushButton("+ Add")
        add_receipt_btn.setMaximumWidth(60)
        add_receipt_btn.clicked.connect(self._add_receipt_entry)
        receipt_entry_row.addWidget(add_receipt_btn)

        accounting_layout.addLayout(receipt_entry_row)

        # Receipt list (table)
        self.receipts_table = QTableWidget()
        self.receipts_table.setColumnCount(4)
        self.receipts_table.setHorizontalHeaderLabels(
            ["Vendor", "Desc", "Amount", ""])
        self.receipts_table.setMaximumHeight(120)
        self.receipts_table.setColumnWidth(0, 100)
        self.receipts_table.setColumnWidth(1, 130)
        self.receipts_table.setColumnWidth(2, 70)
        self.receipts_table.setColumnWidth(3, 30)
        self.receipts_table.horizontalHeader().setStretchLastSection(False)
        self.receipts_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        accounting_layout.addWidget(self.receipts_table)

        # Receipt total and LTS notes
        receipt_total_row = QHBoxLayout()
        receipt_total_row.addWidget(QLabel("<b>Total Receipts:</b>"))
        self.receipt_total_label = QLabel("$0.00")
        self.receipt_total_label.setStyleSheet(
            "font-weight: bold; color: #d00;")
        receipt_total_row.addWidget(self.receipt_total_label)
        receipt_total_row.addStretch()
        accounting_layout.addLayout(receipt_total_row)

        accounting_layout.addWidget(QLabel("LTS Notes:"))
        self.lts_notes_input = QTextEdit()
        self.lts_notes_input.setPlaceholderText(
            "Long-term storage notes, fuel receipts, parking...")
        self.lts_notes_input.setMaximumHeight(60)
        accounting_layout.addWidget(self.lts_notes_input)

        change_row = QHBoxLayout()
        change_row.addWidget(QLabel("Change Returned:"))
        self.change_returned_label = QLabel("$0.00")
        self.change_returned_label.setStyleSheet("font-weight: bold;")
        change_row.addWidget(self.change_returned_label)
        change_row.addStretch()
        accounting_layout.addLayout(change_row)

        accounting_group.setLayout(accounting_layout)

        # === MID ROW: VEHICLE INSPECTION + EXEMPTIONS ===
        mid_row_layout = QHBoxLayout()
        mid_row_layout.setSpacing(8)
        mid_row_layout.setContentsMargins(0, 0, 0, 0)
        mid_row_layout.addWidget(vehicle_inspection_group, 1)
        mid_row_layout.addWidget(exemption_group, 1)
        ops_layout.addLayout(mid_row_layout)

        # === ACCOUNTING ROW ===
        ops_layout.addWidget(accounting_group)

        # === DRIVER PAY ===
        driver_pay_group = QGroupBox("Driver Pay (Approved Hours & Gratuity)")
        driver_pay_group.setStyleSheet(
            "QGroupBox { border: 2px solid #1a6b3a; border-radius: 4px; "
            "margin-top: 8px; font-weight: bold; color: #1a6b3a; }"
            "QGroupBox::title { subcontrol-origin: margin; padding: 0 4px; }")
        dp_layout = QVBoxLayout()
        dp_layout.setSpacing(6)
        dp_layout.setContentsMargins(10, 12, 10, 10)

        # Row 1: Calculated Hours (read-only) + Approved Hours (editable)
        hours_row = QHBoxLayout()
        hours_row.addWidget(QLabel("Charter Hours (start→end):"))
        self.dp_calculated_hours = QLineEdit()
        self.dp_calculated_hours.setReadOnly(True)
        self.dp_calculated_hours.setMaximumWidth(60)
        self.dp_calculated_hours.setStyleSheet("background: #f0f0f0;")
        self.dp_calculated_hours.setToolTip(
            "Auto-calculated: dropoff_time minus pickup_time")
        hours_row.addWidget(self.dp_calculated_hours)

        hours_row.addWidget(QLabel("  Approved Hours (for pay):"))
        self.dp_approved_hours = QDoubleSpinBox()
        self.dp_approved_hours.setRange(0, 24)
        self.dp_approved_hours.setSingleStep(0.25)
        self.dp_approved_hours.setDecimals(2)
        self.dp_approved_hours.setSuffix(" hrs")
        self.dp_approved_hours.setMaximumWidth(100)
        self.dp_approved_hours.setToolTip(
            "Hours approved for driver pay. Defaults from actual/minimum "
            "hours. "
            "Edit to override (e.g., split runs, overtime).")
        hours_row.addWidget(self.dp_approved_hours)
        hours_row.addStretch()
        dp_layout.addLayout(hours_row)

        # Row 2: Hourly Rate + Billed Gratuity (read-only, from billing
        # charges)
        rate_row = QHBoxLayout()
        rate_row.addWidget(QLabel("Hourly Rate:"))
        self.dp_hourly_rate = QDoubleSpinBox()
        self.dp_hourly_rate.setRange(0, 999)
        self.dp_hourly_rate.setDecimals(2)
        self.dp_hourly_rate.setPrefix("$")
        self.dp_hourly_rate.setMaximumWidth(100)
        rate_row.addWidget(self.dp_hourly_rate)

        rate_row.addWidget(QLabel("  Billed Gratuity:"))
        self.dp_gratuity = QLineEdit()
        self.dp_gratuity.setReadOnly(True)
        self.dp_gratuity.setMaximumWidth(80)
        self.dp_gratuity.setStyleSheet("background: #f0f0f0;")
        self.dp_gratuity.setToolTip(
            "Auto-synced from charter billing (charge line). "
            "Read-only - edit in the Billing tab."
        )
        rate_row.addWidget(self.dp_gratuity)
        rate_row.addStretch()
        dp_layout.addLayout(rate_row)

        # Row 3: Approved Gratuity (editable — dispatcher adjusts for
        # complaints, cleaning, shared split)
        appr_grat_row = QHBoxLayout()
        appr_grat_row.addWidget(QLabel("Approved Gratuity (for driver):"))
        self.dp_approved_gratuity = QDoubleSpinBox()
        self.dp_approved_gratuity.setRange(0, 99999)
        self.dp_approved_gratuity.setSingleStep(1.0)
        self.dp_approved_gratuity.setDecimals(2)
        self.dp_approved_gratuity.setPrefix("$")
        self.dp_approved_gratuity.setMaximumWidth(110)
        self.dp_approved_gratuity.setToolTip(
            "Dispatcher-approved gratuity paid to driver. May differ from "
            "billed gratuity\n"
            "due to complaints, cleaning chargebacks, shared tips "
            "(cleaning/dispatch), etc."
        )
        appr_grat_row.addWidget(self.dp_approved_gratuity)
        appr_grat_row.addWidget(
            QLabel("  (reduce for complaints / cleaning / shared staff)"))
        appr_grat_row.addStretch()
        dp_layout.addLayout(appr_grat_row)

        # Row 4: Total Driver Pay (read-only, calculated)
        total_row = QHBoxLayout()
        total_row.addWidget(QLabel("<b>Total Driver Pay:</b>"))
        self.dp_total_pay = QLineEdit()
        self.dp_total_pay.setReadOnly(True)
        self.dp_total_pay.setMaximumWidth(100)
        self.dp_total_pay.setStyleSheet(
            "background: #e8f5e9; font-weight: bold; "
            "color: #1a6b3a; font-size: 11pt;"
        )
        total_row.addWidget(self.dp_total_pay)
        total_row.addWidget(
            QLabel(
                "  = approved_hours * hourly_rate + approved_gratuity"
            )
        )
        total_row.addStretch()
        dp_layout.addLayout(total_row)

        driver_pay_group.setLayout(dp_layout)
        ops_layout.addWidget(driver_pay_group)

        # Wire up auto-recalculate on change
        self.dp_approved_hours.valueChanged.connect(
            self._recalculate_driver_pay)
        self.dp_hourly_rate.valueChanged.connect(self._recalculate_driver_pay)
        self.dp_approved_gratuity.valueChanged.connect(
            self._recalculate_driver_pay)

        ops_layout.addStretch()
        ops_container.setLayout(ops_layout)
        scroll.setWidget(ops_container)
        return scroll

    def load_vehicles(self):
        """Load vehicles sorted with active first and L-numbers in numeric
        order, storing type for display."""
        try:
            cur = self.db.get_cursor()
            cur.execute(
                r"""
                  SELECT vehicle_id, vehicle_number,
                      operational_status as status,
                      COALESCE(vehicle_type, '') as vehicle_type
                FROM vehicles
                ORDER BY
                    CASE WHEN operational_status = 'active' THEN 0 ELSE 1 END,
                    CASE
                        WHEN vehicle_number ~ '^[Ll]-?\d+$' THEN
                            CAST(
                                regexp_replace(
                                    vehicle_number, '[^0-9]', '', 'g')
                                AS INT
                            )
                        ELSE 9999
                    END,
                    vehicle_number
                """)
            rows = cur.fetchall()
            self.vehicle_combo.clear()
            # Map vehicle_id -> vehicle_type for quick lookup when selection
            # changes
            self._vehicle_types = {}
            for vehicle_id, vehicle_number, status, vehicle_type in rows:
                label = str(vehicle_number or f"Vehicle {vehicle_id}")
                self.vehicle_combo.addItem(label, vehicle_id)
                self._vehicle_types[vehicle_id] = vehicle_type or ""
            # Initialize type display for current selection
            self._update_vehicle_type_display()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load vehicles: {e}")

    def _update_vehicle_type_display(self):
        """Update vehicle type label when dispatched vehicle is selected (NO
        pricing impact)"""
        try:
            vid = self.vehicle_combo.currentData()
            vtype = ""
            if hasattr(self, "_vehicle_types") and vid in self._vehicle_types:
                vtype = self._vehicle_types.get(vid) or ""
            self.vehicle_type_label.setText(str(vtype))
        except Exception:
            try:
                self.vehicle_type_label.setText("")
            except Exception:
                pass

    def _update_driver_name_display(self):
        """Update driver name display label when driver is selected"""
        try:
            driver_text = self.driver_combo.currentText()
            if driver_text and driver_text != "":
                # Display just the name (already formatted from combo)
                self.driver_name_display_label.setText(f"({driver_text})")
                self.driver_name_display_label.setStyleSheet(
                    "color: #000; font-weight: bold;")
            else:
                self.driver_name_display_label.setText("")
                self.driver_name_display_label.setStyleSheet(
                    "color: #555; font-style: italic;")
        except Exception as e:
            print(f"Error updating driver name display: {e}")

    def _calculate_charter_duration(self):
        """Auto-calculate charter duration when base timing changed (handles
        midnight span)"""
        try:
            from_time = self.base_time_from.time()
            to_time = self.base_time_to.time()

            # Convert to minutes for calculation
            from_minutes = from_time.hour() * 60 + from_time.minute()
            to_minutes = to_time.hour() * 60 + to_time.minute()

            # Handle overnight (past midnight)
            if to_minutes < from_minutes:
                # Next day - add 24 hours
                to_minutes += 24 * 60

            duration_minutes = to_minutes - from_minutes
            duration_hours = duration_minutes / 60.0

            # Update duration label
            self.duration_label.setText(f"{duration_hours:.1f} hrs")

            return duration_hours
        except Exception as e:
            print(f"Error calculating duration: {e}")
            return 0.0

    def _auto_populate_pricing_from_vehicle_type(self, vehicle_type: str):
        """Auto-populate quoted hourly rate from vehicle pricing defaults"""
        try:
            if not vehicle_type or vehicle_type == "(Not assigned)":
                return

            pricing = self._load_pricing_defaults(vehicle_type)
            hourly_rate = pricing.get("hourly_rate", 0.0)

            if hourly_rate > 0:
                # Only auto-populate if field is empty (don't override custom
                # pricing)
                current_price = self.quoted_hourly_price.text().strip()
                if not current_price or current_price == "$0.00":
                    self.quoted_hourly_price.setText(f"${hourly_rate:.2f}")
                    print(
                        "✅ Auto-populated pricing: "
                        f"{vehicle_type} → ${hourly_rate:.2f}/hr"
                    )
        except Exception as e:
            print(f"Error auto-populating pricing: {e}")

    def _on_requested_vehicle_type_changed(self):
        """When Requested Vehicle Type is selected, auto-fill quoted hourly
        rate from pricing defaults"""
        try:
            current_hourly_text = ""
            if hasattr(self, 'quoted_hourly_price'):
                current_hourly_text = (
                    self.quoted_hourly_price.text() or ""
                ).strip()
            try:
                current_hourly_val = float(
                    current_hourly_text.replace("$", "").replace(",", "")
                ) if current_hourly_text else 0.0
            except Exception:
                current_hourly_val = 0.0

            vehicle_type = self.vehicle_type_requested_combo.currentData()
            if not vehicle_type:
                if current_hourly_val <= 0:
                    self.quoted_hourly_price.clear()
                self.base_charge_display.clear()
                self.day_rate_display.clear()
                self.flat_rate_display.clear()
                self.split_rate_display.clear()
                self.standby_rate_display.clear()
                self.nrr_deposit.clear()
                return

            pricing = self._load_pricing_defaults(vehicle_type)
            hourly_rate = pricing.get("hourly_rate", 0.0)
            hourly_package = pricing.get("hourly_package", 0.0)
            daily_rate = pricing.get("daily_rate", 0.0)
            standby_rate = pricing.get("standby_rate", 0.0)
            nrr = pricing.get("nrr", 0.0)

            # Quoted Hourly (main editable field)
            if hourly_rate > 0 and current_hourly_val <= 0:
                self.quoted_hourly_price.setText(f"${hourly_rate:.2f}")
            elif hourly_rate <= 0 and current_hourly_val <= 0:
                self.quoted_hourly_price.clear()

            # Base Rate = Hourly Rate (for hourly billing)
            if hourly_rate > 0:
                self.base_charge_display.setText(f"${hourly_rate:.2f}")
            else:
                self.base_charge_display.clear()

            # Day Rate
            if daily_rate > 0:
                self.day_rate_display.setText(f"${daily_rate:.2f}")
            else:
                self.day_rate_display.clear()

            # Flat/Package Rate = Hourly Package Rate (flat rate × hours =
            # package total)
            if hourly_package > 0:
                self.flat_rate_display.setText(f"${hourly_package:.2f}")
            elif daily_rate > 0:
                # Fallback to daily_rate if no hourly_package
                self.flat_rate_display.setText(f"${daily_rate:.2f}")
            else:
                self.flat_rate_display.clear()

            # Split Rate = Same as hourly (split run uses hourly with timing
            # breaks)
            if hourly_rate > 0:
                self.split_rate_display.setText(f"${hourly_rate:.2f}")
            else:
                self.split_rate_display.clear()

            # Standby Rate per hour (for wait time during split runs)
            if standby_rate > 0:
                self.standby_rate_display.setText(f"${standby_rate:.2f}")
            else:
                self.standby_rate_display.clear()

            # NRR Deposit (non-refundable deposit amount)
            if nrr > 0:
                self.nrr_deposit.setText(f"${nrr:.2f}")
            else:
                self.nrr_deposit.clear()
        except Exception as e:
            print(f"Error updating quoted rate: {e}")

    def _on_run_type_changed(self):
        """When Run Type is selected, auto-add default charges (e.g., airport
        fees)"""
        try:
            run_type_text = self.run_type_combo.currentText()
            print(f"🔵 Run type changed to: {run_type_text}")
            run_type_id = self.run_type_combo.currentData()
            if not run_type_id:
                print("ℹ️  No run type selected")
                return

            # Remove any previously auto-added charges from old run type
            self._remove_run_type_auto_charges()

            # NOTE: run_type_default_charges table doesn't exist yet
            # For now, only auto-add airport fees based on vehicle pricing

            # Airport Authority Fee (based on run type selection)
            run_type_name = (self.run_type_combo.currentText() or "").lower()
            vehicle_type = (
                self.vehicle_type_label.text().strip()
                if hasattr(self, 'vehicle_type_label')
                else ""
            )
            print(
                f"   Vehicle type: {vehicle_type}, "
                f"Run type: {run_type_name}"
            )

            if vehicle_type:
                pricing = self._load_pricing_defaults(vehicle_type)
                if (
                    "airport pickup - calgary" in run_type_name
                    or "calgary" in run_type_name
                ):
                    airport_rate = pricing.get("airport_pickup_calgary", 0.0)
                    if airport_rate > 0:
                        self.add_charge_line(
                            description="Airport Authority Fee - Calgary",
                            calc_type="Fixed",
                            value=airport_rate,
                            auto_added=True)
                        print(
                            "✅ Auto-added Calgary airport fee: "
                            f"${airport_rate}"
                        )

                if (
                    "airport pickup - edmonton" in run_type_name
                    or "edmonton" in run_type_name
                ):
                    airport_rate = pricing.get("airport_pickup_edmonton", 0.0)
                    if airport_rate > 0:
                        self.add_charge_line(
                            description="Airport Authority Fee - Edmonton",
                            calc_type="Fixed",
                            value=airport_rate,
                            auto_added=True)
                        print(
                            "✅ Auto-added Edmonton airport fee: "
                            f"${airport_rate}"
                        )

        except Exception as e:
            print(f"❌ Error auto-adding charges for run type: {e}")
            import traceback
            traceback.print_exc()

    def _remove_run_type_auto_charges(self):
        """Remove all auto-added charges from previous run type selection"""
        try:
            # Look for charges marked as auto-added in the table
            # We'll use a custom data role to track this
            for row in range(self.charges_table.rowCount() - 1, -1, -1):
                desc_item = self.charges_table.item(row, 0)
                if desc_item and desc_item.data(
                        Qt.ItemDataRole.UserRole + 1) == "auto_added":
                    self.charges_table.removeRow(row)
        except Exception as e:
            print(f"Error removing auto charges: {e}")

    def _on_gratuity_checkbox_toggled(self, checked: bool):
        """When Gratuity checkbox is toggled, add or remove Gratuity line from
        charges"""
        try:
            # Find and remove existing Gratuity line
            for row in range(self.charges_table.rowCount() - 1, -1, -1):
                desc_item = self.charges_table.item(row, 0)
                if desc_item and "Gratuity" in desc_item.text():
                    self.charges_table.removeRow(row)

            # If checked, add Gratuity line
            if checked:
                gratuity_percent = self.gratuity_percent_input.value(
                ) if hasattr(self, 'gratuity_percent_input') else 18.0
                self.add_charge_line(
                    description=f"Gratuity ({gratuity_percent}%)",
                    calc_type="Percent",
                    value=gratuity_percent)

            # Mark form as modified
            current_title = self.windowTitle()
            if "✏️" not in current_title:
                self.setWindowTitle(f"✏️ {current_title}")

            self.recalculate_totals()
        except Exception as e:
            print(f"Error toggling Gratuity: {e}")

    def _on_nrr_received(self, amount: float):
        """When NRR is received, auto-change status to Booked and recalculate
        balance"""
        try:
            if amount > 0:
                # Move inquiry into active booking flow when NRR is received.
                if hasattr(self, 'charter_status_combo'):
                    self.charter_status_combo.setCurrentText(
                        "Booked"
                    )

                # Mark as modified
                current_title = self.windowTitle()
                if "✏️" not in current_title:
                    self.setWindowTitle(f"✏️ {current_title}")

            # Recalculate balance including NRR
            self.recalculate_totals()
        except Exception as e:
            print(f"Error handling NRR: {e}")

    def _on_cc_checkbox_changed(self, state):
        """When CC checkbox is toggled, enable/disable CC fields"""
        try:
            is_checked = self.client_cc_checkbox.isChecked()
            self.client_cc_full.setEnabled(is_checked)
            self.client_cc_last4.setEnabled(is_checked)

            # If unchecked, clear sensitive data
            if not is_checked:
                self.client_cc_full.clear()
                self.client_cc_last4.clear()
        except Exception as e:
            print(f"Error handling CC checkbox: {e}")

    def _on_gratuity_percent_changed(self, value: float):
        """When Gratuity percentage changes, update the Gratuity line if it
        exists"""
        try:
            if (
                not hasattr(self, 'gratuity_checkbox')
                or not self.gratuity_checkbox.isChecked()
            ):
                return

            # Find and update existing Gratuity line
            for row in range(self.charges_table.rowCount()):
                desc_item = self.charges_table.item(row, 0)
                if desc_item and "Gratuity" in desc_item.text():
                    # Update description and value
                    desc_item.setText(f"Gratuity ({value}%)")
                    desc_item.setData(
                        Qt.ItemDataRole.UserRole,
                        {"calc_type": "Percent", "value": float(value)},
                    )

                    # Recalculate line total
                    line_total = self._compute_line_total(
                        "Percent", float(value))
                    total_item = self.charges_table.item(row, 2)
                    if total_item:
                        total_item.setText(f"{line_total:.2f}")

                    # Mark form as modified
                    current_title = self.windowTitle()
                    if "✏️" not in current_title:
                        self.setWindowTitle(f"✏️ {current_title}")
                    break

            # Recalculate all totals
            self.recalculate_totals()
        except Exception as e:
            print(f"Error updating Gratuity percent: {e}")

    def load_drivers(self):
        """Load active drivers from database"""
        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except Exception:
                pass

            self.driver_combo.clear()
            self.driver_combo.addItem("(None)", None)  # Add blank option

            cur = self.db.get_cursor()
            cur.execute("""
                SELECT employee_id, first_name, last_name
                FROM employees
                WHERE employment_status = 'active' AND is_chauffeur = true
                ORDER BY last_name
            """)
            drivers = cur.fetchall()
            if not drivers:
                print("⚠️  No active drivers found in database")
            for row in drivers:
                self.driver_combo.addItem(f"{row[1]} {row[2]}", row[0])
            print(f"✅ Loaded {len(drivers)} drivers")
        except Exception as e:
            print(f"❌ Driver load error: {e}")
            try:
                self.db.rollback()
            except Exception:
                pass
            QMessageBox.warning(self, "Error", f"Failed to load drivers: {e}")

    def load_hos_data(self, employee_id=None):
        """Load HOS records for last 14 days from database
        Default to 24hr off-duty / 0hr on-duty for days without records
        """
        try:
            if not employee_id:
                # Get currently selected driver
                employee_id = self.driver_combo.currentData()

            if not employee_id:
                return  # No driver selected

            from datetime import datetime, timedelta
            today = datetime.now().date()

            cur = self.db.get_cursor()

            # Load last 14 days of HOS records
            for i in range(13, -1, -1):  # 14 days ago to today
                day_date = today - timedelta(days=i)
                col_index = 13 - i  # Column 0 = oldest, column 13 = today

                # Query hos_log for this driver and date
                # Aggregate hours if multiple entries for same day
                cur.execute(
                    """
                    SELECT COALESCE(SUM(on_duty_hours), 0) as total_on_duty,
                           COALESCE(SUM(off_duty_hours), 0) as total_off_duty
                    FROM hos_log
                    WHERE employee_id = %s AND hos_date = %s
                    """,
                    (employee_id, day_date),)

                row = cur.fetchone()

                if row:
                    on_duty = float(row[0] or 0)
                    off_duty = float(row[1] or 0)
                    # Normalize to 24 hours
                    total = on_duty + off_duty
                    if total > 0:
                        on_duty = min(24, on_duty)
                        off_duty = max(0, 24 - on_duty)
                    else:
                        on_duty = 0
                        off_duty = 24
                else:
                    on_duty = 0
                    off_duty = 24

                total = 24

                # Update table cells
                self.hos_table.item(0, col_index).setText(str(int(off_duty)))
                self.hos_table.item(1, col_index).setText(str(int(on_duty)))
                self.hos_table.item(2, col_index).setText(str(int(total)))

            # Recalculate totals column
            self.update_hos_totals()

        except Exception as e:
            print(f"❌ HOS Error: {e}")
            import traceback
            traceback.print_exc()

    def update_hos_from_charter(
            self,
            charter_date,
            on_duty_start,
            off_duty_end):
        """Update HOS table when charter times are entered
        Combines with existing HOS data for same day (multiple trips)
        """
        try:
            employee_id = self.driver_combo.currentData()
            if not employee_id or not charter_date:
                return

            from datetime import datetime
            today = datetime.now().date()

            # Calculate which column this date falls in (last 14 days)
            days_ago = (today - charter_date).days
            if days_ago < 0 or days_ago > 13:
                return  # Outside 14-day window

            col_index = 13 - days_ago

            # Calculate on-duty hours for this charter
            if on_duty_start and off_duty_end:
                charter_on_duty = (
                    off_duty_end - on_duty_start).total_seconds() / 3600
            else:
                charter_on_duty = 0

            try:
                self.db.rollback()
            except Exception:
                pass

            cur = self.db.get_cursor()

            # Get existing HOS for this day
            cur.execute(
                "SELECT hours_on_duty FROM driver_hos_log WHERE employee_id = "
                "%s AND shift_date = %s LIMIT 1",
                (employee_id, charter_date),)

            existing = cur.fetchone()

            if existing:
                total_on_duty = float(existing[0] or 0) + charter_on_duty
            else:
                total_on_duty = charter_on_duty

            total_off_duty = 24 - total_on_duty

            # Persist to driver_hos_log (replace existing for this day)
            cur.execute(
                "DELETE FROM driver_hos_log WHERE employee_id = %s AND "
                "shift_date = %s",
                (employee_id, charter_date),)

            shift_start = (
                on_duty_start
                if on_duty_start
                else datetime.combine(charter_date, datetime.min.time())
            )
            shift_end = off_duty_end if off_duty_end else None

            cur.execute(
                """
                INSERT INTO driver_hos_log (
                    employee_id,
                    charter_id,
                    vehicle_id,
                    shift_date,
                    shift_start,
                    shift_end,
                    hours_on_duty,
                    hours_driven,
                    odometer_start,
                    odometer_end,
                    total_kms,
                    notes
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NULL, NULL, NULL, %s)
                """,
                (
                    employee_id,
                    None,
                    None,
                    charter_date,
                    shift_start,
                    shift_end,
                    total_on_duty,
                    0,
                    "Auto-updated from charter entry",),)

            self.db.commit()

            # Update table display
            self.hos_table.item(0, col_index).setText(str(int(total_off_duty)))
            self.hos_table.item(1, col_index).setText(str(int(total_on_duty)))
            self.update_hos_totals()

        except Exception as e:
            try:
                self.db.rollback()
            except Exception:
                pass
            QMessageBox.warning(
                self,
                "HOS Update Error",
                f"Failed to update HOS: {e}")

    def update_hos_totals(self):
        """Recalculate totals column (sum of all 14 days)"""
        total_off = 0
        total_on = 0

        for col in range(14):
            total_off += int(self.hos_table.item(0, col).text() or 0)
            total_on += int(self.hos_table.item(1, col).text() or 0)

        # Update totals column
        self.hos_table.item(0, 14).setText(str(total_off))
        self.hos_table.item(1, 14).setText(str(total_on))
        self.hos_table.item(2, 14).setText(str(total_off + total_on))

        # Update 5-day total label (last 5 days on-duty hours)
        five_day_on_duty = sum(
            int(self.hos_table.item(1, col).text() or 0)
            for col in range(9, 14)
        )
        self.total_hours_label.setText(str(five_day_on_duty))
        # Update 7-day on-duty label (recent 7 days)
        try:
            last7_table = sum(int(self.hos_table.item(1, col).text() or 0)
                              for col in range(7, 14))
            if hasattr(self, 'total_7day_label'):
                self.total_7day_label.setText(str(last7_table))
        except Exception:
            pass

        # Validate compliance snapshot
        try:
            self._validate_hos_compliance()
        except Exception:
            pass

    def _validate_hos_compliance(self):
        """Validate HOS against Cycle and exemption rules; update status
        label."""
        try:
            # Gather hours from table
            on = []
            off = []
            for col in range(14):
                try:
                    off_val = int(self.hos_table.item(0, col).text() or 0)
                    on_val = int(self.hos_table.item(1, col).text() or 0)
                except Exception:
                    off_val, on_val = 0, 0
                off.append(off_val)
                on.append(on_val)

            # Determine limits
            cycle = self.cycle_combo.currentText() if hasattr(
                self, 'cycle_combo') else 'Cycle 1'
            # Daily on-duty limit is 14h; 16h rule is elapsed time with 2h off,
            # which we don't track here, so keep strict 14h on-duty per day.
            daily_on_limit = 14

            violations = []

            # Per-day on-duty limit
            for idx, hours in enumerate(on):
                if hours > daily_on_limit:
                    violations.append(
                        f"Day {idx + 1}: on-duty {hours}h > {daily_on_limit}h")

            # Daily off-duty minimum (10h) with optional deferral
            allow_deferral = (
                hasattr(self, 'exemption_off_duty_deferral')
                and self.exemption_off_duty_deferral.isChecked()
            )
            off_violations_idx = [i for i, h in enumerate(off) if h < 10]
            if allow_deferral and off_violations_idx:
                # Look for one pair (day i: 8-9h, day i+1: >=12h)
                forgiven = False
                for i in off_violations_idx:
                    if 8 <= off[i] < 10 and i < 13 and off[i + 1] >= 12:
                        forgiven = True
                        break
                # Remove one deferrable violation if found
                if forgiven:
                    # Keep all violations except the forgiven one (first
                    # matching)
                    removed = False
                    tmp = []
                    for i in off_violations_idx:
                        if (
                            not removed
                            and 8 <= off[i] < 10
                            and i < 13
                            and off[i + 1] >= 12
                        ):
                            removed = True
                            continue
                        tmp.append(i)
                    off_violations_idx = tmp
            # Add remaining off-duty violations
            for i in off_violations_idx:
                violations.append(f"Day {i + 1}: off-duty {off[i]}h < 10h")

            # Cycle reset
            # Cycle 1: 2 consecutive days fully off (>=24h each = 48h total)
            # Cycle 2: 3 consecutive days fully off (>=24h each = 72h total)
            reset_index_c1 = -1
            reset_index_c2 = -1

            # Check for Cycle 1 reset (2 days off)
            for i in range(0, 13):
                if off[i] >= 24 and off[i + 1] >= 24:
                    # Start counting after 2-day off block.
                    reset_index_c1 = i + 2
                    break

            # Check for Cycle 2 reset (3 days off)
            for i in range(0, 12):
                if (
                    off[i] >= 24
                    and off[i + 1] >= 24
                    and off[i + 2] >= 24
                ):
                    # Start counting after 3-day off block.
                    reset_index_c2 = i + 3
                    break

            # Apply reset based on cycle type
            reset_index = -1
            if cycle == 'Cycle 1':
                reset_index = reset_index_c1
            elif cycle == 'Cycle 2':
                reset_index = reset_index_c2
            elif cycle == 'Cycle 1 & 2':
                # Use the later reset (more conservative)
                if reset_index_c2 != -1:
                    reset_index = reset_index_c2
                elif reset_index_c1 != -1:
                    reset_index = reset_index_c1

            on_since_reset = on[reset_index:] if reset_index != -1 else on

            # Cycle limits computed from the period since last reset
            last7 = sum(on_since_reset[-7:])
            last14 = sum(on_since_reset[-14:])
            if cycle == 'Cycle 1' or cycle == 'Cycle 1 & 2':
                if last7 > 70:
                    violations.append(f"Cycle 1: 7-day total {last7}h > 70h")
            if cycle == 'Cycle 2' or cycle == 'Cycle 1 & 2':
                if last14 > 120:
                    violations.append(
                        f"Cycle 2: 14-day total {last14}h > 120h")

            # Update label
            if not hasattr(self, 'hos_compliance_label'):
                return
            if not violations:
                # Compose concise OK message
                msg_parts = []
                if cycle in ('Cycle 1', 'Cycle 1 & 2'):
                    msg_parts.append(f"7-day {last7}/70h")
                if cycle in ('Cycle 2', 'Cycle 1 & 2'):
                    msg_parts.append(f"14-day {last14}/120h")
                ok_msg = "; ".join(msg_parts) if msg_parts else "Within limits"
                reset_note = (
                    f"; reset at day {reset_index + 1}"
                    if reset_index != -1 else "")
                self.hos_compliance_label.setText(
                    f"HOS OK ({cycle}): {ok_msg}{reset_note}")
                self.hos_compliance_label.setStyleSheet(
                    "color: #0a0; font-weight: bold;")
            else:
                summary = ", ".join(violations[:2])
                remaining = len(violations) - 2
                if remaining > 0:
                    summary += f", …{remaining} more"
                reset_note = (
                    f"; reset at day {reset_index + 1}"
                    if reset_index != -1 else "")
                self.hos_compliance_label.setText(
                    f"HOS Violations: {summary}{reset_note}")
                self.hos_compliance_label.setStyleSheet(
                    "color: #c00; font-weight: bold;")
                # Suggest fixes interactively when entering violation state
                try:
                    self._maybe_prompt_violation(
                        violations, on, off, daily_on_limit)
                except Exception:
                    pass
            # Track last violation count to reduce prompt spam
            self.hos_last_violation_count = len(violations)
        except Exception:
            # Don't crash UI on validation issues
            if hasattr(self, 'hos_compliance_label'):
                self.hos_compliance_label.setText(
                    "HOS status: validation error")
                self.hos_compliance_label.setStyleSheet("color: #c60;")
            self.hos_last_violation_count = getattr(
                self, 'hos_last_violation_count', 0)

    def _maybe_prompt_violation(self, violations, on, off, daily_on_limit):
        """Show actionable suggestions when a violation is detected."""
        # Only prompt when transitioning from OK -> violation
        prev = getattr(self, 'hos_last_violation_count', 0)
        if prev != 0:
            return

        # Find most recent violating day (closest to today)
        violating_day = None
        needed_break = 0
        for i in range(13, -1, -1):
            if on[i] > daily_on_limit or off[i] < 10:
                violating_day = i
                # Minimum adjustment to meet both daily limits
                need_on = max(0, on[i] - daily_on_limit)
                need_off = max(0, 10 - off[i])
                needed_break = max(need_on, need_off)
                break

        # Compose message
        details = ", ".join(violations[:3])
        if len(violations) > 3:
            details += f", …{len(violations) - 3} more"
        msg_text = (
            "A Hours-of-Service violation was detected.\n\n"
            f"Details: {details}\n\n"
            "You can try: \n"
            "• Adding an off-duty break to reduce on-duty hours\n"
            "• Checking start/end times for typos or mis-entry\n"
            "• Applying Emergency rules "
            "(adverse weather/mechanical/emergency)\n"
        )

        # Build dialog with actionable buttons
        dlg = QMessageBox(self)
        dlg.setWindowTitle("HOS Violation Detected")
        dlg.setIcon(QMessageBox.Warning)
        dlg.setText(msg_text)

        add_break_btn = dlg.addButton("Add Break…", QMessageBox.ActionRole)
        check_times_btn = dlg.addButton("Check Times", QMessageBox.ActionRole)
        apply_emergency_btn = dlg.addButton(
            "Apply Emergency", QMessageBox.ActionRole)
        dlg.addButton(QMessageBox.Close)

        dlg.exec()
        clicked = dlg.clickedButton()

        if clicked == add_break_btn:
            # Suggest needed break (hours), allow user override
            default_break = max(1, int(round(needed_break)))
            ok = False
            try:
                break_hours_str, ok = QInputDialog.getText(
                    self,
                    "Add Off-Duty Break",
                    (
                        f"Enter break hours to add to the most recent "
                        f"violating day (suggested: {default_break}h).\n"
                        "This will increase off-duty and reduce on-duty "
                        "for that day in the log."
                    ),
                    text=str(default_break))
            except Exception:
                break_hours_str, ok = (str(default_break), False)
            if ok:
                try:
                    break_hours = float(break_hours_str)
                    if violating_day is not None:
                        # Preselect violating day in manual panel
                        try:
                            self.manual_day_combo.setCurrentIndex(
                                violating_day)
                        except Exception:
                            pass
                        self._apply_break_to_day(violating_day, break_hours)
                        self.update_hos_totals()
                except Exception:
                    QMessageBox.information(
                        self, "Break Entry", "Invalid break hours.")

        elif clicked == check_times_btn:
            QMessageBox.information(
                self,
                "Check Start/End",
                (
                    "Verify duty start/end entries and any breaks "
                    "for the violating day.\n"
                    "Correct any typos or mismatched times "
                    "to restore compliance."
                ),
            )
            try:
                if violating_day is not None:
                    self.manual_day_combo.setCurrentIndex(violating_day)
                    self.manual_start_input.setFocus()
            except Exception:
                pass
        elif clicked == apply_emergency_btn:
            try:
                # Apply Emergency relief flag and revalidate
                if hasattr(self, 'exemption_emergency'):
                    self.exemption_emergency.setChecked(True)
                self._validate_hos_compliance()
            except Exception:
                pass

    def _apply_break_to_day(self, day_index, break_hours):
        """Adjust the table for a given day: add off-duty break, reduce on-duty
        accordingly."""
        try:
            curr_on = int(self.hos_table.item(1, day_index).text() or 0)
            curr_off = int(self.hos_table.item(0, day_index).text() or 0)
            add_off = max(0.0, float(break_hours))
            new_on = max(0, curr_on - add_off)
            new_off = min(24, curr_off + add_off)
            # Clamp to 24 total
            if new_on + new_off != 24:
                # Adjust to maintain 24h total
                if new_on + new_off > 24:
                    excess = (new_on + new_off) - 24
                    new_off = max(0, new_off - excess)
                else:
                    deficit = 24 - (new_on + new_off)
                    new_off = min(24, new_off + deficit)
            self.hos_table.item(1, day_index).setText(str(int(round(new_on))))
            self.hos_table.item(0, day_index).setText(str(int(round(new_off))))
            self.hos_table.item(2, day_index).setText("24")
        except Exception:
            pass

    def _update_driver_info_name(self):
        """Update driver name label in right column when driver selected"""
        try:
            driver_text = self.driver_combo.currentText()
            if driver_text and driver_text != "Select...":
                self.driver_info_name_label.setText(driver_text)
                self.driver_info_name_label.setStyleSheet(
                    "color: #000; font-weight: bold;")
            else:
                self.driver_info_name_label.setText("(Not assigned)")
                self.driver_info_name_label.setStyleSheet("color: #555;")
        except Exception:
            pass

    def _upload_inspection_form(self):
        """Upload scanned vehicle inspection form for eHOS compliance
        Stores PDF/image in L:\\limo\\data\\inspections\\charter_<id>\\
        """
        try:
            # Create inspections directory if not exists
            import shutil
            inspections_dir = os.path.join(
                os.path.dirname(__file__), "..", "data", "inspections")
            os.makedirs(inspections_dir, exist_ok=True)

            # Open file dialog
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Select Vehicle Inspection Form",
                inspections_dir,
                (
                    "PDF Files (*.pdf);;Image Files (*.jpg *.jpeg *.png);;"
                    "All Files (*.*)"
                ),
            )

            if not file_path:
                return  # User cancelled

            # Create charter-specific subdirectory
            reserve_number = self.reserve_number_input.text() if hasattr(
                self, 'reserve_number_input') else "temp"
            charter_dir = os.path.join(
                inspections_dir, f"charter_{reserve_number}")
            os.makedirs(charter_dir, exist_ok=True)

            # Copy file to archive with timestamp
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_ext = os.path.splitext(file_path)[1]
            dest_filename = f"inspection_{timestamp}{file_ext}"
            dest_path = os.path.join(charter_dir, dest_filename)

            shutil.copy2(file_path, dest_path)

            # Store path for later reference
            self.current_inspection_form_path = dest_path

            # Update label
            self.inspection_form_label.setText(f"✓ {dest_filename}")
            self.inspection_form_label.setStyleSheet(
                "color: #080; font-weight: bold;")

            QMessageBox.information(
                self,
                "Success",
                "Inspection form saved for eHOS compliance.\n\n"
                f"File: {dest_filename}\nPath: {charter_dir}",
            )

        except Exception as e:
            QMessageBox.warning(
                self,
                "Upload Error",
                f"Failed to save inspection form: {e}")

    def _view_inspection_form(self):
        """Open/view the uploaded inspection form"""
        try:
            if (
                not hasattr(self, 'current_inspection_form_path')
                or not self.current_inspection_form_path
            ):
                QMessageBox.warning(
                    self,
                    "No Form",
                    "No inspection form has been uploaded yet.",
                )
                return

            if not os.path.exists(self.current_inspection_form_path):
                QMessageBox.warning(
                    self,
                    "Not Found",
                    "Inspection form file not found:\n"
                    f"{self.current_inspection_form_path}",
                )
                return

            # Open with default application
            import platform
            import subprocess

            if platform.system() == 'Windows':
                os.startfile(self.current_inspection_form_path)
            elif platform.system() == 'Darwin':
                subprocess.Popen(['open', self.current_inspection_form_path])
            else:  # Linux
                subprocess.Popen(
                    ['xdg-open', self.current_inspection_form_path])

        except Exception as e:
            QMessageBox.warning(
                self,
                "View Error",
                f"Failed to open inspection form: {e}")

    def _generate_inspection_pdf(self):
        """Generate a filled inspection PDF with current UI data (checkbox
        style)."""
        try:
            out_dir = os.path.join(project_root, 'reports', 'inspection_logs')
            os.makedirs(out_dir, exist_ok=True)

            driver = getattr(self, 'driver_info_name_label',
                             QLabel('')).text() or 'driver'
            vehicle = getattr(
                self,
                'vehicle_number_input',
                QLineEdit('')).text() or ''
            plate = getattr(
                self,
                'vehicle_plate_input',
                QLineEdit('')).text() or ''
            start_odo = getattr(
                self,
                'start_odometer_input',
                QLineEdit('')).text() or ''
            end_odo = getattr(self, 'end_odometer_input',
                              QLineEdit('')).text() or ''
            insp_status = self.inspection_status_combo.currentText(
            ) if hasattr(self, 'inspection_status_combo') else ''
            no_defects = self.inspection_no_defects.isChecked() if hasattr(
                self, 'inspection_no_defects') else False
            minor_def = self.inspection_minor_defects.isChecked() if hasattr(
                self, 'inspection_minor_defects') else False
            major_def = self.inspection_major_defects.isChecked() if hasattr(
                self, 'inspection_major_defects') else False
            defect_notes = self.defect_notes_input.toPlainText(
            ) if hasattr(self, 'defect_notes_input') else ''
            signature = self.inspection_signature_input.text() if hasattr(
                self, 'inspection_signature_input') else ''
            insp_date = (
                self.inspection_date_input.text()
                if hasattr(self, 'inspection_date_input')
                else datetime.now().strftime('%Y-%m-%d')
            )
            reserve = self.reserve_number_input.text() if hasattr(
                self, 'reserve_number_input') else ''
            exemptions = []
            if (
                hasattr(self, 'exemption_adverse_weather')
                and self.exemption_adverse_weather.isChecked()
            ):
                exemptions.append('Adverse Weather')
            if (
                hasattr(self, 'exemption_mechanical')
                and self.exemption_mechanical.isChecked()
            ):
                exemptions.append('Mechanical Emergency')
            if (
                hasattr(self, 'exemption_emergency')
                and self.exemption_emergency.isChecked()
            ):
                exemptions.append('Emergency Relief')
            if (
                hasattr(self, 'exemption_off_duty_deferral')
                and self.exemption_off_duty_deferral.isChecked()
            ):
                exemptions.append('Off-Duty Deferral Used')

            def cb(flag):
                return '☑' if flag else '☐'

            html = [
                "<html><head><meta charset='utf-8'><style>",
                "body{font-family:Arial;font-size:10pt;} h2{margin:4px 0;} "
                "table{border-collapse:collapse;} th,td{border:1px solid "
                "#999;padding:4px;font-size:10pt;} .lbl{font-weight:bold;} ."
                "row{margin-bottom:6px;}",
                "</style></head><body>",
                "<h2>Vehicle Inspection Form (Filled)</h2>",
                f"<div class='row'><span class='lbl'>Reserve #:</span> "
                f"{reserve} &nbsp; <span class='lbl'>Driver:</span> "
                f"{driver}</div>",
                f"<div class='row'><span class='lbl'>Vehicle #:</span> "
                f"{vehicle} &nbsp; <span class='lbl'>Plate:</span> "
                f"{plate}</div>",
                f"<div class='row'><span class='lbl'>Start Odo:</span> "
                f"{start_odo} &nbsp; <span class='lbl'>End Odo:</span> "
                f"{end_odo}</div>",
                f"<div class='row'><span class='lbl'>Inspection "
                f"Status:</span> {insp_status}</div>",
                "<div class='row'><span class='lbl'>Defects:</span> ",
                (
                    f"{cb(no_defects)} No Defects &nbsp; "
                    f"{cb(minor_def)} Minor Defects &nbsp; "
                    f"{cb(major_def)} Major Defects"
                ),
                "</div>"]

            # HTML-escape defect notes (cannot use backslash in f-string
            # expressions)
            escaped_notes = defect_notes.replace('<', '&lt;').replace(
                '>', '&gt;').replace('\n', '<br>')
            html.append(
                "<div class='row'><span class='lbl'>Defect Notes:</span>"
                f"<br>{escaped_notes}</div>"
            )

            html.extend([
                (
                    "<div class='row'><span class='lbl'>Exemptions:</span> "
                    f"{'; '.join(exemptions) if exemptions else 'None'}</div>"
                ),
                f"<div class='row'><span class='lbl'>Signature:</span> "
                f"{signature} &nbsp; <span class='lbl'>Date:</span> "
                f"{insp_date}</div>",
                "</body></html>"])

            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_driver = ''.join(ch for ch in driver if ch.isalnum(
            ) or ch in ('-', '_')).strip('_') or 'driver'
            safe_vehicle = ''.join(ch for ch in vehicle if ch.isalnum(
            ) or ch in ('-', '_')).strip('_') or 'vehicle'
            filename = f"Inspection_{safe_driver}_{safe_vehicle}_{ts}.pdf"
            out_path = os.path.join(out_dir, filename)

            from PyQt6.QtGui import QTextDocument
            from PyQt6.QtPrintSupport import QPrinter
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(out_path)
            doc = QTextDocument()
            doc.setHtml(''.join(html))
            doc.print(printer)

            self.current_inspection_form_path = out_path
            self.inspection_form_label.setText(f"✓ {filename}")
            self.inspection_form_label.setStyleSheet(
                "color: #080; font-weight: bold;")
            QMessageBox.information(
                self,
                "Inspection PDF",
                f"Inspection PDF saved to:\n{out_path}")
        except Exception as e:
            QMessageBox.warning(
                self,
                "Generate Error",
                f"Failed to generate inspection PDF: {e}")

    def _apply_manual_times(self):
        """Apply manual start/end and break to selected day; update grid and
        persist."""
        try:
            # Which day
            sel_idx = max(0, self.manual_day_combo.currentIndex())
            # Parse times

            def parse_hhmm(txt):
                parts = txt.strip().split(":")
                if len(parts) != 2:
                    raise ValueError("Invalid time format")
                h = int(parts[0])
                m = int(parts[1])
                if not (0 <= h <= 23 and 0 <= m <= 59):
                    raise ValueError("Out-of-range time")
                return h, m
            sh, sm = parse_hhmm(self.manual_start_input.text() or "08:00")
            eh, em = parse_hhmm(self.manual_end_input.text() or "17:00")
            try:
                break_hours = float(
                    (self.manual_break_input.text() or "0").strip())
                if break_hours < 0:
                    break_hours = 0.0
            except Exception:
                break_hours = 0.0
            # Compute elapsed (allow crossing midnight)
            d = self.hos_last14_dates[sel_idx]
            from datetime import datetime, timedelta
            start_dt = datetime(d.year, d.month, d.day, sh, sm)
            end_dt = datetime(d.year, d.month, d.day, eh, em)
            if end_dt <= start_dt:
                end_dt += timedelta(days=1)
            elapsed_hours = (end_dt - start_dt).total_seconds() / 3600.0
            on_hours = max(0.0, min(24.0, elapsed_hours - break_hours))
            off_hours = max(0.0, 24.0 - on_hours)
            # Update grid
            col_index = sel_idx  # columns: oldest..today, same order
            self.hos_table.item(1, col_index).setText(
                str(int(round(on_hours))))
            self.hos_table.item(0, col_index).setText(
                str(int(round(off_hours))))
            self.hos_table.item(2, col_index).setText("24")
            # Persist to DB (driver_hos_log) - replace existing for that day
            try:
                self.db.rollback()
            except Exception:
                pass
            cur = self.db.get_cursor()
            employee_id = self.driver_combo.currentData()
            if employee_id:
                cur.execute(
                    "DELETE FROM driver_hos_log WHERE employee_id = %s AND "
                    "shift_date = %s",
                    (employee_id, d),)
                cur.execute(
                    """
                    INSERT INTO driver_hos_log (
                        employee_id,
                        shift_date,
                        shift_start,
                        shift_end,
                        hours_on_duty,
                        hours_driven,
                        odometer_start,
                        odometer_end,
                        total_kms,
                        notes
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, NULL, NULL, NULL, %s)
                    """,
                    (
                        employee_id,
                        d,
                        start_dt,
                        end_dt,
                        on_hours,
                        0,
                        "Manual correction from dispatcher",),)
                self.db.commit()
            # Refresh totals/compliance
            self.update_hos_totals()
            QMessageBox.information(
                self, "HOS Updated", "Manual correction applied and saved.")
        except Exception as e:
            QMessageBox.warning(
                self,
                "Manual Entry Error",
                f"Failed to apply correction: {e}")

    def _add_receipt_entry(self):
        """Add receipt to the receipts table and update totals"""
        try:
            vendor = self.receipt_vendor_input.text().strip()
            desc = self.receipt_desc_input.text().strip()
            amount_text = self.receipt_amount_input.text(
            ).strip().replace('$', '').replace(',', '')

            if not vendor or not amount_text:
                QMessageBox.warning(
                    self, "Validation", "Vendor and amount are required")
                return

            try:
                amount = float(amount_text)
            except ValueError:
                QMessageBox.warning(
                    self, "Validation", "Invalid amount format")
                return

            # Add row to table
            row_count = self.receipts_table.rowCount()
            self.receipts_table.insertRow(row_count)

            # Vendor
            vendor_item = QTableWidgetItem(vendor)
            self.receipts_table.setItem(row_count, 0, vendor_item)

            # Description
            desc_item = QTableWidgetItem(desc)
            self.receipts_table.setItem(row_count, 1, desc_item)

            # Amount
            amount_item = QTableWidgetItem(f"${amount:.2f}")
            amount_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.receipts_table.setItem(row_count, 2, amount_item)

            # Delete button
            delete_btn = QPushButton("🗑")
            delete_btn.setMaximumWidth(30)
            delete_btn.clicked.connect(
                lambda checked, r=row_count: self._delete_receipt_row(r))
            self.receipts_table.setCellWidget(row_count, 3, delete_btn)

            # Clear inputs
            self.receipt_vendor_input.clear()
            self.receipt_desc_input.clear()
            self.receipt_amount_input.clear()

            # Update totals
            self._update_float_totals()

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to add receipt: {e}")

    def _delete_receipt_row(self, row):
        """Delete receipt row and update totals"""
        try:
            self.receipts_table.removeRow(row)
            self._update_float_totals()
        except Exception as e:
            QMessageBox.warning(
                self, "Error", f"Failed to delete receipt: {e}")

    def _update_float_totals(self):
        """Calculate receipt total and change returned"""
        try:
            # Calculate receipt total
            total_receipts = 0.0
            for row in range(self.receipts_table.rowCount()):
                amount_text = self.receipts_table.item(
                    row,
                    2).text().replace(
                    '$',
                    '').replace(
                    ',',
                    '')
                total_receipts += float(amount_text)

            self.receipt_total_label.setText(f"${total_receipts:.2f}")

            # Calculate change returned
            float_given_text = (
                self.float_given_input.text()
                .strip()
                .replace('$', '')
                .replace(',', '')
            )
            float_given = float(float_given_text) if float_given_text else 0.0

            change = float_given - total_receipts
            self.change_returned_label.setText(f"${change:.2f}")

            # Color code
            if change < 0:
                self.change_returned_label.setStyleSheet(
                    "font-weight: bold; color: #d00;")  # Red if overspent
            else:
                self.change_returned_label.setStyleSheet(
                    "font-weight: bold; color: #080;")  # Green

        except Exception:
            pass  # Silent fail on calculation errors

    def load_charter_types(self):
        """Load charter types from charter_types table for main Charter Type
        dropdown"""
        self.charter_type_combo.clear()
        try:
            try:
                self.db.rollback()
            except Exception:
                try:
                    self.db.rollback()
                except Exception:
                    pass
            cur = self.db.get_cursor()
            cur.execute("""
                SELECT type_code, type_name
                FROM charter_types
                WHERE is_active = true
                ORDER BY display_order
            """)
            rows = cur.fetchall()
            cur.close()
            for code, name in rows:
                label = f"{code} - {name}" if name else str(code)
                self.charter_type_combo.addItem(label, str(code or ""))
            if self.charter_type_combo.count() == 0:
                raise Exception("No charter types found")
        except Exception:
            # Fallback list if DB query fails
            fallback_types = [
                ("AIRPORT", "Airport Pickup"),
                ("EDMONTON", "Edmonton"),
                ("WEDDING", "Wedding"),
                ("CORP", "Corporate Event"),
                ("CONCERT", "Concert"),
                ("PROM", "Prom"),
                ("BACHELOR", "Bachelor Party"),
                ("TOUR", "Tour"),
                ("FUNERAL", "Funeral"),
                ("OTHER", "Other")]
            for code, name in fallback_types:
                self.charter_type_combo.addItem(f"{code} - {name}", code)

    def load_run_types(self):
        """Load run types from database or use defaults"""
        current_run_type = ""
        if hasattr(self, 'run_type_combo'):
            current_run_type = (self.run_type_combo.currentText() or "").strip()
        try:
            try:
                self.db.rollback()
            except Exception:
                pass

            cur = self.db.get_cursor()
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'charter_run_types')
            """)
            table_exists = cur.fetchone()[0]

            if table_exists:
                cur.execute("""
                    SELECT run_type_name
                    FROM charter_run_types
                    WHERE is_active = true
                    ORDER BY display_order, run_type_name
                """)
                run_types = [row[0] for row in cur.fetchall()]
            else:
                run_types = [
                    "Airport Pickup - Calgary",
                    "Airport Pickup - Edmonton",
                    "Airport Pickup - Red Deer",
                    "Airport Drop-off - Calgary",
                    "Airport Drop-off - Edmonton",
                    "Airport Drop-off - Red Deer",
                    "Airport Run",
                    "Corporate Travel",
                    "Guest Transportation",
                    "Wedding",
                    "Concert",
                    "Sporting Event",
                    "Charter",
                    "Christmas Party",
                    "Birthday Party",
                    "Graduation",
                    "Wine Tour",
                    "City Tour",
                    "Other"]

            self.run_type_combo.clear()
            self.run_type_combo.addItem("", None)  # Blank option
            for run_type in run_types:
                self.run_type_combo.addItem(run_type, run_type)

            if current_run_type:
                idx = self.run_type_combo.findText(current_run_type)
                if idx >= 0:
                    self.run_type_combo.setCurrentIndex(idx)

        except Exception:
            try:
                self.db.rollback()
            except Exception:
                pass
            default_types = [
                "Airport Pickup - Calgary",
                "Airport Pickup - Edmonton",
                "Airport Pickup - Red Deer",
                "Airport Drop-off - Calgary",
                "Airport Drop-off - Edmonton",
                "Airport Drop-off - Red Deer",
                "Airport Run",
                "Corporate Travel",
                "Guest Transportation",
                "Wedding",
                "Concert",
                "Sporting Event",
                "Charter",
                "Christmas Party",
                "Birthday Party",
                "Graduation",
                "Wine Tour",
                "City Tour",
                "Other"]
            self.run_type_combo.clear()
            self.run_type_combo.addItem("", None)
            for rt in default_types:
                self.run_type_combo.addItem(rt, rt)

            if current_run_type:
                idx = self.run_type_combo.findText(current_run_type)
                if idx >= 0:
                    self.run_type_combo.setCurrentIndex(idx)

    def open_run_type_editor(self):
        """Open editor for run types list (charter_run_types)."""
        from PyQt6.QtWidgets import (
            QAbstractItemDelegate,
            QDialog,
            QHBoxLayout,
            QLineEdit,
            QMessageBox,
            QPushButton,
            QTableWidget,
            QTableWidgetItem,
            QVBoxLayout,)

        try:
            cur = self.db.get_cursor()
            cur.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema='public' AND table_name='charter_run_types'
            """)
            cols = {r[0] for r in cur.fetchall()}

            if not cols:
                QMessageBox.warning(
                    self, "Run Types", "Table charter_run_types not found.")
                cur.close()
                return

            has_id = 'run_type_id' in cols
            has_active = 'is_active' in cols
            has_order = 'display_order' in cols

            select_cols = []
            if has_id:
                select_cols.append('run_type_id')
            select_cols.append('run_type_name')
            if has_active:
                select_cols.append('is_active')
            if has_order:
                select_cols.append('display_order')

            order_clause = (
                'display_order, run_type_name'
                if has_order
                else 'run_type_name'
            )

            cur.execute(f"""
                SELECT {', '.join(select_cols)}
                FROM charter_run_types
                ORDER BY {order_clause}
            """)
            rows = cur.fetchall()
            cur.close()

            dialog = QDialog(self)
            dialog.setWindowTitle("Edit Run Types")
            dialog.setMinimumWidth(500)

            layout = QVBoxLayout()
            table = QTableWidget()
            table.setColumnCount(3)
            table.setHorizontalHeaderLabels(["Run Type", "Active", "Order"])
            table.setRowCount(len(rows))

            for r_idx, row in enumerate(rows):
                col_offset = 0
                run_type_id = None
                if has_id:
                    run_type_id = row[0]
                    col_offset = 1

                name_val = row[col_offset]
                active_val = row[col_offset + 1] if has_active else True
                order_val = row[col_offset + 2] if has_order else (r_idx + 1)

                name_item = QTableWidgetItem(name_val or "")
                if run_type_id is not None:
                    name_item.setData(Qt.ItemDataRole.UserRole, run_type_id)
                table.setItem(r_idx, 0, name_item)

                active_item = QTableWidgetItem("")
                active_item.setFlags(
                    active_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                active_item.setCheckState(
                    Qt.CheckState.Checked
                    if active_val
                    else Qt.CheckState.Unchecked
                )
                table.setItem(r_idx, 1, active_item)

                order_item = QTableWidgetItem(
                    str(order_val if order_val is not None else ""))
                table.setItem(r_idx, 2, order_item)

            layout.addWidget(table)

            btn_row = QHBoxLayout()
            add_btn = QPushButton("Add")
            del_btn = QPushButton("Delete")
            save_btn = QPushButton("Save")
            cancel_btn = QPushButton("Cancel")

            def add_row():
                row = table.rowCount()
                table.insertRow(row)
                table.setItem(row, 0, QTableWidgetItem(""))
                active_item = QTableWidgetItem("")
                active_item.setFlags(
                    active_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                active_item.setCheckState(Qt.CheckState.Checked)
                table.setItem(row, 1, active_item)
                table.setItem(row, 2, QTableWidgetItem(str(row + 1)))

            def delete_row():
                row = table.currentRow()
                if row >= 0:
                    table.removeRow(row)

            def save_rows():
                try:
                    # Commit any in-progress inline edit before reading cells.
                    editor = table.focusWidget()
                    if isinstance(editor, QLineEdit):
                        try:
                            table.itemDelegate().commitData.emit(editor)
                            table.itemDelegate().closeEditor.emit(
                                editor,
                                QAbstractItemDelegate.EndEditHint.NoHint,
                            )
                        except Exception:
                            pass

                    selected_before_save = (
                        self.run_type_combo.currentText().strip()
                        if hasattr(self, 'run_type_combo')
                        else ""
                    )
                    cur = self.db.get_cursor()

                    if has_id:
                        cur.execute(
                            "SELECT run_type_id FROM charter_run_types"
                        )
                        db_ids_before = {r[0] for r in cur.fetchall()}
                        existing_ids = set()
                        for row in range(table.rowCount()):
                            name_item = table.item(row, 0)
                            if not name_item:
                                continue
                            run_type_name = (name_item.text() or "").strip()
                            if not run_type_name:
                                continue

                            active_item = table.item(row, 1)
                            is_active = True if not has_active else (
                                active_item.checkState()
                                == Qt.CheckState.Checked)
                            order_item = table.item(row, 2)
                            display_order = int(
                                order_item.text() or (
                                    row + 1)) if has_order else None

                            run_type_id = name_item.data(
                                Qt.ItemDataRole.UserRole)
                            if run_type_id:
                                existing_ids.add(run_type_id)
                                if has_active and has_order:
                                    cur.execute(
                                        "UPDATE charter_run_types SET "
                                        "run_type_name=%s, is_active=%s, "
                                        "display_order=%s WHERE "
                                        "run_type_id=%s",
                                        (
                                            run_type_name,
                                            is_active,
                                            display_order,
                                            run_type_id,
                                        ),
                                    )
                                elif has_active:
                                    cur.execute(
                                        "UPDATE charter_run_types SET "
                                        "run_type_name=%s, is_active=%s WHERE "
                                        "run_type_id=%s",
                                        (run_type_name,
                                         is_active, run_type_id))
                                elif has_order:
                                    cur.execute(
                                        "UPDATE charter_run_types SET "
                                        "run_type_name=%s, display_order=%s "
                                        "WHERE run_type_id=%s",
                                        (run_type_name,
                                         display_order, run_type_id))
                                else:
                                    cur.execute(
                                        "UPDATE charter_run_types SET "
                                        "run_type_name=%s WHERE "
                                        "run_type_id=%s",
                                        (run_type_name, run_type_id))
                            else:
                                if has_active and has_order:
                                    cur.execute(
                                        "INSERT INTO charter_run_types "
                                        "(run_type_name, is_active, "
                                        "display_order) VALUES (%s, %s, %s)",
                                        (run_type_name, is_active,
                                         display_order))
                                elif has_active:
                                    cur.execute(
                                        "INSERT INTO charter_run_types "
                                        "(run_type_name, is_active) VALUES "
                                        "(%s, %s)",
                                        (run_type_name, is_active))
                                elif has_order:
                                    cur.execute(
                                        "INSERT INTO charter_run_types "
                                        "(run_type_name, display_order) "
                                        "VALUES (%s, %s)",
                                        (run_type_name, display_order))
                                else:
                                    cur.execute(
                                        "INSERT INTO charter_run_types "
                                        "(run_type_name) VALUES (%s)",
                                        (run_type_name,),
                                    )

                        # Remove any rows deleted in UI
                        to_delete = db_ids_before - existing_ids
                        if to_delete:
                            cur.execute(
                                "DELETE FROM charter_run_types WHERE "
                                "run_type_id = ANY(%s)",
                                (list(to_delete),)
                            )
                    else:
                        # No PK - replace all
                        cur.execute("DELETE FROM charter_run_types")
                        for row in range(table.rowCount()):
                            name_item = table.item(row, 0)
                            if not name_item:
                                continue
                            run_type_name = (name_item.text() or "").strip()
                            if not run_type_name:
                                continue

                            active_item = table.item(row, 1)
                            is_active = True if not has_active else (
                                active_item.checkState()
                                == Qt.CheckState.Checked)
                            order_item = table.item(row, 2)
                            display_order = int(
                                order_item.text() or (
                                    row + 1)) if has_order else None

                            if has_active and has_order:
                                cur.execute(
                                    "INSERT INTO charter_run_types "
                                    "(run_type_name, is_active, "
                                    "display_order) VALUES (%s, %s, %s)",
                                        (run_type_name,
                                         is_active, display_order))
                            elif has_active:
                                cur.execute(
                                    "INSERT INTO charter_run_types "
                                    "(run_type_name, is_active) VALUES (%s, "
                                    "%s)",
                                    (run_type_name, is_active))
                            elif has_order:
                                cur.execute(
                                    "INSERT INTO charter_run_types "
                                    "(run_type_name, display_order) VALUES "
                                    "(%s, %s)",
                                    (run_type_name, display_order))
                            else:
                                cur.execute(
                                    "INSERT INTO charter_run_types "
                                    "(run_type_name) VALUES (%s)",
                                    (run_type_name,),
                                )

                    self.db.commit()
                    QMessageBox.information(
                        dialog, "Run Types", "Saved run types successfully.")
                    dialog.accept()
                    self.load_run_types()
                    if selected_before_save and hasattr(self, 'run_type_combo'):
                        idx = self.run_type_combo.findText(selected_before_save)
                        if idx >= 0:
                            self.run_type_combo.setCurrentIndex(idx)
                except Exception as e:
                    try:
                        self.db.rollback()
                    except Exception:
                        pass
                    QMessageBox.critical(
                        dialog, "Run Types", f"Failed to save run types: {e}")

            add_btn.clicked.connect(add_row)
            del_btn.clicked.connect(delete_row)
            save_btn.clicked.connect(save_rows)
            cancel_btn.clicked.connect(dialog.reject)

            btn_row.addWidget(add_btn)
            btn_row.addWidget(del_btn)
            btn_row.addStretch()
            btn_row.addWidget(save_btn)
            btn_row.addWidget(cancel_btn)
            layout.addLayout(btn_row)

            dialog.setLayout(layout)
            dialog.exec()

        except Exception as e:
            QMessageBox.critical(
                self, "Run Types", f"Failed to load run types: {e}")

    def _build_hos_log_html(self):
        try:
            driver = getattr(self, 'driver_info_name_label', QLabel('')).text()
        except Exception:
            driver = ''
        status = self.hos_compliance_label.text() if hasattr(
            self, 'hos_compliance_label') else ''

        def row_html(label, row_idx):
            total = 0
            cells = []
            for col_idx in range(14):
                val = int(self.hos_table.item(row_idx, col_idx).text() or 0)
                total += val
                cells.append(f"<td>{val}</td>")
            cells.append(f"<td><b>{total}</b></td>")
            return f"<tr><th>{label}</th>{''.join(cells)}</tr>"

        header_dates = ''.join(
            f"<th>{self.hos_last14_dates[c].strftime('%Y-%m-%d')}</th>"
            for c in range(14)
        )
        html = [
            "<html><head><meta charset='utf-8'><style>"
            "table{border-collapse:collapse;font-family:Arial;font-size:10pt;}"
            "th,td{border:1px solid #888;padding:4px;text-align:center;}"
            "h2{font-family:Arial;}"
            "</style></head><body>",
            f"<h2>HOS Log (Last 14 Days) - {driver}</h2>",
            f"<p><b>Status:</b> {status}</p>",
            f"<table><tr><th>Day</th>{header_dates}<th>Total</th></tr>",
            row_html("Off-Duty", 0),
            row_html("On-Duty", 1),
            row_html("Total (24h)", 2),
            "</table></body></html>"]
        return ''.join(html)

    def _export_hos_log_pdf(self):
        """Export the last 14 days HOS log to a PDF file and show its path."""
        try:
            out_dir = os.path.join(project_root, 'reports', 'hos_logs')
            os.makedirs(out_dir, exist_ok=True)

            driver = getattr(self, 'driver_info_name_label',
                             QLabel('')).text() or 'driver'
            safe_driver = ''.join(
                ch for ch in driver if ch.isalnum() or ch in (
                    '-', '_')).strip('_') or 'driver'
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            out_path = os.path.join(out_dir, f"HOS_{safe_driver}_{ts}.pdf")

            from PyQt6.QtGui import QTextDocument
            from PyQt6.QtPrintSupport import QPrinter
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(out_path)
            doc = QTextDocument()
            doc.setHtml(self._build_hos_log_html())
            doc.print(printer)

            QMessageBox.information(
                self, 'PDF Exported', f'PDF saved to:\n{out_path}')
            return out_path
        except Exception as e:
            QMessageBox.warning(
                self,
                'Export Error',
                f'Failed to export PDF: {e}')
            return None

    def _email_hos_pdf(self):
        """Prompt for email address and send HOS PDF as attachment via SMTP."""
        try:
            to_addr, ok = QInputDialog.getText(
                self, 'Send HOS by Email', 'Recipient email:')
            if not ok or not to_addr.strip():
                return
            pdf_path = self._export_hos_log_pdf()
            if not pdf_path:
                return
            subject = 'HOS Log (Last 14 Days)'
            body = 'Attached: HOS log PDF for the last 14 days.'
            self._send_email_with_attachment(
                to_addr.strip(), subject, body, pdf_path)
            QMessageBox.information(
                self, 'Email Sent', f'HOS PDF emailed to {to_addr.strip()}')
        except Exception as e:
            QMessageBox.warning(self, 'Email Error',
                                f'Failed to send email: {e}')

    def _text_hos_pdf(self):
        """Prompt for MMS/SMS email gateway address and send PDF (carrier
        dependent)."""
        try:
            prompt = 'Enter MMS/SMS email (e.g., 4035551234@mms.carrier.com):'
            to_addr, ok = QInputDialog.getText(
                self, 'Send HOS by Text', prompt)
            if not ok or not to_addr.strip():
                return
            pdf_path = self._export_hos_log_pdf()
            if not pdf_path:
                return
            subject = 'HOS Log PDF'
            body = (
                "Attached: HOS log PDF. Delivery depends on carrier "
                "MMS gateway."
            )
            self._send_email_with_attachment(
                to_addr.strip(), subject, body, pdf_path)
            QMessageBox.information(
                self,
                'Text Sent',
                f'HOS PDF sent to {to_addr.strip()} (via MMS gateway)',
            )
        except Exception as e:
            QMessageBox.warning(self, 'Text Error',
                                f'Failed to send text: {e}')

    def _send_email_with_attachment(
        self, to_address: str, subject: str, body: str, attachment_path: str):
        host = os.environ.get('SMTP_HOST')
        port = int(os.environ.get('SMTP_PORT', '587'))
        user = os.environ.get('SMTP_USER')
        password = os.environ.get('SMTP_PASSWORD')
        use_tls = os.environ.get(
            'SMTP_USE_TLS', 'true').lower() in (
            '1', 'true', 'yes')
        use_ssl = os.environ.get(
            'SMTP_USE_SSL', 'false').lower() in (
            '1', 'true', 'yes')
        from_addr = os.environ.get('SMTP_FROM', user or 'noreply@example.com')

        if not host or not user or not password:
            raise RuntimeError(
                'Missing SMTP configuration '
                '(SMTP_HOST, SMTP_USER, SMTP_PASSWORD).')

        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = from_addr
        msg['To'] = to_address
        msg.set_content(body)
        with open(attachment_path, 'rb') as f:
            data = f.read()
        filename = os.path.basename(attachment_path)
        msg.add_attachment(
            data,
            maintype='application',
            subtype='pdf',
            filename=filename)

        if use_ssl:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, context=context) as server:
                server.login(user, password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port) as server:
                if use_tls:
                    server.starttls(context=ssl.create_default_context())
                server.login(user, password)
                server.send_message(msg)

    def _print_monthly_hos_form(self):
        """Open/print the driver's monthly HOS form template."""
        try:
            form_path = os.path.join(
                project_root,
                'forms',
                'Drivers Monthly Hours of service Record.docx')
            if not os.path.exists(form_path):
                QMessageBox.warning(
                    self, 'Missing Form', f'Form not found:\n{form_path}')
                return
            self._open_file_default(form_path, print_mode=False)
        except Exception as e:
            QMessageBox.warning(
                self, 'Form Error', f'Failed to open HOS form: {e}')

    def _print_daily_inspection_form(self):
        """Open the blank daily trip inspection PDF template."""
        try:
            template_path = r"L:\Confirmation\Daily trip inspection record.pdf"
            if not os.path.exists(template_path):
                QMessageBox.warning(
                    self,
                    'Missing Form',
                    f'Form not found:\n{template_path}')
                return

            self._open_file_default(template_path, print_mode=False)
        except Exception as e:
            QMessageBox.warning(
                self,
                'Form Error',
                f'Failed to open inspection form: {e}')

    def _get_selected_driver_name(self) -> str:
        # Prefer canonical full name from employees by selected driver id.
        if hasattr(self, 'driver_combo'):
            employee_id = self.driver_combo.currentData()
            if employee_id:
                try:
                    cur = self.db.get_cursor()
                    cur.execute(
                        """
                        SELECT COALESCE(first_name, ''), COALESCE(last_name, '')
                        FROM employees
                        WHERE employee_id = %s
                        """,
                        (employee_id,),
                    )
                    row = cur.fetchone()
                    cur.close()
                    if row:
                        full_name = f"{(row[0] or '').strip()} {(row[1] or '').strip()}".strip()
                        if full_name:
                            return full_name
                except Exception:
                    try:
                        self.db.rollback()
                    except Exception:
                        pass

        # Legacy fallback: resolve from driver code/text (e.g., Dr09).
        legacy_code = ""
        if hasattr(self, 'driver_combo'):
            name = (self.driver_combo.currentText() or '').strip()
            if name and name != '(None)':
                legacy_code = name
                # If it already looks like a full name, use it directly.
                if " " in name:
                    return name
        if legacy_code:
            try:
                cur = self.db.get_cursor()
                cur.execute(
                    """
                    SELECT COALESCE(first_name, ''), COALESCE(last_name, '')
                    FROM employees
                          WHERE lower(COALESCE(driver_code::text, '')) = lower(%s)
                              OR lower(COALESCE(employee_number::text, '')) = lower(%s)
                              OR lower(COALESCE(legacy_employee::text, '')) = lower(%s)
                              OR lower(COALESCE(legacy_name::text, '')) = lower(%s)
                              OR lower(COALESCE(name::text, '')) = lower(%s)
                              OR lower(COALESCE(full_name::text, '')) = lower(%s)
                    LIMIT 1
                    """,
                    (
                        legacy_code,
                        legacy_code,
                        legacy_code,
                        legacy_code,
                        legacy_code,
                        legacy_code,
                    ),
                )
                row = cur.fetchone()
                cur.close()
                if row:
                    full_name = f"{(row[0] or '').strip()} {(row[1] or '').strip()}".strip()
                    if full_name:
                        return full_name
            except Exception:
                try:
                    self.db.rollback()
                except Exception:
                    pass
            return legacy_code
        if hasattr(self, 'inspection_signature_input'):
            name = (self.inspection_signature_input.text() or '').strip()
            if name:
                return name
        return 'Driver'

    def _get_driver_code_for_inspection(self) -> str:
        """Return the employee number / driver badge code for the driver number field."""
        if hasattr(self, 'driver_combo'):
            employee_id = self.driver_combo.currentData()
            if employee_id:
                try:
                    cur = self.db.get_cursor()
                    cur.execute(
                        "SELECT COALESCE(employee_number::text, COALESCE(driver_code::text, '')) "
                        "FROM employees WHERE employee_id = %s",
                        (employee_id,),
                    )
                    row = cur.fetchone()
                    cur.close()
                    if row and (row[0] or '').strip():
                        return row[0].strip()
                except Exception:
                    try:
                        self.db.rollback()
                    except Exception:
                        pass
            # Fallback: use the combo display text if it looks like a code
            name = (self.driver_combo.currentText() or '').strip()
            if name and name != '(None)' and ' ' not in name:
                return name
        return ''

    def _get_inspection_date_parts_from_charter(self):
        # Charter date should drive inspection date and be split as month/day/year.
        if hasattr(self, 'charter_date_from'):
            try:
                d = self.charter_date_from.date()
                return d.toString('MMMM'), d.toString('dd'), d.toString('yyyy')
            except Exception:
                pass
        if hasattr(self, 'pickup_datetime'):
            try:
                d = self.pickup_datetime.date()
                return d.toString('MMMM'), d.toString('dd'), d.toString('yyyy')
            except Exception:
                pass
        if hasattr(self, 'inspection_date_input'):
            existing = (self.inspection_date_input.text() or '').strip()
            if existing:
                try:
                    dt = datetime.strptime(existing, '%m/%d/%Y')
                    return dt.strftime('%B'), dt.strftime('%d'), dt.strftime('%Y')
                except ValueError:
                    pass
        now = datetime.now()
        return now.strftime('%B'), now.strftime('%d'), now.strftime('%Y')

    def _get_shift_start_time_for_inspection(self) -> str:
        # Time of inspection is the work shift start time.
        for attr_name in ('on_duty_time_input', 'manual_start_input', 'inspection_time_input'):
            widget = getattr(self, attr_name, None)
            if widget is None:
                continue
            try:
                text = (widget.text() or '').strip()
                if text:
                    return text
            except Exception:
                pass
        if hasattr(self, 'base_time_from'):
            try:
                return self.base_time_from.time().toString('HH:mm')
            except Exception:
                pass
        return datetime.now().strftime('%H:%M')

    @staticmethod
    def _normalize_hhmm(time_text: str) -> str:
        text = (time_text or '').strip()
        if not text:
            return datetime.now().strftime('%H:%M')
        if len(text) >= 5 and text[2] == ':':
            return text[:5]
        return text

    def _get_vehicle_id_for_inspection(self) -> str:
        if hasattr(self, 'vehicle_combo'):
            vehicle_id = self.vehicle_combo.currentData()
            if vehicle_id:
                try:
                    cur = self.db.get_cursor()
                    cur.execute(
                        "SELECT COALESCE(vehicle_number, '') FROM vehicles WHERE vehicle_id = %s",
                        (vehicle_id,),
                    )
                    row = cur.fetchone()
                    cur.close()
                    if row and row[0]:
                        return self._normalize_vehicle_number(str(row[0]))
                except Exception:
                    try:
                        self.db.rollback()
                    except Exception:
                        pass
        if hasattr(self, 'vehicle_number_input'):
            vehicle_num = (self.vehicle_number_input.text() or '').strip()
            if vehicle_num:
                return self._normalize_vehicle_number(vehicle_num)
        if hasattr(self, 'vehicle_combo'):
            label = (self.vehicle_combo.currentText() or '').strip()
            if label:
                return self._normalize_vehicle_number(label.split(' - ')[0].strip())
        return 'Vehicle'

    @staticmethod
    def _normalize_vehicle_number(value: str) -> str:
        text = (value or '').strip()
        upper = text.upper()
        digits = ''.join(ch for ch in text if ch.isdigit())
        if upper.startswith('LIMO') and digits:
            return f"L-{digits.zfill(2)}"
        if upper.startswith('L-') and digits:
            return f"L-{digits.zfill(2)}"
        if upper.startswith('L') and digits:
            return f"L-{digits.zfill(2)}"
        return text

    def _open_file_default(self, path, print_mode=False):
        """Open or print a file via OS default application."""
        try:
            import platform
            if platform.system() == 'Windows':
                if print_mode:
                    os.startfile(path, 'print')
                else:
                    os.startfile(path)
            elif platform.system() == 'Darwin':
                import subprocess
                if print_mode:
                    subprocess.Popen(['open', '-P', path])
                else:
                    subprocess.Popen(['open', path])
            else:
                import subprocess
                if print_mode:
                    subprocess.Popen(['xdg-open', path])
                else:
                    subprocess.Popen(['xdg-open', path])
        except Exception as e:
            QMessageBox.warning(
                self, 'Open Error', f'Failed to open file: {e}')

    def _mark_inspection_completed_online(self):
        """Record online completion with signature/name and timestamp."""
        try:
            name, ok = QInputDialog.getText(
                self, 'Inspection Sign-O',
                'Driver/Inspector name (signature):')
            if not ok or not name.strip():
                return
            ts = datetime.now().strftime('%Y-%m-%d %H:%M')
            note = f"Completed online by {name.strip()} @ {ts}"
            self.inspection_form_label.setText(note)
            self.inspection_form_label.setStyleSheet(
                'color: #080; font-weight: bold;')
            self.current_inspection_form_path = note
            QMessageBox.information(self, 'Inspection Recorded', note)
        except Exception as e:
            QMessageBox.warning(
                self,
                'Sign-Off Error',
                f'Failed to record completion: {e}')

    def load_vehicle_types_requested(self):
        """Load generic vehicle type options (customer request, not dispatch
        vehicle)"""
        try:
            try:
                self.db.rollback()
            except Exception:
                pass

            # Get distinct vehicle types from pricing defaults ONLY
            # (authoritative list)
            cur = self.db.get_cursor()
            cur.execute("""
                SELECT DISTINCT vehicle_type
                FROM vehicle_pricing_defaults
                WHERE vehicle_type IS NOT NULL AND vehicle_type != ''
                ORDER BY vehicle_type
            """)
            vehicle_types = sorted([row[0] for row in cur.fetchall()])
            cur.close()

            self.vehicle_type_requested_combo.clear()
            self.vehicle_type_requested_combo.addItem("", None)  # Blank option
            for vtype in vehicle_types:
                self.vehicle_type_requested_combo.addItem(vtype, vtype)

        except Exception:
            try:
                self.db.rollback()
            except Exception:
                pass
            # Use pricing defaults as fallback on error
            default_types = [
                "Luxury Sedan (4 pax)",
                "Luxury SUV (3-4 pax)",
                "Sedan (3-4 pax)",
                "Sedan Stretch (6 Pax)",
                "Party Bus (20 pax)",
                "Party Bus (27 pax)",
                "Shuttle Bus (18 pax)",
                "SUV Stretch (13 pax)"]
            self.vehicle_type_requested_combo.clear()
            self.vehicle_type_requested_combo.addItem("", None)
            for vt in default_types:
                self.vehicle_type_requested_combo.addItem(vt, vt)

    def load_route_event_types(self):
        """Load route event types from database for dropdown"""
        try:
            try:
                self.db.rollback()
            except Exception:
                pass
            cur = self.db.get_cursor()
            cur.execute("""
                SELECT event_code, event_name, clock_action, affects_billing
                FROM route_event_types
                WHERE is_active = TRUE
                ORDER BY display_order
            """)
            self._route_event_types = cur.fetchall()
            # Ensure Depart/Return Red Deer options exist even if DB is missing
            # them
            existing_codes = {code for code, _,
                              _, _ in self._route_event_types}
            if "depart_red_deer" not in existing_codes:
                self._route_event_types.insert(
                    0, ("depart_red_deer", "Depart Red Deer for",
                        "start", True))
            if "return_red_deer" not in existing_codes:
                self._route_event_types.append(
                    ("return_red_deer", "Return to Red Deer", "stop", True))
            cur.close()
        except Exception:
            # Fallback to defaults if table doesn't exist yet
            self._route_event_types = [
                ('depart_red_deer', 'Depart Red Deer for', 'start', True),
                ('return_red_deer', 'Return to Red Deer', 'stop', True),
                ('pickup', 'Pickup Client', 'start', True),
                ('dropo', 'Drop-off Client', 'stop', True),
                ('split_start', 'Split Run - Drop-o', 'stop', True),
                ('split_return', 'Split Run - Pickup', 'start', True),
                ('driver_standby', 'Driver Standby', 'pause', True),
                ('driver_waiting', 'Driver Waiting', 'pause', True),
                ('breakdown', 'Vehicle Breakdown', 'pause', False),
                ('new_vehicle', 'New Vehicle Arrives', 'resume', True),
                ('package_start', 'Package - Service Start', 'start', False),
                ('package_end', 'Package - Service End', 'stop', False),
                ('extra_time', 'Extra Time (Beyond Package)', 'resume', True),
                ('resume_service', 'Resume Service', 'resume', True),
                ('custom', 'Custom Event', 'none', False),]
            try:
                self.db.rollback()
            except Exception:
                pass

    def add_route_line(self, insert_at_row: int = -1):
        """Add new child stop with dropdown selection - inserts before Drop-off
        Client (last row)"""
        from PyQt6.QtWidgets import QComboBox, QTimeEdit

        # Always insert before the last row (Drop-off Client row)
        last_row_index = self.route_table.rowCount() - 1
        # Insert at this position (pushes Drop-off down)
        insert_position = last_row_index

        self.route_table.insertRow(insert_position)
        row = insert_position

        # Column 0: Dropdown selection list (Stop 1, Stop 2 naming for
        # database/printout)
        stop_combo = QComboBox()
        for (event_code, event_name,
             clock_action, affects_billing) in self._route_event_types:
            stop_combo.addItem(event_name, event_code)
        # Default to first available event
        stop_combo.currentIndexChanged.connect(
            lambda idx: self.calculate_route_billing())
        self.route_table.setCellWidget(row, 0, stop_combo)

        # Column 1: Details (location/description) - editable
        self.route_table.setItem(row, 1, QTableWidgetItem(""))

        # Column 2: at/by dropdown
        at_by_combo = QComboBox()
        at_by_combo.addItems(["at", "by"])
        self.route_table.setCellWidget(row, 2, at_by_combo)

        # Column 3: Time (with QTimeEdit for editing)
        time_edit = QTimeEdit()
        time_edit.setDisplayFormat("HH:mm")
        # Default to current time
        time_edit.setTime(QTime.currentTime())
        time_edit.timeChanged.connect(
            lambda *_: self.calculate_route_billing())
        self.route_table.setCellWidget(row, 3, time_edit)

        # Column 4: Driver Comments (editable)
        self.route_table.setItem(row, 4, QTableWidgetItem(""))

    def delete_route_line(self, row: int):
        """Delete a route event line with confirmation"""
        if self.route_table.rowCount() <= 1:
            QMessageBox.warning(
                self,
                "Cannot Delete",
                "Cannot delete the last route event.")
            return

        reply = QMessageBox.question(
            self, "Delete Route Event",
            "Delete this route event?",
            ((QMessageBox.StandardButton.Yes
             | QMessageBox.StandardButton.No)),
            QMessageBox.StandardButton.No)

        if reply != QMessageBox.StandardButton.Yes:
            return

        self.route_table.removeRow(row)

    def delete_selected_route_line(self):
        """Delete the currently selected route line (only middle rows, not
        first/last)"""
        current_row = self.route_table.currentRow()
        if current_row < 0:
            QMessageBox.information(
                self,
                "No Selection",
                "Please select a route event to delete.")
            return

        # Prevent deleting first row (Depart) or last row (Return/Drop-off)
        if current_row == 0:
            QMessageBox.warning(
                self,
                "Cannot Delete",
                "Cannot delete the first (Depart) route event.")
            return

        if current_row == self.route_table.rowCount() - 1:
            QMessageBox.warning(
                self,
                "Cannot Delete",
                "Cannot delete the last (Return/Drop-off) route event.")
            return

        reply = QMessageBox.question(self, "Delete Route Event",
                                     "Delete this route event?",
                                     (QMessageBox.StandardButton.Yes
             | QMessageBox.StandardButton.No),
                                     QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            self.route_table.removeRow(current_row)
            self.calculate_route_billing()

    def move_route_up(self):
        """Move selected route event up (only middle rows)"""
        current_row = self.route_table.currentRow()
        if current_row <= 1:  # Can't move row 0 (Depart) or move above row 1
            QMessageBox.warning(
                self,
                "Cannot Move",
                "Cannot move the first row or move above it.")
            return

        self._swap_route_rows(current_row, current_row - 1)

    def move_route_down(self):
        """Move selected route event down (only middle rows)"""
        current_row = self.route_table.currentRow()
        last_row = self.route_table.rowCount() - 1

        if current_row < 0 or current_row >= last_row - \
                1:  # Can't move last row or move to/past it
            QMessageBox.warning(
                self,
                "Cannot Move",
                "Cannot move the last row or move below it.")
            return

        self._swap_route_rows(current_row, current_row + 1)

    def _swap_route_rows(self, row1: int, row2: int):
        """Swap two route rows maintaining all cell data and auto-renumber
        stops"""
        # Save all data from row1
        row1_data = []
        for col in range(self.route_table.columnCount()):
            widget = self.route_table.cellWidget(row1, col)
            item = self.route_table.item(row1, col)
            if widget:
                row1_data.append(('widget', widget))
            elif item:
                row1_data.append(('item', QTableWidgetItem(item)))
            else:
                row1_data.append((None, None))

        # Save all data from row2
        row2_data = []
        for col in range(self.route_table.columnCount()):
            widget = self.route_table.cellWidget(row2, col)
            item = self.route_table.item(row2, col)
            if widget:
                row2_data.append(('widget', widget))
            elif item:
                row2_data.append(('item', QTableWidgetItem(item)))
            else:
                row2_data.append((None, None))

        # Swap: place row2 into row1
        for col in range(self.route_table.columnCount()):
            cell_type, cell_data = row2_data[col]
            if cell_type == 'widget':
                self.route_table.setCellWidget(row1, col, cell_data)
            elif cell_type == 'item':
                self.route_table.setItem(row1, col, cell_data)

        # Place row1 into row2
        for col in range(self.route_table.columnCount()):
            cell_type, cell_data = row1_data[col]
            if cell_type == 'widget':
                self.route_table.setCellWidget(row2, col, cell_data)
            elif cell_type == 'item':
                self.route_table.setItem(row2, col, cell_data)

        # Swap complete - all cell data preserved
        # Select the moved row
        self.route_table.setCurrentCell(row2, 0)
        self.calculate_route_billing()

    def _renumber_route_stops(self):
        """Auto-renumber middle rows as Stop 1, Stop 2, etc."""
        for row in range(1, self.route_table.rowCount() - 1):
            stop_label = QTableWidgetItem(f"Stop {row}")
            stop_label.setFlags(
                stop_label.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.route_table.setItem(row, 0, stop_label)

    def calculate_route_billing(self):
        """
        Simplified billing calculation - from first line to last line.

        Billing Logic:
        - Start at top line (first event/time)
        - Calculate through each event to the last line
        - Last line determines end time (Drop off at OR Return to Red Deer By)
        - Extra time events calculate from their time to end time
        - Auto-populate invoice charges based on time calculations
        """
        if self.route_table.rowCount() == 0:
            return

        from datetime import datetime, timedelta

        # Get rate information
        try:
            quoted_hourly = float(
                self.quoted_hourly_price.text().replace(
                    "$", "").replace(
                    ",", "")) if self.quoted_hourly_price.text() else 0.0
        except Exception:
            quoted_hourly = 0.0

        try:
            price_text = self.extended_hourly_price.text()
            if (self.extended_hourly_checkbox.isChecked()
                    and price_text):
                extended_hourly = float(
                    price_text.replace("$", "").replace(",", ""))
            else:
                extended_hourly = 0.0
        except Exception:
            extended_hourly = 0.0

        # Find start and end times
        start_time = None
        end_time = None
        extra_time_events = []

        for row in range(self.route_table.rowCount()):
            # Time column may be a QTimeEdit or plain item
            time_widget = self.route_table.cellWidget(row, 3)
            if hasattr(time_widget, 'time'):
                time_obj = time_widget.time()
                time_str = time_obj.toString("HH:mm")
            else:
                time_item = self.route_table.item(row, 3)
                if not time_item:
                    continue
                time_str = time_item.text().strip()
            if not time_str:
                continue

            event_combo = self.route_table.cellWidget(row, 0)
            event_name = (
                event_combo.currentText().upper()
                if event_combo else "")

            # First time is start
            if start_time is None:
                start_time = time_str

            # Last time is always end (whether Drop off or Return to Red Deer)
            end_time = time_str

            # Track extra time events (not start/end events)
            if ("EXTRA" in event_name or "OVERTIME" in event_name
                    or "ADDITIONAL" in event_name):
                extra_time_events.append((row, time_str))

        # Calculate total billable time from start to end
        if start_time and end_time:
            try:
                start = datetime.strptime(start_time, "%H:%M")
                end = datetime.strptime(end_time, "%H:%M")

                # Handle overnight
                if end < start:
                    end += timedelta(days=1)

                total_hours = (end - start).total_seconds() / 3600

                # Calculate base charge
                base_charge = (total_hours * quoted_hourly
                               if quoted_hourly > 0 else 0.0)

                # Calculate extra time charges if any extra events
                extra_charges = 0.0
                for row, extra_time_str in extra_time_events:
                    try:
                        extra_start = datetime.strptime(
                            extra_time_str, "%H:%M")
                        if end < extra_start:
                            extra_start += timedelta(days=1)
                        extra_hours = (
                            end - extra_start).total_seconds() / 3600
                        if extra_hours > 0 and extended_hourly > 0:
                            extra_charges += extra_hours * extended_hourly
                    except Exception:
                        pass

                # Auto-populate charges table
                self._update_invoice_charges(
                    base_charge, extra_charges, total_hours)

            except ValueError:
                pass  # Invalid time format

    def _update_invoice_charges(
            self,
            base_charge: float,
            extra_charge: float,
            total_hours: float):
        """Auto-populate charges from vehicle pricing defaults and routing
        calculation."""
        self._calculated_base_charge = base_charge
        self._calculated_extra_charge = extra_charge
        self._calculated_total_hours = total_hours

        # Auto-populate charges table from vehicle pricing if user hasn't
        # manually entered amounts
        try:
            vehicle_type = (
                self.vehicle_type_label.text().strip()
                if hasattr(self, 'vehicle_type_label') else "")
            if not vehicle_type or vehicle_type == "(Not assigned)":
                return

            pricing = self._load_pricing_defaults(vehicle_type)
            if not pricing:
                return

            # NRR is a MINIMUM charge, not a blocker - continue to populate
            # charges
            # Clear charges and rebuild from pricing
            self.charges_table.setRowCount(0)

            # Charter Charge (Hourly: rate × calculated hours)
            hourly_rate = pricing.get("hourly_rate", 0.0)
            if hourly_rate > 0 and total_hours > 0:
                self.add_charge_line(
                    description="Charter Charge",
                    calc_type="Hourly",
                    value=hourly_rate)

            # Standby fee (if standby_rate set)
            standby_rate = pricing.get("standby_rate", 0.0)
            if standby_rate > 0:
                self.add_charge_line(
                    description="Standby",
                    calc_type="Fixed",
                    value=standby_rate)

            # Airport Authority Fee now added based on Run Type selection

            # Gratuity (as percentage of charter charge) - if enabled
            if hasattr(
                    self,
                    'gratuity_checkbox'
                ) and self.gratuity_checkbox.isChecked():
                if hourly_rate > 0 and total_hours > 0:
                    gratuity_percent = self.gratuity_percent_input.value(
                    ) if hasattr(self, 'gratuity_percent_input') else 18.0
                    self.add_charge_line(
                        description=f"Gratuity ({gratuity_percent}%)",
                        calc_type="Percent",
                        value=gratuity_percent)

            # NRR (Non-Refundable Retainer) as a note if applicable
            nrr = pricing.get("nrr", 0.0)
            if nrr > 0:
                # Store NRR in a hidden field for later reference (minimum
                # charge to apply)
                self._nrr_minimum = nrr
                # Add NRR as info to the UI (optional label near totals)
                # For now, just store it - business logic can apply minimum
                # elsewhere

            self.recalculate_totals()
        except Exception as e:
            print(f"ℹ️  Auto-populate charges: {e}")

    def add_charge_line(
            self,
            description: str = "New Charge",
            calc_type: str = "Fixed",
            value: float = 0.0,
            charge_type: str = "other",
            is_taxable: bool = True,
            auto_added: bool = False):
        """Add new charge line (programmatic helper)."""
        print(
            f"🔵 add_charge_line() called:"
            f" description={description},"
            f" calc_type={calc_type}, value={value}")
        try:
            if not hasattr(self, 'charges_table'):
                print("❌ charges_table not found!")
                return

            row = self.charges_table.rowCount()
            print(f"   Adding at row {row}")
            self.charges_table.insertRow(row)

            desc_item = QTableWidgetItem(description)
            desc_item.setData(Qt.ItemDataRole.UserRole, {
                "calc_type": calc_type,
                "value": float(value),
                "charge_type": charge_type,
                "is_taxable": is_taxable})
            # Mark auto-added charges for easy removal when run type changes
            if auto_added:
                desc_item.setData(Qt.ItemDataRole.UserRole + 1, "auto_added")
            self.charges_table.setItem(row, 0, desc_item)

            type_item = QTableWidgetItem(calc_type)
            type_item.setFlags(type_item.flags() | Qt.ItemFlag.ItemIsEditable)
            self.charges_table.setItem(row, 1, type_item)

            line_total = self._compute_line_total(calc_type, float(value))
            total_item = QTableWidgetItem(f"{line_total:.2f}")
            total_item.setFlags(
                total_item.flags() | Qt.ItemFlag.ItemIsEditable)
            self.charges_table.setItem(row, 2, total_item)

            print("✅ Charge line added successfully")

            self.recalculate_totals()
        except Exception as e:
            print(f"❌ Error in add_charge_line: {e}")
            import traceback
            traceback.print_exc()

        self.recalculate_totals()

    def _compute_line_total(self, calc_type: str, value: float) -> float:
        """Calculate total for a line based on calc type."""
        try:
            calc = (calc_type or "Fixed").strip().lower()
            hours = getattr(self, "_calculated_total_hours", None) or 1.0
            charter_base = self._get_charter_charge_base()

            if calc == "percent":
                return (charter_base or 0.0) * value / 100.0
            if calc == "hourly":
                return hours * value
            return value
        except Exception:
            return value

    def _get_charter_charge_base(self) -> float:
        """Best-effort charter base for percent calculations."""
        try:
            if getattr(self, "_calculated_base_charge", None) is not None:
                return float(self._calculated_base_charge)

            for row in range(self.charges_table.rowCount()):
                desc_item = self.charges_table.item(row, 0)
                self.charges_table.item(row, 1)
                total_item = self.charges_table.item(row, 2)
                if not desc_item or not total_item:
                    continue
                desc_text = desc_item.text().lower()
                if "charter" in desc_text:
                    try:
                        return float(
                            total_item.text().replace(
                                '$', '').replace(
                                ',', ''))
                    except Exception:
                        continue
            return 0.0
        except Exception:
            return 0.0

    def _parse_description_metadata(self, description: str):
        """Extract calc type and value embedded in description, if present."""
        import re

        if not description:
            return "", None, None

        pattern = r"\s\[calc:(Fixed|Percent|Hourly):([0-9.]+)\]$"
        match = re.search(pattern, description)
        if match:
            calc_type = match.group(1)
            try:
                value = float(match.group(2))
            except Exception:
                value = None
            base_desc = re.sub(pattern, "", description).strip()
            return base_desc, calc_type, value
        return description, None, None

    def _format_description_with_metadata(
            self,
            description: str,
            calc_type: str,
            value: float) -> str:
        desc_clean = (description or "").strip()
        calc_clean = (calc_type or "Fixed").strip()
        return f"{desc_clean} [calc:{calc_clean}:{value}]"

    def recalculate_totals(self):
        """Recalculate totals using Description | Calc Type | Total layout."""
        try:
            subtotal = 0.0

            for row in range(self.charges_table.rowCount()):
                desc_item = self.charges_table.item(row, 0)
                type_item = self.charges_table.item(row, 1)
                total_item = self.charges_table.item(row, 2)

                if not desc_item or not type_item or not total_item:
                    continue

                meta = desc_item.data(Qt.ItemDataRole.UserRole) or {}
                calc_type = meta.get(
                    "calc_type") or type_item.text() or "Fixed"
                value = meta.get("value")

                # If user edits the displayed total and type is Fixed, use that
                # as the value
                if value is None or calc_type.lower() == "fixed":
                    try:
                        value = float(
                            total_item.text().replace(
                                '$', '').replace(
                                ',', ''))
                    except Exception:
                        value = 0.0

                # Persist calc metadata on the item for later saves
                if isinstance(meta, dict):
                    meta.update({"calc_type": calc_type, "value": value})
                    desc_item.setData(Qt.ItemDataRole.UserRole, meta)

                line_total = self._compute_line_total(calc_type, value)
                total_item.setText(f"{line_total:.2f}")
                subtotal += line_total

            beverage_total = self.get_beverage_total()
            if hasattr(self, 'beverage_total_display'):
                self.beverage_total_display.setText(f"${beverage_total:.2f}")

            separate_beverage = self.separate_beverage_checkbox.isChecked(
            ) if hasattr(self, 'separate_beverage_checkbox') else False
            if not separate_beverage:
                subtotal += beverage_total

            if hasattr(self, 'subtotal_display'):
                self.subtotal_display.setText(f"${subtotal:.2f}")

            gst_exempt = self.gst_exempt_checkbox.isChecked() if hasattr(
                self, 'gst_exempt_checkbox') else False
            if gst_exempt:
                gst_amount = 0.0
                gross_total = subtotal
            else:
                gst_amount = subtotal * 0.05 / 1.05
                gross_total = subtotal

            if hasattr(self, 'gst_total_display'):
                self.gst_total_display.setText(f"${gst_amount:.2f}")

            if hasattr(self, 'gross_total_display'):
                self.gross_total_display.setText(f"${gross_total:,.2f}")

            # === BALANCE CALCULATION ===
            # Total charges = gross_total (includes all charges + beverages +
            # gratuity + GST)
            nrr_amount = (
                self.nrr_received.value()
                if hasattr(self, 'nrr_received') else 0.0)

            # Get total payments from payments table (deposits + other
            # payments, NOT including NRR)
            total_payments = 0.0
            nrr_from_payments = 0.0
            has_refund_row = False
            if hasattr(self, 'payments_table'):
                for row in range(self.payments_table.rowCount()):
                    amount_item = self.payments_table.item(
                        row, 2)  # col 2 = Amount
                    type_item = self.payments_table.item(row, 0)
                    method_item = self.payments_table.item(row, 3)
                    if amount_item:
                        try:
                            amount_val = float(
                                amount_item.text().replace(
                                    '$', '').replace(
                                    ',', ''))
                            total_payments += amount_val
                            type_txt = (
                                (type_item.text() if type_item else "")
                                .strip()
                                .lower()
                            )
                            method_txt = (
                                (method_item.text() if method_item else "")
                                .strip()
                                .lower()
                            )
                            if (
                                "nrr" in type_txt
                                or method_txt in ("nrr", "retainer")
                            ):
                                nrr_from_payments += amount_val
                            if (
                                "refund" in type_txt
                                or method_txt in ("refund", "credit")
                                or amount_val < 0
                            ):
                                has_refund_row = True
                        except Exception:
                            pass

            # Balance = Total Charges - (NRR + Payments)
            nrr_only_from_field = max(nrr_amount - nrr_from_payments, 0.0)
            total_received = total_payments + nrr_only_from_field
            balance = gross_total - total_received

            # Penny rounding (round to nearest cent)
            balance = round(balance, 2)

            # Display balance with flags
            if hasattr(self, 'gross_total_display'):
                flag_text = ""
                if balance < 0:
                    if has_refund_row:
                        flag_text = f" 🔴 REFUND ${abs(balance):.2f}"
                    else:
                        flag_text = f" 🔵 CREDIT ${abs(balance):.2f}"
                elif abs(balance) < 0.01:
                    flag_text = " ✅ PAID IN FULL"
                else:
                    flag_text = f" ⏳ DUE ${balance:.2f}"

                self.gross_total_display.setText(
                    f"${gross_total:,.2f}{flag_text}")

            # Display NRR separately (escrow note if charter is cancelled)
            if hasattr(self, 'nrr_received'):
                if (self.charter_status_combo.currentText()
                        == "Cancelled" and nrr_amount > 0):
                    pass
                    # Would store this in database for refund tracking
                else:
                    pass

        except Exception as e:
            print(f"Error in recalculate_totals: {e}")
            import traceback
            traceback.print_exc()

    def get_beverage_total(self) -> float:
        """Get total beverage charge from cart"""
        try:
            return getattr(self, 'beverage_cart_total', 0.0)
        except Exception:
            return 0.0

    def add_beverage_item(self):
        """Add a new beverage item to the cart"""
        try:
            row = self.beverage_table.rowCount()
            self.beverage_table.insertRow(row)

            # Item name (editable)
            item_name = QTableWidgetItem("Beverage")
            self.beverage_table.setItem(row, 0, item_name)

            # Quantity (editable)
            qty = QTableWidgetItem("1")
            qty.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.beverage_table.setItem(row, 1, qty)

            # Unit Price (editable)
            price = QTableWidgetItem("0.00")
            price.setTextAlignment(Qt.AlignmentFlag.AlignRight)
            self.beverage_table.setItem(row, 2, price)

            # Total (auto-calculated, read-only)
            total = QTableWidgetItem("$0.00")
            total.setFlags(total.flags() & ~Qt.ItemFlag.ItemIsEditable)
            total.setTextAlignment(Qt.AlignmentFlag.AlignRight)
            self.beverage_table.setItem(row, 3, total)

            self.recalculate_beverage_totals()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to add beverage: {e}")

    def delete_selected_beverage(self):
        """Delete selected beverage item from cart"""
        current_row = self.beverage_table.currentRow()
        if current_row < 0:
            QMessageBox.information(
                self,
                "No Selection",
                "Please select a beverage item to delete.")
            return

        self.beverage_table.removeRow(current_row)
        self.recalculate_beverage_totals()

    def recalculate_beverage_totals(self):
        """Recalculate beverage cart totals (Item × Qty × Price + 5% GST)"""
        try:
            beverage_subtotal = 0.0

            for row in range(self.beverage_table.rowCount()):
                qty_item = self.beverage_table.item(row, 1)
                price_item = self.beverage_table.item(row, 2)
                total_item = self.beverage_table.item(row, 3)

                if not qty_item or not price_item or not total_item:
                    continue

                try:
                    qty = float(qty_item.text())
                    price = float(
                        price_item.text().replace(
                            '$', '').replace(
                            ',', ''))
                    line_total = qty * price
                    total_item.setText(f"${line_total:.2f}")
                    beverage_subtotal += line_total
                except ValueError:
                    total_item.setText("$0.00")

            # Update beverage totals
            gst_amount = beverage_subtotal * 0.05 / 1.05  # GST is included
            total_with_gst = beverage_subtotal

            self.beverage_subtotal.setText(f"${beverage_subtotal:.2f}")
            self.beverage_gst.setText(f"${gst_amount:.2f}")
            self.beverage_total.setText(f"${total_with_gst:,.2f}")

            # Store total for charter totals calculation
            self.beverage_cart_total = beverage_subtotal
        except Exception as e:
            print(f"Error calculating beverage totals: {e}")

    def toggle_payment_edit(self):
        """Toggle payment table between read-only and editable"""
        is_checked = self.edit_payment_btn.isChecked()
        self.payments_table.setEnabled(is_checked)
        if hasattr(self, 'add_payment_btn'):
            self.add_payment_btn.setEnabled(is_checked)
        if hasattr(self, 'delete_payment_btn'):
            self.delete_payment_btn.setEnabled(is_checked)

        if is_checked:
            self.edit_payment_btn.setText("✔️ Done Editing")
        else:
            self.edit_payment_btn.setText("✏️ Edit Payment")

    def add_payment_row(self):
        """Append a manual payment row for this charter."""
        if not self.edit_payment_btn.isChecked():
            QMessageBox.information(
                self,
                "Payments",
                "Enable Edit Payment first to add payment rows.",
            )
            return

        row = self.payments_table.rowCount()
        self.payments_table.insertRow(row)

        type_item = QTableWidgetItem("Deposit")
        type_item.setData(Qt.ItemDataRole.UserRole, None)
        self.payments_table.setItem(row, 0, type_item)
        self.payments_table.setItem(
            row,
            1,
            QTableWidgetItem(datetime.now().strftime("%Y-%m-%d")),
        )
        self.payments_table.setItem(row, 2, QTableWidgetItem("$0.00"))
        self.payments_table.setItem(row, 3, QTableWidgetItem("deposit"))
        self.payments_table.setItem(row, 4, QTableWidgetItem("manual entry"))
        self.payments_table.setItem(row, 5, QTableWidgetItem(""))

        self._payments_dirty = True
        self._sync_nrr_received_from_payments_table()
        self.recalculate_totals()

    def delete_selected_payment(self):
        """Delete the selected payment row from the UI table."""
        if not self.edit_payment_btn.isChecked():
            QMessageBox.information(
                self,
                "Payments",
                "Enable Edit Payment first to delete payment rows.",
            )
            return

        row = self.payments_table.currentRow()
        if row < 0:
            QMessageBox.information(
                self,
                "Payments",
                "Select a payment row to delete.",
            )
            return

        self.payments_table.removeRow(row)
        self._payments_dirty = True
        self._sync_nrr_received_from_payments_table()
        self.recalculate_totals()

    def _on_payments_table_item_changed(self, item):
        """Track payment edits and normalize type/method labels."""
        if self._loading_payments:
            return
        if item is None:
            return

        self._payments_dirty = True

        row = item.row()
        col = item.column()
        if col in (0, 3):
            type_item = self.payments_table.item(row, 0)
            method_item = self.payments_table.item(row, 3)
            type_txt = (type_item.text() if type_item else "").strip().lower()
            method_txt = (method_item.text() if method_item else "").strip().lower()

            normalized_method = method_txt or "deposit"
            normalized_type = type_txt or "deposit"

            if "nrr" in normalized_type or normalized_method in ("nrr", "retainer"):
                normalized_method = "nrr"
                normalized_type = "NRR Retainer"
            elif "deposit" in normalized_type:
                normalized_method = "deposit"
                normalized_type = "Deposit"
            elif "trade" in normalized_type or normalized_method == "trade":
                normalized_method = "trade"
                normalized_type = "Trade of Services"
            elif "promo" in normalized_type or normalized_method in ("promo", "promotional"):
                normalized_method = "promotional"
                normalized_type = "Promotional Credit"
            elif "refund" in normalized_type or normalized_method == "refund":
                normalized_method = "refund"
                normalized_type = "Refund"
            elif "credit" in normalized_type or normalized_method == "credit":
                normalized_method = "credit"
                normalized_type = "Credit"
            elif normalized_method == "bank_transfer":
                normalized_type = "Bank Transfer"
            elif normalized_method == "credit_card":
                normalized_type = "Credit Card"
            elif normalized_method == "etransfer":
                normalized_type = "E-Transfer"
            elif normalized_method == "debit_card":
                normalized_type = "Debit"
            elif normalized_method == "trade":
                normalized_type = "Trade"
            else:
                if normalized_type in ("payment", ""):
                    normalized_type = "Payment"

            self._loading_payments = True
            try:
                if type_item:
                    type_item.setText(normalized_type)
                if method_item:
                    method_item.setText(normalized_method)
            finally:
                self._loading_payments = False

        self._sync_nrr_received_from_payments_table()
        self.recalculate_totals()

    def _sum_nrr_payments_from_table(self) -> float:
        """Return total amount of rows classified as NRR/retainer."""
        total = 0.0
        if not hasattr(self, 'payments_table'):
            return 0.0

        for row in range(self.payments_table.rowCount()):
            type_item = self.payments_table.item(row, 0)
            method_item = self.payments_table.item(row, 3)
            amount_item = self.payments_table.item(row, 2)

            type_txt = (type_item.text() if type_item else "").strip().lower()
            method_txt = (method_item.text() if method_item else "").strip().lower()

            if "nrr" in type_txt or method_txt in ("nrr", "retainer"):
                try:
                    total += float(
                        (amount_item.text() if amount_item else "0")
                        .replace("$", "")
                        .replace(",", "")
                        .strip()
                        or 0
                    )
                except Exception:
                    continue

        return round(total, 2)

    def _sync_nrr_received_from_payments_table(self):
        """Mirror NRR payment totals into NRR Received when NRR rows exist."""
        if not hasattr(self, 'nrr_received'):
            return
        nrr_total = self._sum_nrr_payments_from_table()
        if nrr_total > 0:
            self.nrr_received.blockSignals(True)
            self.nrr_received.setValue(float(nrr_total))
            self.nrr_received.blockSignals(False)

    def _sync_charter_payments_from_table(
        self,
        cur,
        reserve_number: str,
        charter_date,
        client_name: str,
    ):
        """Persist edited payment table rows into charter_payments."""
        if not getattr(self, '_payments_dirty', False):
            return

        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema='public'
                AND table_name='charter_payments'
                AND column_name='gl_code'
            """
        )
        has_gl_code_column = bool(cur.fetchone())

        reserve_key = str(reserve_number or "")
        charter_key = str(self.charter_id or "")

        cur.execute(
            """
            SELECT id
            FROM charter_payments
            WHERE charter_id = %s OR charter_id = %s
            """,
            (reserve_key, charter_key),
        )
        existing_ids = {int(r[0]) for r in (cur.fetchall() or []) if r and r[0] is not None}

        kept_ids = set()
        for row in range(self.payments_table.rowCount()):
            type_item = self.payments_table.item(row, 0)
            date_item = self.payments_table.item(row, 1)
            amount_item = self.payments_table.item(row, 2)
            method_item = self.payments_table.item(row, 3)
            notes_item = self.payments_table.item(row, 4)
            gl_item = self.payments_table.item(row, 5)

            row_id = type_item.data(Qt.ItemDataRole.UserRole) if type_item else None
            type_txt = (type_item.text() if type_item else "").strip().lower()
            method_txt = (method_item.text() if method_item else "").strip().lower()

            if "nrr" in type_txt or method_txt in ("nrr", "retainer"):
                method_txt = "nrr"
            elif "deposit" in type_txt and method_txt in ("", "payment", "unknown"):
                method_txt = "deposit"
            elif "refund" in type_txt:
                method_txt = "credit"
            elif not method_txt:
                method_txt = "payment"

            date_txt = (date_item.text() if date_item else "").strip()
            pay_date = None
            if date_txt:
                try:
                    pay_date = datetime.strptime(date_txt[:10], "%Y-%m-%d").date()
                except Exception:
                    pay_date = None

            try:
                amount_val = float(
                    (amount_item.text() if amount_item else "0")
                    .replace("$", "")
                    .replace(",", "")
                    .strip()
                    or 0
                )
            except Exception:
                amount_val = 0.0

            note_txt = (notes_item.text() if notes_item else "").strip()
            gl_code_txt = (gl_item.text() if gl_item else "").strip()

            # Backward-compatible fallback when DB doesn't yet have charter_payments.gl_code
            if gl_code_txt and not has_gl_code_column:
                if note_txt:
                    note_txt = f"[GL:{gl_code_txt}] {note_txt}"
                else:
                    note_txt = f"[GL:{gl_code_txt}]"

            if row_id:
                if has_gl_code_column:
                    cur.execute(
                        """
                        UPDATE charter_payments
                        SET amount = %s,
                            payment_method = %s,
                            payment_date = %s,
                            client_name = %s,
                            charter_date = %s,
                            source = COALESCE(source, 'MANUAL_DESKTOP'),
                            payment_key = COALESCE(NULLIF(%s, ''), payment_key),
                            gl_code = NULLIF(%s, ''),
                            imported_at = COALESCE(imported_at, NOW())
                        WHERE id = %s
                        """,
                        (
                            amount_val,
                            method_txt,
                            pay_date,
                            client_name or "",
                            charter_date,
                            note_txt,
                            gl_code_txt,
                            int(row_id),
                        ),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE charter_payments
                        SET amount = %s,
                            payment_method = %s,
                            payment_date = %s,
                            client_name = %s,
                            charter_date = %s,
                            source = COALESCE(source, 'MANUAL_DESKTOP'),
                            payment_key = COALESCE(NULLIF(%s, ''), payment_key),
                            imported_at = COALESCE(imported_at, NOW())
                        WHERE id = %s
                        """,
                        (
                            amount_val,
                            method_txt,
                            pay_date,
                            client_name or "",
                            charter_date,
                            note_txt,
                            int(row_id),
                        ),
                    )
                kept_ids.add(int(row_id))
            else:
                if has_gl_code_column:
                    cur.execute(
                        """
                        INSERT INTO charter_payments
                            (charter_id, client_name, charter_date,
                             amount, payment_date, payment_method,
                             payment_key, gl_code, source)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            reserve_key,
                            client_name or "",
                            charter_date,
                            amount_val,
                            pay_date,
                            method_txt,
                            note_txt or None,
                            gl_code_txt or None,
                            "MANUAL_DESKTOP",
                        ),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO charter_payments
                            (charter_id, client_name, charter_date,
                             amount, payment_date, payment_method,
                             payment_key, source)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            reserve_key,
                            client_name or "",
                            charter_date,
                            amount_val,
                            pay_date,
                            method_txt,
                            note_txt or None,
                            "MANUAL_DESKTOP",
                        ),
                    )
                created_id = cur.fetchone()[0]
                if type_item:
                    type_item.setData(Qt.ItemDataRole.UserRole, int(created_id))
                kept_ids.add(int(created_id))

        ids_to_delete = sorted(existing_ids - kept_ids)
        for pid in ids_to_delete:
            cur.execute("DELETE FROM charter_payments WHERE id = %s", (pid,))

        nrr_total_from_rows = self._sum_nrr_payments_from_table()
        if nrr_total_from_rows > 0 and hasattr(self, 'nrr_received'):
            self.nrr_received.blockSignals(True)
            self.nrr_received.setValue(float(nrr_total_from_rows))
            self.nrr_received.blockSignals(False)

        effective_nrr = (
            nrr_total_from_rows
            if nrr_total_from_rows > 0
            else (
                float(self.nrr_received.value())
                if hasattr(self, 'nrr_received')
                else 0.0
            )
        )
        cur.execute(
            """
            UPDATE charters
            SET nrr_amount = %s,
                nrr_received = %s,
                updated_at = NOW()
            WHERE charter_id = %s
            """,
            (
                float(effective_nrr or 0.0),
                bool((effective_nrr or 0.0) > 0),
                self.charter_id,
            ),
        )

        self._payments_dirty = False

    def on_separate_beverage_toggled(self, state):
        """Handle separate beverage checkbox toggle"""
        if state:
            # Show child invoice creation dialog
            self.create_child_beverage_invoice()

    def search_customer(self, text: str):
        """
        Auto-fill customer data from search (minimum 3 characters).
        Searches clients table (not customers - that table doesn't exist).
        """
        if len(text) < 3:
            return

        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except Exception:
                try:
                    self.db.rollback()
                except Exception:
                    pass

            cur = self.db.get_cursor()
            # FIX: Search clients table, not customers table
            cur.execute("""
                SELECT client_id, company_name,
                primary_phone, email, address_line1
                FROM clients
                WHERE company_name ILIKE %s OR primary_phone ILIKE %s
                LIMIT 10
            """, (f"%{text}%", f"%{text}%"))

            results = cur.fetchall()
            if results:
                # Auto-fill first match
                client = results[0]
                self.customer_name.setText(str(client[1] or ""))
                self.customer_phone.setText(str(client[2] or ""))
                self.customer_email.setText(str(client[3] or ""))
                self.customer_address.setText(str(client[4] or ""))
        except Exception:
            try:
                self.db.rollback()
            except Exception:
                pass
            pass  # Silently fail on search

    def on_form_changed(self):
        """Signal handler: form field changed"""
        # Track that changes have been made

    def on_customer_saved(self, client_id: int):
        """Signal handler: customer information saved"""
        # Perform any necessary updates after customer save

    def _compose_legacy_notes(
            self,
            client_notes: Optional[str],
            dispatcher_notes: Optional[str]) -> str:
        """Build a single legacy notes string for screens that use charters.notes."""
        client_txt = (client_notes or "").strip()
        dispatcher_txt = (dispatcher_notes or "").strip()
        parts = []
        if client_txt:
            parts.append(f"Client Notes:\n{client_txt}")
        if dispatcher_txt:
            parts.append(f"Dispatcher Notes:\n{dispatcher_txt}")
        return "\n\n".join(parts).strip()

    def _save_notes_columns(
            self,
            cur,
            charter_id: int,
            client_notes: Optional[str],
            dispatcher_notes: Optional[str]):
        """Persist notes across modern and legacy charters note columns."""
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema='public'
              AND table_name='charters'
              AND column_name IN ('client_notes','booking_notes','notes')
        """)
        existing_cols = {row[0] for row in cur.fetchall()}

        sets = []
        params = []

        if 'client_notes' in existing_cols:
            sets.append('client_notes = %s')
            params.append((client_notes or '').strip())

        if 'booking_notes' in existing_cols:
            sets.append('booking_notes = %s')
            params.append((dispatcher_notes or '').strip())

        if 'notes' in existing_cols:
            sets.append('notes = %s')
            params.append(self._compose_legacy_notes(client_notes, dispatcher_notes))

        if not sets:
            return

        params.append(charter_id)
        cur.execute(
            f"UPDATE charters SET {', '.join(sets)}, updated_at=NOW() "
            f"WHERE charter_id=%s",
            tuple(params),
        )

    def _on_notes_text_changed(self):
        """Show save progress while debouncing notes writes."""
        if hasattr(self, 'notes_save_status_label'):
            self.notes_save_status_label.setText("Saving notes...")
        if hasattr(self, '_notes_status_clear_timer'):
            self._notes_status_clear_timer.stop()
        if hasattr(self, '_notes_save_timer'):
            self._notes_save_timer.start()

    def _clear_notes_save_status(self):
        if hasattr(self, 'notes_save_status_label'):
            self.notes_save_status_label.setText("")

    def _auto_save_notes(self):
        """Persist client_notes and booking_notes to the DB without a full save."""
        if not getattr(self, 'charter_id', None):
            return  # No charter open yet — nothing to persist
        client_notes = (
            self.client_notes_input.toPlainText()
            if hasattr(self, 'client_notes_input') else None)
        dispatcher_notes = (
            self.dispatcher_notes_input.toPlainText()
            if hasattr(self, 'dispatcher_notes_input') else None)
        try:
            cur = self.db.get_cursor()
            self._save_notes_columns(
                cur,
                self.charter_id,
                client_notes,
                dispatcher_notes,
            )
            self.db.commit()
            if hasattr(self, 'notes_save_status_label'):
                self.notes_save_status_label.setText(
                    f"Notes saved {datetime.now().strftime('%I:%M:%S %p')}"
                )
            if hasattr(self, '_notes_status_clear_timer'):
                self._notes_status_clear_timer.start()
        except Exception:
            try:
                self.db.rollback()
            except Exception:
                pass
            if hasattr(self, 'notes_save_status_label'):
                self.notes_save_status_label.setText("Notes save failed")

    def save_charter(self):
        """
        Save charter to database with validation.

        BUSINESS RULES:
        - reserve_number is auto-generated on insert
        - Customer name and phone are required
        - Must commit after insert/update
        - Use business key reserve_number for any linking
        - NRR (Non-Refundable Retainer) is recorded as LIABILITY
          until used in charter
          GL Code: 2400 (Unearned Revenue / Client Deposits Liability)
          NOT GL Code: 4000 (Service Revenue) - only applied
          when charter completes
        """
        # Get customer data from widget
        customer_data = self.customer_widget.get_customer_data()

        # Validation
        if not customer_data['client_name'].strip():
            QMessageBox.warning(
                self,
                "Validation Error",
                "Client name is required")
            return

        if not customer_data['phone'].strip():
            QMessageBox.warning(self, "Validation Error", "Phone is required")
            return

        # Validate pickup/drop-off datetimes from the explicit date+time boxes
        start_dt = datetime.combine(
            self.charter_date_from.date().toPyDate(),
            self.base_time_from.time().toPyTime(),
        )
        end_dt = datetime.combine(
            self.charter_date_to.date().toPyDate(),
            self.base_time_to.time().toPyTime(),
        )
        if end_dt < start_dt:
            QMessageBox.warning(
                self,
                "Validation Error",
                "Drop-off cannot be before pickup. "
                "Adjust the date/time (multi-day allowed).")
            return

        charter_date_val = start_dt.date()
        pickup_time_val = start_dt.time()

        planned_end_iso = end_dt.isoformat()
        charter_data_payload = {"planned_end_time": planned_end_iso}
        if hasattr(self, 'run_type_combo'):
            charter_data_payload["run_type"] = self.run_type_combo.currentText(
            ).strip()

        run_type_val = (
            self.run_type_combo.currentText().strip()
            if hasattr(self, 'run_type_combo')
            else None
        )
        requested_vehicle_type_val = None
        if hasattr(self, 'vehicle_type_requested_combo'):
            requested_vehicle_type_val = (
                self.vehicle_type_requested_combo.currentData()
                or self.vehicle_type_requested_combo.currentText().strip()
            )

        quoted_hours_val = None
        if hasattr(self, 'quoted_hours_input'):
            try:
                quoted_hours_val = float(self.quoted_hours_input.value())
            except Exception:
                quoted_hours_val = None
        if quoted_hours_val is None:
            quoted_hours_val = float(self._calculate_charter_duration() or 0.0)

        quoted_hourly_val = 0.0
        if hasattr(self, 'quoted_hourly_price'):
            try:
                quoted_hourly_val = float(
                    (self.quoted_hourly_price.text() or "")
                    .replace("$", "")
                    .replace(",", "")
                    .strip()
                    or 0
                )
            except Exception:
                quoted_hourly_val = 0.0

        # Add NRR and CC info to charter_data
        nrr_amount = (
            self.nrr_received.value()
            if hasattr(self, 'nrr_received') else 0.0)
        if nrr_amount > 0:
            charter_data_payload["nrr_received"] = float(nrr_amount)

        # Store CC last 4 only (full CC masked at save time)
        if self.client_cc_checkbox.isChecked():
            cc_last4 = self.client_cc_last4.text().strip()
            if cc_last4:
                charter_data_payload["cc_on_file_last4"] = cc_last4
                # After save, mask the full CC field
                self.client_cc_full.clear()
                self.client_cc_full.setEnabled(False)

        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except Exception:
                try:
                    self.db.rollback()
                except Exception:
                    pass

            cur = self.db.get_cursor()

            cur.execute("""
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'charters'
                      AND column_name = 'charter_data'
                )
            """)
            has_charter_data = bool(cur.fetchone()[0])

            cur.execute("""
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'charters'
                      AND column_name = 'booking_notes'
                )
            """)
            has_booking_notes = bool(cur.fetchone()[0])

            if self.charter_id:
                # ===== UPDATE EXISTING =====
                out_of_town = self.out_of_town_checkbox.isChecked() if hasattr(
                    self, 'out_of_town_checkbox') else False
                employee_id_val = (
                    self.driver_combo.currentData()
                    if hasattr(self, 'driver_combo') else None)
                vehicle_id_val = (
                    self.vehicle_combo.currentData()
                    if hasattr(self, 'vehicle_combo') else None)
                charter_type_val = (
                    self.charter_type_combo.currentText()
                    if hasattr(self, 'charter_type_combo') else None)
                gratuity_pct_val = (
                    self.gratuity_percent_input.value()
                    if hasattr(self, 'gratuity_percent_input') else None)
                nrr_amt_val = (
                    self.nrr_received.value()
                    if hasattr(self, 'nrr_received') else 0.0)
                gst_exempt_val = (
                    self.gst_exempt_checkbox.isChecked()
                    if hasattr(self, 'gst_exempt_checkbox') else False)
                beverages_separate_val = (
                    self.separate_beverage_checkbox.isChecked()
                    if hasattr(self, 'separate_beverage_checkbox') else False)
                client_notes_val = (
                    self.client_notes_input.toPlainText()
                    if hasattr(self, 'client_notes_input') else None)
                booking_notes_val = (
                    self.dispatcher_notes_input.toPlainText()
                    if hasattr(self, 'dispatcher_notes_input') else None)
                booking_notes_val = self._apply_internal_delivery_markers(
                    booking_notes_val or ""
                )

                # If escrow NRR is being carried forward, stamp a clear audit
                # note so it is visible on this booking.
                if (
                    hasattr(self, '_escrow_nrr_applied')
                    and self._escrow_nrr_applied
                    and has_booking_notes
                ):
                    move_note = self._compose_nrr_moved_forward_note(
                        self._escrow_nrr_applied
                    )
                    existing = (booking_notes_val or '').strip()
                    if move_note not in existing:
                        booking_notes_val = (
                            f"{existing}\n{move_note}".strip()
                            if existing
                            else move_note
                        )
                if has_charter_data:
                    booking_notes_clause = (
                        "booking_notes = COALESCE(%s, booking_notes),"
                        if has_booking_notes
                        else ""
                    )
                    params = [
                        charter_date_val,
                        pickup_time_val,
                        self.num_passengers.value(),
                        self.charter_status_combo.currentText(),
                        customer_data['client_id'],
                        out_of_town,
                        json.dumps(charter_data_payload),
                        employee_id_val,
                        vehicle_id_val,
                        requested_vehicle_type_val,
                        run_type_val,
                        charter_type_val,
                        quoted_hourly_val,
                        quoted_hours_val,
                        gratuity_pct_val,
                        nrr_amt_val,
                        nrr_amt_val > 0,
                        gst_exempt_val,
                        beverages_separate_val,
                        client_notes_val,
                    ]
                    if has_booking_notes:
                        params.append(booking_notes_val)
                    params.append(self.charter_id)

                    cur.execute(
                        f"""
                        UPDATE charters
                        SET charter_date = %s,
                            pickup_time = %s,
                            passenger_count = %s,
                            status = %s,
                            client_id = %s,
                            is_out_of_town = %s,
                            charter_data = %s::jsonb,
                            employee_id = COALESCE(%s, employee_id),
                            vehicle_id = COALESCE(%s, vehicle_id),
                            vehicle = COALESCE(%s, vehicle),
                            routing_type = COALESCE(%s, routing_type),
                            charter_type = COALESCE(%s, charter_type),
                            hourly_rate = COALESCE(%s, hourly_rate),
                            quoted_hours = COALESCE(%s, quoted_hours),
                            gratuity_percent = COALESCE(%s, gratuity_percent),
                            nrr_amount = %s,
                            nrr_received = %s,
                            gst_exempt = %s,
                            beverages_separate = %s,
                            client_notes = COALESCE(%s, client_notes),
                            {booking_notes_clause}
                            updated_at = NOW()
                        WHERE charter_id = %s
                        """,
                        tuple(params),
                    )
                else:
                    booking_notes_clause = (
                        "booking_notes = COALESCE(%s, booking_notes),"
                        if has_booking_notes
                        else ""
                    )
                    params = [
                        charter_date_val,
                        pickup_time_val,
                        self.num_passengers.value(),
                        self.charter_status_combo.currentText(),
                        customer_data['client_id'],
                        out_of_town,
                        employee_id_val,
                        vehicle_id_val,
                        requested_vehicle_type_val,
                        run_type_val,
                        charter_type_val,
                        quoted_hourly_val,
                        quoted_hours_val,
                        gratuity_pct_val,
                        nrr_amt_val,
                        nrr_amt_val > 0,
                        gst_exempt_val,
                        beverages_separate_val,
                        client_notes_val,
                    ]
                    if has_booking_notes:
                        params.append(booking_notes_val)
                    params.append(self.charter_id)

                    cur.execute(
                        f"""
                        UPDATE charters
                        SET charter_date = %s,
                            pickup_time = %s,
                            passenger_count = %s,
                            status = %s,
                            client_id = %s,
                            is_out_of_town = %s,
                            employee_id = COALESCE(%s, employee_id),
                            vehicle_id = COALESCE(%s, vehicle_id),
                            vehicle = COALESCE(%s, vehicle),
                            routing_type = COALESCE(%s, routing_type),
                            charter_type = COALESCE(%s, charter_type),
                            hourly_rate = COALESCE(%s, hourly_rate),
                            quoted_hours = COALESCE(%s, quoted_hours),
                            gratuity_percent = COALESCE(%s, gratuity_percent),
                            nrr_amount = %s,
                            nrr_received = %s,
                            gst_exempt = %s,
                            beverages_separate = %s,
                            client_notes = COALESCE(%s, client_notes),
                            {booking_notes_clause}
                            updated_at = NOW()
                        WHERE charter_id = %s
                        """,
                        tuple(params),
                    )
                # ✨ SAVE ROUTES & CHARGES ✨
                self.save_charter_routes(cur)
                reserve_for_payments = self._fetch_reserve_number(self.charter_id)
                self._sync_charter_payments_from_table(
                    cur,
                    reserve_for_payments or "",
                    charter_date_val,
                    customer_data.get('client_name', ''),
                )
                self.save_charter_charges(cur)

                self._save_notes_columns(
                    cur,
                    self.charter_id,
                    client_notes_val,
                    booking_notes_val,
                )

                self.db.commit()

                reserve_num = self._fetch_reserve_number(self.charter_id)
                QMessageBox.information(
                    self, "Success",
                    f"Charter #{self.charter_id} updated successfully")

            else:
                # ===== CREATE NEW (WITH RESERVE_NUMBER AUTO-GENERATION) =====
                # Generate reserve_number (max + 1)
                cur.execute(
                    "SELECT MAX(CAST(reserve_number AS INTEGER))"
                    " FROM charters WHERE reserve_number ~ '^\\d+$'")
                max_val = cur.fetchone()[0] or 0
                new_reserve_number = f"{int(max_val) + 1:06d}"

                out_of_town = self.out_of_town_checkbox.isChecked() if hasattr(
                    self, 'out_of_town_checkbox') else False
                if has_charter_data:
                    cur.execute(
                        """
                        INSERT INTO charters (
                            reserve_number, charter_date, pickup_time,
                            passenger_count, notes, status,
                            client_id, is_out_of_town, charter_data,
                            vehicle, routing_type, hourly_rate, quoted_hours
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s)
                        RETURNING charter_id, reserve_number
                        """,
                        (
                            new_reserve_number,
                            charter_date_val,
                            pickup_time_val,
                            self.num_passengers.value(),
                            "",
                            self.charter_status_combo.currentText(),
                            customer_data['client_id'],
                            out_of_town,
                            json.dumps(charter_data_payload),
                            requested_vehicle_type_val,
                            run_type_val,
                            quoted_hourly_val,
                            quoted_hours_val,
                        ),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO charters (
                            reserve_number, charter_date,
                            pickup_time, passenger_count,
                            notes, status, client_id,
                            is_out_of_town, vehicle,
                            routing_type, hourly_rate, quoted_hours
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING charter_id, reserve_number
                        """,
                        (
                            new_reserve_number,
                            charter_date_val,
                            pickup_time_val,
                            self.num_passengers.value(),
                            "",
                            self.charter_status_combo.currentText(),
                            customer_data['client_id'],
                            out_of_town,
                            requested_vehicle_type_val,
                            run_type_val,
                            quoted_hourly_val,
                            quoted_hours_val,
                        ),
                    )

                result = cur.fetchone()
                self.charter_id = result[0]
                reserve_num = result[1]

                client_notes_val = (
                    self.client_notes_input.toPlainText()
                    if hasattr(self, 'client_notes_input') else ''
                )
                booking_notes_val = (
                    self.dispatcher_notes_input.toPlainText()
                    if hasattr(self, 'dispatcher_notes_input') else ''
                )
                booking_notes_val = self._apply_internal_delivery_markers(
                    booking_notes_val or ""
                )
                if hasattr(self, '_escrow_nrr_applied') and self._escrow_nrr_applied:
                    move_note = self._compose_nrr_moved_forward_note(
                        self._escrow_nrr_applied
                    )
                    if move_note not in (booking_notes_val or ''):
                        booking_notes_val = (
                            f"{(booking_notes_val or '').strip()}\n{move_note}".strip()
                            if (booking_notes_val or '').strip()
                            else move_note
                        )

                # ✨ SAVE ROUTES & CHARGES ✨
                self.save_charter_routes(cur)
                self._sync_charter_payments_from_table(
                    cur,
                    reserve_num,
                    charter_date_val,
                    customer_data.get('client_name', ''),
                )
                self.save_charter_charges(cur)

                self._save_notes_columns(
                    cur,
                    self.charter_id,
                    client_notes_val,
                    booking_notes_val,
                )

                # 🔓 GL CODE ESCROW NRR IF APPLIED
                if hasattr(
                        self,
                        '_escrow_nrr_applied') and self._escrow_nrr_applied:
                    self._gl_code_escrow_nrr_as_payment(
                        self.charter_id, reserve_num,
                        self._escrow_nrr_applied, cur)
                    self._escrow_nrr_applied = None  # Clear after use

                # Save inspection form reference if uploaded
                if (has_charter_data and hasattr(
                        self,
                        'current_inspection_form_path')
                        and self.current_inspection_form_path):
                    try:
                        # Store relative path for portability
                        rel_path = os.path.relpath(
                            self.current_inspection_form_path,
                            os.path.dirname(__file__))
                        cur.execute(
                            """UPDATE charters SET charter_data =
                               "jsonb_set(charter_data, "
                               "{'inspection_form_path'}, %s::jsonb)"
                               WHERE charter_id = %s""",
                            (json.dumps(rel_path), self.charter_id))
                    except Exception:
                        pass  # Non-critical

                self.db.commit()

                if hasattr(self, "reserve_number"):
                    try:
                        self.reserve_number.setText(str(reserve_num))
                    except Exception:
                        pass
                QMessageBox.information(
                    self, "Success",
                    f"New charter created!\n\n"
                    f"Reserve #: {reserve_num}\n"
                    f"Charter ID: {self.charter_id}")

            self.saved.emit(self.charter_id)

        except psycopg2.Error as e:
            self.db.rollback()
            QMessageBox.critical(
                self, "Database Error",
                f"Failed to save charter:\n\n"
                f"{e.diag.message_primary if hasattr(e, 'diag') else str(e)}")
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save charter:\n\n{str(e)}")

    def _on_charter_status_changed(self, new_status: str):
        """
        Handle charter status changes.
        When status changes to 'Completed', offer to open driver entry form.
        """
        if new_status == "Completed" and self.charter_id:
            # Only auto-trigger if charter has been saved
            reply = QMessageBox.question(
                self,
                "Driver Entry",
                "Charter marked as complete. Do you want to open the driver "
                "entry form now?",
                ((QMessageBox.StandardButton.Yes
             | QMessageBox.StandardButton.No)),
                QMessageBox.StandardButton.Yes,)

            if reply == QMessageBox.StandardButton.Yes:
                self._open_driver_entry_form()

        if new_status == "Cancelled":
            nrr_amount = (
                float(self.nrr_received.value())
                if hasattr(self, 'nrr_received')
                else 0.0
            )
            if nrr_amount > 0:
                QMessageBox.information(
                    self,
                    "NRR Escrow",
                    f"This cancelled charter has ${nrr_amount:.2f} NRR.\n"
                    "It will be kept in escrow for this client and offered "
                    "on their next booking.",
                )

    def _open_driver_entry_form(self):
        """Open the driver entry form dialog for the current charter"""
        if not self.charter_id:
            QMessageBox.warning(
                self,
                "Driver Entry",
                "Please save charter first")
            return

        try:
            # Get reserve_number for current charter
            reserve_num = self._fetch_reserve_number(self.charter_id)
            if not reserve_num:
                QMessageBox.warning(
                    self, "Driver Entry", "Could not find reserve number")
                return

            # Import and show driver entry dialog
            import os

            from driver_calendar_widget import DriverEntryDialog

            # Ensure submission directory exists
            base_dir = os.path.join(
                os.path.dirname(__file__),
                'reports',
                'driver_logs_submissions')
            os.makedirs(base_dir, exist_ok=True)

            dlg = DriverEntryDialog(reserve_num, base_dir, self.db, self)
            dlg.exec()

        except Exception as e:
            QMessageBox.warning(
                self,
                "Error",
                f"Failed to open driver form:\n\n{str(e)}")

    def _gl_code_escrow_nrr_as_payment(
            self,
            charter_id: int,
            reserve_number: str,
            escrow_info: dict,
            cur):
        """
        GL code the escrow NRR when applied to new charter.
        Treats NRR as a payment received (removes from escrow).

        GL Entry: Debit Bank (1010), Credit Revenue (4000)
        Description: "NRR applied from cancelled reserve #{from_reserve}"
        """
        try:
            nrr_amount = escrow_info.get('amount', 0.0)
            from_charter_id = escrow_info.get('from_charter_id')
            from_reserve = escrow_info.get('from_reserve', '')

            if nrr_amount <= 0:
                return

            # Clear NRR from original cancelled charter (if charter_data
            # exists)
            cur.execute("""
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'charters'
                      AND column_name = 'charter_data'
                )
            """)
            if bool(cur.fetchone()[0]):
                cur.execute("""
                    UPDATE charters
                    SET charter_data = jsonb_set(
                            jsonb_set(
                                COALESCE(charter_data, '{}'::jsonb)
                                - 'nrr_received',
                                '{nrr_escrow_applied}',
                                'true'::jsonb,
                                true
                            ),
                            '{nrr_moved_forward_to}',
                            to_jsonb(%s::text),
                            true
                        ),
                        nrr_amount = 0,
                        nrr_received = FALSE
                    WHERE charter_id = %s
                """, (reserve_number, from_charter_id))
            else:
                cur.execute("""
                    UPDATE charters
                    SET nrr_amount = 0,
                        nrr_received = FALSE
                    WHERE charter_id = %s
                """, (from_charter_id,))

            # GL Code: Bank debit, Revenue credit (payment received)
            cur.execute("""
                INSERT INTO general_ledger
                (charter_id, reserve_number, gl_code,
                 account_name, amount, entry_type,
                 description, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """, (
                charter_id,
                reserve_number,
                '4000',  # Service Revenue
                'Service Revenue',
                nrr_amount,
                'CREDIT',  # Revenue
                f'NRR applied from escrow '
                f'(cancelled reserve #{from_reserve})'))

            # Also debit Bank to balance
            cur.execute("""
                INSERT INTO general_ledger
                (charter_id, reserve_number, gl_code,
                 account_name, amount, entry_type,
                 description, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """, (
                charter_id,
                reserve_number,
                '1010',  # Bank Account
                'Bank - Deposit Account',
                nrr_amount,
                'DEBIT',  # Asset
                'NRR payment from escrow applied'))

            print(
                f"✅ GL coded escrow NRR: ${nrr_amount:.2f}"
                f" from cancelled reserve #{from_reserve}")

        except Exception as e:
            print(f"⚠️ Could not GL code escrow NRR: {e}")

    def _fetch_reserve_number(self, charter_id: int) -> Optional[str]:
        try:
            cur = self.db.get_cursor()
            cur.execute(
                "SELECT reserve_number FROM charters"
                " WHERE charter_id = %s", (charter_id,))
            row = cur.fetchone()
            return row[0] if row else None
        except Exception:
            try:
                self.db.rollback()
            except Exception:
                pass
            return None

    def _prompt_calendar_event(
            self,
            reserve_number: Optional[str],
            start_dt,
            end_dt,
            customer_name: str):
        if not reserve_number:
            return
        try:
            reply = QMessageBox.question(
                self,
                "Calendar",
                "Create/Update calendar event now?",
                ((QMessageBox.StandardButton.Yes
             | QMessageBox.StandardButton.No)),
                QMessageBox.StandardButton.Yes,)
            if reply != QMessageBox.StandardButton.Yes:
                return
            self._create_outlook_event(
                reserve_number, start_dt, end_dt, customer_name)
        except Exception:
            # Fail silently to avoid blocking save flow
            pass

    def sync_charter_to_calendar(self):
        """Create/update the current charter in the Arrow Outlook calendar."""
        if not getattr(self, 'charter_id', None):
            QMessageBox.warning(
                self,
                "Calendar",
                "Please save this charter first, then update the calendar.",
            )
            return

        reserve_number = self._fetch_reserve_number(self.charter_id)
        if not reserve_number:
            QMessageBox.warning(
                self,
                "Calendar",
                "Could not find reserve number for this charter.",
            )
            return

        try:
            start_dt = datetime.combine(
                self.charter_date_from.date().toPyDate(),
                self.base_time_from.time().toPyTime(),
            )
            end_dt = datetime.combine(
                self.charter_date_to.date().toPyDate(),
                self.base_time_to.time().toPyTime(),
            )
            if end_dt < start_dt:
                QMessageBox.warning(
                    self,
                    "Calendar",
                    "Drop-off cannot be before pickup.",
                )
                return

            customer_name = ""
            if hasattr(self, 'customer_widget'):
                try:
                    customer_data = self.customer_widget.get_customer_data()
                    customer_name = customer_data.get("client_name", "")
                except Exception:
                    customer_name = ""

            self._create_outlook_event(
                reserve_number,
                start_dt,
                end_dt,
                customer_name,
            )
        except Exception as e:
            QMessageBox.warning(
                self,
                "Calendar",
                f"Failed to update calendar event: {e}",
            )

    def _create_outlook_event(
            self,
            reserve_number: str,
            start_dt,
            end_dt,
            customer_name: str):
        """Create or update an Outlook event for this reserve number."""
        try:
            import win32com.client  # type: ignore

            outlook = win32com.client.Dispatch("Outlook.Application")
            namespace = outlook.GetNamespace("MAPI")
            calendar_folder = namespace.GetDefaultFolder(9)  # olFolderCalendar
            items = calendar_folder.Items
            items.Sort("[Start]")
            items.IncludeRecurrences = True

            subject_prefix = f"Reserve {reserve_number} -"
            appt = None
            for item in items:
                try:
                    if getattr(item, "Class", None) != 26:
                        continue
                    subj = str(getattr(item, "Subject", "") or "")
                    if subj.startswith(subject_prefix):
                        appt = item
                        break
                except Exception:
                    continue

            created_new = appt is None
            if created_new:
                appt = outlook.CreateItem(1)  # olAppointmentItem

            appt.Subject = (
                f"Reserve {reserve_number} - "
                f"{customer_name or 'Charter'}"
            )
            appt.Start = start_dt
            appt.End = end_dt
            appt.Body = self.dispatch_notes_input.toPlainText(
            ) if hasattr(self, "dispatch_notes_input") else ""
            appt.Categories = "ALMS"
            appt.Save()

            QMessageBox.information(
                self,
                "Calendar",
                (
                    "Calendar event created in Outlook."
                    if created_new
                    else "Calendar event updated in Outlook."
                ),
            )
        except Exception as e:
            QMessageBox.warning(
                self, "Calendar", f"Failed to create Outlook event: {e}")

    def load_charter_by_id(self, charter_id: int):
        """Convenience method for loading charter from lookup widgets"""
        self.charter_id = charter_id
        if hasattr(self, "booking_tab_widget"):
            self.booking_tab_widget.setCurrentIndex(0)
        self.load_charter(charter_id)

    def load_charter_by_reserve(self, reserve_number: str):
        """Load charter by reserve number (used by dispatch drill-down)."""
        try:
            if not reserve_number:
                return

            cur = self.db.get_cursor()
            cur.execute(
                """
                SELECT charter_id
                FROM charters
                WHERE reserve_number = %s
                ORDER BY charter_id DESC
                LIMIT 1
                """,
                (str(reserve_number),),
            )
            row = cur.fetchone()
            cur.close()

            if row and row[0]:
                self.load_charter_by_id(int(row[0]))
            else:
                QMessageBox.warning(
                    self,
                    "Charter Not Found",
                    f"No charter found for reserve #{reserve_number}.",
                )
        except Exception as e:
            try:
                self.db.rollback()
            except Exception:
                pass
            QMessageBox.warning(self, "Error", f"Failed to load charter: {e}")

    def _handle_lookup_print_run_sheet(self, reserve_number: str):
        """Open reserve from Charter Lookup and print its run sheet."""
        if not reserve_number:
            return
        self.load_charter_by_reserve(reserve_number)
        if self.charter_id:
            self.print_run_sheet()

    def prefill_from_dispatch_row(self, booking_row):
        """Fast prefill from Dispatch Board row before canonical DB load.

        booking_row layout (dispatch_management_widget):
        [charter_id, reserve_number, charter_date, client_name, run_type,
         vehicle, driver, status, passengers, pickup, dropoff, has_beverages,
         driver_notes, in_payroll]
        """
        try:
            if not booking_row:
                return

            reserve_number = booking_row[1]
            charter_date = booking_row[2]
            run_type = booking_row[4]
            status = booking_row[7]
            passengers = booking_row[8]
            driver_notes = booking_row[12]

            if hasattr(
                self, "reserve_number") and self.reserve_number is not None:
                try:
                    self.reserve_number.setText(str(reserve_number or ""))
                except Exception:
                    pass

            if hasattr(self, "charter_status_combo") and status:
                try:
                    normalized_status = str(status)
                    if normalized_status in (
                        "Confirmed",
                        "In Progress",
                        "Booking In Progress",
                    ):
                        normalized_status = "Booked"
                    self.charter_status_combo.setCurrentText(
                        normalized_status
                    )
                except Exception:
                    pass

            if hasattr(self, "num_passengers") and passengers is not None:
                try:
                    self.num_passengers.setValue(int(passengers or 0))
                except Exception:
                    pass

            if hasattr(self, "run_type_combo") and run_type:
                try:
                    idx = self.run_type_combo.findText(str(run_type))
                    if idx >= 0:
                        self.run_type_combo.setCurrentIndex(idx)
                except Exception:
                    pass

            if hasattr(self, "pickup_datetime") and charter_date:
                try:
                    from PyQt6.QtCore import QDate
                    self.pickup_datetime.setDate(
                        QDate(charter_date.year,
                              charter_date.month, charter_date.day)
                    )
                except Exception:
                    pass

            if hasattr(self, "dispatch_notes_input") and driver_notes:
                try:
                    self.dispatch_notes_input.setPlainText(str(driver_notes))
                except Exception:
                    pass
        except Exception:
            # Prefill is best-effort only; full load_charter() follows.
            pass

    def load_charter(self, charter_id: int):
        """Load existing charter data from database"""
        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except Exception:
                try:
                    self.db.rollback()
                except Exception:
                    pass

            cur = self.db.get_cursor()
            cur.execute("""
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'charters'
                      AND column_name = 'charter_data'
                )
            """)
            has_charter_data = bool(cur.fetchone()[0])

            # Load charter with all persisted fields.
            # charter_data is optional — choose column at build time so
            # PostgreSQL never sees a reference to a column that may
            # not exist (CASE WHEN is still parsed/validated at plan time).
            charter_data_col = "c.charter_data" if has_charter_data else "NULL::jsonb"
            cur.execute(f"""
                SELECT
                    c.reserve_number,
                    c.charter_date,
                    c.pickup_time,
                    c.passenger_count,
                    c.notes,
                    c.status,
                    c.client_id,
                    {charter_data_col},
                    COALESCE(c.is_out_of_town, FALSE),
                    c.employee_id,
                    c.vehicle_id,
                    COALESCE(c.vehicle, ''),
                    COALESCE(c.routing_type, ''),
                    COALESCE(c.charter_type, ''),
                    COALESCE(c.hourly_rate, 0),
                    COALESCE(c.gratuity_percent, 18.0),
                    COALESCE(c.quoted_hours, 0),
                    COALESCE(c.extra_time_rate, 0),
                    COALESCE(c.standby_rate, 0),
                    COALESCE(c.nrd_received, FALSE),
                    COALESCE(c.nrd_amount, 0),
                    COALESCE(c.nrd_method, ''),
                    COALESCE(c.nrr_received, FALSE),
                    COALESCE(c.nrr_amount, 0),
                    COALESCE(c.gst_exempt, FALSE),
                    COALESCE(c.gst_permit_number, ''),
                    COALESCE(c.pickup_address, ''),
                    COALESCE(c.dropoff_address, ''),
                    c.do_time,
                    c.dropoff_time,
                    COALESCE(c.beverages_separate, FALSE)
                FROM charters c
                WHERE c.charter_id = %s
            """, (charter_id,))

            row = cur.fetchone()
            if row:
                (reserve_number, charter_date, pickup_time,
                 passenger_count, notes, status,
                 client_id, charter_data,
                 is_out_of_town,
                 employee_id, vehicle_id,
                 requested_vehicle_type, routing_type,
                 charter_type, hourly_rate, gratuity_percent,
                 quoted_hours, extra_time_rate, standby_rate,
                 nrd_received, nrd_amount, nrd_method,
                 nrr_received_flag, nrr_amount,
                 gst_exempt, gst_permit_number,
                 pickup_address, dropoff_address,
                 do_time, dropoff_time,
                 beverages_separate) = row
                charter_data_json = charter_data  # consistent alias

                # Load customer widget with data
                self.customer_widget.set_charter_data(
                    charter_id, reserve_number, client_id)

                if charter_date:
                    try:
                        qdate = QDate(
                            charter_date.year,
                            charter_date.month,
                            charter_date.day,
                        )
                        self.charter_date_from.setDate(qdate)
                        self.charter_date_to.setDate(qdate)
                    except Exception:
                        pass

                if pickup_time:
                    try:
                        self.base_time_from.setTime(
                            QTime(pickup_time.hour, pickup_time.minute)
                        )
                    except Exception:
                        pass

                # Planned end from charter_data if present
                planned_end = None
                try:
                    if charter_data_json:
                        payload = (charter_data_json if isinstance(
                            charter_data_json, dict)
                            else json.loads(charter_data_json))
                        planned_end_iso = payload.get("planned_end_time")
                        if planned_end_iso:
                            planned_end = datetime.fromisoformat(
                                planned_end_iso)
                except Exception:
                    planned_end = None

                if planned_end:
                    try:
                        self.charter_date_to.setDate(
                            QDate(
                                planned_end.year,
                                planned_end.month,
                                planned_end.day,
                            )
                        )
                        self.base_time_to.setTime(
                            QTime(planned_end.hour, planned_end.minute)
                        )
                    except Exception:
                        pass
                elif dropoff_time:
                    try:
                        self.base_time_to.setTime(
                            QTime(dropoff_time.hour, dropoff_time.minute)
                        )
                    except Exception:
                        pass
                else:
                    try:
                        self.base_time_to.setTime(
                            self.base_time_from.time().addSecs(2 * 60 * 60)
                        )
                    except Exception:
                        pass

                self.num_passengers.setValue(int(passenger_count or 1))
                if status:
                    self.charter_status_combo.setCurrentText(status)
                if hasattr(self, 'out_of_town_checkbox'):
                    self.out_of_town_checkbox.setChecked(
                        is_out_of_town or False)

                # ── Notes (modern + legacy fallback) ──────────────────────
                try:
                    cur_notes = self.db.get_cursor()
                    cur_notes.execute("""
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema='public'
                          AND table_name='charters'
                          AND column_name IN ('client_notes','booking_notes','notes')
                    """)
                    note_cols = {r[0] for r in cur_notes.fetchall()}

                    select_parts = []
                    if 'client_notes' in note_cols:
                        select_parts.append('client_notes')
                    if 'booking_notes' in note_cols:
                        select_parts.append('booking_notes')
                    if 'notes' in note_cols:
                        select_parts.append('notes')

                    client_notes_val = ''
                    booking_notes_val = ''
                    legacy_notes_val = ''
                    if select_parts:
                        cur_notes.execute(
                            f"SELECT {', '.join(select_parts)} "
                            "FROM charters WHERE charter_id = %s",
                            (charter_id,),
                        )
                        note_row = cur_notes.fetchone() or ()
                        note_map = dict(zip(select_parts, note_row))
                        client_notes_val = str(note_map.get('client_notes') or '').strip()
                        booking_notes_val = str(note_map.get('booking_notes') or '').strip()
                        legacy_notes_val = str(note_map.get('notes') or '').strip()

                    if hasattr(self, 'client_notes_input'):
                        self.client_notes_input.blockSignals(True)
                        self.client_notes_input.setPlainText(
                            client_notes_val or legacy_notes_val
                        )
                        self.client_notes_input.blockSignals(False)

                    if hasattr(self, 'dispatcher_notes_input'):
                        cleaned_booking_notes = self._load_delivery_markers_into_ui(
                            booking_notes_val or legacy_notes_val
                        )
                        self.dispatcher_notes_input.blockSignals(True)
                        self.dispatcher_notes_input.setPlainText(
                            cleaned_booking_notes
                        )
                        self.dispatcher_notes_input.blockSignals(False)
                except Exception:
                    try:
                        self.db.rollback()
                    except Exception:
                        pass

                # ── Vehicle & Driver ─────────────────────────────────────
                if vehicle_id and hasattr(self, 'vehicle_combo'):
                    for i in range(self.vehicle_combo.count()):
                        if self.vehicle_combo.itemData(i) == vehicle_id:
                            self.vehicle_combo.setCurrentIndex(i)
                            break

                if requested_vehicle_type and hasattr(self, 'vehicle_type_requested_combo'):
                    idx = self.vehicle_type_requested_combo.findData(
                        requested_vehicle_type
                    )
                    if idx < 0:
                        idx = self.vehicle_type_requested_combo.findText(
                            str(requested_vehicle_type)
                        )
                    if idx >= 0:
                        self.vehicle_type_requested_combo.setCurrentIndex(idx)

                if employee_id and hasattr(self, 'driver_combo'):
                    for i in range(self.driver_combo.count()):
                        if self.driver_combo.itemData(i) == employee_id:
                            self.driver_combo.setCurrentIndex(i)
                            break

                # ── Charter type ──────────────────────────────────────────
                if charter_type and hasattr(self, 'charter_type_combo'):
                    idx = self.charter_type_combo.findText(
                        charter_type, Qt.MatchFlag.MatchFixedString)
                    if idx >= 0:
                        self.charter_type_combo.setCurrentIndex(idx)

                # ── Rates ─────────────────────────────────────────────────
                if hasattr(self, 'quoted_hourly_price'):
                    self.quoted_hourly_price.setText(
                        f"${float(hourly_rate or 0):.2f}"
                    )
                elif hasattr(self, 'hourly_rate_input'):
                    self.hourly_rate_input.setValue(float(hourly_rate))
                if hasattr(self, 'gratuity_percent_input'):
                    self.gratuity_percent_input.setValue(
                        float(gratuity_percent))
                if hasattr(self, 'quoted_hours_input'):
                    self.quoted_hours_input.setValue(float(quoted_hours))
                elif hasattr(self, 'duration_label'):
                    try:
                        self.duration_label.setText(
                            f"{float(quoted_hours or 0):.1f} hrs"
                        )
                    except Exception:
                        pass
                if hasattr(self, 'extra_time_rate_input'):
                    self.extra_time_rate_input.setValue(float(extra_time_rate))
                if hasattr(self, 'standby_rate_input'):
                    self.standby_rate_input.setValue(float(standby_rate))
                if hasattr(self, 'nrr_deposit'):
                    self.nrr_deposit.setText(
                        f"{float(nrr_amount):.2f}" if nrr_amount else "")

                # ── NRD ───────────────────────────────────────────────────
                if hasattr(self, 'nrd_checkbox'):
                    self.nrd_checkbox.setChecked(bool(nrd_received))
                if hasattr(self, 'nrd_amount_input'):
                    self.nrd_amount_input.setValue(float(nrd_amount))
                if hasattr(self, 'nrd_method_combo'):
                    if nrd_method:
                        idx = self.nrd_method_combo.findText(nrd_method)
                        if idx >= 0:
                            self.nrd_method_combo.setCurrentIndex(idx)

                # ── GST ───────────────────────────────────────────────────
                if hasattr(self, 'gst_exempt_checkbox'):
                    self.gst_exempt_checkbox.setChecked(bool(gst_exempt))
                if hasattr(self, 'gst_permit_input'):
                    self.gst_permit_input.setText(gst_permit_number or "")
                if hasattr(self, 'separate_beverage_checkbox'):
                    self.separate_beverage_checkbox.setChecked(
                        bool(beverages_separate))

                # ── Addresses ─────────────────────────────────────────────
                if hasattr(self, 'pickup_address_input') and pickup_address:
                    self.pickup_address_input.setText(pickup_address)
                if hasattr(self, 'dropoff_address_input') and dropoff_address:
                    self.dropoff_address_input.setText(dropoff_address)

                # ── On-duty / drop-off times ──────────────────────────────
                if do_time and hasattr(self, 'on_duty_time'):
                    try:
                        from PyQt6.QtCore import QTime
                        self.on_duty_time.setTime(
                            QTime(do_time.hour, do_time.minute))
                    except Exception:
                        pass
                if dropoff_time and hasattr(self, 'dropoff_time_input'):
                    try:
                        from PyQt6.QtCore import QTime
                        self.dropoff_time_input.setTime(
                            QTime(dropoff_time.hour, dropoff_time.minute))
                    except Exception:
                        pass

                # Load run_type and CC info from charter_data JSON blob
                if charter_data_json:
                    try:
                        payload = (charter_data_json if isinstance(
                            charter_data_json, dict)
                            else json.loads(charter_data_json))
                        run_type = payload.get("run_type")
                        if run_type and hasattr(self, 'run_type_combo'):
                            idx = self.run_type_combo.findText(run_type)
                            if idx >= 0:
                                self.run_type_combo.setCurrentIndex(idx)

                        # Load CC info (only last 4 visible after save)
                        cc_last4 = payload.get("cc_on_file_last4", "")
                        if cc_last4:
                            self.client_cc_checkbox.setChecked(True)
                            self.client_cc_last4.setText(cc_last4)
                            # Full CC field remains masked/empty after save
                            self.client_cc_full.clear()
                            self.client_cc_full.setEnabled(False)
                    except Exception as e:
                        print(f"Error loading charter_data JSON: {e}")

                if routing_type and hasattr(self, 'run_type_combo'):
                    idx = self.run_type_combo.findText(str(routing_type))
                    if idx >= 0:
                        self.run_type_combo.setCurrentIndex(idx)

                # ✨ LOAD ROUTES & CHARGES & BEVERAGES ✨
                # Use separate cursors to avoid aborting the main transaction
                # on partial failures
                try:
                    cur_routes = self.db.get_cursor()
                    self.load_charter_routes(charter_id, cur_routes)
                    cur_routes.close()
                    self._sync_routing_from_pickup_dropoff_times()
                except Exception as e:
                    try:
                        self.db.rollback()
                    except Exception:
                        pass
                    print(f"❌ Error loading routes: {e}")

                try:
                    cur_charges = self.db.get_cursor()
                    self.load_charter_charges(charter_id, cur_charges)
                    cur_charges.close()
                except Exception as e:
                    try:
                        self.db.rollback()
                    except Exception:
                        pass
                    print(f"❌ Error loading charges: {e}")

                try:
                    cur_bev = self.db.get_cursor()
                    self.load_charter_beverages(
                        charter_id, cur_bev)  # 🍷 NEW: Load saved beverages
                    cur_bev.close()
                except Exception as e:
                    try:
                        self.db.rollback()
                    except Exception:
                        pass
                    print(f"❌ Error loading beverages: {e}")

                # Store reserve_number for use in save_charter_charges
                self._current_reserve_number = reserve_number

                if hasattr(self, "active_charter_label"):
                    self.active_charter_label.setText(
                        f"Viewing Reserve #{reserve_number} (ID {charter_id})"
                    )

                if hasattr(self, "quick_lookup") and hasattr(
                    self.quick_lookup, "charter_input"):
                    self.quick_lookup.charter_input.setText(
                        str(reserve_number))

                # Load driver pay panel
                try:
                    cur_dp = self.db.get_cursor()
                    cur_dp.execute("""
                        SELECT calculated_hours, approved_hours,
                               driver_hourly_rate,
                               driver_gratuity, approved_gratuity
                        FROM charters WHERE charter_id = %s
                    """, (charter_id,))
                    dp_row = cur_dp.fetchone()
                    cur_dp.close()
                    if dp_row:
                        self._load_driver_pay({
                            'calculated_hours': dp_row[0],
                            'approved_hours':   dp_row[1],
                            'driver_hourly_rate': dp_row[2],
                            'driver_gratuity':  dp_row[3],
                            'approved_gratuity': dp_row[4],
                        })
                except Exception as e:
                    print(f"❌ Error loading driver pay: {e}")

                # Load payments from charter_payments table
                try:
                    self._load_charter_payments(reserve_number)
                except Exception as e:
                    print(f"❌ Error loading payments: {e}")

        except Exception as e:
            try:
                self.db.rollback()
            except Exception:
                pass
            QMessageBox.warning(self, "Error", f"Failed to load charter: {e}")

    def load_client(self, client_id: int):
        """Pre-fill charter form with selected client (for new charters)"""
        try:
            try:
                self.db.rollback()
            except Exception:
                pass

            cur = self.db.get_cursor()
            cur.execute("""
                SELECT client_id, client_name,
                primary_phone, email, address_line1, city
                FROM clients
                WHERE client_id = %s
            """, (client_id,))

            row = cur.fetchone()
            if row:
                client_id, client_name, phone, email, address, city = row

                # Pre-fill the customer widget with selected client
                # Clear selection
                self.customer_widget.client_combo.setCurrentIndex(-1)

                # Find client in combo and select it, or just fill fields
                for i in range(self.customer_widget.client_combo.count()):
                    if (str(client_id)
                            in self.customer_widget.client_combo.itemData(
                                    i, Qt.ItemDataRole.UserRole)
                                    or client_name
                                    in self.customer_widget
                                    .client_combo.itemText(i)):
                        self.customer_widget.client_combo.setCurrentIndex(i)
                        break
                else:
                    # If not found in combo, just fill the text fields
                    self.customer_widget.client_combo.setCurrentIndex(0)

                # Fill in contact info
                self.customer_widget.phone_input.setText(phone or "")
                self.customer_widget.email_input.setText(email or "")
                self.customer_widget.address_input.setText(address or "")

                # Store client ID
                self.client_id = client_id

                # Check for NRR in escrow for this client and offer to apply it
                self.check_and_offer_escrow_nrr(client_id, client_name)

        except Exception as e:
            try:
                self.db.rollback()
            except Exception:
                pass
            print(f"Error pre-filling client: {e}")

    def _compose_nrr_moved_forward_note(self, escrow_info: dict) -> str:
        amount = float(escrow_info.get('amount', 0) or 0)
        from_reserve = str(escrow_info.get('from_reserve', '') or '')
        if from_reserve:
            return (
                f"NRR moved forward: ${amount:.2f} "
                f"from cancelled reserve #{from_reserve}"
            )
        return f"NRR moved forward: ${amount:.2f}"

    def check_and_offer_escrow_nrr(self, client_id: int, client_name: str):
        """Check if client has NRR in escrow and
        offer to apply to new charter"""
        try:
            cur = self.db.get_cursor()

            # Find cancelled charters with NRR for this client
            cur.execute("""
                SELECT charter_id,
                       reserve_number,
                       COALESCE(
                           NULLIF(charter_data->>'nrr_received', '')::numeric,
                           nrr_amount,
                           0
                       ) as nrr_amount,
                       status
                FROM charters
                WHERE client_id = %s
                  AND status = 'Cancelled'
                  AND COALESCE(
                      NULLIF(charter_data->>'nrr_escrow_applied', '')::boolean,
                      FALSE
                  ) = FALSE
                  AND COALESCE(
                      NULLIF(charter_data->>'nrr_received', '')::numeric,
                      nrr_amount,
                      0
                  ) > 0
                ORDER BY charter_id DESC
                LIMIT 1
            """, (client_id,))

            escrow_charter = cur.fetchone()

            if escrow_charter:
                charter_id, reserve_num, nrr_num, status = escrow_charter
                nrr_amount = float(nrr_num) if nrr_num else 0.0

                # Show escrow indicator and ask to apply
                response = QMessageBox.question(
                    self,
                    "🔒 NRR in Escrow",
                    f"Customer {client_name} has "
                    f"${nrr_amount:.2f} NRR in escrow\n"
                    f"(from cancelled reserve #{reserve_num})\n\n"
                    "Apply this NRR to the new charter?",
                    ((QMessageBox.StandardButton.Yes
             | QMessageBox.StandardButton.No)))

                if response == QMessageBox.StandardButton.Yes:
                    # Apply NRR to new charter
                    self.apply_escrow_nrr(
                        client_id, charter_id, nrr_amount, reserve_num)

        except Exception as e:
            print(f"Error checking escrow NRR: {e}")

    def apply_escrow_nrr(
            self,
            client_id: int,
            from_charter_id: int,
            nrr_amount: float,
            from_reserve: str):
        """Apply NRR from escrow to new charter"""
        try:
            # Pre-fill the NRR field
            if hasattr(self, 'nrr_received'):
                self.nrr_received.setValue(nrr_amount)

            # Store escrow source for GL coding on save
            self._escrow_nrr_applied = {
                'from_charter_id': from_charter_id,
                'from_reserve': from_reserve,
                'amount': nrr_amount}

            move_note = self._compose_nrr_moved_forward_note(
                self._escrow_nrr_applied
            )
            if hasattr(self, 'dispatcher_notes_input'):
                existing = self.dispatcher_notes_input.toPlainText().strip()
                if move_note not in existing:
                    combined = (
                        f"{existing}\n{move_note}".strip()
                        if existing
                        else move_note
                    )
                    self.dispatcher_notes_input.setPlainText(combined)

            # Show confirmation
            QMessageBox.information(
                self,
                "Escrow NRR Applied",
                f"✅ Applied ${nrr_amount:.2f} from escrow"
                f" (reserve #{from_reserve})\n"
                "Listed as NRR moved forward on this booking and "
                "GL coded when you save.")

        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to apply escrow NRR: {e}")

    def new_charter(self):
        """Clear form for new charter entry"""
        response = QMessageBox.question(
            self,
            "New Charter",
            "Clear form for new charter entry?\n(Any unsaved changes will be "
            "lost)",
            ((QMessageBox.StandardButton.Yes
             | QMessageBox.StandardButton.No)))

        if response == QMessageBox.StandardButton.Yes:
            self.charter_id = None
            if hasattr(self, "active_charter_label"):
                self.active_charter_label.setText("New charter (unsaved)")
            if hasattr(self, "booking_tab_widget"):
                self.booking_tab_widget.setCurrentIndex(0)
            # Reset customer widget
            self.customer_widget.reserve_input.setText("")
            self.customer_widget.client_combo.setCurrentIndex(0)
            self.customer_widget.phone_input.setText("")
            self.customer_widget.email_input.setText("")
            self.customer_widget.address_input.setText("")
            self.customer_widget.enter_edit_mode()
            # Reset other fields
            try:
                self.pickup_datetime.setDateTime(QDateTime.currentDateTime())
                self.dropoff_datetime.setDateTime(
                    QDateTime.currentDateTime().addSecs(2 * 60 * 60))
            except Exception:
                pass
            self.num_passengers.setValue(1)
            self.status_combo.setCurrentText("Quote")
            self.route_table.setRowCount(0)
            self.charges_table.setRowCount(0)
            self.net_total.setText("$0.00")
            self.gst_total.setText("$0.00")
            self.gross_total.setText("$0.00")

    def _build_liability_terms_block(self, heading: str) -> str:
        """Shared legal terms block used by confirmation and quote output."""
        block = "=" * 80 + "\n"
        block += f"{heading}\n"
        block += "=" * 80 + "\n\n"

        block += (
            "1. Customer hereby verifies that the rental date, anticipated "
            "times, number of people and billing information are correctly "
            "stated.\n\n"
        )
        block += (
            "2. Customer shall be liable for all damages to the limousine "
            "sustained during Customer's charter, including all spills, "
            "burns, rips, tears, or damage to the television, stereo or "
            "other electrical or power equipment.\n\n"
        )
        block += (
            "3. Customer shall pay a service charge of $200.00 to clean any "
            "vomit in the limousine.\n\n"
        )
        block += (
            "4. Customer shall not open any emergency exits, including the "
            "sunroof/emergency escape hatch. Penalty is $850.00.\n\n"
        )
        block += (
            "5. While the vehicle is in motion Customers shall refrain from "
            "exiting the vehicle, or littering.\n\n"
        )
        block += (
            "6. Arrow Limousine reserves the right, without any liability or "
            "set-off to the amounts due the charter, to discharge any "
            "passenger(s) who interferes with the safe operation of the "
            "vehicle, vomits, or engages in any illegal conduct or activity."
            "\n\n"
        )
        block += (
            "7. Arrow Limousine shall not be liable for any damages arising "
            "out of the inability to perform due to inclement weather, "
            "mechanical difficulties, delays due to traffic conditions, or "
            "any unforeseen events beyond the reasonable control of Arrow "
            "Limousine.\n\n"
        )
        block += (
            "8. Arrow Limousine shall not be the Bailee of any items left in "
            "the Limousine, and shall not be responsible for the safe-keeping "
            "of any such item.\n\n"
        )
        block += (
            "9. Customer must pay a NON-REFUNDABLE retainer equal to two "
            "hour vehicle rate, with the balance due prior to the charter "
            "pickup.\n\n"
        )
        block += (
            "10. Customer hereby authorizes Arrow Limousine to charge the "
            "credit card on file for the full amount of the charter.\n\n"
        )
        block += "ACCEPTANCE OF TERMS\n\n"
        block += (
            "By agreeing to the discounted rate, the Client waives any "
            "claims regarding vehicle age, cosmetic condition, climate "
            "control irregularities (heating/air conditioning), or "
            "non-essential amenities, as long as the service meets safety "
            "and regulatory requirements.\n\n"
        )
        return block

    def print_confirmation(self):
        """
        Generate and print charter confirmation letter with liability clauses
        and key charter details
        """
        if not self.charter_id:
            QMessageBox.warning(self, "Warning", "Please save charter first")
            return

        # Primary path: open the auto-filled PDF confirmation letter.
        self.print_confirmation_pdf()
        return

        try:
            # Get customer data from widget
            customer_data = self.customer_widget.get_customer_data()
            reserve_num = self.customer_widget.reserve_input.text(
            ) or f"NEW-{self.charter_id}"
            customer_name = customer_data.get("client_name") or "Client"

            charter_date_from = self.charter_date_from.date().toString(
                "MM/dd/yyyy") if hasattr(self, "charter_date_from") else ""
            charter_date_to = (self.charter_date_to.date().toString(
                "MM/dd/yyyy")
                if hasattr(self, "charter_date_to")
                else charter_date_from)
            pickup_time = self.base_time_from.time().toString(
                "HH:mm") if hasattr(self, "base_time_from") else ""
            dropoff_time = self.base_time_to.time().toString(
                "HH:mm") if hasattr(self, "base_time_to") else ""

            status_text = self.charter_status_combo.currentText(
            ) if hasattr(self, "charter_status_combo") else ""
            charter_type = self.charter_type_combo.currentText(
            ) if hasattr(self, "charter_type_combo") else ""
            run_type = self.run_type_combo.currentText(
            ) if hasattr(self, "run_type_combo") else ""
            rate_type = self.rate_type_combo.currentText(
            ) if hasattr(self, "rate_type_combo") else ""
            requested_vehicle = self.vehicle_type_requested_combo.currentText(
            ) if hasattr(self, "vehicle_type_requested_combo") else ""
            assigned_vehicle = (
                self.vehicle_combo.currentText()
                if hasattr(self,
                "vehicle_combo") else "")


            assigned_driver = (
                self.driver_combo.currentText()
                if hasattr(self, "driver_combo") else "")


            gratuity_percent = self.gratuity_percent_input.value(
            ) if hasattr(self, "gratuity_percent_input") else 0.0

            # Invoice items from service charges
            line_items = []
            service_total = 0.0
            for row in range(self.charges_table.rowCount()):
                desc_item = self.charges_table.item(row, 0)
                type_item = self.charges_table.item(row, 1)
                total_item = self.charges_table.item(row, 2)
                if not desc_item or not total_item:
                    continue

                desc = (desc_item.text() or "").strip()
                item_type = (type_item.text() if type_item else "") or "-"
                raw_amt = (total_item.text() or "0").replace(
                    "$", "").replace(",", "").strip()
                try:
                    amt = float(raw_amt)
                except Exception:
                    amt = 0.0

                service_total += amt
                line_items.append((desc, item_type, amt))

            # Beverage items from saved snapshot rows
            beverage_total = 0.0
            if self.charter_id:
                try:
                    cur = self.db.get_cursor()
                    cur.execute(
                        """
                        SELECT item_name, quantity, line_amount_charged
                        FROM charter_beverages
                        WHERE charter_id = %s
                        ORDER BY created_at
                        """,
                        (self.charter_id,),
                    )
                    for item_name, qty, line_amt in cur.fetchall():
                        line_amount = float(line_amt or 0.0)
                        beverage_total += line_amount
                        line_items.append(
                            (f"Beverage: {item_name} x{qty}",
                             "bev", line_amount))
                    cur.close()
                except Exception:
                    try:
                        self.db.rollback()
                    except Exception:
                        pass

            gross_total = service_total + beverage_total
            gst_amount = gross_total * 0.05 / 1.05 if gross_total else 0.0
            subtotal_before_gst = gross_total - gst_amount

            nrr_amount = (
                self.nrr_received.value()
                if hasattr(self, 'nrr_received') else 0.0)
            payments_total = 0.0
            if hasattr(self, "payments_table"):
                for row in range(self.payments_table.rowCount()):
                    amount_item = self.payments_table.item(row, 2)
                    if not amount_item:
                        continue
                    raw_payment = (amount_item.text() or "0").replace(
                        "$", "").replace(",", "").strip()
                    try:
                        payments_total += float(raw_payment)
                    except Exception:
                        continue

            total_received = nrr_amount + payments_total
            balance_due = round(gross_total - total_received, 2)

            client_notes = (
                self.client_notes_input.toPlainText().strip()
                if hasattr(self, 'client_notes_input') else "")


            # Build client confirmation package
            text = "═" * 96 + "\n"
            text += "ARROW LIMOUSINE - CLIENT CHARTER CONFIRMATION\n"
            text += "═" * 96 + "\n"
            text += f"Generated: {datetime.now().strftime('%m/%d/%Y %H:%M')}\n"
            text += f"Reservation Number: {reserve_num}\n"
            text += f"Charter ID: {self.charter_id}\n\n"

            text += f"Dear {customer_name},\n\n"
            text += "This is your auto-filled booking confirmation.\n\n"

            text += "BOOKING REQUIREMENTS\n"
            text += "─" * 96 + "\n"
            text += f"Status: {status_text}\n"
            text += f"Charter Type: {charter_type}\n"
            text += f"Run Type: {run_type}\n"
            text += f"Rate Type: {rate_type}\n"
            text += f"Passengers: {self.num_passengers.value()}\n"
            text += f"Date: {charter_date_from} to {charter_date_to}\n"
            text += f"Pickup/Dropoff Time: {pickup_time} to {dropoff_time}\n"
            text += f"Requested Vehicle Type: {requested_vehicle}\n"
            text += f"Assigned Vehicle: {assigned_vehicle}\n"
            text += f"Assigned Driver: {assigned_driver}\n"
            text += f"Gratuity Setting: {gratuity_percent:.1f}%\n\n"

            text += "CLIENT CONTACT\n"
            text += "─" * 96 + "\n"
            text += f"Client: {customer_name}\n"
            text += f"Phone: {customer_data.get('phone', '')}\n"
            text += f"Email: {customer_data.get('email', '')}\n"
            text += f"Address: {customer_data.get('address', '')}\n\n"

            text += "BOOKING ITINERARY\n"
            text += "─" * 96 + "\n"
            itinerary_added = False
            for row_idx in range(self.route_table.rowCount()):
                event_combo = self.route_table.cellWidget(row_idx, 0)
                if event_combo:
                    event_name = event_combo.currentText()
                else:
                    event_item = self.route_table.item(row_idx, 0)
                    event_name = event_item.text() if event_item else "Stop"

                location_item = self.route_table.item(row_idx, 1)
                time_item = self.route_table.item(row_idx, 3)
                location = location_item.text().strip(
                ) if location_item and location_item.text() else ""
                stop_time = (
                    time_item.text().strip()
                    if time_item and time_item.text() else "")

                if location or stop_time:
                    itinerary_added = True
                    text += f"- {event_name}: {location}"
                    if stop_time:
                        text += f" at {stop_time}"
                    text += "\n"

            if not itinerary_added:
                text += "- No itinerary stops entered yet.\n"
            text += "\n"

            text += "INVOICE ITEMS\n"
            text += "─" * 96 + "\n"
            text += f"{'Description':<66} {'Type':<8} {'Amount':>14}\n"
            text += "─" * 96 + "\n"
            if line_items:
                for desc, item_type, amount in line_items:
                    text += (
                        f"{desc:<66.66} {item_type:<8.8}"
                        f" ${amount:>12.2f}\n")
            else:
                text += "No charge lines entered yet.\n"
            text += "─" * 96 + "\n"
            text += (
                f"Subtotal (before GST): {'':<46} "
                f"${subtotal_before_gst:>12.2f}\n")
            text += f"GST (5% included): {'':<49} ${gst_amount:>12.2f}\n"
            text += f"TOTAL CHARGES: {'':<54} ${gross_total:>12.2f}\n"
            text += "\n"

            text += "PAYMENTS / NRR / BALANCE\n"
            text += "─" * 96 + "\n"
            text += (
                f"NRR Received (booking fee): {'':<38} "
                f"${nrr_amount:>12.2f}\n")
            text += (
                f"Other Payments Received: {'':<40} "
                f"${payments_total:>12.2f}\n")
            text += f"Total Received: {'':<50} ${total_received:>12.2f}\n"
            text += f"BALANCE DUE: {'':<52} ${balance_due:>12.2f}\n\n"

            text += "BOOKING NOTES\n"
            text += "─" * 96 + "\n"
            if client_notes:
                text += f"{client_notes}\n\n"
            else:
                text += "No client notes entered.\n\n"

            # ====== LIABILITY CLAUSES (CRITICAL - LEGAL PROTECTION) ======
            text += self._build_liability_terms_block("LIABILITIES & TERMS")

            text += "=" * 96 + "\n"
            text += "Thank you for your business.\n"
            text += "Arrow Limousine & Sedan Services Ltd.\n"
            text += "Phone: 403-340-3466\n"
            text += "Email: info@arrowlimo.ca\n"
            text += "=" * 96 + "\n"

            self.show_print_dialog("Charter Confirmation Letter", text)

            if (
                hasattr(self, 'vehicle_inspection_checkbox')
                and self.vehicle_inspection_checkbox.isChecked()
            ):
                self._print_daily_inspection_form()

        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to generate confirmation letter: {e}")

    def _gather_confirmation_pdf_data(self):
        """Collect data for confirmation-letter PDF generation."""
        data = self._gather_run_sheet_data()
        customer_data = self.customer_widget.get_customer_data()

        def _display_name(first_name, last_name, company_name, fallback_name):
            company = (company_name or "").strip()
            if company:
                return company

            first = (first_name or "").strip()
            last = (last_name or "").strip()
            if first and last:
                return f"{first} {last}".strip()
            if first:
                return first

            raw = (fallback_name or "").strip()
            if "," in raw:
                parts = [p.strip() for p in raw.split(",", 1)]
                if len(parts) == 2 and parts[1]:
                    return f"{parts[1]} {parts[0]}".strip()
            return raw

        # Client naming aliases used by confirmation PDF template.
        data["client_display_name"] = _display_name(
            customer_data.get("first_name"),
            customer_data.get("last_name"),
            customer_data.get("company_name"),
            customer_data.get("client_name") or data.get("client_name") or "",
        )
        data["company_name"] = (customer_data.get("company_name") or "").strip()
        data["first_name"] = (customer_data.get("first_name") or "").strip()
        data["last_name"] = (customer_data.get("last_name") or "").strip()

        # Provide pickup/dropoff aliases for fallback itinerary rendering.
        routes = data.get("routes") or []
        if routes:
            data["pickup_address"] = routes[0].get("address") or ""
            data["dropoff_address"] = routes[-1].get("address") or ""

        payment_method = ""
        if hasattr(self, "payment_method_combo"):
            payment_method = self.payment_method_combo.currentText().strip()
        elif hasattr(self, "payment_method_input"):
            payment_method = self.payment_method_input.text().strip()
        data["payment_method"] = payment_method

        # Prefer persisted totals/method when available.
        if self.charter_id:
            try:
                cur = self.db.get_cursor()
                cur.execute(
                    """
                    SELECT c.reserve_number,
                           c.charter_date,
                           COALESCE(c.pickup_time, c.reservation_time, c.do_time),
                           COALESCE(c.dropoff_time, c.do_time),
                           COALESCE(c.total_amount_due, c.grand_total, 0),
                           COALESCE(c.amount_paid, c.paid_amount, 0),
                           COALESCE(c.nrr_amount, 0),
                           COALESCE(c.vehicle, ''),
                           COALESCE(c.payment_status, ''),
                           COALESCE(cl.first_name, ''),
                           COALESCE(cl.last_name, ''),
                           COALESCE(cl.company_name, ''),
                           COALESCE(cl.client_name, cl.name, '')
                    FROM charters c
                    LEFT JOIN clients cl ON cl.client_id = c.client_id
                    WHERE c.charter_id = %s
                    """,
                    (self.charter_id,),
                )
                row = cur.fetchone()
                if row:
                    (
                        reserve_no,
                        c_date,
                        c_pickup,
                        c_dropoff,
                        total_due,
                        paid_amt,
                        nrr_amt,
                        vehicle_name,
                        payment_status,
                        first_name,
                        last_name,
                        company_name,
                        fallback_name,
                    ) = row

                    if reserve_no:
                        data["reserve_number"] = str(reserve_no)
                    if c_date:
                        data["charter_date"] = str(c_date)
                    if c_pickup:
                        data["pickup_time"] = str(c_pickup)
                    if c_dropoff:
                        data["dropoff_time"] = str(c_dropoff)
                    data["total_amount_due"] = float(total_due or 0)
                    data["total_paid"] = float(paid_amt or 0)
                    data["nrr_amount"] = float(nrr_amt or 0)
                    if vehicle_name and not data.get("vehicle_description"):
                        data["vehicle_description"] = str(vehicle_name)
                    if payment_status and not data.get("payment_status"):
                        data["payment_status"] = str(payment_status)

                    data["first_name"] = (first_name or "").strip()
                    data["last_name"] = (last_name or "").strip()
                    data["company_name"] = (company_name or "").strip()
                    data["client_display_name"] = _display_name(
                        first_name,
                        last_name,
                        company_name,
                        fallback_name,
                    )

                # Authoritative routing rows from charter_routes.
                cur.execute(
                    """
                    SELECT COALESCE(event_type_code, ''),
                           COALESCE(address, pickup_location, dropoff_location, ''),
                           COALESCE(stop_time, pickup_time, dropoff_time),
                           COALESCE(route_notes, ''),
                           COALESCE(route_sequence, 0)
                    FROM charter_routes
                    WHERE charter_id = %s
                    ORDER BY route_sequence, route_id
                    """,
                    (self.charter_id,),
                )
                route_rows = cur.fetchall()
                if route_rows:
                    data["routes"] = [
                        {
                            "event_type_code": event_code,
                            "address": address,
                            "at_by": "at",
                            "stop_time": str(stop_time) if stop_time else "",
                            "route_notes": route_notes,
                            "route_sequence": int(seq or 0),
                        }
                        for event_code, address, stop_time, route_notes, seq in route_rows
                    ]
                    data["pickup_address"] = data["routes"][0].get("address") or ""
                    data["dropoff_address"] = data["routes"][-1].get("address") or ""

                # Authoritative invoicing rows from charter_charges.
                cur.execute(
                    """
                    SELECT COALESCE(description, ''),
                           COALESCE(amount, 0),
                           COALESCE(rate, 0),
                           COALESCE(charge_type, '')
                    FROM charter_charges
                    WHERE charter_id = %s
                    ORDER BY sequence, charge_id
                    """,
                    (self.charter_id,),
                )
                charge_rows = cur.fetchall()
                if charge_rows:
                    data["charges"] = [
                        {
                            "description": desc,
                            "amount": float(amount or 0),
                            "rate": float(rate or 0),
                            "charge_type": charge_type,
                        }
                        for desc, amount, rate, charge_type in charge_rows
                    ]

                # Payment + NRR from charter_payments (authoritative source).
                reserve_key = str(data.get("reserve_number") or "")
                cur.execute(
                    """
                    SELECT COALESCE(amount, 0),
                           LOWER(COALESCE(payment_method, '')),
                           payment_date
                    FROM charter_payments
                    WHERE charter_id = %s OR charter_id = %s
                    ORDER BY payment_date NULLS LAST, id
                    """,
                    (reserve_key, str(self.charter_id)),
                )
                payment_rows = cur.fetchall()
                if payment_rows:
                    total_paid = 0.0
                    nrr_paid = 0.0
                    preferred_method = ""
                    for amount, method, _pay_date in payment_rows:
                        amt = float(amount or 0)
                        total_paid += amt
                        if method in {"nrr", "retainer"}:
                            nrr_paid += amt
                        if not preferred_method and method:
                            preferred_method = method

                    data["total_paid"] = total_paid
                    if nrr_paid > 0:
                        data["nrr_amount"] = nrr_paid
                    if preferred_method and not data.get("payment_method"):
                        data["payment_method"] = preferred_method

                cur.close()
            except Exception:
                try:
                    self.db.rollback()
                except Exception:
                    pass

        return data

    def print_confirmation_pdf(self):
        """Generate and open the auto-filled client confirmation letter PDF."""
        import os
        import sys
        import traceback

        try:
            proj_root = os.path.abspath(
                os.path.join(os.path.dirname(__file__), os.pardir)
            )
            if proj_root not in sys.path:
                sys.path.insert(0, proj_root)

            from modern_backend.app.services.pdf_generator import (
                generate_confirmation_letter_pdf,
            )

            data = self._gather_confirmation_pdf_data()
            pdf_bytes = generate_confirmation_letter_pdf(data)
            reserve = data.get("reserve_number") or str(self.charter_id)
            self._open_pdf_bytes(pdf_bytes, f"confirmation_{reserve}.pdf")
        except Exception as e:
            QMessageBox.critical(
                self,
                "PDF Error",
                f"Failed to generate confirmation letter PDF:\n{e}\n\n"
                f"{traceback.format_exc()[:500]}",
            )

    def _load_pricing_defaults(self, vehicle_type: str) -> Dict[str, float]:
        """Fetch pricing defaults for vehicle type (new schema)."""
        vtype = (vehicle_type or "").strip()
        defaults = {
            "nrr": 0.0,
            "hourly_rate": 0.0,
            "daily_rate": 0.0,
            "standby_rate": 0.0,
            "airport_pickup_calgary": 0.0,
            "airport_pickup_edmonton": 0.0, }

        if not vtype:
            return defaults

        try:
            cur = self.db.get_cursor()
            cur.execute(
                """
                SELECT nrr, hourly_rate, daily_rate, standby_rate,
                       airport_pickup_calgary, airport_pickup_edmonton
                FROM vehicle_pricing_defaults
                WHERE vehicle_type = %s
                """,
                (vtype,),)
            row = cur.fetchone()
            cur.close()

            if row:
                (
                    nrr,
                    hourly_rate,
                    daily_rate,
                    standby_rate,
                    airport_cgy,
                    airport_edm,) = row
                if nrr is not None:
                    defaults["nrr"] = float(nrr)
                if hourly_rate is not None:
                    defaults["hourly_rate"] = float(hourly_rate)
                if daily_rate is not None:
                    defaults["daily_rate"] = float(daily_rate)
                if standby_rate is not None:
                    defaults["standby_rate"] = float(standby_rate)
                if airport_cgy is not None:
                    defaults["airport_pickup_calgary"] = float(airport_cgy)
                if airport_edm is not None:
                    defaults["airport_pickup_edmonton"] = float(airport_edm)

        except Exception:
            try:
                self.db.rollback()
            except Exception:
                pass

        return defaults

    def _prompt_quote_options(self) -> Optional[Dict[str, object]]:
        """Dialog to pick which quote options to include or free-text
        conversation price."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Quote Options")

        vlayout = QVBoxLayout()

        mode_all = QRadioButton(
            "Show all standard options (Hourly, Package, Split Run)")
        mode_select = QRadioButton("Choose specific options")
        mode_custom = QRadioButton("Conversation price only")
        mode_all.setChecked(True)

        vlayout.addWidget(mode_all)
        vlayout.addWidget(mode_select)
        vlayout.addWidget(mode_custom)

        select_layout = QVBoxLayout()
        select_layout.setContentsMargins(20, 0, 0, 0)
        chk_hourly = QCheckBox("Include Hourly")
        chk_package = QCheckBox("Include Package")
        chk_split = QCheckBox("Include Split Run")
        for chk in (chk_hourly, chk_package, chk_split):
            chk.setChecked(True)
            select_layout.addWidget(chk)
        vlayout.addLayout(select_layout)

        custom_layout = QVBoxLayout()
        custom_layout.setContentsMargins(20, 0, 0, 0)
        custom_label = QLabel("Conversation price / notes:")
        custom_text = QLineEdit()
        custom_text.setPlaceholderText("e.g., Special flat rate $500 all-in")
        custom_layout.addWidget(custom_label)
        custom_layout.addWidget(custom_text)
        vlayout.addLayout(custom_layout)

        buttons = QDialogButtonBox(
            ((QDialogButtonBox.StandardButton.Ok
             | QDialogButtonBox.StandardButton.Cancel)))
        vlayout.addWidget(buttons)

        def update_state():
            select_enabled = mode_select.isChecked()
            for chk in (chk_hourly, chk_package, chk_split):
                chk.setEnabled(select_enabled)
            custom_enabled = mode_custom.isChecked()
            custom_label.setEnabled(custom_enabled)
            custom_text.setEnabled(custom_enabled)

        mode_all.toggled.connect(update_state)
        mode_select.toggled.connect(update_state)
        mode_custom.toggled.connect(update_state)
        update_state()

        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        dialog.setLayout(vlayout)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None

        if mode_custom.isChecked():
            note = custom_text.text().strip()
            if not note:
                QMessageBox.warning(
                    self,
                    "Missing price",
                    "Enter a conversation price or note.")
                return None
            return {"mode": "custom", "note": note}

        include_hourly = include_package = include_split = True
        if mode_select.isChecked():
            include_hourly = chk_hourly.isChecked()
            include_package = chk_package.isChecked()
            include_split = chk_split.isChecked()
            if not any([include_hourly, include_package, include_split]):
                QMessageBox.warning(
                    self,
                    "Select an option",
                    "Pick at least one quote option to include.")
                return None

        return {
            "mode": "standard",
            "hourly": include_hourly,
            "package": include_package,
            "split": include_split, }

    def print_quote(self):
        """
        Generate and print quote letter with 3 pricing options:
        1. Hourly Rate
        2. Package Rate
        3. Split Run Rate (with driver waiting)

        Includes liability clauses same as confirmation letter.
        """
        try:
            options = self._prompt_quote_options()
            if not options:
                return

            # Get customer data from widget
            customer_data = self.customer_widget.get_customer_data()
            reserve_num = (
                self.customer_widget.reserve_input.text()
                or "QUOTE-NEW")

            # Get estimated hours from form
            try:
                estimated_hours = getattr(
                    self, "_calculated_total_hours", None) or 6.0
            except Exception:
                estimated_hours = 6.0

            # Apply minimum hours from pricing defaults
            vehicle_type = (
                self.vehicle_type_label.text().strip()
                if hasattr(self, 'vehicle_type_label') else "")
            pricing_defaults = self._load_pricing_defaults(vehicle_type)
            hourly_min = pricing_defaults.get(
                "hourly", {}).get(
                "minimum_hours", 0.0)
            if hourly_min:
                estimated_hours = max(estimated_hours, hourly_min)

            # Get vehicle type
            vehicle_type_display = vehicle_type or "Luxury SUV"

            # Build quote letter
            text = (
                f"{datetime.now().strftime('%m/%d/%Y')}"
                f"\t\t\t\t\tYour Quote Number is {reserve_num}.\n")
            text += (
                "\t\t\t\t\t\t\t"
                "Please reference this number when contacting us.\n\n")
            text += f"Dear {customer_data['client_name']}:\n\n"
            text += (
                "Thank you for your interest in "
                "Arrow Limousine & Sedan Services Ltd.\n\n")
            text += (
                "We are pleased to provide you with "
                "the following pricing options "
                     "for your transportation needs:\n\n")

            # Service details
            text += (
                f"Date for Service: "
                f"{self.charter_date.getDate().toString('MM/dd/yyyy')}\n")
            text += f"Estimated Time: {self.pickup_time.text()}\n"
            text += f"Vehicle Type: {vehicle_type_display}\n"
            text += f"Passengers: {self.num_passengers.value()}\n\n"

            # Itinerary summary
            text += "Service Details:\n"

            def _cell_text(row_idx: int, col_idx: int) -> str:
                item = self.route_table.item(row_idx, col_idx)
                return item.text().strip() if item else ""

            for row_idx in range(self.route_table.rowCount()):
                pickup_loc = _cell_text(row_idx, 1)
                pickup_time = _cell_text(row_idx, 2)
                dropoff_loc = _cell_text(row_idx, 3)
                dropoff_time = _cell_text(row_idx, 4)
                leg_notes = _cell_text(row_idx, 5)
                if any([pickup_loc,
                        pickup_time,
                        dropoff_loc,
                        dropoff_time,
                        leg_notes]):
                    text += f"  Leg {row_idx + 1}: "
                    parts = []
                    if pickup_loc:
                        parts.append(f"From {pickup_loc}")
                    if pickup_time:
                        parts.append(f"Pickup {pickup_time}")
                    if dropoff_loc:
                        parts.append(f"To {dropoff_loc}")
                    if dropoff_time:
                        parts.append(f"Drop {dropoff_time}")
                    text += ", ".join(parts) + "\n"
                    if leg_notes:
                        text += f"    Notes: {leg_notes}\n"

            # Out-of-town routing details
            if (hasattr(
                    self,
                    'out_of_town_checkbox')
                    and self.out_of_town_checkbox.isChecked()):
                depart_loc = self.depart_from_red_deer.text().strip()
                depart_time = self.depart_by_time.text().strip()
                return_loc = self.return_to_red_deer.text().strip()
                return_time = self.return_by_time.text().strip()
                text += "\nOut-of-town routing:\n"
                if depart_loc or depart_time:
                    text += "  Depart Red Deer for "
                    text += depart_loc if depart_loc else "(unspecified)"
                    if depart_time:
                        text += f" by {depart_time}"
                    text += "\n"
                if return_loc or return_time:
                    text += "  Return to Red Deer"
                    if return_loc:
                        text += f" via {return_loc}"
                    if return_time:
                        text += f" by {return_time}"
                    text += "\n"

            if hasattr(self, 'driver_routing_notes'):
                extra_notes = self.driver_routing_notes.text().strip()
                if extra_notes:
                    text += f"\nDriver routing notes: {extra_notes}\n"

            text += "\n"

            # ====== PRICING OPTIONS ======
            text += "=" * 80 + "\n"
            text += "PRICING OPTIONS\n"
            text += "=" * 80 + "\n\n"

            hourly_cfg = pricing_defaults.get("hourly", {})
            package_cfg = pricing_defaults.get("package", {})
            split_cfg = pricing_defaults.get("split_run", {})

            hourly_rate = hourly_cfg.get("hourly_rate", 195.0)
            package_rate = package_cfg.get("package_rate", 1170.0)
            package_hours = package_cfg.get("package_hours", 6.0)
            extra_time_rate = package_cfg.get(
                "extra_time_rate", hourly_cfg.get(
                    "extra_time_rate", hourly_rate))
            split_run_before = split_cfg.get("split_run_before_hours", 1.5)
            split_run_after = split_cfg.get("split_run_after_hours", 1.5)
            standby_rate = split_cfg.get("standby_rate", 25.0)

            hourly_total = package_total = split_total = 0.0

            if options["mode"] == "custom":
                text += "CUSTOM / CONVERSATION PRICE\n"
                text += "-" * 80 + "\n"
                text += f"Details: {options['note']}\n\n"
            else:
                if options.get("hourly"):
                    hourly_total = hourly_rate * estimated_hours
                    gst_hourly, net_hourly = GSTCalculator.calculate_gst(
                        hourly_total)
                    text += "OPTION 1: Hourly Rate\n"
                    text += "-" * 80 + "\n"
                    text += f"Base Rate: ${hourly_rate:.2f} per hour\n"
                    text += f"Estimated Hours: {estimated_hours} hours\n"
                    text += f"Subtotal: ${net_hourly:.2f}\n"
                    text += f"G.S.T. (5%): ${gst_hourly:.2f}\n"
                    text += f"Total: ${hourly_total:.2f}\n\n"
                    text += (
                        f"This option charges ${hourly_rate:.2f}"
                        f" for each hour of service.\n")
                    text += (
                        f"Minimum {estimated_hours} hours. "
                        f"Extra time billed at same hourly rate.\n")

                if options.get("package"):
                    extra_hours = max(0, estimated_hours - package_hours)
                    extra_cost = extra_hours * extra_time_rate
                    package_total = package_rate + extra_cost
                    gst_package, net_package = GSTCalculator.calculate_gst(
                        package_total)
                    text += "OPTION 2: Package Rate\n"
                    text += "-" * 80 + "\n"
                    text += (
                        f"Package: {package_hours} hours"
                        f" for ${package_rate:.2f}\n")
                    if extra_hours > 0:
                        text += (
                            f"Extra Time: {extra_hours} hours"
                            f" @ ${extra_time_rate:.2f}/hour"
                            f" = ${extra_cost:.2f}\n")
                    text += f"Subtotal: ${net_package:.2f}\n"
                    text += f"G.S.T. (5%): ${gst_package:.2f}\n"
                    text += f"Total: ${package_total:.2f}\n\n"
                    text += (
                        f"This package includes {package_hours}"
                        f" hours of service.\n")
                    text += (
                        f"Additional time beyond {package_hours} hours: "
                        f"${extra_time_rate:.2f}/hour.\n")

                if options.get("split"):
                    free_hours = split_run_before + split_run_after
                    standby_hours = max(0, estimated_hours - free_hours)
                    standby_cost = standby_hours * standby_rate
                    split_total = standby_cost
                    gst_split, net_split = GSTCalculator.calculate_gst(
                        split_total)
                    text += "OPTION 3: Split Run Rate (Driver Waiting)\n"
                    text += "-" * 80 + "\n"
                    text += (
                        f"Free Time: {split_run_before} hours before"
                        f" + {split_run_after} hours after event\n")
                    if standby_hours > 0:
                        text += (
                            f"Driver Standby/Waiting: {standby_hours} hours"
                            f" @ ${standby_rate:.2f}/hour"
                            f" = ${standby_cost:.2f}\n")
                    else:
                        text += (
                            "Service within free time"
                            " - no standby charge\n")
                    text += f"Subtotal: ${net_split:.2f}\n"
                    text += f"G.S.T. (5%): ${gst_split:.2f}\n"
                    text += f"Total: ${split_total:.2f}\n\n"
                    text += (
                        f"Ideal for events: {split_run_before}hr pickup"
                        f" + event + {split_run_after}hr return\n")
                    text += (
                        f"Driver waits during event. "
                        f"Standby time charged at ${standby_rate:.2f}/hr.\n")

                # Comparison summary
                text += "=" * 80 + "\n"
                text += "QUOTE SUMMARY\n"
                text += "=" * 80 + "\n"
                if options.get("hourly"):
                    text += f"Option 1 (Hourly): ${hourly_total:.2f}\n"
                if options.get("package"):
                    text += f"Option 2 (Package): ${package_total:.2f}\n"
                if options.get("split"):
                    text += f"Option 3 (Split Run): ${split_total:.2f}\n"
                text += "\n** Best Value Highlighted **\n\n"

            # Deposit and payment terms
            text += "DEPOSIT & PAYMENT TERMS\n"
            text += "-" * 80 + "\n"
            text += (
                "• A NON-REFUNDABLE deposit equal to"
                " two hour vehicle rate is required.\n")
            text += "• Balance due prior to charter pickup\n"
            text += (
                "• We recommend 15% gratuity"
                " (automatically applied unless declined).\n")
            text += (
                "• Cancellations must be made 24 hours"
                " prior to service time\n\n")

            # ====== LIABILITY CLAUSES (SAME AS CONFIRMATION) ======
            text += self._build_liability_terms_block("LIABILITY & TERMS")

            text += "=" * 80 + "\n"
            text += (
                "To book, please contact us"
                " with your preferred option.\n\n")
            text += (
                "Thank you for considering "
                "Arrow Limousine & Sedan Services Ltd.\n")
            text += "We look forward to serving you!\n\n"
            text += "Arrow Limousine & Sedan Services Ltd.\n"
            text += "Phone: 403-340-3466\n"
            text += "Email: info@arrowlimo.ca\n"
            text += "=" * 80 + "\n"

            self.show_print_dialog("Charter Quote - 3 Pricing Options", text)

        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to generate quote: {e}")

    def generate_airport_sign(self):
        """Generate printable airport pickup sign
        with Arrow Limousine branding"""
        try:
            customer_data = self.customer_widget.get_customer_data()
            client_name = customer_data.get('client_name', '').strip()

            if not client_name:
                QMessageBox.warning(
                    self, "Missing Name", "Please enter customer name first")
                return

            reserve_num = self.customer_widget.reserve_input.text() or "NEW"

            # Import and run generator
            try:
                from scripts.generate_airport_sign import generate_airport_sign
                pdf_path = generate_airport_sign(client_name, reserve_num)

                reply = QMessageBox.question(
                    self,
                    "Airport Sign Generated",
                    f"Airport sign created successfully!\n\nFile: "
                    f"{pdf_path}\n\nOpen now?",
                    ((QMessageBox.StandardButton.Yes
             | QMessageBox.StandardButton.No)))

                if reply == QMessageBox.StandardButton.Yes:
                    import os
                    os.startfile(pdf_path)

            except ImportError:
                QMessageBox.critical(
                    self, "Missing Dependency",
                    "Airport sign generator requires reportlab library.\n\n"
                    "Install with: pip install reportlab")
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Generation Error",
                    f"Failed to generate airport sign:\n\n{e}")

        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to prepare airport sign: {e}")

    def print_invoice(self):
        """
        Backward-compatible wrapper for the single-invoice print action.
        """
        self.print_single_invoice()

    def print_single_invoice(self):
        """Generate and open a single invoice filled from current charter data."""
        if not self.charter_id:
            QMessageBox.warning(self, "Warning", "Please save charter first")
            return

        try:
            reserve_number = str(self._fetch_reserve_number(self.charter_id) or "").strip()
            if not reserve_number:
                reserve_number = f"{int(self.charter_id):06d}"

            safe_reserve = "".join(
                ch if ch.isalnum() or ch in ("-", "_") else "_"
                for ch in reserve_number
            )
            if not safe_reserve:
                safe_reserve = f"{int(self.charter_id):06d}"

            invoices_dir = Path(__file__).resolve().parents[1] / "invoices"
            invoices_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(invoices_dir / f"{safe_reserve}_invoice.pdf")
            saved_file = self.export_modern_invoices_pdf(
                charter_ids=[self.charter_id],
                output_path=output_path,
                open_after_save=True,
            )
            if not saved_file:
                raise RuntimeError("Invoice export returned no file")

            QMessageBox.information(
                self,
                "Invoice Ready",
                "Single invoice saved to:\n"
                f"{saved_file}",
            )

        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to generate invoice: {e}")

    def open_beverage_lookup(self):
        """Open beverage selection dialog for adding beverages to charter"""
        # If editing existing charter, fetch existing beverages
        existing_beverages = None
        if self.charter_id:
            try:
                cur = self.db.get_cursor()
                cur.execute("""
                    SELECT id, item_name, quantity,
                    unit_price_charged, unit_our_cost,
                           deposit_per_unit,
                           line_amount_charged, line_cost, notes
                    FROM charter_beverages
                    WHERE charter_id = %s
                    ORDER BY created_at
                """, (self.charter_id,))
                existing_beverages = [dict(zip([
                    'id', 'item_name', 'quantity', 'unit_price_charged',
                    'unit_our_cost',
                    'deposit_per_unit', 'line_amount_charged',
                    'line_cost', 'notes'], row))
                    for row in cur.fetchall()]
                cur.close()
            except Exception as e:
                print(f"Error loading existing beverages: {e}")

        dialog = BeverageSelectionDialog(self.db, self, existing_beverages)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            totals = dialog.get_cart_totals()
            if totals["items"]:
                # Store beverage cart data
                self.beverage_cart_data = totals
                # Update invoice with beverage total
                self.update_beverage_in_invoice(totals)
                # Offer to save to database if charter is saved
                if self.charter_id:
                    self.save_beverages_to_charter(totals)

    def update_beverage_in_invoice(self, totals):
        """Update invoice section with beverage cart totals and display ordered
        beverages"""
        try:
            # Store total for later use
            self.beverage_cart_total = totals.get("charged_total", 0.0)

            # Update display
            if hasattr(self, 'beverage_total_display'):
                self.beverage_total_display.setText(
                    f"${self.beverage_cart_total:.2f}")

            # Update beverage list (no pricing, just item names with quantity)
            if hasattr(self, 'beverages_list_widget'):
                self.beverages_list_widget.clear()
                items = totals.get("items", [])
                if items:
                    for item in items:
                        name = item.get("name", "Unknown")
                        quantity = item.get("quantity", 1)
                        list_text = f"{quantity}x {name}"
                        list_item = QListWidgetItem(list_text)
                        self.beverages_list_widget.addItem(list_item)

            # Recalculate invoice totals
            self.recalculate_totals()

        except Exception as e:
            print(f"Error updating beverage in invoice: {e}")

    def save_beverages_to_charter(self, totals):
        """Save selected beverages as SNAPSHOTS to charter_beverages table"""
        if not self.charter_id or not totals["items"]:
            return

        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except Exception:
                try:
                    self.db.rollback()
                except Exception:
                    pass

            cur = self.db.get_cursor()

            # Save each beverage as a snapshot (prices locked, not linked to
            # master list)
            for item in totals["items"]:
                # Get beverage_item_id if available
                beverage_item_id = item.get("id")

                # Calculate unit prices (need to reverse from item totals)
                unit_price_charged = item["charged_price"]
                unit_our_cost = item["our_cost"]
                deposit_per_unit = item.get("deposit_amount", 0) or 0

                # Insert into charter_beverages (SNAPSHOT TABLE)
                cur.execute("""
                    INSERT INTO charter_beverages
                    (charter_id, beverage_item_id, item_name, quantity,
                     unit_price_charged, unit_our_cost,
                     deposit_per_unit, notes, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                """, (
                    self.charter_id,
                    beverage_item_id,
                    item["name"],
                    item["quantity"],
                    unit_price_charged,
                    unit_our_cost,
                    deposit_per_unit,
                    "Added via beverage selection dialog"))

                # Also add to charter_charges for backwards compatibility
                cur.execute(
                    """
                    INSERT INTO charter_charges (
                        charter_id,
                        charge_type,
                        charge_description,
                        quantity,
                        charge_amount)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        self.charter_id,
                        "beverage",
                        item["name"],
                        item["quantity"],
                        item["item_charged"],),)

            self.db.conn.commit()

            # Add charge lines to UI
            for item in totals["items"]:
                row = self.charges_table.rowCount()
                self.charges_table.insertRow(row)
                our_cost = format(item["our_cost"], ".2f")
                charged_price = format(item["charged_price"], ".2f")
                item_charged = format(item["item_charged"], ".2f")
                self.charges_table.setItem(
                    row, 0, QTableWidgetItem(item["name"]))
                self.charges_table.setItem(
                    row, 1, QTableWidgetItem(str(item["quantity"])))
                self.charges_table.setItem(
                    row, 2, QTableWidgetItem(f"${our_cost}"))
                self.charges_table.setItem(
                    row, 3, QTableWidgetItem(f"${charged_price}"))
                self.charges_table.setItem(
                    row, 4, QTableWidgetItem(f"${item_charged}"))

            self.recalculate_totals()
            QMessageBox.information(
                self,
                "Success",
                f"✅ Added {len(totals['items'])} beverage items to charter",)
        except Exception as e:
            self.db.conn.rollback()
            QMessageBox.critical(
                self, "Error", f"Failed to save beverages: {e}")

    def create_child_beverage_invoice(self):
        """Create separate invoice for beverages when checkbox is checked"""
        if (not self.separate_beverage_checkbox.isChecked()
        or not self.beverage_cart_data):
            return

        try:
            beverage_total = self.beverage_cart_total

            # Create payment info dialog for child invoice
            payment_dialog = QDialog(self)
            payment_dialog.setWindowTitle("Beverage Invoice - Payment Details")
            payment_dialog.setGeometry(100, 100, 500, 300)

            layout = QVBoxLayout()
            form = QFormLayout()

            # Payment name
            payment_name = QLineEdit()
            payment_name.setPlaceholderText(
                "Name for beverage payment tracking")
            form.addRow("Payment Name:", payment_name)

            # Payment method
            payment_method = QComboBox()
            payment_method.addItems(
                ["Card", "E-Transfer", "Cash", "Check", "Other"])
            form.addRow("Payment Method:", payment_method)

            # Amount (pre-filled)
            amount_field = QDoubleSpinBox()
            amount_field.setMaximum(99999.99)
            amount_field.setDecimals(2)
            amount_field.setValue(beverage_total)
            form.addRow("Amount:", amount_field)

            # GST calculation
            gst_label = QLabel(f"${beverage_total * 0.05 / 1.05:.2f}")
            form.addRow("GST (5%):", gst_label)

            layout.addLayout(form)

            # Buttons
            btn_layout = QHBoxLayout()
            ok_btn = QPushButton("Create Child Invoice")
            cancel_btn = QPushButton("Cancel")
            btn_layout.addWidget(ok_btn)
            btn_layout.addWidget(cancel_btn)
            layout.addLayout(btn_layout)

            payment_dialog.setLayout(layout)

            # Wire buttons
            ok_btn.clicked.connect(lambda: self.save_child_invoice(
                payment_name.text(),
                payment_method.currentText(),
                amount_field.value(),
                payment_dialog))
            cancel_btn.clicked.connect(payment_dialog.reject)

            payment_dialog.exec()

        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to create beverage invoice: {e}")

    def save_child_invoice(
            self, payment_name, payment_method, amount, dialog):
        """Save child beverage invoice to database"""
        try:
            if not self.charter_id:
                QMessageBox.warning(
                    self, "Warning", "Charter must be saved first")
                return

            # Rollback any failed transactions
            try:
                self.db.rollback()
            except Exception:
                pass

            cur = self.db.get_cursor()

            # Create child invoice record
            cur.execute(
                """
                INSERT INTO child_invoices
                (
                    charter_id, invoice_type, payment_name,
                    payment_method, amount, gst_amount, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                    """,
                (
                    self.charter_id,
                    "beverage",
                    payment_name,
                    payment_method,
                    amount,
                    amount * 0.05 / 1.05))

            self.db.commit()
            message = f"✅ Child beverage invoice created for ${amount:.2f}"
            QMessageBox.information(self, "Success", message)
            dialog.accept()

        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(
                self, "Error", f"Failed to save child invoice: {e}")

    def print_client_beverage_list(self):
        """Print client beverage list with
        itemized pricing, GST, and totals."""
        if not self.beverage_cart_data:
            self.show_print_dialog(
                "Client Beverage List",
                self._build_no_beverage_print_text("CLIENT BEVERAGE LIST"),
            )
            return

        try:
            text = self._build_client_beverage_print_text()
            self.show_print_dialog("Client Beverage List", text)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to print: {e}")

    def print_driver_manifest(self):
        """Print driver manifest with checkboxes
        and line totals for load verification."""
        if not self.beverage_cart_data:
            self.show_print_dialog(
                "Driver Beverage Manifest",
                self._build_no_beverage_print_text(
                    "DRIVER BEVERAGE MANIFEST", include_driver=True
                ),
            )
            return

        try:
            rows, totals = self._normalize_beverage_cart_items()
            if not rows:
                self.show_print_dialog(
                    "Driver Beverage Manifest",
                    self._build_no_beverage_print_text(
                        "DRIVER BEVERAGE MANIFEST", include_driver=True
                    ),
                )
                return

            text = "═" * 96 + "\n"
            text += "📋 DRIVER BEVERAGE MANIFEST (LOADING CHECKLIST)\n"
            text += "═" * 96 + "\n"
            text += f"Charter ID: {self.charter_id or 'Unsaved'}\n"
            rn = self.reserve_number.text() if hasattr(self, 'reserve_number') else ''
            cn = self.customer_name.text() if hasattr(self, 'customer_name') else ''
            text += f"Reserve Number: {rn}\n"
            text += f"Customer: {cn}\n"
            text += f"Printed: {datetime.now().strftime('%m/%d/%Y %H:%M')}\n\n"

            text += f"{'☐':<3} {'Item':<44} {'Qty':<6} {'Line Total':>12}\n"
            text += "─" * 96 + "\n"

            for row in rows:
                text += (
                    f"{'☐':<3} {row['name']:<44.44} {row['quantity']:<6} "
                    f"${row['line_total']:>10.2f}\n"
                )

            text += "─" * 96 + "\n"
            text += f"Guest total to collect: ${totals['guest_total']:.2f}\n"
            text += f"GST included:           ${totals['gst_total']:.2f}\n"
            if totals['deposit_total'] > 0:
                text += (
                    f"Deposit included:       "
                    f"${totals['deposit_total']:.2f}\n")

            text += (
                "\nDriver Name (Print): "
                "_________________________________\n")
            text += "Driver Signature: ____________________________________\n"
            text += "Date: ____________________  Time: ____________________\n"
            text += "═" * 96 + "\n"

            self.show_print_dialog("Driver Beverage Manifest", text)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to print: {e}")

    def _normalize_beverage_cart_items(self):
        """Normalize beverage cart rows from
        either in-memory cart or DB snapshot payloads."""
        rows = []
        items = self.beverage_cart_data.get(
            "items", []) if self.beverage_cart_data else []

        for item in items:
            name = item.get("name") or item.get("item_name") or "Unknown"
            quantity = int(item.get("quantity", 1) or 1)

            unit_price = item.get("charged_price")
            if unit_price is None:
                unit_price = item.get("unit_price_charged")
            unit_price = float(unit_price or 0.0)

            line_total = item.get("item_charged")
            if line_total is None:
                line_total = item.get("line_amount_charged")
            if line_total is None:
                line_total = unit_price * quantity
            line_total = float(line_total or 0.0)

            line_gst = item.get("item_gst")
            if line_gst is None:
                line_gst = line_total * 0.05 / 1.05 if line_total else 0.0
            line_gst = float(line_gst or 0.0)

            rows.append(
                {
                    "name": str(name),
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "line_total": line_total,
                    "line_gst": line_gst,
                    "notes": item.get("notes", ""),
                }
            )

        charged_total = self.beverage_cart_data.get("charged_total")
        if charged_total is None:
            charged_total = self.beverage_cart_data.get("total_charged")
        if charged_total is None:
            charged_total = sum(row["line_total"] for row in rows)

        gst_total = self.beverage_cart_data.get("gst_total")
        if gst_total is None:
            gst_total = self.beverage_cart_data.get("gst_amount")
        if gst_total is None:
            gst_total = sum(row["line_gst"] for row in rows)

        deposit_total = self.beverage_cart_data.get("deposit_total")
        if deposit_total is None:
            deposit_total = self.beverage_cart_data.get("total_deposit")
        deposit_total = float(deposit_total or 0.0)

        guest_total = self.beverage_cart_data.get("guest_total")
        if guest_total is None:
            guest_total = float(charged_total or 0.0) + deposit_total

        totals = {
            "charged_total": float(charged_total or 0.0),
            "gst_total": float(gst_total or 0.0),
            "deposit_total": deposit_total,
            "guest_total": float(guest_total or 0.0),
        }

        return rows, totals

    def _build_client_beverage_print_text(self) -> str:
        """Build itemized client beverage print text with GST and totals."""
        rows, totals = self._normalize_beverage_cart_items()
        if not rows:
            return self._build_no_beverage_print_text("CLIENT BEVERAGE LIST")

        net_subtotal = totals["charged_total"] - totals["gst_total"]

        text = "═" * 96 + "\n"
        text += "🛒 CLIENT BEVERAGE LIST\n"
        text += "═" * 96 + "\n"
        text += f"Charter ID: {self.charter_id or 'Unsaved'}\n"
        _rn2 = self.reserve_number.text() if hasattr(self, 'reserve_number') else ''
        _cn2 = self.customer_name.text() if hasattr(self, 'customer_name') else ''
        text += f"Reserve Number: {_rn2}\n"
        text += f"Customer: {_cn2}\n"
        text += f"Printed: {datetime.now().strftime('%m/%d/%Y %H:%M')}\n\n"

        text += (
            f"{'Item':<38} {'Qty':>5} {'Unit':>10} "
            f"{'GST':>10} {'Line Total':>12}\n"
        )
        text += "─" * 96 + "\n"

        for row in rows:
            text += (
                f"{row['name']:<38.38} {row['quantity']:>5} "
                f"${row['unit_price']:>9.2f}"
                f" ${row['line_gst']:>9.2f}"
                f" ${row['line_total']:>11.2f}\n"
            )

        text += "─" * 96 + "\n"
        text += f"Subtotal (before GST): ${net_subtotal:>11.2f}\n"
        text += f"GST included (5%):    ${totals['gst_total']:>11.2f}\n"
        if totals["deposit_total"] > 0:
            text += (
                f"Deposit/Recycle:      "
                f"${totals['deposit_total']:>11.2f}\n")
        text += "═" * 96 + "\n"
        text += f"TOTAL TO COLLECT:     ${totals['guest_total']:>11.2f}\n"
        text += "═" * 96 + "\n"

        return text

    def _build_no_beverage_print_text(
            self, heading: str, include_driver: bool = False) -> str:
        """Build a printable placeholder when no beverage order exists."""
        text = "═" * 70 + "\n"
        text += f"{heading}\n"
        text += "═" * 70 + "\n\n"
        text += f"Charter ID: {self.charter_id or 'Unsaved'}\n"
        reserve_num = self.reserve_number.text() if hasattr(
            self, 'reserve_number') else ''
        customer_name = self.customer_name.text() if hasattr(
            self, 'customer_name') else ''
        text += f"Reserve Number: {reserve_num}\n"
        text += f"Customer: {customer_name}\n"
        if include_driver:
            driver_name = self.driver_combo.currentText() if hasattr(
                self, 'driver_combo') else ''
            text += f"Driver: {driver_name}\n"
        text += f"Date: {datetime.now().strftime('%m/%d/%Y %H:%M')}\n\n"
        text += "No beverage order for this charter.\n"
        text += "Beverages: None\n"
        text += "═" * 70 + "\n"
        return text

    def generate_client_beverage_html(self) -> str:
        """Generate HTML for client beverage list (GST per line)"""
        html = (
            "<html><body>"
            "<table border='1' cellpadding='10' style='width:100%;'>")
        html += "<h2>Beverage Order - Client Collection List</h2>"
        html += (
            "<tr><th>Item</th><th>Qty</th>"
            "<th>Price</th><th>GST</th><th>Total</th></tr>")

        total = 0
        total_gst = 0

        for item in self.beverage_cart_data.get("items", []):
            qty = item.get("quantity", 1)
            price_per_unit = item.get("charged_price", 0)
            item_total = qty * price_per_unit
            gst_per_item = item_total * 0.05 / 1.05

            html += "<tr>"
            html += f"<td>{item.get('name', '')}</td>"
            html += f"<td>{qty}</td>"
            html += f"<td>${price_per_unit:.2f}</td>"
            html += f"<td>${gst_per_item:.2f}</td>"
            html += f"<td>${item_total:.2f}</td>"
            html += "</tr>"

            total += item_total
            total_gst += gst_per_item

        # Deposit/recycle fees row
        deposit = self.beverage_cart_data.get("deposit_total", 0)
        if deposit > 0:
            html += (
                f"<tr><td colspan='3'><b>Deposit/Recycle Fees</b></td>"
                f"<td>-</td><td>${deposit:.2f}</td></tr>")
            total += deposit

        html += (
            f"<tr><td colspan='3'><b>Subtotal</b></td>"
            f"<td><b>${total_gst:.2f}</b></td>"
            f"<td><b>${total:.2f}</b></td></tr>")
        html += "</table></body></html>"

        return html

    def generate_driver_manifest_html(self) -> str:
        """Generate HTML for driver manifest with checkboxes"""
        html = (
            "<html><body>"
            "<table border='1' cellpadding='10' style='width:100%;'>")
        html += "<h2>Driver Beverage Manifest - Loading Checklist</h2>"
        html += "<tr><th>☑️</th><th>Item</th><th>Qty</th><th>Notes</th></tr>"

        for item in self.beverage_cart_data.get("items", []):
            html += "<tr>"
            html += (
                "<td><input type='checkbox'"
                " style='width:20px; height:20px;'></td>")
            html += f"<td>{item.get('name', '')}</td>"
            html += f"<td>{item.get('quantity', 1)}</td>"
            html += f"<td>{item.get('notes', '')}</td>"
            html += "</tr>"

        html += "</table>"
        html += (
            "<p><i>Driver: Check off each item"
            " as it is loaded into the vehicle.</i></p>")
        html += "</body></html>"

        return html

    def print_beverage_dispatch_order(self):
        """
        Print dispatch copy with OUR COSTS (internal, for buying)
        Includes itemization and checkboxes for vehicle load verification
        Uses charter_beverages SNAPSHOT (locked prices)
        """
        if not self.charter_id:
            QMessageBox.warning(self, "Warning", "Please save charter first")
            return

        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except Exception:
                try:
                    self.db.rollback()
                except Exception:
                    pass

            cur = self.db.get_cursor()
            cur.execute("""
                SELECT item_name, quantity, unit_our_cost, line_cost
                FROM charter_beverages
                WHERE charter_id = %s
                ORDER BY item_name
            """, (self.charter_id,))

            items = cur.fetchall()
            if not items:
                self.show_print_dialog(
                    "Beverage Dispatch Order (Internal)",
                    self._build_no_beverage_print_text(
                        "BEVERAGE DISPATCH ORDER (INTERNAL)",
                        include_driver=True,
                    ),
                )
                return

            # Build dispatch order text
            text = "═" * 70 + "\n"
            text += "🍷 BEVERAGE DISPATCH ORDER (INTERNAL - OUR COSTS)\n"
            text += "═" * 70 + "\n\n"
            text += f"Charter ID: {self.charter_id}\n"
            text += f"Reserve Number: {self.reserve_number.text()}\n"
            text += f"Customer: {self.customer_name.text()}\n"
            text += f"Date: {datetime.now().strftime('%m/%d/%Y %H:%M')}\n"
            text += f"Driver: {self.driver_combo.currentText()}\n"
            text += f"Vehicle: {self.vehicle_combo.currentText()}\n\n"

            text += "ITEMS TO PURCHASE (Our Wholesale Costs - SNAPSHOT)\n"
            text += "─" * 70 + "\n"
            text += (
                f"{' ☐':<2} {' Item':<40}"
                f" {' Qty':<6} {' Cost Each':<12}"
                f" {' Total':<10}\n")
            text += "─" * 70 + "\n"

            total_cost = 0
            for item_name, qty, unit_cost, line_cost in items:
                total_cost += line_cost
                text += (
                    f"☐  {item_name:<37} {qty:<6}"
                    f" ${unit_cost:<11.2f} ${line_cost:<9.2f}\n")

            text += "─" * 70 + "\n"
            text += f"TOTAL COST TO PURCHASE: ${total_cost:.2f}\n"
            text += "═" * 70 + "\n"
            text += "\nVERIFICATION AT VEHICLE LOAD:\n"
            text += "─" * 70 + "\n"
            for i, (item_name, qty, _, _) in enumerate(items, 1):
                text += f"☐ {i}. {item_name:<50} Qty: {qty} ✓ Loaded\n"

            text += "\n" + "─" * 70 + "\n"
            text += (
                "Driver Signature: ________________"
                "  Date: ________  Time: ________\n")
            text += "═" * 70 + "\n"
            text += (
                "\nNote: Prices locked from charter creation."
                " Edits to quantities/prices\n")
            text += (
                "are reflected in this cart but do NOT"
                " affect master beverage_products.\n")

            # Display in dialog
            self.show_print_dialog("Beverage Dispatch Order (Internal)", text)

        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to generate dispatch order: {e}")

    def print_beverage_guest_invoice(self):
        """
        Print guest invoice - ONLY guest prices, NO internal costs
        Shows itemized list and total to collect
        Uses charter_beverages SNAPSHOT (locked prices)
        """
        if not self.charter_id:
            QMessageBox.warning(self, "Warning", "Please save charter first")
            return

        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except Exception:
                try:
                    self.db.rollback()
                except Exception:
                    pass

            cur = self.db.get_cursor()
            cur.execute("""
                SELECT item_name, quantity,
                unit_price_charged,
                line_amount_charged, deposit_per_unit
                FROM charter_beverages
                WHERE charter_id = %s
                ORDER BY item_name
            """, (self.charter_id,))

            items = cur.fetchall()
            if not items:
                self.show_print_dialog(
                    "Beverage Guest Invoice",
                    self._build_no_beverage_print_text(
                        "BEVERAGE INVOICE (GUEST COPY)"
                    ),
                )
                return

            # Build guest invoice
            text = "═" * 70 + "\n"
            text += "🍷 BEVERAGE INVOICE (GUEST COPY)\n"
            text += "═" * 70 + "\n\n"
            text += f"Charter ID: {self.charter_id}\n"
            text += f"Reserve Number: {self.reserve_number.text()}\n"
            text += f"Customer: {self.customer_name.text()}\n"
            text += f"Date: {datetime.now().strftime('%m/%d/%Y %H:%M')}\n\n"

            text += "BEVERAGES PROVIDED (SNAPSHOT PRICES)\n"
            text += "─" * 70 + "\n"
            text += (
                f"{' Item':<45} {' Qty':<6}"
                f" {' Price Each':<10} {' Total':<10}\n")
            text += "─" * 70 + "\n"

            subtotal = 0
            gst_total = 0
            for item_name, qty, unit_price, line_amount, deposit in items:
                subtotal += line_amount
                gst_portion = line_amount * 0.05 / 1.05
                gst_total += gst_portion

                text += (
                    f"{item_name:<45} {qty:<6}"
                    f" ${unit_price:<9.2f} ${line_amount:<9.2f}\n")

            text += "─" * 70 + "\n"
            text += f"Subtotal (before GST):            ${subtotal - gst_total:<35.2f}\n"
            text += f"GST (5% included):                ${gst_total:<35.2f}\n"
            text += "═" * 70 + "\n"
            text += f"TOTAL DUE FROM GUEST:             ${subtotal:<35.2f}\n"
            text += "═" * 70 + "\n"
            text += "\nPrices locked at time of charter creation.\n"
            text += "For historical accuracy and dispute resolution.\n"

            # Display
            self.show_print_dialog("Beverage Guest Invoice", text)

        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to generate guest invoice: {e}")

    def print_beverage_driver_sheet(self):
        """
        Print driver verification sheet
        Includes checkboxes for each item, signature line
        Uses charter_beverages SNAPSHOT
        """
        if not self.charter_id:
            QMessageBox.warning(self, "Warning", "Please save charter first")
            return

        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except Exception:
                try:
                    self.db.rollback()
                except Exception:
                    pass

            cur = self.db.get_cursor()
            cur.execute("""
                SELECT item_name, quantity
                FROM charter_beverages
                WHERE charter_id = %s
                ORDER BY item_name
            """, (self.charter_id,))

            items = cur.fetchall()
            if not items:
                self.show_print_dialog(
                    "Driver Beverage Verification Sheet",
                    self._build_no_beverage_print_text(
                        "DRIVER BEVERAGE VERIFICATION SHEET",
                        include_driver=True,
                    ),
                )
                return

            # Build driver sheet
            text = "═" * 70 + "\n"
            text += "🍷 DRIVER BEVERAGE VERIFICATION SHEET\n"
            text += "═" * 70 + "\n\n"
            text += f"Charter ID: {self.charter_id}\n"
            text += f"Reserve Number: {self.reserve_number.text()}\n"
            text += f"Customer: {self.customer_name.text()}\n"
            text += f"Driver: {self.driver_combo.currentText()}\n"
            text += f"Vehicle: {self.vehicle_combo.currentText()}\n"
            text += f"Date: {datetime.now().strftime('%m/%d/%Y')}\n\n"

            text += "BEVERAGE LOAD VERIFICATION (SNAPSHOT)\n"
            text += "Check off each item as it is loaded into the vehicle\n"
            text += "─" * 70 + "\n\n"

            for i, (item_name, qty) in enumerate(items, 1):
                text += f"☐ {i}. {item_name:<50}\n"
                text += f"   Quantity: {qty} units\n"
                text += (
                    "   ✓ Verified at load time: ________"
                    "  Initials: ____\n\n")

            text += "═" * 70 + "\n"
            text += "DRIVER ACKNOWLEDGMENT\n"
            text += "─" * 70 + "\n"
            text += (
                "I confirm that all beverage items"
                " listed above have been loaded\n")
            text += "into the vehicle and are ready for delivery.\n\n"
            text += "Driver Name (Print): _________________________________\n"
            text += "Driver Signature: ____________________________________\n"
            text += (
                "Date: ____________________"
                "  Time: ____________________\n\n")
            text += "Temperature Check (if perishable): ____°C\n"
            text += "═" * 70 + "\n"

            # Display
            self.show_print_dialog("Driver Beverage Verification Sheet", text)

        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to generate driver sheet: {e}")

    def show_print_dialog(self, title, text):
        """Display print preview in dialog with copy/print/export options"""
        dialog = QDialog(self)
        dialog.setWindowTitle(f"🖨️ {title}")
        dialog.setGeometry(50, 50, 900, 650)
        layout = QVBoxLayout()

        # Preview text
        text_edit = QTextEdit()
        text_edit.setText(text)
        text_edit.setFont(QFont("Courier New", 9))
        text_edit.setReadOnly(True)
        layout.addWidget(text_edit)

        # Buttons
        button_layout = QHBoxLayout()

        copy_btn = QPushButton("📋 Copy to Clipboard")
        copy_btn.clicked.connect(lambda: self.copy_to_clipboard(text))
        button_layout.addWidget(copy_btn)

        print_btn = QPushButton("🖨️ Print")
        print_btn.clicked.connect(lambda: self.print_text(title, text))
        button_layout.addWidget(print_btn)

        # Export buttons
        pdf_btn = QPushButton("📄 Save as PDF")
        pdf_btn.clicked.connect(lambda: self.export_dialog_to_pdf(title, text))
        button_layout.addWidget(pdf_btn)

        if title == "Charter Invoice":
            email_btn = QPushButton("✉️ Email Invoice")
            email_btn.setToolTip("Create email draft with the invoice PDF attached")
            email_btn.clicked.connect(self.email_current_invoice)
            button_layout.addWidget(email_btn)

        csv_btn = QPushButton("📊 Export CSV")
        csv_btn.clicked.connect(lambda: self.export_dialog_to_csv(title, text))
        button_layout.addWidget(csv_btn)

        word_btn = QPushButton("📝 Export Word")
        word_btn.clicked.connect(
            lambda: self.export_dialog_to_word(
                title, text))
        button_layout.addWidget(word_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)
        dialog.setLayout(layout)
        dialog.exec()

    def copy_to_clipboard(self, text):
        """Copy text to clipboard"""
        from PyQt6.QtGui import QGuiApplication
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(text)
        QMessageBox.information(self, "Copied", "✅ Text copied to clipboard")

    def print_text(self, title, text):
        """Print text to printer"""
        from PyQt6.QtPrintSupport import QPrintDialog, QPrinter

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog = QPrintDialog(printer, self)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                from PyQt6.QtGui import QTextDocument
                doc = QTextDocument()
                doc.setPlainText(text)
                doc.print(printer)
                QMessageBox.information(self, "Success", "✅ Sent to printer")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Print failed: {e}")

    def export_dialog_to_pdf(self, title, text):
        """Export dialog text to PDF"""
        try:
            from datetime import datetime

            from PyQt6.QtPrintSupport import QPrinter

            filename, _ = QFileDialog.getSaveFileName(
                self,
                f"Save {title} as PDF",
                f"{title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                "PDF Files (*.pdf);;All Files (*)")

            if not filename:
                return

            if title == "Charter Invoice" and self.charter_id:
                saved_file = self.export_modern_invoices_pdf(
                    charter_ids=[self.charter_id],
                    output_path=filename,
                    open_after_save=False,
                )
                if saved_file:
                    QMessageBox.information(
                        self, "Success", f"Saved modern invoice PDF:\n{saved_file}"
                    )
                return

            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(filename)
            printer.setPageSize(QPrinter.PageSize.A4)

            from PyQt6.QtGui import QTextDocument
            doc = QTextDocument()
            doc.setPlainText(text)
            doc.print(printer)

            QMessageBox.information(
                self, "Success", f"✅ Saved to PDF:\n{filename}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"PDF export failed: {e}")

    def _fetch_invoice_packet(self, charter_id):
        """Fetch normalized invoice data for a charter_id."""
        cur = self.db.get_cursor()
        try:
            cur.execute(
                """
                SELECT
                    c.charter_id,
                    c.reserve_number,
                    c.charter_date,
                    c.pickup_time,
                    COALESCE(cl.company_name, cl.client_name, cl.name, 'Unknown') AS customer,
                    COALESCE(cl.company_name, '') AS company_name,
                    COALESCE(cl.first_name, '') AS first_name,
                    COALESCE(cl.last_name, '') AS last_name,
                    COALESCE(cl.primary_phone, cl.phone, '') AS phone,
                    COALESCE(cl.email, '') AS email,
                    COALESCE(cl.address_line1, cl.address, '') AS address_line1,
                    COALESCE(cl.city, '') AS city,
                    COALESCE(cl.province, '') AS province,
                    COALESCE(v.vehicle_number, c.vehicle, '') AS vehicle_number,
                    COALESCE(v.vehicle_type, c.charter_type, '') AS vehicle_type,
                    COALESCE(NULLIF(c.total_amount_due, 0), c.grand_total, 0) AS total_charges,
                    GREATEST(COALESCE(c.amount_paid, 0), COALESCE(c.paid_amount, 0)) AS paid_amount,
                    COALESCE(c.passenger_count, 0) AS passenger_count
                FROM charters c
                LEFT JOIN clients cl ON c.client_id = cl.client_id
                LEFT JOIN vehicles v ON v.vehicle_id = c.vehicle_id
                WHERE c.charter_id = %s
                """,
                (charter_id,),
            )
            row = cur.fetchone()
            if not row:
                return None

            (
                cid,
                reserve,
                charter_date,
                pickup_time,
                customer,
                company_name,
                first_name,
                last_name,
                phone,
                email,
                address_line1,
                city,
                province,
                vehicle_number,
                vehicle_type,
                total_charges,
                paid_amount,
                passenger_count,
            ) = row

            total_charges = float(total_charges or 0)
            paid_amount = float(paid_amount or 0)

            cur.execute(
                """
                SELECT COALESCE(SUM(line_amount_charged), 0)
                FROM charter_beverages
                WHERE charter_id = %s
                """,
                (charter_id,),
            )
            beverage_total = float((cur.fetchone() or [0])[0] or 0)

            cur.execute(
                """
                SELECT
                    COALESCE(description, ''),
                    COALESCE(amount, 0),
                    COALESCE(rate, 0),
                    COALESCE(charge_type, ''),
                    COALESCE(sequence, 0)
                FROM charter_charges
                WHERE charter_id = %s
                ORDER BY sequence, charge_id
                """,
                (charter_id,),
            )
            charge_rows = cur.fetchall() or []
            gratuity_sum = 0.0
            service_sum = 0.0
            charge_items = []
            for description, amount, rate, charge_type, sequence in charge_rows:
                amount_val = float(amount or 0)
                rate_val = float(rate or 0)
                charge_type_text = (charge_type or '').strip()
                desc_text = (description or '').strip()
                charge_items.append({
                    'description': desc_text,
                    'amount': amount_val,
                    'rate': rate_val,
                    'charge_type': charge_type_text,
                    'sequence': int(sequence or 0),
                })
                if 'gratuit' in desc_text.lower() or 'gratuit' in charge_type_text.lower():
                    gratuity_sum += amount_val
                else:
                    service_sum += amount_val

            # Keep totals consistent even when charges table is sparse.
            if service_sum <= 0 and total_charges > 0:
                service_sum = max(total_charges - beverage_total - gratuity_sum, 0)

            cur.execute(
                """
                SELECT COALESCE(amount, 0),
                       COALESCE(payment_method, ''),
                       payment_date,
                       '',
                       COALESCE(payment_key, '')
                FROM charter_payments
                WHERE charter_id = %s
                ORDER BY payment_date NULLS LAST, id
                """,
                (charter_id,),
            )
            payment_rows = cur.fetchall() or []
            payments_detail = []
            payments_total_detail = 0.0
            for amount, method, payment_date, notes, reference in payment_rows:
                amount_val = float(amount or 0)
                payments_total_detail += amount_val
                payments_detail.append({
                    'amount': amount_val,
                    'method': (method or '').strip(),
                    'payment_date': payment_date,
                    'notes': (notes or '').strip(),
                    'reference': (reference or '').strip(),
                })

            if payments_total_detail > 0:
                paid_amount = payments_total_detail

            gst_amount = total_charges * 0.05 / 1.05 if total_charges > 0 else 0
            subtotal = total_charges - gst_amount

            service_date_text = (
                charter_date.strftime("%Y-%m-%d")
                if hasattr(charter_date, "strftime")
                else str(charter_date or "")
            )
            pickup_time_text = (
                pickup_time.strftime("%H:%M")
                if hasattr(pickup_time, "strftime")
                else str(pickup_time or "")
            )

            return {
                "charter_id": cid,
                "reserve_number": reserve,
                "invoice_number": f"{cid:06d}",
                "invoice_date": datetime.now().strftime("%m/%d/%Y"),
                "service_date": service_date_text,
                "pickup_time": pickup_time_text,
                "customer": customer or "",
                "company_name": company_name or "",
                "first_name": first_name or "",
                "last_name": last_name or "",
                "phone": phone or "",
                "email": email or "",
                "address_line1": address_line1 or "",
                "city": city or "",
                "province": province or "",
                "vehicle_number": vehicle_number or "",
                "vehicle_type": vehicle_type or "",
                "passengers": int(passenger_count or 0),
                "service_fee": service_sum,
                "beverage_fee": beverage_total,
                "gratuity_fee": gratuity_sum,
                "gst_amount": gst_amount,
                "subtotal": subtotal,
                "total_charges": total_charges,
                "paid_amount": paid_amount,
                "amount_due": total_charges - paid_amount,
                "charge_items": charge_items,
                "payment_items": payments_detail,
            }
        finally:
            cur.close()

    def _draw_invoice_overlay(self, c, invoice_packet, width, height):
        """Draw one invoice page onto a reportlab canvas."""
        from reportlab.lib.colors import Color
        from reportlab.lib.units import inch

        c.setFillColor(Color(1, 1, 1, alpha=1.0))
        c.rect(0, 0, width, height, fill=1, stroke=0)
        c.setFillColor(Color(0.0, 0.0, 0.0, alpha=1.0))

        client_display = invoice_packet.get("customer") or ""
        company_name = invoice_packet.get("company_name") or ""
        first_name = invoice_packet.get("first_name") or ""
        last_name = invoice_packet.get("last_name") or ""
        address_line1 = invoice_packet.get("address_line1") or ""
        city = invoice_packet.get("city") or ""
        province = invoice_packet.get("province") or ""
        vehicle_number = invoice_packet.get("vehicle_number") or ""
        vehicle_type = invoice_packet.get("vehicle_type") or ""
        addr_text = "38014 C&E Trl, Red Deer County, AB, T4E 1R9"
        gst_text = "G.S.T.#: 861 556 827"

        c.setFont("Helvetica-Bold", 15)
        c.drawCentredString(width / 2, height - 0.68 * inch, "Arrow Limousine & Sedan Services Ltd.")
        c.setFont("Helvetica", 8.5)
        c.drawCentredString(width / 2, height - 0.88 * inch, addr_text)
        c.drawCentredString(width / 2, height - 1.02 * inch, gst_text)

        c.setFont("Helvetica-Bold", 11)
        c.drawString(5.95 * inch, 7.20 * inch, f"Invoice #: {invoice_packet['invoice_number']}")
        c.setFont("Helvetica", 10)
        c.drawString(5.95 * inch, 6.96 * inch, f"Date: {invoice_packet['invoice_date']}")

        # Compact charter summary line using the run charter values.
        c.setFont("Helvetica-Bold", 10)
        summary_line = (
            f"{invoice_packet['reserve_number'] or 'N/A'}, "
            f"{invoice_packet['service_date']}, "
            f"{vehicle_number or 'Vehicle'}, "
            f"{vehicle_type or 'Vehicle Type'}, "
            f"{invoice_packet['passengers']} Pax"
        )
        c.drawString(0.85 * inch, 6.82 * inch, summary_line[:88])
        c.setFont("Helvetica", 9)
        c.drawString(0.85 * inch, 6.62 * inch, f"Client: {client_display[:42]}")
        if company_name:
            c.drawString(0.85 * inch, 6.44 * inch, f"Company: {company_name[:42]}")
        elif first_name or last_name:
            c.drawString(0.85 * inch, 6.44 * inch, f"Name: {(first_name + ' ' + last_name).strip()[:42]}")

        c.drawString(0.85 * inch, 6.26 * inch, f"Pickup Time: {invoice_packet['pickup_time']}")
        if address_line1:
            c.drawString(0.85 * inch, 6.08 * inch, f"Address: {address_line1[:42]}")
        if city or province:
            c.drawString(0.85 * inch, 5.90 * inch, f"City/Prov: {(city + ', ' + province).strip(', ')[:42]}")

        c.drawString(4.12 * inch, 6.62 * inch, f"Phone: {invoice_packet['phone']}")
        c.drawString(4.12 * inch, 6.44 * inch, f"Email: {invoice_packet['email'][:30]}")
        c.drawString(4.12 * inch, 6.26 * inch, f"Vehicle: {vehicle_number or 'N/A'}")
        c.drawString(4.12 * inch, 6.08 * inch, f"Type: {vehicle_type or 'N/A'}")
        c.drawString(4.12 * inch, 5.90 * inch, f"Passengers: {invoice_packet['passengers']}")

        c.setFont("Helvetica-Bold", 9)
        c.drawString(0.85 * inch, 5.48 * inch, "CHARGES FROM RUN CHARTER")
        c.setFont("Helvetica", 8.5)
        charge_y = 5.26 * inch
        c.drawString(0.85 * inch, charge_y, "Description")
        c.drawString(4.70 * inch, charge_y, "Type")
        c.drawRightString(7.75 * inch, charge_y, "Amount")
        c.line(0.85 * inch, 5.20 * inch, 7.75 * inch, 5.20 * inch)

        charge_rows = invoice_packet.get("charge_items") or []
        charge_y -= 0.22 * inch
        if charge_rows:
            for charge in charge_rows[:5]:
                desc = (charge.get("description") or "")[:44]
                ctype = (charge.get("charge_type") or "")[:12]
                amt = float(charge.get("amount") or 0)
                c.drawString(0.85 * inch, charge_y, desc)
                c.drawString(4.70 * inch, charge_y, ctype)
                c.drawRightString(7.75 * inch, charge_y, f"${amt:,.2f}")
                charge_y -= 0.18 * inch
        else:
            c.drawString(0.85 * inch, charge_y, "No charge detail rows found on run charter")
            charge_y -= 0.18 * inch

        c.setFont("Helvetica-Bold", 9)
        c.drawString(0.85 * inch, charge_y - 0.04 * inch, "PAYMENTS FROM RUN CHARTER")
        pay_y = charge_y - 0.28 * inch
        c.setFont("Helvetica", 8.5)
        c.drawString(0.85 * inch, pay_y, "Date")
        c.drawString(1.65 * inch, pay_y, "Method")
        c.drawRightString(7.75 * inch, pay_y, "Amount")
        c.line(0.85 * inch, pay_y - 0.05 * inch, 7.75 * inch, pay_y - 0.05 * inch)

        payment_rows = invoice_packet.get("payment_items") or []
        pay_y -= 0.22 * inch
        if payment_rows:
            for payment in payment_rows[:5]:
                pdate = payment.get("payment_date")
                if hasattr(pdate, "strftime"):
                    pdate_text = pdate.strftime("%Y-%m-%d")
                else:
                    pdate_text = str(pdate or "")
                method = (payment.get("method") or "")[:12]
                amt = float(payment.get("amount") or 0)
                c.drawString(0.85 * inch, pay_y, pdate_text)
                c.drawString(1.65 * inch, pay_y, method)
                c.drawRightString(7.75 * inch, pay_y, f"${amt:,.2f}")
                pay_y -= 0.18 * inch
        else:
            c.drawString(0.85 * inch, pay_y, "No payment rows found on run charter")
            pay_y -= 0.18 * inch

        y = max(pay_y - 0.12 * inch, 2.95 * inch)
        c.setFont("Helvetica", 9)
        c.drawString(0.85 * inch, y, "Subtotal (before GST):")
        c.drawRightString(7.75 * inch, y, f"${invoice_packet['subtotal']:,.2f}")

        y -= 0.22 * inch
        c.drawString(0.85 * inch, y, "GST (5% included)")
        c.drawRightString(7.75 * inch, y, f"${invoice_packet['gst_amount']:,.2f}")

        y -= 0.22 * inch
        c.setFont("Helvetica-Bold", 10)
        c.drawString(0.85 * inch, y, "Total Charges")
        c.drawRightString(7.75 * inch, y, f"${invoice_packet['total_charges']:,.2f}")

        y -= 0.22 * inch
        c.setFont("Helvetica", 9)
        c.drawString(0.85 * inch, y, "Total Payment")
        c.drawRightString(7.75 * inch, y, f"${invoice_packet['paid_amount']:,.2f}")

        y -= 0.22 * inch
        c.setFont("Helvetica-Bold", 10)
        c.drawString(0.85 * inch, y, "Amount Due")
        c.drawRightString(7.75 * inch, y, f"${invoice_packet['amount_due']:,.2f}")

        c.setFont("Helvetica-Oblique", 8)
        c.drawString(
            0.85 * inch,
            2.18 * inch,
            f"Trip Invoice {invoice_packet['invoice_number']} - Charter {invoice_packet['charter_id']} - Generated {invoice_packet['invoice_date']}",
        )

        c.setFont("Helvetica", 7.5)
        c.drawCentredString(
            4.25 * inch,
            0.60 * inch,
            f"{addr_text}     {gst_text}",
        )

    def _draw_grouped_invoice_overlay(self, c, invoice_packet, width, height):
        """Draw a compact grouped charter invoice page without routing."""
        from reportlab.lib.colors import Color
        from reportlab.lib.units import inch

        c.setFillColor(Color(1, 1, 1, alpha=1.0))
        c.rect(0, 0, width, height, fill=1, stroke=0)
        c.setFillColor(Color(0.0, 0.0, 0.0, alpha=1.0))

        customer = invoice_packet.get("customer") or ""
        company_name = invoice_packet.get("company_name") or ""
        first_name = invoice_packet.get("first_name") or ""
        last_name = invoice_packet.get("last_name") or ""
        address_line1 = invoice_packet.get("address_line1") or ""
        city = invoice_packet.get("city") or ""
        province = invoice_packet.get("province") or ""
        vehicle_number = invoice_packet.get("vehicle_number") or ""
        vehicle_type = invoice_packet.get("vehicle_type") or ""
        passengers = int(invoice_packet.get("passengers") or 0)

        c.setFont("Helvetica-Bold", 15)
        c.drawCentredString(width / 2, height - 0.68 * inch, "Arrow Limousine & Sedan Services Ltd.")
        c.setFont("Helvetica", 8.5)
        c.drawCentredString(width / 2, height - 0.88 * inch, "38014 C&E Trl, Red Deer County, AB, T4E 1R9")
        c.drawCentredString(width / 2, height - 1.02 * inch, "G.S.T.#: 861 556 827")

        c.setFont("Helvetica-Bold", 11)
        c.drawString(5.95 * inch, 7.20 * inch, f"Invoice #: {invoice_packet['invoice_number']}")
        c.setFont("Helvetica", 10)
        c.drawString(5.95 * inch, 6.96 * inch, f"Date: {invoice_packet['invoice_date']}")

        box_left = 0.75 * inch
        box_right = width - 0.75 * inch
        box_top = 5.82 * inch
        box_bottom = 2.02 * inch
        c.setLineWidth(1)
        c.rect(box_left, box_bottom, box_right - box_left, box_top - box_bottom, stroke=1, fill=0)

        c.setFont("Helvetica-Bold", 10)
        c.drawString(box_left + 0.12 * inch, box_top - 0.18 * inch, "GROUPED CHARTER SUMMARY")

        left_x = box_left + 0.12 * inch
        right_x = width / 2 + 0.12 * inch
        y = box_top - 0.42 * inch

        c.setFont("Helvetica", 8.5)
        c.drawString(left_x, y, f"Client: {customer[:42]}")
        y -= 0.16 * inch
        if company_name:
            c.drawString(left_x, y, f"Company: {company_name[:42]}")
            y -= 0.16 * inch
        elif first_name or last_name:
            c.drawString(left_x, y, f"Name: {(first_name + ' ' + last_name).strip()[:42]}")
            y -= 0.16 * inch
        if address_line1:
            c.drawString(left_x, y, f"Address: {address_line1[:42]}")
            y -= 0.16 * inch
        if city or province:
            c.drawString(left_x, y, f"City/Prov: {(city + ', ' + province).strip(', ')[:42]}")

        c.drawString(right_x, box_top - 0.42 * inch, f"Reserve #: {invoice_packet['reserve_number'] or 'N/A'}")
        c.drawString(right_x, box_top - 0.58 * inch, f"Service Date: {invoice_packet['service_date']}")
        c.drawString(right_x, box_top - 0.74 * inch, f"Vehicle: {vehicle_number or 'N/A'}")
        c.drawString(right_x, box_top - 0.90 * inch, f"Type: {vehicle_type or 'N/A'}")
        c.drawString(right_x, box_top - 1.06 * inch, f"Passengers: {passengers}")

        section_y = box_top - 1.34 * inch
        c.setFont("Helvetica-Bold", 9)
        c.drawString(left_x, section_y, "CHARGES")
        c.setFont("Helvetica", 8)
        c.drawString(left_x, section_y - 0.16 * inch, "Description")
        c.drawRightString(width - 2.35 * inch, section_y - 0.16 * inch, "Amount")
        c.line(left_x, section_y - 0.20 * inch, width - 2.25 * inch, section_y - 0.20 * inch)

        charge_y = section_y - 0.38 * inch
        for charge in (invoice_packet.get("charge_items") or [])[:5]:
            desc = (charge.get("description") or "")[:48]
            amt = float(charge.get("amount") or 0)
            c.drawString(left_x, charge_y, desc)
            c.drawRightString(width - 2.35 * inch, charge_y, f"${amt:,.2f}")
            charge_y -= 0.16 * inch

        pay_x = width / 2 + 0.12 * inch
        c.setFont("Helvetica-Bold", 9)
        c.drawString(pay_x, section_y, "PAYMENTS")
        c.setFont("Helvetica", 8)
        c.drawString(pay_x, section_y - 0.16 * inch, "Date | Method")
        c.drawRightString(width - 0.85 * inch, section_y - 0.16 * inch, "Amount")
        c.line(pay_x, section_y - 0.20 * inch, width - 0.82 * inch, section_y - 0.20 * inch)

        payment_y = section_y - 0.38 * inch
        for payment in (invoice_packet.get("payment_items") or [])[:5]:
            pdate = payment.get("payment_date")
            if hasattr(pdate, "strftime"):
                pdate_text = pdate.strftime("%m/%d/%Y")
            else:
                pdate_text = str(pdate or "")
            method = (payment.get("method") or "")[:16]
            amt = float(payment.get("amount") or 0)
            c.drawString(pay_x, payment_y, f"{pdate_text} | {method}")
            c.drawRightString(width - 0.85 * inch, payment_y, f"${amt:,.2f}")
            payment_y -= 0.16 * inch

        totals_y = box_bottom + 0.78 * inch
        c.setLineWidth(0.9)
        c.line(box_left + 0.10 * inch, totals_y + 0.12 * inch, box_right - 0.10 * inch, totals_y + 0.12 * inch)
        c.setFont("Helvetica", 9)
        c.drawString(left_x, totals_y, "Total Charges:")
        c.drawRightString(width - 0.85 * inch, totals_y, f"${invoice_packet['total_charges']:,.2f}")
        totals_y -= 0.18 * inch
        c.drawString(left_x, totals_y, "Total Paid:")
        c.drawRightString(width - 0.85 * inch, totals_y, f"${invoice_packet['paid_amount']:,.2f}")
        totals_y -= 0.22 * inch
        c.setFont("Helvetica-Bold", 10)
        due_label = "AMOUNT DUE" if invoice_packet['amount_due'] > 0 else "CREDIT"
        c.drawString(left_x, totals_y, due_label)
        c.drawRightString(width - 0.85 * inch, totals_y, f"${abs(invoice_packet['amount_due']):,.2f}")

        c.setFont("Helvetica-Oblique", 8)
        c.drawCentredString(
            width / 2,
            1.00 * inch,
            f"Trip Invoice {invoice_packet['invoice_number']} - Charter {invoice_packet['charter_id']} - Generated {invoice_packet['invoice_date']}",
        )

    def _draw_multi_client_grouped_boxes(self, c, packets, width, height):
        """Draw one landscape page set with a single client header and bordered expandable charter boxes."""
        from reportlab.lib.units import inch

        if not packets:
            return

        def _fmt_money(amount):
            return f"${float(amount or 0):,.2f}"

        def _fmt_date(value):
            if hasattr(value, "strftime"):
                return value.strftime("%Y-%m-%d")
            return str(value or "")

        def _payment_lines(items, max_lines=6):
            lines = []
            for payment in (items or [])[:max_lines]:
                pdate = _fmt_date(payment.get("payment_date"))
                method = (payment.get("method") or "")
                ptype = "NRR" if "nrr" in method.lower() else "PAYMENT"
                lines.append(f"{pdate}  {ptype}  {_fmt_money(payment.get('amount'))}")
            return lines or ["-"]

        customer = packets[0].get("customer") or ""
        company_name = packets[0].get("company_name") or ""
        first_name = packets[0].get("first_name") or ""
        last_name = packets[0].get("last_name") or ""
        phone = packets[0].get("phone") or ""
        email = packets[0].get("email") or ""

        left = 0.35 * inch
        right = width - 0.35 * inch
        top = height - 0.35 * inch
        bottom = 0.35 * inch
        usable_width = right - left

        display_name = company_name or customer or (f"{first_name} {last_name}".strip()) or "Client"

        col_fracs = [0.09, 0.10, 0.10, 0.20, 0.30, 0.07, 0.07, 0.07]
        x = [left]
        for frac in col_fracs:
            x.append(x[-1] + usable_width * frac)

        def _draw_page_header(continued=False):
            addr_text = "38014 C&E Trl, Red Deer County, AB, T4E 1R9"
            gst_text = "G.S.T.#: 861 556 827"

            c.setFont("Helvetica-Bold", 15)
            c.drawCentredString(width / 2, top, "Arrow Limousine & Sedan Services Ltd.")
            c.setFont("Helvetica", 8.5)
            c.drawCentredString(width / 2, top - 0.16 * inch, addr_text)
            c.drawCentredString(width / 2, top - 0.30 * inch, gst_text)

            c.setFont("Helvetica-Bold", 10)
            c.drawString(left, top - 0.48 * inch, f"Client: {display_name}")
            c.setFont("Helvetica", 8.5)
            c.drawString(left, top - 0.63 * inch, f"Phone: {phone}    Email: {email}")
            c.drawRightString(right, top - 0.48 * inch, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            if continued:
                c.drawRightString(right, top - 0.63 * inch, "Continued")

            table_top = top - 0.82 * inch
            header_h = 0.20 * inch
            c.setLineWidth(0.9)
            c.rect(left, table_top - header_h, usable_width, header_h, stroke=1, fill=0)

            c.setFont("Helvetica-Bold", 7.6)
            headers = [
                "Charter",
                "Reserve",
                "Date",
                "Vehicle / Type / Pax",
                "Payments by Date",
                "Charges",
                "Paid",
                "Balance",
            ]
            for i, header in enumerate(headers):
                c.drawString(x[i] + 0.04 * inch, table_top - 0.14 * inch, header)
                if i > 0:
                    c.line(x[i], table_top, x[i], table_top - header_h)
            return table_top - header_h

        y = _draw_page_header(continued=False)
        total_charges_sum = 0.0
        total_paid_sum = 0.0

        for packet in packets:
            payment_lines = _payment_lines(packet.get("payment_items") or [])
            box_h = max(0.38 * inch, 0.14 * inch + (0.12 * inch * len(payment_lines)))

            if y - box_h < bottom + 0.50 * inch:
                c.showPage()
                y = _draw_page_header(continued=True)

            c.setLineWidth(1.0)
            c.rect(left, y - box_h, usable_width, box_h, stroke=1, fill=0)
            for i in range(1, len(x) - 1):
                c.line(x[i], y, x[i], y - box_h)

            c.setFont("Helvetica", 8)
            c.drawString(x[0] + 0.04 * inch, y - 0.14 * inch, str(packet.get("charter_id") or ""))
            c.drawString(x[1] + 0.04 * inch, y - 0.14 * inch, str(packet.get("reserve_number") or "")[:16])
            c.drawString(x[2] + 0.04 * inch, y - 0.14 * inch, str(packet.get("service_date") or "")[:10])

            vehicle_line = (
                f"{packet.get('vehicle_number') or ''} / "
                f"{packet.get('vehicle_type') or ''} / "
                f"{int(packet.get('passengers') or 0)}"
            )
            c.drawString(x[3] + 0.04 * inch, y - 0.14 * inch, vehicle_line[:34])

            pay_y = y - 0.14 * inch
            for payment_line in payment_lines:
                c.drawString(x[4] + 0.04 * inch, pay_y, payment_line[:56])
                pay_y -= 0.12 * inch

            charges = float(packet.get("total_charges") or 0)
            paid = float(packet.get("paid_amount") or 0)
            balance = float(packet.get("amount_due") or (charges - paid))

            total_charges_sum += charges
            total_paid_sum += paid

            c.drawRightString(x[6] - 0.04 * inch, y - 0.14 * inch, _fmt_money(charges))
            c.drawRightString(x[7] - 0.04 * inch, y - 0.14 * inch, _fmt_money(paid))
            c.drawRightString(x[8] - 0.04 * inch, y - 0.14 * inch, _fmt_money(balance))

            y -= box_h

        total_balance_sum = total_charges_sum - total_paid_sum
        totals_h = 0.28 * inch
        if y - totals_h < bottom:
            c.showPage()
            y = _draw_page_header(continued=True)

        c.setLineWidth(1.1)
        c.rect(left, y - totals_h, usable_width, totals_h, stroke=1, fill=0)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(left + 0.06 * inch, y - 0.18 * inch, "CLIENT TOTALS")
        c.drawRightString(x[6] - 0.04 * inch, y - 0.18 * inch, _fmt_money(total_charges_sum))
        c.drawRightString(x[7] - 0.04 * inch, y - 0.18 * inch, _fmt_money(total_paid_sum))
        c.drawRightString(x[8] - 0.04 * inch, y - 0.18 * inch, _fmt_money(total_balance_sum))

    def export_modern_invoices_pdf(
        self,
        charter_ids: Optional[List[int]] = None,
        output_path: Optional[str] = None,
        open_after_save: bool = True,
    ):
        """Export one or more charter invoices in modern template format."""
        try:
            from PyQt6.QtWidgets import QFileDialog, QMessageBox
        except Exception as e:
            QMessageBox.critical(
                self,
                "Missing Dependency",
                f"Modern invoice export requires pypdf/reportlab.\n\n{e}",
            )
            return None

        if not charter_ids:
            if not self.charter_id:
                QMessageBox.warning(self, "No Charter", "No charter selected for export")
                return None
            charter_ids = [self.charter_id]

        packets = []
        for cid in charter_ids:
            packet = self._fetch_invoice_packet(cid)
            if packet:
                packets.append(packet)

        if not packets:
            QMessageBox.warning(self, "No Data", "No invoice data found for selected charter(s)")
            return None

        if not output_path:
            invoices_dir = Path(__file__).resolve().parents[1] / "invoices"
            invoices_dir.mkdir(parents=True, exist_ok=True)
            if len(packets) == 1:
                reserve = str(packets[0].get("reserve_number") or "").strip()
                if not reserve:
                    reserve = f"{int(packets[0].get('charter_id') or 0):06d}"
                safe_reserve = "".join(
                    ch if ch.isalnum() or ch in ("-", "_") else "_"
                    for ch in reserve
                )
                if not safe_reserve:
                    safe_reserve = f"{int(packets[0].get('charter_id') or 0):06d}"
                default_name = f"{safe_reserve}_invoice.pdf"
            else:
                default_name = f"Multi_Invoice_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            output_path = str(invoices_dir / default_name)

        if not output_path:
            return None

        output_path = str(output_path)
        resolved_output_path = self._resolve_pdf_output_path(output_path)

        try:
            from reportlab.lib.pagesizes import letter, landscape
            from reportlab.pdfgen import canvas
            if len(packets) > 1:
                width, height = landscape(letter)
                c = canvas.Canvas(resolved_output_path, pagesize=landscape(letter))
                self._draw_multi_client_grouped_boxes(c, packets, width, height)
            else:
                width, height = letter
                c = canvas.Canvas(resolved_output_path, pagesize=letter)
                self._draw_grouped_invoice_overlay(c, packets[0], width, height)
            c.save()

            if resolved_output_path != output_path:
                QMessageBox.information(
                    self,
                    "File In Use",
                    "Selected PDF was in use. Saved to alternate file:\n"
                    f"{resolved_output_path}",
                )

            if open_after_save:
                try:
                    os.startfile(resolved_output_path)
                except Exception:
                    pass

            return resolved_output_path
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to build modern invoice PDF:\n{e}")
            return None

    def export_multi_charter_consolidated_invoice(
        self,
        charter_ids: Optional[List[int]] = None,
        output_path: Optional[str] = None,
        open_after_save: bool = True,
    ):
        """Export multiple charters in consolidated format: grouped by charter with consolidated totals."""
        try:
            from PyQt6.QtWidgets import QFileDialog, QMessageBox
        except Exception as e:
            QMessageBox.critical(
                self,
                "Missing Dependency",
                f"Multi-charter export requires PyQt6.\n\n{e}",
            )
            return None

        if not charter_ids:
            QMessageBox.warning(self, "No Charters", "Please provide charter IDs to export")
            return None

        packets = []
        for cid in charter_ids:
            packet = self._fetch_invoice_packet(cid)
            if packet:
                packets.append(packet)

        if not packets:
            QMessageBox.warning(self, "No Data", "No invoice data found for selected charter(s)")
            return None

        if not output_path:
            invoices_dir = Path(__file__).resolve().parents[1] / "invoices"
            invoices_dir.mkdir(parents=True, exist_ok=True)
            default_name = (
                f"Consolidated_Multi_Invoice_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            )
            output_path = str(invoices_dir / default_name)

        if not output_path:
            return None

        output_path = str(output_path)
        resolved_output_path = self._resolve_pdf_output_path(output_path)

        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.units import inch
            from reportlab.pdfgen import canvas

            c = canvas.Canvas(resolved_output_path, pagesize=letter)
            width, height = letter
            current_y = height - 0.75 * inch

            # Header
            from reportlab.lib.colors import Color

            addr_text = "38014 C&E Trl, Red Deer County, AB, T4E 1R9"
            gst_text = "G.S.T.#: 861 556 827"

            c.setFillColor(Color(1, 1, 1, alpha=1.0))
            c.rect(0, 0, width, height, fill=1, stroke=0)
            c.setFillColor(Color(0.0, 0.0, 0.0, alpha=1.0))

            c.setFont("Helvetica-Bold", 14)
            c.drawCentredString(width / 2, current_y, "Arrow Limousine & Sedan Services Ltd.")
            current_y -= 0.25 * inch

            c.setFont("Helvetica", 8)
            c.drawCentredString(width / 2, current_y, addr_text)
            current_y -= 0.15 * inch
            c.drawCentredString(width / 2, current_y, gst_text)
            current_y -= 0.30 * inch

            c.setFont("Helvetica-Bold", 12)
            c.drawString(0.75 * inch, current_y, "CONSOLIDATED INVOICE")
            c.setFont("Helvetica", 9)
            c.drawRightString(width - 0.75 * inch, current_y, f"Date: {datetime.now().strftime('%m/%d/%Y')}")
            current_y -= 0.35 * inch

            # Process each charter
            grand_total_charges = 0.0
            grand_total_paid = 0.0
            grand_total_due = 0.0

            for idx, packet in enumerate(packets):
                # Page break if needed
                if current_y < 2.0 * inch:
                    c.showPage()
                    current_y = height - 0.75 * inch

                # Charter header
                c.setFont("Helvetica-Bold", 10)
                charter_line = (
                    f"Charter {packet['charter_id']:06d} | "
                    f"Reserve #{packet['reserve_number'] or 'N/A'} | "
                    f"{packet['service_date']} | "
                    f"{packet['vehicle_type'] or 'Vehicle'}"
                )
                c.drawString(0.75 * inch, current_y, charter_line[:90])
                current_y -= 0.22 * inch

                # Client info
                c.setFont("Helvetica", 8.5)
                c.drawString(0.75 * inch, current_y, f"Client: {packet['customer']}")
                current_y -= 0.18 * inch
                if packet['phone']:
                    c.drawString(0.75 * inch, current_y, f"Phone: {packet['phone']}")
                    current_y -= 0.18 * inch

                # Charges section
                c.setFont("Helvetica-Bold", 9)
                c.drawString(0.75 * inch, current_y, "Charges:")
                c.setFont("Helvetica", 8)
                current_y -= 0.20 * inch

                charge_items = packet.get("charge_items") or []
                if charge_items:
                    for charge in charge_items:
                        desc = (charge.get("description") or "")[:50]
                        amt = float(charge.get("amount") or 0)
                        c.drawString(1.00 * inch, current_y, desc)
                        c.drawRightString(width - 0.75 * inch, current_y, f"${amt:,.2f}")
                        current_y -= 0.16 * inch
                else:
                    c.drawString(1.00 * inch, current_y, "No detailed charges")
                    current_y -= 0.16 * inch

                # Subtotals
                c.setFont("Helvetica", 8)
                c.line(0.75 * inch, current_y + 0.04 * inch, width - 0.75 * inch, current_y + 0.04 * inch)
                current_y -= 0.12 * inch

                c.drawString(1.00 * inch, current_y, "Subtotal (before GST):")
                c.drawRightString(width - 0.75 * inch, current_y, f"${packet['subtotal']:,.2f}")
                current_y -= 0.16 * inch

                c.drawString(1.00 * inch, current_y, "GST (5% included):")
                c.drawRightString(width - 0.75 * inch, current_y, f"${packet['gst_amount']:,.2f}")
                current_y -= 0.16 * inch

                c.setFont("Helvetica-Bold", 9)
                c.drawString(1.00 * inch, current_y, "Charter Total:")
                c.drawRightString(width - 0.75 * inch, current_y, f"${packet['total_charges']:,.2f}")
                current_y -= 0.20 * inch

                # Payments section
                c.setFont("Helvetica-Bold", 9)
                c.drawString(0.75 * inch, current_y, "Payments:")
                c.setFont("Helvetica", 8)
                current_y -= 0.20 * inch

                payment_items = packet.get("payment_items") or []
                if payment_items:
                    for payment in payment_items:
                        pdate = payment.get("payment_date")
                        if hasattr(pdate, "strftime"):
                            pdate_text = pdate.strftime("%m/%d/%Y")
                        else:
                            pdate_text = str(pdate or "")
                        method = (payment.get("method") or "")[:20]
                        amt = float(payment.get("amount") or 0)
                        c.drawString(1.00 * inch, current_y, f"{pdate_text} | {method}")
                        c.drawRightString(width - 0.75 * inch, current_y, f"${amt:,.2f}")
                        current_y -= 0.16 * inch
                else:
                    c.drawString(1.00 * inch, current_y, "No payments recorded")
                    current_y -= 0.16 * inch

                c.setFont("Helvetica", 8)
                c.line(0.75 * inch, current_y + 0.04 * inch, width - 0.75 * inch, current_y + 0.04 * inch)
                current_y -= 0.12 * inch

                c.drawString(1.00 * inch, current_y, "Total Paid:")
                c.drawRightString(width - 0.75 * inch, current_y, f"${packet['paid_amount']:,.2f}")
                current_y -= 0.16 * inch

                c.setFont("Helvetica-Bold", 9)
                amt_due = packet['amount_due']
                due_label = "AMOUNT DUE" if amt_due > 0 else "CREDIT"
                c.drawString(1.00 * inch, current_y, due_label)
                c.drawRightString(width - 0.75 * inch, current_y, f"${abs(amt_due):,.2f}")
                current_y -= 0.28 * inch

                # Accumulate for grand totals
                grand_total_charges += packet['total_charges']
                grand_total_paid += packet['paid_amount']
                grand_total_due += packet['amount_due']

            # Consolidated summary on last page
            if current_y < 1.5 * inch:
                c.showPage()
                current_y = height - 0.75 * inch

            c.setFont("Helvetica-Bold", 11)
            c.drawString(0.75 * inch, current_y, "CONSOLIDATED TOTALS")
            current_y -= 0.28 * inch

            c.setFont("Helvetica", 9)
            c.line(0.75 * inch, current_y + 0.06 * inch, width - 0.75 * inch, current_y + 0.06 * inch)
            current_y -= 0.12 * inch

            c.drawString(1.00 * inch, current_y, f"Total Charters: {len(packets)}")
            current_y -= 0.20 * inch

            c.drawString(1.00 * inch, current_y, "Total Charges:")
            c.drawRightString(width - 0.75 * inch, current_y, f"${grand_total_charges:,.2f}")
            current_y -= 0.20 * inch

            c.drawString(1.00 * inch, current_y, "Total Paid:")
            c.drawRightString(width - 0.75 * inch, current_y, f"${grand_total_paid:,.2f}")
            current_y -= 0.20 * inch

            c.setFont("Helvetica-Bold", 10)
            due_label = "TOTAL AMOUNT DUE" if grand_total_due > 0 else "TOTAL CREDIT"
            c.drawString(1.00 * inch, current_y, due_label)
            c.drawRightString(width - 0.75 * inch, current_y, f"${abs(grand_total_due):,.2f}")

            c.save()

            if resolved_output_path != output_path:
                QMessageBox.information(
                    self,
                    "File In Use",
                    "Selected PDF was in use. Saved to alternate file:\n"
                    f"{resolved_output_path}",
                )

            if open_after_save:
                try:
                    os.startfile(resolved_output_path)
                except Exception:
                    pass

            return resolved_output_path

        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to build multi-charter invoice:\n{e}")
            return None

    def _resolve_pdf_output_path(self, output_path: str) -> str:
        """Return writable PDF path; when target is locked, use timestamped fallback."""
        path = Path(output_path)
        if path.suffix.lower() != ".pdf":
            path = path.with_suffix(".pdf")

        if not path.exists():
            return str(path)

        try:
            with open(path, "ab"):
                pass
            return str(path)
        except PermissionError:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            fallback = path.with_name(f"{path.stem}_{stamp}{path.suffix}")
            logger.warning(
                "PDF target in use; writing invoice to fallback path: %s",
                fallback,
            )
            return str(fallback)

    def email_current_invoice(self):
        """Create email draft for the current charter invoice with PDF attached."""
        if not self.charter_id:
            QMessageBox.warning(self, "No Charter", "Please save/load a charter first")
            return
        self._email_invoice_pack([self.charter_id], mark_sent=True)

    def _create_invoice_pdf_for_email(self, charter_ids):
        """Build a temporary invoice PDF for email attachment."""
        import tempfile

        tmp_dir = tempfile.gettempdir()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_path = os.path.join(tmp_dir, f"ArrowLimo_Invoices_{stamp}.pdf")
        saved = self.export_modern_invoices_pdf(
            charter_ids=charter_ids,
            output_path=pdf_path,
            open_after_save=False,
        )
        return saved

    def _open_email_draft_with_attachment(self, to_email, subject, body, attachment_path):
        """Open Outlook draft with attachment; fallback to mailto without attachment."""
        try:
            import win32com.client  # type: ignore

            outlook = win32com.client.Dispatch("Outlook.Application")
            mail = outlook.CreateItem(0)
            mail.To = to_email or ""
            mail.Subject = subject
            mail.Body = body
            if attachment_path and os.path.exists(attachment_path):
                mail.Attachments.Add(attachment_path)
            mail.Display(True)
            return True
        except Exception:
            try:
                import urllib.parse
                import webbrowser

                uri = (
                    "mailto:" + urllib.parse.quote(to_email or "") +
                    "?subject=" + urllib.parse.quote(subject) +
                    "&body=" + urllib.parse.quote(body)
                )
                webbrowser.open(uri)
                return True
            except Exception:
                return False

    def _set_invoice_sent_for_charters(self, charter_ids, sent_date=None):
        """Persist invoice sent marker in booking notes for the provided charters."""
        if not charter_ids:
            return
        date_text = sent_date or datetime.now().strftime("%Y-%m-%d")

        cur = self.db.get_cursor()
        try:
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'charters'
                      AND column_name = 'booking_notes'
                )
                """
            )
            has_booking_notes = bool(cur.fetchone()[0])
            notes_col = "booking_notes" if has_booking_notes else "notes"

            for cid in charter_ids:
                cur.execute(
                    f"SELECT COALESCE({notes_col}, '') FROM charters WHERE charter_id = %s",
                    (cid,),
                )
                row = cur.fetchone()
                current_notes = (row[0] if row else "") or ""
                clean_notes, markers = self._extract_internal_delivery_markers(current_notes)
                markers["INVOICE_SENT"] = date_text
                marker_lines = [f"##SYS:{k}={v}" for k, v in sorted(markers.items())]
                updated_notes = (
                    f"{clean_notes}\n" + "\n".join(marker_lines)
                    if clean_notes else "\n".join(marker_lines)
                )
                cur.execute(
                    f"UPDATE charters SET {notes_col} = %s, updated_at = NOW() WHERE charter_id = %s",
                    (updated_notes, cid),
                )

            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        finally:
            cur.close()

    def _email_invoice_pack(self, charter_ids, mark_sent=False):
        """Prepare invoice pack and open direct email draft with attachment."""
        if not charter_ids:
            QMessageBox.warning(self, "No Selection", "No charters selected")
            return
        pdf_file = self._create_invoice_pdf_for_email(charter_ids)
        if not pdf_file:
            return

        to_email = ""
        customer_name = "Client"
        try:
            packet = self._fetch_invoice_packet(charter_ids[0])
            if packet:
                to_email = packet.get("email", "")
                customer_name = packet.get("customer", "Client") or "Client"
        except Exception:
            pass

        subject = f"Arrow Limousine Invoice Pack ({len(charter_ids)} trip{'s' if len(charter_ids) != 1 else ''})"
        body = (
            f"Hello {customer_name},\n\n"
            f"Please find attached your invoice PDF pack containing {len(charter_ids)} trip invoice(s).\n\n"
            "Thank you,\nArrow Limousine"
        )
        ok = self._open_email_draft_with_attachment(to_email, subject, body, pdf_file)
        if ok and mark_sent:
            try:
                self._set_invoice_sent_for_charters(charter_ids)
                if len(charter_ids) == 1 and self.charter_id == charter_ids[0]:
                    self.invoice_sent_checkbox.setChecked(True)
                    self.invoice_sent_date.setDate(QDate.currentDate())
            except Exception as e:
                QMessageBox.warning(self, "Marker Warning", f"Email opened but could not mark sent status:\n{e}")

    def open_multi_invoice_selection_dialog(self):
        """Main print-menu flow: select client charters and print/save/email together."""
        if not self.charter_id:
            QMessageBox.warning(self, "No Charter", "Load/save a charter first")
            return

        cur = self.db.get_cursor()
        try:
            cur.execute(
                """
                SELECT c.client_id, COALESCE(cl.company_name, cl.client_name, cl.name, 'Client')
                FROM charters c
                LEFT JOIN clients cl ON cl.client_id = c.client_id
                WHERE c.charter_id = %s
                """,
                (self.charter_id,),
            )
            head = cur.fetchone()
            if not head or not head[0]:
                QMessageBox.warning(self, "No Client", "Current charter has no client assigned")
                return

            client_id, client_name = head
            cur.execute(
                """
                SELECT charter_id,
                       reserve_number,
                       charter_date,
                       COALESCE(total_amount_due, grand_total, 0) AS total_charges,
                       GREATEST(COALESCE(amount_paid, 0), COALESCE(paid_amount, 0)) AS paid,
                       COALESCE(booking_notes, notes, '') AS notes_blob
                FROM charters
                WHERE client_id = %s
                ORDER BY charter_date DESC, reserve_number DESC
                LIMIT 500
                """,
                (client_id,),
            )
            rows = cur.fetchall()
            if not rows:
                QMessageBox.information(self, "No Charters", "No charters found for this client")
                return

            dialog = QDialog(self)
            dialog.setWindowTitle(f"Print Multi Invoice - {client_name}")
            dialog.setGeometry(120, 120, 980, 620)
            root = QVBoxLayout(dialog)

            info = QLabel("Select charter invoices to print/save/email as one multi invoice")
            root.addWidget(info)

            table = QTableWidget()
            table.setColumnCount(8)
            table.setHorizontalHeaderLabels([
                "Select", "Reserve #", "Date", "Total", "Paid", "Due", "Invoice Sent", "Sent Date"
            ])
            table.setRowCount(len(rows))
            table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
            table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
            table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
            table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
            table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)

            for i, row in enumerate(rows):
                cid, reserve, cdate, total, paid, notes_blob = row
                total = float(total or 0)
                paid = float(paid or 0)
                due = total - paid
                clean_notes, markers = self._extract_internal_delivery_markers(notes_blob or "")
                inv_sent_date = markers.get("INVOICE_SENT", "")

                sel = QTableWidgetItem("")
                sel.setFlags(sel.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                sel.setCheckState(Qt.CheckState.Unchecked)
                sel.setData(Qt.ItemDataRole.UserRole, int(cid))
                table.setItem(i, 0, sel)
                table.setItem(i, 1, QTableWidgetItem(str(reserve or "")))
                table.setItem(i, 2, QTableWidgetItem(str(cdate or "")))
                table.setItem(i, 3, QTableWidgetItem(f"${total:,.2f}"))
                table.setItem(i, 4, QTableWidgetItem(f"${paid:,.2f}"))
                table.setItem(i, 5, QTableWidgetItem(f"${due:,.2f}"))
                table.setItem(i, 6, QTableWidgetItem("Yes" if inv_sent_date else "No"))
                table.setItem(i, 7, QTableWidgetItem(inv_sent_date))

            root.addWidget(table)

            def selected_ids():
                ids = []
                for r in range(table.rowCount()):
                    sel_item = table.item(r, 0)
                    if sel_item and sel_item.checkState() == Qt.CheckState.Checked:
                        ids.append(int(sel_item.data(Qt.ItemDataRole.UserRole)))
                return ids

            btns = QHBoxLayout()
            select_all_btn = QPushButton("Select All")
            clear_btn = QPushButton("Clear")
            print_btn = QPushButton("Print Selected")
            save_btn = QPushButton("Save Multi Invoice PDF")
            save_consolidated_btn = QPushButton("Save Consolidated Multi Invoice")
            email_btn = QPushButton("Email Selected")
            mark_sent_btn = QPushButton("Mark Selected Sent Today")
            close_btn = QPushButton("Close")

            btns.addWidget(select_all_btn)
            btns.addWidget(clear_btn)
            btns.addStretch()
            btns.addWidget(print_btn)
            btns.addWidget(save_btn)
            btns.addWidget(save_consolidated_btn)
            btns.addWidget(email_btn)
            btns.addWidget(mark_sent_btn)
            btns.addWidget(close_btn)
            root.addLayout(btns)

            def do_select_all(state):
                for r in range(table.rowCount()):
                    sel_item = table.item(r, 0)
                    if sel_item:
                        sel_item.setCheckState(state)

            def do_print():
                ids = selected_ids()
                if not ids:
                    QMessageBox.information(dialog, "No Selection", "Select at least one invoice")
                    return
                self.export_modern_invoices_pdf(ids, output_path=None, open_after_save=True)

            def do_save():
                ids = selected_ids()
                if not ids:
                    QMessageBox.information(dialog, "No Selection", "Select at least one invoice")
                    return
                self.export_modern_invoices_pdf(ids, output_path=None, open_after_save=False)

            def do_save_consolidated():
                ids = selected_ids()
                if not ids:
                    QMessageBox.information(dialog, "No Selection", "Select at least one invoice")
                    return
                self.export_multi_charter_consolidated_invoice(ids, output_path=None, open_after_save=True)

            def do_email():
                ids = selected_ids()
                if not ids:
                    QMessageBox.information(dialog, "No Selection", "Select at least one invoice")
                    return
                self._email_invoice_pack(ids, mark_sent=True)

            def do_mark_sent():
                ids = selected_ids()
                if not ids:
                    QMessageBox.information(dialog, "No Selection", "Select at least one invoice")
                    return
                try:
                    today = datetime.now().strftime("%Y-%m-%d")
                    self._set_invoice_sent_for_charters(ids, sent_date=today)
                    for r in range(table.rowCount()):
                        sel_item = table.item(r, 0)
                        if sel_item and sel_item.checkState() == Qt.CheckState.Checked:
                            table.item(r, 6).setText("Yes")
                            table.item(r, 7).setText(today)
                    QMessageBox.information(dialog, "Updated", f"Marked {len(ids)} invoice(s) as sent on {today}")
                except Exception as e:
                    QMessageBox.critical(dialog, "Update Error", f"Failed to update sent marker:\n{e}")

            select_all_btn.clicked.connect(lambda: do_select_all(Qt.CheckState.Checked))
            clear_btn.clicked.connect(lambda: do_select_all(Qt.CheckState.Unchecked))
            print_btn.clicked.connect(do_print)
            save_btn.clicked.connect(do_save)
            save_consolidated_btn.clicked.connect(do_save_consolidated)
            email_btn.clicked.connect(do_email)
            mark_sent_btn.clicked.connect(do_mark_sent)
            close_btn.clicked.connect(dialog.accept)

            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Multi-Invoice Error", f"Failed to open multi-invoice flow:\n{e}")
        finally:
            cur.close()

    def export_dialog_to_csv(self, title, text):
        """Export dialog text to CSV"""
        try:
            import csv
            from datetime import datetime

            filename, _ = QFileDialog.getSaveFileName(
                self,
                f"Export {title} to CSV",
                f"{title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "CSV Files (*.csv);;All Files (*)")

            if not filename:
                return

            # Parse text into rows (split by newlines)
            rows = [line.split('\t') if '\t' in line else [line]
                    for line in text.split('\n') if line.strip()]

            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerows(rows)

            QMessageBox.information(
                self, "Success", f"✅ Exported to CSV:\n{filename}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"CSV export failed: {e}")

    def export_dialog_to_word(self, title, text):
        """Export dialog text to Word (.docx)"""
        try:
            from datetime import datetime

            from docx import Document
            from docx.enum.text import WD_ALIGN_PARAGRAPH
            from docx.shared import Pt

            filename, _ = QFileDialog.getSaveFileName(
                self,
                f"Export {title} to Word",
                f"{title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx",
                "Word Files (*.docx);;All Files (*)")

            if not filename:
                return

            # Create document
            doc = Document()

            # Add title
            title_para = doc.add_paragraph(title)
            title_para.style = 'Heading 1'
            title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

            # Add timestamp
            timestamp_para = doc.add_paragraph(
                f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            timestamp_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            timestamp_para_format = timestamp_para.runs[0]
            timestamp_para_format.italic = True
            timestamp_para_format.font.size = Pt(10)

            # Add blank line
            doc.add_paragraph()

            # Add text content with monospace font (for forms/letters)
            text_para = doc.add_paragraph(text)
            text_para.style = 'Normal'
            for run in text_para.runs:
                run.font.name = 'Courier New'
                run.font.size = Pt(9)

            # Save document
            doc.save(filename)

            QMessageBox.information(
                self, "Success", f"✅ Exported to Word:\n{filename}")
        except ImportError:
            QMessageBox.warning(
                self,
                "Missing Library",
                "Word export requires python-docx.\n\n"
                "Install with: pip install python-docx\n\n"
                "Falling back to text export.")
            self.export_dialog_to_pdf(title, text)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Word export failed: {e}")

    def save_charter_routes(self, cur):
        """
        Save all route lines from UI to charter_routes table.
        CRITICAL: Without this, route data is LOST!
        """
        if not self.charter_id:
            return  # Can't save routes without charter_id

        try:
            # Delete existing routes for this charter
            cur.execute(
                "DELETE FROM charter_routes"
                " WHERE charter_id = %s",
                (self.charter_id,))

            # Insert all routes from UI table
            for row_idx in range(self.route_table.rowCount()):
                # Read event type (col 0 — QComboBox or QTableWidgetItem)
                w0 = self.route_table.cellWidget(row_idx, 0)
                if w0 and hasattr(w0, 'currentData'):
                    event_type_code = w0.currentData() or ""
                elif w0 and hasattr(w0, 'currentText'):
                    event_type_code = w0.currentText() or ""
                else:
                    itm = self.route_table.item(row_idx, 0)
                    event_type_code = itm.data(
                        Qt.ItemDataRole.UserRole) or (
                        itm.text() if itm else "") or ""

                # Col 1: Destination / Description
                itm1 = self.route_table.item(row_idx, 1)
                address = itm1.text() if itm1 else ""

                # Col 2: At/By (QComboBox)
                w2 = self.route_table.cellWidget(row_idx, 2)
                _at_by = w2.currentText() if w2 and hasattr(
                    w2, 'currentText') else (
                    self.route_table.item(row_idx, 2).text()
                    if self.route_table.item(row_idx, 2) else "at")

                # Col 3: Time (QTimeEdit)
                w3 = self.route_table.cellWidget(row_idx, 3)
                if w3 and hasattr(w3, 'time'):
                    t = w3.time()
                    stop_time = f"{t.hour():02d}:{t.minute():02d}"
                else:
                    itm3 = self.route_table.item(row_idx, 3)
                    stop_time = itm3.text() if itm3 else ""

                # Col 4: Notes
                itm4 = self.route_table.item(row_idx, 4)
                route_notes = itm4.text() if itm4 else ""

                # Persist At/By alongside notes without requiring schema changes.
                clean_notes = str(route_notes or "")
                lower_notes = clean_notes.lower()
                if lower_notes.startswith("[at_by:at]"):
                    clean_notes = clean_notes[len("[at_by:at]"):].lstrip()
                elif lower_notes.startswith("[at_by:by]"):
                    clean_notes = clean_notes[len("[at_by:by]"):].lstrip()
                route_notes_to_save = f"[at_by:{_at_by}] {clean_notes}".strip()

                cur.execute(
                    """
                    INSERT INTO charter_routes
                    (charter_id, route_sequence, event_type_code,
                     address, stop_time, route_notes)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (self.charter_id, row_idx + 1,
                     event_type_code, address, stop_time or None,
                     route_notes_to_save))
            print(
                f"✅ Saved {self.route_table.rowCount()}"
                f" routes for charter {self.charter_id}")
        except Exception as e:
            try:
                self.db.rollback()
            except Exception:
                pass
            print(f"❌ Error saving routes: {e}")
            raise

    def save_charter_charges(self, cur):
        """
        Save all charge lines from UI to charter_charges table.
        CRITICAL: Without this, billing data is LOST!
        """
        if not self.charter_id:
            return  # Can't save charges without charter_id

        try:
            # Delete existing charges for this charter
            cur.execute(
                "DELETE FROM charter_charges"
                " WHERE charter_id = %s",
                (self.charter_id,))

            # Insert all charges from UI table
            for row_idx in range(self.charges_table.rowCount()):
                desc_item = self.charges_table.item(row_idx, 0)
                type_item = self.charges_table.item(row_idx, 1)
                total_item = self.charges_table.item(row_idx, 2)

                description_display = desc_item.text() if desc_item else ""
                meta = desc_item.data(
                    Qt.ItemDataRole.UserRole) if desc_item else {}
                calc_type = (
                    meta.get("calc_type") if isinstance(
                        meta, dict) else None) or (
                    type_item.text() if type_item else "Fixed")
                value = meta.get("value") if isinstance(meta, dict) else None

                if calc_type.lower() == "fixed":
                    try:
                        value = float(
                            total_item.text().replace(
                                '$', '').replace(
                                ',', '')) if total_item else 0.0
                    except Exception:
                        value = 0.0
                elif value is None:
                    try:
                        value = float(
                            total_item.text().replace(
                                '$', '').replace(
                                ',', '')) if total_item else 0.0
                    except Exception:
                        value = 0.0

                line_total = self._compute_line_total(calc_type, value)
                description_db = self._format_description_with_metadata(
                    description_display, calc_type, value)
                charge_type = meta.get("charge_type", "service") if isinstance(
                    meta, dict) else "service"

                # Get reserve_number for this charter
                reserve_number = getattr(self, '_current_reserve_number', None)
                if not reserve_number:
                    try:
                        reserve_number = (
                            self.customer_widget.reserve_input.text()
                            or None)
                    except Exception:
                        reserve_number = None

                cur.execute(
                    """
                    INSERT INTO charter_charges
                    (charter_id, reserve_number, description, amount, rate,
                     sequence, charge_type, category,
                     last_updated, last_updated_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), 'DESKTOP')
                    """,
                    (self.charter_id, reserve_number, description_db,
                     line_total, float(value), row_idx + 1,
                     charge_type, charge_type))

            # Sync grand_total, gst_amount, amount_paid, balance_owing as
            # stored values
            reserve_number = getattr(self, '_current_reserve_number', None)
            if not reserve_number:
                try:
                    reserve_number = (
                        self.customer_widget.reserve_input.text()
                        or None)
                except Exception:
                    reserve_number = None
            cur.execute("""
                UPDATE charters
                SET grand_total = (
                    SELECT COALESCE(SUM(amount), 0)
                    FROM charter_charges WHERE charter_id = %s
                ),
                gst_amount = (
                    SELECT COALESCE(SUM(amount), 0)
                    FROM charter_charges
                    WHERE charter_id = %s
                    AND charge_type = 'tax'
                ),
                amount_paid = (
                    CASE
                        WHEN EXISTS (
                            SELECT 1
                            FROM charter_payments
                            WHERE charter_id = %s OR charter_id = %s
                        ) THEN (
                            SELECT COALESCE(SUM(amount), 0)
                            FROM charter_payments
                            WHERE charter_id = %s OR charter_id = %s
                        )
                        ELSE (
                            SELECT COALESCE(SUM(amount), 0)
                            FROM payments
                            WHERE reserve_number = %s OR charter_id = %s
                        )
                    END
                ),
                balance_owing = (
                    SELECT COALESCE(SUM(amount), 0)
                    FROM charter_charges WHERE charter_id = %s
                ) - (
                    CASE
                        WHEN EXISTS (
                            SELECT 1
                            FROM charter_payments
                            WHERE charter_id = %s OR charter_id = %s
                        ) THEN (
                            SELECT COALESCE(SUM(amount), 0)
                            FROM charter_payments
                            WHERE charter_id = %s OR charter_id = %s
                        )
                        ELSE (
                            SELECT COALESCE(SUM(amount), 0)
                            FROM payments
                            WHERE reserve_number = %s OR charter_id = %s
                        )
                    END
                ),
                driver_gratuity = (
                    SELECT COALESCE(SUM(amount), 0)
                    FROM charter_charges
                    WHERE charter_id = %s
                    AND charge_type = 'gratuity'
                ),
                approved_hours = %s,
                approved_gratuity = %s,
                driver_hourly_rate = %s,
                driver_total_expense = (
                    COALESCE(%s, 0) * COALESCE(%s, 0)
                    + COALESCE(%s, (SELECT COALESCE(SUM(amount), 0)
                       FROM charter_charges
                       WHERE charter_id = %s
                       AND charge_type = 'gratuity'))
                ),
                updated_at = NOW()
                WHERE charter_id = %s
            """, (
                self.charter_id,  # grand_total
                self.charter_id,  # gst_amount
                reserve_number,   # amount_paid cp reserve_number
                str(self.charter_id),  # amount_paid cp charter_id text
                reserve_number,   # amount_paid cp reserve_number sum
                str(self.charter_id),  # amount_paid cp charter_id text sum
                reserve_number,   # amount_paid payments reserve_number
                self.charter_id,  # amount_paid payments charter_id int
                self.charter_id,  # balance_owing numerator
                reserve_number,   # balance cp exists reserve_number
                str(self.charter_id),  # balance cp exists charter_id text
                reserve_number,   # balance cp sum reserve_number
                str(self.charter_id),  # balance cp sum charter_id text
                reserve_number,   # balance payments reserve_number
                self.charter_id,  # balance payments charter_id int
                self.charter_id,  # driver_gratuity
                getattr(self.dp_approved_hours, 'value', lambda: None)(
                ) if hasattr(self, 'dp_approved_hours') else None,
                getattr(self.dp_approved_gratuity, 'value', lambda: None)(
                ) if hasattr(self, 'dp_approved_gratuity') else None,
                getattr(self.dp_hourly_rate, 'value', lambda: None)(
                ) if hasattr(self, 'dp_hourly_rate') else None,
                getattr(self.dp_approved_hours, 'value', lambda: None)(
                ) if hasattr(self, 'dp_approved_hours') else 0,
                getattr(self.dp_hourly_rate, 'value', lambda: None)(
                ) if hasattr(self, 'dp_hourly_rate') else 0,
                getattr(self.dp_approved_gratuity, 'value', lambda: None)(
                ) if hasattr(self, 'dp_approved_gratuity') else None,
                self.charter_id,
                # driver_total_expense fallback gratuity subquery
                self.charter_id,  # WHERE
            ))

            print(
                f"✅ Saved {self.charges_table.rowCount()}"
                f" charges for charter {self.charter_id}")

            # Refresh billed gratuity display in Driver Pay panel after save
            try:
                grat_row = None
                for row_idx in range(self.charges_table.rowCount()):
                    meta = self.charges_table.item(row_idx, 0)
                    m = meta.data(Qt.ItemDataRole.UserRole) if meta else {}
                    if isinstance(m, dict) and m.get(
                        'charge_type') == 'gratuity':
                        try:
                            grat_row = float(self.charges_table.item(
                                row_idx, 2).text().replace(
                                    '$', '').replace(',', ''))
                        except Exception:
                            pass
                if grat_row is not None:
                    if hasattr(self, 'dp_gratuity'):
                        self.dp_gratuity.setText(f"${grat_row:.2f}")
                    # If approved_gratuity was equal to the old billed amount,
                    # keep it in sync
                    if hasattr(self, 'dp_approved_gratuity'):
                        prev_billed_text = (
                            self.dp_gratuity.text()
                            .replace('$', '').replace(',', ''))
                        try:
                            if abs(self.dp_approved_gratuity.value() - \
                                   float(prev_billed_text or 0)) < 0.01:
                                self.dp_approved_gratuity.blockSignals(True)
                                self.dp_approved_gratuity.setValue(grat_row)
                                self.dp_approved_gratuity.blockSignals(False)
                        except Exception:
                            pass
                    self._recalculate_driver_pay()
            except Exception:
                pass
        except Exception as e:
            try:
                self.db.rollback()
            except Exception:
                pass
            print(f"❌ Error saving charges: {e}")
            raise

    def load_charter_routes(self, charter_id: int, cur):
        """Load routes from charter_routes table into UI"""
        try:
            def _extract_at_by_marker(note_text):
                note = str(note_text or "")
                lower = note.lower()
                if lower.startswith("[at_by:by]"):
                    return "by", note[len("[at_by:by]"):].lstrip()
                if lower.startswith("[at_by:at]"):
                    return "at", note[len("[at_by:at]"):].lstrip()
                return "at", note

            cur.execute(
                """
                SELECT cr.route_sequence,
                       cr.event_type_code,
                       cr.stop_time,
                       COALESCE(cr.address,
                           cr.pickup_location,
                           cr.dropoff_location) AS address,
                       cr.route_notes
                FROM charter_routes AS cr
                WHERE cr.charter_id = %s
                ORDER BY cr.route_sequence
                """,
                (charter_id,))

            events = cur.fetchall()

            # Reset to parent rows and clear any existing stops
            self._init_parent_routing()
            while self.route_table.rowCount() > 2:
                self.route_table.removeRow(2)

            if not events:
                # Fallback to charter-level pickup/dropoff fields (legacy LMS
                # data)

                def _to_qtime(t, fallback: QTime):
                    if isinstance(t, str):
                        qt = QTime.fromString(t[:5], "HH:mm")
                        return qt if qt.isValid() else fallback
                    if t:
                        try:
                            return QTime(t.hour, t.minute)
                        except Exception:
                            return fallback
                    return fallback

                def _set_parent_row_legacy(row_idx, address, stop_time, notes):
                    # Address
                    addr_item = self.route_table.item(
                        row_idx, 1) or QTableWidgetItem("")
                    addr_item.setText(str(address or ""))
                    self.route_table.setItem(row_idx, 1, addr_item)

                    # Keep parent rows editable via widgets.
                    self._set_route_at_by_widget(row_idx, "at")
                    fallback = (
                        self.base_time_from.time()
                        if row_idx == 0
                        else self.base_time_to.time()
                    )
                    self._set_route_time_widget(
                        row_idx, _to_qtime(stop_time, fallback)
                    )

                    # Notes
                    notes_item = self.route_table.item(
                        row_idx, 4) or QTableWidgetItem("")
                    notes_item.setText(str(notes or ""))
                    self.route_table.setItem(row_idx, 4, notes_item)

                try:
                    cur.execute("""
                        SELECT EXISTS (
                            SELECT 1
                            FROM information_schema.columns
                            WHERE table_schema = 'public'
                              AND table_name = 'charters'
                              AND column_name = 'dropoff_time'
                        )
                    """)
                    has_dropoff_time = bool(cur.fetchone()[0])
                    dropoff_time_select = (
                        "dropoff_time"
                        if has_dropoff_time
                        else "workshift_end::time")

                    cur.execute(
                        f"""
                        SELECT pickup_address, dropoff_address,
                        pickup_time, {dropoff_time_select}
                        FROM charters
                        WHERE charter_id = %s
                        """,
                        (charter_id,))
                    row = cur.fetchone()
                    if row:
                        (pickup_addr, dropoff_addr,
                         pickup_time, dropoff_time) = row
                        # Sanitize OLE epoch timestamps — LMS stored time-only
                        # as '1899-12-30 HH:MM:SS'
                        if (dropoff_addr and isinstance(
                            dropoff_addr, str)
                            and dropoff_addr.startswith("1899-12-30")):
                            dropoff_addr = None
                        _set_parent_row_legacy(0, pickup_addr, pickup_time, "")
                        _set_parent_row_legacy(
                            1, dropoff_addr, dropoff_time, "")
                        print(
                            f"✅ Loaded pickup/dropoff"
                            f" from charter for {charter_id}")
                    else:
                        print(f"ℹ️  No routes found for charter {charter_id}")
                except Exception:
                    print(f"ℹ️  No routes found for charter {charter_id}")
                self._sync_routing_from_pickup_dropoff_times()
                return

            def _to_qtime(t, fallback: QTime):
                if isinstance(t, str):
                    qt = QTime.fromString(t[:5], "HH:mm")
                    return qt if qt.isValid() else fallback
                if t:
                    try:
                        return QTime(t.hour, t.minute)
                    except Exception:
                        return fallback
                return fallback

            def _set_parent_row(row_idx, address, stop_time, notes, at_by="at"):
                # Address
                addr_item = self.route_table.item(
                    row_idx, 1) or QTableWidgetItem("")
                addr_item.setText(str(address or ""))
                self.route_table.setItem(row_idx, 1, addr_item)

                self._set_route_at_by_widget(row_idx, at_by)
                fallback = (
                    self.base_time_from.time()
                    if row_idx == 0
                    else self.base_time_to.time()
                )
                self._set_route_time_widget(
                    row_idx, _to_qtime(stop_time, fallback)
                )

                # Notes
                notes_item = self.route_table.item(
                    row_idx, 4) or QTableWidgetItem("")
                notes_item.setText(str(notes or ""))
                self.route_table.setItem(row_idx, 4, notes_item)

            # Populate first and last routes into parent rows
            (first_seq, first_code, first_time,
             first_addr, first_notes) = events[0]

            loaded_out_of_town = first_code in (
                "depart_red_deer",
                "leave_red_deer",
            )
            if hasattr(self, 'out_of_town_checkbox'):
                self.out_of_town_checkbox.blockSignals(True)
                self.out_of_town_checkbox.setChecked(loaded_out_of_town)
                self.out_of_town_checkbox.blockSignals(False)
                self.handle_out_of_town_routing(loaded_out_of_town)

            first_at_by, first_clean_notes = _extract_at_by_marker(first_notes)
            _set_parent_row(0, first_addr, first_time, first_clean_notes, first_at_by)

            if len(events) > 1:
                (last_seq, last_code, last_time,
                 last_addr, last_notes) = events[-1]
                last_at_by, last_clean_notes = _extract_at_by_marker(last_notes)
                _set_parent_row(1, last_addr, last_time, last_clean_notes, last_at_by)

            # Populate middle route events as stop rows
            for _seq, event_code, stop_time, address, notes in events[1:-1]:
                self.add_route_line()
                row_idx = (
                    self.route_table.rowCount() - 2)  # before last parent
                at_by, clean_notes = _extract_at_by_marker(notes)

                # Event type combo
                combo = self.route_table.cellWidget(row_idx, 0)
                if combo and event_code:
                    idx = combo.findData(event_code)
                    if idx >= 0:
                        combo.setCurrentIndex(idx)

                # Address
                addr_item = self.route_table.item(
                    row_idx, 1) or QTableWidgetItem("")
                addr_item.setText(str(address or ""))
                self.route_table.setItem(row_idx, 1, addr_item)

                self._set_route_at_by_widget(row_idx, at_by)

                # Time widget
                time_edit = self.route_table.cellWidget(row_idx, 3)
                if time_edit and stop_time:
                    try:
                        if isinstance(stop_time, str):
                            qt = QTime.fromString(stop_time[:5], "HH:mm")
                        else:
                            qt = QTime(stop_time.hour, stop_time.minute)
                        if qt.isValid():
                            time_edit.setTime(qt)
                    except Exception:
                        pass

                # Notes
                notes_item = self.route_table.item(
                    row_idx, 4) or QTableWidgetItem("")
                notes_item.setText(str(clean_notes or ""))
                self.route_table.setItem(row_idx, 4, notes_item)

            print(f"✅ Loaded {len(events)} route events")
        except Exception as e:
            try:
                self.db.rollback()
            except Exception:
                pass
            print(f"❌ Error loading routes: {e}")

    def _recalculate_driver_pay(self):
        """Recalculate and display total driver pay = approved_hours *
        hourly_rate + approved_gratuity."""
        try:
            approved = self.dp_approved_hours.value() if hasattr(
                self, 'dp_approved_hours') else 0.0
            rate = (
                self.dp_hourly_rate.value()
                if hasattr(self, 'dp_hourly_rate') else 0.0)
            gratuity = self.dp_approved_gratuity.value() if hasattr(
                self, 'dp_approved_gratuity') else 0.0
            total = round(approved * rate + gratuity, 2)
            if hasattr(self, 'dp_total_pay'):
                self.dp_total_pay.setText(f"${total:,.2f}")
        except Exception:
            pass

    def _load_driver_pay(self, charter_data: dict):
        """Populate Driver Pay panel from a dict of charter DB columns."""
        try:
            calc_h      = charter_data.get('calculated_hours')
            appr_h      = charter_data.get('approved_hours')
            hourly      = charter_data.get('driver_hourly_rate')
            # from charges — read-only display
            billed_grat = charter_data.get('driver_gratuity')
            appr_grat   = charter_data.get(
                'approved_gratuity')   # dispatcher-set — editable

            if hasattr(self, 'dp_calculated_hours'):
                self.dp_calculated_hours.setText(
                    f"{float(calc_h):.2f}" if calc_h else "")

            if hasattr(self, 'dp_approved_hours'):
                self.dp_approved_hours.blockSignals(True)
                self.dp_approved_hours.setValue(
                    float(appr_h) if appr_h else 0.0)
                self.dp_approved_hours.blockSignals(False)

            if hasattr(self, 'dp_hourly_rate'):
                self.dp_hourly_rate.blockSignals(True)
                self.dp_hourly_rate.setValue(float(hourly) if hourly else 0.0)
                self.dp_hourly_rate.blockSignals(False)

            if hasattr(self, 'dp_gratuity'):
                self.dp_gratuity.setText(
                    f"${float(billed_grat):.2f}" if billed_grat else "$0.00")

            if hasattr(self, 'dp_approved_gratuity'):
                # Default approved = billed if not yet set separately
                effective = appr_grat if appr_grat is not None else billed_grat
                self.dp_approved_gratuity.blockSignals(True)
                self.dp_approved_gratuity.setValue(
                    float(effective) if effective else 0.0)
                self.dp_approved_gratuity.blockSignals(False)

            self._recalculate_driver_pay()
        except Exception as e:
            print(f"❌ Error loading driver pay panel: {e}")

    def _load_charter_payments(self, reserve_number: str):
        """Populate the payments_table from charter_payments
        (fallback: payments).
        Cols: Type(0) | Date Paid(1) | Amount(2) | Method(3) | Notes(4) | GL Code(5)
        """
        try:
            self.payments_table.setRowCount(0)
            if not reserve_number:
                return

            charter_id = None
            if getattr(self, 'charter_id', None):
                charter_id = str(self.charter_id)

            cur = self.db.get_cursor()
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema='public'
                  AND table_name='charter_payments'
                  AND column_name='gl_code'
                """
            )
            has_gl_code_column = bool(cur.fetchone())

            if has_gl_code_column:
                cur.execute("""
                    SELECT id, amount, payment_method, payment_date,
                           COALESCE(payment_key, ''), COALESCE(gl_code, '')
                    FROM charter_payments
                    WHERE charter_id = %s OR charter_id = %s
                    ORDER BY payment_date NULLS LAST, payment_id
                """, (reserve_number, charter_id or ''))
            else:
                cur.execute("""
                    SELECT id, amount, payment_method, payment_date,
                           COALESCE(payment_key, ''), ''::text
                    FROM charter_payments
                    WHERE charter_id = %s OR charter_id = %s
                    ORDER BY payment_date NULLS LAST, payment_id
                """, (reserve_number, charter_id or ''))
            rows = cur.fetchall()

            # Legacy fallback for records stored only in payments
            if not rows:
                cur.execute("""
                      SELECT NULL::int AS id, amount, payment_method, payment_date,
                          COALESCE(reference_number, notes, ''), ''::text
                    FROM payments
                    WHERE reserve_number = %s OR charter_id = %s
                    ORDER BY payment_date NULLS LAST, payment_id
                """, (reserve_number, self.charter_id))
                rows = cur.fetchall()

            cur.close()

            self._loading_payments = True
            for payment_row_id, amount, method, pay_date, payment_note, gl_code in rows:
                r = self.payments_table.rowCount()
                self.payments_table.insertRow(r)
                # Classify type
                m = (method or "").lower()
                if m in ("retainer", "nrr"):
                    pay_type = "NRR Retainer"
                elif m == "deposit":
                    pay_type = "Deposit"
                elif m == "bank_transfer":
                    pay_type = "Bank Transfer"
                elif m == "credit_card":
                    pay_type = "Credit Card"
                elif m == "etransfer":
                    pay_type = "E-Transfer"
                elif m == "debit_card":
                    pay_type = "Debit"
                elif m == "trade":
                    pay_type = "Trade of Services"
                elif m in ("promo", "promotional"):
                    pay_type = "Promotional Credit"
                elif m in ("refund", "credit"):
                    pay_type = "Refund"
                else:
                    pay_type = "Payment"
                date_str = pay_date.strftime("%Y-%m-%d") if pay_date else ""

                note_text = payment_note or ""
                gl_text = gl_code or ""
                if not gl_text and note_text.startswith("[GL:"):
                    end_idx = note_text.find("]")
                    if end_idx > 4:
                        gl_text = note_text[4:end_idx].strip()
                        note_text = note_text[end_idx + 1:].strip()

                type_item = QTableWidgetItem(pay_type)
                if payment_row_id is not None:
                    type_item.setData(Qt.ItemDataRole.UserRole, int(payment_row_id))
                self.payments_table.setItem(r, 0, type_item)
                self.payments_table.setItem(r, 1, QTableWidgetItem(date_str))
                self.payments_table.setItem(
                    r, 2, QTableWidgetItem(f"${float(amount):.2f}"))
                self.payments_table.setItem(
                    r, 3, QTableWidgetItem(method or "unknown"))
                self.payments_table.setItem(
                    r, 4, QTableWidgetItem(note_text))
                self.payments_table.setItem(
                    r, 5, QTableWidgetItem(gl_text))

            self._sync_nrr_received_from_payments_table()

            self._loading_payments = False
            self._payments_dirty = False

            print(
                f"✅ Loaded {len(rows)} payments for reserve #{reserve_number}")
        except Exception as e:
            print(f"❌ Error loading charter payments: {e}")

    def load_charter_charges(self, charter_id: int, cur):
        """Load charges from charter_charges table into UI"""
        import re
        try:
            cur.execute(
                """
                SELECT description, amount, rate, sequence, charge_type
                FROM charter_charges
                WHERE charter_id = %s
                ORDER BY sequence
                """,
                (charter_id,))

            rows = cur.fetchall()

            self.charges_table.setRowCount(0)
            charter_base_amount = None
            gratuity_amount = None
            gratuity_percent = None

            for description, amount, rate, _sequence, charge_type in rows:
                (base_desc, meta_type,
                 meta_value) = self._parse_description_metadata(
                    description or "")
                calc_type = meta_type or "Fixed"
                # Use embedded metadata value if present, else use amount
                value = meta_value if meta_value is not None else (
                    float(amount) if amount is not None else 0.0)
                self.add_charge_line(
                    description=base_desc,
                    calc_type=calc_type,
                    value=value,
                    charge_type=charge_type or "service")

                desc_lower = (base_desc or "").lower()
                amount_value = float(amount or 0.0)
                if charter_base_amount is None and (
                    charge_type == "service"
                    or "service fee" in desc_lower
                    or "charter charge" in desc_lower
                ):
                    charter_base_amount = amount_value

                if charge_type == "gratuity" or "gratuity" in desc_lower:
                    gratuity_amount = amount_value
                    if meta_type == "Percent" and meta_value is not None:
                        gratuity_percent = float(meta_value)
                    else:
                        percent_match = re.search(
                            r"(\d+(?:\.\d+)?)%", base_desc or "")
                        if percent_match:
                            gratuity_percent = float(percent_match.group(1))

            if (gratuity_amount is not None
                    and gratuity_percent is None
                    and charter_base_amount not in (
                    None, 0)):
                gratuity_percent = round(
                    (gratuity_amount / charter_base_amount) * 100.0, 1)

            if hasattr(self, 'gratuity_checkbox'):
                self.gratuity_checkbox.blockSignals(True)
                self.gratuity_checkbox.setChecked(gratuity_amount is not None)
                self.gratuity_checkbox.blockSignals(False)

            if gratuity_percent is not None and hasattr(
                self, 'gratuity_percent_input'):
                self.gratuity_percent_input.blockSignals(True)
                self.gratuity_percent_input.setValue(gratuity_percent)
                self.gratuity_percent_input.blockSignals(False)

            self.recalculate_totals()
            print(f"✅ Loaded {self.charges_table.rowCount()} charges")
        except Exception as e:
            try:
                self.db.rollback()
            except Exception:
                pass
            print(f"❌ Error loading charges: {e}")

    def load_charter_beverages(self, charter_id: int, cur):
        """
        Load saved beverages from charter_beverages table (SNAPSHOT DATA)
        Populates the beverage cart so user can edit if needed
        Shows locked prices but allows quantity adjustments
        """
        try:
            cur.execute("""
                SELECT id, item_name, quantity,
                unit_price_charged, unit_our_cost,
                       deposit_per_unit, line_amount_charged, line_cost, notes
                FROM charter_beverages
                WHERE charter_id = %s
                ORDER BY created_at
            """, (charter_id,))

            beverages = cur.fetchall()
            if not beverages:
                print(f"ℹ️  No beverages saved for charter {charter_id}")
                return

            # Store as beverage_cart_data for access in open_beverage_lookup()
            items = []
            total_charged = 0.0
            total_cost = 0.0
            total_deposit = 0.0

            for (bev_id, item_name, qty, unit_price, unit_cost,
                 deposit, line_total_charged, line_cost, notes) in beverages:
                items.append({
                    'id': bev_id,
                    'item_name': item_name,
                    'quantity': qty,
                    'unit_price_charged': unit_price,
                    'unit_our_cost': unit_cost,
                    'deposit_per_unit': deposit or 0.0,
                    'line_amount_charged': line_total_charged,
                    'line_cost': line_cost,
                    'notes': notes})
                total_charged += line_total_charged or 0.0
                total_cost += line_cost or 0.0
                total_deposit += (deposit or 0.0) * qty

            self.beverage_cart_data = {
                'items': items,
                'total_charged': total_charged,
                'total_cost': total_cost,
                'total_deposit': total_deposit,
                'gst_amount': (
                    GSTCalculator.calculate_gst(total_charged)[0]
                    if total_charged else 0.0),
                'net_amount': (
                    GSTCalculator.calculate_gst(total_charged)[1]
                    if total_charged else 0.0)}

            # Display beverages in a summary view
            print(f"\n🍷 SAVED BEVERAGES FOR CHARTER {charter_id}:")
            print("─" * 80)
            print(f"{'Item':<40} {'Qty':<5} {'Unit Price':<12} {'Total':<12}")
            print("─" * 80)

            for item in items:
                print(
                    f"{item['item_name']:<40}"
                    f" {item['quantity']:<5}"
                    f" ${item['unit_price_charged']:<11.2f}"
                    f" ${item['line_amount_charged']:<11.2f}")

            print("─" * 80)
            print(f"Subtotal: ${self.beverage_cart_data['net_amount']:,.2f}")
            print(f"GST (5%): ${self.beverage_cart_data['gst_amount']:,.2f}")
            print(f"Total: ${self.beverage_cart_data['total_charged']:,.2f}")
            print(f"✅ Loaded {len(beverages)} beverage item(s)")
            print(
                "💡 Tip: Click 'Edit Beverages' button"
                " to modify quantities or items\n")

        except Exception as e:
            try:
                self.db.rollback()
            except Exception:
                pass
            print(f"❌ Error loading beverages: {e}")

    # =========================================================================
    # RUN SHEET PDF (Print Run Sheet / Blank Run Sheet)
    # =========================================================================

    def _gather_run_sheet_data(self):
        """Collect current form data into a dict for generate_charter_pdf()."""
        customer_data = self.customer_widget.get_customer_data()

        # ── Charter / date / time ──────────────────────────────────────────
        reserve_number = customer_data.get("reserve_number") or ""
        charter_date = ""
        if hasattr(self, "charter_date_from"):
            charter_date = self.charter_date_from.date().toString("yyyy-MM-dd")

        pickup_time = ""
        if hasattr(self, "base_time_from"):
            pickup_time = self.base_time_from.time().toString("HH:mm")

        dropoff_time = ""
        if hasattr(self, "base_time_to"):
            dropoff_time = self.base_time_to.time().toString("HH:mm")

        status = ""
        if hasattr(self, "charter_status_combo"):
            status = self.charter_status_combo.currentText()

        charter_type = ""
        if hasattr(self, "charter_type_combo"):
            charter_type = self.charter_type_combo.currentText()

        quoted_hours = 0.0
        if hasattr(self, "quoted_hours_input"):
            quoted_hours = float(self.quoted_hours_input.value())

        passenger_load = 0
        if hasattr(self, "num_passengers"):
            passenger_load = int(self.num_passengers.value())

        # ── Vehicle / Driver ──────────────────────────────────────────────
        vehicle_type_requested = ""
        if hasattr(self, "vehicle_type_requested_combo"):
            vehicle_type_requested = (
                self.vehicle_type_requested_combo.currentText())

        vehicle_id = ""
        if hasattr(self, "vehicle_combo"):
            vehicle_id = self.vehicle_combo.currentText()

        driver_name = ""
        employee_number = ""
        if hasattr(self, "driver_combo"):
            driver_name = self.driver_combo.currentText()
            emp_id = self.driver_combo.currentData()
            if emp_id:
                try:
                    cur = self.db.get_cursor()
                    cur.execute(
                        "SELECT employee_number FROM employees "
                        "WHERE employee_id = %s",
                        (emp_id,))
                    row = cur.fetchone()
                    if row:
                        employee_number = str(row[0] or "")
                except Exception:
                    pass

        # ── Client info ───────────────────────────────────────────────────
        client_name = customer_data.get("client_name") or ""
        address_raw = customer_data.get("address") or ""
        phone = customer_data.get("phone") or ""
        email = customer_data.get("email") or ""

        # ── Notes ─────────────────────────────────────────────────────────
        notes = ""
        if hasattr(self, "client_notes_input"):
            notes = self.client_notes_input.toPlainText()
        if not notes and hasattr(self, "dispatcher_notes_input"):
            notes = self.dispatcher_notes_input.toPlainText()

        # ── Routes ────────────────────────────────────────────────────────
        routes = []
        if hasattr(self, "route_table"):
            for row in range(self.route_table.rowCount()):
                # Col 0: Event type (QComboBox or QTableWidgetItem)
                event_widget = self.route_table.cellWidget(row, 0)
                if event_widget and hasattr(event_widget, "currentText"):
                    event_type_code = event_widget.currentText()
                else:
                    item0 = self.route_table.item(row, 0)
                    event_type_code = item0.text() if item0 else ""

                # Col 1: Address
                item1 = self.route_table.item(row, 1)
                address = item1.text() if item1 else ""

                # Col 2: At/By (QComboBox or QTableWidgetItem)
                ab_widget = self.route_table.cellWidget(row, 2)
                if ab_widget and hasattr(ab_widget, "currentText"):
                    at_by = ab_widget.currentText()
                else:
                    item2 = self.route_table.item(row, 2)
                    at_by = item2.text() if item2 else "at"

                # Col 3: Time (QTimeEdit or QTableWidgetItem)
                time_widget = self.route_table.cellWidget(row, 3)
                if time_widget and hasattr(time_widget, "time"):
                    stop_time = time_widget.time().toString("HH:mm")
                else:
                    item3 = self.route_table.item(row, 3)
                    stop_time = item3.text() if item3 else ""

                # Col 4: Notes
                item4 = self.route_table.item(row, 4)
                route_notes = item4.text() if item4 else ""

                if address or stop_time:
                    routes.append({
                        "event_type_code": event_type_code,
                        "address": address,
                        "at_by": at_by,
                        "stop_time": stop_time,
                        "route_notes": route_notes,
                    })

        # ── Charges ───────────────────────────────────────────────────────
        charges = []
        if hasattr(self, "charges_table"):
            for row in range(self.charges_table.rowCount()):
                desc_item = self.charges_table.item(row, 0)
                total_item = self.charges_table.item(row, 2)
                if desc_item and total_item:
                    try:
                        amount = float(
                            total_item.text().replace("$", "").replace(",", "")
                        )
                    except Exception:
                        amount = 0.0
                    charges.append({
                        "description": desc_item.text(),
                        "amount": amount,
                    })

        # ── Totals ────────────────────────────────────────────────────────
        total_amount_due = 0.0
        if hasattr(self, "gross_total_display"):
            try:
                total_amount_due = float(
                    self.gross_total_display.text()
                    .replace("$", "").replace(",", "").split()[0]
                )
            except Exception:
                pass

        nrr_amount = 0.0
        if hasattr(self, "nrr_received"):
            nrr_amount = float(self.nrr_received.value())

        total_payments = 0.0
        if hasattr(self, "payments_table"):
            for row in range(self.payments_table.rowCount()):
                amt_item = self.payments_table.item(row, 2)
                if amt_item:
                    try:
                        total_payments += float(
                            amt_item.text().replace("$", "").replace(",", "")
                        )
                    except Exception:
                        pass

        # ── Beverages ─────────────────────────────────────────────────────
        beverages = []
        bev_items = (self.beverage_cart_data or {}).get("items") or []
        for item in bev_items:
            beverages.append({
                "item_name": (
                    item.get("name") or item.get("item_name") or ""),
                "quantity": int(item.get("quantity") or 1),
            })

        # ── HOS last 14 days (for CDDL grid) ─────────────────────────────
        hos_records = []
        if hasattr(self, "hos_table"):
            max_days = min(14, self.hos_table.columnCount())
            for col in range(max_days):
                off_item = self.hos_table.item(0, col)
                on_item = self.hos_table.item(1, col)
                total_item = self.hos_table.item(2, col)
                hos_records.append(
                    {
                        "day": str(col + 1),
                        "off_duty": off_item.text().strip() if off_item else "-",
                        "on_duty": on_item.text().strip() if on_item else "-",
                        "total_24h": total_item.text().strip() if total_item else "-",
                    }
                )

        # ── Odometer (from DB if charter is saved) ────────────────────────
        odometer_start = ""
        odometer_end = ""
        if self.charter_id:
            try:
                cur = self.db.get_cursor()
                cur.execute(
                    "SELECT odometer_start, odometer_end FROM charters "
                    "WHERE charter_id = %s",
                    (self.charter_id,),
                )
                odo_row = cur.fetchone()
                if odo_row:
                    odometer_start = str(odo_row[0] or "")
                    odometer_end = str(odo_row[1] or "")
            except Exception:
                pass

        return {
            "reserve_number": reserve_number,
            "charter_date": charter_date,
            "pickup_time": pickup_time,
            "dropoff_time": dropoff_time,
            "status": status,
            "charter_type": charter_type,
            "quoted_hours": quoted_hours,
            "passenger_load": passenger_load,
            "vehicle_type_requested": vehicle_type_requested,
            "vehicle_id": vehicle_id,
            "vehicle_number": vehicle_id,
            "driver_name": driver_name,
            "employee_number": employee_number,
            "workshift_start": pickup_time,
            "client_name": client_name,
            "address_line1": address_raw,
            "phone": phone,
            "email": email,
            "notes": notes,
            "routes": routes,
            "charges": charges,
            "beverages": beverages,
            "hos_records": hos_records,
            "total_amount_due": total_amount_due,
            "nrr_amount": nrr_amount,
            "total_paid": total_payments,
            "odometer_start": odometer_start,
            "odometer_end": odometer_end,
        }

    def _open_pdf_bytes(self, pdf_bytes, filename="run_sheet.pdf"):
        """Write PDF bytes to a temp file and open with the system viewer."""
        import tempfile
        import subprocess
        with tempfile.NamedTemporaryFile(
                delete=False, suffix=".pdf",
                prefix=filename.replace(".pdf", "_")) as f:
            f.write(pdf_bytes)
            tmp_path = f.name
        subprocess.Popen(
            ["cmd", "/c", "start", "", tmp_path],
            shell=False,
            creationflags=0x00000008,  # DETACHED_PROCESS
        )

    def print_run_sheet(self):
        """Generate and open run sheet PDF filled with current charter data."""
        import sys
        import os
        if not self.charter_id:
            QMessageBox.warning(
                self, "Warning",
                "Please save the charter first before printing the run sheet.")
            return
        try:
            # Add project root to path so we can import pdf_generator
            proj_root = os.path.abspath(
                os.path.join(os.path.dirname(__file__), os.pardir))
            if proj_root not in sys.path:
                sys.path.insert(0, proj_root)
            from modern_backend.app.services.pdf_generator import (
                generate_charter_pdf)
            data = self._gather_run_sheet_data()
            pdf_bytes = generate_charter_pdf(data)
            reserve = data.get("reserve_number") or str(self.charter_id)
            self._open_pdf_bytes(pdf_bytes, f"run_sheet_{reserve}.pdf")
        except Exception as e:
            import traceback
            QMessageBox.critical(
                self, "PDF Error",
                f"Failed to generate run sheet:\n{e}\n\n"
                f"{traceback.format_exc()[:500]}")

    def print_blank_run_sheet(self):
        """Generate and open a blank run sheet PDF for pencil fill."""
        import sys
        import os
        try:
            proj_root = os.path.abspath(
                os.path.join(os.path.dirname(__file__), os.pardir))
            if proj_root not in sys.path:
                sys.path.insert(0, proj_root)
            from modern_backend.app.services.pdf_generator import (
                generate_charter_pdf)
            # Minimal data — leaves all fields blank for manual fill
            data = {
                "reserve_number": "",
                "charter_date": "",
                "pickup_time": "",
                "dropoff_time": "",
                "status": "",
                "charter_type": "",
                "quoted_hours": None,
                "passenger_load": None,
                "vehicle_type_requested": "",
                "vehicle_id": "",
                "vehicle_number": "",
                "driver_name": "",
                "employee_number": "",
                "workshift_start": "",
                "client_name": "",
                "address_line1": "",
                "phone": "",
                "email": "",
                "notes": "",
                "routes": [],
                "charges": [],
                "beverages": [],
                "total_amount_due": 0.0,
                "nrr_amount": 0.0,
                "total_paid": 0.0,
            }
            pdf_bytes = generate_charter_pdf(data)
            self._open_pdf_bytes(pdf_bytes, "run_sheet_blank.pdf")
        except Exception as e:
            import traceback
            QMessageBox.critical(
                self, "PDF Error",
                f"Failed to generate blank run sheet:\n{e}\n\n"
                f"{traceback.format_exc()[:500]}")

