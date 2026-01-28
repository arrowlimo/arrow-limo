"""
Phase 4B: Identify and update all queries using charters.balance
"""
import os
import re

print("=" * 100)
print("PHASE 4B: FIND & UPDATE CHARTERS.BALANCE QUERIES")
print("=" * 100)

# Files with charters.balance references
files_with_balance = {
    "desktop_app/dashboard_classes.py": [350, 351, 354, 355],
    "desktop_app/receipt_search_match_widget.py": [2103],
    "desktop_app/vendor_payables_dashboard.py": [98, 117],
    "recreate_charge_summary_report.py": [106],
    "scripts/analyze_015808_date_mismatch.py": [44, 127, 167],
    "waste_connections_matching.py": [90],
    "scripts/analyze_2012_credit_card_payments.py": [137],
    "scripts/analyze_686_payment_mismatches.py": [84],
    "scripts/analyze_alms_charter_balances.py": [26, 111, 135],
    "scripts/analyze_cancelled_charter_charges.py": [78],
    "scripts/analyze_cancelled_with_charges.py": [36, 47],
    "scripts/analyze_cash_payment_patterns.py": [192, 210, 227],
    "scripts/analyze_charges_no_payments.py": [49],
    "scripts/analyze_charter_charges.py": [101, 109, 140, 146, 148, 149],
    "scripts/analyze_charter_payment_matching.py": [80, 91],
    "scripts/analyze_credits_for_refunds.py": [29, 34, 40, 91, 94, 102, 120, 123, 130, 167, 169],
    "scripts/analyze_gordon_dean_duplicate.py": [104, 111, 162, 168, 226],
    "simple_multi_charter_matching.py": [140, 141],
    "scripts/analyze_negative_balances.py": [51, 56, 59, 60, 98, 132, 155, 159, 161],
    "scripts/2012_match_orphaned_payments.py": [65],
    "scripts/analyze_orphaned_payments.py": [29],
    "scripts/analyze_overpaid_by_type.py": [64, 69, 73],
    "scripts/analyze_partial_payment_matching.py": [42, 55],
    "scripts/analyze_payment_mismatches.py": [83],
    "scripts/analyze_qb_detailed_for_charters.py": [141],
    "scripts/analyze_remaining_unmatched_banking.py": [35],
    "scripts/analyze_residual_overpaid.py": [23],
    "scripts/analyze_remaining_doubled_sources.py": [20],
    "scripts/analyze_remaining_credits.py": [31, 35, 37, 57, 59, 70, 72],
    "scripts/analyze_unassigned_charters.py": [63],
    "scripts/analyze_unmatched_after_charity.py": [47, 124],
    "scripts/analyze_unmatched_comprehensive.py": [131, 153, 159],
    "scripts/analyze_unmatched_charter_payments.py": [107, 118],
    "scripts/analyze_unpaid_charters.py": [35],
    "scripts/apply_charity_gst_optimization.py": [237],
    "multi_charter_payment_matching.py": [178],
}

print(f"\n[1] FILES AFFECTED: {len(files_with_balance)}")
print("-" * 100)

for file_path in sorted(files_with_balance.keys()):
    lines = files_with_balance[file_path]
    print(f"{file_path:<50} {len(lines):>3} references")

print(f"\nTotal references: {sum(len(v) for v in files_with_balance.values())}")

# Strategy document
print("\n[2] MIGRATION STRATEGY")
print("-" * 100)

strategy = """
APPROACH: Replace charters.balance with calculated balance from v_charter_balances view

PATTERN 1: Simple column select
  BEFORE: SELECT ... c.balance ...
  AFTER:  SELECT ... vcb.calculated_balance AS balance ...
          JOIN v_charter_balances vcb ON vcb.charter_id = c.charter_id

PATTERN 2: Conditional filter (balance > 0)
  BEFORE: WHERE c.balance > 0
  AFTER:  WHERE vcb.calculated_balance > 0

PATTERN 3: Balance calculation check
  BEFORE: AND ABS(COALESCE(c.balance, c.total_amount_due, 0) - p.amount) < 1.0
  AFTER:  AND ABS(COALESCE(vcb.calculated_balance, c.total_amount_due, 0) - p.amount) < 1.0

PATTERN 4: SUM(c.balance)
  BEFORE: SELECT SUM(c.balance)
  AFTER:  SELECT SUM(vcb.calculated_balance)
          JOIN v_charter_balances vcb ...

PHASE 4B TASKS:
1. Create update_queries_phase4b.py (full migration script with --dry-run)
2. Run --dry-run to show all changes
3. Apply changes with --commit flag
4. Test each modified file for syntax errors
5. Run reports/dashboards to verify output unchanged

ROLLBACK PLAN:
- If issues found, revert to using c.balance column (still exists until Phase 4C)
- No schema change yet; only query modifications
- Safe to iterate

PERFORMANCE CONSIDERATIONS:
- JOIN to v_charter_balances adds one extra join in each query
- View already groups by charter_id, so indexed lookup fast
- May need to add indexes on charters.charter_id if not present
"""

print(strategy)

# Priority list (desktop app files first, then most-referenced scripts)
print("\n[3] MIGRATION PRIORITY (Desktop App First, Then Scripts)")
print("-" * 100)

priority_order = [
    # Desktop app (user-facing)
    "desktop_app/dashboard_classes.py",
    "desktop_app/receipt_search_match_widget.py", 
    "desktop_app/vendor_payables_dashboard.py",
    # Core analysis scripts
    "scripts/analyze_charter_payment_matching.py",
    "scripts/analyze_credits_for_refunds.py",
    "scripts/analyze_unpaid_charters.py",
    "scripts/analyze_unmatched_comprehensive.py",
    # Other scripts (lower priority)
    "scripts/analyze_alms_charter_balances.py",
    "scripts/analyze_negative_balances.py",
]

for i, file in enumerate(priority_order, 1):
    refs = len(files_with_balance.get(file, []))
    print(f"{i}. {file:<50} ({refs} refs)")

print("\n[4] MIGRATION STEPS")
print("-" * 100)

steps = """
STEP 1: Create update_queries_phase4b.py script
  - Parse each .py file
  - Find c.balance references
  - Generate replacement SQL
  - Support --dry-run and --commit flags

STEP 2: Test on non-critical files first
  - Run --dry-run on analyze_*.py scripts
  - Verify pattern matches
  - Fix any edge cases

STEP 3: Update desktop app files
  - Most critical user-facing code
  - Test each widget after update
  - Verify reports still work

STEP 4: Run full test suite
  - Execute all modified scripts
  - Compare output to baseline
  - Check for missing/broken queries

STEP 5: Prepare for Phase 4C
  - Create backup of charters table
  - Document all updated queries
  - Schedule column drop

ESTIMATED EFFORT:
- ~40 files to update
- ~100+ SQL statement modifications
- ~2-4 hours for full migration + testing
"""

print(steps)

print("\n[5] RECOMMENDED NEXT STEP")
print("-" * 100)
print("""
✅ Phase 4A Complete: v_charter_balances view created and validated (99.8% match)

→ PROCEED TO PHASE 4B: Create automated migration script
  - File: update_queries_phase4b.py
  - Purpose: Find and replace all c.balance references with view-based calculation
  - Output: Generate SQL + show diffs before applying
  - Safety: Support --dry-run mode to preview changes
  
Execute next command:
  python -X utf8 update_queries_phase4b.py --dry-run

Or skip Phase 4B and jump to Phase 4C (direct drop) if comfortable with manual updates.
""")

print("=" * 100)
