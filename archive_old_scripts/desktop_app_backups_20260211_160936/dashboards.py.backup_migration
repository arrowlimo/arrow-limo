"""
Arrow Limousine - Dashboard Widgets (Phase 1)
Fleet Management, Driver Performance, Financial Reports, Payment Reconciliation
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QComboBox, QGroupBox, QMessageBox
)
from PyQt6.QtCore import QDate

from desktop_app.common_widgets import StandardDateEdit


class FleetManagementWidget(QWidget):
    """Fleet management dashboard showing vehicles, costs, and maintenance"""
    
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.init_ui()
        self.load_fleet_data()
    
    def init_ui(self):
        """Initialize user interface"""
        layout = QVBoxLayout()
        
        # Title and filters
        header = QHBoxLayout()
        header.addWidget(QLabel("<h2>🚐 Fleet Management Dashboard</h2>"))
        
        status_filter = QComboBox()
        status_filter.addItems(["All", "Active", "Inactive", "For Sale"])
        status_filter.currentTextChanged.connect(self.load_fleet_data)
        self.status_filter = status_filter
        header.addWidget(QLabel("Status:"))
        header.addWidget(status_filter)
        header.addStretch()
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.load_fleet_data)
        header.addWidget(refresh_btn)
        
        layout.addLayout(header)
        
        # Fleet table
        self.fleet_table = QTableWidget()
        self.fleet_table.setColumnCount(9)
        self.fleet_table.setHorizontalHeaderLabels([
            "Vehicle #", "Make/Model", "Year", "Status", "License Plate",
            "Fuel Cost YTD", "Maintenance YTD", "Insurance YTD", "Total Cost YTD"
        ])
        self.fleet_table.horizontalHeader().setStretchLastSection(True)
        self.fleet_table.setRowCount(0)
        layout.addWidget(self.fleet_table)
        
        # Fleet summary
        summary_layout = QHBoxLayout()
        self.total_vehicles_label = QLabel("Total Vehicles: 0")
        self.total_fuel_label = QLabel("Total Fuel: $0.00")
        self.total_maintenance_label = QLabel("Total Maintenance: $0.00")
        self.total_insurance_label = QLabel("Total Insurance: $0.00")
        self.fleet_total_label = QLabel("Fleet Total: $0.00")
        
        summary_layout.addWidget(self.total_vehicles_label)
        summary_layout.addWidget(self.total_fuel_label)
        summary_layout.addWidget(self.total_maintenance_label)
        summary_layout.addWidget(self.total_insurance_label)
        summary_layout.addWidget(self.fleet_total_label)
        summary_layout.addStretch()
        
        layout.addLayout(summary_layout)
        
        self.setLayout(layout)
    
    def load_fleet_data(self):
        """Load fleet vehicle data from database"""
        try:
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
            
            status = self.status_filter.currentText()
            if status == "All":
                cur.execute("""
                    SELECT 
                        v.vehicle_id, v.vehicle_number, v.make, v.model, v.year,
                        v.license_plate, 'Active' as status,
                        COALESCE(vf.total_fuel_cost, 0) as fuel_cost,
                        COALESCE(vm.total_maintenance_cost, 0) as maintenance_cost,
                        COALESCE(vi.total_insurance_cost, 0) as insurance_cost
                    FROM vehicles v
                    LEFT JOIN vehicle_fuel_expenses vf ON v.vehicle_id = vf.vehicle_id
                    LEFT JOIN vehicle_maintenance_expenses vm ON v.vehicle_id = vm.vehicle_id
                    LEFT JOIN vehicle_insurance_expenses vi ON v.vehicle_id = vi.vehicle_id
                    ORDER BY v.vehicle_number
                """)
            else:
                cur.execute("""
                    SELECT 
                        v.vehicle_id, v.vehicle_number, v.make, v.model, v.year,
                        v.license_plate, 'Active' as status,
                        COALESCE(vf.total_fuel_cost, 0) as fuel_cost,
                        COALESCE(vm.total_maintenance_cost, 0) as maintenance_cost,
                        COALESCE(vi.total_insurance_cost, 0) as insurance_cost
                    FROM vehicles v
                    LEFT JOIN vehicle_fuel_expenses vf ON v.vehicle_id = vf.vehicle_id
                    LEFT JOIN vehicle_maintenance_expenses vm ON v.vehicle_id = vm.vehicle_id
                    LEFT JOIN vehicle_insurance_expenses vi ON v.vehicle_id = vi.vehicle_id
                    WHERE 1=1
                    ORDER BY v.vehicle_number
                """, (status.lower(),))
            
            rows = cur.fetchall()
            self.fleet_table.setRowCount(len(rows))
            
            total_fuel = 0
            total_maint = 0
            total_insurance = 0
            
            for i, row in enumerate(rows):
                vehicle_id, vehicle_num, make, model, year, plate, status, fuel, maint, insur = row
                
                fuel = float(fuel or 0)
                maint = float(maint or 0)
                insur = float(insur or 0)
                total = fuel + maint + insur
                
                total_fuel += fuel
                total_maint += maint
                total_insurance += insur
                
                self.fleet_table.setItem(i, 0, QTableWidgetItem(str(vehicle_num or "")))
                self.fleet_table.setItem(i, 1, QTableWidgetItem(f"{make or ''} {model or ''}".strip()))
                self.fleet_table.setItem(i, 2, QTableWidgetItem(str(year or "")))
                self.fleet_table.setItem(i, 3, QTableWidgetItem(str(status or "")))
                self.fleet_table.setItem(i, 4, QTableWidgetItem(str(plate or "")))
                
                self.fleet_table.setItem(i, 5, QTableWidgetItem(f"${fuel:,.2f}"))
                self.fleet_table.setItem(i, 6, QTableWidgetItem(f"${maint:,.2f}"))
                self.fleet_table.setItem(i, 7, QTableWidgetItem(f"${insur:,.2f}"))
                self.fleet_table.setItem(i, 8, QTableWidgetItem(f"${total:,.2f}"))
            
            # Update summary
            self.total_vehicles_label.setText(f"Total Vehicles: {len(rows)}")
            self.total_fuel_label.setText(f"Total Fuel: ${total_fuel:,.2f}")
            self.total_maintenance_label.setText(f"Total Maintenance: ${total_maint:,.2f}")
            self.total_insurance_label.setText(f"Total Insurance: ${total_insurance:,.2f}")
            self.fleet_total_label.setText(f"Fleet Total: ${total_fuel + total_maint + total_insurance:,.2f}")
            
        except Exception as e:
            QMessageBox.warning(self, "Load Error", f"Failed to load fleet data:\n{e}")


class DriverPerformanceWidget(QWidget):
    """Driver performance dashboard showing earnings and hours"""
    
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.init_ui()
        self.load_driver_data()
    
    def init_ui(self):
        """Initialize user interface"""
        layout = QVBoxLayout()
        
        header = QHBoxLayout()
        header.addWidget(QLabel("<h2>👤 Driver Performance & Earnings</h2>"))
        
        year_filter = QComboBox()
        year_filter.addItems([str(y) for y in range(2025, 2009, -1)])
        year_filter.currentTextChanged.connect(self.load_driver_data)
        self.year_filter = year_filter
        header.addWidget(QLabel("Year:"))
        header.addWidget(year_filter)
        header.addStretch()
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.load_driver_data)
        header.addWidget(refresh_btn)
        
        layout.addLayout(header)
        
        # Driver table
        self.driver_table = QTableWidget()
        self.driver_table.setColumnCount(8)
        self.driver_table.setHorizontalHeaderLabels([
            "Driver", "Charters", "Gross Pay", "Deductions", "Net Pay",
            "Expenses", "Avg Pay/Charter", "Status"
        ])
        self.driver_table.horizontalHeader().setStretchLastSection(True)
        self.driver_table.setRowCount(0)
        layout.addWidget(self.driver_table)
        
        # Summary
        summary_layout = QHBoxLayout()
        self.total_drivers_label = QLabel("Total Drivers: 0")
        self.total_gross_label = QLabel("Total Gross: $0.00")
        self.total_deductions_label = QLabel("Total Deductions: $0.00")
        self.total_net_label = QLabel("Total Net: $0.00")
        
        summary_layout.addWidget(self.total_drivers_label)
        summary_layout.addWidget(self.total_gross_label)
        summary_layout.addWidget(self.total_deductions_label)
        summary_layout.addWidget(self.total_net_label)
        summary_layout.addStretch()
        
        layout.addLayout(summary_layout)
        
        self.setLayout(layout)
    
    def load_driver_data(self):
        """Load driver performance data"""
        try:
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
            year = self.year_filter.currentText()
            
            cur.execute("""
                SELECT 
                    e.full_name,
                    COUNT(DISTINCT dp.charter_id) as charter_count,
                    COALESCE(SUM(dp.gross_pay), 0) as total_gross,
                    COALESCE(SUM(dp.total_deductions), 0) as total_deductions,
                    COALESCE(SUM(dp.net_pay), 0) as total_net,
                    COALESCE(SUM(dp.gross_pay), 0) as total_expense,
                    e.status
                FROM employees e
                LEFT JOIN driver_payroll dp ON e.employee_id = dp.employee_id
                    AND EXTRACT(YEAR FROM dp.pay_date) = %s
                WHERE e.is_chauffeur = true AND e.employment_status = 'active'
                GROUP BY e.employee_id, e.full_name, e.status
                ORDER BY total_gross DESC
            """, (int(year),))
            
            rows = cur.fetchall()
            self.driver_table.setRowCount(len(rows))
            
            total_gross = 0
            total_deductions = 0
            total_net = 0
            
            for i, row in enumerate(rows):
                name, charters, gross, deductions, net, expense, status = row
                
                gross = float(gross or 0)
                deductions = float(deductions or 0)
                net = float(net or 0)
                expense = float(expense or 0)
                charters = int(charters or 0)
                
                total_gross += gross
                total_deductions += deductions
                total_net += net
                
                avg_pay = gross / charters if charters > 0 else 0
                
                self.driver_table.setItem(i, 0, QTableWidgetItem(str(name or "")))
                self.driver_table.setItem(i, 1, QTableWidgetItem(str(charters)))
                self.driver_table.setItem(i, 2, QTableWidgetItem(f"${gross:,.2f}"))
                self.driver_table.setItem(i, 3, QTableWidgetItem(f"${deductions:,.2f}"))
                self.driver_table.setItem(i, 4, QTableWidgetItem(f"${net:,.2f}"))
                self.driver_table.setItem(i, 5, QTableWidgetItem(f"${expense:,.2f}"))
                self.driver_table.setItem(i, 6, QTableWidgetItem(f"${avg_pay:,.2f}"))
                self.driver_table.setItem(i, 7, QTableWidgetItem(str(status or "active")))
            
            self.total_drivers_label.setText(f"Total Drivers: {len(rows)}")
            self.total_gross_label.setText(f"Total Gross: ${total_gross:,.2f}")
            self.total_deductions_label.setText(f"Total Deductions: ${total_deductions:,.2f}")
            self.total_net_label.setText(f"Total Net: ${total_net:,.2f}")
            
        except Exception as e:
            QMessageBox.warning(self, "Load Error", f"Failed to load driver data:\n{e}")


class FinancialDashboardWidget(QWidget):
    """Financial dashboard showing P&L, cash flow, and AR aging"""
    
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.init_ui()
        self.load_financial_data()
    
    def init_ui(self):
        """Initialize user interface"""
        layout = QVBoxLayout()
        
        header = QHBoxLayout()
        header.addWidget(QLabel("<h2>📈 Financial Reports</h2>"))
        
        # Date range filters
        start_date = StandardDateEdit(prefer_month_text=True)
        start_date.setDate(QDate.currentDate().addMonths(-12))
        start_date.dateChanged.connect(self.load_financial_data)
        self.start_date = start_date
        
        end_date = StandardDateEdit(prefer_month_text=True)
        end_date.setDate(QDate.currentDate())
        end_date.dateChanged.connect(self.load_financial_data)
        self.end_date = end_date
        
        header.addWidget(QLabel("From:"))
        header.addWidget(start_date)
        header.addWidget(QLabel("To:"))
        header.addWidget(end_date)
        header.addStretch()
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.load_financial_data)
        header.addWidget(refresh_btn)
        
        layout.addLayout(header)
        
        # P&L Summary
        pl_group = QGroupBox("Profit & Loss Summary")
        pl_layout = QVBoxLayout()
        
        pl_table = QTableWidget()
        pl_table.setColumnCount(2)
        pl_table.setHorizontalHeaderLabels(["Category", "Amount"])
        header = pl_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setColumnWidth(1, 110)
        pl_table.setMaximumHeight(250)
        self.pl_table = pl_table
        
        pl_layout.addWidget(pl_table)
        pl_group.setLayout(pl_layout)
        layout.addWidget(pl_group)
        
        # Cash Flow Summary
        cf_group = QGroupBox("Cash Flow Summary")
        cf_layout = QHBoxLayout()
        
        self.cash_in_label = QLabel("Cash In: $0.00")
        self.cash_out_label = QLabel("Cash Out: $0.00")
        self.net_cf_label = QLabel("Net Flow: $0.00")
        
        cf_layout.addWidget(self.cash_in_label)
        cf_layout.addWidget(self.cash_out_label)
        cf_layout.addWidget(self.net_cf_label)
        cf_layout.addStretch()
        
        cf_group.setLayout(cf_layout)
        layout.addWidget(cf_group)
        
        # AR Aging
        ar_group = QGroupBox("Accounts Receivable Aging")
        ar_layout = QVBoxLayout()
        
        ar_table = QTableWidget()
        ar_table.setColumnCount(3)
        ar_table.setHorizontalHeaderLabels(["Aging Bucket", "Count", "Total Amount"])
        header = ar_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.ar_table = ar_table
        
        ar_layout.addWidget(ar_table)
        ar_group.setLayout(ar_layout)
        layout.addWidget(ar_group)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def load_financial_data(self):
        """Load financial data from API"""
        try:
            import requests
            
            start = self.start_date.date().toString("MM/dd/yyyy")
            end = self.end_date.date().toString("MM/dd/yyyy")
            
            # Profit & Loss
            try:
                response = requests.get(
                    f"http://127.0.0.1:8000/api/accounting/reports/profit-loss",
                    params={"start_date": start, "end_date": end},
                    timeout=5
                )
                if response.status_code == 200:
                    pl_data = response.json()
                    self.display_pl_report(pl_data)
            except:
                pass
            
            # Cash Flow
            try:
                response = requests.get(
                    f"http://127.0.0.1:8000/api/accounting/reports/cash-flow",
                    params={"start_date": start, "end_date": end},
                    timeout=5
                )
                if response.status_code == 200:
                    cf_data = response.json()
                    self.display_cf_report(cf_data)
            except:
                pass
            
            # AR Aging
            try:
                response = requests.get("http://127.0.0.1:8000/api/accounting/reports/ar-aging", timeout=5)
                if response.status_code == 200:
                    ar_data = response.json()
                    self.display_ar_report(ar_data)
            except:
                pass
        
        except Exception as e:
            pass
    
    def display_pl_report(self, data):
        """Display P&L report"""
        try:
            self.pl_table.setRowCount(0)
            
            rows = [
                ("Charter Revenue", data.get("revenue", {}).get("total_revenue", 0)),
                ("GST Collected", data.get("revenue", {}).get("gst_collected", 0)),
            ]
            
            expenses = data.get("expenses", [])
            for exp in expenses:
                rows.append((exp.get("category", "Other"), exp.get("amount", 0)))
            
            rows.append(("Total Expenses", data.get("total_expenses", 0)))
            rows.append(("Net Profit", data.get("net_profit", 0)))
            
            self.pl_table.setRowCount(len(rows))
            for i, (category, amount) in enumerate(rows):
                self.pl_table.setItem(i, 0, QTableWidgetItem(str(category)))
                self.pl_table.setItem(i, 1, QTableWidgetItem(f"${float(amount):,.2f}"))
        
        except Exception as e:
            pass
    
    def display_cf_report(self, data):
        """Display cash flow report"""
        cash_in = float(data.get("cash_in", 0))
        cash_out = float(data.get("cash_out", 0))
        net = cash_in - cash_out
        
        self.cash_in_label.setText(f"Cash In: ${cash_in:,.2f}")
        self.cash_out_label.setText(f"Cash Out: ${cash_out:,.2f}")
        self.net_cf_label.setText(f"Net Flow: ${net:,.2f}")
    
    def display_ar_report(self, data):
        """Display AR aging report"""
        try:
            self.ar_table.setRowCount(0)
            
            aging = data.get("aging", {})
            buckets = [
                ("Current", aging.get("current", [])),
                ("1-30 Days", aging.get("1_30_days", [])),
                ("31-60 Days", aging.get("31_60_days", [])),
                ("61-90 Days", aging.get("61_90_days", [])),
                ("90+ Days", aging.get("over_90_days", []))
            ]
            
            self.ar_table.setRowCount(len(buckets))
            for i, (bucket, items) in enumerate(buckets):
                count = len(items)
                total = sum(float(item.get("total", 0)) for item in items)
                
                self.ar_table.setItem(i, 0, QTableWidgetItem(str(bucket)))
                self.ar_table.setItem(i, 1, QTableWidgetItem(str(count)))
                self.ar_table.setItem(i, 2, QTableWidgetItem(f"${total:,.2f}"))
        
        except Exception as e:
            pass


class PaymentReconciliationWidget(QWidget):
    """Payment reconciliation dashboard"""
    
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.init_ui()
        self.load_payment_data()
    
    def init_ui(self):
        """Initialize user interface"""
        layout = QVBoxLayout()
        
        header = QHBoxLayout()
        header.addWidget(QLabel("<h2>💳 Payment Reconciliation</h2>"))
        
        method_filter = QComboBox()
        method_filter.addItems(["All Methods", "Cash", "Check", "Credit Card", "Debit Card", "E-Transfer", "Bank Transfer"])
        method_filter.currentTextChanged.connect(self.load_payment_data)
        self.method_filter = method_filter
        header.addWidget(QLabel("Payment Method:"))
        header.addWidget(method_filter)
        header.addStretch()
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.load_payment_data)
        header.addWidget(refresh_btn)
        
        layout.addLayout(header)
        
        # Outstanding payments table
        self.payment_table = QTableWidget()
        self.payment_table.setColumnCount(7)
        self.payment_table.setHorizontalHeaderLabels([
            "Reserve #", "Customer", "Charter Date", "Amount Due", "Payment Date",
            "Payment Method", "Status"
        ])
        self.payment_table.horizontalHeader().setStretchLastSection(True)
        self.payment_table.setRowCount(0)
        layout.addWidget(self.payment_table)
        
        # Summary
        summary_layout = QHBoxLayout()
        self.outstanding_label = QLabel("Outstanding: $0.00")
        self.paid_label = QLabel("Paid: $0.00")
        self.total_label = QLabel("Total: $0.00")
        self.nsf_label = QLabel("NSF Charges: $0.00")
        
        summary_layout.addWidget(self.outstanding_label)
        summary_layout.addWidget(self.paid_label)
        summary_layout.addWidget(self.total_label)
        summary_layout.addWidget(self.nsf_label)
        summary_layout.addStretch()
        
        layout.addLayout(summary_layout)
        
        self.setLayout(layout)
    
    def load_payment_data(self):
        """Load payment and outstanding data"""
        try:
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
            
            # Get outstanding and paid amounts
            cur.execute("""
                SELECT 
                    c.reserve_number,
                    cl.company_name,
                    c.charter_date,
                    c.balance as outstanding,
                    COALESCE(SUM(p.amount), 0) as paid_amount,
                    MAX(p.payment_date) as last_payment_date,
                    MAX(p.payment_method) as payment_method,
                    CASE WHEN c.balance > 0 THEN 'Outstanding' ELSE 'Paid' END as status
                FROM charters c
                LEFT JOIN clients cl ON c.client_id = cl.client_id
                LEFT JOIN payments p ON p.reserve_number = c.reserve_number
                WHERE c.balance > 0 OR COALESCE(SUM(p.amount), 0) > 0
                GROUP BY c.charter_id, c.reserve_number, cl.company_name, c.charter_date, c.balance
                ORDER BY c.balance DESC
                LIMIT 100
            """)
            
            rows = cur.fetchall()
            self.payment_table.setRowCount(len(rows))
            
            outstanding_total = 0
            paid_total = 0
            
            for i, row in enumerate(rows):
                reserve, customer, charter_date, outstanding, paid, last_payment, method, status = row
                
                outstanding = float(outstanding or 0)
                paid = float(paid or 0)
                
                if status == "Outstanding":
                    outstanding_total += outstanding
                if paid > 0:
                    paid_total += paid
                
                self.payment_table.setItem(i, 0, QTableWidgetItem(str(reserve or "")))
                self.payment_table.setItem(i, 1, QTableWidgetItem(str(customer or "")))
                self.payment_table.setItem(i, 2, QTableWidgetItem(str(charter_date or "")))
                self.payment_table.setItem(i, 3, QTableWidgetItem(f"${outstanding:,.2f}"))
                self.payment_table.setItem(i, 4, QTableWidgetItem(str(last_payment or "Unpaid")))
                self.payment_table.setItem(i, 5, QTableWidgetItem(str(method or "Unknown")))
                self.payment_table.setItem(i, 6, QTableWidgetItem(str(status)))
            
            self.outstanding_label.setText(f"Outstanding: ${outstanding_total:,.2f}")
            self.paid_label.setText(f"Paid: ${paid_total:,.2f}")
            self.total_label.setText(f"Total: ${outstanding_total + paid_total:,.2f}")
            self.nsf_label.setText("NSF Charges: $0.00")
            
        except Exception as e:
            QMessageBox.warning(self, "Load Error", f"Failed to load payment data:\n{e}")
