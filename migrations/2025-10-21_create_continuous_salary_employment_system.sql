-- =====================================================
-- CONTINUOUS SALARY EMPLOYMENT & ROE CALCULATION SYSTEM
-- =====================================================
-- Created: October 21, 2025
-- Purpose: Automated monthly salary booking, ROE calculations, 
--          end-of-employment processing, and government forms

-- 1. Continuous Employment Contracts
-- ==================================
CREATE TABLE continuous_employment_contracts (
    contract_id SERIAL PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(employee_id),
    classification_id INTEGER REFERENCES employee_work_classifications(classification_id),
    
    -- Employment Period
    employment_start_date DATE NOT NULL,
    employment_end_date DATE,                -- NULL for ongoing employment
    contract_type VARCHAR(30) NOT NULL,      -- 'permanent', 'contract', 'probation', 'seasonal'
    employment_status VARCHAR(20) DEFAULT 'active', -- 'active', 'terminated', 'laid_off', 'on_leave'
    
    -- Salary Structure
    annual_salary DECIMAL(12,2),
    monthly_salary DECIMAL(10,2) NOT NULL,
    pay_frequency VARCHAR(20) DEFAULT 'monthly', -- 'weekly', 'bi_weekly', 'monthly', 'semi_monthly'
    
    -- Benefits and Deductions
    health_benefits BOOLEAN DEFAULT FALSE,
    dental_benefits BOOLEAN DEFAULT FALSE,
    pension_contribution_rate DECIMAL(5,4) DEFAULT 0, -- Percentage
    vacation_days_per_year INTEGER DEFAULT 10,
    sick_days_per_year INTEGER DEFAULT 5,
    
    -- Automatic Booking Configuration
    auto_book_enabled BOOLEAN DEFAULT TRUE,
    booking_day_of_month INTEGER DEFAULT 1,  -- Which day of month to create payroll
    working_days_per_month DECIMAL(4,1) DEFAULT 21.75, -- For pro-rating calculations
    
    -- ROE and Government Forms
    insurable_employment BOOLEAN DEFAULT TRUE, -- For EI purposes
    pensionable_employment BOOLEAN DEFAULT TRUE, -- For CPP purposes
    
    -- Termination Information
    termination_reason VARCHAR(50),           -- 'resignation', 'dismissal', 'layoff', 'retirement', 'end_of_contract'
    termination_date DATE,
    final_pay_date DATE,
    severance_weeks DECIMAL(4,1) DEFAULT 0,
    vacation_payout DECIMAL(8,2) DEFAULT 0,
    
    -- Record Keeping
    created_by INTEGER REFERENCES employees(employee_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT valid_employment_dates CHECK (employment_end_date IS NULL OR employment_end_date >= employment_start_date),
    CONSTRAINT valid_termination_date CHECK (termination_date IS NULL OR termination_date >= employment_start_date)
);

-- 2. Automated Monthly Payroll Generation
-- =======================================
CREATE TABLE automated_salary_payroll (
    payroll_id SERIAL PRIMARY KEY,
    contract_id INTEGER NOT NULL REFERENCES continuous_employment_contracts(contract_id),
    employee_id INTEGER NOT NULL REFERENCES employees(employee_id),
    
    -- Pay Period Information
    pay_year INTEGER NOT NULL,
    pay_month INTEGER NOT NULL,
    pay_period_start DATE NOT NULL,
    pay_period_end DATE NOT NULL,
    pay_date DATE NOT NULL,
    
    -- Salary Calculation
    base_monthly_salary DECIMAL(10,2) NOT NULL,
    working_days_in_month INTEGER,
    actual_working_days DECIMAL(4,1),        -- Accounting for partial months, sick days
    proration_factor DECIMAL(6,4) DEFAULT 1.0, -- For partial months
    
    -- Calculated Amounts
    gross_salary DECIMAL(10,2) NOT NULL,
    vacation_pay DECIMAL(8,2) DEFAULT 0,     -- 4% or 6% of gross
    overtime_pay DECIMAL(8,2) DEFAULT 0,     -- Any overtime for salaried employees
    bonus_pay DECIMAL(8,2) DEFAULT 0,
    total_gross_pay DECIMAL(10,2) NOT NULL,
    
    -- Statutory Deductions
    cpp_contribution DECIMAL(8,2) DEFAULT 0,
    ei_premium DECIMAL(8,2) DEFAULT 0,
    income_tax DECIMAL(8,2) DEFAULT 0,
    
    -- Other Deductions
    health_benefits_deduction DECIMAL(6,2) DEFAULT 0,
    dental_benefits_deduction DECIMAL(6,2) DEFAULT 0,
    pension_contribution DECIMAL(8,2) DEFAULT 0,
    union_dues DECIMAL(6,2) DEFAULT 0,
    other_deductions DECIMAL(8,2) DEFAULT 0,
    total_deductions DECIMAL(10,2) DEFAULT 0,
    
    -- Net Pay
    net_pay DECIMAL(10,2) NOT NULL,
    
    -- Government Reporting
    insurable_earnings DECIMAL(10,2),         -- For EI calculations
    pensionable_earnings DECIMAL(10,2),       -- For CPP calculations
    taxable_benefits DECIMAL(8,2) DEFAULT 0,
    
    -- T4 Integration
    t4_box_14 DECIMAL(10,2),                 -- Employment income
    t4_box_16 DECIMAL(8,2),                  -- CPP contributions  
    t4_box_18 DECIMAL(8,2),                  -- EI contributions
    t4_box_22 DECIMAL(8,2),                  -- Income tax deducted
    t4_box_24 DECIMAL(10,2),                 -- EI insurable earnings
    t4_box_26 DECIMAL(10,2),                 -- CPP pensionable earnings
    t4_box_44 DECIMAL(6,2),                  -- Union dues
    t4_box_46 DECIMAL(6,2),                  -- Charitable donations
    t4_box_52 DECIMAL(8,2),                  -- Pension adjustment
    
    -- Status and Processing
    payroll_status VARCHAR(20) DEFAULT 'generated', -- 'generated', 'approved', 'processed', 'paid', 'cancelled'
    auto_generated BOOLEAN DEFAULT TRUE,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    approved_by INTEGER REFERENCES employees(employee_id),
    approved_at TIMESTAMP,
    processed_at TIMESTAMP,
    paid_at TIMESTAMP,
    
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(contract_id, pay_year, pay_month)
);

-- 3. ROE (Record of Employment) Calculations
-- ==========================================
CREATE TABLE roe_calculations (
    roe_id SERIAL PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(employee_id),
    contract_id INTEGER REFERENCES continuous_employment_contracts(contract_id),
    
    -- ROE Basic Information
    roe_number VARCHAR(20) UNIQUE,            -- Generated ROE number
    business_number VARCHAR(15),              -- CRA business number
    
    -- Employment Information
    first_day_worked DATE NOT NULL,
    last_day_paid DATE NOT NULL,
    final_pay_period_end DATE NOT NULL,
    return_to_work_date DATE,                 -- If applicable
    
    -- Reason for ROE
    reason_code CHAR(1) NOT NULL,             -- A=Shortage of work, M=Dismissal, etc.
    reason_description TEXT,
    
    -- Insurable Hours and Earnings (Last 53 weeks or since start)
    total_insurable_hours DECIMAL(8,2) NOT NULL,
    total_insurable_earnings DECIMAL(12,2) NOT NULL,
    
    -- Pay Period Information (up to 27 pay periods)
    pay_periods_data JSONB,                   -- Array of pay period details
    
    -- Vacation Pay
    vacation_pay_percentage DECIMAL(5,2) DEFAULT 4.0, -- 4% or 6%
    vacation_pay_amount DECIMAL(10,2) DEFAULT 0,
    vacation_pay_period VARCHAR(50),
    
    -- Comments and Special Circumstances
    comments TEXT,
    expected_return_date DATE,
    recall_date DATE,
    
    -- ROE Status
    roe_status VARCHAR(20) DEFAULT 'draft',   -- 'draft', 'completed', 'submitted', 'amended'
    submitted_to_cra BOOLEAN DEFAULT FALSE,
    submission_date TIMESTAMP,
    cra_confirmation_number VARCHAR(30),
    
    -- Record Keeping
    created_by INTEGER REFERENCES employees(employee_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ROE Pay Period Details (for detailed reporting)
CREATE TABLE roe_pay_period_details (
    detail_id SERIAL PRIMARY KEY,
    roe_id INTEGER NOT NULL REFERENCES roe_calculations(roe_id) ON DELETE CASCADE,
    period_number INTEGER,                    -- 1-6 (most recent periods)
    pay_period_start DATE,
    pay_period_end DATE,
    insurable_hours DECIMAL(8,2) DEFAULT 0,
    insurable_earnings DECIMAL(12,2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. End of Employment Processing
-- ==============================
CREATE TABLE end_of_employment_processing (
    processing_id SERIAL PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(employee_id),
    contract_id INTEGER REFERENCES continuous_employment_contracts(contract_id),
    
    -- Termination Details
    termination_date DATE NOT NULL,
    last_working_day DATE NOT NULL,
    final_pay_date DATE NOT NULL,
    termination_type VARCHAR(30) NOT NULL,    -- 'voluntary', 'involuntary', 'layoff', 'retirement'
    reason_code VARCHAR(10),                  -- For government reporting
    
    -- Final Pay Calculations
    final_salary_days DECIMAL(4,1),          -- Days worked in final period
    final_salary_amount DECIMAL(10,2),
    
    -- Vacation and Benefits Payout
    vacation_days_accrued DECIMAL(5,2),
    vacation_days_used DECIMAL(5,2),
    vacation_days_owing DECIMAL(5,2),
    vacation_payout_amount DECIMAL(10,2),
    
    -- Severance and Additional Payments
    severance_weeks DECIMAL(4,1) DEFAULT 0,
    severance_amount DECIMAL(12,2) DEFAULT 0,
    bonus_payout DECIMAL(10,2) DEFAULT 0,
    commission_payout DECIMAL(10,2) DEFAULT 0,
    
    -- Benefits Continuation
    health_benefits_end_date DATE,
    dental_benefits_end_date DATE,
    group_insurance_conversion BOOLEAN DEFAULT FALSE,
    
    -- Government Forms Required
    roe_required BOOLEAN DEFAULT TRUE,
    t4_slip_required BOOLEAN DEFAULT TRUE,
    final_cpp_ei_required BOOLEAN DEFAULT TRUE,
    
    -- Total Final Pay
    total_gross_final_pay DECIMAL(12,2),
    total_deductions_final_pay DECIMAL(10,2),
    total_net_final_pay DECIMAL(12,2),
    
    -- Processing Status
    processing_status VARCHAR(30) DEFAULT 'pending', -- 'pending', 'in_progress', 'completed'
    final_pay_processed BOOLEAN DEFAULT FALSE,
    roe_generated BOOLEAN DEFAULT FALSE,
    t4_generated BOOLEAN DEFAULT FALSE,
    benefits_terminated BOOLEAN DEFAULT FALSE,
    
    -- Completion Tracking
    completed_by INTEGER REFERENCES employees(employee_id),
    completed_at TIMESTAMP,
    
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. Government Tax Rates and Tables
-- ==================================
CREATE TABLE government_tax_rates (
    rate_id SERIAL PRIMARY KEY,
    tax_year INTEGER NOT NULL,
    province_code CHAR(2) NOT NULL,           -- AB, ON, BC, etc.
    
    -- CPP Rates
    cpp_contribution_rate DECIMAL(6,4),      -- Employee rate
    cpp_employer_rate DECIMAL(6,4),          -- Employer rate
    cpp_max_pensionable_earnings DECIMAL(10,2),
    cpp_basic_exemption DECIMAL(8,2),
    
    -- EI Rates
    ei_premium_rate DECIMAL(6,4),            -- Employee rate
    ei_employer_rate DECIMAL(6,4),           -- Employer rate (1.4x employee)
    ei_max_insurable_earnings DECIMAL(10,2),
    
    -- Federal Tax Brackets
    federal_tax_brackets JSONB,              -- Array of tax brackets and rates
    
    -- Provincial Tax Brackets
    provincial_tax_brackets JSONB,           -- Province-specific tax brackets
    
    -- Other Rates
    vacation_pay_minimum_rate DECIMAL(5,2) DEFAULT 4.0, -- 4% minimum
    
    effective_date DATE NOT NULL,
    expiry_date DATE,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(tax_year, province_code)
);

-- 6. Employee Time Off Accruals
-- =============================
CREATE TABLE employee_time_off_accruals (
    accrual_id SERIAL PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(employee_id),
    contract_id INTEGER REFERENCES continuous_employment_contracts(contract_id),
    accrual_year INTEGER NOT NULL,
    
    -- Vacation Time
    vacation_days_entitled DECIMAL(5,2),     -- Based on years of service
    vacation_days_accrued DECIMAL(5,2) DEFAULT 0,
    vacation_days_used DECIMAL(5,2) DEFAULT 0,
    vacation_days_carried_forward DECIMAL(5,2) DEFAULT 0,
    vacation_days_available DECIMAL(5,2) DEFAULT 0,
    
    -- Sick Time
    sick_days_entitled DECIMAL(5,2),
    sick_days_accrued DECIMAL(5,2) DEFAULT 0,
    sick_days_used DECIMAL(5,2) DEFAULT 0,
    sick_days_available DECIMAL(5,2) DEFAULT 0,
    
    -- Personal Days
    personal_days_entitled DECIMAL(5,2) DEFAULT 0,
    personal_days_used DECIMAL(5,2) DEFAULT 0,
    personal_days_available DECIMAL(5,2) DEFAULT 0,
    
    -- Accrual Calculations (monthly)
    vacation_accrual_rate DECIMAL(6,4),      -- Days per month
    sick_accrual_rate DECIMAL(6,4),          -- Days per month
    
    -- Last Update Tracking
    last_accrual_date DATE,
    next_accrual_date DATE,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(employee_id, accrual_year)
);

-- ===============================
-- INDEXES FOR PERFORMANCE
-- ===============================

-- Continuous Employment Contracts
CREATE INDEX idx_continuous_employment_employee_id ON continuous_employment_contracts(employee_id);
CREATE INDEX idx_continuous_employment_status ON continuous_employment_contracts(employment_status);
CREATE INDEX idx_continuous_employment_auto_book ON continuous_employment_contracts(auto_book_enabled, employment_status);
CREATE INDEX idx_continuous_employment_dates ON continuous_employment_contracts(employment_start_date, employment_end_date);

-- Automated Salary Payroll
CREATE INDEX idx_automated_salary_payroll_employee_id ON automated_salary_payroll(employee_id);
CREATE INDEX idx_automated_salary_payroll_period ON automated_salary_payroll(pay_year, pay_month);
CREATE INDEX idx_automated_salary_payroll_status ON automated_salary_payroll(payroll_status);
CREATE INDEX idx_automated_salary_payroll_auto ON automated_salary_payroll(auto_generated);

-- ROE Calculations
CREATE INDEX idx_roe_calculations_employee_id ON roe_calculations(employee_id);
CREATE INDEX idx_roe_calculations_status ON roe_calculations(roe_status);
CREATE INDEX idx_roe_calculations_dates ON roe_calculations(first_day_worked, last_day_paid);

-- End of Employment Processing
CREATE INDEX idx_end_employment_employee_id ON end_of_employment_processing(employee_id);
CREATE INDEX idx_end_employment_status ON end_of_employment_processing(processing_status);
CREATE INDEX idx_end_employment_date ON end_of_employment_processing(termination_date);

-- Government Tax Rates
CREATE INDEX idx_government_tax_rates_year ON government_tax_rates(tax_year);
CREATE INDEX idx_government_tax_rates_province ON government_tax_rates(province_code);

-- Time Off Accruals
CREATE INDEX idx_time_off_accruals_employee_id ON employee_time_off_accruals(employee_id);
CREATE INDEX idx_time_off_accruals_year ON employee_time_off_accruals(accrual_year);

-- ===============================
-- TRIGGERS AND FUNCTIONS
-- ===============================

-- Function to calculate monthly salary pro-ration
CREATE OR REPLACE FUNCTION calculate_salary_proration(
    base_salary DECIMAL(10,2),
    total_days INTEGER,
    working_days DECIMAL(4,1),
    standard_working_days DECIMAL(4,1) DEFAULT 21.75
) RETURNS DECIMAL(10,2) AS $$
BEGIN
    IF working_days >= standard_working_days THEN
        RETURN base_salary;
    ELSE
        RETURN ROUND(base_salary * (working_days / standard_working_days), 2);
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Function to calculate vacation accrual
CREATE OR REPLACE FUNCTION calculate_vacation_accrual(
    annual_vacation_days DECIMAL(5,2),
    months_worked INTEGER DEFAULT 1
) RETURNS DECIMAL(5,2) AS $$
BEGIN
    RETURN ROUND(annual_vacation_days / 12.0 * months_worked, 2);
END;
$$ LANGUAGE plpgsql;

-- Function to generate next ROE number
CREATE OR REPLACE FUNCTION generate_roe_number() RETURNS VARCHAR(20) AS $$
DECLARE
    next_number INTEGER;
    roe_number VARCHAR(20);
BEGIN
    SELECT COALESCE(MAX(SUBSTRING(roe_number FROM '[0-9]+')::INTEGER), 0) + 1
    INTO next_number
    FROM roe_calculations
    WHERE roe_number ~ '^ROE[0-9]+$';
    
    roe_number := 'ROE' || LPAD(next_number::TEXT, 6, '0');
    RETURN roe_number;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-generate ROE number
CREATE OR REPLACE FUNCTION auto_generate_roe_number()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.roe_number IS NULL THEN
        NEW.roe_number := generate_roe_number();
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_auto_generate_roe_number
    BEFORE INSERT ON roe_calculations
    FOR EACH ROW
    EXECUTE FUNCTION auto_generate_roe_number();

-- Update timestamp triggers (reuse existing function)
CREATE TRIGGER update_continuous_employment_timestamp 
    BEFORE UPDATE ON continuous_employment_contracts 
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER update_automated_salary_payroll_timestamp 
    BEFORE UPDATE ON automated_salary_payroll 
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER update_roe_calculations_timestamp 
    BEFORE UPDATE ON roe_calculations 
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER update_end_employment_processing_timestamp 
    BEFORE UPDATE ON end_of_employment_processing 
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER update_time_off_accruals_timestamp 
    BEFORE UPDATE ON employee_time_off_accruals 
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

-- ===============================
-- SAMPLE DATA FOR TESTING
-- ===============================

-- Insert current tax year rates for Alberta
INSERT INTO government_tax_rates (
    tax_year, province_code, cpp_contribution_rate, cpp_employer_rate,
    cpp_max_pensionable_earnings, cpp_basic_exemption,
    ei_premium_rate, ei_employer_rate, ei_max_insurable_earnings,
    federal_tax_brackets, provincial_tax_brackets,
    effective_date
) VALUES (
    2025, 'AB', 0.0595, 0.0595, 68500.00, 3500.00,
    0.0229, 0.03206, 63300.00,
    '[{"min": 0, "max": 55867, "rate": 0.15}, {"min": 55867, "max": 111733, "rate": 0.205}]'::jsonb,
    '[{"min": 0, "max": 148269, "rate": 0.10}, {"min": 148269, "max": 177922, "rate": 0.12}]'::jsonb,
    '2025-01-01'
);

-- Sample continuous employment contract
INSERT INTO continuous_employment_contracts (
    employee_id, employment_start_date, contract_type, monthly_salary,
    auto_book_enabled, vacation_days_per_year, sick_days_per_year
) VALUES (
    1, '2025-01-01', 'permanent', 4500.00, TRUE, 15, 10
);

COMMENT ON TABLE continuous_employment_contracts IS 'Manages ongoing salary employment with automatic monthly payroll generation';
COMMENT ON TABLE automated_salary_payroll IS 'Auto-generated monthly payroll for salaried employees with full T4 integration';
COMMENT ON TABLE roe_calculations IS 'Record of Employment calculations and CRA submission tracking';
COMMENT ON TABLE end_of_employment_processing IS 'Handles employment termination, final pay, and government form generation';
COMMENT ON TABLE government_tax_rates IS 'Current tax rates and brackets for payroll calculations';
COMMENT ON TABLE employee_time_off_accruals IS 'Tracks vacation and sick time accrual and usage by year';