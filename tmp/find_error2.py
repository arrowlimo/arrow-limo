"""
Find all remaining unterminated triple-quote strings by checking paren balance
and identifying where code lines follow unclosed SQL.
"""
import ast

SRC = 'desktop_app/charter_form_widget.py'

with open(SRC, 'r', encoding='utf-8') as f:
    src = f.read()

# Find all syntax errors - compile iteratively
# The error at 6012 means a previous statement was malformed.
# Let's look at what's near 6012 that would be malformed.

lines = src.splitlines(True)

# Find lines around 6005-6025
print("Context around 6012:")
for i in range(6005, 6030):
    print(f"{i+1}: {repr(lines[i][:90])}")
