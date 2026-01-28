# Receipt Lookup and Entry Workbook - User Guide

## File Location
`l:\limo\reports\receipt_lookup_and_entry_2012.xlsx`

---

## 📋 What This Workbook Contains

### Sheet 1: "Lookup" (4,701 receipts from 2012)
**Purpose:** Search for existing receipts before adding new ones to avoid duplicates

**Columns:**
- Date
- Vendor
- Amount (gross)
- GST
- Net Amount
- Category
- Description
- Receipt ID
- Bank Account (CIBC/Scotia/None)
- Created From Banking (Yes/No)

### Sheet 2: "Add Receipt"
**Purpose:** Template for entering NEW receipts

---

## 🔍 How to Use the Lookup Sheet

### Method 1: Excel AutoFilter (Recommended)
1. **Click any cell in the header row** (row 1)
2. **Click Data → Filter** (or Ctrl+Shift+L)
3. **Use dropdown arrows** in column headers to filter:
   - Filter by **Vendor** to find all receipts for a specific company
   - Filter by **Date** to see receipts from a specific month
   - Filter by **Amount** to find a specific transaction
   - Filter by **Category** to see all fuel, meals, etc.

**Example - Find all Fas Gas receipts:**
1. Click dropdown arrow on "Vendor" column
2. Type "Fas Gas" in search box
3. Press Enter
4. Excel shows only Fas Gas receipts

### Method 2: Ctrl+F Search
1. Press **Ctrl+F** (Find)
2. Type what you're looking for:
   - Vendor name: "Mohawk"
   - Amount: "150.00"
   - Date: "2012-05-"
3. Click "Find Next" to jump to matches

### Method 3: Sort
1. Click any cell in a column you want to sort
2. Click **Data → Sort A to Z** (or Z to A)
3. Now all similar items are grouped together

**Pro Tip:** Sort by Vendor to see all transactions with the same company together, making it easy to spot patterns or duplicates.

---

## ✏️ How to Add a New Receipt

### Step 1: Check if Receipt Already Exists
**ALWAYS search the Lookup sheet first!**

1. Go to **Lookup sheet**
2. Use AutoFilter or Ctrl+F to search for:
   - The vendor name
   - The exact amount
   - The date
3. **If you find a match** → Don't add it again! (It's already in the database)
4. **If no match found** → Proceed to Step 2

### Step 2: Fill Out the Add Receipt Template

Go to the **"Add Receipt"** sheet and fill in the columns:

| Column | What to Enter | Example |
|--------|---------------|---------|
| **Date** | Receipt date (YYYY-MM-DD) | 2012-05-15 |
| **Vendor** | Company/store name | Fas Gas Plus |
| **Gross Amount** | Total amount paid (with tax) | 125.50 |
| **GST Amount** | 5% GST (if applicable) | 5.98 |
| **Net Amount** | Amount before tax | 119.52 |
| **Category** | Type of expense | fuel |
| **Description** | What it was for | Gas for limo #3 |
| **Business/Personal** | Business or Personal | Business |
| **Cheque Number** | If paid by cheque | 1234 |
| **Notes** | Any additional info | Receipt from glove box |

### Step 3: Calculate GST (if needed)

**For receipts that INCLUDE 5% GST in the total:**
```
Gross Amount: $125.50 (what you paid)
GST = $125.50 × 0.05 / 1.05 = $5.98
Net = $125.50 - $5.98 = $119.52
```

**Quick calculator method:**
- GST = Gross × 0.047619 (rounds to 5%)
- Net = Gross × 0.952381

**For receipts with NO tax:**
- Gross = Net
- GST = 0

### Step 4: Import into Database

Once you've filled out one or more rows in "Add Receipt" sheet:

**Option A: Manual SQL (if you know SQL)**
```sql
INSERT INTO receipts (
    receipt_date, vendor_name, gross_amount, gst_amount, net_amount,
    category, description, business_personal, cheque_number, notes
) VALUES (
    '2012-05-15', 'Fas Gas Plus', 125.50, 5.98, 119.52,
    'fuel', 'Gas for limo #3', 'Business', NULL, 'Receipt from glove box'
);
```

**Option B: Use Import Script (easier)**
```powershell
# Save your Excel file first, then run:
l:\limo\.venv\Scripts\python.exe l:\limo\scripts\import_receipts_from_excel.py --file "reports/receipt_lookup_and_entry_2012.xlsx" --sheet "Add Receipt"
```

---

## 📊 Common Categories

| Category | Examples |
|----------|----------|
| `fuel` | Gas stations (Fas Gas, Centex, Shell, Co-op) |
| `maintenance` | Oil changes, car washes, repairs |
| `office_supplies` | Staples, pens, paper |
| `communication` | Telus, Rogers, phone bills |
| `bank_fees` | NSF charges, service fees, overdraft |
| `insurance` | SGI, Aviva, Jevco |
| `meals_entertainment` | Restaurants, client dinners |
| `rent` | Office or garage rent |
| `equipment_lease` | Vehicle leases (Heffner) |
| `government_fees` | CRA payments, WCB |
| `uncategorized` | When you're not sure |

---

## 🚨 Common Mistakes to Avoid

### ❌ DON'T:
1. **Add a receipt that's already in the Lookup sheet**
   - Always search first!
   
2. **Forget to include GST breakdown**
   - CRA requires separate GST tracking
   
3. **Mix up Gross/Net amounts**
   - Gross = what you paid (includes tax)
   - Net = before tax
   
4. **Leave Business/Personal blank**
   - Default to "Business" for company expenses
   
5. **Use random category names**
   - Stick to the standard categories (see table above)

### ✅ DO:
1. **Search the Lookup sheet before adding anything**
2. **Use consistent vendor names** (e.g., always "Fas Gas", not "FasGas" or "Fas Gas Plus")
3. **Include helpful descriptions** (which vehicle, which trip, etc.)
4. **Save your Excel file after adding receipts**
5. **Double-check your math** (Gross = Net + GST)

---

## 💡 Pro Tips

### Tip 1: Batch Entry
- Fill out multiple receipts at once in "Add Receipt" sheet
- Then import them all together (faster)

### Tip 2: Use Copy-Paste
- If entering many receipts for same vendor:
  1. Fill out first row completely
  2. Copy vendor name, category, etc. to other rows
  3. Just change date, amount, description

### Tip 3: Color Code Your Work
- Highlight rows you've entered in yellow
- After importing, delete or move them
- Keeps track of what's done

### Tip 4: Keep Vendor Names Consistent
- Create a "cheat sheet" of common vendors:
  - Fas Gas (not FAS GAS, Fas Gas Plus, etc.)
  - Canadian Tire (not Can Tire, Cdn Tire)
  - Centex (not CENTEX, Centex Gas)

### Tip 5: Monthly Review
- At end of month, compare your receipts to bank statements
- Use the Lookup sheet to find any transactions that might be missing receipts
- Add receipts for any bank transactions that don't have matches

---

## 🔗 Related Files

| File | Purpose |
|------|---------|
| `2012_receipts_and_banking_UPDATED.xlsx` | See receipts side-by-side with banking |
| `auto_created_receipts_unmatched_banking.xlsx` | Bright yellow receipts needing review |
| `cibc_scotia_split_deposits.xlsx` | Inter-account transfers (bright yellow) |

---

## 🆘 Troubleshooting

**Q: I can't find the AutoFilter dropdown arrows**
- A: Click any cell in row 1, then press Ctrl+Shift+L to toggle filters on

**Q: My search isn't finding anything**
- A: Make sure you're searching the right column
- A: Try searching for partial text (e.g., "Fas" instead of "Fas Gas Plus #4320")

**Q: How do I know if a receipt is already in the database?**
- A: Search the Lookup sheet for the same date + vendor + amount
- A: If all three match, it's probably a duplicate

**Q: What if I don't have the exact GST amount?**
- A: Calculate it using: GST = Gross × 0.047619

**Q: Can I delete rows from the Lookup sheet?**
- A: NO! The Lookup sheet is read-only (for reference only)
- A: Only add to "Add Receipt" sheet

**Q: Where did this data come from?**
- A: Check the "Created From Banking" column
- A: "Yes" = auto-created from bank statements
- A: "No" = manually entered or imported from QuickBooks

---

**Last Updated:** December 9, 2025
**Total Receipts in Lookup:** 4,701 (2012 only)
**Date Range:** January 3, 2012 to December 31, 2012
