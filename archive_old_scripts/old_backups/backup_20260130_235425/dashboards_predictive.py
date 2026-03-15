"""
Consolidated Dashboard - Predictive Analytics & Real-Time
Combines Phase 9 (15) + Phase 10 (13) = 28 predictive/real-time widgets
"""

from dashboards_phase9 import (
    DemandForecastingWidget,
    ChurnPredictionWidget,
    RevenueOptimizationWidget,
    CustomerWorthWidget,
    NextBestActionWidget,
    SeasonalityAnalysisWidget,
    CostBehaviorAnalysisWidget,
    BreakEvenAnalysisWidget,
    EmailCampaignPerformanceWidget,
    CustomerJourneyAnalysisWidget,
    CompetitiveIntelligenceWidget,
    RegulatoryComplianceTrackingWidget,
    CRAComplianceReportWidget,
    EmployeeProductivityTrackingWidget,
    PromotionalEffectivenessWidget
)

from dashboards_phase10 import (
    RealTimeFleetTrackingMapWidget,
    LiveDispatchMonitorWidget,
    MobileCustomerPortalWidget,
    MobileDriverDashboardWidget,
    APIEndpointPerformanceWidget,
    ThirdPartyIntegrationMonitorWidget,
    AdvancedTimeSeriesChartWidget,
    InteractiveHeatmapWidget,
    ComparativeAnalysisChartWidget,
    DistributionAnalysisChartWidget,
    CorrelationMatrixWidget,
    AutomationWorkflowsWidget,
    AlertManagementWidget
)

__all__ = [
    # Phase 9 Predictive (15)
    'DemandForecastingWidget',
    'ChurnPredictionWidget',
    'RevenueOptimizationWidget',
    'CustomerWorthWidget',
    'NextBestActionWidget',
    'SeasonalityAnalysisWidget',
    'CostBehaviorAnalysisWidget',
    'BreakEvenAnalysisWidget',
    'EmailCampaignPerformanceWidget',
    'CustomerJourneyAnalysisWidget',
    'CompetitiveIntelligenceWidget',
    'RegulatoryComplianceTrackingWidget',
    'CRAComplianceReportWidget',
    'EmployeeProductivityTrackingWidget',
    'PromotionalEffectivenessWidget',
    
    # Phase 10 Real-Time (13)
    'RealTimeFleetTrackingMapWidget',
    'LiveDispatchMonitorWidget',
    'MobileCustomerPortalWidget',
    'MobileDriverDashboardWidget',
    'APIEndpointPerformanceWidget',
    'ThirdPartyIntegrationMonitorWidget',
    'AdvancedTimeSeriesChartWidget',
    'InteractiveHeatmapWidget',
    'ComparativeAnalysisChartWidget',
    'DistributionAnalysisChartWidget',
    'CorrelationMatrixWidget',
    'AutomationWorkflowsWidget',
    'AlertManagementWidget',
]
