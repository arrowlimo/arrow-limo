-- RECONCILIATION FIXES GENERATED
-- Generated: 20260120_171950
-- BEFORE RUNNING: Review all fixes and commit database

-- FIX 2: Verify retainer charters are marked correctly
-- These should have retainer_received = TRUE

-- Charter 14172 (015279): Verify retainer_received = TRUE
UPDATE charters SET retainer_received = TRUE WHERE charter_id = 14172;

-- Charter 14173 (015280): Verify retainer_received = TRUE
UPDATE charters SET retainer_received = TRUE WHERE charter_id = 14173;

-- Charter 14431 (015541): Verify retainer_received = TRUE
UPDATE charters SET retainer_received = TRUE WHERE charter_id = 14431;

-- Charter 14432 (015542): Verify retainer_received = TRUE
UPDATE charters SET retainer_received = TRUE WHERE charter_id = 14432;

-- Charter 14689 (015799): Verify retainer_received = TRUE
UPDATE charters SET retainer_received = TRUE WHERE charter_id = 14689;

-- FIX 3: REVIEW zero-due charters with payments
-- These indicate charges may have been incorrectly deleted
-- DO NOT AUTO-FIX: Requires manual verification

-- Charter 165 (001188): 1 payments exist but due=$0
--   Status: Closed, Paid: $206.70

-- Charter 3227 (004271): 2 payments exist but due=$0
--   Status: Closed, Paid: $0.00

-- Charter 5250 (006303): 1 payments exist but due=$0
--   Status: closed, Paid: $0.00

-- Charter 5272 (006325): 1 payments exist but due=$0
--   Status: closed, Paid: $0.00

-- Charter 5314 (006344): 1 payments exist but due=$0
--   Status: closed, Paid: $0.00

-- Charter 5440 (006494): 1 payments exist but due=$0
--   Status: Closed, Paid: $0.00

-- Charter 5459 (006513): 1 payments exist but due=$0
--   Status: Closed, Paid: $0.00

-- Charter 5795 (006852): 2 payments exist but due=$0
--   Status: closed_paid_verified, Paid: $0.00

-- Charter 6018 (007078): 3 payments exist but due=$0
--   Status: Closed, Paid: $0.00

-- Charter 6162 (007218): 2 payments exist but due=$0
--   Status: closed_paid_verified, Paid: $0.00

