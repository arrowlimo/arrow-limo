# Vendor Invoice Manager - User Guide

## Overview
The Vendor Invoice Manager is a comprehensive system for managing vendor invoices, payments, and account balances. It handles complex scenarios like multi-invoice payments, split payments, and banking transaction linking.

## Location
**Desktop App → 💰 Accounting & Finance → 📋 Vendor Invoice Manager**

## Key Features

### 1. Vendor Search & Selection
- Type vendor name in search box (min 2 characters)
- Auto-complete shows matching vendors
- Select vendor from dropdown to load all invoices

### 2. Invoice Pool Management
- View all invoices for selected vendor
- Color-coded status (✅ Paid, ❌ Unpaid)
- Shows: Invoice #, Date, Amount, Paid, Balance
- Account summary displays total invoiced, paid, and balance due

### 3. Add New Invoices
**Tab: ➕ Add Invoice**
- Invoice #: Reference number (optional, auto-generated if blank)
- Invoice Date: Original invoice date
- Amount: Invoice total
- Description: Optional notes
- Category: Expense category (auto-complete from existing)
- Click "✅ Add Invoice" to save

### 4. Payment Application

#### Single Invoice Payment
**Tab: 💰 Add Payment**
1. Enter payment details:
   - Payment Date
   - Payment Amount
   - Payment Method (Check, Cash, Credit Card, etc.)
   - Reference (Check #, TX ID, etc.)
   - Banking TX ID (optional)

2. Select invoice from list
3. Click "💵 Apply to Single Invoice"
4. Confirm payment application

#### Multi-Invoice Payment
**Your Example: Check #197 for $550 split across multiple 2011 invoices**

**Tab: 💰 Add Payment**
1. Enter payment amount: $550.00
2. Enter payment details (date, method, check #197)
3. Click "💰 Split Across Multiple Invoices"
4. **Multi-Invoice Payment Dialog** opens:
   - Shows all unpaid invoices
   - Click "⚡ Auto-Allocate (Oldest First)" to auto-distribute
   - OR manually check invoices to allocate
   - Shows: Total Payment, Allocated, Remaining
5. Click OK to apply allocations

**Example Allocation:**
```
Payment: $550.00 (Check #197, Date: 01/03/2012)

Allocated to:
- Invoice 21160: $150.00
- Invoice 21431: $125.00
- Invoice 21739: $100.00
- Invoice 22072: $175.00
Total Allocated: $550.00
Remaining: $0.00 ✅
```

### 5. Banking Transaction Linking
**Tab: 🏦 Link Banking**

**Purpose:** Link bank statement transactions to invoice payments

1. Search for banking transaction:
   - Enter approximate amount
   - Or enter description keywords
   - Click "🔍 Search Banking Transactions"

2. Results show:
   - Transaction ID, Date, Description
   - Amount, Check #
   - Linked status (✅ Yes/❌ No)

3. Double-click transaction to auto-fill Banking TX ID
4. Go to Payment tab and apply to invoice(s)

### 6. Account Summary
**Tab: 📊 Account Summary**

Shows complete account history:
- Total invoiced vs paid
- Balance due
- Detailed invoice list with:
  - Invoice numbers and dates
  - Amount, paid, balance for each
  - Payment status

Click "🔄 Refresh Summary" to update

## Example Workflow: 106.7 Radio Station

### Scenario
You have Check #197 for $550.00 paid in 2012 that covers multiple 2011 invoices (21160, 21431, 21739, 22072). Final balance as of 01/03/2012 is $1,503.25.

### Steps

1. **Search for Vendor**
   - Type "106.7" in vendor search
   - Select "106.7" from dropdown

2. **Verify Existing Invoices**
   - Check invoice list for 21160, 21431, 21739, 22072
   - If missing, add them via "Add Invoice" tab

3. **Add Missing Invoices** (if needed)
   ```
   Invoice #21160 - Date: [2011 date] - Amount: $XXX.XX
   Invoice #21431 - Date: [2011 date] - Amount: $XXX.XX
   Invoice #21739 - Date: [2011 date] - Amount: $XXX.XX
   Invoice #22072 - Date: [2011 date] - Amount: $XXX.XX
   ```

4. **Record Check Payment**
   - Go to "💰 Add Payment" tab
   - Payment Date: 01/03/2012
   - Payment Amount: 550.00
   - Payment Method: Check
   - Reference: 197
   - Click "💰 Split Across Multiple Invoices"

5. **Allocate Payment**
   - Select invoices 21160, 21431, 21739, 22072
   - Manually allocate or use auto-allocate
   - Confirm allocations total $550.00
   - Click OK

6. **Link to Banking** (optional)
   - Go to "🏦 Link Banking" tab
   - Search for $550 transaction
   - Double-click banking transaction
   - Banking TX ID auto-fills in payment form

7. **Verify Balance**
   - Go to "📊 Account Summary" tab
   - Check that balance due shows $1,503.25
   - Verify payment history

## Invoice Additions & Fees

### WCB Late Fees Example
When WCB (Workers Compensation Board) charges a late fee on an invoice:

**Option 1: Separate Invoice**
1. Add original invoice: WCB Invoice #12345 - $1,000.00
2. Add late fee as separate invoice: WCB Late Fee #12345 - $50.00
3. Link both invoices to same payment if paid together

**Option 2: Single Combined Invoice**
1. Add invoice with combined amount: $1,050.00
2. Note in description: "Invoice #12345 $1,000 + $50 late fee"

**Option 3: Use Receipt Search Widget**
The existing Receipt Search widget has built-in WCB late fee detection and auto-split functionality.

## Right-Click Context Menu

Right-click any invoice in the list for:
- ✏️ Edit Invoice
- 🗑️ Delete Invoice
- 👁️ View Full Details

## Features

### Auto-Allocation
- Automatically distributes payment across multiple invoices
- Prioritizes oldest invoices first
- Shows real-time allocation summary
- Prevents over-payment

### Payment Tracking
- Links payments to specific invoices
- Tracks partial payments
- Shows remaining balance per invoice
- Color-coded status indicators

### Banking Integration
- Search banking transactions by amount/description
- Link banking transactions to invoice payments
- Detect duplicate payments
- Track check numbers

### Multi-Invoice Statements
Perfect for handling vendor statements with multiple outstanding invoices, like your 106.7 example where a single check covers multiple dated invoices.

## Database Integration

### Tables Used
- `receipts`: Stores all invoices (vendor receipts)
- `banking_transactions`: Bank statement transactions
- `banking_receipt_matching_ledger`: Links banking to receipts

### Fields
- `receipts.vendor_name`: Vendor identification
- `receipts.source_reference`: Invoice number
- `receipts.receipt_date`: Original invoice date
- `receipts.gross_amount`: Invoice total
- `receipts.banking_transaction_id`: Link to banking transaction

## Tips & Best Practices

1. **Use Original Dates**: Always use the original invoice date, even if payment is much later

2. **Invoice Numbers**: Use vendor's invoice number in `source_reference` field for tracking

3. **Multi-Invoice Payments**: Use auto-allocate for complex splits, then adjust manually if needed

4. **Banking Links**: Link to banking transactions for complete audit trail

5. **Descriptions**: Add notes about payment context (e.g., "Paid via check #197 on 01/03/2012 covering 4 outstanding invoices")

6. **Account Summary**: Regularly check account summary to verify balances match vendor statements

7. **Payment Methods**: Use consistent payment methods (Check, Cash, Credit Card) for better reporting

## Keyboard Shortcuts

- **Double-click invoice**: View full details
- **Right-click invoice**: Context menu
- **Escape**: Close dialogs
- **Enter**: Confirm dialogs

## Troubleshooting

### Issue: Vendor not found
**Solution**: Check spelling, try partial name (e.g., "106" instead of "106.7")

### Issue: Payment amount doesn't match allocation
**Solution**: Use multi-invoice dialog's auto-allocate, then verify totals

### Issue: Banking transaction already linked
**Solution**: Check if invoice already has payment - view invoice details

### Issue: Balance doesn't match vendor statement
**Solution**: Check all invoices are added, verify payment dates, check for missing payments

## Future Enhancements

Planned features (not yet implemented):
- Invoice payment allocation tracking table
- Payment history timeline
- Vendor statement import
- Automatic payment matching
- Email notifications for due invoices
- Recurring invoice templates

## Support

For issues or questions:
- Check database directly: `receipts` table filtered by `vendor_name`
- Use Receipt Search widget for advanced searching
- Check banking transactions for payment verification

---

**Last Updated**: December 29, 2025
**Version**: 1.0
**System**: Arrow Limousine Management System
