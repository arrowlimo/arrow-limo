from datetime import datetime, date
from pathlib import Path
from decimal import Decimal
import csv

import psycopg2
from psycopg2.extras import RealDictCursor

DB = dict(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
OUT_DIR = Path(r'l:\limo\data\audit')
OUT_DIR.mkdir(parents=True, exist_ok=True)
STAMP = datetime.now().strftime('%Y%m%d_%H%M%S')
YEAR = 2012


def money(v):
    return Decimal(str(v or 0))


def write_csv(path: Path, headers, rows):
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)


def main():
    conn = psycopg2.connect(**DB)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Trial Balance from general_ledger
    cur.execute(
        """
        SELECT
            gl.account AS account_code,
            COALESCE(NULLIF(gl.account_name,''), coa.account_name, '(unnamed)') AS account_name,
            COALESCE(NULLIF(gl.account_type,''), coa.account_type, '(unknown)') AS account_type,
            SUM(COALESCE(gl.debit,0)) AS total_debit,
            SUM(COALESCE(gl.credit,0)) AS total_credit,
            SUM(COALESCE(gl.debit,0) - COALESCE(gl.credit,0)) AS net_dr_cr,
            COUNT(*) AS txn_count
        FROM general_ledger gl
        LEFT JOIN chart_of_accounts coa ON coa.account_code = gl.account
        WHERE EXTRACT(YEAR FROM gl.date) = %s
        GROUP BY gl.account, COALESCE(NULLIF(gl.account_name,''), coa.account_name, '(unnamed)'), COALESCE(NULLIF(gl.account_type,''), coa.account_type, '(unknown)')
        ORDER BY gl.account
        """,
        (YEAR,),
    )
    trial_rows = cur.fetchall()

    tb_csv = OUT_DIR / f'trial_balance_{YEAR}_{STAMP}.csv'
    write_csv(
        tb_csv,
        ['account_code', 'account_name', 'account_type', 'total_debit', 'total_credit', 'net_dr_cr', 'txn_count'],
        [
            [
                r['account_code'], r['account_name'], r['account_type'],
                float(money(r['total_debit'])), float(money(r['total_credit'])), float(money(r['net_dr_cr'])), int(r['txn_count'])
            ]
            for r in trial_rows
        ],
    )

    total_debit = sum(money(r['total_debit']) for r in trial_rows)
    total_credit = sum(money(r['total_credit']) for r in trial_rows)
    trial_diff = total_debit - total_credit

    # Profit & Loss based on ledger account classification
    pnl_revenue = Decimal('0')
    pnl_expense = Decimal('0')
    pnl_other = Decimal('0')
    pnl_detail = []

    for r in trial_rows:
        code = str(r['account_code'] or '')
        a_type = str(r['account_type'] or '').lower()
        credits = money(r['total_credit'])
        debits = money(r['total_debit'])
        net = money(r['net_dr_cr'])

        cls = 'other'
        amount = Decimal('0')

        if 'income' in a_type or 'revenue' in a_type or code.startswith('4'):
            cls = 'revenue'
            amount = credits - debits
            pnl_revenue += amount
        elif 'expense' in a_type or 'cost' in a_type or code.startswith(('5', '6', '7', '8')):
            cls = 'expense'
            amount = debits - credits
            pnl_expense += amount
        else:
            cls = 'other'
            amount = net
            pnl_other += amount

        pnl_detail.append((code, r['account_name'], r['account_type'], cls, amount, int(r['txn_count'])))

    net_income = pnl_revenue - pnl_expense

    pnl_csv = OUT_DIR / f'profit_loss_{YEAR}_{STAMP}.csv'
    write_csv(
        pnl_csv,
        ['account_code', 'account_name', 'account_type', 'class', 'amount', 'txn_count'],
        [[a, b, c, d, float(e), f] for a, b, c, d, e, f in pnl_detail],
    )

    # GST / ITC summary
    cur.execute(
        """
        SELECT
            COUNT(*) AS charter_count,
            COALESCE(SUM(COALESCE(total_amount_due,0)),0) AS charter_gross,
            COALESCE(SUM(CASE WHEN COALESCE(total_amount_due,0) > 0 THEN (total_amount_due - total_amount_due / 1.05) ELSE 0 END),0) AS gst_collected_charters
        FROM charters
        WHERE EXTRACT(YEAR FROM charter_date) = %s
          AND COALESCE(status,'') <> 'cancelled'
        """,
        (YEAR,),
    )
    c = cur.fetchone()

    cur.execute(
        """
        SELECT
            COALESCE(SUM(CASE WHEN COALESCE(revenue,0) > 0 THEN COALESCE(gst_amount,0) ELSE 0 END),0) AS gst_collected_receipts_revenue,
            COALESCE(SUM(CASE WHEN COALESCE(gross_amount,0) > 0
                                AND COALESCE(revenue,0) = 0
                                AND COALESCE(exclude_from_reports,false) = false
                                AND COALESCE(is_nsf,false) = false
                              THEN COALESCE(gst_amount,0) ELSE 0 END),0) AS itc_receipts,
            COUNT(*) FILTER (WHERE COALESCE(gross_amount,0) > 0
                                AND COALESCE(revenue,0) = 0
                                AND COALESCE(exclude_from_reports,false) = false
                                AND COALESCE(is_nsf,false) = false) AS itc_receipt_count
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = %s
        """,
        (YEAR,),
    )
    g = cur.fetchone()

    gst_collected_total = money(c['gst_collected_charters']) + money(g['gst_collected_receipts_revenue'])
    itc_total = money(g['itc_receipts'])
    net_gst_payable = gst_collected_total - itc_total

    gst_csv = OUT_DIR / f'gst_itc_summary_{YEAR}_{STAMP}.csv'
    write_csv(
        gst_csv,
        ['year', 'charter_count', 'charter_gross', 'gst_collected_charters', 'gst_collected_receipts_revenue', 'gst_collected_total', 'itc_receipts', 'itc_receipt_count', 'net_gst_payable_estimate'],
        [[YEAR, int(c['charter_count'] or 0), float(money(c['charter_gross'])), float(money(c['gst_collected_charters'])), float(money(g['gst_collected_receipts_revenue'])), float(gst_collected_total), float(itc_total), int(g['itc_receipt_count'] or 0), float(net_gst_payable)]],
    )

    # Journal entry / general journal summaries
    cur.execute(
        """
        SELECT
            COALESCE(transaction_type,'(null)') AS transaction_type,
            COUNT(*) AS txn_count,
            SUM(COALESCE(debit,0)) AS total_debit,
            SUM(COALESCE(credit,0)) AS total_credit
        FROM general_ledger
        WHERE EXTRACT(YEAR FROM date) = %s
        GROUP BY COALESCE(transaction_type,'(null)')
        ORDER BY txn_count DESC
        """,
        (YEAR,),
    )
    journal_types = cur.fetchall()

    journal_type_csv = OUT_DIR / f'journal_entry_types_{YEAR}_{STAMP}.csv'
    write_csv(
        journal_type_csv,
        ['transaction_type', 'txn_count', 'total_debit', 'total_credit'],
        [[r['transaction_type'], int(r['txn_count']), float(money(r['total_debit'])), float(money(r['total_credit']))] for r in journal_types],
    )

    cur.execute(
        """
        SELECT
            id, date, transaction_type, num, account, account_name, memo_description, debit, credit, source_file
        FROM general_ledger
        WHERE EXTRACT(YEAR FROM date) = %s
          AND (
                                COALESCE(transaction_type,'') ILIKE '%%journal%%'
                OR COALESCE(num,'') ILIKE 'GJ%%'
                                OR COALESCE(memo_description,'') ILIKE '%%general journal%%'
          )
        ORDER BY date, id
        """,
        (YEAR,),
    )
    gj_rows = cur.fetchall()

    gj_csv = OUT_DIR / f'general_journal_entries_{YEAR}_{STAMP}.csv'
    write_csv(
        gj_csv,
        ['id', 'date', 'transaction_type', 'num', 'account', 'account_name', 'memo_description', 'debit', 'credit', 'source_file'],
        [[r['id'], r['date'], r['transaction_type'], r['num'], r['account'], r['account_name'], r['memo_description'], float(money(r['debit'])), float(money(r['credit'])), r['source_file']] for r in gj_rows],
    )

    summary = OUT_DIR / f'financial_report_pack_{YEAR}_{STAMP}.txt'
    summary.write_text(
        '\n'.join([
            f'FINANCIAL REPORT PACK - {YEAR}',
            f'Generated: {datetime.now().isoformat(timespec="seconds")}',
            '',
            '1) Profit & Loss',
            f'  Revenue: ${pnl_revenue:,.2f}',
            f'  Expenses: ${pnl_expense:,.2f}',
            f'  Net Income: ${net_income:,.2f}',
            f'  Detail CSV: {pnl_csv}',
            '',
            '2) Trial Balance',
            f'  Accounts: {len(trial_rows)}',
            f'  Total Debits: ${total_debit:,.2f}',
            f'  Total Credits: ${total_credit:,.2f}',
            f'  Debit-Credit Difference: ${trial_diff:,.2f}',
            f'  Detail CSV: {tb_csv}',
            '',
            '3) GST / ITC Summary',
            f'  GST Collected (charters + receipt revenue): ${gst_collected_total:,.2f}',
            f'  ITC from Receipts: ${itc_total:,.2f}',
            f'  Net GST Payable (estimate): ${net_gst_payable:,.2f}',
            f'  Detail CSV: {gst_csv}',
            '',
            '4) Journal Entries / General Journal',
            f'  General Journal-like rows: {len(gj_rows)}',
            f'  Transaction Type CSV: {journal_type_csv}',
            f'  General Journal CSV: {gj_csv}',
        ]),
        encoding='utf-8'
    )

    cur.close()
    conn.close()

    print(f'SUMMARY: {summary}')
    print(f'P_AND_L_CSV: {pnl_csv}')
    print(f'TRIAL_BALANCE_CSV: {tb_csv}')
    print(f'GST_ITC_CSV: {gst_csv}')
    print(f'JOURNAL_TYPE_CSV: {journal_type_csv}')
    print(f'GENERAL_JOURNAL_CSV: {gj_csv}')


if __name__ == '__main__':
    main()
