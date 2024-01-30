# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import copy_metadata
import platform

python_version = platform.python_version()
last_dot = python_version.rfind('.')
python_version = python_version[0:last_dot]
datas = [('img/dpsg_logo.png', 'img'), ('img/favicon.ico', 'img')]
datas.append((f'.venv/lib/python{python_version}/site-packages/schwifty/bank_registry/', 'bank_registry'))
datas.append((f'.venv/lib/python{python_version}/site-packages/schwifty/iban_registry/', 'iban_registry'))
datas += collect_data_files('sv_ttk')
datas += collect_data_files('pycountry')
datas += collect_data_files('schwifty')
datas += copy_metadata('schwifty')


block_cipher = None


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=['babel.numbers'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='Nami Beitragsrechner',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['img/favicon.ico'],
)
app = BUNDLE(
    exe,
    name='Nami Beitragsrechner.app',
    icon='img/favicon.ico',
    bundle_identifier='com.nami-beitragsrechner',
)
