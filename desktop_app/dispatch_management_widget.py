"""
Dispatch Management Widget
Simple booking list view - drill-down to full charter form
Year-filtered lazy loading to avoid loading all 18k+ charters at once.
"""

import logging
import os
from datetime import date, datetime

from common_widgets import StandardDateEdit
from db_connection import DatabaseConnection
from db_error_handling import DatabaseContext
from PyQt6.QtCore import QDate, QSettings, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QCheckBox,
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
    QRadioButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from psycopg2 import sql as pg_sql
from usage_telemetry import UsageTelemetry

logger = logging.getLogger(__name__)

# Default column widths
# Reserve#, Date, Day, Client, Total Due, Total Paid, Balance Owing, Vehicle
# Dispatched,
# Driver, Status, Pax, Pu Time, Pickup, Do Time, Dropoff, Bev, Notes
_COL_WIDTHS = [
    90,
    95,
    48,   # Day
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


class _NumericTableWidgetItem(QTableWidgetItem):
    """QTableWidgetItem that sorts using numeric value, not display text."""

    def __init__(self, display_text: str, numeric_value: float) -> None:
        super().__init__(display_text)
        self.setData(Qt.ItemDataRole.UserRole, float(numeric_value))

    def __lt__(self, other) -> bool:
        if isinstance(other, QTableWidgetItem):
            try:
                left = float(self.data(Qt.ItemDataRole.UserRole))
                right_raw = other.data(Qt.ItemDataRole.UserRole)
                if right_raw is None:
                    return super().__lt__(other)
                right = float(right_raw)
                return left < right
            except Exception:
                return super().__lt__(other)
        return super().__lt__(other)


class _DateTableWidgetItem(QTableWidgetItem):
    """QTableWidgetItem that displays MM/DD/YYYY but sorts by ISO date."""

    def __init__(self, display_text: str, iso_value: str) -> None:
        super().__init__(display_text)
        self.setData(Qt.ItemDataRole.UserRole, iso_value)

    def __lt__(self, other) -> bool:
        if isinstance(other, QTableWidgetItem):
            return str(self.data(Qt.ItemDataRole.UserRole) or "") < str(
                other.data(Qt.ItemDataRole.UserRole) or ""
            )
        return super().__lt__(other)


class _LoadWorker(QThread):
    """Background thread: fetches charter rows for one year."""

    loaded = pyqtSignal(list)
    load_error = pyqtSignal(str)

    def __init__(
        self,
        db_config,
        year,
        include_closed_cancelled=False,
        date_mode="forward",
        date_from=None,
        date_to=None,
    ) -> None:
        super().__init__()
        self.db_config = dict(db_config)
        self.year = year  # int or None (= all)
        self.include_closed_cancelled = bool(include_closed_cancelled)
        self.date_mode = date_mode
        self.date_from = date_from
        self.date_to = date_to

    def run(self) -> None:
        worker_db = None
        try:
            worker_db = DatabaseConnection(self.db_config)
            with DatabaseContext(worker_db, auto_commit=False) as cur:
                conditions = []
                params = []
                if self.year is not None:
                    conditions.append(
                        "c.charter_date >= %s AND c.charter_date < %s"
                    )
                    params.extend(
                        [
                            date(int(self.year), 1, 1),
                            date(int(self.year) + 1, 1, 1),
                        ]
                    )
                if self.date_mode == "forward" and self.date_from:
                    conditions.append("c.charter_date >= %s")
                    params.append(self.date_from)
                elif self.date_mode == "exact" and self.date_from:
                    conditions.append("c.charter_date = %s")
                    params.append(self.date_from)
                elif self.date_mode == "between" and self.date_from and self.date_to:
                    conditions.append("c.charter_date BETWEEN %s AND %s")
                    params.extend([self.date_from, self.date_to])
                if not self.include_closed_cancelled:
                    conditions.append(
                        "NOT (COALESCE(c.cancelled, FALSE) "
                        "OR lower(COALESCE(c.status, '')) IN "
                        "('closed', 'cancelled') "
                        "OR POSITION('cancel' IN lower(COALESCE(c.status, ''))) > 0)"
                    )
                where = "WHERE " + " AND ".join(conditions) if conditions else ""

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
                        COALESCE(c.grand_total, c.total_amount_due,
                        0) as total_due,
                        COALESCE(c.amount_paid, c.paid_amount,
                        0) as total_paid,
                        COALESCE(
                            c.balance_owing,
                            c.balance,
                            COALESCE(c.grand_total, c.total_amount_due,
                            0) - COALESCE(c.amount_paid, c.paid_amount, 0),
                            0
                        ) as balance_owing,
                        COALESCE(
                            v.vehicle_number, c.vehicle, ''
                        ) as vehicle_dispatched,
                        CASE
                            WHEN c.employee_id IS NULL
                             AND c.assigned_driver_id IS NULL THEN ''
                            ELSE COALESCE(
                                e.full_name, e2.full_name, c.driver, ''
                            )
                        END as driver,
                        COALESCE(c.status, 'Pending') as status,
                        COALESCE(c.passenger_count, 0) as passengers,
                        TO_CHAR(c.pickup_time, 'HH24:MI') as pickup_time_fmt,
                        c.pickup_address,
                        TO_CHAR(
                            COALESCE(c.do_time, c.dropoff_time),
                            'HH24:MI'
                        ) as dropoff_time_fmt,
                        c.dropoff_address,
                        EXISTS (
                            SELECT 1
                            FROM charter_beverages cb
                            WHERE cb.charter_id = c.charter_id
                        ) as has_beverages,
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
                        END AS in_payroll,
                        CASE
                            WHEN ABS(
                                COALESCE(c.grand_total, 0) -
                                COALESCE(c.total_amount_due, 0)
                            ) > 0.01 THEN TRUE
                            ELSE FALSE
                        END AS total_mismatch
                        ,COALESCE(c.cancelled, FALSE) AS is_cancelled
                        ,COALESCE(c.needs_review, FALSE) AS needs_review
                        ,COALESCE(c.nrr_amount, 0) AS nrr_amount
                        ,COALESCE(c.nrr_received, FALSE) AS nrr_received
                        ,(
                            COALESCE(c.charter_data, '{{}}'::jsonb)->>
                            'nrr_escrow_applied'
                        ) = 'true' AS nrr_escrow_applied
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
            self.loaded.emit(rows)
        except Exception as e:
            self.load_error.emit(str(e))
        finally:
            if worker_db is not None:
                worker_db.close()


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
        self._dispatch_settings = QSettings("ArrowLimo", "DesktopApp")
        self._restoring_dispatch_filters = False
        self._last_filter_signature = None
        self._date_filter_active = False
        self._date_filter_mode = "all"
        self._dispatch_trace_file = None
        self._dispatch_trace_enabled = str(os.getenv("ALMS_FREEZE_TRACE", "1")).strip().lower() not in {
            "0",
            "false",
            "no",
            "off",
        }
        self.bookings_data = []
        self.displayed_bookings = []
        self._worker = None
        self._pending_load_request = None
        self._date_reload_timer = QTimer(self)
        self._date_reload_timer.setSingleShot(True)
        self._date_reload_timer.setInterval(250)
        self._date_reload_timer.timeout.connect(self._trigger_load)
        self.init_ui()
        # Defer all DB calls so the widget renders before any network round-trips.
        # On remote PCs with cloud DB latency this prevents the tab from freezing
        # on open.
        QTimer.singleShot(0, self._deferred_dispatch_init)

    def _trace_dispatch_event(self, event_name: str, **fields) -> None:
        """Emit consistent dispatch-click trace lines for freeze diagnosis."""
        if not self._dispatch_trace_enabled:
            return
        try:
            parts = [f"event={event_name}"]
            for key, value in fields.items():
                parts.append(f"{key}={value}")
            logger.warning("[dispatch-freeze-trace] %s", " | ".join(parts))
        except Exception as _e:
            logger.debug("Suppressed: %s", _e)

    def _arm_dispatch_watchdog(self, label: str, timeout_seconds: int = 15) -> None:
        """Dump stack traces if the dispatch click path stalls."""
        if not self._dispatch_trace_enabled:
            return
        try:
            import faulthandler

            self._disarm_dispatch_watchdog()
            dump_path = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)),
                                     "charter_freeze_trace.log")
            self._dispatch_trace_file = open(dump_path, "a", encoding="utf-8")
            self._dispatch_trace_file.write(
                f"\n=== dispatch watchdog armed: {label} @ {datetime.now().isoformat()} ===\n"
            )
            self._dispatch_trace_file.flush()
            faulthandler.enable(file=self._dispatch_trace_file, all_threads=True)
            faulthandler.dump_traceback_later(
                timeout_seconds,
                repeat=False,
                file=self._dispatch_trace_file,
                exit=False,
            )
            self._trace_dispatch_event("watchdog_armed", label=label, timeout_s=timeout_seconds)
        except Exception as _e:
            logger.debug("Suppressed: %s", _e)

    def _disarm_dispatch_watchdog(self) -> None:
        try:
            import faulthandler

            faulthandler.cancel_dump_traceback_later()
        except Exception as _e:
            logger.debug("Suppressed: %s", _e)
        try:
            if self._dispatch_trace_file is not None:
                self._dispatch_trace_file.flush()
                self._dispatch_trace_file.close()
                self._dispatch_trace_file = None
        except Exception as _e:
            logger.debug("Suppressed: %s", _e)

    def _deferred_dispatch_init(self) -> None:
        """Run DB-hitting init steps after the widget is visible."""
        self._load_year_list()
        self._restore_dispatch_filters()
        self._run_totals_backfill_once()
        self._trigger_load()

    def _restore_dispatch_filters(self) -> None:
        """Restore persisted filters as one atomic UI state update."""
        self._restoring_dispatch_filters = True
        try:
            saved_year = self._dispatch_settings.value(
                "dispatch/year", str(QDate.currentDate().year())
            )
            if str(saved_year).strip().lower() == "all":
                index = self.year_combo.findData(None)
            else:
                try:
                    index = self.year_combo.findData(int(saved_year))
                except (TypeError, ValueError):
                    index = self.year_combo.findData(QDate.currentDate().year())
            if index >= 0:
                self.year_combo.setCurrentIndex(index)

            saved_status = str(
                self._dispatch_settings.value("dispatch/status", "All")
            )
            status_button = self.status_buttons.get(saved_status)
            if status_button is not None:
                status_button.setChecked(True)

            saved_mode = str(
                self._dispatch_settings.value("dispatch/date_mode", "forward")
            ).strip().lower()
            if saved_mode not in {"forward", "exact", "between", "all"}:
                saved_mode = "forward"
            index = self.date_scope_combo.findData(saved_mode)
            if index >= 0:
                self.date_scope_combo.setCurrentIndex(index)
            self._date_filter_mode = saved_mode
            self._date_filter_active = saved_mode != "all"

            for key, widget in (
                ("dispatch/date_from", self.date_filter),
                ("dispatch/date_to", self.date_to_filter),
            ):
                parsed = QDate.fromString(
                    str(self._dispatch_settings.value(key, "")),
                    "yyyy-MM-dd",
                )
                if parsed.isValid():
                    widget.setDate(parsed)

            include_archived = str(
                self._dispatch_settings.value(
                    "dispatch/include_closed_cancelled", "false"
                )
            ).lower() in {"1", "true", "yes"}
            self.include_closed_cancelled_checkbox.setChecked(include_archived)
            self._update_date_scope_controls()
        finally:
            self._restoring_dispatch_filters = False

    def _save_dispatch_filters(self) -> None:
        if self._restoring_dispatch_filters:
            return
        self._dispatch_settings.setValue(
            "dispatch/year",
            self.year_combo.currentData()
            if self.year_combo.currentData() is not None
            else "all",
        )
        self._dispatch_settings.setValue(
            "dispatch/status", self._selected_status()
        )
        self._dispatch_settings.setValue(
            "dispatch/date_mode", self._date_filter_mode
        )
        self._dispatch_settings.setValue(
            "dispatch/date_from",
            self.date_filter.date().toString("yyyy-MM-dd"),
        )
        self._dispatch_settings.setValue(
            "dispatch/date_to",
            self.date_to_filter.date().toString("yyyy-MM-dd"),
        )
        self._dispatch_settings.setValue(
            "dispatch/include_closed_cancelled",
            self.include_closed_cancelled_checkbox.isChecked(),
        )

    def _on_status_filter_changed(self, _text: str) -> None:
        self._save_dispatch_filters()
        self.filter_bookings()
        self._date_reload_timer.start()
        if (
            not self._restoring_dispatch_filters
            and self._should_include_archived()
            != getattr(self, "_archived_rows_loaded", False)
        ):
            self._trigger_load()

    def _selected_status(self) -> str:
        checked = self.status_button_group.checkedButton()
        return checked.text() if checked is not None else "All"

    def _should_include_archived(self) -> bool:
        return (
            bool(self.search_input.text().strip())
            or self.include_closed_cancelled_checkbox.isChecked()
            or self._selected_status() in {"Closed", "Cancelled"}
        )

    def _on_archive_filter_changed(self, _checked: bool) -> None:
        self._save_dispatch_filters()
        if not self._restoring_dispatch_filters:
            self._trigger_load()

    def _run_totals_backfill_once(self) -> None:
        """One-time repair: sync stored totals from charter_charges for legacy rows."""
        settings = QSettings("ArrowLimo", "DesktopApp")
        if settings.value("dispatch_totals_backfill_v1_done", "0") == "1":
            return

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    WITH charge_totals AS (
                        SELECT
                            charter_id,
                            COALESCE(SUM(amount), 0) AS charge_total
                        FROM charter_charges
                        GROUP BY charter_id
                    )
                    UPDATE charters c
                    SET
                        grand_total = ct.charge_total,
                        total_amount_due = ct.charge_total,
                        balance_owing = ct.charge_total -
                            COALESCE(c.amount_paid, c.paid_amount, 0),
                        updated_at = NOW()
                    FROM charge_totals ct
                    WHERE c.charter_id = ct.charter_id
                      AND (
                          ABS(COALESCE(c.grand_total, 0) - ct.charge_total) > 0.01
                          OR ABS(COALESCE(c.total_amount_due, 0) - ct.charge_total) > 0.01
                      )
                    """
                )
                fixed_rows = int(cur.rowcount or 0)
                self.db.conn.commit()
            settings.setValue("dispatch_totals_backfill_v1_done", "1")
            logger.info("Dispatch totals backfill completed; rows fixed=%s", fixed_rows)
        except Exception as e:
            try:
                self.db.conn.rollback()
            except Exception:
                pass
            logger.warning("Dispatch totals backfill skipped: %s", e)

    # ------------------------------------------------------------------
    # UI CONSTRUCTION
    # ------------------------------------------------------------------
    def _open_driver_run_confirmations(self) -> None:
        """Open the dispatcher queue for driver-submitted run details."""
        try:
            from driver_run_confirmations import DriverRunConfirmationsDialog

            dialog = DriverRunConfirmationsDialog(self.db, parent=self)
            dialog.confirmed.connect(self._trigger_load)
            dialog.exec()
        except Exception as exc:
            logger.exception("Failed to open driver run confirmations")
            QMessageBox.critical(
                self,
                "Unavailable",
                f"Driver run confirmations could not be opened:\n\n{exc}",
            )

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Row 1: action buttons + search + date
        row1 = QHBoxLayout()
        row1.setSpacing(6)

        new_btn = QPushButton("+ New Charter")
        new_btn.setFixedHeight(26)
        new_btn.clicked.connect(self.new_booking)
        row1.addWidget(new_btn)

        bulk_print_btn = QPushButton("Bulk Print Selected")
        bulk_print_btn.setFixedHeight(26)
        bulk_print_btn.clicked.connect(self._open_bulk_print_selected)
        row1.addWidget(bulk_print_btn)

        select_all_btn = QPushButton("Select All Visible")
        select_all_btn.setFixedHeight(26)
        select_all_btn.clicked.connect(
            lambda: self.bookings_table.selectAll()
        )
        row1.addWidget(select_all_btn)

        clear_sel_btn = QPushButton("Clear Selection")
        clear_sel_btn.setFixedHeight(26)
        clear_sel_btn.clicked.connect(
            lambda: self.bookings_table.clearSelection()
        )
        row1.addWidget(clear_sel_btn)

        confirm_runs_btn = QPushButton("🚦 Confirm Driver Details")
        confirm_runs_btn.setFixedHeight(26)
        confirm_runs_btn.setToolTip(
            "Review and confirm run details submitted by drivers in the web portal."
        )
        confirm_runs_btn.clicked.connect(self._open_driver_run_confirmations)
        row1.addWidget(confirm_runs_btn)

        row1.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Client, vehicle, driver, address..."
        )
        self.search_input.setMinimumWidth(160)
        self.search_input.textChanged.connect(self._on_search_text_changed)
        row1.addWidget(self.search_input, 1)

        self.include_closed_cancelled_checkbox = QCheckBox(
            "Include Closed/Cancelled"
        )
        self.include_closed_cancelled_checkbox.setToolTip(
            "Include closed and cancelled runs in the board. "
            "A search term enables them automatically."
        )
        self.include_closed_cancelled_checkbox.toggled.connect(
            self._on_archive_filter_changed
        )
        row1.addWidget(self.include_closed_cancelled_checkbox)

        row1.addWidget(QLabel("Date:"))
        self.date_scope_combo = QComboBox()
        self.date_scope_combo.addItem("From This Month Forward", "forward")
        self.date_scope_combo.addItem("Exact Date", "exact")
        self.date_scope_combo.addItem("Between Dates", "between")
        self.date_scope_combo.addItem("All Dates", "all")
        self.date_scope_combo.currentIndexChanged.connect(
            self._on_date_scope_changed
        )
        self.date_scope_combo.setToolTip(
            "Choose a date range, or use Current for this month forward."
        )
        row1.addWidget(self.date_scope_combo)

        self.date_filter = StandardDateEdit(prefer_month_text=True)
        self.date_filter.setCalendarPopup(True)
        today = QDate.currentDate()
        self.date_filter.setDate(QDate(today.year(), today.month(), 1))
        self.date_filter.setMaximumWidth(115)
        self.date_filter.dateChanged.connect(self._on_date_changed)
        row1.addWidget(self.date_filter)

        self.date_to_label = QLabel("To:")
        self.date_to_filter = StandardDateEdit(prefer_month_text=True)
        self.date_to_filter.setCalendarPopup(True)
        self.date_to_filter.setDate(today)
        self.date_to_filter.setMaximumWidth(115)
        self.date_to_filter.dateChanged.connect(self._on_date_changed)
        row1.addWidget(self.date_to_label)
        row1.addWidget(self.date_to_filter)

        self.date_find_input = StandardDateEdit(
            prefer_month_text=True, allow_blank=True
        )
        self.date_find_input.setCalendarPopup(True)
        self.date_find_input.setPlaceholderText("MM/DD/YYYY")
        self.date_find_input.setMaximumWidth(115)
        self.date_find_input.returnPressed.connect(self._apply_specific_date)
        row1.addWidget(self.date_find_input)

        find_date_btn = QPushButton("Find Date")
        find_date_btn.setFixedHeight(24)
        find_date_btn.clicked.connect(self._apply_specific_date)
        row1.addWidget(find_date_btn)

        today_btn = QPushButton("Today")
        today_btn.setFixedHeight(24)
        today_btn.clicked.connect(self._set_today_filter)
        row1.addWidget(today_btn)

        current_btn = QPushButton("Current")
        current_btn.setFixedHeight(24)
        current_btn.setToolTip(
            "Show runs from the first day of this month forward"
        )
        current_btn.clicked.connect(self._set_current_filter)
        row1.addWidget(current_btn)

        all_dates_btn = QPushButton("All Dates")
        all_dates_btn.setFixedHeight(24)
        all_dates_btn.clicked.connect(self._clear_date_filter)
        row1.addWidget(all_dates_btn)
        self._update_date_scope_controls()

        layout.addLayout(row1)

        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        status_row.addWidget(QLabel("Status:"))
        self.status_button_group = QButtonGroup(self)
        self.status_button_group.setExclusive(True)
        self.status_buttons = {}
        for status in (
            "All",
            "Quote",
            "Booked",
            "Open",
            "Pending",
            "Assigned",
            "Active",
            "Closed",
            "Cancelled",
            "In Payroll",
            "Not in Payroll",
        ):
            button = QRadioButton(status)
            self.status_button_group.addButton(button)
            self.status_buttons[status] = button
            status_row.addWidget(button)
        self.status_buttons["All"].setChecked(True)
        self.status_button_group.buttonToggled.connect(
            lambda button, checked: (
                self._on_status_filter_changed(button.text())
                if checked
                else None
            )
        )
        status_row.addStretch()
        layout.addLayout(status_row)

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

        legend = QLabel(
            "<span style='color:#111827'>Legend:</span> "
            "<span style='color:#166534'>white = complete / paid</span> | "
            "<span style='color:#c2410c'>orange = cancelled / NRR escrow</span> | "
            "<span style='color:#b91c1c'>red = needs review / balance issue</span> | "
            "<span style='color:#2e7d32'>active text = green</span> | "
            "<span style='color:#888888'>completed text = gray</span> | "
            "<span style='color:#e65100'>pending text = orange</span>"
        )
        legend.setWordWrap(False)
        legend.setToolTip(
            "White rows are complete and paid. Orange rows are cancelled or "
            "NRR escrow. Red rows need review because of a balance, payment, "
            "or paperwork issue. Status text uses green for active, gray for "
            "completed, and orange for pending."
        )
        row2.addWidget(legend)

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
        self.bookings_table.setColumnCount(18)
        self.bookings_table.setHorizontalHeaderLabels(
            [
                "Reserve #",
                "Date",
                "Day",
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
        self.bookings_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.bookings_table.setSelectionMode(
            QTableWidget.SelectionMode.ExtendedSelection
        )
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

        idx = self.year_combo.findData(QDate.currentDate().year())
        if idx < 0:
            idx = self.year_combo.findData(None)
        if idx >= 0:
            self.year_combo.setCurrentIndex(idx)
        self.year_combo.blockSignals(False)

    def _on_year_changed(self) -> None:
        if self._restoring_dispatch_filters:
            return
        selected_year = self.year_combo.currentData()
        if selected_year is not None and int(selected_year) < QDate.currentDate().year():
            self._restoring_dispatch_filters = True
            try:
                self._date_filter_mode = "all"
                self._date_filter_active = False
                self.date_scope_combo.setCurrentIndex(
                    self.date_scope_combo.findData("all")
                )
                self.include_closed_cancelled_checkbox.setChecked(True)
                self._update_date_scope_controls()
            finally:
                self._restoring_dispatch_filters = False
        self._save_dispatch_filters()
        self._trigger_load()

    def _on_search_text_changed(self, _text: str) -> None:
        """Use search as the explicit exception to the active-only default."""
        self.filter_bookings()
        include_archived = self._should_include_archived()
        if include_archived != getattr(self, "_archived_rows_loaded", False):
            self._trigger_load()

    def _update_date_scope_controls(self) -> None:
        between = getattr(self, "_date_filter_mode", "forward") == "between"
        if hasattr(self, "date_to_label"):
            self.date_to_label.setVisible(between)
        if hasattr(self, "date_to_filter"):
            self.date_to_filter.setVisible(between)

    def _on_date_scope_changed(self) -> None:
        self._date_filter_mode = self.date_scope_combo.currentData() or "forward"
        self._date_filter_active = self._date_filter_mode != "all"
        self._update_date_scope_controls()
        if self._restoring_dispatch_filters:
            return
        self._save_dispatch_filters()
        self._trigger_load()

    def _trigger_load(self) -> None:
        """Start background load for the selected year."""
        self._date_reload_timer.stop()
        year = self.year_combo.currentData()
        label = self.year_combo.currentText()
        include_archived = self._should_include_archived()
        self._archived_rows_loaded = include_archived
        date_mode = getattr(self, "_date_filter_mode", "forward")
        date_from = self.date_filter.date().toString("yyyy-MM-dd")
        date_to = self.date_to_filter.date().toString("yyyy-MM-dd")
        if date_mode == "all":
            date_from = None
            date_to = None
        elif date_mode == "between" and date_to < date_from:
            date_from, date_to = date_to, date_from
        self.usage_telemetry.track(
            "dispatch_load_started", {"year": year, "label": label}
        )
        self.load_status_label.setText(f"Loading {label}...")
        request = (
            year,
            label,
            include_archived,
            date_mode,
            date_from,
            date_to,
        )
        if self._worker and self._worker.isRunning():
            self._pending_load_request = request
            return
        self._start_load(request)

    def _start_load(self, request: tuple) -> None:
        """Start one dispatch query; later requests are coalesced until it exits."""
        year, _label, include_archived, date_mode, date_from, date_to = request
        self.bookings_table.setRowCount(0)
        self._worker = _LoadWorker(
            self.db.config,
            year,
            include_archived,
            date_mode,
            date_from,
            date_to,
        )
        worker = self._worker
        worker.loaded.connect(
            lambda rows, active_worker=worker: self._on_worker_loaded(
                active_worker, rows
            )
        )
        worker.load_error.connect(
            lambda msg, active_worker=worker: self._on_worker_error(
                active_worker, msg
            )
        )
        worker.finished.connect(
            lambda active_worker=worker: self._on_worker_finished(active_worker)
        )
        self._worker.start()

    def _on_worker_loaded(self, worker: _LoadWorker, rows: list) -> None:
        if worker is self._worker and self._pending_load_request is None:
            self._on_loaded(rows)

    def _on_worker_error(self, worker: _LoadWorker, msg: str) -> None:
        if worker is self._worker and self._pending_load_request is None:
            self._on_load_error(msg)
        else:
            logger.info("Superseded dispatch load failed: %s", msg)

    def _on_worker_finished(self, worker: _LoadWorker) -> None:
        if worker is not self._worker:
            return
        self._worker = None
        pending_request = self._pending_load_request
        self._pending_load_request = None
        if pending_request is not None:
            self._start_load(pending_request)

    def _on_loaded(self, rows) -> None:
        normalized_rows = []
        for row in rows or []:
            values = tuple(row)
            if len(values) < 24:
                values += (None,) * (24 - len(values))
            normalized_rows.append(values)
        self.bookings_data = normalized_rows
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
        n_mismatch = 0
        for b in bookings:
            try:
                td = float(b[4] or 0)
                tp = float(b[5] or 0)
                bo = (
                    float(b[6])
                    if b[6] is not None
                    else round(td - tp, 2)
                )
                total_due += td
                total_paid += tp
                balance += bo
                if bo > 0.01:
                    n_open += 1
                if len(b) > 18 and bool(b[18]):
                    n_mismatch += 1
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
            f"Open: {n_open} │ Mismatch: {n_mismatch}{filter_text}"
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

            # Show the same date format as the filter widgets while retaining
            # an ISO value for chronological sorting.
            raw_date = str(booking[2] or "")
            date_display = raw_date
            parsed_row_date = QDate.fromString(raw_date[:10], "yyyy-MM-dd")
            if parsed_row_date.isValid():
                date_display = parsed_row_date.toString("MM/dd/yyyy")

            # Derive day-of-week abbreviation from charter_date
            try:
                from datetime import date as _date
                _d = booking[2]
                if isinstance(_d, str) and len(_d) >= 10:
                    _d = _date.fromisoformat(_d[:10])
                day_abbr = _d.strftime("%a") if hasattr(_d, "strftime") else ""
            except Exception:
                day_abbr = ""

            cells = [
                str(booking[1] or ""),  # Reserve #
                date_display,          # Date
                day_abbr,              # Day
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
            has_total_mismatch = bool(booking[18]) if len(booking) > 18 else False
            is_cancelled = bool(booking[19]) if len(booking) > 19 else False
            needs_review = bool(booking[20]) if len(booking) > 20 else False
            nrr_amount = float(booking[21] or 0) if len(booking) > 21 else 0.0
            nrr_received = bool(booking[22]) if len(booking) > 22 else False
            nrr_escrow_applied = bool(booking[23]) if len(booking) > 23 else False
            has_escrow = nrr_escrow_applied or (nrr_received and nrr_amount > 0)
            has_payment_issue = balance_owing > 0.009 or has_total_mismatch
            if is_cancelled or has_escrow:
                row_bg = QColor("#fed7aa")
                row_fg = QColor("#9a3412")
            elif needs_review or has_payment_issue:
                row_bg = QColor("#fecaca")
                row_fg = QColor("#991b1b")
            else:
                row_bg = QColor("#ffffff")
                row_fg = None
            numeric_cols = {
                4: total_due,
                5: total_paid,
                6: balance_owing,
            }

            for col_idx, cell in enumerate(cells):
                if col_idx in numeric_cols:
                    item = _NumericTableWidgetItem(
                        cell, numeric_cols[col_idx]
                    )
                elif col_idx == 1:
                    item = _DateTableWidgetItem(cell, raw_date[:10])
                else:
                    item = QTableWidgetItem(cell)
                if col_idx == 0:
                    try:
                        item.setData(Qt.ItemDataRole.UserRole, int(booking[0]))
                    except Exception:
                        pass
                item.setBackground(row_bg)
                if row_fg is not None:
                    item.setForeground(row_fg)
                if col_idx == 9:
                    status = booking[9] or "Pending"
                    if status == "Active":
                        item.setForeground(QColor("#2e7d32"))
                    elif status == "Closed":
                        item.setForeground(QColor("#888"))
                    elif status == "Pending":
                        item.setForeground(QColor("#e65100"))

                # Keep the balance cell readable without overriding row state.
                if col_idx == 6:
                    if balance_owing > 0.009:
                        item.setBackground(QColor("#ffcdd2"))
                        item.setForeground(QColor("#b71c1c"))
                    elif balance_owing < -0.009:
                        item.setBackground(QColor("#fff9c4"))
                        item.setForeground(QColor("#7f6000"))
                    else:
                        item.setBackground(row_bg)
                        if row_fg is not None:
                            item.setForeground(row_fg)

                if col_idx == 4 and has_total_mismatch:
                    item.setBackground(QColor("#ffe082"))
                    item.setForeground(QColor("#5d4037"))
                    item.setToolTip(
                        "Stored totals differ (grand_total vs total_amount_due). "
                        "Open and save charter to re-sync."
                    )

                self.bookings_table.setItem(row_idx, col_idx, item)

            # Checklist completion column (col 17)
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
            self.bookings_table.setItem(row_idx, 17, cl_item)

        self.bookings_table.setSortingEnabled(True)
        self._restore_sort()

    def filter_bookings(self) -> None:
        search_text = self.search_input.text().lower().strip()
        status_filter = self._selected_status()

        try:
            date_mode = getattr(self, "_date_filter_mode", "forward")
            date_str = self.date_filter.date().toString("yyyy-MM-dd")
            date_to_str = self.date_to_filter.date().toString("yyyy-MM-dd")
            if date_mode == "between" and date_to_str < date_str:
                date_str, date_to_str = date_to_str, date_str
            apply_date = date_mode != "all"
        except Exception:
            apply_date = False
            date_str = ""

        filtered = []
        for booking in self.bookings_data:
            booking_date = str(booking[2] or "")
            if date_mode == "forward" and booking_date < date_str:
                continue
            if date_mode == "exact" and booking_date != date_str:
                continue
            if date_mode == "between" and not (date_str <= booking_date <= date_to_str):
                continue

            if search_text:
                haystack = " ".join(
                    [
                        str(booking[1] or ""),  # reserve_number
                        str(booking[3] or ""),  # client_name
                        str(booking[7] or ""),  # vehicle_dispatched
                        str(booking[8] or ""),  # driver
                        str(booking[12] or ""),  # pickup_address
                        str(booking[14] or ""),  # dropoff_address
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
            date_str=(
                f"{date_mode}:{date_str}-{date_to_str}"
                if date_mode == "between"
                else f"{date_mode}:{date_str}" if apply_date else ""
            ),
        )

    def _set_today_filter(self) -> None:
        """Apply today's date filter and refresh the grid."""
        self.date_scope_combo.blockSignals(True)
        self.date_scope_combo.setCurrentIndex(self.date_scope_combo.findData("exact"))
        self.date_scope_combo.blockSignals(False)
        self._date_filter_mode = "exact"
        self._date_filter_active = True
        self.date_filter.setDate(QDate.currentDate())
        self.date_find_input.setText(
            QDate.currentDate().toString("MM/dd/yyyy")
        )
        self._update_date_scope_controls()
        self._save_dispatch_filters()
        self._date_reload_timer.stop()
        self._trigger_load()

    def _set_current_filter(self) -> None:
        """Show runs from the first day of the current month forward."""
        self.date_scope_combo.blockSignals(True)
        self.date_scope_combo.setCurrentIndex(
            self.date_scope_combo.findData("forward")
        )
        self.date_scope_combo.blockSignals(False)
        self._date_filter_mode = "forward"
        self._date_filter_active = True
        today = QDate.currentDate()
        self.date_filter.setDate(QDate(today.year(), today.month(), 1))
        self.date_find_input.clear()
        self._update_date_scope_controls()
        self._save_dispatch_filters()
        self._date_reload_timer.stop()
        self._trigger_load()

    def _clear_date_filter(self) -> None:
        """Show all dates explicitly."""
        self.date_scope_combo.blockSignals(True)
        self.date_scope_combo.setCurrentIndex(self.date_scope_combo.findData("all"))
        self.date_scope_combo.blockSignals(False)
        self._date_filter_mode = "all"
        self._date_filter_active = False
        self.date_filter.setDate(QDate.currentDate())
        self.date_find_input.clear()
        self._update_date_scope_controls()
        self._save_dispatch_filters()
        self._date_reload_timer.stop()
        self._trigger_load()

    def _on_date_changed(self) -> None:
        self._date_filter_active = self._date_filter_mode != "all"
        self.date_find_input.setText(
            self.date_filter.date().toString("MM/dd/yyyy")
        )
        self._save_dispatch_filters()
        self.filter_bookings()

    def _parse_date_entry(self, text: str) -> QDate:
        for fmt in (
            "MM/dd/yyyy",
            "M/d/yyyy",
            "MM-dd-yyyy",
            "M-d-yyyy",
            "yyyy-MM-dd",
            "yyyy/M/d",
            "yyyy/MM/dd",
        ):
            parsed = QDate.fromString(text, fmt)
            if parsed.isValid():
                return parsed

        digits = "".join(c for c in text if c.isdigit())
        if len(digits) == 8:
            parsed = QDate(
                int(digits[4:8]),
                int(digits[0:2]),
                int(digits[2:4]),
            )
            if parsed.isValid():
                return parsed
        return QDate()

    def _apply_specific_date(self) -> None:
        txt = self.date_find_input.text().strip()
        if not txt:
            self._clear_date_filter()
            return

        parsed = self._parse_date_entry(txt)
        if not parsed.isValid():
            QMessageBox.warning(
                self,
                "Invalid Date",
                "Use MM/DD/YYYY, for example 06/11/2026.",
            )
            return

        self.date_scope_combo.blockSignals(True)
        self.date_scope_combo.setCurrentIndex(self.date_scope_combo.findData("exact"))
        self.date_scope_combo.blockSignals(False)
        self._date_filter_mode = "exact"
        self._date_filter_active = True
        year_index = self.year_combo.findData(parsed.year())
        if year_index >= 0:
            self.year_combo.blockSignals(True)
            self.year_combo.setCurrentIndex(year_index)
            self.year_combo.blockSignals(False)
        self.date_filter.setDate(parsed)
        self._update_date_scope_controls()
        self._save_dispatch_filters()
        self._date_reload_timer.stop()
        self._trigger_load()

    def _focus_search(self) -> None:
        """Focus search input quickly for keyboard-first users."""
        self.search_input.setFocus()
        self.search_input.selectAll()

    def _clear_filters(self) -> None:
        """Clear active search/status filters without touching year selection."""
        focused = self.focusWidget()
        if focused and self.isAncestorOf(focused):
            self.search_input.clear()
            self.status_buttons["All"].setChecked(True)
            self.date_scope_combo.blockSignals(True)
            self.date_scope_combo.setCurrentIndex(
                self.date_scope_combo.findData("all")
            )
            self.date_scope_combo.blockSignals(False)
            self._date_filter_mode = "all"
            self._date_filter_active = False
            self.date_filter.setDate(QDate.currentDate())
            self.date_find_input.clear()
            self._update_date_scope_controls()
            self._save_dispatch_filters()
            self._trigger_load()

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

        self._trace_dispatch_event("double_click_start", row=row, reserve=reserve_number)
        self._arm_dispatch_watchdog(f"dispatch_double_click:{reserve_number}", timeout_seconds=15)
        try:
            self.usage_telemetry.track(
                "dispatch_open_charter", {"reserve_number": reserve_number}
            )

            # Pull current row data by reserve from DB so drill-down is correct
            # even when the table has been sorted/reordered by the user.
            charter_id = None
            try:
                self._trace_dispatch_event("resolve_charter_id_start", reserve=reserve_number)
                with DatabaseContext(self.db, auto_commit=False) as cur:
                    try:
                        cur.execute("SET statement_timeout = 30000")
                        cur.execute("SET lock_timeout = 15000")
                    except Exception as _e:
                        logger.debug("Suppressed: %s", _e)
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
                self._trace_dispatch_event("resolve_charter_id_done", reserve=reserve_number, charter_id=charter_id)
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
                            from drill_down_dialogs import PreRunChecklistDialog

                            self._trace_dispatch_event(
                                "pre_run_checklist_open",
                                reserve=reserve_number,
                                charter_id=charter_id,
                            )
                            chk = PreRunChecklistDialog(
                                self.db,
                                charter_id=charter_id,
                                reserve_number=reserve_number,
                                parent=self,
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
                        self._trace_dispatch_event("prefill_dispatch_row_start", reserve=reserve_number)
                        charter_form.prefill_from_dispatch_row(booking)

                    self._trace_dispatch_event("switch_dispatch_tab_start", tab_index=1, reserve=reserve_number)
                    main_window.dispatch_tabs_widget.setCurrentIndex(1)
                    self._trace_dispatch_event("switch_dispatch_tab_done", tab_index=1, reserve=reserve_number)

                    if hasattr(charter_form, "booking_tab_widget"):
                        # Ensure users land on the primary Run Charter page,
                        # not Charter Lookup, so edits/opened data stay visible.
                        self._trace_dispatch_event("switch_booking_tab_start", tab_index=0, reserve=reserve_number)
                        charter_form.booking_tab_widget.setCurrentIndex(0)
                        self._trace_dispatch_event("switch_booking_tab_done", tab_index=0, reserve=reserve_number)

                    if charter_id and hasattr(charter_form, "load_charter_by_id"):
                        self._trace_dispatch_event("charter_form_load_by_id", charter_id=charter_id, reserve=reserve_number)
                        charter_form.load_charter_by_id(int(charter_id))
                    elif hasattr(charter_form, "load_charter_by_reserve"):
                        self._trace_dispatch_event("charter_form_load_by_reserve", reserve=reserve_number)
                        charter_form.load_charter_by_reserve(reserve_number)
                    return
            except Exception as e:
                logger.error(
                    f"Failed to open in Run Charter tab, falling back: {e}"
                )

            try:
                from drill_down_widgets import CharterDetailDialog

                self._trace_dispatch_event("fallback_dialog_open", reserve=reserve_number)
                dialog = CharterDetailDialog(
                    self.db, reserve_number=str(reserve_number), parent=self
                )
                dialog.exec()
                self._trace_dispatch_event("fallback_dialog_closed", reserve=reserve_number)
                self._trigger_load()
            except Exception as e:
                logger.error(f"Failed to open charter details: {e}")
                QMessageBox.warning(
                    self, "Error", f"Failed to open charter details: {e}"
                )
        finally:
            self._trace_dispatch_event("double_click_end", reserve=reserve_number)
            self._disarm_dispatch_watchdog()

    def new_booking(self) -> None:
        try:
            from datetime import date, datetime

            from calendar_event_finder_dialog import CalendarEventFinderDialog
            from client_finder_dialog import ClientFinderDialog
            from charter_form_widget import CharterFormWidget

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
            charter_form.saved.connect(
                lambda _charter_id: self.on_charter_saved(dialog)
            )
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
        s.setValue("sort_order", order.value)

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
        for _s in (
            "Quote",
            "Booked",
            "Open",
            "Pending",
            "Assigned",
            "Active",
            "Closed",
            "Cancelled",
        ):
            _act = status_menu.addAction(_s)
            _act.triggered.connect(
                lambda checked=False, s=_s: self._quick_set_status(row, s)
            )

        menu.addSeparator()
        bulk_print_act = menu.addAction("📚 Bulk Print Selected Charters")
        bulk_print_act.triggered.connect(self._open_bulk_print_selected)
        edit_act = menu.addAction("✏️  Edit Reserve Number...")
        edit_act.triggered.connect(lambda: self._edit_reserve_number(row))
        menu.exec(self.bookings_table.viewport().mapToGlobal(pos))

    def _selected_charter_ids(self) -> list[int]:
        ids = []
        seen = set()

        model = self.bookings_table.selectionModel()
        selected_rows = model.selectedRows() if model else []
        for model_index in selected_rows:
            row = model_index.row()
            reserve_item = self.bookings_table.item(row, 0)
            if not reserve_item:
                continue
            raw_charter_id = reserve_item.data(Qt.ItemDataRole.UserRole)
            try:
                charter_id = int(raw_charter_id)
            except Exception:
                continue
            if charter_id > 0 and charter_id not in seen:
                seen.add(charter_id)
                ids.append(charter_id)

        return ids

    def _open_bulk_print_selected(self) -> None:
        charter_ids = self._selected_charter_ids()
        if not charter_ids:
            QMessageBox.information(
                self,
                "No Selection",
                "Select one or more charter rows first.",
            )
            return

        try:
            main_window = self.window()
            if not hasattr(main_window, "charter_form"):
                QMessageBox.warning(
                    self,
                    "Unavailable",
                    "Charter form is not available to open bulk print.",
                )
                return

            charter_form = main_window.charter_form
            open_bulk = getattr(charter_form, "open_bulk_print_selection_dialog", None)
            if callable(open_bulk):
                open_bulk(charter_ids)
                return

            open_legacy = getattr(charter_form, "open_multi_invoice_selection_dialog", None)
            if callable(open_legacy):
                open_legacy(charter_ids)
                return

            QMessageBox.warning(
                self,
                "Unavailable",
                "Bulk print dialog is not available in charter form.",
            )
            return
        except Exception as e:
            logger.error("Dispatch bulk print failed: %s", e)
            QMessageBox.critical(
                self,
                "Bulk Print Error",
                f"Failed to open bulk print dialog:\n{e}",
            )

    def _record_payment(self, row: int) -> None:
        """Quick payment entry from the dispatch board context menu."""
        reserve_item = self.bookings_table.item(row, 0)
        if not reserve_item:
            return
        reserve_number = reserve_item.text().strip()
        try:
            balance_item = self.bookings_table.item(row, 6)
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
                    "UPDATE charters SET status = %s, updated_at = NOW() "
                    "WHERE reserve_number = %s",
                    (new_status, reserve_number),
                )
            logger.info("Quick status set: %s → %s", reserve_number, new_status)
            self._trigger_load()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update status: {e}")

    # ------------------------------------------------------------------
    # EDIT RESERVE NUMBER
    # ------------------------------------------------------------------
    @staticmethod
    def _rename_reserve_references(
        cur, charter_id: int, current_reserve: str, new_reserve: str
    ) -> int:
        """Rename a reserve and its operational text references atomically."""
        cur.execute(
            "UPDATE charters SET reserve_number = %s, updated_at = NOW() "
            "WHERE charter_id = %s AND reserve_number = %s",
            (new_reserve, charter_id, current_reserve),
        )
        if cur.rowcount != 1:
            raise RuntimeError(
                f"Charter {charter_id} no longer has reserve {current_reserve}."
            )

        cur.execute(
            """
            SELECT c.table_name
            FROM information_schema.columns c
            JOIN information_schema.tables t
              ON t.table_schema = c.table_schema
             AND t.table_name = c.table_name
            WHERE c.table_schema = 'public'
              AND c.column_name = 'reserve_number'
              AND t.table_type = 'BASE TABLE'
              AND c.table_name <> 'charters'
              AND c.table_name NOT ILIKE 'backup%'
              AND c.table_name NOT ILIKE '%archive%'
              AND c.table_name NOT ILIKE '%orphan%deleted%'
            ORDER BY c.table_name
            """
        )
        reference_tables = [row[0] for row in cur.fetchall()]
        updated_references = 0
        for table_name in reference_tables:
            cur.execute(
                pg_sql.SQL(
                    "UPDATE {} SET reserve_number = %s WHERE reserve_number = %s"
                ).format(pg_sql.Identifier(table_name)),
                (new_reserve, current_reserve),
            )
            updated_references += max(0, int(cur.rowcount or 0))

        for table_name in ("charter_payments", "driver_payroll"):
            cur.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = %s
                  AND column_name = 'charter_id'
                  AND data_type IN ('character varying', 'text')
                """,
                (table_name,),
            )
            if not cur.fetchone():
                continue
            cur.execute(
                pg_sql.SQL(
                    "UPDATE {} SET charter_id = %s WHERE charter_id = %s"
                ).format(pg_sql.Identifier(table_name)),
                (new_reserve, current_reserve),
            )
            updated_references += max(0, int(cur.rowcount or 0))

        return updated_references

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
        new_input.setMaxLength(6)
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
                updated_references = self._rename_reserve_references(
                    cur,
                    int(charter_id),
                    current_reserve,
                    new_reserve,
                )
            logger.info(
                "Reserve renamed: %s → %s; related rows updated=%s",
                current_reserve,
                new_reserve,
                updated_references,
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
