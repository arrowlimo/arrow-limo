"""
Phase 4-6 Dashboard Widgets: Fleet Management, Employee/Payroll, Payments,
Financial Reports
Implements 15+ advanced dashboards for comprehensive business analytics
"""

import logging
from datetime import datetime

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

try:
    from app_settings import DASHBOARD_YEARS, WORKING_YEAR
except ImportError:
    # Fallback if app_settings not available
    DASHBOARD_YEARS = list(range(2010, 2031))
    WORKING_YEAR = datetime.now().year
from db_error_handling import DatabaseContext, table_exists
from reporting_base import BaseReportWidget

logger = logging.getLogger(__name__)


# ============================================================================
# PHASE 4: FLEET MANAGEMENT DASHBOARDS (5 widgets)
# ============================================================================


class VehicleFleetCostAnalysisWidget(BaseReportWidget):
    """Vehicle Fleet Cost Analysis - Cost/mile, ROI, depreciation"""

    def __init__(self, db) -> None:
        columns = [
            {"header": "Vehicle", "key": "vehicle"},
            {"header": "Purchase Price", "key": "purchase_price"},
            {"header": "Loan Payments", "key": "loan_payments"},
            {"header": "Insurance", "key": "insurance"},
            {"header": "Maintenance", "key": "maintenance"},
            {"header": "Fuel", "key": "fuel"},
            {"header": "Total Cost", "key": "total_cost"},
            {"header": "Cost/Mile", "key": "cost_mile"},
        ]
        super().__init__(db, "VehicleFleetCostAnalysis", columns)
        self.db = db
        self.init_ui()
        self.load_data()

    def init_ui(self) -> None:
        layout = QVBoxLayout()

        title = QLabel("🚗 Vehicle Fleet Cost Analysis")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # Filters
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Year:"))
        year_combo = QComboBox()
        year_combo.addItems([str(y) for y in DASHBOARD_YEARS])
        year_combo.setCurrentText(str(WORKING_YEAR))
        filter_layout.addWidget(year_combo)
        layout.addLayout(filter_layout)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(
            [
                "Vehicle",
                "Purchase Price",
                "Loan Payments",
                "Insurance",
                "Maintenance",
                "Fuel",
                "Total Cost",
                "Cost/Mile",
            ]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 120)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        self.setLayout(layout)

    def load_data(self) -> None:
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT
                        v.vehicle_number,
                        0 as purchase_price,
                        COALESCE(SUM(CASE WHEN r.category = 'Loan Payment'
                            THEN r.gross_amount ELSE 0 END), 0) as loan_pmts,
                        COALESCE(SUM(CASE WHEN r.category = 'Insurance'
                            THEN r.gross_amount ELSE 0 END), 0) as insurance,
                        COALESCE(SUM(CASE WHEN r.category = 'Maintenance'
                            THEN r.gross_amount ELSE 0 END), 0) as maintenance,
                        COALESCE(SUM(CASE WHEN r.category = 'Fuel'
                            THEN r.gross_amount ELSE 0 END), 0) as fuel,
                        COUNT(DISTINCT c.charter_id) as charter_count
                    FROM vehicles v
                    LEFT JOIN receipts r ON r.vehicle_id = v.vehicle_id AND
                    EXTRACT(YEAR FROM r.receipt_date) = %s
                    LEFT JOIN charters c ON c.vehicle_id = v.vehicle_id AND
                    EXTRACT(YEAR FROM c.charter_date) = %s
                    GROUP BY v.vehicle_id, v.vehicle_number
                    ORDER BY v.vehicle_number
                """,
                    (datetime.now().year, datetime.now().year),
                )

                rows = cur.fetchall()

            self.table.setRowCount(len(rows))

            for row_idx, row in enumerate(rows):
                vehicle, purchase, loans, insurance, maint, fuel, charters = (
                    row
                )
                total_cost = (
                    (purchase or 0)
                    + (loans or 0)
                    + (insurance or 0)
                    + (maint or 0)
                    + (fuel or 0)
                )
                cost_per_charter = (
                    total_cost / (charters or 1) if charters else 0
                )

                self.table.setItem(row_idx, 0, QTableWidgetItem(str(vehicle)))
                self.table.setItem(
                    row_idx, 1, QTableWidgetItem(f"${purchase or 0:.2f}")
                )
                self.table.setItem(
                    row_idx, 2, QTableWidgetItem(f"${loans or 0:.2f}")
                )
                self.table.setItem(
                    row_idx, 3, QTableWidgetItem(f"${insurance or 0:.2f}")
                )
                self.table.setItem(
                    row_idx, 4, QTableWidgetItem(f"${maint or 0:.2f}")
                )
                self.table.setItem(
                    row_idx, 5, QTableWidgetItem(f"${fuel or 0:.2f}")
                )
                self.table.setItem(
                    row_idx, 6, QTableWidgetItem(f"${total_cost:.2f}")
                )
                self.table.setItem(
                    row_idx, 7, QTableWidgetItem(f"${cost_per_charter:.2f}")
                )

            print(
                f"✅ Vehicle Fleet Cost Analysis loaded {len(rows)} vehicles"
            )
        except Exception:
            logger.exception("Vehicle Fleet Cost Analysis load error")
            self.table.setRowCount(0)


class VehicleMaintenanceTrackingWidget(BaseReportWidget):
    """Vehicle Maintenance Tracking - Schedule, overdue, history"""

    def __init__(self, db) -> None:
        columns = [
            {"header": "Vehicle", "key": "vehicle"},
            {"header": "Purchase Price", "key": "purchase_price"},
            {"header": "Loan Payments", "key": "loan_payments"},
            {"header": "Insurance", "key": "insurance"},
            {"header": "Maintenance", "key": "maintenance"},
            {"header": "Fuel", "key": "fuel"},
            {"header": "Total Cost", "key": "total_cost"},
            {"header": "Cost/Mile", "key": "cost_mile"},
        ]
        super().__init__(db, "VehicleMaintenanceTracking", columns)
        self.db = db
        self.init_ui()
        self.load_data()

    def init_ui(self) -> None:
        layout = QVBoxLayout()

        title = QLabel("🔧 Vehicle Maintenance Tracking")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # Filters
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Status:"))
        status_combo = QComboBox()
        status_combo.addItems(
            ["All", "Overdue", "Due Soon", "Scheduled", "Completed"]
        )
        filter_layout.addWidget(status_combo)
        layout.addLayout(filter_layout)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            [
                "Vehicle",
                "Service Type",
                "Last Service",
                "Next Due (km)",
                "Days Until",
                "Status",
                "Cost",
            ]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 120)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(5, 80)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(6, 110)
        layout.addWidget(self.table)

        self.setLayout(layout)

    def load_data(self) -> None:
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                if not table_exists(self.db, "maintenance_schedules"):
                    self.table.setRowCount(0)
                    return

                cur.execute("""
                    SELECT
                        v.vehicle_number,
                        ms.service_type,
                        mr.service_date,
                        ms.next_service_km,
                        EXTRACT(DAY FROM ms.next_service_date - CURRENT_DATE)
                        as days_until,
                        CASE
                            WHEN ms.next_service_date < CURRENT_DATE
                                THEN 'Overdue'
                            WHEN ms.next_service_date
                                < CURRENT_DATE + INTERVAL '7 days'
                                THEN 'Due Soon'
                            ELSE 'Scheduled'
                        END as status,
                        COALESCE(mr.labor_cost + mr.parts_cost,
                        0) as service_cost
                    FROM vehicles v
                    LEFT JOIN maintenance_schedules ms ON ms.vehicle_id =
                    v.vehicle_id
                    LEFT JOIN maintenance_records mr ON mr.vehicle_id =
                    v.vehicle_id
                        AND mr.service_date = (SELECT MAX(service_date) FROM
                        maintenance_records WHERE vehicle_id = v.vehicle_id)
                    ORDER BY ms.next_service_date ASC
                    LIMIT 100
                """)

                rows = cur.fetchall()

            self.table.setRowCount(len(rows))

            for row_idx, row in enumerate(rows):
                if row[0]:  # If vehicle exists
                    (
                        vehicle,
                        service,
                        last_date,
                        next_km,
                        days,
                        status,
                        cost,
                    ) = row
                    self.table.setItem(
                        row_idx, 0, QTableWidgetItem(str(vehicle))
                    )
                    self.table.setItem(
                        row_idx, 1, QTableWidgetItem(str(service or ""))
                    )
                    self.table.setItem(
                        row_idx, 2, QTableWidgetItem(str(last_date or ""))
                    )
                    self.table.setItem(
                        row_idx, 3, QTableWidgetItem(str(next_km or ""))
                    )
                    self.table.setItem(
                        row_idx, 4, QTableWidgetItem(str(days or ""))
                    )
                    self.table.setItem(
                        row_idx, 5, QTableWidgetItem(str(status or ""))
                    )
                    self.table.setItem(
                        row_idx, 6, QTableWidgetItem(f"${cost or 0:.2f}")
                    )
        except Exception as e:
            logger.error(f"Failed to load maintenance schedules: {e}")
            pass  # Table may be empty if no maintenance data


class FuelEfficiencyTrackingWidget(BaseReportWidget):
    """Fuel Efficiency Tracking - Cost per gallon, trends"""

    def __init__(self, db) -> None:
        columns = [
            {"header": "Vehicle", "key": "vehicle"},
            {"header": "Purchase Price", "key": "purchase_price"},
            {"header": "Loan Payments", "key": "loan_payments"},
            {"header": "Insurance", "key": "insurance"},
            {"header": "Maintenance", "key": "maintenance"},
            {"header": "Fuel", "key": "fuel"},
            {"header": "Total Cost", "key": "total_cost"},
            {"header": "Cost/Mile", "key": "cost_mile"},
        ]
        super().__init__(db, "FuelEfficiencyTracking", columns)
        self.db = db
        self.init_ui()
        self.load_data()

    def init_ui(self) -> None:
        layout = QVBoxLayout()

        title = QLabel("⛽ Fuel Efficiency Analysis")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            [
                "Vehicle",
                "Total Fuel Cost",
                "Gallons Used",
                "Cost/Gallon",
                "Distance (km)",
                "Cost/km",
                "Trend",
            ]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 120)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        self.setLayout(layout)

    def load_data(self) -> None:
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute("""
                    SELECT
                        v.vehicle_number,
                        COALESCE(SUM(r.gross_amount), 0) as fuel_cost,
                        COALESCE(SUM(r.fuel_amount), 0) as liters,
                        CASE WHEN COALESCE(SUM(r.fuel_amount), 0) > 0
                            THEN COALESCE(SUM(r.gross_amount),
                            0) / SUM(r.fuel_amount)
                            ELSE 0 END as cost_per_liter,
                        COUNT(DISTINCT c.charter_id) as charter_count
                    FROM vehicles v
                    LEFT JOIN receipts r
                        ON r.vehicle_id = v.vehicle_id AND r.category = 'Fuel'
                    LEFT JOIN charters c ON c.vehicle_id = v.vehicle_id
                    GROUP BY v.vehicle_id, v.vehicle_number
                    ORDER BY v.vehicle_number
                """)

                rows = cur.fetchall()

            self.table.setRowCount(len(rows))

            for row_idx, row in enumerate(rows):
                vehicle, fuel_cost, liters, cost_per_liter, charters = row
                cost_per_charter = (
                    (fuel_cost or 0) / (charters or 1) if charters else 0
                )
                trend = (
                    "↑"
                    if cost_per_liter and cost_per_liter > 2.0
                    else (
                        "↓" if cost_per_liter and cost_per_liter < 1.0 else "→"
                    )
                )

                self.table.setItem(row_idx, 0, QTableWidgetItem(str(vehicle)))
                self.table.setItem(
                    row_idx, 1, QTableWidgetItem(f"${fuel_cost or 0:.2f}")
                )
                self.table.setItem(
                    row_idx, 2, QTableWidgetItem(f"{liters or 0:.1f}L")
                )
                self.table.setItem(
                    row_idx,
                    3,
                    QTableWidgetItem(f"${cost_per_liter or 0:.2f}/L"),
                )
                self.table.setItem(
                    row_idx, 4, QTableWidgetItem(f"{charters or 0:.0f}")
                )
                self.table.setItem(
                    row_idx, 5, QTableWidgetItem(f"${cost_per_charter:.2f}")
                )
                self.table.setItem(row_idx, 6, QTableWidgetItem(trend))

            print(f"✅ Fuel Efficiency loaded {len(rows)} vehicles")
        except Exception:
            logger.exception("Fuel Efficiency load error")
            self.table.setRowCount(0)


class VehicleUtilizationWidget(BaseReportWidget):
    """Vehicle Utilization - Bookings vs available time"""

    def __init__(self, db) -> None:
        columns = [
            {"header": "Vehicle", "key": "vehicle"},
            {"header": "Purchase Price", "key": "purchase_price"},
            {"header": "Loan Payments", "key": "loan_payments"},
            {"header": "Insurance", "key": "insurance"},
            {"header": "Maintenance", "key": "maintenance"},
            {"header": "Fuel", "key": "fuel"},
            {"header": "Total Cost", "key": "total_cost"},
            {"header": "Cost/Mile", "key": "cost_mile"},
        ]
        super().__init__(db, "VehicleUtilization", columns)
        self.db = db
        self.init_ui()
        self.load_data()

    def init_ui(self) -> None:
        layout = QVBoxLayout()

        title = QLabel("📊 Vehicle Utilization Rate")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            [
                "Vehicle",
                "Total Hours Available",
                "Booked Hours",
                "Utilization %",
                "Charters This Month",
                "Revenue",
            ]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 120)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(5, 110)
        layout.addWidget(self.table)

        self.setLayout(layout)

    def load_data(self) -> None:
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute("""
                    SELECT
                        v.vehicle_number,
                        COALESCE(SUM(c.quoted_hours), 0) as booked_hours,
                        COUNT(DISTINCT c.charter_id) as charter_count,
                        COALESCE(SUM(c.total_amount_due), 0) as revenue
                    FROM vehicles v
                    LEFT JOIN charters c ON c.vehicle_id = v.vehicle_id
                        AND EXTRACT(MONTH FROM c.charter_date) = EXTRACT(MONTH
                        FROM CURRENT_DATE)
                        AND EXTRACT(YEAR FROM c.charter_date) = EXTRACT(YEAR
                        FROM CURRENT_DATE)
                    GROUP BY v.vehicle_id, v.vehicle_number
                    ORDER BY v.vehicle_number
                """)

                rows = cur.fetchall()

            self.table.setRowCount(len(rows))

            for row_idx, row in enumerate(rows):
                vehicle, booked_hours, charter_count, revenue = row
                available_hours = 24 * 30  # 30 days in month
                utilization = (
                    (booked_hours or 0) / available_hours * 100
                    if available_hours > 0
                    else 0
                )

                self.table.setItem(row_idx, 0, QTableWidgetItem(str(vehicle)))
                self.table.setItem(
                    row_idx, 1, QTableWidgetItem(f"{available_hours:.0f}")
                )
                self.table.setItem(
                    row_idx, 2, QTableWidgetItem(f"{booked_hours or 0:.1f}")
                )
                self.table.setItem(
                    row_idx, 3, QTableWidgetItem(f"{utilization:.1f}%")
                )
                self.table.setItem(
                    row_idx, 4, QTableWidgetItem(str(charter_count or 0))
                )
                self.table.setItem(
                    row_idx, 5, QTableWidgetItem(f"${revenue or 0:.2f}")
                )
        except Exception as e:
            logger.error(f"Failed to load vehicle utilization: {e}")


class FleetAgeAnalysisWidget(BaseReportWidget):
    """Fleet Age Analysis - Replacement needs, depreciation"""

    def __init__(self, db) -> None:
        columns = [
            {"header": "Vehicle", "key": "vehicle"},
            {"header": "Purchase Price", "key": "purchase_price"},
            {"header": "Loan Payments", "key": "loan_payments"},
            {"header": "Insurance", "key": "insurance"},
            {"header": "Maintenance", "key": "maintenance"},
            {"header": "Fuel", "key": "fuel"},
            {"header": "Total Cost", "key": "total_cost"},
            {"header": "Cost/Mile", "key": "cost_mile"},
        ]
        super().__init__(db, "FleetAgeAnalysis", columns)
        self.db = db
        self.init_ui()
        self.load_data()

    def init_ui(self) -> None:
        layout = QVBoxLayout()

        title = QLabel("📈 Fleet Age & Replacement Analysis")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(
            [
                "Vehicle",
                "Model Year",
                "Age (Years)",
                "Purchase Price",
                "Current Value",
                "Depreciation %",
                "Mileage",
                "Condition",
            ]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 120)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        self.setLayout(layout)

    def load_data(self) -> None:
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute("""
                    SELECT
                        v.vehicle_number,
                        v.year,
                        COUNT(DISTINCT c.charter_id) as charter_count
                    FROM vehicles v
                    LEFT JOIN charters c ON c.vehicle_id = v.vehicle_id
                    GROUP BY v.vehicle_id, v.vehicle_number, v.year
                    ORDER BY v.vehicle_number
                """)

                rows = cur.fetchall()

            self.table.setRowCount(len(rows))

            for row_idx, row in enumerate(rows):
                vehicle, model_year, charter_count = row
                age = datetime.now().year - (model_year or datetime.now().year)
                purchase_price = (
                    50000  # Placeholder since we don't have this data
                )
                current_value = purchase_price * (
                    0.85**age
                )  # 15% depreciation/year
                depreciation = (
                    ((purchase_price or 0) - current_value)
                    / (purchase_price or 1)
                    * 100
                )
                condition = (
                    "Excellent"
                    if age < 3
                    else "Good" if age < 6 else "Fair" if age < 10 else "Poor"
                )

                self.table.setItem(row_idx, 0, QTableWidgetItem(str(vehicle)))
                self.table.setItem(
                    row_idx, 1, QTableWidgetItem(str(model_year or ""))
                )
                self.table.setItem(row_idx, 2, QTableWidgetItem(str(age)))
                self.table.setItem(
                    row_idx, 3, QTableWidgetItem(f"${purchase_price:,.2f}")
                )
                self.table.setItem(
                    row_idx, 4, QTableWidgetItem(f"${current_value:,.2f}")
                )
                self.table.setItem(
                    row_idx, 5, QTableWidgetItem(f"{depreciation:.1f}%")
                )
                self.table.setItem(
                    row_idx, 6, QTableWidgetItem(f"{charter_count or 0}")
                )
                self.table.setItem(row_idx, 7, QTableWidgetItem(condition))

            print(f"✅ Fleet Age Analysis loaded {len(rows)} vehicles")
        except Exception:
            logger.exception("Fleet Age Analysis load error")
            self.table.setRowCount(0)


# ============================================================================
# PHASE 5: EMPLOYEE/PAYROLL DASHBOARDS (5 widgets)
# ============================================================================


class DriverPayAnalysisWidget(BaseReportWidget):
    """Driver Pay Analysis - Gross, deductions, reimbursements"""

    def __init__(self, db) -> None:
        columns = [
            {"header": "Vehicle", "key": "vehicle"},
            {"header": "Purchase Price", "key": "purchase_price"},
            {"header": "Loan Payments", "key": "loan_payments"},
            {"header": "Insurance", "key": "insurance"},
            {"header": "Maintenance", "key": "maintenance"},
            {"header": "Fuel", "key": "fuel"},
            {"header": "Total Cost", "key": "total_cost"},
            {"header": "Cost/Mile", "key": "cost_mile"},
        ]
        super().__init__(db, "DriverPayAnalysis", columns)
        self.db = db
        self.init_ui()
        self.load_data()

    def init_ui(self) -> None:
        layout = QVBoxLayout()

        title = QLabel("💰 Driver Pay Analysis")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # Filters
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Year:"))
        year_combo = QComboBox()
        year_combo.addItems([str(y) for y in DASHBOARD_YEARS])
        year_combo.setCurrentText(str(WORKING_YEAR))
        filter_layout.addWidget(year_combo)
        layout.addLayout(filter_layout)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            [
                "Driver",
                "Gross Pay",
                "CPP",
                "EI",
                "Income Tax",
                "Net Pay",
                "Reimbursements",
            ]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 120)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        self.setLayout(layout)

    def load_data(self) -> None:
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT
                        e.full_name,
                        COALESCE(SUM(dp.gross_pay), 0) as gross,
                        COALESCE(SUM(dp.cpp), 0) as cpp,
                        COALESCE(SUM(dp.ei), 0) as ei,
                        COALESCE(SUM(dp.tax), 0) as tax,
                        COALESCE(SUM(dp.net_pay), 0) as net,
                        0 as reimburse
                    FROM employees e
                    LEFT JOIN driver_payroll dp ON dp.employee_id =
                    e.employee_id
                        AND EXTRACT(YEAR FROM dp.pay_date) = %s
                    WHERE e.is_chauffeur = true
                        AND e.employment_status = 'active'
                    GROUP BY e.employee_id, e.full_name
                    ORDER BY e.full_name
                """,
                    (datetime.now().year,),
                )

                rows = cur.fetchall()

            self.table.setRowCount(len(rows))

            for row_idx, row in enumerate(rows):
                driver, gross, cpp, ei, tax, net, reimburse = row
                self.table.setItem(row_idx, 0, QTableWidgetItem(str(driver)))
                self.table.setItem(
                    row_idx, 1, QTableWidgetItem(f"${gross or 0:.2f}")
                )
                self.table.setItem(
                    row_idx, 2, QTableWidgetItem(f"${cpp or 0:.2f}")
                )
                self.table.setItem(
                    row_idx, 3, QTableWidgetItem(f"${ei or 0:.2f}")
                )
                self.table.setItem(
                    row_idx, 4, QTableWidgetItem(f"${tax or 0:.2f}")
                )
                self.table.setItem(
                    row_idx, 5, QTableWidgetItem(f"${net or 0:.2f}")
                )
                self.table.setItem(
                    row_idx, 6, QTableWidgetItem(f"${reimburse or 0:.2f}")
                )

            print(f"✅ Driver Pay Analysis loaded {len(rows)} drivers")
        except Exception:
            logger.exception("Driver Pay Analysis load error")
            self.table.setRowCount(0)


class EmployeePerformanceMetricsWidget(BaseReportWidget):
    """Employee Performance Metrics - Ratings, quality"""

    def __init__(self, db) -> None:
        columns = [
            {"header": "Vehicle", "key": "vehicle"},
            {"header": "Purchase Price", "key": "purchase_price"},
            {"header": "Loan Payments", "key": "loan_payments"},
            {"header": "Insurance", "key": "insurance"},
            {"header": "Maintenance", "key": "maintenance"},
            {"header": "Fuel", "key": "fuel"},
            {"header": "Total Cost", "key": "total_cost"},
            {"header": "Cost/Mile", "key": "cost_mile"},
        ]
        super().__init__(db, "EmployeePerformanceMetrics", columns)
        self.db = db
        self.init_ui()
        self.load_data()

    def init_ui(self) -> None:
        layout = QVBoxLayout()

        title = QLabel("⭐ Employee Performance Metrics")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            [
                "Employee",
                "Charters Completed",
                "Average Rating",
                "Safety Incidents",
                "Attendance %",
                "Status",
            ]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(5, 80)
        layout.addWidget(self.table)

        self.setLayout(layout)

    def load_data(self) -> None:
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute("""
                    SELECT
                        e.full_name,
                        COUNT(DISTINCT c.charter_id) as charters,
                        CAST(NULL AS NUMERIC(3,2)) as avg_rating,
                        0 as incidents,
                        100 as attendance
                    FROM employees e
                    LEFT JOIN charters c ON c.employee_id = e.employee_id
                    WHERE e.is_chauffeur = true
                        AND e.employment_status = 'active'
                    GROUP BY e.employee_id, e.full_name
                    ORDER BY COUNT(DISTINCT c.charter_id) DESC
                """)

                rows = cur.fetchall()

            self.table.setRowCount(len(rows))

            for row_idx, row in enumerate(rows):
                employee, charters, rating, incidents, attendance = row
                status = (
                    "Excellent"
                    if (rating or 0) >= 4.5
                    else (
                        "Good"
                        if (rating or 0) >= 4
                        else "Fair" if (rating or 0) >= 3 else "Review"
                    )
                )

                self.table.setItem(row_idx, 0, QTableWidgetItem(str(employee)))
                self.table.setItem(
                    row_idx, 1, QTableWidgetItem(str(charters or 0))
                )
                self.table.setItem(
                    row_idx, 2, QTableWidgetItem(f"{rating or 0:.2f}⭐")
                )
                self.table.setItem(
                    row_idx, 3, QTableWidgetItem(str(incidents or 0))
                )
                self.table.setItem(
                    row_idx, 4, QTableWidgetItem(f"{attendance or 0:.0f}%")
                )
                self.table.setItem(row_idx, 5, QTableWidgetItem(status))
        except Exception as e:
            logger.error(f"Failed to load employee performance metrics: {e}")


class PayrollTaxComplianceWidget(BaseReportWidget):
    """Payroll Tax Compliance - T4, CPP/EI, tax tracking"""

    def __init__(self, db) -> None:
        columns = [
            {"header": "Vehicle", "key": "vehicle"},
            {"header": "Purchase Price", "key": "purchase_price"},
            {"header": "Loan Payments", "key": "loan_payments"},
            {"header": "Insurance", "key": "insurance"},
            {"header": "Maintenance", "key": "maintenance"},
            {"header": "Fuel", "key": "fuel"},
            {"header": "Total Cost", "key": "total_cost"},
            {"header": "Cost/Mile", "key": "cost_mile"},
        ]
        super().__init__(db, "PayrollTaxCompliance", columns)
        self.db = db
        self.init_ui()
        self.load_data()

    def init_ui(self) -> None:
        layout = QVBoxLayout()

        title = QLabel("📋 Payroll Tax Compliance")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # Filters
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Tax Year:"))
        year_combo = QComboBox()
        year_combo.addItems([str(y) for y in DASHBOARD_YEARS])
        year_combo.setCurrentText(str(WORKING_YEAR))
        filter_layout.addWidget(year_combo)
        layout.addLayout(filter_layout)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(
            [
                "Employee",
                "Gross Income",
                "CPP Employee",
                "CPP Employer",
                "EI Employee",
                "EI Employer",
                "Income Tax",
                "T4 Status",
            ]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        self.setLayout(layout)

    def load_data(self) -> None:
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT
                        e.full_name,
                        COALESCE(SUM(dp.gross_pay), 0) as gross_income,
                        COALESCE(SUM(dp.cpp), 0) as cpp_emp,
                        COALESCE(SUM(dp.cpp), 0) as cpp_empr,
                         -- Employer match
                        COALESCE(SUM(dp.ei), 0) as ei_emp,
                        COALESCE(SUM(dp.ei), 0) * 1.4 as ei_empr,
                         -- Employer rate higher
                        COALESCE(SUM(dp.tax), 0) as income_tax
                    FROM employees e
                    LEFT JOIN driver_payroll dp ON dp.employee_id =
                    e.employee_id
                        AND EXTRACT(YEAR FROM dp.pay_date) = %s
                    GROUP BY e.employee_id, e.full_name
                    ORDER BY e.full_name
                """,
                    (datetime.now().year,),
                )

                rows = cur.fetchall()

            self.table.setRowCount(len(rows))

            for row_idx, row in enumerate(rows):
                employee, gross, cpp_emp, cpp_empr, ei_emp, ei_empr, tax = row
                t4_status = "Filed" if gross and gross > 0 else "Pending"

                self.table.setItem(row_idx, 0, QTableWidgetItem(str(employee)))
                self.table.setItem(
                    row_idx, 1, QTableWidgetItem(f"${gross or 0:.2f}")
                )
                self.table.setItem(
                    row_idx, 2, QTableWidgetItem(f"${cpp_emp or 0:.2f}")
                )
                self.table.setItem(
                    row_idx, 3, QTableWidgetItem(f"${cpp_empr or 0:.2f}")
                )
                self.table.setItem(
                    row_idx, 4, QTableWidgetItem(f"${ei_emp or 0:.2f}")
                )
                self.table.setItem(
                    row_idx, 5, QTableWidgetItem(f"${ei_empr or 0:.2f}")
                )
                self.table.setItem(
                    row_idx, 6, QTableWidgetItem(f"${tax or 0:.2f}")
                )
                self.table.setItem(row_idx, 7, QTableWidgetItem(t4_status))
        except Exception as e:
            logger.error(f"Failed to load payroll tax compliance: {e}")


class DriverScheduleManagementWidget(BaseReportWidget):
    """Driver Schedule Management - Operational scheduling with active"
    "drivers, charter assignments, gaps, and substitutions"""

    def __init__(self, db) -> None:
        columns = [
            {"header": "Driver", "key": "driver"},
            {"header": "Phone", "key": "phone"},
            {"header": "Status", "key": "status"},
            {"header": "Charters", "key": "charters"},
            {"header": "Available", "key": "available"},
        ]
        super().__init__(db, "DriverScheduleManagement", columns)
        self.db = db

        # Add time filter to existing layout
        existing_layout = self.layout()
        filter_layout = QHBoxLayout()
        self.time_filter = QComboBox()
        self.time_filter.addItems(
            ["Today", "Tomorrow", "This Week", "This Month", "All Upcoming"]
        )
        self.time_filter.currentTextChanged.connect(self.refresh)
        filter_layout.addWidget(QLabel("Show:"))
        filter_layout.addWidget(self.time_filter)
        filter_layout.addStretch()
        existing_layout.insertLayout(1, filter_layout)

    def load_data(self) -> None:
        """Load driver schedule data"""
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                # Determine available employee columns
                cur.execute("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'employees'
                """)
                emp_cols = {r[0] for r in cur.fetchall()}

                if "phone" in emp_cols:
                    phone_sql = "e.phone"
                    phone_group = ", e.phone"
                elif "phone_number" in emp_cols:
                    phone_sql = "e.phone_number"
                    phone_group = ", e.phone_number"
                elif "mobile_phone" in emp_cols:
                    phone_sql = "e.mobile_phone"
                    phone_group = ", e.mobile_phone"
                elif "contact_phone" in emp_cols:
                    phone_sql = "e.contact_phone"
                    phone_group = ", e.contact_phone"
                else:
                    phone_sql = "NULL::text"
                    phone_group = ""

                if "is_active" in emp_cols:
                    active_expr = "e.is_active"
                    _active_cond = "e.is_active = true"
                elif "employment_status" in emp_cols:
                    active_expr = "LOWER(e.employment_status) = 'active'"
                elif "status" in emp_cols:
                    active_expr = "LOWER(e.status) = 'active'"
                else:
                    active_expr = "TRUE"

                if "is_chauffeur" in emp_cols:
                    chauffeur_cond = "e.is_chauffeur = true"
                elif "is_driver" in emp_cols:
                    chauffeur_cond = "e.is_driver = true"
                elif "job_title" in emp_cols:
                    chauffeur_cond = "LOWER(e.job_title) LIKE '%driver%'"
                else:
                    chauffeur_cond = "TRUE"

                # Simple query for active employees
                query = f"""
                    SELECT
                        e.full_name,
                        {phone_sql} AS phone,
                        CASE WHEN {active_expr}
                            THEN 'Active' ELSE 'Inactive' END as status,
                        COUNT(c.charter_id) as charter_count,
                        CASE WHEN {active_expr}
                            THEN 'Yes' ELSE 'No' END as available
                    FROM employees e
                    LEFT JOIN charters c ON c.employee_id = e.employee_id
                        AND c.charter_date >= CURRENT_DATE
                        AND c.status NOT IN ('cancelled')
                    WHERE {chauffeur_cond}
                    GROUP BY e.employee_id, e.full_name{phone_group},
                    {active_expr}
                    ORDER BY e.full_name
                """
                cur.execute(query)

                rows = cur.fetchall()

            self.rows = []
            for row in rows:
                self.rows.append(
                    {
                        "driver": row[0] or "",
                        "phone": row[1] or "",
                        "status": row[2] or "",
                        "charters": str(row[3] or 0),
                        "available": row[4] or "",
                    }
                )

            self._populate_table(self.rows)
        except Exception as e:
            logger.error(f"Failed to load driver schedule: {e}")
            QMessageBox.warning(
                self, "Load Error", f"Failed to load driver schedule: {e}"
            )


# ============================================================================
# PHASE 6: PAYMENTS & FINANCIAL DASHBOARDS (5 widgets)
# ============================================================================


class PaymentReconciliationAdvancedWidget(BaseReportWidget):
    """Payment Reconciliation - Outstanding, by method, NSF tracking"""

    def __init__(self, db) -> None:
        columns = [
            {"header": "Vehicle", "key": "vehicle"},
            {"header": "Purchase Price", "key": "purchase_price"},
            {"header": "Loan Payments", "key": "loan_payments"},
            {"header": "Insurance", "key": "insurance"},
            {"header": "Maintenance", "key": "maintenance"},
            {"header": "Fuel", "key": "fuel"},
            {"header": "Total Cost", "key": "total_cost"},
            {"header": "Cost/Mile", "key": "cost_mile"},
        ]
        super().__init__(db, "PaymentReconciliationAdvanced", columns)
        self.db = db
        self.init_ui()
        self.load_data()

    def init_ui(self) -> None:
        layout = QVBoxLayout()

        title = QLabel("💳 Payment Reconciliation (Advanced)")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # Filters
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Payment Status:"))
        status_combo = QComboBox()
        status_combo.addItems(["All", "Outstanding", "Paid", "NSF", "Partial"])
        filter_layout.addWidget(status_combo)
        layout.addLayout(filter_layout)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(
            [
                "Reserve #",
                "Customer",
                "Amount Due",
                "Payment Method",
                "Payment Date",
                "Amount Paid",
                "Outstanding",
                "Days Overdue",
            ]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 150)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        self.setLayout(layout)

    def load_data(self) -> None:
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute("""
                    SELECT
                        c.reserve_number,
                        COALESCE(cl.client_name,
                        cl.company_name) as customer_name,
                        c.total_amount_due,
                        COALESCE(p.payment_method,
                            'Pending') as payment_method,
                        p.payment_date,
                        COALESCE(SUM(p.amount), 0) as paid_amount,
                        c.total_amount_due - COALESCE(SUM(p.amount),
                        0) as outstanding,
                        (CURRENT_DATE - c.charter_date) as days_overdue
                    FROM charters c
                    LEFT JOIN clients cl ON cl.client_id = c.client_id
                    LEFT JOIN payments p ON p.reserve_number = c.reserve_number
                    GROUP BY c.charter_id, c.reserve_number,
                    c.total_amount_due, c.charter_date,
                             COALESCE(cl.client_name, cl.company_name),
                             p.payment_method, p.payment_date
                    ORDER BY c.reserve_number DESC
                    LIMIT 100
                """)

                rows = cur.fetchall()

            self.table.setRowCount(len(rows))

            for row_idx, row in enumerate(rows):
                (
                    reserve,
                    customer,
                    amount_due,
                    method,
                    pay_date,
                    paid,
                    outstanding,
                    days_over,
                ) = row
                self.table.setItem(row_idx, 0, QTableWidgetItem(str(reserve)))
                self.table.setItem(row_idx, 1, QTableWidgetItem(str(customer)))
                self.table.setItem(
                    row_idx, 2, QTableWidgetItem(f"${amount_due or 0:.2f}")
                )
                self.table.setItem(row_idx, 3, QTableWidgetItem(str(method)))
                self.table.setItem(
                    row_idx, 4, QTableWidgetItem(str(pay_date or ""))
                )
                self.table.setItem(
                    row_idx, 5, QTableWidgetItem(f"${paid or 0:.2f}")
                )
                self.table.setItem(
                    row_idx, 6, QTableWidgetItem(f"${outstanding or 0:.2f}")
                )
                self.table.setItem(
                    row_idx, 7, QTableWidgetItem(str(days_over or 0))
                )

            print(
                f"✅ Customer Payments Dashboard loaded {len(rows)} charters"
            )
        except Exception:
            logger.exception("Customer Payments Dashboard load error")
            self.table.setRowCount(0)


class ARAgingDashboardWidget(BaseReportWidget):
    """AR Aging Dashboard - Past due by days"""

    def __init__(self, db) -> None:
        columns = [
            {"header": "Vehicle", "key": "vehicle"},
            {"header": "Purchase Price", "key": "purchase_price"},
            {"header": "Loan Payments", "key": "loan_payments"},
            {"header": "Insurance", "key": "insurance"},
            {"header": "Maintenance", "key": "maintenance"},
            {"header": "Fuel", "key": "fuel"},
            {"header": "Total Cost", "key": "total_cost"},
            {"header": "Cost/Mile", "key": "cost_mile"},
        ]
        super().__init__(db, "ARAgingDashboard", columns)
        self.db = db
        self.init_ui()
        self.load_data()

    def init_ui(self) -> None:
        layout = QVBoxLayout()

        title = QLabel("📊 Accounts Receivable Aging")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # Stats
        stats_layout = QHBoxLayout()
        stats_layout.addWidget(QLabel("Current: $0.00"))
        stats_layout.addWidget(QLabel("30+ Days: $0.00"))
        stats_layout.addWidget(QLabel("60+ Days: $0.00"))
        stats_layout.addWidget(QLabel("90+ Days: $0.00"))
        layout.addLayout(stats_layout)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            [
                "Customer",
                "Invoice #",
                "Invoice Date",
                "Amount",
                "Age (Days)",
                "Bucket",
            ]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 150)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 120)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(3, 110)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        self.setLayout(layout)

    def load_data(self) -> None:
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute("""
                    SELECT
                        cl.company_name,
                        c.reserve_number,
                        c.charter_date,
                        c.total_amount_due,
                        (CURRENT_DATE - c.charter_date) as days_old,
                        CASE
                            WHEN (CURRENT_DATE - c.charter_date)
                                <= 30 THEN 'Current'
                            WHEN (CURRENT_DATE - c.charter_date)
                                <= 60 THEN '31-60 Days'
                            WHEN (CURRENT_DATE - c.charter_date)
                                <= 90 THEN '61-90 Days'
                            ELSE '90+ Days'
                        END as bucket
                    FROM charters c
                    LEFT JOIN clients cl ON cl.client_id = c.client_id
                    ORDER BY days_old DESC
                    LIMIT 100
                """)

                rows = cur.fetchall() or []

            self.table.setRowCount(len(rows))

            for row_idx, row in enumerate(rows):
                customer, invoice, inv_date, amount, days, bucket = row
                self.table.setItem(row_idx, 0, QTableWidgetItem(str(customer)))
                self.table.setItem(row_idx, 1, QTableWidgetItem(str(invoice)))
                self.table.setItem(row_idx, 2, QTableWidgetItem(str(inv_date)))
                self.table.setItem(
                    row_idx, 3, QTableWidgetItem(f"${amount or 0:.2f}")
                )
                self.table.setItem(
                    row_idx, 4, QTableWidgetItem(str(days or 0))
                )
                self.table.setItem(row_idx, 5, QTableWidgetItem(str(bucket)))
        except Exception as e:
            logger.error(f"Failed to load AR aging dashboard: {e}")


class CashFlowReportWidget(BaseReportWidget):
    """Cash Flow Report - Daily/weekly/monthly"""

    def __init__(self, db) -> None:
        columns = [
            {"header": "Vehicle", "key": "vehicle"},
            {"header": "Purchase Price", "key": "purchase_price"},
            {"header": "Loan Payments", "key": "loan_payments"},
            {"header": "Insurance", "key": "insurance"},
            {"header": "Maintenance", "key": "maintenance"},
            {"header": "Fuel", "key": "fuel"},
            {"header": "Total Cost", "key": "total_cost"},
            {"header": "Cost/Mile", "key": "cost_mile"},
        ]
        super().__init__(db, "CashFlowReport", columns)
        self.db = db
        self.init_ui()
        self.load_data()

    def init_ui(self) -> None:
        layout = QVBoxLayout()

        title = QLabel("💰 Cash Flow Report")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # Filters
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Period:"))
        period_combo = QComboBox()
        period_combo.addItems(["Daily", "Weekly", "Monthly"])
        filter_layout.addWidget(period_combo)
        layout.addLayout(filter_layout)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["Period", "Cash In", "Cash Out", "Net Flow", "Balance"]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(4, 110)
        layout.addWidget(self.table)

        self.setLayout(layout)

    def load_data(self) -> None:
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute("""
                    SELECT
                        DATE_TRUNC('month', c.charter_date)::date as period,
                        COALESCE(SUM(p.amount), 0) as cash_in
                    FROM charters c
                    LEFT JOIN payments p ON p.reserve_number = c.reserve_number
                    GROUP BY DATE_TRUNC('month', c.charter_date)
                    ORDER BY period DESC
                    LIMIT 24
                """)

                rows = cur.fetchall() or []

            self.table.setRowCount(len(rows))

            running_balance = 0
            for row_idx, row in enumerate(rows):
                period, cash_in = row
                cash_out = 0  # Receipts not joined in simplified query
                net_flow = (cash_in or 0) - (cash_out or 0)
                running_balance += net_flow

                self.table.setItem(row_idx, 0, QTableWidgetItem(str(period)))
                self.table.setItem(
                    row_idx, 1, QTableWidgetItem(f"${cash_in or 0:.2f}")
                )
                self.table.setItem(
                    row_idx, 2, QTableWidgetItem(f"${cash_out or 0:.2f}")
                )
                self.table.setItem(
                    row_idx, 3, QTableWidgetItem(f"${net_flow:.2f}")
                )
                self.table.setItem(
                    row_idx, 4, QTableWidgetItem(f"${running_balance:.2f}")
                )
        except Exception as e:
            logger.error(f"Failed to load cash flow report: {e}")


class ProfitLossReportWidget(BaseReportWidget):
    """Profit & Loss Report - Revenue, expenses, net"""

    def __init__(self, db) -> None:
        columns = [
            {"header": "Vehicle", "key": "vehicle"},
            {"header": "Purchase Price", "key": "purchase_price"},
            {"header": "Loan Payments", "key": "loan_payments"},
            {"header": "Insurance", "key": "insurance"},
            {"header": "Maintenance", "key": "maintenance"},
            {"header": "Fuel", "key": "fuel"},
            {"header": "Total Cost", "key": "total_cost"},
            {"header": "Cost/Mile", "key": "cost_mile"},
        ]
        super().__init__(db, "ProfitLossReport", columns)
        self.db = db
        self.init_ui()
        self.load_data()

    def init_ui(self) -> None:
        layout = QVBoxLayout()

        title = QLabel("📊 Profit & Loss Report")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # Filters
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Year:"))
        year_combo = QComboBox()
        year_combo.addItems([str(y) for y in DASHBOARD_YEARS])
        year_combo.setCurrentText(str(WORKING_YEAR))
        filter_layout.addWidget(year_combo)
        layout.addLayout(filter_layout)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(
            ["Category", "Amount", "% of Revenue"]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 110)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        self.setLayout(layout)

    def load_data(self) -> None:
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT COALESCE(SUM(total_amount_due), 0) as total_revenue
                    FROM charters
                    WHERE EXTRACT(YEAR FROM charter_date) = %s
                """,
                    (datetime.now().year,),
                )

                row = cur.fetchone()
                revenue = row[0] if row else 0

                cur.execute(
                    """
                    SELECT
                        COALESCE(SUM(CASE WHEN category = 'Fuel'
                            THEN gross_amount ELSE 0 END), 0) as fuel,
                        COALESCE(SUM(CASE WHEN category = 'Maintenance'
                            THEN gross_amount ELSE 0 END), 0) as maintenance,
                        COALESCE(SUM(CASE WHEN category = 'Insurance'
                            THEN gross_amount ELSE 0 END), 0) as insurance
                    FROM receipts
                    WHERE EXTRACT(YEAR FROM receipt_date) = %s
                """,
                    (datetime.now().year,),
                )

                row2 = cur.fetchone()
                fuel, maintenance, insurance = row2 if row2 else (0, 0, 0)

                cur.execute(
                    """
                    SELECT COALESCE(SUM(gross_pay), 0) as payroll
                    FROM driver_payroll
                    WHERE EXTRACT(YEAR FROM pay_date) = %s
                """,
                    (datetime.now().year,),
                )

                row3 = cur.fetchone()
                payroll = row3[0] if row3 else 0

            self.table.setRowCount(6)

            # Revenue
            self.table.setItem(0, 0, QTableWidgetItem("Revenue"))
            self.table.setItem(0, 1, QTableWidgetItem(f"${revenue or 0:.2f}"))
            self.table.setItem(0, 2, QTableWidgetItem("100%"))

            # Expenses
            expenses_list = [
                ("Fuel", fuel or 0),
                ("Maintenance", maintenance or 0),
                ("Insurance", insurance or 0),
                ("Payroll", payroll or 0),
            ]

            for idx, (name, amount) in enumerate(expenses_list, start=1):
                pct = (amount / (revenue or 1)) * 100 if revenue else 0
                self.table.setItem(idx, 0, QTableWidgetItem(name))
                self.table.setItem(idx, 1, QTableWidgetItem(f"${amount:.2f}"))
                self.table.setItem(idx, 2, QTableWidgetItem(f"{pct:.1f}%"))

            # Net Profit
            total_expenses = (
                (fuel or 0)
                + (maintenance or 0)
                + (insurance or 0)
                + (payroll or 0)
            )
            net_profit = (revenue or 0) - total_expenses
            net_pct = (net_profit / (revenue or 1)) * 100 if revenue else 0

            self.table.setItem(5, 0, QTableWidgetItem("Net Profit"))
            self.table.setItem(5, 1, QTableWidgetItem(f"${net_profit:.2f}"))
            self.table.setItem(5, 2, QTableWidgetItem(f"{net_pct:.1f}%"))

            print("✅ Profit & Loss Dashboard loaded")
        except Exception:
            logger.exception("Profit & Loss Dashboard load error")
            self.table.setRowCount(0)


class CharterAnalyticsAdvancedWidget(BaseReportWidget):
    """Charter Analytics (Advanced) - Volume trends, revenue, cancellations"""

    def __init__(self, db) -> None:
        columns = [
            {"header": "Vehicle", "key": "vehicle"},
            {"header": "Purchase Price", "key": "purchase_price"},
            {"header": "Loan Payments", "key": "loan_payments"},
            {"header": "Insurance", "key": "insurance"},
            {"header": "Maintenance", "key": "maintenance"},
            {"header": "Fuel", "key": "fuel"},
            {"header": "Total Cost", "key": "total_cost"},
            {"header": "Cost/Mile", "key": "cost_mile"},
        ]
        super().__init__(db, "CharterAnalyticsAdvanced", columns)
        self.db = db
        self.init_ui()
        self.load_data()

    def init_ui(self) -> None:
        layout = QVBoxLayout()

        title = QLabel("📈 Charter Analytics (Advanced)")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            [
                "Month",
                "Total Charters",
                "Revenue",
                "Avg Charter Value",
                "Cancellations",
                "Cancellation %",
                "Utilization %",
            ]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2, 110)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        self.setLayout(layout)

    def load_data(self) -> None:
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute("""
                    SELECT
                        DATE_TRUNC('month', c.charter_date)::date as month,
                        COUNT(*) as total_charters,
                        COALESCE(SUM(c.total_amount_due), 0) as revenue,
                        COALESCE(AVG(c.total_amount_due), 0) as avg_value,
                        SUM(CASE WHEN c.status = 'Cancelled'
                            THEN 1 ELSE 0 END) as cancellations
                    FROM charters c
                    GROUP BY DATE_TRUNC('month', c.charter_date)
                    ORDER BY month DESC
                    LIMIT 24
                """)

                rows = cur.fetchall() or []

            self.table.setRowCount(len(rows))

            for row_idx, row in enumerate(rows):
                month, total, revenue, avg_value, cancellations = row
                cancellation_pct = (
                    (cancellations / total * 100) if total > 0 else 0
                )
                # Assume 30 days per month
                utilization = (total / 30) * 100 if total > 0 else 0

                self.table.setItem(row_idx, 0, QTableWidgetItem(str(month)))
                self.table.setItem(
                    row_idx, 1, QTableWidgetItem(str(total or 0))
                )
                self.table.setItem(
                    row_idx, 2, QTableWidgetItem(f"${revenue or 0:.2f}")
                )
                self.table.setItem(
                    row_idx, 3, QTableWidgetItem(f"${avg_value or 0:.2f}")
                )
                self.table.setItem(
                    row_idx, 4, QTableWidgetItem(str(cancellations or 0))
                )
                self.table.setItem(
                    row_idx, 5, QTableWidgetItem(f"{cancellation_pct:.1f}%")
                )
                self.table.setItem(
                    row_idx, 6, QTableWidgetItem(f"{utilization:.1f}%")
                )
        except Exception as e:
            logger.error(f"Failed to load charter analytics: {e}")
