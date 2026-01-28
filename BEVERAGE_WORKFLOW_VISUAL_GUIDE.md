# 🍷 Beverage Ordering Workflow - Visual Guide

## Complete End-to-End Process

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    DISPATCHER FLOW                                       │
└─────────────────────────────────────────────────────────────────────────┘

STEP 1: Create Charter
┌─────────────────────────────────────────────┐
│ Charter Form                                 │
├─────────────────────────────────────────────┤
│ ✓ Customer Name                             │
│ ✓ Date, Driver, Vehicle                     │
│ ✓ Itinerary                                 │
│ ✓ [SAVE CHARTER]                            │
└─────────────────────────────────────────────┘
                    ↓
STEP 2: Add Beverages (Button in Charter Form)
┌─────────────────────────────────────────────┐
│ "🍷 Add Beverage Items" Button              │
└─────────────────────────────────────────────┘
                    ↓
STEP 3: Select Beverages
┌─────────────────────────────────────────────────────────────────────────┐
│ BEVERAGE SELECTION DIALOG                                               │
├─────────────────────────────────────────────────────────────────────────┤
│ Search: Corona                                                          │
│ Category: All / Beer / Spirits / etc.                                  │
├─────────────────────────────────────────────────────────────────────────┤
│ BEVERAGES (Shows Guest Prices Only)                                    │
│ ┌─────────────────────────────────────────────────────────────────────┐
│ │ Name        | Category | Guest Price | Qty | Add                    │
│ ├─────────────────────────────────────────────────────────────────────┤
│ │ Corona      | Beer     | $5.49       | [24]| [ADD] ← Dispatcher     │
│ │ White Claw  | Seltzers | $3.99       | [12]| [ADD]   picks items   │
│ │ Malibu Rum  | Spirits  | $7.99       | [6] | [ADD]                  │
│ └─────────────────────────────────────────────────────────────────────┘
├─────────────────────────────────────────────────────────────────────────┤
│ CART (Guest Prices Only)                                                │
│ ┌─────────────────────────────────────────────────────────────────────┐
│ │ Corona 355ml      | 24 | $5.49 | $131.76 | [❌]                     │
│ │ White Claw        | 12 | $3.99 | $47.88  | [❌]                     │
│ │ Malibu Rum        | 6  | $7.99 | $47.94  | [❌]                     │
│ └─────────────────────────────────────────────────────────────────────┘
│ Total for Guest: $227.58  (GST Included: $10.85)                       │
│                                                                         │
│ [Clear Cart] [Cancel] [✅ ADD TO CHARTER]                              │
└─────────────────────────────────────────────────────────────────────────┘
                    ↓
STEP 4: Items Saved to Database
┌─────────────────────────────────────────────┐
│ charter_charges table:                      │
│ ├─ charter_id: 12345                        │
│ ├─ charge_type: 'beverage'                  │
│ ├─ Corona 355ml × 24 → $131.76              │
│ ├─ White Claw × 12 → $47.88                 │
│ ├─ Malibu Rum × 6 → $47.94                  │
│ └─ TOTAL: $227.58                           │
└─────────────────────────────────────────────┘
                    ↓
STEP 5: Items Show in Charter Charges Section
┌────────────────────────────────────────────────────────────────┐
│ Charter Form → Charges Section                                 │
├────────────────────────────────────────────────────────────────┤
│ Description        | Qty | Unit Price | Gross | Total         │
├────────────────────────────────────────────────────────────────┤
│ Corona 355ml       | 24  | $5.49      | $5.49 | $131.76       │
│ White Claw Seltzer | 12  | $3.99      | $3.99 | $47.88        │
│ Malibu Rum 375ml   | 6   | $7.99      | $7.99 | $47.94        │
├────────────────────────────────────────────────────────────────┤
│ Net Total: $216.98                                             │
│ GST (5%): $10.85                                               │
│ Gross Total: $227.58                                           │
└────────────────────────────────────────────────────────────────┘
                    ↓
STEP 6: Print Documents (3 Options)

┌──────────────────────────────────────────────────────────────────────────┐
│                    3 PRINT FUNCTIONS (Choose One)                         │
└──────────────────────────────────────────────────────────────────────────┘

┌─────────────────────┐   ┌──────────────────────┐   ┌─────────────────┐
│  DISPATCH ORDER     │   │   GUEST INVOICE      │   │  DRIVER SHEET   │
│  (Internal Costs)   │   │  (Guest Prices Only) │   │   (Verification)│
├─────────────────────┤   ├──────────────────────┤   ├─────────────────┤
│                     │   │                      │   │                 │
│ Charter #12345      │   │ Charter #12345       │   │ Charter #12345  │
│ Customer: John Doe  │   │ Customer: John Doe   │   │ Customer: J Doe │
│ Date: 01/08/2026    │   │ Date: 01/08/2026     │   │ Driver: Bob S   │
│ Driver: Bob Smith   │   │                      │   │ Vehicle: Van 05 │
│                     │   │                      │   │                 │
│ ITEMS (OUR COSTS)   │   │ ITEMS (GUEST PRICES) │   │ LOAD CHECKLIST  │
│ ─────────────────── │   │ ─────────────────── │   │ ─────────────── │
│ ☐ Corona 355ml      │   │ Corona 355ml        │   │ ☐ Corona 355ml  │
│   Qty: 24           │   │   Qty: 24           │   │   Qty: 24       │
│   OUR COST: $3.84   │   │   PRICE: $5.49      │   │   ✓ Verified:__ │
│   TOTAL: $92.16 ←   │   │   TOTAL: $131.76    │   │   Initials: __  │
│    (INTERNAL)       │   │                     │   │                 │
│                     │   │                     │   │ ☐ White Claw    │
│ ☐ White Claw        │   │ White Claw Seltzer  │   │   Qty: 12       │
│   Qty: 12           │   │   Qty: 12           │   │   ✓ Verified:__ │
│   OUR COST: $2.80   │   │   PRICE: $3.99      │   │   Initials: __  │
│   TOTAL: $33.60 ←   │   │   TOTAL: $47.88     │   │                 │
│    (INTERNAL)       │   │                     │   │ ☐ Malibu Rum    │
│                     │   │ Malibu Rum 375ml    │   │   Qty: 6        │
│ ☐ Malibu Rum        │   │   Qty: 6            │   │   ✓ Verified:__ │
│   Qty: 6            │   │   PRICE: $7.99      │   │   Initials: __  │
│   OUR COST: $5.60   │   │   TOTAL: $47.94     │   │                 │
│   TOTAL: $33.60 ←   │   │                     │   │ ─────────────── │
│    (INTERNAL)       │   │ ───────────────────────  │                 │
│                     │   │ Subtotal: $216.98   │   │ I confirm all   │
│ ───────────────────  │   │ GST (5%): $10.85    │   │ items loaded.   │
│ OUR TOTAL COST:     │   │ ─────────────────   │   │                 │
│ $159.36 ← WHAT WE   │   │ TOTAL DUE: $227.58  │   │ Signature: ____ │
│   PAID FOR STOCK    │   │                     │   │ Date: _________ │
│                     │   │ [For Customer] [✓]  │   │ Temperature: __ │
│ ☐ Verification at   │   │                     │   │                 │
│   vehicle load:     │   │                     │   │ [Dispatch Use]  │
│ 1. Corona 355ml ✓   │   │                     │   │                 │
│ 2. White Claw ✓     │   │                     │   │                 │
│ 3. Malibu Rum ✓     │   │                     │   │                 │
│                     │   │                     │   │                 │
│ Driver Sig: ___     │   │                     │   │                 │
│ Date: ______        │   │                     │   │                 │
│ Time: ______        │   │                     │   │                 │
│                     │   │                     │   │                 │
│ [Dispatch Only]     │   │ [For Customer] [✓]  │   │ [Driver Signup] │
│ [Contains Costs]    │   │ [NO Costs Shown]    │   │ [Verification]  │
│                     │   │                     │   │                 │
└─────────────────────┘   └──────────────────────┘   └─────────────────┘
      ↓                            ↓                         ↓
   PRINT/COPY                  PRINT/COPY              PRINT/COPY
   (for buying)               (for customer)        (for driver)


┌──────────────────────────────────────────────────────────────────────────┐
│                         SECURITY FEATURES                                 │
└──────────────────────────────────────────────────────────────────────────┘

✓ DISPATCH ORDER       → Shows $3.84, $2.80, $5.60 costs → DISPATCHER ONLY
✓ GUEST INVOICE        → Shows $5.49, $3.99, $7.99 prices → SAFE FOR GUEST
✓ DRIVER SHEET         → No costs at all → NEUTRAL VERIFICATION
✓ DATABASE             → Stores guest price for billing accuracy
✓ ACCESS CONTROL       → Costs visible only in dispatcher application


┌──────────────────────────────────────────────────────────────────────────┐
│                    BEVERAGE MANAGEMENT TAB                               │
└──────────────────────────────────────────────────────────────────────────┘

For internal reporting/analysis (NOT for dispatcher ordering):

⚙️ Admin & Settings → 🍷 Beverage Management
├── 📦 Catalog & Pricing
│   ├── View all products
│   ├── Add new products
│   ├── Check margins (30% good, 20% fair, <20% low)
│   └── Current: 1,179 products loaded
│
├── 📊 Bulk Adjustments
│   ├── Filter by category
│   ├── Raise/lower prices by % or fixed amount
│   ├── Preview before applying
│   └── Adjust costs proportionally (optional)
│
├── 💰 Cost & Margins
│   ├── Dashboard stats
│   ├── See profit per item
│   ├── Identify low-margin products
│   └── Export margin reports
│
└── 📅 Charter Costs
    ├── Filter by date range
    ├── Group by: Charter / Month / Year / Driver / Category
    ├── See cost vs. revenue per grouping
    └── Export detailed reports

(This is for ACCOUNTING/MANAGEMENT review - NOT dispatcher use)


┌──────────────────────────────────────────────────────────────────────────┐
│                      MARGIN EXAMPLE                                       │
└──────────────────────────────────────────────────────────────────────────┘

What Dispatcher SEES (public):
  Corona 355ml: $5.49 ✓

What's HIDDEN from Guest:
  Our Cost: $3.84 (40% margin)
  
What ONLY Management/Accounting SEES (in Beverage Management tab):
  Unit Price: $5.49
  Our Cost: $3.84
  Margin: $1.65
  Margin %: 30.1%
  Low Margin Alert: None (good!)

This separation ensures:
✓ Guest only sees fair price
✓ Dispatcher can order efficiently
✓ Management can analyze profitability
✓ Costs stay confidential


┌──────────────────────────────────────────────────────────────────────────┐
│                    KEY BENEFITS                                           │
└──────────────────────────────────────────────────────────────────────────┘

1. ✓ Full cost tracking (what we paid suppliers)
2. ✓ Transparent pricing (what customers pay)
3. ✓ Driver accountability (signed verification)
4. ✓ Internal reporting (Beverage Management tab)
5. ✓ Database integration (charter_charges table)
6. ✓ Margin analysis (30% good, 20% fair, <20% low)
7. ✓ Bulk adjustments (for pricing changes)
8. ✓ Security (costs hidden from guest copies)

═══════════════════════════════════════════════════════════════════════════
Date: January 8, 2026 | Status: ✅ COMPLETE | Testing: Ready
═══════════════════════════════════════════════════════════════════════════
