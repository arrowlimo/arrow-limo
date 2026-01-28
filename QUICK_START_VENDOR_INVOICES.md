# Quick Start: Vendor Invoice Manager

## Access
**Desktop App → 💰 Accounting & Finance → 📋 Vendor Invoice Manager**

## Your 106.7 Example - Step by Step

### 1. Find Your Vendor
```
Type "106" in Search box
→ Select "106.7" from Vendor dropdown
→ All invoices load automatically
```

### 2. Check Existing Invoices
Look for:
- Invoice #21160
- Invoice #21431  
- Invoice #21739
- Invoice #22072

### 3. Add Missing Invoices (if needed)
Click **➕ Add Invoice** quick action button OR use the "Add Invoice" tab below:
```
Invoice #: 21160
Date: [original 2011 date]
Amount: [amount]
→ Click "Add Invoice to Vendor Account"
```
Repeat for any missing invoices.

### 4. Apply Check #197 Payment
Two ways:

#### Option A: Use Quick Action (EASIEST)
```
1. Select ALL 4 invoices in list (Ctrl+Click each one)
2. Click "💰 Pay Multiple Invoices" button
3. Enter amount: 550.00
4. Dialog opens showing all selected invoices
5. Click "⚡ Auto-Allocate (Oldest First)" 
6. Verify allocations
7. Click OK
```

#### Option B: Use Payment Tab
```
1. Go to "💰 Apply Payment" tab
2. Enter:
   - Payment Date: 01/03/2012
   - Payment Amount: 550.00
   - Payment Method: Check
   - Reference: 197
3. Click "💰 Split Across MULTIPLE Invoices"
4. Select invoices and allocate
5. Click OK
```

### 5. Verify Balance
```
Look at top of invoice list:
Total Invoiced: $X,XXX.XX | Total Paid: $X,XXX.XX | Balance Due: $1,503.25 ✅
```

OR click **📊 View Account Summary** button for full details.

## Key Features

### Multi-Select Invoices
- **Single click** = select one
- **Ctrl+Click** = select multiple
- **Shift+Click** = select range

### Quick Actions (Big Buttons)
- **➕ Add Invoice** - Add new invoice
- **💵 Pay Selected Invoice** - Pay one invoice (select it first)
- **💰 Pay Multiple Invoices** - Split payment across many invoices
- **📊 View Account Summary** - See all history

### Auto-Allocate
The system automatically distributes payments starting with oldest invoices first.

### Color Coding
- **Red balance** = Money owed
- **Green status** = Paid in full
- **✅ Paid** / **❌ Unpaid** indicators

## Common Tasks

### Add WCB Invoice with Late Fee
```
Option 1: Single invoice
Amount: 1050.00
Description: "Invoice #12345 ($1000) + $50 late fee"

Option 2: Separate invoices
Invoice 1: #12345, $1000
Invoice 2: #12345-FEE, $50
```

### Find Banking Transaction
```
1. Go to "🏦 Banking Link" tab
2. Enter amount: 550.00
3. Click "Search Banking Transactions"
4. Double-click matching transaction
5. Banking ID auto-fills
6. Go back to payment tab and apply
```

### View Vendor History
```
Click "📊 View Account Summary" button
→ Shows all invoices with dates, amounts, payments
→ Shows total balance
```

## Tips

✅ **Always use original invoice dates** - Payment dates tracked separately  
✅ **Select multiple = Ctrl+Click** - Not just dragging  
✅ **Auto-allocate first** - Then adjust manually if needed  
✅ **Check balance after** - Verify it matches vendor statement  
✅ **Right-click invoice** - Edit, delete, or view details  

## Shortcuts

- **Double-click invoice** = View full details
- **Right-click invoice** = Menu (edit/delete/view)
- **Ctrl+Click** = Select multiple
- **Esc** = Close dialogs

---

**The layout is now:**
```
┌─────────────────────────────────────────────┐
│ Search for vendor                           │
├─────────────────────────────────────────────┤
│                                             │
│ ALL INVOICES LIST (big table)              │
│ - Shows all invoices for vendor             │
│ - Select multiple with Ctrl+Click          │
│                                             │
├─────────────────────────────────────────────┤
│ [➕ Add] [💵 Pay One] [💰 Pay Many] [📊 View]│  ← QUICK ACTIONS
├─────────────────────────────────────────────┤
│ Tabs: Add Invoice | Apply Payment | etc    │  ← DETAILS
└─────────────────────────────────────────────┘
```

Everything flows top-to-bottom. No confusing side panels!

---
**Last Updated**: December 29, 2025
