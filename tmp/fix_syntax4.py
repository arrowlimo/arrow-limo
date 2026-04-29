"""Fix remaining syntax errors iteratively."""
import ast

SRC = 'desktop_app/charter_form_widget.py'

with open(SRC, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix 1: charter_date_to ternary split
# Pattern:
#   charter_date_to = self.charter_date_to.date().toString(
#       "MM/dd/yyyy")
#       if hasattr(self, "charter_date_to")
#       else charter_date_from
# Fix: add ( after = and ) after charter_date_from
for i in range(len(lines)):
    if ('charter_date_to = self.charter_date_to.date().toString(' in lines[i]
            and i + 3 < len(lines)):
        l1 = lines[i+1].rstrip('\n').rstrip()
        l2 = lines[i+2].rstrip('\n').rstrip()
        l3 = lines[i+3].rstrip('\n').rstrip()
        if ('"MM/dd/yyyy")' in l1
                and 'if hasattr(self, "charter_date_to")' in l2
                and 'else charter_date_from' in l3):
            lines[i] = lines[i].replace(
                'charter_date_to = self.charter_date_to',
                'charter_date_to = (self.charter_date_to'
            )
            lines[i+3] = l3 + ')\n'
            print(f"Fixed charter_date_to ternary at line {i+1}")
            break

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
