import os
import csv
from datetime import date

# Reconciliation for The Drive (2011) per user narrative
# No QuickBooks access; produces paperwork-only CSV and summary.

class Invoice:
    def __init__(self, number: str, dt: date, amount: float):
        self.number = number
        self.date = dt
        self.original_amount = round(float(amount), 2)
        self.remaining = round(float(amount), 2)

class Payment:
    def __init__(self, ref: str, dt: date, amount: float, note: str = ""):
        self.ref = ref
        self.date = dt
        self.amount = round(float(amount), 2)
        self.remaining = round(float(amount), 2)
        self.note = note


def allocate_fifo(invoices, payments):
    """Allocate payments to invoices FIFO and return event rows."""
    events = []

    # sort by date just in case
    invoices = sorted(invoices, key=lambda i: i.date)
    payments = sorted(payments, key=lambda p: p.date)

    inv_index = 0
    for p in payments:
        while p.remaining > 0 and inv_index < len(invoices):
            inv = invoices[inv_index]
            if inv.remaining <= 0:
                inv_index += 1
                continue
            applied = min(p.remaining, inv.remaining)
            inv.remaining = round(inv.remaining - applied, 2)
            p.remaining = round(p.remaining - applied, 2)
            events.append({
                "event_date": p.date.isoformat(),
                "event_type": "payment_applied",
                "payment_ref": p.ref,
                "payment_amount": f"{p.amount:.2f}",
                "invoice_number": inv.number,
                "invoice_date": inv.date.isoformat(),
                "applied_amount": f"{applied:.2f}",
                "invoice_remaining_after": f"{inv.remaining:.2f}",
                "note": p.note,
            })
            if inv.remaining <= 0:
                inv_index += 1
        if p.remaining > 0:
            events.append({
                "event_date": p.date.isoformat(),
                "event_type": "payment_unallocated_credit",
                "payment_ref": p.ref,
                "payment_amount": f"{p.amount:.2f}",
                "invoice_number": "",
                "invoice_date": "",
                "applied_amount": f"0.00",
                "invoice_remaining_after": "",
                "note": f"Unallocated credit remaining: {p.remaining:.2f}",
            })

    # Add outstanding invoices snapshot after allocations
    for inv in invoices:
        if inv.remaining > 0:
            events.append({
                "event_date": inv.date.isoformat(),
                "event_type": "invoice_outstanding",
                "payment_ref": "",
                "payment_amount": "",
                "invoice_number": inv.number,
                "invoice_date": inv.date.isoformat(),
                "applied_amount": "",
                "invoice_remaining_after": f"{inv.remaining:.2f}",
                "note": "Outstanding balance awaiting later payment",
            })

    return events, invoices, payments


def write_outputs(events, invoices, payments, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, "THE_DRIVE_2011_INVOICE_CHAIN.csv")
    txt_path = os.path.join(out_dir, "THE_DRIVE_2011_INVOICE_CHAIN_SUMMARY.txt")

    fieldnames = [
        "event_date",
        "event_type",
        "payment_ref",
        "payment_amount",
        "invoice_number",
        "invoice_date",
        "applied_amount",
        "invoice_remaining_after",
        "note",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in events:
            w.writerow(row)

    total_invoices = sum(inv.original_amount for inv in invoices)
    total_payments = sum(p.amount for p in payments)
    total_outstanding = sum(inv.remaining for inv in invoices)

    lines = []
    lines.append("THE DRIVE 2011 INVOICE CHAIN RECONCILIATION")
    lines.append("Source: User-provided narrative; ALMS paperwork-only ledger")
    lines.append("")
    lines.append("Invoices:")
    for inv in invoices:
        lines.append(f"  #{inv.number} on {inv.date.isoformat()} amount {inv.original_amount:.2f} remaining {inv.remaining:.2f}")
    lines.append("")
    lines.append("Payments:")
    for p in payments:
        lines.append(f"  {p.ref} on {p.date.isoformat()} amount {p.amount:.2f} remaining credit {p.remaining:.2f}")
    lines.append("")
    lines.append(f"Totals: invoices={total_invoices:.2f} payments={total_payments:.2f} outstanding={total_outstanding:.2f}")
    lines.append("")
    lines.append("Notes:")
    lines.append("- CHQ 197 covers invoice 21160 fully and leaves a 92.75 credit applied to 21431.")
    lines.append("- 21431 remains with 416.50 outstanding; later payments should target oldest balances first (FIFO).")
    lines.append("- 21739 (509.25) and 22072 (577.50) remained unpaid at that time; mark as outstanding for later matching.")

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return csv_path, txt_path


def main():
    # Hardcoded per user narrative
    invoices = [
        Invoice("21160", date(2011, 1, 31), 457.25),
        Invoice("21431", date(2011, 2, 28), 509.25),
        Invoice("21739", date(2011, 3, 31), 509.25),
        Invoice("22072", date(2011, 4, 30), 577.50),
    ]
    payments = [
        Payment("CHQ 197", date(2011, 2, 1), 550.00, note="From narrative; applied to 21160 then partial to 21431"),
        # Later payments not specified here; can be added when known
    ]

    events, invoices, payments = allocate_fifo(invoices, payments)

    # Output under repo reports
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    out_dir = os.path.join(repo_root, "reports")
    csv_path, txt_path = write_outputs(events, invoices, payments, out_dir)

    print("Written:")
    print(csv_path)
    print(txt_path)


if __name__ == "__main__":
    main()
