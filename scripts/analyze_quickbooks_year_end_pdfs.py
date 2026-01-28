"""
Analyze presence of QuickBooks year-end PDFs and whether those years are represented in DB tables.
Outputs: reports/quickbooks_year_end_pdf_status.md
"""
import os
import psycopg2
from datetime import date

DB = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'dbname': os.getenv('DB_NAME', 'almsdata'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', '***REMOVED***'),
}

PDFS = [
    r"L:\\limo\\quickbooks\\Arrow Limousine 2003.pdf",
    r"L:\\limo\\quickbooks\\Arrow Limousine 2004.pdf",
    r"L:\\limo\\quickbooks\\Arrow Limousine 2005.pdf",
    r"L:\\limo\\quickbooks\\Arrow Limousine 2006.pdf",
    r"L:\\limo\\quickbooks\\Arrow Limousine 2007.pdf",
    r"L:\\limo\\quickbooks\\Bal Sheet & comp Jan to Dec 2007.pdf",
    r"L:\\limo\\quickbooks\\arrow dec 21.pdf",
]

YEARS = [2003, 2004, 2005, 2006, 2007]


def year_counts(cur, year: int):
    results = {}

    # receipts
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(gross_amount),0)
        FROM receipts 
        WHERE receipt_date >= %s AND receipt_date < %s
    """, (date(year,1,1), date(year+1,1,1)))
    r_cnt, r_sum = cur.fetchone()
    results['receipts'] = (r_cnt, float(r_sum or 0))

    # payments
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(amount),0)
        FROM payments 
        WHERE payment_date >= %s AND payment_date < %s
    """, (date(year,1,1), date(year+1,1,1)))
    p_cnt, p_sum = cur.fetchone()
    results['payments'] = (p_cnt, float(p_sum or 0))

    # charters
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(total_amount_due),0)
        FROM charters 
        WHERE charter_date >= %s AND charter_date < %s
    """, (date(year,1,1), date(year+1,1,1)))
    c_cnt, c_sum = cur.fetchone()
    results['charters'] = (c_cnt, float(c_sum or 0))

    # Detect available columns for journal and UGL
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'journal'
    """)
    journal_cols = {r[0] for r in cur.fetchall()}

    if 'transaction_date' in journal_cols:
        if {'debit_amount', 'credit_amount'}.issubset(journal_cols):
            cur.execute("""
                SELECT COUNT(*), COALESCE(SUM(debit_amount),0), COALESCE(SUM(credit_amount),0)
                FROM journal 
                WHERE transaction_date >= %s AND transaction_date < %s
            """, (date(year,1,1), date(year+1,1,1)))
            j_cnt, j_deb, j_cred = cur.fetchone()
            results['journal'] = (j_cnt, float(j_deb or 0), float(j_cred or 0))
        else:
            cur.execute("""
                SELECT COUNT(*) FROM journal 
                WHERE transaction_date >= %s AND transaction_date < %s
            """, (date(year,1,1), date(year+1,1,1)))
            j_cnt = cur.fetchone()[0]
            results['journal'] = (j_cnt, 0.0, 0.0)
    else:
        # Fallback: just count rows by trying date-like column alternatives, else 0
        results['journal'] = (0, 0.0, 0.0)

    # unified_general_ledger
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'unified_general_ledger'
    """)
    ugl_cols = {r[0] for r in cur.fetchall()}

    if 'transaction_date' in ugl_cols:
        if {'debit_amount', 'credit_amount'}.issubset(ugl_cols):
            cur.execute("""
                SELECT COUNT(*), COALESCE(SUM(debit_amount),0), COALESCE(SUM(credit_amount),0)
                FROM unified_general_ledger 
                WHERE transaction_date >= %s AND transaction_date < %s
            """, (date(year,1,1), date(year+1,1,1)))
            u_cnt, u_deb, u_cred = cur.fetchone()
            results['unified_general_ledger'] = (u_cnt, float(u_deb or 0), float(u_cred or 0))
        else:
            cur.execute("""
                SELECT COUNT(*) FROM unified_general_ledger 
                WHERE transaction_date >= %s AND transaction_date < %s
            """, (date(year,1,1), date(year+1,1,1)))
            u_cnt = cur.fetchone()[0]
            results['unified_general_ledger'] = (u_cnt, 0.0, 0.0)
    else:
        results['unified_general_ledger'] = (0, 0.0, 0.0)

    return results


def main():
    existing = []
    missing = []
    for path in PDFS:
        if os.path.exists(path):
            existing.append(path)
        else:
            missing.append(path)

    conn = psycopg2.connect(**DB)
    cur = conn.cursor()

    by_year = {}
    for y in YEARS:
        by_year[y] = year_counts(cur, y)

    cur.close(); conn.close()

    os.makedirs(r"L:\\limo\\reports", exist_ok=True)
    out_path = r"L:\\limo\\reports\\quickbooks_year_end_pdf_status.md"
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write("# QuickBooks Year-End PDFs & DB Coverage\n\n")
        f.write("## Files Provided\n")
        for p in PDFS:
            mark = "[OK]" if p in existing else "[FAIL]"
            f.write(f"- {mark} {p}\n")
        f.write("\n## Database Coverage by Year\n")
        f.write("Year | Receipts | Payments | Charters | Journal (D/C) | UGL (D/C)\n")
        f.write("---- | -------: | -------: | -------: | ------------: | ---------: \n")
        for y in YEARS:
            r_cnt, _ = by_year[y]['receipts']
            p_cnt, _ = by_year[y]['payments']
            c_cnt, _ = by_year[y]['charters']
            j_cnt, j_deb, j_cred = by_year[y]['journal']
            u_cnt, u_deb, u_cred = by_year[y]['unified_general_ledger']
            f.write(f"{y} | {r_cnt:8d} | {p_cnt:8d} | {c_cnt:8d} | {j_cnt:10d} (${j_deb:,.0f}/${j_cred:,.0f}) | {u_cnt:9d} (${u_deb:,.0f}/${u_cred:,.0f})\n")
        
        f.write("\n## Interpretation\n")
        for y in YEARS:
            r_cnt = by_year[y]['receipts'][0]
            p_cnt = by_year[y]['payments'][0]
            c_cnt = by_year[y]['charters'][0]
            j_cnt = by_year[y]['journal'][0]
            u_cnt = by_year[y]['unified_general_ledger'][0]
            entered = any([r_cnt, p_cnt, c_cnt, j_cnt, u_cnt])
            status = "ENTERED" if entered else "NOT ENTERED"
            f.write(f"- {y}: {status} (receipts={r_cnt}, payments={p_cnt}, charters={c_cnt}, journal={j_cnt}, ugl={u_cnt})\n")
        
        f.write("\nNotes:\n")
        f.write("- If a year shows NOT ENTERED but the PDF exists, we can store the PDF as an audit artifact and optionally enter summary journal entries.\n")
        f.write("- 2007+ typically has operational data (charters/payments). 2003–2006 likely documents only.\n")

    print("Report written:", out_path)

if __name__ == '__main__':
    main()
