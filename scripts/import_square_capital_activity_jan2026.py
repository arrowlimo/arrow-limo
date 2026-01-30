#!/usr/bin/env python3
"""
Import Square Capital Activity CSV (January 2026) for GL coding.
Updates square_capital_activity table with latest payment records.
"""

import os
import csv
import hashlib
import psycopg2
from datetime import datetime
from decimal import Decimal

# Database connection
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REDACTED***")

CSV_FILE = r"l:\limo\Square reports\P-55QV76-Square_Capital_Activity_20260129.csv"


def parse_date(date_str):
    """Parse Square date format: YY-MM-DD to date object."""
    # Format: "25-09-29" -> 2025-09-29
    parts = date_str.split('-')
    year = int('20' + parts[0])
    month = int(parts[1])
    day = int(parts[2])
    return datetime(year, month, day).date()


def parse_amount(amount_str):
    """Parse Square amount format: $1,234.56 to Decimal."""
    # Remove $ and commas
    clean = amount_str.replace('$', '').replace(',', '')
    return Decimal(clean)


def generate_hash(date, desc, amount):
    """Generate deterministic hash for deduplication."""
    key = f"{date}|{desc}|{amount}"
    return hashlib.md5(key.encode()).hexdigest()


def import_csv(conn, dry_run=True):
    """Import Square Capital Activity CSV."""
    cur = conn.cursor()
    
    try:
        # Read CSV
        print(f"\n📂 Reading: {CSV_FILE}")
        records = []
        
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                date = parse_date(row['Date'])
                desc = row['Description']
                amount = parse_amount(row['Amount'])
                row_hash = generate_hash(date, desc, amount)
                
                records.append({
                    'date': date,
                    'desc': desc,
                    'amount': amount,
                    'hash': row_hash
                })
        
        print(f"✓ Loaded {len(records)} records from CSV")
        print(f"  Date range: {min(r['date'] for r in records)} to {max(r['date'] for r in records)}")
        print(f"  Total amount: ${sum(r['amount'] for r in records):,.2f}")
        
        # Check for duplicates
        cur.execute("SELECT COUNT(*) FROM square_capital_activity")
        existing_count = cur.fetchone()[0]
        print(f"\n💾 Current database: {existing_count} records")
        
        # Insert new records (idempotent)
        inserted = 0
        skipped = 0
        
        for rec in records:
            cur.execute("""
                SELECT id FROM square_capital_activity
                WHERE row_hash = %s
            """, (rec['hash'],))
            
            if cur.fetchone():
                skipped += 1
                continue
            
            if not dry_run:
                cur.execute("""
                    INSERT INTO square_capital_activity (
                        activity_date, description, amount,
                        source_file, row_hash
                    )
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    rec['date'],
                    rec['desc'],
                    rec['amount'],
                    os.path.basename(CSV_FILE),
                    rec['hash']
                ))
                inserted += 1
            else:
                inserted += 1
        
        if not dry_run:
            conn.commit()
        
        print(f"\n{'[DRY RUN] ' if dry_run else ''}Results:")
        print(f"  New records: {inserted}")
        print(f"  Duplicates skipped: {skipped}")
        print(f"  Total after import: {existing_count + inserted}")
        
        # Show breakdown by type
        cur.execute("""
            SELECT 
                CASE 
                    WHEN description ILIKE '%loan deposit%' THEN 'Loan Deposits'
                    WHEN description ILIKE '%payment from%loan%' THEN 'Loan Payoffs'
                    WHEN description ILIKE '%automatic payment%' THEN 'Automatic Payments'
                    WHEN description ILIKE '%refund%' THEN 'Refunds'
                    ELSE 'Other'
                END as type,
                COUNT(*) as count,
                SUM(amount) as total
            FROM square_capital_activity
            GROUP BY type
            ORDER BY total DESC
        """)
        
        print(f"\n📊 Activity Breakdown:")
        for row in cur.fetchall():
            print(f"  {row[0]}: {row[1]} records, ${row[2]:,.2f}")
        
        return inserted, skipped
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        cur.close()


def update_loan_payments(conn, dry_run=True):
    """Update square_loan_payments from activity records."""
    cur = conn.cursor()
    
    try:
        print(f"\n{'[DRY RUN] ' if dry_run else ''}Updating loan payment records...")
        
        # Get all loans
        cur.execute("""
            SELECT loan_id, square_loan_id, received_date, loan_amount
            FROM square_capital_loans
            ORDER BY received_date
        """)
        loans = cur.fetchall()
        
        for loan_id, sq_loan_id, rec_date, loan_amt in loans:
            # Find payments for this loan (negative amounts = payments out)
            cur.execute("""
                SELECT activity_date, description, amount, id
                FROM square_capital_activity
                WHERE description ILIKE '%%automatic payment%%'
                AND activity_date >= %s
                ORDER BY activity_date
            """, (rec_date,))
            
            payments = cur.fetchall()
            
            # Check which are already tracked
            cur.execute("""
                SELECT activity_id FROM square_loan_payments
                WHERE loan_id = %s
            """, (loan_id,))
            tracked_ids = {r[0] for r in cur.fetchall()}
            
            new_payments = 0
            for pay_date, pay_desc, pay_amt, activity_id in payments:
                if activity_id in tracked_ids:
                    continue
                
                if not dry_run:
                    cur.execute("""
                        INSERT INTO square_loan_payments (
                            loan_id, activity_id, payment_date,
                            payment_amount, description
                        )
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        loan_id,
                        activity_id,
                        pay_date,
                        abs(pay_amt),
                        pay_desc
                    ))
                new_payments += 1
            
            if new_payments > 0:
                print(f"  Loan {sq_loan_id}: +{new_payments} new payment records")
        
        if not dry_run:
            conn.commit()
            print("✓ Loan payments updated")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error updating payments: {e}")
        raise
    finally:
        cur.close()


def main():
    import sys
    dry_run = '--write' not in sys.argv
    
    print("=" * 70)
    print("SQUARE CAPITAL ACTIVITY IMPORT (January 2026)")
    print("=" * 70)
    
    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
        print("   Use --write to apply changes\n")
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    try:
        # Import CSV
        inserted, skipped = import_csv(conn, dry_run)
        
        print("\n" + "=" * 70)
        print("✓ IMPORT COMPLETE")
        print("=" * 70)
        
        if dry_run and inserted > 0:
            print("\n💡 Run with --write to save changes to database")
        elif inserted == 0:
            print("\n✅ All records already imported - database is up to date")
        
    finally:
        conn.close()


if __name__ == "__main__":
    main()
