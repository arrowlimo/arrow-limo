#!/usr/bin/env python3
"""
Find duplicate payments that are causing negative balances.
Look for payments with same reserve_number, amount, and date.
"""

import psycopg2

def get_db_connection():
    import os
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "="*80)
    print("FINDING DUPLICATE PAYMENTS IN NEGATIVE BALANCE CHARTERS")
    print("="*80)
    
    # Find payments where there are duplicates (same reserve, amount, date)
    cur.execute("""
        WITH payment_groups AS (
            SELECT 
                p.reserve_number,
                p.amount,
                p.payment_date,
                COUNT(*) as dup_count,
                ARRAY_AGG(p.payment_id ORDER BY p.payment_id) as payment_ids,
                ARRAY_AGG(p.charter_id ORDER BY p.payment_id) as charter_ids,
                ARRAY_AGG(p.notes ORDER BY p.payment_id) as notes_list
            FROM payments p
            JOIN charters ch ON p.charter_id = ch.charter_id
            WHERE ch.balance < 0
            AND ch.cancelled = FALSE
            GROUP BY p.reserve_number, p.amount, p.payment_date
            HAVING COUNT(*) > 1
        )
        SELECT 
            reserve_number,
            amount,
            payment_date,
            dup_count,
            payment_ids,
            charter_ids,
            notes_list
        FROM payment_groups
        ORDER BY dup_count DESC, amount DESC
        LIMIT 50
    """)
    
    dupes = cur.fetchall()
    
    print(f"\nFound {len(dupes):,} groups of duplicate payments in negative balance charters")
    
    if not dupes:
        print("No duplicates found!")
        cur.close()
        conn.close()
        return
    
    total_dup_payments = 0
    total_dup_amount = 0
    
    print(f"\n{'-'*80}")
    print("DUPLICATE PAYMENT GROUPS (showing first 20):")
    print(f"{'-'*80}")
    
    for i, dupe in enumerate(dupes[:20]):
        reserve, amount, date, dup_count, payment_ids, charter_ids, notes_list = dupe
        total_dup_payments += dup_count
        total_dup_amount += amount * dup_count
        
        print(f"\n{i+1}. Reserve {reserve}, ${amount:,.2f} on {date}")
        print(f"   {dup_count} duplicate payment records")
        print(f"   Payment IDs: {payment_ids}")
        print(f"   Charter IDs: {charter_ids}")
        
        # Show notes to understand source
        for j, note in enumerate(notes_list):
            if note:
                note_preview = note[:80] + '...' if len(note) > 80 else note
                print(f"   Note {j+1}: {note_preview}")
    
    if len(dupes) > 20:
        print(f"\n... and {len(dupes) - 20} more duplicate groups")
    
    # Identify patterns
    print(f"\n{'-'*80}")
    print("ANALYZING DUPLICATE PATTERNS:")
    print(f"{'-'*80}")
    
    # Check for "Imported from LMS" pattern
    cur.execute("""
        SELECT COUNT(*)
        FROM payments
        WHERE notes LIKE '%Imported from LMS Payment ID%'
        AND charter_id IN (
            SELECT charter_id FROM charters WHERE balance < 0 AND cancelled = FALSE
        )
    """)
    
    lms_import_count = cur.fetchone()[0]
    print(f"Payments with 'Imported from LMS Payment ID': {lms_import_count:,}")
    
    # Check for "Auto-linked" pattern
    cur.execute("""
        SELECT COUNT(*)
        FROM payments
        WHERE notes LIKE '%Auto-linked%'
        AND charter_id IN (
            SELECT charter_id FROM charters WHERE balance < 0 AND cancelled = FALSE
        )
    """)
    
    auto_linked_count = cur.fetchone()[0]
    print(f"Payments with 'Auto-linked':                 {auto_linked_count:,}")
    
    # Find pairs where one is auto-linked and one is LMS import
    cur.execute("""
        WITH auto_linked AS (
            SELECT payment_id, reserve_number, amount, payment_date, notes
            FROM payments
            WHERE notes LIKE '%Auto-linked%'
            AND charter_id IN (
                SELECT charter_id FROM charters WHERE balance < 0 AND cancelled = FALSE
            )
        ),
        lms_imported AS (
            SELECT payment_id, reserve_number, amount, payment_date, notes
            FROM payments
            WHERE notes LIKE '%Imported from LMS Payment ID%'
            AND charter_id IN (
                SELECT charter_id FROM charters WHERE balance < 0 AND cancelled = FALSE
            )
        )
        SELECT 
            a.payment_id as auto_id,
            l.payment_id as lms_id,
            a.reserve_number,
            a.amount,
            a.payment_date,
            a.notes as auto_notes,
            l.notes as lms_notes
        FROM auto_linked a
        JOIN lms_imported l ON 
            a.reserve_number = l.reserve_number
            AND a.amount = l.amount
            AND a.payment_date = l.payment_date
        LIMIT 20
    """)
    
    pairs = cur.fetchall()
    
    if pairs:
        print(f"\n{'-'*80}")
        print(f"FOUND {len(pairs):,} AUTO-LINKED / LMS-IMPORT DUPLICATE PAIRS:")
        print(f"{'-'*80}")
        
        for pair in pairs[:10]:
            auto_id, lms_id, reserve, amount, date, auto_notes, lms_notes = pair
            print(f"\nReserve {reserve}, ${amount:,.2f} on {date}")
            print(f"  Auto-linked ID: {auto_id}")
            print(f"  LMS Import ID: {lms_id}")
            
            # Extract LMS payment ID from notes
            if 'Imported from LMS Payment ID' in lms_notes:
                lms_payment_id = lms_notes.split('Imported from LMS Payment ID ')[1].split()[0]
                print(f"  LMS Payment ID: {lms_payment_id}")
                
                # Check if the auto-linked payment has the same ID
                if lms_payment_id in auto_notes:
                    print(f"  ✓ CONFIRMED DUPLICATE - Same LMS Payment ID in both!")
    
    print(f"\n{'='*80}\n")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
