# Quote Generator - Example Output

## Sample Quote (Reserve #019233)

```
═══════════════════════════════════════════════════════════════════════════════

                        Arrow Limousine Services
                   Professional Transportation & Event Services

                        QUOTATION / BOOKING CONFIRMATION

Reservation #: 019233
Quote Date: January 25, 2026
Status: booked

───────────────────────────────────────────────────────────────────────────────

CLIENT INFORMATION
  Client Name:        John Smith
  Account Number:     ACC-001892

───────────────────────────────────────────────────────────────────────────────

SERVICE DETAILS
  Pickup Address:     Calgary International Airport, Calgary, AB T2E 6W5
  Dropoff Address:    The Fairmont Banff Springs, Banff, AB T1L 1J4
  Passenger Count:    4
  Vehicle Type:       Luxury SUV (Cadillac Escalade)

───────────────────────────────────────────────────────────────────────────────

PRICING

  Rate:                                                         $425.00
  ──────────────────────────────────────────────────────────────────────
  Subtotal (before GST):                                       $404.76
  GST (5% included):                                            $20.24
  ──────────────────────────────────────────────────────────────────────
  TOTAL AMOUNT DUE:                                            $425.00
  
  Deposit Required:                                            $106.25 (25%)
  Balance Due:                                                 $318.75

───────────────────────────────────────────────────────────────────────────────

SPECIAL REQUIREMENTS

  Corporate event transportation with professional driver.
  Professional attire required. Client prefers premium water service.

───────────────────────────────────────────────────────────────────────────────

PAYMENT INSTRUCTIONS

  Payment due within 5 business days of service completion.
  We accept: Visa, Mastercard, Amex, Debit, Bank Transfer, Cheque.
  Corporate accounts: Net 30 terms available upon request.

───────────────────────────────────────────────────────────────────────────────

Terms & Conditions: This quote is valid for 30 days from the quote date. 
A 25% deposit is required to confirm booking. Cancellations must be made 48 
hours in advance. For questions, contact Arrow Limousine Services.

═══════════════════════════════════════════════════════════════════════════════

This document was generated on January 25, 2026 at 02:15 PM
Arrow Limousine Services | Professional Transportation

═══════════════════════════════════════════════════════════════════════════════
```

---

## What the User Sees

### 1. Main Quote Generator Window

```
┌─────────────────────────────────────────────────────────────────┐
│ Quote Generator - Past Charters                         [_][□][X]│
├─────────────────────────────────────────────────────────────────┤
│ Search by Reserve #: [019233        ] [Search] [Reset]          │
│ Filter by Status:   [All ▼]                                      │
│                                                                   │
│ Past Charters - Click to select:                                │
│ ┌──────────────────────────────────────────────────────────────┐│
│ │Reserve│Date      │Client        │Pickup         │Dropoff    ││
│ ├────────────────────────────────────────────────────────────────┤
│ │019233 │2026-01-20│John Smith    │YYC Airport    │Banff      ││
│ │019232 │2026-01-19│Mary Johnson  │Stampede Grnd  │Downtown   ││
│ │019231 │2026-01-18│Corp Events   │Office Park    │Telus Conv ││
│ │...    │...       │...           │...            │...        ││
│ └──────────────────────────────────────────────────────────────┘│
│                                                                   │
│    [Preview Quote] [Print Quote] [Export PDF] [Email Quote]    │
└─────────────────────────────────────────────────────────────────┘
```

### 2. Preview Dialog

```
┌──────────────────────────────────────────────────────┐
│ Quote Preview - 019233                      [_][□][X]│
├──────────────────────────────────────────────────────┤
│ [Scrollable HTML Preview Area]                       │
│                                                       │
│   Arrow Limousine Services                           │
│   QUOTATION / BOOKING CONFIRMATION                   │
│                                                       │
│   Reservation #: 019233                              │
│   Quote Date: January 25, 2026                       │
│   Status: booked                                     │
│                                                       │
│   [... full quote preview ...]                       │
│                                                       │
│   TOTAL AMOUNT DUE: $425.00                          │
│   Deposit Required: $106.25                          │
│   Balance Due: $318.75                               │
│                                                       │
│ ┌──────────────────────────────────────────────────┐│
│ │ [Print from Preview] [Export to PDF] [Close]    ││
│ └──────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────┘
```

### 3. After Selecting "Print Quote"

```
┌────────────────────────────────────────┐
│ Print                            [_][□]│
├────────────────────────────────────────┤
│ Printer: [HP LaserJet Pro     ▼]       │
│ Copies:  [1 ]                          │
│ Pages:   ○ All  ○ Range: [1 to 1]     │
│ Size:    [Letter ▼]                    │
│                                        │
│    [Print]  [Cancel]                  │
└────────────────────────────────────────┘

→ Quote prints to physical printer
```

### 4. After Selecting "Export to PDF"

```
┌────────────────────────────────────────┐
│ Save As                        [_][□][X]│
├────────────────────────────────────────┤
│ File name: [Quote_019233.pdf        ]   │
│ Save as type: [PDF Files (*.pdf)    ▼]  │
│                                        │
│ Location: Desktop/Quotes/             │
│                                        │
│    [Save]  [Cancel]                   │
└────────────────────────────────────────┘

→ Quote_019233.pdf saved to your computer
```

---

## Price Calculation Example

Given a charter with `total_amount_due = $425.00`:

**In Database:** Stored as DECIMAL(12,2) = 425.00

**GST Calculation (5% included in total):**
- Total (inclusive): $425.00
- GST Amount: $425.00 × 0.05 / 1.05 = $20.24
- Net (before tax): $425.00 - $20.24 = $404.76
- Verify: $404.76 × 1.05 = $425.00 ✓

**Deposit (25%):**
- Deposit: $425.00 × 0.25 = $106.25
- Balance: $425.00 - $106.25 = $318.75

---

## Features Demonstrated in This Quote

✅ **Dynamic Data Loading**
- Client name from database
- All address details
- Passenger count and vehicle type

✅ **Automatic Calculations**
- GST breakdown (Alberta 5%)
- Deposit calculation (25% in this example)
- Balance due

✅ **Professional Formatting**
- Clear section headers
- Currency formatting ($X.XX)
- Table-like structure
- Footer with timestamp

✅ **Optional Fields**
- Special requirements (if provided)
- Payment instructions (defaults provided)
- Driver name, notes, etc.

✅ **Print-Ready**
- Professional spacing
- No screen UI elements
- Proper margins
- Readable fonts

---

## Print Quality

The quotes are generated with:
- **Font:** Arial (universal, clean, professional)
- **Style:** Professional business document
- **Color:** Black text on white (prints clearly)
- **Margins:** 1 inch (industry standard)
- **Page Size:** Letter (8.5" × 11")
- **Resolution:** High (QPrinter.HighResolution)

---

## Testing the Quote Generator

### Quick Test Steps

1. **Launch the app**
   ```bash
   python -X utf8 desktop_app/main.py
   ```

2. **Navigate to Operations > Quote Generator**
   - You should see the charter table load
   - Defaults to most recent charters (DESC by date)

3. **Search for a charter**
   - Try: `019233` (example reserve number)
   - Or browse the list

4. **Click on a charter**
   - Row highlights
   - Action buttons become enabled

5. **Click "Preview Quote"**
   - HTML dialog opens
   - You see the formatted quote
   - Try "Print from Preview" or "Export to PDF"

6. **Export to PDF**
   - Save dialog appears
   - Default filename: `Quote_[RESERVE_NUMBER].pdf`
   - File saved to your desktop or selected folder

---

## Sample Queries Used

The Quote Generator uses these database queries:

**Load all charters:**
```sql
SELECT 
    charter_id, reserve_number, charter_date, 
    client_display_name, pickup_address, dropoff_address,
    total_amount_due, booking_status, payment_status
FROM charters
WHERE charter_date IS NOT NULL
ORDER BY charter_date DESC
LIMIT 500
```

**Get full charter details for quote:**
```sql
SELECT 
    charter_id, reserve_number, charter_date, charter_date,
    client_display_name, account_number, pickup_address, dropoff_address,
    passenger_count, vehicle_description, driver_name,
    total_amount_due, deposit, rate, driver_percentage, driver_total,
    payment_instructions, special_requirements, booking_status, 
    payment_status, notes
FROM charters
WHERE reserve_number = %s
```

Both queries use proper parameterized statements for SQL injection prevention.

---

**Ready to use!** 🎉

All quotes are generated on-demand from current database data, ensuring they're always up-to-date and accurate.
