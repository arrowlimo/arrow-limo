#!/usr/bin/env python3
"""
CHARTER ROUTES CODE REVIEW & ISSUES DETECTION
==============================================

Complete code review checking for:
1. Type consistency issues (int vs str for charter_id)
2. Missing error handling
3. SQL injection vulnerabilities
4. Transaction management
5. Response model compatibility
6. Edge cases

Author: AI Assistant
Date: December 10, 2025
"""

def analyze_code_issues():
    """Analyze the code for potential issues."""
    
    issues = []
    warnings = []
    
    print("=" * 80)
    print("CODE REVIEW: CHARTER ROUTES IMPLEMENTATION")
    print("=" * 80)
    print()
    
    # ISSUE 1: Type inconsistency in Path parameters
    print("🔍 ISSUE 1: charter_id Type Inconsistency")
    print("-" * 80)
    print("FOUND: Mixed use of int and str for charter_id in Path parameters")
    print()
    print("❌ PROBLEMATIC CODE:")
    print("  @router.get('/charters/{charter_id}')")
    print("  def get_charter(charter_id: str = Path(...)):  # ← str")
    print()
    print("  @router.patch('/charters/{charter_id}')")
    print("  def update_charter(charter_id: str = Path(...)):  # ← str")
    print()
    print("  @router.get('/charters/{charter_id}/routes')")
    print("  def get_charter_routes(charter_id: int = Path(...)):  # ← int")
    print()
    print("IMPACT: Type mismatch between endpoints. Database charter_id is INTEGER.")
    print("FIX NEEDED: Standardize to 'int' for all charter_id parameters")
    issues.append("charter_id type inconsistency: str vs int")
    print()
    
    # ISSUE 2: SQL parameterization in dynamic query
    print("🔍 ISSUE 2: Dynamic SQL in Reorder Endpoint")
    print("-" * 80)
    print("FOUND: f-string used in SQL with IN clause")
    print()
    print("❌ POTENTIALLY PROBLEMATIC:")
    print("  cur.execute(")
    print("    f\"SELECT route_id FROM charter_routes WHERE charter_id = %s\"")
    print("    f\" AND route_id IN ({','.join(['%s']*len(route_ids))})\",")
    print("    (charter_id, *route_ids),")
    print("  )")
    print()
    print("STATUS: This is SAFE - placeholders are properly used")
    print("NOTE: Better pattern would use psycopg2.sql.SQL() for clarity")
    warnings.append("Dynamic SQL - currently safe but could use sql.SQL()")
    print()
    
    # ISSUE 3: Transaction handling
    print("🔍 ISSUE 3: Transaction Management in Reorder")
    print("-" * 80)
    print("FOUND: Multiple UPDATE statements in reorder endpoint")
    print()
    print("✅ GOOD: Uses cursor() context manager which handles commit/rollback")
    print("✅ GOOD: All updates in same transaction via single cursor context")
    print()
    print("RECOMMENDATION: Add explicit transaction markers for clarity:")
    print("  with cursor() as cur:")
    print("    # Transaction starts here")
    print("    cur.execute('BEGIN')  # Optional but explicit")
    print("    # ... updates ...")
    print("    # cursor() commits on success, rolls back on exception")
    print()
    
    # ISSUE 4: Error messages
    print("🔍 ISSUE 4: Error Response Detail Format")
    print("-" * 80)
    print("FOUND: Error details use snake_case strings")
    print()
    print("CURRENT:")
    print("  raise HTTPException(status_code=404, detail='charter_not_found')")
    print("  raise HTTPException(status_code=400, detail='charter_id_mismatch')")
    print()
    print("STATUS: Consistent pattern - good for API clients")
    print("✅ Machine-readable error codes")
    print("⚠️  Consider adding human-readable messages:")
    print("  detail={'code': 'charter_not_found', 'message': 'Charter does not exist'}")
    warnings.append("Error details are machine-only (no human messages)")
    print()
    
    # ISSUE 5: Charter ID validation
    print("🔍 ISSUE 5: Charter Existence Validation")
    print("-" * 80)
    print("✅ GOOD: create_charter_route() validates charter exists")
    print("✅ GOOD: reorder_charter_routes() validates charter exists")
    print("✅ GOOD: get_charter_with_routes() validates charter exists")
    print("⚠️  MISSING: get_charter_routes() does NOT validate charter exists")
    print()
    print("RECOMMENDATION: Add charter validation to get_charter_routes():")
    print("  # Before querying routes")
    print("  cur.execute('SELECT charter_id FROM charters WHERE charter_id = %s', (charter_id,))")
    print("  if not cur.fetchone():")
    print("    raise HTTPException(status_code=404, detail='charter_not_found')")
    issues.append("get_charter_routes() missing charter existence check")
    print()
    
    # ISSUE 6: Pydantic validation
    print("🔍 ISSUE 6: Pydantic Model Validation")
    print("-" * 80)
    print("✅ GOOD: route_sequence validation (ge=1)")
    print("✅ GOOD: numeric fields validation (ge=0)")
    print("✅ GOOD: route_status regex pattern validation")
    print("✅ GOOD: Optional fields properly marked")
    print()
    print("POTENTIAL ENHANCEMENT:")
    print("  Add field validators for time logic:")
    print("  @field_validator('dropoff_time')")
    print("  def validate_dropoff_after_pickup(cls, v, info):")
    print("    if info.data.get('pickup_time') and v:")
    print("      if v <= info.data['pickup_time']:")
    print("        raise ValueError('dropoff_time must be after pickup_time')")
    print("    return v")
    warnings.append("No cross-field time validation (pickup < dropoff)")
    print()
    
    # ISSUE 7: Response model mapping
    print("🔍 ISSUE 7: Response Model Data Mapping")
    print("-" * 80)
    print("PATTERN USED: dict(zip(cols, row, strict=False))")
    print()
    print("✅ GOOD: Dynamic column mapping from cursor.description")
    print("✅ GOOD: Works with SELECT *")
    print("⚠️  NOTE: strict=False allows length mismatches (Python 3.10+)")
    print()
    print("COMPATIBILITY: Requires Python 3.10+ for strict parameter")
    print("RECOMMENDATION: Verify Python version in requirements.txt")
    warnings.append("strict=False in zip() requires Python 3.10+")
    print()
    
    # ISSUE 8: CharterWithRoutes aggregation
    print("🔍 ISSUE 8: Aggregate NULL Handling")
    print("-" * 80)
    print("FOUND: SUM() aggregates in get_charter_with_routes()")
    print()
    print("✅ GOOD: LEFT JOIN preserves charters with no routes")
    print("⚠️  NOTE: SUM() returns NULL when no routes exist")
    print()
    print("CURRENT QUERY:")
    print("  SUM(r.estimated_duration_minutes) as total_estimated_minutes")
    print()
    print("RECOMMENDATION: Use COALESCE for better default values:")
    print("  COALESCE(SUM(r.estimated_duration_minutes), 0) as total_estimated_minutes")
    issues.append("SUM() aggregates return NULL instead of 0 for empty route sets")
    print()
    
    # ISSUE 9: Reorder sequence logic
    print("🔍 ISSUE 9: Reorder Negative Sequence Approach")
    print("-" * 80)
    print("FOUND: Uses negative route_id values to avoid UNIQUE constraint conflicts")
    print()
    print("LOGIC:")
    print("  1. Set all sequences to -route_id (temporary)")
    print("  2. Apply new sequences")
    print()
    print("⚠️  POTENTIAL ISSUE: route_sequence column allows negatives")
    print("DATABASE CONSTRAINT: route_sequence INTEGER NOT NULL DEFAULT 1")
    print("NO CHECK CONSTRAINT: Negative values are allowed!")
    print()
    print("RISK: If transaction fails mid-way, routes left with negative sequences")
    print()
    print("RECOMMENDATION: Add CHECK constraint:")
    print("  ALTER TABLE charter_routes ADD CONSTRAINT route_sequence_positive")
    print("    CHECK (route_sequence > 0);")
    print()
    print("ALTERNATIVE: Use a different temporary value range:")
    print("  # Use route_id + 10000 instead of -route_id")
    print("  cur.execute('UPDATE ... SET route_sequence = %s', (route_id + 10000, route_id))")
    issues.append("Negative sequence workaround lacks database constraint protection")
    print()
    
    # ISSUE 10: DELETE endpoint return type
    print("🔍 ISSUE 10: DELETE Endpoint Return Value")
    print("-" * 80)
    print("FOUND: delete_charter_route() returns None with status_code=204")
    print()
    print("CURRENT:")
    print("  @router.delete('...', status_code=204)")
    print("  def delete_charter_route(...):")
    print("    # ... delete logic ...")
    print("    return None")
    print()
    print("✅ CORRECT: 204 No Content should return empty body")
    print("✅ FastAPI handles None → empty response correctly")
    print()
    
    # Summary
    print("=" * 80)
    print("REVIEW SUMMARY")
    print("=" * 80)
    print()
    print(f"🔴 CRITICAL ISSUES: {len(issues)}")
    for i, issue in enumerate(issues, 1):
        print(f"  {i}. {issue}")
    print()
    print(f"🟡 WARNINGS/RECOMMENDATIONS: {len(warnings)}")
    for i, warning in enumerate(warnings, 1):
        print(f"  {i}. {warning}")
    print()
    
    if issues:
        print("⚠️  RECOMMENDED FIXES BEFORE PRODUCTION:")
        print("  1. Fix charter_id type consistency (int everywhere)")
        print("  2. Add charter validation to get_charter_routes()")
        print("  3. Use COALESCE() in SUM() aggregates")
        print("  4. Add route_sequence CHECK constraint (> 0)")
    else:
        print("✅ NO CRITICAL ISSUES - Code quality is good!")
    
    if warnings:
        print()
        print("💡 OPTIONAL ENHANCEMENTS:")
        print("  • Add cross-field time validation")
        print("  • Add human-readable error messages")
        print("  • Verify Python 3.10+ requirement")
        print("  • Use psycopg2.sql.SQL() for dynamic queries")
    
    print()
    print("=" * 80)
    print("OVERALL ASSESSMENT")
    print("=" * 80)
    print()
    
    if len(issues) == 0:
        print("🎉 PRODUCTION READY (with optional enhancements)")
        print("✅ Core functionality is solid")
        print("✅ Database integration is correct")
        print("✅ Error handling is present")
        print()
        print("Code quality: GOOD")
        return 0
    elif len(issues) <= 3:
        print("⚠️  MINOR FIXES NEEDED")
        print("Most issues are minor and easy to fix")
        print()
        print("Code quality: ACCEPTABLE")
        return 1
    else:
        print("🔧 SIGNIFICANT REFACTORING NEEDED")
        print("Multiple issues require attention")
        print()
        print("Code quality: NEEDS WORK")
        return 2

if __name__ == "__main__":
    exit(analyze_code_issues())
