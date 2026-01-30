#!/usr/bin/env python3
"""
Merge LMS 2026 Data to ALMSDATA
Selective merge with validation and dry-run mode
Uses staging tables for comprehensive relationship preservation
"""
import psycopg2
from datetime import datetime
import argparse

PG_HOST = "localhost"
PG_DB = "almsdata"
PG_USER = "postgres"
PG_PASSWORD = "***REMOVED***"

def connect():
    return psycopg2.connect(host=PG_HOST, dbname=PG_DB, user=PG_USER, password=PG_PASSWORD)

def merge_missing_charters(dry_run=True):
    """Add charters that exist in LMS but not in almsdata"""
    conn = connect()
    cur = conn.cursor()
    
    print("\n" + "=" * 80)
    print("MERGE MISSING CHARTERS")
    print("=" * 80)
    
    # Find missing charters
    cur.execute("""
        SELECT 
            lms.reserve_no,
            lms.account_no,
            lms.pu_date,
            lms.pu_time,
            lms.client_name,
            lms.phone,
            lms.email,
            lms.pickup_address,
            lms.dropoff_address,
            lms.vehicle_code,
            lms.driver_code,
            lms.passenger_count,
            lms.rate,
            lms.deposit,
            lms.total,
            lms.balance,
            lms.status,
            lms.notes
        FROM lms2026_reserves lms
        WHERE NOT EXISTS (
            SELECT 1 FROM charters c WHERE c.reserve_number = lms.reserve_no
        )
        ORDER BY lms.pu_date DESC
    """)
    
    missing_charters = cur.fetchall()
    print(f"\nFound {len(missing_charters):,} charters in LMS not in almsdata")
    
    if len(missing_charters) == 0:
        print("✅ No missing charters to merge")
        conn.close()
        return 0
    
    # Show sample
    print("\nSample missing charters:")
    for row in missing_charters[:10]:
        print(f"  {row[0]} | {row[2]} | {row[4][:40]:40} | ${row[14]:,.2f}")
    
    if dry_run:
        print(f"\n🔍 DRY RUN: Would insert {len(missing_charters):,} charters")
        conn.close()
        return len(missing_charters)
    
    # Perform merge
    print(f"\n✍️  Inserting {len(missing_charters):,} missing charters...")
    inserted = 0
    errors = []
    
    for row in missing_charters:
        try:
            # Get client_id if exists
            cur.execute("SELECT client_id FROM clients WHERE account_number = %s LIMIT 1", (row[1],))
            client_row = cur.fetchone()
            client_id = client_row[0] if client_row else None
            
            cur.execute("""
                INSERT INTO charters (
                    reserve_number, account_number, charter_date, pickup_time,
                    client_display_name, phone, email, 
                    pickup_address, dropoff_address,
                    vehicle, driver, passenger_count,
                    rate, deposit, total_amount_due, balance, paid_amount,
                    status, notes, client_id, created_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP
                )
            """, (
                row[0], row[1], row[2], row[3], row[4], row[5], row[6],
                row[7], row[8], row[9], row[10], row[11],
                row[12], row[13], row[14], row[15], 
                (row[14] or 0) - (row[15] or 0),  # paid_amount = total - balance
                row[16], row[17], client_id
            ))
            inserted += 1
            
            if inserted % 100 == 0:
                print(f"  {inserted} inserted...", end='\r')
                
        except Exception as e:
            errors.append(f"Error inserting {row[0]}: {e}")
    
    conn.commit()
    print(f"\n✅ Inserted {inserted:,} charters")
    
    if errors:
        print(f"⚠️  {len(errors)} errors (first 5):")
        for err in errors[:5]:
            print(f"   {err}")
    
    conn.close()
    return inserted

def merge_missing_payments(dry_run=True):
    """Add payments that exist in LMS but not matched in almsdata"""
    conn = connect()
    cur = conn.cursor()
    
    print("\n" + "=" * 80)
    print("MERGE MISSING PAYMENTS")
    print("=" * 80)
    
    # Find unmatched payments (using reserve_number as business key)
    cur.execute("""
        SELECT 
            lms.reserve_no,
            lms.amount,
            lms.payment_date,
            lms.payment_method,
            lms.check_number,
            lms.notes,
            lms.payment_key
        FROM lms2026_payments lms
        WHERE lms.reserve_no IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM payments p 
            WHERE p.reserve_number = lms.reserve_no
              AND ABS(p.amount - lms.amount) < 0.02
              AND p.payment_date = lms.payment_date
          )
        ORDER BY lms.payment_date DESC
    """)
    
    missing_payments = cur.fetchall()
    total_amount = sum(row[1] for row in missing_payments if row[1])
    
    print(f"\nFound {len(missing_payments):,} payments in LMS not matched in almsdata")
    print(f"Total amount: ${total_amount:,.2f}")
    
    if len(missing_payments) == 0:
        print("✅ No missing payments to merge")
        conn.close()
        return 0
    
    # Show sample
    print("\nSample missing payments:")
    for row in missing_payments[:10]:
        print(f"  {row[0]} | {row[2]} | ${row[1]:,.2f} | {row[3]}")
    
    if dry_run:
        print(f"\n🔍 DRY RUN: Would insert {len(missing_payments):,} payments (${total_amount:,.2f})")
        conn.close()
        return len(missing_payments)
    
    # Perform merge
    print(f"\n✍️  Inserting {len(missing_payments):,} missing payments...")
    inserted = 0
    errors = []
    
    for row in missing_payments:
        try:
            # Get charter_id and client_id via reserve_number
            cur.execute("""
                SELECT charter_id, account_number, client_id 
                FROM charters 
                WHERE reserve_number = %s LIMIT 1
            """, (row[0],))
            charter_row = cur.fetchone()
            
            if not charter_row:
                errors.append(f"Charter {row[0]} not found - skipping payment")
                continue
            
            charter_id, account_no, client_id = charter_row
            
            # Normalize payment method
            payment_method = (row[3] or 'unknown').lower()
            if payment_method in ['check', 'cheque']:
                payment_method = 'check'
            elif payment_method in ['cc', 'visa', 'mastercard', 'amex']:
                payment_method = 'credit_card'
            elif payment_method in ['debit', 'dc']:
                payment_method = 'debit_card'
            elif payment_method in ['etransfer', 'e-transfer', 'emt']:
                payment_method = 'bank_transfer'
            
            cur.execute("""
                INSERT INTO payments (
                    reserve_number, charter_id, account_number, client_id,
                    amount, payment_date, payment_method,
                    check_number, notes, payment_key, created_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP
                )
            """, (
                row[0], charter_id, account_no, client_id,
                row[1], row[2], payment_method,
                row[4], row[5], row[6]
            ))
            inserted += 1
            
            if inserted % 100 == 0:
                print(f"  {inserted} inserted...", end='\r')
                
        except Exception as e:
            errors.append(f"Error inserting payment for {row[0]}: {e}")
    
    conn.commit()
    print(f"\n✅ Inserted {inserted:,} payments (${sum(row[1] for row in missing_payments[:inserted]):,.2f})")
    
    if errors:
        print(f"⚠️  {len(errors)} errors (first 5):")
        for err in errors[:5]:
            print(f"   {err}")
    
    # Recalculate balances for affected charters
    print("\nRecalculating charter balances...")
    cur.execute("""
        UPDATE charters c
        SET 
            paid_amount = COALESCE((
                SELECT SUM(p.amount) 
                FROM payments p 
                WHERE p.reserve_number = c.reserve_number
            ), 0),
            balance = c.total_amount_due - COALESCE((
                SELECT SUM(p.amount) 
                FROM payments p 
                WHERE p.reserve_number = c.reserve_number
            ), 0)
        WHERE EXISTS (
            SELECT 1 FROM lms2026_payments lms WHERE lms.reserve_no = c.reserve_number
        )
    """)
    recalc_count = cur.rowcount
    conn.commit()
    print(f"✅ Recalculated balances for {recalc_count:,} charters")
    
    conn.close()
    return inserted

def sync_charter_amounts(dry_run=True):
    """Update charter totals where LMS has different amounts"""
    conn = connect()
    cur = conn.cursor()
    
    print("\n" + "=" * 80)
    print("SYNC CHARTER AMOUNTS (LMS → ALMSDATA)")
    print("=" * 80)
    
    # Find amount mismatches
    cur.execute("""
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.total_amount_due as alms_total,
            lms.total as lms_total,
            lms.balance as lms_balance,
            c.balance as alms_balance
        FROM charters c
        JOIN lms2026_reserves lms ON lms.reserve_no = c.reserve_number
        WHERE ABS(COALESCE(lms.total, 0) - COALESCE(c.total_amount_due, 0)) > 0.02
        ORDER BY ABS(lms.total - c.total_amount_due) DESC
    """)
    
    mismatches = cur.fetchall()
    print(f"\nFound {len(mismatches):,} charters with amount discrepancies")
    
    if len(mismatches) == 0:
        print("✅ All charter amounts match")
        conn.close()
        return 0
    
    # Show sample
    print("\nTop amount discrepancies:")
    for row in mismatches[:20]:
        diff = (row[3] or 0) - (row[2] or 0)
        print(f"  {row[1]} | ALMS: ${row[2]:,.2f} | LMS: ${row[3]:,.2f} | Diff: ${diff:,.2f}")
    
    print("\n⚠️  DECISION REQUIRED:")
    print("   Which is the source of truth?")
    print("   1. LMS amounts (legacy system)")
    print("   2. ALMSDATA amounts (current system with manual adjustments)")
    print("\n   Recommendation: Review manual before auto-syncing")
    print("   Many ALMSDATA amounts have been manually corrected for cancelled runs")
    
    if dry_run:
        print(f"\n🔍 DRY RUN: Would update {len(mismatches):,} charter amounts")
        conn.close()
        return len(mismatches)
    
    print("\n⚠️  Skipping auto-sync - manual review required")
    print("   To force sync: Add --force-amounts flag (not recommended)")
    
    conn.close()
    return 0

def merge_missing_charges(dry_run=True):
    """Add charges from LMS that don't exist in almsdata"""
    conn = connect()
    cur = conn.cursor()
    
    print("\n" + "=" * 80)
    print("MERGE MISSING CHARGES")
    print("=" * 80)
    
    # Find missing charges
    cur.execute("""
        SELECT 
            lms.reserve_no,
            lms.description,
            lms.amount,
            lms.rate,
            lms.sequence,
            lms.is_closed,
            lms.note
        FROM lms2026_charges lms
        WHERE lms.reserve_no IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM charter_charges cc 
            JOIN charters c ON c.charter_id = cc.charter_id
            WHERE c.reserve_number = lms.reserve_no
              AND LOWER(cc.description) = LOWER(lms.description)
              AND ABS(cc.amount - lms.amount) < 0.02
          )
        ORDER BY lms.amount DESC
    """)
    
    missing_charges = cur.fetchall()
    total_amount = sum(row[2] for row in missing_charges if row[2])
    
    print(f"\nFound {len(missing_charges):,} charges in LMS not in almsdata")
    print(f"Total amount: ${total_amount:,.2f}")
    
    if len(missing_charges) == 0:
        print("✅ No missing charges to merge")
        conn.close()
        return 0
    
    # Show sample
    print("\nSample missing charges:")
    for row in missing_charges[:10]:
        status = "CLOSED" if row[5] else "OPEN"
        print(f"  {row[0]} | {row[1][:40]:40} | ${row[2]:,.2f} | {status}")
    
    if dry_run:
        print(f"\n🔍 DRY RUN: Would insert {len(missing_charges):,} charges (${total_amount:,.2f})")
        conn.close()
        return len(missing_charges)
    
    # Perform merge
    print(f"\n✍️  Inserting {len(missing_charges):,} missing charges...")
    inserted = 0
    errors = []
    
    for row in missing_charges:
        try:
            # Get charter_id via reserve_number
            cur.execute("SELECT charter_id FROM charters WHERE reserve_number = %s LIMIT 1", (row[0],))
            charter_row = cur.fetchone()
            
            if not charter_row:
                errors.append(f"Charter {row[0]} not found - skipping charge")
                continue
            
            charter_id = charter_row[0]
            
            cur.execute("""
                INSERT INTO charter_charges (
                    charter_id, description, amount, rate, charge_order, notes, created_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP
                )
            """, (
                charter_id, row[1], row[2], row[3], row[4], row[6]
            ))
            inserted += 1
            
            if inserted % 100 == 0:
                print(f"  {inserted} inserted...", end='\r')
                
        except Exception as e:
            errors.append(f"Error inserting charge for {row[0]}: {e}")
    
    conn.commit()
    print(f"\n✅ Inserted {inserted:,} charges")
    
    if errors:
        print(f"⚠️  {len(errors)} errors (first 5):")
        for err in errors[:5]:
            print(f"   {err}")
    
    conn.close()
    return inserted

def main():
    parser = argparse.ArgumentParser(description='Merge LMS 2026 data to almsdata')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without applying')
    parser.add_argument('--charters', action='store_true', help='Merge missing charters only')
    parser.add_argument('--payments', action='store_true', help='Merge missing payments only')
    parser.add_argument('--charges', action='store_true', help='Merge missing charges only')
    parser.add_argument('--all', action='store_true', help='Merge all missing data')
    args = parser.parse_args()
    
    dry_run = args.dry_run
    
    print("=" * 80)
    if dry_run:
        print("LMS 2026 → ALMSDATA MERGE (DRY RUN)")
    else:
        print("LMS 2026 → ALMSDATA MERGE (LIVE)")
    print("=" * 80)
    
    if not any([args.charters, args.payments, args.charges, args.all]):
        print("\nNo merge option selected. Use --help for options")
        print("\nRecommended workflow:")
        print("  1. python scripts/merge_lms_to_almsdata.py --dry-run --all")
        print("  2. Review changes")
        print("  3. python scripts/merge_lms_to_almsdata.py --charters")
        print("  4. python scripts/merge_lms_to_almsdata.py --payments")
        print("  5. python scripts/merge_lms_to_almsdata.py --charges")
        return
    
    results = {}
    
    if args.charters or args.all:
        results['charters'] = merge_missing_charters(dry_run)
    
    if args.payments or args.all:
        results['payments'] = merge_missing_payments(dry_run)
    
    if args.charges or args.all:
        results['charges'] = merge_missing_charges(dry_run)
    
    # Summary
    print("\n" + "=" * 80)
    print("MERGE SUMMARY")
    print("=" * 80)
    for key, count in results.items():
        status = "would merge" if dry_run else "merged"
        print(f"  {key.capitalize():15} {status:15} {count:,}")
    
    if dry_run:
        print("\n🔍 This was a DRY RUN - no changes applied")
        print("   Remove --dry-run to apply changes")
    else:
        print("\n✅ Merge complete!")
        print("   Run charter-payment audit to verify: Run charter-payment audit task")

if __name__ == "__main__":
    main()
