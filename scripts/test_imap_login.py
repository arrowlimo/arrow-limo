#!/usr/bin/env python3
import imaplib
import ssl
from load_env import load_env, get_env

load_env()

HOST = get_env('EMAIL_HOST')
PORT = int(get_env('EMAIL_PORT', '993'))
USER = get_env('EMAIL_USERNAME')
PASS = get_env('EMAIL_PASSWORD')
SSL = get_env('EMAIL_USE_SSL', 'true').lower() == 'true'
FOLDER = get_env('EMAIL_FOLDER', 'INBOX')

assert HOST and USER and PASS, 'Missing EMAIL_HOST/EMAIL_USERNAME/EMAIL_PASSWORD in .env'

print(f'Connecting to {HOST}:{PORT} (SSL={SSL}) ...')

if SSL:
    ctx = ssl.create_default_context()
    M = imaplib.IMAP4_SSL(HOST, PORT, ssl_context=ctx)
else:
    M = imaplib.IMAP4(HOST, PORT)

print('Authenticating...')
M.login(USER, PASS)
print('✓ Authenticated')

print(f'Selecting folder: {FOLDER}')
status, _ = M.select(FOLDER, readonly=True)
print('✓ SELECT status:', status)

print('Fetching message count...')
status, data = M.search(None, 'ALL')
ids = data[0].split() if data and data[0] else []
print(f'✓ Messages in {FOLDER}: {len(ids)}')

M.logout()
print('✓ Logged out')
