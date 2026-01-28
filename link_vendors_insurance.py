#!/usr/bin/env python3
"""
LINK VENDOR/INSURANCE PAYMENTS (Phase 2)
- Insurance APF payments
- Heffner/Centratech
- Business expense vendors
"""

import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

DRY_RUN = "--dry-run" in __import__("sys").argv

def main():
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    mode = "DRY RUN" if DRY_RUN else "PRODUCTION"
    print("\n" + "=" * 100)
    print(f"VENDOR/INSURANCE PAYMENT LINKING - {mode}")
    print("=" * 100)
    
    # Get special vendor/insurance clients
    print("\n1️⃣ LOADING SPECIAL CLIENTS:")
    print("-" * 100)
    
    vendors = {
        'HEFFNER': 3980,
        'ALBERTA INSURANCE': 5133,
        'SWIFT': 5811,
        'CENTRATECH': None,
        'APF': None,
    }
    
    # Get all unmatched with vendor/insurance patterns
    print("\n2️⃣ LOADING VENDOR/INSURANCE PAYMENTS:")
    print("-" * 100)
    
    cur.execute("""
        SELECT transaction_id, transaction_date, credit_amount, debit_amount, description
        FROM banking_transactions
        WHERE reconciled_payment_id IS NULL
        AND (
            description ILIKE '%HEFFNER%' OR
            description ILIKE '%CENTRATECH%' OR
            description ILIKE '%GLOBAL%' OR
            description ILIKE '%INSURANCE%' OR
            description ILIKE '%APF%'
        )
        ORDER BY transaction_date DESC
    """)
    
    vendor_trans = cur.fetchall()
    print(f"   Found {len(vendor_trans)} vendor/insurance transactions")
    
    # Group by pattern
    by_type = {
        'HEFFNER': [],
        'CENTRATECH': [],
        'GLOBAL': [],
        'INSURANCE': [],
        'APF': [],
        'OTHER': []
    }
    
    total_amount = 0
    for trans_id, date, credit, debit, desc in vendor_trans:
        amount = (credit if credit else 0) + (debit if debit else 0)
        amount = abs(amount)
        total_amount += amount
        
        desc_upper = desc.upper() if desc else ""
        
        if 'HEFFNER' in desc_upper:
            by_type['HEFFNER'].append((trans_id, amount, desc, date))
        elif 'CENTRATECH' in desc_upper:
            by_type['CENTRATECH'].append((trans_id, amount, desc, date))
        elif 'GLOBAL' in desc_upper:
            by_type['GLOBAL'].append((trans_id, amount, desc, date))
        elif 'INSURANCE' in desc_upper:
            by_type['INSURANCE'].append((trans_id, amount, desc, date))
        elif 'APF' in desc_upper:
            by_type['APF'].append((trans_id, amount, desc, date))
        else:
            by_type['OTHER'].append((trans_id, amount, desc, date))
    
    print(f"\n3️⃣ VENDOR/INSURANCE BREAKDOWN:")
    print("-" * 100)
    
    for category, trans_list in sorted(by_type.items(), key=lambda x: -sum(t[1] for t in x[1])):
        if trans_list:
            amount = sum(t[1] for t in trans_list)
            print(f"   {category:15s}: {len(trans_list):5d} trans | ${amount:12,.2f}")
    
    print(f"   {'TOTAL':15s}: {len(vendor_trans):5d} trans | ${total_amount:12,.2f}")
    
    # Link them
    if not DRY_RUN:
        print(f"\n4️⃣ LINKING TRANSACTIONS:")
        print("-" * 100)
        
        linked = 0
        failed = 0
        
        for trans_id, date, credit, debit, desc in vendor_trans:
            try:
                amount = (credit if credit else 0) + (debit if debit else 0)
                amount = abs(amount)
                
                # Determine reserve_number
                desc_upper = desc.upper() if desc else ""
                if 'HEFFNER' in desc_upper:
                    reserve = 'VENDOR_HEFFNER'
                elif 'CENTRATECH' in desc_upper:
                    reserve = 'VENDOR_CENTRATECH'
                elif 'GLOBAL' in desc_upper:
                    reserve = 'VENDOR_GLOBAL'
                elif 'INSURANCE' in desc_upper or 'APF' in desc_upper:
                    reserve = 'VENDOR_INSURANCE'
                else:
                    reserve = 'VENDOR_OTHER'
                
                # Create payment
                cur.execute("""
                    INSERT INTO payments
                    (reserve_number, amount, payment_date, payment_method, status, notes, created_at, updated_at)
                    VALUES (%s, %s, %s, 'bank_transfer', 'paid', %s, NOW(), NOW())
                    RETURNING payment_id
                """, (reserve, amount, date, f'Vendor e-transfer: {desc[:80]}'))
                
                payment_id = cur.fetchone()[0]
                
                # Link banking
                cur.execute("""
                    UPDATE banking_transactions
                    SET reconciled_payment_id = %s, updated_at = NOW()
                    WHERE transaction_id = %s
                """, (payment_id, trans_id))
                
                conn.commit()
                linked += 1
                
                if linked % 500 == 0:
                    print(f"   ... {linked} linked")
                    
            except Exception as e:
                failed += 1
                if failed <= 3:
                    print(f"   ❌ Trans {trans_id}: {str(e)[:60]}")
        
        print(f"   ✅ Linked: {linked} | Failed: {failed}")
    
    else:
        print(f"\n4️⃣ DRY RUN - Would link {len(vendor_trans)} transactions (${total_amount:,.2f})")
    
    # Verify
    print(f"\n5️⃣ VERIFICATION:")
    print("-" * 100)
    
    cur.execute("SELECT COUNT(*) FROM banking_transactions WHERE reconciled_payment_id IS NULL")
    remaining = cur.fetchone()[0]
    
    print(f"   Remaining unmatched: {remaining}")
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 100 + "\n")

if __name__ == "__main__":
    main()
