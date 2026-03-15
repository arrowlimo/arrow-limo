#!/usr/bin/env python3
"""Find all Python files with syntax errors (unclosed brackets, braces, parentheses)."""

import ast
import os
from pathlib import Path

def find_syntax_errors(directory):
    """Find all Python files with syntax errors."""
    errors = []
    
    for root, dirs, files in os.walk(directory):
        # Skip __pycache__ and other non-code directories
        dirs[:] = [d for d in dirs if d not in ['__pycache__', '.git', '.venv', 'node_modules']]
        
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    ast.parse(content)
                except SyntaxError as e:
                    errors.append({
                        'file': filepath,
                        'line': e.lineno,
                        'offset': e.offset,
                        'msg': e.msg,
                        'text': e.text
                    })
                except Exception as e:
                    errors.append({
                        'file': filepath,
                        'error': str(e)
                    })
    
    return errors

if __name__ == '__main__':
    errors = find_syntax_errors('desktop_app')
    
    if errors:
        print(f"Found {len(errors)} files with syntax errors:\n")
        for error in errors:
            if 'line' in error:
                print(f"File: {error['file']}")
                print(f"  Line {error['line']}, Col {error['offset']}: {error['msg']}")
                if error['text']:
                    print(f"  Text: {error['text'].rstrip()}")
                print()
            else:
                print(f"File: {error['file']}")
                print(f"  Error: {error['error']}")
                print()
    else:
        print("No syntax errors found!")
