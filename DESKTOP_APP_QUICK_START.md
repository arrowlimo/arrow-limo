# Quick Start Guide - Desktop App Testing

## Start the App

```bash
cd l:\limo
python -X utf8 desktop_app/main.py
```

**Expected Output:**
```
✅ Fleet Management loaded 26 vehicles
✅ Driver Performance loaded 993 drivers
✅ Financial Dashboard: Revenue $9.57M, Expenses $9.29M
✅ Payment Reconciliation loaded 50 outstanding charters
✅ Vehicle Fleet Cost Analysis loaded 26 vehicles
✅ Fuel Efficiency loaded 26 vehicles
✅ Fleet Age Analysis loaded 26 vehicles
✅ Driver Pay Analysis loaded 993 drivers
✅ Main window created successfully
✅ Navigator tab should be available
```

---

## What You'll See

### When App Opens
1. **Navigator Tab** (First tab) - Dashboard search & browse
2. **Reports Tab** (Second tab) - Pre-built reports
3. **Other Tabs** - Charters, Vehicles, Employees, etc.

### Core Dashboard Widgets (Available Now)

| Widget | Tab | What It Shows |
|--------|-----|---------------|
| Fleet Management | Navigator → Fleet | 26 vehicles + costs |
| Driver Performance | Navigator → Core → Drivers | 993 drivers + payroll |
| Financial Dashboard | Navigator → Core → Financial | Revenue vs Expenses |
| Vehicle Analytics | Navigator → Fleet → Analytics | Vehicle metrics |
| Payment Reconciliation | Navigator → Finance → Payments | Outstanding charters |

---

## Testing Steps

### Step 1: Verify App Startup
- [ ] App launches without errors
- [ ] All 8 core widgets show ✅ in console
- [ ] Navigator tab is visible and clickable

### Step 2: Test Navigator Tab
1. Click **Navigator** tab
2. You should see a dashboard menu with categories:
   - 🏢 Core Operations
   - 📊 Operations & Scheduling
   - 🔮 Predictive Analytics
   - ⚡ Optimization
   - 👥 Customer Experience
   - 📈 Analytics
   - 🤖 Machine Learning
3. Expand **Core Operations**
4. You should see **Fleet Management** category

### Step 3: Test Fleet Management Widget
1. Expand **Fleet Management** in Navigator
2. Click on **Fleet Management** (first item)
3. Click **Launch Dashboard** button
4. A new tab should open showing:
   - Title: "🚐 Fleet Management"
   - Table with 26 rows (vehicles)
   - Columns: Vehicle, Make/Model, Year, Fuel $, Maint $, Total $
5. All values should be numbers (not blank)

### Step 4: Test Data Display
1. Pick 3 different widgets from Navigator:
   - Vehicle Analytics
   - Driver Performance
   - Financial Dashboard
2. Launch each one
3. For each, verify:
   - Title displays correctly
   - Data table/summary shows data (not blank rows)
   - No error messages
   - Numbers are formatted with $ and commas

### Step 5: Test Favorites (Optional)
1. In Navigator, select a widget
2. Click ⭐ **Add to Favorites**
3. Click "⭐ Favorites" tab at top of Navigator
4. You should see your favorited widget listed
5. Click it to launch

---

## Expected Results

### ✅ Success Criteria
- [ ] App launches without crashing
- [ ] All 8 core widgets load successfully
- [ ] Navigator tab opens and displays categories
- [ ] Clicking widgets launches them in new tabs
- [ ] Tables display data (26 vehicles, 993 drivers, etc.)
- [ ] No "Column not found" errors
- [ ] Numbers are formatted correctly ($XXX.XX)

### ❌ Failure Indicators
- [ ] Blank tables with no data
- [ ] SQL errors about missing columns
- [ ] Widgets failing to launch
- [ ] Navigator menu not working
- [ ] Data showing as "0.00" or NULL unexpectedly

---

## Data Validation

### Sample Data You Should See

**Fleet Management Widget (26 vehicles):**
- H014606 | Unknown Camry | 2018 | $0.00 | $0.00 | $0.00
- HA29120 | Ford E350 | 2014 | $0.00 | $0.00 | $0.00
- L-05 | Lincoln Town Car | 1996 | $0.00 | $0.00 | $0.00

**Driver Performance Widget (993 drivers):**
- Shows list of drivers with Charters, Gross Pay, Net Pay
- Top drivers by gross pay

**Financial Dashboard:**
- Revenue: $9,569,793.90
- Expenses: $9,293,097.21
- Profit: $276,696.69

---

## Troubleshooting

### Problem: App crashes on startup
**Solution:** Check console output for specific error, report with full traceback

### Problem: Navigator tab not visible
**Solution:** Click on the first tab - it should say "🗂️ Navigator"

### Problem: Widgets show empty tables
**Solution:** This was just fixed - if you see this, report the widget name

### Problem: "Column X not found" errors
**Solution:** These have all been fixed, but if you see new ones, report them

### Problem: App is slow
**Solution:** This is normal first time - widgets are loading 100+ records

---

## Sample Test Cases

### Test Case 1: Happy Path
1. Start app
2. Click Navigator tab
3. Expand "Core Operations"
4. Click "Fleet Management"
5. Click "Launch Dashboard"
6. **Expected:** New tab opens with 26 vehicles listed

### Test Case 2: Multiple Widgets
1. Launch Fleet Management
2. Launch Driver Performance
3. Launch Financial Dashboard
4. **Expected:** 3 tabs open, each with data visible

### Test Case 3: Favorites
1. In Navigator, select any widget
2. Click "⭐ Add to Favorites"
3. Click "⭐ Favorites" tab
4. **Expected:** Widget appears in favorites

### Test Case 4: Search
1. In Navigator search box, type "Fleet"
2. **Expected:** Fleet widgets appear
3. Search "Driver"
4. **Expected:** Driver widgets appear

---

## Quick Reference

| Action | How To |
|--------|--------|
| **Start App** | `python -X utf8 desktop_app/main.py` |
| **Open Navigator** | Click first tab (🗂️) |
| **Launch Widget** | Select widget, click ▶ Launch Dashboard |
| **Add Favorite** | Select widget, click ⭐ |
| **View Favorites** | Click ⭐ Favorites tab in Navigator |
| **Search** | Type in search box, press Enter |
| **Exit** | Close window or Ctrl+Q |

---

## Contact for Issues

If you encounter any problems:
1. Note the widget name
2. Copy the error message from console
3. Take screenshot of the issue
4. Report with steps to reproduce

---

**Last Updated:** December 24, 2025  
**Status:** ✅ Ready for Testing  
**Support:** Contact Development Team
