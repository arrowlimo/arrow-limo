#!/usr/bin/env python3
"""
Convert LMS vehicle format (Limo01, Limo1, Limo18) to L-X format (L-1, L-18).

LMS Format → L-X Format:
- Limo01, Limo1 → L-1
- Limo18 → L-18
- Limo22 → L-22

This allows matching LMS Reserve.Vehicle to charter.vehicle and vehicle_id.
"""

import re

def convert_lms_vehicle_to_l_format(lms_vehicle):
    """
    Convert LMS vehicle format to L-X format.
    
    Examples:
        Limo1 → L-1
        Limo01 → L-1
        Limo18 → L-18
        Limo22 → L-22
        limo03 → L-3
    
    Returns:
        String in L-X format, or None if format doesn't match
    """
    if not lms_vehicle:
        return None
    
    # Pattern: "Limo" followed by digits (with optional leading zeros)
    pattern = re.compile(r'^Limo0*(\d+)$', re.IGNORECASE)
    match = pattern.match(lms_vehicle.strip())
    
    if match:
        vehicle_num = int(match.group(1))  # Convert to int to strip leading zeros
        return f"L-{vehicle_num}"
    
    return None

def test_conversion():
    """Test the conversion function with known formats."""
    test_cases = [
        ("Limo1", "L-1"),
        ("Limo01", "L-1"),
        ("Limo18", "L-18"),
        ("Limo22", "L-22"),
        ("Limo03", "L-3"),
        ("limo19", "L-19"),
        ("LIMO11", "L-11"),
        ("Limo004", "L-4"),
        ("", None),
        (None, None),
        ("L-1", None),  # Already in L-X format
        ("Truck1", None),  # Different format
    ]
    
    print("=" * 80)
    print("LMS VEHICLE FORMAT CONVERSION TEST")
    print("=" * 80)
    print(f"\n{'Input':<15} → {'Expected':<10} {'Result':<10} {'Status':<10}")
    print("-" * 80)
    
    passed = 0
    failed = 0
    
    for input_val, expected in test_cases:
        result = convert_lms_vehicle_to_l_format(input_val)
        status = "✓ PASS" if result == expected else "✗ FAIL"
        input_str = f"'{input_val}'" if input_val else "None"
        expected_str = f"'{expected}'" if expected else "None"
        result_str = f"'{result}'" if result else "None"
        
        print(f"{input_str:<15} → {expected_str:<10} {result_str:<10} {status:<10}")
        
        if result == expected:
            passed += 1
        else:
            failed += 1
    
    print("-" * 80)
    print(f"\nTest Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("✓ All tests passed!")
    else:
        print(f"✗ {failed} test(s) failed")
    
    return failed == 0

if __name__ == '__main__':
    # Run tests
    success = test_conversion()
    
    # Example usage
    print("\n" + "=" * 80)
    print("USAGE EXAMPLE")
    print("=" * 80)
    print("\nIn other scripts, import and use:")
    print("```python")
    print("from convert_lms_vehicle_to_l_format import convert_lms_vehicle_to_l_format")
    print("")
    print("lms_vehicle = 'Limo18'")
    print("l_format = convert_lms_vehicle_to_l_format(lms_vehicle)")
    print(f"# Result: '{convert_lms_vehicle_to_l_format('Limo18')}'")
    print("```")
    
    exit(0 if success else 1)
