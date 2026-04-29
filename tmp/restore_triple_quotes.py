"""
Restore the 5 incorrectly deleted \"\"\")\n lines.
Find each location by looking for patterns around where they should be.
"""
import ast

SRC = 'desktop_app/charter_form_widget.py'

with open(SRC, 'r', encoding='utf-8') as f:
    lines = f.readlines()

insertions = []

# Pattern 1: After "AND table_name = 'charter_run_types')"
for i, line in enumerate(lines):
    if "AND table_name = 'charter_run_types')" in line:
        # Check next line is NOT a triple-quote closer
        if i + 1 < len(lines) and '"""' not in lines[i+1]:
            indent = ' ' * 12  # cur.execute indent
            insertions.append((i + 1, f'{indent}""")\n'))
            print(f"Pattern 1: insert after line {i+1}")
            break

# General pattern: find cur.execute(""" ... blocks where the closing
# "\"\"\")" is missing. Look for the code line following unclosed SQL.
# Strategy: find pairs where cur.execute(""" is followed by lines and then
# a code line without an intervening """)

# Find all cur.execute(""" openings
exec_starts = []
for i, line in enumerate(lines):
    stripped = line.strip()
    if stripped.startswith('cur.execute("""') or 'cur.execute("""' in line or 'cur.execute(f"""' in line:
        exec_starts.append(i)

# For each opening, find the matching """)
for start in exec_starts:
    # Find closing """) after start
    found_close = False
    for j in range(start + 1, min(start + 100, len(lines))):
        if '"""' in lines[j]:
            found_close = True
            break
        # If we hit a code line that clearly can't be in a SQL string
        # (doesn't look like SQL or is a Python statement)
        jstripped = lines[j].strip()
        if (jstripped and 
            not jstripped.startswith('--')
            and not jstripped.startswith('#')
            and any(jstripped.startswith(kw) for kw in
                    ['table_exists', 'rows =', 'row =', 'result =',
                     'max_val', 'new_reserve', 'counts', 'data ='])):
            # Missing """) before line j
            indent = ' ' * (len(lines[start]) - len(lines[start].lstrip()))
            planned = (j, f'{indent}""")\n')
            if planned not in insertions:
                insertions.append(planned)
                print(f"Found missing \"\"\"): insert before line {j+1} (exec at {start+1})")
            found_close = True  # treat as resolved
            break
    
print(f"\nTotal insertions planned: {len(insertions)}")

# Apply insertions in reverse order
for idx, text in sorted(set(insertions), key=lambda x: x[0], reverse=True):
    lines.insert(idx, text)
    print(f"Inserted at index {idx}: {text.rstrip()[:50]}")

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
