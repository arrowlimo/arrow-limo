#!/usr/bin/env python3
"""
Link ALL refunds to charter reservations - 100% linkage required.

Strategy:
1. Direct reserve_number match (already done)
2. Match via payment_id (if refund came from payments table)
3. Match via square_payment_id 
4. Fuzzy match on customer name + date proximity + amount similarity
5. Manual review list for remaining unlinked
"""
import psycopg2
import argparse
from datetime import timedelta

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        dbname='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def link_via_payment_id(cur, dry_run=True):
    """Link refunds to charters via payment_id foreign key"""
    print("\n" + "="*80)
    print("STEP 1: Link via payment_id")
    print("="*80)
    
    # Find refunds from payments table that have payment_id but no charter_id
    cur.execute("""
        SELECT r.id, r.payment_id, p.charter_id, p.reserve_number, r.amount
        FROM charter_refunds r
        JOIN payments p ON r.payment_id = p.payment_id
        WHERE r.charter_id IS NULL
        AND r.payment_id IS NOT NULL
        AND p.charter_id IS NOT NULL
    """)
    
    matches = cur.fetchall()
    print(f"Found {len(matches)} refunds that can be linked via payment_id")
    
    if matches:
        print("\nSample matches:")
        for i, (refund_id, payment_id, charter_id, reserve, amount) in enumerate(matches[:10]):
            print(f"  Refund #{refund_id}: ${amount:,.2f} -> Charter {reserve} (payment #{payment_id})")
        
        if not dry_run:
            for refund_id, payment_id, charter_id, reserve, amount in matches:
                cur.execute("""
                    UPDATE charter_refunds 
                    SET charter_id = %s, reserve_number = %s
                    WHERE id = %s
                """, (charter_id, reserve, refund_id))
            print(f"\n[OK] Linked {len(matches)} refunds via payment_id")
        else:
            print(f"\n[DRY RUN] Would link {len(matches)} refunds")
    
    return len(matches)

def link_via_square_payment_id(cur, dry_run=True):
    """Link refunds to charters via square_payment_id"""
    print("\n" + "="*80)
    print("STEP 2: Link via square_payment_id")
    print("="*80)
    
    cur.execute("""
        SELECT r.id, r.square_payment_id, p.charter_id, p.reserve_number, r.amount
        FROM charter_refunds r
        JOIN payments p ON r.square_payment_id = p.square_payment_id
        WHERE r.charter_id IS NULL
        AND r.square_payment_id IS NOT NULL
        AND r.square_payment_id != ''
        AND p.charter_id IS NOT NULL
    """)
    
    matches = cur.fetchall()
    print(f"Found {len(matches)} refunds that can be linked via square_payment_id")
    
    if matches:
        print("\nSample matches:")
        for i, (refund_id, sq_id, charter_id, reserve, amount) in enumerate(matches[:10]):
            print(f"  Refund #{refund_id}: ${amount:,.2f} -> Charter {reserve} (Square ID: {sq_id[:20]}...)")
        
        if not dry_run:
            for refund_id, sq_id, charter_id, reserve, amount in matches:
                cur.execute("""
                    UPDATE charter_refunds 
                    SET charter_id = %s, reserve_number = %s
                    WHERE id = %s
                """, (charter_id, reserve, refund_id))
            print(f"\n[OK] Linked {len(matches)} refunds via square_payment_id")
        else:
            print(f"\n[DRY RUN] Would link {len(matches)} refunds")
    
    return len(matches)

def link_via_customer_date_amount(cur, dry_run=True):
    """Fuzzy match on customer name + date proximity + amount similarity"""
    print("\n" + "="*80)
    print("STEP 3: Link via customer name + date + amount fuzzy match")
    print("="*80)
    
    # Find refunds with customer names
    cur.execute("""
        SELECT r.id, r.customer, r.refund_date, r.amount, r.description
        FROM charter_refunds r
        WHERE r.charter_id IS NULL
        AND r.customer IS NOT NULL
        AND r.customer != ''
        AND r.refund_date IS NOT NULL
    """)
    
    unlinked = cur.fetchall()
    print(f"Found {len(unlinked)} unlinked refunds with customer info")
    
    matches = []
    for refund_id, customer, refund_date, amount, description in unlinked:
        # Look for charters with similar customer name within ±30 days and similar amount
        cur.execute("""
            SELECT c.charter_id, c.reserve_number, c.charter_date, cl.client_name,
                   c.rate, c.balance, c.deposit
            FROM charters c
            LEFT JOIN clients cl ON c.client_id = cl.client_id
            WHERE (
                LOWER(cl.client_name) LIKE LOWER(%s)
                OR LOWER(%s) LIKE LOWER('%' || cl.client_name || '%')
            )
            AND c.charter_date BETWEEN %s AND %s
            AND (
                ABS(c.rate - %s) < 100
                OR ABS(c.deposit - %s) < 100
                OR ABS(c.balance - %s) < 100
            )
            LIMIT 5
        """, (
            f'%{customer}%',
            customer,
            refund_date - timedelta(days=30),
            refund_date + timedelta(days=30),
            amount,
            amount,
            amount
        ))
        
        candidates = cur.fetchall()
        if len(candidates) == 1:
            # Single match - high confidence
            charter_id, reserve, charter_date, client_name, rate, balance, deposit = candidates[0]
            matches.append((refund_id, charter_id, reserve, customer, client_name, amount, refund_date, charter_date))
    
    print(f"Found {len(matches)} high-confidence fuzzy matches (single candidate)")
    
    if matches:
        print("\nSample matches:")
        for i, (refund_id, charter_id, reserve, refund_cust, charter_cust, amount, refund_date, charter_date) in enumerate(matches[:10]):
            print(f"  Refund #{refund_id}: ${amount:,.2f} '{refund_cust}' on {refund_date}")
            print(f"    -> Charter {reserve}: '{charter_cust}' on {charter_date}")
        
        if not dry_run:
            for refund_id, charter_id, reserve, _, _, _, _, _ in matches:
                cur.execute("""
                    UPDATE charter_refunds 
                    SET charter_id = %s, reserve_number = %s
                    WHERE id = %s
                """, (charter_id, reserve, refund_id))
            print(f"\n[OK] Linked {len(matches)} refunds via fuzzy matching")
        else:
            print(f"\n[DRY RUN] Would link {len(matches)} refunds")
    
    return len(matches)

def analyze_remaining_unlinked(cur):
    """Analyze what's left unlinked and categorize"""
    print("\n" + "="*80)
    print("ANALYSIS: Remaining Unlinked Refunds")
    print("="*80)
    
    # Count remaining
    cur.execute("SELECT COUNT(*), SUM(amount) FROM charter_refunds WHERE charter_id IS NULL")
    count, total = cur.fetchone()
    
    print(f"\nRemaining unlinked: {count:,} refunds = ${total:,.2f}")
    
    if count == 0:
        print("\n🎉 SUCCESS! All refunds are now linked to charters!")
        return
    
    # Categorize by description patterns
    print("\n📊 Breakdown by category:")
    
    categories = [
        ("Workers Comp / Business Expenses", "WCB|WORKERS COMP|PAYROLL|INSURANCE|BILL PAYMENT"),
        ("QuickBooks Imports (2012)", "QBO Import|Debit Memo|Cheque"),
        ("Square Refunds (no reserve #)", "Square refund|Accidental charge"),
        ("No customer info", ""),  # Will check NULL customer
    ]
    
    for category_name, pattern in categories:
        if category_name == "No customer info":
            cur.execute("""
                SELECT COUNT(*), SUM(amount)
                FROM charter_refunds
                WHERE charter_id IS NULL
                AND (customer IS NULL OR customer = '')
            """)
        else:
            cur.execute("""
                SELECT COUNT(*), SUM(amount)
                FROM charter_refunds
                WHERE charter_id IS NULL
                AND description ~* %s
            """, (pattern,))
        
        cat_count, cat_amount = cur.fetchone()
        if cat_count and cat_count > 0:
            pct = (cat_count/count*100) if count > 0 else 0
            print(f"  {category_name}: {cat_count:,} ({pct:.1f}%) = ${cat_amount:,.2f}")
    
    # Show top 20 unlinked for manual review
    print("\n📋 Top 20 unlinked refunds for manual review:")
    cur.execute("""
        SELECT id, refund_date, amount, customer, description, source_file
        FROM charter_refunds
        WHERE charter_id IS NULL
        ORDER BY amount DESC
        LIMIT 20
    """)
    
    print("\nID    | Date       | Amount      | Customer                    | Description")
    print("-" * 100)
    for row in cur.fetchall():
        refund_id, date, amount, customer, desc, source = row
        cust_str = (customer or "")[:25].ljust(25)
        desc_str = (desc or "")[:40]
        print(f"{refund_id:5} | {date} | ${amount:>10,.2f} | {cust_str} | {desc_str}")

def main():
    parser = argparse.ArgumentParser(description='Link all refunds to charter reservations')
    parser.add_argument('--write', action='store_true', help='Apply changes (default is dry-run)')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("="*80)
    print("LINKING ALL REFUNDS TO CHARTER RESERVATIONS")
    print("="*80)
    
    if args.write:
        print("\n[WARN]  WRITE MODE: Changes will be applied to database")
    else:
        print("\n🔍 DRY RUN MODE: No changes will be made (use --write to apply)")
    
    # Check starting status
    cur.execute("SELECT COUNT(*), SUM(amount) FROM charter_refunds WHERE charter_id IS NULL")
    start_count, start_amount = cur.fetchone()
    print(f"\nStarting with {start_count:,} unlinked refunds (${start_amount:,.2f})")
    
    # Step 1: Link via payment_id
    linked_1 = link_via_payment_id(cur, dry_run=not args.write)
    
    # Step 2: Link via square_payment_id
    linked_2 = link_via_square_payment_id(cur, dry_run=not args.write)
    
    # Step 3: Fuzzy matching
    linked_3 = link_via_customer_date_amount(cur, dry_run=not args.write)
    
    total_linked = linked_1 + linked_2 + linked_3
    
    if args.write and total_linked > 0:
        conn.commit()
        print(f"\n[OK] COMMITTED: Linked {total_linked} refunds to charters")
    
    # Analyze what's left
    analyze_remaining_unlinked(cur)
    
    # Final status
    cur.execute("SELECT COUNT(*), SUM(amount) FROM charter_refunds WHERE charter_id IS NULL")
    end_count, end_amount = cur.fetchone()
    
    cur.execute("SELECT COUNT(*), SUM(amount) FROM charter_refunds WHERE charter_id IS NOT NULL")
    linked_count, linked_amount = cur.fetchone()
    
    cur.execute("SELECT COUNT(*), SUM(amount) FROM charter_refunds")
    total_count, total_amount = cur.fetchone()
    
    print("\n" + "="*80)
    print("FINAL RESULTS")
    print("="*80)
    print(f"Total Refunds: {total_count:,} = ${total_amount:,.2f}")
    print(f"[OK] Linked: {linked_count:,} ({linked_count/total_count*100:.1f}%) = ${linked_amount:,.2f} ({linked_amount/total_amount*100:.1f}%)")
    print(f"[FAIL] Unlinked: {end_count:,} ({end_count/total_count*100:.1f}%) = ${end_amount:,.2f} ({end_amount/total_amount*100:.1f}%)")
    
    if args.write:
        print(f"\n[OK] Improved linkage by {total_linked} refunds in this run")
    else:
        print(f"\n[DRY RUN] Would improve linkage by {total_linked} refunds")
        print("Run with --write to apply changes")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
