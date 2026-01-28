#!/usr/bin/env python
"""Auto-categorize GL 9999 entries based on user-defined rules."""
import psycopg2, os, sys, json
from datetime import datetime

DB_HOST = os.environ.get('DB_HOST','localhost')
DB_NAME = os.environ.get('DB_NAME','almsdata')
DB_USER = os.environ.get('DB_USER','postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD',os.environ.get("DB_PASSWORD"))

DRY_RUN = '--dry-run' in sys.argv

# Auto-categorization rules based on vendor name and patterns
RULES = [
    # (condition_func, new_gl, description)
    (lambda v: v and 'TIM HORTONS' in v.upper(), '6800', 'Meals & Entertainment'),
    (lambda v: v and 'MCDONALD' in v.upper(), '6800', 'Meals & Entertainment'),
    (lambda v: v and 'WENDYS' in v.upper() or v and "WENDY'S" in v.upper(), '6800', 'Meals & Entertainment'),
    (lambda v: v and 'SOBEYS' in v.upper(), '6800', 'Meals & Entertainment'),
    (lambda v: v and 'SAFEWAY' in v.upper(), '6800', 'Meals & Entertainment'),
    (lambda v: v and 'SUPERSTORE' in v.upper() or v and 'COOP' in v.upper() or v and 'CO-OP' in v.upper(), '6800', 'Meals & Entertainment'),
    (lambda v: v and 'CINEPLEX' in v.upper(), '6800', 'Meals & Entertainment'),
    (lambda v: v and 'SUSHI' in v.upper(), '6800', 'Meals & Entertainment'),
    (lambda v: v and 'WALMART' in v.upper(), '6800', 'Meals & Entertainment'),
    
    # Fees → Bank Charges
    (lambda v: v and 'FEE' in v.upper(), '5400', 'Bank Charges'),
    (lambda v: v and 'ATM' in v.upper(), '5400', 'Bank Charges'),
    (lambda v: v and 'STATEMENT' in v.upper(), '5400', 'Bank Charges'),
    (lambda v: v and 'ACCOUNT FEE' in v.upper(), '5400', 'Bank Charges'),
    
    # Heffner → Vehicle Lease
    (lambda v: v and 'HEFFNER' in v.upper(), '3100', 'Vehicle Lease Payment'),
    
    # Bank/Cash Withdrawals → Owner Draws
    (lambda v: v and 'BANK WITHDRAWAL' in v.upper(), '3650', 'Cash/Owner Draw'),
    (lambda v: v and 'CASH WITHDRAWAL' in v.upper(), '3650', 'Cash/Owner Draw'),
    (lambda v: v and 'BRANCH TRANSACTION' in v.upper(), '3650', 'Cash/Owner Draw'),
    
    # Transfers → Owner Draw/Internal
    (lambda v: v and v.upper() == 'TRANSFER', '3650', 'Owner Draw/Transfer'),
    (lambda v: v and 'ETRANSFER' in v.upper() and 'HEFFNER' not in v.upper(), '3650', 'Owner Draw/E-transfer'),
    
    # Corrections → Keep as 9999 for manual banking matching
    (lambda v: v and 'CORRECTION' in v.upper(), '9999', 'Correction - needs banking match'),
    
    # Insurance & Mortgage → Keep as-is or map to proper GL
    (lambda v: v and 'MORTGAGE' in v.upper(), '3200', 'Loan Payments'),
    (lambda v: v and 'CAPITAL ONE' in v.upper(), '3200', 'Loan Payments'),
    (lambda v: v and 'MCAP' in v.upper(), '3200', 'Loan Payments'),
]

def categorize_vendor(vendor_name):
    """Apply rules to vendor name, return (new_gl, description) or (None, None)."""
    for condition, gl_code, desc in RULES:
        try:
            if condition(vendor_name):
                return gl_code, desc
        except:
            pass
    return None, None

def main():
    print("=" * 100)
    print("AUTO-CATEGORIZE GL 9999 ENTRIES")
    print("=" * 100)
    print(f"Dry-run: {DRY_RUN}\n")
    
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    # Get all GL 9999 entries
    cur.execute("""
        SELECT receipt_id, vendor_name, gl_account_code, gross_amount
        FROM receipts
        WHERE gl_account_code = '9999'
        ORDER BY vendor_name
    """)
    
    entries = cur.fetchall()
    categorized = {}
    remaining = []
    
    for receipt_id, vendor_name, current_gl, amount in entries:
        new_gl, desc = categorize_vendor(vendor_name)
        if new_gl:
            if new_gl not in categorized:
                categorized[new_gl] = []
            categorized[new_gl].append((receipt_id, vendor_name, desc, amount))
        else:
            remaining.append((receipt_id, vendor_name, amount))
    
    # Show summary
    total_categorized = sum(len(v) for v in categorized.values())
    print(f"📊 Summary:")
    print(f"  Total GL 9999: {len(entries)}")
    print(f"  Auto-categorized: {total_categorized}")
    print(f"  Remaining: {len(remaining)}")
    
    print(f"\n📋 Categorization breakdown:")
    for gl_code in sorted(categorized.keys()):
        items = categorized[gl_code]
        total_amt = sum(a[3] for a in items)
        # Get description from first item
        desc = items[0][2] if items else ''
        print(f"  GL {gl_code} ({desc}): {len(items):4d} items | ${float(total_amt):>12.2f}")
    
    if not DRY_RUN:
        # Backup before applying
        backup_data = {
            "timestamp": datetime.now().isoformat(),
            "total": len(entries),
            "categorized": total_categorized,
            "rules_applied": list(categorized.keys())
        }
        backup_file = f"gl_9999_auto_categorization_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(backup_file, 'w') as f:
            json.dump(backup_data, f, indent=2)
        print(f"\n✅ Backup: {backup_file}")
        
        # Apply updates
        updated = 0
        for gl_code, items in categorized.items():
            receipt_ids = [item[0] for item in items]
            cur.execute(
                "UPDATE receipts SET gl_account_code = %s WHERE receipt_id = ANY(%s)",
                (gl_code, receipt_ids)
            )
            updated += cur.rowcount
        
        conn.commit()
        print(f"✅ Updated {updated} receipts")
        
        # Show remaining for manual review
        if remaining:
            print(f"\n⚠️  Remaining GL 9999 entries ({len(remaining)}) - MANUAL REVIEW NEEDED:")
            print(f"{'Count':<6} {'Vendor':<40} {'Sample Amount':<12}")
            print("-" * 60)
            
            vendor_summary = {}
            for _, vendor, amt in remaining:
                if vendor not in vendor_summary:
                    vendor_summary[vendor] = (0, amt)
                count, _ = vendor_summary[vendor]
                vendor_summary[vendor] = (count + 1, amt)
            
            for vendor in sorted(vendor_summary.keys(), key=lambda x: vendor_summary[x][0], reverse=True)[:20]:
                count, amt = vendor_summary[vendor]
                print(f"{count:<6} {(vendor if vendor else '(NULL)')[:38]:<40} ${float(amt):>10.2f}")
            
            if len(vendor_summary) > 20:
                print(f"\n... and {len(vendor_summary) - 20} more vendors")
    else:
        print("\nDry-run mode: no changes applied.")
    
    cur.close(); conn.close()

if __name__ == '__main__':
    main()
