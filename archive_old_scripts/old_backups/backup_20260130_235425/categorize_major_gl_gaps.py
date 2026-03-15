"""
Categorize major GL gaps:
1. BANK WITHDRAWAL → GL 9999 (Personal Draws/Cash Out)
2. SQUARE DEPOSIT → GL 1010 (Bank Deposit - residual from client payments)
3. WAREHOUSE ONE → GL 9999 (Clothing personal use)
4. ETRANSFERs → GL 9999 (Personal Draws)
5. IFS/HEFFNER/RIFCO FINANCE → GL 2100 (Vehicle Lease/Finance)
6. CARD DEPOSITS (VCARD, MCARD, ACARD) → GL 1010 (Bank Deposit)
7. WOODRIDGE FORD, HEFFNER AUTO → GL 5100 (Vehicle Maintenance)
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
    # GL 9999 - Personal Draws/Cash Out
    ("BANK WITHDRAWAL", "9999", "Personal Draws", "Cash withdrawal"),
    ("ETRANSFER HEFFNER", "9999", "Personal Draws", "E-transfer payment"),
    ("ETRANSFER DAVID RICHARD", "9999", "Personal Draws", "E-transfer payment"),
    ("WAREHOUSE ONE", "9999", "Personal Draws", "Clothing personal use"),
    ("CASH WITHDRAWAL", "9999", "Personal Draws", "Cash withdrawal"),
    ("WITHDRAWAL IBB", "9999", "Personal Draws", "Cash withdrawal"),
    
    # GL 1010 - Bank Deposits
    ("SQUARE DEPOSIT", "1010", "Bank Deposit", "Client payment residual"),
    ("VCARD DEPOSIT", "1010", "Bank Deposit", "Card payment deposit"),
    ("MCARD DEPOSIT", "1010", "Bank Deposit", "Card payment deposit"),
    ("ACARD DEPOSIT", "1010", "Bank Deposit", "Card payment deposit"),
    ("CASH DEPOSIT", "1010", "Bank Deposit", "Cash deposit"),
    ("CUSTOMER DEPOSIT", "1010", "Bank Deposit", "Customer deposit"),
    
    # GL 2100 - Vehicle Finance
    ("IFS PREMIUM FINANCE", "2100", "Vehicle Lease/Finance", "Vehicle finance"),
    ("HEFFNER AUTO FINANCE", "2100", "Vehicle Lease/Finance", "Vehicle finance"),
    ("HEFFNER AUTO FINANCING", "2100", "Vehicle Lease/Finance", "Vehicle finance"),
    ("ASI FINANCE", "2100", "Vehicle Lease/Finance", "Vehicle finance"),
    ("ASI FINANCIAL", "2100", "Vehicle Lease/Finance", "Vehicle finance"),
    ("RIFCO", "2100", "Vehicle Lease/Finance", "Vehicle finance"),
    ("LEASE FINANCE", "2100", "Vehicle Lease/Finance", "Vehicle finance"),
    ("EQUITY PREMIUM FINANCE", "2100", "Vehicle Lease/Finance", "Vehicle finance"),
    
    # GL 5100 - Vehicle Maintenance
    ("WOODRIDGE FORD", "5100", "Vehicle Maintenance & Repair", "Vehicle maintenance"),
    
    # GL 6500 - Bank Fees
    ("GLOBAL MERCHANT FEES", "6500", "Bank Fees", "Merchant service fees"),
    ("SERVICE CHARGE", "6500", "Bank Fees", "Bank service charge"),
    ("NSF CHARGE", "6500", "Bank Fees", "Non-sufficient funds charge"),
]

print("=== CATEGORIZING MAJOR GL GAPS ===\n")

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
        # Update the receipts
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
        print(f"✅ {vendor:<30} {count:>4} receipts  ${total:>13,.0f}  → GL {gl_code}")

conn.commit()
print(f"\n✅ Total receipts updated: {total_updated}")

cur.close()
conn.close()
