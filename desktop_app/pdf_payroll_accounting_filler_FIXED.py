"""Compatibility filler for payroll/accounting PDF exports.

This module was referenced by pdf_payroll_accounting_widget but was missing
from the repository. The class below preserves imports so the desktop app can
launch. Methods intentionally return None when the legacy implementation is
unavailable.
"""

from __future__ import annotations

import logging
logger = logging.getLogger(__name__)


class PayrollAccountingPDFFiller:
    """Best-effort compatibility implementation.

    If the original legacy implementation is unavailable, these methods log a
    warning and return None so callers can show a user-facing failure message
    without crashing on import.
    """

    def __init__(self) -> None:
        self._logger = logger

    def _missing(self, feature: str) -> None:
        self._logger.warning(
            "PayrollAccountingPDFFiller fallback active; feature unavailable: %s",
            feature,
        )

    def generate_t4_slip(self, employee_id: int, tax_year: int, output_path: str) -> str | None:
        self._missing("generate_t4_slip")
        return None

    def generate_paystub(self, employee_id: int, year: int, month: int, output_path: str) -> str | None:
        self._missing("generate_paystub")
        return None

    def generate_invoice_pdf(self, invoice_id: int, output_path: str) -> str | None:
        self._missing("generate_invoice_pdf")
        return None

    def generate_expense_report(self, start_date: str, end_date: str, output_path: str) -> str | None:
        self._missing("generate_expense_report")
        return None

    def generate_vendor_statement(self, vendor_name: str, output_path: str) -> str | None:
        self._missing("generate_vendor_statement")
        return None
