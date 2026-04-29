"""
Smart E501 fixer for receipt_search_match_widget.py.
Handles: SQL string fragments, comments, docstrings, long code lines.
"""
import ast
import re
import textwrap

SRC = 'desktop_app/receipt_search_match_widget.py'
MAX = 79


def split_at_word(text, max_col):
    """Split `text` at the last space at/before max_col. Return (head, tail)."""
    if len(text) <= max_col:
        return text, ''
    cut = text.rfind(' ', 0, max_col)
    if cut == -1:
        cut = text.find(' ', max_col)
    if cut == -1:
        return text, ''
    return text[:cut], text[cut + 1:]


def wrap_comment(line, max_col=MAX):
    """Split a trailing # comment so the code part + comment stay in cols."""
    stripped = line.rstrip()
    # Find a '#' that is not inside a string
    in_str = None
    for i, ch in enumerate(stripped):
        if in_str:
            if ch == in_str and (i == 0 or stripped[i - 1] != '\\'):
                in_str = None
        elif ch in ('"', "'"):
            in_str = ch
        elif ch == '#':
            code_part = stripped[:i].rstrip()
            comment_text = stripped[i + 1:].strip()
            indent = ' ' * (len(code_part) - len(code_part.lstrip()))
            # If code part itself is <= max, keep code & shorten comment
            if len(code_part) <= max_col:
                # Wrap the comment text across multiple lines
                comment_indent = indent + '# '
                avail = max_col - len(comment_indent)
                if avail < 20:
                    return None  # can't help
                words = comment_text.split()
                lines_out = []
                cur = ''
                for word in words:
                    if cur and len(cur) + 1 + len(word) > avail:
                        lines_out.append(comment_indent + cur)
                        cur = word
                    elif cur:
                        cur += ' ' + word
                    else:
                        cur = word
                if cur:
                    lines_out.append(comment_indent + cur)
                if len(lines_out) == 1:
                    # Only one comment line - check if it's already short enough
                    full = code_part + '  # ' + comment_text
                    if len(full) <= max_col:
                        return full + '\n'
                    # Otherwise put comment on next line
                    return code_part + '\n' + lines_out[0] + '\n'
                result = code_part + '  ' + lines_out[0].lstrip() + '\n'
                for cl in lines_out[1:]:
                    result += cl + '\n'
                return result
            break
    return None


def split_string_fragment(line, max_col=MAX):
    """
    For a line that is a string fragment in implicit concatenation:
        INDENT "SQL CONTENT HERE",   (may or may not have comma)
    Split the string at a word boundary.
    """
    stripped = line.rstrip()
    indent = ' ' * (len(stripped) - len(stripped.lstrip()))
    s = stripped.lstrip()

    # Detect string fragment: starts with " or '
    if not (s.startswith('"') or s.startswith("'")):
        return None

    # Find the quote char
    q = s[0]
    # Find where string ends (account for triple-quote vs single-quote)
    if s.startswith(q * 3):
        return None  # triple-quoted, skip

    # Find end of string
    try:
        end_idx = 1
        while end_idx < len(s):
            if s[end_idx] == '\\':
                end_idx += 2
                continue
            if s[end_idx] == q:
                break
            end_idx += 1
        content = s[1:end_idx]
        suffix = s[end_idx + 1:]  # comma, etc.
    except Exception:
        return None

    # Find a space in content to split at
    # We want: indent + '"' + head + '"' to be <= max_col
    avail = max_col - len(indent) - 2  # 2 for quotes
    if avail < 20:
        return None

    # Try to split at the last space at/before avail chars
    split_pos = content.rfind(' ', 0, avail)
    if split_pos == -1:
        # Try finding any space
        split_pos = content.find(' ', avail)
    if split_pos == -1 or split_pos == len(content) - 1:
        return None

    head = content[:split_pos + 1]  # include trailing space
    tail = content[split_pos + 1:]

    # Verify the split fixes the issue
    line1 = indent + q + head + q
    line2 = indent + q + tail + q + suffix

    if len(line1) > max_col or len(line2) > max_col:
        # Try splitting at a different position
        avail2 = max_col - len(indent) - 2
        split_pos2 = content.rfind(' ', 0, avail2)
        if split_pos2 != -1 and split_pos2 != split_pos:
            head2 = content[:split_pos2 + 1]
            tail2 = content[split_pos2 + 1:]
            line1b = indent + q + head2 + q
            line2b = indent + q + tail2 + q + suffix
            if len(line1b) <= max_col and len(line2b) <= max_col:
                return line1b + '\n' + line2b + '\n'
        # Maybe the tail is still too long - return partial fix
        if len(line1) <= max_col:
            return line1 + '\n' + line2 + '\n'
        return None

    return line1 + '\n' + line2 + '\n'


def wrap_single_docstring(line, max_col=MAX):
    """Convert single-line docstring that's too long to multi-line."""
    stripped = line.rstrip()
    indent = ' ' * (len(stripped) - len(stripped.lstrip()))
    s = stripped.lstrip()

    # Match: """content""" or '''content'''
    m = re.match(r'^(\"\"\"|\'\'\')(.*)(\"\"\"|\'\'\')$', s)
    if not m:
        return None

    q = m.group(1)
    content = m.group(2)

    avail = max_col - len(indent)
    if len(s) <= avail:
        return None

    # Break at word boundary
    lines_out = textwrap.wrap(content, avail - len(q))
    if not lines_out:
        return None

    result = indent + q + lines_out[0] + '\n'
    for part in lines_out[1:]:
        result += indent + part + '\n'
    result += indent + q + '\n'
    return result


def docstring_content_line(line, max_col=MAX):
    """
    For a line inside a multi-line docstring (no quotes, just text),
    wrap at word boundary.
    """
    stripped = line.rstrip()
    if len(stripped) <= max_col:
        return None
    indent = ' ' * (len(stripped) - len(stripped.lstrip()))
    content = stripped.lstrip()

    # Only pure text lines (no Python syntax)
    if content.startswith(('def ', 'class ', 'if ', 'return ', 'self.', '#')):
        return None
    if '=' in content and not content.startswith(('-', '*', 'Returns', 'Args')):
        return None
        # Reject lines with string literals or code constructs
        if '"' in content or "'" in content or '(' in content:
            return None

    avail = max_col - len(indent)
    if avail < 20:
        return None

    # Find split point
    split_at = content.rfind(' ', 0, avail)
    if split_at == -1:
        return None
    head = content[:split_at]
    tail = content[split_at + 1:]
    if not tail:
        return None

    return indent + head + '\n' + indent + tail + '\n'


with open(SRC, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Detect which lines are inside triple-quoted strings
def find_triple_string_ranges(lines):
    """Return set of line indices (0-based) that are inside triple-quoted strings."""
    in_triple = False
    triple_char = None
    ranges = set()
    for i, line in enumerate(lines):
        if in_triple:
            ranges.add(i)
            # Check if this line ends the triple string
            end = line.find(triple_char)
            if end != -1:
                in_triple = False
                triple_char = None
        else:
            # Count triple-quote starts
            j = 0
            while j < len(line):
                if line[j] in ('"', "'"):
                    q = line[j]
                    if line[j:j+3] == q * 3:
                        # Start of triple string
                        # Find if it closes on same line
                        close = line.find(q * 3, j + 3)
                        if close != -1:
                            j = close + 3
                            continue
                        else:
                            in_triple = True
                            triple_char = q * 3
                            break
                    else:
                        # Regular string - skip
                        j += 1
                        while j < len(line) and line[j] != q:
                            if line[j] == '\\':
                                j += 1
                            j += 1
                j += 1
    return ranges

triple_ranges = find_triple_string_ranges(lines)

fixed_count = 0
new_lines = list(lines)
i = 0
while i < len(new_lines):
    line = new_lines[i]
    if len(line.rstrip()) <= MAX:
        i += 1
        continue

    # --- Determine context ---
    stripped = line.lstrip()

    # 1. Single-line docstring
    if re.match(r'^(\"\"\"|\'\'\').*\1\s*$', stripped):
        result = wrap_single_docstring(line)
        if result:
            replacement = result.splitlines(keepends=True)
            new_lines[i:i+1] = replacement
            fixed_count += 1
            i += len(replacement)
            continue

    # 2. Inside triple-quoted string (docstring content or SQL)
    if i in triple_ranges and not stripped.startswith(('"', "'")):
        # Plain text line inside docstring — wrap at word boundary
        result = docstring_content_line(line)
        if result:
            replacement = result.splitlines(keepends=True)
            new_lines[i:i+1] = replacement
            fixed_count += 1
            i += len(replacement)
            continue

    # 3. String fragment (starts with quote, likely SQL in parenthesized list)
    if stripped.startswith('"') or stripped.startswith("'"):
        result = split_string_fragment(line)
        if result:
            replacement = result.splitlines(keepends=True)
            new_lines[i:i+1] = replacement
            fixed_count += 1
            i += len(replacement)
            continue

    # 4. Comment line — trim trailing comment
    result = wrap_comment(line)
    if result:
        replacement = result.splitlines(keepends=True)
        # Only apply if it actually fixes the violation
        if all(len(l.rstrip()) <= MAX for l in replacement):
            new_lines[i:i+1] = replacement
            fixed_count += 1
            i += len(replacement)
            continue

    i += 1

print(f"Fixed {fixed_count} lines")

with open(SRC, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

# Verify
with open(SRC, 'r', encoding='utf-8') as f:
    src = f.read()
try:
    ast.parse(src)
    print("SYNTAX OK!")
except SyntaxError as e:
    src_lines = src.splitlines()
    print(f"SyntaxError at line {e.lineno}: {e.msg}")
    for j in range(max(0, e.lineno - 3), min(len(src_lines), e.lineno + 3)):
        print(f"  {j+1}: {src_lines[j][:100]}")

# Count remaining
import subprocess
result = subprocess.run(
    [r'.venv\Scripts\python.exe', '-m', 'flake8',
     'desktop_app/receipt_search_match_widget.py',
     '--select', 'E501,E999', '--format=%(row)d:%(col)d %(text)s'],
    capture_output=True, text=True
)
all_lines = (result.stdout + result.stderr).strip().splitlines()
print(f"Remaining violations: {len(all_lines)}")
