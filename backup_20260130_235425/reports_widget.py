"""
Advanced Drill-Down Reports Module
- Double-click to expand
- Arrow collapse/expand
- "Open All" to see everything
- JSON export for mass queries
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLabel, QComboBox, QMessageBox, QFileDialog,
    QHeaderView
)
from PyQt6.QtCore import Qt, QDate
from desktop_app.common_widgets import StandardDateEdit
import json
from decimal import Decimal

class DrillDownReportWidget(QWidget):
    """
    Collapsible drill-down report tree
    Shows: Year > Month > Week > Day > Charter > Charges
    Double-click expands, arrow keys navigate
    """
    
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Report controls
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Report Type:"))
        
        self.report_type = QComboBox()
        self.report_type.addItems([
            "Revenue Analysis (Drill-Down)",
            "Expense Analysis (Drill-Down)",
            "Customer Activity (Drill-Down)",
            "Vehicle Utilization (Drill-Down)",
            "Driver Performance (Drill-Down)"
        ])
        controls.addWidget(self.report_type)
        
        controls.addWidget(QLabel("Date Range:"))
        self.start_date = StandardDateEdit(prefer_month_text=True)
        self.start_date.setDate(QDate.currentDate().addMonths(-12))
        self.end_date = StandardDateEdit(prefer_month_text=True)
        self.end_date.setDate(QDate.currentDate())
        controls.addWidget(self.start_date)
        controls.addWidget(QLabel("to"))
        controls.addWidget(self.end_date)
        
        generate_btn = QPushButton("📊 Generate Report")
        generate_btn.clicked.connect(self.generate_report)
        controls.addWidget(generate_btn)
        
        controls.addStretch()
        
        expand_all_btn = QPushButton("📂 Expand All")
        expand_all_btn.clicked.connect(self.expand_all)
        controls.addWidget(expand_all_btn)
        
        collapse_all_btn = QPushButton("📁 Collapse All")
        collapse_all_btn.clicked.connect(self.collapse_all)
        controls.addWidget(collapse_all_btn)
        
        export_json_btn = QPushButton("💾 Export JSON")
        export_json_btn.clicked.connect(self.export_json)
        controls.addWidget(export_json_btn)
        
        export_excel_btn = QPushButton("📥 Export Excel")
        export_excel_btn.clicked.connect(self.export_excel)
        controls.addWidget(export_excel_btn)
        
        layout.addLayout(controls)
        
        # Tree widget for drill-down
        self.tree = QTreeWidget()
        self.tree.setColumnCount(6)
        self.tree.setHeaderLabels([
            "Description", "Revenue", "Expenses", "Profit", "Count", "Details"
        ])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.setAlternatingRowColors(True)
        self.tree.itemDoubleClicked.connect(self.on_item_double_clicked)
        
        layout.addWidget(self.tree)
        
        # Summary footer
        footer = QHBoxLayout()
        footer.addWidget(QLabel("<b>Totals:</b>"))
        self.total_revenue = QLabel("$0.00")
        self.total_expenses = QLabel("$0.00")
        self.total_profit = QLabel("$0.00")
        footer.addWidget(QLabel("Revenue:"))
        footer.addWidget(self.total_revenue)
        footer.addWidget(QLabel("Expenses:"))
        footer.addWidget(self.total_expenses)
        footer.addWidget(QLabel("Profit:"))
        footer.addWidget(self.total_profit)
        footer.addStretch()
        layout.addLayout(footer)
        
        self.setLayout(layout)
    
    def generate_report(self):
        """Generate drill-down report based on selection"""
        self.tree.clear()
        
        if "Revenue" in self.report_type.currentText():
            self.generate_revenue_drilldown()
        elif "Expense" in self.report_type.currentText():
            self.generate_expense_drilldown()
        elif "Customer" in self.report_type.currentText():
            self.generate_customer_drilldown()
        elif "Vehicle" in self.report_type.currentText():
            self.generate_vehicle_drilldown()
        elif "Driver" in self.report_type.currentText():
            self.generate_driver_drilldown()
    
    def generate_revenue_drilldown(self):
        """
        Revenue drill-down hierarchy:
        Year > Month > Week > Customer > Charter > Charges
        """
        # Rollback any failed transactions first
        try:
            self.db.rollback()
        except:
            try:
                self.db.rollback()
            except:
                pass
            pass
        
        cur = self.db.get_cursor()
        
        # Get all charters in date range
        cur.execute("""
            SELECT 
                EXTRACT(YEAR FROM charter_date) as year,
                EXTRACT(MONTH FROM charter_date) as month,
                EXTRACT(WEEK FROM charter_date) as week,
                customer_name,
                reserve_number,
                charter_date,
                SUM(charge_amount) as revenue
            FROM charters c
            LEFT JOIN charter_charges cc ON c.charter_id = cc.charter_id
            WHERE charter_date BETWEEN %s AND %s
            GROUP BY year, month, week, customer_name, reserve_number, charter_date
            ORDER BY year DESC, month DESC, week DESC
        """, (
            self.start_date.date().toPyDate(),
            self.end_date.date().toPyDate()
        ))
        
        # Build hierarchical tree
        year_items = {}
        month_items = {}
        week_items = {}
        
        total_revenue = 0.0
        
        for row in cur.fetchall():
            year, month, week, customer, reserve, date, revenue = row
            revenue = float(revenue or 0)
            total_revenue += revenue
            
            # Year level
            year_key = int(year)
            if year_key not in year_items:
                year_item = QTreeWidgetItem(self.tree)
                year_item.setText(0, f"📅 {year_key}")
                year_item.setData(0, Qt.ItemDataRole.UserRole, {"level": "year", "year": year_key})
                year_items[year_key] = year_item
            
            # Month level
            month_key = (year_key, int(month))
            if month_key not in month_items:
                month_names = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                month_item = QTreeWidgetItem(year_items[year_key])
                month_item.setText(0, f"📆 {month_names[int(month)]} {year_key}")
                month_item.setData(0, Qt.ItemDataRole.UserRole, {"level": "month", "year": year_key, "month": int(month)})
                month_items[month_key] = month_item
            
            # Week level
            week_key = (year_key, int(month), int(week))
            if week_key not in week_items:
                week_item = QTreeWidgetItem(month_items[month_key])
                week_item.setText(0, f"📊 Week {int(week)}")
                week_item.setData(0, Qt.ItemDataRole.UserRole, {"level": "week", "year": year_key, "month": int(month), "week": int(week)})
                week_items[week_key] = week_item
            
            # Charter level
            charter_item = QTreeWidgetItem(week_items[week_key])
            charter_item.setText(0, f"🎫 {reserve} - {customer}")
            charter_item.setText(1, f"${revenue:.2f}")
            charter_item.setText(4, "1 charter")
            charter_item.setData(0, Qt.ItemDataRole.UserRole, {
                "level": "charter",
                "reserve_number": reserve,
                "customer": customer,
                "date": str(date)
            })
        
        # Update totals
        self.total_revenue.setText(f"${total_revenue:,.2f}")
        
        # Collapse all by default (user can expand specific years)
        self.tree.collapseAll()
    
    def generate_expense_drilldown(self):
        """Expense analysis drill-down"""
        # Similar structure to revenue
        QMessageBox.information(self, "Info", "Expense drill-down - Coming soon")
    
    def generate_customer_drilldown(self):
        """Customer activity drill-down"""
        QMessageBox.information(self, "Info", "Customer drill-down - Coming soon")
    
    def generate_vehicle_drilldown(self):
        """Vehicle utilization drill-down"""
        QMessageBox.information(self, "Info", "Vehicle drill-down - Coming soon")
    
    def generate_driver_drilldown(self):
        """Driver performance drill-down"""
        QMessageBox.information(self, "Info", "Driver drill-down - Coming soon")
    
    def on_item_double_clicked(self, item, column):
        """Handle double-click to drill deeper"""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data and data.get("level") == "charter":
            # Show charter details in popup
            reserve = data["reserve_number"]
            QMessageBox.information(self, "Charter Details", 
                f"Charter: {reserve}\nCustomer: {data['customer']}\nDate: {data['date']}")
    
    def expand_all(self):
        """Expand all tree items"""
        self.tree.expandAll()
    
    def collapse_all(self):
        """Collapse all tree items"""
        self.tree.collapseAll()
    
    def export_json(self):
        """Export report data as JSON for mass queries"""
        data = self.tree_to_dict(self.tree.invisibleRootItem())
        
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export JSON", "", "JSON Files (*.json)"
        )
        
        if filename:
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            QMessageBox.information(self, "Success", f"Report exported to {filename}")
    
    def tree_to_dict(self, item):
        """Convert tree structure to nested dictionary"""
        result = []
        for i in range(item.childCount()):
            child = item.child(i)
            child_data = {
                "description": child.text(0),
                "revenue": child.text(1),
                "expenses": child.text(2),
                "profit": child.text(3),
                "count": child.text(4),
                "metadata": child.data(0, Qt.ItemDataRole.UserRole),
                "children": self.tree_to_dict(child)
            }
            result.append(child_data)
        return result
    
    def export_excel(self):
        """Export to Excel with drill-down preserved"""
        QMessageBox.information(self, "Info", "Excel export - Coming soon")
