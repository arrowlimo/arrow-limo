"""Canonical audit event catalog and system inventory."""

from __future__ import annotations

AUDIT_EVENT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://arrowlimo.local/schemas/audit_event.schema.json",
    "title": "AuditEvent",
    "type": "object",
    "required": [
        "event_id",
        "occurred_at",
        "module",
        "entity_type",
        "entity_id",
        "action",
        "source",
        "actor",
        "retention_until",
    ],
    "properties": {
        "event_id": {"type": "string", "minLength": 1},
        "occurred_at": {"type": "string", "format": "date-time"},
        "module": {"type": "string", "minLength": 1},
        "entity_type": {"type": "string", "minLength": 1},
        "entity_id": {"type": "string", "minLength": 1},
        "action": {"type": "string", "minLength": 1},
        "source": {"type": "string", "minLength": 1},
        "correlation_id": {"type": ["string", "null"]},
        "actor": {
            "type": "object",
            "required": ["actor_type"],
            "properties": {
                "actor_type": {"type": "string", "enum": ["user", "service", "system"]},
                "user_id": {"type": ["string", "null"]},
                "username": {"type": ["string", "null"]},
                "role": {"type": ["string", "null"]},
            },
        },
        "before": {"type": ["object", "null"]},
        "after": {"type": ["object", "null"]},
        "evidence_links": {"type": "array", "items": {"type": "string"}},
        "retention_until": {"type": "string", "format": "date"},
        "note": {"type": ["string", "null"]},
        "prev_hash": {"type": ["string", "null"]},
        "event_hash": {"type": ["string", "null"]},
    },
}


SYSTEM_INVENTORY = {
    "booking_dispatch_driverpay_invoicing_reporting": {
        "modules": [
            "modern_backend/app/routers/bookings.py",
            "modern_backend/app/routers/charters.py",
            "modern_backend/app/routers/payments.py",
            "modern_backend/app/routers/invoices.py",
            "modern_backend/app/routers/reports.py",
            "desktop_app/charter_form_widget.py",
            "desktop_app/accounting_control_center_widget.py",
        ],
        "data_stores": [
            "charters",
            "charter_routes",
            "payments",
            "invoices",
            "receipts",
            "general_ledger",
            "cash_box_transactions",
        ],
        "exports": [
            "/api/reports/income-summary",
            "/api/reports/pl-summary",
            "/api/reports/trial-balance",
            "/api/reports/driver-pay",
            "/api/reports/invoiced-charges",
            "/api/reports/cra-audit-export",
        ],
    },
    "employee_onboarding_payroll_cra": {
        "modules": [
            "modern_backend/app/routers/employees.py",
            "modern_backend/app/routers/payroll_entries.py",
            "modern_backend/app/routers/payroll_tax.py",
            "modern_backend/app/routers/payroll_compliance.py",
            "modern_backend/app/routers/continuous_employment.py",
            "modern_backend/app/routers/t2_returns.py",
            "modern_backend/app/routers/year_end.py",
            "desktop_app/payroll_entry_widget.py",
        ],
        "data_stores": [
            "employees",
            "payroll_entries",
            "driver_payroll",
            "employee_t4_records",
            "cra_pd7a_returns",
            "employee_roe_records",
            "t2_return_metadata",
        ],
        "exports": [
            "/api/t4/pdf/{employee_id}/{year}",
            "/api/t4/xml/{employee_id}/{year}",
            "/api/payroll-compliance/pd7a/{year}?format=csv",
            "/api/year-end/status/{fiscal_year}",
            "/api/year-end/report/{fiscal_year}",
        ],
    },
    "file_storage_and_records": {
        "modules": [
            "modern_backend/app/routers/file_storage.py",
            "desktop_app/db_connection.py",
        ],
        "data_stores": [
            "Z:/limo_files",
        ],
        "exports": [
            "uploaded payroll/tax supporting documents",
            "charter PDFs",
            "T4/PD7A artifacts",
        ],
    },
}


AUDIT_EVENT_CATALOG = [
    {
        "category": "Identity and access",
        "events": [
            "user_login",
            "user_logout",
            "role_change",
            "permission_grant",
            "permission_revoke",
            "password_reset",
            "session_extension",
        ],
    },
    {
        "category": "Dispatch and booking",
        "events": [
            "booking_created",
            "booking_updated",
            "booking_cancelled",
            "dispatch_assigned",
            "dispatch_reassigned",
            "dispatch_locked",
            "dispatch_unlocked",
            "trip_route_added",
            "trip_route_updated",
            "trip_route_deleted",
        ],
    },
    {
        "category": "Driver pay and payroll",
        "events": [
            "payroll_entry_created",
            "payroll_entry_updated",
            "payroll_entry_posted",
            "driver_pay_created",
            "driver_pay_updated",
            "remittance_period_created",
            "remittance_period_submitted",
            "t4_entry_created",
            "t4_entry_updated",
            "roe_created",
            "roe_submitted",
        ],
    },
    {
        "category": "Invoicing and receipts",
        "events": [
            "invoice_created",
            "invoice_updated",
            "invoice_voided",
            "receipt_matched",
            "receipt_unmatched",
            "payment_recorded",
            "payment_reversed",
        ],
    },
    {
        "category": "Accounting and banking",
        "events": [
            "gl_entry_created",
            "gl_entry_reclassified",
            "bank_transaction_imported",
            "bank_transaction_matched",
            "bank_transaction_unmatched",
            "reconciliation_closed",
            "reconciliation_reopened",
        ],
    },
    {
        "category": "Year-end and CRA",
        "events": [
            "year_end_checklist_item_updated",
            "year_end_close_started",
            "year_end_close_completed",
            "year_end_rollover_created",
            "pd7a_return_created",
            "pd7a_return_submitted",
            "t2_return_prepared",
            "t2_return_submitted",
            "t4_summary_generated",
            "audit_package_generated",
        ],
    },
    {
        "category": "Records and files",
        "events": [
            "file_uploaded",
            "file_downloaded",
            "file_deleted",
            "file_linked_to_record",
            "file_unlinked_from_record",
        ],
    },
]


def get_audit_event_catalog() -> list[dict]:
    return AUDIT_EVENT_CATALOG


def get_system_inventory() -> dict:
    return SYSTEM_INVENTORY
