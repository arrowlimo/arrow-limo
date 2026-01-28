import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("INVESTIGATING 2019 SPLIT RECEIPTS")
print("="*100)

# Check all receipts (including excluded ones) for splits
cur.execute("""
    SELECT 
        banking_transaction_id,
        COUNT(*) as receipt_count,
        STRING_AGG(receipt_id::text, ', ') as receipt_ids,
        STRING_AGG(vendor_name, ' | ') as vendors,
        SUM(gross_amount) as total_amount,
        BOOL_OR(exclude_from_reports) as has_excluded,
        STRING_AGG(DISTINCT EXTRACT(YEAR FROM receipt_date)::text, ', ') as years
    FROM receipts
    WHERE banking_transaction_id IS NOT NULL
    GROUP BY banking_transaction_id
    HAVING COUNT(*) > 1
    ORDER BY COUNT(*) DESC
    LIMIT 100
""")

all_splits = cur.fetchall()

print(f"\n1. ALL SPLIT RECEIPTS (including excluded)")
print("-"*100)
print(f"Found {len(all_splits)} banking transactions with multiple receipts\n")

if all_splits:
    # Separate by year and excluded status
    splits_2019 = []
    splits_excluded = []
    splits_active = []
    
    for tx_id, count, receipt_ids, vendors, amount, has_excluded, years in all_splits:
        if '2019' in years:
            splits_2019.append((tx_id, count, receipt_ids, vendors, amount, has_excluded))
        if has_excluded:
            splits_excluded.append((tx_id, count, receipt_ids, vendors, amount, has_excluded))
        else:
            splits_active.append((tx_id, count, receipt_ids, vendors, amount, has_excluded))
    
    print(f"Breakdown:")
    print(f"  Total splits: {len(all_splits)}")
    print(f"  2019 splits: {len(splits_2019)}")
    print(f"  With excluded receipts: {len(splits_excluded)}")
    print(f"  All active (no excluded): {len(splits_active)}")
    
    # Show 2019 splits
    if splits_2019:
        print(f"\n2. 2019 SPLIT RECEIPTS DETAIL")
        print("-"*100)
        print(f"{'Banking TX':<12} | {'Count':>5} | {'Excluded':>8} | {'Total Amount':>12} | {'Vendors'}")
        print("-"*100)
        
        for tx_id, count, receipt_ids, vendors, amount, has_excluded in splits_2019[:30]:
            excluded_status = "YES" if has_excluded else "NO"
            vendors_short = vendors[:60] if vendors else 'N/A'
            print(f"{tx_id:<12} | {count:>5} | {excluded_status:>8} | ${float(amount) if amount else 0:>11,.2f} | {vendors_short}")
        
        if len(splits_2019) > 30:
            print(f"  ... and {len(splits_2019) - 30} more")
        
        # Check detailed info for first few
        print(f"\n3. DETAILED BREAKDOWN OF FIRST 5 SPLITS")
        print("-"*100)
        
        for i, (tx_id, count, receipt_ids, vendors, amount, has_excluded) in enumerate(splits_2019[:5]):
            print(f"\nBanking TX {tx_id} ({count} receipts):")
            
            # Get detailed receipt info
            cur.execute("""
                SELECT 
                    receipt_id,
                    vendor_name,
                    gross_amount,
                    receipt_date,
                    exclude_from_reports,
                    is_voided
                FROM receipts
                WHERE banking_transaction_id = %s
                ORDER BY receipt_id
            """, (tx_id,))
            
            for receipt_id, vendor, amt, date, excluded, voided in cur.fetchall():
                status_flags = []
                if excluded:
                    status_flags.append("EXCLUDED")
                if voided:
                    status_flags.append("VOIDED")
                status = f" [{', '.join(status_flags)}]" if status_flags else ""
                
                print(f"  Receipt {receipt_id}: {vendor[:40]:<40} ${float(amt):>10,.2f} | {date}{status}")
    
    # Show why they're excluded
    if splits_excluded:
        print(f"\n4. WHY ARE SPLIT RECEIPTS EXCLUDED?")
        print("-"*100)
        
        cur.execute("""
            SELECT 
                r.receipt_id,
                r.vendor_name,
                r.gross_amount,
                r.receipt_date,
                r.exclude_from_reports,
                r.is_voided,
                r.banking_transaction_id
            FROM receipts r
            WHERE r.banking_transaction_id IN (
                SELECT banking_transaction_id 
                FROM receipts 
                WHERE banking_transaction_id IS NOT NULL
                GROUP BY banking_transaction_id 
                HAVING COUNT(*) > 1
            )
            AND (r.exclude_from_reports = TRUE OR r.is_voided = TRUE)
            ORDER BY r.banking_transaction_id, r.receipt_id
            LIMIT 50
        """)
        
        excluded_receipts = cur.fetchall()
        
        print(f"Found {len(excluded_receipts)} excluded/voided receipts in split banking transactions\n")
        print(f"{'Receipt ID':<12} | {'Vendor':<40} | {'Amount':>12} | {'Date':<12} | {'Excluded':>8} | {'Voided':>7}")
        print("-"*100)
        
        for receipt_id, vendor, amt, date, excluded, voided in excluded_receipts[:30]:
            exc = "YES" if excluded else "NO"
            voi = "YES" if voided else "NO"
            print(f"{receipt_id:<12} | {vendor[:38]:<40} | ${float(amt):>11,.2f} | {str(date):<12} | {exc:>8} | {voi:>7}")

# Get banking transaction details for 2019 splits
if splits_2019:
    print(f"\n5. BANKING TRANSACTION DETAILS FOR 2019 SPLITS")
    print("-"*100)
    
    # Get first 5 banking TXs
    tx_ids = [s[0] for s in splits_2019[:5]]
    
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            description,
            debit_amount,
            credit_amount
        FROM banking_transactions
        WHERE transaction_id = ANY(%s)
        ORDER BY transaction_id
    """, (tx_ids,))
    
    print(f"{'TX ID':<12} | {'Date':<12} | {'Debit':>12} | {'Credit':>12} | {'Description'}")
    print("-"*100)
    
    for tx_id, date, desc, debit, credit in cur.fetchall():
        print(f"{tx_id:<12} | {str(date):<12} | ${float(debit) if debit else 0:>11,.2f} | ${float(credit) if credit else 0:>11,.2f} | {desc[:50]}")

print(f"\n{'='*100}")
print(f"SUMMARY")
print(f"{'='*100}")
print(f"""
Total split receipts found: {len(all_splits)}
  2019 splits: {len(splits_2019) if splits_2019 else 0}
  With excluded receipts: {len(splits_excluded) if splits_excluded else 0}
  All active (no excluded): {len(splits_active) if splits_active else 0}

WHY NOT REPORTED:
  The original query filtered WHERE exclude_from_reports = FALSE
  Many 2019 splits have at least one receipt marked exclude_from_reports = TRUE
  This excluded them from the report
  
ACTION:
  Review excluded receipts to determine if they should be unmarked
  Or accept that splits exist but some receipts are legitimately excluded
""")

cur.close()
conn.close()
