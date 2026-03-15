"""
Comprehensive f-string fixer - handles all remaining cases
"""
import ast
import re
from pathlib import Path

def comprehensive_fix(filepath):
    """Try multiple fix strategies"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # Strategy 1: Fix f-strings split across lines with { at end
    # Pattern: f"text {     <-- line ends after {
    #   variable}"
    content = re.sub(
        r'f(["\'])([^"\']*)\{\s+',
        r'f\1\2{',
        content
    )
    
    # Strategy 2: Remove newlines inside f-string braces
    # Find all f-strings and clean them
    def clean_fstring(match):
        quote = match.group(1)
        text_before_brace = match.group(2)
        brace_content = match.group(3)
        text_after = match.group(4)
        
        # Clean whitespace in brace content
        brace_content = re.sub(r'\s+', ' ', brace_content).strip()
        
        return f'f{quote}{text_before_brace}{{{brace_content}}}{text_after}{quote}'
    
    # Match f"text {content} rest"
    content = re.sub(
        r'f(["\'])([^{]*)\{\s*([^}]+?)\s*\}([^"\']*)\1',
        clean_fstring,
        content
    )
    
    # Strategy 3: Fix malformed lines (everything smashed together)
    #Fix lines like: self, "Success", f"text { value:.2f}") self.accept() except
    content = re.sub(
        r'\)\s*self\.accept\(\)\s*except',
        r')\n            self.accept()\n        except',
        content
    )
    
    content = re.sub(
        r'\)\s*except\s+Exception',
        r')\n        except Exception',
        content
    )
    
    content = re.sub(
        r'except\s+Exception:\s*try:',
        r'except Exception:\n            try:',
        content
    )
    
    # Strategy 4: Fix QMessageBox that got mangled
    content = re.sub(
        r'QMessageBox\.(\w+)\(\s*self,\s*"([^"]+)",\s*(f"[^"]+")(\)\s*\w)',
        r'QMessageBox.\1(\n                self, "\2", \3\n            )\4',
        content
    )
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

# Get all error files
desktop_app = Path("l:/limo/desktop_app")
skip_patterns = ['backup', 'BACKUP', 'OLD', 'BROKEN', 'CLEAN']

fixed_count = 0
for py_file in sorted(desktop_app.glob("*.py")):
    if any(pattern in py_file.name for pattern in skip_patterns):
        continue
    
    if comprehensive_fix(py_file):
        fixed_count += 1
        print(f"FIXED: {py_file.name}")

print(f"\nProcessed {fixed_count} files")
