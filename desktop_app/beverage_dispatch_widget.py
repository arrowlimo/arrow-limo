# beverage_dispatch_widget.py
# Dispatcher beverage purchase management.
# Shows all charter beverage orders in a drill-down list.
# Dispatcher marks each cart as purchased (green) or not (red),
# and can print a shopping list to take to the store.

from __future__ import annotations

import os
from datetime import date, datetime

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDateEdit,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _neon_conn() -> object:
    """Open a fresh Neon connection."""
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


_COLS = [
    "Date", "Charter ID", "Reserve #", "Client",
    "Cart #", "# Items", "Our Cost", "Charged", "Notes", "Purchased",
]
_DATE_COL = 0
_CHARTER_COL = 1
_RESERVE_COL = 2
_CLIENT_COL = 3
_CART_COL = 4
_ITEMS_COL = 5
_COST_COL = 6
_CHARGED_COL = 7
_NOTES_COL = 8
_PURCH_COL = 9


def _beverage_write_enabled() -> bool:
    raw_value = os.environ.get(
        "BEVERAGE_WIDGET_WRITE_ENABLED",
        os.environ.get("RECEIPT_WIDGET_WRITE_ENABLED", "true"),
    )
    return str(raw_value).lower() in ("1", "true", "yes")


class BeverageDispatchWidget(QWidget):
    """Dispatcher view: all charter beverage orders, purchased toggle, shopping list print."""

    def __init__(self, db=None, parent=None) -> None:
        super().__init__(parent)
        self.db = db          # may be None; widget uses its own connection
        self.write_enabled = _beverage_write_enabled()
        self._rows: list[dict] = []   # raw data
        self._init_ui()
        self.reload()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # ── Toolbar ────────────────────────────────────────────────────
        bar = QHBoxLayout()

        bar.addWidget(QLabel("<b>🛒 Beverage Purchase Orders</b>"))
        bar.addSpacing(12)

        mode_text = (
            "🔓 Write Mode: ENABLED"
            if self.write_enabled
            else "🔒 Write Mode: DISABLED (read-only)"
        )
        mode_color = "#00aa00" if self.write_enabled else "#cc0000"
        self.write_mode_label = QLabel(mode_text)
        self.write_mode_label.setStyleSheet(
            f"color: {mode_color}; font-size: 8pt; font-weight: bold; "
            f"padding: 3px; border: 1px solid {mode_color}; border-radius: 3px; "
            f"background-color: {'#eaffea' if self.write_enabled else '#ffecec'};"
        )
        bar.addWidget(self.write_mode_label)

        bar.addWidget(QLabel("From:"))
        self.date_from = QDateEdit(QDate.currentDate().addDays(-30))
        self.date_from.setCalendarPopup(True)
        self.date_from.setMaximumWidth(110)
        bar.addWidget(self.date_from)

        bar.addWidget(QLabel("To:"))
        self.date_to = QDateEdit(QDate.currentDate().addDays(60))
        self.date_to.setCalendarPopup(True)
        self.date_to.setMaximumWidth(110)
        bar.addWidget(self.date_to)

        self.show_purchased_chk = QCheckBox("Show purchased")
        self.show_purchased_chk.setChecked(True)
        bar.addWidget(self.show_purchased_chk)

        reload_btn = QPushButton("🔄 Refresh")
        reload_btn.setFixedWidth(90)
        reload_btn.clicked.connect(self.reload)
        bar.addWidget(reload_btn)

        bar.addStretch()

        print_btn = QPushButton("🖨️ Print Shopping List")
        print_btn.setFixedWidth(170)
        print_btn.clicked.connect(self.print_shopping_list)
        bar.addWidget(print_btn)

        layout.addLayout(bar)

        # ── Summary row ────────────────────────────────────────────────
        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet("color: #555; font-size: 11px;")
        layout.addWidget(self.summary_label)

        # ── Main table ─────────────────────────────────────────────────
        self.table = QTableWidget()
        self.table.setColumnCount(len(_COLS))
        self.table.setHorizontalHeaderLabels(_COLS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(_CLIENT_COL, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(_NOTES_COL, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self.table, 1)

        # ── Action buttons ─────────────────────────────────────────────
        btn_row = QHBoxLayout()

        self.mark_bought_btn = QPushButton("✅ Mark Selected Purchased")
        self.mark_bought_btn.clicked.connect(lambda: self._toggle_purchased(True))
        btn_row.addWidget(self.mark_bought_btn)

        self.mark_not_btn = QPushButton("❌ Mark NOT Purchased")
        self.mark_not_btn.clicked.connect(lambda: self._toggle_purchased(False))
        btn_row.addWidget(self.mark_not_btn)

        btn_row.addStretch()

        self.edit_btn = QPushButton("✏️ Edit Cart")
        self.edit_btn.clicked.connect(self._edit_selected_cart)
        btn_row.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("🗑️ Delete Cart")
        self.delete_btn.setStyleSheet("color: #c00;")
        self.delete_btn.clicked.connect(self._delete_selected_cart)
        btn_row.addWidget(self.delete_btn)

        self._apply_write_mode_to_controls()

        layout.addLayout(btn_row)

    def _apply_write_mode_to_controls(self) -> None:
        for button in (
            getattr(self, "mark_bought_btn", None),
            getattr(self, "mark_not_btn", None),
            getattr(self, "delete_btn", None),
        ):
            if button is not None:
                button.setEnabled(self.write_enabled)
                if not self.write_enabled:
                    button.setToolTip("Write mode is disabled for beverage dispatch.")

    def _require_write_enabled(self) -> bool:
        if self.write_enabled:
            return True
        QMessageBox.warning(
            self,
            "Read-only Mode",
            "Beverage Dispatch write mode is disabled.",
        )
        return False

    # ------------------------------------------------------------------
    # DATA LOAD
    # ------------------------------------------------------------------
    def reload(self) -> None:
        """Load all beverage carts for charters in the date range."""
        d_from = self.date_from.date().toPyDate()
        d_to = self.date_to.date().toPyDate()
        show_purchased = self.show_purchased_chk.isChecked()

        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("""
                SELECT
                    c.charter_date,
                    cb.charter_id,
                    c.reserve_number,
                    COALESCE(c.client_display_name, '') AS client_name,
                    cb.id AS cart_id,
                    COUNT(cb.id) OVER (PARTITION BY cb.charter_id) AS cart_count,
                    COALESCE(SUM(cb.line_cost) OVER (PARTITION BY cb.charter_id), 0)
                        AS total_cost,
                    COALESCE(SUM(cb.line_amount_charged)
                        OVER (PARTITION BY cb.charter_id), 0) AS total_charged,
                    COALESCE(c.beverage_purchase_notes, '') AS notes,
                    COALESCE(c.beverages_purchased, FALSE) AS purchased,
                    cb.item_name,
                    cb.quantity,
                    cb.unit_our_cost,
                    cb.unit_price_charged,
                    cb.line_cost,
                    cb.line_amount_charged,
                    cb.notes AS item_notes
                FROM charter_beverages cb
                JOIN charters c ON c.charter_id = cb.charter_id
                WHERE c.charter_date BETWEEN %s AND %s
                  AND (%s OR NOT COALESCE(c.beverages_purchased, FALSE))
                ORDER BY c.charter_date, cb.charter_id, cb.id
            """, (d_from, d_to, show_purchased))
            rows = cur.fetchall()
            conn.close()
        except Exception as e:
            # Column may not exist yet — add it
            self._ensure_columns()
            self._rows = []
            self._populate_table()
            self.summary_label.setText(f"Error loading: {e}")
            return

        # Aggregate by charter (one row per charter in the summary table)
        charters: dict[int, dict] = {}
        items_by_charter: dict[int, list] = {}
        for row in rows:
            (charter_date, charter_id, reserve_num, client_name,
             cart_id, cart_count, total_cost, total_charged,
             notes, purchased,
             item_name, qty, unit_cost, unit_charged, line_cost,
             line_charged, item_notes) = row
            if charter_id not in charters:
                charters[charter_id] = {
                    "date": charter_date,
                    "charter_id": charter_id,
                    "reserve": reserve_num,
                    "client": client_name,
                    "cart_count": int(cart_count or 1),
                    "item_count": 0,
                    "total_cost": float(total_cost or 0),
                    "total_charged": float(total_charged or 0),
                    "notes": notes or "",
                    "purchased": bool(purchased),
                }
                items_by_charter[charter_id] = []
            charters[charter_id]["item_count"] += 1
            items_by_charter[charter_id].append({
                "item_name": item_name,
                "quantity": qty,
                "unit_cost": float(unit_cost or 0),
                "unit_charged": float(unit_charged or 0),
                "line_cost": float(line_cost or 0),
                "line_charged": float(line_charged or 0),
                "notes": item_notes or "",
            })

        self._rows = list(charters.values())
        self._items_by_charter = items_by_charter
        self._populate_table()

        total_carts = len(self._rows)
        pending = sum(1 for r in self._rows if not r["purchased"])
        total_cost = sum(r["total_cost"] for r in self._rows if not r["purchased"])
        self.summary_label.setText(
            f"{total_carts} charter(s) | {pending} pending purchase "
            f"| Estimated cost to buy: ${total_cost:,.2f}"
        )

    def _ensure_columns(self) -> None:
        """Add helper columns to charters table if missing."""
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(
                "ALTER TABLE charters ADD COLUMN IF NOT EXISTS "
                "beverages_purchased BOOLEAN NOT NULL DEFAULT FALSE"
            )
            cur.execute(
                "ALTER TABLE charters ADD COLUMN IF NOT EXISTS "
                "beverage_purchase_notes TEXT"
            )
            conn.commit()
            conn.close()
        except Exception as _e:
            logger.debug('Suppressed: %s', _e)
    def _populate_table(self) -> None:
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        for row_data in self._rows:
            r = self.table.rowCount()
            self.table.insertRow(r)

            d = row_data["date"]
            date_str = d.strftime("%Y-%m-%d") if isinstance(d, date) else str(d)

            items = [
                QTableWidgetItem(date_str),
                QTableWidgetItem(str(row_data["charter_id"])),
                QTableWidgetItem(str(row_data["reserve"] or "")),
                QTableWidgetItem(str(row_data["client"])),
                QTableWidgetItem(str(row_data["cart_count"])),
                QTableWidgetItem(str(row_data["item_count"])),
                QTableWidgetItem(f"${row_data['total_cost']:,.2f}"),
                QTableWidgetItem(f"${row_data['total_charged']:,.2f}"),
                QTableWidgetItem(str(row_data["notes"])),
            ]
            for col, item in enumerate(items):
                item.setData(Qt.ItemDataRole.UserRole, row_data["charter_id"])
                item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                self.table.setItem(r, col, item)

            # Purchased toggle button (green/red)
            purch = row_data["purchased"]
            purch_btn = QPushButton("✅ Purchased" if purch else "❌ Not Purchased")
            purch_btn.setStyleSheet(
                "background-color: #2e7d32; color: white; font-weight: bold;"
                if purch else
                "background-color: #c62828; color: white; font-weight: bold;"
            )
            charter_id = row_data["charter_id"]
            purch_btn.clicked.connect(
                lambda checked, cid=charter_id, current=purch:
                    self._toggle_purchased_for(cid, not current)
            )
            self.table.setCellWidget(r, _PURCH_COL, purch_btn)

        self.table.setSortingEnabled(True)

    # ------------------------------------------------------------------
    # ACTIONS
    # ------------------------------------------------------------------
    def _get_selected_charter_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _toggle_purchased(self, purchased: bool) -> None:
        if not self._require_write_enabled():
            return

        charter_id = self._get_selected_charter_id()
        if charter_id is None:
            QMessageBox.warning(self, "No selection", "Select a row first.")
            return
        self._toggle_purchased_for(charter_id, purchased)

    def _toggle_purchased_for(self, charter_id: int, purchased: bool) -> None:
        if not self._require_write_enabled():
            return

        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(
                "UPDATE charters SET beverages_purchased = %s "
                "WHERE charter_id = %s",
                (purchased, charter_id)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update: {e}")
            return
        self.reload()

    def _on_double_click(self, index) -> None:
        charter_id = self._get_selected_charter_id()
        if charter_id is None:
            return
        self._show_cart_detail(charter_id)

    def _edit_selected_cart(self) -> None:
        charter_id = self._get_selected_charter_id()
        if charter_id is None:
            QMessageBox.warning(self, "No selection", "Select a row first.")
            return
        self._show_cart_detail(charter_id)

    def _show_cart_detail(self, charter_id: int) -> None:
        items = self._items_by_charter.get(charter_id, [])
        row_data = next((r for r in self._rows if r["charter_id"] == charter_id), None)
        if row_data is None:
            return

        dlg = _CartDetailDialog(
            charter_id,
            row_data,
            items,
            self._get_conn,
            self.write_enabled,
            self,
        )
        dlg.exec()
        self.reload()

    def _delete_selected_cart(self) -> None:
        if not self._require_write_enabled():
            return

        charter_id = self._get_selected_charter_id()
        if charter_id is None:
            QMessageBox.warning(self, "No selection", "Select a row first.")
            return
        row_data = next((r for r in self._rows if r["charter_id"] == charter_id), None)
        reserve = row_data["reserve"] if row_data else str(charter_id)
        ans = QMessageBox.question(
            self, "Delete Beverage Cart",
            f"Delete ALL beverage items for charter {reserve}?\n"
            "This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(
                "DELETE FROM charter_beverages WHERE charter_id = %s",
                (charter_id,)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to delete: {e}")
            return
        self.reload()

    # ------------------------------------------------------------------
    # PRINT
    # ------------------------------------------------------------------
    def print_shopping_list(self) -> None:
        """Print all unpurchased beverage items as a shopping list with checkboxes."""
        unpurchased = [r for r in self._rows if not r["purchased"]]
        if not unpurchased:
            QMessageBox.information(
                self, "Nothing to buy",
                "All beverage carts are marked as purchased."
            )
            return

        text = "=" * 72 + "\n"
        text += "BEVERAGE SHOPPING LIST — DISPATCH\n"
        text += f"Printed: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        text += "=" * 72 + "\n\n"

        # Aggregate all items across unpurchased carts
        agg: dict[str, dict] = {}
        for row_data in unpurchased:
            charter_id = row_data["charter_id"]
            items = self._items_by_charter.get(charter_id, [])
            for item in items:
                name = item["item_name"] or "Unknown"
                if name not in agg:
                    agg[name] = {"qty": 0, "cost": 0.0, "charters": []}
                agg[name]["qty"] += item["quantity"]
                agg[name]["cost"] += item["line_cost"]
                agg[name]["charters"].append(str(row_data["reserve"]))

        text += f"{'☐':<3} {'Item':<40} {'Qty':>6} {'Est. Cost':>12}\n"
        text += "-" * 72 + "\n"
        total_cost = 0.0
        for name, data in sorted(agg.items()):
            text += (
                f"{'☐':<3} {name:<40.40} {data['qty']:>6} "
                f"${data['cost']:>10.2f}\n"
            )
            text += f"    Charters: {', '.join(set(data['charters']))}\n"
            total_cost += data["cost"]
        text += "-" * 72 + "\n"
        text += f"{'TOTAL ESTIMATED COST':>52} ${total_cost:>10.2f}\n"
        text += "=" * 72 + "\n\n"

        text += "PER-CHARTER DETAIL:\n"
        text += "-" * 72 + "\n"
        for row_data in unpurchased:
            charter_id = row_data["charter_id"]
            d = row_data["date"]
            date_str = d.strftime("%Y-%m-%d") if isinstance(d, date) else str(d)
            text += (
                f"\nCharter {row_data['reserve']} — "
                f"{row_data['client']} — {date_str}\n"
            )
            items = self._items_by_charter.get(charter_id, [])
            for item in items:
                text += (
                    f"  {'☐'} {item['item_name']:<38.38} "
                    f"x{item['quantity']:>3}  "
                    f"${item['line_cost']:>8.2f}"
                )
                text += "\n"

        # Show in print dialog
        try:
            # Use a simple print-preview dialog
            _show_text_print_dialog(self, "Shopping List", text)
        except Exception:
            QMessageBox.information(self, "Shopping List", text)

    # ------------------------------------------------------------------
    # DB
    # ------------------------------------------------------------------
    def _get_conn(self) -> object:
        """Get a database connection."""
        if self.db is not None:
            try:
                return self.db.conn
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
        return _neon_conn()


# ---------------------------------------------------------------------------
# Cart detail dialog (drill-down)
# ---------------------------------------------------------------------------

class _CartDetailDialog(QDialog):
    def __init__(self, charter_id: int, row_data: dict, items: list,
                 get_conn_fn, write_enabled: bool, parent=None) -> None:
        super().__init__(parent)
        self.charter_id = charter_id
        self.row_data = row_data
        self.items = items
        self._get_conn = get_conn_fn
        self.write_enabled = write_enabled
        self.setWindowTitle(
            f"Beverage Cart — Charter {row_data['reserve']} "
            f"({row_data['client']})"
        )
        self.resize(700, 500)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Header
        d = self.row_data["date"]
        date_str = d.strftime("%Y-%m-%d") if isinstance(d, date) else str(d)
        hdr = QLabel(
            f"<b>Charter {self.row_data['reserve']}</b> — "
            f"{self.row_data['client']} — {date_str}"
        )
        hdr.setStyleSheet("font-size: 13px;")
        layout.addWidget(hdr)

        # Items table
        self.tbl = QTableWidget()
        self.tbl.setColumnCount(7)
        self.tbl.setHorizontalHeaderLabels([
            "Item", "Qty", "Our Cost/Unit", "Line Cost",
            "Charged/Unit", "Line Charged", "Notes",
        ])
        self.tbl.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self.tbl.horizontalHeader().setSectionResizeMode(
            6, QHeaderView.ResizeMode.Stretch)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._load_items()
        layout.addWidget(self.tbl)

        # Totals
        total_cost = sum(i["line_cost"] for i in self.items)
        total_charged = sum(i["line_charged"] for i in self.items)
        profit = total_charged - total_cost
        totals_lbl = QLabel(
            f"Our Cost: <b>${total_cost:,.2f}</b>   "
            f"Charged to Client: <b>${total_charged:,.2f}</b>   "
            f"Profit: <b style='color:{'green' if profit >= 0 else 'red'}'>"
            f"${profit:,.2f}</b>"
        )
        totals_lbl.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(totals_lbl)

        # Notes
        notes_row = QHBoxLayout()
        notes_row.addWidget(QLabel("Purchase notes:"))
        self.notes_edit = QLineEdit(self.row_data.get("notes", ""))
        self.notes_edit.setPlaceholderText("e.g. Buy at Costco, verify quantities...")
        notes_row.addWidget(self.notes_edit, 1)
        layout.addLayout(notes_row)

        # Purchased toggle
        purch = self.row_data.get("purchased", False)
        self.purch_chk = QCheckBox("Marked as PURCHASED")
        self.purch_chk.setChecked(purch)
        self.purch_chk.setStyleSheet(
            "font-weight: bold; color: #2e7d32;" if purch
            else "font-weight: bold; color: #c62828;"
        )
        layout.addWidget(self.purch_chk)

        # Buttons
        btn_row = QHBoxLayout()
        self.save_btn = QPushButton("💾 Save Notes & Status")
        self.save_btn.clicked.connect(self._save)
        self.save_btn.setEnabled(self.write_enabled)
        if not self.write_enabled:
            self.save_btn.setToolTip("Write mode is disabled for beverage dispatch.")
            self.notes_edit.setReadOnly(True)
            self.purch_chk.setEnabled(False)
        btn_row.addWidget(self.save_btn)

        print_btn = QPushButton("🖨️ Print Cart")
        print_btn.clicked.connect(self._print_cart)
        btn_row.addWidget(print_btn)

        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _load_items(self) -> None:
        self.tbl.setRowCount(0)
        for item in self.items:
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            vals = [
                item["item_name"],
                str(item["quantity"]),
                f"${item['unit_cost']:.2f}",
                f"${item['line_cost']:.2f}",
                f"${item['unit_charged']:.2f}",
                f"${item['line_charged']:.2f}",
                item["notes"],
            ]
            for c, v in enumerate(vals):
                self.tbl.setItem(r, c, QTableWidgetItem(v))

    def _save(self) -> None:
        if not self.write_enabled:
            QMessageBox.warning(
                self,
                "Read-only Mode",
                "Beverage Dispatch write mode is disabled.",
            )
            return

        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(
                "UPDATE charters SET beverages_purchased = %s, "
                "beverage_purchase_notes = %s WHERE charter_id = %s",
                (self.purch_chk.isChecked(), self.notes_edit.text(), self.charter_id)
            )
            conn.commit()
            conn.close()
            QMessageBox.information(self, "Saved", "Cart status saved.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")

    def _print_cart(self) -> None:
        d = self.row_data["date"]
        date_str = d.strftime("%Y-%m-%d") if isinstance(d, date) else str(d)
        text = "=" * 60 + "\n"
        text += "BEVERAGE CART — DISPATCH PURCHASE\n"
        text += f"Charter: {self.row_data['reserve']}  Client: {self.row_data['client']}\n"
        text += f"Date: {date_str}   Printed: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        text += "=" * 60 + "\n\n"
        text += f"{'☐':<3} {'Item':<36} {'Qty':>4} {'Cost':>10}\n"
        text += "-" * 60 + "\n"
        total_cost = 0.0
        for item in self.items:
            text += (
                f"{'☐':<3} {item['item_name']:<36.36} "
                f"{item['quantity']:>4}  ${item['line_cost']:>8.2f}"
            )
            text += "\n"
            total_cost += item["line_cost"]
        text += "-" * 60 + "\n"
        text += f"Total to spend: ${total_cost:,.2f}\n"
        if self.notes_edit.text():
            text += f"\nNotes: {self.notes_edit.text()}\n"
        text += "=" * 60 + "\n"
        _show_text_print_dialog(self, "Beverage Cart", text)


# ---------------------------------------------------------------------------
# Minimal print-preview helper (reuses the app's print dialog if available)
# ---------------------------------------------------------------------------

def _show_text_print_dialog(parent: QWidget, title: str, text: str) -> None:
    """Show a simple text preview + print dialog."""
    from PyQt6.QtGui import QTextDocument
    from PyQt6.QtPrintSupport import QPrintDialog, QPrinter
    from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QPlainTextEdit

    dlg = QDialog(parent)
    dlg.setWindowTitle(f"Print Preview — {title}")
    dlg.resize(700, 550)
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
        printer = QPrinter()
        pdlg = QPrintDialog(printer, dlg)
        if pdlg.exec():
            doc = QTextDocument()
            doc.setPlainText(text)
            doc.print(printer)

    print_btn.clicked.connect(do_print)
    close_btn.clicked.connect(dlg.reject)
    dlg.exec()
