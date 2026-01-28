# 🍷 Beverage Management Widget - User Guide

## Overview
The **Beverage Management Widget** is a comprehensive tool for managing beverage products, pricing, and cost tracking. It's accessible from the **Admin & Settings** tab → **Beverage Management**.

## Features & Tabs

### 📦 Tab 1: Catalog & Pricing
**Purpose:** View, search, add, and manage beverage products

**What Dispatchers Can Do:**
- **Search products** by name or category to quickly find existing items
- **View all current prices:** unit price (what you charge customers), wholesale cost (what Arrow Limousine paid), deposit amounts
- **See profit margin** for each item (green = good, orange = fair, red = low)
- **Add new products** that aren't in the database yet:
  - Enter product name (e.g., "Corona Extra 355ml")
  - Select category (Beer, Spirits, Wine, RTD, Hard Seltzers, etc.)
  - Enter unit price (retail/sell price)
  - Either manually enter cost OR click "Calculate @ 70%" (automatically sets cost to 70% of retail)
  - Enter deposit amount if applicable
  - Click ✅ Add Product

**When to Use:**
- When adding new beverage brands from Wine and Beyond
- When you notice a product missing from the system
- When restocking a new variety

---

### 📊 Tab 2: Bulk Adjustments
**Purpose:** Quickly adjust prices across multiple products

**What Dispatchers Can Do:**
- **Filter by category** (e.g., adjust only Beer prices)
- **Choose adjustment type:**
  - Percentage Increase (e.g., raise all prices by 5%)
  - Percentage Decrease (e.g., lower all prices by 3%)
  - Fixed Amount Add (e.g., add $0.50 to all)
  - Fixed Amount Subtract (e.g., subtract $0.25 from all)
- **Option to adjust cost too:** Keep margins consistent when raising/lowering prices
- **Preview changes** before applying (shows old vs. new prices for each product)
- **Apply all at once** with one click

**When to Use:**
- When wholesale costs increase, need to raise retail prices
- Seasonal pricing adjustments
- Promotional pricing (temporary decrease)
- When supplier gives you better costs, want to improve margins

**Example:** If wholesale beer costs went up 5%, you can:
1. Filter by "Beer"
2. Select "Percentage Increase" 
3. Enter "5"
4. Check "Also adjust our_cost proportionally"
5. Preview to see new prices
6. Apply

---

### 💰 Tab 3: Cost & Margins
**Purpose:** Analyze profitability and margins across your beverage catalog

**What You See:**
- **Total Items:** How many beverages in the system (currently 1,179 products)
- **Average Margin:** Overall profit percentage across all products
- **Low Margin Items:** Count of products with <20% profit margin (⚠️ these may need pricing review)
- **Detailed margins table:**
  - Product name
  - Unit Price (what you charge)
  - Our Cost (wholesale cost)
  - Margin $ (profit per unit)
  - Margin % (profit as percentage)
  - Volume Sold (tracks actual sales - showing TBD while feature is being built)
  - Total Margin (volume × margin per unit)

**When to Use:**
- Review profitability of product categories
- Identify products with poor margins that might need price increases
- Export margin report for accounting/management review
- Understand which beverages are most profitable

**Export:** Click 💾 Export Margin Report to save to CSV for Excel analysis

---

### 📅 Tab 4: Charter Costs
**Purpose:** Track beverage costs and margins PER CHARTER, PER MONTH, or PER YEAR

**What Dispatchers Can Do:**
- **Set date range** (From Date → To Date)
- **Choose grouping:** 
  - By Charter (each booking separately)
  - By Month (all beverages sold in January, February, etc.)
  - By Year (all beverages sold in 2025, 2026, etc.)
  - By Driver (costs associated with each driver)
  - By Category (Beer costs, Spirits costs, etc.)
- **Search** to pull data for that period
- **See for each group:**
  - Item count (how many beverages sold)
  - Our Cost Total (wholesale cost to Arrow Limousine)
  - Revenue Total (what customers were charged)
  - Gross Margin (revenue minus cost)
  - Margin % (profit percentage)
  - Average per Item (margin per beverage)

**When to Use:**
- Check profitability of specific charters
- Analyze beverage sales by month/year
- Identify which drivers/routes are moving the most beverage volume
- Understand seasonal patterns (e.g., summer vs. winter sales)
- Budget and forecasting

**Export:** Click 💾 Export Charter Costs Report to save analysis to CSV

---

## Pricing Guidelines

### Default Cost Calculation
- **Cost = 70% of Unit Price** (standard wholesale assumption)
  - e.g., if selling Corona at $5.49, cost is ~$3.84
  - This assumes typical distributor margins

### What Gets Adjusted with Price Changes?
- **Unit Price:** The amount customers are charged
- **Our Cost:** The wholesale cost Arrow Limousine pays suppliers
  - When using "Bulk Adjustments," you can optionally adjust costs too to maintain consistent margins
  - If you DON'T check "Also adjust our_cost," margins will improve when you raise prices

### Deposit Amounts
- **Separate from unit price**
- Typically $0.10-$0.25 per unit (glass/can deposit)
- NOT automatically adjusted when bulk adjusting prices
- Set manually when adding new products

---

## Common Tasks

### Task 1: Add a New Beverage Not in the System
**Steps:**
1. Go to **Catalog & Pricing** tab
2. Scroll to "Add New Beverage Product" section
3. Enter:
   - Product Name: "White Claw Hard Seltzer Lime 355ml"
   - Category: "Hard Seltzers"
   - Unit Price: $3.99 (what Wine and Beyond charges)
   - Cost: [Click "Calculate @ 70%"] → $2.79
   - Deposit: $0.10 (if applicable)
4. Click ✅ Add Product
5. System automatically assigns next available item ID

### Task 2: Raise Prices 5% Due to Supplier Cost Increase
**Steps:**
1. Go to **Bulk Adjustments** tab
2. Filter by Category: "All Categories" (or specific category)
3. Adjustment Type: "Percentage Increase"
4. Adjustment Value: 5
5. Check "Also adjust our_cost proportionally" (keeps margins consistent)
6. Click 👁️ Preview Changes
7. Review the before/after prices
8. Click ✅ Apply All Changes

### Task 3: Check Beverage Profitability on a Specific Charter
**Steps:**
1. Go to **Charter Costs** tab
2. From Date: [charter date]
3. To Date: [charter date + 1]
4. Group By: "Charter"
5. Click 🔍 Search
6. View results showing items sold, costs, revenue, and profit margin

### Task 4: Find Low-Margin Products
**Steps:**
1. Go to **Cost & Margins** tab
2. Look for products in red (⚠️ <20% margin)
3. Consider raising prices or negotiating better wholesale costs
4. Use **Bulk Adjustments** to increase prices on specific category

---

## Important Notes for Dispatchers

✅ **What's Stored:**
- Product name, category, unit price, wholesale cost, deposit amount
- Cost tracking per beverage per charter
- Historical pricing and margins

❌ **What's NOT Stored:**
- Inventory quantities (you don't stock items; you buy per-order)
- Physical warehouse locations
- Supplier information (handled elsewhere)

💡 **Pricing Strategy Tips:**
1. **Higher margin items** (30%+): Spirits, premium beer brands
2. **Lower margin items** (15-20%): Basic beer, water, mixers
3. **Seasonal adjustments:** Raise prices on summer items (seltzers), lower in off-season
4. **Bundle deals:** Can manually adjust individual items to create attractive packages

---

## Data Integration

The Beverage Management Widget connects to:
- **beverage_products table:** All 1,179+ items (item_id, name, price, cost, deposit)
- **Charter charges:** Beverage items added to bookings (auto-tracked)
- **Financial reports:** Margins rolled up to monthly/yearly profit & loss

---

## Questions & Support

- **"I want to add 10 new products":** Use Catalog & Pricing → Add New Beverage Product (repeat for each)
- **"I need to quickly raise all beer prices 5%":** Use Bulk Adjustments → Filter by Beer → Percentage Increase 5%
- **"Which beverages are most profitable?":** Go to Cost & Margins tab → review the table (sorted by margin %)
- **"How much did beverages contribute to Charter #015049?":** Use Charter Costs → Set dates for that charter → Group by Charter

---

**Last Updated:** January 8, 2026
**Widget Location:** Main Window → ⚙️ Admin & Settings → 🍷 Beverage Management
**Database Connection:** PostgreSQL almsdata, beverage_products table
