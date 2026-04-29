"""
Systematically find and fix all missing \"\"\")\n using a state-machine approach.
"""
import ast

SRC = 'desktop_app/charter_form_widget.py'

with open(SRC, 'r', encoding='utf-8') as f:
    lines = f.readlines()

insertions = []

# State machine: track if we're inside a triple-quoted string
# When we find a line that looks like Python code but we think we're
# in a triple-quoted string, insert \"\"\") before that line.

in_triple = False
triple_open_line = -1
triple_open_indent = ""

i = 0
while i < len(lines):
    line = lines[i]
    stripped = line.strip()
    
    # Count triple-quote occurrences on this line
    tq_count = line.count('"""')
    
    if not in_triple:
        if tq_count % 2 == 1:  # opens a triple string
            in_triple = True
            triple_open_line = i
            triple_open_indent = ' ' * (len(line) - len(line.lstrip()))
    else:
        # We're inside a triple string
        if tq_count % 2 == 1:  # closes the triple string
            in_triple = False
        elif tq_count == 0:
            # Still in triple - check if this line looks like Python code
            # (not SQL content)
            if stripped and not stripped.startswith('--') and not stripped.startswith('#'):
                # Heuristic: if the line looks like a Python statement
                python_keywords = ['has_charter_data', 'table_exists', 'row_exists',
                                   'rows =', 'row =', 'result =', 'max_val',
                                   'new_reserve', 'counts =', 'data =',
                                   'has_dropoff', 'if self.', 'if has_',
                                   'out_of_town = ', 'reserve_number =',
                                   'chartered =', 'col_exists']
                if any(stripped.startswith(kw) for kw in python_keywords):
                    # This line should NOT be inside a triple string
                    # Insert """) before it
                    ind = triple_open_indent
                    print(f"Missing \"\"\"): before line {i+1} (opened at {triple_open_line+1})")
                    print(f"  Line content: {stripped[:70]}")
                    insertions.append((i, f'{ind}""")\n'))
                    in_triple = False  # treat as closed
    i += 1

print(f"\nTotal insertions: {len(insertions)}")

# Apply in reverse order
for idx, text in sorted(insertions, key=lambda x: x[0], reverse=True):
    lines.insert(idx, text)
    print(f"Inserted at line {idx+1}: {text.rstrip()[:50]}")

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
