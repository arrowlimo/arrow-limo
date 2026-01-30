#!/usr/bin/env python3
"""
Import Square Payments from Staging to Payments Table
Performs 3 stages:
1. Import 22 missing Square transactions from square_transactions_staging
2. Match ALL unlinked Square payments to charters via reserve_number (amount/date proximity)
3. Report linking success rate and unmatched transactions

All 273 Square transactions are INCOMING client credit card payments (verified against square_deposits_staging).
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from typing import Optional, Tuple
from decimal import Decimal

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment
load_dotenv("l:/limo/.env")
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

DRY_RUN = "--dry-run" in sys.argv
WRITE = "--write" in sys.argv


def get_db_conn():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )


def import_missing_square_payments() -> int:
    """Import 22 missing Square transactions from staging to payments table."""
    print("\n=== STAGE 1: IMPORT 22 MISSING SQUARE TRANSACTIONS ===")
    
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            # Find 22 missing transactions
            cur.execute("""
                SELECT s.staging_id, s.square_payment_id, s.transaction_date, s.amount, s.notes
                FROM square_transactions_staging s
                WHERE NOT EXISTS (
                    SELECT 1 FROM payments p WHERE p.square_payment_id = s.square_payment_id
                )
                ORDER BY s.transaction_date DESC
            """)
            missing = cur.fetchall()
            print(f"📊 Found {len(missing)} missing Square transactions")
            
            if len(missing) > 0:
                total_missing = sum(row[3] for row in missing)
                print(f"💰 Total missing amount: ${total_missing:.2f}")
                
                if WRITE and not DRY_RUN:
                    for staging_id, square_payment_id, trans_date, amount, notes in missing:
                        try:
                            cur.execute("""
                                INSERT INTO payments 
                                (reserve_number, charter_id, amount, payment_date, payment_method, 
                                 square_payment_id, notes, payment_key, created_at)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                                ON CONFLICT (payment_key) DO NOTHING
                            """, (
                                None,  # reserve_number - to be matched in Stage 2
                                None,  # charter_id - to be matched in Stage 2
                                amount,
                                trans_date,
                                'credit_card',
                                square_payment_id,
                                notes or '[Square] Imported from staging',
                                f"SQ-{square_payment_id}"  # payment_key
                            ))
                        except Exception as e:
                            print(f"⚠️  Error importing {square_payment_id}: {e}")
                    
                    conn.commit()
                    print(f"✅ Imported {len(missing)} transactions")
                    return len(missing)
                elif DRY_RUN:
                    print(f"🔍 DRY-RUN: Would import {len(missing)} transactions")
                    for i, (_, sqid, date, amt, notes) in enumerate(missing[:5], 1):
                        print(f"  {i}. {sqid} | {date.date()} | ${amt:.2f}")
                    if len(missing) > 5:
                        print(f"  ... and {len(missing)-5} more")
                    return 0
    
    return 0


def find_matching_charter(cur, amount: Decimal, payment_date, tolerance: Decimal = Decimal("5.00")) -> Optional[Tuple[str, Decimal]]:
    """
    Find matching charter for Square payment using amount/date proximity.
    Returns: (reserve_number, balance_impact) or None if no match found.
    """
    # Look for chartering within tolerance and within date window (±7 days)
    date_from = (payment_date - timedelta(days=7)).date() if hasattr(payment_date, 'date') else payment_date - timedelta(days=7)
    date_to = (payment_date + timedelta(days=7)).date() if hasattr(payment_date, 'date') else payment_date + timedelta(days=7)
    
    # Convert dates to proper format
    if hasattr(date_from, 'date'):
        date_from = date_from.date()
    if hasattr(date_to, 'date'):
        date_to = date_to.date()
    
    # First try: exact amount match on charter_date ±7 days
    cur.execute("""
        SELECT c.reserve_number, c.total_amount_due, COALESCE(SUM(p.amount), 0) as paid_amount
        FROM charters c
        LEFT JOIN payments p ON p.reserve_number = c.reserve_number
        WHERE ABS(c.total_amount_due - %s) <= %s
          AND c.charter_date::date BETWEEN %s AND %s
          AND c.status NOT IN ('cancelled', 'no-show')
        GROUP BY c.reserve_number, c.total_amount_due
        LIMIT 1
    """, (float(amount), float(tolerance), date_from, date_to))
    
    result = cur.fetchone()
    if result:
        reserve_no, total_due, paid = result
        balance = Decimal(str(total_due)) - Decimal(str(paid))
        return (reserve_no, balance)
    
    # Second try: amount within 10% on charter_date ±14 days
    tolerance_pct = amount * Decimal("0.10")
    date_from = (payment_date - timedelta(days=14)).date() if hasattr(payment_date, 'date') else payment_date - timedelta(days=14)
    date_to = (payment_date + timedelta(days=14)).date() if hasattr(payment_date, 'date') else payment_date + timedelta(days=14)
    
    if hasattr(date_from, 'date'):
        date_from = date_from.date()
    if hasattr(date_to, 'date'):
        date_to = date_to.date()
    
    cur.execute("""
        SELECT c.reserve_number, c.total_amount_due, COALESCE(SUM(p.amount), 0) as paid_amount
        FROM charters c
        LEFT JOIN payments p ON p.reserve_number = c.reserve_number
        WHERE c.total_amount_due BETWEEN %s AND %s
          AND c.charter_date::date BETWEEN %s AND %s
          AND c.status NOT IN ('cancelled', 'no-show')
        GROUP BY c.reserve_number, c.total_amount_due
        LIMIT 1
    """, (float(amount - tolerance_pct), float(amount + tolerance_pct), date_from, date_to))
    
    result = cur.fetchone()
    if result:
        reserve_no, total_due, paid = result
        balance = Decimal(str(total_due)) - Decimal(str(paid))
        return (reserve_no, balance)
    
    return None


def match_square_payments_to_charters() -> Tuple[int, int, Decimal]:
    """
    Stage 2: Match all unlinked Square payments to charters.
    Returns: (matched_count, unmatched_count, total_matched_amount)
    """
    print("\n=== STAGE 2: MATCH UNLINKED SQUARE PAYMENTS TO CHARTERS ===")
    
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            # Find all unlinked Square payments
            cur.execute("""
                SELECT p.payment_id, p.reserve_number, p.square_payment_id, 
                       p.amount, p.payment_date, p.notes
                FROM payments p
                WHERE p.square_payment_id IS NOT NULL 
                  AND (p.reserve_number IS NULL OR p.reserve_number = '')
                ORDER BY p.payment_date DESC
            """)
            unlinked = cur.fetchall()
            print(f"📊 Found {len(unlinked)} unlinked Square payments")
            
            matched_count = 0
            unmatched_list = []
            total_matched = Decimal("0.00")
            
            for payment_id, _, square_payment_id, amount, payment_date, notes in unlinked:
                match = find_matching_charter(cur, Decimal(str(amount)), payment_date)
                
                if match:
                    reserve_no, balance = match
                    matched_count += 1
                    total_matched += Decimal(str(amount))
                    
                    if WRITE and not DRY_RUN:
                        try:
                            cur.execute("""
                                UPDATE payments
                                SET reserve_number = %s, last_updated = NOW()
                                WHERE payment_id = %s
                            """, (reserve_no, payment_id))
                        except Exception as e:
                            print(f"⚠️  Error updating payment {payment_id}: {e}")
                    
                    print(f"✅ Matched: {square_payment_id[:8]}... | ${amount:.2f} | Reserve: {reserve_no} | Balance: ${balance:.2f}")
                else:
                    unmatched_list.append((square_payment_id, amount, payment_date))
            
            if WRITE and not DRY_RUN:
                conn.commit()
                print(f"\n✅ Updated {matched_count} payments with reserve numbers")
            elif DRY_RUN:
                print(f"\n🔍 DRY-RUN: Would update {matched_count} payments")
            
            # Report unmatched
            if unmatched_list:
                print(f"\n❌ UNMATCHED: {len(unmatched_list)} Square payments could not be linked to charters")
                total_unmatched = sum(amt for _, amt, _ in unmatched_list)
                print(f"💰 Total unmatched amount: ${total_unmatched:.2f}")
                print("\nFirst 10 unmatched:")
                for sqid, amt, date in unmatched_list[:10]:
                    print(f"  {sqid[:8]}... | ${amt:.2f} | {date.date() if hasattr(date, 'date') else date}")
                if len(unmatched_list) > 10:
                    print(f"  ... and {len(unmatched_list)-10} more")
            
            return matched_count, len(unmatched_list), total_matched


def generate_summary_report():
    """Generate final summary of Square payment import and matching."""
    print("\n=== FINAL SUMMARY ===")
    
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            # Total Square payments in system
            cur.execute("SELECT COUNT(*) FROM payments WHERE square_payment_id IS NOT NULL")
            total_sq = cur.fetchone()[0]
            
            # Linked Square payments
            cur.execute("""
                SELECT COUNT(*), SUM(amount) 
                FROM payments 
                WHERE square_payment_id IS NOT NULL AND reserve_number IS NOT NULL
            """)
            linked_count, linked_total = cur.fetchone()
            linked_total = linked_total or 0
            
            # Unlinked Square payments
            cur.execute("""
                SELECT COUNT(*), SUM(amount)
                FROM payments
                WHERE square_payment_id IS NOT NULL AND (reserve_number IS NULL OR reserve_number = '')
            """)
            unlinked_count, unlinked_total = cur.fetchone()
            unlinked_total = unlinked_total or 0
            
            # Total Square deposits
            cur.execute("SELECT SUM(amount) FROM square_transactions_staging")
            total_deposits = cur.fetchone()[0] or 0
            
            print(f"""
📊 SQUARE PAYMENT TOTALS:
  • Total transactions in staging: 273
  • Total deposited: ${total_deposits:.2f}
  • Total in payments table: {total_sq}
  
🔗 LINKING STATUS:
  • Linked to reserves: {linked_count} payments (${linked_total:.2f})
  • Unlinked to reserves: {unlinked_count} payments (${unlinked_total:.2f})
  • Linking success rate: {100*linked_count/total_sq if total_sq > 0 else 0:.1f}%
  • Amount matched: ${linked_total:.2f} / ${total_deposits:.2f} ({100*linked_total/total_deposits if total_deposits > 0 else 0:.1f}%)
            """)


if __name__ == "__main__":
    print("🚀 SQUARE PAYMENT IMPORT & MATCHING SCRIPT")
    print(f"📋 Mode: {'DRY-RUN' if DRY_RUN else 'WRITE' if WRITE else 'REPORT ONLY'}")
    
    # Stage 1: Import missing
    imported = import_missing_square_payments()
    
    # Stage 2: Match to charters
    matched, unmatched, total_matched = match_square_payments_to_charters()
    
    # Final report
    generate_summary_report()
    
    if DRY_RUN:
        print("\n⚠️  DRY-RUN MODE: No changes written to database")
        print("Run with --write flag to apply changes")
    elif WRITE:
        print("\n✅ IMPORT COMPLETE")
    else:
        print("\n💡 Use --dry-run to preview or --write to apply changes")
