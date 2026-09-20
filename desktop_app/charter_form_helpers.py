import json
import os

from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtGui import QColor, QTextCharFormat, QSyntaxHighlighter
from PyQt6.QtWidgets import QAbstractSpinBox, QComboBox, QStyledItemDelegate

try:
    from spellchecker import SpellChecker as _SpellChecker

    _spell = _SpellChecker()
    _SPELLCHECK_AVAILABLE = True
except Exception:
    _spell = None
    _SPELLCHECK_AVAILABLE = False

_PAYMENT_TYPES = [
    "NRR Retainer",
    "Deposit",
    "Refund",
    "Discount",
    "Trade of Services",
    "Promotional Credit",
    "Other",
]
_PAYMENT_METHODS = [
    "nrr",
    "etransfer",
    "credit_card",
    "cash",
    "cheque",
    "draft",
    "bank_transfer",
    "escrow",
    "trade",
    "promotional",
    "refund",
    "other",
]
_PAYMENT_PLACEHOLDER_NOTE = "manual entry (split example: nrr=500)"

current_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(current_dir, os.pardir))
_RESERVE_CONFIG_PATH = os.path.join(project_root, "config", "reserve_config.json")


def _load_reserve_cap() -> int:
    try:
        with open(_RESERVE_CONFIG_PATH) as _f:
            return int(json.load(_f).get("reserve_cap", 0))
    except Exception:
        return 0


def _save_reserve_cap(cap: int) -> None:
    os.makedirs(os.path.dirname(_RESERVE_CONFIG_PATH), exist_ok=True)
    with open(_RESERVE_CONFIG_PATH, "w") as _f:
        json.dump({"reserve_cap": cap}, _f)


def _encode_payment_key(type_label: str, note_text: str, nrr_portion: float, gl_code: str) -> str:
    parts = []
    clean_type = (type_label or "").strip()
    clean_note = (note_text or "").strip()
    clean_gl = (gl_code or "").strip()
    if clean_type:
        parts.append(f"[TYPE:{clean_type}]")
    if nrr_portion > 0:
        parts.append(f"[NRR_PART:{nrr_portion:.2f}]")
    if clean_gl:
        parts.append(f"[GL:{clean_gl}]")
    if clean_note and clean_note.lower() != _PAYMENT_PLACEHOLDER_NOTE.lower():
        parts.append(clean_note)
    return " ".join(parts).strip()


def _decode_payment_key(raw_value: str) -> tuple[str, str, str, str]:
    text = (raw_value or "").strip()
    type_label = ""
    nrr_portion_text = "0.00"
    gl_text = ""
    try:
        import re

        type_match = re.search(r"\[TYPE:([^\]]+)\]", text, flags=re.IGNORECASE)
        if type_match:
            type_label = type_match.group(1).strip()
            text = re.sub(r"\[TYPE:[^\]]+\]", "", text, flags=re.IGNORECASE).strip()

        nrr_match = re.search(r"\[NRR_PART:\s*([0-9]+(?:\.[0-9]{1,2})?)\]", text, flags=re.IGNORECASE)
        if nrr_match:
            nrr_portion_text = f"{float(nrr_match.group(1)):.2f}"
            text = re.sub(r"\[NRR_PART:\s*[0-9]+(?:\.[0-9]{1,2})?\]", "", text, flags=re.IGNORECASE).strip()

        gl_match = re.search(r"\[GL:([^\]]+)\]", text, flags=re.IGNORECASE)
        if gl_match:
            gl_text = gl_match.group(1).strip()
            text = re.sub(r"\[GL:[^\]]+\]", "", text, flags=re.IGNORECASE).strip()
    except Exception:
        pass

    if text.lower() == _PAYMENT_PLACEHOLDER_NOTE.lower():
        text = ""
    return type_label, text, gl_text, nrr_portion_text


class NoScrollWheelFilter(QObject):
    """Blocks wheel events when the charter is locked or the widget lacks focus."""

    def __init__(self, parent) -> None:
        super().__init__(parent)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel:
            if isinstance(obj, (QComboBox, QAbstractSpinBox)):
                event.ignore()
                return True
        return False


class PaymentTableDelegate(QStyledItemDelegate):
    """Combo-box editor for Type (col 0) and Method (col 3) in payments table."""

    def createEditor(self, parent, option, index):
        col = index.column()
        if col not in (0, 3):
            return super().createEditor(parent, option, index)
        combo = QComboBox(parent)
        combo.addItems(_PAYMENT_TYPES if col == 0 else _PAYMENT_METHODS)
        combo.setEditable(True)
        return combo

    def setEditorData(self, editor, index):
        if not isinstance(editor, QComboBox):
            super().setEditorData(editor, index)
            return
        val = index.data(Qt.ItemDataRole.EditRole) or ""
        idx = editor.findText(val, Qt.MatchFlag.MatchFixedString)
        if idx >= 0:
            editor.setCurrentIndex(idx)
        else:
            editor.setEditText(val)

    def setModelData(self, editor, model, index):
        if not isinstance(editor, QComboBox):
            super().setModelData(editor, model, index)
            return
        model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)


class SpellCheckHighlighter(QSyntaxHighlighter):
    """Underlines misspelled words in red in any QTextDocument."""

    def __init__(self, document) -> None:
        super().__init__(document)
        self._fmt = QTextCharFormat()
        self._fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SpellCheckUnderline)
        self._fmt.setUnderlineColor(QColor("red"))

    def highlightBlock(self, text) -> None:
        if not _SPELLCHECK_AVAILABLE or _spell is None:
            return
        import re

        for m in re.finditer(r"[A-Za-z']+", text):
            word = m.group()
            if word.lower() in ("i",):
                continue
            if _spell.unknown([word]):
                self.setFormat(m.start(), len(word), self._fmt)


def _attach_spellcheck(text_edit) -> None:
    """Attach SpellCheckHighlighter to a QTextEdit if spell check is available."""
    if _SPELLCHECK_AVAILABLE:
        SpellCheckHighlighter(text_edit.document())
