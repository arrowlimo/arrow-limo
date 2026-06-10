"""
Dispatch Management Widget
Simple booking list view - drill-down to full charter form
Year-filtered lazy loading to avoid loading all 18k+ charters at once.
"""

import logging

from common_widgets import StandardDateEdit
from db_error_handling import DatabaseContext
from PyQt6.QtCore import QDate, QSettings, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from usage_telemetry import UsageTelemetry

logger = logging.getLogger(__name__)

# Default column widths
# Reserve#, Date, Client, Total Due, Total Paid, Balance Owing, Vehicle
# Dispatched,
# Driver, Status, Pax, Pu Time, Pickup, Do Time, Dropoff, Bev, Notes
_COL_WIDTHS = [
    90,
    95,
    180,
    100,
    100,
    110,
    110,
    130,
    85,
    45,
    65,
    195,
    65,
    155,
    45,
    160,
    30,   # CL (checklist)
]


class _LoadWorker(QThread):
    """Background thread: fetches charter rows for one year."""

    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, db, year) -> None:
        super().__init__()
        self.db = db
        self.year = year  # int or None (= all)

    def run(self) -> None:
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                if self.year is None:
                    where = ""
                    params = []
                else:
                    where = "WHERE EXTRACT(YEAR FROM c.charter_date)::int = %s"
                    params = [self.year]

                cur.execute(
                    f"""
                    SELECT
                        c.charter_id,
                        c.reserve_number,
                        c.charter_date::date,
                        COALESCE(
                            c.client_display_name, cl.company_name,
                            cl.client_name, 'Unknown'
                        ) as client_name,
                        COALESCE(c.total_amount_due, c.grand_total,
                        0) as total_due,
                        COALESCE(c.amount_paid, c.paid_amount,
                        0) as total_paid,
                        COALESCE(
                            c.balance_owing,
                            c.balance,
                            COALESCE(c.total_amount_due, c.grand_total,
                            0) - COALESCE(c.amount_paid, c.paid_amount, 0),
                            0
                        ) as balance_owing,
                        COALESCE(
                            v.vehicle_number, c.vehicle, ''
                        ) as vehicle_dispatched,
                        COALESCE(
                            e.full_name, e2.full_name, c.driver, ''
                        ) as driver,
                        COALESCE(
                            c.payment_status, c.status, 'Pending'
                        ) as status,
                        COALESCE(c.passenger_count, 0) as passengers,
                        TO_CHAR(c.pickup_time, 'HH24:MI') as pickup_time_fmt,
                        c.pickup_address,
                        TO_CHAR(
                            COALESCE(c.do_time, c.dropoff_time),
                            'HH24:MI'
                        ) as dropoff_time_fmt,
                        c.dropoff_address,
                        false as has_beverages,
                        COALESCE(
                            c.driver_notes, c.notes, c.vehicle_notes, ''
                        ) as driver_notes,
                        CASE
                            WHEN EXISTS (
                                SELECT 1
                                FROM driver_payroll p
                                WHERE p.reserve_number = c.reserve_number
                                  AND (
                                        c.charter_date IS NULL
                                     OR p.year = EXTRACT(YEAR FROM
                                     c.charter_date)::int
                                  )
                            ) THEN TRUE
                            ELSE FALSE
                        END AS in_payroll
                    FROM charters c
                    LEFT JOIN clients cl ON c.client_id = cl.client_id
                    LEFT JOIN employees e ON c.employee_id = e.employee_id
                    LEFT JOIN employees e2 ON c.assigned_driver_id =
                    e2.employee_id
                    LEFT JOIN vehicles v ON c.vehicle_id = v.vehicle_id
                    {where}
                    ORDER BY c.charter_date DESC
                """,
                    params,
                )
                rows = cur.fetchall()
            self.finished.emit(rows)
        except Exception as e:
            self.error.emit(str(e))


class _RecordPaymentDialog(QDialog):
    """Lightweight payment entry dialog launched from the dispatch board."""

    def __init__(self, reserve_number: str, current_balance: float, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Record Payment \u2014 {reserve_number}")
        self.setMinimumWidth(320)
        self.amount = 0.0
        self.method = "Cash"
        self.notes = ""

        layout = QFormLayout(self)
        self._amount_edit = QLineEdit()
        self._amount_edit.setPlaceholderText("0.00")
        layout.addRow(f"Amount  (balance ${current_balance:,.2f})", self._amount_edit)

        self._method_combo = QComboBox()
        self._method_combo.addItems(["Cash", "Debit", "Credit Card", "E-Transfer", "Cheque"])
        layout.addRow("Method", self._method_combo)

        self._notes_edit = QLineEdit()
        layout.addRow("Notes (optional)", self._notes_edit)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._validate_and_accept)
        btn_box.rejected.connect(self.reject)
        layout.addRow(btn_box)

    def _validate_and_accept(self) -> None:
        try:
            val = self._amount_edit.text().replace("$", "").replace(",", "").strip()
            self.amount = float(val)
            if self.amount <= 0:
                raise ValueError("Amount must be greater than zero.")
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Amount", str(e))
            return
        self.method = self._method_combo.currentText()
        self.notes = self._notes_edit.text().strip()
        self.accept()


class DispatchManagementWidget(QWidget):
    def __init__(self, db) -> None:
        super().__init__()
        self.db = db
        self.usage_telemetry = UsageTelemetry("alms_dispatch")
        self._last_filter_signature = None
        self.bookings_data = []
        self.displayed_bookings = []
        self._worker = None
        self.init_ui()
        self._load_year_list()
        self._trigger_load()

    # ------------------------------------------------------------------
    # UI CONSTRUCTION
    # ------------------------------------------------------------------
    def init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Row 1: action buttons + search + status + date
        row1 = QHBoxLayout()
        row1.setSpacing(6)

        new_btn = QPushButton("+ New Charter")
        new_btn.setFixedHeight(26)
        new_btn.clicked.connect(self.new_booking)
        row1.addWidget(new_btn)

        row1.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Client, vehicle, driver, address..."
        )
        self.search_input.setMinimumWidth(160)
        self.search_input.textChanged.connect(self.filter_bookings)
        row1.addWidget(self.search_input, 1)

        row1.addWidget(QLabel("Status:"))
        self.status_filter = QComboBox()
        self.status_filter.setMaximumWidth(130)
        self.status_filter.addItems(
            [
                "All",
                "Pending",
                "Assigned",
                "Active",
                "Completed",
                "In Payroll",
                "Not in Payroll",
            ]
        )
        self.status_filter.currentTextChanged.connect(self.filter_bookings)
        row1.addWidget(self.status_filter)

        row1.addWidget(QLabel("Date:"))
        self.date_filter = StandardDateEdit(prefer_month_text=True)
        self.date_filter.setCalendarPopup(True)
        self.date_filter.setDate(QDate.currentDate())
        self.date_filter.setMaximumWidth(115)
        self.date_filter.dateChanged.connect(self.filter_bookings)
        row1.addWidget(self.date_filter)

        today_btn = QPushButton("Today")
        today_btn.setFixedHeight(24)
        today_btn.clicked.connect(self._set_today_filter)
        row1.addWidget(today_btn)

        all_dates_btn = QPushButton("All Dates")
        all_dates_btn.setFixedHeight(24)
        all_dates_btn.clicked.connect(self._clear_date_filter)
        row1.addWidget(all_dates_btn)

        layout.addLayout(row1)

        # Row 2: year selector + count label + view buttons
        row2 = QHBoxLayout()
        row2.setSpacing(6)

        row2.addWidget(QLabel("Year:"))
        self.year_combo = QComboBox()
        self.year_combo.setMaximumWidth(90)
        self.year_combo.currentIndexChanged.connect(self._on_year_changed)
        row2.addWidget(self.year_combo)

        self.load_status_label = QLabel("Loading...")
        self.load_status_label.setStyleSheet("color: #888; font-size: 11px;")
        row2.addWidget(self.load_status_label)

        row2.addStretch()

        reset_btn = QPushButton("Reset View")
        reset_btn.setFixedHeight(24)
        reset_btn.setToolTip("Reset column widths to defaults")
        reset_btn.clicked.connect(self.reset_view)
        row2.addWidget(reset_btn)

        autofit_btn = QPushButton("Auto-fit")
        autofit_btn.setFixedHeight(24)
        autofit_btn.setToolTip("Auto-resize columns to content")
        autofit_btn.clicked.connect(self.autofit_columns)
        row2.addWidget(autofit_btn)

        layout.addLayout(row2)

        # Table
        self.bookings_table = QTableWidget()
        self.bookings_table.setColumnCount(17)
        self.bookings_table.setHorizontalHeaderLabels(
            [
                "Reserve #",
                "Date",
                "Client",
                "Total Due",
                "Total Paid",
                "Balance Owing",
                "Vehicle Dispatched",
                "Driver",
                "Status",
                "Pax",
                "Pu Time",
                "Pickup",
                "Do Time",
                "Dropoff",
                "Bev",
                "Notes",
                "CL",
            ]
        )

        # Always show both scrollbars
        self.bookings_table.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOn
        )
        self.bookings_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOn
        )
        self.bookings_table.setHorizontalScrollMode(
            QTableWidget.ScrollMode.ScrollPerPixel
        )
        self.bookings_table.setVerticalScrollMode(
            QTableWidget.ScrollMode.ScrollPerPixel
        )

        # Fixed row height prevents fullscreen squish
        self.bookings_table.verticalHeader().setDefaultSectionSize(24)
        self.bookings_table.verticalHeader().setMinimumSectionSize(22)
        self.bookings_table.verticalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Fixed
        )
        self.bookings_table.verticalHeader().setVisible(False)

        self.bookings_table.setSortingEnabled(True)
        self.bookings_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self.bookings_table.horizontalHeader().setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        _hdr = self.bookings_table.horizontalHeader()
        _hdr.customContextMenuRequested.connect(
            self.show_column_menu
        )

        self.bookings_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        self.bookings_table.itemDoubleClicked.connect(self.handle_double_click)
        self.bookings_table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.bookings_table.customContextMenuRequested.connect(
            self._show_row_context_menu
        )

        self.reset_view(silent=True)
        layout.addWidget(self.bookings_table)

        # Persist sort column/order across sessions
        self.bookings_table.horizontalHeader().sortIndicatorChanged.connect(
            self._save_sort
        )

        # Summary strip: totals for currently filtered rows
        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet(
            "font-size: 11px; color: #444; padding: 2px 4px;"
        )
        layout.addWidget(self.summary_label)

        # Keyboard shortcuts for power dispatch flow
        self.refresh_shortcut = QShortcut(QKeySequence("F5"), self)
        self.refresh_shortcut.activated.connect(self._trigger_load)

        self.search_shortcut = QShortcut(QKeySequence.StandardKey.Find, self)
        self.search_shortcut.activated.connect(self._focus_search)

        self.clear_filters_shortcut = QShortcut(QKeySequence("Esc"), self)
        self.clear_filters_shortcut.activated.connect(self._clear_filters)

        self.search_input.returnPressed.connect(self.filter_bookings)

        self._apply_styles()

    # ------------------------------------------------------------------
    # YEAR SELECTOR
    # ------------------------------------------------------------------
    def _load_year_list(self) -> None:
        """Populate year combo from years in charters table."""
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute("""
                    SELECT DISTINCT EXTRACT(YEAR FROM charter_date)::int AS yr
                    FROM charters
                    WHERE charter_date IS NOT NULL
                    ORDER BY yr DESC
                """)
                years = [row[0] for row in cur.fetchall()]
        except Exception:
            import datetime

            years = list(range(datetime.date.today().year, 2006, -1))

        self.year_combo.blockSignals(True)
        self.year_combo.clear()
        self.year_combo.addItem("All Years", None)
        for yr in years:
            self.year_combo.addItem(str(yr), yr)

        import datetime

        current_year = datetime.date.today().year
        idx = self.year_combo.findData(current_year)
        if idx >= 0:
            self.year_combo.setCurrentIndex(idx)
        self.year_combo.blockSignals(False)

    def _on_year_changed(self) -> None:
        self._trigger_load()

    def _trigger_load(self) -> None:
        """Start background load for the selected year."""
        year = self.year_combo.currentData()
        label = self.year_combo.currentText()
        self.usage_telemetry.track(
            "dispatch_load_started", {"year": year, "label": label}
        )
        self.load_status_label.setText(f"Loading {label}...")
        self.bookings_table.setRowCount(0)

        if self._worker and self._worker.isRunning():
            self._worker.finished.disconnect()
            self._worker.error.disconnect()
            self._worker.quit()
            self._worker.wait(500)  # prevent concurrent DB cursor use

        self._worker = _LoadWorker(self.db, year)
        self._worker.finished.connect(self._on_loaded)
        self._worker.error.connect(self._on_load_error)
        self._worker.start()

    def _on_loaded(self, rows) -> None:
        self.bookings_data = rows
        self.filter_bookings()
        year_label = self.year_combo.currentText()
        self.usage_telemetry.track(
            "dispatch_load_finished",
            {"year_label": year_label, "row_count": len(rows)},
        )
        self.load_status_label.setText(
            f"{len(rows):,} charters - {year_label}"
        )

    def _update_summary(
        self,
        bookings,
        search_text: str = "",
        status_filter: str = "All",
        apply_date: bool = False,
        date_str: str = "",
    ) -> None:
        """Update the summary strip with totals for displayed rows."""
        if not hasattr(self, "summary_label"):
            return
        total_due = total_paid = balance = 0.0
        n_open = 0
        for b in bookings:
            try:
                td = float(b[4] or 0)
                tp = float(b[5] or 0)
                bo = float(b[6] or 0) or round(td - tp, 2)
                total_due += td
                total_paid += tp
                balance += bo
                if bo > 0.01:
                    n_open += 1
            except Exception:
                pass
        n = len(bookings)
        active_filters = []
        if search_text:
            active_filters.append(f"search '{search_text}'")
        if status_filter != "All":
            active_filters.append(f"status {status_filter}")
        if apply_date:
            active_filters.append(f"date {date_str}")

        filter_text = (
            " | Filters: " + ", ".join(active_filters)
            if active_filters
            else ""
        )
        self.summary_label.setText(
            f"{n:,} shown │ Due: ${total_due:,.2f} │ "
            f"Paid: ${total_paid:,.2f} │ "
            f"Balance: ${balance:,.2f} │ "
            f"Open: {n_open}{filter_text}"
        )

    def _on_load_error(self, msg) -> None:
        self.load_status_label.setText("Load error - see log")
        logger.error(f"Dispatch board load error: {msg}")
        QMessageBox.warning(
            self, "Load Error", f"Failed to load charters:\n{msg}"
        )

    # ------------------------------------------------------------------
    # DISPLAY / FILTER
    # ------------------------------------------------------------------
    def display_bookings(self, bookings) -> None:
        self.displayed_bookings = list(bookings)
        self.bookings_table.setSortingEnabled(False)
        self.bookings_table.setRowCount(len(bookings))

        # Batch-load checklist completion state for all shown charter_ids
        charter_ids = [b[0] for b in bookings if b[0]]
        checklist_map = self._load_checklist_map(charter_ids)

        for row_idx, booking in enumerate(bookings):
            raw_dropoff = str(booking[14] or "")
            dropoff_display = (
                "" if raw_dropoff.startswith("1899-12-30") else raw_dropoff
            )

            try:
                total_due = float(booking[4] or 0)
            except Exception:
                total_due = 0.0
            try:
                total_paid = float(booking[5] or 0)
            except Exception:
                total_paid = 0.0
            try:
                balance_owing = float(booking[6] or 0)
            except Exception:
                balance_owing = round(total_due - total_paid, 2)

            # Format date with day-of-week for easier weekday planning
            raw_date = str(booking[2] or "")
            try:
                from datetime import date as _dt
                _d = _dt.fromisoformat(raw_date)
                date_display = f"{_d.strftime('%a')} {raw_date}"
            except Exception:
                date_display = raw_date

            cells = [
                str(booking[1] or ""),  # Reserve #
                date_display,           # Date (with day-of-week)
                str(booking[3] or ""),  # Client
                f"{total_due:,.2f}",  # Total Due
                f"{total_paid:,.2f}",  # Total Paid
                f"{balance_owing:,.2f}",  # Balance Owing
                str(booking[7] or ""),  # Vehicle Dispatched
                str(booking[8] or ""),  # Driver (blank if unassigned)
                str(booking[9] or "Pending"),  # Status
                str(booking[10] or ""),  # Pax
                str(booking[11] or ""),  # Pu Time
                str(booking[12] or ""),  # Pickup
                str(booking[13] or ""),  # Do Time
                dropoff_display,  # Dropoff
                "Y" if booking[15] else "",  # Bev
                str(booking[16] or ""),  # Notes
            ]

            in_payroll = bool(booking[17])
            row_bg = QColor("#c6efce") if in_payroll else QColor("#fff2cc")

            for col_idx, cell in enumerate(cells):
                item = QTableWidgetItem(cell)
                item.setBackground(row_bg)
                if col_idx == 8:
                    status = booking[9] or "Pending"
                    if status == "Active":
                        item.setForeground(QColor("#2e7d32"))
                    elif status == "Completed":
                        item.setForeground(QColor("#888"))
                    elif status == "Pending":
                        item.setForeground(QColor("#e65100"))

                # Make balance visually obvious: green when fully paid, red
                # when owing.
                if col_idx == 5:
                    if balance_owing > 0.009:
                        item.setBackground(QColor("#ffcdd2"))
                        item.setForeground(QColor("#b71c1c"))
                    elif balance_owing < -0.009:
                        item.setBackground(QColor("#fff9c4"))
                        item.setForeground(QColor("#7f6000"))
                    else:
                        item.setBackground(QColor("#c6efce"))
                        item.setForeground(QColor("#1b5e20"))

                self.bookings_table.setItem(row_idx, col_idx, item)

            # Checklist completion column (col 16)
            cl_state = checklist_map.get(booking[0])  # True=complete, False=partial, None=none
            if cl_state is True:
                cl_text, cl_tip = "\u2705", "Checklist complete"
            elif cl_state is False:
                cl_text, cl_tip = "\u25d1", "Checklist started but incomplete"
            else:
                cl_text, cl_tip = "", ""
            cl_item = QTableWidgetItem(cl_text)
            cl_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            cl_item.setToolTip(cl_tip)
            cl_item.setBackground(row_bg)
            self.bookings_table.setItem(row_idx, 16, cl_item)

        self.bookings_table.setSortingEnabled(True)
        self._restore_sort()

    def filter_bookings(self) -> None:
        search_text = self.search_input.text().lower().strip()
        status_filter = self.status_filter.currentText()

        try:
            from datetime import date as _date

            today_str = _date.today().isoformat()
            date_str = self.date_filter.date().toString("yyyy-MM-dd")
            apply_date = date_str != today_str
        except Exception:
            apply_date = False
            date_str = ""

        filtered = []
        for booking in self.bookings_data:
            if apply_date and str(booking[2] or "") != date_str:
                continue

            if search_text:
                haystack = " ".join(
                    [
                        str(booking[1] or ""),  # reserve_number
                        str(booking[3] or ""),  # client_name
                        str(booking[7] or ""),  # vehicle_dispatched
                        str(booking[8] or ""),  # driver
                        str(booking[12] or ""),  # pickup_address
                        str(booking[16] or ""),  # notes
                    ]
                ).lower()
                if search_text not in haystack:
                    continue

            if status_filter != "All":
                if status_filter == "In Payroll":
                    if not bool(booking[17]):
                        continue
                elif status_filter == "Not in Payroll":
                    if bool(booking[17]):
                        continue
                elif (
                    booking[9] or "Pending"
                ).lower() != status_filter.lower():
                    continue

            filtered.append(booking)

        signature = (
            search_text,
            status_filter,
            date_str if apply_date else "",
            len(filtered),
        )
        if signature != self._last_filter_signature:
            self.usage_telemetry.track(
                "dispatch_filters_changed",
                {
                    "search": search_text,
                    "status": status_filter,
                    "date": date_str if apply_date else "",
                    "result_count": len(filtered),
                },
            )
            self._last_filter_signature = signature

        self.display_bookings(filtered)
        self._update_summary(
            filtered,
            search_text=search_text,
            status_filter=status_filter,
            apply_date=apply_date,
            date_str=date_str,
        )

    def _set_today_filter(self) -> None:
        """Apply today's date filter and refresh the grid."""
        self.date_filter.setDate(QDate.currentDate())
        self.filter_bookings()

    def _clear_date_filter(self) -> None:
        """Clear date filter by resetting to today and forcing all rows."""
        # The widget uses "today means no explicit date filter" behavior.
        self.date_filter.setDate(QDate.currentDate())
        self.filter_bookings()

    def _focus_search(self) -> None:
        """Focus search input quickly for keyboard-first users."""
        self.search_input.setFocus()
        self.search_input.selectAll()

    def _clear_filters(self) -> None:
        """Clear active search/status filters without touching year selection."""
        focused = self.focusWidget()
        if focused and self.isAncestorOf(focused):
            self.search_input.clear()
            self.status_filter.setCurrentIndex(0)
            self.date_filter.setDate(QDate.currentDate())
            self.filter_bookings()

    def _apply_styles(self) -> None:
        """Apply cohesive visual styling for table-heavy dispatch workflow."""
        self.setStyleSheet(
            """
            QLineEdit, QComboBox, QDateEdit {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 4px 6px;
                background: #ffffff;
            }
            QPushButton {
                background-color: #0ea5e9;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 4px 10px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #0284c7;
            }
            QTableWidget {
                gridline-color: #e2e8f0;
                alternate-background-color: #f8fafc;
                selection-background-color: #dbeafe;
                selection-color: #0f172a;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
            }
            QHeaderView::section {
                background-color: #e2e8f0;
                color: #0f172a;
                padding: 4px;
                border: 0;
                border-right: 1px solid #cbd5e1;
                font-weight: 600;
            }
            """
        )
        self.bookings_table.setAlternatingRowColors(True)

    # ------------------------------------------------------------------
    # INTERACTION
    # ------------------------------------------------------------------
    def handle_double_click(self, item) -> None:
        row = item.row()
        if row < 0:
            return

        reserve_item = self.bookings_table.item(row, 0)
        if not reserve_item:
            return

        reserve_number = reserve_item.text().strip()
        if not reserve_number:
            return
        self.usage_telemetry.track(
            "dispatch_open_charter", {"reserve_number": reserve_number}
        )

        # Pull current row data by reserve from DB so drill-down is correct
        # even when
        # the table has been sorted/reordered by the user.
        charter_id = None
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT charter_id
                    FROM charters
                    WHERE reserve_number = %s
                    ORDER BY charter_id DESC
                    LIMIT 1
                    """,
                    (reserve_number,),
                )
                id_row = cur.fetchone()
                if id_row:
                    charter_id = id_row[0]
        except Exception as e:
            logger.error(
                f"Failed to resolve charter_id for reserve {reserve_number}:"
                f"{e}"
            )

        booking = None
        for candidate in self.displayed_bookings:
            if str(candidate[1] or "").strip() == reserve_number:
                booking = candidate
                break

        # Show pre-run checklist for Booked charters within 48 hours
        if charter_id and booking:
            try:
                from datetime import date
                charter_date = booking[2]
                charter_status = str(booking[9] or "").strip().lower()
                if charter_date and charter_status == "booked":
                    if isinstance(charter_date, str):
                        from datetime import datetime as _dt
                        charter_date = _dt.strptime(charter_date, "%Y-%m-%d").date()
                    days_away = (charter_date - date.today()).days
                    if 0 <= days_away <= 2:
                        from drill_down_widgets import PreRunChecklistDialog
                        chk = PreRunChecklistDialog(
                            self.db, charter_id=charter_id,
                            reserve_number=reserve_number, parent=self
                        )
                        chk.exec()
            except Exception as e:
                logger.warning(f"Pre-run checklist skipped: {e}")

        try:
            main_window = self.window()
            if hasattr(main_window, "dispatch_tabs_widget") and hasattr(
                main_window, "charter_form"
            ):
                charter_form = main_window.charter_form
                if booking and hasattr(
                    charter_form, "prefill_from_dispatch_row"
                ):
                    charter_form.prefill_from_dispatch_row(booking)

                main_window.dispatch_tabs_widget.setCurrentIndex(1)

                if hasattr(charter_form, "booking_tab_widget"):
                    charter_form.booking_tab_widget.setCurrentIndex(1)

                if charter_id and hasattr(charter_form, "load_charter_by_id"):
                    charter_form.load_charter_by_id(int(charter_id))
                elif hasattr(charter_form, "load_charter_by_reserve"):
                    charter_form.load_charter_by_reserve(reserve_number)
                return
        except Exception as e:
            logger.error(
                f"Failed to open in Run Charter tab, falling back: {e}"
            )

        try:
            from drill_down_widgets import CharterDetailDialog

            dialog = CharterDetailDialog(
                self.db, reserve_number=str(reserve_number), parent=self
            )
            dialog.exec()
            self._trigger_load()
        except Exception as e:
            logger.error(f"Failed to open charter details: {e}")
            QMessageBox.warning(
                self, "Error", f"Failed to open charter details: {e}"
            )

    def new_booking(self) -> None:
        try:
            from datetime import date, datetime

            from calendar_event_finder_dialog import CalendarEventFinderDialog
            from client_finder_dialog import ClientFinderDialog
            from main import CharterFormWidget

            calendar_dialog = CalendarEventFinderDialog(self.db, parent=self)
            if calendar_dialog.exec() != QDialog.DialogCode.Accepted:
                return

            event_data = calendar_dialog.selected_event
            client_id = calendar_dialog.selected_client_id
            client_name = calendar_dialog.selected_client_name

            if event_data and event_data.get("is_now"):
                client_dialog = ClientFinderDialog(self.db, parent=self)
                if client_dialog.exec() != QDialog.DialogCode.Accepted:
                    return
                client_id = client_dialog.selected_client_id
                client_name = client_dialog.selected_client_name
                event_data = {
                    "date": date.today(),
                    "time": datetime.now().time(),
                    "driver": None,
                    "vehicle": None,
                    "notes": None,
                }
            elif not event_data:
                client_dialog = ClientFinderDialog(self.db, parent=self)
                if client_dialog.exec() != QDialog.DialogCode.Accepted:
                    return
                client_id = client_dialog.selected_client_id
                client_name = client_dialog.selected_client_name
                event_data = None

            if not client_id:
                QMessageBox.warning(
                    self, "No Client", "Please select a client."
                )
                return

            dialog = QDialog(self)
            dialog.setWindowTitle(f"New Charter - {client_name}")
            dialog.setGeometry(100, 100, 1400, 800)
            dlg_layout = QVBoxLayout()
            charter_form = CharterFormWidget(
                self.db, charter_id=None, client_id=client_id
            )
            if event_data:
                self.prefill_charter_from_event(charter_form, event_data)
            charter_form.saved.connect(lambda: self.on_charter_saved(dialog))
            dlg_layout.addWidget(charter_form)
            dialog.setLayout(dlg_layout)
            dialog.exec()
            self._trigger_load()
        except Exception as e:
            logger.error(f"Failed to create charter: {e}")
            QMessageBox.critical(
                self, "Error", f"Failed to create charter: {e}"
            )

    def prefill_charter_from_event(self, charter_form, event_data) -> None:
        try:
            from PyQt6.QtCore import QDate, QTime

            if event_data.get("date"):
                d = event_data["date"]
                if hasattr(charter_form, "charter_date"):
                    charter_form.charter_date.setDate(
                        QDate(d.year, d.month, d.day)
                    )
            if event_data.get("time"):
                t = event_data["time"]
                if hasattr(charter_form, "pickup_time"):
                    charter_form.pickup_time.setTime(QTime(t.hour, t.minute))
            for field, attr in [
                ("driver", "driver_combo"),
                ("vehicle", "vehicle_combo"),
            ]:
                if event_data.get(field) and hasattr(charter_form, attr):
                    combo = getattr(charter_form, attr)
                    for i in range(combo.count()):
                        if event_data[field] in combo.itemText(i):
                            combo.setCurrentIndex(i)
                            break
            if event_data.get("notes") and hasattr(
                charter_form, "dispatcher_notes"
            ):
                charter_form.dispatcher_notes.setPlainText(event_data["notes"])
        except Exception as e:
            logger.warning("Error prefilling from event: %s", e)

    def on_charter_saved(self, dialog) -> None:
        dialog.accept()
        self._trigger_load()

    # ------------------------------------------------------------------
    # COLUMN / VIEW HELPERS
    # ------------------------------------------------------------------
    def show_column_menu(self, pos) -> None:
        menu = QMenu(self)
        menu.addAction("Show All Columns").triggered.connect(
            lambda: self.toggle_all_columns(True)
        )
        menu.addAction("Hide All Columns").triggered.connect(
            lambda: self.toggle_all_columns(False)
        )
        menu.addSeparator()
        for col in range(self.bookings_table.columnCount()):
            text = self.bookings_table.horizontalHeaderItem(col).text()
            action = menu.addAction(text)
            action.setCheckable(True)
            action.setChecked(not self.bookings_table.isColumnHidden(col))
            action.triggered.connect(
                lambda checked, c=col: self.bookings_table.setColumnHidden(
                    c, not checked
                )
            )
        menu.exec(self.bookings_table.horizontalHeader().mapToGlobal(pos))

    def toggle_all_columns(self, visible) -> None:
        for col in range(self.bookings_table.columnCount()):
            self.bookings_table.setColumnHidden(col, not visible)

    def reset_view(self, silent=False) -> None:
        for col in range(self.bookings_table.columnCount()):
            self.bookings_table.setColumnHidden(col, False)
            if col < len(_COL_WIDTHS):
                self.bookings_table.setColumnWidth(col, _COL_WIDTHS[col])
        if not silent:
            QMessageBox.information(
                self, "View Reset", "Column widths reset to defaults."
            )

    def _save_sort(self, col: int, order) -> None:
        s = QSettings("ArrowLimo", "DispatchWidget")
        s.setValue("sort_col", col)
        s.setValue("sort_order", int(order))

    def _restore_sort(self) -> None:
        s = QSettings("ArrowLimo", "DispatchWidget")
        col = s.value("sort_col", 1, type=int)
        order = Qt.SortOrder(s.value("sort_order", Qt.SortOrder.DescendingOrder.value, type=int))
        # Block the signal so saving doesn't fire while restoring
        hdr = self.bookings_table.horizontalHeader()
        hdr.blockSignals(True)
        hdr.setSortIndicator(col, order)
        self.bookings_table.sortItems(col, order)
        hdr.blockSignals(False)

    def _load_checklist_map(self, charter_ids: list) -> dict:
        """Batch-fetch checklist completion state. Returns {charter_id: True|False}."""
        if not charter_ids:
            return {}
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema='public' AND table_name='charter_checklists'
                """)
                if not cur.fetchone():
                    return {}
                placeholders = ','.join(['%s'] * len(charter_ids))
                cur.execute(
                    f"SELECT charter_id, "
                    f"(driver_confirmed AND vehicle_confirmed AND client_contacted AND deposit_received) AS complete "
                    f"FROM charter_checklists WHERE charter_id IN ({placeholders})",
                    charter_ids,
                )
                return {r[0]: bool(r[1]) for r in cur.fetchall()}
        except Exception:
            return {}

    def autofit_columns(self) -> None:
        self.bookings_table.resizeColumnsToContents()

    # ------------------------------------------------------------------
    # ROW CONTEXT MENU
    # ------------------------------------------------------------------
    def _show_row_context_menu(self, pos) -> None:
        row = self.bookings_table.rowAt(pos.y())
        if row < 0:
            return
        menu = QMenu(self)

        # Status submenu: quick status change without opening the full form
        status_menu = menu.addMenu("🟢 Set Status")
        for _s in ("Quote", "Pending", "Assigned", "Active", "Completed", "Cancelled"):
            _act = status_menu.addAction(_s)
            _act.triggered.connect(
                lambda checked=False, s=_s: self._quick_set_status(row, s)
            )

        menu.addSeparator()
        edit_act = menu.addAction("✏️  Edit Reserve Number...")
        edit_act.triggered.connect(lambda: self._edit_reserve_number(row))
        menu.exec(self.bookings_table.viewport().mapToGlobal(pos))

    def _record_payment(self, row: int) -> None:
        """Quick payment entry from the dispatch board context menu."""
        reserve_item = self.bookings_table.item(row, 0)
        if not reserve_item:
            return
        reserve_number = reserve_item.text().strip()
        try:
            balance_item = self.bookings_table.item(row, 5)
            current_balance = float(
                (balance_item.text() if balance_item else "0").replace(",", "")
            )
        except Exception:
            current_balance = 0.0

        dlg = _RecordPaymentDialog(reserve_number, current_balance, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    "UPDATE charters "
                    "SET amount_paid = COALESCE(amount_paid, 0) + %s, "
                    "    paid_amount = COALESCE(paid_amount, 0) + %s "
                    "WHERE reserve_number = %s",
                    (dlg.amount, dlg.amount, reserve_number),
                )
                # Also insert into charter_payments if table/columns exist
                cur.execute("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema='public' AND table_name='charter_payments'
                      AND column_name IN ('reserve_number','amount','payment_method','notes','payment_date')
                """)
                existing = {r[0] for r in cur.fetchall()}
                if 'reserve_number' in existing and 'amount' in existing:
                    from datetime import date as _date
                    cols = ['reserve_number', 'amount']
                    vals = [reserve_number, dlg.amount]
                    if 'payment_method' in existing:
                        cols.append('payment_method')
                        vals.append(dlg.method)
                    if 'payment_date' in existing:
                        cols.append('payment_date')
                        vals.append(_date.today())
                    if 'notes' in existing:
                        cols.append('notes')
                        vals.append(dlg.notes or None)
                    ph = ', '.join(['%s'] * len(vals))
                    cur.execute(
                        f"INSERT INTO charter_payments ({', '.join(cols)}) VALUES ({ph})",
                        vals,
                    )
            logger.info("Payment recorded: %s $%.2f %s", reserve_number, dlg.amount, dlg.method)
            self._trigger_load()
        except Exception as e:
            QMessageBox.critical(self, "Payment Error", str(e))

    def _quick_set_status(self, row: int, new_status: str) -> None:
        """Update charter status directly from the dispatch board context menu."""
        reserve_item = self.bookings_table.item(row, 0)
        if not reserve_item:
            return
        reserve_number = reserve_item.text().strip()
        if not reserve_number:
            return
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    "UPDATE charters SET status = %s, payment_status = %s "
                    "WHERE reserve_number = %s",
                    (new_status, new_status, reserve_number),
                )
            # Refresh just this row's status cell without full reload
            status_col = 8
            item = self.bookings_table.item(row, status_col)
            if item:
                item.setText(new_status)
                if new_status == "Active":
                    item.setForeground(QColor("#2e7d32"))
                elif new_status == "Completed":
                    item.setForeground(QColor("#888"))
                else:
                    item.setForeground(QColor("#e65100"))
            logger.info("Quick status set: %s → %s", reserve_number, new_status)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update status: {e}")

    # ------------------------------------------------------------------
    # EDIT RESERVE NUMBER
    # ------------------------------------------------------------------
    def _edit_reserve_number(self, row: int) -> None:
        """Open an inline dialog to rename the reserve_number for a charter."""
        reserve_item = self.bookings_table.item(row, 0)
        if not reserve_item:
            return
        current_reserve = reserve_item.text().strip()

        # Resolve charter_id for this row
        charter_id = None
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    "SELECT charter_id FROM charters "
                    "WHERE reserve_number = %s "
                    "ORDER BY charter_id DESC LIMIT 1",
                    (current_reserve,),
                )
                row_db = cur.fetchone()
                if row_db:
                    charter_id = row_db[0]
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not fetch charter: {e}")
            return

        if not charter_id:
            QMessageBox.warning(
                self, "Not Found",
                f"Could not find charter for reserve '{current_reserve}'.")
            return

        # ---- Build dialog ------------------------------------------------
        dlg = QDialog(self)
        dlg.setWindowTitle("Edit Reserve Number")
        dlg.setFixedWidth(340)
        dlg.setModal(True)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(8)

        info = QLabel(
            f"Charter ID: <b>{charter_id}</b>   "
            f"Current: <b>{current_reserve}</b>"
        )
        info.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(info)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        new_input = QLineEdit(current_reserve)
        new_input.setPlaceholderText("New reserve number")
        new_input.selectAll()
        form.addRow("New Reserve #:", new_input)
        layout.addLayout(form)

        status_lbl = QLabel("")
        status_lbl.setStyleSheet("font-size: 11px;")
        layout.addWidget(status_lbl)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = btn_box.button(QDialogButtonBox.StandardButton.Ok)
        ok_btn.setEnabled(False)
        layout.addWidget(btn_box)

        # ---- Validation -------------------------------------------------
        def _validate(text: str) -> None:
            text = text.strip()
            if not text:
                status_lbl.setText("⚠️  Enter a reserve number.")
                status_lbl.setStyleSheet("color: orange; font-size: 11px;")
                ok_btn.setEnabled(False)
                return
            if text == current_reserve:
                status_lbl.setText("")
                ok_btn.setEnabled(False)
                return
            # Check duplicate
            try:
                with DatabaseContext(self.db, auto_commit=False) as cur:
                    cur.execute(
                        "SELECT charter_id FROM charters "
                        "WHERE reserve_number = %s LIMIT 1",
                        (text,),
                    )
                    dup = cur.fetchone()
            except Exception:
                dup = None
            if dup:
                status_lbl.setText(
                    f"❌  Reserve '{text}' already exists "
                    f"(charter {dup[0]})."
                )
                status_lbl.setStyleSheet("color: red; font-size: 11px;")
                ok_btn.setEnabled(False)
            else:
                status_lbl.setText(f"✅  '{text}' is available.")
                status_lbl.setStyleSheet("color: green; font-size: 11px;")
                ok_btn.setEnabled(True)

        new_input.textChanged.connect(_validate)

        # Enter key triggers OK when enabled
        def _on_return() -> None:
            if ok_btn.isEnabled():
                dlg.accept()

        new_input.returnPressed.connect(_on_return)
        btn_box.accepted.connect(dlg.accept)
        btn_box.rejected.connect(dlg.reject)

        # Focus input after show
        QTimer.singleShot(0, new_input.setFocus)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        new_reserve = new_input.text().strip()
        if not new_reserve or new_reserve == current_reserve:
            return

        # ---- Persist change ----------------------------------------------
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    "UPDATE charters SET reserve_number = %s "
                    "WHERE charter_id = %s",
                    (new_reserve, charter_id),
                )
                # Also update driver_payroll references
                cur.execute(
                    "UPDATE driver_payroll SET reserve_number = %s "
                    "WHERE reserve_number = %s",
                    (new_reserve, current_reserve),
                )
        except Exception as e:
            QMessageBox.critical(
                self, "Save Failed", f"Could not update reserve number:\n{e}")
            return

        # Update table cell in-place and bookings_data cache
        reserve_item.setText(new_reserve)
        for booking in self.bookings_data:
            if str(booking[1] or "").strip() == current_reserve:
                # booking is a tuple — rebuild with new reserve_number
                lst = list(booking)
                lst[1] = new_reserve
                idx = self.bookings_data.index(booking)
                self.bookings_data[idx] = tuple(lst)
                break
        for booking in self.displayed_bookings:
            if str(booking[1] or "").strip() == current_reserve:
                lst = list(booking)
                lst[1] = new_reserve
                idx = self.displayed_bookings.index(booking)
                self.displayed_bookings[idx] = tuple(lst)
                break

        QMessageBox.information(
            self,
            "Updated",
            f"Reserve number changed:\n{current_reserve}  →  {new_reserve}",
        )
