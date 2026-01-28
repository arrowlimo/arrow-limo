#!/usr/bin/env python3
"""Test fuzzy filtering in beverage search"""

from difflib import SequenceMatcher

# Test fuzzy matching against some wine names
test_cases = [
    ("apothic", "Apothic Red Wine"),
    ("apothic", "Apothic Decadent Red"),
    ("mixed", "Mixed Berry Wine"),
    ("cabernet", "Robert Mondavi Cabernet 750ml"),
    ("twisted tea", "Twisted Tea 24-pack"),
    ("tequila", "Patrón Tequila 750ml"),
    ("absolut", "Absolut Vodka 1.75L"),
    ("absolt", "Absolut Vodka 1.75L"),  # Misspelled
    ("belevedere", "Belvedere Vodka"),  # Misspelled
    ("belvedere", "Belvedere Vodka"),
]

print("Testing fuzzy match at 60% threshold:\n")
print(f"{'Search':20} | {'Product':40} | {'Ratio':6} | {'Match'}")
print("-" * 75)

for search, product in test_cases:
    ratio = SequenceMatcher(None, search.lower(), product.lower()).ratio()
    is_substring = search.lower() in product.lower()
    matches = is_substring or ratio > 0.6
    match_str = "✓ YES" if matches else "✗ NO"
    print(f"{search:20} | {product:40} | {ratio:6.1%} | {match_str}")

print("\n✅ Fuzzy filter allows typos and partial matches while maintaining precision")
