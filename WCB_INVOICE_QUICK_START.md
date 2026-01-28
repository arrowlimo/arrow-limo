# Quick Start: WCB Invoice Management

## The Problem You Had
- WCB statements show **running balance** (cumulative total due)
- Each invoice is new, but total kept increasing
- Paying by invoice total amount = overpaying

## The Solution: Running Balance Column

**Before (Confusing):**
```
Invoice   Amount    You might think:
001       $1000     Owe $1000
002       $1200     Owe $1200 (but really you owe $2200 total!)
003       $900      Owe $900 (but actually $3100 total!)
```

**After (Clear):**
```
Invoice   Amount    Running Balance    What You Actually Owe
001       $1000     $1000              $1000 cumulative
002       $1200     $2200              $2200 cumulative  ← This is what WCB shows
003       $900      $3100              $3100 cumulative
```

## Quick Steps to Add WCB Invoice with Overdue Fee

### Step 1: Select WCB
- Type "WCB" in vendor search
- Select from dropdown

### Step 2: Go to ➕ Add Invoice Tab

### Step 3: Fill Invoice Details
```
Invoice Number:    9876543
Invoice Date:      12/30/2024
Amount:            1575.00
Category:          6400 - WCB
Description:       WCB Invoice Dec 2024
```

### Step 4: Split the Fee
✓ Check: "Split this invoice into vendor charge + separate fee"
```
Base Charge Amount:      1500.00  (actual WCB invoice)
Fee/Adjustment Amount:   75.00    (overdue fee)
Fee Type:                Overdue Fee
```

### Step 5: Click ✅ Add Invoice
- Invoice saved with $1575 total
- Fee tracked separately (not counted as income for CRA)
- Running balance updates automatically

## How to Pay

### Single Invoice
1. Select one invoice in list
2. Click 💵 Pay Selected Invoice
3. Enter payment amount
4. Done!

### Multiple Invoices (WCB Lump Sum)
1. Ctrl+Click multiple invoices to select
2. Click 💰 Pay Multiple Invoices
3. Allocates to oldest first automatically
4. Done!

## The Running Balance Column (NEW)

**Dark Blue Bold Column:**
- Shows what you owe up to each invoice
- Matches what WCB shows on their statements
- Updates automatically after each payment
- Helps verify you're paying the right amount

## Fee Split Fields (NEW)

| Field | What to Enter |
|-------|--------------|
| Base Charge | $1500 (the actual invoice amount) |
| Fee Amount | $75 (overdue/interest/penalty) |
| Fee Type | Choose: Overdue Fee, Interest, Penalty, etc. |

✅ Fee is tracked separately for CRA (not counted as income)

## Calculator Button (NEW)

The 🧮 button next to any amount field:
1. Click it
2. Enter your number
3. Click OK
4. Amount auto-fills

Perfect for quick math without leaving the form!

## Amount Field (IMPROVED)

- Now **compact** (doesn't stretch across screen)
- Shows up to **6 digits** (999,999.99 max)
- Comes with built-in **calculator button**
- Takes up less screen real estate

## Pro Tips

💡 **Always check the Running Balance column before paying**
- Match it to WCB's statement to confirm
- Don't pay by individual invoice amounts—use running balance

💡 **Use fee splits for clarity**
- WCB with late fees? Use split
- CRA audit? Fee shows separately
- Future reference? Description shows breakdown

💡 **Calculator saves time**
- Quick totals without calculator app
- Right there in the form
- No context switching

## Common WCB Scenario

**WCB says you owe: $3,100**

You see in the system:
- Invoice Jan: $1000 (Running Balance: $1000)
- Invoice Feb: $1200 (Running Balance: $2200)
- Invoice Mar: $900 (Running Balance: $3100) ← Matches WCB!

**To pay in full:**
- Select all 3 invoices (Ctrl+Click)
- Click 💰 Pay Multiple
- Enter $3,100
- Auto-allocates to oldest first

**Done! No more confusion.**

## Database Side (Automatic)

If you split a fee:
- Base charge: recorded as regular invoice
- Fee amount: recorded in vendor ledger as "ADJUSTMENT" type
- Fee note: "Not counted in income calculation"
- CRA compliant: fees don't inflate income numbers

(All automatic—you just enter the info!)

---

**Next time you add a WCB invoice:**
1. Select WCB ✓
2. Add Invoice tab ✓
3. Fill details ✓
4. Enable fee split ✓
5. Split base + fee ✓
6. Save ✓
7. Running balance shows exact cumulative amount ✓
