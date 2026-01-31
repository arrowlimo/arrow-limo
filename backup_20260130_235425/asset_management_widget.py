#!/usr/bin/env python3
"""
Asset Management Dashboard Widget for Desktop App
Displays asset inventory with ownership status, CCA depreciation, and CRA compliance info
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTableWidget,
    QTableWidgetItem, QLabel, QComboBox, QPushButton, QMessageBox,
    QGroupBox, QFormLayout, QLineEdit, QDoubleSpinBox,
    QTextEdit, QFileDialog, QProgressBar, QHeaderView, QAbstractItemView
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal, QThread
from PyQt6.QtGui import QFont, QColor, QBrush
import psycopg2
from decimal import Decimal
from datetime import datetime
import os
import csv

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REDACTED***")


class AssetManagementWidget(QWidget):
    """Asset inventory and CRA compliance dashboard"""
    
    asset_updated = pyqtSignal(int)  # asset_id
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.load_assets()
    
    def init_ui(self):
        """Initialize UI layout"""
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Asset Inventory & CRA Compliance")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Tabs for different asset views
        tabs = QTabWidget()
        
        # Tab 1: All Assets
        tabs.addTab(self.create_all_assets_tab(), "📦 All Assets")
        
        # Tab 2: By Ownership Status
        tabs.addTab(self.create_ownership_status_tab(), "🏠 Ownership Status")
        
        # Tab 3: Depreciation Schedule
        tabs.addTab(self.create_depreciation_tab(), "📊 Depreciation & CCA")
        
        # Tab 4: CRA Compliance Report
        tabs.addTab(self.create_cra_compliance_tab(), "📋 CRA Report")
        
        # Tab 5: Photo & Documentation Tracking
        tabs.addTab(self.create_photo_tracking_tab(), "📸 Photos & Docs")
        
        layout.addWidget(tabs)
        self.setLayout(layout)
    
    def create_all_assets_tab(self):
        """Create tab showing all active assets"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Table
        self.assets_table = QTableWidget()
        self.assets_table.setColumnCount(12)
        self.assets_table.setHorizontalHeaderLabels([
            'ID', 'Asset Name', 'Category', 'Make/Model', 'Year',
            'Ownership', 'VIN', 'Acquisition Cost', 'Book Value',
            'CCA Class', 'Status', 'Actions'
        ])
        self.assets_table.setColumnWidth(1, 200)
        self.assets_table.setColumnWidth(3, 180)
        self.assets_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.assets_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.assets_table)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.load_assets)
        button_layout.addWidget(refresh_btn)
        
        export_btn = QPushButton("💾 Export to CSV")
        export_btn.clicked.connect(self.export_assets_csv)
        button_layout.addWidget(export_btn)
        
        report_btn = QPushButton("📄 Generate CRA Report")
        report_btn.clicked.connect(self.generate_cra_report)
        button_layout.addWidget(report_btn)
        
        layout.addLayout(button_layout)
        widget.setLayout(layout)
        return widget
    
    def create_ownership_status_tab(self):
        """Create tab showing assets by ownership status"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Summary stats
        stats_layout = QHBoxLayout()
        
        self.owned_label = QLabel("Owned: 0")
        owned_font = QFont()
        owned_font.setPointSize(11)
        owned_font.setBold(True)
        self.owned_label.setFont(owned_font)
        stats_layout.addWidget(self.owned_label)
        
        self.leased_label = QLabel("Leased: 0")
        leased_font = QFont()
        leased_font.setPointSize(11)
        leased_font.setBold(True)
        self.leased_label.setFont(leased_font)
        stats_layout.addWidget(self.leased_label)
        
        self.loaned_label = QLabel("Loaned-In: 0")
        loaned_font = QFont()
        loaned_font.setPointSize(11)
        loaned_font.setBold(True)
        self.loaned_label.setFont(loaned_font)
        stats_layout.addWidget(self.loaned_label)
        
        layout.addLayout(stats_layout)
        
        # Table
        self.ownership_table = QTableWidget()
        self.ownership_table.setColumnCount(6)
        self.ownership_table.setHorizontalHeaderLabels([
            'Asset Name', 'Ownership Status', 'Legal Owner', 'Acquisition Cost', 'Book Value', 'Location'
        ])
        self.ownership_table.setColumnWidth(0, 200)
        self.ownership_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.ownership_table)
        
        widget.setLayout(layout)
        return widget
    
    def create_depreciation_tab(self):
        """Create tab showing depreciation schedules"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # CCA Class summary
        cca_group = QGroupBox("CCA Class Breakdown")
        cca_layout = QVBoxLayout()
        
        self.cca_table = QTableWidget()
        self.cca_table.setColumnCount(5)
        self.cca_table.setHorizontalHeaderLabels([
            'CCA Class', 'Count', 'Total Cost', 'CCA Rate', 'Annual Deduction'
        ])
        self.cca_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        cca_layout.addWidget(self.cca_table)
        cca_group.setLayout(cca_layout)
        layout.addWidget(cca_group)
        
        # Depreciation details
        depr_group = QGroupBox("Depreciation Details")
        depr_layout = QVBoxLayout()
        
        self.depr_table = QTableWidget()
        self.depr_table.setColumnCount(8)
        self.depr_table.setHorizontalHeaderLabels([
            'Asset Name', 'Acquisition Date', 'Cost', 'Depreciation Method',
            'Useful Life', 'Book Value', 'Annual Depreciation', 'Status'
        ])
        self.depr_table.setColumnWidth(0, 200)
        self.depr_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        depr_layout.addWidget(self.depr_table)
        depr_group.setLayout(depr_layout)
        layout.addWidget(depr_group)
        
        widget.setLayout(layout)
        return widget
    
    def create_cra_compliance_tab(self):
        """Create tab with CRA compliance information"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Summary
        summary_group = QGroupBox("CRA Compliance Summary")
        summary_layout = QVBoxLayout()
        
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setMinimumHeight(200)
        summary_layout.addWidget(self.summary_text)
        summary_group.setLayout(summary_layout)
        layout.addWidget(summary_group)
        
        # Instructions
        instructions_group = QGroupBox("CRA Compliance Guidelines")
        instructions_layout = QVBoxLayout()
        
        instructions = QTextEdit()
        instructions.setReadOnly(True)
        instructions.setText("""
CRA ASSET COMPLIANCE RULES:

1. OWNED ASSETS (Depreciate via CCA):
   - Document acquisition cost and date
   - Assign CCA class (10, 10.1, 16, etc.)
   - Track depreciation annually
   - Keep purchase receipts and contracts
   
2. LEASED ASSETS (Operating Expense):
   - Monthly payments are deductible as expenses
   - Not depreciated on your balance sheet
   - Keep lease agreements on file
   - Document lender/lessor information
   
3. LOANED-IN ASSETS (NOT Deductible):
   - NOT your property, cannot depreciate
   - NOT a deductible expense
   - Must document owner/lender clearly
   - Keep loan/borrowing agreement
   
4. DOCUMENTATION REQUIREMENTS:
   - Asset register with acquisition dates/costs
   - Proof of ownership (title, registration)
   - Lease agreements for leased assets
   - Loan agreements for borrowed equipment
   - Annual depreciation calculations
   - CCA class assignments
   
COMMON CCA CLASSES:
   - Class 10: Passenger vehicles (30% declining)
   - Class 10.1: Luxury vehicles (30%, no terminal loss)
   - Class 16: Taxis/buses (40% declining)
   - Class 8: General equipment (20% declining)
        """)
        instructions_layout.addWidget(instructions)
        instructions_group.setLayout(instructions_layout)
        layout.addWidget(instructions_group)
        
        # Actions
        action_layout = QHBoxLayout()
        
        export_cra_btn = QPushButton("📊 Export CRA Report")
        export_cra_btn.clicked.connect(self.export_cra_compliance_report)
        action_layout.addWidget(export_cra_btn)
        
        layout.addLayout(action_layout)
        widget.setLayout(layout)
        return widget
    
    def load_assets(self):
        """Load all active assets from database"""
        try:
            conn = psycopg2.connect(
                host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
            )
            cur = conn.cursor()
            
            # Get all active assets
            cur.execute("""
                SELECT 
                    asset_id, asset_name, asset_category, make, model, year,
                    vin, ownership_status, legal_owner, acquisition_cost,
                    current_book_value, cca_class, location, status
                FROM assets
                WHERE status = 'active'
                ORDER BY asset_name
            """)
            
            rows = cur.fetchall()
            self.assets_table.setRowCount(len(rows))
            
            owned_count = 0
            leased_count = 0
            loaned_count = 0
            
            for row_idx, row in enumerate(rows):
                asset_id = row[0]
                name = row[1]
                category = row[2]
                make = row[3]
                model = row[4]
                year = row[5]
                vin = row[6]
                ownership = row[7]
                cost = row[9]
                book_value = row[10]
                cca_class = row[11]
                
                # Count by ownership
                if ownership == 'owned':
                    owned_count += 1
                elif ownership == 'leased':
                    leased_count += 1
                elif ownership == 'loaned_in':
                    loaned_count += 1
                
                # Populate row
                self.assets_table.setItem(row_idx, 0, QTableWidgetItem(str(asset_id)))
                self.assets_table.setItem(row_idx, 1, QTableWidgetItem(name))
                self.assets_table.setItem(row_idx, 2, QTableWidgetItem(category or ''))
                self.assets_table.setItem(row_idx, 3, QTableWidgetItem(f"{make or ''} {model or ''}"))
                self.assets_table.setItem(row_idx, 4, QTableWidgetItem(str(year or '')))
                
                ownership_item = QTableWidgetItem(ownership)
                if ownership == 'owned':
                    ownership_item.setBackground(QBrush(QColor(200, 255, 200)))
                elif ownership == 'leased':
                    ownership_item.setBackground(QBrush(QColor(255, 255, 200)))
                elif ownership == 'loaned_in':
                    ownership_item.setBackground(QBrush(QColor(255, 200, 200)))
                self.assets_table.setItem(row_idx, 5, ownership_item)
                
                self.assets_table.setItem(row_idx, 6, QTableWidgetItem(vin or ''))
                self.assets_table.setItem(row_idx, 7, QTableWidgetItem(f"${cost:,.2f}" if cost else "$0.00"))
                self.assets_table.setItem(row_idx, 8, QTableWidgetItem(f"${book_value:,.2f}" if book_value else "$0.00"))
                self.assets_table.setItem(row_idx, 9, QTableWidgetItem(cca_class or 'Unclassified'))
            
            # Update stats
            self.owned_label.setText(f"Owned: {owned_count}")
            self.leased_label.setText(f"Leased: {leased_count}")
            self.loaned_label.setText(f"Loaned-In: {loaned_count}")
            
            cur.close()
            conn.close()
            
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Failed to load assets:\n{str(e)}")
    
    def export_assets_csv(self):
        """Export assets to CSV"""
        path, _ = QFileDialog.getSaveFileName(self, "Export Assets", "", "CSV Files (*.csv)")
        if path:
            try:
                with open(path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    
                    # Headers
                    headers = []
                    for col in range(self.assets_table.columnCount() - 1):  # Exclude Actions
                        headers.append(self.assets_table.horizontalHeaderItem(col).text())
                    writer.writerow(headers)
                    
                    # Data
                    for row in range(self.assets_table.rowCount()):
                        row_data = []
                        for col in range(self.assets_table.columnCount() - 1):
                            item = self.assets_table.item(row, col)
                            row_data.append(item.text() if item else "")
                        writer.writerow(row_data)
                
                QMessageBox.information(self, "Success", f"Exported {self.assets_table.rowCount()} assets to\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))
    
    def generate_cra_report(self):
        """Generate CRA compliance report"""
        try:
            import subprocess
            result = subprocess.run(
                ["python", "-X", "utf8", "scripts/report_cra_asset_compliance.py"],
                cwd="l:\\limo",
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                QMessageBox.information(self, "Success", "CRA report generated:\n" + result.stdout)
            else:
                QMessageBox.warning(self, "Error", result.stderr or "Report generation failed")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
    
    def export_cra_compliance_report(self):
        """Export CRA compliance report"""
        path, _ = QFileDialog.getSaveFileName(self, "Export CRA Report", "", "Text Files (*.txt)")
        if path:
            try:
                # Run CRA report generator
                import subprocess
                result = subprocess.run(
                    ["python", "-X", "utf8", "scripts/report_cra_asset_compliance.py"],
                    cwd="l:\\limo",
                    capture_output=True,
                    text=True
                )
                
                # Copy the generated report
                src_path = "l:\\limo\\reports\\assets\\CRA_ASSET_SUMMARY.txt"
                import shutil
                shutil.copy(src_path, path)
                
                QMessageBox.information(self, "Success", f"CRA report exported to\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))
    
    def create_photo_tracking_tab(self):
        """Create tab for photo and document tracking"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Asset selector
        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("Select Asset:"))
        
        self.asset_combo = QComboBox()
        self.asset_combo.currentIndexChanged.connect(self.load_asset_photos)
        selector_layout.addWidget(self.asset_combo)
        layout.addLayout(selector_layout)
        
        # Photo/Document list
        doc_group = QGroupBox("Documentation & Photos")
        doc_layout = QVBoxLayout()
        
        self.doc_table = QTableWidget()
        self.doc_table.setColumnCount(5)
        self.doc_table.setHorizontalHeaderLabels([
            'Type', 'Description', 'Date Uploaded', 'File Status', 'Actions'
        ])
        self.doc_table.setColumnWidth(0, 100)
        self.doc_table.setColumnWidth(1, 250)
        self.doc_table.setColumnWidth(2, 150)
        self.doc_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        doc_layout.addWidget(self.doc_table)
        
        # Upload buttons
        button_layout = QHBoxLayout()
        
        upload_photo_btn = QPushButton("📸 Upload Photo")
        upload_photo_btn.clicked.connect(self.upload_photo)
        button_layout.addWidget(upload_photo_btn)
        
        upload_doc_btn = QPushButton("📄 Upload Document")
        upload_doc_btn.clicked.connect(self.upload_document)
        button_layout.addWidget(upload_doc_btn)
        
        refresh_docs_btn = QPushButton("🔄 Refresh")
        refresh_docs_btn.clicked.connect(self.load_asset_photos)
        button_layout.addWidget(refresh_docs_btn)
        
        audit_btn = QPushButton("📊 Documentation Audit")
        audit_btn.clicked.connect(self.show_photo_audit)
        button_layout.addWidget(audit_btn)
        
        doc_layout.addLayout(button_layout)
        doc_group.setLayout(doc_layout)
        layout.addWidget(doc_group)
        
        # Info text
        info_text = QTextEdit()
        info_text.setReadOnly(True)
        info_text.setMaximumHeight(200)
        info_text.setText("""
📸 PHOTO & DOCUMENTATION TRACKING

Upload photos and documents for asset CRA compliance:
  - Photos: Asset condition, before/after, damage assessment
  - Contracts: Loan agreements, lease agreements, borrowing agreements
  - Receipts: Purchase receipts, auction documents, sales records
  - Insurance: Claims, appraisals, payout documentation
  - Registration: Title, registration, VIN proof
  - Maintenance: Service records, repair documentation

All files are stored securely in the asset_photos folder by category.
Documentation audit report shows coverage status for all assets.""")
        layout.addWidget(info_text)
        
        widget.setLayout(layout)
        return widget
    
    def load_asset_photos(self):
        """Load list of assets for selection"""
        try:
            conn = psycopg2.connect(
                host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
            )
            cur = conn.cursor()
            
            cur.execute("""
                SELECT asset_id, asset_name 
                FROM assets 
                WHERE status IN ('active', 'disposed', 'stolen')
                ORDER BY asset_name
            """)
            
            assets = cur.fetchall()
            self.asset_combo.clear()
            
            for asset_id, asset_name in assets:
                self.asset_combo.addItem(f"{asset_name} [#{asset_id}]", asset_id)
            
            # Load photos for current selection
            if assets:
                self.show_asset_documentation(assets[0][0])
            
            cur.close()
            conn.close()
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.critical(self, "Error", f"Failed to load assets:\n{str(e)}")
    
    def show_asset_documentation(self, asset_id):
        """Show documentation for selected asset"""
        try:
            conn = psycopg2.connect(
                host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
            )
            cur = conn.cursor()
            
            cur.execute("""
                SELECT doc_id, document_type, description, uploaded_date, file_path
                FROM asset_documentation
                WHERE asset_id = %s
                ORDER BY uploaded_date DESC
            """, (asset_id,))
            
            docs = cur.fetchall()
            self.doc_table.setRowCount(len(docs))
            
            for row_idx, (doc_id, doc_type, description, uploaded_date, file_path) in enumerate(docs):
                exists = "✓ Found" if file_path and os.path.exists(file_path) else "✗ Missing"
                
                self.doc_table.setItem(row_idx, 0, QTableWidgetItem(doc_type or ""))
                self.doc_table.setItem(row_idx, 1, QTableWidgetItem(description or ""))
                self.doc_table.setItem(row_idx, 2, QTableWidgetItem(
                    uploaded_date.strftime('%m/%d/%Y') if uploaded_date else ""
                ))
                
                status_item = QTableWidgetItem(exists)
                if "Missing" in exists:
                    status_item.setBackground(QBrush(QColor(255, 200, 200)))
                else:
                    status_item.setBackground(QBrush(QColor(200, 255, 200)))
                self.doc_table.setItem(row_idx, 3, status_item)
                
                view_btn = QPushButton("View")
                view_btn.clicked.connect(lambda checked, fp=file_path: self.open_file(fp))
                self.doc_table.setCellWidget(row_idx, 4, view_btn)
            
            cur.close()
            conn.close()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load documentation:\n{str(e)}")
    
    def upload_photo(self):
        """Upload a photo for the selected asset"""
        if self.asset_combo.currentIndex() < 0:
            QMessageBox.warning(self, "No Asset", "Please select an asset first")
            return
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Photo", "", "Images (*.jpg *.jpeg *.png *.bmp *.gif)"
        )
        
        if file_path:
            asset_id = self.asset_combo.currentData()
            description, ok = QLineEdit(self).text, True
            description = f"Photo of asset {asset_id}"
            
            try:
                import subprocess
                result = subprocess.run(
                    ["python", "-X", "utf8", "-c",
                     f"""from scripts.asset_photo_tracking import add_photo_to_asset
add_photo_to_asset({asset_id}, r'{file_path}', '{description}', 'photo')"""],
                    cwd="l:\\limo",
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    QMessageBox.information(self, "Success", "Photo uploaded successfully")
                    self.load_asset_photos()
                else:
                    QMessageBox.warning(self, "Error", result.stderr or "Upload failed")
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
    
    def upload_document(self):
        """Upload a document for the selected asset"""
        if self.asset_combo.currentIndex() < 0:
            QMessageBox.warning(self, "No Asset", "Please select an asset first")
            return
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Document", "", "All Files (*.*)"
        )
        
        if file_path:
            asset_id = self.asset_combo.currentData()
            description = f"Document for asset {asset_id}"
            
            try:
                import subprocess
                result = subprocess.run(
                    ["python", "-X", "utf8", "-c",
                     f"""from scripts.asset_photo_tracking import add_photo_to_asset
add_photo_to_asset({asset_id}, r'{file_path}', '{description}', 'contract')"""],
                    cwd="l:\\limo",
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    QMessageBox.information(self, "Success", "Document uploaded successfully")
                    self.load_asset_photos()
                else:
                    QMessageBox.warning(self, "Error", result.stderr or "Upload failed")
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
    
    def open_file(self, file_path):
        """Open a file in default application"""
        if file_path and os.path.exists(file_path):
            try:
                import subprocess
                subprocess.Popen(f'start "{file_path}"', shell=True)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not open file:\n{str(e)}")
        else:
            QMessageBox.warning(self, "File Not Found", f"File not found:\n{file_path}")
    
    def show_photo_audit(self):
        """Show documentation audit report"""
        try:
            import subprocess
            result = subprocess.run(
                ["python", "-X", "utf8", "-c",
                 "from scripts.asset_photo_tracking import generate_photo_audit_report; generate_photo_audit_report()"],
                cwd="l:\\limo",
                capture_output=True,
                text=True
            )
            
            report_path = "l:\\limo\\reports\\assets\\PHOTO_DOCUMENTATION_AUDIT.txt"
            if os.path.exists(report_path):
                subprocess.Popen(f'start notepad "{report_path}"', shell=True)
                QMessageBox.information(self, "Success", "Audit report generated and opened")
            else:
                QMessageBox.warning(self, "Error", "Report not found")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
