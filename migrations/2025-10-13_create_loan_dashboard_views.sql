-- Vehicle Loan Dashboard Reporting Views and Queries
-- Comprehensive financial reporting for vehicle financing management

-- 1. LOAN SUMMARY VIEW - Current status of all vehicle loans
CREATE OR REPLACE VIEW v_loan_dashboard_summary AS
SELECT 
    vl.id as loan_id,
    vl.vehicle_name,
    v.vin_number,
    v.make || ' ' || v.model || ' ' || v.year as vehicle_description,
    vl.lender,
    vl.paid_by,
    
    -- Financial details
    COALESCE(vl.opening_balance, 0) as original_amount,
    COALESCE(vl.total_paid, 0) as total_paid,
    COALESCE(vl.total_interest, 0) as total_interest,
    COALESCE(vl.total_fees, 0) as total_fees,
    COALESCE(vl.closing_balance, 0) as current_balance,
    
    -- Calculated fields
    CASE 
        WHEN COALESCE(vl.opening_balance, 0) > 0 
        THEN ROUND((COALESCE(vl.total_paid, 0) / vl.opening_balance) * 100, 2)
        ELSE 0 
    END as percent_paid,
    
    CASE 
        WHEN COALESCE(vl.closing_balance, 0) <= 0 THEN 'PAID OFF'
        WHEN COALESCE(vl.closing_balance, 0) > 0 THEN 'ACTIVE'
        ELSE 'UNKNOWN'
    END as loan_status,
    
    -- Payment statistics
    (SELECT COUNT(*) FROM vehicle_loan_payments WHERE loan_id = vl.id) as total_payments,
    (SELECT MAX(payment_date) FROM vehicle_loan_payments WHERE loan_id = vl.id) as last_payment_date,
    (SELECT COUNT(*) FROM vehicle_loan_payments WHERE loan_id = vl.id AND fee_amount > 0) as fee_payments,
    
    -- Dates
    vl.loan_start_date,
    vl.loan_end_date,
    
    -- Days since last payment
    CASE 
        WHEN (SELECT MAX(payment_date) FROM vehicle_loan_payments WHERE loan_id = vl.id) IS NOT NULL
        THEN CURRENT_DATE - (SELECT MAX(payment_date) FROM vehicle_loan_payments WHERE loan_id = vl.id)
        ELSE NULL
    END as days_since_last_payment

FROM vehicle_loans vl
LEFT JOIN vehicles v ON vl.vehicle_id = v.vehicle_id
ORDER BY vl.loan_start_date DESC;

-- 2. PAYMENT HISTORY VIEW - Detailed payment tracking
CREATE OR REPLACE VIEW v_payment_history_detail AS
SELECT 
    vlp.id as payment_id,
    vl.id as loan_id,
    vl.vehicle_name,
    v.vin_number,
    vlp.payment_date,
    vlp.payment_amount,
    COALESCE(vlp.interest_amount, 0) as interest_amount,
    COALESCE(vlp.fee_amount, 0) as fee_amount,
    COALESCE(vlp.penalty_amount, 0) as penalty_amount,
    vlp.paid_by,
    vlp.notes,
    
    -- Running balance calculation
    vl.opening_balance - SUM(vlp2.payment_amount) OVER (
        PARTITION BY vl.id 
        ORDER BY vlp2.payment_date, vlp2.id 
        ROWS UNBOUNDED PRECEDING
    ) as balance_after_payment,
    
    -- Payment type classification
    CASE 
        WHEN vlp.fee_amount > 0 THEN 'FEE/NSF'
        WHEN vlp.penalty_amount > 0 THEN 'PENALTY'
        WHEN vlp.interest_amount > 0 AND vlp.payment_amount = 0 THEN 'INTEREST ONLY'
        ELSE 'REGULAR PAYMENT'
    END as payment_type

FROM vehicle_loan_payments vlp
JOIN vehicle_loans vl ON vlp.loan_id = vl.id
LEFT JOIN vehicles v ON vl.vehicle_id = v.vehicle_id
LEFT JOIN vehicle_loan_payments vlp2 ON vlp2.loan_id = vlp.loan_id 
    AND vlp2.payment_date <= vlp.payment_date 
    AND vlp2.id <= vlp.id
ORDER BY vl.id, vlp.payment_date, vlp.id;

-- 3. NSF AND FEES TRACKING VIEW
CREATE OR REPLACE VIEW v_nsf_fees_summary AS
SELECT 
    vl.id as loan_id,
    vl.vehicle_name,
    v.vin_number,
    COUNT(*) as total_nsf_fees,
    SUM(vlp.fee_amount) as total_nsf_amount,
    SUM(COALESCE(vlp.penalty_amount, 0)) as total_penalties,
    MIN(vlp.payment_date) as first_nsf_date,
    MAX(vlp.payment_date) as last_nsf_date,
    
    -- NSF rate calculation
    ROUND(
        (COUNT(*)::numeric / NULLIF(
            (SELECT COUNT(*) FROM vehicle_loan_payments WHERE loan_id = vl.id), 0
        )) * 100, 2
    ) as nsf_rate_percent

FROM vehicle_loans vl
LEFT JOIN vehicles v ON vl.vehicle_id = v.vehicle_id
JOIN vehicle_loan_payments vlp ON vlp.loan_id = vl.id
WHERE vlp.fee_amount > 0 OR vlp.penalty_amount > 0
GROUP BY vl.id, vl.vehicle_name, v.vin_number
ORDER BY total_nsf_amount DESC;

-- 4. MONTHLY PAYMENT SUMMARY
CREATE OR REPLACE VIEW v_monthly_payment_summary AS
SELECT 
    DATE_TRUNC('month', vlp.payment_date) as payment_month,
    COUNT(*) as total_payments,
    COUNT(DISTINCT vlp.loan_id) as loans_with_payments,
    SUM(vlp.payment_amount) as total_amount_received,
    SUM(COALESCE(vlp.interest_amount, 0)) as total_interest,
    SUM(COALESCE(vlp.fee_amount, 0)) as total_fees,
    SUM(COALESCE(vlp.penalty_amount, 0)) as total_penalties,
    
    -- Average payment amount
    ROUND(AVG(vlp.payment_amount), 2) as avg_payment_amount,
    
    -- Payment breakdown
    COUNT(*) FILTER (WHERE vlp.fee_amount > 0) as nsf_payments,
    COUNT(*) FILTER (WHERE vlp.penalty_amount > 0) as penalty_payments

FROM vehicle_loan_payments vlp
GROUP BY DATE_TRUNC('month', vlp.payment_date)
ORDER BY payment_month DESC;

-- 5. LOAN PORTFOLIO OVERVIEW
CREATE OR REPLACE VIEW v_loan_portfolio_kpis AS
SELECT 
    -- Portfolio totals
    COUNT(*) as total_loans,
    COUNT(*) FILTER (WHERE closing_balance > 0) as active_loans,
    COUNT(*) FILTER (WHERE closing_balance <= 0) as paid_off_loans,
    
    -- Financial summary
    SUM(COALESCE(opening_balance, 0)) as total_original_amount,
    SUM(COALESCE(total_paid, 0)) as total_amount_paid,
    SUM(COALESCE(closing_balance, 0)) as total_outstanding_balance,
    SUM(COALESCE(total_interest, 0)) as total_interest_earned,
    SUM(COALESCE(total_fees, 0)) as total_fees_collected,
    
    -- Portfolio health metrics
    ROUND(AVG(
        CASE 
            WHEN opening_balance > 0 
            THEN (total_paid / opening_balance) * 100 
            ELSE NULL 
        END
    ), 2) as avg_loan_completion_percent,
    
    -- Payment activity (last 30 days)
    (SELECT COUNT(*) FROM vehicle_loan_payments 
     WHERE payment_date >= CURRENT_DATE - INTERVAL '30 days') as payments_last_30_days,
     
    (SELECT SUM(payment_amount) FROM vehicle_loan_payments 
     WHERE payment_date >= CURRENT_DATE - INTERVAL '30 days') as amount_received_last_30_days

FROM vehicle_loans;

-- 6. OVERDUE LOANS ANALYSIS (based on last payment)
CREATE OR REPLACE VIEW v_overdue_loans AS
SELECT 
    vl.id as loan_id,
    vl.vehicle_name,
    v.vin_number,
    vl.closing_balance,
    last_payment.payment_date as last_payment_date,
    CURRENT_DATE - last_payment.payment_date as days_overdue,
    
    CASE 
        WHEN CURRENT_DATE - last_payment.payment_date <= 30 THEN 'CURRENT'
        WHEN CURRENT_DATE - last_payment.payment_date <= 60 THEN '31-60 DAYS'
        WHEN CURRENT_DATE - last_payment.payment_date <= 90 THEN '61-90 DAYS'
        ELSE '90+ DAYS'
    END as overdue_category,
    
    vl.paid_by,
    vl.lender

FROM vehicle_loans vl
LEFT JOIN vehicles v ON vl.vehicle_id = v.vehicle_id
LEFT JOIN (
    SELECT 
        loan_id, 
        MAX(payment_date) as payment_date
    FROM vehicle_loan_payments 
    GROUP BY loan_id
) last_payment ON last_payment.loan_id = vl.id
WHERE vl.closing_balance > 0
  AND (last_payment.payment_date IS NULL OR CURRENT_DATE - last_payment.payment_date > 30)
ORDER BY days_overdue DESC NULLS LAST;

-- 7. PERFORMANCE BY LENDER
CREATE OR REPLACE VIEW v_lender_performance AS
SELECT 
    vl.lender,
    COUNT(*) as total_loans,
    SUM(COALESCE(vl.opening_balance, 0)) as total_financed,
    SUM(COALESCE(vl.total_paid, 0)) as total_collected,
    SUM(COALESCE(vl.closing_balance, 0)) as outstanding_balance,
    SUM(COALESCE(vl.total_fees, 0)) as total_fees,
    
    -- Performance metrics
    ROUND(
        (SUM(COALESCE(vl.total_paid, 0)) / NULLIF(SUM(COALESCE(vl.opening_balance, 0)), 0)) * 100, 
        2
    ) as collection_rate_percent,
    
    COUNT(*) FILTER (WHERE vl.closing_balance <= 0) as completed_loans,
    
    -- Average loan performance
    ROUND(AVG(COALESCE(vl.opening_balance, 0)), 2) as avg_loan_amount,
    
    -- NSF statistics by lender
    (SELECT COUNT(*) FROM vehicle_loan_payments vlp 
     JOIN vehicle_loans vl2 ON vlp.loan_id = vl2.id 
     WHERE vl2.lender = vl.lender AND vlp.fee_amount > 0) as total_nsf_incidents

FROM vehicle_loans vl
GROUP BY vl.lender
ORDER BY total_financed DESC;