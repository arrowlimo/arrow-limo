"""
Report Explorer - lightweight query/report menu with search and tree navigation.
"""

from pathlib import Path
import json

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
)
from PyQt6.QtCore import Qt, pyqtSignal


DEFAULT_REPORTS = [
    {
        "domain": "Finance",
        "category": "Collections",
        "name": "Payment Reconciliation",
        "class_name": "PaymentReconciliationWidget",
    },
    {
        "domain": "Finance",
        "category": "Summary",
        "name": "Financial Dashboard",
        "class_name": "FinancialDashboardWidget",
    },
    {
        "domain": "Finance",
        "category": "Accounting",
        "name": "Trial Balance",
        "class_name": "TrialBalanceWidget",
    },
    {
        "domain": "Finance",
        "category": "Accounting",
        "name": "Journal Explorer",
        "class_name": "JournalExplorerWidget",
    },
    {
        "domain": "Finance",
        "category": "Accounting",
        "name": "Bank Reconciliation",
        "class_name": "BankReconciliationWidget",
    },
    {
        "domain": "Finance",
        "category": "Accounting",
        "name": "Profit & Loss",
        "class_name": "PLSummaryWidget",
    },
    {
        "domain": "Finance",
        "category": "Accounting",
        "name": "P&L by Category",
        "class_name": "PLCategoryWidget",
    },
    {
        "domain": "Finance",
        "category": "Fleet",
        "name": "Vehicle Performance",
        "class_name": "VehiclePerformanceWidget",
    },
    {
        "domain": "Finance",
        "category": "Fleet",
        "name": "Fleet Maintenance",
        "class_name": "FleetMaintenanceWidget",
    },
    {
        "domain": "Finance",
        "category": "Fleet",
        "name": "Vehicle Insurance (Yearly)",
        "class_name": "VehicleInsuranceWidget",
    },
    {
        "domain": "Finance",
        "category": "Fleet",
        "name": "Vehicle Damage Summary",
        "class_name": "VehicleDamageWidget",
    },
    {
        "domain": "Finance",
        "category": "Payroll",
        "name": "Driver Monthly Cost",
        "class_name": "DriverMonthlyCostWidget",
    },
    {
        "domain": "Finance",
        "category": "Payroll",
        "name": "Driver Revenue vs Pay",
        "class_name": "DriverRevenueVsPayWidget",
    },
    {
        "domain": "Finance",
        "category": "Banking",
        "name": "Bank Rec Suggestions",
        "class_name": "BankRecSuggestionsWidget",
    },
    {
        "domain": "Finance",
        "category": "Payroll",
        "name": "Driver Cost",
        "class_name": "DriverCostWidget",
    },
    {
        "domain": "Operations",
        "category": "Fleet",
        "name": "Fleet Management",
        "class_name": "FleetManagementWidget",
    },
    {
        "domain": "Employees",
        "category": "Performance",
        "name": "Driver Performance",
        "class_name": "DriverPerformanceWidget",
    },
]


class ReportExplorerWidget(QWidget):
    """Simple report/query explorer for curated widgets."""

    report_selected = pyqtSignal(str, str)  # class_name, display_name

    def __init__(self, menu_file: Path | None = None):
        super().__init__()
        self.menu_file = menu_file or Path(__file__).parent / "report_menu.json"
        self.reports = self._load_reports()
        self.tree_items = []

        layout = QVBoxLayout()
        layout.addLayout(self._build_search_bar())
        layout.addWidget(self._build_tree())
        self.setLayout(layout)

    def _load_reports(self):
        if self.menu_file.exists():
            try:
                with open(self.menu_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
            except Exception:
                pass
        return DEFAULT_REPORTS

    def _build_search_bar(self):
        bar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search reports...")
        self.search_input.textChanged.connect(self._filter_tree)
        bar.addWidget(QLabel("🔍"))
        bar.addWidget(self.search_input)
        return bar

    def _build_tree(self):
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Reports")
        self.tree.itemDoubleClicked.connect(self._on_activate)
        self._populate_tree()
        return self.tree

    def _populate_tree(self):
        self.tree.clear()
        self.tree_items = []

        # Group by domain/category
        domains = {}
        for rpt in self.reports:
            domain = rpt.get("domain", "Misc")
            category = rpt.get("category", "General")
            name = rpt.get("name", "Report")
            class_name = rpt.get("class_name", "")

            if domain not in domains:
                domains[domain] = QTreeWidgetItem([domain])
                domains[domain].setData(0, Qt.ItemDataRole.UserRole, {"type": "domain"})
                self.tree.addTopLevelItem(domains[domain])

            cats = domains[domain].data(0, Qt.ItemDataRole.UserRole + 1) or {}
            if category not in cats:
                cat_item = QTreeWidgetItem([category])
                cat_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "category"})
                domains[domain].addChild(cat_item)
                cats[category] = cat_item
                domains[domain].setData(0, Qt.ItemDataRole.UserRole + 1, cats)
            else:
                cat_item = cats[category]

            rpt_item = QTreeWidgetItem([name])
            rpt_item.setData(0, Qt.ItemDataRole.UserRole, {
                "type": "report",
                "class_name": class_name,
                "display_name": name,
            })
            cat_item.addChild(rpt_item)
            self.tree_items.append(rpt_item)

        self.tree.expandAll()

    def _filter_tree(self):
        text = (self.search_input.text() or "").lower()
        for item in self.tree_items:
            meta = item.data(0, Qt.ItemDataRole.UserRole) or {}
            display = meta.get("display_name", "").lower()
            hidden = text not in display if text else False
            item.setHidden(hidden)
            # Show parents if child visible
            parent = item.parent()
            if parent and not hidden:
                parent.setHidden(False)
                grand = parent.parent()
                if grand:
                    grand.setHidden(False)

    def _on_activate(self, item, _column):
        meta = item.data(0, Qt.ItemDataRole.UserRole) or {}
        if meta.get("type") == "report":
            cls = meta.get("class_name")
            name = meta.get("display_name")
            if cls and name:
                self.report_selected.emit(cls, name)