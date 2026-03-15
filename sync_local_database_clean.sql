-- ============================================================================
-- SYNC LOCAL DATABASE TO MATCH NEON SCHEMA
-- Generated: 2026-02-05 18:37:31
-- Run as: postgres superuser
-- Database: almsdata (LOCAL)
-- ============================================================================

-- ============================================================================
-- Table: accounting_entries (4 columns)
-- ============================================================================
ALTER TABLE accounting_entries
  ADD COLUMN IF NOT EXISTS banking_transaction_id bigint,
  ADD COLUMN IF NOT EXISTS income_ledger_id bigint,
  ADD COLUMN IF NOT EXISTS payment_id bigint,
  ADD COLUMN IF NOT EXISTS receipt_id bigint
;

-- ============================================================================
-- Table: banking_transactions (4 columns)
-- ============================================================================
ALTER TABLE banking_transactions
  ADD COLUMN IF NOT EXISTS accounting_entry_id bigint,
  ADD COLUMN IF NOT EXISTS charter_id bigint,
  ADD COLUMN IF NOT EXISTS income_ledger_id bigint,
  ADD COLUMN IF NOT EXISTS payment_id bigint
;

-- ============================================================================
-- Table: chart_of_accounts (6 columns)
-- ============================================================================
ALTER TABLE chart_of_accounts
  ADD COLUMN IF NOT EXISTS default_category_code character varying(50),
  ADD COLUMN IF NOT EXISTS is_business_expense boolean DEFAULT true,
  ADD COLUMN IF NOT EXISTS is_linked_account boolean DEFAULT false,
  ADD COLUMN IF NOT EXISTS is_tax_applicable boolean DEFAULT false,
  ADD COLUMN IF NOT EXISTS requires_employee boolean DEFAULT false,
  ADD COLUMN IF NOT EXISTS requires_vehicle boolean DEFAULT false
;

-- ============================================================================
-- Table: charter_payments (4 columns)
-- ============================================================================
ALTER TABLE charter_payments
  ADD COLUMN IF NOT EXISTS accounting_entry_id bigint,
  ADD COLUMN IF NOT EXISTS banking_transaction_id bigint,
  ADD COLUMN IF NOT EXISTS income_ledger_id bigint,
  ADD COLUMN IF NOT EXISTS receipt_id bigint
;

-- ============================================================================
-- Table: charter_routes (3 columns)
-- ============================================================================
ALTER TABLE charter_routes
  ADD COLUMN IF NOT EXISTS address text,
  ADD COLUMN IF NOT EXISTS reserve_number character varying(20),
  ADD COLUMN IF NOT EXISTS stop_time time without time zone
;

-- ============================================================================
-- Table: clients (4 columns)
-- ============================================================================
ALTER TABLE clients
  ADD COLUMN IF NOT EXISTS account_type character varying(50),
  ADD COLUMN IF NOT EXISTS is_company boolean DEFAULT false,
  ADD COLUMN IF NOT EXISTS is_taxable boolean DEFAULT true,
  ADD COLUMN IF NOT EXISTS parent_client_id integer
;

-- ============================================================================
-- Table: employees (3 columns)
-- ============================================================================
ALTER TABLE employees
  ADD COLUMN IF NOT EXISTS department character varying(100),
  ADD COLUMN IF NOT EXISTS driver_code character varying(20),
  ADD COLUMN IF NOT EXISTS version integer DEFAULT 0
;

-- ============================================================================
-- Table: general_ledger (27 columns)
-- ============================================================================
ALTER TABLE general_ledger
  ADD COLUMN IF NOT EXISTS account_description text,
  ADD COLUMN IF NOT EXISTS account_full_name character varying(255),
  ADD COLUMN IF NOT EXISTS account_number character varying(50),
  ADD COLUMN IF NOT EXISTS account_type character varying(50),
  ADD COLUMN IF NOT EXISTS customer character varying(255),
  ADD COLUMN IF NOT EXISTS customer_first_name character varying(100),
  ADD COLUMN IF NOT EXISTS customer_full_name character varying(255),
  ADD COLUMN IF NOT EXISTS customer_middle_name character varying(100),
  ADD COLUMN IF NOT EXISTS customer_title character varying(50),
  ADD COLUMN IF NOT EXISTS distribution_account character varying(255),
  ADD COLUMN IF NOT EXISTS distribution_account_description text,
  ADD COLUMN IF NOT EXISTS distribution_account_number character varying(50),
  ADD COLUMN IF NOT EXISTS distribution_account_subtype character varying(50),
  ADD COLUMN IF NOT EXISTS distribution_account_type character varying(50),
  ADD COLUMN IF NOT EXISTS employee_billable boolean DEFAULT false,
  ADD COLUMN IF NOT EXISTS employee_deleted boolean DEFAULT false,
  ADD COLUMN IF NOT EXISTS employee_id integer,
  ADD COLUMN IF NOT EXISTS item_supplier_company character varying(255),
  ADD COLUMN IF NOT EXISTS parent_account_id integer,
  ADD COLUMN IF NOT EXISTS parent_distribution_account_id integer,
  ADD COLUMN IF NOT EXISTS po_number character varying(50),
  ADD COLUMN IF NOT EXISTS tax_code character varying(20),
  ADD COLUMN IF NOT EXISTS tax_name character varying(100),
  ADD COLUMN IF NOT EXISTS tax_slip_type character varying(50),
  ADD COLUMN IF NOT EXISTS transaction_date date,
  ADD COLUMN IF NOT EXISTS transaction_id bigint,
  ADD COLUMN IF NOT EXISTS ungrouped_tags text
;

-- ============================================================================
-- Table: income_ledger (3 columns)
-- ============================================================================
ALTER TABLE income_ledger
  ADD COLUMN IF NOT EXISTS accounting_entry_id bigint,
  ADD COLUMN IF NOT EXISTS banking_transaction_id bigint,
  ADD COLUMN IF NOT EXISTS receipt_id bigint
;

-- ============================================================================
-- Table: receipt_categories (2 columns)
-- ============================================================================
ALTER TABLE receipt_categories
  ADD COLUMN IF NOT EXISTS gl_account_code character varying(50),
  ADD COLUMN IF NOT EXISTS is_business_expense boolean DEFAULT true
;

-- ============================================================================
-- Table: run_type_default_charges (2 columns)
-- ============================================================================
ALTER TABLE run_type_default_charges
  ADD COLUMN IF NOT EXISTS formula text,
  ADD COLUMN IF NOT EXISTS id integer
;

-- Schema sync complete!
