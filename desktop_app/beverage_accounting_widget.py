# beverage_accounting_widget.py
# Accounting view: beverage cost vs revenue vs profit report.
# Queries charter_beverages joined to charters for a date range.

from __future__ import annotations

from datetime import date

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


def _neon_conn() -> object:
    import os

    import psycopg2
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "neondb"),
        user=os.getenv("DB_USER", "neondb_owner"),
        password=os.getenv("DB_PASSWORD", ""),
        sslmode=os.getenv("DB_SSLMODE", "require"),
    )


class BeverageAccountingWidget(QWidget):
    """Accounting: beverage cost purchased vs charged to client vs profit."""

    def __init__(self, db=None, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self._rows: list[dict] = []
        self._init_ui()
        self.run_report()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # ── Toolbar ────────────────────────────────────────────────────
        bar = QHBoxLayout()
        bar.addWidget(QLabel("<b>🍷 Beverage Cost vs Revenue</b>"))
        bar.addSpacing(12)

        bar.addWidget(QLabel("From:"))
        self.date_from = QDateEdit(QDate(QDate.currentDate().year(), 1, 1))
        self.date_from.setCalendarPopup(True)
        self.date_from.setMaximumWidth(110)
        bar.addWidget(self.date_from)

        bar.addWidget(QLabel("To:"))
        self.date_to = QDateEdit(QDate.currentDate())
        self.date_to.setCalendarPopup(True)
        self.date_to.setMaximumWidth(110)
        bar.addWidget(self.date_to)

        bar.addWidget(QLabel("Group by:"))
        self.group_combo = QComboBox()
        self.group_combo.addItems(["Item", "Charter", "Month"])
        self.group_combo.setMaximumWidth(100)
        bar.addWidget(self.group_combo)

        run_btn = QPushButton("▶ Run Report")
        run_btn.setFixedWidth(110)
        run_btn.clicked.connect(self.run_report)
        bar.addWidget(run_btn)

        bar.addStretch()

        export_btn = QPushButton("🖨️ Print Report")
        export_btn.setFixedWidth(120)
        export_btn.clicked.connect(self.print_report)
        bar.addWidget(export_btn)

        layout.addLayout(bar)

        # ── Summary boxes ──────────────────────────────────────────────
        summ = QHBoxLayout()
        self._make_summary_box(summ, "Our Cost (Purchased)", "cost_lbl", "#c62828")
        self._make_summary_box(summ, "Charged to Clients", "charged_lbl", "#1565c0")
        self._make_summary_box(summ, "Gross Profit", "profit_lbl", "#2e7d32")
        self._make_summary_box(summ, "Margin %", "margin_lbl", "#6a1b9a")
        layout.addLayout(summ)

        # ── Main table ─────────────────────────────────────────────────
        self.table = QTableWidget()
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table, 1)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #555; font-size: 11px;")
        layout.addWidget(self.status_label)

    def _make_summary_box(self, bar: QHBoxLayout, title: str,
                          attr: str, color: str) -> None:
        box = QGroupBox(title)
        bl = QVBoxLayout(box)
        lbl = QLabel("$0.00")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {color};")
        bl.addWidget(lbl)
        setattr(self, attr, lbl)
        bar.addWidget(box, 1)

    # ------------------------------------------------------------------
    # REPORT
    # ------------------------------------------------------------------
    def run_report(self) -> None:
        d_from = self.date_from.date().toPyDate()
        d_to = self.date_to.date().toPyDate()
        group = self.group_combo.currentText()

        try:
            conn = self._get_conn()
            cur = conn.cursor()

            if group == "Item":
                cur.execute("""
                    SELECT
                        cb.item_name,
                        SUM(cb.quantity) AS total_qty,
                        SUM(cb.line_cost) AS total_cost,
                        SUM(cb.line_amount_charged) AS total_charged,
                        SUM(cb.line_amount_charged) - SUM(cb.line_cost) AS profit,
                        COUNT(DISTINCT cb.charter_id) AS charter_count
                    FROM charter_beverages cb
                    JOIN charters c ON c.charter_id = cb.charter_id
                    WHERE c.charter_date BETWEEN %s AND %s
                    GROUP BY cb.item_name
                    ORDER BY SUM(cb.line_cost) DESC
                """, (d_from, d_to))
                cols = ["Item", "Qty Sold", "Our Cost", "Charged",
                        "Profit", "# Charters"]
                rows = cur.fetchall()

            elif group == "Charter":
                cur.execute("""
                    SELECT
                        c.charter_date,
                        c.reserve_number,
                        COALESCE(cl.display_name, c.client_display_name, '') AS client,
                        COUNT(cb.id) AS item_count,
                        SUM(cb.line_cost) AS total_cost,
                        SUM(cb.line_amount_charged) AS total_charged,
                        SUM(cb.line_amount_charged) - SUM(cb.line_cost) AS profit
                    FROM charter_beverages cb
                    JOIN charters c ON c.charter_id = cb.charter_id
                    LEFT JOIN clients cl ON cl.client_id = c.client_id
                    WHERE c.charter_date BETWEEN %s AND %s
                    GROUP BY c.charter_id, c.charter_date, c.reserve_number,
                             cl.display_name, c.client_display_name
                    ORDER BY c.charter_date DESC
                """, (d_from, d_to))
                cols = ["Date", "Reserve #", "Client", "# Items",
                        "Our Cost", "Charged", "Profit"]
                rows = cur.fetchall()

            else:  # Month
                cur.execute("""
                    SELECT
                        TO_CHAR(c.charter_date, 'YYYY-MM') AS month,
                        SUM(cb.quantity) AS total_qty,
                        SUM(cb.line_cost) AS total_cost,
                        SUM(cb.line_amount_charged) AS total_charged,
                        SUM(cb.line_amount_charged) - SUM(cb.line_cost) AS profit,
                        COUNT(DISTINCT cb.charter_id) AS charter_count
                    FROM charter_beverages cb
                    JOIN charters c ON c.charter_id = cb.charter_id
                    WHERE c.charter_date BETWEEN %s AND %s
                    GROUP BY TO_CHAR(c.charter_date, 'YYYY-MM')
                    ORDER BY month DESC
                """, (d_from, d_to))
                cols = ["Month", "Qty", "Our Cost", "Charged",
                        "Profit", "# Charters"]
                rows = cur.fetchall()

            conn.close()
        except Exception as e:
            self.status_label.setText(f"Error: {e}")
            return

        # Update table
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        if len(cols) > 2:
            hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            if group == "Charter":
                hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        total_cost = 0.0
        total_charged = 0.0

        for row in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            for c_idx, val in enumerate(row):
                if isinstance(val, float) or (
                    isinstance(val, (int,)) and cols[c_idx] in (
                        "Our Cost", "Charged", "Profit"
                    )
                ):
                    text = f"${float(val):,.2f}"
                elif val is None:
                    text = ""
                elif isinstance(val, date):
                    text = val.strftime("%Y-%m-%d")
                else:
                    text = str(val)

                item = QTableWidgetItem(text)
                item.setFlags(
                    Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
                )
                # Colour profit column green/red
                if cols[c_idx] == "Profit" and isinstance(val, (int, float)):
                    item.setForeground(
                        QColor("#2e7d32") if float(val) >= 0
                        else QColor("#c62828")
                    )
                self.table.setItem(r, c_idx, item)

            # Accumulate totals (cost & charged are always 3rd and 4th col
            # for Item/Month, 5th and 6th for Charter)
            if group == "Charter":
                total_cost += float(row[4] or 0)
                total_charged += float(row[5] or 0)
            else:
                total_cost += float(row[2] or 0)
                total_charged += float(row[3] or 0)

        self.table.setSortingEnabled(True)

        profit = total_charged - total_cost
        margin = (profit / total_charged * 100) if total_charged else 0.0

        self.cost_lbl.setText(f"${total_cost:,.2f}")
        self.charged_lbl.setText(f"${total_charged:,.2f}")
        self.profit_lbl.setText(f"${profit:,.2f}")
        self.profit_lbl.setStyleSheet(
            f"color: {'#2e7d32' if profit >= 0 else '#c62828'};"
        )
        self.margin_lbl.setText(f"{margin:.1f}%")
        self.margin_lbl.setStyleSheet(
            f"color: {'#2e7d32' if margin >= 0 else '#c62828'};"
        )

        self.status_label.setText(
            f"{self.table.rowCount()} row(s) | "
            f"Period: {d_from} to {d_to}"
        )
        self._last_cols = cols
        self._last_rows = rows

    # ------------------------------------------------------------------
    # PRINT
    # ------------------------------------------------------------------
    def print_report(self) -> None:
        from datetime import datetime
        group = self.group_combo.currentText()
        d_from = self.date_from.date().toPyDate()
        d_to = self.date_to.date().toPyDate()

        text = "=" * 80 + "\n"
        text += "BEVERAGE ACCOUNTING REPORT\n"
        text += f"Group by: {group}   Period: {d_from} to {d_to}\n"
        text += f"Printed: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        text += "=" * 80 + "\n\n"

        cols = getattr(self, '_last_cols', [])
        rows = getattr(self, '_last_rows', [])

        if cols:
            header = "  ".join(f"{c:<16}" for c in cols)
            text += header + "\n"
            text += "-" * 80 + "\n"
            for row in rows:
                line = ""
                for val in row:
                    if isinstance(val, float):
                        line += f"${float(val):>14,.2f}  "
                    elif val is None:
                        line += f"{'':>16}  "
                    elif isinstance(val, date):
                        line += f"{val.strftime('%Y-%m-%d'):<16}  "
                    else:
                        line += f"{val!s:<16}  "
                text += line + "\n"

        text += "-" * 80 + "\n"
        text += f"Total Our Cost:    ${float(self.cost_lbl.text().replace('$','').replace(',','') or 0):,.2f}\n"
        text += f"Total Charged:     ${float(self.charged_lbl.text().replace('$','').replace(',','') or 0):,.2f}\n"
        text += f"Gross Profit:      {self.profit_lbl.text()}\n"
        text += f"Margin:            {self.margin_lbl.text()}\n"
        text += "=" * 80 + "\n"

        dlg = QDialog(self)
        dlg.setWindowTitle("Beverage Accounting Report")
        dlg.resize(800, 560)
        vl = QVBoxLayout(dlg)
        preview = QPlainTextEdit()
        preview.setReadOnly(True)
        preview.setPlainText(text)
        preview.setFont(QFont("Courier New", 9))
        vl.addWidget(preview)
        bb = QDialogButtonBox()
        print_btn = bb.addButton("🖨️ Print", QDialogButtonBox.ButtonRole.AcceptRole)
        close_btn = bb.addButton("Close", QDialogButtonBox.ButtonRole.RejectRole)
        vl.addWidget(bb)

        def do_print() -> None:
            from PyQt6.QtGui import QTextDocument
            from PyQt6.QtPrintSupport import QPrintDialog, QPrinter
            printer = QPrinter()
            pdlg = QPrintDialog(printer, dlg)
            if pdlg.exec():
                doc = QTextDocument()
                doc.setPlainText(text)
                doc.print(printer)

        print_btn.clicked.connect(do_print)
        close_btn.clicked.connect(dlg.reject)
        dlg.exec()

    # ------------------------------------------------------------------
    # DB
    # ------------------------------------------------------------------
    def _get_conn(self) -> object:
        if self.db is not None:
            try:
                return self.db.conn
            except Exception:
                pass
        return _neon_conn()
