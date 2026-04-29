"""
Scan charter_form_widget.py for paren-balance errors introduced by bulk fix script.
Find lines where a string literal ends without matching ), when the next non-blank
keyword line suggests the call should have been closed.
"""
with open('desktop_app/charter_form_widget.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Track paren/bracket depth line by line
# When depth drops to 0 mid-expression (at a string line), the ) is missing
depth = 0
fixes = 0
in_triple = False

for i, line in enumerate(lines):
    stripped = line.strip()
    
    # Skip triple-quoted strings
    count_triple = stripped.count('"""') + stripped.count("'''")
    if count_triple % 2 == 1:
        in_triple = not in_triple
    if in_triple:
        continue
    
    # Count parens/brackets (rough)
    for ch in stripped:
        if ch in '([{':
            depth += 1
        elif ch in ')]}':
            depth -= 1
    
    # If we're currently inside an open call (depth > 0)
    # and this line ends a string but next non-blank line starts with
    # except/else/finally/elif/return/def/class (things that can't be args),
    # then we're missing a closing )
    if depth > 0 and (stripped.endswith('"') or stripped.endswith("'")):
        # Find next non-blank line
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j < len(lines):
            next_stripped = lines[j].strip()
            keywords = ('except ', 'else:', 'finally:', 'elif ', 'return ', 
                        'def ', 'class ', '# ', 'self.', 'conn', 'cur.', 
                        'if ', 'for ', 'with ')
            if any(next_stripped.startswith(kw) for kw in keywords):
                print(f"POSSIBLE MISSING ) at line {i+1}: {stripped[:70]}")
                print(f"  Next line {j+1}: {next_stripped[:60]}")
                print(f"  Current depth: {depth}")
                print()

print("Scan complete")
