import os
from datetime import date
from typing import List, Dict, Tuple
from collections import defaultdict

import psycopg2
import psycopg2.extras

try:
    from openpyxl import Workbook
    from openpyxl.styles import PatternFill
    from openpyxl.utils import get_column_letter
except ImportError:
    Workbook = None

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

DATE_START = date(2012, 1, 1)
DATE_END = date(2019, 12, 31)  # Scotia extends to 2019

# Account definitions
ACC_1615 = {"bank_id": 4, "account_number": "1615", "name": "CIBC 1615"}
ACC_8362 = {"bank_id": 1, "account_number": "0228362", "name": "CIBC 0228362"}
ACC_SCOTIA = {"bank_id": 2, "account_number": "903990106011", "name": "Scotia"}

ACCOUNTS = [ACC_1615, ACC_8362, ACC_SCOTIA]

TRANSFER_KEYWORDS = ["transfer", "xfer", "x-fer", "xfr", "moving", "to 0228362", "to 1615", "to scotia", "from 0228362", "from 1615", "from scotia"]
CASH_KEYWORDS = ["cash", "withdrawal", "atm", "cash box", "petty cash"]


def get_conn():
    return psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)


def fetch_tx(cur, bank_id: int, account_number: str) -> List[Dict]:
    cur.execute(
        """
        SELECT transaction_id, transaction_date, description,
               debit_amount, credit_amount, balance, source_file,
               bank_id, account_number
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


def insert_transfers(cur, pairs: List[Tuple[Dict, Dict, int, str]], from_acc_name: str, to_acc_name: str) -> int:
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
                o["account_number"], i["account_number"],
                o["bank_id"], i["bank_id"],
                o["transaction_date"], amount, dd, reason, tx_type
            ))
            if cur.rowcount > 0:
                inserted += 1
        except Exception as e:
            print(f"⚠️  Error inserting {from_acc_name}→{to_acc_name} transfer {o['transaction_id']}→{i['transaction_id']}: {e}")
    
    return inserted


def mark_all_transfers(cur) -> Tuple[int, int, int]:
    """Mark banking transactions, receipts, and ledger entries as transfers"""
    
    # Banking transactions
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
    bt_marked = cur.rowcount
    
    # Receipts
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
    receipts_marked = cur.rowcount
    
    # Ledger
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
    ledger_updated = cur.rowcount
    
    return bt_marked, receipts_marked, ledger_updated


def main():
    conn = get_conn()
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        print("="*80)
        print("ALL ACCOUNT TRANSFER DETECTION (1615, 0228362, Scotia)")
        print("="*80)
        
        # Load all transactions
        print("\n1. Loading transactions...")
        tx_by_account = {}
        for acc in ACCOUNTS:
            tx = fetch_tx(cur, acc["bank_id"], acc["account_number"])
            tx_by_account[acc["name"]] = tx
            print(f"  {acc['name']}: {len(tx)} transactions")
        
        # Find all pairwise transfers
        print("\n2. Matching transfers between all account pairs...")
        all_pairs = []
        pair_labels = []
        
        for i, acc_from in enumerate(ACCOUNTS):
            for j, acc_to in enumerate(ACCOUNTS):
                if i >= j:  # Skip self and reverse pairs
                    continue
                
                name_from = acc_from["name"]
                name_to = acc_to["name"]
                
                # From -> To direction
                out_from = [r for r in tx_by_account[name_from] if r["debit_amount"] is not None]
                in_to = [r for r in tx_by_account[name_to] if r["credit_amount"] is not None]
                pairs_fwd, _, _ = match_transfers(out_from, in_to)
                
                # To -> From direction
                out_to = [r for r in tx_by_account[name_to] if r["debit_amount"] is not None]
                in_from = [r for r in tx_by_account[name_from] if r["credit_amount"] is not None]
                pairs_rev, _, _ = match_transfers(out_to, in_from)
                
                print(f"  {name_from} ↔ {name_to}: {len(pairs_fwd)} + {len(pairs_rev)} = {len(pairs_fwd)+len(pairs_rev)} transfers")
                
                all_pairs.extend([(name_from, name_to, pairs_fwd), (name_to, name_from, pairs_rev)])
        
        # Insert all transfers
        print("\n3. Inserting transfer pairs...")
        total_inserted = 0
        for name_from, name_to, pairs in all_pairs:
            inserted = insert_transfers(cur, pairs, name_from, name_to)
            if inserted > 0:
                print(f"  {name_from} → {name_to}: {inserted} new pairs")
            total_inserted += inserted
        
        print(f"\n  Total new transfer pairs inserted: {total_inserted}")
        conn.commit()
        
        # Mark all transfers
        print("\n4. Marking transfers...")
        bt_marked, receipts_marked, ledger_updated = mark_all_transfers(cur)
        print(f"  Banking transactions marked: {bt_marked}")
        print(f"  Receipts marked: {receipts_marked}")
        print(f"  Ledger entries updated: {ledger_updated}")
        conn.commit()
        
        # Summary
        print("\n" + "="*80)
        print("FINAL SUMMARY")
        print("="*80)
        
        cur.execute("SELECT COUNT(*) FROM banking_inter_account_transfers")
        total = cur.fetchone()[0]
        print(f"\nTotal transfer pairs in database: {total:,}")
        
        cur.execute("""
            SELECT from_account_number, to_account_number, COUNT(*), SUM(amount)
            FROM banking_inter_account_transfers
            GROUP BY from_account_number, to_account_number
            ORDER BY COUNT(*) DESC
        """)
        print(f"\nBy Direction:")
        for from_acc, to_acc, count, amount in cur.fetchall():
            print(f"  {from_acc} → {to_acc}: {count:,} transfers, ${float(amount or 0):,.2f}")
        
        cur.execute("SELECT COUNT(*) FROM banking_transactions WHERE is_transfer = TRUE")
        bt_total = cur.fetchone()[0]
        print(f"\nBanking transactions flagged as transfers: {bt_total:,}")
        
        cur.execute("SELECT COUNT(*), SUM(gross_amount) FROM receipts WHERE is_transfer = TRUE")
        r_count, r_amount = cur.fetchone()
        print(f"Receipts flagged as transfers: {r_count:,} (${float(r_amount or 0):,.2f} excluded from expenses)")
        
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
