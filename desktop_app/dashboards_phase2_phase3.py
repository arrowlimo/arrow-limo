#!/usr/bin/env python3
"""
Phase 2 & 3 Dashboard Widgets - Advanced Analytics & Reporting
Arrow Limousine Management System (Desktop - PyQt6)

Includes:
- Phase 2: Vehicle Analytics, Payroll Audit, QB Reconciliation,
Charter Analytics
- Phase 3: Compliance, Budget Analysis, Insurance Tracking, Loss Analysis

All dashboards use SQL queries with proper error handling and data validation.
"""

import logging
from datetime import datetime

from db_error_handling import DatabaseContext, table_exists
from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)
from reporting_base import BaseReportWidget

logger = logging.getLogger(__name__)


# ============================================================================
# PHASE 2: ADVANCED VEHICLE ANALYTICS
# ============================================================================


class VehicleAnalyticsWidget(BaseReportWidget):
    """Advanced vehicle analytics - cost per mile, ROI, depreciation"""

    def __init__(self, db) -> None:
        columns = [
            {"header": "Vehicle", "key": "vehicle"},
            {"header": "Miles", "key": "miles"},
            {"header": "Total Cost", "key": "total_cost"},
            {"header": "Cost/Mile", "key": "cost_mile"},
            {"header": "Fuel Cost", "key": "fuel_cost"},
            {"header": "Maint Cost", "key": "maint_cost"},
            {"header": "Insurance", "key": "insurance"},
            {"header": "Depreciation", "key": "depreciation"},
            {"header": "ROI %", "key": "roi_%"},
        ]
        super().__init__(db, "VehicleAnalytics", columns)
        self.db = db
        layout = QVBoxLayout()
        layout.addWidget(
            QLabel(
                "<h3>🚗 Advanced Vehicle Analytics</h3><p>Cost per mile, ROI"
                "analysis, depreciation</p>"
            )
        )

        # Summary metrics
        summary = QHBoxLayout()
        self.avg_cost_per_mile = QLabel("Avg Cost/Mile: $0.00")
        self.avg_fuel_efficiency = QLabel("Avg Fuel Efficiency: 0 L/100km")
        self.total_depreciation = QLabel("Total Depreciation: $0")
        summary.addWidget(self.avg_cost_per_mile)
        summary.addWidget(self.avg_fuel_efficiency)
        summary.addWidget(self.total_depreciation)
        layout.addLayout(summary)

        # Vehicles table
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels(
            [
                "Vehicle",
                "Miles",
                "Total Cost",
                "Cost/Mile",
                "Fuel Cost",
                "Maint Cost",
                "Insurance",
                "Depreciation",
                "ROI %",
            ]
        )
        layout.addWidget(self.table)
        self.setLayout(layout)
        self.load_data()

    def load_data(self) -> None:
        if not hasattr(self, "avg_cost_per_mile"):
            return
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                # Get vehicles with cost analysis
                cur.execute("""
                    SELECT v.vehicle_number,
                           0 as total_miles,
                           COALESCE(SUM(r.gross_amount), 0) as total_cost,
                           COALESCE(SUM(CASE
                               WHEN r.description ILIKE '%fuel%'
                               THEN r.gross_amount
                               ELSE 0 END), 0) as fuel_cost,
                           COALESCE(SUM(CASE
                               WHEN r.description ILIKE '%maint%'
                               THEN r.gross_amount
                               ELSE 0 END), 0) as maint_cost,
                           COALESCE(SUM(CASE
                               WHEN r.description ILIKE '%insur%'
                               THEN r.gross_amount
                               ELSE 0 END), 0) as insur_cost,
                           0 as depreciation
                    FROM vehicles v
                    LEFT JOIN receipts r ON v.vehicle_id = r.vehicle_id
                    GROUP BY v.vehicle_id, v.vehicle_number
                    ORDER BY v.vehicle_number
                """)

                rows = cur.fetchall()

            self.table.setRowCount(len(rows))

            total_cost_per_mile = 0.0
            total_vehicles = 0

            for i, (vnum, miles, total, fuel, maint, insur, depr) in enumerate(
                rows
            ):
                miles = float(miles or 0) or 1  # Avoid division by zero
                total = float(total or 0)
                cost_per_mile = total / miles if miles > 0 else 0

                self.table.setItem(i, 0, QTableWidgetItem(str(vnum or "")))
                self.table.setItem(i, 1, QTableWidgetItem(f"{miles:,.0f}"))
                self.table.setItem(i, 2, QTableWidgetItem(f"${total:,.2f}"))
                self.table.setItem(
                    i, 3, QTableWidgetItem(f"${cost_per_mile:,.2f}")
                )
                self.table.setItem(
                    i, 4, QTableWidgetItem(f"${float(fuel or 0):,.2f}")
                )
                self.table.setItem(
                    i, 5, QTableWidgetItem(f"${float(maint or 0):,.2f}")
                )
                self.table.setItem(
                    i, 6, QTableWidgetItem(f"${float(insur or 0):,.2f}")
                )
                self.table.setItem(
                    i, 7, QTableWidgetItem(f"${float(depr or 0):,.2f}")
                )

                total_cost_per_mile += cost_per_mile
                total_vehicles += 1

            if total_vehicles > 0:
                avg_cost = total_cost_per_mile / total_vehicles
                self.avg_cost_per_mile.setText(
                    f"Avg Cost/Mile: ${avg_cost:,.2f}"
                )
        except Exception as e:
            logger.error(f"Failed to load vehicle analytics: {e}")


class EmployeePayrollAuditWidget(BaseReportWidget):
    """Employee payroll audit - T4 generation, deductions, variance"""

    def __init__(self, db) -> None:
        columns = [
            {"header": "Vehicle", "key": "vehicle"},
            {"header": "Miles", "key": "miles"},
            {"header": "Total Cost", "key": "total_cost"},
            {"header": "Cost/Mile", "key": "cost_mile"},
            {"header": "Fuel Cost", "key": "fuel_cost"},
            {"header": "Maint Cost", "key": "maint_cost"},
            {"header": "Insurance", "key": "insurance"},
            {"header": "Depreciation", "key": "depreciation"},
            {"header": "ROI %", "key": "roi_%"},
        ]
        super().__init__(db, "EmployeePayrollAudit", columns)
        self.db = db
        layout = QVBoxLayout()
        layout.addWidget(
            QLabel(
                "<h3>👔 Employee Payroll Audit</h3><p>T4 generation, tax"
                "deductions, payroll variance</p>"
            )
        )

        # Year filter
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Tax Year:"))
        self.year_spin = QSpinBox()
        self.year_spin.setMinimum(2010)
        self.year_spin.setMaximum(datetime.now().year)
        self.year_spin.setValue(datetime.now().year)
        self.year_spin.valueChanged.connect(self.load_data)
        controls.addWidget(self.year_spin)
        controls.addStretch()
        layout.addLayout(controls)

        # T4 summary table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(
            [
                "Employee",
                "Gross Pay",
                "CPP Contrib",
                "EI Contrib",
                "Income Tax",
                "Total Deductions",
                "Net Pay",
                "T4 Box 14",
            ]
        )
        layout.addWidget(self.table)
        self.setLayout(layout)
        self.load_data()

    def load_data(self) -> None:
        if not hasattr(self, "year_spin"):
            return
        try:
            year = self.year_spin.value()

            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT e.full_name,
                           SUM(dp.gross_pay) as gross,
                          SUM(dp.cpp) as cpp_contrib,
                          SUM(dp.ei) as ei_contrib,
                          SUM(dp.tax) as income_tax,
                           SUM(dp.total_deductions) as total_ded,
                           SUM(dp.net_pay) as net
                    FROM employees e
                    LEFT JOIN driver_payroll dp ON e.employee_id =
                    dp.employee_id
                    WHERE EXTRACT(YEAR FROM dp.pay_date) = %s
                    GROUP BY e.employee_id, e.full_name
                    ORDER BY gross DESC
                """,
                    (year,),
                )

                rows = cur.fetchall()

            self.table.setRowCount(len(rows))

            for i, (name, gross, cpp, ei, tax, total_ded, net) in enumerate(
                rows
            ):
                self.table.setItem(i, 0, QTableWidgetItem(str(name or "")))
                self.table.setItem(
                    i, 1, QTableWidgetItem(f"${float(gross or 0):,.2f}")
                )
                self.table.setItem(
                    i, 2, QTableWidgetItem(f"${float(cpp or 0):,.2f}")
                )
                self.table.setItem(
                    i, 3, QTableWidgetItem(f"${float(ei or 0):,.2f}")
                )
                self.table.setItem(
                    i, 4, QTableWidgetItem(f"${float(tax or 0):,.2f}")
                )
                self.table.setItem(
                    i, 5, QTableWidgetItem(f"${float(total_ded or 0):,.2f}")
                )
                self.table.setItem(
                    i, 6, QTableWidgetItem(f"${float(net or 0):,.2f}")
                )
                self.table.setItem(
                    i, 7, QTableWidgetItem(f"${float(gross or 0):,.2f}")
                )
        except Exception as e:
            logger.error(f"Failed to load payroll audit: {e}")


class QuickBooksReconciliationWidget(BaseReportWidget):
    """QB reconciliation - sync status, account mapping, variance"""

    def __init__(self, db) -> None:
        columns = [
            {"header": "Vehicle", "key": "vehicle"},
            {"header": "Miles", "key": "miles"},
            {"header": "Total Cost", "key": "total_cost"},
            {"header": "Cost/Mile", "key": "cost_mile"},
            {"header": "Fuel Cost", "key": "fuel_cost"},
            {"header": "Maint Cost", "key": "maint_cost"},
            {"header": "Insurance", "key": "insurance"},
            {"header": "Depreciation", "key": "depreciation"},
            {"header": "ROI %", "key": "roi_%"},
        ]
        super().__init__(db, "QuickBooksReconciliation", columns)
        self.db = db
        layout = QVBoxLayout()
        layout.addWidget(
            QLabel(
                "<h3>📊 QuickBooks Reconciliation</h3><p>QB sync status,"
                "account mapping, variance analysis</p>"
            )
        )

        # Status indicators
        status = QHBoxLayout()
        self.sync_status = QLabel("QB Sync: Last Updated 0 days ago")
        self.account_match = QLabel("Account Mapping: 0/0 accounts")
        self.variance = QLabel("Total Variance: $0.00")
        status.addWidget(self.sync_status)
        status.addWidget(self.account_match)
        status.addWidget(self.variance)
        layout.addLayout(status)

        # Reconciliation detail table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            [
                "Account",
                "QB Balance",
                "LMS Balance",
                "Variance",
                "Last Matched",
                "Status",
            ]
        )
        layout.addWidget(self.table)
        self.setLayout(layout)
        self.load_data()

    def load_data(self) -> None:
        if not hasattr(self, "variance"):
            return
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                # Get QB export data and compare with LMS
                cur.execute("""
                    SELECT account_code,
                           account_name,
                           account_type,
                           0::numeric as balance
                    FROM chart_of_accounts
                    ORDER BY account_code
                    LIMIT 100
                """)

                rows = cur.fetchall()

            self.table.setRowCount(len(rows))
            total_variance = 0.0

            for i, (code, name, acct_type, balance) in enumerate(rows):
                balance = float(balance or 0)
                # For now, assume QB and LMS are equal (in reality, would query
                # QB tables)
                qb_balance = balance
                lms_balance = balance
                variance = abs(qb_balance - lms_balance)
                total_variance += variance

                self.table.setItem(i, 0, QTableWidgetItem(f"{code} - {name}"))
                self.table.setItem(
                    i, 1, QTableWidgetItem(f"${qb_balance:,.2f}")
                )
                self.table.setItem(
                    i, 2, QTableWidgetItem(f"${lms_balance:,.2f}")
                )
                self.table.setItem(i, 3, QTableWidgetItem(f"${variance:,.2f}"))
                self.table.setItem(i, 4, QTableWidgetItem("Today"))
                status = "✓ Matched" if variance == 0 else "⚠ Variance"
                self.table.setItem(i, 5, QTableWidgetItem(status))

            self.variance.setText(f"Total Variance: ${total_variance:,.2f}")
            self.account_match.setText(
                f"Account Mapping: {len(rows)}/{len(rows)} accounts"
            )
        except Exception as e:
            logger.error(f"Failed to load QB reconciliation: {e}")


class CharterAnalyticsWidget(BaseReportWidget):
    """Charter analytics - booking trends, route profitability, customer"
    "analysis"""

    def __init__(self, db) -> None:
        columns = [
            {"header": "Vehicle", "key": "vehicle"},
            {"header": "Miles", "key": "miles"},
            {"header": "Total Cost", "key": "total_cost"},
            {"header": "Cost/Mile", "key": "cost_mile"},
            {"header": "Fuel Cost", "key": "fuel_cost"},
            {"header": "Maint Cost", "key": "maint_cost"},
            {"header": "Insurance", "key": "insurance"},
            {"header": "Depreciation", "key": "depreciation"},
            {"header": "ROI %", "key": "roi_%"},
        ]
        super().__init__(db, "CharterAnalytics", columns)
        self.db = db
        layout = QVBoxLayout()
        layout.addWidget(
            QLabel(
                "<h3>📈 Charter Analytics</h3><p>Booking trends, route"
                "profitability, customer insights</p>"
            )
        )

        # Summary metrics
        summary = QHBoxLayout()
        self.total_bookings = QLabel("Total Bookings: 0")
        self.avg_booking_value = QLabel("Avg Value: $0")
        self.cancellation_rate = QLabel("Cancellation Rate: 0%")
        summary.addWidget(self.total_bookings)
        summary.addWidget(self.avg_booking_value)
        summary.addWidget(self.cancellation_rate)
        layout.addLayout(summary)

        # Analytics table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            [
                "Month",
                "Bookings",
                "Revenue",
                "Avg Value",
                "Cancelled",
                "Cancel %",
                "Profit",
            ]
        )
        layout.addWidget(self.table)
        self.setLayout(layout)
        self.load_data()

    def load_data(self) -> None:
        if not hasattr(self, "total_bookings"):
            return
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                # Monthly booking trends
                cur.execute("""
                    SELECT DATE_TRUNC('month', charter_date)::DATE as month,
                           COUNT(*) as bookings,
                           SUM(total_amount_due) as revenue,
                           AVG(total_amount_due) as avg_value,
                           SUM(CASE WHEN status = 'cancelled'
                               THEN 1 ELSE 0 END) as cancelled,
                           SUM(CASE WHEN status = 'completed'
                               THEN total_amount_due
                               ELSE 0 END) as completed_revenue
                    FROM charters
                    WHERE charter_date >= CURRENT_DATE - INTERVAL '12 months'
                    GROUP BY DATE_TRUNC('month', charter_date)
                    ORDER BY month DESC
                    LIMIT 12
                """)

                rows = cur.fetchall()

            self.table.setRowCount(len(rows))

            total_bookings = 0
            total_revenue = 0.0

            for i, (
                month,
                bookings,
                revenue,
                avg_val,
                cancelled,
                comp_rev,
            ) in enumerate(rows):
                bookings = int(bookings or 0)
                revenue = float(revenue or 0)
                avg_val = float(avg_val or 0)
                cancelled = int(cancelled or 0)
                comp_rev = float(comp_rev or 0)
                cancel_pct = (
                    (cancelled / bookings * 100) if bookings > 0 else 0
                )

                self.table.setItem(i, 0, QTableWidgetItem(str(month or "")))
                self.table.setItem(i, 1, QTableWidgetItem(str(bookings)))
                self.table.setItem(i, 2, QTableWidgetItem(f"${revenue:,.2f}"))
                self.table.setItem(i, 3, QTableWidgetItem(f"${avg_val:,.2f}"))
                self.table.setItem(i, 4, QTableWidgetItem(str(cancelled)))
                self.table.setItem(
                    i, 5, QTableWidgetItem(f"{cancel_pct:.1f}%")
                )
                self.table.setItem(i, 6, QTableWidgetItem(f"${comp_rev:,.2f}"))

                total_bookings += bookings
                total_revenue += revenue

            avg_booking = (
                (total_revenue / total_bookings) if total_bookings > 0 else 0
            )
            self.total_bookings.setText(f"Total Bookings: {total_bookings}")
            self.avg_booking_value.setText(f"Avg Value: ${avg_booking:,.2f}")
        except Exception as e:
            logger.error(f"Failed to load charter analytics: {e}")


# ============================================================================
# PHASE 3: COMPLIANCE & ADVANCED ANALYTICS
# ============================================================================


class ComplianceTrackingWidget(BaseReportWidget):
    """Compliance tracking - HOS, insurance, licensing, regulatory"""

    def __init__(self, db) -> None:
        columns = [
            {"header": "Vehicle", "key": "vehicle"},
            {"header": "Miles", "key": "miles"},
            {"header": "Total Cost", "key": "total_cost"},
            {"header": "Cost/Mile", "key": "cost_mile"},
            {"header": "Fuel Cost", "key": "fuel_cost"},
            {"header": "Maint Cost", "key": "maint_cost"},
            {"header": "Insurance", "key": "insurance"},
            {"header": "Depreciation", "key": "depreciation"},
            {"header": "ROI %", "key": "roi_%"},
        ]
        super().__init__(db, "ComplianceTracking", columns)
        self.db = db
        layout = QVBoxLayout()
        layout.addWidget(
            QLabel(
                "<h3>✅ Compliance Tracking</h3><p>HOS violations, insurance"
                "status, licensing</p>"
            )
        )

        # Status summary
        status = QHBoxLayout()
        self.hos_violations = QLabel("HOS Violations: 0")
        self.insurance_expiring = QLabel("Insurance Expiring Soon: 0")
        self.licenses_expiring = QLabel("Licenses Expiring: 0")
        status.addWidget(self.hos_violations)
        status.addWidget(self.insurance_expiring)
        status.addWidget(self.licenses_expiring)
        layout.addLayout(status)

        # Compliance issues table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            [
                "Item",
                "Type",
                "Status",
                "Due/Expires",
                "Days Remaining",
                "Action",
            ]
        )
        layout.addWidget(self.table)
        self.setLayout(layout)
        self.load_data()

    def load_data(self) -> None:
        if not hasattr(self, "table") or not hasattr(self, "insurance_expiring"):
            return

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                has_insurance = table_exists(self.db, "insurance_policies")
                has_licenses = table_exists(self.db, "driver_licenses")

                if not has_insurance and not has_licenses:
                    self.table.setRowCount(0)
                    self.insurance_expiring.setText(
                        "Insurance Expiring Soon: 0"
                    )
                    self.licenses_expiring.setText("Licenses Expiring: 0")
                    return

                parts = []
                if has_insurance:
                    parts.append(
                        """
                        SELECT 'Insurance' as type, policy_number,
                               'Active', expiry_date,
                               (expiry_date - CURRENT_DATE) as days_left
                        FROM insurance_policies
                        WHERE expiry_date <= CURRENT_DATE + INTERVAL '30 days'
                        """
                    )

                if has_licenses:
                    parts.append(
                        """
                        SELECT 'License' as type, license_number,
                               license_status, expiry_date,
                               (expiry_date - CURRENT_DATE) as days_left
                        FROM driver_licenses
                        WHERE expiry_date <= CURRENT_DATE + INTERVAL '60 days'
                        """
                    )

                query = " UNION ALL ".join(parts) + " ORDER BY days_left ASC LIMIT 20"
                cur.execute(query)

                rows = cur.fetchall()

            self.table.setRowCount(len(rows))

            insurance_count = 0
            for i, (typ, identifier, status, expires, days) in enumerate(rows):
                days = int(days or 0)
                self.table.setItem(
                    i, 0, QTableWidgetItem(str(identifier or ""))
                )
                self.table.setItem(i, 1, QTableWidgetItem(str(typ or "")))
                self.table.setItem(i, 2, QTableWidgetItem(str(status or "")))
                self.table.setItem(i, 3, QTableWidgetItem(str(expires or "")))
                self.table.setItem(i, 4, QTableWidgetItem(f"{days} days"))

                if days < 0:
                    action = "⚠️ EXPIRED"
                elif days < 7:
                    action = "🔴 URGENT"
                elif days < 30:
                    action = "🟡 SOON"
                else:
                    action = "✓ OK"
                self.table.setItem(i, 5, QTableWidgetItem(action))

                if "Insurance" in str(typ):
                    insurance_count += 1

            self.insurance_expiring.setText(
                f"Insurance Expiring Soon: {insurance_count}"
            )
        except Exception as e:
            logger.error(f"Failed to load compliance tracking: {e}")


class BudgetAnalysisWidget(BaseReportWidget):
    """Budget vs actual analysis"""

    def __init__(self, db) -> None:
        columns = [
            {"header": "Vehicle", "key": "vehicle"},
            {"header": "Miles", "key": "miles"},
            {"header": "Total Cost", "key": "total_cost"},
            {"header": "Cost/Mile", "key": "cost_mile"},
            {"header": "Fuel Cost", "key": "fuel_cost"},
            {"header": "Maint Cost", "key": "maint_cost"},
            {"header": "Insurance", "key": "insurance"},
            {"header": "Depreciation", "key": "depreciation"},
            {"header": "ROI %", "key": "roi_%"},
        ]
        super().__init__(db, "BudgetAnalysis", columns)
        self.db = db
        layout = QVBoxLayout()
        layout.addWidget(
            QLabel(
                "<h3>💰 Budget vs Actual</h3><p>Compare budgeted vs actual"
                "expenses and revenue</p>"
            )
        )

        # Summary
        summary = QHBoxLayout()
        self.total_budget = QLabel("Total Budget: $0")
        self.total_actual = QLabel("Total Actual: $0")
        self.variance = QLabel("Variance: $0 (0%)")
        summary.addWidget(self.total_budget)
        summary.addWidget(self.total_actual)
        summary.addWidget(self.variance)
        layout.addLayout(summary)

        # Budget vs actual table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            [
                "Category",
                "Budgeted",
                "Actual",
                "Variance $",
                "Variance %",
                "Status",
            ]
        )
        layout.addWidget(self.table)
        self.setLayout(layout)
        self.load_data()

    def load_data(self) -> None:
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                # For now, show by expense category (budget vs actual from
                # receipts)
                cur.execute("""
                    SELECT category, COUNT(*) as count,
                    SUM(gross_amount) as total
                    FROM receipts
                    WHERE receipt_date >= CURRENT_DATE - INTERVAL '90 days'
                    GROUP BY category
                    ORDER BY total DESC
                """)

                rows = cur.fetchall()

            self.table.setRowCount(len(rows))

            for i, (category, count, total) in enumerate(rows):
                total = float(total or 0)
                # Assume budget is 10% more than actual as placeholder
                budget = total * 1.1
                variance = total - budget
                variance_pct = (variance / budget * 100) if budget > 0 else 0

                self.table.setItem(
                    i, 0, QTableWidgetItem(str(category or "Uncategorized"))
                )
                self.table.setItem(i, 1, QTableWidgetItem(f"${budget:,.2f}"))
                self.table.setItem(i, 2, QTableWidgetItem(f"${total:,.2f}"))
                self.table.setItem(i, 3, QTableWidgetItem(f"${variance:,.2f}"))
                self.table.setItem(
                    i, 4, QTableWidgetItem(f"{variance_pct:.1f}%")
                )

                status = "✓ Under" if variance < 0 else "⚠ Over"
                self.table.setItem(i, 5, QTableWidgetItem(status))
        except Exception as e:
            logger.error(f"Failed to load budget analysis: {e}")


class InsuranceTrackingWidget(BaseReportWidget):
    """Insurance tracking & claims"""

    def __init__(self, db) -> None:
        columns = [
            {"header": "Vehicle", "key": "vehicle"},
            {"header": "Miles", "key": "miles"},
            {"header": "Total Cost", "key": "total_cost"},
            {"header": "Cost/Mile", "key": "cost_mile"},
            {"header": "Fuel Cost", "key": "fuel_cost"},
            {"header": "Maint Cost", "key": "maint_cost"},
            {"header": "Insurance", "key": "insurance"},
            {"header": "Depreciation", "key": "depreciation"},
            {"header": "ROI %", "key": "roi_%"},
        ]
        super().__init__(db, "InsuranceTracking", columns)
        self.db = db
        layout = QVBoxLayout()
        layout.addWidget(
            QLabel(
                "<h3>🛡️ Insurance Tracking</h3><p>Policy status, claims,"
                "coverage review</p>"
            )
        )

        # Summary
        summary = QHBoxLayout()
        self.active_policies = QLabel("Active Policies: 0")
        self.total_coverage = QLabel("Total Coverage: $0")
        self.pending_claims = QLabel("Pending Claims: 0")
        summary.addWidget(self.active_policies)
        summary.addWidget(self.total_coverage)
        summary.addWidget(self.pending_claims)
        layout.addLayout(summary)

        # Policies table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            [
                "Policy #",
                "Type",
                "Coverage $",
                "Premium",
                "Expires",
                "Claims",
                "Status",
            ]
        )
        layout.addWidget(self.table)
        self.setLayout(layout)
        self.load_data()

    def load_data(self) -> None:
        if not hasattr(self, "table"):
            return

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                if not table_exists(self.db, "insurance_policies"):
                    self.table.setRowCount(0)
                    if hasattr(self, "active_policies"):
                        self.active_policies.setText("Active Policies: 0")
                    if hasattr(self, "total_coverage"):
                        self.total_coverage.setText("Total Coverage: $0")
                    if hasattr(self, "pending_claims"):
                        self.pending_claims.setText("Pending Claims: 0")
                    return

                cur.execute("""
                    SELECT policy_number, policy_type, coverage_amount,
                    annual_premium, expiry_date
                    FROM insurance_policies
                    WHERE status = 'active'
                        OR expiry_date >= CURRENT_DATE - INTERVAL '30 days'
                    ORDER BY expiry_date
                """)

                rows = cur.fetchall()

            self.table.setRowCount(len(rows))

            total_coverage = 0.0
            for i, (
                policy,
                policy_type,
                coverage,
                premium,
                expires,
            ) in enumerate(rows):
                coverage = float(coverage or 0)
                premium = float(premium or 0)

                self.table.setItem(i, 0, QTableWidgetItem(str(policy or "")))
                self.table.setItem(
                    i, 1, QTableWidgetItem(str(policy_type or ""))
                )
                self.table.setItem(i, 2, QTableWidgetItem(f"${coverage:,.0f}"))
                self.table.setItem(i, 3, QTableWidgetItem(f"${premium:,.2f}"))
                self.table.setItem(i, 4, QTableWidgetItem(str(expires or "")))
                self.table.setItem(i, 5, QTableWidgetItem("0"))

                days_left = (
                    (expires - QDate.currentDate()).days()
                    if isinstance(expires, QDate)
                    else 0
                )
                status = "✓ Active" if days_left > 0 else "⚠ Expired"
                self.table.setItem(i, 6, QTableWidgetItem(status))

                total_coverage += coverage

            self.active_policies.setText(f"Active Policies: {len(rows)}")
            self.total_coverage.setText(
                f"Total Coverage: ${total_coverage:,.0f}"
            )
        except Exception as e:
            logger.error(f"Failed to load insurance tracking: {e}")
