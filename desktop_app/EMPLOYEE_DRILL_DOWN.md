# Employee Drill-Down System - Complete Guide

## Overview

The **Employee Drill-Down System** provides comprehensive access to all employee data through a single double-click interface. View, edit, and manage everything from PDFs to pepper shaker accountability.

## 🎯 Access Everything with One Click

**Double-click any employee** → Opens 10 comprehensive tabs:

### 1. 👤 Personal Info
- Full name, SIN, date of birth
- Address, phone, email
- Emergency contacts
- Editable fields

### 2. 💼 Employment
- Hire date, position, status
- Is chauffeur/driver checkbox
- Hourly rate, annual salary
- Vacation days (allocated vs used)
- Employment status (Active/Suspended/Terminated/On Leave)

### 3. 🎓 Training & Qualifications
**Training Records Table:**
- Course name, completion date, expiry date
- Certificate numbers, status
- Add/Edit/Delete training records

**Licenses & Certifications Table:**
- Driver's license, Class 1/2/4
- First aid, food handling
- Issue dates, expiry dates
- Status tracking (valid/expired)

### 4. 📄 Documents & Forms
**View/Edit PDF Documents:**
- Employment contracts
- T4, T4A, TD1 tax forms
- Driver licenses (scanned)
- Criminal record checks
- Training certificates
- Medical clearances

**Actions:**
- 📤 Upload new documents
- 👁️ View existing PDFs
- ✏️ **Edit PDF forms** (fill in fields)
- 🗑️ Delete documents

**Generate Forms:**
- T4 Form (auto-populate from pay data)
- T4A Form (contractor payments)
- TD1 Form (tax credits)
- Employment Contract (template fill)

### 5. 💰 Pay & Advances
**Pay History Table:**
- Pay date, gross pay, deductions, net pay
- Number of charters driven
- YTD gross and YTD net running totals

**Pay Advances Table:**
- Date issued, amount, reason
- Repaid amount, balance remaining
- Status (Outstanding/Repaid)

**Actions:**
- ➕ Record new advance
- 💵 Record repayment
- Tracks what's owed

### 6. 🧾 Deductions & Tax
**Standard Deductions:**
- CPP rate (%)
- EI rate (%)
- Income tax rate (%)

**Gratuity/Tips Tracking:**
- Date, charter, gratuity amount
- Split percentage
- Employee share calculation

**Custom Deductions:**
- Uniform purchases
- Union dues
- Garnishments
- Frequency (weekly/biweekly/monthly)
- Start and end dates

### 7. 💵 Floats & Cash
**THE BIG ONE - Float Accountability:**

Shows every cash float issued:
- Date issued, amount, purpose
- Date returned (or blank if still out)
- Receipts submitted (yes/no)
- **Variance** (float - receipts = what's missing)
- Status (Out/Returned/Reconciled/Shortage)

**Summary:**
- Total floats out: $500.00
- Unreturned: $150.00 ⚠️

**Actions:**
- ➕ Issue new float
- ✅ Return float
- 🧾 Submit receipts for reconciliation

**Example:**
```
John Smith issued $200 float on Dec 1 for fuel
Returned Dec 3 with $185 in receipts
Variance: $15 (WHERE DID IT GO?)
Status: Shortage - needs explanation
```

### 8. 🧾 Expenses & Receipt Accountability
**Expense Claims:**
- Date, category (fuel, meals, supplies)
- Amount, receipt attached?
- Receipt number
- Approved status, reimbursed status

**⚠️ Missing Receipts Alert:**
Separate table showing:
- Expenses **WITHOUT receipts**
- Days overdue
- Amount at risk

**Actions:**
- ➕ Submit expense claim
- 📎 Attach receipt image/PDF
- ✅ Approve expense (manager)
- Track reimbursement

**Example:**
```
"John has $45 in expenses with NO receipts"
"Overdue by 12 days"
→ System flags this automatically
```

### 9. 🍔 Lunch Tracking
**What They Had for Lunch:**
- Date, meal type (breakfast/lunch/dinner)
- Location/vendor name
- Cost
- Company reimbursable? (yes/no)
- Notes ("Steak sandwich, fries, coffee")

**Use Cases:**
- Track company-provided meals
- Reimbursable meal expenses
- Per diem tracking
- Client entertainment meals

**Actions:**
- ➕ Add meal entry
- View meal history
- Calculate monthly meal costs

### 10. ⭐ Performance
**Performance Reviews:**
- Review date, rating (1-5)
- Reviewer name
- Strengths noted
- Improvement areas

**Manager Notes:**
- Free-form text area
- Track incidents, praise, concerns
- Private manager-only notes

## 🔍 Pepper vs Fly Shit Tracking

**The Accountability System:**

### Float Tracking Example
```
Issue Float:
  John Smith - $200 for fuel stops

After Trip:
  Receipts submitted: $185
  Variance: $15
  
Question: Where's the $15?
  - Lost receipt? (find it)
  - Personal expense? (pay back)
  - Mathematical error? (recount)
  - Stolen? (incident report)

Status: "Shortage - Awaiting Explanation"
```

### Receipt Tracking Example
```
Missing Receipts Alert:
  
Employee: Sarah Jones
Expenses without receipts:
  1. Dec 5 - Fuel - $62.50 (7 days overdue)
  2. Dec 8 - Supplies - $28.00 (4 days overdue)
  
Total at risk: $90.50
Action required: Submit receipts or explain
```

### The "Pepper Shaker Test"
```
Everything is tracked:
  ✅ $200 float → $185 receipts = $15 variance (FLAGGED)
  ✅ Expense claim with no receipt (FLAGGED)
  ✅ Float unreturned after 30 days (FLAGGED)
  ✅ Receipt submitted late (LOGGED)

Nothing escapes:
  "Did John return the pepper shaker?"
  → Check floats tab → Equipment loaned section
  → Status: Not returned
```

## 📊 List View Filtering

**Employee List Dashboard shows:**
- Employee ID | Name | Position | Hire Date | Status | Chauffeur? | YTD Pay | Unreturned Floats | Missing Receipts

**Filters available:**
- **Name** (text search)
- **Position** (Driver/Dispatcher/Manager/Admin)
- **Status** (Active/Suspended/Terminated)
- **Chauffeurs Only** (checkbox)

**Visual Alerts:**
- 🔴 Red background = Unreturned floats
- 🔴 Red background = Missing receipts

## 🔧 Actions Available

**In Employee Detail Dialog:**
- 💾 Save All Changes
- ❌ Terminate Employment (with confirmation)
- ⏸️ Suspend Employee
- 📤 Upload Documents
- 👁️ View PDFs
- ✏️ Edit PDFs (fill forms)
- ➕ Add training/qualifications
- ➕ Record pay advance
- ➕ Issue cash float
- ✅ Return float with receipts
- ➕ Submit expense claim
- 📎 Attach receipt
- ➕ Add meal entry

## 🎬 User Workflow Examples

### Scenario 1: "Where's the money from last week's float?"
1. Open Employee List
2. Filter to "Chauffeurs Only"
3. Notice John has "$75 Unreturned Floats" (red flag)
4. Double-click John
5. Navigate to "💵 Floats & Cash" tab
6. See table:
   ```
   Dec 15 - $100 - Fuel stops - Not Returned - No Receipts - $100 variance
   Dec 18 - $50 - Bridge tolls - Returned Dec 19 - $45 receipts - $5 variance
   ```
7. Issue: $100 float unreturned, $5 shortage on second float
8. Action: Talk to John, get receipts or repayment

### Scenario 2: "Generate John's T4 for 2024"
1. Double-click John in employee list
2. Navigate to "📄 Documents & Forms" tab
3. Click "T4 Form" button
4. System auto-fills:
   - Box 14: Employment income ($45,230)
   - Box 16: CPP contributions ($2,356)
   - Box 18: EI premiums ($712)
   - Box 22: Income tax deducted ($8,940)
5. PDF opens pre-filled
6. Review, save, print

### Scenario 3: "John needs first aid recertification"
1. Double-click John
2. Navigate to "🎓 Training & Qualifications" tab
3. See expiry date: "First Aid - Expires Dec 30, 2025" (soon!)
4. Click "➕ Add Training"
5. Enter: "First Aid Renewal - Jan 15, 2026"
6. Upload new certificate PDF
7. Status updated to "Valid"

### Scenario 4: "Track lunch expenses for December"
1. Double-click employee
2. Navigate to "🍔 Lunch Tracking" tab
3. View all meals:
   ```
   Dec 1 - Lunch - Tim Hortons - $12.50 - No
   Dec 3 - Lunch - Client Meeting - $45.00 - Yes (Reimbursable)
   Dec 5 - Dinner - Overtime - $28.00 - Yes (Company paid)
   ```
4. Total reimbursable: $73.00
5. Generate expense claim

## 🗄️ Database Tables Used

```sql
employees (employee_id, full_name, sin, hire_date, position, is_chauffeur, ...)
driver_payroll (employee_id, payroll_date, gross_pay, deductions, net_pay, ...)
employee_training (employee_id, course_name, completion_date, expiry_date, ...)
employee_documents (employee_id, doc_type, file_path, upload_date, ...)
employee_advances (employee_id, advance_date, amount, reason, repaid_amount, ...)
employee_floats (employee_id, issue_date, amount, purpose, return_date, receipts_amount, ...)
employee_expenses (employee_id, expense_date, category, amount, receipt_attached, ...)
employee_meals (employee_id, meal_date, meal_type, vendor, cost, reimbursable, ...)
```

## ⚙️ Implementation

**Add to your dashboard:**
```python
from enhanced_employee_widget import EnhancedEmployeeListWidget

# In your tab/menu system:
employee_widget = EnhancedEmployeeListWidget(self.db)
tabs.addTab(employee_widget, "Employees")
```

**That's it!** Double-click functionality is built-in.

## 🚀 Future Enhancements

- [ ] Batch upload receipts (scan multiple)
- [ ] Mobile app for submitting expenses on-the-go
- [ ] Email alerts for missing receipts (7 days overdue)
- [ ] Automatic T4 generation on Jan 1
- [ ] Float approval workflow (manager must approve >$200)
- [ ] Expense approval routing
- [ ] Digital signature on PDF forms
- [ ] OCR receipt scanning (auto-extract amount/date)
- [ ] Payroll integration (auto-deduct advances)

## 📞 Support

All employee drill-down features are **fully integrated** with the existing database. No schema changes required for basic functionality (advanced features like float tracking may need new tables).

**Questions?** Everything is in `employee_drill_down.py` and `enhanced_employee_widget.py`
