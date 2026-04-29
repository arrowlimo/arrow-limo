"""
Fix all broken syntax patterns introduced by the bulk fix script in
charter_form_widget.py.

Known broken patterns (from reading tmp/fix_charter_e501.py):
1. Missing ) after f"Charter ID: {self.charter_id}" (QMessageBox.information split)
2. Missing ) after f"{e.diag...}" (QMessageBox.critical "Failed to save charter")
3. charter_data_json ternary: 'charter_data_json, dict)\nelse json.loads(...)'
4. Any other missing ) situations caught by syntax errors

Strategy: fix known patterns, then iteratively check for remaining errors.
"""
import ast

SRC = 'desktop_app/charter_form_widget.py'

with open(SRC, 'r', encoding='utf-8') as f:
    lines = f.readlines()

fixes = 0

def find_and_fix_missing_close(lines, search_str, close_char=')'):
    """Find lines containing search_str that don't end with close_char and add it."""
    count = 0
    for i, line in enumerate(lines):
        stripped = line.rstrip('\n').rstrip()
        if search_str in stripped and not stripped.endswith(close_char):
            lines[i] = stripped + close_char + '\n'
            print(f"Fixed line {i+1}: {lines[i].rstrip()[:80]}")
            count += 1
    return count

# Fix 1: f"Charter ID: {self.charter_id}" missing )
# These appear after QMessageBox.information(self, "Success", ... splits
fixes += find_and_fix_missing_close(
    lines,
    'f"Charter ID: {self.charter_id}"'
)

# Fix 2: f"{e.diag.message_primary if hasattr(e, 'diag') else str(e)}" missing )
# These appear after QMessageBox.critical("Failed to save charter...") splits
fixes += find_and_fix_missing_close(
    lines,
    "f\"{e.diag.message_primary if hasattr(e, 'diag') else str(e)}\""
)

# Fix 3: charter_data_json ternary - "else json.loads(charter_data_json)" 
# The fix script outputs:
#   charter_data_json, dict)
#   else json.loads(charter_data_json)
# This is part of: `x = charter_data_json if isinstance(\n charter_data_json, dict)\nelse json.loads(charter_data_json)`
# The `else` on a new line without enclosing parens is the problem.
# Find "else json.loads(charter_data_json)" lines and check if previous has "dict)"
for i in range(len(lines)):
    stripped = lines[i].rstrip('\n').rstrip()
    if stripped.endswith('else json.loads(charter_data_json)'):
        # Check 2 lines back to see structure
        if i >= 2:
            prev1 = lines[i-1].rstrip('\n').rstrip()
            prev2 = lines[i-2].rstrip('\n').rstrip()
            print(f"  Found ternary continuation at line {i+1}")
            print(f"  Prev2 ({i-1}): {prev2[:80]}")
            print(f"  Prev1 ({i}):   {prev1[:80]}")
            print(f"  This  ({i+1}): {stripped[:80]}")
            # If prev1 ends with "charter_data_json, dict)", that's a dangling ternary
            # We need to check prev2 for the "if isinstance(" part
            # The real fix is to ensure the whole expression is wrapped in parens
            # This requires careful context-aware fixing

# Write fixes
with open(SRC, 'w', encoding='utf-8') as f:
    f.writelines(lines)
print(f"\nTotal fixes applied: {fixes}")

# Check syntax
with open(SRC, 'r', encoding='utf-8') as f:
    src = f.read()
try:
    ast.parse(src)
    print("SYNTAX OK!")
except SyntaxError as e:
    src_lines = src.splitlines()
    print(f"SyntaxError at line {e.lineno}: {e.msg}")
    for j in range(max(0, e.lineno - 4), min(len(src_lines), e.lineno + 4)):
        marker = " >>> " if j == e.lineno - 1 else "     "
        print(f"{marker}{j+1}: {src_lines[j][:100]}")
