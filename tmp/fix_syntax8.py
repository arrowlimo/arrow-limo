"""Fix remaining syntax errors iteratively."""
import ast

SRC = 'desktop_app/charter_form_widget.py'

with open(SRC, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix 1: lines 8054-8055 - broken if statement
# Current:
#   not self.separate_beverage_checkbox.isChecked()
#   or not self.beverage_cart_data):
# Fix:
#   if (not self.separate_beverage_checkbox.isChecked()
#       or not self.beverage_cart_data):
idx = 8054 - 1
if ('not self.separate_beverage_checkbox.isChecked()' in lines[idx]
        and not lines[idx].lstrip().startswith('if ')):
    indent = ' ' * (len(lines[idx]) - len(lines[idx].lstrip()))
    lines[idx] = f'{indent}if (not self.separate_beverage_checkbox.isChecked()\n'
    print(f"Fixed if statement at line {idx+1}")
else:
    print(f"MISMATCH at 8054: {lines[idx].rstrip()[:80]}")

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
