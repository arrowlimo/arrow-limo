"""
Beverage Management Widget
Dispatcher/Admin tool for:
- Add new beverage products to catalog
- Manage pricing (unit price, cost, deposit)
- Bulk price adjustments with percentage/fixed amount
- Cost tracking per charter, per month, per year
- Margin analysis and profitability
"""

import csv
import logging
import os

from db_error_handling import DatabaseContext
from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QBrush, QColor, QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


def _beverage_write_enabled() -> bool:
    raw_value = os.environ.get(
        "BEVERAGE_WIDGET_WRITE_ENABLED",
        os.environ.get("RECEIPT_WIDGET_WRITE_ENABLED", "true"),
    )
    return str(raw_value).lower() in ("1", "true", "yes")


class BeverageManagementWidget(QWidget):
    """Manage beverage products, pricing, and cost tracking"""

    TARGET_MARKUP_MULTIPLIER = 1.25

    def __init__(self, db_conn, parent=None) -> None:
        super().__init__(parent)
        self.db_conn = db_conn
        self.write_enabled = _beverage_write_enabled()
        self._table_name = "beverage_products"
        self._id_col = "item_id"
        self._beverage_columns = set()
        self._col_name = "item_name"
        self._col_price = "unit_price"
        self._col_cost = "our_cost"
        self._col_deposit = "deposit_amount"
        self._col_active = None
        self.init_ui()
        self.load_data()

    def init_ui(self) -> None:
        """Initialize UI with tabs for different functions"""
        layout = QVBoxLayout()

        # Title
        title = QLabel("🍷 Beverage Management")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        mode_text = (
            "🔓 Write Mode: ENABLED"
            if self.write_enabled
            else "🔒 Write Mode: DISABLED (read-only)"
        )
        mode_color = "#00aa00" if self.write_enabled else "#cc0000"
        self.write_mode_label = QLabel(mode_text)
        self.write_mode_label.setStyleSheet(
            f"color: {mode_color}; font-size: 8pt; font-weight: bold; "
            f"padding: 3px; border: 1px solid {mode_color}; "
            "border-radius: 3px; background-color: "
            f"{'#eaffea' if self.write_enabled else '#ffecec'};"
        )
        layout.addWidget(self.write_mode_label)

        # Tab widget for different functions
        self.tabs = QTabWidget()

        # Tab 1: Catalog Management
        self.tabs.addTab(self.create_catalog_tab(), "📦 Catalog & Pricing")

        # Tab 2: Bulk Price Adjustments
        self.tabs.addTab(self.create_bulk_adjust_tab(), "📊 Bulk Adjustments")

        # Tab 3: Cost Tracking & Margins
        self.tabs.addTab(self.create_cost_tracking_tab(), "💰 Cost & Margins")

        # Tab 4: Inventory by Charter
        self.tabs.addTab(self.create_charter_costs_tab(), "📅 Charter Costs")

        layout.addWidget(self.tabs)
        self.setLayout(layout)

    def create_catalog_tab(self) -> object:
        """Tab 1: Add/edit beverage products"""
        widget = QWidget()
        layout = QVBoxLayout()

        self.catalog_tabs = QTabWidget()

        catalog_list_tab = QWidget()
        catalog_list_layout = QVBoxLayout()

        # Header with search
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by name, category...")
        self.search_input.textChanged.connect(self.filter_products)
        header_layout.addWidget(self.search_input)

        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.load_data)
        header_layout.addWidget(refresh_btn)

        self.save_btn = QPushButton("💾 Save Catalog Changes")
        self.save_btn.clicked.connect(self.save_catalog_changes)
        header_layout.addWidget(self.save_btn)

        self.delete_btn = QPushButton("🗑️ Delete Selected")
        self.delete_btn.setStyleSheet(
            "background-color: #c0392b; color: white; font-weight: bold;"
        )
        self.delete_btn.clicked.connect(self.delete_selected_product)
        header_layout.addWidget(self.delete_btn)

        catalog_list_layout.addLayout(header_layout)

        # Products table
        self.products_table = QTableWidget()
        self.products_table.setColumnCount(7)
        self.products_table.setHorizontalHeaderLabels(
            [
                "Beverage ID",
                "Name",
                "Category",
                "Customer Price",
                "Our Cost",
                "Margin %",
                "Active",
            ]
        )
        self.products_table.setColumnWidth(1, 200)
        self.products_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        catalog_list_layout.addWidget(self.products_table)

        catalog_list_tab.setLayout(catalog_list_layout)
        self.catalog_tabs.addTab(catalog_list_tab, "📋 Beverage List")

        add_product_tab = QWidget()
        add_product_layout = QVBoxLayout()

        # Add new product section
        add_group = QGroupBox("➕ Add New Beverage Product")
        add_layout = QFormLayout()

        self.new_name = QLineEdit()
        self.new_name.setPlaceholderText("e.g., Corona Extra 355ml")
        add_layout.addRow("Product Name:", self.new_name)

        self.new_category = QComboBox()
        self.new_category.addItems(
            [
                "Beer",
                "Spirits",
                "Wine",
                "Ready-To-Drink",
                "Hard Seltzers",
                "Champagne",
                "Water",
                "Iced Tea",
                "Mixers",
                "Non-Alcoholic",
                "Energy Drink",
            ]
        )
        add_layout.addRow("Category:", self.new_category)

        self.new_unit_price = QDoubleSpinBox()
        self.new_unit_price.setRange(0.99, 99.99)
        self.new_unit_price.setValue(5.49)
        self.new_unit_price.setSingleStep(0.01)
        add_layout.addRow("Unit Price (sell):", self.new_unit_price)

        self.new_cost = QDoubleSpinBox()
        self.new_cost.setRange(0.0, 99.99)
        self.new_cost.setValue(3.84)  # 70% default
        self.new_cost.setSingleStep(0.01)
        add_layout.addRow("Our Cost (wholesale):", self.new_cost)

        self.new_markup_percent = QDoubleSpinBox()
        self.new_markup_percent.setRange(0.0, 200.0)
        self.new_markup_percent.setValue(25.0)
        self.new_markup_percent.setSingleStep(0.5)
        self.new_markup_percent.setSuffix(" %")
        add_layout.addRow("Auto Markup %:", self.new_markup_percent)

        # Auto-calculate cost from sell price using target 25% markup.
        auto_calc_btn = QPushButton("Apply Markup To Sell Price")
        auto_calc_btn.clicked.connect(self.auto_calc_cost)
        add_layout.addRow("", auto_calc_btn)

        self.add_btn = QPushButton("✅ Add Product")
        self.add_btn.clicked.connect(self.add_new_product)
        add_layout.addRow("", self.add_btn)

        add_group.setLayout(add_layout)
        add_product_layout.addWidget(add_group)
        add_product_layout.addStretch()
        add_product_tab.setLayout(add_product_layout)
        self.catalog_tabs.addTab(add_product_tab, "➕ Add Beverage")

        layout.addWidget(self.catalog_tabs)

        self._apply_write_mode_to_catalog_controls()
        widget.setLayout(layout)
        return widget

    def create_bulk_adjust_tab(self) -> object:
        """Tab 2: Bulk price adjustments"""
        widget = QWidget()
        layout = QVBoxLayout()

        # Category filter
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter by Category:"))
        self.adjust_category = QComboBox()
        self.adjust_category.addItem("All Categories", None)
        self.adjust_category.addItems(
            [
                "Beer",
                "Spirits",
                "Wine",
                "Ready-To-Drink",
                "Hard Seltzers",
                "Champagne",
                "Water",
                "Iced Tea",
                "Mixers",
                "Non-Alcoholic",
                "Energy Drink",
            ]
        )
        filter_layout.addWidget(self.adjust_category)
        layout.addLayout(filter_layout)

        # Adjustment options
        adjust_group = QGroupBox("🔧 Price Adjustment Options")
        adjust_layout = QFormLayout()

        self.adjust_type = QComboBox()
        self.adjust_type.addItems(
            [
                "Percentage Increase",
                "Percentage Decrease",
                "Fixed Amount Add",
                "Fixed Amount Subtract",
            ]
        )
        adjust_layout.addRow("Adjustment Type:", self.adjust_type)

        self.adjust_amount = QDoubleSpinBox()
        self.adjust_amount.setRange(0.01, 99.99)
        self.adjust_amount.setValue(5.0)
        self.adjust_amount.setSingleStep(0.01)
        adjust_layout.addRow("Adjustment Value:", self.adjust_amount)

        self.adjust_cost_too = QCheckBox(
            "Also adjust our_cost proportionally?"
        )
        self.adjust_cost_too.setChecked(False)
        adjust_layout.addRow("", self.adjust_cost_too)

        preview_btn = QPushButton("👁️ Preview Changes")
        preview_btn.clicked.connect(self.preview_bulk_adjust)
        adjust_layout.addRow("", preview_btn)

        adjust_group.setLayout(adjust_layout)
        layout.addWidget(adjust_group)

        # Preview table
        self.adjust_preview_table = QTableWidget()
        self.adjust_preview_table.setColumnCount(6)
        self.adjust_preview_table.setHorizontalHeaderLabels(
            [
                "Product",
                "Current Price",
                "New Price",
                "Current Cost",
                "New Cost",
                "Impact",
            ]
        )
        layout.addWidget(self.adjust_preview_table)

        # Apply button
        self.apply_adjust_btn = QPushButton("✅ Apply All Changes")
        self.apply_adjust_btn.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold;"
        )
        self.apply_adjust_btn.clicked.connect(self.apply_bulk_adjust)
        layout.addWidget(self.apply_adjust_btn)

        # One-click normalization: enforce markup model and clear deposit.
        self.normalize_btn = QPushButton(
            "♻️ Normalize to 25% Markup"
        )
        self.normalize_btn.setStyleSheet(
            "background-color: #2e86c1; color: white; font-weight: bold;"
        )
        self.normalize_btn.clicked.connect(self.normalize_deposit_and_markup)
        layout.addWidget(self.normalize_btn)

        self._apply_write_mode_to_bulk_controls()
        widget.setLayout(layout)
        return widget

    def _apply_write_mode_to_catalog_controls(self) -> None:
        for button in (
            getattr(self, "save_btn", None),
            getattr(self, "delete_btn", None),
            getattr(self, "add_btn", None),
        ):
            if button is not None:
                button.setEnabled(self.write_enabled)
                if not self.write_enabled:
                    button.setToolTip("Write mode is disabled for beverage management.")

    def _apply_write_mode_to_bulk_controls(self) -> None:
        for button in (
            getattr(self, "apply_adjust_btn", None),
            getattr(self, "normalize_btn", None),
        ):
            if button is not None:
                button.setEnabled(self.write_enabled)
                if not self.write_enabled:
                    button.setToolTip(
                        "Write mode is disabled for beverage management."
                    )

    def _require_write_enabled(self) -> bool:
        if self.write_enabled:
            return True
        QMessageBox.warning(
            self,
            "Read-only Mode",
            "Beverage Management write mode is disabled.",
        )
        return False

    def create_cost_tracking_tab(self) -> object:
        """Tab 3: Cost analysis and margins"""
        widget = QWidget()
        layout = QVBoxLayout()

        # Summary stats
        stats_layout = QHBoxLayout()

        self.total_items_label = QLabel("Total Items: 0")
        self.total_items_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        stats_layout.addWidget(self.total_items_label)

        self.avg_margin_label = QLabel("Avg Margin: 0%")
        self.avg_margin_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        stats_layout.addWidget(self.avg_margin_label)

        self.low_margin_label = QLabel("⚠️ Low Margin Items: 0")
        self.low_margin_label.setStyleSheet("color: red;")
        stats_layout.addWidget(self.low_margin_label)

        layout.addLayout(stats_layout)

        # Margins table
        self.margins_table = QTableWidget()
        self.margins_table.setColumnCount(7)
        self.margins_table.setHorizontalHeaderLabels(
            [
                "Product",
                "Unit Price",
                "Our Cost",
                "Margin $",
                "Margin %",
                "Volume Sold",
                "Total Margin",
            ]
        )
        self.margins_table.setColumnWidth(0, 200)
        self.margins_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.margins_table)

        # Export button
        export_btn = QPushButton("💾 Export Margin Report")
        export_btn.clicked.connect(self.export_margins)
        layout.addWidget(export_btn)

        widget.setLayout(layout)
        return widget

    def create_charter_costs_tab(self) -> object:
        """Tab 4: Cost tracking by charter"""
        widget = QWidget()
        layout = QVBoxLayout()

        # Date range filter
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("From Date:"))
        self.from_date = QDateEdit()
        self.from_date.setDate(QDate.currentDate().addMonths(-1))
        filter_layout.addWidget(self.from_date)

        filter_layout.addWidget(QLabel("To Date:"))
        self.to_date = QDateEdit()
        self.to_date.setDate(QDate.currentDate())
        filter_layout.addWidget(self.to_date)

        search_btn = QPushButton("🔍 Search")
        search_btn.clicked.connect(self.search_charter_costs)
        filter_layout.addWidget(search_btn)

        layout.addLayout(filter_layout)

        # Grouping options
        group_layout = QHBoxLayout()
        group_layout.addWidget(QLabel("Group By:"))
        self.group_by = QComboBox()
        self.group_by.addItems(
            ["Charter", "Month", "Year", "Driver", "Category"]
        )
        group_layout.addWidget(self.group_by)
        layout.addLayout(group_layout)

        # Results table
        self.charter_costs_table = QTableWidget()
        self.charter_costs_table.setColumnCount(8)
        self.charter_costs_table.setHorizontalHeaderLabels(
            [
                "Charter/Period",
                "Items Count",
                "Our Cost Total",
                "Revenue Total",
                "Gross Margin",
                "Margin %",
                "Avg per Item",
                "Details",
            ]
        )
        layout.addWidget(self.charter_costs_table)

        # Export button
        export_costs_btn = QPushButton("💾 Export Charter Costs Report")
        export_costs_btn.clicked.connect(self.export_charter_costs)
        layout.addWidget(export_costs_btn)

        widget.setLayout(layout)
        return widget

    # ========================================================================
    # DATA LOADING AND FILTERING
    # ========================================================================

    def load_data(self) -> None:
        """Load all beverages from beverage_products table."""

        try:
            with DatabaseContext(self.db_conn, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'beverage_products'
                    """
                )
                self._beverage_columns = {row[0] for row in cur.fetchall()}

                if not self._beverage_columns:
                    raise RuntimeError("beverage_products table not found")

                self._col_name = (
                    "item_name"
                    if "item_name" in self._beverage_columns
                    else "name"
                )
                self._col_price = (
                    "unit_price"
                    if "unit_price" in self._beverage_columns
                    else "price"
                )
                self._col_active = (
                    "is_active"
                    if "is_active" in self._beverage_columns
                    else None
                )
                self._col_cost = (
                    "our_cost"
                    if "our_cost" in self._beverage_columns
                    else ("cost" if "cost" in self._beverage_columns else None)
                )
                self._col_deposit = (
                    "deposit_amount"
                    if "deposit_amount" in self._beverage_columns
                    else (
                        "gst_deposit_amount"
                        if "gst_deposit_amount" in self._beverage_columns
                        else None
                    )
                )

                deposit_expr = (
                    f"COALESCE({self._col_deposit}, 0)"
                    if self._col_deposit
                    else "0"
                )
                cost_expr = (
                    f"COALESCE({self._col_cost}, 0)"
                    if self._col_cost
                    else "0"
                )

                cur.execute(
                    f"""
                          SELECT {self._id_col} AS beverage_id,
                           {self._col_name} AS name,
                           COALESCE(category, 'Other') AS category,
                           COALESCE({self._col_price}, 0) AS unit_price,
                           {cost_expr} AS our_cost,
                           {deposit_expr} AS deposit,
                              COALESCE(
                               {self._col_active if self._col_active else 'true'},
                               true
                              ) AS is_active
                          FROM {self._table_name}
                    ORDER BY category, name
                    """
                )
                self.all_products = cur.fetchall()

            self.refresh_products_table()
            self.update_margin_stats()
        except Exception as e:
            logger.error(f"Failed to load beverage catalog: {e}")
            try:
                self.db_conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to load beverage catalog: {e}",
            )

    def refresh_products_table(self, filter_text="") -> None:
        """Refresh the products catalog table"""
        self.products_table.setRowCount(0)
        # Clear the search box so all rows are shown after a full refresh
        if hasattr(self, 'search_input'):
            self.search_input.blockSignals(True)
            self.search_input.clear()
            self.search_input.blockSignals(False)

        for product in self.all_products:
            (
                beverage_id,
                name,
                category,
                unit_price,
                our_cost,
                deposit,
                is_active,
            ) = product

            # Apply filter
            if (
                filter_text
                and filter_text.lower() not in name.lower()
                and filter_text.lower() not in category.lower()
            ):
                continue

            row = self.products_table.rowCount()
            self.products_table.insertRow(row)

            # Beverage ID
            id_item = QTableWidgetItem(str(beverage_id))
            id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.products_table.setItem(row, 0, id_item)

            # Name
            self.products_table.setItem(row, 1, QTableWidgetItem(name))

            # Category
            self.products_table.setItem(row, 2, QTableWidgetItem(category))

            # Customer Price
            unit_item = QTableWidgetItem(f"${unit_price:.2f}")
            self.products_table.setItem(row, 3, unit_item)

            # Our Cost
            cost_item = QTableWidgetItem(f"${our_cost:.2f}")
            self.products_table.setItem(row, 4, cost_item)

            # Margin %
            if unit_price > 0:
                margin_pct = (unit_price - our_cost) / unit_price * 100
                color = (
                    QColor("green")
                    if margin_pct >= 30
                    else (
                        QColor("orange") if margin_pct >= 20 else QColor("red")
                    )
                )
                margin_item = QTableWidgetItem(f"{margin_pct:.1f}%")
                margin_item.setForeground(QBrush(color))
                margin_item.setFlags(
                    margin_item.flags() & ~Qt.ItemFlag.ItemIsEditable
                )
                self.products_table.setItem(row, 5, margin_item)

            # Active
            active_item = QTableWidgetItem("Yes" if is_active else "No")
            self.products_table.setItem(row, 6, active_item)

    def filter_products(self) -> None:
        """Filter products by hiding non-matching rows (preserves edits)."""
        search_text = self.search_input.text().strip().lower()
        for row in range(self.products_table.rowCount()):
            name_item = self.products_table.item(row, 1)
            cat_item = self.products_table.item(row, 2)
            name = (name_item.text() if name_item else "").lower()
            cat = (cat_item.text() if cat_item else "").lower()
            hidden = bool(search_text) and (
                search_text not in name and search_text not in cat
            )
            self.products_table.setRowHidden(row, hidden)

    # ========================================================================
    # ADD NEW PRODUCT
    # ========================================================================

    def auto_calc_cost(self) -> None:
        """Auto-calculate sell price from cost using editable markup %."""
        cost = self.new_cost.value()
        markup_pct = self.new_markup_percent.value()
        multiplier = 1.0 + (markup_pct / 100.0)
        sell_price = round(cost * multiplier, 2)
        self.new_unit_price.setValue(max(0.99, sell_price))

    def normalize_deposit_and_markup(self) -> None:
        """Set 25% markup and clear any stored deposit values."""
        if not self._require_write_enabled():
            return

        category_filter = self.adjust_category.currentText()
        scope_text = (
            "all categories"
            if category_filter == "All Categories"
            else f"category '{category_filter}'"
        )
        reply = QMessageBox.question(
            self,
            "Confirm Normalize",
            (
                "Apply to "
                f"{scope_text}?\n\n"
                "This will:\n"
                "1) Set sell price to 25% markup over Our Cost\n"
                "2) Set deposit column to $0.00"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        updated = 0
        skipped = 0
        try:
            with DatabaseContext(self.db_conn, auto_commit=True) as cur:
                for product in self.all_products:
                    (
                        beverage_id,
                        name,
                        category,
                        _unit_price,
                        our_cost,
                        _deposit,
                        _is_active,
                    ) = product

                    if (
                        category_filter != "All Categories"
                        and category != category_filter
                    ):
                        continue

                    cost_val = float(our_cost or 0)
                    if cost_val <= 0:
                        skipped += 1
                        continue

                    new_price = round(cost_val * self.TARGET_MARKUP_MULTIPLIER, 2)
                    new_deposit = 0.0

                    assignments = [f"{self._col_price} = %s"]
                    values = [new_price]
                    if self._col_deposit:
                        assignments.append(f"{self._col_deposit} = %s")
                        values.append(new_deposit)

                    values.append(beverage_id)
                    cur.execute(
                        f"""
                        UPDATE {self._table_name}
                        SET {', '.join(assignments)}
                        WHERE {self._id_col} = %s
                        """,
                        tuple(values),
                    )
                    updated += 1

            self.load_data()
            QMessageBox.information(
                self,
                "Normalization Complete",
                (
                    f"Updated {updated} items with 25% markup.\n"
                    "Deposit column was reset to $0.00 to avoid double-charge.\n"
                    f"Skipped {skipped} items with zero/blank cost."
                ),
            )
        except Exception as e:
            logger.error(f"Failed to normalize deposit and markup: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to normalize deposit and markup: {e}",
            )

    def add_new_product(self) -> None:
        """Add new beverage product to database"""
        if not self._require_write_enabled():
            return

        name = self.new_name.text().strip()
        category = self.new_category.currentText()
        unit_price = self.new_unit_price.value()
        our_cost = self.new_cost.value()
        deposit = 0.0

        if not name:
            QMessageBox.warning(
                self, "Validation", "Please enter a product name"
            )
            return

        try:
            with DatabaseContext(self.db_conn, auto_commit=True) as cur:
                columns = [self._col_name, "category"]
                values = [name, category]

                columns.append(self._col_price)
                values.append(unit_price)

                if self._col_cost:
                    columns.append(self._col_cost)
                    values.append(our_cost)

                if self._col_deposit:
                    columns.append(self._col_deposit)
                    values.append(deposit)

                if self._col_active:
                    columns.append("is_active")
                    values.append(True)

                if "gst_included" in self._beverage_columns:
                    columns.append("gst_included")
                    values.append(True)

                placeholders = ", ".join(["%s"] * len(values))
                col_sql = ", ".join(columns)

                # Ensure the sequence is ahead of the current max id (guards
                # against sequences that fell behind due to manual inserts).
                cur.execute(f"""
                    SELECT setval(
                        pg_get_serial_sequence('{self._table_name}', '{self._id_col}'),
                        COALESCE((SELECT MAX({self._id_col}) FROM {self._table_name}), 0) + 1,
                        false
                    )
                """)

                cur.execute(
                    f"""
                    INSERT INTO {self._table_name} ({col_sql})
                    VALUES ({placeholders})
                    RETURNING {self._id_col}
                    """,
                    tuple(values),
                )
                new_id = cur.fetchone()[0]

            QMessageBox.information(
                self, "Success", f"✅ Added {name} (Beverage #{new_id})"
            )

            # Clear form
            self.new_name.clear()
            self.new_unit_price.setValue(5.49)
            markup_pct = self.new_markup_percent.value() if hasattr(self, "new_markup_percent") else 25.0
            multiplier = 1.0 + (markup_pct / 100.0)
            if multiplier <= 0:
                multiplier = self.TARGET_MARKUP_MULTIPLIER
            self.new_cost.setValue(round(5.49 / multiplier, 2))

            # Reload
            self.load_data()
            if hasattr(self, "catalog_tabs"):
                self.catalog_tabs.setCurrentIndex(0)
        except Exception as e:
            logger.error(f"Failed to add product: {e}")
            QMessageBox.critical(self, "Error", f"Failed to add product: {e}")

    # ========================================================================
    # BULK PRICE ADJUSTMENTS
    # ========================================================================

    def preview_bulk_adjust(self) -> None:
        """Preview bulk price adjustments"""
        category_filter = self.adjust_category.currentText()
        adjust_type = self.adjust_type.currentText()
        adjust_amount = self.adjust_amount.value()

        self.adjust_preview_table.setRowCount(0)

        for product in self.all_products:
            (
                beverage_id,
                name,
                category,
                unit_price,
                our_cost,
                deposit,
                is_active,
            ) = product

            if category_filter != "All Categories" and category != category_filter:
                continue

            # Calculate new prices
            if "Percentage" in adjust_type:
                factor = (
                    1 + (adjust_amount / 100)
                    if "Increase" in adjust_type
                    else 1 - (adjust_amount / 100)
                )
                new_unit_price = round(unit_price * factor, 2)
                new_cost = (
                    round(our_cost * factor, 2)
                    if self.adjust_cost_too.isChecked()
                    else our_cost
                )
            else:
                new_unit_price = (
                    unit_price + adjust_amount
                    if "Add" in adjust_type
                    else unit_price - adjust_amount
                )
                new_cost = (
                    our_cost + adjust_amount
                    if self.adjust_cost_too.isChecked()
                    else our_cost
                )
                new_unit_price = max(0.99, new_unit_price)
                new_cost = max(0.0, new_cost)

            # Add to preview table
            row = self.adjust_preview_table.rowCount()
            self.adjust_preview_table.insertRow(row)

            self.adjust_preview_table.setItem(row, 0, QTableWidgetItem(name))
            self.adjust_preview_table.item(row, 0).setData(
                Qt.ItemDataRole.UserRole, beverage_id
            )
            self.adjust_preview_table.setItem(
                row, 1, QTableWidgetItem(f"${unit_price:.2f}")
            )
            self.adjust_preview_table.setItem(
                row, 2, QTableWidgetItem(f"${new_unit_price:.2f}")
            )
            self.adjust_preview_table.setItem(
                row, 3, QTableWidgetItem(f"${our_cost:.2f}")
            )
            self.adjust_preview_table.setItem(
                row, 4, QTableWidgetItem(f"${new_cost:.2f}")
            )

            diff = new_unit_price - unit_price
            impact_item = QTableWidgetItem(f"${diff:+.2f}")
            impact_color = QColor("green") if diff >= 0 else QColor("red")
            impact_item.setForeground(QBrush(impact_color))
            self.adjust_preview_table.setItem(row, 5, impact_item)

    def apply_bulk_adjust(self) -> None:
        """Apply bulk price adjustments to database"""
        if not self._require_write_enabled():
            return

        reply = QMessageBox.question(
            self,
            "Confirm",
            "Apply all preview changes to database?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            with DatabaseContext(self.db_conn, auto_commit=True) as cur:
                # Apply each change from preview table
                for row in range(self.adjust_preview_table.rowCount()):
                    new_price_text = (
                        self.adjust_preview_table.item(row, 2)
                        .text()
                        .replace("$", "")
                    )
                    new_cost_text = (
                        self.adjust_preview_table.item(row, 4)
                        .text()
                        .replace("$", "")
                    )
                    new_price = float(new_price_text)
                    new_cost = float(new_cost_text)
                    beverage_id = self.adjust_preview_table.item(
                        row, 0
                    ).data(Qt.ItemDataRole.UserRole)

                    if self._col_cost:
                        cur.execute(
                            f"""
                            UPDATE {self._table_name}
                            SET {self._col_price} = %s, {self._col_cost} = %s
                            WHERE {self._id_col} = %s
                            """,
                            (new_price, new_cost, beverage_id),
                        )
                    else:
                        cur.execute(
                            f"""
                            UPDATE {self._table_name}
                            SET {self._col_price} = %s
                            WHERE {self._id_col} = %s
                            """,
                            (new_price, beverage_id),
                        )

            QMessageBox.information(
                self, "Success", "✅ Applied all price adjustments"
            )
            self.load_data()
        except Exception as e:
            logger.error(f"Failed to apply adjustments: {e}")
            QMessageBox.critical(
                self, "Error", f"Failed to apply adjustments: {e}"
            )

    # ========================================================================
    # MARGIN ANALYSIS
    # ========================================================================

    def update_margin_stats(self) -> None:
        """Update margin statistics"""
        if not self.all_products:
            return

        total_items = len(self.all_products)
        self.total_items_label.setText(f"Total Items: {total_items}")

        margins = []
        low_margin_count = 0

        for product in self.all_products:
            (
                beverage_id,
                name,
                category,
                unit_price,
                our_cost,
                deposit,
                is_active,
            ) = product
            if unit_price > 0:
                margin_pct = (unit_price - our_cost) / unit_price * 100
                margins.append(margin_pct)
                if margin_pct < 20:
                    low_margin_count += 1

        avg_margin = sum(margins) / len(margins) if margins else 0
        self.avg_margin_label.setText(f"Avg Margin: {avg_margin:.1f}%")
        self.low_margin_label.setText(
            f"⚠️ Low Margin Items (<20%): {low_margin_count}"
        )

        # Populate margins table
        self.margins_table.setRowCount(0)
        for product in sorted(
            self.all_products,
            key=lambda x: ((x[3] - x[4]) / x[3] * 100 if x[3] > 0 else 0),
            reverse=True,
        ):
            (
                beverage_id,
                name,
                category,
                unit_price,
                our_cost,
                deposit,
                is_active,
            ) = product

            if unit_price > 0:
                margin_pct = (unit_price - our_cost) / unit_price * 100
                margin_dollar = unit_price - our_cost

                row = self.margins_table.rowCount()
                self.margins_table.insertRow(row)

                self.margins_table.setItem(row, 0, QTableWidgetItem(name))
                self.margins_table.setItem(
                    row, 1, QTableWidgetItem(f"${unit_price:.2f}")
                )
                self.margins_table.setItem(
                    row, 2, QTableWidgetItem(f"${our_cost:.2f}")
                )
                self.margins_table.setItem(
                    row, 3, QTableWidgetItem(f"${margin_dollar:.2f}")
                )
                self.margins_table.setItem(
                    row, 4, QTableWidgetItem(f"{margin_pct:.1f}%")
                )
                # Volume would come from actual sales
                self.margins_table.setItem(row, 5, QTableWidgetItem("TBD"))
                self.margins_table.setItem(row, 6, QTableWidgetItem("TBD"))

    def delete_selected_product(self) -> None:
        """Delete (or deactivate) the selected row in the catalog table."""
        if not self._require_write_enabled():
            return

        selected = self.products_table.selectedItems()
        if not selected:
            QMessageBox.warning(
                self, "No Selection", "Please select a row to delete."
            )
            return

        row = self.products_table.currentRow()
        id_item = self.products_table.item(row, 0)
        name_item = self.products_table.item(row, 1)
        if not id_item:
            return

        beverage_id = int(id_item.text())
        name = name_item.text() if name_item else str(beverage_id)

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete '{name}' (ID {beverage_id}) from the beverage catalog?\n\n"
            f"If this beverage is linked to existing charter orders it will be "
            f"deactivated instead of removed.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            with DatabaseContext(self.db_conn, auto_commit=True) as cur:
                try:
                    cur.execute(
                        f"DELETE FROM {self._table_name} WHERE {self._id_col} = %s",
                        (beverage_id,),
                    )
                    msg = f"✅ Deleted '{name}' from catalog."
                except Exception:
                    msg = (
                        f"Could not delete '{name}'. It may be linked to "
                        f"existing orders."
                    )

            QMessageBox.information(self, "Done", msg)
            self.load_data()
        except Exception as e:
            logger.error(f"Failed to delete beverage {beverage_id}: {e}")
            QMessageBox.critical(self, "Error", f"Failed to delete: {e}")

    def save_catalog_changes(self) -> None:
        """Save edited catalog values (customer price/cost/deposit/active)."""
        if not self._require_write_enabled():
            return

        try:
            with DatabaseContext(self.db_conn, auto_commit=True) as cur:
                for row in range(self.products_table.rowCount()):
                    id_item = self.products_table.item(row, 0)
                    if not id_item:
                        continue

                    beverage_id = int(id_item.text())
                    name = self.products_table.item(row, 1).text().strip()
                    category = self.products_table.item(row, 2).text().strip()
                    price_text = self.products_table.item(row, 3).text().replace(
                        "$", ""
                    )
                    cost_text = self.products_table.item(row, 4).text().replace(
                        "$", ""
                    )
                    active_text = self.products_table.item(row, 6).text().strip().lower()

                    unit_price = max(0.0, float(price_text or 0))
                    our_cost = max(0.0, float(cost_text or 0))
                    is_active = active_text in ("yes", "y", "true", "1")

                    assignments = [f"{self._col_name} = %s", "category = %s"]
                    values = [name, category]

                    assignments.append(f"{self._col_price} = %s")
                    values.append(unit_price)

                    if self._col_cost:
                        assignments.append(f"{self._col_cost} = %s")
                        values.append(our_cost)

                    if self._col_deposit:
                        assignments.append(f"{self._col_deposit} = %s")
                        values.append(0.0)

                    if self._col_active == "is_active":
                        assignments.append("is_active = %s")
                        values.append(is_active)

                    values.append(beverage_id)

                    cur.execute(
                        f"""
                        UPDATE {self._table_name}
                        SET {', '.join(assignments)}
                        WHERE {self._id_col} = %s
                        """,
                        tuple(values),
                    )

            QMessageBox.information(
                self,
                "Success",
                "✅ Beverage catalog changes saved",
            )
            self.load_data()
        except Exception as e:
            logger.error(f"Failed to save beverage catalog: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save beverage catalog: {e}",
            )

    def export_margins(self) -> None:
        """Export margin report to CSV"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Margins Report", "", "CSV Files (*.csv)"
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "Product",
                        "Unit Price",
                        "Our Cost",
                        "Margin $",
                        "Margin %",
                    ]
                )

                for row in range(self.margins_table.rowCount()):
                    product = self.margins_table.item(row, 0).text()
                    unit_price = self.margins_table.item(row, 1).text()
                    our_cost = self.margins_table.item(row, 2).text()
                    margin_dollar = self.margins_table.item(row, 3).text()
                    margin_pct = self.margins_table.item(row, 4).text()

                    writer.writerow(
                        [
                            product,
                            unit_price,
                            our_cost,
                            margin_dollar,
                            margin_pct,
                        ]
                    )

            QMessageBox.information(
                self, "Success", f"✅ Report exported to {file_path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export: {e}")

    # ========================================================================
    # CHARTER COST TRACKING
    # ========================================================================

    def search_charter_costs(self) -> None:
        """Search and display beverage costs by charter"""
        from_py = self.from_date.date().toPyDate()
        to_py = self.to_date.date().toPyDate()
        self.group_by.currentText()

        try:
            with DatabaseContext(self.db_conn, auto_commit=False) as cur:
                # Query beverage usage by charter within date range
                cur.execute(
                    """
                    SELECT
                        c.charter_id,
                        c.reserve_number,
                        c.charter_date,
                        COUNT(cc.charge_id) as item_count,
                        SUM(cc.amount) as revenue,
                        COUNT(cc.charge_id) as beverage_count,
                        0 as cost_total
                    FROM charters c
                    LEFT JOIN charter_charges cc ON cc.charter_id =
                    c.charter_id
                    WHERE c.charter_date BETWEEN %s AND %s
                      AND cc.charge_type = 'beverage'
                    GROUP BY c.charter_id, c.reserve_number, c.charter_date
                    ORDER BY c.charter_date DESC
                """,
                    (from_py, to_py),
                )

                results = cur.fetchall()

            self.charter_costs_table.setRowCount(0)

            for result in results:
                (
                    charter_id,
                    reserve_no,
                    charter_date,
                    item_count,
                    revenue,
                    bev_count,
                    cost_total,
                ) = result

                if item_count and cost_total:
                    margin = revenue - cost_total if revenue else 0
                    margin_pct = (margin / revenue * 100) if revenue else 0
                    avg_per_item = revenue / item_count if item_count else 0

                    row = self.charter_costs_table.rowCount()
                    self.charter_costs_table.insertRow(row)

                    self.charter_costs_table.setItem(
                        row,
                        0,
                        QTableWidgetItem(f"#{reserve_no} ({charter_date})"),
                    )
                    self.charter_costs_table.setItem(
                        row, 1, QTableWidgetItem(str(item_count))
                    )
                    self.charter_costs_table.setItem(
                        row, 2, QTableWidgetItem(f"${cost_total:.2f}")
                    )
                    self.charter_costs_table.setItem(
                        row, 3, QTableWidgetItem(f"${revenue:.2f}")
                    )
                    self.charter_costs_table.setItem(
                        row, 4, QTableWidgetItem(f"${margin:.2f}")
                    )
                    self.charter_costs_table.setItem(
                        row, 5, QTableWidgetItem(f"{margin_pct:.1f}%")
                    )
                    self.charter_costs_table.setItem(
                        row, 6, QTableWidgetItem(f"${avg_per_item:.2f}")
                    )

            QMessageBox.information(
                self,
                "Search Complete",
                f"Found {len(results)} charters with beverage costs",
            )
        except Exception as e:
            logger.error(f"Search failed: {e}")
            QMessageBox.critical(self, "Error", f"Search failed: {e}")

    def export_charter_costs(self) -> None:
        """Export charter costs report"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Charter Costs", "", "CSV Files (*.csv)"
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "Charter/Period",
                        "Items Count",
                        "Our Cost Total",
                        "Revenue Total",
                        "Gross Margin",
                        "Margin %",
                        "Avg per Item",
                    ]
                )

                for row in range(self.charter_costs_table.rowCount()):
                    writer.writerow(
                        [
                            self.charter_costs_table.item(row, col).text()
                            for col in range(
                                self.charter_costs_table.columnCount() - 1
                            )
                        ]
                    )

            QMessageBox.information(
                self, "Success", f"✅ Report exported to {file_path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export: {e}")
