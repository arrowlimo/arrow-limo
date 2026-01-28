
# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['installer_main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('main.py', '.'),
        ('desktop_app', 'desktop_app'),
        ('requirements.txt', '.'),
        ('.env.neon', '.'),
    ],
    hiddenimports=[
        'psycopg2',
        'PyQt6',
        'dotenv',
        'win32com.client',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ArrowLimoInstaller',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path here if you have one
)
