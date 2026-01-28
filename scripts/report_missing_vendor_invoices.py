#!/usr/bin/env python3
"""
Report on vendor payments that lack matching invoices.
Helps identify where to enter missing invoices to balance accounts.
"""
import os
import csv
import psycopg2
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

REPORT_DIR = os.path.join("l:\\limo", "reports", "vendor_accounts")
CSV_PATH = os.path.join(REPORT_DIR, "MISSING_INVOICES_BY_VENDOR.csv")
TXT_PATH = os.path.join(REPORT_DIR, "MISSING_INVOICES_SUMMARY.txt")


def main():
    os.makedirs(REPORT_DIR, exist_ok=True)
    conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()

    # Get vendors with negative balances (more payments than invoices)
    cur.execute("""
        SELECT 
            va.account_id,
            va.canonical_vendor,
            va.display_name,
            COALESCE(SUM(val.amount), 0) as net_balance,
            COUNT(CASE WHEN val.entry_type = 'PAYMENT' THEN 1 END) as payment_count,
            COUNT(CASE WHEN val.entry_type = 'INVOICE' THEN 1 END) as invoice_count,
            ABS(COALESCE(SUM(CASE WHEN val.entry_type = 'PAYMENT' THEN val.amount ELSE 0 END), 0)) as total_paid,
            COALESCE(SUM(CASE WHEN val.entry_type = 'INVOICE' THEN val.amount ELSE 0 END), 0) as total_invoiced
        FROM vendor_accounts va
        LEFT JOIN vendor_account_ledger val ON val.account_id = va.account_id
        GROUP BY va.account_id, va.canonical_vendor, va.display_name
        HAVING COALESCE(SUM(val.amount), 0) < -0.01
        ORDER BY COALESCE(SUM(val.amount), 0) ASC
    """)
    
    vendors = cur.fetchall()
    
    # Write CSV detail
    with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'account_id', 'canonical_vendor', 'display_name', 'net_balance',
            'payment_count', 'invoice_count', 'total_paid', 'total_invoiced', 'missing_amount'
        ])
        for row in vendors:
            account_id, canonical, display, balance, pay_cnt, inv_cnt, paid, invoiced = row
            missing = abs(balance)
            writer.writerow([
                account_id, canonical, display or canonical, f"{balance:.2f}",
                pay_cnt, inv_cnt, f"{paid:.2f}", f"{invoiced:.2f}", f"{missing:.2f}"
            ])
    
    # Write summary TXT
    with open(TXT_PATH, 'w', encoding='utf-8') as f:
        f.write("MISSING INVOICES SUMMARY\n")
        f.write("=" * 80 + "\n")
        f.write(f"Report Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"Total Vendors with Negative Balance: {len(vendors)}\n")
        
        if vendors:
            total_missing = sum(abs(row[3]) for row in vendors)
            f.write(f"Total Missing Invoice Amount: ${total_missing:,.2f}\n\n")
            
            f.write("Top 20 Vendors by Missing Amount:\n")
            f.write("-" * 80 + "\n")
            for row in vendors[:20]:
                account_id, canonical, display, balance, pay_cnt, inv_cnt, paid, invoiced = row
                missing = abs(balance)
                f.write(f"{canonical:<40} ${missing:>12,.2f}\n")
                f.write(f"  Payments: {pay_cnt:>3} (${paid:>12,.2f})  |  Invoices: {inv_cnt:>3} (${invoiced:>12,.2f})\n")
                f.write("\n")
    
    cur.close()
    conn.close()
    
    print(f"✅ Missing invoices report generated:")
    print(f"   CSV: {CSV_PATH}")
    print(f"   TXT: {TXT_PATH}")
    print(f"\n   Vendors with missing invoices: {len(vendors)}")
    if vendors:
        total_missing = sum(abs(row[3]) for row in vendors)
        print(f"   Total missing amount: ${total_missing:,.2f}")


if __name__ == "__main__":
    main()
