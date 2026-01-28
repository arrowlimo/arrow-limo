-- STEP 6: Invoice Generation & Payment Collection - database changes
-- Date: 2026-01-22
-- Note: reserve_number is the business key; avoid charter_id for business logic.

-- Ensure we're in public schema and invoices table doesn't exist yet
DROP TABLE IF EXISTS invoice_line_items CASCADE;
DROP TABLE IF EXISTS invoices CASCADE;

BEGIN;

-- 1) Invoices table
CREATE TABLE IF NOT EXISTS invoices (
  invoice_id SERIAL PRIMARY KEY,
  reserve_number VARCHAR(50) NOT NULL UNIQUE, -- business key
  invoice_number VARCHAR(50) UNIQUE, -- INV-{reserve_number}
  invoice_date DATE,
  due_date DATE, -- net 30 terms
  subtotal_taxable DECIMAL(12,2), -- sum of taxable line items minus discounts
  gst_amount DECIMAL(12,2), -- 5% of subtotal_taxable
  subtotal_non_taxable DECIMAL(12,2), -- gratuity, credits, breakdown reimbursements
  invoice_total DECIMAL(12,2), -- (subtotal_taxable + gst_amount) + subtotal_non_taxable
  total_payments DECIMAL(12,2), -- sum of all payments (NRD + subsequent + trade)
  balance_due DECIMAL(12,2), -- invoice_total - total_payments
  paid BOOLEAN DEFAULT FALSE, -- TRUE if balance_due <= 0
  invoice_status VARCHAR(20), -- draft, finalized, sent, overdue, paid, credited
  manager_approved BOOLEAN DEFAULT FALSE, -- required if total > $1000 or extra charges
  manager_approved_by VARCHAR(100),
  manager_approved_at TIMESTAMPTZ,
  sent_at TIMESTAMPTZ,
  sent_method VARCHAR(20), -- email, mail, hand_delivered
  sent_by VARCHAR(100),
  finalized_at TIMESTAMPTZ,
  finalized_by VARCHAR(100),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  created_by VARCHAR(100),
  notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_invoices_reserve ON invoices(reserve_number);
CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(invoice_status);
CREATE INDEX IF NOT EXISTS idx_invoices_due_date ON invoices(due_date);
CREATE INDEX IF NOT EXISTS idx_invoices_balance_due ON invoices(balance_due) WHERE balance_due > 0;

-- 2) Invoice line items (10 types from Step 2 spec)
CREATE TABLE IF NOT EXISTS invoice_line_items (
  line_item_id SERIAL PRIMARY KEY,
  invoice_id INT NOT NULL REFERENCES invoices(invoice_id) ON DELETE CASCADE,
  reserve_number VARCHAR(50), -- business key for easy reference
  line_type VARCHAR(50), -- charter_fee, extra_time, misc_charge, beverage, discount, charitable_comp, breakdown_reimbursement, penny_rounding, gratuity, trade_item
  description VARCHAR(500),
  quantity DECIMAL(8,2), -- 1.00 for most items; >1 for extra hours, beverage multiples
  unit_price DECIMAL(12,2),
  line_total DECIMAL(12,2), -- quantity × unit_price
  taxable BOOLEAN DEFAULT TRUE, -- FALSE for gratuity, credits, breakdown reimbursements
  gst_amount DECIMAL(12,2), -- line_total × 0.05 if taxable
  display_order INT, -- for invoice PDF ordering
  notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_invoice_line_items_invoice ON invoice_line_items(invoice_id);
CREATE INDEX IF NOT EXISTS idx_invoice_line_items_reserve ON invoice_line_items(reserve_number);
CREATE INDEX IF NOT EXISTS idx_invoice_line_items_type ON invoice_line_items(line_type);

COMMIT;
