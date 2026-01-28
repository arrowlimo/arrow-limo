-- ====================================
-- NON-CHARTER EMPLOYEE BOOKING SYSTEM
-- ====================================
-- Created: October 21, 2025
-- Purpose: Extend dispatch dashboard to manage monthly employees, part-time workers, 
--          volunteers, accountants, bookkeepers with time tracking and payroll integration

-- 1. Employee Work Classifications
-- ===============================
CREATE TABLE employee_work_classifications (
    classification_id SERIAL PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(employee_id),
    classification_type VARCHAR(50) NOT NULL, -- 'chauffeur', 'dispatcher', 'accountant', 'bookkeeper', 'cleaner', 'part_time', 'volunteer'
    pay_structure VARCHAR(20) NOT NULL,      -- 'hourly', 'salary', 'contract', 'volunteer'
    hourly_rate DECIMAL(8,2),               -- For hourly employees
    monthly_salary DECIMAL(10,2),           -- For salaried employees
    annual_salary DECIMAL(12,2),            -- For annual salary tracking
    overtime_rate DECIMAL(8,2),             -- Overtime rate if applicable
    effective_start_date DATE NOT NULL,
    effective_end_date DATE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Employee Schedules and Work Assignments
-- ==========================================
CREATE TABLE employee_schedules (
    schedule_id SERIAL PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(employee_id),
    work_date DATE NOT NULL,
    work_type VARCHAR(50) NOT NULL,         -- 'regular', 'overtime', 'holiday', 'on_call', 'training'
    classification_type VARCHAR(50) NOT NULL, -- Links to work classification
    scheduled_start_time TIME,
    scheduled_end_time TIME,
    actual_start_time TIME,
    actual_end_time TIME,
    break_duration_minutes INTEGER DEFAULT 0,
    total_hours_scheduled DECIMAL(5,2),
    total_hours_worked DECIMAL(5,2),
    hourly_rate DECIMAL(8,2),               -- Rate for this specific work
    location VARCHAR(200),                  -- Work location (office, client site, remote)
    description TEXT,                       -- Work description/tasks
    status VARCHAR(20) DEFAULT 'scheduled', -- 'scheduled', 'in_progress', 'completed', 'cancelled', 'no_show'
    approved_by INTEGER REFERENCES employees(employee_id), -- Dispatcher/supervisor approval
    approved_at TIMESTAMP,
    created_by INTEGER REFERENCES employees(employee_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Time Off Management
-- ======================
CREATE TABLE employee_time_off_requests (
    request_id SERIAL PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(employee_id),
    time_off_type VARCHAR(30) NOT NULL,     -- 'vacation', 'sick', 'personal', 'holiday', 'unpaid', 'bereavement', 'training'
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    total_days_requested DECIMAL(4,2),
    total_hours_requested DECIMAL(6,2),
    reason TEXT,
    is_paid BOOLEAN DEFAULT TRUE,
    status VARCHAR(20) DEFAULT 'pending',   -- 'pending', 'approved', 'denied', 'cancelled'
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_by INTEGER REFERENCES employees(employee_id),
    reviewed_at TIMESTAMP,
    review_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Monthly Work Assignments (Non-Charter)
-- =========================================
CREATE TABLE monthly_work_assignments (
    assignment_id SERIAL PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(employee_id),
    work_month DATE NOT NULL,               -- First day of the month
    assignment_type VARCHAR(50) NOT NULL,   -- 'bookkeeping', 'cleaning', 'maintenance', 'administration', 'accounting'
    client_account_number VARCHAR(20),      -- If work is for specific client
    project_name VARCHAR(100),
    estimated_hours DECIMAL(6,2),
    actual_hours DECIMAL(6,2),
    hourly_rate DECIMAL(8,2),
    fixed_amount DECIMAL(10,2),             -- For fixed-price work
    status VARCHAR(20) DEFAULT 'assigned',  -- 'assigned', 'in_progress', 'completed', 'billed', 'paid'
    start_date DATE,
    completion_date DATE,
    description TEXT,
    notes TEXT,
    assigned_by INTEGER REFERENCES employees(employee_id),
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. Non-Charter Payroll Processing
-- =================================
CREATE TABLE non_charter_payroll (
    payroll_id SERIAL PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(employee_id),
    pay_period_start DATE NOT NULL,
    pay_period_end DATE NOT NULL,
    pay_date DATE,
    classification_type VARCHAR(50),
    
    -- Regular Hours and Pay
    regular_hours DECIMAL(6,2) DEFAULT 0,
    overtime_hours DECIMAL(6,2) DEFAULT 0,
    holiday_hours DECIMAL(6,2) DEFAULT 0,
    regular_rate DECIMAL(8,2),
    overtime_rate DECIMAL(8,2),
    holiday_rate DECIMAL(8,2),
    
    -- Salary Information
    monthly_salary DECIMAL(10,2),
    prorated_salary DECIMAL(10,2),         -- For partial months
    
    -- Calculated Amounts
    gross_regular_pay DECIMAL(10,2) DEFAULT 0,
    gross_overtime_pay DECIMAL(10,2) DEFAULT 0,
    gross_holiday_pay DECIMAL(10,2) DEFAULT 0,
    gross_salary_pay DECIMAL(10,2) DEFAULT 0,
    total_gross_pay DECIMAL(10,2) DEFAULT 0,
    
    -- Deductions
    cpp_deduction DECIMAL(8,2) DEFAULT 0,
    ei_deduction DECIMAL(8,2) DEFAULT 0,
    tax_deduction DECIMAL(8,2) DEFAULT 0,
    other_deductions DECIMAL(8,2) DEFAULT 0,
    total_deductions DECIMAL(10,2) DEFAULT 0,
    
    -- Net Pay
    net_pay DECIMAL(10,2) DEFAULT 0,
    
    -- Expense Reimbursements
    expense_reimbursements DECIMAL(8,2) DEFAULT 0,
    
    -- Status and Approval
    status VARCHAR(20) DEFAULT 'draft',     -- 'draft', 'approved', 'processed', 'paid'
    approved_by INTEGER REFERENCES employees(employee_id),
    approved_at TIMESTAMP,
    processed_at TIMESTAMP,
    
    -- T4 Integration (same as driver_payroll)
    t4_box_14 DECIMAL(10,2),               -- Employment income
    t4_box_16 DECIMAL(8,2),                -- CPP contributions
    t4_box_18 DECIMAL(8,2),                -- EI contributions
    t4_box_22 DECIMAL(8,2),                -- Income tax deducted
    t4_box_24 DECIMAL(10,2),               -- EI insurable earnings
    t4_box_26 DECIMAL(10,2),               -- CPP pensionable earnings
    
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 6. Employee Expense Tracking
-- ============================
CREATE TABLE employee_expenses (
    expense_id SERIAL PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(employee_id),
    receipt_id INTEGER REFERENCES receipts(receipt_id), -- Link to existing receipts system
    expense_date DATE NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    gst_amount DECIMAL(8,2) DEFAULT 0,
    net_amount DECIMAL(10,2),
    category VARCHAR(50),                   -- 'travel', 'office_supplies', 'training', 'equipment', 'communication'
    subcategory VARCHAR(50),
    vendor_name VARCHAR(200),
    description TEXT,
    work_assignment_id INTEGER REFERENCES monthly_work_assignments(assignment_id),
    
    -- Business/Personal Classification
    is_business_expense BOOLEAN DEFAULT TRUE,
    business_percentage DECIMAL(5,2) DEFAULT 100.00,
    
    -- Reimbursement Tracking
    is_reimbursable BOOLEAN DEFAULT TRUE,
    reimbursement_status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'approved', 'denied', 'paid'
    reimbursed_amount DECIMAL(10,2),
    reimbursed_date DATE,
    
    -- Approval Workflow
    submitted_by INTEGER REFERENCES employees(employee_id),
    submitted_at TIMESTAMP,
    approved_by INTEGER REFERENCES employees(employee_id),
    approved_at TIMESTAMP,
    approval_notes TEXT,
    
    -- Receipt Management
    receipt_image_path VARCHAR(500),
    receipt_uploaded BOOLEAN DEFAULT FALSE,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 7. Employee Availability and Preferences
-- ========================================
CREATE TABLE employee_availability (
    availability_id SERIAL PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(employee_id),
    day_of_week INTEGER NOT NULL,          -- 0=Sunday, 1=Monday, etc.
    available_start_time TIME,
    available_end_time TIME,
    is_available BOOLEAN DEFAULT TRUE,
    max_hours_per_day DECIMAL(4,2),
    preferred_work_types TEXT[],           -- Array of work types employee can do
    notes TEXT,
    effective_start_date DATE NOT NULL,
    effective_end_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 8. Payroll Approval Workflow
-- ============================
CREATE TABLE payroll_approval_workflow (
    workflow_id SERIAL PRIMARY KEY,
    payroll_id INTEGER REFERENCES non_charter_payroll(payroll_id),
    driver_payroll_id INTEGER REFERENCES driver_payroll(id), -- For charter-based payroll
    workflow_type VARCHAR(20) NOT NULL,    -- 'non_charter', 'charter', 'expense'
    current_step VARCHAR(30) NOT NULL,     -- 'time_entry', 'supervisor_review', 'dispatcher_approval', 'payroll_processing'
    status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'approved', 'rejected', 'completed'
    
    -- Step-by-step tracking
    time_submitted TIMESTAMP,
    supervisor_reviewed_at TIMESTAMP,
    supervisor_reviewed_by INTEGER REFERENCES employees(employee_id),
    dispatcher_approved_at TIMESTAMP,
    dispatcher_approved_by INTEGER REFERENCES employees(employee_id),
    payroll_processed_at TIMESTAMP,
    payroll_processed_by INTEGER REFERENCES employees(employee_id),
    
    comments TEXT,
    rejection_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ===============================
-- INDEXES FOR PERFORMANCE
-- ===============================

-- Employee Work Classifications
CREATE INDEX idx_employee_work_classifications_employee_id ON employee_work_classifications(employee_id);
CREATE INDEX idx_employee_work_classifications_active ON employee_work_classifications(is_active, effective_start_date, effective_end_date);

-- Employee Schedules
CREATE INDEX idx_employee_schedules_employee_id ON employee_schedules(employee_id);
CREATE INDEX idx_employee_schedules_work_date ON employee_schedules(work_date);
CREATE INDEX idx_employee_schedules_status ON employee_schedules(status);
CREATE INDEX idx_employee_schedules_approval ON employee_schedules(approved_by, approved_at);

-- Time Off Requests
CREATE INDEX idx_time_off_requests_employee_id ON employee_time_off_requests(employee_id);
CREATE INDEX idx_time_off_requests_dates ON employee_time_off_requests(start_date, end_date);
CREATE INDEX idx_time_off_requests_status ON employee_time_off_requests(status);

-- Monthly Work Assignments
CREATE INDEX idx_monthly_work_assignments_employee_id ON monthly_work_assignments(employee_id);
CREATE INDEX idx_monthly_work_assignments_month ON monthly_work_assignments(work_month);
CREATE INDEX idx_monthly_work_assignments_status ON monthly_work_assignments(status);

-- Non-Charter Payroll
CREATE INDEX idx_non_charter_payroll_employee_id ON non_charter_payroll(employee_id);
CREATE INDEX idx_non_charter_payroll_pay_period ON non_charter_payroll(pay_period_start, pay_period_end);
CREATE INDEX idx_non_charter_payroll_status ON non_charter_payroll(status);

-- Employee Expenses
CREATE INDEX idx_employee_expenses_employee_id ON employee_expenses(employee_id);
CREATE INDEX idx_employee_expenses_date ON employee_expenses(expense_date);
CREATE INDEX idx_employee_expenses_reimbursement ON employee_expenses(reimbursement_status);

-- Employee Availability
CREATE INDEX idx_employee_availability_employee_id ON employee_availability(employee_id);
CREATE INDEX idx_employee_availability_day ON employee_availability(day_of_week, is_available);

-- Payroll Approval Workflow
CREATE INDEX idx_payroll_approval_workflow_status ON payroll_approval_workflow(status, current_step);
CREATE INDEX idx_payroll_approval_workflow_type ON payroll_approval_workflow(workflow_type);

-- ===============================
-- TRIGGERS FOR AUTOMATIC UPDATES
-- ===============================

-- Update timestamps
CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply update triggers to all tables
CREATE TRIGGER update_employee_work_classifications_timestamp 
    BEFORE UPDATE ON employee_work_classifications 
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER update_employee_schedules_timestamp 
    BEFORE UPDATE ON employee_schedules 
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER update_time_off_requests_timestamp 
    BEFORE UPDATE ON employee_time_off_requests 
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER update_monthly_work_assignments_timestamp 
    BEFORE UPDATE ON monthly_work_assignments 
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER update_non_charter_payroll_timestamp 
    BEFORE UPDATE ON non_charter_payroll 
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER update_employee_expenses_timestamp 
    BEFORE UPDATE ON employee_expenses 
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER update_employee_availability_timestamp 
    BEFORE UPDATE ON employee_availability 
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER update_payroll_approval_workflow_timestamp 
    BEFORE UPDATE ON payroll_approval_workflow 
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

-- ===============================
-- SAMPLE DATA FOR TESTING
-- ===============================

-- Insert sample work classifications
INSERT INTO employee_work_classifications (employee_id, classification_type, pay_structure, hourly_rate, monthly_salary, effective_start_date) VALUES
(1, 'bookkeeper', 'hourly', 25.00, NULL, '2025-01-01'),
(2, 'cleaner', 'hourly', 18.00, NULL, '2025-01-01'),
(3, 'accountant', 'salary', NULL, 4500.00, '2025-01-01'),
(4, 'dispatcher', 'salary', NULL, 3800.00, '2025-01-01'),
(5, 'part_time', 'hourly', 16.50, NULL, '2025-01-01');

COMMENT ON TABLE employee_work_classifications IS 'Defines how employees are classified and paid - extends beyond just chauffeurs';
COMMENT ON TABLE employee_schedules IS 'Tracks work schedules for non-charter employees with time tracking and approval';
COMMENT ON TABLE employee_time_off_requests IS 'Manages vacation, sick time, and other time off requests with approval workflow';
COMMENT ON TABLE monthly_work_assignments IS 'Tracks ongoing work assignments for bookkeeping, cleaning, and other non-charter work';
COMMENT ON TABLE non_charter_payroll IS 'Payroll processing for salaried and hourly employees separate from charter-based pay';
COMMENT ON TABLE employee_expenses IS 'Expense tracking and reimbursement for all employees integrated with receipts system';
COMMENT ON TABLE employee_availability IS 'Tracks when employees are available for work and their preferences';
COMMENT ON TABLE payroll_approval_workflow IS 'Manages the approval process for all types of payroll entries';