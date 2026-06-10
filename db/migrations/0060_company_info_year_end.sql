-- Migration: company_info, year_end_notes, year_end_archive
-- Arrow Limousine & Sedan Services Ltd

CREATE TABLE IF NOT EXISTS company_info (
    info_id SERIAL PRIMARY KEY,
    field_name VARCHAR(100) NOT NULL UNIQUE,
    field_value TEXT,
    last_verified_year INT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO company_info (field_name, field_value, last_verified_year) VALUES
  ('legal_name',            'Arrow Limousine & Sedan Services Ltd', 2025),
  ('trade_name',            'Arrow Limousine',                      2025),
  ('business_number',       '861556827',                            2025),
  ('payroll_account',       '861556827RP0001',                      2025),
  ('gst_account',           '861556827RT0001',                      2025),
  ('address_line1',         '3-6841 52 Ave',                        2025),
  ('address_city',          'Red Deer',                             2025),
  ('address_province',      'AB',                                   2025),
  ('address_postal',        'T4P 2Z1',                              2025),
  ('address_country',       'Canada',                               2025),
  ('phone',                 '',                                     2025),
  ('email',                 '',                                     2025),
  ('fiscal_year_end',       'December 31',                          2025),
  ('incorporation_province','AB',                                   2025),
  ('naics_code',            '485310',                               2025),
  ('wcb_account',           '',                                     2025)
ON CONFLICT (field_name) DO NOTHING;

CREATE TABLE IF NOT EXISTS year_end_notes (
    note_id     SERIAL PRIMARY KEY,
    tax_year    INT NOT NULL,
    category    VARCHAR(50)  NOT NULL DEFAULT 'General',
    note_type   VARCHAR(20)  NOT NULL DEFAULT 'note',
    subject     VARCHAR(200),
    body        TEXT,
    status      VARCHAR(30)  DEFAULT 'open',
    assigned_to VARCHAR(100),
    resolved_at DATE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_yen_year ON year_end_notes(tax_year);

CREATE TABLE IF NOT EXISTS year_end_archive (
    archive_id         SERIAL PRIMARY KEY,
    tax_year           INT     NOT NULL UNIQUE,
    closed_at          TIMESTAMPTZ,
    closed_by          VARCHAR(100),
    gl_snapshot        JSONB,
    payroll_summary    JSONB,
    checklist_summary  JSONB,
    t4_count           INT,
    t4_total_gross     NUMERIC(14,2),
    remittance_total   NUMERIC(14,2),
    notes              TEXT,
    created_at         TIMESTAMPTZ DEFAULT NOW()
);
