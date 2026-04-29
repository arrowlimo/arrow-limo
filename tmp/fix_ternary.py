"""
Fix the ternary continuation and any remaining syntax errors.
"""
import ast

SRC = 'desktop_app/charter_form_widget.py'

with open(SRC, 'r', encoding='utf-8') as f:
    lines = f.readlines()

fixes = 0

# Fix the "payload = charter_data_json if isinstance(" ternary pattern
# The structure produced by the bulk script:
#   payload = charter_data_json if isinstance(
#         charter_data_json, dict)
#         else json.loads(charter_data_json)
# Fix: wrap in parens:
#   payload = (charter_data_json if isinstance(
#         charter_data_json, dict)
#         else json.loads(charter_data_json))
for i in range(len(lines)):
    stripped = lines[i].rstrip('\n').rstrip()
    if ('payload = charter_data_json if isinstance(' in stripped
            and i + 2 < len(lines)):
        next1 = lines[i+1].rstrip('\n').rstrip()
        next2 = lines[i+2].rstrip('\n').rstrip()
        if ('charter_data_json, dict)' in next1
                and 'else json.loads(charter_data_json)' in next2
                and not next2.rstrip().endswith(')')):
            # Add wrapping parens: ( after = on current line, ) at end of next2
            lines[i] = stripped.replace(
                'payload = charter_data_json if isinstance(',
                'payload = (charter_data_json if isinstance('
            ) + '\n'
            lines[i+2] = next2 + ')\n'
            print(f"Fixed ternary at lines {i+1}-{i+3}")
            print(f"  {lines[i].rstrip()[:80]}")
            print(f"  {lines[i+1].rstrip()[:80]}")
            print(f"  {lines[i+2].rstrip()[:80]}")
            fixes += 1

with open(SRC, 'w', encoding='utf-8') as f:
    f.writelines(lines)
print(f"\nFixes applied: {fixes}")

# Check syntax
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
