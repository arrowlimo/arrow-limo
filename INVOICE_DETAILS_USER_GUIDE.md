# Invoice Details Tab - User Guide

## What Changed

### Before
Users saw:
- Two confusing fields that looked the same: "Total Amount Due" and "Amount Paid (Calculated)"
- No breakdown of charges
- No visibility into the calculation logic
- "Pending" status that didn't make sense for invoices

### After
Users now see a dedicated **📄 Invoice Details** tab with:

```
┌─────────────────────────────────────────────┐
│ 📄 Invoice Details & Breakdown              │
├─────────────────────────────────────────────┤
│                                             │
│ INVOICE INFORMATION                         │
│ ┌───────────────────────────────────────┐   │
│ │ Invoice Date:  01/15/2026             │   │
│ │ Client:        Acme Corp              │   │
│ │ Driver:        John Smith             │   │
│ │ Vehicle:       LIM-001                │   │
│ └───────────────────────────────────────┘   │
│                                             │
│ 💰 CHARGE BREAKDOWN                         │
│ ┌───────────────────────────────────────┐   │
│ │ Charter Charge:        $500.00        │   │
│ │ Extra Charges:         $0.00          │   │
│ │ Beverage Total:        $150.00        │   │
│ │ GST (5%):              $32.50         │   │
│ └───────────────────────────────────────┘   │
│                                             │
│ 💳 PAYMENT SUMMARY                          │
│ ┌───────────────────────────────────────┐   │
│ │ Subtotal (before GST):  $650.00       │   │
│ │ Total Invoice Amount:   $682.50       │   │
│ │ Amount Paid:            $682.50       │   │
│ │ Amount Due:             $0.00         │   │
│ │ Invoice Status:         CLOSED        │   │
│ └───────────────────────────────────────┘   │
│                                             │
│ ℹ️ Amount Due = (Charter + Extra + Beverage│
│    + GST) - Amount Paid                    │
│    If Amount Paid ≥ Amount Due, status is  │
│    'CLOSED', otherwise shows balance.      │
└─────────────────────────────────────────────┘
```

## Tab Location

The Invoice Details tab appears as the **2nd tab** in the Charter Detail Dialog:

1. Charter Details (basic info)
2. **📄 Invoice Details** ← NEW
3. Orders & Beverages
4. Routing & Charges
5. Payments

## Key Calculations

### Formula
```
Amount Due = (Charter Charge + Extra Charges + Beverage + GST) - Amount Paid
```

### Status Logic
- If **Amount Due ≤ $0.01** → Status = **CLOSED**
- If **Amount Due > $0.01** → Status = **OPEN**

## Example Scenarios

### Scenario 1: Fully Paid Charter
```
Charter Charge:     $500.00
Beverage:           $150.00
Subtotal:           $650.00
GST (5%):           $ 32.50
─────────────────────────────
Total Invoice:      $682.50
Amount Paid:        $682.50
─────────────────────────────
Amount Due:         $  0.00  ✅ CLOSED
```

### Scenario 2: Partial Payment
```
Charter Charge:     $500.00
Beverage:           $ 75.00
Subtotal:           $575.00
GST (5%):           $ 28.75
─────────────────────────────
Total Invoice:      $603.75
Amount Paid:        $300.00
─────────────────────────────
Amount Due:         $303.75  ⏳ OPEN
```

### Scenario 3: No Beverages
```
Charter Charge:     $400.00
Extra Charges:      $ 50.00
Beverage:           $  0.00
Subtotal:           $450.00
GST (5%):           $ 22.50
─────────────────────────────
Total Invoice:      $472.50
Amount Paid:        $472.50
─────────────────────────────
Amount Due:         $  0.00  ✅ CLOSED
```

## Status Field Changes

**Old Status Options:** Pending | Confirmed | In Progress | Completed | Cancelled
**New Status Options:** Confirmed | In Progress | Completed | Closed | Cancelled

- **Confirmed** - Charter has been accepted
- **In Progress** - Charter is currently running
- **Completed** - Charter finished, now in payment/billing stage
- **Closed** - Invoice fully paid (Invoice Status automatically set)
- **Cancelled** - Charter was cancelled

## FAQ

**Q: Why is the Amount Due $0 but status is OPEN?**
A: This means the invoice is fully paid but hasn't been manually marked as "Closed" yet. The Invoice Status field at the bottom shows the automatic calculation.

**Q: Where do Extra Charges come from?**
A: Currently set to $0.00. In the future, this will include things like surcharges, service fees, or waiting time charges that aren't part of the base charter charge.

**Q: Why is GST always 5%?**
A: Alberta sales tax is 5% GST. This is calculated on the subtotal of all charges.

**Q: Can I edit the Invoice Details?**
A: No, all Invoice Details fields are read-only. They're calculated from the charter data, beverages, and payments. Edit those instead.

---

**Last Updated:** January 15, 2026
