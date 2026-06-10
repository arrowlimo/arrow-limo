from fastapi import Depends, FastAPI

from ..api import receipt_verification as receipt_verification_router
from ..audit import router as audit_router
from ..auth import get_current_user, require_any_modules
from ..routers import accounting as accounting_router
from ..routers import (
    bank_audit_reconciliation as bank_audit_reconciliation_router,
)
from ..routers import banking as banking_router
from ..routers import banking_allocations as banking_allocations_router
from ..routers import beverage_order as beverage_order_router
from ..routers import beverage_reconciliation as beverage_reconciliation_router
from ..routers import bookings as bookings_router
from ..routers import cash_box as cash_box_router
from ..routers import charges as charges_router
from ..routers import charter_sheet as charter_sheet_router
from ..routers import charters as charters_router
from ..routers import chauffeur_self_service as chauffeur_self_service_router
from ..routers import continuous_employment as continuous_employment_router
from ..routers import customers as customers_router
from ..routers import driver_auth as driver_auth_router
from ..routers import employees as employees_router
from ..routers import file_storage as file_storage_router
from ..routers import inspection_forms as inspection_forms_router
from ..routers import invoices as invoices_router
from ..routers import lookup as lookup_router
from ..routers import metrics as metrics_router
from ..routers import owe_david as owe_david_router
from ..routers import payments as payments_router
from ..routers import payroll_compliance as payroll_compliance_router
from ..routers import payroll_entries as payroll_entries_router
from ..routers import payroll_tax as payroll_tax_router
from ..routers import pdf as pdf_router
from ..routers import pricing as pricing_router
from ..routers import receipts as receipts_router
from ..routers import receipts_linked_display as receipts_linked_display_router
from ..routers import receipts_simple as receipts_simple_router
from ..routers import receipts_split as receipts_split_router
from ..routers import reconciliation_report as reconciliation_report_router
from ..routers import reports as reports_router
from ..routers import t2_returns as t2_returns_router
from ..routers import table_management as table_management_router
from ..routers import vehicles as vehicles_router
from ..routers import vendor_standardization as vendor_standardization_router
from ..routers import year_end as year_end_router
from ..routes import cheque_books as cheque_books_router
from ..routes import received_payments as received_payments_router


def register_routers(app: FastAPI) -> None:
    """Register API routers with module-based access dependencies."""
    authenticated_user = Depends(get_current_user)
    dispatch_access = Depends(require_any_modules("dispatch"))
    accounting_access = Depends(require_any_modules("accounting"))
    admin_access = Depends(require_any_modules("admin"))
    dispatch_or_accounting_access = Depends(require_any_modules("dispatch", "accounting"))
    chauffeur_access = Depends(require_any_modules("chauffeur_self_service"))

    app.include_router(driver_auth_router.router)
    app.include_router(inspection_forms_router.router)  # Secure inspection forms
    app.include_router(
        metrics_router.router,
        dependencies=[dispatch_or_accounting_access],
    )  # Dashboard metrics
    app.include_router(pdf_router.router)  # PDF generation
    app.include_router(reports_router.router, dependencies=[accounting_access])
    app.include_router(year_end_router.router, dependencies=[accounting_access])
    app.include_router(charges_router.router, dependencies=[dispatch_or_accounting_access])
    app.include_router(payments_router.router, dependencies=[dispatch_or_accounting_access])
    app.include_router(charters_router.router, dependencies=[dispatch_or_accounting_access])
    app.include_router(bookings_router.router, dependencies=[dispatch_or_accounting_access])
    app.include_router(beverage_order_router.router, dependencies=[dispatch_access])
    app.include_router(beverage_reconciliation_router.router, dependencies=[accounting_access])
    app.include_router(receipts_router.router, dependencies=[dispatch_or_accounting_access])
    app.include_router(
        receipts_simple_router.router,
        dependencies=[dispatch_or_accounting_access],
    )  # Simplified receipts matching actual schema
    app.include_router(receipts_split_router.router, dependencies=[dispatch_or_accounting_access])
    app.include_router(
        receipts_linked_display_router.router,
        dependencies=[dispatch_or_accounting_access],
    )  # Linked split receipts display
    app.include_router(
        receipt_verification_router.router,
        dependencies=[dispatch_or_accounting_access],
    )  # Receipt verification (physical match)
    app.include_router(invoices_router.router, dependencies=[accounting_access])
    app.include_router(accounting_router.router, dependencies=[accounting_access])
    app.include_router(banking_router.router, dependencies=[accounting_access])
    app.include_router(banking_allocations_router.router, dependencies=[accounting_access])
    app.include_router(vehicles_router.router, dependencies=[dispatch_access])
    app.include_router(employees_router.router, dependencies=[admin_access])
    app.include_router(customers_router.router, dependencies=[dispatch_or_accounting_access])
    app.include_router(
        owe_david_router.router, dependencies=[accounting_access]
    )  # David account tracking
    app.include_router(pricing_router.router, dependencies=[dispatch_access])
    app.include_router(
        lookup_router.router, dependencies=[authenticated_user]
    )  # Reference data lookups
    app.include_router(table_management_router.router, dependencies=[admin_access])
    app.include_router(
        t2_returns_router.router, dependencies=[accounting_access]
    )  # T2 Corporate Tax Return entry
    app.include_router(charter_sheet_router.router, dependencies=[dispatch_or_accounting_access])
    app.include_router(
        file_storage_router.router, dependencies=[authenticated_user]
    )  # File storage with role-based access
    app.include_router(
        chauffeur_self_service_router.router, dependencies=[chauffeur_access]
    )  # Chauffeur self-service scope
    app.include_router(
        payroll_tax_router.router, dependencies=[accounting_access]
    )  # Payroll & T4 form entry
    app.include_router(payroll_entries_router.router, dependencies=[accounting_access])
    app.include_router(
        continuous_employment_router.router, dependencies=[accounting_access]
    )  # ROE lifecycle + submission tracking
    app.include_router(
        payroll_compliance_router.router, dependencies=[accounting_access]
    )  # PD7A submission audit + reporting
    app.include_router(cash_box_router.router, dependencies=[accounting_access])
    app.include_router(
        reconciliation_report_router.router, dependencies=[accounting_access]
    )  # Banking-receipt reconciliation
    app.include_router(
        vendor_standardization_router.router, dependencies=[admin_access]
    )  # Vendor name standardization
    app.include_router(
        bank_audit_reconciliation_router.router, dependencies=[accounting_access]
    )  # Bank account reconciliation for auditors

    app.include_router(audit_router, dependencies=[accounting_access])

    app.include_router(
        cheque_books_router.router, dependencies=[accounting_access]
    )  # Cheque book management

    app.include_router(
        received_payments_router.router, dependencies=[accounting_access]
    )  # Record received payments
