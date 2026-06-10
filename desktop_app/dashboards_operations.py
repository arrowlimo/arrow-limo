"""
Consolidated Dashboard - Operations
Combines Phase 4-6 Payroll/Finance (10) + Phase 7-8 (16) = 26 operations
widgets
"""

from dashboards_phase4_5_6 import (
    ARAgingDashboardWidget,
    CashFlowReportWidget,
    CharterAnalyticsAdvancedWidget,
    DriverPayAnalysisWidget,
    DriverScheduleManagementWidget,
    EmployeePerformanceMetricsWidget,
    PaymentReconciliationAdvancedWidget,
    PayrollTaxComplianceWidget,
    ProfitLossReportWidget,
)
from dashboards_phase7_8 import (
    AdvancedMaintenanceScheduleWidget,
    BookingLeadTimeAnalysisWidget,
    CharterCancellationAnalysisWidget,
    CharterManagementDashboardWidget,
    CustomerLifetimeValueWidget,
    CustomerSegmentationWidget,
    DataQualityAuditWidget,
    GeographicRevenueDistributionWidget,
    HosComplianceTrackingWidget,
    RealTimeFleetMonitoringWidget,
    RouteProfitabilityWidget,
    SafetyIncidentTrackingWidget,
    SystemHealthDashboardWidget,
    VendorPerformanceWidget,
)

__all__ = [
    # Phase 4-6 Payroll/Finance (9)
    "DriverPayAnalysisWidget",
    "EmployeePerformanceMetricsWidget",
    "PayrollTaxComplianceWidget",
    "DriverScheduleManagementWidget",
    "PaymentReconciliationAdvancedWidget",
    "ARAgingDashboardWidget",
    "CashFlowReportWidget",
    "ProfitLossReportWidget",
    "CharterAnalyticsAdvancedWidget",
    # Phase 7-8 (16)
    "CharterManagementDashboardWidget",
    "CustomerLifetimeValueWidget",
    "CharterCancellationAnalysisWidget",
    "BookingLeadTimeAnalysisWidget",
    "CustomerSegmentationWidget",
    "RouteProfitabilityWidget",
    "GeographicRevenueDistributionWidget",
    "HosComplianceTrackingWidget",
    "AdvancedMaintenanceScheduleWidget",
    "SafetyIncidentTrackingWidget",
    "VendorPerformanceWidget",
    "RealTimeFleetMonitoringWidget",
    "SystemHealthDashboardWidget",
    "DataQualityAuditWidget",
]
