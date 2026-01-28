#!/usr/bin/env python3
"""Test login with known credentials"""
import os
os.environ['DB_HOST'] = 'localhost'
os.environ['DB_NAME'] = 'almsdata'
os.environ['DB_USER'] = 'postgres'
os.environ['DB_PASSWORD'] = '***REMOVED***'

import sys
sys.path.insert(0, 'desktop_app')

from login_manager import LoginManager

mgr = LoginManager()

# Test with paulr - need to know actual password
test_cases = [
    ('paulr', 'test'),
    ('paulr', 'password'),
    ('paulr', 'paulr'),
]

for username, password in test_cases:
    try:
        print(f'\nTrying {username}:{password}...')
        result = mgr.authenticate(username, password)
        print(f'  ✓ SUCCESS: {result}')
    except Exception as e:
        print(f'  ✗ FAILED: {e}')
