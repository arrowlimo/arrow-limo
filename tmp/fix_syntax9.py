"""Fix remaining syntax errors."""
import ast

SRC = 'desktop_app/charter_form_widget.py'

with open(SRC, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix: lines 8890-8893 - unclosed cur.execute tuple
# Current:
#   (self.charter_id, row_idx + 1,
#    pickup_loc, pickup_time,
#    dropoff_loc, dropoff_time,
#   [blank]
# Fix:
#   (self.charter_id, row_idx + 1,
#    pickup_loc, pickup_time,
#    dropoff_loc, dropoff_time))
idx = 8892 - 1
if 'dropoff_loc, dropoff_time,' in lines[idx] and not lines[idx+1].strip():
    lines[idx] = lines[idx].rstrip('\n').rstrip().rstrip(',') + '))\n'
    del lines[idx+1]  # remove blank line
    print(f"Fixed charter_routes tuple at line {idx+1}: {lines[idx].rstrip()[:80]}")
else:
    print(f"MISMATCH at 8892: {lines[idx].rstrip()[:80]}")
    print(f"  next: {lines[idx+1].rstrip()[:80]}")

with open(SRC, 'w', encoding='utf-8') as f:
    f.writelines(lines)

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
