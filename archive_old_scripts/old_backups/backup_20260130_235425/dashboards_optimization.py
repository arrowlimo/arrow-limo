"""
Consolidated Dashboard - Optimization
Combines Phase 11 (12) + Phase 12 (15) = 27 scheduling & multi-property optimization widgets
"""

from dashboards_phase11 import (
    DriverShiftOptimizationWidget,
    RouteSchedulingWidget,
    VehicleAssignmentPlannerWidget,
    CalendarForecasitngWidget,
    BreakComplianceScheduleWidget,
    MaintenanceSchedulingWidget,
    CrewRotationAnalysisWidget,
    LoadBalancingOptimizerWidget,
    DynamicPricingScheduleWidget,
    HistoricalSchedulingPatternsWidget,
    PredictiveSchedulingWidget,
    CapacityUtilizationWidget
)

from dashboards_phase12 import (
    BranchLocationConsolidationWidget,
    InterBranchPerformanceComparisonWidget,
    ConsolidatedProfitLossWidget,
    ResourceAllocationAcrossPropertiesWidget,
    CrossBranchCharteringWidget,
    SharedVehicleTrackingWidget,
    UnifiedInventoryManagementWidget,
    MultiLocationPayrollWidget,
    TerritoryMappingWidget,
    MarketOverlapAnalysisWidget,
    RegionalPerformanceMetricsWidget,
    PropertyLevelKPIWidget,
    FranchiseIntegrationWidget,
    LicenseTrackingWidget,
    OperationsConsolidationWidget
)

__all__ = [
    # Phase 11 Scheduling (12)
    'DriverShiftOptimizationWidget',
    'RouteSchedulingWidget',
    'VehicleAssignmentPlannerWidget',
    'CalendarForecasitngWidget',
    'BreakComplianceScheduleWidget',
    'MaintenanceSchedulingWidget',
    'CrewRotationAnalysisWidget',
    'LoadBalancingOptimizerWidget',
    'DynamicPricingScheduleWidget',
    'HistoricalSchedulingPatternsWidget',
    'PredictiveSchedulingWidget',
    'CapacityUtilizationWidget',
    
    # Phase 12 Multi-Property (15)
    'BranchLocationConsolidationWidget',
    'InterBranchPerformanceComparisonWidget',
    'ConsolidatedProfitLossWidget',
    'ResourceAllocationAcrossPropertiesWidget',
    'CrossBranchCharteringWidget',
    'SharedVehicleTrackingWidget',
    'UnifiedInventoryManagementWidget',
    'MultiLocationPayrollWidget',
    'TerritoryMappingWidget',
    'MarketOverlapAnalysisWidget',
    'RegionalPerformanceMetricsWidget',
    'PropertyLevelKPIWidget',
    'FranchiseIntegrationWidget',
    'LicenseTrackingWidget',
    'OperationsConsolidationWidget',
]
