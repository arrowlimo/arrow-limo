#!/usr/bin/env python3
"""Add currency columns and backfill USD amounts with FX rates from banking."""

import os
import psycopg2
import re
from decimal import Decimal

def main():
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***'),
    )
    cur = conn.cursor()
    
    # Add currency columns if not exists
    print("Adding currency columns...")
    try:
        cur.execute("ALTER TABLE receipts ADD COLUMN IF NOT EXISTS currency VARCHAR(10) DEFAULT 'CAD'")
        cur.execute("ALTER TABLE receipts ADD COLUMN IF NOT EXISTS amount_usd DECIMAL(12,2)")
        cur.execute("ALTER TABLE receipts ADD COLUMN IF NOT EXISTS fx_rate DECIMAL(10,6)")
        conn.commit()
        print("✅ Added currency, amount_usd, fx_rate columns to receipts table")
    except Exception as e:
        print(f"⚠️  Columns may already exist: {e}")
        conn.rollback()
    
    # Load banking data with USD and FX info
    print("\nLoading banking transactions with USD/FX data...")
    cur.execute("""
        SELECT transaction_date, description, debit_amount
        FROM banking_transactions
        WHERE (description ILIKE '%WIX%' OR description ILIKE '%IONOS%' OR description ILIKE '%1&1%')
        AND debit_amount > 0
        AND description ILIKE '%USD @%'
        ORDER BY transaction_date
    """)
    
    banking_data = {}
    for txn_date, desc, cad_amount in cur.fetchall():
        # Extract USD amount and FX rate from description
        # Format: "... 18.00 USD @ 1.432222 ..."
        match = re.search(r'(\d+\.?\d*)\s+USD\s+@\s+(\d+\.?\d+)', desc)
        if match:
            usd_amount = Decimal(match.group(1))
            fx_rate = Decimal(match.group(2))
            
            # Determine vendor
            vendor = None
            if 'WIX' in desc.upper():
                vendor = 'Wix'
            elif 'IONOS' in desc.upper() or '1&1' in desc.upper():
                vendor = 'IONOS'
            
            if vendor:
                key = (txn_date, vendor, float(cad_amount))
                banking_data[key] = (usd_amount, fx_rate)
    
    print(f"✅ Loaded {len(banking_data)} banking transactions with USD/FX data")
    
    # Backfill Wix receipts
    print("\nBackfilling Wix receipts...")
    cur.execute("""
        SELECT receipt_id, receipt_date, gross_amount, description
        FROM receipts
        WHERE vendor_name ILIKE 'wix%'
        ORDER BY receipt_date
    """)
    
    wix_backfilled = 0
    wix_tagged = 0
    wix_david = 0
    for receipt_id, receipt_date, cad_amount, desc in cur.fetchall():
        # Try to find matching banking transaction
        key = (receipt_date, 'Wix', float(cad_amount))
        
        if key in banking_data:
            usd_amount, fx_rate = banking_data[key]
            cur.execute("""
                UPDATE receipts
                SET currency = 'USD', amount_usd = %s, fx_rate = %s
                WHERE receipt_id = %s
            """, (float(usd_amount), float(fx_rate), receipt_id))
            wix_backfilled += 1
        else:
            # No banking match - David paid for reimbursement/loan
            cur.execute("""
                UPDATE receipts
                SET currency = 'USD', description = %s
                WHERE receipt_id = %s
            """, (f"{desc or 'Wix subscription'} (David paid - reimbursement/loan)", receipt_id))
            wix_david += 1
            wix_tagged += 1
    
    print(f"✅ Backfilled {wix_backfilled} Wix receipts with USD/FX from banking")
    print(f"✅ Tagged {wix_david} Wix receipts as David paid (reimbursement/loan)")
    print(f"✅ Tagged {wix_tagged} Wix receipts as USD total")
    
    # Backfill IONOS receipts
    print("\nBackfilling IONOS receipts...")
    cur.execute("""
        SELECT receipt_id, receipt_date, gross_amount, description
        FROM receipts
        WHERE vendor_name ILIKE 'ionos%'
        ORDER BY receipt_date
    """)
    
    ionos_backfilled = 0
    ionos_tagged = 0
    ionos_david = 0
    for receipt_id, receipt_date, cad_amount, desc in cur.fetchall():
        # Try to find matching banking transaction
        key = (receipt_date, 'IONOS', float(cad_amount))
        
        if key in banking_data:
            usd_amount, fx_rate = banking_data[key]
            cur.execute("""
                UPDATE receipts
                SET currency = 'USD', amount_usd = %s, fx_rate = %s
                WHERE receipt_id = %s
            """, (float(usd_amount), float(fx_rate), receipt_id))
            ionos_backfilled += 1
        else:
            # No banking match - David paid for reimbursement/loan
            cur.execute("""
                UPDATE receipts
                SET currency = 'USD', description = %s
                WHERE receipt_id = %s
            """, (f"{desc or 'IONOS hosting'} (David paid - reimbursement/loan)", receipt_id))
            ionos_david += 1
            ionos_tagged += 1
    
    print(f"✅ Backfilled {ionos_backfilled} IONOS receipts with USD/FX from banking")
    print(f"✅ Tagged {ionos_david} IONOS receipts as David paid (reimbursement/loan)")
    print(f"✅ Tagged {ionos_tagged} IONOS receipts as USD total")
    
    # Tag GoDaddy as USD (no FX data available in banking - likely David paid)
    print("\nTagging GoDaddy receipts as USD (David paid)...")
    cur.execute("""
        UPDATE receipts 
        SET currency = 'USD',
            description = COALESCE(description, '') || ' (David paid - reimbursement/loan)'
        WHERE vendor_name ILIKE 'godaddy%'
        AND (currency IS NULL OR currency = 'CAD')
        AND description NOT ILIKE '%David paid%'
    """)
    godaddy_count = cur.rowcount
    print(f"✅ Tagged {godaddy_count} GoDaddy receipts as USD (David paid)")
    
    conn.commit()
    
    # Verify
    cur.execute("""
        SELECT 
            CASE 
                WHEN vendor_name ILIKE 'godaddy%' THEN 'GoDaddy'
                WHEN vendor_name ILIKE 'wix%' THEN 'Wix'
                WHEN vendor_name ILIKE 'ionos%' THEN 'IONOS'
            END as vendor,
            COUNT(*) as count,
            COUNT(CASE WHEN amount_usd IS NOT NULL THEN 1 END) as with_usd,
            SUM(gross_amount) as total_cad,
            SUM(amount_usd) as total_usd
        FROM receipts
        WHERE (vendor_name ILIKE 'godaddy%' OR vendor_name ILIKE 'wix%' OR vendor_name ILIKE 'ionos%')
        AND currency = 'USD'
        GROUP BY vendor
        ORDER BY vendor
    """)
    
    print("\n" + "="*70)
    print("VERIFICATION: Receipts with USD Currency Data")
    print("="*70)
    print(f"{'Vendor':<10} │ {'Total':>5} │ {'With USD/FX':>11} │ {'CAD Posted':>12} │ {'USD Face':>12}")
    print("-"*70)
    
    for row in cur.fetchall():
        vendor, count, with_usd, total_cad, total_usd = row
        total_cad = total_cad or 0
        total_usd = total_usd or 0
        usd_str = f"${total_usd:,.2f}" if total_usd > 0 else "N/A"
        print(f"{vendor:<10} │ {count:>5} │ {with_usd:>11} │ ${total_cad:>11,.2f} │ {usd_str:>12}")
    
    print("\n" + "="*70)
    print("✅ CURRENCY BACKFILL COMPLETE")
    print(f"   - Wix: {wix_backfilled} with USD/FX from banking, {wix_david} David paid")
    print(f"   - IONOS: {ionos_backfilled} with USD/FX from banking, {ionos_david} David paid")
    print(f"   - GoDaddy: {godaddy_count} David paid (no banking records)")
    print("\n   Note: gross_amount = CAD posted on statements (or estimated for David)")
    print("         amount_usd = original USD billing amount (where available)")
    print("         fx_rate = exchange rate used (where available)")
    print("         'David paid' = Paid personally, to be reimbursed or part of loan\n")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
