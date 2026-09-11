-- Driver-submitted compliance record changes with admin approval.
--
-- Drivers edit their own compliance records in the web portal, but nothing
-- reaches the live employees table until an admin authorizes it in the PC app.
-- Every submission keeps the old value beside the new value so the reviewer
-- can see exactly what a driver is trying to change.

CREATE TABLE IF NOT EXISTS employee_change_requests (
    request_id BIGSERIAL PRIMARY KEY,
    batch_id BIGINT NOT NULL,
    employee_id INTEGER NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE,
    submitted_by_user_id INTEGER NULL,
    submitted_by_username VARCHAR(150) NULL,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    field_key VARCHAR(100) NOT NULL,
    field_label VARCHAR(200) NOT NULL,
    old_value TEXT NULL,
    new_value TEXT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    reviewed_by_username VARCHAR(150) NULL,
    reviewed_at TIMESTAMPTZ NULL,
    review_notes TEXT NULL,
    CONSTRAINT employee_change_requests_status_chk
        CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED'))
);

CREATE SEQUENCE IF NOT EXISTS employee_change_batch_seq;

CREATE INDEX IF NOT EXISTS idx_employee_change_requests_pending
    ON employee_change_requests (status, submitted_at DESC);

CREATE INDEX IF NOT EXISTS idx_employee_change_requests_employee
    ON employee_change_requests (employee_id, submitted_at DESC);

-- Driver-uploaded photos/scans of licences, permits and certificates.
-- Stored as bytea so the Render-hosted portal and the local PC app can both
-- reach them through Neon without a shared network drive.
CREATE TABLE IF NOT EXISTS employee_document_uploads (
    upload_id BIGSERIAL PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE,
    change_request_id BIGINT NULL
        REFERENCES employee_change_requests(request_id) ON DELETE SET NULL,
    document_type VARCHAR(60) NOT NULL,
    document_name VARCHAR(255) NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    file_size INTEGER NOT NULL,
    file_data BYTEA NOT NULL,
    issued_date DATE NULL,
    expiry_date DATE NULL,
    document_number VARCHAR(100) NULL,
    notes TEXT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    uploaded_by_username VARCHAR(150) NULL,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_by_username VARCHAR(150) NULL,
    reviewed_at TIMESTAMPTZ NULL,
    CONSTRAINT employee_document_uploads_status_chk
        CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED'))
);

CREATE INDEX IF NOT EXISTS idx_employee_document_uploads_pending
    ON employee_document_uploads (status, uploaded_at DESC);

CREATE INDEX IF NOT EXISTS idx_employee_document_uploads_employee
    ON employee_document_uploads (employee_id, uploaded_at DESC);

-- Permanent authorization trail: who changed what, who approved it, when.
CREATE TABLE IF NOT EXISTS employee_change_audit (
    audit_id BIGSERIAL PRIMARY KEY,
    request_id BIGINT NULL,
    employee_id INTEGER NOT NULL,
    field_key VARCHAR(100) NOT NULL,
    field_label VARCHAR(200) NULL,
    old_value TEXT NULL,
    new_value TEXT NULL,
    action VARCHAR(20) NOT NULL,
    submitted_by_username VARCHAR(150) NULL,
    reviewed_by_username VARCHAR(150) NULL,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    note TEXT NULL
);

CREATE INDEX IF NOT EXISTS idx_employee_change_audit_employee
    ON employee_change_audit (employee_id, reviewed_at DESC);

-- Driver-entered run details stay unconfirmed until a dispatcher verifies them.
ALTER TABLE charters
    ADD COLUMN IF NOT EXISTS driver_details_submitted_at TIMESTAMPTZ NULL;

ALTER TABLE charters
    ADD COLUMN IF NOT EXISTS dispatcher_confirmed_at TIMESTAMPTZ NULL;

ALTER TABLE charters
    ADD COLUMN IF NOT EXISTS dispatcher_confirmed_by VARCHAR(150) NULL;
