"""
Migrate missing payment records from payments table to charter_payments table.

PROBLEM IDENTIFIED:
- charter_payments table is incomplete (only 24,237 rows)
- payments table has 53,152 rows with many charter-linked entries
- Many charters have paid_amount but NO charter_payments records
- Example: Charter 16187 has $3,852 paid but 0 charter_payments entries (has 9 in payments table)

SOLUTION:
- Create charter_payments entries from payments table where:
  1. Payment is linked to a charter (charter_id OR reserve_number)
  2. Payment amount > 0 (exclude refunds and $0 metadata)
  3. No existing charter_payments entry for that payment_id

SAFETY:
- Dry-run mode by default
- Only inserts missing records (no updates/deletes)
- Preserves all existing charter_payments data
- Uses payment_id as deduplication key

Usage:
  python scripts/migrate_payments_to_charter_payments.py                # Dry run
  python scripts/migrate_payments_to_charter_payments.py --write        # Apply
"""
import argparse
import psycopg2
from datetime import datetime


def get_conn():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REDACTED***",
    )


def columns(cur, table):
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s
        """,
        (table,),
    )
    return {r[0] for r in cur.fetchall()}


def fmt_money(v):
    return f"${float(v or 0):,.2f}"


def get_migration_candidates(cur, amount_field, payment_method_field):
    """Get payments that should be in charter_payments but aren't"""
    
    cur.execute(f"""
    SELECT 
      p.payment_id,
      COALESCE(p.charter_id::text, 
               (SELECT charter_id::text FROM charters WHERE reserve_number = p.reserve_number LIMIT 1)) AS charter_id,
      COALESCE(p.{amount_field}, 0) AS amount,
      p.payment_date,
      p.{payment_method_field} AS payment_method,
      p.payment_key,
      p.reserve_number,
      (SELECT cl.client_name FROM clients cl WHERE cl.client_id = c.client_id LIMIT 1) AS client_name,
      c.charter_date
    FROM payments p
    LEFT JOIN charters c ON (p.charter_id = c.charter_id OR p.reserve_number = c.reserve_number)
    WHERE (p.charter_id IS NOT NULL OR p.reserve_number IS NOT NULL)
      AND p.{amount_field} > 0
      AND NOT EXISTS (
        SELECT 1 FROM charter_payments cp 
        WHERE cp.payment_id = p.payment_id
      )
    ORDER BY p.payment_date
    """)
    
    return cur.fetchall()


def main():
    parser = argparse.ArgumentParser(description="Migrate payments to charter_payments table")
    parser.add_argument("--write", action="store_true", help="Apply changes (default is dry-run)")
    parser.add_argument("--sample", type=int, default=10, help="Number of sample records to show")
    args = parser.parse_args()
    
    print("=" * 100)
    print("PAYMENTS → CHARTER_PAYMENTS MIGRATION")
    print("=" * 100)
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Schema discovery
    pay_cols = columns(cur, "payments")
    amount_field = "payment_amount" if "payment_amount" in pay_cols else "amount"
    payment_method_field = "payment_method" if "payment_method" in pay_cols else "pymt_type"
    
    print(f"\nUsing: {amount_field} for amount, {payment_method_field} for payment method")
    
    # Get current state
    print("\nCURRENT STATE:")
    print("-" * 100)
    
    cur.execute("SELECT COUNT(*), SUM(amount) FROM charter_payments")
    cp_count, cp_sum = cur.fetchone()
    print(f"charter_payments: {cp_count:,} rows, {fmt_money(cp_sum)} total")
    
    cur.execute(f"""
    SELECT COUNT(*), SUM({amount_field}) 
    FROM payments 
    WHERE (charter_id IS NOT NULL OR reserve_number IS NOT NULL)
      AND {amount_field} > 0
    """)
    p_count, p_sum = cur.fetchone()
    print(f"payments (charter-linked, positive): {p_count:,} rows, {fmt_money(p_sum)} total")
    
    # Get candidates
    print("\nFINDING MIGRATION CANDIDATES:")
    print("-" * 100)
    
    candidates = get_migration_candidates(cur, amount_field, payment_method_field)
    
    if not candidates:
        print("✓ No migration needed - all charter-linked payments already in charter_payments!")
        cur.close()
        conn.close()
        return
    
    total_amount = sum(float(row[2]) for row in candidates)
    
    print(f"\nFound {len(candidates):,} payments to migrate")
    print(f"Total amount: {fmt_money(total_amount)}")
    
    # Show samples
    print(f"\nSample {args.sample} records:")
    print(f"{'PayID':<8} {'Charter':<8} {'Amount':>12} {'Date':<12} {'Method':<15} {'Reserve':<8}")
    print("-" * 75)
    
    for i, row in enumerate(candidates[:args.sample]):
        pid, cid, amt, pdate, method, pkey, res, client, cdate = row
        print(f"{pid:<8} {str(cid or '')[:8]:<8} {fmt_money(amt):>12} {str(pdate):<12} {str(method or 'NULL')[:15]:<15} {str(res or ''):<8}")
    
    if len(candidates) > args.sample:
        print(f"... and {len(candidates) - args.sample:,} more")
    
    # Check for specific problem charters
    print("\nCHECKING PROBLEM CHARTERS:")
    print("-" * 100)
    
    problem_charters = [16187, 17555, 16948]  # From investigation
    for charter_id in problem_charters:
        matching = [c for c in candidates if c[1] and int(c[1]) == charter_id]
        if matching:
            amt_sum = sum(float(m[2]) for m in matching)
            print(f"Charter {charter_id}: {len(matching)} payments found totaling {fmt_money(amt_sum)}")
    
    if args.write:
        print("\n" + "!" * 100)
        print("APPLYING MIGRATION")
        print("!" * 100)
        
        print("\nInserting records into charter_payments...")
        
        inserted = 0
        for pid, cid, amt, pdate, method, pkey, res, client, cdate in candidates:
            try:
                cur.execute("""
                INSERT INTO charter_payments 
                  (payment_id, charter_id, client_name, charter_date, amount, payment_date, 
                   payment_method, payment_key, source, imported_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """, (pid, cid, client, cdate, amt, pdate, method, pkey, 'payments_table_migration'))
                inserted += 1
                
                if inserted % 1000 == 0:
                    print(f"  Inserted {inserted:,} records...")
                    conn.commit()
            except Exception as e:
                print(f"  [WARN]  Error inserting payment_id {pid}: {e}")
                conn.rollback()
        
        conn.commit()
        
        print(f"\n✓ Inserted {inserted:,} records into charter_payments")
        
        # Verify results
        print("\nVERIFYING RESULTS:")
        print("-" * 100)
        
        cur.execute("SELECT COUNT(*), SUM(amount) FROM charter_payments")
        new_cp_count, new_cp_sum = cur.fetchone()
        
        print(f"charter_payments now: {new_cp_count:,} rows (was {cp_count:,})")
        print(f"Total amount: {fmt_money(new_cp_sum)} (was {fmt_money(cp_sum)})")
        print(f"Added: {new_cp_count - cp_count:,} rows, {fmt_money(float(new_cp_sum) - float(cp_sum))}")
        
        # Check problem charters again
        print("\nPROBLEM CHARTERS NOW HAVE:")
        for charter_id in problem_charters:
            cur.execute("""
            SELECT COUNT(*), SUM(amount)
            FROM charter_payments
            WHERE charter_id = %s
            """, (str(charter_id),))
            cnt, amt = cur.fetchone()
            if cnt and cnt > 0:
                print(f"  Charter {charter_id}: {cnt} payments, {fmt_money(amt)} total")
        
        print("\n✓ Migration complete!")
        print("  Next step: Run sync_charter_paid_amounts.py to update charter.paid_amount")
        
    else:
        print("\n" + "=" * 100)
        print("DRY RUN MODE - No changes made")
        print("=" * 100)
        print("Run with --write flag to apply these changes")
        print("Example: python scripts/migrate_payments_to_charter_payments.py --write")
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 100)
    print("MIGRATION ANALYSIS COMPLETE")
    print("=" * 100)


if __name__ == "__main__":
    main()
