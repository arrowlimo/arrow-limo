"""Fix remaining syntax errors - driver_combo and others."""
import ast

SRC = 'desktop_app/charter_form_widget.py'

with open(SRC, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix line 6950-6951: assigned_driver broken
# Current:
#   assigned_driver = self.driver_combo.currentText() if hasattr(self,
#                                                       if hasattr(self, "driver_combo") else "")
# Correct:
#   assigned_driver = (
#       self.driver_combo.currentText()
#       if hasattr(self, "driver_combo") else "")
idx = 6950 - 1  # 0-based
if ('assigned_driver = self.driver_combo.currentText() if hasattr(self,' in lines[idx]
        and 'if hasattr(self, "driver_combo") else "")' in lines[idx+1]):
    indent = len(lines[idx]) - len(lines[idx].lstrip())
    ind_str = ' ' * indent
    lines[idx] = f'{ind_str}assigned_driver = (\n'
    lines[idx+1] = f'{ind_str}    self.driver_combo.currentText()\n'
    # Need to insert a 3rd line
    lines.insert(idx+2, f'{ind_str}    if hasattr(self, "driver_combo") else "")\n')
    print(f"Fixed assigned_driver at lines {idx+1}-{idx+3}")
else:
    print(f"MISMATCH: {repr(lines[idx].rstrip()[:80])}")
    print(f"MISMATCH: {repr(lines[idx+1].rstrip()[:80])}")

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
