"""Fix out_of_town_checkbox and remaining syntax errors."""
import ast

SRC = 'desktop_app/charter_form_widget.py'

with open(SRC, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix: All "if hasattr(" where the next line has 'out_of_town_checkbox')
# and the line after has "and self.out_of_town_checkbox.isChecked()):
# Fix: add ( to the if line, keep ): on the and line
fixes = 0
for i in range(len(lines)):
    if ("            if hasattr(\n" == lines[i]
            and i + 3 < len(lines)):
        l1 = lines[i+1].rstrip()
        l2 = lines[i+2].rstrip()
        l3 = lines[i+3].rstrip()
        if ("'out_of_town_checkbox')" in l2
                and "and self.out_of_town_checkbox.isChecked()):" in l3):
            # Fix: change "if hasattr(" to "if (hasattr("
            lines[i] = lines[i].replace(
                'if hasattr(',
                'if (hasattr('
            )
            print(f"Fixed out_of_town_checkbox if at line {i+1}: {lines[i].rstrip()[:80]}")
            fixes += 1

with open(SRC, 'w', encoding='utf-8') as f:
    f.writelines(lines)
print(f"Fixes: {fixes}")

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
