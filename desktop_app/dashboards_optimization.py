"""
Consolidated Dashboard - Optimization
Combines Phase 11 (12) + Phase 12 (15) = 27 scheduling & multi-property
optimization widgets
"""

from dashboards_phase11 import (
    BreakComplianceScheduleWidget,
    CalendarForecasitngWidget,
    CapacityUtilizationWidget,
    CrewRotationAnalysisWidget,
    DriverShiftOptimizationWidget,
    DynamicPricingScheduleWidget,
    HistoricalSchedulingPatternsWidget,
    LoadBalancingOptimizerWidget,
    MaintenanceSchedulingWidget,
    PredictiveSchedulingWidget,
    RouteSchedulingWidget,
    VehicleAssignmentPlannerWidget,
)
from dashboards_phase12 import (
    BranchLocationConsolidationWidget,
    ConsolidatedProfitLossWidget,
    CrossBranchCharteringWidget,
    FranchiseIntegrationWidget,
    InterBranchPerformanceComparisonWidget,
    LicenseTrackingWidget,
    MarketOverlapAnalysisWidget,
    MultiLocationPayrollWidget,
    OperationsConsolidationWidget,
    PropertyLevelKPIWidget,
    RegionalPerformanceMetricsWidget,
    ResourceAllocationAcrossPropertiesWidget,
    SharedVehicleTrackingWidget,
    TerritoryMappingWidget,
    UnifiedInventoryManagementWidget,
)

__all__ = [
    # Phase 11 Scheduling (12)
    "DriverShiftOptimizationWidget",
    "RouteSchedulingWidget",
    "VehicleAssignmentPlannerWidget",
    "CalendarForecasitngWidget",
    "BreakComplianceScheduleWidget",
    "MaintenanceSchedulingWidget",
    "CrewRotationAnalysisWidget",
    "LoadBalancingOptimizerWidget",
    "DynamicPricingScheduleWidget",
    "HistoricalSchedulingPatternsWidget",
    "PredictiveSchedulingWidget",
    "CapacityUtilizationWidget",
    # Phase 12 Multi-Property (15)
    "BranchLocationConsolidationWidget",
    "InterBranchPerformanceComparisonWidget",
    "ConsolidatedProfitLossWidget",
    "ResourceAllocationAcrossPropertiesWidget",
    "CrossBranchCharteringWidget",
    "SharedVehicleTrackingWidget",
    "UnifiedInventoryManagementWidget",
    "MultiLocationPayrollWidget",
    "TerritoryMappingWidget",
    "MarketOverlapAnalysisWidget",
    "RegionalPerformanceMetricsWidget",
    "PropertyLevelKPIWidget",
    "FranchiseIntegrationWidget",
    "LicenseTrackingWidget",
    "OperationsConsolidationWidget",
]
