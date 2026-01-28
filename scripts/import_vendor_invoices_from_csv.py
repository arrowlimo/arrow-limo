#!/usr/bin/env python3
"""
Import vendor invoices from CSV.
CSV format: canonical_vendor,invoice_number,invoice_date,amount,description
"""
import os
import sys
import csv
import argparse
from datetime import datetime
from decimal import Decimal
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")


def parse_date(s: str):
    """Parse date from common formats."""
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {s}")


def get_or_create_account(cur, canonical_vendor: str):
    """Get existing account or create if missing."""
    cur.execute(
        "SELECT account_id FROM vendor_accounts WHERE UPPER(canonical_vendor) = UPPER(%s)",
        (canonical_vendor,)
    )
    row = cur.fetchone()
    if row:
        return row[0]
    
    # Create new account
    cur.execute(
        """
        INSERT INTO vendor_accounts (canonical_vendor, display_name, created_at)
        VALUES (%s, %s, NOW())
        RETURNING account_id
        """,
        (canonical_vendor.upper(), canonical_vendor)
    )
    return cur.fetchone()[0]


def import_invoices(csv_path: str, dry_run: bool = True):
    """Import invoices from CSV."""
    conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    conn.autocommit = False
    cur = conn.cursor()
    
    imported = 0
    skipped = 0
    errors = []
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            required = {'canonical_vendor', 'invoice_date', 'amount'}
            if not required.issubset(reader.fieldnames):
                raise ValueError(f"CSV must have columns: {required}")
            
            for i, row in enumerate(reader, 1):
                try:
                    vendor = row['canonical_vendor'].strip()
                    inv_date = parse_date(row['invoice_date'].strip())
                    amount = Decimal(row['amount'].strip())
                    inv_num = row.get('invoice_number', '').strip() or None
                    desc = row.get('description', '').strip() or None
                    
                    if amount <= 0:
                        skipped += 1
                        errors.append(f"Line {i}: Amount must be positive: {amount}")
                        continue
                    
                    account_id = get_or_create_account(cur, vendor)
                    
                    # Check for existing invoice with same external_ref
                    if inv_num:
                        cur.execute(
                            """
                            SELECT 1 FROM vendor_account_ledger 
                            WHERE account_id = %s AND external_ref = %s AND entry_type = 'INVOICE'
                            """,
                            (account_id, inv_num)
                        )
                        if cur.fetchone():
                            skipped += 1
                            errors.append(f"Line {i}: Duplicate invoice {inv_num} for {vendor}")
                            continue
                    
                    if dry_run:
                        print(f"[DRY-RUN] Would import: {vendor} | {inv_date} | ${amount} | {inv_num or 'N/A'}")
                    else:
                        cur.execute(
                            """
                            INSERT INTO vendor_account_ledger 
                            (account_id, entry_date, entry_type, amount, external_ref, notes)
                            VALUES (%s, %s, 'INVOICE', %s, %s, %s)
                            """,
                            (account_id, inv_date, amount, inv_num, desc)
                        )
                    imported += 1
                    
                except Exception as e:
                    skipped += 1
                    errors.append(f"Line {i}: {e}")
        
        if dry_run:
            print(f"\n[DRY-RUN] Would import {imported} invoices, skip {skipped}")
        else:
            # Recompute balances for affected accounts
            cur.execute("""
                SELECT DISTINCT account_id FROM vendor_account_ledger
                WHERE created_at >= NOW() - INTERVAL '1 minute'
            """)
            for (acc_id,) in cur.fetchall():
                cur.execute("""
                    SELECT ledger_id, amount FROM vendor_account_ledger
                    WHERE account_id = %s
                    ORDER BY entry_date, ledger_id
                """, (acc_id,))
                total = Decimal("0.00")
                for ledger_id, amt in cur.fetchall():
                    total += amt
                    cur.execute(
                        "UPDATE vendor_account_ledger SET balance_after = %s WHERE ledger_id = %s",
                        (total, ledger_id)
                    )
            
            conn.commit()
            print(f"✅ Imported {imported} invoices, skipped {skipped}")
        
        if errors:
            print(f"\n⚠️  Errors/Warnings ({len(errors)}):")
            for err in errors[:20]:
                print(f"   {err}")
            if len(errors) > 20:
                print(f"   ... and {len(errors) - 20} more")
    
    except Exception as e:
        conn.rollback()
        print(f"❌ Import failed: {e}")
        raise
    finally:
        cur.close()
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Import vendor invoices from CSV")
    parser.add_argument("csv_file", help="Path to CSV file")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default is dry-run)")
    args = parser.parse_args()
    
    if not os.path.exists(args.csv_file):
        print(f"❌ File not found: {args.csv_file}")
        sys.exit(1)
    
    dry_run = not args.apply
    if dry_run:
        print("🔍 DRY-RUN MODE (use --apply to commit changes)\n")
    
    import_invoices(args.csv_file, dry_run=dry_run)


if __name__ == "__main__":
    main()
