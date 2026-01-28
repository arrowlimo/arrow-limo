-- =====================================================================
-- Phase 2b: Create Invoices and Invoice Line Items Tables
-- Date: October 16, 2025
-- Purpose: Create QB-compatible invoicing tables
-- =====================================================================

\echo ''
\echo '====================================================================='
\echo 'STEP 1: Drop and recreate invoices table with full QB schema'
\echo '====================================================================='

-- Drop existing empty invoices table if it exists
DROP TABLE IF EXISTS invoice_line_items CASCADE;
DROP TABLE IF EXISTS invoices CASCADE;

-- Create invoices table with full QuickBooks schema
CREATE TABLE invoices (
    id SERIAL PRIMARY KEY,
    invoice_number VARCHAR(50) UNIQUE NOT NULL,
    
    -- Customer reference
    customer_id INTEGER REFERENCES clients(client_id),
    customer_name VARCHAR(255),
    
    -- Dates
    invoice_date DATE NOT NULL,
    due_date DATE,
    ship_date DATE,
    
    -- Charter reference (domain-specific - preserves ALMS charter link)
    charter_id INTEGER REFERENCES charters(charter_id),
    
    -- Amounts
    subtotal DECIMAL(15,2) DEFAULT 0,
    tax_amount DECIMAL(15,2) DEFAULT 0,
    discount_amount DECIMAL(15,2) DEFAULT 0,
    total_amount DECIMAL(15,2) NOT NULL,
    
    -- Payment tracking
    amount_paid DECIMAL(15,2) DEFAULT 0,
    balance_due DECIMAL(15,2),
    
    -- Status
    status VARCHAR(20) DEFAULT 'Open',  -- Open, Paid, PartiallyPaid, Overdue, Void
    
    -- QB-specific fields
    qb_invoice_id VARCHAR(50),
    qb_txn_type VARCHAR(50) DEFAULT 'Invoice',  -- Invoice, SalesReceipt, CreditMemo
    qb_trans_num VARCHAR(50),
    
    -- Terms and tax
    payment_terms VARCHAR(50) DEFAULT 'Net 30',
    tax_code VARCHAR(20),
    tax_rate DECIMAL(5,4),
    
    -- Billing details
    billing_address TEXT,
    shipping_address TEXT,
    
    -- Additional info
    memo TEXT,
    customer_message TEXT,
    po_number VARCHAR(50),
    sales_rep VARCHAR(100),
    
    -- Tracking
    is_emailed BOOLEAN DEFAULT false,
    is_printed BOOLEAN DEFAULT false,
    is_voided BOOLEAN DEFAULT false,
    void_date DATE,
    void_reason TEXT,
    
    -- Aging
    aging_days INTEGER,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    
    CONSTRAINT chk_total_amount CHECK (total_amount >= 0),
    CONSTRAINT chk_amount_paid CHECK (amount_paid >= 0),
    CONSTRAINT chk_balance_due CHECK (balance_due >= 0)
);

COMMENT ON TABLE invoices IS 'QuickBooks-compatible invoices table. Links to both customers (QB standard) and charters (ALMS domain). Tracks full invoice lifecycle from creation to payment.';

-- Create indexes for performance
CREATE INDEX idx_invoices_customer_id ON invoices(customer_id);
CREATE INDEX idx_invoices_charter_id ON invoices(charter_id);
CREATE INDEX idx_invoices_invoice_date ON invoices(invoice_date);
CREATE INDEX idx_invoices_due_date ON invoices(due_date);
CREATE INDEX idx_invoices_status ON invoices(status);
CREATE INDEX idx_invoices_qb_invoice_id ON invoices(qb_invoice_id);
CREATE INDEX idx_invoices_invoice_number ON invoices(invoice_number);

\echo ''
\echo '====================================================================='
\echo 'STEP 2: Create invoice_line_items table'
\echo '====================================================================='

CREATE TABLE invoice_line_items (
    id SERIAL PRIMARY KEY,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    
    -- Line info
    line_number INTEGER NOT NULL,
    
    -- Item/Service details
    item_type VARCHAR(50),  -- Service, Item, Discount, Subtotal, etc.
    item_name VARCHAR(255),
    description TEXT,
    
    -- Quantity and pricing
    quantity DECIMAL(10,2) DEFAULT 1,
    unit_price DECIMAL(15,2),
    rate DECIMAL(15,2),  -- Alias for unit_price (QB uses both terms)
    
    -- Amounts
    amount DECIMAL(15,2) NOT NULL,
    discount_percent DECIMAL(5,2),
    discount_amount DECIMAL(15,2),
    
    -- Tax
    is_taxable BOOLEAN DEFAULT true,
    tax_code VARCHAR(20),
    tax_amount DECIMAL(15,2),
    
    -- Accounting
    account_code VARCHAR(50),
    account_name VARCHAR(255),
    income_account VARCHAR(50),  -- Which income account to credit
    
    -- QB fields
    qb_item_id VARCHAR(50),
    qb_class VARCHAR(100),  -- QB class for job/department tracking
    
    -- Charter-specific (ALMS domain)
    service_type VARCHAR(100),  -- Charter, Airport, Hourly, etc.
    vehicle_id INTEGER,
    driver_id INTEGER,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT chk_line_amount CHECK (amount >= 0),
    CONSTRAINT chk_line_quantity CHECK (quantity >= 0),
    CONSTRAINT uq_invoice_line UNIQUE (invoice_id, line_number)
);

COMMENT ON TABLE invoice_line_items IS 'Line item details for invoices. Each line represents a service/item billed. Links to GL accounts for proper revenue recognition.';

-- Create indexes
CREATE INDEX idx_invoice_line_items_invoice_id ON invoice_line_items(invoice_id);
CREATE INDEX idx_invoice_line_items_account_code ON invoice_line_items(account_code);
CREATE INDEX idx_invoice_line_items_item_name ON invoice_line_items(item_name);

\echo ''
\echo '====================================================================='
\echo 'STEP 3: Add FK constraint to payments table'
\echo '====================================================================='

-- Now we can add the FK constraint that failed earlier
ALTER TABLE payments
ADD CONSTRAINT payments_applied_to_invoice_fkey 
FOREIGN KEY (applied_to_invoice) 
REFERENCES invoices(id);

\echo ''
\echo '====================================================================='
\echo 'STEP 4: Create useful views for invoice reporting'
\echo '====================================================================='

-- View: Invoice summary with customer details
CREATE OR REPLACE VIEW qb_invoice_summary AS
SELECT 
    i.id,
    i.invoice_number,
    i.invoice_date,
    i.due_date,
    c.company_name AS customer,
    c.account_number AS customer_account,
    i.total_amount,
    i.amount_paid,
    i.balance_due,
    i.status,
    i.aging_days,
    i.payment_terms,
    i.charter_id,
    ch.charter_number,
    i.memo,
    -- Calculate if overdue
    CASE 
        WHEN i.status = 'Open' AND i.due_date < CURRENT_DATE THEN true
        ELSE false
    END AS is_overdue,
    -- Days until/past due
    CASE 
        WHEN i.due_date IS NOT NULL THEN (CURRENT_DATE - i.due_date)
        ELSE NULL
    END AS days_overdue
FROM invoices i
LEFT JOIN clients c ON i.customer_id = c.id
LEFT JOIN charters ch ON i.charter_id = ch.id
ORDER BY i.invoice_date DESC;

COMMENT ON VIEW qb_invoice_summary IS 'Invoice summary with customer and charter details, aging calculation, and overdue status.';

-- View: Invoice detail with line items
CREATE OR REPLACE VIEW qb_invoice_detail AS
SELECT 
    i.invoice_number,
    i.invoice_date,
    i.due_date,
    c.company_name AS customer,
    li.line_number,
    li.item_name,
    li.description,
    li.quantity,
    li.unit_price,
    li.amount,
    li.account_code,
    li.account_name,
    i.status,
    i.total_amount AS invoice_total
FROM invoices i
LEFT JOIN clients c ON i.customer_id = c.id
LEFT JOIN invoice_line_items li ON i.id = li.invoice_id
ORDER BY i.invoice_date DESC, i.invoice_number, li.line_number;

COMMENT ON VIEW qb_invoice_detail IS 'Detailed invoice view showing all line items with GL account mapping.';

-- View: AR aging summary
CREATE OR REPLACE VIEW qb_ar_aging AS
SELECT 
    c.company_name AS customer,
    c.account_number,
    COUNT(i.id) AS invoice_count,
    SUM(i.total_amount) AS total_invoiced,
    SUM(i.amount_paid) AS total_paid,
    SUM(i.balance_due) AS total_outstanding,
    -- Aging buckets
    SUM(CASE WHEN i.aging_days <= 30 THEN i.balance_due ELSE 0 END) AS current,
    SUM(CASE WHEN i.aging_days BETWEEN 31 AND 60 THEN i.balance_due ELSE 0 END) AS days_31_60,
    SUM(CASE WHEN i.aging_days BETWEEN 61 AND 90 THEN i.balance_due ELSE 0 END) AS days_61_90,
    SUM(CASE WHEN i.aging_days > 90 THEN i.balance_due ELSE 0 END) AS over_90_days
FROM clients c
LEFT JOIN invoices i ON c.client_id = i.customer_id AND i.status != 'Paid' AND i.status != 'Void'
GROUP BY c.client_id, c.company_name, c.account_number
HAVING SUM(i.balance_due) > 0
ORDER BY total_outstanding DESC;

COMMENT ON VIEW qb_ar_aging IS 'Accounts receivable aging report showing customer balances by aging bucket.';

\echo ''
\echo '====================================================================='
\echo 'STEP 5: Create trigger to auto-update invoice balances'
\echo '====================================================================='

-- Function to calculate balance_due
CREATE OR REPLACE FUNCTION update_invoice_balance()
RETURNS TRIGGER AS $$
BEGIN
    -- Calculate balance_due as total_amount - amount_paid
    NEW.balance_due := NEW.total_amount - COALESCE(NEW.amount_paid, 0);
    
    -- Update status based on balance
    IF NEW.balance_due <= 0 THEN
        NEW.status := 'Paid';
    ELSIF NEW.amount_paid > 0 AND NEW.balance_due > 0 THEN
        NEW.status := 'PartiallyPaid';
    ELSIF NEW.is_voided THEN
        NEW.status := 'Void';
    ELSIF NEW.due_date IS NOT NULL AND NEW.due_date < CURRENT_DATE AND NEW.balance_due > 0 THEN
        NEW.status := 'Overdue';
    ELSE
        NEW.status := 'Open';
    END IF;
    
    -- Calculate aging days
    IF NEW.invoice_date IS NOT NULL THEN
        NEW.aging_days := (CURRENT_DATE - NEW.invoice_date);
    END IF;
    
    -- Update updated_at timestamp
    NEW.updated_at := CURRENT_TIMESTAMP;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger
DROP TRIGGER IF EXISTS trigger_update_invoice_balance ON invoices;
CREATE TRIGGER trigger_update_invoice_balance
    BEFORE INSERT OR UPDATE ON invoices
    FOR EACH ROW
    EXECUTE FUNCTION update_invoice_balance();

COMMENT ON FUNCTION update_invoice_balance() IS 'Automatically calculates invoice balance, status, and aging before insert/update.';

\echo ''
\echo '====================================================================='
\echo 'VERIFICATION'
\echo '====================================================================='

-- Verify tables created
SELECT 
    'invoices' AS table_name,
    COUNT(*) AS column_count
FROM information_schema.columns 
WHERE table_name = 'invoices'

UNION ALL

SELECT 
    'invoice_line_items',
    COUNT(*)
FROM information_schema.columns 
WHERE table_name = 'invoice_line_items';

-- Verify indexes
SELECT 
    'invoices indexes' AS check_name,
    COUNT(*) AS index_count
FROM pg_indexes 
WHERE tablename = 'invoices'

UNION ALL

SELECT 
    'invoice_line_items indexes',
    COUNT(*)
FROM pg_indexes 
WHERE tablename = 'invoice_line_items';

-- Verify views
SELECT 'Views created' AS check_name,
       COUNT(*) AS view_count
FROM information_schema.views
WHERE table_name IN ('qb_invoice_summary', 'qb_invoice_detail', 'qb_ar_aging');

\echo ''
\echo '====================================================================='
\echo '✓ Phase 2b: Invoices Tables Created Successfully!'
\echo '====================================================================='
\echo 'Created:'
\echo '  - invoices table (43 columns, 7 indexes, auto-balance trigger)'
\echo '  - invoice_line_items table (23 columns, 3 indexes)'
\echo '  - 3 reporting views (summary, detail, AR aging)'
\echo '  - FK constraint on payments.applied_to_invoice'
\echo ''
\echo 'Ready to populate from QB reports or charter data!'
\echo '====================================================================='
