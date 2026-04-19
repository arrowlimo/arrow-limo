import csv

p = r"L:\limo\data\intake\unlinked_debits_group_samples.csv"
groups = [
    "TRANSFER_ETRANSFER",
    "WITHDRAWAL_CASH",
    "OTHER_REVIEW",
    "LIQUOR",
    "LEASE_FINANCE",
    "INSURANCE",
]

rows = list(csv.DictReader(open(p, encoding="utf-8")))
print("GROUP_SAMPLES")
for g in groups:
    s = [r for r in rows if r["group"] == g][:5]
    print(f"\n{g} ({len(s)} shown)")
    for x in s:
        print(
            f"{x['transaction_id']}|{x['transaction_date']}|{x['debit_amount']}|"
            f"{x['vendor_extracted'][:30]}|{x['description'][:70]}"
        )
