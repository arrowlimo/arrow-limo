#!/usr/bin/env python3
"""
Vendor Aging Report - 30/60/90+ day analysis of outstanding payables.
"""
import os
import csv
import psycopg2
from datetime import datetime, date, timedelta

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

REPORT_DIR = os.path.join("l:\\limo", "reports", "vendor_accounts")
CSV_PATH = os.path.join(REPORT_DIR, "VENDOR_AGING_REPORT.csv")
TXT_PATH = os.path.join(REPORT_DIR, "VENDOR_AGING_SUMMARY.txt")


def main():
    os.makedirs(REPORT_DIR, exist_ok=True)
    conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    today = date.today()
    days_30 = today - timedelta(days=30)
    days_60 = today - timedelta(days=60)
    days_90 = today - timedelta(days=90)
    
    # Get vendors with positive balances (outstanding payables)
    cur.execute("""
        WITH latest_balance AS (
            SELECT 
                va.account_id,
                va.canonical_vendor,
                va.display_name,
                COALESCE(SUM(val.amount), 0) as balance,
                MAX(val.entry_date) as last_activity
            FROM vendor_accounts va
            LEFT JOIN vendor_account_ledger val ON val.account_id = va.account_id
            GROUP BY va.account_id, va.canonical_vendor, va.display_name
            HAVING COALESCE(SUM(val.amount), 0) > 0.01
        ),
        aging_buckets AS (
            SELECT 
                lb.account_id,
                lb.canonical_vendor,
                lb.display_name,
                lb.balance,
                lb.last_activity,
                COALESCE(SUM(CASE 
                    WHEN val.entry_type = 'INVOICE' AND val.entry_date > %s THEN val.amount 
                    ELSE 0 
                END), 0) as current_0_30,
                COALESCE(SUM(CASE 
                    WHEN val.entry_type = 'INVOICE' AND val.entry_date BETWEEN %s AND %s THEN val.amount 
                    ELSE 0 
                END), 0) as days_31_60,
                COALESCE(SUM(CASE 
                    WHEN val.entry_type = 'INVOICE' AND val.entry_date BETWEEN %s AND %s THEN val.amount 
                    ELSE 0 
                END), 0) as days_61_90,
                COALESCE(SUM(CASE 
                    WHEN val.entry_type = 'INVOICE' AND val.entry_date < %s THEN val.amount 
                    ELSE 0 
                END), 0) as days_90_plus
            FROM latest_balance lb
            LEFT JOIN vendor_account_ledger val ON val.account_id = lb.account_id
            GROUP BY lb.account_id, lb.canonical_vendor, lb.display_name, lb.balance, lb.last_activity
        )
        SELECT * FROM aging_buckets
        ORDER BY balance DESC
    """, (days_30, days_60, days_30, days_90, days_60, days_90))
    
    vendors = cur.fetchall()
    
    # Write CSV
    with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'canonical_vendor', 'display_name', 'total_balance', 'last_activity',
            'current_0_30', 'days_31_60', 'days_61_90', 'days_90_plus'
        ])
        for row in vendors:
            acc_id, canonical, display, balance, last_act, c30, d60, d90, d90p = row
            writer.writerow([
                canonical, display or canonical, f"{balance:.2f}", last_act,
                f"{c30:.2f}", f"{d60:.2f}", f"{d90:.2f}", f"{d90p:.2f}"
            ])
    
    # Write summary
    with open(TXT_PATH, 'w', encoding='utf-8') as f:
        f.write("VENDOR AGING REPORT\n")
        f.write("=" * 100 + "\n")
        f.write(f"Report Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        if vendors:
            total_balance = sum(float(row[3]) for row in vendors)
            total_current = sum(float(row[5]) for row in vendors)
            total_31_60 = sum(float(row[6]) for row in vendors)
            total_61_90 = sum(float(row[7]) for row in vendors)
            total_90p = sum(float(row[8]) for row in vendors)
            
            f.write(f"Total Outstanding Payables: ${total_balance:,.2f}\n")
            f.write(f"  Current (0-30 days):  ${total_current:>12,.2f} ({total_current/total_balance*100:>5.1f}%)\n")
            f.write(f"  31-60 days:           ${total_31_60:>12,.2f} ({total_31_60/total_balance*100:>5.1f}%)\n")
            f.write(f"  61-90 days:           ${total_61_90:>12,.2f} ({total_61_90/total_balance*100:>5.1f}%)\n")
            f.write(f"  90+ days:             ${total_90p:>12,.2f} ({total_90p/total_balance*100:>5.1f}%)\n\n")
            
            f.write(f"Vendors with Outstanding Balances: {len(vendors)}\n\n")
            
            f.write("VENDOR DETAIL\n")
            f.write("-" * 100 + "\n")
            for row in vendors:
                acc_id, canonical, display, balance, last_act, c30, d60, d90, d90p = row
                balance = float(balance)
                c30 = float(c30)
                d60 = float(d60)
                d90 = float(d90)
                d90p = float(d90p)
                f.write(f"{canonical:<45} ${balance:>12,.2f}  Last: {last_act}\n")
                f.write(f"  0-30: ${c30:>10,.2f}  |  31-60: ${d60:>10,.2f}  |  61-90: ${d90:>10,.2f}  |  90+: ${d90p:>10,.2f}\n")
                f.write("\n")
        else:
            f.write("No outstanding payables found.\n")
    
    cur.close()
    conn.close()
    
    print(f"✅ Vendor aging report generated:")
    print(f"   CSV: {CSV_PATH}")
    print(f"   TXT: {TXT_PATH}")
    if vendors:
        total = sum(float(row[3]) for row in vendors)
        print(f"\n   Total Outstanding: ${total:,.2f} across {len(vendors)} vendors")


if __name__ == "__main__":
    main()
