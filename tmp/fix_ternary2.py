"""Fix ternary continuation by direct line number manipulation."""
import ast

SRC = 'desktop_app/charter_form_widget.py'

with open(SRC, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Direct fix: line 6594 (index 6593): add ( after =
# line 6596 (index 6595): add ) at end
# Do both occurrences (around 6594 and 6628)
target_pairs = []
for i in range(len(lines)):
    if 'payload = charter_data_json if isinstance(' in lines[i]:
        # Check lines i+1 and i+2
        if (i + 2 < len(lines)
                and 'charter_data_json, dict)' in lines[i+1]
                and 'else json.loads(charter_data_json)' in lines[i+2]):
            target_pairs.append(i)

print(f"Found {len(target_pairs)} targets: lines {[t+1 for t in target_pairs]}")

for i in target_pairs:
    # Fix line i: add ( 
    old_line = lines[i]
    lines[i] = old_line.replace(
        'payload = charter_data_json if isinstance(',
        'payload = (charter_data_json if isinstance('
    )
    # Fix line i+2: add )
    old_next2 = lines[i+2].rstrip('\n').rstrip()
    lines[i+2] = old_next2 + ')\n'
    print(f"Fixed lines {i+1} and {i+3}:")
    print(f"  {lines[i].rstrip()[:90]}")
    print(f"  {lines[i+2].rstrip()[:90]}")

with open(SRC, 'w', encoding='utf-8') as f:
    f.writelines(lines)
print("Saved.")

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
