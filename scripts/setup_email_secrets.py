#!/usr/bin/env python3
import os
from getpass import getpass

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DOTENV = os.path.join(ROOT, '.env')

print('This will create/update .env at repo root (not committed).')
print('Values are stored locally; you can edit later in any editor.')

protocol = input('EMAIL_PROTOCOL [IMAP]: ').strip() or 'IMAP'
host = input('EMAIL_HOST [imap.ionos.com]: ').strip() or 'imap.ionos.com'
port = input('EMAIL_PORT [993]: ').strip() or '993'
username = input('EMAIL_USERNAME: ').strip()
password = getpass('EMAIL_PASSWORD: ')
use_ssl = input('EMAIL_USE_SSL [true]: ').strip().lower() or 'true'
folder = input('EMAIL_FOLDER [INBOX]: ').strip() or 'INBOX'
debug = input('EMAIL_DEBUG [false]: ').strip().lower() or 'false'

lines = [
    f'EMAIL_PROTOCOL={protocol}',
    f'EMAIL_HOST={host}',
    f'EMAIL_PORT={port}',
    f'EMAIL_USERNAME={username}',
    f'EMAIL_PASSWORD={password}',
    f'EMAIL_USE_SSL={use_ssl}',
    f'EMAIL_FOLDER={folder}',
    f'EMAIL_DEBUG={debug}',
]

with open(DOTENV, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines) + '\n')

print(f'\n✓ Wrote {DOTENV}')
print('Tip: You can review with Notepad and edit as needed.')
