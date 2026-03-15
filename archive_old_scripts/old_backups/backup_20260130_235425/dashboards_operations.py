"""
Consolidated Dashboard - Operations
Combines Phase 4-6 Payroll/Finance (10) + Phase 7-8 (16) = 26 operations widgets
"""

from dashboards_phase4_5_6 import (
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

from dashboards_phase7_8 import (
    CharterManagementDashboardWidget,
    CustomerLifetimeValueWidget,
    CharterCancellationAnalysisWidget,
    BookingLeadTimeAnalysisWidget,
    CustomerSegmentationWidget,
    RouteProfitabilityWidget,
    GeographicRevenueDistributionWidget,
    HosComplianceTrackingWidget,
    AdvancedMaintenanceScheduleWidget,
    SafetyIncidentTrackingWidget,
    VendorPerformanceWidget,
    RealTimeFleetMonitoringWidget,
    SystemHealthDashboardWidget,
    DataQualityAuditWidget
)

__all__ = [
    # Phase 4-6 Payroll/Finance (9)
    'DriverPayAnalysisWidget',
    'EmployeePerformanceMetricsWidget',
    'PayrollTaxComplianceWidget',
    'DriverScheduleManagementWidget',
    'PaymentReconciliationAdvancedWidget',
    'ARAgingDashboardWidget',
    'CashFlowReportWidget',
    'ProfitLossReportWidget',
    'CharterAnalyticsAdvancedWidget',
    
    # Phase 7-8 (16)
    'CharterManagementDashboardWidget',
    'CustomerLifetimeValueWidget',
    'CharterCancellationAnalysisWidget',
    'BookingLeadTimeAnalysisWidget',
    'CustomerSegmentationWidget',
    'RouteProfitabilityWidget',
    'GeographicRevenueDistributionWidget',
    'HosComplianceTrackingWidget',
    'AdvancedMaintenanceScheduleWidget',
    'SafetyIncidentTrackingWidget',
    'VendorPerformanceWidget',
    'RealTimeFleetMonitoringWidget',
    'SystemHealthDashboardWidget',
    'DataQualityAuditWidget',
]
