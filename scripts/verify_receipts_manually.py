#!/usr/bin/env python3
"""
Manually verify receipts by ID (without editing)
Useful for bulk verification or marking receipts as verified after review.
"""
import psycopg2
import argparse

DB_CONFIG = {
    'host': 'localhost',
    'database': 'almsdata',
    'user': 'postgres',
    'password': '***REDACTED***'
}

def verify_receipts(receipt_ids, user='manual_verification', dry_run=True):
    """Verify one or more receipts by ID."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        # Check which receipts exist
        placeholders = ','.join(['%s'] * len(receipt_ids))
        cur.execute(f"""
            SELECT receipt_id, receipt_date, vendor_name, gross_amount, 
                   verified_by_edit
            FROM receipts
            WHERE receipt_id IN ({placeholders})
        """, receipt_ids)
        
        receipts = cur.fetchall()
        
        if not receipts:
            print("❌ No receipts found with the given IDs")
            return
        
        print(f"\n📋 Found {len(receipts)} receipts:")
        print("-" * 80)
        already_verified = []
        to_verify = []
        
        for rid, rdate, vendor, amount, verified in receipts:
            status = "✅ Already Verified" if verified else "⚠️  Unverified"
            print(f"  {rid:<8} {rdate} {(vendor or '')[:30]:<30} ${amount:>12,.2f} {status}")
            
            if verified:
                already_verified.append(rid)
            else:
                to_verify.append(rid)
        
        if not to_verify:
            print("\n✅ All selected receipts are already verified!")
            return
        
        print(f"\n📝 Will verify {len(to_verify)} receipts")
        if already_verified:
            print(f"   ({len(already_verified)} already verified, will be skipped)")
        
        if dry_run:
            print("\n🔒 DRY RUN - No changes made. Use --write to apply.")
            return
        
        # Verify the receipts
        placeholders = ','.join(['%s'] * len(to_verify))
        cur.execute(f"""
            UPDATE receipts
            SET verified_by_edit = TRUE,
                verified_at = NOW(),
                verified_by_user = %s
            WHERE receipt_id IN ({placeholders})
        """, [user] + to_verify)
        
        count = cur.rowcount
        conn.commit()
        
        print(f"\n✅ Verified {count} receipts successfully!")
        
        # Show updated status
        cur.execute("SELECT * FROM receipt_verification_audit_summary")
        row = cur.fetchone()
        if row:
            total, verified, unverified, pct, first, last, users = row
            print(f"\n📊 Updated Summary:")
            print(f"   Total: {total:,}")
            print(f"   Verified: {verified:,} ({pct}%)")
            print(f"   Unverified: {unverified:,}")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()

def verify_by_criteria(vendor=None, date_from=None, date_to=None, 
                       category=None, min_amount=None, max_amount=None,
                       user='bulk_verification', dry_run=True):
    """Verify receipts matching criteria."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        # Build query
        conditions = ["(verified_by_edit = FALSE OR verified_by_edit IS NULL)"]
        params = []
        
        if vendor:
            conditions.append("vendor_name ILIKE %s")
            params.append(f"%{vendor}%")
        
        if date_from:
            conditions.append("receipt_date >= %s")
            params.append(date_from)
        
        if date_to:
            conditions.append("receipt_date <= %s")
            params.append(date_to)
        
        if category:
            conditions.append("category = %s")
            params.append(category)
        
        if min_amount:
            conditions.append("gross_amount >= %s")
            params.append(min_amount)
        
        if max_amount:
            conditions.append("gross_amount <= %s")
            params.append(max_amount)
        
        where_clause = " AND ".join(conditions)
        
        # Find matching receipts
        cur.execute(f"""
            SELECT receipt_id, receipt_date, vendor_name, gross_amount, category
            FROM receipts
            WHERE {where_clause}
            ORDER BY receipt_date, receipt_id
        """, params)
        
        receipts = cur.fetchall()
        
        if not receipts:
            print("❌ No unverified receipts found matching criteria")
            return
        
        print(f"\n📋 Found {len(receipts)} unverified receipts matching criteria:")
        print("-" * 100)
        print(f"{'ID':<8} {'Date':<12} {'Vendor':<30} {'Amount':>12} {'Category':<20}")
        print("-" * 100)
        
        total_amount = 0
        for rid, rdate, vendor, amount, cat in receipts[:50]:  # Show first 50
            print(f"{rid:<8} {rdate} {(vendor or '')[:28]:<30} ${amount:>11,.2f} {(cat or '')[:18]:<20}")
            total_amount += amount or 0
        
        if len(receipts) > 50:
            print(f"... and {len(receipts) - 50} more")
        
        print(f"\nTotal amount: ${total_amount:,.2f}")
        
        if dry_run:
            print("\n🔒 DRY RUN - No changes made. Use --write to apply.")
            return
        
        # Verify all matching receipts
        receipt_ids = [r[0] for r in receipts]
        placeholders = ','.join(['%s'] * len(receipt_ids))
        
        cur.execute(f"""
            UPDATE receipts
            SET verified_by_edit = TRUE,
                verified_at = NOW(),
                verified_by_user = %s
            WHERE receipt_id IN ({placeholders})
        """, [user] + receipt_ids)
        
        count = cur.rowcount
        conn.commit()
        
        print(f"\n✅ Verified {count} receipts successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()

def main():
    parser = argparse.ArgumentParser(description='Manually verify receipts')
    parser.add_argument('--ids', nargs='+', type=int, help='Receipt IDs to verify')
    parser.add_argument('--vendor', help='Verify receipts matching vendor name')
    parser.add_argument('--date-from', help='Verify receipts from date (YYYY-MM-DD)')
    parser.add_argument('--date-to', help='Verify receipts to date (YYYY-MM-DD)')
    parser.add_argument('--category', help='Verify receipts in category')
    parser.add_argument('--min-amount', type=float, help='Verify receipts >= amount')
    parser.add_argument('--max-amount', type=float, help='Verify receipts <= amount')
    parser.add_argument('--user', default='manual_verification', help='Username to record')
    parser.add_argument('--write', action='store_true', help='Apply changes (default is dry-run)')
    
    args = parser.parse_args()
    
    if args.ids:
        print(f"🔍 Verifying receipts by ID: {args.ids}")
        verify_receipts(args.ids, user=args.user, dry_run=not args.write)
    elif any([args.vendor, args.date_from, args.date_to, args.category, 
              args.min_amount, args.max_amount]):
        print("🔍 Verifying receipts by criteria:")
        if args.vendor:
            print(f"   Vendor: {args.vendor}")
        if args.date_from:
            print(f"   From: {args.date_from}")
        if args.date_to:
            print(f"   To: {args.date_to}")
        if args.category:
            print(f"   Category: {args.category}")
        if args.min_amount:
            print(f"   Min Amount: ${args.min_amount:,.2f}")
        if args.max_amount:
            print(f"   Max Amount: ${args.max_amount:,.2f}")
        
        verify_by_criteria(
            vendor=args.vendor,
            date_from=args.date_from,
            date_to=args.date_to,
            category=args.category,
            min_amount=args.min_amount,
            max_amount=args.max_amount,
            user=args.user,
            dry_run=not args.write
        )
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
