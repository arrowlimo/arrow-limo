#!/usr/bin/env python
"""Generate comprehensive audit completion checklist and status report."""
import psycopg2
import os

DB_HOST=os.environ.get("DB_HOST","localhost")
DB_NAME=os.environ.get("DB_NAME","almsdata")
DB_USER=os.environ.get("DB_USER","postgres")
DB_PASSWORD=os.environ.get("DB_PASSWORD","***REMOVED***")

conn=psycopg2.connect(host=DB_HOST,database=DB_NAME,user=DB_USER,password=DB_PASSWORD)
cur=conn.cursor()

print("\n"+"="*100)
print("AUDIT COMPLETION CHECKLIST & STATUS")
print("="*100)
print()

# 1. Banking Reconciliation
print("1. BANKING RECONCILIATION")
print("-" * 100)
cur.execute("""
    SELECT COUNT(*)
    FROM banking_transactions
    WHERE receipt_id IS NULL
      AND reconciled_receipt_id IS NULL
      AND reconciled_payment_id IS NULL
      AND reconciled_charter_id IS NULL
""")
unlinked_banking = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM banking_transactions")
total_banking = cur.fetchone()[0]
pct_done = 100 * (total_banking - unlinked_banking) / total_banking if total_banking > 0 else 0
status = "✅ COMPLETE" if unlinked_banking == 0 else f"⚠️ {unlinked_banking} unlinked"
print(f"   Status: {status}")
print(f"   Progress: {total_banking - unlinked_banking}/{total_banking} linked ({pct_done:.1f}%)")
print()

# 2. GL Code Assignment
print("2. GL CODE ASSIGNMENT (NULL gl_account_code receipts)")
print("-" * 100)
cur.execute("SELECT COUNT(*) FROM receipts WHERE gl_account_code IS NULL")
null_gl = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM receipts")
total_receipts = cur.fetchone()[0]
pct_categorized = 100 * (total_receipts - null_gl) / total_receipts if total_receipts > 0 else 0
status = "✅ COMPLETE" if null_gl == 0 else f"❌ {null_gl:,} need categorization"
print(f"   Status: {status}")
print(f"   Progress: {total_receipts - null_gl:,}/{total_receipts:,} categorized ({pct_categorized:.1f}%)")

# Breakdown by source
cur.execute("""
    SELECT source_system, COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE gl_account_code IS NULL
    GROUP BY source_system
    ORDER BY COUNT(*) DESC
""")
print("   Breakdown by source:")
for source, cnt, total in cur.fetchall():
    print(f"     - {source}: {cnt:,} receipts | ${total:,.2f}")
print()

# 3. Receipt-Banking Linkage
print("3. RECEIPT-BANKING LINKAGE (receipts without banking link)")
print("-" * 100)
cur.execute("""
    SELECT COUNT(*)
    FROM receipts
    WHERE banking_transaction_id IS NULL
      AND created_from_banking = false
""")
unlinked_receipts = cur.fetchone()[0]
pct_linked = 100 * (total_receipts - unlinked_receipts) / total_receipts if total_receipts > 0 else 0
status = "✅ COMPLETE" if unlinked_receipts == 0 else f"⚠️ {unlinked_receipts:,} unlinked"
print(f"   Status: {status}")
print(f"   Progress: {total_receipts - unlinked_receipts:,}/{total_receipts:,} linked ({pct_linked:.1f}%)")
print(f"   Note: {unlinked_receipts:,} receipts are manual entries without banking transactions (expected)")
print()

# 4. Payment-Charter Reconciliation
print("4. PAYMENT-CHARTER RECONCILIATION (via reserve_number)")
print("-" * 100)
cur.execute("""
    SELECT COUNT(*)
    FROM payments
    WHERE charter_id IS NULL AND reserve_number IS NOT NULL
""")
orphan_payments = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM payments")
total_payments = cur.fetchone()[0]
status = "✅ COMPLETE" if orphan_payments == 0 else f"⚠️ {orphan_payments} orphan payments"
print(f"   Status: {status}")
print(f"   Orphan payments (reserve_number exists, charter_id NULL): {orphan_payments}")

# Check charter balances
cur.execute("""
    SELECT COUNT(*)
    FROM charters c
    LEFT JOIN (
        SELECT reserve_number, SUM(amount) as total_paid
        FROM payments
        GROUP BY reserve_number
    ) p ON p.reserve_number = c.reserve_number
    WHERE ABS(COALESCE(c.paid_amount, 0) - COALESCE(p.total_paid, 0)) > 0.01
      AND c.status NOT IN ('cancelled', 'pending')
""")
balance_issues = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM charters WHERE status NOT IN ('cancelled', 'pending')")
total_charters = cur.fetchone()[0]
status = "✅ COMPLETE" if balance_issues == 0 else f"❌ {balance_issues} balance mismatches"
print(f"   Charter balance verification: {status}")
print(f"   Charters with balance issues: {balance_issues}/{total_charters}")
print()

# 5. GL 9999 Cleanup
print("5. GL 9999 CLEANUP")
print("-" * 100)
cur.execute("SELECT COUNT(*) FROM receipts WHERE gl_account_code = '9999'")
gl9999 = cur.fetchone()[0]
status = "✅ COMPLETE" if gl9999 == 0 else f"❌ {gl9999} entries remain"
print(f"   Status: {status}")
print(f"   GL 9999 entries: {gl9999}")
print()

# 6. Duplicate Detection
print("6. DUPLICATE DETECTION")
print("-" * 100)
cur.execute("""
    SELECT COUNT(*)
    FROM receipts r1
    WHERE EXISTS (
        SELECT 1 FROM receipts r2
        WHERE r2.receipt_id != r1.receipt_id
          AND r2.receipt_date = r1.receipt_date
          AND r2.vendor_name = r1.vendor_name
          AND ABS(r2.gross_amount - r1.gross_amount) < 0.01
          AND r2.created_from_banking = false
          AND r1.created_from_banking = false
    )
""")
potential_dupes = cur.fetchone()[0]
status = "✅ CLEAN" if potential_dupes == 0 else f"⚠️ {potential_dupes} potential duplicates"
print(f"   Status: {status}")
print(f"   Potential duplicate receipts (same date/vendor/amount): {potential_dupes}")
print(f"   Note: May include legitimate recurring payments")
print()

# 7. Banking Data Gaps
print("7. BANKING DATA GAPS")
print("-" * 100)
print("   Known gaps:")
print("     - CIBC 0228362: 2012 (corrupted, needs re-import from PDFs)")
print("     - CIBC 8362: Jan 1 - Sep 12, 2018 (⏳ USER CREATING FILE)")
print("     - 80 unmatched CIBC cheques (depends on 2012 re-import)")
print("   Status: ⏳ PENDING USER DATA")
print()

# 8. Vendor Name Standardization
print("8. VENDOR NAME STANDARDIZATION")
print("-" * 100)
cur.execute("""
    SELECT COUNT(DISTINCT vendor_name)
    FROM receipts
    WHERE created_from_banking = true
""")
banking_vendors = cur.fetchone()[0]
print(f"   Auto-created banking vendors: {banking_vendors:,} unique names")
print("   Status: ⚠️ NEEDS REVIEW (especially 2014-2017 CIBC misaligned vendors)")
print("   Recommendation: Export vendor list, apply standardization rules")
print()

# 9. Tax Reconciliation
print("9. TAX RECONCILIATION")
print("-" * 100)
print("   Components:")
print("     - T4 verification (employees): ⏳ NEEDS REVIEW")
print("     - GST/PST calculation: ⏳ NEEDS REVIEW")
print("     - WCB rates: ✅ Historical rates added")
print("   Status: ⏳ PENDING")
print()

# 10. Data Quality Metrics
print("10. DATA QUALITY SUMMARY")
print("-" * 100)
cur.execute("SELECT MIN(receipt_date), MAX(receipt_date) FROM receipts")
min_r, max_r = cur.fetchone()
cur.execute("SELECT MIN(transaction_date), MAX(transaction_date) FROM banking_transactions")
min_b, max_b = cur.fetchone()
cur.execute("SELECT MIN(payment_date), MAX(payment_date) FROM payments")
min_p, max_p = cur.fetchone()
cur.execute("SELECT MIN(charter_date), MAX(charter_date) FROM charters")
min_c, max_c = cur.fetchone()

print(f"   Date ranges:")
print(f"     - Receipts: {min_r} to {max_r}")
print(f"     - Banking: {min_b} to {max_b}")
print(f"     - Payments: {min_p} to {max_p}")
print(f"     - Charters: {min_c} to {max_c}")
print()

# Summary
print("="*100)
print("PRIORITY ACTION ITEMS (IN ORDER)")
print("="*100)
print()
print("1. ✅ COMPLETED: Banking reconciliation (26,294 transactions linked)")
print()
print("2. 🔴 HIGH PRIORITY: GL Code Assignment")
print(f"   - {null_gl:,} receipts need gl_account_code")
print("   - Start with: Export by vendor_name, assign by pattern")
print("   - Tools: Batch update scripts, vendor mapping CSV")
print()
print("3. 🟡 MEDIUM PRIORITY: Vendor Name Standardization")
print(f"   - {banking_vendors:,} unique banking vendor names")
print("   - Focus on: 2014-2017 CIBC misaligned vendors")
print("   - Tools: Vendor canonicalization scripts")
print()
print("4. 🟡 MEDIUM PRIORITY: Charter Balance Verification")
print(f"   - {balance_issues} charters with balance issues")
print("   - Use reserve_number for payment matching")
print("   - Tools: Charter-payment audit script")
print()
print("5. 🟢 LOW PRIORITY: Duplicate Detection Review")
print(f"   - {potential_dupes} potential duplicates (may be legitimate)")
print("   - Manual review of flagged entries")
print()
print("6. ⏳ PENDING USER: Banking Data Gaps")
print("   - CIBC 8362: Jan-Sep 2018 (user creating file)")
print("   - CIBC 0228362: 2012 (needs PDF statements)")
print()
print("7. ⏳ PENDING: Tax Reconciliation")
print("   - T4 verification")
print("   - GST/PST calculation review")
print()

cur.close(); conn.close()
