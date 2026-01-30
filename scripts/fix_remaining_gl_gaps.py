"""
1. Categorize credit memos (CC scanner/POS deposits)
2. Check CORRECTION 00339 in banking for NSF/cancelled details
3. Categorize BRANCH TRANSACTION WITHDRAWAL as GL 9999
4. Match [UNKNOWN POINT OF SALE] to banking descriptions
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

print("=" * 80)
print("1. CREDIT MEMOS (CC Scanner/POS deposits)")
print("=" * 80)

# Categorize credit memos as GL 1010 Bank Deposit
credit_memo_vendors = [
    'CREDIT MEMO 4017775 VISA',
    'CREDIT MEMO 4017775 MC',
    'CREDIT MEMO 4017775 IDP',
]

for vendor in credit_memo_vendors:
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
            SET gl_account_code = '1010',
                gl_account_name = 'GL 1010',
                category = 'Bank Deposit',
                auto_categorized = true
            WHERE vendor_name = %s
            AND (gl_account_code IS NULL OR gl_account_code = '' OR gl_account_code = '6900')
        """, (vendor,))
        print(f"✅ {vendor:<35} {count:>4} receipts  ${total:>13,.0f}")

conn.commit()

print("\n" + "=" * 80)
print("2. CORRECTION 00339 - Check banking for NSF/cancelled details")
print("=" * 80)

# Find CORRECTION 00339 receipts and link to banking
cur.execute("""
    SELECT 
        r.receipt_id,
        r.receipt_date,
        r.gross_amount,
        r.banking_transaction_id,
        bt.transaction_date,
        bt.description,
        bt.is_nsf_charge,
        bt.reconciliation_status
    FROM receipts r
    LEFT JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.vendor_name = 'CORRECTION 00339'
    ORDER BY r.receipt_date
    LIMIT 10
""")

results = cur.fetchall()
print(f"\nFound {len(results)} CORRECTION 00339 receipts")
for receipt_id, receipt_date, gross_amount, btid, bt_date, bt_desc, is_nsf, recon_status in results:
    print(f"\nReceipt {receipt_id} | {receipt_date} | ${gross_amount:,.2f}")
    if btid:
        print(f"  Bank TX: {bt_date} | {bt_desc}")
        print(f"  NSF: {is_nsf} | Recon Status: {recon_status}")
    else:
        print(f"  Not linked to banking!")

print("\n" + "=" * 80)
print("3. BRANCH TRANSACTION WITHDRAWAL - Categorize as GL 9999 (Cash Withdrawal)")
print("=" * 80)

cur.execute("""
    SELECT COUNT(*), COALESCE(SUM(gross_amount), 0)
    FROM receipts
    WHERE vendor_name LIKE 'BRANCH TRANSACTION WITHDRAWAL%'
    AND (gl_account_code IS NULL OR gl_account_code = '' OR gl_account_code = '6900')
""")

count, total = cur.fetchone()
if count > 0:
    cur.execute("""
        UPDATE receipts
        SET gl_account_code = '9999',
            gl_account_name = 'GL 9999',
            category = 'Personal Draws',
            auto_categorized = true
        WHERE vendor_name LIKE 'BRANCH TRANSACTION WITHDRAWAL%'
        AND (gl_account_code IS NULL OR gl_account_code = '' OR gl_account_code = '6900')
    """)
    conn.commit()
    print(f"✅ BRANCH TRANSACTION WITHDRAWAL    {count:>4} receipts  ${total:>13,.0f}")

print("\n" + "=" * 80)
print("4. [UNKNOWN POINT OF SALE] - Match to banking descriptions")
print("=" * 80)

# Get unknown POS receipts linked to banking
cur.execute("""
    SELECT 
        r.receipt_id,
        r.receipt_date,
        r.gross_amount,
        r.banking_transaction_id,
        bt.transaction_date,
        bt.description
    FROM receipts r
    LEFT JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.vendor_name = '[UNKNOWN POINT OF SALE]'
    AND r.banking_transaction_id IS NOT NULL
    ORDER BY r.receipt_date
    LIMIT 15
""")

results = cur.fetchall()
print(f"\nFound {len(results)} [UNKNOWN POINT OF SALE] receipts linked to banking")
for receipt_id, receipt_date, gross_amount, btid, bt_date, bt_desc in results:
    print(f"\nReceipt {receipt_id} | {receipt_date} | ${gross_amount:,.2f}")
    print(f"  Bank Desc: {bt_desc}")
    
    # Extract potential vendor name from bank description
    # Common patterns: vendor names after certain keywords
    if bt_desc:
        # Try to extract vendor - usually after "POS" or "ATM" or "-"
        vendor_guess = bt_desc.strip()
        print(f"  → Could be: {vendor_guess}")

cur.close()
conn.close()
