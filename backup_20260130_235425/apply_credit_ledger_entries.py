#!/usr/bin/env python3
"""Apply credit ledger entries from remediation proposal.

Reads l:/limo/reports/credit_ledger_proposal.csv and creates charter_credit_ledger
entries for charters with proposed_action = 'CREDIT_LEDGER'.

Strategy:
  1. Read proposal CSV filtered to CREDIT_LEDGER actions only
  2. For each charter:
       - Create credit_ledger entry with excess amount
       - Update charter.paid_amount -= excess (reduce to actual due)
       - Update charter.balance = 0 (zero out overpayment)
  3. Create backup before any updates
  4. Log all changes to audit trail

Safeguards:
  - Dry-run by default (--write to execute)
  - Backup charters table before updates
  - Verify credit_ledger table exists
  - Transaction rollback on any error

Usage:
  python scripts/apply_credit_ledger_entries.py                # Dry-run
  python scripts/apply_credit_ledger_entries.py --write        # Execute
  python scripts/apply_credit_ledger_entries.py --write --action-filter VERIFY_DEPOSIT_NONREFUNDABLE
"""

import os
import csv
import psycopg2
from datetime import datetime
from argparse import ArgumentParser
from dotenv import load_dotenv

load_dotenv("l:/limo/.env")
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

PROPOSAL_CSV = "l:/limo/reports/credit_ledger_proposal.csv"


def pg_conn():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def verify_table_exists(cur):
    cur.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_name = 'charter_credit_ledger'
        )
    """)
    return cur.fetchone()[0]


def create_backup(cur):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"charters_backup_credit_ledger_{timestamp}"
    cur.execute(f"CREATE TABLE {backup_name} AS SELECT * FROM charters")
    cur.execute("SELECT COUNT(*) FROM " + backup_name)
    count = cur.fetchone()[0]
    return backup_name, count


def load_proposals(action_filter=None):
    proposals = []
    with open(PROPOSAL_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if action_filter and row['proposed_action'] != action_filter:
                continue
            if not action_filter and row['proposed_action'] != 'CREDIT_LEDGER':
                continue
            # Skip zero or negative excess (constraint violation)
            excess = float(row['excess_amount'])
            if excess <= 0:
                continue
            proposals.append({
                'reserve_number': row['reserve_number'],
                'charter_id': int(row['charter_id']),
                'client_id': int(row['client_id']) if row['client_id'] else None,
                'excess': excess,
                'category': row['category'],
                'action': row['proposed_action'],
                'pg_due': float(row['pg_total_due']),
                'pg_paid': float(row['pg_paid_amount']),
            })
    return proposals


def map_category_to_reason(category):
    mapping = {
        'UNIFORM_INSTALLMENT': 'UNIFORM_INSTALLMENT',
        'LARGE_ETR': 'MULTI_CHARTER_PREPAY',
        'ETR_DOMINATED': 'ETR_OVERPAY',
        'MIXED': 'MIXED_OVERPAY',
    }
    return mapping.get(category, 'MIXED_OVERPAY')


def apply_credits(cur, proposals, dry_run=True):
    applied = []
    for p in proposals:
        reserve = p['reserve_number']
        charter_id = p['charter_id']
        client_id = p['client_id']
        excess = p['excess']
        reason = map_category_to_reason(p['category'])
        
        # Create credit ledger entry
        cur.execute("""
            INSERT INTO charter_credit_ledger 
            (source_reserve_number, source_charter_id, client_id, credit_amount, 
             remaining_balance, credit_reason, notes, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING credit_id
        """, (reserve, charter_id, client_id, excess, excess, reason,
              f"From overpayment remediation: {p['category']} pattern", 'apply_credit_ledger_entries.py'))
        
        credit_id = cur.fetchone()[0]
        
        # Update charter: reduce paid_amount by excess, zero balance
        new_paid = p['pg_paid'] - excess
        cur.execute("""
            UPDATE charters 
            SET paid_amount = %s, balance = 0
            WHERE charter_id = %s
        """, (new_paid, charter_id))
        
        applied.append({
            'credit_id': credit_id,
            'reserve': reserve,
            'charter_id': charter_id,
            'excess': excess,
            'reason': reason,
            'old_paid': p['pg_paid'],
            'new_paid': new_paid,
        })
    
    return applied


def summarize(applied):
    total_credits = sum(a['excess'] for a in applied)
    reason_counts = {}
    for a in applied:
        reason_counts[a['reason']] = reason_counts.get(a['reason'], 0) + 1
    
    print("=== Credit Ledger Application Summary ===")
    print(f"Credits created: {len(applied)}")
    print(f"Total credit amount: ${total_credits:,.2f}")
    print(f"\nBy reason:")
    for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
        reason_total = sum(a['excess'] for a in applied if a['reason'] == reason)
        print(f"  {reason}: {count} credits (${reason_total:,.2f})")
    
    print(f"\nTop 10 credits created:")
    sorted_applied = sorted(applied, key=lambda a: a['excess'], reverse=True)
    for a in sorted_applied[:10]:
        print(f"  credit_id={a['credit_id']} reserve={a['reserve']} "
              f"amount=${a['excess']:.2f} reason={a['reason']}")


def main():
    parser = ArgumentParser(description='Apply credit ledger entries from proposal')
    parser.add_argument('--write', action='store_true',
                       help='Execute changes (default is dry-run)')
    parser.add_argument('--action-filter', type=str,
                       help='Filter to specific action (default: CREDIT_LEDGER only)')
    args = parser.parse_args()
    
    if not os.path.exists(PROPOSAL_CSV):
        print(f"ERROR: Proposal CSV not found: {PROPOSAL_CSV}")
        print("Run generate_credit_ledger_proposal.py first")
        exit(1)
    
    conn = pg_conn()
    cur = conn.cursor()
    
    try:
        # Verify table exists
        if not verify_table_exists(cur):
            print("ERROR: charter_credit_ledger table does not exist")
            print("Run migration: psql -h localhost -U postgres -d almsdata -f migrations/2025-11-22_create_charter_credit_ledger.sql")
            exit(1)
        
        # Load proposals
        proposals = load_proposals(args.action_filter)
        if not proposals:
            filter_msg = f" with action={args.action_filter}" if args.action_filter else ""
            print(f"No proposals found{filter_msg}")
            exit(0)
        
        print(f"Loaded {len(proposals)} proposals from CSV")
        total_excess = sum(p['excess'] for p in proposals)
        print(f"Total excess to convert to credits: ${total_excess:,.2f}")
        
        if args.write:
            # Create backup
            backup_name, backup_count = create_backup(cur)
            print(f"\nBackup created: {backup_name} ({backup_count} rows)")
            
            # Apply credits
            print("\nApplying credit ledger entries...")
            applied = apply_credits(cur, proposals, dry_run=False)
            conn.commit()
            
            summarize(applied)
            print(f"\n✓ Changes committed to database")
            print(f"  Backup: {backup_name}")
        else:
            print("\n=== DRY-RUN MODE ===")
            print("Would create credit ledger entries for:")
            for i, p in enumerate(proposals[:10], 1):
                print(f"  {i}. reserve={p['reserve_number']} excess=${p['excess']:.2f} "
                      f"category={p['category']}")
            if len(proposals) > 10:
                print(f"  ... and {len(proposals) - 10} more")
            print(f"\nTotal credits: {len(proposals)} entries, ${total_excess:,.2f}")
            print("\nRun with --write to execute")
    
    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(2)
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    main()
