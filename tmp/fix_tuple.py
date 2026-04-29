"""Fix the incomplete tuple unpacking and check for more errors."""
import ast

SRC = 'desktop_app/charter_form_widget.py'

with open(SRC, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix lines 7781-7783: incomplete tuple unpacking
# Current:
#   (charter_id, reserve, customer, phone, email,
#    charter_date, pickup_time, total_due, paid,
#   [blank line]
# Fix:
#   (charter_id, reserve, customer, phone, email,
#    charter_date, pickup_time, total_due, paid) = charter_data
idx = 7781 - 1  # 0-based
if ('(charter_id, reserve, customer, phone, email,' in lines[idx]
        and 'charter_date, pickup_time, total_due, paid,' in lines[idx+1]
        and not lines[idx+2].strip()):
    lines[idx+1] = '             charter_date, pickup_time, total_due, paid) = charter_data\n'
    del lines[idx+2]  # remove blank line that was part of the broken expression
    print(f"Fixed tuple unpacking at lines {idx+1}-{idx+2}")
else:
    print(f"MISMATCH:")
    print(f"  {lines[idx].rstrip()[:80]}")
    print(f"  {lines[idx+1].rstrip()[:80]}")
    print(f"  {lines[idx+2].rstrip()[:80]}")

with open(SRC, 'w', encoding='utf-8') as f:
    f.writelines(lines)

# Check
with open(SRC, 'r', encoding='utf-8') as f:
    src = f.read()
try:
    ast.parse(src)
    print("SYNTAX OK!")
except SyntaxError as e:
    src_lines = src.splitlines()
    print(f"SyntaxError at line {e.lineno}: {e.msg}")
    for j in range(max(0, e.lineno - 5), min(len(src_lines), e.lineno + 5)):
        marker = " >>> " if j == e.lineno - 1 else "     "
        print(f"{marker}{j+1}: {src_lines[j][:100]}")
