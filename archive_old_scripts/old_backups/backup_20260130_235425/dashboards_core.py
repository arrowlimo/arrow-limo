"""
Consolidated Dashboard - Core
Combines Phases 1-3 (11) + Phase 4-6 Fleet (5) = 16 core widgets
"""

# Import all widgets from original phases
from dashboards_phase2_phase3 import (
    VehicleAnalyticsWidget,
    EmployeePayrollAuditWidget,
    QuickBooksReconciliationWidget,
    CharterAnalyticsWidget,
    ComplianceTrackingWidget,
    BudgetAnalysisWidget,
    InsuranceTrackingWidget
)

from dashboards_phase4_5_6 import (
    VehicleFleetCostAnalysisWidget,
    VehicleMaintenanceTrackingWidget,
    FuelEfficiencyTrackingWidget,
    VehicleUtilizationWidget,
    FleetAgeAnalysisWidget,
    DriverPayAnalysisWidget,
    EmployeePerformanceMetricsWidget,
    PayrollTaxComplianceWidget,
    DriverScheduleManagementWidget,
    PaymentReconciliationAdvancedWidget,
    ARAgingDashboardWidget,
    CashFlowReportWidget,
    ProfitLossReportWidget,
    CharterAnalyticsAdvancedWidget
)

from dashboard_classes import (
    FleetManagementWidget,
    DriverPerformanceWidget,
    FinancialDashboardWidget,
    PaymentReconciliationWidget
)

# Re-export all for consolidation
__all__ = [
    # From dashboard_classes (4)
    'FleetManagementWidget',
    'DriverPerformanceWidget',
    'FinancialDashboardWidget',
    'PaymentReconciliationWidget',
    
    # From dashboards_phase2_phase3 (7)
    'VehicleAnalyticsWidget',
    'EmployeePayrollAuditWidget',
    'QuickBooksReconciliationWidget',
    'CharterAnalyticsWidget',
    'ComplianceTrackingWidget',
    'BudgetAnalysisWidget',
    'InsuranceTrackingWidget',
    
    # From dashboards_phase4_5_6 Fleet only (5)
    'VehicleFleetCostAnalysisWidget',
    'VehicleMaintenanceTrackingWidget',
    'FuelEfficiencyTrackingWidget',
    'VehicleUtilizationWidget',
    'FleetAgeAnalysisWidget',
]
