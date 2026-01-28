"""
Beverage Management Widget
Dispatcher/Admin tool for:
- Add new beverage products to catalog
- Manage pricing (unit price, cost, deposit)
- Bulk price adjustments with percentage/fixed amount
- Cost tracking per charter, per month, per year
- Margin analysis and profitability
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QDoubleSpinBox, QLineEdit,
    QComboBox, QSpinBox, QMessageBox, QFileDialog, QTabWidget,
    QGroupBox, QFormLayout, QHeaderView, QCheckBox, QDateEdit,
    QDialog, QInputDialog, QScrollArea, QProgressBar
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QBrush, QIcon
import psycopg2
import os
from datetime import datetime, timedelta
from decimal import Decimal
import csv
import json

class BeverageManagementWidget(QWidget):
    """Manage beverage products, pricing, and cost tracking"""
    
    def __init__(self, db_conn, parent=None):
        super().__init__(parent)
        self.db_conn = db_conn
        self.init_ui()
        self.load_data()
    
    def init_ui(self):
        """Initialize UI with tabs for different functions"""
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("🍷 Beverage Management")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
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
    
    def create_catalog_tab(self):
        """Tab 1: Add/edit beverage products"""
        widget = QWidget()
        layout = QVBoxLayout()
        
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
        
        layout.addLayout(header_layout)
        
        # Products table
        self.products_table = QTableWidget()
        self.products_table.setColumnCount(8)
        self.products_table.setHorizontalHeaderLabels([
            "Item ID", "Name", "Category", "Unit Price", "Our Cost", "Deposit", "Margin %", "Actions"
        ])
        self.products_table.setColumnWidth(1, 200)
        self.products_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.products_table)
        
        # Add new product section
        add_group = QGroupBox("➕ Add New Beverage Product")
        add_layout = QFormLayout()
        
        self.new_name = QLineEdit()
        self.new_name.setPlaceholderText("e.g., Corona Extra 355ml")
        add_layout.addRow("Product Name:", self.new_name)
        
        self.new_category = QComboBox()
        self.new_category.addItems([
            "Beer", "Spirits", "Wine", "Ready-To-Drink", "Hard Seltzers",
            "Champagne", "Water", "Iced Tea", "Mixers", "Non-Alcoholic", "Energy Drink"
        ])
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
        
        # Auto-calculate at 70%
        auto_calc_btn = QPushButton("Calculate @ 70%")
        auto_calc_btn.clicked.connect(self.auto_calc_cost)
        add_layout.addRow("", auto_calc_btn)
        
        self.new_deposit = QDoubleSpinBox()
        self.new_deposit.setRange(0.0, 5.0)
        self.new_deposit.setValue(0.0)
        self.new_deposit.setSingleStep(0.10)
        add_layout.addRow("Deposit Amount:", self.new_deposit)
        
        add_btn = QPushButton("✅ Add Product")
        add_btn.clicked.connect(self.add_new_product)
        add_layout.addRow("", add_btn)
        
        add_group.setLayout(add_layout)
        layout.addWidget(add_group)
        
        widget.setLayout(layout)
        return widget
    
    def create_bulk_adjust_tab(self):
        """Tab 2: Bulk price adjustments"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Category filter
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter by Category:"))
        self.adjust_category = QComboBox()
        self.adjust_category.addItem("All Categories", None)
        self.adjust_category.addItems([
            "Beer", "Spirits", "Wine", "Ready-To-Drink", "Hard Seltzers",
            "Champagne", "Water", "Iced Tea", "Mixers", "Non-Alcoholic", "Energy Drink"
        ])
        filter_layout.addWidget(self.adjust_category)
        layout.addLayout(filter_layout)
        
        # Adjustment options
        adjust_group = QGroupBox("🔧 Price Adjustment Options")
        adjust_layout = QFormLayout()
        
        self.adjust_type = QComboBox()
        self.adjust_type.addItems(["Percentage Increase", "Percentage Decrease", "Fixed Amount Add", "Fixed Amount Subtract"])
        adjust_layout.addRow("Adjustment Type:", self.adjust_type)
        
        self.adjust_amount = QDoubleSpinBox()
        self.adjust_amount.setRange(0.01, 99.99)
        self.adjust_amount.setValue(5.0)
        self.adjust_amount.setSingleStep(0.01)
        adjust_layout.addRow("Adjustment Value:", self.adjust_amount)
        
        self.adjust_cost_too = QCheckBox("Also adjust our_cost proportionally?")
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
        self.adjust_preview_table.setHorizontalHeaderLabels([
            "Product", "Current Price", "New Price", "Current Cost", "New Cost", "Impact"
        ])
        layout.addWidget(self.adjust_preview_table)
        
        # Apply button
        apply_btn = QPushButton("✅ Apply All Changes")
        apply_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        apply_btn.clicked.connect(self.apply_bulk_adjust)
        layout.addWidget(apply_btn)
        
        widget.setLayout(layout)
        return widget
    
    def create_cost_tracking_tab(self):
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
        self.margins_table.setHorizontalHeaderLabels([
            "Product", "Unit Price", "Our Cost", "Margin $", "Margin %", "Volume Sold", "Total Margin"
        ])
        self.margins_table.setColumnWidth(0, 200)
        self.margins_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.margins_table)
        
        # Export button
        export_btn = QPushButton("💾 Export Margin Report")
        export_btn.clicked.connect(self.export_margins)
        layout.addWidget(export_btn)
        
        widget.setLayout(layout)
        return widget
    
    def create_charter_costs_tab(self):
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
        self.group_by.addItems(["Charter", "Month", "Year", "Driver", "Category"])
        group_layout.addWidget(self.group_by)
        layout.addLayout(group_layout)
        
        # Results table
        self.charter_costs_table = QTableWidget()
        self.charter_costs_table.setColumnCount(8)
        self.charter_costs_table.setHorizontalHeaderLabels([
            "Charter/Period", "Items Count", "Our Cost Total", "Revenue Total",
            "Gross Margin", "Margin %", "Avg per Item", "Details"
        ])
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
    
    def load_data(self):
        """Load all beverage products from database"""
        try:
            cur = self.db_conn.get_cursor()
            cur.execute("""
                SELECT item_id, item_name, category, unit_price, our_cost, deposit_amount
                FROM beverage_products
                ORDER BY category, item_name
            """)
            self.all_products = cur.fetchall()
            cur.close()
            
            self.refresh_products_table()
            self.update_margin_stats()
            
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.critical(self, "Database Error", f"Failed to load products: {e}")
    
    def refresh_products_table(self, filter_text=""):
        """Refresh the products catalog table"""
        self.products_table.setRowCount(0)
        
        for product in self.all_products:
            item_id, name, category, unit_price, our_cost, deposit = product
            
            # Apply filter
            if filter_text and filter_text.lower() not in name.lower() and filter_text.lower() not in category.lower():
                continue
            
            row = self.products_table.rowCount()
            self.products_table.insertRow(row)
            
            # Item ID
            id_item = QTableWidgetItem(str(item_id))
            id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.products_table.setItem(row, 0, id_item)
            
            # Name
            self.products_table.setItem(row, 1, QTableWidgetItem(name))
            
            # Category
            self.products_table.setItem(row, 2, QTableWidgetItem(category))
            
            # Unit Price
            unit_item = QTableWidgetItem(f"${unit_price:.2f}")
            unit_item.setFlags(unit_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.products_table.setItem(row, 3, unit_item)
            
            # Our Cost
            cost_item = QTableWidgetItem(f"${our_cost:.2f}")
            self.products_table.setItem(row, 4, cost_item)
            
            # Deposit
            deposit_item = QTableWidgetItem(f"${deposit:.2f}" if deposit else "$0.00")
            self.products_table.setItem(row, 5, deposit_item)
            
            # Margin %
            if unit_price > 0:
                margin_pct = ((unit_price - our_cost) / unit_price * 100)
                color = QColor("green") if margin_pct >= 30 else QColor("orange") if margin_pct >= 20 else QColor("red")
                margin_item = QTableWidgetItem(f"{margin_pct:.1f}%")
                margin_item.setForeground(QBrush(color))
                margin_item.setFlags(margin_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.products_table.setItem(row, 6, margin_item)
            
            # Actions
            actions_item = QTableWidgetItem("Edit | Delete")
            actions_item.setFlags(actions_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.products_table.setItem(row, 7, actions_item)
    
    def filter_products(self):
        """Filter products based on search text"""
        search_text = self.search_input.text()
        self.refresh_products_table(search_text)
    
    # ========================================================================
    # ADD NEW PRODUCT
    # ========================================================================
    
    def auto_calc_cost(self):
        """Auto-calculate cost at 70% of unit price"""
        unit_price = self.new_unit_price.value()
        cost = round(unit_price * 0.70, 2)
        self.new_cost.setValue(cost)
    
    def add_new_product(self):
        """Add new beverage product to database"""
        name = self.new_name.text().strip()
        category = self.new_category.currentText()
        unit_price = self.new_unit_price.value()
        our_cost = self.new_cost.value()
        deposit = self.new_deposit.value()
        
        if not name:
            QMessageBox.warning(self, "Validation", "Please enter a product name")
            return
        
        try:
            cur = self.db_conn.get_cursor()
            
            # Get next item_id
            cur.execute("SELECT MAX(item_id) FROM beverage_products")
            max_id = cur.fetchone()[0] or 0
            next_id = max_id + 1
            
            # Insert
            cur.execute("""
                INSERT INTO beverage_products 
                (item_id, item_name, unit_price, our_cost, deposit_amount, category, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
            """, (next_id, name, unit_price, our_cost, deposit, category))
            
            self.db_conn.commit()
            
            QMessageBox.information(self, "Success", f"✅ Added {name} (Item #{next_id})")
            
            # Clear form
            self.new_name.clear()
            self.new_unit_price.setValue(5.49)
            self.new_cost.setValue(3.84)
            self.new_deposit.setValue(0.0)
            
            # Reload
            self.load_data()
            
        except Exception as e:
            self.db_conn.rollback()
            QMessageBox.critical(self, "Error", f"Failed to add product: {e}")
    
    # ========================================================================
    # BULK PRICE ADJUSTMENTS
    # ========================================================================
    
    def preview_bulk_adjust(self):
        """Preview bulk price adjustments"""
        category_filter = self.adjust_category.currentData()
        adjust_type = self.adjust_type.currentText()
        adjust_amount = self.adjust_amount.value()
        
        self.adjust_preview_table.setRowCount(0)
        
        for product in self.all_products:
            item_id, name, category, unit_price, our_cost, deposit = product
            
            if category_filter and category != category_filter:
                continue
            
            # Calculate new prices
            if "Percentage" in adjust_type:
                factor = 1 + (adjust_amount / 100) if "Increase" in adjust_type else 1 - (adjust_amount / 100)
                new_unit_price = round(unit_price * factor, 2)
                new_cost = round(our_cost * factor, 2) if self.adjust_cost_too.isChecked() else our_cost
            else:
                new_unit_price = unit_price + adjust_amount if "Add" in adjust_type else unit_price - adjust_amount
                new_cost = our_cost + adjust_amount if self.adjust_cost_too.isChecked() else our_cost
                new_unit_price = max(0.99, new_unit_price)
                new_cost = max(0.0, new_cost)
            
            # Add to preview table
            row = self.adjust_preview_table.rowCount()
            self.adjust_preview_table.insertRow(row)
            
            self.adjust_preview_table.setItem(row, 0, QTableWidgetItem(name))
            self.adjust_preview_table.setItem(row, 1, QTableWidgetItem(f"${unit_price:.2f}"))
            self.adjust_preview_table.setItem(row, 2, QTableWidgetItem(f"${new_unit_price:.2f}"))
            self.adjust_preview_table.setItem(row, 3, QTableWidgetItem(f"${our_cost:.2f}"))
            self.adjust_preview_table.setItem(row, 4, QTableWidgetItem(f"${new_cost:.2f}"))
            
            diff = new_unit_price - unit_price
            impact_item = QTableWidgetItem(f"${diff:+.2f}")
            impact_color = QColor("green") if diff >= 0 else QColor("red")
            impact_item.setForeground(QBrush(impact_color))
            self.adjust_preview_table.setItem(row, 5, impact_item)
    
    def apply_bulk_adjust(self):
        """Apply bulk price adjustments to database"""
        reply = QMessageBox.question(self, "Confirm", 
                                     "Apply all preview changes to database?\nThis cannot be undone.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        try:
            cur = self.db_conn.get_cursor()
            
            # Apply each change from preview table
            for row in range(self.adjust_preview_table.rowCount()):
                new_price_text = self.adjust_preview_table.item(row, 2).text().replace("$", "")
                new_price = float(new_price_text)
                
                # Find matching product and update
                product_name = self.adjust_preview_table.item(row, 0).text()
                for product in self.all_products:
                    if product[1] == product_name:
                        cur.execute("""
                            UPDATE beverage_products 
                            SET unit_price = %s
                            WHERE item_id = %s
                        """, (new_price, product[0]))
                        break
            
            self.db_conn.commit()
            QMessageBox.information(self, "Success", "✅ Applied all price adjustments")
            self.load_data()
            
        except Exception as e:
            self.db_conn.rollback()
            QMessageBox.critical(self, "Error", f"Failed to apply adjustments: {e}")
    
    # ========================================================================
    # MARGIN ANALYSIS
    # ========================================================================
    
    def update_margin_stats(self):
        """Update margin statistics"""
        if not self.all_products:
            return
        
        total_items = len(self.all_products)
        self.total_items_label.setText(f"Total Items: {total_items}")
        
        margins = []
        low_margin_count = 0
        
        for product in self.all_products:
            item_id, name, category, unit_price, our_cost, deposit = product
            if unit_price > 0:
                margin_pct = ((unit_price - our_cost) / unit_price * 100)
                margins.append(margin_pct)
                if margin_pct < 20:
                    low_margin_count += 1
        
        avg_margin = sum(margins) / len(margins) if margins else 0
        self.avg_margin_label.setText(f"Avg Margin: {avg_margin:.1f}%")
        self.low_margin_label.setText(f"⚠️ Low Margin Items (<20%): {low_margin_count}")
        
        # Populate margins table
        self.margins_table.setRowCount(0)
        for product in sorted(self.all_products, key=lambda x: ((x[3] - x[4]) / x[3] * 100 if x[3] > 0 else 0), reverse=True):
            item_id, name, category, unit_price, our_cost, deposit = product
            
            if unit_price > 0:
                margin_pct = ((unit_price - our_cost) / unit_price * 100)
                margin_dollar = unit_price - our_cost
                
                row = self.margins_table.rowCount()
                self.margins_table.insertRow(row)
                
                self.margins_table.setItem(row, 0, QTableWidgetItem(name))
                self.margins_table.setItem(row, 1, QTableWidgetItem(f"${unit_price:.2f}"))
                self.margins_table.setItem(row, 2, QTableWidgetItem(f"${our_cost:.2f}"))
                self.margins_table.setItem(row, 3, QTableWidgetItem(f"${margin_dollar:.2f}"))
                self.margins_table.setItem(row, 4, QTableWidgetItem(f"{margin_pct:.1f}%"))
                self.margins_table.setItem(row, 5, QTableWidgetItem("TBD"))  # Volume would come from actual sales
                self.margins_table.setItem(row, 6, QTableWidgetItem("TBD"))
    
    def export_margins(self):
        """Export margin report to CSV"""
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Margins Report", "", "CSV Files (*.csv)")
        if not file_path:
            return
        
        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Product", "Unit Price", "Our Cost", "Margin $", "Margin %"])
                
                for row in range(self.margins_table.rowCount()):
                    product = self.margins_table.item(row, 0).text()
                    unit_price = self.margins_table.item(row, 1).text()
                    our_cost = self.margins_table.item(row, 2).text()
                    margin_dollar = self.margins_table.item(row, 3).text()
                    margin_pct = self.margins_table.item(row, 4).text()
                    
                    writer.writerow([product, unit_price, our_cost, margin_dollar, margin_pct])
            
            QMessageBox.information(self, "Success", f"✅ Report exported to {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export: {e}")
    
    # ========================================================================
    # CHARTER COST TRACKING
    # ========================================================================
    
    def search_charter_costs(self):
        """Search and display beverage costs by charter"""
        from_date = self.from_date.date().toString("yyyy-MM-dd")
        to_date = self.to_date.date().toString("yyyy-MM-dd")
        group_by = self.group_by.currentText()
        
        try:
            cur = self.db_conn.get_cursor()
            
            # Query beverage usage by charter within date range
            cur.execute("""
                SELECT 
                    c.charter_id,
                    c.reserve_number,
                    c.charter_date,
                    COUNT(cc.charge_id) as item_count,
                    SUM(cc.charge_amount) as revenue,
                    COUNT(bp.item_id) as beverage_count,
                    SUM(bp.our_cost) as cost_total
                FROM charters c
                LEFT JOIN charter_charges cc ON cc.charter_id = c.charter_id
                LEFT JOIN beverage_products bp ON bp.item_name ILIKE cc.charge_description
                WHERE c.charter_date BETWEEN %s AND %s
                  AND cc.charge_type = 'beverage'
                GROUP BY c.charter_id, c.reserve_number, c.charter_date
                ORDER BY c.charter_date DESC
            """, (from_date, to_date))
            
            results = cur.fetchall()
            cur.close()
            
            self.charter_costs_table.setRowCount(0)
            
            for result in results:
                charter_id, reserve_no, charter_date, item_count, revenue, bev_count, cost_total = result
                
                if item_count and cost_total:
                    margin = revenue - cost_total if revenue else 0
                    margin_pct = (margin / revenue * 100) if revenue else 0
                    avg_per_item = revenue / item_count if item_count else 0
                    
                    row = self.charter_costs_table.rowCount()
                    self.charter_costs_table.insertRow(row)
                    
                    self.charter_costs_table.setItem(row, 0, QTableWidgetItem(f"#{reserve_no} ({charter_date})"))
                    self.charter_costs_table.setItem(row, 1, QTableWidgetItem(str(item_count)))
                    self.charter_costs_table.setItem(row, 2, QTableWidgetItem(f"${cost_total:.2f}"))
                    self.charter_costs_table.setItem(row, 3, QTableWidgetItem(f"${revenue:.2f}"))
                    self.charter_costs_table.setItem(row, 4, QTableWidgetItem(f"${margin:.2f}"))
                    self.charter_costs_table.setItem(row, 5, QTableWidgetItem(f"{margin_pct:.1f}%"))
                    self.charter_costs_table.setItem(row, 6, QTableWidgetItem(f"${avg_per_item:.2f}"))
            
            QMessageBox.information(self, "Search Complete", f"Found {len(results)} charters with beverage costs")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Search failed: {e}")
    
    def export_charter_costs(self):
        """Export charter costs report"""
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Charter Costs", "", "CSV Files (*.csv)")
        if not file_path:
            return
        
        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Charter/Period", "Items Count", "Our Cost Total", "Revenue Total", 
                                "Gross Margin", "Margin %", "Avg per Item"])
                
                for row in range(self.charter_costs_table.rowCount()):
                    writer.writerow([
                        self.charter_costs_table.item(row, col).text() 
                        for col in range(self.charter_costs_table.columnCount() - 1)
                    ])
            
            QMessageBox.information(self, "Success", f"✅ Report exported to {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export: {e}")
