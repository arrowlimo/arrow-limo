"""Fix remaining syntax errors."""
import ast

SRC = 'desktop_app/charter_form_widget.py'

with open(SRC, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix: lines 9233-9235 - if with isinstance missing outer wrap paren
# Current:
#   if dropoff_addr and isinstance(
#       dropoff_addr, str)
#       and dropoff_addr.startswith("1899-12-30")):
# Fix:
#   if (dropoff_addr and isinstance(
#       dropoff_addr, str)
#       and dropoff_addr.startswith("1899-12-30")):
idx = 9233 - 1
if ('if dropoff_addr and isinstance(' in lines[idx]):
    lines[idx] = lines[idx].replace(
        'if dropoff_addr and isinstance(',
        'if (dropoff_addr and isinstance('
    )
    print(f"Fixed if isinstance at line {idx+1}: {lines[idx].rstrip()[:80]}")
else:
    print(f"MISMATCH at 9233: {lines[idx].rstrip()[:80]}")

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
