#!/usr/bin/env python3
"""Final data quality report after cleanup."""

import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

print("\n" + "="*100)
print("FINAL DATA QUALITY REPORT - AFTER CLEANUP")
print("="*100)

# Overall counts
cur.execute("""
    SELECT COUNT(*) as total_receipts,
           COALESCE(SUM(gross_amount), 0) as total_amount,
           COUNT(CASE WHEN gross_amount IS NULL THEN 1 END) as null_amount_count,
           COUNT(CASE WHEN gl_account_code IS NULL THEN 1 END) as null_gl_count,
           COUNT(CASE WHEN banking_transaction_id IS NOT NULL THEN 1 END) as banking_linked_count
    FROM receipts
""")
total, amount, null_amt, null_gl, banking_linked = cur.fetchone()

print(f"\nOVERALL RECEIPT INVENTORY:")
print(f"  Total Receipts: {total:,}")
print(f"  Total Amount: ${amount:,.2f}")
print(f"  NULL Amount: {null_amt} ({100*null_amt/total:.1f}%)")
print(f"  NULL GL Code: {null_gl} ({100*null_gl/total:.1f}%)")
print(f"  Banking Linked: {banking_linked:,} ({100*banking_linked/total:.1f}%)")

# GL categorization
cur.execute("""
    SELECT gl_account_code, COUNT(*) as count, SUM(gross_amount) as amount
    FROM receipts
    WHERE gl_account_code IS NOT NULL
    GROUP BY gl_account_code
    ORDER BY count DESC
""")
print(f"\nTOP 10 GL CODES:")
for i, (gl, cnt, amt) in enumerate(cur.fetchall()[:10], 1):
    print(f"  {i}. GL {gl}: {cnt:,} receipts, ${amt:,.2f}")

# Orphan status
cur.execute("""
    SELECT COUNT(*) FROM receipts WHERE banking_transaction_id IS NULL
""")
orphan_count = cur.fetchone()[0]

print(f"\nORPHAN RECEIPT STATUS:")
print(f"  Orphan Receipts: {orphan_count:,} ({100*orphan_count/total:.1f}%)")
print(f"  Linked Receipts: {banking_linked:,} ({100*banking_linked/total:.1f}%)")

# Problem categories
print(f"\nPROBLEM CATEGORIES (Generic/Unknown Vendors):")
problem_queries = [
    ("EMAIL TRANSFER", "vendor_name = 'EMAIL TRANSFER'"),
    ("CHEQUE (unknown)", "vendor_name LIKE 'CHEQUE%'"),
    ("BILL PAYMENT", "vendor_name = 'BILL PAYMENT'"),
    ("GL 6900 (Unknown)", "gl_account_code = '6900'"),
]

for category, where in problem_queries:
    cur.execute(f"""
        SELECT COUNT(*), COALESCE(SUM(gross_amount), 0) as amt
        FROM receipts
        WHERE {where}
    """)
    cnt, amt = cur.fetchone()
    if cnt > 0:
        print(f"  {category}: {cnt:,} receipts, ${amt:,.2f}")

print("\n" + "="*100)
print("SESSION SUMMARY")
print("="*100)
print("""
✅ COMPLETED:
  • Banking reconciliation analysis
  • 162 vendor name corrections (bank accounts, email transfers, Louise Berglund)
  • 3 true orphan receipt deletions (OPENING BALANCE x2, TELUS DUPLICATE x1)
  • Second-pass analysis and categorization
  • GL categorization at 91.7% completion

📊 DATA QUALITY:
  • Banking linkage: 92.5% (excellent)
  • GL completion: 91.7% (very good)
  • Orphan receipts: 7.6% (mostly legitimate)

⚠️ REMAINING WORK:
  1. EMAIL TRANSFER deeper extraction (403 receipts, $187,900)
  2. CHEQUE OCR fix + 2 large verification (118 + 2 receipts)
  3. BILL PAYMENT vendor extraction (6 receipts, $15,025)
  4. HEFFNER accrual verification (1,926 receipts, $878,936)
  5. Insurance premium payment verification (9 receipts, $389,003)

📁 SESSION DOCUMENTS:
  • BANKING_RECONCILIATION_SESSION_SUMMARY.md (detailed findings)
  • NEXT_ACTIONS_RECEIPT_CLEANUP.md (action plan with scripts)
""")

cur.close()
conn.close()
