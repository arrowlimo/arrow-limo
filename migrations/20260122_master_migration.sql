-- Master migration script runner for booking lifecycle (Steps 2B, 3, 4, 5, 6, 7)
-- Date: 2026-01-22
-- Run from: L:\limo\migrations
-- Usage: psql -h localhost -U postgres -d almsdata -f 20260122_master_migration.sql

-- This script executes all Step migrations in order
-- Review each step before running; comment out any steps already applied

\echo 'Starting booking lifecycle master migration...'

\echo 'Step 2B: Driver Inspection, HOS, Receipts, & Pay'
\i 20260122_step2b_driver_hos_pay.sql

\echo 'Step 2B: Effective hourly trigger'
\i 20260122_step2b_effective_hourly_trigger.sql

\echo 'Step 3: Dispatch & Service Day Operations'
\i 20260122_step3_dispatch.sql

\echo 'Step 4: Service Execution (Charter Day)'
\i 20260122_step4_service_execution.sql

\echo 'Step 5: Trip Completion & Closeout'
\i 20260122_step5_completion_closeout.sql

\echo 'Step 6: Invoice Generation & Payment Collection'
\i 20260122_step6_invoice_payment.sql

\echo 'Step 7: Archive & Records Management'
\i 20260122_step7_archive_records.sql

\echo 'Master migration complete. Review output for errors.'

-- Verification queries (optional)
\echo 'Verification: checking new tables...'

SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' 
  AND table_name IN (
    'vehicle_capacity_tiers',
    'charters_routing_times',
    'hos_log',
    'hos_14day_summary',
    'charter_receipts',
    'charter_beverage_orders',
    'charter_beverage_items',
    'charter_driver_pay',
    'dispatch_events',
    'driver_comms_log',
    'charter_incidents',
    'customer_comms_log',
    'customer_feedback',
    'invoices',
    'invoice_line_items'
  )
ORDER BY table_name;

\echo 'Verification: checking views...'

SELECT table_name FROM information_schema.views 
WHERE table_schema = 'public' 
  AND table_name IN (
    'v_revenue_summary',
    'v_driver_pay_summary',
    'v_vehicle_utilization',
    'v_incident_trends',
    'v_hos_compliance_summary',
    'v_outstanding_receivables'
  )
ORDER BY table_name;

\echo 'Done.'
