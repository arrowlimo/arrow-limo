"""
Multi-Date Filter Builder - Add multiple independent date range selections.
Supports combinations like: "2022 Mar-Apr" OR "2021 Jan" OR "2023 Week 2".
Results can be grouped by year.
"""

from PyQt6.QtCore import QDate, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class DateFilterTag(QFrame):
    """Visual tag/chip representing a single date filter"""

    remove_clicked = pyqtSignal()  # Signal when remove button is clicked

    def __init__(self, year, months, week=0, parent=None) -> None:
        super().__init__(parent)
        self.year = year
        self.months = months  # List of month numbers (1-12)
        self.week = week  # 0 = all weeks, 1-5 = specific week

        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        self.setLineWidth(1)
        self.setStyleSheet("""
            QFrame {
                background-color: #e8f4f8;
                border: 1px solid #0066cc;
                border-radius: 4px;
                padding: 4px 8px;}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)

        # Display text
        label_text = self._build_label_text()
        label = QLabel(label_text)
        label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        layout.addWidget(label)

        # Remove button
        remove_btn = QPushButton("✕")
        remove_btn.setMaximumWidth(24)
        remove_btn.setMaximumHeight(24)
        remove_btn.setStyleSheet(
            "QPushButton { border: none; background: transparent; color:"
            "#cc0000;}"
        )
        remove_btn.clicked.connect(self.remove_clicked.emit)
        layout.addWidget(remove_btn)

        layout.addStretch(0)

    def _build_label_text(self) -> object:
        """Generate display text like '2022 Mar-Apr' or '2021 Week 2'"""
        month_names = [
            "",
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
        ]

        if not self.months:
            return str(self.year)

        if len(self.months) == 1:
            month_str = month_names[self.months[0]]
            if self.week > 0:
                return f"{self.year} {month_str} Week {self.week}"
            else:
                return f"{self.year} {month_str}"
        else:
            # Multiple months - show range
            first_month = month_names[self.months[0]]
            last_month = month_names[self.months[-1]]
            if first_month == last_month:
                return f"{self.year} {first_month}"
            else:
                return f"{self.year} {first_month}-{last_month}"


class MultiDateFilterBuilder(QWidget):
    """
    Build and manage multiple independent date range filters.

    Signals:
        filters_changed: Emitted when filters list is updated with list of
        (year, months, week) tuples
    """

    filters_changed = pyqtSignal(list)  # Emits list of date range tuples

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.current_year = QDate.currentDate().year()
        self.current_month = QDate.currentDate().month()
        self.filters = []  # List of (year, months_list, week) tuples
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the filter builder UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # ===== YEAR SELECTOR =====
        year_layout = QHBoxLayout()
        year_layout.addWidget(QLabel("Add Filter - Year:"))

        self.year_spinbox = QSpinBox()
        self.year_spinbox.setMinimum(2000)
        self.year_spinbox.setMaximum(2100)
        self.year_spinbox.setValue(self.current_year)
        self.year_spinbox.setMaximumWidth(80)
        year_layout.addWidget(self.year_spinbox)

        year_layout.addSpacing(20)
        year_layout.addWidget(QLabel("Month(s):"))
        year_layout.addStretch()
        layout.addLayout(year_layout)

        # ===== MONTH MULTI-SELECT =====
        month_layout = QGridLayout()
        month_layout.setSpacing(6)

        months = [
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
        ]
        self.month_checks = {}

        for idx, month_name in enumerate(months):
            row = idx // 4
            col = idx % 4
            checkbox = QCheckBox(month_name)
            # Check current month by default
            checkbox.setChecked(idx + 1 == self.current_month)
            self.month_checks[idx + 1] = checkbox  # 1-indexed
            month_layout.addWidget(checkbox, row, col)

        layout.addLayout(month_layout)

        # ===== WEEK SELECTOR (conditional) =====
        week_label_layout = QHBoxLayout()
        week_label_layout.addWidget(QLabel("Week (if single month only):"))
        week_label_layout.addStretch()
        layout.addLayout(week_label_layout)

        week_layout = QHBoxLayout()
        self.week_buttons = {}
        week_names = [
            "All Weeks",
            "Week 1",
            "Week 2",
            "Week 3",
            "Week 4",
            "Week 5",
        ]

        for week_num, week_name in enumerate(week_names):
            btn = QPushButton(week_name)
            btn.setMaximumWidth(90)
            btn.setCheckable(True)
            if week_num == 0:
                btn.setChecked(True)  # Default: All weeks
            btn.clicked.connect(self._on_week_selected)
            self.week_buttons[week_num] = btn
            week_layout.addWidget(btn)

        layout.addLayout(week_layout)

        # ===== ADD FILTER BUTTON =====
        add_btn_layout = QHBoxLayout()
        add_btn_layout.addStretch()
        add_filter_btn = QPushButton("➕ Add Filter")
        add_filter_btn.setMaximumWidth(120)
        add_filter_btn.clicked.connect(self._add_filter)
        add_btn_layout.addWidget(add_filter_btn)
        layout.addLayout(add_btn_layout)

        # ===== ACTIVE FILTERS DISPLAY =====
        filters_label = QLabel("Active Filters (click ✕ to remove):")
        filters_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        layout.addWidget(filters_label)

        # Scrollable area for filter tags
        self.filters_scroll = QScrollArea()
        self.filters_scroll.setWidgetResizable(True)
        self.filters_scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: #f9f9f9;}
        """)
        self.filters_scroll.setMinimumHeight(60)
        self.filters_scroll.setMaximumHeight(120)

        self.filters_container = QWidget()
        self.filters_container_layout = QVBoxLayout(self.filters_container)
        self.filters_container_layout.setContentsMargins(4, 4, 4, 4)
        self.filters_container_layout.setSpacing(4)
        self.filters_container_layout.addStretch()

        self.filters_scroll.setWidget(self.filters_container)
        layout.addWidget(self.filters_scroll)

        # ===== OPTIONS =====
        options_layout = QHBoxLayout()

        self.group_by_year_check = QCheckBox("📊 Group results by year")
        self.group_by_year_check.setChecked(False)
        options_layout.addWidget(self.group_by_year_check)

        clear_all_btn = QPushButton("Clear All Filters")
        clear_all_btn.setMaximumWidth(140)
        clear_all_btn.clicked.connect(self._clear_all_filters)
        options_layout.addStretch()
        options_layout.addWidget(clear_all_btn)

        layout.addLayout(options_layout)

    def _on_week_selected(self) -> None:
        """Handle week button selection (exclusive)"""
        sender = self.sender()
        sender.setChecked(True)

        # Uncheck other week buttons
        for btn in self.week_buttons.values():
            if btn is not sender:
                btn.setChecked(False)

    def _get_selected_months(self) -> object:
        """Get list of selected months (1-indexed)"""
        return sorted(
            [m for m, chk in self.month_checks.items() if chk.isChecked()]
        )

    def _get_selected_week(self) -> object:
        """Get selected week (0=all, 1-5=specific week)"""
        for week_num, btn in self.week_buttons.items():
            if btn.isChecked():
                return week_num
        return 0

    def _add_filter(self) -> None:
        """Add current selection as a new filter"""
        selected_months = self._get_selected_months()
        if not selected_months:
            return

        selected_year = self.year_spinbox.value()
        selected_week = self._get_selected_week()

        # Add to filters list
        filter_tuple = (selected_year, selected_months, selected_week)
        self.filters.append(filter_tuple)

        # Add visual tag
        self._add_filter_tag(selected_year, selected_months, selected_week)

        # Uncheck all months for next filter
        for chk in self.month_checks.values():
            chk.setChecked(False)

        # Reset week to All
        self.week_buttons[0].setChecked(True)

        # Emit filters changed
        self._emit_filters_changed()

    def _add_filter_tag(self, year, months, week=0) -> None:
        """Create and display a filter tag"""
        tag = DateFilterTag(year, months, week)
        tag.remove_clicked.connect(
            lambda: self._remove_filter_tag(tag, year, months, week)
        )

        # Insert before the stretch
        self.filters_container_layout.insertWidget(
            self.filters_container_layout.count() - 1, tag
        )

    def _remove_filter_tag(self, tag, year, months, week) -> None:
        """Remove a filter tag and update filters list"""
        self.filters_container_layout.removeWidget(tag)
        tag.deleteLater()

        # Remove from filters list
        filter_tuple = (year, months, week)
        if filter_tuple in self.filters:
            self.filters.remove(filter_tuple)

        # Emit filters changed
        self._emit_filters_changed()

    def _clear_all_filters(self) -> None:
        """Clear all active filters"""
        self.filters.clear()

        # Remove all tags
        while self.filters_container_layout.count() > 1:
            widget = self.filters_container_layout.takeAt(0).widget()
            if widget:
                widget.deleteLater()

        # Reset UI
        for chk in self.month_checks.values():
            chk.setChecked(False)
        self.week_buttons[0].setChecked(True)

        # Emit filters changed
        self._emit_filters_changed()

    def _emit_filters_changed(self) -> None:
        """Emit the filters_changed signal with current filters"""
        self.filters_changed.emit(self.filters)

    def get_filters(self) -> object:
        """Get list of active filters as (year, months_list, week) tuples"""
        return self.filters.copy()

    def should_group_by_year(self) -> object:
        """Check if group by year option is enabled"""
        return self.group_by_year_check.isChecked()

    def calculate_date_ranges(self) -> object:
        """
        Convert filter tuples to list of (from_date, to_date) QDate tuples.

        Returns:
            List of (QDate, QDate) tuples for each filter
        """
        date_ranges = []

        for year, months, week in self.filters:
            first_month = months[0]
            last_month = months[-1]

            # Start date: first of first month
            from_date = QDate(year, first_month, 1)

            # End date: last of last month
            last_day_of_month = QDate(year, last_month, 1)
            to_date = last_day_of_month.addMonths(1).addDays(-1)

            # If specific week in single month
            if len(months) == 1 and week > 0:
                first_day_of_month = QDate(year, first_month, 1)

                # Find first Monday
                first_monday = first_day_of_month
                while first_monday.dayOfWeek() != 1:  # 1 = Monday
                    first_monday = first_monday.addDays(1)

                # Calculate week range
                week_start = first_monday.addDays((week - 1) * 7)
                week_end = week_start.addDays(6)

                # Constrain to month boundaries
                month_end = first_day_of_month.addMonths(1).addDays(-1)
                if week_end > month_end:
                    week_end = month_end
                if week_start < first_day_of_month:
                    week_start = first_day_of_month

                from_date = week_start
                to_date = week_end

            date_ranges.append((from_date, to_date))

        return date_ranges
