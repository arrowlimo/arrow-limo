#!/usr/bin/env python3
"""
Remove all emoji and special Unicode characters from Python scripts.
Replaces: [OK] → [OK], [WARN] → [WARN], [FAIL] → [FAIL], - → -
"""

import os
import glob
import re

def remove_emojis_from_file(filepath):
    """Remove emoji characters from a single file."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        original_content = content
        
        # Replace emojis with text equivalents
        content = content.replace('[OK]', '[OK]')
        content = content.replace('[WARN]', '[WARN]')
        content = content.replace('[FAIL]', '[FAIL]')
        content = content.replace('-', '-')  # Em dash to regular dash
        
        # If content changed, write it back
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        return False
        
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False

def main():
    # Find all Python files in scripts directory
    scripts_dir = r'l:\limo\scripts'
    pattern = os.path.join(scripts_dir, '*.py')
    files = glob.glob(pattern)
    
    print(f"Scanning {len(files)} Python files...")
    
    modified_count = 0
    
    for filepath in files:
        if remove_emojis_from_file(filepath):
            filename = os.path.basename(filepath)
            print(f"  Fixed: {filename}")
            modified_count += 1
    
    print(f"\nComplete: Modified {modified_count} files")

if __name__ == '__main__':
    main()
