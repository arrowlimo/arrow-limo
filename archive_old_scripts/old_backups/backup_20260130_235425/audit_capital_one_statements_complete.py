"""
Complete Capital One Statement Audit
Verifies all 2012 Capital One statements against database:
- Statement balances (previous, new, payments, transactions, interest)
- Banking payment matches
- Receipt matches for purchases
- Interest charge tracking
- Fee tracking
- Full reconciliation
"""
import os
import sys
from datetime import datetime, date
from decimal import Decimal
from typing import Dict, List, Tuple, Optional

import psycopg2
from psycopg2.extras import RealDictCursor


# Statement data from PDFs (account ending 9853)
STATEMENTS = [
    {
        "period": "Jan 21 - Feb 20, 2012",
        "start_date": date(2012, 1, 21),
        "end_date": date(2012, 2, 20),
        "previous_balance": Decimal("2532.28"),
        "payments_credits": Decimal("500.00"),
        "transactions": Decimal("549.41"),
        "other_charges": Decimal("29.00"),
        "interest_charges": Decimal("42.87"),
        "new_balance": Decimal("2653.56"),
        "minimum_payment": Decimal("79.00"),
        "due_date": date(2012, 3, 17),
    },
    {
        "period": "Feb 21 - Mar 20, 2012",
        "start_date": date(2012, 2, 21),
        "end_date": date(2012, 3, 20),
        "previous_balance": Decimal("2653.56"),
        "payments_credits": Decimal("0.00"),
        "transactions": Decimal("0.00"),
        "other_charges": Decimal("29.00"),
        "interest_charges": Decimal("48.00"),
        "new_balance": Decimal("2730.56"),
        "minimum_payment": Decimal("81.00"),
        "due_date": date(2012, 4, 15),
    },
    {
        "period": "Mar 21 - Apr 20, 2012",
        "start_date": date(2012, 3, 21),
        "end_date": date(2012, 4, 20),
        "previous_balance": Decimal("2730.56"),
        "payments_credits": Decimal("2730.56"),
        "transactions": Decimal("0.00"),
        "other_charges": Decimal("29.00"),
        "interest_charges": Decimal("29.51"),
        "new_balance": Decimal("29.51"),
        "minimum_payment": Decimal("10.00"),
        "due_date": date(2012, 5, 16),
    },
    {
        "period": "Apr 21 - May 20, 2012",
        "start_date": date(2012, 4, 21),
        "end_date": date(2012, 5, 20),
        "previous_balance": Decimal("29.51"),
        "payments_credits": Decimal("0.00"),
        "transactions": Decimal("2470.49"),
        "other_charges": Decimal("29.00"),
        "interest_charges": Decimal("0.51"),
        "new_balance": Decimal("2529.51"),
        "minimum_payment": Decimal("75.00"),
        "due_date": date(2012, 6, 15),
    },
    {
        "period": "May 21 - Jun 20, 2012",
        "start_date": date(2012, 5, 21),
        "end_date": date(2012, 6, 20),
        "previous_balance": Decimal("2529.51"),
        "payments_credits": Decimal("0.00"),
        "transactions": Decimal("0.00"),
        "other_charges": Decimal("29.00"),
        "interest_charges": Decimal("75.70"),
        "new_balance": Decimal("2634.21"),
        "minimum_payment": Decimal("154.00"),
        "due_date": date(2012, 7, 16),
    },
    {
        "period": "Jun 21 - Jul 20, 2012",
        "start_date": date(2012, 6, 21),
        "end_date": date(2012, 7, 20),
        "previous_balance": Decimal("2634.21"),
        "payments_credits": Decimal("0.00"),
        "transactions": Decimal("0.00"),
        "other_charges": Decimal("29.00"),
        "interest_charges": Decimal("45.11"),
        "new_balance": Decimal("2708.32"),
        "minimum_payment": Decimal("235.00"),
        "due_date": date(2012, 8, 15),
    },
    {
        "period": "Jul 21 - Aug 20, 2012",
        "start_date": date(2012, 7, 21),
        "end_date": date(2012, 8, 20),
        "previous_balance": Decimal("2708.32"),
        "payments_credits": Decimal("0.00"),
        "transactions": Decimal("0.00"),
        "other_charges": Decimal("29.00"),
        "interest_charges": Decimal("43.34"),
        "new_balance": Decimal("2501.66"),
        "minimum_payment": Decimal("75.00"),
        "due_date": date(2012, 9, 15),
    },
    {
        "period": "Aug 21 - Sep 20, 2012",
        "start_date": date(2012, 8, 21),
        "end_date": date(2012, 9, 20),
        "previous_balance": Decimal("2501.66"),
        "payments_credits": Decimal("250.00"),
        "transactions": Decimal("0.00"),
        "other_charges": Decimal("0.00"),
        "interest_charges": Decimal("42.84"),
        "new_balance": Decimal("2573.50"),
        "minimum_payment": Decimal("137.00"),
        "due_date": date(2012, 10, 16),
    },
    {
        "period": "Sep 21 - Oct 20, 2012",
        "start_date": date(2012, 9, 21),
        "end_date": date(2012, 10, 20),
        "previous_balance": Decimal("2573.50"),
        "payments_credits": Decimal("0.00"),
        "transactions": Decimal("0.00"),
        "other_charges": Decimal("29.00"),
        "interest_charges": Decimal("44.07"),
        "new_balance": Decimal("2646.57"),
        "minimum_payment": Decimal("216.00"),
        "due_date": date(2012, 11, 15),
    },
    {
        "period": "Oct 21 - Nov 20, 2012",
        "start_date": date(2012, 10, 21),
        "end_date": date(2012, 11, 20),
        "previous_balance": Decimal("2646.57"),
        "payments_credits": Decimal("646.57"),
        "transactions": Decimal("391.65"),
        "other_charges": Decimal("0.00"),
        "interest_charges": Decimal("34.61"),
        "new_balance": Decimal("2426.26"),
        "minimum_payment": Decimal("72.00"),
        "due_date": date(2012, 12, 16),
    },
]


def get_db_connection():
    host = os.environ.get("DB_HOST", "localhost")
    name = os.environ.get("DB_NAME", "almsdata")
    user = os.environ.get("DB_USER", "postgres")
    password = os.environ.get("DB_PASSWORD", "***REDACTED***")
    port = int(os.environ.get("DB_PORT", "5432"))
    return psycopg2.connect(host=host, dbname=name, user=user, password=password, port=port)


def fetch_banking_payments(conn, start_date: date, end_date: date) -> List[Dict]:
    """Find Capital One payments in banking_transactions."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT transaction_id, transaction_date, description, 
                   debit_amount, credit_amount, balance
            FROM banking_transactions
            WHERE transaction_date BETWEEN %s AND %s
              AND (description ILIKE '%%capital one%%' 
                   OR description ILIKE '%%capitalone%%'
                   OR description ILIKE '%%9853%%')
            ORDER BY transaction_date
            """,
            (start_date, end_date),
        )
        return cur.fetchall()


def fetch_receipts(conn, start_date: date, end_date: date) -> List[Dict]:
    """Find Capital One purchase receipts."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id, receipt_date, vendor_name, 
                   gross_amount, gst_amount, net_amount, 
                   description, category
            FROM receipts
            WHERE receipt_date BETWEEN %s AND %s
              AND (description ILIKE '%%capital one%%'
                   OR category ILIKE '%%capital one%%'
                   OR vendor_name ILIKE '%%capital one%%')
            ORDER BY receipt_date
            """,
            (start_date, end_date),
        )
        return cur.fetchall()


def fetch_journal_entries(conn, start_date: date, end_date: date) -> List[Dict]:
    """Find Capital One journal entries."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Try both column name conventions
        cur.execute("SELECT * FROM journal LIMIT 0")
        columns = [desc[0] for desc in cur.description]
        date_col = "transaction_date" if "transaction_date" in columns else "Date"
        
        cur.execute(
            f"""
            SELECT *
            FROM journal
            WHERE "{date_col}" BETWEEN %s AND %s
              AND ("Account" ILIKE '%%capital one%%'
                   OR "Account" ILIKE '%%9853%%'
                   OR "Memo/Description" ILIKE '%%capital one%%')
            ORDER BY "{date_col}"
            """,
            (start_date.isoformat(), end_date.isoformat()),
        )
        return cur.fetchall()


def verify_statement_math(stmt: Dict) -> Tuple[bool, str]:
    """Verify statement balance calculation."""
    calc = (stmt["previous_balance"] 
            - stmt["payments_credits"] 
            + stmt["transactions"]
            + stmt["other_charges"]
            + stmt["interest_charges"])
    
    if calc != stmt["new_balance"]:
        return False, f"Math error: {calc} != {stmt['new_balance']}"
    return True, "OK"


def reconcile_statement(conn, stmt: Dict) -> Dict:
    """Full reconciliation of one statement period."""
    result = {
        "period": stmt["period"],
        "statement_balance": stmt["new_balance"],
        "math_check": None,
        "banking_payments": [],
        "banking_payment_total": Decimal("0"),
        "receipts": [],
        "receipt_total": Decimal("0"),
        "journal_entries": [],
        "journal_debit_total": Decimal("0"),
        "journal_credit_total": Decimal("0"),
        "interest_tracked": False,
        "fees_tracked": False,
        "variances": [],
    }
    
    # 1. Verify statement math
    math_ok, math_msg = verify_statement_math(stmt)
    result["math_check"] = {"status": "PASS" if math_ok else "FAIL", "message": math_msg}
    
    # 2. Find banking payments
    banking = fetch_banking_payments(conn, stmt["start_date"], stmt["end_date"])
    result["banking_payments"] = banking
    for b in banking:
        if b["debit_amount"]:
            result["banking_payment_total"] += Decimal(str(b["debit_amount"]))
    
    # Check payment match
    if stmt["payments_credits"] > 0:
        diff = abs(result["banking_payment_total"] - stmt["payments_credits"])
        if diff > Decimal("1.00"):
            result["variances"].append(
                f"Payment variance: Banking ${result['banking_payment_total']} "
                f"vs Statement ${stmt['payments_credits']} (diff ${diff})"
            )
    
    # 3. Find receipts for purchases
    receipts = fetch_receipts(conn, stmt["start_date"], stmt["end_date"])
    result["receipts"] = receipts
    for r in receipts:
        if r["gross_amount"]:
            result["receipt_total"] += Decimal(str(r["gross_amount"]))
    
    # Check transaction match
    if stmt["transactions"] > 0:
        diff = abs(result["receipt_total"] - stmt["transactions"])
        if diff > Decimal("1.00"):
            result["variances"].append(
                f"Transaction variance: Receipts ${result['receipt_total']} "
                f"vs Statement ${stmt['transactions']} (diff ${diff})"
            )
    
    # 4. Find journal entries
    journal = fetch_journal_entries(conn, stmt["start_date"], stmt["end_date"])
    result["journal_entries"] = journal
    for j in journal:
        if j.get("Debit") or j.get("debit_amount"):
            amt = j.get("Debit") or j.get("debit_amount")
            result["journal_debit_total"] += Decimal(str(amt))
        if j.get("Credit") or j.get("credit_amount"):
            amt = j.get("Credit") or j.get("credit_amount")
            result["journal_credit_total"] += Decimal(str(amt))
    
    # 5. Check interest tracking
    interest_keywords = ["interest", "finance charge"]
    for j in journal:
        desc = (j.get("Memo/Description") or j.get("description") or "").lower()
        if any(kw in desc for kw in interest_keywords):
            result["interest_tracked"] = True
            break
    
    if stmt["interest_charges"] > 0 and not result["interest_tracked"]:
        result["variances"].append(
            f"Interest ${stmt['interest_charges']} not tracked in journal"
        )
    
    # 6. Check fee tracking
    fee_keywords = ["fee", "overlimit", "late", "annual"]
    for j in journal:
        desc = (j.get("Memo/Description") or j.get("description") or "").lower()
        if any(kw in desc for kw in fee_keywords):
            result["fees_tracked"] = True
            break
    
    if stmt["other_charges"] > 0 and not result["fees_tracked"]:
        result["variances"].append(
            f"Fees ${stmt['other_charges']} not tracked in journal"
        )
    
    return result


def main():
    print("=" * 80)
    print("CAPITAL ONE COMPLETE STATEMENT AUDIT (2012)")
    print("Account ending: 9853")
    print("=" * 80)
    
    conn = get_db_connection()
    try:
        all_results = []
        
        for stmt in STATEMENTS:
            print(f"\n{'=' * 80}")
            print(f"Period: {stmt['period']}")
            print(f"Statement Balance: ${stmt['new_balance']}")
            print(f"{'=' * 80}")
            
            result = reconcile_statement(conn, stmt)
            all_results.append(result)
            
            # Print results
            print(f"\n1. STATEMENT MATH: {result['math_check']['status']}")
            print(f"   {result['math_check']['message']}")
            
            print(f"\n2. BANKING PAYMENTS:")
            print(f"   Found: {len(result['banking_payments'])} transactions")
            print(f"   Total: ${result['banking_payment_total']}")
            print(f"   Statement: ${stmt['payments_credits']}")
            if result['banking_payments']:
                for bp in result['banking_payments']:
                    print(f"     - {bp['transaction_date']}: {bp['description']} ${bp['debit_amount']}")
            
            print(f"\n3. RECEIPTS/PURCHASES:")
            print(f"   Found: {len(result['receipts'])} receipts")
            print(f"   Total: ${result['receipt_total']}")
            print(f"   Statement: ${stmt['transactions']}")
            if result['receipts']:
                for r in result['receipts'][:5]:  # Show first 5
                    print(f"     - {r['receipt_date']}: {r['vendor_name']} ${r['gross_amount']}")
                if len(result['receipts']) > 5:
                    print(f"     ... and {len(result['receipts']) - 5} more")
            
            print(f"\n4. JOURNAL ENTRIES:")
            print(f"   Found: {len(result['journal_entries'])} entries")
            print(f"   Debits: ${result['journal_debit_total']}")
            print(f"   Credits: ${result['journal_credit_total']}")
            if result['journal_entries']:
                for j in result['journal_entries'][:5]:
                    desc = j.get("Memo/Description") or j.get("description") or ""
                    debit = j.get("Debit") or j.get("debit_amount") or 0
                    credit = j.get("Credit") or j.get("credit_amount") or 0
                    print(f"     - {desc[:50]}: DR ${debit} CR ${credit}")
                if len(result['journal_entries']) > 5:
                    print(f"     ... and {len(result['journal_entries']) - 5} more")
            
            print(f"\n5. INTEREST CHARGES:")
            print(f"   Statement: ${stmt['interest_charges']}")
            print(f"   Tracked: {'YES' if result['interest_tracked'] else 'NO'}")
            
            print(f"\n6. OTHER CHARGES/FEES:")
            print(f"   Statement: ${stmt['other_charges']}")
            print(f"   Tracked: {'YES' if result['fees_tracked'] else 'NO'}")
            
            if result['variances']:
                print(f"\n[WARN]  VARIANCES FOUND:")
                for v in result['variances']:
                    print(f"   - {v}")
        
        # Summary
        print(f"\n\n{'=' * 80}")
        print("OVERALL SUMMARY")
        print(f"{'=' * 80}")
        
        total_variances = sum(len(r['variances']) for r in all_results)
        math_passes = sum(1 for r in all_results if r['math_check']['status'] == 'PASS')
        
        print(f"Statements audited: {len(all_results)}")
        print(f"Math checks passed: {math_passes}/{len(all_results)}")
        print(f"Total variances: {total_variances}")
        
        if total_variances == 0:
            print("\n[OK] AUDIT RESULT: PASS")
            print("All statements reconcile correctly.")
        else:
            print("\n[WARN]  AUDIT RESULT: REVIEW NEEDED")
            print("Variances require investigation.")
        
        # Exit code
        sys.exit(0 if total_variances == 0 else 1)
        
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
