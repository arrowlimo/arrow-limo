-- CRA-registered company details, stored as a simple key/value table.
--
-- The desktop Year-End Audit wizard (desktop_app/year_end_wizard_widget.py) and
-- the T4 form filler (desktop_app/t4_official_form_filler.py) both read employer
-- details from `company_info` via `SELECT field_name, field_value FROM company_info`,
-- upsert with `ON CONFLICT (field_name)`, and stamp `last_verified_year`.
--
-- The table was never created on Neon, so the Year-End wizard's Company Info step
-- failed to load with `relation "company_info" does not exist`. The T4 filler
-- already falls back to hardcoded defaults, but the wizard surfaced the error.
--
-- This table is the single source of those details for both consumers.
--
-- Idempotent: safe to run multiple times.

CREATE TABLE IF NOT EXISTS company_info (
    field_name         TEXT PRIMARY KEY,
    field_value        TEXT,
    last_verified_year INTEGER,
    updated_at         TIMESTAMP DEFAULT NOW()
);
