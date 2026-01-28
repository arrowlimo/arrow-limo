-- Create employee_qualifications table to track certifications/permits with dates
CREATE TABLE IF NOT EXISTS employee_qualifications (
    qualification_id SERIAL PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE,
    qualification_type VARCHAR(255) NOT NULL,
    qualification_date DATE NOT NULL,
    expiry_date DATE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_employee_qualifications_employee_id ON employee_qualifications(employee_id);
CREATE INDEX IF NOT EXISTS idx_employee_qualifications_type ON employee_qualifications(qualification_type);
CREATE INDEX IF NOT EXISTS idx_employee_qualifications_expiry ON employee_qualifications(expiry_date);
