#!/usr/bin/env python
"""
Summarize overpaid charters with/without refunds analysis.

Reports:
- Count of overpaid charters with refunds present vs not
- Top 10 largest credits with refunds
- Top 10 largest credits without refunds
- Refund percentage and total dollar impact
"""
import csv
from pathlib import Path
from collections import Counter


def main():
    p = Path("reports/overpaid_charters_with_refunds.csv")
    if not p.exists():
        print(f"Report not found: {p}")
        return

    rows = list(csv.DictReader(p.open(encoding="utf-8")))
    total = len(rows)
    
    with_refunds = [r for r in rows if r["refunds_present"] == "True"]
    without_refunds = [r for r in rows if r["refunds_present"] == "False"]
    
    print("=" * 80)
    print("OVERPAYMENT & REFUND ANALYSIS SUMMARY")
    print("=" * 80)
    print(f"\nTotal overpaid charters: {total:,}")
    print(f"  With refunds present:  {len(with_refunds):,} ({100*len(with_refunds)/total:.1f}%)")
    print(f"  Without refunds:       {len(without_refunds):,} ({100*len(without_refunds)/total:.1f}%)")
    
    # Dollar totals
    total_credits_with = sum(abs(float(r["expected_balance"])) for r in with_refunds)
    total_credits_without = sum(abs(float(r["expected_balance"])) for r in without_refunds)
    total_refunds_issued = sum(float(r["refunds_sum"]) for r in with_refunds)
    
    print(f"\nCredit amounts:")
    print(f"  With refunds:     ${total_credits_with:,.2f} (refunds issued: ${total_refunds_issued:,.2f})")
    print(f"  Without refunds:  ${total_credits_without:,.2f}")
    print(f"  Total credits:    ${total_credits_with + total_credits_without:,.2f}")
    
    # Top 10 with refunds
    print("\n" + "-" * 80)
    print("TOP 10 LARGEST CREDITS WITH REFUNDS PRESENT:")
    print("-" * 80)
    with_refunds_sorted = sorted(with_refunds, key=lambda r: abs(float(r["expected_balance"])), reverse=True)[:10]
    print(f"{'Charter':<8} {'Reserve':<8} {'Credit$':<12} {'Refunds$':<12} {'Net Credit$':<12}")
    for r in with_refunds_sorted:
        credit = abs(float(r["expected_balance"]))
        refunds = float(r["refunds_sum"])
        net = credit - refunds
        print(f"{r['charter_id']:<8} {r['reserve_number']:<8} ${credit:>10,.2f} ${refunds:>10,.2f} ${net:>10,.2f}")
    
    # Top 10 without refunds
    print("\n" + "-" * 80)
    print("TOP 10 LARGEST CREDITS WITHOUT REFUNDS:")
    print("-" * 80)
    without_refunds_sorted = sorted(without_refunds, key=lambda r: abs(float(r["expected_balance"])), reverse=True)[:10]
    print(f"{'Charter':<8} {'Reserve':<8} {'Total Due$':<12} {'Paid$':<12} {'Credit$':<12}")
    for r in without_refunds_sorted:
        credit = abs(float(r["expected_balance"]))
        total_due = float(r["total_due"])
        paid = float(r["net_paid"])
        print(f"{r['charter_id']:<8} {r['reserve_number']:<8} ${total_due:>10,.2f} ${paid:>10,.2f} ${credit:>10,.2f}")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
