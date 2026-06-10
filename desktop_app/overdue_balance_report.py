"""
Overdue Balance Aging Report
Displays outstanding charter balances bucketed by days past charter date.
Buckets: Current (0-30d), 31-60d, 61-90d, 90d+
"""
import logging
from datetime import date

from db_error_handling import DatabaseContext
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QFont
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

BUCKETS = [
    ("0-30 days",  0,   30,  "#ffffff"),
    ("31-60 days", 31,  60,  "#fff3cd"),
    ("61-90 days", 61,  90,  "#ffd9b3"),
    ("90+ days",   91, 9999, "#f8d7da"),
]


class OverdueBalanceReportWidget(QWidget):
    def __init__(self, db, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Header row
        hdr = QHBoxLayout()
        title = QLabel("Overdue Balance Aging Report")
        title.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        hdr.addWidget(title)
        hdr.addStretch()
        btn = QPushButton("⟳ Refresh")
        btn.clicked.connect(self.refresh)
        hdr.addWidget(btn)
        layout.addLayout(hdr)

        # Bucket summary labels
        self._bucket_labels: list[QLabel] = []
        bucket_row = QHBoxLayout()
        for name, *_ in BUCKETS:
            lbl = QLabel(f"{name}: $0.00")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("border:1px solid #aaa; padding:4px; border-radius:4px;")
            self._bucket_labels.append(lbl)
            bucket_row.addWidget(lbl)
        layout.addLayout(bucket_row)

        # Detail table
        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels([
            "Reserve #", "Client", "Charter Date", "Days Overdue",
            "Amount Due", "Amount Paid", "Balance Owing",
        ])
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self._table)

    def refresh(self) -> None:
        self._table.setRowCount(0)
        rows = self._fetch()
        today = date.today()
        bucket_totals = [0.0] * len(BUCKETS)

        for row in rows:
            (reserve_number, client_name, charter_date,
             total_due, total_paid, balance) = row

            if isinstance(charter_date, str):
                try:
                    from datetime import datetime
                    charter_date = datetime.strptime(charter_date, "%Y-%m-%d").date()
                except Exception:
                    charter_date = None

            days_overdue = (today - charter_date).days if charter_date else 0
            balance = float(balance or 0)
            total_due = float(total_due or 0)
            total_paid = float(total_paid or 0)

            # Find bucket
            row_color = "#ffffff"
            for i, (_, lo, hi, color) in enumerate(BUCKETS):
                if lo <= days_overdue <= hi:
                    bucket_totals[i] += balance
                    row_color = color
                    break

            r = self._table.rowCount()
            self._table.insertRow(r)
            values = [
                reserve_number or "",
                client_name or "",
                charter_date.strftime("%Y-%m-%d") if charter_date else "",
                str(days_overdue),
                f"${total_due:.2f}",
                f"${total_paid:.2f}",
                f"${balance:.2f}",
            ]
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setBackground(QBrush(QColor(row_color)))
                if col in (4, 5, 6):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self._table.setItem(r, col, item)

        for i, (name, *_) in enumerate(BUCKETS):
            self._bucket_labels[i].setText(f"{name}: ${bucket_totals[i]:,.2f}")

    def _fetch(self) -> list:
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute("""
                    SELECT
                        c.reserve_number,
                        COALESCE(c.client_display_name, cl.company_name, cl.client_name, 'Unknown') AS client_name,
                        c.charter_date::date,
                        COALESCE(c.total_amount_due, c.grand_total, 0)      AS total_due,
                        COALESCE(c.amount_paid, c.paid_amount, 0)           AS total_paid,
                        COALESCE(c.balance_owing, c.balance,
                            COALESCE(c.total_amount_due, c.grand_total, 0)
                            - COALESCE(c.amount_paid, c.paid_amount, 0), 0) AS balance_owing
                    FROM charters c
                    LEFT JOIN clients cl ON c.client_id = cl.client_id
                    WHERE
                        c.charter_date < CURRENT_DATE
                        AND COALESCE(c.balance_owing, c.balance,
                                COALESCE(c.total_amount_due, c.grand_total, 0)
                                - COALESCE(c.amount_paid, c.paid_amount, 0), 0) > 0.01
                        AND COALESCE(c.payment_status, c.status, '') NOT IN ('Cancelled', 'Quote')
                    ORDER BY c.charter_date ASC
                """)
                return cur.fetchall()
        except Exception as e:
            logger.error(f"Overdue balance report fetch failed: {e}")
            return []
