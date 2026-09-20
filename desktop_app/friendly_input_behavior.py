"""Application-wide editing behavior for dates, times, and numeric fields."""

from PyQt6.QtCore import QDate, QEvent, QObject, QTime, QTimer
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QDateEdit,
    QDoubleSpinBox,
    QLineEdit,
    QSpinBox,
    QTimeEdit,
)


STANDARD_DATE_DISPLAY_FORMAT = "dd-MMM-yyyy"


class FriendlyInputEventFilter(QObject):
    """Make structured Qt editors behave like replaceable text fields."""

    def eventFilter(self, obj, event) -> bool:
        editor = self._editor_for(obj)
        if editor is None:
            return False

        event_type = event.type()
        if event_type in (QEvent.Type.FocusIn, QEvent.Type.MouseButtonPress):
            if event_type == QEvent.Type.MouseButtonPress:
                editor.setProperty("_friendly_numeric_digits", "")
                editor.setProperty("_friendly_time_digits", "")
                editor.setProperty("_friendly_date_digits", "")
            if isinstance(editor, QDateEdit):
                editor.setDisplayFormat(STANDARD_DATE_DISPLAY_FORMAT)
            elif isinstance(editor, QTimeEdit):
                editor.setDisplayFormat("HH:mm")
            QTimer.singleShot(0, editor.lineEdit().selectAll)
            return False

        if event_type == QEvent.Type.Show:
            if isinstance(editor, QDateEdit):
                editor.setDisplayFormat(STANDARD_DATE_DISPLAY_FORMAT)
                return False
            if isinstance(editor, QTimeEdit):
                editor.setDisplayFormat("HH:mm")
                return False

        if event_type != QEvent.Type.KeyPress or not isinstance(event, QKeyEvent):
            return False

        text = event.text()
        if isinstance(editor, QTimeEdit) and text.isdigit():
            return self._handle_time_digit(editor, text)
        if isinstance(editor, QDateEdit) and text.isdigit():
            return self._handle_date_digit(editor, text)

        if (
            isinstance(editor, (QDoubleSpinBox, QSpinBox))
            and text
            and (text[0].isdigit() or text[0] in ".-")
            and (
                editor.lineEdit().selectedText()
                or editor.property("_friendly_numeric_digits")
            )
        ):
            return self._handle_numeric_key(editor, text[0])
        return False

    @staticmethod
    def _editor_for(obj):
        if isinstance(obj, QAbstractSpinBox):
            return obj
        if isinstance(obj, QLineEdit):
            parent = obj.parentWidget()
            if isinstance(parent, QAbstractSpinBox):
                return parent
        return None

    @staticmethod
    def _start_or_append_buffer(editor, property_name: str, digit: str) -> str:
        line_edit = editor.lineEdit()
        selected_all = bool(
            line_edit.selectedText()
            and len(line_edit.selectedText()) >= len(line_edit.text())
        )
        existing = str(editor.property(property_name) or "")
        if selected_all and not existing:
            existing = ""
        value = (existing + digit)[-8:]
        editor.setProperty(property_name, value)
        QTimer.singleShot(
            1800, lambda: editor.setProperty(property_name, "")
        )
        return value

    def _handle_time_digit(self, editor: QTimeEdit, digit: str) -> bool:
        digits = self._start_or_append_buffer(
            editor, "_friendly_time_digits", digit
        )[-4:]
        editor.setProperty("_friendly_time_digits", digits)
        if len(digits) <= 2:
            hour = int(digits)
            minute = 0
        else:
            hour = int(digits[:-2])
            minute = int(digits[-2:])
        if hour <= 23 and minute <= 59:
            editor.setTime(QTime(hour, minute))
            editor.lineEdit().selectAll()
        return True

    def _handle_date_digit(self, editor: QDateEdit, digit: str) -> bool:
        digits = self._start_or_append_buffer(
            editor, "_friendly_date_digits", digit
        )[-8:]
        editor.setProperty("_friendly_date_digits", digits)
        editor.lineEdit().setText(digits)
        editor.lineEdit().setCursorPosition(len(digits))
        if len(digits) != 8:
            return True

        day, month, year = (
            int(digits[:2]),
            int(digits[2:4]),
            int(digits[4:8]),
        )
        value = QDate(year, month, day)
        if value.isValid():
            editor.setDate(value)
            editor.lineEdit().selectAll()
        else:
            from common_widgets import describe_invalid_date

            editor.setToolTip(describe_invalid_date(digits))
            editor.setProperty("_friendly_date_digits", "")
            editor.lineEdit().setText(
                editor.date().toString(STANDARD_DATE_DISPLAY_FORMAT)
            )
            editor.lineEdit().selectAll()
        return True

    def _handle_numeric_key(
        self, editor: QAbstractSpinBox, character: str
    ) -> bool:
        buffer = str(editor.property("_friendly_numeric_digits") or "")
        if character == "-" and buffer:
            return True
        if character == "." and ("." in buffer or isinstance(editor, QSpinBox)):
            return True
        buffer += character
        editor.setProperty("_friendly_numeric_digits", buffer)
        try:
            value = float(buffer)
        except ValueError:
            return True
        editor.setValue(int(value) if isinstance(editor, QSpinBox) else value)
        editor.lineEdit().selectAll()
        return True


def install_friendly_input_behavior(
    app: QApplication | None = None,
) -> FriendlyInputEventFilter | None:
    """Install the global behavior once and retain it for app lifetime."""
    app = app or QApplication.instance()
    if app is None:
        return None
    existing = getattr(app, "_friendly_input_event_filter", None)
    if isinstance(existing, FriendlyInputEventFilter):
        return existing
    event_filter = FriendlyInputEventFilter(app)
    app.installEventFilter(event_filter)
    app._friendly_input_event_filter = event_filter
    return event_filter
