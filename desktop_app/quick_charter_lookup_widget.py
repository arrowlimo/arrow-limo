"""
Quick charter lookup widget - combined exact lookup and advanced search.

This widget keeps reserve/charter ID lookup as the primary workflow and embeds
optional filters plus results directly in the dispatch screen.
"""

import logging
import os

import psycopg2
from db_error_handling import DatabaseContext
from PyQt6.QtCore import QDate, QStringListModel, Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QCompleter,
    QDateEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class QuickCharterLookupWidget(QWidget):
    """Combined charter lookup widget for quick ID search and filters."""

    def __init__(self, db_connection, parent=None) -> None:
        super().__init__(parent)
        self.db = db_connection
        self.parent_widget = parent
        self._filters_visible = False
        self.init_ui()
        self.populate_autocomplete()
        self.load_filters()
        self.load_filtered_charters()

    def init_ui(self) -> None:
        outer_layout = QVBoxLayout()
        outer_layout.setContentsMargins(0, 5, 0, 5)
        outer_layout.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        self.top_row = top_row

        label = QLabel("Quick Charter Lookup:")
        label_font = QFont()
        label_font.setBold(True)
        label.setFont(label_font)
        top_row.addWidget(label)

        self.charter_input = QLineEdit()
        self.charter_input.setPlaceholderText(
            "Enter reserve # (006717) or charter ID (18720)..."
        )
        self.charter_input.setMaximumWidth(280)
        self.charter_input.returnPressed.connect(self.on_lookup)
        top_row.addWidget(self.charter_input)

        self.lookup_btn = QPushButton("Lookup")
        self.lookup_btn.clicked.connect(self.on_lookup)
        self.lookup_btn.setMaximumWidth(90)
        top_row.addWidget(self.lookup_btn)

        self.advanced_btn = QPushButton("Advanced Filters")
        self.advanced_btn.clicked.connect(self.toggle_filters)
        self.advanced_btn.setMaximumWidth(140)
        top_row.addWidget(self.advanced_btn)

        self.beverage_order_btn = QPushButton("🍷 Beverage Order")
        self.beverage_order_btn.setToolTip(
            "Enter a reserve # above, then click to add/amend the beverage order for that charter"
        )
        self.beverage_order_btn.clicked.connect(self.on_beverage_order)
        self.beverage_order_btn.setMaximumWidth(160)
        top_row.addWidget(self.beverage_order_btn)

        top_row.addStretch()
        outer_layout.addLayout(top_row)

        self.filters_frame = QFrame()
        self.filters_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.filters_frame.setVisible(False)
        filters_layout = QVBoxLayout()
        filters_layout.setContentsMargins(8, 8, 8, 8)
        filters_layout.setSpacing(8)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        grid.addWidget(QLabel("Charter #:"), 0, 0)
        self.charter_num_input = QLineEdit()
        self.charter_num_input.setPlaceholderText("e.g., 006717 or 18720")
        self.charter_num_input.setMaximumWidth(140)
        self.charter_num_input.textChanged.connect(self.on_filter_changed)
        grid.addWidget(self.charter_num_input, 0, 1)

        grid.addWidget(QLabel("Driver:"), 0, 2)
        self.driver_combo = QComboBox()
        self.driver_combo.setMaximumWidth(170)
        self.driver_combo.currentTextChanged.connect(self.on_filter_changed)
        grid.addWidget(self.driver_combo, 0, 3)

        grid.addWidget(QLabel("Vehicle:"), 0, 4)
        self.vehicle_combo = QComboBox()
        self.vehicle_combo.setMaximumWidth(170)
        self.vehicle_combo.currentTextChanged.connect(self.on_filter_changed)
        grid.addWidget(self.vehicle_combo, 0, 5)

        grid.addWidget(QLabel("Status:"), 0, 6)
        self.status_combo = QComboBox()
        self.status_combo.addItems(
            ["All", "pending", "booked", "completed", "cancelled", "closed"]
        )
        self.status_combo.setMaximumWidth(130)
        self.status_combo.currentTextChanged.connect(self.on_filter_changed)
        grid.addWidget(self.status_combo, 0, 7)

        grid.addWidget(QLabel("From:"), 1, 0)
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addMonths(-3))
        self.date_from.setMaximumWidth(140)
        self.date_from.dateChanged.connect(self.on_filter_changed)
        grid.addWidget(self.date_from, 1, 1)

        grid.addWidget(QLabel("To:"), 1, 2)
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate().addDays(30))
        self.date_to.setMaximumWidth(140)
        self.date_to.dateChanged.connect(self.on_filter_changed)
        grid.addWidget(self.date_to, 1, 3)

        grid.addWidget(QLabel("Balance > $:"), 1, 4)
        self.balance_min = QSpinBox()
        self.balance_min.setMaximum(100000)
        self.balance_min.setMaximumWidth(100)
        self.balance_min.valueChanged.connect(self.on_filter_changed)
        grid.addWidget(self.balance_min, 1, 5)

        self.unpaid_only = QCheckBox("Unpaid Only")
        self.unpaid_only.stateChanged.connect(self.on_filter_changed)
        grid.addWidget(self.unpaid_only, 1, 6)

        self.reset_filters_btn = QPushButton("Reset Filters")
        self.reset_filters_btn.clicked.connect(self.reset_filters)
        grid.addWidget(self.reset_filters_btn, 1, 7)

        filters_layout.addLayout(grid)

        sort_row = QHBoxLayout()
        sort_row.setSpacing(8)
        sort_row.addWidget(QLabel("Sort by:"))

        self.sort1_combo = QComboBox()
        self.sort1_combo.addItems(
            ["Date (Newest)", "Date (Oldest)", "Balance (High)", "Balance (Low)", "Reserve #", "Driver", "Vehicle"]
        )
        self.sort1_combo.setMaximumWidth(150)
        self.sort1_combo.currentTextChanged.connect(self.on_filter_changed)
        sort_row.addWidget(self.sort1_combo)

        sort_row.addWidget(QLabel("Then by:"))
        self.sort2_combo = QComboBox()
        self.sort2_combo.addItems(
            ["None", "Vehicle", "Driver", "Reserve #", "Balance (High)", "Balance (Low)"]
        )
        self.sort2_combo.setMaximumWidth(150)
        self.sort2_combo.currentTextChanged.connect(self.on_filter_changed)
        sort_row.addWidget(self.sort2_combo)

        sort_row.addWidget(QLabel("Then by:"))
        self.sort3_combo = QComboBox()
        self.sort3_combo.addItems(["None", "Vehicle", "Driver", "Reserve #", "Time"])
        self.sort3_combo.setMaximumWidth(150)
        self.sort3_combo.currentTextChanged.connect(self.on_filter_changed)
        sort_row.addWidget(self.sort3_combo)

        sort_row.addStretch()
        filters_layout.addLayout(sort_row)

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(10)
        self.results_table.setHorizontalHeaderLabels(
            [
                "Reserve #",
                "Charter ID",
                "Date",
                "Time",
                "Driver",
                "Vehicle",
                "Status",
                "Total Due",
                "Paid",
                "Balance",
            ]
        )
        self.results_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.results_table.setSelectionBehavior(
            self.results_table.SelectionBehavior.SelectRows
        )

        self.results_table.setMaximumHeight(320)
        self.results_table.doubleClicked.connect(self.on_table_double_click)
        filters_layout.addWidget(QLabel("Results (double-click to open charter):"))
        filters_layout.addWidget(self.results_table)

        self.status_line = QLabel("")
        self.status_line.setStyleSheet("color: #555;")
        filters_layout.addWidget(self.status_line)

        self.filters_frame.setLayout(filters_layout)
        outer_layout.addWidget(self.filters_frame)

        self.setLayout(outer_layout)
        self.results_table.setSelectionMode(
            self.results_table.SelectionMode.SingleSelection
        )

    def insert_top_action_widget(self, widget: QWidget) -> None:
        """Insert an action widget into the quick-lookup top row."""
        if widget is None:
            return
        if not hasattr(self, 'top_row'):
            return
        try:
            self.top_row.insertWidget(max(self.top_row.count() - 1, 0), widget)
        except RuntimeError:
            # Defensive guard for transient teardown states.
            logger.warning("Quick lookup top row no longer exists; skipping action insert")

    def toggle_filters(self) -> None:
        self._filters_visible = not self._filters_visible
        self.filters_frame.setVisible(self._filters_visible)
        self.advanced_btn.setText(
            "Hide Filters" if self._filters_visible else "Advanced Filters"
        )
        if self._filters_visible:
            self.load_filtered_charters()

    def reset_filters(self) -> None:
        self.charter_num_input.clear()
        self.driver_combo.setCurrentIndex(0)
        self.vehicle_combo.setCurrentIndex(0)
        self.status_combo.setCurrentIndex(0)
        self.date_from.setDate(QDate.currentDate().addMonths(-3))
        self.date_to.setDate(QDate.currentDate().addDays(30))
        self.balance_min.setValue(0)
        self.unpaid_only.setChecked(False)
        self.sort1_combo.setCurrentIndex(0)
        self.sort2_combo.setCurrentIndex(0)
        self.sort3_combo.setCurrentIndex(0)
        self.load_filtered_charters()

    def populate_autocomplete(self) -> None:
        """Populate autocomplete suggestions from database."""
        try:
            if hasattr(self.db, "cursor"):
                with DatabaseContext(self.db, auto_commit=False) as cur:
                    cur.execute(
                        """
                        SELECT COALESCE(reserve_number, CAST(charter_id AS TEXT))
                        FROM charters
                        WHERE reserve_number IS NOT NULL OR charter_id IS NOT NULL
                        ORDER BY reserve_number
                        LIMIT 500
                        """
                    )
                    suggestions = [row[0] for row in cur.fetchall()]
            else:
                conn = psycopg2.connect(
                    host=os.getenv("DB_HOST", "localhost"),
                    dbname=os.getenv("DB_NAME", "almsdata"),
                    user=os.getenv("DB_USER", "postgres"),
                    password=os.getenv("DB_PASSWORD", "***REDACTED***"),
                )
                with DatabaseContext(conn, auto_commit=False) as cur:
                    cur.execute(
                        """
                        SELECT COALESCE(reserve_number, CAST(charter_id AS TEXT))
                        FROM charters
                        WHERE reserve_number IS NOT NULL OR charter_id IS NOT NULL
                        ORDER BY reserve_number
                        LIMIT 500
                        """
                    )
                    suggestions = [row[0] for row in cur.fetchall()]

            model = QStringListModel(suggestions)
            completer = QCompleter(model)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            self.charter_input.setCompleter(completer)
        except Exception as e:
            logger.error(f"Error loading autocomplete: {e}")
            print(f"Error loading autocomplete: {e}")

    def load_filters(self) -> None:
        """Load driver and vehicle filter values."""
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    "SELECT DISTINCT driver FROM charters WHERE driver IS NOT NULL AND driver != '' ORDER BY driver"
                )
                drivers = [row[0] for row in cur.fetchall()]
                self.driver_combo.blockSignals(True)
                self.driver_combo.clear()
                self.driver_combo.addItems(["All"] + drivers)
                self.driver_combo.blockSignals(False)

                cur.execute(
                    """
                    SELECT v.vehicle_number
                    FROM vehicles v
                    WHERE v.vehicle_number IS NOT NULL
                      AND v.vehicle_number != ''
                    ORDER BY
                        CASE WHEN v.status = 'active' THEN 0 ELSE 1 END,
                        CASE
                            WHEN v.vehicle_number ~ '^[Ll]-?\\d+$'
                                THEN CAST(
                                    regexp_replace(
                                        v.vehicle_number,
                                        '[^0-9]',
                                        '',
                                        'g'
                                    ) AS INT
                                )
                            ELSE 9999
                        END,
                        v.vehicle_number
                    """
                )
                vehicles = [row[0] for row in cur.fetchall()]
                self.vehicle_combo.blockSignals(True)
                self.vehicle_combo.clear()
                self.vehicle_combo.addItems(["All"] + vehicles)
                self.vehicle_combo.blockSignals(False)
        except Exception as e:
            logger.error(f"Failed to load charter filters: {e}")
            QMessageBox.warning(self, "Error", f"Failed to load charter filters: {e}")

    def on_lookup(self) -> None:
        """Lookup charter by reserve number or charter ID."""
        query = self.charter_input.text().strip()
        if not query:
            QMessageBox.warning(self, "Error", "Enter a charter number or ID")
            return

        try:
            row = self._fetch_exact_charter(query)
            if row:
                charter_id = row[0]
                self._open_charter(charter_id)
            else:
                QMessageBox.information(
                    self,
                    "Not Found",
                    f"No exact charter found for '{query}'. Use the filters below for partial matches.",
                )
        except Exception as e:
            logger.error(f"Lookup failed: {e}")
            QMessageBox.critical(self, "Error", f"Lookup failed: {e}")

    def _fetch_exact_charter(self, query: str) -> object:
        try:
            if hasattr(self.db, "cursor"):
                with DatabaseContext(self.db, auto_commit=False) as cur:
                    cur.execute(
                        """
                        SELECT charter_id, reserve_number, charter_date,
                               driver, vehicle, status, balance
                        FROM charters
                        WHERE reserve_number = %s OR CAST(charter_id AS TEXT) = %s
                        LIMIT 1
                        """,
                        (query, query),
                    )
                    return cur.fetchone()
            conn = psycopg2.connect(
                host=os.getenv("DB_HOST", "localhost"),
                dbname=os.getenv("DB_NAME", "almsdata"),
                user=os.getenv("DB_USER", "postgres"),
                password=os.getenv("DB_PASSWORD", "***REDACTED***"),
            )
            with DatabaseContext(conn, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT charter_id, reserve_number, charter_date,
                           driver, vehicle, status, balance
                    FROM charters
                    WHERE reserve_number = %s OR CAST(charter_id AS TEXT) = %s
                    LIMIT 1
                    """,
                    (query, query),
                )
                return cur.fetchone()
        except Exception as e:
            logger.error(f"_fetch_exact_charter failed: {e}")
            return None

    def on_filter_changed(self) -> None:
        self.load_filtered_charters()

    def load_filtered_charters(self) -> object:
        """Apply filters and populate results table."""
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                where_clauses = []
                params = []

                def _to_pydate(qdate: QDate) -> object:
                    """Convert Qt QDate to Python date for psycopg2 parameters."""
                    return qdate.toPyDate() if qdate and qdate.isValid() else None

                charter_num = self.charter_num_input.text().strip()
                if charter_num:
                    where_clauses.append(
                        "(reserve_number ILIKE %s OR CAST(charter_id AS TEXT) ILIKE %s)"
                    )
                    params.extend([f"%{charter_num}%", f"%{charter_num}%"])

                if self.driver_combo.currentText() != "All":
                    where_clauses.append("driver = %s")
                    params.append(self.driver_combo.currentText())

                if self.vehicle_combo.currentText() != "All":
                    where_clauses.append("vehicle = %s")
                    params.append(self.vehicle_combo.currentText())

                if self.status_combo.currentText() != "All":
                    selected_status = self.status_combo.currentText().lower()
                    if selected_status == "booked":
                        where_clauses.append("LOWER(status) IN (%s, %s, %s, %s)")
                        params.extend([
                            "booked",
                            "booking in progress",
                            "confirmed",
                            "in progress",
                        ])
                    else:
                        where_clauses.append("LOWER(status) = %s")
                        params.append(selected_status)

                date_from_value = _to_pydate(self.date_from.date())
                if date_from_value:
                    where_clauses.append("charter_date >= %s")
                    params.append(date_from_value)

                date_to_value = _to_pydate(self.date_to.date())
                if date_to_value:
                    where_clauses.append("charter_date <= %s")
                    params.append(date_to_value)

                if self.balance_min.value() > 0:
                    where_clauses.append("balance >= %s")
                    params.append(self.balance_min.value())

                if self.unpaid_only.isChecked():
                    where_clauses.append("balance > 0")

                where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

                order_map = {
                    "Date (Newest)": "charter_date DESC",
                    "Date (Oldest)": "charter_date ASC",
                    "Balance (High)": "balance DESC",
                    "Balance (Low)": "balance ASC",
                    "Reserve #": "reserve_number ASC",
                    "Driver": "driver ASC",
                    "Vehicle": "vehicle ASC",
                    "Time": "pickup_time ASC",
                    "None": None,
                }

                order_parts = []
                for combo in [self.sort1_combo, self.sort2_combo, self.sort3_combo]:
                    sort_key = order_map.get(combo.currentText())
                    if sort_key:
                        order_parts.append(sort_key)

                order_sql = (
                    "ORDER BY " + ", ".join(order_parts)
                    if order_parts
                    else "ORDER BY charter_date DESC"
                )

                sql = f"""
                    SELECT charter_id, reserve_number, charter_date,
                           pickup_time, driver, vehicle, status,
                           total_amount_due, paid_amount, balance
                    FROM charters
                    WHERE {where_sql}
                    {order_sql}
                    LIMIT 500
                """
                cur.execute(sql, params)
                rows = cur.fetchall()

            self.results_table.setRowCount(len(rows))
            for row_idx, (
                cid,
                res_num,
                cdate,
                ctime,
                driver,
                vehicle,
                status,
                total,
                paid,
                balance,
            ) in enumerate(rows):
                items = [
                    str(res_num or ""),
                    str(cid or ""),
                    cdate.strftime("%Y-%m-%d") if cdate else "",
                    ctime.strftime("%H:%M") if ctime else "",
                    str(driver or ""),
                    str(vehicle or ""),
                    str(status or ""),
                    f"${float(total or 0):,.2f}",
                    f"${float(paid or 0):,.2f}",
                    f"${float(balance or 0):,.2f}",
                ]
                for col_idx, value in enumerate(items):
                    item = QTableWidgetItem(value)
                    if col_idx == 9 and float(balance or 0) > 0:
                        item.setBackground(QColor(255, 200, 200))
                    self.results_table.setItem(row_idx, col_idx, item)

            self.status_line.setText(f"{len(rows)} result(s) found")
        except Exception as e:
            logger.error(f"Failed to load filtered charters: {e}")
            QMessageBox.warning(self, "Error", f"Failed to load charters: {e}")

    def on_table_double_click(self, index) -> None:
        if not index.isValid():
            return
        row = index.row()
        charter_id_item = self.results_table.item(row, 1)
        if charter_id_item:
            self._open_charter(int(charter_id_item.text()))

    def _open_charter(self, charter_id: int) -> None:
        try:
            if hasattr(self.parent_widget, "load_charter_by_id"):
                self.parent_widget.load_charter_by_id(charter_id)
            elif hasattr(self.parent(), "load_charter_by_id"):
                self.parent().load_charter_by_id(charter_id)
        except Exception as e:
            logger.error(f"Could not open charter {charter_id}: {e}")
            QMessageBox.critical(self, "Error", f"Could not open charter: {e}")

    def _resolve_charter_id(self, query: str) -> object:
        """Return charter_id for a reserve number or charter ID string."""
        try:
            row = self._fetch_exact_charter(query)
            return row[0] if row else None
        except Exception as e:
            logger.error(f"_resolve_charter_id failed: {e}")
            return None

    def on_beverage_order(self) -> None:
        """Resolve charter from the input field and open the beverage dialog."""
        query = self.charter_input.text().strip()
        if not query:
            QMessageBox.warning(
                self,
                "No Charter",
                "Enter a reserve number or charter ID, then click Beverage Order.",
            )
            return

        charter_id = self._resolve_charter_id(query)
        if not charter_id:
            QMessageBox.information(self, "Not Found", f"No charter found for '{query}'.")
            return

        try:
            from beverage_ordering import BeverageSelectionDialog

            existing_beverages = []
            try:
                if hasattr(self.db, "cursor"):
                    with DatabaseContext(self.db, auto_commit=False) as cur:
                        cur.execute(
                            """
                            SELECT id, item_name, quantity,
                                   unit_price_charged, unit_our_cost,
                                   deposit_per_unit,
                                   line_amount_charged, line_cost, notes
                            FROM charter_beverages
                            WHERE charter_id = %s
                            ORDER BY created_at
                            """,
                            (charter_id,),
                        )
                        cols = [
                            "id",
                            "item_name",
                            "quantity",
                            "unit_price_charged",
                            "unit_our_cost",
                            "deposit_per_unit",
                            "line_amount_charged",
                            "line_cost",
                            "notes",
                        ]
                        existing_beverages = [dict(zip(cols, row)) for row in cur.fetchall()]
            except Exception as e:
                logger.warning(f"Could not load existing beverages: {e}")

            from PyQt6.QtWidgets import QDialog
            dialog = BeverageSelectionDialog(self.db, self, existing_beverages or None)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                totals = dialog.get_cart_totals()
                if totals.get("items"):
                    self._save_beverages(charter_id, totals)
                    QMessageBox.information(
                        self,
                        "Saved",
                        f"Beverage order saved for charter {query}.",
                    )
        except Exception as e:
            logger.error(f"Beverage order dialog failed: {e}")
            QMessageBox.critical(self, "Error", f"Could not open beverage dialog: {e}")

    def _save_beverages(self, charter_id: int, totals: dict) -> None:
        """Save beverage cart items to charter_beverages, replacing existing."""
        try:
            if hasattr(self.db, "cursor"):
                with DatabaseContext(self.db, auto_commit=True) as cur:
                    cur.execute(
                        "DELETE FROM charter_beverages WHERE charter_id = %s",
                        (charter_id,),
                    )
                    for item in totals["items"]:
                        cur.execute(
                            """
                            INSERT INTO charter_beverages
                                (charter_id, item_name, quantity,
                                 unit_price_charged, unit_our_cost,
                                 deposit_per_unit)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            """,
                            (
                                charter_id,
                                item.get("name", ""),
                                item.get("quantity", 1),
                                item.get("charged_price", 0),
                                item.get("our_cost", 0),
                                item.get("deposit_amount", 0) or 0,
                            ),
                        )
        except Exception as e:
            logger.error(f"_save_beverages failed: {e}")
            raise
