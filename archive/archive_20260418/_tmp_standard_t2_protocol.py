#!/usr/bin/env python3
"""
STANDARD T2 REVENUE RECORDING & REPORTING PROTOCOL

Arrow Limo uses income_ledger as the single source of truth for all T2 reporting.
This script documents the two distinct revenue concepts and how they flow through the system.
"""

import psycopg2
from decimal import Decimal

DB_HOST = 'localhost'
DB_PORT = 5432
DB_NAME = 'almsdata'
DB_USER = 'postgres'
DB_PASSWORD = 'ArrowLimousine'

def main():
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()

    print("\n" + "="*90)
    print("ARROW LIMO - STANDARD T2 REVENUE RECORDING PROTOCOL")
    print("="*90)

    print("""
╔════════════════════════════════════════════════════════════════════════════════════════╗
║                    TWO DISTINCT REVENUE CONCEPTS                                       ║
╚════════════════════════════════════════════════════════════════════════════════════════╝

1. BOOKED REVENUE (charters.grand_total / charters.total_amount_due)
   └─ What the customer was INVOICED
   └─ Used for: Accounts Receivable, invoicing, operational reporting
   └─ Time basis: charter_date (when service was delivered)
   └─ DOES NOT appear in T2 reporting directly
   
2. CASH RECEIVED (charter_payments.amount)
   └─ What the customer actually PAID
   └─ Used for: T2 return, cash-basis reporting, banking reconciliation
   └─ Time basis: payment_date (when payment cleared)
   └─ Only revenue source for income_ledger → T2


╔════════════════════════════════════════════════════════════════════════════════════════╗
║                    2012 REVENUE EXAMPLES                                               ║
╚════════════════════════════════════════════════════════════════════════════════════════╝
""")

    # Show the comparison
    query1 = """
    SELECT 
        COUNT(*) as charter_count,
        COALESCE(SUM(COALESCE(grand_total, total_amount_due, 0)), 0) as booked_revenue
    FROM charters
    WHERE EXTRACT(YEAR FROM charter_date) = 2012;
    """
    
    query2 = """
    SELECT 
        COUNT(*) as payment_count,
        COALESCE(SUM(amount), 0) as cash_received
    FROM charter_payments
    WHERE EXTRACT(YEAR FROM payment_date) = 2012;
    """
    
    cur.execute(query1)
    charter_count, booked_revenue = cur.fetchone()
    
    cur.execute(query2)
    payment_count, cash_received = cur.fetchone()

    booked_revenue = float(booked_revenue)
    cash_received = float(cash_received)
    
    print(f"""╭─ BOOKED REVENUE (charters table)
│  Charters issued: {charter_count:,}
│  Total chargeable: ${booked_revenue:,.2f}
│  Source file: charters.grand_total or charters.total_amount_due
│  Use for: Invoicing, client reporting, AR aging
│  Does NOT go to T2 directly
│
├─ CASH RECEIVED (charter_payments table)  ✓✓✓ THIS GOES TO T2
│  Payments received: {payment_count:,}
│  Total collected: ${cash_received:,.2f}
│  Source file: charter_payments.amount
│  Use for: Income_ledger, T2 return, cash-basis reporting
│  
└─ RECONCILIATION
   Outstanding (unbilled/unreceived): ${booked_revenue - cash_received:,.2f}
   
   For T2 purposes, T2 revenue = ${cash_received:,.2f} (CASH RECEIVED ONLY)

""")

    print("""
╔════════════════════════════════════════════════════════════════════════════════════════╗
║                    HOW REVENUE FLOWS TO T2 REPORTING                                   ║
╚════════════════════════════════════════════════════════════════════════════════════════╝

STEP 1: Extract from charter_payments (ALWAYS)
   ┌─ Table: charter_payments
   ├─ Filter: WHERE EXTRACT(YEAR FROM payment_date) = 2012
   ├─ Fields: id, charter_id, amount, payment_date, payment_method
   └─ Total for 2012: Multiple payment records

STEP 2: Record in income_ledger (STANDARDIZED)
   ┌─ Table: income_ledger
   ├─ Insert with:
   │  ├─ source_system = 'charter_payments'
   │  ├─ transaction_date = charter_payments.payment_date
   │  ├─ gross_amount = charter_payments.amount
   │  ├─ gst_collected = amount * 5 / 105 (AB rate)
   │  ├─ net_amount = gross_amount - gst_collected
   │  ├─ revenue_category = 'Operating Revenue'
   │  ├─ revenue_subcategory = 'Charter Services'
   │  ├─ is_taxable = true
   │  └─ fiscal_year = EXTRACT(YEAR FROM payment_date)
   ├─ Link: payment_id (FK back to charter_payments)
   └─ Purpose: Single source of truth for T2

STEP 3: Extract for T2 Return (READS FROM income_ledger)
   ┌─ Query: SELECT SUM(gross_amount) FROM income_ledger 
   │         WHERE fiscal_year = 2012 AND is_taxable = true
   ├─ Calculate: 
   │  ├─ T2 Total Revenue = SUM(gross_amount)
   │  ├─ GST Collected = SUM(gst_collected)  [Report Line 10400]
   │  ├─ Net Business Income = SUM(net_amount)
   │  └─ Schedule 1 (if applicable) adds back non-deductible items
   ├─ Audit Trail: income_ledger.payment_id → charter_payments
   └─ Result: Accurate, reconciled T2 revenue data

STEP 4: Audit & Reconciliation (t2_deductibility_audit)
   ├─ Compare: income_ledger total vs receipts GL code totals
   ├─ Verify: All revenue categorized and taxable status correct
   ├─ Identify: Non-deductible expense add-backs for Schedule 1
   └─ Link: t2_deductibility_audit.income_ledger_id


╔════════════════════════════════════════════════════════════════════════════════════════╗
║                    CURRENT 2012 STATUS & ACTION                                        ║
╚════════════════════════════════════════════════════════════════════════════════════════╝
""")

    # Check current status
    query_il = """
    SELECT COUNT(*), COALESCE(SUM(gross_amount), 0)
    FROM income_ledger
    WHERE fiscal_year = 2012;
    """
    
    cur.execute(query_il)
    il_count, il_total = cur.fetchone()
    il_total = float(il_total)
    
    print(f"""
Current income_ledger (2012):  {il_count} records, ${il_total:,.2f}
Target (from charter_payments): {payment_count} records, ${cash_received:,.2f}

Status: {"✓ COMPLETE" if il_count == payment_count else "✗ NEEDS POPULATION"}

ACTION ITEMS:
  1. Populate income_ledger from 2012 charter_payments
  2. Verify match: income_ledger total = ${cash_received:,.2f}
  3. Run t2_deductibility_audit to validate GST and deductibility
  4. Export T2 data from income_ledger for return filing
  5. Document reconciliation trail in t2_return_metadata


╔════════════════════════════════════════════════════════════════════════════════════════╗
║                    THIS IS THE STANDARD FOR ALL YEARS                                  ║
╚════════════════════════════════════════════════════════════════════════════════════════╝

For any tax year X:
  
  1. All T2 revenue MUST come from income_ledger
  2. income_ledger populated from charter_payments (cash received basis)
  3. Never use charters.total_amount_due for T2 (that's accrual)
  4. Always calculate GST at 5% (AB) using: amount * 5 / 105
  5. Link audit: income_ledger.payment_id → charter_payments.id
  6. Document cash vs. receivable variance for notes

This ensures:
  ✓ Cash-basis tax reporting (CRA requirement)
  ✓ Reconcilable to banking records
  ✓ Audit trail from T2 → income_ledger → charter_payments
  ✓ Consistent GST extraction and reporting
  ✓ Schedule 1 add-back analysis for deductibility

""")

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
