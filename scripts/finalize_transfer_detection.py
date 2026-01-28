import os
from datetime import date, timedelta
from typing import List, Dict, Tuple
from collections import defaultdict

import psycopg2
import psycopg2.extras

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

DATE_START = date(2012, 1, 1)
DATE_END = date(2017, 12, 31)

ACC_1615 = {"bank_id": 4, "account_number": "1615"}
ACC_8362 = {"bank_id": 1, "account_number": "0228362"}

TRANSFER_KEYWORDS = ["transfer", "xfer", "x-fer", "xfr", "moving", "to 0228362", "to 1615", "from 0228362", "from 1615"]
CASH_KEYWORDS = ["cash", "withdrawal", "atm", "cash box", "petty cash"]


def get_conn():
    return psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)


def fetch_tx(cur, bank_id: int, account_number: str) -> List[Dict]:
    cur.execute(
        """
        SELECT transaction_id, transaction_date, description,
               debit_amount, credit_amount, balance, source_file
        FROM banking_transactions
        WHERE bank_id = %s AND account_number = %s
          AND transaction_date BETWEEN %s AND %s
        ORDER BY transaction_date, transaction_id
        """,
        (bank_id, account_number, DATE_START, DATE_END),
    )
    return [dict(r) for r in cur.fetchall()]


def amt_out(row: Dict) -> float:
    d = row.get("debit_amount")
    return float(d) if d is not None else 0.0


def amt_in(row: Dict) -> float:
    c = row.get("credit_amount")
    return float(c) if c is not None else 0.0


def has_kw(desc: str, keywords: List[str]) -> bool:
    if not desc:
        return False
    low = desc.lower()
    return any(k in low for k in keywords)


def is_arrow_cheque(desc: str) -> bool:
    if not desc:
        return False
    low = desc.lower()
    return ('chq' in low or 'cheque' in low or 'check' in low) and 'arrow' in low and 'limousine' in low


def is_cash_withdrawal(desc: str) -> bool:
    if not desc:
        return False
    return has_kw(desc, CASH_KEYWORDS)


def has_pennies(amount: float) -> bool:
    if amount is None:
        return False
    return round(amount % 1.0, 2) not in [0.0, 0.00]


def classify_transaction(row: Dict) -> str:
    desc = row.get("description", "")
    amt_d = amt_out(row)
    amt_c = amt_in(row)
    amount = amt_d if amt_d > 0 else amt_c
    
    if is_arrow_cheque(desc):
        return "arrow_cheque_transfer"
    if is_cash_withdrawal(desc):
        return "cash_withdrawal"
    if has_kw(desc, TRANSFER_KEYWORDS):
        return "explicit_transfer"
    if has_pennies(amount):
        return "non_round_amount"
    if amount > 0 and round(amount % 100, 2) == 0:
        return "round_100s"
    return "other"


def match_transfers(out_list: List[Dict], in_list: List[Dict], day_window: int = 5) -> Tuple[List[Tuple[Dict, Dict, int, str]], List[Dict], List[Dict]]:
    bucket = defaultdict(list)
    for r in in_list:
        a = round(amt_in(r), 2)
        if a > 0:
            bucket[a].append(r)

    matched = []
    used_in_ids = set()

    for o in out_list:
        a = round(amt_out(o), 2)
        if a <= 0:
            continue
        
        candidates = [r for r in bucket.get(a, []) if r["transaction_id"] not in used_in_ids]
        if not candidates:
            continue
        
        best = None
        best_score = None
        match_reason = ""
        
        for cand in candidates:
            dd = abs((cand["transaction_date"] - o["transaction_date"]).days)
            if dd > day_window:
                continue
            
            score = dd * 100
            reason_parts = []
            
            if is_arrow_cheque(o.get("description")) or is_arrow_cheque(cand.get("description")):
                score -= 500
                reason_parts.append("arrow_cheque")
            
            if has_kw(o.get("description"), TRANSFER_KEYWORDS):
                score -= 300
                reason_parts.append("xfer_kw_out")
            if has_kw(cand.get("description"), TRANSFER_KEYWORDS):
                score -= 300
                reason_parts.append("xfer_kw_in")
            
            if is_cash_withdrawal(o.get("description")):
                score -= 200
                reason_parts.append("cash_withdrawal")
            
            if has_pennies(a):
                score -= 100
                reason_parts.append("pennies")
            
            score += abs(cand["transaction_id"] - o["transaction_id"]) / 10000
            
            reason = "+".join(reason_parts) if reason_parts else "amount_date_match"
            
            if best_score is None or score < best_score:
                best = cand
                best_score = score
                match_reason = reason
        
        if best is not None:
            used_in_ids.add(best["transaction_id"])
            dd = abs((best["transaction_date"] - o["transaction_date"]).days)
            matched.append((o, best, dd, match_reason))

    unmatched_out = [o for o in out_list if round(amt_out(o), 2) > 0 and all(o["transaction_id"] != m[0]["transaction_id"] for m in matched)]
    unmatched_in = [i for i in in_list if round(amt_in(i), 2) > 0 and i["transaction_id"] not in used_in_ids]
    
    return matched, unmatched_out, unmatched_in


def create_transfers_table(cur):
    """Create banking_inter_account_transfers table"""
    cur.execute("""
        CREATE TABLE IF NOT EXISTS banking_inter_account_transfers (
            transfer_id SERIAL PRIMARY KEY,
            from_transaction_id BIGINT NOT NULL,
            to_transaction_id BIGINT NOT NULL,
            from_account_number VARCHAR(50),
            to_account_number VARCHAR(50),
            from_bank_id INTEGER,
            to_bank_id INTEGER,
            transfer_date DATE,
            amount NUMERIC(12,2),
            date_diff_days INTEGER,
            match_reason TEXT,
            transfer_type VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(from_transaction_id, to_transaction_id)
        )
    """)
    
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_transfers_from_tx 
        ON banking_inter_account_transfers(from_transaction_id)
    """)
    
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_transfers_to_tx 
        ON banking_inter_account_transfers(to_transaction_id)
    """)
    
    print("✅ Created banking_inter_account_transfers table")


def add_receipt_transfer_flag(cur):
    """Add is_transfer flag to receipts table"""
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'receipts' AND column_name = 'is_transfer'
    """)
    
    if not cur.fetchone():
        cur.execute("""
            ALTER TABLE receipts 
            ADD COLUMN is_transfer BOOLEAN DEFAULT FALSE
        """)
        print("✅ Added is_transfer column to receipts")
    else:
        print("ℹ️  is_transfer column already exists in receipts")
    
    # Also add to banking_transactions for easier querying
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'banking_transactions' AND column_name = 'is_transfer'
    """)
    
    if not cur.fetchone():
        cur.execute("""
            ALTER TABLE banking_transactions 
            ADD COLUMN is_transfer BOOLEAN DEFAULT FALSE
        """)
        print("✅ Added is_transfer column to banking_transactions")
    else:
        print("ℹ️  is_transfer column already exists in banking_transactions")


def insert_transfers(cur, pairs: List[Tuple[Dict, Dict, int, str]], from_acc: str, to_acc: str, from_bank_id: int, to_bank_id: int) -> int:
    """Insert transfer pairs into the table"""
    inserted = 0
    for o, i, dd, reason in pairs:
        tx_type = classify_transaction(o)
        amount = amt_out(o)
        
        try:
            cur.execute("""
                INSERT INTO banking_inter_account_transfers (
                    from_transaction_id, to_transaction_id, 
                    from_account_number, to_account_number,
                    from_bank_id, to_bank_id,
                    transfer_date, amount, date_diff_days, match_reason, transfer_type
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (from_transaction_id, to_transaction_id) DO NOTHING
            """, (
                o["transaction_id"], i["transaction_id"],
                from_acc, to_acc,
                from_bank_id, to_bank_id,
                o["transaction_date"], amount, dd, reason, tx_type
            ))
            if cur.rowcount > 0:
                inserted += 1
        except Exception as e:
            print(f"⚠️  Error inserting transfer pair {o['transaction_id']} -> {i['transaction_id']}: {e}")
    
    return inserted


def mark_banking_transactions_as_transfers(cur) -> int:
    """Mark banking transactions that are part of transfers"""
    cur.execute("""
        UPDATE banking_transactions bt
        SET is_transfer = TRUE
        WHERE EXISTS (
            SELECT 1 FROM banking_inter_account_transfers t
            WHERE t.from_transaction_id = bt.transaction_id
               OR t.to_transaction_id = bt.transaction_id
        )
        AND is_transfer IS DISTINCT FROM TRUE
    """)
    return cur.rowcount


def mark_receipts_as_transfers(cur) -> int:
    """Mark receipts linked to transfer transactions"""
    cur.execute("""
        UPDATE receipts r
        SET is_transfer = TRUE
        WHERE EXISTS (
            SELECT 1 FROM banking_inter_account_transfers t
            WHERE t.from_transaction_id = r.banking_transaction_id
               OR t.to_transaction_id = r.banking_transaction_id
        )
        AND is_transfer IS DISTINCT FROM TRUE
    """)
    return cur.rowcount


def update_ledger_for_transfers(cur) -> int:
    """Update banking_receipt_matching_ledger to mark transfers"""
    # Check if match_type column exists
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'banking_receipt_matching_ledger' 
          AND column_name = 'match_type'
    """)
    
    if cur.fetchone():
        cur.execute("""
            UPDATE banking_receipt_matching_ledger bm
            SET match_type = 'transfer'
            WHERE EXISTS (
                SELECT 1 FROM banking_inter_account_transfers t
                WHERE t.from_transaction_id = bm.banking_transaction_id
                   OR t.to_transaction_id = bm.banking_transaction_id
            )
            AND match_type IS DISTINCT FROM 'transfer'
        """)
        return cur.rowcount
    return 0


def generate_summary(cur):
    """Generate summary statistics"""
    print("\n" + "="*80)
    print("TRANSFER DETECTION SUMMARY")
    print("="*80)
    
    # Total transfers
    cur.execute("SELECT COUNT(*) FROM banking_inter_account_transfers")
    total = cur.fetchone()[0]
    print(f"\nTotal transfer pairs: {total:,}")
    
    # By transfer type
    cur.execute("""
        SELECT transfer_type, COUNT(*), SUM(amount)
        FROM banking_inter_account_transfers
        GROUP BY transfer_type
        ORDER BY COUNT(*) DESC
    """)
    print(f"\nBy Transfer Type:")
    for tx_type, count, amount in cur.fetchall():
        print(f"  {tx_type}: {count:,} transfers, ${float(amount or 0):,.2f}")
    
    # By direction
    cur.execute("""
        SELECT from_account_number, to_account_number, COUNT(*), SUM(amount)
        FROM banking_inter_account_transfers
        GROUP BY from_account_number, to_account_number
        ORDER BY COUNT(*) DESC
    """)
    print(f"\nBy Direction:")
    for from_acc, to_acc, count, amount in cur.fetchall():
        print(f"  {from_acc} → {to_acc}: {count:,} transfers, ${float(amount or 0):,.2f}")
    
    # Banking transactions marked
    cur.execute("SELECT COUNT(*) FROM banking_transactions WHERE is_transfer = TRUE")
    bt_marked = cur.fetchone()[0]
    print(f"\nBanking transactions marked as transfers: {bt_marked:,}")
    
    # Receipts marked
    cur.execute("SELECT COUNT(*) FROM receipts WHERE is_transfer = TRUE")
    receipts_marked = cur.fetchone()[0]
    print(f"Receipts marked as transfers (excluded from expenses): {receipts_marked:,}")
    
    # Receipts total amount excluded
    cur.execute("""
        SELECT COUNT(*), SUM(gross_amount)
        FROM receipts
        WHERE is_transfer = TRUE
    """)
    r_count, r_amount = cur.fetchone()
    print(f"  Total amount excluded: ${float(r_amount or 0):,.2f}")
    
    print("\n" + "="*80)


def main():
    conn = get_conn()
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        print("="*80)
        print("BANKING INTER-ACCOUNT TRANSFER DETECTION & FLAGGING")
        print("="*80)
        
        # Step 1: Create table and add columns
        print("\n1. Creating schema...")
        create_transfers_table(cur)
        add_receipt_transfer_flag(cur)
        conn.commit()
        
        # Step 2: Load and match transactions
        print("\n2. Loading transactions...")
        t1615 = fetch_tx(cur, ACC_1615["bank_id"], ACC_1615["account_number"])
        t8362 = fetch_tx(cur, ACC_8362["bank_id"], ACC_8362["account_number"])
        print(f"  1615: {len(t1615)} transactions")
        print(f"  0228362: {len(t8362)} transactions")
        
        print("\n3. Matching transfers...")
        out_1615 = [r for r in t1615 if r["debit_amount"] is not None]
        in_8362 = [r for r in t8362 if r["credit_amount"] is not None]
        pairs_1615_to_8362, _, _ = match_transfers(out_1615, in_8362)
        
        out_8362 = [r for r in t8362 if r["debit_amount"] is not None]
        in_1615 = [r for r in t1615 if r["credit_amount"] is not None]
        pairs_8362_to_1615, _, _ = match_transfers(out_8362, in_1615)
        
        print(f"  1615 → 0228362: {len(pairs_1615_to_8362)} matches")
        print(f"  0228362 → 1615: {len(pairs_8362_to_1615)} matches")
        
        # Step 3: Insert transfers
        print("\n4. Inserting transfer pairs...")
        inserted_1 = insert_transfers(cur, pairs_1615_to_8362, "1615", "0228362", 
                                       ACC_1615["bank_id"], ACC_8362["bank_id"])
        inserted_2 = insert_transfers(cur, pairs_8362_to_1615, "0228362", "1615",
                                       ACC_8362["bank_id"], ACC_1615["bank_id"])
        print(f"  Inserted: {inserted_1 + inserted_2:,} transfer pairs")
        conn.commit()
        
        # Step 4: Mark banking transactions
        print("\n5. Marking banking transactions as transfers...")
        bt_marked = mark_banking_transactions_as_transfers(cur)
        print(f"  Marked {bt_marked:,} banking transactions")
        conn.commit()
        
        # Step 5: Mark receipts
        print("\n6. Marking receipts as transfers (excluded from expenses)...")
        receipts_marked = mark_receipts_as_transfers(cur)
        print(f"  Marked {receipts_marked:,} receipts")
        conn.commit()
        
        # Step 6: Update ledger
        print("\n7. Updating banking_receipt_matching_ledger...")
        ledger_updated = update_ledger_for_transfers(cur)
        if ledger_updated > 0:
            print(f"  Updated {ledger_updated:,} ledger entries")
            conn.commit()
        else:
            print("  (No match_type column or no entries to update)")
        
        # Step 7: Generate summary
        generate_summary(cur)
        
        print("\n✅ All operations complete!")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
