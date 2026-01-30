import os
import sys
import psycopg2
from psycopg2.extras import DictCursor
import pandas as pd


def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***'),
    )


def fetch_accounts(cur):
    cur.execute(
        """
        SELECT DISTINCT account_number
        FROM banking_transactions
        WHERE account_number IS NOT NULL
        ORDER BY account_number
        """
    )
    return [r[0] for r in cur.fetchall()]


def fetch_transactions(cur, account_number):
    # Include receipt linkage and heuristic payment→charter linkage
    # Payment linkage heuristic: same date and amount (either debit or credit), optional account match
    cur.execute(
        """
        SELECT 
            bt.transaction_id,
            bt.account_number,
            bt.transaction_date,
            bt.description,
            bt.debit_amount,
            bt.credit_amount,
            bt.balance,
            bt.category,
            /* Receipt linkage */
            bm.match_type,
            bm.match_status,
            bm.match_confidence,
            r.receipt_id,
            r.receipt_date,
            r.vendor_name,
            r.gross_amount,
            r.gst_amount,
            r.net_amount,
            r.category AS receipt_category,
            /* Payment + charter linkage */
            p.payment_id,
            p.payment_date,
            p.reserve_number AS payment_reserve,
            p.amount AS payment_amount,
            p.payment_method,
            c.charter_id,
            c.reserve_number AS charter_reserve,
            c.client_id,
            c.client_id,
            c.total_amount_due,
            c.paid_amount,
            c.balance AS charter_balance
        FROM banking_transactions bt
        LEFT JOIN banking_receipt_matching_ledger bm ON bm.banking_transaction_id = bt.transaction_id
        LEFT JOIN receipts r ON r.receipt_id = bm.receipt_id
        /* Heuristic payment match: date and amount alignment */
        LEFT JOIN payments p ON (
            p.payment_date = bt.transaction_date AND (
                (p.amount IS NOT NULL AND bt.debit_amount IS NOT NULL AND p.amount = bt.debit_amount) OR
                (p.amount IS NOT NULL AND bt.credit_amount IS NOT NULL AND p.amount = bt.credit_amount)
            )
        )
        LEFT JOIN charters c ON c.reserve_number = p.reserve_number
        WHERE bt.account_number = %s
        ORDER BY bt.transaction_date, bt.transaction_id
        """,
        (account_number,)
    )
    cols = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    return pd.DataFrame(rows, columns=cols)


    


def main():
    output = sys.argv[1] if len(sys.argv) > 1 else os.path.join('reports', 'banking_accounts_all_years.xlsx')
    os.makedirs(os.path.dirname(output), exist_ok=True)

    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=DictCursor)
        accounts = fetch_accounts(cur)
        if not accounts:
            print("No accounts found in banking_transactions.")
            return

        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for acct in accounts:
                df = fetch_transactions(cur, acct)
                if df.empty:
                    continue
                # Add computed columns to aid manual verification
                df['type'] = df.apply(lambda r: 'Withdrawal' if (r['debit_amount'] or 0) > 0 else ('Deposit' if (r['credit_amount'] or 0) > 0 else ''), axis=1)
                df['amount'] = df.apply(lambda r: r['debit_amount'] if (r['debit_amount'] or 0) > 0 else (r['credit_amount'] if (r['credit_amount'] or 0) > 0 else 0), axis=1)
                # Flags to assist manual verification
                df['nsf_flag'] = df['description'].str.contains('NSF|NON-SUFFICIENT|RETURNED ITEM', case=False, na=False)
                df['fee_flag'] = df['description'].str.contains('FEE|SERVICE CHARGE|S/C|OVERDRAFT|INTEREST|ACCOUNT FEE|BANK CHARGE', case=False, na=False)
                df['reversal_flag'] = df['description'].str.contains('REVERSAL|CORRECTION|REFUND', case=False, na=False)
                df['preauth_flag'] = df['description'].str.contains('PRE-AUTH|PREAUTH|PAD', case=False, na=False)
                df['mcc_payment_flag'] = df['description'].str.contains('MCC PAYMENT|AMEX BANK OF CANADA', case=False, na=False)
                sheet_name = f"{acct}"
                if len(sheet_name) > 31:
                    sheet_name = f"{str(acct)[:31]}"
                # Ensure at least one visible sheet by writing a minimal sheet if needed
                df.to_excel(writer, sheet_name=sheet_name, index=False)

            # Add Square as a synthetic "bank account" sheet if present in payments
            cur.execute(
                """
                SELECT 
                    payment_id,
                    payment_date,
                    reserve_number,
                    client_id,
                    amount,
                    payment_method,
                    square_payment_id,
                    square_transaction_id,
                    square_card_brand,
                    square_last4,
                    square_customer_name,
                    square_customer_email,
                    square_gross_sales,
                    square_net_sales,
                    square_tip,
                    square_status,
                    notes
                FROM payments
                WHERE square_payment_id IS NOT NULL
                ORDER BY payment_date, payment_id
                """
            )
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
            sq_df = pd.DataFrame(rows, columns=cols)
            if not sq_df.empty:
                # Helper columns
                sq_df['type'] = 'Deposit'  # Square batches are typically deposits
                sq_df['amount_effective'] = sq_df.apply(lambda r: r['square_net_sales'] if r['square_net_sales'] is not None else r['amount'], axis=1)
                sq_df.to_excel(writer, sheet_name='SQUARE', index=False)
        print(f"Exported banking data to {output}")
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == '__main__':
    main()
