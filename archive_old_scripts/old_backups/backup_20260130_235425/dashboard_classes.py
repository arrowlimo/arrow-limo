# Dashboard Widget Classes for Arrow Limousine Management System
# These are imported into main.py after CustomersWidget and before MainWindow

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QMessageBox, QPushButton
)
from PyQt6.QtCore import Qt

from reporting_base import BaseReportWidget


class FleetManagementWidget(QWidget):
    """Fleet management dashboard - vehicle costs and maintenance with action buttons"""
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.vehicle_ids = {}  # Map row to vehicle_id
        
        layout = QVBoxLayout()
        
        # Breadcrumb navigation
        breadcrumb_layout = QHBoxLayout()
        back_btn = QPushButton("⬅ Back to Navigator")
        back_btn.setMaximumWidth(150)
        back_btn.clicked.connect(self.go_back)
        breadcrumb_layout.addWidget(back_btn)
        breadcrumb_layout.addWidget(QLabel("📍 Core Operations › Fleet Management › Fleet Cost Dashboard"))
        breadcrumb_layout.addStretch()
        layout.addLayout(breadcrumb_layout)
        
        layout.addWidget(QLabel("<h3>🚐 Fleet Management</h3><p>Vehicle costs: Fuel, Maintenance, Insurance</p>"))
        
        # Action buttons at TOP
        button_layout = QHBoxLayout()
        
        edit_btn = QPushButton("✏️ Edit Selected Vehicle")
        edit_btn.clicked.connect(self.edit_vehicle)
        button_layout.addWidget(edit_btn)
        
        retire_btn = QPushButton("🚫 Retire Selected")
        retire_btn.clicked.connect(self.retire_vehicle)
        button_layout.addWidget(retire_btn)
        
        inactive_btn = QPushButton("⏸️ Mark Inactive")
        inactive_btn.clicked.connect(self.mark_inactive)
        button_layout.addWidget(inactive_btn)
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.load_data)
        button_layout.addWidget(refresh_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Vehicle", "Make/Model", "Year", "Fuel $", "Maint $", "Total $"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.table)
        
        self.setLayout(layout)
        self.load_data()
    
    def go_back(self):
        """Return to Navigator tab"""
        # Get the main window and switch to Navigator tab
        parent = self.parent()
        while parent and not hasattr(parent, 'tabs'):
            parent = parent.parent()
        if parent and hasattr(parent, 'tabs'):
            parent.tabs.setCurrentIndex(0)  # Navigator is tab 0
    
    def load_data(self):
        try:
            # Rollback any existing failed transactions first
            try:
                self.db.rollback()
            except:
                try:
                    self.db.rollback()
                except:
                    pass
                pass
            
            # Get all vehicles (show all by default)
            cur = self.db.get_cursor()
            cur.execute("""SELECT v.vehicle_id, v.vehicle_number, v.make, v.model, v.year,
                CASE 
                    WHEN v.sale_date IS NOT NULL THEN '💰 Sold'
                    WHEN v.decommission_date IS NOT NULL THEN '⚠️ Decommissioned'
                    WHEN v.operational_status = 'maintenance' THEN '🔧 In Maintenance'
                    WHEN v.is_active = false THEN '🚫 Inactive'
                    ELSE '✅ Active'
                END as status,
                v.last_service_date,
                v.next_service_due,
                COALESCE(SUM(CASE WHEN r.description ILIKE '%fuel%' THEN r.gross_amount ELSE 0 END),0) fuel_cost,
                COALESCE(SUM(CASE WHEN r.description ILIKE '%maint%' OR r.description ILIKE '%repair%' THEN r.gross_amount ELSE 0 END),0) maint_cost
                FROM vehicles v
                LEFT JOIN receipts r ON v.vehicle_id = r.vehicle_id
                GROUP BY v.vehicle_id, v.vehicle_number, v.make, v.model, v.year, v.is_active, v.operational_status, v.decommission_date, v.sale_date, v.last_service_date, v.next_service_due
                ORDER BY v.vehicle_number""")
            rows = cur.fetchall()
            cur.close()
            
            print(f"✅ Fleet Management loaded {len(rows)} vehicles")
            self.table.setRowCount(len(rows))
            self.vehicle_ids = {}
            for i, (vid, vnum, make, model, year, status, last_service, next_service, fuel, maint) in enumerate(rows):
                self.vehicle_ids[i] = vid  # Store vehicle_id for each row
                self.table.setItem(i, 0, QTableWidgetItem(str(vnum or "")))
                self.table.setItem(i, 1, QTableWidgetItem(f"{make or ''} {model or ''}".strip()))
                self.table.setItem(i, 2, QTableWidgetItem(str(year or "")))
                self.table.setItem(i, 3, QTableWidgetItem(status or "✅ Active"))
                self.table.setItem(i, 4, QTableWidgetItem(str(last_service or "")))
                self.table.setItem(i, 5, QTableWidgetItem(str(next_service or "")))
                self.table.setItem(i, 6, QTableWidgetItem(f"${float(fuel or 0):,.2f}"))
                self.table.setItem(i, 7, QTableWidgetItem(f"${float(maint or 0):,.2f}"))
                self.table.setItem(i, 8, QTableWidgetItem(f"${float(fuel or 0) + float(maint or 0):,.2f}"))
        except Exception as e:
            print(f"❌ Fleet Management load error: {e}")
            import traceback
            traceback.print_exc()
            try:
                self.db.rollback()
            except:
                try:
                    self.db.rollback()
                except:
                    pass
                pass
    
    def edit_vehicle(self):
        """Edit selected vehicle"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Warning", "Please select a vehicle first")
            return
        
        vehicle_id = self.vehicle_ids.get(current_row)
        if not vehicle_id:
            QMessageBox.warning(self, "Error", "Could not find vehicle ID")
            return
        
        # Import here to avoid circular imports
        from vehicle_drill_down import VehicleDetailDialog
        dialog = VehicleDetailDialog(self.db, vehicle_id, self)
        dialog.saved.connect(lambda: self.load_data())
        dialog.exec()
    
    def retire_vehicle(self):
        """Retire selected vehicle"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Warning", "Please select a vehicle first")
            return
        
        vehicle_id = self.vehicle_ids.get(current_row)
        vehicle_num = self.table.item(current_row, 0).text()
        
        reply = QMessageBox.question(
            self, "Confirm Retire",
            f"Retire vehicle {vehicle_num}? This will set its status to retired.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                cur = self.db.get_cursor()
                cur.execute("""
                    UPDATE vehicles 
                    SET operational_status = 'retired', 
                        is_active = FALSE,
                        lifecycle_status = 'decommissioned',
                        decommission_date = CURRENT_DATE
                    WHERE vehicle_id = %s
                """, (vehicle_id,))
                self.db.commit()
                QMessageBox.information(self, "Success", f"Vehicle {vehicle_num} retired ✅")
                self.load_data()
            except Exception as e:
                try:
                    self.db.rollback()
                except:
                    pass
                QMessageBox.critical(self, "Error", f"Failed to retire vehicle: {e}")
    
    def mark_inactive(self):
        """Mark selected vehicle as inactive"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Warning", "Please select a vehicle first")
            return
        
        vehicle_id = self.vehicle_ids.get(current_row)
        vehicle_num = self.table.item(current_row, 0).text()
        
        reply = QMessageBox.question(
            self, "Confirm Mark Inactive",
            f"Mark vehicle {vehicle_num} as inactive? It can be reactivated later.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                cur = self.db.get_cursor()
                cur.execute("""
                    UPDATE vehicles 
                    SET operational_status = 'out_of_service', 
                        is_active = FALSE
                    WHERE vehicle_id = %s
                """, (vehicle_id,))
                self.db.commit()
                QMessageBox.information(self, "Success", f"Vehicle {vehicle_num} marked inactive ✅")
                self.load_data()
            except Exception as e:
                try:
                    self.db.rollback()
                except:
                    pass
                QMessageBox.critical(self, "Error", f"Failed to mark vehicle inactive: {e}")


class DriverPerformanceWidget(QWidget):
    """Driver performance - earnings and hours"""
    def __init__(self, db):
        super().__init__()
        self.db = db
        layout = QVBoxLayout()
        layout.addWidget(QLabel("<h3>👤 Driver Performance</h3><p>YTD earnings and charter count</p>"))
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Driver", "Charters", "Gross Pay", "Deductions", "Net Pay"])
        layout.addWidget(self.table)
        self.setLayout(layout)
        self.load_data()
    
    def load_data(self):
        try:
            rows = self.db.safe_query("""SELECT e.full_name, 
                COUNT(DISTINCT dp.charter_id) as charters,
                SUM(dp.gross_pay) gross, 
                SUM(dp.total_deductions) deductions, 
                SUM(dp.net_pay) net
                FROM employees e
                LEFT JOIN driver_payroll dp ON e.employee_id = dp.employee_id
                WHERE e.is_chauffeur = true AND e.employment_status = 'active'
                GROUP BY e.employee_id, e.full_name
                ORDER BY gross DESC""")
            print(f"✅ Driver Performance loaded {len(rows)} drivers")
            self.table.setRowCount(len(rows))
            for i, (name, charters, gross, ded, net) in enumerate(rows):
                self.table.setItem(i, 0, QTableWidgetItem(str(name or "")))
                self.table.setItem(i, 1, QTableWidgetItem(str(int(charters or 0))))
                self.table.setItem(i, 2, QTableWidgetItem(f"${float(gross or 0):,.2f}"))
                self.table.setItem(i, 3, QTableWidgetItem(f"${float(ded or 0):,.2f}"))
                self.table.setItem(i, 4, QTableWidgetItem(f"${float(net or 0):,.2f}"))
        except Exception as e:
            print(f"❌ Driver Performance load error: {e}")
            import traceback
            traceback.print_exc()
            try:
                self.db.rollback()
            except:
                try:
                    self.db.rollback()
                except:
                    pass
                pass


class FinancialDashboardWidget(QWidget):
    """Financial dashboard - P&L, cash flow, AR with detailed reports"""
    def __init__(self, db):
        super().__init__()
        self.db = db
        layout = QVBoxLayout()
        layout.addWidget(QLabel("<h3>📈 Financial Reports</h3>"))
        
        # Summaries
        summary = QHBoxLayout()
        self.revenue_label = QLabel("Revenue: $0")
        self.expense_label = QLabel("Expenses: $0")
        self.profit_label = QLabel("Profit: $0")
        summary.addWidget(self.revenue_label)
        summary.addWidget(self.expense_label)
        summary.addWidget(self.profit_label)
        layout.addLayout(summary)
        
        # Create sub-tabs for financial reports
        from PyQt6.QtWidgets import QTabWidget
        from accounting_reports import (
            TrialBalanceWidget, JournalExplorerWidget, BankReconciliationWidget,
            PLSummaryWidget, PLCategoryWidget
        )
        
        self.report_tabs = QTabWidget()
        
        try:
            # Trial Balance
            self.trial_balance = TrialBalanceWidget(self.db)
            self.report_tabs.addTab(self.trial_balance, "📊 Trial Balance")
            
            # P&L Summary
            self.pl_summary = PLSummaryWidget(self.db)
            self.report_tabs.addTab(self.pl_summary, "💰 Profit & Loss")
            
            # P&L by Category
            self.pl_category = PLCategoryWidget(self.db)
            self.report_tabs.addTab(self.pl_category, "📈 P&L by Category")
            
            # Bank Reconciliation
            self.bank_recon = BankReconciliationWidget(self.db)
            self.report_tabs.addTab(self.bank_recon, "🏦 Bank Reconciliation")
            
            # Journal Explorer
            self.journal = JournalExplorerWidget(self.db)
            self.report_tabs.addTab(self.journal, "📖 Journal Entries")
            
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            print(f"⚠️ Some financial reports unavailable: {e}")
        
        layout.addWidget(self.report_tabs)
        self.setLayout(layout)
        self.load_data()
    
    def load_data(self):
        try:
            revenue = self.db.safe_scalar("SELECT SUM(total_amount_due) FROM charters")
            expense = self.db.safe_scalar("SELECT SUM(gross_amount) FROM receipts WHERE category != 'personal' AND gross_amount IS NOT NULL")
            print(f"✅ Financial Dashboard: Revenue ${revenue:,.2f}, Expenses ${expense:,.2f}")
            self.revenue_label.setText(f"Revenue: ${revenue:,.2f}")
            self.expense_label.setText(f"Expenses: ${expense:,.2f}")
            self.profit_label.setText(f"Profit: ${revenue - expense:,.2f}")
        except Exception as e:
            print(f"❌ Financial Dashboard load error: {e}")
            import traceback
            traceback.print_exc()
            try:
                self.db.rollback()
            except:
                try:
                    self.db.rollback()
                except:
                    pass
                pass


class PaymentReconciliationWidget(BaseReportWidget):
    """Payment reconciliation with reusable report toolbar."""

    def __init__(self, db):
        columns = [
            {"header": "Reserve #", "key": "reserve_number"},
            {"header": "Customer", "key": "customer"},
            {"header": "Charter Date", "key": "charter_date"},
            {"header": "Balance", "key": "balance", "format": lambda v: f"${float(v or 0):,.2f}"},
            {"header": "Status", "key": "status"},
        ]
        self.db = db
        super().__init__(db, "Payment Reconciliation", columns)

    def fetch_rows(self):
        try:
            try:
                self.db.rollback()
            except Exception:
                pass
            cur = self.db.get_cursor()
            cur.execute(
                """
                SELECT c.reserve_number, cl.company_name, c.charter_date, c.balance,
                       CASE WHEN c.balance > 0 THEN 'Outstanding' ELSE 'Paid' END AS status
                FROM charters c
                LEFT JOIN clients cl ON c.client_id = cl.client_id
                WHERE c.balance > 0 OR c.total_amount_due > 0
                ORDER BY c.balance DESC
                LIMIT 50
                """
            )
            rows = cur.fetchall()
            cur.close()
            print(f"✅ Payment Reconciliation loaded {len(rows)} outstanding charters")
            return [
                {
                    "reserve_number": r[0],
                    "customer": r[1],
                    "charter_date": r[2],
                    "balance": r[3],
                    "status": r[4],
                }
                for r in rows
            ]
        except Exception as e:
            print(f"❌ Payment Reconciliation load error: {e}")
            import traceback
            traceback.print_exc()
            try:
                self.db.rollback()
            except Exception:
                pass
            raise e
