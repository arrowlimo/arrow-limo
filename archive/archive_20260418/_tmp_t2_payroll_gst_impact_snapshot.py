import csv
from pathlib import Path
from collections import defaultdict

CSV_PATH = Path(r"l:\limo\data\intake\etransfer_remaining_fuzzy_review.csv")

if not CSV_PATH.exists():
    raise FileNotFoundError(CSV_PATH)

rows = []
with CSV_PATH.open("r", encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f)
    for r in reader:
        rows.append(r)

# Current unresolved scope from review sheet
remaining = [r for r in rows if (r.get("recommended_lane") or "").strip() in {"MANUAL_REVIEW", "VENDOR_REPAYMENT_REVIEW"}]

# Heuristics for impact buckets
# Policy: payroll/source-deduction numbers must come from driver-pay management (PD7/T4),
# not from e-transfer fuzzy/name matches.
vendor_repay = []
vendor_gst_needing_receipt = []
low_material = []

for r in remaining:
    lane = (r.get("recommended_lane") or "").strip()
    amt = float((r.get("debit_amount") or "0").strip() or 0)
    cand = (r.get("candidate_name") or "").strip().upper()
    conf = float((r.get("best_confidence") or "0").strip() or 0)

    if lane == "VENDOR_REPAYMENT_REVIEW":
        vendor_repay.append(r)
        continue

    # GST sensitivity: likely external vendor/service names where receipt/invoice could carry GST.
    if any(tok in cand for tok in ["INC", "LTD", "SERVICE", "PRODUCTION", "TOWING", "FERTILITY", "SKI", "ALERT"]):
        vendor_gst_needing_receipt.append(r)
        continue

    low_material.append(r)


def summarize(label, bucket):
    total = sum(float((r.get("debit_amount") or "0").strip() or 0) for r in bucket)
    print(f"{label}: {len(bucket)} rows | ${total:,.2f}")


print("IMPACT_SNAPSHOT_FROM_REMAINING_REVIEW")
summarize("TOTAL_REMAINING", remaining)
print("PAYROLL_SOURCE_SENSITIVE: 0 rows | $0.00 (policy: PD7/T4 driver-pay management only)")
summarize("VENDOR_REPAYMENT_SENSITIVE", vendor_repay)
summarize("GST_RECEIPT_SENSITIVE", vendor_gst_needing_receipt)
summarize("LOW_MATERIAL_OTHER", low_material)

print("\nTOP_VENDOR_REPAYMENT_SENSITIVE")
for r in sorted(vendor_repay, key=lambda x: float((x.get("debit_amount") or "0") or 0), reverse=True)[:10]:
    print(f"{r.get('candidate_name')}|${r.get('debit_amount')}|{r.get('description','')[:70]}")

print("\nTOP_GST_RECEIPT_SENSITIVE")
for r in sorted(vendor_gst_needing_receipt, key=lambda x: float((x.get("debit_amount") or "0") or 0), reverse=True)[:10]:
    print(f"{r.get('candidate_name')}|${r.get('debit_amount')}|{r.get('description','')[:70]}")

# Also summarize by candidate for fast triage
by_name = defaultdict(lambda: {"count": 0, "amount": 0.0})
for r in remaining:
    name = (r.get("candidate_name") or "").strip().upper()
    by_name[name]["count"] += 1
    by_name[name]["amount"] += float((r.get("debit_amount") or "0").strip() or 0)

print("\nREMAINING_BY_NAME")
for name, info in sorted(by_name.items(), key=lambda kv: (kv[1]["amount"], kv[1]["count"]), reverse=True):
    print(f"{name}|{info['count']}|${info['amount']:,.2f}")
