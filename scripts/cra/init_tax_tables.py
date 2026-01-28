#!/usr/bin/env python
"""
Initialize core tax tables for GST/HST, payroll, and corporate filings.
Idempotent: safe to run multiple times.
"""

import sys
from textwrap import dedent
from pathlib import Path

try:
    from .db import get_connection
except Exception:  # pragma: no cover
    sys.path.append(str(Path(__file__).resolve().parent))
    from db import get_connection  # type: ignore

DDL_STATEMENTS = [
    dedent(
        """
        CREATE TABLE IF NOT EXISTS tax_periods (
            id SERIAL PRIMARY KEY,
            label TEXT NOT NULL UNIQUE,
            period_type TEXT NOT NULL DEFAULT 'gst',
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            year INTEGER NOT NULL,
            quarter INTEGER,
            created_at TIMESTAMP DEFAULT NOW()
        );
        """
    ),
    dedent(
        """
        CREATE TABLE IF NOT EXISTS tax_returns (
            id SERIAL PRIMARY KEY,
            period_id INTEGER NOT NULL REFERENCES tax_periods(id) ON DELETE CASCADE,
            form_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            calculated_amount NUMERIC(14,2) DEFAULT 0,
            filed_amount NUMERIC(14,2),
            filed_at TIMESTAMP,
            reference TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            UNIQUE (period_id, form_type)
        );
        """
    ),
    dedent(
        """
        CREATE TABLE IF NOT EXISTS tax_variances (
            id SERIAL PRIMARY KEY,
            tax_return_id INTEGER NOT NULL REFERENCES tax_returns(id) ON DELETE CASCADE,
            field TEXT NOT NULL,
            actual NUMERIC(14,2),
            expected NUMERIC(14,2),
            severity TEXT DEFAULT 'info',
            message TEXT,
            recommendation TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
        """
    ),
    dedent(
        """
        CREATE TABLE IF NOT EXISTS tax_overrides (
            id SERIAL PRIMARY KEY,
            entity_type TEXT NOT NULL,
            entity_id TEXT,
            field TEXT NOT NULL,
            override_data JSONB NOT NULL,
            reason TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
        """
    ),
    dedent(
        """
        CREATE TABLE IF NOT EXISTS tax_remittances (
            id SERIAL PRIMARY KEY,
            tax_return_id INTEGER NOT NULL REFERENCES tax_returns(id) ON DELETE CASCADE,
            kind TEXT NOT NULL DEFAULT 'gst',
            amount NUMERIC(14,2) NOT NULL DEFAULT 0,
            paid_at DATE,
            reference TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
        """
    ),
    dedent(
        """
        CREATE TABLE IF NOT EXISTS tax_rollovers (
            id SERIAL PRIMARY KEY,
            rollover_type TEXT NOT NULL,
            from_year INTEGER,
            to_year INTEGER,
            amount NUMERIC(14,2) NOT NULL DEFAULT 0,
            expires_year INTEGER,
            created_at TIMESTAMP DEFAULT NOW()
        );
        """
    ),
    "CREATE INDEX IF NOT EXISTS idx_tax_periods_year ON tax_periods(year);",
    "CREATE INDEX IF NOT EXISTS idx_tax_returns_form ON tax_returns(form_type);",
    "CREATE INDEX IF NOT EXISTS idx_tax_variances_return ON tax_variances(tax_return_id);",
    "CREATE INDEX IF NOT EXISTS idx_tax_remittances_return ON tax_remittances(tax_return_id);",
]


def main() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            for ddl in DDL_STATEMENTS:
                cur.execute(ddl)
        conn.commit()
    print("✅ Tax tables ensured (idempotent)")


if __name__ == "__main__":
    main()
