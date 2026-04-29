"""Remove the spurious \"\"\")\n at line 6354 and check for more."""
import ast

SRC = 'desktop_app/charter_form_widget.py'

with open(SRC, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Line 6354 (0-based index 6353) is a spurious """)
# Context:
#   6353:     f" WHERE charter_id = %s", (charter_id,))
#   6354:     """)    ← spurious
#   6355:     row = cur.fetchone()
idx = 6354 - 1  # 0-based
if '""")' in lines[idx] and '""")' not in lines[idx-1]:
    print(f"Removing spurious line {idx+1}: {lines[idx].rstrip()[:60]}")
    del lines[idx]
else:
    print(f"NOT FOUND at 6354: {lines[idx].rstrip()[:60]}")
    # Search for it nearby
    for i in range(6348, 6365):
        if '""")' in lines[i]:
            print(f"  Found at line {i+1}: {lines[i].rstrip()[:60]}")

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
