# Database Schema Reference - Built for Memory
## Commit to memory each session to avoid column/table errors

---

## CORE TABLES

### charters
**Key business table - all customer bookings**
```
charter_id (PK, int)
reserve_number (char varying) - BUSINESS KEY for payments matching
account_number (char varying)
charter_date (date)
total_amount_due (numeric) - Amount customer owes
paid_amount (numeric) - Total paid by customer
balance (numeric) - total_amount_due - paid_amount (can be negative for overpayment)
status (char varying) - cancelled, closed, paid, etc.
client_id (int) - Links to clients/customers
vehicle (char varying)
driver (char varying)
rate (numeric)
deposit (numeric) - Retainer/deposit amount
retainer_received (boolean)
retainer_amount (numeric)
payment_status (char varying)
client_display_name (text) - Customer name
```

### payments
**Individual payment records from customers**
```
payment_id (PK, int)
reserve_number (char varying) - CRITICAL: Links to charters via reserve_number (NOT charter_id!)
account_number (char varying)
amount (numeric) - Payment amount
payment_date (date)
payment_method (char varying) - cash, check, credit_card, debit_card, bank_transfer, etransfer, etc.
payment_key (char varying) - Unique identifier
status (char varying)
notes (text)
reference_number (char varying)
is_deposited (boolean) - Whether deposit was made
created_at (timestamp)
updated_at (timestamp)
```

### banking_transactions
**Bank statement records - SOURCE OF TRUTH for reconciliation**
```
transaction_id (PK, int)
account_number (char varying) - Which bank account
transaction_date (date)
posted_date (date)
description (text) - Transaction description from bank
credit_amount (numeric) - Deposits/income (positive)
debit_amount (numeric) - Withdrawals/expenses (positive)
balance (numeric) - Ending balance after transaction
vendor_extracted (char varying) - Parsed vendor/source name
category (char varying) - deposit, expense, transfer, etc.
reconciliation_status (char varying) - reconciled, unreconciled, etc.
reconciled_payment_id (int) - Links to payments table if matched
reconciled_charter_id (int) - Links to charters if matched
reconciled_at (timestamp)
reconciled_by (char varying)
is_nsf_charge (boolean)
is_transfer (boolean) - Inter-account transfer
verified (boolean)
locked (boolean)
```

### receipts
**Expense/charge records**
```
receipt_id (PK, int)
reserve_number (char varying) - Links to charter
charter_id (int) - Also links to charter
account_number (char varying)
vendor (char varying) - Who was paid
gross_amount (numeric) - Total with tax
net_amount (numeric) - Subtotal without tax
gst_amount (numeric) - Tax amount
receipt_date (date)
receipt_type (char varying)
category (char varying)
payment_method (char varying)
status (char varying)
notes (text)
created_at (timestamp)
```

---

## CRITICAL BUSINESS RULES

### ✅ RULE 1: reserve_number is the Business Key
- Always use `reserve_number` to link charters ↔ payments
- DO NOT use `charter_id` for payment matching (many payments have NULL charter_id)
- Query pattern:
  ```sql
  SELECT c.*, SUM(p.amount) 
  FROM charters c
  LEFT JOIN payments p ON p.reserve_number = c.reserve_number
  GROUP BY c.charter_id
  ```

### ✅ RULE 2: Banking as Source of Truth
- Start reconciliation from `banking_transactions` (bank statement)
- Match banking deposits to payments (credit_amount > 0)
- Then match payments to charters (via reserve_number)
- banking_transactions.reconciled_payment_id should link to payments.payment_id

### ✅ RULE 3: Payment Method Categories
**Allowed values in payments.payment_method:**
- cash
- check
- credit_card
- debit_card
- bank_transfer
- etransfer (e-transfer, electronic transfer)
- trade_of_services
- unknown

### ✅ RULE 4: Charter Status Values
**Common values in charters.status:**
- cancelled (refundable or nonrefundable)
- closed
- closed_paid_verified
- paid_in_full
- Paid in Full
- refund_pair (connected to another charter)
- placeholder (placeholder charter for charges)
- In Route
- None/NULL

### ✅ RULE 5: Overpayment Handling
- Overpayment = SUM(payments) > total_amount_due
- Legitimate overpayments:
  - Retainers (nonrefundable deposits on cancelled charters)
  - Rounding errors (< $0.02)
  - Customer deposits
- Flag for review:
  - Overpayments > $0.02 that are NOT retainers
  - Missing refunds for large overpayments

### ✅ RULE 6: Balance Column
- Positive balance = amount still owed
- Zero balance = fully paid
- Negative balance (overpayment) = stored as 0 for accounting purposes, but calculated can be negative
- Use: `total_amount_due - SUM(payments)` to calculate true balance

---

## RECONCILIATION QUERY PATTERNS

### Find banking payments unmatched to charters
```sql
SELECT bt.transaction_id, bt.transaction_date, bt.credit_amount, bt.description
FROM banking_transactions bt
WHERE bt.credit_amount > 0
  AND NOT EXISTS (
    SELECT 1 FROM payments p 
    WHERE ABS(p.amount - bt.credit_amount) < 0.01
      AND ABS(EXTRACT(DAY FROM (p.payment_date - bt.transaction_date))) <= 7
  )
ORDER BY bt.transaction_date DESC;
```

### Find charters with unpaid balance but no payments
```sql
SELECT c.charter_id, c.reserve_number, c.total_amount_due, c.balance
FROM charters c
WHERE c.total_amount_due > 0.01
  AND NOT EXISTS (
    SELECT 1 FROM payments p WHERE p.reserve_number = c.reserve_number
  )
ORDER BY c.charter_date DESC;
```

### Find overpayment charters
```sql
SELECT c.charter_id, c.reserve_number, c.total_amount_due,
       SUM(p.amount) as total_paid,
       SUM(p.amount) - c.total_amount_due as overpayment
FROM charters c
LEFT JOIN payments p ON p.reserve_number = c.reserve_number
GROUP BY c.charter_id, c.reserve_number, c.total_amount_due
HAVING SUM(p.amount) > c.total_amount_due + 0.01
ORDER BY overpayment DESC;
```

### Find zero-due charters with payments (deleted charges?)
```sql
SELECT c.charter_id, c.reserve_number, c.total_amount_due,
       COUNT(p.payment_id) as payment_count,
       SUM(p.amount) as total_paid
FROM charters c
LEFT JOIN payments p ON p.reserve_number = c.reserve_number
WHERE c.total_amount_due < 0.01
  AND p.payment_id IS NOT NULL
GROUP BY c.charter_id, c.reserve_number, c.total_amount_due
ORDER BY total_paid DESC;
```

---

## TABLE SIZES (Latest)
- charters: ~18,679 rows
- payments: ~24,565 rows
- banking_transactions: ~15,000+ rows
- receipts: ~58,329 rows

---

## IMPORTANT VIEWS CREATED
- `v_charter_balances` - Calculated balance (total_amount_due - SUM(payments))

---

**Last Updated:** January 20, 2026
**Status:** Reference for session continuity
