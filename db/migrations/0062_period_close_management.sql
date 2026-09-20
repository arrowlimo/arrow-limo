CREATE TABLE IF NOT EXISTS period_close_checklist (
    period_type VARCHAR NOT NULL,
    period_key VARCHAR NOT NULL,
    task_key VARCHAR NOT NULL,
    answer VARCHAR NOT NULL DEFAULT 'Later',
    notes TEXT,
    updated_by VARCHAR,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (period_type, period_key, task_key),
    CONSTRAINT period_close_checklist_answer_check
        CHECK (answer IN ('Yes', 'No', 'Later', 'In Progress'))
);

CREATE TABLE IF NOT EXISTS period_close_signoff (
    period_type VARCHAR NOT NULL,
    period_key VARCHAR NOT NULL,
    closed_by VARCHAR,
    closed_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (period_type, period_key)
);
