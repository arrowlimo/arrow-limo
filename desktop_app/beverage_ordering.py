"""
Beverage Ordering System
Shopping cart for dispatcher to add beverages to charter
Email paste-in functionality, automatic pricing with GST
Cost vs. charged tracking for accounting
"""

import logging
from datetime import datetime

from db_error_handling import DatabaseContext
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

logger = logging.getLogger(__name__)


class BeverageOrderingSystem:
    """
    Manage beverage ordering with cost vs. marked-up pricing
    Includes GST calculation on charged amount
    """

    def __init__(self, db) -> None:
        self.db = db
        self._beverage_columns = set()
        self.beverages = self._load_beverages_from_db()
        self.gst_rate = 0.05
        self.shopping_cart = []  # List of beverage items with qty

    def _load_beverages_from_db(self) -> object:
        """Load beverage list, preferring beverage_products (full catalog)."""

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name IN ('beverage_products', 'beverages')
                    """
                )
                tables = {row[0] for row in cur.fetchall()}

                use_products = False
                if "beverage_products" in tables:
                    cur.execute("SELECT COUNT(*) FROM beverage_products")
                    use_products = (cur.fetchone()[0] or 0) > 0

                if use_products:
                    cur.execute(
                        """
                        SELECT bp.item_id,
                               bp.item_name AS name,
                               COALESCE(bp.category, 'Other') AS category,
                               COALESCE(bp.our_cost, 0) AS our_cost,
                               COALESCE(bp.unit_price, 0) AS charged_price,
                               COALESCE(bp.gst_included, true) AS gst_included
                        FROM beverage_products bp
                        ORDER BY bp.category, bp.item_name
                        """
                    )
                    rows = cur.fetchall()
                else:
                    cur.execute(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_name = 'beverages'
                        """
                    )
                    self._beverage_columns = {row[0] for row in cur.fetchall()}

                    if not self._beverage_columns:
                        raise RuntimeError(
                            "No beverage table found (beverage_products/beverages)"
                        )

                    price_col = (
                        "charged_price"
                        if "charged_price" in self._beverage_columns
                        else "price"
                    )
                    name_col = (
                        "name"
                        if "name" in self._beverage_columns
                        else "beverage_name"
                    )
                    active_col = (
                        "active"
                        if "active" in self._beverage_columns
                        else "is_active"
                    )
                    gst_expr = (
                        "COALESCE(b.gst_included, true)"
                        if "gst_included" in self._beverage_columns
                        else "true"
                    )
                    cost_expr = (
                        "COALESCE(b.our_cost, 0)"
                        if "our_cost" in self._beverage_columns
                        else (
                            "COALESCE(b.cost, 0)"
                            if "cost" in self._beverage_columns
                            else "0"
                        )
                    )

                    cur.execute(
                        f"""
                        SELECT b.beverage_id,
                               b.{name_col} AS name,
                               COALESCE(b.category, 'Other') AS category,
                               {cost_expr} AS our_cost,
                               COALESCE(b.{price_col}, 0) AS charged_price,
                               {gst_expr} AS gst_included
                        FROM beverages b
                        WHERE COALESCE(b.{active_col}, true) = true
                        ORDER BY b.category, b.{name_col}
                        """
                    )
                    rows = cur.fetchall()

            beverages = []
            for row in rows:
                beverages.append(
                    {
                        "id": row[0],
                        "name": row[1],
                        "category": row[2],
                        "our_cost": float(row[3] or 0),
                        "charged_price": float(row[4] or 0),
                        "gst_included": bool(row[5]),
                        "image_path": None,
                    }
                )
            return beverages
        except Exception as e:
            logger.error(f"Error loading beverages: {e}")
            return []

    def add_to_cart(self, beverage_id, quantity, notes="") -> None:
        """Add beverage to shopping cart"""
        bev = next((b for b in self.beverages if b["id"] == beverage_id), None)
        if not bev:
            raise ValueError(f"Beverage ID {beverage_id} not found")

        gst_per_unit = 0
        if bev["gst_included"]:
            gst_per_unit = (
                bev["charged_price"] * self.gst_rate / (1 + self.gst_rate)
            )

        cart_item = {
            "beverage_id": beverage_id,
            "name": bev["name"],
            "quantity": quantity,
            "our_cost": bev["our_cost"],
            "charged_price": bev["charged_price"],
            "gst_included": bev["gst_included"],
            "notes": notes,
            "item_cost": bev["our_cost"] * quantity,
            "item_charged": bev["charged_price"] * quantity,
            "item_gst": gst_per_unit * quantity,
        }

        self.shopping_cart.append(cart_item)

    def remove_from_cart(self, index) -> None:
        """Remove item from cart"""
        if 0 <= index < len(self.shopping_cart):
            self.shopping_cart.pop(index)

    def get_cart_totals(self) -> object:
        """Get cost vs. charged totals"""
        if not self.shopping_cart:
            return {
                "our_total_cost": 0,
                "charged_total": 0,
                "gst_total": 0,
                "deposit_total": 0,
                "guest_total": 0,
                "profit": 0,
                "items": [],
            }

        our_cost_sum = sum(item["item_cost"] for item in self.shopping_cart)
        charged_sum = sum(item["item_charged"] for item in self.shopping_cart)
        gst_sum = sum(item["item_gst"] for item in self.shopping_cart)
        deposit_sum = 0.0
        profit = charged_sum - our_cost_sum
        guest_sum = charged_sum

        return {
            "our_total_cost": our_cost_sum,
            "charged_total": charged_sum,
            "gst_total": gst_sum,
            "deposit_total": deposit_sum,
            "guest_total": guest_sum,
            "profit": profit,
            "items": self.shopping_cart,
        }

    def parse_email_list(self, email_text) -> object:
        """
        Parse email recipient list and auto-add beverages
        Format can be:
        - Email addresses (find person in database)
        - Names (find person by first/last name)
        - CSV with headers: Name, Email, Beverage
        """
        results = []
        seen = set()
        for line in email_text.split("\n"):
            line = line.strip()
            if not line:
                continue

            token = line.split(",")[0].strip()
            lookup_email = token if "@" in token else None
            lookup_name = token if "@" not in token else None

            record = {
                "raw": line,
                "name": token,
                "email": "",
            }

            try:
                with DatabaseContext(self.db, auto_commit=False) as cur:
                    if lookup_email:
                        cur.execute(
                            """
                            SELECT COALESCE(client_name, ''), COALESCE(email, '')
                            FROM clients
                            WHERE LOWER(COALESCE(email, '')) = LOWER(%s)
                            LIMIT 1
                            """,
                            (lookup_email,),
                        )
                    else:
                        cur.execute(
                            """
                            SELECT COALESCE(client_name, ''), COALESCE(email, '')
                            FROM clients
                            WHERE LOWER(COALESCE(client_name, '')) = LOWER(%s)
                               OR LOWER(COALESCE(company_name, '')) = LOWER(%s)
                            LIMIT 1
                            """,
                            (lookup_name, lookup_name),
                        )

                    row = cur.fetchone()
                    if row:
                        record["name"] = row[0] or record["name"]
                        record["email"] = row[1] or lookup_email or ""
                    elif lookup_email:
                        record["email"] = lookup_email
            except Exception as err:
                logger.warning(f"parse_email_list lookup failed for '{token}': {err}")
                if lookup_email:
                    record["email"] = lookup_email

            dedupe_key = (record["name"].strip().lower(), record["email"].strip().lower())
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            results.append(record)

        return results


class BeverageOrderingDialog(QDialog):
    """
    Interactive beverage ordering interface
    - Search/browse beverages
    - Add to cart
    - Email paste-in
    - Adjust quantities and notes
    - Cost vs. charged summary for accounting
    """

    cart_updated = pyqtSignal(dict)

    def __init__(self, db, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self.system = BeverageOrderingSystem(db)
        self._suppress_cart_refresh = False

        self.setWindowTitle("Beverage Order Management")
        self.setGeometry(100, 100, 1400, 900)

        layout = QVBoxLayout()

        # Title
        title = QLabel("🍾 Beverage Order Management")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # Top section: Browse beverages
        browse_group = QGroupBox("Available Beverages")
        browse_layout = QHBoxLayout()

        # Category filter
        browse_layout.addWidget(QLabel("Category:"))
        self.category_filter = QComboBox()
        self.category_filter.addItems(
            [
                "All",
                "Beer",
                "Wine",
                "Spirits",
                "Non-Alcoholic",
                "Mixers",
                "Ice",
                "Glassware",
            ]
        )
        self.category_filter.currentTextChanged.connect(
            self.update_beverage_list
        )
        browse_layout.addWidget(self.category_filter)

        # Search
        browse_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search beverages...")
        self.search_input.textChanged.connect(self.update_beverage_list)
        browse_layout.addWidget(self.search_input)

        browse_group.setLayout(browse_layout)
        layout.addWidget(browse_group)

        # Beverage list table (images removed)
        self.beverage_list = QTableWidget()
        self.beverage_list.setColumnCount(6)
        self.beverage_list.setHorizontalHeaderLabels(
            [
                "Name",
                "Category",
                "Our Cost",
                "Charged Price",
                "Qty",
                "Add to Cart",
            ]
        )
        self.beverage_list.doubleClicked.connect(self.add_selected_beverage)
        layout.addWidget(self.beverage_list)

        self.update_beverage_list()

        # Middle section: Email paste-in
        email_group = QGroupBox("Email List (Optional - Auto-add beverages)")
        email_layout = QVBoxLayout()

        email_info = QLabel(
            "Paste email list to find guests and auto-add beverages:\nOne"
            "email/name per line"
        )
        email_layout.addWidget(email_info)

        self.email_paste = QTextEdit()
        self.email_paste.setPlaceholderText(
            "name@example.com\nJohn Smith\n..."
        )
        self.email_paste.setMaximumHeight(80)
        email_layout.addWidget(self.email_paste)

        self.parse_email_btn = QPushButton("🔍 Parse Emails & Add Beverages")
        self.parse_email_btn.clicked.connect(self.parse_email_list)
        email_layout.addWidget(self.parse_email_btn)

        email_group.setLayout(email_layout)
        layout.addWidget(email_group)

        # Shopping cart
        cart_label = QLabel("🛒 Shopping Cart (Adjustable):")
        cart_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        layout.addWidget(cart_label)
        edit_toggle_layout = QHBoxLayout()
        self.edit_mode_checkbox = QCheckBox(
            "Enable quantity/price edits (dispatcher only)"
        )
        self.edit_mode_checkbox.stateChanged.connect(self.update_cart_display)
        edit_toggle_layout.addWidget(self.edit_mode_checkbox)
        edit_toggle_layout.addStretch()
        layout.addLayout(edit_toggle_layout)

        self.cart_table = QTableWidget()
        self.cart_table.setColumnCount(8)
        self.cart_table.setHorizontalHeaderLabels(
            [
                "Beverage",
                "Qty",
                "Our Cost",
                "Charged Price",
                "Item Cost",
                "Item Charged",
                "GST",
                "Remove",
            ]
        )
        self.cart_table.setMaximumHeight(200)
        self.cart_table.cellChanged.connect(self.handle_cart_cell_changed)
        layout.addWidget(self.cart_table)

        # Cost vs. Charged summary
        summary_group = QGroupBox("Order Summary (Cost vs. Charged)")
        summary_form = QFormLayout()

        self.our_cost_label = QLabel("$0.00")
        self.our_cost_label.setStyleSheet("font-weight: bold;")
        summary_form.addRow("Our Total Cost:", self.our_cost_label)

        self.charged_total_label = QLabel("$0.00")
        self.charged_total_label.setStyleSheet(
            "font-weight: bold; color: blue;"
        )
        summary_form.addRow(
            "Charged Total (to Guest):", self.charged_total_label
        )

        self.gst_total_label = QLabel("$0.00")
        summary_form.addRow("GST (in charged price):", self.gst_total_label)

        self.guest_total_label = QLabel("$0.00")
        summary_form.addRow("Guest Collect Total:", self.guest_total_label)

        self.profit_label = QLabel("$0.00")
        self.profit_label.setStyleSheet("font-weight: bold; color: green;")
        summary_form.addRow(
            "Markup/Profit (dispatcher view only):", self.profit_label
        )

        # Guest collection note
        self.guest_collection_note = QLabel()
        self.guest_collection_note.setWordWrap(True)
        self.guest_collection_note.setStyleSheet(
            "color: orange; font-style: italic;"
        )
        summary_form.addRow("Note for Guest:", self.guest_collection_note)

        summary_group.setLayout(summary_form)
        layout.addWidget(summary_group)

        # Discount/Adjustment section
        adjustment_group = QGroupBox(
            "Adjustments (e.g., free champagne for late arrival)"
        )
        adjustment_layout = QFormLayout()

        self.adjustment_desc = QLineEdit()
        self.adjustment_desc.setPlaceholderText(
            "e.g., Free champagne for late arrival"
        )
        adjustment_layout.addRow("Description:", self.adjustment_desc)

        self.adjustment_amount = QDoubleSpinBox()
        self.adjustment_amount.setMinimum(-1000)
        self.adjustment_amount.setMaximum(1000)
        self.adjustment_amount.setPrefix("$")
        adjustment_layout.addRow(
            "Amount (negative = discount):", self.adjustment_amount
        )

        self.charge_cost_only = QCheckBox("Charge Cost Only (No Markup)")
        adjustment_layout.addRow("", self.charge_cost_only)

        apply_adjust_btn = QPushButton("Apply Adjustment")
        apply_adjust_btn.clicked.connect(self.apply_adjustment)
        adjustment_layout.addWidget(apply_adjust_btn)

        adjustment_group.setLayout(adjustment_layout)
        layout.addWidget(adjustment_group)

        # Action buttons
        button_layout = QHBoxLayout()

        button_layout.addStretch()

        self.print_btn = QPushButton("🖨️ Print Order")
        self.print_btn.clicked.connect(self.print_order)
        button_layout.addWidget(self.print_btn)

        self.add_to_charter_btn = QPushButton("➕ Add to Charter")
        self.add_to_charter_btn.clicked.connect(self.add_to_charter)
        button_layout.addWidget(self.add_to_charter_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def update_beverage_list(self) -> None:
        """Update beverage list based on filters"""
        self.beverage_list.setRowCount(0)

        for bev in self.system.beverages:
            # Apply filters
            if self.category_filter.currentText() != "All":
                if bev["category"] != self.category_filter.currentText():
                    continue

            search_text = self.search_input.text().lower()
            if search_text and search_text not in bev["name"].lower():
                continue

            row = self.beverage_list.rowCount()
            self.beverage_list.insertRow(row)

            # Name
            self.beverage_list.setItem(row, 0, QTableWidgetItem(bev["name"]))
            # Category
            self.beverage_list.setItem(
                row, 1, QTableWidgetItem(bev["category"])
            )
            # Our Cost
            self.beverage_list.setItem(
                row, 2, QTableWidgetItem(f"${bev['our_cost']:.2f}")
            )
            # Charged Price (guest price)
            self.beverage_list.setItem(
                row, 3, QTableWidgetItem(f"${bev['charged_price']:.2f}")
            )

            # Quantity
            qty_spin = QSpinBox()
            qty_spin.setMinimum(0)
            qty_spin.setMaximum(100)
            self.beverage_list.setCellWidget(row, 4, qty_spin)

            # Add to Cart
            add_btn = QPushButton("Add")
            add_btn.clicked.connect(
                lambda checked, r=row: self.add_from_row(r)
            )
            self.beverage_list.setCellWidget(row, 5, add_btn)

    # Images removed: no icon loading needed

    def add_selected_beverage(self) -> None:
        """Add beverage from double-click (uses selected row's quantity)"""
        row = self.beverage_list.currentRow()
        if row >= 0:
            self.add_from_row(row)

    def add_from_row(self, row) -> None:
        """Add beverage from selected row"""
        qty_widget = self.beverage_list.cellWidget(
            row, 4
        )  # Column 4 is the Qty spinbox
        qty = qty_widget.value()

        if qty <= 0:
            QMessageBox.warning(self, "Warning", "Please enter quantity > 0")
            return

        bev_name = self.beverage_list.item(
            row, 0
        ).text()  # Column 0 is the Name
        bev = next(
            (b for b in self.system.beverages if b["name"] == bev_name), None
        )

        if bev:
            self.system.add_to_cart(bev["id"], qty)
            self.update_cart_display()
            qty_widget.setValue(0)  # Reset

    def update_cart_display(self) -> None:
        """Update cart table and summary"""
        if self._suppress_cart_refresh:
            return
        totals = self.system.get_cart_totals()

        self._suppress_cart_refresh = True
        try:
            self.cart_table.setRowCount(0)
            for i, item in enumerate(totals["items"]):
                self.cart_table.insertRow(i)

                qty_item = QTableWidgetItem(str(item["quantity"]))
                self.cart_table.setItem(i, 0, QTableWidgetItem(item["name"]))
                self.cart_table.setItem(i, 1, qty_item)
                self.cart_table.setItem(
                    i, 2, QTableWidgetItem(f"${item['our_cost']:.2f}")
                )
                charge_item = QTableWidgetItem(f"${item['charged_price']:.2f}")
                self.cart_table.setItem(i, 3, charge_item)
                self.cart_table.setItem(
                    i, 4, QTableWidgetItem(f"${item['item_cost']:.2f}")
                )
                self.cart_table.setItem(
                    i, 5, QTableWidgetItem(f"${item['item_charged']:.2f}")
                )
                self.cart_table.setItem(
                    i, 6, QTableWidgetItem(f"${item['item_gst']:.2f}")
                )

                remove_btn = QPushButton("❌")
                remove_btn.clicked.connect(
                    lambda checked, idx=i: self.remove_item(idx)
                )
                self.cart_table.setCellWidget(i, 7, remove_btn)

                editable_flags = (
                    Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
                )
                if self.edit_mode_checkbox.isChecked():
                    qty_item.setFlags(
                        editable_flags | Qt.ItemFlag.ItemIsEditable
                    )
                    charge_item.setFlags(
                        editable_flags | Qt.ItemFlag.ItemIsEditable
                    )
                else:
                    qty_item.setFlags(editable_flags)
                    charge_item.setFlags(editable_flags)
        finally:
            self._suppress_cart_refresh = False

        # Update summary
        self.our_cost_label.setText(f"${totals['our_total_cost']:.2f}")
        self.charged_total_label.setText(f"${totals['charged_total']:.2f}")
        self.gst_total_label.setText(f"${totals['gst_total']:.2f}")
        self.guest_total_label.setText(f"${totals['guest_total']:.2f}")
        self.profit_label.setText(f"${totals['profit']:.2f}")

        # Guest collection note
        if totals["guest_total"] > 0:
            self.guest_collection_note.setText(
                f"Collect ${totals['guest_total']:.2f} from guests for"
                f"beverages "
                f"(includes ${totals['gst_total']:.2f} GST)"
            )
        else:
            self.guest_collection_note.setText("")

        self.cart_updated.emit(totals)

    def _parse_currency_value(self, value_text) -> object:
        """Convert currency-like cell text to float."""
        try:
            cleaned = str(value_text).replace("$", "").strip()
            return float(cleaned)
        except Exception:
            return None

    def handle_cart_cell_changed(self, row, column) -> None:
        """Update cart model when dispatcher edits qty or price."""
        if self._suppress_cart_refresh:
            return
        if not self.edit_mode_checkbox.isChecked():
            return
        if row >= len(self.system.shopping_cart):
            return
        if column not in (1, 3):
            return

        item = self.system.shopping_cart[row]
        new_value_text = (
            self.cart_table.item(row, column).text()
            if self.cart_table.item(row, column)
            else ""
        )
        parsed_value = self._parse_currency_value(new_value_text)
        if parsed_value is None or parsed_value < 0:
            return

        self._suppress_cart_refresh = True
        try:
            if column == 1:
                item["quantity"] = int(parsed_value)
            elif column == 3:
                item["charged_price"] = parsed_value

            # Recompute derived amounts
            item["item_cost"] = item["our_cost"] * item["quantity"]
            item["item_charged"] = item["charged_price"] * item["quantity"]
            if item.get("gst_included"):
                item["item_gst"] = (
                    item["charged_price"]
                    * self.system.gst_rate
                    / (1 + self.system.gst_rate)
                    * item["quantity"]
                )
            else:
                item["item_gst"] = 0
        finally:
            self._suppress_cart_refresh = False

        self.update_cart_display()

    def remove_item(self, index) -> None:
        """Remove item from cart"""
        self.system.remove_from_cart(index)
        self.update_cart_display()

    @pyqtSlot()
    def parse_email_list(self) -> None:
        """Parse email list and auto-add beverages"""
        QMessageBox.information(
            self,
            "Info",
            "Email parsing and auto-add feature\n"
            "(Database integration pending)",
        )

    @pyqtSlot()
    def apply_adjustment(self) -> None:
        """Apply discount or adjustment"""
        desc = self.adjustment_desc.text()
        amount = self.adjustment_amount.value()

        if not desc:
            QMessageBox.warning(
                self, "Warning", "Enter adjustment description"
            )
            return

        QMessageBox.information(
            self,
            "Info",
            f"Adjustment applied:\n{desc}: ${amount:.2f}\n"
            "(Implemented in Phase 2)",
        )

    @pyqtSlot()
    def print_order(self) -> None:
        """Print beverage order"""
        totals = self.system.get_cart_totals()

        text = "BEVERAGE ORDER\n"
        text += f"{'=' * 60}\n"
        text += f"Date: {datetime.now().strftime('%m/%d/%Y %H:%M')}\n\n"

        # Invoice view: totals only (guest-facing)
        text += "INVOICE SECTION (Totals Only)\n"
        text += f"{'-' * 60}\n"
        text += (
            "  Charged Total: "
            f"${totals['charged_total']:.2f}\n"
        )
        text += f"  Guest Collect Total: ${totals['guest_total']:.2f}\n"
        text += f"  GST Included: ${totals['gst_total']:.2f}\n"
        text += "  (No line items on invoice)\n"

        # Driver load sheet: itemized with GST per line
        text += "\nDRIVER LOAD SHEET (Itemized, GST included per line)\n"
        text += f"{'-' * 60}\n"
        for item in totals["items"]:
            line_total = item["item_charged"]
            text += (
                f"[] {item['name']} x {item['quantity']}  "
                f"Line Total: ${line_total:.2f}"
            )
            text += f" (GST: ${item['item_gst']:.2f})\n"

        # Internal cost summary (dispatcher/accounting only)
        text += f"\n{'=' * 60}\n"
        text += "INTERNAL SUMMARY (Dispatcher/Accounting)\n"
        text += f"  Our Total Cost: ${totals['our_total_cost']:.2f}\n"
        text += f"  Profit/Markup: ${totals['profit']:.2f}\n"

        QMessageBox.information(self, "Order", text)

    @pyqtSlot()
    def add_to_charter(self) -> None:
        """Add beverages to selected charter"""
        totals = self.system.get_cart_totals()

        if not totals["items"]:
            QMessageBox.warning(self, "Warning", "Cart is empty")
            return

        self.cart_updated.emit(totals)
        QMessageBox.information(
            self,
            "Success",
            "Beverages added to charter:\n"
            f"Items: {len(totals['items'])}\n"
            f"Charged Total: ${totals['charged_total']:.2f}",
        )


# ============================================================================
# BEVERAGE SELECTION DIALOG - For Charter Integration
# ============================================================================


class BeverageSelectionDialog(QDialog):
    """
    Dialog for selecting beverages when adding to a charter.
    Returns cart totals for saving to database.
    Keeps internal costs hidden from guest-facing sections.
    """

    def __init__(self, db, parent=None, existing_beverages=None) -> None:
        super().__init__(parent)
        self.db = db
        self.system = BeverageOrderingSystem(db)
        self._suppress_cart_refresh = False
        self.setWindowTitle("🍷 Add Beverages to Charter")
        self.setGeometry(100, 100, 1200, 700)
        self.init_ui()

        # If editing existing order, pre-load beverages into system
        if existing_beverages:
            self.load_existing_beverages(existing_beverages)

    def load_existing_beverages(self, existing_beverages) -> None:
        """Pre-populate cart with saved snapshot prices (not catalog prices)."""
        try:
            self.system.shopping_cart.clear()
            for bev in existing_beverages:
                qty = int(bev.get("quantity") or 1)
                unit_charged = float(bev.get("unit_price_charged") or 0)
                unit_cost = float(bev.get("unit_our_cost") or 0)
                item_gst = unit_charged * 0.05 / 1.05 * qty
                cart_item = {
                    "beverage_id": bev.get("beverage_item_id"),
                    "name": str(bev.get("item_name") or "Unknown"),
                    "quantity": qty,
                    "our_cost": unit_cost,
                    "charged_price": unit_charged,
                    "gst_included": True,
                    "notes": str(bev.get("notes") or ""),
                    "item_cost": unit_cost * qty,
                    "item_charged": unit_charged * qty,
                    "item_gst": item_gst,
                }
                self.system.shopping_cart.append(cart_item)
            self.update_cart_display()
        except Exception as e:
            logger.error("Error loading existing beverages: %s", e)

    def init_ui(self) -> None:
        """Initialize UI for beverage selection"""
        layout = QVBoxLayout()

        # Title
        title = QLabel("Select Beverages for This Charter")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)

        # Search and filter
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by name...")
        self.search_input.textChanged.connect(self.update_beverage_list)
        filter_layout.addWidget(self.search_input)

        filter_layout.addWidget(QLabel("Category:"))
        self.category_filter = QComboBox()
        self.category_filter.addItem("All")
        categories = sorted(
            {
                (bev.get("category") or "Other")
                for bev in self.system.beverages
            }
        )
        self.category_filter.addItems(categories)
        self.category_filter.currentTextChanged.connect(
            self.update_beverage_list
        )
        filter_layout.addWidget(self.category_filter)

        self.add_new_beverage_btn = QPushButton("➕ Add New Beverage")
        self.add_new_beverage_btn.clicked.connect(
            self.open_add_new_beverage_dialog
        )
        filter_layout.addWidget(self.add_new_beverage_btn)

        layout.addLayout(filter_layout)

        # Beverages table
        self.beverage_list = QTableWidget()
        self.beverage_list.setColumnCount(7)
        self.beverage_list.setHorizontalHeaderLabels(
            ["Name", "Category", "Guest Price", "Qty", "Line Total", "Add", ""]
        )
        self.beverage_list.setColumnWidth(0, 200)
        self.beverage_list.setColumnWidth(1, 100)
        self.update_beverage_list()
        layout.addWidget(self.beverage_list)

        # Cart section
        cart_label = QLabel("Cart (Guest Prices Only)")
        cart_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        layout.addWidget(cart_label)

        self.cart_table = QTableWidget()
        self.cart_table.setColumnCount(5)
        self.cart_table.setHorizontalHeaderLabels(
            ["Product", "Qty", "Guest Price", "Line Total", "Remove"]
        )
        self.cart_table.setMaximumHeight(200)
        self.cart_table.cellChanged.connect(self.handle_cart_cell_changed)
        layout.addWidget(self.cart_table)

        # Per-event pricing tools for one-off comps/discounts
        pricing_tools_layout = QHBoxLayout()
        pricing_tools_layout.addWidget(QLabel("Price Tools:"))

        self.discount_pct_input = QDoubleSpinBox()
        self.discount_pct_input.setRange(0.0, 100.0)
        self.discount_pct_input.setDecimals(1)
        self.discount_pct_input.setSingleStep(1.0)
        self.discount_pct_input.setValue(10.0)
        self.discount_pct_input.setSuffix("%")
        pricing_tools_layout.addWidget(self.discount_pct_input)

        self.apply_discount_btn = QPushButton("Apply % to Selected")
        self.apply_discount_btn.clicked.connect(
            self.apply_discount_to_selected
        )
        pricing_tools_layout.addWidget(self.apply_discount_btn)

        self.apply_markup_btn = QPushButton("Apply % Markup")
        self.apply_markup_btn.clicked.connect(self.apply_markup_to_selected)
        pricing_tools_layout.addWidget(self.apply_markup_btn)

        self.fixed_amount_input = QDoubleSpinBox()
        self.fixed_amount_input.setRange(0.0, 9999.0)
        self.fixed_amount_input.setDecimals(2)
        self.fixed_amount_input.setSingleStep(0.50)
        self.fixed_amount_input.setValue(5.00)
        self.fixed_amount_input.setPrefix("$+")
        pricing_tools_layout.addWidget(self.fixed_amount_input)

        self.add_fixed_btn = QPushButton("Add $ to Selected")
        self.add_fixed_btn.clicked.connect(self.add_fixed_to_selected)
        pricing_tools_layout.addWidget(self.add_fixed_btn)

        self.set_free_btn = QPushButton("Set Selected Free")
        self.set_free_btn.clicked.connect(self.set_selected_item_free)
        pricing_tools_layout.addWidget(self.set_free_btn)

        pricing_tools_layout.addStretch()
        layout.addLayout(pricing_tools_layout)

        # Totals (guest-facing only)
        totals_layout = QHBoxLayout()
        totals_layout.addWidget(QLabel("Total for Guest:"))
        self.guest_total_label = QLabel("$0.00")
        self.guest_total_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.guest_total_label.setStyleSheet("color: green;")
        totals_layout.addWidget(self.guest_total_label)

        totals_layout.addWidget(QLabel("(GST Included)"))
        self.gst_label = QLabel("$0.00")
        self.gst_label.setStyleSheet("color: blue;")
        totals_layout.addWidget(self.gst_label)

        totals_layout.addStretch()
        layout.addLayout(totals_layout)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.clear_btn = QPushButton("Clear Cart")
        self.clear_btn.clicked.connect(self.clear_cart)
        button_layout.addWidget(self.clear_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        self.add_btn = QPushButton("✅ Add to Charter")
        self.add_btn.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold;"
        )
        self.add_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.add_btn)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def update_beverage_list(self) -> None:
        """Update beverage list based on filters"""
        self.beverage_list.setRowCount(0)
        search_text = self.search_input.text().lower()
        category_filter = self.category_filter.currentText()

        for bev in self.system.beverages:
            # Apply filters
            if category_filter != "All" and bev["category"] != category_filter:
                continue
            if search_text and search_text not in bev["name"].lower():
                continue

            row = self.beverage_list.rowCount()
            self.beverage_list.insertRow(row)

            # Name
            self.beverage_list.setItem(row, 0, QTableWidgetItem(bev["name"]))

            # Category
            self.beverage_list.setItem(
                row, 1, QTableWidgetItem(bev["category"])
            )

            # Guest Price (charged_price, NOT our_cost)
            guest_price_item = QTableWidgetItem(f"${bev['charged_price']:.2f}")
            guest_price_item.setFlags(
                guest_price_item.flags() & ~Qt.ItemFlag.ItemIsEditable
            )
            self.beverage_list.setItem(row, 2, guest_price_item)

            # Quantity spinner
            qty_spin = QSpinBox()
            qty_spin.setMinimum(0)
            qty_spin.setMaximum(100)
            self.beverage_list.setCellWidget(row, 3, qty_spin)

            # Line total (calculated)
            line_total_item = QTableWidgetItem("$0.00")
            line_total_item.setFlags(
                line_total_item.flags() & ~Qt.ItemFlag.ItemIsEditable
            )
            self.beverage_list.setItem(row, 4, line_total_item)

            # Add button
            add_btn = QPushButton("Add")
            add_btn.clicked.connect(
                lambda checked, r=row, bid=bev["id"]: self.add_from_row(r, bid)
            )
            self.beverage_list.setCellWidget(row, 5, add_btn)

    def _reload_beverage_catalog(self) -> None:
        """Reload beverages and refresh filters/list after catalog changes."""
        self.system.beverages = self.system._load_beverages_from_db()

        current_category = self.category_filter.currentText()
        self.category_filter.blockSignals(True)
        self.category_filter.clear()
        self.category_filter.addItem("All")
        categories = sorted(
            {
                (bev.get("category") or "Other")
                for bev in self.system.beverages
            }
        )
        self.category_filter.addItems(categories)
        if current_category in ["All", *categories]:
            self.category_filter.setCurrentText(current_category)
        self.category_filter.blockSignals(False)

        self.update_beverage_list()

    def open_add_new_beverage_dialog(self) -> None:
        """Add a new catalog beverage directly from the charter picker."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Add New Beverage")
        form = QFormLayout(dialog)

        name_input = QLineEdit()
        name_input.setPlaceholderText("e.g., Corona Extra 355ml")
        form.addRow("Name:", name_input)

        category_input = QComboBox()
        category_input.setEditable(True)
        existing_categories = sorted(
            {
                (bev.get("category") or "Other")
                for bev in self.system.beverages
            }
        )
        category_input.addItems(existing_categories)
        form.addRow("Category:", category_input)

        price_input = QDoubleSpinBox()
        price_input.setRange(0.0, 9999.0)
        price_input.setDecimals(2)
        price_input.setValue(5.00)
        form.addRow("Guest Price:", price_input)

        cost_input = QDoubleSpinBox()
        cost_input.setRange(0.0, 9999.0)
        cost_input.setDecimals(2)
        cost_input.setValue(3.50)
        form.addRow("Our Cost:", cost_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        name = name_input.text().strip()
        category = category_input.currentText().strip() or "Other"
        if not name:
            QMessageBox.warning(self, "Validation", "Beverage name is required.")
            return

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO beverage_products (
                        item_name,
                        category,
                        unit_price,
                        our_cost,
                        deposit_amount,
                        gst_included,
                        stock_quantity
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        name,
                        category,
                        float(price_input.value()),
                        float(cost_input.value()),
                        0.0,
                        True,
                        0,
                    ),
                )

            self._reload_beverage_catalog()
            QMessageBox.information(
                self,
                "Added",
                f"Added '{name}' to beverage catalog.",
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to add beverage: {e}",
            )

    def add_from_row(self, row, beverage_id) -> None:
        """Add beverage to cart"""
        qty_widget = self.beverage_list.cellWidget(row, 3)
        qty = qty_widget.value()

        if qty <= 0:
            QMessageBox.warning(self, "Warning", "Please enter quantity > 0")
            return

        try:
            self.system.add_to_cart(beverage_id, qty)
            self.update_cart_display()
            qty_widget.setValue(0)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to add: {e}")

    def update_cart_display(self) -> None:
        """Update cart table with guest prices only"""
        totals = self.system.get_cart_totals()

        self._suppress_cart_refresh = True
        self.cart_table.setRowCount(0)

        try:
            for i, item in enumerate(totals["items"]):
                self.cart_table.insertRow(i)

                # Product
                self.cart_table.setItem(i, 0, QTableWidgetItem(item["name"]))

                # Qty
                qty_item = QTableWidgetItem(str(item["quantity"]))
                qty_item.setFlags(
                    Qt.ItemFlag.ItemIsSelectable
                    | Qt.ItemFlag.ItemIsEnabled
                    | Qt.ItemFlag.ItemIsEditable
                )
                self.cart_table.setItem(i, 1, qty_item)

                # Guest Price (charged_price, NOT our_cost)
                price_item = QTableWidgetItem(f"${item['charged_price']:.2f}")
                price_item.setFlags(
                    Qt.ItemFlag.ItemIsSelectable
                    | Qt.ItemFlag.ItemIsEnabled
                    | Qt.ItemFlag.ItemIsEditable
                )
                self.cart_table.setItem(i, 2, price_item)

                # Line Total
                line_item = QTableWidgetItem(f"${item['item_charged']:.2f}")
                line_item.setFlags(
                    line_item.flags() & ~Qt.ItemFlag.ItemIsEditable
                )
                self.cart_table.setItem(i, 3, line_item)

                # Remove button
                remove_btn = QPushButton("❌")
                remove_btn.clicked.connect(
                    lambda checked, idx=i: self.remove_item(idx)
                )
                self.cart_table.setCellWidget(i, 4, remove_btn)
        finally:
            self._suppress_cart_refresh = False

        # Update totals (guest-facing only)
        self.guest_total_label.setText(f"${totals['guest_total']:.2f}")
        self.gst_label.setText(f"${totals['gst_total']:.2f}")

    def remove_item(self, index) -> None:
        """Remove item from cart"""
        self.system.remove_from_cart(index)
        self.update_cart_display()

    def _parse_currency_value(self, value_text) -> object:
        """Convert currency-like text to float."""
        try:
            cleaned = str(value_text).replace("$", "").strip()
            return float(cleaned)
        except Exception:
            return None

    def _recalculate_cart_item(self, item) -> None:
        """Recalculate line-level totals after qty/price changes."""
        qty = max(0, int(item.get("quantity", 0)))
        unit_price = max(0.0, float(item.get("charged_price", 0) or 0))

        item["quantity"] = qty
        item["charged_price"] = unit_price
        item["item_cost"] = item["our_cost"] * qty
        item["item_charged"] = unit_price * qty

        if item.get("gst_included") and unit_price > 0:
            item["item_gst"] = (
                unit_price
                * self.system.gst_rate
                / (1 + self.system.gst_rate)
                * qty
            )
        else:
            item["item_gst"] = 0

    def _get_selected_cart_row(self) -> object:
        """Return selected row index, or None if nothing valid selected."""
        row = self.cart_table.currentRow()
        if row < 0 or row >= len(self.system.shopping_cart):
            QMessageBox.warning(
                self,
                "Select Item",
                "Select a cart row first.",
            )
            return None
        return row

    @pyqtSlot()
    def set_selected_item_free(self) -> None:
        """Set selected cart line guest price to $0.00 for this event only."""
        row = self._get_selected_cart_row()
        if row is None:
            return

        item = self.system.shopping_cart[row]
        item["charged_price"] = 0.0
        self._recalculate_cart_item(item)
        self.update_cart_display()

    def apply_discount_to_selected(self) -> None:
        """Apply percentage discount to selected cart line for this event only."""
        row = self._get_selected_cart_row()
        if row is None:
            return

        discount_pct = max(0.0, min(100.0, self.discount_pct_input.value()))
        item = self.system.shopping_cart[row]
        current_price = float(item.get("charged_price", 0) or 0)
        discounted = round(current_price * (1 - discount_pct / 100.0), 2)
        item["charged_price"] = max(0.0, discounted)
        self._recalculate_cart_item(item)
        self.update_cart_display()

    @pyqtSlot()
    def apply_markup_to_selected(self) -> None:
        """Apply percentage markup to selected cart line for this event only."""
        row = self._get_selected_cart_row()
        if row is None:
            return

        markup_pct = max(0.0, self.discount_pct_input.value())
        item = self.system.shopping_cart[row]
        current_price = float(item.get("charged_price", 0) or 0)
        marked_up = round(current_price * (1 + markup_pct / 100.0), 2)
        item["charged_price"] = max(0.0, marked_up)
        self._recalculate_cart_item(item)
        self.update_cart_display()

    @pyqtSlot()
    def add_fixed_to_selected(self) -> None:
        """Add a fixed dollar amount to selected cart line for this event only."""
        row = self._get_selected_cart_row()
        if row is None:
            return

        amount = max(0.0, self.fixed_amount_input.value())
        item = self.system.shopping_cart[row]
        current_price = float(item.get("charged_price", 0) or 0)
        item["charged_price"] = round(current_price + amount, 2)
        self._recalculate_cart_item(item)
        self.update_cart_display()

    def handle_cart_cell_changed(self, row, column) -> None:
        """Allow per-sale qty/guest price overrides for this charter only."""
        if self._suppress_cart_refresh:
            return
        if row >= len(self.system.shopping_cart):
            return
        if column not in (1, 2):
            return

        item = self.system.shopping_cart[row]
        cell = self.cart_table.item(row, column)
        parsed = self._parse_currency_value(cell.text() if cell else "")
        if parsed is None or parsed < 0:
            return

        if column == 1:
            item["quantity"] = int(parsed)
        else:
            item["charged_price"] = parsed

        self._recalculate_cart_item(item)

        self.update_cart_display()

    @pyqtSlot()
    def clear_cart(self) -> None:
        """Clear all items from cart"""
        self.system.shopping_cart = []
        self.update_cart_display()

    def get_cart_totals(self) -> object:
        """Return cart totals for saving to database"""
        return self.system.get_cart_totals()
