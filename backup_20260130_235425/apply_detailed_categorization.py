"""
Apply detailed categorizations from user:
- Driver payments (Jack Carter, Paul Mansell, Michael Richard, Mark Linton, Keith Dixon, Tammy Pettitt, Mike Woodrow)
- Personal/Finance (MCAP, MONEY MART WITHDRAWAL)
- Insurance (FIRST INSURANCE, ALL SERVICE INSURANCE, ALL SERVICE INSURNACE typo)
- Beverages (PLENTY OF LIQUOR)
- CRA/Tax (RECEIVER GENERAL, ATTACHMENT ORDER)
- Bank Fees (OVERDRAFT INTEREST)
- Need banking descriptions for: DRAFT, BILL PAYMENT, BUSINESS EXPENSE, LFG BUSINESS PAD
- JOURNAL ENTRY is fake (may need deletion)
"""
import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***')
)
cur = conn.cursor()

updates = [
    # Drivers/Staff
    ("JACK CARTER", "2100", "Vehicle Lease/Finance", "Vehicle finance - Jack Carter"),
    ("PAUL MANSELL", "6900", "Driver Payment", "Driver payment - Paul Mansell"),
    ("MICHAEL RICHARD", "6900", "Driver Payment", "Driver payment - Michael Richard"),
    ("ETRANSFER MICHAEL RICHARD", "6900", "Driver Payment", "Driver payment - Michael Richard"),
    ("MARK LINTON", "6900", "Driver Payment", "Driver payment - Mark Linton"),
    ("KEITH DIXON", "6900", "Driver Payment", "Driver payment - Keith Dixon"),
    ("ETRANSFER KEITH DIXON", "6900", "Driver Payment", "Driver payment - Keith Dixon"),
    ("TAMMY PETTITT", "6900", "Office Staff", "Office staff payment"),
    ("MIKE WOODROW", "5410", "Rent", "Rent payment - Mike Woodrow"),
    ("ETRANSFER MIKE WOODROW", "5410", "Rent", "Rent payment - Mike Woodrow"),
    
    # Personal/Finance
    ("MCAP SERVICES-RMG MORTGAGES", "9999", "Personal Draws", "Personal mortgage payment"),
    ("MONEY MART WITHDRAWAL", "6900", "Loan Withdrawal", "Money Mart loan (split later)"),
    
    # Insurance
    ("FIRST INSURANCE", "5150", "Vehicle Insurance", "Vehicle insurance"),
    ("FIRST INSURNACE", "5150", "Vehicle Insurance", "Vehicle insurance"),
    ("ALL SERVICE INSURANCE", "5150", "Vehicle Insurance", "Vehicle insurance"),
    ("ALL SERVICE INSURNACE", "5150", "Vehicle Insurance", "Vehicle insurance"),
    
    # Beverages
    ("PLENTY OF LIQUOR", "4115", "Client Beverages", "Client beverage purchase"),
    
    # CRA/Tax
    ("RECEIVER GENERAL - 861556827 RT0001", "6900", "CRA Tax Payment", "CRA tax payment"),
    ("G-49416-90399 ATTACHMENT ORDER", "6900", "CRA Attachment", "CRA wage/asset garnishment"),
    
    # Bank Fees
    ("OVERDRAFT INTEREST", "6500", "Bank Fees", "Overdraft interest charge"),
]

print("=== DETAILED CATEGORIZATION ===\n")

total_updated = 0
for vendor, gl_code, category, notes in updates:
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(gross_amount), 0)
        FROM receipts
        WHERE vendor_name = %s
        AND (gl_account_code IS NULL OR gl_account_code = '' OR gl_account_code = '6900')
    """, (vendor,))
    
    count, total = cur.fetchone()
    if count > 0:
        cur.execute("""
            UPDATE receipts
            SET gl_account_code = %s,
                gl_account_name = %s,
                category = %s,
                auto_categorized = true
            WHERE vendor_name = %s
            AND (gl_account_code IS NULL OR gl_account_code = '' OR gl_account_code = '6900')
        """, (gl_code, f"GL {gl_code}", category, vendor))
        
        total_updated += count
        print(f"✅ {vendor:<45} {count:>4} receipts  ${total:>13,.0f}  → GL {gl_code}")

conn.commit()

# Show vendors needing banking description review
print("\n" + "=" * 80)
print("VENDORS NEEDING BANKING DESCRIPTION REVIEW:")
print("=" * 80 + "\n")

need_review = [
    ("DRAFT PURCHASE", "Debit via draft - money check to vendor"),
    ("BILL PAYMENT", "Bill payment - need banking desc to identify"),
    ("BUSINESS EXPENSE", "May be error - need banking desc to verify"),
    ("LFG BUSINESS PAD", "Pre-authorized debit - need banking desc"),
    ("CREDIT MEMO", "Credit memo - need banking desc"),
    ("DEBIT VIA DRAFT", "Debit via draft - money check to vendor"),
]

for vendor, note in need_review:
    cur.execute("""
        SELECT 
            r.receipt_id,
            r.receipt_date,
            r.gross_amount,
            r.banking_transaction_id,
            bt.description
        FROM receipts r
        LEFT JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
        WHERE r.vendor_name = %s
        AND (r.gl_account_code IS NULL OR r.gl_account_code = '' OR r.gl_account_code = '6900')
        ORDER BY r.receipt_date DESC
        LIMIT 5
    """, (vendor,))
    
    results = cur.fetchall()
    if results:
        print(f"\n{vendor} ({note})")
        print("-" * 80)
        for receipt_id, receipt_date, gross_amount, btid, bt_desc in results:
            print(f"  {receipt_id:6d} | {receipt_date} | ${gross_amount:>10,.2f} | {bt_desc}")

print("\n" + "=" * 80)
print(f"✅ Total updated: {total_updated} receipts")

cur.close()
conn.close()
