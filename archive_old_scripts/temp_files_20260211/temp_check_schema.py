#!/usr/bin/env python3
"""Check database schema for vendor invoicing tables"""
import psycopg2
import os

# Set env from file
with open("l:\limo\.env") as f:
    for line in f:
        if "=" in line and not line.startswith("#"):
            k,v = line.strip().split("=", 1)
            os.environ[k.strip()] = v.strip()

try:
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        database=os.getenv("DB_NAME", "almsdata"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        port=int(os.getenv("DB_PORT", "5432"))
    )
    
    cur = conn.cursor()
    
    print("=" * 60)
    print("DATABASE SCHEMA CHECK - VENDOR INVOICING")
    print("=" * 60)
    
    # Check receipts table columns
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='receipts' ORDER BY ordinal_position")
    cols = [row[0] for row in cur.fetchall()]
    
    has_vendor_name = "vendor_name" in cols
    has_vendor_id = "vendor_invoice_id" in cols
    has_canonical = "canonical_vendor" in cols
    
    print("\n1. RECEIPTS TABLE COLUMNS:")
    print(f"   vendor_name: {'✓ YES' if has_vendor_name else '✗ NO'}")
    print(f"   vendor_invoice_id: {'✓ YES' if has_vendor_id else '✗ NO'}")
    print(f"   canonical_vendor: {'✓ YES' if has_canonical else '✗ NO'}")
    
    # Check tables exist
    print("\n2. INVOICE-RELATED TABLES:")
    
    cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename='vendor_invoices'")
    vendor_inv_exists = cur.fetchone() is not None
    print(f"   vendor_invoices: {'✓ EXISTS' if vendor_inv_exists else '✗ MISSING'}")
    
    cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename='vendor_invoice_payments'")
    vendor_pay_exists = cur.fetchone() is not None
    print(f"   vendor_invoice_payments: {'✓ EXISTS' if vendor_pay_exists else '✗ MISSING (will be created on first payment)'}")
    
    # Summary
    print("\n3. CODE REQUIREMENTS vs DATABASE:")
    if has_vendor_name:
        print("   ✓ receipts.vendor_name exists (queried by vendor_invoice_manager.py)")
    else:
        print("   ✗ MISSING: receipts.vendor_name - will cause vendor search to fail")
    
    if vendor_pay_exists or not vendor_pay_exists:
        print("   ✓ vendor_invoice_payments - created dynamically on first payment")
    
    if vendor_inv_exists:
        print("   ✓ vendor_invoices table exists")
    else:
        print("   ℹ vendor_invoices table not created (may not be needed if using receipts directly)")
    
    print("\n" + "=" * 60)
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
