#!/usr/bin/env python3
"""
Verify January 2013 balance calculation matches PDF reconciliation report.

Expected:
- Opening balance Jan 01: $21.21
- Net change: -$177.29 (debits $4,773.89 - credits $4,596.60)
- Closing balance Jan 31: $21.21 - $177.29 = -$156.08

But PDF shows closing balance: -$244.65

Need to check if there's a discrepancy or if opening balance is different.
"""

# From import script
OPENING_BALANCE = 21.21
TOTAL_DEBITS = 4773.89
TOTAL_CREDITS = 4596.60

# From PDF
PDF_CLOSING_BALANCE = -244.65

# Calculate
net_change = TOTAL_CREDITS - TOTAL_DEBITS
calculated_closing = OPENING_BALANCE + net_change

print("="*80)
print("JANUARY 2013 BALANCE VERIFICATION")
print("="*80)
print(f"Opening balance (Jan 01): ${OPENING_BALANCE:,.2f}")
print(f"Total debits (withdrawals): ${TOTAL_DEBITS:,.2f}")
print(f"Total credits (deposits): ${TOTAL_CREDITS:,.2f}")
print(f"Net change: ${net_change:+,.2f}")
print()
print(f"Calculated closing: ${calculated_closing:,.2f}")
print(f"PDF closing balance: ${PDF_CLOSING_BALANCE:,.2f}")
print(f"Difference: ${calculated_closing - PDF_CLOSING_BALANCE:+,.2f}")
print()

if abs(calculated_closing - PDF_CLOSING_BALANCE) > 0.01:
    print("[WARNING] Balance mismatch! Need to review transaction details.")
    print()
    print("Possible issues:")
    print("- Missing transactions")
    print("- Incorrect opening balance")
    print("- OCR reading errors in amounts")
else:
    print("[OK] Balance matches PDF!")
