"""
Document Management Widget
Upload, categorize, search, and manage documents
Ported from frontend/src/views/Documents.vue
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QFileDialog, QTabWidget, QListWidget,
    QListWidgetItem, QComboBox, QTextEdit
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor
import psycopg2
from datetime import datetime
import os
import mimetypes


class DocumentManagementWidget(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.init_ui()
        self.load_documents()

    def init_ui(self):
        """Initialize document management UI"""
        layout = QVBoxLayout()

        # Category tabs
        self.tabs = QTabWidget()
        self.categories = ["All", "Contracts", "Insurance", "Licenses", "Maintenance", "Financial", "Legal", "HR", "Other"]
        for category in self.categories:
            self.tabs.addTab(self._create_category_tab(category), f"📋 {category}")
        
        layout.addWidget(self.tabs)

        # Upload section
        upload_group = QGroupBox("📤 Upload Document")
        upload_layout = QFormLayout()

        self.doc_category = QComboBox()
        self.doc_category.addItems(self.categories[1:])  # Exclude "All"
        self.doc_title = QLineEdit()
        self.doc_title.setPlaceholderText("Document title...")
        self.doc_description = QTextEdit()
        self.doc_description.setFixedHeight(50)
        self.doc_description.setPlaceholderText("Description (optional)...")
        self.doc_tags = QLineEdit()
        self.doc_tags.setPlaceholderText("Tags (comma-separated)...")

        upload_btn = QPushButton("🔎 Browse & Upload File")
        upload_btn.clicked.connect(self.upload_document)

        upload_layout.addRow("Category*", self.doc_category)
        upload_layout.addRow("Title*", self.doc_title)
        upload_layout.addRow("Description", self.doc_description)
        upload_layout.addRow("Tags", self.doc_tags)
        upload_layout.addRow(upload_btn)

        upload_group.setLayout(upload_layout)
        layout.addWidget(upload_group)

        self.setLayout(layout)

    def _create_category_tab(self, category):
        """Create a tab for a document category"""
        widget = QWidget()
        layout = QVBoxLayout()

        # Search and filter
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Search:"))
        search_input = QLineEdit()
        search_input.setPlaceholderText("Search by title, tags...")
        filter_layout.addWidget(search_input)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # Documents table
        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(["Title", "Category", "Upload Date", "Size", "Tags", "Actions"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(table)

        # Action buttons
        button_layout = QHBoxLayout()
        view_btn = QPushButton("👁️ View")
        view_btn.clicked.connect(lambda: self.view_document(table))
        download_btn = QPushButton("⬇️ Download")
        download_btn.clicked.connect(lambda: self.download_document(table))
        delete_btn = QPushButton("🗑️ Delete")
        delete_btn.clicked.connect(lambda: self.delete_document(table))
        button_layout.addWidget(view_btn)
        button_layout.addWidget(download_btn)
        button_layout.addWidget(delete_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        widget.setLayout(layout)
        widget.category = category
        widget.table = table
        widget.search_input = search_input
        return widget

    def load_documents(self):
        """Load documents from database"""
        try:
            cur = self.db.get_cursor()
            cur.execute("""
                SELECT 
                    document_id, title, category, upload_date, file_size, tags
                FROM documents
                ORDER BY upload_date DESC
                LIMIT 1000
            """)
            
            documents = cur.fetchall()
            self.documents_data = documents
            self.display_documents(documents)

        except psycopg2.Error as e:
            # Table might not exist yet; rollback to clear aborted transaction
            try:
                self.db.rollback()
            except Exception:
                pass
            print(f"Documents table not found: {e}")
            # Show empty tables so the UI remains usable
            self.documents_data = []
            try:
                self.display_documents([])
            except Exception:
                pass

    def display_documents(self, documents):
        """Display documents in all category tabs"""
        for i in range(1, len(self.categories)):  # Skip "All" tab
            tab_widget = self.tabs.widget(i)
            category = tab_widget.category
            table = tab_widget.table

            # Filter documents by category
            category_docs = [d for d in documents if d[2] == category]

            table.setRowCount(len(category_docs))
            for row_idx, doc in enumerate(category_docs):
                cells = [
                    str(doc[1] or ""),  # title
                    str(doc[2] or ""),  # category
                    str(doc[3] or ""),  # upload_date
                    self._format_size(doc[4] or 0),  # file_size
                    str(doc[5] or ""),  # tags
                    "View | Download | Delete"  # actions
                ]
                for col_idx, cell in enumerate(cells):
                    item = QTableWidgetItem(cell)
                    table.setItem(row_idx, col_idx, item)

        # Also populate "All" tab
        all_tab = self.tabs.widget(0)
        all_table = all_tab.table
        all_table.setRowCount(len(documents))
        for row_idx, doc in enumerate(documents):
            cells = [
                str(doc[1] or ""),  # title
                str(doc[2] or ""),  # category
                str(doc[3] or ""),  # upload_date
                self._format_size(doc[4] or 0),  # file_size
                str(doc[5] or ""),  # tags
                "View | Download | Delete"  # actions
            ]
            for col_idx, cell in enumerate(cells):
                item = QTableWidgetItem(cell)
                all_table.setItem(row_idx, col_idx, item)

    def upload_document(self):
        """Upload a new document"""
        if not self.doc_title.text().strip():
            QMessageBox.warning(self, "Missing Title", "Please enter a document title.")
            return

        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Document(s) to Upload",
            "",
            "All Files (*);;PDF Files (*.pdf);;Images (*.jpg *.jpeg *.png);;Word (*.doc *.docx);;Excel (*.xls *.xlsx)"
        )

        if files:
            for file_path in files:
                try:
                    file_size = os.path.getsize(file_path)
                    file_name = os.path.basename(file_path)

                    cur = self.db.get_cursor()
                    cur.execute("""
                        INSERT INTO documents (title, category, file_path, file_size, tags, upload_date)
                        VALUES (%s, %s, %s, %s, %s, NOW())
                    """, (
                        self.doc_title.text(),
                        self.doc_category.currentText(),
                        file_path,
                        file_size,
                        self.doc_tags.text()
                    ))
                    self.db.commit()

                except Exception as e:
                    self.db.rollback()
                    QMessageBox.critical(self, "Upload Error", f"Failed to upload {file_name}: {e}")
                    return

            QMessageBox.information(self, "Success", f"Uploaded {len(files)} document(s)!")
            self.doc_title.clear()
            self.doc_description.clear()
            self.doc_tags.clear()
            self.load_documents()

    def view_document(self, table):
        """View selected document"""
        selected = table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a document.")
            return

        row = table.row(selected[0])
        title = table.item(row, 0).text()
        QMessageBox.information(self, "View Document", f"Opening document: {title}\n(File viewer will be implemented)")

    def download_document(self, table):
        """Download selected document"""
        selected = table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a document.")
            return

        row = table.row(selected[0])
        title = table.item(row, 0).text()
        QMessageBox.information(self, "Download", f"Downloading: {title}\n(Download implementation will be added)")

    def delete_document(self, table):
        """Delete selected document"""
        selected = table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a document.")
            return

        row = table.row(selected[0])
        title = table.item(row, 0).text()

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete '{title}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Find document ID from data
                doc_id = self.documents_data[row][0]
                cur = self.db.get_cursor()
                cur.execute("DELETE FROM documents WHERE document_id = %s", (doc_id,))
                self.db.commit()
                QMessageBox.information(self, "Success", "Document deleted!")
                self.load_documents()
            except Exception as e:
                self.db.rollback()
                QMessageBox.critical(self, "Error", f"Failed to delete: {e}")

    def _format_size(self, size_bytes):
        """Format file size"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"
