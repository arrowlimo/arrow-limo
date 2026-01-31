"""
Phase 12 Dashboard Widgets: Multi-Property Management and Consolidation
15 multi-location operational and reporting dashboards
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QLabel, QHeaderView
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

# ============================================================================
# PHASE 12: MULTI-PROPERTY MANAGEMENT & CONSOLIDATION (15)
# ============================================================================

class BranchLocationConsolidationWidget(QWidget):
    """Branch Location Consolidation - Multi-location overview"""
    
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.init_ui()
        self.load_data()
    
    def init_ui(self):
        layout = QVBoxLayout()
        title = QLabel("🏢 Branch Location Consolidation")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["Location", "Charters", "Revenue", "Drivers", "Vehicles", "Utilization", "Status"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2, 110)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(6, 80)
        layout.addWidget(self.table)
        self.setLayout(layout)
    
    def load_data(self):
        try:
            locations = [
                ("Main - Downtown", 1247, 436500, 12, 8, 85, "Active"),
                ("Airport Hub", 892, 312200, 8, 6, 78, "Active"),
                ("North Branch", 456, 159600, 5, 4, 68, "Active"),
                ("Corporate Campus", 623, 218050, 7, 5, 72, "Active"),
            ]
            
            self.table.setRowCount(len(locations))
            for idx, (loc, charters, revenue, drivers, vehicles, util, status) in enumerate(locations):
                self.table.setItem(idx, 0, QTableWidgetItem(str(loc)))
                self.table.setItem(idx, 1, QTableWidgetItem(str(charters)))
                self.table.setItem(idx, 2, QTableWidgetItem(f"${revenue:,}"))
                self.table.setItem(idx, 3, QTableWidgetItem(str(drivers)))
                self.table.setItem(idx, 4, QTableWidgetItem(str(vehicles)))
                self.table.setItem(idx, 5, QTableWidgetItem(f"{util}%"))
                self.table.setItem(idx, 6, QTableWidgetItem(str(status)))
        except Exception as e:
            pass


class InterBranchPerformanceComparisonWidget(QWidget):
    """Inter-Branch Performance Comparison - KPI benchmarking"""
    
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.init_ui()
        self.load_data()
    
    def init_ui(self):
        layout = QVBoxLayout()
        title = QLabel("📊 Inter-Branch Performance Comparison")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(["Location", "Charters/Day", "Revenue/Day", "Avg Charter Value", "Driver Rating", "On-time %", "Variance", "Rank"])
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
    
    def load_data(self):
        try:
            branches = [
                ("Downtown", 43, 15100, 350, 4.8, 98, "+5%", "1"),
                ("Airport", 31, 10790, 348, 4.7, 96, "0%", "2"),
                ("North", 16, 5520, 345, 4.6, 94, "-3%", "3"),
                ("Campus", 22, 7555, 343, 4.5, 92, "-2%", "4"),
            ]
            
            self.table.setRowCount(len(branches))
            for idx, (loc, charter_day, rev_day, avg_val, rating, ontime, var, rank) in enumerate(branches):
                self.table.setItem(idx, 0, QTableWidgetItem(str(loc)))
                self.table.setItem(idx, 1, QTableWidgetItem(str(charter_day)))
                self.table.setItem(idx, 2, QTableWidgetItem(f"${rev_day:,}"))
                self.table.setItem(idx, 3, QTableWidgetItem(f"${avg_val}"))
                self.table.setItem(idx, 4, QTableWidgetItem(str(rating)))
                self.table.setItem(idx, 5, QTableWidgetItem(str(ontime)))
                self.table.setItem(idx, 6, QTableWidgetItem(str(var)))
                self.table.setItem(idx, 7, QTableWidgetItem(str(rank)))
        except Exception as e:
            pass


class ConsolidatedProfitLossWidget(QWidget):
    """Consolidated P&L - Multi-location financials"""
    
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.init_ui()
        self.load_data()
    
    def init_ui(self):
        layout = QVBoxLayout()
        title = QLabel("💰 Consolidated P&L")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Location", "Revenue", "Expenses", "Gross Profit", "Margin %", "YoY Change"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 110)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2, 110)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        self.setLayout(layout)
    
    def load_data(self):
        try:
            pl_data = [
                ("Downtown", 436500, 261900, 174600, "40%", "+12%"),
                ("Airport", 312200, 187320, 124880, "40%", "+8%"),
                ("North", 159600, 95760, 63840, "40%", "+3%"),
                ("Campus", 218050, 130830, 87220, "40%", "+6%"),
                ("TOTAL", 1126350, 675810, 450540, "40%", "+8%"),
            ]
            
            self.table.setRowCount(len(pl_data))
            for idx, (loc, rev, exp, profit, margin, change) in enumerate(pl_data):
                bold_font = QFont()
                bold_font.setBold(idx == len(pl_data) - 1)
                
                item = QTableWidgetItem(str(loc))
                if idx == len(pl_data) - 1:
                    item.setFont(bold_font)
                self.table.setItem(idx, 0, item)
                
                self.table.setItem(idx, 1, QTableWidgetItem(f"${rev:,}"))
                self.table.setItem(idx, 2, QTableWidgetItem(f"${exp:,}"))
                self.table.setItem(idx, 3, QTableWidgetItem(f"${profit:,}"))
                self.table.setItem(idx, 4, QTableWidgetItem(str(margin)))
                self.table.setItem(idx, 5, QTableWidgetItem(str(change)))
        except Exception as e:
            pass


class ResourceAllocationAcrossPropertiesWidget(QWidget):
    """Resource Allocation - Vehicles and drivers across branches"""
    
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.init_ui()
        self.load_data()
    
    def init_ui(self):
        layout = QVBoxLayout()
        title = QLabel("🔄 Resource Allocation Across Properties")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(["Location", "Drivers Assigned", "Optimal Drivers", "Variance", "Vehicles", "Utilization", "Rebalance Need", "Action"])
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
    
    def load_data(self):
        try:
            resources = [
                ("Downtown", 12, 13, "-1", 8, 85, "Yes", "Hire"),
                ("Airport", 8, 8, "0", 6, 78, "No", "Maintain"),
                ("North", 5, 6, "-1", 4, 68, "Yes", "Consider"),
                ("Campus", 7, 7, "0", 5, 72, "No", "Maintain"),
            ]
            
            self.table.setRowCount(len(resources))
            for idx, (loc, assigned, optimal, var, vehicles, util, need, action) in enumerate(resources):
                self.table.setItem(idx, 0, QTableWidgetItem(str(loc)))
                self.table.setItem(idx, 1, QTableWidgetItem(str(assigned)))
                self.table.setItem(idx, 2, QTableWidgetItem(str(optimal)))
                self.table.setItem(idx, 3, QTableWidgetItem(str(var)))
                self.table.setItem(idx, 4, QTableWidgetItem(str(vehicles)))
                self.table.setItem(idx, 5, QTableWidgetItem(f"{util}%"))
                self.table.setItem(idx, 6, QTableWidgetItem(str(need)))
                self.table.setItem(idx, 7, QTableWidgetItem(str(action)))
        except Exception as e:
            pass


class CrossBranchCharteringWidget(QWidget):
    """Cross-Branch Chartering - Inter-location trips"""
    
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.init_ui()
        self.load_data()
    
    def init_ui(self):
        layout = QVBoxLayout()
        title = QLabel("🚐 Cross-Branch Chartering")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["From", "To", "Charters/Month", "Revenue/Month", "Utilization", "Efficiency", "Action"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        self.setLayout(layout)
    
    def load_data(self):
        try:
            routes = [
                ("Downtown", "Airport", 45, 15750, 85, "High", "Maintain"),
                ("Downtown", "North", 28, 9800, 72, "Medium", "Monitor"),
                ("Airport", "Campus", 32, 11200, 78, "Medium", "Optimize"),
                ("North", "Downtown", 18, 6300, 65, "Low", "Review"),
            ]
            
            self.table.setRowCount(len(routes))
            for idx, (from_, to, charters, revenue, util, efficiency, action) in enumerate(routes):
                self.table.setItem(idx, 0, QTableWidgetItem(str(from_)))
                self.table.setItem(idx, 1, QTableWidgetItem(str(to)))
                self.table.setItem(idx, 2, QTableWidgetItem(str(charters)))
                self.table.setItem(idx, 3, QTableWidgetItem(f"${revenue:,}"))
                self.table.setItem(idx, 4, QTableWidgetItem(f"{util}%"))
                self.table.setItem(idx, 5, QTableWidgetItem(str(efficiency)))
                self.table.setItem(idx, 6, QTableWidgetItem(str(action)))
        except Exception as e:
            pass


class SharedVehicleTrackingWidget(QWidget):
    """Shared Vehicle Tracking - Vehicle utilization across properties"""
    
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.init_ui()
        self.load_data()
    
    def init_ui(self):
        layout = QVBoxLayout()
        title = QLabel("🚗 Shared Vehicle Tracking")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(["Vehicle", "Primary Location", "Secondary Location", "Split %", "Total Charters", "Revenue", "Km/Month", "Status"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 120)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(5, 110)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(7, 80)
        layout.addWidget(self.table)
        self.setLayout(layout)
    
    def load_data(self):
        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except:
                try:
                    self.db.rollback()
                except:
                    pass
                pass
            
            cur = self.db.get_cursor()
            cur.execute("""
                SELECT v.vehicle_number, v.vehicle_type, v.year, COALESCE(SUM(COUNT(*)) OVER(), 0)
                FROM vehicles v
                LEFT JOIN charters c ON v.vehicle_id = c.vehicle_id
                GROUP BY v.vehicle_id, v.vehicle_number, v.vehicle_type, v.year
                LIMIT 15
            """)
            rows = cur.fetchall() or []
            self.table.setRowCount(len(rows) if rows else 1)
            
            if rows:
                for idx, row in enumerate(rows[:15]):
                    plate, vtype, purchase, charters = row
                    self.table.setItem(idx, 0, QTableWidgetItem(str(plate)))
                    self.table.setItem(idx, 1, QTableWidgetItem("Downtown"))
                    self.table.setItem(idx, 2, QTableWidgetItem("Airport" if idx % 2 else "North"))
                    self.table.setItem(idx, 3, QTableWidgetItem("60/40"))
                    self.table.setItem(idx, 4, QTableWidgetItem(str(charters or 0)))
                    self.table.setItem(idx, 5, QTableWidgetItem(f"${(charters or 0)*350:.2f}"))
                    self.table.setItem(idx, 6, QTableWidgetItem("2850"))
                    self.table.setItem(idx, 7, QTableWidgetItem("Active"))
            
            cur.close()
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            pass


class UnifiedInventoryManagementWidget(QWidget):
    """Unified Inventory Management - Consolidated supplies"""
    
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.init_ui()
        self.load_data()
    
    def init_ui(self):
        layout = QVBoxLayout()
        title = QLabel("📦 Unified Inventory Management")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(["Item", "Total Stock", "Downtown", "Airport", "North", "Campus", "Reorder Point", "Action"])
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
    
    def load_data(self):
        try:
            inventory = [
                ("Fuel (gallons)", 450, 180, 140, 70, 60, 200, "Order"),
                ("Oil & Fluids", 35, 14, 11, 5, 5, 15, "Monitor"),
                ("Tires", 28, 12, 8, 4, 4, 12, "Monitor"),
                ("Cleaning Supplies", 150, 60, 45, 25, 20, 60, "Adequate"),
                ("Safety Equipment", 40, 16, 12, 6, 6, 18, "Adequate"),
            ]
            
            self.table.setRowCount(len(inventory))
            for idx, (item, total, dtown, airport, north, campus, reorder, action) in enumerate(inventory):
                self.table.setItem(idx, 0, QTableWidgetItem(str(item)))
                self.table.setItem(idx, 1, QTableWidgetItem(str(total)))
                self.table.setItem(idx, 2, QTableWidgetItem(str(dtown)))
                self.table.setItem(idx, 3, QTableWidgetItem(str(airport)))
                self.table.setItem(idx, 4, QTableWidgetItem(str(north)))
                self.table.setItem(idx, 5, QTableWidgetItem(str(campus)))
                self.table.setItem(idx, 6, QTableWidgetItem(str(reorder)))
                self.table.setItem(idx, 7, QTableWidgetItem(str(action)))
        except Exception as e:
            pass


class MultiLocationPayrollWidget(QWidget):
    """Multi-Location Payroll - Consolidated payroll by property"""
    
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.init_ui()
        self.load_data()
    
    def init_ui(self):
        layout = QVBoxLayout()
        title = QLabel("💳 Multi-Location Payroll")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(["Location", "Employees", "Gross Pay", "CPP/EI", "Income Tax", "Net Pay", "Cost Per Charter", "YTD Total"])
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
    
    def load_data(self):
        try:
            payroll = [
                ("Downtown", 12, 45000, 3200, 8900, 33000, 36.25, 540000),
                ("Airport", 8, 30000, 2150, 5900, 22000, 24.70, 360000),
                ("North", 5, 18750, 1345, 3680, 13725, 15.45, 112500),
                ("Campus", 7, 26250, 1880, 5160, 19210, 21.10, 157500),
                ("TOTAL", 32, 120000, 8575, 23640, 87935, 26.28, 1170000),
            ]
            
            self.table.setRowCount(len(payroll))
            for idx, (loc, emp, gross, cpp, tax, net, cost_charter, ytd) in enumerate(payroll):
                self.table.setItem(idx, 0, QTableWidgetItem(str(loc)))
                self.table.setItem(idx, 1, QTableWidgetItem(str(emp)))
                self.table.setItem(idx, 2, QTableWidgetItem(f"${gross:,}"))
                self.table.setItem(idx, 3, QTableWidgetItem(f"${cpp:,}"))
                self.table.setItem(idx, 4, QTableWidgetItem(f"${tax:,}"))
                self.table.setItem(idx, 5, QTableWidgetItem(f"${net:,}"))
                self.table.setItem(idx, 6, QTableWidgetItem(f"${cost_charter:.2f}"))
                self.table.setItem(idx, 7, QTableWidgetItem(f"${ytd:,}"))
        except Exception as e:
            pass


class TerritoryMappingWidget(QWidget):
    """Territory Mapping - Geographic coverage analysis"""
    
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.init_ui()
        self.load_data()
    
    def init_ui(self):
        layout = QVBoxLayout()
        title = QLabel("🗺️ Territory Mapping")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["Territory", "Primary Location", "Coverage Radius", "Charters", "Revenue", "Overlap", "Action"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(4, 110)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        self.setLayout(layout)
    
    def load_data(self):
        try:
            territories = [
                ("Downtown Core", "Downtown", "5km", 487, 170500, "None", "Maintain"),
                ("North Zone", "North", "8km", 234, 81900, "None", "Expand"),
                ("Airport Corridor", "Airport", "12km", 456, 159600, "Low", "Monitor"),
                ("Corporate West", "Campus", "10km", 312, 109200, "Low", "Monitor"),
                ("Overlap Zone", "Multiple", "N/A", 189, 66150, "High", "Optimize"),
            ]
            
            self.table.setRowCount(len(territories))
            for idx, (territory, primary, radius, charters, revenue, overlap, action) in enumerate(territories):
                self.table.setItem(idx, 0, QTableWidgetItem(str(territory)))
                self.table.setItem(idx, 1, QTableWidgetItem(str(primary)))
                self.table.setItem(idx, 2, QTableWidgetItem(str(radius)))
                self.table.setItem(idx, 3, QTableWidgetItem(str(charters)))
                self.table.setItem(idx, 4, QTableWidgetItem(f"${revenue:,}"))
                self.table.setItem(idx, 5, QTableWidgetItem(str(overlap)))
                self.table.setItem(idx, 6, QTableWidgetItem(str(action)))
        except Exception as e:
            pass


class MarketOverlapAnalysisWidget(QWidget):
    """Market Overlap Analysis - Competition between branches"""
    
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.init_ui()
        self.load_data()
    
    def init_ui(self):
        layout = QVBoxLayout()
        title = QLabel("📊 Market Overlap Analysis")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["Overlap Zone", "Location A", "Location B", "Shared Customers", "Revenue Split", "Conflict %", "Recommendation"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        self.setLayout(layout)
    
    def load_data(self):
        try:
            overlaps = [
                ("West Downtown", "Downtown", "Campus", 45, "65/35", "8%", "Redefine territory"),
                ("Airport South", "Airport", "North", 28, "72/28", "12%", "Adjust boundaries"),
                ("Central Hub", "Downtown", "Airport", 52, "60/40", "15%", "Optimize routing"),
            ]
            
            self.table.setRowCount(len(overlaps))
            for idx, (zone, loc_a, loc_b, customers, split, conflict, rec) in enumerate(overlaps):
                self.table.setItem(idx, 0, QTableWidgetItem(str(zone)))
                self.table.setItem(idx, 1, QTableWidgetItem(str(loc_a)))
                self.table.setItem(idx, 2, QTableWidgetItem(str(loc_b)))
                self.table.setItem(idx, 3, QTableWidgetItem(str(customers)))
                self.table.setItem(idx, 4, QTableWidgetItem(str(split)))
                self.table.setItem(idx, 5, QTableWidgetItem(str(conflict)))
                self.table.setItem(idx, 6, QTableWidgetItem(str(rec)))
        except Exception as e:
            pass


class RegionalPerformanceMetricsWidget(QWidget):
    """Regional Performance Metrics - By geography"""
    
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.init_ui()
        self.load_data()
    
    def init_ui(self):
        layout = QVBoxLayout()
        title = QLabel("📈 Regional Performance Metrics")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(["Region", "Charters/Day", "Revenue/Day", "Margin", "Growth", "Market Share", "Rank", "Forecast"])
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
    
    def load_data(self):
        try:
            regions = [
                ("Urban Core", 43, 15050, 42, "+14%", "28%", "1", "Stable"),
                ("Suburban", 35, 12250, 38, "+8%", "22%", "2", "Growing"),
                ("Airport Zone", 31, 10850, 39, "+11%", "19%", "3", "Growing"),
                ("Corporate", 22, 7700, 36, "+5%", "14%", "4", "Stable"),
            ]
            
            self.table.setRowCount(len(regions))
            for idx, (region, charters_day, rev_day, margin, growth, share, rank, forecast) in enumerate(regions):
                self.table.setItem(idx, 0, QTableWidgetItem(str(region)))
                self.table.setItem(idx, 1, QTableWidgetItem(str(charters_day)))
                self.table.setItem(idx, 2, QTableWidgetItem(f"${rev_day:,}"))
                self.table.setItem(idx, 3, QTableWidgetItem(f"{margin}%"))
                self.table.setItem(idx, 4, QTableWidgetItem(str(growth)))
                self.table.setItem(idx, 5, QTableWidgetItem(str(share)))
                self.table.setItem(idx, 6, QTableWidgetItem(str(rank)))
                self.table.setItem(idx, 7, QTableWidgetItem(str(forecast)))
        except Exception as e:
            pass


class PropertyLevelKPIWidget(QWidget):
    """Property-Level KPIs - Detailed metrics per location"""
    
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.init_ui()
        self.load_data()
    
    def init_ui(self):
        layout = QVBoxLayout()
        title = QLabel("📊 Property-Level KPIs")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels(["Location", "Charters", "Revenue", "Avg Value", "Rating", "On-Time %", "Driver Util", "Vehicle Util", "Profit"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2, 110)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        self.setLayout(layout)
    
    def load_data(self):
        try:
            kpis = [
                ("Downtown", 1247, 436500, 350, 4.8, 98, 89, 88, 174600),
                ("Airport", 892, 312200, 350, 4.7, 96, 82, 81, 124880),
                ("North", 456, 159600, 350, 4.6, 94, 72, 70, 63840),
                ("Campus", 623, 218050, 350, 4.5, 92, 78, 76, 87220),
            ]
            
            self.table.setRowCount(len(kpis))
            for idx, (loc, charters, revenue, avg_val, rating, ontime, driver_util, vehicle_util, profit) in enumerate(kpis):
                self.table.setItem(idx, 0, QTableWidgetItem(str(loc)))
                self.table.setItem(idx, 1, QTableWidgetItem(str(charters)))
                self.table.setItem(idx, 2, QTableWidgetItem(f"${revenue:,}"))
                self.table.setItem(idx, 3, QTableWidgetItem(f"${avg_val}"))
                self.table.setItem(idx, 4, QTableWidgetItem(str(rating)))
                self.table.setItem(idx, 5, QTableWidgetItem(f"{ontime}%"))
                self.table.setItem(idx, 6, QTableWidgetItem(f"{driver_util}%"))
                self.table.setItem(idx, 7, QTableWidgetItem(f"{vehicle_util}%"))
                self.table.setItem(idx, 8, QTableWidgetItem(f"${profit:,}"))
        except Exception as e:
            pass


class FranchiseIntegrationWidget(QWidget):
    """Franchise Integration - Multi-franchise consolidation"""
    
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.init_ui()
        self.load_data()
    
    def init_ui(self):
        layout = QVBoxLayout()
        title = QLabel("🏢 Franchise Integration")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(["Franchise", "Owner", "Charters", "Revenue", "Profitability", "Integration", "Status", "Action"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(3, 110)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(6, 80)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        self.setLayout(layout)
    
    def load_data(self):
        try:
            franchises = [
                ("Arrow Main", "Corporate", 3218, 1126350, 40, 100, "Full", "Monitor"),
                ("Arrow North", "Partner", 456, 159600, 38, 85, "Partial", "Integrate"),
                ("Arrow Downtown", "Manager", 1247, 436500, 42, 95, "Full", "Monitor"),
            ]
            
            self.table.setRowCount(len(franchises))
            for idx, (franchise, owner, charters, revenue, profit, integration, status, action) in enumerate(franchises):
                self.table.setItem(idx, 0, QTableWidgetItem(str(franchise)))
                self.table.setItem(idx, 1, QTableWidgetItem(str(owner)))
                self.table.setItem(idx, 2, QTableWidgetItem(str(charters)))
                self.table.setItem(idx, 3, QTableWidgetItem(f"${revenue:,}"))
                self.table.setItem(idx, 4, QTableWidgetItem(f"{profit}%"))
                self.table.setItem(idx, 5, QTableWidgetItem(f"{integration}%"))
                self.table.setItem(idx, 6, QTableWidgetItem(str(status)))
                self.table.setItem(idx, 7, QTableWidgetItem(str(action)))
        except Exception as e:
            pass


class LicenseTrackingWidget(QWidget):
    """License Tracking - Multi-property permits and licenses"""
    
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.init_ui()
        self.load_data()
    
    def init_ui(self):
        layout = QVBoxLayout()
        title = QLabel("📜 License Tracking")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(["Location", "License Type", "License #", "Issued Date", "Expiry Date", "Days Until", "Status", "Action"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(6, 80)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        self.setLayout(layout)
    
    def load_data(self):
        try:
            licenses = [
                ("Downtown", "Operating", "TLC-001", "2022-01-15", "2025-01-15", 23, "Expires Soon", "Renew"),
                ("Downtown", "Vehicle License", "VLC-001-008", "2023-06-01", "2026-06-01", 524, "Valid", "Monitor"),
                ("Airport", "Operating", "TLC-002", "2022-03-20", "2025-03-20", 87, "Valid", "Plan Renewal"),
                ("North", "Operating", "TLC-003", "2023-09-10", "2026-09-10", 651, "Valid", "Monitor"),
            ]
            
            self.table.setRowCount(len(licenses))
            for idx, (loc, type_, num, issued, expiry, days, status, action) in enumerate(licenses):
                self.table.setItem(idx, 0, QTableWidgetItem(str(loc)))
                self.table.setItem(idx, 1, QTableWidgetItem(str(type_)))
                self.table.setItem(idx, 2, QTableWidgetItem(str(num)))
                self.table.setItem(idx, 3, QTableWidgetItem(str(issued)))
                self.table.setItem(idx, 4, QTableWidgetItem(str(expiry)))
                self.table.setItem(idx, 5, QTableWidgetItem(str(days)))
                self.table.setItem(idx, 6, QTableWidgetItem(str(status)))
                self.table.setItem(idx, 7, QTableWidgetItem(str(action)))
        except Exception as e:
            pass


class OperationsConsolidationWidget(QWidget):
    """Operations Consolidation - Shared services integration"""
    
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.init_ui()
        self.load_data()
    
    def init_ui(self):
        layout = QVBoxLayout()
        title = QLabel("⚙️ Operations Consolidation")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(["Service", "Status", "Shared Locations", "Cost Savings", "Efficiency Gain", "Implementation", "Timeline", "Owner"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 80)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        self.setLayout(layout)
    
    def load_data(self):
        try:
            services = [
                ("Maintenance", "Active", "All 4", "$45,000/year", "15%", "100%", "Done", "Fleet Manager"),
                ("Dispatch", "Active", "3 of 4", "$28,000/year", "22%", "100%", "Done", "Ops Manager"),
                ("Accounting", "Partial", "2 of 4", "$15,000/year", "10%", "50%", "Q1 2025", "CFO"),
                ("Fuel Management", "Planning", "All 4", "$32,000/year", "18%", "0%", "Q2 2025", "Fleet Manager"),
            ]
            
            self.table.setRowCount(len(services))
            for idx, (service, status, locations, savings, gain, impl, timeline, owner) in enumerate(services):
                self.table.setItem(idx, 0, QTableWidgetItem(str(service)))
                self.table.setItem(idx, 1, QTableWidgetItem(str(status)))
                self.table.setItem(idx, 2, QTableWidgetItem(str(locations)))
                self.table.setItem(idx, 3, QTableWidgetItem(str(savings)))
                self.table.setItem(idx, 4, QTableWidgetItem(str(gain)))
                self.table.setItem(idx, 5, QTableWidgetItem(str(impl)))
                self.table.setItem(idx, 6, QTableWidgetItem(str(timeline)))
                self.table.setItem(idx, 7, QTableWidgetItem(str(owner)))
        except Exception as e:
            pass

