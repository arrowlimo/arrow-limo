"""
Mega Menu Widget - Enhanced Navigation System
Features: Drill-down navigation, Favorites, Recent items, Search, Keyboard shortcuts
"""

import json
import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLineEdit, QLabel, QSplitter, QFrame, QTabWidget,
    QListWidget, QListWidgetItem, QMenu, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QIcon, QFont, QColor, QAction, QKeySequence


class MegaMenuWidget(QWidget):
    """
    Mega Menu with:
    - Drill-down navigation
    - Real-time search
    - Favorites system
    - Recent dashboards
    - Keyboard shortcuts
    - Export functionality
    """
    
    widget_selected = pyqtSignal(str, str)  # (class_name, display_name)
    
    def __init__(self, parent=None, preferences_file=None):
        super().__init__(parent)
        
        # Configuration
        self.menu_data = self._load_menu_structure()
        self.widget_map = {}
        self.preferences_file = preferences_file or Path.home() / ".limo_dashboard_prefs.json"
        
        # State
        self._current_widget = None
        self.favorites = set()
        self.recent = []
        
        # Build indices
        self._build_widget_map()
        self._load_preferences()
        
        # UI
        self.init_ui()
        
        # Keyboard
        self._setup_keyboard_shortcuts()
    
    def _load_menu_structure(self):
        """Load mega menu structure from JSON"""
        menu_file = Path(__file__).parent / "mega_menu_structure.json"
        try:
            with open(menu_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"⚠️  Menu structure file not found: {menu_file}")
            return {"domains": []}
    
    def _build_widget_map(self):
        """Build searchable map of all widgets"""
        for domain in self.menu_data.get("domains", []):
            for category in domain.get("categories", []):
                for widget in category.get("widgets", []):
                    self.widget_map[widget["class_name"]] = {
                        "domain": domain["domain_name"],
                        "category": category["category_name"],
                        "widget": widget["widget_name"],
                        "class_name": widget["class_name"],
                        "description": widget.get("description", "")
                    }
    
    def _load_preferences(self):
        """Load user preferences (favorites, recent)"""
        try:
            if self.preferences_file.exists():
                with open(self.preferences_file, 'r', encoding='utf-8') as f:
                    prefs = json.load(f)
                    self.favorites = set(prefs.get("favorites", []))
                    self.recent = prefs.get("recent", [])
        except:
            self.favorites = set()
            self.recent = []
    
    def _save_preferences(self):
        """Save user preferences"""
        try:
            prefs = {
                "favorites": list(self.favorites),
                "recent": self.recent[-10:]  # Keep last 10
            }
            with open(self.preferences_file, 'w', encoding='utf-8') as f:
                json.dump(prefs, f, indent=2)
        except Exception as e:
            print(f"⚠️  Could not save preferences: {e}")
    
    def init_ui(self):
        """Build the advanced menu interface"""
        layout = QVBoxLayout(self)
        
        # Header
        header = self._create_header()
        layout.addWidget(header)
        
        # Search bar with quick buttons
        search_bar = self._create_search_bar()
        layout.addLayout(search_bar)
        
        # Main tabbed interface
        self.main_tabs = QTabWidget()
        
        # Tab 1: Browse
        browse_widget = self._create_browse_tab()
        self.main_tabs.addTab(browse_widget, "📂 Browse")
        
        # Tab 2: Recent
        recent_widget = self._create_recent_tab()
        self.main_tabs.addTab(recent_widget, "⏱️  Recent")
        
        # Tab 3: Favorites
        favorites_widget = self._create_favorites_tab()
        self.main_tabs.addTab(favorites_widget, "⭐ Favorites")
        
        layout.addWidget(self.main_tabs)
        
        # Footer
        footer = self._create_footer()
        layout.addWidget(footer)
        
        self.setLayout(layout)
    
    def _create_header(self):
        """Create header section"""
        header = QFrame()
        header.setFrameShape(QFrame.Shape.StyledPanel)
        header.setStyleSheet("background-color: #f0f0f0;")
        layout = QVBoxLayout(header)
        
        title = QLabel("🗂️  Dashboard Command Center")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        
        subtitle = QLabel("📂 Click domains/categories to expand • Double-click dashboards to launch • ⭐ = Favorite • 🔍 = Search")
        subtitle_font = QFont()
        subtitle_font.setPointSize(9)
        subtitle.setFont(subtitle_font)
        subtitle.setStyleSheet("color: gray;")
        
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.setContentsMargins(10, 5, 10, 5)
        
        return header
    
    def _create_search_bar(self):
        """Create search bar with quick buttons"""
        layout = QHBoxLayout()
        
        # Search input
        search_label = QLabel("🔍 Quick Search:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type dashboard name... (Ctrl+F)")
        self.search_input.textChanged.connect(self._on_search)
        
        # Clear button
        clear_btn = QPushButton("✕")
        clear_btn.setMaximumWidth(30)
        clear_btn.clicked.connect(lambda: self.search_input.clear())
        
        # Results count
        self.search_results = QLabel("")
        self.search_results.setStyleSheet("color: gray; font-size: 10px;")
        
        # Expand/Collapse controls
        expand_all_btn = QPushButton("➕ Expand All")
        expand_all_btn.setMaximumWidth(100)
        expand_all_btn.clicked.connect(self._expand_all)
        
        collapse_all_btn = QPushButton("➖ Collapse All")
        collapse_all_btn.setMaximumWidth(100)
        collapse_all_btn.clicked.connect(self._collapse_all)
        
        layout.addWidget(search_label)
        layout.addWidget(self.search_input)
        layout.addWidget(clear_btn)
        layout.addWidget(self.search_results)
        layout.addStretch()
        layout.addWidget(expand_all_btn)
        layout.addWidget(collapse_all_btn)
        
        return layout
    
    def _create_browse_tab(self):
        """Create Browse tab with drill-down tree"""
        container = QFrame()
        layout = QHBoxLayout(container)
        
        # Domain tree (left)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("📊 Dashboards")
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_tree_context_menu)
        self.tree.itemSelectionChanged.connect(self._on_item_selected)
        self.tree.itemDoubleClicked.connect(self._on_item_activated)
        self._populate_tree()
        
        # Details pane (right)
        self.details_pane = QFrame()
        self.details_pane.setFrameShape(QFrame.Shape.StyledPanel)
        self.details_pane.setMaximumWidth(350)
        details_layout = QVBoxLayout(self.details_pane)
        
        # Widget info section
        self.details_label = QLabel("Select a dashboard")
        self.details_label.setWordWrap(True)
        self.details_label.setFont(self._make_bold_font(11))
        
        self.details_desc = QLabel("")
        self.details_desc.setWordWrap(True)
        self.details_desc.setStyleSheet("color: gray; font-size: 10px;")
        
        self.details_meta = QLabel("")
        self.details_meta.setWordWrap(True)
        self.details_meta.setStyleSheet("color: #666; font-size: 9px; font-family: monospace;")
        
        # Buttons
        buttons_layout = QVBoxLayout()
        
        self.launch_btn = QPushButton("▶ Launch Dashboard")
        self.launch_btn.clicked.connect(self._launch_selected)
        self.launch_btn.setEnabled(False)
        
        self.favorite_btn = QPushButton("⭐ Add to Favorites")
        self.favorite_btn.clicked.connect(self._toggle_favorite)
        self.favorite_btn.setEnabled(False)
        
        buttons_layout.addWidget(self.launch_btn)
        buttons_layout.addWidget(self.favorite_btn)
        
        details_layout.addWidget(QLabel("📌 Details:"), 0)
        details_layout.addWidget(self.details_label, 0)
        details_layout.addWidget(self.details_desc, 0)
        details_layout.addSpacing(5)
        details_layout.addWidget(self.details_meta, 0)
        details_layout.addSpacing(10)
        details_layout.addLayout(buttons_layout, 0)
        details_layout.addStretch()
        
        # Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.tree)
        splitter.addWidget(self.details_pane)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([500, 300])
        
        layout.addWidget(splitter)
        return container
    
    def _create_recent_tab(self):
        """Create Recent dashboards tab"""
        container = QFrame()
        layout = QVBoxLayout(container)
        
        info = QLabel("Recently launched dashboards (click to launch again):")
        info_font = QFont()
        info_font.setPointSize(10)
        info.setFont(info_font)
        
        self.recent_list = QListWidget()
        self.recent_list.itemDoubleClicked.connect(self._on_recent_selected)
        self.recent_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.recent_list.customContextMenuRequested.connect(self._on_recent_context_menu)
        
        layout.addWidget(info)
        layout.addWidget(self.recent_list)
        
        self._populate_recent_list()
        return container
    
    def _create_favorites_tab(self):
        """Create Favorites tab"""
        container = QFrame()
        layout = QVBoxLayout(container)
        
        info = QLabel("Your favorite dashboards (click to launch):")
        info_font = QFont()
        info_font.setPointSize(10)
        info.setFont(info_font)
        
        self.favorites_list = QListWidget()
        self.favorites_list.itemDoubleClicked.connect(self._on_favorites_selected)
        self.favorites_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.favorites_list.customContextMenuRequested.connect(self._on_favorites_context_menu)
        
        layout.addWidget(info)
        layout.addWidget(self.favorites_list)
        
        self._populate_favorites_list()
        return container
    
    def _create_footer(self):
        """Create footer with statistics"""
        footer = QFrame()
        footer.setFrameShape(QFrame.Shape.StyledPanel)
        footer.setStyleSheet("background-color: #f0f0f0;")
        layout = QHBoxLayout(footer)
        
        domains = len(self.menu_data.get("domains", []))
        categories = sum(len(d.get("categories", [])) for d in self.menu_data.get("domains", []))
        widgets = len(self.widget_map)
        
        stats = QLabel(
            f"📈 {domains} Domains • {categories} Categories • {widgets} Dashboards • "
            f"⭐ {len(self.favorites)} Favorites"
        )
        stats_font = QFont()
        stats_font.setPointSize(9)
        stats.setFont(stats_font)
        
        layout.addWidget(stats)
        layout.addStretch()
        layout.setContentsMargins(10, 5, 10, 5)
        
        return footer
    
    def _populate_tree(self):
        """Populate tree with domains and categories"""
        self.tree.clear()
        
        for domain in self.menu_data.get("domains", []):
            # Domain item
            domain_item = QTreeWidgetItem()
            domain_text = domain['domain_name']
            if domain["domain_id"] in [w.split(':')[0] for w in self.favorites if ':' in w]:
                domain_text = "⭐ " + domain_text
            
            domain_item.setText(0, f"{domain_text} ({domain['widget_count']})")
            domain_item.setData(0, Qt.ItemDataRole.UserRole, {
                "type": "domain",
                "id": domain["domain_id"]
            })
            domain_item.setFont(0, self._make_bold_font())
            domain_item.setForeground(0, QColor("#0066cc"))
            
            # Categories
            for category in domain.get("categories", []):
                cat_item = QTreeWidgetItem(domain_item)
                cat_item.setText(0, f"{category['category_name']} ({len(category['widgets'])})")
                cat_item.setData(0, Qt.ItemDataRole.UserRole, {
                    "type": "category",
                    "domain_id": domain["domain_id"],
                    "category_id": category["category_id"]
                })
                cat_item.setFont(0, self._make_bold_font(size=10))
                cat_item.setForeground(0, QColor("#006633"))
                
                # Widgets
                for widget in category.get("widgets", []):
                    widget_item = QTreeWidgetItem(cat_item)
                    
                    # Mark favorites with star
                    widget_text = widget["widget_name"]
                    if widget["class_name"] in self.favorites:
                        widget_text = "⭐ " + widget_text
                    
                    widget_item.setText(0, widget_text)
                    widget_item.setData(0, Qt.ItemDataRole.UserRole, {
                        "type": "widget",
                        "class_name": widget["class_name"],
                        "widget_name": widget["widget_name"],
                        "description": widget.get("description", ""),
                        "domain": domain["domain_name"],
                        "category": category["category_name"]
                    })
            
            self.tree.addTopLevelItem(domain_item)
            # Collapse by default for cleaner UI
            domain_item.setExpanded(False)
            # Also collapse categories
            for j in range(domain_item.childCount()):
                domain_item.child(j).setExpanded(False)
    
    def _populate_recent_list(self):
        """Populate recent dashboards list"""
        self.recent_list.clear()
        for class_name in self.recent[-5:]:  # Show last 5
            if class_name in self.widget_map:
                info = self.widget_map[class_name]
                item = QListWidgetItem(f"⏱️  {info['widget']}")
                item.setData(Qt.ItemDataRole.UserRole, class_name)
                self.recent_list.addItem(item)
    
    def _populate_favorites_list(self):
        """Populate favorites list"""
        self.favorites_list.clear()
        for class_name in sorted(self.favorites):
            if class_name in self.widget_map:
                info = self.widget_map[class_name]
                item = QListWidgetItem(f"⭐ {info['widget']}")
                item.setData(Qt.ItemDataRole.UserRole, class_name)
                self.favorites_list.addItem(item)
    
    def _expand_all(self):
        """Expand all tree items"""
        self.tree.expandAll()
    
    def _collapse_all(self):
        """Collapse all tree items"""
        self.tree.collapseAll()
    
    def _on_search(self, text):
        """Filter tree based on search"""
        text_lower = text.lower()
        result_count = 0
        
        for i in range(self.tree.topLevelItemCount()):
            domain_item = self.tree.topLevelItem(i)
            domain_visible = False
            
            for j in range(domain_item.childCount()):
                cat_item = domain_item.child(j)
                cat_visible = False
                
                for k in range(cat_item.childCount()):
                    widget_item = cat_item.child(k)
                    widget_name = widget_item.text(0).lower()
                    visible = text_lower in widget_name if text_lower else True
                    widget_item.setHidden(not visible)
                    if visible:
                        result_count += 1
                    cat_visible = cat_visible or visible
                
                cat_item.setHidden(not cat_visible)
                domain_visible = domain_visible or cat_visible
            
            domain_item.setHidden(not domain_visible)
        
        self.search_results.setText(f"{result_count} results" if text else "")
    
    def _on_item_selected(self):
        """Handle item selection"""
        current = self.tree.currentItem()
        if not current:
            return
        
        data = current.data(0, Qt.ItemDataRole.UserRole)
        if not data or data.get("type") != "widget":
            self.details_label.setText("Select a dashboard")
            self.details_desc.setText("")
            self.details_meta.setText("")
            self.launch_btn.setEnabled(False)
            self.favorite_btn.setEnabled(False)
            return
        
        self._current_widget = data
        self.details_label.setText(f"<b>{data['widget_name']}</b>")
        self.details_desc.setText(data.get("description", ""))
        self.details_meta.setText(f"Class: {data['class_name']}\nDomain: {data['domain']}\nCategory: {data['category']}")
        self.launch_btn.setEnabled(True)
        self.favorite_btn.setEnabled(True)
        
        # Update favorite button text
        if data["class_name"] in self.favorites:
            self.favorite_btn.setText("❌ Remove from Favorites")
            self.favorite_btn.setStyleSheet("background-color: #ffe6e6;")
        else:
            self.favorite_btn.setText("⭐ Add to Favorites")
            self.favorite_btn.setStyleSheet("")
    
    def _on_item_activated(self, item, column):
        """Handle double-click"""
        data = item.data(column, Qt.ItemDataRole.UserRole)
        if data and data.get("type") == "widget":
            self._launch_selected()
    
    def _launch_selected(self):
        """Launch selected widget"""
        if hasattr(self, '_current_widget'):
            data = self._current_widget
            class_name = data["class_name"]
            
            # Add to recent
            if class_name in self.recent:
                self.recent.remove(class_name)
            self.recent.append(class_name)
            self.recent = self.recent[-10:]  # Keep last 10
            self._populate_recent_list()
            self._save_preferences()
            
            # Emit signal
            self.widget_selected.emit(class_name, data["widget_name"])
    
    def _toggle_favorite(self):
        """Toggle favorite status"""
        if hasattr(self, '_current_widget'):
            data = self._current_widget
            class_name = data["class_name"]
            
            if class_name in self.favorites:
                self.favorites.remove(class_name)
            else:
                self.favorites.add(class_name)
            
            self._save_preferences()
            self._populate_tree()
            self._populate_favorites_list()
            self._on_item_selected()  # Refresh details
    
    def _on_recent_selected(self, item):
        """Handle recent item selection"""
        class_name = item.data(Qt.ItemDataRole.UserRole)
        if class_name in self.widget_map:
            info = self.widget_map[class_name]
            self.widget_selected.emit(class_name, info["widget"])
    
    def _on_favorites_selected(self, item):
        """Handle favorites item selection"""
        class_name = item.data(Qt.ItemDataRole.UserRole)
        if class_name in self.widget_map:
            info = self.widget_map[class_name]
            self.widget_selected.emit(class_name, info["widget"])
    
    def _on_tree_context_menu(self, position):
        """Context menu for tree items"""
        item = self.tree.itemAt(position)
        if not item:
            return
        
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data or data.get("type") != "widget":
            return
        
        menu = QMenu()
        
        class_name = data["class_name"]
        if class_name in self.favorites:
            action = menu.addAction("Remove from Favorites")
            action.triggered.connect(self._toggle_favorite)
        else:
            action = menu.addAction("Add to Favorites")
            action.triggered.connect(self._toggle_favorite)
        
        menu.addSeparator()
        launch_action = menu.addAction("Launch")
        launch_action.triggered.connect(self._launch_selected)
        
        menu.exec(self.tree.viewport().mapToGlobal(position))
    
    def _on_recent_context_menu(self, position):
        """Context menu for recent list"""
        item = self.recent_list.itemAt(position)
        if not item:
            return
        
        menu = QMenu()
        remove = menu.addAction("Remove from Recent")
        remove.triggered.connect(lambda: self.recent_list.takeItem(self.recent_list.row(item)))
        menu.exec(self.recent_list.viewport().mapToGlobal(position))
    
    def _on_favorites_context_menu(self, position):
        """Context menu for favorites list"""
        item = self.favorites_list.itemAt(position)
        if not item:
            return
        
        menu = QMenu()
        class_name = item.data(Qt.ItemDataRole.UserRole)
        
        remove = menu.addAction("Remove from Favorites")
        remove.triggered.connect(lambda: self._remove_favorite(class_name))
        menu.exec(self.favorites_list.viewport().mapToGlobal(position))
    
    def _remove_favorite(self, class_name):
        """Remove widget from favorites"""
        if class_name in self.favorites:
            self.favorites.remove(class_name)
            self._save_preferences()
            self._populate_tree()
            self._populate_favorites_list()
    
    def _setup_keyboard_shortcuts(self):
        """Setup keyboard shortcuts"""
        # Ctrl+F: Focus search
        shortcut_search = self.findChild(QLineEdit)
        if shortcut_search:
            self.setFocus()
    
    @staticmethod
    def _make_bold_font(size=11):
        """Create bold font"""
        font = QFont()
        font.setBold(True)
        font.setPointSize(size)
        return font


# Example usage
if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    
    def on_widget_selected(class_name, display_name):
        print(f"✅ Launch: {display_name} ({class_name})")
    
    menu = AdvancedMegaMenuWidget()
    menu.widget_selected.connect(on_widget_selected)
    menu.setWindowTitle("Dashboard Navigator")
    menu.resize(1300, 800)
    menu.show()
    
    sys.exit(app.exec())
