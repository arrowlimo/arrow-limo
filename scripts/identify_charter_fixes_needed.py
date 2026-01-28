import os
import csv
import psycopg2
import pyodbc
from collections import defaultdict

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

OUT_REPORT = r"L:\limo\reports\CHARTERS_FIELDS_TO_FIX.csv"


def main():
    # Get LMS data
    lms_conn = pyodbc.connect(r'Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\\limo\\backups\\lms.mdb;')
    lms_cur = lms_conn.cursor()
    lms_cur.execute("SELECT Reserve_No, Est_Charge, Balance, Status FROM Reserve ORDER BY Reserve_No")
    lms_data = {}
    for r in lms_cur.fetchall():
        lms_data[r[0]] = {
            "est_charge": float(r[1] or 0),
            "balance": float(r[2] or 0),
            "status": r[3] or "",
        }
    lms_cur.close()
    lms_conn.close()

    # Get ALMS payments totals
    alms_conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    alms_cur = alms_conn.cursor()
    alms_cur.execute("""
        SELECT reserve_number, SUM(amount) as total_paid
        FROM payments
        WHERE reserve_number IS NOT NULL
        GROUP BY reserve_number
    """)
    payments_by_reserve = {}
    for r in alms_cur.fetchall():
        payments_by_reserve[r[0]] = float(r[1] or 0)

    # Get ALMS charters
    alms_cur.execute("""
        SELECT charter_id, reserve_number, total_amount_due, paid_amount, balance, status
        FROM charters
        WHERE reserve_number IS NOT NULL
        ORDER BY reserve_number
    """)
    
    issues = []
    for r in alms_cur.fetchall():
        charter_id = r[0]
        reserve = r[1]
        alms_total = float(r[2] or 0)
        alms_paid = float(r[3] or 0)
        alms_balance = float(r[4] or 0)
        alms_status = r[5] or ""
        
        lms = lms_data.get(reserve)
        actual_paid = payments_by_reserve.get(reserve, 0.0)
        calculated_balance = alms_total - actual_paid
        
        problems = []
        
        # Check total_amount_due vs LMS
        if lms and abs(alms_total - lms["est_charge"]) > 0.01:
            problems.append(f"total_amount_due:{alms_total}→{lms['est_charge']}")
        
        # Check paid_amount vs actual payments
        if abs(alms_paid - actual_paid) > 0.01:
            problems.append(f"paid_amount:{alms_paid}→{actual_paid}")
        
        # Check balance vs calculated
        if abs(alms_balance - calculated_balance) > 0.01:
            problems.append(f"balance:{alms_balance}→{calculated_balance}")
        
        # Check balance vs LMS
        if lms and abs(alms_balance - lms["balance"]) > 0.01:
            if f"balance:{alms_balance}→{calculated_balance}" not in problems:
                problems.append(f"balance:{alms_balance}→LMS:{lms['balance']}")
        
        if problems:
            issues.append({
                "charter_id": charter_id,
                "reserve_number": reserve,
                "status": alms_status,
                "current_total": alms_total,
                "current_paid": alms_paid,
                "current_balance": alms_balance,
                "lms_est_charge": lms["est_charge"] if lms else "",
                "lms_balance": lms["balance"] if lms else "",
                "actual_paid": actual_paid,
                "calculated_balance": round(calculated_balance, 2),
                "issues": " | ".join(problems),
            })
    
    alms_cur.close()
    alms_conn.close()

    # Write report
    os.makedirs(os.path.dirname(OUT_REPORT), exist_ok=True)
    with open(OUT_REPORT, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "charter_id", "reserve_number", "status",
            "current_total", "current_paid", "current_balance",
            "lms_est_charge", "lms_balance",
            "actual_paid", "calculated_balance",
            "issues"
        ]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for issue in issues:
            w.writerow(issue)
    
    # Summary
    total_issues = len(issues)
    needs_total_fix = sum(1 for i in issues if "total_amount_due:" in i["issues"])
    needs_paid_fix = sum(1 for i in issues if "paid_amount:" in i["issues"])
    needs_balance_fix = sum(1 for i in issues if "balance:" in i["issues"])
    
    print(f"Total charters with issues: {total_issues}")
    print(f"  - Needs total_amount_due fix: {needs_total_fix}")
    print(f"  - Needs paid_amount fix: {needs_paid_fix}")
    print(f"  - Needs balance fix: {needs_balance_fix}")
    print(f"\nReport: {OUT_REPORT}")


if __name__ == "__main__":
    main()
