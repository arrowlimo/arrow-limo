# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Arrow Limousine Management System Desktop App
Builds a standalone Windows executable with all dependencies bundled
"""

import os

block_cipher = None

a = Analysis(
    ['desktop_app/main.py'],
    pathex=['l:\\limo'],
    binaries=[],
    datas=[
        ('desktop_app/ai_knowledge_db', 'desktop_app/ai_knowledge_db'),
        ('desktop_app/mega_menu_structure.json', 'desktop_app'),
        ('config/', 'config'),
        ('.env', '.'),
    ],
    hiddenimports=[
        'PyQt6.QtWidgets',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWebEngineWidgets',
        'PyQt6.sip',
        'psycopg2',
        'psycopg2.extensions',
        'psycopg2.extras',
        'decimal',
        'dotenv',
        'reportlab',
        'reportlab.pdfgen',
        'reportlab.lib',
        'reportlab.lib.pagesizes',
        'reportlab.lib.styles',
        'reportlab.platypus',
        'openpyxl',
        'openpyxl.utils',
        'openpyxl.styles',
        'datetime',
        'json',
        'csv',
        'io',
        'email',
        'email.mime',
        'smtplib',
        'subprocess',
        'threading',
        'queue',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludedimports=['matplotlib', 'pandas', 'numpy'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ArrowLimousineApp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    icon='desktop_app/icon.ico' if os.path.exists('desktop_app/icon.ico') else None,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
