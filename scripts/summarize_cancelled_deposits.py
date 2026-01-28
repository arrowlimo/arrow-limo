#!/usr/bin/env python
"""
Summarize cancelled charters with deposits/retainers.

Reports:
- Total count by year
- Aggregate dollar amounts (deposits, retainers, paid)
- Top 10 candidates for non-refundable retainer classification
"""
import csv
from pathlib import Path
from collections import defaultdict
from datetime import datetime


def main():
    p = Path("reports/cancelled_charters_with_deposits.csv")
    if not p.exists():
        print(f"Report not found: {p}")
        return

    rows = list(csv.DictReader(p.open(encoding="utf-8")))
    total = len(rows)
    
    print("=" * 80)
    print("CANCELLED CHARTERS WITH DEPOSITS/RETAINERS SUMMARY")
    print("=" * 80)
    print(f"\nTotal cancelled charters with deposits: {total:,}")
    
    # Aggregate by year
    by_year = defaultdict(list)
    for r in rows:
        date_str = r.get("charter_date", "")
        if date_str and date_str != "":
            try:
                year = datetime.strptime(date_str, "%Y-%m-%d").year
                by_year[year].append(r)
            except:
                by_year["Unknown"].append(r)
        else:
            by_year["Unknown"].append(r)
    
    print("\nBy Year:")
    for year in sorted(by_year.keys()):
        year_rows = by_year[year]
        year_retainer = sum(float(r["retainer_amount"]) for r in year_rows)
        year_deposit = sum(float(r["deposit"]) for r in year_rows)
        year_paid = sum(float(r["paid_amount"]) for r in year_rows)
        print(f"  {year}: {len(year_rows):>3} charters | Retainer: ${year_retainer:>10,.2f} | Deposit: ${year_deposit:>10,.2f} | Paid: ${year_paid:>10,.2f}")
    
    # Dollar totals
    total_retainer = sum(float(r["retainer_amount"]) for r in rows)
    total_deposit = sum(float(r["deposit"]) for r in rows)
    total_paid = sum(float(r["paid_amount"]) for r in rows)
    
    print(f"\nTotal amounts:")
    print(f"  Retainer amounts: ${total_retainer:,.2f}")
    print(f"  Deposit amounts:  ${total_deposit:,.2f}")
    print(f"  Paid amounts:     ${total_paid:,.2f}")
    print(f"  Combined:         ${total_retainer + total_deposit + total_paid:,.2f}")
    
    # Top 10 candidates (by paid_amount)
    print("\n" + "-" * 80)
    print("TOP 10 CANDIDATES FOR NON-REFUNDABLE RETAINER CLASSIFICATION:")
    print("-" * 80)
    sorted_rows = sorted(rows, key=lambda r: float(r["paid_amount"]), reverse=True)[:10]
    print(f"{'Charter':<8} {'Reserve':<8} {'Date':<12} {'Retainer$':<11} {'Deposit$':<11} {'Paid$':<11}")
    for r in sorted_rows:
        print(f"{r['charter_id']:<8} {r['reserve_number']:<8} {r['charter_date']:<12} ${float(r['retainer_amount']):>9,.2f} ${float(r['deposit']):>9,.2f} ${float(r['paid_amount']):>9,.2f}")
    
    print("\n" + "=" * 80)
    print("\nRECOMMENDATIONS:")
    print("- Review top candidates to determine if deposits should be classified as")
    print("  non-refundable retainers and rolled forward as customer credits.")
    print("- Check cancellation policy and booking terms for these charter dates.")
    print("- Consider creating a 'customer_credits' ledger table to track rollover amounts.")
    print("=" * 80)


if __name__ == "__main__":
    main()
